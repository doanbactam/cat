"""Original music for Mèo Cam: 5 seamless loops + stingers.

Instruments (all synthesised here):
* đàn tranh  — 16-string zither: additive pluck with stretched partials, pluck-position comb, frequency-
               dependent decay, 'nhấn' press-bends and 'rung' vibrato, 'vuốt' glissando sweeps.
* đàn bầu    — monochord played on harmonics: near-sine tone, rod slides (portamento) and wide vibrato.
* sáo trúc   — bamboo flute: harmonic tone, breath noise, onset chiff, pitch scoop, delayed vibrato, grace notes.
* pad        — warm detuned 'bamboo-flute-like' pad on quartal pentatonic chords.
* bass       — soft plucked bass; percussion: lo-fi kit, song loan clapper, mõ, lion-dance trống, chũm chọe.
Modes: Bắc (0 2 5 7 9) and Nam/oán (0 3.3 5 7 9.8 — microtonal 'non/già' inflections).
Loops: everything is rendered with a ringing tail which is wrapped onto the start; lo-fi colouring
(tape wow, saturation, crackle, filtering, glue compression) is applied circularly, so the seam is perfect.
"""
from __future__ import annotations

import numpy as np

import dsp
import sources as S
from dsp import SR, TAU, ns
from registry import Sound

BAC = [0.0, 2.0, 5.0, 7.0, 9.0]
NAM = [0.0, 3.3, 5.0, 7.0, 9.8]


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


class Mode:
    def __init__(self, root_midi, steps):
        self.root = root_midi
        self.steps = steps

    def semis(self, deg):
        o, i = divmod(int(deg), 5)
        return self.steps[i] + 12 * o

    def hz(self, deg, cents=0.0):
        return midi_hz(self.root + self.semis(deg) + cents / 100.0)

    def chord(self, deg, octave=-1):
        """Quartal pentatonic chord on a degree: degree, +2, +3 (and the octave)."""
        base = deg + 5 * octave
        return [self.hz(base), self.hz(base + 2), self.hz(base + 3), self.hz(base + 5)]


# =========================================================================== instruments
def tranh(f0, dur, vel, rng, bend=None, vib=0.0, ring=None, bright=1.0):
    """Đàn tranh pluck. bend: list of (t_s, cents) points for a press-bend; vib: vibrato depth in cents."""
    ring = ring if ring is not None else float(np.clip(1.4 + 1.6 * (260.0 / f0), 1.2, 3.5))
    total = dur + ring
    n = ns(total)
    t = np.arange(n) / SR
    cents = np.zeros(n)
    if bend:
        cents += dsp.env_points(bend, n)
    if vib > 0:
        on = np.clip((t - 0.25) / 0.35, 0, 1) * np.clip((dur + 0.6 - t) / 0.6, 0, 1)
        cents += vib * on * np.sin(TAU * 5.6 * t + rng.uniform(0, 6))
    fr = f0 * 2 ** (cents / 1200)
    ph = TAU * np.cumsum(fr) / SR
    p = rng.uniform(0.12, 0.2)
    B = 0.00012
    tau1 = float(np.clip(2.2 * (300.0 / f0) ** 0.5, 0.6, 3.5))
    y = np.zeros(n)
    K = int(min(28, 15000 / f0))
    for k in range(1, K + 1):
        stretch = k * np.sqrt(1 + B * k * k)
        a = abs(np.sin(np.pi * k * p)) / k ** (1.0 - 0.25 * (bright - 1))
        tk = tau1 / (1 + (k * f0 / 2600.0) ** 1.3)
        m = min(n, ns(tk * 7))
        y[:m] += a * np.exp(-t[:m] / tk) * np.sin(stretch * ph[:m] + rng.uniform(0, 6))
    # finger-pick (móng) transient
    pk = ns(0.004)
    y[:pk] += dsp.bp(rng.standard_normal(pk), 1500, 9000) * np.exp(-np.arange(pk) / ns(0.001)) * 0.25 * bright
    # the string is damped (hand/next stroke) over the second half of the ring time: never cut off ringing
    d0 = dur + ring * 0.35
    damp = np.where(t < d0, 1.0, 0.5 + 0.5 * np.cos(np.pi * np.clip((t - d0) / max(total - d0, 1e-3), 0, 1)))
    return y * damp * vel * 0.35


def bau(fcurve, vel, rng, vib=40.0, release=0.4):
    """Đàn bầu: fcurve is per-sample frequency (slides included). Plucked harmonic, long sustain."""
    n = len(fcurve) + ns(release)
    f = np.concatenate([fcurve, np.full(n - len(fcurve), fcurve[-1])])
    t = np.arange(n) / SR
    on = np.clip((t - 0.18) / 0.4, 0, 1)
    cents = vib * on * np.sin(TAU * 5.8 * t + rng.uniform(0, 6)) * (1 + 0.2 * dsp.smooth_noise(n, 2, rng))
    fr = f * 2 ** (cents / 1200)
    ph = TAU * np.cumsum(fr) / SR
    env = np.exp(-t / 2.8) * np.clip(t / 0.006, 0, 1)
    rel = np.clip((n / SR - t) / release, 0, 1)
    y = (np.sin(ph) + 0.16 * np.sin(2 * ph + 0.4) + 0.06 * np.sin(3 * ph + 1.0) + 0.025 * np.sin(4 * ph)) * env * rel
    pk = ns(0.006)
    y[:pk] += dsp.bp(rng.standard_normal(pk), 1000, 5000) * np.exp(-np.arange(pk) / ns(0.0015)) * 0.08
    return dsp.soft_clip(y * vel * 1.2, 1.2) * 0.5


def flute(f0, dur, vel, rng, scoop=True, vib=True, grace=None, breath=0.07):
    """Sáo trúc. grace: semitone offset of a grace note (láy) before the main note."""
    rel = 0.12
    n = ns(dur + rel)
    t = np.arange(n) / SR
    cents = np.zeros(n)
    if scoop:
        cents += -45 * np.exp(-t / 0.035)
    if grace is not None:
        g = ns(0.06)
        cents[:g] += grace * 100
    if vib and dur > 0.45:
        on = np.clip((t - 0.28) / 0.3, 0, 1)
        cents += 18 * on * np.sin(TAU * 5.3 * t + rng.uniform(0, 6))
    cents += 4 * dsp.smooth_noise(n, 6, rng)
    fr = f0 * 2 ** (cents / 1200)
    ph = TAU * np.cumsum(fr) / SR
    env = dsp.env_points([(0, 0), (0.06, 1.0), (max(0.07, dur * 0.6), 0.92), (dur, 0.85), (dur + rel, 0)], n)
    env *= 1 + 0.04 * dsp.smooth_noise(n, 3, rng)
    br = 0.6 + 0.4 * vel
    harms = [(1, 1.0), (2, 0.32 * br), (3, 0.16 * br), (4, 0.06 * br), (5, 0.04 * br), (6, 0.015)]
    y = sum(a * np.sin(h * ph + 0.3 * h) for h, a in harms)
    nz = dsp.bp(rng.standard_normal(n), max(800, f0 * 1.5), min(9000, f0 * 8)) * breath
    chiff = ns(0.04)
    nz[:chiff] += dsp.bp(rng.standard_normal(chiff), 1500, 6000) * np.hanning(chiff) * 0.25
    return (y + nz) * env * vel * 0.3


def pad(freqs, dur, vel, rng, attack=1.2, release=1.8, bright=0.5):
    n = ns(dur + release)
    t = np.arange(n) / SR
    env = dsp.env_points([(0, 0), (attack, 1), (dur, 0.9), (dur + release, 0)], n)
    out = np.zeros((n, 2))
    for f in freqs:
        for det, pn in ((-6, -0.6), (0, 0), (6, 0.6)):
            ff = f * 2 ** ((det + 2 * dsp.smooth_noise(n, 0.3, rng)) / 1200)
            ph = TAU * np.cumsum(ff) / SR + rng.uniform(0, 6)
            v = np.sin(ph) + 0.25 * bright * np.sin(2 * ph) + 0.1 * bright * np.sin(3 * ph) + 0.04 * bright * np.sin(4 * ph)
            out += dsp.pan(v, pn * 0.7)
    out *= env[:, None] * vel * 0.06
    air = S.stereo_bed(n, rng, S.shape_band(800, 5000, -3, 2), 0.7) * env[:, None] * 0.004 * vel
    return out + air


def bass(f0, dur, vel, rng):
    n = ns(dur + 0.6)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for k in range(1, 9):
        tk = 0.9 / (1 + 0.5 * k)
        y += np.exp(-t / tk) * np.sin(TAU * f0 * k * t + 0.2 * k) / k ** 1.4
    y *= dsp.env_points([(0, 0), (0.008, 1), (dur, 0.85), (dur + 0.12, 0), (dur + 0.6, 0)], n)
    th = ns(0.03)
    y[:th] += dsp.lp(rng.standard_normal(th), 800) * np.exp(-np.arange(th) / ns(0.006)) * 0.3
    return y * vel * 0.5


def kick(rng, vel=1.0):
    n = ns(0.45)
    t = np.arange(n) / SR
    f = 48 + 75 * np.exp(-t / 0.04)
    y = np.sin(TAU * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    y[:ns(0.004)] += dsp.bp(rng.standard_normal(ns(0.004)), 1000, 5000) * 0.3
    return y * vel


def brush(rng, vel=1.0):
    n = ns(0.25)
    t = np.arange(n) / SR
    y = dsp.bp(rng.standard_normal(n), 900, 7000) * np.exp(-t / 0.07) * 0.6
    y += np.sin(TAU * 185 * t) * np.exp(-t / 0.05) * 0.35
    return y * vel


def shaker(rng, vel=1.0):
    n = ns(0.08)
    y = dsp.bp(rng.standard_normal(n), 4000, 11000) * dsp.env_points([(0, 0), (0.012, 1), (0.08, 0)], n)
    return y * vel * 0.4


def rim(rng, vel=1.0):
    n = ns(0.1)
    return dsp.modal(n, [R(rng, 1600, 1800), 3400, 5200], [0.012, 0.008, 0.005], [1, 0.5, 0.3], attack=0.0002) * vel


def clapper(rng, vel=1.0):
    """Song loan (cải lương foot clapper): bright wooden click."""
    n = ns(0.12)
    return dsp.modal(n, [R(rng, 1900, 2300), 4300, 6200], [0.018, 0.01, 0.006], [1, 0.4, 0.2], attack=0.0002) * vel


def mo(rng, vel=1.0):
    n = ns(0.5)
    f = R(rng, 480, 520)
    return dsp.modal(n, f * np.array([1, 2.45, 3.9]), [0.09, 0.04, 0.025], [1, 0.35, 0.2], attack=0.0003) * vel


def R(rng, a, b):
    return float(rng.uniform(a, b))


# =========================================================================== sequencer
class Track:
    def __init__(self, bpm, bars, mode: Mode, rng, beats_per_bar=4, swing=0.5, tail=7.0):
        self.bpm, self.bars, self.mode, self.rng = bpm, bars, mode, rng
        self.bpb = beats_per_bar
        self.beat = 60.0 / bpm
        self.L = bars * beats_per_bar * self.beat
        self.n = ns(self.L + tail)
        self.swing = swing
        self.stems = {}

    def stem(self, name, stereo=False):
        if name not in self.stems:
            self.stems[name] = np.zeros((self.n, 2)) if stereo else np.zeros(self.n)
        return self.stems[name]

    def t_of(self, bar, beat):
        b = beat
        frac = b - np.floor(b)
        if self.swing != 0.5 and abs(frac - 0.5) < 1e-6:
            b = np.floor(b) + self.swing
        return (bar * self.bpb + b) * self.beat

    def add(self, name, snd, bar, beat, human=0.008, stereo=False):
        t = self.t_of(bar, beat) + (self.rng.normal(0, human) if human else 0)
        dsp.place(self.stem(name, stereo or snd.ndim == 2), snd, max(0, ns(t)))

    # ---- melodic helpers
    def melody(self, inst, phrase, bar0, octave=0, vel=0.8, name=None, ornament=0.35, vib=None):
        """phrase: list of (beats, degree|None). Instrument-specific ornamentation."""
        name = name or inst
        beat = 0.0
        prev = None
        notes = [(d, g) for d, g in phrase]
        for idx, (d, deg) in enumerate(notes):
            if deg is not None:
                bar = bar0 + int(beat // self.bpb)
                bt = beat % self.bpb
                dur = d * self.beat
                g = deg + 5 * octave
                f = self.mode.hz(g)
                accent = 1.0 if bt == 0 else (0.9 if bt == 2 else 0.8)
                v = vel * accent * self.rng.uniform(0.9, 1.05)
                r = self.rng.random()
                if inst == "tranh":
                    bend = None
                    if prev is not None and g > prev and r < ornament and dur >= 0.45:
                        # nhấn: pluck the lower string pitch and press up to the target
                        lower = self.mode.hz(g - 1)
                        c0 = 1200 * np.log2(lower / f)
                        bend = [(0, c0), (0.09, c0), (0.22, 0), (dur + 3, 0)]
                    elif r > 1 - ornament * 0.5 and dur >= 0.6:
                        # nhấn luyến: press up a step then release back
                        bend = [(0, 0), (dur * 0.35, 0), (dur * 0.55, 180), (dur * 0.8, 0), (dur + 3, 0)]
                    vv = (vib if vib is not None else (28 if dur >= 0.7 else 0))
                    snd = tranh(f, dur, v, self.rng, bend, vv)
                elif inst == "flute":
                    grace = None
                    if r < ornament * 0.6 and dur >= 0.4:
                        grace = self.mode.semis(g + 1) - self.mode.semis(g)
                    snd = flute(f, dur * 0.97, v, self.rng, scoop=r < 0.6, vib=True, grace=grace)
                elif inst == "bau":
                    n = ns(dur)
                    if prev is not None:
                        fp = self.mode.hz(prev)
                        sl = min(0.18, dur * 0.4)
                        curve = dsp.env_points([(0, fp), (sl, f), (dur, f)], n)
                    else:
                        curve = dsp.env_points([(0, f * 0.94), (0.12, f), (dur, f)], n)
                    if r < ornament and dur > 0.8:  # expressive dip-and-return near the end
                        curve *= 2 ** (dsp.env_points([(0, 0), (dur * 0.65, 0), (dur * 0.8, -110), (dur, 0)], n) / 1200)
                    snd = bau(curve, v, self.rng, vib if vib is not None else 38)
                elif inst == "bass":
                    snd = bass(f, dur * 0.9, v, self.rng)
                else:
                    raise ValueError(inst)
                self.add(name, snd, bar, bt)
                prev = g
            beat += d

    def arpeggio(self, chords, bar0, pattern, octave=0, vel=0.45, name="tranh_arp", sub=0.5, vib=0):
        """chords: list of chord degrees per bar; pattern: indices into the chord tone ladder (0..7)."""
        for b, cd in enumerate(chords):
            ladder = [cd + 5 * octave + o for o in (0, 2, 3, 5, 7, 8, 10, 12)]
            for k, p in enumerate(pattern):
                if p is None:
                    continue
                beat = k * sub
                if beat >= self.bpb:
                    break
                f = self.mode.hz(ladder[p])
                v = vel * (1.0 if k == 0 else 0.8) * self.rng.uniform(0.85, 1.05)
                self.add(name, tranh(f, sub * self.beat * 1.5, v, self.rng, vib=vib, bright=0.9), bar0 + b, beat)

    def vuot(self, bar, beat, start_deg, count=10, step_dur=0.045, up=True, vel=0.5, name="tranh_arp"):
        """Glissando sweep across the strings (pentatonic run)."""
        t0 = self.t_of(bar, beat)
        for k in range(count):
            g = start_deg + (k if up else -k)
            snd = tranh(self.mode.hz(g), 0.4, vel * (0.7 + 0.3 * k / count), self.rng, ring=1.5)
            dsp.place(self.stem(name), snd, ns(t0 + k * step_dur))

    def pads(self, chords, bar0, vel=0.6, octave=-1, bars_each=1, bright=0.5, name="pad"):
        for b, cd in enumerate(chords):
            dur = bars_each * self.bpb * self.beat
            self.add(name, pad(self.mode.chord(cd, octave), dur, vel, self.rng, bright=bright), bar0 + b * bars_each, 0, human=0)

    def bassline(self, chords, bar0, pattern, vel=0.7, octave=-2):
        """pattern: list of (beat, dur_beats, offset_degree)."""
        for b, cd in enumerate(chords):
            for beat, d, off in pattern:
                f = self.mode.hz(cd + 5 * octave + off)
                self.add("bass", bass(f, d * self.beat, vel * self.rng.uniform(0.9, 1.05), self.rng), bar0 + b, beat)

    def drums(self, bar0, bars, hits):
        """hits: list of (beat, kind, vel) per bar; kind in kick/brush/shaker/rim/clapper/mo/drum/drumrim/cymbal/choke."""
        fns = {"kick": kick, "brush": brush, "shaker": shaker, "rim": rim, "clapper": clapper, "mo": mo,
               "drum": lambda r, v: S.drum_hit(r) * v, "drumrim": lambda r, v: S.drum_hit(r, rim=True) * v * 0.6,
               "cymbal": lambda r, v: S.cymbal(r) * v * 0.5, "choke": lambda r, v: S.cymbal(r, True) * v * 0.5}
        for b in range(bars):
            for beat, kind, v in hits:
                self.add(kind if kind in ("kick", "shaker") else "perc", fns[kind](self.rng, v * self.rng.uniform(0.85, 1.05)),
                         bar0 + b, beat, human=0.004)

    # ---- mixdown
    def mix(self, spec, rt60=2.2, wet=0.22, lofi=0.5, crackle=0.3, comp=True):
        """spec: name -> (gain, pan, reverb_send). Returns the seamless stereo loop."""
        rng = self.rng
        dry = np.zeros((self.n, 2))
        send = np.zeros((self.n, 2))
        for name, x in self.stems.items():
            g, p, rs = spec.get(name, (1.0, 0.0, 0.3))
            st = x if x.ndim == 2 else dsp.pan(x, p)
            if name in ("tranh", "tranh_arp", "tranh2"):  # soundboard body
                st = dsp.peak(dsp.peak(st, 220, 1.2, 2.5), 650, 1.5, 1.5)
            if name == "bau":  # pickup + small amp
                st = dsp.peak(st, 1200, 0.8, 2.0)
            dry += st * g
            send += st * g * rs
        ir = dsp.make_ir(rt60, rng=rng, predelay=0.025, brightness=0.45, er_spread=0.06)
        wetsig = dsp.reverb_full(send, ir, wet=1.0, dry=0.0)
        full = dsp.pad_to(dry, len(wetsig)) + wetsig * wet
        L = ns(self.L)
        loop = dsp.wrap_tail(full, L)
        loop = loop - loop.mean(axis=0)
        # master EQ (circular): de-mud around 300 Hz, gentle presence/air shelf
        loop = S.circ_filter(loop, lambda f: (1 - 0.22 / (1 + ((f - 320) / 160) ** 2)) * (1 + 0.55 / (1 + (3200 / np.maximum(f, 1)) ** 2)))
        # ---- circular lo-fi colouring
        if lofi > 0:
            n = len(loop)
            k = max(1, round(self.L / 2.2))           # wow at ~0.45 Hz, an integer number of cycles per loop
            fw = k / self.L
            depth = 0.0016 * lofi                       # relative pitch deviation (0.16 % at lofi=1)
            D = depth / (TAU * fw) * SR                 # time deviation in samples
            idx = np.arange(n, dtype=float)
            warp = idx + D * np.sin(TAU * k * idx / n)
            for c in range(2):
                loop[:, c] = np.interp(warp % n, idx, loop[:, c], period=n)
            loop = S.circ_filter(loop, lambda f: 1 / np.sqrt(1 + (f / (15500 - 4000 * lofi)) ** 4) * (1 + 0.25 * lofi / (1 + (f / 180) ** 2)))
            pk = np.abs(loop).max() + 1e-9
            loop = dsp.soft_clip(loop / pk * (1 + 0.6 * lofi), 1.0 + 0.6 * lofi) * pk
        if crackle > 0:
            n = len(loop)
            hiss = S.stereo_bed(n, rng, S.shape_band(1500, 9000, -2, 2), 0.8) * 0.0015 * crackle
            cr = np.zeros((n, 2))
            for tt in rng.uniform(0, n / SR, int(n / SR * 7)):
                c = dsp.hp(dsp.click(ns(0.002), rng), 1500) * R(rng, 0.002, 0.02) * crackle
                dsp.place_wrap(cr, dsp.pan(c, R(rng, -0.6, 0.6)), ns(tt))
            loop = loop / (np.abs(loop).max() + 1e-9) * 0.5 + hiss + cr
        if comp:
            k = min(len(loop), ns(4.0))
            ext = np.concatenate([loop[-k:], loop], axis=0)
            loop = dsp.compressor(ext, thr_db=-20, ratio=2.2, attack=0.02, release=0.25)[k:]
        return loop


# =========================================================================== track 1: menu
def mus_menu(rng, i):
    """'Phố Cũ' — D Bắc, 72 bpm, 36 bars (2:00). Nostalgic, warm; flute & đàn tranh duet over a pad."""
    m = Mode(62, BAC)  # D4
    T = Track(72, 36, m, rng)
    A = [(1, 3), (1, 4), (2, 5), (1.5, 6), (0.5, 5), (1, 4), (1, 5), (2, 3), (1, 2), (1, 1), (4, 3)]
    A2 = [(1, 3), (1, 4), (2, 5), (1, 6), (1, 7), (2, 6), (1, 5), (1, 4), (1, 3), (1, 2), (3, 0), (1, None)]
    B = [(2, 5), (1, 4), (1, 5), (3, 6), (1, 5), (1, 4), (1, 3), (1, 4), (1, 2), (4, 3)]
    B2 = [(1, 2), (1, 3), (2, 4), (1, 5), (0.5, 4), (0.5, 3), (2, 2), (1.5, 1), (0.5, 2), (2, -2), (4, 0)]
    cA, cA2, cB, cB2 = [0, 2, 3, 3], [0, 1, 2, 0], [2, 1, 4, 3], [2, 0, 1, 0]
    intro = [0, 2, 3, 0]
    arp = [0, 2, 3, 4, 3, 2, 3, 1]
    form = [("intro", intro, None, None), ("A", cA, A, "flute"), ("A2", cA2, A2, "flute"), ("B", cB, B, "tranh"),
            ("B2", cB2, B2, "tranh"), ("A", cA, A, "duo"), ("A2", cA2, A2, "duo"), ("inter", [2, 3, 4, 3], None, "bau"),
            ("outro", intro, None, None)]
    bar = 0
    for name, ch, mel, lead in form:
        T.pads(ch, bar, vel=0.42)
        T.arpeggio(ch, bar, arp, octave=0, vel=0.32 if lead else 0.42)
        T.bassline(ch, bar, [(0, 2, 0), (2, 2, 3)], vel=0.45)
        if name in ("intro", "outro"):
            T.vuot(bar, 0, 0, 9, 0.05, vel=0.35)
        if lead == "flute":
            T.melody("flute", mel, bar, 0, 0.75)
        elif lead == "tranh":
            T.melody("tranh", mel, bar, 0, 0.9, ornament=0.5)
        elif lead == "duo":
            T.melody("flute", mel, bar, 0, 0.7)
            T.melody("tranh", mel, bar, -1, 0.55, name="tranh2", ornament=0.25)
        elif lead == "bau":
            T.melody("bau", [(2, 7), (2, 6), (3, 5), (1, 4), (2, 5), (2, 3), (4, 4)], bar, -1, 0.6)
        if name != "intro":
            for b in range(0, 4, 2):
                T.add("perc", clapper(rng, 0.25), bar + b, 0)
        bar += len(ch)
    spec = {"flute": (1.0, 0.18, 0.35), "tranh": (1.0, -0.2, 0.3), "tranh2": (0.8, -0.35, 0.3), "tranh_arp": (0.8, 0.3, 0.3),
            "pad": (0.9, 0, 0.4), "bass": (0.9, 0, 0.1), "bau": (1.0, 0.1, 0.4), "perc": (0.6, -0.2, 0.3)}
    return T.mix(spec, rt60=2.4, wet=0.25, lofi=0.45, crackle=0.5)


# =========================================================================== track 2: morning exploration
def mus_morning(rng, i):
    """'Sáng Hàng Mây' — G Bắc, 90 bpm, 48 bars (2:08). Sunny lo-fi groove with đàn tranh and flute."""
    m = Mode(55, BAC)  # G3
    T = Track(90, 48, m, rng, swing=0.57)
    H = [(0.5, 7), (0.5, 8), (1, 9), (0.5, 8), (0.5, 7), (1, 5),
         (1, 6), (0.5, 7), (1.5, 6), (1, 5),
         (0.5, 5), (0.5, 6), (1, 7), (1, 8), (1, 9),
         (2, 8), (2, None),
         (0.5, 7), (0.5, 8), (1, 9), (0.5, 8), (0.5, 7), (1, 5),
         (1, 6), (0.5, 7), (1.5, 9), (1, 10),
         (1, 9), (0.5, 8), (0.5, 7), (1, 8), (1, 6),
         (3, 5), (1, None)]
    Bm = [(2, 10), (1, 9), (1, 8), (3, 9), (1, 8), (1, 7), (1, 8), (1, 9), (1, 7), (4, 6),
          (2, 7), (1, 6), (1, 5), (2, 6), (1, 7), (1, 8), (1.5, 9), (0.5, 8), (1, 7), (1, 6), (4, 5)]
    cH = [2, 1, 0, 3, 2, 4, 3, 0]
    cB = [0, 4, 2, 1, 2, 4, 3, 0]
    riff = [0, None, 2, 3, None, 2, 4, 3]
    groove = [(0, "kick", 0.9), (1, "brush", 0.7), (1.75, "kick", 0.5), (2.5, "kick", 0.7), (3, "brush", 0.75)] + \
             [(k * 0.5, "shaker", 0.45 if k % 2 else 0.6) for k in range(8)]
    bass_pat = [(0, 1.5, 0), (1.5, 0.5, 0), (2.5, 1, 3), (3.5, 0.5, 2)]
    bar = 0
    # intro 4
    T.arpeggio([0, 2, 3, 0], bar, riff, octave=1, vel=0.45)
    T.pads([0, 2, 3, 0], bar, 0.4)
    T.drums(bar, 2, [(0, "kick", 0.5), (2.5, "kick", 0.4), (3, "brush", 0.35)])
    T.drums(bar + 2, 2, [(0, "kick", 0.6), (1, "brush", 0.4), (2.5, "kick", 0.5), (3, "brush", 0.45)] +
            [(k * 0.5, "shaker", 0.4) for k in range(8)])
    T.vuot(bar + 3, 2, 5, 9, 0.04, vel=0.4)
    bar += 4
    sections = [("H", cH, H, "tranh"), ("B", cB, Bm, "flute"), ("H", cH, H, "both"), ("break", [4, 3, 2, 3], None, "bau"),
                ("B", cB, Bm, "tranh"), ("H", cH, H, "both")]
    for name, ch, mel, lead in sections:
        T.pads(ch, bar, 0.5)
        if name == "break":
            T.melody("bau", [(3, 9), (1, 8), (2, 7), (2, 6), (3, 8), (1, 7), (4, 5)], bar, 0, 0.7)
            T.arpeggio(ch, bar, [0, None, 2, None, 3, None, 2, None], octave=1, vel=0.3)
            T.drums(bar + 2, 2, [(0, "kick", 0.6), (2.5, "kick", 0.5)] + [(k * 0.5, "shaker", 0.35) for k in range(8)])
            bar += len(ch)
            continue
        T.arpeggio(ch, bar, riff, octave=1, vel=0.35)
        T.bassline(ch, bar, bass_pat, vel=0.7)
        T.drums(bar, len(ch), groove)
        if lead == "tranh":
            T.melody("tranh", mel, bar, 0, 0.95, ornament=0.4)
        elif lead == "flute":
            T.melody("flute", mel, bar, 0, 0.75)
        else:
            T.melody("flute", mel, bar, 0, 0.7)
            T.melody("tranh", mel, bar, -1, 0.6, name="tranh2", ornament=0.3)
        T.add("perc", S.cymbal(rng, choke=True) * 0.15, bar, 0)
        bar += len(ch)
    spec = {"flute": (1.0, 0.2, 0.3), "tranh": (1.0, -0.15, 0.25), "tranh2": (0.75, -0.3, 0.25), "tranh_arp": (0.7, 0.35, 0.25),
            "pad": (0.7, 0, 0.35), "bass": (1.0, 0, 0.05), "bau": (1.0, 0.1, 0.35), "kick": (0.9, 0, 0.05),
            "shaker": (0.6, 0.3, 0.1), "perc": (0.8, -0.1, 0.15)}
    return T.mix(spec, rt60=1.8, wet=0.2, lofi=0.6, crackle=0.6)


# =========================================================================== track 3: night
def mus_night(rng, i):
    """'Đêm Phố' — A Nam/oán, 64 bpm, 36 bars (2:15). Sparse, intimate; đàn bầu over dark pads."""
    m = Mode(57, NAM)  # A3
    T = Track(64, 36, m, rng)
    N1 = [(2, 5), (2, 7), (3, 8), (1, 7), (1, 6), (1, 7), (2, 5), (4, 4)]
    N2 = [(2, 3), (1, 4), (1, 5), (2, 6), (2, 5), (1, 4), (1, 3), (2, 2), (4, 5)]
    N3 = [(1, 8), (1, 9), (2, 10), (3, 9), (1, 8), (2, 7), (1, 8), (1, 6), (4, 7)]
    N4 = [(2, 6), (1, 5), (1, 4), (3, 5), (1, 3), (1, 4), (1, 3), (1, 2), (1, 1), (4, 0)]
    c1, c2, c3, c4 = [0, 3, 1, 4], [3, 1, 4, 0], [3, 4, 2, 2], [1, 0, 4, 0]
    sparse_arp = [0, None, None, 3, None, 2, None, None]
    pulse = [(0, "kick", 0.45), (2.5, "brush", 0.3)]
    bar = 0
    form = [("intro", [0, 2, 0, 3], None, None), ("N1", c1, N1, "bau"), ("N2", c2, N2, "bau"), ("N3", c3, N3, "tranh"),
            ("N4", c4, N4, "tranh"), ("inter", [0, 2, 0, 3], None, "flute"), ("N1", c1, N1, "flute"),
            ("N4", c4, N4, "bau"), ("outro", [0, 2, 0, 3], None, None)]
    for name, ch, mel, lead in form:
        T.pads(ch, bar, 0.6, octave=-1, bright=0.3)
        T.arpeggio(ch, bar, sparse_arp, octave=0, vel=0.35, vib=10)
        T.bassline(ch, bar, [(0, 3.5, 0)], vel=0.4)
        if name not in ("intro",):
            T.drums(bar, len(ch), pulse)
        T.add("perc", mo(rng, 0.25), bar + 1, 2)
        if lead == "bau":
            T.melody("bau", mel, bar, 0, 0.75, ornament=0.5, vib=45)
        elif lead == "tranh":
            T.melody("tranh", mel, bar, 0, 0.85, ornament=0.55, vib=35)
        elif lead == "flute":
            if mel is None:
                T.melody("flute", [(3, 3), (1, 2), (4, 0), (2, 3), (2, 4), (4, 5)], bar, 0, 0.55)
            else:
                T.melody("flute", mel, bar, 0, 0.6)
        if name == "outro":
            T.vuot(bar + 3, 0, 10, 9, 0.06, up=False, vel=0.3)
        bar += len(ch)
    spec = {"flute": (0.9, 0.2, 0.45), "tranh": (1.0, -0.15, 0.4), "tranh_arp": (0.7, 0.35, 0.45), "pad": (0.9, 0, 0.5),
            "bass": (0.8, 0, 0.1), "bau": (1.1, 0.05, 0.5), "kick": (0.6, 0, 0.1), "perc": (0.6, -0.3, 0.45)}
    return T.mix(spec, rt60=3.0, wet=0.3, lofi=0.35, crackle=0.4)


# =========================================================================== track 4: festival
def mus_festival(rng, i):
    """'Đêm Trăng Rằm' — C Bắc, 112 bpm, 64 bars (2:17). Joyful Mid-Autumn night with lion-dance drums."""
    m = Mode(60, BAC)  # C4
    T = Track(112, 64, m, rng)
    Hk = [(0.5, 5), (0.5, 6), (0.5, 5), (0.5, 4), (1, 3), (1, 4),
          (0.5, 5), (0.5, 6), (1, 7), (1, 6), (1, 5),
          (0.5, 4), (0.5, 5), (0.5, 4), (0.5, 3), (1, 2), (1, 3),
          (2, 4), (1, 3), (1, None),
          (0.5, 5), (0.5, 6), (0.5, 5), (0.5, 4), (1, 3), (1, 4),
          (0.5, 5), (0.5, 6), (1, 7), (1, 8), (1, 9),
          (1, 8), (0.5, 7), (0.5, 6), (1, 5), (1, 4),
          (3, 5), (1, None)]
    Bf = [(1, 8), (1, 8), (0.5, 9), (0.5, 8), (1, 7), (1, 6), (1, 7), (2, 8), (1, 7), (0.5, 6), (0.5, 5), (1, 6), (1, 4), (4, 5),
          (1, 3), (1, 4), (1, 5), (1, 6), (1.5, 7), (0.5, 6), (2, 5), (1, 4), (0.5, 3), (0.5, 2), (1, 3), (1, 1), (4, 0)]
    cH = [0, 0, 2, 3, 0, 3, 3, 0]
    cB = [3, 1, 2, 0, 3, 2, 1, 0]
    lion = [(0, "drum", 1.0), (0.5, "drum", 0.6), (1, "drum", 0.8), (1.5, "drumrim", 0.7), (2, "drum", 0.9), (2.75, "drum", 0.6),
            (3, "drum", 0.8), (3.5, "drumrim", 0.8), (0, "cymbal", 0.6), (2, "choke", 0.5)] + \
           [(k * 0.5, "rim", 0.25) for k in range(8)]
    groove = lion + [(0, "kick", 0.8), (2, "kick", 0.7)]
    bass_pat = [(0, 1, 0), (1, 0.5, 3), (1.5, 0.5, 0), (2, 1, 2), (3, 1, 3)]
    riff = [0, 2, 3, 2, 4, 3, 2, 3]
    bar = 0
    # intro: drums + vuot sweeps
    T.drums(bar, 4, lion)
    T.vuot(bar + 1, 0, 0, 12, 0.035, vel=0.45)
    T.vuot(bar + 3, 0, 5, 10, 0.035, vel=0.5)
    T.pads([0, 0, 3, 3], bar, 0.4, bright=0.6)
    bar += 4
    sections = [("H", cH, Hk, "flute"), ("H", cH, Hk, "both"), ("B", cB, Bf, "tranh"), ("B", cB, Bf, "both"),
                ("break", [0, 3, 0, 3], None, None), ("H", cH, Hk, "both"), ("B", cB, Bf, "both"), ("H", cH, Hk, "flute")]
    for name, ch, mel, lead in sections:
        if name == "break":
            T.drums(bar, 4, lion + [(k * 0.5, "mo", 0.35) for k in range(0, 8, 2)])
            T.melody("bau", [(2, 5), (2, 7), (3, 8), (1, 9), (4, 10), (2, 8), (2, 7), (4, 5)], bar, 0, 0.6)
            bar += 4
            continue
        T.pads(ch, bar, 0.45, bright=0.6)
        T.arpeggio(ch, bar, riff, octave=1, vel=0.3)
        T.bassline(ch, bar, bass_pat, vel=0.65)
        T.drums(bar, len(ch), groove)
        if lead == "flute":
            T.melody("flute", mel, bar, 1 if mel is Hk else 0, 0.75)
        elif lead == "tranh":
            T.melody("tranh", mel, bar, 0, 0.95, ornament=0.4)
        else:
            T.melody("flute", mel, bar, 1 if mel is Hk else 0, 0.7)
            T.melody("tranh", mel, bar, 0 if mel is Hk else -1, 0.65, name="tranh2", ornament=0.3)
        bar += len(ch)
    spec = {"flute": (1.0, 0.15, 0.3), "tranh": (1.0, -0.2, 0.25), "tranh2": (0.8, -0.3, 0.25), "tranh_arp": (0.6, 0.35, 0.25),
            "pad": (0.6, 0, 0.35), "bass": (0.85, 0, 0.05), "bau": (1.0, 0.1, 0.35), "kick": (0.55, 0, 0.05), "perc": (0.5, 0.1, 0.25)}
    return T.mix(spec, rt60=2.0, wet=0.22, lofi=0.25, crackle=0.15)


# =========================================================================== track 5: tension (dog chase)
def mus_tension(rng, i):
    """'Vện Đuổi' — E Nam, 128 bpm, 48 bars (1:30). Light, playful tension: ostinato, tremolo tranh, stabs."""
    m = Mode(52, NAM)  # E3
    T = Track(128, 48, m, rng)
    T1 = [(0.5, 5), (0.5, 5), (0.5, 7), (0.5, 5), (1, 8), (1, 7), (0.5, 6), (0.5, 7), (1, 6), (2, 5),
          (0.5, 5), (0.5, 5), (0.5, 7), (0.5, 5), (1, 9), (1, 8), (1, 10), (1, 9), (2, 8)]
    T2 = [(1, 10), (0.5, 9), (0.5, 8), (1, 9), (1, 7), (2, 8), (1, 7), (1, 6),
          (0.5, 7), (0.5, 6), (0.5, 5), (0.5, 4), (1, 3), (1, 4), (4, 5)]
    c1, c2 = [0, 1, 0, 3], [0, 3, 2, 0]
    ost = [(k * 0.5, 0.4, off) for k, off in enumerate([0, 0, 3, 0, 4, 0, 3, 2])]
    gallop = [(0, "kick", 0.9), (0.75, "kick", 0.5), (1.5, "kick", 0.7), (2, "kick", 0.9), (2.75, "kick", 0.5), (3.5, "kick", 0.6),
              (1, "rim", 0.7), (3, "rim", 0.75)] + [(k * 0.25, "shaker", 0.3 + 0.2 * (k % 2 == 0)) for k in range(16)]

    def tremolo(deg_list, bar0):
        for b, deg in enumerate(deg_list):
            f = m.hz(deg)
            for k in range(16):
                v = 0.32 * (0.8 + 0.2 * np.sin(k)) * rng.uniform(0.9, 1.05)
                T.add("tranh2", tranh(f, 0.12, v, rng, ring=0.5), bar0 + b, k * 0.25, human=0.003)

    bar = 0
    T.bassline([0, 0, 0, 0], bar, ost, vel=0.7, octave=-1)
    T.drums(bar, 2, [(0, "kick", 0.7), (2, "kick", 0.6)] + [(k * 0.5, "shaker", 0.25) for k in range(8)])
    T.drums(bar + 2, 2, [(0, "kick", 0.9), (2, "kick", 0.9)] + [(k * 0.25, "shaker", 0.3) for k in range(16)])
    bar += 4
    sections = [("T1", c1, T1, "flute"), ("T1", c1, T1, "tranh"), ("T2", c2, T2, "trem"), ("T1", c1, T1, "both"),
                ("break", [0, 3, 0, 3], None, "bau"), ("T2", c2, T2, "both"), ("T1", c1, T1, "tranh"), ("T2", c2, T2, "trem"),
                ("T1", c1, T1, "both"), ("T2", c2, T2, "flute")]
    for name, ch, mel, lead in sections:
        T.bassline(ch, bar, ost, vel=0.7, octave=-1)
        T.pads(ch, bar, 0.3, octave=-1, bright=0.4)
        if name == "break":
            # comedic đàn bầu 'uh-oh' slides over a half-time beat
            T.drums(bar, 4, [(0, "kick", 0.8), (2, "rim", 0.7)] + [(k * 0.5, "shaker", 0.3) for k in range(8)])
            for b in range(4):
                n = ns(1.6)
                f0 = m.hz(8 if b % 2 == 0 else 7)
                curve = dsp.env_points([(0, f0), (0.3, f0), (0.9, f0 * 2 ** (-5 / 12)), (1.6, f0 * 2 ** (-5 / 12))], n)
                T.add("bau", bau(curve, 0.7, rng, vib=30), bar + b, 0)
            bar += 4
            continue
        T.drums(bar, len(ch), gallop)
        if lead == "flute":
            T.melody("flute", mel, bar, 0, 0.75, ornament=0.2)
        elif lead == "tranh":
            T.melody("tranh", mel, bar, 0, 0.9, ornament=0.3)
        elif lead == "trem":
            tremolo([d + 5 for d in ch], bar)
            T.melody("flute", mel, bar, 0, 0.6, ornament=0.2)
        else:
            T.melody("flute", mel, bar, 0, 0.7, ornament=0.2)
            T.melody("tranh", mel, bar, -1, 0.65, name="tranh", ornament=0.3)
        T.add("perc", S.cymbal(rng, choke=True) * 0.3, bar, 0)
        bar += len(ch)
    spec = {"flute": (0.95, 0.2, 0.2), "tranh": (1.0, -0.2, 0.2), "tranh2": (0.8, -0.35, 0.2), "pad": (0.5, 0, 0.3),
            "bass": (0.9, 0, 0.05), "bau": (1.0, 0.1, 0.3), "kick": (0.65, 0, 0.03), "shaker": (0.6, 0.35, 0.05), "perc": (0.7, -0.1, 0.15)}
    return T.mix(spec, rt60=1.5, wet=0.18, lofi=0.3, crackle=0.2)


# =========================================================================== stingers
def _stinger(rng, build, length, rt60=2.0):
    m = Mode(62, BAC)
    T = Track(90, 4, m, rng, tail=length + 3)
    build(T, m)
    spec = {"flute": (1.0, 0.15, 0.35), "tranh": (1.0, -0.15, 0.3), "tranh_arp": (0.8, 0.25, 0.35), "pad": (0.8, 0, 0.4),
            "bau": (1.0, 0.0, 0.4), "perc": (0.8, 0, 0.3), "bass": (0.8, 0, 0.1), "kick": (0.8, 0, 0.1)}
    dry = np.zeros((T.n, 2))
    send = np.zeros((T.n, 2))
    for name, x in T.stems.items():
        g, p, rs = spec.get(name, (1, 0, 0.3))
        st = x if x.ndim == 2 else dsp.pan(x, p)
        dry += st * g
        send += st * g * rs
    ir = dsp.make_ir(rt60, rng=rng, predelay=0.02, brightness=0.5)
    wet = dsp.reverb_full(send, ir, 1.0, 0.0)
    out = dsp.pad_to(dry, len(wet)) + wet * 0.3
    return dsp.trim_silence(out, -60, 0.05)


def stinger_discovery(rng, i):
    def b(T, m):
        T.vuot(0, 0, 0, 10, 0.045, vel=0.45)
        T.melody("flute", [(1, 3), (1, 5), (2, 6), (4, 5)], 0, 0, 0.7)
        T.pads([0, 2], 0, 0.5, bars_each=1)
    return _stinger(rng, b, 6)


def stinger_quest_complete(rng, i):
    def b(T, m):
        T.vuot(0, 0, 0, 12, 0.035, vel=0.5)
        T.melody("flute", [(0.5, 5), (0.5, 6), (1, 7), (0.5, 6), (0.5, 7), (1, 8), (4, 10)], 0, 0, 0.8)
        T.melody("tranh", [(2, 5), (1, 7), (1, 8), (4, 10)], 0, -1, 0.6)
        T.pads([0, 0], 0, 0.55, bars_each=1, bright=0.6)
        T.add("perc", S.cymbal(rng) * 0.25, 0, 0)
        T.add("perc", S.drum_hit(rng) * 0.6, 0, 0)
        T.add("perc", S.drum_hit(rng) * 0.7, 1, 0)
    return _stinger(rng, b, 7)


def stinger_memory(rng, i):
    """Kỷ niệm (memory photograph found): wistful đàn bầu phrase."""
    def b(T, m):
        T.melody("bau", [(2, 3), (1, 5), (1, 4), (3, 3), (1, 2), (4, 3)], 0, 0, 0.75, vib=42)
        T.pads([0, 4, 3], 0, 0.55, bars_each=1, bright=0.3)
        T.arpeggio([0, 4], 0, [0, None, 2, None, 3, None, 5, None], 0, 0.3)
    return _stinger(rng, b, 9, rt60=2.8)


def stinger_chase_end(rng, i):
    """Relief after escaping the dog: descending tranh run settling on the tonic."""
    def b(T, m):
        T.vuot(0, 0, 10, 10, 0.05, up=False, vel=0.45)
        T.melody("flute", [(1, 7), (1, 6), (2, 5)], 0, 0, 0.6)
        T.pads([0], 0, 0.5)
        T.add("perc", mo(rng, 0.4), 0, 2)
    return _stinger(rng, b, 5)


def stinger_festival(rng, i):
    """Festival begins: drum roll, cymbal crash, flute flourish."""
    def b(T, m):
        for k in range(16):
            T.add("perc", S.drum_hit(rng) * (0.3 + 0.04 * k), 0, k * 0.125, human=0)
        T.add("perc", S.cymbal(rng) * 0.6, 0, 2)
        T.add("perc", S.drum_hit(rng) * 1.0, 0, 2)
        T.melody("flute", [(2, None), (0.5, 5), (0.5, 6), (1, 7), (0.5, 8), (0.5, 9), (3, 10)], 0, 0, 0.8)
        T.vuot(0, 2, 5, 10, 0.03, vel=0.5)
    return _stinger(rng, b, 6)


# =========================================================================== registry
MUS = dict(category="music", bus="Music", loop=True, mode="integrated", quality=5, pitch_jitter=0.0, priority=10)
STG = dict(category="music", sub="stingers", bus="Music", mode="short", quality=5, pitch_jitter=0.0, priority=10)
SOUNDS = [
    Sound("mus_menu", mus_menu, target=-18, desc="'Phố Cũ' menu theme — D Bắc, 72 bpm, 2:00", extra={"bpm": 72, "bars": 36}, **MUS),
    Sound("mus_morning", mus_morning, target=-18, desc="'Sáng Hàng Mây' day exploration — G Bắc, 90 bpm, 2:08", extra={"bpm": 90, "bars": 48}, **MUS),
    Sound("mus_night", mus_night, target=-19, desc="'Đêm Phố' night exploration — A Nam/oán, 64 bpm, 2:15", extra={"bpm": 64, "bars": 36}, **MUS),
    Sound("mus_festival", mus_festival, target=-17, desc="'Đêm Trăng Rằm' festival night — C Bắc, 112 bpm, 2:17", extra={"bpm": 112, "bars": 64}, **MUS),
    Sound("mus_tension", mus_tension, target=-17, desc="'Vện Đuổi' light tension for the dog chase — E Nam, 128 bpm, 1:30", extra={"bpm": 128, "bars": 48}, **MUS),
    Sound("stinger_discovery", stinger_discovery, target=-18, desc="Location discovered", **STG),
    Sound("stinger_quest_complete", stinger_quest_complete, target=-16, desc="Main quest step complete (bigger than ui_quest_complete)", **STG),
    Sound("stinger_memory", stinger_memory, target=-19, desc="Kỷ niệm memory photograph found", **STG),
    Sound("stinger_chase_end", stinger_chase_end, target=-19, desc="Escaped the dog — relief", **STG),
    Sound("stinger_festival", stinger_festival, target=-15, desc="Festival begins", **STG),
]
