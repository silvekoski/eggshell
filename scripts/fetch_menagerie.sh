#!/usr/bin/env bash
# Fetch the robot models we use from MuJoCo Menagerie (Apache-2.0) into
# third_party/ (git-ignored). Sparse and shallow: a few MB.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
dest="$here/third_party/mujoco_menagerie"
if [ ! -d "$dest/.git" ]; then
  mkdir -p "$here/third_party"
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/google-deepmind/mujoco_menagerie.git "$dest"
fi
git -C "$dest" sparse-checkout set shadow_hand
echo "menagerie ready: $dest/shadow_hand"
