"""Where glove frames come from. Every source answers `get(t)` with the
newest HandFrame for the chosen hand (Z-up, yaw not yet applied for raw
RGMP), or None if nothing has arrived.

- RgmpSource: straight from `rkk-hand-solver` over TCP (no ROS needed).
- Ros2Source: the official rokoko-ros2-bridge topic /rkk_hand_bridge/hand/joints.
- ReplaySource: a JSONL recording made by `teleop record-glove` or `teleop synth`.
- SyntheticSource: the scripted operator, generated on the fly.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import numpy as np

from . import rgmp
from .synth import ScriptedOperator
from .xrhand import HandDefinition, HandFrame, XrBaseToZUp

RECORDING_FORMAT = "rokoko-teleop/glove-v1"


class Source:
    live = False
    duration: float | None = None

    def get(self, t: float) -> HandFrame | None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass


class SyntheticSource(Source):
    def __init__(self, op: ScriptedOperator | None = None):
        self.op = op or ScriptedOperator()
        self.duration = self.op.duration

    def get(self, t: float) -> HandFrame:
        return self.op.frame_at(t)


class ReplaySource(Source):
    """Plays a glove recording back by timestamp."""

    def __init__(self, path: str | Path, hand: str = "right", loop: bool = False):
        self.path = Path(path)
        self.loop = loop
        self.frames: list[HandFrame] = []
        self.header: dict = {}
        with self.path.open() as fh:
            for line in fh:
                rec = json.loads(line)
                if rec.get("format") == RECORDING_FORMAT:
                    self.header = rec
                    continue
                if rec.get("hand", hand) != hand:
                    continue
                self.frames.append(
                    HandFrame.from_rows(
                        rec["joints"], rec.get("hand", hand),
                        timestamp_us=int(rec["t_us"]), device_id=int(rec.get("device_id", 0)),
                        frame=self.header.get("frame", "zup"),
                    )
                )
        if not self.frames:
            raise ValueError(f"{path}: no frames for the {hand} hand")
        self.t0 = self.frames[0].timestamp_us
        self._ts = np.array([f.timestamp_us - self.t0 for f in self.frames]) / 1e6
        self.duration = float(self._ts[-1])

    def get(self, t: float) -> HandFrame:
        if self.loop and self.duration > 0:
            t = t % self.duration
        i = int(np.searchsorted(self._ts, t, side="right")) - 1
        return self.frames[max(0, min(i, len(self.frames) - 1))]


class RgmpSource(Source):
    """Background TCP client for the solver's RGMP v2 stream. Keeps only the
    newest frame per hand: a consumer that falls behind sees the latest pose,
    never a queue of stale ones. Reconnects with backoff."""

    live = True

    def __init__(self, host: str = "127.0.0.1", port: int = rgmp.DEFAULT_PORT, hand: str = "right"):
        self.host, self.port, self.hand = host, port, hand
        self._defs: dict[int, HandDefinition] = {}
        self._latest: dict[str, HandFrame] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.frames_received = 0
        self.connected = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        delay = 0.5
        while not self._stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=5.0) as sock:
                    sock.settimeout(2.0)
                    self.connected = True
                    delay = 0.5
                    while not self._stop.is_set():
                        try:
                            kind, payload = rgmp.read_frame(sock)
                        except socket.timeout:
                            continue
                        self._handle(kind, payload)
            except (OSError, EOFError, ValueError):
                pass
            self.connected = False
            self._stop.wait(delay)
            delay = min(delay * 2, 10.0)

    def _handle(self, kind: int, payload: bytes) -> None:
        if kind == rgmp.MSG_DEFINITION:
            d = rgmp.decode_definition(payload)
            if d is not None:
                with self._lock:
                    self._defs[d.device_id] = d
        elif kind == rgmp.MSG_DATA:
            device_id, group_id, _ = rgmp.decode_data_header(payload)
            with self._lock:
                d = self._defs.get(device_id)
            if d is None or group_id != d.group_id:
                return
            f = rgmp.decode_data(payload, d.hand)
            with self._lock:
                self._latest[d.hand] = f
                self.frames_received += 1
        elif kind == rgmp.MSG_DISCONNECT:
            device_id = rgmp.decode_disconnect(payload)
            with self._lock:
                d = self._defs.pop(device_id, None)
                if d is not None:
                    self._latest.pop(d.hand, None)

    def hands(self) -> list[str]:
        with self._lock:
            return sorted(self._latest)

    def get(self, t: float) -> HandFrame | None:
        with self._lock:
            f = self._latest.get(self.hand)
        # Raw solver frames are Y-up; yaw is applied later by the pipeline.
        return XrBaseToZUp(0.0).apply(f) if f is not None else None

    def get_raw(self, hand: str | None = None) -> HandFrame | None:
        with self._lock:
            return self._latest.get(hand or self.hand)

    def close(self) -> None:
        self._stop.set()


class Ros2Source(Source):
    """Subscribes to the official bridge (Z-up, yaw calibrated by the bridge's
    ~/calibrate service). Needs a sourced ROS 2 install with rkk_hand_msgs."""

    live = True

    def __init__(self, hand: str = "right", topic: str = "/rkk_hand_bridge/hand/joints"):
        import rclpy  # noqa: PLC0415 - only available inside a ROS 2 environment
        from rclpy.qos import qos_profile_sensor_data  # noqa: PLC0415
        from rkk_hand_msgs.msg import HandJoints  # noqa: PLC0415

        self.hand = hand
        self._want = HandJoints.HAND_LEFT if hand == "left" else HandJoints.HAND_RIGHT
        self._latest: HandFrame | None = None
        self._lock = threading.Lock()
        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._node = rclpy.create_node("rokoko_teleop")
        self._node.create_subscription(HandJoints, topic, self._on_msg, qos_profile_sensor_data)
        self._thread = threading.Thread(target=rclpy.spin, args=(self._node,), daemon=True)
        self._thread.start()

    def _on_msg(self, msg) -> None:
        if msg.hand != self._want:
            return
        pos = np.array([[p.position.x, p.position.y, p.position.z] for p in msg.joints])
        ori = np.array([[p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w] for p in msg.joints])
        f = HandFrame(self.hand, pos, ori, int(msg.timestamp_us), int(msg.device_id), frame="zup")
        with self._lock:
            self._latest = f

    def get(self, t: float) -> HandFrame | None:
        with self._lock:
            return self._latest

    def close(self) -> None:
        self._node.destroy_node()


class GloveRecorder:
    """Writes glove frames as JSONL: a header line, then one frame per line.
    Raw RGMP frames are stored as-is (frame = xr_base) so a replay goes
    through exactly the conversion a live stream does."""

    def __init__(self, path: str | Path, frame: str, meta: dict | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        header = {"format": RECORDING_FORMAT, "frame": frame, "created": time.time(), **(meta or {})}
        self._fh.write(json.dumps(header) + "\n")
        self.count = 0

    def write(self, f: HandFrame) -> None:
        rec = {"t_us": int(f.timestamp_us), "hand": f.hand, "device_id": f.device_id, "joints": f.as_rows()}
        self._fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
        self.count += 1

    def close(self) -> None:
        self._fh.close()
