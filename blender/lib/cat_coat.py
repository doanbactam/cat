"""Procedural coat of Cam (orange mackerel tabby) and NPC variants, evaluated in 3D on
rest-pose positions/normals baked into UV space (so UV seams never break the pattern).

fields(P, N, part) -> dict of per-texel fields; albedo(fields, palette) -> linear RGB.
Pattern anatomy:
  * dorsal stripe along the spine, mackerel bars swept backwards down the flanks,
    breaking into dashes towards the belly; bullseye swirls over shoulders and thighs;
    necklaces across the chest; bars on the outer legs; rings on the tail + dark tip
  * head: forehead "M", parallel lines over the crown to the nape, mascara line from the
    outer eye corner, cheek swirl, dark eyeliner + pale eye ring, whisker-follicle dots
  * cream-white chin, muzzle, throat bib, belly, inner legs, toes; pink nose leather
    (darker rim, nostrils), rose paw pads, dark lip line, mouth interior, tongue, teeth
"""
from __future__ import annotations

import math

import numpy as np

import cat_anatomy as A
import cat_parts as PT
import cat_sdf as S
import cat_tex as TX
from cat_tex import fbm3, smoothstep, srgb_to_lin, hexc


def _poly_param(p, pts):
    """distance, arc-length param and unit tangent of the closest point on a polyline."""
    pts = [np.asarray(x, np.float64) for x in pts]
    best = np.full(len(p), np.inf)
    sbest = np.zeros(len(p))
    tbest = np.zeros((len(p), 3))
    s0 = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        ab = b - a
        L = np.linalg.norm(ab)
        t = np.clip(((p - a) @ ab) / (L * L), 0, 1)
        d = np.linalg.norm(p - (a + t[:, None] * ab), axis=1)
        upd = d < best
        best[upd] = d[upd]
        sbest[upd] = s0 + t[upd] * L
        tbest[upd] = ab / L
        s0 += L
    return best, sbest, tbest


def _line_dist2d(px, py, pts):
    """2D distance from points to a polyline (list of (x, y))."""
    best = np.full(px.shape, np.inf)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        abx, aby = bx - ax, by - ay
        L2 = abx * abx + aby * aby
        t = np.clip(((px - ax) * abx + (py - ay) * aby) / L2, 0, 1)
        dx = px - (ax + t * abx)
        dy = py - (ay + t * aby)
        best = np.minimum(best, np.sqrt(dx * dx + dy * dy))
    return best


def _line_dist3d(p, pts):
    d, s, _ = _poly_param(p, pts)
    return d, s


def fields(P: np.ndarray, N: np.ndarray, part: np.ndarray, seed: int = 1) -> dict:
    M = len(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    f = -y
    ax = np.abs(x)
    Pm = P.copy()
    Pm[:, 0] = ax
    F = {}
    n1 = fbm3(P * 60.0, 3, seed=seed)
    n2 = fbm3(P * 18.0, 3, seed=seed + 1)
    n3 = fbm3(P * 130.0, 2, seed=seed + 2)
    F["n_fine"] = n3
    F["n_mid"] = n1
    F["n_low"] = n2
    is_ear = part[:, 0] > 0.5
    is_teeth = part[:, 1] > 0.5
    is_tongue = part[:, 2] > 0.5
    skin = ~(is_ear | is_teeth | is_tongue)
    # ---------------- regions ----------------
    p0 = np.asarray(A.head_to_world((0.0, -0.149, 0.236)))
    n0 = np.asarray(A.head_dir_to_world((0.0, -0.991, 0.132)))
    head_w = smoothstep(-0.008, 0.006, (P - p0) @ n0)
    tp = np.asarray(A.tail_points())
    td, ts, ttan = _poly_param(P, tp)
    tail_w = smoothstep(0.002, 0.018, ts) * (td < 0.03) * (1 - head_w)
    fore_pts = [A.UPPERARM_L, A.FOREARM_L, A.HAND_L, A.FINGER_L, A.FINGER_TIP_L]
    hind_pts = [A.THIGH_L, A.SHIN_L, A.FOOT_L, A.TOE_L, A.TOE_TIP_L]
    fd, fs_, _ = _poly_param(Pm, fore_pts)
    hd, hs_, _ = _poly_param(Pm, hind_pts)
    lowleg_f = smoothstep(A.FOREARM_L[2] + 0.012, A.FOREARM_L[2] - 0.008, z) * (fd < 0.028) * (f > -0.03)
    lowleg_h = smoothstep(A.SHIN_L[2] + 0.004, A.SHIN_L[2] - 0.016, z) * (hd < 0.032) * (f < -0.05)
    leg_w = np.clip(lowleg_f + lowleg_h, 0, 1) * (1 - tail_w)
    torso_w = np.clip(1 - head_w - tail_w - leg_w, 0, 1)
    F["head_w"], F["tail_w"], F["leg_w"], F["torso_w"] = head_w, tail_w, leg_w, torso_w
    # head space
    ph = S.world_to_head(P)
    phm = ph.copy()
    phm[:, 0] = np.abs(phm[:, 0])
    hf = -ph[:, 1]
    # ---------------- torso tabby ----------------
    zc = 0.168 + 0.012 * smoothstep(-0.10, -0.21, f)
    theta = np.arctan2(ax, z - zc)               # 0 dorsal .. pi ventral
    F["theta"] = theta
    fw = f + 0.011 * theta + 0.0045 * n1 + 0.007 * n2
    lam = 0.0215 * (1.0 + 0.10 * fbm3(P * 9.0, 2, seed=seed + 3))
    band = 0.5 + 0.5 * np.cos(2 * math.pi * fw / lam)
    mack = smoothstep(0.60, 0.84, band + 0.16 * n3 + 0.06 * n1)
    brk = smoothstep(-0.18, 0.22, fbm3(P * 34.0, 3, seed=seed + 4))
    mack *= 1.0 - (1.0 - brk) * smoothstep(1.15, 2.0, theta)
    mack *= 1.0 - smoothstep(2.10, 2.55, theta + 0.25 * n2)
    dors = (1.0 - smoothstep(0.0075, 0.0125, ax + 0.0025 * n1)) * smoothstep(0.10, 0.45, N[:, 2])
    dors *= smoothstep(0.075, 0.055, f) * smoothstep(-0.235, -0.205, f)
    # shoulder + thigh swirls (rings around the joints)
    rs = np.linalg.norm(Pm - np.asarray(A.UPPERARM_L) - np.array([0.010, 0.0, 0.0]), axis=1)
    sh = smoothstep(0.62, 0.86, 0.5 + 0.5 * np.cos(2 * math.pi * (rs + 0.004 * n1) / 0.019))
    sh_w = (1 - smoothstep(0.030, 0.050, rs)) * smoothstep(0.03, 0.01, x * 0 + (0.03 - ax))
    rt = np.linalg.norm(Pm - np.asarray(A.THIGH_L) - np.array([0.022, 0.0, -0.01]), axis=1)
    th = smoothstep(0.60, 0.85, 0.5 + 0.5 * np.cos(2 * math.pi * (rt + 0.004 * n1) / 0.021))
    th_w = (1 - smoothstep(0.035, 0.060, rt)) * smoothstep(0.012, 0.030, ax)
    torso_str = mack
    # partial swirls only (upper arcs), mackerel cats show just a hint of them
    sh_w *= smoothstep(-0.1, 0.4, N[:, 2]) * 0.35
    th_w *= smoothstep(-0.2, 0.3, N[:, 2]) * 0.40
    torso_str = torso_str * (1 - sh_w) + sh * sh_w
    torso_str = torso_str * (1 - th_w) + th * th_w
    torso_str = np.maximum(torso_str, dors)
    # necklaces across the chest
    chest = smoothstep(0.04, 0.09, f) * smoothstep(0.215, 0.17, z)
    rn = f * 0.6 + (0.215 - z) * 0.8
    neck_band = smoothstep(0.66, 0.86, 0.5 + 0.5 * np.cos(2 * math.pi * (rn + 0.003 * n1) / 0.020))
    torso_str = torso_str * (1 - chest * 0.6) + neck_band * chest * 0.45
    # ---------------- legs ----------------
    lateral = np.stack([np.sign(x), np.zeros(M), np.zeros(M)], 1)
    outer = smoothstep(-0.35, 0.35, np.sum(N * lateral, 1))
    ang = np.arctan2(N[:, 1], N[:, 0] * np.sign(x + 1e-9))
    lb = 0.5 + 0.5 * np.cos(2 * math.pi * (z + 0.003 * ang + 0.002 * n1) / 0.0165)
    leg_str = smoothstep(0.62, 0.86, lb + 0.12 * n3) * outer * smoothstep(0.028, 0.045, z)
    # ---------------- tail ----------------
    tr = 0.5 + 0.5 * np.cos(2 * math.pi * (ts + 0.002 * n1) / (0.0300 - 0.006 * ts / A.TAIL_LENGTH))
    tail_str = smoothstep(0.55, 0.80, tr + 0.1 * n3)
    tip = smoothstep(A.TAIL_LENGTH - 0.040, A.TAIL_LENGTH - 0.012, ts)
    tail_str = np.maximum(tail_str, tip) * (1.0 - 0.45 * smoothstep(0.2, 0.8, -N[:, 2]))
    # ---------------- head ----------------
    hx, hz = phm[:, 0], ph[:, 2]
    front = smoothstep(0.15, 0.45, -N @ np.asarray(A.head_dir_to_world((0, 1, 0))))
    top = smoothstep(0.25, 0.55, N @ np.asarray(A.head_dir_to_world((0, 0, 1))))
    # forehead M (front view polylines in (x, z) head space)
    m_lines = [
        [(0.0040, 0.2585), (0.0042, 0.2700), (0.0048, 0.2830)],
        [(0.0105, 0.2600), (0.0118, 0.2720), (0.0135, 0.2840)],
        [(0.0060, 0.2600), (0.0120, 0.2625), (0.0185, 0.2640), (0.0245, 0.2610)],   # brow arc of the M
    ]
    dm = np.min([_line_dist2d(hx, hz, l) for l in m_lines], axis=0)
    m_str = (1 - smoothstep(0.0005, 0.0011, dm + 0.0004 * n3)) * front * (hf > 0.190)
    m_str *= 0.55 + 0.45 * smoothstep(-0.25, 0.25, fbm3(P * 70.0, 2, seed=seed + 12))
    # crown lines (front->back over the head into the nape)
    crown_x = np.array([0.0, 0.0058, 0.0125])
    dc = np.min(np.abs(hx[:, None] - crown_x[None, :] - 0.0007 * n1[:, None]), axis=1)
    crown = (1 - smoothstep(0.0005, 0.0012, dc)) * top * smoothstep(0.205, 0.195, hf) * smoothstep(0.125, 0.145, hf)
    crown *= 0.6 + 0.4 * smoothstep(-0.3, 0.3, fbm3(P * 45.0, 2, seed=seed + 7))
    # eyes: liner + pale ring, mascara line, cheek swirl
    c, g, u, v = S.eye_frame(1)
    q = phm - c
    am = S.almond2d(q @ u, q @ v, A.EYE_APERTURE_W, A.EYE_APERTURE_H)
    near_eye = (np.linalg.norm(q, axis=1) < A.EYE_RADIUS + 0.007) & ((q @ g) > -0.003)
    liner = near_eye * (1 - smoothstep(0.0005, 0.0010, am))
    pale = near_eye * smoothstep(0.0008, 0.0012, am) * (1 - smoothstep(0.0017, 0.0027, am + 0.0004 * n3))
    corner = c + u * (A.EYE_APERTURE_W * 0.5)
    masc_pts = [tuple(corner + np.array([0.001, 0.0, 0.0])), (corner[0] + 0.007, corner[1] + 0.010, corner[2] - 0.0005),
                (corner[0] + 0.012, corner[1] + 0.024, corner[2] - 0.003)]
    dmasc, smasc = _line_dist3d(phm, masc_pts)
    masc = (1 - smoothstep(0.0007 + 0.0003 * smasc / 0.03, 0.0014 + 0.0005 * smasc / 0.03, dmasc))
    swirl_pts = [(0.0245, -0.1985, 0.2390), (0.0300, -0.1880, 0.2350), (0.0350, -0.1760, 0.2380), (0.0370, -0.1660, 0.2450)]
    dsw, _ = _line_dist3d(phm, swirl_pts)
    swirl = 1 - smoothstep(0.0008, 0.0016, dsw + 0.0003 * n3)
    head_str = np.clip(np.maximum.reduce([m_str, crown, masc * 0.9, swirl * 0.8]), 0, 1)
    # nape stripes continue the crown lines down the neck
    nape = smoothstep(0.30, 0.6, N[:, 2]) * smoothstep(0.155, 0.145, hf) * smoothstep(0.05, 0.09, f)
    head_str = np.maximum(head_str, nape * (1 - smoothstep(0.0012, 0.0024, dc)))
    # ---------------- combine stripe ----------------
    stripe = torso_w * torso_str + leg_w * leg_str + tail_w * tail_str + head_w * head_str
    stripe = np.clip(stripe, 0, 1)
    # ---------------- white / cream areas ----------------
    pj = S.jaw_space(ph)
    chin = head_w * smoothstep(0.2195, 0.2150, pj[:, 2]) * smoothstep(0.168, 0.182, hf)
    pads = head_w * smoothstep(0.0048, 0.0002, S.ellipsoid(phm, A.WHISKER_PAD_L, (0.0102, 0.0090, 0.0098)) + 0.0010 * n3 + 0.0008 * n1)
    muzzle = np.clip(pads * 1.0, 0, 1)
    bib_n = np.asarray((0.0, -0.55, -0.83))
    bib = smoothstep(0.25, 0.6, N @ bib_n) * smoothstep(0.03, 0.08, f) * (1 - head_w * 0.0)
    bib *= smoothstep(0.235, 0.205, z + 0.006 * n2) * smoothstep(-0.2, 0.2, fbm3(P * 22, 2, seed=seed + 9) + 0.35)
    bib *= (1 - leg_w) * smoothstep(0.034, 0.018, ax + 0.004 * n1) * smoothstep(0.10, 0.13, z)
    belly = torso_w * smoothstep(2.30, 2.68, theta + 0.20 * n2 + 0.06 * n1)
    inner_leg = leg_w * smoothstep(0.1, -0.45, np.sum(N * lateral, 1))
    toes = smoothstep(0.024, 0.014, z + 0.002 * n1)
    tail_under = tail_w * smoothstep(0.4, 0.9, -N[:, 2]) * 0.4
    white = np.clip(np.maximum.reduce([chin, muzzle, bib, belly, inner_leg * 0.9, toes, tail_under]), 0, 1)
    F["white_pure"] = np.clip(np.maximum(chin, muzzle), 0, 1)
    # ---------------- bare skin regions ----------------
    nose_d = S.union([S.ellipsoid(ph, (0, -0.2190, 0.2368), (0.0072, 0.0050, 0.0030)),
                      S.ellipsoid(ph, (0, -0.2195, 0.2328), (0.0040, 0.0046, 0.0036))], 0.003)
    nose = head_w * (nose_d < 0.0007) * (hf > 0.2160) * smoothstep(-0.2, 0.3, -N @ np.asarray(A.head_dir_to_world((0, 1, 0))) + 0.4)
    nose_rim = nose * smoothstep(-0.0004, 0.0006, nose_d)
    nostril = head_w * smoothstep(0.0004, 0.0, S.ellipsoid(phm, (0.0040, -0.2240, 0.2330), (0.0017, 0.0014, 0.0009), S.rot_axis((0, 1, 0), 35.0)))
    mc = S.mouth_carve(ph)
    mouth = head_w * (mc < 0.00025) * skin
    lips = head_w * (mc >= 0.00025) * smoothstep(0.0010, 0.0005, mc) * smoothstep(0.190, 0.198, hf) * skin
    socket = (np.linalg.norm(q, axis=1) < A.EYE_RADIUS + 0.0007) * head_w
    # paw pads (beans): near the bean ellipsoids on the underside
    beans = np.full(M, np.inf)
    for (cx, cf), toes_x, toes_f, zb, rb, padc, padr in (
            ((0.031, 0.0), (-0.0112, -0.0037, 0.0037, 0.0112), (0.1070, 0.1125, 0.1125, 0.1070), 0.0040,
             (0.0040, 0.0046, 0.0030), (0.031, 0.0925, 0.0044), (0.0092, 0.0064, 0.0034)),
            ((0.031, 0.0), (-0.0095, -0.0032, 0.0032, 0.0095), (-0.1410, -0.1365, -0.1365, -0.1410), 0.0038,
             (0.0036, 0.0042, 0.0028), (0.031, -0.1560, 0.0042), (0.0085, 0.0070, 0.0032))):
        for tx, tf in zip(toes_x, toes_f):
            beans = np.minimum(beans, S.ellipsoid(Pm, S.F(cx + tx, tf, zb), rb))
        beans = np.minimum(beans, S.ellipsoid(Pm, S.F(*padc), padr))
    carpal = S.ellipsoid(Pm, A.CARPAL_PAD_L, (0.0040, 0.0034, 0.0050))
    pad = ((beans < 0.0011) & (N[:, 2] < 0.15)) | (carpal < 0.0009)
    pad = pad.astype(np.float64) * (z < 0.05)
    # ears
    inner_ear = np.zeros(M)
    ear_h = np.zeros(M)
    ear_u = np.zeros(M)
    for sx in (1, -1):
        base, a, n, b = PT.ear_frame(sx)
        nw = np.asarray(A.head_dir_to_world(tuple(n)))
        side = (np.sign(x) == sx) & is_ear
        inner_ear = np.where(side, smoothstep(0.0, 0.35, N @ nw), inner_ear)
        ear_h = np.where(side, np.clip(((ph - base) @ a) / PT.EAR_H, 0, 1), ear_h)
        hh = np.clip(((ph - base) @ a) / PT.EAR_H, 0, 1)
        wv = 0.5 * PT.EAR_W * (1 - hh) ** 0.8 + 1e-4
        ear_u = np.where(side, np.clip(((ph - base) @ b) / wv, -1.2, 1.2), ear_u)
    F.update(stripe=stripe, white=white, nose=nose, nose_rim=nose_rim, nostril=nostril.astype(float), mouth=mouth,
             lips=lips, socket=socket, pad=pad, ear=is_ear.astype(float), inner_ear=inner_ear, ear_h=ear_h, ear_u=ear_u,
             teeth=is_teeth.astype(float), tongue=is_tongue.astype(float), liner=liner * head_w, pale=pale * head_w,
             chin=chin, muzzle=muzzle, belly=belly, toes=toes, tail_tip=tip * tail_w, follicle=_follicles(phm) * head_w)
    F["palate"] = mouth * smoothstep(0.3, 0.7, -N @ np.asarray(A.head_dir_to_world((0, 0, 1)))) * \
        (0.5 + 0.5 * np.cos(2 * math.pi * hf / 0.0028))
    # ---------------- fur flow (object space) ----------------
    back = np.array([0.0, 1.0, 0.0])
    down = np.array([0.0, 0.0, -1.0])
    flow_t = back[None] + down[None] * (0.45 * np.sin(np.clip(theta, 0, math.pi)))[:, None]
    flow_chest = np.tile(np.array([0.0, 0.45, -1.0]), (M, 1))
    flow_leg = np.tile(np.array([0.0, 0.20, -1.0]), (M, 1))
    flow_tail = ttan
    nose_w = np.asarray(A.head_to_world((0.0, -0.2230, 0.2380)))
    flow_head = (P - nose_w) + np.asarray(A.head_dir_to_world((0, 1.0, 0.0)))[None] * 0.012
    flow_ear = np.zeros((M, 3))
    for sx in (1, -1):
        base, a, n, b = PT.ear_frame(sx)
        flow_ear[np.sign(x) == sx] = np.asarray(A.head_dir_to_world(tuple(a)))
    ch = np.clip(bib * 1.0 + chest * 0.5, 0, 1)[:, None]
    flow = flow_t * (1 - ch) + flow_chest * ch
    flow = flow * torso_w[:, None] + flow_leg * leg_w[:, None] + flow_tail * tail_w[:, None] + \
        (flow_head / (np.linalg.norm(flow_head, axis=1, keepdims=True) + 1e-9)) * head_w[:, None]
    flow = np.where(is_ear[:, None], flow_ear, flow)
    flow -= np.sum(flow * N, 1, keepdims=True) * N
    flow /= np.linalg.norm(flow, axis=1, keepdims=True) + 1e-9
    F["flow"] = flow
    # ---------------- fur length / density ----------------
    L = np.full(M, 0.55)
    L = L + 0.25 * smoothstep(1.7, 2.4, theta) * torso_w             # belly
    L = np.maximum(L, 0.85 * bib)
    neck_ruff = smoothstep(0.06, 0.10, f) * (1 - head_w) * smoothstep(0.17, 0.20, z)
    L = np.maximum(L, 0.78 * neck_ruff)
    L = L * (1 - leg_w) + leg_w * (0.42 - 0.22 * smoothstep(0.06, 0.02, z))
    L = L * (1 - tail_w) + tail_w * (0.80 - 0.15 * tip)
    cheek = smoothstep(0.022, 0.032, phm[:, 0]) * smoothstep(0.245, 0.235, ph[:, 2])
    face_len = 0.42 * (1 - front * 0.5) + 0.33 * cheek
    face_len = np.where(muzzle > 0.5, 0.14, face_len)
    face_len = np.minimum(face_len, 0.12 + 0.6 * smoothstep(0.0015, 0.008, am + 1.0 * (~near_eye)))
    L = L * (1 - head_w) + head_w * face_len
    L = np.where(is_ear, 0.10 + 0.15 * inner_ear * smoothstep(0.1, 0.35, 1 - ear_h), L)
    bare = np.clip(np.maximum.reduce([nose, mouth, lips * 0.8, socket, pad, F["teeth"], F["tongue"]]), 0, 1)
    L = L * (1 - bare)
    D = np.ones(M) * (1 - 0.2 * belly) * (1 - bare)
    D = np.where(is_ear, 1 - 0.7 * inner_ear, D)
    L = L * (0.92 + 0.08 * n1)
    F["fur_len"] = np.clip(L, 0, 1)
    F["fur_den"] = np.clip(D, 0, 1)
    F["bare"] = bare
    return F


def _follicles(phm):
    """Dark whisker-follicle dots on the whisker pads (4 rows x 5)."""
    pad = np.asarray(A.WHISKER_PAD_L)
    best = np.full(len(phm), np.inf)
    for r in range(4):
        for c in range(5):
            pt = pad + np.array([0.0055 + 0.0006 * r, -(c - 2) * 0.0026 - 0.0004 * r, (1.5 - r) * 0.0021])
            best = np.minimum(best, np.linalg.norm(phm - pt, axis=1))
    return 1 - smoothstep(0.00045, 0.00085, best)


# ===========================================================================
# palettes / albedo
# ===========================================================================
PALETTES = {
    "cam": dict(ground=hexc("e3a25c"), ground2=hexc("d48843"), stripe=hexc("b25d26"), stripe_dark=hexc("97481b"),
                cream=hexc("efd6ad"), white=hexc("eae1cf"), nose=hexc("dc8f88"), nose_rim=hexc("b7655f"),
                pad=hexc("c98179"), lips=hexc("a05c50"), liner=hexc("6a3018"), inner_ear=hexc("d9a29b"),
                stripe_strength=1.0, tabby=True),
    "grey_tabby": dict(ground=hexc("a8a196"), ground2=hexc("8f877c"), stripe=hexc("3c3632"), stripe_dark=hexc("2c2724"),
                       cream=hexc("d9d2c4"), white=hexc("e4ded3"), nose=hexc("a8655c"), nose_rim=hexc("5a3a36"),
                       pad=hexc("4a3a37"), lips=hexc("3a2c2a"), liner=hexc("2a2220"), inner_ear=hexc("c9a39b"),
                       stripe_strength=0.95, tabby=True, grizzle=0.25),
    "black": dict(ground=hexc("2c2522"), ground2=hexc("231e1c"), stripe=hexc("1e1a19"), stripe_dark=hexc("1b1716"),
                  cream=hexc("2e2724"), white=hexc("302926"), nose=hexc("3d3534"), nose_rim=hexc("2a2423"),
                  pad=hexc("332b2a"), lips=hexc("2a2322"), liner=hexc("221c1b"), inner_ear=hexc("6a5552"),
                  stripe_strength=0.35, tabby=True, rust=0.10),
    "white": dict(ground=hexc("ebe5da"), ground2=hexc("e4dccd"), stripe=hexc("e2d8c8"), stripe_dark=hexc("ddd2c0"),
                  cream=hexc("ede7dd"), white=hexc("eee9e0"), nose=hexc("e5a29d"), nose_rim=hexc("d08a85"),
                  pad=hexc("dd9c96"), lips=hexc("c9908a"), liner=hexc("c7a49a"), inner_ear=hexc("e8b8b2"),
                  stripe_strength=0.0, tabby=False),
    "calico": dict(ground=hexc("e09a52"), ground2=hexc("d2803a"), stripe=hexc("b8642a"), stripe_dark=hexc("a0541f"),
                   cream=hexc("ece4d6"), white=hexc("ece5d8"), nose=hexc("dc9a92"), nose_rim=hexc("b8726b"),
                   pad=hexc("cf8f88"), lips=hexc("9a6058"), liner=hexc("4a2f22"), inner_ear=hexc("ddaaa3"),
                   stripe_strength=0.35, tabby=True, calico=True, black=hexc("2b2421")),
}


def albedo(F: dict, P: np.ndarray, pal_name: str = "cam", seed: int = 1) -> np.ndarray:
    pal = {k: (srgb_to_lin(v) if isinstance(v, np.ndarray) else v) for k, v in PALETTES[pal_name].items()}
    M = len(P)
    n_low, n_mid, n_fine = F["n_low"], F["n_mid"], F["n_fine"]
    # ground colour: warmer/darker on the back, paler on the flanks
    dorsal_dark = smoothstep(1.4, 0.2, F["theta"]) * F["torso_w"]
    ground = TX.lerp(pal["ground"], pal["ground2"], np.clip(0.55 * dorsal_dark + 0.25 * (0.5 + 0.5 * n_low), 0, 1))
    stripe_col = TX.lerp(pal["stripe"], pal["stripe_dark"], np.clip(dorsal_dark + F["tail_tip"], 0, 1))
    hs1, hs2 = hair_streaks(P, F["flow"], seed + 70)
    # markings feather along the hair direction (stripe edges break into strands)
    st = smoothstep(0.18, 0.82, F["stripe"] + 0.32 * hs2 * smoothstep(0.02, 0.35, F["stripe"]) * smoothstep(0.98, 0.6, F["stripe"]))
    st = st * pal["stripe_strength"]
    col = TX.lerp(ground, stripe_col, st)
    if pal.get("calico"):
        patch = fbm3(P * 9.0, 3, seed=seed + 40)
        blk = smoothstep(0.05, 0.12, patch)
        org = smoothstep(-0.12, -0.05, patch) * (1 - blk)
        col = np.where((blk > 0.5)[:, None], TX.lerp(pal["black"], pal["black"] * 1.25, 0.5 + 0.5 * n_mid), col)
        col = TX.lerp(col, pal["cream"], np.clip(1 - org - blk, 0, 1) * 0.0)
        whiteness = np.clip(F["white"] * 1.4 + smoothstep(1.4, 2.2, F["theta"]) * F["torso_w"] + F["leg_w"] * 0.6, 0, 1)
        col = TX.lerp(col, pal["white"], whiteness)
    # cream/white areas (edges feathered by the hair streaks)
    wcol = TX.lerp(pal["cream"], pal["white"], np.clip(F["white_pure"] + F["toes"] * 0.5, 0, 1))
    wmask = smoothstep(0.08, 0.92, F["white"] + 0.25 * hs2 * smoothstep(0.02, 0.4, F["white"]) * smoothstep(0.98, 0.6, F["white"]))
    col = TX.lerp(col, wcol, wmask * (0.88 + 0.12 * smoothstep(-0.2, 0.2, n_mid)))
    # eye ring
    col = TX.lerp(col, pal["cream"], F["pale"] * 0.55)
    col = TX.lerp(col, pal["liner"], F["liner"])
    col = TX.lerp(col, pal["stripe_dark"] * 0.8, F["follicle"] * 0.85)
    if pal.get("rust"):
        col = col * (1 + pal["rust"] * np.array([1.0, 0.45, 0.1]) * (0.5 + 0.5 * n_low)[:, None] * smoothstep(1.4, 0.2, F["theta"])[:, None])
    if pal.get("grizzle"):
        gz = pal["grizzle"] * F["head_w"] * smoothstep(0.0, 0.6, fbm3(P * 400.0, 1, seed=seed + 50))
        col = TX.lerp(col, pal["white"], gz)
    # ears: back = ground, darker rim/tip; cavity = pink skin with pale sparse hair
    ear_back = TX.lerp(pal["ground2"], pal["stripe_dark"], smoothstep(0.65, 1.0, F["ear_h"]) * 0.6)
    ear_in = TX.lerp(pal["inner_ear"] * 0.92, pal["inner_ear"] * 1.08, smoothstep(0.0, 0.8, F["ear_h"]))
    ear_hair = smoothstep(0.55, 1.0, np.abs(F["ear_u"])) + smoothstep(0.35, 0.0, F["ear_h"])
    ear_hair = np.clip(ear_hair, 0, 1) * smoothstep(-0.1, 0.5, hs1 + 0.2)
    ear_in = TX.lerp(ear_in, pal["cream"], 0.75 * ear_hair)
    ecol = TX.lerp(ear_back, ear_in, F["inner_ear"])
    col = np.where(F["ear"][:, None] > 0.5, ecol, col)
    # bare skin
    nose_col = TX.lerp(pal["nose"], pal["nose_rim"], F["nose_rim"] * 0.9)
    nose_col = nose_col * (1 + 0.06 * n_fine)[:, None]
    col = TX.lerp(col, nose_col, F["nose"])
    col = TX.lerp(col, pal["nose_rim"] * 0.75, F["nostril"] * 0.8)
    col = TX.lerp(col, pal["lips"], F["lips"])
    mouth_col = TX.lerp(srgb_to_lin(hexc("8e3a40")), srgb_to_lin(hexc("b85a62")), F["palate"])
    col = TX.lerp(col, mouth_col, F["mouth"])
    pad_col = pal["pad"] * (1 + 0.10 * n_fine)[:, None]
    col = TX.lerp(col, pad_col, F["pad"])
    col = TX.lerp(col, srgb_to_lin(hexc("3a201c")), F["socket"])
    tongue = srgb_to_lin(hexc("d47f86")) * (1 + 0.12 * fbm3(P * 900.0, 1, seed=seed + 60))[:, None]
    col = np.where(F["tongue"][:, None] > 0.5, tongue, col)
    teeth = srgb_to_lin(hexc("e9e2d0"))
    col = np.where(F["teeth"][:, None] > 0.5, np.broadcast_to(teeth, col.shape), col)
    # fine fur variation (agouti-ish clumps), only on furred texels
    fur = 1 - F["bare"]
    col = col * (1 + fur[:, None] * (0.13 * hs1 + 0.05 * hs2 + 0.04 * n_fine + 0.04 * n_mid)[:, None])
    return np.clip(col, 0.0, 0.85)


def hair_streaks(P: np.ndarray, flow: np.ndarray, seed: int = 70):
    """Anisotropic noise: ~0.4 mm across x 9 mm along the hair (hs1) and coarser clumps (hs2)."""
    along = np.sum(P * flow, 1)
    across = P - along[:, None] * flow
    h1 = TX.perlin3(across * 2600.0 + flow * (along * 110.0)[:, None], seed)
    h2 = 0.65 * TX.perlin3(across * 950.0 + flow * (along * 45.0)[:, None], seed + 1) + \
        0.35 * TX.perlin3(across * 2100.0 + flow * (along * 80.0)[:, None], seed + 2)
    return h1, h2


def roughness(F: dict) -> np.ndarray:
    r = 0.74 + 0.07 * F["n_mid"] + 0.03 * F["n_fine"]
    r = np.where(F["ear"] > 0.5, 0.62 + 0.1 * (1 - F["inner_ear"]), r)
    r = r * (1 - F["nose"]) + 0.40 * F["nose"]
    r = r * (1 - F["pad"]) + 0.55 * F["pad"]
    r = r * (1 - F["lips"]) + 0.45 * F["lips"]
    r = r * (1 - F["mouth"]) + 0.30 * F["mouth"]
    r = np.where(F["tongue"] > 0.5, 0.36, r)
    r = np.where(F["teeth"] > 0.5, 0.22, r)
    r = r * (1 - F["socket"]) + 0.45 * F["socket"]
    return np.clip(r, 0.05, 1.0)


def strand_height(P: np.ndarray, flow: np.ndarray, fur_len: np.ndarray, seed: int = 5) -> np.ndarray:
    """Anisotropic noise stretched along the fur flow: clumps of hair strands."""
    along = np.sum(P * flow, 1)
    across = P - along[:, None] * flow
    q = across * 2200.0 + flow * (along * 260.0)[:, None]
    h = 0.6 * fbm3(q, 2, seed=seed) + 0.4 * fbm3(across * 700.0 + flow * (along * 90.0)[:, None], 2, seed=seed + 1)
    return h * (0.4 + 0.6 * fur_len)
