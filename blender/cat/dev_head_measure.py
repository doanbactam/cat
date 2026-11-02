"""Measure Cam's head on the SDF against cat_anatomy.REFERENCE_HEAD (pure numpy, no Blender).
Usage: python3 blender/cat/dev_head_measure.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import cat_anatomy as A  # noqa: E402
import cat_sdf as S  # noqa: E402


def march(o, d, tmax=0.1, n=5000):
    """First inside point marching from o along d."""
    o = np.asarray(o, float)
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    ts = np.linspace(0, tmax, n)
    P = o[None] + ts[:, None] * d[None]
    i = np.nonzero(S.cat_sdf(P) < 0)[0]
    return P[i[0]] if len(i) else None


def measure() -> dict:
    m = {}
    best = (0.0, 0, 0)
    for f in np.linspace(0.14, 0.23, 19):
        for z in np.linspace(0.22, 0.29, 15):
            p = march((0.1, -f, z), (-1, 0, 0))
            if p is not None and p[0] > best[0]:
                best = (p[0], f, z)
    m["head_width"] = 2 * best[0]
    fwd = np.array(A.head_dir_to_world((0, -1, 0)))
    nose = march(A.head_to_world((0, -0.26, 0.2345)), -fwd)
    c, g, u, v = S.eye_frame(1)
    cw = np.array(A.head_to_world(tuple(c)))
    gw = np.array(A.head_dir_to_world(tuple(g)))
    uw = np.array(A.head_dir_to_world(tuple(u)))
    vw = np.array(A.head_dir_to_world(tuple(v)))
    sc = A.HEAD_SCALE
    R = A.EYE_RADIUS * sc
    m["eye_spacing"] = 2 * cw[0]
    m["eyeball_diameter"] = 2 * R
    m["fissure_width"] = A.EYE_APERTURE_W * sc
    m["fissure_height"] = A.EYE_APERTURE_H * sc
    m["eye_to_nose_fwd"] = float(np.dot(nose - cw, fwd))
    stop = march(np.array([0.0, cw[1] - 0.05, cw[2] + 0.004]), (0, 1, 0))
    m["stop_to_nose"] = float(np.linalg.norm(stop - nose))
    chin_b = march(A.head_to_world((0, -0.199, 0.17)), (0, 0, 1))
    m["nose_to_chin_drop"] = float(nose[2] - chin_b[2])
    chin_f = march(np.array([0.0, nose[1] - 0.03, chin_b[2] + 0.004]), (0, 1, 0))
    m["chin_behind_nose"] = float(chin_f[1] - nose[1])
    apex = R + 0.0011 * sc
    lids = {}
    for nm, off in (("top", vw * (A.EYE_APERTURE_H * 0.56 * sc + 0.0012)),
                    ("bottom", -vw * (A.EYE_APERTURE_H * 0.44 * sc + 0.0012)),
                    ("medial", -uw * (A.EYE_APERTURE_W * 0.5 * sc + 0.0012)),
                    ("lateral", uw * (A.EYE_APERTURE_W * 0.5 * sc + 0.0012))):
        p = march(cw + off + gw * 0.03, -gw, 0.05)
        lids[nm] = apex - float(np.dot(p - cw, gw))
    m["cornea_proud_of_lids"] = float(np.mean([lids["top"], lids["medial"]]))
    m["_lids"] = lids
    m["_landmarks"] = {"nose": nose, "eye_L": cw, "stop": stop, "chin_bottom": chin_b, "chin_front": chin_f}
    return m


if __name__ == "__main__":
    m = measure()
    for k, ref in A.REFERENCE_HEAD.items():
        print(f"{k:22s} {m[k] * 1000:7.1f} mm   (target {ref * 1000:5.1f})")
    print("cornea apex proud of lid margins (mm):", {k: round(v * 1000, 1) for k, v in m["_lids"].items()})
    for k, v in m["_landmarks"].items():
        print(f"  {k:12s}", np.round(v, 4))
