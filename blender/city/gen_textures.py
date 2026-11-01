#!/usr/bin/env python3
"""Generate the tileable PBR material library for the old-quarter architecture kit.

Run:  python3 blender/city/gen_textures.py [--only plaster_ochre,brick] [--sheet]
Out:  assets/textures/architecture/<set>_{albedo.jpg,normal.png,orm.jpg}
      qa/out/city-houses/tex_sheet*.jpg  (contact sheet, --sheet)

Each set: 1024 px tile; TILE_M (metres covered) is listed in SETS and mirrored in
blender/lib/city_mats.py so UV projection gives the right texel density (>= 512 px/m).
All maps are seamless; macro variation is built in (blotches, fading, dirt).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import city_texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "architecture")
N = 1024


# ---------------------------------------------------------------------------
# Plaster family (hero material of the quarter)
# ---------------------------------------------------------------------------
def plaster(name, seed, paint, paint_hi, under, bare, peel=0.30, dirt=0.5, patches=3, tile_m=2.0,
            repaint=None):
    n = N
    rng = np.random.default_rng(seed)
    # --- height field (metres)
    und = T.spectral(n, seed, 2.6, 1.5, 60) * 0.0018          # wall undulation / trowel waves
    trowel = T.spectral(n, seed + 1, 2.0, 6, 90, aniso=(1.0, 0.6), rot_deg=rng.uniform(-40, 40)) * 0.0006
    grain = T.spectral(n, seed + 2, 0.3, 160) * 0.00018         # sand grain
    pores = (rng.random((n, n)) > 0.998).astype(np.float32)
    pores = T.blur(pores, 0.8) * -0.0025
    cracks = T.crack_mask(n, seed + 3, count=2, length_px=(80, 220), width_px=1.0, branch=0.3) * 0.7
    hair = T.crack_mask(n, seed + 33, count=10, length_px=(20, 80), width_px=0.7, branch=0.1)
    cracks = np.maximum(cracks, hair * 0.45)

    # paint layers: peel1 = top paint gone (older coat shows), peel2 = down to bare plaster
    pn = T.spectral(n, seed + 4, 3.0, 2, 60) + T.spectral(n, seed + 44, 1.2, 30, 300) * 0.05
    wx = T.spectral(n, seed + 5, 2.0, 3, 50) * 14
    wy = T.spectral(n, seed + 6, 2.0, 3, 50) * 14
    pn = T.warp(pn, wx, wy)
    thr = 2.0 - peel * 2.0
    peel1 = T.smoothstep(thr, thr + 0.05, pn)
    peel2 = T.smoothstep(thr + 0.35, thr + 0.40, pn + T.spectral(n, seed + 7, 1.5, 8, 200) * 0.2)
    # chipped edge rim (paint lifts at the border of a peel)
    rim = np.clip(T.smoothstep(thr - 0.06, thr, pn) - peel1, 0, 1)

    # repair patches (cement) with ragged edges
    pt = T.blobs(n, seed + 8, patches, 30, 90, warp_amt=0.5, rect=True)
    pt = T.smoothstep(0.35, 0.65, T.blur(pt, 1.5))

    h = und + trowel + grain + pores - cracks * 0.0016
    h += (1 - peel1) * 0.00045 + (1 - peel2) * 0.0006 + rim * 0.0002
    h = h * (1 - pt) + pt * (und * 0.4 + grain * 0.6 + 0.0007)

    # --- albedo
    macro = T.spectral(n, seed + 9, 2.4, 1, 24)
    macro2 = T.spectral(n, seed + 10, 1.8, 3, 60)
    fade = T.smoothstep(-1.2, 1.6, macro)                      # sun-faded blotches
    col_paint = T.lerp(T.rgb(paint), T.rgb(paint_hi), fade)
    col_paint = T.hsv_jitter(col_paint, macro2 * 0.035 + T.spectral(n, seed + 11, 1.0, 40) * 0.015,
                             macro2 * 0.06)
    if repaint is not None:  # areas painted over in a slightly different tone
        rp = T.smoothstep(0.4, 0.6, T.blobs(n, seed + 12, 3, 60, 160, 0.6, rect=True))
        col_paint = T.lerp(col_paint, T.hsv_jitter(np.broadcast_to(T.rgb(repaint), col_paint.shape).copy(),
                                                   macro2 * 0.03), rp * 0.85)
    col_under = T.hsv_jitter(np.broadcast_to(T.rgb(under), (n, n, 3)).copy(), macro2 * 0.05)
    col_bare = T.hsv_jitter(np.broadcast_to(T.rgb(bare), (n, n, 3)).copy(),
                            T.spectral(n, seed + 13, 1.2, 8) * 0.06, -0.2)
    col = T.lerp(col_paint, col_under, peel1)
    col = T.lerp(col, col_bare, peel2)
    col = T.lerp(col, col * 1.06 + 0.02, rim[..., None] * 0.6)
    patch_col = T.hsv_jitter(np.broadcast_to(T.rgb("#a19c92"), (n, n, 3)).copy(),
                             T.spectral(n, seed + 14, 1.5, 4) * 0.05)
    patch_col = T.lerp(patch_col, col_paint * 0.97, 0.35)
    col = T.lerp(col, patch_col, pt)

    # grime: cavities, blotches, vertical runs, cracks
    ao = T.cavity_ao(h - und - trowel, tile_m, 0.006, 0.0012, 0.8)
    blot = T.smoothstep(-0.2, 2.2, T.spectral(n, seed + 15, 2.6, 1, 14)) * dirt
    st = T.streaks(n, seed + 16, 0.55, 8.0) * dirt
    grime_col = T.rgb("#5a5246")
    col = T.lerp(col, col * grime_col * 1.5, np.clip(blot * 0.3 + st * 0.3, 0, 0.7))
    col = col * (0.82 + 0.18 * ao[..., None])
    col = T.lerp(col, T.rgb("#3a342c"), cracks * 0.4)
    # efflorescence / limescale freckles
    eff = T.smoothstep(2.2, 3.0, T.spectral(n, seed + 17, 1.4, 10, 300)) * 0.25
    col = T.lerp(col, T.rgb("#e8e4dc"), eff)

    rough = 0.80 + 0.05 * peel1 + 0.07 * peel2 + 0.06 * blot + 0.04 * pt
    rough += T.spectral(n, seed + 18, 1.0, 20) * 0.025 - rim * 0.05
    rough = np.clip(rough + cracks * 0.1, 0.55, 1.0)
    nrm = T.normal_from_height(h, tile_m, 1.0)
    ao_map = np.clip(0.55 + 0.45 * ao - cracks * 0.3, 0, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), nrm, ao_map, rough, 0.0)


def cement_render(name, seed, base="#9b978e", tile_m=2.0, algae=0.5):
    """Bare cement render / party walls: soft trowel arcs, large rain stains, algae, patches."""
    n = N
    rng = np.random.default_rng(seed)
    und = T.spectral(n, seed, 3.0, 1.5, 18) * 0.0012
    arcs = np.zeros((n, n), np.float32)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    for k in range(30):  # trowel swirl arcs
        cx, cy, r = rng.uniform(0, n), rng.uniform(0, n), rng.uniform(60, 180)
        dx = np.minimum(np.abs(xx - cx), n - np.abs(xx - cx))
        dy = np.minimum(np.abs(yy - cy), n - np.abs(yy - cy))
        d = np.sqrt(dx * dx + dy * dy)
        arcs += np.exp(-((d - r) ** 2) / 30.0) * (d < r * 1.2) * rng.uniform(0.3, 1.0)
    arcs = T.blur(arcs, 1.5)
    grain = T.spectral(n, seed + 2, 0.4, 120) * 0.00012
    cracks = T.crack_mask(n, seed + 3, count=2, length_px=(60, 200), width_px=1.0, branch=0.3) * 0.6
    h = und + arcs * 0.0003 + grain - cracks * 0.0015
    pt = T.smoothstep(0.35, 0.65, T.blur(T.blobs(n, seed + 8, 4, 50, 130, 0.5, rect=True), 2))
    h += pt * 0.0006
    macro = T.spectral(n, seed + 9, 3.0, 1, 6)
    col = np.broadcast_to(T.rgb(base), (n, n, 3)).copy()
    col = T.hsv_jitter(col, macro * 0.045 + T.spectral(n, seed + 10, 1.6, 6, 60) * 0.012, macro * 0.06)
    col = T.lerp(col, T.hsv_jitter(col * 1.07, macro * 0.04), pt)
    ao = T.cavity_ao(h - und, tile_m, 0.01, 0.0015, 0.5)
    st = T.smoothstep(0.2, 2.4, T.spectral(n, seed + 16, 1.9, 2, 40, aniso=(1.0, 16.0)))
    alg = T.smoothstep(1.0, 2.4, T.spectral(n, seed + 17, 2.6, 1, 10) + st * 0.6) * algae
    col = T.lerp(col, col * T.rgb("#6d756a") * 1.1, alg * 0.45)
    col = T.lerp(col, col * 0.8, st * 0.3)
    blk = T.smoothstep(2.0, 2.8, T.spectral(n, seed + 18, 2.0, 4, 80)) * algae
    col = T.lerp(col, T.rgb("#3e4038"), blk * 0.3)
    col = col * (0.85 + 0.15 * ao[..., None])
    col = T.lerp(col, T.rgb("#35322d"), cracks * 0.4)
    rough = np.clip(0.86 + alg * 0.06 - pt * 0.04 + T.spectral(n, seed + 19, 1, 20) * 0.02, 0.6, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.7 + 0.3 * ao, 0, 1), rough, 0.0)


def concrete(name, seed, tile_m=2.0):
    n = N
    rng = np.random.default_rng(seed)
    und = T.spectral(n, seed, 2.4, 1.5, 80) * 0.0025
    agg = T.spectral(n, seed + 1, 0.8, 60) * 0.0004
    holes = (rng.random((n, n)) > 0.9975).astype(np.float32)
    holes = np.clip(T.blur(holes, 1.6) * 6, 0, 1) * -0.003
    # formwork board lines (horizontal, every 0.25 m) faint
    yy = np.mgrid[0:n, 0:n][0].astype(np.float32)
    board = np.exp(-((np.mod(yy, n / (tile_m / 0.25)) - 1.5) ** 2) / 2.0) * 0.0006
    cracks = T.crack_mask(n, seed + 3, 2, (60, 220), 1.1, 0.3) * 0.6
    h = und + agg + holes - board - cracks * 0.0015
    macro = T.spectral(n, seed + 4, 2.2, 1, 40)
    col = T.colorize(np.clip(T.spectral(n, seed + 5, 1.5, 4, 300) / 6 + 0.5, 0, 1),
                     [(0.0, "#6f6d68"), (0.5, "#8d8a83"), (1.0, "#a8a49b")])
    col = T.hsv_jitter(col, macro * 0.08, -0.1)
    spk = T.spectral(n, seed + 6, 0.2, 200)
    col = col * (1 + spk[..., None] * 0.03)
    st = T.streaks(n, seed + 7, 0.6, 9)
    moss = T.smoothstep(0.8, 2.2, T.spectral(n, seed + 8, 2.0, 2, 50) + st * 0.8)
    col = T.lerp(col, col * T.rgb("#4d5a3f") * 1.3, moss * 0.55)
    col = T.lerp(col, col * 0.7, st * 0.35)
    ao = T.cavity_ao(h, tile_m, 0.015, 0.002, 1.0)
    col = col * (0.7 + 0.3 * ao[..., None])
    col = T.lerp(col, T.rgb("#2e2c28"), cracks * 0.4)
    rough = np.clip(0.88 + moss * 0.06 + T.spectral(n, seed + 9, 1, 30) * 0.03, 0.6, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.5 + 0.5 * ao, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
# Brick
# ---------------------------------------------------------------------------
def brick(name, seed, tile_m=2.0, plaster_left=0.25):
    n = N
    rng = np.random.default_rng(seed)
    cols_per_row, rows = 8, 28
    bw, bh = n / cols_per_row, n / rows
    mortar_px = 0.011 / tile_m * n
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    row = np.floor(yy / bh).astype(np.int32)
    xo = xx + (row % 2) * bw * 0.5
    col_i = np.floor(xo / bw).astype(np.int32) % cols_per_row
    lx = np.mod(xo, bw)
    ly = np.mod(yy, bh)
    ex = np.minimum(lx, bw - lx)
    ey = np.minimum(ly, bh - ly)
    edge = np.minimum(ex, ey)
    # ragged brick edges
    rag = T.spectral(n, seed + 1, 1.4, 20, 300) * 1.2
    face = T.smoothstep(mortar_px * 0.5, mortar_px * 0.5 + 2.0, edge + rag)
    bid = (row * 131 + col_i * 17) % 997
    rv = np.random.default_rng(seed + 2).random(1000).astype(np.float32)
    rv2 = np.random.default_rng(seed + 3).random(1000).astype(np.float32)
    tone = rv[bid]
    burn = (rv2[bid] > 0.88).astype(np.float32)
    bcol = T.colorize(tone, [(0.0, "#8a3b26"), (0.35, "#a24a2e"), (0.7, "#b45e3a"), (1.0, "#c27a52")])
    bcol = T.lerp(bcol, T.rgb("#4f2a20"), burn * 0.6)
    bnoise = T.spectral(n, seed + 4, 0.8, 30)
    bcol = T.hsv_jitter(bcol, bnoise * 0.06)
    bump = T.spectral(n, seed + 5, 1.6, 10, 300) * 0.0008
    chips = T.smoothstep(1.6, 2.2, T.spectral(n, seed + 6, 1.2, 30, 300)) * (edge < bh * 0.35)
    mcol = T.hsv_jitter(np.broadcast_to(T.rgb("#9a9286"), (n, n, 3)).copy(),
                        T.spectral(n, seed + 7, 1.0, 40) * 0.08)
    h = face * (0.006 + bump) - chips * 0.003 * face
    # leftover plaster blobs on top of the brickwork
    pl = T.smoothstep(0.45, 0.6, T.blobs(n, seed + 8, int(8 * plaster_left + 1), 40, 150, 0.7))
    pl = pl * (plaster_left > 0)
    plcol = T.hsv_jitter(np.broadcast_to(T.rgb("#b9b1a2"), (n, n, 3)).copy(),
                         T.spectral(n, seed + 9, 1.4, 6) * 0.06)
    h = h * (1 - pl) + pl * (0.009 + T.spectral(n, seed + 10, 1.2, 10) * 0.0006)
    col = T.lerp(mcol, bcol, face)
    col = T.lerp(col, col * 0.75, chips[..., None] * 0.5)
    col = T.lerp(col, plcol, pl)
    st = T.streaks(n, seed + 11, 0.6, 7)
    soot = T.smoothstep(-0.5, 2.0, T.spectral(n, seed + 12, 2.2, 1, 30))
    col = T.lerp(col, col * 0.6, np.clip(st * 0.35 + soot * 0.25, 0, 0.7))
    ao = T.cavity_ao(h, tile_m, 0.01, 0.004, 1.0)
    col = col * (0.65 + 0.35 * ao[..., None])
    rough = np.clip(0.82 + (1 - face) * 0.1 + T.spectral(n, seed + 13, 1, 30) * 0.03, 0.6, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.45 + 0.55 * ao, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
# Ceramic / mosaic facade tiles
# ---------------------------------------------------------------------------
def tiles(name, seed, tile_m, nx, ny, palette, weights, grout="#b8b2a6", grout_m=0.003, stagger=False,
          speckle=0.0, gloss=0.18, missing=0.004, bevel_m=0.002, marble=0.0):
    n = N
    rng = np.random.default_rng(seed)
    tw, th = n / nx, n / ny
    gpx = grout_m / tile_m * n
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    row = np.floor(yy / th).astype(np.int32)
    xo = xx + ((row % 2) * tw * 0.5 if stagger else 0)
    ci = np.floor(xo / tw).astype(np.int32) % nx
    lx, ly = np.mod(xo, tw), np.mod(yy, th)
    edge = np.minimum(np.minimum(lx, tw - lx), np.minimum(ly, th - ly))
    face = T.smoothstep(gpx * 0.5, gpx * 0.5 + max(bevel_m / tile_m * n, 1.0), edge)
    tid = (row % ny) * nx + ci
    ntiles = nx * ny
    trng = np.random.default_rng(seed + 1)
    w = np.array(weights, np.float64)
    choice = trng.choice(len(palette), size=ntiles, p=w / w.sum())
    pal = np.stack([T.rgb(c) for c in palette])
    tcol = pal[choice][tid]
    tv = (trng.random(ntiles).astype(np.float32) - 0.5)[tid]
    tcol = T.hsv_jitter(tcol, tv * 0.08)
    if speckle > 0:
        sp = T.spectral(n, seed + 2, 0.3, 150)
        tcol = T.hsv_jitter(tcol, sp * speckle)
    if marble > 0:
        mv = np.abs(np.sin(T.spectral(n, seed + 3, 2.2, 2, 80) * 3.0 + xx * 0.01))
        tcol = T.lerp(tcol, tcol * 0.85, T.smoothstep(0.92, 1.0, mv) * marble)
    tiltx = ((trng.random(ntiles) - 0.5) * 0.002).astype(np.float32)[tid]
    tilty = ((trng.random(ntiles) - 0.5) * 0.002).astype(np.float32)[tid]
    miss = (trng.random(ntiles) < missing)[tid]
    crack = T.crack_mask(n, seed + 4, 4, (40, 160), 1.0, 0.2) * face
    h = face * (0.003 + tiltx * lx / tw + tilty * ly / th) - crack * 0.0008
    h = np.where(miss, -0.002 + T.spectral(n, seed + 5, 1.0, 30) * 0.0005, h)
    gcol = T.hsv_jitter(np.broadcast_to(T.rgb(grout), (n, n, 3)).copy(), T.spectral(n, seed + 6, 1.0, 20) * 0.1)
    dirt = T.smoothstep(-0.8, 2.0, T.spectral(n, seed + 7, 2.0, 2, 40))
    gcol = T.lerp(gcol, gcol * 0.45, dirt[..., None] * 0.8)
    col = T.lerp(gcol, tcol, face)
    col = np.where(miss[..., None], T.rgb("#8c877c") * (0.9 + 0.1 * dirt[..., None]), col)
    st = T.streaks(n, seed + 8, 0.5, 8)
    col = T.lerp(col, col * T.rgb("#6f6658"), np.clip(st * 0.35 + dirt * 0.18, 0, 0.6))
    col = T.lerp(col, T.rgb("#2a2824"), crack * 0.6)
    smudge = T.smoothstep(-0.5, 2.0, T.spectral(n, seed + 9, 1.8, 3, 80))
    rough = np.where(face > 0.5, gloss + smudge * 0.25 + st * 0.2, 0.92)
    rough = np.where(miss, 0.95, rough)
    ao = T.cavity_ao(h, tile_m, 0.006, 0.002, 1.0)
    col = col * (0.7 + 0.3 * ao[..., None])
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m),
                      np.clip(0.5 + 0.5 * ao, 0, 1), np.clip(rough, 0.05, 1), 0.0)


# ---------------------------------------------------------------------------
# Roof tiles
# ---------------------------------------------------------------------------
def roof_marseille(name, seed, tile_m=2.0, age=0.6):
    """Interlocking French (Marseille) tiles; texture V = up-slope. 9 x 6 tiles per 2 m."""
    n = N
    nx, ny = 9, 6
    tw, th = n / nx, n / ny
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    row = np.floor(yy / th).astype(np.int32)
    ci = np.floor(xx / tw).astype(np.int32)
    u = np.mod(xx, tw) / tw
    v = 1.0 - np.mod(yy, th) / th  # v=0 at bottom lip of the row (image row increases downward)
    # profile across the tile: big roll + small rib + side lock
    roll = np.clip(np.sin(np.clip((u - 0.52) / 0.40, 0, 1) * math.pi), 0, 1) ** 0.8 * 0.016
    rib = np.exp(-((u - 0.3) ** 2) / 0.002) * 0.004
    lock = np.exp(-((u - 0.04) ** 2) / 0.0012) * 0.006
    groove = -np.exp(-((u - 0.12) ** 2) / 0.0008) * 0.003
    across = roll + rib + lock + groove
    along = 0.012 * (1.0 - v)             # lower edge sits proud on the course below
    lip = np.exp(-(v / 0.05) ** 2) * 0.004
    tid = (row % ny) * nx + ci % nx
    trng = np.random.default_rng(seed + 1)
    nt = nx * ny
    tilt = ((trng.random(nt) - 0.5) * 0.004).astype(np.float32)[tid]
    h = across + along + lip + tilt * (u - 0.5)
    h += T.spectral(n, seed + 2, 1.4, 20, 400) * 0.0004
    # gap shadow between tiles of the same row / at row seam
    seam_y = np.exp(-(v / 0.012) ** 2)
    h -= seam_y * 0.004
    tone = trng.random(nt).astype(np.float32)[tid]
    base = T.colorize(tone, [(0.0, "#7d3a24"), (0.3, "#9c4a2c"), (0.65, "#b35a35"), (1.0, "#c06f45")])
    old = (trng.random(nt) < 0.18)[tid]
    base = np.where(old[..., None], base * np.array([0.72, 0.68, 0.66], np.float32), base)
    base = T.hsv_jitter(base, T.spectral(n, seed + 3, 1.2, 10) * 0.05 + T.spectral(n, seed + 4, 0.5, 80) * 0.03)
    # ageing: dark streaks down-slope, black lichen speckle, moss in channels & under lips
    st = T.streaks(n, seed + 5, 0.6, 9.0)
    lich = T.smoothstep(1.2, 2.2, T.spectral(n, seed + 6, 0.9, 20, 400)) * age
    lich_w = T.smoothstep(2.0, 2.6, T.spectral(n, seed + 7, 0.7, 40, 400)) * age
    channel = np.exp(-((u - 0.12) ** 2) / 0.004) + np.exp(-((u - 0.47) ** 2) / 0.003)
    moss = T.smoothstep(0.4, 1.6, T.spectral(n, seed + 8, 2.0, 3, 60) + channel * 0.8 + (v < 0.15) * 0.6) * age
    col = T.lerp(base, base * 0.55, st * 0.45 * age)
    col = T.lerp(col, T.rgb("#2b2a25"), lich * 0.7)
    col = T.lerp(col, T.rgb("#b7b2a0"), lich_w * 0.55)
    col = T.lerp(col, T.rgb("#4f5631"), moss * 0.55)
    ao = T.cavity_ao(h, tile_m, 0.008, 0.004, 1.0)
    under_lip = np.exp(-((1.0 - v) / 0.06) ** 2)  # shadow line under the next course's lip
    ao = ao * (1.0 - under_lip * 0.55)
    col = col * (0.5 + 0.5 * ao[..., None])
    rough = np.clip(0.78 + moss * 0.15 + lich * 0.05 + T.spectral(n, seed + 9, 1, 30) * 0.03, 0.5, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m, 1.0),
                      np.clip(0.35 + 0.65 * ao, 0, 1), rough, 0.0)


def roof_scale(name, seed, tile_m=2.0, age=0.85):
    """Old fish-scale flat tiles (ngoi mui hai): 13 x 25 rows per 2 m, staggered, shoe-tip ends."""
    n = N
    nx, ny = 13, 25
    tw, th = n / nx, n / ny
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    row = np.floor(yy / th).astype(np.int32)
    xo = xx + (row % 2) * tw * 0.5
    ci = np.floor(xo / tw).astype(np.int32) % nx
    u = np.mod(xo, tw) / tw
    v = 1.0 - np.mod(yy, th) / th
    # rounded/pointed lower end: the exposed tile occupies v > tip(u)
    tip = 0.42 * (np.abs(u - 0.5) * 2) ** 1.6
    inside = T.smoothstep(tip - 0.03, tip + 0.03, v)
    h_tile = 0.012 * (1.0 - v) + 0.002
    h = np.where(inside > 0.5, h_tile, 0.012 * (1.0 - (v + 1.0) / 1.0) * 0 + 0.012 * 0.15)
    h = h * inside + (1 - inside) * 0.0015
    tid = (row % ny) * nx + ci
    trng = np.random.default_rng(seed + 1)
    nt = nx * ny
    tone = trng.random(nt).astype(np.float32)[tid]
    base = T.colorize(tone, [(0.0, "#5e3226"), (0.4, "#7f4430"), (0.8, "#975538"), (1.0, "#a6663f")])
    base = T.hsv_jitter(base, T.spectral(n, seed + 3, 1.2, 10) * 0.06)
    under = T.rgb("#3b2a22")
    col = T.lerp(np.broadcast_to(under, base.shape), base, inside)
    h += T.spectral(n, seed + 2, 1.2, 30, 400) * 0.0003
    st = T.streaks(n, seed + 5, 0.6, 8.0)
    lich = T.smoothstep(1.0, 2.0, T.spectral(n, seed + 6, 0.9, 20, 400)) * age
    lich_w = T.smoothstep(1.9, 2.5, T.spectral(n, seed + 7, 0.7, 40, 400)) * age
    moss = T.smoothstep(0.2, 1.6, T.spectral(n, seed + 8, 2.0, 2, 50) + (1 - inside) * 0.9) * age
    col = T.lerp(col, col * 0.55, st * 0.5 * age)
    col = T.lerp(col, T.rgb("#262520"), lich * 0.65)
    col = T.lerp(col, T.rgb("#aaa695"), lich_w * 0.5)
    col = T.lerp(col, T.rgb("#4a5530"), moss * 0.6)
    ao = T.cavity_ao(h, tile_m, 0.015, 0.004, 1.0)
    col = col * (0.55 + 0.45 * ao[..., None])
    rough = np.clip(0.82 + moss * 0.12 + T.spectral(n, seed + 9, 1, 30) * 0.03, 0.5, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.35 + 0.65 * ao, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
# Metals
# ---------------------------------------------------------------------------
def corrugated(name, seed, paint=None, rust=0.5, tile_m=2.0):
    """Sheet-metal surface (the corrugation itself is modelled). V = down the sheet (flow)."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    dents = T.spectral(n, seed, 2.4, 2, 40) * 0.0012
    h = dents + T.spectral(n, seed + 1, 1.0, 40, 300) * 0.00008
    spangle_id = T.voronoi(256, seed + 2, 140)[2]
    sp = np.random.default_rng(seed + 3).random(spangle_id.max() + 1).astype(np.float32)[spangle_id]
    sp = np.kron(sp, np.ones((4, 4), np.float32))[:n, :n]
    galv = T.lerp(T.rgb("#7f8486"), T.rgb("#a3a8a8"), sp[..., None] * 0.6 +
                  T.spectral(n, seed + 4, 1.4, 4)[..., None] * 0.08)
    st = T.streaks(n, seed + 5, 0.7, 10.0)
    rmask = T.smoothstep(1.4 - rust * 1.6, 2.2 - rust * 1.6, T.spectral(n, seed + 6, 2.0, 2, 120) + st * 0.9)
    rdeep = T.smoothstep(0.5, 0.9, rmask * (0.5 + 0.5 * T.fbm(n, seed + 7, 10, 200)))
    rust_col = T.colorize(T.fbm(n, seed + 8, 6, 300), [(0.0, "#4a2414"), (0.5, "#7a3b1c"), (1.0, "#a5582a")])
    if paint:
        pc = T.hsv_jitter(np.broadcast_to(T.rgb(paint), (n, n, 3)).copy(),
                          T.spectral(n, seed + 9, 2.0, 1, 30) * 0.1 + st * -0.08, -0.1 * st)
        chip = T.smoothstep(1.4, 1.8, T.spectral(n, seed + 10, 1.4, 10, 300))
        base = T.lerp(pc, galv, chip)
        metal = chip * 0.85
        rough = 0.55 + st * 0.15 + chip * -0.15
        h += (1 - chip) * 0.0001
    else:
        base = galv
        metal = np.full((n, n), 0.85, np.float32)
        rough = 0.42 + st * 0.15 + T.spectral(n, seed + 11, 1.0, 10) * 0.05
    col = T.lerp(base, rust_col, rmask * 0.85)
    col = T.lerp(col, col * 0.6, st * 0.4)
    metal = metal * (1 - rmask)
    rough = np.clip(rough * (1 - rmask) + rmask * 0.9, 0.2, 1)
    h += rdeep * 0.0004 * T.spectral(n, seed + 12, 0.5, 80)
    ao = np.clip(1.0 - st * 0.15, 0, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m),
                      ao, rough, np.clip(metal, 0, 1))


def painted_metal(name, seed, paint="#c9c6bf", rust=0.35, tile_m=1.0, chips=0.4):
    """Generic painted steel (grilles, cages, brackets, AC casings). Tint via vertex colour."""
    n = N
    st = T.streaks(n, seed, 0.5, 9)
    orange = T.spectral(n, seed + 1, 0.8, 30, 400) * 0.00004
    h = orange + T.spectral(n, seed + 2, 2.4, 2, 30) * 0.0003
    pc = T.hsv_jitter(np.broadcast_to(T.rgb(paint), (n, n, 3)).copy(), T.spectral(n, seed + 3, 2, 1, 30) * 0.06)
    chip = T.smoothstep(2.1 - chips, 2.4 - chips, T.spectral(n, seed + 4, 1.3, 10, 400))
    rmask = T.smoothstep(1.6 - rust, 2.4 - rust, T.spectral(n, seed + 5, 2.0, 3, 200) + st * 0.6)
    rmask = np.maximum(rmask, chip * 0.8)
    rust_col = T.colorize(T.fbm(n, seed + 6, 8, 300), [(0.0, "#3f2013"), (0.5, "#6e3518"), (1.0, "#9c5228")])
    col = T.lerp(pc, rust_col, rmask)
    col = T.lerp(col, col * 0.7, st * 0.3)
    h += -chip * 0.00015 + rmask * T.spectral(n, seed + 7, 0.6, 60) * 0.0002
    rough = np.clip(0.45 + rmask * 0.45 + st * 0.12 + T.spectral(n, seed + 8, 1, 20) * 0.04, 0.2, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m),
                      np.clip(1 - st * 0.12, 0, 1), rough, 0.0)


def iron_black(name, seed, tile_m=0.5):
    n = N
    st = T.streaks(n, seed, 0.5, 8)
    h = T.spectral(n, seed + 1, 1.6, 6, 300) * 0.0003 + T.spectral(n, seed + 2, 0.6, 80) * 0.00006
    pc = T.hsv_jitter(np.broadcast_to(T.rgb("#26282a"), (n, n, 3)).copy(), T.spectral(n, seed + 3, 2, 2, 60) * 0.12)
    rmask = T.smoothstep(0.9, 1.9, T.spectral(n, seed + 4, 1.8, 4, 300) + st * 0.6)
    rust_col = T.colorize(T.fbm(n, seed + 5, 8, 300), [(0.0, "#3a1d10"), (0.5, "#6a3317"), (1.0, "#92502a")])
    col = T.lerp(pc, rust_col, rmask * 0.9)
    dust = T.smoothstep(0.5, 2.0, T.spectral(n, seed + 6, 2, 3, 80)) * 0.3
    col = T.lerp(col, T.rgb("#6b665c"), dust)
    rough = np.clip(0.5 + rmask * 0.4 + dust * 0.3, 0.2, 1)
    h += rmask * T.spectral(n, seed + 7, 0.5, 100) * 0.0002
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.ones((n, n), np.float32) * 0.95, rough, 0.0)


def stainless(name, seed, tile_m=1.0):
    n = N
    brush = T.spectral(n, seed, 1.0, 4, 500, aniso=(14.0, 1.0))
    h = brush * 0.00002 + T.spectral(n, seed + 1, 2.6, 2, 30) * 0.0008  # dents/oil canning
    base = T.lerp(T.rgb("#8f9496"), T.rgb("#b8bdbf"), np.clip(brush / 6 + 0.5, 0, 1)[..., None])
    spots = T.wrap_draw(n, _ring_spots(n, seed + 2, 90))
    st = T.streaks(n, seed + 3, 0.6, 10)
    col = T.lerp(base, base * T.rgb("#8a8270"), np.clip(st * 0.5 + spots * 0.4, 0, 0.8))
    rough = np.clip(0.26 + np.abs(brush) * 0.03 + st * 0.25 + spots * 0.2, 0.1, 0.9)
    metal = np.clip(1.0 - st * 0.4, 0, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.95), T.normal_from_height(h, tile_m),
                      np.ones((n, n), np.float32), rough, metal)


def _ring_spots(n, seed, count):
    rng = np.random.default_rng(seed)

    def draw(d, ox, oy, ss):
        for _ in range(count):
            x, y, r = rng.uniform(0, n), rng.uniform(0, n), rng.uniform(3, 14)
            for dx in (-n, 0, n):
                for dy in (-n, 0, n):
                    cx, cy = x + dx + ox, y + dy + oy
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=int(rng.uniform(80, 200)), width=1)
    return draw


def steel_shutter(name, seed, tile_m=1.0):
    """Rolling shutter curtain: horizontal interlocking slats, 13 per metre."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    pitch = n / 13.0
    t = np.mod(yy, pitch) / pitch
    prof = 0.004 * np.sin(t * math.pi) ** 0.6 - 0.003 * np.exp(-((t - 0.0) / 0.06) ** 2) \
        - 0.003 * np.exp(-((t - 1.0) / 0.06) ** 2) + 0.0012 * np.exp(-((t - 0.5) / 0.08) ** 2)
    slat = np.floor(yy / pitch).astype(np.int32)
    dents = T.spectral(n, seed, 2.4, 3, 60) * 0.0006
    scratches = T.spectral(n, seed + 1, 0.8, 30, 500, aniso=(10, 1))
    h = prof + dents + scratches * 0.00004
    sp_id = T.voronoi(256, seed + 2, 160)[2]
    sp = np.random.default_rng(seed + 3).random(sp_id.max() + 1).astype(np.float32)[sp_id]
    sp = np.kron(sp, np.ones((4, 4), np.float32))[:n, :n]
    galv = T.lerp(T.rgb("#8c9192"), T.rgb("#b3b8b8"), sp[..., None] * 0.5)
    st = T.streaks(n, seed + 4, 0.65, 10)
    joint = np.exp(-((t - 0.0) / 0.08) ** 2) + np.exp(-((t - 1.0) / 0.08) ** 2)
    rmask = T.smoothstep(1.5, 2.3, T.spectral(n, seed + 5, 1.8, 4, 200) + joint * 0.9 + st * 0.4)
    rust_col = T.colorize(T.fbm(n, seed + 6, 8, 300), [(0.0, "#432214"), (1.0, "#8d4c26")])
    col = T.lerp(galv, galv * T.rgb("#7a7366"), np.clip(st * 0.5 + joint * 0.25, 0, 0.8))
    col = T.lerp(col, rust_col, rmask * 0.8)
    col = col * (1 + scratches[..., None] * 0.02)
    rough = np.clip(0.4 + st * 0.2 + rmask * 0.45 + joint * 0.1, 0.15, 1)
    metal = np.clip(0.75 - st * 0.3 - rmask * 0.75, 0, 1)
    ao = np.clip(1 - joint * 0.35, 0, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m), ao, rough, metal)


def acp(name, seed, tile_m=1.0):
    n = N
    st = T.streaks(n, seed, 0.45, 12)
    h = T.spectral(n, seed + 1, 1.0, 40, 400) * 0.00002 + T.spectral(n, seed + 2, 2.6, 1, 20) * 0.0004
    base = T.hsv_jitter(np.broadcast_to(T.rgb("#d0d2d2"), (n, n, 3)).copy(), T.spectral(n, seed + 3, 2, 1, 20) * 0.03)
    col = T.lerp(base, base * T.rgb("#8d8778"), st * 0.45)
    rough = np.clip(0.3 + st * 0.3 + T.spectral(n, seed + 4, 1, 10) * 0.03, 0.1, 1)
    return T.save_set(OUT, name, col, T.normal_from_height(h, tile_m), np.ones((n, n), np.float32), rough,
                      np.clip(0.45 - st * 0.3, 0, 1))


# ---------------------------------------------------------------------------
# Wood
# ---------------------------------------------------------------------------
def wood(name, seed, paint=None, paint2=None, tile_m=1.0, peel=0.4, varnish=False):
    """Grain along V (vertical). Painted (with peeling + crazing) or varnished dark wood."""
    n = N
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    fib = T.spectral(n, seed, 1.2, 8, 500, aniso=(1.0, 14.0))
    wx = T.spectral(n, seed + 1, 2.4, 1, 10, aniso=(1.0, 4.0)) * 18
    rings = np.sin((xx + wx) / n * 2 * math.pi * 28 + fib * 0.6)
    rings = T.smoothstep(0.6, 1.0, rings)
    grain = fib * 0.00035 - rings * 0.0006
    knots = T.blobs(n, seed + 2, 3, 6, 14, 0.2) * (rng.random() < 0.9)
    wood_col = T.colorize(np.clip(fib / 6 + 0.5 + rings * 0.15, 0, 1),
                          [(0.0, "#5e4630"), (0.5, "#7a5c3e"), (1.0, "#9a7a56")])
    if varnish:
        wood_col = T.colorize(np.clip(fib / 6 + 0.5 + rings * 0.2, 0, 1),
                              [(0.0, "#2f1d12"), (0.5, "#4a2e1b"), (1.0, "#6b452a")])
    wood_col = T.lerp(wood_col, wood_col * 0.5, knots)
    weathered = T.hsv_jitter(wood_col * 0.8 + T.rgb("#6d6a63") * 0.35, fib * 0.03, -0.4)
    st = T.streaks(n, seed + 3, 0.5, 9)
    h = grain - knots * 0.0003
    if paint:
        pn = T.spectral(n, seed + 4, 2.0, 2, 300, aniso=(1.0, 4.0))
        pn = T.warp(pn, T.spectral(n, seed + 5, 2, 4, 60) * 6, T.spectral(n, seed + 6, 2, 4, 60) * 6)
        thr = 1.9 - peel * 2.4
        gone = T.smoothstep(thr, thr + 0.08, pn + fib * 0.08)
        f1, edge, _ = T.voronoi(n, seed + 7, 900, 0.9)
        craze = T.smoothstep(1.6, 0.0, edge) * T.smoothstep(-0.5, 1.0, T.spectral(n, seed + 8, 2.0, 2, 30))
        pc = T.hsv_jitter(np.broadcast_to(T.rgb(paint), (n, n, 3)).copy(),
                          T.spectral(n, seed + 9, 2.2, 1, 20) * 0.08 + st * -0.1,
                          T.spectral(n, seed + 10, 2.0, 1, 20) * 0.1 - 0.1 * st)
        if paint2:  # older coat under the top coat
            pc2 = np.broadcast_to(T.rgb(paint2), (n, n, 3)).copy()
            gone1 = T.smoothstep(thr - 0.35, thr - 0.27, pn)
            pc = T.lerp(pc, pc2, gone1 * (1 - gone))
        col = T.lerp(pc, weathered, gone)
        col = T.lerp(col, col * 0.55, craze[..., None] * 0.6 * (1 - gone[..., None]))
        h = h * (0.3 + 0.7 * gone) + (1 - gone) * (0.0003 - craze * 0.0002)
        rough = np.clip(0.55 + gone * 0.35 + st * 0.12 + craze * 0.1, 0.2, 1)
    else:
        col = wood_col
        wear = T.smoothstep(0.5, 2.0, T.spectral(n, seed + 11, 2.0, 2, 60))
        col = T.lerp(col, weathered, wear * 0.5)
        rough = np.clip((0.45 if varnish else 0.7) + wear * 0.3 + st * 0.1, 0.2, 1)
    col = T.lerp(col, col * 0.7, st * 0.3)
    ao = T.cavity_ao(h, tile_m, 0.004, 0.0004, 0.8)
    col = col * (0.8 + 0.2 * ao[..., None])
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.6 + 0.4 * ao, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
# Floors / stone
# ---------------------------------------------------------------------------
def terrazzo(name, seed, base="#b9b4a8", chips_pal=("#2a2a2a", "#e8e6e0", "#8a4a3a", "#6c7466", "#c9b48a"),
             tile_m=1.0, polish=0.32, panel_m=0.4):
    n = N
    rng = np.random.default_rng(seed)
    f1, edge, cid = T.voronoi(n, seed, 2600, 1.0)
    keep = rng.random(cid.max() + 1) < 0.55
    pal = np.stack([T.rgb(c) for c in chips_pal])
    pick = rng.integers(0, len(chips_pal), cid.max() + 1)
    chip = (keep[cid] & (edge > 1.6 + rng.random(cid.max() + 1)[cid] * 2.0)).astype(np.float32)
    chip = T.blur(chip, 0.6)
    ccol = pal[pick][cid] * (0.9 + 0.2 * rng.random(cid.max() + 1)[cid][..., None])
    bcol = T.hsv_jitter(np.broadcast_to(T.rgb(base), (n, n, 3)).copy(), T.spectral(n, seed + 1, 1.5, 3) * 0.05)
    col = T.lerp(bcol, ccol, chip)
    # brass/plastic divider strips forming panels
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    ppx = panel_m / tile_m * n
    strip = np.maximum(np.exp(-((np.mod(xx, ppx)) ** 2) / 2.0), np.exp(-((np.mod(yy, ppx)) ** 2) / 2.0))
    col = T.lerp(col, T.rgb("#8a8c86"), strip * 0.8)
    scuff = T.smoothstep(0.0, 2.2, T.spectral(n, seed + 2, 2.0, 2, 60))
    scratch = T.crack_mask(n, seed + 3, 30, (20, 80), 0.8, 0.0)
    col = T.lerp(col, col * 0.75, scuff[..., None] * 0.35)
    col = T.lerp(col, col * 1.1, scratch[..., None] * 0.3)
    h = chip * 0.00005 - strip * 0.0002 - scratch * 0.00005 + T.spectral(n, seed + 4, 2.4, 1, 20) * 0.0004
    rough = np.clip(polish + scuff * 0.35 + scratch * 0.2 + T.spectral(n, seed + 5, 1, 30) * 0.03, 0.08, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(1 - strip * 0.4, 0, 1), rough, 0.0)


def granite(name, seed, pal=("#5a2a26", "#8d4b42", "#1d1b1b", "#b0a49b", "#6d3830"), tile_m=1.0):
    n = N
    rng = np.random.default_rng(seed)
    f1, edge, cid = T.voronoi(n, seed, 7000, 1.0)
    p = np.stack([T.rgb(c) for c in pal])
    pick = rng.choice(len(pal), cid.max() + 1, p=[0.35, 0.3, 0.15, 0.05, 0.15])
    col = p[pick][cid]
    col = T.lerp(col, col * 0.8, T.smoothstep(1.5, 0.0, edge)[..., None] * 0.5)
    col = T.hsv_jitter(col, T.spectral(n, seed + 1, 1.5, 3) * 0.06)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    joint = np.maximum(np.exp(-(np.mod(xx, n / 2) ** 2) / 1.5), np.exp(-(np.mod(yy, n / 3) ** 2) / 1.5))
    col = T.lerp(col, T.rgb("#3a3532"), joint * 0.8)
    scuff = T.smoothstep(0.0, 2.2, T.spectral(n, seed + 2, 2.0, 2, 60))
    col = T.lerp(col, col * 0.85 + 0.04, scuff[..., None] * 0.4)
    h = -joint * 0.0008 + T.spectral(n, seed + 3, 2.4, 1, 10) * 0.0002
    rough = np.clip(0.14 + scuff * 0.4 + joint * 0.5, 0.05, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(1 - joint * 0.5, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
# Render, stucco, fabric
# ---------------------------------------------------------------------------
def render_modern(name, seed, base="#e2e0da", tile_m=2.0):
    n = N
    h = T.spectral(n, seed, 0.6, 80) * 0.00015 + T.spectral(n, seed + 1, 2.6, 1, 30) * 0.0008
    roller = T.spectral(n, seed + 2, 1.5, 4, 120, aniso=(4.0, 1.0)) * 0.00008
    h += roller
    st = T.streaks(n, seed + 3, 0.5, 10)
    blot = T.smoothstep(0.5, 2.2, T.spectral(n, seed + 4, 2.2, 1, 30))
    col = T.hsv_jitter(np.broadcast_to(T.rgb(base), (n, n, 3)).copy(), T.spectral(n, seed + 5, 2.0, 1, 20) * 0.02)
    col = T.lerp(col, col * T.rgb("#8e8676"), np.clip(st * 0.35 + blot * 0.2, 0, 0.6))
    hair = T.crack_mask(n, seed + 6, 6, (40, 200), 0.9, 0.3)
    col = T.lerp(col, col * 0.6, hair * 0.5)
    rough = np.clip(0.78 + st * 0.08 + T.spectral(n, seed + 7, 1, 20) * 0.02, 0.5, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h - hair * 0.0005, tile_m),
                      np.clip(1 - hair * 0.3, 0, 1), rough, 0.0)


def stucco(name, seed, tile_m=1.0):
    """Moulding / cornice / pilaster plaster, light cream (tinted per building by vertex colour)."""
    n = N
    h = T.spectral(n, seed, 2.4, 2, 60) * 0.0008 + T.spectral(n, seed + 1, 0.4, 100) * 0.0001
    cracks = T.crack_mask(n, seed + 2, 5, (60, 300), 1.1, 0.4)
    chips = T.smoothstep(1.7, 2.1, T.spectral(n, seed + 3, 1.5, 6, 200))
    h = h - cracks * 0.001 - chips * 0.0015
    col = T.hsv_jitter(np.broadcast_to(T.rgb("#e6ddc8"), (n, n, 3)).copy(),
                       T.spectral(n, seed + 4, 2.0, 1, 20) * 0.04)
    col = T.lerp(col, T.rgb("#a69f92"), chips * 0.8)
    st = T.streaks(n, seed + 5, 0.65, 7)
    blot = T.smoothstep(0.0, 2.0, T.spectral(n, seed + 6, 2.2, 1, 30))
    col = T.lerp(col, col * T.rgb("#5d554a") * 1.2, np.clip(st * 0.45 + blot * 0.3, 0, 0.8))
    ao = T.cavity_ao(h, tile_m, 0.01, 0.0012, 1.0)
    col = col * (0.7 + 0.3 * ao[..., None])
    col = T.lerp(col, T.rgb("#3a342c"), cracks * 0.5)
    rough = np.clip(0.84 + blot * 0.06, 0.5, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.55 + 0.45 * ao, 0, 1), rough, 0.0)


def fabric(name, seed, base="#e6e2d8", tile_m=1.0, thread_mm=4.0):
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    per = thread_mm / 1000.0 / tile_m * n
    per = n / round(n / per)
    wx = np.sin(xx / per * math.pi * 2)
    wy = np.sin(yy / per * math.pi * 2)
    weave = np.where((np.floor(xx / per) + np.floor(yy / per)) % 2 == 0, wx, wy)
    h = weave * 0.00015 + T.spectral(n, seed, 2.4, 1, 12) * 0.002  # wrinkles
    col = T.hsv_jitter(np.broadcast_to(T.rgb(base), (n, n, 3)).copy(),
                       T.spectral(n, seed + 1, 2.0, 1, 30) * 0.05 + weave * 0.02)
    dirt = T.smoothstep(0.0, 2.2, T.spectral(n, seed + 2, 2.2, 1, 30))
    rings = T.wrap_draw(n, _ring_spots(n, seed + 3, 25))
    st = T.streaks(n, seed + 4, 0.4, 8)
    col = T.lerp(col, col * T.rgb("#8a8070"), np.clip(dirt * 0.3 + rings * 0.3 + st * 0.3, 0, 0.7))
    rough = np.clip(0.92 + dirt * 0.04, 0.5, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m),
                      np.clip(0.85 + weave * 0.08, 0, 1), rough, 0.0)


def rattan(name, seed, tile_m=0.5):
    """Hand-woven rattan / bamboo basketry: over-under strands with fibre detail (for baskets, trays, hats)."""
    n = N
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    k = 40  # strands per tile each way (12.5 mm strands)
    p = n / k
    u, v = xx / p, yy / p
    iu, iv = np.floor(u).astype(np.int32), np.floor(v).astype(np.int32)
    fu, fv = u - iu, v - iv
    over = ((iu + iv) % 2 == 0)
    prof_h = np.sin(np.clip(fv, 0, 1) * math.pi) ** 0.6      # horizontal strand cross profile
    prof_v = np.sin(np.clip(fu, 0, 1) * math.pi) ** 0.6
    bend_h = np.sin(fu * math.pi) * 0.25                        # strand dips under the crossing one
    bend_v = np.sin(fv * math.pi) * 0.25
    h_h = prof_h * (0.6 + np.where(over, bend_h, -bend_h))
    h_v = prof_v * (0.6 + np.where(over, -bend_v, bend_v))
    top_is_h = h_h >= h_v
    h = np.maximum(h_h, h_v) * 0.0018
    fib = T.spectral(n, seed, 1.0, 40, 500, aniso=(1.0, 12.0))
    fib_h = T.spectral(n, seed + 1, 1.0, 40, 500, aniso=(12.0, 1.0))
    sid = np.where(top_is_h, iv * 7 + 3, iu * 13 + 5) % 97
    tone = np.random.default_rng(seed + 2).random(97).astype(np.float32)[sid]
    base = T.colorize(np.clip(tone * 0.6 + 0.2 + np.where(top_is_h, fib_h, fib) * 0.06, 0, 1),
                      [(0.0, "#8a6436"), (0.5, "#b08850"), (1.0, "#cfa96c")])
    gap = 1.0 - T.smoothstep(0.15, 0.0, np.maximum(h_h, h_v))
    col = base * (0.35 + 0.65 * gap[..., None])
    h = h + np.where(top_is_h, fib_h, fib) * 0.00004
    dirt = T.smoothstep(0.0, 2.2, T.spectral(n, seed + 3, 2.0, 1, 20))
    col = T.lerp(col, col * 0.7, dirt * 0.3)
    rough = np.clip(0.55 + (1 - gap) * 0.35 + dirt * 0.1, 0.3, 1)
    ao = np.clip(0.4 + 0.6 * gap, 0, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m), ao, rough, 0.0)


# ---------------------------------------------------------------------------
SETS = {
    # name: (tile metres, generator)
    "plaster_ochre": (2.0, lambda: plaster("plaster_ochre", 101, "#c99a52", "#dcbc82", "#d9d0bc", "#a59c8d",
                                           peel=0.32, dirt=0.55, repaint="#cfa35e")),
    "plaster_blue": (2.0, lambda: plaster("plaster_blue", 202, "#7096a3", "#9cb8bd", "#d6cfbd", "#a49c8f",
                                          peel=0.30, dirt=0.5)),
    "plaster_pink": (2.0, lambda: plaster("plaster_pink", 303, "#c99384", "#dcb6a8", "#ddd2bf", "#a69d90",
                                          peel=0.28, dirt=0.5)),
    "plaster_white": (2.0, lambda: plaster("plaster_white", 404, "#d9d3c4", "#e8e3d7", "#c2baa9", "#a39b8e",
                                           peel=0.2, dirt=0.5)),
    "plaster_green": (2.0, lambda: plaster("plaster_green", 505, "#93ad94", "#b4c8ad", "#dbd2bd", "#a49c8e",
                                           peel=0.30, dirt=0.55)),
    "plaster_yellow": (2.0, lambda: plaster("plaster_yellow", 606, "#d4b25a", "#e4cc8a", "#dbd3bd", "#a59d8e",
                                            peel=0.2, dirt=0.45, repaint="#e2bd5a")),
    "cement_render": (2.0, lambda: cement_render("cement_render", 707, base="#aaa598")),
    "concrete_weathered": (2.0, lambda: concrete("concrete_weathered", 808)),
    "brick_exposed": (2.0, lambda: brick("brick_exposed", 909)),
    "tile_mosaic_blue": (1.0, lambda: tiles("tile_mosaic_blue", 111, 1.0, 20, 20,
                                            ["#2f5d8c", "#4a7fb3", "#7aa7cf", "#e5ebee", "#1f3f66"],
                                            [4, 4, 2, 1, 1], grout="#c8c3b8", grout_m=0.0025, gloss=0.12)),
    "tile_mosaic_green": (1.0, lambda: tiles("tile_mosaic_green", 112, 1.0, 20, 20,
                                             ["#2f7a5c", "#56a07e", "#9cc9b0", "#e6ede6", "#1e5a40"],
                                             [3, 3, 2, 2, 1], grout="#c8c3b8", grout_m=0.0025, gloss=0.12)),
    "tile_ceramic_beige": (2.0, lambda: tiles("tile_ceramic_beige", 113, 2.0, 10, 8,
                                              ["#d8c4ae", "#ccb59c", "#e0cfbb", "#c3a98e"], [3, 3, 2, 1],
                                              grout="#bdb4a6", grout_m=0.003, speckle=0.06, gloss=0.16,
                                              marble=0.6)),
    "tile_strip_brown": (2.0, lambda: tiles("tile_strip_brown", 114, 2.0, 8, 30,
                                            ["#7a3f28", "#8f4c2f", "#6a3523", "#9c5a3a", "#5b2e20"],
                                            [3, 3, 2, 2, 1], grout="#a9a296", grout_m=0.006, stagger=True,
                                            speckle=0.05, gloss=0.3, bevel_m=0.003)),
    "roof_tile_terracotta": (2.0, lambda: roof_marseille("roof_tile_terracotta", 121, age=0.55)),
    "roof_tile_old": (2.0, lambda: roof_scale("roof_tile_old", 122, age=0.9)),
    "corrugated_rusted": (2.0, lambda: corrugated("corrugated_rusted", 131, None, rust=0.75)),
    "corrugated_blue": (2.0, lambda: corrugated("corrugated_blue", 132, "#3f6f9c", rust=0.35)),
    "metal_painted": (1.0, lambda: painted_metal("metal_painted", 141)),
    "iron_wrought": (0.5, lambda: iron_black("iron_wrought", 142)),
    "stainless": (1.0, lambda: stainless("stainless", 143)),
    "steel_shutter": (1.0, lambda: steel_shutter("steel_shutter", 144)),
    "acp_panel": (1.0, lambda: acp("acp_panel", 145)),
    "wood_teal": (1.0, lambda: wood("wood_teal", 151, "#2f7d78", "#6a8f5a", peel=0.42)),
    "wood_green": (1.0, lambda: wood("wood_green", 152, "#3f6e45", "#b7a77a", peel=0.38)),
    "wood_brown": (1.0, lambda: wood("wood_brown", 153, None, varnish=True)),
    "terrazzo": (1.0, lambda: terrazzo("terrazzo", 161)),
    "granite_red": (1.0, lambda: granite("granite_red", 162)),
    "render_modern": (2.0, lambda: render_modern("render_modern", 171)),
    "stucco_detail": (1.0, lambda: stucco("stucco_detail", 172)),
    "fabric_canvas": (1.0, lambda: fabric("fabric_canvas", 181)),
    "rattan": (0.5, lambda: rattan("rattan", 191)),
}


def contact_sheet(names, path, cell=256):
    from PIL import Image, ImageDraw
    cols = 6
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell * 2), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, nme in enumerate(names):
        a = Image.open(os.path.join(OUT, f"{nme}_albedo.jpg")).resize((cell, cell))
        nm = Image.open(os.path.join(OUT, f"{nme}_normal.png")).resize((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * cell * 2
        sheet.paste(a, (x, y))
        sheet.paste(nm, (x, y + cell))
        d.text((x + 4, y + 4), nme, fill=(255, 255, 0))
    sheet.save(path, quality=88)
    print("SHEET", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    names = [s for s in a.only.split(",") if s] or list(SETS)
    for nme in names:
        t0 = time.time()
        SETS[nme][1]()
        print(f"  {nme}: {time.time() - t0:.1f}s")
    import json
    with open(os.path.join(OUT, "materials.json"), "w") as fh:
        json.dump({k: {"tile_m": v[0], "albedo": f"{k}_albedo.jpg", "normal": f"{k}_normal.png",
                       "orm": f"{k}_orm.jpg"} for k, v in SETS.items()}, fh, indent=1)
    if a.sheet:
        contact_sheet(names, os.path.join(ROOT, "qa", "out", "city-houses", "tex_sheet.jpg"))


if __name__ == "__main__":
    main()
