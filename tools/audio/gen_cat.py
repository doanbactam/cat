"""Cam the cat: vocalisations (meows, trills, purr, hiss, growl, yowl, yawn, sniff) and body foley
(jump effort, scratching, grooming, eating, lapping, pickup/drop, swipe, shake-off, kneading)."""
from __future__ import annotations

import numpy as np

import dsp
from dsp import SR, ns
from registry import Sound
from voice import additive_voice, contour, f0_track, formant_tracks, noise_formant, pulse_voice


# =========================================================================== meows
def _meow(rng, dur, f0_pts, open_pts, round_pts, amp_pts=None, breath=0.12, rough=0.0, sub=0.0,
          vib_rate=6.0, vib_depth=0.012, jitter=0.012, tilt_closed=-11.0, tilt_open=-5.0, size=1.0,
          trill_hz=0.0, trill_pts=None):
    """Source-filter meow. open: 0 = closed/nasal 'm', 1 = wide 'a'. round: lip rounding/closing 'ow'.
    size scales vocal-tract length (bigger cat -> lower formants)."""
    n = ns(dur)
    f0 = f0_track(f0_pts, n, rng, vib_rate, vib_depth, jitter, drift=0.01)
    a = np.clip(contour(open_pts, n), 0, 1)
    r = np.clip(contour(round_pts, n), 0, 1)
    k = 1.0 / size
    F1 = (560 + 950 * a - 150 * r) * k
    F2 = (1650 + 850 * a - 650 * r) * k
    F3 = (3500 + 500 * a - 250 * r) * k
    F4 = (5100 + 300 * a) * k
    F5 = 7000 * k + 0 * a
    fm = [(F1, 200 + 120 * (1 - a)), (F2, 300 + 60 * (1 - a)), (F3, 420 + 0 * a), (F4, 560 + 0 * a), (F5, 800 + 0 * a)]
    tilt = tilt_closed + (tilt_open - tilt_closed) * a
    amp = contour(amp_pts, n) if amp_pts else dsp.env_points([(0, 0), (0.05 * dur, 1), (0.8 * dur, 0.9), (dur, 0)], n)
    amp = amp * (0.45 + 0.55 * a)
    if trill_hz > 0:
        depth = contour(trill_pts, n) if trill_pts else np.full(n, 0.7)
        ph = 2 * np.pi * np.cumsum(trill_hz * (1 + 0.08 * dsp.smooth_noise(n, 4, rng))) / SR
        amp = amp * (1 - depth * (0.5 + 0.5 * np.cos(ph)) ** 1.5)
    y = additive_voice(f0, amp, fm, rng, tilt_db_oct=tilt, breath=breath, sub_harm=sub, roughness=rough,
                       env_model="bumps", breath_hp=1500.0)
    # tiny lip/onset click on wide openings, mouth release noise at the end
    y = dsp.fades(y, 0.004, 0.03)
    return dsp.hp(y, 140, 2)


def _rnd(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def meow_short(rng, i):
    p = _rnd(rng, 0.92, 1.12)
    dur = _rnd(rng, 0.34, 0.52)
    peak_t = _rnd(rng, 0.22, 0.35)
    return _meow(rng, dur,
                 [(0, 500 * p), (peak_t, 690 * p), (0.62, 650 * p), (1, 470 * p)],
                 [(0, 0.08), (peak_t, 0.85), (0.62, 0.72), (1, 0.12)],
                 [(0, 0), (0.5, 0.15), (1, 0.85)],
                 breath=_rnd(rng, 0.08, 0.16), vib_depth=0.008)


def meow_soft(rng, i):
    p = _rnd(rng, 0.95, 1.1)
    dur = _rnd(rng, 0.2, 0.3)
    return _meow(rng, dur,
                 [(0, 760 * p), (0.35, 930 * p), (1, 720 * p)],
                 [(0, 0.15), (0.35, 0.55), (1, 0.15)],
                 [(0, 0), (1, 0.6)], breath=0.24, tilt_closed=-14, tilt_open=-9, vib_depth=0.005, size=0.9)


def meow_chirp(rng, i):
    """'mrrp!' — short rising trill-chirp, closed-ish mouth, brisk."""
    p = _rnd(rng, 0.92, 1.1)
    dur = _rnd(rng, 0.2, 0.32)
    return _meow(rng, dur,
                 [(0, 470 * p), (0.55, 560 * p), (1, 880 * p)],
                 [(0, 0.1), (0.6, 0.25), (0.9, 0.55), (1, 0.3)],
                 [(0, 0.1), (1, 0.0)],
                 amp_pts=[(0, 0), (0.12, 0.8), (0.6, 0.9), (0.88, 1.0), (1, 0)],
                 breath=0.1, trill_hz=_rnd(rng, 26, 32), trill_pts=[(0, 0.85), (0.55, 0.75), (0.8, 0.1), (1, 0)],
                 tilt_closed=-12, tilt_open=-8)


def meow_trill(rng, i):
    """'brrrrrp' — rolled trill, closed mouth with deep 28 Hz pulsing, upturn at the end."""
    p = _rnd(rng, 0.92, 1.08)
    dur = _rnd(rng, 0.42, 0.62)
    return _meow(rng, dur,
                 [(0, 480 * p), (0.7, 560 * p), (1, 760 * p)],
                 [(0, 0.05), (0.75, 0.15), (0.93, 0.45), (1, 0.2)],
                 [(0, 0.3), (1, 0.0)],
                 amp_pts=[(0, 0), (0.08, 0.85), (0.7, 0.9), (0.9, 1.0), (1, 0)],
                 breath=0.09, trill_hz=_rnd(rng, 25, 30), trill_pts=[(0, 0.9), (0.75, 0.85), (0.92, 0.2), (1, 0.0)],
                 tilt_closed=-13, tilt_open=-9)


def meow_loud(rng, i):
    """Loud plaintive 'MRRAAOOWW' — open mouth, vibrato, a little roughness at the peak."""
    p = _rnd(rng, 0.9, 1.08)
    dur = _rnd(rng, 0.95, 1.35)
    return _meow(rng, dur,
                 [(0, 380 * p), (0.15, 560 * p), (0.45, 730 * p), (0.75, 650 * p), (1, 410 * p)],
                 [(0, 0.05), (0.2, 0.9), (0.65, 1.0), (0.9, 0.35), (1, 0.08)],
                 [(0, 0), (0.55, 0.05), (0.85, 0.7), (1, 0.95)],
                 amp_pts=[(0, 0), (0.08, 0.6), (0.35, 1.0), (0.75, 0.9), (1, 0)],
                 breath=_rnd(rng, 0.14, 0.22), rough=0.12, sub=0.06, vib_rate=_rnd(rng, 5, 6.5),
                 vib_depth=0.022, jitter=0.015, tilt_open=-5.5)


def meow_question(rng, i):
    """'mrrow?' — rises at the end."""
    p = _rnd(rng, 0.93, 1.1)
    dur = _rnd(rng, 0.5, 0.7)
    return _meow(rng, dur,
                 [(0, 460 * p), (0.3, 520 * p), (0.62, 545 * p), (1, 840 * p)],
                 [(0, 0.08), (0.35, 0.6), (0.7, 0.55), (0.92, 0.75), (1, 0.35)],
                 [(0, 0), (0.3, 0.1), (0.62, 0.55), (1, 0.15)],
                 amp_pts=[(0, 0), (0.1, 0.7), (0.6, 0.8), (0.9, 1.0), (1, 0)],
                 breath=0.12, vib_depth=0.01)


def meow_demand(rng, i):
    """'MEOW!' — insistent, bright, sharp onset, slight roughness."""
    p = _rnd(rng, 0.92, 1.1)
    dur = _rnd(rng, 0.42, 0.6)
    return _meow(rng, dur,
                 [(0, 600 * p), (0.18, 790 * p), (0.55, 760 * p), (1, 520 * p)],
                 [(0, 0.25), (0.15, 0.95), (0.6, 0.85), (1, 0.15)],
                 [(0, 0), (0.6, 0.15), (1, 0.8)],
                 amp_pts=[(0, 0), (0.06, 1.0), (0.65, 0.85), (1, 0)],
                 breath=0.1, rough=0.1, sub=0.05, tilt_open=-4.8, vib_depth=0.006)


def meow_greet(rng, i):
    """'mrr-aow' — friendly falling greeting."""
    p = _rnd(rng, 0.93, 1.08)
    dur = _rnd(rng, 0.45, 0.6)
    return _meow(rng, dur,
                 [(0, 520 * p), (0.25, 640 * p), (1, 430 * p)],
                 [(0, 0.05), (0.15, 0.2), (0.4, 0.8), (1, 0.1)],
                 [(0, 0), (0.6, 0.3), (1, 0.9)],
                 amp_pts=[(0, 0), (0.1, 0.65), (0.4, 1.0), (1, 0)],
                 breath=0.12, trill_hz=27, trill_pts=[(0, 0.8), (0.25, 0.6), (0.35, 0.0), (1, 0)])


def meow_complain(rng, i):
    """'mraaaow' — long descending grumble."""
    p = _rnd(rng, 0.9, 1.05)
    dur = _rnd(rng, 0.75, 0.95)
    return _meow(rng, dur,
                 [(0, 560 * p), (0.2, 640 * p), (0.6, 520 * p), (1, 340 * p)],
                 [(0, 0.1), (0.25, 0.9), (0.7, 0.7), (1, 0.05)],
                 [(0, 0), (0.6, 0.3), (1, 0.9)],
                 breath=0.15, rough=0.08, sub=0.08, vib_depth=0.015, tilt_open=-6)


def yowl(rng, i):
    """Territorial caterwaul for rooftop rivals: long, wavering, rough."""
    p = _rnd(rng, 0.85, 1.05)
    dur = _rnd(rng, 1.8, 2.4)
    pts = [(0, 330 * p)]
    for k in range(1, 7):
        pts.append((k / 7, (420 + 230 * rng.random()) * p))
    pts.append((1, 360 * p))
    return _meow(rng, dur, pts,
                 [(0, 0.1), (0.15, 0.7), (0.4, 0.95), (0.6, 0.6), (0.8, 0.9), (1, 0.1)],
                 [(0, 0.3), (0.3, 0.6), (0.5, 0.2), (0.7, 0.7), (1, 0.9)],
                 amp_pts=[(0, 0), (0.1, 0.6), (0.4, 1.0), (0.7, 0.8), (0.9, 0.9), (1, 0)],
                 breath=0.2, rough=0.22, sub=0.12, vib_rate=4.5, vib_depth=0.03, jitter=0.02, tilt_open=-6, size=1.1)


def yawn(rng, i):
    """Squeaky yawn: wide slow opening, pitch high then falling, very breathy."""
    p = _rnd(rng, 0.95, 1.1)
    dur = _rnd(rng, 1.0, 1.3)
    y = _meow(rng, dur,
              [(0, 700 * p), (0.25, 980 * p), (0.6, 760 * p), (1, 420 * p)],
              [(0, 0.2), (0.3, 1.0), (0.75, 1.0), (1, 0.2)],
              [(0, 0), (0.8, 0.2), (1, 0.6)],
              amp_pts=[(0, 0), (0.15, 0.5), (0.35, 0.8), (0.7, 0.4), (1, 0)],
              breath=0.6, vib_depth=0.01, tilt_open=-9, tilt_closed=-14)
    # jaw click at the end
    n = len(y)
    c = dsp.bp(dsp.click(ns(0.006), rng), 900, 4000) * 0.25
    dsp.place(y, c, int(n * 0.93))
    return y


# =========================================================================== purr
def _purr(rng, length_s, intensity=1.0, loop=True):
    n = ns(length_s)
    out = np.zeros(n)
    breath_env = np.zeros(n)
    t = 0.0
    phase = rng.uniform(0, 1)
    kernels = []
    for _ in range(8):  # precomputed pulse kernels (each glottal opening/closing burst)
        L = ns(0.022)
        k = rng.standard_normal(L) * np.exp(-np.arange(L) / ns(0.0045))
        thump = np.sin(2 * np.pi * rng.uniform(70, 110) * np.arange(L) / SR) * np.exp(-np.arange(L) / ns(0.006))
        kernels.append(dsp.lp(k, 2600, 2) * 0.8 + thump * 0.9)
    while t < length_s - 0.05:
        exhale = rng.uniform(1.15, 1.4)
        inhale = rng.uniform(0.8, 1.0)
        for seg, dur, rate, g, bright in (("ex", exhale, rng.uniform(23.5, 25.5), 1.0, 0.0),
                                           ("in", inhale, rng.uniform(26.0, 28.5), 0.55, 0.35)):
            gap = rng.uniform(0.04, 0.09)
            seg_n = ns(dur)
            tt = 1.0 / rate
            k = 0.0
            while k < dur:
                frac = k / dur
                env = min(1.0, frac / 0.1) * min(1.0, (1 - frac) / 0.12)
                a = g * env * (1 + 0.18 * rng.standard_normal()) * intensity
                pos = ns(t + k)
                ker = kernels[rng.integers(0, len(kernels))]
                # double pulse: opening + closing burst
                (dsp.place_wrap if loop else dsp.place)(out, ker * a, pos)
                (dsp.place_wrap if loop else dsp.place)(out, ker * a * (0.45 + bright), pos + ns(tt * rng.uniform(0.4, 0.5)))
                k += tt * (1 + 0.025 * rng.standard_normal())
            # airflow envelope
            b0, b1 = ns(t), min(n, ns(t + dur))
            seg_len = b1 - b0
            if seg_len > 0:
                w = np.sin(np.linspace(0, np.pi, seg_len)) ** 0.7 * (0.8 if seg == "ex" else 1.0)
                breath_env[b0:b1] += w
            t += dur + gap
            if t >= length_s - 0.05:
                break
    # vocal tract / nasal resonances
    y = dsp.peak(out, 230, 1.2, 9)
    y = dsp.peak(y, 620, 1.5, 6)
    y = dsp.peak(y, 1350, 2.0, 3)
    y = dsp.lp(y, 1900, 3)
    y = dsp.hp(y, 22, 2)
    air = dsp.bp(dsp.pink(n, rng), 250, 2400, 2) * breath_env * 0.06
    y = y / (np.abs(y).max() + 1e-9) + air
    if loop:
        # breath envelope was not wrapped; gently blend seam
        x2 = np.concatenate([y, y[:ns(0.3)]])
        y = dsp.loop_crossfade(x2, n, ns(0.3))
    return y


def purr_loop(rng, i):
    return _purr(rng, 16.0 + i * 1.7, intensity=1.0, loop=True)


def purr_once(rng, i):
    y = _purr(rng, 4.2, loop=False)
    return dsp.fades(y, 0.25, 0.6)


# =========================================================================== hiss / growl / spit
def hiss(rng, i):
    dur = _rnd(rng, 0.7, 1.3)
    n = ns(dur)
    fm = formant_tracks([
        ([(0, 2600), (0.5, 2900), (1, 2500)], 1400),
        ([(0, 5000), (0.6, 5600), (1, 4800)], 2200),
        ([(0, 8400), (1, 8000)], 3200),
    ], n)
    amp = dsp.env_points([(0, 0), (0.012, 1.0), (0.05, 0.75), (dur * 0.5, 0.85), (dur * 0.85, 0.7), (dur, 0)], n)
    trem = 1 + 0.13 * np.sin(2 * np.pi * _rnd(rng, 7, 11) * np.arange(n) / SR) + 0.1 * dsp.smooth_noise(n, 15, rng)
    y = noise_formant(n, fm, rng, amp * trem, hp_hz=1300)
    # 'spit' burst at onset with lower 'kh' component
    sp = ns(0.04)
    burst = dsp.bp(rng.standard_normal(sp), 700, 9000) * np.exp(-np.arange(sp) / ns(0.01)) * 1.6
    dsp.place(y, burst, 0)
    if i % 2 == 1:  # growl underlay
        f0 = f0_track([(0, 110), (1, 95)], n, rng, 0, 0, 0.05)
        g = pulse_voice(f0, amp * 0.18, formant_tracks([(500, 180), (1200, 300), (2500, 400)], n), rng,
                        jitter=0.06, shimmer=0.3, irregular=0.4, breath=0.1)
        y = y + g
    return dsp.fades(y, 0.001, 0.05)


def growl(rng, i):
    dur = _rnd(rng, 1.6, 2.8)
    n = ns(dur)
    base = _rnd(rng, 95, 125)
    yowl_end = i == 2
    pts = [(0, base * 0.9), (0.5, base), (1, base * 1.05)]
    if yowl_end:
        pts = [(0, base * 0.9), (0.5, base), (0.7, base * 1.6), (0.85, base * 3.5), (1, base * 2.8)]
    f0 = f0_track(pts, n, rng, vib_rate=0, vib_depth=0, jitter=0.07, drift=0.08)
    op = [(0, 0.1), (0.7, 0.15), (1, 0.15)] if not yowl_end else [(0, 0.1), (0.65, 0.15), (0.85, 0.8), (1, 0.3)]
    a = np.clip(contour(op, n), 0, 1)
    fm = [(420 + 900 * a, 160 + 0 * a), (1100 + 900 * a, 280 + 0 * a), (2500 + 600 * a, 420 + 0 * a), (3700 + 0 * a, 600 + 0 * a)]
    sw = 1 + 0.25 * dsp.smooth_noise(n, 2.5, rng)
    amp = dsp.env_points([(0, 0), (0.15, 0.8), (dur * 0.4, 1.0), (dur * 0.85, 0.85), (dur, 0)], n) * sw
    y = pulse_voice(f0, amp, fm, rng, tilt_db_oct=-7.5, breath=0.18, jitter=0.07, shimmer=0.3, irregular=0.5)
    return dsp.fades(dsp.lp(dsp.hp(y, 60, 2), 5000, 2), 0.02, 0.1)


# =========================================================================== breaths, sniffs, effort
def _fur_swish(rng, dur, lo=700, hi=6000, peak_t=0.5):
    n = ns(dur)
    nz = dsp.bp(rng.standard_normal(n), lo, hi, 2)
    crackle = dsp.frac_impulses(n, np.sort(rng.uniform(0, dur, int(dur * 300))), rng.uniform(0.2, 1, int(dur * 300)))
    crackle = dsp.hp(crackle, 2500, 2)
    env = dsp.env_points([(0, 0), (dur * peak_t, 1), (dur, 0)], n)
    return (nz * 0.7 + crackle * 0.5) * env


def jump_effort(rng, i):
    dur = _rnd(rng, 0.14, 0.2)
    n = ns(dur)
    fm = formant_tracks([(900, 300), (1900, 450), (3600, 700)], n)
    amp = dsp.env_points([(0, 0), (0.012, 1), (dur * 0.4, 0.5), (dur, 0)], n)
    br = noise_formant(n, fm, rng, amp, hp_hz=350)
    sw = _fur_swish(rng, dur * 1.4, 900, 6500, 0.35)
    y = dsp.pad_to(br, len(sw)) * 0.8 + sw * 0.55
    # claws push-off scratch
    sc = dsp.bp(rng.standard_normal(ns(0.03)), 2500, 9000) * np.exp(-np.arange(ns(0.03)) / ns(0.008)) * 0.35
    dsp.place(y, sc, 0)
    return dsp.fades(y, 0.002, 0.03)


def sniff(rng, i):
    """3-5 quick nasal inhales (cat-sense)."""
    count = int(rng.integers(3, 6))
    total = 0.12 + count * 0.12
    n = ns(total + 0.1)
    y = np.zeros(n)
    t = 0.02
    for k in range(count):
        d = _rnd(rng, 0.05, 0.08)
        m = ns(d)
        fm = formant_tracks([(_rnd(rng, 1800, 2600), 700), (_rnd(rng, 4200, 5200), 1200)], m)
        amp = dsp.env_points([(0, 0), (d * 0.3, 1), (d, 0)], m)
        y_k = noise_formant(m, fm, rng, amp, hp_hz=900)
        dsp.place(y, y_k * _rnd(rng, 0.6, 1.0), ns(t))
        t += d + _rnd(rng, 0.03, 0.07)
    return y


# =========================================================================== scratching / grooming / eating
def _scratch_stroke(rng, dur, surface="wood"):
    n = ns(dur)
    rate = _rnd(rng, 180, 380)
    cnt = int(rate * dur)
    times = np.sort(rng.uniform(0, dur, cnt))
    env = dsp.env_points([(0, 0), (dur * 0.2, 1), (dur * 0.75, 0.8), (dur, 0)], n)
    amps = rng.uniform(0.3, 1.0, cnt) * np.interp(times, np.arange(n) / SR, env)
    clicks = dsp.frac_impulses(n, times, amps)
    rasp = dsp.bp(rng.standard_normal(n), 1800, 7000, 2) * env * 0.25
    if surface == "wood":
        body = dsp.resonator_bank(clicks, [240, 410, 690, 1150, 1900], [0.03, 0.025, 0.02, 0.015, 0.01], [1, 0.8, 0.6, 0.4, 0.3])
        y = dsp.bp(clicks, 1500, 9000) * 0.9 + body * 0.25 + rasp
    else:  # fabric: duller, fibrous pops
        y = dsp.bp(clicks, 900, 6000) * 0.7 + dsp.lp(rasp, 3500) * 1.2
        pops = dsp.frac_impulses(n, np.sort(rng.uniform(0, dur, int(dur * 25))), rng.uniform(0.5, 1.5, int(dur * 25)))
        y += dsp.bp(pops, 600, 3000) * 0.6
    return y


def scratch(rng, i, surface="wood", strokes=None, loop_len=None):
    strokes = strokes or int(rng.integers(4, 7))
    if loop_len:
        n = ns(loop_len)
    else:
        n = ns(strokes * 0.36 + 0.3)
    y = np.zeros(n)
    t = 0.0
    k = 0
    while (loop_len and t < loop_len - 0.05) or (not loop_len and k < strokes):
        d = _rnd(rng, 0.17, 0.28)
        s = _scratch_stroke(rng, d, surface) * _rnd(rng, 0.7, 1.0) * (1.0 if k % 2 == 0 else 0.85)
        (dsp.place_wrap if loop_len else dsp.place)(y, s, ns(t))
        t += d + _rnd(rng, 0.08, 0.16)
        k += 1
    return y


def scratch_wood(rng, i):
    return scratch(rng, i, "wood")


def scratch_fabric(rng, i):
    return scratch(rng, i, "fabric")


def scratch_loop(rng, i):
    return scratch(rng, i, "wood", loop_len=4.4)


def _lick(rng):
    d = _rnd(rng, 0.07, 0.11)
    n = ns(d + 0.05)
    env = dsp.env_points([(0, 0), (d * 0.25, 1), (d, 0.15), (d + 0.04, 0)], n)
    wet = dsp.bp(rng.standard_normal(n), 1600, 7500, 2) * env
    cnt = int(rng.integers(6, 16))
    clicks = dsp.frac_impulses(n, np.sort(rng.uniform(0, d, cnt)), rng.uniform(0.3, 1.0, cnt))
    y = wet * 0.5 + dsp.hp(clicks, 2000) * 0.6
    # tongue retract 'tk'
    tk = dsp.bp(dsp.click(ns(0.004), rng), 1500, 5000) * 0.5
    dsp.place(y, tk, ns(d * 0.9))
    return y


def groom_loop(rng, i):
    L = 6.0
    n = ns(L)
    y = np.zeros(n)
    t = 0.0
    while t < L - 0.05:
        dsp.place_wrap(y, _lick(rng) * _rnd(rng, 0.6, 1.0), ns(t))
        t += _rnd(rng, 0.24, 0.36) if rng.random() > 0.08 else _rnd(rng, 0.6, 0.9)
    # fur rasp under the tongue strokes
    rasp = dsp.bp(dsp.pink(n, rng), 2500, 9000) * 0.05 * (1 + 0.5 * dsp.smooth_noise_periodic(n, 3, rng))
    return y + rasp


def _crunch(rng, strength=1.0):
    d = _rnd(rng, 0.02, 0.05)
    n = ns(d + 0.06)
    cnt = int(rng.integers(8, 30) * strength)
    times = np.sort(rng.exponential(d / 3, cnt)).clip(0, d)
    imp = dsp.frac_impulses(n, times, rng.uniform(0.2, 1.0, cnt) * np.exp(-times / d))
    lo, hi = _rnd(rng, 900, 2000), _rnd(rng, 5000, 10000)
    y = dsp.bp(imp, lo, hi, 2)
    thud = dsp.lp(dsp.click(ns(0.02), rng), 400, 2) * 0.6
    dsp.place(y, thud, 0)
    return y * strength


def _smack(rng, wet=0.5):
    d = _rnd(rng, 0.03, 0.06)
    n = ns(d)
    env = np.exp(-np.arange(n) / ns(d / 4))
    y = dsp.bp(rng.standard_normal(n), 700, 4000) * env * wet
    tk = dsp.bp(dsp.click(ns(0.003), rng), 1000, 6000) * 0.8
    dsp.place(y, tk, 0)
    return y


def eat_loop(rng, i):
    """Dry food/kibble: crunchy chewing cycles, head tilts, swallow pauses."""
    L = 6.4
    n = ns(L)
    y = np.zeros(n)
    t = 0.0
    while t < L - 0.05:
        burst = int(rng.integers(3, 7))
        for _ in range(burst):
            for c in range(int(rng.integers(1, 3))):
                dsp.place_wrap(y, _crunch(rng, _rnd(rng, 0.5, 1.0)), ns(t + c * _rnd(rng, 0.03, 0.07)))
            dsp.place_wrap(y, _smack(rng, 0.35), ns(t + _rnd(rng, 0.12, 0.2)))
            t += _rnd(rng, 0.3, 0.4)
        t += _rnd(rng, 0.25, 0.5)
    return y


def eat_wet_loop(rng, i):
    """Wet food / fish: squelchy chewing, smacks, tearing."""
    L = 6.0
    n = ns(L)
    y = np.zeros(n)
    t = 0.0
    while t < L - 0.05:
        d = _rnd(rng, 0.08, 0.14)
        m = ns(d)
        env = dsp.env_points([(0, 0), (d * 0.3, 1), (d, 0)], m)
        sq = dsp.bp(rng.standard_normal(m), 300, 2500) * env
        bub = dsp.frac_impulses(m, np.sort(rng.uniform(0, d, 10)), rng.uniform(0.3, 1, 10))
        sq = sq * 0.6 + dsp.bp(bub, 1200, 5000) * 0.5
        dsp.place_wrap(y, sq * _rnd(rng, 0.6, 1.0), ns(t))
        if rng.random() < 0.45:
            dsp.place_wrap(y, _smack(rng, 0.7), ns(t + d + 0.03))
        if rng.random() < 0.12:  # tear
            tear = dsp.bp(rng.standard_normal(ns(0.12)), 1500, 7000) * dsp.env_points([(0, 0), (0.02, 1), (0.12, 0)], ns(0.12)) * 0.5
            dsp.place_wrap(y, tear, ns(t + 0.05))
        t += _rnd(rng, 0.28, 0.4)
    return y


def eat_crunch(rng, i):
    n = ns(0.5)
    y = np.zeros(n)
    for k in range(int(rng.integers(2, 4))):
        dsp.place(y, _crunch(rng, _rnd(rng, 0.7, 1.0)), ns(k * _rnd(rng, 0.04, 0.09)))
    dsp.place(y, _smack(rng, 0.4), ns(0.25))
    return y


def _lap(rng):
    n = ns(0.09)
    t = np.arange(n) / SR
    f0 = _rnd(rng, 600, 1000)
    chirp = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 2.2 * t / 0.03)) / SR) * np.exp(-t / 0.012)
    sp = dsp.hp(rng.standard_normal(n), 2500) * np.exp(-t / 0.008) * 0.3
    y = chirp * 0.6 + sp
    tk = dsp.bp(dsp.click(ns(0.003), rng), 1200, 5000) * 0.3
    dsp.place(y, tk, ns(0.05))
    return y


def lap_loop(rng, i):
    L = 5.0
    n = ns(L)
    y = np.zeros(n)
    t = 0.0
    while t < L - 0.02:
        dsp.place_wrap(y, _lap(rng) * _rnd(rng, 0.5, 1.0), ns(t))
        t += _rnd(rng, 0.22, 0.28) if rng.random() > 0.06 else _rnd(rng, 0.5, 0.8)
    return y


# =========================================================================== pickup / drop / swipe / shake / knead
def pickup(rng, i):
    n = ns(0.3)
    y = np.zeros(n)
    tk = dsp.bp(dsp.click(ns(0.005), rng), 1500, 6000)  # teeth
    dsp.place(y, tk, ns(0.04))
    rus = dsp.bp(rng.standard_normal(ns(0.12)), 1200, 7000) * dsp.env_points([(0, 0), (0.02, 1), (0.12, 0)], ns(0.12))
    dsp.place(y, rus * 0.45, ns(0.05))
    dsp.place(y, _fur_swish(rng, 0.18, 800, 5000, 0.4) * 0.35, 0)
    return y


def drop(rng, i):
    n = ns(0.45)
    y = np.zeros(n)
    pulse = dsp.half_sine(ns(0.006)) * rng.choice([-1, 1])
    body = dsp.resonator_bank(dsp.pad_to(pulse, n), [_rnd(rng, 140, 220), _rnd(rng, 380, 600), _rnd(rng, 900, 1500)],
                              [0.03, 0.02, 0.012], [1.0, 0.6, 0.3])
    y += body
    y += dsp.bp(dsp.pad_to(dsp.click(ns(0.01), rng), n), 800, 6000) * 0.3
    # small bounce
    b = ns(_rnd(rng, 0.08, 0.13))
    dsp.place(y, body[:n - b] * 0.3, b)
    return y


def swipe(rng, i):
    dur = _rnd(rng, 0.17, 0.26)
    n = ns(dur)
    t = np.arange(n) / dur / SR
    fc = 900 + 2600 * np.sin(np.pi * np.clip(t * 1.1, 0, 1)) ** 2

    def g(f, tt):
        idx = np.minimum((tt * SR).astype(int), n - 1)
        c = fc[idx][None, :]
        return 1 / np.sqrt(1 + ((f[:, None] - c) / (0.6 * c)) ** 2) ** 2
    y = dsp.stft_shape(rng.standard_normal(n), g, 256)
    env = dsp.env_points([(0, 0), (dur * 0.55, 1), (dur, 0)], n) ** 1.5
    y = y / (np.abs(y).max() + 1e-9) * env
    y += _fur_swish(rng, dur, 1200, 7000, 0.5) * 0.25
    return dsp.fades(y, 0.002, 0.02)


def shake(rng, i, wet=True):
    dur = _rnd(rng, 0.75, 1.0)
    n = ns(dur + 0.35)
    y = np.zeros(n)
    m = ns(dur)
    tt = np.arange(m) / SR
    rate = 6.5 + 2.0 * tt / dur
    ph = 2 * np.pi * np.cumsum(rate) / SR
    am = np.abs(np.sin(ph)) ** 1.6 * dsp.env_points([(0, 0), (0.08, 1), (dur * 0.7, 0.85), (dur, 0)], m)
    fur = dsp.bp(rng.standard_normal(m), 900, 7000, 2) * am
    fur += dsp.lp(rng.standard_normal(m), 900) * am * 0.4  # body flop
    y[:m] += fur * 0.8
    # ear flaps at the end of the shake (the characteristic 'flap-flap')
    tf = dur * 0.82
    for k in range(int(rng.integers(2, 5))):
        f = dsp.lp(dsp.click(ns(0.012), rng, 1.0), 1600, 2) * 1.4 * (0.85 ** k)
        dsp.place(y, f, ns(tf + k * _rnd(rng, 0.045, 0.06)))
    if wet:
        cnt = int(rng.integers(120, 220))
        times = np.sort(rng.uniform(0.05, dur + 0.3, cnt))
        drops = np.zeros(n)
        for tdrop in times:
            fr = _rnd(rng, 2500, 7000)
            L = ns(0.012)
            d = np.sin(2 * np.pi * fr * (1 + 1.5 * np.arange(L) / L) * np.arange(L) / SR) * np.exp(-np.arange(L) / ns(0.003))
            dsp.place(drops, d * _rnd(rng, 0.05, 0.3), ns(tdrop))
        y += drops
    return dsp.fades(y, 0.005, 0.05)


def shake_wet(rng, i):
    return shake(rng, i, True)


def shake_dry(rng, i):
    return shake(rng, i, False)


def knead_loop(rng, i):
    """Kneading a cushion: alternating paw presses, soft fabric compressions, occasional claw snag."""
    L = 4.0
    n = ns(L)
    y = np.zeros(n)
    t = 0.0
    k = 0
    while t < L - 0.02:
        d = _rnd(rng, 0.12, 0.18)
        m = ns(d)
        env = dsp.env_points([(0, 0), (d * 0.35, 1), (d, 0)], m)
        press = dsp.lp(rng.standard_normal(m), 1400, 2) * env * 0.6 + dsp.bp(rng.standard_normal(m), 1500, 5000) * env * 0.15
        if rng.random() < 0.25:
            sn = dsp.bp(dsp.frac_impulses(m, np.sort(rng.uniform(0, d, 6)), rng.uniform(0.3, 1, 6)), 2000, 8000) * 0.5
            press += sn
        dsp.place_wrap(y, press * (1.0 if k % 2 else 0.8), ns(t))
        t += _rnd(rng, 0.32, 0.42)
        k += 1
    return y


# =========================================================================== registry
V = "Voice"
SOUNDS = [
    Sound("cat_meow_short", meow_short, "sfx", "cat", 5, V, -16, desc="Short 'mew/meow' (kind &\"short\")", unit_size=4, max_distance=45, priority=8),
    Sound("cat_meow_soft", meow_soft, "sfx", "cat", 3, V, -20, desc="Tiny soft mew (affection)", unit_size=3, max_distance=30, priority=8),
    Sound("cat_meow_chirp", meow_chirp, "sfx", "cat", 4, V, -18, desc="'mrrp!' rising chirp (kind &\"chirp\")", unit_size=3, max_distance=35, priority=8),
    Sound("cat_meow_trill", meow_trill, "sfx", "cat", 3, V, -18, desc="'brrrrp' rolled trill greeting", unit_size=3, max_distance=35, priority=8),
    Sound("cat_meow_loud", meow_loud, "sfx", "cat", 4, V, -13, desc="Loud plaintive meow (kind &\"loud\")", unit_size=6, max_distance=70, priority=9),
    Sound("cat_meow_question", meow_question, "sfx", "cat", 3, V, -16, desc="'mrrow?' questioning", unit_size=4, max_distance=45, priority=8),
    Sound("cat_meow_demand", meow_demand, "sfx", "cat", 3, V, -14, desc="Insistent 'MEOW!' (demanding food)", unit_size=5, max_distance=55, priority=8),
    Sound("cat_meow_greet", meow_greet, "sfx", "cat", 3, V, -17, desc="Friendly 'mrr-aow' greeting", unit_size=4, max_distance=45, priority=8),
    Sound("cat_meow_complain", meow_complain, "sfx", "cat", 3, V, -16, desc="Long descending grumble", unit_size=4, max_distance=45, priority=8),
    Sound("cat_yowl", yowl, "sfx", "cat", 3, V, -14, desc="Territorial caterwaul (rooftop rivals)", unit_size=8, max_distance=90, priority=8),
    Sound("cat_yawn", yawn, "sfx", "cat", 2, V, -20, desc="Squeaky yawn (waking from nap)", unit_size=3, max_distance=25),
    Sound("cat_purr_loop", purr_loop, "sfx", "cat", 1, V, -24, "integrated", loop=True, quality=5, unit_size=1.5, max_distance=12, pitch_jitter=0.0, desc="Purr loop (~25 Hz pulses, inhale/exhale)"),
    Sound("cat_purr", purr_once, "sfx", "cat", 2, V, -23, "integrated", unit_size=1.5, max_distance=12, desc="Purr one-shot ~4 s (kind &\"purr\")"),
    Sound("cat_hiss", hiss, "sfx", "cat", 4, V, -15, desc="Hiss with spit onset (odd variants have growl underlay)", unit_size=5, max_distance=40, priority=8),
    Sound("cat_growl", growl, "sfx", "cat", 3, V, -17, "short", desc="Low rough growl (variant 3 rises into a yowl)", unit_size=4, max_distance=35, priority=8),
    Sound("cat_sniff", sniff, "sfx", "cat", 3, V, -24, desc="Quick sniffs (cat-sense)", unit_size=1.5, max_distance=10),
    Sound("cat_jump_effort", jump_effort, "sfx", "cat", 4, "SFX", -25, desc="Push-off exhale + fur swish", unit_size=2, max_distance=15),
    Sound("cat_scratch", scratch_wood, "sfx", "cat", 3, "SFX", -21, "short", desc="Claws on wood post, 4-6 strokes", unit_size=2.5, max_distance=25),
    Sound("cat_scratch_fabric", scratch_fabric, "sfx", "cat", 2, "SFX", -22, "short", desc="Claws on fabric/sofa", unit_size=2.5, max_distance=25),
    Sound("cat_scratch_loop", scratch_loop, "sfx", "cat", 1, "SFX", -22, "integrated", loop=True, desc="Scratching loop for the scratch anim", unit_size=2.5, max_distance=25, pitch_jitter=0.0),
    Sound("cat_groom_loop", groom_loop, "sfx", "cat", 1, "SFX", -27, "integrated", loop=True, desc="Licking/grooming loop", unit_size=1.5, max_distance=10, pitch_jitter=0.0),
    Sound("cat_eat_loop", eat_loop, "sfx", "cat", 1, "SFX", -23, "integrated", loop=True, desc="Crunchy dry-food chewing loop", unit_size=1.5, max_distance=12, pitch_jitter=0.0),
    Sound("cat_eat_wet_loop", eat_wet_loop, "sfx", "cat", 1, "SFX", -24, "integrated", loop=True, desc="Wet food / fish chewing loop", unit_size=1.5, max_distance=12, pitch_jitter=0.0),
    Sound("cat_eat_crunch", eat_crunch, "sfx", "cat", 4, "SFX", -22, desc="Single crunchy bite", unit_size=1.5, max_distance=12),
    Sound("cat_lap_loop", lap_loop, "sfx", "cat", 1, "SFX", -25, "integrated", loop=True, desc="Lapping water loop", unit_size=1.5, max_distance=10, pitch_jitter=0.0),
    Sound("cat_pickup", pickup, "sfx", "cat", 3, "SFX", -24, desc="Grab item in mouth", unit_size=2, max_distance=15),
    Sound("cat_drop", drop, "sfx", "cat", 3, "SFX", -21, desc="Drop item from mouth", unit_size=2.5, max_distance=20),
    Sound("cat_swipe", swipe, "sfx", "cat", 4, "SFX", -21, desc="Paw swipe whoosh", unit_size=2, max_distance=15),
    Sound("cat_shake_wet", shake_wet, "sfx", "cat", 2, "SFX", -20, desc="Shake-off with water spray + ear flaps", unit_size=2.5, max_distance=20),
    Sound("cat_shake_dry", shake_dry, "sfx", "cat", 2, "SFX", -22, desc="Dry fur shake + ear flaps", unit_size=2.5, max_distance=20),
    Sound("cat_knead_loop", knead_loop, "sfx", "cat", 1, "SFX", -29, "integrated", loop=True, desc="Kneading a cushion loop", unit_size=1.5, max_distance=8, pitch_jitter=0.0),
]
