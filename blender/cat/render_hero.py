"""Hero beauty render of Cam with Cycles strand fur (preview only; the game uses shell fur).

Usage: tools/blender_run.sh blender/cat/render_hero.py -- [strands] [WxH] [samples] [pose] [out]
  pose: sit | walk | stand  (default sit)
Strands are generated on the POSED skin: roots sampled by area x fur density, length,
colour and comb direction evaluated from cat_coat.fields at the rest-pose position of each
root (same functions that bake the game textures), flow carried into the posed frame per
triangle.  Output: qa/out/cat-asset/hero_<pose>.png (+ docs/gallery copy when out given).
"""
from __future__ import annotations

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import common as C  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
N_STRANDS = int(argv[0]) if len(argv) > 0 else 600_000
RES = tuple(int(x) for x in argv[1].split("x")) if len(argv) > 1 else (1280, 800)
SAMPLES = int(argv[2]) if len(argv) > 2 else 64
POSE = argv[3] if len(argv) > 3 else "sit"
OUT = argv[4] if len(argv) > 4 else ""

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "cat.blend"))
import cat_anatomy as A  # noqa: E402
import cat_anim as AN  # noqa: E402
import cat_clips as CL  # noqa: E402
import cat_coat as CO  # noqa: E402

sc = bpy.context.scene
rig = bpy.data.objects["CatRig"]
body = bpy.data.objects["CatBody"]
rig.animation_data_create()
rig.animation_data.action = None

# ---------------------------------------------------------------- pose
solver = AN.Solver(rig)
if POSE == "sit":
    prm = AN.mix(CL.SIT, CL.SIT, 0)
    prm["head"] = (-4.0, 24.0, -6.0)
    prm["eyes"] = (6.0, 2.0)
    prm["earL"] = (0.0, 6.0, 0.0)
    prm["earR"] = (0.0, -4.0, 0.0)
    prm["tail"]["tip"] = 36.0
elif POSE == "walk":
    nf, fn, _ = CL.clip_defs()["walk"]
    prm = fn(4, 4 / nf)
    prm["head"] = (-10.0, 18.0, 0.0)
else:
    prm = AN.mix(CL.STAND, CL.STAND, 0)
    prm["head"] = (-6.0, 22.0, -4.0)
Acc, H = solver.solve(prm)
for n, m in solver.bases(Acc, H).items():
    pb = rig.pose.bones[n]
    loc, rot, _ = m.decompose()
    pb.location = loc
    pb.rotation_quaternion = rot
bpy.context.view_layer.update()

# ---------------------------------------------------------------- fur roots
t0 = time.time()
dg = bpy.context.evaluated_depsgraph_get()
ev = body.evaluated_get(dg)
me_ev = ev.to_mesh()
me_ev.calc_loop_triangles()
nt = len(me_ev.loop_triangles)
tri = np.empty(nt * 3, np.int32)
me_ev.loop_triangles.foreach_get("vertices", tri)
tri = tri.reshape(-1, 3)
Vp = np.empty(len(me_ev.vertices) * 3, np.float32)
me_ev.vertices.foreach_get("co", Vp)
Vp = Vp.reshape(-1, 3).astype(np.float64) @ np.array(body.matrix_world.to_3x3()).T + np.array(body.matrix_world.translation)
Vr = np.empty(len(body.data.vertices) * 3, np.float32)
body.data.vertices.foreach_get("co", Vr)
Vr = Vr.reshape(-1, 3).astype(np.float64)
ev.to_mesh_clear()
# exclude teeth/tongue/ear-cavity-free parts by vertex group
skip = np.zeros(len(Vr), bool)
for g in ("part_teeth", "part_tongue"):
    vg = body.vertex_groups.get(g)
    if vg:
        for v in body.data.vertices:
            if any(e.group == vg.index and e.weight > 0.5 for e in v.groups):
                skip[v.index] = True
tri = tri[~skip[tri].any(1)]
a, b, c = Vp[tri[:, 0]], Vp[tri[:, 1]], Vp[tri[:, 2]]
area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
rng = np.random.default_rng(7)
pick = rng.choice(len(tri), size=N_STRANDS, p=area / area.sum())
u = rng.random(N_STRANDS)
v = rng.random(N_STRANDS)
flip = u + v > 1
u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
w = 1 - u - v
T = tri[pick]


def bary(X):
    return X[T[:, 0]] * w[:, None] + X[T[:, 1]] * u[:, None] + X[T[:, 2]] * v[:, None]


Pp, Pr = bary(Vp), bary(Vr)
ra, rb, rc = Vr[T[:, 0]], Vr[T[:, 1]], Vr[T[:, 2]]
pa, pb_, pc = Vp[T[:, 0]], Vp[T[:, 1]], Vp[T[:, 2]]
Nr = np.cross(rb - ra, rc - ra)
Nr /= np.linalg.norm(Nr, axis=1, keepdims=True) + 1e-12
Np = np.cross(pb_ - pa, pc - pa)
Np /= np.linalg.norm(Np, axis=1, keepdims=True) + 1e-12
part = np.zeros((N_STRANDS, 3))
for g, ch in (("part_ear_L", 0), ("part_ear_R", 0)):
    vg = body.vertex_groups.get(g)
    if vg:
        mem = np.zeros(len(Vr), bool)
        for vv in body.data.vertices:
            if any(e.group == vg.index and e.weight > 0.5 for e in vv.groups):
                mem[vv.index] = True
        part[mem[T].all(1), ch] = 1.0
# coat fields at the rest positions (chunked)
fur_len = np.zeros(N_STRANDS)
fur_den = np.zeros(N_STRANDS)
flow_r = np.zeros((N_STRANDS, 3))
col = np.zeros((N_STRANDS, 3))
CH = 400_000
for i in range(0, N_STRANDS, CH):
    sl = slice(i, i + CH)
    F = CO.fields(Pr[sl], Nr[sl], part[sl])
    fur_len[sl] = F["fur_len"]
    fur_den[sl] = F["fur_den"]
    flow_r[sl] = F["flow"]
    col[sl] = CO.albedo(F, Pr[sl], "cam")
keep = (rng.random(N_STRANDS) < fur_den) & (fur_len > 0.03)
print(f"fields {time.time() - t0:.1f}s keep {keep.sum()}/{N_STRANDS}")


def tangent_map(r0, r1, r2, p0, p1, p2, nr, np_, vec):
    """carry rest-space tangent vectors into the posed triangle frame."""
    R = np.stack([r1 - r0, r2 - r0, nr], 2)
    Pm = np.stack([p1 - p0, p2 - p0, np_], 2)
    Ri = np.linalg.inv(R + np.eye(3)[None] * 1e-12)
    M = Pm @ Ri
    return np.einsum("nij,nj->ni", M, vec)


flow_p = tangent_map(ra, rb, rc, pa, pb_, pc, Nr, Np, flow_r)
flow_p -= np.sum(flow_p * Np, 1, keepdims=True) * Np
flow_p /= np.linalg.norm(flow_p, axis=1, keepdims=True) + 1e-12
k = np.nonzero(keep)[0]
Pp, Np, flow_p, fur_len, col = Pp[k], Np[k], flow_p[k], fur_len[k], col[k]
n = len(k)
SEG = 5
L = A.FUR_MAX_LENGTH * fur_len * (0.75 + 0.5 * rng.random(n))
lift = np.radians(18 + 22 * rng.random(n))
d0 = flow_p * np.cos(lift)[:, None] + Np * np.sin(lift)[:, None]
jit = rng.normal(0, 0.18, (n, 3))
jit -= np.sum(jit * Np, 1, keepdims=True) * Np
d0 = d0 + jit * 0.5
d0 /= np.linalg.norm(d0, axis=1, keepdims=True)
pts = np.zeros((n, SEG, 3))
for s in range(SEG):
    t = s / (SEG - 1)
    droop = -Np * (0.22 * t * t) + flow_p * (0.12 * t * t)
    pts[:, s] = Pp - Np * 0.0002 + (d0 * t + droop) * L[:, None]

# ---------------------------------------------------------------- curves object
hc = bpy.data.hair_curves.new("CatFurStrands")
hc.add_curves([SEG] * n)
hc.position_data.foreach_set("vector", pts.astype(np.float32).ravel())
rad = np.tile(np.linspace(0.000055, 0.000012, SEG), n).astype(np.float32)
ra_attr = hc.attributes.get("radius") or hc.attributes.new("radius", "FLOAT", "POINT")
ra_attr.data.foreach_set("value", rad)
cattr = hc.attributes.new("fur_color", "FLOAT_COLOR", "CURVE")
rgba = np.concatenate([col, np.ones((n, 1))], 1).astype(np.float32)
cattr.data.foreach_set("color", rgba.ravel())
fur_ob = bpy.data.objects.new("CatFurStrands", hc)
sc.collection.objects.link(fur_ob)
m = bpy.data.materials.new("FurStrand")
ntr = m.node_tree
for nd in list(ntr.nodes):
    if nd.bl_idname != "ShaderNodeOutputMaterial":
        ntr.nodes.remove(nd)
out = next(nd for nd in ntr.nodes if nd.bl_idname == "ShaderNodeOutputMaterial")
hair = ntr.nodes.new("ShaderNodeBsdfHairPrincipled")
try:
    hair.parametrization = "COLOR"
except Exception:
    pass
attr = ntr.nodes.new("ShaderNodeAttribute")
attr.attribute_name = "fur_color"
gam = ntr.nodes.new("ShaderNodeGamma")
gam.inputs["Gamma"].default_value = 1.15
ntr.links.new(attr.outputs["Color"], gam.inputs["Color"])
ntr.links.new(gam.outputs["Color"], hair.inputs["Color"])
for nm, val in (("Roughness", 0.32), ("Radial Roughness", 0.45), ("Coat", 0.12), ("IOR", 1.55),
                ("Random Roughness", 0.15), ("Random Color", 0.08)):
    if nm in hair.inputs:
        hair.inputs[nm].default_value = val
ntr.links.new(hair.outputs[0], out.inputs["Surface"])
hc.materials.append(m)
print(f"strands {n} built {time.time() - t0:.1f}s")

# skin under the fur: slightly darker (root shadowing) + subsurface for ears/nose
fm = body.data.materials[0]
bsdf = next(nd for nd in fm.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
bsdf.inputs["Subsurface Weight"].default_value = 0.15
bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
bsdf.inputs["Subsurface Scale"].default_value = 0.004
bsdf.inputs["Sheen Weight"].default_value = 0.3
cm = bpy.data.materials.get("CatEye_Cornea")
cb = next(nd for nd in cm.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
cb.inputs["Alpha"].default_value = 1.0
cb.inputs["Transmission Weight"].default_value = 1.0
cb.inputs["Roughness"].default_value = 0.0

# ---------------------------------------------------------------- set dressing / light / camera
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 8
sc.cycles.transparent_max_bounces = 16
sc.render.resolution_x, sc.render.resolution_y = RES
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Medium High Contrast"
sc.view_settings.exposure = -0.2
world = bpy.data.worlds.new("hero_world")
sc.world = world
wn = world.node_tree
bg = next(nd for nd in wn.nodes if nd.bl_idname == "ShaderNodeBackground")
sky = wn.nodes.new("ShaderNodeTexSky")
try:
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(14)
    sky.sun_rotation = math.radians(215)
    sky.sun_intensity = 0.35
except Exception:
    pass
wn.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.16
sun = bpy.data.objects.new("hero_sun", bpy.data.lights.new("hero_sun", "SUN"))
sc.collection.objects.link(sun)
sun.data.energy = 2.4
sun.data.color = (1.0, 0.82, 0.62)
sun.data.angle = math.radians(1.5)
sun.rotation_euler = (math.radians(70), 0, math.radians(215))
fill = bpy.data.objects.new("hero_fill", bpy.data.lights.new("hero_fill", "AREA"))
sc.collection.objects.link(fill)
fill.data.energy = 18
fill.data.size = 1.2
fill.data.color = (0.75, 0.85, 1.0)
fill.location = (-0.9, -1.0, 0.7)
fill.rotation_euler = (Vector((0, 0, 0.15)) - fill.location).to_track_quat("-Z", "Y").to_euler()
# ground: weathered terracotta tile / concrete (procedural)
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
g = bpy.context.active_object
gm = bpy.data.materials.new("hero_ground")
gt = gm.node_tree
gb = next(nd for nd in gt.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
noise = gt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 22.0
noise.inputs["Detail"].default_value = 8.0
ramp = gt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.16, 0.12, 0.09, 1)
ramp.color_ramp.elements[1].color = (0.34, 0.26, 0.20, 1)
gt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
gt.links.new(ramp.outputs["Color"], gb.inputs["Base Color"])
gb.inputs["Roughness"].default_value = 0.85
bump = gt.nodes.new("ShaderNodeBump")
bump.inputs["Strength"].default_value = 0.25
bump.inputs["Distance"].default_value = 0.002
gt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
gt.links.new(bump.outputs["Normal"], gb.inputs["Normal"])
g.data.materials.append(gm)
# camera: 3/4 front, eye level of the cat, shallow depth of field on the near eye
eye = Vector(solver.tip(Acc, H, "fpp_eye")) if False else Vector(H["fpp_eye"])
cam_d = bpy.data.cameras.new("hero_cam")
cam_d.lens = 85
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("hero_cam", cam_d)
sc.collection.objects.link(cam)
target = Vector((0.0, -0.01, eye.z * 0.56))
cam.location = target + Vector((0.55, -0.95, 0.12)).normalized() * 1.55
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_d.dof.focus_distance = (eye - cam.location).length
sc.camera = cam
outp = C.qa_path(f"cat-asset/hero_{POSE}.png")
sc.render.filepath = outp
t1 = time.time()
bpy.ops.render.render(write_still=True)
print(f"HERO rendered {outp} in {time.time() - t1:.0f}s")
