#!/bin/sh
# Voice clips, one per scene, with Kokoro-82M on this machine (through the HyperFrames tts command).
# Run from the video project:  sh tools/make_voice.sh
# Needs: uv, node. First run downloads the Kokoro model (about 340 MB) to ~/.cache/hyperframes.
set -eu
VOICE="${VOICE:-af_heart}"
SPEED="${SPEED:-0.82}"
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1
cd "$(dirname "$0")/.."
uv run -q tools/extract_narration.py
# Arguments: scene numbers to voice again (for example: 4 9 11). Without arguments: every scene.
# tools/pronounce.tsv (optional): "written<TAB>spoken" per line. It changes only what the voice reads;
# the captions keep the written form.
if [ "$#" -gt 0 ]; then set -- $(for n in "$@"; do printf 'voice/scene%02d.txt ' "$n"; done); else set -- voice/scene[0-9][0-9].txt; fi
for txt in "$@"; do
  wav="${txt%.txt}.wav"
  say="${txt%.txt}.say.txt"  # tts reads a file only when it ends in .txt
  cp "$txt" "$say"
  if [ -f tools/pronounce.tsv ]; then
    while IFS="$(printf '\t')" read -r written spoken; do
      [ -n "$written" ] && sed -i.bak "s/$written/$spoken/g" "$say" && rm -f "$say.bak"
    done < tools/pronounce.tsv
  fi
  uv run -q --python 3.12 --with kokoro-onnx --with soundfile -- \
    npx hyperframes tts "$say" -o "$wav" -v "$VOICE" -s "$SPEED" --json > "${txt%.txt}.tts.json"
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$wav")
  words=$(wc -w < "$txt" | tr -d ' ')
  echo "$wav  $dur s  $words words  expected at 150 wpm: $(echo "scale=1; $words / 2.5" | bc) s"
done
