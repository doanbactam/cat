#!/usr/bin/env python3
"""Write/refresh Godot .import presets for assets/textures/architecture/* (run after gen_textures /
gen_atlases, before tools/godot_import.sh). VRAM-compressed with mipmaps; *_normal.png imported as
normal maps (RGTC), *_orm.jpg with normal-map detection disabled. Existing uid/remap data is kept.
Run: python3 blender/city/write_texture_imports.py
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import city_glb as G  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
n = 0
for f in sorted(glob.glob(os.path.join(ROOT, "assets", "textures", "architecture", "*"))):
    if f.endswith((".jpg", ".png")):
        G.write_import(f, "texture", "CompressedTexture2D", G.texture_import_params(os.path.basename(f)))
        n += 1
print(f"texture import presets: {n}")
