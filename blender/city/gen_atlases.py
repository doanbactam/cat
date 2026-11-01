#!/usr/bin/env python3
"""Atlases for the architecture kit (python3 + numpy + Pillow; fonts from the system).

Run: python3 blender/city/gen_atlases.py [--sheet]
Writes into assets/textures/architecture/:
  signs_a.jpg        2048x2048  16 horizontal shop signs (2 cols x 8 rows, 4:1), fictional names
  signs_v.png        1024x1024  vertical signs + small plates (RGBA)
  glass_interiors.jpg 2048x1024 8 window interiors behind glass (curtains, blinds, rooms)
  goods_atlas.jpg    1024x1024  16 shop-interior cells (shelves of goods, altar, rattan, ...)
  decals_grime.png   2048x2048  16 alpha decals (streaks, AC drips, moss, posters, ads, ...)
  foliage_atlas.png  1024x1024  4 alpha foliage cards (leafy, bougainvillea, fern, vine)
  laundry_atlas.png  1024x1024  16 garments (alpha) for laundry lines
  atlases.json       UV rectangles (u0, v0, u1, v1; v up) for every cell + names
All text and brands are fictional.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import city_texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "architecture")
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
F_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
F_SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
F_FREE_B = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
MANIFEST: dict = {}


def font(path, size):
    return ImageFont.truetype(path, size)


def fit_text(draw, text, path, box_w, box_h, squash_max=0.62):
    """Largest font size so text fits box (allowing horizontal condensing down to squash_max).
    Returns (font, squash)."""
    size = int(box_h)
    while size > 6:
        f = font(path, size)
        x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=f)
        w, h = x1 - x0, y1 - y0
        if h <= box_h:
            sq = min(1.0, box_w / max(w, 1))
            if sq >= squash_max:
                return f, sq
        size -= 2
    return font(path, 8), 1.0


def draw_text_condensed(img, xy_center, text, path, box_w, box_h, fill, stroke=0, stroke_fill=None,
                        shadow=None):
    """Draw text centred at xy_center, condensed horizontally to fit box_w (Vietnamese signs use
    condensed bold faces)."""
    tmp = ImageDraw.Draw(img)
    f, sq = fit_text(tmp, text, path, box_w, box_h)
    x0, y0, x1, y1 = tmp.textbbox((0, 0), text, font=f, stroke_width=stroke)
    w, h = x1 - x0 + 8, y1 - y0 + 8
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.text((4 - x0 + 3, 4 - y0 + 3), text, font=f, fill=shadow, stroke_width=stroke, stroke_fill=shadow)
    d.text((4 - x0, 4 - y0), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    nw = max(1, int(w * sq))
    layer = layer.resize((nw, h), Image.LANCZOS)
    cx, cy = xy_center
    img.alpha_composite(layer, (int(cx - nw / 2), int(cy - h / 2)))


def weather_rgba(img: Image.Image, seed: int, amount: float = 1.0, rust_holes=None) -> Image.Image:
    """Fade, dirt, streaks and scratches on a sign/poster image."""
    a = np.asarray(img.convert("RGBA"), np.float32) / 255.0
    h, w = a.shape[:2]
    rng = np.random.default_rng(seed)

    def noise(fmin, fmax, beta, aniso=(1, 1), s=0):
        n = max(h, w)
        nn = 1 << int(math.ceil(math.log2(n)))
        z = T.spectral(nn, seed + s, beta, fmin, fmax, aniso)
        return z[:h, :w]
    fade = T.smoothstep(-1.5, 2.0, noise(1, 8, 2.2, s=1)) * 0.25 * amount
    rgb = a[..., :3]
    lum = rgb.mean(-1, keepdims=True)
    rgb = rgb + (lum - rgb) * fade[..., None] * 0.8 + fade[..., None] * 0.08
    st = T.smoothstep(0.4, 2.4, noise(3, 60, 1.6, (1, 16), s=2)) * amount * 0.8
    dirt = T.smoothstep(0.0, 2.4, noise(1, 20, 2.0, s=3)) * amount
    rgb = rgb * (1 - 0.35 * st[..., None]) * (1 - 0.25 * dirt[..., None])
    rgb = rgb * np.array([1.0, 0.97, 0.9], np.float32) ** (st[..., None] + dirt[..., None])
    if rust_holes:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        for (hx, hy) in rust_holes:
            d = np.exp(-((xx - hx) ** 2) / (2 * 6 ** 2)) * np.clip((yy - hy) / (h * 0.5), 0, 1) ** 0.3 \
                * np.exp(-np.clip(yy - hy, 0, None) / (h * 0.5)) * (yy > hy)
            rgb = rgb * (1 - d[..., None] * 0.5) + d[..., None] * np.array([0.35, 0.18, 0.08]) * 0.5
    a[..., :3] = np.clip(rgb, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------------------
# Shop signs
# ---------------------------------------------------------------------------
SIGNS = [
    # id, main, sub, small, bg, fg, accent, style
    ("taphoa", "TẠP HÓA THU HƯƠNG", "Bánh kẹo · Nước giải khát · Đồ dùng gia đình", "Số 14 Hàng Mây  ·  ĐT 0912 345 678",
     "#b8231d", "#ffd23c", "#ffffff", "panel"),
    ("pho", "PHỞ BÒ GIA TRUYỀN", "Phở tái · Phở chín · Phở gà ta", "Số 27  ·  Mở cửa 6h - 22h", "#f1ead6", "#b01f1a",
     "#1d3f8f", "panel"),
    ("may_tre", "MÂY TRE ĐAN HÀNG MÂY", "Đồ mây tre · Thủ công mỹ nghệ · Bán buôn - bán lẻ", "Số 9 Hàng Mây",
     "#1f6b45", "#ffffff", "#f4d35e", "panel"),
    ("cat_toc", "CẮT TÓC NAM", "Gội đầu · Ráy tai · Cạo mặt", "Salon Tuấn Anh  ·  0987 654 321", "#1c4f9c", "#ffffff",
     "#ffe14a", "panel"),
    ("dien_thoai", "SỬA CHỮA ĐIỆN THOẠI", "Ép kính · Thay pin · Phụ kiện chính hãng", "Hùng Mobile  ·  0901 234 567",
     "#f5cc16", "#1c3e94", "#d4211b", "panel"),
    ("tra_da", "TRÀ ĐÁ · NƯỚC VỐI", "Chè xanh · Thuốc lào · Hướng dương", "Quán Cũ", "#25603a", "#fff4c2", "#ffffff",
     "panel"),
    ("thuoc", "QUẦY THUỐC PHÚC AN", "Thuốc tây · Thực phẩm chức năng · Dụng cụ y tế", "Số 31  ·  ĐT 0918 000 135",
     "#0f7d3f", "#ffffff", "#e8f3ea", "panel"),
    ("kim_khi", "ĐIỆN NƯỚC · KIM KHÍ HÒA BÌNH", "Ống nhựa · Dây điện · Ổ khóa · Sơn", "Số 52  ·  0913 579 246",
     "#2a5bb5", "#ffffff", "#ffd400", "panel"),
    ("banh_cuon", "BÁNH CUỐN NÓNG", "Bánh cuốn Thanh Trì · Chả quế", "Bà Lan", "#fff3d6", "#c0392b", "#2c3e50",
     "panel"),
    ("photo", "PHOTO · IN ẤN · ÉP PLASTIC", "Scan màu · In ảnh thẻ · Đóng quyển", "Số 6  ·  0936 112 233",
     "#ffffff", "#1b3c87", "#d61f26", "panel"),
    ("may_do", "MAY ĐO · SỬA QUẦN ÁO", "Áo dài · Vest · Đồng phục", "Cô Ngọc", "#7b1e3c", "#ffe9b0", "#ffffff",
     "panel"),
    ("ca_phe", "CÀ PHÊ PHỐ CŨ", "Cà phê trứng · Nâu đá · Bạc xỉu", "Since 1998", "#2b1d16", "#f2d6a2", "#c98d4b",
     "panel"),
    ("bun_cha", "BÚN CHẢ HÀNG MÂY", "Nem cua bể · Bún chả que tre", "Số 40", "#d9471f", "#ffffff", "#ffe08a",
     "panel"),
    ("vang_bac", "VÀNG BẠC KIM THÀNH", "Mua bán vàng bạc · Đá quý · Cầm đồ", "Số 18", "#a3121a", "#f7d270",
     "#ffffff", "panel"),
    ("nha_nghi", "NHÀ NGHỈ HOA MAI", "Phòng đẹp · Giá rẻ · Có điều hòa · Wifi", "ĐT 0988 246 810", "#e8e3d9",
     "#0f5ea8", "#c0392b", "panel"),
    ("gao", "GẠO · DẦU ĂN · NƯỚC MẮM", "Gạo tám thơm · Nếp cái hoa vàng", "Đại lý Minh Phát", "#f4f0e2", "#1f7a3a",
     "#c0392b", "panel"),
]


def make_sign(spec, w, h, seed):
    sid, main, sub, small, bg, fg, acc, _style = spec
    ss = 2
    W, H = w * ss, h * ss
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    # subtle panel gradient + border
    g = np.linspace(1.04, 0.92, H, dtype=np.float32)[:, None, None]
    arr = np.asarray(img, np.float32)
    arr[..., :3] = np.clip(arr[..., :3] * g, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    bw = int(H * 0.035)
    d.rectangle([bw, bw, W - bw - 1, H - bw - 1], outline=acc, width=max(2, bw // 2))
    draw_text_condensed(img, (W / 2, H * 0.36), main, F_BLACK, W * 0.9, H * 0.42, fg,
                        stroke=max(1, int(H * 0.008)), stroke_fill=fg, shadow=(0, 0, 0, 90))
    draw_text_condensed(img, (W / 2, H * 0.70), sub, F_BOLD, W * 0.86, H * 0.16, acc)
    draw_text_condensed(img, (W / 2, H * 0.87), small, F_SEMI, W * 0.7, H * 0.10, fg)
    img = img.resize((w, h), Image.LANCZOS)
    holes = [(w * 0.03, h * 0.08), (w * 0.97, h * 0.08)]
    return weather_rgba(img, seed, 0.9, holes)


def gen_signs():
    W, H = 2048, 2048
    atlas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    cells = {}
    for i, spec in enumerate(SIGNS):
        cx, cy = i % 2, i // 2
        im = make_sign(spec, 1024, 256, 900 + i)
        atlas.paste(im, (cx * 1024, cy * 256))
        cells[spec[0]] = [cx * 0.5, 1 - (cy + 1) / 8, (cx + 1) * 0.5, 1 - cy / 8]
    atlas.convert("RGB").save(os.path.join(OUT, "signs_a.jpg"), quality=90, subsampling=0)
    MANIFEST["signs_a"] = {"file": "signs_a.jpg", "aspect": 4.0, "cells": cells}


VSIGNS = [
    ("v_nha_nghi", "NHÀ NGHỈ", "#d6261e", "#ffffff"),
    ("v_cafe", "CÀ PHÊ", "#3b2418", "#f5d9a8"),
    ("v_may_tre", "MÂY TRE", "#1f6b45", "#fff2a8"),
    ("v_thuoc", "NHÀ THUỐC", "#0f7d3f", "#ffffff"),
    ("v_photo", "PHOTO", "#1b3c87", "#ffe14a"),
    ("v_vang", "VÀNG BẠC", "#a3121a", "#f7d270"),
]


def gen_vsigns():
    W, H = 1024, 1024
    atlas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cells = {}
    for i, (sid, txt, bg, fg) in enumerate(VSIGNS):
        w, h = 128, 512
        ss = 2
        im = Image.new("RGBA", (w * ss, h * ss), bg)
        d = ImageDraw.Draw(im)
        d.rectangle([6, 6, w * ss - 7, h * ss - 7], outline=fg, width=5)
        words = txt.split(" ")
        letters = [c for c in txt.replace(" ", "")]
        n = len(letters)
        for k, ch in enumerate(letters):
            cy = (k + 0.5) / n * (h * ss * 0.92) + h * ss * 0.04
            draw_text_condensed(im, (w * ss / 2, cy), ch, F_BLACK, w * ss * 0.8, h * ss * 0.92 / n * 0.8, fg)
        im = weather_rgba(im.resize((w, h), Image.LANCZOS), 1200 + i, 0.8)
        x, y = (i % 6) * 160 + 16, 0
        atlas.paste(im, (x, y))
        cells[sid] = [x / W, 1 - (y + h) / H, (x + w) / W, 1 - y / H]
    # house-number plates (Hanoi blue enamel plates) + small notices
    plates = [("no_%d" % n, "%d" % n) for n in (6, 9, 14, 18, 23, 27, 31, 40, 52, 61)]
    for i, (pid, num) in enumerate(plates):
        w, h = 160, 96
        im = Image.new("RGBA", (w * 2, h * 2), "#1d4fa0")
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([5, 5, w * 2 - 6, h * 2 - 6], radius=14, outline="#ffffff", width=6)
        draw_text_condensed(im, (w, h * 0.42), "SỐ", F_BOLD, w * 0.6, h * 0.3, "#ffffff")
        draw_text_condensed(im, (w, h * 1.25), num, F_BLACK, w * 1.4, h * 0.9, "#ffffff")
        im = weather_rgba(im.resize((w, h), Image.LANCZOS), 1300 + i, 0.6)
        x, y = (i % 5) * 200 + 12, 540 + (i // 5) * 110
        atlas.paste(im, (x, y))
        cells[pid] = [x / W, 1 - (y + h) / H, (x + w) / W, 1 - y / H]
    notices = [("cho_thue", "CHO THUÊ NHÀ", "LH: 0977 135 791", "#ffffff", "#c0392b"),
               ("ban_nha", "BÁN NHÀ", "Chính chủ · 0966 864 202", "#ffeb3b", "#1a1a1a"),
               ("cam_do_xe", "CẤM ĐỖ XE", "Trước cửa", "#ffffff", "#d0021b")]
    for i, (nid, t1, t2, bg, fg) in enumerate(notices):
        w, h = 300, 150
        im = Image.new("RGBA", (w * 2, h * 2), bg)
        d = ImageDraw.Draw(im)
        d.rectangle([4, 4, w * 2 - 5, h * 2 - 5], outline=fg, width=6)
        draw_text_condensed(im, (w, h * 0.75), t1, F_BLACK, w * 1.8, h * 0.8, fg)
        draw_text_condensed(im, (w, h * 1.5), t2, F_BOLD, w * 1.6, h * 0.36, fg)
        im = weather_rgba(im.resize((w, h), Image.LANCZOS), 1400 + i, 1.0)
        x, y = i * 330 + 12, 790
        atlas.paste(im, (x, y))
        cells[nid] = [x / W, 1 - (y + h) / H, (x + w) / W, 1 - y / H]
    atlas.save(os.path.join(OUT, "signs_v.png"), optimize=True)
    MANIFEST["signs_v"] = {"file": "signs_v.png", "cells": cells}


# ---------------------------------------------------------------------------
# Window interiors (seen through glass)
# ---------------------------------------------------------------------------
def gen_glass():
    W, H, C = 2048, 1024, 512
    atlas = np.zeros((H, W, 3), np.float32)
    rng = np.random.default_rng(77)
    yy, xx = np.mgrid[0:C, 0:C].astype(np.float32) / C
    cells = {}
    names = ["lace", "floral", "room_shelf", "blinds", "pink", "dark_room", "boxes", "green_curtain"]
    for i, nm in enumerate(names):
        room = T.lerp(np.array([0.06, 0.055, 0.05]), np.array([0.16, 0.14, 0.12]), (1 - yy) * 0.6)
        room = np.broadcast_to(room, (C, C, 3)).copy() if room.ndim == 1 else room
        room = room * (0.85 + 0.15 * T.fbm(C, 500 + i, 2, 30)[..., None])
        # ceiling light spot
        ls = np.exp(-(((xx - rng.uniform(0.3, 0.7)) ** 2) * 40 + ((yy - 0.12) ** 2) * 80))
        room += ls[..., None] * np.array([0.35, 0.33, 0.28]) * rng.uniform(0.3, 1.0)
        if nm in ("room_shelf", "boxes", "dark_room"):
            # silhouettes of furniture / shelves
            for k in range(rng.integers(3, 7)):
                x0, x1 = sorted(rng.uniform(0, 1, 2))
                y0 = rng.uniform(0.35, 0.8)
                m = (xx > x0) & (xx < x0 + (x1 - x0) * 0.6) & (yy > y0)
                room = np.where(m[..., None], room * 0.45 + np.array(rng.uniform(0.02, 0.12, 3)), room)
            if nm == "room_shelf":
                for k in range(4):
                    y = 0.3 + k * 0.13
                    m = (np.abs(yy - y) < 0.008) & (xx > 0.55) & (xx < 0.95)
                    room = np.where(m[..., None], np.array([0.25, 0.2, 0.15]), room)
                    for j in range(8):
                        bx = 0.56 + j * 0.048
                        mb = (xx > bx) & (xx < bx + 0.035) & (yy < y) & (yy > y - rng.uniform(0.05, 0.1))
                        room = np.where(mb[..., None], np.array(rng.uniform(0.05, 0.4, 3)), room)
        col = room
        if nm in ("lace", "floral", "pink", "green_curtain"):
            base = {"lace": [0.82, 0.8, 0.74], "floral": [0.7, 0.55, 0.45], "pink": [0.85, 0.55, 0.58],
                    "green_curtain": [0.35, 0.5, 0.35]}[nm]
            folds = 0.75 + 0.25 * np.sin(xx * 2 * math.pi * rng.uniform(9, 14) + T.fbm(C, 600 + i, 2, 8) * 3)
            cur = np.array(base) * folds[..., None]
            if nm == "lace":
                pat = (np.sin(xx * 140) * np.sin(yy * 140) > 0.3).astype(np.float32)
                cur = cur * (0.75 + 0.25 * pat[..., None])
                alpha = 0.55 + 0.25 * pat
            else:
                alpha = np.full((C, C), 0.95, np.float32)
            if nm == "floral":
                fl = T.smoothstep(0.62, 0.7, T.fbm(C, 700 + i, 18, 40))
                cur = T.lerp(cur, np.array([0.75, 0.25, 0.25]), fl * 0.8)
            # curtain drawn: covers left or right part, or both sides with gap
            gap = rng.uniform(0.15, 0.45)
            if rng.random() < 0.5:
                cover = (np.abs(xx - 0.5) > gap * 0.5).astype(np.float32)
            else:
                cover = (xx < 1 - gap).astype(np.float32)
            a = (alpha * cover)[..., None]
            col = col * (1 - a) + cur * a * 0.85
        if nm == "blinds":
            sl = 0.7 + 0.3 * (np.mod(yy * 38, 1.0) > 0.25)
            col = np.array([0.55, 0.6, 0.65]) * sl[..., None] * (0.85 + 0.15 * xx[..., None])
        if nm == "boxes":
            for k in range(10):
                x0, y0 = rng.uniform(0, 0.8), rng.uniform(0.4, 0.85)
                w, h = rng.uniform(0.1, 0.25), rng.uniform(0.08, 0.2)
                m = (xx > x0) & (xx < x0 + w) & (yy > y0) & (yy < y0 + h)
                col = np.where(m[..., None], np.array([0.42, 0.32, 0.2]) * rng.uniform(0.6, 1.1), col)
        # dirt on glass + window-frame vignette
        dirt = T.smoothstep(0.4, 0.9, T.fbm(C, 800 + i, 2, 20))
        col = col * (0.92 + 0.08 * dirt[..., None]) + dirt[..., None] * 0.03
        vig = (np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy)) * 8).clip(0, 1) ** 0.5
        col = col * (0.6 + 0.4 * vig[..., None])
        cx, cy = i % 4, i // 4
        atlas[cy * C:(cy + 1) * C, cx * C:(cx + 1) * C] = np.clip(col, 0.02, 0.9)
        cells[nm] = [cx / 4, 1 - (cy + 1) / 2, (cx + 1) / 4, 1 - cy / 2]
    T.save_rgb(os.path.join(OUT, "glass_interiors.jpg"), atlas, 90)
    MANIFEST["glass_interiors"] = {"file": "glass_interiors.jpg", "cells": cells}


# ---------------------------------------------------------------------------
# Shop goods / interior walls
# ---------------------------------------------------------------------------
BRANDS = ["SAO VÀNG", "BÌNH AN", "HOA SEN", "PHÚ QUÝ", "MAI ANH", "THU HÀ", "HẠNH PHÚC", "NAM VIỆT", "AN LẠC",
          "LỘC PHÁT", "TÂM ĐỨC", "HƯƠNG QUÊ"]
GOODS = ["MÌ GÓI", "BÁNH QUY", "NƯỚC MẮM", "TRÀ XANH", "CÀ PHÊ", "BỘT GIẶT", "DẦU ĂN", "SỮA ĐẶC", "KẸO LẠC", "MUỐI",
         "XÀ PHÒNG", "BÚN KHÔ"]


def _shade_rect(arr, x0, y0, x1, y1, col, rng, gloss=0.3, curved=False):
    """Fill a rectangle with a lit-from-above gradient (+ cylinder shading when curved)."""
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    yy = np.linspace(1.08, 0.82, y1 - y0)[:, None]
    xx = np.linspace(-1, 1, x1 - x0)[None, :]
    shade = yy * (1.0 - 0.35 * xx ** 2 if curved else 1.0 - 0.08 * np.abs(xx))
    c = np.array(col, np.float32)[None, None, :] / 255.0 * shade[..., None]
    if gloss > 0:
        hl = np.exp(-((xx + 0.45) / 0.12) ** 2) * gloss if curved else np.exp(-((yy - 1.08) / 0.03) ** 2) * gloss * 0.3
        c = c + hl[..., None] * 0.6 if np.ndim(hl) == 2 else c
    arr[y0:y1, x0:x1] = np.clip(c, 0, 1)


def _label(img, box, text, fg, bg=None, fnt=F_BOLD):
    x0, y0, x1, y1 = [int(v) for v in box]
    if x1 - x0 < 6 or y1 - y0 < 4:
        return
    d = ImageDraw.Draw(img)
    if bg is not None:
        d.rectangle([x0, y0, x1, y1], fill=bg)
    draw_text_condensed(img, ((x0 + x1) / 2, (y0 + y1) / 2), text, fnt, (x1 - x0) * 0.92, (y1 - y0) * 0.8, fg)


def gen_goods():
    W, C = 1024, 256
    rng = np.random.default_rng(55)
    base = np.zeros((W, W, 3), np.float32)
    overlays = []  # (cell_x, cell_y, callable(img_rgba_cell)) for text drawn after shading
    cells = {}
    kinds = ["grocery", "drinks", "noodles", "rattan", "fabric", "hardware", "phones", "kitchen",
             "altar", "wall_tile", "calendar_wall", "rattan_hats", "pharmacy", "snacks", "paint_cans", "dark_back"]
    pal_pack = [(196, 40, 36), (235, 190, 40), (30, 110, 190), (40, 150, 70), (240, 120, 30), (240, 236, 225),
                (120, 40, 120), (20, 60, 120), (200, 200, 60), (160, 30, 60)]
    texts = []
    for i, k in enumerate(kinds):
        cx, cy = i % 4, i // 4
        X0, Y0 = cx * C, cy * C
        cells[k] = [cx / 4, 1 - (cy + 1) / 4, (cx + 1) / 4, 1 - cy / 4]
        cell = base[Y0:Y0 + C, X0:X0 + C]
        # back wall of the shelf unit
        _shade_rect(cell, 0, 0, C, C, (70, 62, 52), rng, 0)
        if k in ("grocery", "noodles", "snacks", "pharmacy", "drinks", "paint_cans", "kitchen"):
            shelves = 4
            for sh_ in range(shelves):
                sy = int((sh_ + 1) * C / shelves) - 7
                top = int(sh_ * C / shelves) + 4
                x = 2
                while x < C - 8:
                    if k == "drinks":
                        bw = int(rng.integers(11, 17)); bh = int(rng.integers(34, min(56, sy - top)))
                        col = pal_pack[int(rng.integers(0, len(pal_pack)))]
                        _shade_rect(cell, x, sy - bh + 8, x + bw, sy, col, rng, 0.5, curved=True)
                        _shade_rect(cell, x + 3, sy - bh, x + bw - 3, sy - bh + 9, col, rng, 0.4, curved=True)
                        _shade_rect(cell, x + 4, sy - bh - 3, x + bw - 4, sy - bh + 1, (230, 230, 225), rng, 0.2)
                        _shade_rect(cell, x + 1, sy - bh * 0.55, x + bw - 1, sy - bh * 0.3, (245, 245, 240), rng, 0.2,
                                    curved=True)
                    elif k == "paint_cans":
                        bw = int(rng.integers(26, 36)); bh = int(rng.integers(30, min(46, sy - top)))
                        _shade_rect(cell, x, sy - bh, x + bw, sy, (205, 205, 210), rng, 0.6, curved=True)
                        col = tuple(int(v) for v in rng.integers(40, 240, 3))
                        _shade_rect(cell, x, sy - bh + 7, x + bw, sy - 9, col, rng, 0.3, curved=True)
                        texts.append((X0 + x, Y0 + sy - bh + 9, X0 + x + bw, Y0 + sy - 12, "SƠN", (255, 255, 255)))
                    elif k == "kitchen":
                        bw = int(rng.integers(30, 52)); bh = int(rng.integers(18, 34))
                        _shade_rect(cell, x, sy - bh, x + bw, sy, (175, 178, 180), rng, 0.8, curved=True)
                        _shade_rect(cell, x - 2, sy - bh - 3, x + bw + 2, sy - bh + 2, (200, 200, 205), rng, 0.5)
                    else:
                        bw = int(rng.integers(16, 34)); bh = int(rng.integers(24, min(56, sy - top)))
                        col = pal_pack[int(rng.integers(0, len(pal_pack)))]
                        if k == "pharmacy":
                            col = [(240, 240, 235), (235, 245, 240), (210, 230, 245), (250, 235, 235)][int(rng.integers(0, 4))]
                        bag = k in ("snacks", "noodles") and rng.random() < 0.7
                        _shade_rect(cell, x, sy - bh, x + bw, sy, col, rng, 0.35, curved=bag)
                        acc = pal_pack[int(rng.integers(0, len(pal_pack)))]
                        _shade_rect(cell, x + 2, sy - bh + bh * 0.15, x + bw - 2, sy - bh + bh * 0.4, acc, rng, 0.1)
                        if k == "pharmacy":
                            m = x + bw // 2
                            _shade_rect(cell, m - 2, sy - bh * 0.75, m + 2, sy - bh * 0.45, (30, 150, 70), rng, 0)
                            _shade_rect(cell, m - 6, sy - bh * 0.62, m + 6, sy - bh * 0.58, (30, 150, 70), rng, 0)
                        if bw > 20 and bh > 30:
                            texts.append((X0 + x + 2, Y0 + sy - bh + bh * 0.45, X0 + x + bw - 2, Y0 + sy - bh + bh * 0.7,
                                          GOODS[int(rng.integers(0, len(GOODS)))], (255, 255, 255)))
                    x += bw + int(rng.integers(1, 3))
                # shelf board with front edge + shadow under it
                _shade_rect(cell, 0, sy, C, sy + 7, (150, 135, 110), rng, 0.1)
                cell[sy + 7:min(C, sy + 14)] *= 0.55
                # price tags
                for q in range(int(rng.integers(2, 5))):
                    tx = int(rng.integers(4, C - 20))
                    _shade_rect(cell, tx, sy + 1, tx + 14, sy + 6, (250, 250, 240), rng, 0)
        elif k in ("hardware", "phones"):
            # pegboard with hanging items
            _shade_rect(cell, 0, 0, C, C, (150, 140, 120) if k == "hardware" else (235, 235, 232), rng, 0)
            for yy_ in range(6, C, 12):
                for xx_ in range(6, C, 12):
                    cell[yy_:yy_ + 2, xx_:xx_ + 2] *= 0.5
            for q in range(26):
                x, y = int(rng.integers(4, C - 40)), int(rng.integers(4, C - 60))
                if k == "phones":  # blister cards
                    col = pal_pack[int(rng.integers(0, len(pal_pack)))]
                    _shade_rect(cell, x, y, x + 28, y + 44, (245, 245, 245), rng, 0.2)
                    _shade_rect(cell, x + 3, y + 4, x + 25, y + 14, col, rng, 0.2)
                    _shade_rect(cell, x + 6, y + 18, x + 22, y + 38, (40, 40, 45), rng, 0.6, curved=True)
                else:
                    col = [(90, 90, 95), (200, 200, 205), (230, 120, 30), (40, 80, 160), (200, 40, 30)][q % 5]
                    if q % 3 == 0:
                        _shade_rect(cell, x, y, x + 8, y + 60, col, rng, 0.5, curved=True)
                    elif q % 3 == 1:
                        _shade_rect(cell, x, y, x + 34, y + 10, col, rng, 0.4, curved=True)
                        _shade_rect(cell, x + 26, y - 6, x + 34, y + 18, (60, 60, 60), rng, 0.4)
                    else:
                        _shade_rect(cell, x, y, x + 24, y + 30, col, rng, 0.3)
        elif k in ("rattan", "rattan_hats"):
            _shade_rect(cell, 0, 0, C, C, (78, 60, 40), rng, 0)
            yy, xx = np.mgrid[0:C, 0:C].astype(np.float32)
            for q in range(30):
                cx_, cy_ = rng.uniform(10, C - 10), rng.uniform(10, C - 10)
                r = rng.uniform(16, 40)
                if k == "rattan_hats":
                    tri = (yy - cy_ > -r) & (yy - cy_ < r * 0.4) & (np.abs(xx - cx_) < (yy - cy_ + r) * 0.9)
                    shade = 0.75 + 0.25 * (xx - cx_ + r) / (2 * r)
                    col = np.array([0.86, 0.79, 0.6]) * shade[..., None]
                    rings = 0.9 + 0.1 * np.sin((yy - cy_) * 1.2)
                    cell[tri] = (col * rings[..., None])[tri]
                else:
                    e = ((xx - cx_) / r) ** 2 + ((yy - cy_) / (r * 0.7)) ** 2 < 1
                    weave = 0.75 + 0.25 * (np.sin((xx + yy) * 0.9) * np.sin((xx - yy) * 0.9) > 0)
                    shade = 1.05 - 0.35 * (((xx - cx_) / r) ** 2 + ((yy - cy_) / (r * 0.7)) ** 2)
                    tone = np.array([0.72, 0.55, 0.32]) * rng.uniform(0.8, 1.1)
                    col = tone * (weave * shade)[..., None]
                    cell[e] = np.clip(col[e], 0, 1)
        elif k == "fabric":
            x = 0
            while x < C:
                bw = int(rng.integers(12, 26))
                col = tuple(int(v) for v in rng.integers(40, 240, 3))
                _shade_rect(cell, x, 8, x + bw, C - 8, col, rng, 0.25, curved=True)
                x += bw
        elif k == "altar":  # ban tho Than Tai: red altar cabinet with lights
            _shade_rect(cell, 0, 0, C, C, (55, 28, 20), rng, 0)
            _shade_rect(cell, 36, 96, C - 36, C - 16, (150, 26, 20), rng, 0.3)
            _shade_rect(cell, 48, 106, C - 48, 172, (205, 155, 45), rng, 0.4)
            for q in range(9):
                _shade_rect(cell, 50 + q * 18, 84, 58 + q * 18, 92, (255, 90, 70), rng, 0.8, curved=True)
            _shade_rect(cell, 100, 176, 156, 206, (215, 185, 80), rng, 0.6)
            _shade_rect(cell, 60, 116, 92, 160, (240, 200, 60), rng, 0.7, curved=True)
            _shade_rect(cell, C - 92, 116, C - 60, 160, (240, 200, 60), rng, 0.7, curved=True)
        elif k == "wall_tile":
            for yy_ in range(0, C, 32):
                for xx_ in range(0, C, 32):
                    v = int(rng.integers(200, 228))
                    _shade_rect(cell, xx_ + 1, yy_ + 1, xx_ + 31, yy_ + 31, (v, v - 4, v - 12), rng, 0.2)
        elif k == "calendar_wall":
            _shade_rect(cell, 0, 0, C, C, (190, 180, 155), rng, 0)
            _shade_rect(cell, 30, 30, 120, 160, (205, 38, 34), rng, 0.2)
            _shade_rect(cell, 36, 40, 114, 110, (240, 220, 170), rng, 0.1)
            _shade_rect(cell, 150, 50, 220, 140, (60, 120, 170), rng, 0.2)
            _shade_rect(cell, 150, 170, 215, 225, (240, 240, 235), rng, 0.3, curved=True)
            texts.append((X0 + 36, Y0 + 112, X0 + 114, Y0 + 150, "2026", (255, 230, 120)))
        else:
            _shade_rect(cell, 0, 0, C, C, (22, 20, 18), rng, 0)
    grime = T.fbm(W, 66, 4, 60)[..., None]
    noise = T.spectral(W, 67, 0.5, 100)[..., None] * 0.02
    base = np.clip(base * (0.82 + 0.18 * grime) + noise, 0, 1)
    img = Image.fromarray((base * 255).astype(np.uint8), "RGB").convert("RGBA")
    for (x0, y0, x1, y1, t, col) in texts:
        _label(img, (x0, y0, x1, y1), t, col + (230,), None, F_BLACK)
    img = img.convert("RGB").filter(ImageFilter.GaussianBlur(0.5))
    img.save(os.path.join(OUT, "goods_atlas.jpg"), quality=90)
    MANIFEST["goods_atlas"] = {"file": "goods_atlas.jpg", "cells": cells}


# ---------------------------------------------------------------------------
# Grime decals (RGBA, alpha blended over walls)
# ---------------------------------------------------------------------------
def gen_decals():
    S, C = 2048, 512
    out = np.zeros((S, S, 4), np.float32)
    yy, xx = np.mgrid[0:C, 0:C].astype(np.float32) / C
    cells = {}

    def put(i, name, rgb, a):
        cx, cy = i % 4, i // 4
        out[cy * C:(cy + 1) * C, cx * C:(cx + 1) * C, :3] = np.clip(rgb, 0, 1)
        out[cy * C:(cy + 1) * C, cx * C:(cx + 1) * C, 3] = np.clip(a, 0, 1)
        cells[name] = [cx / 4, 1 - (cy + 1) / 4, (cx + 1) / 4, 1 - cy / 4]

    def edge_fade(px=0.06):
        e = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
        return T.smoothstep(0.0, px, e)
    n1 = lambda s, a=1.0, b=40, beta=2.0, an=(1, 1): T.spectral(C, s, beta, a, b, an)
    # 0-2: streaks below sills / ledges (top edge = source)
    for k in range(3):
        st = T.smoothstep(-0.6, 2.0, n1(10 + k, 3, 70, 1.6, (1, 22)) + 0.4)
        prof = np.exp(-((xx - 0.5) / (0.22 + 0.08 * k)) ** 4)
        fall = np.clip(1 - yy, 0, 1) ** (1.2 + k * 0.4)
        a = st * prof * fall * (0.55 + 0.15 * k) + np.exp(-(yy / 0.05)) * prof * 0.4
        rgb = np.broadcast_to(np.array([0.18, 0.16, 0.13]), (C, C, 3)).copy()
        rgb = rgb * (0.8 + 0.4 * T.fbm(C, 20 + k, 4, 60)[..., None])
        put(k, f"streak_{k}", rgb, a * edge_fade(0.03))
    # 3: AC drip / rust stain (narrow, orange-brown core)
    core = np.exp(-((xx - 0.5) / 0.08) ** 2) * np.clip(1 - yy, 0, 1) ** 0.8
    wide = np.exp(-((xx - 0.5) / 0.25) ** 2) * np.clip(1 - yy, 0, 1) ** 2
    st = T.smoothstep(-0.5, 2.0, n1(30, 3, 70, 1.6, (1, 20)) + 0.8)
    a = np.clip(core * 0.7 + wide * 0.35, 0, 1) * st
    rgb = T.lerp(np.array([0.2, 0.18, 0.15]), np.array([0.33, 0.2, 0.1]), core)
    put(3, "ac_drip", np.broadcast_to(rgb, (C, C, 3)) if rgb.ndim == 1 else rgb, a * edge_fade(0.03))
    # 4: water stain with tide marks
    r = np.sqrt((xx - 0.5) ** 2 + ((yy - 0.45) * 1.2) ** 2) + n1(40, 2, 30) * 0.04
    tide = (np.exp(-((r - 0.38) / 0.012) ** 2) * 0.5 + np.exp(-((r - 0.3) / 0.01) ** 2) * 0.35
            + np.exp(-((r - 0.22) / 0.01) ** 2) * 0.25)
    a = np.clip((r < 0.38) * 0.25 + tide, 0, 1) * T.smoothstep(-1, 1.5, n1(41, 2, 40))
    put(4, "water_stain", np.broadcast_to(np.array([0.3, 0.27, 0.2]), (C, C, 3)), a * edge_fade())
    # 5: moss / algae band at wall base (bottom edge = ground)
    hgt = 0.35 + n1(50, 1, 20) * 0.12
    m = T.smoothstep(0.0, 0.25, hgt - (1 - yy)) * T.smoothstep(-1.2, 1.0, n1(51, 3, 80))
    rgb = T.lerp(np.array([0.12, 0.16, 0.08]), np.array([0.28, 0.33, 0.14]),
                 T.fbm(C, 52, 6, 120))
    put(5, "moss_base", rgb, np.clip(m * 0.9, 0, 1) * T.smoothstep(0, 0.05, np.minimum(xx, 1 - xx)))
    # 6: splash dirt band (ground splash, darker, speckled)
    hgt = 0.45 + n1(60, 1, 20) * 0.1
    m = T.smoothstep(0.0, 0.35, hgt - (1 - yy)) * (0.6 + 0.4 * T.fbm(C, 61, 30, 250))
    put(6, "splash_base", np.broadcast_to(np.array([0.2, 0.18, 0.15]), (C, C, 3)),
        m * 0.75 * T.smoothstep(0, 0.05, np.minimum(xx, 1 - xx)))
    # 7: black mould corner / soot under eaves (top edge source)
    m = T.smoothstep(-0.2, 1.6, n1(70, 2, 60) + (1 - yy) * 2.2 - 1.0)
    put(7, "soot_top", np.broadcast_to(np.array([0.09, 0.09, 0.08]), (C, C, 3)), m * 0.8 * edge_fade(0.08))
    # 8: peeling paint flake area (light under-layer with darker rim)
    pf = T.fbm(C, 80, 2, 25) - np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2) * 0.5
    pn = T.smoothstep(0.42, 0.46, pf)
    rim = np.clip(T.smoothstep(0.38, 0.42, pf) - pn, 0, 1)
    rgb = np.broadcast_to(np.array([0.78, 0.74, 0.66]), (C, C, 3)).copy()
    rgb = T.lerp(rgb, np.array([0.3, 0.28, 0.25]), rim)
    put(8, "peel_patch", rgb, np.clip(pn * 0.95 + rim * 0.7, 0, 1) * edge_fade(0.15))
    # 9: rust streak from bolt
    core = np.exp(-((xx - 0.5) / 0.05) ** 2) * np.clip(1 - yy * 1.1, 0, 1) ** 1.5
    put(9, "rust_streak", np.broadcast_to(np.array([0.38, 0.19, 0.08]), (C, C, 3)),
        core * T.smoothstep(-0.5, 1.5, n1(90, 2, 200, 1.0, (1, 6)) + 0.5) * 0.85)
    # 10-11: torn poster remnants (paper with faint text)
    for k in range(2):
        im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pc = [(236, 232, 214), (245, 214, 90)][k]
        d.rectangle([60, 50, C - 60, C - 60], fill=pc + (255,))
        tf = font(F_BLACK, 54)
        d.text((80, 70), ["HỌC THÊM", "TUYỂN NV"][k], font=tf, fill=(180, 30, 30, 255))
        bf = font(F_BOLD, 26)
        for q in range(6):
            d.text((80, 160 + q * 40), ["Toán · Lý · Hóa  lớp 6-12", "Bán hàng · Ca sáng",
                                        "Giáo viên nhiều kinh nghiệm", "Lương thỏa thuận",
                                        "LH: 0904 123 789", "Gặp chị Hà"][q], font=bf, fill=(30, 30, 30, 255))
        a = np.asarray(im, np.float32) / 255
        dctr = np.maximum(np.abs(yy - 0.5), np.abs(xx - 0.5))
        tear = T.smoothstep(0.0, 0.03, dctr - 0.30 + (T.fbm(C, 100 + k, 3, 50) - 0.5) * 0.35)
        tear = np.maximum(tear, T.smoothstep(0.72, 0.76, T.fbm(C, 110 + k, 2, 30)))
        a[..., 3] *= 1 - tear
        rgb = a[..., :3] * (0.75 + 0.25 * T.fbm(C, 102 + k, 4, 80)[..., None])
        st = T.smoothstep(0.0, 2.0, n1(104 + k, 3, 70, 1.6, (1, 20)))
        rgb = rgb * (1 - 0.35 * st[..., None])
        put(10 + k, f"poster_{k}", rgb, a[..., 3] * 0.92)
    # 12: stencil ad "KHOAN CAT BE TONG" (ubiquitous wall ads) - fictional number
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    draw_text_condensed(im, (C / 2, C * 0.32), "KHOAN CẮT", F_BLACK, C * 0.9, C * 0.2, (20, 20, 20, 255))
    draw_text_condensed(im, (C / 2, C * 0.52), "BÊ TÔNG", F_BLACK, C * 0.9, C * 0.2, (20, 20, 20, 255))
    draw_text_condensed(im, (C / 2, C * 0.72), "0912.345.678", F_BLACK, C * 0.9, C * 0.16, (180, 20, 20, 255))
    a = np.asarray(im, np.float32) / 255
    a[..., 3] *= 0.85 * (0.7 + 0.3 * T.fbm(C, 120, 10, 200))
    put(12, "ad_stencil", a[..., :3], a[..., 3])
    # 13: "CAM DO RAC" hand painted (no dumping) red
    im = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    draw_text_condensed(im, (C / 2, C * 0.4), "CẤM ĐỔ RÁC", F_FREE_B, C * 0.92, C * 0.22, (170, 25, 20, 255))
    draw_text_condensed(im, (C / 2, C * 0.62), "Phạt 500.000đ", F_BOLD, C * 0.7, C * 0.12, (170, 25, 20, 255))
    a = np.asarray(im, np.float32) / 255
    a[..., 3] *= 0.8 * (0.6 + 0.4 * T.fbm(C, 130, 10, 200))
    put(13, "no_dumping", a[..., :3], a[..., 3])
    # 14: crack with dirt halo
    cr = T.crack_mask(C, 140, 3, (150, 400), 2.0, 0.6)
    halo = T.blur(cr, 6) * 2.5
    put(14, "crack", np.broadcast_to(np.array([0.15, 0.13, 0.11]), (C, C, 3)),
        np.clip(cr * 0.9 + halo * 0.3, 0, 1) * edge_fade(0.1))
    # 15: patched plaster square (fresh cement patch)
    m = T.smoothstep(0.0, 0.02, 0.38 - np.maximum(np.abs(xx - 0.5), np.abs(yy - 0.5) * 1.3)
                     + n1(150, 3, 60) * 0.03)
    rgb = np.broadcast_to(np.array([0.6, 0.58, 0.54]), (C, C, 3)) * (0.9 + 0.1 * T.fbm(C, 151, 8, 200)[..., None])
    put(15, "cement_patch", rgb, m * 0.95)
    T.save_rgba(os.path.join(OUT, "decals_grime.png"), out)
    MANIFEST["decals_grime"] = {"file": "decals_grime.png", "cells": cells}


# ---------------------------------------------------------------------------
# Foliage cards
# ---------------------------------------------------------------------------
def _leaf(d, cx, cy, ang, L, W, col, vein=None):
    pts = []
    for t in np.linspace(0, 1, 14):
        w = W * math.sin(math.pi * t) ** 0.8
        pts.append((t * L, w))
    pts += [(t * L, -W * math.sin(math.pi * t) ** 0.8) for t in np.linspace(1, 0, 14)]
    ca, sa = math.cos(ang), math.sin(ang)
    P = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
    d.polygon(P, fill=col)
    if vein:
        d.line([(cx, cy), (cx + L * 0.9 * ca, cy + L * 0.9 * sa)], fill=vein, width=1)


def gen_foliage():
    S, C = 1024, 512
    rng = np.random.default_rng(31)
    atlas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cells = {}

    def shade(base, k):
        f = rng.uniform(0.6, 1.15)
        return tuple(int(min(255, v * f)) for v in base) + (255,)
    # 0 leafy plant (pothos/money plant) - stems from bottom centre
    im = Image.new("RGBA", (C * 2, C * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for s_ in range(16):
        ang0 = -math.pi / 2 + rng.normal(0, 0.55)
        L = rng.uniform(0.45, 0.85) * C * 1.8
        pts = [(C + math.cos(ang0 + t * t * 0.5 * (1 if ang0 > -math.pi / 2 else -1)) * L * t,
                C * 2 - 10 + math.sin(ang0 + t * t * 0.5 * (1 if ang0 > -math.pi / 2 else -1)) * L * t)
               for t in np.linspace(0, 1, 20)]
        d.line(pts, fill=(70, 110, 45, 255), width=5)
        for j in range(3, 20, 2):
            x, y = pts[j]
            side = 1 if j % 4 == 1 else -1
            _leaf(d, x, y, ang0 + side * rng.uniform(0.5, 1.2), rng.uniform(45, 80) * (1.2 - j / 30),
                  rng.uniform(20, 34) * (1.2 - j / 30), shade((62, 120, 48), j), (110, 160, 80, 255))
    atlas.paste(im.resize((C, C), Image.LANCZOS), (0, 0))
    cells["leafy"] = [0, 0.5, 0.5, 1.0]
    # 1 bougainvillea: dense leaves + magenta bract clusters, arching spray
    im = Image.new("RGBA", (C * 2, C * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(260):
        x, y = rng.uniform(80, C * 2 - 80), rng.uniform(80, C * 2 - 60)
        if (x - C) ** 2 / (C * 0.95) ** 2 + (y - C) ** 2 / (C * 0.9) ** 2 > 1:
            continue
        _leaf(d, x, y, rng.uniform(0, 6.28), rng.uniform(26, 42), rng.uniform(11, 17), shade((52, 105, 40), k))
    for k in range(170):
        x, y = rng.uniform(80, C * 2 - 80), rng.uniform(80, C * 2 - 80)
        if (x - C) ** 2 / (C * 0.9) ** 2 + (y - C) ** 2 / (C * 0.85) ** 2 > 1:
            continue
        base = [(214, 38, 128), (196, 30, 112), (230, 70, 150), (180, 24, 98)][k % 4]
        for q in range(3):
            a = rng.uniform(0, 6.28)
            _leaf(d, x, y, a + q * 2.1, rng.uniform(20, 30), rng.uniform(12, 16), shade(base, k))
        d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(245, 240, 220, 255))
    atlas.paste(im.resize((C, C), Image.LANCZOS), (C, 0))
    cells["bougainvillea"] = [0.5, 0.5, 1.0, 1.0]
    # 2 fern / areca frond
    im = Image.new("RGBA", (C * 2, C * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(9):
        ang = -math.pi / 2 + (k - 4) * 0.28 + rng.normal(0, 0.05)
        L = rng.uniform(0.7, 0.95) * C * 1.9
        x0, y0 = C, C * 2 - 8
        pts = []
        for t in np.linspace(0, 1, 30):
            bend = t * t * 0.6 * (1 if ang > -math.pi / 2 else -1)
            pts.append((x0 + math.cos(ang + bend) * L * t, y0 + math.sin(ang + bend) * L * t))
        d.line(pts, fill=(80, 110, 50, 255), width=4)
        for j in range(4, 30):
            px, py = pts[j]
            tx, ty = pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]
            ta = math.atan2(ty, tx)
            ll = (1 - j / 30) * 70 + 20
            for s in (-1, 1):
                _leaf(d, px, py, ta + s * 1.1, ll, 6, shade((70, 128, 52), j))
    atlas.paste(im.resize((C, C), Image.LANCZOS), (0, C))
    cells["fern"] = [0, 0, 0.5, 0.5]
    # 3 trailing vine (hangs down from top edge)
    im = Image.new("RGBA", (C * 2, C * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for k in range(9):
        x = rng.uniform(80, C * 2 - 80)
        L = rng.uniform(0.5, 1.0) * C * 1.9
        pts = [(x + math.sin(t * 7 + k) * 25, 6 + t * L) for t in np.linspace(0, 1, 40)]
        d.line(pts, fill=(70, 90, 40, 255), width=3)
        for j in range(1, 40, 2):
            px, py = pts[j]
            _leaf(d, px, py, math.pi / 2 + rng.normal(0, 0.8) + (0.8 if j % 4 else -0.8),
                  rng.uniform(26, 40), rng.uniform(12, 18), shade((58, 118, 44), j))
    atlas.paste(im.resize((C, C), Image.LANCZOS), (C, C))
    cells["vine"] = [0.5, 0, 1.0, 0.5]
    a = np.asarray(atlas, np.float32) / 255
    a[..., :3] *= (0.8 + 0.3 * T.fbm(S, 33, 6, 120))[..., None]
    # bleed colour into transparent pixels (avoids dark fringes with mipmaps)
    rgb, al = a[..., :3], a[..., 3:4]
    bl = T.blur(rgb * al, 4) / np.maximum(T.blur(al, 4), 1e-3)
    a[..., :3] = np.where(al > 0.5, rgb, bl)
    T.save_rgba(os.path.join(OUT, "foliage_atlas.png"), a)
    MANIFEST["foliage_atlas"] = {"file": "foliage_atlas.png", "cells": cells}


# ---------------------------------------------------------------------------
# Laundry garments
# ---------------------------------------------------------------------------
def gen_laundry():
    S, C = 1024, 256
    rng = np.random.default_rng(41)
    atlas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cells = {}
    kinds = ["tshirt", "shirt", "trousers", "towel", "dress", "shorts", "tshirt", "towel",
             "pyjama", "tshirt", "sock_pair", "shirt", "towel", "trousers", "tank", "baby"]
    palette = [(200, 40, 40), (40, 90, 180), (240, 240, 235), (250, 200, 60), (80, 150, 90), (230, 120, 160),
               (60, 60, 70), (120, 80, 160), (250, 140, 40), (90, 180, 200), (180, 160, 120), (30, 40, 90)]
    for i, k in enumerate(kinds):
        im = Image.new("RGBA", (C * 2, C * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        col = palette[int(rng.integers(0, len(palette)))] + (255,)
        W2 = C * 2
        if k in ("tshirt", "tank", "baby", "pyjama"):
            sl = 0 if k == "tank" else 1
            body = [(W2 * 0.3, 20), (W2 * 0.7, 20), (W2 * 0.7, W2 - 30), (W2 * 0.3, W2 - 30)]
            d.polygon(body, fill=col)
            if sl:
                d.polygon([(W2 * 0.3, 20), (W2 * 0.12, W2 * 0.3), (W2 * 0.3, W2 * 0.38)], fill=col)
                d.polygon([(W2 * 0.7, 20), (W2 * 0.88, W2 * 0.3), (W2 * 0.7, W2 * 0.38)], fill=col)
            d.ellipse([W2 * 0.42, 6, W2 * 0.58, 50], fill=(0, 0, 0, 0))
            if k == "pyjama" or rng.random() < 0.4:
                for q in range(0, W2, 26):
                    d.line([(W2 * 0.3, q), (W2 * 0.7, q)], fill=tuple(min(255, v + 60) for v in col[:3]) + (255,), width=6)
        elif k == "shirt":
            d.polygon([(W2 * 0.28, 20), (W2 * 0.72, 20), (W2 * 0.74, W2 - 20), (W2 * 0.26, W2 - 20)], fill=col)
            d.polygon([(W2 * 0.28, 20), (W2 * 0.06, W2 * 0.55), (W2 * 0.16, W2 * 0.58), (W2 * 0.3, W2 * 0.3)], fill=col)
            d.polygon([(W2 * 0.72, 20), (W2 * 0.94, W2 * 0.55), (W2 * 0.84, W2 * 0.58), (W2 * 0.7, W2 * 0.3)], fill=col)
            d.line([(W2 * 0.5, 30), (W2 * 0.5, W2 - 20)], fill=(30, 30, 30, 120), width=2)
            for q in range(5):
                d.ellipse([W2 * 0.5 - 4, 60 + q * 80, W2 * 0.5 + 4, 68 + q * 80], fill=(240, 240, 240, 255))
            if rng.random() < 0.5:
                for q in range(0, W2, 18):
                    d.line([(q, 0), (q, W2)], fill=(255, 255, 255, 70), width=3)
        elif k in ("trousers", "shorts"):
            Lg = W2 - 20 if k == "trousers" else W2 * 0.5
            d.polygon([(W2 * 0.25, 10), (W2 * 0.75, 10), (W2 * 0.78, Lg), (W2 * 0.53, Lg), (W2 * 0.5, W2 * 0.3),
                       (W2 * 0.47, Lg), (W2 * 0.22, Lg)], fill=col)
            d.rectangle([W2 * 0.25, 10, W2 * 0.75, 40], fill=tuple(max(0, v - 40) for v in col[:3]) + (255,))
        elif k == "towel":
            d.rectangle([W2 * 0.2, 10, W2 * 0.8, W2 - 10], fill=col)
            for q in (60, W2 - 70):
                d.rectangle([W2 * 0.2, q, W2 * 0.8, q + 20], fill=(250, 250, 250, 255))
        elif k == "dress":
            d.polygon([(W2 * 0.36, 10), (W2 * 0.64, 10), (W2 * 0.68, W2 * 0.35), (W2 * 0.86, W2 - 10),
                       (W2 * 0.14, W2 - 10), (W2 * 0.32, W2 * 0.35)], fill=col)
            for q in range(30):
                x, y = rng.uniform(W2 * 0.2, W2 * 0.8), rng.uniform(W2 * 0.3, W2 - 20)
                d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 255, 255, 200))
        elif k == "sock_pair":
            for s in (0.32, 0.62):
                d.polygon([(W2 * s, 10), (W2 * (s + 0.1), 10), (W2 * (s + 0.1), W2 * 0.7), (W2 * (s + 0.2), W2 * 0.85),
                           (W2 * (s + 0.12), W2 * 0.92), (W2 * s, W2 * 0.75)], fill=col)
        im = im.resize((C, C), Image.LANCZOS)
        a = np.asarray(im, np.float32) / 255
        folds = 0.8 + 0.2 * np.sin(np.mgrid[0:C, 0:C][1] / C * math.pi * rng.uniform(4, 9)
                                    + T.fbm(C, 400 + i, 2, 10) * 4)
        a[..., :3] *= folds[..., None]
        al = a[..., 3:4]
        bl = T.blur(a[..., :3] * al, 3) / np.maximum(T.blur(al, 3), 1e-3)
        a[..., :3] = np.where(al > 0.5, a[..., :3], bl)
        cx, cy = i % 4, i // 4
        atlas.paste(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA"), (cx * C, cy * C))
        cells[f"g{i}_{k}"] = [cx / 4, 1 - (cy + 1) / 4, (cx + 1) / 4, 1 - cy / 4]
    atlas.save(os.path.join(OUT, "laundry_atlas.png"), optimize=True)
    MANIFEST["laundry_atlas"] = {"file": "laundry_atlas.png", "cells": cells}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    for f in (gen_signs, gen_vsigns, gen_glass, gen_goods, gen_decals, gen_foliage, gen_laundry):
        f()
        print("done", f.__name__)
    with open(os.path.join(OUT, "atlases.json"), "w") as fh:
        json.dump(MANIFEST, fh, indent=1, ensure_ascii=False)
    if a.sheet:
        q = os.path.join(ROOT, "qa", "out", "city-houses")
        for nm in ("signs_a.jpg", "signs_v.png", "glass_interiors.jpg", "goods_atlas.jpg", "decals_grime.png",
                   "foliage_atlas.png", "laundry_atlas.png"):
            im = Image.open(os.path.join(OUT, nm))
            if im.mode == "RGBA":
                bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
                bg.alpha_composite(im)
                im = bg
            im.convert("RGB").resize((im.width // 2, im.height // 2)).save(os.path.join(q, "atlas_" + nm.split(".")[0] + ".jpg"))


if __name__ == "__main__":
    main()
