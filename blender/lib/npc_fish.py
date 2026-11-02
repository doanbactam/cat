"""Koi carp (cá chép Koi) - 0.45 m, kohaku/sanke pattern. Owner: creatures.
Origin at the belly bottom centre, swimming toward -Y (Godot +Z).
Bones: root, spine_01..spine_06 (head -> tail), head, jaw, pectoral_L/R, pelvic_L/R, dorsal, anal, tail_fin.
Clip: swim(L) - travelling body wave, fin sculling, gill/mouth pulse."""
from __future__ import annotations

import math

import numpy as np

import npc_anim as A
import npc_quad as Q
import npc_sdf as S
import npc_tex as X
from npc_anim import Pose, qx, qy, qz, wave, noise1, smoothstep
from npc_tex import col, mix, sstep

LEN = 0.45
CLIPS = {"swim": (40, True), "idle": (90, True)}
N_SP = 6


def spine_pts():
    # head tip at y=-0.225, tail fin base at y=+0.16
    ys = np.linspace(-0.13, 0.165, N_SP + 1)
    zc = 0.055
    return [np.array([0, y, zc + 0.006 * math.cos((y + 0.13) / 0.3 * math.pi)]) for y in ys]


def body_profile(y):
    """half-width, half-height of the body cross-section at y."""
    u = (y + 0.225) / 0.39          # 0 nose .. 1 tail base
    u = min(max(u, 0.0), 1.0)
    h = 0.060 * (math.sin(math.pi * min(u * 1.25, 1.0)) ** 0.7) * (1 - 0.65 * max(0.0, u - 0.55) / 0.45) + 0.004
    w = 0.040 * (math.sin(math.pi * min(u * 1.2, 1.0)) ** 0.6) * (1 - 0.6 * max(0.0, u - 0.55) / 0.45) + 0.003
    return w, h


def build_model():
    M = S.Model(band=0.02)
    fp = Q.flow_prim
    sp = spine_pts()
    back = (0, 1, 0)
    # body as a chain of ellipsoids along the spine
    ys = np.linspace(-0.215, 0.17, 14)
    for i, y in enumerate(ys):
        w, h = body_profile(y)
        c = np.array([0, y, 0.055 + 0.006 * math.cos((y + 0.13) / 0.3 * math.pi)])
        idx = int(np.clip(np.searchsorted(np.linspace(-0.13, 0.165, N_SP + 1), y) - 1, -1, N_SP - 1))
        bone = "head" if idx < 0 else f"spine_{idx + 1:02d}"
        fp(M, S.f_ellipsoid(c, (w, 0.034, h)), [c], bone, "body", 0.025, 0.02, back, "seg", pad=0.06)
    # mouth + barbels
    M.add(S.f_round_cone((0, -0.205, 0.05), (0, -0.228, 0.046), 0.012, 0.008), [(0, -0.205, 0.05)], "jaw", "lip", 0.006,
          0.006, "lip", pad=0.02)
    for sd in (1, -1):
        a = np.array([0.008 * sd, -0.215, 0.044])
        b = a + np.array([0.008 * sd, 0.004, -0.012])
        M.add(S.f_round_cone(a, b, 0.0018, 0.0009), [a, b], "jaw", "lip", 0.001, 0.004, "barbel", pad=0.004)
    # gill cover line
    M.carve(S.f_shell(S.f_ellipsoid((0, -0.158, 0.056), (0.05, 0.012, 0.062)), 0.0008), [(0, -0.158, 0.056)], k=0.0015,
            pad=0.06)
    fins = []

    def fin(name, root_a, root_b, tip, bone, thick=0.0012):
        # triangular fin: union of thin round cones fanning from the root edge to the tip
        def f(p):
            d = S.f_round_cone(root_a, tip, thick * 2, thick)(p)
            d = np.minimum(d, S.f_round_cone(root_b, tip + (root_b - root_a) * 0.3, thick * 2, thick)(p))
            # membrane: distance to the triangle plane, clipped to the triangle
            n = S.normalize(np.cross(root_b - root_a, tip - root_a))
            dp = np.abs((p - root_a) @ n) - thick
            q = p - ((p - root_a) @ n)[:, None] * n[None]
            inside = np.ones(len(p), bool)
            for a, b in ((root_a, root_b), (root_b, tip + (root_b - root_a) * 0.3), (tip + (root_b - root_a) * 0.3, tip),
                         (tip, root_a)):
                e = b - a
                cr = np.cross(e, q - a) @ n
                inside &= cr >= -1e-5
            return np.where(inside, np.minimum(dp, d), d)
        pts = [root_a, root_b, tip]
        pr = fp(M, f, pts, bone, "fin", 0.004, 0.012, tip - root_a, name, pad=0.01)
        fins.append(pr)

    for sd, nm in ((1, "L"), (-1, "R")):
        fin("pectoral", np.array([0.024 * sd, -0.15, 0.03]), np.array([0.022 * sd, -0.125, 0.026]),
            np.array([0.075 * sd, -0.105, 0.012]), f"pectoral_{nm}")
        fin("pelvic", np.array([0.016 * sd, -0.02, 0.016]), np.array([0.014 * sd, 0.0, 0.015]),
            np.array([0.045 * sd, 0.03, 0.004]), f"pelvic_{nm}")
    def vfin(name, poly, bone, thick=0.0013):
        """Median fin: planar polygon (y, z) in the x=0 plane, thin, rounded edges."""
        poly = np.asarray(poly, np.float64)

        def f(p):
            d2 = _poly_sdf(p[:, 1:3], poly)
            return np.sqrt(np.maximum(d2, 0) ** 2 + np.maximum(np.abs(p[:, 0]) - thick, 0) ** 2) + \
                np.minimum(np.maximum(d2, np.abs(p[:, 0]) - thick), 0)
        pts = [np.array([0, y, z]) for y, z in poly]
        fp(M, f, pts, bone, "fin", 0.004, 0.012, (0, 1, 0), name, pad=0.01)

    vfin("dorsal", [(-0.075, 0.100), (-0.055, 0.142), (-0.02, 0.14), (0.04, 0.118), (0.085, 0.092), (0.07, 0.085),
                    (-0.06, 0.098)], "dorsal")
    vfin("anal", [(0.065, 0.038), (0.10, 0.006), (0.118, 0.012), (0.105, 0.04)], "anal")
    vfin("caudal", [(0.150, 0.068), (0.150, 0.042), (0.215, -0.012), (0.262, -0.025), (0.235, 0.020), (0.222, 0.055),
                    (0.235, 0.090), (0.262, 0.135), (0.215, 0.122)], "tail_fin")
    for sd in (1, -1):
        e = np.array([0.026 * sd, -0.19, 0.068])
        M.add(S.f_sphere(e, 0.0085), [e], "head", "body", 0.003, 0.006, "eyebulge", pad=0.01)
    return M


def _poly_sdf(q, poly):
    """Signed distance from 2D points q (N,2) to a closed polygon (iq)."""
    n = len(poly)
    d = np.sum((q - poly[0]) ** 2, 1)
    sgn = np.ones(len(q))
    j = n - 1
    for i in range(n):
        e = poly[j] - poly[i]
        w = q - poly[i]
        t = np.clip((w @ e) / (e @ e), 0, 1)
        b = w - t[:, None] * e[None]
        d = np.minimum(d, np.sum(b * b, 1))
        c1 = q[:, 1] >= poly[i][1]
        c2 = q[:, 1] < poly[j][1]
        c3 = e[0] * w[:, 1] > e[1] * w[:, 0]
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        sgn = np.where(flip, -sgn, sgn)
        j = i
    return sgn * np.sqrt(d)


def bones():
    sp = spine_pts()
    t = lambda v: tuple(float(a) for a in v)  # noqa: E731
    U = (0, 0, 1)
    bl = [("root", (0, 0, 0), (0, 0.04, 0), None, U),
          ("head", t(sp[0]), (0, -0.225, 0.052), "root", U),
          ("jaw", (0, -0.2, 0.046), (0, -0.228, 0.044), "head", U)]
    prev = "root"
    for i in range(N_SP):
        nm = f"spine_{i + 1:02d}"
        bl.append((nm, t(sp[i]), t(sp[i + 1]), prev if i else "root", U))
        prev = nm
    bl += [("tail_fin", t(sp[-1]), (0, 0.24, 0.055), prev, U),
           ("dorsal", (0, -0.07, 0.105), (0, -0.03, 0.13), "spine_02", U),
           ("anal", (0, 0.07, 0.035), (0, 0.11, 0.012), "spine_05", U)]
    for sd, sg in (("L", 1), ("R", -1)):
        bl += [(f"pectoral_{sd}", (0.024 * sg, -0.14, 0.03), (0.07 * sg, -0.11, 0.013), "spine_01", U),
               (f"pelvic_{sd}", (0.016 * sg, -0.01, 0.016), (0.042 * sg, 0.025, 0.005), "spine_03", U)]
    return bl


def colour(P, N, lab, fl, s1, s2, names):
    K = len(P)
    li = {n: i for i, n in enumerate(names)}
    white = col("#ece8df")
    red = col("#d2471c")
    black = col("#151416")
    # kohaku-style red patches on the back (low-frequency noise, upper body only), sanke black spots
    n = X.fbm(P * np.array([1.6, 1.0, 1.0]), 14.0, 3, 21)
    top = sstep(0.035, 0.07, P[:, 2]) + sstep(-0.2, 0.5, N[:, 2]) * 0.6
    redm = sstep(0.0, 0.12, n + 0.35 * top - 0.35) * sstep(-0.2, 0.25, N[:, 2] + 0.25)
    head_cap = np.exp(-np.sum(((P - np.array([0, -0.175, 0.09])) / np.array([0.03, 0.03, 0.03])) ** 2, 1))
    redm = np.clip(redm + head_cap * 1.2, 0, 1)
    a = mix(white[None], red[None] * (0.9 + 0.15 * s1[:, None]), redm)
    d, cid, _ = X.cells(P, 0.05, 31)
    blk = sstep(0.016, 0.009, d) * (cid > 0.72) * (P[:, 2] > 0.06) * (P[:, 1] > -0.15)
    a = mix(a, black[None], blk * 0.9)
    # scales: reticulated pattern with darker edges, metallic-ish sheen (low roughness)
    sc, _, _ = X.cells(P * np.array([1.0, 1.25, 1.0]), 0.0075, 33)
    edge = sstep(0.0028, 0.0037, sc)
    a = a * (1 - 0.12 * edge)[:, None]
    rough = 0.22 + 0.1 * edge
    if "fin" in li:
        m = lab == li["fin"]
        rays = 0.5 + 0.5 * np.sin(np.arctan2(P[m, 2] - 0.055, P[m, 1] - 0.0) * 120)
        fa = mix(white[None] * 0.95, red[None], (redm[m] * 0.5)[:, None])
        a[m] = fa * (0.9 + 0.1 * rays[:, None])
        rough[m] = 0.3
    if "lip" in li:
        m = lab == li["lip"]
        a[m] = col("#e3b8a0")
        rough[m] = 0.35
    return a, rough, np.zeros(K)


class KoiAnim:
    def swim(self, t, speed=1.0, amp=1.0):
        T = CLIPS["swim"][0] / A.FPS
        u = t / T
        p = Pose()
        p.r("head", qz(3 * amp * math.sin(2 * math.pi * u)))
        for i in range(N_SP):
            a = amp * (3 + i * 2.4)
            p.r(f"spine_{i + 1:02d}", qz(a * math.sin(2 * math.pi * (u - 0.13 * (i + 1)))))
        p.r("tail_fin", qz(16 * amp * math.sin(2 * math.pi * (u - 0.95))))
        for sd in "LR":
            p.r(f"pectoral_{sd}", qy(-18 * math.sin(2 * math.pi * u * 2)) @ qz(10), sd)
            p.r(f"pelvic_{sd}", qy(-10 * math.sin(2 * math.pi * (u * 2 - 0.25))), sd)
        p.r("dorsal", qz(6 * math.sin(2 * math.pi * (u - 0.3))))
        p.r("jaw", qx(6 * max(0.0, math.sin(2 * math.pi * u * 2))))
        return p

    def idle(self, t):
        T = CLIPS["idle"][0] / A.FPS
        p = self.swim(t * (CLIPS["swim"][0] / A.FPS) * 3 / T, amp=0.35)
        p.r("jaw", qx(8 * max(0.0, math.sin(2 * math.pi * t * 1.2))))
        return p

    def bake_all(self, animator):
        for nm, (fr, loop) in CLIPS.items():
            animator.bake_clip(nm, getattr(self, nm), fr, loop)


def kit(cid):
    M = build_model()
    tex = Q.FurTex(M, colour, seed=2, strand=(2000.0, 2000.0), relief=0.00003, ao_mix=0.25)
    tex.height = _scale_height
    eyes = [(np.array([0.029, -0.19, 0.068]), 0.0065, (1, -0.3, 0.05)),
            (np.array([-0.029, -0.19, 0.068]), 0.0065, (-1, -0.3, 0.05))]
    return dict(model=M, bones=bones(), tex=tex, anim=KoiAnim(), eyes=eyes,
                warp=[(np.array([0, -0.18, 0.06]), 0.05, 1.3)], meta={"swim_speed": 0.35})


def _scale_height(P, lab):
    sc, _, fp = X.cells(P * np.array([1.0, 1.25, 1.0]), 0.0075, 33)
    # overlapping scales: raised toward the tail side of each cell
    rel = (P[:, 1] * 1.25 - fp[:, 1])
    return -0.00025 * sstep(0.0026, 0.0037, sc) + 0.00012 * np.clip(rel / 0.004, -1, 1)
