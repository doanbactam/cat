"""Label / print sheets for the street-props kit (system python3 + Pillow; run before build_props.py).

Every sheet is an RGBA PNG in blender/props/labels/. The Blender builders project faces onto
rectangles of these sheets through the "LabelUV" layer (u right, v UP: rect (u0, v0, u1, v1);
Pillow y grows down, so a rect maps to pixel rows (1-v1)*H .. (1-v0)*H). Alpha = printed area.
All brand names, shops and numbers are fictional.

  python3 blender/props/gen_labels.py [--only name1,name2] [--sheet]
"""
from __future__ import annotations

import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "labels")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FONTS = {
    "black": "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "xbold": "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "bold": "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "semi": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "reg": "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "disp": "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "dispb": "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
    "bvp": os.path.join(ROOT, "assets/fonts/BeVietnamPro-700.ttf"),
    "bvp6": os.path.join(ROOT, "assets/fonts/BeVietnamPro-600.ttf"),
    "serif": os.path.join(ROOT, "assets/fonts/PlayfairDisplay-700.ttf"),
    "serif6": os.path.join(ROOT, "assets/fonts/PlayfairDisplay-600.ttf"),
    "lora_i": os.path.join(ROOT, "assets/fonts/Lora-400i.ttf"),
    "lora": os.path.join(ROOT, "assets/fonts/Lora-600.ttf"),
    "cjk": "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
}
RNG = random.Random(7)


def font(kind, size):
    p = FONTS[kind]
    if not os.path.exists(p):
        p = FONTS["bold"]
    return ImageFont.truetype(p, int(size))


def new(w, h, bg=None):
    return Image.new("RGBA", (w, h), bg if bg else (0, 0, 0, 0))


def rect_px(img, rect):
    """(u0, v0, u1, v1) -> pixel box (x0, y0, x1, y1)."""
    W, H = img.size
    u0, v0, u1, v1 = rect
    return (int(u0 * W), int((1 - v1) * H), int(u1 * W), int((1 - v0) * H))


def text_fit(draw, box, txt, kind="black", fill=(255, 255, 255, 255), max_size=400, align="center",
             valign="center", stroke=0, stroke_fill=None, spacing=0.0, squeeze=1.0, img=None):
    """Draw `txt` as large as fits into box; squeeze < 1 condenses horizontally (via resize)."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    size = max_size
    while size > 6:
        f = font(kind, size)
        l, t, r, b = draw.textbbox((0, 0), txt, font=f, stroke_width=stroke)
        if (r - l) * squeeze <= bw and (b - t) <= bh:
            break
        size = int(size * 0.94)
    f = font(kind, size)
    l, t, r, b = draw.textbbox((0, 0), txt, font=f, stroke_width=stroke)
    tw, th = r - l, b - t
    if squeeze != 1.0 and img is not None:
        tmp = new(tw + 8, th + 8)
        td = ImageDraw.Draw(tmp)
        td.text((4 - l, 4 - t), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        tmp = tmp.resize((max(1, int((tw + 8) * squeeze)), th + 8), Image.LANCZOS)
        tw2 = tmp.size[0]
        x = x0 + (bw - tw2) // 2 if align == "center" else (x0 if align == "left" else x1 - tw2)
        y = y0 + (bh - th) // 2 - 4 if valign == "center" else y0
        img.alpha_composite(tmp, (int(x), int(y)))
        return size
    x = x0 + (bw - tw) // 2 - l if align == "center" else (x0 - l if align == "left" else x1 - tw - l)
    y = y0 + (bh - th) // 2 - t if valign == "center" else y0 - t
    draw.text((x, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return size


def noise(w, h, scale=32, octaves=4, seed=0):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    amp = 1.0
    tot = 0.0
    s = scale
    for _ in range(octaves):
        gh, gw = max(2, h // s + 2), max(2, w // s + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += np.asarray(im, np.float32) / 255.0 * amp
        tot += amp
        amp *= 0.5
        s = max(1, s // 2)
    return acc / tot


def weather(img, fade=0.12, grime=0.15, speckle=0.04, seed=1):
    """Ink fade, dirt tint and tiny speckle losses on the printed layer (alpha kept)."""
    a = np.asarray(img, np.float32) / 255.0
    h, w = a.shape[:2]
    n = noise(w, h, 64, 5, seed)
    n2 = noise(w, h, 8, 3, seed + 1)
    rgb = a[..., :3]
    lum = rgb.mean(axis=2, keepdims=True)
    rgb = rgb * (1 - fade) + (lum * 0.5 + 0.5) * fade * (0.6 + 0.4 * n[..., None])
    rgb = rgb * (1 - grime * n[..., None] ** 2)
    alpha = a[..., 3] * (1 - (n2 > 1 - speckle) * 0.9)
    out = np.dstack([rgb, alpha])
    return Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8), "RGBA")


def save(img, name):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + ".png")
    img.save(p)
    print("LABEL", p, img.size)


def fill_rect(d, box, col):
    d.rectangle(box, fill=col)


# ---------------------------------------------------------------------------
# sheets
# ---------------------------------------------------------------------------
def sign_aframe_com():
    """A-frame sidewalk sign: left half = front face, right half = back face."""
    W, H = 2048, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for i, (u0, u1) in enumerate(((0.0, 0.5), (0.5, 1.0))):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        d.rectangle((x0, y0, x1, y1), fill=(250, 246, 232, 255))
        d.rectangle((x0, y0, x1, y0 + 260), fill=(200, 30, 36, 255))
        text_fit(d, (x0 + 40, y0 + 30, x1 - 40, y0 + 160), "CƠM TẤM", "black", (255, 236, 120, 255), img=img)
        text_fit(d, (x0 + 60, y0 + 165, x1 - 60, y0 + 245), "CÔ BA", "black", (255, 255, 255, 255))
        items = ["Sườn nướng than", "Bì · Chả trứng", "Canh rau miễn phí"] if i == 0 else \
                ["Cơm gà xối mỡ", "Cơm rang dưa bò", "Trà đá 3.000đ"]
        for k, t in enumerate(items):
            text_fit(d, (x0 + 50, y0 + 300 + k * 125, x1 - 50, y0 + 400 + k * 125), t, "bvp", (40, 30, 26, 255),
                     max_size=86)
        d.rectangle((x0 + 30, y1 - 250, x1 - 30, y1 - 120), fill=(30, 110, 60, 255))
        text_fit(d, (x0 + 50, y1 - 240, x1 - 50, y1 - 130), "35.000đ / ĐĨA", "xbold", (255, 255, 255, 255))
        text_fit(d, (x0 + 50, y1 - 105, x1 - 50, y1 - 40), "Mở cửa 6h - 21h · Số 12 Hàng Mây", "semi",
                 (60, 50, 45, 255), max_size=48)
    save(weather(img, 0.1, 0.12, 0.03, 3), "sign_aframe_com")


def sign_aframe_cafe():
    W, H = 2048, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for i, (u0, u1) in enumerate(((0.0, 0.5), (0.5, 1.0))):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        d.rectangle((x0, y0, x1, y1), fill=(28, 34, 30, 255))  # chalkboard
        d.rectangle((x0 + 20, y0 + 20, x1 - 20, y1 - 20), outline=(200, 190, 160, 255), width=6)
        text_fit(d, (x0 + 60, y0 + 50, x1 - 60, y0 + 190), "CÀ PHÊ", "serif", (240, 232, 210, 255))
        text_fit(d, (x0 + 60, y0 + 190, x1 - 60, y0 + 290), "Gác Mái", "lora_i", (232, 196, 120, 255))
        items = ["Cà phê muối ...... 30k", "Bạc xỉu ............ 28k", "Cà phê trứng ..... 35k", "Trà đá ................ 5k"] \
            if i == 0 else ["Sữa chua cà phê .. 32k", "Trà sen vàng ....... 30k", "Nước dừa ............ 25k", "Lên tầng 3 →"]
        for k, t in enumerate(items):
            text_fit(d, (x0 + 70, y0 + 340 + k * 120, x1 - 70, y0 + 430 + k * 120), t, "lora", (235, 230, 215, 255),
                     max_size=70, align="left")
        # chalk doodle: steaming cup
        cx, cy = (x0 + x1) // 2, y1 - 110
        d.arc((cx - 60, cy - 40, cx + 60, cy + 50), 0, 180, fill=(235, 230, 215, 255), width=6)
        d.line((cx - 60, cy + 5, cx + 60, cy + 5), fill=(235, 230, 215, 255), width=6)
        for s in (-25, 0, 25):
            d.arc((cx + s - 10, cy - 90, cx + s + 10, cy - 45), 90, 270, fill=(235, 230, 215, 200), width=4)
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    save(weather(img, 0.05, 0.05, 0.08, 5), "sign_aframe_cafe")


def sign_lightbox():
    """Two-sided light-box sign 'BÚN CHẢ HÀNG MÂY' (left = front, right = back)."""
    W, H = 2048, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for (u0, u1) in ((0.0, 0.5), (0.5, 1.0)):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        d.rectangle((x0, y0, x1, y1), fill=(255, 250, 236, 255))
        d.rectangle((x0, y0, x1, y0 + 120), fill=(16, 100, 52, 255))
        text_fit(d, (x0 + 30, y0 + 15, x1 - 30, y0 + 105), "ĐẶC SẢN HÀ THÀNH", "xbold", (255, 255, 255, 255))
        text_fit(d, (x0 + 30, y0 + 150, x1 - 30, y0 + 470), "BÚN CHẢ", "black", (205, 28, 30, 255), img=img,
                 squeeze=0.9)
        text_fit(d, (x0 + 30, y0 + 480, x1 - 30, y0 + 640), "HÀNG MÂY", "black", (16, 100, 52, 255))
        text_fit(d, (x0 + 40, y0 + 680, x1 - 40, y0 + 780), "Nem cua bể · Bún chả que tre", "bvp", (40, 40, 40, 255),
                 max_size=70)
        d.rectangle((x0, y1 - 160, x1, y1), fill=(205, 28, 30, 255))
        text_fit(d, (x0 + 40, y1 - 145, x1 - 40, y1 - 20), "ĐT: 024 0000 1234", "xbold", (255, 236, 120, 255))
    save(weather(img, 0.08, 0.1, 0.02, 9), "sign_lightbox")


def banner_trachanh():
    """Standing flag banner: tall strip, front only (mirrored on back by geometry)."""
    W, H = 512, 2048
    img = new(W, H, (230, 30, 40, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 260), fill=(255, 214, 0, 255))
    text_fit(d, (20, 20, W - 20, 240), "MỚI", "black", (210, 20, 30, 255))
    words = ["TRÀ", "CHANH", "GIÃ", "TAY"]
    for k, wd in enumerate(words):
        text_fit(d, (30, 300 + k * 300, W - 30, 560 + k * 300), wd, "black", (255, 255, 255, 255), img=img, squeeze=0.95)
    d.rectangle((0, H - 400, W, H), fill=(20, 120, 60, 255))
    text_fit(d, (30, H - 380, W - 30, H - 240), "15.000đ", "black", (255, 230, 80, 255))
    text_fit(d, (30, H - 220, W - 30, H - 80), "MÁT LẠNH", "xbold", (255, 255, 255, 255))
    # lemon slice
    cx, cy = W // 2, H - 470
    save(weather(img, 0.18, 0.1, 0.02, 11), "banner_trachanh")


def bin_municipal():
    """Print on the green 240 L bin: front panel (0..0.5 u) and lid emboss text (0.5..1)."""
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 0.5, 1.0))
    text_fit(d, (x0 + 30, y0 + 30, x1 - 30, y0 + 130), "GIỮ GÌN", "black", (250, 250, 245, 255))
    text_fit(d, (x0 + 30, y0 + 130, x1 - 30, y0 + 230), "VỆ SINH CHUNG", "black", (250, 250, 245, 255))
    d.rectangle((x0 + 60, y0 + 260, x1 - 60, y0 + 268), fill=(250, 250, 245, 255))
    text_fit(d, (x0 + 30, y0 + 290, x1 - 30, y0 + 380), "PHƯỜNG HÀNG MÂY", "bold", (250, 250, 245, 255))
    text_fit(d, (x0 + 30, y0 + 400, x1 - 30, y0 + 480), "Số 07", "bold", (250, 250, 245, 255))
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.0, 1.0, 1.0))
    text_fit(d, (x0 + 30, y0 + 160, x1 - 30, y0 + 340), "240L", "black", (255, 255, 255, 255))
    save(weather(img, 0.2, 0.15, 0.1, 13), "bin_municipal")


def manhole_emboss():
    """Emboss mask for the cast-iron manhole cover (white = raised)."""
    W = H = 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    c = W // 2
    white = (255, 255, 255, 255)
    # concentric ring + radial grip pattern
    d.ellipse((40, 40, W - 40, H - 40), outline=white, width=26)
    d.ellipse((300, 300, W - 300, H - 300), outline=white, width=20)
    for i in range(48):
        a = 2 * math.pi * i / 48
        for r0, r1 in ((330, 440),):
            x0, y0 = c + math.cos(a) * r0, c + math.sin(a) * r0
            d.line((x0, y0, c + math.cos(a) * r1, c + math.sin(a) * r1), fill=white, width=14)
    # ring text
    txt = "THOÁT NƯỚC · HÀNG MÂY · 1998 · "
    f = font("black", 46)
    n = len(txt)
    for i, ch in enumerate(txt):
        a = -math.pi / 2 + 2 * math.pi * i / n
        r = 465
        tmp = new(80, 80)
        td = ImageDraw.Draw(tmp)
        td.text((40, 40), ch, font=f, fill=white, anchor="mm")
        tmp = tmp.rotate(-math.degrees(a) - 90, resample=Image.BICUBIC)
        img.alpha_composite(tmp, (int(c + math.cos(a) * r - 40), int(c + math.sin(a) * r - 40)))
    # centre diamond chequer
    for yy in range(-6, 7):
        for xx in range(-6, 7):
            if abs(xx) + abs(yy) <= 7 and (xx + yy) % 2 == 0:
                x, y = c + xx * 30, c + yy * 30
                d.polygon([(x, y - 12), (x + 12, y), (x, y + 12), (x - 12, y)], fill=white)
    save(img, "manhole_emboss")


def mailbox():
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    # front panel (0,0.5)-(1,1): "HÒM THƯ" + crane logo; lower (0,0)-(1,0.5): collection times plate
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.5, 1.0, 1.0))
    green = (16, 84, 52, 255)
    text_fit(d, (x0 + 60, y0 + 40, x1 - 60, y0 + 230), "HÒM THƯ", "black", green)
    text_fit(d, (x0 + 60, y0 + 250, x1 - 60, y0 + 330), "BƯU ĐIỆN PHỐ CŨ", "bold", green)
    # fictional logo: a stylised paper crane in a circle
    cx, cy = (x0 + x1) // 2, y0 + 420
    d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), outline=green, width=10)
    d.polygon([(cx - 50, cy + 20), (cx, cy - 45), (cx + 15, cy + 5), (cx + 55, cy - 15), (cx + 10, cy + 35)], fill=green)
    x0, y0, x1, y1 = rect_px(img, (0.08, 0.05, 0.92, 0.45))
    d.rectangle((x0, y0, x1, y1), fill=(245, 242, 230, 255))
    d.rectangle((x0, y0, x1, y0 + 70), fill=green)
    text_fit(d, (x0 + 20, y0 + 8, x1 - 20, y0 + 62), "GIỜ LẤY THƯ", "xbold", (255, 255, 255, 255))
    for k, t in enumerate(["Sáng   8:00", "Chiều 15:30", "Chủ nhật nghỉ"]):
        text_fit(d, (x0 + 40, y0 + 100 + k * 80, x1 - 40, y0 + 165 + k * 80), t, "semi", (30, 30, 30, 255),
                 max_size=56, align="left")
    save(weather(img, 0.15, 0.15, 0.04, 17), "mailbox")


def barrier():
    """Water-filled barrier panels: u 0..0.5 front, 0.5..1 back — red/white chevrons + yellow text plate."""
    W, H = 2048, 512
    img = new(W, H)
    for (u0, u1) in ((0.0, 0.5), (0.5, 1.0)):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        half = new(x1 - x0, y1 - y0, (240, 240, 235, 255))
        d = ImageDraw.Draw(half)
        hw, hh = half.size
        step = 150
        for k in range(-4, hw // step + 4):
            xs = k * step
            d.polygon([(xs, hh), (xs + 70, hh), (xs + 70 + 220, 0), (xs + 220, 0)], fill=(214, 40, 34, 255))
        d.rectangle((90, 120, hw - 90, hh - 120), fill=(255, 214, 0, 255))
        d.rectangle((90, 120, hw - 90, hh - 120), outline=(20, 20, 20, 255), width=6)
        text_fit(d, (120, 140, hw - 120, 250), "CÔNG TRÌNH ĐANG THI CÔNG", "black", (20, 20, 20, 255))
        text_fit(d, (150, 262, hw - 150, hh - 140), "Xin lỗi vì sự bất tiện", "bold", (20, 20, 20, 255))
        img.alpha_composite(half, (x0, y0))
    save(weather(img, 0.15, 0.2, 0.06, 19), "barrier")


def gas_cylinder():
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 1.0, 1.0))
    d.rounded_rectangle((60, 60, W - 60, H - 60), 40, fill=(255, 255, 255, 255))
    text_fit(d, (100, 80, W - 100, 230), "GAS PHỐ CŨ", "black", (200, 24, 30, 255))
    text_fit(d, (100, 240, W - 100, 320), "KHÍ DẦU MỎ HÓA LỎNG · 12KG", "bold", (20, 50, 120, 255))
    text_fit(d, (100, 340, W - 100, 430), "CẤM LỬA  ·  ĐỂ NƠI THOÁNG MÁT", "xbold", (200, 24, 30, 255))
    save(weather(img, 0.25, 0.25, 0.12, 23), "gas_cylinder")


def cardboard_noodle():
    """Carton print: 2 big sides (u 0..0.5, 0.5..1 in lower half) + 2 small ends (upper half)."""
    W, H = 2048, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    red = (176, 36, 30, 235)
    blue = (30, 60, 120, 235)
    for i, (u0, u1) in enumerate(((0.0, 0.5), (0.5, 1.0))):
        x0, y0, x1, y1 = rect_px(img, (u0, 0.0, u1, 0.62))
        text_fit(d, (x0 + 80, y0 + 40, x1 - 80, y0 + 200), "MÌ HẠNH PHÚC", "black", red, img=img, squeeze=0.92)
        text_fit(d, (x0 + 120, y0 + 210, x1 - 120, y0 + 290), "Hương vị tôm chua cay · 30 gói x 75g", "bold", blue)
        # fragile glass + arrows
        bx = x1 - 260
        d.rectangle((bx, y1 - 220, bx + 180, y1 - 40), outline=(20, 20, 20, 220), width=6)
        d.polygon([(bx + 50, y1 - 200), (bx + 130, y1 - 200), (bx + 110, y1 - 130), (bx + 70, y1 - 130)],
                  fill=(20, 20, 20, 220))
        d.line((bx + 90, y1 - 130, bx + 90, y1 - 70), fill=(20, 20, 20, 220), width=8)
        d.line((bx + 60, y1 - 65, bx + 120, y1 - 65), fill=(20, 20, 20, 220), width=8)
        ax = x0 + 120
        for k in (0, 70):
            d.polygon([(ax + k, y1 - 210), (ax + k + 30, y1 - 160), (ax + k - 30, y1 - 160)], fill=(20, 20, 20, 220))
            d.rectangle((ax + k - 8, y1 - 160, ax + k + 8, y1 - 60), fill=(20, 20, 20, 220))
        text_fit(d, (x0 + 300, y1 - 160, x1 - 320, y1 - 70), "HÀNG DỄ VỠ - NHẸ TAY", "xbold", (20, 20, 20, 220))
    for i, (u0, u1) in enumerate(((0.0, 0.5), (0.5, 1.0))):
        x0, y0, x1, y1 = rect_px(img, (u0, 0.64, u1, 1.0))
        text_fit(d, (x0 + 80, y0 + 30, x1 - 80, y0 + 160), "MÌ HẠNH PHÚC", "black", red)
        text_fit(d, (x0 + 80, y0 + 200, x1 - 80, y0 + 300), "NSX 08/2026 · HSD 02/2027 · LÔ 0815", "mono", (20, 20, 20, 220))
    save(weather(img, 0.25, 0.1, 0.15, 29), "cardboard_noodle")


def styrofoam_marker():
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for i, (u0, u1, txt) in enumerate(((0.0, 0.5, "RAU MUỐNG"), (0.5, 1.0, "CÔ HOA - CÁ"))):
        x0, y0, x1, y1 = rect_px(img, (u0, 0.1, u1, 0.9))
        tmp = new(x1 - x0, y1 - y0)
        td = ImageDraw.Draw(tmp)
        text_fit(td, (20, 40, x1 - x0 - 20, y1 - y0 - 40), txt, "bvp", (25, 30, 60, 230))
        tmp = tmp.rotate(RNG.uniform(-6, 6), resample=Image.BICUBIC)
        tmp = tmp.filter(ImageFilter.GaussianBlur(1.2))
        img.alpha_composite(tmp, (x0, y0))
    save(weather(img, 0.1, 0.0, 0.18, 31), "styrofoam_marker")


def crate_emboss():
    W, H = 1024, 256
    img = new(W, H)
    d = ImageDraw.Draw(img)
    text_fit(d, (40, 30, W - 40, H - 30), "NHỰA PHỐ CŨ  ·  PP  ·  2024", "black", (255, 255, 255, 255))
    save(img, "crate_emboss")


def bottle_crate():
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    # crate side print (u 0..1, v 0.5..1); bottle label (v 0..0.5): oval brand label
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.5, 1.0, 1.0))
    text_fit(d, (x0 + 40, y0 + 30, x1 - 40, y1 - 30), "BIA HÀNG MÂY", "black", (250, 240, 220, 255))
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 1.0, 0.5))
    d.rectangle((x0, y0, x1, y1), fill=(232, 222, 186, 255))
    d.rectangle((x0, y0 + 20, x1, y0 + 40), fill=(170, 30, 30, 255))
    d.rectangle((x0, y1 - 40, x1, y1 - 20), fill=(170, 30, 30, 255))
    text_fit(d, (x0 + 60, y0 + 50, x1 - 60, y0 + 150), "BIA HÀNG MÂY", "serif", (150, 20, 24, 255))
    text_fit(d, (x0 + 120, y0 + 160, x1 - 120, y0 + 220), "Lager · 4,2% vol · 450ml", "semi", (40, 30, 20, 255))
    save(weather(img, 0.15, 0.15, 0.05, 37), "bottle_crate")


def rice_sack():
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    green = (20, 110, 50, 240)
    red = (200, 30, 30, 240)
    for (u0, u1) in ((0.0, 0.5), (0.5, 1.0)):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        text_fit(d, (x0 + 30, y0 + 80, x1 - 30, y0 + 230), "GẠO", "black", red)
        text_fit(d, (x0 + 30, y0 + 240, x1 - 30, y0 + 380), "BÔNG LÚA", "black", green)
        # rice-stalk emblem
        cx, cy = (x0 + x1) // 2, y0 + 560
        d.ellipse((cx - 130, cy - 130, cx + 130, cy + 130), outline=green, width=10)
        for k in range(7):
            a = math.radians(-60 + k * 20)
            d.line((cx, cy + 90, cx + math.sin(a) * 110, cy - math.cos(a) * 110 + 20), fill=(214, 160, 30, 240), width=8)
        text_fit(d, (x0 + 30, y0 + 730, x1 - 30, y0 + 830), "THƠM DẺO MIỀN TÂY", "xbold", green)
        text_fit(d, (x0 + 30, y0 + 850, x1 - 30, y0 + 960), "25 KG", "black", red)
    save(weather(img, 0.22, 0.12, 0.12, 41), "rice_sack")


def feed_sack():
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for (u0, u1) in ((0.0, 0.5), (0.5, 1.0)):
        x0, y0, x1, y1 = rect_px(img, (u0, 0, u1, 1))
        text_fit(d, (x0 + 40, y0 + 120, x1 - 40, y0 + 260), "THỨC ĂN", "black", (30, 70, 160, 220))
        text_fit(d, (x0 + 40, y0 + 270, x1 - 40, y0 + 400), "CHĂN NUÔI", "black", (30, 70, 160, 220))
        d.rectangle((x0 + 60, y0 + 440, x1 - 60, y0 + 520), fill=(220, 40, 40, 220))
        text_fit(d, (x0 + 70, y0 + 450, x1 - 70, y0 + 510), "HEO CON · 25KG", "xbold", (255, 255, 255, 230))
    save(weather(img, 0.45, 0.25, 0.25, 43), "feed_sack")


def food_cart():
    """Glass-case decals (red letters) + cart skirt panel."""
    W, H = 2048, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.5, 1.0, 1.0))
    text_fit(d, (x0 + 60, y0 + 10, x1 - 60, y1 - 10), "XÔI XÉO · XÔI GẤC · XÔI LẠC", "black", (200, 20, 28, 255))
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 1.0, 0.5))
    d.rectangle((x0, y0, x1, y1), fill=(30, 90, 160, 255))
    text_fit(d, (x0 + 60, y0 + 20, x1 - 60, y1 - 20), "XÔI CÔ HẠNH  ·  NGON - SẠCH - RẺ", "black", (255, 240, 120, 255))
    save(weather(img, 0.12, 0.15, 0.05, 47), "food_cart")


def banh_mi_cart():
    W, H = 2048, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.5, 1.0, 1.0))
    text_fit(d, (x0 + 60, y0 + 10, x1 - 60, y1 - 10), "BÁNH MÌ CHÚ SÁU", "black", (210, 24, 30, 255))
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 1.0, 0.5))
    d.rectangle((x0, y0, x1, y1), fill=(250, 200, 30, 255))
    text_fit(d, (x0 + 60, y0 + 15, x1 - 60, y1 - 15), "PATÊ · CHẢ · XÍU MẠI · TRỨNG  —  15K", "black", (180, 20, 24, 255))
    save(weather(img, 0.12, 0.15, 0.05, 53), "banh_mi_cart")


def altar_box():
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    gold = (232, 186, 70, 255)
    # back panel (top half): big Hán-Việt 'Phúc' character + Vietnamese caption, couplet strips on the sides
    x0, y0, x1, y1 = rect_px(img, (0.15, 0.5, 0.85, 1.0))
    d.ellipse((x0 + 40, y0 + 30, x1 - 40, y1 - 60), outline=gold, width=8)
    text_fit(d, (x0 + 90, y0 + 70, x1 - 90, y1 - 110), "福", "cjk", gold, max_size=380)
    text_fit(d, (x0 + 40, y1 - 60, x1 - 40, y1 - 8), "THỔ ĐỊA · TÀI LỘC", "serif6", gold)
    for (u0, u1, txt) in ((0.0, 0.14, "PHÚC"), (0.86, 1.0, "LỘC")):
        x0, y0, x1, y1 = rect_px(img, (u0, 0.5, u1, 1.0))
        for k, ch in enumerate(txt):
            text_fit(d, (x0 + 10, y0 + 30 + k * 115, x1 - 10, y0 + 140 + k * 115), ch, "serif", gold, max_size=110)
    # bottom half: front apron with cloud scrolls
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 1.0, 0.5))
    for k in range(6):
        cx = x0 + 90 + k * 170
        cy = (y0 + y1) // 2
        d.arc((cx - 60, cy - 40, cx + 20, cy + 40), 90, 360, fill=gold, width=10)
        d.arc((cx - 10, cy - 30, cx + 60, cy + 40), 180, 450, fill=gold, width=10)
    d.rectangle((x0 + 10, y0 + 20, x1 - 10, y0 + 32), fill=gold)
    d.rectangle((x0 + 10, y1 - 32, x1 - 10, y1 - 20), fill=gold)
    save(weather(img, 0.2, 0.2, 0.08, 59), "altar_box")


def silk_pattern():
    """Gold brocade motif for silk lanterns (tileable horizontally)."""
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    gold = (236, 196, 96, 200)
    for k in range(8):
        cx = 64 + k * 128
        for cy in (128, 384):
            d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), outline=gold, width=6)
            for j in range(8):
                a = 2 * math.pi * j / 8
                d.ellipse((cx + math.cos(a) * 42 - 10, cy + math.sin(a) * 42 - 10, cx + math.cos(a) * 42 + 10,
                           cy + math.sin(a) * 42 + 10), fill=gold)
    d.rectangle((0, 250, W, 262), fill=gold)
    save(img, "silk_pattern")


def carp_scales():
    """Painted carp lantern skin: scales, eye, fin stripes (u along body, v around)."""
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for row in range(10):
        for col in range(24):
            cx = 160 + col * 34 + (17 if row % 2 else 0)
            cy = 40 + row * 44
            if cx > W - 120:
                continue
            d.arc((cx - 24, cy - 24, cx + 24, cy + 24), 20, 160, fill=(150, 20, 20, 230), width=5)
    # gold belly band and eye on the head end (u ~0.08)
    d.rectangle((0, 210, W, 300), fill=(255, 205, 60, 120))
    for ey in (120, 390):
        d.ellipse((50, ey - 35, 120, ey + 35), fill=(255, 255, 255, 255))
        d.ellipse((70, ey - 20, 108, ey + 20), fill=(10, 10, 10, 255))
    save(img, "carp_scales")


def bottles():
    """Labels: fish sauce (row 0), soy sauce (1), water (2), herbal tonic (3); each a horizontal strip."""
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    rows = [((235, 205, 120, 255), "NƯỚC MẮM", "PHÚ CHÂU · 40 ĐỘ ĐẠM", (150, 20, 20, 255)),
            ((250, 245, 230, 255), "XÌ DẦU", "ĐẬU NÀNH LÊN MEN · 500ml", (30, 30, 30, 255)),
            ((60, 140, 210, 255), "NƯỚC SUỐI MÂY", "Tinh khiết · 500ml", (255, 255, 255, 255)),
            ((210, 190, 140, 255), "CAO DƯỢC THẢO", "Bổ khí huyết · 100ml", (90, 40, 20, 255))]
    for i, (bg, t1, t2, fg) in enumerate(rows):
        y0 = i * 256
        d.rectangle((0, y0 + 8, W, y0 + 248), fill=bg)
        text_fit(d, (60, y0 + 30, W - 60, y0 + 150), t1, "black", fg)
        text_fit(d, (80, y0 + 160, W - 80, y0 + 230), t2, "semi", fg)
        if i == 2:
            d.line((0, y0 + 20, W, y0 + 20), fill=(255, 255, 255, 255), width=6)
    save(weather(img, 0.12, 0.12, 0.04, 61), "bottles")


def books():
    """Book covers/spines: 4 books, each a horizontal band (v quarters): spine left 0..0.15, cover 0.15..1."""
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    specs = [((120, 30, 30, 255), "TRUYỆN KIỀU", "Nguyễn Du", (236, 206, 130, 255)),
             ((30, 70, 110, 255), "MÈO VÀ PHỐ", "Tản văn", (245, 240, 225, 255)),
             ((40, 90, 50, 255), "CÂY NHÀ LÁ VƯỜN", "Sổ tay", (245, 235, 200, 255)),
             ((205, 175, 120, 255), "NẤU ĂN NGON", "Món Hà Nội", (90, 30, 20, 255))]
    for i, (bg, t1, t2, fg) in enumerate(specs):
        y0 = i * 256
        d.rectangle((0, y0, W, y0 + 256), fill=bg)
        d.rectangle((0, y0, int(W * 0.15), y0 + 256), fill=tuple(int(c * 0.8) for c in bg[:3]) + (255,))
        tmp = new(256, int(W * 0.15))
        td = ImageDraw.Draw(tmp)
        text_fit(td, (10, 10, 246, int(W * 0.15) - 10), t1, "bold", fg, max_size=60)
        img.alpha_composite(tmp.rotate(90, expand=True), (0, y0))
        text_fit(d, (int(W * 0.2), y0 + 40, W - 40, y0 + 150), t1, "serif", fg)
        text_fit(d, (int(W * 0.2), y0 + 160, W - 40, y0 + 220), t2, "lora_i", fg, max_size=50)
    save(weather(img, 0.15, 0.1, 0.03, 67), "books")


def phone_remote():
    """Phone screen (left half, lock screen) + remote buttons (right half)."""
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 0.5, 1.0))
    for y in range(y0, y1):
        t = (y - y0) / (y1 - y0)
        d.line((x0, y, x1, y), fill=(int(30 + 60 * t), int(40 + 30 * t), int(80 + 40 * t), 255))
    text_fit(d, (x0 + 60, y0 + 120, x1 - 60, y0 + 300), "18:42", "semi", (240, 240, 245, 255))
    text_fit(d, (x0 + 100, y0 + 300, x1 - 100, y0 + 350), "Thứ Bảy, 14 tháng 9", "reg", (220, 220, 230, 255))
    d.ellipse((x0 + 180, y0 + 600, x1 - 180, y0 + 860), fill=(240, 160, 60, 255))  # orange cat wallpaper blob
    d.polygon([(x0 + 200, y0 + 640), (x0 + 230, y0 + 560), (x0 + 270, y0 + 630)], fill=(240, 160, 60, 255))
    d.polygon([(x1 - 200, y0 + 640), (x1 - 230, y0 + 560), (x1 - 270, y0 + 630)], fill=(240, 160, 60, 255))
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.0, 1.0, 1.0))
    d.rectangle((x0, y0, x1, y1), fill=(28, 28, 30, 255))
    d.ellipse((x0 + 40, y0 + 40, x0 + 110, y0 + 110), fill=(200, 30, 30, 255))
    labels = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "-", "0", "OK"]
    for k, t in enumerate(labels):
        cx = x0 + 90 + (k % 3) * 160
        cy = y0 + 220 + (k // 3) * 140
        d.rounded_rectangle((cx - 50, cy - 40, cx + 50, cy + 40), 20, fill=(70, 70, 74, 255))
        text_fit(d, (cx - 40, cy - 30, cx + 40, cy + 30), t, "bold", (230, 230, 230, 255))
    text_fit(d, (x0 + 60, y1 - 150, x1 - 60, y1 - 60), "ĐIỀU KHIỂN TV", "semi", (150, 150, 150, 255))
    save(img, "phone_remote")


def letter():
    """Envelope front (left half) + back (right half), handwritten address, fictional stamp."""
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 0.5, 1.0))
    ink = (30, 40, 90, 235)
    text_fit(d, (x0 + 60, y0 + 230, x1 - 40, y0 + 290), "Kính gửi: Bà Tư", "lora_i", ink, align="left")
    text_fit(d, (x0 + 60, y0 + 300, x1 - 40, y0 + 350), "Quán trà đầu ngõ", "lora_i", ink, align="left")
    text_fit(d, (x0 + 60, y0 + 360, x1 - 40, y0 + 410), "Phố Hàng Mây", "lora_i", ink, align="left")
    sx = x1 - 140
    d.rectangle((sx, y0 + 30, sx + 100, y0 + 150), fill=(200, 60, 50, 255))
    d.rectangle((sx + 8, y0 + 38, sx + 92, y0 + 142), outline=(255, 240, 220, 255), width=3)
    d.ellipse((sx + 25, y0 + 60, sx + 75, y0 + 110), fill=(250, 200, 80, 255))  # moon motif
    for k in range(4):
        d.arc((sx - 80 - k * 6, y0 + 50, sx + 30 - k * 6, y0 + 160), 200, 340, fill=(40, 40, 40, 160), width=3)
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.0, 1.0, 1.0))
    d.polygon([(x0, y0), (x1, y0), ((x0 + x1) // 2, y0 + 230)], outline=(150, 135, 110, 200), fill=None)
    d.line((x0, y0, (x0 + x1) // 2, y0 + 230), fill=(150, 135, 110, 200), width=3)
    d.line((x1, y0, (x0 + x1) // 2, y0 + 230), fill=(150, 135, 110, 200), width=3)
    text_fit(d, (x0 + 80, y1 - 120, x1 - 80, y1 - 60), "Người gửi: Mai — Sài Gòn", "lora_i", ink)
    save(img, "letter")


def memory_photo():
    """A faded 1980s-90s sepia snapshot: a young woman at a tea stall in front of shophouses."""
    W, H = 712, 512
    rng = np.random.default_rng(71)
    img = Image.new("RGB", (W, H), (150, 130, 100))
    d = ImageDraw.Draw(img)
    # sky / shopfronts
    d.rectangle((0, 0, W, 180), fill=(196, 182, 150))
    for k, x in enumerate(range(-20, W, 120)):
        tone = 120 + (k * 37) % 50
        d.rectangle((x, 60 + (k % 3) * 15, x + 115, 330), fill=(tone, tone - 15, tone - 35))
        for wy in (100, 170):
            d.rectangle((x + 25, wy + (k % 3) * 15, x + 50, wy + 40 + (k % 3) * 15), fill=(70, 60, 45))
            d.rectangle((x + 65, wy + (k % 3) * 15, x + 90, wy + 40 + (k % 3) * 15), fill=(70, 60, 45))
    d.rectangle((0, 330, W, H), fill=(110, 95, 75))
    # tea stall table + kettle + stools
    d.rectangle((140, 300, 470, 320), fill=(80, 60, 40))
    d.rectangle((160, 320, 175, 420), fill=(70, 50, 35))
    d.rectangle((435, 320, 450, 420), fill=(70, 50, 35))
    d.ellipse((380, 255, 440, 305), fill=(170, 165, 150))
    d.rectangle((395, 245, 425, 260), fill=(160, 155, 140))
    for sx in (110, 500):
        d.rectangle((sx, 380, sx + 70, 395), fill=(90, 70, 55))
        d.rectangle((sx + 5, 395, sx + 15, 450), fill=(90, 70, 55))
        d.rectangle((sx + 55, 395, sx + 65, 450), fill=(90, 70, 55))
    # woman with conical hat (nón lá), smiling, holding a kitten
    d.polygon([(250, 150), (330, 112), (410, 150)], fill=(222, 208, 170))
    d.ellipse((300, 145, 360, 215), fill=(205, 175, 140))
    d.rectangle((285, 210, 375, 330), fill=(235, 228, 210))  # áo bà ba
    d.ellipse((310, 255, 350, 290), fill=(200, 140, 70))      # the kitten (Cam's ancestor?)
    d.rectangle((292, 330, 368, 420), fill=(40, 35, 30))
    a = np.asarray(img, np.float32) / 255.0
    lum = a.mean(axis=2, keepdims=True)
    sep = np.concatenate([lum * 1.07 + 0.06, lum * 0.95 + 0.03, lum * 0.75], axis=2)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.45 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    sep *= vig[..., None]
    sep += rng.normal(0, 0.035, sep.shape)
    sep = np.clip(sep, 0, 1)
    ph = Image.fromarray((sep * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.6))
    # white border, creases, stains
    out = Image.new("RGBA", (W + 64, H + 64), (232, 222, 196, 255))
    out.paste(ph, (32, 32))
    dd = ImageDraw.Draw(out)
    dd.line((0, (H + 64) * 0.62, W + 64, (H + 64) * 0.55), fill=(250, 245, 230, 140), width=3)
    dd.line(((W + 64) * 0.35, 0, (W + 64) * 0.4, H + 64), fill=(250, 245, 230, 110), width=2)
    out = out.resize((1024, 768), Image.LANCZOS)
    big = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    big.paste(out, (0, 0))
    # back side (bottom quarter): handwriting
    bd = ImageDraw.Draw(big)
    bd.rectangle((0, 768, 1024, 1024), fill=(236, 228, 208, 255))
    text_fit(bd, (60, 800, 964, 900), "Hàng Mây, Trung thu 1989", "lora_i", (60, 50, 80, 230))
    text_fit(bd, (60, 900, 964, 990), "— Tư và bé Mướp", "lora_i", (60, 50, 80, 230))
    save(big, "memory_photo")


def coin_figurine():
    """Lucky-cat figurine print: red bib with gold 'LỘC', gold coin 'PHÚC', painted face."""
    W, H = 1024, 512
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 0.5, 1.0))
    d.ellipse((x0 + 20, y0 + 20, x1 - 20, y1 - 20), fill=(210, 160, 40, 255))
    d.ellipse((x0 + 50, y0 + 50, x1 - 50, y1 - 50), outline=(150, 100, 20, 255), width=10)
    text_fit(d, (x0 + 110, y0 + 110, x1 - 110, y1 - 110), "PHÚC", "serif", (130, 80, 10, 255))
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.0, 1.0, 1.0))
    d.ellipse((x0 + 20, y0 + 40, x1 - 20, y1 - 20), fill=(196, 24, 30, 255))
    text_fit(d, (x0 + 120, y0 + 140, x1 - 120, y1 - 100), "LỘC", "serif", (250, 210, 90, 255))
    save(img, "coin_figurine")


def misc_items():
    """Small item prints (quadrants): cap top (u0..0.5,v.5..1), leg band (.5..1,.5..1),
    catnip pouch (0..0.5, 0..0.5), skill tonic (0.5..1, 0..0.5)."""
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.5, 0.5, 1.0))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    d.ellipse((cx - 240, cy - 240, cx + 240, cy + 240), fill=(200, 26, 30, 255))
    d.ellipse((cx - 180, cy - 180, cx + 180, cy + 180), outline=(250, 210, 90, 255), width=12)
    text_fit(d, (cx - 160, cy - 90, cx + 160, cy - 10), "BIA", "black", (250, 240, 220, 255))
    text_fit(d, (cx - 170, cy, cx + 170, cy + 80), "HÀNG MÂY", "black", (250, 210, 90, 255))
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.5, 1.0, 1.0))
    text_fit(d, (x0 + 40, y0 + 160, x1 - 40, y0 + 340), "HM-07", "mono", (40, 40, 40, 255))
    x0, y0, x1, y1 = rect_px(img, (0.0, 0.0, 0.5, 0.5))
    text_fit(d, (x0 + 50, y0 + 150, x1 - 50, y0 + 260), "BẠC HÀ", "bvp", (40, 90, 40, 230))
    text_fit(d, (x0 + 50, y0 + 270, x1 - 50, y0 + 360), "MÈO", "bvp", (40, 90, 40, 230))
    x0, y0, x1, y1 = rect_px(img, (0.5, 0.0, 1.0, 0.5))
    d.rectangle((x0 + 20, y0 + 120, x1 - 20, y1 - 120), fill=(245, 236, 210, 255))
    text_fit(d, (x0 + 50, y0 + 150, x1 - 50, y0 + 250), "TINH CHẤT", "serif", (100, 30, 110, 255))
    text_fit(d, (x0 + 50, y0 + 260, x1 - 50, y0 + 360), "CỬU MẠNG", "serif", (100, 30, 110, 255))
    save(img, "misc_items")


def ceramic_patterns():
    """Blue-and-white (Bát Tràng style) motifs: band (top), lotus sprays (bottom). Tileable in u."""
    W, H = 2048, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    blue = (36, 62, 140, 235)
    d.rectangle((0, 40, W, 56), fill=blue)
    d.rectangle((0, 470, W, 480), fill=blue)
    for k in range(16):
        cx = 64 + k * 128
        d.arc((cx - 50, 80, cx + 50, 200), 180, 360, fill=blue, width=8)
        d.ellipse((cx - 10, 120, cx + 10, 140), fill=blue)
    for k in range(5):
        cx = 200 + k * 400
        cy = 300
        for j in range(5):
            a = math.radians(-90 + (j - 2) * 30)
            px, py = cx + math.cos(a) * 70, cy + math.sin(a) * 70
            d.ellipse((px - 40, py - 70, px + 40, py + 30), outline=blue, width=7)
        d.line((cx, cy, cx - 40, cy + 140), fill=blue, width=7)
        d.ellipse((cx - 160, cy + 40, cx - 60, cy + 110), outline=blue, width=6)
    # lower half: green-glaze crackle tea cup band (u 0..1, v 0..0.5): thin brown lines
    for k in range(10):
        y = 560 + k * 45
        d.line((0, y, W, y + RNG.uniform(-6, 6)), fill=(120, 80, 40, 90), width=2)
    save(img, "ceramic_patterns")


def pole_stickers():
    """Pole clutter (u 0..1 wraps half the pole circumference, v up): torn ads, stencil number,
    plus the distribution-box warning plate in the top-right quadrant."""
    W, H = 1024, 1024
    img = new(W, H)
    d = ImageDraw.Draw(img)
    ads = [((0.02, 0.05, 0.3, 0.22), (255, 236, 60, 255), ["KHOAN CẮT", "BÊ TÔNG", "0900 000 101"], (20, 20, 20, 255)),
           ((0.33, 0.02, 0.6, 0.16), (255, 255, 255, 255), ["THÔNG HÚT", "BỂ PHỐT", "0900 000 202"], (200, 20, 20, 255)),
           ((0.05, 0.26, 0.28, 0.38), (230, 240, 255, 255), ["CHO THUÊ", "PHÒNG", "0900 000 303"], (20, 40, 140, 255)),
           ((0.62, 0.06, 0.95, 0.2), (255, 200, 200, 255), ["DẠY KÈM", "TOÁN · LÝ · HÓA"], (130, 20, 40, 255)),
           ((0.36, 0.22, 0.58, 0.36), (250, 250, 240, 255), ["MUA ĐỒ CŨ", "GIÁ CAO"], (20, 20, 20, 255))]
    for rect, bg, lines, fg in ads:
        x0, y0, x1, y1 = rect_px(img, rect)
        tmp = new(x1 - x0, y1 - y0, bg)
        td = ImageDraw.Draw(tmp)
        n = len(lines)
        hh = (y1 - y0) // n
        for k, t in enumerate(lines):
            text_fit(td, (8, 6 + k * hh, x1 - x0 - 8, (k + 1) * hh - 4), t, "black" if k < n - 1 else "bold", fg)
        a = np.asarray(tmp).copy()
        tn = noise(x1 - x0, y1 - y0, 16, 3, int(x0 + y0))
        a[..., 3] = np.where(tn > 0.7, 0, a[..., 3])  # torn
        tmp = Image.fromarray(a, "RGBA").rotate(RNG.uniform(-5, 5), resample=Image.BICUBIC, expand=False)
        img.alpha_composite(tmp, (x0, y0))
    # stencil pole number (spray paint)
    x0, y0, x1, y1 = rect_px(img, (0.1, 0.45, 0.5, 0.58))
    tmp = new(x1 - x0, y1 - y0)
    text_fit(ImageDraw.Draw(tmp), (4, 4, x1 - x0 - 4, y1 - y0 - 4), "07-HM", "mono", (240, 240, 235, 235))
    img.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(1.5)), (x0, y0))
    # warning plate (box door): yellow triangle + text
    x0, y0, x1, y1 = rect_px(img, (0.55, 0.55, 1.0, 1.0))
    d.rectangle((x0, y0, x1, y1), fill=(245, 245, 240, 255))
    cx = (x0 + x1) // 2
    d.polygon([(cx, y0 + 30), (x1 - 60, y0 + 270), (x0 + 60, y0 + 270)], fill=(250, 205, 0, 255), outline=(20, 20, 20, 255))
    d.line((cx - 30, y0 + 230), fill=None)
    d.polygon([(cx + 15, y0 + 90), (cx - 35, y0 + 180), (cx, y0 + 180), (cx - 20, y0 + 250), (cx + 40, y0 + 150),
               (cx + 5, y0 + 150), (cx + 30, y0 + 90)], fill=(20, 20, 20, 255))
    text_fit(d, (x0 + 20, y0 + 290, x1 - 20, y0 + 370), "NGUY HIỂM", "black", (200, 20, 20, 255))
    text_fit(d, (x0 + 20, y0 + 375, x1 - 20, y0 + 440), "ĐIỆN ÁP CAO", "black", (20, 20, 20, 255))
    save(weather(img, 0.25, 0.25, 0.08, 73), "pole_stickers")


def hydrant_band():
    W, H = 1024, 256
    img = new(W, H)
    d = ImageDraw.Draw(img)
    for k in range(2):
        x0 = k * 512
        text_fit(d, (x0 + 40, 40, x0 + 472, 216), "PCCC · 114", "black", (255, 255, 255, 255))
    save(weather(img, 0.3, 0.2, 0.12, 79), "hydrant_band")


SHEETS = {f.__name__: f for f in [
    sign_aframe_com, sign_aframe_cafe, sign_lightbox, banner_trachanh, bin_municipal, manhole_emboss, mailbox,
    barrier, gas_cylinder, cardboard_noodle, styrofoam_marker, crate_emboss, bottle_crate, rice_sack, feed_sack,
    food_cart, banh_mi_cart, altar_box, silk_pattern, carp_scales, bottles, books, phone_remote, letter,
    memory_photo, coin_figurine, misc_items, ceramic_patterns, pole_stickers, hydrant_band]}


def contact_sheet():
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".png"))
    tiles = []
    for f in files:
        im = Image.open(os.path.join(OUT, f)).convert("RGBA")
        im.thumbnail((360, 360))
        bg = Image.new("RGBA", (380, 400), (90, 90, 90, 255))
        bg.alpha_composite(im, ((380 - im.size[0]) // 2, 10))
        ImageDraw.Draw(bg).text((10, 375), f, fill=(255, 255, 255, 255))
        tiles.append(bg)
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * 380, rows * 400), (60, 60, 60, 255))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % cols) * 380, (i // cols) * 400))
    p = os.path.join(ROOT, "qa", "out", "street-props", "labels_sheet.png")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    sheet.convert("RGB").save(p)
    print("SHEET", p)


if __name__ == "__main__":
    args = sys.argv[1:]
    only = args[args.index("--only") + 1].split(",") if "--only" in args else list(SHEETS)
    for n in only:
        SHEETS[n]()
    if "--sheet" in args:
        contact_sheet()
