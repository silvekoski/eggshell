# Explainer video: script and storyboard

Title: **Egg Shell - technical walkthrough** (the extended cut)

Length: about 3:30 to 4:00, for judges. It holds every scene of the 2:00 pitch cut in `../video/`, with the same
voice clips, plus five technical scenes (3, 4, 8, 10, 12). 1920x1080, 30 fps. English narration, one voice clip per scene.
The narration is the source of truth. A scene is as long as its voice clip plus 0.5 s.

Every number on screen or in the narration is in the table "Numbers and their sources" at the end.
Do not add a number that is not in that table.

**Honesty rule.** No Rokoko gloves or SDK licence were available. All glove input in this video is simulated:
a scripted operator generates OpenXR hand frames that go through the same pipeline as real glove data would
(retargeting, MuJoCo Shadow hand, egg physics, labelled episode). Scene 2 says this plainly. Every scene that
shows simulation footage or data from it carries the chip "glove input: simulated" at the top right.
Never imply that a person wore a glove.

## Style

- Look: dark background `#0E1116` with a faint grid. Simulation footage lies on a paper card `#F4F1EA`.
- One meaning per colour:
  - blue `#4C9BE8`: the input (the glove stream, the operator)
  - amber `#F0A63A`: evidence (grip force, the log, the keyframes the model saw)
  - green `#3FBF8F`: a good outcome or a passed check (lifted, tests pass)
  - red `#E5604D`: a failure or a flag (crushed, dropped, "flagged for a human")
  - grey `#8A93A3`: context. A dashed grey border means "simulated" or "not here yet".
- Fonts: Inter for text, JetBrains Mono for numbers, units, file and tool names. Title 72 px, body 40 px,
  labels 28 px minimum. At most 7 words per line on screen.
- Motion: entrances ease-out 0.4 to 0.6 s, moves ease-in-out 0.8 to 1.2 s. One main motion at a time.
- Captions: burned in at the bottom, at most 2 lines. Sound: voice, one soft tick per labelled episode. No music.

## Real material

| Key | File in `rokoko-teleop/` | What it is |
|---|---|---|
| EGG | `out/demo-egg.mp4` (640x480, 17.2 s) | careful lift: approach, grasp, lift, set down. HUD: force bar bottom left (red = cracked, white tick = crack threshold), lift bar right |
| CRUSH | `out/demo-crush.mp4` (6.4 s) | squeeze, the egg turns red |
| DROP | `out/demo-drop.mp4` (8.0 s) | lift, then the hand opens in the air and the egg falls |
| MISS | `out/demo-miss.mp4` (6.0 s) | grasp 5 cm too high, the egg stays on the table |
| KEY | `datasets/demo/episode_000N_{contact,peak_force,max_lift,final}.png` | keyframes saved with each episode (episode 2 has no peak_force, episode 3 only contact and final) |
| LOG | `datasets/demo/episode_000N.npz` | per-frame time, egg pose, egg contact force, Inspire commands |
| REVIEW | `docs/demo-run/reviews.jsonl`, `review.md` | Nemotron 3.5 Super VL output |
| LABELS | `docs/demo-run/episodes.jsonl` | simulator labels |

All footage is MuJoCo simulation, rendered headless by `teleop demo`, with a scripted operator as the glove source.
Credit line: Shadow Dexterous Hand model from MuJoCo Menagerie (Apache-2.0).

## Scenes

### 1. Hook (about 12 s)

Narration:
> Robots learn to grasp from human demonstrations. But through a teleoperation glove, you feel nothing. So many
> demos end as drops and crushes, and someone sorts them by hand.

Picture: three keyframes from real episodes land as a row of "demos" on paper cards (EGG at max lift, DROP while
the egg falls, CRUSH with the red egg). At "you feel nothing" a red chip "no touch feedback". At "drops and
crushes" red tags "dropped" and "crushed" land on two cards, a green "good" on the first. At "sorts them by hand"
a grey chip "sorted by hand". Chip "glove input: simulated" top right.

### 2. What it is (about 14 s)

Narration:
> Egg Shell: a Rokoko glove stream drives a Shadow robot hand in MuJoCo, with an egg that can crack. The glove
> input here is simulated: a scripted operator, through the same pipeline as real glove data.

Picture: title "Egg Shell" types on. A pipeline draws left to right: glove source -> "26 OpenXR joints" ->
"retargeting, 20 actuators" -> "Shadow hand in MuJoCo" (a real keyframe) -> "egg: force, lift, crack" ->
"labelled episode". At "simulated" the glove source splits into two boxes: a dashed grey "Rokoko Smartglove:
not available here" and a blue "scripted operator: used here". The chip "glove input: simulated" appears.

### 3. The wire path (about 17 s)

Narration:
> Here is the wire path. Rokoko's hand solver serves RGMP version two on TCP port twelve two seven seven. Type one
> messages define the stream. Type two carry twenty-six OpenXR joints, each a position and a rotation. Our client
> reads them directly, with no ROS install.

Picture: a flow row: "rkk-hand-solver" (dashed grey: needs the Rokoko SDK, not here) and "teleop fake-solver"
(blue: used here) -> "TCP :12277" -> "RgmpSource". Under it the message layout: u32 type, u32 length, payload.
Three type rows: 1 JSON definition (solved_hand, 26 streams), 2 binary (device_id, group_id, timestamp_us, then
26 x 7 float32: x y z qx qy qz qw, Y-up), 3 disconnect. A green chip "round trip within 1e-4 rad".

### 4. Retargeting (about 23 s)

Narration:
> Then retargeting. Frames turn Z-up, and a yaw calibration points the fingers forward. Each angle comes from a
> bone relative to its parent, so hand position does not change it. A flat hand, held for five seconds, sets each
> person's zero, and a filter smooths the noise. Twenty-one human angles become twenty Shadow actuators, six
> Inspire values and a wrist target.

Picture: left, the 26 joints of the recorded (scripted) glove frames of episode 0 as a moving skeleton. Right, the
chain in steps that light with the voice: "Z-up + yaw calibration", "21 human angles" (21 bars from the log),
"flat-hand zero, one-euro filter", then three outputs: "20 Shadow actuators" (20 bars), "6 Inspire values,
0 .. 1000", "wrist target -> mocap".

### 5. A clean lift (about 9 s)

Narration:
> A careful try. The hand lifts the egg eleven centimetres, at a peak grip force of three point seven six newtons.

Picture: EGG plays on a large card, from just before the grasp. Callouts name the HUD: "grip force" at the
bottom bar, "lift" at the right bar. On the right: "11.0 cm" max lift and "3.76 N" peak force arrive with the
voice, then a green chip "lifted".

### 6. The crush (about 12 s)

Narration:
> Now a squeeze. Force reaches nineteen point six newtons, past the crack threshold of eight, and the egg
> turns red. That threshold is a simulation proxy, not a measured egg.

Picture: CRUSH plays on the card; when it ends, its last frame stays. On the right a force chart from LOG
(episode 1) draws in step with the clip, with a dashed line "crack threshold 8 N". The peak gets a red label
"19.6 N". A grey chip "8 N: a simulation proxy, not measured". A red chip "crushed".

### 7. Every try is an episode (about 11 s)

Narration:
> Every try is saved as a training episode, with grip force per frame and a simulator label. Lifted. Crushed.
> Lifted. Not lifted.

Picture: four cards, one per episode; each plays its own clip (EGG, CRUSH, DROP, MISS) and holds the last frame. A row of tags "glove frames",
"actions", "force per frame". The labels land one per tick: green "lifted", red "crushed", green "lifted",
grey "not lifted", each with its lift and peak force in mono.

### 8. Inside an episode (about 17 s)

Narration:
> Each episode file holds ten arrays, one row per step: time, raw glove frames, human angles, actions, wrist target,
> Inspire commands, joint positions, hand pose, egg pose and egg force. The actions and the wrist target are
> enough to replay it.

Picture: `episode_0000.npz` as a table of its ten arrays with their shapes (1032 steps), one row per tick.
Then `action` and `wrist_target` turn green, with a chip "teleop replay: same label 4 / 4".

### 9. Thresholds miss things (about 25 s)

Narration:
> But thresholds miss things. The third egg rose ten point nine centimetres, so the simulator says lifted. Then
> the hand opened in the air. NVIDIA Nemotron reviews each episode from keyframes and the force log. Verdict:
> dropped, confidence zero point nine eight. Grip force hit zero with the egg three point four centimetres up.
> The episode is flagged for a human. The simulator label stays.

Picture: DROP plays large. A green chip "simulator: lifted, 10.9 cm" lands with the voice. Then the card moves to
the top left, the three keyframes of episode 2 line up under it (amber frames: what the model sees), and a lift
and force chart from LOG draws on the right. A marker at t = 6.25 s: "force 0.0 N, egg 3.4 cm up". The verdict
card: "Nemotron 3.5 Super VL: dropped", "confidence 0.98". A red chip "flagged for a human", a grey chip
"simulator label kept: lifted".

### 10. How the review works (about 34 s)

Narration:
> The review step by step. Nemotron gets four keyframes, from first contact to the end, and a twenty-four row force
> and lift timeline. It must answer in strict JSON, citing a frame or the log for each claim. A bad schema gets one
> repair request. A grounding check compares its numbers with the log. Then the cross-check with the simulator. One
> bug we hit: with a twelve-hundred-token budget, the model spent it all reasoning and replied empty. Now it gets
> four thousand ninety-six, and empty replies are never cached.

Picture: left, the inputs: four keyframes of episode 0 (contact, peak force, max lift, final) and a 24-row timeline
strip. Middle, the real JSON answer for episode 2 (outcome, confidence, one evidence item). Right, the quality steps
light one by one: schema check (1 repair), grounding check (1 self-check), cross-check (flag). Last, a red bug card
"max_tokens 1200: empty reply" turns into a green "4096, empty replies never cached".

### 11. Proof (about 14 s)

Narration:
> Nemotron agrees on three of four, and four episodes is a smoke test, not an accuracy figure. Fifty-two tests
> pass. Our client speaks Rokoko's RGMP wire format, and round-trips joint angles. Replay gives the same label,
> four of four.

Picture: four dots, three green and one red: "3 of 4 agree, 1 flagged", with a grey chip "a smoke test, not an
accuracy figure". Then three cards: "52 tests pass" (a counter), "RGMP v2 client: TCP 12277, 26 OpenXR joints,
round trip within 1e-4 rad", "replay: same label 4 / 4" with four checks.

### 12. Verified, and not yet (about 21 s)

Narration:
> What is verified, and what is not. Verified with no gloves: the wire format against Rokoko's bridge code, the
> angle maths, the MuJoCo hand, labels and replay. Still needs hardware: real Smartglove data, the ROS 2 path, the
> live viewer, and a real Inspire hand. And the crack threshold stays a proxy.

Picture: two columns. "verified, no gloves" with green checks, one per item as it is spoken. "needs hardware"
with dashed grey boxes. Last, a grey chip "crack threshold 8 N: a simulation proxy".

### 13. Programming a policy in weight space (about 40 s)

Narration:
> The labels make the data trainable. We trained a small policy on four hundred eighty scripted demonstrations,
> then fine-tuned one copy on the lifted ones and one on the crushed ones. The difference in weights is a task
> vector. Add the lifted vector, with no new training, and success on unseen eggs goes from twenty-seven to
> sixty-seven percent, while crushes fall from sixty-two to twenty-eight. Add the crushed vector, and crushes rise
> to eighty-three. Not everything works: subtracting the crushed vector breaks the reach. Scripted
> demonstrations, simulated egg.

Picture: left, the program θ = θ₀ + a·τ_lifted + c·τ_crushed in big mono, with a and c as small dials that move
with the voice (a: 0 → 1, then c: 0 → 1, then c → −1). Right, three stat columns with hairline dividers: θ₀ 27 %
lifted (62 % crushed), +τ_lifted 67 % lifted (28 % crushed), +τ_crushed 83 % crushed (13 % lifted). The blue
block: "+τ_lifted: 27 % → 67 % lifted". A grey row for the negative result: "−τ_crushed: 3 % lifted, it breaks
the reach", and "clock-only policy: at most 31 % on a moved egg". A mono line with the setup: 480 scripted demos
(153 lifted / 255 crushed / 72 not lifted), 5 seeds × 20 unseen egg positions = 100 rollouts per program,
no gradient step at program time.

### 14. Next (about 10 s)

Narration:
> Next: real Rokoko gloves at the venue, Inspire hand commands sent to a real hand, and a behaviour-cloning
> policy trained on clean episodes only.

Picture: three cards arrive with the voice. 1: "real Rokoko gloves at the venue". 2: "Inspire hand": six bars move
with the Inspire commands from LOG (episode 0, scale 0 to 1000), "computed every frame, not sent yet".
3: "behaviour cloning on clean episodes", tag "plan".

### 15. Close (about 4 s)

Narration:
> Egg Shell. The robot feels what you can't.

Picture: the final keyframe of episode 0 (the white egg, set down) on its card, the title, the tagline, and three
short lines: "every try becomes a labelled episode", "Nemotron flags what thresholds miss", "glove input
simulated; real gloves next". Credit line at the bottom of the frame above the caption zone.

## Numbers and their sources

| Number | Source |
|---|---|
| egg episode: lifted, max lift 11.0 cm, peak force 3.76 N | `docs/demo-run/episodes.jsonl` episode 0 (`max_lift_m` 0.1102, `peak_force_n` 3.763) |
| crush: crushed, peak force 19.63 N (spoken "nineteen point six") | episodes.jsonl episode 1 (`peak_force_n` 19.626) |
| crack threshold 8 N, a simulation proxy, not a measured egg property | episodes.jsonl `crack_force_n` 8.0; README "What is verified" |
| drop: simulator label "lifted", max lift 10.9 cm, peak 3.08 N | episodes.jsonl episode 2 (`max_lift_m` 0.1092, `peak_force_n` 3.077) |
| drop: Nemotron says "dropped", confidence 0.98; grip force 0.0 N at t = 6.25 s with the egg 3.4 cm up; flagged | `docs/demo-run/reviews.jsonl` episode 2 |
| the simulator label is never overwritten | `docs/SUBMISSION.md`, Nemotron section |
| miss: not_lifted, 0.0 cm, peak 2.23 N | episodes.jsonl episode 3 |
| 3 of 4 agree, 1 flagged | reviews.jsonl (`status`) |
| replay: same label 4 of 4 | README "What is verified" (`teleop replay` on the demo set) |
| 52 automated tests pass | `docs/SUBMISSION.md` "Proof it works" |
| RGMP v2, TCP port 12277, 26 OpenXR joints, round trip within 1e-4 rad | README "Architecture" and "What is verified" |
| Shadow hand: 20 actuators | `datasets/demo/info.json` (`action_names`, 20 entries) |
| Inspire commands 0 to 1000 per finger, computed every frame, not sent yet | README "Architecture"; `inspire` array in episode_0000.npz |
| Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl-120b-a12b`), after the episodes are saved, never in the control loop | reviews.jsonl `model_id`; SUBMISSION.md |
| chart curves (force and lift over time) | `egg_force` and `egg_pose` in episode_0001.npz and episode_0002.npz; lift is the egg height minus its height at t = 0 |
| RGMP v2 message layout: u32 type, u32 length, payload; type 1 JSON definition, type 2 binary (`<IIQ` + 26 x `<7f`, Y-up), type 3 disconnect | README "Architecture" |
| hold a flat hand for the first 5 s to calibrate yaw, finger zero and wrist anchor | README "With real gloves at the venue" |
| 21 canonical human angles, one-euro filter, 20 Shadow actuators, 6 Inspire values, wrist -> mocap target | README "Architecture" and "Retargeting"; `info.json` |
| ten arrays in each episode file, 1032 steps in episode 0, the shapes on screen | `datasets/demo/episode_0000.npz` (keys and shapes); episodes.jsonl `steps` 1032 |
| four keyframes, 24-row force/lift timeline, strict JSON, one repair request, grounding check with one self-check, cross-check | README "Second opinion on every label" |
| token budget 1200 gave empty replies; now 4096, empty replies never cached | README (4096, empty replies); git history of `src/rokoko_teleop/nemotron.py` (`max_tokens: int = 1200` -> `4096`, commit ea325a0e) |
| verified and needs-hardware lists | README "What is verified, and what needs hardware" |
| 200 random poses in the angle round-trip tests | README "What is verified" |
| weight space (scene 13): 480 scripted demos, egg moved up to ±15 mm, 153 lifted / 255 crushed / 72 not lifted; 5 seeds × 20 unseen egg positions = 100 rollouts per program; θ₀ 27 % lifted / 62 % crushed; θ₀ + τ_lifted 67 % / 28 %; θ₀ + τ_crushed 13 % / 83 %; θ₀ − τ_crushed 3 % lifted; clock-only (time-indexed) policy at most 31 % lifted; no gradient step at program time | `docs/weightspace/results_v2.json`, `docs/weightspace/README.md` (v2) |
