"""Signed-distance model of Cam's body (skin + compressed fur), numpy-vectorised.

The body is a smooth union of anatomical primitives (ribcage, scapulae, haunches,
calf, hock, toes, whisker pads ...) followed by carving operations (mouth slot +
cavity, eye apertures with lid margins, nostrils, philtrum, toe separations).
Ears, eyes, teeth, tongue and whiskers are separate parametric meshes.

All functions take P: (N, 3) float64 array of Blender object-space points.
"""
from __future__ import annotations

import math

import numpy as np

import cat_anatomy as A


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def V(*a) -> np.ndarray:
    if len(a) == 1:
        a = a[0]
    return np.asarray(a, dtype=np.float64)


def F(x, f, z) -> np.ndarray:
    return V(A.F(x, f, z))


def length(q: np.ndarray) -> np.ndarray:
    return np.sqrt(np.einsum("ij,ij->i", q, q))


def normalize(v) -> np.ndarray:
    v = V(v)
    return v / np.linalg.norm(v)


def sphere(p, c, r):
    return length(p - V(c)) - r


def ellipsoid(p, c, r, R=None):
    """iq's ellipsoid bound. R: 3x3 with local axes as columns (world)."""
    q = p - V(c)
    if R is not None:
        q = q @ R
    r = V(r)
    k0 = length(q / r)
    k1 = length(q / (r * r))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-12)


def frame(axis_y, hint_x) -> np.ndarray:
    """Orthonormal frame (columns x, y, z) with y along axis_y, x close to hint_x."""
    y = normalize(axis_y)
    x = V(hint_x) - np.dot(V(hint_x), y) * y
    x = x / np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], axis=1)


def seg_ellipsoid(p, a, b, r_side, r_other, side=(1, 0, 0), extend=0.0):
    """Ellipsoid spanning segment a-b (half length |b-a|/2 + extend)."""
    a, b = V(a), V(b)
    c = (a + b) * 0.5
    R = frame(b - a, side)
    hl = np.linalg.norm(b - a) * 0.5 + extend
    return ellipsoid(p, c, (r_side, hl, r_other), R)


def round_cone(p, a, b, r1, r2):
    """iq's exact round cone (capsule with radius r1 at a, r2 at b)."""
    a, b = V(a), V(b)
    ba = b - a
    l2 = float(ba @ ba)
    rr = r1 - r2
    a2 = l2 - rr * rr
    il2 = 1.0 / l2
    pa = p - a
    y = pa @ ba
    z = y - l2
    xv = pa * l2 - y[:, None] * ba
    x2 = np.einsum("ij,ij->i", xv, xv)
    y2 = y * y * l2
    z2 = z * z * l2
    k = math.copysign(1.0, rr) * rr * rr * x2 if rr != 0 else np.zeros_like(x2)
    d_b = np.sqrt(x2 + z2) * il2 - r2
    d_a = np.sqrt(x2 + y2) * il2 - r1
    d_m = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
    return np.where(np.sign(z) * a2 * z2 > k, d_b, np.where(np.sign(y) * a2 * y2 < k, d_a, d_m))


def squash(p, c, axis, s):
    """Evaluate a primitive squashed by factor s along `axis` around c:
    returns (q, scale) -> call prim(q) * scale."""
    n = normalize(axis)
    t = (p - V(c)) @ n
    return p + np.outer(t * (1.0 / s - 1.0), n), s


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    return -smin(-a, -b, k)


def rot_axis(axis, deg) -> np.ndarray:
    ax = normalize(axis)
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    x, y, z = ax
    return np.array([
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ])


def union(ds, k):
    d = ds[0]
    for e in ds[1:]:
        d = smin(d, e, k)
    return d


# ---------------------------------------------------------------------------
# eye helpers (shared with the eyeball mesh builder)
# ---------------------------------------------------------------------------
def eye_frame(side: int = 1):
    """Returns (centre, gaze, u_horizontal, v_up) for the left (1) / right (-1) eye."""
    c = V(A.EYE_L) * V(side, 1, 1)
    out = math.radians(A.EYE_GAZE_OUT_DEG)
    up = math.radians(A.EYE_GAZE_UP_DEG)
    g = normalize((side * math.sin(out) * math.cos(up), -math.cos(out) * math.cos(up), math.sin(up)))
    u = normalize(np.cross(g, V(0, 0, 1)))       # points to the cat's left for +gaze..
    if u[0] * side < 0:
        u = -u                                   # u points laterally (outer corner)
    v = normalize(np.cross(u, g))
    if v[2] < 0:
        v = -v
    # tilt the aperture: outer corner higher
    tilt = math.radians(A.EYE_APERTURE_TILT_DEG)
    u2 = u * math.cos(tilt) + v * math.sin(tilt)
    v2 = -u * math.sin(tilt) + v * math.cos(tilt)
    return c, g, u2, v2


def aperture_frame(side: int = 1):
    """Eye frame of the lid opening: the gaze frame yawed outwards by EYE_APERTURE_OUT_DEG about
    the aperture's up axis (a cat's palpebral fissure faces more laterally than its visual
    axis, so the lateral lid sits further back and the cornea shows in profile)."""
    c, g, u, v = eye_frame(side)
    R = rot_axis(v, A.EYE_APERTURE_OUT_DEG)
    if (R @ g)[0] * side < g[0] * side:
        R = rot_axis(v, -A.EYE_APERTURE_OUT_DEG)
    return c, R @ g, R @ u, v


def almond2d(qu, qv, w, h, up_frac=None):
    """2D SDF-ish of an almond aperture centred at 0 (corners at +-w/2, 0)."""
    if up_frac is None:
        up_frac = A.EYE_APERTURE_UP_FRAC
    a = w * 0.5
    bu = h * up_frac
    bl = h * (1.0 - up_frac)
    cu = (bu * bu - a * a) / (2 * bu)
    ru = bu - cu
    cl = (a * a - bl * bl) / (2 * bl)
    rl = cl + bl
    du = np.sqrt(qu * qu + (qv - cu) ** 2) - ru
    dl = np.sqrt(qu * qu + (qv - cl) ** 2) - rl
    return smax(du, dl, 0.0016)          # rounded canthi (no sliver triangles at the corners)


# ---------------------------------------------------------------------------
# body parts
# ---------------------------------------------------------------------------
def world_to_head(p):
    """World points -> head design space (inverse of cat_anatomy.head_to_world)."""
    piv = V(A.HEAD_PIVOT)
    R = np.array(A._head_rot())
    q = p - piv - V(A.HEAD_LIFT)
    q = q @ R          # R^T applied to row vectors
    return A.muzzle_unwarp(piv + q / A.HEAD_SCALE)


def jaw_space(p, open_deg=None):
    """Map head-space points into 'closed jaw' coordinates (jaw rotated open by open_deg)."""
    if open_deg is None:
        open_deg = A.JAW_REST_OPEN_DEG
    h = V(A.JAW)
    R = rot_axis((1, 0, 0), -open_deg)   # inverse of opening (+X rotation opens)
    return (p - h) @ R.T + h


def torso(p):
    d = union([
        ellipsoid(p, F(0, 0.036, 0.171), (0.0440, 0.088, 0.054)),         # ribcage
        ellipsoid(p, F(0, 0.068, 0.143), (0.0255, 0.042, 0.029)),         # sternum keel
        ellipsoid(p, F(0, -0.060, 0.170), (0.0425, 0.086, 0.046)),        # abdomen
        round_cone(p, F(0, 0.066, 0.204), F(0, -0.150, 0.208), 0.031, 0.034),  # epaxial muscles
        ellipsoid(p, F(0, 0.070, 0.216), (0.026, 0.042, 0.029)),          # withers
        ellipsoid(p, F(0, -0.168, 0.201), (0.036, 0.058, 0.040)),         # pelvis / croup
        ellipsoid(p, F(0, -0.203, 0.191), (0.032, 0.030, 0.037)),         # rump
        ellipsoid(p, F(0, -0.104, 0.138), (0.031, 0.054, 0.024)),         # primordial pouch
    ], 0.030)
    return d


def torso_detail(p, pm):
    # ilium wings + spine ridge (subtle)
    d = union([
        ellipsoid(pm, F(0.018, -0.140, 0.223), (0.014, 0.020, 0.012)),
        round_cone(p, F(0, 0.040, 0.230), F(0, -0.120, 0.233), 0.006, 0.006),
    ], 0.01)
    return d


def neck(p):
    return union([
        round_cone(p, F(0, 0.078, 0.190), F(0, 0.148, 0.250), 0.037, 0.030),
        ellipsoid(p, F(0, 0.126, 0.192), (0.024, 0.032, 0.022)),          # throat
        ellipsoid(p, F(0, 0.114, 0.212), (0.038, 0.028, 0.036)),          # neck ruff
    ], 0.022)


def head_upper(p, pm):
    """Skull, face and upper lip (p, pm in head design space)."""
    cran = union([
        ellipsoid(p, F(0, 0.170, 0.2515), (0.0305, 0.0365, 0.0236)),      # cranium (narrower, flatter dome)
        ellipsoid(p, F(0, 0.150, 0.2440), (0.0262, 0.0250, 0.0255)),      # occiput
        ellipsoid(p, F(0, 0.1925, 0.2600), (0.0200, 0.0185, 0.0115)),     # forehead
        ellipsoid(p, F(0, 0.1965, 0.2455), (0.0265, 0.0170, 0.0180)),     # orbital plate (eyes sit in it)
    ], 0.012)
    face = union([
        ellipsoid(pm, F(0.0150, 0.2072, 0.2588), (0.0098, 0.0074, 0.0050)),  # brow ridge over the upper lid
        ellipsoid(pm, F(0.0254, 0.1940, 0.2390), (0.0118, 0.0180, 0.0100)),  # zygomatic arch (wide cheekbones)
        ellipsoid(pm, F(0.0160, 0.2060, 0.2385), (0.0078, 0.0085, 0.0055)),  # infra-orbital (lower lid support)
        ellipsoid(pm, F(0.0236, 0.1730, 0.2300), (0.0104, 0.0205, 0.0125)),  # cheek / jowl ruff (lighter jowls)
        round_cone(p, F(0, 0.2070, 0.2525), F(0, 0.2200, 0.2385), 0.0082, 0.0068),  # nose bridge
        ellipsoid(p, F(0, 0.2045, 0.2310), (0.0128, 0.0125, 0.0118)),       # muzzle core
    ], 0.008)
    d = smin(cran, face, 0.010)
    pads = ellipsoid(pm, A.WHISKER_PAD_L, (0.0078, 0.0066, 0.0062))         # whisker pads
    flews = ellipsoid(pm, F(0.0108, 0.2045, 0.2212), (0.0056, 0.0092, 0.0053))  # upper lip flews over the jaw
    corner = ellipsoid(pm, F(0.0128, 0.1935, 0.2200), (0.0048, 0.0060, 0.0048))  # lip commissure tissue
    curtain = ellipsoid(pm, F(0.0022, 0.2166, 0.2188), (0.0058, 0.0036, 0.0046))  # midline upper lip (covers the lower lip)
    lip = smin(smin(smin(flews, curtain, 0.003), corner, 0.004), pads, 0.0075)
    d = smin(d, lip, 0.0085)
    nose = union([
        ellipsoid(p, F(0, 0.2192, 0.2366), (0.0066, 0.0048, 0.0030)),      # nose leather top (wide)
        ellipsoid(p, F(0, 0.2196, 0.2330), (0.0038, 0.0045, 0.0034)),      # tapering lower point
    ], 0.003)
    d = smin(d, nose, 0.0045)
    return d


def head_jaw(p):
    pj = jaw_space(p)
    pjm = pj.copy()
    pjm[:, 0] = np.abs(pjm[:, 0])
    return union([
        round_cone(pjm, F(0.0215, 0.166, 0.2150), F(0.0052, 0.2030, 0.2125), 0.0076, 0.0054),  # mandible
        ellipsoid(pj, F(0, 0.2125, 0.2132), (0.0070, 0.0066, 0.0050)),        # chin (small, forward)
        ellipsoid(pj, F(0, 0.1815, 0.2112), (0.0146, 0.0200, 0.0062)),        # jaw underside
        round_cone(pjm, F(0.0098, 0.1965, 0.2160), F(0.0, 0.2145, 0.2158), 0.0023, 0.0026),  # lower lip
    ], 0.006)


MOUTH_GAP = 0.0007          # air gap kept between the lower jaw and the upper lip / palate


def mouth_carve(p):
    """Negative inside the mouth (head space; to be subtracted).  A thin shell around the
    lower jaw's upper/front surface separates it from the upper lip -- the upper lip
    (curtain + flews) hangs in front of the lower lip, so the lip line opens downwards and is
    hidden from the front like a real cat's -- plus the oral cavity."""
    jd = head_jaw(p)
    pj = jaw_space(p)
    f = -p[:, 1]
    shell = smax(-jd, jd - MOUTH_GAP, 0.0002)
    upper_part = 0.2128 - pj[:, 2]                            # only the jaw's top / lip region
    lateral = np.abs(p[:, 0]) - (0.0098 + 0.22 * np.clip(f - 0.193, 0, 0.02))
    behind = 0.1925 - f                                        # mouth corner (commissure)
    gap = smax(smax(shell, upper_part, 0.0008), smax(lateral, behind, 0.0010), 0.0008)
    cavity = ellipsoid(p, F(0, 0.1885, 0.2182), (0.0088, 0.0200, 0.0044))
    pm = p.copy()
    pm[:, 0] = np.abs(pm[:, 0])
    vestibule = ellipsoid(pm, F(0.0074, 0.2050, 0.2192), (0.0022, 0.0036, 0.0026))   # room for the canines behind the flews
    return smin(smin(gap, cavity, 0.0015), vestibule, 0.0012)


def eye_carve(pm):
    c, g, u, v = aperture_frame(1)
    q = pm - c
    s = q @ g
    qu, qv = q @ u, q @ v
    prism = almond2d(qu, qv, A.EYE_APERTURE_W, A.EYE_APERTURE_H)
    front = smax(prism, -s, 0.0008)
    # thin clearance shell between eyeball and lids, only just behind the lid margins (the lid
    # margin sits at s ~ 0.6 R at the canthi, ~0.85-0.9 R top/bottom): a deep 0.35 mm slit cannot be resolved by the ~1.5 mm game
    # mesh and folded into flaps at the canthi once the eye was sunk into the orbit
    socket = smax(sphere(pm, c, A.EYE_RADIUS + 0.00035), A.EYE_RADIUS * 0.72 - s, 0.0008)
    return smin(front, socket, 0.0006)


# Periorbital fill (design metres): an ellipsoid centred behind the eyeball, in the eye frame,
# whose front surface lies just over the eyeball at the aperture rim.  It fills the dish that a
# bare lid sphere leaves between eyeball, brow, cheek and nose bridge, so the eye reads as an
# almond opening in the face (lids overlapping the cornea) instead of a globe in a ring.
PERIORB_BACK = 0.0030       # centre behind the eyeball centre along -gaze
PERIORB_U = 0.0122          # half-extent along the aperture axis (corner to corner)
PERIORB_V = 0.0108          # half-extent up/down
PERIORB_FRONT = -0.0010     # front pole ahead of the eyeball surface (inside the aperture, carved)


def lid_shell(pm):
    c, g, u, v = eye_frame(1)
    shell = sphere(pm, c, A.EYE_RADIUS + 0.0007)
    R = np.stack([u, v, g], axis=1)
    fill = ellipsoid(pm, c - g * PERIORB_BACK, (PERIORB_U, PERIORB_V, PERIORB_BACK + A.EYE_RADIUS + PERIORB_FRONT), R)
    return smin(shell, fill, 0.0030)


def head_sdf(ph):
    """Complete head in design space (unscaled distances)."""
    phm = ph.copy()
    phm[:, 0] = np.abs(phm[:, 0])
    d = smin(head_upper(ph, phm), head_jaw(ph), 0.006)
    d = smin(d, lid_shell(phm), 0.0045)
    return d


def head_carve(ph, d):
    phm = ph.copy()
    phm[:, 0] = np.abs(phm[:, 0])
    d = smax(d, -mouth_carve(ph), 0.0012)
    d = smax(d, -eye_carve(phm), 0.0011)
    nostril = ellipsoid(phm, F(0.0038, 0.2236, 0.2330), (0.0014, 0.0012, 0.0008),
                        rot_axis((0, 1, 0), 35.0))
    d = smax(d, -nostril, 0.0006)
    philtrum = round_cone(ph, F(0, 0.2232, 0.2310), F(0, 0.2182, 0.2175), 0.0004, 0.0005)
    d = smax(d, -philtrum, 0.0005)
    return d


def foreleg(pm):
    L = A
    toes_x = (-0.0112, -0.0037, 0.0037, 0.0112)
    toes_f = (0.1070, 0.1125, 0.1125, 0.1070)
    upper = union([
        seg_ellipsoid(pm, L.SCAPULA_L, L.UPPERARM_L, 0.0125, 0.0260, side=(0, -1, 0)),  # scapula plate
        seg_ellipsoid(pm, F(0.040, 0.097, 0.180), F(0.040, 0.058, 0.107), 0.0210, 0.0280, side=(1, 0, 0)),  # triceps
        round_cone(pm, L.UPPERARM_L, L.FOREARM_L, 0.0200, 0.0155),                    # humerus / biceps
        sphere(pm, F(0.0390, 0.0575, 0.1090), 0.0115),                                 # olecranon
    ], 0.012)
    q, s = squash(pm, L.FOREARM_L, (1, 0, 0), 0.88)
    lower = union([
        round_cone(q, L.FOREARM_L, L.HAND_L, 0.0150, 0.0090) * s,                     # forearm
        ellipsoid(pm, F(0.0400, 0.0760, 0.0850), (0.0118, 0.0122, 0.0240)),             # extensor bulge
        sphere(pm, L.HAND_L, 0.0094),                                                   # carpus
        ellipsoid(pm, L.CARPAL_PAD_L, (0.0040, 0.0034, 0.0050)),                         # carpal pad
        round_cone(pm, L.HAND_L, L.FINGER_L, 0.0093, 0.0100),                           # metacarpus
        ellipsoid(pm, F(0.0240, 0.0860, 0.0255), (0.0034, 0.0040, 0.0050)),             # dewclaw
    ], 0.006)
    paw = ellipsoid(pm, F(0.031, 0.0985, 0.0120), (0.0172, 0.0180, 0.0108))
    toes = [ellipsoid(pm, F(0.031 + tx, tf, 0.0088), (0.0062, 0.0078, 0.0074)) for tx, tf in zip(toes_x, toes_f)]
    toe_u = toes[0]
    for t in toes[1:]:
        toe_u = smin(toe_u, t, 0.0018)
    pawd = smin(paw, toe_u, 0.004)
    beans = [ellipsoid(pm, F(0.031 + tx, tf - 0.0005, 0.0040), (0.0040, 0.0046, 0.0030)) for tx, tf in zip(toes_x, toes_f)]
    beans.append(ellipsoid(pm, F(0.031, 0.0925, 0.0044), (0.0092, 0.0064, 0.0034)))
    pawd = smin(pawd, union(beans, 0.0005), 0.0015)
    d = smin(upper, lower, 0.010)
    d = smin(d, pawd, 0.005)
    return d


def hindleg(pm):
    L = A
    toes_x = (-0.0095, -0.0032, 0.0032, 0.0095)
    toes_f = (-0.1410, -0.1365, -0.1365, -0.1410)
    upper = union([
        seg_ellipsoid(pm, F(0.036, -0.172, 0.196), F(0.040, -0.124, 0.112), 0.0235, 0.0410, side=(1, 0, 0)),  # haunch
        seg_ellipsoid(pm, F(0.032, -0.206, 0.180), F(0.037, -0.160, 0.095), 0.0205, 0.0225, side=(1, 0, 0)),  # hamstrings
        sphere(pm, L.SHIN_L, 0.0165),                                                    # stifle
        seg_ellipsoid(pm, F(0.026, -0.212, 0.170), F(0.034, -0.170, 0.120), 0.0200, 0.0200, side=(1, 0, 0)),  # buttock
    ], 0.018)
    lower = union([
        round_cone(pm, L.SHIN_L, L.FOOT_L, 0.0172, 0.0082),                              # tibia
        seg_ellipsoid(pm, F(0.0385, -0.134, 0.108), F(0.0365, -0.178, 0.078), 0.0135, 0.0148, side=(1, 0, 0)),  # calf
        round_cone(pm, F(0.0365, -0.172, 0.090), L.CALCANEUS_L, 0.0060, 0.0056),        # achilles
        sphere(pm, L.FOOT_L, 0.0082),                                                     # hock
        round_cone(pm, L.FOOT_L, L.TOE_L, 0.0082, 0.0088),                               # metatarsus
    ], 0.006)
    paw = ellipsoid(pm, F(0.031, -0.1525, 0.0115), (0.0150, 0.0190, 0.0102))
    toes = [ellipsoid(pm, F(0.031 + tx, tf, 0.0082), (0.0056, 0.0072, 0.0070)) for tx, tf in zip(toes_x, toes_f)]
    toe_u = toes[0]
    for t in toes[1:]:
        toe_u = smin(toe_u, t, 0.0016)
    pawd = smin(paw, toe_u, 0.0038)
    beans = [ellipsoid(pm, F(0.031 + tx, tf + 0.0005, 0.0038), (0.0036, 0.0042, 0.0028)) for tx, tf in zip(toes_x, toes_f)]
    beans.append(ellipsoid(pm, F(0.031, -0.1560, 0.0042), (0.0085, 0.0070, 0.0032)))
    pawd = smin(pawd, union(beans, 0.0005), 0.0014)
    d = smin(upper, lower, 0.010)
    d = smin(d, pawd, 0.005)
    return d


def tail(p):
    pts = A.tail_points()
    radii = A.TAIL_RADII
    d = None
    for i in range(len(pts) - 1):
        e = round_cone(p, pts[i], pts[i + 1], radii[i], radii[i + 1])
        d = e if d is None else smin(d, e, 0.004)
    return d


# ---------------------------------------------------------------------------
# full body
# ---------------------------------------------------------------------------
def cat_sdf(P: np.ndarray) -> np.ndarray:
    p = np.asarray(P, dtype=np.float64)
    pm = p.copy()
    pm[:, 0] = np.abs(pm[:, 0])
    sc = A.HEAD_SCALE
    ph = world_to_head(p)
    d = torso(p)
    d = smin(d, torso_detail(p, pm), 0.012)
    d = smin(d, neck(p), 0.030)
    d = smin(d, head_sdf(ph) * sc, 0.018)
    d = smin(d, foreleg(pm), 0.020)
    d = smin(d, hindleg(pm), 0.030)
    d = smin(d, tail(p), 0.028)
    # carving happens in head space (distances rescaled to world)
    d = head_carve(ph, d / sc) * sc
    return d


# Bounding box of the SDF body (ears/whiskers are separate)
BBOX_MIN = (-0.078, -0.250, -0.004)
BBOX_MAX = (0.078, 0.540, 0.336)


def gradient(P: np.ndarray, eps: float = 2.5e-4) -> np.ndarray:
    g = np.zeros_like(P)
    for i in range(3):
        o = np.zeros(3)
        o[i] = eps
        g[:, i] = (cat_sdf(P + o) - cat_sdf(P - o)) / (2 * eps)
    return g


def project(P: np.ndarray, iters: int = 4, max_step: float = 0.004) -> np.ndarray:
    """Newton-project points onto the zero level set along the SDF gradient."""
    P = np.array(P, dtype=np.float64)
    for _ in range(iters):
        d = cat_sdf(P)
        g = gradient(P)
        gg = np.maximum(np.einsum("ij,ij->i", g, g), 1e-8)
        step = np.clip(d / gg, -max_step, max_step)
        P -= g * step[:, None]
    return P
