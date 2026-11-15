#!/bin/sh
# Stills for the check loop: 3 per scene (10%, 50% and 95% of the scene), from the composition, without a render.
# Run from the video project:  sh tools/stills.sh            (writes out/stills/)
# After the master:            sh tools/stills.sh final      (one frame each 6 s of the final MP4, in out/review/)
set -eu
cd "$(dirname "$0")/.."
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1
if [ "${1:-}" = "final" ]; then
  NAME=$(sed -n 's/.*"name" *: *"\([^"]*\)".*/\1/p' video.json)
  rm -rf out/review && mkdir -p out/review
  ffmpeg -hide_banner -nostdin -loglevel error -i "out/$NAME.mp4" -vf "fps=1/6,scale=960:-1" out/review/f%03d.jpg
  ls out/review | wc -l
  exit 0
fi
AT=$(node -e '
  global.window = {}; require("./assets/timing.js");
  const t = window.VID_TIMING, out = [];
  for (const id of t.order) { const s = t.scenes[id]; for (const p of [0.1, 0.5, 0.95]) out.push((s.start + s.dur * p).toFixed(2)); }
  console.log(out.join(","));')
rm -rf out/stills
npx hyperframes snapshot --at "$AT" --no-end -o out/stills
