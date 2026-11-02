#!/usr/bin/env python3
"""Landmark atlas: carved door panels, plaques, couplet boards, signs (market gate, Bông's café,
Bà Tư's tea stall), menus, shrine panels, snack-jar contents, fish on ice, produce piles, nest twigs,
café interior seen through glass.

Run:  python3 blender/landmarks/gen_atlas.py [--sheet]
Out:  assets/textures/landmarks/landmarks_atlas.png        (RGBA albedo, alpha = cut-out)
      assets/textures/landmarks/landmarks_atlas_normal.png (OpenGL normal from the carved height)
      assets/textures/landmarks/atlas.json                 (cell rects in UV space, v up)
All lettering is fictional; ornament motifs (cloud scrolls, curling leaves, lotus) are drawn here.
The "glyph seals" on couplets are procedural pseudo-characters (no real text).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "..", "city"))
import city_texlib as T  # noqa: E402
import gen_atlases as GA  # noqa: E402  (city-houses helpers: fonts, condensed text, weathering)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "landmarks")
S = 2048
F_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
F_PLAY = os.path.join(ROOT, "assets", "fonts", "PlayfairDisplay-700.ttf")
F_PLAY_I = os.path.join(ROOT, "assets", "fonts", "PlayfairDisplay-400i.ttf")
F_LORA_I = os.path.join(ROOT, "assets", "fonts", "Lora-400i.ttf")
F_BVP = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-700.ttf")
F_BVP5 = os.path.join(ROOT, "assets", "fonts", "BeVietnamPro-500.ttf")
F_HAND = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

CELLS: dict[str, tuple[int, int, int, int]] = {
    # temple
    "door_a": (0, 0, 384, 1024),
    "door_b": (384, 0, 384, 1024),
    "couplet_l": (768, 0, 128, 1024),
    "couplet_r": (896, 0, 128, 1024),
    "plaque_dinh": (1024, 0, 1024, 256),
    "frieze": (1024, 256, 1024, 128),
    # signs
    "sign_cho": (1024, 384, 1024, 192),
    "sign_cafe": (1024, 576, 512, 192),
    "sign_tea": (1536, 576, 512, 192),
    "menu_tea": (1024, 768, 256, 256),
    "menu_cafe": (1280, 768, 256, 256),
    "shrine_back": (1536, 768, 256, 256),
    "calendar": (1792, 768, 256, 256),
    # snack jars (8 x 128)
    "snack_peanut": (0, 1024, 128, 128),
    "snack_seeds": (128, 1024, 128, 128),
    "snack_plum": (256, 1024, 128, 128),
    "snack_biscuit": (384, 1024, 128, 128),
    "snack_tea": (512, 1024, 128, 128),
    "snack_ginger": (640, 1024, 128, 128),
    "snack_candy": (768, 1024, 128, 128),
    "snack_rice": (896, 1024, 128, 128),
    # market food
    "fish_ice": (0, 1152, 512, 256),
    "shrimp": (512, 1152, 256, 256),
    "ice": (768, 1152, 256, 256),
    "veg_greens": (0, 1408, 256, 256),
    "veg_tomato": (256, 1408, 256, 256),
    "veg_chili": (512, 1408, 256, 256),
    "fruit_orange": (768, 1408, 256, 256),
    "fruit_dragon": (0, 1664, 256, 256),
    "fruit_banana": (256, 1664, 256, 256),
    "veg_herbs": (512, 1664, 256, 256),
    "dried_goods": (768, 1664, 256, 256),
    "price_cards": (1024, 1024, 512, 256),
    "sign_fish": (1024, 1280, 512, 128),
    "nest": (1536, 1024, 512, 512),
    "cafe_interior": (1024, 1536, 512, 512),
    "lantern_paper": (1536, 1536, 256, 256),
    "tea_label": (1792, 1536, 256, 256),
    "fabric_dark": (1536, 1792, 512, 256),
    "fabric_bundle": (0, 1920, 512, 128),
    "poster_lost_cat": (512, 1920, 256, 128),
    "cushion": (768, 1920, 256, 128),
}

rng = np.random.default_rng(4242)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def noise_img(w, h, seed, fmin=2, fmax=None, beta=2.0, aniso=(1, 1)):
    n = 1 << int(math.ceil(math.log2(max(w, h))))
    return T.spectral(n, seed, beta, fmin, fmax, aniso)[:h, :w]


# ---------------------------------------------------------------------------
# Carved relief helpers (height field 0..1 in a float image + colour)
# ---------------------------------------------------------------------------
def scroll_curve(cx, cy, r0, turns, ang0, flip, n=60):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        a = ang0 + flip * t * turns * 2 * math.pi
        r = r0 * (1 - 0.82 * t)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def cloud_motif(d: ImageDraw.ImageDraw, cx, cy, s, flip=1, width=None):
    """Stylised auspicious-cloud: a chain of three spiral curls with a trailing tail (original)."""
    w = width or max(2, int(s * 0.09))
    for k, (dx, dy, r, tn) in enumerate(((0, 0, 0.45, 1.25), (0.62, -0.18, 0.32, 1.1), (-0.55, -0.12, 0.3, 1.1))):
        pts = scroll_curve(cx + dx * s * flip, cy + dy * s, r * s, tn, math.pi * (0.5 + k * 0.3), flip if k != 2 else -flip)
        d.line(pts, fill=255, width=w, joint="curve")
    tail = [(cx - 0.2 * s * flip, cy + 0.45 * s), (cx + 0.3 * s * flip, cy + 0.55 * s), (cx + 0.9 * s * flip, cy + 0.4 * s),
            (cx + 1.3 * s * flip, cy + 0.55 * s)]
    d.line(tail, fill=255, width=w, joint="curve")


def leaf_scroll(d, x0, y0, x1, y1, seed, width=6):
    """Running leaf scroll (dây lá) inside a rectangle."""
    r = np.random.default_rng(seed)
    n = 5
    pts = []
    for i in range(80):
        t = i / 79
        x = x0 + (x1 - x0) * t
        y = (y0 + y1) / 2 + math.sin(t * n * math.pi) * (y1 - y0) * 0.28
        pts.append((x, y))
    d.line(pts, fill=255, width=width, joint="curve")
    for k in range(n):
        t = (k + 0.5) / n
        x = x0 + (x1 - x0) * t
        y = (y0 + y1) / 2 + math.sin(t * n * math.pi) * (y1 - y0) * 0.28
        up = 1 if k % 2 == 0 else -1
        s = (y1 - y0) * 0.33
        sc = scroll_curve(x, y - up * s * 0.6, s * 0.55, 1.1, math.pi / 2 * up, up)
        d.line(sc, fill=255, width=max(2, width - 1), joint="curve")
        # leaves: lens shapes
        for j in range(3):
            a = r.uniform(0, math.pi * 2)
            lx, ly = x + math.cos(a) * s * 0.8, y + math.sin(a) * s * 0.5
            L = s * r.uniform(0.35, 0.55)
            pts2 = [(lx + math.cos(a + math.pi / 2) * L * 0.25 * math.sin(u * math.pi) + math.cos(a) * L * u,
                     ly + math.sin(a + math.pi / 2) * L * 0.25 * math.sin(u * math.pi) + math.sin(a) * L * u)
                    for u in np.linspace(0, 1, 10)]
            pts3 = [(lx - math.cos(a + math.pi / 2) * L * 0.25 * math.sin(u * math.pi) + math.cos(a) * L * u,
                     ly - math.sin(a + math.pi / 2) * L * 0.25 * math.sin(u * math.pi) + math.sin(a) * L * u)
                    for u in np.linspace(1, 0, 10)]
            d.polygon(pts2 + pts3, fill=255)


def lotus(d, cx, cy, s):
    for k in range(7):
        a = math.pi + (k / 6) * math.pi
        L = s * (0.9 if k in (2, 3, 4) else 0.7)
        tip = (cx + math.cos(a) * L, cy + math.sin(a) * L)
        ang = a + math.pi / 2
        p = [(cx + math.cos(ang) * s * 0.16, cy + math.sin(ang) * s * 0.16), tip,
             (cx - math.cos(ang) * s * 0.16, cy - math.sin(ang) * s * 0.16)]
        d.polygon(p, fill=200)
        d.line(p + [p[0]], fill=255, width=max(2, int(s * 0.05)))
    d.ellipse([cx - s * 0.5, cy - s * 0.08, cx + s * 0.5, cy + s * 0.14], fill=255)


def glyph(d, x, y, s, seed, fill=255):
    """Procedural pseudo-character: 4-9 strokes on a 4x4 lattice inside a square (decorative only)."""
    r = np.random.default_rng(seed)
    w = max(2, int(s * 0.09))
    g = [(x + s * (0.12 + 0.76 * i / 3), y + s * (0.12 + 0.76 * j / 3)) for j in range(4) for i in range(4)]
    for _ in range(r.integers(5, 10)):
        a = r.integers(0, 16)
        kind = r.integers(0, 4)
        ax, ay = g[a]
        if kind == 0 and a % 4 < 3:      # horizontal
            b = g[a + r.integers(1, 4 - a % 4)]
            d.line([(ax, ay), b], fill=fill, width=w)
        elif kind == 1 and a < 12:        # vertical
            b = g[a + 4 * r.integers(1, 4 - a // 4)]
            d.line([(ax, ay), b], fill=fill, width=w)
        elif kind == 2:                   # sweep
            d.line([(ax, ay), (ax - s * 0.18, ay + s * 0.22)], fill=fill, width=w)
        else:                             # dot / hook
            d.line([(ax, ay), (ax + s * 0.08, ay + s * 0.1), (ax + s * 0.14, ay + s * 0.06)], fill=fill, width=w)


def relief(cw, ch, draw_fn, blur_px=2.0):
    """Draw a mask (L) with draw_fn(d), return height 0..1 (rounded profile)."""
    m = Image.new("L", (cw, ch), 0)
    draw_fn(ImageDraw.Draw(m))
    a = np.asarray(m, np.float32) / 255.0
    b = np.asarray(m.filter(ImageFilter.GaussianBlur(blur_px)), np.float32) / 255.0
    return np.clip(a * 0.55 + b * 0.6, 0, 1), a


class Atlas:
    def __init__(self):
        self.img = Image.new("RGBA", (S, S), (128, 128, 128, 255))
        self.h = np.zeros((S, S), np.float32)

    def put(self, name, im: Image.Image, h=None):
        x, y, w, hh = CELLS[name]
        im = im.convert("RGBA").resize((w, hh), Image.LANCZOS) if im.size != (w, hh) else im.convert("RGBA")
        self.img.paste(im, (x, y))
        if h is not None:
            self.h[y:y + hh, x:x + w] = h

    def save(self):
        os.makedirs(OUT, exist_ok=True)
        self.img.save(os.path.join(OUT, "landmarks_atlas.png"), optimize=True)
        # normal map from height (px units scaled): carved depth ~ 8 mm per unit over a 0.6 m panel
        h = self.h * 0.010
        px = 0.6 / 384
        dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * px)
        dy = -(np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * px)
        nz = np.ones_like(dx)
        L = np.sqrt(dx * dx + dy * dy + 1)
        nrm = np.stack([-dx / L, -dy / L, nz / L], -1) * 0.5 + 0.5
        Image.fromarray((nrm * 255 + 0.5).astype(np.uint8), "RGB").save(
            os.path.join(OUT, "landmarks_atlas_normal.png"), optimize=True)
        cells = {k: [x / S, 1 - (y + h_) / S, (x + w) / S, 1 - y / S] for k, (x, y, w, h_) in CELLS.items()}
        with open(os.path.join(OUT, "atlas.json"), "w") as f:
            json.dump({"file": "landmarks_atlas.png", "normal": "landmarks_atlas_normal.png", "size": S,
                       "cells": cells}, f, indent=1)


def colour_relief(h, base, high, low_dirt=0.5, seed=0, gold=None, gold_mask=None):
    """Colour a carved panel: recess = dark dusty, raised = lacquer/gilt with rubbed highlights."""
    hh, ww = h.shape
    nz = noise_img(ww, hh, seed, 2, 120)
    b = np.array(rgb(base), np.float32) / 255
    hi = np.array(rgb(high), np.float32) / 255
    col = b[None, None] * (0.85 + 0.06 * nz[..., None])
    col = col + (hi - b)[None, None] * np.clip(h, 0, 1)[..., None]
    if gold is not None and gold_mask is not None:
        g = np.array(rgb(gold), np.float32) / 255
        rub = T.smoothstep(0.6, 2.2, noise_img(ww, hh, seed + 3, 3, 150))
        gm = gold_mask * (1 - rub * 0.7)
        col = col * (1 - gm[..., None]) + g[None, None] * (0.8 + 0.3 * h[..., None]) * gm[..., None]
    # dust in recesses
    blurred = T.blur(h, 3.0)
    cav = np.clip((blurred - h) * 4, 0, 1)
    col = col * (1 - cav[..., None] * 0.45) * (1 - low_dirt * 0.25 * (1 - h[..., None]))
    col = np.clip(col, 0.02, 0.95)
    return Image.fromarray((col * 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------
def door_panel(variant: int) -> tuple[Image.Image, np.ndarray]:
    w, h = 384, 1024

    def draw(d):
        # frame + 4 fields: top lattice, upper medallion, waist band, lower panel
        d.rectangle([0, 0, w - 1, h - 1], outline=255, width=16)
        fields = [(24, 24, w - 24, 300), (24, 316, w - 24, 640), (24, 656, w - 24, 720), (24, 736, w - 24, h - 24)]
        for f in fields:
            d.rectangle(f, outline=230, width=8)
        # lattice (song tiện): vertical turned bars
        for i in range(9):
            x = 40 + i * (w - 80) / 8
            d.line([(x, 34), (x, 290)], fill=200, width=10)
        for y in (100, 200):
            d.line([(34, y), (w - 34, y)], fill=180, width=6)
        # medallion
        cx, cy = w / 2, 478
        d.ellipse([cx - 120, cy - 130, cx + 120, cy + 130], outline=255, width=10)
        if variant == 0:
            cloud_motif(d, cx - 20, cy - 10, 70, 1, 12)
            cloud_motif(d, cx + 10, cy + 60, 45, -1, 9)
        else:
            lotus(d, cx, cy + 30, 95)
            d.line([(cx, cy + 40), (cx, cy + 115)], fill=230, width=10)
        for (x, y) in ((50, 340), (w - 50, 340), (50, 615), (w - 50, 615)):
            d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=255)
        leaf_scroll(d, 34, 662, w - 34, 714, 7 + variant, 6)
        # lower panel: big leaf scroll + vase/cloud
        leaf_scroll(d, 40, 760, w - 40, 860, 11 + variant, 8)
        cloud_motif(d, w / 2 - 30, 920, 55, 1 if variant == 0 else -1, 10)
    hgt, mask = relief(w, h, draw, 2.2)
    gold_mask = T.smoothstep(0.55, 0.9, hgt)
    img = colour_relief(hgt, "#5a120d", "#8f2316", 0.6, 31 + variant, "#b58a3a", gold_mask)
    return img, hgt


def couplet(seed, dark=True) -> tuple[Image.Image, np.ndarray]:
    w, h = 128, 1024
    bg = Image.new("RGB", (w, h), rgb("#1d1410" if dark else "#7a1a12"))
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rectangle([4, 4, w - 5, h - 5], outline=200, width=5)
    for k in range(7):
        glyph(d, 20, 40 + k * 136, 88, seed + k)
    a = np.asarray(m.filter(ImageFilter.GaussianBlur(1.0)), np.float32) / 255
    gold = np.array(rgb("#c49a45"), np.float32) / 255
    base = np.asarray(bg, np.float32) / 255
    nz = noise_img(w, h, seed, 2, 80)
    base = base * (0.9 + 0.08 * nz[..., None])
    rub = T.smoothstep(0.8, 2.4, noise_img(w, h, seed + 1, 3, 100))
    col = base * (1 - a[..., None]) + gold * (0.85 + 0.15 * nz[..., None]) * a[..., None] * (1 - rub[..., None] * 0.5)
    return Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), a * 0.6


def plaque() -> tuple[Image.Image, np.ndarray]:
    w, h = 1024, 256
    img = Image.new("RGBA", (w, h), rgb("#1f1611") + (255,))
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rectangle([6, 6, w - 7, h - 7], outline=255, width=14)
    d.rectangle([30, 30, w - 31, h - 31], outline=180, width=4)
    for x in (70, w - 70):
        cloud_motif(d, x, h / 2 - 10, 34, 1 if x < w / 2 else -1, 6)
    tl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    GA.draw_text_condensed(tl, (w / 2, h / 2 + 4), "ĐÌNH HÀNG MÂY", F_SERIF, 760, 120, (255, 255, 255, 255))
    ta = np.asarray(tl, np.float32)[..., 3] / 255
    a = np.maximum(np.asarray(m.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255, ta)
    nz = noise_img(w, h, 77, 2, 100)
    base = np.array(rgb("#1f1611"), np.float32) / 255 * (0.85 + 0.12 * nz[..., None])
    gold = np.array(rgb("#c9a04a"), np.float32) / 255
    rub = T.smoothstep(0.8, 2.4, noise_img(w, h, 78, 3, 100))
    col = base * (1 - a[..., None]) + gold * a[..., None] * (0.85 + 0.2 * nz[..., None]) * (1 - 0.4 * rub[..., None])
    return Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)), a * 0.7


def frieze() -> tuple[Image.Image, np.ndarray]:
    w, h = 1024, 128

    def draw(d):
        d.line([(0, 8), (w, 8)], fill=255, width=8)
        d.line([(0, h - 8), (w, h - 8)], fill=255, width=8)
        for k in range(6):
            cloud_motif(d, 80 + k * 172, 58, 34, 1 if k % 2 == 0 else -1, 7)
    hgt, _ = relief(w, h, draw, 1.8)
    gold_mask = T.smoothstep(0.5, 0.9, hgt)
    return colour_relief(hgt, "#5c130d", "#8a2215", 0.5, 91, "#b88c3c", gold_mask), hgt


def sign_cho() -> Image.Image:
    w, h = 1024, 192
    im = Image.new("RGBA", (w, h), rgb("#e9d9a8") + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=rgb("#8a1c14"), width=14)
    d.rectangle([22, 22, w - 23, h - 23], outline=rgb("#8a1c14"), width=3)
    GA.draw_text_condensed(im, (w / 2, h / 2 - 8), "CHỢ HÀNG MÂY", F_BVP, 860, 110, rgb("#a8231a") + (255,),
                           shadow=(90, 40, 20, 120))
    GA.draw_text_condensed(im, (w / 2, h - 34), "· CHỢ DÂN SINH · MỞ CỬA 5H - 19H ·", F_BVP5, 520, 24,
                           rgb("#5a3a1a") + (255,))
    return GA.weather_rgba(im, 501, 0.9, rust_holes=[(40, 30), (w - 40, 30)])


def sign_cafe() -> Image.Image:
    w, h = 512, 192
    im = Image.new("RGBA", (w, h), rgb("#22382d") + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([6, 6, w - 7, h - 7], outline=rgb("#c9b07a"), width=3)
    GA.draw_text_condensed(im, (w / 2 - 40, h / 2 - 6), "Bông", F_PLAY_I, 260, 120, rgb("#f1e6cc") + (255,))
    GA.draw_text_condensed(im, (w / 2 + 150, h / 2 + 18), "café", F_PLAY, 110, 52, rgb("#c9b07a") + (255,))
    GA.draw_text_condensed(im, (w / 2, h - 22), "EST. 2016  ·  SỐ 3 PHỐ HÀNG MÂY", F_BVP5, 300, 16,
                           rgb("#c9b07a") + (255,))
    # small cat silhouette (stylised, original): sitting cat
    cx, cy = 60, 70
    d.ellipse([cx - 16, cy + 6, cx + 16, cy + 50], fill=rgb("#f1e6cc"))
    d.ellipse([cx - 12, cy - 16, cx + 12, cy + 10], fill=rgb("#f1e6cc"))
    d.polygon([(cx - 11, cy - 8), (cx - 9, cy - 26), (cx - 2, cy - 14)], fill=rgb("#f1e6cc"))
    d.polygon([(cx + 11, cy - 8), (cx + 9, cy - 26), (cx + 2, cy - 14)], fill=rgb("#f1e6cc"))
    d.line([(cx + 14, cy + 44), (cx + 30, cy + 40), (cx + 34, cy + 24)], fill=rgb("#f1e6cc"), width=5)
    return GA.weather_rgba(im, 502, 0.25)


def sign_tea() -> Image.Image:
    w, h = 512, 192
    im = Image.new("RGBA", (w, h), rgb("#f2e6c4") + (255,))
    d = ImageDraw.Draw(im)
    # hand-painted on a board: brush-stroke uneven letters
    GA.draw_text_condensed(im, (w / 2, 62), "TRÀ ĐÁ · TRÀ NÓNG", F_HAND, 470, 70, rgb("#1f5a34") + (255,))
    GA.draw_text_condensed(im, (w / 2, 140), "QUÁN BÀ TƯ", F_BVP, 380, 64, rgb("#b0261b") + (255,))
    d.line([(40, 104), (w - 40, 104)], fill=rgb("#1f5a34"), width=3)
    return GA.weather_rgba(im, 503, 1.1)


def handwritten_board(w, h, lines, bg, fg, seed, chalk=False, title=None):
    im = Image.new("RGBA", (w, h), rgb(bg) + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([3, 3, w - 4, h - 4], outline=rgb("#6b4a2a"), width=8)
    y = 18
    if title:
        GA.draw_text_condensed(im, (w / 2, y + 14), title, F_PLAY if chalk else F_BVP, w - 40, 30, rgb(fg) + (255,))
        y += 40
    lh = (h - y - 12) / max(len(lines), 1)
    for i, (a, b) in enumerate(lines):
        GA.draw_text_condensed(im, (w * 0.38, y + lh * (i + 0.5)), a, F_HAND if not chalk else F_LORA_I, w * 0.62,
                               lh * 0.62, rgb(fg) + (255,))
        GA.draw_text_condensed(im, (w * 0.84, y + lh * (i + 0.5)), b, F_HAND, w * 0.26, lh * 0.6, rgb(fg) + (255,))
    if chalk:
        a = np.asarray(im, np.float32)
        smear = noise_img(w, h, seed, 4, 100)[..., None]
        a[..., :3] = np.clip(a[..., :3] * (1 + smear * 0.05) + 6, 0, 255)
        im = Image.fromarray(a.astype(np.uint8), "RGBA")
    return GA.weather_rgba(im, seed, 0.6)


def shrine_back() -> Image.Image:
    w, h = 256, 256
    im = Image.new("RGBA", (w, h), rgb("#8d1c12") + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([8, 8, w - 9, h - 9], outline=rgb("#d0a64e"), width=6)
    d.ellipse([w / 2 - 70, h / 2 - 70, w / 2 + 70, h / 2 + 70], outline=rgb("#d0a64e"), width=5)
    m = Image.new("L", (w, h), 0)
    glyph(ImageDraw.Draw(m), w / 2 - 50, h / 2 - 50, 100, 9001)
    gold = Image.new("RGBA", (w, h), rgb("#d6ad55") + (255,))
    im.paste(gold, (0, 0), m)
    for x in (30, w - 30):
        for y in (30, h - 30):
            d.ellipse([x - 8, y - 8, x + 8, y + 8], fill=rgb("#d0a64e"))
    return GA.weather_rgba(im, 504, 0.6)


def calendar() -> Image.Image:
    w, h = 256, 256
    im = Image.new("RGBA", (w, h), rgb("#f4efe4") + (255,))
    d = ImageDraw.Draw(im)
    # picture: pastel landscape (lake + pagoda-like silhouette, generic)
    sky = np.linspace(0, 1, 120)[:, None]
    pic = np.zeros((120, 236, 3), np.float32)
    pic[:] = (np.array([0.95, 0.75, 0.55]) * (1 - sky) + np.array([0.55, 0.7, 0.85]) * sky)[:, None, :]
    pic = pic[::-1]
    pic[85:] = np.array([0.35, 0.5, 0.55])
    im.paste(Image.fromarray((pic * 255).astype(np.uint8)), (10, 10))
    d.polygon([(60, 95), (90, 70), (120, 95)], fill=(40, 40, 50))
    d.rectangle([75, 95, 105, 102], fill=(40, 40, 50))
    d.rectangle([10, 140, w - 10, 182], fill=rgb("#c0271c"))
    GA.draw_text_condensed(im, (w / 2, 161), "THÁNG 8", F_BVP, 160, 30, (255, 245, 220, 255))
    for r in range(3):
        for c in range(7):
            d.text((18 + c * 33, 190 + r * 20), str(1 + r * 7 + c), fill=(60, 60, 60))
    return GA.weather_rgba(im, 505, 0.7)


def pile(w, h, seed, items, bg="#3a2e22", density=1.0):
    """Top-down pile of round/oval items: items = [(hex, rmin, rmax, aspect, weight)]."""
    r = np.random.default_rng(seed)
    im = Image.new("RGBA", (w, h), rgb(bg) + (255,))
    d = ImageDraw.Draw(im)
    wts = np.array([it[4] for it in items], float)
    wts /= wts.sum()
    count = int(w * h / 180 * density)
    for _ in range(count):
        it = items[r.choice(len(items), p=wts)]
        cx, cy = r.uniform(-10, w + 10), r.uniform(-10, h + 10)
        rad = r.uniform(it[1], it[2])
        asp = it[3]
        ang = r.uniform(0, math.pi)
        base = np.array(rgb(it[0]), float) * r.uniform(0.8, 1.1)
        # shaded ellipse: 4 concentric steps from dark rim to highlight
        for k, f in enumerate((1.0, 0.8, 0.55, 0.25)):
            c = np.clip(base * (0.55 + 0.18 * k), 0, 255).astype(int)
            pts = [(cx + math.cos(t) * rad * f * math.cos(ang) - math.sin(t) * rad * f * asp * math.sin(ang)
                    - rad * 0.15 * k,
                    cy + math.cos(t) * rad * f * math.sin(ang) + math.sin(t) * rad * f * asp * math.cos(ang)
                    - rad * 0.15 * k) for t in np.linspace(0, 2 * math.pi, 18)]
            d.polygon(pts, fill=tuple(c))
    return im.filter(ImageFilter.GaussianBlur(0.6))


def greens(w, h, seed, pal=("#2f5a1f", "#3f7a2a", "#5c9a3a", "#284a1a"), stems="#9fbf6a"):
    r = np.random.default_rng(seed)
    im = Image.new("RGBA", (w, h), rgb("#22301a") + (255,))
    d = ImageDraw.Draw(im)
    for _ in range(int(w * h / 90)):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        L = r.uniform(10, 26)
        a = r.uniform(0, math.pi * 2)
        c = np.array(rgb(pal[r.integers(0, len(pal))])) * r.uniform(0.8, 1.2)
        tip = (cx + math.cos(a) * L, cy + math.sin(a) * L)
        side = (math.cos(a + math.pi / 2) * L * 0.3, math.sin(a + math.pi / 2) * L * 0.3)
        mid = (cx + math.cos(a) * L * 0.45, cy + math.sin(a) * L * 0.45)
        d.polygon([(cx, cy), (mid[0] + side[0], mid[1] + side[1]), tip, (mid[0] - side[0], mid[1] - side[1])],
                  fill=tuple(np.clip(c, 0, 255).astype(int)))
        d.line([(cx, cy), tip], fill=rgb(stems), width=1)
    return im


def fish_ice() -> Image.Image:
    w, h = 512, 256
    im = ice_img(w, h, 61)
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(62)
    for k in range(9):
        cx, cy = r.uniform(40, w - 40), r.uniform(30, h - 30)
        L = r.uniform(70, 110)
        a = r.uniform(-0.5, 0.5) + (math.pi if k % 2 else 0)
        kind = k % 3
        body = [(-1, 0), (-0.7, -0.17), (-0.2, -0.24), (0.4, -0.18), (0.75, -0.06), (0.86, 0), (0.75, 0.06),
                (0.4, 0.18), (-0.2, 0.24), (-0.7, 0.17)]
        tail = [(0.82, 0), (1.05, -0.17), (1.0, 0), (1.05, 0.17)]

        def tr(p):
            return (cx + (p[0] * math.cos(a) - p[1] * math.sin(a)) * L / 2,
                    cy + (p[0] * math.sin(a) + p[1] * math.cos(a)) * L / 2)
        back = {0: "#3d5a6a", 1: "#5c6c70", 2: "#7a5a46"}[kind]
        belly = {0: "#c8d0d4", 1: "#d8d8d0", 2: "#d9b49a"}[kind]
        d.polygon([tr(p) for p in body], fill=rgb(belly))
        d.polygon([tr(p) for p in body[:6]] + [tr((0.86, -0.02)), tr((-1, -0.02))], fill=rgb(back))
        d.polygon([tr(p) for p in tail], fill=rgb(back))
        # mackerel stripes / scales
        for s in range(6):
            x = -0.5 + s * 0.2
            d.line([tr((x, -0.2)), tr((x + 0.06, -0.08))], fill=rgb("#1d2c34"), width=2)
        ex, ey = tr((-0.78, -0.04))
        d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(230, 225, 200))
        d.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=(20, 20, 20))
        d.line([tr((-0.6, -0.16)), tr((-0.55, 0.0)), tr((-0.6, 0.16))], fill=rgb("#8a2a22"), width=2)  # gill
        hx, hy = tr((0.0, -0.1))
        d.ellipse([hx - 8, hy - 3, hx + 8, hy + 3], fill=(240, 245, 245))  # wet highlight
    return im


def ice_img(w, h, seed):
    r = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.float32)
    nz = noise_img(w, h, seed, 8, 200)
    base[:] = np.array([0.78, 0.84, 0.86])
    base *= (0.9 + 0.08 * nz[..., None])
    im = Image.fromarray((base * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    for _ in range(int(w * h / 60)):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        s = r.uniform(3, 9)
        v = int(r.uniform(170, 250))
        d.polygon([(cx + math.cos(a) * s * r.uniform(0.6, 1.2), cy + math.sin(a) * s * r.uniform(0.6, 1.2))
                   for a in np.linspace(0, 2 * math.pi, 6)[:-1]], fill=(v - 20, v - 6, v))
    return im.filter(ImageFilter.GaussianBlur(0.5))


def shrimp() -> Image.Image:
    w, h = 256, 256
    im = ice_img(w, h, 71)
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(72)
    for _ in range(26):
        cx, cy = r.uniform(10, w - 10), r.uniform(10, h - 10)
        s = r.uniform(14, 22)
        a0 = r.uniform(0, 2 * math.pi)
        pts = [(cx + math.cos(a0 + t) * s * (1 - 0.3 * t / 3), cy + math.sin(a0 + t) * s * (1 - 0.3 * t / 3))
               for t in np.linspace(0, 3.4, 12)]
        d.line(pts, fill=rgb("#c96a4a"), width=int(s * 0.5), joint="curve")
        d.line(pts, fill=rgb("#e59a72"), width=int(s * 0.18), joint="curve")
    return im


def nest() -> Image.Image:
    """Alpha-cut twig mat for the crow nest cards."""
    w, h = 512, 512
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = np.random.default_rng(81)
    for _ in range(900):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        L = r.uniform(30, 120)
        a = r.uniform(0, math.pi * 2)
        bend = r.uniform(-0.3, 0.3)
        pts = [(cx + math.cos(a + bend * t) * L * t, cy + math.sin(a + bend * t) * L * t) for t in np.linspace(0, 1, 6)]
        c = r.choice(["#4a3524", "#5e4630", "#3a2a1c", "#7a6248", "#8d7a5a", "#2e2218"])
        d.line(pts, fill=rgb(c) + (255,), width=int(r.integers(2, 6)))
    # soft fibres / grass
    for _ in range(300):
        cx, cy = r.uniform(0, w), r.uniform(0, h)
        a = r.uniform(0, math.pi * 2)
        d.line([(cx, cy), (cx + math.cos(a) * 40, cy + math.sin(a) * 40)], fill=rgb("#a69469") + (255,), width=1)
    return im


def cafe_interior() -> Image.Image:
    w, h = 512, 512
    yy = np.linspace(0, 1, h)[:, None, None]
    base = np.array([0.32, 0.22, 0.14]) * (1 - yy) + np.array([0.18, 0.12, 0.08]) * yy
    im = Image.fromarray((np.broadcast_to(base, (h, w, 3)) * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    # back wall: shelves with jars/cups, pendant lamps, a counter, plants
    d.rectangle([0, 0, w, 300], fill=rgb("#d9c7a8"))
    for y in (90, 170):
        d.rectangle([40, y, 470, y + 8], fill=rgb("#6b4a2e"))
        x = 50
        r = np.random.default_rng(y)
        while x < 460:
            ww = r.integers(14, 30)
            hh = r.integers(20, 50)
            c = r.choice(["#efe8da", "#3a3a3a", "#8a5a3a", "#c9b07a", "#5b7a5b", "#2e4a6a"])
            d.rectangle([x, y - hh, x + ww, y], fill=rgb(c))
            x += ww + r.integers(4, 12)
    for x in (110, 256, 400):
        d.line([(x, 0), (x, 60)], fill=(30, 30, 30), width=2)
        d.polygon([(x - 26, 86), (x - 14, 60), (x + 14, 60), (x + 26, 86)], fill=rgb("#2c2c2c"))
        d.ellipse([x - 22, 78, x + 22, 98], fill=(255, 228, 170))
    d.rectangle([0, 300, w, 330], fill=rgb("#4a3020"))
    d.rectangle([0, 330, w, h], fill=rgb("#5d3d26"))
    # espresso machine + counter
    d.rectangle([300, 240, 420, 300], fill=rgb("#b8b8b6"))
    d.rectangle([310, 250, 410, 270], fill=rgb("#555555"))
    # monstera plant
    r = np.random.default_rng(5)
    for _ in range(14):
        cx, cy = 60 + r.uniform(-40, 40), 260 + r.uniform(-90, 40)
        d.ellipse([cx - 28, cy - 18, cx + 28, cy + 18], fill=rgb("#2f5a2a"))
    d.rectangle([40, 300, 90, 360], fill=rgb("#c9b9a0"))
    img = im.filter(ImageFilter.GaussianBlur(2.2))  # seen through glass, slightly soft
    a = np.asarray(img, np.float32)
    vign = noise_img(w, h, 9, 1, 8)[..., None] * 6
    a[..., :3] = np.clip(a[..., :3] + vign, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def price_cards() -> Image.Image:
    w, h = 512, 256
    im = Image.new("RGBA", (w, h), rgb("#c9b28c") + (255,))
    labels = [("CÁ THU", "120k"), ("CÁ RÔ", "60k"), ("TÔM", "180k"), ("RAU", "10k"), ("CÀ CHUA", "25k"),
              ("CAM", "35k"), ("ỚT", "5k"), ("THANH LONG", "30k")]
    for i, (a, b) in enumerate(labels):
        x0, y0 = (i % 4) * 128, (i // 4) * 128
        card = Image.new("RGBA", (124, 124), rgb("#efe6d0" if i % 3 else "#d9c49a") + (255,))
        GA.draw_text_condensed(card, (62, 40), a, F_HAND, 110, 28, rgb("#1d2c7a") + (255,))
        GA.draw_text_condensed(card, (62, 86), b, F_HAND, 100, 44, rgb("#b5231a") + (255,))
        im.paste(card, (x0 + 2, y0 + 2))
    return GA.weather_rgba(im, 506, 0.8)


def sign_fish() -> Image.Image:
    w, h = 512, 128
    im = Image.new("RGBA", (w, h), rgb("#1f4f8a") + (255,))
    GA.draw_text_condensed(im, (w / 2, 54), "CÁ TƯƠI CÔ HOA", F_BVP, 470, 66, (255, 255, 255, 255))
    GA.draw_text_condensed(im, (w / 2, 106), "Cá sông · Cá biển · Tôm cua", F_BVP5, 320, 22, rgb("#ffe08a") + (255,))
    return GA.weather_rgba(im, 507, 0.8)


def lantern_paper() -> Image.Image:
    w, h = 256, 256
    a = np.zeros((h, w, 3), np.float32)
    nz = noise_img(w, h, 111, 4, 120)
    a[:] = np.array([0.82, 0.16, 0.1])
    a *= (0.85 + 0.12 * nz[..., None])
    yy, xx = np.mgrid[0:h, 0:w]
    ribs = (np.mod(xx, 32) < 2)
    a[ribs] *= 0.6
    im = Image.fromarray((a * 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 20], fill=rgb("#d0a64e"))
    d.rectangle([0, h - 20, w, h], fill=rgb("#d0a64e"))
    return im


def tea_label() -> Image.Image:
    w, h = 256, 256
    im = Image.new("RGBA", (w, h), rgb("#2d6a3a") + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([10, 10, w - 11, h - 11], outline=rgb("#e8d48a"), width=4)
    GA.draw_text_condensed(im, (w / 2, 90), "CHÈ THÁI", F_BVP, 200, 50, rgb("#f4e7b0") + (255,))
    GA.draw_text_condensed(im, (w / 2, 150), "TÂN CƯƠNG · 200g", F_BVP5, 190, 22, rgb("#f4e7b0") + (255,))
    d.ellipse([w / 2 - 30, 180, w / 2 + 30, 230], outline=rgb("#e8d48a"), width=3)
    return GA.weather_rgba(im, 508, 0.3)


def fabric_cell(w, h, seed, pal) -> Image.Image:
    a = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.random.default_rng(seed)
    band = (yy // max(4, h // 8)) % len(pal)
    for i, c in enumerate(pal):
        a[band == i] = np.array(rgb(c)) / 255
    weave = (np.sin(xx * 1.6) * np.sin(yy * 1.6)) * 0.04
    nz = noise_img(w, h, seed, 2, 60)
    a = a * (0.88 + weave[..., None] + 0.06 * nz[..., None])
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGBA")


def lost_cat_poster() -> Image.Image:
    w, h = 256, 128
    im = Image.new("RGBA", (w, h), rgb("#f2efe6") + (255,))
    GA.draw_text_condensed(im, (w / 2, 22), "TÌM VỊT LẠC", F_BVP, 200, 28, rgb("#c0271c") + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([14, 40, 100, 116], fill=rgb("#d8d0b8"))
    d.ellipse([34, 56, 80, 100], fill=rgb("#e7c050"))
    d.ellipse([60, 50, 84, 72], fill=rgb("#e7c050"))
    d.polygon([(82, 60), (96, 63), (82, 66)], fill=rgb("#e08a2a"))
    for i, t in enumerate(["Vịt trắng, tên Bơ", "Ai thấy xin báo", "Bà Tư - quán trà", "Hậu tạ!"]):
        GA.draw_text_condensed(im, (176, 54 + i * 18), t, F_HAND, 140, 14, rgb("#333333") + (255,))
    return GA.weather_rgba(im, 509, 0.8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    A = Atlas()
    for i, nm in enumerate(("door_a", "door_b")):
        im, h = door_panel(i)
        A.put(nm, im, h)
    for nm, sd in (("couplet_l", 300), ("couplet_r", 400)):
        im, h = couplet(sd)
        A.put(nm, im, h)
    im, h = plaque()
    A.put("plaque_dinh", im, h)
    im, h = frieze()
    A.put("frieze", im, h)
    A.put("sign_cho", sign_cho())
    A.put("sign_cafe", sign_cafe())
    A.put("sign_tea", sign_tea())
    A.put("menu_tea", handwritten_board(256, 256, [("Trà đá", "5k"), ("Trà nóng", "5k"), ("Nước vối", "7k"),
                                                     ("Hướng dương", "10k"), ("Kẹo lạc", "3k"), ("Bánh quy", "5k")],
                                        "#f0e8d2", "#1d2a6a", 510, title="BÀ TƯ"))
    A.put("menu_cafe", handwritten_board(256, 256, [("Cà phê nâu", "35"), ("Bạc xỉu", "39"), ("Cà phê trứng", "45"),
                                                      ("Trà sen", "40"), ("Sữa chua", "35")],
                                         "#22272a", "#ece6d6", 511, chalk=True, title="Bông café"))
    A.put("shrine_back", shrine_back())
    A.put("calendar", calendar())
    snacks = {
        "snack_peanut": [("#b07a3a", 5, 9, 0.8, 3), ("#d6a55a", 4, 7, 0.9, 2), ("#7a4a22", 3, 5, 0.8, 1)],
        "snack_seeds": [("#2a2622", 3, 5, 0.45, 3), ("#e8e2d2", 2, 4, 0.45, 1), ("#5a5248", 3, 5, 0.45, 1)],
        "snack_plum": [("#7a1a1a", 7, 11, 0.9, 3), ("#a8322a", 6, 9, 0.9, 2), ("#4a0f10", 6, 9, 1.0, 1)],
        "snack_biscuit": [("#d9a75a", 11, 15, 0.9, 3), ("#c48a42", 10, 14, 0.9, 1)],
        "snack_tea": [("#3e4a22", 2, 5, 0.4, 3), ("#5d6a32", 2, 4, 0.5, 2), ("#2a3218", 2, 4, 0.4, 1)],
        "snack_ginger": [("#e6d38a", 6, 10, 0.7, 3), ("#f2e6b0", 6, 9, 0.8, 1)],
        "snack_candy": [("#d0302a", 6, 9, 0.6, 1), ("#2a7ad0", 6, 9, 0.6, 1), ("#f0c020", 6, 9, 0.6, 1),
                        ("#30a050", 6, 9, 0.6, 1), ("#f2f2f2", 6, 9, 0.6, 1)],
        "snack_rice": [("#e9e1c6", 8, 14, 0.9, 3), ("#d6c48e", 8, 12, 0.9, 1)],
    }
    for k, (nm, items) in enumerate(snacks.items()):
        A.put(nm, pile(128, 128, 600 + k, items, "#4a3a2a", 1.4))
    A.put("fish_ice", fish_ice())
    A.put("shrimp", shrimp())
    A.put("ice", ice_img(256, 256, 73))
    A.put("veg_greens", greens(256, 256, 74))
    A.put("veg_herbs", greens(256, 256, 75, ("#3d6a2a", "#5a8a36", "#7aa04a", "#2e5220"), "#c8d89a"))
    A.put("veg_tomato", pile(256, 256, 76, [("#c42a1a", 14, 20, 0.95, 4), ("#d8501f", 13, 18, 0.95, 1),
                                            ("#6a9a2a", 3, 5, 1, 0.3)]))
    A.put("veg_chili", pile(256, 256, 77, [("#c41a12", 4, 6, 4.0, 3), ("#2f6a1a", 4, 6, 4.0, 1)], density=1.6))
    A.put("fruit_orange", pile(256, 256, 78, [("#d98a1a", 18, 24, 0.95, 3), ("#8aa02a", 18, 22, 0.95, 1)]))
    A.put("fruit_dragon", pile(256, 256, 79, [("#c4206a", 22, 30, 0.75, 3), ("#5a9a2a", 6, 9, 1.8, 1)]))
    A.put("fruit_banana", pile(256, 256, 80, [("#e2c23a", 8, 11, 4.0, 3), ("#a8a82a", 8, 11, 4.0, 1)], density=1.3))
    A.put("dried_goods", pile(256, 256, 82, [("#8a5a2a", 6, 10, 0.6, 2), ("#c9a06a", 4, 7, 0.7, 2),
                                             ("#5a3a20", 5, 8, 0.9, 1)], density=1.5))
    A.put("price_cards", price_cards())
    A.put("sign_fish", sign_fish())
    A.put("nest", nest())
    A.put("cafe_interior", cafe_interior())
    A.put("lantern_paper", lantern_paper())
    A.put("tea_label", tea_label())
    A.put("fabric_dark", fabric_cell(512, 256, 83, ("#3a3a4a", "#4a3a3a", "#2e3a40")))
    A.put("fabric_bundle", fabric_cell(512, 128, 84, ("#7a2a3a", "#2a5a8a", "#c9a03a", "#3a6a3a")))
    A.put("poster_lost_cat", lost_cat_poster())
    A.put("cushion", fabric_cell(256, 128, 85, ("#b34a2a", "#c95a32")))
    A.save()
    if a.sheet:
        im = A.img.convert("RGB").resize((1024, 1024))
        im.save(os.path.join(ROOT, "qa", "out", "city-landmarks", "atlas_sheet.jpg"), quality=88)
        print("SHEET")


if __name__ == "__main__":
    main()
