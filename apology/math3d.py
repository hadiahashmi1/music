"""Small 3D maths toolkit: rotations, projection and easing curves."""
import math

import numpy as np


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def normalize(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


class Camera:
    """A pinhole camera sitting on +Z looking toward the origin."""

    def __init__(self, width, height, fov_deg=40.0, distance=7.0):
        self.distance = distance
        self.resize(width, height, fov_deg)

    def resize(self, width, height, fov_deg=40.0):
        self.width, self.height = width, height
        self.cx, self.cy = width / 2.0, height / 2.0
        self.focal = (height / 2.0) / math.tan(math.radians(fov_deg) / 2.0)

    @property
    def position(self):
        return np.array([0.0, 0.0, self.distance])

    def project(self, pts, cx=None, cy=None, focal=None):
        """Return screen x, y and view depth for an (N, 3) array."""
        cx = self.cx if cx is None else cx
        cy = self.cy if cy is None else cy
        f = self.focal if focal is None else focal
        z = np.maximum(self.distance - pts[:, 2], 0.05)
        inv = f / z
        return cx + pts[:, 0] * inv, cy - pts[:, 1] * inv, z


# ----------------------------------------------------------------- easing
def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def smoothstep(a, b, x):
    t = clamp01((x - a) / (b - a)) if b != a else float(x >= b)
    return t * t * (3 - 2 * t)


def ease_in_out(t):
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t, s=1.70158):
    t = clamp01(t) - 1
    return 1 + t * t * ((s + 1) * t + s)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))
