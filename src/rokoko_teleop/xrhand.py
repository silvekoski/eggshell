"""The OpenXR hand skeleton that Rokoko's hand solver emits.

`rkk-hand-solver --emit-openxr` streams 26 joints per hand in
XrHandJointEXT order. Each joint pose is a position (metres) and an
orientation (x, y, z, w). OpenXR bone frames: -Z points along the bone,
towards the fingertip; +Y points out of the back of the hand; +X = Y x Z.

Raw solver data (RGMP) is in `xr_base`, which is Y-up. The ROS 2 bridge
republishes it Z-up (REP-103) and applies a yaw calibration. Everything in
this package works Z-up, like ROS and MuJoCo, so raw RGMP frames go
through `XrBaseToZUp` first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import quat as Q

JOINT_NAMES: tuple[str, ...] = (
    "palm",
    "wrist",
    "thumb_metacarpal",
    "thumb_proximal",
    "thumb_distal",
    "thumb_tip",
    "index_metacarpal",
    "index_proximal",
    "index_intermediate",
    "index_distal",
    "index_tip",
    "middle_metacarpal",
    "middle_proximal",
    "middle_intermediate",
    "middle_distal",
    "middle_tip",
    "ring_metacarpal",
    "ring_proximal",
    "ring_intermediate",
    "ring_distal",
    "ring_tip",
    "little_metacarpal",
    "little_proximal",
    "little_intermediate",
    "little_distal",
    "little_tip",
)
JOINT_COUNT = 26
J = {name: i for i, name in enumerate(JOINT_NAMES)}

FINGERS = ("index", "middle", "ring", "little")

# Local bone axes (OpenXR convention).
FORWARD = np.array([0.0, 0.0, -1.0])  # along the bone, distal
DORSAL = np.array([0.0, 1.0, 0.0])  # out of the back of the hand

HAND_LEFT = "left"
HAND_RIGHT = "right"


@dataclass
class HandFrame:
    """One solved hand at one instant: 26 joint poses."""

    hand: str  # "left" | "right"
    positions: np.ndarray  # (26, 3) metres
    orientations: np.ndarray  # (26, 4) x, y, z, w
    timestamp_us: int = 0
    device_id: int = 0
    frame: str = "zup"  # "xr_base" (raw RGMP, Y-up) or "zup" (ROS / MuJoCo)

    def pose(self, name: str) -> tuple[np.ndarray, np.ndarray]:
        i = J[name]
        return self.positions[i], self.orientations[i]

    def as_rows(self) -> list[list[float]]:
        """26 rows of [x, y, z, qx, qy, qz, qw]: the recording format."""
        return np.concatenate([self.positions, self.orientations], axis=1).round(6).tolist()

    @classmethod
    def from_rows(cls, rows, hand: str, **kw) -> "HandFrame":
        a = np.asarray(rows, dtype=float).reshape(JOINT_COUNT, 7)
        return cls(hand=hand, positions=a[:, :3].copy(), orientations=a[:, 3:].copy(), **kw)


# Y-up to Z-up: +90 degrees about X (same as rkk_hand_bridge.frame_convert).
XR_BASE_TO_ZUP = Q.axis_angle((1.0, 0.0, 0.0), math.pi / 2.0)


@dataclass
class XrBaseToZUp:
    """xr_base (Y-up) to Z-up, followed by a yaw about +Z.

    The solver references heading to magnetic north, so until the yaw is
    calibrated the hand has the right shape but faces an arbitrary way.
    """

    yaw_rad: float = 0.0

    def rotation(self) -> np.ndarray:
        return Q.normalize(Q.mul(Q.rz(self.yaw_rad), XR_BASE_TO_ZUP))

    def apply(self, f: HandFrame) -> HandFrame:
        if f.frame == "zup":
            r = Q.rz(self.yaw_rad)
        else:
            r = self.rotation()
        R = Q.to_matrix(r)
        pos = f.positions @ R.T
        ori = np.array([Q.normalize(Q.mul(r, q)) for q in f.orientations])
        return HandFrame(f.hand, pos, ori, f.timestamp_us, f.device_id, frame="zup")


def wrist_heading(f: HandFrame) -> float:
    """Heading (rad, about +Z) the fingers point at, in a Z-up frame."""
    _, q = f.pose("wrist")
    fwd = Q.rotate(q, FORWARD)
    if math.hypot(fwd[0], fwd[1]) < 0.2:
        raise ValueError("hand is too vertical to read a heading")
    return math.atan2(fwd[1], fwd[0])


def yaw_to_face(f: HandFrame, facing_rad: float = 0.0) -> float:
    """Yaw offset that makes a Z-up hand frame point its fingers at `facing_rad`."""
    d = facing_rad - wrist_heading(f)
    return math.atan2(math.sin(d), math.cos(d))


@dataclass
class HandDefinition:
    device_id: int
    hand: str
    joint_names: tuple[str, ...] = JOINT_NAMES
    joint_radii: tuple[float, ...] = field(default_factory=lambda: (0.0,) * JOINT_COUNT)
    timestamp_epoch: str | None = "unix_epoch"
    group_id: int = 0
