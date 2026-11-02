"""Car body shell generator for Mèo Cam (taxi hatchback, panel van).

A car body is described by a list of *key stations* along the length (Blender Y, front toward -Y).
Each station gives the cross-section parameters

    y      position along the car
    zb     underside height
    zl     belt-line (shoulder) height
    w      half width at the shoulder / max body side
    zt     roof (or hood/boot) height at the centre line minus crown
    wt     half width of the roof (tumblehome)
    crown  extra height of the roof centre

and the *interval* that starts at the station carries flags ("side_glass", "top_glass") that decide
which bands of the cross-section become glass.  The cross-section ring is built from named key points

    P0 bottom-centre, P1 floor edge, P2 sill radius, P3 mid side (max width), P4 shoulder (belt),
    P5 glass bottom (step-in of the belt moulding), P6 roof rail (glass top), P7 roof corner,
    P8 roof half, P9 roof centre

so window openings, pillars and the belt moulding fall exactly on mesh edge loops: the A/B/C pillars
are the painted P6-P7 band and the painted side intervals between windows, the belt moulding is the
black P4-P5 band.  Key stations are Catmull-Rom interpolated so the surfaces are smooth.

Details (lamps, grilles, handles, seams, decals) are *projected patches*: a grid of rays shot at the
finished shell; hits are offset a few mm along the normal so details sit exactly on curved panels.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import common as C
import vehicles_lib as V

# band indices (segment between key point i and i+1)
B_FLOOR, B_SILL, B_LOWER, B_UPPER, B_BELT, B_GLASS, B_RAIL, B_ROOF_EDGE, B_ROOF = range(9)


def _cr(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def _key_points(s):
    zb, zl, w, zt, wt, crown = s["zb"], s["zl"], s["w"], s["zt"], s["wt"], s.get("crown", 0.02)
    tuck = s.get("tuck", 0.06)
    step = s.get("step", 0.035)
    zg = zl + max(0.012, min(0.03, (zt - zl) * 0.15))
    zr = max(zg + 0.01, zt - min(0.045, (zt - zl) * 0.3))
    return [
        (0.0, zb),
        (w - tuck - 0.04, zb),
        (w - tuck * 0.35, zb + 0.05),
        (w, zb + (zl - zb) * 0.5),
        (w - 0.008, zl),
        (w - step, zg),
        (wt + 0.012, zr),
        (wt - 0.022, zt - 0.004),
        (wt * 0.55, zt + crown * 0.8),
        (0.0, zt + crown),
    ]


def _ring2d(s, sub=3):
    """Right half profile from bottom centre to top centre: list of (x, z, band)."""
    K = [Vector(p) for p in _key_points(s)]
    out = []
    n = len(K)
    sharp = {4, 5}           # shoulder + glass bottom stay crisp
    for i in range(n - 1):
        m = 1 if i in (B_BELT, B_RAIL) else sub
        for k in range(m):
            t = k / m
            if i in sharp or (i + 1) in sharp or i == 0:
                p = K[i].lerp(K[i + 1], t)
            else:
                p = _cr(K[max(i - 1, 0)], K[i], K[i + 1], K[min(i + 2, n - 1)], t)
            out.append((p.x, p.y, i))
    out.append((K[-1].x, K[-1].y, n - 2))
    return out


def _interp_station(a, b, c, d, t):
    keys = ("y", "zb", "zl", "w", "zt", "wt", "crown", "tuck", "step")
    r = {}
    for k in keys:
        vals = [s.get(k, {"crown": 0.02, "tuck": 0.06, "step": 0.035}.get(k, 0.0)) for s in (a, b, c, d)]
        r[k] = _cr(*vals, t) if k != "y" else vals[1] + (vals[2] - vals[1]) * t
    return r


def shell(name, stations, paint, sub_len=4, sub_ring=3, trim="veh_plastic_black"):
    """Build the body shell. Returns the object (materials: paint, glass, trim)."""
    S = stations
    rows = []          # (station dict, interval flags)
    for i in range(len(S) - 1):
        steps = S[i].get("steps", sub_len)
        for k in range(steps):
            st = _interp_station(S[max(i - 1, 0)], S[i], S[i + 1], S[min(i + 2, len(S) - 1)], k / steps)
            rows.append((st, S[i]))
    rows.append((dict(S[-1]), S[-1]))
    bm = bmesh.new()
    rings = []
    bands = None
    for st, _ in rows:
        prof = _ring2d(st, sub_ring)
        right = [(x, z) for x, z, _ in prof]
        b = [bd for _, _, bd in prof]
        # full ring: bottom centre -> right side -> top centre -> left side -> (back to bottom centre)
        full = [(x, z) for x, z in right] + [(-x, z) for x, z in reversed(right[1:-1])]
        bfull = b[:-1] + [b[len(b) - 2 - j] for j in range(len(right) - 1)]
        bands = bfull
        rings.append([bm.verts.new((x, st["y"], z)) for x, z in full])
    n = len(rings[0])
    mats = {"paint": 0, "glass": 1, "trim": 2}
    for i in range(len(rings) - 1):
        flags = rows[i][1]
        side_glass = flags.get("side_glass", False)
        top_glass = flags.get("top_glass", False)
        for k in range(n):
            f = bm.faces.new([rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k]])
            bd = bands[k]
            m = "paint"
            if bd == B_BELT and flags.get("belt_trim", True):
                m = "trim"
            if bd == B_GLASS and side_glass:
                m = "glass"
            if bd in (B_ROOF_EDGE, B_ROOF) and top_glass:
                m = "glass"
            if bd == B_FLOOR:
                m = "trim"
            f.material_index = mats[m]
    # caps (fan to a centre vertex)
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        c = sum((v.co for v in ring), Vector()) / len(ring)
        cv = bm.verts.new(c)
        for k in range(n):
            vs = [ring[k], ring[(k + 1) % n], cv]
            f = bm.faces.new(list(reversed(vs)) if rev else vs)
            f.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = C.mesh_from_bmesh(name, bm)
    for mname in (paint, "veh_glass", trim):
        ob.data.materials.append(V.mat(mname))
    C.uv_cube_project(ob, 1.0)
    C.shade_smooth(ob, 32)
    return ob


# ---------------------------------------------------------------------------
# projected details
# ---------------------------------------------------------------------------
class Surface:
    def __init__(self, ob):
        self.bvh = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())

    def hit(self, origin, direction, dist=3.0):
        loc, nrm, _, _ = self.bvh.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
        return (loc, nrm) if loc is not None else (None, None)


def patch(name, surf, axis, center, size, material, offset=0.003, res=(8, 4), uv_rect=None, rot=0.0,
          thickness=0.0, round_corners=0.0):
    """Grid patch projected onto the shell.

    axis: '+X'/'-X' (side, rays shot toward the body from that side), '-Y' (front), '+Y' (rear), '+Z' (top).
    center: 3-D point; the two in-plane coordinates are used.  size: (u, v) extents in the plane.
    uv_rect: (u0, v0, u1, v1) for atlas decals; otherwise box UVs.  round_corners: 0..1 superellipse mask.
    thickness: extrude the patch outward (lamp lenses, grille frames)."""
    cx, cy, cz = center
    su, sv = size
    nu, nv = res
    if axis in ("+X", "-X"):
        s = 1 if axis == "+X" else -1
        d = Vector((-s, 0, 0))

        def org(u, v):
            return Vector((s * 3.0, cy + u * s, cz + v))
    elif axis in ("-Y", "+Y"):
        s = 1 if axis == "-Y" else -1
        d = Vector((0, s, 0))

        def org(u, v):
            return Vector((cx + u * s, -s * 4.0, cz + v))
    else:
        d = Vector((0, 0, -1))

        def org(u, v):
            return Vector((cx + v, cy + u, 4.0))
    cr, sr = math.cos(rot), math.sin(rot)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    grid = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            a, b = (i / nu - 0.5), (j / nv - 0.5)
            if round_corners > 0:
                # pull the grid onto a rounded rectangle
                e = 2 + 10 * (1 - round_corners)
                ra, rb = abs(2 * a), abs(2 * b)
                rr = (ra ** e + rb ** e) ** (1 / e)
                mx = max(ra, rb)
                if rr > 1e-6:
                    sc = mx / rr
                    a, b = a * sc, b * sc
            u, v = a * su, b * sv
            u, v = u * cr - v * sr, u * sr + v * cr
            loc, nrm = surf.hit(org(u, v), d, 8.0)
            if loc is None:
                continue
            if nrm.dot(d) > 0:
                nrm = -nrm
            grid[i, j] = (bm.verts.new(loc + nrm * offset), (i / nu, j / nv), nrm)
    faces = []
    for i in range(nu):
        for j in range(nv):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(k in grid for k in q):
                f = bm.faces.new([grid[k][0] for k in q])
                faces.append(f)
                for l, k in zip(f.loops, q):
                    uu, vv = grid[k][1]
                    if uv_rect:
                        u0, v0, u1, v1 = uv_rect
                        l[uvl].uv = (u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv)
                    else:
                        l[uvl].uv = (uu * su, vv * sv)
    if not faces:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    # orient outward (same side as the ray origin)
    if faces[0].normal.dot(d) > 0:
        bmesh.ops.reverse_faces(bm, faces=faces)
    if thickness > 0:
        r = bmesh.ops.extrude_face_region(bm, geom=faces)
        nv_ = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
        for v in nv_:
            v.co += -d * thickness
        # outer face shrink slightly for a bevelled look
        cen = sum((v.co for v in nv_), Vector()) / len(nv_)
        for v in nv_:
            v.co = cen + (v.co - cen) * 0.97 + (-d) * 0.0
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = C.mesh_from_bmesh(name, bm)
    ob.data.materials.append(V.mat(material) if isinstance(material, str) else material)
    if not uv_rect:
        C.uv_cube_project(ob, 1.0)
    C.shade_smooth(ob, 50)
    return ob


def decal_patch(name, surf, axis, center, size, rect_name, res=(12, 3), offset=0.004):
    from vehicles_decals import DECALS
    x, y, w, h = DECALS[rect_name]
    u0, u1 = x / 1024, (x + w) / 1024
    v0, v1 = 1 - (y + h) / 1024, 1 - y / 1024
    return patch(name, surf, axis, center, size, "veh_decals", offset, res, (u0, v0, u1, v1))


def seam_line(name, surf, axis, pts, width=0.005, offset=0.0015, material="veh_plastic_black", steps=24):
    """Thin dark panel-gap ribbon following a polyline on the surface (pts in world coords, projected
    along `axis`)."""
    d = {"+X": Vector((-1, 0, 0)), "-X": Vector((1, 0, 0)), "-Y": Vector((0, 1, 0)), "+Y": Vector((0, -1, 0)),
         "+Z": Vector((0, 0, -1))}[axis]
    P = [Vector(p) for p in pts]
    samp = []
    for i in range(len(P) - 1):
        for k in range(steps):
            samp.append(P[i].lerp(P[i + 1], k / steps))
    samp.append(P[-1])
    hits = []
    for p in samp:
        loc, nrm = surf.hit(p - d * 3.0, d, 6.0)
        if loc is not None:
            if nrm.dot(d) > 0:
                nrm = -nrm
            hits.append((loc, nrm))
    if len(hits) < 2:
        return None
    bm = bmesh.new()
    prev = None
    for i, (loc, nrm) in enumerate(hits):
        t = (hits[min(i + 1, len(hits) - 1)][0] - hits[max(i - 1, 0)][0])
        if t.length < 1e-6:
            continue
        side = t.cross(nrm).normalized() * width * 0.5
        a = bm.verts.new(loc + nrm * offset + side)
        b = bm.verts.new(loc + nrm * offset - side)
        if prev:
            try:
                bm.faces.new([prev[0], prev[1], b, a])
            except ValueError:
                pass
        prev = (a, b)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.dot(d) > 0:
            f.normal_flip()
    ob = C.mesh_from_bmesh(name, bm)
    ob.data.materials.append(V.mat(material))
    C.uv_cube_project(ob, 1.0)
    return ob
