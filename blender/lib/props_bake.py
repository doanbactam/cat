"""Street-props build pipeline: registry -> model -> unwrap -> bake -> GLB (+ external textures) -> catalog.

A prop builder is registered with @prop(...) (or register(...)) and returns a dict:
    {"parts": [mesh objects with props_nodes materials],      # joined & baked into one texture set
     "glass": [objects with glass_material / unbaked],          # optional, exported as-is
     "colliders": [G.col_box(...)...], "markers": [G.marker(...)],
     "label": "/abs/label_sheet.png" (optional), "meta": {...catalog extras...}}

Baking (Cycles CPU): 1) geometry masks (AO / convex edge / cavity) -> shared mask image,
2) albedo (EMIT of Base Color), 3) ORM (EMIT: R=AO, G=roughness, B=metallic), 4) tangent normal.
Final materials: "<id>" (opaque), "<id>__2s" (double sided), "<id>__lit" (night emissive) all sharing
the three textures in assets/textures/props/. Unbaked transparent parts use "glass_*" materials.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import struct
import sys
import time
import traceback

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import props_geo as G  # noqa: E402
import props_nodes as PN  # noqa: E402

ROOT = C.ROOT
MODEL_DIR = os.path.join(ROOT, "assets", "models", "props")
TEX_DIR = os.path.join(ROOT, "assets", "textures", "props")
CACHE_DIR = os.path.join(ROOT, "qa", "out", "street-props", "cache")
CATALOG = os.path.join(MODEL_DIR, "catalog.json")
TEX_REL = "../../textures/props"
POST_IMPORT = "res://assets/models/props/_import/props_post_import.gd"

REG: dict[str, dict] = {}
CATEGORY_ORDER = ["street", "utility", "sign", "container", "stall", "furniture", "home", "plant",
                  "festival", "clutter", "item"]


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
def register(id: str, fn, *, category: str, kind: str | None = None, dynamic=False, mass=0.0,
             surface="plastic", material_kind: str | None = None, name_key: str | None = None,
             grounded=True, density=1024.0, max_tex=2048, min_tex=512, ao_dist=None, edge_r=None,
             tags=(), variant_of: str | None = None, item_id: str | None = None, file: str | None = None,
             args: dict | None = None, **extra):
    REG[id] = dict(id=id, fn=fn, category=category, kind=kind or category, dynamic=dynamic, mass=mass,
                   surface=surface, material_kind=material_kind or surface, name_key=name_key,
                   grounded=grounded, density=density, max_tex=max_tex, min_tex=min_tex, ao_dist=ao_dist,
                   edge_r=edge_r, tags=list(tags), variant_of=variant_of, item_id=item_id,
                   file=file or f"{id}.glb", args=args or {}, extra=extra)
    return fn


def prop(id: str, **kw):
    def deco(fn):
        register(id, fn, **kw)
        return fn
    return deco


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _find(nt, idname):
    return next((n for n in nt.nodes if n.bl_idname == idname), None)


def _src(sock):
    return sock.links[0].from_socket if sock.is_linked else None


def _cycles(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    try:
        sc.render.threads_mode = "AUTO"
    except Exception:
        pass


def _new_img(name, size, non_color=False, alpha=False):
    old = bpy.data.images.get(name)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def _bake_into(ob, img, btype, samples, margin):
    sc = bpy.context.scene
    _cycles(samples)
    tmp = []
    for slot in ob.material_slots:
        m = slot.material
        if m is None:
            continue
        n = m.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        n.label = "_bake_target"
        m.node_tree.nodes.active = n
        tmp.append((m, n))
    bk = sc.render.bake
    bk.margin = margin
    bk.margin_type = "EXTEND"
    bk.use_clear = True
    bk.use_selected_to_active = False
    bk.target = "IMAGE_TEXTURES"
    C.set_active(ob)
    if btype == "NORMAL":
        bk.normal_space = "TANGENT"
        bpy.ops.object.bake(type="NORMAL")
    else:
        bpy.ops.object.bake(type="EMIT")
    for m, n in tmp:
        m.node_tree.nodes.remove(n)


def _route_emission(mat, builder):
    """Temporarily route `builder(nt, bsdf) -> socket` into an Emission shader on the output."""
    nt = mat.node_tree
    out = _find(nt, "ShaderNodeOutputMaterial")
    bsdf = _find(nt, "ShaderNodeBsdfPrincipled")
    prev = _src(out.inputs["Surface"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    sock = builder(nt, bsdf)
    if isinstance(sock, bpy.types.NodeSocket):
        nt.links.new(sock, em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = sock
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return (mat, em, prev)


def _restore(routes):
    for mat, em, prev in routes:
        nt = mat.node_tree
        out = _find(nt, "ShaderNodeOutputMaterial")
        nt.nodes.remove(em)
        if prev is not None:
            nt.links.new(prev, out.inputs["Surface"])


def _val_or_src(nt, sock, scalar=True):
    s = _src(sock)
    if s is not None:
        return s
    v = nt.nodes.new("ShaderNodeValue")
    v.outputs[0].default_value = sock.default_value if scalar else 0.0
    return v.outputs[0]


def _albedo_builder(nt, bsdf):
    s = _src(bsdf.inputs["Base Color"])
    return s if s is not None else tuple(bsdf.inputs["Base Color"].default_value)


def _orm_builder(nt, bsdf):
    comb = nt.nodes.new("ShaderNodeCombineColor")
    mk = next((n for n in nt.nodes if n.label == "PROPS_MASK"), None)
    if mk is not None:
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(mk.outputs["Color"], sep.inputs["Color"])
        # gentle curve: AO in the ORM is used only for ambient light in Godot
        p = nt.nodes.new("ShaderNodeMath")
        p.operation = "POWER"
        nt.links.new(sep.outputs[0], p.inputs[0])
        p.inputs[1].default_value = 0.8
        nt.links.new(p.outputs[0], comb.inputs["Red"])
    else:
        comb.inputs["Red"].default_value = 1.0
    nt.links.new(_val_or_src(nt, bsdf.inputs["Roughness"]), comb.inputs["Green"])
    nt.links.new(_val_or_src(nt, bsdf.inputs["Metallic"]), comb.inputs["Blue"])
    return comb.outputs["Color"]


def _mask_material(ao_dist, edge_r, cav_dist):
    m = bpy.data.materials.new("__mask")
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != "ShaderNodeOutputMaterial":
            nt.nodes.remove(n)
    out = _find(nt, "ShaderNodeOutputMaterial")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 16
    ao.only_local = False
    ao.inputs["Distance"].default_value = ao_dist
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = edge_r
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(geo.outputs["Normal"], dot.inputs[1])
    e1 = nt.nodes.new("ShaderNodeMath")
    e1.operation = "SUBTRACT"
    e1.inputs[0].default_value = 1.0
    nt.links.new(dot.outputs["Value"], e1.inputs[1])
    e2 = nt.nodes.new("ShaderNodeMath")
    e2.operation = "MULTIPLY"
    e2.use_clamp = True
    nt.links.new(e1.outputs[0], e2.inputs[0])
    e2.inputs[1].default_value = 7.0
    # concave edges are occluded at short range -> suppress them (wear happens on convex edges)
    aos = nt.nodes.new("ShaderNodeAmbientOcclusion")
    aos.samples = 8
    aos.only_local = True
    aos.inputs["Distance"].default_value = edge_r * 2.5
    sm = nt.nodes.new("ShaderNodeMapRange")
    sm.interpolation_type = "SMOOTHSTEP"
    nt.links.new(aos.outputs["AO"], sm.inputs["Value"])
    sm.inputs["From Min"].default_value = 0.62
    sm.inputs["From Max"].default_value = 0.92
    e3 = nt.nodes.new("ShaderNodeMath")
    e3.operation = "MULTIPLY"
    nt.links.new(e2.outputs[0], e3.inputs[0])
    nt.links.new(sm.outputs["Result"], e3.inputs[1])
    # cavity
    aoc = nt.nodes.new("ShaderNodeAmbientOcclusion")
    aoc.samples = 10
    aoc.only_local = True
    aoc.inputs["Distance"].default_value = cav_dist
    cv = nt.nodes.new("ShaderNodeMapRange")
    cv.interpolation_type = "SMOOTHSTEP"
    nt.links.new(aoc.outputs["AO"], cv.inputs["Value"])
    cv.inputs["From Min"].default_value = 0.95
    cv.inputs["From Max"].default_value = 0.35
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(ao.outputs["AO"], comb.inputs["Red"])
    nt.links.new(e3.outputs[0], comb.inputs["Green"])
    nt.links.new(cv.outputs["Result"], comb.inputs["Blue"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(comb.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def _save(img, path, fmt, quality=90):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.filepath_raw = path
    img.file_format = fmt
    if fmt == "JPEG":
        img.save(filepath=path, quality=quality)
    else:
        img.save(filepath=path)


def _surface_area(ob, only_full=False):
    me = ob.data
    w = [1.0] * len(me.polygons)
    if only_full and "uvw" in me.attributes:
        me.attributes["uvw"].data.foreach_get("value", w)
    return sum(p.area for p in me.polygons if w[p.index] >= 0.99)


def _uv_area(ob, layer="UVMap", only_full=False):
    me = ob.data
    uv = me.uv_layers[layer].data
    w = [1.0] * len(me.polygons)
    if only_full and "uvw" in me.attributes:
        me.attributes["uvw"].data.foreach_get("value", w)
    tot = 0.0
    for p in me.polygons:
        if w[p.index] < 0.99:
            continue
        pts = [uv[li].uv for li in p.loop_indices]
        a = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            a += x1 * y2 - x2 * y1
        tot += abs(a) * 0.5
    return tot


def _cull_hidden_bottom(ob, eps=0.0015):
    """Delete downward faces lying on the ground plane (never visible, waste texels)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    dead = [f for f in bm.faces if f.normal.z < -0.97 and all(v.co.z < eps for v in f.verts)]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()


def _weighted_normals(ob):
    m = ob.modifiers.new("WN", "WEIGHTED_NORMAL")
    m.mode = "FACE_AREA"
    m.weight = 50
    m.keep_sharp = True
    G.apply_mods(ob)


def _unwrap(ob, margin_px=6, size_guess=1024):
    """Atlas UVs: smart-project every face without parametric UVs (tubes come pre-unwrapped),
    equalise texel density across islands, apply importance weights, pack."""
    me = ob.data
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    lay = me.uv_layers["UVMap"]
    me.uv_layers.active = lay
    lay.active_render = True
    pre = [0.0] * len(me.polygons)
    if "preuv" in me.attributes:
        me.attributes["preuv"].data.foreach_get("value", pre)
    sel = [p < 0.5 for p in pre]
    me.polygons.foreach_set("select", sel)
    C.set_active(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    if any(sel):
        bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=margin_px / size_guess,
                                 area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    _scale_islands(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin_px / size_guess, shape_method="CONCAVE")
    except Exception:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin_px / size_guess)
    bpy.ops.object.mode_set(mode="OBJECT")


def _scale_islands(ob):
    """Scale UV islands by the mean per-face "uvw" importance (see props_geo.uv_weight)."""
    me = ob.data
    if "uvw" not in me.attributes:
        return
    w = [0.0] * len(me.polygons)
    me.attributes["uvw"].data.foreach_get("value", w)
    if all(abs(x - 1.0) < 1e-4 for x in w):
        return
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv["UVMap"]
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        lf = e.link_loops
        if len(lf) != 2:
            continue
        a, b = lf[0], lf[1]
        # loops on the two faces: a goes v1->v2, b goes v2->v1
        a2, b2 = a.link_loop_next, b.link_loop_next
        if (a[uvl].uv - b2[uvl].uv).length < 1e-5 and (a2[uvl].uv - b[uvl].uv).length < 1e-5:
            ra, rb = find(a.face.index), find(b.face.index)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    for faces in groups.values():
        k = sum(w[f.index] for f in faces) / len(faces)
        if abs(k - 1.0) < 1e-4:
            continue
        loops = [l for f in faces for l in f.loops]
        c = sum((l[uvl].uv for l in loops), Vector((0.0, 0.0))) / len(loops)
        for l in loops:
            l[uvl].uv = c + (l[uvl].uv - c) * k
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------------------
# GLB post-processing (pure python)
# ---------------------------------------------------------------------------
def _glb_read(path):
    d = open(path, "rb").read()
    magic, ver, length = struct.unpack_from("<III", d, 0)
    assert magic == 0x46546C67
    off = 12
    chunks = []
    while off < length:
        cl, ct = struct.unpack_from("<II", d, off)
        chunks.append((ct, d[off + 8:off + 8 + cl]))
        off += 8 + cl
    return json.loads(chunks[0][1].decode()), (chunks[1][1] if len(chunks) > 1 else b"")


def _glb_write(path, js, binc):
    jb = json.dumps(js, separators=(",", ":"), ensure_ascii=False).encode()
    while len(jb) % 4:
        jb += b" "
    binc = bytes(binc)
    while len(binc) % 4:
        binc += b"\0"
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(jb) + (8 + len(binc) if binc else 0))
    out += struct.pack("<II", len(jb), 0x4E4F534A) + jb
    if binc:
        out += struct.pack("<II", len(binc), 0x004E4942) + binc
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, path)


def externalize(path, image_files: dict, tex_rel=TEX_REL):
    """Replace embedded images by relative URIs to the shared texture files; drop TANGENTs."""
    js, binc = _glb_read(path)
    drop = set()
    for im in js.get("images", []):
        stem = os.path.splitext(im.get("name", ""))[0]
        if "bufferView" in im and stem in image_files:
            drop.add(im["bufferView"])
            del im["bufferView"]
            fn = image_files[stem]
            im["mimeType"] = "image/png" if fn.endswith(".png") else "image/jpeg"
            im["uri"] = tex_rel + "/" + fn
    # strip tangents (Godot regenerates MikkTSpace tangents on import: meshes/ensure_tangents)
    acc = js.get("accessors", [])
    for me in js.get("meshes", []):
        for prim in me["primitives"]:
            t = prim["attributes"].pop("TANGENT", None)
    used = set()
    for me in js.get("meshes", []):
        for prim in me["primitives"]:
            used.update(prim["attributes"].values())
            if "indices" in prim:
                used.add(prim["indices"])
            for tg in prim.get("targets", []):
                used.update(tg.values())
    remap_a = {}
    new_acc = []
    for i, a in enumerate(acc):
        if i in used:
            remap_a[i] = len(new_acc)
            new_acc.append(a)
    js["accessors"] = new_acc
    for me in js.get("meshes", []):
        for prim in me["primitives"]:
            prim["attributes"] = {k: remap_a[v] for k, v in prim["attributes"].items()}
            if "indices" in prim:
                prim["indices"] = remap_a[prim["indices"]]
    live = {a["bufferView"] for a in new_acc if "bufferView" in a}
    live |= {im["bufferView"] for im in js.get("images", []) if "bufferView" in im}
    bvs = js.get("bufferViews", [])
    remap = {}
    newbin = bytearray()
    newbvs = []
    for i, bv in enumerate(bvs):
        if i not in live:
            continue
        o = bv.get("byteOffset", 0)
        data = binc[o:o + bv["byteLength"]]
        while len(newbin) % 4:
            newbin.append(0)
        bv = dict(bv)
        bv["byteOffset"] = len(newbin)
        bv["buffer"] = 0
        newbin += data
        remap[i] = len(newbvs)
        newbvs.append(bv)
    js["bufferViews"] = newbvs
    for a in js["accessors"]:
        if "bufferView" in a:
            a["bufferView"] = remap[a["bufferView"]]
    for im in js.get("images", []):
        if "bufferView" in im:
            im["bufferView"] = remap[im["bufferView"]]
    js["buffers"] = [{"byteLength": len(newbin)}] if newbin else []
    for m in js.get("materials", []):
        n = m.get("name", "")
        m["doubleSided"] = n.endswith("__2s") or n.endswith("__lit")
        if n.startswith("glass_"):
            m["alphaMode"] = "BLEND"
            m["doubleSided"] = False
    _glb_write(path, js, newbin)


def glb_tris(path):
    js, _ = _glb_read(path)
    t = 0
    for me in js.get("meshes", []):
        for p in me["primitives"]:
            if "indices" in p:
                t += js["accessors"][p["indices"]]["count"] // 3
    return t


def write_import(path, importer, type_, params):
    imp = path + ".import"

    def fmt(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return '"' + v + '"'
        return str(v)
    if os.path.exists(imp):
        txt = open(imp).read()
        m = re.search(r"^\[params\]\s*$", txt, re.M)
        if m:
            head, body = txt[:m.end()], txt[m.end():]
            lines = body.strip("\n").split("\n") if body.strip() else []
            keys = {ln.split("=", 1)[0]: i for i, ln in enumerate(lines) if "=" in ln}
            for k, v in params.items():
                ln = f"{k}={fmt(v)}"
                if k in keys:
                    lines[keys[k]] = ln
                else:
                    lines.append(ln)
            open(imp, "w").write(head + "\n\n" + "\n".join(lines) + "\n")
            return
    with open(imp, "w") as f:
        f.write(f'[remap]\n\nimporter="{importer}"\ntype="{type_}"\n\n[params]\n\n')
        for k, v in params.items():
            f.write(f"{k}={fmt(v)}\n")


GLB_PARAMS = {
    "import_script/path": POST_IMPORT,
    "meshes/generate_lods": True,
    "meshes/create_shadow_meshes": True,
    "meshes/light_baking": 1,
    "meshes/ensure_tangents": True,
    "gltf/embedded_image_handling": 1,
}


def tex_params(fname):
    p = {"compress/mode": 2, "mipmaps/generate": True, "detect_3d/compress_to": 0}
    if fname.endswith("_normal.png"):
        p["compress/normal_map"] = 1
    else:
        p["compress/normal_map"] = 2
    return p


# ---------------------------------------------------------------------------
# catalog
# ---------------------------------------------------------------------------
def catalog_load():
    if os.path.exists(CATALOG):
        try:
            return json.load(open(CATALOG))
        except Exception:
            return []
    return []


def catalog_save(entries):
    def key(e):
        c = e.get("category", "")
        return (CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99, e["id"])
    entries = sorted(entries, key=key)
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(CATALOG + ".tmp", "w") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)
    os.replace(CATALOG + ".tmp", CATALOG)


def catalog_put(entry):
    es = [e for e in catalog_load() if e.get("id") != entry["id"]]
    es.append(entry)
    catalog_save(es)


def _gd(v):
    """Blender (x, y, z) -> Godot (x, z, -y), rounded."""
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


# ---------------------------------------------------------------------------
# build one prop
# ---------------------------------------------------------------------------
def build(pid: str, preview=False, preview_kw=None, tex_override=None, samples=None) -> dict:
    spec = REG[pid]
    t0 = time.time()
    C.reset_scene()
    G.reset_counters()
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(pid))
    random.seed(seed)
    PN.ensure_mask_image()
    PN.ensure_label_image()
    res = spec["fn"](**spec["args"]) or {}
    parts = [p for p in res.get("parts", []) if p is not None]
    glass = res.get("glass", [])
    cols = res.get("colliders", [])
    marks = res.get("markers", [])
    meta = res.get("meta", {})
    if res.get("label"):
        PN.set_label_image(res["label"])

    # shading: give flat-shaded parts smooth-by-angle normals
    for p in parts:
        if not any(f.use_smooth for f in p.data.polygons):
            G.mark_sharp(p, 35)
    body = G.join(parts, pid)
    if spec["grounded"]:
        _cull_hidden_bottom(body)
    _weighted_normals(body)

    # bounds (before UV) for catalog
    mn, mx = G.bounds([body] + glass)
    size = mx - mn
    area = max(_surface_area(body, True), 1e-6)

    # texture size from texel density (measured on full-importance faces)
    _unwrap(body, 6, 1024)
    uva = max(_uv_area(body, only_full=True), 1e-6)
    need = spec["density"] * math.sqrt(area / uva) * 0.85   # 15 % tolerance before doubling
    tex = spec["min_tex"]
    while tex < need and tex < spec["max_tex"]:
        tex *= 2
    if tex_override:
        tex = tex_override
    if os.environ.get("PROPS_FAST"):
        tex, samples = int(os.environ["PROPS_FAST"]), 1
    if tex != 1024:
        _unwrap(body, 6 if tex >= 1024 else 4, tex)
        uva = max(_uv_area(body, only_full=True), 1e-6)
    density = tex * math.sqrt(uva / max(area, 1e-9))
    print(f"UVSTAT {pid}: uv_used={_uv_area(body):.3f} full_uv={uva:.3f} full_area={area:.3f}m2 "
          f"all_area={_surface_area(body):.3f}m2 islands_tex={tex}")
    margin = max(4, tex // 128)
    if os.environ.get("PROPS_UVONLY"):
        print(f"UVSTAT {pid}: tex={tex} density={density:.0f} uv_used={_uv_area(body):.3f} full_area={area:.3f}m2 "
              f"all_area={_surface_area(body):.3f}m2")
        return {}

    # 1) geometry masks
    diag = size.length
    ao_dist = spec["ao_dist"] or max(0.03, min(0.5, diag * 0.18))
    edge_r = spec["edge_r"] or max(0.0015, min(0.012, diag * 0.012))
    ground = None
    if spec["grounded"]:
        bpy.ops.mesh.primitive_plane_add(size=max(4.0, diag * 4), location=(0, 0, 0))
        ground = bpy.context.active_object
    mm = _mask_material(ao_dist, edge_r, edge_r * 4)
    orig = [s.material for s in body.material_slots]
    for s in body.material_slots:
        s.material = mm
    mask_img = _new_img("__mask_bake", tex, non_color=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    t1 = time.time()
    _bake_into(body, mask_img, "EMIT", samples or 2, margin)
    mpath = os.path.join(CACHE_DIR, f"{pid}_mask.png")
    _save(mask_img, mpath, "PNG")
    for s, m in zip(body.material_slots, orig):
        s.material = m
    if ground is not None:
        bpy.data.objects.remove(ground, do_unlink=True)
    mi = PN.ensure_mask_image()
    mi.source = "FILE"
    mi.filepath = mpath
    mi.colorspace_settings.name = "Non-Color"
    mi.reload()
    t_mask = time.time() - t1

    # 2) albedo, 3) ORM, 4) normal
    mats = [m for m in orig if m is not None]
    t1 = time.time()
    alb = _new_img("__alb", tex)
    routes = [_route_emission(m, _albedo_builder) for m in mats]
    _bake_into(body, alb, "EMIT", samples or 2, margin)
    _restore(routes)
    t_alb = time.time() - t1
    t1 = time.time()
    orm = _new_img("__orm", tex, non_color=True)
    routes = [_route_emission(m, _orm_builder) for m in mats]
    _bake_into(body, orm, "EMIT", samples or 2, margin)
    _restore(routes)
    t_orm = time.time() - t1
    t1 = time.time()
    nrm = _new_img("__nrm", tex, non_color=True)
    _bake_into(body, nrm, "NORMAL", samples or 2, margin)
    t_nrm = time.time() - t1
    bpy.context.scene.render.image_settings.compression = 100
    files = {"albedo": f"{pid}_albedo.jpg", "orm": f"{pid}_orm.jpg", "normal": f"{pid}_normal.png"}
    _save(alb, os.path.join(TEX_DIR, files["albedo"]), "JPEG", 90)
    _save(orm, os.path.join(TEX_DIR, files["orm"]), "JPEG", 92)
    _save(nrm, os.path.join(TEX_DIR, files["normal"]), "PNG")
    for k in ("albedo", "orm", "normal"):
        write_import(os.path.join(TEX_DIR, files[k]), "texture", "CompressedTexture2D", tex_params(files[k]))

    # final materials by role
    roles = []
    for m in orig:
        r = (m.get("role", "base") if m is not None else "base")
        roles.append(r)
    role_names = {"base": pid, "2s": pid + "__2s", "lit": pid + "__lit"}
    finals = {}
    for r in sorted(set(roles), key=lambda x: ["base", "2s", "lit"].index(x) if x in ("base", "2s", "lit") else 9):
        nm = role_names.get(r, pid)
        fm = C.image_material(nm, albedo=os.path.join(TEX_DIR, files["albedo"]),
                              orm=os.path.join(TEX_DIR, files["orm"]),
                              normal=os.path.join(TEX_DIR, files["normal"]))
        for n in fm.node_tree.nodes:
            if n.bl_idname == "ShaderNodeTexImage":
                n.image.name = os.path.splitext(os.path.basename(n.image.filepath))[0]
        finals[r] = fm
    order = list(finals.keys())
    me = body.data
    idx_map = [order.index(r) for r in roles]
    mi_arr = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", mi_arr)
    mi_arr = [idx_map[i] if i < len(idx_map) else 0 for i in mi_arr]
    me.materials.clear()
    for r in order:
        me.materials.append(finals[r])
    me.polygons.foreach_set("material_index", mi_arr)
    me.update()
    if "LabelUV" in me.uv_layers:
        me.uv_layers.remove(me.uv_layers["LabelUV"])
    me.uv_layers["UVMap"].active = True

    for g in glass:
        if "LabelUV" in g.data.uv_layers:
            g.data.uv_layers.remove(g.data.uv_layers["LabelUV"])

    # export
    out = os.path.join(MODEL_DIR, spec["file"])
    for o in [body] + glass + cols + marks:
        o.parent = None
    objs = [body] + glass + cols + marks
    C.export_glb(out, objects=objs)
    externalize(out, {os.path.splitext(v)[0]: v for v in files.values()})
    write_import(out, "scene", "PackedScene", GLB_PARAMS)

    # catalog entry
    tris = glb_tris(out)
    w, d, h = size.x, size.y, size.z
    entry = {
        "id": pid,
        "file": f"res://assets/models/props/{spec['file']}",
        "kind": spec["kind"],
        "category": spec["category"],
        "footprint": [round(w, 3), round(d, 3)],
        "width": round(w, 3), "depth": round(d, 3), "height": round(mx.z - min(mn.z, 0.0) if spec["grounded"] else h, 3),
        "bounds_min": _gd((mn.x, mx.y, mn.z)), "bounds_max": _gd((mx.x, mn.y, mx.z)),
        "dynamic": bool(spec["dynamic"]),
        "mass": round(float(spec["mass"]), 3),
        "surface": spec["surface"],
        "material_kind": spec["material_kind"],
        "name_key": spec["name_key"] or ("PROP_" + pid.upper()),
        "tris": tris,
        "materials": len(order) + len({m.name for g in glass for m in g.data.materials}),
        "texture_size": tex,
        "texel_density": round(density),
        "textures": [f"res://assets/textures/props/{v}" for v in files.values()],
        "colliders": len(cols),
        "climb_points": [], "nap_spots": [], "entrances": [],
        "tags": spec["tags"],
    }
    if spec["variant_of"]:
        entry["variant_of"] = spec["variant_of"]
    if spec["item_id"]:
        entry["item_id"] = spec["item_id"]
    for mk in marks:
        p = mk.location
        if mk.name.startswith("NAP"):
            entry["nap_spots"].append(_gd(p))
        elif mk.name.startswith("CLIMB"):
            entry["climb_points"].append(_gd(p))
        elif mk.name.startswith("SIT"):
            entry.setdefault("sit_spots", []).append(_gd(p))
        elif mk.name.startswith("LIGHT"):
            info = json.loads(mk.get("light_json", "{}"))
            if "dir" in info:
                info["dir"] = _gd(info["dir"])
            entry.setdefault("lights", []).append({"name": mk.name, "pos": _gd(p), **info})
        elif mk.name.startswith("ATTACH") or mk.name.startswith("HANG"):
            entry.setdefault("attach_points", []).append({"name": mk.name, "pos": _gd(p)})
    entry.update(spec["extra"])
    entry.update(meta)
    if "lights" in entry:
        entry["light_pos"] = entry["lights"][0]["pos"]
    if "lit" in finals:
        entry["emissive"] = True
    catalog_put(entry)
    dt = time.time() - t0
    print(f"PROP {pid}: tris={tris} tex={tex} density={density:.0f}px/m mask={t_mask:.1f}s alb={t_alb:.1f}s orm={t_orm:.1f}s nrm={t_nrm:.1f}s total={dt:.1f}s "
          f"size=({w:.3f},{d:.3f},{h:.3f})")
    if preview:
        _preview(pid, objs, mn, mx, **(preview_kw or {}))
    return entry


def _preview(pid, objs, mn, mx, yaw=35.0, pitch=18.0, res=(640, 480), samples=24):
    c = (mn + mx) * 0.5
    diag = (mx - mn).length
    for o in bpy.context.scene.objects:
        if o.name.startswith("col_"):
            o.hide_render = True
    C.preview_render(C.qa_path(f"street-props/{pid}.png"), target=tuple(c), distance=max(0.25, diag * 1.9),
                     yaw_deg=yaw, pitch_deg=pitch, res=res, samples=samples, lens=50)


def run(ids, preview=False, stop_on_error=False):
    ok, bad = [], []
    for pid in ids:
        try:
            build(pid, preview=preview)
            ok.append(pid)
        except Exception:
            traceback.print_exc()
            print(f"PROP FAILED {pid}")
            bad.append(pid)
            if stop_on_error:
                break
    print(f"BUILD SUMMARY ok={len(ok)} failed={len(bad)} {bad}")
    return ok, bad
