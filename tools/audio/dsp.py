"""Core DSP toolkit for Mèo Cam procedural audio.

Everything here is vectorised numpy/scipy. Signals are float64 numpy arrays:
mono = shape (n,), stereo = shape (n, 2). Sample rate is fixed at SR (44.1 kHz).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter1d, minimum_filter1d

SR = 44100
TAU = 2.0 * np.pi


# --------------------------------------------------------------------------- basics
def ns(t: float, sr: int = SR) -> int:
    """Seconds -> samples."""
    return max(0, int(round(t * sr)))


def tvec(n: int, sr: int = SR) -> np.ndarray:
    return np.arange(n) / sr


def rng_for(*keys) -> np.random.Generator:
    h = hashlib.md5("|".join(str(k) for k in keys).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def to_db(x: float) -> float:
    return 20.0 * np.log10(max(float(x), 1e-12))


def mono(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 1 else x.mean(axis=1)


def stereo(x: np.ndarray) -> np.ndarray:
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def pad_to(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    shape = (n - len(x),) + x.shape[1:]
    return np.concatenate([x, np.zeros(shape)], axis=0)


def place(buf: np.ndarray, snd: np.ndarray, start: int, gain: float = 1.0) -> None:
    """Mix `snd` into `buf` at sample `start` (clipped to bounds). Handles mono->stereo."""
    if start >= len(buf) or len(snd) == 0:
        return
    s0 = max(0, start)
    off = s0 - start
    end = min(len(buf), start + len(snd))
    if end <= s0:
        return
    seg = snd[off:off + (end - s0)] * gain
    if buf.ndim == 2 and seg.ndim == 1:
        seg = seg[:, None]
    buf[s0:end] += seg


def place_wrap(buf: np.ndarray, snd: np.ndarray, start: int, gain: float = 1.0) -> None:
    """Mix with wrap-around (for building seamless loops)."""
    n = len(buf)
    start %= n
    pos = 0
    while pos < len(snd):
        s = (start + pos) % n
        chunk = min(len(snd) - pos, n - s)
        seg = snd[pos:pos + chunk] * gain
        if buf.ndim == 2 and seg.ndim == 1:
            seg = seg[:, None]
        buf[s:s + chunk] += seg
        pos += chunk


# --------------------------------------------------------------------------- noise
def white(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(n)


def colored(n: int, rng: np.random.Generator, slope_db_oct: float, f_lo: float = 10.0) -> np.ndarray:
    """Noise with a spectral slope (dB/octave). -3 = pink, -6 = brown."""
    if n == 0:
        return np.zeros(0)
    m = int(2 ** np.ceil(np.log2(max(n, 16))))
    spec = np.fft.rfft(rng.standard_normal(m))
    f = np.fft.rfftfreq(m, 1.0 / SR)
    f[0] = f[1]
    g = (np.maximum(f, f_lo) / 1000.0) ** (slope_db_oct / 6.0206)
    out = np.fft.irfft(spec * g, m)[:n]
    return out / (np.std(out) + 1e-12)


def pink(n, rng):
    return colored(n, rng, -3.0)


def brown(n, rng):
    return colored(n, rng, -6.0, f_lo=15.0)


def smooth_noise(n: int, rate_hz: float, rng: np.random.Generator, sr: int = SR) -> np.ndarray:
    """Band-limited random modulation signal in roughly [-1, 1] (cubic-interpolated control points)."""
    if n == 0:
        return np.zeros(0)
    k = max(4, int(n / sr * rate_hz) + 4)
    pts = rng.uniform(-1, 1, k)
    xs = np.linspace(0, n, k)
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(xs, pts, bc_type="natural")
    out = cs(np.arange(n))
    return np.clip(out, -1.5, 1.5)


def smooth_noise_periodic(n: int, rate_hz: float, rng: np.random.Generator, sr: int = SR) -> np.ndarray:
    """Like smooth_noise but periodic over n samples (for seamless loops)."""
    k = max(4, int(n / sr * rate_hz))
    pts = rng.uniform(-1, 1, k)
    from scipy.interpolate import CubicSpline
    xs = np.linspace(0, n, k + 1)
    cs = CubicSpline(xs, np.append(pts, pts[0]), bc_type="periodic")
    return cs(np.arange(n))


# --------------------------------------------------------------------------- filters
def butter(x: np.ndarray, kind: str, f, order: int = 2, sr: int = SR) -> np.ndarray:
    nyq = sr / 2
    if kind in ("low", "high"):
        f = min(max(f, 5.0), nyq * 0.98)
    else:
        f = [min(max(f[0], 5.0), nyq * 0.97), min(max(f[1], 6.0), nyq * 0.98)]
        if f[1] <= f[0] * 1.01:
            f[1] = f[0] * 1.02
    sos = signal.butter(order, f, btype={"low": "lowpass", "high": "highpass", "band": "bandpass"}[kind], fs=sr, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def lp(x, f, order=2, sr=SR):
    return butter(x, "low", f, order, sr)


def hp(x, f, order=2, sr=SR):
    return butter(x, "high", f, order, sr)


def bp(x, lo, hi, order=2, sr=SR):
    return butter(x, "band", (lo, hi), order, sr)


def rbj(kind: str, f0: float, q: float = 0.707, gain_db: float = 0.0, sr: int = SR):
    """RBJ cookbook biquad (b, a)."""
    f0 = min(max(f0, 5.0), sr * 0.49)
    A = 10 ** (gain_db / 40)
    w0 = TAU * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "lowshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa)]
        a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    elif kind == "highshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa)]
        a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
    elif kind == "bandpass":  # constant 0 dB peak gain
        b = [alpha, 0, -alpha]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "lowpass":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "highpass":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    elif kind == "notch":
        b = [1, -2 * cw, 1]
        a = [1 + alpha, -2 * cw, 1 - alpha]
    else:
        raise ValueError(kind)
    b = np.array(b) / a[0]
    a = np.array(a) / a[0]
    return b, a


def biquad(x, kind, f0, q=0.707, gain_db=0.0, sr=SR):
    b, a = rbj(kind, f0, q, gain_db, sr)
    return signal.lfilter(b, a, x, axis=0)


def peak(x, f0, q, gain_db, sr=SR):
    return biquad(x, "peak", f0, q, gain_db, sr)


def reson(x, f0, bw, sr=SR):
    """Band-pass resonator, unity gain at f0."""
    return biquad(x, "bandpass", f0, max(f0 / max(bw, 1.0), 0.3), 0.0, sr)


def onepole_lp(x, fc, sr=SR):
    a = np.exp(-TAU * fc / sr)
    return signal.lfilter([1 - a], [1, -a], x, axis=0)


def dc_block(x, fc=12.0, sr=SR):
    return hp(x, fc, 1, sr)


def tilt(x, db_per_oct, pivot=1000.0, sr=SR):
    """Gentle spectral tilt via shelves."""
    y = biquad(x, "highshelf", pivot, 0.5, db_per_oct * 2.0, sr)
    return y


# --------------------------------------------------------------------------- STFT-domain shaping
def stft_shape(x: np.ndarray, gain_fn, nperseg: int = 1024, sr: int = SR) -> np.ndarray:
    """Time-varying linear filtering in the STFT domain.
    gain_fn(freqs[F], times[T]) -> gains[F, T] (magnitude)."""
    n = len(x)
    if n < 8:
        return x.copy()
    hop = nperseg // 4
    f, t, Z = signal.stft(x, fs=sr, window="hann", nperseg=nperseg, noverlap=nperseg - hop, boundary="even", padded=True)
    G = gain_fn(f, t)
    _, y = signal.istft(Z * G, fs=sr, window="hann", nperseg=nperseg, noverlap=nperseg - hop, boundary=True)
    return pad_to(y, n)


def formant_mag(f: np.ndarray, F: np.ndarray, BW: np.ndarray) -> np.ndarray:
    """|H(f)| of a 2nd-order resonance normalised to 1 at DC (Klatt cascade element).
    Broadcasting: f and F/BW must be broadcast-compatible."""
    F2 = F * F
    return F2 / np.sqrt((F2 - f * f) ** 2 + (BW * f) ** 2 + 1e-9)


def formant_env(f: np.ndarray, formants) -> np.ndarray:
    """Product of formant magnitudes. formants: list of (F, BW) arrays/scalars broadcastable vs f."""
    g = np.ones(np.broadcast(f, *[np.asarray(F) for F, _ in formants]).shape)
    for F, BW in formants:
        g = g * formant_mag(f, F, BW)
    return g


# --------------------------------------------------------------------------- envelopes
def env_points(points, n: int, sr: int = SR, smooth: bool = True) -> np.ndarray:
    """Piecewise envelope from [(t_sec, value), ...]; smooth=True uses cosine (smoothstep) segments."""
    pts = sorted(points)
    ts = np.array([p[0] for p in pts]) * sr
    vs = np.array([p[1] for p in pts], dtype=float)
    x = np.arange(n, dtype=float)
    if not smooth:
        return np.interp(x, ts, vs)
    idx = np.clip(np.searchsorted(ts, x, side="right") - 1, 0, len(ts) - 2)
    t0, t1 = ts[idx], ts[idx + 1]
    u = np.clip((x - t0) / np.maximum(t1 - t0, 1e-9), 0, 1)
    u = u * u * (3 - 2 * u)
    out = vs[idx] + (vs[idx + 1] - vs[idx]) * u
    out[x < ts[0]] = vs[0]
    out[x > ts[-1]] = vs[-1]
    return out


def ar_env(n: int, attack: float, release_tau: float, sr: int = SR, curve: float = 1.0) -> np.ndarray:
    """Attack (raised-cosine) then exponential decay."""
    t = tvec(n, sr)
    a = np.clip(t / max(attack, 1e-5), 0, 1)
    a = 0.5 - 0.5 * np.cos(np.pi * a)
    d = np.exp(-np.maximum(t - attack, 0) / max(release_tau, 1e-5))
    return (a ** curve) * d


def adsr(n: int, a: float, d: float, s: float, r: float, sr: int = SR) -> np.ndarray:
    na, nd, nr = ns(a, sr), ns(d, sr), ns(r, sr)
    nsus = max(0, n - na - nd - nr)
    parts = [0.5 - 0.5 * np.cos(np.linspace(0, np.pi, na, endpoint=False)) if na else np.zeros(0),
             s + (1 - s) * np.exp(-5 * np.linspace(0, 1, nd)) if nd else np.zeros(0),
             np.full(nsus, s),
             s * (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, nr))) if nr else np.zeros(0)]
    return pad_to(np.concatenate(parts), n)


def fades(x: np.ndarray, fin: float = 0.002, fout: float = 0.01, sr: int = SR) -> np.ndarray:
    y = x.copy()
    a, b = ns(fin, sr), ns(fout, sr)
    if a > 0:
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
        y[:a] *= w if y.ndim == 1 else w[:, None]
    if b > 0:
        w = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, b))
        y[-b:] *= w if y.ndim == 1 else w[:, None]
    return y


def trim_silence(x: np.ndarray, thresh_db: float = -70.0, keep_tail: float = 0.02) -> np.ndarray:
    a = np.abs(mono(x))
    pk = a.max() if len(a) else 0
    if pk <= 0:
        return x
    th = pk * db(thresh_db)
    idx = np.nonzero(a > th)[0]
    end = min(len(x), idx[-1] + ns(keep_tail))
    return fades(x[:end], 0.0, min(0.02, end / SR / 4))


# --------------------------------------------------------------------------- oscillators
def phase_of(freq: np.ndarray, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    return phase0 + TAU * np.cumsum(freq) / sr


def osc(freq, n=None, sr=SR, phase0=0.0) -> np.ndarray:
    if np.isscalar(freq):
        freq = np.full(n, float(freq))
    return np.sin(phase_of(freq, sr, phase0))


def modal(n: int, freqs, decays, amps, sr: int = SR, phases=None, attack: float = 0.0) -> np.ndarray:
    """Sum of exponentially damped sinusoids (impact response). decays = T60-ish time constants (s, 1/e)."""
    freqs = np.asarray(freqs, float)
    decays = np.asarray(decays, float)
    amps = np.asarray(amps, float)
    ok = freqs < sr * 0.47
    freqs, decays, amps = freqs[ok], decays[ok], amps[ok]
    if phases is None:
        phases = np.zeros(len(freqs))
    else:
        phases = np.asarray(phases)[ok]
    out = np.zeros(n)
    t = tvec(n, sr)
    chunk = 8192
    for s in range(0, n, chunk):
        tt = t[s:s + chunk][:, None]
        out[s:s + chunk] = (amps * np.exp(-tt / decays) * np.sin(TAU * freqs * tt + phases)).sum(axis=1)
    if attack > 0:
        out *= np.clip(t / attack, 0, 1)
    return out


def resonator_bank(exc: np.ndarray, freqs, decays, amps, sr: int = SR) -> np.ndarray:
    """Drive a bank of 2-pole resonators with an excitation (for scrapes/rolls/rain on metal)."""
    out = np.zeros(len(exc))
    for f, d, a in zip(freqs, decays, amps):
        if f >= sr * 0.47:
            continue
        r = np.exp(-1.0 / (d * sr))
        w = TAU * f / sr
        b0 = (1 - r * r) * 0.5
        out += a * signal.lfilter([b0, 0, -b0], [1, -2 * r * np.cos(w), r * r], exc)
    return out


def click(n_len: int, rng, bright: float = 1.0) -> np.ndarray:
    """Short noisy click (excitation)."""
    x = rng.standard_normal(n_len) * np.exp(-np.arange(n_len) / max(1, n_len / 5))
    if bright < 1.0:
        x = lp(x, 500 + 18000 * bright)
    return x


def half_sine(n_len: int) -> np.ndarray:
    return np.sin(np.linspace(0, np.pi, max(n_len, 2)))


def frac_impulses(n: int, times_s: np.ndarray, amps: np.ndarray, sr: int = SR, taps: int = 8) -> np.ndarray:
    """Band-limited impulses at fractional sample times (windowed sinc), vectorised."""
    out = np.zeros(n + 2 * taps)
    pos = times_s * sr
    ip = np.floor(pos).astype(int)
    fr = pos - ip
    k = np.arange(-taps + 1, taps + 1)
    x = k[None, :] - fr[:, None]
    w = 0.5 + 0.5 * np.cos(np.pi * x / taps)
    ker = np.sinc(x) * w * amps[:, None]
    idx = ip[:, None] + k[None, :] + taps
    m = (idx >= 0) & (idx < len(out))
    np.add.at(out, idx[m], ker[m])
    return out[taps:taps + n]


def pulse_times(freq: np.ndarray, jitter: float, rng, sr: int = SR, phase0: float = 0.0) -> np.ndarray:
    """Times (s) of periodic events for an instantaneous frequency curve, with relative period jitter."""
    ph = phase0 + np.cumsum(freq) / sr  # in cycles
    total = ph[-1]
    if total < 1:
        return np.zeros(0)
    cycles = np.arange(np.ceil(ph[0]), np.floor(total))
    t = np.interp(cycles, ph, np.arange(len(freq))) / sr
    if jitter > 0 and len(t) > 1:
        per = np.diff(t, append=t[-1] + (t[-1] - t[-2]))
        t = t + rng.standard_normal(len(t)) * per * jitter
        t = np.sort(np.clip(t, 0, (len(freq) - 1) / sr))
    return t


# --------------------------------------------------------------------------- spatial
def pan(x: np.ndarray, p) -> np.ndarray:
    """Constant-power pan, p in [-1, 1] (scalar or per-sample)."""
    th = (np.asarray(p) + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=1)


def spatialize(x: np.ndarray, az, sr: int = SR) -> np.ndarray:
    """Cheap binaural-ish: ILD + head-shadow lowpass + ITD. az in radians (0 front, +pi/2 right).
    az may be scalar or per-sample array."""
    n = len(x)
    az = np.broadcast_to(np.asarray(az, float), (n,))
    s = np.sin(az)
    itd = 0.00062 * s  # seconds, + => right ear earlier
    shadowed = lp(x, 1800, 1)
    out = np.zeros((n, 2))
    idx = np.arange(n, dtype=float)
    for ch, sign in ((0, -1.0), (1, 1.0)):
        # ear facing source gets direct; opposite ear blend toward shadowed
        facing = np.clip(0.5 + 0.5 * sign * s, 0, 1)
        sig = x * (0.55 + 0.45 * facing) + shadowed * (1 - facing) * 0.35
        delay = np.maximum(0, -sign * itd) * sr
        out[:, ch] = np.interp(idx - delay, idx, sig, left=0)
    return out


def moving_source(src: np.ndarray, traj, sr: int = SR, c: float = 343.0, ref_dist: float = 1.0,
                  air: bool = True, binaural: bool = True, ground: bool = True) -> np.ndarray:
    """Render a moving point source heard by a listener at the origin facing +Y.
    traj(t_emit[s]) -> (x, y, z) arrays (metres; x right, y forward, z up).
    Handles Doppler (propagation delay), 1/r spreading, air absorption and a ground reflection."""
    n = len(src)
    te = np.arange(n) / sr
    x, y, z = traj(te)
    d = np.sqrt(x * x + y * y + z * z) + 1e-3
    ta = te + d / c
    tr = te  # receive times
    # emission time for each receive time
    tem = np.interp(tr, ta, te, left=-1.0, right=-1.0)
    valid = tem >= 0
    s_at = np.interp(tem * sr, np.arange(n), src, left=0, right=0) * valid
    d_at = np.interp(tem, te, d)
    g = ref_dist / np.maximum(d_at, ref_dist * 0.5)
    out_m = s_at * g
    if air:
        # crossfade between progressively darker versions according to distance
        dark1 = lp(out_m, 6000, 1)
        dark2 = lp(out_m, 1500, 2)
        dark3 = lp(out_m, 400, 2)
        u = np.clip(np.log2(np.maximum(d_at, 1) / 15.0) / 2.0, 0, 3)  # 15m->0, 60m->1 (6k), 240m->2 (1.5k), ~1km->3
        w0 = np.clip(1 - u, 0, 1)
        w1 = np.clip(1 - np.abs(u - 1), 0, 1)
        w2 = np.clip(1 - np.abs(u - 2), 0, 1)
        w3 = np.clip(u - 2, 0, 1)
        out_m = out_m * w0 + dark1 * w1 + dark2 * w2 + dark3 * w3
    if ground:
        # listener ear height ~0.25 m (cat!) => ground reflection very short; mild comb at high freq
        out_m = out_m + 0.35 * np.concatenate([np.zeros(3), out_m[:-3]])
    if binaural:
        xa = np.interp(tem, te, x)
        ya = np.interp(tem, te, y)
        az = np.arctan2(xa, ya)
        return spatialize(out_m, az, sr)
    return out_m


# --------------------------------------------------------------------------- reverb
def make_ir(rt60: float, sr: int = SR, predelay: float = 0.01, brightness: float = 0.6,
            er: int = 12, er_spread: float = 0.04, stereo_out: bool = True, rng=None, length: float | None = None) -> np.ndarray:
    """Synthetic room impulse response: early reflections + frequency-dependent exponential tail."""
    rng = rng or np.random.default_rng(1)
    L = ns(length if length else min(rt60 * 1.2, 8.0), sr)
    chans = 2 if stereo_out else 1
    out = np.zeros((L, chans))
    bands = [(20, 300, 1.25), (300, 1500, 1.0), (1500, 5000, 0.55 + 0.35 * brightness), (5000, 16000, 0.25 + 0.4 * brightness)]
    t = tvec(L, sr)
    pd = ns(predelay, sr)
    for ch in range(chans):
        tail = np.zeros(L)
        nz = rng.standard_normal(L)
        for lo, hi, k in bands:
            rt = rt60 * k
            b = bp(nz, lo, hi, 2) if lo > 20 else lp(nz, hi, 2)
            tail += b * np.exp(-6.9078 * t / rt)
        # soft onset of the diffuse tail
        onset = np.clip(t / max(predelay * 2 + 0.01, 0.005), 0, 1)
        tail *= onset
        tail = np.concatenate([np.zeros(pd), tail[:L - pd]])
        # early reflections
        for i in range(er):
            dt = predelay * 0.3 + rng.uniform(0.002, er_spread + predelay)
            k = ns(dt, sr)
            if k < L:
                tail[k] += rng.uniform(0.25, 0.9) * (-1 if rng.random() < 0.5 else 1) * np.exp(-dt * 6.9 / rt60) * 3.0
        out[:, ch] = tail
    out /= np.sqrt((out ** 2).sum() / chans) + 1e-12
    return out if stereo_out else out[:, 0]


def reverb(x: np.ndarray, ir: np.ndarray, wet: float = 0.3, dry: float = 1.0) -> np.ndarray:
    """Convolution reverb; output is stereo if ir is stereo. Output length = len(x) (tail truncated)."""
    n = len(x)
    xm = mono(x)
    if ir.ndim == 2:
        w = np.stack([signal.fftconvolve(xm, ir[:, c])[:n] for c in range(ir.shape[1])], axis=1)
        d = stereo(x)
    else:
        w = signal.fftconvolve(xm, ir)[:n]
        d = xm
    return d * dry + w * wet


def reverb_full(x: np.ndarray, ir: np.ndarray, wet: float = 0.3, dry: float = 1.0) -> np.ndarray:
    """Like reverb() but keeps the full tail (len(x)+len(ir)-1)."""
    xm = mono(x)
    n = len(xm) + len(ir) - 1
    if ir.ndim == 2:
        w = np.stack([signal.fftconvolve(xm, ir[:, c]) for c in range(ir.shape[1])], axis=1)
        d = pad_to(stereo(x), n)
    else:
        w = signal.fftconvolve(xm, ir)
        d = pad_to(xm, n)
    return d * dry + w * wet


def reverb_loop(x: np.ndarray, ir: np.ndarray, wet: float = 0.3, dry: float = 1.0) -> np.ndarray:
    """Circular convolution reverb: the tail wraps to the start, so loops stay seamless."""
    n = len(x)
    out = []
    xs = stereo(x)
    for c in range(2):
        irc = ir[:, c] if ir.ndim == 2 else ir
        m = n
        X = np.fft.rfft(xs[:, c], m)
        irp = np.zeros(m)
        L = min(len(irc), m)
        irp[:L] = irc[:L]
        out.append(np.fft.irfft(X * np.fft.rfft(irp, m), m)[:n])
    return xs * dry + np.stack(out, axis=1) * wet


# --------------------------------------------------------------------------- dynamics
def soft_clip(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


def _smooth_gain(g_block: np.ndarray, att: float, rel: float) -> np.ndarray:
    out = np.empty_like(g_block)
    cur = 1.0
    for i, g in enumerate(g_block):
        cur = cur + (g - cur) * (att if g < cur else rel)
        out[i] = cur
    return out


def compressor(x: np.ndarray, thr_db: float = -18, ratio: float = 3.0, attack: float = 0.01,
               release: float = 0.15, makeup_db: float = 0.0, block: int = 32, sr: int = SR) -> np.ndarray:
    a = np.abs(stereo(x)).max(axis=1)
    nb = int(np.ceil(len(a) / block))
    lv = np.sqrt(np.mean(pad_to(a, nb * block).reshape(nb, block) ** 2, axis=1) * 2) + 1e-9
    ldb = 20 * np.log10(lv)
    over = np.maximum(ldb - thr_db, 0)
    gdb = -over * (1 - 1 / ratio)
    g = 10 ** (gdb / 20)
    bt = block / sr
    g = _smooth_gain(g, 1 - np.exp(-bt / attack), 1 - np.exp(-bt / release))
    gs = np.interp(np.arange(len(a)), np.arange(nb) * block + block / 2, g) * db(makeup_db)
    return x * (gs if x.ndim == 1 else gs[:, None])


def limiter(x: np.ndarray, ceiling_db: float = -1.0, lookahead: float = 0.004, release: float = 0.08, sr: int = SR) -> np.ndarray:
    ceil = db(ceiling_db)
    a = np.abs(stereo(x)).max(axis=1)
    la = max(1, ns(lookahead, sr))
    pk = maximum_filter1d(a, size=2 * la + 1)
    g = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    g = minimum_filter1d(g, size=2 * la + 1)
    # release smoothing (only when gain rises)
    blk = 16
    nb = int(np.ceil(len(g) / blk))
    gb = pad_to(g, nb * blk).reshape(nb, blk).min(axis=1)
    gb = _smooth_gain(gb, 1.0, 1 - np.exp(-(blk / sr) / release))
    gs = np.minimum(g, np.repeat(gb, blk)[:len(g)])
    y = x * (gs if x.ndim == 1 else gs[:, None])
    return np.clip(y, -ceil, ceil)


# --------------------------------------------------------------------------- loudness (ITU-R BS.1770-4)
def _k_filters(sr: int = SR):
    G, Q, fc = 3.999843853973347, 0.7071752369554196, 1681.974450955533
    b1, a1 = rbj("highshelf", fc, Q, G, sr)
    b2, a2 = rbj("highpass", 38.13547087602444, 0.5003270373238773, 0.0, sr)
    return (b1, a1), (b2, a2)


def k_weight(x: np.ndarray, sr: int = SR) -> np.ndarray:
    (b1, a1), (b2, a2) = _k_filters(sr)
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)


def _block_loudness(x: np.ndarray, block_s: float, overlap: float, sr: int = SR) -> np.ndarray:
    y = stereo(k_weight(x, sr)) if x.ndim == 2 else k_weight(x, sr)[:, None]
    p = (y ** 2).sum(axis=1)
    bl = ns(block_s, sr)
    hop = max(1, int(bl * (1 - overlap)))
    if len(p) < bl:
        p = pad_to(p, bl)
    c = np.concatenate([[0], np.cumsum(p)])
    starts = np.arange(0, len(p) - bl + 1, hop)
    ms = (c[starts + bl] - c[starts]) / bl
    # mono signals are counted as a single channel (BS.1770), so a mono SFX and a centred stereo
    # mix of the same content measure ~3 dB apart; we compensate so mono == dual-mono loudness
    if x.ndim == 1:
        ms = ms * 2.0
    return -0.691 + 10 * np.log10(ms + 1e-15)


def lufs_integrated(x: np.ndarray, sr: int = SR) -> float:
    lb = _block_loudness(x, 0.4, 0.75, sr)
    g = lb[lb > -70]
    if len(g) == 0:
        return -70.0
    pw = 10 ** ((g + 0.691) / 10)
    rel = -0.691 + 10 * np.log10(pw.mean()) - 10
    g2 = g[g > rel]
    if len(g2) == 0:
        return -70.0
    return float(-0.691 + 10 * np.log10((10 ** ((g2 + 0.691) / 10)).mean()))


def lufs_momentary_max(x: np.ndarray, sr: int = SR) -> float:
    return float(_block_loudness(x, 0.4, 0.9, sr).max())


def lufs_short_max(x: np.ndarray, sr: int = SR) -> float:
    return float(_block_loudness(x, 3.0, 0.9, sr).max())


def true_peak_db(x: np.ndarray) -> float:
    y = signal.resample_poly(x, 4, 1, axis=0)
    return to_db(np.abs(y).max())


def measure(x: np.ndarray, mode: str) -> float:
    if mode == "integrated":
        return lufs_integrated(x)
    if mode == "short":
        return lufs_short_max(x)
    return lufs_momentary_max(x)


def normalize(x: np.ndarray, target: float, mode: str = "momentary", ceiling_db: float = -1.5) -> np.ndarray:
    """Gain to reach target loudness (LUFS), then a transparent lookahead limiter for the true-peak ceiling."""
    x = x - np.mean(x, axis=0)
    cur = measure(x, mode)
    y = x * db(target - cur)
    for _ in range(3):
        if true_peak_db(y) <= ceiling_db + 0.05:
            break
        y = limiter(y, ceiling_db - 0.3)
    return y


# --------------------------------------------------------------------------- loops
def loop_crossfade(x: np.ndarray, L: int, xf: int) -> np.ndarray:
    """Make a seamless loop of length L from a render of length >= L + xf.
    The head is crossfaded with the material that naturally follows sample L."""
    assert len(x) >= L + xf, "need L+xf samples"
    out = x[:L].copy()
    t = np.linspace(0, 1, xf)
    fin = np.sin(t * np.pi / 2)   # equal-power for uncorrelated material
    fout = np.cos(t * np.pi / 2)
    if x.ndim == 2:
        fin, fout = fin[:, None], fout[:, None]
    out[:xf] = x[:xf] * fin + x[L:L + xf] * fout
    return out


def wrap_tail(x: np.ndarray, L: int) -> np.ndarray:
    """Fold everything after L back onto the start (music/reverb tails): perfect seamless loop."""
    out = x[:L].copy()
    tail = x[L:]
    while len(tail):
        k = min(len(tail), L)
        out[:k] += tail[:k]
        tail = tail[k:]
    return out


def seam_discontinuity(x: np.ndarray) -> float:
    """Jump at the loop seam relative to typical sample-to-sample change (≈1 means seamless)."""
    m = mono(x)
    d = np.abs(np.diff(m))
    typical = np.percentile(d, 99) + 1e-9
    return float(abs(m[0] - m[-1]) / typical)


# --------------------------------------------------------------------------- IO
def write_ogg(path: str, x: np.ndarray, quality: float = 5.0, sr: int = SR) -> int:
    """Encode float signal to Ogg Vorbis via ffmpeg/libvorbis. Returns file size in bytes."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    y = np.clip(x, -1.0, 1.0)
    pcm = (y * 32767.0).astype("<i2")
    ch = 1 if y.ndim == 1 else y.shape[1]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(sr), "-ac", str(ch),
           "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", str(quality), "-map_metadata", "-1", path]
    subprocess.run(cmd, input=pcm.tobytes(), check=True)
    return os.path.getsize(path)


def read_audio(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf
    x, sr = sf.read(path, always_2d=False)
    return x.astype(np.float64), sr


def write_wav(path: str, x: np.ndarray, sr: int = SR) -> None:
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.clip(x, -1, 1), sr, subtype="PCM_16")
