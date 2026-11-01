#!/usr/bin/env python3
"""Build every procedural sound for Mèo Cam.

Usage (from repo root):
  tools/audio/build.sh                      # everything (clean rebuild)
  tools/audio/build.sh --only 'cat_meow.*'  # regex filter on bank names (manifest is merged)
  tools/audio/build.sh --cards              # also render a spectrogram card per sound
Outputs: assets/audio/{sfx,ambience,music,ui}/**.ogg, assets/audio/bank.json,
         qa/out/audio/{report.md,report.json,sheet_*.png,cards/*.png}
"""
from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
AUDIO = os.path.join(ROOT, "assets", "audio")
QA = os.path.join(ROOT, "qa", "out", "audio")

import dsp  # noqa: E402
import qa  # noqa: E402

MODULES = ["gen_cat", "gen_foley", "gen_world", "gen_entities", "gen_ui", "gen_music"]


def load_specs(only: str | None):
    specs = []
    for m in MODULES:
        try:
            mod = importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name == m:
                continue
            raise
        for s in mod.SOUNDS:
            if only is None or re.fullmatch(only, s.name):
                specs.append((m, s))
    return specs


def out_path(s, i: int) -> str:
    sub = os.path.join(s.category, s.sub) if s.sub else s.category
    fn = f"{s.name}_{i + 1:02d}.ogg" if s.variants > 1 else f"{s.name}.ogg"
    return os.path.join(AUDIO, sub, fn)


def _circular_filter(x: np.ndarray, fn, pre_s: float = 2.0) -> np.ndarray:
    """Apply an IIR/stateful process to a loop without breaking its seam."""
    k = min(len(x), dsp.ns(pre_s))
    ext = np.concatenate([x[-k:], x], axis=0)
    return fn(ext)[k:]


def render_one(modname: str, name: str, i: int, cards: bool):
    mod = importlib.import_module(modname)
    s = next(x for x in mod.SOUNDS if x.name == name)
    rng = dsp.rng_for(name, i)
    t0 = time.time()
    x = np.asarray(s.fn(rng, i), dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise RuntimeError(f"{name}[{i}] produced non-finite samples")
    if s.loop:
        x = x - x.mean(axis=0)
        x = _circular_filter(x, lambda y: dsp.hp(y, 18, 2))
        cur = dsp.measure(x, s.mode)
        x = x * dsp.db(s.target - cur)
        if dsp.true_peak_db(x) > -1.0:
            x = _circular_filter(x, lambda y: dsp.limiter(y, -1.3))
    else:
        x = dsp.hp(x, 18, 2)
        if s.trim:
            x = dsp.trim_silence(x, -65)
        x = dsp.fades(x, 0.0005, min(0.02, len(x) / dsp.SR / 5))
        x = dsp.normalize(x, s.target, s.mode, -1.5)
    path = out_path(s, i)
    # encode; Vorbis can overshoot on sharp transients -> verify decoded true peak and back off if needed
    for _attempt in range(4):
        size = dsp.write_ogg(path, x, s.quality)
        y, sr = dsp.read_audio(path)  # decode back: verify what Godot will actually play
        tp = dsp.true_peak_db(y)
        if tp <= -1.0:
            break
        x = x * dsp.db(-1.2 - tp)
    st = qa.stats(y, s.loop)
    st["target"] = s.target
    st["mode"] = s.mode
    st["measured"] = dsp.measure(y, s.mode)
    st["size"] = size
    st["render_s"] = time.time() - t0
    if cards and (i == 0 or s.loop):
        rel = os.path.relpath(path, AUDIO)
        qa.render_card(y, f"{name} [{i + 1}/{s.variants}]  {rel}", os.path.join(QA, "cards", f"{name}_{i + 1:02d}.png"), s.loop)
    thumb = y if len(y) < dsp.ns(20) else y[:dsp.ns(20)]
    return name, i, path, st, thumb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="regex on bank names")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--no-clean", action="store_true")
    args = ap.parse_args()

    specs = load_specs(args.only)
    if not specs:
        print("no sounds matched")
        return 1
    manifest_path = os.path.join(AUDIO, "bank.json")
    manifest = {"version": 1, "sounds": {}}
    if args.only and os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    if not args.only and not args.no_clean:
        for p in glob.glob(os.path.join(AUDIO, "**", "*.ogg"), recursive=True) + \
                glob.glob(os.path.join(AUDIO, "**", "*.ogg.import"), recursive=True):
            os.remove(p)
    else:
        for _, s in specs:  # remove stale variants of rebuilt sounds
            d = os.path.dirname(out_path(s, 0))
            for p in glob.glob(os.path.join(d, f"{s.name}.ogg*")) + glob.glob(os.path.join(d, f"{s.name}_[0-9][0-9].ogg*")):
                os.remove(p)

    jobs = [(m, s.name, i) for m, s in specs for i in range(s.variants)]
    # longest first (music, ambience) for better packing
    weight = {"music": 0, "ambience": 1}
    jobs.sort(key=lambda j: weight.get(next(s for m, s in specs if s.name == j[1]).category, 2))
    print(f"rendering {len(jobs)} files for {len(specs)} sounds with {args.jobs} workers")
    results = {}
    failures = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(render_one, m, n, i, args.cards): (n, i) for m, n, i in jobs}
        for k, fut in enumerate(as_completed(futs)):
            n, i = futs[fut]
            try:
                name, i, path, st, thumb = fut.result()
            except Exception as e:  # report and keep going
                import traceback
                tb = "".join(traceback.format_exception(e)).strip().splitlines()
                print(f"  FAIL {n}[{i}]: {e!r}\n    " + "\n    ".join(l for l in tb if 'tools/audio' in l or 'Error' in l))
                failures.append(f"{n}[{i}]")
                continue
            results[(name, i)] = (path, st, thumb)
            if (k + 1) % 20 == 0 or k + 1 == len(jobs):
                print(f"  {k + 1}/{len(jobs)} done ({time.time() - t0:.0f}s)")

    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)} (manifest not written)")
        return 2
    # ---------------------------------------------------------------- manifest
    for m, s in specs:
        files = []
        for i in range(s.variants):
            p = results[(s.name, i)][0]
            files.append("res://" + os.path.relpath(p, ROOT).replace(os.sep, "/"))
        entry = {
            "files": files, "category": s.category, "group": s.sub, "bus": s.bus, "loop": s.loop,
            "volume_db": s.volume_db, "pitch_jitter": s.pitch_jitter, "unit_size": s.unit_size,
            "max_distance": s.max_distance, "priority": s.priority, "desc": s.desc,
            "length": round(float(np.mean([results[(s.name, i)][1]["dur"] for i in range(s.variants)])), 3),
        }
        entry.update(s.extra)
        manifest["sounds"][s.name] = entry
    manifest["sounds"] = dict(sorted(manifest["sounds"].items()))
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)

    # ---------------------------------------------------------------- QA report
    os.makedirs(QA, exist_ok=True)
    rep_path = os.path.join(QA, "report.json")
    report = {}
    if args.only and os.path.exists(rep_path):
        with open(rep_path) as f:
            report = json.load(f)
    for (name, i), (path, st, _) in results.items():
        report[f"{name}#{i + 1}"] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()}
        report[f"{name}#{i + 1}"]["file"] = os.path.relpath(path, ROOT)
    report = dict(sorted(report.items()))
    with open(rep_path, "w") as f:
        json.dump(report, f, indent=1)
    problems = []
    for key, st in report.items():
        if st["true_peak_db"] > -0.5:
            problems.append(f"{key}: true peak {st['true_peak_db']:.2f} dBTP")
        if st["dc"] > 0.002:
            problems.append(f"{key}: DC {st['dc']:.4f}")
        if abs(st["measured"] - st["target"]) > 1.5:
            peak_limited = st["measured"] < st["target"] and st["true_peak_db"] > -3.0
            if not peak_limited:  # transient sounds that hit the TP ceiling first are expected to read low
                problems.append(f"{key}: loudness {st['measured']:.1f} vs target {st['target']:.1f} ({st['mode']})")
        if "seam" in st and st["seam"] > 3.0:
            problems.append(f"{key}: loop seam discontinuity {st['seam']:.2f}")
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(AUDIO, "**", "*.ogg"), recursive=True))
    with open(os.path.join(QA, "report.md"), "w") as f:
        f.write(f"# Audio build report\n\nfiles: {len(report)}  total ogg size: {total / 1e6:.1f} MB\n\n")
        f.write("## Problems\n" + ("\n".join(f"- {p}" for p in problems) if problems else "none") + "\n\n")
        f.write("| sound | dur s | target | measured | TP dBTP | DC | seam | KB |\n|---|---|---|---|---|---|---|---|\n")
        for key, st in report.items():
            f.write(f"| {key} | {st['dur']:.2f} | {st['target']} {st['mode'][:3]} | {st['measured']:.1f} | "
                    f"{st['true_peak_db']:.1f} | {st['dc']:.4f} | {st.get('seam', '')} | {st['size'] // 1024} |\n")
    # contact sheets per category/group
    groups = {}
    for m, s in specs:
        groups.setdefault(f"{s.category}_{s.sub}" if s.sub else s.category, []).append(s)
    for g, ss in groups.items():
        items = []
        for s in ss:
            for i in range(s.variants):
                items.append((f"{s.name}#{i + 1}", results[(s.name, i)][2]))
        for page in range(0, len(items), 48):
            qa.contact_sheet(items[page:page + 48], os.path.join(QA, f"sheet_{g}_{page // 48 + 1}.png"))
    print(f"total ogg size {total / 1e6:.1f} MB; problems: {len(problems)}")
    for p in problems[:40]:
        print("  !", p)
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
