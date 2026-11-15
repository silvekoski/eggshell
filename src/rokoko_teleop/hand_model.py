"""A parametric human hand: canonical joint angles <-> OpenXR joint poses.

`HandAngles` is the robot-independent middle layer of the pipeline:

    Rokoko solver (26 OpenXR poses) -> HandAngles (21 angles) -> robot joints

`forward()` builds the 26 OpenXR poses from angles (used to synthesise a
glove stream with no hardware, and as ground truth in tests).
`retarget.human.extract_angles()` is its inverse on any OpenXR hand,
real or synthetic.

Frames: everything is expressed for a right hand. Wrist-local axes follow
OpenXR: -Z forward along the fingers, +Y out of the back of the hand,
+X = Y x Z (so on a right hand the thumb is on the -X side). A left hand is
the mirror image; `mirror_frame` converts between them.

Angle conventions (radians):
- *_mcp_flex, *_pip, *_dip, thumb_mcp, thumb_ip, thumb_cmc_flex, little_cup:
  positive = flexion (curling towards the palm).
- *_mcp_abd, thumb_cmc_abd: positive = towards the thumb (radial).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import quat as Q
from .xrhand import FINGERS, FORWARD, J, JOINT_COUNT, HandFrame

ANGLE_NAMES: tuple[str, ...] = (
    *(f"{f}_{k}" for f in FINGERS for k in ("mcp_flex", "mcp_abd", "pip", "dip")),
    "little_cup",
    "thumb_cmc_flex",
    "thumb_cmc_abd",
    "thumb_mcp",
    "thumb_ip",
)
A = {name: i for i, name in enumerate(ANGLE_NAMES)}
ANGLE_COUNT = len(ANGLE_NAMES)


@dataclass
class HandAngles:
    values: np.ndarray  # (ANGLE_COUNT,)

    @classmethod
    def zeros(cls) -> "HandAngles":
        return cls(np.zeros(ANGLE_COUNT))

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> "HandAngles":
        v = np.zeros(ANGLE_COUNT)
        for k, x in d.items():
            v[A[k]] = x
        return cls(v)

    def __getitem__(self, name: str) -> float:
        return float(self.values[A[name]])

    def as_dict(self) -> dict[str, float]:
        return {n: float(x) for n, x in zip(ANGLE_NAMES, self.values)}

    def lerp(self, other: "HandAngles", t: float) -> "HandAngles":
        return HandAngles(self.values + (other.values - self.values) * t)


# --- anatomy (right hand, wrist-local, metres) ------------------------------

# Base of each metacarpal (the CMC joint), relative to the wrist joint.
METACARPAL_BASE = {
    "index": np.array([-0.020, 0.0, -0.010]),
    "middle": np.array([-0.005, 0.0, -0.010]),
    "ring": np.array([0.010, 0.0, -0.010]),
    "little": np.array([0.022, -0.002, -0.012]),
}
# Rest splay of each metacarpal about +Y (positive = towards the thumb).
METACARPAL_SPLAY = {"index": 0.12, "middle": 0.03, "ring": -0.08, "little": -0.18}
# Bone lengths: metacarpal, proximal, intermediate, distal.
BONES = {
    "index": (0.068, 0.040, 0.024, 0.020),
    "middle": (0.066, 0.045, 0.028, 0.021),
    "ring": (0.060, 0.042, 0.027, 0.020),
    "little": (0.055, 0.033, 0.019, 0.018),
}
THUMB_BASE = np.array([-0.022, -0.012, -0.006])
THUMB_BONES = (0.045, 0.035, 0.030)  # metacarpal, proximal, distal
# Thumb metacarpal at rest: angled towards the thumb side and the palm, and
# rolled so its flexion axis faces across the palm.
THUMB_REST = Q.normalize(Q.mul(Q.mul(Q.ry(0.75), Q.rx(-0.35)), Q.rz(-0.9)))
PALM_OFFSET = np.array([0.0, 0.0, -0.045])


def finger_rest(finger: str) -> np.ndarray:
    return Q.ry(METACARPAL_SPLAY[finger])


def yx(abd: float, flex: float) -> np.ndarray:
    """Abduction about +Y, then flexion: flexion is a negative rotation about X
    (a positive one would lift -Z towards +Y, the back of the hand)."""
    return Q.mul(Q.ry(abd), Q.rx(-flex))


def forward(
    angles: HandAngles,
    wrist_pos=(0.0, 0.0, 0.0),
    wrist_quat=Q.IDENTITY,
    hand: str = "right",
    timestamp_us: int = 0,
    device_id: int = 0,
) -> HandFrame:
    """26 OpenXR joint poses (Z-up world) for the given angles and wrist pose."""
    pos = np.zeros((JOINT_COUNT, 3))
    ori = np.zeros((JOINT_COUNT, 4))
    pos[J["wrist"]] = 0.0
    ori[J["wrist"]] = Q.IDENTITY
    pos[J["palm"]] = PALM_OFFSET
    ori[J["palm"]] = Q.IDENTITY

    for f in FINGERS:
        lm, lp, li, ld = BONES[f]
        q = finger_rest(f)
        if f == "little":
            q = Q.mul(q, Q.rx(-angles["little_cup"]))
        p = METACARPAL_BASE[f].copy()
        names = [f"{f}_metacarpal", f"{f}_proximal", f"{f}_intermediate", f"{f}_distal", f"{f}_tip"]
        pos[J[names[0]]], ori[J[names[0]]] = p, q
        p = p + Q.rotate(q, FORWARD * lm)
        q = Q.mul(q, yx(angles[f"{f}_mcp_abd"], angles[f"{f}_mcp_flex"]))
        pos[J[names[1]]], ori[J[names[1]]] = p, q
        p = p + Q.rotate(q, FORWARD * lp)
        q = Q.mul(q, Q.rx(-angles[f"{f}_pip"]))
        pos[J[names[2]]], ori[J[names[2]]] = p, q
        p = p + Q.rotate(q, FORWARD * li)
        q = Q.mul(q, Q.rx(-angles[f"{f}_dip"]))
        pos[J[names[3]]], ori[J[names[3]]] = p, q
        p = p + Q.rotate(q, FORWARD * ld)
        pos[J[names[4]]], ori[J[names[4]]] = p, q

    lm, lp, ld = THUMB_BONES
    q = Q.mul(THUMB_REST, yx(angles["thumb_cmc_abd"], angles["thumb_cmc_flex"]))
    p = THUMB_BASE.copy()
    pos[J["thumb_metacarpal"]], ori[J["thumb_metacarpal"]] = p, q
    p = p + Q.rotate(q, FORWARD * lm)
    q = Q.mul(q, Q.rx(-angles["thumb_mcp"]))
    pos[J["thumb_proximal"]], ori[J["thumb_proximal"]] = p, q
    p = p + Q.rotate(q, FORWARD * lp)
    q = Q.mul(q, Q.rx(-angles["thumb_ip"]))
    pos[J["thumb_distal"]], ori[J["thumb_distal"]] = p, q
    p = p + Q.rotate(q, FORWARD * ld)
    pos[J["thumb_tip"]], ori[J["thumb_tip"]] = p, q

    local = HandFrame("right", pos, ori, timestamp_us, device_id, frame="zup")
    if hand == "left":
        local = mirror_frame(local)
    # Place in the world.
    R = Q.to_matrix(wrist_quat)
    world_pos = local.positions @ R.T + np.asarray(wrist_pos, dtype=float)
    world_ori = np.array([Q.normalize(Q.mul(wrist_quat, q)) for q in local.orientations])
    return HandFrame(hand, world_pos, world_ori, timestamp_us, device_id, frame="zup")


def mirror_quat(q) -> np.ndarray:
    """Reflect a rotation through the YZ plane (x -> -x)."""
    return np.array([q[0], -q[1], -q[2], q[3]])


def mirror_frame(f: HandFrame) -> HandFrame:
    """Mirror image through the world YZ plane: turns a left hand into a right
    hand (and back). Relative joint rotations mirror with it, so angles
    extracted from the result are those of the original hand."""
    pos = f.positions * np.array([-1.0, 1.0, 1.0])
    ori = np.array([mirror_quat(q) for q in f.orientations])
    other = "left" if f.hand == "right" else "right"
    return HandFrame(other, pos, ori, f.timestamp_us, f.device_id, frame=f.frame)


# --- named poses ---------------------------------------------------------------

def pose(**kw: float) -> HandAngles:
    return HandAngles.from_dict(kw)


def _curl(mcp: float, pip: float, dip: float, fingers=FINGERS) -> dict[str, float]:
    d = {}
    for f in fingers:
        d[f"{f}_mcp_flex"] = mcp
        d[f"{f}_pip"] = pip
        d[f"{f}_dip"] = dip
    return d


POSES: dict[str, HandAngles] = {
    "open": pose(thumb_cmc_abd=0.15),
    "spread": pose(
        index_mcp_abd=0.25, middle_mcp_abd=0.05, ring_mcp_abd=-0.2, little_mcp_abd=-0.35,
        thumb_cmc_abd=0.6, thumb_cmc_flex=-0.2,
    ),
    "fist": pose(**_curl(1.45, 1.6, 0.9), little_cup=0.3,
                 thumb_cmc_flex=0.7, thumb_cmc_abd=0.3, thumb_mcp=0.6, thumb_ip=0.5),
    # Power grasp sized for an egg (tuned in simulation: lifts it gently).
    "grasp": pose(**_curl(0.9, 1.0, 0.6), little_cup=0.3,
                  thumb_cmc_flex=0.9, thumb_cmc_abd=0.6, thumb_mcp=0.4, thumb_ip=0.4),
    "pinch": pose(index_mcp_flex=0.85, index_pip=0.75, index_dip=0.3,
                  **_curl(0.2, 0.3, 0.15, fingers=("middle", "ring", "little")),
                  thumb_cmc_flex=0.9, thumb_cmc_abd=0.6, thumb_mcp=0.35, thumb_ip=0.25),
    "point": pose(**_curl(1.4, 1.5, 0.8, fingers=("middle", "ring", "little")),
                  little_cup=0.3, thumb_cmc_flex=0.7, thumb_cmc_abd=0.3, thumb_mcp=0.5, thumb_ip=0.4),
    "peace": pose(**_curl(1.4, 1.5, 0.8, fingers=("ring", "little")),
                  index_mcp_abd=0.15, middle_mcp_abd=-0.1,
                  thumb_cmc_flex=0.8, thumb_cmc_abd=0.3, thumb_mcp=0.5, thumb_ip=0.4),
}
