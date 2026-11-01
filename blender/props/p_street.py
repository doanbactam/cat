"""Street furniture: lamp posts, cone, barrier, bins, grates, manhole, hydrant, mailbox, rack, signs, banner."""
import json
import math
import os
import random
import sys

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


# ---------------------------------------------------------------------------
# Traffic cone — 70 cm PVC cone on a square recycled-rubber base, two retro-reflective sleeves
# ---------------------------------------------------------------------------
@prop("traffic_cone", category="street", surface="plastic", material_kind="plastic", mass=2.6,
      tags=["roadwork"])
def traffic_cone():
    BASE_W, BASE_H = 0.38, 0.032
    R0, R1, H = 0.135, 0.026, 0.70
    m_cone = PN.plastic("cone", "#f0561e", rough=0.38, fade=0.5, scratch=0.9, dirt=0.7, dust=0.5, ground=0.8)
    m_base = PN.rubber("cone_base", "#1b1b1a", dirt=0.6, dust=0.5, ground=0.6)
    m_band = PN.plastic("cone_band", "#e9ebe6", rough=0.22, fade=0.1, scratch=0.9, dirt=0.6, dust=0.3, stress=0.0,
                        textured=1.0)
    parts = []
    base = G.rbox("base", (BASE_W, BASE_W, BASE_H), bevel=0.012, segs=3, mat=m_base)
    collar = G.lathe("collar", [(0.0, BASE_H), (R0 + 0.03, BASE_H), (R0 + 0.022, BASE_H + 0.018),
                                (R0 + 0.004, BASE_H + 0.024), (0.0, BASE_H + 0.024)], 40, mat=m_base)

    def cone_r(z):
        return R0 + (R1 - R0) * (z - BASE_H) / (H - BASE_H)
    prof = [(R0 + 0.006, BASE_H)]
    n = 12
    for i in range(n + 1):
        z = BASE_H + 0.02 + (H - 0.012 - BASE_H - 0.02) * i / n
        prof.append((cone_r(z), z))
    prof += [(R1 - 0.002, H - 0.004), (R1 - 0.006, H), (R1 - 0.010, H - 0.004), (R1 - 0.013, H - 0.05)]
    cone = G.lathe("cone", prof, 40, mat=m_cone, rfunc=lambda r, z, a: r * (1 + 0.004 * math.sin(a * 3 + z * 9)))
    G.wobble(cone, 0.0025, 4.0, seed=3, zmin=0.1)
    G.dent(cone, (0.08, -0.06, 0.25), 0.07, 0.008)
    parts += [base, collar, cone]
    for (z0, z1) in ((0.36, 0.46), (0.53, 0.60)):
        bp = [(cone_r(z0 + (z1 - z0) * i / 4) + 0.0012, z0 + (z1 - z0) * i / 4) for i in range(5)]
        band = G.lathe("band", bp, 40, mat=m_band)
        G.solidify(band, 0.0008, offset=1.0)
        parts.append(band)
    cols = [G.col_box("plastic", (BASE_W, BASE_W, BASE_H)),
            G.col_cyl("plastic", R0, H - BASE_H, loc=(0, 0, BASE_H), r2=R1)]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Colonial cast-iron lamp post (Hoàn Kiếm style): octagonal plinth, fluted column, lantern head
# ---------------------------------------------------------------------------
@prop("lamp_post_colonial", category="street", kind="lighting", surface="metal", material_kind="metal",
      mass=180.0, max_tex=2048, tags=["light", "colonial"], night_emission=3.0)
def lamp_post_colonial():
    iron = PN.painted_metal("iron", "#1c2a23", primer="#5a2e1c", chip=0.35, rust=0.5, gloss=0.42, streaks=0.55,
                            dirt=0.6, dust=0.4, ground=0.8)
    glass = PN.emissive_plain("lamp_glass", "#f1e2bf", role="lit", rough=0.25)
    brass = PN.metal("brass", "brass", wear=0.6, dirt=0.5)
    parts = []
    oct_phase = math.pi / 8
    plinth = G.lathe("plinth", [(0.0, 0.0), (0.24, 0.0), (0.24, 0.05), (0.215, 0.07), (0.205, 0.10), (0.17, 0.13),
                                (0.165, 0.42), (0.19, 0.45), (0.19, 0.49), (0.14, 0.52), (0.12, 0.56), (0.0, 0.56)],
                     8, mat=iron, phase=oct_phase, smooth_angle=30)
    # raised panels on the plinth faces
    for i in range(8):
        a = oct_phase + math.pi / 8 + i * math.pi / 4
        pnl = G.rbox("panel", (0.09, 0.012, 0.2), bevel=0.003, mat=iron)
        G.place(pnl, (0, 0, 0), (0, 0, math.degrees(a) + 90))
        G.place(pnl, (math.cos(a) * 0.158, math.sin(a) * 0.158, 0.17))
        parts.append(pnl)
    flute = lambda r, z, a: r * (1 + 0.045 * max(0.0, math.cos(a * 16)) ** 0.5)  # noqa: E731
    col = G.lathe("column", [(0.088, 0.56), (0.084, 1.4), (0.078, 2.4), (0.07, 3.3)], 64, mat=iron, rfunc=flute,
                  smooth_angle=70)
    parts += [plinth, col]
    for z, r in ((0.6, 0.11), (1.25, 0.1), (3.3, 0.09)):
        ring = G.lathe("ring", [(r - 0.02, z - 0.03), (r, z - 0.02), (r + 0.004, z), (r, z + 0.02), (r - 0.02, z + 0.03)],
                       40, mat=iron)
        parts.append(ring)
    neck = G.lathe("neck", [(0.07, 3.3), (0.06, 3.38), (0.09, 3.5), (0.1, 3.58), (0.075, 3.66), (0.05, 3.72),
                            (0.08, 3.76), (0.08, 3.79)], 32, mat=iron)
    parts.append(neck)
    # scroll brackets
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        pts = []
        for k in range(14):
            t = k / 13
            rr = 0.07 + 0.11 * math.sin(t * math.pi * 0.85)
            z = 3.42 + 0.36 * t
            pts.append((math.cos(a) * rr, math.sin(a) * rr, z))
        sc = G.tube("scroll", pts, 0.008, 8, mat=iron)
        curl = [(math.cos(a) * (0.07 + 0.03 * math.cos(u)), math.sin(a) * (0.07 + 0.03 * math.cos(u)),
                 3.42 + 0.03 * math.sin(u)) for u in [j * 0.5 for j in range(12)]]
        parts += [sc, G.tube("curl", curl, 0.007, 6, mat=iron)]
    # lantern: square frustum (4 sides, rotated 45 deg so faces look along the axes)
    zb, zt = 3.8, 4.15
    base_tray = G.lathe("tray", [(0.0, 3.77), (0.13, 3.77), (0.15, 3.8), (0.15, 3.82), (0.0, 3.82)], 4,
                        mat=iron, phase=math.pi / 4, smooth_angle=30)
    pane = G.lathe("glass", [(0.14, zb + 0.02), (0.2, zt - 0.01)], 4, mat=glass, phase=math.pi / 4, smooth_angle=30)
    inner = G.lathe("glass_in", [(0.19, zt - 0.015), (0.135, zb + 0.025)], 4, mat=glass, phase=math.pi / 4,
                    smooth_angle=30)
    parts += [base_tray, pane, inner]
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        p0 = (math.cos(a) * 0.15, math.sin(a) * 0.15, zb + 0.01)
        p1 = (math.cos(a) * 0.212, math.sin(a) * 0.212, zt)
        parts.append(G.tube("mullion", [p0, p1], 0.008, 6, mat=iron))
    for z, r in ((zb + 0.02, 0.152), (zt, 0.214)):
        ring = G.lathe("lring", [(r - 0.012, z - 0.012), (r + 0.004, z - 0.012), (r + 0.004, z + 0.012),
                                 (r - 0.012, z + 0.012)], 4, mat=iron, phase=math.pi / 4, smooth_angle=30)
        parts.append(ring)
    roof = G.lathe("roof", [(0.0, zt), (0.25, zt), (0.25, zt + 0.02), (0.13, zt + 0.1), (0.05, zt + 0.17),
                            (0.035, zt + 0.19), (0.0, zt + 0.19)], 4, mat=iron, phase=math.pi / 4, smooth_angle=30)
    fin = G.lathe("finial", [(0.0, zt + 0.19), (0.03, zt + 0.2), (0.035, zt + 0.23), (0.02, zt + 0.26),
                             (0.008, zt + 0.32), (0.0, zt + 0.34)], 16, mat=brass)
    bulb = G.sphere("bulb", 0.05, loc=(0, 0, 3.97), mat=glass, scale=(1, 1, 1.25))
    parts += [roof, fin, bulb]
    for p in parts:
        G.uv_weight(p, 0.45, zmin=0.9, zmax=3.75)
    cols = [G.col_cyl("metal", 0.24, 0.56, segs=8), G.col_cyl("metal", 0.09, 3.25, loc=(0, 0, 0.56), r2=0.075),
            G.col_box("metal", (0.4, 0.4, 0.55), loc=(0, 0, 3.78))]
    marks = [light_marker("LIGHT_01", (0, 0, 3.97), kind="omni", range=11.0, energy=2.4,
                          color=[1.0, 0.8, 0.55], shadow=False, fade=60.0)]
    return {"parts": parts, "colliders": cols, "markers": marks}


# ---------------------------------------------------------------------------
# Modern galvanized lamp post with curved outreach arm and LED head, pole stickers
# ---------------------------------------------------------------------------
@prop("lamp_post_modern", category="street", kind="lighting", surface="metal", material_kind="metal", mass=95.0,
      max_tex=2048, tags=["light", "modern"], night_emission=4.0)
def lamp_post_modern():
    galv = PN.metal("galv", "galvanized", dirt=0.6, dust=0.3, ground=0.8, wear=0.4, rust=0.15, label=True,
                    label_wear=0.25)
    head_m = PN.painted_metal("head", "#8c9296", chip=0.1, rust=0.05, gloss=0.5, streaks=0.3, dirt=0.4)
    diff = PN.emissive_plain("led", "#f4f1ea", role="lit", rough=0.2)
    parts = []
    H = 7.0
    pole = G.lathe("pole", [(0.0, 0.02), (0.09, 0.02), (0.088, 0.3), (0.075, 2.5), (0.058, 5.0), (0.045, H),
                            (0.0, H + 0.01)], 8, mat=galv, phase=math.pi / 8, smooth_angle=50)
    G.label_cyl(pole, (0.0, 0.0, 1.0, 0.42), 1.0, 2.1, a0=-math.pi / 2 - 1.3, a1=-math.pi / 2 + 1.3)
    plate = G.rbox("plate", (0.36, 0.36, 0.02), bevel=0.004, mat=galv)
    parts += [pole, plate]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(G.cyl("nut", 0.018, 0.022, loc=(sx * 0.14, sy * 0.14, 0.02), segs=6, bevel=0.002, mat=galv))
            parts.append(G.cyl("bolt", 0.009, 0.045, loc=(sx * 0.14, sy * 0.14, 0.02), segs=10, bevel=0.001, mat=galv))
    door = G.rbox("door", (0.09, 0.012, 0.28), bevel=0.003, mat=galv)
    G.place(door, (0, -0.083, 0.55))
    parts.append(door)
    arm = []
    for k in range(17):
        t = k / 16
        a = t * math.pi * 0.5
        arm.append((0, -0.9 * (1 - math.cos(a)) - 0.75 * t ** 1.6, H - 0.4 + 0.75 * math.sin(a)))
    parts.append(G.tube("arm", arm, 0.03, 12, mat=galv, rfunc=lambda t: 1.0 - 0.25 * t))
    hx, hy, hz = 0.0, arm[-1][1] - 0.22, arm[-1][2] - 0.02
    head = G.rbox("head", (0.24, 0.62, 0.1), bevel=0.04, segs=4, mat=head_m)
    G.place(head, (hx, hy, hz - 0.05), (-6, 0, 0))
    lens = G.rbox("lens", (0.19, 0.48, 0.012), bevel=0.004, mat=diff)
    G.place(lens, (hx, hy - 0.03, hz - 0.062), (-6, 0, 0))
    parts += [head, lens]
    for p in parts:
        G.uv_weight(p, 0.3, zmin=2.6)
    cols = [G.col_cyl("metal", 0.09, H, segs=8, r2=0.05), G.col_box("metal", (0.36, 0.36, 0.02))]
    marks = [light_marker("LIGHT_01", (hx, hy - 0.03, hz - 0.1), kind="spot", range=16.0, angle=62.0, energy=6.0,
                          color=[1.0, 0.93, 0.82], dir=[0, -0.12, -1.0], shadow=False, fade=80.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("pole_stickers")}


# ---------------------------------------------------------------------------
# Water-filled plastic road barrier (1.5 m) with chevron panels
# ---------------------------------------------------------------------------
@prop("construction_barrier", category="street", surface="plastic", mass=18.0, tags=["roadwork"])
def construction_barrier():
    body_m = PN.plastic("barrier", "#ecebe4", rough=0.45, fade=0.4, scratch=0.9, dirt=0.75, dust=0.5, ground=0.9,
                        label=True, label_wear=0.35)
    cap_m = PN.plastic("cap", "#d23a2a", rough=0.4, fade=0.4)
    LEN, WB, WT, H = 1.5, 0.42, 0.16, 0.8
    import bmesh
    bm = bmesh.new()
    prof = [(-WB / 2, 0.0), (WB / 2, 0.0), (WB / 2, 0.08), (WT / 2 + 0.05, 0.45), (WT / 2, H), (-WT / 2, H),
            (-WT / 2 - 0.05, 0.45), (-WB / 2, 0.08)]
    vs0 = [bm.verts.new((-LEN / 2, y, z)) for (y, z) in prof]
    vs1 = [bm.verts.new((LEN / 2, y, z)) for (y, z) in prof]
    n = len(prof)
    for i in range(n):
        bm.faces.new((vs0[i], vs1[i], vs1[(i + 1) % n], vs0[(i + 1) % n]))
    bm.faces.new(vs0[::-1])
    bm.faces.new(vs1)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.025, segments=3, profile=0.5, affect="EDGES", clamp_overlap=True)
    body = G.obj_from_bm("barrier", bm, body_m)
    G.wobble(body, 0.004, 2.0, seed=5)
    # chevron panels on both long faces (the sloped faces between z 0.1 and 0.42 are near-vertical)
    G.label_planar(body, (0.0, 0.0, 0.5, 1.0), (-LEN / 2 + 0.05, -WB / 2, 0.06), (1, 0, 0), (0, 0.17, 0.98),
                   (LEN - 0.1, 0.72), normal=(0, -1, 0.15), min_dot=0.6, bounds_pad=0.02)
    G.label_planar(body, (0.5, 0.0, 1.0, 1.0), (LEN / 2 - 0.05, WB / 2, 0.06), (-1, 0, 0), (0, -0.17, 0.98),
                   (LEN - 0.1, 0.72), normal=(0, 1, 0.15), min_dot=0.6, bounds_pad=0.02)
    parts = [body]
    # interlock lugs + fill cap + fork slots (dark recesses)
    for sx in (-1, 1):
        for z in (0.18, 0.62):
            lug = G.rbox("lug", (0.06, 0.12, 0.08), bevel=0.012, mat=body_m)
            G.place(lug, (sx * (LEN / 2 + 0.02), 0, z))
            parts.append(lug)
    cap = G.cyl("cap", 0.05, 0.03, loc=(0.4, 0, H - 0.005), segs=20, bevel=0.004, mat=cap_m)
    parts.append(cap)
    for sx in (-0.4, 0.4):
        slot = G.rbox("slot", (0.22, WB + 0.004, 0.05), bevel=0.01, mat=PN.rubber("slot", "#202020", dirt=0.7))
        G.place(slot, (sx, 0, 0.012))
        parts.append(slot)
    cols = [G.col_box("plastic", (LEN, WB, 0.45)), G.col_box("plastic", (LEN, WT + 0.08, H - 0.45), loc=(0, 0, 0.45))]
    return {"parts": parts, "colliders": cols, "label": L("barrier")}


# ---------------------------------------------------------------------------
# Green municipal 240 L wheelie bin
# ---------------------------------------------------------------------------
def _frustum_box(name, wb, db, wt, dt, h, z0=0.0, bevel=0.02, mat=None, segs=3):
    import bmesh
    bm = bmesh.new()
    vb = [bm.verts.new((x * wb / 2, y * db / 2, z0)) for (x, y) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    vt = [bm.verts.new((x * wt / 2, y * dt / 2, z0 + h)) for (x, y) in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    for i in range(4):
        bm.faces.new((vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bevel:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, profile=0.5, affect="EDGES",
                        clamp_overlap=True)
    return G.obj_from_bm(name, bm, mat)


@prop("trash_bin_municipal", category="street", kind="container", surface="plastic", mass=14.0,
      tags=["bin", "standable"])
def trash_bin_municipal():
    body_m = PN.plastic("bin", "#2f7d3a", rough=0.5, fade=0.55, scratch=0.9, dirt=0.85, dust=0.5, ground=0.9,
                        label=True, label_wear=0.45)
    lid_m = PN.plastic("lid", "#2c7536", rough=0.45, fade=0.7, scratch=0.8, dirt=0.7, dust=0.7)
    rub = PN.rubber("wheel", "#1a1a1a", dirt=0.7, dust=0.4, ground=0.8)
    steel = PN.metal("axle", "galvanized", dirt=0.7, rust=0.4)
    parts = []
    body = _frustum_box("body", 0.48, 0.52, 0.58, 0.66, 0.96, z0=0.04, bevel=0.035, mat=body_m, segs=4)
    G.wobble(body, 0.004, 3.0, seed=2)
    G.dent(body, (0.2, -0.3, 0.45), 0.12, 0.012)
    G.label_planar(body, (0.0, 0.0, 0.5, 1.0), (-0.2, -0.3, 0.45), (1, 0, 0), (0, -0.07, 1), (0.4, 0.4),
                   normal=(0, -1, 0.1), min_dot=0.7)
    rim = G.rbox("rim", (0.61, 0.70, 0.05), bevel=0.012, mat=body_m)
    G.place(rim, (0, 0, 0.97))
    lid = G.rbox("lid", (0.62, 0.74, 0.05), bevel=0.02, segs=3, mat=lid_m)
    G.place(lid, (0, -0.01, 1.01))
    G.wobble(lid, 0.003, 4, seed=8)
    G.label_planar(lid, (0.5, 0.0, 1.0, 1.0), (-0.15, -0.25, 1.06), (1, 0, 0), (0, 1, 0), (0.3, 0.3), normal=(0, 0, 1))
    lip = G.rbox("lip", (0.3, 0.04, 0.03), bevel=0.01, mat=lid_m)
    G.place(lip, (0, -0.39, 1.02))
    parts += [body, rim, lid, lip]
    # rear: hinge rail, handle bar, axle + wheels
    bar = G.tube("handle", [(-0.27, 0.40, 0.98), (-0.25, 0.42, 1.0), (0.25, 0.42, 1.0), (0.27, 0.40, 0.98)], 0.017,
                 10, mat=body_m)
    parts.append(bar)
    for sx in (-1, 1):
        hinge = G.rbox("hinge", (0.06, 0.05, 0.06), bevel=0.01, mat=body_m)
        G.place(hinge, (sx * 0.2, 0.37, 0.98))
        parts.append(hinge)
        w = G.lathe("wheel", [(0.0, -0.035), (0.1, -0.035), (0.125, -0.03), (0.13, 0.0), (0.125, 0.03),
                              (0.1, 0.035), (0.0, 0.035)], 28, mat=rub)
        G.place(w, (0, 0, 0), (0, 90, 0))
        G.place(w, (sx * 0.29, 0.30, 0.13))
        hub = G.cyl("hub", 0.05, 0.075, loc=(0, 0, -0.0375), segs=16, mat=body_m)
        G.place(hub, (0, 0, 0), (0, 90, 0))
        G.place(hub, (sx * 0.29, 0.30, 0.13))
        parts += [w, hub]
    axle = G.cyl("axle", 0.012, 0.66, loc=(0, 0, -0.33), segs=10, mat=steel)
    G.place(axle, (0, 0, 0), (0, 90, 0))
    G.place(axle, (0, 0.30, 0.13))
    foot = G.rbox("foot", (0.36, 0.06, 0.05), bevel=0.01, mat=body_m)
    G.place(foot, (0, -0.24, 0.0))
    parts += [axle, foot]
    cols = [G.col_box("plastic", (0.6, 0.72, 1.06))]
    marks = [G.marker("NAP_01", (0, 0, 1.06))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("bin_municipal")}


@prop("trash_bin_household", category="street", kind="container", dynamic=True, surface="plastic", mass=1.4,
      material_kind="plastic", tags=["bin", "knockable"])
def trash_bin_household():
    body_m = PN.plastic("hbin", "#3a7fb5", rough=0.4, fade=0.3, scratch=0.7, dirt=0.6, dust=0.4, ground=0.5)
    lid_m = PN.plastic("hlid", "#e8e6df", rough=0.35, fade=0.2, scratch=0.6, dirt=0.5, dust=0.6)
    parts = []
    body = G.lathe("body", [(0.0, 0.012), (0.12, 0.012), (0.125, 0.02), (0.145, 0.38), (0.15, 0.40), (0.0, 0.40)], 36,
                   mat=body_m)
    ribs = []
    for i in range(12):
        a = 2 * math.pi * i / 12
        r = G.rbox("rib", (0.012, 0.01, 0.3), bevel=0.003, mat=body_m)
        G.place(r, (0, 0, 0), (-3.0, 0, 0))
        G.place(r, (0, 0, 0), (0, 0, math.degrees(a) + 90))
        G.place(r, (math.cos(a) * 0.132, math.sin(a) * 0.132, 0.05))
        ribs.append(r)
    foot = G.lathe("foot", [(0.0, 0.0), (0.115, 0.0), (0.12, 0.014), (0.0, 0.014)], 36, mat=body_m)
    lid = G.lathe("lid", [(0.0, 0.40), (0.158, 0.40), (0.158, 0.415), (0.14, 0.44), (0.07, 0.455), (0.0, 0.457)], 36,
                  mat=lid_m)
    hinge = G.rbox("hinge", (0.08, 0.03, 0.03), bevel=0.008, mat=lid_m)
    G.place(hinge, (0, 0.155, 0.395))
    pedal = G.rbox("pedal", (0.1, 0.07, 0.02), bevel=0.006, mat=lid_m)
    G.place(pedal, (0, -0.15, 0.02), (8, 0, 0))
    bag = G.lathe("bag", [(0.146, 0.385), (0.16, 0.39), (0.155, 0.405)], 36, mat=PN.plastic("bag", "#1e1e1e", rough=0.3))
    G.wobble(bag, 0.006, 20, seed=4)
    parts += [body, foot, lid, hinge, pedal, bag] + ribs
    cols = [G.col_cyl("plastic", 0.15, 0.457, segs=12)]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# Cast-iron drain grate and manhole cover
# ---------------------------------------------------------------------------
@prop("drain_grate", category="street", kind="utility", surface="metal", mass=22.0, tags=["ground"])
def drain_grate():
    iron = PN.metal("grate", "cast_iron", dirt=0.8, dust=0.4, rust=0.7, wear=0.5)
    pit_m = PN.concrete("pit", "#3c3a35", dirt=0.9, moss=0.5, stains=0.8)
    W, D, T = 0.62, 0.34, 0.03
    parts = []
    frame = []
    for (sx, sy, x, y) in ((W, 0.04, 0, -D / 2 + 0.02), (W, 0.04, 0, D / 2 - 0.02), (0.04, D, -W / 2 + 0.02, 0),
                           (0.04, D, W / 2 - 0.02, 0)):
        b = G.rbox("frame", (sx, sy, T), bevel=0.004, mat=iron)
        G.place(b, (x, y, -T + 0.008))
        frame.append(b)
    n = 13
    for i in range(n):
        x = -W / 2 + 0.06 + (W - 0.12) * i / (n - 1)
        bar = G.rbox("bar", (0.016, D - 0.06, T - 0.004), bevel=0.003, mat=iron)
        G.place(bar, (x, 0, -T + 0.008))
        frame.append(bar)
    cross = G.rbox("cross", (W - 0.06, 0.02, T - 0.012), bevel=0.003, mat=iron)
    G.place(cross, (0, 0, -T + 0.004))
    # dark pit under the slots (open box, faces inward)
    pit = G.rbox("pit", (W - 0.06, D - 0.06, 0.25), bevel=0.0, mat=pit_m)
    G.place(pit, (0, 0, -0.27))
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(pit.data)
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    top = [f for f in bm.faces if f.calc_center_median().z > -0.03]
    bmesh.ops.delete(bm, geom=top, context="FACES")
    bm.to_mesh(pit.data)
    bm.free()
    G.uv_weight(pit, 0.4)
    parts += frame + [cross, pit]
    cols = [G.col_box("metal", (W, D, 0.02), loc=(0, 0, -0.012))]
    return {"parts": parts, "colliders": cols}


@prop("manhole_cover", category="street", kind="utility", surface="metal", mass=40.0, tags=["ground"])
def manhole_cover():
    iron = PN.NB("manhole", "base")
    nb = iron
    em = nb.node("ShaderNodeUVMap")
    em.uv_map = "LabelUV"
    t = nb.node("ShaderNodeTexImage", extension="CLIP", interpolation="Cubic")
    t.image = PN.ensure_label_image()
    nb.link(em.outputs["UV"], t.inputs["Vector"])
    raised = t.outputs["Alpha"]
    base_c = PN._var(nb, "#34312e", 0.08, 5)
    rustc = nb.ramp(nb.noise(scale=40, detail=6), [(0.2, "#3b1d0e"), (0.6, "#6e3516"), (0.9, "#8f4e22")])
    low = nb.inv(raised)
    rmask = nb.clamp(nb.add(nb.mul(low, nb.smooth(nb.noise(scale=7, detail=6), 0.45, 0.7)), nb.mul(nb.cav, 1.2)))
    c = nb.mixc(nb.mul(rmask, 0.75), base_c, rustc)
    pol = nb.mul(raised, nb.smooth(nb.noise(scale=4, detail=3), 0.2, 0.6))
    c = nb.mixc(nb.mul(pol, 0.7), c, "#77736c")
    r = nb.mixf(pol, nb.madd(nb.noise(scale=30, detail=4), 0.15, 0.68), 0.3)
    m = nb.mixf(pol, 0.4, 0.95)
    h = nb.add(nb.mul(raised, 1.0), nb.mul(nb.noise(scale=200, detail=6), 0.25))
    s = nb.weather(nb.st(c, r, m, h), dirt=0.8, dust=0.5)
    mat = nb.finish(s, bump=0.004, strength=1.0)
    frame_m = PN.metal("frame", "cast_iron", dirt=0.8, rust=0.7)
    asph = PN.concrete("patch", "#3d3c3a", dirt=0.6, stains=0.3, aggregate=0.9, moss=0.0)
    parts = []
    disc = G.lathe("disc", [(0.0, 0.012), (0.345, 0.012), (0.35, 0.008), (0.35, 0.0), (0.0, 0.0)], 72, mat=mat,
                   smooth_angle=30)
    G.label_all_planar_top(disc, (0, 0, 1, 1), 0, 0, 0.7, 0.7)
    ring = G.lathe("ring", [(0.352, 0.0), (0.352, 0.013), (0.36, 0.016), (0.42, 0.016), (0.43, 0.008), (0.43, 0.0)],
                   72, mat=frame_m)
    # cracked asphalt/cement patch around the frame
    patch = G.lathe("patch", [(0.43, 0.006), (0.5, 0.004), (0.56, 0.0)], 48, mat=asph,
                    rfunc=lambda r, z, a: r * (1 + 0.05 * math.sin(a * 5) + 0.03 * math.sin(a * 11)))
    for i in range(2):
        a = i * math.pi
        hole = G.cyl("pickhole", 0.016, 0.003, loc=(math.cos(a) * 0.26, math.sin(a) * 0.26, 0.0105), segs=12,
                     bevel=0.0, mat=frame_m)
        parts.append(hole)
    parts += [disc, ring, patch]
    cols = [G.col_cyl("metal", 0.43, 0.016, segs=16)]
    return {"parts": parts, "colliders": cols, "label": L("manhole_emboss")}


# ---------------------------------------------------------------------------
# Fire hydrant (pillar type, red)
# ---------------------------------------------------------------------------
@prop("fire_hydrant", category="street", kind="utility", surface="metal", mass=90.0, tags=["standable"])
def fire_hydrant():
    red = PN.painted_metal("hydrant", "#b3221c", primer="#6a2a18", chip=0.55, rust=0.55, gloss=0.4, streaks=0.5,
                           dirt=0.6, dust=0.4, ground=0.8, label=True, label_wear=0.5)
    brass = PN.metal("hbrass", "brass", wear=0.7, dirt=0.6)
    iron = PN.metal("hchain", "cast_iron", rust=0.8)
    conc = PN.concrete("hpad", "#8f8b82", dirt=0.7, moss=0.3, stains=0.5)
    parts = []
    pad = G.rbox("pad", (0.42, 0.42, 0.05), bevel=0.012, mat=conc)
    G.wobble(pad, 0.004, 5, seed=3)
    body = G.lathe("body", [(0.0, 0.05), (0.15, 0.05), (0.15, 0.08), (0.115, 0.09), (0.1, 0.12), (0.092, 0.2),
                            (0.09, 0.55), (0.1, 0.57), (0.105, 0.6), (0.095, 0.62), (0.085, 0.68), (0.06, 0.72),
                            (0.035, 0.74), (0.0, 0.745)], 40, mat=red)
    G.label_cyl(body, (0, 0, 1, 1), 0.42, 0.5, a0=-math.pi, a1=math.pi)
    for i in range(8):
        a = 2 * math.pi * i / 8
        parts.append(G.cyl("bolt", 0.011, 0.02, loc=(math.cos(a) * 0.13, math.sin(a) * 0.13, 0.08), segs=6,
                           bevel=0.001, mat=red))
    nut = G.cyl("topnut", 0.025, 0.035, loc=(0, 0, 0.735), segs=5, bevel=0.003, mat=red)
    parts += [pad, body, nut]
    for side in (-1, 1):
        o = G.lathe("outlet", [(0.0, 0.0), (0.045, 0.0), (0.045, 0.06), (0.05, 0.065), (0.05, 0.085), (0.0, 0.085)],
                    24, mat=red)
        G.place(o, (0, 0, 0), (0, side * 90, 0))
        G.place(o, (side * 0.07, 0, 0.44))
        capm = G.cyl("cap", 0.052, 0.035, loc=(0, 0, 0.085), segs=5, bevel=0.004, mat=red)
        G.place(capm, (0, 0, 0), (0, side * 90, 0))
        G.place(capm, (side * 0.07, 0, 0.44))
        chain = [(side * (0.17 + 0.0), 0.0, 0.42)]
        for k in range(8):
            t = k / 7
            chain.append((side * (0.17 - 0.06 * t), -0.04 * math.sin(t * math.pi), 0.42 - 0.08 * math.sin(t * math.pi)
                          + 0.06 * t))
        parts += [o, capm, G.tube("chain", chain, 0.004, 5, mat=iron)]
    front = G.lathe("front", [(0.0, 0.0), (0.06, 0.0), (0.06, 0.05), (0.0, 0.05)], 24, mat=red)
    G.place(front, (0, 0, 0), (90, 0, 0))
    G.place(front, (0, -0.07, 0.3))
    fcap = G.cyl("fcap", 0.063, 0.03, loc=(0, 0, 0.05), segs=6, bevel=0.004, mat=brass)
    G.place(fcap, (0, 0, 0), (90, 0, 0))
    G.place(fcap, (0, -0.07, 0.3))
    parts += [front, fcap]
    cols = [G.col_box("concrete", (0.42, 0.42, 0.05)), G.col_cyl("metal", 0.1, 0.7, loc=(0, 0, 0.05), r2=0.07)]
    return {"parts": parts, "colliders": cols, "label": L("hydrant_band")}


# ---------------------------------------------------------------------------
# Standing letterbox
# ---------------------------------------------------------------------------
@prop("mailbox", category="street", kind="street", surface="metal", mass=35.0, tags=["standable"])
def mailbox():
    green = PN.painted_metal("mbox", "#1f5a43", primer="#6e3a24", chip=0.4, rust=0.45, gloss=0.5, streaks=0.5,
                             dirt=0.6, dust=0.5, ground=0.7, label=True, label_wear=0.3)
    steel = PN.metal("lock", "stainless", dirt=0.5)
    conc = PN.concrete("mpad", "#8d897f", dirt=0.6, moss=0.25)
    parts = []
    post = G.rbox("post", (0.08, 0.08, 0.78), bevel=0.006, mat=green)
    foot = G.rbox("foot", (0.2, 0.2, 0.012), bevel=0.003, mat=green)
    G.place(foot, (0, 0, 0.03))
    pad = G.rbox("pad", (0.3, 0.3, 0.03), bevel=0.008, mat=conc)
    box = G.rbox("box", (0.42, 0.3, 0.52), bevel=0.018, segs=3, mat=green)
    G.place(box, (0, 0, 0.78))
    G.label_planar(box, (0.0, 0.5, 1.0, 1.0), (-0.19, -0.15, 1.02), (1, 0, 0), (0, 0, 1), (0.38, 0.26),
                   normal=(0, -1, 0))
    G.label_planar(box, (0.08, 0.05, 0.92, 0.45), (-0.12, -0.15, 0.82), (1, 0, 0), (0, 0, 1), (0.24, 0.16),
                   normal=(0, -1, 0))
    # sloped rain hood roof
    import bmesh
    bm = bmesh.new()
    pts = [(-0.24, -0.19, 1.30), (0.24, -0.19, 1.30), (0.24, 0.17, 1.36), (-0.24, 0.17, 1.36)]
    vb = [bm.verts.new(p) for p in pts]
    vt = [bm.verts.new((p[0], p[1], p[2] + 0.025)) for p in pts]
    bm.faces.new(vb[::-1])
    bm.faces.new(vt)
    for i in range(4):
        bm.faces.new((vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.008, segments=2, profile=0.5, affect="EDGES")
    roof = G.obj_from_bm("roof", bm, green)
    slot_hood = G.rbox("slothood", (0.26, 0.04, 0.035), bevel=0.008, mat=green)
    G.place(slot_hood, (0, -0.16, 1.22), (-20, 0, 0))
    slot = G.rbox("slot", (0.22, 0.02, 0.012), bevel=0.002, mat=PN.rubber("slotdark", "#0c0c0c", dirt=0.2))
    G.place(slot, (0, -0.15, 1.205))
    door = G.rbox("door", (0.36, 0.012, 0.42), bevel=0.004, mat=green)
    G.place(door, (0, 0.152, 0.83))
    lock = G.cyl("lock", 0.016, 0.015, loc=(0, 0, 0), segs=16, mat=steel)
    G.place(lock, (0, 0, 0), (-90, 0, 0))
    G.place(lock, (0.12, 0.16, 1.05))
    parts += [post, foot, pad, box, roof, slot_hood, slot, door, lock]
    cols = [G.col_box("metal", (0.08, 0.08, 0.78)), G.col_box("metal", (0.44, 0.32, 0.6), loc=(0, 0, 0.78))]
    marks = [G.marker("NAP_01", (0, 0, 1.38))]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("mailbox")}


# ---------------------------------------------------------------------------
# Galvanized wave bicycle rack
# ---------------------------------------------------------------------------
@prop("bicycle_rack", category="street", surface="metal", mass=28.0, tags=["climbable_low"])
def bicycle_rack():
    galv = PN.metal("rack", "galvanized", dirt=0.6, dust=0.3, ground=0.7, rust=0.3, wear=0.6)
    pts = []
    loops = 5
    W, H, R = 1.8, 0.72, 0.17
    for i in range(loops * 24 + 1):
        t = i / (loops * 24)
        x = -W / 2 + W * t
        ph = t * loops * 2 * math.pi
        z = 0.03 + (H - 0.03) * (0.5 - 0.5 * math.cos(ph))
        pts.append((x, 0.0, z))
    pts = [(-W / 2, 0, 0.03)] + pts[1:]
    wave = G.tube("wave", pts, 0.024, 12, mat=galv)
    parts = [wave]
    for y in (-0.0,):
        rail = G.tube("rail", [(-W / 2 - 0.02, y, 0.025), (W / 2 + 0.02, y, 0.025)], 0.022, 10, mat=galv)
        parts.append(rail)
    for x in (-W / 2, W / 2):
        f = G.rbox("foot", (0.12, 0.12, 0.008), bevel=0.003, mat=galv)
        G.place(f, (x, 0, 0))
        parts.append(f)
    cols = [G.col_box("metal", (W, 0.05, H))]
    return {"parts": parts, "colliders": cols}


# ---------------------------------------------------------------------------
# A-frame sidewalk signs and a light-box sign
# ---------------------------------------------------------------------------
def _aframe(label, board_col):
    frame_m = PN.painted_metal("aframe", "#2b2b2b", chip=0.4, rust=0.5, dirt=0.6, ground=0.7)
    board_m = PN.label_only("board", board_col, rough=0.45, wear=0.25, dirt=0.4, dust=0.3)
    W, H, TILT = 0.62, 0.95, 13.0
    parts = []
    for side in (-1, 1):
        objs = []
        brd = G.rbox("board", (W - 0.04, 0.006, H - 0.06), bevel=0.002, mat=board_m)
        G.place(brd, (0, 0, 0.03))
        if side < 0:
            G.label_planar(brd, (0.0, 0.0, 0.5, 1.0), (-(W - 0.04) / 2, -0.003, 0.03), (1, 0, 0), (0, 0, 1),
                           (W - 0.04, H - 0.06), normal=(0, -1, 0))
        else:
            G.label_planar(brd, (0.5, 0.0, 1.0, 1.0), ((W - 0.04) / 2, 0.003, 0.03), (-1, 0, 0), (0, 0, 1),
                           (W - 0.04, H - 0.06), normal=(0, 1, 0))
        objs.append(brd)
        for x in (-W / 2 + 0.01, W / 2 - 0.01):
            objs.append(G.rbox("leg", (0.02, 0.02, H), bevel=0.003, mat=frame_m, loc=(x, 0, 0)))
        for z in (0.02, H - 0.01):
            objs.append(G.rbox("rail", (W, 0.02, 0.02), bevel=0.003, mat=frame_m, loc=(0, 0, z - 0.01)))
        for o in objs:
            G.place(o, (0, 0, -H))
            G.place(o, (0, 0, 0), (side * TILT, 0, 0))
            G.place(o, (0, 0, H + 0.0))
        parts += objs
    hinge = G.cyl("hinge", 0.008, W + 0.02, loc=(0, 0, -(W + 0.02) / 2), segs=10, mat=frame_m)
    G.place(hinge, (0, 0, 0), (0, 90, 0))
    G.place(hinge, (0, 0, H))
    chain = G.tube("chain", [(-0.2, -0.2, 0.25), (-0.2, 0.0, 0.2), (-0.2, 0.2, 0.25)], 0.003, 5, mat=frame_m)
    parts += [hinge, chain]
    spread = math.tan(math.radians(TILT)) * H
    cols = [G.col_box("metal", (W, spread * 2, H * 0.98))]
    return parts, cols


@prop("sign_aframe_com", category="sign", surface="metal", mass=6.0, tags=["sign", "food"])
def sign_aframe_com():
    parts, cols = _aframe("sign_aframe_com", "#faf6e8")
    return {"parts": parts, "colliders": cols, "label": L("sign_aframe_com")}


@prop("sign_aframe_cafe", category="sign", surface="metal", mass=6.0, tags=["sign", "cafe"])
def sign_aframe_cafe():
    parts, cols = _aframe("sign_aframe_cafe", "#1c221e")
    return {"parts": parts, "colliders": cols, "label": L("sign_aframe_cafe")}


@prop("sign_lightbox", category="sign", surface="plastic", mass=9.0, tags=["sign", "light"], night_emission=2.2)
def sign_lightbox():
    alu = PN.metal("alu", "aluminium", dirt=0.6, dust=0.4, ground=0.6, wear=0.4)
    face = PN.label_only("lbface", "#fffaec", rough=0.3, role="lit", wear=0.15, dirt=0.35, dust=0.3)
    rub = PN.rubber("lbwheel", "#1a1a1a", dirt=0.6, ground=0.8)
    W, D, H, Z0 = 0.56, 0.2, 0.86, 0.14
    parts = []
    shell = G.rbox("shell", (W, D, H), bevel=0.015, segs=3, mat=alu)
    G.place(shell, (0, 0, Z0))
    parts.append(shell)
    for side in (-1, 1):
        pf = G.rbox("face", (W - 0.05, 0.004, H - 0.05), bevel=0.001, mat=face)
        G.place(pf, (0, side * (D / 2 + 0.001), Z0 + 0.025))
        if side < 0:
            G.label_planar(pf, (0.0, 0.0, 0.5, 1.0), (-(W - 0.05) / 2, -D / 2 - 0.003, Z0 + 0.025), (1, 0, 0),
                           (0, 0, 1), (W - 0.05, H - 0.05), normal=(0, -1, 0))
        else:
            G.label_planar(pf, (0.5, 0.0, 1.0, 1.0), ((W - 0.05) / 2, D / 2 + 0.003, Z0 + 0.025), (-1, 0, 0),
                           (0, 0, 1), (W - 0.05, H - 0.05), normal=(0, 1, 0))
        parts.append(pf)
    for x in (-W / 2 + 0.06, W / 2 - 0.06):
        leg = G.rbox("leg", (0.04, D - 0.02, Z0), bevel=0.006, mat=alu)
        parts.append(G.place(leg, (x, 0, 0)))
        w = G.lathe("wheel", [(0.0, -0.012), (0.035, -0.012), (0.04, 0.0), (0.035, 0.012), (0.0, 0.012)], 16, mat=rub)
        G.place(w, (0, 0, 0), (0, 90, 0))
        G.place(w, (x, D / 2 - 0.02, 0.04))
        parts.append(w)
    cable = G.tube("cable", [(0.0, 0.1, 0.16), (0.03, 0.18, 0.05), (0.15, 0.32, 0.008), (0.5, 0.5, 0.008)], 0.004, 6,
                   mat=rub)
    parts.append(cable)
    cols = [G.col_box("plastic", (W, D, H + Z0))]
    marks = [light_marker("LIGHT_01", (0, -0.25, 0.6), kind="omni", range=2.6, energy=0.5,
                          color=[1.0, 0.96, 0.88], shadow=False, fade=30.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("sign_lightbox")}


@prop("banner_standing", category="sign", surface="plastic", mass=12.0, tags=["sign", "fabric"])
def banner_standing():
    cloth = PN.fabric("flag", "#e21e28", weave_scale=1400, rough=0.8, fade=0.35, dirt=0.3, label=True,
                      label_wear=0.15, role="2s", wrinkle=0.2)
    pole_m = PN.metal("fpole", "aluminium", dirt=0.5, wear=0.5)
    base_m = PN.plastic("fbase", "#222222", rough=0.55, fade=0.3, dirt=0.7, dust=0.6, ground=0.7)
    parts = []
    base = G.lathe("base", [(0.0, 0.0), (0.27, 0.0), (0.28, 0.02), (0.26, 0.09), (0.12, 0.13), (0.05, 0.15),
                            (0.0, 0.15)], 6, mat=base_m, phase=math.pi / 6, smooth_angle=35)
    capb = G.cyl("fillcap", 0.035, 0.02, loc=(0.16, 0.0, 0.11), segs=14, mat=base_m)
    pole = G.cyl("pole", 0.012, 2.25, loc=(0, 0, 0.12), segs=12, bevel=0.0, mat=pole_m)
    bar = G.cyl("bar", 0.008, 0.56, loc=(0, 0, 0), segs=10, bevel=0.0, mat=pole_m)
    G.place(bar, (0, 0, 0), (0, 90, 0))
    G.place(bar, (0, 0, 2.3))
    FW, FH = 0.52, 1.85
    flag = G.grid("flag", FW, FH, 10, 30, mat=cloth)
    # grid is in XY; stand it up in XZ (facing -Y), add gentle wind ripples
    for v in flag.data.vertices:
        x, y = v.co.x, v.co.y
        u = (x + FW / 2) / FW
        v.co.x = x + FW / 2 + 0.015
        v.co.z = y + 0.45 + FH / 2
        v.co.y = 0.03 * math.sin(u * 5.0 + y * 2.0) * u + 0.01 * math.sin(y * 9.0)
    G.label_planar(flag, (0, 0, 1, 1), (0.015, 0, 0.45), (1, 0, 0), (0, 0, 1), (FW, FH), normal=None, bounds_pad=0.05)
    hem = G.tube("hem", [(0.015, 0.0, 0.45), (0.015, 0.0, 0.45 + FH)], 0.016, 10, mat=cloth)
    parts += [base, capb, pole, bar, flag, hem]
    cols = [G.col_cyl("plastic", 0.27, 0.15, segs=6), G.col_cyl("metal", 0.02, 2.2, loc=(0, 0, 0.15))]
    return {"parts": parts, "colliders": cols, "label": L("banner_trachanh")}
