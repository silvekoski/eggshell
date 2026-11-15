"""Render saved episodes as clean 1920x1080 footage for the video.

Each episode is re-simulated from its recorded actuator and wrist targets
(the same path as `teleop replay`) in the "studio" look, with no HUD burned
in. A sidecar JSON per clip has the per-frame force, lift and crack state,
so the video draws its own overlays from the data.

  scripts/glrun uv run python scripts/render_footage.py --dataset datasets/demo --out out/footage
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from rokoko_teleop.recorder import label_episode
from rokoko_teleop.sim import SceneConfig, TeleopSim

NAMES = {0: "egg", 1: "crush", 2: "drop", 3: "miss"}


def render(dataset: Path, out: Path, ep: dict, fps: int, w: int, h: int, cam: tuple[float, float, float], args_look: str = "studio",
           track: bool = False) -> dict:
    a = np.load(dataset / ep["file"])
    t, action, wrist = a["t"], a["action"], a["wrist_target"]
    ss = 2 if args_look == "light" else 1  # supersample: render 2x, box-filter down
    sim = TeleopSim(SceneConfig(width=w * ss, height=h * ss, look=args_look))
    sim.camera.azimuth, sim.camera.elevation, sim.camera.distance = cam
    sim.camera.lookat[:] = [-0.06, 0.0, 0.13]
    palm_id, egg_id = sim._ids["palm"], sim._ids["egg"]
    look = None
    name = NAMES.get(ep["episode"], f"ep{ep['episode']}")
    video = out / f"{name}.mp4"
    writer = imageio.get_writer(str(video), fps=fps, codec="libx264", quality=9, macro_block_size=8)
    frames, next_t, max_lift, egg = [], 0.0, 0.0, None
    try:
        for i in range(len(t)):
            dt = float(t[i] - t[i - 1]) if i else 1 / 60
            sim.set_ctrl(action[i])
            sim.set_wrist(wrist[i, :3], wrist[i, 3:])
            if i == 0:
                sim._snap_root_to_target()
            egg = sim.step(dt)
            max_lift = max(max_lift, egg.lifted_m)
            rel = float(t[i] - t[0])
            if track:  # follow the hand and egg smoothly, so the hand fills the frame
                target = 0.5 * sim.data.xpos[palm_id] + 0.5 * sim.data.xpos[egg_id]
                look = target.copy() if look is None else look + (1 - np.exp(-dt / 0.6)) * (target - look)
                sim.camera.lookat[:] = look
            if rel >= next_t:
                img = sim.render()
                if ss > 1:
                    img = img.reshape(h, ss, w, ss, 3).mean(axis=(1, 3)).round().astype(np.uint8)
                writer.append_data(img)
                frames.append({"t": round(rel, 3), "force_n": round(egg.force_n, 3),
                               "lift_cm": round(egg.lifted_m * 100, 2), "cracked": bool(egg.cracked)})
                next_t += 1.0 / fps
    finally:
        writer.close()
        sim.close()
    label = label_episode(max_lift, egg.lifted_m, sim.cracked, sim.peak_force, sim.config.crack_force_n)
    meta = {"episode": ep["episode"], "name": name, "video": video.name, "fps": fps, "width": w, "height": h,
            "stored_label": {k: ep[k] for k in ("outcome", "max_lift_m", "peak_force_n")},
            "replayed_label": label, "crack_force_n": sim.config.crack_force_n, "frames": frames}
    (out / f"{name}.json").write_text(json.dumps(meta))
    print(f"{video}: {len(frames)} frames, label {label['outcome']} (stored {ep['outcome']})")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="datasets/demo")
    ap.add_argument("--out", default="out/footage")
    ap.add_argument("--episodes", type=int, nargs="+")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--look", choices=["studio", "light"], default="studio")
    ap.add_argument("--track", action="store_true", help="camera follows the hand and the egg")
    ap.add_argument("--camera", type=float, nargs=3, default=(232.0, -12.0, 0.8), metavar=("AZ", "EL", "DIST"))
    args = ap.parse_args()
    w, h = (int(x) for x in args.size.split("x"))
    ds, out = Path(args.dataset), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    eps = [json.loads(line) for line in (ds / "episodes.jsonl").open() if line.strip()]
    if args.episodes:
        eps = [e for e in eps if e["episode"] in args.episodes]
    for ep in eps:
        render(ds, out, ep, args.fps, w, h, tuple(args.camera), args.look, args.track)


if __name__ == "__main__":
    main()
