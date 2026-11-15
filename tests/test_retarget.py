"""Retargeting maths: OpenXR joint poses -> canonical angles -> robot commands."""

import math

import numpy as np
import pytest

from rokoko_teleop import quat as Q
from rokoko_teleop.fake_solver import to_xr_base
from rokoko_teleop.hand_model import ANGLE_NAMES, POSES, HandAngles, forward, mirror_frame
from rokoko_teleop.retarget.human import (
    AngleFilter,
    NeutralCalibration,
    decompose_yx,
    extract_angles,
    hinge_flex,
)
from rokoko_teleop.retarget.inspire import inspire_command
from rokoko_teleop.retarget.shadow import HI, IDX, LO, ShadowRetargeter
from rokoko_teleop.xrhand import XrBaseToZUp, wrist_heading, yaw_to_face

RNG = np.random.default_rng(7)


def random_angles() -> HandAngles:
    lo = {"mcp_flex": -0.2, "mcp_abd": -0.3, "pip": 0.0, "dip": 0.0}
    hi = {"mcp_flex": 1.5, "mcp_abd": 0.3, "pip": 1.9, "dip": 1.4}
    d = {}
    for name in ANGLE_NAMES:
        kind = name.split("_", 1)[1]
        if kind in lo:
            d[name] = RNG.uniform(lo[kind], hi[kind])
    d.update(little_cup=RNG.uniform(0, 0.5), thumb_cmc_flex=RNG.uniform(-0.3, 1.0),
             thumb_cmc_abd=RNG.uniform(-0.2, 0.8), thumb_mcp=RNG.uniform(0, 1.0), thumb_ip=RNG.uniform(-0.2, 1.3))
    return HandAngles.from_dict(d)


def random_quat() -> np.ndarray:
    return Q.normalize(RNG.normal(size=4))


def test_decompose_inverts_abduction_then_flexion():
    for abd in (-0.4, 0.0, 0.3):
        for flex in (-0.3, 0.0, 0.8, 1.5):
            a, f = decompose_yx(Q.mul(Q.ry(abd), Q.rx(-flex)))
            assert a == pytest.approx(abd, abs=1e-9)
            assert f == pytest.approx(flex, abs=1e-9)


def test_hinge_flex_covers_hyperflexion_past_90_degrees():
    assert hinge_flex(Q.rx(-2.0)) == pytest.approx(2.0)
    assert hinge_flex(Q.rx(0.3)) == pytest.approx(-0.3)  # hyperextension


@pytest.mark.parametrize("name", sorted(POSES))
@pytest.mark.parametrize("hand", ["right", "left"])
def test_named_poses_round_trip(name, hand):
    p = POSES[name]
    f = forward(p, wrist_pos=(0.3, -0.1, 1.2), wrist_quat=random_quat(), hand=hand)
    assert np.allclose(extract_angles(f).values, p.values, atol=1e-9)


def test_random_poses_round_trip_anywhere_in_space():
    for _ in range(200):
        p = random_angles()
        f = forward(p, wrist_pos=RNG.uniform(-1, 1, 3), wrist_quat=random_quat(), hand=RNG.choice(["left", "right"]))
        assert np.allclose(extract_angles(f).values, p.values, atol=1e-8)


def test_angles_survive_the_raw_solver_frame_and_float32_wire():
    """Synthetic Z-up -> raw xr_base (Y-up) -> float32 -> back to Z-up with a yaw."""
    p = POSES["pinch"]
    raw = to_xr_base(forward(p, (0.1, 0.2, 0.3), random_quat()))
    raw.positions = raw.positions.astype(np.float32).astype(float)
    raw.orientations = raw.orientations.astype(np.float32).astype(float)
    back = XrBaseToZUp(yaw_rad=1.234).apply(raw)
    assert np.allclose(extract_angles(back).values, p.values, atol=1e-5)


def test_left_hand_is_a_mirror_image():
    p = POSES["spread"]
    right = forward(p, hand="right")
    left = forward(p, hand="left")
    # Thumb on -X for a right hand and +X for a left hand (OpenXR convention).
    assert right.pose("thumb_tip")[0][0] < 0 < left.pose("thumb_tip")[0][0]
    assert np.allclose(mirror_frame(left).positions, right.positions)


def test_yaw_calibration_points_the_fingers_forward():
    from rokoko_teleop.synth import palm_down

    for heading in (-2.5, -0.4, 0.0, 1.0, 3.0):
        f = forward(POSES["open"], wrist_quat=palm_down(yaw=heading))
        assert wrist_heading(f) == pytest.approx(heading, abs=1e-9)
        yaw = yaw_to_face(f)
        assert wrist_heading(XrBaseToZUp(yaw).apply(f)) == pytest.approx(0.0, abs=1e-9)


def test_neutral_calibration_zeroes_a_persons_flat_hand():
    offset = RNG.normal(0, 0.1, len(ANGLE_NAMES))  # this person's sensor/anatomy bias
    cal = NeutralCalibration()
    cal.capture(HandAngles(POSES["open"].values + offset))  # their flat hand
    assert np.allclose(cal.apply(HandAngles(POSES["open"].values + offset)).values, POSES["open"].values)
    fist = HandAngles(POSES["fist"].values + offset)
    assert np.allclose(cal.apply(fist).values, POSES["fist"].values)


def test_filter_settles_on_a_step_and_damps_jitter():
    filt = AngleFilter()
    target = POSES["grasp"]
    out = filt(POSES["open"], 1 / 60)
    for _ in range(120):
        out = filt(target, 1 / 60)
    assert np.allclose(out.values, target.values, atol=1e-3)
    noisy = [HandAngles(target.values + RNG.normal(0, 0.05, target.values.shape)) for _ in range(120)]
    outs = np.array([filt(n, 1 / 60).values for n in noisy])
    assert outs.std(axis=0).mean() < 0.5 * 0.05


def test_shadow_map_stays_within_joint_limits():
    shadow = ShadowRetargeter()
    for _ in range(200):
        c = shadow(random_angles())
        assert np.all(c >= LO - 1e-12) and np.all(c <= HI + 1e-12)


def test_shadow_map_curls_fingers_for_a_fist_and_opens_for_open():
    shadow = ShadowRetargeter()
    fist, open_ = shadow(POSES["fist"]), shadow(POSES["open"])
    for p in ("FF", "MF", "RF", "LF"):
        assert fist[IDX[f"rh_A_{p}J3"]] > 1.3 and open_[IDX[f"rh_A_{p}J3"]] == pytest.approx(0.0)
        assert fist[IDX[f"rh_A_{p}J0"]] > 2.0 and open_[IDX[f"rh_A_{p}J0"]] == pytest.approx(0.0)
    assert fist[IDX["rh_A_THJ4"]] > open_[IDX["rh_A_THJ4"]]


def test_shadow_spread_moves_index_and_little_apart():
    c = ShadowRetargeter()(POSES["spread"])
    # Menagerie knuckle axes: index/middle J4 negative = towards the thumb,
    # ring/little J4 positive = towards the thumb (see test_sim for the check in MuJoCo).
    assert c[IDX["rh_A_FFJ4"]] < 0
    assert c[IDX["rh_A_LFJ4"]] < 0


def test_inspire_command_range_and_direction():
    assert inspire_command(POSES["open"]) == [1000] * 6
    fist = inspire_command(POSES["fist"])
    assert all(0 <= v <= 1000 for v in fist)
    assert max(fist[:4]) < 50  # fingers closed
    point = inspire_command(POSES["point"])
    assert point[3] == 1000 and max(point[:3]) < 100  # index out, others curled
    for _ in range(100):
        assert all(0 <= v <= 1000 for v in inspire_command(random_angles()))


def test_forward_kinematics_bone_lengths_are_preserved():
    f = forward(random_angles(), wrist_quat=random_quat())
    d = np.linalg.norm(f.pose("index_intermediate")[0] - f.pose("index_proximal")[0])
    assert d == pytest.approx(0.040)
    assert math.isclose(np.linalg.norm(f.orientations, axis=1).min(), 1.0, abs_tol=1e-9)
