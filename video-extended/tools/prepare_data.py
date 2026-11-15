# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow"]
# ///
"""Data for the scenes, from the real demo run of rokoko-teleop.

Run from the video project:  uv run tools/prepare_data.py
Needs ffmpeg on PATH. Writes assets/data/: the demo clips, still frames, keyframes and data.js.

Sources (all in rokoko-teleop/):
  out/demo-{egg,crush,drop,miss}.mp4         clips rendered by `teleop demo` (scripted operator, simulated glove input)
  datasets/demo/episode_000N_*.png       keyframes saved with each episode
  datasets/demo/episode_000N.npz         per-frame log: t, egg_pose, egg_force, inspire
  docs/demo-run/episodes.jsonl           simulator labels
  docs/demo-run/reviews.jsonl            Nemotron 3.5 Super VL review
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

VIDEO = Path(__file__).resolve().parent.parent
ROOT = VIDEO.parent
OUT = VIDEO / "assets/data"
DEMO = ROOT / "datasets/demo"


def frame(clip: Path, at: float | str, dest: Path) -> None:
    """One frame of a clip as a JPEG. at = seconds, or "last"."""
    if at == "last":
        args = ["-sseof", "-0.1", "-i", str(clip), "-update", "1"]
    else:
        args = ["-ss", str(at), "-i", str(clip)]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-frames:v", "1", "-q:v", "2", str(dest)], check=True)


def jpg(src: Path, dest: Path) -> None:
    Image.open(src).convert("RGB").save(dest, quality=92)


def series(npz: Path, hz: float = 30.0) -> dict:
    d = np.load(npz)
    t, force = d["t"], d["egg_force"]
    lift = (d["egg_pose"][:, 2] - d["egg_pose"][0, 2]) * 100.0  # cm above the height at t = 0
    step = max(1, int(round((1.0 / hz) / (t[1] - t[0]))))
    idx = np.arange(0, len(t), step)
    return {"t": [round(float(x), 3) for x in t[idx]], "force": [round(float(x), 3) for x in force[idx]],
            "lift": [round(float(x), 2) for x in lift[idx]], "inspire": d["inspire"][idx].astype(int).tolist(),
            "dur": round(float(t[-1]), 3)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("egg", "crush", "drop", "miss"):
        clip = ROOT / f"out/demo-{name}.mp4"
        shutil.copyfile(clip, OUT / f"{name}.mp4")
        frame(clip, 0, OUT / f"{name}-first.jpg")
        frame(clip, "last", OUT / f"{name}-last.jpg")
    frame(ROOT / "out/demo-egg.mp4", 3.9, OUT / "egg-at-3.9.jpg")   # the first frame of scene 3 (media start 3.9 s)
    frame(ROOT / "out/demo-crush.mp4", 1.0, OUT / "crush-at-1.0.jpg")
    frame(ROOT / "out/demo-drop.mp4", 6.2, OUT / "drop-falling.jpg")  # the egg falls under the open hand

    for png in sorted(DEMO.glob("episode_000?_*.png")):
        jpg(png, OUT / (png.stem.replace("episode_", "ep") + ".jpg"))

    labels = [json.loads(line) for line in (ROOT / "docs/demo-run/episodes.jsonl").read_text().splitlines() if line.strip()]
    reviews = [json.loads(line) for line in (ROOT / "docs/demo-run/reviews.jsonl").read_text().splitlines() if line.strip()]
    data = {
        "episodes": [{k: e[k] for k in ("episode", "file", "outcome", "max_lift_m", "peak_force_n", "crack_force_n")} for e in labels],
        "reviews": [{k: r[k] for k in ("episode", "sim_outcome", "outcome", "confidence", "status", "flag", "model", "model_id")} for r in reviews],
        "crush": series(DEMO / "episode_0001.npz"),
        "drop": series(DEMO / "episode_0002.npz"),
        "egg": series(DEMO / "episode_0000.npz", hz=15.0),
    }
    for k in ("crush", "drop"):
        data[k].pop("inspire")
    # extended cut: the recorded (scripted) glove skeleton, the human angles and the actions of episode 0,
    # and a 24-row force/lift timeline of episode 2 like the one the review sends
    d0 = np.load(DEMO / "episode_0000.npz")
    idx = np.arange(0, len(d0["t"]), 4)  # 15 Hz
    rel = d0["glove"][idx, :, :3] - d0["glove"][idx, 1:2, :3]  # joint positions relative to the wrist, metres
    data["egg"]["glove"] = np.round(rel, 4).tolist()
    data["egg"]["angles"] = np.round(d0["human_angles"][idx], 3).tolist()
    data["egg"]["action"] = np.round(d0["action"][idx], 3).tolist()
    data["shapes"] = {k: list(d0[k].shape) for k in d0.files}
    d2 = data["drop"]
    rows = np.linspace(0, len(d2["t"]) - 1, 24).round().astype(int)
    data["timeline24"] = [[d2["t"][i], d2["force"][i], d2["lift"][i]] for i in rows]
    # studio footage (1920x1080, no HUD) from scripts/render_footage.py, kept in assets/footage/ (committed):
    # per-frame force, lift and crack state for the overlays, and stills of the first and last frames
    FOOT = VIDEO / "assets/footage"  # copied from ../video/assets/footage (git-ignored here)
    FOOT.mkdir(parents=True, exist_ok=True)
    for f in (VIDEO.parent / "video/assets/footage").iterdir():
        shutil.copyfile(f, FOOT / f.name)
    data["footage"] = {}
    for name in ("egg", "crush", "drop", "miss"):
        side = json.loads((FOOT / f"{name}.json").read_text())
        fr = side["frames"]
        data["footage"][name] = {"fps": side["fps"], "crack_force_n": side["crack_force_n"],
                                 "force": [round(f["force_n"], 2) for f in fr], "lift": [round(f["lift_cm"], 2) for f in fr],
                                 "cracked": [1 if f["cracked"] else 0 for f in fr]}
        frame(FOOT / f"{name}.mp4", 0, OUT / f"hd-{name}-first.jpg")
        frame(FOOT / f"{name}.mp4", "last", OUT / f"hd-{name}-last.jpg")
    for name, at in (("egg", 3.9), ("egg", 12.0), ("egg", 2.4), ("egg", 1.75), ("egg", 4.0), ("egg", 7.0), ("crush", 0.0), ("crush", 0.65), ("drop", 5.0)):
        frame(FOOT / f"{name}.mp4", at, OUT / f"hd-{name}-at-{at}.jpg")
    (OUT / "data.js").write_text("window.VIDEO_DATA = " + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("wrote", len(list(OUT.iterdir())), "files to", OUT)
    print("crush peak", max(data["crush"]["force"]), "drop max lift", max(data["drop"]["lift"]))


if __name__ == "__main__":
    main()
