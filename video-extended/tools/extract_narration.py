# /// script
# requires-python = ">=3.11"
# ///
"""Read the narration of each scene from SCRIPT.md and write voice/sceneNN.txt.

Run from the video project:  uv run tools/extract_narration.py
SCRIPT.md is the source of truth. Do not edit the .txt files by hand.
"""
import json
import re
from pathlib import Path

VIDEO = Path(__file__).resolve().parent.parent
text = (VIDEO / "SCRIPT.md").read_text(encoding="utf-8")
scenes = re.split(r"^### (\d+)\. (.+?) \(about (\d+) s\)\s*$", text, flags=re.M)
out = []
(VIDEO / "voice").mkdir(exist_ok=True)
for i in range(1, len(scenes), 4):
    num, title, about, body = int(scenes[i]), scenes[i + 1], int(scenes[i + 2]), scenes[i + 3]
    m = re.search(r"Narration:\n((?:> .*\n?)+)", body)
    narration = " ".join(line[2:].strip() for line in m.group(1).strip().splitlines())
    (VIDEO / "voice" / f"scene{num:02d}.txt").write_text(narration + "\n", encoding="utf-8")
    out.append({"scene": num, "title": title, "about_s": about, "words": len(narration.split()), "text": narration})
(VIDEO / "voice" / "narration.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
for s in out:
    print(f'{s["scene"]:2d} {s["words"]:3d} words  about {s["about_s"]} s  expected at 150 wpm {s["words"] / 2.5:.1f} s  {s["title"]}')
print("total words", sum(s["words"] for s in out))
