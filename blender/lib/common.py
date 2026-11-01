"""Shared Blender 5.2 helpers for all asset generators.

OWNERSHIP: lead-owned. Asset agents must NOT edit this file; put domain helpers in
blender/lib/<domain>_*.py (e.g. cat_rig.py, city_mats.py) instead.

Usage inside a generator script (run via tools/blender_run.sh path/to/script.py):

    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
    import common as C
    C.reset_scene()
    ...
    C.export_glb(C.asset_path("models/props/bench.glb"), objects=[...])

Conventions (see CLAUDE.md "Asset contract"):
  * Blender units = meters, Z up. Godot receives Y up via the glTF exporter.
  * "Front" of every asset faces Blender -Y  ->  Godot +Z (Node3D MODEL_FRONT).
  * Origin at ground contact point (bottom centre unless the contract says otherwise).
  * Collision-only meshes are named "<name>-colonly" (box/convex: "-convcolonly").
"""
from __future__ import annotations

import math
import os
import random
from typing import Iterable, Sequence

import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# Paths / scene
# ---------------------------------------------------------------------------
def asset_path(rel: str) -> str:
    """Absolute path under the project's assets/ dir; creates parent dirs."""
    p = os.path.join(ROOT, "assets", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def qa_path(rel: str) -> str:
    """Absolute path under qa/out/ (git-ignored) for preview renders."""
    p = os.path.join(ROOT, "qa", "out", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def reset_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = 30
    return sc


def seed(n: int) -> random.Random:
    random.seed(n)
    return random.Random(n)


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link(obj: bpy.types.Object, col: bpy.types.Collection | None = None) -> bpy.types.Object:
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


def set_active(obj: bpy.types.Object) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def apply_transforms(obj: bpy.types.Object, loc=False, rot=True, scale=True) -> None:
    set_active(obj)
    bpy.ops.object.transform_apply(location=loc, rotation=rot, scale=scale)


def apply_modifiers(obj: bpy.types.Object) -> None:
    set_active(obj)
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def join(objs: Sequence[bpy.types.Object], name: str) -> bpy.types.Object:
    set_active(objs[0])
    for o in objs:
        o.select_set(True)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


def shade_smooth(obj: bpy.types.Object, angle_deg: float | None = 40.0) -> None:
    """Smooth shading; with angle -> 'Smooth by Angle' (keeps hard edges)."""
    set_active(obj)
    if angle_deg is None:
        bpy.ops.object.shade_smooth()
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle_deg))


# ---------------------------------------------------------------------------
# Mesh helpers
# ---------------------------------------------------------------------------
def mesh_from_bmesh(name: str, bm: bmesh.types.BMesh, col=None) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    return link(ob, col)


def box(name: str, size: Sequence[float], loc: Sequence[float] = (0, 0, 0), col=None,
        bevel: float = 0.0, bevel_segments: int = 2) -> bpy.types.Object:
    """Axis-aligned box; `loc` is the box's bottom-centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], (v.co.z + 0.5) * size[2]))
    ob = mesh_from_bmesh(name, bm, col)
    ob.location = loc
    if bevel > 0:
        m = ob.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = bevel_segments
        m.limit_method = "ANGLE"
        m.harden_normals = True
    return ob


def collision_box(name: str, size: Sequence[float], loc: Sequence[float] = (0, 0, 0), col=None) -> bpy.types.Object:
    """Invisible box collider. Godot import turns '-colonly' into StaticBody3D+CollisionShape3D."""
    ob = box(f"{name}-colonly", size, loc, col)
    ob.display_type = "WIRE"
    ob.hide_render = True  # never visible in preview renders (still exported)
    return ob


def uv_cube_project(obj: bpy.types.Object, scale: float = 1.0) -> None:
    """World-scale box-projection UVs (1 UV unit = 1/scale meters). Good for tiling PBR sets."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    mw = obj.matrix_world
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = mw @ l.vert.co
            if ax == 0:
                u, v = co.y, co.z
            elif ax == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            l[uv].uv = (u * scale, v * scale)
    bm.to_mesh(me)
    bm.free()


def smart_uv(obj: bpy.types.Object, angle_deg=66.0, margin=0.003) -> None:
    set_active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def principled(name: str, color=(0.8, 0.8, 0.8, 1.0), roughness=0.5, metallic=0.0,
               **inputs) -> bpy.types.Material:
    """Simple Principled BSDF material. Extra inputs by socket name, e.g. principled(..., **{"Emission Strength": 2})."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    if len(color) == 3:
        color = (*color, 1.0)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    for k, v in inputs.items():
        bsdf.inputs[k].default_value = v
    return m


def image_material(name: str, albedo: str | None = None, normal: str | None = None,
                   orm: str | None = None, roughness: str | None = None,
                   normal_strength: float = 1.0, alpha_clip: bool = False) -> bpy.types.Material:
    """Material wired from image files (exports cleanly to glTF PBR).
    orm = packed R:AO G:Roughness B:Metallic (glTF convention)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")

    def tex(path, non_color=False, y=0):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=False)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        n.location = (-700, y)
        return n

    if albedo:
        t = tex(albedo, y=300)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        if alpha_clip:
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
    if orm:
        t = tex(orm, True, y=0)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-400, 0)
        nt.links.new(t.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    elif roughness:
        t = tex(roughness, True, y=0)
        nt.links.new(t.outputs["Color"], bsdf.inputs["Roughness"])
    if normal:
        t = tex(normal, True, y=-300)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (-400, -300)
        nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def assign(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


# ---------------------------------------------------------------------------
# Baking (Cycles, CPU)
# ---------------------------------------------------------------------------
def _setup_cycles(samples: int = 16) -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples


def bake_maps(obj: bpy.types.Object, out_prefix: str, size: int = 1024,
              maps: Iterable[str] = ("albedo", "roughness", "normal"), samples: int = 8,
              margin: int = 8) -> dict:
    """Bake the object's (procedural) material into image files.

    out_prefix: absolute path prefix, e.g. assets/textures/brick/brick  -> brick_albedo.png ...
    maps: subset of albedo, roughness, metallic, normal, ao, emission.
    Returns {map_name: filepath}. Object must have UVs. Uses the first material slot.
    Albedo is baked with direct/indirect lighting disabled (pure colour).
    """
    _setup_cycles(samples)
    sc = bpy.context.scene
    mat = obj.active_material
    nt = mat.node_tree
    set_active(obj)
    results = {}
    for mname in maps:
        img = bpy.data.images.new(f"bake_{mname}", width=size, height=size, alpha=False,
                                  float_buffer=(mname == "normal"))
        if mname in ("roughness", "metallic", "normal", "ao"):
            img.colorspace_settings.name = "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        bake = sc.render.bake
        bake.margin = margin
        bake.use_clear = True
        restore = None
        if mname == "albedo":
            bake.use_pass_direct = False
            bake.use_pass_indirect = False
            bake.use_pass_color = True
            bpy.ops.object.bake(type="DIFFUSE")
        elif mname == "roughness":
            bpy.ops.object.bake(type="ROUGHNESS")
        elif mname == "normal":
            bake.normal_space = "TANGENT"
            bpy.ops.object.bake(type="NORMAL")
        elif mname == "ao":
            bpy.ops.object.bake(type="AO")
        elif mname == "emission":
            bpy.ops.object.bake(type="EMIT")
        elif mname == "metallic":
            # Bake metallic by temporarily routing it to emission.
            bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
            out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
            prev = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
            em = nt.nodes.new("ShaderNodeEmission")
            src = bsdf.inputs["Metallic"].links[0].from_socket if bsdf.inputs["Metallic"].links else None
            if src:
                nt.links.new(src, em.inputs["Color"])
            else:
                v = bsdf.inputs["Metallic"].default_value
                em.inputs["Color"].default_value = (v, v, v, 1)
            nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
            bpy.ops.object.bake(type="EMIT")
            if prev:
                nt.links.new(prev, out.inputs["Surface"])
            nt.nodes.remove(em)
        path = f"{out_prefix}_{mname}.png"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save(filepath=path)
        nt.nodes.remove(node)
        # Drop the GENERATED bake image so later loads read the saved file
        # (a generated image keeps regenerating as blank when re-used in-session).
        bpy.data.images.remove(img)
        results[mname] = path
    return results


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_glb(path: str, objects: Sequence[bpy.types.Object] | None = None,
               animations: bool = False, image_format: str = "AUTO", jpeg_quality: int = 90,
               extras: bool = True) -> str:
    """Export selection (or whole scene) to .glb with Godot-friendly options."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if objects is not None:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
            # include children (e.g. armature + skinned meshes, collision meshes)
            for c in o.children_recursive:
                c.select_set(True)
    kw = dict(
        filepath=path,
        export_format="GLB",
        use_selection=objects is not None,
        export_apply=True,
        export_yup=True,
        export_tangents=True,
        export_extras=extras,
        export_image_format=image_format,
        export_jpeg_quality=jpeg_quality,
        export_animations=animations,
        export_cameras=False,
    )
    if animations:
        kw.update(export_animation_mode="ACTIONS", export_force_sampling=True,
                  export_def_bones=True, export_optimize_animation_size=True)
    bpy.ops.export_scene.gltf(**kw)
    print(f"EXPORTED {path} ({os.path.getsize(path) / 1024:.0f} KiB)")
    return path


# ---------------------------------------------------------------------------
# Preview renders (QA)
# ---------------------------------------------------------------------------
def preview_render(path: str, target: Sequence[float] = (0, 0, 0.5), distance: float = 3.0,
                   yaw_deg: float = 35.0, pitch_deg: float = 15.0, res=(960, 720),
                   samples: int = 32, lens: float = 50.0, sun_strength: float = 4.0,
                   world_strength: float = 0.6, ground: bool = True) -> str:
    """Quick Cycles CPU turntable-style still for visual QA. Adds temp camera/lights."""
    sc = bpy.context.scene
    _setup_cycles(samples)
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    tmp = []
    cam_data = bpy.data.cameras.new("_qa_cam")
    cam_data.lens = lens
    cam = link(bpy.data.objects.new("_qa_cam", cam_data))
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    t = Vector(target)
    # camera on the front side (-Y) of the asset
    off = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch))) * distance
    cam.location = t + off
    d = (t - cam.location)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    tmp.append(cam)
    sun = link(bpy.data.objects.new("_qa_sun", bpy.data.lights.new("_qa_sun", "SUN")))
    sun.data.energy = sun_strength
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
    tmp.append(sun)
    if sc.world is None:
        sc.world = bpy.data.worlds.new("_qa_world")
    w = sc.world
    bg = next((n for n in w.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"), None)
    if bg:
        bg.inputs["Color"].default_value = (0.55, 0.65, 0.8, 1)
        bg.inputs["Strength"].default_value = world_strength
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "_qa_ground"
        assign(g, principled("_qa_ground_mat", (0.18, 0.18, 0.18, 1), 0.8))
        tmp.append(g)
    for o in sc.objects:  # colliders never render
        if "-col" in o.name or "-convcol" in o.name:
            o.hide_render = True
    sc.render.filepath = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    for o in tmp:
        bpy.data.objects.remove(o, do_unlink=True)
    print(f"PREVIEW {path}")
    return path
