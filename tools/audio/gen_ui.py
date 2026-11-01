"""UI sound set — one cohesive palette: bamboo/wood ticks, đàn tranh plucks and small bells tuned to
D Bắc (D E G A B), the key of the menu theme. Short, soft, never harsh."""
from __future__ import annotations

import numpy as np

import dsp
import sources as S
from dsp import SR, ns
from gen_music import BAC, Mode, tranh
from registry import Sound

M = Mode(74, BAC)  # D5
R = S.R


def _bell(f, amp=1.0, dec=0.8):
    ratios = np.array([1.0, 2.0, 3.01, 4.17, 5.43])
    m = ns(dec * 4)
    return dsp.modal(m, f * ratios, dec * np.array([1, 0.55, 0.35, 0.22, 0.14]), np.array([1, 0.35, 0.2, 0.1, 0.06]) * amp,
                     phases=np.zeros(5), attack=0.0006)


def _wood(rng, f=None, amp=1.0):
    f = f or R(rng, 1400, 1700)
    m = ns(0.12)
    s = dsp.modal(m, f * np.array([1, 2.4, 3.9]), [0.018, 0.01, 0.006], [1, 0.4, 0.2], attack=0.0002)
    return s * amp


def _pluck(rng, deg, dur=0.25, vel=0.8, ring=0.8, oct=0):
    return tranh(M.hz(deg + 5 * oct), dur, vel, rng, ring=ring, bright=1.1)


def _swish(rng, dur, rising=True, lo=500, hi=5000):
    n = ns(dur)
    t = np.linspace(0, 1, n)
    fc = lo * (hi / lo) ** (t if rising else 1 - t)

    def g(f, tt):
        idx = np.minimum((tt * SR).astype(int), n - 1)
        c = fc[idx][None, :]
        return 1 / (1 + ((f[:, None] - c) / (0.5 * c)) ** 2)
    y = dsp.stft_shape(rng.standard_normal(n), g, 512)
    env = np.sin(np.pi * t) ** 1.5
    return y / (np.abs(y).max() + 1e-9) * env


def _seq(parts, total):
    y = np.zeros(ns(total))
    for t, s, g in parts:
        dsp.place(y, s * g, ns(t))
    return y


def ui_hover(rng, i):
    return _seq([(0, _wood(rng, R(rng, 2300, 2600), 0.5), 1), (0, _pluck(rng, 4 + (i % 2), 0.05, 0.3, 0.12), 0.6)], 0.2)


def ui_click(rng, i):
    return _seq([(0, _wood(rng, R(rng, 1500, 1700)), 1), (0.004, _pluck(rng, 0, 0.08, 0.5, 0.25), 0.7)], 0.35)


def ui_confirm(rng, i):
    return _seq([(0, _pluck(rng, -2, 0.1, 0.8, 0.5), 1), (0.075, _pluck(rng, 0, 0.3, 0.9, 0.8), 1),
                 (0.075, _bell(M.hz(5), 0.15, 0.5), 1), (0, _wood(rng, 1600, 0.4), 1)], 1.2)


def ui_back(rng, i):
    return _seq([(0, _pluck(rng, 0, 0.1, 0.6, 0.4), 1), (0.08, _pluck(rng, -2, 0.25, 0.55, 0.5), 1),
                 (0, _wood(rng, 1300, 0.35), 1)], 0.9)


def ui_menu_open(rng, i):
    parts = [(0, _swish(rng, 0.28, True, 400, 4500), 0.25)]
    for k, d in enumerate([0, 2, 3, 5]):
        parts.append((0.06 + k * 0.045, _pluck(rng, d - 2, 0.2, 0.55 + 0.1 * k, 0.6), 1))
    return _seq(parts, 1.4)


def ui_menu_close(rng, i):
    parts = [(0, _swish(rng, 0.25, False, 400, 4000), 0.22)]
    for k, d in enumerate([5, 3, 2, 0]):
        parts.append((0.03 + k * 0.04, _pluck(rng, d - 2, 0.15, 0.6 - 0.07 * k, 0.45), 1))
    return _seq(parts, 1.1)


def ui_notify(rng, i):
    return _seq([(0, _bell(M.hz(6), 0.7, 0.7), 1), (0.11, _bell(M.hz(4), 0.6, 0.9), 1)], 2.2)


def ui_quest_start(rng, i):
    import gen_music as GM
    parts = [(0, GM.mo(rng, 0.6), 1), (0.05, _pluck(rng, 0, 0.18, 0.8, 0.8), 1), (0.2, _pluck(rng, 1, 0.18, 0.8, 0.8), 1),
             (0.35, _pluck(rng, 3, 0.6, 0.95, 1.4), 1), (0.35, _bell(M.hz(8), 0.12, 0.9), 1)]
    y = _seq(parts, 2.4)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.4, rng=rng, predelay=0.015), 0.25)


def ui_quest_complete(rng, i):
    import gen_music as GM
    parts = [(0, GM.mo(rng, 0.5), 1)]
    for k, d in enumerate([0, 1, 2, 3, 5]):
        parts.append((0.04 + k * 0.085, _pluck(rng, d, 0.2 if k < 4 else 0.9, 0.75 + 0.05 * k, 1.0 if k < 4 else 1.6), 1))
    parts += [(0.42, _bell(M.hz(5), 0.45, 1.2), 1), (0.42, _bell(M.hz(8), 0.25, 1.0), 1),
              (0.42, S.cymbal(rng) * 0.06, 1)]
    y = _seq(parts, 3.2)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.6, rng=rng, predelay=0.02), 0.28)


def ui_level_up(rng, i):
    import gen_music as GM
    parts = [(0, S.drum_hit(rng) * 0.5, 1)]
    for k in range(10):  # vuốt sweep across two octaves
        parts.append((k * 0.035, _pluck(rng, -3 + k, 0.15, 0.5 + 0.04 * k, 0.9), 1))
    for d, a in ((5, 0.6), (7, 0.35), (8, 0.3), (10, 0.25)):
        parts.append((0.4, _bell(M.hz(d), a, 1.4), 1))
    parts.append((0.4, S.cymbal(rng) * 0.08, 1))
    y = _seq(parts, 4.0)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.8, rng=rng, predelay=0.02), 0.3)


def ui_item_get(rng, i):
    return _seq([(0, _pluck(rng, 2, 0.08, 0.8, 0.5), 1), (0.07, _pluck(rng, 4, 0.3, 0.85, 0.8), 1),
                 (0.07, _bell(M.hz(9), 0.12, 0.5), 1)], 1.3)


def ui_map_open(rng, i):
    paper = S.bag_rustle(rng, 0.45) * 0.25 + _swish(rng, 0.45, True, 300, 3000) * 0.3
    paper = dsp.lp(paper, 6000)
    return _seq([(0, paper, 1), (0.25, _bell(M.hz(3), 0.35, 0.8), 1), (0.3, _pluck(rng, 0, 0.3, 0.5, 0.8), 1)], 1.8)


def ui_map_close(rng, i):
    paper = dsp.lp(S.bag_rustle(rng, 0.35) * 0.25 + _swish(rng, 0.35, False, 300, 2500) * 0.3, 5000)
    return _seq([(0, paper, 1), (0.2, _wood(rng, 1200, 0.5), 1)], 0.8)


def ui_error(rng, i):
    return _seq([(0, _wood(rng, 650, 0.9), 1), (0.11, _wood(rng, 560, 0.8), 1),
                 (0, tranh(M.hz(-5), 0.15, 0.4, rng, ring=0.3), 0.6)], 0.6)


def ui_slider(rng, i):
    return _wood(rng, R(rng, 2600, 3000), 0.6)[:ns(0.06)]


def ui_page(rng, i):
    return dsp.lp(_swish(rng, 0.22, True, 800, 6000) * 0.4 + dsp.pad_to(S.bag_rustle(rng, 0.2), ns(0.22)) * 0.15, 7000)


def ui_save(rng, i):
    return _seq([(0, _pluck(rng, 3, 0.12, 0.6, 0.6), 1), (0.09, _pluck(rng, 2, 0.12, 0.6, 0.6), 1),
                 (0.18, _pluck(rng, 0, 0.5, 0.7, 1.0), 1), (0.18, _bell(M.hz(5), 0.2, 0.9), 1)], 1.8)


def ui_discover(rng, i):
    import gen_music as GM
    parts = []
    for k in range(7):
        parts.append((k * 0.04, _pluck(rng, k, 0.12, 0.45, 0.9), 1))
    parts.append((0.3, GM.flute(M.hz(3), 0.25, 0.7, rng), 1))
    parts.append((0.55, GM.flute(M.hz(5), 0.8, 0.75, rng), 1))
    y = _seq(parts, 2.4)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.6, rng=rng), 0.3)


def ui_collectible(rng, i):
    parts = []
    for k, d in enumerate([5, 6, 7, 8, 10]):
        parts.append((k * 0.06, _bell(M.hz(d), 0.4, 0.7), 1))
    parts.append((0.0, S.bag_rustle(rng, 0.2) * 0.05, 1))
    y = _seq(parts, 2.6)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.5, rng=rng), 0.3)


def ui_skill_unlock(rng, i):
    parts = [(0, _swish(rng, 0.35, True, 300, 6000), 0.2)]
    for k, d in enumerate([0, 3, 5, 8]):
        parts.append((0.15 + k * 0.05, _pluck(rng, d, 0.3, 0.7, 1.0), 1))
    parts.append((0.35, _bell(M.hz(10), 0.35, 1.0), 1))
    y = _seq(parts, 2.6)
    return dsp.reverb(dsp.stereo(y), dsp.make_ir(1.5, rng=rng), 0.25)


def ui_pause(rng, i):
    n = ns(0.5)
    t = np.arange(n) / SR
    whoomp = np.sin(2 * np.pi * np.cumsum(140 - 60 * t / t[-1]) / SR) * np.exp(-t / 0.12) * 0.6
    return whoomp + dsp.lp(_swish(rng, 0.5, False, 200, 1500), 1500) * 0.3


def ui_unpause(rng, i):
    n = ns(0.45)
    t = np.arange(n) / SR
    up = np.sin(2 * np.pi * np.cumsum(80 + 70 * t / t[-1]) / SR) * np.sin(np.pi * t / t[-1]) * 0.5
    return up + dsp.lp(_swish(rng, 0.45, True, 200, 2000), 2000) * 0.3


def ui_cat_sense_on(rng, i):
    """Cat-sense: whiskers tingle — shimmering filtered sweep with a soft heartbeat pulse."""
    n = ns(1.2)
    out = np.zeros((n, 2))
    sh = _swish(rng, 1.0, True, 1500, 9000)
    out += dsp.pan(dsp.pad_to(sh, n) * 0.35, -0.4) + dsp.pan(dsp.pad_to(_swish(rng, 1.0, True, 1800, 10000), n) * 0.35, 0.4)
    for k, tt in enumerate((0.0, 0.32)):
        m = ns(0.25)
        x = np.arange(m) / SR
        hb = np.sin(2 * np.pi * (60 - 15 * x / x[-1]) * x) * np.exp(-x / 0.06) * (0.7 if k == 0 else 0.5)
        dsp.place(out, dsp.stereo(hb), ns(tt))
    for d in (8, 10, 12):
        dsp.place(out, dsp.pan(_bell(M.hz(d), 0.06, 0.6), R(rng, -0.6, 0.6)), ns(R(rng, 0.3, 0.7)))
    return out


def ui_cat_sense_off(rng, i):
    n = ns(0.7)
    out = np.zeros((n, 2))
    out += dsp.pan(dsp.pad_to(_swish(rng, 0.6, False, 1200, 8000), n) * 0.35, -0.3)
    out += dsp.pan(dsp.pad_to(_swish(rng, 0.6, False, 1500, 9000), n) * 0.35, 0.3)
    return out


def ui_dialogue_next(rng, i):
    return _seq([(0, _wood(rng, R(rng, 1900, 2200), 0.6), 1), (0, _pluck(rng, 2 + i % 3, 0.04, 0.3, 0.1), 0.5)], 0.18)


U = dict(category="ui", bus="UI", pitch_jitter=0.0, priority=10, unit_size=1.0)
SOUNDS = [
    Sound("ui_hover", ui_hover, variants=2, target=-30, desc="Focus/hover tick", **U),
    Sound("ui_click", ui_click, variants=2, target=-25, desc="Button press", **U),
    Sound("ui_confirm", ui_confirm, target=-22, desc="Confirm/accept (rising pluck)", **U),
    Sound("ui_back", ui_back, target=-24, desc="Back/cancel (falling pluck)", **U),
    Sound("ui_menu_open", ui_menu_open, target=-23, desc="Menu opens (swish + rising arpeggio)", **U),
    Sound("ui_menu_close", ui_menu_close, target=-24, desc="Menu closes", **U),
    Sound("ui_notify", ui_notify, target=-21, desc="Toast notification (two bells)", **U),
    Sound("ui_quest_start", ui_quest_start, target=-18, desc="Quest started", **U),
    Sound("ui_quest_complete", ui_quest_complete, target=-16, desc="Quest/objective complete", **U),
    Sound("ui_level_up", ui_level_up, target=-15, desc="Level up (sweep + bell chord)", **U),
    Sound("ui_item_get", ui_item_get, target=-20, desc="Item obtained", **U),
    Sound("ui_map_open", ui_map_open, target=-22, desc="Map unfolds", **U),
    Sound("ui_map_close", ui_map_close, target=-24, desc="Map folds", **U),
    Sound("ui_error", ui_error, target=-24, desc="Not allowed / error (soft double knock)", **U),
    Sound("ui_slider", ui_slider, variants=2, target=-30, desc="Slider step tick", **U),
    Sound("ui_page", ui_page, variants=2, target=-27, desc="Journal page turn", **U),
    Sound("ui_save", ui_save, target=-22, desc="Game saved", **U),
    Sound("ui_discover", ui_discover, target=-19, desc="New location discovered (short)", **U),
    Sound("ui_collectible", ui_collectible, target=-19, desc="Collectible / memory found", **U),
    Sound("ui_skill_unlock", ui_skill_unlock, target=-18, desc="Skill unlocked", **U),
    Sound("ui_pause", ui_pause, target=-24, desc="Pause (world muffles)", **U),
    Sound("ui_unpause", ui_unpause, target=-25, desc="Unpause", **U),
    Sound("ui_cat_sense_on", ui_cat_sense_on, target=-22, desc="Cat-sense activated", **U),
    Sound("ui_cat_sense_off", ui_cat_sense_off, target=-25, desc="Cat-sense ends", **U),
    Sound("ui_dialogue_next", ui_dialogue_next, variants=3, target=-29, desc="Dialogue line advance blip", **U),
]
