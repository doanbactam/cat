"""Shared building blocks for the landmark kit (temple, market, lake, café, tea stall).

Built on the city-houses mesh builder (city_geo.MB) and component library (city_parts) which are used
read-only. Frame: Blender metres, Z up, front faces -Y (Godot +Z), origin documented per module.

LCtx extends city_parts.Ctx with:
  marks   : [(name, Vector)]           -> empties exported verbatim (MARKER_*, QUEST_*, LIGHT_*)
  zones   : [(name, centre, size)]     -> empties scaled to size/2 (SHELTER_*, REVERB_*) that the Godot
                                          post-import turns into Area3D boxes.
"""
from __future__ import annotations

import math
import os
import random
from typing import Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import common as C
import city_geo as G
import city_glb as GLB
import city_parts as P
import landmarks_mats as LM
from city_geo import MB, V
from city_parts import WHITE, mul

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "assets", "models", "landmarks")
TEX_REL = "../../textures"
TMP = os.path.join("/tmp", "city_landmarks_build")
IMPORT_SCRIPT = "res://assets/models/landmarks/_import/landmarks_post_import.gd"

LACQUER = (0.95, 0.9, 0.88, 1)
GOLD = (1.0, 0.95, 0.85, 1)
NO_GRIME = {"atlas", "atlas_cut", "atlas_lit", "glass_jar", "water", "lamp_globe", "bulb", "candle", "ceramic",
            "glass", "glass_lit", "signs", "signs_lit", "signs_v", "decals", "foliage", "laundry", "lamp", "goods",
            "dark", "solar", "chrome", "lm:gilt", "lm:bronze"}


class LCtx(P.Ctx):
    def __init__(self, mid: str, seed: int, pal: dict | None = None):
        super().__init__(mid, seed, pal or {})
        self.marks: list[tuple[str, Vector]] = []
        self.zones: list[tuple[str, Vector, Vector]] = []

    def mark_pt(self, name: str, p) -> None:
        self.marks.append((name, V(p)))

    def zone(self, name: str, mn, mx) -> None:
        mn, mx = V(mn), V(mx)
        self.zones.append((name, (mn + mx) / 2, V([abs(b - a) for a, b in zip(mn, mx)])))

    def mark(self) -> dict:
        m = super().mark()
        m.update(marks=len(self.marks), zones=len(self.zones))
        return m

    def xform_since(self, mark: dict, M: Matrix) -> None:
        super().xform_since(mark, M)
        for i in range(mark["marks"], len(self.marks)):
            n, p = self.marks[i]
            self.marks[i] = (n, M @ p)
        R = M.to_3x3()
        for i in range(mark["zones"], len(self.zones)):
            n, c, s = self.zones[i]
            s2 = R @ s
            self.zones[i] = (n, M @ c, V([abs(x) for x in s2]))


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def frame_along(a, b, up=(0, 0, 1)) -> tuple[Matrix, float]:
    """Matrix centred between a and b with local +Y along a->b, local +Z ~ up (orthonormal)."""
    A, B = V(a), V(b)
    y = (B - A)
    L = y.length
    y = y.normalized()
    u = V(up)
    x = y.cross(u)
    if x.length < 1e-6:
        x = V((1, 0, 0))
    x.normalize()
    z = x.cross(y).normalized()
    M = Matrix(((x.x, y.x, z.x, 0), (x.y, y.y, z.y, 0), (x.z, y.z, z.z, 0), (0, 0, 0, 1)))
    M.translation = (A + B) / 2
    return M, L


def col_slab(ctx: LCtx, a, b, half_w: float, thick: float, surface: str, tags=()) -> None:
    """Rotated box collider whose TOP face runs from a to b (width 2*half_w)."""
    M, L = frame_along(a, b)
    ctx.col((-half_w, -L / 2, -thick), (half_w, L / 2, 0.0), surface, tags, M)


def col_box(ctx: LCtx, mn, mx, surface: str, tags=()) -> None:
    ctx.col(mn, mx, surface, tags)


def atlas_quad(mb: MB, pts, cell: str, mat: str = "atlas", tint=WHITE, flip_u=False, inset=0.002, n=None):
    r = LM.cell(cell)
    P.quad_n(mb, pts, mat, tint, n, P.atlas_uv(r, inset, flip_u))


def atlas_box(mb: MB, mn, mx, cell: str, side_mat: str, tint=WHITE, face="-y", mat="atlas", side_tint=None):
    """Box whose one face shows an atlas cell, the rest side_mat."""
    x0, y0, z0 = mn
    x1, y1, z1 = mx
    skip = [face]
    mb.box(mn, mx, side_mat, side_tint or tint, skip=skip)
    if face == "-y":
        atlas_quad(mb, [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], cell, mat, tint, n=(0, -1, 0))
    elif face == "+y":
        atlas_quad(mb, [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)], cell, mat, tint, n=(0, 1, 0))
    elif face == "+z":
        atlas_quad(mb, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], cell, mat, tint, n=(0, 0, 1))
    elif face == "-x":
        atlas_quad(mb, [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)], cell, mat, tint, n=(-1, 0, 0))
    elif face == "+x":
        atlas_quad(mb, [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], cell, mat, tint, n=(1, 0, 0))


def lathe(mb: MB, base, profile: Sequence[tuple[float, float]], mat: str, tint=WHITE, sides: int = 16,
          cap_top: bool = True, smooth: bool = True, uvmode: str = "box") -> None:
    """Surface of revolution around +Z at base; profile = [(radius, z)] bottom->top."""
    bm = bmesh.new()
    b = V(base)
    rings = []
    for r, z in profile:
        ring = [bm.verts.new(b + V((math.cos(2 * math.pi * k / sides) * r, math.sin(2 * math.pi * k / sides) * r, z)))
                for k in range(sides)]
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            try:
                bm.faces.new([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]])
            except ValueError:
                pass
    if cap_top and profile[-1][0] > 1e-4:
        bm.faces.new(rings[-1])
    if profile[0][0] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add_bm(bm, mat, tint, uvmode, smooth=smooth)


def spiral_pts(c, r0, turns, ang0, plane="xz", flip=1, n=24, shrink=0.85, lift=0.0):
    """Points of a flat spiral (cloud curl) centred at c, in plane xz/yz/xy."""
    c = V(c)
    out = []
    for i in range(n):
        t = i / (n - 1)
        a = ang0 + flip * t * turns * 2 * math.pi
        r = r0 * (1 - shrink * t)
        ca, sa = math.cos(a) * r, math.sin(a) * r
        if plane == "xz":
            out.append(c + V((ca, lift * t, sa)))
        elif plane == "yz":
            out.append(c + V((lift * t, ca, sa)))
        else:
            out.append(c + V((ca, sa, lift * t)))
    return out


def cloud_curl(mb: MB, c, size: float, mat: str, tint=WHITE, plane="xz", flip=1, thick=None):
    """Original 'auspicious cloud' ornament: two opposed spirals joined by a swelling stem."""
    th = thick or size * 0.11
    c = V(c)
    off = {"xz": V((1, 0, 0)), "yz": V((0, 1, 0)), "xy": V((1, 0, 0))}[plane] * size * 0.45 * flip
    s1 = spiral_pts(c + off, size * 0.42, 1.15, math.pi, plane, -flip, 22)
    s2 = spiral_pts(c - off * 0.9, size * 0.32, 1.1, 0.0, plane, flip, 20)
    mb.tube(list(reversed(s1)) + s2[1:], th, mat, tint, sides=6,
            radii=[th * (0.55 + 0.6 * math.sin(math.pi * i / (len(s1) + len(s2) - 2))) for i in range(len(s1) + len(s2) - 1)])


def sag_cloth(mb: MB, p00, p10, p01, p11, mat: str, tint=WHITE, nu=10, nv=6, sag=0.08, seed=0, double=True,
              uv_scale=1.0):
    """Tarp / awning cloth patch between 4 corners with a centre sag and wrinkle noise.
    Box-free UVs: u along p00->p10 (m), v along p00->p01 (m), scaled by uv_scale/tile."""
    A, B, Cc, D = V(p00), V(p10), V(p01), V(p11)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    grid = []
    lu = (B - A).length
    lv = (Cc - A).length
    tile = LM.tile_m(mat) if (mat.startswith("lm:") or mat in LM.CM.SETS) else 1.0
    off = V((seed * 1.7, seed * 0.3, 0))
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            p = A.lerp(B, u).lerp(Cc.lerp(D, u), v)
            s = 4 * u * (1 - u) * 4 * v * (1 - v)
            p.z -= sag * s
            p.z += noise.noise(p * 2.3 + off) * 0.015 * s
            row.append(bm.verts.new(p))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            f = bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
            for l, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                l[uvl].uv = (ii / nu * lu / tile * uv_scale, jj / nv * lv / tile * uv_scale)
    if double:
        bmesh.ops.reverse_faces(bm, faces=[])
        faces = list(bm.faces)
        for f in faces:
            vs = [v for v in f.verts]
            nf = bm.faces.new([bm.verts.new(v.co - V((0, 0, 0.004))) for v in reversed(vs)])
            for l, l0 in zip(nf.loops, reversed(list(f.loops))):
                l[uvl].uv = l0[uvl].uv
    mb.add_bm(bm, mat, tint, "keep", src_uv=True, smooth=True)


def mound(mb: MB, cx, cy, z, rx, ry, h, cell: str, tint=WHITE, nu=10, nv=5):
    """Dome-shaped heap (produce, fish, snacks) textured with an atlas cell from the top."""
    r = LM.cell(cell)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for j in range(nv + 1):
        t = j / nv
        rr = math.cos(t * math.pi / 2)
        zz = z + h * math.sin(t * math.pi / 2)
        ring = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            ring.append(bm.verts.new((cx + math.cos(a) * rx * max(rr, 0.02), cy + math.sin(a) * ry * max(rr, 0.02), zz)))
        rings.append(ring)
    for j in range(nv):
        for i in range(nu):
            i2 = (i + 1) % nu
            f = bm.faces.new([rings[j][i], rings[j][i2], rings[j + 1][i2], rings[j + 1][i]])
            for l in f.loops:
                co = l.vert.co
                uu = 0.5 + (co.x - cx) / (2 * rx) * 0.96
                vv = 0.5 + (co.y - cy) / (2 * ry) * 0.96
                l[uvl].uv = (r[0] + (r[2] - r[0]) * uu, r[1] + (r[3] - r[1]) * vv)
    mb.add_bm(bm, "atlas", tint, "keep", src_uv=True, smooth=True)


# ---------------------------------------------------------------------------
# Small furniture / props shared by several landmarks
# ---------------------------------------------------------------------------
STOOL_COLS = [(0.72, 0.1, 0.08, 1), (0.12, 0.3, 0.65, 1), (0.75, 0.1, 0.1, 1), (0.1, 0.45, 0.6, 1),
              (0.85, 0.55, 0.1, 1), (0.15, 0.5, 0.25, 1)]


def plastic_stool(ctx: LCtx, x, y, z=0.0, col=None, h=0.26, top=0.27, rot=0.0, collide=True):
    """Low Vietnamese plastic stool (ghế nhựa đỏ/xanh) — tapered legs, ribbed top."""
    col = col or ctx.rng.choice(STOOL_COLS)
    mb = ctx.clutter
    R = G.rot_z(rot, (x, y, 0))
    s = top / 2
    mb.box((x - s, y - s, z + h - 0.025), (x + s, y + s, z + h), "plastic", col, bevel=0.012, xform=R)
    # top grid slots (dark recesses)
    for k in range(3):
        oy = -0.06 + k * 0.06
        mb.box((x - 0.07, y + oy - 0.008, z + h - 0.001), (x + 0.07, y + oy + 0.008, z + h + 0.0005), "dark",
               WHITE, xform=R)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = V((x + sx * (s - 0.02), y + sy * (s - 0.02), z + h - 0.02))
            b = V((x + sx * (s + 0.025), y + sy * (s + 0.025), z))
            mb.tube([R @ a, R @ b], 0.018, "plastic", col, sides=6, radii=[0.022, 0.016])
    # skirt
    for sx in (-1, 1):
        mb.box((x + sx * s - 0.006, y - s, z + h - 0.07), (x + sx * s + 0.006, y + s, z + h - 0.02), "plastic", col,
               xform=R)
        mb.box((x - s, y + sx * s - 0.006, z + h - 0.07), (x + s, y + sx * s + 0.006, z + h - 0.02), "plastic", col,
               xform=R)
    if collide:
        ctx.col((x - s, y - s, z), (x + s, y + s, z + h), "plastic")


def low_table(ctx: LCtx, x, y, z=0.0, w=0.6, d=0.45, h=0.42, col=(0.15, 0.35, 0.6, 1)):
    mb = ctx.clutter
    mb.box((x - w / 2, y - d / 2, z + h - 0.03), (x + w / 2, y + d / 2, z + h), "plastic", col, bevel=0.01)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((x + sx * (w / 2 - 0.05) - 0.02, y + sy * (d / 2 - 0.05) - 0.02, z),
                   (x + sx * (w / 2 - 0.05) + 0.02, y + sy * (d / 2 - 0.05) + 0.02, z + h - 0.03), "plastic", col)
    ctx.col((x - w / 2, y - d / 2, z + h - 0.03), (x + w / 2, y + d / 2, z + h), "plastic")


def tea_glass(mb: MB, x, y, z, tea=True, h=0.075, r=0.028, ice=False):
    lathe(mb, (x, y, z), [(r * 0.8, 0), (r, h)], "glass_jar", WHITE, sides=10, cap_top=False)
    if tea:
        lathe(mb, (x, y, z + 0.004), [(r * 0.78, 0), (r * 0.93, h * 0.75)], "plastic",
              (0.55, 0.38, 0.12, 1) if not ice else (0.62, 0.48, 0.2, 1), sides=10)
        if ice:
            for k in range(3):
                mb.box((x - 0.01 + k * 0.006, y - 0.008, z + h * 0.6), (x + 0.004 + k * 0.006, y + 0.008,
                                                                         z + h * 0.6 + 0.014), "glass_jar")


def teapot(mb: MB, x, y, z, s=1.0, tint=(0.86, 0.86, 0.82, 1), mat="ceramic"):
    lathe(mb, (x, y, z), [(0.035 * s, 0), (0.06 * s, 0.03 * s), (0.062 * s, 0.06 * s), (0.04 * s, 0.09 * s),
                           (0.028 * s, 0.095 * s)], mat, tint, sides=14)
    lathe(mb, (x, y, z + 0.095 * s), [(0.03 * s, 0), (0.024 * s, 0.012 * s), (0.008 * s, 0.022 * s),
                                      (0.001, 0.03 * s)], mat, tint, sides=12)
    mb.tube([(x + 0.05 * s, y, z + 0.04 * s), (x + 0.085 * s, y, z + 0.07 * s), (x + 0.1 * s, y, z + 0.095 * s)],
            0.008 * s, mat, tint, sides=6, radii=[0.011 * s, 0.008 * s, 0.006 * s])
    mb.tube([(x - 0.055 * s, y, z + 0.075 * s), (x - 0.085 * s, y, z + 0.06 * s), (x - 0.06 * s, y, z + 0.025 * s)],
            0.006 * s, mat, tint, sides=6)


def kettle(mb: MB, x, y, z, s=1.0, tint=(0.75, 0.74, 0.7, 1)):
    """Dented aluminium kettle (ấm nhôm) with bail handle."""
    lathe(mb, (x, y, z), [(0.09 * s, 0), (0.105 * s, 0.03 * s), (0.1 * s, 0.11 * s), (0.06 * s, 0.15 * s),
                           (0.04 * s, 0.16 * s), (0.035 * s, 0.17 * s)], "chrome", tint, sides=16)
    mb.cylinder((x, y, z + 0.17 * s), (0, 0, 1), 0.012 * s, 0.015 * s, "plastic", (0.08, 0.08, 0.08, 1), sides=8)
    mb.tube([(x + 0.085 * s, y, z + 0.05 * s), (x + 0.14 * s, y, z + 0.11 * s), (x + 0.16 * s, y, z + 0.15 * s)],
            0.012 * s, "chrome", tint, sides=6, radii=[0.018 * s, 0.012 * s, 0.009 * s])
    arc = [(x + math.cos(a) * 0.075 * s, y, z + 0.17 * s + math.sin(a) * 0.08 * s) for a in
           [math.pi * i / 10 for i in range(11)]]
    mb.tube(arc, 0.004 * s, "chrome", tint, sides=5)


def thermos(mb: MB, x, y, z, col=(0.65, 0.12, 0.1, 1)):
    """Chinese-style vacuum flask (phích nước) with painted metal body."""
    lathe(mb, (x, y, z), [(0.05, 0), (0.055, 0.01), (0.055, 0.27), (0.042, 0.3), (0.025, 0.32), (0.025, 0.34)],
          "metal_painted", col, sides=14)
    mb.cylinder((x, y, z + 0.34), (0, 0, 1), 0.028, 0.03, "plastic", (0.55, 0.42, 0.25, 1), sides=10)
    mb.tube([(x + 0.05, y, z + 0.08), (x + 0.075, y, z + 0.12), (x + 0.075, y, z + 0.22), (x + 0.05, y, z + 0.26)],
            0.008, "plastic", (0.15, 0.15, 0.15, 1), sides=6)


def jar(ctx: LCtx, x, y, z, cell: str, r=0.065, h=0.2, fill=0.8):
    """Glass snack jar (hũ nhựa/thuỷ tinh) with red lid; contents textured from the atlas."""
    mb = ctx.clutter
    mound(mb, x, y, z + 0.005, r * 0.92, r * 0.92, h * fill, cell, WHITE, nu=10, nv=4)
    # contents column (side view) as an atlas cylinder
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    cr = LM.cell(cell)
    sides = 10
    bot = [bm.verts.new((x + math.cos(2 * math.pi * k / sides) * r * 0.9, y + math.sin(2 * math.pi * k / sides) * r * 0.9,
                         z + 0.005)) for k in range(sides)]
    top = [bm.verts.new((v.co.x, v.co.y, z + 0.005 + h * fill * 0.6)) for v in bot]
    for k in range(sides):
        k2 = (k + 1) % sides
        f = bm.faces.new([bot[k], bot[k2], top[k2], top[k]])
        for l, (uu, vv) in zip(f.loops, ((k / sides, 0), ((k + 1) / sides, 0), ((k + 1) / sides, 0.6), (k / sides, 0.6))):
            l[uvl].uv = (cr[0] + (cr[2] - cr[0]) * uu, cr[1] + (cr[3] - cr[1]) * vv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add_bm(bm, "atlas", WHITE, "keep", src_uv=True, smooth=True)
    lathe(mb, (x, y, z), [(r, 0), (r, h * 0.92), (r * 0.8, h)], "glass_jar", WHITE, sides=14, cap_top=False)
    lid = ctx.rng.choice([(0.7, 0.08, 0.06, 1), (0.1, 0.35, 0.65, 1), (0.85, 0.65, 0.1, 1)])
    mb.cylinder((x, y, z + h), (0, 0, 1), r * 0.85, 0.03, "plastic", lid, sides=14)


def crate(ctx: LCtx, x, y, z, w=0.55, d=0.38, h=0.3, col=None, rot=0.0, collide=True, mb=None):
    """Plastic market crate (két nhựa) with side openings."""
    mb = mb or ctx.clutter
    col = col or ctx.rng.choice([(0.15, 0.35, 0.7, 1), (0.75, 0.15, 0.1, 1), (0.85, 0.6, 0.1, 1),
                                 (0.2, 0.5, 0.25, 1), (0.25, 0.25, 0.27, 1)])
    R = G.rot_z(rot, (x, y, 0))
    t = 0.012
    mb.box((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + t), "plastic", col, xform=R)
    for sx in (-1, 1):
        # long sides with 3 window slots: rails + posts
        yy = y + sx * (d / 2 - t / 2)
        mb.box((x - w / 2, yy - t / 2, z), (x + w / 2, yy + t / 2, z + 0.06), "plastic", col, xform=R)
        mb.box((x - w / 2, yy - t / 2, z + h - 0.05), (x + w / 2, yy + t / 2, z + h), "plastic", col, xform=R)
        for k in range(5):
            px = x - w / 2 + k * (w / 4)
            mb.box((px - 0.015, yy - t / 2, z), (px + 0.015, yy + t / 2, z + h), "plastic", col, xform=R)
        xx = x + sx * (w / 2 - t / 2)
        mb.box((xx - t / 2, y - d / 2, z), (xx + t / 2, y + d / 2, z + 0.06), "plastic", col, xform=R)
        mb.box((xx - t / 2, y - d / 2, z + h - 0.05), (xx + t / 2, y + d / 2, z + h), "plastic", col, xform=R)
        for k in range(3):
            py = y - d / 2 + k * (d / 2)
            mb.box((xx - t / 2, py - 0.015, z), (xx + t / 2, py + 0.015, z + h), "plastic", col, xform=R)
    if collide:
        if abs(rot) < 1e-3:
            ctx.col((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + h), "plastic")
        else:
            ctx.col((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + h), "plastic", (), R)


def wood_crate(ctx: LCtx, x, y, z, w=0.5, d=0.35, h=0.28, collide=True):
    mb = ctx.clutter
    tint = mul(WHITE, ctx.rng.uniform(0.85, 1.1))
    for k in range(3):
        zz = z + k * h / 3
        mb.box((x - w / 2, y - d / 2, zz + 0.01), (x + w / 2, y - d / 2 + 0.015, zz + h / 3 - 0.012), "lm:wood_aged",
               tint, uvmode="grain_h")
        mb.box((x - w / 2, y + d / 2 - 0.015, zz + 0.01), (x + w / 2, y + d / 2, zz + h / 3 - 0.012), "lm:wood_aged",
               tint, uvmode="grain_h")
    for sx in (-1, 1):
        mb.box((x + sx * w / 2 - 0.02 * (sx > 0), y - d / 2, z), (x + sx * w / 2 + 0.02 * (sx < 0), y + d / 2, z + h),
               "lm:wood_aged", tint)
    mb.box((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + 0.012), "lm:wood_aged", tint)
    if collide:
        ctx.col((x - w / 2, y - d / 2, z), (x + w / 2, y + d / 2, z + h), "wood")


def column(ctx: LCtx, x, y, z0, h, r, mat="lm:lacquer_red", tint=LACQUER, base=True, base_mat="lm:bluestone",
           collide=True, climb=False):
    """Round lacquered column on a carved bluestone base (chân tảng)."""
    if base:
        b = r * 1.75
        ctx.shell.box((x - b, y - b, z0), (x + b, y + b, z0 + 0.12), base_mat, WHITE, bevel=0.02)
        lathe(ctx.shell, (x, y, z0 + 0.12), [(r * 1.55, 0), (r * 1.5, 0.06), (r * 1.2, 0.12), (r * 1.05, 0.14)],
              base_mat, WHITE, sides=16)
        z0 += 0.14
    ctx.shell.tube([(x, y, z0), (x, y, z0 + h * 0.5), (x, y, z0 + h)], r, mat, tint, sides=18,
                   radii=[r, r * 1.02, r * 0.94])
    if collide:
        rr = r * 0.9
        ctx.col((x - rr, y - rr, z0 - (0.14 if base else 0)), (x + rr, y + rr, z0 + h), "wood",
                ("climb",) if climb else ())


def lantern_star(mb: MB, x, y, z, s=0.35, col=(0.85, 0.15, 0.1, 1)):
    """Mid-autumn star lantern (đèn ông sao) — 5-pointed bipyramid on a stick (festival dressing)."""
    bm = bmesh.new()
    c = V((x, y, z))
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        r = s if k % 2 == 0 else s * 0.42
        pts.append(bm.verts.new(c + V((math.cos(a) * r, 0, math.sin(a) * r))))
    f = bm.verts.new(c + V((0, -s * 0.25, 0)))
    b = bm.verts.new(c + V((0, s * 0.25, 0)))
    for k in range(10):
        bm.faces.new([pts[k], pts[(k + 1) % 10], f])
        bm.faces.new([pts[(k + 1) % 10], pts[k], b])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mb.add_bm(bm, "atlas", col, "box")


# ---------------------------------------------------------------------------
# Curved Vietnamese hip roof (mái cong, upturned corners)
# ---------------------------------------------------------------------------
class HipRoof:
    """Concave hip roof over an eave rectangle (cx±a, cy±b), b <= a. Height z = z_eave + H*t^p plus a
    corner uplift U*exp(-(s-d)/L)*(1-t)^2 (s = distance to the nearest eave corner along the eave,
    d = distance to the eave). Provides z(x,y) for ornaments and builds mesh + strip colliders."""

    def __init__(self, cx, cy, a, b, z_eave, H, p=1.45, U=0.75, L=1.6):
        self.cx, self.cy, self.a, self.b = cx, cy, a, b
        self.ze, self.H, self.p, self.U, self.L = z_eave, H, p, U, L

    def z_at(self, x, y):
        dx = self.a - abs(x - self.cx)
        dy = self.b - abs(y - self.cy)
        d = max(0.0, min(dx, dy))
        t = min(1.0, d / self.b)
        s = max(dx, dy)
        z = self.ze + self.H * t ** self.p
        z += self.U * math.exp(-max(0.0, s - d) / self.L) * (1 - t) ** 2
        return z

    def plane_pts(self, side: str, u: float, t: float):
        d = t * self.b
        if side in ("front", "back"):
            x = self.cx + (2 * u - 1) * (self.a - d)
            y = self.cy - self.b + d if side == "front" else self.cy + self.b - d
        else:
            y = self.cy + (2 * u - 1) * (self.b - d)
            x = self.cx + self.a - d if side == "right" else self.cx - self.a + d
        return V((x, y, self.z_at(x, y)))

    def build(self, ctx: LCtx, mat="roof_tile_old", tint=WHITE, soffit_mat="lm:wood_aged", nt=16, du=0.32,
              thick=0.22, mb=None, collide=True, sides=("front", "back", "left", "right"), surface="roof_tile"):
        mb = mb or ctx.shell
        tm = 2.0
        for side in sides:
            span = 2 * (self.a if side in ("front", "back") else self.b)
            nu = max(4, int(math.ceil(span / du)))
            bm = bmesh.new()
            uvl = bm.loops.layers.uv.new("UVMap")
            grid = []
            for j in range(nt + 1):
                t = (j / nt) ** 0.85
                grid.append([self.plane_pts(side, i / nu, t) for i in range(nu + 1)])
            # arc length along t for V
            arc = [[0.0] * (nu + 1)]
            for j in range(1, nt + 1):
                arc.append([arc[-1][i] + (grid[j][i] - grid[j - 1][i]).length for i in range(nu + 1)])
            top = [[bm.verts.new(p) for p in row] for row in grid]
            for j in range(nt):
                for i in range(nu):
                    vs = [top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]]
                    if len(set(vs)) < 3:
                        continue
                    try:
                        f = bm.faces.new(vs)
                    except ValueError:
                        continue
                    for l, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                        p = grid[jj][ii]
                        uu = p.x if side in ("front", "back") else p.y
                        l[uvl].uv = (uu / tm, arc[jj][ii] / tm)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
            for f in bm.faces:
                f.normal_update()
                if f.normal.z < 0:
                    f.normal_flip()
            mb.add_bm(bm, mat, tint, "keep", src_uv=True, smooth=True)
            # soffit (underside) and fascia
            bm2 = bmesh.new()
            bot = [[bm2.verts.new(p - V((0, 0, thick))) for p in row] for row in grid]
            for j in range(nt):
                for i in range(nu):
                    try:
                        f = bm2.faces.new([bot[j][i], bot[j + 1][i], bot[j + 1][i + 1], bot[j][i + 1]])
                    except ValueError:
                        continue
            bmesh.ops.remove_doubles(bm2, verts=bm2.verts, dist=1e-4)
            for f in bm2.faces:
                f.normal_update()
                if f.normal.z > 0:
                    f.normal_flip()
            mb.add_bm(bm2, soffit_mat, (0.55, 0.5, 0.48, 1), "box", smooth=True)
            # fascia band along the eave (t = 0)
            for i in range(nu):
                a0, a1 = grid[0][i], grid[0][i + 1]
                P.quad_n(mb, [a0 - V((0, 0, thick)), a1 - V((0, 0, thick)), a1 + V((0, 0, 0.03)), a0 + V((0, 0, 0.03))],
                         "lm:wood_aged", (0.45, 0.4, 0.36, 1),
                         n=(a1 - a0).cross(V((0, 0, 1))) * (1 if side in ("front", "right") else 1))
            # tile course lips every ~0.33 m of arc (silhouette of overlapping tiles near the eave)
            if collide:
                nb = 5
                for k in range(nb):
                    t0, t1 = k / nb, (k + 1) / nb
                    um = 0.5
                    pa, pb = self.plane_pts(side, um, t0), self.plane_pts(side, um, t1)
                    # band width at the upper edge (narrower) keeps the hip clean
                    if side in ("front", "back"):
                        hw = self.a - t1 * self.b
                    else:
                        hw = self.b - t1 * self.b
                    hw = max(hw, 0.25)
                    pa.z = self.ze + self.H * t0 ** self.p
                    pb.z = self.ze + self.H * t1 ** self.p
                    col_slab(ctx, pa + V((0, 0, 0.02)), pb + V((0, 0, 0.02)), hw, 0.25, surface)

    def hip_line(self, corner: tuple[int, int], n=14):
        """Points from the eave corner (sx, sy) up the hip to the ridge end."""
        sx, sy = corner
        pts = []
        for i in range(n + 1):
            t = i / n
            d = t * self.b
            x = self.cx + sx * (self.a - d)
            y = self.cy + sy * (self.b - d)
            pts.append(V((x, y, self.z_at(x, y))))
        return pts

    @property
    def ridge_z(self):
        return self.ze + self.H

    @property
    def ridge_half(self):
        return self.a - self.b


def roof_ornaments(ctx: LCtx, roof: HipRoof, mat="plaster_white", tint=(0.86, 0.84, 0.78, 1), cap_mat="roof_tile_old",
                   ridge_h=0.42, ridge_w=0.42, curl=1.0, centre="sun", walkable=True, mb=None):
    """Main ridge band with end curls + centre ornament, hip ridges ending in upswept corner tips."""
    mb = mb or ctx.detail
    zr = roof.ridge_z
    hx = roof.ridge_half
    cx, cy = roof.cx, roof.cy
    if hx > 0.05:
        mb.box((cx - hx - 0.1, cy - ridge_w / 2, zr - 0.15), (cx + hx + 0.1, cy + ridge_w / 2, zr + ridge_h), mat, tint,
               bevel=0.03)
        # tile cap with a rounded top
        mb.tube([(cx - hx - 0.12, cy, zr + ridge_h), (cx + hx + 0.12, cy, zr + ridge_h)], ridge_w * 0.38, cap_mat,
                (0.8, 0.75, 0.72, 1), sides=8)
        # relief panel band (frieze in the ridge face)
        for sgn in (-1, 1):
            yy = cy + sgn * (ridge_w / 2 + 0.004)
            n = (0, sgn, 0)
            pts = [(cx - hx + 0.2, yy, zr + 0.02), (cx + hx - 0.2, yy, zr + 0.02), (cx + hx - 0.2, yy, zr + ridge_h - 0.08),
                   (cx - hx + 0.2, yy, zr + ridge_h - 0.08)]
            atlas_quad(mb, pts, "frieze", "atlas", (0.85, 0.85, 0.85, 1), flip_u=sgn > 0, n=n)
        if walkable:
            ctx.col((cx - hx - 0.1, cy - ridge_w / 2, zr - 0.3), (cx + hx + 0.1, cy + ridge_w / 2, zr + ridge_h + 0.08),
                    "roof_tile")
        # end ornaments: tall curling scrolls (original "cloud-horn" finials)
        for sgn in (-1, 1):
            ex = cx + sgn * (hx + 0.05)
            base = V((ex, cy, zr + ridge_h))
            pts = [base, base + V((sgn * 0.05, 0, 0.35 * curl)), base + V((sgn * 0.2, 0, 0.75 * curl)),
                   base + V((sgn * 0.05, 0, 1.05 * curl))]
            sp = spiral_pts(base + V((-sgn * 0.12 * curl, 0, 1.0 * curl)), 0.18 * curl, 1.2, 0.0, "xz", -sgn, 18)
            mb.tube(pts + sp, 0.07 * curl, mat, tint, sides=7,
                    radii=[0.14 * curl, 0.12 * curl, 0.1 * curl, 0.085 * curl] + [0.08 * curl * (1 - 0.6 * i / 17) for i in range(18)])
            cloud_curl(mb, base + V((-sgn * 0.35 * curl, 0, 0.35 * curl)), 0.45 * curl, mat, tint, "xz", sgn)
    # centre ornament
    if centre == "sun" and hx > 0.3:
        base = V((cx, cy, zr + ridge_h))
        lathe(mb, base, [(0.18, 0), (0.12, 0.12), (0.16, 0.2), (0.1, 0.3)], mat, tint, sides=10)
        disc_c = base + V((0, 0, 0.62))
        mb.cylinder(disc_c - V((0, 0.05, 0)), (0, 1, 0), 0.3, 0.1, "lm:gilt", WHITE, sides=20)
        for k in range(8):
            a = k * math.pi / 4
            p0 = disc_c + V((math.cos(a) * 0.32, 0, math.sin(a) * 0.32))
            p1 = disc_c + V((math.cos(a + 0.35) * 0.55, 0, math.sin(a + 0.35) * 0.55))
            sp = spiral_pts(p1, 0.09, 0.9, a + 0.35 + math.pi / 2, "xz", 1, 8)
            mb.tube([p0] + sp, 0.035, mat, tint, sides=5, radii=[0.045] + [0.04 * (1 - 0.5 * i / 7) for i in range(8)])
        for sgn in (-1, 1):
            cloud_curl(mb, base + V((sgn * 0.75, 0, 0.25)), 0.55, mat, tint, "xz", sgn)
    # hip ridges + corner tips (all dimensions scale with `curl`)
    s = max(0.05, curl)
    hr = min(1.0, 1.7 * s)
    for sx in (-1, 1):
        for sy in (-1, 1):
            hl = roof.hip_line((sx, sy))
            pts = [p + V((0, 0, 0.12 * hr)) for p in hl]
            mb.tube(pts, 0.13 * hr, mat, tint, sides=6,
                    radii=[(0.1 + 0.05 * i / (len(pts) - 1)) * hr for i in range(len(pts))])
            mb.tube([p + V((0, 0, 0.1 * hr)) for p in hl], 0.09 * hr, cap_mat, (0.8, 0.75, 0.72, 1), sides=6)
            c0 = hl[0] + V((0, 0, 0.12 * hr))
            out = V((sx, sy, 0)).normalized()
            tip = [c0, c0 + (out * 0.35 + V((0, 0, 0.12))) * s, c0 + (out * 0.6 + V((0, 0, 0.42))) * s,
                   c0 + (out * 0.62 + V((0, 0, 0.78))) * s, c0 + (out * 0.48 + V((0, 0, 0.95))) * s]
            sp = spiral_pts(c0 + (out * 0.36 + V((0, 0, 0.9))) * s, 0.12 * s, 1.1, 0.0, "xy", 1, 10, lift=-0.08 * s)
            mb.tube(tip + sp[1:], 0.1 * s, mat, tint, sides=7,
                    radii=[x * hr for x in (0.13, 0.12, 0.1, 0.085, 0.07)] + [0.06 * hr * (1 - 0.6 * i / 9) for i in range(9)])
            # little flame curls along the lower hip
            if s > 0.5:
                for k, t in enumerate((0.18, 0.36)):
                    p = hl[int(t * (len(hl) - 1))] + V((0, 0, 0.22 * hr))
                    cloud_curl(mb, p, 0.32 * s, mat, tint, "xz" if abs(sx) > 0 else "yz", sx * sy)


def tile_eave_ends(mb: MB, roof: HipRoof, step=0.2, mat="roof_tile_old", tint=(0.8, 0.6, 0.5, 1)):
    """Row of small rounded tile ends along all four eaves (ngói diềm)."""
    for side in ("front", "back", "left", "right"):
        span = 2 * (roof.a if side in ("front", "back") else roof.b)
        n = int(span / step)
        for i in range(n):
            u0, u1 = (i + 0.1) / n, (i + 0.9) / n
            p0 = roof.plane_pts(side, u0, 0.0)
            p1 = roof.plane_pts(side, u1, 0.0)
            mid = (p0 + p1) / 2
            outn = (p1 - p0).cross(V((0, 0, 1))).normalized()
            if side in ("back", "left"):
                outn = -outn
            P.quad_n(mb, [p0 + V((0, 0, 0.01)), p1 + V((0, 0, 0.01)), mid + V((0, 0, 0.09)) + outn * 0.02,
                          mid + V((0, 0, 0.09)) + outn * 0.02 - (p1 - p0) * 0.001], mat, tint, n=-outn)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def to_godot(v):
    return [round(v.x, 3), round(v.z, 3), round(-v.y, 3)]


def make_grime(ctx: LCtx, height: float, seed: int, dirt=1.0):
    g = P.make_grime(ctx, height, seed, dirt=dirt)

    def f(co, n, mat):
        if mat in NO_GRIME:
            return (1.0, 1.0, 1.0)
        return g(co, n, mat)
    return f


def finish_and_export(spec: dict, ctx: LCtx, info: dict, preview=None, export=True, preview_views=None) -> dict:
    col = bpy.context.scene.collection
    H = info["height"]
    grime = make_grime(ctx, H, spec["seed"], spec.get("dirt", 1.0))
    rng = random.Random(spec["seed"])
    uvoff = (rng.random(), rng.random())
    objs = []
    for k in P.Ctx.LAYERS:
        ob = ctx.B[k].finish(LM.get, LM.tile_m, grime if k not in ("decals", "foliage") else None, col, uvoff)
        if ob is None:
            continue
        if k in ("shell", "detail", "clutter"):
            G.smooth_weighted(ob, 35.0)
        objs.append(ob)
    for i, c in enumerate(ctx.cols):
        mn, mx = c["mn"], c["mx"]
        size = [max(abs(mx[j] - mn[j]), 0.01) for j in range(3)]
        ctr = (mn + mx) / 2
        name = "col_" + c["surface"] + "".join("_" + t for t in c["tags"]) + f"_{i:03d}-convcolonly"
        ob = C.box(name, size, (0, 0, 0), col)
        for v in ob.data.vertices:
            v.co.z -= size[2] / 2
        ob.matrix_world = c["xform"] @ Matrix.Translation(ctr)
        ob.display_type = "WIRE"
        ob.hide_render = True
        objs.append(ob)
    for lst, pre in ((ctx.nap, "NAP"), (ctx.climb, "CLIMB"), (ctx.entr, "ENTRANCE"), (ctx.lights, "LIGHT_SHOP")):
        for i, p in enumerate(lst):
            e = bpy.data.objects.new(f"{pre}_{i:02d}", None)
            e.location = p
            col.objects.link(e)
            objs.append(e)
    counts: dict[str, int] = {}
    for name, p in ctx.marks:
        k = counts.get(name, 0)
        counts[name] = k + 1
        e = bpy.data.objects.new(name if name.startswith(("QUEST_", "MARKER_")) and k == 0 else f"{name}_{k:02d}", None)
        e.location = p
        col.objects.link(e)
        objs.append(e)
    for i, (name, c, s) in enumerate(ctx.zones):
        e = bpy.data.objects.new(f"{name}_{i:02d}", None)
        e.empty_display_type = "CUBE"
        e.location = c
        e.scale = (s.x / 2, s.y / 2, s.z / 2)
        col.objects.link(e)
        objs.append(e)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH"
               and "-col" not in o.name)
    path = os.path.join(OUT_DIR, spec["id"] + ".glb")
    if export:
        os.makedirs(TMP, exist_ok=True)
        tmp = os.path.join(TMP, spec["id"] + ".glb")
        C.export_glb(tmp, objects=objs)
        r = GLB.postprocess(tmp, LM.IMAGE_FILES, TEX_REL)
        if r["embedded_left"]:
            print("WARNING embedded images left:", r["embedded_left"])
        params = dict(GLB.GLB_IMPORT_PARAMS)
        params["import_script/path"] = IMPORT_SCRIPT
        GLB.write_import(path, "scene", "PackedScene", params)
        os.replace(tmp, path)
    for i, v in enumerate(preview_views or []):
        if preview and (preview == "all" or i == 0):
            C.preview_render(C.qa_path(f"city-landmarks/{spec['id']}{'' if i == 0 else '_' + str(i)}.png"), **v)
    markers = {}
    for name, p in ctx.marks:
        markers.setdefault(name, []).append(to_godot(p))
    entry = {
        "id": spec["id"],
        "file": f"res://assets/models/landmarks/{spec['id']}.glb",
        "kind": spec.get("kind", "landmark"),
        "width": spec["width"],
        "depth": spec["depth"],
        "height": round(H, 2),
        "floors": info.get("floors", 1),
        "style": spec["style"],
        "climb_points": [to_godot(p) for p in ctx.climb],
        "nap_spots": [to_godot(p) for p in ctx.nap],
        "entrances": [to_godot(p) for p in ctx.entr],
        "markers": markers,
        "zones": [{"name": n, "center": to_godot(c), "size": [round(s.x, 3), round(s.z, 3), round(s.y, 3)]}
                  for n, c, s in ctx.zones],
        "origin": spec.get("origin", "front facade bottom-centre at ground level"),
        "category": spec.get("category", ""),
        "colliders": len(ctx.cols),
        "tris": tris,
    }
    return entry
