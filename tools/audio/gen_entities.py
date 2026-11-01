"""World entities: scooters, horns, bicycles, dogs, birds, geckos, frogs, mice, human non-verbal,
roller shutters, doors, AC units, neon signs, drips, temple bell & wood block."""
from __future__ import annotations

import numpy as np

import dsp
import sources as S
from dsp import SR, ns
from registry import Sound

R = S.R


# --------------------------------------------------------------------------- vehicles
def scooter_idle_loop(rng, i):
    L = 4.0
    n = ns(L + 0.5)
    rpm = 1450 * (1 + 0.03 * dsp.smooth_noise(n, 1.2, rng))
    y = S.engine(rng, rpm, np.full(n, 0.15), "scooter")
    return dsp.loop_crossfade(y, ns(L), ns(0.5))


def scooter_ride_loop(rng, i):
    L = 4.0
    n = ns(L + 0.5)
    rpm = S.rpm_cruise(rng, n, 5200, 0.04, 0.8)
    y = S.engine(rng, rpm, np.full(n, 0.6), "scooter") + S.tire_noise(rng, n, 9.0)
    return dsp.loop_crossfade(y, ns(L), ns(0.5))


def motorbike_ride_loop(rng, i):
    L = 4.0
    n = ns(L + 0.5)
    rpm = S.rpm_cruise(rng, n, 6000, 0.05, 0.9)
    y = S.engine(rng, rpm, np.full(n, 0.7), "manual") + S.tire_noise(rng, n, 10.0)
    return dsp.loop_crossfade(y, ns(L), ns(0.5))


def scooter_pass(rng, i):
    return S.motorbike_pass(rng, 6.0, lateral=R(rng, 2.0, 4.0), binaural=False, kind="scooter" if i % 2 == 0 else "manual")


def scooter_start(rng, i):
    """Electric starter whirr, engine catches with a small rev, settles to idle."""
    n = ns(3.0)
    y = np.zeros(n)
    st = ns(0.45)
    tt = np.arange(st) / SR
    sm = np.sin(2 * np.pi * np.cumsum(180 + 120 * tt / tt[-1]) / SR) * 0.3 + dsp.bp(rng.standard_normal(st), 800, 4000) * 0.1
    sm *= (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 9 * tt)))
    y[:st] += sm * 0.6
    m = n - ns(0.35)
    t = np.arange(m) / SR
    rpm = 1450 + 3200 * np.exp(-((t - 0.35) / 0.18) ** 2) * (t > 0.1) + 400 * np.exp(-t / 0.5)
    e = S.engine(rng, rpm, np.clip(0.2 + 0.6 * np.exp(-((t - 0.3) / 0.2) ** 2), 0, 1), "scooter")
    dsp.place(y, e * dsp.env_points([(0, 0), (0.05, 1), (m / SR, 1)], m), ns(0.35))
    return dsp.fades(y, 0.002, 0.3)


def horn_motorbike(rng, i):
    return S.horn_beep(rng, double=i % 2 == 1, long=i == 3)


def horn_car(rng, i):
    return S.horn_beep(rng, double=i == 1, car=True, long=i == 0)


def bicycle_bell(rng, i):
    """Thumb-lever bell: rapid double/triple strikes on a small dome bell."""
    f0 = R(rng, 2100, 2700)
    ratios = np.array([1, 1.52, 2.13, 2.88, 3.95])
    strikes = int(rng.integers(2, 4)) if i != 2 else 6
    n = ns(1.8)
    y = np.zeros(n)
    t = 0.0
    for k in range(strikes):
        a = R(rng, 0.7, 1.0)
        s = dsp.modal(ns(1.5), f0 * ratios * R(rng, 0.999, 1.001), [0.6, 0.4, 0.25, 0.15, 0.1], [1, 0.6, 0.5, 0.3, 0.2],
                      phases=rng.uniform(0, 6, 5), attack=0.0002)
        dsp.place(y, s * a, ns(t))
        dsp.place(y, dsp.hp(dsp.click(ns(0.002), rng), 3000) * 0.3 * a, ns(t))
        t += R(rng, 0.055, 0.075) if (k % 2 == 0) else R(rng, 0.12, 0.2)
    return y


def bicycle_pass(rng, i):
    """Freewheel ticking + tyre hiss + chain, passing by (mono)."""
    dur = 4.0
    n = ns(dur + 0.4)
    tick_rate = R(rng, 25, 40)
    tt = dsp.pulse_times(np.full(n, tick_rate), 0.02, rng)
    ticks = dsp.bp(dsp.frac_impulses(n, tt, rng.uniform(0.6, 1, len(tt))), 2500, 9000) * 0.3
    coast = dsp.env_points([(0, 0), (1.2, 0), (1.3, 1), (2.6, 1), (2.7, 0), (dur, 0)], n) if i % 2 else np.ones(n)
    tyre = dsp.bp(dsp.pink(n, rng), 400, 5000) * 0.08
    chain = dsp.bp(rng.standard_normal(n), 1500, 6000) * 0.02 * (1 - coast)
    src = ticks * coast + tyre + chain
    sp = R(rng, 4, 6)

    def traj(te):
        return sp * (te - dur / 2), np.full_like(te, R(rng, 1.5, 3)), np.full_like(te, 0.5)
    out = dsp.moving_source(src, traj, ref_dist=1.5, binaural=False)
    return dsp.fades(out[:ns(dur)], 0.3, 0.5)


# --------------------------------------------------------------------------- animals
def dog_bark(rng, i):
    return dsp.hp(S.dog_bark(rng, size=R(rng, 0.95, 1.1)), 50, 2)


def dog_bark_series(rng, i):
    cnt = int(rng.integers(3, 6))
    n = ns(cnt * 0.45 + 0.5)
    y = np.zeros(n)
    t = 0.0
    size = R(rng, 0.95, 1.1)
    for k in range(cnt):
        dsp.place(y, S.dog_bark(rng, size) * R(rng, 0.75, 1.0), ns(t))
        t += R(rng, 0.25, 0.45)
    return y


def dog_growl(rng, i):
    return S.dog_growl(rng)


def dog_pant_loop(rng, i):
    return S.dog_pant(rng, 4.0)


def dog_whine(rng, i):
    return S.dog_whine(rng)


def pigeon_coo(rng, i):
    return S.pigeon_coo(rng)


def pigeon_takeoff(rng, i):
    return S.wing_flaps(rng, takeoff=True)


def pigeon_land(rng, i):
    y = S.wing_flaps(rng, beats=int(rng.integers(3, 6)), rate=R(rng, 6, 8), takeoff=False)
    n = len(y)
    # tiny feet/settle
    dsp.place(y, dsp.bp(dsp.click(ns(0.01), rng), 1000, 6000) * 0.4, n - ns(0.5))
    return y


def flock_takeoff(rng, i):
    """Whole pigeon flock bursts up: many overlapping wing claps (stereo)."""
    n = ns(3.5)
    out = np.zeros((n, 2))
    for k in range(int(rng.integers(12, 22))):
        f = S.wing_flaps(rng, beats=int(rng.integers(6, 14)), takeoff=True)
        dsp.place(out, dsp.pan(f * R(rng, 0.3, 1.0), R(rng, -0.8, 0.8)), ns(rng.gamma(2, 0.08)))
    return out


def crow_caw(rng, i):
    return S.crow_caw(rng, 1)


def crow_caw_series(rng, i):
    return S.crow_caw(rng, int(rng.integers(2, 5)))


def crow_rattle(rng, i):
    return S.crow_rattle(rng)


def sparrow_chirp(rng, i):
    return S.sparrow_chirp(rng)


def bulbul_song(rng, i):
    return S.bulbul_song(rng)


def gecko_chirp(rng, i):
    return S.gecko_house(rng)


def tokay_call(rng, i):
    return S.tokay_call(rng)


def frog_croak(rng, i):
    return S.frog_croak(rng)


def mouse_squeak(rng, i):
    return S.mouse_squeak(rng)


def rooster(rng, i):
    return S.rooster(rng)


# --------------------------------------------------------------------------- humans (non-verbal)
def human_laugh(rng, i):
    return S.laugh(rng, female=i % 2 == 0, kind="laugh" if i < 2 else "chuckle")


def human_call(rng, i):
    return S.call_oi(rng, female=i % 2 == 0)


def human_shoo(rng, i):
    return S.shoo(rng, i)


def human_hum(rng, i):
    return S.hum(rng, female=i % 2 == 0)


def human_surprise(rng, i):
    """'Ơ!' surprised exclamation (something got knocked over)."""
    female = i % 2 == 0
    d = R(rng, 0.2, 0.32)
    n = ns(d)
    f0b = R(rng, 300, 380) if female else R(rng, 170, 210)
    from voice import additive_voice, f0_track, formant_tracks
    f0 = f0_track([(0, f0b * 1.15), (0.3, f0b * 1.3), (1, f0b * 0.95)], n, rng, 0, 0, 0.01)
    fs = 1.0 if female else 0.86
    fm = formant_tracks([(520 * fs, 110), (1350 * fs, 140), (2700 * fs, 220), (3900 * fs, 300)], n)
    amp = dsp.env_points([(0, 0), (0.015, 1), (d * 0.6, 0.8), (d, 0)], n)
    return additive_voice(f0, amp, fm, rng, tilt_db_oct=-6, breath=0.2, env_model="bumps")


def human_aww(rng, i):
    """Soft delighted 'ôi~' when seeing/petting the cat."""
    female = i % 2 == 0
    d = R(rng, 0.6, 0.9)
    n = ns(d)
    f0b = R(rng, 260, 320) if female else R(rng, 140, 170)
    from voice import additive_voice, f0_track, formant_tracks
    f0 = f0_track([(0, f0b * 1.2), (0.3, f0b * 1.35), (1, f0b * 0.85)], n, rng, 5, 0.01, 0.008)
    fs = 1.0 if female else 0.86
    fm = formant_tracks([([(0, 450 * fs), (0.6, 450 * fs), (1, 330 * fs)], 110), ([(0, 850 * fs), (0.6, 900 * fs), (1, 2500 * fs)], 140),
                         (2700 * fs, 220), (3800 * fs, 300)], n)
    amp = dsp.env_points([(0, 0), (0.06, 0.9), (d * 0.6, 0.8), (d, 0)], n)
    return additive_voice(f0, amp, fm, rng, tilt_db_oct=-8, breath=0.3, env_model="bumps")


def human_clap_shoo(rng, i):
    n = ns(1.2)
    y = np.zeros(n)
    t = 0.0
    for k in range(int(rng.integers(2, 4))):
        m = ns(0.05)
        c = dsp.bp(rng.standard_normal(m) * np.exp(-np.arange(m) / ns(0.006)), 600, 7000)
        c = dsp.peak(c, R(rng, 900, 1500), 2, 8)
        dsp.place(y, c, ns(t))
        t += R(rng, 0.18, 0.28)
    dsp.place(y, S.shoo(rng, 0) * 0.7, ns(t + 0.05))
    return y


# --------------------------------------------------------------------------- mechanical / places
def shutter(rng, i, opening=True):
    """Roller shutter (cửa cuốn): slat clatter at a rate following the drum speed, rumble, end bang."""
    dur = R(rng, 2.4, 3.4)
    n = ns(dur + 1.0)
    y = np.zeros(n)
    m = ns(dur)
    t = np.arange(m) / SR
    speed = dsp.env_points([(0, 0.2), (0.25, 1), (dur - 0.3, 0.95), (dur, 0.3)], m)
    rate = 14 * speed * R(rng, 0.85, 1.15)
    tt = dsp.pulse_times(rate, 0.08, rng)
    amps = rng.uniform(0.3, 1.0, len(tt))
    imp = dsp.frac_impulses(m, tt, amps)
    modes = [R(rng, 250, 350), R(rng, 700, 900), R(rng, 1400, 1800), R(rng, 2400, 3000), R(rng, 3800, 4500)]
    clat = dsp.resonator_bank(imp, modes, [0.06, 0.04, 0.03, 0.02, 0.012], [1, 0.8, 0.6, 0.4, 0.25])
    rumble = dsp.bp(rng.standard_normal(m), 60, 500) * speed * 0.6
    squeal = np.sin(2 * np.pi * np.cumsum(R(rng, 1800, 2600) * (1 + 0.03 * dsp.smooth_noise(m, 4, rng))) / SR) * 0.03 * speed
    y[:m] = clat * 0.5 + rumble + squeal
    if not opening:  # closing ends with a slam on the ground
        bang = dsp.modal(ns(0.9), np.array(modes) * 0.8, [0.3, 0.25, 0.2, 0.15, 0.1], [1, 0.8, 0.6, 0.4, 0.3], attack=0.0005)
        bang += dsp.lp(rng.standard_normal(ns(0.9)) * np.exp(-np.arange(ns(0.9)) / ns(0.05)), 400) * 0.8
        dsp.place(y, bang * 1.8, m - ns(0.05))
    else:  # opening ends with the lock stop clunk
        dsp.place(y, dsp.modal(ns(0.5), np.array(modes[:3]), [0.12, 0.08, 0.05], [1, 0.6, 0.3]) * 0.9, m - ns(0.05))
    return dsp.fades(y, 0.01, 0.1)


def shutter_open(rng, i):
    return shutter(rng, i, True)


def shutter_close(rng, i):
    return shutter(rng, i, False)


def door_creak(rng, i):
    """Old wooden door: stick-slip hinge creak (pitch follows angular speed) + latch."""
    dur = R(rng, 1.0, 1.8)
    n = ns(dur + 0.4)
    m = ns(dur)
    speed = np.clip(dsp.env_points([(0, 0), (dur * 0.2, 1), (dur * 0.8, 0.7), (dur, 0)], m) * (1 + 0.3 * dsp.smooth_noise(m, 3, rng)), 0, None)
    rate = 150 + 450 * speed
    tt = dsp.pulse_times(rate, 0.03, rng)
    imp = dsp.frac_impulses(m, tt, rng.uniform(0.5, 1, len(tt)) * np.interp(tt, np.arange(m) / SR, speed))
    y = np.zeros(n)
    y[:m] = dsp.resonator_bank(imp, [R(rng, 600, 900), R(rng, 1500, 2100), R(rng, 2800, 3600)], [0.01, 0.007, 0.005], [1, 0.7, 0.4])
    dsp.place(y, dsp.modal(ns(0.3), [R(rng, 1800, 2600), 4100], [0.03, 0.02], [1, 0.5]) * 0.6, m)
    return y


def ac_unit_loop(rng, i):
    return S.ac_hum(ns(6.0), rng)


def neon_buzz_loop(rng, i):
    return S.neon_buzz(ns(5.0), rng)


def water_drip(rng, i):
    m = ns(0.25)
    tt = np.arange(m) / SR
    fb = R(rng, 700, 1800)
    s = np.sin(2 * np.pi * np.cumsum(fb * (1 + 8 * tt)) / SR) * np.exp(-tt / 0.02)
    dsp.place(s, dsp.bp(dsp.click(ns(0.004), rng), 1000, 6000) * 0.6, 0)
    return s


def temple_bell(rng, i):
    """Bronze temple bell (chuông) struck by a wooden log: long inharmonic ring with beating partials."""
    f0 = R(rng, 110, 150)
    ratios = np.array([0.5, 1.0, 1.19, 1.5, 2.0, 2.52, 2.66, 3.01, 4.1, 5.2])
    dec = np.array([9, 7, 6, 4, 3.2, 2.4, 2.2, 1.6, 1.0, 0.6])
    amps = np.array([0.5, 1, 0.5, 0.6, 0.45, 0.35, 0.3, 0.2, 0.12, 0.08])
    n = ns(10.0)
    y = dsp.modal(n, f0 * ratios, dec, amps, phases=rng.uniform(0, 6, 10), attack=0.002)
    # beating doublets (slightly mistuned pairs)
    y += dsp.modal(n, f0 * ratios[1:5] * 1.003, dec[1:5], amps[1:5] * 0.5, phases=rng.uniform(0, 6, 4), attack=0.002)
    thud = dsp.lp(rng.standard_normal(ns(0.08)) * np.exp(-np.arange(ns(0.08)) / ns(0.015)), 500) * 0.5
    dsp.place(y, thud, 0)
    out = dsp.stereo(y)
    ir = dsp.make_ir(3.0, rng=rng, predelay=0.03, brightness=0.4)
    return dsp.reverb(out, ir, 0.25)


def temple_woodblock(rng, i):
    """Mõ (temple wood block): hollow resonant knocks, a few in a row."""
    cnt = int(rng.integers(1, 4))
    n = ns(cnt * 0.6 + 0.5)
    y = np.zeros(n)
    f = R(rng, 420, 620)
    for k in range(cnt):
        s = dsp.modal(ns(0.4), f * np.array([1, 2.45, 3.9, 5.6]), [0.09, 0.04, 0.025, 0.015], [1, 0.4, 0.25, 0.1], attack=0.0003)
        dsp.place(s, dsp.bp(dsp.click(ns(0.003), rng), 1500, 7000) * 0.3, 0)
        dsp.place(y, s, ns(k * R(rng, 0.45, 0.6)))
    return y


# --------------------------------------------------------------------------- registry
E = dict(category="sfx", sub="entities", bus="SFX")
SOUNDS = [
    Sound("scooter_idle_loop", scooter_idle_loop, variants=2, target=-20, mode="integrated", loop=True, unit_size=4, max_distance=60, pitch_jitter=0, desc="Scooter idling (attach with play_loop; pitch_scale ~ rpm)", **E),
    Sound("scooter_ride_loop", scooter_ride_loop, variants=2, target=-18, mode="integrated", loop=True, unit_size=6, max_distance=90, pitch_jitter=0, desc="Scooter cruising loop (CVT); use with doppler", **E),
    Sound("motorbike_ride_loop", motorbike_ride_loop, variants=2, target=-17, mode="integrated", loop=True, unit_size=6, max_distance=100, pitch_jitter=0, desc="Manual-gear motorbike cruising loop", **E),
    Sound("scooter_pass", scooter_pass, variants=4, target=-16, unit_size=8, max_distance=120, desc="Mono pass-by with baked Doppler", **E),
    Sound("scooter_start", scooter_start, variants=2, target=-18, unit_size=5, max_distance=60, desc="Electric start, catch, idle", **E),
    Sound("horn_motorbike", horn_motorbike, variants=4, target=-13, unit_size=12, max_distance=200, priority=6, desc="Motorbike horn: short, double, long", **E),
    Sound("horn_car", horn_car, variants=2, target=-12, unit_size=14, max_distance=220, priority=6, desc="Car dual-tone horn", **E),
    Sound("bicycle_bell", bicycle_bell, variants=3, target=-16, unit_size=6, max_distance=60, desc="Thumb-lever bicycle bell", **E),
    Sound("bicycle_pass", bicycle_pass, variants=2, target=-22, unit_size=3, max_distance=30, desc="Bicycle freewheel ticking pass-by", **E),
    Sound("dog_bark", dog_bark, variants=6, target=-12, unit_size=8, max_distance=120, priority=7, desc="Single bark (Vện)", **E),
    Sound("dog_bark_series", dog_bark_series, variants=3, target=-12, unit_size=8, max_distance=120, priority=7, desc="3-5 barks", **E),
    Sound("dog_growl", dog_growl, variants=3, target=-17, mode="short", unit_size=4, max_distance=35, priority=7, desc="Low warning growl", **E),
    Sound("dog_pant_loop", dog_pant_loop, variants=1, target=-24, mode="integrated", loop=True, unit_size=2, max_distance=20, pitch_jitter=0, desc="Panting loop (after chase)", **E),
    Sound("dog_whine", dog_whine, variants=2, target=-20, unit_size=4, max_distance=40, desc="Whine", **E),
    Sound("pigeon_coo", pigeon_coo, variants=4, target=-22, unit_size=3, max_distance=30, desc="Rock dove coo", **E),
    Sound("pigeon_takeoff", pigeon_takeoff, variants=3, target=-17, unit_size=4, max_distance=40, desc="Wing claps on take-off", **E),
    Sound("pigeon_land", pigeon_land, variants=2, target=-21, unit_size=3, max_distance=30, desc="Flutter and land", **E),
    Sound("flock_takeoff", flock_takeoff, variants=2, target=-14, unit_size=8, max_distance=80, desc="Whole flock bursts up (stereo)", **E),
    Sound("crow_caw", crow_caw, variants=4, target=-14, unit_size=10, max_distance=150, desc="Single caw (Lão Quạ)", **E),
    Sound("crow_caw_series", crow_caw_series, variants=3, target=-14, unit_size=10, max_distance=150, desc="2-4 caws", **E),
    Sound("crow_rattle", crow_rattle, variants=2, target=-18, unit_size=5, max_distance=50, desc="Corvid rattle/chuckle (Lão Quạ talking)", **E),
    Sound("sparrow_chirp", sparrow_chirp, variants=5, target=-21, unit_size=4, max_distance=50, desc="Tree sparrow chirps", **E),
    Sound("bulbul_song", bulbul_song, variants=4, target=-19, unit_size=6, max_distance=70, desc="Red-whiskered bulbul (chào mào) phrase", **E),
    Sound("rooster", rooster, variants=2, target=-16, unit_size=12, max_distance=200, desc="Rooster crow (dawn)", **E),
    Sound("gecko_chirp", gecko_chirp, variants=3, target=-20, unit_size=4, max_distance=40, desc="House gecko (thạch sùng) chirps", **E),
    Sound("tokay_call", tokay_call, variants=2, target=-15, mode="short", unit_size=10, max_distance=120, desc="Tokay gecko 'tắc kè' call", **E),
    Sound("frog_croak", frog_croak, variants=3, target=-20, unit_size=5, max_distance=60, desc="Frog croaks (lake, night)", **E),
    Sound("mouse_squeak", mouse_squeak, variants=3, target=-24, unit_size=1.5, max_distance=12, desc="Mouse squeaks", **E),
    Sound("human_laugh", human_laugh, variants=4, target=-18, unit_size=5, max_distance=50, desc="Laugh/chuckle (even=female)", **E),
    Sound("human_call", human_call, variants=4, target=-14, unit_size=8, max_distance=80, desc="Non-verbal 'ơi!' call (even=female)", **E),
    Sound("human_shoo", human_shoo, variants=3, target=-14, unit_size=5, max_distance=40, priority=7, desc="'Suỵt!/Xùy!' shoo hiss", **E),
    Sound("human_clap_shoo", human_clap_shoo, variants=2, target=-14, unit_size=6, max_distance=50, priority=7, desc="Hand claps + shoo", **E),
    Sound("human_hum", human_hum, variants=2, target=-22, unit_size=3, max_distance=25, desc="Vendor humming a little tune", **E),
    Sound("human_surprise", human_surprise, variants=4, target=-16, unit_size=5, max_distance=50, desc="'Ơ!' surprised (object knocked over)", **E),
    Sound("human_aww", human_aww, variants=2, target=-20, unit_size=3, max_distance=25, desc="Soft delighted 'ôi~' (petting the cat)", **E),
    Sound("shutter_open", shutter_open, variants=2, target=-15, mode="short", unit_size=8, max_distance=80, desc="Roller shutter going up", **E),
    Sound("shutter_close", shutter_close, variants=2, target=-14, mode="short", unit_size=8, max_distance=80, desc="Roller shutter coming down + slam", **E),
    Sound("door_creak", door_creak, variants=2, target=-19, unit_size=4, max_distance=30, desc="Wooden door hinge creak + latch", **E),
    Sound("ac_unit_loop", ac_unit_loop, variants=2, target=-26, mode="integrated", loop=True, unit_size=2, max_distance=18, pitch_jitter=0, desc="AC condenser hum loop (emitter on AC units)", **E),
    Sound("neon_buzz_loop", neon_buzz_loop, variants=1, target=-30, mode="integrated", loop=True, unit_size=1.5, max_distance=10, pitch_jitter=0, desc="Neon/fluorescent sign buzz loop", **E),
    Sound("water_drip", water_drip, variants=4, target=-24, unit_size=2, max_distance=15, desc="Single drip into a puddle", **E),
    Sound("temple_bell", temple_bell, variants=2, target=-16, mode="short", unit_size=20, max_distance=300, desc="Bronze temple bell (stereo, long)", **E),
    Sound("temple_woodblock", temple_woodblock, variants=3, target=-18, unit_size=6, max_distance=60, desc="Mõ wood block knocks", **E),
]
