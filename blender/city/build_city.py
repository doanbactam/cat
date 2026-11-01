"""Old-quarter architecture kit generator (Blender 5.2, headless).

Run:   tools/blender_run.sh blender/city/build_city.py [-- --only id1,id2] [--preview] [--no-export]
Needs: python3 blender/city/gen_textures.py && python3 blender/city/gen_atlases.py (textures first)
Out:   assets/models/city/<module>.glb (+ .import with the post-import script)
       assets/models/city/catalog.json
       qa/out/city-houses/<module>.png with --preview

Every module is built procedurally from a spec (style, width, floors, depth, palette, seed); variants
reuse the geometry seed and swap palette + clutter seed. Front facade faces Blender -Y (Godot +Z),
origin = facade bottom-centre at sidewalk level.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import common as C  # noqa: E402
import city_geo as G  # noqa: E402
import city_glb as GLB  # noqa: E402
import city_mats as CM  # noqa: E402
import city_parts as P  # noqa: E402
from city_geo import V  # noqa: E402
from city_parts import WHITE, mul  # noqa: E402

OUT_DIR = C.asset_path("models/city/x").rsplit("/", 1)[0]
TEX_REL = "../../textures/architecture"
TMP = os.path.join("/tmp", "city_houses_build")

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
PAL = {
    # colonial
    "col_ochre": dict(wall="plaster_ochre", trim=(1.0, 0.97, 0.9), shutter="wood_teal", side="cement_render",
                      roof="roof_tile_terracotta"),
    "col_blue": dict(wall="plaster_blue", trim=(1.0, 1.0, 0.97), shutter="wood_green", side="cement_render",
                     roof="roof_tile_terracotta"),
    "col_yellow": dict(wall="plaster_yellow", trim=(1.0, 0.98, 0.94), shutter="wood_green", side="cement_render",
                       roof="roof_tile_terracotta"),
    "col_pink": dict(wall="plaster_pink", trim=(1.0, 0.96, 0.9), shutter="wood_teal", side="cement_render",
                     roof="roof_tile_terracotta"),
    "col_white": dict(wall="plaster_white", trim=(0.95, 0.93, 0.88), shutter="wood_teal", side="cement_render",
                      roof="roof_tile_terracotta"),
    # 1990s tube houses
    "t90_blue": dict(wall="plaster_white", tile="tile_mosaic_blue", metal=(0.28, 0.42, 0.38, 1), side="cement_render",
                     deco_roof="roof_tile_terracotta"),
    "t90_pink": dict(wall="plaster_pink", tile="tile_ceramic_beige", metal=(0.82, 0.82, 0.8, 1), side="brick_exposed",
                     deco_roof="roof_tile_terracotta"),
    "t90_green": dict(wall="plaster_green", tile="tile_strip_brown", metal=(0.2, 0.22, 0.24, 1), side="cement_render",
                      deco_roof="roof_tile_terracotta"),
    "t90_yellow": dict(wall="plaster_yellow", tile="tile_mosaic_green", metal=(0.25, 0.33, 0.45, 1),
                       side="cement_render", deco_roof="roof_tile_terracotta"),
    "t90_white": dict(wall="plaster_white", tile="tile_ceramic_beige", metal=(0.42, 0.18, 0.15, 1),
                      side="brick_exposed", deco_roof="roof_tile_terracotta"),
    # modern
    "mod_white": dict(wall="render_modern", wall_tint=(1, 1, 1), acp=(0.55, 0.57, 0.6, 1), side="cement_render"),
    "mod_grey": dict(wall="render_modern", wall_tint=(0.78, 0.77, 0.74), acp=(0.82, 0.74, 0.6, 1),
                     side="cement_render"),
    "mod_dark": dict(wall="render_modern", wall_tint=(0.55, 0.55, 0.56), acp=(0.9, 0.9, 0.88, 1),
                     side="cement_render"),
    # old single-storey
    "old_white": dict(wall="plaster_white", door="wood_brown", roof="roof_tile_old", side="brick_exposed"),
    "old_yellow": dict(wall="plaster_yellow", door="wood_teal", roof="roof_tile_old", side="cement_render"),
    "old_blue": dict(wall="plaster_blue", door="wood_brown", roof="roof_tile_old", side="brick_exposed"),
    # alley / rear
    "alley_grey": dict(wall="cement_render", trim=(1, 1, 1), side="cement_render"),
    "alley_yellow": dict(wall="plaster_yellow", trim=(1, 1, 1), side="cement_render"),
    "alley_brick": dict(wall="brick_exposed", trim=(1, 1, 1), side="cement_render"),
    "alley_green": dict(wall="plaster_green", trim=(1, 1, 1), side="cement_render"),
}
CANVAS = [(0.15, 0.3, 0.62, 1), (0.75, 0.18, 0.12, 1), (0.2, 0.5, 0.3, 1), (0.85, 0.55, 0.12, 1),
          (0.9, 0.9, 0.85, 1)]


# ---------------------------------------------------------------------------
# Shared shell pieces
# ---------------------------------------------------------------------------
def side_and_back(ctx: P.Ctx, W, D, H, side_mat, back_mat, back_tint=WHITE, back_windows=True, start_y=0.0):
    """Party walls (x = +-W/2) and rear wall (y = D) incl. modest rear-facade detail."""
    sh = ctx.shell
    rng = ctx.rng
    hw = W / 2
    stint = mul(WHITE, rng.uniform(0.85, 1.0))
    P.plain_wall(sh, (-hw, start_y, 0), (0, 1, 0), D - start_y, H, side_mat, stint, (-1, 0, 0), 0.6)
    P.plain_wall(sh, (hw, start_y, 0), (0, 1, 0), D - start_y, H, side_mat, stint, (1, 0, 0), 0.6)
    ctx.col((-hw, start_y, 0), (-hw + 0.2, D, H), "concrete", ("wall",))
    ctx.col((hw - 0.2, start_y, 0), (hw, D, H), "concrete", ("wall",))
    P.wall_weathering(ctx, (-hw, start_y, 0), (0, 1, 0), D - start_y, H, (-1, 0, 0))
    P.wall_weathering(ctx, (hw, start_y, 0), (0, 1, 0), D - start_y, H, (1, 0, 0))
    # rear wall (faces +Y): small windows, a drainpipe, an AC unit
    holes = []
    if back_windows:
        z = 1.0
        while z + 1.4 < H - 0.6:
            w = min(1.2, W - 1.2)
            holes.append((-w / 2, z, w / 2, z + 1.2))
            z += 3.4
    mk = ctx.mark()
    P.wall_with_holes(sh, -hw, hw, 0, H, holes, back_mat, back_tint, y=0.0, depth=0.2)
    for (x0, z0, x1, z1) in holes:
        P.alu_window(ctx, x0, z0, x1, z1, 0.0, 0.12, (0.8, 0.8, 0.8, 1), panes=2)
        P.grille(ctx, x0 - 0.05, z0 - 0.05, x1 + 0.05, z1 + 0.05, -0.01, (0.3, 0.3, 0.3, 1), "bars")
    if H > 5 and rng.random() < 0.8:
        P.drainpipe(ctx, hw - 0.35, 0.0, H - 0.1, 0.0, "plastic", (0.75, 0.75, 0.72, 1))
    if holes and rng.random() < 0.7:
        h = holes[rng.randrange(len(holes))]
        P.ac_unit(ctx, -hw + 0.6 if W > 3.8 else 0.0, h[1] + 1.5, 0.0, nap=True)
    ctx.col((-hw, 0.0, 0), (hw, 0.2, H), "concrete", ("wall",))
    P.wall_weathering(ctx, (-hw, 0.0, 0), (1, 0, 0), W, H, (0, -1, 0), cat_level=False)
    ctx.xform_since(mk, Matrix.Translation((0, D, 0)) @ Matrix.Rotation(math.pi, 4, "Z"))


def roof_flat(ctx: P.Ctx, W, D, z, parapet=1.0, front_mat="plaster_white", tint=WHITE, clutter=True,
              tum=True, front_parapet=True, rail=False, style="t90"):
    """Flat roof terrace: slab, parapets, scuppers, stair-head room, tank, solar heater, plants, laundry."""
    rng = ctx.rng
    sh = ctx.shell
    hw = W / 2
    # slab top (terrace tiles on many, bare concrete on others)
    floor_mat = rng.choice(["concrete_weathered", "concrete_weathered", "terrazzo"]) if style != "mod" else "terrazzo"
    sh.box((-hw, 0, z - 0.25), (hw, D, z), "concrete_weathered", WHITE, skip=("-z", "-x", "+x", "-y", "+y"))
    sh.box((-hw + 0.15, 0.2, z), (hw - 0.15, D - 0.15, z + 0.02), floor_mat,
           (0.62, 0.42, 0.33, 1) if floor_mat == "terrazzo" and rng.random() < 0.6 else WHITE, skip=("-z",))
    ctx.col((-hw, 0, z - 0.25), (hw, D, z + 0.02), "tile" if floor_mat == "terrazzo" else "concrete")
    # parapets: sides (party walls up), back, front
    ph = parapet
    for xs in (-hw, hw - 0.15):
        P.masonry_parapet(ctx, xs, xs + 0.15, 0.0, D, z, ph, "cement_render", mul(WHITE, 0.9))
    P.masonry_parapet(ctx, -hw + 0.15, hw - 0.15, D - 0.15, D, z, ph, "cement_render", mul(WHITE, 0.9))
    if front_parapet:
        P.masonry_parapet(ctx, -hw + 0.15, hw - 0.15, 0.0, 0.18, z, ph, front_mat, tint)
        if rail:
            P.railing_steel(ctx, -hw + 0.2, hw - 0.2, 0.09, z + ph + 0.05, 0.6, (0.25, 0.25, 0.25, 1))
    ctx.nap.append(V((-hw + 0.075, D * 0.5, z + ph + 0.05)))
    # scupper + stains
    if not clutter:
        return z
    zz_top = z
    if tum and D > 8:
        tw = min(W - 0.6, 2.6)
        tx0 = hw - 0.2 - tw if rng.random() < 0.5 else -hw + 0.2
        ty0 = D - 3.4
        top = P.stair_head(ctx, tx0, tx0 + tw, ty0, D - 0.2, z, 2.6, "plaster_white", (0.9, 0.9, 0.88, 1))
        # tank on the stair-head roof
        if rng.random() < 0.85:
            P.water_tank(ctx, tx0 + tw / 2, ty0 + 1.6, top, rng.choice(["horizontal", "horizontal", "vertical"]))
        ladder_x = tx0 - 0.35 if tx0 > -hw + 1 else tx0 + tw + 0.35
        if abs(ladder_x) < hw - 0.3:
            P.ladder(ctx, ladder_x, ty0 + 0.6, z, top, bamboo=rng.random() < 0.4)
        zz_top = top
        free_y1 = ty0 - 0.3
    else:
        free_y1 = D - 0.5
    if rng.random() < 0.75 and free_y1 > 4:
        P.solar_heater(ctx, rng.uniform(-hw + 0.9, hw - 0.9) * 0.3, free_y1 - 0.4, z, ntubes=rng.choice([12, 14, 16])
                       if W > 4 else 10)
    if rng.random() < 0.7:
        P.antenna(ctx, hw - 0.5, free_y1 - 2.4, z, rng.uniform(2.5, 3.6))
    # potted plants / styrofoam vegetable boxes along the front parapet
    n = int(W / 0.8)
    for k in range(n):
        if rng.random() < 0.6:
            x = -hw + 0.5 + k * (W - 1.0) / max(n - 1, 1)
            P.potted_plant(ctx, x, 0.5, z + 0.02, rng.uniform(0.35, 0.6),
                           pot=rng.choice(["styro", "terracotta", "styro", "blue"]))
    # laundry line across the terrace
    if rng.random() < 0.75 and free_y1 > 3.5:
        y = rng.uniform(1.6, free_y1 - 1.2)
        P.laundry_line(ctx, (-hw + 0.2, y, z + 1.9), (hw - 0.2, y + rng.uniform(-0.3, 0.3), z + 1.85))
        for x in (-hw + 0.2, hw - 0.2):
            ctx.clutter.tube([(x, y, z), (x, y, z + 1.95)], 0.02, "metal_painted", (0.4, 0.4, 0.4, 1), sides=6)
    if rng.random() < 0.35 and free_y1 > 5:
        P.roof_shed(ctx, -hw + 0.25, -hw + min(2.4, W - 0.6), free_y1 - 3.2, free_y1 - 1.0, z, 2.1,
                    rng.choice(["corrugated_rusted", "corrugated_blue"]))
    ctx.nap.append(V((0.0, D * 0.4, z + 0.02)))
    return zz_top


def roof_pitched(ctx: P.Ctx, W, D, z_eave, pitch_deg=28, mat="roof_tile_terracotta", y0=0.6, front_eave=0.0,
                 back_eave=0.4, gable_mat="cement_render", ridge_y=None, wall_top=None):
    """Two-slope tile roof, ridge parallel to the street. Gable walls on the party walls."""
    hw = W / 2
    ry = ridge_y if ridge_y is not None else (y0 + D) / 2
    zr = z_eave + math.tan(math.radians(pitch_deg)) * (ry - y0)
    ov = 0.15
    yf = y0 - front_eave
    yb = D + back_eave
    zf = z_eave - math.tan(math.radians(pitch_deg)) * front_eave
    zb = z_eave + math.tan(math.radians(pitch_deg)) * (ry - y0) - math.tan(math.radians(pitch_deg)) * (yb - ry)
    P.roof_plane(ctx, -hw - ov * 0, hw + ov * 0, yf, zf, ry, zr, mat)
    P.roof_plane(ctx, -hw, hw, yb, zb, ry, zr, mat)
    # ridge cap
    ctx.shell.tube([(-hw, ry, zr + 0.03), (hw, ry, zr + 0.03)], 0.09, mat, mul(WHITE, 0.85), sides=8)
    ctx.col((-hw, ry - 0.08, zr - 0.05), (hw, ry + 0.08, zr + 0.12), "roof_tile")
    # gable walls (triangles) on both party walls, closed down to the wall top
    wt = z_eave if wall_top is None else wall_top
    for xs, n in ((-hw, (-1, 0, 0)), (hw, (1, 0, 0))):
        pts = [(xs, y0, z_eave), (xs, D, z_eave), (xs, ry, zr - 0.02)]
        P.quad_n(ctx.shell, [pts[0], pts[1], pts[2], pts[2]], gable_mat, WHITE, n)
        if wt < z_eave - 0.005:
            P.quad_n(ctx.shell, [(xs, y0, wt), (xs, D, wt), (xs, D, z_eave), (xs, y0, z_eave)], gable_mat, WHITE, n)
    if wt < z_eave - 0.005:  # front and back knee walls under the eaves
        P.quad_n(ctx.shell, [(-hw, y0, wt), (hw, y0, wt), (hw, y0, z_eave), (-hw, y0, z_eave)], gable_mat, WHITE,
                 (0, -1, 0))
        P.quad_n(ctx.shell, [(-hw, D, wt), (hw, D, wt), (hw, D, z_eave), (-hw, D, z_eave)], gable_mat, WHITE,
                 (0, 1, 0))
        # gable coping following the slopes
        ctx.shell.tube([(xs, y0 - 0.02, z_eave + 0.08), (xs, ry, zr + 0.06), (xs, D + 0.02, zb + 0.08)], 0.06,
                       "concrete_weathered", sides=4, square=True)
    ctx.nap.append(V((hw * 0.3, ry - 0.6, zr - 0.3)))
    return zr


def deco_roof(ctx: P.Ctx, x0, x1, z, depth=0.6, mat="roof_tile_terracotta"):
    """Small decorative pent roof ('mai thai') on a 1990s front parapet."""
    dz = depth * 0.55
    P.roof_plane(ctx, x0, x1, -depth, z, 0.12, z + dz + 0.07, mat, rows=True, row_len=0.2)
    ctx.shell.box((x0, -depth - 0.03, z - 0.18), (x1, -depth + 0.02, z + 0.02), "stucco_detail", WHITE)
    ctx.nap.append(V(((x0 + x1) / 2, -depth / 2, z + dz / 2)))


# ---------------------------------------------------------------------------
# Style: colonial shophouse
# ---------------------------------------------------------------------------
def colonial_facade(ctx: P.Ctx, W, floors, g, f, pal, opts, ground=True):
    """Builds a colonial facade centred at x=0 on y=0. Returns top-of-facade z."""
    rng = ctx.rng
    hw = W / 2
    wall = pal["wall"]
    trim = (*pal["trim"], 1)
    shutter = pal["shutter"]
    H = g + (floors - 1) * f
    pil = 0.32 if W >= 3.9 else 0.24
    bays = opts.get("bays", 2 if W >= 4.4 else (1 if W < 3.8 else 2))
    # --- openings
    holes = []
    gf = []
    if ground:
        gx0, gx1 = -hw + pil + 0.08, hw - pil - 0.08
        if opts.get("ground_split", W >= 5.5):
            mid = 0.0
            gf = [(gx0, 0.18, mid - 0.2, g - 0.6), (mid + 0.2, 0.18, gx1, g - 0.6)]
        else:
            gf = [(gx0, 0.18, gx1, g - 0.55)]
        holes += gf
    win = []
    inner = W - 2 * pil
    for k in range(1, floors):
        zf = g + (k - 1) * f
        ww = min(1.15, inner / bays - 0.45)
        wh = min(2.55, f - 0.75)
        for b in range(bays):
            cx = -hw + pil + inner * (b + 0.5) / bays
            win.append((k, cx, zf + 0.05, ww, wh))
            holes.append((cx - ww / 2, zf + 0.05, cx + ww / 2, zf + 0.05 + wh))
    P.wall_with_holes(ctx.shell, -hw, hw, 0, H, holes, wall, WHITE, depth=0.24, max_cell=0.35)
    ctx.col((-hw, 0, g - 0.5), (hw, 0.24, H), "concrete", ("wall",))
    # rusticated base (plinth) and pilasters
    ctx.shell.box((-hw, -0.03, 0), (hw, 0.001, 0.18), "stucco_detail", mul(trim, 0.8), bevel=0.01, skip=("+y",))
    for xc in (-hw + pil / 2, hw - pil / 2):
        P.pilaster(ctx, xc, pil, 0.18, H - 0.3, wall, mul(WHITE, 0.97), 0.06, capital=True)
        ctx.col((xc - pil / 2, -0.06, 0), (xc + pil / 2, 0.0, H - 0.3), "concrete", ("wall",))
    if W >= 5.5 and opts.get("mid_pilaster", True) and ground and opts.get("ground_split", W >= 5.5):
        P.pilaster(ctx, 0.0, 0.4, 0.18, g - 0.55, wall, WHITE, 0.05, capital=False)
    # floor cornices
    for k in range(1, floors):
        zf = g + (k - 1) * f
        P.cornice(ctx, -hw - 0.04, hw + 0.04, zf - 0.32, "band", "stucco_detail", trim)
    # crown cornice + parapet
    P.cornice(ctx, -hw - 0.06, hw + 0.06, H - 0.3, "classic", "stucco_detail", trim, scale=1.1)
    ph = opts.get("parapet_h", 1.1)
    top = H - 0.3 + 0.29
    para = opts.get("parapet", "balustrade")
    if para == "balustrade":
        ctx.shell.box((-hw, -0.02, top), (hw, 0.22, top + 0.12), "stucco_detail", trim, bevel=0.01)
        nb = int((W - 0.6) / 0.22)
        for i in range(nb):
            bx = -hw + 0.3 + (i + 0.5) * (W - 0.6) / nb
            prof = [(0.045, 0), (0.06, 0.06), (0.04, 0.12), (0.07, 0.3), (0.05, 0.42), (0.035, 0.48),
                    (0.05, 0.52)]
            pts = [(bx, 0.1, top + 0.12 + p[1] * (ph - 0.3) / 0.52) for p in prof]
            ctx.shell.tube(pts, 0.05, "stucco_detail", trim, sides=8, radii=[p[0] for p in prof])
        ctx.shell.box((-hw - 0.03, -0.04, top + ph - 0.18), (hw + 0.03, 0.24, top + ph - 0.06), "stucco_detail",
                      trim, bevel=0.015)
        for xc in (-hw + 0.15, hw - 0.15):
            ctx.shell.box((xc - 0.15, -0.03, top), (xc + 0.15, 0.24, top + ph), wall, WHITE, bevel=0.012)
            ctx.shell.box((xc - 0.18, -0.05, top + ph), (xc + 0.18, 0.26, top + ph + 0.1), "stucco_detail", trim,
                          bevel=0.015)
    else:
        P.wall_with_holes(ctx.shell, -hw, hw, top, top + ph, [], wall, WHITE)
        ctx.shell.box((-hw, 0.0, top), (hw, 0.22, top + ph), wall, WHITE, skip=("-y",))
        ctx.shell.box((-hw + 0.4, -0.025, top + 0.15), (hw - 0.4, 0.001, top + ph - 0.2), "stucco_detail",
                      mul(trim, 0.95), bevel=0.02, skip=("+y",))
        ctx.shell.box((-hw - 0.03, -0.05, top + ph), (hw + 0.03, 0.25, top + ph + 0.1), "stucco_detail", trim,
                      bevel=0.015)
    if opts.get("pediment", True):
        pw = min(2.4, W * 0.5)
        pz = top + ph + 0.1
        prof = [(-pw / 2, 0), (pw / 2, 0), (0, 0.6)]
        ctx.shell.box((-pw / 2, -0.06, pz - 0.1), (pw / 2, 0.2, pz), "stucco_detail", trim, bevel=0.01)
        P.quad_n(ctx.shell, [(-pw / 2, -0.06, pz), (pw / 2, -0.06, pz), (0, -0.06, pz + 0.55), (0, -0.06, pz + 0.55)],
                 wall, WHITE, (0, -1, 0))
        P.quad_n(ctx.shell, [(-pw / 2, 0.2, pz), (pw / 2, 0.2, pz), (0, 0.2, pz + 0.55), (0, 0.2, pz + 0.55)],
                 wall, WHITE, (0, 1, 0))
        ctx.shell.tube([(-pw / 2 - 0.05, -0.08, pz), (0, -0.08, pz + 0.6), (pw / 2 + 0.05, -0.08, pz)], 0.05,
                       "stucco_detail", trim, sides=4, square=True)
        # year medallion
        ctx.shell.cylinder((0, -0.07, pz + 0.22), (0, 1, 0), 0.14, 0.02, "stucco_detail", trim, sides=16)
    ctx.col((-hw, -0.05, top), (hw, 0.25, top + ph + 0.1), "concrete")
    ctx.nap.append(V((-hw + 0.15, 0.1, top + ph + 0.1)))
    # --- ground floor shopfront
    if ground:
        aw_z = g - 0.45
        kinds = opts.get("shops", ["rattan"])
        for i, (x0, z0, x1, z1) in enumerate(gf):
            kind = kinds[i % len(kinds)]
            P.shop_interior(ctx, x0, x1, z0, z1, rng.uniform(2.0, 3.0), kind)
            if opts.get("folding_doors", True):
                # folded wooden doors stacked at both jambs (the old 'cua xep')
                for side in (0, 1):
                    xs = x0 if side == 0 else x1
                    for k in range(3):
                        off = (0.045 * k + 0.02) * (1 if side == 0 else -1)
                        ctx.detail.box((xs + off - 0.02, 0.02 + k * 0.05, z0), (xs + off + 0.02, 0.2, z1 - 0.05),
                                       shutter, WHITE, uvmode="grain_v")
            if opts.get("shutter") is not None:
                P.rolling_shutter(ctx, x0, x1, z0, z1, opts["shutter"], -0.0)
            # transom + sign above opening
            if i == 0 and opts.get("sign"):
                P.sign_board(ctx, gf[0][0] + 0.1, gf[-1][2] - 0.1, z1 + 0.05, aw_z - 0.08, opts["sign"], 0.0,
                             0.06, (0.2, 0.2, 0.2, 1))
        if "rattan" in kinds:
            P.rattan_display(ctx, gf[0][0] + 0.1, gf[-1][2] - 0.1, aw_z - 0.2, 0.0, 0.55)
        if opts.get("awning", "tile") == "tile":
            P.awning_tile(ctx, -hw + 0.02, hw - 0.02, aw_z, rng.uniform(0.9, 1.15), 20)
        elif opts.get("awning") == "canvas":
            P.awning_canvas(ctx, gf[0][0], gf[-1][2], aw_z - 0.1, 1.2, rng.choice(CANVAS))
        # base pier clutter
        P.meter_cluster(ctx, -hw + pil + 0.45, 1.65, -0.0, n=rng.choice([2, 3, 4])) if W > 3.8 and rng.random() < 0.7 \
            else None
        P.cable_run(ctx, -hw + 0.05, hw - 0.05, g - 0.25, -0.06 * 0, n=rng.randint(4, 8), sag=0.07,
                    drops=[(-hw + pil + 0.45, 2.2)])
        P.house_number(ctx, hw - pil - 0.3, 2.6, rng.choice(["no_14", "no_18", "no_23", "no_27", "no_9"]))
        P.decal(ctx, "moss_base", 0, 0.7, W, 0.7, -0.0045)
        P.decal(ctx, "splash_base", -hw + 0.4, 0.9, 1.0, 0.9, -0.004)
    # --- upper floors
    for k in range(1, floors):
        zf = g + (k - 1) * f
        fw = [w for w in win if w[0] == k]
        balcony = (k == 1 and opts.get("balcony1", True)) or (k > 1 and opts.get("balcony_upper", False))
        for (_, cx, z, ww, wh) in fw:
            state = rng.choice(["open", "open", "half", "closed"])
            P.french_window(ctx, cx, z, ww, wh, shutter, state, 0.0, 0.14, trim, hood="cornice" if k > 1 or
                            not balcony else "cornice", sill=not balcony)
            if not balcony:
                # balconette: shallow wrought-iron guard
                P.balcony_slab(ctx, cx - ww / 2 - 0.15, cx + ww / 2 + 0.15, z, 0.3, 0.1, "stucco_detail",
                               edge_tint=trim, corbels=2, corbel_tint=trim)
                P.railing_wrought(ctx, cx - ww / 2 - 0.12, cx + ww / 2 + 0.12, -0.28, z, 0.9, sides=0.27)
                if rng.random() < 0.6:
                    P.potted_plant(ctx, cx + rng.uniform(-0.3, 0.3), -0.15, z + 0.02, 0.4,
                                   pot=rng.choice(["terracotta", "blue"]))
        if balcony:
            proj = opts.get("balcony_proj", 0.85)
            P.balcony_slab(ctx, -hw + pil + 0.02, hw - pil - 0.02, zf, proj, 0.16, "stucco_detail", edge_tint=trim,
                           corbels=3 if W > 4.4 else 2, corbel_tint=trim)
            P.railing_wrought(ctx, -hw + pil + 0.05, hw - pil - 0.05, -proj + 0.04, zf + 0.015, 1.0,
                              style=rng.randint(0, 1), sides=proj - 0.06)
            ctx.nap.append(V((rng.uniform(-hw + 0.8, hw - 0.8), -proj * 0.5, zf + 0.02)))
            if rng.random() < 0.7:
                P.bougainvillea_cascade(ctx, rng.uniform(-hw + pil, -0.4), rng.uniform(0.2, hw - pil), zf + 1.05,
                                        -proj, rng.uniform(1.0, 2.2))
            for q in range(rng.randint(1, 3)):
                P.potted_plant(ctx, rng.uniform(-hw + pil + 0.3, hw - pil - 0.3), -proj + 0.25, zf + 0.02,
                               rng.uniform(0.35, 0.6), pot=rng.choice(["terracotta", "blue", "white"]))
            if rng.random() < 0.5:
                P.laundry_line(ctx, (-hw + pil + 0.1, -proj + 0.1, zf + 1.9), (hw - pil - 0.1, -proj + 0.12, zf + 1.85),
                               density=0.6)
        # AC condenser: standing on the balcony floor against the wall (colonial facades leave no wall
        # space between the tall windows), or hung on the outer face of a pilaster on wide facades
        if rng.random() < opts.get("ac_prob", 0.6) and fw:
            if balcony:
                side = rng.choice([-1, 1])
                P.ac_unit(ctx, side * (hw - pil - 0.48), zf + 0.06, 0.0, bracket=False, pipe_side=-side, drip=False)
            elif W >= 5.5:
                P.ac_unit(ctx, 0.0, zf + 1.2, -0.06, pipe_side=1)
        if rng.random() < 0.5:
            P.decal(ctx, "water_stain", rng.uniform(-hw + 0.6, hw - 0.6), zf + f - 0.4, 1.4, 1.2)
    # grime streaks under the crown cornice and posters on the ground piers
    for _ in range(rng.randint(2, 4)):
        P.decal(ctx, rng.choice(["streak_0", "streak_1", "streak_2"]), rng.uniform(-hw + 0.5, hw - 0.5), H - 0.3,
                rng.uniform(0.6, 1.4), rng.uniform(1.2, 2.6))
    if ground and rng.random() < 0.7:
        P.decal(ctx, rng.choice(["poster_0", "poster_1", "ad_stencil"]), -hw + pil / 2 + 0.02, 1.9, 0.32, 0.4, -0.065)
    if rng.random() < 0.6:
        P.decal(ctx, "peel_patch", rng.uniform(-hw + 0.5, hw - 0.5), rng.uniform(2.5, H - 1), 0.9, 0.9)
    # drainpipe down one pilaster
    P.drainpipe(ctx, (hw - pil / 2) * rng.choice([-1, 1]), 0.0, H - 0.35, -0.06, rng.choice(["plastic", "metal_painted"]),
                rng.choice([(0.75, 0.75, 0.72, 1), (0.35, 0.3, 0.28, 1)]))
    return top + ph


def build_colonial(spec):
    pal = PAL[spec["palette"]]
    W, D, floors = spec["width"], spec["depth"], spec["floors"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    g, f = spec.get("g", 4.0), spec.get("f", 3.6)
    H = g + (floors - 1) * f
    top = colonial_facade(ctx, W, floors, g, f, pal, spec.get("opts", {}))
    side_and_back(ctx, W, D, H - 0.3, pal["side"], pal["wall"], WHITE)
    # roof: slab behind the parapet + pitched tile roof over the back part
    roof_flat(ctx, W, 2.4, H - 0.3, 0.0, clutter=False, front_parapet=False)
    zr = roof_pitched(ctx, W, D, H - 0.3 + 0.15, 26, pal["roof"], y0=2.4, back_eave=0.35, wall_top=H - 0.3)
    # gutter between parapet terrace and roof slope + walkable terrace behind parapet
    ctx.nap.append(V((0.0, 1.2, H - 0.3 + 0.02)))
    if ctx.rng.random() < 0.6:
        P.water_tank(ctx, -W / 2 + 1.0, 1.2, H - 0.3, "vertical")
    if ctx.rng.random() < 0.5:
        P.potted_plant(ctx, W / 2 - 0.6, 0.7, H - 0.28, 0.5, pot="terracotta")
    return ctx, dict(height=max(top, zr), floors=floors)


def build_corner(spec):
    """Colonial corner building: front facade (W) + side facade along +X with a chamfered corner."""
    pal = PAL[spec["palette"]]
    W, D, floors = spec["width"], spec["depth"], spec["floors"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    g, f = spec.get("g", 4.0), spec.get("f", 3.6)
    H = g + (floors - 1) * f
    ch = 1.2
    opts = dict(spec.get("opts", {}))
    # front facade (shortened by the chamfer)
    Wf = W - ch
    mk = ctx.mark()
    colonial_facade(ctx, Wf, floors, g, f, pal, dict(opts, pediment=False))
    ctx.xform_since(mk, Matrix.Translation((-ch / 2, 0, 0)))
    # chamfer facade: 45 degrees, entrance door + balconette windows
    mk = ctx.mark()
    cw = ch * math.sqrt(2)
    colonial_facade(ctx, cw, floors, g, f, pal, dict(opts, bays=1, pediment=True, sign=None, shops=["cafe"],
                                                     awning="canvas", balcony1=False, parapet="solid",
                                                     ground_split=False, ac_prob=0.0, folding_doors=False))
    ctx.xform_since(mk, Matrix.Translation((W / 2 - ch / 2, ch / 2, 0)) @ Matrix.Rotation(math.radians(45), 4, "Z"))
    # side facade along +X
    Ls = D - ch
    mk = ctx.mark()
    colonial_facade(ctx, Ls, floors, g, f, pal, dict(opts, bays=max(2, int(Ls / 2.4)), pediment=False,
                                                     sign=opts.get("sign2"), shops=["tailor", "home"],
                                                     ground_split=True, balcony1=True))
    ctx.xform_since(mk, Matrix.Translation((W / 2, ch + Ls / 2, 0)) @ Matrix.Rotation(math.radians(90), 4, "Z"))
    # left party wall + back wall
    sh = ctx.shell
    P.plain_wall(sh, (-W / 2, 0, 0), (0, 1, 0), D, H - 0.3, pal["side"], WHITE, (-1, 0, 0), 0.6)
    ctx.col((-W / 2, 0, 0), (-W / 2 + 0.2, D, H), "concrete", ("wall",))
    P.plain_wall(sh, (-W / 2, D, 0), (1, 0, 0), W, H - 0.3, pal["side"], WHITE, (0, 1, 0), 0.6)
    ctx.col((-W / 2, D - 0.2, 0), (W / 2, D, H), "concrete", ("wall",))
    # roof: flat terrace with tank & laundry (corner roofs are terraces)
    zt = roof_flat(ctx, W, D, H - 0.3, 0.0, clutter=True, front_parapet=False, tum=True)
    return ctx, dict(height=H + 1.2, floors=floors)


# ---------------------------------------------------------------------------
# Style: 1990s tube house
# ---------------------------------------------------------------------------
def build_tube90s(spec):
    pal = PAL[spec["palette"]]
    W, D, floors = spec["width"], spec["depth"], spec["floors"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    rng = ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    geo = random.Random(spec["seed"])
    opts = spec.get("opts", {})
    g, f = spec.get("g", 3.7), spec.get("f", 3.3)
    H = g + (floors - 1) * f
    hw = W / 2
    wall, tile, metal = pal["wall"], pal["tile"], pal["metal"]
    sh = ctx.shell
    pier = 0.22
    proj = opts.get("proj", geo.choice([0.9, 1.0, 1.2]))
    # floor plan of the facade: per upper floor 'balcony' or 'cage'
    kinds = opts.get("floors_kind") or [geo.choice(["balcony", "balcony", "cage"]) for _ in range(floors - 1)]
    holes = []
    gx0, gx1 = -hw + pier, hw - pier
    holes.append((gx0, 0.15, gx1, g - 0.45))
    fl = []
    for k in range(1, floors):
        zf = g + (k - 1) * f
        kind = kinds[k - 1]
        if kind == "balcony":
            dw = min(W - 1.0, 2.6)
            holes.append((-dw / 2, zf, dw / 2, zf + 2.45))
            fl.append((k, zf, kind, (-dw / 2, zf, dw / 2, zf + 2.45)))
        else:
            ww = min(W - 1.2, 2.0)
            holes.append((-ww / 2, zf + 0.9, ww / 2, zf + 2.4))
            fl.append((k, zf, kind, (-ww / 2, zf + 0.9, ww / 2, zf + 2.4)))
    P.wall_with_holes(sh, -hw, hw, 0, H, holes, wall, WHITE, depth=0.22, max_cell=0.35)
    ctx.col((-hw, 0, g - 0.45), (hw, 0.22, H), "concrete", ("wall",))
    # ground floor: tiled piers + header band
    for xs in (-hw, hw - pier):
        sh.box((xs, -0.02, 0), (xs + pier, 0.001, g - 0.45), tile, WHITE, bevel=0.005, skip=("+y",))
        ctx.col((xs, -0.02, 0), (xs + pier, 0.22, g - 0.45), "tile", ("wall",))
    shop = opts.get("shop", "grocery")
    P.shop_interior(ctx, gx0, gx1, 0.15, g - 0.45, rng.uniform(2.2, 3.2), shop)
    sfrac = opts.get("shutter", rng.choice([1.0, 1.0, 0.45, 0.0]))
    P.rolling_shutter(ctx, gx0, gx1, 0.15, g - 0.45, sfrac)
    if sfrac < 0.6:
        ctx.entr.append(V((0, -0.2, 0.15)))
    # balconies / cages per floor
    for (k, zf, kind, (x0, z0, x1, z1)) in fl:
        if kind == "balcony":
            P.balcony_slab(ctx, -hw, hw, zf, proj, 0.15, "concrete_weathered", edge_mat=tile, floor_mat="terrazzo")
            # wing walls (party walls continue to the balcony front)
            for xs in (-hw, hw - 0.1):
                sh.box((xs, -proj, zf), (xs + 0.1, 0.001, zf + f - 0.15), wall, WHITE, bevel=0.008, skip=("+y",))
                ctx.col((xs, -proj, zf), (xs + 0.1, 0.0, zf + f - 0.15), "concrete", ("wall",))
            # front: low tiled wall + railing or full cage
            btype = opts.get("balcony_types", {}).get(k) or geo.choice(["cage", "cage", "rail", "rail", "glass",
                                                                         "solid"])
            if btype == "solid":
                P.masonry_parapet(ctx, -hw + 0.1, hw - 0.1, -proj, -proj + 0.12, zf, 1.0, tile, WHITE, "granite_red",
                                  "tile")
                for q in range(rng.randint(2, 4)):
                    P.potted_plant(ctx, rng.uniform(-hw + 0.4, hw - 0.4), -proj + 0.06, zf + 1.06,
                                   rng.uniform(0.3, 0.45), pot=rng.choice(["terracotta", "blue"]))
                ctx.nap.append(V((0.0, -proj + 0.06, zf + 1.06)))
            else:
                P.masonry_parapet(ctx, -hw + 0.1, hw - 0.1, -proj, -proj + 0.12, zf, 0.5 if btype != "glass" else 0.9,
                                  tile, WHITE, "granite_red", "tile")
            if btype == "cage":
                P.grille(ctx, -hw + 0.1, zf + 0.55, hw - 0.1, zf + f - 0.2, -proj + 0.06, metal,
                         geo.choice(["bars_h", "bars_h", "bars", "diamond"]), 0.016)
            elif btype == "rail":
                P.railing_steel(ctx, -hw + 0.12, hw - 0.12, -proj + 0.06, zf + 0.55, 0.55, metal,
                                stainless=geo.random() < 0.4)
            elif btype == "glass":
                P.alu_window(ctx, -hw + 0.1, zf + 0.95, hw - 0.1, zf + f - 0.2, -proj - 0.02, 0.1,
                             (0.85, 0.86, 0.86, 1), panes=4 if W > 4 else 3, sill=False)
            P.alu_window(ctx, x0, z0, x1, z1, 0.0, 0.1, (0.82, 0.83, 0.84, 1), panes=4 if x1 - x0 > 2 else 2,
                         sill=False)
            # life on the balcony
            if rng.random() < 0.7:
                P.laundry_line(ctx, (-hw + 0.15, -proj + 0.25, zf + 2.0), (hw - 0.15, -proj + 0.3, zf + 1.95))
            for q in range(rng.randint(1, 4)):
                P.potted_plant(ctx, rng.uniform(-hw + 0.35, hw - 0.35), -proj + 0.3, zf + 0.02,
                               rng.uniform(0.35, 0.65), pot=rng.choice(["terracotta", "styro", "blue", "white"]))
            if rng.random() < 0.35:
                P.bougainvillea_cascade(ctx, -hw + 0.2, rng.uniform(-0.3, hw - 0.2), zf + 0.6, -proj - 0.02,
                                        rng.uniform(1.0, 2.0))
            if rng.random() < 0.75:
                # AC condenser hung on the wing wall or standing on the balcony
                P.ac_unit(ctx, hw - 0.62 if rng.random() < 0.5 else -hw + 0.62, zf + 2.55, -proj + 0.38,
                          drip=False)
            if btype == "rail":  # cats squeeze through a 12 cm rail: the balcony floor is a nap spot
                ctx.nap.append(V((rng.uniform(-hw + 0.5, hw - 0.5), -proj * 0.45, zf + 0.02)))
        else:
            P.alu_window(ctx, x0, z0, x1, z1, 0.0, 0.12, (0.82, 0.83, 0.84, 1), panes=2)
            P.grille(ctx, x0 - 0.08, z0 - 0.1, x1 + 0.08, z1 + 0.08, 0.0, metal, rng.choice(["sun", "diamond", "bars_h"]),
                     0.016, proj=0.45)
            sh.box((x0 - 0.15, -0.5, z1 + 0.25), (x1 + 0.15, 0.001, z1 + 0.33), "concrete_weathered", WHITE,
                   bevel=0.01)  # window hood slab
            ctx.col((x0 - 0.15, -0.5, z1 + 0.25), (x1 + 0.15, 0.0, z1 + 0.33), "concrete")
            ctx.ledge(x0 - 0.15, x1 + 0.15, -0.5, z1 + 0.25, 1.0)
            if rng.random() < 0.65:
                P.ac_unit(ctx, (x1 + 0.5) if x1 + 0.9 < hw else -hw + 0.55, zf + 0.9, 0.0)
            if rng.random() < 0.5:
                P.potted_plant(ctx, (x0 + x1) / 2 + rng.uniform(-0.4, 0.4), -0.25, z0 - 0.08, 0.4)
        # tiled spandrel band under each slab (typical 90s detail)
        if kind == "balcony":
            sh.box((-hw + 0.1, -0.012, zf - 0.6), (hw - 0.1, 0.001, zf - 0.15), tile, WHITE, skip=("+y",))
    # sign on the first floor balcony front / header
    sign = opts.get("sign")
    if sign:
        first = fl[0] if fl else None
        if first and first[2] == "balcony":
            P.sign_board(ctx, -hw + 0.15, hw - 0.15, g - 0.95, g + 0.42, sign, -proj, 0.06, lit=opts.get("lit", False))
        else:
            P.sign_board(ctx, -hw + 0.15, hw - 0.15, g - 0.42, g + 0.55, sign, 0.0, 0.1, lit=opts.get("lit", False))
    if opts.get("vsign"):
        P.vsign(ctx, hw - 0.35, g + f + 0.5, opts["vsign"], 0.0 if fl[1][2] != "balcony" else -proj, 0.55)
    # top: front parapet (+ optional decorative tile roof), roof terrace
    P.cornice(ctx, -hw, hw, H - 0.1, "drip", "concrete_weathered", WHITE)
    if fl and fl[-1][2] == "balcony":
        # top balcony gets a roof canopy slab
        sh.box((-hw, -proj, H - 0.2), (hw, 0.001, H), "concrete_weathered", WHITE, bevel=0.01)
        ctx.col((-hw, -proj, H - 0.2), (hw, 0.0, H), "concrete")
        ctx.ledge(-hw, hw, -proj, H - 0.2, 1.0)
    zt = roof_flat(ctx, W, D, H, 1.05, wall, WHITE, clutter=True, tum=True, rail=geo.random() < 0.3)
    if opts.get("deco_roof", geo.random() < 0.6):
        deco_roof(ctx, -hw + 0.05, hw - 0.05, H + 0.75, 0.55, pal["deco_roof"])
    side_and_back(ctx, W, D, H, pal["side"], "cement_render", WHITE)
    # utilities on the front
    P.cable_run(ctx, -hw + 0.05, hw - 0.05, g - 0.1, -proj - 0.02 if fl and fl[0][2] == "balcony" else 0.0,
                n=rng.randint(5, 9), sag=0.1, drops=[(-hw + 0.1, 1.4)])
    P.meter_cluster(ctx, -hw + pier + 0.3, 1.5, 0.0, n=2) if W >= 4 else None
    px = (hw - 0.06) * (1 if rng.random() < 0.5 else -1)
    first_bal = fl and fl[0][2] == "balcony"
    yb = -proj - 0.07 if first_bal else -0.09
    path = [(px, 0.05, H + 0.95), (px, yb + 0.05, H + 0.85), (px, yb, H + 0.7)]
    if first_bal:
        path += [(px, yb, g - 0.25), (px, yb * 0.5, g - 0.45), (px, -0.09, g - 0.65), (px, -0.09, 0.2)]
    else:
        path += [(px, yb, 0.2)]
    P.drainpipe_path(ctx, path, "plastic", rng.choice([(0.78, 0.78, 0.76, 1), (0.55, 0.57, 0.6, 1)]))
    P.decal(ctx, "moss_base", 0, 0.5, W, 0.5, -0.025)
    for _ in range(rng.randint(2, 4)):
        P.decal(ctx, rng.choice(["streak_0", "streak_1", "streak_2", "soot_top"]), rng.uniform(-hw + 0.5, hw - 0.5),
                rng.choice([g - 0.45, H - 0.15]), rng.uniform(0.7, 1.4), rng.uniform(1.0, 2.2))
    if rng.random() < 0.6:
        P.decal(ctx, rng.choice(["ad_stencil", "poster_0", "poster_1", "no_dumping"]), -hw + pier / 2, 2.1, 0.22, 0.3,
                -0.025)
    P.house_number(ctx, hw - pier / 2, 2.7, rng.choice(["no_31", "no_40", "no_52", "no_61", "no_6"]), -0.022)
    return ctx, dict(height=H + 1.1, floors=floors)


# ---------------------------------------------------------------------------
# Style: modern narrow house
# ---------------------------------------------------------------------------
def build_modern(spec):
    pal = PAL[spec["palette"]]
    W, D, floors = spec["width"], spec["depth"], spec["floors"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    rng = ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    opts = spec.get("opts", {})
    g, f = spec.get("g", 3.8), spec.get("f", 3.4)
    H = g + (floors - 1) * f
    hw = W / 2
    sh = ctx.shell
    wt = (*pal["wall_tint"], 1)
    acp = pal["acp"]
    frame = 0.3
    fin_w = 0.7 if W >= 4.5 else 0.5
    fin_side = rng.choice([-1, 1])
    # deep frame: outer white render frame (sides + top), recessed glass box per floor
    gx0, gx1 = -hw + frame, hw - frame
    holes = [(gx0, 0.15, gx1, g - 0.4)]
    for k in range(1, floors):
        zf = g + (k - 1) * f
        holes.append((gx0, zf, gx1, zf + f - 0.35))
    P.wall_with_holes(sh, -hw, hw, 0, H + 0.9, holes, pal["wall"], wt, depth=0.6, max_cell=0.4,
                      reveal_mat=pal["wall"])
    ctx.col((-hw, 0, g - 0.4), (hw, 0.25, H + 0.9), "concrete", ("wall",))
    # ACP fin panel running the height
    fx = (hw - frame - fin_w / 2) * fin_side
    sh.box((fx - fin_w / 2, -0.35, g - 0.4), (fx + fin_w / 2, -0.05, H + 0.9), "acp_panel", acp, bevel=0.006)
    for k in range(int((H + 1.3 - g) / 1.2)):
        zz = g - 0.4 + k * 1.2
        sh.box((fx - fin_w / 2 - 0.001, -0.351, zz), (fx + fin_w / 2 + 0.001, -0.06, zz + 0.008), "dark")
    ctx.col((fx - fin_w / 2, -0.35, g - 0.4), (fx + fin_w / 2, 0.0, H + 0.9), "metal", ("wall",))
    shop = opts.get("shop", "phones")
    P.shop_interior(ctx, gx0, gx1, 0.15, g - 0.4, rng.uniform(2.5, 3.5), shop, wall_y=0.6, floor_mat="granite_red")
    if opts.get("garage"):
        P.rolling_shutter(ctx, gx0, gx1, 0.15, g - 0.4, opts.get("shutter", 0.0), 0.55, (0.55, 0.56, 0.58, 1))
    else:
        P.alu_window(ctx, gx0, 0.15, gx1, g - 0.4, 0.55, 0.05, (0.15, 0.15, 0.16, 1), panes=3, sill=False,
                     dark_frame=True, lit=False)
    for k in range(1, floors):
        zf = g + (k - 1) * f
        gx = (gx0, gx1)
        y_glass = 0.45
        P.alu_window(ctx, gx[0] + 0.05, zf + 0.05, gx[1] - 0.05, zf + f - 0.4, y_glass - 0.1, 0.1,
                     (0.15, 0.15, 0.16, 1), panes=3 if W > 4.5 else 2, sill=False, dark_frame=True)
        sh.box((gx0, -0.0, zf - 0.2), (gx1, y_glass, zf + 0.05), "terrazzo", WHITE)  # balcony floor
        ctx.col((gx0, 0.0, zf - 0.2), (gx1, y_glass, zf + 0.05), "tile")
        P.railing_glass(ctx, gx0 + 0.02, gx1 - 0.02, 0.03, zf + 0.05, 1.05)
        # planter trough on the frame
        if rng.random() < 0.75:
            sh.box((gx0 + 0.05, -0.32, zf - 0.35), (gx1 - 0.05, 0.0, zf + 0.0), "render_modern", wt, bevel=0.01)
            ctx.col((gx0 + 0.05, -0.32, zf - 0.35), (gx1 - 0.05, 0.0, zf + 0.0), "concrete")
            for q in range(int((gx1 - gx0) / 0.5)):
                P.foliage_card(ctx, gx0 + 0.3 + q * 0.5, -0.16, zf - 0.05, 0.6, rng.uniform(0.4, 0.7),
                               rng.choice(["leafy", "fern"]), rng.uniform(0, 180))
            if rng.random() < 0.5:
                P.foliage_card(ctx, gx0 + rng.uniform(0.3, 1.0), -0.3, zf - 1.2, 0.5, 1.2, "vine", 0)
        if rng.random() < 0.6:
            P.ac_unit(ctx, -fin_side * (hw - frame - 0.5), zf + f - 1.1, -0.0, pipe_side=fin_side, drip=True)
        ctx.ledge(-hw, hw, 0.0, zf - 0.2, 0.7)
    # vertical wood/alu louvres on top floor
    if opts.get("louvres", True):
        zf = g + (floors - 2) * f
        n = int((gx1 - gx0) / 0.12)
        for i in range(n):
            x = gx0 + (i + 0.5) * (gx1 - gx0) / n
            ctx.detail.box((x - 0.02, -0.1, zf + 1.2), (x + 0.02, -0.02, zf + f - 0.35), "wood_brown",
                           (1.3, 1.1, 0.9, 1), uvmode="grain_v")
    if opts.get("sign"):
        P.sign_board(ctx, gx0, gx1, g - 0.4, g + 0.25, opts["sign"], 0.0, 0.05, (0.1, 0.1, 0.1, 1))
    sh.box((-hw, -0.05, H + 0.9), (hw, 0.6, H + 1.0), "concrete_weathered", WHITE, bevel=0.01)
    zt = roof_flat(ctx, W, D, H, 1.0, pal["wall"], wt, clutter=True, tum=True, front_parapet=False, style="mod")
    # pergola on the roof
    if rng.random() < 0.6:
        for i in range(int(W / 0.4)):
            x = -hw + 0.2 + i * 0.4
            ctx.clutter.box((x - 0.03, 0.6, H + 2.4), (x + 0.03, 3.2, H + 2.5), "wood_brown", WHITE, uvmode="grain_h")
        for x in (-hw + 0.25, hw - 0.25):
            ctx.clutter.box((x - 0.05, 3.0, H), (x + 0.05, 3.1, H + 2.4), "metal_painted", (0.15, 0.15, 0.15, 1))
        ctx.clutter.box((-hw + 0.2, 3.0, H + 2.3), (hw - 0.2, 3.1, H + 2.4), "metal_painted", (0.15, 0.15, 0.15, 1))
        ctx.col((-hw + 0.2, 0.6, H + 2.4), (hw - 0.2, 3.2, H + 2.5), "wood")
    side_and_back(ctx, W, D, H, pal["side"], "render_modern", wt)
    P.drainpipe(ctx, -fin_side * (hw - 0.12), 0.0, H + 0.8, -0.0, "plastic", (0.3, 0.3, 0.3, 1), offset=0.06)
    P.decal(ctx, "splash_base", 0, 0.6, W, 0.6, -0.004)
    for _ in range(rng.randint(1, 3)):
        P.decal(ctx, "streak_2", rng.uniform(-hw + 0.3, hw - 0.3), H + 0.9, rng.uniform(0.4, 0.9), rng.uniform(1.0, 2.0))
    return ctx, dict(height=H + 1.0, floors=floors)


# ---------------------------------------------------------------------------
# Style: old single-storey tile-roof house
# ---------------------------------------------------------------------------
def build_oldtile(spec):
    pal = PAL[spec["palette"]]
    W, D = spec["width"], spec["depth"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    rng = ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    opts = spec.get("opts", {})
    hw = W / 2
    sh = ctx.shell
    he = opts.get("eave", 3.3)
    wall = pal["wall"]
    # front wall with doors/windows
    holes = []
    shop = opts.get("shop")
    if shop:
        holes.append((-hw + 0.35, 0.3, hw - 0.35, he - 0.55))
    else:
        dw = min(1.8, W - 1.6)
        holes.append((-dw / 2 - 0.4, 0.3, dw / 2 - 0.4, 2.45))
        holes.append((hw - 0.95, 1.1, hw - 0.3, 2.1))
    P.wall_with_holes(sh, -hw, hw, 0, he, holes, wall, WHITE, depth=0.25, max_cell=0.35)
    ctx.col((-hw, 0, 0), (hw, 0.25, he), "concrete", ("wall",))
    # raised plinth + steps
    sh.box((-hw, -0.06, 0), (hw, 0.001, 0.3), "cement_render", mul(WHITE, 0.8), bevel=0.01, skip=("+y",))
    sh.box((-hw + 0.3, -0.55, 0), (hw - 0.3, -0.06, 0.15), "concrete_weathered", WHITE, bevel=0.015)
    ctx.col((-hw + 0.3, -0.55, 0), (hw - 0.3, 0.0, 0.15), "concrete")
    ctx.ledge(-hw, hw, -0.06, 0.3, 0.6)
    if shop:
        x0, z0, x1, z1 = holes[0]
        P.shop_interior(ctx, x0, x1, z0, z1, rng.uniform(2.2, 3.0), shop)
        # wooden plank doors stacked at one side (cua lua)
        for k in range(4):
            ctx.detail.box((x1 - 0.04 - k * 0.035, 0.02 + k * 0.03, z0), (x1 - 0.005 - k * 0.035, 0.24, z1 - 0.02),
                           pal["door"], WHITE, uvmode="grain_v")
        if opts.get("sign"):
            P.sign_board(ctx, x0 + 0.05, x1 - 0.05, z1 + 0.04, he - 0.06, opts["sign"], 0.0, 0.05)
    else:
        x0, z0, x1, z1 = holes[0]
        P.door_wood_panel(ctx, x0, z0, x1, z1, pal["door"], 0.0, 0.14, leaves=4, open_frac=rng.choice([0, 0.6, 1.0]))
        ctx.entr.append(V(((x0 + x1) / 2, -0.3, 0.3)))
        wx0, wz0, wx1, wz1 = holes[1]
        frame_t = pal["door"]
        P.frame_rect(ctx.detail, wx0, wz0, wx1, wz1, 0.06, 0.14, 0.06, frame_t)
        for i in range(5):
            x = wx0 + 0.06 + (i + 0.5) * (wx1 - wx0 - 0.12) / 5
            ctx.detail.box((x - 0.018, 0.08, wz0), (x + 0.018, 0.12, wz1), frame_t, WHITE, uvmode="grain_v")
        P.glass_pane(ctx, wx0 + 0.06, wz0 + 0.06, wx1 - 0.06, wz1 - 0.06, 0.15, "dark_room")
        sh.box((wx0 - 0.08, -0.06, wz0 - 0.06), (wx1 + 0.08, 0.06, wz0), "concrete_weathered", WHITE, bevel=0.01)
        ctx.col((wx0 - 0.08, -0.06, wz0 - 0.06), (wx1 + 0.08, 0.25, wz0), "concrete")
        P.potted_plant(ctx, hw - 0.4, -0.3, 0.15, 0.55, pot="terracotta")
        P.potted_plant(ctx, -hw + 0.35, -0.3, 0.15, 0.45, pot="blue")
        P.wall_altar(ctx, x1 + 0.35 if x1 + 0.6 < hw - 0.9 else x0 - 0.35, 1.55, 0.0)
        ctx.nap.append(V((0.0, -0.35, 0.15)))
    # eave: wooden plate + exposed rafter ends
    sh.box((-hw - 0.02, -0.12, he - 0.25), (hw + 0.02, 0.001, he), "wood_brown", WHITE, uvmode="grain_h", skip=("+y",))
    eave = opts.get("overhang", 0.65)
    pitch = opts.get("pitch", 30)
    zr = roof_pitched(ctx, W, D, he, pitch, pal["roof"], y0=0.0, front_eave=eave, back_eave=0.3,
                      gable_mat=pal["side"], ridge_y=D * 0.5)
    ry = D * 0.5
    for xs, sg in ((-hw, -1), (hw, 1)):
        pts = [(xs - sg * 0.25, ry, zr + 0.08), (xs, ry, zr + 0.12), (xs + sg * 0.12, ry, zr + 0.22),
               (xs + sg * 0.1, ry, zr + 0.34), (xs + sg * 0.0, ry, zr + 0.38)]
        ctx.shell.tube(pts, 0.07, "cement_render", (0.75, 0.74, 0.7, 1), sides=8, radii=[0.1, 0.09, 0.07, 0.05, 0.03])
    nr = int(W / 0.45)
    for i in range(nr):
        x = -hw + (i + 0.5) * W / nr
        # rafter: built horizontal from the wall out past the eave, then pitched down under the tiles
        L = eave / math.cos(math.radians(pitch)) - 0.03
        ctx.detail.box((x - 0.035, -L, he - 0.06 - 0.08), (x + 0.035, 0.0, he - 0.06), "wood_brown", WHITE,
                       xform=G.rot_x(pitch, (x, 0, he - 0.06)), uvmode="grain_h")
    P.decal(ctx, "soot_top", 0, he - 0.2, W, 0.9, -0.004)
    P.decal(ctx, "moss_base", 0, 0.75, W, 0.75, -0.065)
    sh2 = ctx.shell
    P.plain_wall(sh2, (-hw, 0, 0), (0, 1, 0), D, he, pal["side"], WHITE, (-1, 0, 0), 0.6)
    P.plain_wall(sh2, (hw, 0, 0), (0, 1, 0), D, he, pal["side"], WHITE, (1, 0, 0), 0.6)
    P.plain_wall(sh2, (-hw, D, 0), (1, 0, 0), W, he, pal["side"], WHITE, (0, 1, 0), 0.6)
    ctx.col((-hw, 0, 0), (-hw + 0.2, D, he), "concrete", ("wall",))
    ctx.col((hw - 0.2, 0, 0), (hw, D, he), "concrete", ("wall",))
    ctx.col((-hw, D - 0.2, 0), (hw, D, he), "concrete", ("wall",))
    P.cable_run(ctx, -hw + 0.05, hw - 0.05, he - 0.35, -0.0, n=rng.randint(3, 6), sag=0.06,
                drops=[(hw - 0.2, 1.8)])
    zg = he - math.tan(math.radians(pitch)) * eave - 0.06
    ctx.clutter.tube([(-hw + 0.05, -eave - 0.05, zg), (hw - 0.05, -eave - 0.05, zg)], 0.06, "metal_painted",
                     (0.5, 0.5, 0.48, 1), sides=8)  # eave gutter
    gx = (-hw + 0.25) if rng.random() < 0.5 else (hw - 0.25)
    P.drainpipe_path(ctx, [(gx, -eave - 0.05, zg), (gx, -eave * 0.5, zg - 0.25), (gx, -0.1, zg - 0.5),
                           (gx, -0.1, 0.35)], "metal_painted", (0.4, 0.38, 0.35, 1))
    if rng.random() < 0.6:
        P.ac_unit(ctx, -hw + 0.6, he - 1.05, 0.0, w=0.7, h=0.5, pipe_up=0.25)
    if rng.random() < 0.7:
        P.decal(ctx, rng.choice(["poster_0", "ad_stencil", "no_dumping"]), hw - 0.5, 2.6, 0.5, 0.5)
    return ctx, dict(height=zr + 0.12, floors=1)


# ---------------------------------------------------------------------------
# Alley walls / rear walls / roof props
# ---------------------------------------------------------------------------
def build_wall(spec):
    """Alley side wall or rear facade: thin module (depth 0.3) with doors, windows, utilities."""
    pal = PAL[spec["palette"]]
    L, Hh = spec["width"], spec["height_m"]
    ctx = P.Ctx(spec["id"], spec["seed"], pal)
    rng = ctx.rng = random.Random(spec["seed"] * 31 + spec.get("vseed", 0))
    opts = spec.get("opts", {})
    hl = L / 2
    sh = ctx.shell
    wall = pal["wall"]
    holes, doors, wins = [], [], []
    rear = spec["kind"] == "wall"
    if opts.get("gate"):
        gw = 2.4
        holes.append((-gw / 2, 0.0, gw / 2, 2.3))
    else:
        for i in range(opts.get("doors", 1)):
            dx = -hl + 1.0 + i * (L - 2.0) / max(1, opts.get("doors", 1) - 1) if opts.get("doors", 1) > 1 else \
                rng.uniform(-hl + 1.0, hl - 1.6)
            doors.append((dx, 0.15, dx + 0.95, 2.25))
        holes += doors
    z = 2.9 if not rear else 1.2
    while z + 1.1 < Hh - 0.5:
        nwin = max(1, int(L / 2.8))
        for i in range(nwin):
            if rng.random() < (0.85 if rear else 0.5):
                cx = -hl + (i + 0.5) * L / nwin + rng.uniform(-0.3, 0.3)
                w = rng.choice([0.6, 0.8, 1.0, 1.2])
                hb = (cx - w / 2, z, cx + w / 2, z + rng.choice([0.6, 0.9, 1.2]))
                if all(hb[2] < d[0] - 0.1 or hb[0] > d[2] + 0.1 or hb[1] > d[3] + 0.3 for d in doors):
                    wins.append(hb)
        z += 3.3
    holes += wins
    P.wall_with_holes(sh, -hl, hl, 0, Hh, holes, wall, mul(WHITE, rng.uniform(0.85, 1.0)), depth=0.22, max_cell=0.4)
    sh.box((-hl - 0.03, -0.04, Hh), (hl + 0.03, 0.3, Hh + 0.08), "concrete_weathered", WHITE, bevel=0.01)
    # back face + ends so the wall reads as solid from the other side and above
    P.plain_wall(sh, (-hl, 0.3, 0), (1, 0, 0), L, Hh, pal["side"], mul(WHITE, 0.8), (0, 1, 0), 0.8)
    sh.box((-hl, 0.0, 0), (-hl + 0.001, 0.3, Hh), pal["side"], WHITE, skip=("+x",))
    sh.box((hl - 0.001, 0.0, 0), (hl, 0.3, Hh), pal["side"], WHITE, skip=("-x",))
    ctx.col((-hl, 0, 0), (hl, 0.3, Hh), "concrete", ("wall",))
    ctx.col((-hl - 0.03, -0.04, Hh), (hl + 0.03, 0.3, Hh + 0.08), "concrete")
    ctx.nap.append(V((rng.uniform(-hl + 0.5, hl - 0.5), 0.13, Hh + 0.08)))
    for (x0, z0, x1, z1) in doors:
        if rng.random() < 0.5:
            P.door_steel(ctx, x0, z0, x1, z1, 0.0, 0.12, rng.choice([(0.25, 0.35, 0.3, 1), (0.45, 0.2, 0.15, 1),
                                                                     (0.2, 0.25, 0.4, 1)]))
        else:
            P.door_wood_panel(ctx, x0, z0, x1, z1, rng.choice(["wood_teal", "wood_green", "wood_brown"]), 0.0, 0.12, 2,
                              open_frac=rng.choice([0.0, 0.0, 0.5]))
        # steps + threshold
        sh.box((x0 - 0.15, -0.45, 0), (x1 + 0.15, 0.001, 0.15), "concrete_weathered", WHITE, bevel=0.015)
        ctx.col((x0 - 0.15, -0.45, 0), (x1 + 0.15, 0.0, 0.15), "concrete")
        sh.box((x0 - 0.12, -0.08, 2.25), (x1 + 0.12, 0.001, 2.35), "concrete_weathered", WHITE, bevel=0.01)
        ctx.entr.append(V(((x0 + x1) / 2, -0.3, 0.15)))
        if rng.random() < 0.6:
            P.potted_plant(ctx, x1 + 0.35, -0.3, 0.0, 0.5, pot=rng.choice(["terracotta", "styro", "blue"]))
        P.house_number(ctx, x1 + 0.25, 2.35, rng.choice(["no_6", "no_9", "no_14", "no_18", "no_23"]), -0.0)
        ctx.ledge(x0 - 0.12, x1 + 0.12, -0.08, 2.25, 0.8)
    if opts.get("gate"):
        x0, z0, x1, z1 = holes[0]
        gt = (0.3, 0.38, 0.33, 1)
        P.frame_rect(ctx.detail, x0, 0.02, x1, z1, 0.04, 0.1, 0.06, "metal_painted", gt)
        for half in (0, 1):
            hx0 = x0 + 0.06 + half * (x1 - x0 - 0.12) / 2
            hx1 = hx0 + (x1 - x0 - 0.12) / 2
            ctx.detail.box((hx0, 0.06, 0.05), (hx1, 0.08, 1.1), "metal_painted", gt, bevel=0.004)
            P.grille(ctx, hx0, 1.1, hx1, z1 - 0.06, 0.08, gt, "sun", 0.014)
        ctx.col((x0, 0.04, 0), (x1, 0.1, z1), "metal", ("wall",))
        sh.box((x0 - 0.2, -0.1, z1), (x1 + 0.2, 0.3, z1 + 0.3), wall, WHITE, bevel=0.01)
        for xs in (x0 - 0.2, x1):
            sh.box((xs, -0.1, 0), (xs + 0.2, 0.3, z1), wall, WHITE, bevel=0.01)
        if rng.random() < 0.8:
            P.bougainvillea_cascade(ctx, x0 - 0.5, x0 + 1.2, Hh + 0.3, -0.02, 1.6)
    for (x0, z0, x1, z1) in wins:
        P.alu_window(ctx, x0, z0, x1, z1, 0.0, 0.12, (0.8, 0.8, 0.8, 1), panes=2,
                     sill_mat="concrete_weathered") if rng.random() < 0.6 else \
            P.door_wood_panel(ctx, x0, z0, x1, z1, rng.choice(["wood_teal", "wood_green"]), 0.0, 0.12, 2)
        if rng.random() < 0.6:
            P.grille(ctx, x0 - 0.05, z0 - 0.05, x1 + 0.05, z1 + 0.05, -0.01, (0.3, 0.3, 0.3, 1),
                     rng.choice(["bars", "bars_h", "diamond"]), proj=0.3 if rng.random() < 0.4 else 0.0)
        if rng.random() < 0.4 and z1 + 0.8 < Hh:
            P.ac_unit(ctx, x1 + 0.55 if x1 + 0.95 < hl else x0 - 0.55, z0 + 0.3, 0.0)
        if rng.random() < 0.3 and rear:
            P.awning_corrugated(ctx, x0 - 0.2, x1 + 0.2, z1 + 0.25, 0.6, 15, 0.0,
                                rng.choice(["corrugated_rusted", "corrugated_blue"]))
    # utilities: cables along the wall with drops, meters, drainpipe, ads
    P.cable_run(ctx, -hl + 0.05, hl - 0.05, min(Hh - 0.4, 3.0), 0.0, n=rng.randint(4, 9), sag=0.1,
                drops=[(rng.uniform(-hl + 0.3, hl - 0.6), 1.5)])
    if rng.random() < 0.7:
        P.meter_cluster(ctx, rng.uniform(-hl + 0.6, hl - 0.6), 1.6, 0.0, n=rng.choice([2, 3, 5]))
    if Hh > 3.5:
        P.drainpipe(ctx, hl - 0.2 if rng.random() < 0.5 else -hl + 0.2, 0.0, Hh - 0.05, 0.0,
                    rng.choice(["plastic", "metal_painted"]), rng.choice([(0.75, 0.75, 0.72, 1), (0.35, 0.3, 0.28, 1)]))
    if opts.get("laundry") and Hh > 4:
        P.laundry_line(ctx, (-hl + 0.3, -0.6, 2.6), (hl - 0.3, -0.65, 2.55))
        for xs in (-hl + 0.3, hl - 0.3):
            ctx.clutter.tube([(xs, 0.0, 2.6), (xs, -0.65, 2.6)], 0.012, "metal_painted", (0.3, 0.3, 0.3, 1), sides=5)
    for _ in range(rng.randint(2, 5)):
        P.decal(ctx, rng.choice(["ad_stencil", "poster_0", "poster_1", "no_dumping", "water_stain", "peel_patch",
                                 "cement_patch", "crack"]), rng.uniform(-hl + 0.5, hl - 0.5), rng.uniform(1.2, 2.6),
                rng.uniform(0.4, 0.9), rng.uniform(0.4, 0.9), -0.004)
    P.decal(ctx, "moss_base", 0, 0.8, L, 0.8, -0.0045)
    for _ in range(rng.randint(1, 3)):
        P.decal(ctx, rng.choice(["streak_0", "streak_1", "soot_top"]), rng.uniform(-hl + 0.5, hl - 0.5), Hh,
                rng.uniform(0.6, 1.4), rng.uniform(1.2, 2.4))
    return ctx, dict(height=Hh + 0.08, floors=max(1, int(Hh / 3.3)))


def build_roof_prop(spec):
    ctx = P.Ctx(spec["id"], spec["seed"], {})
    rng = ctx.rng = random.Random(spec["seed"])
    k = spec["prop"]
    h = 0.5
    if k == "plank_bridge":
        L = spec["width"]
        P.plank(ctx, (-L / 2, -0.12, 0.0), (L / 2, -0.12, 0.0), 0.28)
        P.plank(ctx, (-L / 2, 0.14, 0.0), (L / 2, 0.14, 0.01), 0.22)
        for x in (-L / 2 + 0.2, L / 2 - 0.2):
            ctx.clutter.box((x - 0.05, -0.3, -0.05), (x + 0.05, 0.3, 0.0), "wood_brown", WHITE, uvmode="grain_h")
        ctx.nap.append(V((0.0, 0.0, 0.04)))
        h = 0.06
    elif k == "ladder_bamboo":
        P.ladder(ctx, 0.0, 0.0, 0.0, spec.get("height_m", 3.0) - 0.4, bamboo=True, lean_y=0.6)
        h = spec.get("height_m", 3.0)
    elif k == "ladder_steel":
        P.ladder(ctx, 0.0, 0.0, 0.0, spec.get("height_m", 2.6) - 0.4, bamboo=False, lean_y=0.0)
        for z in (0.6, 1.8):
            ctx.clutter.box((-0.25, 0.0, z), (0.25, 0.08, z + 0.04), "metal_painted", (0.3, 0.3, 0.3, 1))
        h = spec.get("height_m", 2.6)
    elif k == "shed":
        P.roof_shed(ctx, -1.2, 1.2, 0.0, 2.2, 0.0, 2.1, rng.choice(["corrugated_rusted", "corrugated_blue"]))
        ctx.clutter.box((-1.1, 0.3, 0.0), (-0.3, 1.0, 0.6), "plastic_matte", (0.2, 0.35, 0.7, 1), bevel=0.02)
        h = 2.2
    elif k in ("cables", "cables_street"):
        L = spec["width"]
        for c in range(rng.randint(8, 14) if k == "cables" else rng.randint(14, 24)):
            r = rng.choice([0.005, 0.007, 0.009, 0.012])
            a = (-L / 2, rng.uniform(-0.15, 0.15), rng.uniform(-0.2, 0.2))
            b = (L / 2, rng.uniform(-0.15, 0.15), rng.uniform(-0.2, 0.2))
            sag = rng.uniform(0.15, 0.5) if k == "cables" else rng.uniform(0.5, 1.4)
            ctx.clutter.tube(G.catenary(a, b, sag, 16 if k == "cables" else 28, 0.01, rng), r, "rubber",
                             rng.choice([WHITE, WHITE, (5, 5, 5, 1)]), sides=5, caps=False)
        for x in (-L / 2, L / 2):
            ctx.clutter.box((x - 0.04, -0.2, -0.25), (x + 0.04, 0.2, 0.25), "metal_painted", (0.3, 0.3, 0.3, 1))
        # one balance-walkable bundle
        ctx.col((-L / 2, -0.04, -0.3), (L / 2, 0.04, -0.2), "plastic")
        h = 0.3
    elif k == "tank_stand":
        top = P.water_tank(ctx, 0.0, 0.0, 0.0, "horizontal")
        h = top
    elif k == "solar":
        P.solar_heater(ctx, 0.0, 1.0, 0.0, 14)
        h = 1.4
    return ctx, dict(height=h, floors=0)


# ---------------------------------------------------------------------------
# Module list
# ---------------------------------------------------------------------------
def modules():
    M = []

    def add(base, variants, **kw):
        for i, (suffix, pal) in enumerate(variants):
            d = dict(kw)
            d.update(id=f"{base}_{suffix}", palette=pal, vseed=i * 101, base=base)
            M.append(d)
    add("colonial_2f_w4", [("ochre", "col_ochre"), ("blue", "col_blue"), ("yellow", "col_yellow")], style="colonial",
        kind="shop", width=4.0, depth=12.0, floors=2, seed=11,
        opts=dict(sign="may_tre", shops=["rattan"], parapet="balustrade", pediment=True))
    add("colonial_3f_w5", [("pink", "col_pink"), ("ochre", "col_ochre"), ("white", "col_white")], style="colonial",
        kind="shop", width=5.0, depth=14.0, floors=3, seed=12,
        opts=dict(sign="tra_da", shops=["cafe"], shutter=1.0, balcony_upper=False, parapet="solid", pediment=True))
    add("colonial_2f_w6", [("yellow", "col_yellow"), ("blue", "col_blue")], style="colonial", kind="shop", width=6.0,
        depth=12.0, floors=2, seed=13, opts=dict(sign="vang_bac", shops=["gold", "pharmacy"], ground_split=True,
                                                 bays=3, awning="tile"))
    add("colonial_3f_w4_5", [("ochre", "col_ochre"), ("green", "col_blue")], style="colonial", kind="shop", width=4.5,
        depth=13.0, floors=3, seed=14, opts=dict(sign="pho", shops=["pho"], awning="canvas", balcony_upper=True,
                                                 folding_doors=False, parapet="balustrade"))
    add("colonial_corner_3f", [("ochre", "col_ochre"), ("yellow", "col_yellow")], style="colonial", kind="corner",
        width=6.0, depth=10.0, floors=3, seed=15, opts=dict(sign="ca_phe", sign2=None, shops=["cafe", "grocery"],
                                                            parapet="solid"))
    add("tube90s_4f_w4", [("blue", "t90_blue"), ("pink", "t90_pink"), ("green", "t90_green")], style="tube90s",
        kind="shop", width=4.0, depth=14.0, floors=4, seed=21, opts=dict(sign="taphoa", shop="grocery", shutter=1.0))
    add("tube90s_5f_w3_5", [("yellow", "t90_yellow"), ("white", "t90_white"), ("blue", "t90_blue")], style="tube90s",
        kind="house", width=3.5, depth=12.0, floors=5, seed=22,
        opts=dict(shop="home", shutter=0.0, floors_kind=["cage", "balcony", "cage", "balcony"], sign=None))
    add("tube90s_3f_w4_5", [("green", "t90_green"), ("pink", "t90_pink")], style="tube90s", kind="shop", width=4.5,
        depth=13.0, floors=3, seed=23, opts=dict(sign="dien_thoai", shop="phones", shutter=0.45))
    add("tube90s_6f_w5", [("white", "t90_white"), ("blue", "t90_blue"), ("yellow", "t90_yellow")], style="tube90s",
        kind="shop", width=5.0, depth=16.0, floors=6, seed=24,
        opts=dict(sign="nha_nghi", shop="home", shutter=1.0, vsign="v_nha_nghi", lit=True,
                  floors_kind=["balcony", "balcony", "cage", "balcony", "balcony"]))
    add("tube90s_4f_w5", [("pink", "t90_pink"), ("green", "t90_green")], style="tube90s", kind="shop", width=5.0,
        depth=15.0, floors=4, seed=25, opts=dict(sign="kim_khi", shop="hardware", shutter=1.0))
    add("modern_5f_w4", [("white", "mod_white"), ("grey", "mod_grey")], style="modern", kind="shop", width=4.0,
        depth=14.0, floors=5, seed=31, opts=dict(shop="phones", sign="photo"))
    add("modern_4f_w6", [("dark", "mod_dark"), ("white", "mod_white")], style="modern", kind="house", width=6.0,
        depth=15.0, floors=4, seed=32, opts=dict(shop="home", garage=True, shutter=0.0))
    add("oldtile_1f_w4", [("white", "old_white"), ("yellow", "old_yellow"), ("blue", "old_blue")], style="old_tile",
        kind="house", width=4.0, depth=10.0, floors=1, seed=41, opts=dict())
    add("oldtile_1f_w5_shop", [("yellow", "old_yellow"), ("white", "old_white")], style="old_tile", kind="shop",
        width=5.0, depth=11.0, floors=1, seed=42, opts=dict(shop="grocery", sign="banh_cuon", eave=3.5))
    add("alley_wall_4m", [("grey", "alley_grey"), ("yellow", "alley_yellow")], style="old_tile", kind="alley",
        width=4.0, depth=0.3, height_m=4.2, seed=51, opts=dict(doors=1))
    add("alley_wall_6m_gate", [("green", "alley_green"), ("brick", "alley_brick")], style="old_tile", kind="alley",
        width=6.0, depth=0.3, height_m=3.2, seed=52, opts=dict(gate=True))
    add("alley_wall_8m", [("grey", "alley_grey"), ("yellow", "alley_yellow")], style="tube90s", kind="alley",
        width=8.0, depth=0.3, height_m=6.8, seed=53, opts=dict(doors=2, laundry=True))
    add("rear_wall_4f_w4", [("grey", "alley_grey"), ("brick", "alley_brick")], style="tube90s", kind="wall",
        width=4.0, depth=0.3, height_m=13.6, seed=61, opts=dict(doors=0, laundry=True))
    add("rear_wall_3f_w6", [("yellow", "alley_yellow"), ("grey", "alley_grey")], style="colonial", kind="wall",
        width=6.0, depth=0.3, height_m=10.4, seed=62, opts=dict(doors=1))
    for pid, w, extra in (("plank_bridge", 2.4, {}), ("ladder_bamboo", 0.5, {"height_m": 3.4}),
                          ("ladder_steel", 0.5, {"height_m": 2.6}), ("shed", 2.6, {}), ("cables", 3.0, {}),
                          ("tank_stand", 2.0, {}), ("solar", 1.4, {}), ("cables_street", 13.5, {})):
        M.append(dict(id=f"roofprop_{pid}", base=f"roofprop_{pid}", style="tube90s", kind="roof_prop", width=w,
                      depth=1.0, prop=pid, seed=70 + len(M), palette=None, **extra))
    return M


BUILDERS = {"colonial": build_colonial, "tube90s": build_tube90s, "modern": build_modern, "old_tile": build_oldtile}


def build(spec):
    if spec["kind"] in ("alley", "wall"):
        return build_wall(spec)
    if spec["kind"] == "roof_prop":
        return build_roof_prop(spec)
    if spec["kind"] == "corner":
        return build_corner(spec)
    return BUILDERS[spec["style"]](spec)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def to_godot(v):
    return [round(v.x, 3), round(v.z, 3), round(-v.y, 3)]


def finish_and_export(spec, ctx: P.Ctx, info, preview=False, export=True):
    col = bpy.context.scene.collection
    H = info["height"]
    dirt = 1.0
    grime = P.make_grime(ctx, H, spec["seed"], dirt=dirt)
    rng = random.Random(spec["seed"])
    uvoff = (rng.random(), rng.random())
    objs = []
    for k in P.Ctx.LAYERS:
        ob = ctx.B[k].finish(CM.get, CM.tile_m, grime if k not in ("decals", "foliage") else None, col, uvoff)
        if ob is None:
            continue
        if k in ("shell", "detail", "clutter"):
            G.smooth_weighted(ob, 35.0)
        objs.append(ob)
    # colliders
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
    # markers
    for lst, pre in ((ctx.nap, "NAP"), (ctx.climb, "CLIMB"), (ctx.entr, "ENTRANCE"), (ctx.lights, "LIGHT_SHOP")):
        for i, p in enumerate(lst):
            e = bpy.data.objects.new(f"{pre}_{i:02d}", None)
            e.location = p
            col.objects.link(e)
            objs.append(e)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH"
               and "-col" not in o.name)
    path = os.path.join(OUT_DIR, spec["id"] + ".glb")
    if export:
        os.makedirs(TMP, exist_ok=True)
        tmp = os.path.join(TMP, spec["id"] + ".glb")
        C.export_glb(tmp, objects=objs)
        r = GLB.postprocess(tmp, CM.IMAGE_FILES, TEX_REL)
        if r["embedded_left"]:
            print("WARNING embedded images left:", r["embedded_left"])
        GLB.write_import(path, "scene", "PackedScene", GLB.GLB_IMPORT_PARAMS)
        os.replace(tmp, path)
    if preview:
        W = spec["width"]
        C.preview_render(C.qa_path(f"city-houses/{spec['id']}.png"), target=(0, -0.5, H * 0.5),
                         distance=max(H * 1.45, W * 2.6, 6), yaw_deg=24, pitch_deg=6, res=(720, 960), samples=24,
                         lens=35, sun_strength=4.5, world_strength=0.8)
        if preview == "all":
            C.preview_render(C.qa_path(f"city-houses/{spec['id']}_roof.png"), target=(0, spec.get("depth", 1) * 0.45, H),
                             distance=max(H * 1.1, 8), yaw_deg=150, pitch_deg=38, res=(800, 600), samples=20,
                             lens=30, sun_strength=4.5, world_strength=0.8)
    entry = {
        "id": spec["id"],
        "file": f"res://assets/models/city/{spec['id']}.glb",
        "kind": spec["kind"],
        "width": spec["width"],
        "depth": spec.get("depth", 0.3),
        "height": round(H, 2),
        "floors": info["floors"],
        "style": spec["style"],
        "climb_points": [to_godot(p) for p in ctx.climb],
        "nap_spots": [to_godot(p) for p in ctx.nap],
        "entrances": [to_godot(p) for p in ctx.entr],
        "variant_of": spec["base"],
        "colliders": len(ctx.cols),
        "tris": tris,
    }
    return entry


def clear_scene():
    C.reset_scene()
    CM.reset_cache()
    CM.IMAGE_FILES.clear()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    argv = [x for x in argv if x != "--"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--preview", nargs="?", const="front", default=None)
    ap.add_argument("--no-export", action="store_true")
    a = ap.parse_args(argv)
    only = [s for s in a.only.split(",") if s]
    cat_path = os.path.join(OUT_DIR, "catalog.json")
    catalog = {}
    if os.path.exists(cat_path):
        for e in json.load(open(cat_path)):
            catalog[e["id"]] = e
    specs = modules()
    ids = {s["id"] for s in specs}
    for spec in specs:
        if only and not any(spec["id"] == o or spec["id"].startswith(o) for o in only):
            continue
        t0 = time.time()
        clear_scene()
        ctx, info = build(spec)
        entry = finish_and_export(spec, ctx, info, a.preview, not a.no_export)
        catalog[spec["id"]] = entry
        print(f"MODULE {spec['id']}: tris={entry['tris']} cols={entry['colliders']} nap={len(entry['nap_spots'])} "
              f"climb={len(entry['climb_points'])} {time.time() - t0:.1f}s")
    # write the catalog in module order, dropping ids that no longer exist
    out = [catalog[s["id"]] for s in specs if s["id"] in catalog and s["id"] in ids]
    if not a.no_export:
        with open(cat_path, "w") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        print(f"CATALOG {cat_path} ({len(out)} modules)")


if __name__ == "__main__":
    main()
