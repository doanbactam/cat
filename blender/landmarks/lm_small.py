"""Small landmarks: wall shrine box, tree/post shrine, Bông's café facade module, Bà Tư's tea stall.

shrine_wall_box : origin = bottom-back centre (on the wall face), front toward -Y (Godot +Z).
shrine_tree     : origin = post base centre (stand it at a tree's roots / street corner).
cafe_bong       : city-compatible shop module, 6 m wide x 10 m deep, 2 floors + roof terrace; origin at the
                  front facade bottom-centre, sidewalk level; café terrace deck in front (y -1.5..0).
quan_tra_ba_tu  : tea stall that leans on a building wall 2.8 m behind its front edge; origin = front-centre
                  on the sidewalk. Cam's cardboard bed under the counter, Grandma's chair, brazier + kettle.
"""
from __future__ import annotations

import math

import bmesh

import city_geo as G
import city_mats as CM
import city_parts as P
import landmarks_kit as K
from city_geo import V
from city_parts import WHITE, mul

RED = K.LACQUER


def _shrine_house(ctx: K.LCtx, cx, cy_back, z, w=0.56, d=0.4, h=0.5, roof=True):
    """Red lacquered shrine box with gilt trim, open front, back panel, two tiny columns, tiled roof."""
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    x0, x1 = cx - w / 2, cx + w / 2
    yb, yf = cy_back, cy_back - d
    t = 0.02
    sh.box((x0 - 0.03, yf - 0.03, z), (x1 + 0.03, yb, z + 0.04), "lm:lacquer_red", RED, bevel=0.006)
    sh.box((x0, yb - t, z + 0.04), (x1, yb, z + h), "lm:lacquer_red", RED)
    for xa, xb in ((x0, x0 + t), (x1 - t, x1)):
        sh.box((xa, yf, z + 0.04), (xb, yb, z + h), "lm:lacquer_red", RED)
    sh.box((x0 - 0.02, yf - 0.02, z + h), (x1 + 0.02, yb, z + h + 0.03), "lm:lacquer_red", RED, bevel=0.005)
    K.atlas_quad(dt, [(x0 + t, yb - t - 0.002, z + 0.05), (x1 - t, yb - t - 0.002, z + 0.05),
                      (x1 - t, yb - t - 0.002, z + h - 0.01), (x0 + t, yb - t - 0.002, z + h - 0.01)], "shrine_back",
                 n=(0, -1, 0))
    # gilt trim + front columns + carved valance
    for xx in (x0 + 0.025, x1 - 0.025):
        dt.tube([(xx, yf + 0.02, z + 0.04), (xx, yf + 0.02, z + h)], 0.012, "lm:gilt", WHITE, sides=8)
    K.atlas_quad(dt, [(x0, yf - 0.001, z + h - 0.07), (x1, yf - 0.001, z + h - 0.07), (x1, yf - 0.001, z + h),
                      (x0, yf - 0.001, z + h)], "frieze", n=(0, -1, 0))
    dt.box((x0 - 0.035, yf - 0.035, z + 0.035), (x1 + 0.035, yf - 0.025, z + 0.05), "lm:gilt", WHITE)
    # contents: two gilt figures, incense bowl, candles, water cups, fruit plate
    for sx, s in ((-1, 0.9), (1, 1.0)):
        fx = cx + sx * w * 0.2
        fy = yb - 0.1
        K.lathe(cl, (fx, fy, z + 0.04), [(0.04 * s, 0), (0.045 * s, 0.05 * s), (0.032 * s, 0.11 * s),
                                          (0.028 * s, 0.13 * s), (0.03 * s, 0.16 * s), (0.001, 0.19 * s)], "lm:gilt",
                WHITE, sides=10)
    K.lathe(cl, (cx, yf + 0.12, z + 0.04), [(0.03, 0), (0.05, 0.03), (0.055, 0.05)], "lm:bronze", WHITE, sides=10)
    for k in range(5):
        a = k * 1.25
        cl.tube([(cx + math.cos(a) * 0.012, yf + 0.12 + math.sin(a) * 0.012, z + 0.08),
                 (cx + math.cos(a) * 0.025, yf + 0.12 + math.sin(a) * 0.025, z + 0.24)], 0.0018, "plastic",
                (0.6, 0.1, 0.07, 1), sides=3)
    for sx in (-1, 1):
        xx = cx + sx * (w / 2 - 0.07)
        cl.cylinder((xx, yf + 0.1, z + 0.04), (0, 0, 1), 0.013, 0.09, "plastic", (0.75, 0.6, 0.15, 1), sides=8)
        cl.box((xx - 0.007, yf + 0.093, z + 0.13), (xx + 0.007, yf + 0.107, z + 0.155), "candle")
        K.lathe(cl, (cx + sx * 0.06, yf + 0.06, z + 0.04), [(0.012, 0), (0.016, 0.03)], "ceramic", sides=8)
    K.lathe(cl, (cx + w * 0.22, yf + 0.2, z + 0.04), [(0.02, 0), (0.06, 0.015), (0.065, 0.02)], "ceramic", sides=10)
    K.mound(cl, cx + w * 0.22, yf + 0.2, z + 0.055, 0.05, 0.05, 0.04, "fruit_orange")
    ctx.mark_pt("LIGHT_ALTAR", (cx, yf + 0.15, z + 0.25))
    if roof:
        r = K.HipRoof(cx, (yb + yf) / 2, w / 2 + 0.12, d / 2 + 0.12, z + h + 0.03, 0.2, p=1.1, U=0.08, L=0.12)
        r.build(ctx, collide=False, nt=4, du=0.08, thick=0.03)
        K.roof_ornaments(ctx, r, ridge_h=0.05, ridge_w=0.05, curl=0.12, centre="none", walkable=False)
    ctx.col((x0 - 0.03, yf - 0.03, z), (x1 + 0.03, yb, z + h + 0.25), "wood")


def build_wall_shrine(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    dt = ctx.detail
    # wall brackets
    for sx in (-1, 1):
        x = sx * 0.2
        dt.box((x - 0.012, -0.42, -0.02), (x + 0.012, 0.0, 0.01), "iron_wrought")
        dt.tube([(x, -0.38, 0.0), (x, -0.02, -0.3)], 0.01, "iron_wrought", sides=4, square=True)
        dt.box((x - 0.02, -0.01, -0.34), (x + 0.02, 0.0, -0.26), "iron_wrought")
    _shrine_house(ctx, 0.0, 0.0, 0.0, 0.56, 0.4, 0.46)
    ctx.mark_pt("MARKER_shrine", (0, -0.25, 0.04))
    return ctx, {"height": 0.8, "floors": 0}


def build_tree_shrine(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, cl = ctx.shell, ctx.clutter
    sh.box((-0.2, -0.2, 0), (0.2, 0.2, 0.12), "lm:bluestone", WHITE, bevel=0.01)
    sh.box((-0.07, -0.07, 0.12), (0.07, 0.07, 1.15), "concrete_weathered", WHITE, bevel=0.01)
    sh.box((-0.32, -0.27, 1.12), (0.32, 0.27, 1.17), "concrete_weathered", WHITE, bevel=0.01)
    ctx.col((-0.07, -0.07, 0), (0.07, 0.07, 1.15), "concrete", ("climb",))
    _shrine_house(ctx, 0.0, 0.22, 1.17, 0.5, 0.42, 0.44)
    # red cloth band tied round the post, offerings at the foot
    cl.box((-0.075, -0.075, 0.75), (0.075, 0.075, 0.85), "fabric_canvas", (0.7, 0.1, 0.08, 1))
    K.lathe(cl, (0.25, -0.1, 0), [(0.06, 0), (0.08, 0.06), (0.07, 0.09)], "lm:bronze", WHITE, sides=10)
    for k in range(4):
        cl.tube([(0.25 + 0.01 * k, -0.1, 0.06), (0.25 + 0.02 * k, -0.1, 0.25)], 0.002, "plastic", (0.6, 0.1, 0.07, 1),
                sides=3)
    ctx.col((-0.2, -0.2, 0), (0.2, 0.2, 0.12), "concrete")
    ctx.climb.append(V((0, -0.1, 0.6)))
    ctx.mark_pt("MARKER_shrine", (0, -0.3, 0))
    return ctx, {"height": 1.9, "floors": 0}


# ---------------------------------------------------------------------------
CAFE_W2 = 3.0
CAFE_D = 10.0
F1 = 3.6
F2 = 3.3
BLACK = (0.08, 0.08, 0.08, 1)


def _steel_window(ctx: K.LCtx, x0, z0, x1, z1, y=0.0, cell="lace", bars=(), hbars=(), lit=False):
    dt = ctx.detail
    P.frame_rect(dt, x0, z0, x1, z1, y - 0.04, y + 0.02, 0.04, "metal_painted", BLACK,
                 mid_v=bars, mid_h=hbars)
    r = CM.atlas_cell("glass_interiors", cell)
    P.front_rect(dt, x0 + 0.02, z0 + 0.02, x1 - 0.02, z1 - 0.02, y - 0.005, "glass_lit" if lit else "glass", WHITE,
                 P.atlas_uv(r, 0.002))


def build_cafe(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt, cl = ctx.shell, ctx.detail, ctx.clutter
    rng = ctx.rng
    W2 = CAFE_W2
    H = F1 + F2 + 0.2
    wall = "plaster_white"
    # --- ground floor: steel-framed glass shopfront, open folding doors in the middle bay
    holes = [(-2.6, 0.15, -0.95, 3.05), (-0.85, 0.15, 0.85, 2.65), (0.95, 0.15, 2.6, 3.05)]
    P.wall_with_holes(sh, -W2, W2, 0.0, F1, holes, wall, WHITE, depth=0.25)
    for (hx0, hz0, hx1, hz1), mode in zip(holes, ("fixed", "open", "fixed")):
        if mode == "fixed":
            _steel_window(ctx, hx0, hz0 + 0.45, hx1, hz1 - 0.55, 0.18, "room_shelf",
                          bars=((hx0 + hx1) / 2,), lit=True)
            P.frame_rect(dt, hx0, hz1 - 0.55, hx1, hz1, 0.14, 0.2, 0.035, "metal_painted", BLACK, mid_v=((hx0 + hx1) / 2,))
            P.front_rect(dt, hx0 + 0.02, hz1 - 0.53, hx1 - 0.02, hz1 - 0.02, 0.175, "glass", WHITE,
                         P.atlas_uv(CM.atlas_cell("glass_interiors", "blinds"), 0.002))
            # window bench inside + low wall below glass
            sh.box((hx0, -0.02, 0.0), (hx1, 0.25, hz0 + 0.45), "tile_mosaic_green", WHITE)
            ctx.col((hx0, -0.02, 0.0), (hx1, 0.25, hz0 + 0.45), "tile", ("wall",))
            ctx.col((hx0, 0.13, hz0 + 0.45), (hx1, 0.2, hz1), "concrete", ("wall",))
        else:
            # folded glass leaves stacked at both jambs
            for sx, xh in ((-1, hx0), (1, hx1)):
                for k in range(2):
                    xx = xh - sx * (0.06 + k * 0.07)
                    dt.box((xx - 0.025, 0.02 + k * 0.01, hz0), (xx + 0.025, 0.55, hz1 - 0.05), "metal_painted", BLACK)
                    P.quad_n(dt, [(xx, 0.06, hz0 + 0.05), (xx, 0.52, hz0 + 0.05), (xx, 0.52, hz1 - 0.1),
                                  (xx, 0.06, hz1 - 0.1)], "glass_jar", WHITE, (sx, 0, 0))
            dt.box((hx0, 0.12, hz1 - 0.06), (hx1, 0.2, hz1), "metal_painted", BLACK)
            ctx.entr.append(V(((hx0 + hx1) / 2, -0.2, 0.15)))
    # --- interior (4.5 m deep): floor, counter, shelves, pendant lights, Bông's cushion seat
    yi0, yi1 = 0.25, 4.6
    sh.box((-W2 + 0.2, yi0, 0.0), (W2 - 0.2, yi1, 0.15), "wood_brown", (1.1, 1.0, 0.95, 1), uvmode="grain_h")
    ctx.col((-W2, yi0, -0.2), (W2, yi1, 0.15), "wood")
    sh.box((-W2 + 0.2, yi1, 0.0), (W2 - 0.2, yi1 + 0.2, F1), "plaster_white", (0.95, 0.9, 0.82, 1))
    sh.box((-W2 + 0.2, yi0, F1 - 0.15), (W2 - 0.2, yi1, F1 - 0.12), "wood_brown", (0.8, 0.75, 0.7, 1))
    for sx in (-1, 1):
        x_in = sx * (W2 - 0.2)
        P.quad_n(sh, [(x_in, yi0, 0.15), (x_in, yi1, 0.15), (x_in, yi1, F1 - 0.15), (x_in, yi0, F1 - 0.15)],
                 "brick_exposed", (1.05, 1.0, 0.95, 1), (-sx, 0, 0))
    # back shelves with cups/jars + atlas backdrop
    K.atlas_quad(dt, [(-1.8, yi1 - 0.002, 1.0), (1.8, yi1 - 0.002, 1.0), (1.8, yi1 - 0.002, 3.0), (-1.8, yi1 - 0.002, 3.0)],
                 "cafe_interior", n=(0, -1, 0))
    for z in (1.5, 2.1):
        dt.box((-1.7, yi1 - 0.3, z), (1.7, yi1, z + 0.04), "wood_brown", WHITE, uvmode="grain_h")
        for k in range(10):
            x = -1.55 + k * 0.33
            K.lathe(cl, (x, yi1 - 0.15, z + 0.04), [(0.04, 0), (0.05, 0.1), (0.035, 0.12)],
                    rng.choice(["ceramic", "glass_jar"]), rng.choice([WHITE, (0.3, 0.3, 0.32, 1), (0.6, 0.45, 0.3, 1)]),
                    sides=10)
    # counter (L-shaped) with espresso machine, pastry case, grinder
    cl.box((-0.6, 3.0, 0.15), (2.6, 3.65, 1.1), "wood_brown", (0.75, 0.65, 0.55, 1), bevel=0.01, uvmode="grain_v")
    cl.box((-0.65, 2.95, 1.1), (2.65, 3.7, 1.15), "terrazzo", (1.15, 1.15, 1.12, 1), bevel=0.008)
    ctx.col((-0.65, 2.95, 0.15), (2.65, 3.7, 1.15), "wood")
    cl.box((1.4, 3.2, 1.15), (2.2, 3.6, 1.6), "chrome", (0.85, 0.85, 0.85, 1), bevel=0.02)
    cl.box((1.45, 3.15, 1.25), (2.15, 3.2, 1.3), "dark")
    for k in range(2):
        cl.cylinder((1.6 + k * 0.4, 3.15, 1.32), (0, 0, -1), 0.03, 0.08, "chrome", sides=8)
    cl.box((-0.5, 3.05, 1.15), (0.6, 3.6, 1.5), "glass_jar", WHITE)
    for k in range(4):
        K.mound(cl, -0.35 + k * 0.27, 3.3, 1.17, 0.1, 0.1, 0.05, "snack_biscuit")
    K.lathe(cl, (0.95, 3.4, 1.15), [(0.08, 0), (0.08, 0.15), (0.05, 0.2), (0.07, 0.35)], "metal_painted", BLACK, sides=10)
    # pendant lamps (lit bulbs inside black cones)
    for x in (-1.6, 0.0, 1.6):
        dt.tube([(x, 2.0, F1 - 0.15), (x, 2.0, 2.45)], 0.004, "dark", sides=4)
        K.lathe(dt, (x, 2.0, 2.2), [(0.18, 0), (0.17, 0.02), (0.06, 0.2), (0.02, 0.26)], "metal_painted", BLACK,
                sides=14, cap_top=True)
        K.lathe(dt, (x, 2.0, 2.18), [(0.001, 0), (0.05, 0.03), (0.04, 0.08)], "bulb", WHITE, sides=10)
    ctx.lights += [V((-1.2, 2.0, 2.4)), V((1.2, 2.0, 2.4))]
    # tables + rattan chairs inside and the window bench (Bông's cushion)
    for (tx, ty) in ((-1.6, 1.6), (0.2, 1.4)):
        K.lathe(cl, (tx, ty, 0.15), [(0.22, 0), (0.22, 0.03), (0.04, 0.05), (0.04, 0.7), (0.3, 0.72), (0.3, 0.75)],
                "terrazzo", (1.1, 1.1, 1.1, 1), sides=16)
        ctx.col((tx - 0.3, ty - 0.3, 0.15), (tx + 0.3, ty + 0.3, 0.9), "tile")
        K.tea_glass(cl, tx + 0.1, ty, 0.9, tea=True, h=0.09, r=0.035)
        for a in (0.0, math.pi):
            cx, cy = tx + math.cos(a) * 0.55, ty + math.sin(a) * 0.15
            P.basket(cl, cx, cy, 0.15, 0.24, 0.45, (0.9, 0.85, 0.75, 1), "jar")
            cl.cylinder((cx, cy, 0.6), (0, 0, 1), 0.22, 0.05, "fabric_canvas", (0.65, 0.35, 0.22, 1), sides=12)
            ctx.col((cx - 0.22, cy - 0.22, 0.15), (cx + 0.22, cy + 0.22, 0.65), "fabric")
    bx0, bx1 = -2.6, -0.95
    cl.box((bx0, 0.25, 0.15), (bx1, 0.75, 0.6), "wood_brown", WHITE, uvmode="grain_h")
    cl.box((bx0 + 0.05, 0.28, 0.6), (bx1 - 0.05, 0.72, 0.7), "fabric_canvas", (0.85, 0.82, 0.75, 1), bevel=0.04)
    cl.box((-2.1, 0.32, 0.7), (-1.5, 0.7, 0.78), "fabric_canvas", (0.75, 0.45, 0.5, 1), bevel=0.035)
    ctx.col((bx0, 0.25, 0.15), (bx1, 0.75, 0.7), "fabric")
    ctx.nap.append(V((-1.8, 0.5, 0.79)))
    ctx.mark_pt("MARKER_bong_spot", (-1.8, 0.5, 0.79))
    # --- terrace deck in front with planters and tables
    sh.box((-W2, -1.5, 0.0), (W2, 0.0, 0.15), "wood_brown", (1.2, 1.05, 0.9, 1), uvmode="grain_h")
    for k in range(int(2 * W2 / 0.14)):
        x = -W2 + k * 0.14
        dt.box((x, -1.502, 0.02), (x + 0.004, 0.0, 0.151), "dark")
    ctx.col((-W2, -1.5, 0.0), (W2, 0.0, 0.15), "wood")
    for sx in (-1, 1):
        px = sx * (W2 - 0.35)
        cl.box((px - 0.3, -1.45, 0.15), (px + 0.3, -0.95, 0.6), "render_modern", (0.9, 0.9, 0.88, 1), bevel=0.02)
        cl.box((px - 0.27, -1.42, 0.58), (px + 0.27, -0.98, 0.59), "lm:leaves_ground", WHITE)
        for k in range(4):
            P.foliage_card(ctx, px, -1.2, 0.5, 0.9, 1.3, rng.choice(["leafy", "fern"]), k * 45 + rng.uniform(0, 20),
                           mul(WHITE, rng.uniform(0.8, 1.0)))
        ctx.col((px - 0.3, -1.45, 0.15), (px + 0.3, -0.95, 0.6), "concrete")
        ctx.nap.append(V((px, -1.2, 0.6)))
    for tx in (-1.2, 1.2):
        K.lathe(cl, (tx, -0.75, 0.15), [(0.18, 0), (0.18, 0.02), (0.03, 0.04), (0.03, 0.72), (0.27, 0.73), (0.27, 0.75)],
                "metal_painted", BLACK, sides=14)
        cl.cylinder((tx, -0.75, 0.88), (0, 0, 1), 0.27, 0.02, "terrazzo", (1.15, 1.15, 1.12, 1), sides=16)
        ctx.col((tx - 0.27, -1.02, 0.15), (tx + 0.27, -0.48, 0.9), "metal")
        for a in (-0.6, 0.6):
            cx = tx + a
            # bistro chair: rattan seat on black frame
            for sx in (-1, 1):
                for sy in (-1, 1):
                    cl.tube([(cx + sx * 0.17, -0.75 + sy * 0.17, 0.15), (cx + sx * 0.19, -0.75 + sy * 0.19, 0.6)], 0.01,
                            "metal_painted", BLACK, sides=5)
            cl.box((cx - 0.21, -0.96, 0.58), (cx + 0.21, -0.54, 0.63), "rattan", WHITE, bevel=0.01)
            cl.tube([(cx - 0.18, -0.75 + 0.2 * (1 if a > 0 else -1) * 0 + 0.2, 0.62),
                     (cx - 0.18, -0.55, 1.02), (cx + 0.18, -0.55, 1.02), (cx + 0.18, -0.55, 0.62)], 0.012, "metal_painted",
                    BLACK, sides=5)
            ctx.col((cx - 0.21, -0.96, 0.15), (cx + 0.21, -0.54, 0.63), "wood")
    # menu stand (chalkboard)
    K.atlas_box(cl, (2.15, -1.48, 0.25), (2.6, -1.44, 1.0), "menu_cafe", "wood_brown", WHITE)
    for sx in (2.17, 2.58):
        cl.tube([(sx, -1.46, 0.15), (sx, -1.46, 1.05)], 0.015, "wood_brown", WHITE, sides=5)
    # --- awning + lit sign
    P.awning_canvas(ctx, -W2 + 0.15, W2 - 0.15, F1 - 0.15, 1.3, (0.16, 0.28, 0.22, 1), slope_deg=20, valance=0.2)
    # lit sign board in the transom above the open doors (under the awning, readable from the street)
    K.atlas_box(dt, (-0.84, -0.1, 2.68), (0.84, 0.02, 3.3), "sign_cafe", "metal_painted", BLACK)
    K.atlas_quad(dt, [(-0.82, -0.102, 2.7), (0.82, -0.102, 2.7), (0.82, -0.102, 3.28), (-0.82, -0.102, 3.28)],
                 "sign_cafe", "atlas_lit", n=(0, -1, 0))
    for x in (-2.8, 2.8):   # brass-and-glass wall lanterns on the outer piers
        dt.box((x - 0.06, -0.03, 2.3), (x + 0.06, 0.0, 2.5), "copper", (0.8, 0.7, 0.5, 1))
        dt.tube([(x, -0.02, 2.4), (x, -0.2, 2.45)], 0.01, "copper", (0.8, 0.7, 0.5, 1), sides=5)
        K.lathe(dt, (x, -0.22, 2.3), [(0.05, 0), (0.06, 0.04), (0.06, 0.16), (0.03, 0.2)], "glass_jar", WHITE, sides=8)
        K.lathe(dt, (x, -0.22, 2.33), [(0.001, 0), (0.025, 0.03), (0.02, 0.07)], "bulb", WHITE, sides=8)
        ctx.mark_pt("LIGHT_NIGHT", (x, -0.4, 2.4))
    # --- upper floor: balcony with planters, full-height steel glazing
    P.balcony_slab(ctx, -W2, W2, F1 + 0.12, 0.9, mat="render_modern", floor_mat="terrazzo")
    P.railing_steel(ctx, -W2 + 0.05, W2 - 0.05, -0.85, F1 + 0.12, 1.0, BLACK)
    holes2 = [(-2.5, F1 + 0.25, -0.9, F1 + 2.85), (-0.7, F1 + 0.25, 0.7, F1 + 2.85), (0.9, F1 + 0.25, 2.5, F1 + 2.85)]
    P.wall_with_holes(sh, -W2, W2, F1, F1 + F2, holes2, wall, WHITE, depth=0.25)
    for (hx0, hz0, hx1, hz1), cell in zip(holes2, ("lace", "green_curtain", "floral")):
        _steel_window(ctx, hx0, hz0, hx1, hz1, 0.12, cell, bars=((hx0 + hx1) / 2,), hbars=(hz1 - 0.5,))
    for k in range(4):
        px = -2.4 + k * 1.6
        cl.box((px - 0.35, -0.8, F1 + 0.135), (px + 0.35, -0.5, F1 + 0.42), "wood_brown", WHITE, uvmode="grain_h")
        for j in range(3):
            P.foliage_card(ctx, px, -0.65, F1 + 0.3, 0.9, 0.9, rng.choice(["leafy", "fern", "bougainvillea"]),
                           j * 60 + rng.uniform(0, 30))
        ctx.col((px - 0.35, -0.8, F1 + 0.12), (px + 0.35, -0.5, F1 + 0.42), "wood")
    P.bougainvillea_cascade(ctx, -W2 + 0.2, -0.5, F1 + 1.05, -0.9, drop=1.4)
    for x in (-1.6, 1.6):  # hanging pothos pots under the balcony
        dt.tube([(x, -0.7, F1 - 0.05), (x, -0.7, F1 - 0.5)], 0.003, "dark", sides=3)
        K.lathe(cl, (x, -0.7, F1 - 0.75), [(0.08, 0), (0.12, 0.15), (0.13, 0.2)], "ceramic", WHITE, sides=12)
        P.foliage_card(ctx, x, -0.7, F1 - 1.4, 0.45, 0.9, "vine", 0)
        P.foliage_card(ctx, x, -0.7, F1 - 1.4, 0.45, 0.9, "vine", 90)
    # cornice + parapet + roof terrace with pergola
    zt = F1 + F2
    P.cornice(ctx, -W2, W2, zt, mat="stucco_detail")
    sh.box((-W2, -0.05, zt), (W2, 0.2, zt + 1.0), wall, WHITE)
    sh.box((-W2, -0.08, zt + 1.0), (W2, 0.23, zt + 1.08), "concrete_weathered", WHITE, bevel=0.01)
    ctx.col((-W2, -0.05, zt), (W2, 0.2, zt + 1.08), "concrete", ("wall",))
    for sx in (-1, 1):
        sh.box((sx * W2 - 0.2 * (sx > 0), 0.0, 0.0), (sx * W2 + 0.2 * (sx < 0), CAFE_D, zt + 1.08), "cement_render",
               WHITE)
        ctx.col((sx * W2 - 0.2 * (sx > 0), 0.0, 0.0), (sx * W2 + 0.2 * (sx < 0), CAFE_D, zt + 1.08), "concrete", ("wall",))
    sh.box((-W2, CAFE_D - 0.2, 0), (W2, CAFE_D, zt + 1.08), "cement_render", WHITE)
    ctx.col((-W2, CAFE_D - 0.2, 0), (W2, CAFE_D, zt + 1.08), "concrete", ("wall",))
    sh.box((-W2 + 0.2, 0.2, zt - 0.2), (W2 - 0.2, CAFE_D - 0.2, zt), "concrete_weathered", WHITE, skip=("+z",))
    P.quad_n(sh, [(-W2 + 0.2, 0.2, zt), (W2 - 0.2, 0.2, zt), (W2 - 0.2, CAFE_D - 0.2, zt), (-W2 + 0.2, CAFE_D - 0.2, zt)],
             "tile_strip_brown", WHITE, (0, 0, 1))
    ctx.col((-W2, 0.2, zt - 0.2), (W2, CAFE_D - 0.2, zt), "tile")
    for x in (-2.4, 2.4):
        for y in (1.0, 4.0):
            cl.box((x - 0.05, y - 0.05, zt), (x + 0.05, y + 0.05, zt + 2.4), "wood_brown", WHITE)
    for y in (1.0, 4.0):
        cl.box((-2.5, y - 0.06, zt + 2.4), (2.5, y + 0.06, zt + 2.55), "wood_brown", WHITE, uvmode="grain_h")
    for k in range(9):
        x = -2.4 + k * 0.6
        cl.box((x - 0.03, 0.8, zt + 2.55), (x + 0.03, 4.2, zt + 2.63), "wood_brown", WHITE)
        ctx.col((x - 0.03, 0.8, zt + 2.55), (x + 0.03, 4.2, zt + 2.63), "wood")
    for k in range(7):
        P.foliage_card(ctx, -2.4 + k * 0.8, 2.5, zt + 2.0, 1.2, 0.7, "vine", rng.uniform(0, 180))
    # string lights across the pergola
    pts = G.catenary((-2.4, 1.0, zt + 2.35), (2.4, 4.0, zt + 2.35), 0.25, 14)
    dt.tube(pts, 0.004, "dark", sides=3)
    for p in pts[1:-1]:
        K.lathe(dt, (p.x, p.y, p.z - 0.06), [(0.001, 0), (0.022, 0.02), (0.012, 0.05)], "bulb", WHITE, sides=6)
    # lounger with cushion (nap), potted plants, a small water tank + AC unit at the back
    cl.box((-1.8, 5.5, zt), (-1.1, 7.3, zt + 0.3), "wood_brown", WHITE, uvmode="grain_v")
    cl.box((-1.78, 5.55, zt + 0.3), (-1.12, 7.25, zt + 0.38), "fabric_canvas", (0.9, 0.85, 0.7, 1), bevel=0.03)
    ctx.col((-1.8, 5.5, zt), (-1.1, 7.3, zt + 0.38), "fabric")
    ctx.nap.append(V((-1.45, 6.4, zt + 0.39)))
    for (px, py) in ((2.4, 5.5), (2.4, 7.0), (0.5, 8.9)):
        P.potted_plant(ctx, px, py, zt, 0.8, "leafy", "white")
    P.water_tank(ctx, 1.5, 8.6, zt, "vertical", nap=False)
    P.drainpipe(ctx, W2 - 0.12, 0.15, F1 + F2 + 0.9, 0.0, "metal_painted", BLACK, r=0.045)   # climb route
    P.decal(ctx, "streak_0", 2.2, zt + 0.9, 0.8, 1.6)
    P.decal(ctx, "water_stain", -2.6, F1 - 0.3, 0.6, 0.5)
    ctx.mark_pt("MARKER_cafe", (0, -1.0, 0.15))
    ctx.zone("SHELTER", (-W2, -1.3, 0.0), (W2, 0.0, F1 - 0.2))
    ctx.zone("SHELTER", (-W2, 0.0, 0.0), (W2, yi1, F1 - 0.2))
    ctx.zone("REVERB_Interior", (-W2, 0.2, 0.0), (W2, yi1, F1))
    return ctx, {"height": zt + 2.7, "floors": 2}


# ---------------------------------------------------------------------------
def build_tea_stall(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt, cl, fo = ctx.shell, ctx.detail, ctx.clutter, ctx.foliage
    rng = ctx.rng
    WB = 2.8      # wall line behind
    # --- tarp roof: batten on the wall, two leaning bamboo poles in front, guy ropes
    dt.box((-2.1, WB - 0.08, 2.35), (2.1, WB, 2.43), "lm:wood_aged", WHITE, uvmode="grain_h")
    for px in (-1.95, 1.95):
        cl.tube([(px, 0.25, 0.0), (px * 1.0, 0.27, 1.05), (px, 0.3, 2.05)], 0.032, "wood_brown", (1.7, 1.5, 0.95, 1),
                sides=8, radii=[0.035, 0.033, 0.03])
        for z in (0.5, 1.2, 1.8):  # bamboo nodes
            cl.cylinder((px, 0.27, z), (0, 0, 1), 0.037, 0.02, "wood_brown", (1.4, 1.2, 0.75, 1), sides=8)
        cl.tube([(px, 0.3, 2.0), (px * 1.15, -0.5, 0.0)], 0.004, "fabric_canvas", (0.7, 0.6, 0.4, 1), sides=3)
        ctx.col((px - 0.035, 0.22, 0.0), (px + 0.035, 0.32, 2.05), "wood", ("climb",))
        ctx.climb.append(V((px, 0.15, 0.9)))
    K.sag_cloth(cl, (-2.15, 0.15, 2.05), (2.15, 0.15, 2.05), (-2.15, WB - 0.04, 2.42), (2.15, WB - 0.04, 2.42),
                "lm:tarp_blue", WHITE, nu=12, nv=8, sag=0.14, seed=7)
    # an older striped tarp layered over one side + a hanging flap at the front
    K.sag_cloth(cl, (0.3, 0.6, 2.13), (2.2, 0.6, 2.12), (0.3, WB - 0.04, 2.47), (2.2, WB - 0.04, 2.47), "lm:tarp_stripe",
                WHITE, nu=8, nv=6, sag=0.1, seed=8)
    K.sag_cloth(cl, (-2.15, 0.14, 2.04), (2.15, 0.14, 2.04), (-2.15, 0.12, 1.82), (2.15, 0.12, 1.82), "lm:tarp_blue",
                (0.9, 0.9, 0.9, 1), nu=12, nv=2, sag=0.0, seed=9)
    K.col_slab(ctx, V((0, 0.15, 2.05)), V((0, WB - 0.04, 2.42)), 2.15, 0.06, "fabric")
    ctx.zone("SHELTER", (-2.1, 0.15, 0.0), (2.1, WB, 2.0))
    ctx.nap.append(V((0.9, 1.4, 2.27)))       # sunny tarp hammock spot (sags under a cat)
    # sign board tied to the front flap
    K.atlas_box(dt, (-1.0, 0.06, 1.62), (1.0, 0.1, 2.0), "sign_tea", "lm:wood_aged", WHITE)
    for x in (-0.9, 0.9):
        dt.tube([(x, 0.08, 2.0), (x, 0.12, 2.08)], 0.004, "fabric_canvas", (0.6, 0.5, 0.35, 1), sides=3)
    # --- counter: old wooden cabinet with a glass display box on top
    cx0, cx1, cy0, cy1 = -1.5, 0.3, 1.75, 2.35
    ch = 0.78
    # open-fronted cabinet: back + side panels, a mid shelf and a front panel only above it, so the
    # space under the counter (Cam's bed) stays open toward the street
    for (a, b) in (((cx0, cy1 - 0.02, 0.1), (cx1, cy1, ch - 0.03)), ((cx0, cy0, 0.1), (cx0 + 0.02, cy1, ch - 0.03)),
                   ((cx1 - 0.02, cy0, 0.1), (cx1, cy1, ch - 0.03)), ((cx0, cy0, 0.4), (cx1, cy1, 0.42)),
                   ((cx0, cy0, 0.42), (cx1, cy0 + 0.02, ch - 0.03)), ((cx0, cy0, 0.1), (cx1, cy1, 0.115))):
        sh.box(a, b, "wood_teal", WHITE, uvmode="grain_v")
    for xx in (cx0 + 0.45, cx0 + 0.9, cx0 + 1.35):   # door stiles on the upper front
        dt.box((xx - 0.012, cy0 - 0.012, 0.44), (xx + 0.012, cy0, ch - 0.05), "wood_teal", (0.8, 0.85, 0.82, 1))
    sh.box((cx0 - 0.03, cy0 - 0.03, ch - 0.03), (cx1 + 0.03, cy1 + 0.03, ch), "lm:wood_aged", WHITE, bevel=0.006,
           uvmode="grain_h")
    for (lx, ly) in ((cx0 + 0.04, cy0 + 0.04), (cx1 - 0.04, cy0 + 0.04), (cx0 + 0.04, cy1 - 0.04), (cx1 - 0.04, cy1 - 0.04)):
        sh.box((lx - 0.035, ly - 0.035, 0.0), (lx + 0.035, ly + 0.035, 0.1), "lm:wood_aged", WHITE)
    # open space under the counter (front panel only covers the top half) -> Cam's bed is visible
    ctx.col((cx0, cy0, 0.42), (cx1, cy1, ch), "wood")
    # glass display box with snacks
    gx0, gx1 = -1.35, -0.5
    dt.box((gx0, cy0 + 0.05, ch), (gx1, cy1 - 0.08, ch + 0.02), "lm:wood_aged", WHITE)
    for k, cell in enumerate(("snack_candy", "snack_ginger", "snack_biscuit")):
        K.mound(cl, gx0 + 0.15 + k * 0.27, (cy0 + cy1) / 2 - 0.02, ch + 0.02, 0.11, 0.17, 0.05, cell)
    dt.box((gx0, cy0 + 0.05, ch + 0.02), (gx1, cy1 - 0.08, ch + 0.3), "glass_jar", WHITE)
    dt.box((gx0 - 0.01, cy0 + 0.04, ch + 0.3), (gx1 + 0.01, cy1 - 0.07, ch + 0.32), "lm:wood_aged", WHITE)
    # jars on the counter (front row), tray of upside-down tea glasses, teapot in a padded basket
    for k, cell in enumerate(("snack_peanut", "snack_seeds", "snack_plum", "snack_rice")):
        K.jar(ctx, -0.35 + k * 0.0 + (k % 2) * 0.16, cy0 + 0.12 + (k // 2) * 0.2, ch, cell, r=0.06, h=0.2)
    cl.box((cx1 - 0.0 - 0.45, cy1 - 0.3, ch), (cx1 - 0.05, cy1 - 0.02, ch + 0.012), "metal_painted", (0.7, 0.2, 0.15, 1))
    for i in range(3):
        for j in range(2):
            K.tea_glass(cl, cx1 - 0.4 + i * 0.12, cy1 - 0.22 + j * 0.11, ch + 0.012, tea=False, h=0.07, r=0.026)
    tb_x, tb_y = 0.05, 2.15
    K.lathe(cl, (tb_x, tb_y, ch), [(0.12, 0), (0.14, 0.04), (0.14, 0.18), (0.12, 0.2)], "rattan", WHITE, sides=14,
            cap_top=False)
    K.lathe(cl, (tb_x, tb_y, ch + 0.17), [(0.12, 0), (0.08, 0.05), (0.001, 0.07)], "fabric_canvas", (0.7, 0.25, 0.25, 1),
            sides=12)
    K.teapot(cl, tb_x, tb_y, ch + 0.2, 1.0, (0.88, 0.88, 0.84, 1))
    # thermos flasks + radio + plate of peanut candy + a rattan fan
    K.thermos(cl, -1.45, 2.22, ch, (0.65, 0.12, 0.1, 1))
    K.thermos(cl, -1.3, 2.25, ch, (0.2, 0.45, 0.35, 1))
    cl.box((-0.2, 2.18, ch), (0.05, 2.3, ch + 0.15), "plastic", (0.55, 0.12, 0.1, 1), bevel=0.012)  # radio
    cl.cylinder((-0.14, 2.179, ch + 0.075), (0, -1, 0), 0.04, 0.003, "dark", sides=12)
    cl.tube([(0.03, 2.25, ch + 0.15), (0.06, 2.3, ch + 0.4)], 0.003, "chrome", sides=3)
    K.lathe(cl, (-0.8, 1.9, ch), [(0.06, 0), (0.12, 0.012), (0.13, 0.02)], "ceramic", (0.85, 0.9, 0.95, 1), sides=12)
    K.mound(cl, -0.8, 1.9, ch + 0.015, 0.1, 0.1, 0.025, "snack_peanut")
    cl.cylinder((-0.65, 2.25, ch + 0.003), (0.1, 0.2, 1), 0.12, 0.004, "rattan", WHITE, sides=14)
    # --- under the counter: Cam's cardboard bed with a folded cushion + Cam's bowl
    bx0, bx1, by0, by1 = -1.3, -0.65, cy0 + 0.05, cy1 - 0.02
    for (a, b) in (((bx0, by0, 0.1), (bx1, by0 + 0.01, 0.26)), ((bx0, by1 - 0.01, 0.1), (bx1, by1, 0.3)),
                   ((bx0, by0, 0.1), (bx0 + 0.01, by1, 0.28)), ((bx1 - 0.01, by0, 0.1), (bx1, by1, 0.28)),
                   ((bx0, by0, 0.1), (bx1, by1, 0.11))):
        cl.box(a, b, "fabric_canvas", (0.62, 0.45, 0.28, 1))
    cl.box((bx0 + 0.03, by0 + 0.03, 0.11), (bx1 - 0.03, by1 - 0.03, 0.17), "fabric_canvas", (0.75, 0.32, 0.22, 1),
               bevel=0.025)
    # floor slab of the stall (old concrete pad) so the bed sits off the pavement
    sh.box((-2.0, 0.3, 0.0), (2.0, WB, 0.1), "concrete_weathered", WHITE, bevel=0.01)
    ctx.col((-2.0, 0.3, -0.1), (2.0, WB, 0.1), "concrete")
    ctx.nap.append(V(((bx0 + bx1) / 2, (by0 + by1) / 2, 0.18)))
    ctx.mark_pt("MARKER_cam_bed", ((bx0 + bx1) / 2, (by0 + by1) / 2, 0.18))
    K.lathe(cl, (-0.35, 1.45, 0.1), [(0.06, 0), (0.08, 0.035), (0.085, 0.04)], "metal_painted", (0.25, 0.45, 0.75, 1),
            sides=14, cap_top=False)
    cl.cylinder((-0.35, 1.45, 0.1), (0, 0, 1), 0.062, 0.005, "metal_painted", (0.25, 0.45, 0.75, 1), sides=14)
    K.mound(cl, -0.35, 1.45, 0.106, 0.055, 0.055, 0.02, "snack_rice")
    ctx.mark_pt("MARKER_bowl", (-0.35, 1.45, 0.1))
    ctx.mark_pt("MARKER_stall_counter", ((cx0 + cx1) / 2, cy0 - 0.15, 0.1))
    # --- grandma's corner: low wooden chair, conical hat on a nail, calendar + menu on the wall
    gx, gy = 0.85, 2.35
    cl.box((gx - 0.2, gy - 0.2, 0.36), (gx + 0.2, gy + 0.2, 0.4), "lm:wood_aged", WHITE, uvmode="grain_h")
    for sx in (-1, 1):
        for sy in (-1, 1):
            cl.box((gx + sx * 0.17 - 0.02, gy + sy * 0.17 - 0.02, 0.1), (gx + sx * 0.17 + 0.02, gy + sy * 0.17 + 0.02, 0.36),
                   "lm:wood_aged", WHITE)
    cl.box((gx - 0.2, gy + 0.17, 0.4), (gx + 0.2, gy + 0.2, 0.75), "lm:wood_aged", WHITE, uvmode="grain_h")
    ctx.col((gx - 0.2, gy - 0.2, 0.1), (gx + 0.2, gy + 0.2, 0.4), "wood")
    ctx.nap.append(V((gx, gy - 0.05, 0.41)))
    ctx.mark_pt("MARKER_grandma", (gx, gy - 0.4, 0.1))
    P.basket(cl, 1.4, WB - 0.25, 1.25, 0.22, 0.18, (1.05, 0.98, 0.85, 1), "hat")   # nón lá on a nail
    K.atlas_quad(dt, [(0.4, WB - 0.01, 1.25), (0.75, WB - 0.01, 1.25), (0.75, WB - 0.01, 1.6), (0.4, WB - 0.01, 1.6)],
                 "calendar", n=(0, -1, 0))
    K.atlas_box(dt, (-1.2, WB - 0.03, 1.1), (-0.6, WB - 0.01, 1.7), "menu_tea", "lm:wood_aged", WHITE)
    K.atlas_quad(dt, [(-1.912, 0.2, 1.0), (-1.912, 0.36, 1.0), (-1.912, 0.36, 1.08), (-1.912, 0.2, 1.08)],
                 "poster_lost_cat", n=(-1, 0, 0))
    # --- brazier with the big kettle (warm spot), iced-tea cooler, styrofoam ice box, water cans
    kx, ky = 1.45, 1.75
    K.lathe(cl, (kx, ky, 0.1), [(0.17, 0), (0.17, 0.3), (0.19, 0.32)], "metal_painted", (0.25, 0.22, 0.2, 1), sides=14,
            cap_top=False)
    cl.cylinder((kx, ky, 0.36), (0, 0, 1), 0.13, 0.06, "dark", sides=14)   # honeycomb briquette
    for k in range(7):
        a = k * 2 * math.pi / 6
        r = 0.0 if k == 6 else 0.07
        cl.cylinder((kx + math.cos(a) * r, ky + math.sin(a) * r, 0.42), (0, 0, 1), 0.014, 0.002, "candle", sides=6)
    K.kettle(cl, kx, ky, 0.44, 1.3)
    ctx.col((kx - 0.19, ky - 0.19, 0.1), (kx + 0.19, ky + 0.19, 0.44), "metal")
    ctx.nap.append(V((kx - 0.45, ky + 0.25, 0.11)))    # warm floor next to the brazier
    cl.box((0.55, 0.85, 0.1), (1.1, 1.25, 0.42), "plastic_matte", (0.92, 0.92, 0.9, 1), bevel=0.02)
    cl.box((0.53, 0.83, 0.42), (1.12, 1.27, 0.46), "plastic_matte", (0.95, 0.95, 0.93, 1), bevel=0.015)
    ctx.col((0.53, 0.83, 0.1), (1.12, 1.27, 0.46), "plastic")
    K.lathe(cl, (0.82, 1.05, 0.46), [(0.13, 0), (0.14, 0.05), (0.14, 0.32), (0.1, 0.36), (0.05, 0.38)], "plastic",
            (0.85, 0.45, 0.12, 1), sides=14)
    cl.cylinder((0.82, 0.9, 0.52), (0, -1, 0), 0.015, 0.05, "plastic", (0.2, 0.5, 0.2, 1), sides=6)
    for k in range(2):
        cl.box((1.65 - k * 0.25, 2.45, 0.1), (1.85 - k * 0.25, 2.7, 0.45), "plastic", (0.85, 0.85, 0.75, 1), bevel=0.02)
    # --- front: two low tables + stools, glasses of iced tea, sunflower seed shells
    for (tx, ty) in ((-1.0, 0.85), (0.6, 0.3)):
        K.low_table(ctx, tx, ty, 0.1 if ty > 0.3 else 0.0, h=0.4)
        zt = (0.1 if ty > 0.3 else 0.0) + 0.4
        K.tea_glass(cl, tx - 0.1, ty, zt, tea=True, ice=True, h=0.1, r=0.033)
        K.tea_glass(cl, tx + 0.12, ty + 0.08, zt, tea=True, ice=True, h=0.1, r=0.033)
        K.lathe(cl, (tx + 0.05, ty - 0.12, zt), [(0.05, 0), (0.09, 0.01), (0.1, 0.015)], "ceramic", sides=10)
        K.mound(cl, tx + 0.05, ty - 0.12, zt + 0.005, 0.08, 0.08, 0.02, "snack_seeds")
    stools = [(-1.55, 0.6, 0.1), (-0.45, 1.05, 0.1), (-1.1, 0.25, 0.0), (0.05, 0.1, 0.0), (1.15, 0.05, 0.0),
              (1.1, 0.6, 0.0), (-1.75, 1.3, 0.1), (0.35, -0.35, 0.0)]
    for k, (sx_, sy_, sz) in enumerate(stools):
        K.plastic_stool(ctx, sx_, sy_, sz, col=K.STOOL_COLS[k % 2] if k < 6 else K.STOOL_COLS[2 + k % 3],
                        rot=rng.uniform(-25, 25))
    # stacked stools by the pole
    for k in range(4):
        K.plastic_stool(ctx, -1.75, 2.45, 0.1 + k * 0.06, col=K.STOOL_COLS[0], collide=(k == 0))
    # --- hanging things: bare bulb, bunch of bananas, strings of snack packets, a lighter on a string
    dt.tube([(-0.3, 1.5, 2.25), (-0.3, 1.5, 1.85)], 0.004, "dark", sides=3)
    K.lathe(dt, (-0.3, 1.5, 1.7), [(0.001, 0), (0.035, 0.03), (0.04, 0.08), (0.015, 0.14), (0.015, 0.16)], "bulb", WHITE,
            sides=10)
    ctx.mark_pt("LIGHT_NIGHT", (-0.3, 1.5, 1.6))
    ctx.lights.append(V((-0.3, 1.6, 1.9)))
    bx, by = 0.6, 1.9
    dt.tube([(bx, by, 2.25), (bx, by, 1.75)], 0.004, "fabric_canvas", (0.6, 0.5, 0.35, 1), sides=3)
    for k in range(9):
        a = k * 2 * math.pi / 9
        p0 = V((bx + math.cos(a) * 0.04, by + math.sin(a) * 0.04, 1.75))
        cl.tube([p0, p0 + V((math.cos(a) * 0.08, math.sin(a) * 0.08, -0.06)),
                 p0 + V((math.cos(a) * 0.1, math.sin(a) * 0.1, -0.16))], 0.017, "plastic", (0.85, 0.72, 0.2, 1), sides=5,
                radii=[0.012, 0.018, 0.01])
    for sxs in (-1.6, -1.3):
        dt.tube([(sxs, 0.25, 2.04), (sxs, 0.25, 1.35)], 0.003, "fabric_canvas", (0.6, 0.5, 0.35, 1), sides=3)
        for k in range(6):
            z = 1.95 - k * 0.11
            col = [(0.85, 0.2, 0.15, 1), (0.95, 0.75, 0.15, 1), (0.2, 0.5, 0.8, 1), (0.25, 0.65, 0.3, 1)][k % 4]
            cl.box((sxs - 0.06, 0.24, z - 0.09), (sxs + 0.06, 0.26, z), "plastic", col, bevel=0.003)
    # potted herbs in old paint cans along the wall
    for k, px in enumerate((-1.95, -1.7, 1.95)):
        K.lathe(cl, (px, WB - 0.15, 0.1), [(0.1, 0), (0.1, 0.2), (0.105, 0.21)], "metal_painted",
                [(0.75, 0.75, 0.7, 1), (0.6, 0.15, 0.1, 1), (0.25, 0.4, 0.6, 1)][k], sides=12, cap_top=False)
        cl.cylinder((px, WB - 0.15, 0.27), (0, 0, 1), 0.095, 0.01, "lm:leaves_ground", sides=10)
        for j in range(2):
            P.foliage_card(ctx, px, WB - 0.15, 0.25, 0.4, 0.45, "fern" if k != 1 else "leafy", j * 90 + 20)
    # festival touch: a star lantern tucked into the batten
    K.lantern_star(dt, 1.7, WB - 0.25, 2.1, 0.18)
    ctx.mark_pt("MARKER_tea_stall", (0, 0.6, 0.0))
    ctx.entr.append(V((0, 0.0, 0.0)))
    return ctx, {"height": 2.5, "floors": 1}
