"""Godot glue for the vehicles-nature area: GLB export (vertex colours, no embedded images),
.import presets, shared .tres materials (ShaderMaterial for plants, StandardMaterial3D for
vehicles) and catalog helpers.

Why no embedded images: every plant / vehicle shares a handful of atlases.  GLBs are exported with
material *names* only; the area's post-import scripts swap each named material for a shared .tres
(res://assets/models/{nature,vehicles}/materials/<name>.tres) that references the textures in
assets/textures/{nature,vehicles}/.  One copy of each texture on disk and in VRAM, batched draws.
"""
from __future__ import annotations

import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def res(path_abs: str) -> str:
    return "res://" + os.path.relpath(path_abs, ROOT).replace(os.sep, "/")


def abs_(rel: str) -> str:
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# export (bpy)
# ---------------------------------------------------------------------------
def export_glb(path: str, objects) -> str:
    import bpy
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objects:
        o.select_set(True)
        for c in o.children_recursive:
            c.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True,
        export_tangents=False, export_extras=True, export_image_format="NONE", export_cameras=False,
        export_lights=False, export_animations=False, export_vertex_color="ACTIVE",
        export_active_vertex_color_when_no_material=True, export_normals=True)
    print(f"EXPORTED {path} ({os.path.getsize(path) / 1024:.0f} KiB)")
    return path


def glb_stats(path: str) -> dict:
    import struct
    d = open(path, "rb").read()
    jl = struct.unpack_from("<I", d, 12)[0]
    js = json.loads(d[20:20 + jl])
    tris = 0
    for me in js.get("meshes", []):
        for p in me["primitives"]:
            if "indices" in p:
                tris += js["accessors"][p["indices"]]["count"] // 3
    return {"tris": tris, "materials": [m.get("name", "") for m in js.get("materials", [])],
            "bytes": os.path.getsize(path)}


# ---------------------------------------------------------------------------
# .import files
# ---------------------------------------------------------------------------
def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return '"' + v + '"'
    return str(v)


def write_import(path: str, importer: str, type_: str, params: dict) -> None:
    """Create or merge `<asset>.import` (keeps uid / remap written by Godot)."""
    imp = path + ".import"
    if os.path.exists(imp):
        txt = open(imp).read()
        m = re.search(r"^\[params\]\s*$", txt, re.M)
        if m:
            head, body = txt[:m.end()], txt[m.end():]
            lines = body.strip("\n").split("\n") if body.strip() else []
            keys = {ln.split("=", 1)[0]: i for i, ln in enumerate(lines) if "=" in ln}
            for k, v in params.items():
                ln = f"{k}={_fmt(v)}"
                if k in keys:
                    lines[keys[k]] = ln
                else:
                    lines.append(ln)
            open(imp, "w").write(head + "\n\n" + "\n".join(lines) + "\n")
            return
    with open(imp, "w") as f:
        f.write(f'[remap]\n\nimporter="{importer}"\ntype="{type_}"\n\n[params]\n\n')
        for k, v in params.items():
            f.write(f"{k}={_fmt(v)}\n")


def glb_import(path: str, area: str) -> None:
    write_import(path, "scene", "PackedScene", {
        "import_script/path": f"res://assets/models/{area}/_import/{area}_post_import.gd",
        "meshes/generate_lods": True,
        "meshes/create_shadow_meshes": True,
        "meshes/light_baking": 1,
        "meshes/ensure_tangents": True,
        "nodes/use_name_suffixes": True,
    })


def texture_import(path: str) -> None:
    p = {"compress/mode": 2, "mipmaps/generate": True, "detect_3d/compress_to": 0,
         "process/fix_alpha_border": True}
    if path.endswith("_normal.png"):
        p["compress/normal_map"] = 1
    else:
        p["compress/normal_map"] = 2
    write_import(path, "texture", "CompressedTexture2D", p)


# ---------------------------------------------------------------------------
# .tres materials
# ---------------------------------------------------------------------------
def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v)
    if isinstance(v, tuple) and len(v) in (3, 4):
        c = list(v) + ([1.0] if len(v) == 3 else [])
        return "Color(%s)" % ", ".join(f"{x:.4g}" for x in c)
    return str(v)


def write_shader_material(out: str, shader_res: str, textures: dict, params: dict) -> None:
    exts = [("Shader", shader_res)] + [("Texture2D", t) for t in textures.values()]
    lines = [f'[gd_resource type="ShaderMaterial" load_steps={len(exts) + 1} format=3]', ""]
    for i, (t, p) in enumerate(exts, start=1):
        lines.append(f'[ext_resource type="{t}" path="{p}" id="{i}"]')
    lines += ["", "[resource]", 'shader = ExtResource("1")']
    for i, k in enumerate(textures, start=2):
        lines.append(f'shader_parameter/{k} = ExtResource("{i}")')
    for k, v in params.items():
        lines.append(f"shader_parameter/{k} = {_val(v)}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("\n".join(lines) + "\n")


def write_standard_material(out: str, name: str, textures: dict, props: dict) -> None:
    """textures: {property: res_path} e.g. albedo_texture, normal_texture, orm_texture (-> ORMMaterial3D)."""
    ext = list(textures.items())
    typ = "ORMMaterial3D" if "orm_texture" in textures else "StandardMaterial3D"
    lines = [f'[gd_resource type="{typ}" load_steps={len(ext) + 1} format=3]', ""]
    for i, (_, p) in enumerate(ext, start=1):
        lines.append(f'[ext_resource type="Texture2D" path="{p}" id="{i}"]')
    lines += ["", "[resource]", f'resource_name = "{name}"']
    for i, (k, _) in enumerate(ext, start=1):
        lines.append(f'{k} = ExtResource("{i}")')
    for k, v in props.items():
        lines.append(f"{k} = {_val(v)}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("\n".join(lines) + "\n")


def to_godot(v) -> list:
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


def write_catalog(path: str, entries: list) -> None:
    """Merge entries by id into the catalog JSON (so builders can run per-asset)."""
    cur = []
    if os.path.exists(path):
        try:
            cur = json.load(open(path))
        except Exception:
            cur = []
    by = {e["id"]: e for e in cur}
    for e in entries:
        by[e["id"]] = e
    out = sorted(by.values(), key=lambda e: e["id"])
    json.dump(out, open(path, "w"), indent=1)
