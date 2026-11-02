"""Parametric parts of Cam that are not part of the SDF skin:
ears (thin cartilage shells with cavity), eyeballs (concave iris + bulging cornea),
teeth, tongue, whiskers and ear furnishings.  All authored in head design space
and mapped to the body with cat_anatomy.head_to_world()."""
from __future__ import annotations

import math
import os

import bmesh
import bpy
import numpy as np

import cat_anatomy as A
import cat_mesh as M
import cat_sdf as S


def head_to_world_np(v: np.ndarray) -> np.ndarray:
    return A.head_to_world_np(v)


def _nrm(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
# Ears
# ---------------------------------------------------------------------------
EAR_H = 0.0425          # design space (x1.10 -> ~0.047 m)
EAR_W = 0.0345
EAR_NU, EAR_NV = 12, 11
EAR_TUFTS = 5           # soft furnishing cards per ear (more read as a white comb)


def ear_frame(side: int = 1):
    base = np.asarray(A.EAR_BASE_L) * np.array([side, 1, 1])
    a = _nrm((side * math.sin(math.radians(14)), 0.08, math.cos(math.radians(14))))
    n = np.array([side * math.sin(math.radians(24)), -math.cos(math.radians(24)), 0.05])
    n = _nrm(n - np.dot(n, a) * a)
    b = _nrm(np.cross(a, n))
    if b[0] * side < 0:
        b = -b
    return base, a, n, b


def ear_surface(side: int = 1):
    """Single-sheet ear (cup facing +n). Returns verts (N,3) in head space, quads, v-param."""
    base, a, n, b = ear_frame(side)
    vs = np.concatenate([np.linspace(-0.20, 0.0, 3)[:-1], np.linspace(0.0, 1.0, EAR_NV)])
    us = np.linspace(-1.0, 1.0, EAR_NU + 1)
    verts, vpar = [], []
    for v in vs:
        vv = max(v, 0.0)
        w = 0.5 * EAR_W * (1.0 - vv) ** 0.80 * (1.0 + 0.28 * vv * (1.0 - vv))
        if v < 0:
            w = 0.5 * EAR_W * (1.0 + 0.35 * (-v))
        sag = w * (0.58 - 0.32 * vv)
        for u in us:
            ww = w * (1.0 + 0.10 * math.sin(math.pi * vv)) if u > 0 else w * (1.0 - 0.04 * math.sin(math.pi * vv))
            # Henry's pocket: small fold/notch at the lateral base edge
            hp = math.exp(-((vv - 0.16) / 0.07) ** 2) * max(0.0, (u - 0.6) / 0.4) if v >= 0 else 0.0
            ww *= 1.0 - 0.10 * hp
            p = (base + a * (EAR_H * v) + b * (ww * u)
                 - n * (sag * (1 - u * u)) - n * (0.10 * EAR_H * vv * vv)
                 + n * (0.0022 * hp))
            verts.append(p)
            vpar.append(v)
    verts = np.array(verts)
    nu1 = len(us)
    quads = []
    for j in range(len(vs) - 1):
        for i in range(len(us) - 1):
            k = j * nu1 + i
            quads.append((k, k + 1, k + 1 + nu1, k + nu1))
    return verts, np.array(quads), np.array(vpar), n


def build_ear(name: str, side: int, col=None) -> bpy.types.Object:
    v, q, vpar, n = ear_surface(side)
    ob = M.mesh_from_arrays(name, v, q, col)
    # weld the collapsed tip, orient normals towards the cavity (+n)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    avg = np.sum([np.array(f.normal) for f in bm.faces], axis=0)
    if np.dot(avg, n) < 0:
        for f in bm.faces:
            f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    # thickness: 2.0 mm at the base -> 1.1 mm at the tip (design space)
    vg = ob.vertex_groups.new(name="thick")
    co = M.get_verts(ob)
    base, a, _, _ = ear_frame(side)
    h = np.clip(((co - base) @ a) / EAR_H, 0, 1)
    for i, hv in enumerate(h):
        vg.add([i], float(1.0 - 0.45 * hv), "REPLACE")
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.0020
    sol.offset = -1.0
    sol.use_even_offset = True
    sol.use_rim = True
    sol.vertex_group = "thick"
    sol.thickness_vertex_group = 0.55
    sub = ob.modifiers.new("Subsurf", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    import common as C
    C.apply_modifiers(ob)
    co = M.get_verts(ob)
    M.set_verts(ob, head_to_world_np(co))
    ob.vertex_groups.clear()
    g = ob.vertex_groups.new(name="part_ear_" + ("L" if side > 0 else "R"))
    g.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    return ob


# ---------------------------------------------------------------------------
# Eyes
# ---------------------------------------------------------------------------
LIMBUS_DEG = 56.0          # cat irises are huge: little sclera ever shows


def _eye_geometry(side: int):
    c, g, u, v = S.eye_frame(side)
    # undo the aperture tilt for the texture frame: keep pupil vertical in head space
    up = np.array([0.0, 0.0, 1.0])
    uu = _nrm(np.cross(g, up))
    if uu[0] * side < 0:
        uu = -uu
    vv = _nrm(np.cross(uu, g))
    if vv[2] < 0:
        vv = -vv
    return c, g, uu, vv


def build_eye(side: int, col=None):
    """Returns (eyeball_obj, cornea_obj) in world space with UVs (planar along gaze)."""
    c, g, uu, vv = _eye_geometry(side)
    R = A.EYE_RADIUS
    tl = math.radians(LIMBUS_DEG)
    rho_l = R * math.sin(tl)
    s_l = R * math.cos(tl)
    s_iris = s_l - 0.0007
    nseg = 40
    # rings: list of (rho, s)
    rings = []
    for k in range(1, 7):                       # iris (pupil centre handled by a pole)
        t = k / 6.0
        rho = rho_l * 0.985 * t
        rings.append((rho, s_iris + 0.0007 * (1 - t * t)))
    rings.append((rho_l, s_iris))               # limbal wall bottom
    for k in range(0, 13):                      # sclera: theta from limbus to back
        th = tl + (math.pi - 0.15 - tl) * (k / 12.0) ** 1.1
        rings.append((R * math.sin(th), R * math.cos(th)))
    verts = [c + g * (s_iris + 0.0007)]
    for rho, s in rings:
        for i in range(nseg):
            a = 2 * math.pi * i / nseg
            verts.append(c + g * s + uu * (rho * math.cos(a)) + vv * (rho * math.sin(a)))
    verts = np.array(verts)
    faces_t, faces_q = [], []
    for i in range(nseg):
        faces_t.append((0, 1 + i, 1 + (i + 1) % nseg))
    for r in range(len(rings) - 1):
        o0, o1 = 1 + r * nseg, 1 + (r + 1) * nseg
        for i in range(nseg):
            j = (i + 1) % nseg
            faces_q.append((o0 + i, o1 + i, o1 + j, o0 + j))
    name = "CatEyeball_" + ("L" if side > 0 else "R")
    ob = M.mesh_from_arrays(name, verts, [np.array(faces_q), np.array(faces_t)], col)
    _planar_uv(ob, c, uu * side, vv, R)
    # cornea: spherical cap through the limbus with apex at R + 1.1 mm, continuing as a thin
    # tear film over the sclera to 72 deg so the highlight never stops at the limbus
    apex = R + 0.0011
    h = apex - s_l
    rc = (rho_l ** 2 + h ** 2) / (2 * h)
    cc = apex - rc
    cverts = [c + g * apex]
    crings = []
    for k in range(1, 10):
        t = k / 9.0
        phi = math.asin(min(1.0, rho_l / rc)) * t
        crings.append((rc * math.sin(phi), cc + rc * math.cos(phi)))
    for k in range(1, 4):
        th = tl + math.radians(22) * k / 3.0
        crings.append(((R + 0.00012) * math.sin(th), (R + 0.00012) * math.cos(th)))
    for rho, s in crings:
        for i in range(nseg):
            a = 2 * math.pi * i / nseg
            cverts.append(c + g * s + uu * (rho * math.cos(a)) + vv * (rho * math.sin(a)))
    cverts = np.array(cverts)
    ct, cq = [], []
    for i in range(nseg):
        ct.append((0, 1 + i, 1 + (i + 1) % nseg))
    for r in range(len(crings) - 1):
        o0, o1 = 1 + r * nseg, 1 + (r + 1) * nseg
        for i in range(nseg):
            j = (i + 1) % nseg
            cq.append((o0 + i, o1 + i, o1 + j, o0 + j))
    cname = "CatCornea_" + ("L" if side > 0 else "R")
    cob = M.mesh_from_arrays(cname, cverts, [np.array(cq), np.array(ct)], col)
    _planar_uv(cob, c, uu * side, vv, R)
    for o in (ob, cob):
        # make sure faces point outwards (away from the eye centre)
        me = o.data
        me.update()
        fc = np.array([p.center for p in me.polygons])
        fn = np.array([p.normal for p in me.polygons])
        if np.mean(np.einsum("ij,ij->i", fc - c, fn)) < 0:
            me.flip_normals()
        M.set_verts(o, head_to_world_np(M.get_verts(o)))
    return ob, cob


def _planar_uv(ob, c, uu, vv, R):
    me = ob.data
    uvl = me.uv_layers.new(name="UVMap")
    co = M.get_verts(ob)
    li = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", li)
    q = co[li] - c
    uv = np.stack([0.5 + 0.5 * (q @ uu) / R, 0.5 + 0.5 * (q @ vv) / R], 1)
    uvl.data.foreach_set("uv", uv.astype(np.float32).ravel())


# ---------------------------------------------------------------------------
# Mouth parts: teeth (canines + incisors) and tongue
# ---------------------------------------------------------------------------
def _jaw_rest(v: np.ndarray) -> np.ndarray:
    """jaw 'closed' design coords -> head design coords (rest pose is open)."""
    h = np.asarray(A.JAW)
    R = S.rot_axis((1, 0, 0), A.JAW_REST_OPEN_DEG)
    return (v - h) @ R.T + h


def _tooth(root, direction, length, radius, curl, nseg=6, nring=5):
    d = _nrm(direction)
    side = _nrm(np.cross(d, (1.0, 0.0, 0.0)) if abs(d[0]) < 0.9 else np.cross(d, (0.0, 1.0, 0.0)))
    side2 = np.cross(d, side)
    verts, faces = [], []
    for k in range(nring):
        t = k / (nring - 1)
        rad = radius * (1.0 - t) ** 0.8 + 0.00008
        c = np.asarray(root) + d * (length * t) + np.asarray(curl) * (length * t * t)
        for i in range(nseg):
            a = 2 * math.pi * i / nseg
            verts.append(c + side * (rad * math.cos(a)) + side2 * (rad * 0.8 * math.sin(a)))
    tip = np.asarray(root) + d * (length * 1.02) + np.asarray(curl) * length
    verts.append(tip)
    for k in range(nring - 1):
        for i in range(nseg):
            j = (i + 1) % nseg
            faces.append((k * nseg + i, k * nseg + j, (k + 1) * nseg + j, (k + 1) * nseg + i))
    tri = []
    last = (nring - 1) * nseg
    for i in range(nseg):
        tri.append((last + i, last + (i + 1) % nseg, len(verts) - 1))
    return np.array(verts), np.array(faces), np.array(tri)


def _merge(parts):
    V, Q, T = [], [], []
    off = 0
    for v, q, t in parts:
        V.append(v)
        if len(q):
            Q.append(q + off)
        if len(t):
            T.append(t + off)
        off += len(v)
    return np.concatenate(V), (np.concatenate(Q) if Q else np.zeros((0, 4), int)), (np.concatenate(T) if T else np.zeros((0, 3), int))


def build_mouth_parts(col=None):
    up_parts, low_parts = [], []
    for sx in (1, -1):
        # upper canine: hangs down, curls slightly back
        up_parts.append(_tooth((0.0080 * sx, -0.2060, 0.2228), (0.05 * sx, 0.12, -1.0), 0.0050, 0.00125, (0, 0.15, 0)))
        # lower canine (closed-jaw coords): points up, slightly out
        low_parts.append(_tooth((0.0068 * sx, -0.2020, 0.2150), (0.10 * sx, -0.05, 1.0), 0.0034, 0.0010, (0, 0.10, 0)))
        for k in range(3):   # incisors
            x = (0.0012 + 0.0016 * k) * sx
            up_parts.append(_tooth((x, -0.2112 + 0.0006 * k, 0.2214), (0, 0.05, -1), 0.0013, 0.00045, (0, 0, 0), 5, 3))
            low_parts.append(_tooth((x * 0.9, -0.2080 + 0.0006 * k, 0.2158), (0, -0.05, 1), 0.0011, 0.0004, (0, 0, 0), 5, 3))
    uv, uq, ut = _merge(up_parts)
    lv, lq, lt = _merge(low_parts)
    lv = _jaw_rest(lv)
    tv = np.concatenate([uv, lv])
    tq = np.concatenate([uq, lq + len(uv)])
    tt = np.concatenate([ut, lt + len(uv)])
    teeth = M.mesh_from_arrays("CatTeeth", head_to_world_np(tv), [tq, tt], col)
    g = teeth.vertex_groups.new(name="part_teeth")
    g.add(list(range(len(tv))), 1.0, "REPLACE")
    gl = teeth.vertex_groups.new(name="part_lowerjaw")
    gl.add(list(range(len(uv), len(tv))), 1.0, "REPLACE")
    # tongue: lofted, flattened, with a median groove (closed-jaw coords)
    ns, nc = 12, 12
    verts = []
    f0, f1 = 0.1745, 0.2060
    for k in range(ns):
        t = k / (ns - 1)
        f = f0 + (f1 - f0) * t
        hw = 0.0060 * (1 - 0.15 * t) * (math.sqrt(max(0.0, 1 - ((t - 0.0) / 1.0) ** 6)) if t > 0.8 else 1.0)
        th = 0.0019 * (1.0 - 0.45 * t)
        zc = 0.2128 - 0.0008 * t
        if k == ns - 1:
            hw *= 0.35
            th *= 0.6
        for i in range(nc):
            a = 2 * math.pi * i / nc
            x = hw * math.cos(a)
            z = th * math.sin(a)
            if z > 0:
                z -= 0.00035 * math.exp(-(x / (0.25 * hw + 1e-6)) ** 2)   # median groove
            verts.append((x, -f, zc + z))
    verts.append((0.0, -(f1 + 0.0012), 0.2120))
    verts = np.array(verts)
    q, tr = [], []
    for k in range(ns - 1):
        for i in range(nc):
            j = (i + 1) % nc
            q.append((k * nc + i, k * nc + j, (k + 1) * nc + j, (k + 1) * nc + i))
    last = (ns - 1) * nc
    for i in range(nc):
        tr.append((last + i, last + (i + 1) % nc, len(verts) - 1))
    tr += [(0, (i + 1) % nc, i) for i in range(1, nc - 1)]   # back cap fan (hidden)
    tongue = M.mesh_from_arrays("CatTongue", head_to_world_np(_jaw_rest(verts)), [np.array(q), np.array(tr)], col)
    g = tongue.vertex_groups.new(name="part_tongue")
    g.add(list(range(len(verts))), 1.0, "REPLACE")
    gl = tongue.vertex_groups.new(name="part_lowerjaw")
    gl.add(list(range(len(verts))), 1.0, "REPLACE")
    return [teeth, tongue]


# ---------------------------------------------------------------------------
# Whiskers + ear furnishings (alpha-clipped ribbons; one atlas)
# ---------------------------------------------------------------------------
def _ribbon_pair(pts, w0, w1, up, u0, u1):
    """Two crossed ribbons along polyline pts. Returns verts, quads, uvs (per vert)."""
    pts = np.asarray(pts)
    n = len(pts)
    tang = np.gradient(pts, axis=0)
    tang /= np.linalg.norm(tang, axis=1)[:, None]
    verts, uvs, quads = [], [], []
    for rib in range(2):
        base = len(verts)
        for i in range(n):
            t = i / (n - 1)
            w = w0 + (w1 - w0) * t
            s1 = np.cross(tang[i], up)
            s1 /= np.linalg.norm(s1) + 1e-12
            s = s1 if rib == 0 else np.cross(tang[i], s1)
            verts += [pts[i] - s * w * 0.5, pts[i] + s * w * 0.5]
            uvs += [(u0, t), (u1, t)]
        for i in range(n - 1):
            a = base + 2 * i
            quads.append((a, a + 1, a + 3, a + 2))
    return verts, quads, uvs


def _whisker_curve(root, d0, bend_dir, length, bend, n=9):
    d0 = _nrm(d0)
    bd = _nrm(bend_dir)
    pts = []
    for i in range(n):
        s = length * i / (n - 1)
        pts.append(np.asarray(root) + d0 * s + bd * (bend * s * s / length))
    return np.array(pts)


def build_whiskers(col=None, seed: int = 11):
    """CatWhiskers: mystacial (12/side), superciliary (3/side), genal (2/side), chin (3),
    carpal (3/foreleg) whiskers + ear furnishing tufts (6/ear). Head-space parts are
    mapped to world; carpal whiskers are authored in world space."""
    rng = np.random.default_rng(seed)
    V, Q, UV, groups = [], [], [], []

    def add(pts_world, w0, w1, up, region, grp):
        u0, u1 = (0.0, 0.5) if region == "whisker" else (0.5, 1.0)
        v, q, uv = _ribbon_pair(pts_world, w0, w1, up, u0, u1)
        off = len(V)
        V.extend(v)
        Q.extend([tuple(i + off for i in f) for f in q])
        UV.extend(uv)
        groups.extend([grp] * len(v))

    up_w = np.array(A.head_dir_to_world((0.0, 0.0, 1.0)))
    for sx, nm in ((1, "L"), (-1, "R")):
        pad = np.asarray(A.WHISKER_PAD_L) * np.array([sx, 1, 1])
        for r in range(4):
            for c in range(3):
                root = pad + np.array([0.0072 * sx, -(c - 1) * 0.0040 - 0.0006 * r, (1.5 - r) * 0.0024])
                root = S.project(head_to_world_np(root[None]), iters=4, max_step=0.003)[0]
                d_head = np.array([sx * 1.0, -0.30 + 0.06 * c, 0.28 - 0.20 * r]) + rng.normal(0, 0.06, 3)
                d = np.array(A.head_dir_to_world(tuple(_nrm(d_head))))
                length = (0.046 + 0.010 * (2 - c) + 0.007 * (1.5 - abs(r - 1.2)) + rng.normal(0, 0.003)) * A.HEAD_SCALE
                bend = np.array(A.head_dir_to_world((0.0, -0.7, -0.5)))
                pts = _whisker_curve(root - d * 0.0008, d, bend, length, 0.14 + rng.normal(0, 0.03))
                add(pts, 0.00090, 0.00034, up_w, "whisker", "wh_mystacial_" + nm)
        # superciliary (above the eye): fine, short, up-forward-outward, curving outwards
        for k in range(4):
            root_h = np.array([0.0110 * sx + 0.0022 * k * sx, -0.2050 + 0.0012 * k, 0.2592 - 0.0006 * k])
            root = S.project(head_to_world_np(root_h[None]), iters=4, max_step=0.003)[0]
            d = np.array(A.head_dir_to_world(tuple(_nrm((0.55 * sx + 0.08 * k * sx, -0.62 + 0.06 * k, 0.55)))))
            pts = _whisker_curve(root, d, np.array(A.head_dir_to_world((sx * 0.7, 0.3, -0.4))),
                                 (0.022 + 0.004 * k + rng.normal(0, 0.002)) * A.HEAD_SCALE, 0.16)
            add(pts, 0.00055, 0.00022, up_w, "whisker", "wh_head")
        # genal (cheek, behind the mouth corner)
        for k in range(2):
            root_h = np.array([0.0300 * sx, -0.1840 + 0.004 * k, 0.2330 - 0.004 * k])
            root = S.project(head_to_world_np(root_h[None]), iters=4, max_step=0.004)[0]
            d = np.array(A.head_dir_to_world(tuple(_nrm((0.9 * sx, 0.35, 0.05 - 0.15 * k)))))
            pts = _whisker_curve(root, d, np.array(A.head_dir_to_world((0, 0, -1))), 0.026 * A.HEAD_SCALE, 0.10)
            add(pts, 0.0008, 0.0003, up_w, "whisker", "wh_head")
        # carpal whiskers (back of the front wrist) -- world space, hand bone
        for k in range(3):
            root = np.array(A.CARPAL_PAD_L) * np.array([sx, 1, 1]) + np.array([0.0, 0.002 * k, 0.005 + 0.002 * k])
            root = S.project(root[None], iters=4, max_step=0.004)[0]
            d = _nrm((0.25 * sx * (k - 1), 0.6, 0.8))
            pts = _whisker_curve(root, d, (0, 1, 0), 0.016 + 0.002 * k, 0.15)
            add(pts, 0.0006, 0.00025, np.array([1.0, 0, 0]), "whisker", "wh_carpal_" + nm)
        # ear furnishings: soft tufts growing from the medial rim / lower cavity, lying along the
        # inner surface and spilling a little past the front edge.  The ribbon plane spans the
        # ear width (faces out of the cavity), so from the front it reads as a fan of fine hairs
        # instead of an edge-on white line.
        base, a, n, b = ear_frame(sx)
        for k in range(EAR_TUFTS):
            vv = 0.05 + 0.035 * k              # lower cavity only (furnishings are densest low down)
            uu = -0.55 + 0.22 * k + 0.08 * rng.normal()
            w = 0.5 * EAR_W * (1 - vv) ** 0.8
            sag = w * (0.58 - 0.32 * vv)
            root_h = base + a * (EAR_H * vv) + b * (w * uu) - n * (sag * (1 - uu * uu)) + n * 0.0008
            dir_h = _nrm(a * 0.85 + n * 0.30 + b * (-0.15 + 0.10 * uu))
            L = (0.009 + 0.004 * rng.random()) * A.HEAD_SCALE
            ts = np.linspace(0, 1, 5)
            pts_h = np.array([root_h + dir_h * L * t - n * (0.0035 * t * t) + b * (0.002 * sx * t * t * 0) for t in ts])
            pts = head_to_world_np(pts_h)
            up_n = np.array(A.head_dir_to_world(tuple(n)))
            v, q, uv = _ribbon_pair(pts, 0.0060, 0.0075, up_n, 0.5, 1.0)
            nv = len(v) // 2          # single ribbon (plane spans tangent x ear width)
            off = len(V)
            V.extend(v[:nv])
            Q.extend([tuple(i + off for i in f) for f in q[: len(q) // 2]])
            UV.extend(uv[:nv])
            groups.extend(["ear_tuft_" + nm] * nv)
    # chin whiskers (jaw)
    for k in range(3):
        xs = (k - 1) * 0.0035
        root_h = _jaw_rest(np.array([[xs, -0.2010, 0.2050]]))
        root = S.project(head_to_world_np(root_h), iters=4, max_step=0.003)[0]
        d = np.array(A.head_dir_to_world(tuple(_nrm((xs * 30, -0.6, -0.8)))))
        pts = _whisker_curve(root, d, np.array(A.head_dir_to_world((0, -1, 0))), 0.011 * A.HEAD_SCALE, 0.1, 5)
        add(pts, 0.0006, 0.0003, np.array([1.0, 0, 0]), "whisker", "wh_chin")
    V = np.array(V)
    ob = M.mesh_from_arrays("CatWhiskers", V, [np.array(Q)], col)
    me = ob.data
    uvl = me.uv_layers.new(name="UVMap")
    li = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", li)
    uvs = np.array(UV)[li]
    uvl.data.foreach_set("uv", uvs.astype(np.float32).ravel())
    for gname in sorted(set(groups)):
        g = ob.vertex_groups.new(name=gname)
        g.add([i for i, gg in enumerate(groups) if gg == gname], 1.0, "REPLACE")
    return ob


# ---------------------------------------------------------------------------
# Eye + whisker materials (export-friendly Principled setups)
# ---------------------------------------------------------------------------
def tex_dir():
    import common as C
    return os.path.dirname(C.asset_path("models/cat/textures/x"))


def eye_materials(eye_objs):
    import common as C
    import cat_tex as TX
    d = tex_dir()
    iris_path = os.path.join(d, "cat_eye_iris.png")
    TX.save_png(iris_path, TX.iris_texture(1024, palette="cam", limbus_deg=LIMBUS_DEG))
    for pal in ("green", "copper", "blue"):
        TX.save_png(os.path.join(d, f"cat_eye_iris_{pal}.png"), TX.iris_texture(512, palette=pal, limbus_deg=LIMBUS_DEG))
    m_iris = C.image_material("CatEye_Iris", albedo=iris_path)
    bsdf = next(n for n in m_iris.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.30
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    m_cor = C.principled("CatEye_Cornea", (0.0, 0.0, 0.0, 1.0), 0.02, **{"Alpha": 0.16, "IOR": 1.376,
                                                                           "Specular IOR Level": 1.0})
    m_cor.surface_render_method = "BLENDED"
    for o in eye_objs:
        o.data.materials.clear()
        o.data.materials.append(m_cor if "Cornea" in o.name else m_iris)
    return m_iris, m_cor


def whisker_material(ob):
    import common as C
    import cat_tex as TX
    path = os.path.join(tex_dir(), "cat_whiskers.png")
    TX.save_png(path, TX.whisker_atlas(), alpha=True)
    m = C.image_material("CatWhiskers", albedo=path, alpha_clip=True)
    bsdf = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.35
    m.use_backface_culling = False
    # glTF exporter detects MASK mode from a Math(ROUND)/(GREATER_THAN) node on alpha
    nt = m.node_tree
    img = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage")
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.4
    nt.links.new(img.outputs["Alpha"], gt.inputs[0])
    nt.links.new(gt.outputs[0], bsdf.inputs["Alpha"])
    ob.data.materials.clear()
    ob.data.materials.append(m)
    return m
