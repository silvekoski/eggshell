# Egg Shell pitch video (Remotion) and deck: script and sources

- Video: `npm run render` -> `out/video.mp4` (115.6 s, 1920x1080). Deck: `bash src/deck/build.sh` -> `out/deck/*.png` and
  `out/egg-shell-pitch-deck.pdf`, copied to `../docs/deck/` and `../docs/egg-shell-pitch-deck.pdf`. Render both on a Verda CPU VM.
- Voice: ElevenLabs, voice id `Hm0mJlZY3Pws7nTKAftG` (video.config.json). Music: ElevenLabs Music bed, volume 0.1.
- Look: measured from teenage.engineering (`npm run theme`), then hand-edited in `src/site-theme.json` toward the TX-6 page.
  Shared parts (fader, dotted meter, LEDs, pill, knobs, sim screen) are in `src/te.tsx`; the scenes are in `src/scenes/egg.tsx`.
- Footage: `public/rec/{egg,crush,drop,miss}.mp4` (git-ignored; copy from `../out/footage-light/`). Per-frame force/lift for
  the faders: `src/clips/*.json` (the sidecars). Deck stills: `public/stills/` (frames of the same clips).
- Honesty: all glove input is simulated (scripted operator). Said in s02; "glove input: simulated" is on every scene and slide.

## Narration

- **s01** Robots learn to grasp from human demonstrations. But through a teleoperation glove, you feel nothing. So demos end as drops and crushes, and someone sorts them by hand.
- **s02** Egg Shell gives the robot the sense you lack. A glove stream drives a twenty-actuator Shadow hand in MuJoCo, holding an egg that can crack. One honest note: we had no Rokoko gloves, so all glove input here is simulated, by a scripted operator.
- **s03** A careful lift: eleven centimetres, three point eight newtons. The egg survives. Squeeze too hard: nineteen point six newtons, past the eight newton crack threshold, and the egg turns red.
- **s04** Every try becomes a labelled episode, with the grip force of every frame: lifted, crushed, or not lifted.
- **s05** But thresholds miss things. This egg rose eleven centimetres, then the hand opened, and the simulator still says lifted. NVIDIA Nemotron reviews each episode from four keyframes and the force log. It says dropped, and flags it for a human.
- **s06** Labels make the data trainable. We trained a policy on four hundred eighty demos, then added the lifted task vector to its weights, with no new training. Lifts rose from twenty-seven to sixty-seven percent. Subtracting the crushed vector failed: it broke the reach.
- **s07** Fifty-seven tests pass. Our wire client is rebuilt from Rokoko's bridge code, and replay gives the same label four times out of four.
- **s08** Next: real gloves at the venue, the Inspire hand, whose commands we already compute, and many more demonstrations.
- **s09** Egg Shell. The robot feels what you can't.

## Numbers and their sources (all paths in `rokoko-teleop/`)

| Number | Source |
|---|---|
| RGMP v2, TCP 12277, 26 OpenXR joints; client rebuilt from rokoko-ros2-bridge; angles back within 1e-4 rad | docs/SUBMISSION.md |
| Shadow hand, 20 actuators, MuJoCo | docs/SUBMISSION.md |
| Careful: 11.0 cm, 3.76 N, lifted (voice rounds to "three point eight") | docs/SUBMISSION.md, docs/demo-run/review.md |
| Squeeze: 19.63 N, crushed; crack threshold 8 N, a simulation proxy | docs/SUBMISSION.md |
| Drop: 10.9 cm, simulator says lifted (voice rounds to "eleven") | docs/SUBMISSION.md |
| Miss: 0.0 cm, 2.23 N, not lifted | docs/SUBMISSION.md |
| Nemotron 3.5 Super VL, 4 keyframes + 24-row force/lift log; drop -> dropped, 0.98, flagged; 3 of 4 agree; quote | docs/demo-run/review.md, docs/SUBMISSION.md |
| Review table in the terminal (reformatted from the markdown table) | docs/demo-run/review.md |
| 57 tests pass; replay same label 4 of 4 | docs/SUBMISSION.md |
| 480 demos, egg ±15 mm, 5 seeds x 20 unseen positions = 100 rollouts | docs/weightspace/README.md (v2) |
| θ₀ 27 % lifted / 62 % crushed; +τ lifted 67 / 28; +τ crushed 13 / 83; −τ crushed 3 / 57 | docs/weightspace/results_v2.md |
| Inspire commands 0..1000 per finger, computed, not sent | docs/SUBMISSION.md |
| Live fader and meter values during clips | out/footage-light/*.json (per-frame sim data of the rendered clip) |

