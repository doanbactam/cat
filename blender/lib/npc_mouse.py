"""House mouse (prey) - 9 cm body + 8.5 cm tail, ~20 g. Owner: creatures.
Shares the quadruped rig layout (npc_quad). Clips: idle(L) (sniffing, whisker/ear twitch,
grooming flick) and run(L) (half-bound scurry, 1.0 m/s)."""
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
CLIPS = {"idle": (60, True), "run": (8, True)}
SPEEDS = {"run": 1.0}


def landmarks():
    lm = {"scale": 0.2}
    lm["pelvis"] = np.array([0, 0.030, 0.026])
    lm["spine1"] = np.array([0, 0.012, 0.030])
    lm["spine2"] = np.array([0, -0.006, 0.030])
    lm["chest"] = np.array([0, -0.022, 0.027])
    lm["neck_base"] = np.array([0, -0.036, 0.024])
    lm["head_base"] = np.array([0, -0.046, 0.025])
    lm["nose"] = np.array([0, -0.074, 0.017])
    lm["jaw_pivot"] = np.array([0, -0.052, 0.016])
    lm["jaw_tip"] = np.array([0, -0.068, 0.012])
    tail = []
    for i in range(N_TAIL + 1):
        u = i / N_TAIL
        tail.append(np.array([0.012 * math.sin(u * 2.4) * u, 0.050 + 0.085 * u, 0.018 - 0.014 * u + 0.006 * u * u]))
    lm["tail"] = tail
    L = {"ear_base_L": [0.010, -0.043, 0.034], "ear_tip_L": [0.015, -0.040, 0.041],
         "scap_L": [0.010, -0.018, 0.030], "shoulder_L": [0.013, -0.026, 0.019], "elbow_L": [0.014, -0.022, 0.011],
         "wrist_L": [0.013, -0.030, 0.004], "fpaw_L": [0.013, -0.034, 0.0015],
         "hip_L": [0.013, 0.032, 0.020], "knee_L": [0.016, 0.022, 0.012], "hock_L": [0.014, 0.040, 0.005],
         "hpaw_L": [0.014, 0.030, 0.0015], "htoe_L": [0.014, 0.020, 0.001], "eye_L": [0.0085, -0.058, 0.025]}
    for k, v in L.items():
        lm[k] = np.array(v, np.float64)
    return Q.complete_sides(lm)


def build_model(lm):
    M = S.Model(band=0.008)
    fp = Q.flow_prim
    E = S.f_ellipsoid
    RC = S.f_round_cone
    back = (0, 1, 0)
    fp(M, E((0, 0.022, 0.022), (0.020, 0.030, 0.019)), [(0, 0.022, 0.022)], {"pelvis": 0.5, "spine_01": 0.5}, "fur",
       0.012, 0.008, back, "body", pad=0.04)
    fp(M, E((0, -0.012, 0.021), (0.0155, 0.022, 0.0155)), [(0, -0.012, 0.021)], {"chest": 0.6, "spine_02": 0.4}, "fur",
       0.012, 0.008, back, "chest", pad=0.03)
    fp(M, E((0, -0.050, 0.024), (0.0125, 0.0165, 0.0115)), [(0, -0.050, 0.024)], "head", "fur", 0.01, 0.005, back,
       "head", pad=0.02)
    fp(M, RC((0, -0.058, 0.021), (0, -0.072, 0.017), 0.0085, 0.0035), [(0, -0.058, 0.021), (0, -0.072, 0.017)], "head",
       "fur", 0.005, 0.004, (0, 1, 0.2), "snout", pad=0.012)
    M.add(S.f_sphere((0, -0.0745, 0.0172), 0.0022), [(0, -0.0745, 0.0172)], "head", "nose", 0.0015, 0.003, "nose",
          pad=0.003)
    for sd, nm in ((1, "L"), (-1, "R")):
        eb, et = lm[f"ear_base_{nm}"], lm[f"ear_tip_{nm}"]
        ear = S.f_flat_cone(eb, et, 0.0062, 0.0078, 0.2, (0.4 * sd, -1, 0))
        fp(M, ear, [eb, et], f"ear_{nm}", "ear", 0.003, 0.003, et - eb, "ear", pad=0.01)
        e = lm[f"eye_{nm}"]
        fp(M, S.f_sphere(e, 0.0036), [e], "head", "fur", 0.0015, 0.003, back, "lid", pad=0.004)
        for leg, a, b, c, d in (("F", "shoulder", "elbow", "wrist", "fpaw"), ("H", "hip", "knee", "hock", "hpaw")):
            pa, pb, pc, pd = (lm[f"{x}_{nm}"] for x in (a, b, c, d))
            bones = (("upperarm", "forearm", "hand") if leg == "F" else ("thigh", "shin", "foot"))
            r0 = 0.0045 if leg == "F" else 0.0075
            fp(M, RC(pa, pb, r0, 0.0032), [pa, pb], f"{bones[0]}_{nm}", "fur", 0.004, 0.003, (0, 0.2, -1), "leg1",
               pad=0.01)
            fp(M, RC(pb, pc, 0.0025, 0.0016), [pb, pc], f"{bones[1]}_{nm}", "skin", 0.002, 0.002, (0, 0, -1), "leg2",
               pad=0.006)
            tip = pd + np.array([0, -0.006, 0.0005])
            M.add(RC(pc, tip, 0.0016, 0.0014), [pc, tip], f"{bones[2]}_{nm}", "skin",
                  0.0015, 0.002, "paw", pad=0.006)
    tp = lm["tail"]
    for i in range(N_TAIL):
        r1 = 0.0028 - 0.0003 * i
        r2 = 0.0028 - 0.0003 * (i + 1)
        M.add(RC(tp[i], tp[i + 1], r1, r2), [tp[i], tp[i + 1]], f"tail_{i + 1:02d}", "tail", 0.002, 0.004, "tail",
              pad=0.01)
    return M


def colour(P, N, lab, fl, s1, s2, names):
    K = len(P)
    li = {n: i for i, n in enumerate(names)}
    base = col("#6e655c")
    belly = col("#a59a8c")
    a = base[None] * (0.85 + 0.25 * s1[:, None] + 0.1 * X.fbm(P, 200.0, 2, 3)[:, None])
    under = sstep(0.1, -0.6, N[:, 2])
    a = mix(a, belly[None], under * 0.7)
    rough = 0.6 + 0.08 * s1
    for nm, c, r in (("skin", "#c7a196", 0.5), ("ear", "#b8918a", 0.5), ("tail", "#9c8a80", 0.45),
                     ("nose", "#c48a86", 0.35)):
        if nm in li:
            m = lab == li[nm]
            ring = 0.5 + 0.5 * np.sin(P[m, 1] * 2 * np.pi / 0.0012) if nm == "tail" else 0.0
            a[m] = col(c) * (0.9 + 0.12 * X.fbm(P[m], 900.0, 2, 4)[:, None]) * (0.92 + 0.08 * np.asarray(ring))[..., None] \
                if nm == "tail" else col(c) * (0.9 + 0.12 * X.fbm(P[m], 900.0, 2, 4)[:, None])
            rough[m] = r
    return a, rough, np.zeros(K)


class MouseAnim(Q.QuadAnim):
    def idle(self, t):
        p = Pose()
        sn = max(0.0, math.sin(2 * math.pi * t * 6)) * (0.5 + 0.5 * math.sin(2 * math.pi * t / 2.0))
        tg = {leg: (0.0, 0.0) for leg in Q.LEGS}
        rear = smoothstep(0.55, 0.65, (t / 2.0) % 1.0) - smoothstep(0.85, 0.95, (t / 2.0) % 1.0)
        self.leg_targets(p, (0, 0.0, 0.004 * rear), -18 * rear, 0.0, {**tg, "FL": (0.004, 0.012 * rear),
                         "FR": (0.004, 0.012 * rear)}, {})
        p.r("neck", qx(-8 * rear + 3 * sn) @ qz(18 * noise1(t, 3, 2.0)))
        p.r("head", qx(-6 * sn) @ qz(8 * noise1(t, 4, 2.0)))
        for sd in "LR":
            p.r(f"ear_{sd}", qz(10 * noise1(t, 5 if sd == "L" else 6, 1.0)), sd)
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qz(6 * math.sin(2 * math.pi * (t / 2.0 - i * 0.1))))
        return p

    def run(self, t):
        T = CLIPS["run"][0] / A.FPS
        u = t / T
        half = SPEEDS["run"] * T * 0.4 * 0.5
        p = Pose()
        tg, fx = {}, {}
        for leg, off in (("HL", 0.0), ("HR", 0.06), ("FL", 0.5), ("FR", 0.56)):
            dy, dz, f = self.cycle((u + off) % 1.0, 0.4, half, 0.009)
            tg[leg] = (dy, dz)
            fx[leg] = f * 40
        self.leg_targets(p, (0, 0, 0.002 * math.cos(2 * math.pi * u)), 0.0, 0.0, tg, fx)
        p.r("spine_01", qx(12 * math.sin(2 * math.pi * u)))
        p.r("spine_02", qx(-8 * math.sin(2 * math.pi * u)))
        p.r("neck", qx(-6 * math.cos(2 * math.pi * u)))
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qz(10 * math.sin(2 * math.pi * (u - i * 0.12))) @ qx(-2))
        return p

    def bake_all(self, animator):
        for nm, (fr, loop) in CLIPS.items():
            animator.bake_clip(nm, getattr(self, nm), fr, loop)


def kit(cid):
    lm = landmarks()
    M = build_model(lm)
    tex = Q.FurTex(M, colour, seed=3, strand=(3000.0, 120.0), relief=0.00012, ao_mix=0.3)
    return dict(model=M, bones=Q.quad_bones(lm, N_TAIL), tex=tex, anim=MouseAnim(lm, N_TAIL),
                eyes=[(lm["eye_L"], 0.0027, (0.7, -1, 0.15)), (lm["eye_R"], 0.0027, (-0.7, -1, 0.15))],
                warp=[(lm["head_base"], 0.02, 1.4)], meta={"speeds": SPEEDS})
