#!/usr/bin/env bash
# Renders the deck (one slide per frame) to PNGs in out/deck/ and joins them into out/egg-shell-pitch-deck.pdf.
# Copy the results to ../docs/deck/ and ../docs/egg-shell-pitch-deck.pdf. Needs img2pdf.
# The temp folder name has no dot: Remotion reads a dot in the output path as a file extension.
set -euo pipefail
cd "$(dirname "$0")/../.."
TMP=$(mktemp -d /tmp/deckXXXXXX)
npx remotion render src/deck/index.ts Deck "$TMP" --sequence --image-format=png --log=error
rm -rf out/deck && mkdir -p out/deck
i=1; for f in "$TMP"/element-*.png; do cp "$f" "out/deck/slide-$(printf %02d $i).png"; i=$((i+1)); done
img2pdf --pagesize 1440ptx810pt out/deck/slide-*.png -o out/egg-shell-pitch-deck.pdf
echo out/egg-shell-pitch-deck.pdf
