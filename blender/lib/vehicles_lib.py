"""Hard-surface building blocks for the vehicles of Mèo Cam (Blender 5.2, bmesh).

Conventions: vehicle length along Blender Y with the FRONT toward -Y (-> Godot +Z), X = right side,
Z up, origin on the ground at the centre of the wheelbase.  Wheels are separate objects whose
origin is the hub centre and whose spin axis is local X (Godot X).  Everything else is joined into
one `body` mesh with a handful of shared materials (veh_*), which the post-import script swaps for
the shared Godot .tres materials (assets/models/vehicles/materials/).

Wear is baked into a float vertex-colour attribute "vc" (multiplied into albedo in Godot):
ray-traced ambient occlusion, mud/road dust rising from the wheels and the underside, grime in
cavities.  That is why bodies are moderately subdivided (enough vertices to carry the gradients).
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import common as C

TEX = "textures/vehicles"

# ---------------------------------------------------------------------------
# materials
# ---------------------------------------------------------------------------
PAINTS = {
    "red": (0.55, 0.04, 0.035), "maroon": (0.25, 0.03, 0.03), "white": (0.82, 0.82, 0.8),
    "black": (0.025, 0.025, 0.028), "blue": (0.05, 0.16, 0.42), "teal": (0.05, 0.32, 0.32),
    "green": (0.07, 0.36, 0.2), "cream": (0.78, 0.7, 0.52), "silver": (0.5, 0.52, 0.54),
    "yellow": (0.85, 0.6, 0.06), "sky": (0.32, 0.55, 0.72), "grey": (0.32, 0.33, 0.34),
    "olive": (0.25, 0.3, 0.16),
}

# name -> (texture set, base colour, roughness scale, metallic, extra)
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


def tpath(name, kind):
    ext = {"albedo": "_albedo.jpg", "albedo_png": "_albedo.png", "normal": "_normal.png", "orm": "_orm.jpg"}[kind]
    return C.asset_path(f"{TEX}/{name}{ext}")


def _textured(name: str, texset: str, color, rough_scale: float, metal: float, coat: float = 0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")

    def img(path, nc):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path, check_existing=True)
        if nc:
            n.image.colorspace_settings.name = "Non-Color"
        return n
    a = img(tpath(texset, "albedo"), False)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(a.outputs["Color"], mul.inputs[6])
    mul.inputs[7].default_value = (*color, 1.0)
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "vc"
    mul2 = nt.nodes.new("ShaderNodeMix")
    mul2.data_type = "RGBA"
    mul2.blend_type = "MULTIPLY"
    mul2.inputs["Factor"].default_value = 1.0
    nt.links.new(mul.outputs[2], mul2.inputs[6])
    nt.links.new(vc.outputs["Color"], mul2.inputs[7])
    nt.links.new(mul2.outputs[2], bsdf.inputs["Base Color"])
    o = img(tpath(texset, "orm"), True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(o.outputs["Color"], sep.inputs["Color"])
    rm = nt.nodes.new("ShaderNodeMath")
    rm.operation = "MULTIPLY"
    rm.use_clamp = True
    rm.inputs[1].default_value = rough_scale
    nt.links.new(sep.outputs["Green"], rm.inputs[0])
    nt.links.new(rm.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = metal
    nrm = img(tpath(texset, "normal"), True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.6
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.04
    return m


def mat(name: str) -> bpy.types.Material:
    """veh_paint_<colour> | one of SPECS | LIGHTS | veh_glass | veh_mirror | veh_decals."""
    if name.startswith("veh_paint_"):
        return _textured(name, "veh_paint", PAINTS[name[10:]], 1.0, 0.0, coat=1.0)
    if name in SPECS:
        t, c, r, mt = SPECS[name]
        return _textured(name, t, c, r, mt)
    m = bpy.data.materials.get(name)
    if m:
        return m
    if name in LIGHTS:
        return C.principled(name, LIGHTS[name], 0.08, 0.0, **{"Transmission Weight": 0.6,
                                                              "Emission Color": (*LIGHTS[name], 1),
                                                              "Emission Strength": 0.0})
    if name == "veh_glass":
        m = C.principled(name, (0.06, 0.08, 0.08), 0.03, 0.0, **{"Alpha": 0.35})
        return m
    if name == "veh_mirror":
        return C.principled(name, (0.9, 0.9, 0.9), 0.02, 1.0)
    if name == "veh_decals":
        return C.image_material(name, albedo=tpath("veh_decals", "albedo_png"), alpha_clip=True)
    raise KeyError(name)


# ---------------------------------------------------------------------------
# primitive builders  (all return objects linked to the scene, transforms applied)
# ---------------------------------------------------------------------------
def _obj(name, bm, material, smooth=None, uv_box=1.0):
    ob = C.mesh_from_bmesh(name, bm)
    if material:
        ob.data.materials.append(mat(material) if isinstance(material, str) else material)
    if uv_box:
        C.uv_cube_project(ob, uv_box)
    if smooth is not None:
        C.shade_smooth(ob, smooth if smooth > 0 else None)
    return ob


def rbox(name, size, center, material, bevel=0.01, segs=2, smooth=35, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    ob = _obj(name, bm, material, None, 0)
    ob.rotation_euler = rot
    ob.location = center
    if bevel > 0:
        m = ob.modifiers.new("b", "BEVEL")
        m.width = min(bevel, min(size) * 0.45)
        m.segments = segs
        m.limit_method = "ANGLE"
        m.harden_normals = False
        C.apply_modifiers(ob)
    C.apply_transforms(ob, loc=True)
    C.uv_cube_project(ob, 1.0)
    C.shade_smooth(ob, smooth)
    return ob


def cyl(name, r, length, center, axis="X", material="veh_steel_dark", sides=16, r2=None, cap=True, smooth=40):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=sides, radius1=r,
                          radius2=r if r2 is None else r2, depth=length)
    rot = {"X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X"), "Z": Matrix()}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    return _obj(name, bm, material, smooth)


def sphere(name, r, center, material, scale=(1, 1, 1), segs=16, rings=10):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co = Vector(center) + Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    return _obj(name, bm, material, 0)


def tube(name, pts, r, material="veh_steel_dark", sides=8, bend=0.04, cap=True, r_end=None):
    """Swept tube along a polyline; corners are rounded with a small bend radius."""
    P = [Vector(p) for p in pts]
    if bend > 0 and len(P) > 2:
        Q = [P[0]]
        for i in range(1, len(P) - 1):
            a, b, c = P[i - 1], P[i], P[i + 1]
            da, dc = (a - b), (c - b)
            ra, rc = min(bend, da.length * 0.45), min(bend, dc.length * 0.45)
            p0, p2 = b + da.normalized() * ra, b + dc.normalized() * rc
            for k in range(5):
                t = k / 4
                Q.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p2)
        Q.append(P[-1])
        P = Q
    n = len(P)
    tans = [(P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized() for i in range(n)]
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    N = tans[0].cross(up).normalized()
    bm = bmesh.new()
    rings = []
    for i in range(n):
        if i:
            N = tans[i - 1].rotation_difference(tans[i]) @ N
            N = (N - tans[i] * N.dot(tans[i])).normalized()
        B = tans[i].cross(N)
        rr = r if r_end is None else r + (r_end - r) * i / (n - 1)
        rings.append([bm.verts.new(P[i] + (N * math.cos(a) + B * math.sin(a)) * rr)
                      for a in [k / sides * math.tau for k in range(sides)]])
    for i in range(n - 1):
        for k in range(sides):
            bm.faces.new([rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]])
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm, material, 0, 0)


def lathe(name, profile, center, axis="X", material="veh_steel_dark", sides=24, smooth=40, cap=False):
    """Revolve [(radius, offset_along_axis), ...] around an axis through `center`."""
    bm = bmesh.new()
    rings = []
    for r, x in profile:
        ring = []
        for k in range(sides):
            a = k / sides * math.tau
            if r < 1e-5:
                ring.append(None)
                continue
            ring.append(bm.verts.new((x, math.cos(a) * r, math.sin(a) * r)))
        if r < 1e-5:
            ring = [bm.verts.new((x, 0, 0))] * sides
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            vs = [rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]]
            uniq = []
            for v in vs:
                if v not in uniq:
                    uniq.append(v)
            if len(uniq) >= 3:
                try:
                    bm.faces.new(uniq)
                except ValueError:
                    pass
    rot = {"X": Matrix(), "Y": Matrix.Rotation(math.pi / 2, 4, "Z"), "Z": Matrix.Rotation(-math.pi / 2, 4, "Y")}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm, material, smooth)


def loft(name, sections, material, n=24, cap=True, smooth=50):
    """Smooth body panel lofted along Y. Each section: (y, cx, cz, half_w, half_h, exponent[, flat_bottom]).
    Cross-sections are superellipses |x/a|^e + |z/b|^e = 1 in the XZ plane."""
    bm = bmesh.new()
    rings = []
    for s in sections:
        y, cx, cz, a, b, e = s[:6]
        flat = s[6] if len(s) > 6 else 0.0
        ring = []
        for k in range(n):
            t = k / n * math.tau
            c, si = math.cos(t), math.sin(t)
            x = a * math.copysign(abs(c) ** (2 / e), c)
            z = b * math.copysign(abs(si) ** (2 / e), si)
            if flat and z < -b * (1 - flat):
                z = -b * (1 - flat)
            ring.append(bm.verts.new((cx + x, y, cz + z)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(n):
            bm.faces.new([rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k]])
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _obj(name, bm, material, smooth)


def extrude(name, poly, thickness, plane="YZ", offset=0.0, material="veh_steel_dark", bevel=0.0, smooth=35):
    """Extrude a 2-D polygon. plane YZ: poly in (y, z), extruded along X centred at `offset`.
    plane XY: poly in (x, y) extruded along Z; plane XZ: poly in (x, z) along Y."""
    bm = bmesh.new()
    vs = []
    for p in poly:
        if plane == "YZ":
            vs.append(bm.verts.new((offset - thickness / 2, p[0], p[1])))
        elif plane == "XY":
            vs.append(bm.verts.new((p[0], p[1], offset - thickness / 2)))
        else:
            vs.append(bm.verts.new((p[0], offset - thickness / 2, p[1])))
    f = bm.faces.new(vs)
    d = {"YZ": Vector((thickness, 0, 0)), "XY": Vector((0, 0, thickness)), "XZ": Vector((0, thickness, 0))}[plane]
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in r["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=d, verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _obj(name, bm, material, None, 0)
    if bevel > 0:
        m = ob.modifiers.new("b", "BEVEL")
        m.width = bevel
        m.segments = 2
        m.limit_method = "ANGLE"
        C.apply_modifiers(ob)
    C.uv_cube_project(ob, 1.0)
    C.shade_smooth(ob, smooth)
    return ob


def mirror_x(ob, name=None):
    """Mirrored copy across the X=0 plane (applied, normals fixed)."""
    me = ob.data.copy()
    nb = bpy.data.objects.new(name or ob.name + "_R", me)
    bpy.context.scene.collection.objects.link(nb)
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    C.uv_cube_project(nb, 1.0)
    return nb


def decal(name, rect_name, center, size, normal_axis="-Y", flip=False, offset=0.002):
    """Flat quad textured with one rect of the decal atlas. normal_axis: -Y (front), +Y (rear), +X/-X sides."""
    from vehicles_decals import DECALS
    x, y, w, h = DECALS[rect_name]
    u0, u1 = x / 1024, (x + w) / 1024
    v0, v1 = 1 - (y + h) / 1024, 1 - y / 1024
    if flip:
        u0, u1 = u1, u0
    cx, cy, cz = center
    sw, sh = size
    bm = bmesh.new()
    if normal_axis in ("-Y", "+Y"):
        s = 1 if normal_axis == "-Y" else -1
        o = Vector((0, -offset * s, 0))
        pts = [(cx - sw / 2 * s, cy, cz - sh / 2), (cx + sw / 2 * s, cy, cz - sh / 2), (cx + sw / 2 * s, cy, cz + sh / 2),
               (cx - sw / 2 * s, cy, cz + sh / 2)]
    else:
        so = 1 if normal_axis == "+X" else -1
        o = Vector((offset * so, 0, 0))
        s = -so
        pts = [(cx, cy + sw / 2 * s, cz - sh / 2), (cx, cy - sw / 2 * s, cz - sh / 2), (cx, cy - sw / 2 * s, cz + sh / 2),
               (cx, cy + sw / 2 * s, cz + sh / 2)]
    vs = [bm.verts.new(Vector(p) + o) for p in pts]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.verify()
    for l, uv in zip(f.loops, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]):
        l[uvl].uv = uv
    ob = C.mesh_from_bmesh(name, bm)
    ob.data.materials.append(mat("veh_decals"))
    return ob


def conform_decal_to(ob, target, max_dist=0.3):
    """Project a decal's vertices onto a curved target surface along the decal normal."""
    bvh = BVHTree.FromObject(target, bpy.context.evaluated_depsgraph_get())
    me = ob.data
    n = me.polygons[0].normal.copy()
    for v in me.vertices:
        hit = bvh.ray_cast(v.co + n * max_dist, -n, max_dist * 2)
        if hit[0] is not None:
            v.co = hit[0] + n * 0.003


# ---------------------------------------------------------------------------
# wheels
# ---------------------------------------------------------------------------
def tyre(name, r_out, width, r_rim, sides=40, prof=10):
    """Tyre with a rounded rectangular profile. UV: u around (repeats ~ every 0.4 m), v across the profile."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.verify()
    hw = width / 2
    wall = r_out - r_rim
    # profile from inner bead side A -> crown -> inner bead side B, (x, r)
    pr = []
    for k in range(prof + 1):
        t = k / prof
        a = math.pi * t
        x = -math.cos(a) * hw * (0.92 + 0.08 * math.sin(a))
        rr = r_rim + wall * (0.15 + 0.85 * math.sin(a) ** 0.55)
        pr.append((x, rr))
    pr = [(-hw * 0.8, r_rim)] + pr + [(hw * 0.8, r_rim)]
    rings = []
    for (x, rr) in pr:
        rings.append([bm.verts.new((x, math.cos(k / sides * math.tau) * rr, math.sin(k / sides * math.tau) * rr))
                      for k in range(sides)])
    urep = max(4, round(2 * math.pi * r_out / 0.4))
    for i in range(len(rings) - 1):
        for k in range(sides):
            f = bm.faces.new([rings[i][k], rings[i + 1][k], rings[i + 1][(k + 1) % sides], rings[i][(k + 1) % sides]])
            vv = [i / (len(rings) - 1), (i + 1) / (len(rings) - 1)]
            uu = [k / sides * urep, (k + 1) / sides * urep]
            for l, uv in zip(f.loops, [(uu[0], vv[0]), (uu[0], vv[1]), (uu[1], vv[1]), (uu[1], vv[0])]):
                l[uvl].uv = uv
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = C.mesh_from_bmesh(name, bm)
    ob.data.materials.append(mat("veh_rubber"))
    C.shade_smooth(ob, None)
    return ob


def spoked_rim(name, r_rim, width, hub_w, spokes=36, rim_mat="veh_chrome"):
    parts = []
    parts.append(lathe(name + "_rim", [(r_rim - 0.018, -width * 0.42), (r_rim + 0.004, -width * 0.48),
                                       (r_rim - 0.004, -width * 0.2), (r_rim - 0.006, 0.0),
                                       (r_rim - 0.004, width * 0.2), (r_rim + 0.004, width * 0.48),
                                       (r_rim - 0.018, width * 0.42), (r_rim - 0.018, -width * 0.42)],
                       (0, 0, 0), "X", rim_mat, 40, 30))
    parts.append(lathe(name + "_hub", [(0.0, -hub_w / 2), (0.022, -hub_w / 2), (0.03, -hub_w * 0.35), (0.05, -hub_w * 0.3),
                                       (0.05, -hub_w * 0.22), (0.032, -hub_w * 0.15), (0.032, hub_w * 0.15),
                                       (0.05, hub_w * 0.22), (0.05, hub_w * 0.3), (0.03, hub_w * 0.35),
                                       (0.022, hub_w / 2), (0.0, hub_w / 2)], (0, 0, 0), "X", "veh_alloy", 16, 40))
    for k in range(spokes):
        side = 1 if k % 2 else -1
        a = k / spokes * math.tau
        hx = side * hub_w * 0.27
        ha = a + side * 0.35
        p0 = Vector((hx, math.cos(ha) * 0.045, math.sin(ha) * 0.045))
        p1 = Vector((side * 0.004, math.cos(a) * (r_rim - 0.012), math.sin(a) * (r_rim - 0.012)))
        parts.append(tube(f"{name}_sp{k}", [p0, p1], 0.0013, "veh_chrome", sides=3, bend=0, cap=False))
    return parts


def cast_rim(name, r_rim, width, spokes=5, mat_name="veh_alloy", disc=0.0):
    parts = [lathe(name + "_rim", [(r_rim - 0.02, -width * 0.45), (r_rim + 0.006, -width * 0.5), (r_rim, -width * 0.25),
                                   (r_rim - 0.004, 0), (r_rim, width * 0.25), (r_rim + 0.006, width * 0.5),
                                   (r_rim - 0.02, width * 0.45), (r_rim - 0.02, -width * 0.45)], (0, 0, 0), "X",
                   mat_name, 40, 30)]
    parts.append(lathe(name + "_hub", [(0.0, -width * 0.45), (0.035, -width * 0.45), (0.05, -width * 0.2),
                                       (0.05, width * 0.2), (0.035, width * 0.45), (0.0, width * 0.45)], (0, 0, 0), "X",
                       mat_name, 16, 40))
    for k in range(spokes):
        a = k / spokes * math.tau
        for sgn in (-1, 1):  # split-spoke pairs
            aa = a + sgn * 0.09
            p0 = Vector((0, math.cos(a) * 0.045, math.sin(a) * 0.045))
            p1 = Vector((0, math.cos(aa) * (r_rim - 0.015), math.sin(aa) * (r_rim - 0.015)))
            parts.append(tube(f"{name}_sp{k}{sgn}", [p0, p1], 0.011, mat_name, sides=6, bend=0, r_end=0.008))
    if disc:
        parts.append(lathe(name + "_disc", [(0.06, -0.003), (disc, -0.003), (disc, 0.003), (0.06, 0.003),
                                            (0.06, -0.003)], (-width * 0.55, 0, 0), "X", "veh_alloy", 32, 20))
    return parts


def car_rim(name, r_rim, width, style="steel"):
    parts = [lathe(name + "_rim", [(r_rim - 0.02, -width * 0.48), (r_rim + 0.012, -width * 0.5), (r_rim, -width * 0.3),
                                   (r_rim - 0.03, 0), (r_rim, width * 0.3), (r_rim + 0.012, width * 0.5),
                                   (r_rim - 0.02, width * 0.48)], (0, 0, 0), "X",
                   "veh_alloy" if style == "alloy" else "veh_steel_dark", 32, 30)]
    if style == "steel":
        # pressed steel wheel behind a plastic hub cap with vents
        parts.append(lathe(name + "_cap", [(0.0, width * 0.35), (0.05, width * 0.36), (r_rim * 0.75, width * 0.3),
                                           (r_rim * 0.92, width * 0.22), (r_rim * 0.98, width * 0.12),
                                           (r_rim * 0.95, width * 0.05)], (0, 0, 0), "X", "veh_plastic_grey", 32, 35))
    else:
        parts.append(lathe(name + "_face", [(0.0, width * 0.2), (0.07, width * 0.2), (0.08, width * 0.1),
                                            (0.08, -width * 0.2), (0.0, -width * 0.2)], (0, 0, 0), "X", "veh_alloy", 16, 40))
        for k in range(6):
            a = k / 6 * math.tau
            p0 = Vector((width * 0.15, math.cos(a) * 0.07, math.sin(a) * 0.07))
            p1 = Vector((width * 0.05, math.cos(a) * (r_rim - 0.02), math.sin(a) * (r_rim - 0.02)))
            parts.append(tube(f"{name}_sp{k}", [p0, p1], 0.016, "veh_alloy", sides=6, bend=0, r_end=0.012))
    parts.append(lathe(name + "_back", [(0.0, -width * 0.2), (r_rim - 0.02, -width * 0.2)], (0, 0, 0), "X",
                       "veh_steel_dark", 24, 40))
    return parts


def make_wheel(name, center, r_out, tyre_w, r_rim, style="spoked", spokes=36, hub_w=0.11, mirror=False,
               disc=0.0):
    """Assembles a wheel object named `name`, origin at the hub (`center`), spin axis local X."""
    parts = [tyre(name + "_tyre", r_out, tyre_w, r_rim)]
    if style == "spoked":
        parts += spoked_rim(name, r_rim, tyre_w * 0.9, hub_w, spokes)
    elif style == "cast":
        parts += cast_rim(name, r_rim, tyre_w * 0.9, spokes, disc=disc)
    else:
        parts += car_rim(name, r_rim, tyre_w * 0.95, style)
    ob = C.join(parts, name)
    if mirror:
        for v in ob.data.vertices:
            v.co.x = -v.co.x
        ob.data.flip_normals()
    ob.location = center
    return ob


# ---------------------------------------------------------------------------
# wear (vertex colour "vc")
# ---------------------------------------------------------------------------
def bake_wear(objs, mud_height=0.45, mud=0.6, ao_rays=12, ao_dist=0.25, seed=1, wheels=()):
    """AO + mud + grime into float colour attribute 'vc' (multiplied into albedo)."""
    rng = random.Random(seed)
    deps = bpy.context.evaluated_depsgraph_get()
    occluders = []
    for o in list(objs) + list(wheels):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.transform(o.matrix_world)
        occluders.append(bm)
    big = bmesh.new()
    for bm in occluders:
        me = bpy.data.meshes.new("_tmp")
        bm.to_mesh(me)
        big.from_mesh(me)
        bpy.data.meshes.remove(me)
        bm.free()
    tree = BVHTree.FromBMesh(big)
    big.free()
    dirs = []
    for i in range(ao_rays):
        z = (i + 0.5) / ao_rays
        a = i * 2.39996
        rr = math.sqrt(1 - z * z)
        dirs.append(Vector((math.cos(a) * rr, math.sin(a) * rr, z)))
    from mathutils import noise
    wheel_pos = [w.matrix_world.translation.copy() for w in wheels]
    for o in list(objs) + list(wheels):
        me = o.data
        attr = me.color_attributes.get("vc") or me.color_attributes.new("vc", "FLOAT_COLOR", "POINT")
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        cols = []
        for v in me.vertices:
            p = mw @ v.co
            n = (nmat @ v.normal).normalized()
            # cosine-weighted hemisphere around n
            tq = n.to_track_quat("Z", "Y")
            occ = 0
            for d in dirs:
                dd = tq @ d
                hit = tree.ray_cast(p + n * 0.004, dd, ao_dist)
                if hit[0] is not None:
                    occ += 1
            ao = 1 - 0.75 * occ / len(dirs)
            # mud: rises from the ground, thrown up behind / around wheels, patchy
            h = max(0.0, 1 - p.z / mud_height)
            near = 0.0
            for wp in wheel_pos:
                d = (p - wp).length
                near = max(near, max(0.0, 1 - d / 0.55))
            nz = noise.noise(p * 7.0 + Vector((seed, 0, 0))) * 0.5 + 0.5
            m = min(1.0, (h ** 1.5 * 0.8 + near * 0.5) * mud * (0.55 + 0.9 * nz))
            if n.z < -0.5:
                m = min(1.0, m + 0.3 * mud)
            mudc = Vector((0.55, 0.47, 0.37))
            c = Vector((1, 1, 1)).lerp(mudc, m) * ao
            cols.append((c.x, c.y, c.z, 1.0))
        for i, c in enumerate(cols):
            attr.data[i].color = c
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.find("vc")


def finish_body(parts, name="body"):
    """Join parts (applying modifiers), merge-by-distance off (separate shells), returns body object."""
    for p in parts:
        if p.modifiers:
            C.apply_modifiers(p)
    return C.join(parts, name)


def marker(name, loc):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.1
    e.location = loc
    bpy.context.scene.collection.objects.link(e)
    return e


def box_col(name, center, size):
    """Box collider (-convcolonly, becomes an exact BoxShape3D). name = col_<surface>_<tag>."""
    ob = C.box(name + "-convcolonly", size, (center[0], center[1], center[2] - size[2] / 2))
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob
