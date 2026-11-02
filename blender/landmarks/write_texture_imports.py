#!/usr/bin/env python3
"""Write/refresh Godot .import presets for assets/textures/landmarks/* (run after gen_textures.py /
gen_atlas.py, before tools/godot_import.sh). Same presets as the city kit: VRAM-compressed with mipmaps,
*_normal.png as normal maps (RGTC), *_orm.jpg without normal-map detection. Keeps existing uid/remap.
Run: python3 blender/landmarks/write_texture_imports.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import city_glb as G  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
n = 0
for f in sorted(glob.glob(os.path.join(ROOT, "assets", "textures", "landmarks", "*"))):
    if f.endswith((".jpg", ".png")):
        G.write_import(f, "texture", "CompressedTexture2D", G.texture_import_params(os.path.basename(f)))
        n += 1
print(f"texture import presets: {n}")
