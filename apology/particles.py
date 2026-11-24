"""
GPU-free particle field: a few thousand glowing points that morph between
3D formations (sphere, heart, broken heart, kintsugi heart, words...).
"""
import math

import numpy as np
import pygame

from . import config as C
from .math3d import rot_x, rot_y, rot_z

# colour slots used by every formation
GOLD, SILVER, BLUE, ICE, GOLD_HI, WHITE = range(6)
# particle colours: golds carry little blue so that stacked glows stay gold, not white
PALETTE = [(236, 158, 38), C.SILVER, C.ROYAL_BLUE, C.ICE_BLUE, (250, 196, 84), C.WHITE_WARM]
_GAIN = [0.8, 1.0, 1.0, 1.0, 0.85, 1.0]
_HOT = [0.15, 0.5, 0.5, 0.5, 0.25, 0.5]

_RNG = np.random.default_rng(1975)


# ============================================================== formations
def sphere(n, r=1.6, rng=_RNG):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    theta = math.pi * (1 + 5 ** 0.5) * i
    rr = r * (1 + rng.normal(0, 0.015, n))
    pts = np.stack([np.cos(theta) * np.sin(phi), np.cos(phi), np.sin(theta) * np.sin(phi)], 1) * rr[:, None]
    cols = rng.choice([SILVER, SILVER, ICE, BLUE, BLUE], n)
    return pts, cols


def rings(n, rng=_RNG):
    """A calm planet of light: a soft core and three tilted orbits."""
    k = int(n * 0.35)
    core, _ = sphere(k, 0.65, rng)
    core *= rng.random((k, 1)) ** 0.25
    rest = n - k
    parts = []
    tilts = [(0.35, 0.0), (-0.5, 0.9), (0.95, -0.45)]
    for j, (tx, tz) in enumerate(tilts):
        m = rest // 3 + (1 if j < rest % 3 else 0)
        a = rng.uniform(0, 2 * math.pi, m)
        rad = 1.2 + 0.28 * j + rng.normal(0, 0.025, m)
        p = np.stack([np.cos(a) * rad, rng.normal(0, 0.02, m), np.sin(a) * rad], 1)
        parts.append(p @ (rot_x(tx) @ rot_z(tz)).T)
    pts = np.concatenate([core] + parts)
    cols = np.concatenate([rng.choice([ICE, BLUE, WHITE], k),
                           rng.choice([SILVER, SILVER, ICE, GOLD], rest)])
    return pts, cols


def dust(n, rng=_RNG):
    """Everything scattered - the moment something breaks."""
    d = rng.normal(0, 1, (n, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    r = 2.0 + rng.random(n) ** 0.6 * 4.5
    pts = d * r[:, None] * np.array([1.4, 0.8, 1.0])
    cols = rng.choice([SILVER, BLUE, BLUE, ICE], n)
    return pts, cols


_HK = 0.1                       # heart scale
_HSHIFT = 2.4 * _HK + 0.1       # keep it optically centred


def _heart_outline(m=420):
    t = np.linspace(0, 2 * math.pi, 4000)
    x = 16 * np.sin(t) ** 3
    y = 13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)
    seg = np.hypot(np.diff(x), np.diff(y))
    arc = np.concatenate([[0], np.cumsum(seg)])
    u = np.linspace(0, arc[-1], m, endpoint=False)
    return np.stack([np.interp(u, arc, x), np.interp(u, arc, y)], 1) * _HK


_OUTLINE = None


def _inside(px, py, poly):
    """Vectorised even-odd point-in-polygon test."""
    x1, y1 = poly[:, 0][None], poly[:, 1][None]
    x2, y2 = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    px, py = px[:, None], py[:, None]
    cond = (y1 > py) != (y2 > py)
    xint = (x2 - x1) * (py - y1) / np.where(y2 - y1 == 0, 1e-9, y2 - y1) + x1
    return (cond & (px < xint)).sum(axis=1) % 2 == 1


def _heart_raw(n, depth=0.62, edge_ratio=0.38, rng=_RNG):
    """Points on / inside a puffy 3D heart. Returns points and 'edge-ness' (0..1)."""
    global _OUTLINE
    if _OUTLINE is None:
        _OUTLINE = _heart_outline()
    poly = _OUTLINE
    ne = int(n * edge_ratio)
    ni = n - ne
    # outline, evenly spaced by arc length, with a little thickness
    e = poly[rng.integers(0, len(poly), ne)] + rng.normal(0, 0.018, (ne, 2))
    # interior by rejection sampling
    lo, hi = poly.min(axis=0), poly.max(axis=0)
    inner = np.empty((0, 2))
    while len(inner) < ni:
        c = lo + rng.random((ni * 2, 2)) * (hi - lo)
        inner = np.concatenate([inner, c[_inside(c[:, 0], c[:, 1], poly)]])
    inner = inner[:ni]
    # distance to the outline -> puffiness
    d = np.sqrt(((inner[:, None, :] - poly[None, ::3, :]) ** 2).sum(-1)).min(axis=1)
    dn = np.clip(d / 0.95, 0, 1)
    puff = np.sqrt(dn * (2 - dn))
    sign = rng.choice([-1.0, 1.0], ni)
    zi = sign * depth * puff * (0.55 + 0.45 * rng.random(ni))
    ze = rng.normal(0, 0.03, ne)
    xy = np.concatenate([e, inner])
    z = np.concatenate([ze, zi])
    pts = np.stack([xy[:, 0], xy[:, 1] + _HSHIFT, z], 1)
    edge = np.concatenate([np.ones(ne), 1 - dn])
    return pts, edge


def heart(n, rng=_RNG):
    pts, s = _heart_raw(n, rng=rng)
    cols = np.where(s > 0.97, rng.choice([SILVER, ICE, ICE], n), rng.choice([BLUE, ICE, BLUE, BLUE], n))
    return pts, cols


# the crack: a zig-zag from the top dip down to the tip
_CRACK_Y = np.array([5.0, 2.6, 0.4, -2.6, -5.6, -9.0, -12.5, -17.0]) * _HK + _HSHIFT
_CRACK_X = np.array([0.0, -0.20, 0.16, -0.14, 0.18, -0.10, 0.08, 0.0])


def crack_x(y):
    return np.interp(-y, -_CRACK_Y, _CRACK_X)


def broken_heart(n, gap=0.55, rng=_RNG):
    pts, s = _heart_raw(n, rng=rng)
    left = pts[:, 0] < crack_x(pts[:, 1])
    pivot = np.array([0.0, -17 * _HK + _HSHIFT, 0.0])
    out = pts.copy()
    for mask, sgn in ((left, -1.0), (~left, 1.0)):
        p = pts[mask] - pivot
        p = p @ rot_z(-sgn * 0.22 * gap).T @ rot_y(sgn * 0.25 * gap).T
        out[mask] = p + pivot + np.array([sgn * gap, -0.12 * gap, -0.2 * gap])
    cols = np.where(s > 0.97, rng.choice([SILVER, ICE, ICE], n), rng.choice([BLUE, BLUE, ICE], n))
    return out, cols


def kintsugi_heart(n, seam_ratio=0.17, rng=_RNG):
    """The heart, mended - the crack filled with gold."""
    m = int(n * seam_ratio)
    body, s = _heart_raw(n - m, rng=rng)
    body_cols = np.where(s > 0.97, rng.choice([SILVER, ICE, SILVER], n - m),
                         rng.choice([BLUE, ICE, BLUE, BLUE], n - m))
    y = rng.uniform(_CRACK_Y[-1], _CRACK_Y[0], m)
    x = crack_x(y) + rng.normal(0, 0.03, m)
    # thickness of the heart at this point, so the seam runs through it
    z = rng.uniform(-1, 1, m) * 0.55 * (0.4 + 0.6 * np.clip((y - _CRACK_Y[-1]) / 1.4, 0, 1))
    seam = np.stack([x, y, z], 1)
    pts = np.concatenate([body, seam])
    cols = np.concatenate([body_cols, rng.choice([GOLD, GOLD, GOLD_HI, GOLD_HI, WHITE], m)])
    return pts, cols


HALO_TILT = rot_x(0.42) @ rot_z(0.18)
HALO_CENTRE = np.array([0.0, 0.15, 0.0])


def axis_rotation(axis, a):
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = math.cos(a), math.sin(a)
    K = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def halo_heart(n, rng=_RNG):
    k = int(n * 0.74)
    hp, hc = kintsugi_heart(k, rng=rng)
    m = n - k
    a = rng.uniform(0, 2 * math.pi, m)
    rad = 2.75 + rng.normal(0, 0.05, m)
    ring = np.stack([np.cos(a) * rad, rng.normal(0, 0.025, m), np.sin(a) * rad], 1)
    ring = ring @ HALO_TILT.T + HALO_CENTRE
    pts = np.concatenate([hp, ring])
    cols = np.concatenate([hc, rng.choice([GOLD, SILVER, GOLD_HI, SILVER], m)])
    orbit = np.concatenate([np.zeros(k, bool), np.ones(m, bool)])
    return pts, cols, orbit


def text_shape(n, text, font, width=6.2, palette=(GOLD, GOLD_HI, SILVER), rng=_RNG, y=0.0):
    surf = font.render(text, True, (255, 255, 255))
    alpha = pygame.surfarray.array_alpha(surf)  # (w, h)
    xs, ys = np.nonzero(alpha > 110)
    w, h = alpha.shape
    pick = rng.integers(0, len(xs), n)
    px = xs[pick] + rng.random(n)
    py = ys[pick] + rng.random(n)
    k = width / w
    pts = np.stack([(px - w / 2) * k, -(py - h / 2) * k + y, rng.normal(0, 0.05, n)], 1)
    cols = rng.choice(list(palette), n)
    return pts, cols


# ============================================================== sprites
class SpriteBank:
    """Pre-rendered additive glow dots: colour x size x brightness."""
    SIZES = np.array([1.2, 1.6, 2.0, 2.5, 3.0, 3.6, 4.3, 5.1, 6.0, 7.2, 8.6, 10.5, 12.6, 15.2])
    LEVELS = 10

    def __init__(self):
        self.sprites = []
        for ci, col in enumerate(PALETTE):
            col = np.array(col, dtype=np.float64) * _GAIN[ci]
            for r in self.SIZES:
                R = int(math.ceil(r * 3.2)) + 1
                yy, xx = np.mgrid[0:2 * R, 0:2 * R]
                d = np.hypot(xx - R + 0.5, yy - R + 0.5)
                core = np.exp(-(d / (r * 0.5)) ** 2) * 0.78
                halo = np.exp(-(d / (r * 1.5)) ** 2) * 0.2
                inten = core + halo
                hot = np.clip(core - 0.55, 0, 1) * _HOT[ci]     # white-hot centre
                for b in range(1, self.LEVELS + 1):
                    lv = b / self.LEVELS
                    rgb = inten[..., None] * col[None, None] * lv + hot[..., None] * 255 * lv * 0.6
                    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
                    s = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
                    self.sprites.append((s, R))
        self.nS = len(self.SIZES)

    def draw(self, screen, cam, pts, cols, size_scale=1.0, fade=1.0, depth_fade=True):
        if fade <= 0.01 or len(pts) == 0:
            return
        x, y, z = cam.project(pts)
        on = (x > -40) & (x < cam.width + 40) & (y > -40) & (y < cam.height + 40)
        x, y, z, cols = x[on], y[on], z[on], cols[on]
        radius = 0.026 * size_scale * cam.focal / z
        si = np.clip(np.searchsorted(self.SIZES, radius), 0, self.nS - 1)
        b = np.full(len(z), fade)
        if depth_fade:
            b = b * np.clip(1.35 - (z - 4.0) / 6.0, 0.25, 1.0)
        bi = np.clip((b * self.LEVELS).astype(np.int32), 0, self.LEVELS - 1)
        idx = (cols * self.nS + si) * self.LEVELS + bi
        spr = self.sprites
        flag = pygame.BLEND_RGB_ADD
        seq = []
        for k, px, py in zip(idx.tolist(), x.tolist(), y.tolist()):
            s, R = spr[k]
            seq.append((s, (px - R, py - R), None, flag))
        screen.blits(seq, doreturn=False)


# ============================================================== the field
class ParticleField:
    def __init__(self, n=C.PARTICLE_COUNT, seed=11):
        self.n = n
        self.rng = np.random.default_rng(seed)
        self.pos = np.zeros((n, 3))
        self.vel = np.zeros((n, 3))
        self.base = np.zeros((n, 3))
        self.col = np.full(n, SILVER)
        self.next_col = self.col.copy()
        self.delay = np.zeros(n)
        self.t_change = 0.0
        self.spin = 0.0
        self.spin_angle = 0.0
        self.pulse = 0.0
        self.turbulence = 0.0
        self.stiffness = 4.0
        self.phase = self.rng.uniform(0, 2 * math.pi, (n, 3))
        self.orbit = np.zeros(n, bool)
        self.orbit_speed = 0.0
        self.orbit_angle = 0.0
        self.shimmer = 0.015

    def place(self, pts, cols):
        self.pos[:] = pts
        self.vel[:] = 0
        self.base[:] = pts
        self.col[:] = cols
        self.next_col[:] = cols

    def burst(self, strength=3.2):
        d = self.pos - self.pos.mean(axis=0)
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-6)
        self.vel = d * strength * (0.4 + self.rng.random((self.n, 1))) + self.rng.normal(0, 0.7, (self.n, 3))

    def set_shape(self, shape, now, stagger=1.4, spin=0.0, pulse=0.0, turbulence=0.0,
                  stiffness=4.0, ordered=True):
        pts, cols = shape[0], shape[1]
        orbit = shape[2] if len(shape) > 2 else np.zeros(len(pts), bool)
        if ordered:
            # match particles to targets by height so morphs flow instead of scramble
            key_old = self.pos[:, 1] + 0.25 * self.pos[:, 0]
            key_new = pts[:, 1] + 0.25 * pts[:, 0]
            o_old = np.argsort(key_old)
            o_new = np.argsort(key_new)
            new_pts = np.empty_like(pts)
            new_cols = np.empty_like(cols)
            new_pts[o_old] = pts[o_new]
            new_cols[o_old] = cols[o_new]
            new_orbit = np.empty_like(orbit)
            new_orbit[o_old] = orbit[o_new]
            pts, cols, orbit = new_pts, new_cols, new_orbit
        self.orbit = orbit
        # undo any spin so the new formation starts facing forward
        self.spin_angle = 0.0
        self.base = pts.copy()
        self.next_col = cols.copy()
        self.delay = self.rng.random(self.n) * stagger
        self.t_change = now
        self.spin = spin
        self.pulse = pulse
        self.turbulence = turbulence
        self.stiffness = stiffness

    @staticmethod
    def heartbeat(t):
        ph = t % 1.25
        return math.exp(-(ph / 0.07) ** 2) + 0.55 * math.exp(-((ph - 0.26) / 0.08) ** 2)

    def update(self, dt, now):
        dt = min(dt, 1 / 30)
        self.spin_angle += self.spin * dt
        tgt = self.base
        if self.orbit_speed and self.orbit.any():
            self.orbit_angle += self.orbit_speed * dt
            Rm = axis_rotation(HALO_TILT @ np.array([0.0, 1.0, 0.0]), self.orbit_angle)
            tgt = tgt.copy()
            tgt[self.orbit] = (tgt[self.orbit] - HALO_CENTRE) @ Rm.T + HALO_CENTRE
        if self.spin_angle:
            tgt = tgt @ rot_y(self.spin_angle).T
        if self.pulse:
            tgt = tgt * (1.0 + self.pulse * self.heartbeat(now))

        active = (now - self.t_change) >= self.delay
        self.col = np.where(active, self.next_col, self.col)

        k = self.stiffness
        c = 2.0 * math.sqrt(k) * 0.72
        acc = (k * (tgt - self.pos) - c * self.vel) * active[:, None]
        acc -= self.vel * (0.9 * ~active)[:, None]
        if self.turbulence:
            p = self.pos
            acc[:, 0] += np.sin(p[:, 1] * 1.3 + now * 0.7 + self.phase[:, 0]) * self.turbulence
            acc[:, 1] += np.sin(p[:, 2] * 1.1 + now * 0.9 + self.phase[:, 1]) * self.turbulence
            acc[:, 2] += np.sin(p[:, 0] * 1.2 + now * 0.6 + self.phase[:, 2]) * self.turbulence
        self.vel += acc * dt
        self.pos += self.vel * dt

    def render_points(self, now, view):
        """World positions with a gentle shimmer, rotated by the view matrix."""
        jitter = np.sin(now * 1.7 + self.phase) * self.shimmer
        return (self.pos + jitter) @ view.T


# ============================================================== starfield
class Starfield:
    def __init__(self, n=520, seed=3):
        rng = np.random.default_rng(seed)
        self.pts = np.stack([rng.uniform(-16, 16, n), rng.uniform(-9, 9, n), rng.uniform(-26, 3, n)], 1)
        self.cols = rng.choice([SILVER, ICE, ICE, BLUE, WHITE, GOLD], n)
        self.tw = rng.uniform(0, 2 * math.pi, n)
        self.speed = 0.35

    def update(self, dt):
        self.pts[:, 2] += self.speed * dt
        wrap = self.pts[:, 2] > 3
        self.pts[wrap, 2] -= 29

    def draw(self, bank, screen, cam, now, view, fade=1.0):
        pts = self.pts @ view.T
        tw = 0.55 + 0.45 * np.sin(now * 1.3 + self.tw)
        # draw in two brightness groups to get a little twinkle
        for lo, hi, f in ((0.0, 0.6, 0.45), (0.6, 1.01, 0.8)):
            m = (tw >= lo) & (tw < hi)
            bank.draw(screen, cam, pts[m], self.cols[m], size_scale=0.42, fade=fade * f)
