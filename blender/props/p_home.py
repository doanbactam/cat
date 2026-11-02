"""Home & container props: boxes, crates, sacks, buckets, brooms, potted plants, bird cage, wind chime,
altar, laundry rack, footwear, pet bowls."""
import json
import math
import os
import random
import sys

import bmesh
from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import props_geo as G  # noqa: E402
import props_nodes as PN  # noqa: E402
from props_bake import prop, register  # noqa: E402

LABELS = os.path.join(HERE, "labels")


def L(name):
    return os.path.join(LABELS, name + ".png")


def light_marker(name, loc, **info):
    m = G.marker(name, loc)
    m["light_json"] = json.dumps(info)
    return m


def open_box(name, w, d, h, t, mat):
    """Open-top box shell (walls + bottom) with wall thickness t (outer size w x d x h)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * d, (v.co.z + 0.5) * h))
    top = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.delete(bm, geom=top, context="FACES")
    ob = G.obj_from_bm(name, bm, mat)
    G.solidify(ob, t, offset=-1.0)
    return ob


# ---------------------------------------------------------------------------
# Cardboard
# ---------------------------------------------------------------------------
def _box_labels(ob, w, d, h, z0=0.0, front_rect=(0.0, 0.0, 0.5, 0.62), back_rect=(0.5, 0.0, 1.0, 0.62),
                side_rects=((0.0, 0.64, 0.5, 1.0), (0.5, 0.64, 1.0, 1.0))):
    G.label_planar(ob, front_rect, (-w / 2, -d / 2, z0), (1, 0, 0), (0, 0, 1), (w, h), normal=(0, -1, 0), min_dot=0.8, bounds_pad=0.01)
    G.label_planar(ob, back_rect, (w / 2, d / 2, z0), (-1, 0, 0), (0, 0, 1), (w, h), normal=(0, 1, 0), min_dot=0.8, bounds_pad=0.01)
    G.label_planar(ob, side_rects[0], (w / 2, -d / 2, z0), (0, 1, 0), (0, 0, 1), (d, h), normal=(1, 0, 0), min_dot=0.8, bounds_pad=0.01)
    G.label_planar(ob, side_rects[1], (-w / 2, d / 2, z0), (0, -1, 0), (0, 0, 1), (d, h), normal=(-1, 0, 0),
                   min_dot=0.8, bounds_pad=0.01)


@prop("cardboard_box_open", category="container", surface="fabric", material_kind="cardboard", mass=0.7,
      tags=["nap", "sit_in", "cardboard"])
def cardboard_box_open():
    card = PN.cardboard("box", "#b38a5e", wet=0.35, scuff=0.6, label=True, label_wear=0.3, dirt=0.5, ground=0.4)
    towel = PN.fabric("towel", "#d98aa0", weave_scale=1600, rough=0.9, fade=0.5, dirt=0.5, role="2s",
                      stripes=("#efe7da", 60.0), wrinkle=0.8)
    W, D, H, T = 0.46, 0.34, 0.26, 0.004
    box = open_box("box", W, D, H, T, card)
    G.wobble(box, 0.006, 4, seed=1, zmin=0.05)
    _box_labels(box, W, D, H)
    parts = [box]
    rng = random.Random(3)
    for (axis, sgn, length, width) in (("y", -1, W, D * 0.5), ("y", 1, W, D * 0.5), ("x", -1, D, W * 0.36),
                                       ("x", 1, D, W * 0.36)):
        flap = G.rbox("flap", (length - 0.004, width, T), bevel=0.0015, mat=card) if axis == "y" else \
            G.rbox("flap", (width, length - 0.004, T), bevel=0.0015, mat=card)
        ang = rng.uniform(100, 128)
        if axis == "y":
            G.place(flap, (0, sgn * width / 2, 0))
            G.place(flap, (0, 0, 0), (sgn * (180 - ang), 0, 0))
            G.place(flap, (0, sgn * D / 2, H))
        else:
            G.place(flap, (sgn * width / 2, 0, 0))
            G.place(flap, (0, 0, 0), (0, -sgn * (180 - ang), 0))
            G.place(flap, (sgn * W / 2, 0, H))
        G.wobble(flap, 0.01, 3.5, seed=rng.randint(0, 99))
        parts.append(flap)
    # an old towel someone left inside (cat comfort)
    tw = G.grid("towel", W - 0.03, D - 0.03, 18, 14, mat=towel,
                fn=lambda x, y: 0.012 + 0.012 * noise.noise(Vector((x * 9, y * 9, 0.3))) + 0.03 * max(0, abs(x) - 0.15))
    G.place(tw, (0, 0, T))
    parts.append(tw)
    cols = [G.col_box("fabric", (W, D, 0.012)),
            G.col_box("fabric", (W, 0.012, H), loc=(0, -D / 2 + 0.006, 0)),
            G.col_box("fabric", (W, 0.012, H), loc=(0, D / 2 - 0.006, 0)),
            G.col_box("fabric", (0.012, D, H), loc=(-W / 2 + 0.006, 0, 0)),
            G.col_box("fabric", (0.012, D, H), loc=(W / 2 - 0.006, 0, 0))]
    marks = [G.marker("NAP_01", (0, 0, 0.02)), G.marker("SIT_01", (0, 0, 0.02))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("cardboard_noodle")}


@prop("cardboard_box_closed", category="container", dynamic=True, surface="fabric", material_kind="cardboard",
      mass=0.9, tags=["knockable", "cardboard"])
def cardboard_box_closed():
    card = PN.cardboard("cbox", "#b08659", wet=0.25, scuff=0.5, label=True, label_wear=0.3, dirt=0.4, ground=0.2)
    tape = PN.plastic("tape", "#c99a5a", rough=0.22, fade=0.1, scratch=0.5, dirt=0.4, textured=0.1)
    W, D, H = 0.34, 0.25, 0.22
    box = G.rbox("box", (W, D, H), bevel=0.004, segs=2, mat=card)
    G.wobble(box, 0.004, 5, seed=4)
    G.dent(box, (W / 2, -D / 2, H), 0.05, 0.012)
    _box_labels(box, W, D, H)
    seam = G.rbox("seam", (W - 0.01, 0.003, 0.002), bevel=0.0, mat=card)
    G.place(seam, (0, 0, H))
    t1 = G.rbox("tape", (W + 0.004, 0.05, 0.0008), bevel=0.0, mat=tape)
    G.place(t1, (0, 0, H + 0.0004))
    parts = [box, seam, t1]
    for s in (-1, 1):
        t2 = G.rbox("tape_end", (0.0008, 0.05, 0.06), bevel=0.0, mat=tape)
        G.place(t2, (s * (W / 2 + 0.0004), 0, H - 0.06))
        parts.append(t2)
    cols = [G.col_box("fabric", (W, D, H))]
    return {"parts": parts, "colliders": cols, "label": L("cardboard_noodle")}


@prop("cardboard_flat_pile", category="container", surface="fabric", material_kind="cardboard", mass=6.0,
      tags=["nap", "standable", "cardboard", "recycling"])
def cardboard_flat_pile():
    rng = random.Random(8)
    card = PN.cardboard("flat", "#b08b62", wet=0.5, scuff=0.7, label=True, label_wear=0.5, dirt=0.6, ground=0.5)
    string = PN.plastic("string", "#d23b2e", rough=0.5, fade=0.5, dirt=0.5)
    parts = []
    z = 0.0
    for i in range(9):
        w, d, t = rng.uniform(0.74, 0.86), rng.uniform(0.52, 0.62), 0.007
        sh = G.rbox("sheet", (w, d, t), bevel=0.002, mat=card)
        G.label_planar(sh, (rng.choice([0.0, 0.5]), 0.0, rng.choice([0.0, 0.5]) + 0.5, 0.62), (-w / 2, -d / 2, 0),
                       (1, 0, 0), (0, 1, 0), (w, d), normal=(0, 0, 1))
        G.place(sh, (rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), z), (0, 0, rng.uniform(-6, 6)))
        G.wobble(sh, 0.006, 2.5, seed=i, axis_mask=(0, 0, 1))
        parts.append(sh)
        z += t + 0.001
    for x in (-0.22, 0.22):
        pts = [(x, -0.33, z + 0.004), (x, 0.33, z + 0.004), (x, 0.33, 0.004), (x, -0.33, 0.004)]
        st = G.tube("string", pts + [pts[0]], 0.002, 5, mat=string, closed=True)
        parts.append(st)
    cols = [G.col_box("fabric", (0.82, 0.6, z))]
    marks = [G.marker("NAP_01", (0, 0, z))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("cardboard_noodle")}


# ---------------------------------------------------------------------------
# Styrofoam box, crates, sack
# ---------------------------------------------------------------------------
@prop("styrofoam_box", category="container", surface="plastic", material_kind="soft", mass=0.6,
      tags=["standable", "market"])
def styrofoam_box():
    foam = PN.styrofoam("foam", "#efefe8", dirt=0.6, dust=0.3, ground=0.5, label=True)
    W, D, H = 0.56, 0.38, 0.27
    body = G.rbox("body", (W, D, H - 0.04), bevel=0.015, segs=3, mat=foam)
    G.wobble(body, 0.003, 6, seed=2)
    G.label_planar(body, (0.0, 0.1, 0.5, 0.9), (-W / 2 + 0.03, -D / 2, 0.03), (1, 0, 0), (0, 0, 1), (W - 0.06, 0.17),
                   normal=(0, -1, 0))
    G.label_planar(body, (0.5, 0.1, 1.0, 0.9), (W / 2, -D / 2 + 0.03, 0.03), (0, 1, 0), (0, 0, 1),
                   (D - 0.06, 0.17), normal=(1, 0, 0))
    lid = G.rbox("lid", (W + 0.01, D + 0.01, 0.045), bevel=0.012, segs=3, mat=foam)
    G.place(lid, (0.012, -0.006, H - 0.045), (0, 0, 2.5))
    lip = G.rbox("lip", (W - 0.05, D - 0.05, 0.02), bevel=0.005, mat=foam)
    G.place(lip, (0.012, -0.006, H - 0.06), (0, 0, 2.5))
    G.dent(lid, (-0.2, 0.1, H), 0.06, 0.008)
    cols = [G.col_box("plastic", (W, D, H))]
    marks = [G.marker("NAP_01", (0, 0, H))]
    return {"parts": [body, lid, lip], "colliders": cols, "markers": marks, "label": L("styrofoam_marker")}


def _plastic_crate(color):
    pm = PN.plastic("crate", color, rough=0.48, fade=0.5, scratch=0.9, dirt=0.75, dust=0.5, ground=0.6,
                    label=True, label_wear=0.6)
    W, D, H = 0.53, 0.36, 0.28
    parts = []
    # bottom grid
    for i in range(7):
        x = -W / 2 + 0.03 + (W - 0.06) * i / 6
        parts.append(G.rbox("bx", (0.012, D - 0.02, 0.014), bevel=0.003, mat=pm, loc=(x, 0, 0)))
    for j in range(5):
        y = -D / 2 + 0.03 + (D - 0.06) * j / 4
        parts.append(G.rbox("by", (W - 0.02, 0.012, 0.012), bevel=0.003, mat=pm, loc=(0, y, 0.001)))
    # corner posts, rims, rails, ribs
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(G.rbox("post", (0.03, 0.03, H), bevel=0.007, mat=pm, loc=(sx * (W / 2 - 0.015), sy * (D / 2 - 0.015), 0)))
    for z, hgt in ((0.0, 0.03), (0.105, 0.012), (0.19, 0.012), (H - 0.028, 0.028)):
        for sy in (-1, 1):
            parts.append(G.rbox("rail", (W, 0.014 if hgt < 0.02 else 0.02, hgt), bevel=0.004, mat=pm,
                                loc=(0, sy * (D / 2 - 0.008), z)))
        for sx in (-1, 1):
            if z >= H - 0.03:
                continue
            parts.append(G.rbox("rail", (0.014 if hgt < 0.02 else 0.02, D, hgt), bevel=0.004, mat=pm,
                                loc=(sx * (W / 2 - 0.008), 0, z)))
    for sx in (-1, 1):
        # short side top: handle band with slot
        top = G.rbox("hband", (0.02, D, 0.022), bevel=0.005, mat=pm, loc=(sx * (W / 2 - 0.01), 0, H - 0.022))
        low = G.rbox("hband2", (0.02, D, 0.03), bevel=0.005, mat=pm, loc=(sx * (W / 2 - 0.01), 0, H - 0.085))
        for sy in (-1, 1):
            parts.append(G.rbox("hend", (0.02, 0.08, 0.06), bevel=0.005, mat=pm,
                                loc=(sx * (W / 2 - 0.01), sy * (D / 2 - 0.04), H - 0.06)))
        G.label_planar(low, (0.0, 0.0, 1.0, 1.0), (sx * W / 2, -sx * (D / 2 - 0.02), H - 0.085), (0, sx, 0), (0, 0, 1),
                       (D - 0.04, 0.03), normal=(sx, 0, 0))
        parts += [top, low]
    for i in range(1, 8):
        x = -W / 2 + W * i / 8
        for sy in (-1, 1):
            parts.append(G.rbox("rib", (0.012, 0.012, H - 0.03), bevel=0.003, mat=pm,
                                loc=(x, sy * (D / 2 - 0.008), 0.02)))
    for j in range(1, 5):
        y = -D / 2 + D * j / 5
        for sx in (-1, 1):
            parts.append(G.rbox("rib", (0.012, 0.012, H - 0.1), bevel=0.003, mat=pm,
                                loc=(sx * (W / 2 - 0.008), y, 0.02)))
    cols = [G.col_box("plastic", (W, D, 0.015)), G.col_box("plastic", (W, 0.02, H), loc=(0, -D / 2 + 0.01, 0)),
            G.col_box("plastic", (W, 0.02, H), loc=(0, D / 2 - 0.01, 0)),
            G.col_box("plastic", (0.02, D, H), loc=(-W / 2 + 0.01, 0, 0)),
            G.col_box("plastic", (0.02, D, H), loc=(W / 2 - 0.01, 0, 0))]
    marks = [G.marker("NAP_01", (0, 0, 0.016))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("crate_emboss")}


register("plastic_crate_blue", lambda: _plastic_crate("#2a63b0"), category="container", surface="plastic", mass=1.6,
         tags=["crate", "sit_in", "standable"])
register("plastic_crate_red", lambda: _plastic_crate("#c4352c"), category="container", surface="plastic", mass=1.6,
         tags=["crate", "sit_in", "standable"], variant_of="plastic_crate_blue")


@prop("wooden_crate", category="container", surface="wood", mass=3.5, tags=["crate", "sit_in", "standable"])
def wooden_crate():
    rng = random.Random(5)
    wd = PN.wood("crate", "#b08a5c", axis="X", rings=55, weather_grey=0.55, rough=0.75, dirt=0.65, ground=0.7,
                 knots=0.6, plank_var=0.18)
    nails = PN.metal("nails", "cast_iron", rust=0.9)
    W, D, H = 0.5, 0.32, 0.3
    parts = []
    for sy in (-1, 1):
        for k in range(3):
            z = 0.02 + k * 0.1
            sl = G.rbox("slat", (W, 0.012, 0.07), bevel=0.002, mat=wd)
            G.place(sl, (rng.uniform(-0.004, 0.004), sy * (D / 2 - 0.006), z), (0, rng.uniform(-0.6, 0.6), 0))
            G.wobble(sl, 0.0015, 8, seed=k + sy)
            parts.append(sl)
            for x in (-W / 2 + 0.018, W / 2 - 0.018):
                for dz in (0.02, 0.05):
                    parts.append(G.cyl("nail", 0.003, 0.002, loc=(x, sy * (D / 2 + 0.0005), z + dz), rot=(90, 0, 0),
                                       segs=6, bevel=0.0, mat=nails))
    wd2 = PN.wood("crate_end", "#a37f55", axis="Y", rings=55, weather_grey=0.5, rough=0.75, dirt=0.65, ground=0.7)
    for sx in (-1, 1):
        for k in range(2):
            pl = G.rbox("end", (0.015, D - 0.024, 0.135), bevel=0.002, mat=wd2)
            G.place(pl, (sx * (W / 2 - 0.0255), 0, 0.015 + k * 0.145))
            parts.append(pl)
        for sy in (-1, 1):
            parts.append(G.rbox("post", (0.035, 0.035, H - 0.01), bevel=0.003, mat=wd2,
                                loc=(sx * (W / 2 - 0.05), sy * (D / 2 - 0.03), 0.0)))
    for k in range(3):
        bs = G.rbox("bottom", (W - 0.04, 0.08, 0.012), bevel=0.002, mat=wd)
        G.place(bs, (0, -D / 2 + 0.06 + k * 0.1, 0.0))
        parts.append(bs)
    cols = [G.col_box("wood", (W, D, 0.015)), G.col_box("wood", (W, 0.015, H), loc=(0, -D / 2 + 0.0075, 0)),
            G.col_box("wood", (W, 0.015, H), loc=(0, D / 2 - 0.0075, 0)),
            G.col_box("wood", (0.03, D, H), loc=(-W / 2 + 0.015, 0, 0)),
            G.col_box("wood", (0.03, D, H), loc=(W / 2 - 0.015, 0, 0))]
    marks = [G.marker("NAP_01", (0, 0, 0.013))]
    return {"parts": parts, "colliders": cols, "markers": marks}


def _pet_bottle(name, h=0.22, r=0.032, col="#cfe3ea"):
    m = PN.glass_opaque(name, col, rough=0.12, dirt=0.4)
    b = G.lathe(name, [(0.0, 0.0), (r * 0.8, 0.0), (r, 0.01), (r, h * 0.55), (r * 0.94, h * 0.6), (r, h * 0.66),
                       (r, h * 0.72), (r * 0.45, h * 0.9), (r * 0.36, h * 0.93), (r * 0.36, h), (0.0, h)], 16, mat=m)
    G.wobble(b, 0.004, 25, seed=int(h * 1000))
    cap = G.cyl(name + "_cap", r * 0.42, 0.016, loc=(0, 0, h), segs=14, mat=PN.plastic(name + "c", "#2a68c2", rough=0.4))
    return [b, cap]


@prop("recycling_sack", category="container", surface="fabric", material_kind="soft", mass=3.0,
      tags=["recycling", "standable"])
def recycling_sack():
    rng = random.Random(6)
    sack = PN.weave("sack", "#e8e6dc", scale=180, dirt=0.75, dust=0.4, rough=0.6, gap=0.12, vary=0.05)
    nb_label = PN.weave("sack_print", "#e8e6dc", scale=180, dirt=0.75, dust=0.4, rough=0.6, gap=0.12, vary=0.05)
    sack_l = PN.NB("sack_l")
    s = sack_l.st(PN._var(sack_l, "#e6e4da", 0.05, 4), 0.62, 0.0, sack_l.mul(sack_l.wave(scale=180, kind="BANDS"), 0.4))
    s = sack_l.label(s, wear=0.5, rough=0.65)
    s = sack_l.weather(s, dirt=0.75, dust=0.4, ground=0.6)
    sack_mat = sack_l.finish(s, bump=0.0008)

    def lump(r, z, a):
        b = 1.0 + 0.09 * noise.noise(Vector((math.cos(a) * 2.5, math.sin(a) * 2.5, z * 5.0)))
        return r * b
    prof = [(0.0, 0.0), (0.2, 0.0), (0.26, 0.04), (0.29, 0.15), (0.3, 0.35), (0.29, 0.55), (0.25, 0.7), (0.17, 0.78),
            (0.1, 0.8), (0.085, 0.84)]
    body = G.lathe("sack", prof, 40, mat=sack_mat, rfunc=lump)
    for v in body.data.vertices:
        v.co.y *= 0.72
    G.wobble(body, 0.02, 3.0, seed=6)
    G.label_planar(body, (0.0, 0.0, 0.5, 1.0), (-0.25, -0.25, 0.08), (1, 0, 0), (0, 0, 1), (0.5, 0.62),
                   normal=(0, -1, 0), min_dot=0.4)
    parts = [body]
    for k in range(5):
        bot = _pet_bottle("pet", rng.uniform(0.18, 0.25), rng.uniform(0.028, 0.034),
                          rng.choice(["#cfe3ea", "#d9ecd8", "#e8e8e4"]))
        for b in bot:
            G.place(b, (0, 0, 0), (rng.uniform(-35, 35), rng.uniform(-35, 35), rng.uniform(0, 360)))
            G.place(b, (rng.uniform(-0.06, 0.06), rng.uniform(-0.04, 0.04), 0.66))
        parts += bot
    neck = G.tube("tie", [(0.09 * math.cos(a), 0.065 * math.sin(a), 0.8) for a in [i * 0.4 for i in range(17)]],
                  0.004, 5, mat=PN.plastic("rope", "#3a6bc4", rough=0.6))
    parts.append(neck)
    cols = [G.col_box("fabric", (0.56, 0.42, 0.78))]
    marks = [G.marker("NAP_01", (0, 0, 0.8))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("feed_sack")}


# ---------------------------------------------------------------------------
# Bucket, basin, brooms
# ---------------------------------------------------------------------------
@prop("bucket_plastic", category="container", dynamic=True, surface="plastic", mass=0.7, material_kind="plastic",
      tags=["knockable", "household"])
def bucket_plastic():
    pm = PN.plastic("bucket", "#2a6fc0", rough=0.38, fade=0.45, scratch=0.8, dirt=0.6, dust=0.4, ground=0.5)
    steel = PN.metal("handle", "galvanized", rust=0.4, dirt=0.5)
    grip = PN.plastic("grip", "#2a6fc0", rough=0.4)
    H, R0, R1, T = 0.27, 0.118, 0.15, 0.003
    body = G.lathe("bucket", [(0.0, 0.004), (R0 - 0.01, 0.0), (R0, 0.006), (R1, H - 0.02), (R1 + 0.008, H - 0.012),
                              (R1 + 0.009, H), (R1 + 0.002, H + 0.004), (R1 - T, H - 0.006), (R0 - T, 0.012),
                              (0.0, 0.012)], 40, mat=pm)
    G.dent(body, (R1 * 0.7, -R1 * 0.7, H * 0.7), 0.05, 0.006)
    parts = [body]
    for s in (-1, 1):
        ear = G.rbox("ear", (0.03, 0.03, 0.04), bevel=0.008, mat=pm, loc=(s * (R1 + 0.006), 0, H - 0.05))
        parts.append(ear)
    gp = G.cyl("grip", 0.011, 0.09, segs=12, mat=grip)
    G.place(gp, (0, 0, -0.045))
    G.place(gp, (0, 0, 0), (0, 90, 0))
    G.place(gp, (0, 0.13, H))
    hnd_obj = G.tube("handle", [(-(R1 + 0.012), 0, H - 0.03), (-(R1 + 0.02), 0.06, H - 0.01),
                                (-0.05, 0.13, H + 0.0), (0.05, 0.13, H + 0.0), ((R1 + 0.02), 0.06, H - 0.01),
                                ((R1 + 0.012), 0, H - 0.03)], 0.0025, 6, mat=steel)
    parts += [hnd_obj, gp]
    cols = [G.col_cyl("plastic", R1, H, segs=12, r2=R1)]
    return {"parts": parts, "colliders": cols}


@prop("basin_plastic", category="container", surface="plastic", mass=0.8, tags=["household"])
def basin_plastic():
    pm = PN.plastic("basin", "#d8364c", rough=0.36, fade=0.5, scratch=0.9, dirt=0.6, dust=0.3, ground=0.4)
    H, R0, R1, T = 0.15, 0.2, 0.28, 0.003
    body = G.lathe("basin", [(0.0, 0.006), (R0 - 0.02, 0.0), (R0, 0.008), (R1, H - 0.01), (R1 + 0.025, H - 0.006),
                             (R1 + 0.028, H), (R1 + 0.02, H + 0.004), (R1 - T, H - 0.004), (R0 - T, 0.012), (0.0, 0.012)],
                   56, mat=pm)
    ribs = []
    for i in range(16):
        a = 2 * math.pi * i / 16
        r = G.rbox("rib", (0.006, 0.02, 0.008), bevel=0.002, mat=pm)
        G.place(r, (0, 0, 0), (0, 0, math.degrees(a)))
        G.place(r, (math.cos(a) * (R1 + 0.014), math.sin(a) * (R1 + 0.014), H - 0.014))
        ribs.append(r)
    cols = [G.col_cyl("plastic", R1, H, segs=14, r2=R1)]
    return {"parts": [body] + ribs, "colliders": cols}


@prop("broom_soft", category="home", dynamic=True, surface="wood", material_kind="wood", mass=0.35,
      tags=["knockable", "lean"])
def broom_soft():
    rng = random.Random(2)
    bam = PN.bamboo("handle", "#c8a86a", axis="Z", node_spacing=0.3, dirt=0.5)
    straw = PN.organic("straw", [(0.0, "#8b7343"), (0.4, "#b49a62"), (0.8, "#cdb47c"), (1.0, "#9a8150")], scale=25,
                       rough=0.75, role="2s", h_amp=0.6)
    strap = PN.plastic("strap", "#c22d2d", rough=0.4, fade=0.4, dirt=0.4)
    parts = [G.cyl("handle", 0.012, 0.82, loc=(0, 0, 0.3), segs=12, bevel=0.002, mat=bam)]
    for k in range(70):
        t = (k + rng.uniform(-0.3, 0.3)) / 69
        xb = (t - 0.5) * 0.07
        xt = (t - 0.5) * 0.34 + rng.uniform(-0.01, 0.01)
        yb, yt = rng.uniform(-0.012, 0.012), rng.uniform(-0.025, 0.025)
        L_ = rng.uniform(0.28, 0.34)
        w = 0.006
        bm = bmesh.new()
        n = 6
        vs = []
        for i in range(n + 1):
            u = i / n
            x = xb + (xt - xb) * u
            y = yb + (yt - yb) * u + 0.01 * math.sin(u * 3 + k)
            z = 0.36 - L_ * u
            vs.append((bm.verts.new((x - w / 2, y, max(0.002, z))), bm.verts.new((x + w / 2, y, max(0.002, z)))))
        for i in range(n):
            bm.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0]))
        parts.append(G.obj_from_bm("straw", bm, straw))
    bundle = G.lathe("bundle", [(0.0, 0.3), (0.04, 0.3), (0.045, 0.36), (0.03, 0.42), (0.014, 0.44), (0.0, 0.44)], 20,
                     mat=straw)
    for v in bundle.data.vertices:
        v.co.y *= 0.45
    parts.append(bundle)
    for z in (0.33, 0.38, 0.41):
        ring = G.tube("strap", [(0.046 * math.cos(a), 0.022 * math.sin(a), z) for a in
                                [i * 2 * math.pi / 24 for i in range(25)]], 0.003, 5, mat=strap)
        parts.append(ring)
    loop = G.tube("hangloop", [(0, 0, 1.12), (0.015, 0, 1.15), (0, 0, 1.17), (-0.015, 0, 1.15), (0, 0, 1.12)],
                  0.0015, 4, mat=strap)
    parts.append(loop)
    cols = [G.col_box("wood", (0.34, 0.06, 0.36)), G.col_cyl("wood", 0.014, 0.82, loc=(0, 0, 0.36))]
    return {"parts": parts, "colliders": cols}


@prop("broom_bamboo", category="home", dynamic=True, surface="wood", material_kind="wood", mass=0.9,
      tags=["knockable", "lean", "street_sweeper"])
def broom_bamboo():
    rng = random.Random(9)
    bam = PN.bamboo("bhandle", "#b9995a", axis="Z", node_spacing=0.32, dirt=0.6, aged=0.6)
    twig = PN.bamboo("twigs", "#a48a55", axis="Z", node_spacing=0.12, dirt=0.6, aged=0.8, rough=0.6)
    wire = PN.metal("bwire", "galvanized", rust=0.7)
    parts = [G.cyl("handle", 0.016, 1.25, loc=(0, 0, 0.45), segs=12, bevel=0.002, mat=bam)]
    for k in range(70):
        a = rng.uniform(0, 2 * math.pi)
        rb = rng.uniform(0, 0.035)
        xb, yb = math.cos(a) * rb, math.sin(a) * rb * 0.6
        xt = (rng.random() - 0.5) * 0.55
        yt = (rng.random() - 0.5) * 0.12
        pts = []
        for i in range(7):
            u = i / 6
            pts.append((xb + (xt - xb) * u ** 1.3, yb + (yt - yb) * u + 0.01 * math.sin(u * 4 + k),
                        0.55 - 0.548 * u))
        t = G.tube("twig", pts, rng.uniform(0.0018, 0.003), 4, mat=twig, rfunc=lambda s: 1.0 - 0.6 * s)
        G.uv_weight(t, 0.4)
        parts.append(t)
    for z in (0.47, 0.53):
        parts.append(G.tube("wire", helix(0.042, z - 0.01, z + 0.01, 3), 0.0016, 4, mat=wire))
    cols = [G.col_box("wood", (0.5, 0.1, 0.5)), G.col_cyl("wood", 0.018, 1.25, loc=(0, 0, 0.5))]
    return {"parts": parts, "colliders": cols}


def helix(r, z0, z1, turns, n=48):
    return [(math.cos(t * turns * 2 * math.pi) * r, math.sin(t * turns * 2 * math.pi) * r * 0.7, z0 + (z1 - z0) * t)
            for t in [k / n for k in range(n + 1)]]


# ---------------------------------------------------------------------------
# Potted plants
# ---------------------------------------------------------------------------
def _pot(kind, r_top, r_bot, h, mat, rim=0.012):
    if kind == "round":
        return G.lathe("pot", [(0.0, 0.0), (r_bot - 0.01, 0.0), (r_bot, 0.008), (r_top - 0.004, h - rim),
                               (r_top + 0.006, h - rim), (r_top + 0.008, h - rim * 0.5), (r_top + 0.006, h),
                               (r_top - 0.008, h), (r_top - 0.012, h - 0.02), (0.0, h - 0.025)], 40, mat=mat)
    raise ValueError(kind)


def _soil(r, z, mat, rng, pebbles=None):
    s = G.lathe("soil", [(0.0, z + 0.006), (r * 0.6, z + 0.004), (r, z)], 28, mat=mat,
                rfunc=lambda rr, zz, a: rr * (1 + 0.02 * math.sin(a * 5)))
    G.wobble(s, 0.004, 30, seed=rng.randint(0, 99))
    return s


def leaf_shape(length, width, n=8, tip=0.15):
    """Outline of a lanceolate leaf along +X (base at x=0)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * min(1.0, t * (1 + tip))) ** 0.8 * (1 - t * 0.2)
        pts.append((t * length, w / 2))
    for i in range(n - 1, 0, -1):
        t = i / n
        w = width * math.sin(math.pi * min(1.0, t * (1 + tip))) ** 0.8 * (1 - t * 0.2)
        pts.append((t * length, -w / 2))
    return pts


def leaf_mesh(name, length, width, mat, bend=0.3, fold=0.2, n=8):
    """Single-sided leaf strip along +X with a midrib fold and a downward arch."""
    bm = bmesh.new()
    rows = []
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * min(1.0, t * 1.12)) ** 0.75 * (1 - 0.15 * t) + 1e-4
        x = t * length
        z = -bend * length * t * t
        row = []
        for j, s in enumerate((-1.0, 0.0, 1.0)):
            row.append(bm.verts.new((x, s * w / 2, z + (0.0 if s == 0 else fold * w * 0.5))))
        rows.append(row)
    for i in range(n):
        for j in range(2):
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    ob = G.obj_from_bm(name, bm, mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


@prop("pot_snake_plant", category="plant", surface="tile", material_kind="ceramic", mass=6.0,
      tags=["plant", "doorway"])
def pot_snake_plant():
    rng = random.Random(21)
    pot_m = PN.ceramic("spot", "#2f5f73", rough=0.14, crackle=0.2, chip=0.35, dirt=0.5, dust=0.3, unglazed_h=0.01)
    soil_m = PN.soil("ssoil", "#3a2a1e", pebbles=0.5, moss=0.2)
    leaf_m = PN.NB("sansevieria")
    nb = leaf_m
    band = nb.wave(nb.coords((1, 1, 1)), scale=28, dist=12, detail=4, kind="BANDS", axis="Z")
    base = nb.mixc(nb.smooth(band, 0.45, 0.75), "#2e4a26", "#5f7d47")
    # golden edge (Laurentii): faces near the leaf margin = baked convex edge mask
    c = nb.mixc(nb.smooth(nb.edge, 0.15, 0.5), base, "#c8b84a")
    c = nb.mixc(nb.mul(nb.smooth(nb.noise(scale=30, detail=6), 0.72, 0.8), 0.6), c, "#6b5a32")
    s = nb.weather(nb.st(c, nb.madd(nb.noise(scale=20), 0.12, 0.38), 0.0, nb.mul(band, 0.3)), dirt=0.2, dust=0.35)
    leaf_mat = nb.finish(s, bump=0.0004)
    H = 0.24
    pot = _pot("round", 0.14, 0.105, H, pot_m)
    parts = [pot, _soil(0.135, H - 0.025, soil_m, rng)]
    for k in range(10):
        Lh = rng.uniform(0.38, 0.68)
        Wd = rng.uniform(0.045, 0.07)
        bm = bmesh.new()
        n = 10
        rows = []
        for i in range(n + 1):
            t = i / n
            w = Wd * (math.sin(math.pi * min(1.0, 0.25 + t * 0.9)) ** 0.6) * (1 - t ** 3) + 0.002
            z = t * Lh
            twist = t * rng.uniform(-0.6, 0.6)
            ring = []
            for (u, th) in ((-1, 0.0), (0, 0.006), (1, 0.0), (0, -0.006)):
                x = u * w / 2
                y = th + abs(u) * -0.006
                ring.append(bm.verts.new((x * math.cos(twist) - y * math.sin(twist),
                                          x * math.sin(twist) + y * math.cos(twist), z)))
            rows.append(ring)
        for i in range(n):
            for j in range(4):
                bm.faces.new((rows[i][j], rows[i][(j + 1) % 4], rows[i + 1][(j + 1) % 4], rows[i + 1][j]))
        bm.faces.new(rows[0][::-1])
        bm.faces.new(rows[-1])
        lf = G.obj_from_bm("leaf", bm, leaf_mat)
        for p in lf.data.polygons:
            p.use_smooth = True
        lean = rng.uniform(4, 18)
        a = rng.uniform(0, 360)
        G.bend_z(lf, lambda z, l=lean: (math.sin(math.radians(l)) * z * z / Lh * 0.6, 0.0))
        G.place(lf, (0, 0, 0), (0, 0, a))
        r0 = rng.uniform(0.0, 0.05)
        G.place(lf, (math.cos(math.radians(a)) * r0, math.sin(math.radians(a)) * r0, H - 0.03))
        parts.append(lf)
    cols = [G.col_cyl("tile", 0.145, H, segs=12, r2=0.145)]
    return {"parts": parts, "colliders": cols}


@prop("pot_chili", category="plant", surface="plastic", material_kind="plastic", mass=2.5, tags=["plant"])
def pot_chili():
    rng = random.Random(22)
    pot_m = PN.plastic("cpot", "#1c1c1c", rough=0.55, fade=0.6, scratch=0.6, dirt=0.7, dust=0.5)
    soil_m = PN.soil("csoil", "#3b2b1f", pebbles=0.3)
    stem_m = PN.organic("stem", [(0.0, "#3d5a2a"), (1.0, "#5d7a3a")], scale=20, rough=0.6)
    leaf_m = PN.leaf("cleaf", "#3e6b2c", vein="#6f9a4c", rough=0.4)
    red_m = PN.organic("chili", [(0.0, "#a8140f"), (0.6, "#d52a1a"), (1.0, "#e84a22")], scale=12, rough=0.18,
                       h_amp=0.2)
    grn_m = PN.organic("chili_g", [(0.0, "#3f7a22"), (1.0, "#5d9a30")], scale=12, rough=0.2, h_amp=0.2)
    H = 0.16
    pot = G.lathe("pot", [(0.0, 0.0), (0.075, 0.0), (0.08, 0.01), (0.105, H - 0.01), (0.112, H - 0.008),
                          (0.112, H), (0.1, H), (0.098, H - 0.02), (0.0, H - 0.025)], 24, mat=pot_m)
    for i in range(24):
        a = 2 * math.pi * i / 24
    parts = [pot, _soil(0.1, H - 0.025, soil_m, rng)]
    tips = []

    def branch(p0, d, length, depth):
        p1 = Vector(p0) + Vector(d).normalized() * length
        mid = (Vector(p0) + p1) / 2 + Vector((rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), 0.01))
        parts.append(G.tube("stem", [p0, mid, p1], 0.004 * (1.0 if depth == 0 else 0.6 ** depth), 5, mat=stem_m))
        if depth < 3:
            for _ in range(2 if depth > 0 else 3):
                nd = Vector(d).normalized() + Vector((rng.uniform(-0.8, 0.8), rng.uniform(-0.8, 0.8), rng.uniform(0.1, 0.5)))
                branch(tuple(p1), tuple(nd), length * rng.uniform(0.55, 0.8), depth + 1)
        else:
            tips.append(p1)
    branch((0, 0, H - 0.03), (0, 0, 1), 0.12, 0)
    for tpt in tips:
        for _ in range(3):
            lf = leaf_mesh("leaf", rng.uniform(0.04, 0.065), rng.uniform(0.018, 0.026), leaf_m, bend=0.25)
            G.place(lf, (0, 0, 0), (rng.uniform(-30, 10), rng.uniform(-40, 10), rng.uniform(0, 360)))
            G.place(lf, tpt + Vector((rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), rng.uniform(-0.02, 0.0))))
            parts.append(lf)
    for k in range(16):
        tpt = rng.choice(tips) + Vector((rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), rng.uniform(-0.05, -0.01)))
        Lc = rng.uniform(0.035, 0.055)
        ch = G.lathe("chili", [(0.0, 0.0), (0.004, 0.003), (0.0055, 0.012), (0.005, Lc * 0.6), (0.003, Lc * 0.9),
                               (0.0, Lc)], 10, mat=red_m if rng.random() < 0.65 else grn_m)
        G.bend_z(ch, lambda z: (0.25 * z * z / Lc, 0.0))
        G.place(ch, (0, 0, 0), (rng.uniform(150, 200), rng.uniform(-20, 20), rng.uniform(0, 360)))
        G.place(ch, tpt)
        parts.append(ch)
    cols = [G.col_cyl("plastic", 0.11, H, segs=12)]
    return {"parts": parts, "colliders": cols}


@prop("pot_bonsai", category="plant", surface="tile", material_kind="ceramic", mass=9.0, tags=["plant", "altar"])
def pot_bonsai():
    rng = random.Random(23)
    pot_m = PN.ceramic("bpot", "#6b3a26", rough=0.25, crackle=0.1, chip=0.3, dirt=0.4, unglazed_h=0.0)
    bark = PN.organic("bark", [(0.0, "#3a2c22"), (0.5, "#5a4636"), (1.0, "#7b6553")], scale=60, rough=0.85,
                      h_amp=1.0, detail_scale=200, bump=0.0012)
    leaf_m = PN.leaf("bleaf", "#2f5a24", vein="#4f7a3a", rough=0.35, spots=0.1)
    moss_m = PN.soil("moss", "#3c4f22", pebbles=0.2, moss=0.9)
    W, D, H = 0.42, 0.28, 0.09
    pot = G.rbox("pot", (W, D, H), bevel=0.012, segs=3, mat=pot_m)
    G.place(pot, (0, 0, 0.018))
    lip = G.rbox("lip", (W + 0.02, D + 0.02, 0.014), bevel=0.005, mat=pot_m)
    G.place(lip, (0, 0, H + 0.006))
    parts = [pot, lip]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(G.rbox("foot", (0.04, 0.03, 0.02), bevel=0.004, mat=pot_m, loc=(sx * 0.16, sy * 0.1, 0)))
    soil = G.grid("moss", W - 0.03, D - 0.03, 12, 8, mat=moss_m,
                  fn=lambda x, y: 0.01 * noise.noise(Vector((x * 12, y * 12, 0))) + 0.012 * (1 - (x * x / 0.04 + y * y / 0.02)))
    G.place(soil, (0, 0, H + 0.01))
    parts.append(soil)
    trunk = [(0.04, 0.0, H + 0.01), (0.05, 0.01, H + 0.08), (0.0, 0.0, H + 0.15), (-0.06, -0.01, H + 0.2),
             (-0.04, 0.0, H + 0.27), (0.02, 0.01, H + 0.31)]
    parts.append(G.tube("trunk", trunk, 0.03, 12, mat=bark, rfunc=lambda t: 1.0 - 0.65 * t))
    roots = [G.tube("root", [(0.04, 0.0, H + 0.02), (0.04 + dx, dy, H + 0.012)], 0.012, 6, mat=bark,
                    rfunc=lambda t: 1 - 0.7 * t) for (dx, dy) in ((0.08, 0.02), (-0.06, 0.05), (0.02, -0.07))]
    parts += roots
    pads = [((-0.13, 0.0, H + 0.24), 0.07), ((0.12, 0.02, H + 0.2), 0.065), ((0.0, 0.0, H + 0.36), 0.08),
            ((-0.08, 0.03, H + 0.33), 0.05), ((0.1, -0.03, H + 0.31), 0.05)]
    for (c, r) in pads:
        src = Vector(trunk[min(len(trunk) - 1, int((c[2] - H) / 0.07))])
        parts.append(G.tube("branch", [src, (src + Vector(c)) / 2 + Vector((0, 0, 0.02)), Vector(c)], 0.009, 6,
                            mat=bark, rfunc=lambda t: 1 - 0.6 * t))
        for k in range(55):
            u, v = rng.uniform(0, 2 * math.pi), rng.uniform(0.0, 1.0)
            p = Vector(c) + Vector((math.cos(u) * r * v ** 0.5, math.sin(u) * r * 0.75 * v ** 0.5,
                                    (1 - v) * r * 0.35 + rng.uniform(-0.01, 0.01)))
            lf = leaf_mesh("leaf", rng.uniform(0.018, 0.026), rng.uniform(0.009, 0.013), leaf_m, bend=0.15)
            G.place(lf, (0, 0, 0), (rng.uniform(-25, 25), rng.uniform(-35, 5), rng.uniform(0, 360)))
            G.place(lf, p)
            parts.append(lf)
    for k in range(5):
        parts.append(G.sphere("pebble", rng.uniform(0.006, 0.012), loc=(rng.uniform(-0.15, 0.15),
                                                                         rng.uniform(-0.09, 0.09), H + 0.014),
                              segs=8, rings=5, mat=PN.concrete("peb", "#c8c2b4", moss=0.0, dirt=0.2),
                              scale=(1, 0.8, 0.6)))
    cols = [G.col_box("tile", (W + 0.02, D + 0.02, H + 0.02))]
    return {"parts": parts, "colliders": cols}


@prop("pot_aloe", category="plant", surface="tile", material_kind="ceramic", mass=4.0, tags=["plant", "doorway"])
def pot_aloe():
    rng = random.Random(24)
    pot_m = PN.terracotta("apot", "#a65a3c", salt=0.5, moss=0.4)
    soil_m = PN.soil("asoil", "#3a2b1f", pebbles=0.6)
    aloe = PN.NB("aloe")
    nb = aloe
    sp = nb.smooth(nb.voronoi(scale=80, feature="F1"), 0.12, 0.04)
    c = nb.mixc(nb.mul(sp, 0.55), PN._var(nb, "#5d8256", 0.08, 6), "#b9c9a0")
    c = nb.mixc(nb.smooth(nb.edge, 0.2, 0.7), c, "#9a7a52")
    s = nb.weather(nb.st(c, 0.42, 0.0, nb.mul(sp, 0.4)), dirt=0.2, dust=0.4)
    aloe_m = nb.finish(s, bump=0.0004)
    H = 0.19
    pot = _pot("round", 0.13, 0.095, H, pot_m)
    parts = [pot, _soil(0.125, H - 0.025, soil_m, rng)]
    for k in range(15):
        ring = k // 5
        Lh = rng.uniform(0.22, 0.32) * (1.0 - 0.15 * ring)
        Wd = rng.uniform(0.04, 0.055)
        bm = bmesh.new()
        n = 9
        rows = []
        for i in range(n + 1):
            t = i / n
            w = Wd * (1 - t) ** 0.9 + 0.001
            th = 0.012 * (1 - t) + 0.001
            rows.append([bm.verts.new((t * Lh, -w / 2, 0.0)), bm.verts.new((t * Lh, 0.0, -th)),
                         bm.verts.new((t * Lh, w / 2, 0.0)), bm.verts.new((t * Lh, 0.0, th * 0.3))])
        for i in range(n):
            for j in range(4):
                bm.faces.new((rows[i][j], rows[i][(j + 1) % 4], rows[i + 1][(j + 1) % 4], rows[i + 1][j]))
        bm.faces.new(rows[0][::-1])
        lf = G.obj_from_bm("aloe", bm, aloe_m)
        for p in lf.data.polygons:
            p.use_smooth = True
        up = rng.uniform(40, 70) - ring * 12
        # arch: leaf rises then droops at the tip
        for v in lf.data.vertices:
            t = v.co.x / Lh
            ang = math.radians(up) * (1 - 0.8 * t)
            r = v.co.x
            v.co.x, v.co.z = r * math.cos(ang) * 0.9 + 0.0, r * math.sin(ang) + v.co.z
        G.place(lf, (0, 0, 0), (0, 0, k * 137.5 + rng.uniform(-8, 8)))
        G.place(lf, (0, 0, H - 0.02))
        parts.append(lf)
    cols = [G.col_cyl("tile", 0.135, H, segs=12)]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Bird cage & wind chime (hanging; origin = hang point)
# ---------------------------------------------------------------------------
@prop("bird_cage", category="home", surface="wood", mass=1.2, grounded=False, tags=["hanging", "balcony"])
def bird_cage():
    bam = PN.bamboo("cage", "#c49a5a", axis="Z", node_spacing=0.5, dirt=0.5, aged=0.4, rough=0.4)
    tray_m = PN.wood("tray", "#6b4226", axis="X", varnish=0.7, dirt=0.5, weather_grey=0.1)
    brass = PN.metal("cbrass", "brass", wear=0.5)
    cup_m = PN.ceramic("cup", "#f0ece0", pattern=True, rough=0.1, chip=0.2)
    R, Hc = 0.15, 0.36
    top = -0.08
    parts = []
    hook = G.tube("hook", [(0, 0, 0), (0.02, 0, -0.015), (0.02, 0, -0.035), (0, 0, -0.05), (0, 0, top + 0.02)], 0.003,
                  6, mat=brass)
    knob = G.sphere("knob", 0.016, loc=(0, 0, top + 0.005), mat=brass, segs=12, rings=8)
    parts += [hook, knob]
    zb = top - 0.06 - Hc
    nbars = 40
    for i in range(nbars):
        a = 2 * math.pi * i / nbars
        pts = []
        for k in range(9):
            t = k / 8
            if t < 0.25:  # dome
                u = t / 0.25
                rr = R * math.sin(u * math.pi / 2)
                z = top - 0.06 * (1 - math.cos(u * math.pi / 2))
            else:
                rr = R
                z = top - 0.06 - Hc * (t - 0.25) / 0.75
            pts.append((math.cos(a) * rr, math.sin(a) * rr, z))
        b = G.tube("bar", pts, 0.0016, 4, mat=bam, cap=False)
        G.uv_weight(b, 0.35)
        parts.append(b)
    for z in (top - 0.06, top - 0.06 - Hc * 0.55, zb + 0.05):
        parts.append(G.tube("ring", [(math.cos(a) * (R + 0.002), math.sin(a) * (R + 0.002), z) for a in
                                     [k * 2 * math.pi / 48 for k in range(49)]], 0.004, 6, mat=bam))
    tray = G.lathe("tray", [(0.0, zb - 0.02), (R + 0.02, zb - 0.02), (R + 0.025, zb), (R + 0.02, zb + 0.05),
                            (R - 0.005, zb + 0.05), (0.0, zb + 0.045)], 40, mat=tray_m)
    perch = G.cyl("perch", 0.005, 2 * R - 0.01, segs=8, mat=bam)
    G.place(perch, (0, 0, -(R - 0.005)))
    G.place(perch, (0, 0, 0), (0, 90, 0))
    G.place(perch, (0, 0, zb + 0.14))
    parts += [tray, perch]
    for s in (-1, 1):
        cup = G.lathe("cup", [(0.0, 0.0), (0.018, 0.0), (0.022, 0.025), (0.019, 0.025), (0.015, 0.004), (0.0, 0.004)],
                      16, mat=cup_m)
        G.place(cup, (s * (R - 0.03), -0.04, zb + 0.08))
        parts.append(cup)
    cols = [G.col_cyl("wood", R + 0.02, Hc + 0.12, loc=(0, 0, zb - 0.02), segs=12)]
    marks = [G.marker("HANG_01", (0, 0, 0))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("ceramic_patterns"),
            "meta": {"origin": "hang_point"}}


@prop("wind_chime", category="home", surface="metal", mass=0.4, grounded=False, tags=["hanging", "balcony", "sound"])
def wind_chime():
    rng = random.Random(30)
    wd = PN.wood("chime_top", "#7a5432", axis="X", varnish=0.5, dirt=0.4)
    alu = PN.metal("chime", "aluminium", wear=0.3, dirt=0.3, tint="#c9c6bf")
    cord = PN.fabric("cord", "#3a2a22", weave_scale=3000, rough=0.9, role="base")
    parts = []
    disc = G.cyl("disc", 0.065, 0.014, loc=(0, 0, -0.1), segs=24, bevel=0.003, mat=wd)
    parts.append(disc)
    for a in (0, 120, 240):
        ar = math.radians(a)
        parts.append(G.tube("cord", [(0, 0, 0), (math.cos(ar) * 0.05, math.sin(ar) * 0.05, -0.088)], 0.0012, 4,
                            mat=cord))
    ring = G.tube("ring", [(0.005 * math.cos(t), 0, 0.008 + 0.008 * math.sin(t)) for t in
                           [k * 2 * math.pi / 12 for k in range(13)]], 0.0015, 4, mat=alu)
    parts.append(ring)
    n = 6
    for i in range(n):
        a = 2 * math.pi * i / n
        L_ = 0.14 + 0.03 * i
        x, y = math.cos(a) * 0.05, math.sin(a) * 0.05
        parts.append(G.tube("cord", [(x, y, -0.114), (x, y, -0.15)], 0.0008, 4, mat=cord))
        tube = G.lathe("tube", [(0.0055, 0.0), (0.0055, L_), (0.004, L_), (0.004, 0.0)], 14, mat=alu)
        G.place(tube, (x, y, -0.15 - L_))
        parts.append(tube)
    parts.append(G.tube("cord", [(0, 0, -0.114), (0, 0, -0.33)], 0.0008, 4, mat=cord))
    clap = G.cyl("clapper", 0.025, 0.008, loc=(0, 0, -0.22), segs=20, bevel=0.002, mat=wd)
    sail = G.extrude("sail", [(0.0, 0.0), (0.03, -0.03), (0.035, -0.09), (0.0, -0.12), (-0.035, -0.09),
                              (-0.03, -0.03)], 0.004, mat=wd, bevel=0.001)
    G.place(sail, (0, 0, 0), (90, 0, 0))
    G.place(sail, (0, 0, -0.33))
    parts += [clap, sail]
    marks = [G.marker("HANG_01", (0, 0, 0))]
    return {"parts": parts, "markers": marks, "meta": {"origin": "hang_point"}}


# ---------------------------------------------------------------------------
# Floor altar (Thổ Địa / Thần Tài) with incense bowl, cups, fruit and electric candles
# ---------------------------------------------------------------------------
@prop("altar_box", category="home", surface="wood", mass=12.0, tags=["altar", "shop", "light"], night_emission=2.0)
def altar_box():
    rng = random.Random(31)
    lac = PN.NB("altar_lacquer")
    nb = lac
    c = PN._var(nb, "#9e1c1a", 0.06, 3)
    c = nb.mixc(nb.mul(nb.edge_wear(0.35, 30), 0.8), c, "#4a2a1a")
    s = nb.st(c, nb.madd(nb.noise(scale=8), 0.1, 0.32), 0.0, nb.mul(nb.noise(scale=300), 0.15))
    s = nb.label(s, wear=0.15, rough=0.3, metal=0.6)
    s = nb.weather(s, dirt=0.5, dust=0.6)
    lacq = nb.finish(s, bump=0.0003)
    gold = PN.metal("agold", "gold", wear=0.6, dirt=0.5)
    bowl_m = PN.ceramic("incense_bowl", "#e8e2d2", pattern=True, rough=0.1)
    sand = PN.organic("ash", [(0.0, "#8d8478"), (1.0, "#c9c1b2")], scale=60, rough=0.95)
    stick = PN.organic("incense", [(0.0, "#7a2a20"), (0.7, "#a0402a"), (1.0, "#3a2a20")], scale=40, rough=0.8)
    orange = PN.organic("orange", [(0.0, "#d86a12"), (0.6, "#ef8a1e"), (1.0, "#c05a10")], scale=30, rough=0.4,
                        spec_spots=(400, 0.05, "#c06010"))
    banana = PN.organic("banana", [(0.0, "#c9a828"), (0.7, "#e4c84a"), (1.0, "#6d5a1e")], scale=10, rough=0.45)
    candle_glow = PN.emissive_plain("candle", "#ff4a32", role="lit", rough=0.2)
    W, D = 0.5, 0.36
    parts = []
    base = G.rbox("base", (W, D, 0.07), bevel=0.006, mat=lacq)
    G.label_planar(base, (0.0, 0.0, 1.0, 0.5), (-W / 2, -D / 2, 0.0), (1, 0, 0), (0, 0, 1), (W, 0.07), normal=(0, -1, 0))
    back = G.rbox("back", (W, 0.025, 0.5), bevel=0.004, mat=lacq, loc=(0, D / 2 - 0.0125, 0.07))
    G.label_planar(back, (0.15, 0.5, 0.85, 1.0), (-0.17, D / 2 - 0.026, 0.12), (1, 0, 0), (0, 0, 1), (0.34, 0.4),
                   normal=(0, -1, 0))
    parts += [base, back]
    for sx in (-1, 1):
        side = G.rbox("side", (0.025, D - 0.025, 0.5), bevel=0.004, mat=lacq, loc=(sx * (W / 2 - 0.0125), -0.0125, 0.07))
        col = G.rbox("pillar", (0.04, 0.04, 0.5), bevel=0.006, mat=lacq, loc=(sx * (W / 2 - 0.02), -D / 2 + 0.02, 0.07))
        G.label_planar(col, ((0.0, 0.5, 0.14, 1.0) if sx < 0 else (0.86, 0.5, 1.0, 1.0)),
                       (sx * (W / 2 - 0.02) - 0.02, -D / 2, 0.1), (1, 0, 0), (0, 0, 1), (0.04, 0.44), normal=(0, -1, 0))
        parts += [side, col]
    # pagoda roof with up-turned corners
    bm = bmesh.new()
    rw, rd, rz = W / 2 + 0.06, D / 2 + 0.06, 0.57
    corners = [(-rw, -rd), (rw, -rd), (rw, rd), (-rw, rd)]
    vb = [bm.verts.new((x, y, rz + 0.03)) for (x, y) in corners]
    vt = [bm.verts.new((x * 0.25, y * 0.4, rz + 0.13)) for (x, y) in corners]
    vb2 = [bm.verts.new((x, y, rz)) for (x, y) in corners]
    for i in range(4):
        bm.faces.new((vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]))
        bm.faces.new((vb2[i], vb2[(i + 1) % 4], vb[(i + 1) % 4], vb[i]))
    bm.faces.new(vt)
    bm.faces.new(vb2[::-1])
    for v in vb + vb2:
        v.co.z += 0.03
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    roof = G.obj_from_bm("roof", bm, lacq)
    G.bevel_sharp(roof, 0.004, 2, 30)
    ridge = G.rbox("ridge", (W * 0.5 + 0.02, 0.03, 0.03), bevel=0.008, mat=gold, loc=(0, 0, rz + 0.13))
    pearl = G.sphere("pearl", 0.022, loc=(0, 0, rz + 0.18), mat=gold, segs=12, rings=8)
    parts += [roof, ridge, pearl]
    # offerings
    bowl = G.lathe("bowl", [(0.0, 0.0), (0.035, 0.0), (0.05, 0.03), (0.06, 0.07), (0.055, 0.07), (0.0, 0.06)], 24,
                   mat=bowl_m)
    G.place(bowl, (0, 0.03, 0.07))
    ash = G.cyl("ash", 0.052, 0.002, loc=(0, 0.03, 0.128), segs=20, bevel=0.0, mat=sand)
    parts += [bowl, ash]
    for k in range(5):
        a = rng.uniform(-0.3, 0.3)
        st = G.cyl("stick", 0.0015, rng.uniform(0.12, 0.2), loc=(0, 0, 0), segs=5, bevel=0.0, mat=stick)
        G.place(st, (0, 0, 0), (rng.uniform(-8, 8), rng.uniform(-8, 8), 0))
        G.place(st, (rng.uniform(-0.03, 0.03), 0.03 + rng.uniform(-0.02, 0.02), 0.128))
        parts.append(st)
    for sx in (-1, 1):
        cup = G.lathe("cup", [(0.0, 0.0), (0.012, 0.0), (0.018, 0.025), (0.016, 0.025), (0.0, 0.005)], 14, mat=bowl_m)
        G.place(cup, (sx * 0.09, 0.07, 0.07))
        cnd = G.lathe("candle", [(0.0, 0.0), (0.018, 0.0), (0.018, 0.012), (0.012, 0.016), (0.012, 0.09),
                                 (0.0, 0.09)], 14, mat=gold)
        G.place(cnd, (sx * 0.19, 0.08, 0.07))
        flame = G.lathe("flame", [(0.0, 0.0), (0.008, 0.008), (0.006, 0.022), (0.0, 0.034)], 12, mat=candle_glow)
        G.place(flame, (sx * 0.19, 0.08, 0.16))
        parts += [cup, cnd, flame]
    plate = G.lathe("plate", [(0.0, 0.0), (0.06, 0.0), (0.085, 0.015), (0.08, 0.016), (0.0, 0.006)], 24, mat=gold)
    G.place(plate, (0.0, -0.1, 0.07))
    parts.append(plate)
    for k, (dx, dy, dz) in enumerate(((-0.025, -0.01, 0.0), (0.025, -0.01, 0.0), (0.0, 0.025, 0.0), (0.0, 0.0, 0.04))):
        o = G.sphere("orange", 0.026, loc=(dx, -0.1 + dy, 0.096 + dz), mat=orange, segs=16, rings=10, scale=(1, 1, 0.92))
        parts.append(o)
    for k in range(3):
        b = G.tube("banana", [(-0.06, -0.14 + k * 0.012, 0.09 + 0.012 * k), (0.0, -0.17 + k * 0.012, 0.075 + 0.012 * k),
                              (0.06, -0.14 + k * 0.012, 0.09 + 0.012 * k)], 0.012, 8, mat=banana,
                   rfunc=lambda t: 0.6 + 0.4 * math.sin(t * math.pi))
        parts.append(b)
    cols = [G.col_box("wood", (W, D, 0.07)), G.col_box("wood", (W + 0.12, D + 0.12, 0.13), loc=(0, 0, 0.57))]
    marks = [light_marker("LIGHT_01", (0, 0.0, 0.2), kind="omni", range=1.4, energy=0.35, color=[1.0, 0.35, 0.22],
                          shadow=False, fade=20.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("altar_box")}


# ---------------------------------------------------------------------------
# Laundry drying rack with clothes
# ---------------------------------------------------------------------------
def drape(name, width, drop_front, drop_back, rail, mat, rng, n=(10, 14), sway=0.02):
    """Cloth sheet hung over a horizontal rail along X at `rail` (x, y, z)."""
    nx, ny = n
    bm = bmesh.new()
    rows = []
    total = drop_front + drop_back
    for j in range(ny + 1):
        s = j / ny * total
        row = []
        for i in range(nx + 1):
            x = (i / nx - 0.5) * width
            if s < drop_front:
                y = -0.012 - 0.004 * (s / drop_front)
                z = -(drop_front - s)
            else:
                y = 0.012 + 0.004 * ((s - drop_front) / max(drop_back, 1e-3))
                z = -(s - drop_front)
            if abs(z) < 0.015:
                y *= abs(z) / 0.015
                z = 0.008 * (1 - abs(z) / 0.015)
            wv = sway * math.sin(x * 25 + j * 0.4) * (abs(z) / max(drop_front, drop_back))
            row.append(bm.verts.new((rail[0] + x + 0.004 * math.sin(z * 30), rail[1] + y + wv, rail[2] + z)))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    ob = G.obj_from_bm(name, bm, mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


@prop("laundry_rack", category="home", surface="metal", mass=3.5, tags=["laundry", "balcony"])
def laundry_rack():
    rng = random.Random(40)
    steel = PN.metal("rack", "stainless", dirt=0.4, wear=0.3)
    foot = PN.plastic("rfoot", "#e8e8e2", rough=0.4)
    cloth = [PN.fabric("shirt", "#3d6fb0", weave_scale=1800, fade=0.5, dirt=0.15, role="2s"),
             PN.fabric("towel", "#e9e2cf", weave_scale=900, fade=0.3, dirt=0.25, role="2s", wrinkle=0.9),
             PN.fabric("trousers", "#2b2f36", weave_scale=1500, fade=0.6, dirt=0.15, role="2s"),
             PN.fabric("ao", "#c33a4a", weave_scale=1800, fade=0.4, dirt=0.15, role="2s", stripes=("#f0e6d8", 120.0))]
    W, D, H = 1.25, 0.55, 1.05
    parts = []
    for sx in (-1, 1):
        x = sx * W / 2
        for sy in (-1, 1):
            parts.append(G.tube("leg", [(x, sy * D / 2, 0.02), (x, sy * 0.06, H)], 0.009, 8, mat=steel))
            parts.append(G.cyl("foot", 0.014, 0.025, loc=(x, sy * D / 2, 0.0), segs=10, mat=foot))
        parts.append(G.tube("pivot", [(x, 0.0, H * 0.48 - 0.0), (x + sx * 0.0001, 0.0, H * 0.48)], 0.012, 8, mat=steel))
    rails = []
    for (y, z) in ((-0.06, H), (0.06, H), (-0.17, H * 0.72), (0.17, H * 0.72), (-0.26, 0.28), (0.26, 0.28)):
        parts.append(G.tube("rail", [(-W / 2, y, z), (W / 2, y, z)], 0.007, 8, mat=steel))
        rails.append((y, z))
    plan = [(0, -0.3, 0.38, 0.38, 0), (1, 0.3, 0.6, 0.5, 1), (2, -0.25, 0.5, 0.4, 3), (3, 0.2, 0.42, 0.42, 4)]
    for (ci, x, w, drop, ri) in plan:
        y, z = rails[ri]
        dr = min(drop, z - 0.05)
        parts.append(drape("cloth", w, dr, dr * rng.uniform(0.6, 0.95), (x, y, z + 0.008), cloth[ci], rng))
    cols = [G.col_box("metal", (W, 0.1, 0.05), loc=(0, 0, H - 0.03))]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Footwear left at doorways
# ---------------------------------------------------------------------------
def footprint(length=0.26, width=0.1, n=16):
    """Sole outline (x along length, heel at -L/2), slightly asymmetric like a right foot."""
    pts = []
    for i in range(n):
        t = i / (n - 1)
        x = -length / 2 + length * t
        w = width * (0.72 + 0.28 * math.sin(math.pi * (0.15 + 0.85 * t))) * (0.8 + 0.2 * t if t < 0.85 else
                                                                               (1 - (t - 0.85) * 3.5))
        pts.append((x, w / 2 + 0.006 * t))
    for i in range(n - 1, -1, -1):
        t = i / (n - 1)
        x = -length / 2 + length * t
        w = width * (0.72 + 0.28 * math.sin(math.pi * (0.15 + 0.85 * t))) * (0.8 + 0.2 * t if t < 0.85 else
                                                                               (1 - (t - 0.85) * 3.5))
        pts.append((x, -w / 2 + 0.004 * t))
    return pts


def _flipflop(mat_sole, mat_strap, mirror, length=0.25):
    sole = G.extrude("sole", footprint(length, 0.095), 0.014, mat=mat_sole, bevel=0.003, centre=False)
    if mirror:
        G.place(sole, scale=(1, -1, 1))
        import bmesh as _b
        bm = _b.new()
        bm.from_mesh(sole.data)
        _b.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(sole.data)
        bm.free()
    s = -1 if mirror else 1
    toe = (length * 0.28, 0.0 * s, 0.014)
    a = (-length * 0.08, 0.045 * s, 0.014)
    b = (-length * 0.08, -0.045 * s, 0.014)
    st1 = G.tube("strap", [toe, (length * 0.2, 0.01 * s, 0.04), (length * 0.05, 0.035 * s, 0.045), a], 0.005, 6,
                 mat=mat_strap)
    st2 = G.tube("strap", [toe, (length * 0.2, -0.01 * s, 0.04), (length * 0.05, -0.035 * s, 0.045), b], 0.005, 6,
                 mat=mat_strap)
    return [sole, st1, st2]


@prop("slippers_pair", category="home", dynamic=True, surface="plastic", material_kind="soft", mass=0.25,
      tags=["doorway", "knockable", "footwear"])
def slippers_pair():
    sole = PN.rubber("ffsole", "#e9e6dc", rough=0.6, dirt=0.8, dust=0.4, ground=0.9, wear=0.7)
    top = PN.plastic("fftop", "#2a5fae", rough=0.5, fade=0.5, scratch=0.6, dirt=0.7)
    strap = PN.rubber("ffstrap", "#2a5fae", rough=0.45, dirt=0.4)
    parts = []
    for i, (dx, dy, rot, mir) in enumerate(((0.0, -0.06, -6, False), (0.02, 0.065, 9, True))):
        objs = _flipflop(sole, strap, mir)
        layer = G.extrude("top", footprint(0.25, 0.093), 0.003, mat=top, centre=False)
        if mir:
            G.place(layer, scale=(1, -1, 1))
        G.place(layer, (0, 0, 0.0115))
        objs.append(layer)
        for o in objs:
            G.place(o, (0, 0, 0), (0, 0, rot))
            G.place(o, (dx, dy, 0))
        parts += objs
    cols = [G.col_box("plastic", (0.27, 0.24, 0.03))]
    return {"parts": parts, "colliders": cols}


@prop("sandals_honeycomb", category="home", dynamic=True, surface="plastic", material_kind="soft", mass=0.4,
      tags=["doorway", "knockable", "footwear"])
def sandals_honeycomb():
    """'Dép tổ ong' — the classic moulded honeycomb PVC slip-on, olive green."""
    nb = PN.NB("honeycomb")
    hexd = nb.voronoi(nb.coords((1, 1.15, 1)), scale=55, feature="DISTANCE_TO_EDGE", rnd=0.0)
    holes = nb.smooth(hexd, 0.12, 0.2)
    base = PN._var(nb, "#55663a", 0.05, 6)
    c = nb.mixc(nb.mul(nb.inv(holes), 0.92), base, "#141a10")
    s = nb.st(c, nb.mixf(holes, 0.8, 0.42), 0.0, nb.mul(holes, 1.0))
    s = nb.weather(s, dirt=0.7, dust=0.4, ground=0.9, ground_h=0.02)
    mat = nb.finish(s, bump=0.0012)
    sole_m = PN.rubber("hcsole", "#3b4628", dirt=0.8, ground=0.9)
    parts = []
    for (dx, dy, rot, mir) in ((0.0, -0.065, 4, False), (0.03, 0.065, -7, True)):
        sole = G.extrude("sole", footprint(0.26, 0.1), 0.018, mat=sole_m, bevel=0.004, centre=False)
        # upper: half-shell over the forefoot
        bm = bmesh.new()
        rows = []
        n, m = 10, 12
        for i in range(n + 1):
            t = i / n
            x = -0.02 + 0.13 * t
            hw = 0.05 * (1 - 0.35 * t ** 2)
            hh = 0.045 * (1 - t ** 1.8) + 0.008
            row = []
            for j in range(m + 1):
                u = j / m
                a = math.pi * u
                row.append(bm.verts.new((x, -math.cos(a) * hw, 0.018 + math.sin(a) * hh)))
            rows.append(row)
        for i in range(n):
            for j in range(m):
                bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        up = G.obj_from_bm("upper", bm, mat)
        G.solidify(up, 0.004, offset=1.0)
        heel = G.tube("heelstrap", [(-0.02, 0.05, 0.03), (-0.1, 0.04, 0.055), (-0.12, 0.0, 0.06), (-0.1, -0.04, 0.055),
                                    (-0.02, -0.05, 0.03)], 0.006, 6, mat=mat)
        objs = [sole, up, heel]
        for o in objs:
            if mir:
                G.place(o, scale=(1, -1, 1))
                bm2 = bmesh.new()
                bm2.from_mesh(o.data)
                bmesh.ops.reverse_faces(bm2, faces=list(bm2.faces))
                bm2.to_mesh(o.data)
                bm2.free()
            G.place(o, (0, 0, 0), (0, 0, rot))
            G.place(o, (dx, dy, 0))
        parts += objs
    cols = [G.col_box("plastic", (0.29, 0.26, 0.07))]
    return {"parts": parts, "colliders": cols}


@prop("shoes_canvas_pair", category="home", dynamic=True, surface="fabric", material_kind="soft", mass=0.6,
      tags=["doorway", "knockable", "footwear"])
def shoes_canvas_pair():
    """White canvas 'giày bata' with rubber toe caps and laces."""
    canvas = PN.fabric("canvas", "#e6e2d4", weave_scale=2200, rough=0.9, fade=0.2, dirt=0.75, ground=0.9, role="base",
                       wrinkle=0.6)
    rub = PN.rubber("bsole", "#e2ddcf", rough=0.55, dirt=0.85, ground=1.0, wear=0.5)
    stripe = PN.rubber("bstripe", "#2a4d8a", rough=0.5, dirt=0.4)
    lace = PN.fabric("lace", "#efece4", weave_scale=4000, role="base", dirt=0.5)
    parts = []
    for (dx, dy, rot, mir) in ((0.0, -0.07, 3, False), (0.04, 0.07, -11, True)):
        Ls = 0.27
        sole = G.extrude("sole", footprint(Ls, 0.098), 0.026, mat=rub, bevel=0.006, centre=False)
        band = G.extrude("band", footprint(Ls + 0.004, 0.102), 0.006, mat=stripe, bevel=0.0015, centre=False)
        G.place(band, (0, 0, 0.012))
        # upper: lofted cross-sections from heel to toe
        bm = bmesh.new()
        rows = []
        n, m = 16, 14
        for i in range(n + 1):
            t = i / n
            x = -Ls / 2 + 0.01 + (Ls - 0.02) * t
            hw = 0.046 * (0.78 + 0.22 * math.sin(math.pi * (0.15 + 0.85 * t))) * (1 if t < 0.85 else (1 - (t - 0.85) * 2.4))
            hh = (0.075 if t < 0.35 else 0.075 - (t - 0.35) * 0.09) * (1 if t < 0.9 else (1 - (t - 0.9) * 6))
            hh = max(hh, 0.012)
            row = []
            for j in range(m + 1):
                u = j / m
                a = math.pi * u
                yy = -math.cos(a) * hw
                zz = 0.024 + math.sin(a) ** 0.8 * hh
                # collar opening at the back half: lower the top
                if t < 0.45 and 0.25 < u < 0.75:
                    zz = 0.024 + hh * 0.85
                row.append(bm.verts.new((x, yy, zz)))
            rows.append(row)
        for i in range(n):
            for j in range(m):
                bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
        up = G.obj_from_bm("upper", bm, canvas)
        G.solidify(up, 0.003, offset=1.0)
        G.wobble(up, 0.002, 30, seed=int(dy * 100))
        toe = G.lathe("toecap", [(0.0, 0.0), (0.05, 0.0), (0.052, 0.02), (0.035, 0.04), (0.0, 0.045)], 20, mat=rub)
        for v in toe.data.vertices:
            v.co.y *= 0.95
            v.co.x *= 0.9
        G.place(toe, (Ls / 2 - 0.05, 0, 0.022))
        lacing = []
        for k in range(5):
            x = -0.02 + k * 0.022
            lacing.append(G.tube("lace", [(x, -0.022, 0.085 - k * 0.006), (x + 0.011, 0.0, 0.088 - k * 0.006),
                                          (x, 0.022, 0.085 - k * 0.006)], 0.0018, 4, mat=lace))
        lacing.append(G.tube("lace", [(-0.03, 0.0, 0.09), (-0.06, 0.03, 0.07), (-0.07, 0.05, 0.03), (-0.09, 0.08, 0.002)],
                             0.0018, 4, mat=lace))
        objs = [sole, band, up, toe] + lacing
        for o in objs:
            if mir:
                G.place(o, scale=(1, -1, 1))
                bm2 = bmesh.new()
                bm2.from_mesh(o.data)
                bmesh.ops.reverse_faces(bm2, faces=list(bm2.faces))
                bm2.to_mesh(o.data)
                bm2.free()
            G.place(o, (0, 0, 0), (0, 0, rot))
            G.place(o, (dx, dy, 0))
        parts += objs
    cols = [G.col_box("fabric", (0.3, 0.28, 0.1))]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Pet bowls
# ---------------------------------------------------------------------------
def _bowl(mat, rub):
    b = G.lathe("bowl", [(0.0, 0.006), (0.06, 0.006), (0.075, 0.008), (0.085, 0.045), (0.088, 0.05), (0.083, 0.05),
                         (0.07, 0.016), (0.062, 0.013), (0.0, 0.013)], 40, mat=mat)
    ring = G.lathe("ring", [(0.058, 0.0), (0.072, 0.0), (0.074, 0.008), (0.06, 0.009)], 40, mat=rub)
    return [b, ring]


@prop("food_bowl", category="home", surface="metal", material_kind="metal", mass=0.25, tags=["cat", "food"])
def food_bowl():
    rng = random.Random(50)
    steel = PN.metal("fbowl", "stainless", dirt=0.5, wear=0.6)
    rub = PN.rubber("fring", "#2a2a2a", dirt=0.5)
    rice = PN.organic("rice", [(0.0, "#d9d2bf"), (0.7, "#efe9da"), (1.0, "#c9b896")], scale=200, rough=0.55,
                      detail_scale=600, h_amp=0.8)
    fish = PN.organic("fishflake", [(0.0, "#8a6a4a"), (0.6, "#b99a74"), (1.0, "#d8c4a4")], scale=60, rough=0.5)
    parts = _bowl(steel, rub)
    heap = G.lathe("heap", [(0.0, 0.03), (0.06, 0.025), (0.072, 0.016)], 24, mat=rice,
                   rfunc=lambda r, z, a: r * (1 + 0.06 * math.sin(a * 4)))
    G.wobble(heap, 0.004, 60, seed=3)
    parts.append(heap)
    for k in range(9):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0, 0.045)
        fl = G.rbox("flake", (rng.uniform(0.01, 0.018), rng.uniform(0.006, 0.01), 0.004), bevel=0.0015, mat=fish)
        G.place(fl, (0, 0, 0), (rng.uniform(-30, 30), rng.uniform(-30, 30), rng.uniform(0, 360)))
        G.place(fl, (math.cos(a) * r, math.sin(a) * r, 0.026 + (0.045 - r) * 0.08))
        parts.append(fl)
    cols = [G.col_cyl("metal", 0.088, 0.05, segs=12)]
    return {"parts": parts, "colliders": cols}


@prop("water_bowl", category="home", surface="metal", material_kind="metal", mass=0.6, tags=["cat", "water"])
def water_bowl():
    steel = PN.metal("wbowl", "stainless", dirt=0.5, wear=0.6)
    rub = PN.rubber("wring", "#2a2a2a", dirt=0.5)
    parts = _bowl(steel, rub)
    water = G.lathe("water", [(0.081, 0.038), (0.0, 0.038)], 32, mat=PN.glass_material("glass_water", (0.75, 0.82, 0.8),
                                                                                       alpha=0.35, rough=0.02))
    cols = [G.col_cyl("metal", 0.088, 0.05, segs=12)]
    return {"parts": parts, "glass": [water], "colliders": cols}
