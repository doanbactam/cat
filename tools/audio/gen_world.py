"""Ambience beds (stereo, seamless 60-120 s loops) and weather (rain loops, rain on tin, storm wind,
thunder and gust one-shots). Beds are sums of periodic noise layers and wrapped events, finished with a
circular-convolution reverb, so the loop seam is perfect by construction."""
from __future__ import annotations

import numpy as np

import dsp
import sources as S
from dsp import SR, ns
from registry import Sound

R = S.R


# --------------------------------------------------------------------------- helpers
def emit(bed, snd, t, dist, az, rng=None, air=True):
    """Place a mono (or stereo) event at distance/azimuth with spreading loss + air absorption (wrapping)."""
    g = min(1.0, 3.0 / max(dist, 0.5))
    x = snd
    if air and dist > 6:
        x = dsp.lp(x, max(1200.0, 16000.0 * np.exp(-dist / 60.0)), 2)
    if x.ndim == 1:
        x = dsp.spatialize(x, az)
    dsp.place_wrap(bed, x * g, ns(t))


def scatter(rng, L, count):
    return np.sort(rng.uniform(0, L, count))


def city_ir(rt60, rng, predelay=0.02, bright=0.5, er_spread=0.05):
    return dsp.make_ir(rt60, rng=rng, predelay=predelay, brightness=bright, er_spread=er_spread)


def traffic_far(n, rng, level=1.0, passes=12, dist=(40, 140)):
    L = n / SR
    bed = S.stereo_bed(n, rng, S.shape_band(55, 1400, -3.0, 2), 0.6, 0.15, 0.25) * 0.16 * level
    hum = S.stereo_bed(n, rng, S.shape_band(90, 600, -2, 2), 0.4, 0.3, 0.3) * 0.05 * level
    bed += hum
    for t in scatter(rng, L, passes):
        p = S.motorbike_pass(rng, 9.0, lateral=R(rng, *dist), binaural=True)
        dsp.place_wrap(bed, p * level * 1.5, ns(t))
    return bed


def horns(bed, rng, L, count, dist=(8, 60)):
    for t in scatter(rng, L, count):
        h = S.horn_beep(rng, double=rng.random() < 0.5, long=rng.random() < 0.1, car=rng.random() < 0.15)
        emit(bed, h * 2.0, t, R(rng, *dist), R(rng, -1.5, 1.5))


def birds(bed, rng, L, sparrows=10, bulbuls=4, dist=(5, 30), koels=0, pigeons=0):
    for t in scatter(rng, L, sparrows):
        emit(bed, S.sparrow_chirp(rng), t, R(rng, *dist), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, bulbuls):
        emit(bed, S.bulbul_song(rng), t, R(rng, *dist) * 1.5, R(rng, -1.5, 1.5))
    for t in scatter(rng, L, koels):
        emit(bed, S.koel_call(rng), t, R(rng, 40, 90), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, pigeons):
        emit(bed, S.pigeon_coo(rng) * 0.3, t, R(rng, 8, 25), R(rng, -1.5, 1.5))


def crickets(n, rng, count=30, level=1.0):
    """Many crickets, each with its own carrier/rate/position; periodic."""
    L = n / SR
    bed = np.zeros((n, 2))
    for k in range(count):
        fc = R(rng, 3900, 5600)
        rate = R(rng, 1.4, 3.2)
        dist = R(rng, 3, 30)
        az = R(rng, -1.5, 1.5)
        ch = S.cricket_chirp(rng, fc)
        st = dsp.spatialize(ch, az) * min(1, 3 / dist) * R(rng, 0.5, 1.0)
        t = R(rng, 0, 1 / rate)
        # crickets chirp in bouts with pauses
        on = rng.random() < 0.7
        while t < L:
            if on:
                dsp.place_wrap(bed, st, ns(t))
                t += 1 / rate * R(rng, 0.95, 1.05)
                if rng.random() < 0.02:
                    on = False
            else:
                t += R(rng, 1.0, 5.0)
                on = True
    # far chorus / katydid trill shimmer
    tr = S.stereo_bed(n, rng, lambda f: 1 / (1 + ((f - 7800) / 900) ** 2), 0.7)
    t = np.arange(n) / SR
    am = 0.5 + 0.5 * np.sin(2 * np.pi * (round(48 * L) / L) * t)
    bed += tr * am[:, None] * 0.05
    return bed * level


# --------------------------------------------------------------------------- beds
def amb_street_day(rng, i):
    L = 90.0
    n = ns(L)
    bed = traffic_far(n, rng, 1.0, 16)
    # mid/near flow
    t = 0.0
    while t < L:
        p = S.motorbike_pass(rng, 8.0, lateral=R(rng, 4, 16), horn=rng.random() < 0.15)
        dsp.place_wrap(bed, p * R(rng, 0.6, 1.0), ns(t))
        t += rng.exponential(3.2) + 0.4
    horns(bed, rng, L, 16)
    cr = S.crowd(rng, L, speakers=7, dist=(8, 35), callers=2)
    bed += cr * 0.7
    birds(bed, rng, L, sparrows=14, bulbuls=5, pigeons=3)
    for t in scatter(rng, L, 2):
        emit(bed, S.dog_bark(rng) * 0.8, t, R(rng, 40, 90), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 2):
        emit(bed, S.laugh(rng, rng.random() < 0.6), t, R(rng, 10, 25), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(1.3, rng), wet=0.22)


def amb_street_night(rng, i):
    L = 80.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.45, 7, (60, 200))
    t = 0.0
    while t < L:
        p = S.motorbike_pass(rng, 8.0, lateral=R(rng, 8, 30))
        dsp.place_wrap(bed, p * R(rng, 0.4, 0.8), ns(t))
        t += rng.exponential(11.0) + 2.0
    horns(bed, rng, L, 3, (40, 120))
    bed += crickets(n, rng, 26, 0.32)
    for t in scatter(rng, L, 4):
        emit(bed, S.gecko_house(rng), t, R(rng, 3, 12), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 1):
        emit(bed, S.tokay_call(rng), t, R(rng, 25, 50), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 3):
        emit(bed, S.dog_bark(rng) * 0.7, t, R(rng, 60, 140), R(rng, -1.5, 1.5))
    tv = S.tv_murmur(n, rng)
    emit(bed, tv * 0.25, 0.0, 14, R(rng, -1, 1))
    for t in scatter(rng, L, 1):
        emit(bed, S.koel_call(rng), t, R(rng, 60, 120), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(1.4, rng, bright=0.4), wet=0.25)


def amb_market(rng, i):
    L = 90.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.6, 8)
    cr = S.crowd(rng, L, speakers=16, dist=(3, 22), callers=4)
    bed += cr * 1.0
    # slow scooters threading through the market
    t = R(rng, 0, 6)
    while t < L:
        p = S.motorbike_pass(rng, 10.0, speed=R(rng, 2.5, 4.5), lateral=R(rng, 2.5, 7), horn=rng.random() < 0.3)
        dsp.place_wrap(bed, p * 0.6, ns(t))
        t += rng.exponential(9) + 3
    import gen_foley as F
    events = [(F.impact_plastic, 7, (4, 15)), (F.impact_metal, 3, (6, 18)), (F.impact_wood, 5, (4, 15)),
              (F.impact_cardboard, 4, (4, 12)), (F.splash_small, 5, (5, 15))]
    for fn, cnt, dr in events:
        for t in scatter(rng, L, cnt):
            emit(bed, fn(rng, int(rng.integers(0, 4))) * 0.5, t, R(rng, *dr), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 6):
        emit(bed, S.chopping(rng) * 0.7, t, R(rng, 4, 14), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 10):
        emit(bed, S.bag_rustle(rng) * 0.35, t, R(rng, 2, 8), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 5):
        emit(bed, S.laugh(rng, rng.random() < 0.6), t, R(rng, 5, 15), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 3):
        emit(bed, S.dish_clink(rng) * 0.5, t, R(rng, 4, 12), R(rng, -1.5, 1.5))
    horns(bed, rng, L, 6, (15, 50))
    birds(bed, rng, L, sparrows=6, bulbuls=0, pigeons=2)
    return dsp.reverb_loop(bed, city_ir(1.6, rng, bright=0.45), wet=0.28)


def amb_lake(rng, i):
    L = 75.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.35, 8, (80, 220))
    horns(bed, rng, L, 4, (90, 200))
    bed += S.water_lapping(n, rng) * 0.9
    gust = np.clip(0.5 + 0.5 * dsp.smooth_noise_periodic(n, 0.1, rng), 0, 1)
    bed += S.leaves_bed(n, rng, 0.8, gust) * 0.12
    bed += S.wind_bed(n, rng, 0.25, 0.1, 0.0) * 0.18
    birds(bed, rng, L, sparrows=12, bulbuls=8, dist=(6, 40), pigeons=4)
    import gen_foley as F
    for t in scatter(rng, L, 2):  # fish jumping
        emit(bed, F.splash_small(rng, 0) * 0.4, t, R(rng, 15, 40), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 1):
        emit(bed, S.wing_flaps(rng), t, R(rng, 8, 20), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(0.9, rng, bright=0.6), wet=0.12)


def amb_temple(rng, i):
    L = 75.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.18, 5, (100, 250))
    bed += S.wind_bed(n, rng, 0.25, 0.12, 0.15) * 0.22
    gust = np.clip(0.4 + 0.6 * dsp.smooth_noise_periodic(n, 0.12, rng), 0, 1)
    bed += S.leaves_bed(n, rng, 0.6, gust) * 0.1
    bed += S.wind_chimes_bed(n, rng, activity=0.45) * 0.35
    birds(bed, rng, L, sparrows=6, bulbuls=4, dist=(10, 40), pigeons=4)
    import gen_entities as E
    for t in scatter(rng, L, 1):
        emit(bed, E.temple_woodblock(rng, 0) * 0.5, t, 25, R(rng, -1, 1))
    return dsp.reverb_loop(bed, city_ir(2.0, rng, predelay=0.035, bright=0.45), wet=0.25)


def amb_alley(rng, i):
    L = 70.0
    n = ns(L)
    bed = np.zeros((n, 2))
    far = traffic_far(n, rng, 0.35, 8, (25, 80))
    bed += S.circ_filter(far, S.shape_band(20, 1800, 0, 2))  # heard around corners: darker
    tv = S.tv_murmur(n, rng)
    emit(bed, tv * 0.35, 0.0, 4.5, -0.9)
    # kitchen through a window on the other side
    kit = np.zeros(n)
    t = R(rng, 0, 5)
    while t < L:
        d = R(rng, 4, 11)
        sz = S.sizzle(ns(d), rng) * dsp.env_points([(0, 0), (0.6, 1), (d - 1.0, 1), (d, 0)], ns(d))
        dsp.place_wrap(kit, sz * 0.5, ns(t))
        for k in range(int(rng.integers(1, 4))):
            dsp.place_wrap(kit, S.wok_scrape(rng), ns(t + R(rng, 0.5, d - 0.5)))
        t += d + R(rng, 4, 12)
    for t in scatter(rng, L, 3):
        dsp.place_wrap(kit, S.chopping(rng) * 0.8, ns(t))
    for t in scatter(rng, L, 4):
        dsp.place_wrap(kit, S.dish_clink(rng) * 0.6, ns(t))
    for t in scatter(rng, L, 2):
        dsp.place_wrap(kit, S.tap_water(rng) * 0.4, ns(t))
    emit(bed, kit, 0.0, 5.0, 0.9)
    ac = S.ac_hum(n, rng)
    emit(bed, ac * 0.12, 0.0, 6.0, 0.3, air=False)
    # dripping pipe (steady period)
    per = R(rng, 1.2, 2.2)
    import gen_entities as E
    t = 0.0
    while t < L:
        emit(bed, E.water_drip(rng, 0) * 0.3, t, 2.5, -0.4)
        t += per * R(rng, 0.97, 1.03)
    for t in scatter(rng, L, 3):
        emit(bed, S.gecko_house(rng), t, R(rng, 3, 8), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 1):  # a bike squeezes through the alley
        p = S.motorbike_pass(rng, 9.0, speed=R(rng, 2.5, 4), lateral=1.2, kind="manual")
        dsp.place_wrap(bed, p * 0.5, ns(t))
    for t in scatter(rng, L, 2):
        emit(bed, S.laugh(rng, rng.random() < 0.5) * 0.6, t, 9, R(rng, -1.5, 1.5))
    ir = dsp.make_ir(0.9, rng=rng, predelay=0.006, brightness=0.55, er=24, er_spread=0.03)
    return dsp.reverb_loop(bed, ir, wet=0.38)


def amb_rooftop(rng, i):
    L = 80.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.55, 14, (60, 250))
    horns(bed, rng, L, 8, (70, 220))
    gust = np.clip(0.55 + 0.45 * dsp.smooth_noise_periodic(n, 0.13, rng), 0.05, 1.2)
    bed += S.wind_bed(n, rng, 0.6, 0.13, 0.5) * 0.45
    bed += S.stereo_bed(n, rng, S.shape_band(2500, 9000, 0, 2), 0.8) * (gust ** 2)[:, None] * 0.02
    # laundry flapping at gust peaks
    t = 0.0
    while t < L:
        g = gust[min(n - 1, ns(t))]
        if g > 0.8:
            m = ns(R(rng, 0.4, 1.0))
            fl = dsp.bp(rng.standard_normal(m), 300, 4000) * np.abs(np.sin(2 * np.pi * R(rng, 6, 11) * np.arange(m) / SR)) ** 3
            emit(bed, fl * dsp.env_points([(0, 0), (0.05, 1), (m / SR, 0)], m) * 0.5, t, 4, R(rng, -1.2, 1.2))
        t += R(rng, 0.6, 1.4)
    birds(bed, rng, L, sparrows=4, bulbuls=1, dist=(15, 40), pigeons=4)
    for t in scatter(rng, L, 2):
        emit(bed, S.wing_flaps(rng), t, R(rng, 8, 25), R(rng, -1.5, 1.5))
    ac = S.ac_hum(n, rng)
    emit(bed, ac * 0.15, 0.0, 9.0, -0.7, air=False)
    # antenna/tin ticks on gusts
    for t in scatter(rng, L, 10):
        tick = dsp.modal(ns(0.2), [R(rng, 1800, 3000), R(rng, 4200, 5600)], [0.03, 0.02], [1, 0.5])
        emit(bed, tick * 0.3, t, R(rng, 3, 8), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(0.8, rng, bright=0.5), wet=0.1)


def amb_night_insects(rng, i):
    L = 60.0
    n = ns(L)
    bed = crickets(n, rng, 34, 1.0)
    for t in scatter(rng, L, 3):
        emit(bed, S.gecko_house(rng), t, R(rng, 4, 12), R(rng, -1.5, 1.5))
    for t in scatter(rng, L, 4):
        emit(bed, S.frog_croak(rng) * 0.6, t, R(rng, 15, 40), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(1.0, rng, bright=0.4), wet=0.15)


def amb_dawn_chorus(rng, i):
    L = 60.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.2, 3, (80, 200))
    birds(bed, rng, L, sparrows=34, bulbuls=14, dist=(4, 35), koels=2, pigeons=5)
    for t in scatter(rng, L, 2):
        emit(bed, S.rooster(rng), t, R(rng, 70, 150), R(rng, -1.5, 1.5))
    return dsp.reverb_loop(bed, city_ir(1.0, rng, bright=0.5), wet=0.15)


def amb_festival(rng, i):
    """Mid-Autumn festival night: happy crowd with children, lion-dance drums & cymbals in the distance."""
    L = 96.0
    n = ns(L)
    bed = traffic_far(n, rng, 0.3, 4, (60, 150))
    bed += S.crowd(rng, L, speakers=14, dist=(3, 25), callers=2, child_ratio=0.35) * 1.0
    for t in scatter(rng, L, 9):
        emit(bed, S.laugh(rng, rng.random() < 0.7), t, R(rng, 4, 15), R(rng, -1.5, 1.5))
    # lion-dance troupe ~40 m away: drum pattern at 138 bpm, cymbals on accents
    drums = np.zeros(n)
    beat = 60 / 138
    t = 0.0
    bar = 0
    pattern = [1, 0, 1, 1, 0, 1, 0, 2]  # 1 = drum, 2 = rim
    while t < L:
        for k, p in enumerate(pattern):
            tt = t + k * beat / 2
            if p == 1:
                dsp.place_wrap(drums, S.drum_hit(rng) * R(rng, 0.7, 1.0), ns(tt))
            elif p == 2:
                dsp.place_wrap(drums, S.drum_hit(rng, rim=True) * 0.5, ns(tt))
            if k in (0, 4):
                dsp.place_wrap(drums, S.cymbal(rng, choke=k == 4) * 0.35, ns(tt))
        t += 4 * beat
        bar += 1
    emit(bed, drums * 1.4, 0.0, 35, 0.6)
    # toy lantern tunes (tinny electronic melodies) from children's star lanterns
    for t0 in scatter(rng, L, 4):
        mel = np.zeros(ns(4.0))
        base = R(rng, 700, 1000)
        for k, st in enumerate(rng.choice([0, 2, 4, 7, 9, 12], 10)):
            m = ns(0.18)
            tone = np.sign(np.sin(2 * np.pi * base * 2 ** (st / 12) * np.arange(m) / SR)) * np.exp(-np.arange(m) / ns(0.12))
            dsp.place(mel, dsp.lp(tone, 4000) * 0.3, ns(k * 0.25))
        emit(bed, mel, t0, R(rng, 3, 8), R(rng, -1.5, 1.5))
    horns(bed, rng, L, 3, (50, 120))
    return dsp.reverb_loop(bed, city_ir(1.5, rng, bright=0.45), wet=0.25)


# --------------------------------------------------------------------------- weather
def rain_light_loop(rng, i):
    n = ns(45.0)
    return dsp.reverb_loop(S.rain_bed(n, rng, 0.3), city_ir(0.9, rng, bright=0.4), wet=0.15)


def rain_heavy_loop(rng, i):
    n = ns(45.0)
    return dsp.reverb_loop(S.rain_bed(n, rng, 1.0), city_ir(1.1, rng, bright=0.4), wet=0.2)


def rain_tin_loop(rng, i):
    n = ns(40.0)
    return dsp.reverb_loop(S.rain_on_tin(n, rng, 0.7) + S.rain_bed(n, rng, 0.5) * 0.4, city_ir(0.6, rng, bright=0.5), wet=0.12)


def wind_storm_loop(rng, i):
    n = ns(60.0)
    w = S.wind_bed(n, rng, 0.95, 0.25, 0.7)
    gust = np.clip(0.5 + 0.5 * dsp.smooth_noise_periodic(n, 0.25, rng), 0, 1)
    return w + S.leaves_bed(n, rng, 1.2, gust) * 0.2


def thunder_near(rng, i):
    return S.thunder(rng, True)


def thunder_far(rng, i):
    return S.thunder(rng, False)


def wind_gust(rng, i):
    return S.gust(rng)


# --------------------------------------------------------------------------- registry
A = dict(category="ambience", bus="Ambience", loop=True, mode="integrated", quality=4, pitch_jitter=0.0, priority=10)
W = dict(category="ambience", sub="weather", bus="Ambience", pitch_jitter=0.0, priority=9)
SOUNDS = [
    Sound("amb_street_day", amb_street_day, target=-25, desc="Day street: motorbike flow, horns, vendor murmur, birds", **A),
    Sound("amb_street_night", amb_street_night, target=-29, desc="Night street: crickets, geckos, distant traffic, TV", **A),
    Sound("amb_market", amb_market, target=-24, desc="Market bustle: dense crowd, vendors' calls, clatter, slow scooters", **A),
    Sound("amb_lake", amb_lake, target=-28, desc="Lake: water lapping, birds, leaves, distant city", **A),
    Sound("amb_temple", amb_temple, target=-30, desc="Temple courtyard: wind chimes, quiet wind, birds", **A),
    Sound("amb_alley", amb_alley, target=-28, desc="Alley: echoey, TV murmur, kitchen sounds, drips, AC hum", **A),
    Sound("amb_rooftop", amb_rooftop, target=-28, desc="Rooftop: wind, distant city, laundry flaps, pigeons", **A),
    Sound("amb_night_insects", amb_night_insects, target=-31, desc="Overlay: crickets, geckos, frogs (night, non-street areas)", **A),
    Sound("amb_dawn_chorus", amb_dawn_chorus, target=-28, desc="Overlay: dawn birds + distant roosters", **A),
    Sound("amb_festival", amb_festival, target=-24, desc="Mid-Autumn festival night: crowd, children, lion-dance drums", **A),
    Sound("rain_light_loop", rain_light_loop, target=-28, mode="integrated", loop=True, quality=4, desc="Light rain loop", **W),
    Sound("rain_heavy_loop", rain_heavy_loop, target=-22, mode="integrated", loop=True, quality=4, desc="Heavy rain loop", **W),
    Sound("rain_tin_loop", rain_tin_loop, target=-24, mode="integrated", loop=True, quality=4, desc="Rain drumming on corrugated iron (sheltered)", **W),
    Sound("wind_storm_loop", wind_storm_loop, target=-26, mode="integrated", loop=True, quality=4, desc="Storm wind loop", **W),
    Sound("thunder_near", thunder_near, variants=3, target=-14, mode="short", desc="Close thunder: crack + rumble (stereo)", **W),
    Sound("thunder_far", thunder_far, variants=3, target=-21, mode="short", desc="Distant rolling thunder (stereo)", **W),
    Sound("wind_gust", wind_gust, variants=4, target=-23, mode="short", desc="Wind gust one-shot (stereo)", **W),
]
