"""Build Cam the orange tabby: assets/models/cat/cat.glb (+ textures).

Usage:
  tools/blender_run.sh blender/cat/build_cat.py                 # full build
  tools/blender_run.sh blender/cat/build_cat.py -- --from uv    # resume from a cached stage
  tools/blender_run.sh blender/cat/build_cat.py -- --only low --qa

Stages (each saves qa/out/cat-asset/cache/stage_<name>.blend):
  high     SDF anatomy -> dense skin mesh (openvdb, 0.8 mm voxels)      [CatHigh]
  low      QuadriFlow retopo + ears/teeth/tongue -> game skin              [CatBody]
  parts    eyes (CatEyes), whiskers + ear furnishings (CatWhiskers)
  uv       seams (belly, inner legs, under tail, neck ring) + unwrap/pack
  rig      CatRig armature (contract bones + extras)
  weights  skinning
  tex      baked position/normal maps -> numpy tabby albedo, normal, roughness,
           fur mask, fur flow, NPC variant albedos, eye + whisker textures
  anim     all contract clips (in-place, 30 fps)
  export   materials + glb export + source .blend
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import common as C  # noqa: E402

STAGES = ["high", "low", "parts", "uv", "rig", "weights", "tex", "anim", "export"]
CACHE = C.qa_path("cat-asset/cache/x")[:-1]
HIGH_VOXEL = 0.0008


def args():
    a = [x for x in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if x != "--"]
    opts = {"from": None, "only": None, "qa": False, "to": None}
    i = 0
    while i < len(a):
        if a[i] in ("--from", "--only", "--to"):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        elif a[i] == "--qa":
            opts["qa"] = True
            i += 1
        else:
            i += 1
    return opts


def stage_path(name: str) -> str:
    return os.path.join(CACHE, f"stage_{name}.blend")


def save_stage(name: str) -> None:
    os.makedirs(CACHE, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=stage_path(name), compress=False)
    print(f"STAGE {name} saved")


def load_stage(name: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=stage_path(name))
    bpy.context.scene.render.fps = 30


# ---------------------------------------------------------------------------
def st_high(o):
    import cat_mesh as M
    import cat_sdf as S
    C.reset_scene()
    v, q, t = M.sdf_to_mesh(S.cat_sdf, S.BBOX_MIN, S.BBOX_MAX, HIGH_VOXEL)
    np.savez_compressed(os.path.join(CACHE, "high.npz"), v=v, q=q)
    hi = M.mesh_from_arrays("CatHigh", v, [q, t])
    hi.hide_render = True
    C.shade_smooth(hi, None)


def st_low(o):
    import cat_topo as T
    import cat_parts as P
    d = np.load(os.path.join(CACHE, "high.npz"))
    body = T.build_low(d["v"], d["q"], target_quads=18500)
    parts = [body]
    for side, nm in ((1, "L"), (-1, "R")):
        parts.append(P.build_ear("CatEar_" + nm, side))
    parts += P.build_mouth_parts()
    body = C.join(parts, "CatBody")
    C.shade_smooth(body, None)
    me = body.data
    print("CatBody tris", sum(len(p.vertices) - 2 for p in me.polygons))


def st_parts(o):
    import cat_parts as P
    eyes = []
    for side in (1, -1):
        eb, cb = P.build_eye(side)
        for o in (eb, cb):
            g = o.vertex_groups.new(name="eye_" + ("L" if side > 0 else "R"))
            g.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
        eyes += [eb, cb]
    P.eye_materials(eyes)
    ob = C.join(eyes, "CatEyes")
    C.shade_smooth(ob, None)
    w = P.build_whiskers()
    P.whisker_material(w)


def st_uv(o):
    import cat_uv as U
    body = bpy.data.objects["CatBody"]
    lab = U.classify_faces(body)
    print("regions:", {n: int((lab == i).sum()) for i, n in enumerate(U.REGIONS)})
    U.mark_seams(body, lab)
    U.unwrap(body, lab)
    U.texel_report(body, lab)
    body["uv_regions"] = lab.tolist()
    if o["qa"]:
        uv_layout_png(body, C.qa_path("cat-asset/topo/uv_layout.png"), lab)


def uv_layout_png(ob, path, lab=None, size=1024):
    import cat_tex as TX
    import cat_uv as U
    me = ob.data
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    img = np.full((size, size, 3), 0.08)
    cols = np.array([[0.9, 0.5, 0.2], [0.3, 0.8, 0.3], [0.8, 0.2, 0.3], [0.5, 0.5, 0.5], [0.3, 0.5, 0.9],
                     [0.9, 0.8, 0.2], [0.7, 0.3, 0.9], [0.2, 0.9, 0.9], [1, 1, 1], [1, 0.4, 0.7]])
    for i, p in enumerate(me.polygons):
        li = list(range(p.loop_start, p.loop_start + p.loop_total))
        col = cols[lab[i] % len(cols)] if lab is not None else (0.8, 0.8, 0.8)
        for a, b in zip(li, li[1:] + li[:1]):
            for t in np.linspace(0, 1, 12):
                q = uv[a] * (1 - t) + uv[b] * t
                x, y = int(q[0] * (size - 1)), int((1 - q[1]) * (size - 1))
                if 0 <= x < size and 0 <= y < size:
                    img[y, x] = col
    TX.save_png(path, img)


def qa_checker(tag):
    import cat_qa as Q
    m = bpy.data.materials.new("_checker")
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 160.0
    chk.inputs["Color1"].default_value = (0.75, 0.55, 0.3, 1)
    chk.inputs["Color2"].default_value = (0.15, 0.25, 0.45, 1)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["UV"], chk.inputs["Vector"])
    nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    body = bpy.data.objects["CatBody"]
    body.data.materials.clear()
    body.data.materials.append(m)
    Q.studio()
    Q.render_views(C.qa_path(f"cat-asset/topo/{tag}"), ["hf_front", "hf_q", "paws", "side", "q_back", "under"], samples=12)


def st_rig(o):
    import cat_rig as R
    R.build_rig()


def st_weights(o):
    import cat_rig as R
    rig = bpy.data.objects["CatRig"]
    body = bpy.data.objects["CatBody"]
    R.weight_body(body, rig)
    R.attach_rigid(bpy.data.objects["CatEyes"], rig, {"eye_L": [("eye_L", 1.0)], "eye_R": [("eye_R", 1.0)]})
    R.attach_rigid(bpy.data.objects["CatWhiskers"], rig, {
        "wh_mystacial_L": [("whisker_L", 1.0)], "wh_mystacial_R": [("whisker_R", 1.0)],
        "wh_head": [("head", 1.0)], "wh_chin": [("jaw", 1.0)],
        "wh_carpal_L": [("hand_L", 1.0)], "wh_carpal_R": [("hand_R", 1.0)],
        "ear_tuft_L": [("ear_L", 1.0)], "ear_tuft_R": [("ear_R", 1.0)]})


TEXDIR = os.path.dirname(C.asset_path("models/cat/textures/x"))


def _part_attribute(body):
    me = body.data
    n = len(me.vertices)
    col = np.zeros((n, 4), np.float32)
    col[:, 3] = 1
    for gname, ch in (("part_ear_L", 0), ("part_ear_R", 0), ("part_teeth", 1), ("part_tongue", 2)):
        g = body.vertex_groups.get(gname)
        if not g:
            continue
        for v in me.vertices:
            for e in v.groups:
                if e.group == g.index and e.weight > 0.5:
                    col[v.index, ch] = 1.0
    if "part_id" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["part_id"])
    a = me.color_attributes.new("part_id", "FLOAT_COLOR", "POINT")
    a.data.foreach_set("color", col.ravel())


def _eval_fields(maps, chunk=1_500_000, want=("albedo",), palettes=("cam",)):
    """Evaluate coat fields on covered texels in chunks. Returns dict name -> (H,W,C) arrays."""
    import cat_coat as CO
    pos, nrm, part = maps["pos"], maps["nrm"], maps["part"]
    H, W = pos.shape[:2]
    cov = pos[..., 3] > 0.5
    idx = np.nonzero(cov.ravel())[0]
    P_all = pos[..., :3].reshape(-1, 3)
    N_all = nrm[..., :3].reshape(-1, 3) * 2 - 1
    N_all /= np.linalg.norm(N_all, axis=1, keepdims=True) + 1e-9
    Q_all = part[..., :3].reshape(-1, 3)
    out = {}
    for i in range(0, len(idx), chunk):
        ii = idx[i:i + chunk]
        P = P_all[ii].astype(np.float64)
        N = N_all[ii].astype(np.float64)
        F = CO.fields(P, N, Q_all[ii])
        res = {}
        for pal in palettes:
            res["albedo_" + pal] = CO.albedo(F, P, pal)
        if "masks" in want:
            res["rough"] = CO.roughness(F)[:, None]
            res["mask"] = np.stack([F["fur_len"], F["fur_den"], F["stripe"]], 1)
            res["flow"] = F["flow"]
            res["strand"] = CO.strand_height(P, F["flow"], F["fur_len"])[:, None]
            res["bare"] = F["bare"][:, None]
        for k, v in res.items():
            if k not in out:
                out[k] = np.zeros((H * W, v.shape[1]), np.float32)
            out[k][ii] = v
        print(f"  fields chunk {i // chunk + 1}/{(len(idx) + chunk - 1) // chunk}", flush=True)
    return {k: v.reshape(H, W, -1) for k, v in out.items()}, cov


def _bake_normal_high(body, size):
    """Tangent-space normal map: dense SDF skin (+ copies of ears/teeth/tongue) -> CatBody."""
    import bmesh
    hi = bpy.data.objects["CatHigh"]
    parts = body.copy()
    parts.data = body.data.copy()
    parts.modifiers.clear()
    parts.parent = None
    bpy.context.scene.collection.objects.link(parts)
    bm = bmesh.new()
    bm.from_mesh(parts.data)
    keep = set()
    for gname in ("part_ear_L", "part_ear_R", "part_teeth", "part_tongue"):
        g = body.vertex_groups.get(gname)
        for v in body.data.vertices:
            if any(e.group == g.index and e.weight > 0.5 for e in v.groups):
                keep.add(v.index)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS")
    bm.to_mesh(parts.data)
    bm.free()
    for o in (hi, parts):
        o.hide_render = False
        o.hide_set(False)
    sc = bpy.context.scene
    sc.cycles.samples = 4
    img = bpy.data.images.new("_bake_nrm_hi", size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("_bake_n")
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node
    old = list(body.data.materials)
    body.data.materials.clear()
    body.data.materials.append(mat)
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
    hi.select_set(True)
    parts.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    b = sc.render.bake
    b.use_selected_to_active = True
    b.cage_extrusion = 0.0025
    b.max_ray_distance = 0.008
    b.normal_space = "TANGENT"
    b.margin = 16
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.0025,
                        max_ray_distance=0.008, normal_space="TANGENT", margin=16)
    a = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(a)
    n = a.reshape(size, size, 4)[::-1, :, :3].copy()
    b.use_selected_to_active = False
    body.data.materials.clear()
    for m in old:
        body.data.materials.append(m)
    bpy.data.objects.remove(parts, do_unlink=True)
    hi.hide_render = True
    bpy.data.images.remove(img)
    return n * 2 - 1


def _bake_ao(body, size):
    sc = bpy.context.scene
    if sc.world is None:
        sc.world = bpy.data.worlds.new("World")
    sc.world.light_settings.distance = 0.035
    sc.cycles.samples = 32
    hidden = []
    for ob in sc.objects:
        if ob.type == "MESH" and ob.name not in ("CatBody", "CatEyes") and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    img = bpy.data.images.new("_bake_ao", size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("_bake_ao")
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = img
    mat.node_tree.nodes.active = node
    old = list(body.data.materials)
    body.data.materials.clear()
    body.data.materials.append(mat)
    C.set_active(body)
    bpy.ops.object.bake(type="AO", margin=16, use_selected_to_active=False)
    a = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(a)
    ao = a.reshape(size, size, 4)[::-1, :, 0].copy()
    body.data.materials.clear()
    for m in old:
        body.data.materials.append(m)
    for ob in hidden:
        ob.hide_render = False
    bpy.data.images.remove(img)
    return ao


def _resize(img, size):
    """Box-downsample by an integer factor."""
    k = img.shape[0] // size
    if k <= 1:
        return img
    return img.reshape(size, k, size, k, -1).mean((1, 3))


def st_tex(o):
    import cat_tex as TX
    body = bpy.data.objects["CatBody"]
    _part_attribute(body)
    t0 = time.time()
    # --- 2048 pass: masks, flow, normal detail, roughness, variants ---
    S2 = 2048
    maps2 = TX.bake_emit_maps(body, S2)
    res2, cov2 = _eval_fields(maps2, want=("masks",), palettes=("cam", "black", "white", "calico", "grey_tabby"))
    print("  2048 fields", time.time() - t0)
    nrm_obj = maps2["nrm"][..., :3] * 2 - 1
    T, B, texel, ok = TX.tangent_frames(maps2["pos"], nrm_obj, cov2)
    # fur flow in tangent space
    fl = res2["flow"]
    fts = np.stack([np.sum(fl * T, -1), np.sum(fl * B, -1)], -1)
    fts /= np.linalg.norm(fts, axis=-1, keepdims=True) + 1e-9
    flow_img = np.concatenate([fts * 0.5 + 0.5, np.full(fts.shape[:2] + (1,), 0.5)], -1)
    flow_img[~cov2] = (0.5, 0.5, 0.5)
    TX.save_png(os.path.join(TEXDIR, "cat_fur_flow.png"), TX.dilate(flow_img, cov2, 12), srgb=False)
    # normal: baked shape detail + fur strand micro-normal (RNM blend)
    n_shape = _bake_normal_high(body, S2)
    h = res2["strand"][..., 0]
    tex_m = np.maximum(texel, 1e-5)
    dhu = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * tex_m)
    dhv = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) / (2 * tex_m)
    amp = 0.00025 * (1 - res2["bare"][..., 0])
    dhu = np.where(ok, dhu * amp, 0)
    dhv = np.where(ok, dhv * amp, 0)
    n_det = np.stack([-dhu, -dhv, np.ones_like(dhu)], -1)
    n_det /= np.linalg.norm(n_det, axis=-1, keepdims=True)
    t = n_shape + np.array([0, 0, 1.0])
    u = n_det * np.array([-1, -1, 1.0])
    r = t * np.sum(t * u, -1, keepdims=True) / np.maximum(t[..., 2:3], 1e-4) - u
    r /= np.linalg.norm(r, axis=-1, keepdims=True) + 1e-9
    r = np.where(cov2[..., None], r, n_shape)
    TX.save_png(os.path.join(TEXDIR, "cat_normal.png"), TX.dilate(r * 0.5 + 0.5, cov2, 16), srgb=False)
    # AO + roughness -> ORM
    ao = _bake_ao(body, S2)
    ao = np.clip(0.35 + 0.65 * ao, 0, 1)
    rough = res2["rough"][..., 0]
    orm = np.stack([ao, rough, np.zeros_like(ao)], -1)
    TX.save_png(os.path.join(TEXDIR, "cat_orm.png"), TX.dilate(orm, cov2, 16), srgb=False)
    mask = res2["mask"]
    TX.save_png(os.path.join(TEXDIR, "cat_fur_mask.png"), TX.dilate(mask, cov2, 16), srgb=False)
    aoc = (0.55 + 0.45 * ao)[..., None]
    for pal, fname in (("cam", "cat_albedo.png"), ("black", "cat_albedo_black.png"), ("white", "cat_albedo_white.png"),
                       ("calico", "cat_albedo_calico.png"), ("grey_tabby", "cat_albedo_grey_tabby.png")):
        alb = res2["albedo_" + pal] * aoc
        TX.save_png(os.path.join(TEXDIR, fname), TX.dilate(TX.lin_to_srgb(alb), cov2, 16))
    print("  2048 maps written", time.time() - t0)
    del res2, maps2, T, B
    # --- 4096 hero albedo (embedded in the glb as JPEG) ---
    S4 = 4096
    maps4 = TX.bake_emit_maps(body, S4)
    res4, cov4 = _eval_fields(maps4, want=(), palettes=("cam",))
    ao4 = np.kron(ao, np.ones((2, 2)))
    alb = res4["albedo_cam"] * (0.55 + 0.45 * ao4)[..., None]
    TX.save_jpg(os.path.join(TEXDIR, "cat_albedo_4k.jpg"), TX.dilate(TX.lin_to_srgb(alb), cov4, 24), 92)
    print("  4096 albedo written", time.time() - t0)


def st_anim(o):
    import cat_anim as AN
    import cat_clips as CL
    rig = bpy.data.objects["CatRig"]
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    solver = AN.Solver(rig)
    CL.build_all(solver)
    names = {a.name for a in bpy.data.actions}
    missing = [n for n in CL.CONTRACT if n not in names]
    print("ANIM missing:", missing)
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def _fur_material():
    m = C.image_material("CatFur", albedo=os.path.join(TEXDIR, "cat_albedo_4k.jpg"),
                         normal=os.path.join(TEXDIR, "cat_normal.png"), orm=os.path.join(TEXDIR, "cat_orm.png"))
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Specular IOR Level"].default_value = 0.35
    # glTF occlusion: exporter reads the "glTF Material Output" group's Occlusion socket
    grp = bpy.data.node_groups.get("glTF Material Output")
    if grp is None:
        grp = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = grp
    sep = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeSeparateColor")
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    return m


def st_export(o):
    import cat_clips as CL
    body = bpy.data.objects["CatBody"]
    body.data.materials.clear()
    body.data.materials.append(_fur_material())
    rig = bpy.data.objects["CatRig"]
    rig.animation_data_create()
    rig.animation_data.action = None
    for ob in list(bpy.data.objects):
        if ob.name.startswith("_"):
            bpy.data.objects.remove(ob, do_unlink=True)
    for nm in ("CatBody", "CatEyes", "CatWhiskers"):
        ob = bpy.data.objects[nm]
        ob.data.name = nm
        if ob.parent != rig:
            ob.parent = rig
    out = C.asset_path("models/cat/cat.glb")
    C.export_glb(out, objects=[rig], animations=True, image_format="AUTO", jpeg_quality=92)
    # human-editable source: drop the dense sculpt mesh to keep the .blend small
    hi = bpy.data.objects.get("CatHigh")
    if hi:
        bpy.data.objects.remove(hi, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cat.blend"), compress=True)
    print("SOURCE", os.path.join(HERE, "cat.blend"), os.path.getsize(os.path.join(HERE, "cat.blend")) // 1024, "KiB")


def qa_anim(tag, clips=None, frames_per=4, views=("side",)):
    import cat_qa as Q
    import cat_clips as CL
    rig = bpy.data.objects["CatRig"]
    Q.studio()
    out = []
    for name in (clips or CL.CONTRACT):
        act = bpy.data.actions.get(name)
        if act is None:
            continue
        rig.animation_data.action = act
        n = int(act.frame_end)
        for k in range(frames_per):
            fr = int(round(k * n / frames_per)) if CL.LOOPING.__contains__(name) else int(round(k * n / max(1, frames_per - 1)))
            bpy.context.scene.frame_set(fr)
            for v in views:
                Q.camera_for(v, (480, 300))
                out.append(Q.render(C.qa_path(f"cat-asset/anim/{tag}_{name}_{k}_{v}.png"), samples=8))
    rig.animation_data.action = None
    return out


def qa_pose(tag):
    """Extreme test poses (FK) to check skinning: head turn + jaw open + blink, tail curl,
    leg raise, crouch."""
    import math as m
    import cat_qa as Q
    from mathutils import Quaternion
    rig = bpy.data.objects["CatRig"]
    body = bpy.data.objects["CatBody"]
    body.data.materials.clear()
    body.data.materials.append(Q.clay())
    Q.studio()

    def rot(b, axis, deg):
        pb = rig.pose.bones[b]
        pb.rotation_quaternion = Quaternion(axis, m.radians(deg)) @ pb.rotation_quaternion

    def reset():
        for pb in rig.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.location = (0, 0, 0)
    poses = {
        "headjaw": lambda: [rot("neck", (0, 0, 1), 25), rot("neck_02", (0, 0, 1), 20), rot("head", (0, 0, 1), 15),
                            rot("jaw", (1, 0, 0), 28), rot("eyelid_L", (1, 0, 0), 38), rot("eyelid_low_L", (1, 0, 0), -14),
                            rot("ear_L", (1, 0, 0), -40), rot("ear_R", (0, 0, 1), 40)],
        "legs": lambda: [rot("upperarm_L", (1, 0, 0), -55), rot("forearm_L", (1, 0, 0), 70), rot("hand_L", (1, 0, 0), 60),
                         rot("thigh_R", (1, 0, 0), 45), rot("shin_R", (1, 0, 0), -60), rot("foot_R", (1, 0, 0), 50),
                         rot("scapula_L", (1, 0, 0), -15)],
        "spine": lambda: [rot("spine_01", (1, 0, 0), 14), rot("spine_02", (1, 0, 0), 14), rot("spine_03", (1, 0, 0), 12),
                          rot("spine_02", (0, 0, 1), 15), rot("spine_03", (0, 0, 1), 15)] +
                         [rot(f"tail_{i:02d}", (0, 0, 1), 25) for i in range(1, 9)] + [rot("tail_01", (1, 0, 0), 50)],
    }
    for nm, fn in poses.items():
        reset()
        fn()
        bpy.context.view_layer.update()
        views = ["q_front", "hf_q"] if nm == "headjaw" else (["q_front", "side"] if nm == "legs" else ["top", "q_back"])
        Q.render_views(C.qa_path(f"cat-asset/rig/{tag}_{nm}"), views, samples=12)
    reset()


def qa_wire(tag):
    import cat_qa as Q
    m = bpy.data.materials.new("_wire")
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    w = nt.nodes.new("ShaderNodeWireframe")
    w.use_pixel_size = True
    w.inputs[0].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.6, 0.58, 0.55, 1)
    mix.inputs["B"].default_value = (0.05, 0.05, 0.08, 1)
    nt.links.new(w.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    body = bpy.data.objects["CatBody"]
    body.data.materials.clear()
    body.data.materials.append(m)
    Q.studio()
    Q.render_views(C.qa_path(f"cat-asset/topo/{tag}"), ["hf_front", "hf_q", "eye_close", "paws", "side", "q_back"], samples=12)


STAGE_FN = {"high": st_high, "low": st_low, "parts": st_parts, "uv": st_uv, "rig": st_rig, "weights": st_weights, "tex": st_tex, "anim": st_anim, "export": st_export}


def main():
    o = args()
    t0 = time.time()
    names = STAGES
    if o["only"]:
        names = [o["only"]]
    elif o["from"]:
        names = STAGES[STAGES.index(o["from"]):]
    if o["to"]:
        names = names[:names.index(o["to"]) + 1]
    first = names[0]
    if first != "high":
        load_stage(STAGES[STAGES.index(first) - 1])
    for n in names:
        if n not in STAGE_FN:
            print("stage not implemented yet:", n)
            break
        ts = time.time()
        STAGE_FN[n](o)
        save_stage(n)
        print(f"== stage {n} done in {time.time() - ts:.1f}s")
    if o["qa"]:
        if names[-1] == "uv":
            qa_checker("uv")
        elif names[-1] == "weights":
            qa_pose("w")
        elif names[-1] == "anim":
            qa_anim("a")
        else:
            qa_wire(names[-1])
    print(f"BUILD done in {time.time() - t0:.1f}s")


main()
