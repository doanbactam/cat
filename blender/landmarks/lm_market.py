"""Chợ Hàng Mây — covered market hall, open-air stall lane segment, market-street gate arch.

cho_market_hall : origin = street-front centre of the floor slab at ground level. Hall x -12..12,
                  y 0..18 (Godot z 0..-18). Concrete columns on a 6 m grid, steel Pratt trusses spanning
                  the depth (bottom chords at 5.2 m are walkable beams, a service ladder on the NE column
                  and stacked crates give access), corrugated roof with a raised ventilation monitor.
                  West half = wet market (tiled fish counters with basins, ice, styrofoam boxes; cô Hoa's
                  counter = MARKER_fish_stall), east half = produce / dry goods on wooden platforms.
cho_stall_lane  : 12 m street segment, origin = kerb-side centre; 4 stalls with tarps / umbrellas.
cho_gate_arch   : origin = arch centre on the road; pillars at x ±4.15, sign both sides.
"""
from __future__ import annotations

import math

import city_geo as G
import city_parts as P
import landmarks_kit as K
from city_geo import V
from city_parts import WHITE, mul

HX, HY0, HY1 = 12.0, 0.0, 18.0
COLS_X = [-12.0, -6.0, 0.0, 6.0, 12.0]
COLS_Y = [0.4, 6.2, 12.0, 17.8]
EAVE = 5.2
RIDGE = 7.9
STEEL = (0.95, 0.95, 0.95, 1)
CONC = (0.95, 0.95, 0.93, 1)


def _truss(ctx: K.LCtx, x):
    dt = ctx.detail
    y0, y1 = COLS_Y[0], COLS_Y[-1]
    ym = (y0 + y1) / 2

    def top(y):
        return EAVE + (RIDGE - EAVE) * (1 - abs(y - ym) / (ym - y0))
    w = 0.1
    # bottom chord (walkable beam) + top chords (double angle look: box)
    dt.box((x - w / 2, y0 - 0.3, EAVE - 0.16), (x + w / 2, y1 + 0.3, EAVE), "lm:steel_green", STEEL)
    ctx.col((x - 0.09, y0 - 0.3, EAVE - 0.16), (x + 0.09, y1 + 0.3, EAVE), "metal")
    for ya, yb in ((y0 - 0.6, ym), (ym, y1 + 0.6)):
        za, zb = top(max(min(ya, y1), y0)) - (0.15 if ya < y0 else 0), top(max(min(yb, y1), y0))
        if ya < y0:
            za = EAVE - (RIDGE - EAVE) * (y0 - ya) / (ym - y0)
        if yb > y1:
            zb = EAVE - (RIDGE - EAVE) * (yb - y1) / (ym - y0)
        M, L = K.frame_along((x, ya, za), (x, yb, zb))
        dt.box((-w / 2, -L / 2, -0.16), (w / 2, L / 2, 0.0), "lm:steel_green", STEEL, xform=M)
        ctx.col((-0.09, -L / 2, -0.16), (0.09, L / 2, 0.0), "metal", (), M)
    # web: verticals + diagonals every 1.45 m
    n = 12
    for k in range(n + 1):
        y = y0 + (y1 - y0) * k / n
        zt = top(y) - 0.16
        if zt - EAVE > 0.05:
            dt.box((x - 0.035, y - 0.035, EAVE), (x + 0.035, y + 0.035, zt), "lm:steel_green", STEEL)
        if k < n:
            yb = y0 + (y1 - y0) * (k + 1) / n
            if y < ym:
                a, b = (x, y, EAVE), (x, yb, top(yb) - 0.16)
            else:
                a, b = (x, y, top(y) - 0.16), (x, yb, EAVE)
            dt.tube([a, b], 0.03, "lm:steel_green", STEEL, sides=4, square=True)
    # gusset plates at the heel
    for yy in (y0, y1):
        dt.box((x - 0.06, yy - 0.3, EAVE - 0.4), (x + 0.06, yy + 0.3, EAVE + 0.1), "lm:steel_green", mul(STEEL, 0.9))


def _roof(ctx: K.LCtx):
    sh, dt = ctx.shell, ctx.detail
    y0, y1 = COLS_Y[0] - 0.9, COLS_Y[-1] + 0.9
    ym = (COLS_Y[0] + COLS_Y[-1]) / 2
    slope = (RIDGE - EAVE) / (ym - COLS_Y[0])
    xa, xb = -HX - 0.9, HX + 0.9
    mon = 1.4   # monitor half-width
    for sgn in (-1, 1):
        ye = y0 if sgn < 0 else y1
        ze = EAVE - slope * (COLS_Y[0] - y0)
        # main slope up to the monitor
        yt = ym + sgn * mon
        zt = EAVE + slope * (ym - mon - COLS_Y[0])
        # individual trapezoidal sheets (~1 m) with real corrugation; most rusted, a few newer blue
        # replacements, slight height jitter so overlaps read
        x = xa
        k = 0
        rr = ctx.rng
        while x < xb - 0.01:
            w = min(xb - x, rr.uniform(0.9, 1.1))
            mat = "corrugated_blue" if rr.random() < 0.14 else "corrugated_rusted"
            tint = mul(WHITE, rr.uniform(0.85, 1.05))
            j = 0.004 * (k % 2)
            P.corrugated_sheet(ctx, x - 0.03, x + w, yt if sgn < 0 else yt, ye, zt + 0.12 + j, ze + 0.12 + j, mat,
                               pitch=0.2, amp=0.016, mb=sh, tint=tint)
            x += w
            k += 1
        K.col_slab(ctx, V((0, ye, ze + 0.12)), V((0, yt, zt + 0.12)), HX + 0.9, 0.12, "metal")
        # gutter
        sh.prism([(-0.08, -0.1), (-0.08, 0.04), (0.08, 0.04), (0.08, -0.1)], (xa, ye, ze + 0.06), (xb, ye, ze + 0.06),
                 "metal_painted", (0.55, 0.55, 0.52, 1))
        # monitor: vertical louvre band + upper roof
        zm0, zm1 = zt, zt + 0.7
        for k in range(5):
            z = zm0 + 0.05 + k * 0.13
            sh.box((xa, ym + sgn * mon - 0.04, z), (xb, ym + sgn * mon + 0.04, z + 0.06), "lm:steel_green", STEEL)
        zr = RIDGE + 0.85
        P.corrugated_sheet(ctx, xa, xb, ym, ym + sgn * (mon + 0.4), zr, zm1, "corrugated_rusted", pitch=0.2, amp=0.016,
                           mb=sh)
        K.col_slab(ctx, V((0, ym + sgn * (mon + 0.4), zm1)), V((0, ym, zr)), HX + 0.9, 0.12, "metal")
    sh.tube([(xa, ym, RIDGE + 0.87), (xb, ym, RIDGE + 0.87)], 0.06, "metal_painted", (0.5, 0.5, 0.48, 1), sides=6)
    # purlins
    for k in range(1, 6):
        for sgn in (-1, 1):
            y = ym + sgn * (mon + (ym - mon - COLS_Y[0]) * k / 6)
            z = EAVE + slope * (ym - abs(y - ym) - COLS_Y[0]) + 0.02
            dt.box((xa + 0.3, y - 0.04, z - 0.1), (xb - 0.3, y + 0.04, z + 0.09), "lm:steel_green", STEEL)
    # rain water drop patches -> decals not needed (no wall); gable infill: none (open ventilated)
    return ym


def _column(ctx: K.LCtx, x, y):
    sh = ctx.shell
    sh.box((x - 0.2, y - 0.2, 0.12), (x + 0.2, y + 0.2, EAVE - 0.1), "concrete_weathered", CONC, bevel=0.015)
    sh.box((x - 0.26, y - 0.26, 0.12), (x + 0.26, y + 0.26, 0.5), "concrete_weathered", mul(CONC, 0.85), bevel=0.01)
    ctx.col((x - 0.2, y - 0.2, 0), (x + 0.2, y + 0.2, EAVE - 0.1), "concrete", ("wall",))
    # painted stall number + posters on the street face
    P.decal_plane(ctx, ctx.rng.choice(["poster_0", "poster_1", "streak_0", "water_stain"]), V((x, y - 0.205, 2.3)),
                  (0, -1, 0), 0.36, 0.5)
    P.decal_plane(ctx, "splash_base", V((x, y - 0.265, 0.6)), (0, -1, 0), 0.5, 0.48)


def fish_counter(ctx: K.LCtx, x0, x1, y0, y1, sign=False, hoa=False):
    """Tiled concrete counter (0.8 m) with sloped display top, basin, ice, fish, scale, styrofoam boxes."""
    sh, cl = ctx.shell, ctx.clutter
    z = 0.12
    h = 0.8
    sh.box((x0, y0, z), (x1, y1, z + h), "lm:tile_white", WHITE, skip=("+z",))
    sh.box((x0 - 0.03, y0 - 0.03, z + h - 0.04), (x1 + 0.03, y1 + 0.03, z + h), "lm:tile_white", (0.9, 0.95, 0.95, 1),
           bevel=0.01, skip=("-z",))
    ctx.col((x0, y0, z), (x1, y1, z + h), "tile")
    # display tray of crushed ice with fish (front half), basin with water (back)
    ym = (y0 + y1) / 2
    cl.box((x0 + 0.08, y0 + 0.06, z + h), (x1 - 0.08, ym, z + h + 0.03), "metal_painted", (0.7, 0.7, 0.72, 1))
    K.mound(cl, (x0 + x1) / 2, (y0 + ym) / 2 + 0.03, z + h + 0.02, (x1 - x0) / 2 - 0.1, (ym - y0) / 2 - 0.05, 0.08,
            "fish_ice")
    # basin
    bx0, bx1 = x0 + 0.1, x0 + (x1 - x0) * 0.55
    for (a, b) in (((bx0, ym + 0.02), (bx1, ym + 0.08)), ((bx0, y1 - 0.08), (bx1, y1 - 0.02)),
                   ((bx0, ym + 0.02), (bx0 + 0.06, y1 - 0.02)), ((bx1 - 0.06, ym + 0.02), (bx1, y1 - 0.02))):
        sh.box((a[0], a[1], z + h), (b[0], b[1], z + h + 0.22), "lm:tile_white", WHITE, bevel=0.01)
    cl.box((bx0 + 0.06, ym + 0.08, z + h + 0.15), (bx1 - 0.06, y1 - 0.08, z + h + 0.155), "water")
    ctx.col((bx0, ym + 0.02, z + h), (bx1, y1 - 0.02, z + h + 0.22), "tile")
    # aerator hose into the basin
    cl.tube([(bx1 - 0.1, y1 - 0.1, z + h + 0.05), (bx1 - 0.05, y1 + 0.05, z + h + 0.3), (bx1 + 0.2, y1 + 0.2, z + 0.4),
             (bx1 + 0.3, y1 + 0.25, z)], 0.006, "plastic", (0.2, 0.6, 0.3, 1), sides=4)
    # scale
    sx = x1 - 0.3
    cl.box((sx - 0.12, y1 - 0.35, z + h), (sx + 0.12, y1 - 0.12, z + h + 0.1), "plastic", (0.85, 0.85, 0.82, 1), bevel=0.01)
    K.lathe(cl, (sx, y1 - 0.235, z + h + 0.1), [(0.02, 0), (0.02, 0.06), (0.14, 0.07), (0.15, 0.09)], "chrome", WHITE,
            sides=14)
    cl.cylinder((sx, y1 - 0.355, z + h + 0.06), (0, -1, 0), 0.04, 0.005, "plastic", (0.95, 0.95, 0.9, 1), sides=12)
    # styrofoam boxes + red plastic basin on the floor in front of the counter
    for k in range(2):
        bx = x0 + 0.35 + k * 0.7
        cl.box((bx - 0.3, y0 - 0.5, 0.12), (bx + 0.3, y0 - 0.1, 0.42), "plastic_matte", (0.92, 0.92, 0.9, 1), bevel=0.02)
        ctx.col((bx - 0.3, y0 - 0.5, 0.12), (bx + 0.3, y0 - 0.1, 0.42), "plastic")
    K.lathe(cl, (x1 - 0.3, y0 - 0.35, 0.12), [(0.18, 0), (0.25, 0.14), (0.26, 0.15)], "plastic", (0.75, 0.12, 0.1, 1),
            sides=16, cap_top=False)
    cl.cylinder((x1 - 0.3, y0 - 0.35, 0.22), (0, 0, 1), 0.23, 0.003, "water", sides=16)
    # price cards stuck into the ice
    K.atlas_quad(cl, [(x0 + 0.2, y0 + 0.04, z + h + 0.05), (x0 + 0.42, y0 + 0.04, z + h + 0.05),
                      (x0 + 0.42, y0 + 0.04, z + h + 0.27), (x0 + 0.2, y0 + 0.04, z + h + 0.27)], "price_cards",
                 n=(0, -1, 0))
    # vendor stool behind + bucket
    K.plastic_stool(ctx, (x0 + x1) / 2 + 0.3, y1 + 0.45, 0.12, h=0.38, top=0.3)
    if sign:
        K.atlas_box(ctx.detail, ((x0 + x1) / 2 - 0.9, y1 + 0.05, 2.1), ((x0 + x1) / 2 + 0.9, y1 + 0.1, 2.55), "sign_fish",
                    "metal_painted", WHITE)
        for xx in ((x0 + x1) / 2 - 0.8, (x0 + x1) / 2 + 0.8):
            ctx.detail.tube([(xx, y1 + 0.075, 2.55), (xx, y1 + 0.075, EAVE - 0.15)], 0.005, "iron_wrought", sides=4)
    # hanging bulb over the counter
    bxm, bym = (x0 + x1) / 2, (y0 + y1) / 2
    ctx.detail.tube([(bxm, bym, EAVE - 0.16), (bxm, bym, 2.55)], 0.004, "dark", sides=4)
    K.lathe(ctx.detail, (bxm, bym, 2.38), [(0.001, 0), (0.035, 0.03), (0.04, 0.08), (0.015, 0.14), (0.015, 0.17)],
            "bulb", WHITE, sides=10)
    if hoa:
        ctx.mark_pt("MARKER_fish_stall", ((x0 + x1) / 2, y0 - 0.25, 0.12))
        ctx.mark_pt("QUEST_fish_stall", ((x0 + x1) / 2, (y0 + y1) / 2, z + h + 0.05))


def produce_platform(ctx: K.LCtx, x0, x1, y0, y1, rng, cells):
    """Raised wooden platform (sạp) with produce in flat bamboo trays, sacks, crates, a canvas over it."""
    sh, cl = ctx.shell, ctx.clutter
    z = 0.12
    h = 0.6
    sh.box((x0, y0, z), (x1, y1, z + 0.08), "lm:wood_aged", WHITE, uvmode="grain_h", skip=())
    sh.box((x0, y0, z + h - 0.05), (x1, y1, z + h), "lm:wood_aged", WHITE, bevel=0.005, uvmode="grain_h")
    for xx in (x0 + 0.05, x1 - 0.05):
        for yy in (y0 + 0.05, y1 - 0.05):
            sh.box((xx - 0.04, yy - 0.04, z), (xx + 0.04, yy + 0.04, z + h - 0.05), "lm:wood_aged", WHITE)
    ctx.col((x0, y0, z), (x1, y1, z + h), "wood")
    n = max(2, int((x1 - x0) / 0.62))
    for k in range(n):
        cx = x0 + (k + 0.5) * (x1 - x0) / n
        for j, cy in enumerate(((y0 * 0.7 + y1 * 0.3), (y0 * 0.3 + y1 * 0.7))):
            r = min((x1 - x0) / n, (y1 - y0) / 2) * 0.46
            P.basket(cl, cx, cy, z + h, r, 0.05, mul(WHITE, rng.uniform(0.85, 1.05)), "tray")
            K.mound(cl, cx, cy, z + h + 0.03, r * 0.85, r * 0.85, r * rng.uniform(0.35, 0.6), rng.choice(cells))
    # sacks under the platform + a scale
    for k in range(2):
        sx = x0 + 0.4 + k * 0.6
        K.lathe(cl, (sx, y1 - 0.3, z + 0.08), [(0.18, 0), (0.22, 0.12), (0.2, 0.36), (0.12, 0.44), (0.05, 0.47)],
                "fabric_canvas", (0.85, 0.8, 0.68, 1), sides=10)
    ctx.nap.append(V((x1 - 0.3, y1 - 0.25, z + h + 0.01)))


def build_hall(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, cl, dt = ctx.shell, ctx.clutter, ctx.detail
    rng = ctx.rng
    # floor slab with drain channel and a step at the street edge
    sh.box((-HX - 0.3, HY0, 0), (HX + 0.3, HY1 + 0.2, 0.12), "lm:market_floor", WHITE, skip=("-z",))
    ctx.col((-HX - 0.3, HY0, -0.2), (HX + 0.3, HY1 + 0.2, 0.12), "concrete")
    sh.box((-HX - 0.3, HY1 + 0.2 - 0.0, 0), (HX + 0.3, HY1 + 0.4, 1.3), "brick_exposed", WHITE)
    ctx.col((-HX - 0.3, HY1 + 0.2, 0), (HX + 0.3, HY1 + 0.4, 1.3), "concrete", ("wall",))
    P.wall_weathering(ctx, V((-HX - 0.3, HY1 + 0.19, 0)), V((1, 0, 0)), 2 * HX + 0.6, 1.3, V((0, -1, 0)), rng,
                      top_streaks=False)
    cl.box((-HX, 8.9, 0.115), (HX, 9.3, 0.122), "iron_wrought", (0.5, 0.5, 0.5, 1))  # drain grating strip
    for x in COLS_X:
        for y in COLS_Y:
            _column(ctx, x, y)
    for x in COLS_X:
        _truss(ctx, x)
    # longitudinal eave beams
    for y in (COLS_Y[0], COLS_Y[-1]):
        dt.box((-HX - 0.2, y - 0.15, EAVE - 0.45), (HX + 0.2, y + 0.15, EAVE - 0.1), "concrete_weathered", CONC)
        ctx.col((-HX - 0.2, y - 0.15, EAVE - 0.45), (HX + 0.2, y + 0.15, EAVE - 0.1), "concrete")
    _roof(ctx)
    # --- wet market (west): fish counters in two rows
    k = 0
    for row_y in (3.0, 9.8):
        for x0 in (-11.2, -8.2, -5.2, -2.2):
            fish_counter(ctx, x0, x0 + 2.2, row_y, row_y + 1.3, sign=(k == 1), hoa=(k == 1))
            k += 1
    # --- produce / dry goods (east)
    cells_veg = ["veg_greens", "veg_tomato", "veg_chili", "fruit_orange", "fruit_dragon", "fruit_banana", "veg_herbs"]
    cells_dry = ["dried_goods", "snack_peanut", "snack_rice", "snack_tea", "dried_goods"]
    for j, row_y in enumerate((3.0, 9.8, 14.6)):
        for x0 in (1.0, 4.0, 7.0, 10.0):
            if x0 + 2.0 > HX - 0.4:
                continue
            produce_platform(ctx, x0, x0 + 2.0, row_y, row_y + 1.4, rng, cells_veg if j < 2 else cells_dry)
            if rng.random() < 0.5:
                K.plastic_stool(ctx, x0 + 1.0, row_y + 1.75, 0.12)
    # stacked crates against the NE column -> access to the truss via the ladder
    for i, (cx, cy, cz) in enumerate(((10.9, 16.9, 0.12), (10.9, 16.9, 0.42), (11.45, 16.9, 0.12), (10.9, 16.4, 0.12))):
        K.crate(ctx, cx, cy, cz, rot=0.0)
    P.ladder(ctx, 12.0, 17.5, 0.12, EAVE - 0.2)
    # rear stack of empty styrofoam boxes and a hand cart
    for k in range(4):
        cl.box((-11.5, 16.6, 0.12 + k * 0.3), (-10.9, 17.0, 0.42 + k * 0.3), "plastic_matte", (0.92, 0.92, 0.9, 1),
               bevel=0.02)
    ctx.col((-11.5, 16.6, 0.12), (-10.9, 17.0, 1.32), "plastic")
    ctx.nap.append(V((-11.2, 16.8, 1.33)))
    # canvas tarps tied under the trusses over some stalls (sun/rain shades)
    for x0, y0 in ((-11.0, 2.4), (1.2, 9.2), (7.2, 2.4)):
        K.sag_cloth(cl, (x0, y0, 3.2), (x0 + 2.6, y0, 3.2), (x0, y0 + 2.0, 3.35), (x0 + 2.6, y0 + 2.0, 3.35),
                    "lm:tarp_stripe" if x0 > 0 else "lm:tarp_blue", WHITE, nu=8, nv=6, sag=0.18, seed=int(x0 * 3))
        for (px, py) in ((x0, y0), (x0 + 2.6, y0), (x0, y0 + 2.0), (x0 + 2.6, y0 + 2.0)):
            cl.tube([(px, py, 3.2), (px, py, EAVE - 0.16)], 0.004, "fabric_canvas", (0.5, 0.45, 0.35, 1), sides=3)
    # hanging bulbs over the produce rows + night lights
    for x in (2.0, 5.0, 8.0, 11.0):
        for y in (3.7, 10.5):
            dt.tube([(x, y, EAVE - 0.16), (x, y, 2.6)], 0.004, "dark", sides=4)
            K.lathe(dt, (x, y, 2.42), [(0.001, 0), (0.035, 0.03), (0.04, 0.08), (0.015, 0.14), (0.015, 0.18)], "bulb",
                    WHITE, sides=10)
    for x in (-9.0, -3.0, 3.0, 9.0):
        ctx.mark_pt("LIGHT_NIGHT", (x, 9.0, 3.0))
    for x in (-6.0, 6.0):
        ctx.lights.append(V((x, 6.0, 3.5)))
    # nap spots up on the truss bottom chords (cat balance beams)
    ctx.nap.append(V((6.0, 9.1, EAVE + 0.01)))
    # downpipe on the street-front column at x=6: second climb route up to the eave beam
    P.drainpipe(ctx, 6.0, 0.12, EAVE - 0.3, COLS_Y[0] - 0.2, "plastic", (0.6, 0.62, 0.6, 1), r=0.05, offset=0.06)
    ctx.entr += [V((x, -0.1, 0.12)) for x in (-9.0, -3.0, 3.0, 9.0)]
    ctx.zone("SHELTER", (-HX - 0.9, -0.5, 0.0), (HX + 0.9, HY1 + 0.5, EAVE))
    ctx.zone("REVERB_Market", (-HX, 0.0, 0.0), (HX, HY1, EAVE + 1.5))
    ctx.mark_pt("MARKER_market_hall", (0, 9.0, 0.12))
    return ctx, {"height": RIDGE + 1.0, "floors": 1}


# ---------------------------------------------------------------------------
def umbrella(ctx: K.LCtx, x, y, r=1.25, h=2.3, tilt=8.0, col=(0.85, 0.2, 0.15, 1)):
    """Big market umbrella with alternating panels, on a pole stuck in a weighted bucket."""
    cl = ctx.clutter
    import bmesh
    from mathutils import Matrix
    R = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(math.radians(tilt), 4, "X") @ Matrix.Translation((-x, -y, 0))
    n = 8
    c = V((x, y, h + 0.35))
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0 = V((x + math.cos(a0) * r, y + math.sin(a0) * r, h))
        p1 = V((x + math.cos(a1) * r, y + math.sin(a1) * r, h))
        pc = (p0 + p1) / 2 + V((0, 0, 0.06))
        tint = col if k % 2 == 0 else (0.92, 0.9, 0.84, 1)
        for tri in ((p0, pc, c), (pc, p1, c)):
            bm = bmesh.new()
            vs = [bm.verts.new(R @ q) for q in tri]
            bm.faces.new(vs)
            bm.faces.new([bm.verts.new(R @ q - V((0, 0, 0.005))) for q in reversed(tri)])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            cl.add_bm(bm, "fabric_canvas", tint)
        cl.tube([R @ c, R @ p0], 0.006, "chrome", (0.6, 0.6, 0.6, 1), sides=4)
    cl.tube([V((x, y, 0.0)), R @ c], 0.02, "chrome", (0.7, 0.7, 0.7, 1), sides=8)
    K.lathe(cl, (x, y, 0), [(0.14, 0), (0.17, 0.3), (0.18, 0.32)], "plastic", (0.2, 0.2, 0.22, 1), sides=14)
    ctx.zone("SHELTER", (x - r * 0.8, y - r * 0.8, 0), (x + r * 0.8, y + r * 0.8, h))


def build_lane(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, cl = ctx.shell, ctx.clutter
    rng = ctx.rng
    # sidewalk pavers + kerb at the front edge
    sh.box((-6.0, 0.0, 0.0), (6.0, 3.2, 0.15), "lm:brick_paving", (0.85, 0.85, 0.85, 1),
           skip=("-z",))
    sh.box((-6.0, -0.02, 0.0), (6.0, 0.18, 0.16), "lm:bluestone", WHITE, bevel=0.015)
    ctx.col((-6.0, 0.0, -0.1), (6.0, 3.2, 0.15), "tile")
    z = 0.15
    cells_veg = ["veg_greens", "veg_tomato", "veg_chili", "fruit_orange", "fruit_dragon", "fruit_banana", "veg_herbs"]
    stalls = [(-6.0, -3.0, "umbrella"), (-3.0, 0.0, "tarp"), (0.0, 3.0, "umbrella"), (3.0, 6.0, "tarp")]
    for i, (x0, x1, roof) in enumerate(stalls):
        cx = (x0 + x1) / 2
        # display: wooden board on two crates / folding legs
        bx0, bx1, by0, by1 = x0 + 0.3, x1 - 0.3, 1.0, 1.9
        K.crate(ctx, bx0 + 0.35, (by0 + by1) / 2, z, rot=90, w=0.55, d=0.38, h=0.3, collide=False)
        K.crate(ctx, bx1 - 0.35, (by0 + by1) / 2, z, rot=90, w=0.55, d=0.38, h=0.3, collide=False)
        sh.box((bx0, by0, z + 0.3), (bx1, by1, z + 0.34), "lm:wood_aged", WHITE, uvmode="grain_h", bevel=0.005)
        ctx.col((bx0, by0, z), (bx1, by1, z + 0.34), "wood")
        n = 4
        for k in range(n):
            ccx = bx0 + (k + 0.5) * (bx1 - bx0) / n
            P.basket(cl, ccx, (by0 + by1) / 2, z + 0.34, 0.27, 0.05, mul(WHITE, rng.uniform(0.85, 1.05)), "tray")
            K.mound(cl, ccx, (by0 + by1) / 2, z + 0.37, 0.24, 0.24, rng.uniform(0.07, 0.13), rng.choice(cells_veg))
        K.atlas_quad(cl, [(cx - 0.25, by0 - 0.01, z + 0.15), (cx + 0.25, by0 - 0.01, z + 0.15),
                          (cx + 0.25, by0 - 0.01, z + 0.33), (cx - 0.25, by0 - 0.01, z + 0.33)], "price_cards",
                     n=(0, -1, 0))
        # vendor stool + basket + conical hat on the stool
        K.plastic_stool(ctx, cx + 0.5, 2.5, z)
        P.basket(cl, cx - 0.6, 2.6, z, 0.25, 0.22, WHITE, "bowl")
        P.basket(cl, cx + 0.5, 2.5, z + 0.26, 0.2, 0.14, (0.95, 0.9, 0.8, 1), "hat")
        if roof == "umbrella":
            umbrella(ctx, cx, 1.5, col=rng.choice([(0.85, 0.2, 0.15, 1), (0.2, 0.45, 0.75, 1), (0.9, 0.6, 0.1, 1)]))
        else:
            # tarp stretched between two bamboo poles at the front and the wall hooks behind
            for px in (x0 + 0.15, x1 - 0.15):
                cl.tube([(px, 0.45, z), (px, 0.45, 2.15)], 0.03, "wood_brown", (1.7, 1.5, 0.9, 1), sides=8)
            K.sag_cloth(cl, (x0 + 0.1, 0.4, 2.15), (x1 - 0.1, 0.4, 2.15), (x0 + 0.1, 3.2, 2.55), (x1 - 0.1, 3.2, 2.55),
                        "lm:tarp_stripe" if i % 2 else "lm:tarp_orange", WHITE, nu=8, nv=6, sag=0.15, seed=i)
            ctx.zone("SHELTER", (x0 + 0.1, 0.4, 0.0), (x1 - 0.1, 3.2, 2.1))
            ctx.nap.append(V((cx, 1.45, z + 0.35)))
    for k in range(3):
        K.crate(ctx, -5.5 + k * 0.6, 2.85, z, rot=0, col=(0.15, 0.35, 0.7, 1))
    K.crate(ctx, -5.2, 2.85, z + 0.3, rot=0)
    ctx.mark_pt("MARKER_stall_lane", (0, 1.5, z))
    return ctx, {"height": 2.7, "floors": 1}


# ---------------------------------------------------------------------------
def build_gate(spec):
    ctx = K.LCtx(spec["id"], spec["seed"])
    sh, dt = ctx.shell, ctx.detail
    px = 4.15
    H = 4.6
    for sx in (-1, 1):
        x = sx * px
        sh.box((x - 0.4, -0.4, 0), (x + 0.4, 0.4, 0.5), "lm:stone_plinth", WHITE, bevel=0.02)
        sh.box((x - 0.32, -0.32, 0.5), (x + 0.32, 0.32, H), "plaster_yellow", WHITE, bevel=0.02)
        for z in (1.4, 3.2):
            sh.box((x - 0.36, -0.36, z), (x + 0.36, 0.36, z + 0.08), "stucco_detail", WHITE, bevel=0.01)
        ctx.col((x - 0.4, -0.4, 0), (x + 0.4, 0.4, H), "concrete", ("wall", "climb"))
        P.decal_plane(ctx, "moss_base", V((x, -0.325, 0.9)), (0, -1, 0), 0.64, 0.8)
        P.decal_plane(ctx, "streak_1", V((x, -0.325, H)), (0, -1, 0), 0.6, 2.2)
        # posters / notices pasted on the pillar
        P.decal_plane(ctx, "poster_1" if sx < 0 else "poster_0", V((x, -0.33, 2.2)), (0, -1, 0), 0.4, 0.55)
    # arched beam: segmented curved box between the pillars
    n = 16
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        xa, xb = -px - 0.4 + (2 * px + 0.8) * t0, -px - 0.4 + (2 * px + 0.8) * t1
        za = H + 0.35 * math.sin(math.pi * t0)
        zb = H + 0.35 * math.sin(math.pi * t1)
        M, L = K.frame_along((xa, 0, za), (xb, 0, zb), up=(0, 0, 1))
        sh.box((-0.3, -L / 2 - 0.002, 0), (0.3, L / 2 + 0.002, 0.55), "plaster_yellow", WHITE,
               xform=M)
        ctx.col((-0.3, -L / 2, 0), (0.3, L / 2, 0.55), "concrete", (), M)
    # sign boards both faces
    for sgn, face in ((-1, "-y"), (1, "+y")):
        y = sgn * 0.31
        K.atlas_box(dt, (-3.0, y - 0.04 if sgn < 0 else y, H + 0.35), (3.0, y if sgn < 0 else y + 0.04, H + 0.95),
                    "sign_cho", "metal_painted", WHITE, face=face)
    # small tiled canopy on top with upturned ends
    roof = K.HipRoof(0, 0, px + 0.7, 0.55, H + 1.05, 0.45, p=1.2, U=0.35, L=0.8)
    roof.build(ctx, collide=True, nt=6, du=0.3, thick=0.1)
    K.roof_ornaments(ctx, roof, ridge_h=0.18, ridge_w=0.2, curl=0.45, centre="sun")
    # lanterns hanging under the beam (red cylinder lanterns + festival star lanterns)
    for x in (-2.2, 2.2):
        dt.tube([(x, 0, H), (x, 0, H - 0.5)], 0.004, "dark", sides=3)
        K.lathe(dt, (x, 0, H - 1.0), [(0.05, 0), (0.18, 0.08), (0.21, 0.25), (0.18, 0.42), (0.05, 0.5)], "atlas",
                (0.95, 0.9, 0.9, 1), sides=12)
        dt.cylinder((x, 0, H - 1.06), (0, 0, 1), 0.06, 0.06, "lm:gilt", sides=8)
        dt.tube([(x, 0, H - 1.06), (x, 0, H - 1.35)], 0.012, "plastic", (0.85, 0.65, 0.1, 1), sides=4)
        ctx.mark_pt("LIGHT_NIGHT", (x, 0, H - 0.75))
    K.lantern_star(dt, 0.0, -0.05, H - 0.4, 0.3)
    dt.tube([(0, -0.05, H), (0, -0.05, H - 0.1)], 0.004, "dark", sides=3)
    ctx.climb += [V((sx * px, -0.45, 1.0)) for sx in (-1, 1)]
    ctx.nap.append(V((px, 0.0, H + 0.36)))
    ctx.mark_pt("MARKER_market_gate", (0, 0, 0))
    return ctx, {"height": H + 1.9, "floors": 1}
