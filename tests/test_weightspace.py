"""Weight-space programming: the arithmetic, the gradients and the training loop (no simulator)."""

import numpy as np

from rokoko_teleop.weightspace import _grads, forward, grasp_script, init_params, program, train


def test_program_is_task_arithmetic():
    rng = np.random.default_rng(0)
    base, L, C = (init_params([3, 4, 2], rng) for _ in range(3))
    params = {"theta_0": base, "theta_lifted": L, "theta_crushed": C}
    assert all(np.allclose(program(params, 0, 0)[k], base[k]) for k in base)
    assert all(np.allclose(program(params, 1, 0)[k], L[k]) for k in base)
    neg = program(params, 0, -1)
    assert all(np.allclose(neg[k], 2 * base[k] - C[k]) for k in base)


def test_gradients_match_finite_differences():
    rng = np.random.default_rng(1)
    p = init_params([5, 7, 3], rng)
    x, y = rng.normal(size=(9, 5)), rng.normal(size=(9, 3))
    _, g = _grads(p, x, y)
    eps = 1e-6
    for k in ("W0", "b1"):
        idx = (0, 0) if p[k].ndim == 2 else (0,)
        q = {kk: v.copy() for kk, v in p.items()}
        q[k][idx] += eps
        up = np.mean((forward(q, x) - y) ** 2)
        q[k][idx] -= 2 * eps
        down = np.mean((forward(q, x) - y) ** 2)
        assert abs((up - down) / (2 * eps) - g[k][idx]) < 1e-6


def test_training_fits_a_smooth_function():
    rng = np.random.default_rng(2)
    x = rng.uniform(-1, 1, (512, 2))
    y = np.stack([np.sin(2 * x[:, 0]), x[:, 0] * x[:, 1]], 1)
    p, loss = train(init_params([2, 32, 2], rng), x, y, 800, 1e-2, rng, batch=128)
    assert loss < 0.01


def test_grasp_script_squeezes_after_closing():
    keys = grasp_script(0.7)
    assert keys[2].pose == "grasp"  # close first, then squeeze: blending straight to a fist pushes the egg away
    assert not isinstance(keys[3].pose, str)


def test_setup_round_trip(tmp_path):
    from rokoko_teleop.weightspace import Setup, eval_offsets

    s = Setup(obs="state", egg_range_m=0.015, dart_m=0.006)
    s.save(tmp_path)
    assert Setup.load(tmp_path) == s
    offs = eval_offsets(s, 20)
    assert len(offs) == 20 and max(abs(v) for o in offs for v in o) <= 0.015
    assert len(eval_offsets(Setup())) == 5  # fixed egg: the 5 small offsets
