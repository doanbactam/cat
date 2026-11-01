"""Build the street-props kit: every registered prop -> assets/models/props/<id>.glb + catalog.json.

Usage:
  python3 blender/props/gen_labels.py                     # label sheets (Pillow, once / after text edits)
  tools/blender_run.sh blender/props/build_props.py [-- --only id1,id2 | --category street,item
                                                        | --from id | --list] [--preview]
  tools/godot_import.sh && tools/run_tests.sh street_props
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)

import props_bake as PB  # noqa: E402

# prop definition modules (each registers its props into PB.REG on import)
import p_street  # noqa: E402,F401
import p_utility  # noqa: E402,F401
import p_stall  # noqa: E402,F401
import p_home  # noqa: E402,F401
import p_festival  # noqa: E402,F401
import p_clutter  # noqa: E402,F401
import p_items  # noqa: E402,F401


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ids = list(PB.REG.keys())
    preview = "--preview" in argv
    if "--list" in argv:
        for k, v in PB.REG.items():
            print(f"{v['category']:10s} {k}")
        print(f"TOTAL {len(PB.REG)}")
        return
    if "--only" in argv:
        want = argv[argv.index("--only") + 1].split(",")
        ids = [i for i in ids if any(i == w or (w.endswith("*") and i.startswith(w[:-1])) for w in want)]
    if "--category" in argv:
        cats = argv[argv.index("--category") + 1].split(",")
        ids = [i for i in ids if PB.REG[i]["category"] in cats]
    if "--from" in argv:
        start = argv[argv.index("--from") + 1]
        ids = ids[ids.index(start):]
    if "--missing" in argv:
        ids = [i for i in ids if not os.path.exists(os.path.join(PB.MODEL_DIR, PB.REG[i]["file"]))]
    print(f"BUILDING {len(ids)} props: {ids}")
    ok, bad = PB.run(ids, preview=preview)
    if bad:
        sys.exit(1)


main()
