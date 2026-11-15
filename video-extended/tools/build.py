# /// script
# requires-python = ">=3.11"
# ///
"""Timing, captions and the root composition, from the voice clips.

Run from the video project, after make_voice.sh and align_words.py:  uv run tools/build.py
Writes assets/timing.js, compositions/captions.html, out/<name>.srt, assets/sfx/tick.wav and index.html.
Reads video.json (name, title) and cues.json (optional: series of times between two phrases, with or without ticks).

A scene lasts as long as its voice clip plus 0.5 s: 0.2 s before the voice and 0.3 s after it.
video.json may add a pause after the voice: "pad": {"s09": 2.0} (seconds per scene), for example for an end card.
"""
from __future__ import annotations

import json
import math
import re
import struct
import subprocess
import wave
from pathlib import Path

VIDEO = Path(__file__).resolve().parent.parent
LEAD, TAIL = 0.2, 0.3
FPS = 30


def clip_seconds(wav: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                         check=True, capture_output=True, text=True).stdout
    return float(out.strip())


def frames(t: float) -> float:
    """Round up to a whole frame."""
    return math.ceil(t * FPS - 1e-6) / FPS


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def find(words, phrase, nth=0, edge="s") -> float:
    want = [norm(w) for w in phrase.split()]
    seen = 0
    for i in range(len(words) - len(want) + 1):
        if all(norm(words[i + k]["w"]) == want[k] for k in range(len(want))):
            if seen == nth:
                return LEAD + (words[i + len(want) - 1]["e"] if edge == "e" else words[i]["s"])
            seen += 1
    raise KeyError(phrase)


def caption_chunks(words: list[dict], max_chars=76) -> list[list[dict]]:
    """Group words into captions of at most two lines. Break at sentence ends first, then at commas."""
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.?!]$", w["w"]):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)

    def text(ws):
        return " ".join(w["w"] for w in ws)

    def split(ws):
        if len(text(ws)) <= max_chars:
            return [ws]
        mid = len(text(ws)) / 2
        best, best_cost = None, 1e9
        pos = 0
        for i, w in enumerate(ws[:-1]):
            pos += len(w["w"]) + 1
            if i < 1 or i > len(ws) - 3:
                continue
            cost = abs(pos - mid) - (14 if re.search(r"[,:;]$", w["w"]) else 0)
            if cost < best_cost:
                best, best_cost = i + 1, cost
        return split(ws[:best]) + split(ws[best:])

    chunks = []
    for s in sentences:
        chunks.extend(split(s))
    # join very short neighbours inside the limit ("Nine." stays alone: it is a beat)
    return chunks


def two_lines(text: str, one_line=44) -> str:
    """Break a caption into two balanced lines, so the plate is as wide as the text."""
    if len(text) <= one_line:
        return esc(text)
    words = text.split()
    best, best_cost = 1, 1e9
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = abs(len(a) - len(b)) + (0 if re.search(r"[,:;]$", words[i - 1]) else 4)
        if cost < best_cost:
            best, best_cost = i, cost
    return esc(" ".join(words[:best])) + "<br />" + esc(" ".join(words[best:]))


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_tick(path: Path) -> None:
    """One soft tick: a short sine burst with a fast decay. Made here, so no sound file with a licence is needed."""
    sr = 48000
    n = int(sr * 0.09)
    data = bytearray()
    for i in range(n):
        t = i / sr
        env = math.exp(-t * 70) * min(1.0, t / 0.002)
        v = env * (0.55 * math.sin(2 * math.pi * 1250 * t) + 0.25 * math.sin(2 * math.pi * 2500 * t))
        data += struct.pack("<h", int(max(-1, min(1, v * 0.5)) * 32767))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(data))


def main() -> None:
    config = json.loads((VIDEO / "video.json").read_text(encoding="utf-8"))
    scenes = {}
    order = []
    t0 = 0.0
    all_caps = []
    for wav in sorted((VIDEO / "voice").glob("scene[0-9][0-9].wav")):
        n = int(wav.stem[-2:])
        sid = f"s{n:02d}"
        words = json.loads(wav.with_suffix(".words.json").read_text(encoding="utf-8"))["words"]
        clip = clip_seconds(wav)
        dur = frames(clip + LEAD + TAIL + float(config.get("pad", {}).get(sid, 0.0)))  # pad: a pause after the voice, per scene
        scenes[sid] = {"start": round(t0, 4), "dur": round(dur, 4), "clip": round(clip, 4),
                       "words": [[w["w"], w["s"], w["e"]] for w in words]}
        order.append(sid)
        chunks = caption_chunks(words)
        for i, ch in enumerate(chunks):
            start = max(0.05, LEAD + ch[0]["s"] - 0.08)
            end = (LEAD + chunks[i + 1][0]["s"] - 0.08) if i + 1 < len(chunks) else min(dur - 0.05, LEAD + ch[-1]["e"] + 0.45)
            end = min(end, LEAD + ch[-1]["e"] + 0.9)
            all_caps.append({"start": round(t0 + start, 3), "dur": round(end - start, 3), "text": " ".join(w["w"] for w in ch)})
        t0 += dur
    total = round(t0, 4)

    # cues that other files need (the scenes read them, the tick sounds use them)
    # cues.json: {"s01": {"bars": {"from": "phrase", "to": "phrase", "count": 4, "from_offset": 0, "to_offset": -0.25, "tick": true}}}
    # gives `count` times spread evenly from the first phrase to the second. Scenes read VID.timing.cues.s01.bars.
    cues: dict[str, dict[str, list[float]]] = {}
    ticks: list[float] = []
    cue_file = VIDEO / "cues.json"
    for sid, series in (json.loads(cue_file.read_text(encoding="utf-8")) if cue_file.exists() else {}).items():
        words = [{"w": w[0], "s": w[1], "e": w[2]} for w in scenes[sid]["words"]]
        for key, c in series.items():
            a = find(words, c["from"]) + c.get("from_offset", 0.0)
            b = find(words, c["to"]) + c.get("to_offset", 0.0)
            n = int(c["count"])
            times = [round(a + (b - a) * i / max(1, n - 1), 3) for i in range(n)]
            cues.setdefault(sid, {})[key] = times
            if c.get("tick"):
                ticks += [round(scenes[sid]["start"] + t, 3) for t in times]
    timing = {"lead": LEAD, "fps": FPS, "total": total, "order": order, "scenes": scenes, "cues": cues}
    (VIDEO / "assets/timing.js").write_text("window.VID_TIMING = " + json.dumps(timing, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                            encoding="utf-8")

    # captions
    rows = []
    for i, c in enumerate(all_caps):
        rows.append(f'    <div id="cap-{i:03d}" class="clip cap" data-start="{c["start"]}" data-duration="{c["dur"]}" '
                    f'data-track-index="1"><span>{two_lines(c["text"])}</span></div>')
    captions = f"""<template>
  <style>
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    #root .cap {{
      position: absolute; left: 0; right: 0; bottom: 48px;
      display: flex; justify-content: center; align-items: flex-end;
    }}
    #root .cap span {{
      display: block; padding: 8px 24px 10px; border-radius: 24px;
      background: rgba(11, 11, 10, 0.55); color: #FFFFFF; text-transform: lowercase;
      font-family: "VID Inter", sans-serif; font-weight: 300; font-size: 34px; line-height: 1.3;
      text-align: center; white-space: nowrap;
    }}
  </style>
  <div id="root" data-composition-id="captions" data-width="1920" data-height="1080">
{chr(10).join(rows)}
  </div>
  <script>
    (function () {{
      const tl = gsap.timeline({{ paused: true }});
      tl.set({{}}, {{}}, {total});
      window.__timelines["captions"] = tl;
    }})();
  </script>
</template>
"""
    (VIDEO / "compositions/captions.html").write_text(captions, encoding="utf-8")

    # the same captions as a sidecar file for players
    def stamp(t: float) -> str:
        ms = round(t * 1000)
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    srt = "".join(f"{i + 1}\n{stamp(c['start'])} --> {stamp(c['start'] + c['dur'])}\n"
                  + two_lines(c["text"]).replace("<br />", "\n") + "\n\n" for i, c in enumerate(all_caps))
    (VIDEO / "out").mkdir(exist_ok=True)
    (VIDEO / f"out/{config['name']}.srt").write_text(srt, encoding="utf-8")

    # tick sound and the root composition
    write_tick(VIDEO / "assets/sfx/tick.wav")
    hosts, audio = [], []
    for i, sid in enumerate(order):
        s = scenes[sid]
        hosts.append(f'      <div id="{sid}" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" '
                     f'data-start="{s["start"]}" data-duration="{s["dur"]}" data-track-index="{1 + i % 2}" data-track-kind="graphics" '
                     f'data-width="1920" data-height="1080"></div>')
        audio.append(f'      <audio id="voice-{sid}" class="clip" src="voice/scene{sid[1:]}.wav" data-start="{round(s["start"] + LEAD, 4)}" '
                     f'data-duration="{s["clip"]}" data-track-index="10" data-volume="1"></audio>')
    for k, t in enumerate(ticks, 1):
        audio.append(f'      <audio id="tick-{k:02d}" class="clip" src="assets/sfx/tick.wav" data-start="{t}" '
                     f'data-duration="0.09" data-track-index="{11 + k % 2}" data-volume="0.5"></audio>')
    data_js = VIDEO / "assets/data/data.js"  # the scenes' data bundle; a stub when the video has none
    if not data_js.exists():
        data_js.parent.mkdir(parents=True, exist_ok=True)
        data_js.write_text("window.VIDEO_DATA = {};\n", encoding="utf-8")
    template = (VIDEO / "tools/index.template.html").read_text(encoding="utf-8")
    html = (template.replace("{{TITLE}}", esc(config["title"])).replace("{{TOTAL}}", str(total)).replace("{{HOSTS}}", "\n".join(hosts)).replace("{{AUDIO}}", "\n".join(audio)))
    (VIDEO / "index.html").write_text(html, encoding="utf-8")

    for sid in order:
        s = scenes[sid]
        print(f'{sid}: start {s["start"]:7.3f}  dur {s["dur"]:6.3f}  clip {s["clip"]:6.3f}')
    print(f"total {total} s, {len(all_caps)} captions, longest caption {max(len(c['text']) for c in all_caps)} chars, "
          f"shortest caption time {min(c['dur'] for c in all_caps)} s")


if __name__ == "__main__":
    main()
