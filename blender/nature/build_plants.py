"""Build the small plants of the vehicles-nature area (shrubs, climbers, ferns, weeds, grass, moss,
lotus, water hyacinth, leaf litter).

    tools/blender_run.sh blender/nature/build_plants.py [-- id ... [--nopreview]]

Every asset uses the undergrowth atlas (blender/lib/nature_atlas.py) with the shared foliage
shader material (wind from vertex colour, translucency, wetness).  Origins: ground contact
(water level for aquatic plants).  Small ground-cover meshes are named "small_*" so the post-import
script gives them a visibility range.
"""
from __future__ import annotations

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common as C            # noqa: E402
import nature_atlas as NA     # noqa: E402
import nature_godot as G      # noqa: E402
import nature_tree as T       # noqa: E402

OUT = "models/nature"
CATALOG = C.asset_path(f"{OUT}/catalog.json")
UG = "undergrowth"
UP = Vector((0, 0, 1))


def uv(cell, sub=None):
    return NA.cell_uv(UG, cell, sub)


def size(cell, sc=1.0):
    w, h = NA.cell(UG, cell)["size"]
    return (w * sc, h * sc)


def fol():
    return T.foliage_material(UG)


def finish(pid, objs, kind, extra, preview, view=None, cols=()):
    path = C.asset_path(f"{OUT}/{pid}.glb")
    G.export_glb(path, list(objs) + list(cols))
    G.glb_import(path, "nature")
    st = G.glb_stats(path)
    xs, ys, zs = [], [], []
    for o in objs:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    e = {"id": pid, "file": f"res://assets/models/nature/{pid}.glb", "kind": kind,
         "width": round(max(xs) - min(xs), 2), "depth": round(max(ys) - min(ys), 2), "height": round(max(zs), 2),
         "footprint": [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)], "floors": 0, "style": "nature",
         "climb_points": [], "nap_spots": [], "entrances": [], "tris": st["tris"], "materials": st["materials"],
         "dynamic": False, "mass": 0.0, "surface": "grass", "wind": True, "collision": bool(cols)}
    e.update(extra)
    G.write_catalog(CATALOG, [e])
    print(f"BUILT {pid}: tris={st['tris']} {e['width']}x{e['depth']}x{e['height']}")
    if preview:
        v = view or {}
        h = max(e["height"], 0.2)
        C.preview_render(C.qa_path(f"vehicles-nature/plant_{pid}.png"), target=v.get("target", (0, 0, h * 0.4)),
                         distance=v.get("distance", max(h, e["width"]) * 2.2), yaw_deg=v.get("yaw", 25),
                         pitch_deg=v.get("pitch", 20), res=(480, 400), samples=24, lens=40, world_strength=0.9)
    return e


def core_mat():
    """Dark inner-canopy material: hides the see-through gaps between leaf cards (self-shadowed foliage)."""
    return C.principled("nmat_foliage_core", (0.018, 0.035, 0.012), 0.9)


def core_blob(name, c, r):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in bm.verts:
        v.co = Vector((c.x + v.co.x * r[0], c.y + v.co.y * r[1], max(0.02, c.z + v.co.z * r[2])))
    ob = C.mesh_from_bmesh(name, bm)
    ob.data.materials.append(core_mat())
    return ob


def dome_cards(lm, rng, n, radius, height, cells, center=Vector((0, 0, 0)), sc=(0.9, 1.3), bend=0.25, up=0.35,
               w_base=0.2):
    """Cards on a squashed hemisphere, pointing outward (shrubs / hedges)."""
    cc = center + Vector((0, 0, height * 0.35))
    for i in range(n):
        z = rng.uniform(0.05, 1.0) ** 0.7
        a = rng.uniform(0, math.tau)
        rr = math.sqrt(max(0.0, 1 - z * z))
        p = center + Vector((math.cos(a) * rr * radius * rng.uniform(0.5, 0.95), math.sin(a) * rr * radius *
                             rng.uniform(0.5, 0.95), z * height * rng.uniform(0.55, 0.85)))
        out = (p - cc).normalized()
        axis = (out + UP * up + T._rand_unit(rng) * 0.4).normalized()
        side = axis.cross(UP)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        normal = (Quaternion(axis, rng.uniform(-1.0, 1.0)) @ side.normalized()).normalized()
        cell = T.pick(rng, cells)
        T.card(lm, p - axis * 0.05, axis, normal, size(cell, rng.uniform(*sc)), uv(cell), NA.cell(UG, cell)["pivot"],
               bend=bend * rng.uniform(0.6, 1.3), wind_base=w_base + 0.25 * z, phase=rng.random(), center=cc, blend=0.6)


def stems(mb, rng, n, radius, height, r0=0.012):
    for i in range(n):
        a = rng.uniform(0, math.tau)
        d = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 1.0)).normalized()
        pts, radii = T.grow(Vector((rng.gauss(0, 0.03), rng.gauss(0, 0.03), 0)), d, height * rng.uniform(0.5, 0.8),
                            r0, 0.3, 0.12, 0.2, 0.25, 0.1, rng, Vector((0, 0, 0)))
        T.sweep(mb, pts, radii, sides=5, tile=(0.2, 0.5), wind_fn=lambda t: (0.25 * t, 0.5, 0.0), cap=True)


# ---------------------------------------------------------------------------
def shrub_ixora(preview):
    C.reset_scene()
    rng = random.Random(101)
    mb = T.MeshBuilder("shrub_ixora_stems")
    stems(mb, rng, 9, 0.5, 0.85)
    bark = mb.finish([T.bark_material("bark_smooth")])
    lm = T.MeshBuilder("shrub_ixora_leaves")
    dome_cards(lm, rng, 150, 0.55, 0.9, [("ixora", 5), ("ixora_flowers", 2), ("hedge", 1)])
    leaves = lm.finish([fol()], custom_normals=True)
    core = core_blob("shrub_ixora_core", Vector((0, 0, 0.36)), (0.42, 0.42, 0.34))
    return finish("shrub_ixora", [bark, leaves, core], "shrub", {"name_key": "NATURE_IXORA", "cover": True,
                                                           "species": "Ixora coccinea"}, preview)


def hedge_trimmed(preview):
    C.reset_scene()
    rng = random.Random(102)
    lm = T.MeshBuilder("hedge_trimmed_leaves")
    L, W, H = 1.6, 0.55, 0.85
    cc = Vector((0, 0, H * 0.5))
    for i in range(420):
        f = rng.random()
        if f < 0.3:      # top
            p = Vector((rng.uniform(-L / 2, L / 2), rng.uniform(-W / 2, W / 2), H - rng.uniform(0, 0.08)))
            nrm = UP
        else:            # sides
            sx = rng.choice([-1, 1])
            if rng.random() < 0.75:
                p = Vector((rng.uniform(-L / 2, L / 2), sx * (W / 2 - rng.uniform(0, 0.06)), rng.uniform(0.05, H)))
                nrm = Vector((0, sx, 0))
            else:
                p = Vector((sx * (L / 2 - rng.uniform(0, 0.06)), rng.uniform(-W / 2, W / 2), rng.uniform(0.05, H)))
                nrm = Vector((sx, 0, 0))
        axis = (nrm * 0.6 + UP * 0.5 + T._rand_unit(rng) * 0.5).normalized()
        side = axis.cross(nrm)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        normal = side.cross(axis).normalized()
        T.card(lm, p - axis * 0.12, axis, normal, size("hedge", rng.uniform(0.8, 1.1)), uv("hedge"), "bottom",
               bend=0.15, wind_base=0.1 + 0.15 * p.z / H, phase=rng.random(), center=cc, blend=0.7)
    leaves = lm.finish([fol()], custom_normals=True)
    core = C.box("hedge_trimmed_core", (L - 0.14, W - 0.14, H - 0.1), (0, 0, 0.0))
    core.data.materials.append(core_mat())
    col = T.box_collider("col_grass_hedge", Vector((0, 0, H * 0.45)), (L * 0.92, W * 0.85, H * 0.9))
    return finish("hedge_trimmed", [leaves, core], "shrub", {"name_key": "NATURE_HEDGE", "cover": False,
                                                       "nap_spots": [[0.0, H, 0.0]]}, preview, cols=[col])


def bougainvillea_wall(preview):
    """Woody climber trained up a wall (wall plane at y = +0.06 behind the plant), magenta bracts."""
    C.reset_scene()
    rng = random.Random(103)
    mb = T.MeshBuilder("bougainvillea_wall_stems")
    W, H = 3.0, 3.4
    tips = []
    for i in range(6):
        x0 = rng.uniform(-0.15, 0.15)
        pts = [Vector((x0, 0.0, 0.0))]
        tx = (i / 5 - 0.5) * W * 0.9
        n = 16
        for k in range(1, n + 1):
            f = k / n
            pts.append(Vector((x0 + (tx - x0) * f ** 1.4 + math.sin(f * 9 + i) * 0.06, 0.02 + 0.02 * math.sin(f * 7),
                               H * (0.55 + 0.4 * rng.random()) * f)))
        radii = [0.035 * (1 - 0.75 * k / n) for k in range(n + 1)]
        T.sweep(mb, pts, radii, sides=6, tile=(0.3, 0.6), wind_fn=lambda t: (0.15 * t, 0.3, 0.0), cap=True)
        tips += pts[6:]
    bark = mb.finish([T.bark_material("bark_furrowed")])
    lm = T.MeshBuilder("bougainvillea_wall_leaves")
    cc = Vector((0, -1.0, H * 0.5))
    for i in range(150):
        base = rng.choice(tips)
        p = base + Vector((rng.gauss(0, 0.35), rng.uniform(-0.18, 0.0), rng.gauss(0, 0.25)))
        p.z = max(0.4, min(H + 0.2, p.z))
        axis = (Vector((rng.gauss(0, 0.6), -0.5, rng.uniform(-0.3, 1.0)))).normalized()
        if p.z > H * 0.85:
            axis = (axis + Vector((0, -0.6, -0.9))).normalized()       # arching, drooping crown spill
        normal = Vector((rng.gauss(0, 0.3), -1.0, rng.gauss(0, 0.3))).normalized()
        cell = "bougainvillea_b" if rng.random() < 0.6 else "bougainvillea_a"
        T.card(lm, p, axis, normal, size(cell, rng.uniform(1.0, 1.5)), uv(cell), "bottom", bend=0.2,
               wind_base=0.25 + 0.2 * p.z / H, phase=rng.random(), center=cc, blend=0.35)
    leaves = lm.finish([fol()], custom_normals=True)
    return finish("bougainvillea_wall", [bark, leaves], "climber", {"name_key": "NATURE_BOUGAINVILLEA",
                                                                     "species": "Bougainvillea spectabilis",
                                                                     "mount": "wall_back_+z"}, preview,
                  {"yaw": 15, "pitch": 8, "target": (0, 0, 1.6), "distance": 7})


def bougainvillea_cascade(preview):
    """Hangs from a balcony rail / wall top: origin at the rail top, spills down 2 m."""
    C.reset_scene()
    rng = random.Random(104)
    mb = T.MeshBuilder("bougainvillea_cascade_stems")
    lm = T.MeshBuilder("bougainvillea_cascade_leaves")
    W = 2.2
    cc = Vector((0, -0.8, -0.8))
    for i in range(9):
        x = (i / 8 - 0.5) * W
        pts = [Vector((x, 0.1, 0.05))]
        d = Vector((rng.gauss(0, 0.2), -0.7, 0.4)).normalized()
        for k in range(10):
            d = (d + Vector((0, 0, -0.32))).normalized()
            pts.append(pts[-1] + d * rng.uniform(0.17, 0.24))
        T.sweep(mb, pts, [0.02 * (1 - 0.7 * k / 10) for k in range(11)], sides=5, tile=(0.3, 0.6),
                wind_fn=lambda t: (0.2 + 0.6 * t, rng.random(), 0.0), cap=True)
        for k in range(2, 11):
            p = pts[k]
            for j in range(2):
                q = p + Vector((rng.gauss(0, 0.12), rng.gauss(-0.05, 0.08), rng.gauss(0, 0.1)))
                axis = Vector((rng.gauss(0, 0.5), -0.6, rng.uniform(-1.0, 0.2))).normalized()
                normal = Vector((rng.gauss(0, 0.3), -1.0, 0.3)).normalized()
                cell = "bougainvillea_b" if rng.random() < 0.65 else "bougainvillea_a"
                T.card(lm, q, axis, normal, size(cell, rng.uniform(1.0, 1.4)), uv(cell), "bottom", bend=0.15,
                       wind_base=0.3 + 0.06 * k, phase=rng.random(), center=cc, blend=0.35)
    bark = mb.finish([T.bark_material("bark_furrowed")])
    leaves = lm.finish([fol()], custom_normals=True)
    return finish("bougainvillea_cascade", [bark, leaves], "climber",
                  {"name_key": "NATURE_BOUGAINVILLEA", "mount": "rail_top_origin"}, preview,
                  {"yaw": 20, "pitch": 5, "target": (0, 0, -0.8), "distance": 6})


def fern_clump(preview):
    C.reset_scene()
    rng = random.Random(105)
    lm = T.MeshBuilder("fern_clump_fronds")
    n = 26
    for i in range(n):
        a = i / n * math.tau + rng.uniform(-0.2, 0.2)
        out = Vector((math.cos(a), math.sin(a), 0))
        elev = rng.uniform(0.6, 1.25)
        axis = (out * math.cos(elev) + UP * math.sin(elev)).normalized()
        normal = (UP - axis * UP.dot(axis)).normalized()
        normal = (Quaternion(axis, rng.uniform(-0.4, 0.4)) @ normal)
        cell = rng.choice(["fern_a", "fern_b"])
        T.card(lm, Vector((0, 0, 0.02)) + out * 0.04, axis, normal, size(cell, rng.uniform(0.8, 1.2)), uv(cell),
               "bottom", bend=rng.uniform(0.35, 0.6), wind_base=0.1, phase=rng.random(), center=Vector((0, 0, -0.3)),
               blend=0.4, rows=4)
    leaves = lm.finish([fol()], custom_normals=True)
    return finish("fern_clump", [leaves], "groundcover", {"name_key": "NATURE_FERN", "cover": True}, preview)


def grass_tuft(pid, preview, cells, n, sc):
    C.reset_scene()
    rng = random.Random(sum(map(ord, pid)))
    lm = T.MeshBuilder(f"small_{pid}")
    for i in range(n):
        a = i / n * math.pi + rng.uniform(-0.3, 0.3)
        axis = (UP + T._rand_unit(rng) * 0.15).normalized()
        normal = Vector((math.cos(a), math.sin(a), 0))
        cell = rng.choice(cells)
        T.card(lm, Vector((rng.gauss(0, 0.03), rng.gauss(0, 0.03), -0.01)), axis, normal,
               size(cell, rng.uniform(*sc)), uv(cell), "bottom", bend=0.1, wind_base=0.05, phase=rng.random(),
               center=Vector((0, 0, -0.2)), blend=0.5)
    leaves = lm.finish([fol()], custom_normals=True)
    return finish(pid, [leaves], "groundcover", {"name_key": "NATURE_GRASS"}, preview, {"distance": 1.2})


def weeds_crack(pid, preview, length):
    """Weeds + grass growing along a crack / wall foot (line along X, length m)."""
    C.reset_scene()
    rng = random.Random(sum(map(ord, pid)) + 7)
    lm = T.MeshBuilder(f"small_{pid}")
    k = int(length * 9)
    for i in range(k):
        x = (i / max(1, k - 1) - 0.5) * length + rng.gauss(0, 0.03)
        cell = T.pick(rng, [("weed", 3), ("grass_b", 3), ("grass_a", 1), ("fern_b", 0.3)])
        sc = rng.uniform(0.45, 0.8) if cell != "fern_b" else rng.uniform(0.3, 0.45)
        a = rng.uniform(0, math.pi)
        T.card(lm, Vector((x, rng.gauss(0, 0.02), -0.005)), (UP + T._rand_unit(rng) * 0.25).normalized(),
               Vector((math.cos(a), math.sin(a), 0)), size(cell, sc), uv(cell), "bottom", bend=0.15,
               wind_base=0.05, phase=rng.random(), center=Vector((x, 0, -0.2)), blend=0.5)
    leaves = lm.finish([fol()], custom_normals=True)
    return finish(pid, [leaves], "groundcover", {"name_key": "NATURE_WEEDS"}, preview, {"distance": 1.6})


def moss_patch(preview):
    C.reset_scene()
    rng = random.Random(106)
    lm = T.MeshBuilder("small_moss_patch")
    for i in range(7):
        p = Vector((rng.gauss(0, 0.25), rng.gauss(0, 0.25), 0.003 + i * 0.0015))
        a = rng.uniform(0, math.tau)
        T.card(lm, p, Vector((math.cos(a), math.sin(a), 0)), UP, size("moss", rng.uniform(0.7, 1.4)), uv("moss"),
               "center", bend=-0.02, wind_base=0.0, phase=0.0, center=None, rows=3)
    leaves = lm.finish([fol()], custom_normals=False)
    return finish("moss_patch", [leaves], "groundcover", {"name_key": "NATURE_MOSS", "wind": False}, preview,
                  {"distance": 1.6, "pitch": 45})


def leaf_litter(preview):
    C.reset_scene()
    rng = random.Random(107)
    lm = T.MeshBuilder("small_litter_leaves")
    for i in range(140):
        r = 0.8 * math.sqrt(rng.random())
        a = rng.uniform(0, math.tau)
        p = Vector((math.cos(a) * r, math.sin(a) * r * 0.8, 0.004 + rng.uniform(0, 0.012)))
        sub = rng.randrange(16)
        sc = rng.uniform(0.07, 0.12)
        ax = rng.uniform(0, math.tau)
        axis = Vector((math.cos(ax), math.sin(ax), rng.uniform(-0.05, 0.08))).normalized()
        nrm = (UP + T._rand_unit(rng) * 0.15).normalized()
        T.card(lm, p - axis * sc * 0.5, axis, nrm, (sc, sc), uv("fallen_leaves", (4, 4, sub)), "bottom",
               bend=-0.12, wind_base=0.0, phase=rng.random(), center=None, rows=2, cup=rng.uniform(0.2, 0.6))
    leaves = lm.finish([fol()], custom_normals=False)
    return finish("leaf_litter", [leaves], "litter", {"name_key": "NATURE_LITTER", "wind": False, "surface": "dirt"},
                  preview, {"distance": 2.2, "pitch": 40})


# ---------------------------------------------------------------------------
# aquatic (origin at the water surface)
# ---------------------------------------------------------------------------
def pad(mb, c, r, rng, tilt=0.0, wind=0.1, raised=False):
    """Lotus leaf: radial disc with a slightly up-turned rim (raised ones are cupped like umbrellas)."""
    u0, v0, u1, v1 = uv("lotus_pad")
    seg, rings = 20, 3
    rot = rng.uniform(0, math.tau)
    tq = Quaternion(Vector((math.cos(rot), math.sin(rot), 0)), tilt)
    centre_v = mb.vert(c + Vector((0, 0, 0.004)), (wind, 0.3, 0.0), UP)
    prev = None
    ring_list = []
    for ri in range(1, rings + 1):
        f = ri / rings
        ring = []
        for k in range(seg + 1):
            a = k / seg * math.tau + rot
            lift = (f ** 2) * (0.04 if not raised else -0.08) * r / 0.25
            p = c + tq @ Vector((math.cos(a) * r * f, math.sin(a) * r * f, lift))
            uu = 0.5 + 0.5 * f * math.cos(k / seg * math.tau)
            vv = 0.5 + 0.5 * f * math.sin(k / seg * math.tau)
            ring.append((mb.vert(p, (wind, 0.3, f * 0.6), (tq @ UP).normalized()),
                         (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv)))
        ring_list.append(ring)
    cuv = ((u0 + u1) / 2, (v0 + v1) / 2)
    for k in range(seg):
        a, b = ring_list[0][k], ring_list[0][k + 1]
        mb.face([centre_v, a[0], b[0]], [cuv, a[1], b[1]])
    for ri in range(rings - 1):
        for k in range(seg):
            a, b = ring_list[ri][k], ring_list[ri][k + 1]
            cc, d = ring_list[ri + 1][k + 1], ring_list[ri + 1][k]
            mb.face([a[0], d[0], cc[0], b[0]], [a[1], d[1], cc[1], b[1]])


def lotus_flower(mb, c, rng, scale=1.0, open_=1.0):
    for ring, (n, elev, sz) in enumerate([(8, 0.55, 1.0), (8, 0.85, 0.92), (6, 1.15, 0.8)]):
        for k in range(n):
            a = k / n * math.tau + ring * 0.35
            out = Vector((math.cos(a), math.sin(a), 0))
            e = elev + (1 - open_) * 0.6
            axis = (out * math.cos(e) + UP * math.sin(e)).normalized()
            normal = (UP - axis * UP.dot(axis)).normalized()
            sub = rng.choice([0, 1])
            s = 0.1 * sz * scale
            T.card(mb, c + out * 0.015 * scale, axis, normal, (s * 0.65, s), uv("lotus_petal", (2, 2, sub)), "bottom",
                   bend=-0.15, wind_base=0.15, phase=0.4, center=c - Vector((0, 0, 0.1)), blend=0.3, cup=0.6)
    if open_ > 0.5:
        T.card(mb, c + Vector((0, 0, 0.035 * scale)), Vector((1, 0, 0)), UP, (0.05 * scale, 0.05 * scale),
               uv("lotus_petal", (2, 2, 2)), "center", bend=0.0, wind_base=0.15, phase=0.4, center=None)
        T.card(mb, c + Vector((0, 0, 0.03 * scale)), Vector((1, 0, 0)), UP, (0.08 * scale, 0.08 * scale),
               uv("lotus_petal", (2, 2, 3)), "center", bend=0.0, wind_base=0.15, phase=0.4, center=None)


def lotus_cluster(preview):
    C.reset_scene()
    rng = random.Random(108)
    lm = T.MeshBuilder("lotus_cluster_leaves")
    sm = T.MeshBuilder("lotus_cluster_stems")
    for i in range(11):
        r = 1.0 * math.sqrt(rng.random())
        a = rng.uniform(0, math.tau)
        c = Vector((math.cos(a) * r, math.sin(a) * r, 0.0))
        if rng.random() < 0.35:   # emergent leaf held above the water on its petiole
            h = rng.uniform(0.25, 0.7)
            top = c + Vector((rng.gauss(0, 0.05), rng.gauss(0, 0.05), h))
            T.sweep(sm, [c - Vector((0, 0, 0.3)), c + Vector((0, 0, h * 0.5)), top], [0.008, 0.007, 0.006], sides=5,
                    tile=(0.1, 0.5), wind_fn=lambda t: (0.3 * t, 0.2, 0.0), cap=False)
            pad(lm, top, rng.uniform(0.18, 0.28), rng, tilt=rng.uniform(0.1, 0.4), wind=0.4, raised=True)
        else:
            pad(lm, c + Vector((0, 0, 0.002 + i * 0.0006)), rng.uniform(0.17, 0.3), rng, tilt=0.0, wind=0.05)
    for i in range(4):
        a = rng.uniform(0, math.tau)
        c = Vector((math.cos(a) * 0.6, math.sin(a) * 0.6, 0))
        h = rng.uniform(0.45, 0.8)
        top = c + Vector((rng.gauss(0, 0.04), rng.gauss(0, 0.04), h))
        T.sweep(sm, [c - Vector((0, 0, 0.3)), c + Vector((0, 0, h * 0.5)), top], [0.007, 0.006, 0.005], sides=5,
                tile=(0.1, 0.5), wind_fn=lambda t: (0.35 * t, 0.6, 0.0), cap=False)
        lotus_flower(lm, top, rng, rng.uniform(0.9, 1.15), open_=1.0 if i < 3 else 0.0)
    stem_mat = C.principled("nmat_lotus_stem", (0.2, 0.3, 0.1), 0.5)
    stems_o = sm.finish([stem_mat])
    leaves = lm.finish([fol()], custom_normals=True)
    return finish("lotus_cluster", [stems_o, leaves], "aquatic", {"name_key": "NATURE_LOTUS", "surface": "water",
                                                                  "origin": "water_surface"}, preview,
                  {"distance": 3.2, "pitch": 25, "target": (0, 0, 0.25)})


def water_hyacinth(preview):
    C.reset_scene()
    rng = random.Random(109)
    lm = T.MeshBuilder("water_hyacinth_leaves")
    for r_i in range(22):
        c = Vector((rng.gauss(0, 0.45), rng.gauss(0, 0.45), 0.0))
        for k in range(6):
            a = k / 6 * math.tau + rng.uniform(-0.3, 0.3)
            out = Vector((math.cos(a), math.sin(a), 0))
            axis = (out * 0.45 + UP).normalized()
            normal = out.cross(UP).cross(axis).normalized() * -1
            T.card(lm, c, axis, normal, size("hyacinth_leaf", rng.uniform(1.6, 2.3)), uv("hyacinth_leaf"), "bottom",
                   bend=0.05, wind_base=0.1, phase=rng.random(), center=c - Vector((0, 0, 0.1)), blend=0.4)
        if rng.random() < 0.45:
            for j in range(2):
                a = j * math.pi / 2
                T.card(lm, c, UP, Vector((math.cos(a), math.sin(a), 0)), size("hyacinth_flower", rng.uniform(1.0, 1.3)),
                       uv("hyacinth_flower"), "bottom", bend=0.0, wind_base=0.15, phase=rng.random(), center=None)
    leaves = lm.finish([fol()], custom_normals=True)
    return finish("water_hyacinth", [leaves], "aquatic", {"name_key": "NATURE_HYACINTH", "surface": "water",
                                                           "origin": "water_surface"}, preview,
                  {"distance": 2.4, "pitch": 30})


BUILDERS = {
    "shrub_ixora": shrub_ixora, "hedge_trimmed": hedge_trimmed, "bougainvillea_wall": bougainvillea_wall,
    "bougainvillea_cascade": bougainvillea_cascade, "fern_clump": fern_clump,
    "grass_tuft_a": lambda pv: grass_tuft("grass_tuft_a", pv, ["grass_a"], 5, (0.8, 1.2)),
    "grass_tuft_b": lambda pv: grass_tuft("grass_tuft_b", pv, ["grass_b", "grass_a"], 4, (0.7, 1.0)),
    "weeds_crack_a": lambda pv: weeds_crack("weeds_crack_a", pv, 0.8),
    "weeds_crack_b": lambda pv: weeds_crack("weeds_crack_b", pv, 1.6),
    "moss_patch": moss_patch, "leaf_litter": leaf_litter, "lotus_cluster": lotus_cluster,
    "water_hyacinth": water_hyacinth,
}

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--nopreview" not in argv
    ids = [a for a in argv if not a.startswith("--")] or list(BUILDERS)
    for pid in ids:
        BUILDERS[pid](preview)
