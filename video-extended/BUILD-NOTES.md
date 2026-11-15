# Build notes: Egg Shell (extended cut, technical walkthrough)

A cut of about 4:37 for judges. It holds all nine scenes of the 2:00 pitch cut (`../video/`) with the same
voice clips, plus six technical scenes: 3 the wire path, 4 retargeting, 8 inside an episode, 10 how the review
works, 12 verified and not yet, 13 programming a policy in weight space. `SCRIPT.md` has every scene and the table of numbers.

## Result

| Item | Value |
|---|---|
| File | `out/egg-shell-extended.mp4` |
| Length | 277.1 s (4:37.1) |
| Picture | H.264 High, yuv420p, 1920x1080, 30 fps |
| Sound | AAC-LC, 48 kHz, stereo, -14 LUFS |
| Size | 18,714,916 bytes (18.7 MB) |
| Poster | `out/poster.png`, scene 6 at 94.1 s (side by side: "3.76 N Lifted" and "19.63 N Crushed") |
| Captions | burned in, and `out/egg-shell-extended.srt` |
| Measurements | `out/measure.txt` |

## How it was made

- The project is a copy of `../video/`. Scenes and voice files were renumbered (pitch 3 -> 5, 4 -> 6, 5 -> 7,
  6 -> 9, 7 -> 11, 8 -> 13, 9 -> 14); the shared narration is identical (checked with `cmp` on the voice texts).
- Only the five new scenes were voiced: `SPEED=0.9 sh tools/make_voice.sh 3 4 8 10 12`, then
  `uv run tools/align_words.py voice/scene03.wav ...`. Then build, lint, stills, render and master as in
  `../video/BUILD-NOTES.md`.
- `tools/prepare_data.py` also writes the glove skeleton, the human angles and the actions of episode 0, the
  array shapes of `episode_0000.npz`, and a 24-row force/lift timeline of episode 2.
- `video.json`: name `egg-shell-extended`, 1.5 s pause after the voice of scene 14.
- Version 3 (15 Nov): the light editorial look with side-by-side comparisons (see `../video/BUILD-NOTES.md`,
  "Look (version 3)"). The nine pitch scenes were copied again from `../video/`, with `assets/lib.js`,
  `assets/base.css`, `tools/build.py` (white caption pill) and `tools/index.template.html` (light background).
  The five technical scenes were moved to the same palette (black on light grey, no green or amber, red only for
  errors), got the header row and 120 px margins. The footage is not committed here: `tools/prepare_data.py`
  copies it from `../video/assets/footage/` into `assets/footage/` (git-ignored).

- Scene 13 (15 Nov): "Programming a policy in weight space", before the next steps. Voiced alone with
  `SPEED=0.9 sh tools/make_voice.sh 13` (36.96 s); the next-steps and closing scenes were renumbered to 14 and 15
  (voice files and compositions renamed, pad now on s15). Numbers from `docs/weightspace/results_v2.json` and the v2
  section of `docs/weightspace/README.md`. Greek letters (θ, τ) need the Greek subsets of Inter and JetBrains Mono,
  added to `assets/fonts/` and `assets/base.css`. `dial.svg` is not used: the dials are drawn in the scene.

- Version 4 (15 Nov): the teenage engineering look of the pitch cut (see `../video/BUILD-NOTES.md`); the
  technical scenes moved to white on grey and black panels; in scene 13, a and c are outline knobs that turn with
  the voice and the key result is the red pill. Rendered on the Verda CPU VM `nixos-cpu-27f4` (deleted after use).
  The optional weight-space footage (`scripts/render_policy.py`) was not rendered.

## Honesty

The same rule as the pitch cut: the spoken disclosure in scene 2 and the header label "GLOVE INPUT: SIMULATED"
on every scene. Scene 3 shows `rkk-hand-solver` as "Rokoko SDK, not here" and
`teleop fake-solver` as "scripted operator, used here". The skeleton in scene 4 is labelled "episode 0 (scripted
operator)".

## Data on screen (new scenes)

- Scene 3: RGMP v2 layout from the README "Architecture" section.
- Scene 4: `glove` (joint positions relative to the wrist, oblique view), `human_angles`, `action` and `inspire`
  of `episode_0000.npz` at 15 Hz, stretched over the scene. Bar heights are scaled for display; no axis numbers.
- Scene 8: the real keys and shapes of `episode_0000.npz`, and the fields of episode 0 in `episodes.jsonl`.
- Scene 10: keyframes of episode 0; 24 rows sampled evenly from the episode 2 log (display only, the review builds
  its own 24 rows); the JSON is the real answer for episode 2 from `reviews.jsonl`, shortened (`...`); the token
  budget change 1200 -> 4096 from the git history of `src/rokoko_teleop/nemotron.py` (commit ea325a0e) and the README.
- Scene 12: the README section "What is verified, and what needs hardware".

## Checks done

- `npx hyperframes lint`: 0 errors, 1 warning (caption density, by design).
- Stills of every scene, and frames of the final MP4 every 6 s (`out/review/`), looked at.
  Fixed: a nearly empty first 3 s in scene 3, a wrapped label in scenes 3 and 4, the wrist panel that came in
  0.9 s before the end of scene 4.

## Known defects

- Nobody has heard the voice or watched the motion. Watch it once.
- The length is at the top of the asked range (about 4:00).
- Scene 4 plays the 17 s glove recording over 25 s (slower than real time); the skeleton is a schematic view.
- Scene 10 shows the keyframes that Nemotron really saw: the old 640x480 renders with the default MuJoCo look,
  so they do not match the studio footage of the other scenes.
- The technical scenes (3, 4, 8, 10, 12) are still diagrams with many text elements, not footage.
