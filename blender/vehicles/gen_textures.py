"""Paint the shared vehicle texture sets (numpy + Pillow, no Blender).

    python3 blender/vehicles/gen_textures.py

assets/textures/vehicles/:
  veh_paint_*      near-white albedo (dust speckle, faint water spots) x paint colour, orange-peel +
                   micro-scratch normal, ORM with swirl/scratch roughness variation (clearcoat in Godot)
  veh_metal_*      brushed / chrome micro-scratch normal + roughness
  veh_rubber_*     tyre: tread blocks across the crown, sidewall ribs + moulded text-free rings,
                   dusty sidewall (u = around the tyre, v = across the profile, 1024x512)
  veh_vinyl_*      seat vinyl grain, cracks, stitching welt
  veh_plastic_*    textured black plastic (fine grain)
  veh_rust_*       old steel: chipped paint over rust
  veh_wood_*       cargo-bed planks (ba gác)
  veh_fabric_*     cyclo hood canvas
  veh_decals_*     RGBA atlas: fictional plates, livery, stickers (see DECALS below)
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import nature_paint as P  # noqa: E402  (noise / normal helpers are generic)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "vehicles")
os.makedirs(OUT, exist_ok=True)
f32 = np.float32
FONT_B = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-700.ttf")
FONT_M = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-600.ttf")


def save_set(name, alb, hgt, rough, ao=None, metal=None, nstr=4.0, wrap=True):
    P.save_rgb(os.path.join(OUT, name + "_albedo.jpg"), alb)
    P.save_rgb(os.path.join(OUT, name + "_normal.png"), P.height_to_normal(hgt, nstr, wrap))
    ao = np.ones_like(rough) if ao is None else ao
    metal = np.zeros_like(rough) if metal is None else metal
    P.save_rgb(os.path.join(OUT, name + "_orm.jpg"), np.stack([ao, np.clip(rough, 0.03, 1), metal], -1))


def scratches(S, rng, n=400, maxlen=0.15, width=1):
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    for _ in range(n):
        x, y = rng.uniform(0, S), rng.uniform(0, S)
        a = rng.uniform(0, math.pi) if rng.random() < 0.5 else rng.normal(0.3, 0.2)
        L = rng.uniform(0.01, maxlen) * S
        pts = []
        for k in range(6):
            pts.append((x + math.cos(a) * L * k / 5 + rng.normal(0, 1.5), y + math.sin(a) * L * k / 5 + rng.normal(0, 1.5)))
        d.line(pts, fill=int(rng.uniform(80, 255)), width=width)
    return np.asarray(im, f32) / 255.0


def paint(S=1024):
    rng = np.random.default_rng(201)
    peel = P.fft_noise(S, S, rng, 1.0, lo=60, hi=260)
    swirl = scratches(S, rng, 900, 0.06)
    deep = scratches(S, rng, 60, 0.12, 2)
    dust = P.sstep(0.55, 0.8, P.fft_noise(S, S, rng, 1.2)) * P.fft_noise(S, S, rng, 0.3)
    spots = P.sstep(0.82, 0.86, P.fft_noise(S, S, rng, 0.5, lo=20))
    alb = np.ones((S, S, 3), f32) * 0.92
    alb = alb * (1 - 0.18 * dust[..., None]) + np.array([0.6, 0.55, 0.48], f32) * 0.18 * dust[..., None]
    alb = alb * (1 - 0.06 * spots[..., None])
    alb = alb * (1 - 0.35 * deep[..., None]) + np.array([0.75, 0.75, 0.75], f32) * 0.35 * deep[..., None]
    hgt = peel * 0.25 - swirl * 0.15 - deep * 0.6
    rough = 0.18 + 0.12 * swirl + 0.25 * dust + 0.15 * deep + 0.05 * spots
    save_set("veh_paint", alb, hgt, rough, nstr=2.5)


def metal(S=1024):
    rng = np.random.default_rng(202)
    brush = P.fft_noise(S, S, rng, 0.8, ax=40.0, ay=1.0)
    sc = scratches(S, rng, 700, 0.08)
    pit = P.sstep(0.8, 0.9, P.fft_noise(S, S, rng, 0.4))
    alb = np.ones((S, S, 3), f32) * (0.88 + 0.06 * brush[..., None]) * (1 - 0.3 * pit[..., None])
    hgt = brush * 0.3 - sc * 0.4 - pit * 0.3
    rough = 0.12 + 0.12 * brush + 0.2 * sc + 0.4 * pit
    save_set("veh_metal", alb, hgt, rough, metal=np.ones_like(rough), nstr=2.0)


def rubber():
    W, H = 1024, 512
    rng = np.random.default_rng(203)
    yy, xx = np.mgrid[0:H, 0:W].astype(f32)
    v = yy / H                       # across profile: 0 = inner edge (side A), 0.5 = crown centre, 1 = side B
    u = xx / W
    crown = P.sstep(0.28, 0.33, v) * (1 - P.sstep(0.67, 0.72, v))
    # directional tread: chevron blocks repeating 48x around the tyre
    ph = np.mod(u * 48 + np.abs(v - 0.5) * 3.0, 1.0)
    blocks = (ph > 0.18).astype(f32)
    centre_groove = np.exp(-((v - 0.5) / 0.012) ** 2)
    side_groove = np.exp(-((np.abs(v - 0.5) - 0.11) / 0.01) ** 2)
    tread = crown * (blocks * (1 - centre_groove) * (1 - side_groove))
    ribs = (1 - crown) * (0.5 + 0.5 * np.sin(v * 220)) * 0.15
    ring = np.exp(-((np.abs(v - 0.5) - 0.38) / 0.006) ** 2)        # moulded bead ring on the sidewall
    letters = (1 - crown) * P.sstep(0.6, 0.62, P.fft_noise(H, W, rng, 0.2, ax=0.2, ay=1.0)) * \
        (np.abs(np.abs(v - 0.5) - 0.3) < 0.03)
    fine = P.fft_noise(H, W, rng, 0.5)
    hgt = tread * 1.0 + ribs + ring * 0.4 + letters * 0.3 + fine * 0.05
    dust = (1 - crown) * P.sstep(0.4, 0.8, P.fft_noise(H, W, rng, 1.5)) * 0.8 + crown * 0.15 * (1 - tread)
    alb = np.ones((H, W, 3), f32) * 0.055 * (0.9 + 0.2 * fine[..., None])
    alb = alb * (1 - dust[..., None]) + np.array([0.3, 0.27, 0.23], f32) * dust[..., None] * 0.6 + alb * dust[..., None] * 0.4
    rough = 0.82 + 0.1 * dust - 0.12 * crown * tread
    P.save_rgb(os.path.join(OUT, "veh_rubber_albedo.jpg"), alb)
    P.save_rgb(os.path.join(OUT, "veh_rubber_normal.png"), P.height_to_normal(hgt, 5.0, True))
    P.save_rgb(os.path.join(OUT, "veh_rubber_orm.jpg"), np.stack([1 - 0.5 * (1 - tread) * crown, rough, 0 * rough], -1))


def vinyl(S=1024):
    rng = np.random.default_rng(204)
    grain = P.fft_noise(S, S, rng, 0.6, lo=80)
    cells = P.fft_noise(S, S, rng, 1.0, lo=30, hi=120)
    cracks = P.sstep(0.47, 0.5, 0.5 - np.abs(P.fft_noise(S, S, rng, 1.6, lo=6) - 0.5)) * \
        P.sstep(0.6, 0.75, P.fft_noise(S, S, rng, 1.8))
    yy = np.mgrid[0:S, 0:S][0].astype(f32)
    welt = np.exp(-((np.mod(yy, S / 4) - S / 8) / 4.0) ** 2)
    stitch = welt * (np.mod(np.mgrid[0:S, 0:S][1], 14) < 7) * 0
    alb = np.ones((S, S, 3), f32) * (0.85 + 0.15 * cells[..., None])
    alb = alb * (1 - 0.35 * cracks[..., None]) + np.array([0.6, 0.55, 0.5], f32) * 0.35 * cracks[..., None]
    hgt = grain * 0.4 + cells * 0.3 - cracks * 0.6 + welt * 0.8 + stitch
    rough = 0.45 + 0.15 * grain + 0.25 * cracks
    save_set("veh_vinyl", alb, hgt, rough, nstr=3.0)


def plastic(S=512):
    rng = np.random.default_rng(205)
    g = P.fft_noise(S, S, rng, 0.4, lo=60)
    sc = scratches(S, rng, 150, 0.1)
    alb = np.ones((S, S, 3), f32) * (0.9 + 0.1 * g[..., None]) * (1 + 0.6 * sc[..., None])
    save_set("veh_plastic", alb, g * 0.5 - sc * 0.3, 0.55 + 0.15 * g - 0.15 * sc, nstr=2.5)


def rust(S=1024):
    rng = np.random.default_rng(206)
    n = P.fft_noise(S, S, rng, 1.8)
    chip = P.sstep(0.62, 0.66, n * 0.8 + P.fft_noise(S, S, rng, 0.8) * 0.2)
    rustc = P.fft_noise(S, S, rng, 1.2)
    streak = P.fft_noise(S, S, rng, 1.6, ax=1.0, ay=0.15)
    paint = np.array([0.9, 0.9, 0.9], f32)
    rust_col = np.array([0.36, 0.17, 0.07], f32) * (0.7 + 0.6 * rustc[..., None])
    alb = paint * (1 - chip[..., None]) + rust_col * chip[..., None]
    st = P.sstep(0.55, 0.8, streak) * 0.4
    alb = alb * (1 - st[..., None]) + np.array([0.45, 0.25, 0.12], f32) * st[..., None]
    hgt = (1 - chip) * 0.4 + rustc * chip * 0.3
    rough = 0.35 * (1 - chip) + 0.9 * chip
    save_set("veh_rust", alb, hgt, rough, nstr=4.0)


def wood(S=1024):
    rng = np.random.default_rng(207)
    xx = np.mgrid[0:S, 0:S][1].astype(f32) / S
    plank = np.floor(xx * 6)
    seam = np.exp(-((np.mod(xx * 6, 1.0) - 0.0) / 0.01) ** 2) + np.exp(-((np.mod(xx * 6, 1.0) - 1.0) / 0.01) ** 2)
    grain = P.fft_noise(S, S, rng, 1.2, ax=8.0, ay=1.0)
    tone = (np.sin(plank * 12.9898) * 43758.5453) % 1.0
    worn = P.fft_noise(S, S, rng, 1.8)
    alb = np.array([0.42, 0.3, 0.18], f32) * (0.75 + 0.35 * tone[..., None]) * (0.8 + 0.4 * grain[..., None])
    alb = alb * (1 - 0.35 * P.sstep(0.55, 0.8, worn)[..., None]) + np.array([0.3, 0.28, 0.25], f32) * \
        0.35 * P.sstep(0.55, 0.8, worn)[..., None]
    alb *= (1 - 0.6 * seam[..., None])
    hgt = grain * 0.4 - seam * 1.0
    save_set("veh_wood", alb, hgt, 0.75 + 0.15 * grain, nstr=5.0)


def fabric(S=512):
    rng = np.random.default_rng(208)
    yy, xx = np.mgrid[0:S, 0:S].astype(f32)
    weave = 0.5 + 0.25 * np.sin(xx * math.pi / 2) * np.sign(np.sin(yy * math.pi / 8)) + 0.25 * np.sin(yy * math.pi / 2)
    fade = P.fft_noise(S, S, rng, 1.8)
    alb = np.ones((S, S, 3), f32) * (0.8 + 0.2 * fade[..., None]) * (0.9 + 0.1 * weave[..., None])
    save_set("veh_fabric", alb, weave * 0.5, 0.85 + 0.1 * fade, nstr=3.0)


# ---------------------------------------------------------------------------
# decal atlas (1024x1024 RGBA). Rects in px (x, y, w, h) from the top-left; vehicles_lib reads DECALS.
# ---------------------------------------------------------------------------
from vehicles_decals import DECALS  # noqa: E402


def decals():
    S = 1024
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fb = lambda s: ImageFont.truetype(FONT_B, s)  # noqa: E731
    fm = lambda s: ImageFont.truetype(FONT_M, s)  # noqa: E731

    def rrect(r, fill, outline=None, w=0, rad=10):
        x, y, ww, hh = r
        d.rounded_rectangle((x + 3, y + 3, x + ww - 4, y + hh - 4), radius=rad, fill=fill, outline=outline, width=w)

    def center_text(r, txt, font, fill, dy=0):
        x, y, ww, hh = r
        bb = d.textbbox((0, 0), txt, font=font)
        d.text((x + (ww - (bb[2] - bb[0])) / 2 - bb[0], y + (hh - (bb[3] - bb[1])) / 2 - bb[1] + dy), txt, font=font,
               fill=fill)

    moto = [("29-B1", "386.52"), ("29-H7", "042.18"), ("30-K3", "917.04"), ("29-X2", "655.31")]
    for i, (a, b) in enumerate(moto):
        r = DECALS[f"plate_moto_{'abcd'[i]}"]
        rrect(r, (236, 236, 230, 255), (25, 25, 25, 255), 5, 12)
        x, y, w, h = r
        center_text((x, y + 10, w, h / 2), a, fb(64), (20, 20, 22, 255))
        center_text((x, y + h / 2 - 8, w, h / 2), b, fb(64), (20, 20, 22, 255))
    for k, txt in (("plate_car_a", "30G-517.86"), ("plate_car_b", "29C-204.73")):
        r = DECALS[k]
        rrect(r, (238, 238, 232, 255), (25, 25, 25, 255), 5, 8)
        center_text(r, txt, fb(76), (20, 20, 22, 255))
    # taxi livery: green band with white text (fictional company of the old quarter)
    x, y, w, h = DECALS["taxi_door"]
    d.rectangle((x, y + 60, x + w, y + 150), fill=(18, 120, 72, 255))
    d.rectangle((x, y + 150, x + w, y + 162), fill=(240, 196, 40, 255))
    center_text((x, y + 60, w, 90), "TAXI HÀNG MÂY", fb(70), (250, 250, 245, 255))
    center_text((x, y, w, 60), "1900 6868 · Phố Cũ", fm(36), (18, 100, 60, 255))
    x, y, w, h = DECALS["taxi_roof"]
    rrect(DECALS["taxi_roof"], (245, 245, 238, 255), (18, 120, 72, 255), 10, 18)
    center_text((x, y, w, 100), "TAXI", fb(92), (18, 120, 72, 255), 10)
    center_text((x, y + 100, w, 50), "HÀNG MÂY", fm(34), (40, 40, 40, 255))
    x, y, w, h = DECALS["van_side"]
    d.polygon([(x, y + 150), (x + w, y + 70), (x + w, y + 110), (x, y + 190)], fill=(232, 120, 20, 255))
    center_text((x, y, w, 90), "GIAO NHANH PHỐ CŨ", fb(80), (30, 60, 120, 255))
    center_text((x, y + 85, w, 40), "Hàng hóa · Chuyển nhà · 0912 345 678", fm(34), (40, 40, 40, 255))
    for k, txt, col in (("brand_saola", "SAOLA", (200, 200, 205, 255)), ("brand_soc", "SÓC 110", (210, 40, 40, 255)),
                        ("brand_hac", "HẠC 125", (240, 200, 60, 255))):
        center_text(DECALS[k], txt, fb(50), col)
    x, y, w, h = DECALS["sticker_a"]
    d.ellipse((x + 8, y + 4, x + 76, y + 72), fill=(30, 90, 170, 255))
    center_text((x + 8, y + 4, 68, 68), "P", fb(48), (255, 255, 255, 255))
    d.text((x + 82, y + 20), "Gửi\nxe", font=fm(18), fill=(30, 30, 30, 255))
    rrect(DECALS["sticker_b"], (250, 220, 40, 255), None, 0, 8)
    x, y, w, h = DECALS["sticker_b"]
    center_text((x, y, w, h), "SỬA XE\nCHÚ SÁU", fb(18), (30, 30, 30, 255))
    x, y, w, h = DECALS["stripe"]
    d.rectangle((x, y + 20, x + w, y + 28), fill=(240, 240, 240, 255))
    d.rectangle((x, y + 34, x + w, y + 38), fill=(200, 40, 40, 255))
    x, y, w, h = DECALS["grille_mesh"]
    for i in range(0, w, 16):
        for j in range(0, h, 16):
            d.polygon([(x + i + 8, y + j), (x + i + 16, y + j + 8), (x + i + 8, y + j + 16), (x + i, y + j + 8)],
                      fill=(20, 20, 22, 255), outline=(60, 60, 64, 255))
    # light wear on everything printed
    arr = np.asarray(im, f32) / 255.0
    rng = np.random.default_rng(209)
    wear = P.sstep(0.62, 0.7, P.fft_noise(S, S, rng, 0.8))
    arr[..., :3] = arr[..., :3] * (1 - 0.25 * wear[..., None]) + 0.25 * wear[..., None] * 0.7
    a = arr[..., 3]
    # bleed colour into transparent texels
    rgb = arr[..., :3]
    num, den = rgb * a[..., None], a.copy()
    for r in (2, 4, 8, 16):
        num, den = P.blur(num, r), P.blur(den, r)
        fill = (den > 1e-4) & (a < 0.01)
        rgb[fill] = num[fill] / den[fill][..., None]
    P.save_rgba(os.path.join(OUT, "veh_decals_albedo.png"), rgb, a)


if __name__ == "__main__":
    for fn in (paint, metal, rubber, vinyl, plastic, rust, wood, fabric, decals):
        fn()
        print("done", fn.__name__)
