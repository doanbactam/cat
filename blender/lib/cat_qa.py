"""Studio QA renders for the cat (Cycles CPU): orthographic proportion views,
perspective beauty views and close-ups. Keeps render settings small for iteration."""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

import common as C

VIEWS = {
    # name: (target, direction-from-target (unit-ish), distance, ortho_scale or None, lens)
    "side": ((0, 0.02, 0.15), (1, 0, 0.0), 1.2, 0.80, 50),
    "front": ((0, 0, 0.16), (0, -1, 0.0), 1.2, 0.56, 50),
    "top": ((0, 0.13, 0.1), (0, 0, 1), 1.2, 0.84, 50),
    "back": ((0, 0, 0.15), (0, 1, 0.08), 1.2, 0.40, 50),
    "q_front": ((0, -0.02, 0.15), (0.75, -0.85, 0.32), 1.25, None, 50),
    "q_back": ((0, 0.06, 0.14), (-0.8, 0.9, 0.45), 1.35, None, 50),
    "face": ((0, -0.20, 0.235), (0.35, -1, 0.12), 0.32, None, 60),
    "face_side": ((0, -0.19, 0.235), (1, -0.15, 0.05), 0.32, None, 60),
    "hf_front": ((0, -0.215, 0.255), (0.0, -1, 0.05), 0.5, 0.15, 50),
    "hf_side": ((0, -0.200, 0.250), (1, -0.12, -0.12), 0.5, 0.15, 50),
    "hf_q": ((0, -0.205, 0.255), (0.75, -0.9, 0.25), 0.36, None, 60),
    "hf_low": ((0, -0.21, 0.24), (-0.4, -1, -0.25), 0.33, None, 60),
    "eye_close": ((0.022, -0.226, 0.263), (0.45, -1, 0.15), 0.12, None, 60),
    # head close-ups for the polished head (world landmarks: nose ~(0,-0.236,0.269), eye ~(0.019,-0.205,0.282))
    "hd_front": ((0, -0.215, 0.282), (0.0, -1, 0.04), 0.5, 0.125, 50),
    "hd_side": ((0, -0.200, 0.280), (1, 0.0, 0.0), 0.5, 0.135, 50),
    "hd_q": ((0, -0.208, 0.278), (0.75, -0.9, 0.18), 0.30, None, 60),
    "hd_eye": ((0.019, -0.212, 0.281), (0.40, -1, 0.10), 0.105, None, 60),
    "hd_low": ((0, -0.22, 0.262), (0.30, -1, -0.30), 0.28, None, 60),
    "hd_mouth": ((0, -0.232, 0.258), (0.35, -1, 0.0), 0.11, None, 60),
    "paws": ((0.0, -0.05, 0.03), (0.5, -1, 0.35), 0.62, None, 50),
    "under": ((0, 0.0, 0.10), (0.6, -0.5, -0.35), 0.75, None, 40),
}


def clay(name="_clay", color=(0.55, 0.52, 0.50, 1.0), rough=0.55):
    return C.principled(name, color, rough)


def studio(world_strength: float = 0.35, grid_ground: bool = True):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("_qa_world")
    bg = next((n for n in sc.world.node_tree.nodes if n.bl_idname == "ShaderNodeBackground"), None)
    bg.inputs["Color"].default_value = (0.42, 0.45, 0.5, 1)
    bg.inputs["Strength"].default_value = world_strength
    objs = []

    def area(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        ob = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(ob)
        ob.location = loc
        d = Vector((0, 0, 0.15)) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        objs.append(ob)

    area("_key", (0.9, -1.1, 1.3), 42, 0.8, (1.0, 0.95, 0.88))
    area("_fill", (-1.2, -0.6, 0.6), 12, 1.2, (0.85, 0.9, 1.0))
    area("_rim", (-0.3, 1.3, 0.9), 30, 0.6, (1.0, 0.97, 0.92))
    if grid_ground:
        bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0))
        g = bpy.context.active_object
        g.name = "_qa_ground"
        m = bpy.data.materials.new("_qa_grid")
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        chk = nt.nodes.new("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 6 / 0.05 / 2  # 5 cm squares over 6 m plane
        chk.inputs["Color1"].default_value = (0.30, 0.30, 0.30, 1)
        chk.inputs["Color2"].default_value = (0.24, 0.24, 0.24, 1)
        nt.links.new(tc.outputs["UV"], chk.inputs["Vector"])
        nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.8
        g.data.materials.append(m)
        objs.append(g)
    return objs


def camera_for(view: str, res=(640, 400)):
    sc = bpy.context.scene
    target, direction, dist, ortho, lens = VIEWS[view]
    cd = bpy.data.cameras.get("_qa_cam") or bpy.data.cameras.new("_qa_cam")
    cam = bpy.data.objects.get("_qa_cam") or bpy.data.objects.new("_qa_cam", cd)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    t = Vector(target)
    dvec = Vector(direction).normalized()
    cam.location = t + dvec * dist
    up = "Y" if abs(dvec.z) < 0.99 else "Y"
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", up).to_euler()
    if abs(dvec.z) > 0.99:
        cam.rotation_euler = (0, 0, math.pi / 2)
        cam.location = t + Vector((0, 0, dist))
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.type = "PERSP"
        cd.lens = lens
    cd.clip_start = 0.01
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    return cam


def render(path: str, samples: int = 24):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.filepath = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    return path


def render_views(prefix: str, views=("side", "front", "top", "q_front", "q_back", "face"), res=(640, 400),
                 samples: int = 20):
    out = []
    for v in views:
        camera_for(v, res)
        out.append(render(f"{prefix}_{v}.png", samples))
    return out
