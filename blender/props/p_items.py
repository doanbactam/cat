"""Gameplay items (PickupItem meshes): res://assets/models/props/item_<id>.glb for every entry of
data/items/items.json. Small, readable, real-size, origin = bottom centre (lying as found on the ground).
Every item: one baked texture set (density 2048 px/m), catalog category "item", "item_id": <id>."""
import math
import os
import random
import sys

from mathutils import Vector, noise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import props_geo as G  # noqa: E402
import props_nodes as PN  # noqa: E402
from props_bake import register  # noqa: E402

LABELS = os.path.join(HERE, "labels")


def L(name):
    return os.path.join(LABELS, name + ".png")


def item(item_id, *, mass, surface="fabric", material_kind="soft", tags=(), file_id=None, **kw):
    """Decorator: register `item_<file_id or item_id>`."""
    pid = "item_" + (file_id or item_id)

    def deco(fn):
        register(pid, fn, category="item", kind="item", dynamic=False, mass=mass, surface=surface,
                 material_kind=material_kind, name_key="ITEM_" + item_id.upper(), item_id=item_id,
                 density=kw.pop("density", 2048.0), max_tex=kw.pop("max_tex", 1024), min_tex=kw.pop("min_tex", 256),
                 tags=["item", *tags], **kw)
        return fn
    return deco


def _drop(parts, z=0.0):
    """Translate parts so the lowest vertex sits at z."""
    mn, _ = G.bounds(parts)
    for p in parts:
        G.place(p, (0, 0, z - mn.z))
    return parts


def _centre_xy(parts):
    mn, mx = G.bounds(parts)
    c = (mn + mx) * 0.5
    for p in parts:
        G.place(p, (-c.x, -c.y, 0))
    return parts


# ---------------------------------------------------------------------------
# fish helpers
# ---------------------------------------------------------------------------
def fish_body(name, length, height, width, mat, segs=20, on_side=True, rng=None):
    """Spindle-shaped fish body along +X (head at +X). on_side: flattened along Z (lying on its side,
    back toward +Y); otherwise upright (flattened along Y, back +Z). Centre line at the origin."""
    prof = []
    n = 18
    for i in range(n + 1):
        t = i / n
        # tail stalk (t=0) -> max girth at 0.38 -> blunt head (t=1)
        r = (math.sin(math.pi * min(1.0, 0.5 * t ** 1.6 + 0.48 * t)) ** 0.6) * 0.5 * height
        if t > 0.85:
            r *= 1.0 - 2.2 * (t - 0.85) ** 1.5
        r = max(r, 0.06 * height) if t < 0.98 else r
        prof.append((r, t * length))
    prof[0] = (0.07 * height, 0.0)
    prof.append((0.0, length + 0.0005))
    body = G.lathe(name, [(0.0, -0.0005)] + prof, segs, mat=mat, smooth_angle=None)
    sx = width / height
    if on_side:
        # Z -> X, flatten what becomes Z
        G.place(body, (-length / 2, 0, 0), (0, 90, 0))
        G.place(body, (0, 0, 0), (0, 0, 0), (1, 1, sx))
    else:
        G.place(body, (-length / 2, 0, 0), (0, 90, 0))
        G.place(body, (0, 0, 0), (0, 0, 0), (1, sx, 1))
    return body


def _cut_above(ob, z):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > z], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def fin(name, pts2d, mat, thick=0.0008):
    f = G.extrude(name, pts2d, thick, mat=mat, centre=True)
    return f


# ---------------------------------------------------------------------------
# Fish (cá nục / round scad, fresh from the market) — 21 cm, lying on its side
# ---------------------------------------------------------------------------
@item("fish", mass=0.12, surface="fabric", material_kind="soft", tags=["food", "mouth"])
def item_fish():
    Lh, H, W = 0.21, 0.056, 0.026
    skin = PN.fish_skin("scad", back="#1f3446", belly="#d2d6d0", stripe="#c9a640", dorsal="-Y", centre=-0.008,
                        span=1.3, wet=True)
    finm = PN.organic("fin", [(0.0, "#6b7a80"), (0.6, "#9aa4a2"), (1.0, "#c9c9bd")], scale=60, rough=0.35,
                      detail_scale=400, role="2s")
    eye = PN.glass_opaque("eye", "#1b1a14", rough=0.05, dirt=0.0)
    iris = PN.metal("iris", "gold", dirt=0.1, wear=0.0)
    parts = []
    body = fish_body("body", Lh * 0.86, H, W, skin, segs=24)
    G.place(body, (0.012, 0, 0))
    G.wobble(body, 0.0008, 40, seed=2)
    parts.append(body)
    # forked tail fin in XY (lying flat)
    tx = -Lh * 0.43 + 0.012
    tail = fin("tail", [(tx + 0.008, 0.0), (tx - 0.034, 0.032), (tx - 0.042, 0.028), (tx - 0.02, 0.0),
                        (tx - 0.042, -0.028), (tx - 0.034, -0.032)], finm, 0.0012)
    G.place(tail, (0, 0, 0.0))
    G.wobble(tail, 0.001, 50, seed=4, axis_mask=(0, 0, 1))
    # dorsal finlets & fins (toward +Y on the side-lying fish), pectoral fin flat on the upper side
    dors = fin("dorsal", [(-0.03, 0.019), (0.0, 0.027), (0.035, 0.022), (0.03, 0.017), (-0.03, 0.015)], finm)
    anal = fin("anal", [(-0.045, -0.015), (-0.025, -0.022), (0.0, -0.018), (0.0, -0.014), (-0.045, -0.012)], finm)
    pect = fin("pect", [(0.045, 0.0), (0.02, 0.007), (0.012, 0.004), (0.02, -0.002)], finm)
    G.place(pect, (0, 0, W * 0.5 - 0.001), (0, -12, 0))
    parts += [tail, dors, anal, pect]
    # head: eye, gill cover line, mouth
    ex = Lh * 0.43 - 0.018
    e = G.sphere("eye", 0.0068, loc=(ex, 0.005, W * 0.36), mat=eye, segs=16, rings=8, scale=(1, 1, 0.55))
    ir = G.lathe("iris", [(0.0074, 0.0), (0.0079, 0.0007), (0.0068, 0.0014)], 18, mat=iris)
    G.place(ir, (ex, 0.005, W * 0.36 - 0.0009))
    gill = G.tube("gill", [(ex - 0.016, 0.014, W * 0.33), (ex - 0.02, 0.002, W * 0.43), (ex - 0.017, -0.012, W * 0.33)],
                  0.0009, 6, mat=skin)
    parts += [e, ir, gill]
    for p in parts:   # back toward -Y (the side the player usually sees first in previews/showcase)
        G.place(p, (0, 0, 0), (0, 0, 180))
    _drop(parts)
    cols = [G.col_box("fabric", (Lh, 0.06, W))]
    return {"parts": parts, "colliders": cols}


@item("dried_fish", mass=0.04, surface="fabric", material_kind="soft", tags=["food", "mouth"])
def item_dried_fish():
    """Cá cơm khô: a little bundle of nine sun-dried anchovies, tied at the tails with a twist of banana fibre;
    heads fan out, bodies slightly curled and twisted from drying."""
    skin = PN.organic("anch", [(0.0, "#3f3a30"), (0.3, "#6a604b"), (0.6, "#8f8466"), (0.85, "#b3a986"),
                               (1.0, "#c9c6b8")], scale=70, rough=0.5, detail_scale=420, h_amp=0.5, cav_dark=0.55,
                      spec_spots=(160, 0.1, "#e9ecef"))
    stripe = PN.metal("anch_stripe", "tin", dirt=0.2, wear=0.2)
    eye_m = PN.glass_opaque("anch_eye", "#15130f", rough=0.15, dirt=0.0)
    tie = PN.fabric("fibre", "#a3854f", weave_scale=2600, rough=0.92, role="base", wrinkle=0.0, dirt=0.3)
    rng = random.Random(14)
    parts = []
    nfish = 9
    tie_x = -0.018
    for k in range(nfish):
        Lf = rng.uniform(0.062, 0.074)
        Hf, Wf = 0.0105, 0.0046
        body = fish_body("anchovy", Lf, Hf, Wf, skin, segs=12, on_side=True)
        # silver lateral stripe: thin ribbon along the flank (upper side, +Z)
        st = G.tube("stripe", [(-Lf * 0.36, 0.0, Wf * 0.42), (0.0, 0.0004, Wf * 0.5), (Lf * 0.33, 0.0, Wf * 0.4)],
                    0.0009, 5, mat=stripe)
        G.place(st, (0, 0, 0), (0, 0, 0), (1, 1.6, 0.35))
        G.place(st, (0, 0, Wf * 0.28))
        tail = fin("tail", [(-Lf / 2 + 0.003, 0.0), (-Lf / 2 - 0.007, 0.0048), (-Lf / 2 - 0.0085, 0.0036),
                            (-Lf / 2 - 0.0045, 0.0), (-Lf / 2 - 0.0085, -0.0036), (-Lf / 2 - 0.007, -0.0048)],
                   skin, 0.0007)
        eye = G.sphere("eye", 0.0012, loc=(Lf / 2 - 0.0045, 0.0009, Wf * 0.38), mat=eye_m, segs=8, rings=5,
                       scale=(1, 1, 0.6))
        grp = [body, st, tail, eye]
        # drying deformation: gentle curl along the length + a little twist
        curl = rng.uniform(-0.12, 0.12)
        for g in grp:
            for v in g.data.vertices:
                t = v.co.x / Lf
                v.co.y += curl * Lf * t * t
                v.co.z += 0.0018 * math.sin(t * 3.0) * (k % 2 * 2 - 1)
        # fan: tails converge at the tie, heads spread; two layers
        layer = k % 2
        spread = (k - (nfish - 1) / 2) / ((nfish - 1) / 2)
        ang = spread * 22 + rng.uniform(-3, 3)
        roll = rng.uniform(-10, 10) + (8 if layer else -8)
        for g in grp:
            G.place(g, (Lf / 2 - 0.006, 0, 0))            # pivot = just ahead of the tail fin (the tie)
            G.place(g, (0, 0, 0), (roll, 0, 0))
            G.place(g, (0, 0, 0), (0, 0, ang))
            G.place(g, (tie_x, spread * 0.003, 0.003 + layer * 0.0045))
        parts += grp
    # banana-fibre tie: a flattened ring around the tails + a short knotted tag
    band = G.lathe("tie", [(0.0105, -0.0028), (0.0118, 0.0), (0.0105, 0.0028)], 20, mat=tie)
    G.place(band, (0, 0, 0), (0, 90, 0))
    G.place(band, scale=(1.0, 1.0, 0.55))
    G.place(band, (tie_x, 0.0, 0.0062))
    knot = G.tube("knot", [(tie_x, -0.004, 0.0115), (tie_x - 0.006, -0.009, 0.012),
                           (tie_x - 0.012, -0.012, 0.009)], 0.0013, 5, mat=tie, rfunc=lambda t: 1.0 - 0.5 * t)
    parts += [band, knot]
    _drop(parts)
    _centre_xy(parts)
    mn, mx = G.bounds(parts)
    sz = mx - mn
    return {"parts": parts, "colliders": [G.col_box("fabric", (sz.x, sz.y, max(0.012, sz.z)))]}


@item("shrimp", mass=0.015, surface="fabric", material_kind="soft", tags=["food", "mouth"])
def item_shrimp():
    """Boiled river shrimp (tôm luộc), curled, ~8 cm."""
    shell = PN.organic("shell", [(0.0, "#c2401e"), (0.45, "#e6703a"), (0.8, "#f3a26a"), (1.0, "#f6d1aa")], scale=30,
                       rough=0.32, detail_scale=300, h_amp=0.3, sss=0.15)
    pts = []
    for i in range(16):
        t = i / 15
        a = math.radians(-40 + 220 * t)
        r = 0.026 - 0.008 * t
        pts.append((math.cos(a) * r, 0.0, math.sin(a) * r + 0.026))

    def rf(t):
        return max(0.25, math.sin(math.pi * min(1.0, 0.15 + t * 0.95)) ** 0.6) * (1.0 - 0.35 * t)
    body = G.tube("body", pts, 0.0085, 14, mat=shell, rfunc=rf)
    G.place(body, (0, 0, 0), (0, 0, 0), (1, 1.1, 1))
    # segment ridges
    parts = [body]
    for k in range(6):
        t = 0.25 + k * 0.1
        i = int(t * 15)
        p, q = Vector(pts[i]), Vector(pts[min(i + 1, 15)])
        d = (q - p).normalized()
        ring = G.tube("seg", [p - d * 0.0006, p + d * 0.0006], 0.0088 * rf(t) * 1.05, 14, mat=shell)
        parts.append(ring)
    # tail fan
    tp = Vector(pts[-1])
    fan = G.extrude("fan", [(0, 0), (-0.012, 0.007), (-0.016, 0.0), (-0.012, -0.007)], 0.0012, mat=shell)
    G.place(fan, (0, 0, 0), (90, 0, 0))
    G.place(fan, tuple(tp), (0, -150, 0))
    parts.append(fan)
    # head, rostrum, antennae, legs
    hp = Vector(pts[0])
    head = G.sphere("head", 0.0095, loc=tuple(hp + Vector((0.004, 0, -0.002))), mat=shell, segs=14, rings=8,
                    scale=(1.5, 1.1, 1.0))
    ros = G.tube("rostrum", [tuple(hp + Vector((0.012, 0, 0.003))), tuple(hp + Vector((0.026, 0, 0.0)))], 0.0012, 5,
                 mat=shell, rfunc=lambda t: 1 - 0.8 * t)
    parts += [head, ros]
    for s in (-1, 1):
        ant = [tuple(hp + Vector((0.01, s * 0.002, -0.002))), tuple(hp + Vector((0.03, s * 0.003, -0.008 + s * 0.006))),
               tuple(hp + Vector((0.048, s * 0.003, -0.012 + s * 0.014))), tuple(hp + Vector((0.06, s * 0.002, -0.014 + s * 0.022)))]
        parts.append(G.tube("antenna", ant, 0.0004, 4, mat=shell))
        for k in range(5):
            t = 0.08 + k * 0.07
            i = int(t * 15)
            p = Vector(pts[i])
            parts.append(G.tube("leg", [tuple(p + Vector((0, s * 0.003, 0))), tuple(p + Vector((0.004, s * 0.004, -0.009)))],
                                0.0006, 4, mat=shell))
    for p in parts:
        G.place(p, (0, 0, 0), (90, 0, 0))
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.07, 0.05, 0.022))]}


# ---------------------------------------------------------------------------
@item("gio_lua", mass=0.08, surface="fabric", material_kind="soft", tags=["food", "mouth"])
def item_gio_lua():
    """A thick slice-end of giò lụa (Vietnamese pork roll) still in its banana-leaf wrap and string."""
    R, Lg = 0.034, 0.018
    meat = PN.organic("gio", [(0.0, "#c99d8c"), (0.5, "#dcb6a6"), (1.0, "#ead0c2")], scale=60, rough=0.38,
                      detail_scale=500, h_amp=0.3, sss=0.25, spec_spots=(140, 0.06, "#c9b09a"))
    leafm = PN.leaf("banana", "#5b7d33", vein="#7f9a4a", rough=0.4, role="base", axis="Z", spots=0.5)
    inner = PN.organic("leafin", [(0.0, "#9db06a"), (1.0, "#c8cf96")], scale=20, rough=0.4)
    twine = PN.fabric("twine", "#b49a6c", weave_scale=2500, rough=0.9, role="base", wrinkle=0.0)
    parts = []
    core = G.cyl("core", R - 0.002, Lg, segs=32, bevel=0.002, mat=meat)
    wrap = G.lathe("wrap", [(R + 0.0015, 0.004), (R + 0.002, Lg - 0.002), (R - 0.0005, Lg + 0.003)], 32, mat=leafm,
                   rfunc=lambda r, z, a: r * (1 + 0.025 * math.sin(a * 5 + z * 40)))
    G.solidify(wrap, 0.0012, offset=1.0)
    parts += [core, wrap]
    # overlapping outer leaf layers (folds)
    for k in range(4):
        a0 = k * math.pi / 2 + 0.3
        fold = G.tube("fold", [(math.cos(a0) * (R + 0.003), math.sin(a0) * (R + 0.003), 0.006),
                               (math.cos(a0 + 0.04) * (R + 0.003), math.sin(a0 + 0.04) * (R + 0.003), Lg - 0.004)],
                      0.0012, 5, mat=leafm)
        parts.append(fold)
    for z in (0.009,):
        parts.append(G.lathe("string", [(R + 0.0032, z - 0.0012), (R + 0.0042, z), (R + 0.0032, z + 0.0012)], 24,
                             mat=twine))
    # cut faces are the meat; the slice lies flat on its face, leaf ring around it
    for p in parts:
        G.place(p, (0, 0, 0), (0, 0, 0))
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_cyl("fabric", R + 0.004, Lg, segs=10)]}


@item("pate_crust", mass=0.03, surface="fabric", material_kind="soft", tags=["food", "mouth"])
def item_pate_crust():
    """The pointed end of a Hanoi bánh mì (~10 cm), torn off: blistered golden crust split open along the
    scored 'ear', airy crumb at the torn face with a smear of pâté."""
    crust = PN.organic("crust", [(0.0, "#8d5520"), (0.3, "#b8772f"), (0.62, "#d7a457"), (0.85, "#e6c486"),
                                 (1.0, "#efd9a8")], scale=34, rough=0.5, detail_scale=380, h_amp=0.9,
                       spec_spots=(90, 0.12, "#f2dfb4"), cav_dark=0.5, bump=0.0006)
    crumb = PN.organic("crumb", [(0.0, "#cdb487"), (0.55, "#ead9b4"), (1.0, "#f7eed8")], scale=140, rough=0.85,
                       detail_scale=700, h_amp=1.4, cav_dark=0.75, bump=0.0008)
    pate = PN.organic("pate", [(0.0, "#5e3b26"), (0.55, "#80553a"), (1.0, "#a2775a")], scale=50, rough=0.3,
                      sss=0.1, detail_scale=300, h_amp=0.3)
    Lb, R = 0.10, 0.026
    tear_z = Lb
    rows, segs = 22, 32
    rng = random.Random(7)

    def radius(t):        # t: 0 tip .. 1 torn end
        return R * (0.13 + 0.87 * math.sin(min(1.0, t * 1.25) * math.pi / 2) ** 0.85)

    import bmesh
    bm = bmesh.new()
    vr = []
    for i in range(rows + 1):
        t = i / rows
        row = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            ca, sa = math.cos(a), math.sin(a)
            r = radius(t)
            # cross-section: wide oval, flat bottom (ca<0 is down after the final rotation), domed top
            rr = r * (0.74 if ca > 0 else 0.62 - 0.1 * (-ca) ** 3)
            ry = r * 1.08
            x = ca * rr
            y = sa * ry
            # the scored ear: a raised, split lip along the top-centre, offset to one side
            ear = math.exp(-((a - 0.25) / 0.22) ** 2) * 0.0045 * math.sin(math.pi * min(1.0, t * 1.15)) if ca > 0 else 0.0
            x += ear
            # blistered, uneven crust
            x += 0.0007 * noise.noise(Vector((t * 9, a * 1.7, 3.1)))
            z = t * Lb
            if i == rows:       # ragged torn edge
                z += 0.004 * noise.noise(Vector((a * 2.3, 0.5, 7.0))) + rng.uniform(-0.0012, 0.0012)
            row.append(bm.verts.new((x, y, z)))
        vr.append(row)
    tip = bm.verts.new((0.0, 0.0, -0.004))
    for j in range(segs):
        bm.faces.new((tip, vr[0][(j + 1) % segs], vr[0][j]))
    for i in range(rows):
        for j in range(segs):
            j1 = (j + 1) % segs
            bm.faces.new((vr[i][j], vr[i][j1], vr[i + 1][j1], vr[i + 1][j]))
    shell = G.obj_from_bm("crust", bm, crust)
    G.solidify(shell, 0.0025, offset=-1.0)
    for p in shell.data.polygons:
        p.use_smooth = True
    # torn face: crumb cap following the ragged rim, bulging out with torn lumps
    bm = bmesh.new()
    ring_pts = []
    for j in range(segs):
        a = 2 * math.pi * j / segs
        ca, sa = math.cos(a), math.sin(a)
        r = radius(1.0) - 0.0022
        rr = r * (0.74 if ca > 0 else 0.62 - 0.1 * (-ca) ** 3)
        ring_pts.append((ca * rr, sa * r * 1.08, a))
    centre = bm.verts.new((0.0, 0.0, tear_z + 0.006))
    rings_c = []
    for k in (1.0, 0.66, 0.33):
        row = []
        for (x, y, a) in ring_pts:
            z = tear_z + 0.004 * noise.noise(Vector((a * 2.3, 0.5, 7.0))) * (k ** 2) + 0.006 * (1 - k ** 2) \
                + 0.0025 * noise.noise(Vector((x * 300, y * 300, k * 5)))
            row.append(bm.verts.new((x * k, y * k, z)))
        rings_c.append(row)
    for i in range(2):
        for j in range(segs):
            j1 = (j + 1) % segs
            bm.faces.new((rings_c[i][j], rings_c[i][j1], rings_c[i + 1][j1], rings_c[i + 1][j]))
    for j in range(segs):
        bm.faces.new((rings_c[2][j], rings_c[2][(j + 1) % segs], centre))
    cap = G.obj_from_bm("crumb", bm, crumb)
    G.subsurf(cap, 1)
    for v in cap.data.vertices:   # torn crumb lumps
        v.co.z += 0.0018 * max(0.0, noise.noise(Vector((v.co.x * 260, v.co.y * 260, 2.0))))
    # pâté smear: a thin irregular patch across the crumb, slightly off-centre
    smear = G.grid("pate", R * 1.0, R * 1.1, 10, 10, mat=pate,
                   fn=lambda x, y: 0.0012 + 0.0007 * noise.noise(Vector((x * 150, y * 150, 4.0))))
    for v in smear.data.vertices:
        d = math.hypot(v.co.x / (R * 0.55), v.co.y / (R * 0.6))
        if d > 0.85:
            v.co.z -= 0.004 * (d - 0.85)
    G.place(smear, (0.002, -0.002, tear_z + 0.0055))
    parts = [shell, cap, smear]
    # lay it down: bread axis along X, flat bottom on the ground, slight roll
    for p in parts:
        G.place(p, (0, 0, 0), (0, -90, 0))
        G.place(p, (0, 0, 0), (6, 0, 0))
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (Lb + 0.01, 2.2 * R, 1.5 * R))]}


@item("quail_egg", mass=0.011, surface="fabric", material_kind="ceramic", tags=["food", "mouth"])
def item_quail_egg():
    egg = PN.organic("qegg", [(0.0, "#e6e2d8"), (0.6, "#f2efe8"), (1.0, "#faf8f3")], scale=10, rough=0.18,
                     detail_scale=300, h_amp=0.08, cav_dark=0.05, sss=0.4)
    H, R = 0.033, 0.0128
    prof = [(0.0, 0.0)]
    for i in range(1, 16):
        t = i / 16
        r = R * math.sin(math.pi * t) ** 0.55 * (1.0 + 0.12 * (0.5 - t))
        prof.append((r, t * H))
    prof.append((0.0, H))
    e = G.lathe("egg", prof, 28, mat=egg)
    G.place(e, (0, 0, 0), (0, 90, 8))
    parts = _centre_xy(_drop([e]))
    return {"parts": parts, "colliders": [G.col_box("fabric", (H, 2 * R, 2 * R))]}


@item("mooncake_crumb", mass=0.04, surface="fabric", material_kind="soft", tags=["food", "mouth", "festival"])
def item_mooncake_crumb():
    """A quarter of a baked mooncake (bánh nướng) with lotus-seed paste and salted egg yolk."""
    crust = PN.organic("mcrust", [(0.0, "#6e3a14"), (0.4, "#9a5a22"), (0.8, "#c4843c"), (1.0, "#d8a35c")], scale=14,
                       rough=0.4, detail_scale=260, h_amp=0.4, sss=0.05)
    fill = PN.organic("mfill", [(0.0, "#b88f52"), (0.5, "#cfa86a"), (1.0, "#e0c48a")], scale=50, rough=0.5,
                      detail_scale=400, h_amp=0.5, spec_spots=(90, 0.05, "#7a5a30"))
    yolk = PN.organic("yolk", [(0.0, "#d0661a"), (0.6, "#e88a2a"), (1.0, "#f3aa48")], scale=30, rough=0.4)
    R, H = 0.045, 0.034
    sector = [(0.0, 0.0)] + [(math.cos(math.radians(a)) * R, math.sin(math.radians(a)) * R) for a in range(0, 91, 9)]
    cut = G.extrude("fill", sector, H - 0.004, mat=fill, bevel=0.0012, segs=1, centre=False)
    G.place(cut, (0, 0, 0.002))
    # crust: outer arc wall + top/bottom shells
    top = G.extrude("top", [(x * 1.02, y * 1.02) for (x, y) in sector], 0.004, mat=crust, bevel=0.0018, segs=2,
                    centre=False)
    G.place(top, (0, 0, H - 0.004))
    bot = G.extrude("bot", [(x * 1.02, y * 1.02) for (x, y) in sector], 0.003, mat=crust, bevel=0.001, segs=1,
                    centre=False)
    arc = [(math.cos(math.radians(a)) * (R + 0.001), math.sin(math.radians(a)) * (R + 0.001), H * 0.5) for a in
           range(0, 91, 6)]
    wall = G.tube("wall", arc, H * 0.5, 16, mat=crust, cap=False)
    G.place(wall, (0, 0, 0), (0, 0, 0), (1, 1, 1))
    for v in wall.data.vertices:
        # flatten the tube into an arc band of width ~4 mm
        rr = math.hypot(v.co.x, v.co.y)
        a = math.atan2(v.co.y, v.co.x)
        rr = R + 0.001 + (rr - (R + 0.001)) * 0.12
        v.co.x, v.co.y = math.cos(a) * rr, math.sin(a) * rr
        v.co.z = max(0.0005, min(H - 0.0005, v.co.z))
    # embossed pattern ridges on top (stamped mould flower)
    parts = [cut, top, bot, wall]
    for k in range(5):
        a = math.radians(9 + k * 18)
        ridge = G.tube("ridge", [(math.cos(a) * 0.01, math.sin(a) * 0.01, H + 0.0005),
                                 (math.cos(a) * 0.036, math.sin(a) * 0.036, H + 0.0005)], 0.0012, 5, mat=crust)
        parts.append(ridge)
    rim = [(math.cos(math.radians(a)) * 0.038, math.sin(math.radians(a)) * 0.038, H + 0.0004) for a in range(2, 89, 6)]
    parts.append(G.tube("rimridge", rim, 0.0011, 5, mat=crust))
    y = G.sphere("yolk", 0.012, loc=(0.006, 0.006, H * 0.5), mat=yolk, segs=20, rings=12, scale=(1, 1, 0.8))
    for v in y.data.vertices:
        v.co.x = max(v.co.x, -0.0004)
        v.co.y = max(v.co.y, -0.0004)
    parts.append(y)
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (R, R, H))]}


# ---------------------------------------------------------------------------
# Bottle cap (currency) — crown cork 26.6 mm, 21 flutes, slightly bent from the opener
# ---------------------------------------------------------------------------
@item("cap", mass=0.002, surface="metal", material_kind="metal", tags=["currency"], density=4096.0, min_tex=512)
def item_cap():
    m = PN.painted_metal("capm", "#c3241f", primer="#c9c6be", bare="#bdbab2", chip=0.4, rust=0.15, gloss=0.25,
                         streaks=0.0, dirt=0.3, dust=0.1, label=True, label_wear=0.25)
    R, H = 0.0133, 0.006

    def flute(r, z, a):
        if z < H - 0.0012:
            return r * (1 + 0.075 * max(0.0, math.cos(a * 21)) ** 0.6)
        return r
    cap = G.lathe("cap", [(R * 1.05, 0.0), (R * 1.04, 0.0006), (R, H - 0.001), (R - 0.0012, H), (0.0, H)], 63, mat=m,
                  rfunc=flute)
    inner = G.lathe("liner", [(0.0, H - 0.0012), (R - 0.0008, H - 0.0012), (R * 1.0, 0.0008), (R * 1.04, 0.0002)], 63,
                    mat=m, rfunc=flute)
    G.label_all_planar_top(cap, (0.0, 0.5, 0.5, 1.0), 0, 0, 2 * R * 1.07, 2 * R * 1.07)
    # opener bend
    for o in (cap, inner):
        for v in o.data.vertices:
            if v.co.x > R * 0.3:
                v.co.z += (v.co.x - R * 0.3) * 0.16
    G.dent(cap, (R * 0.9, 0, H * 0.6), 0.004, 0.0008)
    parts = _drop([cap, inner])
    return {"parts": parts, "colliders": [G.col_cyl("metal", R * 1.05, H, segs=10)], "label": L("misc_items")}


# ---------------------------------------------------------------------------
# Golden lucky-cat figurine (mèo thần tài) — original design: a plump seated tabby-shaped cat,
# left paw raised, hugging a "PHÚC" coin, red bib "LỘC", painted face; gilded ceramic, 11 cm.
# ---------------------------------------------------------------------------
@item("lucky_cat_figurine", mass=0.22, surface="tile", material_kind="ceramic", tags=["quest", "mouth"],
      density=2048.0, max_tex=1024)
def item_lucky_cat_figurine():
    gold = PN.metal("gild", "gold", dirt=0.45, wear=0.55, dust=0.3)
    red = PN.ceramic("bib", "#b81c24", rough=0.12, crackle=0.2, chip=0.3, label=True, label_wear=0.15, dirt=0.3)
    coin = PN.metal("coin", "gold", dirt=0.3, wear=0.4, label=True, label_wear=0.1)
    paint = PN.ceramic("paint", "#f1e6cf", rough=0.1, crackle=0.1, chip=0.1, dirt=0.2)
    black = PN.ceramic("black", "#17130f", rough=0.08, crackle=0.0, chip=0.0, dirt=0.0)
    parts = []
    base = G.lathe("base", [(0.0, 0.0), (0.042, 0.0), (0.045, 0.004), (0.044, 0.01), (0.04, 0.012), (0.0, 0.012)], 40,
                   mat=gold)
    G.place(base, (0, 0, 0), (0, 0, 0), (1.0, 0.85, 1.0))
    body = G.lathe("body", [(0.0, 0.012), (0.034, 0.012), (0.038, 0.025), (0.035, 0.045), (0.027, 0.06),
                            (0.016, 0.068), (0.0, 0.07)], 32, mat=gold)
    G.place(body, (0, 0, 0), (0, 0, 0), (1.0, 0.85, 1.0))
    head = G.sphere("head", 0.03, loc=(0, -0.003, 0.088), mat=gold, segs=28, rings=16, scale=(1.08, 0.92, 0.88))
    parts += [base, body, head]
    for s in (-1, 1):
        ear = G.lathe("ear", [(0.0, 0.0), (0.012, 0.0), (0.0, 0.017)], 8, mat=gold)
        G.place(ear, (0, 0, 0), (0, s * 18, 0), (1.0, 0.55, 1.0))
        G.place(ear, (s * 0.019, -0.002, 0.106))
        inner = G.lathe("earin", [(0.0, 0.0), (0.007, 0.0), (0.0, 0.011)], 8, mat=red)
        G.place(inner, (0, 0, 0), (0, s * 18, 0), (1.0, 0.3, 1.0))
        G.place(inner, (s * 0.019, -0.006, 0.108))
        # eyes: closed happy arcs, black; cheeks & muzzle cream
        arc = [(s * (0.009 + 0.006 * math.cos(math.radians(a))), -0.031, 0.093 + 0.003 * math.sin(math.radians(a)))
               for a in range(10, 171, 20)]
        parts += [ear, inner, G.tube("eye", arc, 0.0011, 5, mat=black)]
        for k in range(3):
            parts.append(G.tube("whisker", [(s * 0.014, -0.03, 0.082 - k * 0.003),
                                            (s * 0.03, -0.024, 0.083 - k * 0.005)], 0.0005, 4, mat=black))
        # hind feet
        foot = G.sphere("foot", 0.012, loc=(s * 0.02, -0.024, 0.017), mat=gold, segs=14, rings=8, scale=(1.0, 1.3, 0.6))
        parts.append(foot)
    muzzle = G.sphere("muzzle", 0.011, loc=(0, -0.026, 0.081), mat=paint, segs=16, rings=8, scale=(1.4, 0.7, 0.8))
    nose = G.sphere("nose", 0.0028, loc=(0, -0.0335, 0.0855), mat=red, segs=10, rings=6)
    parts += [muzzle, nose]
    # raised left paw (cat's left = +X when facing -Y)
    arm = G.tube("arm", [(0.026, -0.006, 0.05), (0.036, -0.012, 0.075), (0.034, -0.016, 0.1)], 0.0085, 14, mat=gold,
                 rfunc=lambda t: 1.0 - 0.1 * t)
    paw = G.sphere("paw", 0.011, loc=(0.034, -0.017, 0.106), mat=gold, segs=16, rings=10, scale=(1, 0.8, 1.1))
    pad = G.sphere("pad", 0.006, loc=(0.034, -0.026, 0.106), mat=red, segs=12, rings=6, scale=(1, 0.4, 1))
    parts += [arm, paw, pad]
    # right arm hugging the coin
    arm2 = G.tube("arm2", [(-0.026, -0.008, 0.06), (-0.02, -0.03, 0.045), (0.004, -0.036, 0.04)], 0.008, 14, mat=gold)
    cz = 0.043
    c = G.cyl("coin", 0.019, 0.005, segs=40, bevel=0.0008, mat=coin)
    G.place(c, (0, 0, 0), (90, 0, 0))
    G.place(c, (-0.006, -0.032, cz))
    G.label_planar(c, (0.0, 0.0, 0.5, 1.0), (-0.006 - 0.0205, -0.04, cz - 0.0205), (1, 0, 0), (0, 0, 1),
                   (0.041, 0.041), normal=(0, -1, 0), min_dot=0.7)
    parts += [arm2, c]
    # bib: collar band + hanging bib with "LỘC"
    collar = G.lathe("collar", [(0.026, 0.066), (0.029, 0.069), (0.026, 0.072)], 32, mat=red)
    G.place(collar, (0, 0, 0), (0, 0, 0), (1.05, 0.9, 1))
    bib = G.grid("bib", 0.03, 0.022, 10, 8, mat=red, fn=lambda x, y: 0.0)
    G.place(bib, (0, 0, 0), (90, 0, 0))
    for v in bib.data.vertices:
        v.co.y = -0.0 - 0.006 * (1 - (v.co.x / 0.016) ** 2)
    G.place(bib, (0, -0.026, 0.06))
    G.label_planar(bib, (0.5, 0.0, 1.0, 1.0), (-0.015, -0.05, 0.049), (1, 0, 0), (0, 0, 1), (0.03, 0.022),
                   normal=(0, -1, 0), min_dot=0.3, bounds_pad=0.02)
    G.solidify(bib, 0.0012, offset=1.0)
    bell = G.sphere("bell", 0.0045, loc=(0.012, -0.03, 0.064), mat=gold, segs=12, rings=8)
    parts += [collar, bib, bell]
    # tail curled round the base
    tail = G.tube("tail", [(0.03, 0.022, 0.016), (0.038, -0.004, 0.016), (0.03, -0.024, 0.018)], 0.0065, 10, mat=gold,
                  rfunc=lambda t: 1.0 - 0.3 * t)
    parts.append(tail)
    cols = [G.col_cyl("tile", 0.045, 0.12, segs=10)]
    return {"parts": parts, "colliders": cols, "label": L("coin_figurine")}


# ---------------------------------------------------------------------------
@item("letter", mass=0.012, surface="fabric", material_kind="soft", tags=["quest", "mouth", "paper"])
def item_letter():
    """Sealed airmail-ish envelope, addressed to Bà Tư (label sheet 'letter'), a little creased."""
    pap = PN.paper("env", "#ece2c9", aged=0.5, label=True, label_wear=0.08, role="base", dirt=0.35)
    W, D, T = 0.16, 0.095, 0.0028
    env = G.rbox("env", (W, D, T), bevel=0.0008, segs=1, mat=pap)
    # subdivide for the crease
    G.subsurf(env, 2)
    G.apply_mods(env)
    for v in env.data.vertices:
        v.co.z += 0.004 * math.exp(-((v.co.x - 0.02) / 0.012) ** 2) + 0.0025 * (v.co.y / D) ** 2 * 4
    # front faces UP (address side); flap side faces down
    G.label_planar(env, (0.0, 0.0, 0.5, 1.0), (-W / 2, -D / 2, 0), (1, 0, 0), (0, 1, 0), (W, D), normal=(0, 0, 1),
                   min_dot=0.5)
    G.label_planar(env, (0.5, 0.0, 1.0, 1.0), (W / 2, -D / 2, 0), (-1, 0, 0), (0, 1, 0), (W, D), normal=(0, 0, -1),
                   min_dot=0.5)
    # wax seal blob on the underside is invisible; a torn stamp corner sticks up a bit
    parts = _drop([env])
    return {"parts": parts, "colliders": [G.col_box("fabric", (W, D, 0.008))], "label": L("letter")}


@item("key", mass=0.02, surface="metal", material_kind="metal", tags=["quest", "mouth"], density=3072.0)
def item_key():
    """Old brass door key (khóa cửa cổ) on a split ring with a red string tag."""
    brass = PN.metal("kbrass", "brass", dirt=0.6, wear=0.7, dust=0.2)
    steel = PN.metal("kring", "stainless", dirt=0.4, wear=0.5)
    cord = PN.fabric("kcord", "#b3262a", weave_scale=3000, rough=0.8, role="base", wrinkle=0.0)
    r = 0.0025
    parts = []
    bow = G.tube("bow", [(math.cos(a) * 0.011, math.sin(a) * 0.011, 0) for a in
                         [2 * math.pi * i / 20 for i in range(20)]], 0.0022, 8, mat=brass, closed=True)
    G.place(bow, (-0.024, 0, 0), (0, 0, 0), (1.0, 0.85, 1.0))
    shaft = G.tube("shaft", [(-0.013, 0, 0), (0.034, 0, 0)], r, 10, mat=brass)
    collar = G.lathe("kcollar", [(0.0, 0.0), (0.0034, 0.0), (0.0036, 0.002), (0.0034, 0.004), (0.0, 0.004)], 12, mat=brass)
    G.place(collar, (0, 0, 0), (0, 90, 0))
    G.place(collar, (-0.01, 0, 0))
    bit = G.rbox("bit", (0.012, 0.011, 0.0022), mat=brass, bevel=0.0006, segs=1, centre=True)
    G.place(bit, (0.026, -0.0065, 0))
    parts += [bow, shaft, collar, bit]
    for k, (x, d) in enumerate(((0.022, 0.004), (0.026, 0.0025), (0.03, 0.005))):
        nt = G.rbox("ward", (0.0018, d, 0.0024), mat=steel, bevel=0.0002, segs=1, centre=True)
        G.place(nt, (x, -0.012 + d / 2 - 0.0005, 0))
        parts.append(nt)
    ring = G.tube("ring", [(math.cos(a) * 0.009, math.sin(a) * 0.009, 0.0008 * math.sin(a)) for a in
                           [2 * math.pi * i / 24 for i in range(24)]], 0.0009, 6, mat=steel, closed=True)
    G.place(ring, (-0.041, 0.002, 0))
    string = G.tube("string", [(-0.048, 0.004, 0), (-0.058, 0.01, -0.001), (-0.066, 0.004, -0.0015),
                               (-0.074, 0.012, -0.0015)], 0.0011, 6, mat=cord)
    star_m = PN.plastic("kstar", "#f2c41e", rough=0.3, fade=0.4, scratch=0.6, dirt=0.4)
    star = G.extrude("star", G.star_points(5, 0.011, 0.0048, 90.0), 0.003, mat=star_m, bevel=0.0007, segs=1)
    G.place(star, (-0.08, 0.016, -0.0005))
    parts += [ring, string, star]
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("metal", (0.1, 0.03, 0.008))]}


@item("leg_band", mass=0.001, surface="metal", material_kind="metal", tags=["quest", "pigeon"], density=6144.0,
      min_tex=512)
def item_leg_band():
    """Racing-pigeon aluminium leg ring 'HM-07' with a green plastic clip band — lying on its side."""
    alu = PN.metal("band", "aluminium", dirt=0.5, wear=0.6, label=True, label_wear=0.1, dust=0.2)
    clip = PN.plastic("clip", "#2f9b52", rough=0.35, fade=0.3, scratch=0.6, dirt=0.4)
    R, H = 0.0055, 0.0075
    ring = G.lathe("ring", [(R, 0.0), (R + 0.0006, 0.0003), (R + 0.0006, H - 0.0003), (R, H), (R - 0.0004, H),
                            (R - 0.0004, 0.0)], 32, mat=alu, max_seg=0.0007)
    G.label_cyl(ring, (0.55, 0.62, 0.95, 0.85), 0.0008, H - 0.0008, a0=-math.pi / 2 - 1.3, a1=-math.pi / 2 + 1.3,
                radial_min=R + 0.0003)
    c2 = G.lathe("clip", [(R * 0.98, 0.0), (R + 0.001, 0.0), (R + 0.001, 0.004), (R * 0.98, 0.004)], 24, mat=clip)
    G.place(c2, (0, 0, 0), (0, 0, 0), (1, 1, 1))
    G.place(c2, (0.0, 0.0, -0.0048))
    parts = [ring, c2]
    for p in parts:
        G.place(p, (0, 0, 0), (90, 0, 0))
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("metal", (0.014, 0.013, 0.014))], "label": L("misc_items")}


@item("toy_mouse", mass=0.015, surface="fabric", material_kind="soft", tags=["toy", "mouth"])
def item_toy_mouse():
    """Felt toy mouse with pink ears, bead eyes, rope tail and a tiny bell — well chewed."""
    felt = PN.fabric("felt", "#8d8a86", weave_scale=1800, rough=0.95, fade=0.2, dirt=0.6, role="base", wrinkle=0.6)
    pink = PN.fabric("pink", "#e59aa8", weave_scale=1800, rough=0.9, role="base", wrinkle=0.2)
    bead = PN.glass_opaque("bead", "#121212", rough=0.05, dirt=0.0)
    rope = PN.fabric("rope", "#d8cfbd", weave_scale=2600, rough=0.9, role="base", wrinkle=0.0)
    brass = PN.metal("mbell", "brass", dirt=0.4, wear=0.5)
    prof = [(0.0, 0.0)]
    for i in range(1, 14):
        t = i / 14
        prof.append((0.016 * math.sin(math.pi * t ** 0.7) ** 0.8, t * 0.065))
    prof.append((0.0, 0.065))
    body = G.lathe("body", prof, 24, mat=felt)
    G.place(body, (-0.03, 0, 0), (0, 90, 0), (1, 1, 1))
    G.place(body, (0, 0, 0), (0, 0, 0), (1, 1, 0.8))
    G.wobble(body, 0.0012, 60, seed=5)
    # seam along the back
    seam = G.tube("seam", [(-0.028, 0, 0.012), (0.0, 0, 0.0128), (0.025, 0, 0.0075)], 0.0007, 5, mat=rope)
    parts = [body, seam]
    for s in (-1, 1):
        ear = G.cyl("ear", 0.0062 if s < 0 else 0.0032, 0.0012, segs=16, bevel=0.0003, mat=pink)
        G.place(ear, (0, 0, 0), (75, 0, s * 20 + 90))
        G.place(ear, (0.016, s * 0.008, 0.009))
        eye = G.sphere("eye", 0.0016, loc=(0.026, s * 0.0045, 0.0045), mat=bead, segs=8, rings=6)
        parts += [ear, eye]
    nose = G.sphere("nose", 0.0022, loc=(0.0352, 0, 0.0012), mat=pink, segs=8, rings=6)
    tail = G.tube("tail", [(-0.034, 0, 0.0), (-0.05, 0.006, -0.008), (-0.065, -0.004, -0.0125), (-0.08, 0.008, -0.0128),
                           (-0.088, 0.016, -0.0128)], 0.0012, 6, mat=rope)
    bell = G.sphere("bell", 0.0035, loc=(-0.088, 0.019, -0.0125), mat=brass, segs=10, rings=6)
    parts += [nose, tail, bell]
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.075, 0.032, 0.026))]}


@item("yarn", mass=0.05, surface="fabric", material_kind="soft", tags=["toy", "mouth"])
def item_yarn():
    """Ball of red wool yarn, strands wound on random great circles, loose end trailing."""
    wool = PN.fabric("wool", "#b8232a", weave_scale=1400, rough=0.95, fade=0.15, dirt=0.35, role="base", wrinkle=0.3)
    rng = random.Random(21)
    R = 0.038
    core = G.sphere("core", R - 0.0025, mat=wool, segs=24, rings=14)
    parts = [core]
    for k in range(34):
        ax = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized()
        u = ax.orthogonal().normalized()
        v = ax.cross(u)
        rr = R - 0.0008 + rng.uniform(-0.0006, 0.0006)
        pts = [tuple((u * math.cos(a) + v * math.sin(a)) * rr) for a in [2 * math.pi * i / 28 for i in range(28)]]
        parts.append(G.tube("strand", pts, 0.0016, 5, mat=wool, closed=True, twist=40.0))
    # loose end
    lo = [(R * 0.7, -R * 0.7, -R * 0.1), (R * 1.1, -R * 1.1, -R * 0.6), (R * 1.6, -R * 1.2, -R * 0.95),
          (R * 2.3, -R * 0.9, -R * 0.98), (R * 3.0, -R * 1.3, -R * 0.98)]
    parts.append(G.tube("loose", lo, 0.0016, 6, mat=wool, twist=40.0))
    for p in parts:
        G.place(p, (0, 0, R))
    G.place(parts[-1], (0, 0, 0.0))
    for v in parts[-1].data.vertices:
        v.co.z = max(v.co.z, 0.0)
    _drop(parts)
    return {"parts": parts, "colliders": [G.col_cyl("fabric", R, 2 * R, segs=10)]}


@item("silver_spoon", mass=0.025, surface="metal", material_kind="metal", tags=["mouth", "shiny"], density=3072.0)
def item_silver_spoon():
    """Small silver baby spoon (thìa bạc) with an engraved lotus handle, slightly tarnished."""
    silver = PN.metal("silver", "silver", dirt=0.6, wear=0.6, dust=0.1)
    bowl = G.sphere("bowl", 0.016, segs=24, rings=12, mat=silver, scale=(1.35, 1.0, 0.42))
    _cut_above(bowl, 1e-6)
    G.solidify(bowl, 0.0012, offset=1.0)
    G.place(bowl, (0.03, 0, 0.0075))
    handle = G.tube("handle", [(0.009, 0, 0.007), (-0.02, 0, 0.0095), (-0.05, 0, 0.0085), (-0.07, 0, 0.0065)], 0.0028,
                    10, mat=silver, rfunc=lambda t: 0.7 + 0.6 * t)
    G.place(handle, (0, 0, 0), (0, 0, 0), (1, 1, 1))
    for v in handle.data.vertices:
        v.co.z = 0.0075 + (v.co.z - 0.0075) * 0.35 + 0.0
    tip = G.sphere("lotus", 0.0055, loc=(-0.072, 0, 0.0068), mat=silver, segs=12, rings=8, scale=(1.2, 1.0, 0.45))
    parts = _drop([bowl, handle, tip])
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("metal", (0.115, 0.034, 0.014))]}


@item("hair_clip", mass=0.006, surface="plastic", material_kind="plastic", tags=["mouth", "shiny"], density=3072.0)
def item_hair_clip():
    """Metal snap hair clip set with a row of faux pearls — dropped by someone in a hurry."""
    steel = PN.metal("clipm", "chrome", dirt=0.3, wear=0.4)
    pearl = PN.ceramic("pearl", "#efe8dc", rough=0.12, crackle=0.0, chip=0.05, dirt=0.15, speckle=0.0)
    bar = G.extrude("bar", [(-0.03, 0.0), (-0.024, 0.005), (0.026, 0.004), (0.03, 0.0), (0.026, -0.004),
                            (-0.024, -0.005)], 0.0012, mat=steel, bevel=0.0004, segs=1)
    for v in bar.data.vertices:
        v.co.z += 0.0035 * (1 - (v.co.x / 0.03) ** 2)
    G.place(bar, (0, 0, 0.0006))
    parts = [bar]
    for k in range(9):
        x = -0.022 + k * 0.0055
        r = 0.0024 + 0.0008 * (1 - abs(k - 4) / 4)
        parts.append(G.sphere("pearl", r, loc=(x, 0, 0.0035 * (1 - (x / 0.03) ** 2) + 0.0012 + r * 0.8), mat=pearl,
                              segs=12, rings=8))
    _drop(parts)
    return {"parts": parts, "colliders": [G.col_box("plastic", (0.06, 0.02, 0.009))]}


@item("glass_marble", mass=0.005, surface="plastic", material_kind="glass", tags=["mouth", "shiny", "toy"],
      density=6144.0, min_tex=512)
def item_glass_marble():
    """Cat's-eye glass marble (bi ve), 16 mm: clear blue-tinted glass with a twisted coloured vane."""
    nb = PN.NB("marble", "base")
    R = 0.008
    v = nb.coords((1.0, 1.0, 1.0), offset=(0, 0, -R))
    sw = nb.wave(v, scale=55.0, dist=6.0, detail=3.0, kind="RINGS", axis="Z")
    band = nb.smooth(nb.math("ABSOLUTE", nb.sub(sw, 0.5)), 0.12, 0.02)
    clear = nb.mixc(nb.pow(nb.inv(nb.up), 1.5), "#1f5a34", "#79b88a")
    col = nb.mixc(band, clear, nb.ramp(nb.noise(scale=300, detail=2), [(0.3, "#e8e4d0"), (0.7, "#fbfaf2")]))
    st = nb.st(col, nb.madd(band, 0.12, 0.04), 0.0, nb.mul(nb.scratches(400, 0.3), -0.2))
    st = nb.weather(st, dirt=0.15, dust=0.1, ao_in_albedo=0.1)
    mat = nb.finish(st, bump=0.00015)
    ball = G.sphere("marble", R, segs=28, rings=16, mat=mat, loc=(0, 0, R))
    parts = [ball]
    return {"parts": parts, "colliders": [G.col_box("plastic", (2 * R, 2 * R, 2 * R))]}


@item("brass_bell", mass=0.012, surface="metal", material_kind="metal", tags=["mouth", "shiny", "sound"],
      density=4096.0)
def item_brass_bell():
    """Jingle bell (lục lạc) 26 mm with a cross slot and hanging loop, worn brass."""
    brass = PN.metal("bbrass", "brass", dirt=0.55, wear=0.6, dust=0.2)
    dark = PN.metal("slot", "cast_iron", dirt=0.9, wear=0.0)
    R = 0.013
    prof = [(0.0, 0.0)] + [(R * math.sin(math.pi * i / 16), R - R * math.cos(math.pi * i / 16)) for i in range(1, 16)] + [
        (0.0, 2 * R)]
    shell = G.lathe("shell", prof, 32, mat=brass)
    belt = G.lathe("belt", [(R + 0.0002, R - 0.001), (R + 0.0009, R), (R + 0.0002, R + 0.001)], 32, mat=brass)
    parts = [shell, belt]
    slot = G.rbox("slot", (0.0016, 2 * R * 0.95, R * 0.95), mat=dark, bevel=0.0003, segs=1, centre=True)
    G.place(slot, (0, 0, R * 0.55))
    for v in slot.data.vertices:
        v.co.z = R - math.sqrt(max(0.0, (R * 1.0) ** 2 - v.co.y ** 2)) + (v.co.z - R * 0.55) * 0.12 + 0.0006
    holes = [G.sphere("hole", 0.0018, loc=(s * 0.006, 0, 0.0018), mat=dark, segs=8, rings=4, scale=(1.4, 0.8, 0.4))
             for s in (-1, 1)]
    loop = G.tube("loop", [(math.cos(a) * 0.004, 0, 2 * R + 0.003 + math.sin(a) * 0.004) for a in
                           [2 * math.pi * i / 16 for i in range(16)]], 0.0011, 6, mat=brass, closed=True)
    parts += [slot, loop] + holes
    for p in parts:
        G.place(p, (0, 0, 0), (0, 80, 0))
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_cyl("metal", R, 2 * R, segs=10)]}


@item("pigeon_feather", mass=0.0005, surface="fabric", material_kind="soft", tags=["quest", "pigeon"])
def item_pigeon_feather():
    """Grey rock-pigeon wing covert with a dark bar and iridescent base; vanes split in two places."""
    vanem = PN.organic("vane", [(0.0, "#4a4e55"), (0.3, "#6d727a"), (0.75, "#9298a0"), (1.0, "#b7bcc2")], scale=30,
                       rough=0.7, detail_scale=900, h_amp=0.6, role="2s", cav_dark=0.2)
    shaft = PN.organic("rachis", [(0.0, "#cfcbc2"), (1.0, "#ebe7de")], scale=40, rough=0.45)
    Lf = 0.12
    pts = [(x * Lf, 0.0, 0.004 + 0.006 * math.sin(x * math.pi)) for x in [i / 14 for i in range(15)]]
    rach = G.tube("rachis", pts, 0.0012, 6, mat=shaft, rfunc=lambda t: 1.0 - 0.75 * t)
    parts = [rach]
    for side in (-1, 1):
        nx, ny = 22, 3
        g = G.grid("vane", 1.0, 1.0, nx, ny, mat=vanem)
        for v in g.data.vertices:
            u = v.co.x + 0.5           # 0..1 along the shaft
            w = v.co.y + 0.5           # 0..1 away from the shaft
            x = 0.012 + u * (Lf - 0.014)
            width = (0.024 if side > 0 else 0.016) * math.sin(math.pi * min(1.0, u * 0.95 + 0.05)) ** 0.6
            gap = 0.003 if (0.42 < u < 0.46 or 0.7 < u < 0.73) and w > 0.4 else 0.0
            y = side * (0.0012 + w * width) - side * gap
            z = 0.004 + 0.006 * math.sin(x / Lf * math.pi) - 0.004 * w ** 2 + 0.0008 * math.sin(u * 60 + w * 9)
            v.co = Vector((x - side * 0.004 * w, y, z))
        parts.append(g)
    down = G.grid("down", 0.014, 0.02, 4, 4, mat=vanem, fn=lambda x, y: 0.003 + 0.002 * math.sin(x * 400))
    G.place(down, (0.006, 0, 0))
    parts.append(down)
    _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.12, 0.045, 0.012))]}


@item("memory_photo", mass=0.003, surface="fabric", material_kind="soft", tags=["memory", "collectible", "paper"],
      file_id="memory_photo", density=4096.0, max_tex=1024)
def item_memory_photo():
    """Old 10 x 7.5 cm sepia snapshot (label 'memory_photo'), slightly curled; the 12 memory_XX items
    share this mesh (catalog item_id 'memory_01', others via items.json 'mesh')."""
    pap = PN.paper("photo", "#efe6cf", aged=0.5, label=True, label_wear=0.05, role="base", dirt=0.25, gloss=True)
    W, D, T = 0.1, 0.075, 0.0007
    ph = G.grid("photo", W, D, 16, 12, mat=pap,
                fn=lambda x, y: 0.0025 * (x / (W / 2)) ** 2 + 0.0012 * (y / (D / 2)) ** 2 + 0.0008 * math.sin(x * 70 + y * 30))
    G.solidify(ph, T, offset=-1.0)
    G.label_planar(ph, (0.0, 0.25, 1.0, 1.0), (-W / 2, -D / 2, 0), (1, 0, 0), (0, 1, 0), (W, D), normal=(0, 0, 1),
                   min_dot=0.5)
    G.label_planar(ph, (0.0, 0.0, 1.0, 0.25), (W / 2, -D / 2, 0), (-1, 0, 0), (0, 1, 0), (W, D), normal=(0, 0, -1),
                   min_dot=0.5)
    parts = _drop([ph])
    return {"parts": parts, "colliders": [G.col_box("fabric", (W, D, 0.005))], "label": L("memory_photo")}


# ---------------------------------------------------------------------------
# Collars (cosmetics), lying flat: band = rectangle revolved
# ---------------------------------------------------------------------------
def _collar(band_mat, buckle_mat, R=0.048, w=0.012, t=0.0022):
    band = G.lathe("band", [(R, 0.0), (R + t, 0.0), (R + t, w), (R, w)], 48, mat=band_mat, smooth_angle=50,
                   rfunc=lambda r, z, a: r * (1 + 0.04 * math.cos(a)) * (1 + 0.008 * math.sin(a * 5)))
    G.wobble(band, 0.0015, 18, seed=3)
    # stitching lines
    sts = [G.lathe("stitch", [(R + t + 0.0002, z - 0.0003), (R + t + 0.0004, z), (R + t + 0.0002, z + 0.0003)], 48,
                   mat=buckle_mat, rfunc=lambda r, z, a: r * (1 + 0.04 * math.cos(a)))
           for z in (0.002, w - 0.002)]
    buckle = G.rbox("buckle", (0.004, 0.018, w + 0.004), mat=buckle_mat, bevel=0.001, segs=2, centre=False)
    G.place(buckle, (R * 1.04 + t + 0.0015, 0, -0.002))
    dring = G.tube("dring", [(R * 1.04 + t, math.sin(a) * 0.006 - 0.0, 0.006 + math.cos(a) * 0.006) for a in
                             [math.pi * i / 10 for i in range(11)]], 0.0009, 6, mat=buckle_mat)
    G.place(dring, (-2 * R - 0.004, 0, 0))
    return [band, buckle, dring] + sts


@item("collar_red", mass=0.02, surface="fabric", material_kind="soft", tags=["cosmetic", "collar"])
def item_collar_red():
    band = PN.fabric("red_band", "#b51f2a", weave_scale=1800, rough=0.7, fade=0.25, dirt=0.3, role="base",
                     wrinkle=0.2)
    gold = PN.metal("buckle", "brass", dirt=0.3, wear=0.4)
    parts = _drop(_collar(band, gold))
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.11, 0.1, 0.016))]}


@item("collar_bell", mass=0.03, surface="fabric", material_kind="soft", tags=["cosmetic", "collar", "sound"])
def item_collar_bell():
    band = PN.fabric("blue_band", "#2b5aa8", weave_scale=1800, rough=0.7, fade=0.3, dirt=0.3, role="base",
                     stripes=None, wrinkle=0.2)
    gold = PN.metal("cbrass", "brass", dirt=0.3, wear=0.5)
    parts = _collar(band, gold)
    R = 0.012
    prof = [(0.0, 0.0)] + [(R * math.sin(math.pi * i / 12), R - R * math.cos(math.pi * i / 12)) for i in range(1, 12)] + [
        (0.0, 2 * R)]
    bell = G.lathe("bell", prof, 24, mat=gold)
    G.place(bell, (0, 0, 0), (0, 90, 0))
    G.place(bell, (-0.062 - R, 0, R))
    parts.append(bell)
    parts = _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.13, 0.1, 0.024))]}


@item("collar_jade", mass=0.02, surface="fabric", material_kind="soft", tags=["cosmetic", "collar"])
def item_collar_jade():
    """Braided red-silk cord collar with a carved jade bead (ngọc bích) and a brass bead."""
    cord = PN.fabric("silkcord", "#8c1d24", weave_scale=900, rough=0.55, fade=0.2, dirt=0.25, role="base", wrinkle=0.0)
    jade = PN.glass_opaque("jade", "#3f8a5a", rough=0.15, dirt=0.15, frost=0.4)
    brass = PN.metal("jbrass", "brass", dirt=0.3, wear=0.5)
    R = 0.05
    parts = []
    for k in range(3):
        ph = k * 2 * math.pi / 3
        pts = [(math.cos(a) * (R + 0.0012 * math.cos(a * 30 + ph)), math.sin(a) * (R + 0.0012 * math.cos(a * 30 + ph)),
                0.0025 + 0.0012 * math.sin(a * 30 + ph)) for a in [2 * math.pi * i / 120 for i in range(120)]]
        parts.append(G.tube("braid", pts, 0.0013, 6, mat=cord, closed=True))
    bead = G.sphere("jade", 0.008, loc=(-R - 0.008, 0, 0.0075), mat=jade, segs=20, rings=12, scale=(1.0, 1.0, 0.92))
    for k in (-2, -1, 1, 2):
        a = math.pi + k * 0.32
        parts.append(G.sphere("jbead", 0.0048, loc=(math.cos(a) * R, math.sin(a) * R, 0.0048), mat=jade, segs=14,
                              rings=8))
    groove = G.lathe("groove", [(0.0081, 0.0055), (0.0086, 0.0075), (0.0081, 0.0095)], 20, mat=jade)
    G.place(groove, (-R - 0.008, 0, 0))
    b2 = G.sphere("brassbead", 0.0035, loc=(-R + 0.002, 0.0, 0.0035), mat=brass, segs=12, rings=8)
    knot = G.sphere("knot", 0.0045, loc=(R, 0, 0.004), mat=cord, segs=12, rings=8, scale=(1.3, 1.0, 0.8))
    parts += [bead, groove, b2, knot]
    for s in (-1, 1):
        parts.append(G.tube("tassel", [(R + 0.003, s * 0.002, 0.003), (R + 0.02, s * 0.006, 0.0015)], 0.0012, 5,
                            mat=cord))
    parts = _drop(parts)
    _centre_xy(parts)
    return {"parts": parts, "colliders": [G.col_box("fabric", (0.13, 0.11, 0.016))]}


# ---------------------------------------------------------------------------
@item("catnip", mass=0.02, surface="fabric", material_kind="soft", tags=["consumable"], min_tex=512)
def item_catnip():
    """Little drawstring cotton pouch of dried 'bạc hà mèo' (catnip), stamped in green."""
    cloth = PN.fabric("pouch", "#e6dcc4", weave_scale=1500, rough=0.9, fade=0.1, dirt=0.4, role="base",
                      label=True, wrinkle=0.7)
    string = PN.fabric("draw", "#3f7a3a", weave_scale=2500, rough=0.85, role="base", wrinkle=0.0)
    herb = PN.organic("herb", [(0.0, "#4a5a2a"), (0.6, "#6f7d3e"), (1.0, "#8f965a")], scale=120, rough=0.8)
    H, R = 0.075, 0.03
    prof = [(0.0, 0.0), (R * 0.85, 0.0), (R, 0.012), (R * 1.02, 0.035), (R * 0.9, 0.05), (R * 0.45, 0.058),
            (R * 0.35, 0.062), (R * 0.55, 0.07), (R * 0.65, H)]
    p = G.lathe("pouch", prof, 32, mat=cloth, max_seg=0.005, rfunc=lambda r, z, a: r * (1 + (0.06 if z > 0.055 else 0.03) *
                                                                       math.sin(a * 9 + z * 30)))
    G.place(p, (0, 0, 0), (0, 0, 0), (1, 0.8, 1))
    G.wobble(p, 0.0015, 40, seed=8)
    G.label_cyl(p, (0.0, 0.0, 0.5, 0.5), 0.008, 0.05, a0=-math.pi / 2 - 1.1, a1=-math.pi / 2 + 1.1)
    neck = G.tube("draw", [(math.cos(a) * R * 0.4, math.sin(a) * R * 0.32, 0.06) for a in
                           [2 * math.pi * i / 16 for i in range(16)]], 0.0012, 5, mat=string, closed=True)
    ends = G.tube("ends", [(R * 0.35, -0.004, 0.06), (R * 0.9, -0.012, 0.045), (R * 1.1, -0.02, 0.02)], 0.0012, 5,
                  mat=string)
    top = G.lathe("herbs", [(0.0, H + 0.002), (R * 0.6, H - 0.002)], 16, mat=herb)
    parts = [p, neck, ends, top]
    return {"parts": parts, "colliders": [G.col_cyl("fabric", R, H, segs=10)], "label": L("misc_items")}


def _vial(name, glass_col, label_rect, H, R, neck_r, stopper, label_z, sheet, half_angle=1.25):
    gl = PN.glass_opaque(name, glass_col, rough=0.06, dirt=0.3, label=True, label_wear=0.15)
    prof = [(0.0, 0.0), (R * 0.9, 0.0), (R, 0.004), (R, H * 0.68), (R * 0.85, H * 0.76), (neck_r, H * 0.82),
            (neck_r, H * 0.9), (neck_r * 1.15, H * 0.92), (neck_r * 1.15, H * 0.95), (0.0, H * 0.95)]
    b = G.lathe(name, prof, 32, mat=gl, max_seg=0.008)
    G.label_cyl(b, label_rect, label_z[0], label_z[1], a0=-math.pi / 2 - half_angle,
                a1=-math.pi / 2 + half_angle)
    return b, stopper


@item("herbal_tonic", mass=0.15, surface="plastic", material_kind="glass", tags=["consumable"], min_tex=512)
def item_herbal_tonic():
    """Brown-glass bottle of 'Cao dược thảo' herbal tonic, 100 ml, screw cap with tamper ring."""
    capm = PN.metal("tcap", "aluminium", tint="#c9a650", dirt=0.3, wear=0.4)
    H, R = 0.105, 0.021
    b, _ = _vial("amber", "#5a2c0e", (0.0, 0.0, 1.0, 0.25), H, R, 0.0105, None, (0.026, 0.047), "bottles", 1.5)
    cap = G.cyl("cap", 0.0125, 0.016, segs=32, bevel=0.0012, mat=capm)
    G.place(cap, (0, 0, H * 0.93))
    ribs = G.lathe("ribs", [(0.0126, 0.0), (0.013, 0.002), (0.013, 0.011), (0.0126, 0.013)], 48, mat=capm,
                   rfunc=lambda r, z, a: r * (1 + 0.02 * math.cos(a * 24)))
    G.place(ribs, (0, 0, H * 0.93 + 0.002))
    return {"parts": [b, cap, ribs], "colliders": [G.col_cyl("plastic", R, H + 0.012, segs=10)], "label": L("bottles")}


@item("skill_tonic", mass=0.05, surface="plastic", material_kind="glass", tags=["consumable", "rare"], min_tex=512)
def item_skill_tonic():
    """'Tinh chất Cửu Mạng' — a small violet apothecary vial with a cork and wax-sealed string."""
    cork = PN.organic("cork", [(0.0, "#8a6440"), (0.5, "#b08a5e"), (1.0, "#c9a67a")], scale=200, rough=0.85,
                      detail_scale=900, h_amp=1.0, spec_spots=(300, 0.08, "#5a3e22"))
    wax = PN.plastic("wax", "#8e1a22", rough=0.35, fade=0.0, scratch=0.2, dirt=0.2, textured=0.4)
    H, R = 0.07, 0.0145
    b, _ = _vial("violet", "#4b1f63", (0.52, 0.12, 0.98, 0.38), H, R, 0.0068, None, (0.014, 0.036), "misc_items", 1.3)
    c = G.cyl("cork", 0.0068, 0.016, segs=20, bevel=0.0008, mat=cork, r2=0.0076)
    G.place(c, (0, 0, H * 0.86))
    seal = G.lathe("seal", [(0.0, H * 0.95 + 0.0105), (0.0086, H * 0.95 + 0.009), (0.0094, H * 0.95 + 0.004),
                            (0.0084, H * 0.95)], 20, mat=wax,
                   rfunc=lambda r, z, a: r * (1 + 0.08 * math.sin(a * 5) * (1 if z < H * 0.95 + 0.004 else 0.2)))
    drip = G.sphere("drip", 0.0022, loc=(0.0086, -0.003, H * 0.93), mat=wax, segs=8, rings=6, scale=(0.8, 0.8, 1.8))
    string = G.lathe("string", [(0.0072, H * 0.88), (0.0078, H * 0.885), (0.0072, H * 0.89)], 20, mat=wax)
    return {"parts": [b, c, seal, drip, string], "colliders": [G.col_cyl("plastic", R, H + 0.012, segs=10)],
            "label": L("misc_items")}
