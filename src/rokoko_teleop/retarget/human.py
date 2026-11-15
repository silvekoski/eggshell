"""OpenXR hand poses -> canonical HandAngles.

Each angle comes from the rotation of a bone relative to its parent bone,
so it is independent of where the hand is and which way it faces (and of
the uncalibrated yaw). Only the thumb CMC and little-finger cupping are
measured against an anatomical rest pose; `NeutralCalibration` removes
the per-person offset there (and anywhere else) from one flat-hand sample.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .. import quat as Q
from ..hand_model import ANGLE_COUNT, POSES, THUMB_REST, HandAngles, finger_rest, mirror_frame
from ..xrhand import FINGERS, FORWARD, J, HandFrame


def relative(q_parent, q_child) -> np.ndarray:
    return Q.mul(Q.conj(q_parent), q_child)


def decompose_yx(q_rel) -> tuple[float, float]:
    """(abduction, flexion) of a rotation built as Ry(abd) * Rx(-flex).

    Reads where the bone's forward axis ends up: d = q_rel * (0, 0, -1)
    = (-cos f sin a, -sin f, -cos f cos a). Exact for |flex| <= 90 degrees.
    """
    d = Q.rotate(q_rel, FORWARD)
    abd = math.atan2(-d[0], -d[2])
    flex = math.atan2(-d[1], math.hypot(d[0], d[2]))
    return abd, flex


def hinge_flex(q_rel) -> float:
    """Flexion of a hinge (rotation about local X), full -180..180 range."""
    d = Q.rotate(q_rel, FORWARD)
    return math.atan2(-d[1], -d[2])


def extract_angles(frame: HandFrame) -> HandAngles:
    """Canonical joint angles from 26 OpenXR joint poses (any hand, any frame)."""
    f = mirror_frame(frame) if frame.hand == "left" else frame
    o = f.orientations
    out: dict[str, float] = {}
    for finger in FINGERS:
        meta = o[J[f"{finger}_metacarpal"]]
        prox = o[J[f"{finger}_proximal"]]
        inter = o[J[f"{finger}_intermediate"]]
        dist = o[J[f"{finger}_distal"]]
        abd, flex = decompose_yx(relative(meta, prox))
        out[f"{finger}_mcp_abd"] = abd
        out[f"{finger}_mcp_flex"] = flex
        out[f"{finger}_pip"] = hinge_flex(relative(prox, inter))
        out[f"{finger}_dip"] = hinge_flex(relative(inter, dist))

    wrist = o[J["wrist"]]
    # Little-finger cupping: the metacarpal's flexion against its rest splay.
    rest = Q.mul(wrist, finger_rest("little"))
    _, cup = decompose_yx(relative(rest, o[J["little_metacarpal"]]))
    out["little_cup"] = cup

    thumb_rest = Q.mul(wrist, THUMB_REST)
    abd, flex = decompose_yx(relative(thumb_rest, o[J["thumb_metacarpal"]]))
    out["thumb_cmc_abd"] = abd
    out["thumb_cmc_flex"] = flex
    out["thumb_mcp"] = hinge_flex(relative(o[J["thumb_metacarpal"]], o[J["thumb_proximal"]]))
    out["thumb_ip"] = hinge_flex(relative(o[J["thumb_proximal"]], o[J["thumb_distal"]]))
    return HandAngles.from_dict(out)


@dataclass
class NeutralCalibration:
    """Per-person zero: angles measured while the operator holds a flat,
    relaxed hand become the robot's "open" pose."""

    offset: np.ndarray = field(default_factory=lambda: np.zeros(ANGLE_COUNT))
    # What a flat hand should read as (a relaxed thumb is slightly abducted).
    target: np.ndarray = field(default_factory=lambda: POSES["open"].values.copy())

    def capture(self, flat: HandAngles) -> None:
        self.offset = flat.values - self.target

    def apply(self, a: HandAngles) -> HandAngles:
        return HandAngles(a.values - self.offset)


class AngleFilter:
    """One-euro-style low-pass: smooth when still, responsive when moving.
    Glove IMU jitter otherwise shows up as robot finger tremor."""

    def __init__(self, min_cutoff_hz: float = 2.0, beta: float = 0.5, d_cutoff_hz: float = 1.0):
        self.min_cutoff = min_cutoff_hz
        self.beta = beta
        self.d_cutoff = d_cutoff_hz
        self._x: np.ndarray | None = None
        self._dx = np.zeros(ANGLE_COUNT)

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, a: HandAngles, dt: float) -> HandAngles:
        x = a.values
        if self._x is None or dt <= 0:
            self._x = x.copy()
            return HandAngles(x.copy())
        dx = (x - self._x) / dt
        ad = self._alpha(self.d_cutoff, dt)
        self._dx = ad * dx + (1 - ad) * self._dx
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        tau = 1.0 / (2 * math.pi * cutoff)
        alpha = 1.0 / (1.0 + tau / dt)
        self._x = alpha * x + (1 - alpha) * self._x
        return HandAngles(self._x.copy())
