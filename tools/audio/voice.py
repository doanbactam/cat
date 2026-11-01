"""Source-filter voice synthesis used by cats, dogs, birds, geckos and human non-verbal sounds.

Two engines:
* additive_voice: phase-coherent harmonic synthesis; each harmonic's amplitude is the time-varying
  formant envelope evaluated at k*F0(t). Clean, alias-free, ideal for meows/whistles/coos.
* pulse_voice: band-limited glottal pulse train with jitter/shimmer, spectrally shaped by a
  time-varying formant envelope in the STFT domain. Ideal for rough voices (growls, barks, caws, fry).
Both add aspiration noise shaped by the same envelope, modulated pitch-synchronously.
"""
from __future__ import annotations

import numpy as np

from dsp import SR, TAU, env_points, formant_env, formant_mag, frac_impulses, smooth_noise, stft_shape, pulse_times, hp, lp


def bumps_env(f: np.ndarray, formants, gains_db=(14.0, 12.0, 9.0, 6.0, 4.0, 3.0)) -> np.ndarray:
    """Parallel-style envelope: every formant is a Lorentzian peak (gain gains_db[i]) on a flat floor.
    The overall spectral slope then comes only from the source tilt, avoiding the cascade's cumulative
    -12 dB/oct per formant (which makes bright open voices sound dull)."""
    g = 1.0
    for (F, BW), gd in zip(formants, gains_db):
        G = 10 ** (gd / 20)
        g = g * (1 + (G - 1) / (1 + ((f - F) / (BW * 0.5)) ** 2))
    return g


def contour(points, n: int, sr: int = SR) -> np.ndarray:
    """Smooth contour from [(t_frac 0..1, value)] over n samples."""
    dur = n / sr
    return env_points([(p[0] * dur, p[1]) for p in points], n, sr, smooth=True)


def f0_track(points, n: int, rng, vib_rate: float = 6.0, vib_depth: float = 0.01, jitter: float = 0.01,
             drift: float = 0.0, sr: int = SR) -> np.ndarray:
    base = contour(points, n, sr)
    t = np.arange(n) / sr
    vib_on = np.clip(t / 0.15, 0, 1)
    vib = vib_depth * vib_on * np.sin(TAU * vib_rate * t + rng.uniform(0, TAU)) * (1 + 0.3 * smooth_noise(n, 3, rng))
    jit = jitter * smooth_noise(n, 35, rng) + drift * smooth_noise(n, 2.5, rng)
    return base * (1 + vib + jit)


def formant_tracks(spec: list, n: int, sr: int = SR):
    """spec: list of (F_points, BW_points) where points are [(t_frac, Hz)] or a scalar."""
    out = []
    for F, BW in spec:
        Fa = contour(F, n, sr) if isinstance(F, (list, tuple)) else np.full(n, float(F))
        Ba = contour(BW, n, sr) if isinstance(BW, (list, tuple)) else np.full(n, float(BW))
        out.append((Fa, Ba))
    return out


def additive_voice(f0: np.ndarray, amp: np.ndarray, formants, rng, tilt_db_oct=-9.0, breath: float = 0.1,
                   sub_harm: float = 0.0, roughness: float = 0.0, max_h: int = 80, ctrl: int = 32,
                   breath_hp: float = 1200.0, env_model: str = "cascade", sr: int = SR) -> np.ndarray:
    """formants: list of (F[n], BW[n]) arrays. tilt_db_oct: scalar or per-sample array (source+radiation slope).
    env_model: "cascade" (Klatt cascade, dark, for closed/nasal voices) or "bumps" (bright open voices)."""
    envf = formant_env if env_model == "cascade" else bumps_env
    n = len(f0)
    nc = n // ctrl + 2
    ci = np.minimum(np.arange(nc) * ctrl, n - 1)
    f0c = f0[ci]
    tilt_c = (np.broadcast_to(np.asarray(tilt_db_oct, float), (n,)))[ci]
    Fc = [(F[ci], B[ci]) for F, B in formants]
    phi = TAU * np.cumsum(f0) / sr
    out = np.zeros(n)
    xs = np.arange(n)
    hmax = int(min(max_h, (sr * 0.45) / max(f0.min(), 30)))
    shimmer = 1 + 0.06 * smooth_noise(n, 25, rng) if roughness > 0 else None
    for k in range(1, hmax + 1):
        fk = k * f0c
        if fk.min() > sr * 0.45:
            break
        a = envf(fk, Fc) * (k ** (tilt_c / 6.0206))
        a *= np.clip((sr * 0.45 - fk) / 2000.0, 0, 1)  # fade near Nyquist
        if a.max() < 1e-5:
            continue
        ak = np.interp(xs, ci, a)
        out += ak * np.sin(k * phi + rng.uniform(-0.3, 0.3))
    if sub_harm > 0:  # period doubling: half-harmonics shaped by the same envelope, in intermittent bursts
        gate = np.clip(smooth_noise(n, 5, rng) * 1.6 - 0.2, 0, 1)
        for k in range(1, hmax * 2, 2):
            fk = 0.5 * k * f0c
            if fk.min() > sr * 0.45:
                break
            a = envf(fk, Fc) * (max(0.5 * k, 1.0) ** (tilt_c / 6.0206)) * sub_harm
            ak = np.interp(xs, ci, a) * gate
            out += ak * np.sin(0.5 * k * phi + rng.uniform(0, TAU))
    if roughness > 0:
        out *= shimmer * (1 + roughness * smooth_noise(n, 60, rng))
    out /= (np.abs(out).max() + 1e-9)
    if breath > 0:
        nz = rng.standard_normal(n)
        # pitch-synchronous modulation fuses breath with voice
        nz *= 0.55 + 0.45 * (0.5 + 0.5 * np.cos(phi)) ** 2
        Ftr = formants

        def g(f, t):
            idx = np.minimum((t * sr).astype(int), n - 1)
            spec = [(F[idx][None, :], B[idx][None, :] * 1.6) for F, B in Ftr]
            e = envf(f[:, None], spec)
            hpf = 1 / np.sqrt(1 + (breath_hp / np.maximum(f[:, None], 1)) ** 4)
            return e * hpf
        nz = stft_shape(nz, g, 512, sr)
        nz /= (np.abs(nz).max() + 1e-9)
        out = out + breath * nz
    return out * amp


def glottal_source(f0: np.ndarray, rng, jitter: float = 0.01, shimmer: float = 0.05, sr: int = SR,
                   irregular: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Band-limited impulse train (glottal closures). irregular adds random missing/extra pulses (fry).
    Returns (pulses, phase_cycles)."""
    n = len(f0)
    t = pulse_times(f0, jitter, rng, sr, phase0=rng.uniform(0, 1))
    if irregular > 0 and len(t) > 2:
        keep = rng.random(len(t)) > irregular * 0.25
        t = t[keep]
    amps = 1 + shimmer * rng.standard_normal(len(t))
    if irregular > 0:
        amps *= 1 + irregular * rng.standard_normal(len(t))
    x = frac_impulses(n, t, np.abs(amps), sr)
    ph = np.cumsum(f0) / sr
    return x, ph


def pulse_voice(f0: np.ndarray, amp: np.ndarray, formants, rng, tilt_db_oct=-6.0, breath: float = 0.1,
                jitter: float = 0.01, shimmer: float = 0.05, irregular: float = 0.0, nperseg: int = 512,
                breath_hp: float = 800.0, sr: int = SR) -> np.ndarray:
    n = len(f0)
    src, ph = glottal_source(f0, rng, jitter, shimmer, sr, irregular)
    nz = rng.standard_normal(n) * (0.5 + 0.5 * (0.5 + 0.5 * np.cos(TAU * ph)) ** 2)
    src_tilt = np.broadcast_to(np.asarray(tilt_db_oct, float), (n,))

    def g_voice(f, t):
        idx = np.minimum((t * sr).astype(int), n - 1)
        spec = [(F[idx][None, :], B[idx][None, :]) for F, B in formants]
        e = formant_env(f[:, None], spec)
        tl = (np.maximum(f[:, None], 50) / 100.0) ** (src_tilt[idx][None, :] / 6.0206)
        return e * tl

    def g_breath(f, t):
        idx = np.minimum((t * sr).astype(int), n - 1)
        spec = [(F[idx][None, :], B[idx][None, :] * 1.5) for F, B in formants]
        e = formant_env(f[:, None], spec)
        return e / np.sqrt(1 + (breath_hp / np.maximum(f[:, None], 1)) ** 4)

    v = stft_shape(src, g_voice, nperseg, sr)
    v /= np.abs(v).max() + 1e-9
    out = v
    if breath > 0:
        b = stft_shape(nz, g_breath, nperseg, sr)
        b /= np.abs(b).max() + 1e-9
        out = out + breath * b
    return out * amp


def noise_formant(n: int, formants, rng, amp: np.ndarray | None = None, hp_hz: float = 0.0, nperseg: int = 512,
                  sr: int = SR) -> np.ndarray:
    """Noise shaped by a (time-varying) formant envelope — whispers, hisses, breaths."""
    nz = rng.standard_normal(n)

    def g(f, t):
        idx = np.minimum((t * sr).astype(int), n - 1)
        spec = [(F[idx][None, :], B[idx][None, :]) for F, B in formants]
        e = formant_env(f[:, None], spec)
        if hp_hz > 0:
            e = e / np.sqrt(1 + (hp_hz / np.maximum(f[:, None], 1)) ** 4)
        return e
    y = stft_shape(nz, g, nperseg, sr)
    y /= np.abs(y).max() + 1e-9
    return y * (amp if amp is not None else 1.0)
