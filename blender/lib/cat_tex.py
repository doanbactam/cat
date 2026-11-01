"""numpy texture synthesis for Cam: noise, iris, whisker/tuft atlas, and (from baked
position/normal maps) the tabby albedo, roughness, fur mask/flow, NPC variants.

Images are float arrays (H, W, C) in [0,1], row 0 = TOP (as PNG); conversions to
Blender pixel order (row 0 = bottom) happen in save/load helpers."""
from __future__ import annotations

import math
import os

import numpy as np

# ---------------------------------------------------------------------------
# colour helpers
# ---------------------------------------------------------------------------


def srgb_to_lin(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hexc(h: str):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    t = np.asarray(t)
    if t.ndim and np.ndim(a) and np.shape(a)[-1:] == (3,) and t.shape[-1:] != (3,):
        t = t[..., None]
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# noise (vectorised Perlin gradient noise, 3D)
# ---------------------------------------------------------------------------
_GRAD = np.array([[1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0], [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
                  [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1], [1, 1, 0], [-1, 1, 0], [0, -1, 1], [0, -1, -1]],
                 np.float64)


def _hash(ix, iy, iz, seed):
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (iz.astype(np.int64) * 83492791) ^ (seed * 2654435761)
    h = h & 0xFFFFFFFF
    h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    h = ((h ^ (h >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return h


def perlin3(p: np.ndarray, seed: int = 0) -> np.ndarray:
    """p: (N,3). Returns ~[-1,1]."""
    p = np.asarray(p, np.float64)
    pi = np.floor(p)
    pf = p - pi
    pi = pi.astype(np.int64)
    w = pf * pf * pf * (pf * (pf * 6 - 15) + 10)
    out = np.zeros(len(p))
    res = {}
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                h = _hash(pi[:, 0] + dx, pi[:, 1] + dy, pi[:, 2] + dz, seed) & 15
                g = _GRAD[h]
                d = pf - np.array([dx, dy, dz], np.float64)
                res[(dx, dy, dz)] = np.einsum("ij,ij->i", g, d)
    x0 = res[(0, 0, 0)] + w[:, 0] * (res[(1, 0, 0)] - res[(0, 0, 0)])
    x1 = res[(0, 1, 0)] + w[:, 0] * (res[(1, 1, 0)] - res[(0, 1, 0)])
    x2 = res[(0, 0, 1)] + w[:, 0] * (res[(1, 0, 1)] - res[(0, 0, 1)])
    x3 = res[(0, 1, 1)] + w[:, 0] * (res[(1, 1, 1)] - res[(0, 1, 1)])
    y0 = x0 + w[:, 1] * (x1 - x0)
    y1 = x2 + w[:, 1] * (x3 - x2)
    out = y0 + w[:, 2] * (y1 - y0)
    return out * 1.15


def fbm3(p, octaves=4, lac=2.0, gain=0.5, seed=0):
    amp, tot, s = 1.0, 0.0, np.zeros(len(p))
    q = np.asarray(p, np.float64)
    for o in range(octaves):
        s += amp * perlin3(q, seed + o * 17)
        tot += amp
        amp *= gain
        q = q * lac
    return s / tot


def noise2(u, v, seed=0):
    """2D Perlin on arrays u, v (any shape)."""
    sh = np.shape(u)
    p = np.stack([np.ravel(u), np.ravel(v), np.full(np.size(u), 0.37)], 1)
    return perlin3(p, seed).reshape(sh)


def fbm2(u, v, octaves=4, seed=0, gain=0.5):
    amp, tot = 1.0, 0.0
    s = np.zeros(np.shape(u))
    for o in range(octaves):
        s += amp * noise2(u * (2 ** o), v * (2 ** o), seed + o * 31)
        tot += amp
        amp *= gain
    return s / tot


# ---------------------------------------------------------------------------
# image IO (PNG via Blender image API so this works inside Blender's python)
# ---------------------------------------------------------------------------
def save_png(path: str, img: np.ndarray, srgb: bool = True, alpha: bool = False, bits16: bool = False):
    import bpy
    img = np.asarray(img, np.float32)
    h, w = img.shape[:2]
    if img.ndim == 2:
        img = np.repeat(img[:, :, None], 3, 2)
    if img.shape[2] == 3:
        img = np.concatenate([img, np.ones((h, w, 1), np.float32)], 2)
    name = "_tmp_save"
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    bimg = bpy.data.images.new(name, w, h, alpha=alpha, float_buffer=bits16)
    # values are already encoded (sRGB done in numpy): always write the raw buffer,
    # otherwise save_render would bake the scene view transform (AgX) into the file
    bimg.colorspace_settings.name = "Non-Color"
    bimg.pixels.foreach_set(np.ascontiguousarray(img[::-1]).ravel())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bimg.filepath_raw = path
    bimg.file_format = "PNG"
    sc = None
    try:
        import bpy as _b
        sc = _b.context.scene
        settings = sc.render.image_settings
        old = (settings.color_depth, settings.color_mode, settings.compression)
        settings.color_depth = "16" if bits16 else "8"
        settings.color_mode = "RGBA" if alpha else "RGB"
        settings.compression = 90
        bimg.save_render(path, scene=sc)
        settings.color_depth, settings.color_mode, settings.compression = old
    except Exception:
        bimg.save()
    bpy.data.images.remove(bimg)
    return path


def save_jpg(path: str, img: np.ndarray, quality: int = 92):
    import bpy
    img = np.asarray(img, np.float32)
    h, w = img.shape[:2]
    rgba = np.concatenate([img[:, :, :3], np.ones((h, w, 1), np.float32)], 2)
    bimg = bpy.data.images.new("_tmp_jpg", w, h)
    bimg.colorspace_settings.name = "Non-Color"
    bimg.pixels.foreach_set(np.ascontiguousarray(rgba[::-1]).ravel())
    sc = bpy.context.scene
    s = sc.render.image_settings
    old = (s.file_format, s.quality, s.color_mode)
    s.file_format = "JPEG"
    s.quality = quality
    s.color_mode = "RGB"
    bimg.save_render(path, scene=sc)
    s.file_format, s.quality, s.color_mode = old
    bpy.data.images.remove(bimg)
    return path


def load_image_np(path: str, linear: bool = True) -> np.ndarray:
    import bpy
    im = bpy.data.images.load(path, check_existing=False)
    if linear:
        im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1].copy()


# ---------------------------------------------------------------------------
# Eye iris
# ---------------------------------------------------------------------------
def iris_texture(size: int = 1024, seed: int = 7, palette: str = "cam") -> np.ndarray:
    """Planar eye texture: iris radius = 0.5*sin(50deg) of the half-size (see cat_parts)."""
    y, x = np.mgrid[0:size, 0:size]
    u = (x + 0.5) / size - 0.5
    v = 0.5 - (y + 0.5) / size
    r = np.sqrt(u * u + v * v)
    th = np.arctan2(v, u)
    r_l = 0.5 * math.sin(math.radians(50))
    rn = r / r_l
    pal = {
        "cam": (hexc("a9bd3a"), hexc("eeb52c"), hexc("d98c1a"), hexc("5e3a0e")),     # green-gold -> amber
        "green": (hexc("9db84a"), hexc("b7c25a"), hexc("8a9a36"), hexc("4a5520")),
        "copper": (hexc("d9902e"), hexc("e3a33c"), hexc("b8701f"), hexc("6a3d12")),
        "blue": (hexc("9fc3d8"), hexc("7fa9c9"), hexc("5f87ab"), hexc("2f4458")),
    }[palette]
    inner, mid, outer, edge = (srgb_to_lin(c) for c in pal)
    # radial fibre field
    ang = (th / (2 * math.pi) + 0.5)
    fib = fbm2(ang * 120.0, rn * 2.5, octaves=3, seed=seed) * 0.55 + fbm2(ang * 340.0, rn * 7.0, 2, seed + 5) * 0.45
    crypt = fbm2(u * 38.0, v * 38.0, 3, seed + 9)
    t = np.clip(rn, 0, 1)
    col = np.where((t < 0.45)[..., None], lerp(inner, mid, smoothstep(0.15, 0.45, t)), lerp(mid, outer, smoothstep(0.45, 0.92, t)))
    col = col * (1.0 + 0.48 * fib[..., None])
    col = col * (1.0 - 0.35 * smoothstep(0.25, 0.55, crypt)[..., None])
    # collarette (jagged ring ~ 0.42)
    jag = 0.42 + 0.03 * noise2(ang * 24.0, np.zeros_like(ang), seed + 3)
    coll = np.exp(-((rn - jag) / 0.025) ** 2)
    col = col * (1.0 + 0.35 * coll[..., None])
    # limbal ring + darkening to the edge
    col = lerp(col, edge * 0.35, smoothstep(0.80, 1.0, t))
    # pupil: vertical slit (lens-shaped), soft edge
    ph = 0.80 * r_l
    pw = 0.11 * r_l
    sl = np.clip(1.0 - (v / ph) ** 2, 0, 1)
    pupil_d = np.abs(u) - pw * np.sqrt(sl)
    pupil = 1.0 - smoothstep(-0.003, 0.004, pupil_d)
    pupil *= (np.abs(v) < ph)
    # dark rim around the pupil
    col = col * (1.0 - 0.45 * np.exp(-np.maximum(pupil_d, 0) / 0.012)[..., None] * (np.abs(v) < ph)[..., None])
    col = lerp(col, np.array([0.004, 0.004, 0.005]), pupil)
    # sclera beyond the limbus (rarely visible on cats): warm off-white with veins
    sclera = srgb_to_lin(hexc("d8cbb3")) * (0.85 + 0.15 * fbm2(u * 20, v * 20, 2, seed + 11)[..., None])
    veins = smoothstep(0.62, 0.75, 1 - np.abs(fbm2(u * 9, v * 9, 3, seed + 21))) * smoothstep(1.05, 1.4, rn)
    sclera = lerp(sclera, srgb_to_lin(hexc("a0503c")), 0.35 * veins)
    out = lerp(col, sclera, smoothstep(1.0, 1.04, rn))
    return lin_to_srgb(out)


# ---------------------------------------------------------------------------
# Whisker / tuft atlas (RGBA): u<0.5 whisker strip, u>=0.5 ear-furnishing tuft
# ---------------------------------------------------------------------------
def whisker_atlas(w: int = 256, h: int = 1024, seed: int = 3, tint=(0.93, 0.91, 0.86)) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w]
    u = (x + 0.5) / w
    v = 1.0 - (y + 0.5) / h            # v=0 root .. 1 tip (image bottom = root)
    img = np.zeros((h, w, 4))
    # whisker: tapered line, slightly translucent towards the tip, darker root
    uw = u / 0.5
    half = 0.36 * (1.0 - 0.75 * v)
    a = 1.0 - smoothstep(half * 0.55, half, np.abs(uw - 0.5))
    a *= 1.0 - smoothstep(0.92, 1.0, v)
    col_root = srgb_to_lin(np.array([0.55, 0.45, 0.36]))
    col = lerp(col_root, srgb_to_lin(np.array(tint)), smoothstep(0.0, 0.12, v))
    left = u < 0.5
    img[..., :3] = np.where(left[..., None], col, srgb_to_lin(np.array(tint)))   # no black bleed into mips
    img[..., 3] = np.where(left, a, 0)
    # tuft: many fine strands converging to the root, wavy
    ut = (u - 0.5) / 0.5
    acc = np.zeros_like(u)
    rng = np.random.default_rng(seed)
    for _ in range(46):
        x0 = rng.uniform(0.08, 0.92)
        bend = rng.uniform(-0.12, 0.12)
        length = rng.uniform(0.55, 1.0)
        wid = rng.uniform(0.006, 0.012)
        cx = 0.5 + (x0 - 0.5) * v + bend * v * v
        d = np.abs(ut - cx)
        strand = (1 - smoothstep(wid * 0.4, wid, d)) * (v < length) * (1 - smoothstep(length * 0.7, length, v))
        acc = np.maximum(acc, strand * rng.uniform(0.6, 1.0))
    tuft_col = srgb_to_lin(np.array([0.92, 0.88, 0.80]))
    right = ~left
    img[..., :3] = np.where(right[..., None], tuft_col * (0.85 + 0.15 * v[..., None]), img[..., :3])
    img[..., 3] = np.where(right, acc, img[..., 3])
    out = img.copy()
    out[..., :3] = lin_to_srgb(img[..., :3])
    return out


# ===========================================================================
# Baking helpers (Blender): position / normal / part-id maps of the rest pose
# ===========================================================================
def _emit_material(name, build):
    import bpy
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != "ShaderNodeOutputMaterial":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    build(nt, em)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


def bake_emit_maps(ob, size: int):
    """Returns dict of float arrays (H,W,4), row 0 = top: pos, nrm, part. Alpha of `pos`
    = coverage (baked with margin 0)."""
    import bpy
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.use_clear = True
    sc.render.bake.margin = 0
    old = list(ob.data.materials)
    results = {}

    def pos_b(nt, em):
        g = nt.nodes.new("ShaderNodeNewGeometry")
        nt.links.new(g.outputs["Position"], em.inputs["Color"])

    def nrm_b(nt, em):
        g = nt.nodes.new("ShaderNodeNewGeometry")
        vm = nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY_ADD"
        vm.inputs[1].default_value = (0.5, 0.5, 0.5)
        vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(g.outputs["True Normal"], vm.inputs[0])
        nt.links.new(vm.outputs[0], em.inputs["Color"])

    def part_b(nt, em):
        a = nt.nodes.new("ShaderNodeAttribute")
        a.attribute_name = "part_id"
        nt.links.new(a.outputs["Color"], em.inputs["Color"])

    for key, fn in (("pos", pos_b), ("nrm", nrm_b), ("part", part_b)):
        mat = _emit_material("_bake_" + key, fn)
        ob.data.materials.clear()
        ob.data.materials.append(mat)
        img = bpy.data.images.new("_bake_" + key, size, size, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 0)
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.nodes.active = node
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.bake(type="EMIT", margin=0, use_clear=True)
        a = np.empty(size * size * 4, np.float32)
        img.pixels.foreach_get(a)
        results[key] = a.reshape(size, size, 4)[::-1].copy()
        bpy.data.images.remove(img)
        bpy.data.materials.remove(mat)
    ob.data.materials.clear()
    for m in old:
        ob.data.materials.append(m)
    return results


def dilate(img: np.ndarray, mask: np.ndarray, iters: int = 16) -> np.ndarray:
    """Fill texels outside `mask` from covered neighbours (bake margin)."""
    img = img.copy()
    m = mask.copy()
    for _ in range(iters):
        acc = np.zeros_like(img)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sm = np.roll(np.roll(m, dy, 0), dx, 1)
            si = np.roll(np.roll(img, dy, 0), dx, 1)
            acc += si * (sm[..., None] if img.ndim == 3 else sm)
            cnt += sm
        new = (~m) & (cnt > 0)
        if not new.any():
            break
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        m = m | new
    return img


def tangent_frames(pos: np.ndarray, nrm: np.ndarray, cov: np.ndarray):
    """Per-texel unit T (dP/du), B (dP/dv, made orthogonal) from the position map.
    Image row 0 = v=1, so dP/dv = P[r-1] - P[r+1]."""
    P = pos[..., :3]
    du = np.roll(P, -1, 1) - np.roll(P, 1, 1)
    dv = np.roll(P, 1, 0) - np.roll(P, -1, 0)
    ok_u = cov & np.roll(cov, -1, 1) & np.roll(cov, 1, 1)
    ok_v = cov & np.roll(cov, 1, 0) & np.roll(cov, -1, 0)
    du[~ok_u] = 0
    dv[~ok_v] = 0
    N = nrm[..., :3]
    T = du - np.sum(du * N, -1, keepdims=True) * N
    T /= np.linalg.norm(T, axis=-1, keepdims=True) + 1e-12
    B = np.cross(N, T)
    sgn = np.sign(np.sum(B * dv, -1, keepdims=True))
    sgn[sgn == 0] = 1
    B *= sgn
    texel = 0.5 * (np.linalg.norm(du, axis=-1) + np.linalg.norm(dv, axis=-1)) * 0.5
    return T, B, texel, ok_u & ok_v
