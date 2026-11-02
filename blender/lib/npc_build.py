"""Creature build pipeline: SDF model -> game mesh -> rig + skin weights -> UVs ->
baked surface maps (position / normal / tangent) -> numpy texture synthesis ->
glTF materials -> GLB export, plus a Cycles preview helper.

Used by every blender/npc/build_*.py script (owner: creatures).
"""
from __future__ import annotations

import math
import os
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import common as C
import npc_sdf as S


# ---------------------------------------------------------------------------
# SDF -> mesh (openvdb, block-sparse sampling)
# ---------------------------------------------------------------------------
def sdf_to_mesh(sdf, bmin, bmax, h: float, block: int = 8, adaptivity: float = 0.0):
    import openvdb as vdb
    t0 = time.time()
    bmin = np.asarray(bmin, np.float64) - 3 * h
    bmax = np.asarray(bmax, np.float64) + 3 * h
    n = np.ceil((bmax - bmin) / h).astype(int) + 1
    n = ((n + block - 1) // block) * block
    nb = n // block
    bi = np.stack(np.meshgrid(np.arange(nb[0]), np.arange(nb[1]), np.arange(nb[2]), indexing="ij"), -1).reshape(-1, 3)
    centers = bmin + (bi * block + (block - 1) * 0.5) * h
    dc = np.concatenate([sdf(centers[i:i + 400_000]) for i in range(0, len(centers), 400_000)])
    half_diag = block * h * 0.8660254
    keep = np.abs(dc) < half_diag * 1.6 + 2 * h
    band = 3.0 * h
    signs = np.where(dc < 0, -band, band).astype(np.float32).reshape(tuple(nb))
    dense = np.repeat(np.repeat(np.repeat(signs, block, 0), block, 1), block, 2)
    kb = bi[keep]
    off = np.stack(np.meshgrid(np.arange(block), np.arange(block), np.arange(block), indexing="ij"), -1).reshape(-1, 3)
    per = max(1, 600_000 // len(off))
    for i in range(0, len(kb), per):
        idx = (kb[i:i + per, None, :] * block + off[None]).reshape(-1, 3)
        d = sdf(bmin + idx * h)
        dense[idx[:, 0], idx[:, 1], idx[:, 2]] = np.clip(d, -band, band).astype(np.float32)
    t1 = time.time()
    g = vdb.FloatGrid()
    g.background = band
    g.copyFromArray(dense)
    del dense
    pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=adaptivity)
    pts = bmin + np.asarray(pts, np.float64) * h
    quads = np.asarray(quads, np.int64).reshape(-1, 4)
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    print(f"sdf_to_mesh: grid {tuple(n)} blocks {int(keep.sum())}/{len(keep)} eval {t1 - t0:.1f}s "
          f"mesh {time.time() - t1:.1f}s -> {len(pts)} verts")
    return pts, quads, tris


def mesh_from_arrays(name: str, verts, faces_list, col=None) -> bpy.types.Object:
    faces_list = [np.asarray(f) for f in faces_list if len(f)]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    starts, totals, loops = [], [], []
    s = 0
    for f in faces_list:
        k = f.shape[1]
        starts.append(s + np.arange(len(f)) * k)
        totals.append(np.full(len(f), k))
        loops.append(f.ravel())
        s += len(f) * k
    me.loops.add(s)
    me.loops.foreach_set("vertex_index", np.concatenate(loops).astype(np.int32))
    me.polygons.add(sum(len(f) for f in faces_list))
    me.polygons.foreach_set("loop_start", np.concatenate(starts).astype(np.int32))
    me.polygons.foreach_set("loop_total", np.concatenate(totals).astype(np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def get_verts(ob) -> np.ndarray:
    v = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get("co", v)
    return v.reshape(-1, 3).astype(np.float64)


def set_verts(ob, v) -> None:
    ob.data.vertices.foreach_set("co", np.asarray(v, np.float32).ravel())
    ob.data.update()


def get_edges(ob) -> np.ndarray:
    e = np.empty(len(ob.data.edges) * 2, np.int32)
    ob.data.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def vertex_normals(ob) -> np.ndarray:
    n = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertex_normals.foreach_get("vector", n)
    return n.reshape(-1, 3).astype(np.float64)


def laplacian(values: np.ndarray, edges: np.ndarray, n: int, iters=1, lam=0.5) -> np.ndarray:
    deg = np.bincount(edges.ravel(), minlength=n).astype(np.float64)
    deg = np.maximum(deg, 1)
    v = values.copy()
    for _ in range(iters):
        acc = np.zeros_like(v)
        np.add.at(acc, edges[:, 0], v[edges[:, 1]])
        np.add.at(acc, edges[:, 1], v[edges[:, 0]])
        avg = acc / (deg[:, None] if v.ndim == 2 else deg)
        v = v + lam * (avg - v)
    return v


def fix_normals(ob) -> None:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def build_mesh(model: S.Model, name: str, h: float, target_tris: int, relax_rounds: int = 2,
               adaptivity: float = 0.0, keep_islands: bool = False) -> bpy.types.Object:
    """Polygonise the model and decimate to a game budget, then re-project onto the SDF."""
    lo, hi = model.bounds()
    pts, quads, tris = sdf_to_mesh(model, lo, hi, h, adaptivity=adaptivity)
    ob = mesh_from_arrays(name, pts, [quads, tris])
    fix_normals(ob)
    if not keep_islands:
        _drop_small_islands(ob)
    cur = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    if cur > target_tris:
        m = ob.modifiers.new("Dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = target_tris / cur
        m.use_symmetry = True
        m.symmetry_axis = "X"
        C.apply_modifiers(ob)
    # tangential relax + projection back on the surface (decimation flattens curvature)
    v = get_verts(ob)
    edges = get_edges(ob)
    n = len(v)
    for _ in range(relax_rounds):
        nrm = vertex_normals(ob)
        avg = laplacian(v, edges, n, iters=1, lam=1.0)
        d = avg - v
        d -= np.einsum("ij,ij->i", d, nrm)[:, None] * nrm
        v = v + 0.35 * d
        v = model.project(v, iters=2, max_step=0.002)
        set_verts(ob, v)
    fix_normals(ob)
    C.shade_smooth(ob, None)
    ntri = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print(f"build_mesh {name}: {len(ob.data.vertices)} verts, {ntri} tris")
    return ob


def _drop_small_islands(ob, min_frac=0.002):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        isl = []
        seen.add(v.index)
        while stack:
            x = stack.pop()
            isl.append(x)
            for e in x.link_edges:
                o = e.other_vert(x)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        islands.append(isl)
    total = len(bm.verts)
    kill = [v for isl in islands if len(isl) < total * min_frac for v in isl]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
        print(f"  dropped {len(kill)} verts in tiny islands")
    bm.to_mesh(ob.data)
    bm.free()


def triangulate(ob) -> None:
    m = ob.modifiers.new("Tri", "TRIANGULATE")
    m.quad_method = "SHORTEST_DIAGONAL"
    C.apply_modifiers(ob)


# ---------------------------------------------------------------------------
# Armature
# ---------------------------------------------------------------------------
def make_armature(name: str, bones: list, col=None) -> bpy.types.Object:
    """bones: list of (name, head, tail, parent | None, z_axis_hint | None). Blender space."""
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    (col or bpy.context.scene.collection).objects.link(ob)
    C.set_active(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for nm, hd, tl, par, zh in bones:
        b = eb.new(nm)
        b.head = Vector(hd)
        b.tail = Vector(tl)
        if zh is not None:
            b.align_roll(Vector(zh))
        b.use_deform = True
        if par:
            b.parent = eb[par]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "STICK"
    return ob


def bone_rest(arm_ob) -> dict:
    """bone -> (head (3,), 3x3 rest rotation in armature space)."""
    out = {}
    for b in arm_ob.data.bones:
        out[b.name] = (np.array(b.head_local), np.array(b.matrix_local.to_3x3()))
    return out


# ---------------------------------------------------------------------------
# Skinning from SDF primitives
# ---------------------------------------------------------------------------
def skin_weights(ob, model: S.Model, bone_names: list[str], extra_prims=(), smooth_iters=3,
                 max_influences=4) -> np.ndarray:
    v = get_verts(ob)
    prims = model.all_prims() + list(extra_prims)
    bidx = {b: i for i, b in enumerate(bone_names)}
    D = np.full((len(v), len(prims)), S.BIG)
    for j, pr in enumerate(prims):
        dc = S.length(v - pr.c) - pr.r
        m = dc < 0.15
        if m.any():
            D[m, j] = pr.fn(v[m])
    dmin = D.min(1, keepdims=True)
    W = np.zeros((len(v), len(bone_names)))
    for j, pr in enumerate(prims):
        w = np.exp(-np.clip(D[:, j] - dmin[:, 0], 0, None) / max(pr.soft, 1e-4))
        w[D[:, j] >= S.BIG * 0.5] = 0
        if isinstance(pr.bone, dict):
            for b, f in pr.bone.items():
                W[:, bidx[b]] += w * f
        else:
            W[:, bidx[pr.bone]] += w
    W /= np.maximum(W.sum(1, keepdims=True), 1e-12)
    if smooth_iters:
        W = laplacian(W, get_edges(ob), len(v), iters=smooth_iters, lam=0.5)
    return finalize_weights(W, max_influences)


def finalize_weights(W, max_influences=4):
    if W.shape[1] > max_influences:
        thr = -np.sort(-W, axis=1)[:, max_influences - 1:max_influences]
        W = np.where(W >= thr, W, 0.0)
    W = np.where(W < 0.01, 0.0, W)
    return W / np.maximum(W.sum(1, keepdims=True), 1e-12)


def apply_weights(ob, arm_ob, W: np.ndarray, bone_names: list[str]) -> None:
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    for j, b in enumerate(bone_names):
        idx = np.nonzero(W[:, j] > 0)[0]
        g = ob.vertex_groups.new(name=b)
        for i in idx:
            g.add([int(i)], float(W[i, j]), "REPLACE")
    ob.parent = arm_ob
    m = ob.modifiers.new("Armature", "ARMATURE")
    m.object = arm_ob


def rigid_bind(ob, arm_ob, bone: str) -> None:
    g = ob.vertex_groups.new(name=bone)
    g.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")
    ob.parent = arm_ob
    m = ob.modifiers.new("Armature", "ARMATURE")
    m.object = arm_ob


# ---------------------------------------------------------------------------
# UVs
# ---------------------------------------------------------------------------
def unwrap(ob, warp_centres=(), angle=60.0, margin=0.004) -> None:
    """Smart-UV with optional local magnification (centre, radius, factor) so faces/
    hands get more texels: the mesh is temporarily inflated around each centre."""
    v0 = get_verts(ob)
    v = v0.copy()
    for c, r, f in warp_centres:
        c = np.asarray(c)
        d = v - c
        dist = np.linalg.norm(d, axis=1)
        s = 1.0 + (f - 1.0) * np.exp(-(dist / r) ** 2)
        v = c + d * s[:, None]
    set_verts(ob, v)
    C.smart_uv(ob, angle, margin)
    C.set_active(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    except Exception as e:  # noqa
        print("pack_islands failed:", e)
    bpy.ops.object.mode_set(mode="OBJECT")
    set_verts(ob, v0)


# ---------------------------------------------------------------------------
# Surface-map baking (Cycles EMIT, 1 sample)
# ---------------------------------------------------------------------------
def _bake_emit(ob, size: int, kind: str, lo=None, hi=None, margin=6) -> np.ndarray:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.margin = margin
    sc.render.bake.use_clear = True
    mat = bpy.data.materials.new(f"_bake_{kind}")
    nt = mat.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "MULTIPLY_ADD"
    if kind == "position":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        lo = np.asarray(lo)
        span = np.asarray(hi) - lo
        nt.links.new(geo.outputs["Position"], vm.inputs[0])
        vm.inputs[1].default_value = tuple(1.0 / span)
        vm.inputs[2].default_value = tuple(-lo / span)
    elif kind == "normal":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        nt.links.new(geo.outputs["Normal"], vm.inputs[0])
        vm.inputs[1].default_value = (0.5, 0.5, 0.5)
        vm.inputs[2].default_value = (0.5, 0.5, 0.5)
    elif kind == "tangent":
        tg = nt.nodes.new("ShaderNodeTangent")
        tg.direction_type = "UV_MAP"
        tg.uv_map = ob.data.uv_layers.active.name
        nt.links.new(tg.outputs["Tangent"], vm.inputs[0])
        vm.inputs[1].default_value = (0.5, 0.5, 0.5)
        vm.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(vm.outputs[0], em.inputs["Color"])
    img = bpy.data.images.new(f"_bake_{kind}", size, size, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    old = [s.material for s in ob.material_slots]
    if not ob.material_slots:
        ob.data.materials.append(mat)
    for s in ob.material_slots:
        s.material = mat
    C.set_active(ob)
    bpy.ops.object.bake(type="EMIT")
    arr = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape(size, size, 4).astype(np.float64)
    for s, m in zip(ob.material_slots, old):
        s.material = m
    bpy.data.images.remove(img)
    bpy.data.materials.remove(mat)
    return arr


def _coverage(ob, size: int) -> np.ndarray:
    """Texels covered by a UV triangle (before bake margin), via a tiny numpy rasteriser."""
    me = ob.data
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2) * size
    mask = np.zeros((size, size), bool)
    me.calc_loop_triangles()
    lt = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("loops", lt)
    tri = uv[lt.reshape(-1, 3)]
    for a, b, c in tri:
        x0 = int(max(math.floor(min(a[0], b[0], c[0])), 0))
        x1 = int(min(math.ceil(max(a[0], b[0], c[0])), size - 1))
        y0 = int(max(math.floor(min(a[1], b[1], c[1])), 0))
        y1 = int(min(math.ceil(max(a[1], b[1], c[1])), size - 1))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
        l3 = 1 - l1 - l2
        e = -0.02
        inside = (l1 >= e) & (l2 >= e) & (l3 >= e)
        mask[y0:y1 + 1, x0:x1 + 1] |= inside
    return mask


class SurfaceMaps:
    """Per-texel surface samples of a UV'd mesh: P (object space), N, T, B, valid mask."""

    def __init__(self, ob, size: int, margin: int = 6):
        t0 = time.time()
        lo = get_verts(ob).min(0) - 0.01
        hi = get_verts(ob).max(0) + 0.01
        pos = _bake_emit(ob, size, "position", lo, hi, margin)
        nrm = _bake_emit(ob, size, "normal", margin=margin)
        tan = _bake_emit(ob, size, "tangent", margin=margin)
        self.size = size
        self.valid = _coverage(ob, size)
        v = self.valid
        self.P = lo + pos[..., :3][v] * (hi - lo)
        N = nrm[..., :3][v] * 2 - 1
        self.N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        T = tan[..., :3][v] * 2 - 1
        T -= np.einsum("ij,ij->i", T, self.N)[:, None] * self.N
        self.T = T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        self.B = np.cross(self.N, self.T)
        yy, xx = np.nonzero(v)
        self.uv = np.stack([(xx + 0.5) / size, (yy + 0.5) / size], 1)
        self.idx = (yy, xx)
        print(f"SurfaceMaps {size}: {v.sum()} texels in {time.time() - t0:.1f}s")

    def image(self, values, fill=0.0) -> np.ndarray:
        values = np.asarray(values)
        shape = (self.size, self.size) + values.shape[1:]
        out = np.full(shape, fill, np.float64)
        out[self.idx] = values
        return out


def save_rgb(path: str, arr: np.ndarray, quality: int = 90) -> str:
    """Write an (H, W[, 3]) array in [0,1] (row 0 = bottom, Blender convention) as PNG/JPEG."""
    a = np.clip(np.asarray(arr, np.float64), 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, -1)
    hgt, wid = a.shape[:2]
    rgba = np.concatenate([a, np.ones((hgt, wid, 1))], -1).astype(np.float32)
    img = bpy.data.images.new("_save_tmp", wid, hgt, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color"
    img.pixels.foreach_set(rgba.ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = "JPEG" if path.endswith(".jpg") else "PNG"
    img.save(filepath=path, quality=quality)
    bpy.data.images.remove(img)
    return path


def srgb(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def lin(srgb_v):
    s = np.asarray(srgb_v, np.float64)
    return np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4)


def tangent_normal(sm: SurfaceMaps, n_obj: np.ndarray, height_fn=None, strength=1.0, eps=4e-4) -> np.ndarray:
    """Object-space detail normal -> tangent space, plus an optional 3D height function
    (metres) whose tangential gradient perturbs the normal. Returns (K,3) in [-1,1]."""
    n = n_obj
    if height_fn is not None:
        hT = (height_fn(sm.P + sm.T * eps) - height_fn(sm.P - sm.T * eps)) / (2 * eps)
        hB = (height_fn(sm.P + sm.B * eps) - height_fn(sm.P - sm.B * eps)) / (2 * eps)
        n = n - strength * (hT[:, None] * sm.T + hB[:, None] * sm.B)
        n = n / np.linalg.norm(n, axis=1, keepdims=True)
    ts = np.stack([np.einsum("ij,ij->i", n, sm.T), np.einsum("ij,ij->i", n, sm.B),
                   np.einsum("ij,ij->i", n, sm.N)], 1)
    ts[:, 2] = np.maximum(ts[:, 2], 0.05)
    return ts / np.linalg.norm(ts, axis=1, keepdims=True)


def dilate(img: np.ndarray, valid: np.ndarray, px: int = 8) -> np.ndarray:
    """Push edge texels outward so mip-maps / bilinear filtering do not pull in black."""
    out = img.copy()
    m = valid.copy()
    for _ in range(px):
        acc = np.zeros_like(out)
        cnt = np.zeros(m.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = np.roll(m, (dy, dx), (0, 1))
            so = np.roll(out, (dy, dx), (0, 1))
            acc[sm] += so[sm]
            cnt[sm] += 1
        grow = (~m) & (cnt > 0)
        if not grow.any():
            break
        out[grow] = acc[grow] / cnt[grow][..., None] if out.ndim == 3 else acc[grow] / cnt[grow]
        m = m | grow
    # fill the rest with the mean so mips stay sane
    if (~m).any():
        out[~m] = out[valid].mean(0)
    return out


# ---------------------------------------------------------------------------
# glTF material with ORM + occlusion
# ---------------------------------------------------------------------------
def _gltf_output_group():
    g = bpy.data.node_groups.get("glTF Material Output")
    if g is None:
        g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        g.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def pbr_material(name: str, albedo: str, normal: str | None, orm: str | None,
                 normal_strength: float = 1.0, subsurface: float = 0.0, sss_radius=(1.0, 0.35, 0.2),
                 sheen: float = 0.0, alpha_clip: bool = False, spec: float = 0.5) -> bpy.types.Material:
    m = C.image_material(name, albedo=albedo, normal=normal, orm=orm, normal_strength=normal_strength,
                         alpha_clip=alpha_clip)
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Specular IOR Level"].default_value = spec
    if subsurface > 0:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
        bsdf.inputs["Subsurface Radius"].default_value = sss_radius
        bsdf.inputs["Subsurface Scale"].default_value = 0.01
    if sheen > 0:
        bsdf.inputs["Sheen Weight"].default_value = sheen
        bsdf.inputs["Sheen Roughness"].default_value = 0.5
    if orm:
        tex = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image.filepath.endswith(os.path.basename(orm)))
        sep = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeSeparateColor")
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = _gltf_output_group()
        grp.location = (200, -400)
        nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    if alpha_clip:
        try:
            m.blend_method = "CLIP"
        except Exception:  # noqa
            pass
        m.surface_render_method = "DITHERED"
    return m


# ---------------------------------------------------------------------------
# Export / helpers
# ---------------------------------------------------------------------------
def export(path: str, arm_ob, meshes) -> str:
    for o in bpy.context.scene.objects:
        if o.type == "ARMATURE" and o.animation_data:
            o.animation_data.action = None
    for o in meshes:
        o.parent = arm_ob
    return C.export_glb(path, objects=[arm_ob], animations=True)


def clean_temp_objects(keep):
    keep = set(keep)
    for o in list(bpy.context.scene.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)


def eye_mesh(name: str, centre, radius: float, forward=(0, -1, 0), segs=24, rings=16):
    """UV sphere with its pole along `forward`; UV = planar front projection
    (u, v in [0,1], iris in the middle) so a small iris texture maps cleanly."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    uvl = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for l in f.loops:
            co = l.vert.co
            l[uvl].uv = (0.5 + 0.5 * co.x / radius, 0.5 + 0.5 * co.y / radius)
    # sphere's +Z pole -> forward
    R = Vector((0, 0, 1)).rotation_difference(Vector(forward)).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=R, verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(centre), verts=bm.verts)
    ob = C.mesh_from_bmesh(name, bm)
    C.shade_smooth(ob, None)
    return ob


def tri_count(ob) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ---------------------------------------------------------------------------
# Texture synthesis driver
# ---------------------------------------------------------------------------
def _upsample(img: np.ndarray, size: int) -> np.ndarray:
    """Bilinear resize of a square image (numpy only)."""
    n = img.shape[0]
    if n == size:
        return img
    x = (np.arange(size) + 0.5) * n / size - 0.5
    x0 = np.clip(np.floor(x).astype(int), 0, n - 1)
    x1 = np.clip(x0 + 1, 0, n - 1)
    f = np.clip(x - x0, 0, 1)
    rows = img[x0] * (1 - f)[:, None] + img[x1] * f[:, None] if img.ndim == 2 else \
        img[x0] * (1 - f)[:, None, None] + img[x1] * f[:, None, None]
    out = rows[:, x0] * (1 - f)[None, :] + rows[:, x1] * f[None, :] if img.ndim == 2 else \
        rows[:, x0] * (1 - f)[None, :, None] + rows[:, x1] * f[None, :, None]
    return out


def synthesize_textures(ob, model: S.Model, tex, out_prefix: str, alb_size=2048, nrm_size=1024,
                        normal_strength=1.0, ao_strength=1.0, jpeg_q=90) -> dict:
    """Bake surface samples and write <prefix>_albedo.jpg, _normal.png, _orm.jpg.
    tex: object with albedo_rough(P, N, lab, ao) -> (alb_lin, rough, metal) and height(P, lab)."""
    t0 = time.time()
    # detail resolution: normals, AO, roughness
    sm1 = SurfaceMaps(ob, nrm_size)
    lab1 = model.labels(sm1.P)
    n_hi = model.gradient(sm1.P)
    # keep the low-poly normal where the SDF gradient is unreliable (thin parts, carve seams)
    bad = np.einsum("ij,ij->i", n_hi, sm1.N) < 0.2
    n_hi[bad] = sm1.N[bad]
    ao1 = model.ao(sm1.P, n_hi, strength=ao_strength)
    nts = tangent_normal(sm1, n_hi, lambda P: tex.height(P, lab1), strength=normal_strength)
    print(f"  detail maps {time.time() - t0:.1f}s")
    _, rough1, metal1 = tex.albedo_rough(sm1.P, n_hi, lab1, ao1)
    nimg = dilate(sm1.image(nts * 0.5 + 0.5, fill=0.5), sm1.valid, 8)
    orm = np.stack([sm1.image(ao1, 1.0), sm1.image(rough1, 0.6), sm1.image(metal1, 0.0)], -1)
    orm = dilate(orm, sm1.valid, 8)
    ao_img = dilate(sm1.image(ao1, 1.0), sm1.valid, 8)
    # colour resolution
    sm2 = SurfaceMaps(ob, alb_size) if alb_size != nrm_size else sm1
    lab2 = model.labels(sm2.P) if sm2 is not sm1 else lab1
    ao2 = _upsample(ao_img, alb_size)[sm2.idx]
    alb, _, _ = tex.albedo_rough(sm2.P, sm2.N, lab2, ao2)
    aimg = dilate(sm2.image(srgb(alb)), sm2.valid, 12)
    paths = {
        "albedo": save_rgb(out_prefix + "_albedo.jpg", aimg, jpeg_q),
        "normal": save_rgb(out_prefix + "_normal.png", nimg),
        "orm": save_rgb(out_prefix + "_orm.jpg", orm, 92),
    }
    print(f"  textures written in {time.time() - t0:.1f}s")
    return paths
