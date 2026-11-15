#!/bin/sh
# Master the HyperFrames render: loudness, codecs, size, and the poster.
# Run from the video project:  sh tools/master.sh <raw render.mp4>
# Writes out/<name>.mp4, out/poster.png and out/measure.txt. <name> and the poster time come from video.json.
#
# Audio: two-pass EBU R128 loudness normalisation to -14 LUFS integrated, true peak limit -1.5 dBTP
#        (the AAC encoder adds a few tenths of a dB, so the file stays below -1 dBTP).
# Video: H.264 high profile, yuv420p, 1920x1080, 30 fps, +faststart.
set -eu
RAW="${1:?give the raw render}"
CRF="${CRF:-18}"
cd "$(dirname "$0")/.."
NAME=$(sed -n 's/.*"name" *: *"\([^"]*\)".*/\1/p' video.json)
POSTER_AT="${POSTER_AT:-$(sed -n 's/.*"poster_at" *: *\([0-9.]*\).*/\1/p' video.json)}"
[ -n "$NAME" ] && [ -n "$POSTER_AT" ] || { echo "video.json needs name and poster_at" >&2; exit 1; }
mkdir -p out
OUT="out/$NAME.mp4"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# pass 1: measure
ffmpeg -hide_banner -nostdin -i "$RAW" -vn -af "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json" -f null - 2> "$TMP/pass1.txt"
val() { sed -n "s/.*\"$1\" *: *\"\\(.*\\)\".*/\\1/p" "$TMP/pass1.txt" | tail -n 1; }
I=$(val input_i); TP=$(val input_tp); LRA=$(val input_lra); TH=$(val input_thresh); OFF=$(val target_offset)
[ -n "$I" ] && [ -n "$TP" ] && [ -n "$LRA" ] && [ -n "$TH" ] && [ -n "$OFF" ] || { echo "loudness pass 1 gave no values" >&2; exit 1; }

# pass 2: normalise and encode
ffmpeg -hide_banner -nostdin -y -i "$RAW" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$I:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$TH:offset=$OFF:print_format=summary,aresample=48000" \
  -c:v libx264 -preset slow -crf "$CRF" -profile:v high -pix_fmt yuv420p -r 30 -s 1920x1080 \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -c:a aac -b:a 160k -ar 48000 -ac 2 \
  -movflags +faststart "$OUT" 2> "$TMP/pass2.txt"

# poster: the frame at poster_at
ffmpeg -hide_banner -nostdin -y -ss "$POSTER_AT" -i "$OUT" -frames:v 1 -update 1 out/poster.png 2> /dev/null

# measure the result
{
  echo "input loudness: I=$I LUFS, TP=$TP dBTP, LRA=$LRA LU"
  ffprobe -v error -show_entries format=duration,size,bit_rate:stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,sample_rate,channels,bit_rate -of default=nw=1 "$OUT"
  ffprobe -v error -show_entries format_tags=major_brand -of default=nw=1 "$OUT"
  ffmpeg -hide_banner -nostdin -i "$OUT" -vn -af ebur128=peak=true -f null - 2>&1 | tail -n 14
} > out/measure.txt
cat out/measure.txt
