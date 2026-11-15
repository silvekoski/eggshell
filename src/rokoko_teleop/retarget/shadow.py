"""HandAngles -> Shadow Dexterous Hand (MuJoCo Menagerie `shadow_hand`) controls.

The Shadow hand is close to human kinematics, so most joints map one to
one. Its middle and distal finger joints are coupled by a tendon
(J0 = J1 + J2), so the actuator gets PIP + DIP. The thumb differs most:
THJ5 rotates the thumb base about the palm axis, THJ4 swings it across
the palm (opposition). The gains below were tuned so the canonical pinch
closes thumb and index tips together (see tests/test_sim.py).
"""

from __future__ import annotations

import numpy as np

from ..hand_model import HandAngles

ACTUATORS: tuple[str, ...] = (
    "rh_A_WRJ2", "rh_A_WRJ1",
    "rh_A_THJ5", "rh_A_THJ4", "rh_A_THJ3", "rh_A_THJ2", "rh_A_THJ1",
    "rh_A_FFJ4", "rh_A_FFJ3", "rh_A_FFJ0",
    "rh_A_MFJ4", "rh_A_MFJ3", "rh_A_MFJ0",
    "rh_A_RFJ4", "rh_A_RFJ3", "rh_A_RFJ0",
    "rh_A_LFJ5", "rh_A_LFJ4", "rh_A_LFJ3", "rh_A_LFJ0",
)
IDX = {n: i for i, n in enumerate(ACTUATORS)}

# Control ranges from the Menagerie model, so the map can clip without MuJoCo.
CTRL_RANGE: dict[str, tuple[float, float]] = {
    "rh_A_WRJ2": (-0.523599, 0.174533), "rh_A_WRJ1": (-0.698132, 0.488692),
    "rh_A_THJ5": (-1.0472, 1.0472), "rh_A_THJ4": (0.0, 1.22173), "rh_A_THJ3": (-0.20944, 0.20944),
    "rh_A_THJ2": (-0.698132, 0.698132), "rh_A_THJ1": (-0.261799, 1.5708),
    **{f"rh_A_{f}J4": (-0.349066, 0.349066) for f in ("FF", "MF", "RF", "LF")},
    **{f"rh_A_{f}J3": (-0.261799, 1.5708) for f in ("FF", "MF", "RF", "LF")},
    **{f"rh_A_{f}J0": (0.0, 3.1415) for f in ("FF", "MF", "RF", "LF")},
    "rh_A_LFJ5": (0.0, 0.785398),
}
LO = np.array([CTRL_RANGE[n][0] for n in ACTUATORS])
HI = np.array([CTRL_RANGE[n][1] for n in ACTUATORS])

FINGER_PREFIX = {"index": "FF", "middle": "MF", "ring": "RF", "little": "LF"}
# Sign of each knuckle (J4) joint for "towards the thumb": the Menagerie
# model flips the axis on ring and little. Verified in tests/test_sim.py.
ABD_SIGN = {"index": -1.0, "middle": -1.0, "ring": 1.0, "little": 1.0}


class ShadowRetargeter:
    """Joint-space map with per-joint gain/offset, then clip to limits."""

    def __init__(
        self,
        abd_gain: float = 1.0,
        thumb_rot_gain: float = 1.0,
        thumb_opp_gain: float = 1.0,
        thumb_rot_offset: float = 0.0,
        thumb_opp_offset: float = 0.0,
    ):
        self.abd_gain = abd_gain
        self.thumb_rot_gain = thumb_rot_gain
        self.thumb_opp_gain = thumb_opp_gain
        self.thumb_rot_offset = thumb_rot_offset
        self.thumb_opp_offset = thumb_opp_offset

    def __call__(self, a: HandAngles) -> np.ndarray:
        c = np.zeros(len(ACTUATORS))
        for finger, p in FINGER_PREFIX.items():
            c[IDX[f"rh_A_{p}J4"]] = ABD_SIGN[finger] * self.abd_gain * a[f"{finger}_mcp_abd"]
            c[IDX[f"rh_A_{p}J3"]] = a[f"{finger}_mcp_flex"]
            c[IDX[f"rh_A_{p}J0"]] = a[f"{finger}_pip"] + a[f"{finger}_dip"]
        # Little-finger cupping, helped by a share of its MCP flexion (the
        # Shadow LFJ5 metacarpal is what lets the little finger reach the thumb).
        c[IDX["rh_A_LFJ5"]] = a["little_cup"] + 0.25 * max(0.0, a["little_mcp_flex"])

        # Thumb. Opposition (THJ4) follows CMC flexion across the palm; base
        # rotation (THJ5) follows CMC abduction away from the palm.
        c[IDX["rh_A_THJ4"]] = self.thumb_opp_offset + self.thumb_opp_gain * a["thumb_cmc_flex"] * 1.3
        c[IDX["rh_A_THJ5"]] = self.thumb_rot_offset + self.thumb_rot_gain * (a["thumb_cmc_abd"] - 0.15) * 1.4
        c[IDX["rh_A_THJ3"]] = 0.0
        c[IDX["rh_A_THJ2"]] = a["thumb_mcp"] * 0.3
        c[IDX["rh_A_THJ1"]] = a["thumb_ip"]
        return np.clip(c, LO, HI)
