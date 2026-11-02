"""Landmark kit generator (Blender 5.2, headless).

Run:   tools/blender_run.sh blender/landmarks/build_landmarks.py [-- --only id1,id2] [--preview [all]] [--no-export]
Needs: python3 blender/landmarks/gen_textures.py && python3 blender/landmarks/gen_atlas.py
       (+ the city-houses texture library in assets/textures/architecture/, used read-only)
Out:   assets/models/landmarks/<id>.glb (+ .import with the post-import script)
       assets/models/landmarks/catalog.json
       qa/out/city-landmarks/<id>[_n].png with --preview
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import landmarks_kit as K  # noqa: E402
import landmarks_mats as LM  # noqa: E402
import importlib  # noqa: E402


def V3(t, d, yaw, pitch, res=(800, 600), samples=24, lens=35, sun=4.5, world=0.8, ground=True):
    return dict(target=t, distance=d, yaw_deg=yaw, pitch_deg=pitch, res=res, samples=samples, lens=lens,
                sun_strength=sun, world_strength=world, ground=ground)


SPECS = [
    dict(id="dinh_hang_may", builder="lm_temple:build", seed=101, width=26.0, depth=37.2, style="temple",
         category="temple", origin="street-front centre of the tam quan gate, ground level; complex extends to -Z",
         views=[V3((0, 14, 3), 40, 28, 22), V3((0, 28, 7), 16, 150, 30), V3((0, 4, 2.5), 13, 20, 6),
                V3((2, 28, 9), 5, 30, 25)]),
    dict(id="cho_market_hall", builder="lm_market:build_hall", seed=201, width=24.6, depth=18.6, style="market",
         category="market", views=[V3((0, 9, 3), 30, 30, 18), V3((0, 9, 1.5), 9, 10, 8)]),
    dict(id="cho_stall_lane", builder="lm_market:build_lane", seed=202, width=12.0, depth=3.2, style="market",
         category="market", views=[V3((0, 1.2, 1.2), 10, 25, 12)]),
    dict(id="cho_gate_arch", builder="lm_market:build_gate", seed=203, width=9.0, depth=0.8, style="market",
         category="market", origin="centre of the arch at street level; road passes along Z",
         views=[V3((0, 0, 3), 13, 20, 8)]),
    dict(id="ho_embank_straight_4m", builder="lm_lake:build_straight", seed=301, width=4.0, depth=3.0, style="lake",
         category="lake", origin="top of the water-side edge at walkway level; water toward +Z, water level -1.0",
         views=[V3((0, 0, -0.6), 7, 30, 15, ground=False)]),
    dict(id="ho_embank_curve_30", builder="lm_lake:build_curve", seed=302, width=4.2, depth=3.0, style="lake",
         category="lake", origin="midpoint of the arc on the water-side edge at walkway level; arc radius 8 m",
         views=[V3((0, 0, -0.6), 8, 30, 18, ground=False)]),
    dict(id="ho_embank_steps_4m", builder="lm_lake:build_steps", seed=303, width=4.0, depth=3.0, style="lake",
         category="lake", origin="top of the water-side edge at walkway level; water toward +Z",
         views=[V3((0, -0.5, -0.6), 7, 25, 22, ground=False)]),
    dict(id="ho_railing_4m", builder="lm_lake:build_railing", seed=304, width=4.0, depth=0.3, style="lake",
         category="lake", origin="same as the embankment pieces (place on top of them)",
         views=[V3((0, 0.3, 0.4), 4, 25, 12, ground=False)]),
    dict(id="ho_bridge", builder="lm_lake:build_bridge", seed=305, width=3.4, depth=16.0, style="lake",
         category="lake", origin="bridge midpoint at walkway level; spans Z -8..8, water level -1.0",
         views=[V3((0, 0, 0.5), 20, 70, 12, ground=False), V3((0, -6, 1), 6, 15, 10, ground=False)]),
    dict(id="ho_islet_shrine", builder="lm_lake:build_islet", seed=306, width=9.0, depth=7.0, style="lake",
         category="lake", origin="islet centre at ground level (+0.0 = walkway level), water level -1.0",
         views=[V3((0, 0, 1), 13, 30, 20, ground=False)]),
    dict(id="ho_lamp_post", builder="lm_lake:build_lamp", seed=307, width=0.8, depth=0.8, style="lake",
         category="lake", origin="post base centre", views=[V3((0, 0, 2.0), 6, 25, 5, res=(480, 720))]),
    dict(id="ho_bench", builder="lm_lake:build_bench", seed=308, width=1.8, depth=0.7, style="lake",
         category="lake", origin="bench front-centre on the ground", views=[V3((0, 0.2, 0.4), 3.2, 30, 15)]),
    dict(id="shrine_wall_box", builder="lm_small:build_wall_shrine", seed=401, width=0.6, depth=0.45, style="temple",
         category="shrine", kind="roof_prop", origin="bottom-back centre (mount on a wall face, front = +Z)",
         views=[V3((0, -0.2, 0.4), 1.6, 25, 10)]),
    dict(id="shrine_tree", builder="lm_small:build_tree_shrine", seed=402, width=0.7, depth=0.7, style="temple",
         category="shrine", kind="roof_prop", origin="post base centre",
         views=[V3((0, 0, 1.0), 3.0, 25, 10, res=(480, 720))]),
    dict(id="cafe_bong", builder="lm_small:build_cafe", seed=501, width=6.0, depth=10.0, style="modern",
         category="shop", kind="shop", views=[V3((0, -1, 3.4), 14, 22, 8, res=(720, 900)), V3((0, -1, 1), 5, 15, 6)]),
    dict(id="quan_tra_ba_tu", builder="lm_small:build_tea_stall", seed=502, width=4.0, depth=2.8, style="old_tile",
         category="shop", kind="shop",
         origin="front-centre on the sidewalk; the stall leans against a wall at +2.8 m behind (Godot -Z)",
         views=[V3((0, 1.2, 1.0), 6, 25, 12), V3((0.3, 1.5, 0.4), 2.4, 15, 10)]),
]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--preview", nargs="?", const="front", default=None)
    ap.add_argument("--no-export", action="store_true")
    a = ap.parse_args([x for x in argv if x != "--"])
    only = [s for s in a.only.split(",") if s]
    cat_path = os.path.join(K.OUT_DIR, "catalog.json")
    catalog = {}
    if os.path.exists(cat_path):
        for e in json.load(open(cat_path)):
            catalog[e["id"]] = e
    for spec in SPECS:
        if only and not any(spec["id"] == o or spec["id"].startswith(o) for o in only):
            continue
        t0 = time.time()
        C.reset_scene()
        LM.reset()
        mod, fn = spec["builder"].split(":")
        ctx, info = getattr(importlib.import_module(mod), fn)(spec)
        entry = K.finish_and_export(spec, ctx, info, a.preview, not a.no_export, spec.get("views"))
        catalog[spec["id"]] = entry
        print(f"MODULE {spec['id']}: tris={entry['tris']} cols={entry['colliders']} nap={len(entry['nap_spots'])} "
              f"climb={len(entry['climb_points'])} {time.time() - t0:.1f}s", flush=True)
    ids = [s["id"] for s in SPECS]
    out = [catalog[i] for i in ids if i in catalog]
    if not a.no_export:
        with open(cat_path, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        print(f"CATALOG {cat_path} ({len(out)} modules)")


if __name__ == "__main__":
    main()
