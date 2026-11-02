"""Quadruped NPCs (owner: creatures): shared rig layout, SDF helpers, procedural gaits.
Used for Vện the street dog and the mouse (the gecko has its own sprawling clips).

Bone layout (all quadrupeds): root, pelvis, spine_01, spine_02, chest, neck, head, jaw,
ear_L/R, tail_01..tail_N, scapula_L/R, upperarm_L/R, forearm_L/R, hand_L/R,
thigh_L/R, shin_L/R, foot_L/R, toe_L/R.  Front = -Y (Blender) = +Z (Godot).
"""
from __future__ import annotations

import math

import numpy as np
from mathutils import Quaternion, Vector

import npc_anim as A
import npc_sdf as S
import npc_tex as X
from npc_anim import Pose, qx, qy, qz, wave, noise1, smoothstep
from npc_tex import col, mix, sstep

LEGS = ("FL", "FR", "HL", "HR")


def mirror(v):
    v = np.array(v, np.float64)
    v[0] = -v[0]
    return v


def complete_sides(lm: dict) -> dict:
    for k in list(lm):
        if k.endswith("_L"):
            lm[k[:-2] + "_R"] = mirror(lm[k]) if not isinstance(lm[k], list) else [mirror(p) for p in lm[k]]
    return lm


def quad_bones(lm: dict, n_tail: int):
    F = (0, -1, 0)
    U = (0, 0, 1)
    t = lambda v: tuple(float(a) for a in v)  # noqa: E731
    bl = [
        ("root", (0, 0, 0), (0, 0.05 * lm["scale"], 0), None, U),
        ("pelvis", t(lm["pelvis"]), t(lm["spine1"]), "root", U),
        ("spine_01", t(lm["spine1"]), t(lm["spine2"]), "pelvis", U),
        ("spine_02", t(lm["spine2"]), t(lm["chest"]), "spine_01", U),
        ("chest", t(lm["chest"]), t(lm["neck_base"]), "spine_02", U),
        ("neck", t(lm["neck_base"]), t(lm["head_base"]), "chest", U),
        ("head", t(lm["head_base"]), t(lm["nose"]), "neck", U),
        ("jaw", t(lm["jaw_pivot"]), t(lm["jaw_tip"]), "head", U),
    ]
    tail = lm["tail"]
    prev = "pelvis"
    for i in range(n_tail):
        nm = f"tail_{i + 1:02d}"
        bl.append((nm, t(tail[i]), t(tail[i + 1]), prev, U))
        prev = nm
    for sd in "LR":
        bl += [
            (f"ear_{sd}", t(lm[f"ear_base_{sd}"]), t(lm[f"ear_tip_{sd}"]), "head", F),
            (f"scapula_{sd}", t(lm[f"scap_{sd}"]), t(lm[f"shoulder_{sd}"]), "chest", F),
            (f"upperarm_{sd}", t(lm[f"shoulder_{sd}"]), t(lm[f"elbow_{sd}"]), f"scapula_{sd}", F),
            (f"forearm_{sd}", t(lm[f"elbow_{sd}"]), t(lm[f"wrist_{sd}"]), f"upperarm_{sd}", F),
            (f"hand_{sd}", t(lm[f"wrist_{sd}"]), t(lm[f"fpaw_{sd}"]), f"forearm_{sd}", F),
            (f"thigh_{sd}", t(lm[f"hip_{sd}"]), t(lm[f"knee_{sd}"]), "pelvis", F),
            (f"shin_{sd}", t(lm[f"knee_{sd}"]), t(lm[f"hock_{sd}"]), f"thigh_{sd}", F),
            (f"foot_{sd}", t(lm[f"hock_{sd}"]), t(lm[f"hpaw_{sd}"]), f"shin_{sd}", F),
            (f"toe_{sd}", t(lm[f"hpaw_{sd}"]), t(lm[f"htoe_{sd}"]), f"foot_{sd}", F),
        ]
    return bl


def flow_prim(M: S.Model, fn, pts, bone, label, k, soft, flow, name="", pad=0.0):
    p = M.add(fn, pts, bone, label, k, soft, name, pad)
    p.flow = S.normalize(flow)
    return p


class FurTex:
    """Generic fur texture: colour callback + strand relief following the prims' flow."""

    def __init__(self, model: S.Model, colour_fn, seed=1, strand=(900.0, 35.0), relief=0.00045,
                 rough=(0.62, 0.08), label_mats=None, ao_mix=0.3):
        self.model = model
        self.colour_fn = colour_fn
        self.seed = seed
        self.strand = strand
        self.relief = relief
        self.rough = rough
        self.names = model.label_names() if model is not None else []
        self.label_mats = label_mats or {}
        self.ao_mix = ao_mix

    def flow(self, P):
        prims = [p for p in self.model.prims if hasattr(p, "flow")]
        D = np.full((len(P), len(prims)), S.BIG)
        for j, pr in enumerate(prims):
            dc = S.length(P - pr.c) - pr.r
            m = dc < 0.03
            if m.any():
                D[m, j] = pr.fn(P[m])
        dmin = D.min(1, keepdims=True)
        W = np.exp(-np.clip(D - dmin, 0, None) / 0.006)
        F = W @ np.stack([p.flow for p in prims])
        return F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-9)

    def albedo_rough(self, P, N, lab, ao):
        fl = self.flow(P)
        s1 = X.aniso(P, fl, self.strand[0], self.strand[1], self.seed + 1, 2)
        s2 = X.aniso(P, fl, self.strand[0] * 0.25, self.strand[1] * 0.3, self.seed + 2, 2)
        alb, rough, metal = self.colour_fn(P, N, lab, fl, s1, s2, self.names)
        alb = alb * (1 - self.ao_mix + self.ao_mix * ao)[:, None]
        return np.clip(alb, 0.01, 0.9), np.clip(rough, 0.05, 1.0), metal

    def height(self, P, lab):
        fl = self.flow(P)
        h = self.relief * (0.6 * X.aniso(P, fl, self.strand[0], self.strand[1], self.seed + 1, 2)
                           + 0.8 * X.aniso(P, fl, self.strand[0] * 0.25, self.strand[1] * 0.3, self.seed + 2, 2))
        for li, nm in enumerate(self.names):
            if nm in self.label_mats:
                m = lab == li
                h[m] = self.label_mats[nm](P[m]) if callable(self.label_mats[nm]) else 0.0
        return h


# ---------------------------------------------------------------------------
# gaits
# ---------------------------------------------------------------------------
class QuadAnim:
    """Leg IK + gait cycles for quadrupeds in the sagittal plane."""

    def __init__(self, lm: dict, n_tail: int):
        self.lm = lm
        self.n_tail = n_tail
        self.s = lm["scale"]
        g = lambda k: np.asarray(lm[k], np.float64)  # noqa: E731
        self.sh = g("shoulder_L")
        self.el = g("elbow_L")
        self.wr = g("wrist_L")
        self.fp = g("fpaw_L")
        self.hp = g("hip_L")
        self.kn = g("knee_L")
        self.hk = g("hock_L")
        self.pw = g("hpaw_L")
        self.f1 = float(np.linalg.norm(self.el - self.sh))
        self.f2 = float(np.linalg.norm(self.wr - self.el))
        self.h1 = float(np.linalg.norm(self.kn - self.hp))
        self.h2 = float(np.linalg.norm(self.hk - self.kn))
        self.fp1 = A.pitch_of(self.sh, self.el)
        self.fp2 = A.pitch_of(self.el, self.wr)
        self.fp3 = A.pitch_of(self.wr, self.fp)
        self.hp1 = A.pitch_of(self.hp, self.kn)
        self.hp2 = A.pitch_of(self.kn, self.hk)
        self.hp3 = A.pitch_of(self.hk, self.pw)
        self.wr_off = self.wr - self.fp        # wrist above the paw contact
        self.hk_off = self.hk - self.pw        # hock above the paw contact

    def leg_targets(self, p: Pose, body_off, body_pitch, front_pitch_extra, tg: dict, flex: dict):
        """tg[leg] = (dy, dz) paw contact displacement from rest; flex[leg] = paw curl (deg)."""
        p.t("pelvis", body_off)
        p.r("pelvis", qx(body_pitch))
        bp = math.radians(body_pitch)
        cs, sn = math.cos(bp), math.sin(bp)
        piv = np.asarray(self.lm["pelvis"])

        def rotp(pt):
            r = np.asarray(pt) - piv
            y = r[1] * cs - r[2] * sn
            z = r[1] * sn + r[2] * cs
            return np.array([0, y, z]) + piv + np.asarray(body_off)

        for leg in LEGS:
            sd = leg[1]
            dy, dz = tg[leg]
            fl = flex.get(leg, 0.0)
            if leg[0] == "F":
                sh = rotp(self.sh)
                paw = self.fp + np.array([0, dy, dz])
                wr = paw + self.wr_off + np.array([0, 0, 0.0])
                # flexing the carpus lifts the wrist target slightly forward
                p1, p2, _ = A.ik2((sh[1], sh[2]), (wr[1], wr[2]), self.f1, self.f2, bend_sign=+1.0)
                ua = (p1 - self.fp1) - bp - math.radians(front_pitch_extra)
                fa = (p2 - self.fp2) - (p1 - self.fp1)
                hd = math.radians(fl) - (p2 - self.fp2)
                p.r(f"upperarm_{sd}", qx(math.degrees(ua)), sd)
                p.r(f"forearm_{sd}", qx(math.degrees(fa)), sd)
                p.r(f"hand_{sd}", qx(math.degrees(hd)), sd)
            else:
                hp = rotp(self.hp)
                paw = self.pw + np.array([0, dy, dz])
                hk = paw + self.hk_off
                p1, p2, _ = A.ik2((hp[1], hp[2]), (hk[1], hk[2]), self.h1, self.h2, bend_sign=-1.0)
                th = (p1 - self.hp1) - bp
                sh_ = (p2 - self.hp2) - (p1 - self.hp1)
                ft = -(p2 - self.hp2) + (math.radians(fl * 4.0) if fl < 0 else 0.0)
                p.r(f"thigh_{sd}", qx(math.degrees(th)), sd)
                p.r(f"shin_{sd}", qx(math.degrees(sh_)), sd)
                p.r(f"foot_{sd}", qx(math.degrees(ft)), sd)
                p.r(f"toe_{sd}", qx(-fl), sd)
        return p

    @staticmethod
    def cycle(ph, duty, half, lift):
        """Paw displacement (dy, dz, flex 0..1) for phase ph in [0,1): stance first."""
        if ph < duty:
            u = ph / duty
            return -half + 2 * half * u, 0.0, 0.0
        u = (ph - duty) / (1 - duty)
        e = 0.5 - 0.5 * math.cos(math.pi * u)
        return half - 2 * half * e, lift * math.sin(math.pi * u) ** 0.8, math.sin(math.pi * min(u * 1.3, 1.0))

    def tail(self, p: Pose, base_pitch, wag_amp, wag_t, curl=0.0):
        n = self.n_tail
        for i in range(n):
            ph = wag_t - i * 0.08
            p.r(f"tail_{i + 1:02d}", qz(wag_amp * math.sin(2 * math.pi * ph) / n * 2.0) @
                qx(-(base_pitch if i == 0 else 0) - curl / n))
        return p
