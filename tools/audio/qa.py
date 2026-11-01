"""Listen-by-analysis: spectrogram PNGs, waveform strips, loudness/peak/DC/seam checks."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import dsp

# perceptual colour map (dark violet -> magenta -> orange -> pale yellow), "magma"-like
_CMAP_PTS = np.array([
    [0.00, 0, 0, 4], [0.13, 28, 16, 68], [0.25, 79, 18, 123], [0.38, 129, 37, 129], [0.50, 181, 54, 122],
    [0.63, 229, 80, 100], [0.75, 251, 135, 97], [0.88, 254, 194, 135], [1.00, 252, 253, 191]])


def _cmap(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0, 1)
    out = np.zeros(v.shape + (3,), np.uint8)
    for c in range(3):
        out[..., c] = np.interp(v, _CMAP_PTS[:, 0], _CMAP_PTS[:, c + 1]).astype(np.uint8)
    return out


def _font(size=12):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def spectrogram_img(x: np.ndarray, width: int = 800, height: int = 220, fmin: float = 30.0, fmax: float = 20000.0,
                    dyn_db: float = 80.0, sr: int = dsp.SR) -> Image.Image:
    m = dsp.mono(x)
    nfft = 2048 if len(m) > 4096 else 512
    hop = max(1, (len(m) - nfft) // width) if len(m) > nfft else 1
    if len(m) < nfft:
        m = dsp.pad_to(m, nfft)
    idx = np.arange(0, len(m) - nfft + 1, hop)[:width * 2]
    win = np.hanning(nfft)
    frames = np.stack([m[i:i + nfft] * win for i in idx])
    S = np.abs(np.fft.rfft(frames, axis=1)) + 1e-10
    Sdb = 20 * np.log10(S / (nfft / 4))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    # log-frequency rows
    rows = np.geomspace(fmin, fmax, height)[::-1]
    fi = np.clip(np.searchsorted(freqs, rows), 1, len(freqs) - 1)
    img = Sdb[:, fi].T  # (height, frames)
    top = 0.0
    v = (img - (top - dyn_db)) / dyn_db
    rgb = _cmap(v)
    im = Image.fromarray(rgb).resize((width, height), Image.BILINEAR)
    return im


def wave_img(x: np.ndarray, width: int = 800, height: int = 80) -> Image.Image:
    im = Image.new("RGB", (width, height), (18, 18, 24))
    d = ImageDraw.Draw(im)
    chans = [x] if x.ndim == 1 else [x[:, 0], x[:, 1]]
    hh = height / len(chans)
    for ci, c in enumerate(chans):
        n = len(c)
        edges = np.linspace(0, n, width + 1).astype(int)
        mid = hh * ci + hh / 2
        d.line([(0, mid), (width, mid)], fill=(50, 50, 60))
        for px in range(width):
            seg = c[edges[px]:max(edges[px] + 1, edges[px + 1])]
            if len(seg) == 0:
                continue
            lo, hi = seg.min(), seg.max()
            clip = max(abs(lo), abs(hi)) >= 0.995
            col = (255, 60, 60) if clip else (120, 200, 255)
            d.line([(px, mid - hi * hh / 2), (px, mid - lo * hh / 2)], fill=col)
    return im


def stats(x: np.ndarray, loop: bool = False) -> dict:
    s = {
        "dur": len(x) / dsp.SR,
        "peak_db": dsp.to_db(np.abs(x).max()),
        "true_peak_db": dsp.true_peak_db(x),
        "dc": float(np.abs(np.mean(x, axis=0)).max()),
        "lufs_i": dsp.lufs_integrated(x),
        "lufs_m_max": dsp.lufs_momentary_max(x),
        "clipped": int((np.abs(x) >= 0.999).sum()),
    }
    if loop:
        s["seam"] = dsp.seam_discontinuity(x)
    return s


def render_card(x: np.ndarray, title: str, path: str, loop: bool = False, info: dict | None = None, width: int = 900) -> dict:
    st = stats(x, loop)
    if info:
        st.update(info)
    sp = spectrogram_img(x, width, 220)
    wv = wave_img(x, width, 70)
    extra = None
    if loop:
        # seam panel: last 1.5 s + first 1.5 s, should look continuous across the centre line
        k = min(dsp.ns(1.5), len(x) // 2)
        seam = np.concatenate([x[-k:], x[:k]], axis=0)
        extra = spectrogram_img(seam, width // 2, 140)
        zoom = np.concatenate([x[-dsp.ns(0.01):], x[:dsp.ns(0.01)]], axis=0)
        zw = wave_img(zoom, width // 2, 140)
    H = 26 + 220 + 70 + (150 if loop else 0) + 22
    im = Image.new("RGB", (width, H), (10, 10, 14))
    d = ImageDraw.Draw(im)
    f = _font(13)
    d.text((6, 5), title, fill=(240, 240, 240), font=f)
    im.paste(sp, (0, 26))
    # frequency gridlines labels
    for fr in (100, 1000, 10000):
        y = 26 + int((1 - (np.log(fr) - np.log(30)) / (np.log(20000) - np.log(30))) * 220)
        d.line([(0, y), (12, y)], fill=(255, 255, 255))
        d.text((14, y - 7), f"{fr if fr < 1000 else str(fr // 1000) + 'k'}", fill=(220, 220, 220), font=_font(10))
    im.paste(wv, (0, 246))
    y0 = 316
    if loop:
        im.paste(extra, (0, y0 + 5))
        im.paste(zw, (width // 2, y0 + 5))
        d.line([(width // 4, y0 + 5), (width // 4, y0 + 145)], fill=(0, 255, 120))
        d.line([(width * 3 // 4, y0 + 5), (width * 3 // 4, y0 + 145)], fill=(0, 255, 120))
        d.text((4, y0 + 6), "loop seam (end|start)", fill=(0, 255, 120), font=_font(10))
        y0 += 150
    txt = (f"{st['dur']:.2f}s  peak {st['peak_db']:.1f} dBFS  TP {st['true_peak_db']:.1f}  "
           f"LUFS-I {st['lufs_i']:.1f}  M-max {st['lufs_m_max']:.1f}  DC {st['dc']:.4f}")
    if loop:
        txt += f"  seam {st['seam']:.2f}"
    d.text((6, y0 + 3), txt, fill=(200, 220, 200), font=_font(12))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return st


def contact_sheet(items: list[tuple[str, np.ndarray]], path: str, cols: int = 4, cell_w: int = 300, cell_h: int = 120) -> None:
    rows = (len(items) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell_w, rows * (cell_h + 18)), (10, 10, 14))
    d = ImageDraw.Draw(im)
    f = _font(11)
    for i, (name, x) in enumerate(items):
        r, c = divmod(i, cols)
        sp = spectrogram_img(x, cell_w - 4, cell_h - 30)
        wv = wave_img(x, cell_w - 4, 28)
        X, Y = c * cell_w + 2, r * (cell_h + 18)
        d.text((X, Y + 2), f"{name} ({len(x) / dsp.SR:.2f}s)", fill=(235, 235, 235), font=f)
        im.paste(sp, (X, Y + 16))
        im.paste(wv, (X, Y + 16 + cell_h - 30))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
