#!/usr/bin/env python3
"""Generates the painted UI textures of Mèo Cam (owner: ui) into assets/ui/textures/.

Everything is procedural (numpy + Pillow), deterministic (fixed seeds) and supersampled 4x for
clean anti-aliased edges. Run from the repo root:  python3 scripts/ui/build/gen_ui_textures.py
Then: tools/godot_import.sh

Art direction: Vietnamese old quarter at lantern time — warm lacquer-black panels with hairline
gold borders and cloud-scroll corners, aged rice paper, red seal stamps, ink-brush highlights.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "assets", "ui", "textures")
SS = 4  # supersampling factor


def rng(seed):
    return np.random.default_rng(seed)


def value_noise(w, h, cell, seed, octaves=4, persistence=0.5, tile=True):
    """Tileable fractal value noise in [0,1], shape (h, w)."""
    r = rng(seed)
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    total = 0.0
    c = cell
    for _ in range(octaves):
        gw = max(1, int(round(w / c)))
        gh = max(1, int(round(h / c)))
        grid = r.random((gh, gw)).astype(np.float32)
        ys = np.linspace(0, gh, h, endpoint=False)
        xs = np.linspace(0, gw, w, endpoint=False)
        y0 = np.floor(ys).astype(int)
        x0 = np.floor(xs).astype(int)
        fy = ys - y0
        fx = xs - x0
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        y1 = (y0 + 1) % gh if tile else np.minimum(y0 + 1, gh - 1)
        x1 = (x0 + 1) % gw if tile else np.minimum(x0 + 1, gw - 1)
        a = grid[y0][:, x0]
        b = grid[y0][:, x1]
        cc = grid[y1][:, x0]
        d = grid[y1][:, x1]
        top = a + (b - a) * fx[None, :]
        bot = cc + (d - cc) * fx[None, :]
        out += amp * (top + (bot - top) * fy[:, None])
        total += amp
        amp *= persistence
        c = max(1, c / 2)
    return out / total


def fibers(w, h, seed, count=900, length=(6, 40), alpha=0.08):
    """Paper fibres: thin random curved strokes, returned as float mask (h, w)."""
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    r = rng(seed)
    for _ in range(count):
        x, y = r.random() * w, r.random() * h
        ang = r.random() * math.pi
        ln = r.uniform(*length)
        pts = []
        for i in range(6):
            t = i / 5.0
            ang += r.normal(0, 0.15)
            pts.append((x + math.cos(ang) * ln * t, y + math.sin(ang) * ln * t))
        d.line(pts, fill=int(255 * r.uniform(0.3, 1.0)), width=1)
    return np.asarray(img, np.float32) / 255.0 * alpha


def to_img(rgba):
    return Image.fromarray(np.clip(rgba * 255.0 + 0.5, 0, 255).astype(np.uint8), "RGBA")


def downsample(img, factor=SS):
    return img.resize((img.width // factor, img.height // factor), Image.LANCZOS)


def hexc(s, a=1.0):
    s = s.lstrip("#")
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0, a)


def rgba8(c):
    return tuple(int(round(v * 255)) for v in c)


# ---------------------------------------------------------------------------------------------
# Cloud-scroll corner ornament (stylised "mây" motif from carved temple woodwork)
# ---------------------------------------------------------------------------------------------

def draw_cloud_corner(d, ox, oy, s, color, width, flip_x=False, flip_y=False):
    """Draws a small cloud-scroll in a corner. (ox, oy) = corner point, s = size in px."""
    fx = -1 if flip_x else 1
    fy = -1 if flip_y else 1

    def P(x, y):
        return (ox + fx * x * s, oy + fy * y * s)

    # L-shaped double line hugging the corner
    d.line([P(0.10, 0.95), P(0.10, 0.10), P(0.95, 0.10)], fill=color, width=width, joint="curve")
    # spiral scroll
    pts = []
    for i in range(80):
        t = i / 79.0
        a = math.pi * 0.5 + t * math.pi * 2.6
        rr = 0.30 * (1.0 - 0.75 * t)
        pts.append(P(0.42 + math.cos(a) * rr, 0.42 + math.sin(a) * rr))
    d.line(pts, fill=color, width=width, joint="curve")
    # little tails along each edge
    for i in range(2):
        tail = []
        for j in range(30):
            t = j / 29.0
            if i == 0:
                tail.append(P(0.42 + 0.30 + t * 0.35, 0.42 - math.sin(t * math.pi) * 0.10))
            else:
                tail.append(P(0.42 - math.sin(t * math.pi) * 0.10, 0.42 + 0.30 + t * 0.35))
        d.line(tail, fill=color, width=width, joint="curve")
    # dot
    cx, cy = P(0.42, 0.42)
    rdot = width * 0.9
    d.ellipse([cx - rdot, cy - rdot, cx + rdot, cy + rdot], fill=color)


# ---------------------------------------------------------------------------------------------
# Textures
# ---------------------------------------------------------------------------------------------

def panel_lacquer(size=256, margin=56, name="panel_lacquer.png", alpha=0.90, corners=True, seed=11):
    W = size * SS
    m = margin * SS
    n = value_noise(W, W, 64 * SS, seed, 5)
    grain = value_noise(W, W, 3 * SS, seed + 1, 2)
    streak = value_noise(W, W // 8, 48 * SS, seed + 2, 3)
    streak = np.repeat(streak, 8, axis=0)[:W, :W] if streak.shape[0] * 8 >= W else np.resize(streak, (W, W))
    base = np.array(hexc("#1c140f")[:3], np.float32)
    warm = np.array(hexc("#3a2117")[:3], np.float32)
    t = np.clip(n * 0.65 + streak * 0.35, 0, 1)[..., None]
    rgb = base * (1 - t * 0.55) + warm * (t * 0.55)
    rgb *= (0.94 + grain[..., None] * 0.10)
    # inner glow toward the centre (lamp light on lacquer)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32) / W
    rad = np.sqrt((xx - 0.5) ** 2 + (yy - 0.35) ** 2)
    rgb *= (1.0 + 0.10 * np.clip(1 - rad * 1.6, 0, 1))[..., None]
    a = np.full((W, W), alpha, np.float32)
    # rounded outer edge (soft, 10 px radius)
    r_px = 10 * SS
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, W - 1], radius=r_px, fill=255)
    a *= np.asarray(mask, np.float32) / 255.0
    img = to_img(np.dstack([rgb, a]))
    d = ImageDraw.Draw(img)
    gold = rgba8(hexc("#d9a441", 0.85))
    gold_dim = rgba8(hexc("#d9a441", 0.35))
    inset = 9 * SS
    d.rounded_rectangle([inset, inset, W - 1 - inset, W - 1 - inset], radius=4 * SS, outline=gold, width=int(1.4 * SS))
    inset2 = 14 * SS
    d.rounded_rectangle([inset2, inset2, W - 1 - inset2, W - 1 - inset2], radius=3 * SS, outline=gold_dim, width=int(1.0 * SS))
    # top highlight bevel
    hl = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, W - 2 * SS], radius=r_px, outline=(255, 220, 170, 40), width=2 * SS)
    img = Image.alpha_composite(img, hl)
    d = ImageDraw.Draw(img)
    if corners:
        cs = 40 * SS
        w_line = int(1.6 * SS)
        for fx_, fy_, ox, oy in [(False, False, inset2, inset2), (True, False, W - 1 - inset2, inset2),
                                 (False, True, inset2, W - 1 - inset2), (True, True, W - 1 - inset2, W - 1 - inset2)]:
            draw_cloud_corner(d, ox, oy, cs, gold, w_line, fx_, fy_)
    out = downsample(img)
    out.save(os.path.join(OUT, name))
    return out


def panel_paper(size=256, name="panel_paper.png", seed=21, tint="#efe0bf", edge_dark=0.28, deckle=True):
    W = size * SS
    n = value_noise(W, W, 48 * SS, seed, 5)
    blot = value_noise(W, W, 96 * SS, seed + 7, 3)
    fib = fibers(W, W, seed + 3, count=1400 * SS, length=(4 * SS, 26 * SS), alpha=0.10)
    base = np.array(hexc(tint)[:3], np.float32)
    rgb = base[None, None, :] * (0.93 + 0.09 * n[..., None])
    stain = np.clip((blot - 0.55) * 2.2, 0, 1)[..., None]
    rgb = rgb * (1 - stain * 0.10) + np.array(hexc("#b88a4a")[:3]) * stain * 0.10
    rgb -= fib[..., None] * np.array([0.35, 0.40, 0.48])
    # edge darkening (aged)
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32) / W
    edge = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    e = np.clip(1 - edge / 0.16, 0, 1) ** 2.2
    rgb *= (1 - e[..., None] * edge_dark * (0.7 + 0.6 * n[..., None]))
    # deckled alpha edge
    a = np.ones((W, W), np.float32)
    if deckle:
        jag = value_noise(W, W, 6 * SS, seed + 9, 3)
        thr = 0.012 + jag * 0.018
        a = np.clip((edge - thr) / 0.006, 0, 1)
    img = to_img(np.dstack([np.clip(rgb, 0, 1), a]))
    out = downsample(img)
    out.save(os.path.join(OUT, name))
    return out


def brush_highlight(name="brush_highlight.png", w=640, h=110, seed=31, color="#d9a441"):
    """Dry-brush ink stroke, white-ish core fading to ragged ends; tinted in engine via modulate."""
    W, H = w * SS, h * SS
    r = rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = xx / W
    v = (yy / H - 0.5) * 2.0
    # stroke thickness profile: swells in the first third, tapers at the end
    thick = 0.62 * (np.sin(np.clip(u, 0, 1) * math.pi) ** 0.45) * (1.0 - 0.25 * u)
    wav = 0.06 * np.sin(u * 7.0 + 1.3)
    body = np.clip((thick - np.abs(v - wav)) / 0.05, 0, 1)
    # bristle streaks
    streaks = value_noise(W, H, 2 * SS, seed + 1, 2, tile=False)
    bristle = value_noise(1, H, 2 * SS, seed + 2, 1, tile=False) if False else None
    rows = r.random(H).astype(np.float32)
    rows = np.convolve(rows, np.ones(5) / 5, mode="same")
    dry = np.clip((rows[:, None] - 0.25 - 0.55 * u ** 3) * 3.0, 0, 1)
    dry = dry * (0.75 + 0.25 * streaks)
    # ragged ends
    ends = value_noise(W, H, 8 * SS, seed + 3, 3, tile=False)
    endmask = np.clip((u - 0.015 - ends * 0.05) / 0.03, 0, 1) * np.clip((0.985 - u - ends * 0.12) / 0.05, 0, 1)
    a = body * (0.55 + 0.45 * dry) * endmask
    c = np.array(hexc(color)[:3], np.float32)
    rgb = np.ones((H, W, 3), np.float32) * c
    img = to_img(np.dstack([rgb, a.astype(np.float32)]))
    img = img.filter(ImageFilter.GaussianBlur(0.6 * SS))
    downsample(img).save(os.path.join(OUT, name))


def glow(name="glow_soft.png", size=256, power=2.2):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** power
    img = to_img(np.dstack([np.ones((size, size, 3), np.float32), a]))
    img.save(os.path.join(OUT, name))


def bokeh(name="bokeh.png", size=128):
    """Soft disc with a brighter rim (lens bokeh of distant lanterns)."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2 + 0.5) ** 2 + (yy - size / 2 + 0.5) ** 2) / (size / 2 - 2)
    disc = np.clip((1 - r) / 0.06, 0, 1)
    rim = np.exp(-((r - 0.9) / 0.08) ** 2) * 0.35
    a = np.clip(disc * (0.55 + 0.45 * r ** 2) + rim * disc, 0, 1)
    img = to_img(np.dstack([np.ones((size, size, 3), np.float32), a * 0.9]))
    img.save(os.path.join(OUT, name))


def vignette(name="vignette.png", size=512):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    r = np.sqrt(((xx - 0.5) * 1.25) ** 2 + (yy - 0.5) ** 2) * 1.6
    a = np.clip(r - 0.35, 0, 1) ** 1.6
    rgb = np.ones((size, size, 3), np.float32) * np.array(hexc("#0b0705")[:3])
    to_img(np.dstack([rgb, np.clip(a, 0, 1)])).save(os.path.join(OUT, name))


def paper_grain(name="paper_grain.png", size=512, seed=41):
    n = value_noise(size, size, 2, seed, 3)
    f = fibers(size, size, seed + 1, count=1800, length=(3, 18), alpha=0.5)
    v = np.clip(0.5 + (n - 0.5) * 0.6 - f * 0.4, 0, 1)
    rgb = np.dstack([v, v, v])
    a = np.full((size, size), 1.0, np.float32)
    to_img(np.dstack([rgb, a])).save(os.path.join(OUT, name))


def divider(name="divider.png", w=720, h=40, color="#d9a441"):
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = rgba8(hexc(color, 0.9))
    cy = H // 2
    # tapered lines
    for side in (-1, 1):
        for i in range(60):
            t0 = i / 60.0
            t1 = (i + 1) / 60.0
            x0 = W / 2 + side * (34 * SS + t0 * (W / 2 - 40 * SS))
            x1 = W / 2 + side * (34 * SS + t1 * (W / 2 - 40 * SS))
            a = int(230 * (1 - t0) ** 1.4)
            d.line([(x0, cy), (x1, cy)], fill=(c[0], c[1], c[2], a), width=int(1.5 * SS))
        # small dots
        for k in range(3):
            x = W / 2 + side * (44 * SS + k * 14 * SS)
            rr = (2.2 - k * 0.5) * SS
            d.ellipse([x - rr, cy - 7 * SS - rr, x + rr, cy - 7 * SS + rr], fill=(c[0], c[1], c[2], 160 - k * 40))
    # lotus/diamond centre
    s = 11 * SS
    d.polygon([(W / 2, cy - s), (W / 2 + s, cy), (W / 2, cy + s), (W / 2 - s, cy)], outline=c, width=int(1.6 * SS))
    s2 = 5 * SS
    d.polygon([(W / 2, cy - s2), (W / 2 + s2, cy), (W / 2, cy + s2), (W / 2 - s2, cy)], fill=c)
    for side in (-1, 1):
        d.arc([W / 2 + side * 14 * SS - 8 * SS, cy - 8 * SS, W / 2 + side * 14 * SS + 8 * SS, cy + 8 * SS],
              0 if side > 0 else 180, 180 if side > 0 else 360, fill=c, width=int(1.4 * SS))
    downsample(img).save(os.path.join(OUT, name))


def paw_path(d, cx, cy, s, fill):
    """Cat paw print: main pad + 4 toe beans."""
    # main pad (rounded triangle via ellipses)
    d.ellipse([cx - 0.42 * s, cy - 0.05 * s, cx + 0.42 * s, cy + 0.45 * s], fill=fill)
    d.ellipse([cx - 0.30 * s, cy - 0.12 * s, cx + 0.30 * s, cy + 0.30 * s], fill=fill)
    for (tx, ty, rx, ry) in [(-0.43, -0.30, 0.13, 0.17), (-0.16, -0.52, 0.14, 0.18), (0.16, -0.52, 0.14, 0.18), (0.43, -0.30, 0.13, 0.17)]:
        d.ellipse([cx + (tx - rx) * s, cy + (ty - ry) * s, cx + (tx + rx) * s, cy + (ty + ry) * s], fill=fill)


def seal_stamp(name="seal_stamp.png", size=256, seed=51, color="#b8321f", glyph="paw"):
    """Square red seal (con dấu) with worn ink and a negative paw print."""
    W = size * SS
    img = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(img)
    m = 18 * SS
    d.rounded_rectangle([m, m, W - m, W - m], radius=18 * SS, fill=255)
    inner = 34 * SS
    d.rounded_rectangle([inner, inner, W - inner, W - inner], radius=10 * SS, outline=0, width=6 * SS)
    if glyph == "paw":
        paw_path(d, W / 2, W / 2 + 6 * SS, 92 * SS, 0)
    elif glyph == "check":
        d.line([(W * 0.30, W * 0.52), (W * 0.45, W * 0.67), (W * 0.72, W * 0.36)], fill=0, width=18 * SS, joint="curve")
    a = np.asarray(img, np.float32) / 255.0
    # ink wear: speckles and uneven pressure
    n = value_noise(W, W, 3 * SS, seed, 3)
    n2 = value_noise(W, W, 40 * SS, seed + 1, 3)
    wear = np.clip((n - 0.25 - n2 * 0.25) * 4.0, 0, 1)
    a = a * (0.55 + 0.45 * wear)
    # rough outer edge
    a_img = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2 * SS))
    a = np.asarray(a_img, np.float32) / 255.0
    edge = value_noise(W, W, 5 * SS, seed + 2, 2)
    a = np.clip((a - 0.35 - (edge - 0.5) * 0.3) * 3.0, 0, 1) * 0.92
    c = np.array(hexc(color)[:3], np.float32)
    rgb = np.ones((W, W, 3), np.float32) * c * (0.9 + 0.2 * n2[..., None])
    downsample(to_img(np.dstack([np.clip(rgb, 0, 1), a]))).save(os.path.join(OUT, name))


def slot_frame(name="slot_frame.png", size=128, seed=61):
    """Item slot: recessed paper square with a thin ink border (9-slice, margins 20)."""
    W = size * SS
    base = panel_paper(size, name="_tmp_paper.png", seed=seed, tint="#e6d3ad", edge_dark=0.45, deckle=False)
    big = base.resize((W, W), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([3 * SS, 3 * SS, W - 3 * SS, W - 3 * SS], radius=8 * SS, outline=(70, 48, 32, 200), width=int(1.6 * SS))
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rounded_rectangle([2 * SS, 2 * SS, W - 2 * SS, W - 2 * SS], radius=9 * SS, fill=255)
    big.putalpha(Image.fromarray(np.minimum(np.asarray(big.split()[3]), np.asarray(mask))))
    # inner shadow at top
    sh = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for i in range(12):
        sd.rounded_rectangle([4 * SS + i * SS, 4 * SS + i * SS, W - 4 * SS - i * SS, W - 4 * SS - i * SS], radius=8 * SS,
                             outline=(40, 25, 15, int(30 * (1 - i / 12))), width=SS)
    big = Image.alpha_composite(big, sh)
    downsample(big).save(os.path.join(OUT, name))
    os.remove(os.path.join(OUT, "_tmp_paper.png"))


def nameplate(name="nameplate.png", w=256, h=72, seed=71):
    """Red-lacquer name tag (9-slice horizontally, margins 28) with gold edge."""
    W, H = w * SS, h * SS
    n = value_noise(W, H, 24 * SS, seed, 4, tile=False)
    c0 = np.array(hexc("#7a2416")[:3])
    c1 = np.array(hexc("#a8331d")[:3])
    yy = np.linspace(0, 1, H)[:, None, None]
    rgb = c1 * (1 - yy) + c0 * yy
    rgb = rgb * (0.9 + 0.15 * n[..., None])
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2 - 4 * SS, fill=255)
    a = np.asarray(mask, np.float32) / 255.0
    img = to_img(np.dstack([np.clip(rgb, 0, 1), a]))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4 * SS, 4 * SS, W - 5 * SS, H - 5 * SS], radius=H // 2 - 8 * SS, outline=(242, 207, 126, 210), width=int(1.4 * SS))
    hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([7 * SS, 6 * SS, W - 8 * SS, H // 2], radius=H // 3, fill=(255, 210, 160, 26))
    img = Image.alpha_composite(img, hl)
    downsample(img).save(os.path.join(OUT, name))


def photo_frame(name="photo_frame.png", w=256, h=300, seed=81):
    """Old photograph border: cream deckled border, photo window transparent (9-slice 28/28/28/56)."""
    W, H = w * SS, h * SS
    paper = panel_paper(max(w, h), name="_tmp_p.png", seed=seed, tint="#efe4cc", edge_dark=0.18, deckle=False)
    big = paper.resize((W, H), Image.LANCZOS)
    a = np.asarray(big.split()[3], np.float32) / 255.0
    mask = Image.new("L", (W, H), 255)
    md = ImageDraw.Draw(mask)
    md.rectangle([22 * SS, 22 * SS, W - 22 * SS, H - 52 * SS], fill=0)
    a = a * (np.asarray(mask, np.float32) / 255.0)
    jag = value_noise(W, H, 4 * SS, seed + 3, 2, tile=False)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx, W - 1 - xx), np.minimum(yy, H - 1 - yy)) / SS
    a = a * np.clip((edge - 1.0 - jag * 3.0) / 1.0, 0, 1)
    big.putalpha(Image.fromarray((a * 255).astype(np.uint8)))
    downsample(big).save(os.path.join(OUT, name))
    os.remove(os.path.join(OUT, "_tmp_p.png"))


def map_paper(name="map_paper.png", size=1024, seed=91):
    panel_paper(size // 2, name="_tmp_m.png", seed=seed, tint="#eadbb8", edge_dark=0.35, deckle=False)
    img = Image.open(os.path.join(OUT, "_tmp_m.png")).resize((size, size), Image.LANCZOS)
    img.save(os.path.join(OUT, name))
    os.remove(os.path.join(OUT, "_tmp_m.png"))


def ink_wash(name="ink_wash.png", w=1024, h=512, seed=101):
    """Soft ink-wash cloud (menu backdrop overlay behind the button column)."""
    W, H = w, h
    n = value_noise(W, H, 160, seed, 5, tile=False)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = xx / W
    v = yy / H
    shape = np.clip(1.0 - u * 1.15, 0, 1) ** 1.2 * np.clip(1 - np.abs(v - 0.5) * 1.6, 0, 1) ** 0.6
    a = np.clip(shape * (0.75 + 0.5 * (n - 0.5)), 0, 1) * 0.85
    rgb = np.ones((H, W, 3), np.float32) * np.array(hexc("#0e0906")[:3])
    to_img(np.dstack([rgb, a])).save(os.path.join(OUT, name))


def lantern_sprite(name="lantern.png", w=96, h=160, seed=111):
    """Glowing red silk lantern (for 2D UI decoration: loading screen, splash)."""
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W / 2
    # tassel & cord
    d.line([(cx, 0), (cx, 22 * SS)], fill=(60, 30, 20, 255), width=int(2 * SS))
    # caps
    d.rounded_rectangle([cx - 20 * SS, 20 * SS, cx + 20 * SS, 30 * SS], radius=3 * SS, fill=(196, 150, 60, 255))
    d.rounded_rectangle([cx - 20 * SS, 122 * SS, cx + 20 * SS, 132 * SS], radius=3 * SS, fill=(196, 150, 60, 255))
    # body: radial gradient ellipse
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    by0, by1 = 26 * SS, 126 * SS
    bx = 42 * SS
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ex = (xx - cx) / bx
    ey = (yy - (by0 + by1) / 2) / ((by1 - by0) / 2)
    r = np.sqrt(ex ** 2 + ey ** 2)
    inside = np.clip((1 - r) / 0.02, 0, 1)
    core = np.clip(1 - r, 0, 1)
    c_edge = np.array(hexc("#8e1f12")[:3])
    c_mid = np.array(hexc("#e2502a")[:3])
    c_core = np.array(hexc("#ffd28a")[:3])
    t = core[..., None]
    rgb = c_edge * (1 - t) + c_mid * t
    rgb = rgb * (1 - t ** 3) + c_core * (t ** 3)
    # ribs
    ribs = 0.88 + 0.12 * np.cos(ex * math.pi * 3.0) ** 2
    rgb = rgb * ribs[..., None]
    body_arr = np.dstack([np.clip(rgb, 0, 1), inside])
    body = to_img(body_arr)
    img = Image.alpha_composite(body, img)
    d = ImageDraw.Draw(img)
    # tassel
    for i in range(7):
        x = cx - 6 * SS + i * 2 * SS
        d.line([(x, 132 * SS), (x + (i - 3) * 0.5 * SS, 156 * SS)], fill=(200, 40, 25, 230), width=int(1.4 * SS))
    downsample(img).save(os.path.join(OUT, name))


def toggle(name, on, w=76, h=40):
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    track = rgba8(hexc("#a8331d", 1.0)) if on else rgba8(hexc("#2a201a", 1.0))
    edge = rgba8(hexc("#f2cf7e", 0.9)) if on else rgba8(hexc("#8a6a32", 0.9))
    d.rounded_rectangle([2 * SS, 4 * SS, W - 2 * SS, H - 4 * SS], radius=(H - 8 * SS) // 2, fill=track, outline=edge, width=int(1.6 * SS))
    r = (H - 14 * SS) // 2
    cx = W - 2 * SS - 5 * SS - r if on else 2 * SS + 5 * SS + r
    cy = H // 2
    d.ellipse([cx - r, cy - r + SS, cx + r, cy + r + SS], fill=(0, 0, 0, 90))
    knob = rgba8(hexc("#f6e8c8", 1.0)) if on else rgba8(hexc("#b8a688", 1.0))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=knob, outline=rgba8(hexc("#2b1d14", 0.8)), width=SS)
    if on:
        paw_path(d, cx, cy + 2 * SS, r * 1.1, rgba8(hexc("#a8331d", 0.9)))
    downsample(img).save(os.path.join(OUT, name))


def grabber(name, hl, size=34):
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = W / 2
    r = W * 0.36
    d.ellipse([c - r + SS, c - r + 2 * SS, c + r + SS, c + r + 2 * SS], fill=(0, 0, 0, 100))
    fill = rgba8(hexc("#f2cf7e" if hl else "#d9a441", 1.0))
    d.ellipse([c - r, c - r, c + r, c + r], fill=fill, outline=rgba8(hexc("#2b1d14", 0.9)), width=int(1.5 * SS))
    r2 = r * 0.38
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=rgba8(hexc("#a8331d" if hl else "#7a4c18", 1.0)))
    downsample(img).save(os.path.join(OUT, name))


def checkbox(name, on, size=34):
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 3 * SS
    d.rounded_rectangle([m, m, W - m, W - m], radius=6 * SS, fill=rgba8(hexc("#a8331d" if on else "#241b15", 1.0)),
                        outline=rgba8(hexc("#f2cf7e" if on else "#8a6a32", 1.0)), width=int(1.6 * SS))
    if on:
        d.line([(W * 0.28, W * 0.52), (W * 0.44, W * 0.68), (W * 0.74, W * 0.32)], fill=rgba8(hexc("#f6e8c8")), width=int(3.2 * SS), joint="curve")
    downsample(img).save(os.path.join(OUT, name))


def radio(name, on, size=34):
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 3 * SS
    d.ellipse([m, m, W - m, W - m], fill=rgba8(hexc("#241b15", 1.0)), outline=rgba8(hexc("#f2cf7e" if on else "#8a6a32", 1.0)), width=int(1.6 * SS))
    if on:
        r = W * 0.2
        d.ellipse([W / 2 - r, W / 2 - r, W / 2 + r, W / 2 + r], fill=rgba8(hexc("#e2683a")))
    downsample(img).save(os.path.join(OUT, name))


def main():
    os.makedirs(OUT, exist_ok=True)
    panel_lacquer()
    panel_lacquer(size=128, margin=28, name="panel_lacquer_small.png", alpha=0.88, corners=False, seed=13)
    panel_paper()
    panel_paper(size=256, name="panel_paper_plain.png", seed=23, tint="#efe2c4", edge_dark=0.22, deckle=False)
    brush_highlight()
    brush_highlight(name="brush_highlight_red.png", seed=33, color="#c8452a")
    glow()
    glow(name="glow_sharp.png", size=128, power=4.0)
    bokeh()
    vignette()
    paper_grain()
    divider()
    seal_stamp()
    seal_stamp(name="seal_check.png", seed=53, glyph="check")
    slot_frame()
    nameplate()
    photo_frame()
    map_paper()
    ink_wash()
    lantern_sprite()
    toggle("toggle_on.png", True)
    toggle("toggle_off.png", False)
    grabber("grabber.png", False)
    grabber("grabber_hl.png", True)
    checkbox("check_on.png", True)
    checkbox("check_off.png", False)
    radio("radio_on.png", True)
    radio("radio_off.png", False)
    print("UI textures written to", OUT)
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".png"):
            print("  ", f, Image.open(os.path.join(OUT, f)).size)


if __name__ == "__main__":
    sys.exit(main())
