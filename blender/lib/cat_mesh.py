"""Mesh utilities for the cat: SDF meshing (openvdb), fast numpy<->Blender mesh I/O,
mesh-graph helpers (adjacency, Dijkstra seams, smoothing)."""
from __future__ import annotations

import heapq
import time

try:
    import bmesh
except ImportError:
    bmesh = None
try:
    import bpy
except ImportError:
    bpy = None
import numpy as np


# ---------------------------------------------------------------------------
# SDF -> mesh
# ---------------------------------------------------------------------------
def _eval_chunked(fn, pts, chunk=600_000):
    out = np.empty(len(pts), np.float64)
    for i in range(0, len(pts), chunk):
        out[i:i + chunk] = fn(pts[i:i + chunk])
    return out


def sdf_to_mesh(sdf, bmin, bmax, h: float, block: int = 8, margin: float = 2.2, adaptivity: float = 0.0):
    """Sample `sdf` on a block-sparse grid of voxel size h and extract the zero
    iso-surface with openvdb. Returns (verts (N,3), quads (Q,4), tris (T,3))."""
    import openvdb as vdb
    t0 = time.time()
    bmin = np.asarray(bmin, np.float64)
    bmax = np.asarray(bmax, np.float64)
    n = np.ceil((bmax - bmin) / h).astype(int) + 1
    n = ((n + block - 1) // block) * block
    nb = n // block
    bi = np.stack(np.meshgrid(np.arange(nb[0]), np.arange(nb[1]), np.arange(nb[2]), indexing="ij"), -1).reshape(-1, 3)
    centers = bmin + (bi * block + (block - 1) * 0.5) * h
    dc = _eval_chunked(sdf, centers)
    half_diag = block * h * 0.8660254
    keep = np.abs(dc) < half_diag * margin + 2 * h
    band = 3.0 * h
    signs = np.where(dc < 0, -band, band).astype(np.float32).reshape(tuple(nb))
    dense = np.repeat(np.repeat(np.repeat(signs, block, 0), block, 1), block, 2)
    kb = bi[keep]
    off = np.stack(np.meshgrid(np.arange(block), np.arange(block), np.arange(block), indexing="ij"), -1).reshape(-1, 3)
    per = max(1, 900_000 // len(off))
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
    print(f"sdf_to_mesh: grid {tuple(n)} blocks {keep.sum()}/{len(keep)} eval {t1 - t0:.1f}s mesh {time.time() - t1:.1f}s "
          f"-> {len(pts)} verts {len(quads)} quads {len(tris)} tris")
    quads = np.asarray(quads, np.int64)
    tris = np.asarray(tris, np.int64)
    # orient outward: positive signed volume
    vol = 0.0
    if len(quads):
        a, b, c, d4 = (pts[quads[:, k]] for k in range(4))
        vol += np.einsum("ij,ij->i", a, np.cross(b, c)).sum() + np.einsum("ij,ij->i", a, np.cross(c, d4)).sum()
    if len(tris):
        a, b, c = (pts[tris[:, k]] for k in range(3))
        vol += np.einsum("ij,ij->i", a, np.cross(b, c)).sum()
    if vol < 0:
        quads = quads[:, ::-1].copy()
        tris = tris[:, ::-1].copy()
    return pts, quads, tris


# ---------------------------------------------------------------------------
# numpy <-> Blender meshes
# ---------------------------------------------------------------------------
def mesh_from_arrays(name: str, verts: np.ndarray, faces: list[np.ndarray] | np.ndarray,
                     col: bpy.types.Collection | None = None) -> bpy.types.Object:
    """Create a mesh object from verts and face index arrays (list of (K,n) arrays)."""
    if isinstance(faces, np.ndarray):
        faces = [faces]
    faces = [f for f in faces if len(f)]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", np.asarray(verts, np.float32).ravel())
    loop_starts, loop_totals, loops = [], [], []
    start = 0
    for f in faces:
        k = f.shape[1]
        cnt = len(f)
        loop_starts.append(start + np.arange(cnt) * k)
        loop_totals.append(np.full(cnt, k))
        loops.append(f.ravel())
        start += cnt * k
    loop_starts = np.concatenate(loop_starts).astype(np.int32)
    loop_totals = np.concatenate(loop_totals).astype(np.int32)
    loops = np.concatenate(loops).astype(np.int32)
    me.loops.add(len(loops))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(loop_starts))
    me.polygons.foreach_set("loop_start", loop_starts)
    me.polygons.foreach_set("loop_total", loop_totals)
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def get_verts(ob: bpy.types.Object) -> np.ndarray:
    me = ob.data
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3).astype(np.float64)


def set_verts(ob: bpy.types.Object, v: np.ndarray) -> None:
    ob.data.vertices.foreach_set("co", np.asarray(v, np.float32).ravel())
    ob.data.update()


def get_edges(ob) -> np.ndarray:
    me = ob.data
    a = np.empty(len(me.edges) * 2, np.int32)
    me.edges.foreach_get("vertices", a)
    return a.reshape(-1, 2)


def vertex_normals(ob) -> np.ndarray:
    me = ob.data
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("normal", a)
    return a.reshape(-1, 3).astype(np.float64)


def adjacency(n: int, edges: np.ndarray):
    """CSR-style neighbour lists."""
    e = np.concatenate([edges, edges[:, ::-1]])
    order = np.argsort(e[:, 0], kind="stable")
    e = e[order]
    counts = np.bincount(e[:, 0], minlength=n)
    ptr = np.concatenate([[0], np.cumsum(counts)])
    return ptr, e[:, 1]


def laplacian_smooth(values: np.ndarray, edges: np.ndarray, n: int, iters: int = 10, lam: float = 0.5,
                     fixed: np.ndarray | None = None) -> np.ndarray:
    """Uniform-weight Laplacian smoothing of per-vertex values (N,) or (N,k)."""
    v = np.array(values, dtype=np.float64)
    deg = np.bincount(edges.ravel(), minlength=n).astype(np.float64)
    deg = np.maximum(deg, 1.0)
    for _ in range(iters):
        acc = np.zeros_like(v)
        np.add.at(acc, edges[:, 0], v[edges[:, 1]])
        np.add.at(acc, edges[:, 1], v[edges[:, 0]])
        avg = acc / (deg[:, None] if v.ndim == 2 else deg)
        nv = v + lam * (avg - v)
        if fixed is not None:
            nv[fixed] = v[fixed]
        v = nv
    return v


def dijkstra_path(verts: np.ndarray, edges: np.ndarray, src: int, dst: int, cost_fn=None) -> list[int]:
    """Shortest vertex path src->dst on the mesh graph. cost_fn(i, j) -> extra multiplier (>=1)."""
    n = len(verts)
    ptr, nbr = adjacency(n, edges)
    dist = np.full(n, np.inf)
    prev = np.full(n, -1, np.int64)
    dist[src] = 0.0
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == dst:
            break
        if d > dist[u]:
            continue
        for k in range(ptr[u], ptr[u + 1]):
            w = nbr[k]
            c = float(np.linalg.norm(verts[w] - verts[u]))
            if cost_fn is not None:
                c *= cost_fn(u, w)
            nd = d + c
            if nd < dist[w]:
                dist[w] = nd
                prev[w] = u
                heapq.heappush(pq, (nd, w))
    path = [dst]
    while path[-1] != src and prev[path[-1]] >= 0:
        path.append(int(prev[path[-1]]))
    return path[::-1]


def nearest_vertex(verts: np.ndarray, p) -> int:
    return int(np.argmin(np.einsum("ij,ij->i", verts - np.asarray(p), verts - np.asarray(p))))


def mark_seam_path(ob, path: list[int]) -> int:
    """Mark edges along a vertex path as UV seams. Returns number marked."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    cnt = 0
    for a, b in zip(path[:-1], path[1:]):
        e = bm.edges.get((bm.verts[a], bm.verts[b]))
        if e is not None:
            e.seam = True
            cnt += 1
    bm.to_mesh(ob.data)
    bm.free()
    return cnt


# ---------------------------------------------------------------------------
# Density warp: radial magnification around centres so a uniform remesher
# (QuadriFlow) puts more quads there.  m(r) = 1 + (s-1) exp(-(r/R)^2) is
# monotonic for s < 3.2, so the map is invertible (Newton per vertex).
# ---------------------------------------------------------------------------
def _radial(r, s, R):
    e = np.exp(-(r / R) ** 2)
    m = 1.0 + (s - 1.0) * e
    dm = (s - 1.0) * e * (-2.0 * r / (R * R))
    return m, dm


def warp(p: np.ndarray, centres) -> np.ndarray:
    p = np.array(p, dtype=np.float64)
    for c, R, s in centres:
        c = np.asarray(c, np.float64)
        q = p - c
        r = np.sqrt(np.einsum("ij,ij->i", q, q))
        m, _ = _radial(r, s, R)
        p = c + q * m[:, None]
    return p


def unwarp(p: np.ndarray, centres) -> np.ndarray:
    p = np.array(p, dtype=np.float64)
    for c, R, s in reversed(list(centres)):
        c = np.asarray(c, np.float64)
        q = p - c
        rp = np.sqrt(np.einsum("ij,ij->i", q, q))
        r = rp / s
        for _ in range(30):
            m, dm = _radial(r, s, R)
            f = r * m - rp
            r = np.maximum(r - f / (m + r * dm), 0.0)
        ratio = np.where(rp > 1e-12, r / np.maximum(rp, 1e-12), 1.0 / s)
        p = c + q * ratio[:, None]
    return p
