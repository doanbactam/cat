"""Blender material library for the city-houses kit.

Material names (= glTF material names = Godot material names) and their meaning:
  arch_<set>     tiling PBR set from assets/textures/architecture/<set>_{albedo,normal,orm}
  arch_signs     shop-sign atlas (signs_a.jpg)            arch_signs_v  vertical signs/plates
  arch_glass     glass with interior atlas (glass_interiors.jpg), glossy
  arch_goods     shop interior goods atlas
  arch_<flat>    untextured: plastic, rubber, copper, dark, chrome, solar, lamp (emissive)
  dec_grime      alpha-blended grime/poster decals (decals_grime.png)  -> no shadows in Godot
  fol_foliage    alpha-scissor foliage cards (foliage_atlas.png)
  fol_laundry    alpha-scissor garments (laundry_atlas.png)
  lit_*          emissive at night (Godot post-import exposes them for the world to drive)
Every material multiplies Base Color by the vertex colour layer "Col" (glTF COLOR_0); the Godot
post-import script turns on vertex_color_use_as_albedo for these materials.
"""
from __future__ import annotations

import json
import os

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEX = os.path.join(ROOT, "assets", "textures", "architecture")

with open(os.path.join(TEX, "materials.json")) as _f:
    SETS = json.load(_f)
with open(os.path.join(TEX, "atlases.json")) as _f:
    ATLAS = json.load(_f)

# physical size (m) of one UV unit for box projection, per material name
FLAT_TILE = 1.0
_cache: dict[str, bpy.types.Material] = {}
IMAGE_FILES: dict[str, str] = {}  # image datablock name (stem) -> file name in TEX


def tile_m(mat_name: str) -> float:
    s = mat_name[5:] if mat_name.startswith("arch_") else mat_name
    if s in SETS:
        return SETS[s]["tile_m"]
    return FLAT_TILE


def _img(fname: str, non_color: bool) -> bpy.types.Image:
    stem = os.path.splitext(fname)[0]
    im = bpy.data.images.get(stem)
    if im is None:
        im = bpy.data.images.load(os.path.join(TEX, fname), check_existing=False)
        im.name = stem
        if non_color:
            im.colorspace_settings.name = "Non-Color"
    IMAGE_FILES[stem] = fname
    return im


def _gltf_group() -> bpy.types.NodeTree:
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def _base(name: str):
    m = bpy.data.materials.new(name)
    m.use_backface_culling = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "Col"
    vc.location = (-500, 500)
    return m, nt, bsdf, vc


def _mul_vc(nt, color_socket, vc, bsdf):
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    mix.location = (-250, 350)
    if color_socket is None:
        mix.inputs[6].default_value = (1, 1, 1, 1)
    else:
        nt.links.new(color_socket, mix.inputs[6])
    nt.links.new(vc.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])


def pbr(name: str, set_name: str, normal_strength: float = 1.0) -> bpy.types.Material:
    s = SETS[set_name]
    m, nt, bsdf, vc = _base(name)
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = _img(s["albedo"], False)
    ta.location = (-800, 400)
    _mul_vc(nt, ta.outputs["Color"], vc, bsdf)
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = _img(s["orm"], True)
    to.location = (-800, 50)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    sep.location = (-500, 50)
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = _gltf_group()
    grp.location = (0, -400)
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img(s["normal"], True)
    tn.location = (-800, -300)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal_strength
    nm.location = (-500, -300)
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def atlas_mat(name: str, fname: str, rough: float, metal: float = 0.0, alpha: str | None = None,
              emission: float = 0.0, spec: float = 0.5) -> bpy.types.Material:
    m, nt, bsdf, vc = _base(name)
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = _img(fname, False)
    ta.location = (-800, 400)
    _mul_vc(nt, ta.outputs["Color"], vc, bsdf)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Specular IOR Level"].default_value = spec
    if alpha:
        nt.links.new(ta.outputs["Alpha"], bsdf.inputs["Alpha"])
        if alpha == "BLEND":
            m.surface_render_method = "BLENDED"
        else:
            m.surface_render_method = "DITHERED"
    if emission > 0:
        nt.links.new(ta.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission
    return m


def flat(name: str, rough: float, metal: float = 0.0, emission: float = 0.0, emit_col=(1, 1, 1, 1),
         base=(1, 1, 1, 1)) -> bpy.types.Material:
    m, nt, bsdf, vc = _base(name)
    mix_src = None
    _mul_vc(nt, mix_src, vc, bsdf)
    mix = bsdf.inputs["Base Color"].links[0].from_node
    mix.inputs[6].default_value = base
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission > 0:
        bsdf.inputs["Emission Color"].default_value = emit_col
        bsdf.inputs["Emission Strength"].default_value = emission
    return m


FLATS = {
    "plastic": dict(rough=0.45),
    "plastic_matte": dict(rough=0.75),
    "rubber": dict(rough=0.62, base=(0.035, 0.035, 0.035, 1)),
    "copper": dict(rough=0.35, metal=1.0, base=(0.85, 0.5, 0.33, 1)),
    "dark": dict(rough=0.9, base=(0.025, 0.022, 0.02, 1)),
    "chrome": dict(rough=0.18, metal=1.0, base=(0.8, 0.8, 0.8, 1)),
    "solar": dict(rough=0.08, metal=0.0, base=(0.04, 0.06, 0.12, 1)),
    "glass_clear": dict(rough=0.04, base=(0.12, 0.15, 0.15, 1)),
}


def get(name: str) -> bpy.types.Material:
    """Resolve a builder material key -> Blender material (created once per scene)."""
    if name in _cache and _cache[name].name in bpy.data.materials:
        return _cache[name]
    if name in SETS:
        nstr = 1.0
        if name.startswith("plaster") or name in ("cement_render", "stucco_detail", "render_modern"):
            nstr = 1.0
        m = pbr("arch_" + name, name, nstr)
    elif name == "signs":
        m = atlas_mat("arch_signs", ATLAS["signs_a"]["file"], 0.45, spec=0.5)
    elif name == "signs_lit":
        m = atlas_mat("lit_signs", ATLAS["signs_a"]["file"], 0.3, emission=1.5)
    elif name == "signs_v":
        m = atlas_mat("arch_signs_v", ATLAS["signs_v"]["file"], 0.45)
    elif name == "glass":
        m = atlas_mat("arch_glass", ATLAS["glass_interiors"]["file"], 0.05, spec=0.6)
    elif name == "glass_lit":
        m = atlas_mat("lit_glass", ATLAS["glass_interiors"]["file"], 0.05, spec=0.6, emission=1.0)
    elif name == "goods":
        m = atlas_mat("arch_goods", ATLAS["goods_atlas"]["file"], 0.6)
    elif name == "decals":
        m = atlas_mat("dec_grime", ATLAS["decals_grime"]["file"], 0.9, alpha="BLEND")
    elif name == "foliage":
        m = atlas_mat("fol_foliage", ATLAS["foliage_atlas"]["file"], 0.7, alpha="CLIP")
        m.use_backface_culling = False
    elif name == "laundry":
        m = atlas_mat("fol_laundry", ATLAS["laundry_atlas"]["file"], 0.9, alpha="CLIP")
        m.use_backface_culling = False
    elif name == "lamp":
        m = flat("lit_lamp", 0.3, emission=4.0, emit_col=(1.0, 0.97, 0.9, 1), base=(0.9, 0.9, 0.9, 1))
    elif name in FLATS:
        m = flat("arch_" + name, **FLATS[name])
    else:
        raise KeyError(f"unknown material key {name}")
    _cache[name] = m
    return m


def atlas_cell(atlas: str, cell: str) -> list[float]:
    return ATLAS[atlas]["cells"][cell]


def reset_cache() -> None:
    _cache.clear()
