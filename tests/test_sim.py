"""Simulation checks against the real Menagerie Shadow hand model.
Skipped when the model has not been fetched (scripts/fetch_menagerie.sh)."""

import mujoco
import numpy as np
import pytest

from rokoko_teleop.hand_model import POSES
from rokoko_teleop.retarget.shadow import ABD_SIGN, ACTUATORS, CTRL_RANGE, FINGER_PREFIX, ShadowRetargeter
from rokoko_teleop.sim import TeleopSim, menagerie_dir

pytestmark = pytest.mark.skipif(
    not (menagerie_dir() / "shadow_hand" / "right_hand.xml").exists(),
    reason="Menagerie shadow_hand not fetched",
)


@pytest.fixture(scope="module")
def sim():
    return TeleopSim()


def body(sim, name):
    return sim.data.xpos[mujoco.mj_name2id(sim.model, mujoco.mjtObj.mjOBJ_BODY, name)].copy()


def test_ctrl_ranges_match_the_model(sim):
    for i, name in enumerate(ACTUATORS):
        a = sim._ids["act"][i]
        assert tuple(sim.model.actuator_ctrlrange[a]) == pytest.approx(CTRL_RANGE[name], abs=1e-4)


def test_abduction_signs_move_fingers_towards_the_thumb(sim):
    m, d = sim.model, sim.data
    toward_thumb_palm = -sim.xr_in_palm[:, 0]
    for finger, p in FINGER_PREFIX.items():
        qa = m.jnt_qposadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, f"rh_{p}J4")]
        tip = f"rh_{p.lower()}distal"
        saved = d.qpos.copy()
        mujoco.mj_forward(m, d)
        p0 = body(sim, tip)
        d.qpos[qa] = 0.2 * ABD_SIGN[finger]
        mujoco.mj_forward(m, d)
        moved = body(sim, tip) - p0
        d.qpos[:] = saved
        mujoco.mj_forward(m, d)
        R = d.xmat[sim._ids["palm"]].reshape(3, 3)
        assert (R.T @ moved) @ toward_thumb_palm > 0.005, finger


def _settle(sim, pose, seconds=1.0):
    sim.reset()
    sim.set_ctrl(ShadowRetargeter()(pose))
    for _ in range(int(seconds / 0.02)):
        sim.step(0.02)


def test_pinch_brings_thumb_and_index_together(sim):
    _settle(sim, POSES["open"])
    open_gap = np.linalg.norm(body(sim, "rh_thdistal") - body(sim, "rh_ffdistal"))
    _settle(sim, POSES["pinch"])
    pinch_gap = np.linalg.norm(body(sim, "rh_thdistal") - body(sim, "rh_ffdistal"))
    assert pinch_gap < 0.6 * open_gap


def test_wrist_target_places_the_palm(sim):
    from rokoko_teleop.synth import palm_down

    sim.reset()
    target = np.array([0.05, 0.02, 0.22])
    sim.set_wrist(target, palm_down())
    sim._snap_root_to_target()
    for _ in range(25):
        sim.step(0.02)
    assert np.linalg.norm(sim.data.xpos[sim._ids["palm"]] - target) < 0.01
    # Fingers point along +X, back of the hand up.
    R = sim.data.xmat[sim._ids["palm"]].reshape(3, 3)
    xr = R @ sim.xr_in_palm  # OpenXR axes in the world
    assert xr[:, 2] @ [-1, 0, 0] > 0.99  # -Z (fingers) along +X
    assert xr[:, 1] @ [0, 0, 1] > 0.99  # +Y (dorsal) up


def test_scripted_operator_lifts_the_egg_gently_and_a_squeeze_crushes_it(sim, tmp_path):
    from rokoko_teleop.runner import run_headless
    from rokoko_teleop.sources import SyntheticSource
    from rokoko_teleop.synth import EGG_CRUSH, EGG_DEMO, ScriptedOperator
    from rokoko_teleop.teleop import Teleop

    sim.reset()
    good = run_headless(SyntheticSource(ScriptedOperator(EGG_DEMO[:12])), Teleop(), sim=sim,
                        dataset=tmp_path, log_every_s=0)
    assert good.label["outcome"] == "lifted", good.label
    assert good.label["max_lift_m"] > 0.08
    sim.reset()
    bad = run_headless(SyntheticSource(ScriptedOperator(EGG_CRUSH)), Teleop(), sim=sim,
                       dataset=tmp_path, log_every_s=0)
    assert bad.label["outcome"] == "crushed", bad.label
    ep = np.load(good.episode)
    assert ep["action"].shape[1] == 20 and ep["glove"].shape[1:] == (26, 7)
    assert (tmp_path / "episodes.jsonl").read_text().count("\n") == 2
