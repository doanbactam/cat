#!/usr/bin/env python3
"""Merges every data/i18n/requests/<area>.csv into data/i18n/strings.csv (owner: ui).

Rules
- Columns: keys,en,vi (other columns are ignored; missing translations fall back to the other
  language and are reported).
- Keys already in strings.csv but in no request file are kept (hand-added by the lead).
- A key defined by several request files: ui.csv wins, then alphabetical area order; every
  conflicting definition with different text is reported.
- Output order: kept keys first, then each area's keys in file order (stable diffs).
- ui.csv gets a sibling .import with importer="keep" so Godot never builds a translation from a
  request file (only strings.csv is imported as a Translation); other areas' files are only
  reported when they lack one (their owners add it).
Run:  python3 scripts/ui/build/merge_i18n.py [--check]   (--check: report only, write nothing)
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
I18N = os.path.join(ROOT, "data", "i18n")
REQ = os.path.join(I18N, "requests")
OUT = os.path.join(I18N, "strings.csv")
KEEP_IMPORT = '[remap]\n\nimporter="keep"\n'


def read_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        if not header:
            return rows
        cols = [h.strip() for h in header]
        try:
            ik, ie, iv = cols.index("keys"), cols.index("en"), cols.index("vi")
        except ValueError:
            print("  ! %s: header must contain keys,en,vi (got %s)" % (os.path.relpath(path, ROOT), cols))
            return rows
        for n, row in enumerate(r, start=2):
            if not row or not row[ik].strip():
                continue
            if len(row) <= max(ik, ie, iv):
                row = row + [""] * (max(ik, ie, iv) + 1 - len(row))
            rows.append((row[ik].strip(), row[ie], row[iv], n))
    return rows


def main():
    check = "--check" in sys.argv
    existing = read_csv(OUT) if os.path.exists(OUT) else []
    files = sorted(f for f in os.listdir(REQ) if f.endswith(".csv"))
    files.sort(key=lambda f: (0 if f == "ui.csv" else 1, f))
    merged = {}
    origin = {}
    order = []
    problems = 0
    for f in files:
        path = os.path.join(REQ, f)
        imp = path + ".import"
        has_keep = os.path.exists(imp) and 'importer="keep"' in open(imp).read()
        if not has_keep:
            if f == "ui.csv" and not check:
                with open(imp, "w") as fi:
                    fi.write(KEEP_IMPORT)
            elif f != "ui.csv":
                print("  ~ %s has no importer=\"keep\" .import (its owner should add one)" % f)
        for key, en, vi, line in read_csv(path):
            if not en and not vi:
                print("  ! %s:%d %s has no text" % (f, line, key))
                problems += 1
                continue
            if not vi:
                print("  ~ %s:%d %s missing vi (falls back to en)" % (f, line, key))
                vi = en
            if not en:
                print("  ~ %s:%d %s missing en (falls back to vi)" % (f, line, key))
                en = vi
            if key in merged:
                if merged[key] != (en, vi):
                    print("  ! conflict %s: %s keeps %r, %s:%d has %r" % (key, origin[key], merged[key][0], f, line, en))
                    problems += 1
                continue
            merged[key] = (en, vi)
            origin[key] = f
            order.append(key)
    kept = [(k, e, v) for (k, e, v, _) in existing if k not in merged]
    out_rows = [(k, e, v) for (k, e, v) in kept] + [(k,) + merged[k] for k in order]
    print("merge: %d request files, %d keys from requests, %d kept-only keys, %d total, %d problems" %
          (len(files), len(order), len(kept), len(out_rows), problems))
    for f in files:
        n = sum(1 for k in order if origin[k] == f)
        print("   %-24s %4d keys" % (f, n))
    if check:
        return 1 if problems else 0
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(["keys", "en", "vi"])
        for row in out_rows:
            w.writerow(row)
    print("wrote", os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
