"""Knockable desk / table / shelf clutter for the "knock it off" mischief (all dynamic RigidBody props
via the post-import: Pushable, material_kind, mass). Real sizes; origin bottom centre."""
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


def clutter(pid, *, mass, material_kind, surface="plastic", tags=(), break_height=None, **kw):
    extra = {"break_height": break_height} if break_height is not None else {}
    return prop(pid, category="clutter", kind="clutter", dynamic=True, mass=mass, surface=surface,
                material_kind=material_kind, tags=["knockable", *tags], density=kw.pop("density", 1536.0),
                max_tex=kw.pop("max_tex", 1024), min_tex=kw.pop("min_tex", 256), **extra, **kw)


def shell_lathe(name, outer, wall, segs, mat, rfunc=None):
    """Open vessel: outer profile [(r, z)] bottom->rim, closed bottom; inner wall offset by `wall`."""
    inner = [(max(0.0, r - wall), z + (wall if i == 0 else 0.0)) for i, (r, z) in enumerate(outer)]
    rim_r, rim_z = outer[-1]
    prof = [(0.0, outer[0][1])] + outer + [(rim_r - wall * 0.5, rim_z + wall * 0.15)] + inner[::-1][:-1] + \
        [(inner[0][0], inner[0][1]), (0.0, inner[0][1])]
    # lathe auto-orients; inner part follows the reversed outer path, keeping the loop closed
    return G.lathe(name, prof, segs, mat=mat, rfunc=rfunc, max_seg=0.008)


# ---------------------------------------------------------------------------
@clutter("cup_ceramic", mass=0.22, material_kind="ceramic", surface="tile", break_height=1.2,
         tags=["cup", "table"])
def cup_ceramic():
    """Blue-and-white porcelain coffee cup (Bát Tràng style motif) with a loop handle, 8 cm."""
    por = PN.ceramic("porcelain", "#eef0ec", rough=0.08, crackle=0.15, chip=0.3, label=True, label_wear=0.05,
                     dirt=0.2, speckle=0.15)
    coffee = PN.organic("coffee", [(0.0, "#1c0f07"), (0.7, "#2c170a"), (1.0, "#4a2a12")], scale=20, rough=0.05,
                        detail_scale=200, h_amp=0.0, dirt=0.0)
    out = [(0.026, 0.0), (0.03, 0.004), (0.036, 0.02), (0.04, 0.05), (0.042, 0.075), (0.043, 0.08)]
    cup = shell_lathe("cup", out, 0.0032, 40, por)
    G.label_cyl(cup, (0.0, 0.5, 1.0, 1.0), 0.008, 0.078, a0=-math.pi, a1=math.pi, radial_min=0.0335)
    foot = G.lathe("foot", [(0.024, 0.0), (0.027, 0.0), (0.027, 0.004), (0.024, 0.004)], 40, mat=por)
    handle = G.tube("handle", [(0.038, 0, 0.064), (0.052, 0, 0.066), (0.06, 0, 0.05), (0.052, 0, 0.032),
                               (0.037, 0, 0.026)], 0.0042, 10, mat=por)
    G.place(handle, (0, 0, 0), (0, 0, 0), (1, 1.4, 1))
    liquid = G.lathe("coffee", [(0.0, 0.055), (0.039, 0.055)], 32, mat=coffee)
    cols = [G.col_cyl("tile", 0.042, 0.08, segs=10)]
    return {"parts": [cup, foot, handle, liquid], "colliders": cols, "label": L("ceramic_patterns")}


@clutter("mug_enamel", mass=0.18, material_kind="metal", surface="metal", tags=["cup", "table"])
def mug_enamel():
    """Classic white enamel-on-steel mug with blue rim, chipped to black steel at the edges."""
    enamel = PN.painted_metal("enamel", "#f0eee6", primer="#1c1c22", bare="#26262a", chip=0.55, rust=0.25,
                              gloss=0.15, streaks=0.0, dirt=0.35, dust=0.15)
    blue = PN.painted_metal("enrim", "#1f4b9a", primer="#1c1c22", bare="#26262a", chip=0.6, rust=0.2, gloss=0.15,
                            streaks=0.0, dirt=0.3)
    out = [(0.039, 0.0), (0.041, 0.003), (0.041, 0.085)]
    mug = shell_lathe("mug", out, 0.0012, 40, enamel)
    rim = G.lathe("rim", [(0.0408, 0.0835), (0.0425, 0.0855), (0.042, 0.0875), (0.0398, 0.0865)], 40, mat=blue)
    handle = G.tube("handle", [(0.04, 0, 0.074), (0.058, 0, 0.07), (0.062, 0, 0.045), (0.054, 0, 0.022),
                               (0.04, 0, 0.018)], 0.0035, 8, mat=enamel)
    G.place(handle, (0, 0, 0), (0, 0, 0), (1, 1.8, 1))
    G.dent(mug, (0.0, -0.041, 0.03), 0.012, 0.0015)
    cols = [G.col_cyl("metal", 0.041, 0.087, segs=10)]
    return {"parts": [mug, rim, handle], "colliders": cols}


@clutter("glass_tra_da", mass=0.25, material_kind="glass", surface="plastic", break_height=0.9,
         tags=["cup", "table", "glass"])
def glass_tra_da():
    """Ribbed pressed-glass tumbler of iced tea (trà đá) — the street-corner classic, 11 cm."""
    tea = PN.organic("tea", [(0.0, "#7a4a12"), (0.5, "#9a6420"), (1.0, "#b98232")], scale=12, rough=0.05,
                     detail_scale=80, h_amp=0.1, dirt=0.0, cav_dark=0.1)
    ice = PN.glass_opaque("ice", "#d8e2e0", rough=0.1, dirt=0.0, frost=0.5)
    base = PN.glass_opaque("gbase", "#c3d2cc", rough=0.05, dirt=0.25)
    Hh = 0.11
    foot = G.lathe("foot", [(0.0, 0.0), (0.028, 0.0), (0.029, 0.003), (0.029, 0.012), (0.0, 0.012)], 36, mat=base,
                   rfunc=lambda r, z, a: r * (1 + 0.025 * max(0.0, math.cos(a * 12))))
    liquid = G.lathe("tea", [(0.0, 0.012), (0.0278, 0.012), (0.033, 0.075), (0.0, 0.075)], 32, mat=tea)
    parts = [foot, liquid]
    rng = random.Random(4)
    for k in range(4):
        cube = G.rbox("ice", (0.017, 0.017, 0.015), mat=ice, bevel=0.003, segs=2, centre=True)
        G.place(cube, (0, 0, 0), (rng.uniform(0, 40), rng.uniform(0, 40), rng.uniform(0, 90)))
        a = k * 1.7
        G.place(cube, (math.cos(a) * 0.012, math.sin(a) * 0.012, 0.07 + 0.004 * k))
        parts.append(cube)
    wall = G.lathe("glass_wall", [(0.0285, 0.003), (0.035, Hh), (0.0335, Hh), (0.027, 0.012)], 36,
                   mat=PN.glass_material("glass_clear", (0.86, 0.92, 0.9), alpha=0.16, rough=0.04),
                   rfunc=lambda r, z, a: r * (1 + 0.02 * max(0.0, math.cos(a * 12))))
    cols = [G.col_cyl("plastic", 0.034, Hh, segs=10, r2=0.035)]
    return {"parts": parts, "glass": [wall], "colliders": cols}


@clutter("vase_flower", mass=1.1, material_kind="ceramic", surface="tile", break_height=0.8,
         tags=["vase", "table", "altar"])
def vase_flower():
    """Blue-and-white baluster vase with three yellow chrysanthemums (cúc vàng), 38 cm overall."""
    por = PN.ceramic("vase", "#e9ece6", rough=0.07, crackle=0.3, chip=0.25, label=True, label_wear=0.05, dirt=0.3)
    stem = PN.organic("stem", [(0.0, "#2f4a1c"), (1.0, "#56783a")], scale=40, rough=0.5)
    leafm = PN.leaf("cleaf", "#3b5e26", vein="#6b8a4a", rough=0.5, role="2s", spots=0.3)
    petal = PN.organic("petal", [(0.0, "#d89a10"), (0.5, "#f0bc22"), (1.0, "#f8d660")], scale=60, rough=0.6,
                       role="2s", sss=0.2)
    prof = [(0.045, 0.0), (0.05, 0.006), (0.075, 0.06), (0.083, 0.11), (0.07, 0.16), (0.04, 0.2), (0.032, 0.225),
            (0.036, 0.24), (0.044, 0.25)]
    vase = shell_lathe("vase", prof, 0.005, 44, por)
    G.label_cyl(vase, (0.0, 0.0, 1.0, 1.0), 0.03, 0.2, a0=-math.pi, a1=math.pi, radial_min=0.05)
    foot = G.lathe("foot", [(0.04, 0.0), (0.047, 0.0), (0.047, 0.006), (0.04, 0.006)], 44, mat=por)
    parts = [vase, foot]
    rng = random.Random(11)
    for k in range(3):
        a = k * 2.1 + 0.3
        top = Vector((math.cos(a) * 0.07, math.sin(a) * 0.07, 0.36 + 0.03 * k))
        pts = [(math.cos(a) * 0.008, math.sin(a) * 0.008, 0.1), (math.cos(a) * 0.02, math.sin(a) * 0.02, 0.25),
               tuple(top)]
        parts.append(G.tube("stem", pts, 0.0028, 6, mat=stem))
        # chrysanthemum head: rings of narrow curved petals around a dome
        for ring in range(4):
            n = 14 + ring * 4
            rr = 0.008 + ring * 0.007
            for i in range(n):
                ph = 2 * math.pi * i / n + ring * 0.3
                pl = G.grid("petal", 0.016 + ring * 0.003, 0.0045, 3, 1, mat=petal)
                for v in pl.data.vertices:
                    v.co.z += 0.12 * (v.co.x + 0.01) ** 2 * 60
                G.place(pl, (0.008 + ring * 0.0015, 0, 0))
                G.place(pl, (0, 0, 0), (0, -(60 - ring * 18), math.degrees(ph)))
                G.place(pl, tuple(top + Vector((0, 0, 0.012 - ring * 0.004))))
                parts.append(pl)
            del rr
        for j in range(2):
            lf = G.grid("leaf", 0.06, 0.03, 6, 2, mat=leafm,
                        fn=lambda x, y: -0.4 * x * x + 0.15 * y * y * 10 - 0.0)
            for v in lf.data.vertices:
                f = 1 - (abs(v.co.x) / 0.03) ** 2 if abs(v.co.x) < 0.03 else 0
                v.co.y *= max(0.15, f ** 0.5)
            G.place(lf, (0.03, 0, 0))
            p = Vector(pts[1]).lerp(top, 0.3 + 0.35 * j)
            G.place(lf, (0, 0, 0), (rng.uniform(-30, 10), 0, math.degrees(a) + (90 if j else -90)))
            G.place(lf, tuple(p))
            parts.append(lf)
    cols = [G.col_cyl("tile", 0.083, 0.25, segs=10)]
    return {"parts": parts, "colliders": cols, "label": L("ceramic_patterns")}


@clutter("cactus_pot", mass=0.35, material_kind="ceramic", surface="tile", break_height=1.0,
         tags=["plant", "table", "windowsill"])
def cactus_pot():
    """Small terracotta pot with a ribbed barrel cactus (spines) and white pebble top dressing."""
    pot = PN.terracotta("pot", "#b0603c", salt=0.5, moss=0.15, dirt=0.4)
    cact = PN.organic("cactus", [(0.0, "#2e5a2a"), (0.5, "#3f7438"), (1.0, "#5d8e4c")], scale=12, rough=0.4,
                      detail_scale=200, h_amp=0.3)
    spine = PN.organic("spine", [(0.0, "#d9cfa8"), (1.0, "#f2ead0")], scale=50, rough=0.4)
    pebble = PN.organic("pebble", [(0.0, "#c9c4b8"), (1.0, "#efece4")], scale=20, rough=0.6)
    out = [(0.032, 0.0), (0.034, 0.004), (0.042, 0.065), (0.047, 0.068), (0.048, 0.078)]
    p = shell_lathe("pot", out, 0.005, 36, pot)
    soil = G.lathe("soil", [(0.0, 0.07), (0.043, 0.068)], 24, mat=pebble)
    parts = [p, soil]
    rng = random.Random(7)
    for k in range(10):
        a, r = rng.uniform(0, 6.28), rng.uniform(0.028, 0.04)
        parts.append(G.sphere("peb", 0.004, loc=(math.cos(a) * r, math.sin(a) * r, 0.071), mat=pebble, segs=8,
                              rings=5, scale=(1, 0.8, 0.6)))
    prof = [(0.0, 0.066)] + [(0.032 * math.sin(math.pi * (0.15 + 0.85 * i / 12)) ** 0.6, 0.066 + 0.085 * i / 12)
                             for i in range(13)] + [(0.0, 0.153)]
    body = G.lathe("cactus", prof, 48, mat=cact, rfunc=lambda r, z, a: r * (1 + 0.1 * math.cos(a * 12)))
    parts.append(body)
    # spine clusters along the 12 ribs
    for rib in range(12):
        a = 2 * math.pi * rib / 12
        for j in range(5):
            t = 0.2 + j * 0.15
            z = 0.066 + 0.085 * t
            r = 0.032 * math.sin(math.pi * (0.15 + 0.85 * t)) ** 0.6 * 1.1
            base = Vector((math.cos(a) * r, math.sin(a) * r, z))
            for s in range(3):
                d = Vector((math.cos(a + (s - 1) * 0.5), math.sin(a + (s - 1) * 0.5), 0.3 + s * 0.2)).normalized()
                parts.append(G.tube("spine", [tuple(base), tuple(base + d * 0.007)], 0.00045, 3, mat=spine,
                                    rfunc=lambda tt: 1 - 0.8 * tt, cap=False))
    cols = [G.col_cyl("tile", 0.048, 0.15, segs=10, r2=0.04)]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Bottles (label sheet 'bottles': rows fish sauce / soy / water / tonic)
# ---------------------------------------------------------------------------
def _bottle(name, mat, H, R, shoulder, neck_r, neck_h):
    prof = [(0.0, 0.0), (R * 0.88, 0.0), (R, 0.006), (R, shoulder), (R * 0.82, shoulder + (H - shoulder - neck_h) * 0.4),
            (neck_r * 1.05, H - neck_h), (neck_r, H - neck_h * 0.7), (neck_r * 1.12, H - 0.006), (neck_r * 1.12, H),
            (0.0, H)]
    return G.lathe(name, prof, 36, mat=mat, max_seg=0.008)


@clutter("bottle_fish_sauce", mass=0.75, material_kind="glass", surface="plastic", break_height=0.7,
         tags=["bottle", "kitchen"])
def bottle_fish_sauce():
    gl = PN.glass_opaque("fsglass", "#5a3a12", rough=0.05, dirt=0.35, label=True, label_wear=0.2)
    capm = PN.plastic("fscap", "#c22a24", rough=0.35, fade=0.3, scratch=0.5, dirt=0.4)
    b = _bottle("bottle", gl, 0.26, 0.032, 0.15, 0.012, 0.06)
    G.label_cyl(b, (0.0, 0.75, 1.0, 1.0), 0.04, 0.12, a0=-math.pi / 2 - 1.6, a1=-math.pi / 2 + 1.6, radial_min=0.03)
    cap = G.cyl("cap", 0.0145, 0.022, segs=32, bevel=0.0015, mat=capm)
    G.place(cap, (0, 0, 0.25))
    cols = [G.col_cyl("plastic", 0.032, 0.27, segs=10, r2=0.015)]
    return {"parts": [b, cap], "colliders": cols, "label": L("bottles")}


@clutter("bottle_soy", mass=0.6, material_kind="glass", surface="plastic", break_height=0.7,
         tags=["bottle", "kitchen", "table"])
def bottle_soy():
    gl = PN.glass_opaque("soyglass", "#2a1a0e", rough=0.05, dirt=0.3, label=True, label_wear=0.15)
    capm = PN.plastic("soycap", "#e8b020", rough=0.35, fade=0.3, scratch=0.4, dirt=0.4)
    b = _bottle("bottle", gl, 0.22, 0.028, 0.12, 0.011, 0.055)
    G.label_cyl(b, (0.0, 0.5, 1.0, 0.75), 0.035, 0.1, a0=-math.pi / 2 - 1.7, a1=-math.pi / 2 + 1.7, radial_min=0.026)
    cap = G.cyl("cap", 0.013, 0.02, segs=32, bevel=0.0015, mat=capm)
    G.place(cap, (0, 0, 0.212))
    cols = [G.col_cyl("plastic", 0.028, 0.23, segs=10, r2=0.014)]
    return {"parts": [b, cap], "colliders": cols, "label": L("bottles")}


@clutter("bottle_water", mass=0.52, material_kind="plastic", surface="plastic", tags=["bottle", "table"])
def bottle_water():
    """500 ml PET water bottle 'Nước suối Mây', ribbed, a bit crushed."""
    pet = PN.glass_opaque("pet", "#a9c7d2", rough=0.08, dirt=0.15, label=True, label_wear=0.1)
    water = PN.glass_opaque("water", "#7fa9b8", rough=0.04, dirt=0.0)
    capm = PN.plastic("wcap", "#1f5fb8", rough=0.4, fade=0.2, scratch=0.4, dirt=0.3)
    H, R = 0.21, 0.0325

    def ribs(r, z, a):
        k = 1 + (0.03 * math.sin(z * 260) if 0.03 < z < 0.11 else 0.0)
        return r * k * (1 - 0.04 * max(0.0, math.cos(a - 0.6)) * math.exp(-((z - 0.06) / 0.03) ** 2))
    b = G.lathe("pet", [(0.0, 0.0), (R * 0.7, 0.0), (R, 0.012), (R, 0.13), (R * 0.75, 0.165), (0.013, 0.188),
                        (0.0125, 0.196), (0.0145, 0.198), (0.0, 0.198)], 36, mat=pet, rfunc=ribs, max_seg=0.008)
    G.label_cyl(b, (0.0, 0.25, 1.0, 0.5), 0.115, 0.15, a0=-math.pi, a1=math.pi, radial_min=0.03)
    cap = G.cyl("cap", 0.0145, 0.013, segs=32, bevel=0.0012, mat=capm)
    G.place(cap, (0, 0, 0.197))
    lvl = G.lathe("waterline", [(0.0, 0.15), (R * 0.88, 0.15)], 24, mat=water)
    cols = [G.col_cyl("plastic", R, H, segs=10, r2=0.014)]
    return {"parts": [b, cap, lvl], "colliders": cols, "label": L("bottles")}


# ---------------------------------------------------------------------------
# Phone & remote (label 'phone_remote')
# ---------------------------------------------------------------------------
@clutter("phone", mass=0.18, material_kind="plastic", surface="plastic", tags=["electronics", "table", "bed"])
def phone():
    """Budget smartphone face-up, cracked screen corner, worn blue silicone case."""
    case = PN.plastic("case", "#3a6aa0", rough=0.6, fade=0.4, scratch=0.7, dirt=0.6, textured=0.6)
    screen = PN.label_only("screen", base="#101216", rough=0.06, wear=0.0, dirt=0.15, dust=0.15)
    W, D, H = 0.078, 0.162, 0.011
    body = G.extrude("case", G.rounded_rect(W, D, 0.01, 5), H, mat=case, bevel=0.0028, segs=3, centre=False)
    scr = G.extrude("screen", G.rounded_rect(W - 0.007, D - 0.007, 0.007, 5), 0.0006, mat=screen, centre=False)
    G.place(scr, (0, 0, H - 0.0003))
    G.label_planar(scr, (0.0, 0.0, 0.5, 1.0), (-(W - 0.007) / 2, -(D - 0.007) / 2, 0), (1, 0, 0), (0, 1, 0),
                   (W - 0.007, D - 0.007), normal=(0, 0, 1), min_dot=0.5)
    # crack lines in the top-left corner (dark glossy tubes, very thin)
    crack = PN.glass_opaque("crack", "#d8dde0", rough=0.3, dirt=0.0)
    parts = [body, scr]
    rng = random.Random(5)
    o = Vector((-W / 2 + 0.008, D / 2 - 0.01, H + 0.0004))
    for k in range(5):
        d = Vector((math.cos(rng.uniform(-0.6, 0.0) - k * 0.35), math.sin(rng.uniform(-0.6, 0.0) - k * 0.35), 0))
        pts = [tuple(o), tuple(o + d * 0.01 + Vector((0.002 * k, 0, 0))), tuple(o + d * rng.uniform(0.02, 0.035))]
        parts.append(G.tube("crack", pts, 0.00018, 3, mat=crack, cap=False))
    cam = G.cyl("camera", 0.006, 0.0015, segs=20, bevel=0.0003, mat=screen)
    G.place(cam, (0, 0, 0), (180, 0, 0))
    G.place(cam, (-0.022, 0.06, 0.0002))
    parts.append(cam)
    G.lean(body, 0.0, 0.0)
    cols = [G.col_box("plastic", (W, D, H))]
    return {"parts": parts, "colliders": cols, "label": L("phone_remote")}


@clutter("tv_remote", mass=0.12, material_kind="plastic", surface="plastic", tags=["electronics", "table", "sofa"])
def tv_remote():
    """Black TV remote with rubber keypad (label sheet right half), back battery cover taped."""
    shell = PN.plastic("rshell", "#1d1d20", rough=0.45, fade=0.25, scratch=0.8, dirt=0.6, textured=0.3, label=True,
                       label_wear=0.35)
    tape = PN.plastic("rtape", "#d9cfb0", rough=0.6, fade=0.0, scratch=0.2, dirt=0.6)
    W, D, H = 0.048, 0.19, 0.022
    body = G.extrude("remote", G.rounded_rect(W, D, 0.012, 5), H, mat=shell, bevel=0.005, segs=3, centre=False)
    for v in body.data.vertices:
        v.co.z *= 1.0 - 0.25 * max(0.0, (v.co.y + D / 2) / D - 0.6)
    G.label_planar(body, (0.5, 0.0, 1.0, 1.0), (-W / 2, -D / 2, 0), (1, 0, 0), (0, 1, 0), (W, D), normal=(0, 0, 1),
                   min_dot=0.6)
    parts = [body]
    # raised buttons matching the printed grid (label right half: x0+90.., y0+220.. step 160/140 px of 512/1024)
    for k in range(12):
        col, row = k % 3, k // 3
        u = (90 + col * 160) / 512.0
        v = 1.0 - (220 + row * 140) / 1024.0
        x = -W / 2 + u * W
        y = -D / 2 + v * D
        btn = G.extrude("btn", G.rounded_rect(0.0085, 0.0066, 0.0025, 3), 0.0016, mat=shell, bevel=0.0006, segs=1,
                        centre=False)
        G.place(btn, (x, y, H * (1.0 - 0.25 * max(0.0, (y + D / 2) / D - 0.6)) - 0.0004))
        G.label_planar(btn, (0.5, 0.0, 1.0, 1.0), (-W / 2, -D / 2, 0), (1, 0, 0), (0, 1, 0), (W, D),
                       normal=(0, 0, 1), min_dot=0.6)
        parts.append(btn)
    t = G.rbox("tape", (W + 0.002, 0.025, 0.0006), mat=tape, bevel=0.0, segs=1)
    G.place(t, (0, -0.06, -0.0001))
    for s in (-1, 1):
        te = G.rbox("tape_s", (0.0006, 0.025, H * 0.6), mat=tape, bevel=0.0)
        G.place(te, (s * (W / 2 + 0.0004), -0.06, 0.0))
        parts.append(te)
    parts.append(t)
    G.place(t, (0, 0, 0))
    cols = [G.col_box("plastic", (W, D, H))]
    return {"parts": parts, "colliders": cols, "label": L("phone_remote")}


# ---------------------------------------------------------------------------
# Books (label 'books': 4 bands — spine 0..0.15 / cover 0.15..1)
# ---------------------------------------------------------------------------
def _book(idx, W, D, H, mat_cover, mat_pages, loc=(0, 0, 0), rot=0.0, open_k=0.0):
    """Hardcover lying flat: spine on -X, cover faces +Z. Returns parts."""
    v0, v1 = 1.0 - (idx + 1) * 0.25, 1.0 - idx * 0.25
    t = 0.0025
    parts = []
    pages = G.rbox("pages", (W - 0.006, D - 0.006, H - 2 * t), mat=mat_pages, bevel=0.0008, segs=1)
    G.place(pages, (0.003, 0, t))
    for v in pages.data.vertices:
        if v.co.x > W / 2 - 0.01:
            v.co.z += open_k * (v.co.z - H / 2) * 0.2
    top = G.rbox("cover", (W, D, t), mat=mat_cover, bevel=0.0008, segs=1)
    G.place(top, (0, 0, H - t))
    bot = G.rbox("cover_b", (W, D, t), mat=mat_cover, bevel=0.0008, segs=1)
    spine = G.lathe("spine", [(H / 2, -D / 2), (H / 2, D / 2)], 16, mat=mat_cover, smooth_angle=None)
    G.place(spine, (0, 0, 0), (90, 0, 0))
    G.place(spine, (0, 0, 0), (0, 0, 0), (0.45, 1, 1))
    G.place(spine, (-W / 2 + 0.0015, 0, H / 2))
    # labels: cover (top face) 0.15..1, spine band 0..0.15 (on -X, rotated text)
    G.label_planar(top, (0.15, v0, 1.0, v1), (-W / 2, D / 2, 0), (1, 0, 0), (0, -1, 0), (W, D), normal=(0, 0, 1),
                   min_dot=0.6)
    G.label_planar(spine, (0.0, v0, 0.15, v1), (-W, D / 2, 0), (0, 0, 1), (0, -1, 0), (H, D), normal=(-1, 0, 0),
                   min_dot=0.3)
    parts += [pages, top, bot, spine]
    for p in parts:
        G.place(p, (0, 0, 0), (0, 0, rot))
        G.place(p, loc)
    return parts


def _book_mats():
    cover = PN.paper("bcover", "#d9cfb6", aged=0.4, label=True, label_wear=0.25, role="base", rough=0.6, dirt=0.4)
    pages = PN.paper("bpages", "#eadfc3", aged=0.6, label=False, role="base", rough=0.9, dirt=0.3, fibre=0.8)
    return cover, pages


@clutter("book_single", mass=0.45, material_kind="soft", surface="fabric", tags=["book", "table", "shelf"])
def book_single():
    cover, pages = _book_mats()
    parts = _book(1, 0.15, 0.21, 0.026, cover, pages, open_k=1.0)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.15, 0.21, 0.026))], "label": L("books")}


@clutter("book_stack", mass=1.6, material_kind="soft", surface="fabric", tags=["book", "table", "shelf", "standable"])
def book_stack():
    """Three/four books stacked crooked — a cat-height step and a classic knock target."""
    cover, pages = _book_mats()
    parts = []
    z = 0.0
    rng = random.Random(3)
    dims = [(0.17, 0.24, 0.032), (0.15, 0.21, 0.026), (0.145, 0.205, 0.02), (0.13, 0.19, 0.03)]
    for i, (w, d, h) in enumerate(dims):
        parts += _book(i, w, d, h, cover, pages, loc=(rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), z),
                       rot=rng.uniform(-12, 12), open_k=0.5)
        z += h
    cols = [G.col_box("fabric", (0.17, 0.24, z))]
    return {"parts": parts, "colliders": cols, "label": L("books")}


@clutter("can_condensed_milk", mass=0.4, material_kind="metal", surface="metal", tags=["kitchen", "can", "table"])
def can_condensed_milk():
    """Tin of sweetened condensed milk (for cà phê sữa) — printed tin, opened with two punch holes."""
    nb = PN.NB("tinprint", "base")
    # printed band: cream with blue band + red stripes, done procedurally (no brand)
    z = nb.z
    band = nb.smooth(nb.math("ABSOLUTE", nb.sub(z, 0.04)), 0.018, 0.016)
    stripe = nb.smooth(nb.math("ABSOLUTE", nb.sub(z, 0.064)), 0.0025, 0.002)
    col = nb.mixc(band, "#efe3c2", "#1f4e9a")
    col = nb.mixc(stripe, col, "#c52a24")
    s = nb.st(col, 0.32, 0.25, nb.mul(nb.scratches(140, 0.5), -0.2))
    wear = nb.edge_wear(0.5, 60)
    s = nb.layer(s, nb.st("#b9b8b2", 0.25, 1.0, 0.0), wear)
    s = nb.weather(s, dirt=0.5, dust=0.3)
    printm = nb.finish(s, bump=0.0002)
    tin = PN.metal("tin", "tin", dirt=0.5, wear=0.4, rust=0.15)
    H, R = 0.08, 0.037
    body = G.lathe("can", [(R - 0.002, 0.0), (R, 0.003), (R, H - 0.003), (R - 0.002, H)], 40, mat=printm,
                   rfunc=lambda r, z, a: r * (1 + 0.004 * math.sin(z * 900)))
    lid = G.lathe("lid", [(0.0, H - 0.002), (R - 0.004, H - 0.002), (R - 0.0025, H), (R - 0.001, H + 0.0025),
                          (R, H + 0.002)], 40, mat=tin)
    base = G.lathe("base", [(0.0, 0.002), (R - 0.004, 0.002), (R - 0.0025, 0.0), (R - 0.001, -0.0)], 40, mat=tin)
    parts = [body, lid, base]
    for s in (-1, 1):
        hole = G.lathe("hole", [(0.0, H - 0.0035), (0.003, H - 0.0035), (0.0042, H - 0.0016)], 12, mat=tin)
        G.place(hole, (s * 0.02, 0, 0))
        parts.append(hole)
    drip = G.sphere("drip", 0.003, loc=(0.02, -R + 0.001, H - 0.008), mat=PN.organic("milk", [(0.0, "#e9d9a8"),
                                                                                              (1.0, "#f4e8c2")],
                                                                                      scale=10, rough=0.15),
                    segs=8, rings=6, scale=(0.8, 0.5, 2.5))
    parts.append(drip)
    cols = [G.col_cyl("metal", R, H + 0.002, segs=10)]
    return {"parts": parts, "colliders": cols}
