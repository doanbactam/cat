"""Paint every nature texture: leaf/flower atlases (albedo+alpha, normal, ORM, translucency) and
tiling bark sets (albedo, normal, ORM).  Pure python (numpy + Pillow) — no Blender needed.

    python3 blender/nature/gen_textures.py [atlas_or_bark_name ...]

Output: assets/textures/nature/<name>_{albedo.png|albedo.jpg, normal.png, orm.jpg, trans.jpg}
Layouts come from blender/lib/nature_atlas.py (shared with the Blender plant generators).
"""
from __future__ import annotations

import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import nature_atlas as NA  # noqa: E402
import nature_paint as P   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", NA.TEX_DIR)
os.makedirs(OUT, exist_ok=True)
f32 = np.float32
TAU = math.tau


# ---------------------------------------------------------------------------
# card context
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, cv: P.Canvas, atlas: str, cell: str):
        c = NA.cell(atlas, cell)
        self.cv = cv
        self.x, self.y, self.w, self.h = c["rect"]
        self.ppm = self.w / c["size"][0]           # px per metre
        piv = c["pivot"]
        if piv == "bottom":
            self.pivot = (self.x + self.w * 0.5, self.y + self.h - 4)
        elif piv == "top":
            self.pivot = (self.x + self.w * 0.5, self.y + 4)
        else:
            self.pivot = (self.x + self.w * 0.5, self.y + self.h * 0.5)
        cv.set_clip(c["rect"], 2)

    def m(self, metres: float) -> float:
        return metres * self.ppm

    def inside(self, p, pad=0.0) -> bool:
        return (self.x + pad <= p[0] <= self.x + self.w - pad) and (self.y + pad <= p[1] <= self.y + self.h - pad)


def path(start, ang, length, n, rng, wobble=0.12, curl=0.0):
    pts = [np.array(start, f32)]
    a = ang
    for i in range(n):
        a += rng.normal(0, wobble) + curl
        step = length / n
        pts.append(pts[-1] + np.array([math.sin(a), -math.cos(a)], f32) * step)
    return pts, a


def along(pts, t):
    """Point and tangent angle at fraction t of a polyline."""
    seg = [float(np.linalg.norm(pts[i + 1] - pts[i])) for i in range(len(pts) - 1)]
    tot = sum(seg)
    d = t * tot
    for i, s in enumerate(seg):
        if d <= s or i == len(seg) - 1:
            f = 0 if s == 0 else min(1.0, d / s)
            p = pts[i] + (pts[i + 1] - pts[i]) * f
            dv = pts[i + 1] - pts[i]
            return p, math.atan2(dv[0], -dv[1])
        d -= s
    return pts[-1], 0.0


def sprig(ctx: Ctx, rng, *, stem_len, stem_w, stem_col, shape, leaf_len, wr, col, col_tip=None, n=10,
          spread=(0.5, 1.1), start=0.18, twig_ang=0.0, side=2, side_len=0.55, petiole=0.012, rough=0.45,
          trans=0.55, veins=0.55, vein_spacing=0.12, midrib=0.35, edge_col=None, young=0.12,
          young_col=(0.45, 0.5, 0.12), terminal=3, bend=0.12, spots=0.05, serrate=0.0, opposite=False,
          base=None, ang=None, wobble=0.1, underside=0.15, leaf_cb=None, droop=0.0, vein_slope=0.9):
    cv = ctx.cv
    base = base if base is not None else ctx.pivot
    ang = ang if ang is not None else twig_ang + rng.normal(0, 0.12)
    pts, end_ang = path(base, ang, ctx.m(stem_len), 10, rng, wobble)
    cv.curve(pts, stem_w, stem_w * 0.45, stem_col)
    twigs = [(pts, 1.0)]
    for k in range(side):
        t = rng.uniform(0.3, 0.75)
        p, a = along(pts, t)
        s = 1 if (k % 2 == 0) else -1
        tp, _ = path(p, a + s * rng.uniform(0.45, 0.9), ctx.m(stem_len * side_len * rng.uniform(0.7, 1.0)), 6,
                     rng, wobble)
        cv.curve(tp, stem_w * 0.6, stem_w * 0.3, stem_col)
        twigs.append((tp, 0.6))
    leaves = []
    for tp, wscale in twigs:
        cnt = max(2, int(n * wscale))
        for i in range(cnt):
            t = start + (1 - start) * (i / max(1, cnt - 1)) ** 0.9
            p, a = along(tp, min(t, 0.98))
            s = 1 if i % 2 == 0 else -1
            for sgn in ((1, -1) if opposite else (s,)):
                la = a + sgn * rng.uniform(*spread) + droop * sgn
                leaves.append((t, p, la))
        tip, ta = along(tp, 1.0)
        for j in range(terminal):
            leaves.append((1.01 + j * 0.01, tip, ta + rng.normal(0, 0.35)))
    leaves.sort(key=lambda x: x[0])
    for t, p, la in leaves:
        L = ctx.m(rng.uniform(*leaf_len)) * (0.7 + 0.3 * min(1.0, t + 0.2))
        if t > 1.0:
            L *= rng.uniform(0.55, 0.85)
        W = L * wr * rng.uniform(0.55, 1.0)
        pd = np.array([math.sin(la), -math.cos(la)])
        b = p + pd * ctx.m(petiole)
        cv.curve([p, b], max(1.0, stem_w * 0.35), max(1.0, stem_w * 0.25), stem_col, shadow=0.1)
        is_young = rng.random() < young * (0.5 + t)
        c = P.jitter(rng, young_col if is_young else col, 0.07)
        ct = P.jitter(rng, col_tip if col_tip is not None else c, 0.05) if not is_young else c
        cv.leaf(b, la, L, W, shape=shape, color=c, color_tip=ct, bend=rng.normal(0, bend), rough=rough,
                trans=trans * (1.2 if is_young else 1.0), veins=veins, vein_spacing=vein_spacing, midrib=midrib,
                vein_slope=vein_slope,
                edge_col=edge_col, spots=spots if rng.random() < 0.3 else 0.0, serrate=serrate,
                underside=rng.random() < underside)
        if leaf_cb:
            leaf_cb(b, la, L)
    return pts


# ---------------------------------------------------------------------------
# flowers
# ---------------------------------------------------------------------------
def flame_flower(cv: P.Canvas, c, r, rng, ang=0.0):
    """Delonix regia flower: 4 scarlet spoon petals + 1 larger white/yellow streaked standard."""
    std = rng.integers(0, 5)
    for k in range(5):
        a = ang + k * TAU / 5 + rng.normal(0, 0.15)
        if k == std:
            col, tip = (0.95, 0.85, 0.62), (0.9, 0.3, 0.12)
            L = r * 1.15
        else:
            col, tip = (0.72, 0.07, 0.03), (0.86, 0.16, 0.05)
            L = r * rng.uniform(0.9, 1.05)
        cv.leaf(c, a, L, L * 0.8, shape="petal", color=col, color_tip=tip, bend=rng.normal(0, 0.08),
                midrib=0.15, veins=0.7 if k == std else 0.35, vein_spacing=0.18, vein_slope=0.3, trans=0.85,
                rough=0.5, edge_col=(0.6, 0.05, 0.03) if k != std else None, thickness=0.6, shadow=0.25)
    for k in range(8):
        a = ang + rng.uniform(0, TAU)
        e = np.array(c) + np.array([math.sin(a), -math.cos(a)]) * r * rng.uniform(0.6, 1.0)
        cv.curve([c, e], 1.2, 0.8, (0.6, 0.05, 0.04), shadow=0.1)
        cv.disc(e, 1.3, (0.35, 0.12, 0.05), rough=0.6)


def frangipani_flower(cv, c, r, rng, ang=0.0, pink=0.0):
    for k in range(5):
        a = ang + k * TAU / 5 + rng.normal(0, 0.06)
        base_c = (0.95, 0.82, 0.32)
        tip = (0.93 - 0.05 * pink, 0.91 - 0.35 * pink, 0.86 - 0.2 * pink)
        # petals overlap in a pinwheel: offset the base sideways, bend the tip
        off = np.array([math.cos(a), math.sin(a)]) * r * 0.12
        cv.leaf(np.array(c) + off, a, r, r * 0.62, shape="obovate", color=base_c, color_tip=tip, bend=0.18,
                midrib=0.05, veins=0.15, vein_slope=0.2, trans=0.8, rough=0.42, thickness=0.9, shadow=0.3)
    cv.disc(c, r * 0.12, (0.85, 0.62, 0.15), rough=0.5)


def bract_cluster(cv, c, r, rng, col=(0.78, 0.06, 0.42)):
    """Bougainvillea: three papery magenta bracts around tiny cream tubular flowers."""
    ang = rng.uniform(0, TAU)
    for k in range(3):
        a = ang + k * TAU / 3 + rng.normal(0, 0.2)
        cc = P.jitter(rng, col, 0.06)
        cv.leaf(c, a, r, r * 0.95, shape="bract", color=cc, color_tip=tuple(np.array(cc) * 1.08),
                midrib=0.2, veins=0.8, vein_spacing=0.1, vein_slope=0.6, trans=0.95, rough=0.55,
                thickness=0.4, bend=rng.normal(0, 0.1), shadow=0.2)
    for k in range(3):
        a = ang + k * TAU / 3 + TAU / 6
        e = np.array(c) + np.array([math.sin(a), -math.cos(a)]) * r * 0.45
        cv.curve([c, e], 1.6, 1.2, (0.86, 0.82, 0.7), shadow=0.1)
        cv.disc(e, 1.5, (0.95, 0.94, 0.85))


def tiny4(cv, c, r, rng, col=(0.85, 0.12, 0.06)):
    a0 = rng.uniform(0, TAU)
    for k in range(4):
        a = a0 + k * TAU / 4
        cv.leaf(c, a, r, r * 0.7, shape="elliptic", color=P.jitter(rng, col, 0.05), midrib=0.1, veins=0,
                trans=0.8, rough=0.5, thickness=0.5, shadow=0.15)
    cv.disc(c, max(0.8, r * 0.15), (0.95, 0.75, 0.2))


# ---------------------------------------------------------------------------
# atlases
# ---------------------------------------------------------------------------
def atlas_banyan():
    name = "leaf_banyan"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 11)
    rng = np.random.default_rng(11)
    leaf = dict(shape="ovate", wr=0.55, col=(0.11, 0.22, 0.06), col_tip=(0.15, 0.28, 0.07), rough=0.32,
                trans=0.45, veins=0.55, vein_spacing=0.09, vein_slope=0.75, midrib=0.55,
                young_col=(0.36, 0.46, 0.13), stem_col=(0.38, 0.33, 0.24), edge_col=(0.2, 0.26, 0.08))
    for cell, figs, n, twig in (("sprig_a", 0, 9, 0.0), ("sprig_figs", 1, 8, -0.15), ("sprig_c", 0, 7, 0.2)):
        ctx = Ctx(cv, name, cell)
        L = 0.42 if cell != "sprig_c" else 0.36
        for s in range(2):
            pts = sprig(ctx, rng, stem_len=L * (0.95 if s == 0 else 0.7), stem_w=ctx.m(0.008), n=n,
                        leaf_len=(0.1, 0.15), side=2, ang=twig + (s * 0.7 - 0.35) * (1 if s else 0.3),
                        **leaf)
            if figs:
                for k in range(14):
                    p, a = along(pts, rng.uniform(0.2, 0.95))
                    off = np.array([math.cos(a), math.sin(a)]) * ctx.m(0.012) * rng.choice([-1, 1])
                    fc = [(0.72, 0.3, 0.1), (0.55, 0.12, 0.08), (0.6, 0.55, 0.18)][rng.integers(0, 3)]
                    cv.disc(p + off, ctx.m(0.0075), P.jitter(rng, fc, 0.05), rough=0.35, trans=0.1)
    # aerial-root fringe: thin tapering strands hanging from the top
    ctx = Ctx(cv, name, "roots")
    for k in range(70):
        x = ctx.x + rng.uniform(0.06, 0.94) * ctx.w
        L = ctx.h * rng.uniform(0.35, 0.95)
        pts, _ = path((x, ctx.y + 3), math.pi + rng.normal(0, 0.03), L, 24, rng, 0.035)
        w = ctx.m(rng.uniform(0.003, 0.009))
        c = P.jitter(rng, (0.4, 0.34, 0.27), 0.1)
        cv.curve(pts, w, w * 0.5, c, trans=0.05, rough=0.75, shadow=0.15)
        tip = pts[-1]
        cv.curve([tip, tip + np.array([0, ctx.m(0.02)])], w * 0.5, w * 0.3, (0.72, 0.62, 0.48), shadow=0.0)
        if rng.random() < 0.3:  # side rootlets
            p, a = along(pts, rng.uniform(0.3, 0.8))
            sp, _ = path(p, a + rng.choice([-0.35, 0.35]), L * 0.25, 6, rng, 0.05)
            cv.curve(sp, w * 0.5, w * 0.3, c, shadow=0.1)
    return cv.save(os.path.join(OUT, name), 2.2)


def bipinnate(ctx, rng, base, ang, length, pinnae=9, col=(0.2, 0.36, 0.08), stem_col=(0.32, 0.36, 0.14),
              leaflet=0.011):
    cv = ctx.cv
    pts, _ = path(base, ang, ctx.m(length), 12, rng, 0.05, curl=rng.normal(0, 0.015))
    cv.curve(pts, ctx.m(0.004), ctx.m(0.0015), stem_col, shadow=0.1)
    for i in range(pinnae):
        t = 0.15 + 0.85 * i / max(1, pinnae - 1)
        p, a = along(pts, t)
        for s in (-1, 1):
            pl = ctx.m(length * 0.42 * (1 - 0.55 * t) * rng.uniform(0.85, 1.05))
            pa = a + s * rng.uniform(0.85, 1.15)
            pp, _ = path(p, pa, pl, 6, rng, 0.04, curl=-s * 0.03)
            cv.curve(pp, ctx.m(0.0018), ctx.m(0.001), stem_col, shadow=0.05)
            nl = max(5, int(pl / ctx.m(leaflet * 0.9)))
            for j in range(nl):
                q, qa = along(pp, 0.06 + 0.94 * j / nl)
                for s2 in (-1, 1):
                    L = ctx.m(leaflet) * rng.uniform(0.8, 1.1) * (1 - 0.35 * j / nl)
                    cv.leaf(q, qa + s2 * rng.uniform(1.0, 1.35), L, L * 0.42, shape="elliptic",
                            color=P.jitter(rng, col, 0.06), midrib=0.15, veins=0, trans=0.6, rough=0.55,
                            shadow=0.18, thickness=0.5)
    return pts


def atlas_flame():
    name = "leaf_flame"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 21)
    rng = np.random.default_rng(21)
    for cell in ("frond_a", "frond_b"):
        ctx = Ctx(cv, name, cell)
        for k in range(3):
            bipinnate(ctx, rng, ctx.pivot, rng.normal(0, 0.35) + (k - 1) * 0.45, rng.uniform(0.38, 0.5),
                      pinnae=rng.integers(8, 12), col=(0.17, 0.33, 0.06) if cell == "frond_a" else (0.22, 0.38, 0.08))
    ctx = Ctx(cv, name, "flowers")
    for k in range(2):
        bipinnate(ctx, rng, ctx.pivot, (k - 0.5) * 1.1, 0.3, pinnae=7)
    stalk, _ = path(ctx.pivot, 0.05, ctx.m(0.28), 8, rng, 0.05)
    cv.curve(stalk, ctx.m(0.005), ctx.m(0.003), (0.35, 0.3, 0.12))
    top = stalk[-1]
    for k in range(13):
        a = rng.uniform(-1.4, 1.4)
        r = ctx.m(rng.uniform(0.07, 0.2))
        e = top + np.array([math.sin(a), -math.cos(a)]) * r
        if ctx.inside(e, ctx.m(0.07)):
            cv.curve([top, e], ctx.m(0.002), ctx.m(0.0015), (0.42, 0.3, 0.1))
            if rng.random() < 0.2:
                cv.disc(e, ctx.m(0.008), (0.45, 0.28, 0.08))
            else:
                flame_flower(cv, e, ctx.m(rng.uniform(0.032, 0.042)), rng, rng.uniform(0, TAU))
    ctx = Ctx(cv, name, "frond_flowers")
    for k in range(2):
        bipinnate(ctx, rng, ctx.pivot, (k - 0.5) * 0.9, 0.45, pinnae=10)
    hub = np.array([ctx.x + ctx.w * 0.5, ctx.y + ctx.h * 0.55])
    cv.curve([np.array(ctx.pivot, f32), hub], ctx.m(0.006), ctx.m(0.004), (0.4, 0.3, 0.12))
    for k in range(9):
        p = (ctx.x + ctx.w * rng.uniform(0.22, 0.78), ctx.y + ctx.h * rng.uniform(0.1, 0.42))
        cv.curve([hub, np.array(p, f32)], ctx.m(0.003), ctx.m(0.002), (0.42, 0.3, 0.1))
        flame_flower(cv, p, ctx.m(rng.uniform(0.032, 0.04)), rng, rng.uniform(0, TAU))
    return cv.save(os.path.join(OUT, name), 2.0)


def atlas_sao():
    name = "leaf_sao"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 31)
    rng = np.random.default_rng(31)
    for i, cell in enumerate(("sprig_a", "sprig_b", "sprig_c", "sprig_d")):
        ctx = Ctx(cv, name, cell)
        for s in range(3):
            sprig(ctx, rng, stem_len=rng.uniform(0.25, 0.36), stem_w=ctx.m(0.004), stem_col=(0.3, 0.24, 0.17),
                  shape="elliptic", leaf_len=(0.055, 0.085), wr=0.45, col=(0.12, 0.24, 0.06),
                  col_tip=(0.16, 0.3, 0.07), n=12, side=2, rough=0.38, trans=0.5, vein_spacing=0.1,
                  young=0.2 if i % 2 else 0.08, young_col=(0.4, 0.3, 0.14), ang=(s - 1) * 0.45 + rng.normal(0, 0.15),
                  terminal=2)
    return cv.save(os.path.join(OUT, name), 2.0)


def atlas_frangipani():
    name = "leaf_frangipani"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 41)
    rng = np.random.default_rng(41)
    lk = dict(shape="oblanceolate", color=(0.16, 0.3, 0.07), rough=0.4, trans=0.45, midrib=0.75, veins=0.85,
              vein_spacing=0.045, vein_slope=0.25, thickness=1.2)
    for cell in ("rosette", "rosette_flowers"):
        ctx = Ctx(cv, name, cell)
        n = 15
        for k in range(n):
            a = k * TAU / n + rng.normal(0, 0.12)
            L = ctx.m(rng.uniform(0.27, 0.38))
            c = P.jitter(rng, (0.16, 0.3, 0.07), 0.08)
            cv.leaf(ctx.pivot, a, L, L * 0.3, color_tip=tuple(np.array(c) * 1.15), bend=rng.normal(0, 0.06),
                    edge_col=(0.3, 0.32, 0.08), **{**lk, "color": c})
        cv.disc(ctx.pivot, ctx.m(0.022), (0.38, 0.36, 0.26), rough=0.7)
        if cell == "rosette_flowers":
            for k in range(9):
                a = rng.uniform(0, TAU)
                r = ctx.m(rng.uniform(0.0, 0.08))
                p = np.array(ctx.pivot) + np.array([math.sin(a), -math.cos(a)]) * r
                frangipani_flower(cv, p, ctx.m(rng.uniform(0.04, 0.05)), rng, rng.uniform(0, TAU))
    ctx = Ctx(cv, name, "flower_cluster")
    stalk, _ = path(ctx.pivot, 0.0, ctx.m(0.15), 6, rng, 0.06)
    cv.curve(stalk, ctx.m(0.006), ctx.m(0.004), (0.4, 0.38, 0.22))
    for k in range(9):
        a = rng.uniform(-1.3, 1.3)
        e = stalk[-1] + np.array([math.sin(a), -math.cos(a)]) * ctx.m(rng.uniform(0.03, 0.09))
        cv.curve([stalk[-1], e], ctx.m(0.003), ctx.m(0.002), (0.45, 0.42, 0.25))
        frangipani_flower(cv, e, ctx.m(rng.uniform(0.04, 0.05)), rng, rng.uniform(0, TAU), pink=0.15 * rng.random())
    ctx = Ctx(cv, name, "leaf_side")
    for k in range(5):
        a = (k - 2) * 0.35 + rng.normal(0, 0.08)
        L = ctx.m(rng.uniform(0.32, 0.42))
        c = P.jitter(rng, (0.16, 0.3, 0.07), 0.08)
        cv.leaf(ctx.pivot, a, L, L * 0.28, color_tip=tuple(np.array(c) * 1.12), bend=rng.normal(0, 0.1),
                **{**lk, "color": c})
    return cv.save(os.path.join(OUT, name), 2.2)


def atlas_palm():
    name = "leaf_palm"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 51)
    rng = np.random.default_rng(51)
    for cell in ("coconut", "coconut_dry", "areca", "areca_b"):
        ctx = Ctx(cv, name, cell)
        dry = cell == "coconut_dry"
        areca = cell.startswith("areca")
        x0 = ctx.x + 5
        # rachis strip on the left edge (geometry covers the real rachis; this is its texture)
        cv.curve([(x0, ctx.y + ctx.h - 2), (x0, ctx.y + 2)], 7, 3,
                 (0.55, 0.45, 0.2) if dry else (0.42, 0.45, 0.16), shadow=0)
        n = 46 if not areca else 34
        for i in range(n):
            t = (i + rng.uniform(0, 0.6)) / n
            if dry and rng.random() < 0.18:
                continue
            y = ctx.y + ctx.h - 6 - t * (ctx.h - 14)
            env = math.sin(math.pi * min(1.0, 0.12 + t * 0.95)) ** 0.7
            Lm = (0.75 if not areca else 0.55) * env + 0.08
            L = ctx.m(Lm) * rng.uniform(0.9, 1.05)
            ang = rng.uniform(0.55, 0.75) if not areca else rng.uniform(0.6, 0.8)  # from vertical
            Wl = ctx.m(0.035 if not areca else 0.05) * rng.uniform(0.85, 1.1)
            if dry:
                c = P.jitter(rng, (0.55, 0.42, 0.18) if rng.random() < 0.6 else (0.45, 0.4, 0.15), 0.08)
                ct = (0.42, 0.3, 0.14)
            else:
                c = P.jitter(rng, (0.2, 0.34, 0.07) if not areca else (0.24, 0.4, 0.08), 0.07)
                ct = tuple(np.array(c) * (1.15 if not areca else 1.1) + np.array([0.04, 0.03, 0.0]))
            cv.leaf((x0 + 3, y), ang, L, Wl, shape="linear", color=c, color_tip=ct, bend=0.13 + rng.normal(0, 0.03),
                    midrib=0.6, veins=0, rough=0.45 if not dry else 0.75, trans=0.55 if not dry else 0.25,
                    edge_col=(0.45, 0.42, 0.18) if not dry else None, shadow=0.3,
                    spots=0.25 if dry else 0.03)
    return cv.save(os.path.join(OUT, name), 1.8)


def atlas_willow():
    name = "leaf_willow"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 61)
    rng = np.random.default_rng(61)
    for cell in ("strand_a", "strand_b", "strand_c", "strand_d"):
        ctx = Ctx(cv, name, cell)
        for s in range(3):
            x = ctx.x + ctx.w * (0.3 + 0.2 * s) + rng.normal(0, 5)
            pts, _ = path((x, ctx.y + 3), math.pi + rng.normal(0, 0.05), ctx.h * rng.uniform(0.75, 0.95), 20, rng, 0.04)
            cv.curve(pts, ctx.m(0.003), ctx.m(0.0015), (0.42, 0.4, 0.2), shadow=0.1)
            nl = 34
            for i in range(nl):
                t = 0.04 + 0.96 * i / nl
                p, a = along(pts, t)
                sgn = 1 if i % 2 else -1
                L = ctx.m(rng.uniform(0.07, 0.11)) * (1 - 0.35 * t)
                c = P.jitter(rng, (0.32, 0.45, 0.12), 0.08)
                cv.leaf(p, a + sgn * rng.uniform(0.25, 0.55), L, L * 0.16, shape="lanceolate", color=c,
                        color_tip=tuple(np.array(c) * 1.1), bend=sgn * 0.05, midrib=0.4, veins=0, rough=0.5,
                        trans=0.7, shadow=0.2, underside=rng.random() < 0.3)
    return cv.save(os.path.join(OUT, name), 1.6)


def atlas_bamboo():
    name = "leaf_bamboo"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 71)
    rng = np.random.default_rng(71)
    for cell in ("sprig_a", "sprig_b", "sprig_c", "sprig_d"):
        ctx = Ctx(cv, name, cell)
        for s in range(3):
            pts, _ = path(ctx.pivot, (s - 1) * 0.55 + rng.normal(0, 0.1), ctx.m(rng.uniform(0.2, 0.3)), 8, rng, 0.08)
            cv.curve(pts, ctx.m(0.003), ctx.m(0.0018), (0.45, 0.48, 0.2))
            for j in range(rng.integers(5, 8)):
                p, a = along(pts, 0.4 + 0.6 * rng.random())
                la = a + rng.normal(0, 0.9)
                L = ctx.m(rng.uniform(0.13, 0.2))
                c = P.jitter(rng, (0.24, 0.4, 0.09), 0.08)
                cv.leaf(p, la, L, L * 0.13, shape="lanceolate", color=c, color_tip=tuple(np.array(c) * 1.1),
                        bend=rng.normal(0, 0.12), midrib=0.45, veins=0, rough=0.5, trans=0.65,
                        edge_col=(0.45, 0.42, 0.18) if rng.random() < 0.3 else None, shadow=0.3)
    return cv.save(os.path.join(OUT, name), 1.8)


def atlas_undergrowth():
    name = "undergrowth"
    W, H = NA.ATLASES[name]["size"]
    cv = P.Canvas(W, H, 81)
    rng = np.random.default_rng(81)
    # ---- ixora shrub sprig (dark glossy opposite leaves + red cluster)
    ctx = Ctx(cv, name, "ixora")
    for s in range(3):
        pts = sprig(ctx, rng, stem_len=rng.uniform(0.2, 0.28), stem_w=ctx.m(0.004), stem_col=(0.35, 0.3, 0.2),
                    shape="elliptic", leaf_len=(0.07, 0.1), wr=0.36, col=(0.08, 0.2, 0.05), col_tip=(0.11, 0.25, 0.06),
                    n=6, side=0, rough=0.3, opposite=True, ang=(s - 1) * 0.5, terminal=2, vein_spacing=0.1)
        top = pts[-1]
        for k in range(22):
            a = rng.uniform(0, TAU)
            r = ctx.m(0.03) * math.sqrt(rng.random())
            tiny4(cv, top + np.array([math.cos(a), math.sin(a) * 0.7]) * r - np.array([0, ctx.m(0.015)]),
                  ctx.m(0.008), rng)
    ctx = Ctx(cv, name, "ixora_flowers")
    for k in range(80):
        a = rng.uniform(0, TAU)
        r = ctx.m(0.1) * math.sqrt(rng.random())
        c = np.array(ctx.pivot) + np.array([math.cos(a) * r, -ctx.m(0.12) + math.sin(a) * r * 0.8])
        tiny4(cv, c, ctx.m(0.01), rng, col=(0.86, 0.15 + 0.1 * rng.random(), 0.05))
    # ---- hedge (Murraya-like dense small leaves)
    ctx = Ctx(cv, name, "hedge")
    for s in range(5):
        sprig(ctx, rng, stem_len=rng.uniform(0.2, 0.3), stem_w=ctx.m(0.003), stem_col=(0.33, 0.28, 0.2),
              shape="elliptic", leaf_len=(0.03, 0.045), wr=0.5, col=(0.1, 0.24, 0.06), col_tip=(0.14, 0.3, 0.07),
              n=11, side=2, rough=0.35, ang=(s - 2) * 0.35, terminal=2, young=0.15)
    # ---- bougainvillea
    for cell, nfl in (("bougainvillea_a", 7), ("bougainvillea_b", 16)):
        ctx = Ctx(cv, name, cell)
        for s in range(2):
            pts = sprig(ctx, rng, stem_len=0.36, stem_w=ctx.m(0.005), stem_col=(0.36, 0.3, 0.22), shape="ovate",
                        leaf_len=(0.04, 0.07), wr=0.6, col=(0.13, 0.27, 0.07), n=8, side=2,
                        ang=(s - 0.5) * 0.9 + rng.normal(0, 0.1), rough=0.5, vein_spacing=0.14)
            for k in range(nfl // 2):
                p, a = along(pts, rng.uniform(0.35, 1.0))
                off = np.array([math.cos(a), math.sin(a)]) * ctx.m(0.03) * rng.normal()
                bract_cluster(cv, p + off, ctx.m(rng.uniform(0.022, 0.03)), rng)
    # ---- ferns (Nephrolepis)
    for cell in ("fern_a", "fern_b"):
        ctx = Ctx(cv, name, cell)
        for s in range(2):
            pts, _ = path(ctx.pivot, (s - 0.5) * 0.25, ctx.m(0.62 if s == 0 else 0.5), 14, rng, 0.03,
                          curl=(0.02 if s else -0.02))
            cv.curve(pts, ctx.m(0.0035), ctx.m(0.0015), (0.3, 0.32, 0.12))
            nl = 30
            for i in range(nl):
                t = 0.08 + 0.92 * i / nl
                p, a = along(pts, t)
                env = math.sin(math.pi * min(1.0, t * 1.05)) ** 0.6
                for sg in (-1, 1):
                    L = ctx.m(0.07) * env + 2
                    c = P.jitter(rng, (0.2, 0.38, 0.08) if cell == "fern_a" else (0.25, 0.42, 0.1), 0.06)
                    cv.leaf(p, a + sg * 1.25, L, L * 0.3, shape="lanceolate", color=c, bend=-sg * 0.08,
                            midrib=0.35, veins=0.4, vein_spacing=0.2, serrate=0.25, teeth=9, rough=0.55,
                            trans=0.6, shadow=0.2)
    # ---- grass tufts
    for cell, dry in (("grass_a", 0.08), ("grass_b", 0.35)):
        ctx = Ctx(cv, name, cell)
        for k in range(70):
            a = rng.normal(0, 0.45)
            L = ctx.m(rng.uniform(0.12, 0.3))
            b = (ctx.pivot[0] + rng.normal(0, ctx.m(0.02)), ctx.pivot[1])
            isdry = rng.random() < dry
            c = P.jitter(rng, (0.46, 0.42, 0.2) if isdry else (0.2, 0.36, 0.08), 0.1)
            cv.leaf(b, a, L, ctx.m(rng.uniform(0.004, 0.007)), shape="blade", color=c,
                    color_tip=tuple(np.array(c) * 1.15 + 0.03), bend=np.sign(a) * rng.uniform(0.05, 0.25),
                    midrib=0.3, veins=0, rough=0.6, trans=0.6, shadow=0.15)
    # ---- weeds (toothed rosette + clover)
    ctx = Ctx(cv, name, "weed")
    for k in range(9):
        a = rng.normal(0, 0.8)
        L = ctx.m(rng.uniform(0.08, 0.13))
        cv.leaf(ctx.pivot, a, L, L * 0.3, shape="oblanceolate", color=P.jitter(rng, (0.2, 0.36, 0.08), 0.08),
                serrate=0.45, teeth=6, midrib=0.5, veins=0.3, rough=0.55, trans=0.55, bend=rng.normal(0, 0.1))
    for k in range(6):
        stem_top = np.array(ctx.pivot) + np.array([rng.normal(0, ctx.m(0.05)), -ctx.m(rng.uniform(0.04, 0.09))])
        cv.curve([ctx.pivot, stem_top], 1.5, 1.2, (0.3, 0.36, 0.12))
        for j in range(3):
            cv.leaf(stem_top, j * TAU / 3 + rng.normal(0, 0.1), ctx.m(0.016), ctx.m(0.016), shape="obovate",
                    color=P.jitter(rng, (0.2, 0.38, 0.1), 0.05), midrib=0.4, veins=0, rough=0.5, trans=0.6)
    cv.disc((ctx.pivot[0] + ctx.m(0.03), ctx.pivot[1] - ctx.m(0.11)), ctx.m(0.01), (0.95, 0.8, 0.15))
    # ---- moss (top-down)
    ctx = Ctx(cv, name, "moss")
    cx, cy = ctx.pivot
    n1 = P.fft_noise(ctx.h, ctx.w, rng, 1.8)
    n2 = P.fft_noise(ctx.h, ctx.w, rng, 0.4)
    yy, xx = np.mgrid[0:ctx.h, 0:ctx.w].astype(f32)
    rr = np.sqrt((xx - ctx.w / 2) ** 2 + (yy - ctx.h / 2) ** 2) / (ctx.w * 0.47)
    m = np.clip((1 - rr) * 2.2 + (n1 - 0.5) * 2.0 + (n2 - 0.5) * 0.6, 0, 1)
    a = P.sstep(0.35, 0.55, m)
    col = np.array([0.22, 0.3, 0.07], f32) * (0.6 + 0.6 * n2[..., None]) + np.array([0.12, 0.1, 0.0], f32) * n1[..., None]
    sy, sx = slice(ctx.y, ctx.y + ctx.h), slice(ctx.x, ctx.x + ctx.w)
    cv.col[sy, sx] = col
    cv.a[sy, sx] = a
    cv.hgt[sy, sx] = m * 0.5 + n2 * 0.8
    cv.rough[sy, sx] = 0.85
    cv.tr[sy, sx] = 0.15
    # ---- fallen leaves: 4x4 grid of single leaves (each mapped onto one litter quad)
    ctx = Ctx(cv, name, "fallen_leaves")
    sw, sh = ctx.w / 4, ctx.h / 4
    kinds = [("ovate", 0.55, (0.45, 0.3, 0.12)), ("ovate", 0.55, (0.62, 0.48, 0.15)), ("elliptic", 0.45, (0.35, 0.22, 0.1)),
             ("oblanceolate", 0.3, (0.55, 0.4, 0.15)), ("ovate", 0.55, (0.3, 0.36, 0.1)), ("lanceolate", 0.2, (0.6, 0.5, 0.25)),
             ("elliptic", 0.45, (0.7, 0.45, 0.12)), ("ovate", 0.5, (0.4, 0.18, 0.08))]
    for i in range(16):
        cx0 = ctx.x + (i % 4) * sw
        cy0 = ctx.y + (i // 4) * sh
        shp, wr, c = kinds[i % len(kinds)]
        cv.set_clip((int(cx0), int(cy0), int(sw), int(sh)), 2)
        a = rng.uniform(-0.5, 0.5)
        L = sh * 0.82
        b = (cx0 + sw / 2 - math.sin(a) * L / 2, cy0 + sh / 2 + math.cos(a) * L / 2)
        cv.leaf(b, a, L, L * wr, shape=shp, color=P.jitter(rng, c, 0.08), color_tip=P.jitter(rng, c, 0.12),
                bend=rng.normal(0, 0.08), midrib=0.5, veins=0.6, vein_spacing=0.1, rough=0.75, trans=0.3,
                spots=0.5, edge_col=(0.3, 0.2, 0.08), thickness=1.4)
        cv.curve([b, (b[0] + math.sin(a) * -8, b[1] + math.cos(a) * 8)], 2.5, 1.5, (0.35, 0.25, 0.12))
    # ---- lotus pad (top-down, notch at the bottom)
    ctx = Ctx(cv, name, "lotus_pad")
    yy, xx = np.mgrid[0:ctx.h, 0:ctx.w].astype(f32)
    dx, dy = xx - ctx.w / 2 + 0.5, yy - ctx.h / 2 + 0.5
    r = np.sqrt(dx * dx + dy * dy)
    R = ctx.w * 0.47
    ang = np.arctan2(dx, dy)                 # 0 = straight down (notch)
    edge = R * (1 + 0.012 * np.sin(ang * 23) + 0.01 * np.sin(ang * 7))
    notch = np.abs(ang) < 0.09 * (r / R)
    a = np.clip(edge - r + 0.5, 0, 1) * (~notch)
    n1 = P.fft_noise(ctx.h, ctx.w, rng, 1.6)
    veins = (1 - np.abs(np.mod(ang / TAU * 22, 1.0) - 0.5) * 2) ** 14 * P.sstep(0.05, 0.3, r / R)
    base = np.array([0.18, 0.33, 0.12], f32)
    col = base * (0.85 + 0.35 * n1[..., None]) * (1.0 + 0.25 * veins[..., None])
    col = col * (1 - 0.25 * P.sstep(0.0, 0.12, 1 - r / R)[..., None] * 0) + 0
    rim = P.sstep(0.9, 1.0, r / R)
    col = col * (1 - rim[..., None] * 0.5) + np.array([0.45, 0.4, 0.12], f32) * rim[..., None] * 0.5
    blot = P.sstep(0.78, 0.86, P.fft_noise(ctx.h, ctx.w, rng, 1.2))
    col = col * (1 - blot[..., None] * 0.6) + np.array([0.42, 0.32, 0.12], f32) * blot[..., None] * 0.6
    centre = np.exp(-(r / (R * 0.08)) ** 2)
    col = col * (1 - centre[..., None]) + np.array([0.45, 0.48, 0.25], f32) * centre[..., None]
    sy, sx = slice(ctx.y, ctx.y + ctx.h), slice(ctx.x, ctx.x + ctx.w)
    cv.col[sy, sx] = col
    cv.a[sy, sx] = a
    cv.hgt[sy, sx] = 0.25 * veins + 0.3 * rim + 0.08 * n1
    cv.rough[sy, sx] = 0.3 + 0.2 * blot      # waxy, water-repellent
    cv.tr[sy, sx] = 0.35
    # ---- lotus petals: 2x2 sub-cells: two petals, seed pod (top-down), stamen ring
    ctx = Ctx(cv, name, "lotus_petal")
    sw, sh = ctx.w / 2, ctx.h / 2
    for i in range(2):
        cv.set_clip((int(ctx.x + i * sw), int(ctx.y), int(sw), int(sh)), 2)
        L = sh * 0.92
        cv.leaf((ctx.x + i * sw + sw / 2, ctx.y + sh - 3), 0.0, L, L * 0.62, shape="petal",
                color=(0.95, 0.88, 0.85), color_tip=(0.88, 0.35, 0.55) if i == 0 else (0.92, 0.55, 0.68),
                midrib=0.3, veins=0.6, vein_spacing=0.07, vein_slope=0.15, rough=0.45, trans=0.9, thickness=0.6)
    cv.set_clip((int(ctx.x), int(ctx.y + sh), int(sw), int(sh)), 2)
    pc = (ctx.x + sw / 2, ctx.y + sh * 1.5)
    cv.disc(pc, sw * 0.42, (0.62, 0.66, 0.3), rough=0.55)
    for k in range(17):
        a = k * TAU / 12 if k < 12 else (k - 12) * TAU / 5
        rr = sw * (0.28 if k < 12 else 0.12)
        cv.disc((pc[0] + math.cos(a) * rr, pc[1] + math.sin(a) * rr), sw * 0.045, (0.32, 0.36, 0.12), hgt=-0.4)
    cv.set_clip((int(ctx.x + sw), int(ctx.y + sh), int(sw), int(sh)), 2)
    for k in range(60):
        a = rng.uniform(0, TAU)
        b = (ctx.x + sw * 1.5, ctx.y + sh * 1.5)
        cv.leaf(b, a, sw * 0.45, 3, shape="linear", color=(0.95, 0.78, 0.25), midrib=0, veins=0, trans=0.6)
    # ---- water hyacinth leaf (glossy round blade on a swollen petiole)
    ctx = Ctx(cv, name, "hyacinth_leaf")
    for k in range(3):
        a = (k - 1) * 0.45 + rng.normal(0, 0.05)
        L = ctx.m(0.05)
        tip = np.array(ctx.pivot) + np.array([math.sin(a), -math.cos(a)]) * L
        cv.leaf(ctx.pivot, a, L, ctx.m(0.022), shape="obovate", color=(0.25, 0.4, 0.12), color_tip=(0.2, 0.38, 0.1),
                midrib=0.2, veins=0, rough=0.35, trans=0.5, thickness=1.6)
        cv.leaf(tip - np.array([math.sin(a), -math.cos(a)]) * ctx.m(0.006), a + rng.normal(0, 0.1), ctx.m(0.065),
                ctx.m(0.07), shape="round", color=(0.13, 0.3, 0.07), color_tip=(0.17, 0.35, 0.08), midrib=0.3,
                veins=0.5, vein_spacing=0.08, vein_slope=0.15, rough=0.22, trans=0.4)
    ctx = Ctx(cv, name, "hyacinth_flower")
    stalk, _ = path(ctx.pivot, 0.0, ctx.m(0.18), 6, rng, 0.03)
    cv.curve(stalk, ctx.m(0.005), ctx.m(0.003), (0.3, 0.4, 0.15))
    for k in range(9):
        p, a = along(stalk, 0.35 + 0.65 * k / 8)
        p = p + np.array([rng.normal(0, ctx.m(0.012)), 0])
        for j in range(6):
            pa = j * TAU / 6 + rng.normal(0, 0.1)
            cv.leaf(p, pa, ctx.m(0.018), ctx.m(0.012), shape="obovate", color=(0.6, 0.5, 0.82),
                    color_tip=(0.68, 0.58, 0.88), midrib=0.2, veins=0.3, trans=0.85, rough=0.45, shadow=0.15)
        cv.disc(p - np.array([0, ctx.m(0.008)]), ctx.m(0.004), (0.25, 0.25, 0.7))
        cv.disc(p - np.array([0, ctx.m(0.008)]), ctx.m(0.0018), (0.95, 0.85, 0.2))
    return cv.save(os.path.join(OUT, name), 2.0)


# ---------------------------------------------------------------------------
# bark sets (tiling)
# ---------------------------------------------------------------------------
def _bark_save(name, alb, hgt, rough, cav_strength=1.0, nstrength=6.0):
    cav = np.clip((hgt - P.blur(hgt, 6)) * 4.0 * cav_strength + 0.5, 0, 1)
    ao = np.clip(0.45 + 0.75 * cav, 0, 1)
    alb = alb * (0.75 + 0.25 * ao[..., None])
    P.save_rgb(os.path.join(OUT, name + "_albedo.jpg"), alb)
    P.save_rgb(os.path.join(OUT, name + "_normal.png"), P.height_to_normal(hgt, nstrength))
    P.save_rgb(os.path.join(OUT, name + "_orm.jpg"), np.stack([ao, np.clip(rough, 0.05, 1), np.zeros_like(ao)], -1))


def bark_banyan(S=1024):
    rng = np.random.default_rng(101)
    # fused aerial-root trunk: sinuous vertical strands, fine horizontal wrinkles, lenticels, lichen
    strands = P.fft_noise(S, S, rng, 2.0, ax=1.0, ay=6.0, lo=5)
    strands = np.clip(np.abs(strands - 0.5) * 2.6, 0, 1)
    wrinkles = P.fft_noise(S, S, rng, 1.2, ax=9.0, ay=1.0)
    fine = P.fft_noise(S, S, rng, 0.8)
    mott = P.fft_noise(S, S, rng, 2.0)
    lich = P.sstep(0.62, 0.72, P.fft_noise(S, S, rng, 1.6) * 0.8 + fine * 0.2)
    hgt = (1 - strands) ** 1.5 * 1.0 + wrinkles * 0.25 + fine * 0.08
    base = np.array([0.42, 0.39, 0.35], f32)
    alb = base * (0.75 + 0.45 * mott[..., None]) * (0.85 + 0.25 * hgt[..., None])
    alb = alb * (1 - lich[..., None] * 0.6) + np.array([0.58, 0.6, 0.5], f32) * lich[..., None] * 0.6
    green = P.sstep(0.68, 0.8, P.fft_noise(S, S, rng, 1.8))
    alb = alb * (1 - green[..., None] * 0.5) + np.array([0.24, 0.3, 0.12], f32) * green[..., None] * 0.5
    lent = P.sstep(0.86, 0.92, P.fft_noise(S, S, rng, 0.2, ax=0.35, ay=1.0))
    alb *= (1 - 0.3 * lent[..., None])
    hgt = hgt - 0.1 * lent
    rough = 0.7 + 0.15 * fine - 0.1 * lich
    _bark_save("bark_banyan", alb, hgt, rough, nstrength=10.0)


def bark_furrowed(S=1024):
    rng = np.random.default_rng(102)
    # Hopea / willow style: deep vertical furrows broken into flaky plates
    f = P.fft_noise(S, S, rng, 2.0, ax=1.0, ay=6.0, lo=7)
    ridges = np.clip(1 - np.abs(f - 0.5) * 2.4, 0, 1)
    plates = P.fft_noise(S, S, rng, 2.0, ax=1.0, ay=2.2)
    breaks = P.sstep(0.45, 0.5, np.abs(np.sin(plates * 18.0)))
    fine = P.fft_noise(S, S, rng, 0.7)
    hgt = ridges ** 2.2 * (0.6 + 0.4 * breaks) + fine * 0.12
    mott = P.fft_noise(S, S, rng, 1.8)
    base = np.array([0.3, 0.25, 0.2], f32)
    alb = base * (0.55 + 0.8 * hgt[..., None]) * (0.85 + 0.3 * mott[..., None])
    deep = P.sstep(0.0, 0.25, hgt)
    alb = alb * (0.45 + 0.55 * deep[..., None])
    lich = P.sstep(0.7, 0.78, P.fft_noise(S, S, rng, 1.5)) * deep
    alb = alb * (1 - lich[..., None] * 0.55) + np.array([0.5, 0.52, 0.42], f32) * lich[..., None] * 0.55
    rough = 0.82 + 0.1 * fine
    _bark_save("bark_furrowed", alb, hgt, rough, 1.4, nstrength=11.0)


def bark_smooth(S=1024):
    rng = np.random.default_rng(103)
    # Delonix / Plumeria: smooth grey-brown skin, mottled flaking patches, horizontal lenticels
    mott = P.fft_noise(S, S, rng, 2.2)
    patch = P.sstep(0.55, 0.6, P.fft_noise(S, S, rng, 2.0))
    fine = P.fft_noise(S, S, rng, 0.8)
    rings = P.fft_noise(S, S, rng, 1.0, ax=10.0, ay=1.0)
    lent = P.sstep(0.84, 0.9, P.fft_noise(S, S, rng, 0.3, ax=0.25, ay=1.0))
    hgt = patch * 0.25 + rings * 0.15 + fine * 0.05 - lent * 0.1
    base = np.array([0.46, 0.43, 0.38], f32)
    alb = base * (0.8 + 0.35 * mott[..., None])
    alb = alb * (1 - patch[..., None] * 0.25) + np.array([0.52, 0.48, 0.36], f32) * patch[..., None] * 0.25
    alb = alb * (1 - lent[..., None] * 0.35)
    lich = P.sstep(0.72, 0.8, P.fft_noise(S, S, rng, 1.5))
    alb = alb * (1 - lich[..., None] * 0.5) + np.array([0.6, 0.62, 0.55], f32) * lich[..., None] * 0.5
    rough = 0.6 + 0.15 * fine + 0.1 * patch
    _bark_save("bark_smooth", alb, hgt, rough, nstrength=5.0)


def bark_palm(S=1024):
    rng = np.random.default_rng(104)
    yy = np.mgrid[0:S, 0:S][0].astype(f32) / S
    warp = P.fft_noise(S, S, rng, 2.0, ax=1.0, ay=0.3) * 0.08
    period = 1.0 / 11.0          # ring every ~7 cm on a 0.8 m tile
    ph = np.mod((yy + warp) / period, 1.0)
    ring = P.sstep(0.0, 0.25, ph) * (1 - P.sstep(0.75, 1.0, ph)) * 0.6 + 0.4
    fine = P.fft_noise(S, S, rng, 0.9, ax=1.0, ay=4.0)
    cracks = P.sstep(0.82, 0.9, P.fft_noise(S, S, rng, 1.4, ax=1.0, ay=5.0))
    hgt = ring * 0.6 + fine * 0.2 - cracks * 0.25
    mott = P.fft_noise(S, S, rng, 2.0)
    base = np.array([0.45, 0.41, 0.36], f32)
    alb = base * (0.7 + 0.35 * mott[..., None]) * (0.75 + 0.35 * ring[..., None])
    dark = 1 - ring
    alb = alb * (1 - 0.3 * dark[..., None]) * (1 - 0.35 * cracks[..., None])
    rough = 0.78 + 0.1 * fine
    _bark_save("bark_palm", alb, hgt, rough, nstrength=6.0)


def bamboo_culm(S=1024):
    rng = np.random.default_rng(105)
    yy = np.mgrid[0:S, 0:S][0].astype(f32) / S
    fib = P.fft_noise(S, S, rng, 1.0, ax=1.0, ay=30.0)
    mott = P.fft_noise(S, S, rng, 2.2, ax=1.0, ay=3.0)
    v = 1 - yy                                     # 0 at the bottom (node) .. 1 top of internode
    node = np.exp(-((v - 0.0) / 0.02) ** 2) + np.exp(-((v - 1.0) / 0.02) ** 2)
    sheath_band = np.exp(-((v - 0.06) / 0.03) ** 2)   # pale waxy band just above each node
    base = np.array([0.32, 0.42, 0.12], f32)
    alb = base * (0.8 + 0.3 * mott[..., None]) * (0.92 + 0.1 * fib[..., None])
    yel = P.sstep(0.6, 0.85, P.fft_noise(S, S, rng, 2.0, ax=1, ay=4))
    alb = alb * (1 - yel[..., None] * 0.45) + np.array([0.55, 0.52, 0.2], f32) * yel[..., None] * 0.45
    alb = alb * (1 - sheath_band[..., None] * 0.35) + np.array([0.62, 0.64, 0.5], f32) * sheath_band[..., None] * 0.35
    alb = alb * (1 - node[..., None] * 0.4) + np.array([0.38, 0.36, 0.18], f32) * node[..., None] * 0.4
    spots = P.sstep(0.8, 0.86, P.fft_noise(S, S, rng, 1.0))
    alb = alb * (1 - spots[..., None] * 0.5) + np.array([0.25, 0.22, 0.12], f32) * spots[..., None] * 0.5
    hgt = fib * 0.15 + node * 0.8
    rough = 0.35 + 0.15 * mott + 0.2 * spots
    _bark_save("bamboo_culm", alb, hgt, rough, nstrength=4.0)


JOBS = {
    "leaf_banyan": atlas_banyan, "leaf_flame": atlas_flame, "leaf_sao": atlas_sao,
    "leaf_frangipani": atlas_frangipani, "leaf_palm": atlas_palm, "leaf_willow": atlas_willow,
    "leaf_bamboo": atlas_bamboo, "undergrowth": atlas_undergrowth,
    "bark_banyan": bark_banyan, "bark_furrowed": bark_furrowed, "bark_smooth": bark_smooth,
    "bark_palm": bark_palm, "bamboo_culm": bamboo_culm,
}

if __name__ == "__main__":
    names = sys.argv[1:] or list(JOBS)
    for n in names:
        t = time.time()
        JOBS[n]()
        print(f"{n}: {time.time() - t:.1f}s")
