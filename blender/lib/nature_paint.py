"""Procedural 2-D painter for leaf / flower / bark textures (numpy + Pillow, no bpy).

Leaves are rendered analytically (signed distance to a parametric leaf outline in a bent leaf
frame), so edges are anti-aliased without supersampling and every leaf gets its own midrib,
lateral veins, colour gradient, blemishes, drop shadow on what lies below, a height field (for
the normal map), a translucency value and a roughness value.

Canvas channels: col (linear-ish sRGB floats 0..1), a (coverage), h (height), tr (translucency),
rough (roughness), ao (occlusion from overlapping leaves).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

f32 = np.float32


# ---------------------------------------------------------------------------
# noise
# ---------------------------------------------------------------------------
def fft_noise(h: int, w: int, rng: np.random.Generator, beta: float = 2.0, ax: float = 1.0, ay: float = 1.0,
              lo: float = 0.0, hi: float = 1e9) -> np.ndarray:
    """Tileable fractal noise with power spectrum 1/f^beta, anisotropic (ax, ay stretch the
    frequency axes: ay > 1 = features elongated vertically). Normalised to 0..1."""
    ky = np.fft.fftfreq(h)[:, None] * h
    kx = np.fft.rfftfreq(w)[None, :] * w
    k = np.sqrt((kx * ax) ** 2 + (ky * ay) ** 2)
    k[0, 0] = 1.0
    amp = 1.0 / k ** (beta * 0.5 + 0.5)
    amp[(k < lo) | (k > hi)] = 0.0
    amp[0, 0] = 0.0
    ph = rng.normal(size=(h, w // 2 + 1)) + 1j * rng.normal(size=(h, w // 2 + 1))
    n = np.fft.irfft2(ph * amp, s=(h, w)).astype(f32)
    n = (n - n.mean()) / max(1e-9, float(n.std()))
    return np.clip(0.5 + n / 6.0, 0.0, 1.0)      # +-3 sigma -> 0..1


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blur(img: np.ndarray, r: int, wrap: bool = True) -> np.ndarray:
    """Separable box blur (3 passes ~ gaussian)."""
    out = img.astype(f32)
    for _ in range(3):
        for ax in (0, 1):
            acc = np.zeros_like(out)
            for d in range(-r, r + 1):
                acc += np.roll(out, d, axis=ax)
            out = acc / (2 * r + 1)
    return out


def height_to_normal(hgt: np.ndarray, strength: float, wrap: bool = True) -> np.ndarray:
    """OpenGL (Y+) tangent-space normal map from a height field (rows grow downward)."""
    if wrap:
        dx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5
        dy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5
    else:
        dy, dx = np.gradient(hgt)
    nx = -dx * strength
    ny = dy * strength
    nz = np.ones_like(hgt)
    l = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return (n * 0.5 + 0.5)


def save_rgb(path: str, arr: np.ndarray, quality: int = 92) -> None:
    im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    if path.endswith(".jpg"):
        im.save(path, quality=quality, subsampling=0)
    else:
        im.save(path, optimize=True)


def save_rgba(path: str, rgb: np.ndarray, a: np.ndarray) -> None:
    arr = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)[..., None]], -1)
    Image.fromarray((arr * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def save_gray(path: str, g: np.ndarray, quality: int = 92) -> None:
    im = Image.fromarray((np.clip(g, 0, 1) * 255 + 0.5).astype(np.uint8), "L")
    if path.endswith(".jpg"):
        im.save(path, quality=quality)
    else:
        im.save(path, optimize=True)


# ---------------------------------------------------------------------------
# leaf shapes: half-width profile s(t), t = 0 base .. 1 tip, max ~1
# ---------------------------------------------------------------------------
SHAPES = {
    "ovate": (0.55, 0.95),
    "elliptic": (0.6, 0.6),
    "lanceolate": (0.45, 1.25),
    "oblanceolate": (1.0, 0.55),
    "obovate": (1.2, 0.45),
    "linear": (0.12, 0.35),
    "blade": (0.08, 0.9),
    "round": (0.5, 0.5),
    "stem": (0.0, 0.0),
    "petal": (0.9, 0.5),
    "bract": (0.7, 0.75),
}


def shape_profile(name: str, t: np.ndarray) -> np.ndarray:
    a, b = SHAPES[name]
    if name == "stem":
        return np.ones_like(t) * (1.0 - 0.35 * t)
    tc = np.clip(t, 1e-4, 1 - 1e-4)
    s = tc ** a * (1 - tc) ** b
    # normalise to max 1
    tm = a / (a + b)
    m = tm ** a * (1 - tm) ** b
    return s / m


# ---------------------------------------------------------------------------
# canvas
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, w: int, h: int, seed: int = 1):
        self.w, self.h = w, h
        self.rng = np.random.default_rng(seed)
        self.col = np.zeros((h, w, 3), f32)
        self.a = np.zeros((h, w), f32)
        self.hgt = np.zeros((h, w), f32)
        self.tr = np.zeros((h, w), f32)
        self.rough = np.full((h, w), 0.6, f32)
        self.ao = np.ones((h, w), f32)
        self.noise = fft_noise(h, w, self.rng, beta=1.6)
        self.noise_hi = fft_noise(h, w, self.rng, beta=0.6)
        self.clip = (0, 0, w, h)   # current cell clip rect x0, y0, x1, y1

    def set_clip(self, rect, margin: int = 3):
        x, y, w, h = rect
        self.clip = (x + margin, y + margin, x + w - margin, y + h - margin)

    # -- primitive: one bent leaf / petal / stem segment ------------------------------------------
    def leaf(self, base, ang: float, length: float, width: float, shape: str = "ovate", color=(0.2, 0.35, 0.1),
             color_tip=None, bend: float = 0.0, midrib: float = 0.35, veins: float = 0.5, vein_spacing: float = 0.12,
             vein_slope: float = 0.9, thickness: float = 1.0, trans: float = 0.6, rough: float = 0.55,
             shadow: float = 0.35, edge_col=None, spots: float = 0.0, serrate: float = 0.0, teeth: float = 12.0,
             underside: bool = False, lobe_notch: float = 0.0, grain: float = 0.08, height_bias: float = 0.0,
             vein_col: float = 1.0, fit: bool = True):
        """Draw a leaf whose base is at `base` (px), pointing at angle `ang` (radians, 0 = up the
        image, positive = clockwise), `length`/`width` in px. `bend` curves the midrib sideways
        (fraction of length at the tip)."""
        bx, by = base
        d = np.array([math.sin(ang), -math.cos(ang)])      # leaf axis in image coords
        n = np.array([-d[1], d[0]])                        # across (right-hand)
        if fit and shape != "stem":
            # shrink leaves that would poke out of the card cell (no hard clipped edges)
            m = 4.0
            cx0, cy0, cx1, cy1 = self.clip
            if not (cx0 + 1 <= bx <= cx1 - 1 and cy0 + 1 <= by <= cy1 - 1):
                return
            s = 1.0
            for _ in range(8):
                L, Wd = length * s, width * s
                probe = [(bx + d[0] * L * f + n[0] * Wd * g * 0.5 + n[0] * bend * L * f * f,
                          by + d[1] * L * f + n[1] * Wd * g * 0.5 + n[1] * bend * L * f * f)
                         for f, g in ((1.0, 0.0), (0.5, 1.0), (0.5, -1.0), (0.75, 0.8), (0.75, -0.8))]
                if all(cx0 + m <= px_ <= cx1 - m and cy0 + m <= py_ <= cy1 - m for px_, py_ in probe):
                    break
                s *= 0.85
            else:
                return
            if s < 0.5:
                return
            length, width = length * s, width * s
        ext = width * 0.6 + abs(bend) * length + 3
        pts = [np.array([bx, by]) + d * u + n * v for u in (-3, length + 3) for v in (-ext, ext)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0 = int(max(self.clip[0], math.floor(min(xs))))
        x1 = int(min(self.clip[2], math.ceil(max(xs)) + 1))
        y0 = int(max(self.clip[1], math.floor(min(ys))))
        y1 = int(min(self.clip[3], math.ceil(max(ys)) + 1))
        if x1 <= x0 or y1 <= y0 or length < 1:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
        px, py = xx + 0.5 - bx, yy + 0.5 - by
        u = px * d[0] + py * d[1]
        v = px * n[0] + py * n[1]
        t = u / length
        tcl = np.clip(t, 0, 1)
        vb = v - bend * length * tcl * tcl
        hw = 0.5 * width * shape_profile(shape, tcl)
        if serrate > 0:
            hw = hw * (1 - serrate * (0.5 + 0.5 * np.sin(tcl * teeth * 2 * math.pi)) ** 3)
        hw = np.maximum(hw, 0.35 if shape == "stem" else 0.0)
        sd = hw - np.abs(vb)
        cov = np.clip(sd + 0.5, 0, 1) * np.clip(u + 0.5, 0, 1) * np.clip(length - u + 0.5, 0, 1)
        if cov.max() <= 0:
            return
        rel = np.abs(vb) / np.maximum(hw, 1e-3)            # 0 at midrib, 1 at edge
        sy, sx = slice(y0, y1), slice(x0, x1)
        nz = self.noise[sy, sx]
        nzh = self.noise_hi[sy, sx]
        # ---- colour
        c0 = np.array(color, f32)
        c1 = np.array(color_tip if color_tip is not None else color, f32)
        col = c0[None, None, :] * (1 - tcl[..., None]) + c1[None, None, :] * tcl[..., None]
        if underside:
            col = col * 0.8 + np.array([0.12, 0.14, 0.1], f32) * 0.6
        shade = 0.88 + 0.24 * (nz - 0.5) + grain * (nzh - 0.5) * 2
        mid = np.exp(-(vb / max(0.6, width * 0.035 + 0.4)) ** 2) * midrib
        if veins > 0 and shape not in ("stem", "blade", "linear"):
            ph = (u - np.abs(vb) * vein_slope) / max(2.0, vein_spacing * length)
            vl = (1.0 - np.abs(np.mod(ph, 1.0) - 0.5) * 2.0) ** 10 * sstep(0.05, 0.2, 1 - rel) * sstep(0.02, 0.1, tcl)
            vl = vl * veins
        else:
            vl = np.zeros_like(u)
        light = (shade + 0.35 * mid * vein_col + 0.18 * vl * vein_col)
        col = col * light[..., None]
        if edge_col is not None:
            e = sstep(0.75, 1.0, rel) * 0.6
            col = col * (1 - e[..., None]) + np.array(edge_col, f32)[None, None, :] * e[..., None]
        if spots > 0:
            sp = sstep(0.82 - spots * 0.25, 0.9, self.noise_hi[sy, sx] * 0.5 + nz * 0.5)
            col = col * (1 - 0.55 * sp[..., None]) + np.array([0.32, 0.22, 0.08], f32)[None, None, :] * 0.55 * sp[..., None]
        # ---- height / translucency / roughness
        dome = np.sqrt(np.clip(1 - rel * rel, 0, 1)) * 0.6 * thickness
        hh = height_bias + dome - 0.45 * mid * thickness - 0.25 * vl * thickness + 0.12 * (nzh - 0.5)
        if shape == "stem":
            hh = height_bias + np.sqrt(np.clip(1 - rel * rel, 0, 1)) * thickness
        trv = trans * (1 - 0.6 * mid) * (1 - 0.4 * vl) * (0.85 + 0.3 * nz)
        rgh = rough + 0.1 * (nz - 0.5) + 0.12 * vl
        # ---- drop shadow onto what is below (offset down-right)
        if shadow > 0:
            sh = np.zeros_like(cov)
            o = 3
            sh[o:, o:] = cov[:-o, :-o]
            k = 1 - shadow * sh * self.a[sy, sx]
            self.col[sy, sx] *= k[..., None]
            self.ao[sy, sx] *= k
        a = cov
        ia = 1 - a
        self.col[sy, sx] = self.col[sy, sx] * ia[..., None] + col * a[..., None]
        self.hgt[sy, sx] = self.hgt[sy, sx] * ia + hh * a
        self.tr[sy, sx] = self.tr[sy, sx] * ia + trv * a
        self.rough[sy, sx] = self.rough[sy, sx] * ia + rgh * a
        self.ao[sy, sx] = self.ao[sy, sx] * ia + 1.0 * a
        self.a[sy, sx] = np.maximum(self.a[sy, sx], a)

    def disc(self, c, r: float, color, hgt: float = 0.5, rough: float = 0.5, trans: float = 0.2, shadow: float = 0.3):
        """Small sphere-ish blob (figs, buds, flower centres, berries)."""
        cx, cy = c
        x0, x1 = int(max(self.clip[0], cx - r - 2)), int(min(self.clip[2], cx + r + 3))
        y0, y1 = int(max(self.clip[1], cy - r - 2)), int(min(self.clip[3], cy + r + 3))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
        d = np.sqrt((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2)
        cov = np.clip(r - d + 0.5, 0, 1)
        sy, sx = slice(y0, y1), slice(x0, x1)
        rel = np.clip(d / max(r, 0.5), 0, 1)
        dome = np.sqrt(1 - rel * rel)
        # simple lambert from upper-left for a 3-D read
        lx = np.clip(((cx - xx) + (cy - yy)) / max(r, 0.5) * 0.35 + 0.75, 0.4, 1.15)
        col = np.array(color, f32)[None, None, :] * (lx * (0.9 + 0.2 * self.noise_hi[sy, sx]))[..., None]
        if shadow > 0:
            sh = np.zeros_like(cov)
            sh[2:, 2:] = cov[:-2, :-2]
            k = 1 - shadow * sh * self.a[sy, sx]
            self.col[sy, sx] *= k[..., None]
        ia = 1 - cov
        self.col[sy, sx] = self.col[sy, sx] * ia[..., None] + col * cov[..., None]
        self.hgt[sy, sx] = self.hgt[sy, sx] * ia + (hgt + dome * 0.8) * cov
        self.tr[sy, sx] = self.tr[sy, sx] * ia + trans * cov
        self.rough[sy, sx] = self.rough[sy, sx] * ia + rough * cov
        self.ao[sy, sx] = self.ao[sy, sx] * ia + cov
        self.a[sy, sx] = np.maximum(self.a[sy, sx], cov)

    def curve(self, pts, w0: float, w1: float, color, **kw):
        """Tapered stem/twig along a polyline of points (px)."""
        n = len(pts) - 1
        for i in range(n):
            p, q = np.array(pts[i], f32), np.array(pts[i + 1], f32)
            dv = q - p
            L = float(np.linalg.norm(dv))
            if L < 0.5:
                continue
            ang = math.atan2(dv[0], -dv[1])
            w = w0 + (w1 - w0) * (i / max(1, n))
            self.leaf(p - dv / L * 0.5 * w * 0.5, ang, L + w * 0.5, w, shape="stem", color=color,
                      midrib=0, veins=0, trans=kw.get("trans", 0.1), rough=kw.get("rough", 0.7),
                      shadow=kw.get("shadow", 0.25), thickness=kw.get("thickness", 1.0), height_bias=0.0)

    # -- finishing -----------------------------------------------------------------------------
    def bleed(self) -> None:
        """Push leaf colours into transparent texels (no dark fringes when mip-mapped)."""
        a = (self.a > 0.02).astype(f32)
        num = self.col * a[..., None]
        den = a.copy()
        filled = self.col.copy()
        have = a > 0
        r = 2
        acc_n, acc_d = num, den
        for _ in range(9):
            acc_n = blur(acc_n, r)
            acc_d = blur(acc_d, r)
            fill = acc_d > 1e-4
            take = fill & ~have
            filled[take] = acc_n[take] / acc_d[take][..., None]
            have = have | take
            r *= 2
            if have.all():
                break
        filled[~have] = self.col[self.a > 0.5].mean(0) if (self.a > 0.5).any() else 0.2
        self.col = np.where((self.a > 0.02)[..., None], self.col, filled)

    def save(self, prefix: str, normal_strength: float = 2.0) -> dict:
        self.bleed()
        save_rgba(prefix + "_albedo.png", self.col, self.a)
        hb = blur(self.hgt, 1, wrap=False)
        nrm = height_to_normal(hb, normal_strength, wrap=False)
        save_rgb(prefix + "_normal.png", nrm)
        orm = np.stack([np.clip(0.55 + 0.45 * self.ao, 0, 1), np.clip(self.rough, 0.05, 1), np.zeros_like(self.ao)], -1)
        save_rgb(prefix + "_orm.jpg", orm)
        tr = blur(self.tr * self.a, 1, wrap=False)
        save_gray(prefix + "_trans.jpg", tr)
        return {"albedo": prefix + "_albedo.png", "normal": prefix + "_normal.png", "orm": prefix + "_orm.jpg",
                "trans": prefix + "_trans.jpg"}


def jitter(rng, c, amt=0.08):
    c = np.array(c, f32)
    k = 1 + rng.normal(0, amt)
    hue = rng.normal(0, amt * 0.6, 3)
    return tuple(np.clip(c * k * (1 + hue), 0.0, 1.0))
