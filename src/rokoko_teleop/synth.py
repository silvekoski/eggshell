"""A scripted "operator": glove frames for a pick-up-the-egg demonstration
plus a few gestures, generated with the parametric hand model.

It stands in for a person wearing Smartgloves, so the whole pipeline
(RGMP encoding, retargeting, simulation, recording) runs with no hardware.
Positions are in scene coordinates (Z-up, metres, egg on the table at the
origin), i.e. what a calibrated live stream looks like after workspace
mapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import quat as Q
from .hand_model import POSES, HandAngles, forward
from .xrhand import HandFrame


def palm_down(pitch: float = 0.0, roll: float = 0.0, yaw: float = 0.0) -> np.ndarray:
    """OpenXR wrist orientation (Z-up) for a palm-down hand, fingers along +X.
    pitch > 0 tips the fingers down; roll > 0 rolls the thumb side up."""
    base = Q.from_matrix(np.array([[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]))
    tilt = Q.mul(Q.rz(yaw), Q.mul(Q.ry(pitch), Q.rx(roll)))
    return Q.normalize(Q.mul(tilt, base))


@dataclass
class Key:
    t: float
    pos: tuple[float, float, float]
    pose: str | HandAngles
    pitch: float = 0.0
    roll: float = 0.0
    yaw: float = 0.0

    def angles(self) -> HandAngles:
        return POSES[self.pose] if isinstance(self.pose, str) else self.pose


def _smooth(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# Wrist positions (tuned in simulation): the egg ends up under the Shadow
# palm, between thumb and fingers.
_HOVER = (-0.07, 0.0, 0.20)
_GRASP = (-0.07, 0.0, 0.10)
_LIFT = (-0.07, 0.0, 0.21)

EGG_DEMO: tuple[Key, ...] = (
    Key(0.0, _HOVER, "open"),
    Key(1.0, _HOVER, "spread"),
    Key(1.8, _HOVER, "open"),
    Key(3.3, _GRASP, "open"),
    Key(4.8, _GRASP, "grasp"),
    Key(5.3, _GRASP, "grasp"),
    Key(6.8, _LIFT, "grasp"),
    Key(7.8, (-0.07, 0.06, 0.21), "grasp", roll=0.2),
    Key(8.8, (-0.07, -0.06, 0.21), "grasp", roll=-0.2),
    Key(9.8, _LIFT, "grasp"),
    Key(11.3, _GRASP, "grasp"),
    Key(12.0, _GRASP, "open"),
    Key(13.2, _HOVER, "open"),
    Key(14.0, _HOVER, "point"),
    Key(14.8, _HOVER, "peace"),
    Key(15.6, _HOVER, "pinch"),
    Key(16.4, _HOVER, "fist"),
    Key(17.2, _HOVER, "open"),
)

# The same approach, but the operator squeezes into a fist: a labelled
# negative example (the egg cracks).
EGG_CRUSH: tuple[Key, ...] = (
    Key(0.0, _HOVER, "open"),
    Key(1.5, _GRASP, "open"),
    Key(3.0, _GRASP, "grasp"),
    Key(3.6, _GRASP, "fist"),
    Key(4.4, _GRASP, "fist"),
    Key(5.6, _LIFT, "fist"),
    Key(6.4, _LIFT, "open"),
)

# A clean grasp and lift, then the operator opens the hand at height: the egg
# falls. The threshold label still says "lifted" (it rose >= 5 cm); this is
# the case the Nemotron review exists for.
EGG_DROP: tuple[Key, ...] = (
    Key(0.0, _HOVER, "open"),
    Key(1.5, _GRASP, "open"),
    Key(3.0, _GRASP, "grasp"),
    Key(3.5, _GRASP, "grasp"),
    Key(5.0, _LIFT, "grasp"),
    Key(6.0, _LIFT, "grasp"),
    Key(6.4, _LIFT, "open"),
    Key(8.0, _LIFT, "open"),
)

# The operator closes the hand 5 cm too high: the fingers brush the egg and
# it stays on the table.
_SHORT = (-0.07, 0.0, 0.15)
EGG_MISS: tuple[Key, ...] = (
    Key(0.0, _HOVER, "open"),
    Key(1.5, _SHORT, "open"),
    Key(3.0, _SHORT, "grasp"),
    Key(3.5, _SHORT, "grasp"),
    Key(5.0, _LIFT, "grasp"),
    Key(6.0, _LIFT, "open"),
)

SCRIPTS = {"egg": EGG_DEMO, "crush": EGG_CRUSH, "drop": EGG_DROP, "miss": EGG_MISS}


class ScriptedOperator:
    """Interpolates a key-pose script into glove frames."""

    def __init__(self, keys=EGG_DEMO, hand: str = "right", tremor_rad: float = 0.0, seed: int = 0):
        self.keys = list(keys)
        self.hand = hand
        self.duration = self.keys[-1].t
        self.tremor = tremor_rad
        self._rng = np.random.default_rng(seed)

    def frame_at(self, t: float) -> HandFrame:
        ks = self.keys
        if t <= ks[0].t:
            a, b, x = ks[0], ks[0], 0.0
        elif t >= ks[-1].t:
            a, b, x = ks[-1], ks[-1], 0.0
        else:
            i = max(j for j in range(len(ks)) if ks[j].t <= t)
            a, b = ks[i], ks[i + 1]
            x = _smooth((t - a.t) / (b.t - a.t))
        angles = a.angles().lerp(b.angles(), x)
        if self.tremor:
            angles = HandAngles(angles.values + self._rng.normal(0, self.tremor, angles.values.shape))
        pos = np.array(a.pos) + (np.array(b.pos) - np.array(a.pos)) * x
        qa = palm_down(a.pitch, a.roll, a.yaw)
        qb = palm_down(b.pitch, b.roll, b.yaw)
        q = Q.slerp(qa, qb, x)
        return forward(angles, pos, q, hand=self.hand, timestamp_us=int(t * 1e6), device_id=1)


def frames(op: ScriptedOperator, rate_hz: float = 60.0):
    n = int(math.floor(op.duration * rate_hz)) + 1
    for i in range(n):
        yield op.frame_at(i / rate_hz)
