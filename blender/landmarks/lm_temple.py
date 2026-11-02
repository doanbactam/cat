"""Đình Hàng Mây — the communal temple complex (one GLB).

Origin: street-front centre of the three-entrance gate (tam quan) at ground level. The complex
extends to +Y (Blender) = Godot -Z: x -13..13, y -1.2..36. Layout (Blender coords):
  y -1.2..1.2   tam quan gate (central 2.6 m opening, two 1.4 m side openings), flag pillars at x ±7
  y 0..36       courtyard walls (2.4 m, tile coping, ceramic vent blocks) — walkable tops
  y 2..20       paved courtyard (Bát Tràng bricks), bluestone central path,
                banyan planter (-7.5, 9) [MARKER_banyan: the tree is placed by vehicles-nature/world],
                bell frame (8, 9) [MARKER_bell], bronze incense burner (0, 15) [MARKER_burner]
  y 19..34.8    main hall (đại đình) on a 0.75 m stone platform: 5 bays, red lacquered columns on
                bluestone bases, carved door panels (central bay open), altar inside, sweeping
                concave hip roof with upturned corners, ridge ornaments, crow nest on the ridge
                [QUEST_crow_nest], east lean-to store shed = the roof route (wall -> shed -> eave).
"""
from __future__ import annotations

import math

from mathutils import Vector

import city_geo as G
import city_parts as P
import landmarks_kit as K
from city_geo import V
from city_parts import WHITE, mul

W2 = 13.0          # half width of the walled complex
D = 36.0           # depth
WALL_H = 2.4
WALL_T = 0.36
PLAT_H = 0.75      # hall platform height
BAYS = [-7.2, -4.4, -1.6, 1.6, 4.4, 7.2]
ROW_VER, ROW_FRONT, ROW_IN1, ROW_IN2, ROW_BACK = 21.3, 23.0, 26.0, 30.0, 33.0
STONE = (0.95, 0.95, 0.95, 1)
PLASTER = (1.0, 0.98, 0.95, 1)


def wall_coping(ctx: K.LCtx, a, b, z, t=WALL_T):
    """Little double-pitched tile cap on a wall from a to b (horizontal), walkable."""
    A, B = V(a), V(b)
    d = (B - A).normalized()
    prof = [(-t / 2 - 0.06, -0.02), (-t / 2 - 0.06, 0.03), (0, 0.16), (t / 2 + 0.06, 0.03), (t / 2 + 0.06, -0.02)]
    ctx.shell.prism(prof, A + V((0, 0, z)), B + V((0, 0, z)), "roof_tile_old", (0.85, 0.8, 0.78, 1))
    ctx.shell.prism([(-t / 2 - 0.02, -0.12), (-t / 2 - 0.02, 0.0), (t / 2 + 0.02, 0.0), (t / 2 + 0.02, -0.12)],
                    A + V((0, 0, z)), B + V((0, 0, z)), "stucco_detail", (0.92, 0.9, 0.84, 1))
    M, L = K.frame_along(A + V((0, 0, z)), B + V((0, 0, z)))
    ctx.col((-t / 2 - 0.04, -L / 2, -0.12), (t / 2 + 0.04, L / 2, 0.12), "roof_tile", (), M)


def vent_panel(ctx: K.LCtx, x0, x1, z0, z1, y, n=(0, -1, 0)):
    """Ceramic vent blocks (hoa gió): grid of quatrefoil cells, green glazed."""
    mb = ctx.detail
    cs = 0.2
    nx = int((x1 - x0) / cs)
    nz = int((z1 - z0) / cs)
    tint = (0.35, 0.55, 0.45, 1)
    for i in range(nx + 1):
        x = x0 + i * (x1 - x0) / nx
        mb.box((x - 0.012, y - 0.06, z0), (x + 0.012, y + 0.06, z1), "plaster_green", tint)
    for j in range(nz + 1):
        z = z0 + j * (z1 - z0) / nz
        mb.box((x0, y - 0.06, z - 0.012), (x1, y + 0.06, z + 0.012), "plaster_green", tint)
    for i in range(nx):
        for j in range(nz):
            cx = x0 + (i + 0.5) * (x1 - x0) / nx
            cz = z0 + (j + 0.5) * (z1 - z0) / nz
            mb.cylinder((cx, y - 0.05, cz), (0, 1, 0), 0.035, 0.1, "plaster_green", tint, sides=6)


def courtyard_walls(ctx: K.LCtx):
    sh = ctx.shell
    rng = ctx.rng
    segs = [  # (a, b) wall centre lines
        ((-W2, 0.18), (-5.4, 0.18)), ((5.4, 0.18), (W2, 0.18)),
        ((-W2 + 0.18, 0.0), (-W2 + 0.18, D)), ((W2 - 0.18, 0.0), (W2 - 0.18, D)),
        ((-W2, D - 0.18), (W2, D - 0.18)),
    ]
    for a, b in segs:
        A, B = V((a[0], a[1], 0)), V((b[0], b[1], 0))
        d = (B - A).normalized()
        L = (B - A).length
        nrm = V((-d.y, d.x, 0))
        # thick wall body as box rotated in plan
        M, _ = K.frame_along(A, B)
        sh.box((-WALL_T / 2, -L / 2, 0), (WALL_T / 2, L / 2, WALL_H), "lm:plaster_temple",
               PLASTER, xform=M)
        # base skirting (stone)
        sh.box((-WALL_T / 2 - 0.03, -L / 2, 0), (WALL_T / 2 + 0.03, L / 2, 0.35), "lm:stone_plinth", STONE, xform=M)
        # pilasters every ~3 m
        npil = int(L / 3.0)
        for k in range(npil + 1):
            t = -L / 2 + k * L / max(npil, 1)
            sh.box((-WALL_T / 2 - 0.06, t - 0.18, 0), (WALL_T / 2 + 0.06, t + 0.18, WALL_H + 0.05), "lm:plaster_temple",
                   mul(PLASTER, 0.95), bevel=0.02, xform=M)
        wall_coping(ctx, A, B, WALL_H)
        ctx.col((-WALL_T / 2, -L / 2, 0), (WALL_T / 2, L / 2, WALL_H), "concrete", ("wall",), M)
        for sgn in (-1, 1):
            P.wall_weathering(ctx, A + nrm * sgn * (WALL_T / 2 + 0.065), d, L, WALL_H, nrm * sgn, rng,
                              top_streaks=True, cat_level=sgn < 0)
    # vent panels in the front walls (both faces)
    for sx in (-1, 1):
        for xc in (7.6, 10.6):
            vent_panel(ctx, sx * xc - 0.6, sx * xc + 0.6, 1.1, 1.9, 0.18)
    # stone benches along the inner side walls
    for sx in (-1, 1):
        for yy in (5.0, 17.0):
            x = sx * (W2 - 0.9)
            ctx.shell.box((x - 0.25, yy - 0.9, 0.38), (x + 0.25, yy + 0.9, 0.48), "lm:bluestone", STONE, bevel=0.015)
            for dy in (-0.65, 0.65):
                ctx.shell.box((x - 0.2, yy + dy - 0.1, 0), (x + 0.2, yy + dy + 0.1, 0.38), "lm:bluestone", STONE)
            ctx.col((x - 0.25, yy - 0.9, 0), (x + 0.25, yy + 0.9, 0.48), "concrete")
            ctx.nap.append(V((x, yy + 0.4, 0.49)))


def gate(ctx: K.LCtx):
    sh, dt = ctx.shell, ctx.detail
    y0, y1 = -0.6, 1.0
    piers = [(-5.4, -3.8, 3.2), (-2.4, -1.3, 4.2), (1.3, 2.4, 4.2), (3.8, 5.4, 3.2)]
    for x0, x1, h in piers:
        sh.box((x0, y0, 0), (x1, y1, h), "lm:plaster_temple", PLASTER, bevel=0.02)
        sh.box((x0 - 0.04, y0 - 0.04, 0), (x1 + 0.04, y1 + 0.04, 0.45), "lm:stone_plinth", STONE, bevel=0.02)
        ctx.col((x0, y0, 0), (x1, y1, h), "concrete", ("wall",))
        # cornice band
        sh.box((x0 - 0.05, y0 - 0.05, h - 0.35), (x1 + 0.05, y1 + 0.05, h - 0.25), "stucco_detail", PLASTER)
    # lintel walls over the openings
    sh.box((-1.3, y0, 3.2), (1.3, y1, 4.2), "lm:plaster_temple", PLASTER)
    for sx in (-1, 1):
        sh.box((sx * 2.4 if sx > 0 else -3.8, y0, 2.4), (3.8 if sx > 0 else -2.4, y1, 3.2), "lm:plaster_temple", PLASTER)
    ctx.col((-1.3, y0, 3.2), (1.3, y1, 4.2), "concrete")
    ctx.col((-3.8, y0, 2.4), (-2.4, y1, 3.2), "concrete")
    ctx.col((2.4, y0, 2.4), (3.8, y1, 3.2), "concrete")
    # plaque + couplets on the front face
    K.atlas_box(dt, (-1.25, y0 - 0.08, 3.32), (1.25, y0, 3.95), "plaque_dinh", "lm:lacquer_red", WHITE)
    for x0, x1 in ((-2.3, -1.45), (1.45, 2.3)):
        cx = (x0 + x1) / 2
        K.atlas_box(dt, (cx - 0.16, y0 - 0.05, 0.75), (cx + 0.16, y0, 3.3), "couplet_l" if cx < 0 else "couplet_r",
                    "lm:lacquer_red", WHITE)
    # gate floor + thresholds + front step
    sh.box((-5.4, -1.2, 0), (5.4, y0, 0.15), "lm:bluestone", STONE, bevel=0.01)
    sh.box((-3.8, y0, 0), (3.8, y1, 0.15), "lm:bluestone", STONE)
    ctx.col((-5.4, -1.2, 0), (5.4, y0, 0.15), "concrete")
    ctx.col((-3.8, y0, 0), (3.8, y1, 0.15), "concrete")
    for x0, x1 in ((-1.3, 1.3), (-3.8, -2.4), (2.4, 3.8)):
        sh.box((x0, 0.15, 0.15), (x1, 0.3, 0.32), "lm:wood_aged", (0.6, 0.55, 0.5, 1), bevel=0.01, uvmode="grain_h")
        ctx.col((x0, 0.15, 0.15), (x1, 0.3, 0.32), "wood")
    # doors: open inward, swung against the jambs
    for (x0, x1, h) in ((-1.3, 1.3, 3.2), (-3.8, -2.4, 2.4), (2.4, 3.8, 2.4)):
        lw = (x1 - x0) / 2
        for sgn, xh in ((-1, x0), (1, x1)):
            ang = sgn * -78
            R = G.rot_z(ang, (xh, y1, 0))
            xa, xb = (xh, xh + lw) if sgn < 0 else (xh - lw, xh)
            dt.box((xa, y1, 0.17), (xb, y1 + 0.07, h - 0.05), "lm:lacquer_red", LACQ_DOOR, bevel=0.008, xform=R,
                   uvmode="grain_v")
            for r in range(4):
                for c in range(3):
                    bx = xa + (c + 0.5) * lw / 3
                    bz = 0.5 + r * (h - 0.8) / 3
                    dt.cylinder(R @ V((bx, y1 - 0.0, bz)), R.to_3x3() @ V((0, -1, 0)), 0.03, 0.025, "lm:gilt", WHITE,
                                sides=8)
    # roofs: central two tiers + side roofs
    r1 = K.HipRoof(0, 0.2, 2.75, 1.25, 4.2, 0.9, p=1.3, U=0.35, L=0.9)
    r1.build(ctx, collide=True, nt=8, du=0.3, thick=0.16)
    sh.box((-1.8, -0.35, 4.6), (1.8, 0.75, 5.15), "lm:plaster_temple", PLASTER)
    K.atlas_quad(dt, [(-1.6, -0.36, 4.68), (1.6, -0.36, 4.68), (1.6, -0.36, 5.08), (-1.6, -0.36, 5.08)], "frieze",
                 n=(0, -1, 0))
    r2 = K.HipRoof(0, 0.2, 2.15, 0.95, 5.1, 0.85, p=1.3, U=0.45, L=0.8)
    r2.build(ctx, collide=True, nt=8, du=0.3, thick=0.16)
    K.roof_ornaments(ctx, r2, ridge_h=0.3, ridge_w=0.3, curl=0.6, centre="sun")
    for sx in (-1, 1):
        rs = K.HipRoof(sx * 3.95, 0.2, 1.75, 1.05, 3.2, 0.75, p=1.3, U=0.3, L=0.7)
        rs.build(ctx, collide=True, nt=7, du=0.3, thick=0.14)
        K.roof_ornaments(ctx, rs, ridge_h=0.22, ridge_w=0.26, curl=0.4, centre="none")
    # flag pillars (trụ biểu) in front of the wall
    for sx in (-1, 1):
        x, y = sx * 7.0, -0.55
        sh.box((x - 0.42, y - 0.42, 0), (x + 0.42, y + 0.42, 0.5), "lm:stone_plinth", STONE, bevel=0.02)
        sh.box((x - 0.3, y - 0.3, 0.5), (x + 0.3, y + 0.3, 4.6), "lm:plaster_temple", PLASTER, bevel=0.02)
        for z in (1.6, 3.4, 4.3):
            sh.box((x - 0.36, y - 0.36, z), (x + 0.36, y + 0.36, z + 0.1), "stucco_detail", PLASTER, bevel=0.01)
        # lantern head (đèn lồng) + finial
        sh.box((x - 0.36, y - 0.36, 4.6), (x + 0.36, y + 0.36, 5.2), "lm:plaster_temple", PLASTER, bevel=0.03)
        for f in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            cx, cy = x + f[0] * 0.365, y + f[1] * 0.365
            dt.box((cx - 0.13 * abs(f[1]) - 0.005 * abs(f[0]), cy - 0.13 * abs(f[0]) - 0.005 * abs(f[1]), 4.7),
                   (cx + 0.13 * abs(f[1]) + 0.005 * abs(f[0]), cy + 0.13 * abs(f[0]) + 0.005 * abs(f[1]), 5.1),
                   "dark", WHITE)
        rp = K.HipRoof(x, y, 0.5, 0.5, 5.2, 0.35, p=1.2, U=0.18, L=0.3)
        rp.build(ctx, collide=False, nt=5, du=0.2, thick=0.1)
        K.lathe(dt, (x, y, 5.55), [(0.12, 0), (0.08, 0.1), (0.1, 0.18), (0.02, 0.35)], "lm:plaster_temple", PLASTER,
                sides=8)
        K.cloud_curl(dt, (x, y, 5.95), 0.35, "lm:plaster_temple", PLASTER, "xz", sx)
        K.atlas_box(dt, (x - 0.14, y - 0.32, 1.75), (x + 0.14, y - 0.3, 3.35), "couplet_l" if sx < 0 else "couplet_r",
                    "lm:plaster_temple", WHITE)
        ctx.col((x - 0.42, y - 0.42, 0), (x + 0.42, y + 0.42, 5.2), "concrete", ("wall",))
    ctx.entr += [V((0, -1.0, 0.15)), V((-3.1, -1.0, 0.15)), V((3.1, -1.0, 0.15))]
    ctx.zone("SHELTER", (-1.3, -0.6, 0.15), (1.3, 1.0, 3.2))


LACQ_DOOR = (0.9, 0.85, 0.82, 1)


def courtyard(ctx: K.LCtx):
    sh = ctx.shell
    # brick paving with a subdivided grid (vertex-colour resolution), leaving the banyan planter
    xs = [-W2 + 0.36 + i * 2.0 for i in range(13)] + [W2 - 0.36]
    xs = sorted(set([min(x, W2 - 0.36) for x in xs]))
    ys = [1.0 + j * 2.0 for j in range(10)] + [20.6]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
            P.quad_n(sh, [(x0, y0, 0.02), (x1, y0, 0.02), (x1, y1, 0.02), (x0, y1, 0.02)], "lm:brick_paving", WHITE,
                     (0, 0, 1))
    for y0, y1 in ((20.6, D - 0.36),):
        for x0, x1 in ((-W2 + 0.36, -9.0), (9.0, W2 - 0.36)):
            P.quad_n(sh, [(x0, y0, 0.02), (x1, y0, 0.02), (x1, y1, 0.02), (x0, y1, 0.02)], "lm:leaves_ground", WHITE,
                     (0, 0, 1))
        P.quad_n(sh, [(-9.0, 34.8, 0.02), (9.0, 34.8, 0.02), (9.0, y1, 0.02), (-9.0, y1, 0.02)], "lm:leaves_ground", WHITE,
                 (0, 0, 1))
    ctx.col((-W2, -1.2, -0.3), (W2, D, 0.02), "tile")
    # bluestone path slabs
    y = 1.0
    k = 0
    while y < 19.0:
        L = 0.6 + 0.3 * (k % 3 == 0)
        for x0, x1 in ((-1.2, 0.0), (0.0, 1.2)):
            sh.box((x0 + 0.01, y + 0.01, 0.0), (x1 - 0.01, y + L - 0.01, 0.05), "lm:bluestone",
                   mul(STONE, 0.9 + 0.1 * ((k * 7 + int(x0 * 3)) % 3) / 2), bevel=0.006)
        y += L
        k += 1
    # banyan planter (tree supplied by vehicles-nature; marker only)
    bx, by, br = -7.5, 9.0, 2.0
    K.lathe(sh, (bx, by, 0), [(br + 0.1, 0), (br + 0.1, 0.42), (br - 0.05, 0.45)], "lm:bluestone", STONE, sides=32,
            cap_top=False, smooth=False)
    K.lathe(sh, (bx, by, 0.3), [(br - 0.1, 0.0), (br - 0.1, 0.08), (0.01, 0.12)], "lm:leaves_ground", WHITE, sides=32)
    for k in range(10):
        a = 2 * math.pi * k / 10
        ctx.col((bx + math.cos(a) * br - 0.4, by + math.sin(a) * br - 0.4, 0), (bx + math.cos(a) * br + 0.4,
                                                                                 by + math.sin(a) * br + 0.4, 0.45), "concrete")
    ctx.col((bx - br + 0.4, by - br + 0.4, 0), (bx + br - 0.4, by + br - 0.4, 0.42), "dirt")
    ctx.mark_pt("MARKER_banyan", (bx, by, 0.42))
    ctx.nap.append(V((bx + br * 0.72, by - br * 0.72, 0.46)))


def bell_frame(ctx: K.LCtx, x, y):
    sh, dt = ctx.shell, ctx.detail
    sh.box((x - 1.1, y - 1.1, 0), (x + 1.1, y + 1.1, 0.25), "lm:stone_plinth", STONE, bevel=0.02)
    ctx.col((x - 1.1, y - 1.1, 0), (x + 1.1, y + 1.1, 0.25), "concrete")
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.column(ctx, x + sx * 0.8, y + sy * 0.8, 0.25, 2.55, 0.1, climb=False)
    for sy in (-1, 1):
        dt.box((x - 0.95, y + sy * 0.8 - 0.07, 2.62), (x + 0.95, y + sy * 0.8 + 0.07, 2.82), "lm:lacquer_red", LACQ_DOOR,
               uvmode="grain_h")
    dt.box((x - 0.07, y - 0.95, 2.62), (x + 0.07, y + 0.95, 2.82), "lm:lacquer_red", LACQ_DOOR)
    # bell
    K.lathe(dt, (x, y, 1.35), [(0.36, 0), (0.34, 0.06), (0.3, 0.3), (0.28, 0.75), (0.2, 0.88), (0.05, 0.92)],
            "lm:bronze", WHITE, sides=24)
    for z in (1.55, 1.85, 2.0):
        K.lathe(dt, (x, y, z), [(0.305 if z < 1.6 else 0.29, 0), (0.31 if z < 1.6 else 0.295, 0.03)], "lm:bronze",
                WHITE, sides=24, cap_top=False)
    dt.tube([(x, y - 0.06, 2.27), (x, y - 0.06, 2.4), (x, y + 0.06, 2.4), (x, y + 0.06, 2.27)], 0.025, "lm:bronze")
    dt.tube([(x, y, 2.4), (x, y, 2.62)], 0.03, "iron_wrought")
    # striker log on ropes
    dt.cylinder((x + 0.45, y - 0.55, 1.65), (0, 1, 0), 0.07, 1.1, "lm:wood_aged", WHITE, sides=10)
    for yy in (y - 0.4, y + 0.4):
        dt.tube([(x + 0.45, yy, 1.7), (x + 0.5, yy, 2.62)], 0.008, "fabric_canvas", (0.6, 0.5, 0.35, 1), sides=4)
    roof = K.HipRoof(x, y, 1.25, 1.25, 2.95, 0.9, p=1.25, U=0.3, L=0.5)
    roof.build(ctx, collide=True, nt=6, du=0.25, thick=0.12)
    K.roof_ornaments(ctx, roof, ridge_h=0.2, ridge_w=0.2, curl=0.35, centre="none")
    K.lathe(dt, (x, y, roof.ridge_z), [(0.12, 0), (0.06, 0.15), (0.09, 0.25), (0.01, 0.45)], "lm:gilt", WHITE, sides=8)
    ctx.mark_pt("MARKER_bell", (x, y, 0.25))
    ctx.zone("SHELTER", (x - 1.1, y - 1.1, 0.25), (x + 1.1, y + 1.1, 2.6))


def incense_burner(ctx: K.LCtx, x, y):
    sh, dt = ctx.shell, ctx.detail
    sh.box((x - 0.8, y - 0.8, 0), (x + 0.8, y + 0.8, 0.22), "lm:bluestone", STONE, bevel=0.02)
    sh.box((x - 0.6, y - 0.6, 0.22), (x + 0.6, y + 0.6, 0.62), "lm:bluestone", STONE, bevel=0.03)
    sh.box((x - 0.66, y - 0.66, 0.62), (x + 0.66, y + 0.66, 0.7), "lm:bluestone", STONE, bevel=0.02)
    ctx.col((x - 0.8, y - 0.8, 0), (x + 0.8, y + 0.8, 0.22), "concrete")
    ctx.col((x - 0.66, y - 0.66, 0.22), (x + 0.66, y + 0.66, 0.7), "concrete")
    z = 0.7
    # three legs + bowl + flared rim, two upright ears, domed lid with a lotus finial
    for k in range(3):
        a = math.pi / 2 + k * 2 * math.pi / 3
        lx, ly = x + math.cos(a) * 0.3, y + math.sin(a) * 0.3
        dt.tube([(lx * 1.0, ly, z), ((lx + x) / 2 * 0 + lx * 0.97 + x * 0.03, ly * 0.97 + y * 0.03, z + 0.18),
                 (lx * 0.9 + x * 0.1, ly * 0.9 + y * 0.1, z + 0.28)], 0.05, "lm:bronze", WHITE, sides=8,
                radii=[0.06, 0.045, 0.06])
    K.lathe(dt, (x, y, z + 0.25), [(0.22, 0), (0.38, 0.08), (0.44, 0.22), (0.42, 0.36), (0.47, 0.42), (0.47, 0.45),
                                   (0.4, 0.45), (0.38, 0.4)], "lm:bronze", WHITE, sides=28)
    K.lathe(dt, (x, y, z + 0.6), [(0.38, 0), (0.001, 0.02)], "lm:leaves_ground", (0.75, 0.7, 0.6, 1), sides=20)
    for sx in (-1, 1):
        dt.tube([(x + sx * 0.4, y, z + 0.66), (x + sx * 0.44, y, z + 0.85), (x + sx * 0.36, y, z + 0.92),
                 (x + sx * 0.32, y, z + 0.78)], 0.03, "lm:bronze", WHITE, sides=6)
    # incense sticks (red, slightly fanned) with glowing tips
    rng = ctx.rng
    for k in range(26):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.0, 0.3)
        px, py = x + math.cos(a) * r, y + math.sin(a) * r
        top = (px + math.cos(a) * 0.04, py + math.sin(a) * 0.04, z + 0.6 + rng.uniform(0.22, 0.38))
        dt.tube([(px, py, z + 0.6), top], 0.003, "plastic", (0.65, 0.12, 0.08, 1), sides=3)
        if k % 3 == 0:
            dt.box((top[0] - 0.004, top[1] - 0.004, top[2]), (top[0] + 0.004, top[1] + 0.004, top[2] + 0.012), "candle")
    # lid on a separate small stand next to it? -> lid lifted on the rim back half (classic look)
    ctx.col((x - 0.47, y - 0.47, z), (x + 0.47, y + 0.47, z + 0.7), "metal")
    ctx.mark_pt("MARKER_burner", (x, y, 0.7))
    ctx.nap.append(V((x + 0.55, y - 0.55, 0.71)))


def hall(ctx: K.LCtx):
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    y0, y1 = 20.6, 34.8
    x0, x1 = -9.0, 9.0
    # platform
    sh.box((x0, y0, 0), (x1, y1, PLAT_H), "lm:stone_plinth", STONE, skip=("+z",))
    sh.box((x0 - 0.05, y0 - 0.05, PLAT_H - 0.12), (x1 + 0.05, y1 + 0.05, PLAT_H), "lm:bluestone", STONE, bevel=0.01,
           skip=("+z",))
    for i in range(9):
        xa, xb = x0 + i * 2.0, x0 + (i + 1) * 2.0
        for j in range(7):
            ya, yb = y0 + j * 2.0, min(y1, y0 + (j + 1) * 2.0)
            P.quad_n(sh, [(xa, ya, PLAT_H), (xb, ya, PLAT_H), (xb, yb, PLAT_H), (xa, yb, PLAT_H)],
                     "lm:brick_paving" if ROW_FRONT <= (ya + yb) / 2 <= ROW_BACK and -7.2 < (xa + xb) / 2 < 7.2
                     else "lm:bluestone", WHITE, (0, 0, 1))
    ctx.col((x0, y0, 0), (x1, y1, PLAT_H), "tile")
    # front steps with cheek walls
    nst = 5
    for k in range(nst):
        z = (k + 1) * PLAT_H / nst
        ya = 19.0 + k * 0.32
        sh.box((-3.0, ya, 0), (3.0, ya + 0.34, z), "lm:bluestone", mul(STONE, 0.95 + 0.05 * (k % 2)), bevel=0.01)
        ctx.col((-3.0, ya, 0), (3.0, 20.6, z), "concrete")
    for sx in (-1, 1):
        sh.box((sx * 3.0 - 0.2 * (sx < 0) - 0.0, 19.0, 0), (sx * 3.0 + 0.2 * (sx > 0), y0, PLAT_H + 0.15), "lm:bluestone",
               STONE, bevel=0.02)
        K.cloud_curl(dt, (sx * 3.1, 19.05, PLAT_H * 0.6), 0.45, "lm:bluestone", STONE, "yz", 1, thick=0.06)
        ctx.col((sx * 3.0 - 0.2 * (sx < 0), 19.0, 0), (sx * 3.0 + 0.2 * (sx > 0), y0, PLAT_H + 0.15), "concrete")
    z0 = PLAT_H
    # columns
    for yy, r, h in ((ROW_VER, 0.17, 2.95), (ROW_FRONT, 0.21, 3.75), (ROW_IN1, 0.26, 5.4), (ROW_IN2, 0.26, 5.4),
                     (ROW_BACK, 0.21, 3.75)):
        for x in BAYS:
            if yy in (ROW_IN1, ROW_IN2) and abs(x) > 7:
                continue
            K.column(ctx, x, yy, z0, h, r, climb=(yy == ROW_VER and abs(x) > 7))
            if yy == ROW_VER and abs(x) > 7:
                ctx.climb.append(V((x, yy - 0.2, z0 + 1.5)))
    # beams on the column heads (front veranda + front wall line) and brackets
    for yy, zt in ((ROW_VER, z0 + 3.09), (ROW_FRONT, z0 + 3.89)):
        dt.box((BAYS[0] - 0.3, yy - 0.12, zt - 0.28), (BAYS[-1] + 0.3, yy + 0.12, zt), "lm:lacquer_red", LACQ_DOOR,
               uvmode="grain_h")
    for x in BAYS:
        dt.box((x - 0.09, ROW_VER - 0.1, z0 + 2.85), (x + 0.09, ROW_FRONT + 0.1, z0 + 3.05), "lm:lacquer_red", LACQ_DOOR)
        for sgn in (-1, 1):  # carved bracket arms (dragon-tail-like curls -> stylised cloud)
            K.cloud_curl(dt, (x + sgn * 0.32, ROW_VER - 0.02, z0 + 2.72), 0.32, "lm:gilt", WHITE, "xz", sgn, thick=0.03)
    # walls of the hall: sides + back (plaster over brick), front = carved door panels
    wz1 = z0 + 3.75
    for sx in (-1, 1):
        x = sx * 7.2
        sh.box((x - 0.15, ROW_FRONT, z0), (x + 0.15, ROW_BACK, wz1), "lm:plaster_temple", PLASTER)
        ctx.col((x - 0.15, ROW_FRONT, z0), (x + 0.15, ROW_BACK, wz1), "concrete", ("wall",))
        # round window (cửa sổ tròn) on the side walls
        for yy in (25.0, 31.0):
            dt.cylinder((x - sx * 0.16, yy, z0 + 2.1), (sx, 0, 0), 0.45, 0.33, "lm:lacquer_red", LACQ_DOOR, sides=20)
            dt.cylinder((x - sx * 0.17, yy, z0 + 2.1), (sx, 0, 0), 0.36, 0.34, "dark", WHITE, sides=20)
            for k in range(5):
                zz = z0 + 2.1 - 0.3 + k * 0.15
                dt.box((x - 0.18, yy - 0.36, zz - 0.012), (x + 0.18, yy + 0.36, zz + 0.012), "lm:lacquer_red", LACQ_DOOR)
        P.wall_weathering(ctx, V((x + sx * 0.151, ROW_FRONT if sx > 0 else ROW_BACK, z0)), V((0, sx, 0)),
                          ROW_BACK - ROW_FRONT, 3.75, V((sx, 0, 0)), ctx.rng, cat_level=False)
    sh.box((-7.2, ROW_BACK - 0.15, z0), (7.2, ROW_BACK + 0.15, wz1), "lm:plaster_temple", PLASTER)
    ctx.col((-7.2, ROW_BACK - 0.15, z0), (7.2, ROW_BACK + 0.15, wz1), "concrete", ("wall",))
    P.wall_weathering(ctx, V((7.2, ROW_BACK + 0.151, z0)), V((-1, 0, 0)), 14.4, 3.75, V((0, 1, 0)), ctx.rng,
                      cat_level=False)
    # front: 4 leaves per bay; central bay middle leaves open
    for i in range(len(BAYS) - 1):
        xa, xb = BAYS[i] + 0.21, BAYS[i + 1] - 0.21
        lw = (xb - xa) / 4
        for k in range(4):
            lx0, lx1 = xa + k * lw, xa + (k + 1) * lw
            open_leaf = (i == 2 and k in (1, 2))
            cell = "door_a" if (k + i) % 2 == 0 else "door_b"
            if open_leaf:
                hinge = lx0 if k == 1 else lx1
                R = G.rot_z(-80 if k == 1 else 80, (hinge, ROW_FRONT, 0))
            else:
                R = None
            mn, mx = (lx0 + 0.005, ROW_FRONT - 0.04, z0 + 0.12), (lx1 - 0.005, ROW_FRONT + 0.04, z0 + 3.0)
            dt.box(mn, mx, "lm:lacquer_red", LACQ_DOOR, skip=("-y", "+y"), xform=R)
            pts = [(mn[0], mn[1], mn[2]), (mx[0], mn[1], mn[2]), (mx[0], mn[1], mx[2]), (mn[0], mn[1], mx[2])]
            ptsb = [(mx[0], mx[1], mn[2]), (mn[0], mx[1], mn[2]), (mn[0], mx[1], mx[2]), (mx[0], mx[1], mx[2])]
            if R is not None:
                pts = [R @ V(p) for p in pts]
                ptsb = [R @ V(p) for p in ptsb]
            K.atlas_quad(dt, pts, cell, n=(R.to_3x3() @ V((0, -1, 0))) if R is not None else (0, -1, 0))
            K.atlas_quad(dt, ptsb, cell, tint=(0.6, 0.55, 0.5, 1), n=(R.to_3x3() @ V((0, 1, 0))) if R is not None else (0, 1, 0))
            if not open_leaf:
                ctx.col(mn, mx, "wood", ("wall",))
        # sill + transom frieze
        dt.box((xa, ROW_FRONT - 0.06, z0), (xb, ROW_FRONT + 0.06, z0 + 0.12), "lm:lacquer_red", LACQ_DOOR,
               uvmode="grain_h")
        dt.box((xa, ROW_FRONT - 0.06, z0 + 3.0), (xb, ROW_FRONT + 0.06, z0 + 3.08), "lm:lacquer_red", LACQ_DOOR,
               uvmode="grain_h")
        K.atlas_box(dt, (xa, ROW_FRONT - 0.05, z0 + 3.08), (xb, ROW_FRONT + 0.05, wz1 - 0.12), "frieze",
                    "lm:lacquer_red", WHITE)
        ctx.col((xa, ROW_FRONT - 0.06, z0 + 3.0), (xb, ROW_FRONT + 0.06, wz1), "wood")
    # interior: dark ceiling, altar, plaque, couplets on inner columns
    sh.box((-7.2, ROW_FRONT, wz1 + 0.02), (7.2, ROW_BACK, wz1 + 0.1), "lm:wood_aged", (0.35, 0.3, 0.28, 1),
           skip=("+z",))
    ax, ay = 0.0, 31.6
    cl.box((ax - 1.4, ay - 0.6, z0), (ax + 1.4, ay + 0.6, z0 + 0.9), "lm:lacquer_red", LACQ_DOOR, bevel=0.02)
    cl.box((ax - 1.0, ay - 0.35, z0 + 0.9), (ax + 1.0, ay + 0.6, z0 + 1.35), "lm:lacquer_red", LACQ_DOOR, bevel=0.02)
    cl.box((ax - 1.5, ay - 0.65, z0 + 0.88), (ax + 1.5, ay + 0.65, z0 + 0.94), "lm:gilt", WHITE, bevel=0.01)
    K.atlas_quad(dt, [(ax - 1.38, ay - 0.605, z0 + 0.1), (ax + 1.38, ay - 0.605, z0 + 0.1), (ax + 1.38, ay - 0.605, z0 + 0.8),
                      (ax - 1.38, ay - 0.605, z0 + 0.8)], "frieze", n=(0, -1, 0))
    # throne / tabernacle (khám) with gilt
    cl.box((ax - 0.6, ay - 0.1, z0 + 1.35), (ax + 0.6, ay + 0.55, z0 + 2.6), "lm:gilt", WHITE, bevel=0.03)
    cl.box((ax - 0.45, ay - 0.12, z0 + 1.45), (ax + 0.45, ay - 0.1, z0 + 2.4), "dark", WHITE)
    K.cloud_curl(cl, (ax, ay - 0.13, z0 + 2.75), 0.5, "lm:gilt", WHITE, "xz", 1, thick=0.05)
    for sx in (-1, 1):
        K.lathe(cl, (ax + sx * 0.85, ay - 0.15, z0 + 0.94), [(0.06, 0), (0.04, 0.05), (0.035, 0.35), (0.07, 0.4)],
                "lm:bronze", WHITE, sides=10)
        cl.box((ax + sx * 0.85 - 0.02, ay - 0.17, z0 + 1.34), (ax + sx * 0.85 + 0.02, ay - 0.13, z0 + 1.42), "candle")
        K.lathe(cl, (ax + sx * 0.45, ay - 0.2, z0 + 0.94), [(0.05, 0), (0.12, 0.04), (0.13, 0.06)], "ceramic",
                (0.9, 0.88, 0.8, 1), sides=12)
        K.mound(cl, ax + sx * 0.45, ay - 0.2, z0 + 1.0, 0.11, 0.11, 0.08, "fruit_orange")
    K.lathe(cl, (ax, ay - 0.25, z0 + 0.94), [(0.08, 0), (0.13, 0.08), (0.14, 0.12)], "lm:bronze", WHITE, sides=14)
    for k in range(7):
        a = k * 0.9
        cl.tube([(ax + math.cos(a) * 0.04, ay - 0.25 + math.sin(a) * 0.04, z0 + 1.04),
                 (ax + math.cos(a) * 0.08, ay - 0.25 + math.sin(a) * 0.08, z0 + 1.3)], 0.003, "plastic",
                (0.65, 0.12, 0.08, 1), sides=3)
    K.atlas_box(dt, (-1.4, ROW_IN2 - 0.32, z0 + 4.0), (1.4, ROW_IN2 - 0.27, z0 + 4.7), "plaque_dinh", "lm:lacquer_red")
    for x in (-1.6, 1.6):
        K.atlas_quad(dt, [(x - 0.12, ROW_IN1 - 0.27, z0 + 0.9), (x + 0.12, ROW_IN1 - 0.27, z0 + 0.9),
                          (x + 0.12, ROW_IN1 - 0.27, z0 + 3.4), (x - 0.12, ROW_IN1 - 0.27, z0 + 3.4)],
                     "couplet_l" if x < 0 else "couplet_r", n=(0, -1, 0))
    ctx.col((ax - 1.4, ay - 0.6, z0), (ax + 1.4, ay + 0.6, z0 + 1.35), "wood")
    ctx.lights.append(V((0, 28.5, z0 + 2.6)))
    ctx.mark_pt("LIGHT_ALTAR", (ax, ay - 0.6, z0 + 1.6))
    ctx.mark_pt("MARKER_altar", (ax, ay - 0.8, z0))
    # floor mats inside (chiếu)
    for k, xx in enumerate((-3.0, 3.0)):
        cl.box((xx - 1.0, 26.6, z0), (xx + 1.0, 28.6, z0 + 0.008), "rattan", (0.95, 0.85, 0.65, 1))
    ctx.nap.append(V((-3.0, 27.6, z0 + 0.01)))
    # roof
    roof = K.HipRoof(0, 27.95, 9.7, 6.45, z0 + 3.05, 5.0, p=1.3, U=0.85, L=1.7)
    ncol0 = len(ctx.cols)
    roof.build(ctx, nt=18, du=0.32, thick=0.24)
    roof_cols = ctx.cols[ncol0:]
    K.tile_eave_ends(dt, roof, step=0.22)
    K.roof_ornaments(ctx, roof, ridge_h=0.5, ridge_w=0.46, curl=1.15, centre="sun")
    # make the upper roof bands climbable (steep top of a concave roof)
    for c in roof_cols:
        if c["surface"] == "roof_tile" and c["xform"].translation.z > roof.ze + roof.H * 0.45:
            c["tags"] = ("climb",)
    # rafters under the front and back eaves
    for side, ye, yw in (("front", 21.65, ROW_FRONT), ("back", 34.25, ROW_BACK)):
        for k in range(44):
            x = -8.6 + k * 0.4
            if abs(x) > 8.8:
                continue
            ze = roof.z_at(x, ye) - 0.25
            zw = z0 + 3.75
            dt.tube([(x, ye, ze), (x, yw, zw)], 0.04, "lm:wood_aged", (0.45, 0.38, 0.33, 1), sides=4, smooth=False)
    # nest on the ridge (finale): twig bowl + trinkets
    nx, ny = 2.1, roof.cy
    nz = roof.ridge_z + 0.5 + 0.02
    nest(ctx, nx, ny, nz)
    # roof route from the east store shed
    store_shed(ctx)
    # zones
    ctx.zone("SHELTER", (-9.6, 21.6, z0), (9.6, 34.3, z0 + 3.6))
    ctx.zone("REVERB_Temple", (-7.2, ROW_FRONT, z0), (7.2, ROW_BACK, z0 + 5.0))
    ctx.mark_pt("MARKER_temple_roof", (0, roof.cy, roof.ridge_z + 0.5))
    ctx.entr.append(V((0, ROW_FRONT - 0.3, z0)))
    ctx.nap.append(V((-6.0, 22.2, z0 + 0.01)))
    return roof


def nest(ctx: K.LCtx, x, y, z):
    cl, fo = ctx.clutter, ctx.foliage
    rng = ctx.rng
    # woven twig bowl: rings of twig tubes
    for ring in range(5):
        r = 0.18 + ring * 0.045
        zz = z + ring * 0.035
        for k in range(10):
            a0 = k * 2 * math.pi / 10 + rng.uniform(0, 0.4)
            a1 = a0 + rng.uniform(0.9, 1.4)
            pts = [(x + math.cos(a0 + (a1 - a0) * t) * (r + rng.uniform(-0.02, 0.02)),
                    y + math.sin(a0 + (a1 - a0) * t) * (r + rng.uniform(-0.02, 0.02)) * 0.8,
                    zz + rng.uniform(-0.015, 0.015)) for t in (0, 0.33, 0.66, 1.0)]
            cl.tube(pts, 0.007, "lm:wood_aged", mul(WHITE, rng.uniform(0.4, 0.8)), sides=4)
    # straggly sticks poking out
    for k in range(14):
        a = rng.uniform(0, 2 * math.pi)
        p0 = V((x + math.cos(a) * 0.25, y + math.sin(a) * 0.2, z + 0.06))
        p1 = p0 + V((math.cos(a) * rng.uniform(0.12, 0.3), math.sin(a) * rng.uniform(0.1, 0.25), rng.uniform(-0.05, 0.12)))
        cl.tube([p0, p1], 0.005, "lm:wood_aged", (0.5, 0.45, 0.4, 1), sides=3)
    # twig mat cards (alpha)
    for k in range(4):
        a = k * math.pi / 4
        dx, dy = math.cos(a) * 0.36, math.sin(a) * 0.3
        K.atlas_quad(fo, [(x - dx, y - dy, z - 0.01), (x + dx, y + dy, z - 0.01), (x + dx * 0.9, y + dy * 0.9, z + 0.2),
                          (x - dx * 0.9, y - dy * 0.9, z + 0.2)], "nest", "atlas_cut")
    K.atlas_quad(fo, [(x - 0.3, y - 0.25, z + 0.04), (x + 0.3, y - 0.25, z + 0.04), (x + 0.3, y + 0.25, z + 0.04),
                      (x - 0.3, y + 0.25, z + 0.04)], "nest", "atlas_cut")
    # lining + trinkets: bottle caps, a spoon, a marble, a key, foil, a brass bell, coins
    cl.cylinder((x, y, z + 0.02), (0, 0, 1), 0.17, 0.03, "fabric_canvas", (0.55, 0.5, 0.42, 1), sides=12)
    tz = z + 0.055
    for k, (dx, dy, col) in enumerate(((-0.08, 0.05, (0.75, 0.1, 0.08, 1)), (0.06, -0.06, (0.1, 0.35, 0.7, 1)),
                                       (0.1, 0.07, (0.85, 0.75, 0.2, 1)))):
        cl.cylinder((x + dx, y + dy, tz), (0.1, 0.05, 1), 0.016, 0.006, "chrome", col, sides=12)
    cl.tube([(x - 0.12, y - 0.04, tz + 0.005), (x - 0.02, y - 0.09, tz + 0.01)], 0.005, "chrome", sides=5)
    K.lathe(cl, (x - 0.13, y - 0.035, tz), [(0.016, 0), (0.02, 0.006), (0.001, 0.01)], "chrome", WHITE, sides=8)
    cl.tube([(x + 0.01, y + 0.02, tz + 0.01), (x + 0.012, y + 0.021, tz + 0.012)], 0.012, "glass_jar", sides=8)
    cl.cylinder((x + 0.02, y + 0.12, tz), (0, 0, 1), 0.012, 0.004, "copper", sides=10)
    cl.box((x + 0.05, y + 0.1, tz), (x + 0.11, y + 0.115, tz + 0.004), "copper", (0.9, 0.75, 0.4, 1))
    K.lathe(cl, (x - 0.03, y + 0.1, tz), [(0.018, 0), (0.016, 0.02), (0.006, 0.03)], "copper", (1.0, 0.85, 0.45, 1), sides=10)
    cl.box((x + 0.02, y - 0.12, tz), (x + 0.09, y - 0.07, tz + 0.002), "chrome", (0.95, 0.95, 0.9, 1))
    ctx.col((x - 0.35, y - 0.3, z - 0.06), (x + 0.35, y + 0.3, z + 0.06), "wood")
    ctx.mark_pt("QUEST_crow_nest", (x, y, z + 0.07))
    ctx.mark_pt("MARKER_nest", (x, y, z + 0.07))


def store_shed(ctx: K.LCtx):
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    xa, xb = 9.55, W2 - 0.36
    ya, yb = 26.0, 32.0
    zl, zh = 2.62, 3.35
    for x0, x1, y0, y1 in ((xa, xa + 0.2, ya, yb), (xa, xb, ya, ya + 0.2), (xa, xb, yb - 0.2, yb)):
        sh.box((x0, y0, 0), (x1, y1, 2.55 if x0 > xa else 3.25), "brick_exposed", WHITE)
        ctx.col((x0, y0, 0), (x1, y1, 2.55 if x0 > xa else 3.25), "concrete", ("wall",))
    # door opening on the hall side: a plank door ajar
    dt.box((xa - 0.02, 28.2, 0), (xa + 0.02, 29.1, 2.0), "wood_green", WHITE, uvmode="grain_v")
    # corrugated roof sloping to the outer wall (rotated plane: we build it along +X)
    nseg = 12
    for k in range(nseg):
        y0 = ya - 0.1 + k * (yb - ya + 0.2) / nseg
        y1 = y0 + (yb - ya + 0.2) / nseg
        P.quad_n(sh, [(xa - 0.2, y0, zh), (xb + 0.12, y0, zl), (xb + 0.12, y1, zl), (xa - 0.2, y1, zh)],
                 "corrugated_rusted", WHITE, (0, 0, 1))
        P.quad_n(sh, [(xa - 0.2, y0, zh - 0.02), (xb + 0.12, y0, zl - 0.02), (xb + 0.12, y1, zl - 0.02),
                      (xa - 0.2, y1, zh - 0.02)], "corrugated_rusted", (0.5, 0.5, 0.5, 1), (0, 0, -1))
    K.col_slab(ctx, V((xa - 0.2, (ya + yb) / 2, zh)), V((xb + 0.12, (ya + yb) / 2, zl)), (yb - ya) / 2 + 0.1, 0.12, "metal")
    # bricks/stones holding the sheet down + a broom + rice sacks inside
    for k in range(4):
        yy = ya + 0.6 + k * 1.5
        t = 0.3 + 0.15 * (k % 2)
        z = zh + (zl - zh) * t + 0.01
        x = xa - 0.2 + (xb - xa + 0.3) * t
        cl.box((x - 0.12, yy - 0.06, z), (x + 0.12, yy + 0.06, z + 0.07), "brick_exposed", WHITE, bevel=0.01)
    ctx.nap.append(V((xa + 0.9, 30.6, zh + (zl - zh) * 0.3 + 0.04)))
    ctx.mark_pt("MARKER_roof_route", (xb, 29.0, 2.6))
    for k in range(3):
        cl.box((xa + 0.4 + k * 0.5, yb - 0.75, 0), (xa + 0.8 + k * 0.5, yb - 0.3, 0.55), "fabric_canvas",
               (0.85, 0.82, 0.72, 1), bevel=0.06)


def build(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    courtyard_walls(ctx)
    gate(ctx)
    courtyard(ctx)
    bell_frame(ctx, 8.0, 9.0)
    incense_burner(ctx, 0.0, 15.0)
    # large glazed pots with bonsai-like shrubs flanking the path
    for sx in (-1, 1):
        for yy in (12.0, 18.0):
            x = sx * 2.4
            K.lathe(ctx.clutter, (x, yy, 0), [(0.22, 0), (0.34, 0.15), (0.36, 0.38), (0.3, 0.55), (0.33, 0.6)],
                    "ceramic", (0.25, 0.4, 0.6, 1), sides=16)
            ctx.clutter.cylinder((x, yy, 0.56), (0, 0, 1), 0.3, 0.01, "lm:leaves_ground", sides=12)
            for k in range(3):
                P.foliage_card(ctx, x, yy, 0.5, 1.0, 1.1, "leafy", k * 60 + 15, mul(WHITE, 0.85))
            ctx.col((x - 0.33, yy - 0.33, 0), (x + 0.33, yy + 0.33, 0.6), "tile")
    hall(ctx)
    return ctx, {"height": 10.4, "floors": 1}


LACQ = LACQ_DOOR
