"""Quaternion helpers. Convention: (x, y, z, w), the order Rokoko's RGMP
stream and ROS geometry_msgs use. MuJoCo uses (w, x, y, z): convert with
`to_wxyz` / `from_wxyz` at the MuJoCo boundary only."""

from __future__ import annotations

import math

import numpy as np

IDENTITY = np.array([0.0, 0.0, 0.0, 1.0])


def normalize(q) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    return q / np.linalg.norm(q)


def mul(a, b) -> np.ndarray:
    """Hamilton product: rotating by the result applies b first, then a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array(
        [
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ]
    )


def conj(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([-x, -y, -z, w])


def rotate(q, v) -> np.ndarray:
    """Rotate vector v by unit quaternion q."""
    qv = np.asarray(q[:3], dtype=float)
    w = float(q[3])
    v = np.asarray(v, dtype=float)
    t = 2.0 * np.cross(qv, v)
    return v + w * t + np.cross(qv, t)


def axis_angle(axis, angle: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    s = math.sin(angle / 2.0)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0)])


def rx(a: float) -> np.ndarray:
    return axis_angle((1.0, 0.0, 0.0), a)


def ry(a: float) -> np.ndarray:
    return axis_angle((0.0, 1.0, 0.0), a)


def rz(a: float) -> np.ndarray:
    return axis_angle((0.0, 0.0, 1.0), a)


def to_matrix(q) -> np.ndarray:
    x, y, z, w = normalize(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def from_matrix(m) -> np.ndarray:
    m = np.asarray(m, dtype=float)
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    return normalize([x, y, z, w])


def to_wxyz(q) -> np.ndarray:
    return np.array([q[3], q[0], q[1], q[2]], dtype=float)


def from_wxyz(q) -> np.ndarray:
    return np.array([q[1], q[2], q[3], q[0]], dtype=float)


def slerp(a, b, t: float) -> np.ndarray:
    a = normalize(a)
    b = normalize(b)
    dot = float(np.dot(a, b))
    if dot < 0.0:
        b = -b
        dot = -dot
    if dot > 0.9995:
        return normalize(a + t * (b - a))
    theta = math.acos(dot)
    return (math.sin((1 - t) * theta) * a + math.sin(t * theta) * b) / math.sin(theta)


def angle_between(a, b) -> float:
    """Rotation angle (radians, 0..pi) taking a to b."""
    d = abs(float(np.dot(normalize(a), normalize(b))))
    return 2.0 * math.acos(min(1.0, d))
