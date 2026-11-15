"""Weight-space programming on Egg Shell demonstrations.

The labelled episodes give us split datasets for free: lifted demonstrations
and crushed demonstrations. That makes task arithmetic possible:

  theta_0         behaviour cloning on ALL demonstrations (the base policy)
  theta_lifted    theta_0 fine-tuned on the lifted demonstrations only
  theta_crushed   theta_0 fine-tuned on the crushed demonstrations only
  tau_L = theta_lifted - theta_0      tau_C = theta_crushed - theta_0

A "program" is a point in weight space, theta_0 + a * tau_L + c * tau_C, and
we run each program closed-loop in the simulator and measure what it does:
peak grip force, crush rate, lift. No gradient step happens at program time:
behaviour is edited by adding and subtracting weights.

Everything is NumPy (a 2-layer MLP with a hand-written Adam), so it runs on a
laptop CPU in minutes. Glove input for the demonstrations is the scripted
operator, as in the rest of this repository.

  teleop weightspace gen     # demonstrations with a spread of grip strengths
  teleop weightspace train   # theta_0, theta_lifted, theta_crushed
  teleop weightspace eval    # programs in weight space -> results.json, results.md
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .hand_model import POSES
from .recorder import label_episode
from .sim import SceneConfig, TeleopSim
from .sources import SyntheticSource
from .synth import Key, ScriptedOperator
from .teleop import Teleop

EPISODE_S = 8.0
CONTROL_HZ = 60.0
N_STEPS = int(EPISODE_S * CONTROL_HZ)


# --- demonstrations -----------------------------------------------------------

def grasp_script(grip: float, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> tuple[Key, ...]:
    """Reach, close the hand to the "grasp" pose, squeeze by `grip` (0 = no
    squeeze, 1 = into a full fist), lift, hold, set down, open. dx/dy/dz shift where the
    operator closes the hand (operator variability)."""
    pose = POSES["grasp"].lerp(POSES["fist"], grip)
    hover = (-0.07 + dx, dy, 0.20)
    grasp = (-0.07 + dx, dy, 0.10 + dz)
    lift = (-0.07 + dx, dy, 0.21)
    return (
        Key(0.0, hover, "open"),
        Key(1.5, grasp, "open"),
        Key(3.0, grasp, "grasp"),
        Key(3.5, grasp, pose),
        Key(4.9, lift, pose),
        Key(5.8, lift, pose),
        Key(7.0, grasp, pose),
        Key(7.6, grasp, "open"),
        Key(EPISODE_S, hover, "open"),
    )


def phase_features(t: float) -> np.ndarray:
    p = t / EPISODE_S
    return np.array([p, *(f(2 * np.pi * k * p) for k in (1, 2, 3) for f in (np.sin, np.cos))])


def observation(t: float, sim: TeleopSim, mode: str = "phase") -> np.ndarray:
    """Policy input.
    "phase": the episode phase only (a time-indexed, open-loop policy).
    "state": the phase plus where the egg is and where the palm is (closed-loop:
    the policy must find an egg that moves between episodes)."""
    if mode == "phase":
        return phase_features(t)
    egg = sim.data.xpos[sim._ids["egg"]]
    palm = sim.data.xpos[sim._ids["palm"]]
    return np.concatenate([phase_features(t), egg, palm, egg - palm])


@dataclass
class Setup:
    """How the demonstrations and the evaluation vary. Saved as setup.json."""
    obs: str = "phase"
    egg_range_m: float = 0.0  # the egg moves +-this in x and y between episodes
    dart_m: float = 0.0  # DART: noise on the EXECUTED wrist position while the clean action is recorded
    aim_noise_m: float = 0.003  # operator misses the egg centre by up to this

    def save(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        (d / "setup.json").write_text(json.dumps(self.__dict__))

    @classmethod
    def load(cls, d: Path) -> "Setup":
        f = d / "setup.json"
        return cls(**json.loads(f.read_text())) if f.exists() else cls()


def _demo(args) -> dict:
    seed, grip, dx, dy, dz, tremor, egg_xy, setup = args
    op = ScriptedOperator(grasp_script(grip, egg_xy[0] + dx, egg_xy[1] + dy, dz), tremor_rad=tremor, seed=seed)
    src, tele = SyntheticSource(op), Teleop()
    sim = TeleopSim(SceneConfig(egg_pos=(egg_xy[0], egg_xy[1], 0.0)))
    rng = np.random.default_rng(seed + 7)
    noise = np.zeros(3)
    obs, act, quats, force, lift = [], [], [], [], []
    first = True
    for i in range(N_STEPS):
        t = i / CONTROL_HZ
        cmd = tele.process(src.get(t), 1 / CONTROL_HZ)
        o = observation(t, sim, setup.obs)
        sim.set_ctrl(cmd.ctrl)
        if setup.dart_m:  # smooth (Ornstein-Uhlenbeck) wrist noise, executed but not recorded
            noise += -noise * (1 / CONTROL_HZ) / 0.3 + setup.dart_m * np.sqrt(2 / 0.3 / CONTROL_HZ) * rng.normal(size=3)
        # Only during the approach: fade out before the hand closes (t = 3 s), so the
        # expert still grasps cleanly but the policy sees off-course states to correct.
        env = float(np.clip((2.8 - t) / 0.8, 0.0, 1.0))
        sim.set_wrist(cmd.wrist_pos + env * noise, cmd.wrist_quat)
        if first:
            sim._snap_root_to_target()
            first = False
        egg = sim.step(1 / CONTROL_HZ)
        obs.append(o)
        act.append(np.concatenate([cmd.ctrl, cmd.wrist_pos]))
        quats.append(cmd.wrist_quat)
        force.append(egg.force_n)
        lift.append(egg.lifted_m)
    label = label_episode(max(lift), lift[-1], sim.cracked, sim.peak_force, sim.config.crack_force_n)
    return {"seed": seed, "grip": grip, "obs": np.array(obs), "act": np.array(act),
            "quat": np.array(quats), "force": np.array(force), "lift": np.array(lift), "label": label}


def generate(out: Path, n: int = 96, workers: int = 16, seed: int = 0, setup: Setup | None = None) -> dict:
    setup = setup or Setup()
    setup.save(out)
    rng = np.random.default_rng(seed)
    a, r = setup.aim_noise_m, setup.egg_range_m
    jobs = [(seed * 10_000 + i, float(rng.uniform(0.0, 1.0)), *rng.uniform(-a, a, 2),
             float(rng.uniform(-0.003, 0.003)), float(rng.uniform(0.0, 0.015)),
             tuple(rng.uniform(-r, r, 2)) if r else (0.0, 0.0), setup) for i in range(n)]
    t0 = time.monotonic()
    with ProcessPoolExecutor(workers) as ex:
        demos = list(ex.map(_demo, jobs))
    out.mkdir(parents=True, exist_ok=True)
    labels = [d["label"] for d in demos]
    np.savez_compressed(
        out / "demos.npz",
        obs=np.stack([d["obs"] for d in demos]), act=np.stack([d["act"] for d in demos]),
        quat=np.stack([d["quat"] for d in demos]).mean(axis=(0, 1)),
        grip=np.array([d["grip"] for d in demos]),
        outcome=np.array([lb["outcome"] for lb in labels]),
        peak_force=np.array([lb["peak_force_n"] for lb in labels]),
        max_lift=np.array([lb["max_lift_m"] for lb in labels]),
    )
    counts = {k: sum(lb["outcome"] == k for lb in labels) for k in ("lifted", "crushed", "not_lifted")}
    summary = {"episodes": n, "counts": counts, "setup": setup.__dict__, "seconds": round(time.monotonic() - t0, 1)}
    (out / "demos.json").write_text(json.dumps(
        {**summary, "episodes_detail": [{"seed": d["seed"], "grip": round(d["grip"], 3), **d["label"]}
                                        for d in demos]}, indent=1))
    return summary


# --- policy: a 2-layer MLP in NumPy ---------------------------------------------

@dataclass
class Norm:
    mu: np.ndarray
    sd: np.ndarray

    def __call__(self, x):
        return (x - self.mu) / self.sd

    def inv(self, y):
        return y * self.sd + self.mu


def init_params(sizes: list[int], rng) -> dict[str, np.ndarray]:
    p = {}
    for i, (a, b) in enumerate(zip(sizes[:-1], sizes[1:])):
        p[f"W{i}"] = rng.normal(0, np.sqrt(1.0 / a), (a, b))
        p[f"b{i}"] = np.zeros(b)
    return p


def forward(p: dict, x: np.ndarray, cache: list | None = None) -> np.ndarray:
    n = len(p) // 2
    h = x
    for i in range(n):
        z = h @ p[f"W{i}"] + p[f"b{i}"]
        if cache is not None:
            cache.append(h)
        h = np.tanh(z) if i < n - 1 else z
    return h


def _grads(p: dict, x: np.ndarray, y: np.ndarray) -> tuple[float, dict]:
    cache: list = []
    out = forward(p, x, cache)
    n = len(p) // 2
    err = out - y
    loss = float(np.mean(err ** 2))
    g, d = {}, 2 * err / err.size
    for i in reversed(range(n)):
        h = cache[i]
        g[f"W{i}"] = h.T @ d
        g[f"b{i}"] = d.sum(0)
        if i:
            d = (d @ p[f"W{i}"].T) * (1 - h ** 2)
    return loss, g


def train(p: dict, x: np.ndarray, y: np.ndarray, steps: int, lr: float, rng, batch: int = 1024) -> tuple[dict, float]:
    p = {k: v.copy() for k, v in p.items()}
    m = {k: np.zeros_like(v) for k, v in p.items()}
    v = {k: np.zeros_like(w) for k, w in p.items()}
    b1, b2, loss = 0.9, 0.999, 0.0
    for s in range(1, steps + 1):
        idx = rng.integers(0, len(x), batch)
        loss, g = _grads(p, x[idx], y[idx])
        for k in p:
            m[k] = b1 * m[k] + (1 - b1) * g[k]
            v[k] = b2 * v[k] + (1 - b2) * g[k] ** 2
            p[k] -= lr * (m[k] / (1 - b1 ** s)) / (np.sqrt(v[k] / (1 - b2 ** s)) + 1e-8)
    return p, loss


def train_all(data_dir: Path, base_steps: int = 4000, ft_steps: int = 1500, seed: int = 0) -> dict:
    d = np.load(data_dir / "demos.npz")
    obs, act, outcome = d["obs"], d["act"], d["outcome"]
    E, T, _ = obs.shape
    xin, yin = obs.reshape(E * T, -1), act.reshape(E * T, -1)
    nx = Norm(xin.mean(0), xin.std(0) + 1e-6)
    ny = Norm(yin.mean(0), yin.std(0) + 1e-6)
    rng = np.random.default_rng(seed)
    X, Y = nx(xin), ny(yin)
    ep = np.repeat(np.arange(E), T)
    p0 = init_params([X.shape[1], 128, 128, Y.shape[1]], rng)
    t0 = time.monotonic()
    base, base_loss = train(p0, X, Y, base_steps, 1e-3, rng)
    out = {"base_loss": base_loss}
    params = {"theta_0": base}
    for name, cls in (("theta_lifted", "lifted"), ("theta_crushed", "crushed")):
        mask = np.isin(ep, np.flatnonzero(outcome == cls))
        if not mask.any():
            raise SystemExit(f"no {cls} demonstrations: generate more")
        params[name], out[f"{name}_loss"] = train(base, X[mask], Y[mask], ft_steps, 3e-4, rng)
    flat = {f"{k}/{w}": arr for k, ps in params.items() for w, arr in ps.items()}
    np.savez(data_dir / "policies.npz", **flat, nx_mu=nx.mu, nx_sd=nx.sd, ny_mu=ny.mu, ny_sd=ny.sd,
             quat=d["quat"])
    out["seconds"] = round(time.monotonic() - t0, 1)
    tl = {k: params["theta_lifted"][k] - base[k] for k in base}
    tc = {k: params["theta_crushed"][k] - base[k] for k in base}
    nrm = lambda t: float(np.sqrt(sum((a ** 2).sum() for a in t.values())))  # noqa: E731
    dot = sum((tl[k] * tc[k]).sum() for k in base)
    out.update({"norm_tau_lifted": round(nrm(tl), 3), "norm_tau_crushed": round(nrm(tc), 3),
                "cos_tau_lifted_tau_crushed": round(float(dot / (nrm(tl) * nrm(tc))), 3)})
    return out


# --- programs in weight space, run closed-loop -------------------------------------

def load_policies(data_dir: Path) -> tuple[dict, Norm, Norm, np.ndarray]:
    z = np.load(data_dir / "policies.npz")
    params: dict[str, dict] = {}
    for key in z.files:
        if "/" in key:
            name, w = key.split("/")
            params.setdefault(name, {})[w] = z[key]
    return params, Norm(z["nx_mu"], z["nx_sd"]), Norm(z["ny_mu"], z["ny_sd"]), z["quat"]


def program(params: dict, a: float, c: float) -> dict:
    """theta_0 + a * tau_lifted + c * tau_crushed."""
    b, L, C = params["theta_0"], params["theta_lifted"], params["theta_crushed"]
    return {k: b[k] + a * (L[k] - b[k]) + c * (C[k] - b[k]) for k in b}


def rollout(args) -> dict:
    p, nx, ny, quat, egg_xy, mode = args
    cfg = SceneConfig(egg_pos=(egg_xy[0], egg_xy[1], 0.0))
    sim = TeleopSim(cfg)
    lift, first = [], True
    for i in range(N_STEPS):
        t = i / CONTROL_HZ
        a = ny.inv(forward(p, nx(observation(t, sim, mode))[None])[0])
        sim.set_ctrl(a[:20])
        sim.set_wrist(a[20:23], quat)
        if first:
            sim._snap_root_to_target()
            first = False
        egg = sim.step(1 / CONTROL_HZ)
        lift.append(egg.lifted_m)
    return label_episode(max(lift), lift[-1], sim.cracked, sim.peak_force, sim.config.crack_force_n)


PROGRAMS = [
    ("theta_0 (all demos)", 0.0, 0.0),
    ("theta_0 + tau_lifted", 1.0, 0.0),
    ("theta_0 + tau_crushed", 0.0, 1.0),
    ("theta_0 - tau_crushed", 0.0, -1.0),
    ("theta_0 + tau_lifted - tau_crushed", 1.0, -1.0),
    ("theta_0 + 2 tau_lifted", 2.0, 0.0),
]
DIAL = [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]  # theta_0 + c * tau_crushed
EGG_OFFSETS = [(0.0, 0.0), (0.004, 0.0), (-0.004, 0.0), (0.0, 0.004), (0.0, -0.004)]


def eval_offsets(setup: Setup, n: int = 20, seed: int = 12345) -> list[tuple[float, float]]:
    """Egg positions for evaluation: the fixed 5 for a fixed egg, else n random
    positions in the training range (a seed the demonstrations never used)."""
    if not setup.egg_range_m:
        return EGG_OFFSETS
    rng = np.random.default_rng(seed)
    return [tuple(rng.uniform(-setup.egg_range_m, setup.egg_range_m, 2)) for _ in range(n)]


def evaluate(data_dir: Path, workers: int = 16, n_eval: int = 20, eval_setup: Setup | None = None) -> dict:
    setup = Setup.load(data_dir)
    params, nx, ny, quat = load_policies(data_dir)
    offsets = eval_offsets(eval_setup or setup, n_eval)
    rows = [(name, a, c) for name, a, c in PROGRAMS] + [(f"dial c={c:+.1f}", 0.0, c) for c in DIAL]
    jobs = [(program(params, a, c), nx, ny, quat, off, setup.obs) for _, a, c in rows for off in offsets]
    with ProcessPoolExecutor(workers) as ex:
        labels = list(ex.map(rollout, jobs))
    k = len(offsets)
    results = []
    for j, (name, a, c) in enumerate(rows):
        ls = labels[j * k:(j + 1) * k]
        results.append({
            "program": name, "a_lifted": a, "c_crushed": c, "rollouts": k,
            "lifted": sum(lb["outcome"] == "lifted" for lb in ls),
            "crushed": sum(lb["outcome"] == "crushed" for lb in ls),
            "not_lifted": sum(lb["outcome"] == "not_lifted" for lb in ls),
            "peak_force_n_mean": round(float(np.mean([lb["peak_force_n"] for lb in ls])), 2),
            "max_lift_cm_mean": round(float(np.mean([lb["max_lift_m"] for lb in ls])) * 100, 1),
        })
    (data_dir / "results.json").write_text(json.dumps(results, indent=1))
    (data_dir / "results.md").write_text(render_md(results, setup, offsets))
    return {"results": results}


def render_md(results: list[dict], setup: Setup | None = None, offsets=None) -> str:
    setup = setup or Setup()
    where = (f"egg at {len(offsets)} random positions within +-{setup.egg_range_m * 1000:.0f} mm"
             if setup.egg_range_m else "egg at the centre and moved 4 mm in x and y")
    lines = ["# Weight-space programs, run closed-loop in the simulator", "",
             f"Policy input: {setup.obs}. Each program is theta_0 + a * tau_lifted + c * tau_crushed. "
             f"Each row is {len(offsets or EGG_OFFSETS)} rollouts ({where}). Crack threshold 8 N (a simulation proxy).", "",
             "| Program | a | c | Lifted | Crushed | Not lifted | Mean peak force (N) | Mean max lift (cm) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['program']} | {r['a_lifted']:+.1f} | {r['c_crushed']:+.1f} | {r['lifted']}/{r['rollouts']} | "
                     f"{r['crushed']}/{r['rollouts']} | {r['not_lifted']}/{r['rollouts']} | "
                     f"{r['peak_force_n_mean']} | {r['max_lift_cm_mean']} |")
    return "\n".join(lines) + "\n"
