"""Geometry helpers for the street-props kit (bmesh based, Blender 5.2).

All builders return a linked bpy Object with transforms applied (object origin = world origin),
so parts can be joined freely. Units are metres, Z up, prop front faces -Y.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Iterable, Sequence

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector, noise

_COL_COUNT = {"n": 0}


# ---------------------------------------------------------------------------
# basics
# ---------------------------------------------------------------------------
def obj_from_bm(name: str, bm: bmesh.types.BMesh, mat=None) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    return ob


def place(ob: bpy.types.Object, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)) -> bpy.types.Object:
    """Bake a transform (rot in degrees, XYZ euler) into the mesh."""
    if isinstance(scale, (int, float)):
        scale = (scale,) * 3
    m = Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4() \
        @ Matrix.Diagonal((*scale, 1.0))
    ob.data.transform(m)
    ob.data.update()
    return ob


def transform(ob, m: Matrix):
    ob.data.transform(m)
    ob.data.update()
    return ob


def copy(ob: bpy.types.Object, name: str | None = None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    me = ob.data.copy()
    o2 = bpy.data.objects.new(name or ob.name + "_c", me)
    bpy.context.scene.collection.objects.link(o2)
    return place(o2, loc, rot, scale)


def set_mat(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.material_index = 0
    return ob


def join(objs: Sequence[bpy.types.Object], name: str) -> bpy.types.Object:
    objs = [o for o in objs if o is not None]
    ensure_label_layers(objs)
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = ctx.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


def ensure_label_layers(objs):
    """Every part gets a LabelUV layer (far outside 0..1 unless a label was projected) and a
    per-face texel-importance attribute "uvw" (1.0 unless set with uv_weight)."""
    for o in objs:
        me = o.data
        if "LabelUV" not in me.uv_layers:
            lay = me.uv_layers.new(name="LabelUV")
            n = len(lay.data)
            lay.data.foreach_set("uv", [-8.0] * (2 * n))
        if "uvw" not in me.attributes:
            at = me.attributes.new("uvw", "FLOAT", "FACE")
            at.data.foreach_set("value", [1.0] * len(me.polygons))
        if "preuv" not in me.attributes:
            at = me.attributes.new("preuv", "FLOAT", "FACE")
            at.data.foreach_set("value", [0.0] * len(me.polygons))
        if "UVMap" not in me.uv_layers:
            me.uv_layers.new(name="UVMap")


def uv_weight(ob, w: float, zmin: float | None = None, zmax: float | None = None):
    """Texel importance for (some) faces: islands are scaled by w before packing (w < 1 = less
    texture space, e.g. the upper shaft of a 7 m pole that is only seen from afar)."""
    ensure_label_layers([ob])
    me = ob.data
    at = me.attributes["uvw"]
    for p in me.polygons:
        z = p.center.z
        if (zmin is None or z >= zmin) and (zmax is None or z <= zmax):
            at.data[p.index].value = w
    return ob


def delete(ob):
    bpy.data.objects.remove(ob, do_unlink=True)


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def rbox(name, size, loc=(0, 0, 0), bevel=0.004, segs=2, mat=None, rot=(0, 0, 0), centre=False):
    """Bevelled box; loc = bottom centre (or centre when centre=True)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz + (0 if centre else sz * 0.5)))
    if bevel > 0:
        b = min(bevel, min(size) * 0.45)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=segs, profile=0.5, affect="EDGES",
                        clamp_overlap=True)
    ob = obj_from_bm(name, bm, mat)
    return place(ob, loc, rot)


def cyl(name, r, h, loc=(0, 0, 0), segs=24, bevel=0.002, mat=None, rot=(0, 0, 0), r2=None, cap=True,
        bseg=2):
    """Cylinder/frustum standing on loc (bottom centre), axis Z before rotation."""
    r2 = r if r2 is None else r2
    prof = [(0.0, 0.0), (r, 0.0), (r2, h), (0.0, h)] if cap else [(r, 0.0), (r2, h)]
    ob = lathe(name, prof, segs, mat=mat, smooth_angle=None)
    if bevel > 0:
        bevel_sharp(ob, bevel, bseg, angle=50)
    return place(ob, loc, rot)


def lathe(name, prof: Sequence[tuple], segs=32, mat=None, loc=(0, 0, 0), rot=(0, 0, 0),
          smooth_angle: float | None = 40.0, phase=0.0, rfunc: Callable | None = None):
    """Surface of revolution around Z from a profile [(r, z), ...] (bottom to top).
    r == 0 endpoints become poles (closed caps). rfunc(r, z, angle) -> r for wobble/flutes."""
    prof = list(prof)
    if len(prof) >= 3:
        # auto-orient: a counter-clockwise (r, z) polygon gives outward normals
        area = 0.0
        for i in range(len(prof)):
            r1, z1 = prof[i]
            r2, z2 = prof[(i + 1) % len(prof)]
            area += r1 * z2 - r2 * z1
        if area < -1e-12:
            prof = prof[::-1]
    bm = bmesh.new()
    rings = []
    for (r, z) in prof:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
            continue
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs + phase
            rr = rfunc(r, z, a) if rfunc else r
            ring.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, z)))
        rings.append(ring)
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for i in range(segs):
                bm.faces.new((A[0], B[(i + 1) % segs], B[i]))
        elif len(B) == 1:
            for i in range(segs):
                bm.faces.new((A[i], A[(i + 1) % segs], B[0]))
        else:
            for i in range(segs):
                bm.faces.new((A[i], A[(i + 1) % segs], B[(i + 1) % segs], B[i]))
    ob = obj_from_bm(name, bm, mat)
    place(ob, loc, rot)
    for p in ob.data.polygons:
        p.use_smooth = True
    if smooth_angle is not None:
        mark_sharp(ob, smooth_angle)
    return ob


def tube(name, pts: Sequence[Sequence[float]], r=0.01, segs=8, mat=None, closed=False, cap=True,
         rfunc: Callable | None = None, twist=0.0):
    """Sweep a circle along a polyline (parallel transport frames). rfunc(t 0..1) -> radius factor."""
    P = [Vector(p) for p in pts]
    n = len(P)
    T = []
    for i in range(n):
        if closed:
            d = P[(i + 1) % n] - P[i - 1]
        else:
            d = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T.append(d.normalized() if d.length > 1e-9 else Vector((0, 0, 1)))
    up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    Nrm = [T[0].cross(up).normalized()]
    for i in range(1, n):
        v = Nrm[-1] - T[i] * Nrm[-1].dot(T[i])
        Nrm.append(v.normalized() if v.length > 1e-9 else Nrm[-1])
    bm = bmesh.new()
    rings = []
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (P[i] - P[i - 1]).length)
    tot = L[-1] if L[-1] > 0 else 1.0
    for i in range(n):
        B = T[i].cross(Nrm[i])
        k = rfunc(L[i] / tot) if rfunc else 1.0
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs + twist * L[i]
            ring.append(bm.verts.new(P[i] + (Nrm[i] * math.cos(a) + B * math.sin(a)) * r * k))
        rings.append(ring)
    m = n if closed else n - 1
    for i in range(m):
        A, Bq = rings[i], rings[(i + 1) % n]
        for j in range(segs):
            bm.faces.new((A[j], A[(j + 1) % segs], Bq[(j + 1) % segs], Bq[j]))
    side_faces = len(bm.faces)
    if cap and not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])
    # parametric UVs in metres: u around the tube, v along it (one seam), caps as small disks
    uvl = bm.loops.layers.uv.new("UVMap")
    circ = 2 * math.pi * r
    bm.faces.ensure_lookup_table()
    ring_index = {}
    for i, ring in enumerate(rings):
        for j, v in enumerate(ring):
            ring_index[v] = (i, j)
    for f in bm.faces[:side_faces]:
        js = [ring_index[l.vert][1] for l in f.loops]
        wrap = max(js) == segs - 1 and min(js) == 0
        for l in f.loops:
            i, j = ring_index[l.vert]
            jj = segs if (wrap and j == 0) else j
            l[uvl].uv = (jj / segs * circ, L[i])
    for f in bm.faces[side_faces:]:
        for l in f.loops:
            i, j = ring_index[l.vert]
            a = 2 * math.pi * j / segs
            l[uvl].uv = (math.cos(a) * r, math.sin(a) * r)
    ob = obj_from_bm(name, bm, mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    if cap and not closed:
        mark_sharp(ob, 60)
    at = ob.data.attributes.new("preuv", "FLOAT", "FACE")
    at.data.foreach_set("value", [1.0] * len(ob.data.polygons))
    return ob


def extrude(name, pts2d: Sequence[tuple], depth: float, mat=None, bevel=0.0, segs=2, loc=(0, 0, 0),
            rot=(0, 0, 0), centre=True):
    """Polygon in XY extruded along +Z by depth (centered on z=0 if centre)."""
    bm = bmesh.new()
    z0 = -depth / 2 if centre else 0.0
    vs = [bm.verts.new((x, y, z0)) for (x, y) in pts2d]
    f = bm.faces.new(vs)
    if f.normal.z > 0:
        f.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    for v in top:
        v.co.z += depth
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, profile=0.5, affect="EDGES",
                        clamp_overlap=True)
    ob = obj_from_bm(name, bm, mat)
    return place(ob, loc, rot)


def sheet(name, pts2d, mat=None, loc=(0, 0, 0), rot=(0, 0, 0), subdiv=0):
    """Single-sided flat polygon (for '2s' materials: leaves, cloth, paper)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0.0)) for (x, y) in pts2d]
    bm.faces.new(vs)
    if subdiv:
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=subdiv, use_grid_fill=True)
    ob = obj_from_bm(name, bm, mat)
    return place(ob, loc, rot)


def grid(name, sx, sy, nx, ny, mat=None, fn: Callable | None = None):
    """Grid in XY centred at origin; fn(x, y) -> z height (or Vector offset)."""
    bm = bmesh.new()
    vv = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = (i / nx - 0.5) * sx
            y = (j / ny - 0.5) * sy
            z = 0.0
            p = Vector((x, y, z))
            if fn:
                r = fn(x, y)
                p = p + (r if isinstance(r, Vector) else Vector((0, 0, r)))
            row.append(bm.verts.new(p))
        vv.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vv[j][i], vv[j][i + 1], vv[j + 1][i + 1], vv[j + 1][i]))
    ob = obj_from_bm(name, bm, mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def sphere(name, r, loc=(0, 0, 0), segs=16, rings=10, mat=None, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    ob = obj_from_bm(name, bm, mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return place(ob, loc, (0, 0, 0), scale)


def solidify(ob, thickness, offset=-1.0, rim=True):
    m = ob.modifiers.new("Solid", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_rim = rim
    m.use_even_offset = True
    apply_mods(ob)
    return ob


def subsurf(ob, levels=1):
    m = ob.modifiers.new("Sub", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    apply_mods(ob)
    return ob


def apply_mods(ob):
    ctx = bpy.context
    for o in ctx.view_layer.objects:
        o.select_set(False)
    ctx.view_layer.objects.active = ob
    ob.select_set(True)
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def bevel_sharp(ob, width, segs=2, angle=40.0):
    """Bevel edges sharper than `angle` (applied)."""
    m = ob.modifiers.new("Bev", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.use_clamp_overlap = True
    m.profile = 0.5
    apply_mods(ob)
    return ob


def mark_sharp(ob, angle_deg=40.0):
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < lim
        else:
            e.smooth = True
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()


def weld(ob, dist=1e-5):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


# ---------------------------------------------------------------------------
# deformers ("no perfect primitives")
# ---------------------------------------------------------------------------
def wobble(ob, amp=0.002, scale=3.0, seed=0, axis_mask=(1, 1, 1), zmin=None):
    """Low-frequency 3D noise displacement of vertices (sag, dents, hand-made irregularity)."""
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    for v in ob.data.vertices:
        if zmin is not None and v.co.z < zmin:
            continue
        p = v.co * scale + off
        d = noise.noise_vector(p)
        v.co.x += d.x * amp * axis_mask[0]
        v.co.y += d.y * amp * axis_mask[1]
        v.co.z += d.z * amp * axis_mask[2]
    ob.data.update()
    return ob


def lean(ob, deg_x=0.0, deg_y=0.0, pivot=(0, 0, 0)):
    m = Matrix.Translation(Vector(pivot)) @ Euler((math.radians(deg_x), math.radians(deg_y), 0)).to_matrix().to_4x4() \
        @ Matrix.Translation(-Vector(pivot))
    return transform(ob, m)


def bend_z(ob, fn: Callable):
    """Per-vertex XY offset as a function of z: fn(z) -> (dx, dy)."""
    for v in ob.data.vertices:
        dx, dy = fn(v.co.z)
        v.co.x += dx
        v.co.y += dy
    ob.data.update()
    return ob


def dent(ob, centre, radius, depth, direction=None):
    c = Vector(centre)
    for v in ob.data.vertices:
        d = (v.co - c).length
        if d < radius:
            k = (1 - d / radius) ** 2 * depth
            n = Vector(direction) if direction else (v.normal * -1)
            v.co += n.normalized() * k
    ob.data.update()
    return ob


# ---------------------------------------------------------------------------
# colliders & markers
# ---------------------------------------------------------------------------
def col_box(surface: str, size, loc=(0, 0, 0), rot=(0, 0, 0), tag: str = "", centre=False):
    """Convex box collider (Godot: StaticBody3D + exact BoxShape3D via post-import)."""
    _COL_COUNT["n"] += 1
    nm = f"col_{surface}{('_' + tag) if tag else ''}_{_COL_COUNT['n']:02d}-convcolonly"
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz + (0 if centre else sz * 0.5)))
    ob = obj_from_bm(nm, bm)
    place(ob, loc, rot)
    ob.display_type = "WIRE"
    ob.hide_render = True
    ob["collider"] = True
    return ob


def col_cyl(surface: str, r, h, loc=(0, 0, 0), rot=(0, 0, 0), segs=12, tag: str = "", r2=None):
    _COL_COUNT["n"] += 1
    nm = f"col_{surface}{('_' + tag) if tag else ''}_{_COL_COUNT['n']:02d}-convcolonly"
    r2 = r if r2 is None else r2
    bm = bmesh.new()
    for z, rr in ((0.0, r), (h, r2)):
        for i in range(segs):
            a = 2 * math.pi * i / segs
            bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, z))
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    ob = obj_from_bm(nm, bm)
    place(ob, loc, rot)
    ob.display_type = "WIRE"
    ob.hide_render = True
    ob["collider"] = True
    return ob


def col_hull(surface: str, src: bpy.types.Object, tag: str = "", max_verts=64):
    """Convex hull collider from an object's vertices (decimated by random sampling)."""
    _COL_COUNT["n"] += 1
    nm = f"col_{surface}{('_' + tag) if tag else ''}_{_COL_COUNT['n']:02d}-convcolonly"
    pts = [v.co.copy() for v in src.data.vertices]
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
    bmesh.ops.delete(bm, geom=[v for v in res.get("geom_interior", []) if isinstance(v, bmesh.types.BMVert)],
                     context="VERTS")
    if len(bm.verts) > max_verts:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(12), verts=list(bm.verts), edges=list(bm.edges))
    ob = obj_from_bm(nm, bm)
    ob.display_type = "WIRE"
    ob.hide_render = True
    ob["collider"] = True
    return ob


def reset_counters():
    _COL_COUNT["n"] = 0


def marker(name: str, loc=(0, 0, 0), rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.05
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot]
    bpy.context.scene.collection.objects.link(e)
    return e


# ---------------------------------------------------------------------------
# label UVs (LabelUV layer, sampled from the prop's label sheet)
# ---------------------------------------------------------------------------
def label_planar(ob, rect, origin, u_axis, v_axis, size, normal=None, min_dot=0.5, bounds_pad=0.0):
    """Project faces onto a plane: point p -> ((p-origin).u / size[0], (p-origin).v / size[1]) mapped into
    rect (u0, v0, u1, v1) of the label sheet (v up). Only faces facing `normal` and inside the rectangle."""
    ensure_label_layers([ob])
    me = ob.data
    lay = me.uv_layers["LabelUV"]
    O, U, V = Vector(origin), Vector(u_axis).normalized(), Vector(v_axis).normalized()
    nrm = Vector(normal).normalized() if normal else None
    u0, v0, u1, v1 = rect
    for p in me.polygons:
        if nrm is not None and p.normal.dot(nrm) < min_dot:
            continue
        coords = []
        ok = True
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a = (co - O).dot(U) / size[0]
            b = (co - O).dot(V) / size[1]
            if a < -bounds_pad or a > 1 + bounds_pad or b < -bounds_pad or b > 1 + bounds_pad:
                ok = False
                break
            coords.append((li, a, b))
        if not ok:
            continue
        for li, a, b in coords:
            lay.data[li].uv = (u0 + a * (u1 - u0), v0 + b * (v1 - v0))


def label_cyl(ob, rect, z0, z1, a0=-math.pi / 2 - 0.9, a1=-math.pi / 2 + 0.9, radial_min=0.0, centre=(0, 0)):
    """Cylindrical projection around Z: angle a0..a1 (front is -Y => -pi/2) and height z0..z1."""
    ensure_label_layers([ob])
    me = ob.data
    lay = me.uv_layers["LabelUV"]
    u0, v0, u1, v1 = rect
    cx, cy = centre
    for p in me.polygons:
        n = p.normal
        if math.hypot(n.x, n.y) < 0.5:
            continue
        coords = []
        ok = True
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            a = math.atan2(co.y - cy, co.x - cx)
            if math.hypot(co.x - cx, co.y - cy) < radial_min:
                ok = False
                break
            t = (a - a0) / (a1 - a0)
            s = (co.z - z0) / (z1 - z0)
            if not (0 <= t <= 1 and 0 <= s <= 1):
                ok = False
                break
            coords.append((li, t, s))
        if not ok:
            continue
        for li, t, s in coords:
            lay.data[li].uv = (u0 + t * (u1 - u0), v0 + s * (v1 - v0))


def label_all_planar_top(ob, rect, cx, cy, sx, sy):
    """Top-down projection for every upward face inside the rect (sx, sy)."""
    label_planar(ob, rect, (cx - sx / 2, cy - sy / 2, 0), (1, 0, 0), (0, 1, 0), (sx, sy), normal=(0, 0, 1),
                 min_dot=0.3)


# ---------------------------------------------------------------------------
# misc helpers
# ---------------------------------------------------------------------------
def bounds(objs) -> tuple[Vector, Vector]:
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != "MESH":
            continue
        for v in o.data.vertices:
            co = o.matrix_world @ v.co
            mn = Vector(map(min, mn, co))
            mx = Vector(map(max, mx, co))
    return mn, mx


def tris(ob) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def catenary(p0, p1, sag, n=16):
    """Points of a sagging cable between p0 and p1 (parabola approx)."""
    P0, P1 = Vector(p0), Vector(p1)
    out = []
    for i in range(n + 1):
        t = i / n
        p = P0.lerp(P1, t)
        p.z -= sag * 4 * t * (1 - t)
        out.append(p)
    return out


def star_points(n=5, r_out=1.0, r_in=0.4, rot=90.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot) + math.pi * i / n
        pts.append((math.cos(a) * r, math.sin(a) * r))
    return pts


def circle_pts(r, n=24, cx=0.0, cy=0.0, phase=0.0):
    return [(cx + math.cos(phase + 2 * math.pi * i / n) * r, cy + math.sin(phase + 2 * math.pi * i / n) * r) for i in range(n)]


def rounded_rect(w, h, r, n=4):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts
