"""Procedural tree / plant generator for Blender 5.2 (vehicles-nature area).

Recursive branching with gravitropism (+ up / - weeping), phototropism (outward), random wander,
phyllotactic child placement and pipe-model radius taper.  Produces:

* bark mesh: generalised cylinders swept with parallel-transport frames (no twisting), radius
  profile hooks (buttress flare, lumpy fused-root trunks), seam-safe tiling UVs (u wraps an integer
  number of times around the girth so the bark texel density stays ~constant), end caps.
* leaf-card mesh: alpha-tested cards cut from the species atlas (blender/lib/nature_atlas.py), bent
  under gravity, normals blended toward the canopy hull for soft "volume" shading.
* wind vertex colours (float attribute "wind", exported as COLOR_0):
      R = sway weight (0 at trunk base .. 1 at twig tips)  — whole-branch bending
      G = phase (per main limb + per twig offset)          — de-synchronises limbs
      B = flutter weight (0 at the attachment .. 1 at leaf-card tips)
* gameplay data: convex trunk / limb colliders (climbable), nap spots on thick near-horizontal limbs
  and crotches, climb points on the trunk surface.

All coordinates here are Blender (Z up, front = -Y).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector, noise

import common as C
import nature_atlas as NA

UP = Vector((0, 0, 1))
DOWN = Vector((0, 0, -1))


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
@dataclass
class Level:
    count: tuple = (4, 6)            # children per parent branch (min, max)
    span: tuple = (0.3, 1.0)         # where along the parent they spawn (t range)
    angle: tuple = (35, 60)          # divergence from parent direction, degrees
    length: tuple = (0.4, 0.7)       # length as fraction of parent length (or metres if abs_len)
    abs_len: bool = False
    len_taper: float = 0.5           # children near the parent tip are shorter by this fraction
    radius_ratio: float = 0.55       # child base radius / parent radius at the spawn point
    grav: float = 0.0                # +: bends up, -: droops (per metre of growth)
    wander: float = 0.15
    photo: float = 0.1               # outward pull (away from trunk axis)
    seg: float = 0.3                 # segment length (m)
    tip_ratio: float = 0.35          # tip radius / base radius
    up_bias: float = 0.0             # added to child direction before normalising
    min_radius: float = 0.004        # thinner branches are not meshed (cards carry them)


@dataclass
class Species:
    name: str
    trunk_height: float = 6.0
    trunk_radius: float = 0.25
    trunk_lean: float = 0.05
    trunk_wander: float = 0.05
    trunk_grav: float = 0.2
    trunk_seg: float = 0.3
    trunk_tip_ratio: float = 0.35
    levels: list = field(default_factory=list)
    bark: str = "bark_smooth"
    atlas: str = "leaf_sao"
    cards: list = field(default_factory=list)     # [(cell, weight)]
    card_scale: tuple = (0.8, 1.2)
    card_levels: tuple = (2, 3)                   # branch levels carrying cards
    card_spacing: float = 0.25                    # metres between cards along a carrying branch
    card_span: tuple = (0.3, 1.0)
    card_bend: float = 0.25
    card_up: float = 0.4                          # how much cards point upward/outward
    card_hang: bool = False                       # pivot-top cards hang straight down
    sides_max: int = 16
    buttress: float = 0.0
    buttress_lobes: int = 7
    buttress_height: float = 1.0
    lumpy: float = 0.0
    normal_blend: float = 0.55
    tip_cards: list = field(default_factory=list)  # [(cell, count, spread_deg, up)] placed at terminal tips


class Branch:
    __slots__ = ("pts", "radii", "level", "parent", "t0", "children", "w0", "w1", "phase", "length", "dirs")

    def __init__(self, pts, radii, level, parent=None, t0=0.0, w0=0.0, w1=0.2, phase=0.0):
        self.pts, self.radii, self.level, self.parent, self.t0 = pts, radii, level, parent, t0
        self.children = []
        self.w0, self.w1, self.phase = w0, w1, phase
        self.length = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
        self.dirs = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]

    def at(self, t: float):
        n = len(self.pts) - 1
        f = max(0.0, min(1.0, t)) * n
        i = min(int(f), n - 1)
        a = f - i
        p = self.pts[i].lerp(self.pts[i + 1], a)
        d = (self.pts[i + 1] - self.pts[i]).normalized()
        r = self.radii[i] * (1 - a) + self.radii[i + 1] * a
        return p, d, r

    def weight(self, t: float) -> float:
        return self.w0 + (self.w1 - self.w0) * t


def _perp(v: Vector) -> Vector:
    a = Vector((1, 0, 0)) if abs(v.x) < 0.9 else Vector((0, 1, 0))
    return v.cross(a).normalized()


def _rand_unit(rng: random.Random) -> Vector:
    while True:
        v = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if 0.01 < v.length <= 1:
            return v.normalized()


# ---------------------------------------------------------------------------
# growth
# ---------------------------------------------------------------------------
def grow(origin: Vector, direction: Vector, length: float, r0: float, tip_ratio: float, seg: float,
         grav: float, wander: float, photo: float, rng: random.Random, axis_origin: Vector,
         curl: Vector | None = None):
    n = max(3, int(round(length / seg)))
    step = length / n
    d = direction.normalized()
    pts = [origin.copy()]
    for i in range(n):
        out = (pts[-1] - axis_origin)
        out.z = 0
        outv = out.normalized() if out.length > 1e-4 else Vector((0, 0, 0))
        d = d + UP * (grav * step) + _rand_unit(rng) * wander * math.sqrt(step) + outv * photo * step
        if curl is not None:
            d = d + curl * step
        d.normalize()
        pts.append(pts[-1] + d * step)
    radii = [r0 * (1 - (1 - tip_ratio) * (i / n) ** 0.9) for i in range(n + 1)]
    return pts, radii


def build_skeleton(sp: Species, rng: random.Random, trunk_pts=None, trunk_radii=None) -> list:
    """Returns the list of all branches (trunk first)."""
    if trunk_pts is None:
        lean = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized() * sp.trunk_lean
        trunk_pts, trunk_radii = grow(Vector((0, 0, 0)), (UP + lean).normalized(), sp.trunk_height, sp.trunk_radius,
                                      sp.trunk_tip_ratio, sp.trunk_seg, sp.trunk_grav, sp.trunk_wander, 0.0, rng,
                                      Vector((0, 0, 0)))
    trunk = Branch(trunk_pts, trunk_radii, 0, None, 0.0, 0.0, 0.12, rng.random())
    allb = [trunk]
    frontier = [trunk]
    for li, L in enumerate(sp.levels, start=1):
        nxt = []
        for par in frontier:
            cnt = rng.randint(*L.count)
            if cnt <= 0:
                continue
            phi0 = rng.uniform(0, math.tau)
            for k in range(cnt):
                t = L.span[0] + (L.span[1] - L.span[0]) * ((k + rng.uniform(0.2, 0.8)) / cnt)
                p, d, r = par.at(t)
                r_child = r * L.radius_ratio * rng.uniform(0.85, 1.1)
                if r_child < L.min_radius:
                    continue
                ang = math.radians(rng.uniform(*L.angle))
                phi = phi0 + k * math.radians(137.5) + rng.uniform(-0.3, 0.3)
                perp = _perp(d)
                rot_axis = Quaternion(d, phi) @ perp
                cd = (Quaternion(rot_axis, ang) @ d)
                cd = (cd + UP * L.up_bias).normalized()
                if L.abs_len:
                    ln = rng.uniform(*L.length)
                else:
                    ln = par.length * rng.uniform(*L.length)
                ln *= (1 - L.len_taper * t)
                if ln < 0.05:
                    continue
                pts, radii = grow(p, cd, ln, r_child, L.tip_ratio, L.seg, L.grav, L.wander, L.photo, rng,
                                  Vector((trunk_pts[0].x, trunk_pts[0].y, 0)))
                w0 = par.weight(t)
                b = Branch(pts, radii, li, par, t, w0, min(1.0, w0 + 0.22 + 0.08 * li),
                           par.phase if li > 1 else rng.random())
                if li > 1:
                    b.phase = (par.phase + rng.uniform(-0.08, 0.08)) % 1.0
                par.children.append(b)
                allb.append(b)
                nxt.append(b)
        frontier = nxt
    return allb


# ---------------------------------------------------------------------------
# mesh building
# ---------------------------------------------------------------------------
class MeshBuilder:
    """Accumulates verts / faces / uvs / wind colours / custom normals, then makes an object."""

    def __init__(self, name: str):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.verify()
        self.wind = self.bm.verts.layers.float_color.new("wind")
        self.normals: list = []     # per vertex custom normal or None
        self.mat_index = {}

    def vert(self, co: Vector, wind=(0, 0, 0), normal: Vector | None = None):
        v = self.bm.verts.new(co)
        v[self.wind] = (wind[0], wind[1], wind[2], 1.0)
        self.normals.append(normal)
        return v

    def face(self, vs, uvs, mat=0):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = mat
        for l, uv in zip(f.loops, uvs):
            l[self.uv].uv = uv
        f.smooth = True
        return f

    def finish(self, mats: list, custom_normals: bool = False, col=None) -> bpy.types.Object:
        me = bpy.data.meshes.new(self.name)
        self.bm.verts.index_update()
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        (col or bpy.context.scene.collection).objects.link(ob)
        attr = me.color_attributes.get("wind")
        if attr:
            me.color_attributes.active_color = attr
            me.color_attributes.render_color_index = me.color_attributes.find("wind")
        if custom_normals and any(n is not None for n in self.normals):
            vn = []
            for i, v in enumerate(me.vertices):
                n = self.normals[i]
                vn.append(tuple(n) if n is not None else tuple(v.normal))
            me.normals_split_custom_set_from_vertices(vn)
        return ob


def sweep(mb: MeshBuilder, pts, radii, *, sides: int, tile=(1.0, 1.0), wind_fn=None, profile=None,
          cap=True, mat=0, v_offset=0.0, frame0: Vector | None = None):
    """Generalised cylinder along pts. wind_fn(t) -> (r, g, b). profile(theta, z, t) -> radius scale."""
    n = len(pts)
    tans = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    N = frame0.copy() if frame0 is not None else _perp(tans[0])
    N = (N - tans[0] * N.dot(tans[0])).normalized()
    frames = []
    for i in range(n):
        if i > 0:
            q = tans[i - 1].rotation_difference(tans[i])
            N = q @ N
            N = (N - tans[i] * N.dot(tans[i])).normalized()
        frames.append((N.copy(), tans[i].cross(N).normalized()))
    circ = 2 * math.pi * max(radii[0], 1e-3)
    urep = max(1, round(circ / tile[0]))
    rings = []
    vacc = v_offset
    for i in range(n):
        if i > 0:
            vacc += (pts[i] - pts[i - 1]).length / tile[1]
        Ni, Bi = frames[i]
        t = i / (n - 1)
        w = wind_fn(t) if wind_fn else (0, 0, 0)
        ring = []
        for j in range(sides + 1):
            th = (j % sides) / sides * math.tau
            r = radii[i]
            if profile is not None:
                r *= profile(th, pts[i].z, t)
            off = Ni * math.cos(th) + Bi * math.sin(th)
            ring.append((mb.vert(pts[i] + off * r, w) if j < sides else None, j / sides * urep, vacc))
        ring[-1] = (ring[0][0], urep, vacc)
        rings.append(ring)
    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(sides):
            mb.face([a[j][0], a[j + 1][0], b[j + 1][0], b[j][0]],
                    [(a[j][1], a[j][2]), (a[j + 1][1], a[j + 1][2]), (b[j + 1][1], b[j + 1][2]), (b[j][1], b[j][2])],
                    mat)
    if cap:
        tip = pts[-1] + tans[-1] * radii[-1] * 0.8
        w = wind_fn(1.0) if wind_fn else (0, 0, 0)
        tv = mb.vert(tip, w)
        last = rings[-1]
        for j in range(sides):
            mb.face([last[j][0], last[j + 1][0], tv], [(last[j][1], last[j][2]), (last[j + 1][1], last[j][2]),
                                                        ((last[j][1] + last[j + 1][1]) * 0.5, last[j][2] + 0.05)], mat)
    return frames


def sides_for(r: float, smax: int) -> int:
    return int(max(4, min(smax, round(r * 2 * math.pi / 0.035))))


def card(mb: MeshBuilder, pivot: Vector, axis: Vector, normal: Vector, size, uv, mode: str = "bottom",
         bend: float = 0.2, wind_base: float = 0.5, phase: float = 0.0, center: Vector | None = None,
         blend: float = 0.5, rows: int = 3, mat: int = 0, cup: float = 0.0):
    """One alpha card. axis = card 'up' (pivot -> far end), normal = facing.
    uv = (u0, v0, u1, v1). mode bottom|top|center."""
    axis = axis.normalized()
    normal = (normal - axis * normal.dot(axis)).normalized()
    right = axis.cross(normal).normalized()
    w, h = size
    u0, v0, u1, v1 = uv
    grid = []
    for ri in range(rows):
        s = ri / (rows - 1)
        row = []
        for ci in range(3):
            c = ci / 2.0
            x = (c - 0.5) * w
            if mode == "center":
                y = (s - 0.5) * h
                d2 = (abs(y) / (h * 0.5)) ** 2 + (abs(x) / (w * 0.5)) ** 2
                p = pivot + right * x + axis * y + normal * (-bend * 0.25 * h * d2 + cup * 0.1 * h * (1 - d2))
                fl = min(1.0, math.sqrt(d2))
                uv_ = (u0 + (u1 - u0) * c, v0 + (v1 - v0) * s)
            else:
                y = s * h
                p = pivot + right * x + axis * y + DOWN * (bend * h * s * s) + normal * (cup * w * (abs(c - 0.5) * 2) ** 2 * 0.3)
                fl = s * (0.6 + 0.4 * abs(c - 0.5) * 2)
                if mode == "bottom":
                    uv_ = (u0 + (u1 - u0) * c, v0 + (v1 - v0) * s)
                else:  # top: pivot at the top of the cell
                    uv_ = (u0 + (u1 - u0) * c, v1 - (v1 - v0) * s)
            nrm = normal
            if center is not None:
                outv = (p - center)
                if outv.length > 1e-4:
                    nrm = normal.lerp(outv.normalized(), blend).normalized()
            wind = (min(1.0, wind_base + 0.08 * s), phase, fl)
            row.append((mb.vert(p, wind, nrm), uv_))
        grid.append(row)
    for ri in range(rows - 1):
        for ci in range(2):
            a, b, c_, d = grid[ri][ci], grid[ri][ci + 1], grid[ri + 1][ci + 1], grid[ri + 1][ci]
            mb.face([a[0], b[0], c_[0], d[0]], [a[1], b[1], c_[1], d[1]], mat)


def pick(rng: random.Random, weighted: list):
    tot = sum(w for _, w in weighted)
    x = rng.uniform(0, tot)
    for v, w in weighted:
        x -= w
        if x <= 0:
            return v
    return weighted[-1][0]


# ---------------------------------------------------------------------------
# materials (Blender side; Godot replaces them with shared .tres via the post-import script)
# ---------------------------------------------------------------------------
def tex(name: str, kind: str) -> str:
    ext = {"albedo_png": "_albedo.png", "albedo": "_albedo.jpg", "normal": "_normal.png", "orm": "_orm.jpg",
           "trans": "_trans.jpg"}[kind]
    return C.asset_path(f"{NA.TEX_DIR}/{name}{ext}")


def bark_material(bark: str) -> bpy.types.Material:
    mname = f"nbark_{bark}"
    m = bpy.data.materials.get(mname)
    if m:
        return m
    m = C.image_material(mname, albedo=tex(bark, "albedo"), normal=tex(bark, "normal"), orm=tex(bark, "orm"))
    return m


def foliage_material(atlas: str) -> bpy.types.Material:
    mname = f"nfol_{atlas}"
    m = bpy.data.materials.get(mname)
    if m:
        return m
    m = C.image_material(mname, albedo=tex(atlas, "albedo_png"), normal=tex(atlas, "normal"), orm=tex(atlas, "orm"),
                         alpha_clip=True)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    # preview translucency: a little diffuse transmission via subsurface
    bsdf.inputs["Subsurface Weight"].default_value = 0.15
    try:
        m.surface_render_method = "DITHERED"
    except Exception:
        pass
    return m


def simple_material(name: str, color, rough=0.6, metal=0.0) -> bpy.types.Material:
    return C.principled(name, color, rough, metal)


# ---------------------------------------------------------------------------
# colliders
# ---------------------------------------------------------------------------
def prism_collider(name: str, p0: Vector, p1: Vector, r: float, sides: int = 8, col=None) -> bpy.types.Object:
    d = (p1 - p0)
    t = d.normalized()
    nrm = _perp(t)
    b = t.cross(nrm)
    bm = bmesh.new()
    rings = []
    for p in (p0, p1):
        rings.append([bm.verts.new(p + (nrm * math.cos(a) + b * math.sin(a)) * r)
                      for a in [k / sides * math.tau for k in range(sides)]])
    bmesh.ops.convex_hull(bm, input=rings[0] + rings[1])
    ob = C.mesh_from_bmesh(name + "-convcolonly", bm, col)
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob


def box_collider(name: str, center: Vector, size, rot_z: float = 0.0, col=None) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    mat = Matrix.Translation(center) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Diagonal((*size, 1.0))
    for v in bm.verts:
        v.co = mat @ v.co
    ob = C.mesh_from_bmesh(name + "-convcolonly", bm, col)
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob


def to_godot(v: Vector) -> list:
    return [round(v.x, 3), round(v.z, 3), round(-v.y, 3)]


# ---------------------------------------------------------------------------
# full tree
# ---------------------------------------------------------------------------
class TreeResult:
    def __init__(self):
        self.objects = []
        self.colliders = []
        self.nap = []        # Blender coords
        self.climb = []
        self.branches = []
        self.height = 0.0
        self.radius = 0.0


def bark_profile(sp: Species, seed: float):
    def prof(th, z, t):
        s = 1.0
        if sp.buttress > 0:
            fl = math.exp(-max(z, 0.0) / max(0.05, sp.buttress_height))
            lob = (0.5 + 0.5 * math.cos(th * sp.buttress_lobes + seed * 6.0 + 0.6 * math.sin(th * 3 + seed))) ** 2.5
            s += sp.buttress * fl * (0.25 + 1.2 * lob)
        if sp.lumpy > 0:
            s += sp.lumpy * noise.noise(Vector((math.cos(th) * 1.6, math.sin(th) * 1.6, z * 1.3 + seed * 10)))
        return s
    return prof


def mesh_branches(sp: Species, branches: list, mb: MeshBuilder, rng: random.Random, tile, height: float):
    seedf = rng.random()
    for b in branches:
        r0 = b.radii[0]
        L = sp.levels[b.level - 1] if b.level > 0 else None
        if L is not None and r0 < L.min_radius:
            continue
        sides = sides_for(r0, sp.sides_max if b.level == 0 else max(6, sp.sides_max // (b.level + 1)))
        if b.level >= len(sp.levels) and b.level > 1:
            sides = 3
        prof = bark_profile(sp, seedf) if b.level == 0 else None
        if b.level == 0:
            def wf(t, b=b):
                return (0.12 * t * t, b.phase, 0.0)
        else:
            def wf(t, b=b):
                return (b.weight(t), b.phase, 0.25 * t if b.level >= len(sp.levels) else 0.0)
        pts = list(b.pts)
        radii = list(b.radii)
        if b.parent is not None:
            # sink the base into the parent so joints never show a gap
            back = b.dirs[0] * min(b.parent.at(b.t0)[2] * 0.8, 0.3)
            pts[0] = pts[0] - back
        sweep(mb, pts, radii, sides=sides, tile=tile, wind_fn=wf, profile=prof, cap=True)


def place_cards(sp: Species, branches: list, mb: MeshBuilder, rng: random.Random, center: Vector):
    atlas = NA.ATLASES[sp.atlas]
    count = 0
    for b in branches:
        if b.level not in sp.card_levels or not sp.cards:
            continue
        n = max(1, int(b.length * (sp.card_span[1] - sp.card_span[0]) / sp.card_spacing))
        for k in range(n + 1):
            t = sp.card_span[0] + (sp.card_span[1] - sp.card_span[0]) * (k + rng.uniform(0, 0.8)) / (n + 1)
            if k == n:
                t = 1.0
            p, d, r = b.at(t)
            cell_name = pick(rng, sp.cards)
            cell = atlas["cells"][cell_name]
            sc = rng.uniform(*sp.card_scale)
            size = (cell["size"][0] * sc, cell["size"][1] * sc)
            mode = cell["pivot"]
            out = p - center
            out.z = 0
            outv = out.normalized() if out.length > 1e-3 else _rand_unit(rng)
            if mode == "top" or sp.card_hang:
                axis = DOWN.copy()
                normal = (outv + _rand_unit(rng) * 0.6).normalized()
                normal.z = 0
                if normal.length < 1e-3:
                    normal = Vector((1, 0, 0))
                normal.normalize()
                mode = "top"
            elif mode == "center":
                axis = (outv + _rand_unit(rng) * 0.3)
                axis.z = 0
                axis = axis.normalized() if axis.length > 1e-3 else Vector((1, 0, 0))
                normal = (UP + outv * 0.35 + _rand_unit(rng) * 0.25).normalized()
            else:
                axis = (d * 0.5 + outv * 0.6 + UP * sp.card_up + _rand_unit(rng) * 0.45).normalized()
                side = axis.cross(UP)
                if side.length < 1e-3:
                    side = Vector((1, 0, 0))
                normal = (Quaternion(axis, rng.uniform(-1.2, 1.2)) @ side.normalized()).normalized()
            uv = NA.cell_uv(sp.atlas, cell_name)
            card(mb, p, axis, normal, size, uv, mode, bend=sp.card_bend * rng.uniform(0.6, 1.3),
                 wind_base=min(1.0, b.weight(t) + 0.05), phase=(b.phase + rng.uniform(-0.05, 0.05)) % 1.0,
                 center=center, blend=sp.normal_blend)
            count += 1
    if sp.tip_cards:
        for b in branches:
            if b.children or b.level == 0:
                continue
            p, d, r = b.at(1.0)
            for cell_name, cnt, spread, up in sp.tip_cards:
                cell = atlas["cells"][cell_name]
                for k in range(cnt):
                    sc = rng.uniform(*sp.card_scale)
                    size = (cell["size"][0] * sc, cell["size"][1] * sc)
                    mode = cell["pivot"]
                    a = k / max(1, cnt) * math.tau + rng.uniform(-0.4, 0.4)
                    if mode == "center":
                        axis = Vector((math.cos(a), math.sin(a), 0))
                        normal = (UP + d * 0.3 + _rand_unit(rng) * 0.15).normalized()
                        q = p + d * 0.03
                    else:
                        tilt = math.radians(spread) * rng.uniform(0.6, 1.0)
                        side = Vector((math.cos(a), math.sin(a), 0))
                        axis = (d * (1 - up) + UP * up).normalized()
                        axis = (axis * math.cos(tilt) + side * math.sin(tilt)).normalized()
                        normal = (side.cross(axis)).normalized()
                        if normal.length < 1e-3:
                            normal = _perp(axis)
                        q = p - d * 0.02
                    card(mb, q, axis, normal, size, NA.cell_uv(sp.atlas, cell_name), mode,
                         bend=sp.card_bend * rng.uniform(0.6, 1.3), wind_base=min(1.0, b.weight(1.0) + 0.05),
                         phase=b.phase, center=center, blend=sp.normal_blend * 0.6)
                    count += 1
    return count


def build_tree(sp: Species, seed: int, col=None, skeleton=None, extra_bark=None) -> TreeResult:
    rng = random.Random(seed)
    res = TreeResult()
    branches = skeleton if skeleton is not None else build_skeleton(sp, rng)
    res.branches = branches
    zs = [p.z for b in branches for p in b.pts]
    res.height = max(zs)
    res.radius = max(math.hypot(p.x, p.y) for b in branches for p in b.pts)
    tile = NA.BARKS.get(sp.bark, (1.0, 1.0))
    mb = MeshBuilder(f"{sp.name}_bark")
    mesh_branches(sp, branches, mb, rng, tile, res.height)
    if extra_bark:
        extra_bark(mb, rng)
    bark = mb.finish([bark_material(sp.bark)], col=col)
    res.objects.append(bark)
    if sp.cards or sp.tip_cards:
        cz = res.height * 0.62
        center = Vector((branches[0].pts[-1].x, branches[0].pts[-1].y, cz))
        lm = MeshBuilder(f"{sp.name}_leaves")
        ncards = place_cards(sp, branches, lm, rng, center)
        lv = {}
        for b in branches:
            lv[b.level] = lv.get(b.level, 0) + 1
        print(f"TREE {sp.name}: branches per level {lv}, cards {ncards}")
        leaves = lm.finish([foliage_material(sp.atlas)], custom_normals=True, col=col)
        res.objects.append(leaves)
    return res


def trunk_colliders(res: TreeResult, trunk: Branch, name: str, col=None, rscale: float = 0.95, max_z: float = 99.0,
                    step: int = 2, climb: bool = True):
    tag = "col_wood_climb" if climb else "col_wood"
    pts = trunk.pts
    i = 0
    k = 0
    while i < len(pts) - 1 and pts[i].z < max_z:
        j = min(i + step, len(pts) - 1)
        r = (trunk.radii[i] + trunk.radii[j]) * 0.5 * rscale
        res.colliders.append(prism_collider(f"{tag}_{name}{k}", pts[i], pts[j], r, 8, col))
        i = j
        k += 1


def limb_perches(res: TreeResult, branches: list, name: str, min_r: float = 0.08, max_slope_deg: float = 35.0,
                 max_z: float = 99.0, col=None, nap_max: int = 6, rng: random.Random | None = None):
    """Convex colliders along thick, near-horizontal limbs + nap spots on their tops."""
    rng = rng or random.Random(3)
    k = 0
    naps = []
    for b in branches:
        if b.level == 0:
            continue
        n = len(b.pts)
        for i in range(n - 1):
            p0, p1 = b.pts[i], b.pts[i + 1]
            r = (b.radii[i] + b.radii[i + 1]) * 0.5
            if r < min_r or p0.z > max_z:
                continue
            d = (p1 - p0)
            slope = math.degrees(math.asin(max(-1.0, min(1.0, d.normalized().z))))
            res.colliders.append(prism_collider(f"col_wood_climb_{name}L{k}", p0, p1, r * 0.95, 8, col))
            k += 1
            if abs(slope) < max_slope_deg and r >= min_r * 1.15:
                naps.append((r, (p0 + p1) * 0.5 + Vector((0, 0, r * 0.95))))
    naps.sort(key=lambda x: -x[0])
    chosen = []
    for r, p in naps:
        if all((p - q).length > 1.2 for q in chosen):
            chosen.append(p)
        if len(chosen) >= nap_max:
            break
    res.nap.extend(chosen)


def climb_points_on_trunk(res: TreeResult, trunk: Branch, heights, facing: Vector = Vector((0, -1, 0)),
                          rscale: float = 0.95):
    for h in heights:
        best = min(range(len(trunk.pts)), key=lambda i: abs(trunk.pts[i].z - h))
        p, r = trunk.pts[best], trunk.radii[best] * rscale
        res.climb.append(p + facing.normalized() * r)
