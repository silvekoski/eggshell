"""RGMP v2: the wire format `rkk-hand-solver` serves on TCP port 12277.

Re-implemented from Rokoko's rokoko-ros2-bridge (rkk_hand_bridge/rgmp.py)
so that we can read the solver directly, with no ROS 2 install, and so we
can *serve* the same format from synthetic or recorded data (`teleop
fake-solver`), which lets the real ROS 2 bridge and our client be tested
without gloves.

Framing: little-endian u32 msg_prefix, u32 length, then `length` bytes.
  1 = definition (JSON), 2 = data (binary), 3 = disconnect (u32 device_id)
Data payload: u32 device_id, u32 group_id, u64 timestamp_us, then
26 x float32[7] (x, y, z, qx, qy, qz, qw) in xr_base (Y-up).
"""

from __future__ import annotations

import json
import struct

import numpy as np

from .xrhand import JOINT_COUNT, JOINT_NAMES, HandDefinition, HandFrame

MSG_DEFINITION = 1
MSG_DATA = 2
MSG_DISCONNECT = 3

DEVICE_TYPE = "solved_hand"
GROUP_NAME = "joints_openxr"
XR_PREFIX = "xr_"
RADIUS_LABEL = "joint_radius"
DEFAULT_PORT = 12277

_HEADER = struct.Struct("<II")
_DATA_HEADER = struct.Struct("<IIQ")
_POSE = struct.Struct("<7f")


def read_frame(sock) -> tuple[int, bytes]:
    msg_prefix, msg_len = _HEADER.unpack(_read_exact(sock, _HEADER.size))
    return msg_prefix, _read_exact(sock, msg_len)


def _read_exact(sock, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf.extend(chunk)
    return bytes(buf)


def frame(msg_prefix: int, payload: bytes) -> bytes:
    return _HEADER.pack(msg_prefix, len(payload)) + payload


def decode_definition(payload: bytes) -> HandDefinition | None:
    d = json.loads(payload)
    if d.get("device_type") != DEVICE_TYPE:
        return None
    group_id, group = -1, None
    for index, g in enumerate(d.get("groups") or []):
        if g.get("name") == GROUP_NAME:
            group_id, group = g.get("group_id", g.get("id", index)), g
            break
    if group is None:
        return None
    names = tuple(s["target_frame"].removeprefix(XR_PREFIX) for s in group["streams"])
    if len(names) != JOINT_COUNT:
        return None
    radii = {
        e["target_frame"].removeprefix(XR_PREFIX): e["value"]
        for e in d.get("static_data") or []
        if e.get("custom_label") == RADIUS_LABEL
    }
    return HandDefinition(
        device_id=d["device_id"],
        hand=(d.get("device_info") or {}).get("hand", "unknown"),
        joint_names=names,
        joint_radii=tuple(radii.get(n, 0.0) for n in names),
        timestamp_epoch=d.get("timestamp_epoch"),
        group_id=group_id,
    )


def encode_definition(defn: HandDefinition) -> bytes:
    payload = {
        "device_id": defn.device_id,
        "device_type": DEVICE_TYPE,
        "timestamp_epoch": defn.timestamp_epoch,
        "device_info": {"hand": defn.hand},
        "static_data": [
            {"custom_label": RADIUS_LABEL, "target_frame": XR_PREFIX + n, "value": r}
            for n, r in zip(defn.joint_names, defn.joint_radii)
        ],
        "groups": [
            {
                "name": GROUP_NAME,
                "group_id": defn.group_id,
                "streams": [{"target_frame": XR_PREFIX + n} for n in defn.joint_names],
            }
        ],
    }
    return json.dumps(payload).encode()


def decode_data_header(payload: bytes) -> tuple[int, int, int]:
    return _DATA_HEADER.unpack_from(payload, 0)


def decode_data(payload: bytes, hand: str) -> HandFrame:
    device_id, _group, ts = decode_data_header(payload)
    a = np.frombuffer(payload, dtype="<f4", count=JOINT_COUNT * 7, offset=_DATA_HEADER.size)
    a = a.astype(float).reshape(JOINT_COUNT, 7)
    return HandFrame(hand, a[:, :3].copy(), a[:, 3:].copy(), ts, device_id, frame="xr_base")


def encode_data(f: HandFrame, group_id: int = 0) -> bytes:
    if f.frame != "xr_base":
        raise ValueError("RGMP carries xr_base (Y-up) poses; convert before encoding")
    a = np.concatenate([f.positions, f.orientations], axis=1).astype("<f4")
    return _DATA_HEADER.pack(f.device_id, group_id, int(f.timestamp_us)) + a.tobytes()


def encode_disconnect(device_id: int) -> bytes:
    return struct.pack("<I", device_id)


def decode_disconnect(payload: bytes) -> int:
    return struct.unpack("<I", payload)[0]


__all__ = [
    "DEFAULT_PORT",
    "JOINT_NAMES",
    "MSG_DATA",
    "MSG_DEFINITION",
    "MSG_DISCONNECT",
    "decode_data",
    "decode_definition",
    "decode_disconnect",
    "encode_data",
    "encode_definition",
    "encode_disconnect",
    "frame",
    "read_frame",
]
