"""
A fully procedural 3D padlock: a gold body with rounded edges, a polished
silver shackle, an engraved front plate and a keyhole.

Rendered with a tiny software rasteriser (numpy + pygame polygons),
supersampled 2x for clean anti-aliased edges, and lit with an image-based
"studio" environment so the metal reads like real gold and chrome.
"""
import math

import numpy as np
import pygame

from . import config as C
from .math3d import normalize, rot_x, rot_y, rot_z

SS = 2  # supersampling factor

# Material tints (linear-ish 0..1)
GOLD_TINT = np.array([1.00, 0.76, 0.33])
SILVER_TINT = np.array([0.86, 0.90, 0.97])


def _edge_coords(h, r, k_edge=5, k_mid=5):
    """Grid coordinates along one axis of a rounded box face."""
    phi = np.linspace(math.pi / 4, 0.0, k_edge)
    left = -(h - r) - r * np.tan(phi)
    mid = np.linspace(-(h - r), h - r, k_mid + 2)[1:-1]
    right = -left[::-1]
    return np.concatenate([left, mid, right])


def _rounded_box(hx, hy, hz, r):
    """Quads (Q, 4, 3) of a rounded box via a Minkowski cube->sphere map."""
    half = np.array([hx, hy, hz])
    inner = half - r
    coords = [_edge_coords(h, r) for h in half]
    quads = []
    for axis in range(3):
        u, v = [a for a in range(3) if a != axis]
        for sign in (-1.0, 1.0):
            cu, cv = coords[u], coords[v]
            gu, gv = np.meshgrid(cu, cv, indexing="ij")
            p = np.zeros(gu.shape + (3,))
            p[..., axis] = sign * half[axis]
            p[..., u] = gu
            p[..., v] = gv
            q = np.clip(p, -inner, inner)
            n = normalize(p - q)
            p = q + r * n
            a = p[:-1, :-1]
            b = p[1:, :-1]
            c = p[1:, 1:]
            d = p[:-1, 1:]
            quads.append(np.stack([a, b, c, d], axis=2).reshape(-1, 4, 3))
    quads = np.concatenate(quads)
    # make every quad wind outward
    nrm = np.cross(quads[:, 1] - quads[:, 0], quads[:, 2] - quads[:, 0])
    cen = quads.mean(axis=1)
    flip = np.einsum("ij,ij->i", nrm, cen) < 0
    quads[flip] = quads[flip][:, ::-1]
    return quads


def _shackle(body_top, radius, leg_h, tube, sides=18):
    """Tube swept along a U path. Returns quads, the bottom cap and the path."""
    path = []
    y_top = body_top + leg_h
    for y in np.linspace(body_top - 0.02, y_top, 10):           # short (left) leg
        path.append((-radius, y, 0.0))
    for a in np.linspace(math.pi, 0.0, 36)[1:-1]:                 # the arch
        path.append((radius * math.cos(a), y_top + radius * math.sin(a), 0.0))
    for y in np.linspace(y_top, body_top - 0.9, 22):              # long (right) leg
        path.append((radius, y, 0.0))
    path = np.array(path)
    tang = np.gradient(path, axis=0)
    tang = normalize(tang)
    nrm = np.stack([-tang[:, 1], tang[:, 0], np.zeros(len(path))], axis=1)
    bin_ = np.array([0.0, 0.0, 1.0])
    ang = np.linspace(0, 2 * math.pi, sides + 1)[:-1]
    rings = (path[:, None, :]
             + tube * (np.cos(ang)[None, :, None] * nrm[:, None, :]
                       + np.sin(ang)[None, :, None] * bin_[None, None, :]))
    quads = []
    for i in range(len(path) - 1):
        for j in range(sides):
            k = (j + 1) % sides
            quads.append([rings[i, j], rings[i + 1, j], rings[i + 1, k], rings[i, k]])
    quads = np.array(quads)
    # outward winding (relative to the tube centre line)
    centre = np.repeat((path[:-1] + path[1:]) / 2, sides, axis=0)
    nn = np.cross(quads[:, 1] - quads[:, 0], quads[:, 2] - quads[:, 0])
    flip = np.einsum("ij,ij->i", nn, quads.mean(axis=1) - centre) < 0
    quads[flip] = quads[flip][:, ::-1]
    cap = rings[0][::-1].copy()
    return quads, cap, path


def _keyhole(cx, cy, z, s=1.0):
    pts = []
    r = 0.12 * s
    for a in np.linspace(math.radians(-62), math.radians(242), 26):
        pts.append((cx + r * math.cos(a), cy + 0.05 * s + r * math.sin(a), z))
    pts.append((cx - 0.065 * s, cy - 0.30 * s, z))
    pts.append((cx + 0.065 * s, cy - 0.30 * s, z))
    pts = np.array(pts)
    return pts[::-1]  # counter-clockwise for consistency


def _rounded_rect_outline(hx, hy, r, z, n=8):
    pts = []
    corners = [(hx - r, hy - r, 0), (-hx + r, hy - r, 90), (-hx + r, -hy + r, 180), (hx - r, -hy + r, 270)]
    for cx, cy, start in corners:
        for a in np.linspace(math.radians(start), math.radians(start + 90), n):
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
    pts.append(pts[0])
    return np.array(pts)


def _circle(cx, cy, cz, r, n=20, axis="y"):
    a = np.linspace(0, 2 * math.pi, n + 1)[:-1]
    if axis == "y":
        return np.stack([cx + r * np.cos(a), np.full(n, cy), cz + r * np.sin(a)], axis=1)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a), np.full(n, cz)], axis=1)


# ------------------------------------------------------------------ lighting
_ENV_LOW = np.array([0.10, 0.13, 0.26])
_ENV_HIGH = np.array([0.78, 0.84, 0.98])
_KEY_LIGHT = np.array([-2.5, 3.0, 5.0])
_FILL_LIGHT = np.array([5.0, -1.0, 3.0])


def shade(centroids, normals, tint, cam_pos, glow=0.0):
    V = normalize(cam_pos - centroids)
    N = normals
    ndv = np.clip(np.einsum("ij,ij->i", N, V), 0.0, 1.0)

    # environment reflection: dark navy floor, bright studio sky with a strip light
    R = -V + 2.0 * ndv[:, None] * N
    ry = R[:, 1]
    t = np.clip((ry + 0.55) / 1.3, 0.0, 1.0)
    t = t * t * (3 - 2 * t)
    env = _ENV_LOW[None] * (1 - t[:, None]) + _ENV_HIGH[None] * t[:, None]
    strip = np.exp(-((ry - 0.42) / 0.11) ** 2) * 1.1
    side = np.exp(-((R[:, 0] + 0.55) / 0.18) ** 2) * np.clip(ry + 0.6, 0, 1) * 0.45
    env = env + (strip + side)[:, None]

    L1 = normalize(_KEY_LIGHT[None] - centroids)
    L2 = normalize(_FILL_LIGHT[None] - centroids)
    d1 = np.clip(np.einsum("ij,ij->i", N, L1), 0, 1)
    d2 = np.clip(np.einsum("ij,ij->i", N, L2), 0, 1)
    H1 = normalize(L1 + V)
    nh = np.clip(np.einsum("ij,ij->i", N, H1), 0, 1)
    s1 = nh ** 80 + 0.22 * nh ** 10

    fres = (1.0 - ndv) ** 3
    sweep = 0.5 + 0.5 * np.tanh(-R[:, 0] * 2.2 + R[:, 1] * 1.4)
    env = env * (0.55 + 0.75 * sweep[:, None])
    col = (tint[None] * (0.14 + 0.62 * d1[:, None] + 0.16 * d2[:, None])
           + tint[None] * env * 0.95
           + s1[:, None] * np.array([1.0, 0.97, 0.9]) * 1.3
           + fres[:, None] * np.array([0.18, 0.36, 0.85]) * 0.55)
    if glow:
        col = col + glow * np.array([1.0, 0.8, 0.4]) * 0.6
    # filmic-ish tone curve
    col = col / (1.0 + 0.35 * col) * 1.25
    return np.clip(col * 255.0, 0, 255).astype(np.int32)


class Padlock:
    HX, HY, HZ, R = 1.0, 0.78, 0.42, 0.24
    ARCH_R, LEG_H, TUBE = 0.62, 0.55, 0.14

    def __init__(self):
        self.body = _rounded_box(self.HX, self.HY, self.HZ, self.R)
        self.shackle, self.cap, _ = _shackle(self.HY, self.ARCH_R, self.LEG_H, self.TUBE)
        zf = self.HZ + 0.004
        self.keyhole = _keyhole(0.0, -0.08, zf + 0.002)
        self.keyhole_rim = _keyhole(0.0, -0.08, zf + 0.001, s=1.42)
        self.plate = _rounded_rect_outline(self.HX - 0.13, self.HY - 0.13, 0.12, zf)
        self.plate2 = _rounded_rect_outline(self.HX - 0.17, self.HY - 0.17, 0.09, zf)
        self.hole_l = _circle(-self.ARCH_R, self.HY + 0.003, 0.0, self.TUBE * 1.12)
        self.hole_r = _circle(self.ARCH_R, self.HY + 0.003, 0.0, self.TUBE * 1.12)
        self.glow_cache = {}

    # -------------------------------------------------------------- transforms
    @staticmethod
    def model(yaw, pitch, roll=0.0):
        return rot_y(yaw) @ rot_x(pitch) @ rot_z(roll)

    def shackle_local(self, pts, lift, swivel):
        p = pts.copy()
        p[..., 1] += lift
        if swivel:
            piv = np.array([self.ARCH_R, 0.0, 0.0])
            p = (p - piv) @ rot_y(swivel).T + piv
        return p

    def to_world(self, pts, M, scale, offset):
        return (pts * scale) @ M.T + offset

    # -------------------------------------------------------------- sampling
    def sample_points(self, n, M, scale, offset, lift=0.0, swivel=0.0, rng=None):
        """Points on the lock's surface (world space) + colour indices,
        used to turn the lock into particles."""
        rng = rng or np.random.default_rng(7)
        n_sh = int(n * 0.28)
        n_bd = n - n_sh
        sh = self.shackle_local(self.shackle, lift, swivel)
        keep = sh.mean(axis=1)[:, 1] > self.HY
        sh = sh[keep]
        pts = []
        for quads, cnt in ((self.body, n_bd), (sh, n_sh)):
            area = np.linalg.norm(np.cross(quads[:, 2] - quads[:, 0], quads[:, 3] - quads[:, 1]), axis=1)
            idx = rng.choice(len(quads), cnt, p=area / area.sum())
            q = quads[idx]
            u = rng.random((cnt, 1))
            v = rng.random((cnt, 1))
            p = (q[:, 0] * (1 - u) * (1 - v) + q[:, 1] * u * (1 - v)
                 + q[:, 2] * u * v + q[:, 3] * (1 - u) * v)
            pts.append(p)
        pts = self.to_world(np.concatenate(pts), M, scale, offset)
        cols = np.concatenate([
            rng.choice([0, 0, 0, 4], n_bd),      # gold / bright gold
            rng.choice([1, 1, 3], n_sh),         # silver / ice
        ])
        return pts, cols

    # -------------------------------------------------------------- drawing
    def _glow_sprite(self, radius, color, level=1.0):
        """Additive glow sprite with the colour pre-multiplied by `level`."""
        q = max(0, min(32, int(round(level * 32))))
        key = (radius, color, q)
        if key not in self.glow_cache:
            size = radius * 2
            yy, xx = np.mgrid[0:size, 0:size]
            d = np.hypot(xx - radius + 0.5, yy - radius + 0.5) / radius
            a = (np.clip(1 - d, 0, 1) ** 2.2) * (q / 32.0)
            rgb = (a[..., None] * np.array(color)[None, None, :]).astype(np.uint8)
            self.glow_cache[key] = pygame.surfarray.make_surface(rgb.transpose(1, 0, 2))
        return self.glow_cache[key]

    def draw(self, screen, cam, yaw, pitch, roll=0.0, scale=0.8, offset=(0, 0, 0),
             lift=0.0, swivel=0.0, glow=0.0, alpha=255, region=820):
        offset = np.asarray(offset, dtype=np.float64)
        M = self.model(yaw, pitch, roll)
        cam_pos = cam.position

        # where on screen does the lock sit?
        sx, sy, _ = cam.project(offset[None])
        left = int(sx[0] - region / 2)
        top = int(sy[0] - region / 2)
        S = region * SS
        cx = (cam.cx - left) * SS
        cy = (cam.cy - top) * SS
        f = cam.focal * SS

        # soft halo behind the lock
        halo_r = int(region * 0.42)
        halo = self._glow_sprite(halo_r, C.ROYAL_BLUE, 0.30 * alpha / 255)
        screen.blit(halo, (sx[0] - halo_r, sy[0] - halo_r), special_flags=pygame.BLEND_RGB_ADD)
        if glow > 0:
            g = self._glow_sprite(int(region * 0.42), C.GOLD_DEEP, min(1.0, glow) * alpha / 255)
            gr = g.get_width() // 2
            screen.blit(g, (sx[0] - gr, sy[0] - gr), special_flags=pygame.BLEND_RGB_ADD)

        layer = pygame.Surface((S, S), pygame.SRCALPHA)

        def proj(world):
            flat = world.reshape(-1, 3)
            x, y, z = cam.project(flat, cx, cy, f)
            return np.stack([x, y], axis=1).reshape(world.shape[:-1] + (2,)), z

        # ---------------- body (convex => back-face culling is enough)
        body_w = self.to_world(self.body, M, scale, offset)
        cen = body_w.mean(axis=1)
        nrm = normalize(np.cross(body_w[:, 1] - body_w[:, 0], body_w[:, 2] - body_w[:, 0]))
        vis = np.einsum("ij,ij->i", nrm, cam_pos[None] - cen) > 0
        cols = shade(cen[vis], nrm[vis], GOLD_TINT, cam_pos, glow)
        p2, _ = proj(body_w[vis])
        draw_poly = pygame.draw.polygon
        for poly, col in zip(p2, cols):
            draw_poly(layer, col, poly)

        # ---------------- front plate decals
        front_n = M @ np.array([0.0, 0.0, 1.0])
        front_c = M @ np.array([0.0, 0.0, self.HZ]) * scale + offset
        if np.dot(front_n, cam_pos - front_c) > 0:
            for outline, col in ((self.plate, (120, 82, 26)), (self.plate2, (255, 226, 160))):
                pts, _ = proj(self.to_world(outline, M, scale, offset))
                pygame.draw.lines(layer, col, False, pts, SS)
            rim_col = tuple(int(c) for c in shade(front_c[None], front_n[None], SILVER_TINT, cam_pos)[0])
            pts, _ = proj(self.to_world(self.keyhole_rim, M, scale, offset))
            draw_poly(layer, rim_col, pts)
            pts, _ = proj(self.to_world(self.keyhole, M, scale, offset))
            draw_poly(layer, (4, 8, 20), pts)

        # ---------------- holes on top
        top_n = M @ np.array([0.0, 1.0, 0.0])
        top_c = M @ np.array([0.0, self.HY, 0.0]) * scale + offset
        if np.dot(top_n, cam_pos - top_c) > 0:
            for hole in (self.hole_l, self.hole_r):
                pts, _ = proj(self.to_world(hole, M, scale, offset))
                draw_poly(layer, (10, 8, 6), pts)

        # ---------------- shackle (sorted back to front)
        sh = self.shackle_local(self.shackle, lift, swivel)
        keep = sh.mean(axis=1)[:, 1] > self.HY + 0.005
        sh = sh[keep]
        sh_w = self.to_world(sh, M, scale, offset)
        cen = sh_w.mean(axis=1)
        nrm = normalize(np.cross(sh_w[:, 1] - sh_w[:, 0], sh_w[:, 2] - sh_w[:, 0]))
        vis = np.einsum("ij,ij->i", nrm, cam_pos[None] - cen) > 0
        sh_w, cen, nrm = sh_w[vis], cen[vis], nrm[vis]
        order = np.argsort(cen[:, 2])  # far (small z) first
        cols = shade(cen[order], nrm[order], SILVER_TINT, cam_pos, glow * 0.6)
        p2, _ = proj(sh_w[order])
        for poly, col in zip(p2, cols):
            draw_poly(layer, col, poly)
        if lift > 0.02:
            cap_w = self.to_world(self.shackle_local(self.cap, lift, swivel), M, scale, offset)
            cap_c = cap_w.mean(axis=0)
            cap_n = normalize(np.cross(cap_w[1] - cap_w[0], cap_w[2] - cap_w[0]))
            if np.dot(cap_n, cam_pos - cap_c) > 0:
                col = shade(cap_c[None], cap_n[None], SILVER_TINT, cam_pos)[0]
                pts, _ = proj(cap_w)
                draw_poly(layer, tuple(int(c) for c in col), pts)

        small = pygame.transform.smoothscale(layer, (region, region))
        if alpha < 255:
            small.set_alpha(alpha)
        screen.blit(small, (left, top))
        return M
