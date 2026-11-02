"""Vện - medium Vietnamese street dog (chó cỏ), brindle coat, sickle tail, erect ears.
Shoulder height 0.50 m, nose-to-rump 0.86 m, ~15 kg. Owner: creatures.
Clips: idle(L) walk(L, 1.1 m/s) run(L, 3.6 m/s) bark sleep(L) sniff(L) growl(L)."""
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
CLIPS = {"idle": (90, True), "walk": (30, True), "run": (12, True), "bark": (24, False), "sleep": (150, True),
         "sniff": (90, True), "growl": (60, True)}
SPEEDS = {"walk": 1.1, "run": 3.6}


def landmarks():
    lm = {"scale": 1.0}
    lm["pelvis"] = np.array([0, 0.25, 0.445])
    lm["spine1"] = np.array([0, 0.13, 0.465])
    lm["spine2"] = np.array([0, 0.00, 0.475])
    lm["chest"] = np.array([0, -0.13, 0.48])
    lm["neck_base"] = np.array([0, -0.24, 0.49])
    lm["head_base"] = np.array([0, -0.335, 0.625])
    lm["nose"] = np.array([0, -0.525, 0.585])
    lm["jaw_pivot"] = np.array([0, -0.36, 0.59])
    lm["jaw_tip"] = np.array([0, -0.50, 0.555])
    # sickle tail: up from the croup, curling forward over the back
    ts = []
    for i in range(N_TAIL + 1):
        a = math.radians(-30 + i * 34)        # sweep angle
        r = 0.11
        c = np.array([0, 0.285, 0.565])
        ts.append(c + np.array([0.004 * i * i, r * math.cos(math.radians(-90) + a) * -1.0 + 0.0,
                                r * math.sin(math.radians(-90) + a) * -1.0]) * np.array([1, 1, 1]))
    # re-shape to a clear curl: base behind the rump, rising, arcing over toward the back
    pts = [np.array([0, 0.335, 0.47]), np.array([0, 0.385, 0.53]), np.array([0, 0.405, 0.60]),
           np.array([0.004, 0.39, 0.665]), np.array([0.014, 0.345, 0.70]), np.array([0.03, 0.29, 0.695]),
           np.array([0.045, 0.255, 0.66])]
    lm["tail"] = pts
    L = {
        "ear_base_L": [0.042, -0.335, 0.672], "ear_tip_L": [0.066, -0.33, 0.762],
        "scap_L": [0.055, -0.15, 0.50], "shoulder_L": [0.072, -0.225, 0.37], "elbow_L": [0.07, -0.175, 0.255],
        "wrist_L": [0.064, -0.19, 0.075], "fpaw_L": [0.064, -0.215, 0.012],
        "hip_L": [0.068, 0.25, 0.405], "knee_L": [0.078, 0.17, 0.27], "hock_L": [0.07, 0.315, 0.115],
        "hpaw_L": [0.07, 0.285, 0.012], "htoe_L": [0.07, 0.245, 0.008],
        "eye_L": [0.034, -0.425, 0.645],
    }
    for k, v in L.items():
        lm[k] = np.array(v, np.float64)
    return Q.complete_sides(lm)


def build_model(lm) -> S.Model:
    M = S.Model(band=0.04)
    fp = Q.flow_prim
    E = S.f_ellipsoid
    RC = S.f_round_cone
    back = (0, 1, 0)
    down = (0, 0.15, -1)
    # torso: deep chest, tucked waist, rump
    fp(M, E((0, -0.105, 0.392), (0.106, 0.17, 0.128)), [(0, -0.105, 0.395)], {"chest": 0.6, "spine_02": 0.4}, "fur",
       0.05, 0.04, back, "ribcage", pad=0.17)
    fp(M, S.f_sphere((0, -0.232, 0.39), 0.086), [(0, -0.235, 0.385)], "chest", "fur", 0.05, 0.03, (0, 0.3, -1),
       "brisket", pad=0.08)
    fp(M, E((0, 0.10, 0.425), (0.079, 0.15, 0.079)), [(0, 0.10, 0.425)], {"spine_01": 0.7, "spine_02": 0.3}, "fur",
       0.06, 0.04, back, "loin", pad=0.15)
    fp(M, E((0, 0.255, 0.43), (0.088, 0.10, 0.088)), [(0, 0.255, 0.43)], "pelvis", "fur", 0.05, 0.03, back, "rump",
       pad=0.1)
    for sd, nm in ((1, "L"), (-1, "R")):
        x = 0.052 * sd
        fp(M, E((x, -0.18, 0.43), (0.035, 0.075, 0.095), S.rot((1, 0, 0), -25)), [(x, -0.18, 0.43)],
           {f"scapula_{nm}": 0.7, "chest": 0.3}, "fur", 0.04, 0.03, (0, 0.4, -1), "shoulder", pad=0.1)
        # front leg
        sh, el, wr, pw = (lm[f"shoulder_{nm}"], lm[f"elbow_{nm}"], lm[f"wrist_{nm}"], lm[f"fpaw_{nm}"])
        fp(M, RC(sh + np.array([0, -0.01, 0.03]), el, 0.050, 0.035), [sh, el], f"upperarm_{nm}", "fur", 0.035, 0.02,
           down, "upperarm", pad=0.05)
        fp(M, RC(el, wr, 0.0295, 0.0195), [el, wr], f"forearm_{nm}", "fur", 0.02, 0.015, down, "forearm", pad=0.03)
        fp(M, RC(wr, pw + np.array([0, -0.01, 0.012]), 0.017, 0.018), [wr, pw], f"hand_{nm}", "fur", 0.012, 0.012,
           (0, -0.2, -1), "pastern", pad=0.02)
        fp(M, E(pw + np.array([0, -0.012, 0.012]), (0.022, 0.03, 0.014)), [pw], f"hand_{nm}", "fur", 0.01, 0.01,
           (0, -1, -0.3), "paw", pad=0.03)
        for i, ox in enumerate((-0.012, -0.004, 0.004, 0.012)):
            c = pw + np.array([ox * sd, -0.036 + 0.006 * abs(ox) / 0.012, 0.008])
            fp(M, S.f_sphere(c, 0.0085), [c], f"hand_{nm}", "fur", 0.006, 0.008, (0, -1, -0.5), "toe", pad=0.01)
            cl = c + np.array([0, -0.009, -0.003])
            M.add(RC(cl, cl + np.array([0, -0.008, -0.006]), 0.0028, 0.0012), [cl], f"hand_{nm}", "claw", 0.002, 0.008,
                  "claw", pad=0.015)
        # hind leg
        hp, kn, hk, hw, ht = (lm[f"hip_{nm}"], lm[f"knee_{nm}"], lm[f"hock_{nm}"], lm[f"hpaw_{nm}"], lm[f"htoe_{nm}"])
        fp(M, E(hp + (kn - hp) * 0.45 + np.array([0.004 * sd, 0.018, 0.0]), (0.045, 0.075, 0.095),
                S.rot((1, 0, 0), 30)), [hp], f"thigh_{nm}", "fur", 0.05, 0.025, (0, 0.5, -1), "thigh", pad=0.1)
        fp(M, RC(kn, hk, 0.038, 0.0195), [kn, hk], f"shin_{nm}", "fur", 0.03, 0.02, (0, 0.6, -1), "gaskin", pad=0.04)
        fp(M, RC(hk + np.array([0, 0.01, 0.0]), hw + np.array([0, 0, 0.012]), 0.0185, 0.017), [hk, hw], f"foot_{nm}",
           "fur", 0.012, 0.012, (0, -0.1, -1), "metatarsus", pad=0.02)
        fp(M, E(hw + np.array([0, -0.014, 0.011]), (0.021, 0.029, 0.013)), [hw], f"toe_{nm}", "fur", 0.01, 0.01,
           (0, -1, -0.3), "hpaw", pad=0.03)
        for ox in (-0.011, -0.004, 0.004, 0.011):
            c = hw + np.array([ox * sd, -0.036 + 0.006 * abs(ox) / 0.011, 0.008])
            fp(M, S.f_sphere(c, 0.008), [c], f"toe_{nm}", "fur", 0.006, 0.008, (0, -1, -0.5), "htoes", pad=0.01)
            cl = c + np.array([0, -0.009, -0.003])
            M.add(RC(cl, cl + np.array([0, -0.008, -0.006]), 0.0026, 0.0011), [cl], f"toe_{nm}", "claw", 0.002, 0.008,
                  "claw", pad=0.015)
        # ear: erect triangle, cupped
        eb, et = lm[f"ear_base_{nm}"], lm[f"ear_tip_{nm}"]
        ear = S.f_flat_cone(eb, et, 0.036, 0.008, 0.46, (0, 1, 0.0))
        fp(M, ear, [eb, et], f"ear_{nm}", "fur", 0.012, 0.008, et - eb, "ear", pad=0.03)
        cup = S.f_flat_cone(eb + np.array([0, -0.009, 0.016]), et + np.array([0, -0.006, -0.018]), 0.016, 0.002, 0.22,
                            (0, 1, 0))
        M.carve(cup, [eb, et], k=0.003, pad=0.03)
        # eyes: sockets + lids
        e = lm[f"eye_{nm}"]
        fp(M, S.f_sphere(e, 0.0126), [e], "head", "lid", 0.004, 0.008, back, "lid", pad=0.015)
        M.carve(_eye_aperture(e, sd), [e], k=0.0012, pad=0.025)
        # cheeks
        fp(M, E((0.036 * sd, -0.385, 0.605), (0.032, 0.04, 0.032)), [(0.036 * sd, -0.385, 0.605)], "head", "fur", 0.025,
           0.012, (0.2 * sd, 1, -0.3), "cheek", pad=0.04)
    # neck
    fp(M, RC((0, -0.215, 0.452), (0, -0.33, 0.598), 0.086, 0.066), [(0, -0.215, 0.455), (0, -0.33, 0.6)],
       {"neck": 0.8, "chest": 0.2}, "fur", 0.05, 0.03, (0, 1, -0.6), "neck", pad=0.08)
    # head: skull, stop, muzzle, jaw, nose
    fp(M, E((0, -0.35, 0.633), (0.064, 0.076, 0.058)), [(0, -0.35, 0.635)], "head", "fur", 0.03, 0.015, back, "skull",
       pad=0.075)
    fp(M, S.f_flat_cone((0, -0.39, 0.612), (0, -0.50, 0.590), 0.041, 0.026, 0.85, (1, 0, 0)),
       [(0, -0.39, 0.612), (0, -0.50, 0.590)], "head", "fur", 0.025, 0.012, (0, 1, 0.2), "muzzle", pad=0.04)
    fp(M, RC((0, -0.38, 0.580), (0, -0.48, 0.566), 0.026, 0.014), [(0, -0.38, 0.58), (0, -0.48, 0.566)], "jaw",
       "fur", 0.014, 0.008, (0, 1, 0), "lowerjaw", pad=0.03)
    M.add(S.f_ellipsoid((0, -0.511, 0.592), (0.0165, 0.012, 0.0125)), [(0, -0.511, 0.592)], "head", "nose", 0.006, 0.008,
          "nose", pad=0.02)
    # lip line (mouth slit) carve
    M.carve(S.f_ellipsoid((0, -0.462, 0.574), (0.021, 0.055, 0.0012), S.rot((1, 0, 0), -8)), [(0, -0.462, 0.574)],
            k=0.0015, pad=0.06)
    # tail
    tp = lm["tail"]
    for i in range(N_TAIL):
        r1 = 0.026 - 0.0025 * i
        r2 = 0.026 - 0.0025 * (i + 1)
        fp(M, RC(tp[i], tp[i + 1], r1, r2), [tp[i], tp[i + 1]], f"tail_{i + 1:02d}", "fur", 0.02, 0.012,
           tp[i + 1] - tp[i], "tail", pad=0.03)
    return M


def _eye_aperture(c, sd):
    w, a = 0.0088, 0.0054

    def f(p):
        q = p - c
        # opening faces forward-outward: local frame rotated 20 deg outward
        ang = math.radians(25) * sd
        x = q[:, 0] * math.cos(ang) + q[:, 1] * math.sin(ang)
        y = -q[:, 0] * math.sin(ang) + q[:, 1] * math.cos(ang)
        z = q[:, 2]
        Rr = (w * w + a * a) / (2 * a)
        cc = Rr - a
        d1 = np.sqrt(x * x + (z + cc) ** 2) - Rr
        d2 = np.sqrt(x * x + (z - cc) ** 2) - Rr
        return np.maximum(np.maximum(d1, d2), y + 0.003)
    return f


def colour(P, N, lab, fl, s1, s2, names):
    K = len(P)
    li = {n: i for i, n in enumerate(names)}
    base = col("#9a6a3c")
    light = col("#cdb08a")
    dark = col("#1c1510")
    # brindle ("vện"): irregular dark tiger streaks running dorso-ventrally on the trunk (bands across the
    # body axis), ringing the legs and tail; streaks are torn into hair-length dashes and fade in patches.
    leg = sstep(0.33, 0.24, P[:, 2]) * sstep(0.03, 0.08, np.abs(P[:, 0]))
    neck_head = sstep(-0.22, -0.30, P[:, 1])
    ax = P[:, 1] * (1.0 - leg) + P[:, 2] * leg * 1.15
    ax = ax + neck_head * P[:, 2] * 0.55
    warp = X.fbm(P, 6.0, 3, 5) * 0.035 + X.fbm(P, 18.0, 2, 6) * 0.012 + X.fbm(P, 55.0, 2, 12) * 0.004
    period = 0.021 * (1.0 + 0.25 * X.fbm(P, 3.0, 2, 14))
    st = 0.5 + 0.5 * np.sin(2 * np.pi * (ax + warp) / period)
    brk = X.aniso(P, fl, 30.0, 220.0, 11) + 0.6 * X.fbm(P, 40.0, 2, 15)
    streak = X.aniso(P, fl, 420.0, 22.0, 13)
    patch = sstep(-0.55, 0.15, X.fbm(P, 4.0, 3, 7))
    stripes = sstep(0.62, 1.05, st + 0.5 * brk + 0.4 * streak) * patch
    stripes = stripes * (1.0 - 0.75 * sstep(-0.4, -0.85, N[:, 2]))      # belly stays light
    # where the surface faces along the body axis (chest front, face, rump) the bands would turn into
    # contour rings: fade them into a dark-tipped grizzle instead
    endon = sstep(0.45, 0.85, np.abs(N[:, 1])) * (1.0 - leg)
    stripes = stripes * (1.0 - 0.85 * endon) + endon * 0.25 * sstep(0.3, 0.8, streak)
    a = base[None] * (0.84 + 0.22 * X.fbm(P, 9.0, 2, 8)[:, None])
    # sun-bleached tips: slightly lighter, warmer on the upper flanks and back
    a = mix(a, a * np.array([1.12, 1.08, 1.0]), sstep(0.2, 0.9, N[:, 2]) * 0.6)
    a = mix(a, dark[None] * (1.2 + 0.6 * s2[:, None]), stripes * 0.68)
    # muddy undercoat: brindle base is never clean, a fine dark ticking all over the trunk
    tick = sstep(0.2, 0.9, streak) * (1.0 - leg * 0.5)
    a = mix(a, a * 0.62, tick * 0.35)
    # darker saddle along the back
    saddle = sstep(0.0, 0.7, N[:, 2]) * sstep(0.40, 0.5, P[:, 2]) * (P[:, 1] > -0.25)
    a = mix(a, a * 0.7, saddle * 0.5)
    # countershading: lighter belly, chest, inner legs, throat
    belly = sstep(0.0, -0.75, N[:, 2]) * sstep(0.30, 0.42, P[:, 2]) * (P[:, 1] > -0.22)
    throat = np.exp(-np.sum(((P - np.array([0, -0.33, 0.50])) / np.array([0.045, 0.07, 0.07])) ** 2, 1))
    inner = sstep(0.4, 0.8, -np.sign(P[:, 0]) * N[:, 0]) * (P[:, 2] < 0.36)
    lt = np.clip(belly + throat * 0.9 + inner * 0.5, 0, 1)
    a = mix(a, light[None] * (0.92 + 0.12 * s1[:, None]), lt * 0.75)
    # muzzle: dark-brown mask fading toward the eyes
    muzzle = sstep(-0.43, -0.49, P[:, 1]) * (P[:, 2] > 0.54)
    a = mix(a, col("#3a2c22")[None], muzzle * 0.7)
    lip = (P[:, 1] < -0.40) & (np.abs(P[:, 2] - 0.574) < 0.006)
    a = mix(a, dark[None], lip * 0.6)
    ear = (P[:, 2] > 0.67) & (np.abs(P[:, 0]) > 0.025)
    inner_ear = ear & (N[:, 1] < -0.3)
    a = mix(a, a * 0.7, ear * 0.5)
    a = mix(a, col("#7a5446")[None] * (0.8 + 0.3 * s1[:, None]), inner_ear * 0.6)
    # paws: lighter socks, dusty
    paws = sstep(0.06, 0.02, P[:, 2])
    a = mix(a, light[None] * 0.85, paws * 0.45)
    a = mix(a, col("#5a4a3a")[None], sstep(0.02, 0.0, P[:, 2]) * 0.4)
    a = a * (0.88 + 0.16 * s1[:, None])
    rough = 0.62 + 0.08 * s1
    metal = np.zeros(K)
    for nm, c, r in (("nose", "#151210", 0.32), ("claw", "#2c2622", 0.4), ("lid", "#2a1e16", 0.45)):
        if nm in li:
            m = lab == li[nm]
            a[m] = col(c) * (0.9 + 0.2 * X.fbm(P[m], 600.0, 2, 9)[:, None])
            rough[m] = r
    return a, rough, metal


# ---------------------------------------------------------------------------
class DogAnim(Q.QuadAnim):
    def base(self, t, p=None, breathe=1.0):
        p = p or Pose()
        b = wave(t, 1.5) * breathe
        p.r("chest", qx(0.8 * b))
        p.r("spine_02", qx(-0.5 * b))
        return p

    def stand(self, p, off=(0, 0, 0), pitch=0.0, front_extra=0.0):
        tg = {leg: (0.0, 0.0) for leg in Q.LEGS}
        return self.leg_targets(p, off, pitch, front_extra, tg, {})

    def ears(self, p, t, back=0.0, flick=True):
        for sd in "LR":
            f = 0.0
            if flick:
                ph = (t * 0.6 + (0.37 if sd == "R" else 0.0)) % 1.0
                f = 14 * math.sin(math.pi * min(ph / 0.1, 1.0)) if ph < 0.1 else 0.0
            p.r(f"ear_{sd}", qx(back) @ qz(f if sd == "L" else -f), sd)
        return p

    def idle(self, t):
        p = self.base(t)
        self.stand(p, (0.004 * wave(t, 3.0), 0, -0.004 + 0.002 * wave(t, 1.5)))
        p.r("neck", qz(10 * noise1(t, 2, 3.0)) @ qx(-4 + 3 * noise1(t, 3, 3.0)))
        p.r("head", qz(8 * noise1(t, 4, 3.0)) @ qy(5 * noise1(t, 5, 3.0)))
        self.ears(p, t)
        self.tail(p, 10, 14, t / 1.5)
        p.r("jaw", qx(1.5 + 3 * max(0.0, wave(t, 0.5))))     # light panting
        return p

    def _gait(self, t, frames, speed, duty, phases, lift, bob, flexion=0.0, head=0.0):
        T = frames / A.FPS
        half = speed * T * duty * 0.5
        p = self.base(t, breathe=0.0)
        tg, fx = {}, {}
        u = t / T
        for leg in Q.LEGS:
            ph = (u + phases[leg]) % 1.0
            dy, dz, f = self.cycle(ph, duty, half, lift)
            tg[leg] = (dy, dz)
            fx[leg] = f * (70 if leg[0] == "F" else 35)
        off = (0.0, 0.0, -0.012 + bob * math.cos(4 * math.pi * u))
        pitch = flexion * 0.3 * math.sin(2 * math.pi * u)
        self.leg_targets(p, off, pitch, 0.0, tg, fx)
        p.r("spine_01", qx(flexion * math.sin(2 * math.pi * u)))
        p.r("spine_02", qx(-flexion * 0.6 * math.sin(2 * math.pi * u)) @ qz(3 * math.sin(2 * math.pi * u)))
        p.r("neck", qx(-head + 4 * math.cos(4 * math.pi * u)))
        p.r("head", qx(head * 0.5 - 3 * math.cos(4 * math.pi * u)))
        return p

    def walk(self, t):
        p = self._gait(t, CLIPS["walk"][0], SPEEDS["walk"], 0.62,
                       {"HL": 0.0, "FL": 0.75, "HR": 0.5, "FR": 0.25}, 0.06, 0.006)
        self.ears(p, t, flick=False)
        self.tail(p, 8, 16, t / 0.5)
        return p

    def run(self, t):
        p = self._gait(t, CLIPS["run"][0], SPEEDS["run"], 0.36,
                       {"HL": 0.0, "HR": 0.1, "FL": 0.55, "FR": 0.45}, 0.10, 0.02, flexion=10.0, head=-8)
        self.ears(p, t, back=25, flick=False)
        self.tail(p, -10, 8, t / 0.4)
        return p

    def bark(self, t):
        T = CLIPS["bark"][0] / A.FPS
        u = t / T
        k = math.sin(math.pi * smoothstep(0.1, 0.55, u)) * (1 - smoothstep(0.75, 1.0, u)) + \
            0.3 * math.sin(math.pi * smoothstep(0.55, 0.9, u))
        jaw = smoothstep(0.15, 0.3, u) - smoothstep(0.4, 0.62, u)
        p = self.base(t, breathe=0.0)
        self.stand(p, (0, 0.01 * k, -0.01 * k), pitch=-4 * k)
        p.r("neck", qx(-14 * k))
        p.r("head", qx(10 * k))
        p.r("jaw", qx(28 * jaw + 3))
        p.r("chest", qx(-3 * k))
        self.ears(p, t, back=-8 * k, flick=False)
        self.tail(p, 18, 6, t * 2)
        return p

    def sleep(self, t):
        p = self.base(t, breathe=1.6)
        drop = 0.25
        tg = {"FL": (-0.29, 0.0), "FR": (-0.27, 0.0), "HL": (-0.13, -0.08), "HR": (-0.12, -0.08)}
        fx = {"FL": -75, "FR": -70, "HL": -20, "HR": -20}
        self.leg_targets(p, (0.0, 0.02, -drop), 3.0, 0.0, tg, fx)
        p.r("thigh_L", qy(-28))
        p.r("thigh_R", qy(28))
        p.r("upperarm_L", qy(-6))
        p.r("upperarm_R", qy(6))
        p.r("spine_01", qz(10))
        p.r("spine_02", qz(8))
        p.r("neck", qx(30) @ qz(8))
        p.r("head", qx(18 + 1.5 * wave(t, 5.0)) @ qy(-6))
        self.ears(p, t * 0.3, back=30)
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qx(14) @ qz(10 if i < 3 else 6))
        return p

    def sniff(self, t):
        p = self.base(t, breathe=0.3)
        T = CLIPS["sniff"][0] / A.FPS
        u = t / T
        side = math.sin(2 * math.pi * u)
        self.stand(p, (0.0, -0.01, -0.03), pitch=6.0, front_extra=0.0)
        p.r("chest", qx(6))
        p.r("neck", qx(48 + 4 * math.sin(2 * math.pi * u * 2)) @ qz(14 * side))
        p.r("head", qx(16) @ qy(-6 * side))
        p.r("jaw", qx(2 + 2 * max(0.0, math.sin(2 * math.pi * t * 6))))
        self.ears(p, t, back=-6)
        self.tail(p, 4, 12, t / 0.8)
        return p

    def growl(self, t):
        p = self.base(t, breathe=0.0)
        tr = 0.6 * math.sin(2 * math.pi * t * 9)
        self.stand(p, (0.0, 0.035, -0.03), pitch=-5.0)
        p.r("chest", qx(5 + 0.6 * tr))
        p.r("neck", qx(22 + tr))
        p.r("head", qx(-14) @ qx(0.8 * tr))
        p.r("jaw", qx(9 + 1.5 * tr))
        self.ears(p, t, back=35, flick=False)
        for i in range(N_TAIL):
            p.r(f"tail_{i + 1:02d}", qx(22 if i == 0 else 8))
        return p

    def bake_all(self, animator):
        for nm, (fr, loop) in CLIPS.items():
            animator.bake_clip(nm, getattr(self, nm), fr, loop)
