"""Sound specification shared by all generator modules.

A generator module exposes SOUNDS: list[Sound]. build_all.py renders every variant, normalises it to
its loudness target, encodes Ogg Vorbis into assets/audio/<category>/<sub>/ and writes the manifest
assets/audio/bank.json consumed by scripts/autoload/audio_manager.gd.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Sound:
    name: str                      # bank name used by AudioManager (snake_case)
    fn: Callable                   # fn(rng, variant_index) -> np.ndarray (mono (n,) or stereo (n,2))
    category: str                  # sfx | ambience | music | ui
    sub: str = ""                  # sub-folder inside category
    variants: int = 1
    bus: str = "SFX"               # Master | Music | SFX | Ambience | UI | Voice
    target: float = -18.0          # loudness target (LUFS)
    mode: str = "momentary"        # momentary (max 400 ms) | short (max 3 s) | integrated
    loop: bool = False
    quality: float = 4.0           # vorbis -q
    max_distance: float = 0.0      # AudioStreamPlayer3D.max_distance (0 = unlimited)
    unit_size: float = 3.0         # AudioStreamPlayer3D.unit_size
    pitch_jitter: float = 0.04
    volume_db: float = 0.0
    priority: int = 5              # voice stealing priority (higher survives)
    desc: str = ""
    trim: bool = True              # trim trailing silence for one-shots
    extra: dict = field(default_factory=dict)  # any extra manifest fields (e.g. bpm)
