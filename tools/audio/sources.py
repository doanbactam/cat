"""Shared physical/procedural sources for the world: motorbikes, horns, voices (non-verbal babble in
Vietnamese tonal contours), birds, insects, geckos, frogs, wind, rain, water, chimes, kitchen, TV.
All functions return mono float arrays unless stated otherwise."""
from __future__ import annotations

import numpy as np
from scipy import signal

import dsp
from dsp import SR, TAU, ns
from voice import additive_voice, contour, f0_track, formant_tracks, noise_formant, pulse_voice


def R(rng, lo, hi):
    return float(rng.uniform(lo, hi))


# =========================================================================== periodic noise helpers (loops)
def loop_noise(n: int, rng, shape) -> np.ndarray:
    """Noise exactly periodic over n samples, spectrally shaped by shape(freqs)->gain (FFT, circular)."""
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    y = np.fft.irfft(X * shape(f), n)
    return y / (np.std(y) + 1e-12)


def shape_band(lo=20.0, hi=20000.0, slope=0.0, order=2):
    def g(f):
        f = np.maximum(f, 1.0)
        out = (f / 1000.0) ** (slope / 6.0206)
        if lo > 0:
            out = out / np.sqrt(1 + (lo / f) ** (2 * order))
        if hi < 22050:
            out = out / np.sqrt(1 + (f / hi) ** (2 * order))
        return out
    return g


def circ_filter(x: np.ndarray, shape) -> np.ndarray:
    """Zero-phase circular FFT filter (keeps loops seamless). Works on mono or stereo."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = shape(f)
    if x.ndim == 1:
        return np.fft.irfft(np.fft.rfft(x) * g, n)
    return np.stack([np.fft.irfft(np.fft.rfft(x[:, c]) * g, n) for c in range(x.shape[1])], axis=1)


def stereo_bed(n, rng, shape, width=0.8, mod_rate=0.0, mod_depth=0.0):
    """Decorrelated stereo noise bed, periodic."""
    a = loop_noise(n, rng, shape)
    b = loop_noise(n, rng, shape)
    L = a * (1 + width) / 2 + b * (1 - width) / 2
    Rr = b * (1 + width) / 2 + a * (1 - width) / 2
    out = np.stack([L, Rr], axis=1)
    if mod_rate > 0:
        m = 1 + mod_depth * dsp.smooth_noise_periodic(n, mod_rate, rng)
        out *= m[:, None]
    return out


# =========================================================================== motorbikes
def engine(rng, rpm: np.ndarray, load: np.ndarray, kind: str = "scooter") -> np.ndarray:
    """Single-cylinder 4-stroke (110-125cc) engine: firing pulses at rpm/120 through exhaust resonances,
    combustion variability, valve-train clatter, intake hiss and (scooters) CVT whine."""
    n = len(rpm)
    ff = rpm / 120.0
    t = dsp.pulse_times(ff, 0.004, rng)
    amps = (0.55 + 0.45 * np.interp(t, np.arange(n) / SR, load)) * np.abs(1 + 0.13 * rng.standard_normal(len(t)))
    miss = rng.random(len(t)) < 0.015
    amps[miss] *= 0.3
    imp = dsp.frac_impulses(n, t, amps)
    # pressure pulse: fast rise, ~3 ms decay
    a = np.exp(-1 / (0.0032 * SR))
    p = signal.lfilter([1.0], [1, -a], imp)
    p = p - signal.lfilter([1.0], [1, -np.exp(-1 / (0.0004 * SR))], imp) * 0.9
    mres = R(rng, 85, 140)
    y = dsp.peak(p, mres, 1.8, 10)
    y = dsp.peak(y, R(rng, 330, 480), 2.5, 7)
    y = dsp.peak(y, R(rng, 900, 1300), 3.0, 4)
    y = dsp.lp(y, R(rng, 2800, 4200), 2)
    y = dsp.hp(y, 35, 2)
    y /= np.abs(y).max() + 1e-9
    crank = rpm / 60.0
    ph = np.cumsum(crank) / SR
    valve = dsp.bp(rng.standard_normal(n), 2500, 7000) * (np.abs(np.sin(np.pi * ph * 2)) ** 12) * 0.05
    intake = dsp.bp(rng.standard_normal(n), 800, 2800) * (0.02 + 0.05 * load)
    y = y + valve + intake
    if kind == "scooter":
        wf = crank * R(rng, 6.5, 8.0) * (1 + 0.004 * dsp.smooth_noise(n, 3, rng))
        whine = np.sin(TAU * np.cumsum(wf) / SR) * 0.012 * (0.3 + load)
        belt = dsp.bp(rng.standard_normal(n), 1500, 4000) * 0.012
        y = y + whine + belt
    return y


def rpm_cruise(rng, n, base, var=0.08, rate=0.6, shifts=0):
    r = base * (1 + var * dsp.smooth_noise(n, rate, rng))
    if shifts:
        for k in range(shifts):
            c = int(rng.uniform(0.2, 0.8) * n)
            w = ns(0.35)
            dip = np.zeros(n)
            seg = np.concatenate([np.linspace(0, 1, w // 5), np.linspace(1, 0, w - w // 5)])
            dip[c:c + len(seg)] = seg[:max(0, min(len(seg), n - c))]
            r = r * (1 - 0.3 * dip)
    return r


def tire_noise(rng, n, speed):
    return dsp.bp(dsp.pink(n, rng), 300, 4000) * 0.02 * (speed / 8.0) ** 1.5


def motorbike_pass(rng, dur=7.0, speed=None, lateral=None, direction=None, kind=None, z=0.6, binaural=True,
                   t_center=None, horn=False):
    """Stereo (binaural=True) or mono pass-by of a motorbike, Doppler + distance + air absorption."""
    speed = speed or R(rng, 6.5, 12.0)
    lateral = lateral if lateral is not None else R(rng, 2.5, 8.0)
    direction = direction or (1 if rng.random() < 0.5 else -1)
    kind = kind or ("scooter" if rng.random() < 0.55 else "manual")
    t_center = t_center if t_center is not None else dur / 2
    n = ns(dur + 0.5)
    base = R(rng, 4200, 6200) * (speed / 9.0) ** 0.4
    rpm = rpm_cruise(rng, n, base, 0.06, 0.7, shifts=1 if (kind == "manual" and rng.random() < 0.4) else 0)
    load = np.clip(0.5 + 0.3 * dsp.smooth_noise(n, 0.5, rng), 0.1, 1)
    src = engine(rng, rpm, load, kind) + tire_noise(rng, n, speed)
    if horn:
        h = horn_beep(rng, double=rng.random() < 0.6)
        dsp.place(src, h * 3.0, ns(t_center - R(rng, 0.8, 1.6)))

    def traj(te):
        return direction * speed * (te - t_center), np.full_like(te, lateral), np.full_like(te, z)
    out = dsp.moving_source(src, traj, ref_dist=2.0, binaural=binaural)
    out = out[:ns(dur)]
    return dsp.fades(out, 0.3, 0.6)


def motorbike_far(rng, dur, dist, binaural=True):
    """Distant bike crossing at a far street: mostly low buzz."""
    return motorbike_pass(rng, dur, speed=R(rng, 7, 12), lateral=dist, binaural=binaural)


def horn_beep(rng, double=False, long=False, base=None, car=False):
    """Electromagnetic disc horn: buzzy harmonic tone with a disc resonance near 2.5-3.5 kHz."""
    base = base or (R(rng, 380, 500) if not car else R(rng, 330, 420))
    segs = []
    if long:
        segs = [(0.0, R(rng, 0.5, 0.9))]
    elif double:
        d1 = R(rng, 0.09, 0.16)
        segs = [(0.0, d1), (d1 + R(rng, 0.06, 0.1), R(rng, 0.1, 0.22))]
    else:
        segs = [(0.0, R(rng, 0.12, 0.3))]
    total = segs[-1][0] + segs[-1][1] + 0.1
    n = ns(total)
    out = np.zeros(n)
    tones = [base] if not car else [base, base * R(rng, 1.18, 1.26)]
    for (t0, d) in segs:
        m = ns(d + 0.03)
        f = np.full(m, 1.0)
        f *= 1 + 0.01 * dsp.smooth_noise(m, 20, rng)
        env = dsp.env_points([(0, 0), (0.006, 1), (d, 0.95), (d + 0.03, 0)], m)
        y = np.zeros(m)
        for b in tones:
            ph = TAU * np.cumsum(b * f) / SR
            for k in range(1, 40):
                fk = k * b
                if fk > 16000:
                    break
                a = k ** -0.75 * (1 + 4 / (1 + ((fk - R(rng, 2400, 3200)) / 500) ** 2)) * (1 + 2 / (1 + ((fk - 3900) / 700) ** 2))
                y += a * np.sin(k * ph + rng.uniform(0, 1))
        y = dsp.soft_clip(y / (np.abs(y).max() + 1e-9) * 1.6, 1.5)
        y += dsp.bp(rng.standard_normal(m), 1500, 6000) * 0.05
        dsp.place(out, y * env, ns(t0))
    return out


# =========================================================================== human non-verbal voices
VOWELS = {  # F1, F2, F3 (adult female); male scaled by 0.85
    "a": (850, 1600, 2850), "e": (600, 2200, 2900), "i": (330, 2700, 3300), "o": (550, 950, 2700),
    "u": (380, 900, 2500), "ơ": (520, 1350, 2700), "ư": (380, 1450, 2700), "ô": (450, 850, 2600),
}
TONES = {  # relative F0 contour points (t_frac, ratio) — Northern Vietnamese tones
    "ngang": [(0, 1.0), (1, 0.98)], "sac": [(0, 0.95), (0.4, 1.0), (1, 1.3)], "huyen": [(0, 0.92), (1, 0.75)],
    "hoi": [(0, 0.9), (0.5, 0.72), (1, 0.88)], "nga": [(0, 0.95), (0.45, 0.85), (0.55, 1.05), (1, 1.35)],
    "nang": [(0, 0.88), (1, 0.68)],
}


def babble_voice(rng, dur, sr=22050, female=True, style="chat", level_var=0.3, f0_mult=1.0):
    """Unintelligible speech-like voice stream: syllables with Vietnamese tonal F0 contours and vowel formants.
    Rendered at a reduced sample rate (it is always heard distant/filtered)."""
    n = int(dur * sr)
    f0b = (R(rng, 190, 240) if female else R(rng, 105, 140)) * f0_mult
    fs = (1.0 if female else 0.86) * (1.0 if f0_mult <= 1.0 else 1.12)
    f0 = np.full(n, f0b)
    amp = np.zeros(n)
    F = [np.full(n, 500.0), np.full(n, 1500.0), np.full(n, 2700.0)]
    t = R(rng, 0, 0.8)
    while t < dur - 0.2:
        phrase = int(rng.integers(3, 12)) if style != "call" else int(rng.integers(2, 5))
        for s in range(phrase):
            d = R(rng, 0.11, 0.26) if style != "call" else R(rng, 0.3, 0.8)
            a0, a1 = int(t * sr), min(n, int((t + d) * sr))
            if a1 - a0 < 10:
                break
            tone = list(TONES)[int(rng.integers(0, 6))]
            seg = a1 - a0
            fr = contour(TONES[tone], seg, sr)
            if style == "call":
                fr = fr * contour([(0, 1.1), (0.3, 1.25), (1, 0.85)], seg, sr) * 1.25
            f0[a0:a1] = f0b * fr * (1 + 0.15 * (rng.random() - 0.5))
            v = VOWELS[list(VOWELS)[int(rng.integers(0, len(VOWELS)))]]
            for k in range(3):
                F[k][a0:a1] = v[k] * fs * R(rng, 0.92, 1.08)
            env = dsp.env_points([(0, 0), (0.025, 1), (d * 0.7, 0.85), (d, 0)], seg, sr)
            amp[a0:a1] = env * (1 + level_var * (rng.random() - 0.5)) * (1.0 if style != "call" else 1.3)
            t += d + R(rng, 0.0, 0.05)
        t += R(rng, 0.25, 1.4) if style != "call" else R(rng, 1.5, 5.0)
    # smooth formant/F0 transitions (co-articulation)
    k = int(0.03 * sr)
    win = np.hanning(k) / np.hanning(k).sum()
    F = [np.convolve(x, win, "same") for x in F]
    f0 = np.convolve(f0, win, "same")
    fm = [(F[0], 90 + 0 * F[0]), (F[1], 120 + 0 * F[1]), (F[2], 180 + 0 * F[2])]
    y = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-6, breath=0.12, jitter=0.01, shimmer=0.05, nperseg=512, sr=sr)
    # consonant bursts at some onsets
    ons = np.nonzero((amp[1:] > 0.05) & (amp[:-1] <= 0.05))[0]
    for o in ons:
        if rng.random() < 0.45:
            m = int(R(rng, 0.02, 0.06) * sr)
            c = dsp.bp(rng.standard_normal(m), 2500, 7500, 2, sr) * np.hanning(m) * 0.15
            dsp.place(y, c, max(0, o - m // 2))
    return y


def upsample(x, sr_in):
    from math import gcd
    g = gcd(SR, sr_in)
    return signal.resample_poly(x, SR // g, sr_in // g)


def crowd(rng, dur, speakers=10, dist=(4, 25), callers=0, sr=22050, female_ratio=0.6, child_ratio=0.0):
    """Stereo crowd murmur from many babble voices at various distances/angles (+ melodic vendor calls)."""
    n = ns(dur)
    out = np.zeros((n, 2))
    for s in range(speakers + callers):
        call = s >= speakers
        child = rng.random() < child_ratio
        v = babble_voice(rng, dur, sr, female=child or rng.random() < female_ratio, style="call" if call else "chat",
                         f0_mult=R(rng, 1.35, 1.6) if child else 1.0)
        v = dsp.pad_to(upsample(v, sr), n)
        d = R(rng, *dist)
        g = 3.0 / d * (1.6 if call else 1.0)
        cut = 9000 * np.exp(-d / 40) + 1200
        v = dsp.lp(v, cut, 2)
        az = R(rng, -1.4, 1.4)
        out += dsp.spatialize(v, az) * g
    return out


def laugh(rng, female=True, kind="laugh"):
    """Non-verbal laugh: breathy 'ha' pulses with descending pitch."""
    f0b = R(rng, 230, 300) if female else R(rng, 120, 160)
    cnt = int(rng.integers(4, 8)) if kind == "laugh" else int(rng.integers(2, 4))
    per = R(rng, 0.14, 0.2)
    dur = cnt * per + 0.4
    n = ns(dur)
    amp = np.zeros(n)
    f0 = np.full(n, f0b)
    for k in range(cnt):
        a0 = ns(0.05 + k * per)
        d = per * R(rng, 0.55, 0.75)
        m = ns(d)
        env = dsp.env_points([(0, 0), (0.015, 1), (d, 0)], m) * (1 - 0.08 * k)
        amp[a0:a0 + m] = env[:max(0, min(m, n - a0))]
        f0[a0:a0 + m] = f0b * (1.25 - 0.05 * k) * contour([(0, 1.05), (1, 0.9)], m)[:max(0, min(m, n - a0))]
    fs = 1.0 if female else 0.86
    fm = formant_tracks([(800 * fs, 120), (1500 * fs, 150), (2800 * fs, 220), (3800 * fs, 300)], n)
    y = additive_voice(f0, amp, fm, rng, tilt_db_oct=-8, breath=0.45, env_model="bumps", breath_hp=600)
    return y


def call_oi(rng, female=True):
    """'Ơ-ới!' style non-verbal call: sustained vowel glide with a melodic fall."""
    dur = R(rng, 0.6, 1.0)
    n = ns(dur)
    f0b = R(rng, 260, 340) if female else R(rng, 150, 190)
    f0 = f0_track([(0, f0b * 0.95), (0.25, f0b * 1.15), (0.6, f0b * 1.1), (1, f0b * 0.8)], n, rng, 5.5, 0.012, 0.008)
    fs = 1.0 if female else 0.86
    fm = formant_tracks([([(0, 520 * fs), (0.55, 520 * fs), (0.8, 340 * fs), (1, 330 * fs)], 110),
                         ([(0, 1350 * fs), (0.55, 1400 * fs), (0.8, 2600 * fs), (1, 2700 * fs)], 140),
                         ([(0, 2700 * fs), (1, 3300 * fs)], 220), (3900 * fs, 300)], n)
    amp = dsp.env_points([(0, 0), (0.04, 1), (dur * 0.7, 0.9), (dur, 0)], n)
    return additive_voice(f0, amp, fm, rng, tilt_db_oct=-6.5, breath=0.12, env_model="bumps")


def shoo(rng, kind=0):
    """'Suỵt!' / 'Xùy!' — hissed shoo: sibilant then a short voiced 'uy'/'ùy'."""
    n = ns(0.9)
    y = np.zeros(n)
    sd = R(rng, 0.18, 0.35)
    m = ns(sd)
    s_fm = formant_tracks([(R(rng, 4800, 6500), 2500), (R(rng, 8000, 9500), 3000)], m)
    s = noise_formant(m, s_fm, rng, dsp.env_points([(0, 0), (0.02, 1), (sd * 0.8, 0.9), (sd, 0.3)], m), hp_hz=2500)
    dsp.place(y, s, 0)
    vd = R(rng, 0.12, 0.22)
    vm = ns(vd)
    f0b = R(rng, 180, 300)
    f0 = f0_track([(0, f0b * 1.1), (1, f0b * (0.85 if kind % 2 else 1.25))], vm, rng, 0, 0, 0.01)
    fm = formant_tracks([([(0, 380), (1, 330)], 100), ([(0, 900), (1, 2500)], 150), (2800, 250)], vm)
    v = additive_voice(f0, dsp.env_points([(0, 0), (0.02, 1), (vd, 0)], vm), fm, rng, tilt_db_oct=-7, breath=0.35, env_model="bumps")
    dsp.place(y, v * 0.8, ns(sd - 0.02))
    if kind == 2:  # second hiss 'xùy xùy'
        dsp.place(y, s * 0.8, ns(sd + vd + 0.08))
    return y


def hum(rng, female=True):
    """Closed-mouth humming of a short pentatonic phrase (vendor at work)."""
    scale = np.array([0, 2, 5, 7, 9, 12])
    base = R(rng, 200, 260) if female else R(rng, 110, 140)
    notes = rng.choice(scale, int(rng.integers(5, 9)))
    durs = rng.choice([0.25, 0.35, 0.5, 0.7], len(notes))
    n = ns(durs.sum() + 0.3)
    pts = []
    t = 0
    for nn, d in zip(notes, durs):
        pts += [(t / (n / SR), base * 2 ** (nn / 12)), ((t + d * 0.8) / (n / SR), base * 2 ** (nn / 12))]
        t += d
    pts = [(min(p[0], 1.0), p[1]) for p in pts]
    pts.append((1.0, pts[-1][1]))
    f0 = f0_track(pts, n, rng, 5, 0.01, 0.006)
    fm = formant_tracks([(300, 80), (1000, 200), (2500, 300)], n)
    amp = dsp.env_points([(0, 0), (0.08, 0.8), (n / SR - 0.3, 0.8), (n / SR, 0)], n)
    return additive_voice(f0, amp, fm, rng, tilt_db_oct=-12, breath=0.05)


# =========================================================================== animals
def sparrow_chirp(rng, count=None):
    count = count or int(rng.integers(2, 6))
    n = ns(count * 0.32 + 0.2)
    y = np.zeros(n)
    t = 0.0
    style = int(rng.integers(0, 3))
    for k in range(count):
        d = R(rng, 0.04, 0.09)
        m = ns(d)
        if style == 0:   # 'chilp': up-down
            pts = [(0, R(rng, 3200, 3800)), (0.35, R(rng, 5200, 6300)), (1, R(rng, 3800, 4600))]
        elif style == 1:  # 'cheep': down sweep
            pts = [(0, R(rng, 6000, 7000)), (1, R(rng, 3500, 4200))]
        else:
            pts = [(0, R(rng, 4000, 4500)), (0.5, R(rng, 4800, 5600)), (1, R(rng, 4400, 5000))]
        f = contour(pts, m) * (1 + 0.02 * np.sin(TAU * R(rng, 80, 140) * np.arange(m) / SR))
        ph = TAU * np.cumsum(f) / SR
        env = np.sin(np.linspace(0, np.pi, m)) ** 1.4
        s = (np.sin(ph) + 0.18 * np.sin(2 * ph + 0.3) + 0.05 * np.sin(3 * ph)) * env
        dsp.place(y, s * R(rng, 0.6, 1.0), ns(t))
        t += d + R(rng, 0.06, 0.25)
    return y


def bulbul_song(rng):
    """Red-whiskered bulbul (chào mào): liquid fluted phrase of 3-6 glides."""
    notes = int(rng.integers(3, 7))
    durs = rng.uniform(0.07, 0.2, notes)
    gaps = rng.uniform(0.01, 0.06, notes)
    n = ns(durs.sum() + gaps.sum() + 0.2)
    y = np.zeros(n)
    t = 0.0
    prev = R(rng, 1800, 3500)
    for d, g in zip(durs, gaps):
        m = ns(d)
        nxt = R(rng, 1600, 4300)
        f = contour([(0, prev), (0.3, (prev + nxt) / 2 * R(rng, 0.9, 1.15)), (1, nxt)], m)
        f *= 1 + 0.012 * np.sin(TAU * R(rng, 25, 45) * np.arange(m) / SR)
        ph = TAU * np.cumsum(f) / SR
        env = np.sin(np.linspace(0, np.pi, m)) ** 0.8
        s = (np.sin(ph) + 0.1 * np.sin(2 * ph)) * env
        dsp.place(y, s, ns(t))
        prev = nxt
        t += d + g
    return y


def pigeon_coo(rng):
    """Rock dove perch coo 'uu-RRUU-uu': low closed-beak tone with a rolled middle syllable."""
    base = R(rng, 290, 380)
    parts = [(R(rng, 0.12, 0.2), 0.9, 0.0), (R(rng, 0.4, 0.6), 1.15, 0.6), (R(rng, 0.15, 0.25), 0.95, 0.0)]
    if rng.random() < 0.5:
        parts.append((R(rng, 0.2, 0.3), 0.85, 0.2))
    n = ns(sum(p[0] for p in parts) + 0.15 * len(parts) + 0.2)
    y = np.zeros(n)
    t = 0.0
    for d, r, roll in parts:
        m = ns(d)
        f0 = f0_track([(0, base * r * 0.95), (0.4, base * r * 1.04), (1, base * r * 0.92)], m, rng, 0, 0, 0.006)
        amp = dsp.env_points([(0, 0), (d * 0.2, 1), (d * 0.75, 0.9), (d, 0)], m)
        if roll > 0:
            amp *= 1 - roll * (0.5 + 0.5 * np.cos(TAU * np.cumsum(np.full(m, R(rng, 38, 50))) / SR)) ** 2
        fm = formant_tracks([(base * 1.1, 120), (base * 2.6, 300), (1800, 500)], m)
        s = additive_voice(f0, amp, fm, rng, tilt_db_oct=-16, breath=0.08, breath_hp=300)
        dsp.place(y, s, ns(t))
        t += d + R(rng, 0.04, 0.14)
    return dsp.lp(y, 2500, 2)


def wing_flaps(rng, beats=None, rate=None, takeoff=True):
    """Pigeon wing claps: each downstroke a broadband clap + feather whoosh; rate accelerates then settles."""
    beats = beats or int(rng.integers(6, 12))
    rate = rate or R(rng, 8, 10)
    n = ns(beats / rate + 0.6)
    y = np.zeros(n)
    t = 0.0
    for k in range(beats):
        a = (1.0 if k < 3 else 0.8 ** (k - 2)) if takeoff else 0.6 + 0.4 * (k / beats)
        cl = ns(0.006)
        clap = dsp.bp(rng.standard_normal(cl) * np.exp(-np.arange(cl) / ns(0.0015)), 600, 8000) * (1.5 if (k < 2 and takeoff) else 0.6)
        wm = ns(R(rng, 0.05, 0.08))
        wh = dsp.bp(rng.standard_normal(wm), 300, 3500) * np.sin(np.linspace(0, np.pi, wm)) ** 2 * 0.5
        thr = dsp.lp(rng.standard_normal(wm), 250) * np.sin(np.linspace(0, np.pi, wm)) * 0.6
        dsp.place(y, (clap + 0) * a, ns(t))
        dsp.place(y, (wh + thr) * a, ns(t + 0.004))
        t += 1 / rate * R(rng, 0.9, 1.1)
    return y


def crow_caw(rng, count=1, big=True):
    """Large-billed crow 'kaaa': rough, noisy, nasal; slightly falling."""
    out = []
    for k in range(count):
        d = R(rng, 0.25, 0.45) if big else R(rng, 0.18, 0.3)
        m = ns(d)
        f0b = R(rng, 420, 560) if big else R(rng, 600, 750)
        f0 = f0_track([(0, f0b * 0.9), (0.2, f0b * 1.05), (1, f0b * 0.8)], m, rng, 0, 0, 0.05, 0.04)
        fm = formant_tracks([([(0, 900), (0.3, 1300), (1, 1100)], 260), ([(0, 1800), (0.3, 2200), (1, 1900)], 350),
                             (3300, 500), (4600, 700)], m)
        amp = dsp.env_points([(0, 0), (0.02, 1), (d * 0.6, 0.85), (d, 0)], m)
        v = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-4, breath=0.35, jitter=0.04, shimmer=0.25, irregular=0.35, breath_hp=600)
        out.append(v)
        out.append(np.zeros(ns(R(rng, 0.25, 0.45))))
    return np.concatenate(out[:-1]) if out else np.zeros(1)


def crow_rattle(rng):
    """Corvid 'rattle'/chuckle: rapid series of knocking clicks with a guttural tone."""
    d = R(rng, 0.5, 0.9)
    n = ns(d)
    rate = R(rng, 18, 26)
    f = np.full(n, rate)
    t = dsp.pulse_times(f, 0.05, rng)
    imp = dsp.frac_impulses(n, t, rng.uniform(0.5, 1, len(t)))
    y = dsp.resonator_bank(imp, [R(rng, 900, 1200), R(rng, 2000, 2600), 3400], [0.006, 0.004, 0.003], [1, 0.6, 0.3])
    f0 = f0_track([(0, 300), (1, 260)], n, rng, 0, 0, 0.08)
    g = pulse_voice(f0, dsp.env_points([(0, 0), (0.05, 1), (d, 0)], n), formant_tracks([(800, 200), (1600, 300)], n), rng,
                    jitter=0.08, shimmer=0.3, irregular=0.5)
    return y * dsp.env_points([(0, 0), (0.03, 1), (d, 0.2)], n) + g * 0.35


def dog_bark(rng, size=1.0, kind="bark"):
    """Medium dog bark: noisy onset, rough voiced core with a fast pitch fall, open-mouth formants."""
    d = R(rng, 0.14, 0.24) if kind == "bark" else R(rng, 0.08, 0.12)
    m = ns(d)
    f0b = R(rng, 330, 480) / size
    f0 = f0_track([(0, f0b * 0.85), (0.15, f0b * 1.12), (1, f0b * 0.6)], m, rng, 0, 0, 0.04, 0.03)
    fm = formant_tracks([([(0, 500), (0.2, 900), (1, 650)], 200), ([(0, 1200), (0.2, 1700), (1, 1300)], 260),
                         (2700, 380), (3700, 500)], m)
    for i, (F, B) in enumerate(fm):
        fm[i] = (F / size, B)
    amp = dsp.env_points([(0, 0), (0.008, 1), (d * 0.5, 0.75), (d, 0)], m)
    y = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-5, breath=0.4, jitter=0.03, shimmer=0.2, irregular=0.25, breath_hp=500)
    # chest thump at onset
    th = ns(0.03)
    dsp.place(y, dsp.lp(rng.standard_normal(th) * np.exp(-np.arange(th) / ns(0.008)), 300) * 0.6, 0)
    return y


def dog_growl(rng, dur=None):
    d = dur or R(rng, 1.4, 2.4)
    n = ns(d)
    f0 = f0_track([(0, 85), (0.5, 95), (1, 80)], n, rng, 0, 0, 0.08, 0.1)
    fm = formant_tracks([(380, 140), (1000, 250), (2300, 380), (3300, 500)], n)
    amp = dsp.env_points([(0, 0), (0.12, 0.8), (d * 0.5, 1), (d * 0.85, 0.8), (d, 0)], n) * (1 + 0.25 * dsp.smooth_noise(n, 3, rng))
    y = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-7, breath=0.22, jitter=0.08, shimmer=0.3, irregular=0.55)
    return dsp.lp(y, 4500, 2)


def dog_pant(rng, length=4.0):
    """Panting loop (periodic): fast in/out breaths ~3.3 Hz with wet tongue noise."""
    n = ns(length)
    y = np.zeros(n)
    rate = R(rng, 3.0, 3.6)
    t = 0.0
    k = 0
    while t < length - 0.01:
        d = 1 / rate * R(rng, 0.42, 0.5)
        m = ns(d)
        exhale = k % 2 == 0
        fm = formant_tracks([(R(rng, 700, 900), 300), (R(rng, 1500, 1900), 400), (3000, 700)], m)
        b = noise_formant(m, fm, rng, dsp.env_points([(0, 0), (d * 0.3, 1), (d, 0)], m), hp_hz=300)
        dsp.place_wrap(y, b * (1.0 if exhale else 0.7), ns(t))
        t += 1 / rate / 2 * R(rng, 0.95, 1.05)
        k += 1
    return y


def dog_whine(rng):
    d = R(rng, 0.6, 1.1)
    n = ns(d)
    f0b = R(rng, 700, 1000)
    f0 = f0_track([(0, f0b * 0.9), (0.3, f0b * 1.15), (1, f0b * 0.8)], n, rng, 7, 0.02, 0.01)
    fm = formant_tracks([(1200, 300), (2400, 400), (3600, 500)], n)
    amp = dsp.env_points([(0, 0), (0.05, 0.8), (d * 0.5, 1), (d, 0)], n)
    return additive_voice(f0, amp, fm, rng, tilt_db_oct=-10, breath=0.25)


def mouse_squeak(rng):
    d = R(rng, 0.04, 0.09)
    cnt = int(rng.integers(1, 4))
    n = ns(cnt * 0.15 + 0.1)
    y = np.zeros(n)
    for k in range(cnt):
        m = ns(d)
        f = contour([(0, R(rng, 5000, 6500)), (0.4, R(rng, 7000, 8500)), (1, R(rng, 5500, 6500))], m)
        s = np.sin(TAU * np.cumsum(f) / SR) * np.sin(np.linspace(0, np.pi, m)) + 0.1 * dsp.hp(rng.standard_normal(m), 4000) * np.hanning(m)
        dsp.place(y, s, ns(k * R(rng, 0.08, 0.14)))
    return y


def cricket_chirp(rng, fc=None):
    fc = fc or R(rng, 4200, 5400)
    pulses = int(rng.integers(3, 6))
    pr = R(rng, 26, 36)
    n = ns(pulses / pr + 0.03)
    y = np.zeros(n)
    for k in range(pulses):
        m = ns(R(rng, 0.012, 0.02))
        tt = np.arange(m) / SR
        s = np.sin(TAU * fc * (1 - 0.03 * tt / tt[-1]) * tt) + 0.12 * np.sin(TAU * 2 * fc * tt)
        s *= np.sin(np.linspace(0, np.pi, m)) ** 0.6
        dsp.place(y, s * (0.8 + 0.2 * rng.random()), ns(k / pr))
    return y


def gecko_house(rng):
    """House gecko (thạch sùng) 'chặc chặc chặc': 6-10 sharp chirp clicks, slowing and fading."""
    cnt = int(rng.integers(6, 11))
    n = ns(cnt * 0.16 + 0.2)
    y = np.zeros(n)
    t = 0.0
    per = R(rng, 0.1, 0.14)
    for k in range(cnt):
        m = ns(0.03)
        tt = np.arange(m) / SR
        f = R(rng, 2600, 3600) * (1 - 0.25 * tt / tt[-1])
        s = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-tt / 0.006)
        s += dsp.bp(dsp.click(m, rng), 1800, 7000) * 0.4
        dsp.place(y, s * (1 - 0.06 * k), ns(t))
        t += per * (1 + 0.05 * k)
    return y


def tokay_call(rng, reps=None):
    """Tokay gecko (tắc kè): a croaky rattle, then repeated loud 'tắc-kè' two-syllable calls, fading."""
    reps = reps or int(rng.integers(5, 9))
    n = ns(0.8 + reps * 1.0 + 0.5)
    y = np.zeros(n)
    # opening rattle
    rd = 0.5
    rm = ns(rd)
    rt = dsp.pulse_times(np.full(rm, R(rng, 30, 45)), 0.06, rng)
    rat = dsp.resonator_bank(dsp.frac_impulses(rm, rt, rng.uniform(0.4, 1, len(rt))), [700, 1500, 2600], [0.005, 0.004, 0.003], [1, 0.6, 0.3])
    dsp.place(y, rat * dsp.env_points([(0, 0), (0.05, 1), (rd, 0.4)], rm) * 0.6, 0)
    t = rd + 0.25
    for k in range(reps):
        g = 1.0 - 0.07 * k
        for syl, (d, f0b, F1, F2) in enumerate([(0.11, R(rng, 520, 600), 900, 1900), (0.22, R(rng, 420, 480), 700, 1300)]):
            m = ns(d)
            f0 = f0_track([(0, f0b * 1.1), (0.3, f0b), (1, f0b * (0.9 if syl else 1.0))], m, rng, 0, 0, 0.04)
            fm = formant_tracks([(F1, 220), (F2, 320), (3000, 500)], m)
            amp = dsp.env_points([(0, 0), (0.008, 1), (d * 0.6, 0.8), (d, 0)], m)
            v = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-6, breath=0.25, jitter=0.03, shimmer=0.2, irregular=0.3)
            dsp.place(y, v * g, ns(t))
            t += d + (0.05 if syl == 0 else 0)
        t += R(rng, 0.55, 0.75)
    return y[:ns(t + 0.3)]


def frog_croak(rng):
    cnt = int(rng.integers(2, 5))
    n = ns(cnt * 0.35 + 0.2)
    y = np.zeros(n)
    for k in range(cnt):
        d = R(rng, 0.08, 0.15)
        m = ns(d)
        f0 = f0_track([(0, R(rng, 180, 260)), (1, R(rng, 150, 200))], m, rng, 0, 0, 0.05)
        fm = formant_tracks([(R(rng, 500, 700), 150), (R(rng, 1300, 1700), 250)], m)
        amp = dsp.env_points([(0, 0), (0.01, 1), (d, 0)], m)
        v = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-7, breath=0.15, jitter=0.03, irregular=0.3)
        dsp.place(y, v, ns(k * R(rng, 0.25, 0.4)))
    return y


def rooster(rng):
    """Distant rooster 'ò ó o o': four syllables, last one long and falling."""
    segs = [(0.18, 1.0), (0.22, 1.2), (0.16, 1.1), (0.6, 1.15)]
    n = ns(sum(s[0] for s in segs) + 0.3)
    y = np.zeros(n)
    t = 0.0
    base = R(rng, 500, 650)
    for i, (d, r) in enumerate(segs):
        m = ns(d)
        pts = [(0, base * r), (1, base * r * (0.75 if i == 3 else 0.95))]
        f0 = f0_track(pts, m, rng, 6, 0.01, 0.03)
        fm = formant_tracks([(1100, 250), (2200, 350), (3500, 500)], m)
        amp = dsp.env_points([(0, 0), (0.02, 1), (d * 0.7, 0.9), (d, 0)], m)
        v = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-5, breath=0.25, jitter=0.03, shimmer=0.15, irregular=0.2)
        dsp.place(y, v, ns(t))
        t += d + 0.02
    return y


# =========================================================================== wind / water / weather
def wind_bed(n, rng, strength=0.5, gust_rate=0.15, whistle=0.3, stereo_out=True):
    """Periodic gusty wind: noise whose level and brightness follow a gust envelope; plus edge whistles."""
    gust = np.clip(0.55 + 0.45 * dsp.smooth_noise_periodic(n, gust_rate, rng), 0.05, 1.2)
    gust2 = gust ** 1.5
    out = np.zeros((n, 2))
    for c in range(2):
        low = loop_noise(n, rng, shape_band(25, 350, -3, 2))
        mid = loop_noise(n, rng, shape_band(200, 1800, -2, 2))
        g = np.roll(gust, int(c * 0.15 * SR))
        out[:, c] = low * g * 0.8 + mid * g ** 2 * 0.35 * strength
        if whistle > 0:
            for k in range(2):
                fcen = R(rng, 500, 1400)
                wn = loop_noise(n, rng, lambda f, fc=fcen: 1 / (1 + ((f - fc) / (fc / 40)) ** 2))
                out[:, c] += wn * (g ** 3) * whistle * 0.12
    return out if stereo_out else out.mean(axis=1)


def leaves_bed(n, rng, density=1.0, gust=None):
    """Rustling foliage: dense micro-events whose rate follows the gust envelope (periodic)."""
    if gust is None:
        gust = np.clip(0.5 + 0.5 * dsp.smooth_noise_periodic(n, 0.2, rng), 0, 1)
    out = np.zeros((n, 2))
    for c in range(2):
        nz = loop_noise(n, rng, shape_band(1800, 9000, 0, 2))
        flick = np.clip(dsp.smooth_noise_periodic(n, 60 * density, rng), 0, None) ** 2
        out[:, c] = nz * flick * np.roll(gust, int(c * 0.2 * SR)) ** 2
    return out


def rain_bed(n, rng, intensity=0.5):
    """Periodic stereo rain: shaped hiss + thousands of individual drops on mixed surfaces + drips."""
    out = stereo_bed(n, rng, shape_band(600, 9000, -1.5, 2), width=0.6, mod_rate=0.3, mod_depth=0.15) * (0.12 + 0.5 * intensity ** 1.5)
    out += stereo_bed(n, rng, shape_band(40, 400, -3, 2), width=0.5) * 0.25 * intensity ** 2
    rate = 120 + 1400 * intensity ** 1.5
    cnt = int(rate * n / SR)
    times = rng.uniform(0, n / SR, cnt)
    drops = np.zeros((n, 2))
    kinds = rng.random(cnt)
    amps = np.exp(rng.uniform(np.log(0.05), 0, cnt))
    pans = rng.uniform(-1, 1, cnt)
    templates = []
    for k in range(60):
        kind = k % 3
        if kind == 0:  # hard-surface tick
            m = ns(0.006)
            s = dsp.bp(dsp.click(m, rng), R(rng, 1500, 3000), R(rng, 6000, 12000))
        elif kind == 1:  # leaf/awning tap
            m = ns(0.02)
            s = dsp.reson(dsp.click(m, rng), R(rng, 900, 3000), 800)
        else:  # puddle bubble
            m = ns(0.03)
            tt = np.arange(m) / SR
            s = np.sin(TAU * np.cumsum(R(rng, 1200, 4000) * (1 + 10 * tt)) / SR) * np.exp(-tt / 0.006) * 0.5
            dsp.place(s, dsp.hp(dsp.click(ns(0.003), rng), 3000) * 0.3, 0)
        templates.append(s / (np.abs(s).max() + 1e-9))
    for tt, kk, a, p in zip(times, kinds, amps, pans):
        s = templates[int(kk * 59.999)]
        st = dsp.pan(s * a, p)
        dsp.place_wrap(drops, st, ns(tt))
    out += drops * (0.25 + 0.15 * intensity)
    # eaves drips: a few positions with steady periods
    for k in range(int(2 + 3 * intensity)):
        per = R(rng, 0.35, 1.4) / (0.5 + intensity)
        p = R(rng, -0.9, 0.9)
        t = R(rng, 0, per)
        fb = R(rng, 700, 1800)
        while t < n / SR:
            m = ns(0.05)
            tt = np.arange(m) / SR
            s = np.sin(TAU * np.cumsum(fb * R(rng, 0.9, 1.1) * (1 + 6 * tt)) / SR) * np.exp(-tt / 0.012)
            dsp.place(s, dsp.bp(dsp.click(ns(0.004), rng), 1000, 6000) * 0.5, 0)
            dsp.place_wrap(out, dsp.pan(s * R(rng, 0.25, 0.5), p), ns(t))
            t += per * R(rng, 0.9, 1.1)
    return out


def rain_on_tin(n, rng, intensity=0.6):
    """Rain drumming on a corrugated iron (tôn) awning overhead: each drop excites sheet modes."""
    out = stereo_bed(n, rng, shape_band(800, 9000, -1, 2), 0.5) * 0.1 * intensity
    rate = 500 + 2500 * intensity
    cnt = int(rate * n / SR)
    modes = [np.array([R(rng, 900, 1300), R(rng, 1700, 2300), R(rng, 2600, 3400), R(rng, 3800, 4800), R(rng, 5200, 6400)]) for _ in range(6)]
    templates = []
    for k in range(48):
        md = modes[k % 6] * rng.uniform(0.97, 1.03, 5)
        m = ns(0.08)
        s = dsp.modal(m, md, rng.uniform(0.01, 0.035, 5), rng.uniform(0.3, 1, 5), phases=rng.uniform(0, 6, 5), attack=0.0002)
        s += dsp.modal(m, [R(rng, 110, 190)], [0.02], [0.5])
        templates.append(s / (np.abs(s).max() + 1e-9))
    times = rng.uniform(0, n / SR, cnt)
    amps = np.exp(rng.uniform(np.log(0.04), 0, cnt))
    pans = rng.uniform(-0.8, 0.8, cnt)
    drops = np.zeros((n, 2))
    idx = rng.integers(0, 48, cnt)
    for tt, a, p, i in zip(times, amps, pans, idx):
        dsp.place_wrap(drops, dsp.pan(templates[i] * a, p), ns(tt))
    out += drops * 0.2
    # gutter overflow trickle
    trick = stereo_bed(n, rng, shape_band(300, 2500, -2, 2), 0.3) * np.clip(dsp.smooth_noise_periodic(n, 8, rng), 0, None)[:, None] * 0.12
    return out + trick


def thunder(rng, near=True):
    dur = R(rng, 6, 9) if near else R(rng, 4.5, 7)
    n = ns(dur)
    out = np.zeros((n, 2))
    env = np.zeros(n)
    t0 = 0.0 if near else R(rng, 0.2, 0.6)
    # rumble: series of swelling bursts (multipath from the long channel)
    t = t0
    while t < dur * 0.8:
        m = ns(R(rng, 0.4, 1.4))
        a = np.exp(-(t - t0) / (dur * 0.35)) * R(rng, 0.4, 1.0)
        seg = np.sin(np.linspace(0, np.pi, m)) ** 2 * a
        dsp.place(env, seg, ns(t))
        t += R(rng, 0.15, 0.6)
    env = dsp.lp(env, 8, 1)
    for c in range(2):
        nz = dsp.brown(n, rng) * 0.7 + dsp.pink(n, rng) * 0.1
        nz = dsp.lp(nz, 160 if near else 110, 3)
        out[:, c] = nz * env * (1 + 0.3 * dsp.smooth_noise(n, 3, rng))
    if near:
        # crack: rapid broadband rips
        crack = np.zeros(n)
        tt = 0.0
        for k in range(int(rng.integers(4, 9))):
            m = ns(R(rng, 0.02, 0.08))
            b = dsp.hp(rng.standard_normal(m), 250) * np.exp(-np.arange(m) / (m / 3)) * R(rng, 0.4, 1.0)
            dsp.place(crack, b, ns(tt))
            tt += R(rng, 0.01, 0.05)
        rip = ns(0.5)
        ripn = dsp.bp(rng.standard_normal(rip), 150, 5000) * np.exp(-np.arange(rip) / ns(0.12)) * (0.5 + 0.5 * np.abs(dsp.smooth_noise(rip, 60, rng)))
        dsp.place(crack, ripn * 0.6, ns(0.02))
        out += dsp.pan(crack, R(rng, -0.4, 0.4)) * 0.8
    ir = dsp.make_ir(2.5, rng=rng, predelay=0.03, brightness=0.2)
    return dsp.reverb_full(out, ir, wet=0.35)[:n + ns(1.5)]


def gust(rng):
    dur = R(rng, 3.0, 6.0)
    n = ns(dur)
    env = dsp.env_points([(0, 0), (dur * R(rng, 0.3, 0.5), 1), (dur, 0)], n) ** 1.3
    out = np.zeros((n, 2))
    fc = 300 + 1500 * env
    for c in range(2):
        nz = rng.standard_normal(n)

        def g(f, t, fc=fc):
            idx = np.minimum((t * SR).astype(int), n - 1)
            cc = fc[idx][None, :]
            return 1 / (1 + (f[:, None] / cc) ** 2) + 0.15 / (1 + ((f[:, None] - cc * 1.4) / 60) ** 2)
        y = dsp.stft_shape(nz, g, 2048)
        out[:, c] = y / (np.abs(y).max() + 1e-9) * env
    pan = np.linspace(R(rng, -0.8, 0), R(rng, 0, 0.8), n)
    out[:, 0] *= np.cos((pan + 1) * np.pi / 4) * 1.4
    out[:, 1] *= np.sin((pan + 1) * np.pi / 4) * 1.4
    lv = leaves_bed(n, rng, 1.0, env)
    return out + lv * 0.3


def water_lapping(n, rng):
    """Lake shore: irregular small wave slaps and gurgles (periodic)."""
    out = stereo_bed(n, rng, shape_band(80, 900, -4, 2), 0.4, 0.2, 0.3) * 0.05
    t = 0.0
    while t < n / SR:
        d = R(rng, 0.25, 0.6)
        m = ns(d + 0.4)
        env = dsp.env_points([(0, 0), (d * 0.3, 1), (d, 0.2), (d + 0.4, 0)], m)
        sl = dsp.bp(rng.standard_normal(m), R(rng, 150, 300), R(rng, 900, 2200)) * env
        for k in range(int(rng.integers(1, 6))):
            fb = R(rng, 300, 1500)
            bm = ns(R(rng, 0.03, 0.08))
            tt = np.arange(bm) / SR
            b = np.sin(TAU * np.cumsum(fb * (1 + 4 * tt / tt[-1])) / SR) * np.exp(-tt / (tt[-1] / 3))
            dsp.place(sl, b * R(rng, 0.1, 0.4), ns(R(rng, d * 0.3, d + 0.2)))
        trick = dsp.bp(dsp.frac_impulses(m, np.sort(rng.uniform(d * 0.5, d + 0.35, 30)), rng.uniform(0.1, 1, 30)), 2000, 7000) * 0.3
        dsp.place_wrap(out, dsp.pan((sl + trick) * R(rng, 0.3, 1.0), R(rng, -0.8, 0.8)), ns(t))
        t += R(rng, 0.5, 2.2)
    return out


def chime_strike(rng, f0, amp=1.0):
    ratios = np.array([1.0, 2.756, 5.404, 8.933])
    dec = np.array([R(rng, 2.0, 3.5), 1.0, 0.45, 0.2])
    a = np.array([1.0, 0.55, 0.3, 0.12])
    m = ns(dec[0] * 4)
    s = dsp.modal(m, f0 * ratios, dec, a, phases=rng.uniform(0, 6, 4), attack=0.0005)
    dsp.place(s, dsp.bp(dsp.click(ns(0.003), rng), 2000, 9000) * 0.1, 0)  # clapper tick
    return s * amp


def wind_chimes_bed(n, rng, tubes=(587.3, 659.3, 740.0, 880.0, 987.8), activity=0.6):
    gust = np.clip(0.4 + 0.6 * dsp.smooth_noise_periodic(n, 0.12, rng), 0, 1)
    out = np.zeros((n, 2))
    pans = np.linspace(-0.5, 0.5, len(tubes))
    t = 0.0
    while t < n / SR:
        g = gust[min(n - 1, ns(t))]
        rate = 0.2 + 5.0 * activity * g ** 3
        t += rng.exponential(1 / rate)
        if t >= n / SR:
            break
        k = int(rng.integers(0, len(tubes)))
        s = chime_strike(rng, tubes[k] * R(rng, 0.998, 1.002), R(rng, 0.2, 1.0) * (0.4 + 0.6 * g))
        dsp.place_wrap(out, dsp.pan(s, pans[k]), ns(t))
    return out


# =========================================================================== domestic / urban mechanical
def sizzle(n, rng):
    """Wok/oil sizzle (periodic): dense crackle + hiss, swelling when ingredients are tossed."""
    sw = np.clip(0.6 + 0.4 * dsp.smooth_noise_periodic(n, 0.4, rng), 0.2, 1)
    hiss = loop_noise(n, rng, shape_band(2500, 12000, 0, 2)) * 0.25
    cnt = int(n / SR * 900)
    times = rng.uniform(0, n / SR, cnt)
    cr = np.zeros(n)
    for tt in times:
        m = ns(0.003)
        dsp.place_wrap(cr, dsp.bp(dsp.click(m, rng), 1500, 9000) * R(rng, 0.1, 1.0), ns(tt))
    return (hiss + cr * 0.6) * sw


def wok_scrape(rng):
    d = R(rng, 0.2, 0.45)
    m = ns(d)
    exc = dsp.bp(rng.standard_normal(m), 800, 6000) * dsp.env_points([(0, 0), (0.03, 1), (d * 0.7, 0.8), (d, 0)], m)
    modes = [R(rng, 380, 520), R(rng, 900, 1200), R(rng, 1700, 2100), R(rng, 2600, 3300), R(rng, 4100, 4800)]
    return dsp.resonator_bank(exc, modes, [0.08, 0.06, 0.04, 0.03, 0.02], [1, 0.8, 0.6, 0.4, 0.3]) * 0.3 + exc * 0.2


def chopping(rng, count=None):
    count = count or int(rng.integers(4, 12))
    rate = R(rng, 3.5, 6)
    n = ns(count / rate + 0.3)
    y = np.zeros(n)
    for k in range(count):
        m = ns(0.08)
        b = R(rng, 180, 260)
        s = dsp.modal(m, [b, b * 2.7, b * 5.1, R(rng, 2500, 3500)], [0.02, 0.012, 0.008, 0.004], [1, 0.6, 0.3, 0.3], attack=0.0004)
        dsp.place(s, dsp.bp(dsp.click(ns(0.003), rng), 2000, 8000) * 0.5, 0)
        dsp.place(y, s * R(rng, 0.7, 1.0), ns(k / rate * R(rng, 0.95, 1.05)))
    return y


def dish_clink(rng):
    m = ns(0.6)
    f = R(rng, 1800, 3500)
    s = dsp.modal(m, f * np.array([1, 2.3, 3.9]), [0.15, 0.08, 0.04], [1, 0.5, 0.25], attack=0.0003)
    if rng.random() < 0.5:
        dsp.place(s, dsp.modal(ns(0.4), f * 1.07 * np.array([1, 2.3]), [0.1, 0.05], [0.6, 0.3]), ns(R(rng, 0.05, 0.12)))
    return s


def tap_water(rng, dur=None):
    d = dur or R(rng, 2.5, 6.0)
    n = ns(d)
    stream = dsp.bp(dsp.pink(n, rng), 400, 5000) * 0.4
    bub = np.zeros(n)
    for tt in np.sort(rng.uniform(0, d, int(d * 60))):
        m = ns(0.02)
        x = np.arange(m) / SR
        dsp.place(bub, np.sin(TAU * np.cumsum(R(rng, 600, 2400) * (1 + 6 * x)) / SR) * np.exp(-x / 0.005) * R(rng, 0.1, 0.4), ns(tt))
    return (stream + bub) * dsp.env_points([(0, 0), (0.15, 1), (d - 0.3, 1), (d, 0)], n)


def tv_murmur(n, rng, sr=22050):
    """TV inside a house: one or two talk-show voices + a little jingle music, through a small speaker."""
    dur = n / SR
    v = babble_voice(rng, dur, sr, female=True, level_var=0.2)
    v2 = babble_voice(rng, dur, sr, female=False, level_var=0.2)
    y = dsp.pad_to(upsample(v, sr), n) + dsp.pad_to(upsample(v2, sr), n) * 0.8
    # jingle: simple plucked arpeggio every ~20 s
    t = R(rng, 2, 8)
    while t < dur - 3:
        base = R(rng, 300, 500)
        for k, st in enumerate([0, 4, 7, 12, 7, 4]):
            m = ns(0.5)
            dsp.place(y, dsp.modal(m, [base * 2 ** (st / 12) * h for h in (1, 2, 3)], [0.2, 0.1, 0.05], [0.4, 0.15, 0.06]), ns(t + k * 0.18))
        t += R(rng, 15, 25)
    y = dsp.bp(y, 280, 4500, 2)
    y = dsp.soft_clip(y / (np.abs(y).max() + 1e-9) * 1.4, 1.3)
    return y


def ac_hum(n, rng):
    """Window AC / condenser unit: motor hum (100 Hz + harmonics), fan blade-pass tone, airflow, rattles. Periodic."""
    t = np.arange(n) / SR
    L = n / SR
    def per(f):  # snap frequency so it is periodic over the loop
        return round(f * L) / L
    y = np.zeros(n)
    for k, a in ((1, 0.5), (2, 0.25), (3, 0.12), (4, 0.06)):
        y += a * np.sin(TAU * per(100 * k) * t + rng.uniform(0, 6))
    bpf = per(R(rng, 40, 55))
    blade = sum(a * np.sin(TAU * per(bpf * h) * t) for h, a in ((1, 0.3), (2, 0.15), (3, 0.08)))
    y += blade
    y += loop_noise(n, rng, shape_band(150, 2500, -3, 2)) * 0.35
    rat = loop_noise(n, rng, shape_band(1500, 6000, 0, 2)) * (np.clip(np.sin(TAU * per(bpf) * t), 0, 1) ** 8) * 0.15
    return y + rat


def neon_buzz(n, rng):
    t = np.arange(n) / SR
    L = n / SR
    f = round(100 * L) / L
    y = np.zeros(n)
    for k in range(1, 40):
        y += np.sin(TAU * f * k * t + rng.uniform(0, 6)) / k ** 0.9 * (1.5 if k in (6, 7, 8) else 1)
    y = y / np.abs(y).max()
    flick = np.clip(1 + 0.4 * dsp.smooth_noise_periodic(n, 2, rng), 0.3, 1.4)
    y *= flick
    crackle = np.zeros(n)
    for tt in rng.uniform(0, L, int(L * 3)):
        dsp.place_wrap(crackle, dsp.hp(dsp.click(ns(0.01), rng), 2000) * R(rng, 0.2, 0.8), ns(tt))
    return circ_filter(y, shape_band(80, 22000, 0, 2)) * 0.6 + crackle * 0.4


def koel_call(rng, reps=None):
    """Asian koel (tu hú) male call 'ko-EL', repeated with rising intensity and pitch."""
    reps = reps or int(rng.integers(4, 8))
    n = ns(reps * 0.75 + 0.4)
    y = np.zeros(n)
    base = R(rng, 650, 800)
    for k in range(reps):
        up = 1 + 0.05 * k
        for j, (d, r) in enumerate([(0.12, 1.0), (0.26, 1.45)]):
            m = ns(d)
            f = contour([(0, base * r * up * 0.97), (0.3, base * r * up), (1, base * r * up * (0.96 if j else 1.0))], m)
            ph = TAU * np.cumsum(f) / SR
            env = dsp.env_points([(0, 0), (0.02, 1), (d * 0.7, 0.9), (d, 0)], m)
            dsp.place(y, (np.sin(ph) + 0.15 * np.sin(2 * ph)) * env * (0.6 + 0.4 * k / reps), ns(0.05 + k * 0.72 + j * 0.16))
    return y


def bag_rustle(rng, dur=None):
    """Plastic bag crinkle: bursts of sharp clicks and swishes."""
    d = dur or R(rng, 0.4, 1.2)
    n = ns(d)
    cnt = int(d * R(rng, 300, 700))
    env = np.clip(dsp.smooth_noise(n, 8, rng) + 0.3, 0, None)
    t = np.sort(rng.uniform(0, d, cnt))
    imp = dsp.frac_impulses(n, t, rng.uniform(0.1, 1, cnt) * np.interp(t, np.arange(n) / SR, env))
    return dsp.bp(imp, 2000, 12000) + dsp.bp(rng.standard_normal(n), 1500, 7000) * env * 0.08


def drum_hit(rng, f0=None, rim=False):
    """Lion-dance drum (trống): membrane modes with pitch drop; rim = wooden 'cắc' on the drum body."""
    if rim:
        m = ns(0.12)
        return dsp.modal(m, [R(rng, 900, 1300), R(rng, 2200, 2800), 3900], [0.02, 0.012, 0.008], [1, 0.5, 0.3], attack=0.0002)
    f0 = f0 or R(rng, 85, 115)
    m = ns(0.9)
    t = np.arange(m) / SR
    y = np.zeros(m)
    for r, d, a in ((1, 0.35, 1), (1.59, 0.22, 0.5), (2.14, 0.15, 0.35), (2.3, 0.12, 0.25), (2.65, 0.1, 0.2), (2.92, 0.08, 0.15)):
        f = f0 * r * (1 + 0.12 * np.exp(-t / 0.03))
        y += a * np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / d)
    y += dsp.lp(rng.standard_normal(m) * np.exp(-t / 0.01), 2500) * 0.4
    return y


def cymbal(rng, choke=False):
    m = ns(0.35 if choke else 1.4)
    t = np.arange(m) / SR
    fr = rng.uniform(1500, 12000, 80)
    y = dsp.modal(m, fr, rng.uniform(0.05, 0.6, 80) * (0.3 if choke else 1), rng.uniform(0.2, 1, 80), phases=rng.uniform(0, 6, 80), attack=0.0005)
    y = y / (np.abs(y).max() + 1e-9) + dsp.bp(rng.standard_normal(m), 3000, 12000) * np.exp(-t / (0.08 if choke else 0.4)) * 0.6
    return y
