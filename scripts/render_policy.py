"""Render weight-space programs as footage: the same egg position, different weights.

  scripts/glrun uv run python scripts/render_policy.py find --dir datasets/ws-state/seed0
  scripts/glrun uv run python scripts/render_policy.py render --dir datasets/ws-state/seed0 --egg 0.004 -0.01 --out out/ws-footage
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from rokoko_teleop import weightspace as ws
from rokoko_teleop.recorder import label_episode
from rokoko_teleop.sim import SceneConfig, TeleopSim

PROGS = {"theta_0": (0.0, 0.0), "plus_tau_lifted": (1.0, 0.0), "plus_tau_crushed": (0.0, 1.0)}


def _one(args):
    d, name, egg = args
    params, nx, ny, quat = ws.load_policies(Path(d))
    setup = ws.Setup.load(Path(d))
    a, c = PROGS[name]
    return name, egg, ws.rollout((ws.program(params, a, c), nx, ny, quat, egg, setup.obs))


def find(d: str) -> None:
    setup = ws.Setup.load(Path(d))
    offs = ws.eval_offsets(setup, 20)
    jobs = [(d, n, o) for o in offs for n in PROGS]
    with ProcessPoolExecutor(24) as ex:
        res = list(ex.map(_one, jobs))
    by = {}
    for name, egg, lb in res:
        by.setdefault(egg, {})[name] = (lb["outcome"], lb["peak_force_n"])
    for i, (egg, r) in enumerate(by.items()):
        mark = " <==" if r["theta_0"][0] == "crushed" and r["plus_tau_lifted"][0] == "lifted" else ""
        print(f"[{i}] egg=({egg[0]:+.4f},{egg[1]:+.4f}) " + "  ".join(f"{k}={v[0]}/{v[1]:.1f}N" for k, v in r.items()) + mark)


def render(d: str, egg: tuple[float, float], out: Path, w=1920, h=1080, fps=30) -> None:
    params, nx, ny, quat = ws.load_policies(Path(d))
    setup = ws.Setup.load(Path(d))
    out.mkdir(parents=True, exist_ok=True)
    for name, (a, c) in PROGS.items():
        p = ws.program(params, a, c)
        sim = TeleopSim(SceneConfig(egg_pos=(egg[0], egg[1], 0.0), width=2 * w, height=2 * h, look="light"))
        sim.camera.azimuth, sim.camera.elevation, sim.camera.distance = 225, -32, 0.56
        palm_id, egg_id = sim._ids["palm"], sim._ids["egg"]
        look, lift, first, next_t, frames = None, [], True, 0.0, []
        writer = imageio.get_writer(str(out / f"{name}.mp4"), fps=fps, codec="libx264", quality=9, macro_block_size=8)
        for i in range(ws.N_STEPS):
            t = i / ws.CONTROL_HZ
            act = ny.inv(ws.forward(p, nx(ws.observation(t, sim, setup.obs))[None])[0])
            sim.set_ctrl(act[:20])
            sim.set_wrist(act[20:23], quat)
            if first:
                sim._snap_root_to_target()
                first = False
            e = sim.step(1 / ws.CONTROL_HZ)
            lift.append(e.lifted_m)
            target = 0.5 * sim.data.xpos[palm_id] + 0.5 * sim.data.xpos[egg_id]
            look = target.copy() if look is None else look + (1 - np.exp(-(1 / ws.CONTROL_HZ) / 0.6)) * (target - look)
            sim.camera.lookat[:] = look
            if t >= next_t:
                img = sim.render().reshape(h, 2, w, 2, 3).mean(axis=(1, 3)).round().astype(np.uint8)
                writer.append_data(img)
                frames.append({"t": round(t, 3), "force_n": round(e.force_n, 3), "lift_cm": round(e.lifted_m * 100, 2),
                               "cracked": bool(e.cracked)})
                next_t += 1 / fps
        writer.close()
        lb = label_episode(max(lift), lift[-1], sim.cracked, sim.peak_force, sim.config.crack_force_n)
        (out / f"{name}.json").write_text(json.dumps({"program": name, "a": a, "c": c, "egg_xy": egg, "label": lb,
                                                      "frames": frames}))
        print(name, lb["outcome"], lb["peak_force_n"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["find", "render"])
    ap.add_argument("--dir", default="datasets/ws-state/seed0")
    ap.add_argument("--egg", type=float, nargs=2, default=(0.0, 0.0))
    ap.add_argument("--egg-index", type=int, help="use evaluation egg position i exactly (find prints them in order)")
    ap.add_argument("--out", type=Path, default=Path("out/ws-footage"))
    a = ap.parse_args()
    if a.cmd == "find":
        find(a.dir)
    else:
        egg = tuple(a.egg) if a.egg_index is None else ws.eval_offsets(ws.Setup.load(Path(a.dir)), 20)[a.egg_index]
        render(a.dir, egg, a.out)
