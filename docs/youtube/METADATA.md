# Egg Shell: YouTube and Junction platform metadata

Video to upload: `rokoko-teleop/docs/egg-shell-pitch.mp4` (Remotion, 1:55.6), or the hyperframes cut
`rokoko-teleop/video/out/egg-shell.mp4` (1:57.7). Both are under the 2:00 limit. The chapters below match the
Remotion cut.

Thumbnail: `rokoko-teleop/docs/youtube/thumbnail.png` (1280x720 PNG, under 2 MB). To build it again, open
`thumbnail.html` in Chromium and take a 1280x720 screenshot.

---

## YouTube

**Title** (81 characters)

```
Egg Shell: a robot hand that feels the squeeze you can't | Rokoko × Junction 2026
```

**Description**

```
Robots learn to grasp from human demonstrations. But through a teleoperation glove you feel nothing, so many demos end as drops and crushes, and someone sorts them by hand.

Egg Shell: a Rokoko glove stream drives a simulated Shadow Dexterous Hand (20 actuators) in MuJoCo, holding an egg that can crack. Each try is saved as a training episode with the grip force of every frame, and the simulator labels it: lifted, crushed or not lifted. NVIDIA Nemotron 3.5 Super VL reviews each episode from four keyframes and the force log, and flags what the thresholds miss, such as an egg that was lifted and then dropped.

Then the labels train a robot policy: adding the "lifted" task vector to the policy weights, with no new training, raised the lift rate from 27 % to 67 % on egg positions the policy never saw (5 seeds × 20 positions). Subtracting the "crushed" vector did not work: it broke the reach.

Honest note: we had no Rokoko gloves or SDK licence at the event. All glove input in this video is simulated: a scripted operator produces the same OpenXR hand frames as the Rokoko solver. The 8 N crack threshold is a simulation proxy, not a measured egg. The narration is an AI voice (ElevenLabs).

Chapters
0:00 Robots learn from demos, but you feel nothing
0:13 Egg Shell (glove input simulated)
0:30 Careful lift vs squeeze
0:45 Labelled episodes, and Nemotron catches the drop
1:12 Weight-space programming: 27 % → 67 %
1:31 Proof and next steps

Built at Junction 2026 for the Rokoko Robot Teleoperation Challenge.
Stack: Python, MuJoCo, MuJoCo Menagerie Shadow Hand, NumPy, NVIDIA Nemotron 3.5 Super VL, Rokoko RGMP v2 wire format (rebuilt from rokoko-ros2-bridge), OpenXR hand skeleton, Remotion.
Source: <REPO LINK>

#robotics #teleoperation #junction2026
```

**Tags** (comma separated, under 500 characters)

```
robotics, teleoperation, rokoko, junction 2026, hackathon, robot hand, shadow hand, dexterous manipulation, mujoco, simulation, imitation learning, behaviour cloning, robot learning, task vectors, weight space, nvidia nemotron, vision language model, data labelling, smartgloves, motion capture
```

**Settings**
- Visibility: **Public**. Junction requires that the video is "available for everyone"; Unlisted also works if the link is shared.
- Audience: not made for kids.
- Category: Science & Technology.
- Altered or synthetic content: **No**. The footage is an obvious 3D simulation, and the AI narration is disclosed in the description. Choose Yes if you want to be extra careful.
- Language: English. Captions: auto-generated is fine. The `.srt` from the hyperframes cut matches only that cut.
- License: Standard YouTube. Comments: on.

---

## Junction platform (paste field by field)

**Project name**

```
Egg Shell
```

**Punchline**

```
Pick up an egg with a robot hand, and every try becomes labelled training data.
```

**Description**: paste the "Description" section of `rokoko-teleop/docs/SUBMISSION.md`, from "The problem" through "Why it matters", plus the "Weight-space programming" paragraph. Short version if the field is limited:

```
Robots learn dexterous skills from human demonstrations, but through a teleoperation glove the operator feels nothing, so many demos are drops and crushes that someone sorts by hand.

Egg Shell: a Rokoko glove stream (RGMP v2 client rebuilt from Rokoko's rokoko-ros2-bridge code) drives a 20-actuator Shadow hand in MuJoCo, holding an egg that can crack. Every try becomes a labelled training episode with per-frame grip force: lifted (careful: 11.0 cm at 3.76 N), crushed (19.63 N, past an 8 N simulation threshold) or not lifted. NVIDIA Nemotron 3.5 Super VL reviews each episode from keyframes and the force log. On a drop the thresholds called "lifted", it said "dropped" (0.98) and flagged it for a human.

The labels make the data trainable. We fine-tuned a closed-loop policy on lifted and crushed episodes, and added the resulting task vector to the base weights with no new training: on 100 rollouts with unseen egg positions, lifts rose from 27 % to 67 % and crushes fell from 62 % to 28 %. Subtracting the crushed vector failed (it broke the reach), and we say so.

Verified: 57 automated tests, wire-format round trip within 1e-4 rad, replay reproduces 4 of 4 labels. Honest note: we had no gloves or SDK licence, so all glove input is simulated by a scripted operator producing the same OpenXR frames as the Rokoko solver.
```

**Challenge**: Rokoko – The Robot Teleoperation Challenge. Tech challenge: NVIDIA – Best Use of Nemotron (if the platform has a field for it).

**Technologies used**

```
Python, MuJoCo, MuJoCo Menagerie (Shadow Dexterous Hand), NumPy, uv, pytest, NVIDIA Nemotron 3.5 Super VL (NVIDIA Build API), Rokoko Device SDK wire format (RGMP v2 over TCP), rokoko-ros2-bridge message format, OpenXR hand skeleton, Remotion, ElevenLabs
```

**Video pitch**: `<YOUTUBE LINK>` (≤ 2:00)

**Demo link**: no hosted demo. The demo runs locally with no hardware (`scripts/glrun uv run teleop demo --scripts egg crush drop miss`). Use the YouTube link here too, or `<REPO LINK>/tree/main/rokoko-teleop`.

**Source code link**: `<REPO LINK>/tree/main/rokoko-teleop`

**Source code publicity**: TODO(person). The repository `github.com/henrikkvamme/junction-2026` is private now. Make it public, or give the organizers access. The rules say organizers must be able to see the source.

**Credited for the project**: TODO(person): yes or no, for each team member.

**Pitch deck (PDF)**: upload `rokoko-teleop/docs/egg-shell-pitch-deck.pdf` (10 slides, 1.9 MB).

**Phone numbers, Discord usernames**: TODO(person). These are private; enter them only on the platform.
