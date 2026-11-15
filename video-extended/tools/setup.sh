#!/bin/sh
# One-time setup of a new video project: packages, fonts, GSAP, and the .gitignore.
# Run from the video project:  sh tools/setup.sh
set -eu
cd "$(dirname "$0")/.."
export HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1
[ -f gitignore ] && mv gitignore .gitignore
npm install --no-fund --no-audit
mkdir -p assets/fonts assets/vendor assets/data voice out
for f in inter-latin-400-normal inter-latin-600-normal inter-latin-ext-400-normal inter-latin-ext-600-normal; do
  cp "node_modules/@fontsource/inter/files/$f.woff2" assets/fonts/
done
for f in jetbrains-mono-latin-400-normal jetbrains-mono-latin-600-normal; do
  cp "node_modules/@fontsource/jetbrains-mono/files/$f.woff2" assets/fonts/
done
cp node_modules/@fontsource/inter/LICENSE assets/fonts/LICENSE-Inter.txt
cp node_modules/@fontsource/jetbrains-mono/LICENSE assets/fonts/LICENSE-JetBrainsMono.txt
cp node_modules/gsap/dist/gsap.min.js assets/vendor/gsap.min.js
for tool in uv ffmpeg ffprobe node; do command -v "$tool" > /dev/null || echo "missing tool: $tool" >&2; done
echo "ready. Next: write SCRIPT.md, then sh tools/make_voice.sh"
