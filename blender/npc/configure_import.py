"""Post-build step for the creature GLBs (run with system python3 AFTER tools/godot_import.sh created the
.import files, then run tools/godot_import.sh again):
  * sets loop_mode=LINEAR on every looping clip (so gameplay code need not set it)
  * writes assets/models/npc/catalog.json (id, file, kind, height, tris, clips, speeds)
Usage: python3 blender/npc/configure_import.py"""
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NPC = os.path.join(ROOT, "assets", "models", "npc")
TEX = os.path.join(ROOT, "qa", "out", "creatures", "tex")
HUMAN_CLIPS = ["idle", "walk", "sit", "talk", "sell", "pet_cat", "shoo", "look_around", "carry", "phone"]
CLIPS = {
    "dog": ["idle", "walk", "run", "bark", "sleep", "sniff", "growl"],
    "mouse": ["idle", "run"], "gecko": ["idle", "run"],
    "pigeon": ["idle", "peck", "walk", "fly", "takeoff", "land"],
    "crow": ["idle", "peck", "walk", "fly", "takeoff", "land", "caw", "hop"],
    "sparrow": ["idle", "peck", "walk", "fly", "takeoff", "land"],
    "koi": ["swim", "idle"],
}
NON_LOOPING = {"takeoff", "land", "bark", "caw", "hop"}
KIND = {"dog": "dog", "mouse": "mouse", "gecko": "gecko", "pigeon": "pigeon", "crow": "crow", "sparrow": "sparrow",
        "koi": "koi"}
NPC_ID = {"ba_tu": "ba_tu", "co_hoa": "co_hoa", "chu_sau": "chu_sau", "bin": "bin", "dog": "ven", "crow": "lao_qua",
          "pigeon": "xam"}


def clips_for(gid):
    return CLIPS.get(gid, HUMAN_CLIPS)


def configure(gid):
    p = os.path.join(NPC, gid + ".glb.import")
    if not os.path.exists(p):
        print("no import file yet:", p)
        return
    entries = []
    for a in clips_for(gid):
        if a in NON_LOOPING:
            continue
        entries.append(f'"{a}": {{\n"save_to_file/enabled": false,\n"save_to_file/keep_custom_tracks": "",\n'
                       f'"save_to_file/path": "",\n"settings/loop_mode": 1,\n"slices/amount": 0\n}}')
    sub = '{\n"animations": {\n' + ",\n".join(entries) + "\n}\n}"
    s = open(p).read()
    s = re.sub(r"^_subresources=\{.*?^\}$|^_subresources=\{\}$", "_subresources=" + sub, s, flags=re.M | re.S)
    open(p, "w").write(s)


def main():
    cat = []
    for f in sorted(os.listdir(NPC)):
        if not f.endswith(".glb"):
            continue
        gid = f[:-4]
        configure(gid)
        meta = {}
        mp = os.path.join(TEX, gid + "_meta.json")
        if os.path.exists(mp):
            meta = json.load(open(mp))
        human = gid not in CLIPS
        e = {"id": gid, "file": f"res://assets/models/npc/{gid}.glb",
             "kind": "human" if human else KIND[gid],
             "npc_id": NPC_ID.get(gid, ""),
             "role": "named" if gid in NPC_ID else ("pedestrian" if gid.startswith("ped_") else "ambient"),
             "clips": clips_for(gid),
             "looping": [c for c in clips_for(gid) if c not in NON_LOOPING],
             "skeleton": "Armature/Skeleton3D", "front": "+Z", "origin": "ground contact, bottom centre"}
        for k in ("height", "tris", "walk_speed", "speeds", "swim_speed", "flight_wings"):
            if k in meta:
                e[k] = meta[k]
        cat.append(e)
    with open(os.path.join(NPC, "catalog.json"), "w") as fh:
        json.dump(cat, fh, indent=1, ensure_ascii=False)
    print(f"configured {len(cat)} models")


if __name__ == "__main__":
    main()
