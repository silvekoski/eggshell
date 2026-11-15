# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["mlx-whisper; sys_platform == 'darwin'", "faster-whisper; sys_platform != 'darwin'"]
# ///
"""Word timings for each voice clip, with a pronunciation check.

Run from the video project:  uv run tools/align_words.py [wav ...]
Without arguments it reads voice/sceneNN.wav and writes voice/sceneNN.words.json.

A local Whisper model (MLX, on this Mac) transcribes each clip with word timestamps.
The script then maps the heard words to the script words (voice/sceneNN.txt), so each
script word gets a start and an end. Script words that the model did not hear get
interpolated times and are listed as a warning: check those by ear.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

if sys.platform == "darwin":
    import mlx_whisper
else:
    from faster_whisper import WhisperModel

VIDEO = Path(__file__).resolve().parent.parent
MODEL = "mlx-community/whisper-small.en-mlx"

NUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
       "eight": "8", "nine": "9", "ten": "10", "twenty": "20", "thirty": "30", "hundred": "100"}


def norm(w: str) -> str:
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    return NUM.get(w, w)


_FASTER = None


def transcribe(wav: Path) -> list[dict]:
    """Heard words with times. MLX Whisper on a Mac, faster-whisper (CPU) elsewhere."""
    global _FASTER
    if sys.platform == "darwin":
        res = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MODEL, word_timestamps=True, language="en",
                                     condition_on_previous_text=False, initial_prompt=None)
        return [{"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
                for seg in res["segments"] for w in seg.get("words", []) if w["word"].strip()]
    if _FASTER is None:
        _FASTER = WhisperModel("small.en", device="cpu", compute_type="int8")
    import subprocess
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    segments, _ = _FASTER.transcribe(audio, word_timestamps=True, language="en", condition_on_previous_text=False)
    return [{"w": w.word.strip(), "s": float(w.start), "e": float(w.end)}
            for seg in segments for w in (seg.words or []) if w.word.strip()]


def align(wav: Path, text: str) -> dict:
    heard = transcribe(wav)
    script = text.split()
    a = [norm(w) for w in script]
    b = [norm(h["w"]) for h in heard]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times: list[list[float] | None] = [None] * len(script)
    missed = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = [heard[j1 + k]["s"], heard[j1 + k]["e"]]
        elif tag == "replace" and j2 > j1:
            # same span, other spelling ("twenty-seven" against "27"): spread the heard span over the script words
            s, e = heard[j1]["s"], heard[j2 - 1]["e"]
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = [s + (e - s) * k / n, s + (e - s) * (k + 1) / n]
            missed.append({"script": " ".join(script[i1:i2]), "heard": " ".join(h["w"] for h in heard[j1:j2])})
        elif tag == "delete":
            missed.append({"script": " ".join(script[i1:i2]), "heard": ""})
        elif tag == "insert":
            missed.append({"script": "", "heard": " ".join(h["w"] for h in heard[j1:j2])})
    # interpolate script words with no time
    known = [(i, t) for i, t in enumerate(times) if t]
    for i, t in enumerate(times):
        if t is None:
            prev = max((k for k in known if k[0] < i), default=None, key=lambda k: k[0])
            nxt = min((k for k in known if k[0] > i), default=None, key=lambda k: k[0])
            s = prev[1][1] if prev else 0.0
            e = nxt[1][0] if nxt else s + 0.3
            times[i] = [s, e]
    words = [{"w": w, "s": round(t[0], 3), "e": round(t[1], 3)} for w, t in zip(script, times)]
    return {"wav": wav.name, "ratio": round(sm.ratio(), 4), "mismatch": missed, "words": words,
            "heard": " ".join(h["w"] for h in heard)}


def main() -> None:
    args = [Path(a) for a in sys.argv[1:]]
    if not args:
        args = sorted((VIDEO / "voice").glob("scene[0-9][0-9].wav"))
    for wav in args:
        txt = wav.with_suffix(".txt")
        if not txt.exists():
            m = re.search(r"s(?:cene)?(\d\d)", wav.name)
            txt = VIDEO / "voice" / f"scene{m.group(1)}.txt"
        out = align(wav, txt.read_text(encoding="utf-8").strip())
        wav.with_suffix(".words.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f'{wav.name}: match {out["ratio"]:.3f}, {len(out["mismatch"])} mismatch spans')
        for m in out["mismatch"]:
            print("   script:", repr(m["script"]), "| heard:", repr(m["heard"]))


if __name__ == "__main__":
    main()
