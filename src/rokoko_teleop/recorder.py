"""Demonstration recorder: every teleoperated episode becomes a training sample.

Per episode, one .npz with time-aligned arrays, plus a line in
`episodes.jsonl` with the automatic label. The label is the point: the
simulator knows whether the egg was lifted, dropped or crushed, so the
dataset arrives already sorted into good and bad demonstrations.

Arrays (T = number of control steps):
  t                 (T,)        seconds
  glove             (T, 26, 7)  scene-frame OpenXR joints [x y z qx qy qz qw]
  human_angles      (T, 21)     canonical angles (ANGLE_NAMES)
  action            (T, 20)     Shadow actuator targets (ACTUATORS)
  wrist_target      (T, 7)      commanded wrist pose [x y z qx qy qz qw]
  inspire           (T, 6)      Inspire hand commands 0..1000
  qpos              (T, 24)     Shadow joint positions
  root_pose         (T, 7)      hand root pose [x y z qw qx qy qz]
  egg_pose          (T, 7)      [x y z qx qy qz qw]
  egg_force         (T,)        hand-on-egg normal force, N
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .hand_model import ANGLE_NAMES
from .retarget.inspire import ORDER as INSPIRE_ORDER
from .retarget.shadow import ACTUATORS

LIFT_SUCCESS_M = 0.05


def pick_keyframes(frames: list[tuple[float, np.ndarray]], t: np.ndarray, force: np.ndarray,
                   lift: np.ndarray, contact_n: float = 0.2) -> list[tuple[str, float, np.ndarray]]:
    """From frames rendered during the episode, keep the ones nearest to the
    key moments: first contact, peak force, highest lift and the end."""
    if not frames or len(t) == 0:
        return []
    moments = []
    touched = np.flatnonzero(force > contact_n)
    if touched.size:
        moments.append(("contact", float(t[touched[0]])))
    moments.append(("peak_force", float(t[int(np.argmax(force))])))
    moments.append(("max_lift", float(t[int(np.argmax(lift))])))
    moments.append(("final", float(t[-1])))
    ft = np.array([f[0] for f in frames])
    out, used = [], set()
    for name, tm in moments:
        i = int(np.argmin(np.abs(ft - tm)))
        if i in used:
            continue
        used.add(i)
        out.append((name, float(ft[i]), frames[i][1]))
    return out


def label_episode(max_lift_m: float, final_lift_m: float, cracked: bool, peak_force_n: float,
                  crack_force_n: float) -> dict:
    if cracked:
        outcome = "crushed"
    elif max_lift_m >= LIFT_SUCCESS_M:
        outcome = "lifted"
    else:
        outcome = "not_lifted"
    gentleness = max(0.0, 1.0 - peak_force_n / crack_force_n) if crack_force_n > 0 else 0.0
    return {
        "outcome": outcome,
        "success": outcome == "lifted",
        "max_lift_m": round(max_lift_m, 4),
        "final_lift_m": round(final_lift_m, 4),
        "peak_force_n": round(peak_force_n, 3),
        "gentleness": round(gentleness, 3),
    }


@dataclass
class EpisodeBuffer:
    rows: dict[str, list] = field(default_factory=lambda: {
        k: [] for k in ("t", "glove", "human_angles", "action", "wrist_target", "inspire",
                        "qpos", "root_pose", "egg_pose", "egg_force")
    })
    max_lift: float = 0.0

    def add(self, t, cmd, sim, egg) -> None:
        r = self.rows
        r["t"].append(t)
        r["glove"].append(np.concatenate([cmd.frame.positions, cmd.frame.orientations], axis=1))
        r["human_angles"].append(cmd.angles.values.copy())
        r["action"].append(cmd.ctrl.copy())
        r["wrist_target"].append(np.concatenate([cmd.wrist_pos, cmd.wrist_quat]))
        r["inspire"].append(np.array(cmd.inspire))
        r["qpos"].append(sim.hand_qpos())
        r["root_pose"].append(sim.root_pose())
        r["egg_pose"].append(np.concatenate([egg.pos, egg.quat_xyzw]))
        r["egg_force"].append(egg.force_n)
        self.max_lift = max(self.max_lift, egg.lifted_m)

    def __len__(self) -> int:
        return len(self.rows["t"])


class DatasetWriter:
    def __init__(self, root: str | Path, meta: dict | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        info = self.root / "info.json"
        if not info.exists():
            info.write_text(json.dumps({
                "format": "rokoko-teleop/episodes-v1",
                "robot": "shadow_hand (MuJoCo Menagerie), floating",
                "task": "pick up the egg without crushing it",
                "action_names": list(ACTUATORS),
                "human_angle_names": list(ANGLE_NAMES),
                "inspire_order": list(INSPIRE_ORDER),
                **(meta or {}),
            }, indent=2))
        self.index = self.root / "episodes.jsonl"

    def next_id(self) -> int:
        if not self.index.exists():
            return 0
        return sum(1 for _ in self.index.open())

    def save(self, buf: EpisodeBuffer, label: dict, extra: dict | None = None,
             keyframes: list[tuple[str, float, np.ndarray]] | None = None) -> Path:
        """keyframes: (name, t, RGB image) camera frames of key moments, saved as
        PNGs next to the episode. `teleop review` shows them to Nemotron."""
        ep = self.next_id()
        path = self.root / f"episode_{ep:04d}.npz"
        arrays = {k: np.asarray(v) for k, v in buf.rows.items()}
        np.savez_compressed(path, **arrays)
        kf_meta = []
        if keyframes:
            import imageio.v2 as imageio  # noqa: PLC0415

            for name, t, img in keyframes:
                kf = self.root / f"episode_{ep:04d}_{name}.png"
                imageio.imwrite(kf, img)
                kf_meta.append({"name": name, "t": round(float(t), 3), "file": kf.name})
        entry = {"episode": ep, "file": path.name, "steps": len(buf), "saved": time.time(),
                 **label, **(extra or {})}
        if kf_meta:
            entry["keyframes"] = kf_meta
        with self.index.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        return path
