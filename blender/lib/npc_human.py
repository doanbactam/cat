"""Parametric human NPCs (owner: creatures): body SDF, shared rig, modular garments,
hair and accessories, texture synthesis and the clip set.

Reference body: adult woman, 1.58 m, A-pose (arms 42 deg from vertical), facing -Y.
Every character = Spec(height, sex, mass, head, age ...) + garment/hair/accessory modules.
All characters share one skeleton layout ("Armature") with identical bone names; the kid
is the same rig at child proportions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from mathutils import Quaternion, Vector

import npc_anim as A
import npc_sdf as S
import npc_tex as X

REF_H = 1.58
ARM_ABD = 42.0          # A-pose arm abduction (deg from vertical)


@dataclass
class Spec:
    name: str
    height: float = 1.58
    sex: float = 0.0              # 0 female .. 1 male
    mass: float = 0.0             # -1 slim .. 1 heavy
    head: float = 1.0             # head scale relative to body scale
    kid: bool = False
    age: float = 0.4              # 0 young .. 1 very old (texture + posture)
    skin: str = "#c99a78"         # sRGB base skin tone
    lips: str = "#a4605a"
    hair_col: str = "#1b1714"
    eye_col: str = "#2a1a12"
    stoop: float = 0.0            # posture: 0 upright .. 1 strongly stooped
    gait: float = 1.0             # stride scale
    walk_speed: float = 1.25      # m/s the walk clip is authored for
    garments: list = field(default_factory=list)   # (fn_name, kwargs)
    hair: tuple = ("short", {})
    accessories: list = field(default_factory=list)
    seed: int = 1
    tex_size: int = 2048
    nrm_size: int = 1024
    tris: int = 16000
    beard: float = 0.0


# ---------------------------------------------------------------------------
# landmarks
# ---------------------------------------------------------------------------
class Body:
    """Landmarks and body primitives for one Spec. All points in Blender metres."""

    def __init__(self, spec: Spec):
        self.spec = spec
        sp = spec
        if sp.kid:
            self.s = sp.height / 1.30 * 0.823   # body scale relative to the ref woman
            self.hs = sp.head * 0.95 * (sp.height / 1.30)
            self.wx = 0.90
        else:
            self.s = sp.height / REF_H
            self.hs = sp.head * self.s * (1.0 - 0.03 * sp.sex)
            self.wx = 1.0
        s = self.s
        m = sp.mass
        sx = sp.sex
        # neck top (head pivot) of the reference
        self.neck_top_ref = np.array([0.0, 0.0, 1.405])
        self.legs_k = 1.0 if not sp.kid else 0.97
        # body landmarks (scaled) --------------------------------------
        L = {}
        L["hip_z"] = 0.830 * s * self.legs_k
        L["pelvis"] = self.b(0, 0.005, 0.86)
        L["hip_L"] = self.b(0.085 + 0.004 * m, 0.0, 0.83)
        L["knee_L"] = self.b(0.092, -0.012, 0.455)
        L["ankle_L"] = self.b(0.097, 0.012, 0.068)
        L["heel_L"] = self.b(0.097, 0.040, 0.034)
        L["ball_L"] = self.b(0.103, -0.125, 0.022)
        L["toe_L"] = self.b(0.106, -0.188, 0.018)
        sh_w = 0.160 + 0.022 * sx + 0.006 * m
        L["shoulder_L"] = self.b(sh_w, 0.004, 1.288)
        L["clav_L"] = self.b(0.022, -0.02, 1.30)
        L["neck_base"] = self.b(0, 0.012, 1.315)
        self.L = L
        # neck top in body-space then head points relative to it
        self.neck_top = self.b(0, -0.004, 1.405)
        # arm chain in A-pose
        ab = math.radians(ARM_ABD)
        ua = 0.292 * s
        fa = 0.235 * s
        d_ua = S.normalize((math.sin(ab), -0.06, -math.cos(ab)))
        d_fa = S.normalize(d_ua + np.array([0.0, -0.22, 0.0]))
        Sh = L["shoulder_L"]
        E = Sh + d_ua * ua
        W = E + d_fa * fa
        self.d_ua, self.d_fa = d_ua, d_fa
        L["elbow_L"] = E
        L["wrist_L"] = W
        # palm frame: axis along forearm, palm normal toward body/down, width ~ Y
        n_palm = -S.normalize(np.cross(d_fa, np.array([0.0, 1.0, 0.0])))
        w_axis = S.normalize(np.cross(n_palm, d_fa))     # points toward -Y (thumb side)
        if w_axis[1] > 0:
            w_axis = -w_axis
        self.n_palm, self.w_axis = n_palm, w_axis
        L["knuckle_L"] = W + d_fa * 0.095 * s
        L["fingertip_L"] = L["knuckle_L"] + d_fa * 0.075 * s + n_palm * 0.018 * s
        L["thumb_base_L"] = W + d_fa * 0.025 * s + w_axis * 0.028 * s + n_palm * 0.012 * s
        L["thumb_tip_L"] = L["thumb_base_L"] + S.normalize(d_fa + w_axis * 0.6 + n_palm * 0.5) * 0.062 * s
        for k in list(L.keys()):
            if k.endswith("_L"):
                v = L[k].copy()
                v[0] = -v[0]
                L[k[:-2] + "_R"] = v
        # head landmarks
        L["head_top"] = self.h(0, 0.0, 1.582)
        L["chin"] = self.h(0, -0.078, 1.383)
        L["eye_L"] = self.h(0.0315, -0.0705, 1.486)
        L["eye_R"] = self.h(-0.0315, -0.0705, 1.486)
        L["jaw_pivot"] = self.h(0, -0.004, 1.435)
        self.eye_r = 0.0118 * self.hs
        self.jaw_pts = []

    def b(self, x, y, z) -> np.ndarray:
        """Body point from reference coordinates."""
        s = self.s
        zz = z * s
        if self.spec.kid:
            # children: legs a bit shorter relative to the trunk
            zz = z * s * (0.97 if z < 0.86 else 1.0) + (0.0 if z < 0.86 else 0.86 * s * -0.03)
        return np.array([x * s * self.wx, y * s, zz])

    def h(self, x, y, z) -> np.ndarray:
        """Head point: scaled about the neck top with the head scale."""
        r = np.array([x, y, z]) - self.neck_top_ref
        return self.neck_top + r * self.hs

    # -----------------------------------------------------------------
    def bones(self):
        L = self.L
        s = self.s
        F = (0, -1, 0)
        hip_c = np.array([0, 0.0, (L["hip_L"][2])])
        z = lambda v: tuple(float(a) for a in v)  # noqa
        top_chest = L["neck_base"][2]
        sp0 = hip_c[2] + 0.06 * s
        sp1 = sp0 + (top_chest - sp0) * 0.30
        sp2 = sp0 + (top_chest - sp0) * 0.62
        bl = [
            ("root", (0, 0, 0), (0, 0.18 * s, 0), None, (0, 0, 1)),
            ("pelvis", z(hip_c), (0, 0, sp0), "root", F),
            ("spine_01", (0, 0, sp0), (0, 0.004, sp1), "pelvis", F),
            ("spine_02", (0, 0.004, sp1), (0, 0.008, sp2), "spine_01", F),
            ("chest", (0, 0.008, sp2), z(L["neck_base"]), "spine_02", F),
            ("neck", z(L["neck_base"]), z(self.neck_top), "chest", F),
            ("head", z(self.neck_top), z(L["head_top"]), "neck", F),
            ("jaw", z(L["jaw_pivot"]), z(L["chin"]), "head", (0, 0, -1)),
        ]
        for sd in ("L", "R"):
            sg = 1 if sd == "L" else -1
            bl += [
                (f"clavicle_{sd}", z(L[f"clav_{sd}"]), z(L[f"shoulder_{sd}"]), "chest", F),
                (f"upperarm_{sd}", z(L[f"shoulder_{sd}"]), z(L[f"elbow_{sd}"]), f"clavicle_{sd}", F),
                (f"forearm_{sd}", z(L[f"elbow_{sd}"]), z(L[f"wrist_{sd}"]), f"upperarm_{sd}", F),
                (f"hand_{sd}", z(L[f"wrist_{sd}"]), z(L[f"knuckle_{sd}"]), f"forearm_{sd}", F),
                (f"fingers_{sd}", z(L[f"knuckle_{sd}"]), z(L[f"fingertip_{sd}"]), f"hand_{sd}", F),
                (f"thumb_{sd}", z(L[f"thumb_base_{sd}"]), z(L[f"thumb_tip_{sd}"]), f"hand_{sd}", F),
                (f"thigh_{sd}", z(L[f"hip_{sd}"]), z(L[f"knee_{sd}"]), "pelvis", F),
                (f"shin_{sd}", z(L[f"knee_{sd}"]), z(L[f"ankle_{sd}"]), f"thigh_{sd}", F),
                (f"foot_{sd}", z(L[f"ankle_{sd}"]), z(L[f"ball_{sd}"]), f"shin_{sd}", (0, 0, 1)),
                (f"toe_{sd}", z(L[f"ball_{sd}"]), z(L[f"toe_{sd}"]), f"foot_{sd}", (0, 0, 1)),
            ]
            _ = sg
        return bl

    # -----------------------------------------------------------------
    def build_model(self) -> S.Model:
        sp = self.spec
        L = self.L
        s = self.s
        hs = self.hs
        m = sp.mass
        sx = sp.sex
        fem = 1.0 - sx
        M = S.Model(band=0.04)
        b, h = self.b, self.h
        ell = S.f_ellipsoid
        rc = S.f_round_cone
        wx = self.wx

        def add(fn, pts, bone, label="skin", k=0.02, soft=0.02, name="", pad=0.0):
            return M.add(fn, pts, bone, label, k, soft, name, pad)

        def E(c, r, bone, label="skin", k=0.02, soft=0.02, name="", R=None):
            r = np.asarray(r, np.float64)
            return add(ell(c, r, R), [c], bone, label, k, soft, name, pad=float(r.max()))

        def RC(a, bb, r1, r2, bone, label="skin", k=0.015, soft=0.015, name=""):
            return add(rc(a, bb, r1, r2), [a, bb], bone, label, k, soft, name, pad=max(r1, r2))

        mm = (1.0 + 0.18 * m) * (0.80 if sp.kid else 1.0)
        # ---- torso -------------------------------------------------------
        E(b(0, 0.006, 0.875), np.array([(0.140 + 0.018 * fem) * mm * wx, 0.098 * mm, 0.108]) * s, "pelvis", k=0.04,
          name="pelvis")
        for sd in (1, -1):
            E(b(0.068 * sd, 0.058, 0.835), np.array([0.075 * wx, 0.07, 0.085]) * s * (1 + 0.1 * fem) * mm,
              {"pelvis": 0.6, f"thigh_{'L' if sd > 0 else 'R'}": 0.4}, k=0.04, name="glute")
        E(b(0, 0.0, 0.985), np.array([(0.118 + 0.012 * sx) * wx * (1 + 0.25 * m), 0.084 * (1 + 0.35 * m), 0.11]) * s,
          {"spine_01": 0.7, "pelvis": 0.3}, k=0.05, name="waist")
        if m > 0 or sp.age > 0.6:
            E(b(0, -0.028 - 0.02 * m, 0.955), np.array([0.105 * wx, 0.07 + 0.03 * m, 0.085]) * s,
              {"spine_01": 0.6, "pelvis": 0.4}, k=0.05, name="belly")
        E(b(0, 0.008, 1.150), np.array([(0.128 + 0.02 * sx) * wx * (1 + 0.08 * m), 0.092 * (1 + 0.1 * m), 0.15]) * s,
          {"spine_02": 0.55, "chest": 0.45}, k=0.05, name="ribcage")
        E(b(0, 0.016, 1.245), np.array([(0.115 + 0.025 * sx) * wx, 0.075, 0.07]) * s, "chest", k=0.05,
          name="upper_chest")
        if fem > 0.5 and not sp.kid:
            for sd in (1, -1):
                E(b(0.054 * sd, -0.062, 1.148), np.array([0.052, 0.045, 0.05]) * s * (1 + 0.1 * m), "chest",
                  k=0.03, name="breast")
        for sd, nm in ((1, "L"), (-1, "R")):
            # trapezius / shoulder mass
            RC(b(0.035 * sd, 0.018, 1.33), L[f"shoulder_{nm}"] + np.array([0, 0.006, 0.02]) * s,
               0.038 * s, 0.044 * s, {"chest": 0.6, f"clavicle_{nm}": 0.4}, k=0.03, soft=0.02, name="trap")
            # deltoid
            E(L[f"shoulder_{nm}"] + np.array([0.012 * sd, -0.004, -0.01]) * s,
              np.array([0.052, 0.055, 0.06]) * s * (1 + 0.1 * sx), {f"upperarm_{nm}": 0.7, f"clavicle_{nm}": 0.3},
              k=0.03, soft=0.02, name="deltoid")
        # ---- neck -------------------------------------------------------
        RC(b(0, 0.015, 1.30), self.neck_top + np.array([0, 0.004, -0.01]) * s,
           0.056 * s * (1 + 0.15 * sx + 0.1 * m), (0.047 + 0.006 * sx) * hs, {"neck": 1.0}, k=0.035, soft=0.02,
           name="neck")
        # ---- head -------------------------------------------------------
        self._head(M, add)
        # ---- arms -------------------------------------------------------
        for sd, nm in ((1, "L"), (-1, "R")):
            Sh, El, Wr = L[f"shoulder_{nm}"], L[f"elbow_{nm}"], L[f"wrist_{nm}"]
            RC(Sh, El, 0.046 * s * mm * (1 + 0.1 * sx), 0.034 * s * mm, f"upperarm_{nm}", k=0.02, soft=0.018,
               name="upperarm")
            E(Sh + (El - Sh) * 0.45 + np.array([0, 0.006, 0]) * s, np.array([0.042, 0.045, 0.085]) * s * mm,
              f"upperarm_{nm}", k=0.02, soft=0.015, name="biceps",
              R=S.frame(El - Sh, (1, 0, 0))[:, [0, 2, 1]])
            RC(El, Wr, 0.035 * s * mm, 0.024 * s, f"forearm_{nm}", k=0.02, soft=0.015, name="forearm")
            E(El + (Wr - El) * 0.25, np.array([0.038, 0.034, 0.075]) * s * mm, f"forearm_{nm}", k=0.02, soft=0.015,
              name="forearm_m", R=S.frame(Wr - El, (1, 0, 0))[:, [0, 2, 1]])
            self._hand(M, add, nm)
        # ---- legs -------------------------------------------------------
        for sd, nm in ((1, "L"), (-1, "R")):
            Hp, K, An = L[f"hip_{nm}"], L[f"knee_{nm}"], L[f"ankle_{nm}"]
            RC(Hp + np.array([0.004 * sd, 0, 0.02]) * s, K, (0.083 + 0.012 * fem) * s * mm, 0.050 * s * mm,
               f"thigh_{nm}", k=0.045, soft=0.02, name="thigh")
            E(K + np.array([0.0, -0.022, 0.005]) * s, np.array([0.03, 0.022, 0.032]) * s, {f"thigh_{nm}": 0.5,
              f"shin_{nm}": 0.5}, k=0.02, soft=0.012, name="kneecap")
            RC(K, An, 0.046 * s * mm, 0.029 * s, f"shin_{nm}", k=0.02, soft=0.015, name="shin")
            E(K + (An - K) * 0.28 + np.array([0.0, 0.018, 0]) * s, np.array([0.043, 0.048, 0.10]) * s * mm,
              f"shin_{nm}", k=0.03, soft=0.012, name="calf")
            self._foot(M, add, nm)
        self.model = M
        return M

    def _head(self, M, add):
        h = self.h
        hs = self.hs
        sx = self.spec.sex
        ell = S.f_ellipsoid
        H = "head"
        J = "jaw"

        def E(c, r, bone=H, label="skin", k=0.02, soft=0.01, R=None, name=""):
            r = np.asarray(r, np.float64) * hs
            return add(ell(c, r, R), [c], bone, label, k, soft, name, pad=float(r.max()))

        jw = 1.0 + 0.10 * sx
        rng = np.random.default_rng(self.spec.seed)
        fv = lambda a: 1.0 + rng.uniform(-a, a)  # noqa: E731  per-character facial variation
        nose_w, nose_l, cheek, lip, chin_f, face_l = fv(0.12), fv(0.10), fv(0.15), fv(0.12), fv(0.12), fv(0.05)
        jw *= fv(0.06)
        E(h(0, 0.014, 1.492), [0.0715, 0.091, 0.090], k=0.03, name="cranium")
        E(h(0, -0.020, 1.462), [0.060 * jw ** 0.5, 0.064, 0.056 * face_l], k=0.03, name="face")
        E(h(0, -0.046, 1.514), [0.056, 0.032, 0.036], k=0.025, name="forehead")
        for sd in (1, -1):
            E(h(0.036 * sd, -0.052, 1.454), np.array([0.024, 0.022, 0.022]) * cheek, k=0.035, name="cheek")
            add(S.f_round_cone(h(0.052 * sd * jw, -0.004, 1.432), h(0.016 * sd * jw, -0.064, 1.392), 0.016 * hs * jw,
                               0.011 * hs), [h(0.052 * sd, -0.004, 1.432), h(0.016 * sd, -0.064, 1.392)],
                {J: 0.8, H: 0.2}, "skin", 0.045, 0.01, "jaw", pad=0.02)
        E(h(0, -0.063, 1.396), [0.018 * jw, 0.014 * chin_f, 0.016], J, k=0.03, name="chin")
        E(h(0, -0.059, 1.424), [0.032, 0.024, 0.026], H, k=0.035, name="muzzle")
        # brow ridge
        add(S.f_capsule(h(-0.036, -0.068, 1.505), h(0.036, -0.068, 1.505), 0.0075 * hs),
            [h(-0.036, -0.068, 1.505), h(0.036, -0.068, 1.505)], H, "skin", 0.016, 0.01, "brow", pad=0.01)
        # nose (broad, low bridge, soft)
        add(S.f_round_cone(h(0, -0.077, 1.478), h(0, -0.077 - 0.017 * nose_l, 1.447), 0.0058 * hs, 0.0102 * hs * nose_w),
            [h(0, -0.077, 1.478), h(0, -0.094, 1.447)], H, "skin", 0.010, 0.008, "nose", pad=0.012)
        for sd in (1, -1):
            E(h(0.0128 * sd * nose_w, -0.083, 1.442), [0.0078 * nose_w, 0.0078, 0.0068], k=0.008, name="ala")
        # lips
        E(h(0, -0.0828, 1.4215), [0.0190 * lip, 0.0072, 0.0050 * lip], H, "lips", k=0.006, name="lip_up")
        E(h(0, -0.0805, 1.4090), [0.0170 * lip, 0.0075, 0.0054 * lip], J, "lips", k=0.006, name="lip_low")
        E(h(0, -0.080, 1.431), [0.012, 0.006, 0.007], H, "skin", k=0.008, name="philtrum")
        # ears
        for sd in (1, -1):
            R = S.rot((0, 0, 1), 18 * sd) @ S.rot((1, 0, 0), -12)
            E(h(0.0705 * sd, 0.012, 1.474), [0.009, 0.019, 0.031], k=0.006, R=R, name="ear")
        # eyelids: shell around each eyeball, with an almond aperture carved through
        r = self.eye_r
        for sd, nm in ((1, "L"), (-1, "R")):
            c = self.L[f"eye_{nm}"]
            add(S.f_sphere(c, r + 0.0016 * hs), [c], H, "skin", 0.006, 0.008, "lid", pad=r + 0.002)
            M.carve(self._aperture(c, sd), [c], k=0.0015, pad=0.03)
            # socket under the brow so the lid is not a bump
        # neck/jaw underside fill
        E(h(0, -0.025, 1.395), [0.048, 0.045, 0.03], {J: 0.4, "neck": 0.3, H: 0.3}, k=0.035, name="submandible")

    def _aperture(self, c, sd):
        """Almond eye opening (lens shape) extruded forward from the eye centre."""
        hs = self.hs
        w = 0.0145 * hs        # half width
        a = 0.0050 * hs        # half height
        Rr = (w * w + a * a) / (2 * a)
        cc = Rr - a
        tilt = math.radians(4.0) * sd
        ca, sa = math.cos(tilt), math.sin(tilt)
        c = np.asarray(c)

        def f(p):
            q = p - c
            # local: u = x (outward), v = z (up), depth = -y (forward)
            u = q[:, 0] * ca + q[:, 2] * sa * -1
            v = q[:, 2] * ca + q[:, 0] * sa
            u = u - 0.0012 * hs * sd           # outer corner slightly lower/longer
            d1 = np.sqrt(u * u + (v + cc) ** 2) - Rr
            d2 = np.sqrt(u * u + (v - cc) ** 2) - Rr
            d2d = np.maximum(d1, d2)
            depth = -q[:, 1]
            return np.maximum(d2d, -(depth + 0.002 * hs))
        return f

    def _hand(self, M, add, nm):
        L = self.L
        s = self.s
        sd = 1 if nm == "L" else -1
        W, Kn = L[f"wrist_{nm}"], L[f"knuckle_{nm}"]
        d = self.d_fa.copy()
        n = self.n_palm.copy()
        w = self.w_axis.copy()
        if sd < 0:
            d[0], n[0], w[0] = -d[0], -n[0], -w[0]
        R = np.stack([w, d, n], 1)    # columns: width, length, thickness
        pc = W + d * 0.05 * s
        add(S.f_ellipsoid(pc, np.array([0.040, 0.055, 0.015]) * s, R), [pc], f"hand_{nm}", "skin", 0.012, 0.012,
            "palm", pad=0.06 * s)
        offs = [-0.024, -0.008, 0.008, 0.022]
        lens = [0.068, 0.077, 0.072, 0.058]
        rads = [0.0088, 0.0090, 0.0085, 0.0075]
        for o, ln, rr in zip(offs, lens, rads):
            base = Kn + w * o * s * -1 - d * 0.008 * s
            mid = base + (d * 0.95 + n * 0.25) * ln * 0.55 * s + w * o * 0.15 * s * -1
            tip = mid + S.normalize(d * 0.8 + n * 0.6) * ln * 0.45 * s
            add(S.f_round_cone(base, mid, rr * s, rr * 0.92 * s), [base, mid], {f"fingers_{nm}": 0.6, f"hand_{nm}": 0.4},
                "skin", 0.004, 0.008, "finger", pad=0.01)
            add(S.f_round_cone(mid, tip, rr * 0.92 * s, rr * 0.80 * s), [mid, tip], f"fingers_{nm}", "skin", 0.003,
                0.008, "finger_tip", pad=0.01)
        tb, tt = L[f"thumb_base_{nm}"], L[f"thumb_tip_{nm}"]
        add(S.f_round_cone(tb, tt, 0.0125 * s, 0.0085 * s), [tb, tt], f"thumb_{nm}", "skin", 0.010, 0.008, "thumb",
            pad=0.012)

    def _foot(self, M, add, nm):
        L = self.L
        s = self.s
        An, He, Ba, To = L[f"ankle_{nm}"], L[f"heel_{nm}"], L[f"ball_{nm}"], L[f"toe_{nm}"]
        add(S.f_sphere(He, 0.034 * s), [He], f"foot_{nm}", "skin", 0.02, 0.012, "heel", pad=0.035 * s)
        add(S.f_flat_cone(He + np.array([0, -0.01, 0.012]) * s, Ba + np.array([0, 0, 0.004]) * s, 0.034 * s,
                          0.026 * s, 0.62, (0, 0, 1)), [He, Ba], f"foot_{nm}", "skin", 0.02, 0.012, "foot", pad=0.04 * s)
        add(S.f_round_cone(An + np.array([0, 0.004, 0.0]) * s, He + np.array([0, -0.01, 0.01]) * s, 0.03 * s, 0.03 * s),
            [An, He], f"foot_{nm}", "skin", 0.02, 0.012, "ankle", pad=0.035 * s)
        add(S.f_flat_cone(Ba + np.array([0, 0.005, 0.002]) * s, To + np.array([0, 0, 0.002]) * s, 0.026 * s, 0.017 * s,
                          0.55, (0, 0, 1)), [Ba, To], f"toe_{nm}", "skin", 0.012, 0.01, "toes", pad=0.03 * s)


# ---------------------------------------------------------------------------
# garments (each adds a Layer)
# ---------------------------------------------------------------------------
def _named(M: S.Model, names):
    return [p for p in M.prims if p.name in names]


def _offset_layer(M, label, names, t, k_extra=0.0, side=None):
    """Garment layer from offset copies of the named body prims."""
    L = M.layer(label)
    for p in _named(M, names):
        if side is not None:
            if p.c[0] * side < -0.02:
                continue
        L.prims.append(S.Prim(S.f_offset(p.fn, t), p.c, p.r + t, p.bone, label, p.k + k_extra, p.soft, p.name))
    return L


def _cut(L, point, normal, c, r, k=0.004):
    """Remove the part of the layer on the -normal side of the plane, limited to sphere (c, r)."""
    pl = S.f_plane(point, normal)
    sph = S.f_sphere(c, r)
    L.carves.append(S.Carve(lambda p: np.maximum(pl(p), sph(p)), np.asarray(c, np.float64), r, k))


def _panel_r(body: Body, t=0.01, loose=0.01):
    sp = body.spec
    mm = (1.0 + 0.18 * sp.mass) * (0.80 if sp.kid else 1.0)
    return (0.150 + 0.022 * (1 - sp.sex)) * body.s * mm * body.wx + t + loose + 0.012


def g_top(body: Body, label="top", sleeve=0.55, hem=0.80, t=0.010, loose=0.006, collar=None, tuck=False):
    """Shirt / blouse. sleeve: 0 = sleeveless .. 1 = to the wrist (fraction of the arm).
    hem: hem height in reference metres (0.80 = hip, 0.95 = tucked waist)."""
    M = body.model
    L = body.L
    s = body.s
    torso = ["pelvis", "glute", "waist", "belly", "ribcage", "upper_chest", "breast", "trap", "deltoid", "neck"]
    lay = _offset_layer(M, label, torso + ["upperarm", "biceps", "forearm", "forearm_m"], t, loose)
    lay.hems = []
    # lower panel hanging from the ribcage to the hem (covers the trouser waistband)
    zr = body.b(0, 0, 1.12)
    zh = body.b(0, 0, hem - 0.02)
    hip_r = _panel_r(body, t, loose)
    panel = S.f_round_cone(np.array([0, 0.004, zr[2]]), np.array([0, 0.004, zh[2]]), 0.135 * s * body.wx + t, hip_r)
    sq = np.array([1.0, 1.22, 1.0])
    pc = np.array([0, 0.004, 0])
    if hem < 0.9:
        lay.prims.append(S.Prim(lambda p: panel((p - pc) * sq + pc) / 1.16, np.array([0, 0, (zr[2] + zh[2]) / 2]),
                                (zr[2] - zh[2]) / 2 + 0.25, {"pelvis": 0.45, "spine_01": 0.35, "spine_02": 0.2}, label,
                                0.05, 0.05, "panel"))
    # neckline: remove the neck above the collar line
    nb = L["neck_base"]
    _cut(lay, nb + np.array([0, -0.02, 0.022]) * s, (0, 0.35, -1), nb, 0.11 * s, k=0.006)
    # hem
    zc = body.b(0, 0, hem)[2]
    _cut(lay, (0, 0, zc), (0, 0, 1), (0, 0, zc - 0.5), 0.5, k=0.004)
    lay.hems.append(("z", zc))
    # sleeves
    for nm in ("L", "R"):
        Sh, El, Wr = L[f"shoulder_{nm}"], L[f"elbow_{nm}"], L[f"wrist_{nm}"]
        arm_len = np.linalg.norm(El - Sh) + np.linalg.norm(Wr - El)
        dist = max(sleeve, 0.08) * arm_len
        if dist <= np.linalg.norm(El - Sh):
            p = Sh + S.normalize(El - Sh) * dist
            nrm = -S.normalize(El - Sh)
        else:
            p = El + S.normalize(Wr - El) * (dist - np.linalg.norm(El - Sh))
            nrm = -S.normalize(Wr - El)
        _cut(lay, p, nrm, p + (-nrm) * 0.25, 0.27, k=0.004)
        lay.hems.append(("pt", p, nrm))
    if collar == "polo":
        nb2 = nb + np.array([0, -0.004, 0.018]) * s
        c = S.f_torus(nb2, 0.062 * s, 0.009 * s, axis=(0, 0.25, 1))
        lay.prims.append(S.Prim(c, nb2, 0.075 * s, {"neck": 0.5, "chest": 0.5}, label + "_trim", 0.006, 0.02, "collar"))
    if collar == "mandarin":
        nb2 = nb + np.array([0, -0.006, 0.03]) * s
        c = S.f_shell(S.f_cyl(nb2 - np.array([0, 0, 0.012]) * s, nb2 + np.array([0, 0, 0.012]) * s, 0.06 * s), 0.003)
        lay.prims.append(S.Prim(c, nb2, 0.075 * s, {"neck": 0.6, "chest": 0.4}, label + "_trim", 0.004, 0.02, "collar"))
    return lay


def g_bottom(body: Body, label="bottom", length=1.0, t=0.008, loose=0.01, flare=0.0, waist=0.98):
    """Trousers (length 1 = ankle, 0.5 = knee shorts)."""
    M = body.model
    L = body.L
    s = body.s
    names = ["pelvis", "glute", "waist", "belly", "thigh", "kneecap", "shin", "calf"]
    lay = _offset_layer(M, label, names, t, loose)
    lay.hems = []
    if flare > 0:
        for nm in ("L", "R"):
            K, An = L[f"knee_{nm}"], L[f"ankle_{nm}"]
            lay.prims.append(S.Prim(S.f_round_cone(K, An + np.array([0, 0, 0.01]), 0.058 * s, (0.058 + flare) * s),
                                    (K + An) / 2, np.linalg.norm(K - An) / 2 + 0.1, f"shin_{nm}", label, 0.03, 0.015,
                                    "flare"))
    zc = body.b(0, 0, waist)[2]
    _cut(lay, (0, 0, zc), (0, 0, -1), (0, 0, zc + 0.5), 0.5, k=0.004)
    for nm in ("L", "R"):
        Hp, K, An = L[f"hip_{nm}"], L[f"knee_{nm}"], L[f"ankle_{nm}"]
        leg = np.linalg.norm(K - Hp) + np.linalg.norm(An - K)
        dist = length * leg
        if dist <= np.linalg.norm(K - Hp):
            p = Hp + S.normalize(K - Hp) * dist
            nrm = -S.normalize(K - Hp)
        else:
            p = K + S.normalize(An - K) * min(dist - np.linalg.norm(K - Hp), np.linalg.norm(An - K) - 0.004)
            nrm = -S.normalize(An - K)
        _cut(lay, p, nrm, p - nrm * 0.25, 0.27, k=0.003)
        lay.hems.append(("pt", p, nrm))
    lay.hems.append(("z", zc))
    return lay


def g_skirt_wrap(body: Body, label="skirt", top=0.98, bottom=0.30, t=0.03):
    """Wrap sun-skirt (váy chống nắng) over trousers: a cone from waist to shin."""
    M = body.model
    s = body.s
    lay = M.layer(label)
    lay.hems = []
    zt = body.b(0, 0, top)[2]
    zb = body.b(0, 0, bottom)[2]
    a = np.array([0, 0.004, zt])
    bb = np.array([0, 0.004, zb])
    fn = S.f_round_cone(a, bb, 0.135 * s * body.wx, 0.20 * s)
    sq = np.array([1.0, 1.25, 1.0])
    f2 = lambda p: fn((p - a) * sq + a) / 1.12  # noqa: E731  (flattened front-back)
    lay.prims.append(S.Prim(f2, (a + bb) / 2, (zt - zb) / 2 + 0.25, {"pelvis": 0.5, "thigh_L": 0.25, "thigh_R": 0.25},
                            label, 0.02, 0.06, "skirt"))
    _cut(lay, (0, 0, zt), (0, 0, -1), (0, 0, zt + 0.4), 0.4)
    _cut(lay, (0, 0, zb), (0, 0, 1), (0, 0, zb - 0.4), 0.4)
    lay.hems.append(("z", zb))
    return lay


def g_apron(body: Body, label="apron", top=1.20, bottom=0.50, t=0.022):
    """Fishmonger's plastic apron: bib following the chest + a curved sheet hanging from the
    waist to below the knee in front of the legs, neck strap."""
    M = body.model
    s = body.s
    lay = M.layer(label, priority=0.003)
    lay.hems = []
    zt, zb = body.b(0, 0, top)[2], body.b(0, 0, bottom)[2]
    zw = body.b(0, 0, 0.98)[2]
    for p in _named(M, ["ribcage", "breast", "upper_chest", "waist", "belly"]):
        lay.prims.append(S.Prim(S.f_offset(p.fn, t + 0.012), p.c, p.r + t, p.bone, label, p.k + 0.03, p.soft * 2,
                                p.name))
    # skirt sheet: section of a vertical cylinder just in front of the blouse panel / thighs
    pr = _panel_r(body, 0.011, 0.01)
    R = 0.30 * s
    cy = R - pr / 1.22 - 0.014
    zcut = zw + 0.01
    shell = lambda p: np.maximum(np.abs(np.sqrt(p[:, 0] ** 2 + (p[:, 1] - cy) ** 2) - R) - 0.005,  # noqa: E731
                                 p[:, 2] - zcut)
    lay.prims.append(S.Prim(shell, np.array([0, -0.1 * s, (zb + zw) / 2]), (zw - zb) / 2 + 0.2,
                            {"pelvis": 0.6, "thigh_L": 0.2, "thigh_R": 0.2}, label, 0.02, 0.05, "sheet"))
    # front only, between top and bottom, width limited
    big = np.array([0, 0, 0.8])
    lay.carves.append(S.Carve(S.f_plane((0, -0.03 * s, 0), (0, -1, 0)), big, 3.0, 0.006))
    lay.carves.append(S.Carve(S.f_plane((0, 0, zt), (0, 0, -1)), big, 3.0, 0.006))
    lay.carves.append(S.Carve(S.f_plane((0, 0, zb), (0, 0, 1)), big, 3.0, 0.004))
    for sd in (1, -1):
        lay.carves.append(S.Carve(S.f_plane((0.165 * s * sd, 0, 0), (-sd, 0, 0)), big, 3.0, 0.006))
    # neck strap
    nb = body.L["neck_base"]
    for sd in (1, -1):
        a = np.array([0.085 * s * sd, -0.07 * s, zt - 0.005])
        bb = nb + np.array([0.055 * sd, -0.01, 0.0]) * s
        lay.prims.append(S.Prim(S.f_capsule(a, bb, 0.006), (a + bb) / 2, 0.15, {"chest": 1.0}, label, 0.004, 0.02,
                                "strap"))
    lay.hems.append(("z", zb))
    return lay


def g_footwear(body: Body, kind="sandal", label="shoes", boot_height=0.40):
    M = body.model
    L = body.L
    s = body.s
    names = ["heel", "foot", "toes", "ankle"]
    if kind == "boots":
        lay = _offset_layer(M, label, names + ["shin", "calf"], 0.010, 0.01)
        lay.hems = []
        for nm in ("L", "R"):
            z = body.b(0, 0, boot_height)[2]
            lay.prims.append(S.Prim(S.f_round_cone(L[f"ankle_{nm}"] + np.array([0, 0, 0.02]),
                                                   L[f"ankle_{nm}"] * np.array([1, 1, 0]) + np.array([0, 0.005, z]),
                                                   0.048 * s, 0.062 * s),
                                    L[f"ankle_{nm}"] + np.array([0, 0, 0.15]), 0.3, f"shin_{nm}", label, 0.02, 0.015,
                                    "shaft"))
        zc = body.b(0, 0, boot_height)[2]
        _cut(lay, (0, 0, zc), (0, 0, -1), (0, 0, zc + 0.5), 0.5, k=0.004)
        lay.hems.append(("z", zc))
        return lay
    if kind == "shoes":
        lay = _offset_layer(M, label, names, 0.009, 0.004)
        lay.hems = []
        zc = body.b(0, 0, 0.085)[2]
        _cut(lay, (0, 0, zc), (0, 0.45, -1), (0, 0, zc + 0.5), 0.5, k=0.004)
        # sole rim
        for nm in ("L", "R"):
            He, To = L[f"heel_{nm}"], L[f"toe_{nm}"]
            a = He * np.array([1, 1, 0]) + np.array([0, 0.012, 0.012])
            bb = To * np.array([1, 1, 0]) + np.array([0, -0.012, 0.012])
            lay.prims.append(S.Prim(S.f_flat_cone(a, bb, 0.042 * s, 0.036 * s, 0.32, (0, 0, 1)), (a + bb) / 2, 0.16,
                                    {f"foot_{nm}": 0.7, f"toe_{nm}": 0.3}, label + "_sole", 0.006, 0.012, "sole"))
        lay.hems.append(("z", zc))
        return lay
    # sandals / flip-flops: sole slab + straps
    lay = M.layer(label, priority=0.002)
    lay.hems = []
    for nm in ("L", "R"):
        He, To, Ba = L[f"heel_{nm}"], L[f"toe_{nm}"], L[f"ball_{nm}"]
        a = He * np.array([1, 1, 0]) + np.array([0, 0.008, 0.008])
        bb = To * np.array([1, 1, 0]) + np.array([0, -0.014, 0.008])
        lay.prims.append(S.Prim(S.f_flat_cone(a, bb, 0.040 * s, 0.040 * s, 0.22, (0, 0, 1)), (a + bb) / 2, 0.16,
                                {f"foot_{nm}": 0.75, f"toe_{nm}": 0.25}, label + "_sole", 0.004, 0.012, "sole"))
        # straps: a band over the instep (sandal) or a V thong (flip-flop)
        if kind == "flipflop":
            toe_gap = Ba + np.array([0.0, -0.02, 0.004])
            for sg in (1, -1):
                side = Ba + np.array([0.035 * sg, 0.03, 0.006])
                top = Ba + np.array([0.0, 0.0, 0.03 * s])
                lay.prims.append(S.Prim(S.f_capsule(toe_gap, top + (side - top) * 0.5 + np.array([0, 0, 0.0]), 0.0045),
                                        Ba, 0.08, f"foot_{nm}", label + "_strap", 0.003, 0.01, "strap"))
        else:
            ctr = (Ba + He) / 2 + np.array([0, -0.01, 0.0])
            tor = S.f_torus(ctr + np.array([0, 0, 0.012]), 0.043 * s, 0.006, axis=(0, 1, 0.15))
            lay.prims.append(S.Prim(tor, ctr, 0.08, f"foot_{nm}", label + "_strap", 0.003, 0.01, "strap"))
            ank = He + np.array([0, 0.002, 0.03])
            tor2 = S.f_torus(ank, 0.036 * s, 0.005, axis=(0, 0.6, 1))
            lay.prims.append(S.Prim(tor2, ank, 0.07, f"foot_{nm}", label + "_strap", 0.003, 0.01, "strap"))
    return lay


def g_scarf(body: Body, label="scarf"):
    """Red neck-scarf of the school uniform (khăn quàng): band round the collar + knot."""
    M = body.model
    s = body.s
    nb = body.L["neck_base"] + np.array([0, -0.006, 0.014]) * s
    lay = M.layer(label, priority=0.003)
    lay.hems = []
    lay.prims.append(S.Prim(S.f_torus(nb, 0.070 * s, 0.013 * s, axis=(0, 0.35, 1)), nb, 0.1, {"chest": 0.6, "neck": 0.4},
                            label, 0.008, 0.02, "band"))
    knot = nb + np.array([0, -0.100, -0.045]) * s
    lay.prims.append(S.Prim(S.f_ellipsoid(knot, np.array([0.02, 0.014, 0.017]) * s), knot, 0.03, "chest", label, 0.012,
                            0.01, "knot"))
    for sg in (1, -1):
        tail_end = knot + np.array([0.045 * sg, -0.022, -0.13]) * s
        lay.prims.append(S.Prim(S.f_flat_cone(knot, tail_end, 0.014 * s, 0.026 * s, 0.22, (1, 0.0, 0)),
                                (knot + tail_end) / 2, 0.1, "chest", label, 0.006, 0.01, "tail"))
    return lay


def g_mask(body: Body, label="mask"):
    """Cloth face mask (sun protection) over nose + mouth."""
    M = body.model
    lay = _offset_layer(M, label, ["face", "chin", "jaw", "cheek", "nose", "ala", "lip_up", "lip_low", "philtrum", "muzzle",
                                   "submandible"], 0.004, 0.012)
    lay.hems = []
    h = body.h
    p_top = h(0, -0.09, 1.468)
    lay.carves.append(S.Carve(S.f_plane(p_top, (0, 0.25, -1)), p_top, 0.25, 0.004))
    lay.carves.append(S.Carve(S.f_plane(h(0, -0.01, 0), (0, -1, 0)), h(0, 0.2, 1.45), 0.2, 0.006))
    lay.hems.append(("pt", p_top, np.array([0, -0.25, 1.0])))
    return lay


def g_backpack(body: Body, label="backpack"):
    M = body.model
    s = body.s
    lay = M.layer(label, priority=0.003)
    lay.hems = []
    c = body.b(0, 0.155, 1.08)
    lay.prims.append(S.Prim(S.f_box(c, np.array([0.135, 0.065, 0.19]) * s, None, 0.035 * s), c, 0.3,
                            {"spine_02": 0.5, "chest": 0.5}, label, 0.01, 0.05, "bag"))
    pc = body.b(0, 0.215, 0.99)
    lay.prims.append(S.Prim(S.f_box(pc, np.array([0.10, 0.03, 0.07]) * s, None, 0.02 * s), pc, 0.15,
                            {"spine_02": 0.6, "chest": 0.4}, label, 0.006, 0.05, "pocket"))
    for sd in (1, -1):
        a = body.b(0.075 * sd, 0.10, 1.27)
        m1 = body.b(0.10 * sd, -0.07, 1.22)
        e = body.b(0.11 * sd, -0.035, 0.98)
        e2 = body.b(0.12 * sd, 0.10, 0.93)
        for p0, p1 in ((a, m1), (m1, e), (e, e2)):
            lay.prims.append(S.Prim(S.f_flat_cone(p0, p1, 0.016 * s, 0.016 * s, 0.35, (0, 1, 0) if p0 is not e else (1, 0, 0)),
                                    (p0 + p1) / 2, 0.2, {"chest": 0.7, "spine_02": 0.3}, label + "_strap", 0.004, 0.02,
                                    "strap"))
    return lay


# ---------------------------------------------------------------------------
# hair
# ---------------------------------------------------------------------------
def hair(body: Body, style="short", label="hair"):
    M = body.model
    h = body.h
    hs = body.hs
    cran = _named(M, ["cranium", "forehead"])
    lay = M.layer(label, priority=0.002)
    lay.hems = []
    thick = {"short": 0.007, "kid": 0.008, "bun": 0.009, "ponytail": 0.010, "perm": 0.016, "thin": 0.004,
             "side_part": 0.010, "under_hat": 0.006}[style] * hs
    # hairline: plane from forehead to nape
    front = h(0, -0.083, 1.528 if style not in ("perm",) else 1.522)
    nape = h(0, 0.095, 1.415 if style not in ("short", "thin", "side_part") else 1.428)
    if style == "perm":
        nape = h(0, 0.095, 1.40)
    dvec = nape - front
    nrm = np.array([0.0, -dvec[2], dvec[1]])
    nrm = nrm if nrm[2] > 0 else -nrm
    pl = S.f_plane(front, nrm)
    ramp = 0.03 * hs
    for p in cran:
        fn = (lambda f: (lambda q: f(q) - thick * np.clip(pl(q) / ramp, 0.12, 1.0)))(p.fn)
        lay.prims.append(S.Prim(fn, p.c, p.r + thick, "head", label, p.k, 0.02, p.name))
    lay.carves.append(S.Carve(pl, h(0, 0, 1.40), 0.2, 0.008 * hs))
    # around the ears
    for sd in (1, -1):
        ec = h(0.071 * sd, 0.008, 1.468)
        lay.carves.append(S.Carve(S.f_sphere(ec, 0.026 * hs), ec, 0.027 * hs, 0.006 * hs))
        # temples
        tc = h(0.066 * sd, -0.07, 1.47)
        lay.carves.append(S.Carve(S.f_sphere(tc, 0.03 * hs), tc, 0.031 * hs, 0.01 * hs))
    if style == "bun":
        bc = h(0, 0.108, 1.505)
        lay.prims.append(S.Prim(S.f_ellipsoid(bc, np.array([0.036, 0.028, 0.032]) * hs), bc, 0.04 * hs, "head", label,
                                0.012, 0.02, "bun"))
    if style == "ponytail":
        tb = h(0, 0.098, 1.50)
        te = h(0, 0.13, 1.33)
        lay.prims.append(S.Prim(S.f_flat_cone(tb, te, 0.022 * hs, 0.012 * hs, 0.7, (1, 0, 0)), (tb + te) / 2, 0.12 * hs,
                                {"head": 0.7, "neck": 0.3}, label, 0.012, 0.03, "tail"))
        tie = h(0, 0.105, 1.485)
        lay.prims.append(S.Prim(S.f_torus(tie, 0.015 * hs, 0.004, axis=(0, 0.35, -1)), tie, 0.03, "head",
                                label + "_tie", 0.002, 0.01, "tie"))
    if style == "perm":
        for i in range(14):
            a = i / 14 * 2 * math.pi
            c = h(0.07 * math.cos(a), 0.01 + 0.085 * math.sin(a), 1.52 + 0.012 * math.sin(3 * a))
            lay.prims.append(S.Prim(S.f_sphere(c, 0.024 * hs), c, 0.025 * hs, "head", label, 0.02, 0.02, "curl"))
    if style == "kid":
        c = h(0, -0.062, 1.535)
        lay.prims.append(S.Prim(S.f_ellipsoid(c, np.array([0.05, 0.03, 0.02]) * hs, S.rot((1, 0, 0), -25)), c,
                                0.06 * hs, "head", label, 0.012, 0.02, "fringe"))
    if style == "side_part":
        c = h(0.02, -0.04, 1.565)
        lay.prims.append(S.Prim(S.f_ellipsoid(c, np.array([0.06, 0.05, 0.022]) * hs), c, 0.06 * hs, "head", label, 0.02,
                                0.02, "quiff"))
    lay.hair_style = style
    return lay


# ---------------------------------------------------------------------------
# rigid accessories (unioned into the skin mesh, rigidly weighted to one bone)
# ---------------------------------------------------------------------------
def acc_nonla(body: Body, label="nonla"):
    """Conical palm-leaf hat: apex ~ 0.17 m above the crown, 0.44 m diameter."""
    M = body.model
    h = body.h
    hs = body.hs
    top = body.L["head_top"]
    apex = top + np.array([0, 0.004, 0.155]) * hs
    rim_z = top[2] - 0.052 * hs
    R = 0.215 * hs
    tilt = S.rot((1, 0, 0), -6)      # pushed back a little
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    a2 = np.array([0.0, apex[2] - rim_z])
    seg = np.array([R, -(apex[2] - rim_z)])
    L2 = float(seg @ seg)

    def cone(p):
        q = (p - top) @ tilt + top
        r = np.sqrt(q[:, 0] ** 2 + (q[:, 1] - apex[1]) ** 2)
        z = q[:, 2] - rim_z
        rel = np.stack([r - a2[0], z - a2[1]], 1)
        t = np.clip((rel @ seg) / L2, 0, 1)
        dv = rel - t[:, None] * seg[None]
        return np.sqrt(np.einsum("ij,ij->i", dv, dv)) - 0.0042
    lay.prims.append(S.Prim(cone, np.array([0, apex[1], rim_z + 0.07]), R + 0.08, "head", label, 0.0, 0.004, "cone"))
    # inner head ring (keeps the hat seated) + chin ribbon
    ring_c = top + np.array([0, 0.0, -0.035]) * hs
    lay.prims.append(S.Prim(S.f_torus(ring_c, 0.062 * hs, 0.006, axis=(0, 0.1, 1)), ring_c, 0.08 * hs, "head",
                            label + "_ring", 0.004, 0.004, "ring"))
    chin = body.L["chin"] + np.array([0, 0.03, -0.006]) * hs
    for sd in (1, -1):
        hp = h(0.071 * sd, 0.0, 1.52)
        lay.prims.append(S.Prim(S.f_flat_cone(hp, chin + np.array([0.01 * sd, 0, 0]), 0.0075, 0.0075, 0.4, (1, 0, 0)),
                                (hp + chin) / 2, 0.12, {"head": 0.7, "jaw": 0.3}, label + "_ribbon", 0.003, 0.008,
                                "ribbon"))
    return lay


def acc_cap(body: Body, label="cap"):
    M = body.model
    h = body.h
    hs = body.hs
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    for p in _named(M, ["cranium", "forehead"]):
        lay.prims.append(S.Prim(S.f_offset(p.fn, 0.016 * hs), p.c, p.r + 0.02, "head", label, p.k, 0.02, "crown"))
    cut_p = h(0, -0.02, 1.525)
    pl = S.f_plane(cut_p, (0, -0.32, 1))
    lay.carves.append(S.Carve(pl, h(0, 0, 1.40), 0.2, 0.004))
    bc = h(0, -0.13, 1.528)
    R = S.rot((1, 0, 0), 8)
    brim = S.f_ellipsoid(bc, np.array([0.078, 0.072, 0.006]) * hs, R)
    cut_b = S.f_plane(h(0, -0.06, 0), (0, -1, 0))
    lay.prims.append(S.Prim(lambda p: np.maximum(brim(p), -cut_b(p) - 0.0), bc, 0.09 * hs, "head", label + "_brim", 0.006,
                            0.01, "brim"))
    btn = h(0, 0.01, 1.602)
    lay.prims.append(S.Prim(S.f_sphere(btn, 0.007 * hs), btn, 0.01, "head", label, 0.004, 0.01, "button"))
    return lay


def acc_helmet(body: Body, label="helmet"):
    """Half-shell motorbike helmet with a short visor and chin straps."""
    M = body.model
    h = body.h
    hs = body.hs
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    shell_c = h(0, 0.012, 1.50)
    lay.prims.append(S.Prim(S.f_ellipsoid(shell_c, np.array([0.098, 0.122, 0.112]) * hs), shell_c, 0.13 * hs, "head",
                            label, 0.0, 0.01, "shell"))
    cut_p = h(0, 0.0, 1.488)
    pl = S.f_plane(cut_p, (0, -0.18, 1))
    lay.carves.append(S.Carve(pl, h(0, 0, 1.38), 0.2, 0.005))
    vc = h(0, -0.118, 1.512)
    vis = S.f_ellipsoid(vc, np.array([0.075, 0.035, 0.005]) * hs, S.rot((1, 0, 0), 14))
    cutv = S.f_plane(h(0, -0.095, 0), (0, -1, 0))
    lay.prims.append(S.Prim(lambda p: np.maximum(vis(p), -cutv(p)), vc, 0.08 * hs, "head", label + "_visor", 0.004,
                            0.01, "visor"))
    chin = body.L["chin"] + np.array([0, 0.028, -0.004]) * hs
    for sd in (1, -1):
        hp = h(0.074 * sd, 0.012, 1.49)
        lay.prims.append(S.Prim(S.f_flat_cone(hp, chin + np.array([0.008 * sd, 0, 0]), 0.0075, 0.0075, 0.4, (1, 0, 0)),
                                (hp + chin) / 2, 0.12, {"head": 0.7, "jaw": 0.3}, label + "_strap", 0.003, 0.008,
                                "strap"))
    return lay


def _neutral_hand_frame(body: Body, nm: str):
    """World direction mapping: rest-space vector that becomes `down` after the neutral
    standing arm pose (arms lowered from the A-pose)."""
    q = _neutral_arm_quat(nm)
    return q


def _neutral_arm_quat(nm):
    sgn = 1 if nm == "L" else -1
    qa = A.qy(ARM_ABD - 8.0) if nm == "L" else A.qy(-(ARM_ABD - 8.0))
    qf = A.qx(-8.0)
    return qa @ qf


def acc_cane(body: Body, label="cane"):
    M = body.model
    L = body.L
    s = body.s
    nm = "R"
    W, Kn = L[f"wrist_{nm}"], L[f"knuckle_{nm}"]
    grip = W + (Kn - W) * 0.55 + np.array([0, -0.0, 0])
    q = _neutral_arm_quat(nm)
    down_rest = np.array(q.inverted() @ Vector((0, 0, -1)))
    fwd_rest = np.array(q.inverted() @ Vector((0, -1, 0)))
    # hand height in the neutral pose ~ 0.48 H; cane length so the tip touches the ground
    length = 0.47 * body.spec.height + 0.06
    tip = grip + down_rest * length
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    lay.prims.append(S.Prim(S.f_round_cone(grip - down_rest * 0.01, tip, 0.0115, 0.0105), (grip + tip) / 2,
                            length / 2 + 0.03, f"hand_{nm}", label, 0.0, 0.004, "shaft"))
    # crook handle
    hc = grip - down_rest * 0.035 + fwd_rest * 0.045
    lay.prims.append(S.Prim(S.f_torus(hc, 0.045, 0.012, axis=np.cross(down_rest, fwd_rest)), hc, 0.07,
                            f"hand_{nm}", label, 0.004, 0.004, "crook"))
    lay.carves.append(S.Carve(S.f_plane(hc, -down_rest), hc + down_rest * 0.06, 0.06, 0.003))
    lay.prims.append(S.Prim(S.f_cyl(tip - down_rest * 0.02, tip + down_rest * 0.004, 0.0135, 0.003), tip, 0.03,
                            f"hand_{nm}", label + "_tip", 0.002, 0.004, "ferrule"))
    return lay


def acc_basket(body: Body, label="basket"):
    """Woven plastic market basket hanging from the left hand."""
    M = body.model
    L = body.L
    nm = "L"
    W, Kn = L[f"wrist_{nm}"], L[f"knuckle_{nm}"]
    grip = W + (Kn - W) * 0.6
    q = _neutral_arm_quat(nm)
    down = np.array(q.inverted() @ Vector((0, 0, -1)))
    fwd = np.array(q.inverted() @ Vector((0, -1, 0)))
    side = np.cross(fwd, down)
    Rb = np.stack([side, fwd, -down], 1)        # local x side, y fwd, z up
    c = grip + down * 0.20
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    body_fn = S.f_box(c, np.array([0.17, 0.11, 0.09]), Rb, 0.03)
    inner = S.f_box(c - down * 0.015, np.array([0.155, 0.095, 0.09]), Rb, 0.025)
    shell = lambda p: np.maximum(body_fn(p), -inner(p))   # noqa: E731
    lay.prims.append(S.Prim(shell, c, 0.24, f"hand_{nm}", label, 0.0, 0.004, "basket"))
    for sg in (1, -1):
        a = c + side * 0.06 * sg - down * 0.08
        tor = S.f_torus(c - down * 0.08, 0.11, 0.008, axis=fwd)
        cut = S.f_plane(c - down * 0.08, -down)
        lay.prims.append(S.Prim(lambda p, tor=tor, cut=cut: np.maximum(tor(p), -cut(p)), c - down * 0.12, 0.14,
                                f"hand_{nm}", label + "_handle", 0.0, 0.004, "handle"))
        break
    # greens sticking out
    g = c - down * 0.10 + side * 0.05
    lay.prims.append(S.Prim(S.f_ellipsoid(g, np.array([0.08, 0.05, 0.05]), Rb), g, 0.09, f"hand_{nm}", "greens", 0.01,
                            0.004, "greens"))
    return lay


def acc_phone(body: Body, label="phone"):
    M = body.model
    L = body.L
    nm = "R"
    W, Kn = L[f"wrist_{nm}"], L[f"knuckle_{nm}"]
    c = W + (Kn - W) * 0.7 + body.n_palm * np.array([-1, 1, 1]) * 0.018
    d = body.d_fa * np.array([-1, 1, 1])
    n = body.n_palm * np.array([-1, 1, 1])
    w = np.cross(n, d)
    R = np.stack([w, d, n], 1)
    lay = M.layer(label, priority=0.004)
    lay.hems = []
    lay.prims.append(S.Prim(S.f_box(c, np.array([0.036, 0.075, 0.0045]), R, 0.003), c, 0.09, f"hand_{nm}", label, 0.0,
                            0.004, "phone"))
    return lay


ACCESSORIES = {"nonla": acc_nonla, "cap": acc_cap, "helmet": acc_helmet, "cane": acc_cane, "basket": acc_basket,
               "phone": acc_phone}
GARMENTS = {"top": g_top, "bottom": g_bottom, "skirt": g_skirt_wrap, "apron": g_apron, "footwear": g_footwear,
            "scarf": g_scarf, "mask": g_mask, "backpack": g_backpack}
