"""Signed-distance modelling kit for NPC creatures (numpy, vectorised).

A creature is described as a `Model`: an ordered list of `Prim`s (each a distance
function + bounding sphere + the bone that drives it + a texture label), smoothly
unioned, minus `Carve`s, plus optional garment `Layer`s (clothing, hair, feathers ...)
that are unioned on top with a texel-accurate label so textures know what they are.

Everything works on (N, 3) float64 arrays of Blender object-space points (Z up,
front = -Y). Distances are metres.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

BIG = 1.0e3


# ---------------------------------------------------------------------------
# vector helpers
# ---------------------------------------------------------------------------
def V(*a) -> np.ndarray:
    if len(a) == 1:
        a = a[0]
    return np.asarray(a, dtype=np.float64)


def length(q: np.ndarray) -> np.ndarray:
    return np.sqrt(np.einsum("ij,ij->i", q, q))


def normalize(v) -> np.ndarray:
    v = V(v)
    return v / max(np.linalg.norm(v), 1e-12)


def frame(axis_y, hint_x=(1, 0, 0)) -> np.ndarray:
    """Orthonormal frame (columns x, y, z) with y along axis_y and x close to hint_x."""
    y = normalize(axis_y)
    hx = V(hint_x)
    x = hx - np.dot(hx, y) * y
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(y, V(0, 0, 1))
    x = normalize(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], 1)


def rot(axis, deg) -> np.ndarray:
    a = normalize(axis)
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


# ---------------------------------------------------------------------------
# primitive distance functions (return callables)
# ---------------------------------------------------------------------------
def f_sphere(c, r):
    c = V(c)
    return lambda p: length(p - c) - r


def f_ellipsoid(c, r, R=None):
    """iq's ellipsoid bound; R: 3x3 with the ellipsoid's local axes as columns."""
    c = V(c)
    r = V(r)

    def f(p):
        q = p - c
        if R is not None:
            q = q @ R
        k0 = length(q / r)
        k1 = length(q / (r * r))
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-12)
    return f


def f_round_cone(a, b, r1, r2):
    """Capsule with linearly varying radius (exact iq round cone)."""
    a = V(a)
    b = V(b)
    ba = b - a
    l2 = float(np.dot(ba, ba))
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2

    def f(p):
        pa = p - a
        y = pa @ ba
        z = y - l2
        xv = pa * l2 - y[:, None] * ba[None]
        x2 = np.einsum("ij,ij->i", xv, xv)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        out = (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
        m1 = np.sign(z) * a2 * z2 > k
        m2 = np.sign(y) * a2 * y2 < k
        out = np.where(m1, np.sqrt(x2 + z2) * il2 - r2, out)
        out = np.where(m2, np.sqrt(x2 + y2) * il2 - r1, out)
        return out
    return f


def f_capsule(a, b, r):
    return f_round_cone(a, b, r, r)


def f_flat_cone(a, b, r1, r2, flat: float, side=(1, 0, 0)):
    """Round cone squashed across `side` by factor `flat` (<1 = flatter)."""
    a = V(a)
    b = V(b)
    Rf = frame(b - a, side)        # x = side, y = axis, z = normal
    base = f_round_cone(V(0, 0, 0), V(0, np.linalg.norm(b - a), 0), r1, r2)
    s = V(1.0 / flat, 1.0, 1.0)

    def f(p):
        q = (p - a) @ Rf
        return base(q * s) * flat
    return f


def f_box(c, half, R=None, round_r: float = 0.0):
    c = V(c)
    h = V(half) - round_r

    def f(p):
        q = p - c
        if R is not None:
            q = q @ R
        d = np.abs(q) - h
        out = length(np.maximum(d, 0.0)) + np.minimum(d.max(1), 0.0)
        return out - round_r
    return f


def f_cyl(a, b, r, round_r=0.0):
    """Capped cylinder between a and b (optionally rounded edges)."""
    a = V(a)
    b = V(b)
    ba = b - a
    L = np.linalg.norm(ba)
    ax = ba / L
    mid = (a + b) * 0.5

    def f(p):
        q = p - mid
        y = q @ ax
        rad = length(q - y[:, None] * ax[None])
        dx = rad - (r - round_r)
        dy = np.abs(y) - (L * 0.5 - round_r)
        out = np.minimum(np.maximum(dx, dy), 0.0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2)
        return out - round_r
    return f


def f_torus(c, R_major, r_minor, axis=(0, 0, 1)):
    c = V(c)
    Rf = frame(axis)

    def f(p):
        q = (p - c) @ Rf          # y = axis
        xz = np.sqrt(q[:, 0] ** 2 + q[:, 2] ** 2) - R_major
        return np.sqrt(xz * xz + q[:, 1] ** 2) - r_minor
    return f


def f_plane(point, normal):
    """Half-space: negative on the side the normal points AWAY from (i.e. 'below')."""
    point = V(point)
    n = normalize(normal)
    return lambda p: (p - point) @ n


def f_transform(fn, c, R):
    """Evaluate fn in a local frame: point p -> c + R @ local."""
    c = V(c)
    return lambda p: fn((p - c) @ R)


# ---------------------------------------------------------------------------
# combinators
# ---------------------------------------------------------------------------
def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def f_union(fns, k=0.0):
    def f(p):
        d = fns[0](p)
        for g in fns[1:]:
            d = smin(d, g(p), k)
        return d
    return f


def f_intersect(fa, fb, k=0.0):
    return lambda p: smax(fa(p), fb(p), k)


def f_subtract(fa, fb, k=0.0):
    return lambda p: smax(fa(p), -fb(p), k)


def f_shell(fn, thickness):
    return lambda p: np.abs(fn(p)) - thickness


def f_offset(fn, o):
    return lambda p: fn(p) - o


# ---------------------------------------------------------------------------
# model description
# ---------------------------------------------------------------------------
@dataclass
class Prim:
    """One smooth-unioned body part.

    fn: distance function; c/r: bounding sphere (conservative: the surface lies within it);
    bone: name of the deforming bone (or dict bone->weight for blended parts);
    label: texture region ("skin", "fur_belly", "shirt" ...); k: smooth-union radius.
    soft: skinning falloff (m) - larger = smoother weights.
    """
    fn: Callable
    c: np.ndarray
    r: float
    bone: str | dict
    label: str = "skin"
    k: float = 0.01
    soft: float = 0.012
    name: str = ""


@dataclass
class Carve:
    fn: Callable
    c: np.ndarray
    r: float
    k: float = 0.004


@dataclass
class Layer:
    """A garment / hair / plumage layer unioned over the body (label wins where it is the surface)."""
    label: str
    prims: list = field(default_factory=list)
    carves: list = field(default_factory=list)
    k_body: float = 0.0          # smooth blend with the body (0 = hard min = garment edge step)
    priority: float = 0.0015     # label tie-break: layer wins when d_layer <= d_body + priority


def bound_prim(fn, pts, bone, label="skin", k=0.01, soft=0.012, name="", pad=0.0) -> Prim:
    """Helper: Prim whose bounding sphere encloses the given defining points (+ pad)."""
    pts = np.atleast_2d(V(pts))
    c = pts.mean(0)
    r = float(np.max(np.linalg.norm(pts - c, axis=1))) + pad
    return Prim(fn, c, r, bone, label, k, soft, name)


class Model:
    def __init__(self, band: float = 0.05):
        self.prims: list[Prim] = []
        self.carves: list[Carve] = []
        self.layers: list[Layer] = []
        self.band = band

    # -- building --------------------------------------------------------
    def add(self, fn, pts, bone, label="skin", k=0.01, soft=0.012, name="", pad=0.0) -> Prim:
        p = bound_prim(fn, pts, bone, label, k, soft, name, pad)
        self.prims.append(p)
        return p

    def carve(self, fn, pts, k=0.004, pad=0.0) -> None:
        pts = np.atleast_2d(V(pts))
        c = pts.mean(0)
        r = float(np.max(np.linalg.norm(pts - c, axis=1))) + pad
        self.carves.append(Carve(fn, c, r, k))

    def layer(self, label, k_body=0.0, priority=0.0015) -> Layer:
        L = Layer(label, k_body=k_body, priority=priority)
        self.layers.append(L)
        return L

    def bounds(self):
        allp = self.prims + [p for L in self.layers for p in L.prims]
        lo = np.min([p.c - p.r for p in allp], 0)
        hi = np.max([p.c + p.r for p in allp], 0)
        return lo, hi

    # -- evaluation ------------------------------------------------------
    def _eval_prims(self, prims, P, cutoff):
        d = np.full(len(P), BIG)
        for pr in prims:
            dc = length(P - pr.c) - pr.r
            m = dc < cutoff + pr.k
            if not m.any():
                continue
            v = np.full(len(P), BIG)
            v[m] = pr.fn(P[m])
            # outside the bound we only know a lower bound; keep it for ordering
            v[~m] = np.maximum(dc[~m], cutoff + pr.k)
            d = smin(d, v, pr.k)
        return d

    def _apply_carves(self, carves, P, d):
        for cv in carves:
            dc = length(P - cv.c) - cv.r
            m = dc < cv.k
            if not m.any():
                continue
            sub = np.full(len(P), BIG)
            sub[m] = cv.fn(P[m])
            d = smax(d, -sub, cv.k)
        return d

    def body(self, P, cutoff=None):
        cutoff = self.band if cutoff is None else cutoff
        d = self._eval_prims(self.prims, P, cutoff)
        return self._apply_carves(self.carves, P, d)

    def layer_d(self, L: Layer, P, cutoff=None):
        cutoff = self.band if cutoff is None else cutoff
        d = self._eval_prims(L.prims, P, cutoff)
        return self._apply_carves(L.carves, P, d)

    def sdf(self, P, cutoff=None):
        d = self.body(P, cutoff)
        for L in self.layers:
            dl = self.layer_d(L, P, cutoff)
            d = smin(d, dl, L.k_body) if L.k_body > 0 else np.minimum(d, dl)
        return d

    def __call__(self, P):
        return self.sdf(P)

    def labels(self, P) -> np.ndarray:
        """Texture label (index into self.label_names()) of the surface nearest to each point."""
        names = self.label_names()
        lid = {n: i for i, n in enumerate(names)}
        # body: label of the closest body prim
        best = np.full(len(P), BIG)
        lab = np.zeros(len(P), np.int32)
        for pr in self.prims:
            dc = length(P - pr.c) - pr.r
            m = dc < 0.03
            if not m.any():
                continue
            v = pr.fn(P[m])
            sel = v < best[m]
            idx = np.nonzero(m)[0][sel]
            best[idx] = v[sel]
            lab[idx] = lid[pr.label]
        dbody = self.body(P)
        for L in self.layers:
            dl = self.layer_d(L, P)
            win = dl <= dbody + L.priority
            # a layer's own prims may carry sub-labels (e.g. a shirt collar)
            sub_best = np.full(len(P), BIG)
            sub_lab = np.full(len(P), lid[L.label], np.int32)
            for pr in L.prims:
                if pr.label == L.label:
                    continue
                dc = length(P - pr.c) - pr.r
                m = dc < 0.03
                if not m.any():
                    continue
                v = pr.fn(P[m])
                idx = np.nonzero(m)[0]
                close = v < 0.004
                sel = close & (v < sub_best[idx])
                sub_best[idx[sel]] = v[sel]
                sub_lab[idx[sel]] = lid[pr.label]
            lab = np.where(win, sub_lab, lab)
            dbody = np.minimum(dbody, dl)
        return lab

    def label_names(self) -> list[str]:
        names = []
        for p in self.prims:
            if p.label not in names:
                names.append(p.label)
        for L in self.layers:
            if L.label not in names:
                names.append(L.label)
            for p in L.prims:
                if p.label not in names:
                    names.append(p.label)
        return names

    def all_prims(self):
        return self.prims + [p for L in self.layers for p in L.prims]

    # -- derived fields --------------------------------------------------
    def gradient(self, P, eps=4e-4):
        g = np.zeros_like(P)
        for i in range(3):
            e = np.zeros(3)
            e[i] = eps
            g[:, i] = self.sdf(P + e) - self.sdf(P - e)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-12)

    def ao(self, P, N, steps=(0.006, 0.014, 0.028, 0.05, 0.08), strength=1.0):
        """Classic SDF ambient occlusion along the normal."""
        occ = np.zeros(len(P))
        w = 1.0
        tot = 0.0
        for s in steps:
            d = self.sdf(P + N * s, cutoff=max(self.band, s * 1.5))
            occ += w * np.clip(s - d, 0, None) / s
            tot += w
            w *= 0.7
        return np.clip(1.0 - strength * occ / tot, 0.0, 1.0)

    def project(self, P, iters=3, max_step=0.003):
        for _ in range(iters):
            d = self.sdf(P)
            g = self.gradient(P)
            P = P - g * np.clip(d, -max_step, max_step)[:, None]
        return P
