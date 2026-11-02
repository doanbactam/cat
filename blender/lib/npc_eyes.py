"""Eye textures (iris / sclera) for NPC eyeballs (owner: creatures). The eyeball UV is a
front planar projection: iris centred at (0.5, 0.5); `iris_r` is the iris radius in UV units."""
from __future__ import annotations

import numpy as np

import npc_tex as X
from npc_build import save_rgb, srgb


def iris_texture(path: str, iris_col="#3a2416", sclera_col="#e6ddd2", iris_r=0.26, pupil_r=0.10, size=256,
                 slit=False, limbal=0.85, seed=3, full_iris=False, ring_col=None):
    n = size
    yy, xx = np.mgrid[0:n, 0:n]
    u = (xx + 0.5) / n - 0.5
    v = (yy + 0.5) / n - 0.5
    r = np.sqrt(u * u + v * v)
    ang = np.arctan2(v, u)
    P = np.stack([np.cos(ang) * 30, np.sin(ang) * 30, r * 40], -1).reshape(-1, 3)
    fib = X.fbm(P, 1.0, 3, seed).reshape(n, n)
    ic = X.col(iris_col)
    sc = X.col(sclera_col)
    # sclera with faint veins/warmth toward the corners
    veins = X.ridged(np.stack([u * 40, v * 40, np.zeros_like(u)], -1).reshape(-1, 3), 1.0, 3, seed + 1).reshape(n, n)
    scl = sc[None, None] * (1 - 0.06 * X.sstep(0.25, 0.5, r))[..., None]
    scl = X.mix(scl, X.col("#c98f86")[None, None], (X.sstep(0.85, 0.97, veins) * X.sstep(0.3, 0.48, r) * 0.5)[..., None])
    rr = r / iris_r
    iris = ic[None, None] * (0.75 + 0.35 * fib[..., None] + 0.2 * (1 - rr)[..., None])
    if ring_col is not None:
        iris = X.mix(iris, X.col(ring_col)[None, None], (X.sstep(0.55, 0.3, rr) * 0.6)[..., None])
    iris = X.mix(iris, iris * 0.35, (X.sstep(limbal, 1.0, rr))[..., None])
    a = X.mix(scl, iris, X.sstep(1.03, 0.98, rr)[..., None]) if not full_iris else iris
    if slit:
        pd = np.sqrt((u / (pupil_r * 0.25)) ** 2 + (v / pupil_r) ** 2)
    else:
        pd = r / pupil_r
    a = X.mix(a, np.full_like(a, 0.008), X.sstep(1.05, 0.95, pd)[..., None])
    save_rgb(path, srgb(a.reshape(n, n, 3)), 92)
    return path
