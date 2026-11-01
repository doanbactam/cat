"""Tileable procedural texture synthesis for the city-houses architecture kit.

Pure numpy (+ Pillow for drawing / saving). No bpy: runs in plain python3
(blender/city/gen_textures.py) and inside Blender alike.

Every generator here is *periodic* (seamless) by construction:
  * spectral (FFT) noise is periodic on the tile,
  * blurs are FFT based (periodic),
  * drawn features (cracks, chips, stones) are stamped with wrap-around offsets.

Conventions
  * images are float32 arrays in [0, 1], shape (n, n) or (n, n, 3); row 0 = top (v = 1).
  * heights are in metres; `tile_m` is the physical size of the tile (e.g. 2.0 m).
  * normal maps are OpenGL / glTF / Godot convention (+Y = green = up in the image).
"""
from __future__ import annotations

import math
import os

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except Exception:  # inside Blender Pillow is usually missing; only saving needs it
    Image = ImageDraw = ImageFilter = ImageFont = None


# ---------------------------------------------------------------------------
# Core noise
# ---------------------------------------------------------------------------
def _freq_grid(n: int):
    f = np.fft.fftfreq(n) * n
    fx, fy = np.meshgrid(f, f)
    return fx, fy


def spectral(n: int, seed: int, beta: float = 2.0, fmin: float = 1.0, fmax: float | None = None,
             aniso: tuple[float, float] = (1.0, 1.0), rot_deg: float = 0.0) -> np.ndarray:
    """Periodic 1/f^beta noise, zero mean / unit std.

    fmin/fmax are in cycles per tile. aniso=(ax, ay) stretches the spectrum: ay > ax gives
    features elongated along X... use aniso=(1, 6) for vertical streaks (low freq along Y).
    """
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((n, n)).astype(np.float32)
    F = np.fft.fft2(white)
    fx, fy = _freq_grid(n)
    if rot_deg:
        a = math.radians(rot_deg)
        fx, fy = fx * math.cos(a) - fy * math.sin(a), fx * math.sin(a) + fy * math.cos(a)
    r = np.sqrt((fx * aniso[0]) ** 2 + (fy * aniso[1]) ** 2)
    rr = np.maximum(r, 1e-6)
    amp = rr ** (-beta / 2.0)
    amp *= 1.0 / (1.0 + np.exp(-(r - fmin) * 3.0))  # soft high-pass at fmin
    if fmax is not None:
        amp *= 1.0 / (1.0 + np.exp((r - fmax) * (6.0 / max(fmax, 1.0))))
    amp[0, 0] = 0.0
    out = np.real(np.fft.ifft2(F * amp)).astype(np.float32)
    out -= out.mean()
    s = out.std()
    return out / (s if s > 1e-8 else 1.0)


def fbm(n: int, seed: int, fmin: float = 2.0, fmax: float | None = None, beta: float = 2.0,
        aniso=(1.0, 1.0)) -> np.ndarray:
    """Spectral noise remapped to [0, 1] (approx; 3 sigma)."""
    s = spectral(n, seed, beta, fmin, fmax, aniso)
    return np.clip(s / 6.0 + 0.5, 0.0, 1.0)


def blur(img: np.ndarray, sigma_px: float) -> np.ndarray:
    """Periodic gaussian blur via FFT (works for 2D or 3D HxWxC)."""
    if sigma_px <= 0:
        return img
    n0, n1 = img.shape[:2]
    f0 = np.fft.fftfreq(n0)[:, None]
    f1 = np.fft.fftfreq(n1)[None, :]
    g = np.exp(-2.0 * (math.pi ** 2) * (sigma_px ** 2) * (f0 ** 2 + f1 ** 2))
    if img.ndim == 3:
        return np.stack([np.real(np.fft.ifft2(np.fft.fft2(img[..., c]) * g)) for c in range(img.shape[2])],
                        -1).astype(np.float32)
    return np.real(np.fft.ifft2(np.fft.fft2(img) * g)).astype(np.float32)


def blur_aniso(img: np.ndarray, sx: float, sy: float) -> np.ndarray:
    n0, n1 = img.shape[:2]
    f0 = np.fft.fftfreq(n0)[:, None]
    f1 = np.fft.fftfreq(n1)[None, :]
    g = np.exp(-2.0 * (math.pi ** 2) * ((sy ** 2) * f0 ** 2 + (sx ** 2) * f1 ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(img) * g)).astype(np.float32)


def sample(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear periodic sampling at float pixel coords (x = column, y = row)."""
    h, w = img.shape[:2]
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = (x - x0).astype(np.float32)
    fy = (y - y0).astype(np.float32)
    x0m, y0m = x0 % w, y0 % h
    x1m, y1m = (x0 + 1) % w, (y0 + 1) % h
    if img.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    a = img[y0m, x0m] * (1 - fx) + img[y0m, x1m] * fx
    b = img[y1m, x0m] * (1 - fx) + img[y1m, x1m] * fx
    return (a * (1 - fy) + b * fy).astype(np.float32)


def warp(img: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    return sample(img, xx + dx, yy + dy)


def remap(x, a, b):
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    """a + (b-a)*t. A 2D scalar field t is broadcast over RGB when a or b is a colour (3,) or image."""
    if isinstance(t, np.ndarray) and t.ndim == 2 and (np.ndim(a) in (1, 3) or np.ndim(b) in (1, 3)):
        t = t[..., None]
    return a + (b - a) * t


def rgb(hexstr: str) -> np.ndarray:
    hexstr = hexstr.lstrip("#")
    return np.array([int(hexstr[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def colorize(t: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """Map scalar field t (0..1) through colour stops [(pos, '#hex'), ...]."""
    pos = np.array([p for p, _ in stops], np.float32)
    cols = np.stack([rgb(c) for _, c in stops])
    out = np.empty(t.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def hsv_jitter(col: np.ndarray, dv: np.ndarray, ds: np.ndarray | float = 0.0) -> np.ndarray:
    """Cheap value/saturation jitter on an RGB image (dv, ds ~ +-0.1)."""
    lum = col.mean(-1, keepdims=True)
    if np.ndim(ds):
        ds = ds[..., None]
    if np.ndim(dv):
        dv = dv[..., None]
    out = lum + (col - lum) * (1.0 + ds)
    return np.clip(out * (1.0 + dv), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Feature stamping (periodic)
# ---------------------------------------------------------------------------
def _canvas(n: int, mode="L"):
    return Image.new(mode, (n, n), 0)


def wrap_draw(n: int, draw_fn, supersample: int = 1) -> np.ndarray:
    """Draw with PIL on an n*3 canvas and fold the 3x3 tiles together -> periodic mask in [0,1].
    draw_fn(draw, off_x, off_y, ss) is called once with the centre offset (n, n)."""
    N = n * 3 * supersample
    im = Image.new("L", (N, N), 0)
    d = ImageDraw.Draw(im)
    draw_fn(d, n * supersample, n * supersample, supersample)
    if supersample > 1:
        im = im.resize((n * 3, n * 3), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255.0
    out = np.zeros((n, n), np.float32)
    for i in range(3):
        for j in range(3):
            out = np.maximum(out, a[i * n:(i + 1) * n, j * n:(j + 1) * n])
    return out


def crack_mask(n: int, seed: int, count: int = 6, length_px: tuple[int, int] = (80, 320),
               width_px: float = 1.6, branch: float = 0.35, vertical_bias: float = 0.0) -> np.ndarray:
    """Thin random-walk cracks with branching, periodic."""
    rng = np.random.default_rng(seed)

    def draw(d, ox, oy, ss):
        for _ in range(count):
            x, y = rng.uniform(0, n), rng.uniform(0, n)
            ang = rng.uniform(0, 2 * math.pi)
            if vertical_bias > 0 and rng.random() < vertical_bias:
                ang = math.pi / 2 + rng.normal(0, 0.4)
            L = int(rng.integers(*length_px))
            stack = [(x, y, ang, L, width_px)]
            while stack:
                x, y, ang, L, w = stack.pop()
                pts = [(x, y)]
                for _s in range(L // 4):
                    ang += rng.normal(0, 0.35)
                    x += math.cos(ang) * 4
                    y += math.sin(ang) * 4
                    pts.append((x, y))
                    if rng.random() < branch * 0.02 and w > 0.8:
                        stack.append((x, y, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.2), L // 2, w * 0.7))
                for dx in (-n, 0, n):
                    for dy in (-n, 0, n):
                        P = [((px + dx + ox) * ss, (py + dy + oy) * ss) for px, py in pts]
                        d.line(P, fill=255, width=max(1, int(round(w * ss))))
    return wrap_draw(n, draw, supersample=2)


def blobs(n: int, seed: int, count: int, rmin: float, rmax: float, warp_amt: float = 0.25,
          rect: bool = False) -> np.ndarray:
    """Irregular blobs / patches (periodic), values 0..1 (soft edged)."""
    rng = np.random.default_rng(seed)

    def draw(d, ox, oy, ss):
        for _ in range(count):
            cx, cy = rng.uniform(0, n), rng.uniform(0, n)
            r = rng.uniform(rmin, rmax)
            if rect:
                w = r * rng.uniform(0.8, 2.0)
                h = r * rng.uniform(0.6, 1.6)
                for dx in (-n, 0, n):
                    for dy in (-n, 0, n):
                        x0, y0 = cx - w / 2 + dx + ox, cy - h / 2 + dy + oy
                        d.rectangle([x0 * ss, y0 * ss, (x0 + w) * ss, (y0 + h) * ss], fill=255)
            else:
                k = 18
                ph = rng.uniform(0, 6.28, 3)
                pts = []
                for i in range(k):
                    a = 2 * math.pi * i / k
                    rr = r * (1 + warp_amt * (math.sin(a * 2 + ph[0]) * 0.5 + math.sin(a * 3 + ph[1]) * 0.3
                                              + math.sin(a * 5 + ph[2]) * 0.2))
                    pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
                for dx in (-n, 0, n):
                    for dy in (-n, 0, n):
                        d.polygon([((px + dx + ox) * ss, (py + dy + oy) * ss) for px, py in pts], fill=255)
    m = wrap_draw(n, draw)
    # warp the edges so they become ragged
    wx = spectral(n, seed + 11, 1.6, 4, 64) * warp_amt * rmax * 0.25
    wy = spectral(n, seed + 12, 1.6, 4, 64) * warp_amt * rmax * 0.25
    return warp(m, wx, wy)


def voronoi(n: int, seed: int, count: int, jitter: float = 1.0):
    """Periodic Voronoi: returns (F1 distance px, F2-F1 edge distance px, cell id)."""
    rng = np.random.default_rng(seed)
    g = int(math.ceil(math.sqrt(count)))
    pts = []
    for i in range(g):
        for j in range(g):
            pts.append(((j + 0.5 + (rng.random() - 0.5) * jitter) * n / g,
                        (i + 0.5 + (rng.random() - 0.5) * jitter) * n / g))
    pts = np.array(pts, np.float32)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    f1 = np.full((n, n), 1e9, np.float32)
    f2 = np.full((n, n), 1e9, np.float32)
    cid = np.zeros((n, n), np.int32)
    for k, (px, py) in enumerate(pts):
        dx = np.abs(xx - px)
        dx = np.minimum(dx, n - dx)
        dy = np.abs(yy - py)
        dy = np.minimum(dy, n - dy)
        d = np.sqrt(dx * dx + dy * dy)
        closer = d < f1
        f2 = np.where(closer, f1, np.minimum(f2, d))
        cid = np.where(closer, k, cid)
        f1 = np.where(closer, d, f1)
    return f1, f2 - f1, cid


def streaks(n: int, seed: int, density: float = 0.5, length: float = 6.0) -> np.ndarray:
    """Vertical drip / rain streak field (periodic) in [0, 1]."""
    s = spectral(n, seed, 1.0, 2, n / 3, aniso=(1.0, length))
    s2 = spectral(n, seed + 1, 2.0, 1, 8)
    v = np.clip((s * 0.6 + s2 * 0.4) / 3 + 0.5, 0, 1)
    return smoothstep(1.0 - density * 0.6, 1.0, v)


# ---------------------------------------------------------------------------
# Derived maps
# ---------------------------------------------------------------------------
def normal_from_height(h_m: np.ndarray, tile_m: float, strength: float = 1.0) -> np.ndarray:
    """Height in metres -> OpenGL tangent-space normal (float -1..1, HxWx3)."""
    n = h_m.shape[0]
    px = tile_m / n
    dhdx = (np.roll(h_m, -1, 1) - np.roll(h_m, 1, 1)) / (2 * px)
    dhdv = -(np.roll(h_m, -1, 0) - np.roll(h_m, 1, 0)) / (2 * px)  # rows go down, v goes up
    nx = -dhdx * strength
    ny = -dhdv * strength
    nz = np.ones_like(nx)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / l, ny / l, nz / l], -1).astype(np.float32)


def cavity_ao(h_m: np.ndarray, tile_m: float, radius_m: float = 0.02, depth_m: float = 0.004,
              strength: float = 1.0) -> np.ndarray:
    n = h_m.shape[0]
    sig = radius_m / (tile_m / n)
    b = blur(h_m, sig)
    occ = np.clip((b - h_m) / depth_m, 0.0, 1.0)
    return np.clip(1.0 - occ * strength, 0.0, 1.0)


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def to_u8(a: np.ndarray) -> np.ndarray:
    return (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def save_rgb(path: str, a: np.ndarray, quality: int = 90) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.fromarray(to_u8(a), "RGB")
    if path.endswith(".jpg"):
        im.save(path, quality=quality, subsampling=0, optimize=True)
    else:
        im.save(path, optimize=True)


def save_rgba(path: str, a: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(to_u8(a), "RGBA").save(path, optimize=True)


def save_normal(path: str, nrm: np.ndarray) -> None:
    save_rgb(path, nrm * 0.5 + 0.5)


def save_set(out_dir: str, name: str, albedo: np.ndarray, normal: np.ndarray, ao: np.ndarray,
             rough: np.ndarray, metal: np.ndarray | float = 0.0) -> dict:
    """Writes <name>_albedo.jpg, <name>_normal.png, <name>_orm.jpg (R=AO G=rough B=metal)."""
    if not isinstance(metal, np.ndarray):
        metal = np.full_like(rough, float(metal))
    orm = np.stack([ao, rough, metal], -1)
    p = {
        "albedo": os.path.join(out_dir, f"{name}_albedo.jpg"),
        "normal": os.path.join(out_dir, f"{name}_normal.png"),
        "orm": os.path.join(out_dir, f"{name}_orm.jpg"),
    }
    save_rgb(p["albedo"], albedo, 90)
    save_normal(p["normal"], normal)
    save_rgb(p["orm"], orm, 92)
    return p
