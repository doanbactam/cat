"""Street food & stalls: xôi cart with glass case, bánh mì cart, phở pot on a stove, low plastic stools &
tables, tarp umbrella, tea set, fruit basket, flower bucket, fish basin, rice sack, bottle crate."""
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


def shell_lathe(name, outer, wall, segs, mat, rfunc=None):
    inner = [(max(0.0, r - wall), z + (wall if i == 0 else 0.0)) for i, (r, z) in enumerate(outer)]
    rim_r, rim_z = outer[-1]
    prof = [(0.0, outer[0][1])] + outer + [(rim_r - wall * 0.5, rim_z + wall * 0.15)] + inner[::-1][:-1] + \
        [(inner[0][0], inner[0][1]), (0.0, inner[0][1])]
    return G.lathe(name, prof, segs, mat=mat, rfunc=rfunc, max_seg=0.008)


def wheel(name, r, w, rub, hub, loc, axis="X", spokes=0, spoke_mat=None):
    tyre = G.lathe(name, [(r * 0.72, -w / 2), (r * 0.95, -w / 2), (r, -w * 0.3), (r, w * 0.3), (r * 0.95, w / 2),
                          (r * 0.72, w / 2), (r * 0.72, -w / 2)], 32, mat=rub)
    rim = G.lathe("rim", [(0.0, -w * 0.35), (r * 0.74, -w * 0.35), (r * 0.74, w * 0.35), (0.0, w * 0.35)], 32, mat=hub)
    parts = [tyre, rim]
    for p in parts:
        G.place(p, (0, 0, 0), (0, 90, 0) if axis == "X" else (90, 0, 0))
        G.place(p, loc)
    return parts


# ---------------------------------------------------------------------------
# Glass-case push cart (xe đẩy): steel frame on bicycle wheels, glass display case on top, skirt panel
# ---------------------------------------------------------------------------
def food_cart(kind="xoi"):
    steel = PN.metal("cart_steel", "stainless", dirt=0.6, wear=0.5, dust=0.3, ground=0.6)
    paint = PN.painted_metal("cart_paint", "#2e5d9a" if kind == "xoi" else "#c9302a", primer="#6a3a22", chip=0.5,
                             rust=0.45, gloss=0.4, streaks=0.4, dirt=0.6, dust=0.35, ground=0.7, label=True,
                             label_wear=0.25)
    rub = PN.rubber("tyre", "#1d1d1c", dirt=0.6, dust=0.4)
    wood = PN.wood("board", "#7a5232", axis="X", rings=40, weather_grey=0.3, dirt=0.6, varnish=0.1)
    food1 = PN.organic("food1", [(0.0, "#e9d8b0"), (0.5, "#f3e7c8"), (1.0, "#fbf3e2")], scale=120, rough=0.55,
                       detail_scale=600, h_amp=0.9) if kind == "xoi" else \
        PN.organic("bread", [(0.0, "#a5631f"), (0.5, "#cf8a3a"), (1.0, "#e8b56a")], scale=18, rough=0.55,
                   detail_scale=200, h_amp=0.5)
    food2 = PN.organic("food2", [(0.0, "#b8241c"), (0.5, "#d83a26"), (1.0, "#ec6a3a")], scale=120, rough=0.5,
                       detail_scale=600, h_amp=0.9) if kind == "xoi" else \
        PN.organic("cha", [(0.0, "#c79a7a"), (0.6, "#e0bfa2"), (1.0, "#efd8c2")], scale=40, rough=0.4, sss=0.2)
    food3 = PN.organic("food3", [(0.0, "#c9a84a"), (0.6, "#e0c260"), (1.0, "#efd98a")], scale=150, rough=0.6,
                       detail_scale=600, h_amp=0.9)
    alu = PN.metal("alu_tray", "aluminium", dirt=0.5, wear=0.4)
    cloth = PN.fabric("cloth", "#e7e2d4", weave_scale=1600, rough=0.9, dirt=0.6, role="2s", stripes=("#c43a34", 40.0))
    W, D = 1.1, 0.62
    deck = 0.78
    parts = []
    # chassis: tube frame
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(G.tube("leg", [(sx * (W / 2 - 0.03), sy * (D / 2 - 0.03), 0.28), (sx * (W / 2 - 0.03),
                                                                                          sy * (D / 2 - 0.03), deck)],
                                0.013, 10, mat=steel))
    for z in (0.3, deck - 0.01):
        for sy in (-1, 1):
            parts.append(G.tube("rail", [(-W / 2 + 0.03, sy * (D / 2 - 0.03), z), (W / 2 - 0.03, sy * (D / 2 - 0.03), z)],
                                0.012, 10, mat=steel))
        for sx in (-1, 1):
            parts.append(G.tube("rail", [(sx * (W / 2 - 0.03), -D / 2 + 0.03, z), (sx * (W / 2 - 0.03), D / 2 - 0.03, z)],
                                0.012, 10, mat=steel))
    shelf = G.rbox("shelf", (W - 0.06, D - 0.06, 0.018), mat=wood, bevel=0.003)
    G.place(shelf, (0, 0, 0.31))
    top = G.rbox("deck", (W + 0.02, D + 0.02, 0.025), mat=steel, bevel=0.004)
    G.place(top, (0, 0, deck))
    parts += [shelf, top]
    # skirt panel (painted sheet, printed) on the customer side (-Y)
    skirt = G.rbox("skirt", (W - 0.04, 0.008, 0.36), mat=paint, bevel=0.003)
    G.place(skirt, (0, -D / 2 + 0.01, deck - 0.4))
    G.label_planar(skirt, (0.0, 0.0, 1.0, 0.5), (-(W - 0.04) / 2, -D / 2, deck - 0.4), (1, 0, 0), (0, 0, 1),
                   (W - 0.04, 0.36), normal=(0, -1, 0), min_dot=0.7)
    parts.append(skirt)
    # wheels: two bicycle wheels at the back, a caster at the front, handle bar
    for sx in (-1, 1):
        parts += wheel("wheel", 0.28, 0.04, rub, steel, (sx * (W / 2 + 0.05), 0.0, 0.28))
        parts.append(G.tube("axle", [(sx * (W / 2 - 0.03), 0, 0.3), (sx * (W / 2 + 0.07), 0, 0.28)], 0.01, 8, mat=steel))
    for sx in (-1, 1):
        stand = G.tube("stand", [(sx * 0.3, D / 2 - 0.05, 0.3), (sx * 0.32, D / 2 - 0.05, 0.0)], 0.012, 8, mat=steel)
        foot = G.cyl("foot", 0.025, 0.012, segs=12, mat=rub)
        G.place(foot, (sx * 0.32, D / 2 - 0.05, 0.0))
        parts += [stand, foot]
    handle = G.tube("handle", [(-W / 2 + 0.05, D / 2 - 0.03, deck - 0.02), (-W / 2 + 0.05, D / 2 + 0.25, deck + 0.1),
                               (W / 2 - 0.05, D / 2 + 0.25, deck + 0.1), (W / 2 - 0.05, D / 2 - 0.03, deck - 0.02)],
                    0.014, 10, mat=steel)
    parts.append(handle)
    # glass case: aluminium frame, trays of food inside, sliding back panes
    cw, cd, ch = W - 0.12, D - 0.12, 0.42
    z0 = deck + 0.025
    frame_pts = []
    for (x, y) in ((-cw / 2, -cd / 2), (cw / 2, -cd / 2), (cw / 2, cd / 2), (-cw / 2, cd / 2)):
        parts.append(G.rbox("post", (0.02, 0.02, ch), mat=alu, bevel=0.002, loc=(x, y, z0)))
        frame_pts.append((x, y))
    for z in (z0, z0 + ch):
        for i in range(4):
            a, b = frame_pts[i], frame_pts[(i + 1) % 4]
            parts.append(G.tube("bar", [(a[0], a[1], z), (b[0], b[1], z)], 0.009, 4, mat=alu))
    roof = G.rbox("roof", (cw + 0.03, cd + 0.03, 0.012), mat=alu, bevel=0.002)
    G.place(roof, (0, 0, z0 + ch))
    parts.append(roof)
    # printed decal strip across the top front pane (red letters), modelled as a thin film on the glass
    decal = G.rbox("decal", (cw - 0.06, 0.002, 0.09), mat=paint, bevel=0.0)
    G.place(decal, (0, -cd / 2 - 0.004, z0 + ch - 0.11))
    G.label_planar(decal, (0.0, 0.5, 1.0, 1.0), (-(cw - 0.06) / 2, -cd / 2, z0 + ch - 0.11), (1, 0, 0), (0, 0, 1),
                   (cw - 0.06, 0.09), normal=(0, -1, 0), min_dot=0.7)
    parts.append(decal)
    # food trays
    rng = random.Random(8 if kind == "xoi" else 9)
    tray_specs = [(-0.28, food1), (0.0, food2), (0.28, food3)]
    for x, fm in tray_specs:
        tr = shell_lathe("tray", [(0.11, 0.0), (0.13, 0.04)], 0.002, 32, alu)
        G.place(tr, (0, 0, 0), (0, 0, 0), (1.0, 1.25, 1.0))
        G.place(tr, (x, 0.0, z0 + 0.005))
        parts.append(tr)
        if kind == "xoi":
            heap = G.lathe("heap", [(0.0, 0.08), (0.06, 0.07), (0.11, 0.045), (0.12, 0.03)], 32, mat=fm,
                           rfunc=lambda r, z, a: r * (1 + 0.05 * noise.noise(Vector((math.cos(a) * 3, math.sin(a) * 3, z * 20)))))
            G.wobble(heap, 0.006, 25, seed=int(x * 100) + 3)
            G.place(heap, (0, 0, 0), (0, 0, 0), (1.0, 1.2, 1.0))
            G.place(heap, (x, 0.0, z0 + 0.005))
            parts.append(heap)
        else:
            for k in range(5 if x < 0 else 7):
                if x < 0:     # baguettes stacked
                    b = G.sphere("baguette", 0.035, segs=16, rings=8, mat=fm, scale=(3.6, 1.0, 0.85))
                    G.place(b, (0, 0, 0), (0, 0, rng.uniform(-10, 10)))
                    G.place(b, (x + rng.uniform(-0.02, 0.02), -0.09 + k * 0.045, z0 + 0.04 + (k % 2) * 0.02))
                else:         # slices of chả / giò
                    b = G.cyl("slice", 0.035, 0.012, segs=20, bevel=0.002, mat=fm)
                    G.place(b, (0, 0, 0), (rng.uniform(50, 70), 0, rng.uniform(-20, 20)))
                    G.place(b, (x + rng.uniform(-0.05, 0.05), -0.08 + k * 0.03, z0 + 0.03))
                parts.append(b)
    # a cloth draped over the front corner & a stack of foam boxes / paper on the shelf
    cl = G.grid("cloth", 0.35, 0.25, 10, 8, mat=cloth,
                fn=lambda x, y: -0.12 * max(0.0, -y - 0.03) * 4 + 0.01 * noise.noise(Vector((x * 20, y * 20, 0))))
    G.place(cl, (cw / 2 - 0.1, -D / 2 + 0.1, deck + 0.026))
    parts.append(cl)
    glass = []
    gm = PN.glass_material("glass_case", (0.88, 0.94, 0.93), alpha=0.15, rough=0.03)
    for (sz, loc) in (((cw - 0.01, 0.006, ch - 0.01), (0, -cd / 2, z0 + 0.005)),
                      ((0.006, cd - 0.01, ch - 0.01), (-cw / 2, 0, z0 + 0.005)),
                      ((0.006, cd - 0.01, ch - 0.01), (cw / 2, 0, z0 + 0.005)),
                      ((cw - 0.01, 0.006, ch - 0.01), (0, cd / 2 - 0.006, z0 + 0.005)),
                      ((cw - 0.01, 0.006, ch - 0.01), (0, cd / 2 + 0.004, z0 + 0.005))):
        g = G.rbox("glass_pane", sz, mat=gm, bevel=0.0)
        G.place(g, loc)
        glass.append(g)
    cols = [G.col_box("metal", (W + 0.02, D + 0.02, deck + 0.025)),
            G.col_box("metal", (cw + 0.03, cd + 0.03, ch + 0.012), loc=(0, 0, z0)),
            G.col_cyl("metal", 0.28, 0.04, loc=(-W / 2 - 0.07, 0, 0.28), rot=(0, 90, 0), segs=12),
            G.col_cyl("metal", 0.28, 0.04, loc=(W / 2 + 0.03, 0, 0.28), rot=(0, 90, 0), segs=12)]
    marks = [G.marker("NAP_01", (0, 0, z0 + ch + 0.013)), G.marker("CLIMB_01", (0, -D / 2 - 0.05, deck + 0.025)),
             light_marker("LIGHT_01", (0, 0, z0 + ch - 0.03), kind="omni", range=2.5, energy=0.8,
                          color=[1.0, 0.9, 0.75], shadow=False, fade=30.0)]
    return {"parts": parts, "glass": glass, "colliders": cols, "markers": marks,
            "label": L("food_cart" if kind == "xoi" else "banh_mi_cart")}


register("food_cart_xoi", lambda: food_cart("xoi"), category="stall", kind="stall", surface="metal",
         material_kind="metal", mass=60.0, density=768.0, max_tex=2048,
         tags=["stall", "food", "cart", "standable", "nap"], night_emission=1.5, vendor="co_hoa")
register("banh_mi_cart", lambda: food_cart("banhmi"), category="stall", kind="stall", surface="metal",
         material_kind="metal", mass=60.0, density=768.0, max_tex=2048,
         tags=["stall", "food", "cart", "standable", "nap"], night_emission=1.5, vendor="chu_sau")


# ---------------------------------------------------------------------------
# Phở stall: 50 L aluminium stockpot with lid & ladle on a cast-iron charcoal stove
# ---------------------------------------------------------------------------
@prop("pho_pot_stove", category="stall", kind="stall", surface="metal", material_kind="metal", mass=25.0,
      density=1024.0, max_tex=2048, tags=["stall", "food", "hot", "smell"], night_emission=1.2)
def pho_pot_stove():
    alu = PN.metal("pot", "aluminium", dirt=0.7, wear=0.5, soot=0.6, dents=0.5, ground=0.0)
    iron = PN.metal("stove", "cast_iron", dirt=0.8, wear=0.3, soot=0.9, rust=0.4, ground=0.6)
    clay = PN.terracotta("liner", "#8a4a30", salt=0.2, moss=0.0, dirt=0.8)
    ember = PN.emissive_plain("ember", "#ff6a22", role="lit", rough=0.8)
    broth = PN.organic("broth", [(0.0, "#6a3a12"), (0.6, "#8a5420"), (1.0, "#b07a3a")], scale=8, rough=0.05,
                       detail_scale=60, h_amp=0.1, spec_spots=(30, 0.08, "#d6a85a"), dirt=0.0)
    wood = PN.wood("ladle_handle", "#6a4024", axis="Z", varnish=0.3, dirt=0.6)
    parts = []
    # stove: cylindrical cast-iron body with air door, clay liner, three pot supports
    st = shell_lathe("stove", [(0.2, 0.0), (0.21, 0.02), (0.2, 0.26), (0.22, 0.28)], 0.012, 40, iron)
    liner = G.lathe("liner", [(0.0, 0.08), (0.18, 0.08), (0.15, 0.26), (0.0, 0.2)], 32, mat=clay)
    coal = G.lathe("coals", [(0.0, 0.205), (0.14, 0.19)], 24, mat=ember,
                   rfunc=lambda r, z, a: r * (1 + 0.05 * math.sin(a * 7)))
    G.wobble(coal, 0.008, 20, seed=2)
    door = G.rbox("door", (0.14, 0.012, 0.08), mat=iron, bevel=0.003)
    G.place(door, (0, -0.205, 0.04))
    parts += [st, liner, coal, door]
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        sup = G.rbox("support", (0.06, 0.02, 0.04), mat=iron, bevel=0.004)
        G.place(sup, (0, 0, 0), (0, 0, math.degrees(a)))
        G.place(sup, (math.cos(a) * 0.17, math.sin(a) * 0.17, 0.28))
        parts.append(sup)
    # pot
    zp = 0.32
    pot = shell_lathe("pot", [(0.22, 0.0), (0.235, 0.012), (0.24, 0.42), (0.245, 0.43)], 0.004, 56, alu)
    G.place(pot, (0, 0, zp))
    G.dent(pot, (0.17, -0.17, zp + 0.25), 0.07, 0.005, direction=(-1, 1, 0))
    G.dent(pot, (-0.2, 0.12, zp + 0.1), 0.06, 0.004, direction=(1, -0.6, 0))
    surface = G.lathe("broth", [(0.0, zp + 0.37), (0.236, zp + 0.37)], 40, mat=broth)
    parts += [pot, surface]
    for s in (-1, 1):
        parts.append(G.tube("handle", [(s * 0.235, -0.05, zp + 0.36), (s * 0.28, -0.04, zp + 0.37),
                                       (s * 0.28, 0.04, zp + 0.37), (s * 0.235, 0.05, zp + 0.36)], 0.009, 8, mat=alu))
    # lid pushed back on the rim (pot ~60 % covered) so the ladle can go in; sooty, dull from years of use
    lid_m = PN.metal("lid", "aluminium", dirt=0.9, wear=0.7, soot=0.9, dents=0.7, ground=0.0)
    lid = G.lathe("lid", [(0.0, 0.04), (0.06, 0.037), (0.2, 0.014), (0.248, 0.004), (0.252, 0.0), (0.244, 0.0),
                          (0.2, 0.01), (0.06, 0.033), (0.0, 0.036)], 48, mat=lid_m)
    knob = G.lathe("knob", [(0.0, 0.036), (0.016, 0.036), (0.013, 0.05), (0.03, 0.058), (0.03, 0.068),
                            (0.0, 0.07)], 16, mat=wood)
    G.dent(lid, (0.12, 0.1, 0.03), 0.05, 0.003, direction=(0, 0, -1))
    for p in (lid, knob):
        G.place(p, (0, 0, 0), (-1.5, 0, 0))
        G.place(p, (0.0, 0.165, zp + 0.434))
    ladle_bowl = shell_lathe("ladle", [(0.03, 0.0), (0.045, 0.03)], 0.002, 20, alu)
    G.place(ladle_bowl, (0.1, -0.08, zp + 0.33))
    lh = G.tube("ladle_h", [(0.14, -0.08, zp + 0.36), (0.2, -0.12, zp + 0.55), (0.24, -0.14, zp + 0.72)], 0.008, 8,
                mat=wood)
    parts += [lid, knob, ladle_bowl, lh]
    for p in parts:
        G.uv_weight(p, 1.0)
    cols = [G.col_cyl("metal", 0.22, 0.32, segs=12), G.col_cyl("metal", 0.245, 0.43, loc=(0, 0, zp), segs=14)]
    marks = [light_marker("LIGHT_01", (0, -0.25, 0.08), kind="omni", range=1.6, energy=0.6, color=[1.0, 0.45, 0.2],
                          shadow=False, fade=20.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "meta": {"hot": True, "steam_point":
                                                                          [0.0, 0.8, 0.0]}}


# ---------------------------------------------------------------------------
# Low plastic stool (ghế nhựa đỏ) & low table
# ---------------------------------------------------------------------------
def stool(color):
    pl = PN.plastic("stool", color, rough=0.4, fade=0.55, scratch=0.8, dirt=0.6, dust=0.35, ground=0.6,
                    textured=0.4, stress=0.6)
    H, Wt, Wb = 0.26, 0.27, 0.31
    parts = []
    # seat with drain holes pattern (raised ring), rounded square
    seat = G.extrude("seat", G.rounded_rect(Wt, Wt, 0.03, 4), 0.018, mat=pl, bevel=0.004, segs=2, centre=False)
    G.place(seat, (0, 0, H - 0.018))
    for i in range(-2, 3):
        for j in range(-2, 3):
            if abs(i) == 2 and abs(j) == 2:
                continue
            hole = G.cyl("dimple", 0.008, 0.002, segs=10, bevel=0.0, mat=pl)
            G.place(hole, (i * 0.045, j * 0.045, H - 0.0005))
            parts.append(hole)
    # skirt: frustum with 4 arched leg cut-outs (built as 4 leg panels + corner columns)
    for k in range(4):
        rot = k * 90
        panel = G.grid("panel", Wt - 0.04, 0.06, 8, 2, mat=pl)
        G.place(panel, (0, 0, 0), (90, 0, 0))
        G.place(panel, (0, 0, H - 0.05))
        # arched lower edge panel (from z 0.06 to H - 0.08) as a thin extrusion
        arch = [(-(Wb - 0.08) / 2, 0.0)]
        for i in range(13):
            t = i / 12
            x = -(Wb - 0.12) / 2 + (Wb - 0.12) * t
            arch.append((x * (1 - 0.0), 0.12 + 0.05 * math.sin(math.pi * t)))
        arch.append(((Wb - 0.08) / 2, 0.0))
        arch = arch + [((Wt - 0.04) / 2, H - 0.06), (-(Wt - 0.04) / 2, H - 0.06)]
        side = G.extrude("side", [(x, z) for (x, z) in [arch[0]] + arch[1:-2] + [arch[-2]] + [arch[-1]]], 0.006,
                         mat=pl, bevel=0.0015, segs=1)
        G.place(side, (0, 0, 0), (90, 0, 0))
        G.place(side, (0, -(Wb + Wt) / 4 + 0.0, 0.0))
        # lean the side panel inwards (frustum)
        for v in side.data.vertices:
            v.co.y += (v.co.z / H) * (Wb - Wt) / 2
        G.place(side, (0, 0, 0), (0, 0, rot))
        G.place(panel, (0, -Wt / 2 + 0.004, 0))
        G.place(panel, (0, 0, 0), (0, 0, rot))
        parts += [side, panel]
    for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        col = G.tube("corner", [(sx * (Wb / 2 - 0.02), sy * (Wb / 2 - 0.02), 0.0),
                                (sx * (Wt / 2 - 0.02), sy * (Wt / 2 - 0.02), H - 0.01)], 0.016, 10, mat=pl)
        parts.append(col)
    G.wobble(seat, 0.0015, 6, seed=2)
    parts.append(seat)
    cols = [G.col_box("plastic", (Wt, Wt, H))]
    marks = [G.marker("SIT_01", (0, 0, H)), G.marker("NAP_01", (0, 0, H))]
    return {"parts": parts, "colliders": cols, "markers": marks}


for _n, _c in (("red", "#c8282a"), ("blue", "#2457a8"), ("green", "#2f8a4a")):
    register(f"stool_plastic_{_n}", (lambda c=_c: stool(c)), category="furniture", kind="furniture", dynamic=True,
             surface="plastic", material_kind="plastic", mass=0.6, density=1024.0, max_tex=1024,
             tags=["stool", "sit", "knockable", "stall", "standable"], name_key="PROP_STOOL_PLASTIC")


@prop("table_plastic_low", category="furniture", kind="furniture", surface="plastic", material_kind="plastic",
      mass=2.5, density=1024.0, max_tex=2048, tags=["table", "stall", "standable", "nap"])
def table_plastic_low():
    """Low blue plastic street-food table (bàn nhựa thấp), 60 x 60 x 45 cm, chopstick holder & napkins."""
    pl = PN.plastic("table", "#2a63ad", rough=0.42, fade=0.6, scratch=0.9, dirt=0.6, dust=0.35, ground=0.6,
                    textured=0.3, stress=0.5)
    holder = PN.plastic("holder", "#e9e4d6", rough=0.35, fade=0.2, scratch=0.5, dirt=0.5)
    bam = PN.bamboo("chopsticks", "#d9bf8a", axis="Z", node_spacing=1.0, dirt=0.2)
    tissue = PN.paper("napkin", "#f1ede2", aged=0.1, label=False, role="2s")
    chili = PN.plastic("chili_jar", "#d23a20", rough=0.2, fade=0.0, scratch=0.3, dirt=0.4)
    S, H = 0.6, 0.45
    top = G.extrude("top", G.rounded_rect(S, S, 0.04, 4), 0.025, mat=pl, bevel=0.005, segs=2, centre=False)
    G.place(top, (0, 0, H - 0.025))
    lip = G.extrude("lip", G.rounded_rect(S - 0.02, S - 0.02, 0.035, 4), 0.05, mat=pl, bevel=0.003, segs=1,
                    centre=False)
    G.place(lip, (0, 0, H - 0.07))
    parts = [top, lip]
    for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        leg = G.extrude("leg", [(-0.025, -0.025), (0.025, -0.025), (0.025, 0.025), (-0.025, 0.025)], H - 0.06,
                        mat=pl, bevel=0.006, segs=2, centre=False)
        G.place(leg, (0, 0, 0), (sx * 3, -sy * 3, 0))
        G.place(leg, (sx * (S / 2 - 0.06), sy * (S / 2 - 0.06), 0))
        ft = G.cyl("foot", 0.028, 0.01, segs=12, bevel=0.002, mat=pl)
        G.place(ft, (sx * (S / 2 - 0.06), sy * (S / 2 - 0.06), 0))
        parts += [leg, ft]
    # chopstick holder with chopsticks, tissue box, chili jar
    hd = shell_lathe("holder", [(0.03, 0.0), (0.033, 0.13)], 0.003, 20, holder)
    G.place(hd, (0.15, 0.12, H))
    parts.append(hd)
    rng = random.Random(4)
    for k in range(10):
        a, r = rng.uniform(0, 6.28), rng.uniform(0, 0.02)
        x, y = 0.15 + math.cos(a) * r, 0.12 + math.sin(a) * r
        parts.append(G.tube("chopstick", [(x, y, H + 0.004), (x + rng.uniform(-0.02, 0.02), y + rng.uniform(-0.02, 0.02),
                                                              H + 0.24)], 0.0035, 5, mat=bam,
                            rfunc=lambda t: 1.0 - 0.4 * t))
    box = G.rbox("tissuebox", (0.13, 0.08, 0.07), mat=holder, bevel=0.006, loc=(-0.12, 0.15, H))
    nap = G.grid("napkin", 0.06, 0.05, 3, 3, mat=tissue, fn=lambda x, y: 0.02 * (1 - abs(x) / 0.03))
    G.place(nap, (0, 0, 0), (90, 0, 10))
    G.place(nap, (-0.12, 0.15, H + 0.09))
    jar = G.lathe("jar", [(0.0, 0.0), (0.03, 0.0), (0.032, 0.06), (0.02, 0.07), (0.022, 0.08), (0.0, 0.08)], 20,
                  mat=chili)
    G.place(jar, (0.05, 0.2, H))
    parts += [box, nap, jar]
    cols = [G.col_box("plastic", (S, S, 0.07), loc=(0, 0, H - 0.07))] + \
        [G.col_box("plastic", (0.05, 0.05, H - 0.07), loc=(sx * (S / 2 - 0.06), sy * (S / 2 - 0.06), 0))
         for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    marks = [G.marker("NAP_01", (-0.1, -0.1, H)), G.marker("SIT_01", (-0.1, -0.1, H))]
    return {"parts": parts, "colliders": cols, "markers": marks}


# ---------------------------------------------------------------------------
# Tarp umbrella: big square vendor umbrella (dù bạt), faded stripes, on a tyre-rim concrete base
# ---------------------------------------------------------------------------
@prop("umbrella_tarp", category="stall", kind="stall", surface="fabric", material_kind="soft", mass=18.0,
      density=512.0, max_tex=2048, tags=["stall", "shelter", "shade"])
def umbrella_tarp():
    tarp = PN.fabric("tarp", "#2a6fb5", weave_scale=500, rough=0.75, fade=0.8, dirt=0.6, dust=0.5, role="2s",
                     stripes=("#e9e2cc", 2.2), wrinkle=0.6)
    steel = PN.painted_metal("upole", "#d9d6cc", primer="#7a3b22", chip=0.6, rust=0.6, gloss=0.3, streaks=0.6,
                             dirt=0.6, ground=0.6)
    conc = PN.concrete("ubase", "#8f8a80", stains=0.6, moss=0.1, dirt=0.7, ground=0.7)
    rub = PN.rubber("rim_tyre", "#1d1d1c", dirt=0.6, dust=0.5)
    H, R = 2.35, 1.25
    parts = []
    base = G.cyl("base", 0.26, 0.12, segs=32, bevel=0.01, mat=conc)
    tyre = G.lathe("tyre", [(0.26, 0.0), (0.3, 0.02), (0.31, 0.06), (0.3, 0.1), (0.26, 0.12)], 32, mat=rub)
    pole = G.tube("pole", [(0, 0, 0.1), (0, 0, H + 0.08)], 0.019, 12, mat=steel)
    parts += [base, tyre, pole]
    # canopy: square pyramid, 8 ribs, sagging between ribs, scalloped valance
    n = 8
    canopy = G.grid("canopy", 2 * R, 2 * R, 24, 24, mat=tarp)
    for v in canopy.data.vertices:
        x, y = v.co.x, v.co.y
        a = math.atan2(y, x)
        r = math.hypot(x, y)
        # radial distance to the octagon edge
        a8 = (a + math.pi / n) % (2 * math.pi / n) - math.pi / n
        redge = R * math.cos(math.pi / n) / math.cos(a8)
        k = min(1.0, r / redge)
        sag = 0.06 * math.sin(math.pi * k) * (1 - math.cos(a8 * n)) * 0.5
        z = H - 0.45 * k ** 1.15 - sag
        v.co = Vector((x / max(r, 1e-6) * k * redge if r > 1e-6 else 0.0,
                       y / max(r, 1e-6) * k * redge if r > 1e-6 else 0.0, z))
    parts.append(canopy)
    for i in range(n):
        a = 2 * math.pi * i / n
        rib = G.tube("rib", [(math.cos(a) * 0.03, math.sin(a) * 0.03, H - 0.005),
                             (math.cos(a) * R * 0.5, math.sin(a) * R * 0.5, H - 0.235 - 0.006),
                             (math.cos(a) * R * 1.0, math.sin(a) * R * 1.0, H - 0.452)], 0.006, 6, mat=steel)
        strut = G.tube("strut", [(0, 0, H - 0.5), (math.cos(a) * R * 0.45, math.sin(a) * R * 0.45, H - 0.22)], 0.005, 6,
                       mat=steel)
        parts += [rib, strut]
    hub = G.cyl("hub", 0.035, 0.06, segs=16, bevel=0.004, mat=steel)
    G.place(hub, (0, 0, H - 0.53))
    cap = G.lathe("cap", [(0.0, H + 0.08), (0.05, H), (0.0, H - 0.01)], 16, mat=tarp)
    parts += [hub, cap]
    # valance
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0 = Vector((math.cos(a0) * R, math.sin(a0) * R, H - 0.452))
        p1 = Vector((math.cos(a1) * R, math.sin(a1) * R, H - 0.452))
        val = G.grid("valance", 1.0, 1.0, 8, 2, mat=tarp)
        for v in val.data.vertices:
            t = v.co.x + 0.5
            h = v.co.y + 0.5
            p = p0.lerp(p1, t)
            drop = 0.16 + 0.05 * math.sin(math.pi * t)
            v.co = Vector((p.x, p.y, p.z - h * drop * (1 if h < 0.99 else 1)))
        parts.append(val)
    for p in parts:
        G.uv_weight(p, 1.0)
    G.uv_weight(pole, 0.5)
    cols = [G.col_cyl("concrete", 0.3, 0.12, segs=12), G.col_cyl("metal", 0.02, H, loc=(0, 0, 0.12), segs=8)]
    return {"parts": parts, "colliders": cols, "meta": {"shelter_radius": R}}


# ---------------------------------------------------------------------------
# Tea set (trà đá / trà nóng corner): dented aluminium kettle, green-crackle cups, plastic tray
# ---------------------------------------------------------------------------
@prop("tea_set", category="stall", kind="stall", dynamic=True, surface="metal", material_kind="metal", mass=1.8,
      density=1536.0, max_tex=1024, tags=["stall", "tea", "knockable", "table"])
def tea_set():
    alu = PN.metal("kettle", "aluminium", dirt=0.7, wear=0.5, soot=0.5, dents=0.6)
    cup = PN.ceramic("teacup", "#8fb39a", rough=0.08, crackle=0.7, chip=0.35, label=True, label_wear=0.05, dirt=0.3)
    tray = PN.plastic("ttray", "#b8352c", rough=0.35, fade=0.5, scratch=0.9, dirt=0.6)
    tea = PN.organic("tea", [(0.0, "#6a3a10"), (1.0, "#a2671f")], scale=10, rough=0.05, h_amp=0.0, dirt=0.0)
    parts = []
    tr = shell_lathe("tray", [(0.17, 0.0), (0.18, 0.015)], 0.003, 40, tray)
    G.place(tr, (0, 0, 0), (0, 0, 0), (1.25, 1.0, 1.0))
    parts.append(tr)
    # kettle
    kp = [(0.0, 0.0), (0.075, 0.0), (0.085, 0.01), (0.09, 0.05), (0.085, 0.09), (0.06, 0.115), (0.04, 0.12),
          (0.042, 0.13), (0.0, 0.135)]
    k = G.lathe("kettle", kp, 40, mat=alu)
    G.place(k, (-0.07, 0.02, 0.004))
    G.dent(k, (-0.07 + 0.06, 0.02 - 0.06, 0.06), 0.03, 0.006)
    spout = G.tube("spout", [(-0.0, 0.02, 0.04), (0.05, 0.02, 0.08), (0.075, 0.02, 0.125)], 0.011, 10, mat=alu,
                   rfunc=lambda t: 1.0 - 0.5 * t)
    knob = G.sphere("knob", 0.012, loc=(-0.07, 0.02, 0.145), mat=alu, segs=12, rings=6)
    hand = G.tube("bail", [(-0.07 + math.cos(a) * 0.075, 0.02, 0.12 + math.sin(a) * 0.08) for a in
                           [math.pi * i / 12 for i in range(13)]], 0.004, 6, mat=alu)
    parts += [k, spout, knob, hand]
    # four small cups, one with tea, one upside-down
    for i, (x, y, flip) in enumerate(((0.09, -0.06, False), (0.13, 0.04, False), (0.05, 0.08, True),
                                      (-0.02, -0.09, False))):
        c = shell_lathe("cup", [(0.02, 0.0), (0.024, 0.006), (0.033, 0.05)], 0.0025, 24, cup)
        if flip:
            G.place(c, (0, 0, 0), (180, 0, 0))
            G.place(c, (0, 0, 0.05))
        G.label_cyl(c, (0.0, 0.0, 1.0, 0.5), 0.0, 0.05, a0=-math.pi, a1=math.pi, radial_min=0.02)
        G.place(c, (x, y, 0.004))
        parts.append(c)
        if not flip and i != 3:
            parts.append(G.lathe("tea", [(0.0, 0.035), (0.029, 0.035)], 16, mat=tea, loc=(x, y, 0.004)))
    cols = [G.col_box("metal", (0.45, 0.36, 0.02)), G.col_cyl("metal", 0.09, 0.14, loc=(-0.07, 0.02, 0.0), segs=10)]
    return {"parts": parts, "colliders": cols, "label": L("ceramic_patterns")}


# ---------------------------------------------------------------------------
# Fruit basket (bamboo) with mangoes, dragon fruit, bananas, rambutans
# ---------------------------------------------------------------------------
@prop("fruit_basket", category="stall", kind="stall", surface="wood", material_kind="wood", mass=6.0,
      density=1024.0, max_tex=2048, tags=["stall", "food", "market"])
def fruit_basket():
    wv = PN.weave("basket", "#b48b52", scale=60, dirt=0.5, dust=0.3, rough=0.65, gap=0.3)
    rimm = PN.bamboo("brim", "#a77e46", axis="Z", node_spacing=1.0, dirt=0.5, aged=0.5)
    mango = PN.organic("mango", [(0.0, "#c99a1a"), (0.45, "#e8b62a"), (0.8, "#f0c843"), (1.0, "#a6ad38")], scale=8,
                       rough=0.35, detail_scale=400, h_amp=0.15, spec_spots=(80, 0.04, "#7a6a2a"), sss=0.1)
    drag = PN.organic("dragon", [(0.0, "#b8124f"), (0.5, "#d81f6a"), (1.0, "#e85a8f")], scale=6, rough=0.3,
                      detail_scale=200, h_amp=0.2)
    bract = PN.leaf("bract", "#7fae3a", vein="#c8d870", rough=0.35, role="2s", edge_col="#d8346e")
    banana = PN.organic("banana", [(0.0, "#b89a1e"), (0.5, "#e2c43a"), (1.0, "#f0d860")], scale=10, rough=0.4,
                        detail_scale=200, h_amp=0.2, spec_spots=(30, 0.05, "#5a3e18"))
    ramb = PN.organic("rambutan", [(0.0, "#8a1414"), (0.6, "#c42a1c"), (1.0, "#d86a2a")], scale=20, rough=0.6,
                      detail_scale=300, h_amp=0.8)
    leafm = PN.leaf("bleaf", "#4f7a2c", vein="#86a858", rough=0.4, role="2s")
    R, H = 0.3, 0.12
    parts = [shell_lathe("basket", [(0.2, 0.0), (0.24, 0.02), (0.3, 0.12)], 0.006, 48, wv)]
    parts.append(G.lathe("rim", [(R - 0.004, H - 0.008), (R + 0.012, H), (R - 0.004, H + 0.012)], 48, mat=rimm))
    # banana leaf liner
    liner = G.grid("liner", 0.6, 0.6, 12, 12, mat=leafm,
                   fn=lambda x, y: 0.02 + 0.6 * (x * x + y * y) + 0.004 * math.sin(x * 40))
    for v in liner.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        if r > R * 0.98:
            k = R * 0.98 / r
            v.co.x *= k
            v.co.y *= k
            v.co.z = min(v.co.z, H)
    parts.append(liner)
    rng = random.Random(12)
    zb = 0.045
    # mangoes (pile), dragon fruits, a hand of bananas, rambutans
    for k in range(7):
        a = k * 0.9 + rng.uniform(-0.2, 0.2)
        r = 0.1 + 0.05 * (k % 2)
        m = G.sphere("mango", 0.045, segs=20, rings=12, mat=mango, scale=(1.35, 0.95, 0.85))
        for v in m.data.vertices:
            if v.co.x > 0:
                v.co.z -= 0.25 * v.co.x ** 2 / 0.06 * 0.6
        G.place(m, (0, 0, 0), (rng.uniform(-10, 10), rng.uniform(-10, 10), math.degrees(a) + 90))
        G.place(m, (math.cos(a) * r - 0.06, math.sin(a) * r * 0.9, zb + 0.035 + 0.03 * (k > 4)))
        parts.append(m)
    for k in range(2):
        cx, cy = 0.12 + k * 0.04, -0.08 + k * 0.13
        df = G.sphere("dragon", 0.05, segs=18, rings=12, mat=drag, scale=(1.35, 1.0, 1.0))
        G.place(df, (0, 0, 0), (0, 0, 40 * k))
        G.place(df, (cx, cy, zb + 0.05))
        parts.append(df)
        for j in range(12):
            a = j * 2.4
            fz = (j % 4) / 4.0
            br = G.grid("bract", 0.035, 0.016, 3, 1, mat=bract, fn=lambda x, y: 4 * (x + 0.0175) ** 2)
            for v in br.data.vertices:
                f = 1 - abs(v.co.y) / 0.008 * (v.co.x + 0.0175) / 0.035
                v.co.y *= max(0.05, f)
            G.place(br, (0.015, 0, 0))
            G.place(br, (0, 0, 0), (0, -30, math.degrees(a)))
            G.place(br, (cx + math.cos(a) * 0.035, cy + math.sin(a) * 0.035, zb + 0.03 + fz * 0.05))
            parts.append(br)
    for k in range(5):
        pts = [(0.0, -0.12 + k * 0.022, zb + 0.09), (0.06, -0.13 + k * 0.025, zb + 0.105),
               (0.14, -0.12 + k * 0.03, zb + 0.1), (0.2, -0.1 + k * 0.035, zb + 0.08)]
        parts.append(G.tube("banana", pts, 0.017, 6, mat=banana, rfunc=lambda t: 0.35 + 0.9 * math.sin(math.pi * min(1, 0.1 + t)) ** 0.5))
    parts.append(G.tube("bstem", [(-0.02, -0.08, zb + 0.09), (-0.05, -0.08, zb + 0.1)], 0.012, 6, mat=banana))
    for k in range(9):
        a, r = rng.uniform(0, 6.28), rng.uniform(0.18, 0.24)
        rb = G.sphere("rambutan", 0.022, segs=12, rings=8, mat=ramb, loc=(math.cos(a) * r, math.sin(a) * r, zb + 0.06),
                      scale=(1.0, 1.0, 0.92))
        parts.append(rb)
        for h in range(10):
            d = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.2, 1))).normalized()
            base = Vector((math.cos(a) * r, math.sin(a) * r, zb + 0.06)) + d * 0.02
            parts.append(G.tube("hair", [tuple(base), tuple(base + d * 0.012 + Vector((0, 0, 0.004)))], 0.0012, 3,
                                mat=ramb, cap=False, rfunc=lambda t: 1.0 - 0.7 * t))
    cols = [G.col_cyl("wood", R, H, segs=12), G.col_cyl("fabric", R * 0.8, 0.08, loc=(0, 0, H), segs=10)]
    return {"parts": parts, "colliders": cols, "meta": {"sells": ["mango", "dragon_fruit", "banana", "rambutan"]}}


# ---------------------------------------------------------------------------
# Flower bucket: galvanized bucket of water with chrysanthemums, roses and gladioli wrapped in newspaper
# ---------------------------------------------------------------------------
@prop("flower_bucket", category="stall", kind="stall", surface="metal", material_kind="metal", mass=8.0,
      density=1024.0, max_tex=2048, tags=["stall", "flowers", "market"])
def flower_bucket():
    zinc = PN.metal("fbucket", "galvanized", dirt=0.6, wear=0.4, rust=0.3, dents=0.4, ground=0.5)
    water = PN.organic("fwater", [(0.0, "#2a3a30"), (1.0, "#4a5a48")], scale=6, rough=0.04, h_amp=0.0, dirt=0.0)
    stem = PN.organic("fstem", [(0.0, "#2f5a1c"), (1.0, "#5e8a3a")], scale=40, rough=0.5)
    leafm = PN.leaf("fleaf", "#3e6a28", vein="#78a050", rough=0.45, role="2s", spots=0.2)
    rose = PN.organic("rose", [(0.0, "#7a0e1c"), (0.5, "#b0182a"), (1.0, "#d8384a")], scale=40, rough=0.55, role="2s",
                      sss=0.2)
    mum = PN.organic("mum", [(0.0, "#d8c8a0"), (0.6, "#f0ead8"), (1.0, "#fbf8f0")], scale=60, rough=0.6, role="2s",
                     sss=0.2)
    glad = PN.organic("glad", [(0.0, "#d8401a"), (0.6, "#f06a2a"), (1.0, "#f89a5a")], scale=50, rough=0.55, role="2s")
    news = PN.paper("news", "#d9d2bf", aged=0.5, label=False, role="2s", rough=0.8, fibre=0.8)
    H = 0.32
    parts = [shell_lathe("bucket", [(0.13, 0.0), (0.135, 0.01), (0.16, H - 0.01), (0.165, H)], 0.002, 48, zinc)]
    for z in (0.08, 0.2):
        r = 0.13 + 0.03 * z / H
        parts.append(G.lathe("rib", [(r, z - 0.006), (r + 0.004, z), (r, z + 0.006)], 48, mat=zinc))
    for s in (-1, 1):
        parts.append(G.tube("handle", [(s * 0.165, 0, H - 0.03), (s * 0.12, 0, H + 0.08), (0, 0, H + 0.11)][:: s], 0.003,
                            6, mat=zinc))
    parts.append(G.lathe("water", [(0.0, H * 0.7), (0.157, H * 0.7)], 32, mat=water))
    rng = random.Random(31)

    def bloom(center, kind):
        out = []
        if kind == "rose":
            for ring in range(4):
                for i in range(5 + ring * 2):
                    a = 2 * math.pi * i / (5 + ring * 2) + ring
                    pt = G.grid("rpetal", 0.03 + ring * 0.006, 0.026 + ring * 0.006, 3, 3, mat=rose,
                                fn=lambda x, y: 18 * (x * x) - 6 * y * y)
                    G.place(pt, (0.006 + ring * 0.006, 0, 0.0))
                    G.place(pt, (0, 0, 0), (0, -(80 - ring * 18), math.degrees(a)))
                    G.place(pt, tuple(center))
                    out.append(pt)
        elif kind == "mum":
            for ring in range(4):
                n = 12 + ring * 4
                for i in range(n):
                    a = 2 * math.pi * i / n + ring * 0.4
                    pt = G.grid("mpetal", 0.025 + ring * 0.004, 0.006, 3, 1, mat=mum, fn=lambda x, y: 6 * (x + 0.012) ** 2)
                    G.place(pt, (0.006 + ring * 0.003, 0, 0))
                    G.place(pt, (0, 0, 0), (0, -(70 - ring * 20), math.degrees(a)))
                    G.place(pt, tuple(center))
                    out.append(pt)
        return out
    heads = []
    for k in range(14):
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.0, 0.11)
        top = Vector((math.cos(a) * (r + 0.05), math.sin(a) * (r + 0.05), H + 0.25 + rng.uniform(-0.05, 0.12)))
        base = Vector((math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, 0.05))
        parts.append(G.tube("stem", [tuple(base), tuple(base.lerp(top, 0.6) + Vector((0, 0, 0.0))), tuple(top)], 0.004, 5,
                            mat=stem))
        kind = "rose" if k % 3 == 0 else ("mum" if k % 3 == 1 else "glad")
        if kind == "glad":
            for j in range(7):
                p = base.lerp(top, 0.65 + 0.06 * j) + Vector((0, 0, 0.03 * j))
                fl = G.sphere("glad", 0.018 - j * 0.0015, loc=tuple(p), mat=glad, segs=10, rings=6, scale=(1.2, 1.0, 0.7))
                parts.append(fl)
        else:
            heads += bloom(top, kind)
        for j in range(2):
            lf = G.grid("leaf", 0.09, 0.03, 6, 2, mat=leafm, fn=lambda x, y: -3 * x * x + 20 * y * y)
            for v in lf.data.vertices:
                f = max(0.0, 1 - (abs(v.co.x) / 0.045) ** 2)
                v.co.y *= max(0.1, f ** 0.5)
            G.place(lf, (0.045, 0, 0))
            p = base.lerp(top, 0.45 + 0.2 * j)
            G.place(lf, (0, 0, 0), (rng.uniform(-30, 0), -20, math.degrees(a) + rng.uniform(-60, 60)))
            G.place(lf, tuple(p))
            parts.append(lf)
    parts += heads
    # newspaper cone wrapping one bunch
    cone = G.lathe("news", [(0.03, H - 0.02), (0.12, H + 0.22)], 24, mat=news,
                   rfunc=lambda r, z, a: r * (1 + 0.1 * math.sin(a * 3)) if math.cos(a) > -0.6 else r * 0.2)
    G.place(cone, (0.05, 0.04, 0))
    parts.append(cone)
    cols = [G.col_cyl("metal", 0.165, H, segs=12)]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Fish basin: big plastic basin of water with live fish, aerator tube, at a wet-market stall
# ---------------------------------------------------------------------------
@prop("fish_basin", category="stall", kind="stall", surface="plastic", material_kind="plastic", mass=30.0,
      density=1024.0, max_tex=2048, tags=["stall", "fish", "market", "water", "cat_interest"])
def fish_basin():
    pl = PN.plastic("fbasin", "#d63c2a", rough=0.4, fade=0.6, scratch=0.9, dirt=0.7, dust=0.2, ground=0.8)
    water = PN.organic("bwater", [(0.0, "#1e2e2a"), (0.6, "#2c4038"), (1.0, "#3e544a")], scale=5, rough=0.03,
                       h_amp=0.05, dirt=0.0, detail_scale=40)
    hose = PN.plastic("hose", "#c9d6d0", rough=0.3, fade=0.1, scratch=0.3, dirt=0.4)
    stone = PN.organic("airstone", [(0.0, "#9a9a92"), (1.0, "#c9c6bc")], scale=80, rough=0.9)
    R, H = 0.38, 0.2
    basin = shell_lathe("basin", [(0.3, 0.0), (0.31, 0.012), (0.37, H - 0.015), (0.385, H)], 0.005, 56, pl)
    lip = G.lathe("lip", [(R - 0.002, H - 0.004), (R + 0.022, H - 0.002), (R + 0.022, H + 0.006), (R - 0.004, H + 0.008)],
                  56, mat=pl)
    # murky basin floor (baked) + transparent water surface (glass) so the fish read through it
    floor = G.lathe("floor", [(0.0, 0.0065), (0.3, 0.0065)], 40, mat=water)
    wl = G.grid("glass_water", 0.74, 0.74, 24, 24, mat=PN.glass_material("glass_water", (0.55, 0.66, 0.58),
                                                                         alpha=0.32, rough=0.02),
                fn=lambda x, y: 0.0015 * math.sin(x * 40) * math.cos(y * 35))
    for v in wl.data.vertices:
        r = math.hypot(v.co.x, v.co.y)
        if r > 0.364:
            v.co.x *= 0.364 / r
            v.co.y *= 0.364 / r
    G.place(wl, (0, 0, H - 0.05))
    parts = [basin, lip, floor]
    rng = random.Random(77)
    zf = H - 0.075
    for k in range(5):
        Lf = rng.uniform(0.2, 0.28)
        skin = PN.fish_skin(f"carp{k}", back="#3a3a2a" if k % 2 else "#4a4a3a", belly="#cfc8a8", dorsal="Z",
                            centre=zf, span=2.2, wet=True)
        prof = []
        for i in range(17):
            t = i / 16
            prof.append((Lf * 0.13 * math.sin(math.pi * min(1.0, 0.05 + t * 1.0)) ** 0.7, t * Lf))
        body = G.lathe("fish", [(0.0, 0.0)] + prof + [(0.0, Lf + 0.002)], 16, mat=skin, smooth_angle=None)
        G.place(body, (0, 0, -Lf / 2), (0, 0, 0))
        G.place(body, (0, 0, 0), (0, 90, 0), (1, 0.55, 1))
        tail = G.extrude("tail", [(0, 0), (-0.05, 0.035), (-0.035, 0), (-0.05, -0.035)], 0.002, mat=skin)
        G.place(tail, (0, 0, 0), (90, 0, 0))
        G.place(tail, (-Lf / 2 + 0.01, 0, 0))
        fish = [body, tail]
        a = rng.uniform(0, 6.28)
        r = rng.uniform(0.0, 0.2)
        yaw = rng.uniform(0, 360)
        for f in fish:
            G.place(f, (0, 0, 0), (rng.uniform(-6, 6), 0, yaw))
            G.place(f, (math.cos(a) * r, math.sin(a) * r, zf - 0.01 * k % 3))
        parts += fish
    hp = [(0.3, 0.1, 0.03), (0.34, 0.12, H), (0.4, 0.14, H + 0.03), (0.5, 0.2, 0.02), (0.7, 0.25, 0.01)]
    parts.append(G.tube("hose", hp, 0.004, 6, mat=hose))
    parts.append(G.cyl("airstone", 0.015, 0.03, segs=12, bevel=0.003, mat=stone, loc=(0.29, 0.1, 0.01)))
    cols = [G.col_cyl("plastic", R + 0.02, H + 0.008, segs=14)]
    marks = [G.marker("ATTACH_01", (0, 0, H - 0.05))]
    return {"parts": parts, "glass": [wl], "colliders": cols, "markers": marks,
            "meta": {"water_level": round(H - 0.05, 3)}}


# ---------------------------------------------------------------------------
# Rice sack: 25 kg woven polypropylene sack (label 'rice_sack'), tied top, slumped
# ---------------------------------------------------------------------------
@prop("rice_sack", category="stall", kind="container", surface="fabric", material_kind="soft", mass=25.0,
      density=1024.0, max_tex=2048, tags=["market", "sack", "standable", "nap"])
def rice_sack():
    pp = PN.weave("ricepp", "#e9e4d6", scale=180, dirt=0.5, dust=0.4, rough=0.7, gap=0.15, vary=0.05)
    pp_l = PN.label_only("ricelabel", base="#ebe6d8", rough=0.65, wear=0.25, dirt=0.5, dust=0.4)
    twine = PN.fabric("rtwine", "#c42a24", weave_scale=2500, rough=0.85, role="base", wrinkle=0.0)
    W, D, H = 0.48, 0.3, 0.62
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=10, use_grid_fill=True)
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z + 0.5
        # pillow shape: bulge in the middle, sag & widen at the bottom, gathered at the top
        bul = 1.0 + 0.18 * math.sin(math.pi * z) - 0.1 * z ** 3
        gather = 1.0 - 0.55 * max(0.0, z - 0.8) / 0.2
        v.co.x = x * W * bul * gather
        v.co.y = y * D * (bul + 0.15 * (1 - z)) * gather
        v.co.z = z * H * (1 - 0.06 * (abs(x) * 2) ** 2)
        n = noise.noise(Vector((x * 4, y * 4, z * 4)))
        v.co.x += 0.008 * n
        v.co.z += 0.006 * n
    sack = G.obj_from_bm("sack", bm, pp)
    for p in sack.data.polygons:
        p.use_smooth = True
    front = G.copy(sack, "sack_front")
    # front print panel uses the printed material: copy faces facing -Y only (keep back on the plain weave)
    bm2 = bmesh.new()
    bm2.from_mesh(front.data)
    bmesh.ops.delete(bm2, geom=[f for f in bm2.faces if f.normal.y > -0.6], context="FACES")
    bm2.to_mesh(front.data)
    bm2.free()
    G.set_mat(front, pp_l)
    G.place(front, (0, -0.0012, 0))
    G.label_planar(front, (0.0, 0.0, 0.5, 1.0), (-W * 0.6, 0, 0.0), (1, 0, 0), (0, 0, 1), (W * 1.2, H),
                   normal=(0, -1, 0), min_dot=0.6)
    # top gather & twine
    knot = G.lathe("neck", [(0.0, H - 0.02), (0.07, H - 0.03), (0.05, H + 0.05), (0.09, H + 0.1), (0.0, H + 0.11)], 20,
                   mat=pp, rfunc=lambda r, z, a: r * (1 + 0.2 * math.sin(a * 6)))
    G.place(knot, (0, 0, 0), (0, 0, 0), (1.3, 0.8, 1.0))
    tie = G.tube("tie", [(math.cos(a) * 0.055, math.sin(a) * 0.04, H + 0.03) for a in
                         [2 * math.pi * i / 16 for i in range(16)]], 0.004, 6, mat=twine, closed=True)
    parts = [sack, front, knot, tie]
    G.lean(sack, 0, 0)
    cols = [G.col_box("fabric", (W * 1.1, D * 1.2, H * 0.95))]
    marks = [G.marker("NAP_01", (0, 0, H * 0.92))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("rice_sack")}


# ---------------------------------------------------------------------------
# Bottle crate: red plastic beer crate (fictional brand, label 'bottle_crate') with 20 brown bottles
# ---------------------------------------------------------------------------
@prop("bottle_crate", category="stall", kind="container", dynamic=False, surface="plastic", material_kind="plastic",
      mass=16.0, density=1024.0, max_tex=2048, tags=["market", "crate", "standable", "bottles"])
def bottle_crate():
    pl = PN.plastic("bcrate", "#b8262a", rough=0.42, fade=0.55, scratch=0.9, dirt=0.65, dust=0.4, ground=0.6,
                    label=True, label_wear=0.35, textured=0.3)
    gl = PN.glass_opaque("bbottle", "#4a2a0c", rough=0.06, dirt=0.35, label=True, label_wear=0.25)
    capm = PN.painted_metal("bcap", "#c8a23a", chip=0.4, rust=0.3, gloss=0.3, streaks=0.0)
    W, D, H = 0.46, 0.33, 0.28
    parts = []
    walls = []
    for (sz, loc) in (((W, 0.012, H), (0, -D / 2 + 0.006, 0)), ((W, 0.012, H), (0, D / 2 - 0.006, 0)),
                      ((0.012, D, H), (-W / 2 + 0.006, 0, 0)), ((0.012, D, H), (W / 2 - 0.006, 0, 0))):
        w = G.rbox("wall", sz, mat=pl, bevel=0.003, loc=loc)
        walls.append(w)
    # hand holes on the short sides (dark recesses), ribs, base grid
    for s in (-1, 1):
        hh = G.extrude("handhole", G.rounded_rect(0.11, 0.035, 0.015, 3), 0.004, mat=pl, centre=True)
        G.place(hh, (0, 0, 0), (0, 90, 0))
        G.place(hh, (s * (W / 2 + 0.001), 0, H - 0.05))
        parts.append(hh)
    for x in (-0.15, -0.05, 0.05, 0.15):
        for s in (-1, 1):
            rib = G.rbox("rib", (0.014, 0.006, H - 0.02), mat=pl, bevel=0.002, loc=(x, s * (D / 2 + 0.002), 0.01))
            parts.append(rib)
    base = G.rbox("base", (W - 0.01, D - 0.01, 0.012), mat=pl, bevel=0.002, loc=(0, 0, 0.0))
    parts += walls + [base]
    # dividers
    for i in range(1, 5):
        x = -W / 2 + W * i / 5
        parts.append(G.rbox("div", (0.004, D - 0.02, H * 0.6), mat=pl, bevel=0.001, loc=(x, 0, 0.012)))
    for j in range(1, 4):
        y = -D / 2 + D * j / 4
        parts.append(G.rbox("div", (W - 0.02, 0.004, H * 0.6), mat=pl, bevel=0.001, loc=(0, y, 0.012)))
    # labels on long sides: front printed (top half of sheet), back (bottom half)
    G.label_planar(walls[0], (0.0, 0.5, 1.0, 1.0), (-W / 2, -D / 2, 0.06), (1, 0, 0), (0, 0, 1), (W, 0.16),
                   normal=(0, -1, 0), min_dot=0.7)
    G.label_planar(walls[1], (0.0, 0.5, 1.0, 1.0), (W / 2, D / 2, 0.06), (-1, 0, 0), (0, 0, 1), (W, 0.16),
                   normal=(0, 1, 0), min_dot=0.7)
    rng = random.Random(6)
    for i in range(5):
        for j in range(4):
            if (i, j) in ((4, 3), (0, 0)):
                continue
            x = -W / 2 + W * (i + 0.5) / 5
            y = -D / 2 + D * (j + 0.5) / 4
            prof = [(0.0, 0.012), (0.03, 0.012), (0.032, 0.02), (0.032, 0.17), (0.022, 0.21), (0.013, 0.24),
                    (0.013, 0.275), (0.0, 0.275)]
            b = G.lathe("bottle", prof, 18, mat=gl, max_seg=0.008)
            G.label_cyl(b, (0.0, 0.0, 1.0, 0.5), 0.06, 0.15, a0=-math.pi / 2 - 1.2, a1=-math.pi / 2 + 1.2)
            G.place(b, (0, 0, 0), (0, 0, rng.uniform(-60, 60)))
            G.place(b, (x, y, 0))
            cap = G.cyl("cap", 0.0145, 0.008, segs=14, bevel=0.0012, mat=capm, loc=(x, y, 0.275))
            parts += [b, cap]
    cols = [G.col_box("plastic", (W, D, H))]
    marks = [G.marker("SIT_01", (0, 0, H + 0.02))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("bottle_crate")}
