"""Physical-ish foley: cat paw contacts per surface (steps, runs, landings), knock-over impacts,
splashes and push scrapes. Everything is excitation x surface response (modal / granular)."""
from __future__ import annotations

import numpy as np

import dsp
from dsp import SR, ns
from registry import Sound


def _r(rng, lo, hi):
    return float(rng.uniform(lo, hi))


def _pad_pulse(rng, force, soft=1.0):
    """Paw pad contact force pulse (raised half-sine); softer pads -> longer pulse -> darker."""
    tc = _r(rng, 0.008, 0.014) * soft / (0.6 + 0.4 * force)
    p = dsp.half_sine(ns(tc)) ** 1.5
    return p * force


def _grains(rng, n, count, t_spread, lo, hi, amp=1.0, t0=0.0, decay=None):
    if count <= 0:
        return np.zeros(n)
    times = t0 + np.sort(rng.exponential(t_spread / 2.5, count)).clip(0, t_spread)
    a = rng.uniform(0.15, 1.0, count) ** 2
    if decay:
        a = a * np.exp(-(times - t0) / decay)
    imp = dsp.frac_impulses(n, times, a)
    return dsp.bp(imp, lo, hi, 2) * amp


def _noise_burst(rng, n, dur, lo, hi, t0=0.0, att=0.15):
    m = ns(dur)
    env = dsp.env_points([(0, 0), (dur * att, 1), (dur, 0)], m) ** 1.5
    b = dsp.bp(rng.standard_normal(m), lo, hi, 2) * env
    out = np.zeros(n)
    dsp.place(out, b, ns(t0))
    return out


def _thump(rng, n, force, fc=300.0, res=110.0, decay=0.006, soft=1.0):
    pulse = dsp.pad_to(_pad_pulse(rng, force, soft), n)
    body = dsp.resonator_bank(pulse, [res * _r(rng, 0.85, 1.15)], [decay], [1.0])
    # pads are soft: keep the thump short and above the sub range (no 'pump' on headphones)
    return dsp.hp(dsp.lp(pulse * 0.6 + body * 0.25, fc, 2), 75, 2) * 0.55


def _modal_hit(rng, n, force, freqs, decays, amps, t0=0.0, exc_cut=4000.0):
    freqs = np.asarray(freqs) * rng.uniform(0.94, 1.06, len(freqs))
    exc = 1 / (1 + (freqs / exc_cut) ** 2)  # soft exciter cannot drive high modes
    m = n - ns(t0)
    y = dsp.modal(m, freqs, np.asarray(decays) * rng.uniform(0.8, 1.2, len(freqs)),
                  np.asarray(amps) * exc * force, phases=rng.uniform(0, 2 * np.pi, len(freqs)), attack=0.0008)
    out = np.zeros(n)
    dsp.place(out, y, ns(t0))
    return out


def contact(rng, surface: str, force: float = 0.5, claws: bool = False) -> np.ndarray:
    """One paw contact. force 0..1."""
    n = ns(0.5 if surface in ("metal", "water") else 0.3)
    f = force
    y = np.zeros(n)
    if surface == "asphalt":
        y += _thump(rng, n, f, 420, 120) * 0.9
        y += _grains(rng, n, int(rng.integers(6, 16) * (0.5 + f)), 0.045, 2200, 8500, 0.5 * f)
        y += _grains(rng, n, int(rng.integers(2, 5)), 0.03, 800, 3000, 0.35 * f)
        y += _noise_burst(rng, n, _r(rng, 0.02, 0.035), 1500, 6000, 0.002) * 0.09 * f
    elif surface == "concrete":
        y += _thump(rng, n, f, 520, 140) * 1.0
        y += _grains(rng, n, int(rng.integers(3, 8) * (0.5 + f)), 0.03, 3000, 9500, 0.32 * f)
        y += _noise_burst(rng, n, _r(rng, 0.025, 0.04), 1800, 7000, 0.003) * 0.08 * f
    elif surface == "tile":
        y += _thump(rng, n, f, 650, 170) * 0.8
        y += _modal_hit(rng, n, f, [_r(rng, 1600, 2000), 3200, 4700, 6900], [0.012, 0.009, 0.006, 0.004], [0.35, 0.25, 0.15, 0.1], 0.001, 2500)
        if claws or rng.random() < 0.3:
            for k in range(int(rng.integers(1, 3))):
                tick = dsp.hp(dsp.click(ns(0.002), rng), 4500, 2) * _r(rng, 0.08, 0.2) * (0.5 + f)
                dsp.place(y, tick, ns(_r(rng, 0.004, 0.02)))
    elif surface == "wood":
        base = _r(rng, 105, 145)
        y += _thump(rng, n, f, 400, base) * 0.7
        y += _modal_hit(rng, n, f, [base, base * 1.9, base * 3.2, base * 5.1, base * 8.3],
                        [0.028, 0.022, 0.016, 0.011, 0.007], [0.35, 0.4, 0.32, 0.2, 0.12], 0.001, 1500)
        y += _grains(rng, n, int(rng.integers(3, 8)), 0.02, 900, 4500, 0.22 * f)
        y += _noise_burst(rng, n, _r(rng, 0.015, 0.03), 700, 3500, 0.001) * 0.06 * f
        if rng.random() < 0.2:  # board creak
            m = ns(_r(rng, 0.06, 0.12))
            fr = _r(rng, 350, 800) * (1 + 0.15 * dsp.smooth_noise(m, 30, rng))
            cr = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.sign(np.sin(2 * np.pi * np.cumsum(fr * 0.5) / SR)) ** 2
            cr = dsp.bp(cr * dsp.env_points([(0, 0), (m / SR * 0.3, 1), (m / SR, 0)], m), 300, 3000) * 0.06 * f
            dsp.place(y, cr, ns(_r(rng, 0.01, 0.04)))
    elif surface == "metal":
        f0 = _r(rng, 170, 320)
        ratios = np.array([1, 1.58, 2.31, 3.17, 4.12, 5.3, 6.6, 8.2, 10.3]) * rng.uniform(0.95, 1.05, 9)
        decs = np.array([0.22, 0.2, 0.17, 0.14, 0.11, 0.09, 0.07, 0.05, 0.04])
        amps = np.array([0.6, 0.5, 0.45, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1])
        y += _modal_hit(rng, n, f, f0 * ratios, decs, amps, 0.001, 1800) * 0.3
        y += _thump(rng, n, f, 350, 95, 0.02) * 1.6
        # hollow 'dunk' of the panel / AC casing
        y += _modal_hit(rng, n, f, [_r(rng, 90, 140), _r(rng, 210, 280)], [0.04, 0.03], [0.6, 0.4], 0.001, 600)
        # sheet flex 'boing' glide
        m = ns(0.12)
        fr = _r(rng, 80, 120) * (1 - 0.25 * np.arange(m) / m)
        bo = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-np.arange(m) / ns(0.03)) * 0.12 * f
        dsp.place(y, bo, 0)
    elif surface == "roof_tile":
        y += _thump(rng, n, f, 500, 150) * 0.7
        y += _modal_hit(rng, n, f, [_r(rng, 650, 900), _r(rng, 1450, 1800), _r(rng, 2300, 2900), 3700],
                        [0.025, 0.018, 0.012, 0.008], [0.5, 0.35, 0.22, 0.12], 0.001, 2200)
        if rng.random() < 0.35:  # loose tile clack
            for k in range(int(rng.integers(2, 4))):
                y += _modal_hit(rng, n, f * _r(rng, 0.25, 0.5), [_r(rng, 1800, 2600), _r(rng, 3500, 4500)], [0.01, 0.006], [0.5, 0.3],
                                _r(rng, 0.015, 0.05) + k * _r(rng, 0.012, 0.03), 6000)
        y += _grains(rng, n, int(rng.integers(1, 5)), 0.025, 2500, 8000, 0.12 * f)
    elif surface == "grass":
        y += _thump(rng, n, f, 220, 90) * 0.5
        cnt = int(rng.integers(25, 60) * (0.5 + f))
        dur = _r(rng, 0.07, 0.15)
        times = np.sort(rng.uniform(0, dur, cnt))
        bl = np.zeros(n)
        for tt in times:
            m = ns(_r(rng, 0.001, 0.004))
            c = _r(rng, 2000, 8500)
            g = dsp.reson(rng.standard_normal(m) * dsp.half_sine(m), c, c * 0.5)
            dsp.place(bl, g * rng.uniform(0.2, 1.0), ns(tt))
        env = dsp.pad_to(dsp.env_points([(0, 0), (dur * 0.3, 1), (dur, 0.2), (dur + 0.05, 0)], ns(dur + 0.05)), n)
        y += bl * env * 0.9 * f
        y += _noise_burst(rng, n, dur, 1200, 4500, 0.0, 0.3) * 0.06 * f
    elif surface == "dirt":
        y += _thump(rng, n, f, 300, 85, 0.01) * 1.1
        y += _grains(rng, n, int(rng.integers(8, 20) * (0.5 + f)), 0.05, 700, 3200, 0.22 * f)
        y += _noise_burst(rng, n, _r(rng, 0.03, 0.05), 2000, 6500, 0.005) * 0.06 * f
    elif surface == "water":
        y += _noise_burst(rng, n, _r(rng, 0.008, 0.014), 600, 4500, 0.0, 0.1) * 0.5 * f
        for k in range(int(rng.integers(2, 6))):
            fb = _r(rng, 800, 2600)
            m = ns(_r(rng, 0.015, 0.035))
            tt = np.arange(m) / SR
            bub = np.sin(2 * np.pi * np.cumsum(fb * (1 + 8 * tt)) / SR) * np.exp(-tt / (m / SR / 3))
            dsp.place(y, bub * _r(rng, 0.1, 0.35) * f, ns(_r(rng, 0.004, 0.06)))
        for k in range(int(rng.integers(3, 9))):
            fb = _r(rng, 2500, 6000)
            m = ns(0.01)
            tt = np.arange(m) / SR
            d = np.sin(2 * np.pi * np.cumsum(fb * (1 + 15 * tt)) / SR) * np.exp(-tt / 0.0025)
            dsp.place(y, d * _r(rng, 0.03, 0.12) * f, ns(_r(rng, 0.03, 0.2)))
        y += _thump(rng, n, f, 250, 80) * 0.25
    elif surface == "fabric":
        y += _thump(rng, n, f, 260, 90, 0.008, 1.6) * 0.8
        y += _noise_burst(rng, n, _r(rng, 0.03, 0.06), 300, 1800, 0.0, 0.3) * 0.08 * f
        y += _noise_burst(rng, n, _r(rng, 0.02, 0.04), 2000, 6000, 0.01, 0.3) * 0.015 * f
    elif surface == "plastic":
        y += _thump(rng, n, f, 500, 160) * 0.6
        b = _r(rng, 380, 470)
        y += _modal_hit(rng, n, f, [b, b * 2.4, b * 4.4, b * 7.6], [0.03, 0.022, 0.014, 0.008], [0.5, 0.4, 0.25, 0.12], 0.001, 2800)
        if rng.random() < 0.3:
            y += _modal_hit(rng, n, f * 0.3, [_r(rng, 1800, 2400), _r(rng, 3200, 4000)], [0.008, 0.005], [0.5, 0.3], _r(rng, 0.02, 0.04), 6000)
    else:
        raise ValueError(surface)
    return y


SURFACES = ["asphalt", "concrete", "tile", "wood", "metal", "roof_tile", "grass", "dirt", "water", "fabric", "plastic"]


def _step(surface, run=False):
    def fn(rng, i):
        f = _r(rng, 0.75, 1.0) if run else _r(rng, 0.4, 0.65)
        y = contact(rng, surface, f, claws=run and rng.random() < 0.5)
        # toes settle / second paw shortly after (cats place hind paw into the front paw's print)
        if rng.random() < (0.7 if run else 0.45):
            y2 = contact(rng, surface, f * _r(rng, 0.25, 0.45))
            off = ns(_r(rng, 0.03, 0.08) if run else _r(rng, 0.01, 0.025))
            dsp.place(y, y2, off)
        return y
    fn.__name__ = f"step_{surface}{'_run' if run else ''}"
    return fn


def step_wet(rng, i):
    n = ns(0.2)
    y = np.zeros(n)
    y += _noise_burst(rng, n, _r(rng, 0.012, 0.02), 900, 5000, 0.0, 0.1) * 0.6
    y += _grains(rng, n, int(rng.integers(6, 14)), 0.04, 2000, 7000, 0.35, decay=0.02)
    for k in range(int(rng.integers(1, 4))):
        fb = _r(rng, 1200, 3200)
        m = ns(0.02)
        tt = np.arange(m) / SR
        dsp.place(y, np.sin(2 * np.pi * np.cumsum(fb * (1 + 10 * tt)) / SR) * np.exp(-tt / 0.005) * 0.2, ns(_r(rng, 0.005, 0.05)))
    return y


# --------------------------------------------------------------------------- landings
FAMILIES = {"stone": "concrete", "tile": "tile", "wood": "wood", "metal": "metal", "roof": "roof_tile",
            "soft": "dirt", "water": "water", "plastic": "plastic"}


def _landing(fam, hard):
    surf = FAMILIES[fam]

    def fn(rng, i):
        n = ns(2.3 if fam == "water" else 1.2 if fam == "metal" else 0.7)
        y = np.zeros(n)
        f = _r(rng, 0.85, 1.0) if hard else _r(rng, 0.45, 0.65)
        # front paws (two, close together), then hind paws
        t = 0.0
        times = [0.0, _r(rng, 0.004, 0.018), _r(rng, 0.045, 0.09), 0]
        times[3] = times[2] + _r(rng, 0.004, 0.02)
        for k, tt in enumerate(times):
            ff = f * (1.0 if k < 2 else 0.8) * _r(rng, 0.85, 1.1)
            s = surf if fam != "soft" else ("grass" if (i + k) % 2 else "dirt")
            dsp.place(y, contact(rng, s, ff, claws=hard), ns(tt))
        # body mass thump
        bm = ns(0.05)
        mass = dsp.lp(rng.standard_normal(bm) * np.exp(-np.arange(bm) / ns(0.012)), 180 if hard else 120, 2)
        lowres = dsp.modal(ns(0.12), [_r(rng, 55, 80)], [0.03], [1.0])
        body = dsp.pad_to(mass, ns(0.12)) * 0.8 + lowres * 0.6
        dsp.place(y, body * (1.0 if hard else 0.4) * (0.5 if fam == "water" else 1.0), ns(times[2] * 0.5))
        if fam == "metal":
            # the whole sheet rings (loud tin-roof landing)
            f0 = _r(rng, 120, 220)
            ratios = np.array([1, 1.51, 2.27, 2.9, 3.7, 4.6, 5.9, 7.4])
            dsp.place(y, dsp.modal(ns(1.1), f0 * ratios * rng.uniform(0.97, 1.03, 8),
                                   [0.6, 0.5, 0.42, 0.35, 0.28, 0.22, 0.16, 0.12],
                                   np.array([1, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15]) * (0.35 if hard else 0.12),
                                   phases=rng.uniform(0, 6, 8), attack=0.001), 0)
        if fam == "water":
            dsp.place(y, _splash(rng, big=hard, scale=0.5 if not hard else 0.8), 0)
        if hard and fam not in ("water", "soft"):
            # claw skid / scrabble to catch balance
            sk = ns(_r(rng, 0.07, 0.14))
            env = dsp.env_points([(0, 0), (sk / SR * 0.2, 1), (sk / SR, 0)], sk)
            skid = dsp.bp(rng.standard_normal(sk), 2500, 9000) * env * 0.12
            skid += dsp.bp(dsp.frac_impulses(sk, np.sort(rng.uniform(0, sk / SR, 25)), rng.uniform(0.2, 1, 25)), 3000, 9000) * 0.25
            dsp.place(y, skid, ns(times[2] + 0.01))
        return y
    fn.__name__ = f"land_{'hard' if hard else 'soft'}_{fam}"
    return fn


# --------------------------------------------------------------------------- impacts
def _bounces(rng, first_dt, e, n_max, min_dt=0.012):
    times, amps = [0.0], [1.0]
    dt = first_dt
    a = 1.0
    t = 0.0
    for _ in range(n_max):
        t += dt
        a *= e * _r(rng, 0.85, 1.1)
        times.append(t)
        amps.append(a)
        dt *= e * _r(rng, 0.9, 1.05)
        if dt < min_dt:
            break
    return np.array(times), np.array(amps)


def _crack(rng, dur=0.006, lo=1500, hi=14000):
    m = ns(dur)
    return dsp.bp(rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 4)), lo, hi, 2)


def _shard_field(rng, n, count, t_spread, f_lo, f_hi, dec_lo, dec_hi, t0=0.0, amp=1.0):
    y = np.zeros(n)
    times = t0 + np.sort(rng.gamma(1.3, t_spread / 4, count)).clip(0, t_spread)
    for tt in times:
        k = int(rng.integers(2, 4))
        fr = rng.uniform(f_lo, f_hi, k)
        dec = rng.uniform(dec_lo, dec_hi, k)
        m = ns(dec.max() * 4)
        s = dsp.modal(m, fr, dec, rng.uniform(0.3, 1, k), phases=rng.uniform(0, 6, k), attack=0.0003)
        size = rng.uniform(0.05, 1.0) ** 2
        a = size * amp * np.exp(-(tt - t0) / (t_spread * 0.6))
        dsp.place(y, s * a, ns(tt))
        if rng.random() < 0.5:  # shard's tiny tick on landing
            dsp.place(y, dsp.hp(dsp.click(ns(0.0015), rng), 3000) * a * 0.5, ns(tt))
    return y


def impact_ceramic(rng, i):
    n = ns(1.5)
    y = np.zeros(n)
    f1 = _r(rng, 600, 1150)
    y += dsp.modal(n, f1 * np.array([1, 2.3, 3.9, 5.6, 7.8]) * rng.uniform(0.97, 1.03, 5),
                   [0.05, 0.035, 0.025, 0.018, 0.012], [1, 0.8, 0.6, 0.4, 0.3], phases=rng.uniform(0, 6, 5), attack=0.0005) * 0.7
    dsp.place(y, _crack(rng, 0.008, 900, 15000) * 2.2, 0)
    body = ns(0.04)
    dsp.place(y, dsp.lp(rng.standard_normal(body) * np.exp(-np.arange(body) / ns(0.01)), 250) * 1.2, 0)
    y += _shard_field(rng, n, int(rng.integers(50, 110)), _r(rng, 0.6, 1.0), 1800, 9500, 0.006, 0.05, 0.005, 0.9)
    # a few big pieces bouncing
    for k in range(int(rng.integers(2, 5))):
        tt = _r(rng, 0.05, 0.5)
        fb = _r(rng, 900, 2400)
        dsp.place(y, dsp.modal(ns(0.2), fb * np.array([1, 2.4, 4.1]), [0.03, 0.02, 0.012], [0.6, 0.4, 0.2], attack=0.0005) * _r(rng, 0.2, 0.5), ns(tt))
    # skitter: grit of tiny fragments sliding
    y += _grains(rng, n, 120, 0.8, 3000, 10000, 0.15, t0=0.02, decay=0.3)
    return y


def impact_ceramic_knock(rng, i):
    """Ceramic bowl/cup knocked over without breaking: clatter and rocking settle."""
    n = ns(1.2)
    y = np.zeros(n)
    f1 = _r(rng, 900, 1700)
    times, amps = _bounces(rng, _r(rng, 0.06, 0.11), _r(rng, 0.45, 0.6), 8, 0.01)
    for tt, a in zip(times, amps):
        y += _modal_hit(rng, n, a, f1 * np.array([1, 2.32, 3.95, 5.7]), [0.12, 0.08, 0.05, 0.03], [1, 0.6, 0.4, 0.25], tt, 9000)
        dsp.place(y, _crack(rng, 0.002, 2000, 12000) * a * 0.4, ns(tt))
    # rocking settle (accelerating taps)
    t = times[-1] + 0.03
    dt = 0.06
    a = amps[-1] * 0.6
    while dt > 0.008 and t < 1.1:
        y += _modal_hit(rng, n, a, f1 * np.array([1, 2.32]), [0.05, 0.03], [1, 0.5], t, 9000)
        t += dt
        dt *= 0.8
        a *= 0.92
    return y


def impact_glass_clink(rng, i):
    n = ns(1.6)
    y = np.zeros(n)
    if i % 2 == 0:  # glass 'ting'
        f1 = _r(rng, 1900, 3200)
        fr = f1 * np.array([1, 2.32, 4.25, 6.3])
        dec = [0.7, 0.35, 0.18, 0.1]
        amps = [1, 0.5, 0.3, 0.15]
    else:  # bottle tunk + ring
        f1 = _r(rng, 700, 1300)
        fr = f1 * np.array([1, 2.05, 3.4, 4.9, 6.2])
        dec = [0.35, 0.22, 0.14, 0.09, 0.06]
        amps = [1, 0.6, 0.45, 0.3, 0.2]
    times, ampb = _bounces(rng, _r(rng, 0.05, 0.12), _r(rng, 0.35, 0.5), 3, 0.015)
    for tt, a in zip(times, ampb):
        y += _modal_hit(rng, n, a, fr, dec, amps, tt, 12000)
        dsp.place(y, _crack(rng, 0.0015, 3000, 15000) * a * 0.3, ns(tt))
    return y


def impact_glass_break(rng, i):
    n = ns(1.8)
    y = np.zeros(n)
    dsp.place(y, _crack(rng, 0.01, 1200, 16000) * 2.5, 0)
    f1 = _r(rng, 900, 1500)
    y += dsp.modal(n, f1 * np.array([1, 2.1, 3.5, 5.2]), [0.03, 0.02, 0.015, 0.01], [1, 0.7, 0.5, 0.3], attack=0.0003) * 0.5
    y += _shard_field(rng, n, int(rng.integers(90, 160)), _r(rng, 0.8, 1.3), 3000, 13000, 0.01, 0.12, 0.003, 1.0)
    y += _shard_field(rng, n, int(rng.integers(6, 14)), 1.2, 2500, 6000, 0.15, 0.4, 0.05, 0.25)  # long ringing pieces
    y += _grains(rng, n, 200, 1.2, 4000, 12000, 0.12, t0=0.01, decay=0.4)
    return y


def impact_plastic(rng, i):
    n = ns(1.4)
    y = np.zeros(n)
    b = _r(rng, 230, 460)
    fr = b * np.array([1, 2.1, 3.3, 4.9, 7.1])
    times, amps = _bounces(rng, _r(rng, 0.12, 0.22), _r(rng, 0.5, 0.65), 9, 0.012)
    for tt, a in zip(times, amps):
        y += _modal_hit(rng, n, a, fr, [0.05, 0.035, 0.022, 0.014, 0.008], [1, 0.8, 0.5, 0.3, 0.18], tt, 5000)
        dsp.place(y, _crack(rng, 0.002, 1500, 8000) * a * 0.35, ns(tt))
    # final roll rattle
    t_end = times[-1]
    y += _grains(rng, n, 25, 0.35, 1500, 5000, 0.12, t0=t_end, decay=0.15)
    return y


def impact_metal(rng, i):
    n = ns(2.4)
    y = np.zeros(n)
    f0 = _r(rng, 280, 650)
    ratios = np.sort(np.array([1, 1.47, 2.09, 2.56, 3.6, 4.1, 5.43, 6.8]) * rng.uniform(0.95, 1.05, 8))
    dec = np.array([1.1, 0.9, 0.7, 0.6, 0.45, 0.35, 0.25, 0.18]) * _r(rng, 0.6, 1.2)
    amps = np.array([0.8, 1, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2])
    times, ab = _bounces(rng, _r(rng, 0.1, 0.18), _r(rng, 0.4, 0.55), 5, 0.02)
    for tt, a in zip(times, ab):
        y += _modal_hit(rng, n, a, f0 * ratios, dec, amps, tt, 7000) * 0.8
        dsp.place(y, _crack(rng, 0.002, 2000, 12000) * a * 0.5, ns(tt))
    if i % 2 == 1:  # lid wobble: accelerating taps (Euler's disk)
        t = times[-1] + 0.05
        dt = 0.11
        a = 0.35
        while dt > 0.006 and t < 2.2:
            y += _modal_hit(rng, n, a, f0 * ratios[:4], dec[:4] * 0.5, amps[:4], t, 5000) * 0.6
            t += dt
            dt *= 0.86
            a *= 0.97
    return y


def metal_can_roll(rng, i):
    n = ns(2.5)
    y = np.zeros(n)
    f0 = _r(rng, 700, 1100)
    fr = f0 * np.array([1, 1.6, 2.4, 3.3, 4.6])
    t = 0.0
    rate = _r(rng, 10, 16)
    while t < 2.3:
        a = 0.3 * (1 - t / 2.4) * _r(rng, 0.5, 1.0)
        y += _modal_hit(rng, n, a, fr, [0.08, 0.06, 0.04, 0.03, 0.02], [1, 0.7, 0.5, 0.3, 0.2], t, 8000)
        t += 1 / rate * _r(rng, 0.6, 1.4)
        rate *= 0.985
    rumble = dsp.bp(rng.standard_normal(n), 150, 900) * dsp.env_points([(0, 0), (0.1, 1), (2.0, 0.6), (2.5, 0)], n) * 0.1
    return y + rumble


def impact_wood(rng, i):
    n = ns(0.9)
    y = np.zeros(n)
    b = _r(rng, 85, 160)
    fr = b * np.array([1, 2.6, 4.1, 6.3, 9.7])
    times, amps = _bounces(rng, _r(rng, 0.07, 0.13), _r(rng, 0.25, 0.4), 3, 0.02)
    for tt, a in zip(times, amps):
        y += _modal_hit(rng, n, a, fr, [0.03, 0.02, 0.014, 0.01, 0.006], [1, 0.8, 0.6, 0.35, 0.2], tt, 2500)
        dsp.place(y, _crack(rng, 0.003, 500, 5000) * a * 0.3, ns(tt))
    if i % 2:  # tips over: second knock
        tt = _r(rng, 0.25, 0.4)
        y += _modal_hit(rng, n, 0.6, fr * 1.1, [0.04, 0.03, 0.02, 0.012, 0.008], [1, 0.8, 0.5, 0.3, 0.2], tt, 2500)
    return y


def impact_soft(rng, i):
    n = ns(0.6)
    y = np.zeros(n)
    m = ns(0.06)
    y[:m] += dsp.lp(rng.standard_normal(m) * np.exp(-np.arange(m) / ns(0.015)), 400, 2) * 1.0
    y += _noise_burst(rng, n, _r(rng, 0.06, 0.12), 400, 3000, 0.0, 0.1) * 0.25
    y += _grains(rng, n, 20, 0.15, 1500, 6000, 0.1, decay=0.08)
    return y


def impact_cardboard(rng, i):
    n = ns(0.8)
    y = np.zeros(n)
    b = _r(rng, 120, 220)
    times, amps = _bounces(rng, _r(rng, 0.08, 0.12), 0.3, 2, 0.02)
    for tt, a in zip(times, amps):
        y += _modal_hit(rng, n, a, [b, b * 1.7, b * 2.9, b * 4.4], [0.03, 0.022, 0.015, 0.01], [1, 0.7, 0.4, 0.2], tt, 1500)
        y += _noise_burst(rng, n, 0.05, 600, 4000, tt, 0.1) * 0.25 * a
        y += _grains(rng, n, 15, 0.06, 2000, 7000, 0.1 * a, t0=tt)
    return y


def push_scrape(rng, i):
    """Object pushed along a ledge by a paw (stick-slip scrape)."""
    dur = _r(rng, 0.4, 0.75)
    n = ns(dur + 0.1)
    m = ns(dur)
    rate = _r(rng, 40, 120)
    times = np.cumsum(rng.exponential(1 / rate, int(dur * rate * 2)))
    times = times[times < dur]
    env = dsp.env_points([(0, 0), (0.05, 1), (dur * 0.8, 0.9), (dur, 0)], m)
    stick = dsp.frac_impulses(m, times, rng.uniform(0.3, 1, len(times)) * np.interp(times, np.arange(m) / SR, env))
    kind = i % 3
    if kind == 0:   # ceramic on concrete
        fr = [_r(rng, 900, 1300), 2400, 4100]
    elif kind == 1:  # glass bottle on tile
        fr = [_r(rng, 1500, 2200), 3600, 5800]
    else:  # plastic on wood
        fr = [_r(rng, 350, 500), 900, 1700]
    body = dsp.resonator_bank(stick, fr, [0.02, 0.015, 0.01], [1, 0.6, 0.35])
    noise = dsp.bp(rng.standard_normal(m), 1200, 8000) * env * 0.12
    y = np.zeros(n)
    y[:m] = body * 0.6 + noise + dsp.bp(stick, 2000, 9000) * 0.3
    return y


def _splash(rng, big=False, scale=1.0):
    n = ns(2.2 if big else 1.2)
    y = np.zeros(n)
    sl = ns(0.02 if big else 0.012)
    dsp.place(y, dsp.bp(rng.standard_normal(sl), 300, 6000) * np.exp(-np.arange(sl) / (sl / 3)) * (2.0 if big else 1.2), 0)
    if big:
        pl = ns(0.18)
        dsp.place(y, dsp.lp(rng.standard_normal(pl), 300, 2) * dsp.env_points([(0, 0), (0.02, 1), (0.18, 0)], pl) * 1.6, 0)
    # cavity collapse bubbles (Minnaert resonance, rising pitch)
    nb = int(rng.integers(8, 20) if big else rng.integers(3, 8))
    for k in range(nb):
        fb = _r(rng, 150, 700) if (big and k < 4) else _r(rng, 500, 2600)
        m = ns(_r(rng, 0.03, 0.09))
        tt = np.arange(m) / SR
        bub = np.sin(2 * np.pi * np.cumsum(fb * (1 + 3 * tt / (m / SR))) / SR) * np.exp(-tt / (m / SR / 3.5))
        dsp.place(y, bub * _r(rng, 0.2, 0.6), ns(_r(rng, 0.01, 0.25 if big else 0.12)))
    # spray
    sp = ns(0.8 if big else 0.35)
    spray = dsp.hp(rng.standard_normal(sp), 2000, 2) * dsp.env_points([(0, 0), (0.01, 1), (sp / SR, 0)], sp) ** 2
    dsp.place(y, spray * (0.5 if big else 0.3), ns(0.005))
    # droplets falling back
    nd = int(rng.integers(30, 70) if big else rng.integers(10, 25))
    for k in range(nd):
        fb = _r(rng, 1500, 6000)
        m = ns(0.015)
        tt = np.arange(m) / SR
        d = np.sin(2 * np.pi * np.cumsum(fb * (1 + 12 * tt)) / SR) * np.exp(-tt / 0.004)
        dsp.place(y, d * _r(rng, 0.03, 0.18), ns(_r(rng, 0.15, 1.4 if big else 0.6)))
    if big:  # sloshing
        sl2 = ns(1.6)
        slosh = dsp.lp(rng.standard_normal(sl2), 700, 2) * np.clip(0.5 + 0.6 * dsp.smooth_noise(sl2, 4, rng), 0, 1) \
            * dsp.env_points([(0, 0), (0.2, 1), (1.6, 0)], sl2) * 0.25
        dsp.place(y, slosh, ns(0.3))
    return y * scale


def splash_small(rng, i):
    return _splash(rng, False)


def splash_big(rng, i):
    return _splash(rng, True)


# --------------------------------------------------------------------------- registry
SOUNDS = []
for s in SURFACES:
    tgt = {"metal": -27, "water": -25, "fabric": -31, "grass": -27, "wood": -26, "plastic": -26, "roof_tile": -26}.get(s, -27)
    SOUNDS.append(Sound(f"step_{s}", _step(s), "sfx", "foley", 6, "SFX", tgt, unit_size=1.6, max_distance=18,
                        pitch_jitter=0.06, priority=2, desc=f"Cat paw step on {s} (walk/sneak/trot)"))
    SOUNDS.append(Sound(f"step_{s}_run", _step(s, True), "sfx", "foley", 4, "SFX", tgt + 3, unit_size=2.0, max_distance=22,
                        pitch_jitter=0.06, priority=3, desc=f"Cat paw step on {s} at a run"))
SOUNDS.append(Sound("step_wet", step_wet, "sfx", "foley", 6, "SFX", -28, unit_size=1.6, max_distance=15, priority=2,
                    desc="Wet layer added to steps while ground is wet"))
for fam in FAMILIES:
    SOUNDS.append(Sound(f"land_soft_{fam}", _landing(fam, False), "sfx", "foley", 3, "SFX", -24 if fam != "metal" else -21,
                        unit_size=2.5, max_distance=30, priority=5, desc=f"Soft landing on {fam}"))
    SOUNDS.append(Sound(f"land_hard_{fam}", _landing(fam, True), "sfx", "foley", 3, "SFX", -18 if fam != "metal" else -15,
                        unit_size=3.5, max_distance=45, priority=6, desc=f"Hard landing on {fam}"))

_IMP = dict(category="sfx", sub="impacts", bus="SFX", unit_size=5.0, max_distance=60, priority=6, pitch_jitter=0.06)
SOUNDS += [
    Sound("impact_ceramic", impact_ceramic, variants=4, target=-15, desc="Ceramic pot/bowl smashes", **_IMP),
    Sound("impact_ceramic_knock", impact_ceramic_knock, variants=3, target=-18, desc="Ceramic knocked over, not broken", **_IMP),
    Sound("impact_glass_clink", impact_glass_clink, variants=4, target=-19, desc="Glass/bottle clink and ring", **_IMP),
    Sound("impact_glass_break", impact_glass_break, variants=3, target=-15, desc="Glass shatters", **_IMP),
    Sound("impact_plastic", impact_plastic, variants=4, target=-18, desc="Hollow plastic bounces", **_IMP),
    Sound("impact_metal", impact_metal, variants=4, target=-16, desc="Metal clang (even: pot/can, odd: lid wobble)", **_IMP),
    Sound("metal_can_roll", metal_can_roll, variants=2, target=-21, mode="short", desc="Tin can rolling away", **_IMP),
    Sound("impact_wood", impact_wood, variants=4, target=-18, desc="Wooden object thud (odd: tips over)", **_IMP),
    Sound("impact_soft", impact_soft, variants=3, target=-21, desc="Fabric/bag/cushion thud", **_IMP),
    Sound("impact_cardboard", impact_cardboard, variants=3, target=-20, desc="Cardboard box thud", **_IMP),
    Sound("push_scrape", push_scrape, variants=3, target=-23, desc="Object pushed along a ledge by a paw", **_IMP),
    Sound("splash_small", splash_small, variants=3, target=-18, desc="Small object / paw into water", **_IMP),
    Sound("splash_big", splash_big, variants=2, target=-14, desc="Cat falls into water", **_IMP),
]
