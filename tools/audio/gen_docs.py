#!/usr/bin/env python3
"""Regenerate the sound catalogue in docs/areas/audio.md from assets/audio/bank.json.
The table goes between the markers <!-- BANK:BEGIN --> and <!-- BANK:END -->."""
from __future__ import annotations

import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BANK = os.path.join(ROOT, "assets", "audio", "bank.json")
DOC = os.path.join(ROOT, "docs", "areas", "audio.md")

ORDER = [("sfx", "cat", "Cat — voice & body foley"), ("sfx", "foley", "Footsteps & landings"),
         ("sfx", "impacts", "Knock-over impacts, splashes"), ("sfx", "entities", "World entities (vehicles, animals, people, places)"),
         ("ambience", "", "Ambience beds (loops)"), ("ambience", "weather", "Weather"), ("music", "", "Music (loops)"),
         ("music", "stingers", "Music stingers (play_stinger)"), ("ui", "", "UI (play_ui)")]


def main() -> None:
    with open(BANK) as f:
        bank = json.load(f)["sounds"]
    total_files = sum(len(e["files"]) for e in bank.values())
    size = 0
    for e in bank.values():
        for p in e["files"]:
            fp = os.path.join(ROOT, p.replace("res://", ""))
            if os.path.exists(fp):
                size += os.path.getsize(fp)
    out = [f"**{len(bank)} bank names, {total_files} variant files, {size / 1e6:.1f} MB Ogg Vorbis.** "
           "Columns: variants · bus · loop · approx. length · 3D unit_size / max_distance (m).\n"]
    for cat, grp, title in ORDER:
        rows = [(k, e) for k, e in bank.items() if e["category"] == cat and e.get("group", "") == grp]
        if not rows:
            continue
        out.append(f"\n### {title}\n")
        out.append("| name | var | bus | loop | len s | unit/max | description |")
        out.append("|---|---|---|---|---|---|---|")
        for k, e in sorted(rows):
            ud = f"{e['unit_size']:g}/{e['max_distance']:g}" if cat == "sfx" else "–"
            out.append(f"| `{k}` | {len(e['files'])} | {e['bus']} | {'yes' if e['loop'] else ''} | {e['length']:.1f} | {ud} | "
                       f"{e['desc'].replace('|', '/')} |")
    table = "\n".join(out)
    with open(DOC) as f:
        doc = f.read()
    a, b = "<!-- BANK:BEGIN -->", "<!-- BANK:END -->"
    i, j = doc.index(a) + len(a), doc.index(b)
    doc = doc[:i] + "\n" + table + "\n" + doc[j:]
    with open(DOC, "w") as f:
        f.write(doc)
    print(f"catalogue written: {len(bank)} sounds")


if __name__ == "__main__":
    main()
