"""teleop: Rokoko Smartgloves -> simulated Shadow hand, with demo recording.

  teleop demo                       scripted operator -> video + labelled episodes (no hardware)
  teleop run --source rgmp          live from rkk-hand-solver (viewer window; --headless for video)
  teleop run --source ros2          live from rokoko-ros2-bridge topics
  teleop run --source replay --file recordings/x.jsonl
  teleop record-glove --out recordings/x.jsonl   raw glove capture for later replay
  teleop synth --out recordings/synthetic.jsonl  scripted operator as a glove recording
  teleop fake-solver                serve RGMP on :12277 (synthetic or --file), for testing clients
  teleop review --dataset datasets/demo   Nemotron 3.5 Super VL re-labels each episode from its
                                    camera keyframes + force log and flags disagreements (needs NVIDIA_API_KEY)
  teleop replay --dataset datasets/demo   play saved episodes again in the MuJoCo viewer
                                    (or --headless --video out.mp4); the label is computed again
  teleop weightspace all            train policies on the labelled episodes and program them in weight space
  teleop nemotron-smoke             one text and one image request, to check the key
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import rgmp
from .runner import replay_dataset, run_headless, run_live
from .sources import GloveRecorder, ReplaySource, RgmpSource, Source, SyntheticSource
from .synth import SCRIPTS, ScriptedOperator, frames
from .teleop import Teleop, WristMapper


def _source(args) -> Source:
    if args.source == "synthetic":
        return SyntheticSource(ScriptedOperator(SCRIPTS[args.script], hand=args.hand, tremor_rad=args.tremor))
    if args.source == "replay":
        if not args.file:
            sys.exit("--file is required with --source replay")
        return ReplaySource(args.file, hand=args.hand)
    if args.source == "rgmp":
        return RgmpSource(args.host, args.port, hand=args.hand)
    if args.source == "ros2":
        from .sources import Ros2Source  # noqa: PLC0415

        return Ros2Source(hand=args.hand)
    sys.exit(f"unknown source {args.source}")


def _teleop(args, source: Source) -> Teleop:
    # Synthetic and replayed-synthetic data are already in scene coordinates;
    # a real glove's position is relative to wherever the operator stands.
    mode = args.wrist_mode or ("absolute" if args.source in ("synthetic", "replay") else "relative")
    return Teleop(wrist=WristMapper(mode=mode, scale=args.wrist_scale))


def _add_source_args(p: argparse.ArgumentParser, default: str) -> None:
    p.add_argument("--source", choices=["synthetic", "replay", "rgmp", "ros2"], default=default)
    p.add_argument("--script", choices=sorted(SCRIPTS), default="egg", help="synthetic operator script")
    p.add_argument("--tremor", type=float, default=0.0, help="synthetic finger noise, rad")
    p.add_argument("--file", help="glove recording (JSONL) for --source replay")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=rgmp.DEFAULT_PORT)
    p.add_argument("--hand", choices=["right", "left"], default="right")
    p.add_argument("--wrist-mode", choices=["absolute", "relative"])
    p.add_argument("--wrist-scale", type=float, default=1.0)


def cmd_demo(args) -> None:
    out = Path(args.out)
    results = []
    for script in args.scripts:
        src = SyntheticSource(ScriptedOperator(SCRIPTS[script], tremor_rad=args.tremor))
        video = out.with_name(f"{out.stem}-{script}{out.suffix}") if len(args.scripts) > 1 else out
        r = run_headless(src, Teleop(), video=None if args.no_video else video,
                         dataset=Path(args.dataset), log_every_s=args.log_every)
        results.append({"script": script, "video": str(r.video), "episode": str(r.episode), **r.label})
        print(json.dumps(results[-1]))
    print(f"dataset: {args.dataset}/episodes.jsonl")


def cmd_run(args) -> None:
    src = _source(args)
    tele = _teleop(args, src)
    try:
        if args.headless:
            if src.live:
                print(f"waiting for glove frames from {args.source} ...")
                t0 = time.monotonic()
                while src.get(0) is None:
                    if time.monotonic() - t0 > 15:
                        sys.exit("no glove frames after 15 s")
                    time.sleep(0.1)
                if args.calibrate:
                    print("calibrating from the current pose (flat hand, fingers forward)")
                    tele.calibrate(src.get(0))
            r = run_headless(src, tele, seconds=args.seconds, video=Path(args.video) if args.video else None,
                             dataset=Path(args.dataset) if args.dataset else None, log_every_s=args.log_every)
            print(json.dumps({"steps": r.steps, "video": str(r.video), "episode": str(r.episode), **r.label}))
        else:
            run_live(src, tele, dataset=Path(args.dataset) if args.dataset else None,
                     calibrate_after_s=args.calibrate_after if src.live else None)
    finally:
        src.close()


def cmd_record_glove(args) -> None:
    src = RgmpSource(args.host, args.port, hand=args.hand)
    rec = GloveRecorder(args.out, frame="xr_base", meta={"source": f"rgmp://{args.host}:{args.port}"})
    print(f"recording {args.hand} hand from {args.host}:{args.port} for {args.seconds:.0f}s -> {args.out}")
    last_ts = None
    t_end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < t_end:
            f = src.get_raw()
            if f is not None and f.timestamp_us != last_ts:
                rec.write(f)
                last_ts = f.timestamp_us
            time.sleep(0.002)
    finally:
        rec.close()
        src.close()
    print(f"wrote {rec.count} frames")


def cmd_synth(args) -> None:
    from .fake_solver import to_xr_base  # noqa: PLC0415

    op = ScriptedOperator(SCRIPTS[args.script], hand=args.hand, tremor_rad=args.tremor)
    frame = "xr_base" if args.xr_base else "zup"
    rec = GloveRecorder(args.out, frame=frame, meta={"source": f"synthetic:{args.script}"})
    for f in frames(op, args.rate):
        rec.write(to_xr_base(f) if args.xr_base else f)
    rec.close()
    print(f"wrote {rec.count} frames ({frame}) to {args.out}")


def cmd_fake_solver(args) -> None:
    from .fake_solver import FakeSolver  # noqa: PLC0415

    src: Source
    if args.file:
        src = ReplaySource(args.file, hand=args.hand)
    else:
        src = SyntheticSource(ScriptedOperator(SCRIPTS[args.script], hand=args.hand, tremor_rad=args.tremor))
    solver = FakeSolver(src, host=args.host, port=args.port, rate_hz=args.rate).start()
    print(f"fake rkk-hand-solver serving RGMP v2 on {args.host}:{solver.port} (Ctrl-C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        solver.stop()


def cmd_replay(args) -> None:
    import os  # noqa: PLC0415

    live = not args.headless
    if live and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and sys.platform == "linux":
        sys.exit("no display: use --headless --video out/replay.mp4 (or run under xvfb-run)")
    if not live and not args.video:
        sys.exit("--headless needs --video")
    results = replay_dataset(Path(args.dataset), episodes=args.episodes, live=live,
                             video=Path(args.video) if args.video else None, speed=args.speed)
    same = sum(r.same_label for r in results)
    print(f"{same}/{len(results)} replayed label(s) match the stored label")
    if same != len(results):
        sys.exit(1)


def cmd_weightspace(args) -> None:
    from . import weightspace as ws  # noqa: PLC0415

    d = Path(args.dir)
    if args.step in ("gen", "all"):
        setup = ws.Setup(obs=args.obs, egg_range_m=args.egg_range, dart_m=args.dart)
        print("demonstrations:", json.dumps(ws.generate(d, n=args.n, workers=args.workers, seed=args.data_seed,
                                                        setup=setup)))
    if args.step in ("train", "all"):
        print("training:", json.dumps(ws.train_all(d, seed=args.seed)))
    if args.step in ("eval", "all"):
        res = ws.evaluate(d, workers=args.workers, n_eval=args.n_eval)["results"]
        print((d / "results.md").read_text())
        _ = res


def cmd_review(args) -> None:
    from .review import review_dataset, summary_line  # noqa: PLC0415

    results = review_dataset(Path(args.dataset), episodes=args.episodes, force=args.force)
    for r in results:
        print(summary_line(r))
    flagged = sum(1 for r in results if r.get("flag"))
    print(f"{len(results)} episode(s), {flagged} flagged for review -> {args.dataset}/reviews.jsonl, "
          f"{args.dataset}/review.md")


def cmd_nemotron_smoke(args) -> None:
    import io  # noqa: PLC0415

    import imageio.v2 as imageio  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    from .nemotron import DISPLAY_NAME, NemotronClient, NemotronError, image_part  # noqa: PLC0415

    client = NemotronClient(max_retries=2)
    if not client.configured():
        sys.exit("Nemotron not configured: run with NVIDIA_API_KEY=... teleop nemotron-smoke")
    img = np.zeros((64, 64, 3), np.uint8)
    img[:, :] = (210, 30, 30)
    buf = io.BytesIO()
    imageio.imwrite(buf, img, format="png")
    try:
        t0 = time.monotonic()
        text = client.chat([{"role": "user", "content": "Reply with the single word OK."}], max_tokens=200)
        print(f"{DISPLAY_NAME} ({client.model}) text: {text.strip()[:80]!r} in {time.monotonic() - t0:.1f}s")
        t0 = time.monotonic()
        text = client.chat([{"role": "user", "content": [
            {"type": "text", "text": "What colour fills this image? One word."}, image_part(buf.getvalue())]}],
            max_tokens=200)
        print(f"{DISPLAY_NAME} image: {text.strip()[:80]!r} in {time.monotonic() - t0:.1f}s (expected: red)")
    except NemotronError as e:
        sys.exit(str(e))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="teleop", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("demo", help="scripted operator -> video + labelled dataset (no hardware)")
    p.add_argument("--out", default="out/demo.mp4")
    p.add_argument("--dataset", default="datasets/demo")
    p.add_argument("--scripts", nargs="+", default=["egg"], choices=sorted(SCRIPTS))
    p.add_argument("--tremor", type=float, default=0.0)
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--log-every", type=float, default=1.0)
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("run", help="drive the sim from a glove source")
    _add_source_args(p, default="rgmp")
    p.add_argument("--headless", action="store_true", help="no window; optionally write --video")
    p.add_argument("--seconds", type=float)
    p.add_argument("--video")
    p.add_argument("--dataset", help="save labelled episodes here")
    p.add_argument("--calibrate", action="store_true", help="headless: calibrate on the first frame")
    p.add_argument("--calibrate-after", type=float, default=5.0, help="viewer: seconds before auto-calibration")
    p.add_argument("--log-every", type=float, default=1.0)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("record-glove", help="capture raw solver frames to JSONL")
    p.add_argument("--out", required=True)
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=rgmp.DEFAULT_PORT)
    p.add_argument("--hand", choices=["right", "left"], default="right")
    p.set_defaults(fn=cmd_record_glove)

    p = sub.add_parser("synth", help="write the scripted operator as a glove recording")
    p.add_argument("--out", default="recordings/synthetic.jsonl")
    p.add_argument("--script", choices=sorted(SCRIPTS), default="egg")
    p.add_argument("--hand", choices=["right", "left"], default="right")
    p.add_argument("--tremor", type=float, default=0.0)
    p.add_argument("--rate", type=float, default=60.0)
    p.add_argument("--xr-base", action="store_true", help="store raw Y-up frames, like record-glove")
    p.set_defaults(fn=cmd_synth)

    p = sub.add_parser("fake-solver", help="serve RGMP v2 like rkk-hand-solver")
    p.add_argument("--file")
    p.add_argument("--script", choices=sorted(SCRIPTS), default="egg")
    p.add_argument("--tremor", type=float, default=0.0)
    p.add_argument("--hand", choices=["right", "left"], default="right")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=rgmp.DEFAULT_PORT)
    p.add_argument("--rate", type=float, default=60.0)
    p.set_defaults(fn=cmd_fake_solver)

    p = sub.add_parser("review", help="Nemotron 3.5 Super VL second opinion on each episode label")
    p.add_argument("--dataset", default="datasets/demo")
    p.add_argument("--episodes", type=int, nargs="+", help="only these episode numbers")
    p.add_argument("--force", action="store_true", help="review again, even episodes already reviewed")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("replay", help="play saved episodes again (viewer or video); labels must reproduce")
    p.add_argument("--dataset", default="datasets/demo")
    p.add_argument("--episodes", type=int, nargs="+", help="only these episode numbers")
    p.add_argument("--headless", action="store_true", help="no window; write --video")
    p.add_argument("--video", help="also write an MP4 with the force/lift HUD")
    p.add_argument("--speed", type=float, default=1.0, help="viewer playback speed")
    p.set_defaults(fn=cmd_replay)

    p = sub.add_parser("weightspace", help="task arithmetic on policies trained from labelled episodes")
    p.add_argument("step", choices=["gen", "train", "eval", "all"])
    p.add_argument("--dir", default="datasets/weightspace")
    p.add_argument("--n", type=int, default=120)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--seed", type=int, default=0, help="training seed")
    p.add_argument("--data-seed", type=int, default=0)
    p.add_argument("--obs", choices=["phase", "state"], default="phase", help="policy input (gen)")
    p.add_argument("--egg-range", type=float, default=0.0, help="egg moves +-this (m) between episodes (gen)")
    p.add_argument("--dart", type=float, default=0.0, help="executed wrist noise (m) during demos (gen)")
    p.add_argument("--n-eval", type=int, default=20, help="random egg positions per program (eval)")
    p.set_defaults(fn=cmd_weightspace)

    p = sub.add_parser("nemotron-smoke", help="check NVIDIA_API_KEY with one text and one image request")
    p.set_defaults(fn=cmd_nemotron_smoke)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
