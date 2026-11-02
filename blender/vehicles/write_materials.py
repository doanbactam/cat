"""Write the shared Godot StandardMaterial3D .tres files for every veh_* material + texture .import presets.
Pure python:  python3 blender/vehicles/write_materials.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import nature_godot as G      # noqa: E402

T = "res://assets/textures/vehicles/"
OUT = os.path.join(G.ROOT, "assets/models/vehicles/materials")

# keep in sync with blender/lib/vehicles_lib.py (PAINTS / SPECS / LIGHTS); duplicated here so this
# script runs without Blender.
PAINTS = {
    "red": (0.55, 0.04, 0.035), "maroon": (0.25, 0.03, 0.03), "white": (0.82, 0.82, 0.8),
    "black": (0.025, 0.025, 0.028), "blue": (0.05, 0.16, 0.42), "teal": (0.05, 0.32, 0.32),
    "green": (0.07, 0.36, 0.2), "cream": (0.78, 0.7, 0.52), "silver": (0.5, 0.52, 0.54),
    "yellow": (0.85, 0.6, 0.06), "sky": (0.32, 0.55, 0.72), "grey": (0.32, 0.33, 0.34),
    "olive": (0.25, 0.3, 0.16),
}
SPECS = {
    "veh_chrome": ("veh_metal", (0.9, 0.9, 0.9), 0.5, 1.0),
    "veh_alloy": ("veh_metal", (0.62, 0.63, 0.64), 1.2, 1.0),
    "veh_steel_dark": ("veh_metal", (0.12, 0.12, 0.13), 2.2, 0.85),
    "veh_rubber": ("veh_rubber", (1.0, 1.0, 1.0), 1.0, 0.0),
    "veh_plastic_black": ("veh_plastic", (0.035, 0.035, 0.037), 1.0, 0.0),
    "veh_plastic_grey": ("veh_plastic", (0.2, 0.2, 0.21), 1.0, 0.0),
    "veh_vinyl_black": ("veh_vinyl", (0.04, 0.035, 0.035), 1.0, 0.0),
    "veh_vinyl_red": ("veh_vinyl", (0.32, 0.04, 0.035), 1.0, 0.0),
    "veh_vinyl_brown": ("veh_vinyl", (0.22, 0.12, 0.06), 1.0, 0.0),
    "veh_rust": ("veh_rust", (0.18, 0.2, 0.22), 1.0, 0.25),
    "veh_rust_green": ("veh_rust", (0.12, 0.25, 0.18), 1.0, 0.25),
    "veh_wood": ("veh_wood", (1.0, 1.0, 1.0), 1.0, 0.0),
    "veh_fabric_black": ("veh_fabric", (0.05, 0.05, 0.055), 1.0, 0.0),
    "veh_fabric_blue": ("veh_fabric", (0.12, 0.2, 0.35), 1.0, 0.0),
    "veh_fabric_sack": ("veh_fabric", (0.42, 0.34, 0.22), 1.0, 0.0),
    "veh_engine": ("veh_metal", (0.32, 0.32, 0.33), 2.6, 0.7),
}
LIGHTS = {"veh_light_head": (0.95, 0.95, 0.9), "veh_light_tail": (0.55, 0.02, 0.02),
          "veh_light_amber": (0.9, 0.42, 0.04)}


def tex(ts):
    return {"albedo_texture": T + ts + "_albedo.jpg", "normal_texture": T + ts + "_normal.png",
            "orm_texture": T + ts + "_orm.jpg"}


def lin(c):
    """Colours above are linear (Blender); Godot albedo_color is sRGB."""
    def f(x):
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return tuple(round(f(x), 4) for x in c[:3]) + tuple(c[3:])


BASE = {"vertex_color_use_as_albedo": True, "normal_enabled": True, "texture_filter": 5,
        "uv1_triplanar": False}
for col, rgb in PAINTS.items():
    p = dict(BASE)
    p.update({"albedo_color": lin(rgb), "metallic": 0.0, "roughness": 1.0, "metallic_specular": 0.5,
              "clearcoat_enabled": True, "clearcoat": 1.0, "clearcoat_roughness": 0.06, "normal_scale": 0.5})
    G.write_standard_material(os.path.join(OUT, f"veh_paint_{col}.tres"), f"veh_paint_{col}", tex("veh_paint"), p)
for name, (ts, rgb, rs, mt) in SPECS.items():
    p = dict(BASE)
    p.update({"albedo_color": lin(rgb), "metallic": mt, "roughness": min(1.0, rs), "normal_scale": 0.7})
    G.write_standard_material(os.path.join(OUT, f"{name}.tres"), name, tex(ts), p)
for name, rgb in LIGHTS.items():
    G.write_standard_material(os.path.join(OUT, f"{name}.tres"), name, {}, {
        "albedo_color": lin(rgb), "roughness": 0.08, "metallic_specular": 0.8, "emission_enabled": True,
        "emission": lin(rgb), "emission_energy_multiplier": 0.0, "rim_enabled": False})
G.write_standard_material(os.path.join(OUT, "veh_glass.tres"), "veh_glass", {}, {
    "transparency": 1, "albedo_color": (0.03, 0.045, 0.05, 0.72), "roughness": 0.05, "metallic_specular": 0.7,
    "cull_mode": 0})
G.write_standard_material(os.path.join(OUT, "veh_mirror.tres"), "veh_mirror", {}, {
    "albedo_color": (0.9, 0.9, 0.9), "metallic": 1.0, "roughness": 0.03})
G.write_standard_material(os.path.join(OUT, "veh_decals.tres"), "veh_decals",
                          {"albedo_texture": T + "veh_decals_albedo.png"}, {
                              "transparency": 2, "alpha_scissor_threshold": 0.5, "roughness": 0.45,
                              "texture_filter": 5})
texdir = os.path.join(G.ROOT, "assets/textures/vehicles")
for f in sorted(os.listdir(texdir)):
    if f.endswith((".png", ".jpg")):
        G.texture_import(os.path.join(texdir, f))
print(len(os.listdir(OUT)), "materials")
