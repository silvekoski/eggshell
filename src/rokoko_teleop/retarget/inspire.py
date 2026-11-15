"""HandAngles -> Inspire RH56 dexterous hand commands.

The Inspire hand (on the Unitree G1 at the venue, and the subject of the
Aalto Robotics Club integration) has 6 actuators, each commanded with an
"angle" from 0 (closed) to 1000 (open), in this order:
little, ring, middle, index, thumb bend, thumb rotation.

This is a curl-per-finger map, so the same glove stream that drives the
simulated Shadow hand can drive the real Inspire hand. Unverified on
hardware: check direction and range with the Aalto integration first.
"""

from __future__ import annotations

import numpy as np

from ..hand_model import HandAngles

ORDER = ("little", "ring", "middle", "index", "thumb_bend", "thumb_rotation")

# Angle sums that count as fully curled.
FINGER_FULL_CURL = 1.45 + 1.6  # MCP + PIP of a fist
THUMB_FULL_BEND = 0.6 + 0.5  # thumb MCP + IP of a fist
THUMB_FULL_ROTATION = 0.9  # thumb CMC flexion across the palm


def _open_value(curl: float) -> int:
    return int(round(1000 * (1.0 - float(np.clip(curl, 0.0, 1.0)))))


def inspire_command(a: HandAngles) -> list[int]:
    cmd = []
    for f in ("little", "ring", "middle", "index"):
        cmd.append(_open_value((a[f"{f}_mcp_flex"] + a[f"{f}_pip"]) / FINGER_FULL_CURL))
    cmd.append(_open_value((a["thumb_mcp"] + a["thumb_ip"]) / THUMB_FULL_BEND))
    cmd.append(_open_value(a["thumb_cmc_flex"] / THUMB_FULL_ROTATION))
    return cmd
