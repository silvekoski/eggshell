"""Second opinion on every episode label, from NVIDIA Nemotron 3.5 Super VL.

The simulator labels each episode from thresholds (lift >= 5 cm, force >
crack threshold). Thresholds miss things: an egg that was lifted and then
dropped from height still counts as "lifted". This step runs after the
episodes are saved, never in the control loop:

1. Evidence: the camera keyframes of the episode (first contact, peak force,
   highest lift, end) plus a compact force/lift timeline from the .npz log.
2. Nemotron looks at both and returns strict JSON: outcome (lifted, dropped,
   not_lifted, crushed), confidence, a reason, and evidence items that cite a
   frame name or the log with a timestamp.
3. Validation: the JSON must match the schema and cite only frames that exist.
   If not, one repair request with the exact error.
4. Grounding check: the peak force and the highest lift that the model states
   must match the log. If they do not, one self-check request that shows the
   model its numbers next to the logged ones.
5. Cross-check with the simulator label. A disagreement or an ungrounded answer
   is flagged for human review. The simulator label is never overwritten.

Results go to `reviews.jsonl` and `review.md` in the dataset directory.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .nemotron import DISPLAY_NAME, NemotronClient, NemotronError, NemotronNotConfigured, image_part

OUTCOMES = ("lifted", "dropped", "not_lifted", "crushed")
TIMELINE_ROWS = 24
FORCE_TOL_N, FORCE_TOL_REL = 0.5, 0.15
LIFT_TOL_CM, LIFT_TOL_REL = 1.0, 0.15
MAX_CALLS = 3  # first answer + one repair + one self-check, per episode

SYSTEM_PROMPT = f"""You review robot grasp attempts for a teleoperation dataset.
A human wearing a data glove drives a simulated Shadow robot hand. The task is to pick up an egg
from a table without crushing it. The egg is white when untouched, turns orange as the grip force
rises, and turns red once it has cracked. You get camera frames of key moments and a force/lift log.

Label the attempt with exactly one outcome:
- "crushed": the egg cracked (red in a frame, or the peak force went above the crack threshold).
- "dropped": the egg was raised but then fell: the grip force went to about 0 while the egg was
  still high, and the egg came down fast (high descent speed), or it ended away from the hand.
- "lifted": the egg was raised at least 5 cm, intact, and was held or set down under control.
- "not_lifted": the egg never rose 5 cm and did not crack.

Rules:
- Use only what the frames and the log show. Cite each piece of evidence with its source:
  "frame:<name>" for a frame (use the names given) or "log" for the log, and the time in seconds.
- State the peak force (N) and the highest lift (cm) exactly as you read them from the log.
- Reply with one JSON object and nothing else:
{{"outcome": one of {list(OUTCOMES)},
  "confidence": number 0..1,
  "reason": "one or two sentences",
  "egg_red_in_frames": true or false,
  "claimed_peak_force_n": number,
  "claimed_max_lift_cm": number,
  "evidence": [{{"source": "frame:<name>" or "log", "t": seconds, "observation": "..."}}]}}"""


@dataclass
class Evidence:
    episode: int
    sim_label: dict
    timeline: str
    facts: dict
    frames: list[dict] = field(default_factory=list)  # {name, t, png}


def load_evidence(dataset: Path, entry: dict) -> Evidence:
    data = np.load(dataset / entry["file"])
    t = np.asarray(data["t"], dtype=float)
    force = np.asarray(data["egg_force"], dtype=float)
    z = np.asarray(data["egg_pose"], dtype=float)[:, 2]
    lift = z - z[0]
    vz = np.gradient(lift, t) if len(t) > 2 else np.zeros_like(lift)
    idx = np.unique(np.linspace(0, len(t) - 1, min(TIMELINE_ROWS, len(t))).round().astype(int))
    rows = ["t_s, force_n, lift_cm"] + [f"{t[i]:.2f}, {force[i]:.2f}, {lift[i] * 100:.1f}" for i in idx]
    facts = {
        "duration_s": round(float(t[-1] - t[0]), 2) if len(t) else 0.0,
        "peak_force_n": round(float(force.max()), 2) if len(t) else 0.0,
        "t_peak_force_s": round(float(t[int(force.argmax())]), 2) if len(t) else 0.0,
        "max_lift_cm": round(float(lift.max()) * 100, 1) if len(t) else 0.0,
        "t_max_lift_s": round(float(t[int(lift.argmax())]), 2) if len(t) else 0.0,
        "final_lift_cm": round(float(lift[-1]) * 100, 1) if len(t) else 0.0,
        "max_descent_speed_m_s": round(float(max(0.0, -vz.min())), 3) if len(t) else 0.0,
        "final_force_n": round(float(force[-1]), 2) if len(t) else 0.0,
        "crack_threshold_n": entry.get("crack_force_n", 8.0),
    }
    frames = []
    for kf in entry.get("keyframes", []):
        p = dataset / kf["file"]
        if p.exists():
            frames.append({"name": kf["name"], "t": kf["t"], "png": p.read_bytes()})
    return Evidence(entry["episode"], entry, "\n".join(rows), facts, frames)


def build_messages(ev: Evidence) -> list[dict]:
    if ev.frames:
        frame_list = ", ".join(f"{f['name']} (t={f['t']:.2f}s)" for f in ev.frames)
    else:
        frame_list = "none (no camera frames were saved for this episode: use the log only)"
    text = (f"Episode {ev.episode}.\nFrames, in order: {frame_list}\n"
            f"Log facts: {json.dumps(ev.facts)}\nForce/lift timeline:\n{ev.timeline}")
    content: list[dict] = [{"type": "text", "text": text}]
    for f in ev.frames:
        content.append({"type": "text", "text": f"frame:{f['name']} t={f['t']:.2f}s"})
        content.append(image_part(f["png"]))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]


def parse_answer(text: str, frame_names: set[str]) -> tuple[dict | None, str | None]:
    """Returns (answer, None) or (None, error message for the repair request)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None, "no JSON object found in the reply"
    try:
        a = json.loads(m.group(0))
    except ValueError as e:
        return None, f"invalid JSON: {e}"
    if not isinstance(a, dict):
        return None, "the reply must be a JSON object"
    if a.get("outcome") not in OUTCOMES:
        return None, f"outcome must be one of {list(OUTCOMES)}, got {a.get('outcome')!r}"
    for k in ("confidence", "claimed_peak_force_n", "claimed_max_lift_cm"):
        if not isinstance(a.get(k), (int, float)) or isinstance(a.get(k), bool):
            return None, f"{k} must be a number"
    if not isinstance(a.get("reason"), str) or not a["reason"].strip():
        return None, "reason must be a non-empty string"
    ev = a.get("evidence")
    if not isinstance(ev, list) or not ev:
        return None, "evidence must be a non-empty list"
    for item in ev:
        src = item.get("source", "") if isinstance(item, dict) else ""
        if src != "log" and not (src.startswith("frame:") and src[6:] in frame_names):
            return None, (f"evidence source {src!r} is not 'log' or one of the frames "
                          f"{sorted('frame:' + n for n in frame_names)}")
    a["confidence"] = float(min(1.0, max(0.0, a["confidence"])))
    return a, None


def grounding_errors(a: dict, facts: dict) -> list[str]:
    errs = []
    pf, cf = facts["peak_force_n"], float(a["claimed_peak_force_n"])
    if abs(cf - pf) > max(FORCE_TOL_N, FORCE_TOL_REL * pf):
        errs.append(f"you said peak force {cf:g} N, the log says {pf:g} N")
    ml, cl = facts["max_lift_cm"], float(a["claimed_max_lift_cm"])
    if abs(cl - ml) > max(LIFT_TOL_CM, LIFT_TOL_REL * abs(ml)):
        errs.append(f"you said highest lift {cl:g} cm, the log says {ml:g} cm")
    if a["outcome"] == "crushed" and pf <= facts["crack_threshold_n"] and not a.get("egg_red_in_frames"):
        errs.append("you said crushed, but the peak force is below the crack threshold and no frame shows a red egg")
    return errs


def review_episode(client: NemotronClient, ev: Evidence) -> dict:
    """One episode: at most MAX_CALLS requests. Raises NemotronError if the API fails."""
    messages = build_messages(ev)
    names = {f["name"] for f in ev.frames}
    steps: list[str] = []
    answer, err, calls = None, None, 0
    while calls < MAX_CALLS:
        reply = client.chat(messages)
        calls += 1
        answer, err = parse_answer(reply, names)
        if err and reply.startswith("(empty reply"):
            err = reply.strip("()")
        if err:
            steps.append(f"repair: {err}")
            messages = messages + [{"role": "assistant", "content": reply},
                                   {"role": "user", "content": f"Your reply was rejected: {err}. "
                                    "Reply again with only the JSON object."}]
            continue
        g = grounding_errors(answer, ev.facts)
        if g and not any(s.startswith("self-check") for s in steps):
            steps.append("self-check: " + "; ".join(g))
            messages = messages + [{"role": "assistant", "content": reply},
                                   {"role": "user", "content": "Check your answer against the log: " + "; ".join(g)
                                    + ". Look at the frames and the log again and reply with the corrected JSON object."}]
            continue
        break
    sim_outcome = ev.sim_label.get("outcome")
    out = {"episode": ev.episode, "model": DISPLAY_NAME, "model_id": client.model,
           "sim_outcome": sim_outcome, "frames": sorted(names), "calls": calls, "steps": steps,
           "reviewed": time.time()}
    if answer is None:
        return {**out, "status": "invalid", "flag": True, "note": err}
    g = grounding_errors(answer, ev.facts)
    agree = answer["outcome"] == sim_outcome
    status = "ungrounded" if g else ("agree" if agree else "disagree")
    return {**out, "status": status, "flag": status != "agree", "outcome": answer["outcome"],
            "confidence": answer["confidence"], "reason": answer["reason"], "evidence": answer["evidence"],
            "egg_red_in_frames": bool(answer.get("egg_red_in_frames")), "grounding": g or ["ok"],
            "log_facts": ev.facts}


def review_dataset(dataset: Path, client: NemotronClient | None = None, episodes: list[int] | None = None,
                   force: bool = False) -> list[dict]:
    dataset = Path(dataset)
    index = dataset / "episodes.jsonl"
    if not index.exists():
        raise FileNotFoundError(f"no episodes in {dataset} (run `teleop demo` first)")
    client = client or NemotronClient(cache_dir=dataset / ".nemotron_cache")
    entries = [json.loads(line) for line in index.open() if line.strip()]
    if episodes is not None:
        entries = [e for e in entries if e["episode"] in episodes]
    out_path = dataset / "reviews.jsonl"
    done = {}
    if out_path.exists() and not force:
        for line in out_path.open():
            r = json.loads(line)
            if r.get("status") in ("agree", "disagree", "ungrounded"):
                done[r["episode"]] = r
    results = []
    for e in entries:
        if e["episode"] in done:
            results.append(done[e["episode"]])
            continue
        if not client.configured():
            results.append({"episode": e["episode"], "model": DISPLAY_NAME, "sim_outcome": e.get("outcome"),
                            "status": "not_configured", "flag": False,
                            "note": "Nemotron not configured: set NVIDIA_API_KEY. The simulator label stands."})
            continue
        try:
            results.append(review_episode(client, load_evidence(dataset, e)))
        except NemotronNotConfigured as err:
            results.append({"episode": e["episode"], "status": "not_configured", "note": str(err), "flag": False})
        except NemotronError as err:
            results.append({"episode": e["episode"], "model": DISPLAY_NAME, "sim_outcome": e.get("outcome"),
                            "status": "unavailable", "flag": False,
                            "note": f"Nemotron unavailable: {err}. The simulator label stands."})
    keep = {r["episode"]: r for r in done.values()}
    keep.update({r["episode"]: r for r in results})
    with out_path.open("w") as fh:
        for ep in sorted(keep):
            fh.write(json.dumps(keep[ep]) + "\n")
    (dataset / "review.md").write_text(render_report(sorted(keep.values(), key=lambda r: r["episode"])))
    return results


def render_report(results: list[dict]) -> str:
    lines = [f"# Episode review by {DISPLAY_NAME}", "",
             "The simulator label comes from thresholds. Nemotron labels the same episode from the camera "
             "keyframes and the force/lift log. Flagged rows need a human look.", "",
             "| Episode | Simulator | Nemotron 3.5 Super VL | Confidence | Status | Reason |",
             "|---|---|---|---|---|---|"]
    for r in results:
        conf = f"{r['confidence']:.2f}" if "confidence" in r else "-"
        flag = "FLAG " if r.get("flag") else ""
        reason = (r.get("reason") or r.get("note") or "").replace("|", "/").replace("\n", " ")
        lines.append(f"| {r['episode']} | {r.get('sim_outcome', '-')} | {r.get('outcome', '-')} | {conf} | "
                     f"{flag}{r['status']} | {reason} |")
    for r in results:
        if r.get("evidence"):
            lines += ["", f"## Episode {r['episode']}: evidence cited by {DISPLAY_NAME}", ""]
            lines += [f"- `{e.get('source')}` t={e.get('t')}: {e.get('observation')}" for e in r["evidence"]]
            lines.append(f"- Grounding check against the log: {'; '.join(r.get('grounding', []))}")
            if r.get("steps"):
                lines.append(f"- Repair and self-check steps: {'; '.join(r['steps'])}")
    return "\n".join(lines) + "\n"


def summary_line(r: dict) -> str:
    if r["status"] in ("not_configured", "unavailable", "invalid"):
        return f"episode {r['episode']}: sim={r.get('sim_outcome')} | {DISPLAY_NAME}: {r['status']} ({r.get('note')})"
    flag = "  <-- FLAG for review" if r.get("flag") else ""
    return (f"episode {r['episode']}: sim={r['sim_outcome']} | {DISPLAY_NAME}={r['outcome']} "
            f"({r['confidence']:.2f}) {r['status']}: {r['reason']}{flag}")
