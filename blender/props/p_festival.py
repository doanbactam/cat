"""Mid-Autumn (Trung thu) festival lanterns: star lanterns (đèn ông sao, cellophane on bamboo),
Hội An silk lanterns (round / oval), carp lantern (đèn cá chép), paper-lantern string.
Translucent skins use role "lit" (double-sided, backlit by day, emissive at night via the post-import);
bamboo / wood frames stay opaque. Hanging props: origin = hang point (top), geometry below z = 0."""
import json
import math
import os
import random
import sys

from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import props_geo as G  # noqa: E402
import props_nodes as PN  # noqa: E402
from props_bake import register  # noqa: E402

LABELS = os.path.join(HERE, "labels")


def L(name):
    return os.path.join(LABELS, name + ".png")


def light_marker(name, loc, **info):
    m = G.marker(name, loc)
    m["light_json"] = json.dumps(info)
    return m


def label_axial(ob, rect, z0, z1, a0=-math.pi, a1=math.pi, centre=(0, 0)):
    """Like label_cyl, but u runs along Z (z0..z1) and v around the axis (a0..a1)."""
    G.ensure_label_layers([ob])
    me = ob.data
    lay = me.uv_layers["LabelUV"]
    u0, v0, u1, v1 = rect
    for p in me.polygons:
        loops = []
        angs = []
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a = math.atan2(co.y - centre[1], co.x - centre[0])
            angs.append(a)
            loops.append((li, co))
        # faces straddling the seam: unwrap angles to one side
        if max(angs) - min(angs) > math.pi:
            angs = [a + 2 * math.pi if a < 0 else a for a in angs]
        for (li, co), a in zip(loops, angs):
            t = (co.z - z0) / (z1 - z0)
            s = (a - a0) / (a1 - a0)
            lay.data[li].uv = (u0 + t * (u1 - u0), v0 + s * (v1 - v0))


# ---------------------------------------------------------------------------
# Star lantern — two 5-point star frames joined by spacers, each face a shallow cellophane pyramid
# ---------------------------------------------------------------------------
STAR_SETS = {
    "red": ["#d8261f"] * 5,
    "yellow": ["#f2b81c"] * 5,
    "multi": ["#d8261f", "#f2b81c", "#2f8a3e", "#2a5fc0", "#e0569a"],
}


def star_lantern(colors="red"):
    cols = STAR_SETS[colors]
    bam = PN.bamboo("sbamboo", "#d1ad6c", axis="Z", node_spacing=0.6, dirt=0.3, aged=0.3, rough=0.5)
    paper = PN.paper("fringe", "#f3d24a", aged=0.2, label=False, role="2s", rough=0.7)
    films = [PN.film(f"film{i}", c, crinkle=0.7, rough=0.16, role="lit") for i, c in enumerate(cols)]
    tip = PN.paper("tipgold", "#e8c35a", aged=0.1, label=False, role="2s", rough=0.4)
    Ro, Ri, gap, bulge = 0.24, 0.1, 0.05, 0.085
    pts = [Vector((x, 0.0, y)) for (x, y) in G.star_points(5, Ro, Ri, 90.0)]
    hang = -0.02
    cz = -(Ro + 0.06)                 # star centre below the hang loop
    parts = []
    for side in (-1, 1):
        y = side * gap / 2
        frame = [tuple(p + Vector((0, y, cz))) for p in pts]
        parts.append(G.tube("frame", frame, 0.0035, 6, mat=bam, closed=True))
        apex = Vector((0, side * (gap / 2 + bulge), cz))
        # film: 10 triangles from the apex to the outline (each arm = 2 triangles, colour per arm)
        for i in range(10):
            a, b = pts[i] + Vector((0, y, cz)), pts[(i + 1) % 10] + Vector((0, y, cz))
            arm = ((i + 1) // 2) % 5 if i % 2 else (i // 2) % 5
            tri = G.sheet("film", [(0, 0), (1, 0), (0, 1)], mat=films[arm])
            me = tri.data
            me.vertices[0].co, me.vertices[1].co, me.vertices[2].co = apex, a, b
            me.update()
            parts.append(tri)
        # inner spokes (bamboo) from apex to the inner vertices — the frame of the pyramid
        for i in range(1, 10, 2):
            parts.append(G.tube("spoke", [tuple(apex), tuple(pts[i] + Vector((0, y, cz)))], 0.002, 5, mat=bam))
    # spacers between the two stars at the outer tips, paper tassel fringe at the 5 tips
    for i in range(0, 10, 2):
        p = pts[i] + Vector((0, 0, cz))
        parts.append(G.tube("spacer", [tuple(p + Vector((0, -gap / 2, 0))), tuple(p + Vector((0, gap / 2, 0)))], 0.003,
                            6, mat=bam))
        d = (pts[i]).normalized()
        if d.z > 0.9:
            continue
        for k in range(7):
            ang = (k - 3) * 0.09
            dd = Vector((d.x * math.cos(ang) - d.z * math.sin(ang), 0, d.x * math.sin(ang) + d.z * math.cos(ang)))
            strip = G.grid("fringe", 0.004, 0.11, 1, 6, mat=paper)
            G.place(strip, (0, 0.055, 0), (0, 0, 0))
            G.place(strip, (0, 0, 0), (90, 0, 0))
            # orient the strip along dd (initially along +Z after rotation)
            rot = Vector((0, 0, 1)).rotation_difference(dd).to_euler()
            G.place(strip, (0, 0, 0), tuple(math.degrees(x) for x in rot))
            G.place(strip, tuple(p))
            for v in strip.data.vertices:
                v.co.z -= 0.25 * ((v.co - p).length ** 2) * 6
            parts.append(strip)
        cone = G.lathe("tip", [(0.0, 0.0), (0.012, 0.0), (0.0, 0.03)], 8, mat=tip)
        rot = Vector((0, 0, 1)).rotation_difference(d).to_euler()
        G.place(cone, (0, 0, 0), tuple(math.degrees(x) for x in rot))
        G.place(cone, tuple(p))
        parts.append(cone)
    # top hanging loop (string) and the carrying stick socket under the bottom-left tip
    loop = G.tube("loop", [(math.cos(a) * 0.012, 0, hang - 0.012 + math.sin(a) * 0.012) for a in
                           [2 * math.pi * i / 12 for i in range(12)]], 0.0012, 5, mat=paper, closed=True)
    string = G.tube("string", [(0, 0, hang - 0.024), (0, 0, cz + Ro + 0.0)], 0.0012, 5, mat=paper)
    parts += [loop, string]
    for p in parts:
        G.uv_weight(p, 1.0)
    cols = [G.col_box("fabric", (2 * Ro, gap + 2 * bulge, 2 * Ro), loc=(0, 0, cz - Ro))]
    marks = [G.marker("HANG_01", (0, 0, 0)), light_marker("LIGHT_01", (0, 0, cz), kind="omni", range=2.2,
                                                          energy=0.35, color=[1.0, 0.62, 0.32], shadow=False,
                                                          fade=25.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "meta": {"origin": "hang_point"}}


for _c in STAR_SETS:
    register(f"star_lantern_{_c}", (lambda c=_c: star_lantern(c)), category="festival", kind="lantern",
             surface="fabric", material_kind="soft", mass=0.25, grounded=False, density=1024.0, max_tex=1024,
             tags=["festival", "lantern", "hanging", "light", "trung_thu"], night_emission=2.2,
             name_key="PROP_STAR_LANTERN")


# ---------------------------------------------------------------------------
# Hội An silk lanterns: bamboo ribs + stretched silk + turned-wood caps + tassel
# ---------------------------------------------------------------------------
def silk_lantern(shape="round", color="#c4202a", tassel="#d8a52a"):
    silkm = PN.silk("silk", color, rough=0.5, role="lit", pattern=True)
    rib = PN.bamboo("rib", "#6e4a2a", axis="Z", node_spacing=0.9, dirt=0.4, aged=0.6, rough=0.45)
    cap = PN.wood("cap", "#5a2e1a", axis="Z", varnish=0.8, dirt=0.4, weather_grey=0.05)
    tas = PN.fabric("tassel", tassel, weave_scale=3000, rough=0.7, role="2s", wrinkle=0.0)
    brass = PN.metal("lbrass", "brass", wear=0.5)
    if shape == "round":
        H, R, nrib = 0.34, 0.19, 16
        def rad(t):  # noqa: E306
            return R * math.sin(math.pi * (0.12 + 0.76 * t)) ** 0.85
    else:
        H, R, nrib = 0.46, 0.15, 12
        def rad(t):  # noqa: E306
            return R * math.sin(math.pi * (0.1 + 0.8 * t)) ** 0.7
    top = -0.1
    z0 = top - H
    prof = [(rad(i / 20), z0 + H * i / 20) for i in range(21)]

    def pleat(r, z, a):
        return r * (1 - 0.03 * (0.5 + 0.5 * math.cos(a * nrib)) ** 6)
    skin = G.lathe("silk", prof, nrib * 6, mat=silkm, rfunc=pleat, smooth_angle=None)
    G.label_cyl(skin, (0.0, 0.0, 1.0, 1.0), z0, z0 + H, a0=-math.pi, a1=math.pi)
    parts = [skin]
    for i in range(nrib):
        a = 2 * math.pi * i / nrib
        pts = [(math.cos(a) * (r + 0.0015), math.sin(a) * (r + 0.0015), z) for (r, z) in prof]
        parts.append(G.tube("rib", pts, 0.0022, 5, mat=rib))
    rt, rb = prof[-1][0], prof[0][0]
    capt = G.lathe("capt", [(0.0, top - 0.004), (rt + 0.012, top - 0.004), (rt + 0.014, top + 0.012), (rt * 0.6, top + 0.028),
                            (0.012, top + 0.05), (0.0, top + 0.05)], 24, mat=cap)
    capb = G.lathe("capb", [(0.0, z0 - 0.045), (0.016, z0 - 0.045), (rb * 0.7, z0 - 0.02), (rb + 0.014, z0 - 0.004),
                            (rb + 0.012, z0 + 0.006), (0.0, z0 + 0.006)], 24, mat=cap)
    hook = G.tube("hook", [(0, 0, top + 0.05), (0, 0, -0.012)], 0.0016, 6, mat=brass)
    ring = G.tube("ring", [(math.cos(a) * 0.009, 0, -0.009 + math.sin(a) * 0.009) for a in
                           [2 * math.pi * i / 12 for i in range(12)]], 0.0016, 6, mat=brass, closed=True)
    parts += [capt, capb, hook, ring]
    # tassel: knot bead + bundle of strands
    tz = z0 - 0.045
    parts.append(G.sphere("bead", 0.012, loc=(0, 0, tz - 0.02), mat=cap, segs=12, rings=8))
    rng = random.Random(5)
    for k in range(22):
        a = 2 * math.pi * k / 22
        rr = 0.008 + rng.uniform(0, 0.004)
        Ls = 0.22 + rng.uniform(-0.02, 0.02)
        parts.append(G.tube("strand", [(math.cos(a) * 0.006, math.sin(a) * 0.006, tz - 0.03),
                                       (math.cos(a) * rr, math.sin(a) * rr, tz - 0.06),
                                       (math.cos(a) * (rr + 0.01), math.sin(a) * (rr + 0.01), tz - 0.03 - Ls)],
                            0.0012, 4, mat=tas))
    parts.append(G.lathe("wrap", [(0.009, tz - 0.035), (0.0105, tz - 0.045), (0.0095, tz - 0.06)], 16, mat=brass))
    cols = [G.col_cyl("fabric", R, H + 0.15, loc=(0, 0, z0 - 0.05), segs=12)]
    marks = [G.marker("HANG_01", (0, 0, 0)),
             light_marker("LIGHT_01", (0, 0, z0 + H * 0.5), kind="omni", range=3.0, energy=0.55,
                          color=[1.0, 0.45, 0.28] if color != "#e6b22c" else [1.0, 0.72, 0.36], shadow=False,
                          fade=30.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("silk_pattern"),
            "meta": {"origin": "hang_point"}}


register("silk_lantern_round", lambda: silk_lantern("round", "#c4202a", "#d8a52a"), category="festival",
         kind="lantern", surface="fabric", material_kind="soft", mass=0.4, grounded=False, density=1024.0,
         max_tex=2048, tags=["festival", "lantern", "hanging", "light", "hoi_an"], night_emission=2.6)
register("silk_lantern_oval", lambda: silk_lantern("oval", "#e6b22c", "#b8202a"), category="festival",
         kind="lantern", surface="fabric", material_kind="soft", mass=0.4, grounded=False, density=1024.0,
         max_tex=2048, tags=["festival", "lantern", "hanging", "light", "hoi_an"], night_emission=2.6)


# ---------------------------------------------------------------------------
# Carp lantern (đèn cá chép): painted silk/paper over a bamboo body, flowing tail, hangs level
# ---------------------------------------------------------------------------
def carp_lantern():
    skin = PN.silk("carp", "#e8572a", rough=0.5, role="lit", pattern=True)
    fins = PN.film("cfin", "#f2a22a", crinkle=0.4, rough=0.3, role="lit")
    bam = PN.bamboo("cbam", "#c9a265", axis="Z", node_spacing=0.6, dirt=0.3)
    gold = PN.paper("cgold", "#e7c14e", aged=0.1, label=False, role="2s", rough=0.4)
    Lb, R = 0.52, 0.11
    prof = []
    for i in range(25):
        t = i / 24
        r = R * (math.sin(math.pi * min(1.0, 0.06 + t * 0.98)) ** 0.7) * (1.0 - 0.25 * (1 - t) ** 3)
        prof.append((max(r, 0.02), t * Lb))
    prof = [(0.0, 0.0)] + prof + [(0.0, Lb + 0.004)]
    body = G.lathe("body", prof, 40, mat=skin, smooth_angle=None,
                   rfunc=lambda r, z, a: r * (1.0 + 0.04 * math.cos(a * 2)))
    # scales sheet: u along the body; head (eyes at u~0.08) is the TOP of the lathe -> reverse range
    label_axial(body, (0.0, 0.0, 1.0, 1.0), Lb, 0.0, a0=-math.pi, a1=math.pi)
    ribs = []
    for k in range(8):
        a = 2 * math.pi * k / 8
        ribs.append(G.tube("rib", [(math.cos(a) * (r + 0.001), math.sin(a) * (r + 0.001), z) for (r, z) in prof[2:-2]],
                           0.0018, 4, mat=bam))
    parts = [body] + ribs
    # tail: two long lobes of film along -Z from the tail end, with gold ribs
    for s in (-1, 1):
        tail = G.grid("tail", 0.1, 0.34, 4, 10, mat=fins)
        for v in tail.data.vertices:
            t = (v.co.y + 0.17) / 0.34
            v.co = Vector((s * (0.01 + 0.09 * t) + v.co.x * (0.4 + 0.6 * t), 0.012 * math.sin(t * 5 + s),
                           -t * 0.34))
        parts.append(tail)
        for j in range(3):
            parts.append(G.tube("tailrib", [(s * 0.01, 0, -0.005), (s * (0.02 + 0.05 * j), 0.004, -0.2),
                                            (s * (0.03 + 0.07 * j), 0.0, -0.34)], 0.0014, 4, mat=gold))
    # dorsal & pectoral fins (film), whisker barbels (gold paper strips)
    # (before the final Ry(90) the back of the fish is -X)
    dors = G.grid("dorsal", 0.07, 0.26, 2, 8, mat=fins)
    G.place(dors, (0, 0, 0), (90, 0, 0))
    for v in dors.data.vertices:
        v.co.x -= 0.012 * math.sin(v.co.z * 30)
    G.place(dors, (-R * 0.95 - 0.03, 0, Lb * 0.45))
    parts.append(dors)
    for s in (-1, 1):
        pf = G.grid("pect", 0.08, 0.05, 3, 2, mat=fins)
        G.place(pf, (0, 0, 0), (0, 0, s * 30))
        G.place(pf, (R * 0.5, s * R * 0.9, Lb * 0.72))
        parts.append(pf)
        parts.append(G.tube("barbel", [(R * 0.2, s * 0.03, Lb - 0.01), (R * 0.5, s * 0.06, Lb + 0.04),
                                       (R * 0.9, s * 0.07, Lb + 0.06)], 0.0018, 4, mat=gold))
    # orient: lathe axis Z (tail at z=0, head at z=Lb) -> horizontal along +X (head forward), back up (+Z)
    for p in parts:
        G.place(p, (0, 0, 0), (0, 90, 0))
        G.place(p, (-Lb * 0.5, 0, 0))
    # hanging strings from two points on the back to the hang point
    mn, mx = G.bounds(parts)
    hang_h = 0.14
    for p in parts:
        G.place(p, (0, 0, -hang_h - mx.z))
    zt = -hang_h
    for x in (-0.12, 0.12):
        parts.append(G.tube("hstring", [(0, 0, -0.005), (x, 0, zt - 0.005)], 0.001, 4, mat=gold))
    parts.append(G.tube("hloop", [(math.cos(a) * 0.008, 0, -0.008 + math.sin(a) * 0.008) for a in
                                  [2 * math.pi * i / 12 for i in range(12)]], 0.0012, 5, mat=gold, closed=True))
    mn, mx = G.bounds(parts)
    cols = [G.col_box("fabric", (mx.x - mn.x, 2 * R, 2 * R), loc=(0, 0, zt - 2 * R))]
    marks = [G.marker("HANG_01", (0, 0, 0)),
             light_marker("LIGHT_01", (0, 0, zt - R), kind="omni", range=2.8, energy=0.5, color=[1.0, 0.55, 0.3],
                          shadow=False, fade=25.0)]
    return {"parts": parts, "colliders": cols, "markers": marks, "label": L("carp_scales"),
            "meta": {"origin": "hang_point"}}


register("carp_lantern", carp_lantern, category="festival", kind="lantern", surface="fabric", material_kind="soft",
         mass=0.35, grounded=False, density=1024.0, max_tex=2048, tags=["festival", "lantern", "hanging", "light",
                                                                         "trung_thu"], night_emission=2.4)


# ---------------------------------------------------------------------------
# Lantern string: 3.2 m cord with 7 small accordion paper lanterns (red / yellow), ATTACH ends
# ---------------------------------------------------------------------------
def lantern_string():
    cordm = PN.fabric("cord", "#2a2420", weave_scale=2500, rough=0.85, role="base", wrinkle=0.0)
    paper_r = PN.paper("pred", "#d42a22", aged=0.2, label=False, role="lit", rough=0.65, fibre=0.7)
    paper_y = PN.paper("pyel", "#efb425", aged=0.2, label=False, role="lit", rough=0.65, fibre=0.7)
    black = PN.paper("pblack", "#1d1a18", aged=0.1, label=False, role="base", rough=0.6)
    span, sag = 3.2, 0.28
    pts = G.catenary((-span / 2, 0, 0), (span / 2, 0, 0), sag, 40)
    # cord in 8 short pieces (one 3 m island would starve the UV atlas)
    parts = [G.tube("cord", [tuple(p) for p in pts[i:i + 6]], 0.0025, 6, mat=cordm, cap=False) for i in range(0, 40, 5)]
    n = 7
    for k in range(n):
        t = (k + 1) / (n + 1)
        x = -span / 2 + span * t
        zc = -sag * 4 * t * (1 - t)
        m = paper_r if k % 2 == 0 else paper_y
        R, H = 0.075, 0.13
        # accordion folds
        prof = [(R * math.sin(math.pi * (0.12 + 0.76 * i / 16)) ** 0.8 * (0.96 if i % 2 else 1.0), -H * i / 16)
                for i in range(17)]
        lan = G.lathe("lantern", prof, 24, mat=m, smooth_angle=None)
        topc = G.cyl("topcap", prof[0][0] + 0.004, 0.012, segs=24, bevel=0.001, mat=black)
        G.place(topc, (0, 0, -0.004))
        botc = G.cyl("botcap", prof[-1][0] + 0.004, 0.012, segs=24, bevel=0.001, mat=black)
        G.place(botc, (0, 0, -H - 0.008))
        drop = 0.06 + 0.02 * (k % 3)
        hang = G.tube("hang", [(0, 0, 0.0), (0, 0, drop)], 0.0012, 4, mat=cordm)
        tas = G.tube("tassel", [(0, 0, -H - 0.01), (0, 0, -H - 0.09)], 0.004, 6, mat=m, rfunc=lambda tt: 0.6 + 0.6 * tt)
        group = [lan, topc, botc, hang, tas]
        for g in group:
            G.place(g, (x, 0, zc - drop))
        parts += group
    cols = [G.col_box("fabric", (0.15, 0.15, 0.22), loc=(-span / 2 + span * (k + 1) / (n + 1), 0,
                                                       -sag * 4 * ((k + 1) / (n + 1)) * (1 - (k + 1) / (n + 1)) - 0.3))
            for k in range(n)]
    marks = [G.marker("ATTACH_01", (-span / 2, 0, 0)), G.marker("ATTACH_02", (span / 2, 0, 0))]
    for k in range(0, n, 2):
        t = (k + 1) / (n + 1)
        marks.append(light_marker(f"LIGHT_{k:02d}", (-span / 2 + span * t, 0, -sag * 4 * t * (1 - t) - 0.15),
                                  kind="omni", range=1.8, energy=0.25, color=[1.0, 0.5, 0.3], shadow=False, fade=20.0))
    return {"parts": parts, "colliders": cols, "markers": marks, "meta": {"origin": "string_centre",
                                                                          "span": span}}


register("lantern_string", lantern_string, category="festival", kind="lantern", surface="fabric",
         material_kind="soft", mass=1.2, grounded=False, density=768.0, max_tex=2048,
         tags=["festival", "lantern", "hanging", "light", "string"], night_emission=2.2)
