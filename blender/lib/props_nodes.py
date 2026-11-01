"""Procedural layered materials for the street-props kit (Blender 5.2, Cycles bake sources).

Every prop is modelled with these node materials, then *baked* into one texture set per prop
(albedo / ORM / normal, see props_bake.py). The materials therefore may be as rich as we like
(layered paint, rust, scratches, dirt, dust, labels) — runtime cost is one baked material.

Conventions
* Colours are given in sRGB (hex string "#rrggbb" or 0..1 tuple) and converted to linear.
* Object-space coordinates (metres; transforms are applied before baking) drive all noise, so
  patterns are seamless across UV islands.
* Baked geometry masks are available in every material through the shared image
  "__props_mask" sampled with the atlas UV ("UVMap"):  R = ambient occlusion (prop scale),
  G = convex edge (bevel-normal trick, concave edges removed), B = cavity (short-range AO).
  props_bake fills it before the colour bakes; before that it is neutral (AO 1, no edges).
* Labels/decals: image "__props_label" sampled with the "LabelUV" layer (CLIP outside 0..1);
  faces that carry no label have LabelUV far outside the image.
* Every recipe returns the Material; custom property "role" tells the baker which final
  material the faces go to: "base" (opaque), "2s" (double-sided: leaves, cloth, paper),
  "lit" (night-emissive: lantern film/silk, lamp diffusers, light boxes).
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

MASK_IMAGE = "__props_mask"
LABEL_IMAGE = "__props_label"


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
def _s2l(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb(c) -> tuple:
    """'#rrggbb' or (r,g,b[,a]) in sRGB 0..1 -> linear RGBA tuple."""
    if isinstance(c, str):
        h = c.lstrip("#")
        c = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    r, g, b = c[:3]
    return (_s2l(r), _s2l(g), _s2l(b), 1.0)


def jitter(c, rng: random.Random, amount: float = 0.04) -> tuple:
    """Small random value/hue jitter of an sRGB colour (for variants)."""
    if isinstance(c, str):
        h = c.lstrip("#")
        c = tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    k = 1.0 + rng.uniform(-amount, amount)
    return tuple(min(1.0, max(0.0, x * k + rng.uniform(-amount, amount) * 0.3)) for x in c[:3])


def ensure_mask_image() -> bpy.types.Image:
    img = bpy.data.images.get(MASK_IMAGE)
    if img is None:
        img = bpy.data.images.new(MASK_IMAGE, 4, 4, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set([1.0, 0.0, 0.0, 1.0] * 16)
    return img


def ensure_label_image() -> bpy.types.Image:
    img = bpy.data.images.get(LABEL_IMAGE)
    if img is None:
        img = bpy.data.images.new(LABEL_IMAGE, 4, 4, alpha=True)
        img.pixels.foreach_set([0.0, 0.0, 0.0, 0.0] * 16)
    return img


def set_label_image(path: str) -> None:
    img = ensure_label_image()
    img.source = "FILE"
    img.filepath = path
    img.reload()
    img.alpha_mode = "STRAIGHT"


# ---------------------------------------------------------------------------
# Node builder
# ---------------------------------------------------------------------------
class NB:
    """Tiny DSL over a material node tree. Arguments may be sockets or constants."""

    def __init__(self, name: str, role: str = "base"):
        m = bpy.data.materials.new(name)
        m["role"] = role
        self.mat = m
        self.nt = m.node_tree
        self.nodes = self.nt.nodes
        self.bsdf = next(n for n in self.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        self.out = next(n for n in self.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        self._x = -2400
        tc = self.node("ShaderNodeTexCoord")
        self.co = tc.outputs["Object"]
        geo = self.node("ShaderNodeNewGeometry")
        self.N = geo.outputs["Normal"]
        self.x, self.y, self.z = self.sep(self.co)
        self.nx, self.ny, self.nz = self.sep(self.N)
        self.up = self.clamp(self.nz)
        self.down = self.clamp(self.mul(self.nz, -1.0))
        # baked geometry masks
        uv = self.node("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        mk = self.node("ShaderNodeTexImage")
        mk.image = ensure_mask_image()
        mk.label = "PROPS_MASK"
        mk.interpolation = "Linear"
        self.link(uv.outputs["UV"], mk.inputs["Vector"])
        r, g, b = self.sepc(mk.outputs["Color"])
        self.ao, self.edge, self.cav = r, g, b
        self._label = None

    # -- plumbing ----------------------------------------------------------
    def node(self, t: str, **props):
        n = self.nodes.new(t)
        n.location = (self._x, 0)
        self._x += 10
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def _in(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        elif v is None:
            return
        else:
            if isinstance(v, str):
                v = srgb(v)
            try:
                n = len(sock.default_value)
            except TypeError:
                n = 0
            if n and not isinstance(v, (tuple, list)):
                v = (v,) * n
            elif n == 4 and len(v) == 3:
                v = (*v, 1.0)
            elif n == 3 and len(v) == 4:
                v = v[:3]
            sock.default_value = v

    # -- math --------------------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._in(n.inputs[0], a)
        if b is not None:
            self._in(n.inputs[1], b)
        if c is not None:
            self._in(n.inputs[2], c)
        return n.outputs[0]

    def add(self, a, b, clamp=False):
        return self.math("ADD", a, b, clamp=clamp)

    def sub(self, a, b, clamp=False):
        return self.math("SUBTRACT", a, b, clamp=clamp)

    def mul(self, a, b, clamp=False):
        return self.math("MULTIPLY", a, b, clamp=clamp)

    def madd(self, a, b, c, clamp=False):
        return self.math("MULTIPLY_ADD", a, b, c, clamp=clamp)

    def pow(self, a, b):
        return self.math("POWER", a, b)

    def maxf(self, a, b):
        return self.math("MAXIMUM", a, b)

    def minf(self, a, b):
        return self.math("MINIMUM", a, b)

    def clamp(self, a):
        return self.math("ADD", a, 0.0, clamp=True)

    def inv(self, a):
        return self.math("SUBTRACT", 1.0, a, clamp=True)

    def smooth(self, x, e0, e1, lo=0.0, hi=1.0):
        n = self.node("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
        self._in(n.inputs["Value"], x)
        self._in(n.inputs["From Min"], e0)
        self._in(n.inputs["From Max"], e1)
        self._in(n.inputs["To Min"], lo)
        self._in(n.inputs["To Max"], hi)
        return n.outputs["Result"]

    def remap(self, x, e0, e1, lo=0.0, hi=1.0, clamp=True):
        n = self.node("ShaderNodeMapRange", interpolation_type="LINEAR", clamp=clamp)
        self._in(n.inputs["Value"], x)
        self._in(n.inputs["From Min"], e0)
        self._in(n.inputs["From Max"], e1)
        self._in(n.inputs["To Min"], lo)
        self._in(n.inputs["To Max"], hi)
        return n.outputs["Result"]

    # -- vectors -----------------------------------------------------------
    def sep(self, v):
        n = self.node("ShaderNodeSeparateXYZ")
        self._in(n.inputs[0], v)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def comb(self, x, y, z):
        n = self.node("ShaderNodeCombineXYZ")
        self._in(n.inputs[0], x)
        self._in(n.inputs[1], y)
        self._in(n.inputs[2], z)
        return n.outputs[0]

    def sepc(self, c):
        n = self.node("ShaderNodeSeparateColor")
        self._in(n.inputs[0], c)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def combc(self, r, g, b):
        n = self.node("ShaderNodeCombineColor")
        self._in(n.inputs[0], r)
        self._in(n.inputs[1], g)
        self._in(n.inputs[2], b)
        return n.outputs[0]

    def vmul(self, a, b):
        n = self.node("ShaderNodeVectorMath", operation="MULTIPLY")
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        return n.outputs["Vector"]

    def vadd(self, a, b):
        n = self.node("ShaderNodeVectorMath", operation="ADD")
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        return n.outputs["Vector"]

    def coords(self, scale=(1, 1, 1), offset=(0, 0, 0), swizzle: str = "xyz"):
        """Object coords, optionally swizzled (e.g. 'yzx' puts X on the third axis), scaled, offset."""
        comp = {"x": self.x, "y": self.y, "z": self.z}
        v = self.comb(comp[swizzle[0]], comp[swizzle[1]], comp[swizzle[2]]) if swizzle != "xyz" else self.co
        v = self.vmul(v, tuple(scale))
        if any(offset):
            v = self.vadd(v, tuple(offset))
        return v

    # -- textures ----------------------------------------------------------
    def noise(self, vec=None, scale=5.0, detail=4.0, rough=0.55, dist=0.0, lac=2.0, seed=None,
              col=False, ntype="FBM"):
        n = self.node("ShaderNodeTexNoise", noise_dimensions="3D", noise_type=ntype)
        rs = random.Random(seed) if seed is not None else random
        off = (rs.uniform(-50, 50), rs.uniform(-50, 50), rs.uniform(-50, 50))
        self._in(n.inputs["Vector"], self.vadd(vec if vec is not None else self.co, off))
        self._in(n.inputs["Scale"], scale)
        self._in(n.inputs["Detail"], detail)
        self._in(n.inputs["Roughness"], rough)
        self._in(n.inputs["Distortion"], dist)
        self._in(n.inputs["Lacunarity"], lac)
        return n.outputs["Color"] if col else n.outputs["Fac"]

    def voronoi(self, vec=None, scale=5.0, feature="F1", rnd=1.0, out="Distance", detail=0.0,
                metric="EUCLIDEAN"):
        n = self.node("ShaderNodeTexVoronoi", voronoi_dimensions="3D", feature=feature,
                      distance=metric)
        off = (random.uniform(-50, 50), random.uniform(-50, 50), random.uniform(-50, 50))
        self._in(n.inputs["Vector"], self.vadd(vec if vec is not None else self.co, off))
        self._in(n.inputs["Scale"], scale)
        self._in(n.inputs["Randomness"], rnd)
        if "Detail" in n.inputs:
            self._in(n.inputs["Detail"], detail)
        return n.outputs[out]

    def wave(self, vec=None, scale=5.0, dist=0.0, detail=2.0, dscale=1.0, kind="BANDS", axis="X",
             profile="SIN", phase=0.0, out="Fac"):
        n = self.node("ShaderNodeTexWave", wave_type=kind, wave_profile=profile)
        if kind == "BANDS":
            n.bands_direction = axis
        else:
            n.rings_direction = axis
        self._in(n.inputs["Vector"], vec if vec is not None else self.co)
        self._in(n.inputs["Scale"], scale)
        self._in(n.inputs["Distortion"], dist)
        self._in(n.inputs["Detail"], detail)
        self._in(n.inputs["Detail Scale"], dscale)
        self._in(n.inputs["Phase Offset"], phase)
        return n.outputs[out]

    def ramp(self, fac, stops):
        """stops: [(pos, colour)] -> colour socket."""
        n = self.node("ShaderNodeValToRGB")
        cr = n.color_ramp
        while len(cr.elements) > len(stops):
            cr.elements.remove(cr.elements[-1])
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for el, (p, c) in zip(cr.elements, stops):
            el.position = p
            cc = srgb(c) if isinstance(c, str) or len(c) == 3 else c
            el.color = cc
        self._in(n.inputs[0], fac)
        return n.outputs["Color"]

    # -- colour ------------------------------------------------------------
    @staticmethod
    def _id(coll, ident):
        return next(x for x in coll if x.identifier == ident)

    def mixc(self, fac, a, b, blend="MIX", clamp=True):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend, clamp_result=clamp)
        self._in(self._id(n.inputs, "Factor_Float"), fac)
        self._in(self._id(n.inputs, "A_Color"), a)
        self._in(self._id(n.inputs, "B_Color"), b)
        return self._id(n.outputs, "Result_Color")

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT", clamp_factor=True)
        self._in(self._id(n.inputs, "Factor_Float"), fac)
        self._in(self._id(n.inputs, "A_Float"), a)
        self._in(self._id(n.inputs, "B_Float"), b)
        return self._id(n.outputs, "Result_Float")

    def hsv(self, col, h=0.5, s=1.0, v=1.0, fac=1.0):
        n = self.node("ShaderNodeHueSaturation")
        self._in(n.inputs["Hue"], h)
        self._in(n.inputs["Saturation"], s)
        self._in(n.inputs["Value"], v)
        self._in(n.inputs["Fac"], fac)
        self._in(n.inputs["Color"], col)
        return n.outputs["Color"]

    def cmul(self, col, k):
        return self.mixc(1.0, col, k if isinstance(k, (tuple, bpy.types.NodeSocket)) else (k, k, k, 1), blend="MULTIPLY",
                         clamp=False)

    # -- state layering ----------------------------------------------------
    def st(self, col, rough, metal=0.0, h=0.0):
        return {"col": col, "rough": rough, "metal": metal, "h": h}

    def layer(self, base: dict, top: dict, fac) -> dict:
        out = {}
        out["col"] = self.mixc(fac, base["col"], top["col"])
        out["rough"] = self.mixf(fac, base["rough"], top["rough"])
        out["metal"] = self.mixf(fac, base["metal"], top["metal"])
        out["h"] = self.mixf(fac, base["h"], top["h"])
        return out

    # -- common masks ----------------------------------------------------------
    def scratches(self, scale=60.0, density=0.5, stretch=10.0, width=0.03):
        """Sparse fine scratch lines: iso-lines of noise stretched along random directions,
        gathered in clusters (handled/scuffed zones). Returns 0..1."""
        acc = None
        dirs = [(stretch, 1.0, 1.0), (1.0, stretch, 1.0), (1.0, 1.0, stretch)]
        for k, sc in enumerate(dirs):
            v = self.vmul(self.co, sc)
            n = self.noise(v, scale=scale / stretch * 1.5, detail=1.0, rough=0.5)
            line = self.smooth(self.math("ABSOLUTE", self.sub(n, 0.5)), width * 0.35, 0.0)
            acc = line if acc is None else self.maxf(acc, line)
        cl = self.smooth(self.noise(scale=scale * 0.05, detail=3), 0.72 - density * 0.25, 0.86 - density * 0.25)
        fine = self.smooth(self.noise(scale=scale * 0.6, detail=2), 0.35, 0.6)
        return self.mul(self.mul(acc, cl), fine)

    def edge_wear(self, amount=0.5, noise_scale=40.0, spread=1.0):
        """Chips/wear following baked convex edges, broken up by noise."""
        n = self.noise(scale=noise_scale, detail=6, rough=0.65)
        e = self.madd(self.edge, 1.6 * spread, self.mul(self.sub(n, 0.5), 1.2))
        t = 1.15 - amount
        return self.smooth(e, t, t + 0.12)

    def ground_mask(self, height=0.15):
        return self.smooth(self.z, height, 0.0)

    # -- weathering pass ---------------------------------------------------
    def weather(self, s: dict, dirt=0.5, dust=0.3, ground=0.0, ground_h=0.15, ao_in_albedo=0.35,
                dirt_col="#2a2219", dust_col="#8a8072", grime_col="#2e2820") -> dict:
        col = s["col"]
        # bake a little of the large-scale AO into albedo for depth (runtime adds SSAO on top)
        col = self.mixc(ao_in_albedo, col, self.cmul(col, self.combc(self.ao, self.ao, self.ao)))
        rough = s["rough"]
        if dirt > 0:
            nz = self.noise(scale=9, detail=5)
            cav = self.mul(self.pow(self.cav, 0.8), self.madd(nz, 0.8, 0.4))
            f = self.clamp(self.mul(cav, dirt * 1.4))
            col = self.mixc(f, col, dirt_col)
            rough = self.mixf(f, rough, 0.85)
        if dust > 0:
            nz = self.noise(scale=14, detail=4)
            f = self.mul(self.pow(self.up, 2.0), self.smooth(nz, 0.35, 0.7))
            f = self.clamp(self.mul(f, dust))
            col = self.mixc(f, col, dust_col)
            rough = self.mixf(f, rough, 0.92)
        if ground > 0:
            nz = self.noise(scale=6, detail=6, rough=0.7)
            g = self.mul(self.ground_mask(ground_h), self.smooth(nz, 0.3, 0.7))
            g = self.clamp(self.mul(g, ground))
            col = self.mixc(g, col, grime_col)
            rough = self.mixf(g, rough, 0.8)
        return {"col": col, "rough": rough, "metal": s["metal"], "h": s["h"]}

    # -- labels ------------------------------------------------------------
    def label(self, s: dict, wear=0.3, rough=None, metal=None, emboss=0.0) -> dict:
        """Overlay the prop's label sheet (LabelUV) with wear."""
        uv = self.node("ShaderNodeUVMap")
        uv.uv_map = "LabelUV"
        t = self.node("ShaderNodeTexImage", extension="CLIP", interpolation="Cubic")
        t.image = ensure_label_image()
        self.link(uv.outputs["UV"], t.inputs["Vector"])
        a = t.outputs["Alpha"]
        if wear > 0:
            w = self.add(self.edge_wear(wear, 90), self.mul(self.scratches(90, wear), 0.8))
            a = self.mul(a, self.inv(w))
            a = self.mul(a, self.remap(self.noise(scale=25, detail=6), 0.2, 0.55, 1.0 - wear * 0.6, 1.0))
        out = dict(s)
        out["col"] = self.mixc(a, s["col"], t.outputs["Color"])
        if rough is not None:
            out["rough"] = self.mixf(a, s["rough"], rough)
        if metal is not None:
            out["metal"] = self.mixf(a, s["metal"], metal)
        if emboss:
            out["h"] = self.madd(a, emboss, s["h"])
        return out

    # -- output ------------------------------------------------------------
    def finish(self, s: dict, bump=0.001, strength=1.0, emission=None) -> bpy.types.Material:
        self._in(self.bsdf.inputs["Base Color"], s["col"])
        self._in(self.bsdf.inputs["Roughness"], s["rough"])
        self._in(self.bsdf.inputs["Metallic"], s["metal"])
        if isinstance(s["h"], bpy.types.NodeSocket) and bump > 0:
            b = self.node("ShaderNodeBump")
            b.inputs["Strength"].default_value = strength
            b.inputs["Distance"].default_value = bump
            self.link(s["h"], b.inputs["Height"])
            self.link(b.outputs["Normal"], self.bsdf.inputs["Normal"])
        if emission is not None:
            self._in(self.bsdf.inputs["Emission Color"], emission)
            self.bsdf.inputs["Emission Strength"].default_value = 1.0
        return self.mat


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------
def _var(nb: NB, col, amount=0.06, scale=4.0, hue=0.008):
    """Low-frequency colour variation (value + tiny hue)."""
    n = nb.noise(scale=scale, detail=3)
    n2 = nb.noise(scale=scale * 6, detail=2)
    v = nb.madd(nb.sub(n, 0.5), amount * 2, 1.0)
    v = nb.madd(nb.sub(n2, 0.5), amount * 0.8, v)
    h = nb.madd(nb.sub(n, 0.5), hue * 2, 0.5)
    return nb.hsv(col, h=h, v=v)


def plastic(name, color, rough=0.42, fade=0.35, scratch=0.5, dirt=0.45, dust=0.3, ground=0.0,
            textured=0.3, label=False, label_wear=0.25, role="base", stress=0.4, gloss_var=0.08):
    """Injection-moulded PP/PE: orange-peel micro texture, sun-fade on up faces, scuffs, stress whitening."""
    nb = NB(name, role)
    c = _var(nb, color, 0.05)
    # sun fade (UV-bleached, chalky) on surfaces facing the sky
    fz = nb.mul(nb.madd(nb.up, 0.7, 0.3), nb.smooth(nb.noise(scale=2.5, detail=3), 0.25, 0.75))
    fz = nb.clamp(nb.mul(fz, fade))
    faded = nb.hsv(color, s=0.62, v=1.22)
    c = nb.mixc(fz, c, faded)
    r = nb.madd(nb.noise(scale=8, detail=3), gloss_var * 2, rough - gloss_var)
    r = nb.mixf(fz, r, min(0.85, rough + 0.25))
    # micro scratches & scuffs
    sc = nb.scratches(70, scratch)
    scuff = nb.mul(nb.smooth(nb.noise(scale=30, detail=6), 0.62, 0.8), scratch)
    sc = nb.maxf(sc, nb.mul(scuff, nb.maxf(nb.edge, 0.3)))
    c = nb.mixc(nb.mul(sc, 0.45), c, nb.hsv(color, s=0.55, v=1.35))
    r = nb.mixf(sc, r, min(0.9, rough + 0.3))
    # stress whitening on sharp convex edges
    if stress > 0:
        sw = nb.mul(nb.smooth(nb.edge, 0.3, 0.9), stress)
        c = nb.mixc(nb.mul(sw, 0.5), c, nb.hsv(color, s=0.45, v=1.5))
    h = nb.mul(nb.noise(scale=900, detail=1, rough=0.4), textured)
    h = nb.sub(h, nb.mul(sc, 0.5))
    s = nb.st(c, r, 0.0, h)
    if label:
        s = nb.label(s, wear=label_wear, rough=0.55)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.00025)


def painted_metal(name, paint, primer="#7a3b22", bare="#8c8a86", chip=0.45, rust=0.4, gloss=0.42,
                  streaks=0.4, dirt=0.5, dust=0.35, ground=0.0, label=False, label_wear=0.35,
                  fade=0.25, role="base", orange_peel=0.4):
    """Enamel over red-oxide primer over steel; chipped edges, rust blooms & streaks."""
    nb = NB(name, role)
    pc = _var(nb, paint, 0.06, 3.0)
    fz = nb.clamp(nb.mul(nb.mul(nb.up, nb.noise(scale=2, detail=2)), fade * 1.6))
    pc = nb.mixc(fz, pc, nb.hsv(paint, s=0.7, v=1.15))
    paint_s = nb.st(pc, nb.madd(nb.noise(scale=6, detail=3), 0.12, gloss - 0.06), 0.0,
                    nb.mul(nb.noise(scale=500, detail=1), 0.15 * orange_peel))
    prim_s = nb.st(_var(nb, primer, 0.08), 0.7, 0.0, -0.3)
    rust_c = nb.ramp(nb.noise(scale=35, detail=8, rough=0.7), [(0.2, "#3a1a0c"), (0.5, "#7a3613"), (0.75, "#a4561f"), (0.95, "#c27a3a")])
    rust_s = nb.st(rust_c, nb.madd(nb.noise(scale=60, detail=4), 0.15, 0.8), 0.0,
                   nb.mul(nb.noise(scale=120, detail=6, rough=0.75), 0.6))
    bare_s = nb.st(_var(nb, bare, 0.08, 20), 0.38, 1.0, -0.4)
    # chipping: primer ring around bare/rusted centre
    ch = nb.edge_wear(chip, 35)
    ch_rand = nb.smooth(nb.noise(scale=18, detail=8, rough=0.7), 0.72 - chip * 0.08, 0.76 - chip * 0.08)
    chips = nb.maxf(ch, nb.mul(ch_rand, chip))
    inner = nb.smooth(nb.sub(chips, 0.0), 0.55, 0.85)
    s = nb.layer(paint_s, prim_s, chips)
    core = nb.layer(bare_s, rust_s, nb.smooth(nb.noise(scale=12, detail=4), 0.4 - rust * 0.3, 0.6 - rust * 0.3))
    s = nb.layer(s, core, inner)
    # rust blooms from cavities and streaks running down
    if rust > 0:
        bloom = nb.mul(nb.smooth(nb.add(nb.mul(nb.cav, 1.3), nb.noise(scale=7, detail=6)), 1.0 - rust * 0.35, 1.25 - rust * 0.35), rust)
        s = nb.layer(s, rust_s, nb.clamp(bloom))
    if streaks > 0:
        sv = nb.coords((45, 45, 2.2))
        st_n = nb.smooth(nb.noise(sv, scale=1.0, detail=4, rough=0.6), 0.58, 0.8)
        side = nb.inv(nb.pow(nb.up, 0.5))
        f = nb.clamp(nb.mul(nb.mul(st_n, side), streaks * 0.75))
        sc = nb.mixc(0.5, rust_s["col"], "#4a3426")
        s["col"] = nb.mixc(f, s["col"], sc)
        s["rough"] = nb.mixf(f, s["rough"], 0.75)
    sc = nb.scratches(55, 0.4)
    s["col"] = nb.mixc(nb.mul(sc, 0.5), s["col"], nb.hsv(paint, s=0.6, v=1.3))
    if label:
        s = nb.label(s, wear=label_wear, rough=0.5)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0006)


def metal(name, kind="galvanized", dirt=0.4, dust=0.2, ground=0.0, wear=0.4, soot=0.0, rust=0.0,
          tint=None, label=False, label_wear=0.3, role="base", dents=0.0):
    """Bare metals. kind: galvanized, stainless, aluminium, cast_iron, brass, gold, chrome, copper, tin."""
    nb = NB(name, role)
    base = {
        "galvanized": ("#9a9d9e", 0.42, 1.0), "stainless": ("#b8b8b6", 0.28, 1.0),
        "aluminium": ("#b9b9b6", 0.38, 1.0), "cast_iron": ("#3d3b39", 0.62, 0.75),
        "brass": ("#c99a4c", 0.3, 1.0), "gold": ("#e2b04a", 0.2, 1.0), "chrome": ("#d6d6d4", 0.08, 1.0),
        "copper": ("#c27a4c", 0.32, 1.0), "tin": ("#a7a6a1", 0.36, 1.0), "silver": ("#cfcfcc", 0.22, 1.0),
    }[kind]
    col, rough, met = base
    if tint:
        col = tint
    c = _var(nb, col, 0.05, 6)
    r = nb.madd(nb.noise(scale=10, detail=4), 0.12, rough - 0.06)
    h = 0.0
    if kind == "galvanized":
        sp = nb.voronoi(scale=45, out="Color")
        spv, _, _ = nb.sepc(sp)
        c = nb.mixc(nb.mul(spv, 0.35), c, nb.hsv(col, v=0.82))
        r = nb.madd(spv, 0.18, r)
        wr = nb.mul(nb.smooth(nb.noise(scale=11, detail=6), 0.6, 0.75), 0.8)
        c = nb.mixc(wr, c, "#c9c7bf")
        r = nb.mixf(wr, r, 0.8)
        met = 1.0
    elif kind in ("stainless", "aluminium", "silver", "tin"):
        br = nb.noise(nb.coords((1, 1, 1)), scale=1, detail=0)
        brush = nb.noise(nb.coords((380, 380, 4)), scale=1.0, detail=2)
        r = nb.madd(brush, 0.16, nb.sub(r, 0.06))
        smudge = nb.smooth(nb.noise(scale=9, detail=5), 0.55, 0.75)
        r = nb.mixf(nb.mul(smudge, 0.6), r, rough + 0.22)
        h = nb.mul(brush, 0.15)
    elif kind == "cast_iron":
        pit = nb.noise(scale=180, detail=6, rough=0.8)
        h = nb.mul(pit, 0.6)
        polish = nb.smooth(nb.edge, 0.1, 0.6)
        c = nb.mixc(nb.mul(polish, 0.7), c, "#6f6c68")
        r = nb.mixf(polish, r, 0.35)
        rr = nb.clamp(nb.add(nb.mul(nb.cav, 1.5), nb.mul(nb.smooth(nb.noise(scale=6, detail=6), 0.55, 0.75), 0.8)))
        rust = max(rust, 0.5)
        rc = nb.ramp(nb.noise(scale=40, detail=6), [(0.2, "#3b1d0e"), (0.6, "#7a3a17"), (0.9, "#9b5523")])
        c = nb.mixc(nb.mul(rr, rust), c, rc)
        r = nb.mixf(nb.mul(rr, rust), r, 0.85)
    elif kind in ("brass", "gold", "copper"):
        tarn = nb.clamp(nb.add(nb.mul(nb.cav, 1.4), nb.mul(nb.inv(nb.ao), 1.0)))
        tcol = {"brass": "#5b4a2a", "gold": "#7a5a22", "copper": "#3f5a46"}[kind]
        c = nb.mixc(nb.mul(tarn, wear), c, tcol)
        r = nb.mixf(nb.mul(tarn, wear), r, 0.6)
        pol = nb.smooth(nb.edge, 0.2, 0.7)
        c = nb.mixc(nb.mul(pol, 0.5), c, nb.hsv(col, s=0.8, v=1.2))
        r = nb.mixf(pol, r, max(0.08, rough - 0.12))
    if dents > 0:
        h = nb.add(h, nb.mul(nb.noise(scale=3, detail=2), dents * 4))
    if soot > 0:
        sz = nb.smooth(nb.z, 0.0, 0.12 * soot + 0.05, 1.0, 0.0)
        sn = nb.smooth(nb.noise(scale=8, detail=6), 0.3, 0.7)
        f = nb.clamp(nb.mul(nb.mul(sz, sn), 1.4))
        c = nb.mixc(f, c, "#151311")
        r = nb.mixf(f, r, 0.9)
    if rust > 0 and kind not in ("cast_iron",):
        rr = nb.clamp(nb.mul(nb.add(nb.mul(nb.cav, 1.2), nb.mul(nb.smooth(nb.noise(scale=9, detail=6), 0.6, 0.78), 1.0)), rust))
        c = nb.mixc(rr, c, nb.ramp(nb.noise(scale=40, detail=6), [(0.3, "#4a2310"), (0.8, "#8f4a1d")]))
        r = nb.mixf(rr, r, 0.85)
        met = nb.mixf(rr, met, 0.0) if True else met
    sc = nb.scratches(80, wear)
    r = nb.mixf(nb.mul(sc, 0.8), r, nb.add(r, -0.08) if kind != "cast_iron" else 0.4)
    c = nb.mixc(nb.mul(sc, 0.25), c, nb.hsv(col, v=1.25))
    s = nb.st(c, r, met, h)
    if label:
        s = nb.label(s, wear=label_wear, rough=0.5, metal=0.0)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0004)


def wood(name, color="#8a5a34", axis="X", rings=40.0, weather_grey=0.25, rough=0.62, varnish=0.0,
         paint=None, peel=0.4, dirt=0.5, dust=0.35, ground=0.0, plank_var=0.12, label=False,
         label_wear=0.4, role="base", knots=0.4):
    """Wood with rings/fibres along `axis`, optional varnish or peeling paint."""
    nb = NB(name, role)
    sw = {"X": "yzx", "Y": "zxy", "Z": "xyz"}[axis]
    v = nb.coords((1, 1, 1), swizzle=sw)
    vd = nb.vadd(v, nb.vmul(nb.noise(v, scale=1.2, detail=3, col=True), (0.05, 0.05, 0.4)))
    ring = nb.wave(nb.vmul(vd, (1, 1, 0.08)), scale=rings, dist=6.0, detail=3, kind="RINGS", axis="Z",
                   profile="SAW")
    fib = nb.noise(nb.vmul(v, (90, 90, 3)), scale=1.0, detail=6, rough=0.6)
    late = nb.smooth(ring, 0.55, 0.95)
    dark = nb.hsv(color, v=0.62, s=1.1)
    c = nb.mixc(nb.mul(late, 0.75), _var(nb, color, plank_var, 1.2), dark)
    c = nb.mixc(nb.mul(fib, 0.35), c, nb.hsv(color, v=0.8))
    if knots > 0:
        kn = nb.voronoi(nb.vmul(v, (1, 1, 0.25)), scale=7, out="Distance")
        kmask = nb.mul(nb.smooth(kn, 0.06, 0.0), knots)
        c = nb.mixc(kmask, c, nb.hsv(color, v=0.35))
    grey = nb.clamp(nb.mul(nb.madd(nb.up, 0.5, 0.5), weather_grey * 1.4))
    grey = nb.mul(grey, nb.smooth(nb.noise(scale=3, detail=3), 0.2, 0.7))
    c = nb.mixc(grey, c, nb.mixc(0.6, "#8d867c", nb.hsv(color, s=0.3)))
    r = nb.madd(fib, 0.15, rough - 0.07)
    h = nb.add(nb.mul(late, 0.4), nb.mul(fib, 0.5))
    s = nb.st(c, r, 0.0, h)
    if varnish > 0:
        s["rough"] = nb.mixf(varnish, s["rough"], nb.madd(nb.noise(scale=12, detail=3), 0.15, 0.22))
        s["col"] = nb.mixc(varnish * 0.5, s["col"], nb.hsv(color, s=1.25, v=0.8))
    if paint:
        pnt = nb.st(_var(nb, paint, 0.06, 3), nb.madd(nb.noise(scale=7), 0.15, 0.48), 0.0,
                    nb.add(nb.mul(fib, 0.15), 0.6))
        pe = nb.maxf(nb.edge_wear(peel, 25), nb.mul(nb.smooth(nb.noise(nb.vmul(v, (6, 6, 1)), scale=4, detail=8, rough=0.7), 0.7 - peel * 0.15, 0.74 - peel * 0.15), 1.0))
        s = nb.layer(pnt, s, pe)
    if label:
        s = nb.label(s, wear=label_wear, rough=0.6)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0007)


def bamboo(name, color="#c9a865", axis="Z", node_spacing=0.28, dirt=0.4, dust=0.2, role="base",
           aged=0.4, rough=0.45):
    """Bamboo culm skin: glossy waxy surface, fine longitudinal fibres, darker growth nodes."""
    nb = NB(name, role)
    sw = {"X": "yzx", "Y": "zxy", "Z": "xyz"}[axis]
    v = nb.coords((1, 1, 1), swizzle=sw)
    _, _, a = nb.sep(v)
    fib = nb.noise(nb.vmul(v, (160, 160, 2)), scale=1, detail=4)
    nodez = nb.wave(nb.vmul(v, (0, 0, 1.0 / node_spacing)), scale=1.0, kind="BANDS", axis="Z",
                    profile="SAW", dist=0.0)
    nmask = nb.maxf(nb.smooth(nodez, 0.04, 0.0), nb.smooth(nodez, 0.96, 1.0))
    c = _var(nb, color, 0.08, 2.5)
    c = nb.mixc(nb.mul(fib, 0.3), c, nb.hsv(color, v=0.82))
    c = nb.mixc(nb.mul(nmask, 0.8), c, nb.hsv(color, v=0.55, s=1.2))
    spots = nb.mul(nb.smooth(nb.noise(scale=15, detail=6), 0.66, 0.78), aged)
    c = nb.mixc(spots, c, "#4b3a26")
    r = nb.madd(fib, 0.12, rough - 0.05)
    h = nb.add(nb.mul(nmask, 0.8), nb.mul(fib, 0.2))
    s = nb.weather(nb.st(c, r, 0.0, h), dirt=dirt, dust=dust)
    return nb.finish(s, bump=0.0006)


def weave(name, color="#b8915a", scale=55.0, dirt=0.4, dust=0.25, role="base", rough=0.62, gap=0.25,
          vary=0.12, axis="Z"):
    """Basketry/rattan/woven polypropylene: over-under strands from object coords."""
    nb = NB(name, role)
    sw = {"X": "yzx", "Y": "zxy", "Z": "xyz"}[axis]
    v = nb.coords((scale, scale, scale), swizzle=sw)
    vx, vy, vz = nb.sep(v)
    # strands run around (angle) and up (z); approximate with two band sets
    ang = nb.math("ARCTAN2", vy, vx)
    u = nb.mul(ang, scale / (2 * math.pi) * 0.25)
    w1 = nb.math("SINE", nb.mul(vz, math.pi))
    w2 = nb.math("SINE", nb.mul(nb.add(u, vz), math.pi * 0.5))
    over = nb.math("GREATER_THAN", nb.mul(w1, w2), 0.0)
    band1 = nb.math("ABSOLUTE", nb.math("SINE", nb.mul(vz, math.pi)))
    band2 = nb.math("ABSOLUTE", nb.math("SINE", nb.mul(u, math.pi)))
    hgt = nb.mixf(over, band1, band2)
    gapm = nb.smooth(hgt, 0.0, gap)
    c = _var(nb, color, vary, 3)
    strand = nb.noise(nb.vmul(v, (3, 3, 0.4)), scale=1.0, detail=2)
    c = nb.mixc(nb.mul(strand, 0.4), c, nb.hsv(color, v=0.78))
    c = nb.mixc(nb.inv(gapm), c, nb.hsv(color, v=0.3))
    r = nb.madd(strand, 0.12, rough - 0.06)
    s = nb.weather(nb.st(c, r, 0.0, nb.mul(hgt, 1.0)), dirt=dirt, dust=dust)
    return nb.finish(s, bump=0.0012)


def ceramic(name, color="#e9e4d8", rough=0.1, crackle=0.25, chip=0.25, pattern=None, unglazed_h=0.004,
            bisque="#cdbfa8", dirt=0.25, dust=0.15, label=False, label_wear=0.1, role="base", speckle=0.2):
    """Glazed ceramic/porcelain: glossy glaze with pooling, fine crazing, chipped rims, unglazed foot."""
    nb = NB(name, role)
    c = _var(nb, color, 0.035, 5)
    sp = nb.mul(nb.smooth(nb.noise(scale=260, detail=1), 0.72, 0.8), speckle)
    c = nb.mixc(sp, c, nb.hsv(color, v=0.55))
    # glaze pooling darker in cavities
    c = nb.mixc(nb.mul(nb.cav, 0.5), c, nb.hsv(color, s=1.3, v=0.75))
    r = nb.madd(nb.noise(scale=12, detail=2), 0.05, rough - 0.025)
    h = 0.0
    if crackle > 0:
        cr = nb.smooth(nb.voronoi(scale=60, feature="DISTANCE_TO_EDGE"), 0.02, 0.0)
        cr = nb.mul(cr, nb.mul(nb.smooth(nb.noise(scale=6), 0.4, 0.6), crackle))
        c = nb.mixc(nb.mul(cr, 0.6), c, nb.hsv(color, v=0.6))
        h = nb.mul(cr, -0.3)
    s = nb.st(c, r, 0.0, h)
    if pattern is not None:
        s = nb.label(s, wear=0.05, rough=rough + 0.02)
    if label:
        s = nb.label(s, wear=label_wear, rough=rough + 0.1)
    bis = nb.st(_var(nb, bisque, 0.06, 20), 0.85, 0.0, nb.mul(nb.noise(scale=300), 0.4))
    if chip > 0:
        s = nb.layer(s, bis, nb.edge_wear(chip * 0.7, 60))
    if unglazed_h > 0:
        s = nb.layer(s, bis, nb.smooth(nb.z, unglazed_h, unglazed_h * 0.5))
    s = nb.weather(s, dirt=dirt, dust=dust)
    return nb.finish(s, bump=0.0003)


def terracotta(name, color="#a8573a", salt=0.4, moss=0.3, dirt=0.5, dust=0.3, role="base", ground=0.3):
    nb = NB(name, role)
    c = _var(nb, color, 0.08, 4)
    grain = nb.noise(scale=220, detail=4, rough=0.7)
    c = nb.mixc(nb.mul(grain, 0.25), c, nb.hsv(color, v=0.75))
    salt_m = nb.mul(nb.smooth(nb.noise(nb.coords((6, 6, 14)), scale=1.5, detail=6), 0.55, 0.75), salt)
    c = nb.mixc(salt_m, c, "#d9d2c3")
    moss_m = nb.mul(nb.mul(nb.ground_mask(0.12), nb.smooth(nb.noise(scale=10, detail=6), 0.45, 0.65)), moss)
    c = nb.mixc(moss_m, c, "#4a5a2a")
    wet = nb.mul(nb.ground_mask(0.06), 0.5)
    c = nb.mixc(wet, c, nb.hsv(color, v=0.6))
    s = nb.st(c, nb.madd(grain, 0.1, 0.8), 0.0, nb.mul(grain, 0.6))
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0005)


def concrete(name, color="#9b978e", rough=0.85, stains=0.4, moss=0.15, dirt=0.5, dust=0.3,
             ground=0.4, aggregate=0.5, label=False, label_wear=0.5, role="base", pores=0.5):
    nb = NB(name, role)
    c = _var(nb, color, 0.07, 1.5)
    ag = nb.voronoi(scale=90, out="Color")
    agv, _, _ = nb.sepc(ag)
    agm = nb.mul(nb.smooth(nb.voronoi(scale=90, feature="F1"), 0.18, 0.05), aggregate)
    c = nb.mixc(nb.mul(agm, 0.5), c, nb.hsv(color, v=nb.madd(agv, 0.6, 0.7)))
    pr = nb.smooth(nb.noise(scale=420, detail=2), 0.68, 0.74)
    c = nb.mixc(nb.mul(pr, 0.4 * pores), c, nb.hsv(color, v=0.45))
    if stains > 0:
        sv = nb.coords((14, 14, 1.2))
        st = nb.mul(nb.smooth(nb.noise(sv, scale=1, detail=5, rough=0.65), 0.5, 0.8), stains)
        c = nb.mixc(st, c, nb.hsv(color, v=0.6, s=0.8))
    if moss > 0:
        mm = nb.mul(nb.mul(nb.madd(nb.up, 0.6, nb.ground_mask(0.3)), nb.smooth(nb.noise(scale=12, detail=6), 0.55, 0.7)), moss)
        c = nb.mixc(nb.clamp(mm), c, "#46512b")
    h = nb.sub(nb.mul(nb.noise(scale=60, detail=6, rough=0.7), 0.5), nb.mul(pr, pores))
    s = nb.st(c, nb.madd(nb.noise(scale=20), 0.08, rough - 0.04), 0.0, h)
    if label:
        s = nb.label(s, wear=label_wear, rough=0.8)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0008)


def cardboard(name, color="#b48a5c", flute_axis="X", wet=0.3, scuff=0.5, label=True, label_wear=0.25,
              dirt=0.45, dust=0.3, ground=0.3, role="base", crush=0.5):
    """Corrugated kraft board: fibres, faint flute ribs, crushed whitish edges, water rings, print."""
    nb = NB(name, role)
    c = _var(nb, color, 0.06, 3)
    fib = nb.noise(scale=350, detail=3, rough=0.7)
    c = nb.mixc(nb.mul(fib, 0.18), c, nb.hsv(color, v=0.82))
    fl = {"X": nb.x, "Y": nb.y, "Z": nb.z}[flute_axis]
    flute = nb.math("ABSOLUTE", nb.math("SINE", nb.mul(fl, 2 * math.pi / 0.0085)))
    h = nb.add(nb.mul(flute, 0.25), nb.mul(fib, 0.2))
    if crush > 0:
        ce = nb.edge_wear(crush, 40)
        c = nb.mixc(nb.mul(ce, 0.55), c, nb.hsv(color, s=0.55, v=1.25))
        h = nb.sub(h, nb.mul(ce, 0.5))
    if wet > 0:
        ring = nb.voronoi(scale=4, feature="F1")
        wr = nb.mul(nb.smooth(nb.noise(scale=3, detail=4), 0.55, 0.62), wet)
        edge_line = nb.mul(nb.smooth(nb.math("ABSOLUTE", nb.sub(nb.noise(scale=3, detail=4), 0.6)), 0.01, 0.0), wet)
        c = nb.mixc(wr, c, nb.hsv(color, v=0.72, s=1.15))
        c = nb.mixc(edge_line, c, nb.hsv(color, v=0.5, s=1.2))
    r = nb.madd(fib, 0.08, 0.84)
    s = nb.st(c, r, 0.0, h)
    if scuff > 0:
        sc = nb.scratches(40, scuff)
        s["col"] = nb.mixc(nb.mul(sc, 0.4), s["col"], nb.hsv(color, s=0.5, v=1.3))
    if label:
        s = nb.label(s, wear=label_wear, rough=0.7)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0006)


def paper(name, color="#e8e0cc", aged=0.4, label=True, label_wear=0.15, role="2s", rough=0.82, dirt=0.2,
          fibre=0.5, gloss=False):
    nb = NB(name, role)
    c = _var(nb, color, 0.04, 6)
    fb = nb.noise(scale=500, detail=3)
    c = nb.mixc(nb.mul(fb, 0.12 * fibre), c, nb.hsv(color, v=0.85))
    if aged > 0:
        ag = nb.mul(nb.clamp(nb.add(nb.mul(nb.edge, 1.5), nb.smooth(nb.noise(scale=5, detail=6), 0.5, 0.8))), aged)
        c = nb.mixc(ag, c, nb.hsv(color, s=1.8, v=0.78, h=0.48))
        fox = nb.mul(nb.smooth(nb.noise(scale=40, detail=4), 0.75, 0.8), aged)
        c = nb.mixc(fox, c, "#9a7a4a")
    s = nb.st(c, rough if not gloss else 0.25, 0.0, nb.mul(fb, 0.3))
    if label:
        s = nb.label(s, wear=label_wear)
    s = nb.weather(s, dirt=dirt, dust=0.1)
    return nb.finish(s, bump=0.0002)


def fabric(name, color="#3a6ea5", weave_scale=900.0, rough=0.88, fade=0.3, dirt=0.4, dust=0.2,
           ground=0.0, label=False, label_wear=0.3, role="2s", sheen=True, stripes=None, wrinkle=0.5):
    """Woven textile: plain weave micro-bump, fading on top, folds/wrinkles, grime."""
    nb = NB(name, role)
    c = _var(nb, color, 0.07, 4)
    if stripes:
        st_col, st_scale = stripes
        band = nb.math("GREATER_THAN", nb.math("SINE", nb.mul(nb.z, st_scale)), 0.4)
        c = nb.mixc(band, c, st_col)
    fz = nb.clamp(nb.mul(nb.mul(nb.up, nb.noise(scale=2, detail=2)), fade * 1.5))
    c = nb.mixc(fz, c, nb.hsv(color, s=0.6, v=1.2))
    w1 = nb.math("ABSOLUTE", nb.math("SINE", nb.mul(nb.add(nb.x, nb.y), weave_scale)))
    w2 = nb.math("ABSOLUTE", nb.math("SINE", nb.mul(nb.z, weave_scale)))
    wv = nb.mul(w1, w2)
    fuzz = nb.noise(scale=400, detail=4)
    c = nb.mixc(nb.mul(wv, 0.15), c, nb.hsv(color, v=0.7))
    h = nb.add(nb.mul(wv, 0.5), nb.mul(nb.noise(scale=12, detail=3), wrinkle * 3.0))
    s = nb.st(c, nb.madd(fuzz, 0.08, rough - 0.04), 0.0, h)
    if label:
        s = nb.label(s, wear=label_wear, rough=0.8)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    if sheen:
        nb.bsdf.inputs["Sheen Weight"].default_value = 0.4
    return nb.finish(s, bump=0.0003)


def rubber(name, color="#1e1e1e", rough=0.78, dirt=0.4, dust=0.35, ground=0.0, role="base", wear=0.4):
    nb = NB(name, role)
    c = _var(nb, color, 0.08, 6)
    pol = nb.mul(nb.smooth(nb.edge, 0.2, 0.8), wear)
    r = nb.mixf(pol, nb.madd(nb.noise(scale=30), 0.1, rough - 0.05), rough - 0.25)
    c = nb.mixc(nb.mul(nb.up, 0.25 * wear), c, "#5a5550")
    s = nb.st(c, r, 0.0, nb.mul(nb.noise(scale=300, detail=3), 0.3))
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground, dust_col="#9a9084")
    return nb.finish(s, bump=0.0002)


def styrofoam(name, color="#eeeee8", dirt=0.6, dust=0.3, ground=0.4, label=False, role="base"):
    nb = NB(name, role)
    beads = nb.voronoi(scale=260, feature="F1")
    cells = nb.voronoi(scale=260, feature="DISTANCE_TO_EDGE")
    c = _var(nb, color, 0.03, 4)
    c = nb.mixc(nb.mul(nb.smooth(cells, 0.06, 0.0), 0.25), c, nb.hsv(color, v=0.8))
    stains = nb.mul(nb.smooth(nb.noise(scale=5, detail=6), 0.55, 0.75), dirt)
    c = nb.mixc(stains, c, "#b5a98f")
    h = nb.smooth(beads, 0.5, 0.0)
    s = nb.st(c, nb.madd(beads, 0.1, 0.72), 0.0, h)
    if label:
        s = nb.label(s, wear=0.3, rough=0.6)
    s = nb.weather(s, dirt=dirt * 0.8, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0006)


def film(name, color="#d42a2a", crinkle=0.6, rough=0.18, role="lit", frame_shadow=0.0, gold=None):
    """Cellophane/plastic film for star lanterns (role lit: night emissive)."""
    nb = NB(name, role)
    c = _var(nb, color, 0.05, 3)
    cr = nb.voronoi(scale=35, out="Distance", feature="F1")
    cr2 = nb.voronoi(scale=90, feature="DISTANCE_TO_EDGE")
    c = nb.mixc(nb.mul(nb.smooth(cr2, 0.05, 0.0), 0.4), c, nb.hsv(color, s=0.6, v=1.4))
    h = nb.add(nb.mul(cr, crinkle), nb.mul(nb.smooth(cr2, 0.05, 0.0), crinkle * 0.5))
    s = nb.st(c, nb.madd(cr, 0.1, rough), 0.0, h)
    s = nb.label(s, wear=0.1, rough=0.35) if gold else s
    return nb.finish(s, bump=0.0008)


def silk(name, color="#c4202a", rough=0.55, role="lit", pattern=False, tassel=None):
    nb = NB(name, role)
    c = _var(nb, color, 0.05, 3)
    thr = nb.noise(nb.coords((600, 600, 20)), scale=1, detail=2)
    c = nb.mixc(nb.mul(thr, 0.2), c, nb.hsv(color, v=1.25))
    s = nb.st(c, nb.madd(thr, 0.1, rough - 0.05), 0.0, nb.mul(thr, 0.3))
    if pattern:
        s = nb.label(s, wear=0.05, rough=0.45)
    nb.bsdf.inputs["Sheen Weight"].default_value = 0.6
    return nb.finish(s, bump=0.0002)


def glass_opaque(name, color="#2f5f3a", rough=0.08, dirt=0.3, label=False, label_wear=0.15, role="base",
                 frost=0.0):
    """Thick tinted bottle glass baked as an opaque, glossy, dark-tinted surface."""
    nb = NB(name, role)
    c = _var(nb, color, 0.05, 6)
    fres = nb.pow(nb.inv(nb.up), 2.0)
    c = nb.mixc(nb.mul(fres, 0.2), c, nb.hsv(color, v=1.6))
    r = nb.madd(nb.noise(scale=10), 0.04, rough)
    sc = nb.scratches(120, 0.3)
    r = nb.mixf(sc, r, 0.35)
    if frost:
        r = nb.mixf(frost, r, 0.55)
    s = nb.st(c, r, 0.0, nb.mul(sc, -0.3))
    if label:
        s = nb.label(s, wear=label_wear, rough=0.7)
    s = nb.weather(s, dirt=dirt, dust=0.25)
    return nb.finish(s, bump=0.0002)


# --- organics -----------------------------------------------------------------
def fish_skin(name, back="#2f3c46", belly="#d9dcd6", stripe=None, scales=1.0, role="base", wet=True,
              dried=False):
    nb = NB(name, role)
    # body is modelled along X with dorsal side +Z
    t = nb.smooth(nb.add(nb.z, nb.mul(nb.noise(scale=30, detail=3), 0.006)), -0.004, 0.012)
    c = nb.mixc(t, belly, back)
    sc = nb.voronoi(nb.coords((1.0, 1.6, 1.6)), scale=260, feature="DISTANCE_TO_EDGE")
    scm = nb.smooth(sc, 0.08, 0.0)
    irid = nb.ramp(nb.noise(scale=40, detail=2), [(0.3, "#9fb3c0"), (0.5, "#c9c6a0"), (0.7, "#a5c3b6")])
    c = nb.mixc(nb.mul(nb.inv(t), 0.35), c, irid)
    c = nb.mixc(nb.mul(scm, 0.35 * scales), c, nb.hsv(back, v=0.5))
    if stripe:
        sb = nb.mul(nb.smooth(nb.math("ABSOLUTE", nb.sub(nb.z, 0.004)), 0.003, 0.0), 0.6)
        c = nb.mixc(sb, c, stripe)
    r = 0.22 if wet else 0.6
    if dried:
        c = nb.mixc(0.65, c, nb.ramp(nb.noise(scale=30, detail=5), [(0.2, "#5d4126"), (0.6, "#8a6a3e"), (0.9, "#b08a52")]))
        r = 0.7
    met = nb.mul(nb.inv(t), 0.0 if dried else 0.25)
    s = nb.st(c, nb.madd(scm, 0.15, r), met, nb.add(nb.mul(scm, 0.5), nb.mul(nb.noise(scale=80), 0.2)))
    return nb.finish(s, bump=0.0002)


def organic(name, colors, scale=6.0, rough=0.5, bump=0.0004, detail_scale=120.0, h_amp=0.5, role="base",
            spec_spots=None, sss=0.0, dirt=0.15, cav_dark=0.35, label=False):
    """Generic natural surface: colour ramp over noise + fine bump. colors: [(pos, hex)]."""
    nb = NB(name, role)
    n = nb.noise(scale=scale, detail=6, rough=0.6)
    c = nb.ramp(n, colors)
    fine = nb.noise(scale=detail_scale, detail=4)
    c = nb.mixc(nb.mul(fine, 0.15), c, nb.hsv(c, v=0.8))
    if spec_spots:
        sp = nb.smooth(nb.voronoi(scale=spec_spots[0], feature="F1"), spec_spots[1], 0.0)
        c = nb.mixc(sp, c, spec_spots[2])
    c = nb.mixc(nb.mul(nb.cav, cav_dark), c, nb.hsv(c, v=0.55))
    s = nb.st(c, nb.madd(fine, 0.1, rough - 0.05), 0.0, nb.mul(fine, h_amp))
    if label:
        s = nb.label(s, wear=0.0)
    if sss:
        nb.bsdf.inputs["Subsurface Weight"].default_value = sss
    s = nb.weather(s, dirt=dirt, dust=0.05, ao_in_albedo=0.3)
    return nb.finish(s, bump=bump)


def leaf(name, color="#3f6a2a", vein="#8aa865", variegate=None, rough=0.45, role="2s", edge_col=None,
         axis="X", dust=0.2, spots=0.2):
    """Leaf surface: midrib along leaf length (uses LabelUV-free object coords), waxy sheen, blemishes."""
    nb = NB(name, role)
    c = _var(nb, color, 0.1, 8)
    if variegate:
        band = nb.wave(nb.coords((1, 1, 1)), scale=40, dist=8, kind="BANDS", axis="Z", detail=4)
        c = nb.mixc(nb.mul(nb.smooth(band, 0.55, 0.8), 0.8), c, variegate)
    vn = nb.voronoi(scale=90, feature="DISTANCE_TO_EDGE")
    c = nb.mixc(nb.mul(nb.smooth(vn, 0.04, 0.0), 0.35), c, vein)
    if edge_col:
        c = nb.mixc(nb.smooth(nb.edge, 0.3, 0.8), c, edge_col)
    bl = nb.mul(nb.smooth(nb.noise(scale=25, detail=6), 0.7, 0.78), spots)
    c = nb.mixc(bl, c, "#6b5a2e")
    s = nb.st(c, nb.madd(nb.noise(scale=20), 0.1, rough - 0.05), 0.0, nb.mul(nb.smooth(vn, 0.04, 0.0), -0.5))
    nb.bsdf.inputs["Subsurface Weight"].default_value = 0.0
    s = nb.weather(s, dirt=0.15, dust=dust, ao_in_albedo=0.4)
    return nb.finish(s, bump=0.0003)


def soil(name, color="#3b2c20", role="base", pebbles=0.4, moss=0.2):
    nb = NB(name, role)
    n = nb.noise(scale=40, detail=8, rough=0.7)
    c = nb.mixc(nb.mul(n, 0.6), color, nb.hsv(color, v=1.5))
    pb = nb.smooth(nb.voronoi(scale=70, feature="F1"), 0.16, 0.05)
    pbc = nb.voronoi(scale=70, out="Color")
    c = nb.mixc(nb.mul(pb, pebbles), c, nb.mixc(0.5, "#8a8072", pbc))
    mm = nb.mul(nb.smooth(nb.noise(scale=8, detail=5), 0.62, 0.72), moss)
    c = nb.mixc(mm, c, "#3e5222")
    s = nb.st(c, 0.95, 0.0, nb.add(nb.mul(n, 0.7), nb.mul(pb, 0.6)))
    return nb.finish(s, bump=0.002)


def emissive_plain(name, color="#fff2d0", strength=1.0, role="lit", rough=0.3):
    """Lamp diffusers / bulbs: baked albedo is the lit colour (runtime adds emission at night)."""
    nb = NB(name, role)
    c = _var(nb, color, 0.03, 4)
    s = nb.st(c, rough, 0.0, nb.mul(nb.noise(scale=200), 0.1))
    s = nb.weather(s, dirt=0.25, dust=0.25, ao_in_albedo=0.2)
    return nb.finish(s, bump=0.0002)


def label_only(name, base="#ffffff", rough=0.5, role="base", wear=0.2, dirt=0.3, dust=0.2, metal=0.0,
               ground=0.0):
    """Printed sign face: the label sheet IS the surface (with wear and weathering)."""
    nb = NB(name, role)
    s = nb.st(_var(nb, base, 0.03), rough, metal, nb.mul(nb.noise(scale=300), 0.15))
    s = nb.label(s, wear=wear, rough=rough)
    s = nb.weather(s, dirt=dirt, dust=dust, ground=ground)
    return nb.finish(s, bump=0.0002)


def glass_material(name, tint=(0.9, 0.95, 0.95), alpha=0.18, rough=0.05) -> bpy.types.Material:
    """Unbaked transparent glass (separate object/material, name prefix 'glass_')."""
    m = bpy.data.materials.new(name if name.startswith("glass_") else "glass_" + name)
    m["role"] = "glass"
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = srgb(tint)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    b.inputs["IOR"].default_value = 1.5
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    return m
