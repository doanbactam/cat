"""Game-mesh retopology for Cam: dense SDF mesh -> quad-dominant ~19k-quad skin.

Pipeline: merge micro edges -> density warp (face x1.6, paws x1.35) -> QuadriFlow
(with X symmetry, mesh scaled x1000 because QuadriFlow's degeneracy test is unit
dependent) -> unwarp -> consistent outward normals -> Newton projection onto the
SDF + tangential relaxation (2 rounds)."""
from __future__ import annotations

import time

import bmesh
import bpy
import numpy as np

import cat_anatomy as A
import cat_mesh as M
import cat_sdf as S
import common as C


def warp_centres():
    face = A.head_to_world((0.0, -0.205, 0.240))
    eyes_l = A.head_to_world(A.EYE_L)
    paws = [A.FINGER_L, A.TOE_L]
    cs = [(face, 0.034, 1.55), (eyes_l, 0.012, 1.25), ((-eyes_l[0], eyes_l[1], eyes_l[2]), 0.012, 1.25)]
    for p in paws:
        for sx in (1, -1):
            cs.append(((p[0] * sx, p[1], 0.012), 0.020, 1.35))
    return cs


def relax_project(ob, rounds: int = 2, lam: float = 0.45, smooth_iters: int = 3):
    v = M.get_verts(ob)
    edges = M.get_edges(ob)
    n = len(v)
    for _ in range(rounds):
        for _ in range(smooth_iters):
            nrm = M.vertex_normals(ob)
            avg = M.laplacian_smooth(v, edges, n, iters=1, lam=1.0)
            delta = avg - v
            delta -= np.einsum("ij,ij->i", delta, nrm)[:, None] * nrm   # tangential only
            v = v + lam * delta
            M.set_verts(ob, v)
        v = S.project(v, iters=3, max_step=0.0006)
        M.set_verts(ob, v)
    return ob


def fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def build_low(high_v: np.ndarray, high_q: np.ndarray, target_quads: int = 19000, seed: int = 3,
              name: str = "CatBody") -> bpy.types.Object:
    """Remesh the +X half with QuadriFlow (boundary preserved), snap the cut to x=0 and
    mirror-weld, so the skin is exactly symmetric and watertight along the midline."""
    t0 = time.time()
    cs = warp_centres()
    ob = M.mesh_from_arrays(name, M.warp(high_v, cs) * 1000.0, [high_q])
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.03)   # 30 um at x1000 scale
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=(0, 0, 0), plane_no=(1, 0, 0),
                           clear_inner=True, clear_outer=False)
    bm.to_mesh(ob.data)
    bm.free()
    C.set_active(ob)
    r = bpy.ops.object.quadriflow_remesh(target_faces=target_quads // 2, use_mesh_symmetry=False,
                                         use_preserve_sharp=False, use_preserve_boundary=True, seed=seed)
    if "FINISHED" not in r:
        raise RuntimeError("QuadriFlow failed")
    v = M.get_verts(ob)
    # snap the open boundary to the mirror plane
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bnd = {vv.index for e in bm.edges if e.is_boundary for vv in e.verts}
    bm.free()
    bnd = np.array(sorted(bnd), np.int64)
    print(f"  half remesh: {len(ob.data.polygons)} faces, boundary verts {len(bnd)}, max |x| {np.abs(v[bnd, 0]).max():.4f}")
    v[bnd, 0] = 0.0
    v = M.unwarp(v / 1000.0, cs)
    v[bnd, 0] = 0.0
    M.set_verts(ob, v)
    mir = ob.modifiers.new("Mirror", "MIRROR")
    mir.use_axis[0] = True
    mir.use_clip = True
    mir.use_mirror_merge = True
    mir.merge_threshold = 1e-6
    C.apply_modifiers(ob)
    fix_normals(ob)
    v = M.get_verts(ob)
    me = ob.data
    vol = 0.0
    for p in me.polygons:
        idx = list(p.vertices)
        a = v[idx[0]]
        for k in range(1, len(idx) - 1):
            vol += np.dot(a, np.cross(v[idx[k]], v[idx[k + 1]]))
    if vol < 0:
        me.flip_normals()
    bm = bmesh.new()
    bm.from_mesh(me)
    nb = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    relax_project(ob)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    quads = sum(1 for p in me.polygons if len(p.vertices) == 4)
    print(f"build_low: {len(me.polygons)} faces ({quads} quads) {tris} tris, non-manifold edges {nb}, "
          f"{time.time() - t0:.1f}s")
    return ob
