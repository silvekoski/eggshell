"""RGMP v2 wire format, checked against the byte layout in Rokoko's bridge
(rkk_hand_bridge/rgmp.py and its tests), and the TCP path end to end."""

import io
import json
import struct
import time

import numpy as np
import pytest

from rokoko_teleop import quat as Q
from rokoko_teleop import rgmp
from rokoko_teleop.fake_solver import FakeSolver
from rokoko_teleop.hand_model import POSES, forward
from rokoko_teleop.retarget.human import extract_angles
from rokoko_teleop.sources import RgmpSource, SyntheticSource
from rokoko_teleop.synth import Key, ScriptedOperator
from rokoko_teleop.xrhand import JOINT_NAMES, HandDefinition


class RecvSocket:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    def recv(self, n):
        return self._buf.read(n)


def upstream_definition(groups, hand="right"):
    """The JSON shape the solver sends (as in the bridge's test fixtures)."""
    return json.dumps({
        "device_id": 7, "device_type": "solved_hand", "timestamp_epoch": "unix_epoch",
        "device_info": {"hand": hand},
        "static_data": [{"custom_label": "joint_radius", "target_frame": "xr_palm", "value": 0.025}],
        "groups": groups,
    }).encode()


def openxr_group(names=JOINT_NAMES):
    return {"name": "joints_openxr", "streams": [{"target_frame": f"xr_{n}"} for n in names]}


def test_framing_round_trip_and_truncation():
    sock = RecvSocket(rgmp.frame(2, b"hello"))
    assert rgmp.read_frame(sock) == (2, b"hello")
    with pytest.raises(EOFError):
        rgmp.read_frame(RecvSocket(b"\x00\x00"))


def test_definition_uses_group_index_unless_stated():
    d = rgmp.decode_definition(upstream_definition([{"name": "joints_local", "streams": []}, openxr_group()]))
    assert d.group_id == 1 and d.hand == "right" and d.joint_names == JOINT_NAMES
    assert d.joint_radii[0] == 0.025
    g = openxr_group()
    g["group_id"] = 9
    assert rgmp.decode_definition(upstream_definition([g])).group_id == 9


def test_definition_rejects_other_devices_and_short_groups():
    assert rgmp.decode_definition(json.dumps({"device_type": "smartgloves"}).encode()) is None
    assert rgmp.decode_definition(upstream_definition([openxr_group(JOINT_NAMES[:20])])) is None


def test_definition_encode_decode_round_trip():
    d = HandDefinition(device_id=42, hand="left", group_id=3)
    back = rgmp.decode_definition(rgmp.encode_definition(d))
    assert (back.device_id, back.hand, back.group_id, back.joint_names) == (42, "left", 3, JOINT_NAMES)


def test_data_matches_upstream_byte_layout():
    payload = struct.pack("<IIQ", 7, 1, 1_234_567)
    for i in range(26):
        payload += struct.pack("<7f", float(i), 0.5, -0.25, 0.0, 0.0, 0.0, 1.0)
    f = rgmp.decode_data(payload, "right")
    assert (f.device_id, f.timestamp_us, f.frame) == (7, 1_234_567, "xr_base")
    assert f.positions[3].tolist() == [3.0, 0.5, -0.25]
    assert f.orientations[3].tolist() == [0.0, 0.0, 0.0, 1.0]
    assert rgmp.encode_data(f, group_id=1) == payload


def test_disconnect_round_trip():
    assert rgmp.decode_disconnect(rgmp.encode_disconnect(843143769)) == 843143769


def test_fake_solver_to_rgmp_client_over_tcp():
    """Scripted operator -> fake rkk-hand-solver (TCP) -> RgmpSource -> angles."""
    hold = ScriptedOperator([Key(0.0, (0.1, 0.0, 0.2), "pinch"), Key(10.0, (0.1, 0.0, 0.2), "pinch")])
    solver = FakeSolver(SyntheticSource(hold), port=0, rate_hz=120).start()
    src = RgmpSource("127.0.0.1", solver.port, hand="right")
    try:
        deadline = time.monotonic() + 5
        f = None
        while f is None and time.monotonic() < deadline:
            f = src.get(0.0)
            time.sleep(0.02)
        assert f is not None, "no frame over TCP"
        assert src.frames_received > 0 and f.frame == "zup"
        assert np.allclose(extract_angles(f).values, POSES["pinch"].values, atol=1e-4)
        # Position came back through Y-up -> Z-up unchanged.
        assert np.allclose(f.pose("wrist")[0], [0.1, 0.0, 0.2], atol=1e-5)
    finally:
        src.close()
        solver.stop()


def test_quaternion_helpers_agree_with_matrices():
    rng = np.random.default_rng(1)
    for _ in range(50):
        q = Q.normalize(rng.normal(size=4))
        v = rng.normal(size=3)
        assert np.allclose(Q.rotate(q, v), Q.to_matrix(q) @ v)
        assert Q.angle_between(Q.from_matrix(Q.to_matrix(q)), q) < 1e-6
        r = Q.normalize(rng.normal(size=4))
        assert np.allclose(Q.to_matrix(Q.mul(q, r)), Q.to_matrix(q) @ Q.to_matrix(r))
    assert forward(POSES["open"]).positions.shape == (26, 3)
