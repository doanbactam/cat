"""UV layout for CatBody.

Islands (seams are placed where fur hides them):
  head mask (neck ring behind the ears/jaw + cut under the chin), torso pelt (cut on the
  ventral midline throat->belly->under the tail), 4 leg tubes below elbow/knee (cut on the
  medial-posterior line), 4 paw caps (cut at the back of the pad), tail (cut on its
  underside), mouth interior, eye sockets, ears (inner/outer split at the rim), teeth, tongue.
Unwrap: angle-based, islands averaged to uniform texel density, then importance
scaling (face x1.35, paws x1.15, hidden interiors x0.3-0.6) and packing.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np

import cat_anatomy as A
import cat_mesh as M
import cat_parts as P
import cat_sdf as S
import common as C

UNWRAP_METHOD = "MINIMUM_STRETCH"
REGIONS = ["torso", "head", "mouth", "socket", "leg", "paw", "tail", "ear", "teeth", "tongue"]
SCALE = {"torso": 1.0, "head": 1.35, "mouth": 0.45, "socket": 0.25, "leg": 1.0, "paw": 1.15, "tail": 1.0,
         "ear": 1.05, "teeth": 0.6, "tongue": 0.8}


def _seg_dist(p, pts):
    d = np.full(len(p), np.inf)
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = np.asarray(a), np.asarray(b)
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
        q = a + t[:, None] * ab
        d = np.minimum(d, np.linalg.norm(p - q, axis=1))
    return d


def _vg_verts(ob, name):
    g = ob.vertex_groups.get(name)
    if g is None:
        return set()
    gi = g.index
    return {v.index for v in ob.data.vertices if any(e.group == gi and e.weight > 0.5 for e in v.groups)}


def classify_faces(ob) -> np.ndarray:
    """Region label (index into REGIONS) per polygon."""
    me = ob.data
    nf = len(me.polygons)
    cen = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get("center", cen)
    c = cen.reshape(-1, 3).astype(np.float64)
    nrm = np.empty(nf * 3, np.float32)
    me.polygons.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)
    lab = np.zeros(nf, np.int64)
    f = -c[:, 1]
    ax = np.abs(c[:, 0])
    # parts by vertex group
    vg = {k: _vg_verts(ob, k) for k in ("part_teeth", "part_tongue", "part_ear_L", "part_ear_R")}
    pv = [list(p.vertices) for p in me.polygons]
    # head ring plane (design space -> world)
    p0 = np.asarray(A.head_to_world((0.0, -0.149, 0.236)))
    n0 = np.asarray(A.head_dir_to_world((0.0, -0.991, 0.132)))
    head = (c - p0) @ n0 > 0
    lab[head] = REGIONS.index("head")
    ph = S.world_to_head(c)
    mouth = head & (S.mouth_carve(ph) < 0.00030)
    lab[mouth] = REGIONS.index("mouth")
    for sx in (1, -1):
        ec = np.asarray(P.head_to_world_np(np.asarray(A.EYE_L)[None] * np.array([sx, 1, 1])))[0]
        sock = np.linalg.norm(c - ec, axis=1) < (A.EYE_RADIUS + 0.0007) * A.HEAD_SCALE
        lab[sock] = REGIONS.index("socket")
    # legs / paws
    fl = [A.FOREARM_L, A.HAND_L, A.FINGER_L, A.FINGER_TIP_L]
    hl = [A.SHIN_L, A.FOOT_L, A.TOE_L, A.TOE_TIP_L]
    cm = c.copy()
    cm[:, 0] = np.abs(cm[:, 0])
    fore = (c[:, 2] < A.FOREARM_L[2] - 0.004) & (ax > 0.010) & (f > -0.02) & (_seg_dist(cm, fl) < 0.030)
    hind = (c[:, 2] < A.SHIN_L[2] - 0.016) & (ax > 0.010) & (f < -0.06) & (_seg_dist(cm, hl) < 0.034)
    lab[fore | hind] = REGIONS.index("leg")
    fpaw = fore & (c[:, 2] < 0.024)
    hpaw = hind & (c[:, 2] < 0.022)
    lab[fpaw | hpaw] = REGIONS.index("paw")
    # tail
    tp = np.asarray(A.tail_points())
    tdir = (tp[1] - tp[0]) / np.linalg.norm(tp[1] - tp[0])
    tail = ((c - (tp[0] + tdir * 0.014)) @ tdir > 0) & (c[:, 2] > 0.10) & ~head
    lab[tail] = REGIONS.index("tail")
    for i, verts in enumerate(pv):
        s = set(verts)
        if s <= vg["part_teeth"]:
            lab[i] = REGIONS.index("teeth")
        elif s <= vg["part_tongue"]:
            lab[i] = REGIONS.index("tongue")
        elif s <= (vg["part_ear_L"] | vg["part_ear_R"]):
            lab[i] = REGIONS.index("ear")
    return lab


def mark_seams(ob, lab: np.ndarray) -> None:
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    for e in bm.edges:
        e.seam = False
    # 1) region boundaries
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2 and lab[fs[0].index] != lab[fs[1].index]:
            e.seam = True
    R = {n: i for i, n in enumerate(REGIONS)}
    # 2) midline cuts: torso ventral, under the chin, under the tail
    for e in bm.edges:
        a, b = e.verts
        if abs(a.co.x) > 1e-6 or abs(b.co.x) > 1e-6:
            continue
        fs = [lab[f.index] for f in e.link_faces]
        nz = (a.normal.z + b.normal.z) * 0.5
        if all(x == R["torso"] for x in fs):
            e.seam = True          # ventral AND dorsal midline: torso = left/right flank islands
        elif all(x == R["head"] for x in fs) and nz < -0.25:
            e.seam = True
        elif all(x == R["tail"] for x in fs) and nz < 0.0:
            e.seam = True
        elif all(x == R["tongue"] for x in fs) and nz < 0.0:
            e.seam = True
    # 3) ear rim: split cavity side from back side
    for sx, nm in ((1, "L"), (-1, "R")):
        _, _, n, _ = P.ear_frame(sx)
        nw = np.asarray(A.head_dir_to_world(tuple(n)))
        for e in bm.edges:
            fs = e.link_faces
            if len(fs) != 2 or not all(lab[f.index] == R["ear"] for f in fs):
                continue
            if np.sign(e.verts[0].co.x) != sx:
                continue
            d0 = np.dot(np.array(fs[0].normal), nw)
            d1 = np.dot(np.array(fs[1].normal), nw)
            if (d0 > 0.25) != (d1 > 0.25):
                e.seam = True
    # 4) teeth: one cut per cone (edges along the cone's back side)
    for e in bm.edges:
        fs = e.link_faces
        if len(fs) == 2 and all(lab[f.index] == R["teeth"] for f in fs):
            d = e.verts[1].co - e.verts[0].co
            if abs(d.z) > 0.8 * d.length and min(v.co.y for v in e.verts) > max(f.calc_center_median().y for f in fs) - 1e-5:
                e.seam = True
    bm.to_mesh(me)
    bm.free()
    # 5) leg + paw cuts via Dijkstra inside each limb region
    v = M.get_verts(ob)
    edges = M.get_edges(ob)
    vlab = np.full(len(v), -1)
    for i, p in enumerate(me.polygons):
        for vi in p.vertices:
            if vlab[vi] in (-1, lab[i]):
                vlab[vi] = lab[i]
            else:
                vlab[vi] = 99   # boundary vertex between regions
    paths = []
    for sx in (1, -1):
        for front in (True, False):
            top_z = (A.FOREARM_L[2] - 0.004) if front else (A.SHIN_L[2] - 0.016)
            joint = np.asarray(A.FOREARM_L if front else A.SHIN_L) * np.array([sx, 1, 1])
            paw = np.asarray(A.FINGER_L if front else A.TOE_L) * np.array([sx, 1, 1])
            side = (-v[:, 1] > -0.02) if front else (-v[:, 1] < -0.06)
            near = (np.linalg.norm(v[:, [0, 1]] - joint[[0, 1]], axis=1) < 0.05) & side & (np.sign(v[:, 0]) == sx)
            # medial-posterior direction (towards body midline and backwards)
            mp = np.array([-sx * 0.8, 0.6, 0.0])
            cand_top = np.where(near & (vlab == 99) & (np.abs(v[:, 2] - top_z) < 0.012))[0]
            cand_bot = np.where((vlab == 99) & (np.abs(v[:, 2] - (0.024 if front else 0.022)) < 0.008)
                                & (np.linalg.norm(v[:, [0, 1]] - paw[[0, 1]], axis=1) < 0.03))[0]
            if len(cand_top) == 0 or len(cand_bot) == 0:
                print("  leg cut: no candidates", sx, front)
                continue
            top = cand_top[np.argmax(v[cand_top] @ mp)]
            bot = cand_bot[np.argmax(v[cand_bot] @ mp)]
            allowed = (vlab == REGIONS.index("leg")) | (vlab == 99)

            def cost(i, j, allowed=allowed, mp=mp, cen=joint):
                if not allowed[j]:
                    return 1e6
                return 1.0 + 3.0 * (1.0 - max(-1.0, min(1.0, float(np.dot(v[j, :2] - paw[:2], mp[:2]) /
                                                                   (np.linalg.norm(v[j, :2] - paw[:2]) + 1e-9)))))
            paths.append(M.dijkstra_path(v, edges, int(top), int(bot), cost))
            # paw cut: from the ring's back vertex to the main pad centre
            pad = paw + np.array([0.0, (0.004 if front else -0.004), -paw[2] + 0.003])
            pad_v = M.nearest_vertex(v, pad)
            allowed_p = (vlab == REGIONS.index("paw")) | (vlab == 99)
            paths.append(M.dijkstra_path(v, edges, int(bot), int(pad_v),
                                         lambda i, j, al=allowed_p: 1.0 if al[j] else 1e6))
    for pth in paths:
        M.mark_seam_path(ob, pth)


def unwrap(ob, lab: np.ndarray, margin: float = 0.0035) -> None:
    C.set_active(ob)
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method=UNWRAP_METHOD, fill_holes=True, correct_aspect=True, margin=0.001, iterations=20)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    # importance scaling per region (around each face-group centroid in UV)
    uvl = me.uv_layers.active
    uv = np.empty(len(me.loops) * 2, np.float32)
    uvl.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), np.int32)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    loop_lab = np.repeat(lab, lt)
    for name, s in SCALE.items():
        m = loop_lab == REGIONS.index(name)
        if m.any() and s != 1.0:
            cen = uv[m].mean(0)
            uv[m] = cen + (uv[m] - cen) * s
    uvl.data.foreach_set("uv", uv.ravel())
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="ANY", scale=True, margin_method="SCALED",
                            margin=margin, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def texel_report(ob, lab, size=4096):
    me = ob.data
    uvl = me.uv_layers.active
    v = M.get_verts(ob)
    uv = np.empty(len(me.loops) * 2, np.float32)
    uvl.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    out = {}
    for name in REGIONS:
        a3 = a2 = 0.0
        for i, p in enumerate(me.polygons):
            if lab[i] != REGIONS.index(name):
                continue
            idx = list(p.vertices)
            li = list(range(p.loop_start, p.loop_start + p.loop_total))
            for k in range(1, len(idx) - 1):
                a3 += 0.5 * np.linalg.norm(np.cross(v[idx[k]] - v[idx[0]], v[idx[k + 1]] - v[idx[0]]))
                e1 = uv[li[k]] - uv[li[0]]
                e2 = uv[li[k + 1]] - uv[li[0]]
                a2 += 0.5 * abs(e1[0] * e2[1] - e1[1] * e2[0])
        if a3 > 0:
            out[name] = math.sqrt(a2 / a3) * size   # px per metre
    used = 0.0
    for p in me.polygons:
        li = list(range(p.loop_start, p.loop_start + p.loop_total))
        for k in range(1, len(li) - 1):
            e1 = uv[li[k]] - uv[li[0]]
            e2 = uv[li[k + 1]] - uv[li[0]]
            used += 0.5 * abs(e1[0] * e2[1] - e1[1] * e2[0])
    print("UV texel density px/m @%d:" % size, {k: int(x) for k, x in out.items()}, "coverage %.2f" % used)
    return out, used
