"""Birds (owner: creatures): rock pigeon, house crow "Lão Quạ" (old, scruffy, nicked beak), sparrow.

One parametric bird body + a separate spread flight-wing mesh. Ground clips keep the flight
wings collapsed (wing bones scaled to 0.01, hidden inside the body) and show the folded
wings sculpted on the flanks; flight clips scale them in and flap.

Bones: root, pelvis, chest, neck_01, neck_02, head, jaw, tail, wingfold_L/R,
upperarm_L/R, forearm_L/R, hand_L/R, thigh_L/R, shin_L/R, foot_L/R, toe_L/R.
Clips: idle(L) peck(L) walk(L) fly(L) takeoff land  (+ crow: caw, hop).
"""
from __future__ import annotations

import math

import numpy as np
from mathutils import Quaternion, Vector

import npc_anim as A
import npc_quad as Q
import npc_sdf as S
import npc_tex as X
from npc_anim import Pose, qx, qy, qz, wave, noise1, smoothstep
from npc_tex import col, mix, sstep

KINDS = {
    #            scale  length  body width fac, tail fac, beak len fac, legs fac
    "pigeon": dict(s=1.0, beak=0.0175, tail=1.0, body=1.0, neck=1.0, leg=1.0, span=1.0, head=1.0),
    "crow": dict(s=1.32, beak=0.044, tail=1.15, body=0.92, neck=1.05, leg=1.15, span=1.05, head=1.08),
    "sparrow": dict(s=0.47, beak=0.0125, tail=1.05, body=1.0, neck=0.7, leg=1.0, span=0.9, head=1.25),
}
CLIPS = {"idle": (90, True), "peck": (36, True), "walk": (20, True), "fly": (12, True), "takeoff": (20, False),
         "land": (24, False)}
CROW_CLIPS = {"caw": (30, False), "hop": (18, False)}
WALK_SPEED = {"pigeon": 0.45, "crow": 0.6, "sparrow": 0.25}


class Bird:
    def __init__(self, kind: str):
        self.kind = kind
        k = KINDS[kind]
        self.k = k
        s = self.s = k["s"]
        hs = k["head"]
        L = {}
        L["pelvis"] = np.array([0, 0.035, 0.105]) * s
        L["chest"] = np.array([0, -0.03, 0.125]) * s
        L["neck_base"] = np.array([0, -0.052, 0.145]) * s
        L["neck_mid"] = np.array([0, -0.066, 0.178]) * s * np.array([1, 1, 1]) + np.array([0, 0, 0.012]) * s * (k["neck"] - 1)
        L["head"] = np.array([0, -0.078, 0.205 + 0.01 * (k["neck"] - 1)]) * s
        L["beak_base"] = L["head"] + np.array([0, -0.020 * hs, 0.002]) * s
        L["beak_tip"] = L["beak_base"] + np.array([0, -k["beak"], -0.004 * k["beak"] / 0.0175])
        L["jaw_pivot"] = L["head"] + np.array([0, -0.012, -0.006]) * s
        L["tail_base"] = np.array([0, 0.075, 0.092]) * s
        L["tail_tip"] = np.array([0, 0.075 + 0.095 * k["tail"], 0.066]) * s
        for sd, sg in (("L", 1), ("R", -1)):
            L[f"shoulder_{sd}"] = np.array([0.036 * sg, -0.025, 0.14]) * s
            L[f"elbow_{sd}"] = np.array([0.105 * sg * k["span"], -0.012, 0.145]) * s
            L[f"wrist_{sd}"] = np.array([0.175 * sg * k["span"], -0.02, 0.145]) * s
            L[f"wingtip_{sd}"] = np.array([0.33 * sg * k["span"], 0.035, 0.142]) * s
            L[f"fold_{sd}"] = np.array([0.04 * sg, -0.02, 0.135]) * s
            L[f"fold_tip_{sd}"] = np.array([0.026 * sg, 0.13, 0.092]) * s
            L[f"hip_{sd}"] = np.array([0.022 * sg, 0.018, 0.095]) * s
            L[f"knee_{sd}"] = np.array([0.026 * sg, -0.012, 0.072 * k["leg"]]) * s
            L[f"ankle_{sd}"] = np.array([0.022 * sg, 0.012, 0.042 * k["leg"]]) * s
            L[f"foot_{sd}"] = np.array([0.020 * sg, 0.002, 0.006]) * s
            L[f"toe_{sd}"] = np.array([0.020 * sg, -0.032, 0.003]) * s
            eye_off = np.array([0.0135 * sg * hs, -0.006 * hs, 0.004 * hs]) * s
            L[f"eye_{sd}"] = L["head"] + eye_off
        self.L = L
        self.eye_r = 0.0042 * s * hs * (1.25 if kind == "sparrow" else 1.0)

    def bones(self):
        L = self.L
        t = lambda v: tuple(float(a) for a in v)  # noqa: E731
        U = (0, 0, 1)
        F = (0, -1, 0)
        s = self.s
        bl = [
            ("root", (0, 0, 0), (0, 0.03 * s, 0), None, U),
            ("pelvis", t(L["pelvis"]), t(L["chest"]), "root", U),
            ("chest", t(L["chest"]), t(L["neck_base"]), "pelvis", U),
            ("neck_01", t(L["neck_base"]), t(L["neck_mid"]), "chest", F),
            ("neck_02", t(L["neck_mid"]), t(L["head"]), "neck_01", F),
            ("head", t(L["head"]), t(L["beak_tip"]), "neck_02", U),
            ("jaw", t(L["jaw_pivot"]), t(L["beak_tip"] + np.array([0, 0.002, -0.002]) * s), "head", U),
            ("tail", t(L["tail_base"]), t(L["tail_tip"]), "pelvis", U),
        ]
        for sd in "LR":
            bl += [
                (f"wingfold_{sd}", t(L[f"fold_{sd}"]), t(L[f"fold_tip_{sd}"]), "chest", U),
                (f"upperarm_{sd}", t(L[f"shoulder_{sd}"]), t(L[f"elbow_{sd}"]), "chest", U),
                (f"forearm_{sd}", t(L[f"elbow_{sd}"]), t(L[f"wrist_{sd}"]), f"upperarm_{sd}", U),
                (f"hand_{sd}", t(L[f"wrist_{sd}"]), t(L[f"wingtip_{sd}"]), f"forearm_{sd}", U),
                (f"thigh_{sd}", t(L[f"hip_{sd}"]), t(L[f"knee_{sd}"]), "pelvis", F),
                (f"shin_{sd}", t(L[f"knee_{sd}"]), t(L[f"ankle_{sd}"]), f"thigh_{sd}", F),
                (f"foot_{sd}", t(L[f"ankle_{sd}"]), t(L[f"foot_{sd}"]), f"shin_{sd}", F),
                (f"toe_{sd}", t(L[f"foot_{sd}"]), t(L[f"toe_{sd}"]), f"foot_{sd}", U),
            ]
        return bl

    # ------------------------------------------------------------------
    def body_model(self) -> S.Model:
        L = self.L
        s = self.s
        k = self.k
        M = S.Model(band=0.03 * s)
        fp = Q.flow_prim
        E = S.f_ellipsoid
        RC = S.f_round_cone
        back = (0, 1, -0.25)
        bw = k["body"]
        tilt = S.rot((1, 0, 0), -22)
        fp(M, E(np.array([0, 0.018, 0.112]) * s, np.array([0.047 * bw, 0.080, 0.050]) * s, tilt),
           [np.array([0, 0.018, 0.112]) * s], {"pelvis": 0.6, "chest": 0.4}, "body", 0.02 * s, 0.015 * s, back, "body",
           pad=0.08 * s)
        fp(M, E(np.array([0, -0.035, 0.122]) * s, np.array([0.045 * bw, 0.045, 0.048]) * s),
           [np.array([0, -0.035, 0.122]) * s], "chest", "breast", 0.025 * s, 0.015 * s, (0, 0.2, -1), "breast",
           pad=0.05 * s)
        fp(M, E(np.array([0, 0.06, 0.085]) * s, np.array([0.032, 0.05, 0.03]) * s), [np.array([0, 0.06, 0.085]) * s],
           "pelvis", "belly", 0.02 * s, 0.015 * s, back, "vent", pad=0.05 * s)
        nr = (0.026 if self.kind != "sparrow" else 0.03) * s
        fp(M, RC(L["neck_base"] + np.array([0, 0.005, -0.008]) * s, L["neck_mid"], nr, nr * 0.88), [L["neck_base"],
           L["neck_mid"]], "neck_01", "neck", 0.02 * s, 0.012 * s, (0, 0.6, -1), "neck", pad=0.03 * s)
        fp(M, RC(L["neck_mid"], L["head"] + np.array([0, 0.006, -0.008]) * s, nr * 0.88, nr * 0.72),
           [L["neck_mid"], L["head"]], "neck_02", "neck", 0.016 * s, 0.01 * s, (0, 0.6, -1), "neck2", pad=0.03 * s)
        hr = 0.0205 * s * k["head"]
        fp(M, E(L["head"], np.array([hr * 0.95, hr * 1.12, hr * 0.98])), [L["head"]], "head", "head", 0.012 * s,
           0.008 * s, (0, 1, 0.1), "head", pad=hr * 1.2)
        # beak (upper on head, lower on jaw)
        bb, bt = L["beak_base"], L["beak_tip"]
        br = 0.0062 * s * (1.45 if self.kind == "crow" else 1.0) * (1.3 if self.kind == "sparrow" else 1.0)
        up = RC(bb + np.array([0, 0.0, 0.0015]) * s, bt + np.array([0, 0, 0.0005]) * s, br, 0.0009 * s)
        lo = RC(bb + np.array([0, 0.0, -0.0028]) * s, bt + np.array([0, -0.001, -0.0012]) * s + (bb - bt) * 0.06,
                br * 0.8, 0.0008 * s)
        if self.kind == "crow":
            # old crow: a chip out of the upper mandible's cutting edge
            nick_c = bb + (bt - bb) * 0.62 + np.array([0.0035, 0, -0.0012]) * s
            up_f = up
            up = lambda p, f=up_f, c=nick_c: np.maximum(f(p), -(S.length(p - c) - 0.0032 * s))  # noqa: E731
        M.add(up, [bb, bt], "head", "beak", 0.004 * s, 0.006 * s, "beak", pad=0.012 * s)
        M.add(lo, [bb, bt], "jaw", "beak", 0.003 * s, 0.006 * s, "beak_low", pad=0.012 * s)
        if self.kind == "pigeon":
            M.add(E(bb + np.array([0, -0.002, 0.0035]) * s, np.array([0.0045, 0.006, 0.003]) * s), [bb], "head", "cere",
                  0.003 * s, 0.006 * s, "cere", pad=0.008 * s)
        if self.kind == "crow":
            # rictal bristles / nasal tuft over the beak base
            fp(M, E(bb + np.array([0, 0.002, 0.0045]) * s, np.array([0.006, 0.009, 0.004]) * s), [bb], "head", "head",
               0.004 * s, 0.006 * s, (0, -1, 0.2), "tuft", pad=0.01 * s)
        # eyes: small sockets
        for sd in "LR":
            e = L[f"eye_{sd}"]
            M.add(S.f_sphere(e, self.eye_r * 1.25), [e], "head", "eyering", 0.002 * s, 0.006 * s, "lid",
                  pad=self.eye_r * 1.5)
            sg = 1 if sd == "L" else -1
            ap = (lambda c, sgn: (lambda p: S.length((p - c) * np.array([1.6, 1.0, 1.0])) - self.eye_r * 1.1
                                  - 0.0 * sgn))(e + np.array([0.004 * sg, 0, 0]) * s, sg)
            M.carve(ap, [e], k=0.0008 * s, pad=0.01 * s)
        # folded wings on the flanks
        for sd, sg in (("L", 1), ("R", -1)):
            a, b = L[f"fold_{sd}"], L[f"fold_tip_{sd}"]
            fp(M, S.f_flat_cone(a + np.array([0.004 * sg, 0.01, -0.006]) * s, b, 0.032 * s, 0.009 * s, 0.38,
                                (1 * sg, 0, 0.35)), [a, b], f"wingfold_{sd}", "wing", 0.008 * s, 0.01 * s, b - a,
               "foldwing", pad=0.04 * s)
        # tail fan
        tb, tt = L["tail_base"], L["tail_tip"]
        tail = S.f_flat_cone(tb, tt, 0.022 * s, 0.038 * s, 0.14, (0, 0, 1))
        fp(M, tail, [tb, tt], "tail", "tail", 0.01 * s, 0.01 * s, tt - tb, "tail", pad=0.04 * s)
        # legs: feathered thigh, scaly tarsus, toes with claws
        for sd, sg in (("L", 1), ("R", -1)):
            kn, an, ft, to = L[f"knee_{sd}"], L[f"ankle_{sd}"], L[f"foot_{sd}"], L[f"toe_{sd}"]
            fp(M, E(L[f"hip_{sd}"] * 0.5 + kn * 0.5, np.array([0.014, 0.02, 0.022]) * s), [kn], {f"thigh_{sd}": 0.7,
               "pelvis": 0.3}, "body", 0.015 * s, 0.01 * s, (0, 0.3, -1), "thigh", pad=0.03 * s)
            M.add(RC(kn, an, 0.0048 * s, 0.0032 * s), [kn, an], f"shin_{sd}", "leg", 0.004 * s, 0.006 * s, "shank",
                  pad=0.008 * s)
            M.add(RC(an, ft + np.array([0, 0, 0.002]) * s, 0.0029 * s, 0.0027 * s), [an, ft], f"foot_{sd}", "leg",
                  0.003 * s, 0.005 * s, "tarsus", pad=0.006 * s)
            for ang in (-28, 0, 28):
                d = S.rot((0, 0, 1), ang * sg) @ np.array([0, -1, 0])
                tip = ft + d * 0.03 * s * (1.1 if ang == 0 else 0.85) + np.array([0, 0, -0.0035]) * s
                M.add(RC(ft, tip, 0.0024 * s, 0.0015 * s), [ft, tip], f"toe_{sd}", "leg", 0.002 * s, 0.004 * s, "toe",
                      pad=0.006 * s)
                M.add(RC(tip, tip + d * 0.005 * s + np.array([0, 0, -0.002]) * s, 0.0012 * s, 0.0005 * s), [tip],
                      f"toe_{sd}", "claw", 0.001 * s, 0.003 * s, "claw", pad=0.008 * s)
            hall = ft + np.array([0, 0.018, -0.002]) * s
            M.add(RC(ft, hall, 0.0022 * s, 0.0014 * s), [ft, hall], f"foot_{sd}", "leg", 0.002 * s, 0.004 * s, "hallux",
                  pad=0.006 * s)
        if self.kind == "crow":
            # scruffy: a few raised feather tufts on the nape and a ragged tail notch
            for i, (dx, dy, dz) in enumerate(((0.006, 0.012, 0.016), (-0.007, 0.016, 0.012), (0.0, 0.02, 0.006))):
                c = L["head"] + np.array([dx, dy, dz]) * s
                fp(M, S.f_flat_cone(c - np.array([0, 0.006, 0.004]) * s, c + np.array([dx * 0.4, 0.012, 0.006]) * s,
                                    0.004 * s, 0.0012 * s, 0.4, (1, 0, 0)), [c], "head", "head", 0.003 * s, 0.006 * s,
                   (0, 1, 0.4), "tuft", pad=0.015 * s)
            M.carve(S.f_sphere(tt + np.array([0.012, 0.004, 0.0]) * s, 0.012 * s), [tt], k=0.002 * s, pad=0.015 * s)
        return M

    def wing_model(self) -> S.Model:
        """Spread flight wings (separate mesh), feathered trailing edge."""
        L = self.L
        s = self.s
        M = S.Model(band=0.02 * s)
        fp = Q.flow_prim
        for sd, sg in (("L", 1), ("R", -1)):
            sh, el, wr, tp = (L[f"shoulder_{sd}"], L[f"elbow_{sd}"], L[f"wrist_{sd}"], L[f"wingtip_{sd}"])
            th = 0.0035 * s
            # arm section (secondaries): slab between leading edge and trailing edge
            for a, b, c1, c2, bone, nm in ((sh + np.array([0.012 * sg, 0, 0]) * s, el, 0.085, 0.10, f"upperarm_{sd}",
                                            "inner"), (el, wr, 0.10, 0.095, f"forearm_{sd}", "mid")):
                mid_a = a + np.array([0, c1 * 0.42, 0]) * s
                mid_b = b + np.array([0, c2 * 0.42, 0]) * s
                fn = S.f_flat_cone(mid_a, mid_b, c1 * 0.5 * s, c2 * 0.5 * s, 0.05, (0, 1, 0))
                fp(M, fn, [mid_a, mid_b], bone, "flight", 0.006 * s, 0.01 * s, (0, 1, 0), nm, pad=0.06 * s)
                fp(M, S.f_capsule(a, b, 0.0075 * s), [a, b], bone, "coverts", 0.008 * s, 0.01 * s, (0, 1, 0), nm + "_le",
                   pad=0.01 * s)
            # hand section (primaries): tapering to the tip
            ma = wr + np.array([0, 0.045, 0]) * s
            fn = S.f_flat_cone(ma, tp, 0.05 * s, 0.014 * s, 0.07, (0, 1, 0))
            fp(M, fn, [ma, tp], f"hand_{sd}", "flight", 0.006 * s, 0.01 * s, S.normalize(tp - wr), "outer", pad=0.06 * s)
            fp(M, S.f_round_cone(wr, wr + (tp - wr) * 0.45, 0.007 * s, 0.003 * s), [wr, tp], f"hand_{sd}", "coverts",
               0.008 * s, 0.01 * s, (0, 1, 0), "hand_le", pad=0.01 * s)
            # serrated trailing edge: notches between feather tips
            for i in range(14):
                u = (i + 0.5) / 14
                if u < 0.55:
                    pa = sh + (wr - sh) * (u / 0.55)
                    te = pa + np.array([0, 0.095, -0.0]) * s
                else:
                    v = (u - 0.55) / 0.45
                    pa = wr + (tp - wr) * v
                    te = pa + np.array([0, 0.045 * (1 - v) + 0.006, 0]) * s
                c = te + np.array([0, 0.0085, 0]) * s
                M.carve(S.f_cyl(c - np.array([0, 0, 0.02]) * s, c + np.array([0, 0, 0.02]) * s, 0.0075 * s), [c],
                        k=0.0015 * s, pad=0.02 * s)
        return M


# ---------------------------------------------------------------------------
# plumage colours
# ---------------------------------------------------------------------------
def plumage(kind, L, s):
    head = np.asarray(L["head"])

    def fn(P, N, lab, fl, s1, s2, names):
        K = len(P)
        li = {n: i for i, n in enumerate(names)}
        rough = 0.6 + 0.08 * s1
        metal = np.zeros(K)
        # feather scallops: cell pattern aligned with the flow
        d, cid, _ = X.cells(P, 0.007 * s, 13)
        edge = sstep(0.0025 * s, 0.0036 * s, d)
        if kind == "pigeon":
            grey = col("#8d929c")
            a = grey[None] * (0.92 + 0.12 * s2[:, None])
            # dark head and neck, iridescent green/purple neck sheen
            neck = np.exp(-np.sum(((P - (head + np.array([0, 0.03, -0.045]) * s)) / (np.array([0.05, 0.05, 0.05]) * s))
                                  ** 2, 1))
            hd = np.exp(-np.sum(((P - head) / (0.028 * s)) ** 2, 1))
            dark = col("#4b505c")
            a = mix(a, dark[None], np.clip(neck * 1.4 + hd, 0, 1) * 0.8)
            band = np.sin(np.einsum("ij,j->i", P - head, np.array([0.3, 0.6, 1.0])) / (0.012 * s) * 2.0)
            irid = mix(col("#3f7a5a")[None], col("#7a4a86")[None], (0.5 + 0.5 * band))
            ir = sstep(0.25, 0.7, neck) * (1 - sstep(0.5, 0.9, hd))
            a = mix(a, irid * (0.9 + 0.2 * s1[:, None]), ir * 0.85)
            rough = rough - 0.25 * ir
            # two black wing bars + dark primaries / tail band
            if "wing" in li:
                m = lab == li["wing"]
                fy = (P[m, 1] / s)
                bars = (sstep(0.006, 0.0, np.abs(fy - 0.045)) + sstep(0.006, 0.0, np.abs(fy - 0.072)))
                a[m] = mix(a[m], col("#2a2a2e")[None], np.clip(bars, 0, 1) * 0.9)
                tipd = sstep(0.10, 0.125, fy)
                a[m] = mix(a[m], col("#3e4048")[None], tipd * 0.8)
            if "tail" in li:
                m = lab == li["tail"]
                a[m] = mix(a[m], col("#2c2d33")[None], sstep(0.14, 0.155, P[m, 1] / s)[:, None] * 0.9)
            if "flight" in li:
                m = lab == li["flight"]
                ax = np.abs(P[m, 0]) / s
                a[m] = grey[None] * 0.95
                a[m] = mix(a[m], col("#33353b")[None], sstep(0.2, 0.28, ax) * 0.85)
            body_lab = ("body", "breast", "belly", "neck", "head", "wing", "tail", "flight", "coverts")
            a = mix(a, a * 0.8, (1 - edge) * 0.25 * np.isin(lab, [li[n] for n in body_lab if n in li]))
            legc, beakc = "#b8423c", "#2e2a2a"
        elif kind == "crow":
            # house crow: glossy black with a dusty grey nape/neck collar; old bird -> faded, ragged
            blk = col("#16161a")
            a = blk[None] * (0.9 + 0.25 * s2[:, None])
            # grey-brown shawl: nape, neck sides, upper mantle and upper breast; crown, face and throat stay black
            collar = np.exp(-np.sum(((P - (head + np.array([0, 0.016, -0.042]) * s)) /
                                     (np.array([0.042, 0.042, 0.036]) * s)) ** 2, 1))
            collar *= sstep(head[2] - 0.10 * s, head[2] - 0.07 * s, P[:, 2])
            face = np.exp(-np.sum(((P - (head + np.array([0, -0.018, 0.022]) * s)) / (np.array([0.03, 0.03, 0.024]) * s))
                                  ** 2, 1))
            throat = np.exp(-np.sum(((P - (head + np.array([0, -0.03, -0.008]) * s)) /
                                     (np.array([0.014, 0.016, 0.02]) * s)) ** 2, 1))
            collar = np.clip(collar * 1.7 - face * 2.5 - throat * 1.6, 0, 1)
            collar *= 0.75 + 0.5 * sstep(0.3, 0.7, X.aniso(P, fl, 300.0 / s, 30.0 / s, 23))
            gloss = col("#262c3e")
            a = mix(a, gloss[None], sstep(0.2, 0.8, s1) * 0.35)
            faded = sstep(0.3, 0.9, X.fbm(P, 30.0 / s, 3, 17)) * 0.35
            a = mix(a, col("#3c3832")[None], faded)
            a = mix(a, a * 0.65, (1 - edge) * 0.4)
            grey = col("#8a857e")[None] * (0.8 + 0.3 * s1[:, None]) * (0.75 + 0.25 * edge[:, None])
            a = mix(a, grey, np.clip(collar, 0, 1) * 0.95)
            rough = 0.42 + 0.15 * s1 + 0.2 * faded + 0.15 * collar
            legc, beakc = "#141414", "#121212"
        else:   # sparrow (Eurasian tree sparrow: chestnut cap, black cheek spot, white collar)
            brown = col("#8a5c38")
            buff = col("#c9b49a")
            a = brown[None] * (0.85 + 0.2 * s2[:, None])
            streak = sstep(0.3, 0.7, X.aniso(P, fl, 400.0 / s, 30.0 / s, 19))
            a = mix(a, col("#2d1e14")[None], streak * 0.55 * (P[:, 2] > 0.1 * s))
            under = sstep(0.0, -0.6, N[:, 2]) + sstep(-0.02 * s, -0.05 * s, P[:, 1]) * (P[:, 2] < 0.15 * s)
            a = mix(a, buff[None], np.clip(under, 0, 1) * 0.8)
            cap = np.exp(-np.sum(((P - (head + np.array([0, 0.004, 0.012]) * s)) / (0.016 * s)) ** 2, 1))
            a = mix(a, col("#7a3f22")[None], np.clip(cap * 1.5, 0, 1))
            cheek = np.zeros(K)
            for sg in (1, -1):
                cheek += np.exp(-np.sum(((P - (head + np.array([0.017 * sg, 0.006, -0.006]) * s)) / (0.0045 * s)) ** 2, 1))
            white = np.zeros(K)
            for sg in (1, -1):
                white += np.exp(-np.sum(((P - (head + np.array([0.016 * sg, 0.004, -0.004]) * s)) / (0.010 * s)) ** 2, 1))
            a = mix(a, col("#e6e0d6")[None], np.clip(white, 0, 1) * 0.85)
            a = mix(a, col("#161210")[None], np.clip(cheek * 1.4, 0, 1))
            bib = np.exp(-np.sum(((P - (head + np.array([0, -0.006, -0.016]) * s)) / (np.array([0.007, 0.006, 0.008]) * s))
                                 ** 2, 1))
            a = mix(a, col("#161210")[None], np.clip(bib * 1.5, 0, 1))
            if "wing" in li:
                m = lab == li["wing"]
                bar = sstep(0.005, 0.0, np.abs(P[m, 1] / s - 0.035))
                a[m] = mix(a[m], col("#e8e2d8")[None], bar * 0.8)
            a = mix(a, a * 0.75, (1 - edge) * 0.25)
            legc, beakc = "#a07a5c", "#252220"
        for nm, c, r in (("leg", legc, 0.55), ("claw", "#2a2522", 0.4), ("beak", beakc, 0.35),
                         ("cere", "#e8e4dc", 0.7), ("eyering", "#d06040" if kind == "pigeon" else "#2a2420", 0.5)):
            if nm in li:
                m = lab == li[nm]
                v = X.fbm(P[m], 900.0 / s, 2, 23)
                a[m] = col(c) * (0.9 + 0.15 * v[:, None])
                rough[m] = r + 0.05 * v
        if kind == "crow" and "beak" in li:
            m = lab == li["beak"]
            wear = sstep(0.4, 0.9, X.fbm(P[m], 400.0 / s, 2, 29))
            a[m] = mix(a[m], col("#3a3632")[None], wear * 0.6)
        if kind == "pigeon" and "leg" in li:
            m = lab == li["leg"]
            scales = sstep(0.4, 0.6, 0.5 + 0.5 * np.sin(P[m, 2] / s * 900))
            a[m] = a[m] * (0.85 + 0.15 * scales[:, None])
        return a, rough, metal
    return fn


# ---------------------------------------------------------------------------
class BirdAnim:
    def __init__(self, bird: Bird):
        self.b = bird
        self.kind = bird.kind
        L = bird.L
        self.s = bird.s
        self.hip = np.asarray(L["hip_L"])
        self.knee = np.asarray(L["knee_L"])
        self.ankle = np.asarray(L["ankle_L"])
        self.foot = np.asarray(L["foot_L"])
        self.l1 = float(np.linalg.norm(self.knee - self.hip))
        self.l2 = float(np.linalg.norm(self.ankle - self.knee))
        self.p1r = A.pitch_of(self.hip, self.knee)
        self.p2r = A.pitch_of(self.knee, self.ankle)
        self.p3r = A.pitch_of(self.ankle, self.foot)
        self.clips = dict(CLIPS)
        if bird.kind == "crow":
            self.clips.update(CROW_CLIPS)

    def wings(self, p, open_=0.0, flap=0.0, fold_lift=0.0):
        """open_ 0 = flight wings hidden (scaled to 0.01), 1 = spread. flap in [-1, 1]."""
        sc = 0.01 + 0.99 * open_
        for sd in "LR":
            p.r(f"upperarm_{sd}", qy(-flap * 42 * open_ - (1 - open_) * 30), sd)
            p.r(f"forearm_{sd}", qy(-flap * 14 * open_) @ qz(18 * (1 - open_)), sd)
            p.r(f"hand_{sd}", qy(-flap * 22 * open_) @ qx(8 * flap * open_), sd)
            p.r(f"wingfold_{sd}", qy(-fold_lift * 12) @ qx(-fold_lift * 6), sd)
            self.scale(p, f"upperarm_{sd}", sc)
        return p

    @staticmethod
    def scale(p, bone, s):
        if not hasattr(p, "scl"):
            p.scl = {}
        p.scl[bone] = s

    def legs(self, p, body_off, body_pitch, tg, toe_curl=None):
        p.t("pelvis", body_off)
        p.r("pelvis", qx(body_pitch))
        bp = math.radians(body_pitch)
        for sd in "LR":
            dy, dz = tg[sd]
            hip_y = self.hip[1] + body_off[1]
            hip_z = self.hip[2] + body_off[2]
            target = (self.ankle[1] + dy, self.ankle[2] + dz)
            p1, p2, _ = A.ik2((hip_y, hip_z), target, self.l1, self.l2, bend_sign=-1.0)
            p.r(f"thigh_{sd}", qx(math.degrees((p1 - self.p1r) - bp)), sd)
            p.r(f"shin_{sd}", qx(math.degrees((p2 - self.p2r) - (p1 - self.p1r))), sd)
            p.r(f"foot_{sd}", qx(math.degrees(-(p2 - self.p2r))), sd)
            if toe_curl:
                p.r(f"toe_{sd}", qx(toe_curl.get(sd, 0.0)), sd)
        return p

    def stand(self, p, off=(0, 0, 0), pitch=0.0):
        return self.legs(p, off, pitch, {"L": (0, 0), "R": (0, 0)})

    def idle(self, t):
        p = Pose()
        s = self.s
        self.stand(p, (0, 0, -0.002 * s + 0.001 * s * wave(t, 1.2)))
        k = noise1(t, 3, 3.0)
        p.r("neck_01", qx(4 * noise1(t, 5, 3.0)))
        snap = 1.0 if (t % 1.0) < 0.5 else -1.0
        p.r("head", qz(28 * k + 6 * snap * (abs(k) > 0.3)) @ qy(10 * noise1(t, 7, 3.0)))
        p.r("tail", qx(4 * wave(t, 1.5)))
        self.wings(p, 0.0, fold_lift=0.1 * max(0.0, wave(t, 3.0)))
        return p

    def peck(self, t):
        p = Pose()
        s = self.s
        T = self.clips["peck"][0] / A.FPS
        u = t / T
        dip = smoothstep(0.05, 0.25, u) - smoothstep(0.75, 0.95, u)
        jab = max(0.0, math.sin(2 * math.pi * (u * 3))) if 0.25 < u < 0.75 else 0.0
        self.stand(p, (0, -0.004 * s * dip, -0.012 * s * dip), pitch=18 * dip)
        p.r("neck_01", qx(40 * dip + 14 * jab))
        p.r("neck_02", qx(25 * dip + 10 * jab))
        p.r("head", qx(10 * dip))
        p.r("jaw", qx(10 * jab))
        p.r("tail", qx(-12 * dip))
        self.wings(p, 0.0)
        return p

    def walk(self, t):
        p = Pose()
        s = self.s
        T = self.clips["walk"][0] / A.FPS
        u = t / T
        half = WALK_SPEED[self.kind] * T * 0.6 * 0.5
        tg = {}
        for sd, ph in (("L", u), ("R", (u + 0.5) % 1.0)):
            dy, dz, f = Q.QuadAnim.cycle(ph, 0.6, half, 0.022 * s)
            tg[sd] = (dy, dz)
        sway = 0.004 * s * math.sin(2 * math.pi * u)
        self.legs(p, (sway, 0, -0.003 * s), 6, tg, {"L": 20 * max(0, tg["L"][1]) / (0.02 * s),
                                                      "R": 20 * max(0, tg["R"][1]) / (0.02 * s)})
        p.r("pelvis", qy(-5 * math.sin(2 * math.pi * u)))
        # head bob: hold still then thrust (twice per cycle)
        v = (u * 2) % 1.0
        thrust = smoothstep(0.55, 0.8, v) - smoothstep(0.9, 1.0, v) * 0.0
        back_ = 1 - thrust
        p.r("neck_01", qx(-10 * back_ + 14 * thrust))
        p.r("neck_02", qx(10 * back_ - 8 * thrust))
        p.r("tail", qx(4 * math.sin(4 * math.pi * u)))
        self.wings(p, 0.0)
        return p

    def _flight_body(self, p, t, flap, open_=1.0, legs_up=1.0):
        s = self.s
        p.r("pelvis", qx(-12 * legs_up))
        p.r("neck_01", qx(-18))
        p.r("neck_02", qx(8))
        p.r("head", qx(16))
        # legs tucked back
        for sd in "LR":
            p.r(f"thigh_{sd}", qx(55 * legs_up), sd)
            p.r(f"shin_{sd}", qx(-40 * legs_up), sd)
            p.r(f"foot_{sd}", qx(60 * legs_up), sd)
            p.r(f"toe_{sd}", qx(50 * legs_up), sd)
        p.r("tail", qx(10))
        self.wings(p, open_, flap)
        p.t("pelvis", (0, 0, 0.004 * s * flap))
        return p

    def fly(self, t):
        T = self.clips["fly"][0] / A.FPS
        flap = math.sin(2 * math.pi * t / T)
        return self._flight_body(Pose(), t, flap)

    def takeoff(self, t):
        T = self.clips["takeoff"][0] / A.FPS
        u = t / T
        p = Pose()
        s = self.s
        crouch = smoothstep(0.0, 0.25, u) - smoothstep(0.25, 0.4, u)
        air = smoothstep(0.3, 0.6, u)
        open_ = smoothstep(0.1, 0.35, u)
        flap = math.sin(2 * math.pi * u * 2.5)
        if air < 0.5:
            self.stand(p, (0, 0, -0.02 * s * crouch + 0.03 * s * air), pitch=-10 * crouch)
            self.wings(p, open_, flap * open_)
        else:
            self._flight_body(p, t, flap, open_, legs_up=air)
            p.t("pelvis", (0, 0, 0.03 * s * air))
        return p

    def land(self, t):
        T = self.clips["land"][0] / A.FPS
        u = t / T
        p = Pose()
        s = self.s
        air = 1 - smoothstep(0.35, 0.55, u)
        open_ = 1 - smoothstep(0.55, 0.85, u)
        flap = math.sin(2 * math.pi * u * 3.0) * (0.4 + 0.6 * air)
        if air > 0.5:
            self._flight_body(p, t, flap, open_, legs_up=0.0)
            p.r("pelvis", qx(-25 * air))
            p.t("pelvis", (0, 0, 0.03 * s * air))
        else:
            sink = smoothstep(0.45, 0.6, u) - smoothstep(0.6, 0.9, u)
            self.stand(p, (0, 0, -0.015 * s * sink), pitch=-8 * (1 - u))
            self.wings(p, open_, flap * open_ * 0.5)
        return p

    # crow extras
    def caw(self, t):
        T = self.clips["caw"][0] / A.FPS
        u = t / T
        k = math.sin(math.pi * smoothstep(0.1, 0.6, u)) * (1 - smoothstep(0.85, 1.0, u))
        p = Pose()
        s = self.s
        self.stand(p, (0, 0, 0.004 * s * k), pitch=-6 * k)
        p.r("neck_01", qx(-22 * k))
        p.r("neck_02", qx(28 * k))
        p.r("head", qx(-6 * k))
        p.r("jaw", qx(26 * (smoothstep(0.2, 0.32, u) - smoothstep(0.55, 0.7, u))))
        p.r("tail", qx(-14 * k))
        self.wings(p, 0.0, fold_lift=0.8 * k)
        return p

    def hop(self, t):
        T = self.clips["hop"][0] / A.FPS
        u = t / T
        p = Pose()
        s = self.s
        crouch = smoothstep(0.0, 0.2, u) - smoothstep(0.2, 0.3, u) + smoothstep(0.75, 0.85, u) - smoothstep(0.85, 1.0, u)
        air = math.sin(math.pi * min(max((u - 0.25) / 0.5, 0.0), 1.0))
        z = 0.05 * s * air - 0.015 * s * crouch
        self.legs(p, (0, 0, z), -8 * crouch, {"L": (0, z * 0.7 if air > 0 else 0), "R": (0, z * 0.7 if air > 0 else 0)})
        self.wings(p, 0.0, fold_lift=air)
        p.r("tail", qx(-10 * air))
        return p

    def bake_all(self, animator):
        for nm, (fr, loop) in self.clips.items():
            animator.bake_clip(nm, getattr(self, nm), fr, loop)

    def pose_list(self):
        return [(n, 0.25 * self.clips[n][0] / 30.0) for n in self.clips]


def kit(kind):
    import npc_build  # noqa: F401
    b = Bird(kind)
    body = b.body_model()
    wings = b.wing_model()
    # texture model: body + wings as a layer
    tm = b.body_model()
    lay = tm.layer("flight")
    lay.prims = wings.prims
    lay.carves = wings.carves
    tex = Q.FurTex(tm, plumage(kind, b.L, b.s), seed=5, strand=(500.0 / b.s, 40.0 / b.s), relief=0.0003 * b.s,
                   rough=(0.6, 0.08), ao_mix=0.25)
    L = b.L
    eyes = [(L["eye_L"], b.eye_r, (1, -0.25, 0.1)), (L["eye_R"], b.eye_r, (-1, -0.25, 0.1))]
    return dict(model=tm, parts=[(body, 1.0, 0.82), (wings, 0.8, 0.18)], bones=b.bones(), tex=tex,
                anim=BirdAnim(b), eyes=eyes, warp=[(L["head"], 0.03 * b.s, 1.5)],
                meta={"walk_speed": WALK_SPEED[kind], "flight_wings": "upperarm_* scale 0.01 on ground clips"})
