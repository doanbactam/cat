"""Hồ Gương (Mirror Lake) kit: embankment segments, railing, red arched bridge, islet shrine, lamp post, bench.

Lake conventions (Blender): walkway level z = 0, water level z = -1.0, lake bed z = -1.6. Embankment pieces
have their water side toward -Y (Godot +Z) and their origin on the top water-side edge; land/paving
extends 3 m toward +Y. Pieces tile along X every 4 m (straight / steps) or chain every 30° (curve,
centre of curvature 8 m out over the water). The world area owns the water surface itself.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix

import city_geo as G
import city_parts as P
import landmarks_kit as K
from city_geo import V
from city_parts import WHITE, mul

WATER = -1.0
BED = -1.6
LAND = 3.0
COPE_W = 0.42
COPE_H = 0.12
STONE = (0.95, 0.95, 0.95, 1)
RED = (0.92, 0.86, 0.84, 1)
IRON = (0.32, 0.42, 0.36, 1)


def qa_water(size=40.0, z=WATER):
    """Preview-only water plane (not exported: finish_and_export exports only builder objects)."""
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, -size / 2 + 0.5, z))
    o = bpy.context.active_object
    o.name = "_qa_water_preview"
    m = bpy.data.materials.new("_qa_water")
    b = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (0.05, 0.08, 0.07, 1)
    b.inputs["Roughness"].default_value = 0.05
    o.data.materials.append(m)
    o.hide_select = True
    return o


def embank_strip(ctx: K.LCtx, pts, closed=False, land=LAND, paving=True, cope=True, wall_mat="lm:stone_embank",
                 collide=True):
    """Embankment along edge points (CCW seen from above with water on the RIGHT of travel... i.e. for a
    straight piece pts go -X -> +X and water is -Y). Builds battered wall face, coping, paving."""
    sh, dt = ctx.shell, ctx.detail
    P_ = [V((p[0], p[1], 0.0)) for p in pts]
    n = len(P_)
    segs = list(range(n if closed else n - 1))
    # outward (water) normal per vertex
    def water_n(i):
        a = P_[(i - 1) % n] if (closed or i > 0) else P_[i]
        b = P_[(i + 1) % n] if (closed or i < n - 1) else P_[i]
        d = (b - a).normalized()
        return V((d.y, -d.x, 0.0)).normalized()     # right-hand side of travel
    WN = [water_n(i) for i in range(n)]
    # arc length for UVs
    arc = [0.0]
    for i in segs:
        arc.append(arc[-1] + (P_[(i + 1) % n] - P_[i]).length)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    for k, i in enumerate(segs):
        j = (i + 1) % n
        a, b = P_[i], P_[j]
        na, nb = WN[i], WN[j]
        top_a, top_b = a + na * 0.0 + V((0, 0, -COPE_H * 0)), b + V((0, 0, 0))
        q = [a + na * 0.16 + V((0, 0, BED)), b + nb * 0.16 + V((0, 0, BED)), b + V((0, 0, -0.1)), a + V((0, 0, -0.1))]
        vs = [bm.verts.new(p) for p in q]
        f = bm.faces.new(vs)
        uv = [(arc[k] / 2, (BED + 1.25) / 2), (arc[k + 1] / 2, (BED + 1.25) / 2), (arc[k + 1] / 2, (-0.1 + 1.25) / 2),
              (arc[k] / 2, (-0.1 + 1.25) / 2)]
        for l, u in zip(f.loops, uv):
            l[uvl].uv = u
        f.normal_update()
        if f.normal.dot(na) < 0:
            f.normal_flip()
    sh.add_bm(bm, wall_mat, WHITE, "keep", src_uv=True)
    rng = ctx.rng
    if cope:
        for i in segs:
            j = (i + 1) % n
            a, b = P_[i], P_[j]
            L = (b - a).length
            nb_ = max(1, int(round(L / 0.9)))
            for s in range(nb_):
                pa = a.lerp(b, s / nb_)
                pb = a.lerp(b, (s + 1) / nb_)
                d = (pb - pa).normalized()
                pa2, pb2 = pa + d * 0.004, pb - d * 0.004
                drop = rng.uniform(-0.006, 0.006)
                prof = [(-COPE_W + 0.05, -0.14), (-COPE_W + 0.05, COPE_H + drop - 0.01), (-COPE_W + 0.06, COPE_H + drop),
                        (0.03, COPE_H + drop), (0.05, COPE_H + drop - 0.02), (0.05, -0.1)]
                # profile x positive = right of travel = water side
                dt.prism(prof, pa2, pb2, "lm:bluestone", mul(STONE, rng.uniform(0.86, 1.04)))
    if paving:
        for i in segs:
            j = (i + 1) % n
            a, b = P_[i], P_[j]
            la, lb = -WN[i], -WN[j]
            for r0, r1 in ((COPE_W - 0.05, 1.4), (1.4, land)):
                q = [a + la * r0, b + lb * r0, b + lb * r1, a + la * r1]
                P.quad_n(sh, [V((p.x, p.y, 0.0)) for p in q], "lm:brick_paving", WHITE, (0, 0, 1))
    if collide:
        # one rotated box per segment: wall+coping body, paving slab
        for i in segs:
            j = (i + 1) % n
            a, b = P_[i], P_[j]
            mid = (a + b) / 2
            wn = (WN[i] + WN[j]).normalized()
            M, L = K.frame_along(a, b)
            # local x = right of travel = water side
            ctx.col((-COPE_W + 0.05, -L / 2 - 0.01, BED), (0.05, L / 2 + 0.01, COPE_H), "concrete", ("wall",), M)
            if paving:
                ctx.col((-land, -L / 2 - 0.01, -0.4), (-COPE_W + 0.05, L / 2 + 0.01, 0.0), "tile", (), M)
    return WN


def build_straight(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    embank_strip(ctx, [(-2.0, 0.0), (0.0, 0.0), (2.0, 0.0)])
    # weathering: algae line + streaks under the coping on the water face
    P.decal_plane(ctx, "moss_base", V((0, -0.13, -0.55)), (0, -1, 0), 4.0, 0.6)
    P.decal_plane(ctx, "streak_2", V((ctx.rng.uniform(-1.4, 1.4), -0.13, -0.1)), (0, -1, 0), 1.0, 0.8)
    # mooring ring + iron bollard
    ctx.detail.tube([(0.6 + 0.06 * math.cos(a), -0.15, -0.35 + 0.06 * math.sin(a)) for a in
                     [i * math.pi / 6 for i in range(13)]], 0.008, "iron_wrought", sides=5)
    ctx.nap.append(V((1.2, 0.2, COPE_H + 0.005)))
    ctx.mark_pt("MARKER_shore", (0, 1.5, 0))
    qa_water()
    return ctx, {"height": 1.72, "floors": 0}


def build_curve(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    R = 8.0
    pts = []
    for k in range(7):
        th = math.radians(-15 + 5 * k)
        pts.append((R * math.sin(th), -R + R * math.cos(th)))
    embank_strip(ctx, pts)
    P.decal_plane(ctx, "moss_base", V((0, -0.13, -0.55)), (0, -1, 0), 2.0, 0.6)
    ctx.nap.append(V((0.0, 0.2, COPE_H + 0.005)))
    qa_water()
    return ctx, {"height": 1.72, "floors": 0}


def build_steps(spec):
    """Ghat steps down to a landing just above the water, flanked by cheek walls."""
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt = ctx.shell, ctx.detail
    embank_strip(ctx, [(-2.0, 0.0), (-1.15, 0.0)])
    embank_strip(ctx, [(1.15, 0.0), (2.0, 0.0)])
    # paving behind the stair opening
    P.quad_n(sh, [(-1.15, COPE_W - 0.05, 0), (1.15, COPE_W - 0.05, 0), (1.15, LAND, 0), (-1.15, LAND, 0)],
             "lm:brick_paving", WHITE, (0, 0, 1))
    ctx.col((-1.15, COPE_W - 0.05, -0.4), (1.15, LAND, 0.0), "tile")
    nst = 6
    rise = 0.85 / nst
    run = 0.3
    for k in range(nst):
        y0 = COPE_W - 0.05 - (k + 1) * run
        ztop = -(k + 1) * rise
        sh.box((-1.0, y0, BED), (1.0, y0 + run + 0.02, ztop), "lm:bluestone", mul(STONE, 0.9 + 0.03 * (k % 3)),
               bevel=0.01)
        ctx.col((-1.0, y0, BED), (1.0, y0 + run, ztop), "concrete")
    ylo = COPE_W - 0.05 - nst * run
    sh.box((-1.0, ylo - 0.9, BED), (1.0, ylo, -0.85), "lm:bluestone", STONE, bevel=0.01)
    ctx.col((-1.0, ylo - 0.9, BED), (1.0, ylo, -0.85), "concrete")
    # cheek walls
    for sx in (-1, 1):
        x0, x1 = (-1.15, -1.0) if sx < 0 else (1.0, 1.15)
        xa, xb = (x0 - 0.0, x1) if sx < 0 else (x0, x1)
        sh.box((xa, ylo - 0.9, BED), (xb, COPE_W, 0.12), "lm:stone_plinth", STONE)
        dt.box((xa - 0.04, ylo - 0.95, 0.12), (xb + 0.04, COPE_W, 0.2), "lm:bluestone", STONE, bevel=0.015)
        ctx.col((xa, ylo - 0.9, BED), (xb, COPE_W, 0.2), "concrete", ("wall",))
        # stone post with lotus cap at the top of each cheek
        px = sx * 1.08
        dt.box((px - 0.11, COPE_W - 0.25, 0.2), (px + 0.11, COPE_W - 0.03, 0.75), "lm:bluestone", STONE, bevel=0.015)
        K.lathe(dt, (px, COPE_W - 0.14, 0.75), [(0.11, 0), (0.14, 0.05), (0.1, 0.12), (0.02, 0.2)], "lm:bluestone", STONE,
                sides=10)
    P.decal_plane(ctx, "moss_base", V((0, ylo - 0.905, -0.6)), (0, -1, 0), 2.0, 0.5)
    ctx.nap.append(V((0.4, ylo - 0.4, -0.84)))
    ctx.mark_pt("MARKER_water_access", (0, ylo - 0.5, -0.85))
    qa_water()
    return ctx, {"height": 2.35, "floors": 0}


def build_railing(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    dt = ctx.detail
    y = 0.2
    for x in (-1.0, 1.0):
        dt.box((x - 0.08, y - 0.08, COPE_H), (x + 0.08, y + 0.08, 0.62), "lm:bluestone", STONE, bevel=0.012)
        K.lathe(dt, (x, y, 0.62), [(0.1, 0), (0.1, 0.03), (0.06, 0.07), (0.075, 0.1), (0.01, 0.16)], "lm:bluestone", STONE,
                sides=8)
        ctx.col((x - 0.08, y - 0.08, COPE_H), (x + 0.08, y + 0.08, 0.78), "concrete")
    for z in (0.32, 0.55):
        dt.tube([(-2.0, y, z), (2.0, y, z)], 0.022, "metal_painted", IRON, sides=8)
    # sagging decorative chain under the top rail
    for x0 in (-2.0, -1.0, 0.0, 1.0):
        dt.tube(G.catenary((x0, y, 0.5), (x0 + 1.0, y, 0.5), 0.08, 10), 0.006, "iron_wrought", sides=4)
    ctx.col((-2.0, y - 0.025, 0.53), (2.0, y + 0.025, 0.575), "metal")
    ctx.nap.append(V((0.0, y, 0.58)))  # balance-walk / perch spot on the top rail
    return ctx, {"height": 0.78, "floors": 0}


# ---------------------------------------------------------------------------
BR_L = 8.0      # half span
BR_H = 1.55     # rise
BR_W = 1.45     # half deck width


def deck_z(y):
    t = y / BR_L
    return BR_H * (1 - t * t) ** 1.0


def build_bridge(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    rng = ctx.rng
    # planks
    y = -BR_L
    k = 0
    while y < BR_L - 0.01:
        y1 = min(BR_L, y + 0.17)
        za, zb = deck_z(y), deck_z(y1)
        M, L = K.frame_along((0, y + 0.005, za), (0, y1 - 0.005, zb))
        sh.box((-BR_W, -L / 2, -0.05), (BR_W, L / 2, 0.0), "lm:wood_red_paint", mul(RED, rng.uniform(0.85, 1.02)),
               xform=M, uvmode="grain_h")
        y = y1
        k += 1
    # stringers + fascia boards (curved)
    n = 32
    for xs in (-BR_W + 0.1, -0.5, 0.5, BR_W - 0.1):
        pts = [(xs, -BR_L + 2 * BR_L * i / n, deck_z(-BR_L + 2 * BR_L * i / n) - 0.14) for i in range(n + 1)]
        dt.tube(pts, 0.09, "lm:wood_red_paint", mul(RED, 0.75), sides=4, square=True)
    for sx in (-1, 1):
        for i in range(n):
            ya, yb = -BR_L + 2 * BR_L * i / n, -BR_L + 2 * BR_L * (i + 1) / n
            P.quad_n(sh, [(sx * (BR_W + 0.02), ya, deck_z(ya) - 0.3), (sx * (BR_W + 0.02), yb, deck_z(yb) - 0.3),
                          (sx * (BR_W + 0.02), yb, deck_z(yb) + 0.01), (sx * (BR_W + 0.02), ya, deck_z(ya) + 0.01)],
                     "lm:wood_red_paint", RED, (sx, 0, 0))
    # deck colliders along the arch
    nseg = 10
    for i in range(nseg):
        ya, yb = -BR_L + 2 * BR_L * i / nseg, -BR_L + 2 * BR_L * (i + 1) / nseg
        K.col_slab(ctx, V((0, ya, deck_z(ya))), V((0, yb, deck_z(yb))), BR_W, 0.12, "wood")
    # piers: post pairs + cap beams + cross bracing
    for py in (-6.0, -3.5, -1.2, 1.2, 3.5, 6.0):
        zt = deck_z(py) - 0.2
        for sx in (-1, 1):
            dt.box((sx * 1.2 - 0.09, py - 0.09, BED), (sx * 1.2 + 0.09, py + 0.09, zt), "lm:wood_red_paint",
                   mul(RED, 0.8))
            # algae / water stain band on the posts
            dt.box((sx * 1.2 - 0.093, py - 0.093, WATER - 0.4), (sx * 1.2 + 0.093, py + 0.093, WATER + 0.12),
                   "lm:wood_aged", (0.35, 0.4, 0.3, 1))
        dt.box((-1.5, py - 0.1, zt - 0.05), (1.5, py + 0.1, zt + 0.08), "lm:wood_red_paint", mul(RED, 0.8))
        dt.tube([(-1.2, py, WATER + 0.1), (1.2, py, zt - 0.1)], 0.04, "lm:wood_red_paint", mul(RED, 0.75), sides=4,
                square=True)
        dt.tube([(1.2, py, WATER + 0.1), (-1.2, py, zt - 0.1)], 0.04, "lm:wood_red_paint", mul(RED, 0.75), sides=4,
                square=True)
    # railings
    npst = 16
    for sx in (-1, 1):
        x = sx * (BR_W - 0.06)
        post_y = [-BR_L + 0.15 + (2 * BR_L - 0.3) * i / npst for i in range(npst + 1)]
        for py in post_y:
            z0 = deck_z(py)
            dt.box((x - 0.06, py - 0.06, z0 - 0.05), (x + 0.06, py + 0.06, z0 + 0.95), "lm:wood_red_paint", RED,
                   bevel=0.01)
            K.lathe(dt, (x, py, z0 + 0.95), [(0.07, 0), (0.08, 0.03), (0.05, 0.07), (0.06, 0.1), (0.01, 0.17)],
                    "lm:wood_red_paint", RED, sides=8)
        # top handrail (walkable by the cat), mid rail, bottom rail
        for zoff, r in ((0.86, 0.055), (0.45, 0.03), (0.12, 0.03)):
            pts = [(x, py, deck_z(py) + zoff) for py in [-BR_L + 0.15 + (2 * BR_L - 0.3) * i / 40 for i in range(41)]]
            dt.tube(pts, r, "lm:wood_red_paint", RED, sides=4, square=True)
        for i in range(8):
            ya = -BR_L + 0.15 + (2 * BR_L - 0.3) * i / 8
            yb = -BR_L + 0.15 + (2 * BR_L - 0.3) * (i + 1) / 8
            K.col_slab(ctx, V((x, ya, deck_z(ya) + 0.91)), V((x, yb, deck_z(yb) + 0.91)), 0.05, 0.1, "wood")
            # rail wall (keeps the camera / cat from falling through the balusters)
            M, L = K.frame_along((x, ya, deck_z(ya)), (x, yb, deck_z(yb)))
            ctx.col((-0.03, -L / 2, 0.0), (0.03, L / 2, 0.8), "wood", (), M)
        # lattice: vertical balusters between bottom and mid rail, diagonal pairs above
        for i in range(int(2 * BR_L / 0.14)):
            py = -BR_L + 0.2 + i * 0.14
            if py > BR_L - 0.2:
                break
            z0 = deck_z(py)
            dt.box((x - 0.015, py - 0.015, z0 + 0.12), (x + 0.015, py + 0.015, z0 + 0.45), "lm:wood_red_paint", RED)
            if i % 2 == 0:
                dt.tube([(x, py, z0 + 0.45), (x, py + 0.14, deck_z(py + 0.14) + 0.86)], 0.012, "lm:wood_red_paint", RED,
                        sides=4, square=True)
                dt.tube([(x, py + 0.14, deck_z(py + 0.14) + 0.45), (x, py, z0 + 0.86)], 0.012, "lm:wood_red_paint",
                        RED, sides=4, square=True)
    # stone abutments with end posts
    for sy in (-1, 1):
        yb = sy * BR_L
        sh.box((-BR_W - 0.3, min(yb, yb + sy * 0.8), BED), (BR_W + 0.3, max(yb, yb + sy * 0.8), 0.0), "lm:stone_plinth",
               STONE)
        P.quad_n(sh, [(-BR_W - 0.3, min(yb, yb + sy * 0.8), 0.0), (BR_W + 0.3, min(yb, yb + sy * 0.8), 0.0),
                      (BR_W + 0.3, max(yb, yb + sy * 0.8), 0.0), (-BR_W - 0.3, max(yb, yb + sy * 0.8), 0.0)],
                 "lm:bluestone", STONE, (0, 0, 1))
        ctx.col((-BR_W - 0.3, min(yb, yb + sy * 0.8), BED), (BR_W + 0.3, max(yb, yb + sy * 0.8), 0.0), "concrete")
        for sx in (-1, 1):
            px, py = sx * (BR_W + 0.12), yb + sy * 0.4
            dt.box((px - 0.15, py - 0.15, 0), (px + 0.15, py + 0.15, 1.15), "lm:bluestone", STONE, bevel=0.02)
            K.lathe(dt, (px, py, 1.15), [(0.17, 0), (0.18, 0.05), (0.1, 0.14), (0.13, 0.2), (0.02, 0.32)], "lm:bluestone",
                    STONE, sides=10)
            ctx.col((px - 0.15, py - 0.15, 0), (px + 0.15, py + 0.15, 1.15), "concrete")
            ctx.nap.append(V((px, py, 1.16)))
    ctx.mark_pt("MARKER_riddle_bridge", (0, 0, BR_H))
    ctx.nap.append(V((0.6, 0.0, BR_H + 0.01)))
    ctx.entr += [V((0, -BR_L - 0.6, 0)), V((0, BR_L + 0.6, 0))]
    qa_water(60, WATER)
    return ctx, {"height": BR_H + 1.1 - BED, "floors": 0}


# ---------------------------------------------------------------------------
def build_islet(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    rng = ctx.rng
    # irregular rounded outline (clockwise seen from above => water on the right of travel = outside)
    n = 28
    pts = []
    for k in range(n):
        a = -2 * math.pi * k / n
        r = 1.0 + 0.06 * math.sin(3 * a + 0.4) + 0.04 * math.sin(5 * a + 1.3)
        pts.append((4.4 * r * math.cos(a), 3.4 * r * math.sin(a)))
    embank_strip(ctx, pts, closed=True, paving=False)
    # ground: gentle dome of leaf litter / packed earth with a stone-paved path
    bm = bmesh.new()
    rings = []
    for j, s in enumerate((1.0, 0.75, 0.5, 0.25)):
        ring = []
        for (x, y) in pts:
            ring.append(bm.verts.new((x * (s * 0.92 + 0.08 * (j == 0)) * (0.92 if j == 0 else 1.0),
                                      y * (s * 0.92 + 0.08 * (j == 0)) * (0.92 if j == 0 else 1.0),
                                      0.02 + 0.12 * (1 - s))))
        rings.append(ring)
    c = bm.verts.new((0, 0, 0.16))
    for j in range(len(rings) - 1):
        for k in range(n):
            bm.faces.new([rings[j][k], rings[j][(k + 1) % n], rings[j + 1][(k + 1) % n], rings[j + 1][k]])
    for k in range(n):
        bm.faces.new([rings[-1][k], rings[-1][(k + 1) % n], c])
    for f in bm.faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    sh.add_bm(bm, "lm:leaves_ground", WHITE, "box", smooth=True)
    ctx.col((-4.0, -3.0, -0.4), (4.0, 3.0, 0.1), "dirt")
    # path from the bridge landing (-Y) to the shrine
    for k in range(6):
        yy = -3.3 + k * 0.5
        sh.box((-0.55, yy, 0.0), (0.55, yy + 0.44, 0.06 + 0.02 * k), "lm:bluestone", mul(STONE, rng.uniform(0.85, 1.0)),
               bevel=0.01)
    # shrine pavilion
    sx0, sy0 = 0.0, 0.6
    sh.box((sx0 - 1.3, sy0 - 1.3, 0), (sx0 + 1.3, sy0 + 1.3, 0.25), "lm:stone_plinth", STONE, bevel=0.02)
    sh.box((sx0 - 1.15, sy0 - 1.15, 0.25), (sx0 + 1.15, sy0 + 1.15, 0.45), "lm:bluestone", STONE, bevel=0.02)
    ctx.col((sx0 - 1.3, sy0 - 1.3, 0), (sx0 + 1.3, sy0 + 1.3, 0.25), "concrete")
    ctx.col((sx0 - 1.15, sy0 - 1.15, 0.25), (sx0 + 1.15, sy0 + 1.15, 0.45), "concrete")
    for cx in (-0.85, 0.85):
        for cy in (-0.85, 0.85):
            K.column(ctx, sx0 + cx, sy0 + cy, 0.45, 1.9, 0.085)
    # back + side lattice screens
    dt.box((sx0 - 0.85, sy0 + 0.8, 0.45), (sx0 + 0.85, sy0 + 0.9, 2.3), "lm:plaster_temple", WHITE)
    ctx.col((sx0 - 0.85, sy0 + 0.8, 0.45), (sx0 + 0.85, sy0 + 0.9, 2.3), "concrete", ("wall",))
    K.atlas_quad(dt, [(sx0 - 0.45, sy0 + 0.795, 1.2), (sx0 + 0.45, sy0 + 0.795, 1.2), (sx0 + 0.45, sy0 + 0.795, 2.1),
                      (sx0 - 0.45, sy0 + 0.795, 2.1)], "shrine_back", n=(0, -1, 0))
    for sxx in (-1, 1):
        for k in range(7):
            yy = sy0 - 0.75 + k * 0.25
            dt.box((sx0 + sxx * 0.85 - 0.02, yy - 0.015, 1.5), (sx0 + sxx * 0.85 + 0.02, yy + 0.015, 2.3),
                   "lm:lacquer_red", K.LACQUER)
    dt.box((sx0 - 1.0, sy0 - 1.0, 2.3), (sx0 + 1.0, sy0 + 1.0, 2.45), "lm:lacquer_red", K.LACQUER, bevel=0.01)
    # altar: small stone table, incense bowl, fruit, vase
    cl.box((sx0 - 0.5, sy0 + 0.2, 0.45), (sx0 + 0.5, sy0 + 0.75, 1.15), "lm:bluestone", STONE, bevel=0.02)
    K.lathe(cl, (sx0, sy0 + 0.45, 1.15), [(0.07, 0), (0.12, 0.07), (0.13, 0.1)], "lm:bronze", WHITE, sides=12)
    for k in range(5):
        a = k * 1.2
        cl.tube([(sx0 + math.cos(a) * 0.03, sy0 + 0.45 + math.sin(a) * 0.03, 1.22),
                 (sx0 + math.cos(a) * 0.06, sy0 + 0.45 + math.sin(a) * 0.06, 1.45)], 0.003, "plastic",
                (0.65, 0.12, 0.08, 1), sides=3)
    K.lathe(cl, (sx0 - 0.3, sy0 + 0.45, 1.15), [(0.04, 0), (0.1, 0.03), (0.11, 0.05)], "ceramic", sides=12)
    K.mound(cl, sx0 - 0.3, sy0 + 0.45, 1.19, 0.09, 0.09, 0.07, "fruit_orange")
    K.lathe(cl, (sx0 + 0.3, sy0 + 0.45, 1.15), [(0.04, 0), (0.06, 0.08), (0.025, 0.18), (0.04, 0.22)], "ceramic",
            (0.3, 0.5, 0.7, 1), sides=12)
    ctx.col((sx0 - 0.5, sy0 + 0.2, 0.45), (sx0 + 0.5, sy0 + 0.75, 1.15), "concrete")
    ctx.mark_pt("LIGHT_ALTAR", (sx0, sy0 + 0.3, 1.6))
    roof = K.HipRoof(sx0, sy0, 1.45, 1.45, 2.45, 0.85, p=1.25, U=0.4, L=0.6)
    roof.build(ctx, nt=8, du=0.25, thick=0.12)
    K.tile_eave_ends(dt, roof, step=0.2)
    K.roof_ornaments(ctx, roof, ridge_h=0.2, ridge_w=0.2, curl=0.4, centre="none")
    K.lathe(dt, (sx0, sy0, roof.ridge_z - 0.05), [(0.16, 0), (0.1, 0.12), (0.13, 0.2), (0.06, 0.3), (0.08, 0.38),
                                                   (0.01, 0.55)], "lm:gilt", WHITE, sides=10)
    ctx.zone("SHELTER", (sx0 - 1.3, sy0 - 1.3, 0.45), (sx0 + 1.3, sy0 + 1.3, 2.3))
    # an old frangipani tree (hoa sứ) leaning over the water + shrubs
    tx, ty = -2.6, 1.2
    trunk = [(tx, ty, 0.05), (tx - 0.15, ty + 0.1, 0.9), (tx - 0.5, ty + 0.15, 1.6), (tx - 1.1, ty + 0.3, 2.1)]
    cl.tube(trunk, 0.14, "lm:wood_aged", (0.55, 0.5, 0.45, 1), sides=8, radii=[0.16, 0.12, 0.09, 0.06])
    for br in ([(tx - 0.15, ty + 0.1, 0.9), (tx + 0.4, ty + 0.2, 1.5), (tx + 0.7, ty + 0.1, 2.0)],
               [(tx - 0.5, ty + 0.15, 1.6), (tx - 0.4, ty + 0.7, 2.2)]):
        cl.tube(br, 0.06, "lm:wood_aged", (0.55, 0.5, 0.45, 1), sides=6, radii=[0.07, 0.05, 0.035][:len(br)])
    for (fx, fy, fz) in ((tx - 1.1, ty + 0.3, 2.1), (tx + 0.7, ty + 0.1, 2.0), (tx - 0.4, ty + 0.7, 2.2), (tx, ty, 2.3)):
        for k in range(3):
            P.foliage_card(ctx, fx, fy, fz - 0.45, 1.3, 0.95, "leafy", k * 60 + rng.uniform(0, 30),
                           mul(WHITE, rng.uniform(0.8, 1.0)))
    ctx.col((tx - 0.15, ty - 0.15, 0), (tx + 0.15, ty + 0.15, 1.2), "wood", ("climb",))
    ctx.climb.append(V((tx, ty - 0.2, 0.6)))
    for (bx, by) in ((2.8, 1.0), (2.2, -1.8), (-2.9, -1.4)):
        for k in range(3):
            P.foliage_card(ctx, bx, by, 0.05, 1.1, 0.8, rng.choice(["leafy", "fern"]), k * 60, mul(WHITE, 0.85))
    # stone stools
    for (bx, by) in ((1.9, -1.0), (-1.8, -0.4)):
        K.lathe(cl, (bx, by, 0.05), [(0.16, 0), (0.12, 0.2), (0.18, 0.4), (0.18, 0.42)], "lm:bluestone", STONE, sides=12)
        ctx.col((bx - 0.17, by - 0.17, 0), (bx + 0.17, by + 0.17, 0.47), "concrete")
        ctx.nap.append(V((bx, by, 0.48)))
    ctx.nap.append(V((sx0 + 1.1, sy0 - 1.1, 0.46)))
    ctx.mark_pt("MARKER_islet_shrine", (sx0, sy0 - 1.4, 0.05))
    ctx.mark_pt("MARKER_bridge_landing", (0, -3.5, 0.05))
    ctx.mark_pt("MARKER_pigeons", (1.5, -1.6, 0.1))
    qa_water(60, WATER)
    return ctx, {"height": roof.ridge_z + 0.6 - BED, "floors": 0}


# ---------------------------------------------------------------------------
def build_lamp(spec):
    """Lake promenade lamp: cast-iron post, fluted shaft, three opal globes on curled arms."""
    ctx = K.LCtx(spec["id"], spec["seed"])
    dt = ctx.detail
    iron = (0.22, 0.3, 0.26, 1)
    K.lathe(dt, (0, 0, 0), [(0.24, 0), (0.24, 0.08), (0.2, 0.12), (0.17, 0.4), (0.19, 0.45), (0.13, 0.52), (0.1, 0.6),
                            (0.085, 0.65)], "metal_painted", iron, sides=12, smooth=False)
    # fluted shaft: 8 ribs around a core
    dt.tube([(0, 0, 0.6), (0, 0, 3.0)], 0.06, "metal_painted", iron, sides=10, radii=[0.07, 0.05])
    for k in range(8):
        a = k * math.pi / 4
        dt.tube([(math.cos(a) * 0.066, math.sin(a) * 0.066, 0.66), (math.cos(a) * 0.05, math.sin(a) * 0.05, 2.95)],
                0.012, "metal_painted", iron, sides=4)
    for z in (1.2, 2.2, 3.0):
        K.lathe(dt, (0, 0, z), [(0.06, 0), (0.09, 0.03), (0.07, 0.06)], "metal_painted", iron, sides=10)
    ctx.col((-0.2, -0.2, 0), (0.2, 0.2, 0.6), "metal")
    ctx.col((-0.07, -0.07, 0.6), (0.07, 0.07, 3.05), "metal", ("climb",))
    # crown: lotus cup + central globe; two curled arms with globes
    def globe(x, y, z, r=0.15):
        K.lathe(dt, (x, y, z - 0.06), [(0.04, 0), (0.08, 0.03), (0.1, 0.06), (0.09, 0.08)], "metal_painted", iron, sides=10)
        prof = [(0.001 + r * math.sin(math.pi * i / 10), r - r * math.cos(math.pi * i / 10)) for i in range(11)]
        prof[0] = (0.06, 0.0)
        K.lathe(dt, (x, y, z), prof, "lamp_globe", WHITE, sides=14)
        K.lathe(dt, (x, y, z + 2 * r - 0.01), [(0.03, 0), (0.035, 0.03), (0.005, 0.08)], "metal_painted", iron, sides=8)
    globe(0, 0, 3.15, 0.17)
    for sx in (-1, 1):
        arm = [(0, 0, 2.75), (sx * 0.2, 0, 2.85), (sx * 0.38, 0, 2.95), (sx * 0.45, 0, 2.9)]
        dt.tube(arm, 0.02, "metal_painted", iron, sides=6)
        sp = K.spiral_pts((sx * 0.2, 0, 2.7), 0.08, 1.1, 0, "xz", sx, 14)
        dt.tube(sp, 0.01, "metal_painted", iron, sides=4)
        globe(sx * 0.45, 0, 2.92, 0.12)
    ctx.mark_pt("LIGHT_NIGHT", (0, 0, 3.1))
    return ctx, {"height": 3.55, "floors": 0}


def build_bench(spec):
    """Promenade bench: cast-iron end frames with scroll armrests, 5 seat slats + 3 back slats."""
    ctx = K.LCtx(spec["id"], spec["seed"])
    dt = ctx.detail
    iron = (0.22, 0.3, 0.26, 1)
    L2 = 0.9
    for x in (-0.8, 0.8):
        # leg frame: front leg, rear leg rising into the backrest, seat rail, scroll arm
        dt.tube([(x, 0.05, 0), (x, 0.08, 0.2), (x, 0.06, 0.42)], 0.022, "metal_painted", iron, sides=6, square=True)
        dt.tube([(x, 0.5, 0), (x, 0.47, 0.4), (x, 0.55, 0.85)], 0.022, "metal_painted", iron, sides=6, square=True)
        dt.tube([(x, 0.04, 0.42), (x, 0.5, 0.42)], 0.018, "metal_painted", iron, sides=6, square=True)
        arm = [(x, 0.5, 0.62), (x, 0.25, 0.64), (x, 0.06, 0.62)]
        dt.tube(arm, 0.02, "metal_painted", iron, sides=6)
        sp = K.spiral_pts((x, 0.08, 0.56), 0.06, 1.1, math.pi / 2, "yz", -1, 12)
        dt.tube(sp, 0.014, "metal_painted", iron, sides=5)
        sp2 = K.spiral_pts((x, 0.22, 0.24), 0.08, 1.2, 0, "yz", 1, 14)
        dt.tube(sp2, 0.01, "metal_painted", iron, sides=4)
    for k in range(5):
        y = 0.06 + k * 0.09
        dt.box((-L2, y, 0.42), (L2, y + 0.075, 0.455), "wood_brown", (1.25, 1.1, 0.95, 1), bevel=0.006, uvmode="grain_h")
    for k in range(3):
        z = 0.55 + k * 0.1
        y = 0.5 + (z - 0.5) * 0.17
        dt.box((-L2, y, z), (L2, y + 0.03, z + 0.075), "wood_brown", (1.25, 1.1, 0.95, 1), bevel=0.006, uvmode="grain_h")
    ctx.col((-L2, 0.04, 0.0), (L2, 0.52, 0.455), "wood")
    ctx.col((-L2, 0.5, 0.455), (L2, 0.6, 0.85), "wood")
    ctx.nap.append(V((0.2, 0.28, 0.46)))
    return ctx, {"height": 0.86, "floors": 0}
