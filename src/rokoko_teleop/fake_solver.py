"""A stand-in for `rkk-hand-solver`: serves RGMP v2 on TCP 12277 from the
scripted operator or a recording.

Lets everything downstream of the gloves be exercised with no hardware:
our `RgmpSource`, and also Rokoko's own ROS 2 bridge
(`ros2 launch rkk_hand_bringup smartglove_hands.launch.py spawn_solver:=false`).
"""

from __future__ import annotations

import socket
import threading
import time

import numpy as np

from . import quat as Q
from . import rgmp
from .sources import Source
from .xrhand import XR_BASE_TO_ZUP, HandDefinition, HandFrame

ZUP_TO_XR_BASE = Q.conj(XR_BASE_TO_ZUP)


def to_xr_base(f: HandFrame) -> HandFrame:
    """Undo the Y-up -> Z-up rotation, so frames look like raw solver output."""
    if f.frame == "xr_base":
        return f
    R = Q.to_matrix(ZUP_TO_XR_BASE)
    pos = f.positions @ R.T
    ori = [Q.normalize(Q.mul(ZUP_TO_XR_BASE, q)) for q in f.orientations]
    return HandFrame(f.hand, pos, np.array(ori), f.timestamp_us, f.device_id, frame="xr_base")


class FakeSolver:
    def __init__(self, source: Source, host: str = "127.0.0.1", port: int = rgmp.DEFAULT_PORT,
                 rate_hz: float = 60.0, loop: bool = True, device_id: int = 843143769):
        self.source, self.rate_hz, self.loop, self.device_id = source, rate_hz, loop, device_id
        self._srv = socket.create_server((host, port), reuse_port=False)
        self.port = self._srv.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)

    def start(self) -> "FakeSolver":
        self._thread.start()
        return self

    def _accept(self) -> None:
        self._srv.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        first = self.source.get(0.0)
        hand = first.hand if first is not None else "right"
        defn = HandDefinition(device_id=self.device_id, hand=hand, timestamp_epoch="unix_epoch", group_id=0)
        start = time.monotonic()
        try:
            conn.sendall(rgmp.frame(rgmp.MSG_DEFINITION, rgmp.encode_definition(defn)))
            period = 1.0 / self.rate_hz
            while not self._stop.is_set():
                t = time.monotonic() - start
                dur = self.source.duration
                if dur and t > dur:
                    if not self.loop:
                        break
                    t = t % dur
                f = self.source.get(t)
                if f is not None:
                    raw = to_xr_base(f)
                    raw.device_id = self.device_id
                    raw.timestamp_us = int(time.time() * 1e6)
                    conn.sendall(rgmp.frame(rgmp.MSG_DATA, rgmp.encode_data(raw, group_id=0)))
                time.sleep(period)
            conn.sendall(rgmp.frame(rgmp.MSG_DISCONNECT, rgmp.encode_disconnect(self.device_id)))
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self) -> None:
        self._stop.set()
        self._srv.close()
