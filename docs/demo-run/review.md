# Episode review by Nemotron 3.5 Super VL

The simulator label comes from thresholds. Nemotron labels the same episode from the camera keyframes and the force/lift log. Flagged rows need a human look.

| Episode | Simulator | Nemotron 3.5 Super VL | Confidence | Status | Reason |
|---|---|---|---|---|---|
| 0 | lifted | lifted | 1.00 | agree | The egg was lifted to 11.1 cm with a peak force of 3.76 N, which is below the 8.0 N crack threshold, and it remained white in all frames. The grip force released only after the egg returned to the table surface, indicating a controlled placement. |
| 1 | crushed | crushed | 1.00 | agree | The egg turned red in the peak_force and max_lift frames, and the log records a peak force of 19.63 N which exceeds the 8.0 N crack threshold. |
| 2 | lifted | dropped | 0.98 | FLAG disagree | The egg was lifted to 11.0 cm but the grip force dropped to 0.0 N at t=6.25s while the egg was still at 3.4 cm height, followed by a rapid descent to -0.7 cm (max speed 1.262 m/s), confirmed by the final frame showing the egg resting on the table with the hand open. |
| 3 | not_lifted | not_lifted | 1.00 | agree | The log shows a peak force of 2.23 N at t=2.6s, below the 8.0 N crack threshold, and a max lift of 0.0 cm, below the 5 cm requirement; both frames show the egg white and resting on the table. |

## Episode 0: evidence cited by Nemotron 3.5 Super VL

- `log` t=7.8: max lift 11.1 cm
- `log` t=11.23: peak force 3.76 N
- `frame:max_lift` t=7.75: egg held in air, white
- `frame:final` t=17.0: egg resting on table, white, hand open
- Grounding check against the log: ok

## Episode 1: evidence cited by Nemotron 3.5 Super VL

- `frame:peak_force` t=3.75: The egg is red, indicating it has cracked.
- `log` t=3.65: Peak force was 19.63 N, exceeding the 8.0 N crack threshold.
- `frame:max_lift` t=5.5: The egg remains red while being held in the air.
- `log` t=5.62: Maximum lift height reached 13.4 cm.
- Grounding check against the log: ok

## Episode 2: evidence cited by Nemotron 3.5 Super VL

- `log` t=5.02: max lift reached 11.0 cm
- `log` t=6.25: force dropped to 0.0 N while lift was 3.4 cm
- `log` t=6.6: lift fell to -0.7 cm with force 0.0 N
- `frame:final` t=7.75: egg sits on table, hand open, egg is white
- Grounding check against the log: ok

## Episode 3: evidence cited by Nemotron 3.5 Super VL

- `log` t=2.6: peak force 2.23 N and max lift 0.0 cm
- `frame:contact` t=2.5: hand contacts white egg on table
- `frame:final` t=5.75: hand withdrawn, white egg remains on table
- Grounding check against the log: ok
