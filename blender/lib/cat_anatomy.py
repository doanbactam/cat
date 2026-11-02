"""Cam the orange tabby -- measured anatomy shared by the SDF body, rig and animation.

Coordinates are Blender object space (metres, Z up, the cat FACES -Y).
For readability every landmark is written as F(x, f, z) where f is the distance
*forward* (towards the nose) -> Blender y = -f.  x > 0 is the cat's LEFT side.

Reference proportions (CLAUDE.md scale reference, adult domestic cat ~4 kg):
  * nose tip -> tail base ..... 0.46 m   (nose f=+0.232, tail root f=-0.228)
  * shoulder (withers) height . 0.25 m
  * tail length ............... 0.28 m   (8 segments, contract needs tail_01..06)
  * head width (cheeks) ....... ~0.090 m ; ear height ~0.045 m
Skeleton segment lengths follow feline ratios (scapula : humerus : radius :
metacarpus ~ 0.30 : 0.32 : 0.29 : 0.11 of foreleg; femur : tibia : metatarsus
~ 0.33 : 0.38 : 0.26 of hind leg) scaled so the digitigrade stance hits the
0.25 m withers height with ~6 mm of compressed fur on top.  The mesh surface is
"skin + compressed fur"; the game's shell fur adds up to FUR_MAX_LENGTH on top.
"""
from __future__ import annotations

import math

import numpy as np

FUR_MAX_LENGTH = 0.016      # metres of shell fur at fur_mask.R == 1 (documented for the shell shader)
JAW_REST_OPEN_DEG = 4.0     # mouth is modelled slightly open; anims key the jaw closed (-4 deg)
UPPER_LID_CLOSE_DEG = 38.0  # eyelid bone rotation that fully closes the eye
LOWER_LID_CLOSE_DEG = 14.0


def F(x: float, f: float, z: float) -> tuple[float, float, float]:
    """(lateral, forward, up) -> Blender (x, y, z) with the cat facing -Y."""
    return (x, -f, z)


def mirror(p):
    return (-p[0], p[1], p[2])


# ---------------------------------------------------------------------------
# Axial skeleton (midline) -- head of each bone
# ---------------------------------------------------------------------------
PELVIS = F(0, -0.170, 0.198)        # sacrum / pelvis pivot
SPINE_01 = F(0, -0.112, 0.204)      # L5-L7 lumbar
SPINE_02 = F(0, -0.048, 0.207)      # L1-L4
SPINE_03 = F(0, 0.012, 0.204)       # T10-T13
CHEST = F(0, 0.060, 0.200)          # T1-T9, carries the scapulae
NECK = F(0, 0.100, 0.200)           # C7
NECK_02 = F(0, 0.120, 0.220)        # C3-C4
HEAD = F(0, 0.143, 0.228)           # atlas / occipital condyles
HEAD_TAIL = F(0, 0.200, 0.245)      # bone points along the skull towards the stop
JAW = F(0, 0.164, 0.2172)            # temporomandibular hinge (axis = X)
JAW_TAIL = F(0, 0.2110, 0.2080)       # chin
TONGUE_01 = F(0, 0.176, 0.2130)
TONGUE_02 = F(0, 0.192, 0.2125)
TONGUE_TAIL = F(0, 0.2065, 0.2125)
MOUTH_SOCKET = F(0, 0.2000, 0.2170)   # held items sit here (between the canines)
FPP_EYE = F(0, 0.2028, 0.2496)       # midpoint between the eyes (first-person camera socket)

# Tail root and rest curve (gentle descending arc so weights are clean)
TAIL_ROOT = F(0, -0.222, 0.203)
TAIL_LENGTH = 0.280
TAIL_SEGMENTS = 8
TAIL_SEG_FRACTIONS = (0.150, 0.140, 0.132, 0.125, 0.120, 0.115, 0.110, 0.108)  # sums to 1.0
TAIL_START_ANGLE_DEG = 14.0          # elevation above horizontal at the root (going back)
TAIL_END_ANGLE_DEG = -38.0           # elevation at the tip (drooping)
TAIL_RADII = (0.0150, 0.0126, 0.0118, 0.0111, 0.0105, 0.0099, 0.0093, 0.0087, 0.0074)  # at joints


def tail_points() -> list[tuple[float, float, float]]:
    """Joint positions tail_01 head ... tail tip (TAIL_SEGMENTS + 1 points)."""
    pts = [TAIL_ROOT]
    x, y, z = TAIL_ROOT
    s = 0.0
    for frac in TAIL_SEG_FRACTIONS:
        seg = frac * TAIL_LENGTH
        mid = (s + seg * 0.5) / TAIL_LENGTH
        ang = math.radians(TAIL_START_ANGLE_DEG + (TAIL_END_ANGLE_DEG - TAIL_START_ANGLE_DEG) * mid ** 1.15)
        y += seg * math.cos(ang)   # backwards = +y
        z += seg * math.sin(ang)
        s += seg
        pts.append((0.0, y, z))
    return pts


# ---------------------------------------------------------------------------
# Limbs (LEFT side, x > 0); right side is mirrored
# ---------------------------------------------------------------------------
# Foreleg: scapula is a separate (extra) bone hanging from the chest.
SCAPULA_L = F(0.030, 0.070, 0.234)      # dorsal border (top of the shoulder blade)
UPPERARM_L = F(0.040, 0.106, 0.170)     # shoulder joint (humeral head)
FOREARM_L = F(0.038, 0.066, 0.107)      # elbow (sits behind the chest, against the ribs)
HAND_L = F(0.033, 0.083, 0.031)         # wrist (carpus)
FINGER_L = F(0.031, 0.094, 0.011)       # metacarpophalangeal joint ("ball")
FINGER_TIP_L = F(0.031, 0.113, 0.006)   # toe tips
CARPAL_PAD_L = F(0.033, 0.072, 0.036)

# Hind leg: pantograph (femur ~ parallel to metatarsus), visible hock.
THIGH_L = F(0.035, -0.166, 0.170)       # hip (acetabulum)
SHIN_L = F(0.040, -0.118, 0.113)        # stifle / knee
FOOT_L = F(0.034, -0.190, 0.061)        # hock (tarsus); calcaneus sticks out behind
TOE_L = F(0.031, -0.161, 0.013)         # metatarsophalangeal joint
TOE_TIP_L = F(0.031, -0.136, 0.007)
CALCANEUS_L = F(0.034, -0.201, 0.066)

# Face landmarks (head design space; see REFERENCE_HEAD for the world-space targets)
EYE_L = F(0.0170, 0.2028, 0.2496)       # eyeball centre (set back into the orbit)
EYE_RADIUS = 0.0094       # design space (x HEAD_SCALE in world -> eyeball diameter ~21 mm)
EYE_GAZE_OUT_DEG = 11.0                 # divergence from straight ahead
EYE_GAZE_UP_DEG = 2.0
EYE_APERTURE_W = 0.0150                 # corner to corner (palpebral fissure)
EYE_APERTURE_H = 0.0100                 # lid to lid (relaxed open)
EYE_APERTURE_TILT_DEG = 13.0            # outer corner higher (almond slant)
EAR_BASE_L = F(0.0255, 0.166, 0.2705)   # centre of the ear base on the skull
EAR_HEIGHT = 0.046
EAR_BASE_WIDTH = 0.038
WHISKER_PAD_L = F(0.0080, 0.2150, 0.2262)
NOSE_TIP = F(0, 0.2250, 0.2345)

# Real-world targets for an adult (young male) domestic shorthair, measured on the finished
# SDF by blender/cat/dev_head_measure.py (world metres, fur compressed):
REFERENCE_HEAD = {
    "head_width": 0.084,          # across the cheeks (zygomatic + jowl fur), 80-88 mm
    "eye_spacing": 0.037,         # eyeball centre to centre, 35-39 mm
    "eyeball_diameter": 0.0212,   # 20.5-22 mm
    "fissure_width": 0.017,       # palpebral fissure corner to corner, 16-18 mm
    "fissure_height": 0.0113,     # relaxed open, ~0.65-0.7 of the width
    "eye_to_nose_fwd": 0.028,     # eyeball centre -> nose tip along the head axis, 26-30 mm
    "stop_to_nose": 0.024,        # nasal bridge length (stop between the eyes -> nose tip), 22-26 mm
    "nose_to_chin_drop": 0.026,   # nose tip -> bottom of the chin, 24-30 mm
    "chin_behind_nose": 0.012,    # chin front behind the nose tip, 9-14 mm
    "cornea_proud_of_lids": 0.0025,  # cornea apex ahead of the lid margins (top/medial), <= 3 mm
}

# Muzzle warp: the muzzle (nose, whisker pads, lips, chin, teeth, tongue) is pushed forward
# in design space before the similarity transform, lengthening the face without moving the
# eyes (eyeball region masked out) or the skull/jaw hinge.  Applied by head_to_world() to
# every head-space part, inverted by cat_sdf.world_to_head(), so all consumers stay in sync.
MUZZLE_PUSH = 0.0042            # design metres at full weight
MUZZLE_RAMP_F = (0.176, 0.212)  # forward ramp (design f)
MUZZLE_Z = (0.196, 0.236, 0.252, 0.264)   # vertical window: rise, full, fall-start, zero
# Lower-face lift: lips, jaw and chin move up towards the nose (shorter philtrum, shallower
# lower jaw); fades out above the nose leather and behind the jaw hinge (throat untouched).
LOWER_FACE_LIFT = 0.0072
LOWER_FACE_F = (0.150, 0.178)
LOWER_FACE_Z = (0.213, 0.2355)


def _sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def muzzle_offset(q):
    """(N,3) design points -> (N,3) forward displacement (design units)."""
    q = np.atleast_2d(np.asarray(q, dtype=np.float64))
    f = -q[:, 1]
    z = q[:, 2]
    w = _sstep(MUZZLE_RAMP_F[0], MUZZLE_RAMP_F[1], f)
    w = w * _sstep(MUZZLE_Z[0], MUZZLE_Z[1], z) * (1.0 - _sstep(MUZZLE_Z[2], MUZZLE_Z[3], z))
    ec = np.array([abs(EYE_L[0]), EYE_L[1], EYE_L[2]])
    qe = q.copy()
    qe[:, 0] = np.abs(qe[:, 0])
    de = np.linalg.norm(qe - ec, axis=1)
    w = w * _sstep(EYE_RADIUS + 0.0012, EYE_RADIUS + 0.0062, de)
    out = np.zeros_like(q)
    out[:, 1] = -MUZZLE_PUSH * w
    wl = _sstep(LOWER_FACE_F[0], LOWER_FACE_F[1], f) * (1.0 - _sstep(LOWER_FACE_Z[0], LOWER_FACE_Z[1], z))
    out[:, 2] = LOWER_FACE_LIFT * wl
    return out


def muzzle_warp(q):
    q = np.atleast_2d(np.asarray(q, dtype=np.float64))
    return q + muzzle_offset(q)


def muzzle_unwarp(r, iters: int = 8):
    r = np.atleast_2d(np.asarray(r, dtype=np.float64))
    q = r.copy()
    for _ in range(iters):
        q = r - muzzle_offset(q)
    return q


# ---------------------------------------------------------------------------
# Head space: all head landmarks above (HEAD_TAIL, JAW*, TONGUE*, MOUTH_SOCKET,
# FPP_EYE, EYE_L, EAR_BASE_L, WHISKER_PAD_L, NOSE_TIP and the SDF head parts) are
# authored in a "design" frame and placed on the body by this similarity transform
# (scale + pitch about the atlas joint, then lift).  Use head_to_world() for them.
# ---------------------------------------------------------------------------
HEAD_PIVOT = HEAD
HEAD_SCALE = 1.13
HEAD_PITCH_DEG = 7.0           # + = nose up
HEAD_LIFT = (0.0, 0.002, 0.022)  # Blender-space translation after scaling (up 10 mm)


def _head_rot():
    t = math.radians(HEAD_PITCH_DEG)
    c, s = math.cos(t), math.sin(t)
    # rotation about +X: nose (-Y) goes up for +t
    return ((1, 0, 0), (0, c, s), (0, -s, c))


def head_to_world(p):
    R = _head_rot()
    p = tuple(muzzle_warp(p)[0])
    q = [(p[i] - HEAD_PIVOT[i]) * HEAD_SCALE for i in range(3)]
    r = [sum(R[i][j] * q[j] for j in range(3)) for i in range(3)]
    return tuple(HEAD_PIVOT[i] + r[i] + HEAD_LIFT[i] for i in range(3))


def head_to_world_np(v):
    """Vectorised head_to_world for (N,3) arrays."""
    v = muzzle_warp(v)
    piv = np.asarray(HEAD_PIVOT)
    R = np.asarray(_head_rot())
    q = (v - piv) * HEAD_SCALE
    return piv + q @ R.T + np.asarray(HEAD_LIFT)


def head_dir_to_world(d):
    R = _head_rot()
    return tuple(sum(R[i][j] * d[j] for j in range(3)) for i in range(3))


# Gait speeds the locomotion clips are authored for (m/s) -- contract
GAIT_SPEED = {"walk": 0.7, "trot": 1.6, "run": 4.5, "sneak": 0.45, "balance_walk": 0.40}
FPS = 30
