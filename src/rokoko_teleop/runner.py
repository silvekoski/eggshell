"""Run loops: headless (sim time, renders a video) and live (wall clock,
MuJoCo viewer window)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .recorder import DatasetWriter, EpisodeBuffer, label_episode, pick_keyframes
from .sim import TeleopSim
from .sources import Source
from .teleop import Teleop


@dataclass
class RunResult:
    steps: int
    label: dict
    video: Path | None
    episode: Path | None


def _hud(img: np.ndarray, force: float, crack: float, cracked: bool, lifted: float) -> np.ndarray:
    """A grip-force bar in the corner, drawn into the frame (no GL text needed)."""
    out = img.copy()
    h, w, _ = out.shape
    x0, y0, bw, bh = 16, h - 40, 220, 18
    out[y0 - 2 : y0 + bh + 2, x0 - 2 : x0 + bw + 2] = (20, 20, 20)
    frac = 1.0 if cracked else (min(1.0, force / crack) if crack > 0 else 0.0)
    color = (200, 30, 20) if cracked else ((240, 170, 30) if frac > 0.6 else (60, 190, 90))
    out[y0 : y0 + bh, x0 : x0 + int(bw * frac)] = color
    # Crack threshold tick at the end, lift indicator bar on the right.
    out[y0 - 6 : y0 + bh + 6, x0 + bw - 2 : x0 + bw] = (230, 230, 230)
    lx = w - 30
    lh = int(min(1.0, max(0.0, lifted) / 0.15) * 160)
    out[h - 200 : h - 40, lx : lx + 14] = (20, 20, 20)
    if lh > 0:
        out[h - 40 - lh : h - 40, lx : lx + 14] = (80, 160, 240)
    return out


def run_headless(
    source: Source,
    teleop: Teleop,
    seconds: float | None = None,
    control_hz: float = 60.0,
    video: Path | None = None,
    fps: int = 30,
    dataset: Path | None = None,
    sim: TeleopSim | None = None,
    log_every_s: float = 1.0,
    snapshots: Path | None = None,
    keyframe_hz: float = 4.0,
) -> RunResult:
    sim = sim or TeleopSim()
    duration = seconds if seconds is not None else (source.duration or 10.0)
    dt = 1.0 / control_hz
    steps = int(round(duration * control_hz))
    writer = None
    if video is not None:
        import imageio.v2 as imageio  # noqa: PLC0415

        video.parent.mkdir(parents=True, exist_ok=True)
        writer = imageio.get_writer(str(video), fps=fps, codec="libx264", quality=7, macro_block_size=8)
    buf = EpisodeBuffer()
    next_frame_t = 0.0
    next_log_t = 0.0
    next_snap_t = 0.0
    next_kf_t = 0.0
    kf_frames: list[tuple[float, np.ndarray]] = []  # camera frames for the post-hoc review
    can_render = dataset is not None and keyframe_hz > 0
    egg = None
    first = True
    try:
        wall0 = time.monotonic()
        for i in range(steps):
            t = i * dt
            if source.live:  # a live stream runs on the wall clock
                time.sleep(max(0.0, wall0 + t - time.monotonic()))
            f = source.get(t)
            if f is None:
                if source.live:
                    time.sleep(dt)
                continue
            cmd = teleop.process(f, dt)
            sim.set_ctrl(cmd.ctrl)
            sim.set_wrist(cmd.wrist_pos, cmd.wrist_quat)
            if first:
                sim._snap_root_to_target()
                first = False
            egg = sim.step(dt)
            buf.add(t, cmd, sim, egg)
            if writer is not None and t >= next_frame_t:
                img = _hud(sim.render(), egg.force_n, sim.config.crack_force_n, egg.cracked, egg.lifted_m)
                writer.append_data(img)
                next_frame_t += 1.0 / fps
            if can_render and t >= next_kf_t:
                try:
                    kf_frames.append((t, sim.render().copy()))
                except Exception as e:  # noqa: BLE001  no GL: the review uses the log only
                    print(f"keyframes off (no renderer: {e})")
                    can_render = False
                next_kf_t += 1.0 / keyframe_hz
            if snapshots is not None and t >= next_snap_t:
                import imageio.v2 as imageio  # noqa: PLC0415

                snapshots.mkdir(parents=True, exist_ok=True)
                imageio.imwrite(snapshots / f"t{t:05.1f}.png", sim.render())
                next_snap_t += 2.0
            if log_every_s and t >= next_log_t:
                print(f"t={t:5.2f}s egg_lift={egg.lifted_m * 100:5.1f}cm force={egg.force_n:5.2f}N "
                      f"contacts={egg.hand_contacts} cracked={egg.cracked} inspire={cmd.inspire}")
                next_log_t += log_every_s
    finally:
        if writer is not None:
            writer.close()
    final = egg.lifted_m if egg else 0.0
    label = label_episode(buf.max_lift, final, sim.cracked, sim.peak_force, sim.config.crack_force_n)
    ep_path = None
    if dataset is not None and len(buf):
        r = buf.rows
        egg_z = np.asarray(r["egg_pose"])[:, 2]
        kfs = pick_keyframes(kf_frames, np.asarray(r["t"]), np.asarray(r["egg_force"]), egg_z - egg_z[0])
        ep_path = DatasetWriter(dataset).save(
            buf, label, {"source": type(source).__name__, "crack_force_n": sim.config.crack_force_n}, kfs)
    return RunResult(len(buf), label, video, ep_path)


def run_live(
    source: Source,
    teleop: Teleop,
    dataset: Path | None = None,
    control_hz: float = 60.0,
    calibrate_after_s: float | None = 5.0,
) -> None:
    """Interactive loop with the MuJoCo viewer. Keys (in the viewer window):
    C = calibrate now (flat hand, fingers forward), R = reset the scene and
    start a new episode (the previous one is saved and labelled)."""
    import mujoco.viewer  # noqa: PLC0415

    sim = TeleopSim()
    state = {"calibrate": False, "reset": False}

    def on_key(keycode: int) -> None:
        if keycode in (ord("C"), ord("c")):
            state["calibrate"] = True
        elif keycode in (ord("R"), ord("r")):
            state["reset"] = True

    writer = DatasetWriter(dataset) if dataset is not None else None
    buf = EpisodeBuffer()
    dt = 1.0 / control_hz
    t0 = time.monotonic()
    calibrated = calibrate_after_s is None
    if not calibrated:
        print(f"Hold a flat hand, level, fingers forward: calibrating in {calibrate_after_s:.0f}s")

    def finish_episode() -> None:
        nonlocal buf
        if writer is not None and len(buf) > control_hz:  # ignore < 1 s
            label = label_episode(buf.max_lift, buf.rows["egg_pose"][-1][2] - sim._egg_rest_z,
                                  sim.cracked, sim.peak_force, sim.config.crack_force_n)
            path = writer.save(buf, label, {"source": type(source).__name__,
                                            "crack_force_n": sim.config.crack_force_n})
            print(f"saved {path.name}: {label}")
        buf = EpisodeBuffer()

    with mujoco.viewer.launch_passive(sim.model, sim.data, key_callback=on_key) as viewer:
        while viewer.is_running():
            tick = time.monotonic()
            t = tick - t0
            f = source.get(t)
            if f is not None:
                if (not calibrated and t >= calibrate_after_s) or state["calibrate"]:
                    teleop.calibrate(f)
                    calibrated = True
                    state["calibrate"] = False
                    print(f"calibrated: yaw={teleop.yaw_rad:.3f} rad")
                if state["reset"]:
                    finish_episode()
                    sim.reset()
                    state["reset"] = False
                cmd = teleop.process(f, dt)
                sim.set_ctrl(cmd.ctrl)
                sim.set_wrist(cmd.wrist_pos, cmd.wrist_quat)
                egg = sim.step(dt)
                if calibrated:
                    buf.add(t, cmd, sim, egg)
            viewer.sync()
            time.sleep(max(0.0, dt - (time.monotonic() - tick)))
    finish_episode()


@dataclass
class ReplayResult:
    episode: int
    stored: dict
    replayed: dict

    @property
    def same_label(self) -> bool:
        return self.stored.get("outcome") == self.replayed.get("outcome")


def replay_dataset(
    dataset: Path,
    episodes: list[int] | None = None,
    live: bool = True,
    video: Path | None = None,
    speed: float = 1.0,
    fps: int = 30,
    pause_s: float = 1.0,
) -> list[ReplayResult]:
    """Play saved episodes again: the recorded actuator targets and wrist
    targets drive a fresh simulation, so the egg physics run again and the
    label is computed again (it must match the stored label).

    live=True opens the MuJoCo viewer and plays on the wall clock (needs a
    display). Otherwise, with `video`, it renders the same HUD frames to MP4."""
    import json  # noqa: PLC0415

    index = Path(dataset) / "episodes.jsonl"
    entries = [json.loads(line) for line in index.open() if line.strip()]
    if episodes is not None:
        entries = [e for e in entries if e["episode"] in set(episodes)]
    if not entries:
        raise SystemExit(f"no episodes to replay in {index}")

    sim = TeleopSim()
    results: list[ReplayResult] = []
    viewer = writer = None
    if live:
        import mujoco.viewer  # noqa: PLC0415

        viewer = mujoco.viewer.launch_passive(sim.model, sim.data)
    if video is not None:
        import imageio.v2 as imageio  # noqa: PLC0415

        video.parent.mkdir(parents=True, exist_ok=True)
        writer = imageio.get_writer(str(video), fps=fps, codec="libx264", quality=7, macro_block_size=8)
    try:
        for entry in entries:
            arr = np.load(Path(dataset) / entry["file"])
            t, action, wrist = arr["t"], arr["action"], arr["wrist_target"]
            sim.reset()
            print(f"replay episode {entry['episode']}: stored label {entry['outcome']} "
                  f"(lift {entry['max_lift_m'] * 100:.1f} cm, peak {entry['peak_force_n']:.2f} N)")
            max_lift = 0.0
            egg = None
            next_frame_t = 0.0
            wall0 = time.monotonic()
            for i in range(len(t)):
                dt = float(t[i] - t[i - 1]) if i else float(t[1] - t[0]) if len(t) > 1 else 1 / 60
                sim.set_ctrl(action[i])
                sim.set_wrist(wrist[i, :3], wrist[i, 3:])
                if i == 0:
                    sim._snap_root_to_target()
                egg = sim.step(dt)
                max_lift = max(max_lift, egg.lifted_m)
                rel_t = float(t[i] - t[0])
                if writer is not None and rel_t >= next_frame_t:
                    writer.append_data(_hud(sim.render(), egg.force_n, sim.config.crack_force_n,
                                            egg.cracked, egg.lifted_m))
                    next_frame_t += 1.0 / fps
                if viewer is not None:
                    if not viewer.is_running():
                        return results
                    viewer.sync()
                    time.sleep(max(0.0, wall0 + rel_t / speed - time.monotonic()))
            replayed = label_episode(max_lift, egg.lifted_m if egg else 0.0, sim.cracked, sim.peak_force,
                                     sim.config.crack_force_n)
            results.append(ReplayResult(entry["episode"], entry, replayed))
            print(f"  replayed label {replayed['outcome']} (lift {replayed['max_lift_m'] * 100:.1f} cm, "
                  f"peak {replayed['peak_force_n']:.2f} N) {'same' if results[-1].same_label else 'DIFFERENT'}")
            if viewer is not None:
                end = time.monotonic() + pause_s
                while time.monotonic() < end and viewer.is_running():
                    viewer.sync()
                    time.sleep(1 / 60)
            if writer is not None:  # hold the last frame
                last = _hud(sim.render(), egg.force_n, sim.config.crack_force_n, egg.cracked, egg.lifted_m)
                for _ in range(int(pause_s * fps)):
                    writer.append_data(last)
    finally:
        if writer is not None:
            writer.close()
        if viewer is not None:
            viewer.close()
    return results
