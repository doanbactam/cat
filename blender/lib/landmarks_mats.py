"""Material resolver for the landmark kit (Blender 5.2).

Builder material keys -> Blender materials (names become glTF / Godot material names):
  <arch set>        e.g. "plaster_white", "roof_tile_old"   -> arch_<set>   (assets/textures/architecture, read-only)
  "lm:<set>"        e.g. "lm:lacquer_red", "lm:bluestone"   -> lm_<set>     (assets/textures/landmarks)
  "atlas"           landmark atlas, opaque, with carved normal map  -> lm_atlas
  "atlas_cut"       same atlas, alpha-scissor (nest twigs, leaves)   -> fol_lm_atlas
  "atlas_lit"       same atlas, emissive at night (signs, menus)     -> lit_lm_atlas
  "glass_jar"       translucent glass (jars, café glazing)           -> dec_lm_glass  (alpha blend)
  "water"           dark still water in basins / buckets             -> lm_water
  "ceramic"         white/celadon glazed ceramics (teapots, cups)    -> lm_ceramic
  "lamp_globe"      opal globe, emissive at night                    -> lit_lm_globe
  "bulb"            bare warm bulb, emissive at night                -> lit_lm_bulb
  "candle"          red electric candle / altar lamp, always on      -> lit_lamp
  city keys         "signs", "glass", "foliage", "decals", "plastic", "chrome", ... via city_mats
Every material multiplies Base Color by the vertex colour "Col" (tint + baked grime), like the
city kit, so the same post-import rules apply (vertex_color_use_as_albedo).
IMAGE_FILES maps image datablock name -> path relative to assets/textures/ ("architecture/x.jpg"),
used by city_glb.postprocess(tex_rel="../../textures") to reference shared files by URI.
"""
from __future__ import annotations

import json
import os

import bpy

import city_mats as CM

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEX_LM = os.path.join(ROOT, "assets", "textures", "landmarks")

with open(os.path.join(TEX_LM, "materials.json")) as _f:
    LM_SETS = json.load(_f)
with open(os.path.join(TEX_LM, "atlas.json")) as _f:
    ATLAS = json.load(_f)

_cache: dict[str, bpy.types.Material] = {}
IMAGE_FILES: dict[str, str] = {}


def tile_m(key: str) -> float:
    if key.startswith("lm:"):
        return LM_SETS[key[3:]]["tile_m"]
    return CM.tile_m(key)


def _img_lm(fname: str, non_color: bool) -> bpy.types.Image:
    stem = "lm__" + os.path.splitext(fname)[0]
    im = bpy.data.images.get(stem)
    if im is None:
        im = bpy.data.images.load(os.path.join(TEX_LM, fname), check_existing=False)
        im.name = stem
        if non_color:
            im.colorspace_settings.name = "Non-Color"
    IMAGE_FILES[os.path.splitext(fname)[0]] = "landmarks/" + fname
    return im


def _pbr_lm(name: str, set_name: str, normal_strength: float = 1.0) -> bpy.types.Material:
    s = LM_SETS[set_name]
    m, nt, bsdf, vc = CM._base(name)
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = _img_lm(s["albedo"], False)
    CM._mul_vc(nt, ta.outputs["Color"], vc, bsdf)
    to = nt.nodes.new("ShaderNodeTexImage")
    to.image = _img_lm(s["orm"], True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = CM._gltf_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img_lm(s["normal"], True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal_strength
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _atlas(name: str, alpha: str | None = None, emission: float = 0.0, rough: float = 0.6) -> bpy.types.Material:
    m, nt, bsdf, vc = CM._base(name)
    ta = nt.nodes.new("ShaderNodeTexImage")
    ta.image = _img_lm(ATLAS["file"], False)
    CM._mul_vc(nt, ta.outputs["Color"], vc, bsdf)
    bsdf.inputs["Roughness"].default_value = rough
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img_lm(ATLAS["normal"], True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if alpha:
        nt.links.new(ta.outputs["Alpha"], bsdf.inputs["Alpha"])
        m.surface_render_method = "DITHERED"
        m.use_backface_culling = False
    if emission > 0:
        nt.links.new(ta.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission
    return m


def _flat_alpha(name: str, base, alpha: float, rough: float) -> bpy.types.Material:
    m = CM.flat(name, rough, base=base)
    bsdf = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Specular IOR Level"].default_value = 0.7
    m.surface_render_method = "BLENDED"
    return m


def get(key: str) -> bpy.types.Material:
    if key in _cache and _cache[key].name in bpy.data.materials:
        return _cache[key]
    if key.startswith("lm:"):
        m = _pbr_lm("lm_" + key[3:], key[3:])
    elif key == "atlas":
        m = _atlas("lm_atlas", rough=0.55)
    elif key == "atlas_cut":
        m = _atlas("fol_lm_atlas", alpha="CLIP", rough=0.85)
    elif key == "atlas_lit":
        m = _atlas("lit_lm_atlas", emission=1.2, rough=0.4)
    elif key == "glass_jar":
        m = _flat_alpha("dec_lm_glass", (0.82, 0.88, 0.86, 1), 0.22, 0.05)
    elif key == "water":
        m = CM.flat("lm_water", 0.04, base=(0.06, 0.075, 0.06, 1))
    elif key == "ceramic":
        m = CM.flat("lm_ceramic", 0.12, base=(0.86, 0.86, 0.82, 1))
    elif key == "lamp_globe":
        m = CM.flat("lit_lm_globe", 0.3, emission=3.0, emit_col=(1.0, 0.86, 0.62, 1), base=(0.88, 0.86, 0.8, 1))
    elif key == "bulb":
        m = CM.flat("lit_lm_bulb", 0.2, emission=5.0, emit_col=(1.0, 0.8, 0.5, 1), base=(0.95, 0.9, 0.8, 1))
    elif key == "candle":
        m = CM.flat("lit_lamp", 0.3, emission=3.0, emit_col=(1.0, 0.25, 0.12, 1), base=(0.8, 0.12, 0.08, 1))
    else:
        m = CM.get(key)
        # register city images with their architecture/ prefix
        for st, fn in CM.IMAGE_FILES.items():
            IMAGE_FILES[st] = "architecture/" + fn
    _cache[key] = m
    return m


def cell(name: str) -> list[float]:
    return ATLAS["cells"][name]


def reset() -> None:
    _cache.clear()
    IMAGE_FILES.clear()
    CM.reset_cache()
    CM.IMAGE_FILES.clear()
