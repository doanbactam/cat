"""Mesh-building core for the city-houses kit (Blender 5.2, bmesh based, fast).

A `MB` (mesh builder) accumulates geometry for one output object with many materials.
Every face remembers its material name, a tint (RGBA multiplied into the vertex colour)
and its UV mode:
  * "box"  : world-scale box projection using the material's physical tile size,
  * "keep" : the UVs given by the primitive (atlases: signs, decals, glass interiors),
  * "grain_h"/"grain_v": box projection rotated so wood grain runs horizontally/vertically.

At `finish()` the builder creates a mesh object, assigns materials (via a resolver callback),
computes UVs, and writes the vertex colour layer "Col" = tint * grime(world_pos, normal)
where grime is a module-provided callable (macro variation, splash zone, under-ledge dirt).
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector

V = Vector


class MB:
    def __init__(self, name: str):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.col = self.bm.loops.layers.float_color.new("Col")
        self.mat_names: list[str] = []
        self.face_info: dict[int, tuple] = {}  # face index -> (tint, uvmode, uvrot)
        self._fl_tint = self.bm.faces.layers.float_vector.new("tint")  # rgb tint
        self._fl_mode = self.bm.faces.layers.int.new("uvmode")         # 0 box 1 keep 2 grain_h 3 grain_v
        self._fl_alpha = self.bm.faces.layers.float.new("talpha")

    # ------------------------------------------------------------------
    def _mi(self, mat: str) -> int:
        if mat not in self.mat_names:
            self.mat_names.append(mat)
        return self.mat_names.index(mat)

    def add_bm(self, src: bmesh.types.BMesh, mat: str, tint=(1, 1, 1, 1), uvmode: str = "box",
               mat_xform: Matrix | None = None, smooth: bool = False, src_uv: bool = False) -> None:
        """Append all faces of a temporary bmesh (frees it)."""
        if mat_xform is not None:
            bmesh.ops.transform(src, matrix=mat_xform, verts=src.verts)
        mi = self._mi(mat)
        mode = {"box": 0, "keep": 1, "grain_h": 2, "grain_v": 3}[uvmode]
        vmap = {}
        for v in src.verts:
            vmap[v] = self.bm.verts.new(v.co)
        suv = src.loops.layers.uv.active if src_uv else None
        t3 = V(tint[:3])
        for f in src.faces:
            try:
                nf = self.bm.faces.new([vmap[v] for v in f.verts])
            except ValueError:
                continue
            nf.material_index = mi
            nf.smooth = smooth
            nf[self._fl_tint] = t3
            nf[self._fl_mode] = mode
            nf[self._fl_alpha] = tint[3] if len(tint) > 3 else 1.0
            if suv is not None:
                for la, lb in zip(f.loops, nf.loops):
                    lb[self.uv].uv = la[suv].uv
        src.free()

    # ------------------------------------------------------------------
    # Primitives
    # ------------------------------------------------------------------
    def box(self, mn: Sequence[float], mx: Sequence[float], mat: str, tint=(1, 1, 1, 1),
            bevel: float = 0.0, segs: int = 1, xform: Matrix | None = None, uvmode: str = "box",
            skip: Sequence[str] = ()) -> None:
        """Axis-aligned box from min/max corners (then optional transform). skip: faces to delete
        among '-x','+x','-y','+y','-z','+z' (hidden faces, saves tris)."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        c = [(a + b) / 2 for a, b in zip(mn, mx)]
        s = [max(b - a, 1e-4) for a, b in zip(mn, mx)]
        for v in bm.verts:
            v.co = V((v.co.x * s[0] + c[0], v.co.y * s[1] + c[1], v.co.z * s[2] + c[2]))
        if bevel > 0:
            bw = min(bevel, min(s) * 0.45)
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bw, segments=segs, profile=0.5,
                            affect="EDGES", clamp_overlap=True)
        if skip:
            dirs = {"-x": V((-1, 0, 0)), "+x": V((1, 0, 0)), "-y": V((0, -1, 0)), "+y": V((0, 1, 0)),
                    "-z": V((0, 0, -1)), "+z": V((0, 0, 1))}
            kill = [f for f in bm.faces if any(f.normal.dot(dirs[k]) > 0.999 for k in skip)]
            bmesh.ops.delete(bm, geom=kill, context="FACES")
        self.add_bm(bm, mat, tint, uvmode, xform)

    def quad(self, pts: Sequence[Sequence[float]], mat: str, tint=(1, 1, 1, 1), uvs=None,
             uvmode: str | None = None, double: bool = False) -> None:
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in pts]
        f = bm.faces.new(vs)
        if uvs is not None:
            uvl = bm.loops.layers.uv.new("UVMap")
            for l, uv in zip(f.loops, uvs):
                l[uvl].uv = uv
        if double:
            vs2 = [bm.verts.new(p) for p in reversed(pts)]
            f2 = bm.faces.new(vs2)
            if uvs is not None:
                for l, uv in zip(f2.loops, list(reversed(uvs))):
                    l[uvl].uv = uv
        self.add_bm(bm, mat, tint, uvmode or ("keep" if uvs is not None else "box"), src_uv=uvs is not None)

    def grid_quad(self, origin, ax_u, ax_v, nu: int, nv: int, mat: str, tint=(1, 1, 1, 1)) -> None:
        """Subdivided planar quad (for vertex-colour resolution). origin + u*ax_u + v*ax_v."""
        bm = bmesh.new()
        o, au, av = V(origin), V(ax_u), V(ax_v)
        grid = [[bm.verts.new(o + au * (i / nu) + av * (j / nv)) for i in range(nu + 1)] for j in range(nv + 1)]
        for j in range(nv):
            for i in range(nu):
                bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
        self.add_bm(bm, mat, tint)

    def prism(self, profile2d: Sequence[tuple[float, float]], path_a, path_b, mat: str, tint=(1, 1, 1, 1),
              cap: bool = True, uvmode: str = "box", smooth: bool = False) -> None:
        """Extrude a 2D profile (in the plane perpendicular to a->b; profile x = right, y = up)
        from point a to b. Used for cornices, mouldings, gutters, rails."""
        a, b = V(path_a), V(path_b)
        d = (b - a).normalized()
        up = V((0, 0, 1))
        if abs(d.dot(up)) > 0.99:
            up = V((0, 1, 0))
        right = d.cross(up).normalized()
        upv = right.cross(d).normalized()
        bm = bmesh.new()
        ra = [bm.verts.new(a + right * px + upv * py) for px, py in profile2d]
        rb = [bm.verts.new(b + right * px + upv * py) for px, py in profile2d]
        n = len(profile2d)
        for i in range(n - 1):
            bm.faces.new([ra[i], ra[i + 1], rb[i + 1], rb[i]])
        if cap and n >= 3:
            try:
                bm.faces.new(list(reversed(ra)))
                bm.faces.new(rb)
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self.add_bm(bm, mat, tint, uvmode, smooth=smooth)

    def tube(self, pts: Sequence[Sequence[float]], radius: float, mat: str, tint=(1, 1, 1, 1), sides: int = 6,
             caps: bool = True, radii: Sequence[float] | None = None, smooth: bool = True,
             square: bool = False) -> None:
        """Polyline tube with parallel-transport frames. square=True -> 4 sides rotated 45deg
        (flat bar look for wrought iron)."""
        P = [V(p) for p in pts]
        if len(P) < 2:
            return
        if square:
            sides = 4
        bm = bmesh.new()
        rings = []
        tang = []
        for i in range(len(P)):
            if i == 0:
                t = P[1] - P[0]
            elif i == len(P) - 1:
                t = P[-1] - P[-2]
            else:
                t = (P[i + 1] - P[i]).normalized() + (P[i] - P[i - 1]).normalized()
            if t.length < 1e-9:
                t = V((0, 0, 1))
            tang.append(t.normalized())
        ref = V((0, 0, 1)) if abs(tang[0].z) < 0.9 else V((1, 0, 0))
        nrm = tang[0].cross(ref).normalized()
        for i, p in enumerate(P):
            if i > 0:  # parallel transport
                axis = tang[i - 1].cross(tang[i])
                if axis.length > 1e-6:
                    ang = tang[i - 1].angle(tang[i])
                    nrm = Matrix.Rotation(ang, 3, axis.normalized()) @ nrm
            bin_ = tang[i].cross(nrm).normalized()
            r = radii[i] if radii else radius
            ring = []
            for k in range(sides):
                a = 2 * math.pi * k / sides + (math.pi / 4 if square else 0)
                ring.append(bm.verts.new(p + (nrm * math.cos(a) + bin_ * math.sin(a)) * r))
            rings.append(ring)
        for i in range(len(rings) - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                bm.faces.new([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]])
        if caps:
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        self.add_bm(bm, mat, tint, "box", smooth=smooth and not square)

    def cylinder(self, base, axis, radius: float, length: float, mat: str, tint=(1, 1, 1, 1), sides: int = 16,
                 caps: bool = True, smooth: bool = True) -> None:
        a = V(base)
        b = a + V(axis).normalized() * length
        self.tube([a, b], radius, mat, tint, sides, caps, smooth=smooth)

    # ------------------------------------------------------------------
    def finish(self, resolve_mat: Callable[[str], bpy.types.Material], tile_of: Callable[[str], float],
               grime: Callable[[Vector, Vector, str], tuple] | None = None, col=None,
               uv_offset: tuple[float, float] = (0.0, 0.0), merge_dist: float = 0.0) -> bpy.types.Object | None:
        bm = self.bm
        if not bm.faces:
            bm.free()
            return None
        if merge_dist > 0:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:  # tangents (normal maps) need tris/quads
            bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        degen = [f for f in bm.faces if f.calc_area() < 1e-9]
        if degen:
            bmesh.ops.delete(bm, geom=degen, context="FACES")
        bm.normal_update()
        ou, ov = uv_offset
        for f in bm.faces:
            mode = f[self._fl_mode]
            mat = self.mat_names[f.material_index]
            n = f.normal
            if mode != 1:
                s = 1.0 / max(tile_of(mat), 1e-3)
                ax = max(range(3), key=lambda i: abs(n[i]))
                for l in f.loops:
                    co = l.vert.co
                    if ax == 0:
                        u, v = (co.y if n.x > 0 else -co.y), co.z
                    elif ax == 1:
                        u, v = (-co.x if n.y > 0 else co.x), co.z
                    else:
                        u, v = co.x, (co.y if n.z > 0 else -co.y)
                    if mode == 2:   # grain horizontal: swap
                        u, v = v, u
                    l[self.uv].uv = (u * s + ou, v * s + ov)
            t = f[self._fl_tint]
            ta = f[self._fl_alpha]
            for l in f.loops:
                g = grime(l.vert.co, n, mat) if grime else (1.0, 1.0, 1.0)
                l[self.col] = (t[0] * g[0], t[1] * g[1], t[2] * g[2], ta)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(self.name, me)
        (col or bpy.context.scene.collection).objects.link(ob)
        for mn in self.mat_names:
            me.materials.append(resolve_mat(mn))
        # remove helper attributes (not needed in export)
        for nm in ("tint", "uvmode", "talpha"):
            a = me.attributes.get(nm)
            if a is not None:
                me.attributes.remove(a)
        me.color_attributes.active_color = me.color_attributes["Col"]
        return ob


def smooth_weighted(ob: bpy.types.Object, angle_deg: float = 35.0, weighted: bool = True) -> None:
    """Smooth-by-angle + weighted normals (harden large faces next to bevels)."""
    me = ob.data
    # mark sharp edges by angle, keep per-face smooth flags set by the builder
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            a = e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)
            e.smooth = a < lim
        else:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    if weighted:
        m = ob.modifiers.new("WN", "WEIGHTED_NORMAL")
        m.keep_sharp = True
        m.weight = 50
        m.mode = "FACE_AREA"


# ---------------------------------------------------------------------------
# Small math helpers
# ---------------------------------------------------------------------------
def rot_z(deg: float, pivot=(0, 0, 0)) -> Matrix:
    p = V(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Z") @ Matrix.Translation(-p)


def rot_x(deg: float, pivot=(0, 0, 0)) -> Matrix:
    p = V(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "X") @ Matrix.Translation(-p)


def rot_y(deg: float, pivot=(0, 0, 0)) -> Matrix:
    p = V(pivot)
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(deg), 4, "Y") @ Matrix.Translation(-p)


def catenary(a, b, sag: float, n: int = 12, jitter: float = 0.0, rng: random.Random | None = None):
    a, b = V(a), V(b)
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        if jitter and rng and 0 < i < n:
            p += V((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * jitter
        pts.append(p)
    return pts


def wall_cells(x0: float, x1: float, z0: float, z1: float, holes: Sequence[tuple[float, float, float, float]],
               max_cell: float = 0.5) -> list[tuple[float, float, float, float]]:
    """Decompose a wall rectangle minus rectangular holes into cells (for facades with openings).
    holes: (hx0, hz0, hx1, hz1). Returns cells (cx0, cz0, cx1, cz1) not covered by holes,
    subdivided so no cell exceeds max_cell (vertex-colour resolution)."""
    xs = {x0, x1}
    zs = {z0, z1}
    for hx0, hz0, hx1, hz1 in holes:
        xs.update([max(x0, min(x1, hx0)), max(x0, min(x1, hx1))])
        zs.update([max(z0, min(z1, hz0)), max(z0, min(z1, hz1))])

    def refine(vals):
        vals = sorted(vals)
        out = [vals[0]]
        for v in vals[1:]:
            d = v - out[-1]
            if d < 1e-5:
                continue
            k = max(1, int(math.ceil(d / max_cell)))
            for i in range(1, k + 1):
                out.append(out[-1] + d / k if i < k else v)
        # fix accumulated error
        return out
    X = refine(xs)
    Z = refine(zs)
    cells = []
    for i in range(len(X) - 1):
        for j in range(len(Z) - 1):
            cx, cz = (X[i] + X[i + 1]) / 2, (Z[j] + Z[j + 1]) / 2
            if any(hx0 < cx < hx1 and hz0 < cz < hz1 for hx0, hz0, hx1, hz1 in holes):
                continue
            cells.append((X[i], Z[j], X[i + 1], Z[j + 1]))
    return cells
