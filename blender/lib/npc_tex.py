"""Procedural 3D texture functions (numpy) for NPC texture synthesis (owner: creatures).

All functions take P (N,3) object-space points in metres and return (N,) arrays.
Patterns are evaluated in 3D so UV seams never show.
"""
from __future__ import annotations

import numpy as np

_M1, _M2, _M3 = np.int64(73856093), np.int64(19349663), np.int64(83492791)


def _hash(ix, iy, iz, seed=0):
    h = (ix * _M1) ^ (iy * _M2) ^ (iz * _M3) ^ np.int64(seed * 2654435761 % (2 ** 31))
    h = (h ^ (h >> 13)) * np.int64(1274126177)
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def vnoise(P, freq=1.0, seed=0):
    """Smooth value noise in [-1, 1]."""
    q = P * freq
    i = np.floor(q).astype(np.int64)
    f = q - i
    u = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        wx = u[:, 0] if dx else 1 - u[:, 0]
        for dy in (0, 1):
            wy = u[:, 1] if dy else 1 - u[:, 1]
            for dz in (0, 1):
                wz = u[:, 2] if dz else 1 - u[:, 2]
                out = out + wx * wy * wz * _hash(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz, seed)
    return out * 2 - 1


def fbm(P, freq=1.0, octaves=4, seed=0, lac=2.03, gain=0.5):
    s = 0.0
    a = 1.0
    tot = 0.0
    for o in range(octaves):
        s = s + a * vnoise(P, freq, seed + o * 31)
        tot += a
        a *= gain
        freq *= lac
    return s / tot


def ridged(P, freq=1.0, octaves=3, seed=0):
    return 1.0 - np.abs(fbm(P, freq, octaves, seed))


def aniso(P, axis, freq_across, freq_along, seed=0, octaves=2):
    """Noise stretched along `axis` (unit vector or (N,3)): strands, wood grain, brushed metal."""
    axis = np.asarray(axis, np.float64)
    if axis.ndim == 1:
        axis = np.broadcast_to(axis, P.shape)
    along = np.einsum("ij,ij->i", P, axis)
    Q = (P - along[:, None] * axis) * freq_across + (along * freq_along)[:, None] * axis
    return fbm(Q, 1.0, octaves, seed)


def cells(P, size, seed=0, jitter=0.8):
    """Jittered-grid cellular noise: (F1 distance, cell random id in [0,1), nearest feature point)."""
    q = P / size
    i = np.floor(q).astype(np.int64)
    best = np.full(len(P), 1e9)
    bid = np.zeros(len(P))
    bpt = np.zeros_like(P)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = i + np.array([dx, dy, dz])
                jx = _hash(c[:, 0], c[:, 1], c[:, 2], seed)
                jy = _hash(c[:, 0], c[:, 1], c[:, 2], seed + 1)
                jz = _hash(c[:, 0], c[:, 1], c[:, 2], seed + 2)
                fp = c + 0.5 + (np.stack([jx, jy, jz], 1) - 0.5) * jitter
                d = np.linalg.norm(q - fp, axis=1)
                m = d < best
                best = np.where(m, d, best)
                bid = np.where(m, _hash(c[:, 0], c[:, 1], c[:, 2], seed + 7), bid)
                bpt[m] = fp[m] * size
    return best * size, bid, bpt


def mix(a, b, t):
    t = np.asarray(t)
    if np.ndim(a) and np.ndim(t) == 1 and np.ndim(a) == 2:
        t = t[:, None]
    elif np.ndim(t) == 1 and np.ndim(b) == 2:
        t = t[:, None]
    return a + (b - a) * t


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def col(hex_or_rgb):
    """sRGB hex/tuple -> linear RGB numpy (3,)."""
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        rgb = np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    else:
        rgb = np.asarray(hex_or_rgb, np.float64)
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def weave_height(P, T, B, pitch=0.0012, axis_u=None, axis_v=None):
    """Plain-weave height field. Thread directions follow axis_u/axis_v (N,3) if given,
    otherwise the surface tangent frame (T, B)."""
    au = T if axis_u is None else axis_u
    av = B if axis_v is None else axis_v
    u = np.einsum("ij,ij->i", P, au) / pitch
    v = np.einsum("ij,ij->i", P, av) / pitch
    over = np.sign(np.sin(np.pi * u) * np.sin(np.pi * v))
    hu = np.abs(np.sin(np.pi * v))
    hv = np.abs(np.sin(np.pi * u))
    return (np.where(over > 0, hu, hv) - 0.5) * pitch * 0.35


def cyl_axes(P, centre_axis=(0, 0, 1)):
    """Garment thread axes: 'weft' around the body (horizontal), 'warp' vertical."""
    up = np.broadcast_to(np.asarray(centre_axis, np.float64), P.shape)
    radial = P.copy()
    radial[:, 2] = 0
    radial /= np.maximum(np.linalg.norm(radial, axis=1, keepdims=True), 1e-6)
    around = np.cross(up, radial)
    return around, up
