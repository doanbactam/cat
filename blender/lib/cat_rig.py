"""CatRig armature + skin weights.

Contract bones: root pelvis spine_01..03 chest neck head jaw ear_L/R eyelid_L/R tail_01..06
upperarm/forearm/hand_L/R thigh/shin/foot/toe_L/R.
Extras: neck_02, tail_07, tail_08, scapula_L/R (shoulder blades slide/rotate on the thorax),
finger_L/R (front toes), ear_tip_L/R, eyelid_low_L/R, eye_L/R (eyeball aim), tongue_01/02,
whisker_L/R (whisker-pad protraction), mouth_socket (held items), fpp_eye (first-person camera).
All bones deform (sockets carry no weights) so glTF exports every one of them.
"""
from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Vector

import cat_anatomy as A
import cat_mesh as M
import cat_parts as P
import cat_sdf as S
import common as C

RIG_NAME = "CatRig"


def hw(p):
    return tuple(A.head_to_world(p))


def jaw_rest_w(p):
    return tuple(P.head_to_world_np(P._jaw_rest(np.asarray(p, np.float64)[None]))[0])


def mir(p):
    return (-p[0], p[1], p[2])


def bone_defs():
    """(name, head, tail, parent, connected, roll_up_vector)."""
    up, fwd, back = (0, 0, 1), (0, -1, 0), (0, 1, 0)
    head_p = hw(A.HEAD)
    d = [
        ("root", (0, 0, 0), (0, -0.06, 0), None, False, up),
        ("pelvis", A.PELVIS, A.SPINE_01, "root", False, up),
        ("spine_01", A.SPINE_01, A.SPINE_02, "pelvis", True, up),
        ("spine_02", A.SPINE_02, A.SPINE_03, "spine_01", True, up),
        ("spine_03", A.SPINE_03, A.CHEST, "spine_02", True, up),
        ("chest", A.CHEST, A.NECK, "spine_03", True, up),
        ("neck", A.NECK, A.NECK_02, "chest", True, up),
        ("neck_02", A.NECK_02, head_p, "neck", True, up),
        ("head", head_p, hw(A.HEAD_TAIL), "neck_02", True, up),
        ("jaw", hw(A.JAW), jaw_rest_w(A.JAW_TAIL), "head", False, up),
        ("tongue_01", jaw_rest_w(A.TONGUE_01), jaw_rest_w(A.TONGUE_02), "jaw", False, up),
        ("tongue_02", jaw_rest_w(A.TONGUE_02), jaw_rest_w(A.TONGUE_TAIL), "tongue_01", True, up),
        ("mouth_socket", jaw_rest_w(A.MOUTH_SOCKET), jaw_rest_w((0, A.MOUTH_SOCKET[1] - 0.01, A.MOUTH_SOCKET[2])), "jaw", False, up),
        ("fpp_eye", hw(A.FPP_EYE), hw((0, A.FPP_EYE[1] - 0.012, A.FPP_EYE[2])), "head", False, up),
    ]
    for sx, s in ((1, "L"), (-1, "R")):
        m = (lambda p: p) if sx > 0 else mir
        # ears
        base, a, n, b = P.ear_frame(sx)
        e0 = hw(tuple(base + a * 0.002))
        e1 = hw(tuple(base + a * (P.EAR_H * 0.55)))
        e2 = hw(tuple(base + a * (P.EAR_H * 1.0) - n * 0.004))
        nw = A.head_dir_to_world(tuple(n))
        d += [(f"ear_{s}", e0, e1, "head", False, nw), (f"ear_tip_{s}", e1, e2, f"ear_{s}", True, nw)]
        # eyes / lids (pivot at the eyeball centre, pointing along the gaze)
        c, g, _, _ = S.eye_frame(sx)
        cw = hw(tuple(c))
        gw = np.asarray(A.head_dir_to_world(tuple(g)))
        tip = tuple(np.asarray(cw) + gw * A.EYE_RADIUS * A.HEAD_SCALE)
        tip_lid = tuple(np.asarray(cw) + gw * A.EYE_RADIUS * A.HEAD_SCALE * 0.9)
        d += [(f"eye_{s}", cw, tip, "head", False, up),
              (f"eyelid_{s}", cw, tip_lid, "head", False, up),
              (f"eyelid_low_{s}", cw, tip_lid, "head", False, up)]
        pad = hw(A.WHISKER_PAD_L) if sx > 0 else mir(hw(A.WHISKER_PAD_L))
        d += [(f"whisker_{s}", pad, (pad[0] + sx * 0.010, pad[1] - 0.004, pad[2]), "head", False, up)]
        # foreleg
        d += [(f"scapula_{s}", m(A.SCAPULA_L), m(A.UPPERARM_L), "chest", False, fwd),
              (f"upperarm_{s}", m(A.UPPERARM_L), m(A.FOREARM_L), f"scapula_{s}", True, fwd),
              (f"forearm_{s}", m(A.FOREARM_L), m(A.HAND_L), f"upperarm_{s}", True, fwd),
              (f"hand_{s}", m(A.HAND_L), m(A.FINGER_L), f"forearm_{s}", True, fwd),
              (f"finger_{s}", m(A.FINGER_L), m(A.FINGER_TIP_L), f"hand_{s}", True, up),
              (f"thigh_{s}", m(A.THIGH_L), m(A.SHIN_L), "pelvis", False, fwd),
              (f"shin_{s}", m(A.SHIN_L), m(A.FOOT_L), f"thigh_{s}", True, fwd),
              (f"foot_{s}", m(A.FOOT_L), m(A.TOE_L), f"shin_{s}", True, fwd),
              (f"toe_{s}", m(A.TOE_L), m(A.TOE_TIP_L), f"foot_{s}", True, up)]
    tp = A.tail_points()
    for i in range(A.TAIL_SEGMENTS):
        d.append((f"tail_{i + 1:02d}", tp[i], tp[i + 1], "pelvis" if i == 0 else f"tail_{i:02d}", i > 0, up))
    return d


def build_rig() -> bpy.types.Object:
    arm = bpy.data.armatures.new(RIG_NAME)
    ob = bpy.data.objects.new(RIG_NAME, arm)
    bpy.context.scene.collection.objects.link(ob)
    arm.display_type = "STICK"
    C.set_active(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for name, h, t, parent, conn, upv in bone_defs():
        b = eb.new(name)
        b.head = Vector(h)
        b.tail = Vector(t)
        b.align_roll(Vector(upv))
        b.use_deform = True
        if parent:
            b.parent = eb[parent]
            b.use_connect = conn
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


# ---------------------------------------------------------------------------
# Skin weights
# ---------------------------------------------------------------------------
SKIN_HEAT_BONES = [
    "pelvis", "spine_01", "spine_02", "spine_03", "chest", "neck", "neck_02", "head",
    "scapula_L", "upperarm_L", "forearm_L", "hand_L", "finger_L",
    "scapula_R", "upperarm_R", "forearm_R", "hand_R", "finger_R",
    "thigh_L", "shin_L", "foot_L", "toe_L", "thigh_R", "shin_R", "foot_R", "toe_R",
] + [f"tail_{i:02d}" for i in range(1, 9)]


def _set_groups(ob, W: dict, n: int):
    for name, w in W.items():
        g = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
        idx = np.nonzero(w > 1e-4)[0]
        g.remove(list(range(n)))
        for i in idx:
            g.add([int(i)], float(w[i]), "REPLACE")


def _get_weights(ob, names, n):
    W = {nm: np.zeros(n) for nm in names}
    gi = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for e in v.groups:
            nm = gi.get(e.group)
            if nm in W:
                W[nm][v.index] = e.weight
    return W


def weight_body(body: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Bone-heat for the skin (big bones only), then procedural face/ear/mouth weights,
    smoothing, normalisation and a 4-influence limit."""
    n = len(body.data.vertices)
    v = M.get_verts(body)
    parts = {k: np.zeros(n, bool) for k in ("part_teeth", "part_tongue", "part_ear_L", "part_ear_R", "part_lowerjaw")}
    for k in parts:
        g = body.vertex_groups.get(k)
        if g:
            for vv in body.data.vertices:
                for e in vv.groups:
                    if e.group == g.index and e.weight > 0.5:
                        parts[k][vv.index] = True
    skin = ~(parts["part_teeth"] | parts["part_tongue"] | parts["part_ear_L"] | parts["part_ear_R"])
    # 1) bone heat on a temporary skin-only copy scaled x10 (heat solver is scale sensitive and
    #    fails with the separate ear/teeth/tongue shells), only the large skin bones deforming
    names = [b.name for b in rig.data.bones]
    W = heat_weights(body, rig, skin, SKIN_HEAT_BONES)
    tot = sum(W.values())
    print("  heat: verts without weights:", int(((tot < 1e-3) & skin).sum()))
    # vertices the heat solver missed: nearest-bone fallback
    miss = (tot < 1e-3) & skin
    if miss.any():
        segs = []
        for nm in SKIN_HEAT_BONES:
            b = rig.data.bones[nm]
            segs.append((nm, np.array(b.head_local), np.array(b.tail_local)))
        best = np.full(n, np.inf)
        bestn = np.empty(n, object)
        for nm, a, b in segs:
            ab = b - a
            t = np.clip(((v - a) @ ab) / (ab @ ab), 0, 1)
            dd = np.linalg.norm(v - (a + t[:, None] * ab), axis=1)
            upd = dd < best
            best[upd] = dd[upd]
            bestn[upd] = nm
        for i in np.nonzero(miss)[0]:
            W[bestn[i]][i] = 1.0
    for k in W:
        W[k][~skin] = 0.0
    # 2) head-space procedural weights
    ph = S.world_to_head(v)
    phm = ph.copy()
    phm[:, 0] = np.abs(phm[:, 0])
    f = -ph[:, 1]
    headw = W["head"]
    # jaw: below the lip line, in front of the hinge, fading at the mouth corners / cheeks
    pj = S.jaw_space(ph)
    lip = 0.2192
    below = smooth01((lip - pj[:, 2]) / 0.0022 + 0.5)
    front = smooth01((f - 0.170) / 0.018)
    lateral = 1.0 - smooth01((np.abs(ph[:, 0]) - 0.017) / 0.010)
    under = smooth01((0.214 - ph[:, 2]) / 0.008) * smooth01((f - 0.158) / 0.02) * (1.0 - smooth01((np.abs(ph[:, 0]) - 0.022) / 0.012))
    jaw = np.clip(np.maximum(below * front * lateral, under * 0.85), 0, 1)
    region_head = headw + W["neck_02"] * 0.0
    jaw *= smooth01((f - 0.150) / 0.01)
    jaw = np.where(skin, jaw, 0.0)
    take = np.minimum(jaw, headw + W["neck_02"] + W["neck"])
    W["jaw"] = take
    W["head"] = np.maximum(headw - take, 0)
    # eyelids: upper lid skin around the aperture (eye frame v > 0), lower lid (v < 0)
    for sx, s in ((1, "L"), (-1, "R")):
        c, g, u, vv = S.eye_frame(1)
        q = phm - c
        side = np.sign(ph[:, 0]) == sx
        r = np.linalg.norm(q, axis=1)
        qv = q @ vv
        qg = q @ g
        shell = (r < (A.EYE_RADIUS + 0.0055)) & (qg > -0.002) & side & skin
        near = 1.0 - smooth01((r - (A.EYE_RADIUS + 0.0026)) / 0.0030)
        up_w = shell * near * smooth01((qv - 0.0010) / 0.0022)
        lo_w = shell * near * smooth01((-qv - 0.0012) / 0.0022) * 0.9
        for nm, w in ((f"eyelid_{s}", up_w), (f"eyelid_low_{s}", lo_w)):
            w = np.minimum(w, W["head"])
            W[nm] = w
            W["head"] = W["head"] - w
        # whisker pad protraction (small influence on the pad)
        pc = np.asarray(A.WHISKER_PAD_L)
        dp = np.linalg.norm(phm - pc, axis=1)
        ww = np.where(side & skin, 0.6 * (1.0 - smooth01((dp - 0.004) / 0.008)), 0.0)
        ww = np.minimum(ww, W["head"])
        W[f"whisker_{s}"] = ww
        W["head"] -= ww
    # 3) ears: ear_X near the base -> ear_tip_X above 55 %
    for sx, s in ((1, "L"), (-1, "R")):
        msk = parts[f"part_ear_{s}"]
        base, a, n_, b = P.ear_frame(sx)
        h = np.clip(((ph - base) @ a) / P.EAR_H, -1, 2)
        tipw = smooth01((h - 0.40) / 0.30)
        basew = 1.0 - smooth01((h + 0.05) / 0.20)
        W[f"ear_tip_{s}"] = np.where(msk, tipw * (1 - basew), W[f"ear_tip_{s}"])
        W[f"ear_{s}"] = np.where(msk, (1 - tipw) * (1 - basew), W[f"ear_{s}"])
        W["head"] = np.where(msk, basew, W["head"])
    # 4) teeth / tongue
    low = parts["part_lowerjaw"]
    W["jaw"] = np.where(parts["part_teeth"] & low, 1.0, W["jaw"])
    W["head"] = np.where(parts["part_teeth"] & ~low, 1.0, W["head"])
    tf = (f - 0.176) / (0.2065 - 0.176)
    t2 = smooth01((tf - 0.35) / 0.4)
    tg = parts["part_tongue"]
    W["tongue_02"] = np.where(tg, t2, W["tongue_02"])
    W["tongue_01"] = np.where(tg, (1 - t2) * smooth01((tf + 0.2) / 0.3), W["tongue_01"])
    W["jaw"] = np.where(tg, 1.0 - W["tongue_01"] - W["tongue_02"], W["jaw"])
    # 5) smooth skin weights a little on the mesh graph, then normalise + limit to 4
    edges = M.get_edges(body)
    keys = [k for k in W if W[k].any()]
    mat = np.stack([W[k] for k in keys], 1)
    fixed = ~skin
    mat = M.laplacian_smooth(mat, edges, n, iters=3, lam=0.35, fixed=fixed)
    mat = limit_normalise(mat, 4)
    W = {k: mat[:, i] for i, k in enumerate(keys)}
    for g in list(body.vertex_groups):
        if g.name in names:
            body.vertex_groups.remove(g)
    _set_groups(body, W, n)


def heat_weights(body, rig, skin_mask, bone_names, scale=10.0):
    import bmesh
    n = len(body.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    drop = [bm.verts[i] for i in np.nonzero(~skin_mask)[0]]
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    keep_idx = np.nonzero(skin_mask)[0]
    me = bpy.data.meshes.new("_heat_skin")
    bm.to_mesh(me)
    bm.free()
    tmp = bpy.data.objects.new("_heat_skin", me)
    bpy.context.scene.collection.objects.link(tmp)
    tmp.vertex_groups.clear()
    arm = rig.data.copy()
    trig = bpy.data.objects.new("_heat_rig", arm)
    bpy.context.scene.collection.objects.link(trig)
    for o in (tmp, trig):
        o.scale = (scale, scale, scale)
        C.apply_transforms(o, loc=False, rot=False, scale=True)
    for b in trig.data.bones:
        b.use_deform = b.name in bone_names
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    tmp.select_set(True)
    trig.select_set(True)
    bpy.context.view_layer.objects.active = trig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    W = {nm: np.zeros(n) for nm in bone_names}
    gi = {g.index: g.name for g in tmp.vertex_groups}
    for v in tmp.data.vertices:
        for e in v.groups:
            nm = gi.get(e.group)
            if nm in W:
                W[nm][keep_idx[v.index]] = e.weight
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.objects.remove(trig, do_unlink=True)
    bpy.data.meshes.remove(me)
    bpy.data.armatures.remove(arm)
    for nm in [b.name for b in rig.data.bones]:
        W.setdefault(nm, np.zeros(n))
    body.parent = rig
    if not any(m.type == "ARMATURE" for m in body.modifiers):
        mod = body.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
    return W


def smooth01(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def limit_normalise(mat: np.ndarray, k: int = 4) -> np.ndarray:
    mat = np.maximum(mat, 0.0)
    if mat.shape[1] > k:
        idx = np.argsort(-mat, axis=1)[:, k:]
        np.put_along_axis(mat, idx, 0.0, axis=1)
    mat[mat < 0.01] = 0.0
    s = mat.sum(1, keepdims=True)
    s[s == 0] = 1.0
    return mat / s


def attach_rigid(ob: bpy.types.Object, rig: bpy.types.Object, groups_to_bones: dict[str, list[tuple[str, float]]]):
    """Skin helper meshes whose vertex groups name a part: map part group -> bones."""
    n = len(ob.data.vertices)
    W: dict[str, np.ndarray] = {}
    gi = {g.index: g.name for g in ob.vertex_groups}
    member = {name: np.zeros(n, bool) for name in gi.values()}
    for v in ob.data.vertices:
        for e in v.groups:
            member[gi[e.group]][v.index] = True
    for gname, bones in groups_to_bones.items():
        if gname not in member:
            continue
        for bname, w in bones:
            W.setdefault(bname, np.zeros(n))
            W[bname] = np.where(member[gname], w, W[bname])
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    _set_groups(ob, W, n)
    ob.parent = rig
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
