"""Build every tree of the vehicles-nature area.

    tools/blender_run.sh blender/nature/build_trees.py [-- tree_id ... [--preview] [--nopreview]]

Trees: banyan (cây đa), flame_tree (phượng vĩ), sao_tree (sao đen street tree), frangipani (hoa sứ),
coconut_palm, areca_palm, weeping_willow, bamboo_clump.  Each -> assets/models/nature/<id>.glb
(+ .import using the nature post-import script) and an entry merged into assets/models/nature/catalog.json.
Requires the textures from blender/nature/gen_textures.py and materials from write_materials.py.
"""
from __future__ import annotations

import math
import os
import random
import sys

import bpy
from mathutils import Quaternion, Vector  # noqa: F401

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common as C            # noqa: E402
import nature_atlas as NA     # noqa: E402
import nature_godot as G      # noqa: E402
import nature_tree as T       # noqa: E402
from nature_tree import Level, Species  # noqa: E402

OUT = "models/nature"
CATALOG = C.asset_path(f"{OUT}/catalog.json")

# ---------------------------------------------------------------------------
# species
# ---------------------------------------------------------------------------
SAO = Species(
    "sao_tree", trunk_height=11.0, trunk_radius=0.3, trunk_lean=0.03, trunk_wander=0.03, trunk_grav=0.05,
    trunk_seg=0.5, trunk_tip_ratio=0.22, bark="bark_furrowed", atlas="leaf_sao",
    cards=[("sprig_a", 1), ("sprig_b", 1), ("sprig_c", 1), ("sprig_d", 1)], card_scale=(1.1, 1.6),
    card_levels=(2, 3), card_spacing=0.2, card_span=(0.2, 1.0), card_bend=0.2, card_up=0.35,
    sides_max=18, buttress=0.18, buttress_lobes=5, buttress_height=0.5, lumpy=0.03,
    levels=[
        Level(count=(13, 16), span=(0.4, 1.0), angle=(40, 65), length=(0.36, 0.5), len_taper=0.65,
              radius_ratio=0.5, grav=0.08, wander=0.12, photo=0.05, seg=0.45, tip_ratio=0.3),
        Level(count=(6, 8), span=(0.2, 1.0), angle=(35, 60), length=(0.38, 0.55), radius_ratio=0.65, grav=0.12,
              wander=0.2, seg=0.35, tip_ratio=0.35),
        Level(count=(3, 5), span=(0.3, 1.0), angle=(30, 55), length=(0.4, 0.6), radius_ratio=0.7, grav=0.2,
              wander=0.25, seg=0.3, tip_ratio=0.4, min_radius=0.0025),
    ])

BANYAN = Species(
    "banyan", trunk_height=5.0, trunk_radius=1.15, trunk_lean=0.06, trunk_wander=0.04, trunk_grav=0.0,
    trunk_seg=0.35, trunk_tip_ratio=0.62, bark="bark_banyan", atlas="leaf_banyan",
    cards=[("sprig_a", 3), ("sprig_figs", 2), ("sprig_c", 2)], card_scale=(1.4, 2.0),
    card_levels=(2, 3), card_spacing=0.28, card_span=(0.2, 1.0), card_bend=0.18, card_up=0.25,
    sides_max=30, buttress=0.55, buttress_lobes=7, buttress_height=0.9, lumpy=0.1, normal_blend=0.6,
    levels=[
        Level(count=(8, 9), span=(0.55, 1.0), angle=(50, 78), length=(7.0, 9.5), abs_len=True, len_taper=0.2,
              radius_ratio=0.46, grav=0.05, wander=0.1, photo=0.06, seg=0.5, tip_ratio=0.22),
        Level(count=(6, 8), span=(0.15, 1.0), angle=(35, 65), length=(0.35, 0.55), radius_ratio=0.6, grav=0.15,
              wander=0.22, seg=0.4, tip_ratio=0.3),
        Level(count=(4, 6), span=(0.25, 1.0), angle=(30, 60), length=(0.35, 0.55), radius_ratio=0.7, grav=0.2,
              wander=0.25, seg=0.3, tip_ratio=0.4, min_radius=0.0025),
    ])

FLAME = Species(
    "flame_tree", trunk_height=3.4, trunk_radius=0.36, trunk_lean=0.08, trunk_wander=0.06, trunk_grav=0.0,
    trunk_seg=0.35, trunk_tip_ratio=0.55, bark="bark_smooth", atlas="leaf_flame",
    cards=[("frond_a", 2), ("frond_b", 2), ("flowers", 3), ("frond_flowers", 4)], card_scale=(1.3, 1.8),
    card_levels=(2, 3), card_spacing=0.15, card_span=(0.15, 1.0), card_bend=0.12, card_up=0.75,
    sides_max=20, buttress=0.3, buttress_lobes=6, buttress_height=0.6, lumpy=0.05,
    levels=[
        Level(count=(5, 6), span=(0.75, 1.0), angle=(48, 72), length=(4.0, 5.8), abs_len=True, len_taper=0.1,
              radius_ratio=0.62, grav=0.12, wander=0.1, photo=0.08, seg=0.45, tip_ratio=0.25),
        Level(count=(5, 7), span=(0.25, 1.0), angle=(35, 60), length=(0.38, 0.55), radius_ratio=0.62, grav=0.06,
              wander=0.2, photo=0.05, seg=0.35, tip_ratio=0.32),
        Level(count=(4, 6), span=(0.3, 1.0), angle=(30, 55), length=(0.35, 0.5), radius_ratio=0.7, grav=0.02,
              wander=0.25, seg=0.3, tip_ratio=0.4, min_radius=0.0025),
    ])

FRANGIPANI = Species(
    "frangipani", trunk_height=1.1, trunk_radius=0.15, trunk_lean=0.1, trunk_wander=0.05, trunk_grav=0.0,
    trunk_seg=0.2, trunk_tip_ratio=0.85, bark="bark_smooth", atlas="leaf_frangipani",
    cards=[], card_scale=(0.85, 1.15), card_levels=(3,),
    card_spacing=5.0, card_span=(1.0, 1.0), card_bend=0.25, card_up=0.8, sides_max=14, lumpy=0.04,
    tip_cards=[("rosette_flowers", 1, 0, 0), ("leaf_side", 4, 35, 0.8), ("rosette", 1, 0, 0),
               ("flower_cluster", 1, 10, 0.9)],
    levels=[
        Level(count=(3, 4), span=(0.9, 1.0), angle=(28, 45), length=(0.9, 1.3), abs_len=True, len_taper=0.0,
              radius_ratio=0.72, grav=0.45, wander=0.08, photo=0.15, seg=0.18, tip_ratio=0.72),
        Level(count=(2, 3), span=(0.92, 1.0), angle=(25, 45), length=(0.6, 0.85), radius_ratio=0.8, grav=0.55,
              wander=0.1, photo=0.2, seg=0.16, tip_ratio=0.78),
        Level(count=(2, 3), span=(0.92, 1.0), angle=(22, 42), length=(0.5, 0.8), radius_ratio=0.82, grav=0.6,
              wander=0.1, photo=0.2, seg=0.15, tip_ratio=0.8),
    ])

WILLOW = Species(
    "weeping_willow", trunk_height=2.8, trunk_radius=0.3, trunk_lean=0.22, trunk_wander=0.08, trunk_grav=0.05,
    trunk_seg=0.3, trunk_tip_ratio=0.55, bark="bark_furrowed", atlas="leaf_willow",
    cards=[("strand_a", 1), ("strand_b", 1), ("strand_c", 1), ("strand_d", 1)], card_scale=(0.9, 1.5),
    card_levels=(2, 3), card_spacing=0.26, card_span=(0.3, 1.0), card_bend=0.0, card_hang=True,
    sides_max=18, buttress=0.15, buttress_height=0.4, lumpy=0.06, normal_blend=0.45,
    levels=[
        Level(count=(6, 7), span=(0.6, 1.0), angle=(25, 50), length=(3.2, 4.6), abs_len=True, len_taper=0.1,
              radius_ratio=0.55, grav=0.12, wander=0.12, photo=0.1, seg=0.4, tip_ratio=0.3),
        Level(count=(5, 7), span=(0.3, 1.0), angle=(35, 60), length=(0.5, 0.75), radius_ratio=0.6, grav=-0.55,
              wander=0.15, photo=0.25, seg=0.3, tip_ratio=0.35),
        Level(count=(3, 4), span=(0.3, 1.0), angle=(20, 40), length=(0.5, 0.7), radius_ratio=0.7, grav=-1.1,
              wander=0.1, photo=0.1, seg=0.25, tip_ratio=0.4, min_radius=0.005),
    ])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def marker(name: str, loc: Vector, col=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.15
    e.location = loc
    (col or bpy.context.scene.collection).objects.link(e)
    return e


def finish(tid: str, res: T.TreeResult, kind: str, extra: dict, preview: bool, view=None):
    objs = list(res.objects) + list(res.colliders)
    for i, p in enumerate(res.nap):
        objs.append(marker(f"NAP_{i}", p))
    for i, p in enumerate(res.climb):
        objs.append(marker(f"CLIMB_{i}", p))
    path = C.asset_path(f"{OUT}/{tid}.glb")
    G.export_glb(path, objs)
    G.glb_import(path, "nature")
    st = G.glb_stats(path)
    xs, ys, zs = [], [], []
    for o in res.objects:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    entry = {
        "id": tid, "file": f"res://assets/models/nature/{tid}.glb", "kind": kind,
        "width": round(max(xs) - min(xs), 2), "depth": round(max(ys) - min(ys), 2), "height": round(max(zs), 2),
        "footprint": [round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)],
        "floors": 0, "style": "nature",
        "climb_points": [G.to_godot(p) for p in res.climb],
        "nap_spots": [G.to_godot(p) for p in res.nap],
        "entrances": [],
        "tris": st["tris"], "materials": st["materials"], "dynamic": False, "mass": 0.0,
        "surface": "wood", "wind": True, "collision": bool(res.colliders),
    }
    entry.update(extra)
    G.write_catalog(CATALOG, [entry])
    print(f"BUILT {tid}: tris={st['tris']} h={entry['height']} naps={len(res.nap)} climbs={len(res.climb)}")
    if preview:
        h = entry["height"]
        v = view or {}
        C.preview_render(C.qa_path(f"vehicles-nature/tree_{tid}.png"), target=v.get("target", (0, 0, h * 0.45)),
                         distance=v.get("distance", max(h, entry["width"]) * 1.9), yaw_deg=v.get("yaw", 30),
                         pitch_deg=v.get("pitch", 8), res=(560, 560), samples=24, lens=40,
                         sun_strength=4.0, world_strength=0.8)
    return entry


def new_scene():
    C.reset_scene()
    # materials must be re-created after reset_scene (factory settings wipe them)


# ---------------------------------------------------------------------------
# generic recursive trees
# ---------------------------------------------------------------------------
def build_generic(sp: Species, seed: int, kind: str, preview: bool, climb_h=(0.5, 1.4, 2.3), perch_r=0.08,
                  nap_max=5, extra=None, extra_bark=None, skeleton_fn=None, view=None, trunk_climb=True):
    new_scene()
    rng = random.Random(seed)
    skel = skeleton_fn(rng) if skeleton_fn else T.build_skeleton(sp, rng)
    res = T.build_tree(sp, seed, skeleton=skel, extra_bark=(lambda mb, r: extra_bark(mb, r, skel)) if extra_bark else None)
    trunk = skel[0]
    T.trunk_colliders(res, trunk, "trunk", climb=trunk_climb)
    T.limb_perches(res, skel, "limb", min_r=perch_r, nap_max=nap_max, rng=rng)
    T.climb_points_on_trunk(res, trunk, [h for h in climb_h if h < trunk.pts[-1].z - 0.1])
    # the fork where the main limbs leave the trunk is where cats actually nap
    top = trunk.pts[-1]
    l1 = [b for b in skel if b.level == 1]
    if l1 and trunk.radii[-1] >= 0.06:
        fz = min(b.pts[0].z for b in l1)
        fork = trunk.pts[min(range(len(trunk.pts)), key=lambda i: abs(trunk.pts[i].z - fz))]
        r = max(trunk.radii[-1], 0.12)
        res.colliders.append(T.prism_collider("col_wood_climb_fork", fork - Vector((0, 0, 0.25)), fork, r * 1.15, 10))
        res.nap.insert(0, fork.copy())
    return finish(sp.name, res, kind, extra or {}, preview, view)


# ---- banyan extras: aerial roots, prop roots, root-fringe cards, crotch nap spot
def banyan_extras(mb: T.MeshBuilder, rng: random.Random, skel):
    limbs = [b for b in skel if b.level in (1, 2)]
    tile = NA.BARKS["bark_banyan"]
    banyan_extras.props = []
    # thick prop roots that reached the ground and lignified into secondary trunks
    l1 = [b for b in skel if b.level == 1]
    for b in rng.sample(l1, min(5, len(l1))):
        t = rng.uniform(0.45, 0.75)
        p, d, r = b.at(t)
        if p.z < 2.5:
            continue
        rr = rng.uniform(0.07, 0.13)
        pts = []
        n = max(4, int(p.z / 0.4))
        for i in range(n + 1):
            f = i / n
            q = Vector((p.x + math.sin(f * 3 + rng.random()) * 0.06, p.y + math.cos(f * 2.3) * 0.05, p.z * (1 - f) - 0.15 * f))
            pts.append(q)
        radii = [rr * (0.7 + 0.5 * (i / n) ** 2) for i in range(n + 1)]
        T.sweep(mb, pts, radii, sides=8, tile=tile, wind_fn=lambda t_: (0.0, b.phase, 0.0), cap=False)
        banyan_extras.props.append((pts[-1], pts[0], rr))
    # thin hanging aerial roots (sway with their limb)
    for k in range(46):
        b = rng.choice(limbs)
        t = rng.uniform(0.2, 0.95)
        p, d, r = b.at(t)
        if p.z < 1.6:
            continue
        L = rng.uniform(0.6, p.z - 0.25)
        n = max(3, int(L / 0.3))
        pts = [p - Vector((0, 0, r * 0.5))]
        for i in range(n):
            pts.append(pts[-1] + Vector((rng.gauss(0, 0.03), rng.gauss(0, 0.03), -L / n)))
        rr = rng.uniform(0.006, 0.02)
        w0 = b.weight(t)
        T.sweep(mb, pts, [rr * (1 - 0.5 * i / n) for i in range(n + 1)], sides=4, tile=(0.3, 1.0),
                wind_fn=lambda t_, w0=w0, ph=b.phase: (min(1.0, w0 + 0.3 * t_), ph, 0.2 * t_), cap=True)


def build_banyan(preview: bool):
    sp = BANYAN
    new_scene()
    seed = 7
    rng = random.Random(seed)
    skel = T.build_skeleton(sp, rng)
    res = T.build_tree(sp, seed, skeleton=skel, extra_bark=lambda mb, r: banyan_extras(mb, r, skel))
    # hanging root-fringe cards under the big limbs
    lm = T.MeshBuilder("banyan_rootfringe")
    for b in [b for b in skel if b.level == 1]:
        for k in range(4):
            t = rng.uniform(0.25, 0.9)
            p, d, r = b.at(t)
            side = d.cross(T.UP).normalized()
            for j in range(2):
                q = p + side * rng.uniform(-r, r) - Vector((0, 0, r * 0.7))
                sc = rng.uniform(0.9, 1.6)
                T.card(lm, q, T.DOWN, (side + T._rand_unit(rng) * 0.4).normalized(), (0.55 * sc, 1.6 * sc),
                       NA.cell_uv("leaf_banyan", "roots"), "top", bend=0.0, wind_base=b.weight(t) + 0.1,
                       phase=b.phase, center=None)
    fr = lm.finish([T.foliage_material("leaf_banyan")], custom_normals=False)
    res.objects.append(fr)
    trunk = skel[0]
    T.trunk_colliders(res, trunk, "trunk", rscale=1.05)
    T.limb_perches(res, skel, "limb", min_r=0.12, nap_max=6, rng=rng)
    for i, (bot, top, rr) in enumerate(banyan_extras.props):
        res.colliders.append(T.prism_collider(f"col_wood_climb_proproot{i}", bot, top, rr * 1.1, 6))
    # the crotch where the limbs fan out is the classic nap spot
    top = trunk.pts[-1]
    res.nap.insert(0, top + Vector((0, 0, trunk.radii[-1] * 0.1)))
    res.colliders.append(T.prism_collider("col_wood_climb_crotch", top - Vector((0, 0, 0.3)), top + Vector((0, 0, 0.02)),
                                          trunk.radii[-1] * 1.1, 10))
    T.climb_points_on_trunk(res, trunk, [0.6, 1.5, 2.4, 3.3], rscale=1.05)
    return finish("banyan", res, "tree", {"name_key": "NATURE_BANYAN", "species": "Ficus benghalensis",
                                          "climbable": True, "shade_radius": round(res.radius, 1)}, preview,
                  {"distance": 30, "pitch": 6})


# ---------------------------------------------------------------------------
# palms
# ---------------------------------------------------------------------------
def palm_frond(mb_r, mb_l, base: Vector, direction: Vector, length: float, cell: str, rng, width: float,
               droop: float, phase: float, w0: float, rachis_r: float):
    """Rachis tube + two half-frond strips (leaflet texture), arched under gravity, leaflets in a V."""
    n = 10
    d = direction.normalized()
    pts = [base.copy()]
    for i in range(n):
        f = (i + 1) / n
        d = (d + Vector((0, 0, -droop * 0.22 * (0.3 + f)))).normalized()
        pts.append(pts[-1] + d * length / n)
    radii = [rachis_r * (1 - 0.8 * i / n) for i in range(n + 1)]
    T.sweep(mb_r, pts, radii, sides=5, tile=(0.3, 1.0),
            wind_fn=lambda t: (min(1.0, w0 + 0.6 * t), phase, 0.0), cap=True)
    u0, v0, u1, v1 = NA.cell_uv("leaf_palm", cell)
    tans = [(pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized() for i in range(n + 1)]
    for side in (-1, 1):
        rows = []
        for i in range(n + 1):
            f = i / n
            t = tans[i]
            lat = t.cross(T.UP)
            if lat.length < 1e-3:
                lat = T.Vector((1, 0, 0))
            lat = lat.normalized() * side
            # V-shaped leaflet plane: tilt up, droop more toward the tip
            vdir = (lat + T.UP * (0.45 - 0.9 * f)).normalized()
            env = math.sin(math.pi * min(1.0, 0.1 + f * 0.95)) ** 0.6
            wv = width * (0.35 + 0.65 * env)
            p0 = pts[i]
            p1 = p0 + vdir * wv * 0.5 + T.DOWN * wv * 0.08
            p2 = p0 + vdir * wv + T.DOWN * wv * (0.25 + 0.3 * f)
            v = v0 + (v1 - v0) * f
            nrm = (T.UP * 0.7 + vdir * 0.3).normalized()
            wb = min(1.0, w0 + 0.6 * f)
            row = []
            for j, q in enumerate((p0, p1, p2)):
                uu = u0 + (u1 - u0) * (0.02 + 0.98 * j / 2)
                row.append((mb_l.vert(q, (wb, phase, j / 2.0), nrm), (uu, v)))
            rows.append(row)
        for i in range(n):
            for j in range(2):
                a, b, c, dd = rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]
                if side > 0:
                    mb_l.face([a[0], b[0], c[0], dd[0]], [a[1], b[1], c[1], dd[1]])
                else:
                    mb_l.face([dd[0], c[0], b[0], a[0]], [dd[1], c[1], b[1], a[1]])
    return pts


def build_palm(kind: str, preview: bool):
    new_scene()
    coconut = kind == "coconut_palm"
    rng = random.Random(31 if coconut else 37)
    H = 9.5 if coconut else 7.2
    r0 = 0.2 if coconut else 0.085
    # curved, slightly leaning trunk (coconuts lean toward light), swollen base
    n = 24
    lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
    pts = []
    for i in range(n + 1):
        f = i / n
        bend = (0.9 if coconut else 0.25) * (f ** 1.6)
        pts.append(Vector((0, 0, f * H)) + lean * bend)
    radii = [r0 * (1.0 + (0.6 if coconut else 0.35) * math.exp(-(i / n) * 12) - 0.25 * (i / n)) for i in range(n + 1)]
    mb = T.MeshBuilder(f"{kind}_bark")
    T.sweep(mb, pts, radii, sides=14 if coconut else 10, tile=NA.BARKS["bark_palm"],
            wind_fn=lambda t: (0.25 * t * t, 0.3, 0.0), cap=False)
    # root flare: short roots at the base
    for k in range(10 if coconut else 6):
        a = k / (10 if coconut else 6) * math.tau + rng.uniform(-0.2, 0.2)
        dirv = Vector((math.cos(a), math.sin(a), 0))
        rp = [Vector((0, 0, 0.18)) + dirv * r0 * 0.8, Vector((0, 0, 0.02)) + dirv * (r0 + 0.12)]
        T.sweep(mb, rp, [0.035 if coconut else 0.02, 0.015], sides=5, tile=(0.3, 0.3), cap=True)
    top = pts[-1]
    tdir = (pts[-1] - pts[-2]).normalized()
    lm = T.MeshBuilder(f"{kind}_fronds")
    rm = mb
    extra_objs = []
    if not coconut:
        # smooth green crownshaft (areca)
        cs = T.MeshBuilder("areca_crownshaft")
        cpts = [top + tdir * (k * 0.25) for k in range(5)]
        T.sweep(cs, cpts, [r0 * 1.25, r0 * 1.35, r0 * 1.3, r0 * 1.1, r0 * 0.7], sides=12, tile=(0.3, 1.0),
                wind_fn=lambda t: (0.3, 0.3, 0.0), cap=True)
        shaft = cs.finish([C.principled("nmat_areca_crownshaft", (0.22, 0.36, 0.12), 0.4)])
        extra_objs.append(shaft)
        top = cpts[-1]
    nf = 20 if coconut else 10
    for k in range(nf):
        a = k * math.radians(137.5) + rng.uniform(-0.15, 0.15)
        age = k / nf                               # 0 = oldest (lowest, drooping) .. 1 = youngest (upright spear)
        elev = math.radians(-35 + 95 * age) if coconut else math.radians(-10 + 80 * age)
        dirv = Vector((math.cos(a) * math.cos(elev), math.sin(a) * math.cos(elev), math.sin(elev)))
        L = (rng.uniform(4.0, 5.0) if coconut else rng.uniform(1.9, 2.4)) * (0.65 + 0.35 * min(1.0, (1 - age) * 1.6))
        cell = ("coconut_dry" if (coconut and age < 0.12) else "coconut") if coconut else rng.choice(["areca", "areca_b"])
        base = top + dirv * 0.05 - tdir * (0.35 * (1 - age) if coconut else 0.0)
        palm_frond(rm, lm, base, dirv, L, cell, rng, width=1.6 if coconut else 1.1,
                   droop=(1.3 if coconut else 0.9) * (1.2 - age), phase=rng.random(), w0=0.35,
                   rachis_r=0.045 if coconut else 0.025)
    bark = mb.finish([T.bark_material("bark_palm")])
    leaves = lm.finish([T.foliage_material("leaf_palm")], custom_normals=True)
    res = T.TreeResult()
    res.objects = [bark, leaves] + extra_objs
    if coconut:
        nm = T.MeshBuilder("coconut_nuts")
        bm = nm.bm
        for k in range(9):
            a = rng.uniform(0, math.tau)
            c = top - tdir * 0.45 + Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(0.18, 0.3) - Vector((0, 0, rng.uniform(0, 0.25)))
            import bmesh
            ret = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=7, radius=0.12)
            for v in ret["verts"]:
                v.co = c + Vector((v.co.x, v.co.y, v.co.z * 1.15))
                v[nm.wind] = (0.35, 0.2, 0.0, 1.0)
                nm.normals.append(None)
        nuts = nm.finish([C.principled("nmat_coconut", (0.32, 0.38, 0.12), 0.45)])
        C.shade_smooth(nuts, None)
        res.objects.append(nuts)
    trunk = T.Branch(pts, radii, 0)
    T.trunk_colliders(res, trunk, "trunk", rscale=1.0, step=4)
    T.climb_points_on_trunk(res, trunk, [0.6, 1.6, 2.6, 3.6])
    name_key = "NATURE_COCONUT" if coconut else "NATURE_ARECA"
    return finish(kind, res, "palm", {"name_key": name_key, "climbable": True}, preview,
                  {"distance": H * 1.7, "target": (0, 0, H * 0.55), "pitch": 6})


# ---------------------------------------------------------------------------
# bamboo clump
# ---------------------------------------------------------------------------
def build_bamboo(preview: bool):
    new_scene()
    rng = random.Random(53)
    mb = T.MeshBuilder("bamboo_clump_culms")
    lm = T.MeshBuilder("bamboo_clump_leaves")
    uvn = {c: NA.cell_uv("leaf_bamboo", c) for c in ("sprig_a", "sprig_b", "sprig_c", "sprig_d")}
    ncul = 24
    for k in range(ncul):
        a = rng.uniform(0, math.tau)
        rr = 0.75 * math.sqrt(rng.random())
        base = Vector((math.cos(a) * rr, math.sin(a) * rr, -0.05))
        H = rng.uniform(6.0, 9.5)
        r = rng.uniform(0.035, 0.055)
        out = Vector((math.cos(a), math.sin(a), 0)) * (0.15 + rr * 0.3)
        d = (T.UP + out * 0.35 + Vector((rng.gauss(0, 0.05), rng.gauss(0, 0.05), 0))).normalized()
        internode = rng.uniform(0.3, 0.42)
        n = int(H / internode)
        pts = [base]
        for i in range(n):
            f = i / n
            d = (d + Vector((out.x, out.y, 0)) * 0.012 + Vector((0, 0, -0.03 * f * f * 3))).normalized()
            pts.append(pts[-1] + d * internode)
        radii = [r * (1 - 0.6 * (i / n) ** 1.5) for i in range(n + 1)]
        ph = rng.random()
        T.sweep(mb, pts, radii, sides=7, tile=(0.25, internode),
                wind_fn=lambda t, ph=ph: (min(1.0, 0.05 + t * t * 0.95), ph, 0.0), cap=True)
        # node rings (slightly swollen) every internode
        for i in range(2, n, 1):
            q = pts[i]
            dd = (pts[i + 1] - pts[i - 1]).normalized() if i + 1 < len(pts) else d
            f = i / n
            T.sweep(mb, [q - dd * 0.012, q + dd * 0.012], [radii[i] * 1.12, radii[i] * 1.12], sides=7,
                    tile=(0.25, 0.05), wind_fn=lambda t, f=f, ph=ph: (min(1.0, 0.05 + f * f * 0.95), ph, 0.0), cap=False)
            # branchlets with leaf sprigs on the upper culm
            if f > 0.3 and rng.random() < 0.9:
                for s in range(rng.randint(2, 4)):
                    ba = rng.uniform(0, math.tau)
                    bd = (Vector((math.cos(ba), math.sin(ba), 0)) + T.UP * 0.4).normalized()
                    sc = rng.uniform(1.3, 1.9)
                    cell = rng.choice(list(uvn))
                    T.card(lm, q, (bd + T.DOWN * 0.2).normalized(), (T.UP + T._rand_unit(rng) * 0.5).normalized(),
                           (0.6 * sc, 0.6 * sc), uvn[cell], "bottom", bend=0.25, wind_base=min(1.0, 0.1 + f * f),
                           phase=ph, center=Vector((0, 0, 5.0)), blend=0.5)
    culms = mb.finish([T.bark_material("bamboo_culm")])
    leaves = lm.finish([T.foliage_material("leaf_bamboo")], custom_normals=True)
    res = T.TreeResult()
    res.objects = [culms, leaves]
    # the dense clump base blocks the cat; culms are too smooth/slender to climb
    res.colliders.append(T.prism_collider("col_wood_clump", Vector((0, 0, 0)), Vector((0, 0, 2.2)), 0.72, 10))
    return finish("bamboo_clump", res, "bamboo", {"name_key": "NATURE_BAMBOO", "climbable": False}, preview,
                  {"distance": 16, "target": (0, 0, 4.0), "pitch": 6})


BUILDERS = {
    "banyan": lambda pv: build_banyan(pv),
    "sao_tree": lambda pv: build_generic(SAO, 3, "tree", pv, climb_h=(0.5, 1.5, 2.5, 3.5), perch_r=0.08,
                                         extra={"name_key": "NATURE_SAO", "species": "Hopea odorata",
                                                "climbable": True}),
    "flame_tree": lambda pv: build_generic(FLAME, 11, "tree", pv, climb_h=(0.5, 1.4, 2.3), perch_r=0.075,
                                           extra={"name_key": "NATURE_FLAME_TREE", "species": "Delonix regia",
                                                  "climbable": True}),
    "frangipani": lambda pv: build_generic(FRANGIPANI, 5, "tree", pv, climb_h=(0.4,), perch_r=0.07, nap_max=2,
                                           extra={"name_key": "NATURE_FRANGIPANI", "species": "Plumeria rubra",
                                                  "climbable": True}, view={"distance": 9}),
    "weeping_willow": lambda pv: build_generic(WILLOW, 19, "tree", pv, climb_h=(0.5, 1.4, 2.2), perch_r=0.07,
                                               extra={"name_key": "NATURE_WILLOW", "species": "Salix babylonica",
                                                      "climbable": True}),
    "coconut_palm": lambda pv: build_palm("coconut_palm", pv),
    "areca_palm": lambda pv: build_palm("areca_palm", pv),
    "bamboo_clump": lambda pv: build_bamboo(pv),
}

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--nopreview" not in argv
    ids = [a for a in argv if not a.startswith("--")] or list(BUILDERS)
    for tid in ids:
        BUILDERS[tid](preview)
