"""Utility props: concrete electric pole (distribution box + cable mess), cable coils, cable drum, AC unit,
LPG cylinder."""
import json
import math
import os
import random
import sys

from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import props_geo as G  # noqa: E402
import props_nodes as PN  # noqa: E402
from props_bake import prop  # noqa: E402

LABELS = os.path.join(HERE, "labels")


def L(name):
    return os.path.join(LABELS, name + ".png")


def _perp(d):
    d = Vector(d).normalized()
    a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(a).normalized()
    v = d.cross(u).normalized()
    return u, v


def bundle(path, n, spread, mats, rng, r_min=0.004, r_max=0.009, segs=6, wander=0.6, name="cable", w=0.12):
    """n cables following `path` (list of points), randomly offset in the normal plane with slow drift."""
    P = [Vector(p) for p in path]
    out = []
    for i in range(n):
        ox, oy = rng.uniform(-1, 1), rng.uniform(-1, 1)
        r = rng.uniform(r_min, r_max)
        seed = rng.uniform(0, 100)
        pts = []
        for k, p in enumerate(P):
            d = P[min(k + 1, len(P) - 1)] - P[max(k - 1, 0)]
            u, v = _perp(d)
            t = k / max(1, len(P) - 1)
            dx = ox + wander * noise.noise(Vector((t * 3.0, seed, 0.0)))
            dy = oy + wander * noise.noise(Vector((seed, t * 3.0, 1.0)))
            pts.append(p + u * dx * spread + v * dy * spread)
        t = G.tube(name, pts, r, segs, mat=rng.choice(mats))
        if w != 1.0:
            G.uv_weight(t, w)
        out.append(t)
    return out


def helix(c, r, z0, z1, turns, n=60, phase=0.0):
    pts = []
    for k in range(n + 1):
        t = k / n
        a = phase + t * turns * 2 * math.pi
        pts.append((c[0] + math.cos(a) * r, c[1] + math.sin(a) * r, z0 + (z1 - z0) * t))
    return pts


def cable_mats():
    return [PN.rubber("cab_black", "#141414", rough=0.55, dirt=0.3, dust=0.5, wear=0.2),
            PN.rubber("cab_grey", "#3b3b3a", rough=0.6, dirt=0.3, dust=0.5, wear=0.2),
            PN.rubber("cab_dark", "#1d1c1b", rough=0.45, dirt=0.3, dust=0.6, wear=0.2)]


# ---------------------------------------------------------------------------
# Concrete electric pole
# ---------------------------------------------------------------------------
@prop("electric_pole_concrete", category="utility", surface="concrete", mass=900.0, max_tex=2048,
      tags=["pole", "cables"], visibility_range=220.0)
def electric_pole_concrete():
    rng = random.Random(11)
    conc = PN.concrete("pole", "#a19d93", rough=0.8, stains=0.7, moss=0.3, dirt=0.6, dust=0.3, ground=0.9,
                       label=True, label_wear=0.35, pores=0.7)
    galv = PN.metal("arm", "galvanized", dirt=0.6, rust=0.45, wear=0.5)
    insul = PN.ceramic("insul", "#7a4a2a", rough=0.12, crackle=0.0, chip=0.3, dirt=0.6, dust=0.5, unglazed_h=0.0)
    box_m = PN.painted_metal("dbox", "#9aa09a", primer="#7a3b22", chip=0.4, rust=0.6, gloss=0.45, streaks=0.8,
                             dirt=0.6, dust=0.5, label=True, label_wear=0.3)
    cm = cable_mats()
    pipe_m = PN.plastic("conduit", "#d9d4c4", rough=0.5, fade=0.4, dirt=0.8, ground=0.9)
    parts = []
    H = 8.6
    def pr(z):  # spun-concrete taper
        return 0.175 - (0.175 - 0.095) * (z / H) ** 0.9
    cuts = [0.0, 0.8, 1.6, 2.4, 3.4, 4.6, 5.8, 7.0, H]
    segs_pole = []
    for z0, z1 in zip(cuts[:-1], cuts[1:]):
        prof = [(pr(z0 + (z1 - z0) * k / 4), z0 + (z1 - z0) * k / 4) for k in range(5)]
        if z1 >= H:
            prof += [(0.06, H + 0.005), (0.0, H + 0.005)]
        sp = G.lathe("pole", prof, 28, mat=conc, smooth_angle=50, max_seg=0.1,
                     rfunc=lambda r, z, a: r * (1 + 0.006 * math.sin(a * 2 + z)))
        segs_pole.append(sp)
        if z0 >= 2.3:
            G.uv_weight(sp, 0.3)
    pole = segs_pole[0]
    # stickers / stencil on the street side, below the box
    for sp in segs_pole[1:3]:
        G.label_cyl(sp, (0.0, 0.0, 1.0, 0.6), 0.9, 2.3, a0=-math.pi / 2 - 1.5, a1=-math.pi / 2 + 1.5)
    parts += segs_pole[1:]
    collar = G.lathe("collar", [(0.0, 0.0), (0.3, 0.0), (0.29, 0.06), (0.2, 0.09), (0.0, 0.09)], 20, mat=conc,
                     rfunc=lambda r, z, a: r * (1 + 0.08 * math.sin(a * 3) + 0.05 * math.sin(a * 7)))
    G.wobble(collar, 0.01, 6, seed=2)
    parts += [pole, collar]
    # cross-arms + insulators
    attach = []
    for (z, L_arm, n_ins, kind) in ((8.25, 1.9, 4, "pin"), (7.6, 1.5, 4, "spool")):
        yA = -0.13
        arm = G.rbox("arm", (L_arm, 0.07, 0.07), bevel=0.003, mat=galv)
        G.place(arm, (0, yA, z - 0.035))
        brace_l = G.tube("brace", [(-0.5, yA, z - 0.03), (0, -0.1, z - 0.55)], 0.01, 6, mat=galv)
        brace_r = G.tube("brace", [(0.5, yA, z - 0.03), (0, -0.1, z - 0.55)], 0.01, 6, mat=galv)
        ub = G.tube("ubolt", helix((0, 0), 0.115, z - 0.02, z - 0.02, 1.0, 24), 0.008, 6, mat=galv)
        parts += [arm, brace_l, brace_r, ub]
        xs = [(-L_arm / 2 + 0.12) + (L_arm - 0.24) * i / (n_ins - 1) for i in range(n_ins)]
        for x in xs:
            if abs(x) < 0.15:
                continue
            if kind == "pin":
                ins = G.lathe("ins", [(0.0, 0.0), (0.02, 0.0), (0.045, 0.03), (0.04, 0.05), (0.06, 0.07),
                                      (0.055, 0.1), (0.035, 0.12), (0.03, 0.14), (0.0, 0.145)], 18, mat=insul)
                G.place(ins, (x, yA, z))
                attach.append((x, yA, z + 0.13))
            else:
                ins = G.lathe("ins", [(0.0, 0.0), (0.035, 0.0), (0.04, 0.02), (0.028, 0.04), (0.04, 0.06),
                                      (0.035, 0.08), (0.0, 0.08)], 16, mat=insul)
                G.place(ins, (x, yA, z))
                attach.append((x, yA, z + 0.04))
            parts.append(ins)
    # line stubs from the insulators (cut where the world's spans continue)
    for (x, y, z) in attach:
        side = -1 if x < 0 else 1
        pts = [(x, y, z), (x + side * 0.6, y - 0.02, z - 0.03), (x + side * 1.2, y - 0.03, z - 0.05)]
        parts.append(G.uv_weight(G.tube("line", pts, 0.006, 6, mat=cm[0]), 0.1))
    # the bundle: wraps around the pole, stubs out both sides, slack coils hanging
    zb = 6.15
    for side in (-1, 1):
        path = [(side * 0.14, -0.03, zb), (side * 0.5, -0.08, zb - 0.02), (side * 0.95, -0.12, zb - 0.07),
                (side * 1.45, -0.15, zb - 0.1)]
        parts += bundle(path, 9, 0.035, cm, rng, wander=0.5)
    for k in range(3):
        parts += bundle(helix((0, 0), 0.165 + 0.012 * k, zb - 0.25 + 0.06 * k, zb + 0.15, 1.6, 48, phase=k * 2.1), 3,
                        0.01, cm, rng, wander=0.3)
    for (cx, cr, cz) in ((-0.6, 0.22, zb - 0.32), (0.75, 0.17, zb - 0.26)):
        loop = [(cx + math.sin(t * 2 * math.pi) * cr * 0.9, -0.13 + 0.03 * math.sin(t * 6),
                 cz + math.cos(t * 2 * math.pi) * cr) for t in [i / 28 for i in range(29)]]
        parts += bundle(loop, 5, 0.02, cm, rng, wander=0.4)
        tie = G.tube("tie", helix((cx, -0.13), 0.03, cz + cr - 0.03, cz + cr + 0.03, 3, 24), 0.0025, 5,
                     mat=galv)
        G.place(tie, (0, 0, 0))
        parts.append(tie)
    # distribution box (street side, -Y)
    by = -0.29
    box = G.rbox("dbox", (0.52, 0.24, 0.74), bevel=0.01, mat=box_m)
    G.place(box, (0, by, 2.45))
    door = G.rbox("door", (0.48, 0.012, 0.68), bevel=0.004, mat=box_m)
    G.place(door, (0, by - 0.125, 2.48))
    G.label_planar(door, (0.55, 0.55, 1.0, 1.0), (-0.12, by - 0.14, 2.82), (1, 0, 0), (0, 0, 1), (0.24, 0.24),
                   normal=(0, -1, 0))
    rainhood = G.rbox("hood", (0.58, 0.3, 0.025), bevel=0.006, mat=box_m)
    G.place(rainhood, (0, by - 0.02, 3.19), (-6, 0, 0))
    handle = G.rbox("handle", (0.03, 0.03, 0.12), bevel=0.008, mat=galv)
    G.place(handle, (0.2, by - 0.14, 2.75))
    parts += [box, door, rainhood, handle]
    for z in (2.6, 3.05):
        band = G.tube("band", helix((0, 0), 0.158, z, z, 1.0, 28), 0.006, 5, mat=galv)
        strap = G.rbox("strap", (0.4, 0.03, 0.04), bevel=0.004, mat=galv)
        G.place(strap, (0, by + 0.13, z - 0.02))
        parts += [band, strap]
    # cables dropping into the box top and out of the bottom into a conduit
    for k in range(4):
        x = -0.12 + 0.08 * k
        drop = [(x * 0.6, -0.15, zb - 0.1), (x * 0.8, -0.17, 4.5), (x, -0.2, 3.6), (x, by, 3.25), (x, by, 3.18)]
        parts += bundle(drop, 1, 0.01, cm, rng, wander=0.2)
    conduit = G.tube("conduit", [(0.0, by, 2.45), (0.0, by, 1.2), (0.0, -0.22, 0.35), (0.0, -0.2, 0.0)], 0.025, 10,
                     mat=pipe_m)
    parts.append(conduit)
    for p in parts:
        if p.name.startswith(("cable", "line", "pole")):
            continue
        if p.name.startswith(("dbox", "door", "hood", "handle", "band", "strap")):
            G.uv_weight(p, 0.6)
            continue
        G.uv_weight(p, 0.28, zmin=3.4)
    cols = [G.col_cyl("concrete", 0.17, H, segs=12, r2=0.095), G.col_box("metal", (0.54, 0.26, 0.78),
                                                                         loc=(0, by, 2.43)),
            G.col_box("metal", (1.9, 0.08, 0.08), loc=(0, -0.13, 8.18)),
            G.col_box("metal", (1.5, 0.08, 0.08), loc=(0, -0.13, 7.53))]
    marks = [G.marker("NAP_01", (0, by, 3.22))]
    for i, (x, y, z) in enumerate(attach):
        marks.append(G.marker(f"ATTACH_LINE_{i:02d}", (x + (-1.2 if x < 0 else 1.2), y - 0.03, z - 0.05)))
    marks.append(G.marker("ATTACH_BUNDLE_L", (-1.45, -0.15, zb - 0.1)))
    marks.append(G.marker("ATTACH_BUNDLE_R", (1.45, -0.15, zb - 0.1)))
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("pole_stickers")}


# ---------------------------------------------------------------------------
# Hanging cable coils (origin = hang point; geometry below)
# ---------------------------------------------------------------------------
def _coil(seed, radius, n, junction):
    rng = random.Random(seed)
    cm = cable_mats() + [PN.rubber("cab_white", "#d8d6cf", rough=0.5, dirt=0.7, dust=0.4)]
    galv = PN.metal("hook", "galvanized", rust=0.5)
    parts = []
    cz = -radius - 0.08
    turns = 3
    for i in range(n):
        ph = rng.uniform(0, 2 * math.pi)
        rr = radius * rng.uniform(0.85, 1.12)
        pts = []
        steps = 60 * turns
        for k in range(steps + 1):
            t = k / steps
            a = ph + t * turns * 2 * math.pi
            wob = 0.03 * noise.noise(Vector((t * 6, i, 0)))
            rx = (rr + wob) * (1.0 if math.sin(a) > -0.9 else 1.0)
            x = math.sin(a) * rx
            z = cz + math.cos(a) * (rr + wob) * (0.9 + 0.1 * math.cos(a))
            # gravity: lower part of each loop sags and spreads
            sag = max(0.0, -math.cos(a)) ** 2 * 0.06 * rng.uniform(0.5, 1.5)
            y = 0.04 * math.sin(a * 0.5 + i) + rng.uniform(-0.002, 0.002)
            pts.append((x, y, z - sag))
        parts.append(G.tube("coil", pts, rng.uniform(0.004, 0.008), 6, mat=rng.choice(cm)))
    # tails into the bundle going up/sideways
    for i in range(min(n, 5)):
        parts.append(G.tube("tail", [(rng.uniform(-0.03, 0.03), rng.uniform(-0.02, 0.02), -0.06),
                                     (rng.uniform(-0.05, 0.05), 0.0, 0.0),
                                     (rng.uniform(0.3, 0.45) * (1 if i % 2 else -1), 0.0, rng.uniform(0.0, 0.05))],
                             0.006, 6, mat=rng.choice(cm)))
    for zt in (cz + radius, cz - radius * 0.9):
        tie = G.tube("tie", helix((0, 0.0), 0.035, -0.025, 0.025, 4, 32), 0.0022, 5, mat=galv)
        G.place(tie, (0, 0, 0), (0, 90, 0))
        G.place(tie, (0, 0, zt))
        parts.append(tie)
    hook = G.tube("hook", [(0, 0, 0.0), (0, 0, -0.05), (0.02, 0, -0.08), (0.0, 0, -0.1)], 0.004, 6, mat=galv)
    parts.append(hook)
    if junction:
        jm = PN.plastic("jbox", "#8e9190", rough=0.5, fade=0.5, dirt=0.8, dust=0.6)
        jb = G.rbox("jbox", (0.16, 0.07, 0.22), bevel=0.012, mat=jm)
        G.place(jb, (radius * 0.6, 0.06, cz - 0.05))
        parts.append(jb)
    return {"parts": parts, "markers": [G.marker("HANG_01", (0, 0, 0))], "meta": {"origin": "hang_point"}}


@prop("cable_coil_small", category="utility", surface="fabric", material_kind="soft", mass=4.0, grounded=False, tags=["cables", "hanging"])
def cable_coil_small():
    return _coil(3, 0.17, 6, False)


@prop("cable_coil_large", category="utility", surface="fabric", material_kind="soft", mass=9.0, grounded=False, tags=["cables", "hanging"])
def cable_coil_large():
    return _coil(9, 0.27, 11, True)


@prop("cable_drum", category="utility", surface="wood", mass=60.0, tags=["standable", "climbable_low"])
def cable_drum():
    rng = random.Random(4)
    wood = PN.wood("drum", "#8a6a48", axis="Z", rings=25, weather_grey=0.5, dirt=0.6, ground=0.8)
    cm = cable_mats()
    galv = PN.metal("bolt", "galvanized", rust=0.6)
    parts = []
    R, Wd, rc = 0.42, 0.5, 0.16
    for side in (-1, 1):
        fl = G.cyl("flange", R, 0.035, loc=(0, 0, -0.0175), segs=40, bevel=0.004, mat=wood)
        G.wobble(fl, 0.004, 4, seed=side + 3)
        G.place(fl, (0, 0, 0), (0, 90, 0))
        G.place(fl, (side * (Wd / 2 + 0.0175), 0, R))
        hole = G.cyl("hub", 0.06, 0.04, loc=(0, 0, -0.02), segs=20, mat=galv)
        G.place(hole, (0, 0, 0), (0, 90, 0))
        G.place(hole, (side * (Wd / 2 + 0.03), 0, R))
        parts += [fl, hole]
        for k in range(8):
            a = 2 * math.pi * k / 8
            b = G.cyl("bolt", 0.008, 0.01, loc=(0, 0, 0), segs=6, mat=galv)
            G.place(b, (0, 0, 0), (0, 90 * side, 0))
            G.place(b, (side * (Wd / 2 + 0.036), math.cos(a) * 0.28, R + math.sin(a) * 0.28))
            parts.append(b)
    core = G.cyl("core", rc, Wd, loc=(0, 0, -Wd / 2), segs=24, mat=wood)
    G.place(core, (0, 0, 0), (0, 90, 0))
    G.place(core, (0, 0, R))
    parts.append(core)
    # remaining cable wound: several helical layers
    for layer in range(5):
        rr = rc + 0.018 + layer * 0.022
        pts = []
        turns = 11
        for k in range(turns * 24 + 1):
            t = k / (turns * 24)
            a = t * turns * 2 * math.pi
            x = -Wd / 2 + 0.02 + (Wd - 0.04) * (t if layer % 2 == 0 else 1 - t)
            pts.append((x, math.cos(a) * rr, R + math.sin(a) * rr))
        parts.append(G.uv_weight(G.tube("wound", pts, 0.011, 6, mat=cm[0]), 0.05))
    tail = G.tube("tail", [(0.1, 0.0, R + 0.27), (0.18, -0.25, R + 0.2), (0.25, -0.45, 0.05), (0.4, -0.7, 0.012),
                           (0.9, -0.8, 0.012)], 0.011, 6, mat=cm[0])
    parts.append(tail)
    cols = [G.col_cyl("wood", R, Wd + 0.07, loc=(-(Wd + 0.07) / 2, 0, R), rot=(0, 90, 0), segs=14)]
    marks = [G.marker("NAP_01", (0, 0, 2 * R)), G.marker("SIT_01", (0, 0, 2 * R))]
    return {"parts": parts, "colliders": cols, "markers": marks}


# ---------------------------------------------------------------------------
# Outdoor AC condenser (standalone, on rubber feet) — a favourite warm nap spot
# ---------------------------------------------------------------------------
@prop("ac_unit", category="utility", kind="home", surface="metal", mass=32.0, tags=["standable", "nap"])
def ac_unit():
    shell = PN.painted_metal("acshell", "#e4e2da", primer="#a9a59a", bare="#9a9a96", chip=0.25, rust=0.35, gloss=0.45,
                             streaks=0.8, dirt=0.8, dust=0.6, ground=0.5)
    dark = PN.plastic("acfan", "#2a2b2c", rough=0.5, fade=0.1, dirt=0.8, dust=0.7)
    grille = PN.painted_metal("acgrille", "#3a3c3d", chip=0.2, rust=0.5, gloss=0.4, dirt=0.7, dust=0.6)
    fin = PN.metal("fins", "aluminium", dirt=0.9, dust=0.7, wear=0.2)
    copper = PN.metal("copper", "copper", wear=0.6, dirt=0.6)
    foam = PN.plastic("insul", "#e9e7df", rough=0.75, fade=0.6, dirt=0.8, dust=0.6, scratch=0.2)
    rub = PN.rubber("feet", "#1b1b1b", dirt=0.6)
    W, D, H, Z0 = 0.78, 0.27, 0.54, 0.06
    parts = []
    body = G.rbox("body", (W, D, H), bevel=0.012, segs=3, mat=shell)
    G.place(body, (0, 0, Z0))
    top = G.rbox("top", (W + 0.012, D + 0.012, 0.012), bevel=0.004, mat=shell)
    G.place(top, (0, 0, Z0 + H - 0.006))
    parts += [body, top]
    # fan opening: recessed dark ring + 3 blades + concentric wire grille
    fx, fz, fr = 0.1, Z0 + H / 2, 0.205
    well = G.lathe("well", [(fr + 0.012, 0.0), (fr, 0.01), (fr - 0.01, 0.06), (0.0, 0.06)], 48, mat=dark)
    G.place(well, (0, 0, 0), (90, 0, 0))
    G.place(well, (fx, -D / 2 - 0.001, fz))
    hubc = G.cyl("hub", 0.05, 0.04, loc=(0, 0, 0), segs=24, mat=dark)
    G.place(hubc, (0, 0, 0), (-90, 0, 0))
    G.place(hubc, (fx, -D / 2 + 0.05, fz))
    parts += [well, hubc]
    for k in range(3):
        bl = G.extrude("blade", [(0.04, -0.03), (0.19, -0.07), (0.2, 0.02), (0.05, 0.035)], 0.004, mat=dark,
                       bevel=0.0015)
        G.place(bl, (0, 0, 0), (20, 0, 0))
        G.place(bl, (0, 0, 0), (90, 0, 0))
        G.place(bl, (0, 0, 0), (0, k * 120, 0))
        G.place(bl, (fx, -D / 2 + 0.045, fz))
        parts.append(bl)
    for rr in [0.03 + 0.03 * i for i in range(7)]:
        ring = G.tube("gr", [(fx + math.cos(a) * rr, -D / 2 - 0.012, fz + math.sin(a) * rr)
                             for a in [j * 2 * math.pi / 36 for j in range(37)]], 0.0022, 5, mat=grille)
        parts.append(ring)
    for k in range(4):
        a = k * math.pi / 4
        parts.append(G.tube("spoke", [(fx + math.cos(a) * fr, -D / 2 - 0.012, fz + math.sin(a) * fr),
                                      (fx - math.cos(a) * fr, -D / 2 - 0.012, fz - math.sin(a) * fr)], 0.0025, 5,
                            mat=grille))
    # side panel (left): louvred coil
    for k in range(14):
        lv = G.rbox("louver", (0.012, D - 0.04, 0.012), bevel=0.003, mat=shell)
        G.place(lv, (0, 0, 0), (0, -30, 0))
        G.place(lv, (-W / 2 - 0.004, 0, Z0 + 0.06 + k * 0.031))
        parts.append(lv)
    coil = G.rbox("coil", (W - 0.06, 0.01, H - 0.08), bevel=0.0, mat=fin)
    G.place(coil, (0, D / 2 + 0.002, Z0 + 0.04))
    parts.append(coil)
    for k in range(18):
        bar = G.rbox("bgr", (0.006, 0.006, H - 0.08), bevel=0.0, mat=grille)
        G.place(bar, (-W / 2 + 0.05 + k * 0.04, D / 2 + 0.01, Z0 + 0.04))
        parts.append(bar)
    # valve cover + pipes on the right side
    cover = G.rbox("vcover", (0.012, 0.16, 0.14), bevel=0.004, mat=shell)
    G.place(cover, (W / 2 + 0.008, -0.02, Z0 + 0.1))
    parts.append(cover)
    for k, (yy, r) in enumerate(((-0.05, 0.016), (0.02, 0.011))):
        pts = [(W / 2 + 0.01, yy, Z0 + 0.15), (W / 2 + 0.08, yy, Z0 + 0.15), (W / 2 + 0.1, yy + 0.02, Z0 + 0.25),
               (W / 2 + 0.1, yy + 0.08, Z0 + 0.55), (W / 2 + 0.1, yy + 0.2, Z0 + 0.62)]
        parts.append(G.tube("pipe", pts, r + 0.008, 10, mat=foam))
        parts.append(G.tube("cu", pts[:2], r, 10, mat=copper))
    tape = G.tube("tape", helix((W / 2 + 0.1, 0.0), 0.04, Z0 + 0.3, Z0 + 0.5, 6, 80), 0.003, 5, mat=foam)
    drain = G.tube("drain", [(-0.2, 0.0, Z0 + 0.005), (-0.25, -0.05, 0.03), (-0.3, -0.25, 0.006)], 0.007, 8,
                   mat=dark)
    parts += [tape, drain]
    for x in (-W / 2 + 0.08, W / 2 - 0.08):
        rail = G.rbox("rail", (0.05, D + 0.06, 0.04), bevel=0.006, mat=shell)
        G.place(rail, (x, 0, 0.02))
        parts.append(rail)
        for y in (-D / 2 - 0.01, D / 2 + 0.01):
            parts.append(G.cyl("foot", 0.025, 0.02, loc=(x, y, 0.0), segs=12, mat=rub))
    badge = G.rbox("badge", (0.09, 0.004, 0.025), bevel=0.001, mat=PN.metal("badge", "chrome"))
    G.place(badge, (-0.26, -D / 2 - 0.002, Z0 + H - 0.07))
    parts.append(badge)
    cols = [G.col_box("metal", (W, D, H + Z0))]
    marks = [G.marker("NAP_01", (0, 0, H + Z0 + 0.006))]
    return {"parts": parts, "colliders": cols, "markers": marks}


# ---------------------------------------------------------------------------
# LPG cylinder 12 kg
# ---------------------------------------------------------------------------
@prop("gas_cylinder", category="utility", kind="container", surface="metal", mass=26.0, material_kind="metal",
      tags=["kitchen"])
def gas_cylinder():
    red = PN.painted_metal("lpg", "#b62a24", primer="#5d2a1e", chip=0.5, rust=0.55, gloss=0.5, streaks=0.4,
                           dirt=0.6, dust=0.4, ground=0.8, label=True, label_wear=0.35)
    brass = PN.metal("valve", "brass", wear=0.6)
    reg = PN.plastic("reg", "#e0812a", rough=0.4, fade=0.4, dirt=0.5)
    hose = PN.rubber("hose", "#262626", rough=0.6)
    parts = []
    R = 0.152
    body = G.lathe("body", [(0.0, 0.05), (0.07, 0.05), (0.12, 0.06), (0.148, 0.09), (R, 0.13), (R, 0.47),
                            (0.145, 0.51), (0.12, 0.54), (0.07, 0.56), (0.03, 0.565), (0.0, 0.565)], 40, mat=red, max_seg=0.02)
    G.label_cyl(body, (0, 0, 1, 1), 0.22, 0.4, a0=-math.pi / 2 - 1.2, a1=-math.pi / 2 + 1.2)
    G.dent(body, (0.1, -0.11, 0.3), 0.06, 0.006)
    foot = G.lathe("foot", [(0.13, 0.0), (0.14, 0.0), (0.14, 0.06), (0.13, 0.06)], 40, mat=red)
    seam = G.lathe("seam", [(R, 0.295), (R + 0.004, 0.3), (R, 0.305)], 40, mat=red)
    guard = G.lathe("guard", [(0.105, 0.55), (0.11, 0.55), (0.11, 0.66), (0.105, 0.66)], 32, mat=red)
    G.solidify(guard, 0.003)
    gr = G.lathe("guardrim", [(0.1, 0.655), (0.115, 0.66), (0.1, 0.665)], 32, mat=red)
    valve = G.lathe("valve", [(0.0, 0.565), (0.02, 0.565), (0.02, 0.6), (0.015, 0.61), (0.015, 0.63), (0.0, 0.63)], 16,
                    mat=brass)
    regb = G.lathe("regulator", [(0.0, 0.0), (0.035, 0.0), (0.04, 0.02), (0.035, 0.045), (0.0, 0.05)], 20, mat=reg)
    G.place(regb, (0.0, 0.0, 0.63))
    hosep = G.tube("hose", [(0.035, 0.0, 0.655), (0.09, 0.0, 0.66), (0.14, -0.05, 0.62), (0.2, -0.12, 0.4),
                            (0.24, -0.2, 0.15), (0.3, -0.3, 0.01), (0.5, -0.35, 0.01)], 0.007, 8, mat=hose)
    parts += [body, foot, seam, guard, gr, valve, regb, hosep]
    cols = [G.col_cyl("metal", R, 0.66, segs=12)]
    return {"parts": parts, "colliders": cols, "label": L("gas_cylinder")}
