"""Write the shared Godot materials (.tres) + texture .import presets for all nature assets.
Pure python:  python3 blender/nature/write_materials.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import nature_atlas as NA   # noqa: E402
import nature_godot as G    # noqa: E402

TEX = "res://assets/textures/nature/"
MAT = os.path.join(G.ROOT, "assets/models/nature/materials")
FOL = "res://assets/models/nature/shaders/nature_foliage.gdshader"
BARK = "res://assets/models/nature/shaders/nature_bark.gdshader"

# per-atlas look: backlight colour (light through thin leaves), strength, spec, flutter, sway, alpha cut
FOLIAGE = {
    "leaf_banyan": dict(backlight_color=(0.45, 0.6, 0.18), backlight_strength=0.7, specular_level=0.45, sway_amp=0.8),
    "leaf_flame": dict(backlight_color=(0.6, 0.7, 0.25), backlight_strength=1.0, specular_level=0.3, flutter_amp=1.4),
    "leaf_sao": dict(backlight_color=(0.45, 0.6, 0.2), backlight_strength=0.8, specular_level=0.45),
    "leaf_frangipani": dict(backlight_color=(0.55, 0.68, 0.25), backlight_strength=0.8, specular_level=0.4,
                            flutter_amp=0.6),
    "leaf_palm": dict(backlight_color=(0.6, 0.7, 0.25), backlight_strength=1.0, specular_level=0.4, sway_amp=1.2,
                      flutter_amp=1.3),
    "leaf_willow": dict(backlight_color=(0.6, 0.75, 0.3), backlight_strength=1.1, specular_level=0.3, sway_amp=1.6,
                        flutter_amp=1.5),
    "leaf_bamboo": dict(backlight_color=(0.6, 0.72, 0.28), backlight_strength=1.0, specular_level=0.35, sway_amp=1.3,
                        flutter_amp=1.5),
    "undergrowth": dict(backlight_color=(0.55, 0.65, 0.25), backlight_strength=0.9, specular_level=0.35),
}
BARKS = {
    "bark_banyan": dict(moss_amount=0.35, normal_strength=1.3, sway_amp=0.6),
    "bark_furrowed": dict(moss_amount=0.25, normal_strength=1.4),
    "bark_smooth": dict(moss_amount=0.2, normal_strength=1.0),
    "bark_palm": dict(moss_amount=0.1, normal_strength=1.2, sway_amp=1.2),
    "bamboo_culm": dict(moss_amount=0.0, normal_strength=0.8, sway_amp=1.3),
}

for atlas, params in FOLIAGE.items():
    G.write_shader_material(os.path.join(MAT, f"fol_{atlas}.tres"), FOL, {
        "albedo_tex": TEX + atlas + "_albedo.png", "normal_tex": TEX + atlas + "_normal.png",
        "orm_tex": TEX + atlas + "_orm.jpg", "trans_tex": TEX + atlas + "_trans.jpg"}, params)
for bark, params in BARKS.items():
    G.write_shader_material(os.path.join(MAT, f"{bark}.tres"), BARK, {
        "albedo_tex": TEX + bark + "_albedo.jpg", "normal_tex": TEX + bark + "_normal.png",
        "orm_tex": TEX + bark + "_orm.jpg"}, params)

texdir = os.path.join(G.ROOT, "assets/textures/nature")
for f in sorted(os.listdir(texdir)):
    if f.endswith((".png", ".jpg")):
        G.texture_import(os.path.join(texdir, f))
print("materials:", sorted(os.listdir(MAT)))
