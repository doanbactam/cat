"""Common house gecko (thằn lằn / Hemidactylus) - 11 cm snout to tail tip. Owner: creatures.
Sprawling lizard on the XY plane (belly down, front -Y); on walls world-life rotates the node
so local +Z (Godot +Y) is the wall normal. Clips: idle(L) (throat pulse, head tilts, tail curl)
and run(L) (lateral undulation with diagonal leg pairs, 0.6 m/s)."""
from __future__ import annotations

import math

import numpy as np

import npc_anim as A
import npc_quad as Q
import npc_sdf as S
import npc_tex as X
from npc_anim import Pose, qx, qy, qz, wave, noise1, smoothstep
from npc_tex import col, mix, sstep

N_TAIL = 6
CLIPS = {"idle": (90, True), "run": (10, True)}
SPEEDS = {"run": 0.6}


def landmarks():
    lm = {"scale": 0.15}
    z = 0.0055
    lm["pelvis"] = np.array([0, 0.012, z])
    lm["spine1"] = np.array([0, 0.000, z])
    lm["spine2"] = np.array([0, -0.012, z])
    lm["chest"] = np.array([0, -0.022, z])
    lm["neck_base"] = np.array([0, -0.030, z + 0.0005])
    lm["head_base"] = np.array([0, -0.035, z + 0.001])
    lm["nose"] = np.array([0, -0.054, z - 0.0005])
    lm["jaw_pivot"] = np.array([0, -0.036, z - 0.002])
    lm["jaw_tip"] = np.array([0, -0.052, z - 0.0025])
    lm["tail"] = [np.array([0, 0.018 + 0.0095 * i, z - 0.0005 * i]) for i in range(N_TAIL + 1)]
    L = {"ear_base_L": [0.006, -0.038, z + 0.001], "ear_tip_L": [0.0075, -0.036, z + 0.001],
         "scap_L": [0.003, -0.022, z], "shoulder_L": [0.006, -0.022, z], "elbow_L": [0.0155, -0.024, z + 0.002],
         "wrist_L": [0.019, -0.030, 0.0015], "fpaw_L": [0.021, -0.035, 0.0006],
         "hip_L": [0.006, 0.014, z], "knee_L": [0.0165, 0.010, z + 0.002], "hock_L": [0.022, 0.018, 0.0015],
         "hpaw_L": [0.024, 0.016, 0.0006], "htoe_L": [0.027, 0.012, 0.0005], "eye_L": [0.0048, -0.043, z + 0.0018]}
    for k, v in L.items():
        lm[k] = np.array(v, np.float64)
    return Q.complete_sides(lm)


def build_model(lm):
    M = S.Model(band=0.006)
    fp = Q.flow_prim
    E = S.f_ellipsoid
    RC = S.f_round_cone
    back = (0, 1, 0)
    fp(M, E((0, -0.004, 0.0052), (0.0068, 0.024, 0.0038)), [(0, -0.004, 0.0052)],
       {"spine_01": 0.4, "spine_02": 0.3, "pelvis": 0.3}, "skin", 0.004, 0.004, back, "body", pad=0.025)
    fp(M, E((0, -0.043, 0.0058), (0.0058, 0.010, 0.0034)), [(0, -0.043, 0.0058)], "head", "skin", 0.003, 0.003, back,
       "head", pad=0.012)
    fp(M, RC((0, -0.046, 0.0055), (0, -0.0535, 0.0048), 0.0042, 0.0018), [(0, -0.046, 0.0055), (0, -0.0535, 0.0048)],
       "head", "skin", 0.002, 0.002, back, "snout", pad=0.006)
    fp(M, RC((0, -0.03, 0.0055), (0, -0.036, 0.0057), 0.0042, 0.0046), [(0, -0.03, 0.0055), (0, -0.036, 0.0057)],
       "neck", "skin", 0.003, 0.003, back, "neck", pad=0.006)
    for sd, nm in ((1, "L"), (-1, "R")):
        e = lm[f"eye_{nm}"]
        fp(M, S.f_sphere(e, 0.0027), [e], "head", "lid", 0.0012, 0.002, back, "lid", pad=0.003)
        for leg, a, b, c, d in (("F", "shoulder", "elbow", "wrist", "fpaw"), ("H", "hip", "knee", "hock", "hpaw")):
            pa, pb, pc, pd = (lm[f"{x}_{nm}"] for x in (a, b, c, d))
            bones = ("upperarm", "forearm", "hand") if leg == "F" else ("thigh", "shin", "foot")
            fp(M, RC(pa, pb, 0.0022 if leg == "F" else 0.0028, 0.0016), [pa, pb], f"{bones[0]}_{nm}", "skin", 0.002,
               0.002, pb - pa, "leg1", pad=0.004)
            fp(M, RC(pb, pc, 0.0015, 0.0012), [pb, pc], f"{bones[1]}_{nm}", "skin", 0.0012, 0.0015, pc - pb, "leg2",
               pad=0.004)
            bn3 = f"{bones[2]}_{nm}" if leg == "F" else f"foot_{nm}"
            fp(M, RC(pc, pd, 0.0012, 0.0011), [pc, pd], bn3, "skin", 0.001, 0.0015, pd - pc, "leg3", pad=0.004)
            # splayed toes with adhesive pads
            for k in range(5):
                ang = math.radians(-70 + 35 * k) * sd
                base_dir = S.normalize(pd - pc)
                dvec = S.rot((0, 0, 1), math.degrees(ang)) @ base_dir
                tip = pd + dvec * 0.0042
                M.add(S.f_sphere(tip, 0.0009), [tip], f"{bones[2]}_{nm}" if leg == "F" else f"toe_{nm}", "skin",
                      0.0006, 0.0015, "pad", pad=0.002)
                bn = f"{bones[2]}_{nm}" if leg == "F" else f"toe_{nm}"
                M.add(RC(pd, tip, 0.0006, 0.0009), [pd, tip], bn, "skin", 0.0006, 0.0015, "toe", pad=0.003)
    tp = lm["tail"]
    for i in range(N_TAIL):
        r1 = 0.0036 - 0.00052 * i
        r2 = 0.0036 - 0.00052 * (i + 1)
        fp(M, RC(tp[i], tp[i + 1], r1, max(r2, 0.0006)), [tp[i], tp[i + 1]], f"tail_{i + 1:02d}", "skin", 0.002,
           0.003, back, "tail", pad=0.008)
    return M


def colour(P, N, lab, fl, s1, s2, names):
    K = len(P)
    li = {n: i for i, n in enumerate(names)}
    base = col("#b9a588")
    a = base[None] * (0.9 + 0.12 * X.fbm(P, 400.0, 3, 4)[:, None])
    # tubercles + darker speckle bands, pale translucent belly
    d, cid, _ = X.cells(P, 0.0011, 9)
    tub = sstep(0.00045, 0.0002, d) * (cid > 0.6)
    a = mix(a, col("#7d6a52")[None], tub * 0.5)
    bands = sstep(0.2, 0.7, np.sin(P[:, 1] * 2 * np.pi / 0.008 + X.fbm(P, 300.0, 2, 5) * 2.0)) * (P[:, 2] > 0.004)
    a = mix(a, col("#8a7558")[None], bands * 0.4)
    belly = sstep(0.0, -0.6, N[:, 2])
    a = mix(a, col("#e2cfbf")[None], belly * 0.75)
    rough = 0.48 + 0.08 * X.fbm(P, 600.0, 2, 6)
    if "lid" in li:
        m = lab == li["lid"]
        a[m] = col("#9a8468")
    return a, rough, np.zeros(K)


class GeckoAnim(Q.QuadAnim):
    def _sprawl(self, p, t, u, amp, stride):
        # lateral undulation: spine yaw wave, diagonal limbs swing about Z
        w = math.sin(2 * math.pi * u)
        p.r("pelvis", qz(10 * amp * w))
        p.r("spine_01", qz(-12 * amp * w))
        p.r("spine_02", qz(-10 * amp * w))
        p.r("chest", qz(-6 * amp * w))
        p.r("neck", qz(8 * amp * w))
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qz(14 * amp * math.sin(2 * math.pi * (u - 0.12 * (i + 1)))))
        for sd in "LR":
            sg = 1 if sd == "L" else -1
            ph_f = w * sg
            ph_h = -w * sg
            lift_f = max(0.0, math.cos(2 * math.pi * u) * sg) * stride
            lift_h = max(0.0, -math.cos(2 * math.pi * u) * sg) * stride
            p.r(f"upperarm_{sd}", qz(-28 * stride * ph_f) @ qy(-25 * lift_f), sd)
            p.r(f"forearm_{sd}", qz(14 * stride * ph_f), sd)
            p.r(f"thigh_{sd}", qz(-30 * stride * ph_h) @ qy(-25 * lift_h), sd)
            p.r(f"shin_{sd}", qz(16 * stride * ph_h), sd)
        return p

    def idle(self, t):
        p = Pose()
        u = t / (CLIPS["idle"][0] / A.FPS)
        p.r("head", qy(10 * noise1(t, 3, 3.0)) @ qz(12 * noise1(t, 4, 3.0)) @ qx(-4 * noise1(t, 5, 3.0)))
        p.r("jaw", qx(1.5 * max(0.0, math.sin(2 * math.pi * t * 2.5))))
        p.t("chest", (0, 0, 0.0002 * math.sin(2 * math.pi * t * 1.2)))
        flick = smoothstep(0.6, 0.65, u) - smoothstep(0.7, 0.8, u)
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qz(8 * flick * (i + 1) / N_TAIL + 3 * math.sin(2 * math.pi * (u - i * 0.1))))
        return p

    def run(self, t):
        T = CLIPS["run"][0] / A.FPS
        p = Pose()
        self._sprawl(p, t, t / T, 1.0, 1.0)
        p.t("pelvis", (0, 0, 0.0008))
        return p

    def bake_all(self, animator):
        for nm, (fr, loop) in CLIPS.items():
            animator.bake_clip(nm, getattr(self, nm), fr, loop)


def kit(cid):
    lm = landmarks()
    M = build_model(lm)
    tex = Q.FurTex(M, colour, seed=8, strand=(3000.0, 2500.0), relief=0.00004, ao_mix=0.3)
    return dict(model=M, bones=Q.quad_bones(lm, N_TAIL), tex=tex, anim=GeckoAnim(lm, N_TAIL),
                eyes=[(lm["eye_L"], 0.0021, (1, -0.5, 0.25)), (lm["eye_R"], 0.0021, (-1, -0.5, 0.25))],
                warp=[(lm["head_base"], 0.012, 1.3)], meta={"speeds": SPEEDS})
