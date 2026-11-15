# Egg Shell · Rokoko: The Robot Teleoperation Challenge

> Submission text for the Junction platform. Paste it field by field. Set the project to FINAL before Sun 15.11 10:00.
> The older draft in `docs/submissions/rokoko.md` is out of date: this file replaces it.

**Read this first: the glove input in this submission is simulated.** We had no Rokoko SDK licence and no
Smartgloves. A scripted operator produces the same OpenXR hand frames that the Rokoko solver sends. Those frames
go through the real pipeline: retargeting, the MuJoCo Shadow hand, egg physics and labelled episodes. No person
wore a glove in the video or in the numbers below.

## Project name
Egg Shell

## Punchline
Pick up an egg with a robot hand, and every try becomes labelled training data.

## Description

**The problem.** Robots learn dexterous skills from human demonstrations, and teleoperation is how we collect
them. But the operator feels nothing through the glove, so many demonstrations are bad grasps: the object drops,
or the hand crushes it. Someone must sort them by hand before training. Rokoko's brief names both points:
precise manipulation of fragile objects, and collecting human demonstrations to train robot policies.

**What we built.** A Rokoko Smartglove stream drives a simulated Shadow Dexterous Hand (20 actuators) in MuJoCo.
On the table is an egg that can crack. Squeeze too hard and the egg turns red: the simulator sees the squeeze
that the operator cannot feel. Each attempt is saved as a training episode with the grip force for each frame,
and the simulator labels it: lifted, not lifted or crushed. Then NVIDIA Nemotron 3.5 Super VL reviews each
episode from its camera frames and its force log. It catches what the thresholds miss, for example an egg that
was lifted and then dropped. The same glove stream also computes commands for the real Inspire robot hand
(0 to 1000 per finger).

**What is real and what is simulated.**
- Simulated: the operator. A scripted operator generates the glove frames for four attempts: a careful lift,
  a crush, a drop (the hand opens in the air) and a miss (the hand closes 5 cm too high).
- Real code, verified with no hardware: our client for the Rokoko solver's RGMP v2 stream (TCP port 12277,
  26 OpenXR joints). We wrote it from Rokoko's `rokoko-ros2-bridge` code. Through a fake solver, angles come
  back within 1e-4 rad. The live client calibrates, lifts the egg and records a labelled episode in real time.
- Not verified: real Smartglove data, the ROS 2 path, the live viewer window (no display on our build machine),
  and the real Inspire hand.

**Proof it works.**
- 57 automated tests pass: retargeting maths, the wire format, the TCP path, the MuJoCo checks and the
  Nemotron review (HTTP mocked).
- The four demo episodes: careful lift 11.0 cm at a peak force of 3.76 N (lifted). Squeeze 19.63 N (crushed,
  against a crack threshold of 8 N). Drop: 10.9 cm, then the egg falls (the simulator says lifted). Miss: 0.0 cm
  at 2.23 N (not lifted).
- Replay: `teleop replay` drives a fresh simulation from the recorded actuator and wrist targets of each episode.
  All 4 episodes give the same label, lift and peak force again.
- Nemotron review on the 4 episodes: it agrees with the simulator on 3. On the drop it says "dropped"
  (confidence 0.98), so the episode is flagged for a human. Four episodes is a smoke test, not an accuracy figure.
- The 8 N crack threshold is a simulation proxy. It is not a measured property of an egg.

**Why it matters.** Each robot lab that collects teleoperation data spends time to clean it. Egg Shell sorts the
data when it is captured, and a vision-language model checks the labels that thresholds get wrong.
Technical execution: a full pipeline from glove bytes to labelled `.npz` episodes, with tests and a replay that
reproduces each label. Originality: the haptics gap becomes the feature, because the simulator feels what the
operator cannot. Usefulness: one pipeline for fragile-object practice, clean demonstration datasets and a real
robot hand. Human-controlled robotics: the pipeline is built for a human hand that drives a 20-actuator dexterous
hand. In this submission the hand is simulated, and the next step is a real glove.

**Weight-space programming.** The labels are what make the dataset useful for training, so we tested that.
We trained a closed-loop behaviour-cloning policy on 480 demonstrations, with the egg moved up to 15 mm between
episodes. Then we fine-tuned one copy on the lifted episodes and one on the crushed episodes. The differences are
"task vectors": adding them to the base weights changes the behaviour with no new training. On 5 seeds × 20 egg
positions the policy never saw, the base policy lifts 27 % and crushes 62 %. Base + the "lifted" vector lifts 67 %
and crushes 28 %. Adding the "crushed" vector raises crushes to 83 %. Not everything works: subtracting the
"crushed" vector breaks the reach (3 % lifted). A policy that sees only the clock cannot find a moved egg (31 % at
best). Demonstrations are scripted. Details: `rokoko-teleop/docs/weightspace/README.md`.

## NVIDIA Nemotron (Best Use of Nemotron tech challenge)

**Model used.** NVIDIA Nemotron 3.5 Super VL (`nvidia/nemotron-3.5-super-vl-120b-a12b`), through the NVIDIA
Build API.

**What it does.** The simulator labels each episode from thresholds: a lift of 5 cm or more, a force above the
crack threshold. Thresholds miss things. An egg that is lifted and then dropped from 10 cm still counts as
"lifted". After each session, `teleop review` gives each episode to Nemotron with the camera frames of the key
moments (first contact, peak force, highest lift, end) and a 24-row force/lift timeline from the log. It returns
strict JSON: a label (lifted, dropped, not lifted, crushed), a confidence, a reason, and evidence that cites a
named frame or the log, with a time. We compare its label with the simulator label and flag a disagreement for a
human. The simulator label is never overwritten. The review runs after the episodes are saved, never in the
control loop.

**Result on our demo set.** 3 of 4 agree. On the drop episode, the simulator said "lifted" and Nemotron said
"dropped" (confidence 0.98): "the grip force dropped to 0.0 N at t=6.25s while the egg was still at 3.4 cm height,
followed by a rapid descent to -0.7 cm (max speed 1.262 m/s), confirmed by the final frame showing the egg resting
on the table with the hand open." Full output: `rokoko-teleop/docs/demo-run/review.md`.

**How we improved its outputs.**
- Structured output: a strict JSON schema with a fixed set of outcomes. Each evidence item must cite `log` or a
  frame of that episode. An invalid reply gets one repair request that states the exact error.
- Grounding check: the peak force and the highest lift that the model states must match the log (within 15 %).
  "Crushed" needs a red egg in a frame or a force above the threshold. If the check fails, the model gets one
  self-check request with its numbers next to the logged numbers.
- Token budget: in our first live run, the model used the whole 1200-token budget on reasoning and returned no
  content for the drop episode. We raised the budget to 4096, stopped the cache from storing empty replies, and
  send an empty reply to the repair step as an error. A test covers this.
- Reliability: at most 3 requests per episode, a 60 s timeout, retries with backoff on 429 and 5xx errors, and
  a disk cache by request hash. With no key or with the API down, the app keeps working and the simulator labels
  stand.

## Challenge
Rokoko: The Robot Teleoperation Challenge

## Technologies used
Python, MuJoCo, MuJoCo Menagerie (Shadow Dexterous Hand), NumPy, imageio, uv, pytest, NVIDIA Nemotron 3.5 Super VL
(NVIDIA Build API), Rokoko Device SDK wire format (rkk-hand-solver, RGMP v2 over TCP), rokoko-ros2-bridge message
format, OpenXR hand skeleton

## Links
- Pitch video, Remotion version (1:55.6, ElevenLabs voice): `rokoko-teleop/docs/egg-shell-pitch.mp4` (team preview https://nixos-1.tail5b0fae.ts.net:4417/egg-shell-pitch-remotion.mp4). Pick ONE pitch video to upload.
- Pitch deck PDF: `rokoko-teleop/docs/egg-shell-pitch-deck.pdf` (10 slides).
- Video (pitch, hyperframes version, 1:57.7): `rokoko-teleop/video/out/egg-shell.mp4`. TODO(person): upload it as a public or unlisted video and paste the link here. Team preview (tailnet only): https://nixos-1.tail5b0fae.ts.net:4417/egg-shell.mp4
- Extended technical walkthrough (3:59.7, not the pitch video): `rokoko-teleop/video-extended/out/egg-shell-extended.mp4`. Team preview: https://nixos-1.tail5b0fae.ts.net:4417/egg-shell-extended.mp4
- Source: `github.com/henrikkvamme/junction-2026` → `rokoko-teleop/`. TODO(person): the repository is private. Make it public or give the organizers access.
- Demo: no hosted demo. Run it from the README with no hardware:
  `scripts/glrun uv run teleop demo --scripts egg crush drop miss`, then `uv run teleop review --dataset datasets/demo`.
- Stills: `rokoko-teleop/docs/demo-egg.png`, `rokoko-teleop/docs/demo-crush.png`, `rokoko-teleop/docs/demo-run/drop-final.png`.

## Judge Q&A prep

- **Did you run this with real gloves?** No. We had no SDK licence and no gloves. A scripted operator and a fake
  solver that speaks Rokoko's RGMP v2 format drive it. The client is built from Rokoko's own bridge code, and
  `teleop record-glove` and `teleop run --source rgmp` are ready for a real solver.
- **Is the crack force realistic?** No. 8 N of summed contact force is a simulation threshold, set between the
  careful grasp (3.76 N) and the squeeze (19.63 N). It is not a measured property of an egg.
- **How good is the Nemotron review?** We have 4 episodes: 3 agree, and the 1 disagreement is correct (the
  drop). That is a smoke test, not an accuracy figure. The next step is a few hundred episodes with tremor and
  noise, and a hand-labelled sample.
- **How do you know the labels help training?** Not proven yet. The plan is a LeRobot export and a
  behaviour-cloning policy trained on the clean episodes, compared with one trained on all episodes.
- **Why simulation and not the G1 or the Inspire hand?** The G1 is shared with another challenge, and we had no
  glove access. The Inspire commands are computed and recorded on each frame, but nothing sends them yet.

## Before FINAL: checklist
- Watch both videos once (nobody has heard the voice yet), then upload the pitch cut and paste the link. It must stay at or under 2:00.
- Decide the source code publicity (the repository is private).
- Make the pitch deck PDF if the platform requires one.
- Fill in the team phone numbers, the Discord usernames and the credit choice on the platform.
