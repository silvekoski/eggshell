"""The teleoperation pipeline: glove frame -> robot command.

    HandFrame (Z-up or raw xr_base)
      -> yaw calibration (fingers forward = +X)
      -> HandAngles (extract) -> neutral calibration -> one-euro filter
      -> Shadow controls (sim)  and  Inspire commands (real hand)
      -> wrist pose -> workspace mapping -> mocap target
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .hand_model import HandAngles
from .retarget.human import AngleFilter, NeutralCalibration, extract_angles
from .retarget.inspire import inspire_command
from .retarget.shadow import ShadowRetargeter
from .xrhand import HandFrame, XrBaseToZUp, yaw_to_face


@dataclass
class Command:
    ctrl: np.ndarray  # Shadow actuator targets
    wrist_pos: np.ndarray  # scene coordinates
    wrist_quat: np.ndarray  # OpenXR wrist orientation (x, y, z, w), Z-up
    angles: HandAngles  # filtered, calibrated
    raw_angles: HandAngles
    inspire: list[int]
    frame: HandFrame  # the yaw-corrected glove frame


@dataclass
class WristMapper:
    """absolute: glove positions are already scene coordinates (synthetic data,
    or a Coil Pro origin placed at the table). relative: the hand position at
    calibration maps to `center`, motion is scaled by `scale`."""

    mode: str = "absolute"
    scale: float = 1.0
    center: np.ndarray = field(default_factory=lambda: np.array([-0.075, 0.0, 0.20]))
    anchor: np.ndarray | None = None
    floor_z: float = 0.06  # keep the palm above the table

    def __call__(self, p: np.ndarray) -> np.ndarray:
        if self.mode == "absolute":
            out = np.asarray(p, dtype=float).copy()
        else:
            if self.anchor is None:
                self.anchor = np.asarray(p, dtype=float).copy()
            out = self.center + self.scale * (np.asarray(p) - self.anchor)
        out[2] = max(out[2], self.floor_z)
        return out


@dataclass
class Teleop:
    wrist: WristMapper = field(default_factory=WristMapper)
    yaw_rad: float = 0.0
    neutral: NeutralCalibration = field(default_factory=NeutralCalibration)
    shadow: ShadowRetargeter = field(default_factory=ShadowRetargeter)
    smooth: bool = True

    def __post_init__(self) -> None:
        self._filter = AngleFilter()

    def to_scene(self, f: HandFrame) -> HandFrame:
        return XrBaseToZUp(self.yaw_rad).apply(f)

    def calibrate(self, f: HandFrame, facing_rad: float = 0.0) -> None:
        """Operator holds a flat hand, level, fingers pointing 'forward'.
        Sets yaw (forward = +X in the scene), the per-person angle zero, and
        the wrist anchor for relative mode."""
        zup = XrBaseToZUp(0.0).apply(f)
        self.yaw_rad = yaw_to_face(zup, facing_rad)
        scene = self.to_scene(f)
        self.neutral.capture(extract_angles(scene))
        self.wrist.anchor = scene.positions[1].copy()  # wrist joint
        self._filter = AngleFilter()

    def process(self, f: HandFrame, dt: float) -> Command:
        scene = self.to_scene(f)
        raw = extract_angles(scene)
        a = self.neutral.apply(raw)
        if self.smooth:
            a = self._filter(a, dt)
        wrist_pos, wrist_quat = scene.pose("wrist")
        return Command(
            ctrl=self.shadow(a),
            wrist_pos=self.wrist(wrist_pos),
            wrist_quat=wrist_quat.copy(),
            angles=a,
            raw_angles=raw,
            inspire=inspire_command(a),
            frame=scene,
        )
