# Build notes: Egg Shell (pitch cut, at most 2:00)

The video is built from `SCRIPT.md` with the `explainer-video` skill. The extended cut for judges (about 4 minutes)
is in `../video-extended/` and reuses these voice clips and scenes.

Version 4 (15 Nov): a teenage engineering look (the TX-6 product page as reference). Same narration and voice
clips, so the timing did not change. Rendered on a Verda CPU VM (`nixos-cpu-27f4`, CPU.8V.32G, deleted after use),
not on the shared machine.

## Result

| Item | Value |
|---|---|
| File | `out/egg-shell.mp4` |
| Length | 117.7 s (1:57.7), 2.3 s under the 2:00 limit |
| Picture | H.264 High, yuv420p, 1920x1080, 30 fps |
| Sound | AAC-LC, 48 kHz, stereo, -14 LUFS integrated |
| Size | 11,085,298 bytes (11.1 MB) |
| Poster | `out/poster.png`, scene 4 at 47.2 s (two panels: "3.76 N lifted", "19.63 N crushed") |
| Captions | burned in, and the same text as `out/egg-shell.srt` |
| Measurements | `out/measure.txt` |

## Honesty

No Rokoko gloves or SDK licence were available. All glove input is simulated: a scripted operator generates the
OpenXR hand frames. Scene 2 says so ("The glove input here is simulated: a scripted operator") and shows the real
glove as a grey card "Real glove, Rokoko Smartglove, not available here" next to "Scripted operator, used here".
Every scene has the header row "EGG SHELL / ROBOT TELEOPERATION · ROKOKO × JUNCTION 2026 · GLOVE INPUT: SIMULATED".
The end card says "All footage: MuJoCo simulation, glove input from a scripted operator".

## Build it again

```sh
cd rokoko-teleop/video
sh tools/setup.sh                                       # packages, fonts, GSAP
export PATH=<ffmpeg-full>/bin:<bc>/bin:$PATH HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1
C=$(readlink -f $(which chromium)); export PUPPETEER_EXECUTABLE_PATH=$C PRODUCER_HEADLESS_SHELL_PATH=$C   # NixOS
uv run tools/prepare_data.py                            # stills, keyframes, data.js (incl. the footage sidecars)
SPEED=0.9 sh tools/make_voice.sh                        # Kokoro af_heart, speed 0.9 (only if the narration changes)
uv run tools/align_words.py && uv run tools/build.py
npx hyperframes lint && sh tools/stills.sh
npx hyperframes render -o /tmp/egg-shell-raw.mp4 -q looks -f 30
sh tools/master.sh /tmp/egg-shell-raw.mp4 && sh tools/stills.sh final
```

ffmpeg is not on PATH on this machine: `/nix/store/mdd1yg7sjnvl28r1caw1mqxw07lgvajg-ffmpeg-full-8.1.3-bin/bin`.
`bc` (for `make_voice.sh`) comes from `nix shell nixpkgs#bc`.

## Look (version 4, teenage engineering)

- Flat mid-grey page (#767676), all type white, Inter 200/300, lowercase. A huge thin wordmark "egg shell" on the
  hook, the title and the closing, overlapped by a black rounded hardware panel (#0B0B0A, radius 28, no shadow).
- The data is the hardware: grip force is a vertical fader (the cap follows the sidecar force, a tick at 8 N, the
  slot fills red once the egg cracked); lift is a dotted level meter; episode labels are LEDs (white ring = lifted,
  red = crushed, grey = not lifted); the Inspire hand is a row of 6 faders; the Nemotron verdict is the red pill
  "dropped · 0.98". One row of orange knobs is the only decoration. Footage sits in the panels as rounded screens.
- Header row on every scene: "egg shell — robot teleoperation · rokoko × junction 2026 · glove input: simulated".
- Side-by-side comparisons: two panels (careful vs squeeze; lifted vs dropped), each with a screen, a fader and a
  dotted meter. Captions: white lowercase on a faint dark plate.
- Remote build: push the project with `pnpm j gpu push` (it skips `data/` folders, so `assets/data/` went up as a
  tarball), install node 24, ffmpeg and the Chrome libraries on the VM, `npx hyperframes browser ensure`, then
  render, master and `stills.sh final` there, and pull `out/` back.

## Footage

- `assets/footage/{egg,crush,drop,miss}.mp4` (committed, 7.2 MB): the light studio renders from
  `out/footage-light/` (`scripts/render_footage.py`, rendered at 4K and downsampled), re-encoded here with
  x264 CRF 20 and a keyframe every 30 frames to keep the repository small. Each is re-simulated from the
  recorded actuator and wrist targets of the saved episode; the replayed labels match the stored labels.
- `assets/footage/<clip>.json`: per frame `force_n`, `lift_cm`, `cracked`, copied into `data.js` by
  `tools/prepare_data.py`. `VID.syncFootage` drives the gauges from the clip clock.
- The live gauges follow the replayed sidecar, so the force bar has no number on it (replayed peaks differ from
  the stored ones, for example 3.48 N against 3.76 N for the egg). Every number in text is a stored value from
  the table in `SCRIPT.md`. The crush gauge has no lift readout.

## Voice

- Kokoro-82M, voice `af_heart`, speed **0.9** (not 0.82): 274 words had to fit in 2:00. A scene is its clip plus 0.5 s.
- `video.json` adds a 2.0 s pause after the voice of scene 9 (`pad`, a new option of `tools/build.py`, also in
  the skill template).
- `tools/pronounce.tsv` respells RGMP and MuJoCo for the voice only.
- Whisper heard every number right. Other differences: "Rokoko" heard as "rococo", "Nemotron" as "Nemetron".

## Departures from the script

The narration is unchanged (scene 7 gained the wire-path beat in version 1). The pictures follow the version 3
design brief, not the `Picture:` lines: see "Look (version 3)" above. Scene 6 drops the force/lift chart; the
moment the grip let go is a note on the drop panel ("t = 6.25 s · force 0.0 N · egg 3.4 cm up") while the
release replays.

## Checks done

- `npx hyperframes lint`: 0 errors, 1 warning (caption track density, by design).
- Stills of each scene and extra stills at layout changes, looked at for overlaps, empty halves and contrast.
  Fixed in version 3: the 8 N note crowding the crush numbers (now the label of the squeeze gauge), a tag over the
  behaviour-cloning thumbnails, the blue verdict block running into the caption.
- Frames of the final MP4 every 6 s (`out/review/`), looked at, and `out/measure.txt`.

## Known defects

- Nobody has heard the voice. Watch it once before you submit.
- Scene 2 shows only the real-glove card for its first 10 s; the scripted-operator card comes with the voice.
- In scene 4 the careful clip starts again from before contact (the pair replays in sync), so the left panel
  jumps back at the cut from scene 3.
- The squeeze clip ends 6 s into scene 4 and holds its last frame; the drop clip holds its last frame between
  8.9 s and the replay of the release at 16.4 s in scene 6.
- The footage is light grey (about #AEAEAE at the top to #D0D0D0); the slide background is lighter, so footage
  panels read as cards rather than blending into the page.
