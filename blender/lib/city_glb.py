"""GLB post-processing + Godot .import presets for the city-houses kit (pure python, no bpy).

* externalize_images(): rewrites a .glb so its images reference the shared texture files in
  assets/textures/architecture/ by relative URI instead of embedding copies. Godot's glTF
  importer then loads them as project resources (res://assets/textures/architecture/...), so all
  ~50 modules share one copy of each texture in memory and on disk.
* fix_materials(): enforces alphaMode / doubleSided per material-name prefix (dec_, fol_).
* write_import(): writes/updates the [params] of a Godot .import file (keeps uid/remap sections).
"""
from __future__ import annotations

import json
import os
import re
import struct


def _read(path):
    d = open(path, "rb").read()
    magic, ver, length = struct.unpack_from("<III", d, 0)
    assert magic == 0x46546C67, "not a glb"
    off = 12
    chunks = []
    while off < length:
        cl, ct = struct.unpack_from("<II", d, off)
        chunks.append((ct, d[off + 8:off + 8 + cl]))
        off += 8 + cl
    js = json.loads(chunks[0][1].decode())
    binc = chunks[1][1] if len(chunks) > 1 else b""
    return js, binc


def _write(path, js, binc):
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


def _strip_tangents(js) -> set:
    """Remove TANGENT attributes (Godot regenerates them with meshes/ensure_tangents) and compact
    the accessor list. Returns the set of bufferViews no longer referenced."""
    acc = js.get("accessors", [])
    used = set()
    for me in js.get("meshes", []):
        for prim in me["primitives"]:
            prim["attributes"].pop("TANGENT", None)
            for t in prim.get("targets", []):
                t.pop("TANGENT", None)
            used.update(prim["attributes"].values())
            if "indices" in prim:
                used.add(prim["indices"])
    for sk in js.get("skins", []):
        if "inverseBindMatrices" in sk:
            used.add(sk["inverseBindMatrices"])
    for an in js.get("animations", []):
        for smp in an.get("samplers", []):
            used.update([smp["input"], smp["output"]])
    remap = {}
    new = []
    for i, a in enumerate(acc):
        if i in used:
            remap[i] = len(new)
            new.append(a)
    js["accessors"] = new
    for me in js.get("meshes", []):
        for prim in me["primitives"]:
            prim["attributes"] = {k: remap[v] for k, v in prim["attributes"].items()}
            if "indices" in prim:
                prim["indices"] = remap[prim["indices"]]
    for sk in js.get("skins", []):
        if "inverseBindMatrices" in sk:
            sk["inverseBindMatrices"] = remap[sk["inverseBindMatrices"]]
    for an in js.get("animations", []):
        for smp in an.get("samplers", []):
            smp["input"], smp["output"] = remap[smp["input"]], remap[smp["output"]]
    live = {a["bufferView"] for a in new if "bufferView" in a}
    live |= {im["bufferView"] for im in js.get("images", []) if "bufferView" in im}
    return {i for i in range(len(js.get("bufferViews", []))) if i not in live}


def postprocess(path: str, image_files: dict[str, str], tex_rel: str, strip_tangents: bool = True) -> dict:
    """image_files: image stem -> file name; tex_rel: texture dir relative to the glb dir."""
    js, binc = _read(path)
    drop = set()
    missing = []
    for im in js.get("images", []):
        nm = im.get("name", "")
        stem = os.path.splitext(nm)[0]
        if "bufferView" in im and stem in image_files:
            drop.add(im["bufferView"])
            del im["bufferView"]
            fn = image_files[stem]
            im["mimeType"] = "image/png" if fn.endswith(".png") else "image/jpeg"
            im["uri"] = tex_rel.rstrip("/") + "/" + fn
        elif "bufferView" in im:
            missing.append(nm)
    if strip_tangents:
        drop |= _strip_tangents(js)
    bvs = js.get("bufferViews", [])
    remap = {}
    newbin = bytearray()
    newbvs = []
    for i, bv in enumerate(bvs):
        if i in drop:
            continue
        o = bv.get("byteOffset", 0)
        data = binc[o:o + bv["byteLength"]]
        while len(newbin) % 4:
            newbin.append(0)
        bv = dict(bv)
        bv["byteOffset"] = len(newbin)
        newbin += data
        remap[i] = len(newbvs)
        newbvs.append(bv)
    js["bufferViews"] = newbvs
    for a in js.get("accessors", []):
        if "bufferView" in a:
            a["bufferView"] = remap[a["bufferView"]]
    for im in js.get("images", []):
        if "bufferView" in im:
            im["bufferView"] = remap[im["bufferView"]]
    js["buffers"] = [{"byteLength": len(newbin)}] if newbin else []
    # material fixes
    for m in js.get("materials", []):
        n = m.get("name", "")
        if n.startswith("dec_"):
            m["alphaMode"] = "BLEND"
            m["doubleSided"] = False
        elif n.startswith("fol_"):
            m["alphaMode"] = "MASK"
            m["alphaCutoff"] = 0.5
            m["doubleSided"] = True
        else:
            m.pop("alphaMode", None)
            m.pop("alphaCutoff", None)
            m["doubleSided"] = False
    _write(path, js, newbin)
    return {"external": len(drop), "embedded_left": missing}


def stats(path: str) -> dict:
    js, binc = _read(path)
    tris = 0
    for me in js.get("meshes", []):
        for p in me["primitives"]:
            if "indices" in p:
                tris += js["accessors"][p["indices"]]["count"] // 3
    return {"tris": tris, "nodes": len(js.get("nodes", [])), "materials": len(js.get("materials", [])),
            "bytes": os.path.getsize(path)}


def write_import(path: str, importer: str, type_: str, params: dict) -> None:
    """Create or update `<asset>.import`. Existing sections/uid are kept; params are merged."""
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
            changed = False
            for k, v in params.items():
                ln = f"{k}={fmt(v)}"
                if k in keys:
                    if lines[keys[k]] != ln:
                        lines[keys[k]] = ln
                        changed = True
                else:
                    lines.append(ln)
                    changed = True
            if changed:
                open(imp, "w").write(head + "\n\n" + "\n".join(lines) + "\n")
            return
    with open(imp, "w") as f:
        f.write(f'[remap]\n\nimporter="{importer}"\ntype="{type_}"\n\n[params]\n\n')
        for k, v in params.items():
            f.write(f"{k}={fmt(v)}\n")


GLB_IMPORT_PARAMS = {
    "import_script/path": "res://assets/models/city/_import/city_post_import.gd",
    "meshes/generate_lods": True,
    "meshes/create_shadow_meshes": True,
    "meshes/light_baking": 1,
    "meshes/ensure_tangents": True,
}


def texture_import_params(fname: str) -> dict:
    p = {"compress/mode": 2, "mipmaps/generate": True, "detect_3d/compress_to": 0}
    if fname.endswith("_normal.png"):
        p["compress/normal_map"] = 1
    if fname.endswith("_orm.jpg"):
        p["compress/normal_map"] = 2
    return p
