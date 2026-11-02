"""Procedural, biomechanically-driven animation for CatRig.

A frame is described by a parameter dict (see DEFAULT); `Solver.solve(params)` turns it
into armature-space bone transforms:
  * torso: pelvis translation/rotation, spine pitch/yaw/roll distributed over
    spine_01..chest, neck lift; head orientation is a WORLD target (head stabilisation),
    the residual rotation is shared by neck / neck_02 / head
  * forelegs: scapula auto-rotates with the paw's fore-aft offset (feline scapular
    excursion), wrist = paw - hand_length * hand_dir(carpal flex), humerus+radius
    2-bone IK with the elbow bending backwards, toes flat when planted
  * hind legs: pantograph IK -- femur and metatarsus keep their rest angle relation,
    so thigh+metatarsus form one virtual bone and the leg is a 2-bone problem
    (knee forward, hock back). Or explicit metatarsus direction (sitting/crouching)
  * tail: per-segment pitch/yaw from lift, curve, tip curl and a travelling wave
  * ears (back/swivel/flatten), eyelids, eyes, jaw, tongue, whisker pads
Clips are written as keys on every frame (rotation quaternions; location for bones that
translate) into one Action per clip -> one glTF animation each.
"""
from __future__ import annotations

import copy
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import cat_anatomy as A

FPS = 30
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def qa(axis, deg) -> Quaternion:
    return Quaternion(Vector(axis).normalized(), math.radians(deg))


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def ease5(t):
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (t * 6 - 15) + 10)


def bump(t, a, b):
    """0 outside [a,b], smooth 0->1->0 inside."""
    if t <= a or t >= b:
        return 0.0
    u = (t - a) / (b - a)
    return math.sin(math.pi * u) ** 2


def Fv(x, f, z) -> Vector:
    return Vector((x, -f, z))


# ---------------------------------------------------------------------------
# parameter set
# ---------------------------------------------------------------------------
REST_PAW = {
    "FL": Fv(A.FINGER_L[0], -A.FINGER_L[1], A.FINGER_L[2]),
    "FR": Fv(-A.FINGER_L[0], -A.FINGER_L[1], A.FINGER_L[2]),
    "HL": Fv(A.TOE_L[0], -A.TOE_L[1], A.TOE_L[2]),
    "HR": Fv(-A.TOE_L[0], -A.TOE_L[1], A.TOE_L[2]),
}

DEFAULT = {
    "pel": (0.0, 0.0, 0.0),           # pelvis translation (Blender x, y(+back), z)
    "pel_rot": (0.0, 0.0, 0.0),       # pitch(nose-up +), yaw(left +), roll(left side down +)
    "spine": (0.0, 0.0, 0.0),         # total pitch(nose-up +), yaw(left +), roll over spine_01..chest
    "spine_w": (0.22, 0.28, 0.30, 0.20),
    "neck_lift": 0.0,                 # deg, + raises the neck (head keeps its world target)
    "head": (0.0, 0.0, 0.0),          # world-relative head pitch(+ up) / yaw(+ left) / roll(+ left ear down)
    "head_follow": 0.0,               # 0 = head target is world-relative, 1 = relative to chest
    "jaw": -3.0, "tongue": 0.0, "tongue_curl": 0.0,   # jaw 0 = lips touching; -3 tucks the lower lip behind the upper lip (closed mouth, no slit)
    "earL": (0.0, 0.0, 0.0), "earR": (0.0, 0.0, 0.0),   # back, swivel(out/back +), flatten
    "blink": (0.0, 0.0), "lower_lid": None, "eyes": (0.0, 0.0), "whisk": 0.0,
    "tail": {"lift": 0.0, "curve": 0.0, "yaw": 0.0, "amp": 0.0, "phase": 0.0, "wl": 1.4, "tip": 0.0,
             "side": 0.0, "pamp": 0.0},
    "FL": {"p": None, "a": 0.0, "toe": 0.0, "scap": 0.0},
    "FR": {"p": None, "a": 0.0, "toe": 0.0, "scap": 0.0},
    "HL": {"p": None, "a": 0.0, "toe": 0.0, "mode": "panto", "dir": None},
    "HR": {"p": None, "a": 0.0, "toe": 0.0, "mode": "panto", "dir": None},
}


def P(**kw) -> dict:
    p = copy.deepcopy(DEFAULT)
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(p.get(k), dict):
            p[k].update(v)
        else:
            p[k] = v
    return p


def mix(a: dict, b: dict, t: float) -> dict:
    """Interpolate two parameter dicts (numbers, tuples, Vectors, nested dicts)."""
    out = {}
    for k in a:
        va, vb = a[k], b.get(k, a[k])
        out[k] = _mix_val(va, vb, t)
    return out


def _mix_val(va, vb, t):
    if isinstance(va, dict):
        return {k: _mix_val(va[k], vb.get(k, va[k]), t) for k in va}
    if va is None or vb is None:
        return vb if t > 0.5 else va
    if isinstance(va, str):
        return vb if t > 0.5 else va
    if isinstance(va, Vector):
        return va.lerp(vb, t)
    if isinstance(va, tuple):
        return tuple(_mix_val(x, y, t) for x, y in zip(va, vb))
    if isinstance(va, (int, float)):
        return va + (vb - va) * t
    return vb if t > 0.5 else va


def keyed(keys: list, frame: float, easing=ease) -> dict:
    """keys: [(frame, params), ...] sorted. Smooth interpolation between neighbouring keys."""
    if frame <= keys[0][0]:
        return copy.deepcopy(keys[0][1])
    for (f0, p0), (f1, p1) in zip(keys[:-1], keys[1:]):
        if frame <= f1:
            return mix(p0, p1, easing((frame - f0) / max(1e-6, f1 - f0)))
    return copy.deepcopy(keys[-1][1])


# ---------------------------------------------------------------------------
# solver
# ---------------------------------------------------------------------------
def _rot_between(y0: Vector, n0: Vector, y1: Vector, n1: Vector) -> Quaternion:
    """Rotation taking frame (y0, n0) to (y1, n1) (n is a reference normal)."""
    def frame(y, n):
        y = y.normalized()
        n = (n - y * n.dot(y))
        if n.length < 1e-8:
            n = y.orthogonal()
        n.normalize()
        z = n.cross(y)
        return Matrix((n, y, z)).transposed()
    return (frame(y1, n1) @ frame(y0, n0).transposed()).to_quaternion()


def two_bone(root: Vector, target: Vector, l1: float, l2: float, bend: Vector, stats=None, tag="") -> Vector:
    d = target - root
    dist = d.length
    lo, hi = abs(l1 - l2) + 1e-5, (l1 + l2) * 0.9985
    if stats is not None:
        stats.append((dist / (l1 + l2), tag))
    dist_c = min(max(dist, lo), hi)
    dh = d.normalized()
    cos_a = (l1 * l1 + dist_c * dist_c - l2 * l2) / (2 * l1 * dist_c)
    cos_a = max(-1.0, min(1.0, cos_a))
    sin_a = math.sqrt(1 - cos_a * cos_a)
    p = bend - dh * bend.dot(dh)
    if p.length < 1e-8:
        p = dh.orthogonal()
    p.normalize()
    return root + (dh * cos_a + p * sin_a) * l1


def signed_angle(a: Vector, b: Vector, n: Vector) -> float:
    a = a - n * a.dot(n)
    b = b - n * b.dot(n)
    return math.atan2(a.cross(b).dot(n), a.dot(b))


class Solver:
    def __init__(self, rig_ob: bpy.types.Object):
        self.ob = rig_ob
        bones = rig_ob.data.bones
        self.names = []
        depth = {}
        for b in bones:
            d, q = 0, b
            while q.parent:
                d += 1
                q = q.parent
            depth[b.name] = d
        self.names = sorted([b.name for b in bones], key=lambda n: depth[n])
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.M = {b.name: b.matrix_local.copy() for b in bones}
        self.Rr = {n: self.M[n].to_quaternion() for n in self.names}
        self.head = {b.name: b.head_local.copy() for b in bones}
        self.tail = {b.name: b.tail_local.copy() for b in bones}
        self.len = {b.name: (b.tail_local - b.head_local).length for b in bones}
        self.rel = {}
        for n in self.names:
            p = self.parent[n]
            self.rel[n] = (self.M[p].inverted() @ self.M[n]) if p else self.M[n].copy()
        self.stats = []

    # -- generic FK ------------------------------------------------------------
    def fk(self, delta: dict, offs: dict, absolute: dict | None = None, heads: dict | None = None):
        Acc, H = {}, {}
        absolute = absolute or {}
        heads = heads or {}
        for n in self.names:
            p = self.parent[n]
            if n in heads:
                h = heads[n]
            elif p is None:
                h = self.head[n].copy()
            else:
                h = H[p] + Acc[p] @ (self.head[n] - self.head[p])
            if n in offs:
                h = h + offs[n]
            if n in absolute:
                a = absolute[n]
            else:
                a = (Acc[p] if p else Quaternion()) @ delta.get(n, Quaternion())
            Acc[n] = a
            H[n] = h
        return Acc, H

    def tip(self, Acc, H, n):
        return H[n] + Acc[n] @ (self.tail[n] - self.head[n])

    # -- full pose -------------------------------------------------------------
    def solve(self, prm: dict):
        D, O = {}, {}
        # pelvis
        pp, py, pr = prm["pel_rot"]
        D["pelvis"] = qa(Z, py) @ qa(X, -pp) @ qa(Y, -pr)
        O["pelvis"] = Vector(prm["pel"])
        sp, sy, sr = prm["spine"]
        for b, w in zip(("spine_01", "spine_02", "spine_03", "chest"), prm["spine_w"]):
            D[b] = qa(Z, sy * w) @ qa(X, -sp * w) @ qa(Y, -sr * w)
        D["neck"] = qa(X, -prm["neck_lift"])
        # first pass for torso
        Acc, H = self.fk(D, O)
        # head: world target, residual shared by neck / neck_02 / head
        hp, hy, hr = prm["head"]
        tgt = qa(Z, hy) @ qa(X, -hp) @ qa(Y, -hr)
        if prm.get("head_follow", 0.0) > 0:
            chest_rel = Acc["chest"]
            tgt = Quaternion().slerp(chest_rel, prm["head_follow"]) @ tgt
        q_rem = Acc["neck"].inverted() @ tgt
        q_half = Quaternion().slerp(q_rem, 0.5)
        D["neck_02"] = q_half
        D["head"] = q_half
        D["jaw"] = qa(X, prm["jaw"] - A.JAW_REST_OPEN_DEG)
        D["tongue_01"] = qa(X, prm["tongue_curl"] * 0.5)
        D["tongue_02"] = qa(X, prm["tongue_curl"])
        O["tongue_01"] = Vector((0, -0.010 * prm["tongue"], -0.002 * prm["tongue"]))
        bl, br = prm["blink"]
        low = prm["lower_lid"]
        for s, b in (("L", bl), ("R", br)):
            lo = (b * 0.85) if low is None else low
            ax = self._lid_axis(s)
            D[f"eyelid_{s}"] = Quaternion(ax, math.radians(A.UPPER_LID_CLOSE_DEG * b))
            D[f"eyelid_low_{s}"] = Quaternion(ax, -math.radians(A.LOWER_LID_CLOSE_DEG * lo))
            ey, ep = prm["eyes"]
            D[f"eye_{s}"] = qa(Z, ey) @ qa(X, -ep)
            back, swiv, flat = prm["ear" + s]
            sgn = 1.0 if s == "L" else -1.0
            D[f"ear_{s}"] = qa(Y, sgn * flat) @ qa(X, -back) @ qa(Z, sgn * swiv)
            D[f"ear_tip_{s}"] = qa(X, -back * 0.25)
            D[f"whisker_{s}"] = qa(Z, -sgn * prm["whisk"])
        # tail
        t = prm["tail"]
        n = A.TAIL_SEGMENTS
        for i in range(n):
            u = i / (n - 1)
            pitch = (t["lift"] if i == 0 else 0.0) + t["curve"] / n + t["tip"] * max(0.0, (u - 0.55) / 0.45) ** 1.5 * 0.5
            pitch += t["pamp"] * math.sin(2 * math.pi * (t["phase"] - u / t["wl"]) + 1.3)
            yaw = (t["yaw"] / n) + t["amp"] * (0.35 + 0.65 * u) * math.sin(2 * math.pi * (t["phase"] - u / t["wl"]))
            yaw += t["side"] / n * (1.0 + 1.5 * u)
            D[f"tail_{i + 1:02d}"] = qa(Z, -yaw) @ qa(X, pitch)
        Acc, H = self.fk(D, O)
        absolute, heads = {}, {}
        for leg in ("FL", "FR"):
            self._foreleg(leg, prm, prm[leg], Acc, H, D, absolute, heads)
        for leg in ("HL", "HR"):
            self._hindleg(leg, prm[leg], Acc, H, absolute, heads)
        Acc, H = self.fk(D, O, absolute, heads)
        return Acc, H

    def _lid_axis(self, s):
        h = self.head[f"eyelid_{s}"]
        tl = self.tail[f"eyelid_{s}"]
        g = (tl - h).normalized()
        return Z.cross(g).normalized()

    # -- limbs -----------------------------------------------------------------
    def _lateral(self, Acc, bone, s):
        lat = Acc[bone] @ X
        lat.z *= 0.3
        return lat.normalized() * (1 if s == "L" else -1)

    def _foreleg(self, leg, prm, L, Acc, H, D, absolute, heads):
        s = leg[1]
        names = [f"scapula_{s}", f"upperarm_{s}", f"forearm_{s}", f"hand_{s}", f"finger_{s}"]
        target = L["p"] if L["p"] is not None else REST_PAW[leg].copy()
        # scapula: swings with the paw's fore-aft offset relative to the chest
        chest_f = -(H["chest"].y) + 0.06
        rest_f = -REST_PAW[leg].y
        off = (-target.y - rest_f) - (chest_f - (-self.head["chest"].y + 0.06))
        lift = max(0.0, target.z - 0.03)
        scap = max(-32.0, min(32.0, -off * 210.0 - lift * 90.0)) + L.get("scap", 0.0)
        D[names[0]] = qa(X, scap)
        Acc_s = Acc["chest"] @ D[names[0]]
        h_s = H["chest"] + Acc["chest"] @ (self.head[names[0]] - self.head["chest"])
        S = h_s + Acc_s @ (self.tail[names[0]] - self.head[names[0]])
        lat = self._lateral(Acc, "chest", s)
        # hand direction: rest metacarpus rotated by carpal flex about the lateral axis
        hand_rest = (self.tail[names[3]] - self.head[names[3]]).normalized()
        yaw_q = qa(Z, prm["spine"][1] * 0.6 + prm["pel_rot"][1])
        latx = (yaw_q @ X).normalized()
        hand_dir = Quaternion(latx, math.radians(L["a"])) @ (yaw_q @ hand_rest)
        W = target - hand_dir * self.len[names[3]]
        # scapular glide: the shoulder blade slides on the thorax towards an out-of-reach wrist
        reach = (self.len[names[1]] + self.len[names[2]]) * 0.975
        dvec = W - S
        if dvec.length > reach:
            g = dvec.normalized() * min(dvec.length - reach, 0.034)
            h_s = h_s + g
            S = S + g
        back = (yaw_q @ Y)
        E = two_bone(S, W, self.len[names[1]], self.len[names[2]], back + lat * 0.15, self.stats, leg)
        fin_rest = (self.tail[names[4]] - self.head[names[4]]).normalized()
        fin_dir = Quaternion(latx, math.radians(L["toe"])) @ (yaw_q @ fin_rest)
        pts = [None, S, E, W, target, target + fin_dir * self.len[names[4]]]
        absolute[names[0]] = Acc_s
        heads[names[0]] = h_s
        for i, n in enumerate(names[1:], start=1):
            y0 = self.tail[n] - self.head[n]
            y1 = pts[i + 1] - pts[i]
            absolute[n] = _rot_between(y0, X * (1 if s == "L" else -1), y1, lat)
            heads[n] = pts[i]

    def _hindleg(self, leg, L, Acc, H, absolute, heads):
        s = leg[1]
        th, sh, ft, to = f"thigh_{s}", f"shin_{s}", f"foot_{s}", f"toe_{s}"
        target = L["p"] if L["p"] is not None else REST_PAW[leg].copy()
        Hp = H["pelvis"] + Acc["pelvis"] @ (self.head[th] - self.head["pelvis"])
        lat = self._lateral(Acc, "pelvis", s)
        lf, lt, lm = self.len[th], self.len[sh], self.len[ft]
        F0 = self.tail[th] - self.head[th]
        M0 = self.tail[ft] - self.head[ft]
        fwd = (Acc["pelvis"] @ (-Y))
        fwd.z = 0
        fwd.normalize()
        n = lat - (target - Hp).normalized() * lat.dot((target - Hp).normalized())
        n.normalize()
        if L.get("mode", "panto") == "dir" and L.get("dir") is not None:
            Md = Vector(L["dir"]).normalized()
            Ah = target - Md * lm
            K = two_bone(Hp, Ah, lf, lt, fwd, self.stats, leg)
        else:
            n0 = Vector((1, 0, 0))
            delta = signed_angle(F0, M0, n0) + math.radians(L.get("a", 0.0))
            u0 = F0.normalized()
            V0 = u0 * lf + (Quaternion(n0, delta) @ u0) * lm
            beta = signed_angle(u0, V0, n0)
            J = two_bone(Hp, target, V0.length, lt, fwd, self.stats, leg)
            Vh = (J - Hp).normalized()
            nn = n if s == "L" else n
            nn = Vector((1, 0, 0)) if nn.length < 1e-6 else nn
            # keep rotation sense consistent with the rest plane normal (+X)
            if nn.dot(Vector((1, 0, 0))) < 0:
                nn = -nn
            u = Quaternion(nn, -beta) @ Vh
            K = Hp + u * lf
            Md = Quaternion(nn, delta) @ u
            Ah = target - Md * lm
        to_rest = (self.tail[to] - self.head[to]).normalized()
        yaw_q = Quaternion(Vector((0, 0, 1)), math.atan2(-fwd.x, -fwd.y) * -1.0)
        latx = (yaw_q @ X).normalized()
        toe_dir = Quaternion(latx, math.radians(L.get("toe", 0.0))) @ (yaw_q @ to_rest)
        pts = [Hp, K, Ah, target, target + toe_dir * self.len[to]]
        for i, nme in enumerate((th, sh, ft, to)):
            y0 = self.tail[nme] - self.head[nme]
            y1 = pts[i + 1] - pts[i]
            absolute[nme] = _rot_between(y0, X * (1 if s == "L" else -1), y1, lat)
            heads[nme] = pts[i]

    # -- matrices -> local bases -------------------------------------------
    def bases(self, Acc, H):
        G = {n: Matrix.Translation(H[n]) @ (Acc[n] @ self.Rr[n]).to_matrix().to_4x4() for n in self.names}
        out = {}
        for n in self.names:
            p = self.parent[n]
            if p is None:
                L = self.M[n].inverted() @ G[n]
            else:
                L = self.rel[n].inverted() @ G[p].inverted() @ G[n]
            out[n] = L
        return out


# ---------------------------------------------------------------------------
# writing actions
# ---------------------------------------------------------------------------
LOC_BONES = {"pelvis", "scapula_L", "scapula_R", "tongue_01"}


# Clips are AUTHORED in 30 fps frames (clip functions take 30 fps frame numbers) but KEYED at
# KEY_RATE x 30 = 120 Hz: the exporter writes one glTF key per scene frame and Godot interpolates
# bone rotations linearly (and re-bakes at the import option animation/fps, set to KEY_FPS by
# configure_import.py).  At 30 Hz the gallop's planted paws sagged ~22 mm through the floor and
# slid between keys, at 60 Hz still ~7 mm; at 120 Hz the chord error is ~1-2 mm.  The scene fps
# is set to KEY_FPS; clip durations in seconds are unchanged.
KEY_RATE = 4
KEY_FPS = FPS * KEY_RATE


def write_action(solver: Solver, name: str, nframes: int, fn, loop: bool) -> bpy.types.Action:
    """fn(frame:float (30 fps units), t:float in [0,1)) -> params. Keys 0..nframes*KEY_RATE
    at KEY_FPS (last == first for loops)."""
    ob = solver.ob
    bpy.context.scene.render.fps = KEY_FPS
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ob.animation_data_create()
    ob.animation_data.action = act
    prev_q = {}
    solver.stats = []
    nk = nframes * KEY_RATE
    for fr in range(nk + 1):
        k_eval = (fr % nk) if loop else fr
        f_eval = k_eval / KEY_RATE
        prm = fn(f_eval, f_eval / nframes)
        Acc, H = solver.solve(prm)
        L = solver.bases(Acc, H)
        for n, m in L.items():
            pb = ob.pose.bones[n]
            loc, rot, _ = m.decompose()
            if n in prev_q and prev_q[n].dot(rot) < 0:
                rot.negate()
            prev_q[n] = rot
            pb.rotation_quaternion = rot
            pb.keyframe_insert("rotation_quaternion", frame=fr)
            if n in LOC_BONES:
                pb.location = loc
                pb.keyframe_insert("location", frame=fr)
    act.use_frame_range = True
    act.frame_start = 0
    act.frame_end = nk
    act["loop"] = bool(loop)
    ob.animation_data.action = None
    per = {}
    for r, tag in solver.stats:
        per[tag] = max(per.get(tag, 0.0), r)
    rs = " ".join(f"{k}:{v:.2f}" for k, v in sorted(per.items()))
    print(f"  action {name:14s} frames {nframes:3d} loop={loop!s:5s} reach {rs}")
    return act
