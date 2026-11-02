#!/usr/bin/env python3
"""Tileable PBR sets for the landmark kit (temple, market, lake, cafe, tea stall).

Run:  python3 blender/landmarks/gen_textures.py [--only lacquer_red,...] [--sheet]
Out:  assets/textures/landmarks/<set>_{albedo.jpg,normal.png,orm.jpg} + materials.json
      qa/out/city-landmarks/tex_sheet.jpg with --sheet

Re-uses the (read-only) synthesis library of the city-houses kit: city_texlib (noise, cracks, voronoi,
normal-from-height) and the generic generators in blender/city/gen_textures.py (wood, tiles, fabric,
painted_metal, concrete) with their output dir redirected here. Landmark-specific sets (temple
bluestone, ashlar embankment blocks, bronze patina, gilt lacquer, striped tarp, courtyard bricks,
lake-stone coping) are synthesised below. 1024 px tiles; texel density >= 512 px/m.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "city"))
import city_texlib as T  # noqa: E402
import gen_textures as GT  # noqa: E402  (city-houses generator, used read-only)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "landmarks")
GT.OUT = OUT
N = GT.N


def _const(c):
    return np.broadcast_to(T.rgb(c), (N, N, 3)).copy()


# ---------------------------------------------------------------------------
# Stone
# ---------------------------------------------------------------------------
def ashlar(name, seed, tile_m=2.0, course_m=0.38, block_m=(0.55, 1.1), base=("#6f716c", "#8a8b84", "#9d9b92"),
           mortar="#8f8a7d", joint_m=0.012, tooling=0.6, moss=0.5, waterline=0.0):
    """Coursed stone blocks (embankment walls, temple plinths). V = up."""
    n = N
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    rows = max(1, round(tile_m / course_m))
    th = n / rows
    row = np.floor(yy / th).astype(np.int32)
    # per-row random block lengths that tile horizontally
    bid = np.zeros((n, n), np.int32)
    lx = np.zeros((n, n), np.float32)
    bw = np.zeros((n, n), np.float32)
    nid = 0
    for r in range(rows):
        cuts = [0.0]
        while True:
            L = rng.uniform(*block_m) / tile_m * n
            if cuts[-1] + L > n - block_m[0] / tile_m * n * 0.6:
                break
            cuts.append(cuts[-1] + L)
        cuts.append(float(n))
        off = rng.uniform(0, n)
        sel = row == r
        xr = np.mod(xx + off, n)
        for i in range(len(cuts) - 1):
            m = sel & (xr >= cuts[i]) & (xr < cuts[i + 1])
            bid[m] = nid
            lx[m] = np.minimum(xr[m] - cuts[i], cuts[i + 1] - xr[m])
            bw[m] = cuts[i + 1] - cuts[i]
            nid += 1
    ly = np.minimum(np.mod(yy, th), th - np.mod(yy, th))
    jp = joint_m / tile_m * n
    edge = np.minimum(lx, ly)
    face = T.smoothstep(jp * 0.5, jp * 0.5 + 6, edge)
    brng = np.random.default_rng(seed + 1)
    tone = brng.random(nid + 1).astype(np.float32)[bid]
    pal = T.colorize(tone, [(0.0, base[0]), (0.55, base[1]), (1.0, base[2])])
    # chisel tooling: fine diagonal strokes, stronger near arrises (pitched edges)
    tool = T.spectral(n, seed + 2, 0.8, 40, 300, aniso=(1.0, 5.0), rot_deg=60)
    rough_face = T.spectral(n, seed + 3, 2.2, 3, 120)
    bulge = T.smoothstep(0, 40, edge) * 0.004
    chips = T.smoothstep(1.4, 2.2, T.spectral(n, seed + 4, 1.4, 8, 200)) * (edge < 26)
    h = face * (0.006 + bulge + rough_face * 0.0012 + tool * 0.0003 * tooling) - chips * 0.004
    col = T.hsv_jitter(pal, T.spectral(n, seed + 5, 1.6, 4, 200) * 0.07 + tool * 0.015)
    # lichen spots (white/grey + black) and moss in joints / lower blocks
    st = T.streaks(n, seed + 6, 0.55, 10)
    lich_w = T.smoothstep(1.7, 2.4, T.spectral(n, seed + 7, 0.8, 30, 400))
    lich_b = T.smoothstep(1.5, 2.3, T.spectral(n, seed + 8, 0.8, 25, 400))
    mz = T.smoothstep(0.4, 2.0, T.spectral(n, seed + 9, 2.0, 2, 60) + (1 - face) * 1.4 + st * 0.5) * moss
    mcol = T.colorize(T.fbm(n, seed + 10, 10, 300), [(0.0, "#2f3a1d"), (0.6, "#4f5d2a"), (1.0, "#6d7838")])
    gcol = T.hsv_jitter(_const(mortar), T.spectral(n, seed + 11, 1.0, 20) * 0.1)
    col = T.lerp(gcol * 0.8, col, face)
    col = T.lerp(col, col * 0.6, st * 0.45)
    col = T.lerp(col, T.rgb("#b9b6a8"), lich_w * 0.45)
    col = T.lerp(col, T.rgb("#262620"), lich_b * 0.5)
    col = T.lerp(col, mcol, mz * 0.75)
    if waterline > 0:   # dark wet band + algae at the bottom of the tile (v small = bottom rows)
        wl = T.smoothstep(n * (1 - waterline), n, yy + T.spectral(n, seed + 12, 1.5, 4, 80) * 8)
        col = T.lerp(col, col * T.rgb("#4c5a3c") * 0.9, wl * 0.8)
        mz = np.maximum(mz, wl * 0.6)
    ao = T.cavity_ao(h, tile_m, 0.02, 0.004, 1.0)
    col = col * (0.62 + 0.38 * ao[..., None])
    rough = np.clip(0.78 + mz * 0.12 - st * 0.05 + rough_face * 0.03, 0.4, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.35 + 0.65 * ao, 0, 1), rough, 0.0)


def bluestone(name, seed, tile_m=1.0):
    """Monolithic dressed bluestone (column bases, steps, coping, burner plinths). Fine tooling,
    calcite veins, worn shiny tops; tint per object via vertex colour."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    tool = T.spectral(n, seed, 0.6, 60, 400, aniso=(1.0, 8.0), rot_deg=20)
    pits = T.spectral(n, seed + 1, 0.3, 200) * 0.00015
    und = T.spectral(n, seed + 2, 2.4, 1.5, 40) * 0.0015
    vein = np.abs(np.sin(T.spectral(n, seed + 3, 2.2, 2, 50) * 2.4 + xx * 0.004))
    vein = T.smoothstep(0.985, 1.0, vein)
    h = und + tool * 0.00012 + pits - vein * 0.0002
    col = T.colorize(T.fbm(n, seed + 4, 2, 200, 1.8), [(0.0, "#3f4646"), (0.5, "#59605f"), (1.0, "#727775")])
    col = T.hsv_jitter(col, tool * 0.02)
    col = T.lerp(col, T.rgb("#a9aba3"), vein * 0.55)
    st = T.streaks(n, seed + 5, 0.5, 9)
    lich = T.smoothstep(1.8, 2.5, T.spectral(n, seed + 6, 0.8, 30, 400))
    moss = T.smoothstep(1.2, 2.5, T.spectral(n, seed + 7, 2.0, 2, 60) + st * 0.6)
    col = T.lerp(col, col * 0.7, st * 0.35)
    col = T.lerp(col, T.rgb("#b5b3a5"), lich * 0.4)
    col = T.lerp(col, T.rgb("#46522a"), moss * 0.5)
    polish = T.smoothstep(-0.5, 2.0, T.spectral(n, seed + 8, 2.0, 2, 30))
    ao = T.cavity_ao(h, tile_m, 0.01, 0.0008, 0.8)
    col = col * (0.75 + 0.25 * ao[..., None])
    rough = np.clip(0.62 - polish * 0.2 + moss * 0.25 + st * 0.08, 0.25, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.5 + 0.5 * ao, 0, 1), rough, 0.0)


def bronze(name, seed, tile_m=0.5):
    """Cast bronze with verdigris in recesses, soot, polished high spots (incense burner, bells)."""
    n = N
    cast = T.spectral(n, seed, 2.0, 3, 200) * 0.0004 + T.spectral(n, seed + 1, 0.5, 100) * 0.00005
    patina = T.smoothstep(-0.2, 1.8, T.spectral(n, seed + 2, 2.0, 3, 120) + T.streaks(n, seed + 3, 0.6, 7) * 1.2)
    soot = T.smoothstep(0.0, 2.2, T.spectral(n, seed + 4, 2.2, 2, 50))
    metal_col = T.colorize(T.fbm(n, seed + 5, 3, 200), [(0.0, "#5a3e1e"), (0.5, "#7d5a2c"), (1.0, "#9c7638")])
    ver = T.colorize(T.fbm(n, seed + 6, 6, 300), [(0.0, "#3d6656"), (0.6, "#5e8c76"), (1.0, "#86ad97")])
    col = T.lerp(metal_col, ver, patina * 0.75)
    col = T.lerp(col, T.rgb("#1d1a16"), soot * 0.55)
    metal = np.clip(1.0 - patina * 0.85 - soot * 0.6, 0, 1)
    rough = np.clip(0.38 + patina * 0.45 + soot * 0.2, 0.2, 1)
    ao = T.cavity_ao(cast, tile_m, 0.01, 0.0005, 0.6)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(cast, tile_m),
                      np.clip(0.6 + 0.4 * ao, 0, 1), rough, metal)


def gilt(name, seed, tile_m=0.5):
    """Gold leaf over red lacquer (sơn thếp): rubbed through at high points, crazed, dusty."""
    n = N
    f1, edge, _ = T.voronoi(n, seed, 700, 0.9)
    craze = T.smoothstep(1.4, 0.0, edge)
    rub = T.smoothstep(0.8, 2.2, T.spectral(n, seed + 1, 2.0, 3, 150))
    leaf = T.spectral(n, seed + 2, 1.0, 20, 300) * 0.00004
    gold = T.colorize(T.fbm(n, seed + 3, 4, 200), [(0.0, "#8a6424"), (0.5, "#b18a3c"), (1.0, "#cfa955")])
    red = _const("#6a1710")
    col = T.lerp(gold, red, rub * 0.85)
    col = T.lerp(col, col * 0.55, craze[..., None] * 0.5)
    dust = T.smoothstep(0.0, 2.0, T.spectral(n, seed + 4, 2, 2, 60))
    col = T.lerp(col, col * T.rgb("#8f8576"), dust * 0.25)
    metal = np.clip((1 - rub) * 0.9 - dust * 0.3, 0, 1)
    rough = np.clip(0.35 + rub * 0.25 + dust * 0.25 + craze * 0.1, 0.2, 1)
    h = leaf - craze * 0.00008
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(1 - craze * 0.3, 0, 1), rough, metal)


def tarp_stripe(name, seed, tile_m=1.0, stripes=("#c43a2c", "#f0ece4", "#2a5aa8"), widths=(0.06, 0.06, 0.06)):
    """Woven polyethylene tarp (bạt sọc) — the red/white/blue striped market tarp. Stripes along U."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    per = n / round(n / (2.5 / 1000 / tile_m * n))
    weave = np.where((np.floor(xx / per) + np.floor(yy / per)) % 2 == 0,
                     np.sin(xx / per * math.pi * 2), np.sin(yy / per * math.pi * 2))
    total = sum(widths)
    reps = max(1, round(tile_m / total))
    pos = np.mod(yy / n * reps, 1.0) * total
    col = np.zeros((n, n, 3), np.float32)
    acc = 0.0
    for c, w in zip(stripes, widths):
        m = (pos >= acc) & (pos < acc + w)
        col[m] = T.rgb(c)
        acc += w
    col = T.hsv_jitter(col, T.spectral(n, seed, 2.0, 1, 30) * 0.06 + weave * 0.025, -0.08)
    sun = T.smoothstep(-1.0, 2.0, T.spectral(n, seed + 1, 2.2, 1, 12))
    col = T.lerp(col, col * 0.7 + T.rgb("#c9c3b4") * 0.3, sun * 0.45)      # UV fading
    dirt = T.smoothstep(0.3, 2.2, T.spectral(n, seed + 2, 2.2, 2, 40))
    st = T.streaks(n, seed + 3, 0.4, 6)
    col = T.lerp(col, col * T.rgb("#7d7466"), np.clip(dirt * 0.35 + st * 0.35, 0, 0.6))
    h = weave * 0.0001 + T.spectral(n, seed + 4, 2.4, 1, 10) * 0.003
    rough = np.clip(0.55 + dirt * 0.2 + st * 0.1, 0.3, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.92), T.normal_from_height(h, tile_m),
                      np.clip(0.85 + weave * 0.08, 0, 1), rough, 0.0)


def wet_concrete_floor(name, seed, tile_m=2.0):
    """Market floor: trowelled concrete, wet patches with low roughness, drain stains, fish-scale grit."""
    n = N
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    trow = T.spectral(n, seed, 2.0, 4, 120, aniso=(1.0, 0.7), rot_deg=30) * 0.0005
    agg = T.spectral(n, seed + 1, 0.6, 80) * 0.0002
    cracks = T.crack_mask(n, seed + 2, 3, (80, 260), 1.2, 0.3)
    joint = np.exp(-((np.mod(xx, n / 2) - 1) ** 2) / 3.0) + np.exp(-((np.mod(yy, n / 2) - 1) ** 2) / 3.0)
    h = trow + agg - cracks * 0.0015 - np.clip(joint, 0, 1) * 0.004
    col = T.colorize(T.fbm(n, seed + 3, 2, 200), [(0.0, "#5f5d57"), (0.5, "#7a776f"), (1.0, "#8f8b81")])
    wet = T.smoothstep(0.2, 1.4, T.spectral(n, seed + 4, 2.4, 1.5, 30))
    stain = T.smoothstep(0.6, 2.4, T.spectral(n, seed + 5, 2.0, 2, 60))
    col = T.lerp(col, col * 0.62, wet * 0.6)
    col = T.lerp(col, col * T.rgb("#6d6250"), stain * 0.5)
    col = T.lerp(col, T.rgb("#2c2a26"), cracks * 0.5)
    ao = T.cavity_ao(h, tile_m, 0.01, 0.002, 1)
    col = col * (0.7 + 0.3 * ao[..., None])
    rough = np.clip(0.82 - wet * 0.62 + stain * 0.05, 0.08, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.5 + 0.5 * ao, 0, 1), rough, 0.0)


def leaves_litter(name, seed, tile_m=2.0):
    """Packed earth with fallen banyan leaves (courtyard corners, islet ground)."""
    n = N
    rng = np.random.default_rng(seed)
    h = T.spectral(n, seed, 2.2, 2, 200) * 0.004
    col = T.colorize(T.fbm(n, seed + 1, 2, 300), [(0.0, "#3e3428"), (0.5, "#5a4a37"), (1.0, "#6f604b")])
    lv = np.zeros((n, n), np.float32)
    lcol = np.zeros((n, n, 3), np.float32)
    pal = [T.rgb(c) for c in ("#7a5a28", "#94702f", "#5d4a24", "#a2803e", "#6b6a2c", "#3f4a22")]

    def draw_leaf(img, cimg, cx, cy, L, W, ang, c):
        yy0, xx0 = np.mgrid[-int(L): int(L) + 1, -int(L): int(L) + 1].astype(np.float32)
        ca, sa = math.cos(ang), math.sin(ang)
        u = (xx0 * ca + yy0 * sa) / L
        v = (-xx0 * sa + yy0 * ca) / W
        taper = np.clip(1.0 - 0.45 * u, 0.2, 2.0)
        m = ((u * u + (v / taper) ** 2) < 1.0).astype(np.float32)
        ys = (np.arange(-int(L), int(L) + 1) + int(cy)) % n
        xs = (np.arange(-int(L), int(L) + 1) + int(cx)) % n
        sub = img[np.ix_(ys, xs)]
        img[np.ix_(ys, xs)] = np.maximum(sub, m * (0.8 + 0.2 * (1 - np.abs(v))))
        cs = cimg[np.ix_(ys, xs)]
        cimg[np.ix_(ys, xs)] = np.where(m[..., None] > 0, c * (0.85 + 0.15 * (1 - np.abs(v)))[..., None], cs)
    for _ in range(260):
        draw_leaf(lv, lcol, rng.uniform(0, n), rng.uniform(0, n), rng.uniform(18, 34), rng.uniform(7, 13),
                  rng.uniform(0, math.pi), pal[rng.integers(0, len(pal))] * rng.uniform(0.8, 1.1))
    col = T.lerp(col, lcol, lv > 0)
    h = h + lv * 0.0015
    ao = T.cavity_ao(h, tile_m, 0.01, 0.002, 1)
    col = col * (0.6 + 0.4 * ao[..., None])
    rough = np.clip(0.9 - lv * 0.15, 0.4, 1)
    return T.save_set(OUT, name, np.clip(col, 0.03, 0.9), T.normal_from_height(h, tile_m),
                      np.clip(0.4 + 0.6 * ao, 0, 1), rough, 0.0)


# ---------------------------------------------------------------------------
SETS = {
    # temple
    "lacquer_red": (1.0, lambda: GT.wood("lacquer_red", 701, "#7e1a12", "#1b120e", tile_m=1.0, peel=0.18)),
    "gilt": (0.5, lambda: gilt("gilt", 702)),
    "wood_aged": (1.0, lambda: GT.wood("wood_aged", 703, None, tile_m=1.0)),
    "bluestone": (1.0, lambda: bluestone("bluestone", 704)),
    "brick_paving": (2.0, lambda: GT.tiles("brick_paving", 705, 2.0, 7, 7,
                                           ["#8c4a32", "#9e5839", "#7a3e2a", "#a8654a", "#6c3a2a"],
                                           [3, 3, 2, 2, 1], grout="#5d5a48", grout_m=0.012, speckle=0.08,
                                           gloss=0.62, missing=0.01, bevel_m=0.004)),
    "plaster_temple": (2.0, lambda: GT.plaster("plaster_temple", 706, "#cfa752", "#e0c27e", "#d8cdb5", "#9a9384",
                                               peel=0.28, dirt=0.75, patches=4, repaint="#c79a45")),
    "bronze": (0.5, lambda: bronze("bronze", 707)),
    # lake
    "stone_embank": (2.0, lambda: ashlar("stone_embank", 711, 2.0, 0.4, (0.6, 1.2),
                                         ("#5d605b", "#76786f", "#8c8b80"), "#7b776a", moss=0.55, waterline=0.18)),
    "stone_plinth": (2.0, lambda: ashlar("stone_plinth", 712, 2.0, 0.33, (0.45, 0.9),
                                         ("#6b6e6a", "#83847d", "#9a978c"), "#8c8678", moss=0.35)),
    "wood_red_paint": (1.0, lambda: GT.wood("wood_red_paint", 713, "#a3261a", "#5e4a3b", tile_m=1.0, peel=0.25)),
    "leaves_ground": (2.0, lambda: leaves_litter("leaves_ground", 714)),
    # market
    "tile_white": (1.0, lambda: GT.tiles("tile_white", 721, 1.0, 5, 5, ["#e3e1da", "#dad8d0", "#eceae4", "#cfccc2"],
                                         [4, 3, 2, 1], grout="#9c978a", grout_m=0.003, gloss=0.08, missing=0.006,
                                         bevel_m=0.002)),
    "market_floor": (2.0, lambda: wet_concrete_floor("market_floor", 722)),
    "steel_green": (1.0, lambda: GT.painted_metal("steel_green", 723, paint="#4c6a58", rust=0.5, chips=0.5)),
    "tarp_stripe": (1.0, lambda: tarp_stripe("tarp_stripe", 724)),
    "tarp_blue": (1.0, lambda: tarp_stripe("tarp_blue", 725, 1.0, ("#2b5f9e", "#2f66a8"), (0.5, 0.5))),
    "tarp_orange": (1.0, lambda: tarp_stripe("tarp_orange", 726, 1.0, ("#d26a22", "#d8742b"), (0.5, 0.5))),
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
    os.makedirs(OUT, exist_ok=True)
    for nme in names:
        t0 = time.time()
        SETS[nme][1]()
        print(f"  {nme}: {time.time() - t0:.1f}s", flush=True)
    with open(os.path.join(OUT, "materials.json"), "w") as fh:
        json.dump({k: {"tile_m": v[0], "albedo": f"{k}_albedo.jpg", "normal": f"{k}_normal.png",
                       "orm": f"{k}_orm.jpg"} for k, v in SETS.items()}, fh, indent=1)
    if a.sheet:
        contact_sheet(list(SETS), os.path.join(ROOT, "qa", "out", "city-landmarks", "tex_sheet.jpg"))


if __name__ == "__main__":
    main()
