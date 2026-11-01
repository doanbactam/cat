"""Configure Godot import options for the cat asset (run with system python3 after an
initial tools/godot_import.sh, then re-run the import):
  * cat.glb: loop_mode=LINEAR on looping clips (so gameplay code need not set it)
  * colour textures: VRAM compressed + mipmaps; normal maps: normal-map compression;
    fur mask / fur flow (data): lossless + mipmaps (no block-compression artefacts)
Usage: python3 blender/cat/configure_import.py"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAT = os.path.join(ROOT, "assets", "models", "cat")
sys.path.insert(0, os.path.join(ROOT, "blender", "lib"))
LOOPING = ["idle", "idle_look", "walk", "trot", "run", "sneak", "sneak_idle", "fall", "sit_idle", "sleep", "groom",
           "scratch", "climb", "drink", "eat", "knead", "balance_walk"]


def set_params(path, params):
    s = open(path).read()
    for k, v in params.items():
        pat = re.compile(r"^" + re.escape(k) + r"=.*$", re.M)
        if pat.search(s):
            s = pat.sub(f"{k}={v}", s)
        else:
            s = s.replace("[params]\n", f"[params]\n\n{k}={v}\n", 1)
    open(path, "w").write(s)


def glb():
    p = os.path.join(CAT, "cat.glb.import")
    entries = []
    for a in LOOPING:
        entries.append(f'"{a}": {{\n"save_to_file/enabled": false,\n"save_to_file/keep_custom_tracks": "",\n'
                       f'"save_to_file/path": "",\n"settings/loop_mode": 1,\n"slices/amount": 0\n}}')
    sub = '{\n"animations": {\n' + ",\n".join(entries) + "\n}\n}"
    s = open(p).read()
    s = re.sub(r"^_subresources=\{.*?^\}$|^_subresources=\{\}$", "_subresources=" + sub, s, flags=re.M | re.S)
    open(p, "w").write(s)


def textures():
    for d in (CAT, os.path.join(CAT, "textures")):
        for f in os.listdir(d):
            if not f.endswith(".import") or f.startswith("cat.glb"):
                continue
            path = os.path.join(d, f)
            name = f[:-7]
            if "fur_mask" in name or "fur_flow" in name:
                prm = {"compress/mode": 0, "mipmaps/generate": "true", "detect_3d/compress_to": 0}
            elif "normal" in name:
                prm = {"compress/mode": 2, "compress/normal_map": 1, "mipmaps/generate": "true", "detect_3d/compress_to": 0}
            elif "whiskers" in name:
                prm = {"compress/mode": 0, "mipmaps/generate": "true", "detect_3d/compress_to": 0,
                       "process/fix_alpha_border": "true"}
            else:
                prm = {"compress/mode": 2, "compress/high_quality": "true", "mipmaps/generate": "true",
                       "detect_3d/compress_to": 0}
            set_params(path, prm)


if __name__ == "__main__":
    glb()
    textures()
    print("configured")
