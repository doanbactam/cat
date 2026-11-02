#!/usr/bin/env python3
"""Procedural ground + decal textures for Hàng Mây (owner: world).

Usage:  python3 scripts/world/tools/gen_ground_textures.py [--only asphalt,pavers,...] [--sheet]

Writes tileable PBR sets into assets/textures/ground/<set>_{albedo.jpg,normal.png,orm.jpg}
(ORM: R = AO, G = roughness, B = metallic) and RGBA decals into assets/textures/decals/.
Everything is seeded/deterministic. numpy + Pillow only.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GROUND = os.path.join(ROOT, "assets", "textures", "ground")
DECALS = os.path.join(ROOT, "assets", "textures", "decals")
FONT_BOLD = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-700.ttf")
FONT_MED = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-500.ttf")


# ----------------------------------------------------------------------------------------------
# noise helpers (periodic → tileable)
# ----------------------------------------------------------------------------------------------

def periodic_noise(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Smooth periodic value noise in [0,1] (bicubic upsample of a wrapped random grid)."""
    g = rng.random((cells, cells)).astype(np.float32)
    big = np.tile(g, (3, 3))
    im = Image.fromarray(big, mode="F").resize((size * 3, size * 3), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32)[size:2 * size, size:2 * size]
    return np.clip(a, 0.0, 1.0)


def fbm(size: int, base: int, octaves: int, rng: np.random.Generator, gain: float = 0.5) -> np.ndarray:
    out = np.zeros((size, size), np.float32)
    amp, tot, c = 1.0, 0.0, base
    for _ in range(octaves):
        if c >= size:
            break
        out += amp * periodic_noise(size, c, rng)
        tot += amp
        amp *= gain
        c *= 2
    return out / tot


def blur_wrap(a: np.ndarray, radius: float) -> np.ndarray:
    """Periodic gaussian blur via FFT (texture tiles stay seamless)."""
    if radius <= 0:
        return a
    h, w = a.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2.0 * (math.pi ** 2) * (radius ** 2) * (fx ** 2 + fy ** 2))
    return np.fft.irfft2(np.fft.rfft2(a) * g, s=a.shape).astype(np.float32)


def normal_from_height(h: np.ndarray, strength: float) -> np.ndarray:
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5 * strength
    n = np.stack([-dx, dy, np.ones_like(h)], -1)  # OpenGL (+Y up) convention
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def ao_from_height(h: np.ndarray, radius: float = 6.0, strength: float = 2.5) -> np.ndarray:
    blur = blur_wrap(h, radius)
    ao = 1.0 - np.clip((blur - h) * strength, 0.0, 1.0)
    return np.clip(ao, 0.0, 1.0)


def crack_field(size: int, rng: np.random.Generator, count: int, length: tuple, width: float,
                branch: float = 0.3) -> np.ndarray:
    """Random-walk cracks drawn wrap-around; returns 0..1 mask."""
    im = Image.new("L", (size * 3, size * 3), 0)
    d = ImageDraw.Draw(im)
    for _ in range(count):
        x, y = rng.random() * size + size, rng.random() * size + size
        ang = rng.random() * math.tau
        n = int(rng.integers(length[0], length[1]))
        w = max(1, int(width * (0.6 + rng.random() * 0.8)))
        stack = [(x, y, ang, n, w)]
        while stack:
            x, y, ang, n, w = stack.pop()
            for _i in range(n):
                ang += rng.normal(0, 0.35)
                step = 3 + rng.random() * 4
                nx, ny = x + math.cos(ang) * step, y + math.sin(ang) * step
                d.line([(x, y), (nx, ny)], fill=255, width=w)
                x, y = nx, ny
                if rng.random() < branch * 0.04 and w > 1:
                    stack.append((x, y, ang + rng.choice([-1, 1]) * (0.6 + rng.random()), n // 3, max(1, w - 1)))
    a = np.asarray(im, np.float32) / 255.0
    # fold the 3x3 canvas back onto the tile (wrap)
    out = np.zeros((size, size), np.float32)
    for i in range(3):
        for j in range(3):
            out = np.maximum(out, a[i * size:(i + 1) * size, j * size:(j + 1) * size])
    return out


def lerp(a, b, t):
    return a + (b - a) * t


def col(rgb) -> np.ndarray:
    return np.array(rgb, np.float32) / 255.0


def save_set(name: str, albedo: np.ndarray, height: np.ndarray, rough: np.ndarray,
             nstrength: float, ao: np.ndarray | None = None, metal: np.ndarray | None = None,
             normal: np.ndarray | None = None) -> None:
    os.makedirs(GROUND, exist_ok=True)
    alb = (np.clip(albedo, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)  # albedo given in linear
    Image.fromarray(alb, "RGB").save(os.path.join(GROUND, f"{name}_albedo.jpg"), quality=90)
    nrm = normal if normal is not None else normal_from_height(height, nstrength)
    Image.fromarray(nrm, "RGB").save(os.path.join(GROUND, f"{name}_normal.png"), optimize=True)
    if ao is None:
        ao = ao_from_height(height)
    if metal is None:
        metal = np.zeros_like(rough)
    orm = np.stack([ao, np.clip(rough, 0.02, 1), metal], -1)
    Image.fromarray((orm * 255).astype(np.uint8), "RGB").save(os.path.join(GROUND, f"{name}_orm.jpg"), quality=92)
    print("wrote", name, albedo.shape[0])


# ----------------------------------------------------------------------------------------------
# sets
# ----------------------------------------------------------------------------------------------

def gen_asphalt(seed: int = 11, S: int = 2048) -> None:
    """4 m tile: aged Hanoi asphalt — aggregate, ravelling, sealed cracks, patches, oil drips."""
    rng = np.random.default_rng(seed)
    macro = fbm(S, 4, 4, rng)
    mid = fbm(S, 32, 4, rng)
    # aggregate: many small stones
    stones = periodic_noise(S, 512, rng)
    stones2 = periodic_noise(S, 256, rng)
    agg = np.clip((stones - 0.55) * 4, 0, 1) * 0.6 + np.clip((stones2 - 0.6) * 3, 0, 1) * 0.4
    pits = np.clip((0.22 - periodic_noise(S, 400, rng)) * 6, 0, 1)
    h = 0.5 + agg * 0.35 - pits * 0.5 + (mid - 0.5) * 0.15
    # patches (rectangular repaired areas, darker & smoother)
    patch = np.zeros((S, S), np.float32)
    pim = Image.new("L", (S, S), 0)
    pd = ImageDraw.Draw(pim)
    for _ in range(5):
        w, hh = rng.integers(S // 10, S // 4), rng.integers(S // 12, S // 5)
        x, y = rng.integers(0, S - w), rng.integers(0, S - hh)
        pd.rectangle([x, y, x + w, y + hh], fill=int(rng.integers(160, 255)))
    patch = blur_wrap(np.asarray(pim, np.float32) / 255.0, 1.5)
    patch_edge = np.clip(np.abs(patch - blur_wrap(patch, 3)) * 8, 0, 1)
    # cracks: sealed (black tar) and open
    cr = crack_field(S, rng, 26, (40, 160), 3, branch=0.6)
    cr_soft = blur_wrap(cr, 1.2)
    sealed = blur_wrap(crack_field(S, rng, 8, (60, 200), 9, branch=0.2), 1.5)
    h = h - cr_soft * 0.6 + patch * 0.05 - patch_edge * 0.2
    # colours (linear)
    base = lerp(col((58, 58, 60)), col((92, 90, 88)), macro[..., None])
    base = base * (0.85 + agg[..., None] * 0.35)
    stone_tint = lerp(col((120, 112, 104)), col((140, 138, 135)), stones2[..., None])
    base = lerp(base, stone_tint, np.clip(agg - 0.3, 0, 1)[..., None] * 0.6)
    patchc = col((50, 50, 52)) * (0.9 + mid[..., None] * 0.2)
    base = lerp(base, patchc, patch[..., None] * 0.55)
    base = lerp(base, col((22, 22, 23)), np.clip(sealed * 1.3, 0, 1)[..., None])
    base = lerp(base, col((30, 28, 26)), cr_soft[..., None] * 0.9)
    # oil drips / tyre grime (soft dark blobs, slightly rainbowy shine via low roughness)
    oil = np.clip((fbm(S, 16, 3, rng) - 0.62) * 5, 0, 1)
    base = lerp(base, col((26, 25, 25)), oil[..., None] * 0.7)
    # dust in low points
    dust = np.clip((blur_wrap(h, 4) - h) * 6, 0, 1)
    base = lerp(base, col((120, 108, 92)), dust[..., None] * 0.35)
    base = (base ** 2.2)  # treat values as sRGB-ish → linear
    rough = 0.86 + (mid - 0.5) * 0.1 - oil * 0.35 - patch * 0.06 + agg * 0.04
    save_set("asphalt", base, h, rough, 3.0)


def gen_pavers(seed: int = 21, S: int = 2048) -> None:
    """2 m tile = 5×5 Hanoi 40 cm cement sidewalk tiles with 3×3 groove pattern; varied, a few broken."""
    rng = np.random.default_rng(seed)
    n = 5
    cell = S // n
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    lx = (xx % cell) / cell
    ly = (yy % cell) / cell
    ix = (xx // cell).astype(int)
    iy = (yy // cell).astype(int)
    joint_w = 0.018
    edge = np.minimum(np.minimum(lx, 1 - lx), np.minimum(ly, 1 - ly))
    joint = np.clip((joint_w - edge) / joint_w, 0, 1)
    bevel = np.clip((edge - joint_w) / 0.02, 0, 1)
    # grooves: 3x3 sub-squares (classic pattern)
    gx = np.minimum(np.abs(lx - 1 / 3), np.abs(lx - 2 / 3))
    gy = np.minimum(np.abs(ly - 1 / 3), np.abs(ly - 2 / 3))
    groove = np.clip((0.008 - np.minimum(gx, gy)) / 0.008, 0, 1) * (edge > 0.06)
    tint_rng = rng.random((n, n, 3))
    kind = rng.random((n, n))
    grain = fbm(S, 64, 4, rng)
    macro = fbm(S, 4, 3, rng)
    speck = np.clip((periodic_noise(S, 700, rng) - 0.7) * 4, 0, 1)
    # tile palette: weathered red-terracotta cement & grey cement tiles
    reds = np.array([[150, 82, 66], [138, 76, 62], [160, 95, 76]], np.float32) / 255
    greys = np.array([[150, 146, 138], [128, 126, 120], [170, 165, 155]], np.float32) / 255
    albedo = np.zeros((S, S, 3), np.float32)
    h = np.zeros((S, S), np.float32)
    broken_mask = np.zeros((S, S), np.float32)
    for j in range(n):
        for i in range(n):
            m = (ix == i) & (iy == j)
            if kind[j, i] < 0.62:
                c = reds[int(tint_rng[j, i, 0] * 3) % 3]
            else:
                c = greys[int(tint_rng[j, i, 1] * 3) % 3]
            c = c * (0.85 + tint_rng[j, i, 2] * 0.25)
            albedo[m] = c
            h[m] = 0.55 + (tint_rng[j, i, 0] - 0.5) * 0.06  # slight per-tile height offset
    # broken / missing tiles: two per tile set
    bim = Image.new("L", (S, S), 0)
    bd = ImageDraw.Draw(bim)
    for _ in range(2):
        i, j = int(rng.integers(0, n)), int(rng.integers(0, n))
        cx, cy = i * cell + cell / 2, j * cell + cell / 2
        pts = []
        for k in range(9):
            a = k / 9 * math.tau + rng.normal(0, 0.2)
            r = cell * (0.25 + rng.random() * 0.3)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        bd.polygon(pts, fill=255)
    broken_mask = blur_wrap(np.asarray(bim, np.float32) / 255.0, 2.0)
    cracks = blur_wrap(crack_field(S, rng, 14, (20, 70), 2, branch=0.8), 0.8) * (1 - joint)
    dirt = fbm(S, 8, 4, rng)
    albedo *= (0.88 + grain[..., None] * 0.22)
    albedo = lerp(albedo, albedo * 0.7, speck[..., None] * 0.5)
    # grime in joints and grooves
    jointc = col((52, 46, 40))
    albedo = lerp(albedo, jointc, np.clip(joint + groove * 0.7, 0, 1)[..., None])
    albedo = lerp(albedo, albedo * 0.72, (1 - bevel)[..., None] * 0.4)
    # footfall wear / dirt film (macro)
    albedo = lerp(albedo, col((96, 88, 78)), (np.clip(dirt - 0.45, 0, 1) * 1.3)[..., None] * 0.6)
    albedo *= (0.9 + macro[..., None] * 0.18)
    # broken: exposed mortar bed + soil
    soil = lerp(col((70, 58, 44)), col((110, 100, 86)), periodic_noise(S, 128, rng)[..., None])
    albedo = lerp(albedo, soil, broken_mask[..., None])
    albedo = lerp(albedo, col((40, 34, 30)), cracks[..., None] * 0.9)
    h = h - joint * 0.35 - groove * 0.2 - (1 - bevel) * 0.05 - broken_mask * 0.4 - cracks * 0.25 + grain * 0.04
    rough = 0.82 + grain * 0.08 + joint * 0.1 - np.clip(dirt - 0.6, 0, 1) * 0.2
    albedo = albedo ** 2.2
    save_set("pavers", albedo, h, rough, 4.0)


def gen_granite(seed: int = 31, S: int = 1024) -> None:
    """1 m tile granite curb stone (bush-hammered top, chips)."""
    rng = np.random.default_rng(seed)
    f1 = periodic_noise(S, 300, rng)
    f2 = periodic_noise(S, 150, rng)
    macro = fbm(S, 4, 3, rng)
    feld = np.clip((f1 - 0.62) * 5, 0, 1)
    mica = np.clip((0.3 - f2) * 5, 0, 1)
    base = lerp(col((140, 138, 134)), col((176, 172, 166)), macro[..., None])
    base = lerp(base, col((212, 206, 198)), feld[..., None] * 0.7)
    base = lerp(base, col((40, 40, 44)), mica[..., None] * 0.8)
    grime = fbm(S, 8, 4, rng)
    base = lerp(base, col((70, 66, 60)), np.clip(grime - 0.55, 0, 1)[..., None] * 1.4)
    h = 0.5 + (f1 - 0.5) * 0.2 + (periodic_noise(S, 512, rng) - 0.5) * 0.25
    rough = 0.7 + (f2 - 0.5) * 0.2 - mica * 0.3
    save_set("granite_curb", base ** 2.2, h, rough, 2.5)


def gen_concrete_alley(seed: int = 41, S: int = 1024) -> None:
    """2 m tile poured alley concrete: trowel marks, cracks with moss, damp stains."""
    rng = np.random.default_rng(seed)
    macro = fbm(S, 4, 4, rng)
    mid = fbm(S, 24, 4, rng)
    fine = periodic_noise(S, 400, rng)
    cr = crack_field(S, rng, 10, (40, 140), 2, branch=0.7)
    crs = blur_wrap(cr, 1.0)
    moss_zone = np.clip(blur_wrap(cr, 10) * 6, 0, 1) * np.clip((fbm(S, 16, 3, rng) - 0.35) * 2, 0, 1)
    damp = np.clip((macro - 0.55) * 3, 0, 1)
    base = lerp(col((150, 146, 136)), col((118, 114, 106)), mid[..., None])
    base *= (0.92 + fine[..., None] * 0.12)
    base = lerp(base, col((88, 86, 80)), damp[..., None] * 0.6)
    moss = lerp(col((62, 78, 34)), col((92, 104, 46)), periodic_noise(S, 128, rng)[..., None])
    base = lerp(base, moss, moss_zone[..., None] * 0.85)
    base = lerp(base, col((45, 42, 38)), crs[..., None])
    # broom lines
    yy = np.mgrid[0:S, 0:S][0].astype(np.float32)
    broom = (np.sin(yy / S * math.tau * 90 + periodic_noise(S, 16, rng) * 6) * 0.5 + 0.5) * 0.04
    h = 0.5 + (mid - 0.5) * 0.2 + broom - crs * 0.5 + moss_zone * 0.08 + (fine - 0.5) * 0.06
    rough = 0.9 - damp * 0.15 + moss_zone * 0.05
    save_set("concrete_alley", base ** 2.2, h, rough, 3.0)


def gen_brick_courtyard(seed: int = 51, S: int = 1024) -> None:
    """2 m tile: old red bát tràng-style square bricks (30 cm) laid in grid, mossy joints."""
    rng = np.random.default_rng(seed)
    n = 6  # ≈33 cm squares in 2 m
    cell = S / n
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    lx = (xx % cell) / cell
    ly = (yy % cell) / cell
    ix = (xx // cell).astype(int) % n
    iy = (yy // cell).astype(int) % n
    edge = np.minimum(np.minimum(lx, 1 - lx), np.minimum(ly, 1 - ly))
    jw = 0.03 + (periodic_noise(S, 64, rng) - 0.5) * 0.015
    joint = np.clip((jw - edge) / 0.015, 0, 1)
    t = rng.random((n, n))
    t2 = rng.random((n, n))
    pal = np.array([[132, 76, 58], [116, 66, 52], [146, 92, 70], [108, 70, 58]], np.float32) / 255
    base = pal[(t[iy, ix] * 4).astype(int) % 4] * (0.85 + t2[iy, ix][..., None] * 0.3)
    grain = fbm(S, 48, 4, rng)
    base *= (0.85 + grain[..., None] * 0.3)
    worn = np.clip((fbm(S, 8, 3, rng) - 0.5) * 2, 0, 1)
    base = lerp(base, col((150, 120, 100)), worn[..., None] * 0.3)
    moss = lerp(col((50, 66, 30)), col((86, 98, 42)), periodic_noise(S, 96, rng)[..., None])
    mj = np.clip(blur_wrap(joint, 2) * 2.5, 0, 1) * np.clip((fbm(S, 12, 3, rng) - 0.3) * 2, 0, 1)
    base = lerp(base, col((60, 52, 44)), joint[..., None])
    base = lerp(base, moss, mj[..., None] * 0.8)
    h = 0.55 - joint * 0.4 + (grain - 0.5) * 0.1 + (t[iy, ix] - 0.5) * 0.05
    h -= np.clip((0.2 - periodic_noise(S, 256, rng)) * 3, 0, 1) * 0.15
    rough = 0.85 + grain * 0.1 - mj * 0.05
    save_set("brick_courtyard", base ** 2.2, h, rough, 4.0)


def gen_grass(seed: int = 61, S: int = 1024) -> None:
    """2 m tile tired park lawn with bare dirt patches and fallen leaves."""
    rng = np.random.default_rng(seed)
    macro = fbm(S, 4, 4, rng)
    blades = periodic_noise(S, 512, rng)
    blades2 = periodic_noise(S, 300, rng)
    bare = np.clip((fbm(S, 6, 4, rng) - 0.58) * 4, 0, 1)
    g = lerp(col((54, 78, 30)), col((96, 110, 44)), (blades * 0.6 + macro * 0.4)[..., None])
    g = lerp(g, col((120, 118, 58)), np.clip(blades2 - 0.7, 0, 1)[..., None] * 2)
    dirt = lerp(col((96, 80, 58)), col((128, 110, 84)), periodic_noise(S, 128, rng)[..., None])
    base = lerp(g, dirt, bare[..., None])
    leaves = np.clip((periodic_noise(S, 160, rng) - 0.82) * 8, 0, 1)
    base = lerp(base, col((140, 96, 44)), leaves[..., None] * 0.8)
    h = 0.5 + (blades - 0.5) * 0.4 * (1 - bare) + (macro - 0.5) * 0.1
    rough = 0.92 - leaves * 0.1
    save_set("grass", base ** 2.2, h, rough, 3.0)


def gen_stone_embankment(seed: int = 71, S: int = 1024) -> None:
    """2 m tile: lake embankment — coursed granite blocks (≈50×25 cm), algae near bottom (v=1)."""
    rng = np.random.default_rng(seed)
    rows = 8
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    rh = S / rows
    r = (yy // rh).astype(int)
    off = (r % 2) * 0.5
    bw = S / 4
    u = (xx / bw + off)
    lx = u % 1.0
    ly = (yy % rh) / rh
    bid = (np.floor(u).astype(int) % 4) + r * 4
    edge = np.minimum(np.minimum(lx * 2, (1 - lx) * 2), np.minimum(ly, 1 - ly))
    joint = np.clip((0.05 - edge) / 0.03, 0, 1)
    t = rng.random(rows * 4 + 8)
    base = lerp(col((120, 116, 108)), col((156, 150, 140)), t[bid][..., None])
    grain = fbm(S, 64, 4, rng)
    base *= (0.85 + grain[..., None] * 0.3)
    v = yy / S
    algae = np.clip((v - 0.55) * 2.5, 0, 1) * (0.6 + fbm(S, 16, 3, rng) * 0.6)
    base = lerp(base, col((58, 72, 44)), np.clip(algae, 0, 1)[..., None] * 0.8)
    streak = np.clip((periodic_noise(S, 32, rng) - 0.5) * 2, 0, 1) * np.clip(1 - v * 1.5, 0, 1)
    base = lerp(base, col((70, 66, 60)), (streak * 0.3)[..., None])
    base = lerp(base, col((70, 64, 56)), joint[..., None])
    bulge = np.sin(np.clip(lx, 0, 1) * math.pi) * np.sin(np.clip(ly, 0, 1) * math.pi)
    h = 0.4 + bulge * 0.25 - joint * 0.4 + (grain - 0.5) * 0.15
    rough = 0.8 - algae * 0.25
    save_set("stone_embankment", base ** 2.2, h, rough, 4.0)


def gen_wood_deck(seed: int = 81, S: int = 1024) -> None:
    """1 m tile: weathered teak planks (12.5 cm) for the bridge deck / walkways."""
    rng = np.random.default_rng(seed)
    n = 8
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    pw = S / n
    pi = (xx // pw).astype(int)
    lx = (xx % pw) / pw
    shift = rng.random(n)[pi] * S
    vy = ((yy + shift) % S) / S
    gap = np.clip((0.04 - np.minimum(lx, 1 - lx)) / 0.03, 0, 1)
    endj = np.clip((0.006 - np.abs(vy - 0.5)) / 0.006, 0, 1) * (rng.random(n)[pi] > 0.4)
    grain_n = periodic_noise(S, 64, rng)
    grain = np.sin((xx / pw * 6 + grain_n * 8) * math.pi) * 0.5 + 0.5
    t = rng.random(n)[pi]
    base = lerp(col((112, 78, 50)), col((150, 112, 76)), t[..., None])
    base *= (0.8 + grain[..., None] * 0.25)
    weather = fbm(S, 8, 3, rng)
    base = lerp(base, col((128, 120, 108)), np.clip(weather - 0.45, 0, 1)[..., None] * 1.2)
    base = lerp(base, col((30, 24, 20)), np.clip(gap + endj, 0, 1)[..., None])
    h = 0.6 - gap * 0.5 - endj * 0.3 + grain * 0.06
    rough = 0.78 + weather * 0.12
    save_set("wood_deck", base ** 2.2, h, rough, 3.0)


def gen_lakebed(seed: int = 91, S: int = 512) -> None:
    rng = np.random.default_rng(seed)
    m = fbm(S, 4, 5, rng)
    base = lerp(col((40, 44, 30)), col((76, 72, 52)), m[..., None])
    h = m
    save_set("lakebed", base ** 2.2, h, 0.95 - m * 0.05, 2.0)


def gen_lane_paint(seed: int = 101, S: int = 1024) -> None:
    """Worn road paint mask (RGBA, white; alpha = paint coverage) — 1×4 m strip (x = across)."""
    rng = np.random.default_rng(seed)
    wear = fbm(S, 8, 5, rng)
    chips = periodic_noise(S, 256, rng)
    a = np.clip((wear - 0.3) * 2.5, 0, 1) * np.clip((chips - 0.25) * 4, 0, 1)
    alpha = (a * 0.92 * 255).astype(np.uint8)
    rgb = np.stack([np.full((S, S), 232), np.full((S, S), 228), np.full((S, S), 214)], -1).astype(np.uint8)
    os.makedirs(DECALS, exist_ok=True)
    Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(os.path.join(DECALS, "lane_paint.png"), optimize=True)
    print("wrote lane_paint")


# ----------------------------------------------------------------------------------------------
# decals (RGBA albedo; some with normal maps)
# ----------------------------------------------------------------------------------------------

def _save_decal(name: str, rgba: np.ndarray, normal: np.ndarray | None = None) -> None:
    os.makedirs(DECALS, exist_ok=True)
    Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(DECALS, f"{name}.png"), optimize=True)
    if normal is not None:
        Image.fromarray(normal, "RGB").save(os.path.join(DECALS, f"{name}_normal.png"), optimize=True)
    print("wrote decal", name)


def _radial(S: int) -> np.ndarray:
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    return np.hypot(xx - S / 2, yy - S / 2) / (S / 2)


def decal_oil(seed: int, name: str, S: int = 512) -> None:
    rng = np.random.default_rng(seed)
    r = _radial(S)
    n = fbm(S, 6, 4, rng)
    a = np.clip((1.0 - r * (0.9 + n * 0.7)) * 2.2, 0, 1)
    a = a * (0.55 + fbm(S, 32, 3, rng) * 0.45)
    ring = np.clip(1 - np.abs(r * (0.9 + n * 0.7) - 0.75) * 12, 0, 1) * 0.3
    rgb = np.stack([np.full((S, S), 18), np.full((S, S), 17), np.full((S, S), 16)], -1).astype(np.float32)
    rgb += ring[..., None] * np.array([30, 24, 40])
    _save_decal(name, np.dstack([rgb, np.clip(a * 0.85, 0, 1) * 255]))


def decal_crack(seed: int, name: str, S: int = 512) -> None:
    rng = np.random.default_rng(seed)
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    for k in range(3):
        x, y = S * 0.5 + rng.normal(0, 30), S * 0.5 + rng.normal(0, 30)
        ang = rng.random() * math.tau
        w = 5
        for i in range(70):
            ang += rng.normal(0, 0.3)
            nx, ny = x + math.cos(ang) * 4, y + math.sin(ang) * 4
            if not (20 < nx < S - 20 and 20 < ny < S - 20):
                break
            d.line([(x, y), (nx, ny)], fill=255, width=max(1, int(w)))
            x, y = nx, ny
            w = max(1.0, w - 0.06)
            if rng.random() < 0.06:
                bx, by, ba = x, y, ang + rng.choice([-1, 1]) * 0.9
                for j in range(20):
                    ba += rng.normal(0, 0.3)
                    nbx, nby = bx + math.cos(ba) * 3, by + math.sin(ba) * 3
                    if not (10 < nbx < S - 10 and 10 < nby < S - 10):
                        break
                    d.line([(bx, by), (nbx, nby)], fill=200, width=1)
                    bx, by = nbx, nby
    m = np.asarray(im.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    halo = np.asarray(im.filter(ImageFilter.GaussianBlur(5)), np.float32) / 255
    a = np.clip(m + halo * 0.35, 0, 1)
    rgb = np.zeros((S, S, 3), np.float32) + np.array([28, 25, 22])
    rgb = lerp(np.array([70, 64, 56], np.float32), rgb, m[..., None])
    h = 1 - m
    _save_decal(name, np.dstack([rgb, a * 255]), normal_from_height(h, 6))


def decal_leaves(seed: int, name: str, S: int = 512) -> None:
    """Scatter of fallen leaves (bàng/sấu-like) — dry browns and a few yellow/green."""
    rng = np.random.default_rng(seed)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hm = Image.new("L", (S, S), 0)
    for k in range(int(rng.integers(26, 40))):
        L = rng.uniform(20, 46)
        W = L * rng.uniform(0.35, 0.55)
        cx, cy = rng.uniform(L, S - L), rng.uniform(L, S - L)
        if np.hypot(cx - S / 2, cy - S / 2) > S * 0.45 * rng.uniform(0.6, 1.1):
            continue
        ang = rng.random() * math.tau
        pal = [(122, 80, 36), (150, 104, 46), (96, 60, 30), (176, 140, 60), (110, 120, 50), (160, 74, 34)]
        c = pal[int(rng.integers(0, len(pal)))]
        pts = []
        for i in range(24):
            t = i / 24 * math.tau
            px = math.cos(t) * L / 2
            py = math.sin(t) * W / 2 * (1 - 0.3 * math.cos(t))
            pts.append((cx + px * math.cos(ang) - py * math.sin(ang), cy + px * math.sin(ang) + py * math.cos(ang)))
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dl = ImageDraw.Draw(layer)
        shade = rng.uniform(0.8, 1.1)
        dl.polygon(pts, fill=(int(c[0] * shade), int(c[1] * shade), int(c[2] * shade), 255))
        # midrib
        x0, y0 = cx - math.cos(ang) * L / 2, cy - math.sin(ang) * L / 2
        x1, y1 = cx + math.cos(ang) * L * 0.62, cy + math.sin(ang) * L * 0.62
        dl.line([(x0, y0), (x1, y1)], fill=(int(c[0] * 0.6), int(c[1] * 0.6), int(c[2] * 0.6), 255), width=2)
        im = Image.alpha_composite(im, layer)
        ImageDraw.Draw(hm).polygon(pts, fill=int(120 + rng.random() * 120))
    arr = np.asarray(im, np.float32)
    shadow = np.asarray(im.split()[3].filter(ImageFilter.GaussianBlur(4)), np.float32) / 255
    a = np.maximum(arr[..., 3] / 255, shadow * 0.35)
    rgb = np.where(arr[..., 3:4] > 0, arr[..., :3], 25)
    h = np.asarray(hm.filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
    _save_decal(name, np.dstack([rgb, a * 255]), normal_from_height(h, 3))


def decal_puddle(seed: int, name: str, S: int = 512) -> None:
    """Puddle: alpha = water coverage (used by the wet decal: albedo darkening; roughness → 0)."""
    rng = np.random.default_rng(seed)
    r = _radial(S)
    n = fbm(S, 4, 4, rng)
    shape = 1.0 - r * (0.75 + n * 0.6)
    a = np.clip(shape * 5, 0, 1)
    rim = np.clip(shape * 5, 0, 1) - np.clip(shape * 5 - 0.6, 0, 1)
    rgb = np.zeros((S, S, 3), np.float32) + np.array([30, 32, 34])
    rgb += rim[..., None] * np.array([40, 34, 28])
    _save_decal(name, np.dstack([rgb, a * 255 * 0.75]))


def decal_stain(seed: int, name: str, tint, S: int = 512, strength: float = 0.6) -> None:
    rng = np.random.default_rng(seed)
    r = _radial(S)
    n = fbm(S, 5, 5, rng)
    a = np.clip((1 - r * (0.6 + n)) * 1.6, 0, 1) * (0.5 + fbm(S, 40, 3, rng) * 0.5)
    rgb = np.zeros((S, S, 3), np.float32) + np.array(tint, np.float32)
    _save_decal(name, np.dstack([rgb, a * 255 * strength]))


def decal_chalk(seed: int, name: str, S: int = 1024) -> None:
    """Children's chalk on the pavement: hopscotch (ô lò cò) grid + a cat doodle + numbers."""
    rng = np.random.default_rng(seed)
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    def jline(p0, p1, w=7):
        segs = 12
        pts = []
        for i in range(segs + 1):
            t = i / segs
            pts.append((p0[0] + (p1[0] - p0[0]) * t + rng.normal(0, 1.5), p0[1] + (p1[1] - p0[1]) * t + rng.normal(0, 1.5)))
        d.line(pts, fill=255, width=w, joint="curve")
    # hopscotch along vertical axis
    x0, w, hh = S * 0.18, S * 0.22, S * 0.11
    y = S * 0.92
    font = ImageFont.truetype(FONT_BOLD, int(hh * 0.6))
    num = 1
    layout = [1, 1, 2, 1, 2, 1]
    for k, cnt in enumerate(layout):
        y1 = y - hh
        if cnt == 1:
            jline((x0 + w * 0.5, y), (x0 + w * 1.5, y)); jline((x0 + w * 0.5, y1), (x0 + w * 1.5, y1))
            jline((x0 + w * 0.5, y), (x0 + w * 0.5, y1)); jline((x0 + w * 1.5, y), (x0 + w * 1.5, y1))
            d.text((x0 + w, y - hh / 2), str(num), fill=230, font=font, anchor="mm"); num += 1
        else:
            jline((x0, y), (x0 + w * 2, y)); jline((x0, y1), (x0 + w * 2, y1))
            for xx in (x0, x0 + w, x0 + w * 2):
                jline((xx, y), (xx, y1))
            d.text((x0 + w * 0.5, y - hh / 2), str(num), fill=230, font=font, anchor="mm")
            d.text((x0 + w * 1.5, y - hh / 2), str(num + 1), fill=230, font=font, anchor="mm"); num += 2
        y = y1
    # semicircle "trời" (sky)
    d.arc([x0 + w * 0.3, y - hh * 0.9, x0 + w * 1.7, y + hh * 0.9], 180, 360, fill=255, width=7)
    # cat doodle
    cx, cy, R = S * 0.72, S * 0.4, S * 0.1
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=255, width=7)
    d.polygon([(cx - R * 0.8, cy - R * 0.5), (cx - R * 0.6, cy - R * 1.5), (cx - R * 0.15, cy - R * 0.95)], outline=255, width=7)
    d.polygon([(cx + R * 0.8, cy - R * 0.5), (cx + R * 0.6, cy - R * 1.5), (cx + R * 0.15, cy - R * 0.95)], outline=255, width=7)
    d.ellipse([cx - R * 0.45, cy - R * 0.2, cx - R * 0.25, cy], fill=255)
    d.ellipse([cx + R * 0.25, cy - R * 0.2, cx + R * 0.45, cy], fill=255)
    for s in (-1, 1):
        for k in (-0.15, 0.1):
            d.line([(cx + s * R * 0.3, cy + R * 0.35 + k * R), (cx + s * R * 1.4, cy + R * 0.2 + k * R * 2)], fill=255, width=4)
    d.arc([cx - R * 0.9, cy + R * 0.6, cx + R * 0.9, cy + R * 2.6], 200, 340, fill=255, width=7)
    font2 = ImageFont.truetype(FONT_BOLD, int(S * 0.06))
    d.text((cx, cy + R * 3.0), "MÈO CAM", fill=240, font=font2, anchor="mm")
    m = np.asarray(im, np.float32) / 255
    grain = fbm(S, 200, 2, rng)
    a = m * np.clip((grain - 0.2) * 1.8, 0, 1) * 0.85
    colr = np.zeros((S, S, 3), np.float32)
    yy = np.mgrid[0:S, 0:S][0]
    colr[...] = np.array([236, 232, 222])
    colr[yy < S * 0.3] = np.array([244, 200, 210])  # pink chalk for the top part
    _save_decal(name, np.dstack([colr, a * 255]))


def decal_poster(seed: int, name: str, lines: list[tuple[str, int, tuple]], bg, S: tuple = (512, 704)) -> None:
    """Weathered wall flyer (fictional text). lines: (text, size, rgb)."""
    rng = np.random.default_rng(seed)
    W, H = S
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    y = int(H * 0.08)
    for text, size, c in lines:
        f = ImageFont.truetype(FONT_BOLD if size > 40 else FONT_MED, size)
        for line in text.split("\n"):
            d.text((W / 2, y), line, fill=c, font=f, anchor="ma")
            y += int(size * 1.18)
        y += int(size * 0.3)
    arr = np.asarray(im, np.float32)
    # ageing: yellowing, sun fade, rain streaks, torn edges
    fade = fbm(W if W > H else H, 4, 3, rng)[:H, :W]
    arr = lerp(arr, np.array([214, 204, 176], np.float32), (0.25 + fade * 0.25)[..., None])
    streak = periodic_noise(max(W, H), 48, rng)[:H, :W]
    xs = np.mgrid[0:H, 0:W][1]
    streak = np.clip((np.sin(xs * 0.11 + streak * 9) - 0.6) * 2, 0, 1) * np.linspace(0.2, 0.6, H)[:, None]
    arr = lerp(arr, arr * 0.75, streak[..., None])
    tear = fbm(max(W, H), 16, 4, rng)[:H, :W]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx / W, 1 - xx / W), np.minimum(yy / H, 1 - yy / H))
    alpha = np.clip((edge * 40 - tear * 1.6 + 0.4), 0, 1)
    rip = np.clip((fbm(max(W, H), 6, 4, rng)[:H, :W] - 0.74) * 10, 0, 1)
    alpha *= 1 - rip
    _save_decal(name, np.dstack([arr, alpha * 255]))


def decal_manhole_ring(seed: int, name: str, S: int = 512) -> None:
    decal_stain(seed, name, (34, 30, 26), S, 0.55)


def decal_tire(seed: int, name: str, S: int = 512) -> None:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    a = np.zeros((S, S), np.float32)
    for cx in (S * 0.3, S * 0.7):
        band = np.clip(1 - np.abs(xx - cx - np.sin(yy / S * 3) * 20) / 30, 0, 1)
        a = np.maximum(a, band)
    tread = (np.sin(yy * 0.6) * 0.5 + 0.5) * 0.4 + 0.6
    a *= tread * (0.4 + fbm(S, 8, 3, rng) * 0.6) * np.clip(np.sin(yy / S * math.pi) * 2, 0, 1)
    rgb = np.zeros((S, S, 3), np.float32) + np.array([20, 20, 20])
    _save_decal(name, np.dstack([rgb, a * 255 * 0.5]))


def decal_ripples_normal(S: int = 512, seed: int = 111) -> None:
    """Tileable rain-ripple normal atlas: 4 frames? (single): concentric rings, used by water/ground shaders."""
    rng = np.random.default_rng(seed)
    h = np.zeros((S, S), np.float32)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    phase = np.zeros((S, S), np.float32)
    for k in range(60):
        cx, cy = rng.random() * S, rng.random() * S
        dx = (xx - cx + S / 2) % S - S / 2
        dy = (yy - cy + S / 2) % S - S / 2
        r = np.hypot(dx, dy)
        R = rng.uniform(10, 26)
        p = rng.random()
        mask = np.clip(1 - r / R, 0, 1)
        h += np.sin(r * 0.9) * mask * mask
        phase = np.maximum(phase, mask * 0 + p * (r < R))
    nrm = normal_from_height(h * 0.5 + 0.5, 3.0)
    # pack: RG = normal xy, B = per-drop phase (for animation), A = ring mask
    ring = np.clip(np.abs(h), 0, 1)
    out = np.dstack([nrm[..., 0], nrm[..., 1], (phase * 255).astype(np.uint8), (ring * 255).astype(np.uint8)])
    os.makedirs(GROUND, exist_ok=True)
    Image.fromarray(out, "RGBA").save(os.path.join(GROUND, "rain_ripples.png"), optimize=True)
    print("wrote rain_ripples")


def gen_water_normals(S: int = 1024, seed: int = 121) -> None:
    """Tileable small-wave normal map for the lake (sum of periodic directional waves + noise)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    h = np.zeros((S, S), np.float32)
    for k in range(24):
        kx, ky = int(rng.integers(-12, 13)), int(rng.integers(-12, 13))
        if kx == 0 and ky == 0:
            continue
        amp = 1.0 / math.hypot(kx, ky) ** 1.3
        h += amp * np.sin((kx * xx + ky * yy) * math.tau + rng.random() * math.tau)
    h += fbm(S, 16, 4, rng) * 0.6
    h = (h - h.min()) / (h.max() - h.min())
    Image.fromarray(normal_from_height(h, 6.0), "RGB").save(os.path.join(GROUND, "water_normal.png"), optimize=True)
    print("wrote water_normal")


def gen_noise_tex(S: int = 512, seed: int = 131) -> None:
    """RGBA tileable noise utility: R fbm-low, G fbm-mid, B cellular-ish, A fine — used by shaders
    (puddle masks, cloud breakup, macro variation)."""
    rng = np.random.default_rng(seed)
    r = fbm(S, 4, 5, rng)
    g = fbm(S, 16, 4, rng)
    b = periodic_noise(S, 64, rng)
    a = fbm(S, 64, 3, rng)
    out = np.dstack([(c * 255).astype(np.uint8) for c in (r, g, b, a)])
    Image.fromarray(out, "RGBA").save(os.path.join(GROUND, "noise_rgba.png"), optimize=True)
    print("wrote noise_rgba")


def gen_decals() -> None:
    decal_oil(201, "oil_stain_a")
    decal_oil(202, "oil_stain_b")
    decal_crack(211, "crack_a")
    decal_crack(212, "crack_b")
    decal_crack(213, "crack_c")
    decal_leaves(221, "leaves_a")
    decal_leaves(222, "leaves_b")
    decal_puddle(231, "puddle_a")
    decal_puddle(232, "puddle_b")
    decal_stain(241, "stain_damp", (40, 38, 34), strength=0.5)
    decal_stain(242, "stain_rust", (96, 50, 26), strength=0.55)
    decal_stain(243, "stain_food", (70, 52, 30), strength=0.5)
    decal_manhole_ring(244, "stain_drain")
    decal_tire(251, "tire_marks")
    decal_chalk(261, "chalk_hopscotch")
    decal_poster(271, "poster_rent", [("CHO THUÊ\nNHÀ", 84, (190, 24, 24)), ("Mặt tiền 4m\nngõ Hàng Mây", 44, (30, 30, 30)),
                                      ("LH: 09xx.xxx.271", 40, (30, 30, 30))], (236, 232, 220))
    decal_poster(272, "poster_lost_cat", [("TÌM MÈO\nLẠC", 84, (20, 20, 20)), ("Mèo mướp xám, đeo\nvòng đỏ có chuông", 38, (40, 40, 40)),
                                          ("Ai thấy xin báo\nbà Năm, số 12", 38, (40, 40, 40))], (246, 226, 120))
    decal_poster(273, "poster_festival", [("TRUNG THU", 74, (200, 40, 30)), ("Rước đèn ông sao\nĐình Hàng Mây", 44, (120, 60, 10)),
                                          ("Rằm tháng Tám · 19h", 40, (60, 40, 20))], (250, 214, 120))
    decal_poster(274, "poster_lessons", [("DẠY ĐÀN\nTRANH", 76, (20, 60, 120)), ("Học thử miễn phí\ncác tối thứ Ba", 40, (40, 40, 40)),
                                         ("Gác 2 · ngõ 7", 40, (40, 40, 40))], (232, 236, 240))
    gen_lane_paint()


def gen_bark(seed: int = 141, S: int = 1024) -> None:
    """1×2 m-ish tile tree bark (fissured, lichen) — V runs along the trunk."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32) / S
    warp = fbm(S, 8, 4, rng)
    ridges = np.abs(np.sin((xx * 9 + warp * 1.8) * math.pi))
    fiss = np.clip(1 - ridges * 3, 0, 1)
    plates = periodic_noise(S, 24, rng)
    cross_cr = np.clip((np.abs(np.sin((yy * 14 + plates * 3) * math.pi)) - 0.94) * 15, 0, 1) * (ridges > 0.4)
    fine = periodic_noise(S, 256, rng)
    h = ridges * 0.6 + fine * 0.15 - cross_cr * 0.3
    base = lerp(col((74, 64, 54)), col((118, 106, 92)), (ridges * 0.7 + fine * 0.3)[..., None])
    base = lerp(base, col((40, 34, 28)), fiss[..., None] * 0.9)
    lich = np.clip((fbm(S, 12, 4, rng) - 0.6) * 4, 0, 1) * (ridges > 0.5)
    base = lerp(base, col((128, 138, 104)), lich[..., None] * 0.6)
    moss = np.clip((fbm(S, 6, 3, rng) - 0.62) * 4, 0, 1)
    base = lerp(base, col((64, 78, 38)), moss[..., None] * 0.5)
    save_set("bark", base ** 2.2, h, 0.9 - lich * 0.1, 5.0)


def gen_leaf_cluster(seed: int = 151, S: int = 1024) -> None:
    """RGBA leaf-cluster cards (2×2 cells): 0 small tropical street-tree leaves, 1 ficus/banyan,
    2 sparse twig tips, 3 lotus pad (round, top view). Alpha-tested; normal map alongside."""
    rng = np.random.default_rng(seed)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hmap = Image.new("L", (S, S), 0)
    C = S // 2
    def leaf(d, hd, cx, cy, L, W, ang, colr, vein=True):
        pts = []
        for i in range(20):
            t = i / 20 * math.tau
            px = math.cos(t) * L / 2
            py = math.sin(t) * W / 2 * (1 - 0.25 * math.cos(t))
            pts.append((cx + px * math.cos(ang) - py * math.sin(ang), cy + px * math.sin(ang) + py * math.cos(ang)))
        d.polygon(pts, fill=colr)
        hd.polygon(pts, fill=int(140 + rng.random() * 110))
        if vein:
            x0, y0 = cx - math.cos(ang) * L / 2, cy - math.sin(ang) * L / 2
            x1, y1 = cx + math.cos(ang) * L / 2, cy + math.sin(ang) * L / 2
            d.line([(x0, y0), (x1, y1)], fill=(int(colr[0] * 1.25), int(colr[1] * 1.2), int(colr[2] * 1.1), 255), width=1)
            hd.line([(x0, y0), (x1, y1)], fill=90, width=1)
    for cell, (ox, oy) in enumerate([(0, 0), (C, 0), (0, C), (C, C)]):
        layer = Image.new("RGBA", (C, C), (0, 0, 0, 0))
        hl = Image.new("L", (C, C), 0)
        d = ImageDraw.Draw(layer)
        hd = ImageDraw.Draw(hl)
        if cell in (0, 1, 2):
            # twig skeleton
            twigs = []
            n_tw = 7 if cell != 2 else 4
            for k in range(n_tw):
                a = -math.pi / 2 + rng.normal(0, 0.7)
                x, y = C / 2 + rng.normal(0, 8), C * 0.98
                pts = [(x, y)]
                for j in range(8):
                    a += rng.normal(0, 0.18)
                    x += math.cos(a) * C * 0.06
                    y += math.sin(a) * C * 0.06
                    pts.append((x, y))
                twigs.append(pts)
                d.line(pts, fill=(70, 58, 44, 255), width=3)
            nl = {0: 520, 1: 380, 2: 70}[cell]
            for k in range(nl):
                tw = twigs[int(rng.integers(0, len(twigs)))]
                p = tw[int(rng.integers(2, len(tw)))]
                cx, cy = p[0] + rng.normal(0, C * 0.11), p[1] + rng.normal(0, C * 0.11)
                if not (20 < cx < C - 20 and 20 < cy < C - 20):
                    continue
                if cell == 1:
                    L, W = rng.uniform(34, 52), rng.uniform(16, 24)  # ficus: glossy oval
                    base = np.array([46, 86, 34]) if rng.random() < 0.8 else np.array([96, 120, 40])
                else:
                    L, W = rng.uniform(22, 34), rng.uniform(9, 13)
                    base = np.array([62, 104, 40]) if rng.random() < 0.75 else np.array([120, 130, 50])
                if rng.random() < 0.06:
                    base = np.array([170, 140, 60])
                shade = rng.uniform(0.7, 1.15)
                c = tuple(int(v) for v in np.clip(base * shade, 0, 255)) + (255,)
                leaf(d, hd, cx, cy, L, W, rng.random() * math.tau, c)
        else:
            # lotus pad (top view): round with notch, radial veins, slightly cupped
            cx, cy, R = C / 2, C / 2, C * 0.46
            notch = rng.random() * math.tau
            pts = []
            for i in range(96):
                t = i / 96 * math.tau
                dd = (t - notch + math.pi) % math.tau - math.pi
                r = R * (1 - 0.03 * math.sin(t * 7))
                if abs(dd) < 0.08:
                    r = R * 0.02
                pts.append((cx + math.cos(t) * r, cy + math.sin(t) * r))
            d.polygon(pts, fill=(58, 98, 52, 255))
            hd.polygon(pts, fill=150)
            for i in range(22):
                t = i / 22 * math.tau
                d.line([(cx, cy), (cx + math.cos(t) * R * 0.95, cy + math.sin(t) * R * 0.95)], fill=(86, 128, 70, 255), width=2)
                hd.line([(cx, cy), (cx + math.cos(t) * R * 0.95, cy + math.sin(t) * R * 0.95)], fill=190, width=2)
            d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(120, 140, 70, 255))
        out.paste(layer, (ox, oy), layer)
        hmap.paste(hl, (ox, oy))
    arr = np.asarray(out, np.float32)
    tex = periodic_noise(S, 128, rng)
    rgb = arr[..., :3] * (0.85 + tex[..., None] * 0.3)
    a = arr[..., 3]
    # bleed colour into transparent texels so mipmaps don't fringe black
    bled = np.asarray(Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)), np.float32)
    rgb = np.where(a[..., None] > 0, rgb, bled * 0.8)
    os.makedirs(GROUND, exist_ok=True)
    Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8), "RGBA").save(os.path.join(GROUND, "leaf_cluster_albedo.png"), optimize=True)
    h = np.asarray(hmap.filter(ImageFilter.GaussianBlur(2)), np.float32) / 255
    Image.fromarray(normal_from_height(h, 4.0), "RGB").save(os.path.join(GROUND, "leaf_cluster_normal.png"), optimize=True)
    print("wrote leaf_cluster")


SETS = {
    "asphalt": gen_asphalt, "pavers": gen_pavers, "granite": gen_granite, "concrete": gen_concrete_alley,
    "brick": gen_brick_courtyard, "grass": gen_grass, "embankment": gen_stone_embankment, "wood": gen_wood_deck,
    "lakebed": gen_lakebed, "ripples": decal_ripples_normal, "water": gen_water_normals, "noise": gen_noise_tex,
    "decals": gen_decals, "bark": gen_bark, "leaves": gen_leaf_cluster,
}


def contact_sheet() -> None:
    files = sorted(f for f in os.listdir(GROUND) if f.endswith("_albedo.jpg"))
    files += [os.path.join("..", "decals", f) for f in sorted(os.listdir(DECALS)) if f.endswith(".png") and "_normal" not in f]
    T = 256
    cols = 6
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * T, rows * (T + 18)), (60, 60, 60))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(os.path.join(GROUND, f))
        if im.mode == "RGBA":
            bgim = Image.new("RGBA", im.size, (110, 108, 104, 255))
            im = Image.alpha_composite(bgim, im).convert("RGB")
        im = im.convert("RGB").resize((T, T))
        x, y = (i % cols) * T, (i // cols) * (T + 18)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + T + 2), os.path.basename(f), fill=(255, 255, 255))
    out = os.path.join(ROOT, "qa", "out", "world", "ground_textures_sheet.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out, quality=88)
    print("sheet", out)


def main() -> None:
    only = None
    sheet = "--sheet" in sys.argv
    for i, a in enumerate(sys.argv):
        if a == "--only" and i + 1 < len(sys.argv):
            only = sys.argv[i + 1].split(",")
    for k, fn in SETS.items():
        if only is None or k in only:
            fn()
    if sheet:
        contact_sheet()


if __name__ == "__main__":
    main()
