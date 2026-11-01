"""Architectural components for the old-quarter kit (facade pieces, clutter, roofs).

Frame: Blender metres, Z up. A facade is authored in the plane y = 0 facing -Y (the street),
x to the right as seen from the street. Things in front of the facade have y < 0. Building
mass extends to +Y. Components append geometry to the Ctx builders and register colliders,
climb points, nap spots and "ledges" (grime sources).
Side/rear facades are authored the same way and moved with Ctx.mark()/Ctx.xform_since().
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from mathutils import Matrix, Vector, noise

import city_geo as G
from city_geo import MB, V

WHITE = (1, 1, 1, 1)


def mul(c, k):
    return (c[0] * k, c[1] * k, c[2] * k, c[3] if len(c) > 3 else 1)


class Ctx:
    LAYERS = ("shell", "detail", "clutter", "decals", "foliage")

    def __init__(self, mid: str, seed: int, pal: dict):
        self.mid = mid
        self.rng = random.Random(seed)
        self.seed = seed
        self.pal = pal
        self.B = {k: MB(f"{mid}_{k}") for k in self.LAYERS}
        self.cols: list[dict] = []
        self.climb: list[Vector] = []
        self.nap: list[Vector] = []
        self.entr: list[Vector] = []
        self.lights: list[Vector] = []
        self.ledges: list[tuple[Vector, Vector, float]] = []

    @property
    def shell(self) -> MB:
        return self.B["shell"]

    @property
    def detail(self) -> MB:
        return self.B["detail"]

    @property
    def clutter(self) -> MB:
        return self.B["clutter"]

    @property
    def decals(self) -> MB:
        return self.B["decals"]

    @property
    def foliage(self) -> MB:
        return self.B["foliage"]

    # -- colliders / markers -------------------------------------------------
    def col(self, mn, mx, surface: str, tags: Sequence[str] = (), xform: Matrix | None = None) -> None:
        self.cols.append(dict(mn=V(mn), mx=V(mx), surface=surface, tags=tuple(tags),
                              xform=xform.copy() if xform is not None else Matrix.Identity(4)))

    def ledge(self, x0, x1, y, z, k=1.0):
        self.ledges.append((V((x0, y, z)), V((x1, y, z)), k))

    # -- move everything built since a mark (side / rear facades) -----------
    def mark(self) -> dict:
        m = {k: len(b.bm.verts) for k, b in self.B.items()}
        m.update(cols=len(self.cols), climb=len(self.climb), nap=len(self.nap), entr=len(self.entr),
                 lights=len(self.lights), ledges=len(self.ledges))
        return m

    def xform_since(self, mark: dict, M: Matrix) -> None:
        for k, b in self.B.items():
            b.bm.verts.ensure_lookup_table()
            vs = b.bm.verts[mark[k]:]
            for v in vs:
                v.co = M @ v.co
        for c in self.cols[mark["cols"]:]:
            c["xform"] = M @ c["xform"]
        for lst in ("climb", "nap", "entr", "lights"):
            L = getattr(self, lst)
            for i in range(mark[lst], len(L)):
                L[i] = M @ L[i]
        for i in range(mark["ledges"], len(self.ledges)):
            a, b, k = self.ledges[i]
            self.ledges[i] = (M @ a, M @ b, k)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def slope_xform(a, b, x=0.0):
    """Matrix at the midpoint of a-b (YZ plane) whose local +Y runs along the slope and local +Z is
    the up-facing normal. Use with a local box (x0, -L/2, z0)-(x1, L/2, z1)."""
    A, B = V(a), V(b)
    d = B - A
    th = math.atan2(d.z, d.y)
    if math.cos(th) < 0:
        th += math.pi
    c = (A + B) / 2
    return Matrix.Translation((x, c.y, c.z)) @ Matrix.Rotation(th, 4, "X"), d.length


def quad_n(mb: MB, pts, mat, tint=WHITE, n=None, uvs=None):
    """Quad with winding fixed so its normal points along n."""
    P = [V(p) for p in pts]
    if n is not None:
        nn = (P[1] - P[0]).cross(P[2] - P[0])
        if nn.dot(V(n)) < 0:
            P = list(reversed(P))
            if uvs is not None:
                uvs = list(reversed(uvs))
    mb.quad(P, mat, tint, uvs=uvs)


def front_rect(mb: MB, x0, z0, x1, z1, y, mat, tint=WHITE, uvs=None, n=(0, -1, 0)):
    quad_n(mb, [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], mat, tint, n, uvs)


def atlas_uv(rect, inset=0.002, flip_u=False):
    u0, v0, u1, v1 = rect
    u0, u1 = u0 + inset, u1 - inset
    v0, v1 = v0 + inset, v1 - inset
    if flip_u:
        u0, u1 = u1, u0
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def decal_plane(ctx: Ctx, cell: str, p_top_center, n, w, h, off=0.004, atlas="decals_grime"):
    """Decal on any vertical wall: p_top_center lies on the wall surface (top edge centre), n = wall
    outward normal (horizontal)."""
    import city_mats as CM
    r = CM.atlas_cell(atlas, cell)
    n = V(n).normalized()
    right = V((-n.y, n.x, 0.0))
    c = V(p_top_center) + n * off
    a = c - right * (w / 2)
    b = c + right * (w / 2)
    pts = [a - V((0, 0, h)), b - V((0, 0, h)), b, a]
    ctx.decals.quad(pts, "decals", WHITE, uvs=atlas_uv(r, 0.004))


def wall_weathering(ctx: Ctx, p0, u_axis, length, height, n, rng=None, top_streaks=True, cat_level=True):
    """Random large-scale weathering on a big plain wall (party/rear/side): streaks hanging from the
    top, water stains, cracks, cement patches, moss/splash along the base, the odd stencil ad."""
    rng = rng or ctx.rng
    p0 = V(p0)
    u = V(u_axis).normalized()

    def at(t, z):
        return p0 + u * (length * t) + V((0, 0, z))
    # u_axis may run opposite to the viewer's right; decal_plane uses n to orient, positions via at()
    if top_streaks:
        for _ in range(rng.randint(2, 4) + int(length / 5)):
            w = rng.uniform(1.0, 2.6)
            decal_plane(ctx, rng.choice(["streak_0", "streak_1", "streak_2", "soot_top"]),
                        at(rng.uniform(0.08, 0.92), height - 0.02), n, w, rng.uniform(2.0, min(6.0, height * 0.6)))
    for _ in range(rng.randint(1, 3) + int(length * height / 60)):
        cell = rng.choice(["water_stain", "crack", "cement_patch", "peel_patch", "water_stain", "crack"])
        sz = rng.uniform(0.6, 1.8)
        decal_plane(ctx, cell, at(rng.uniform(0.1, 0.9), rng.uniform(1.5, max(1.6, height - 0.5))), n, sz, sz)
    decal_plane(ctx, "moss_base", at(0.5, 0.8), n, length, 0.8, off=0.005)
    if cat_level and rng.random() < 0.5:
        decal_plane(ctx, rng.choice(["ad_stencil", "no_dumping", "poster_0", "poster_1"]),
                    at(rng.uniform(0.15, 0.85), rng.uniform(1.4, 2.2)), n, 0.6, 0.6)


def decal(ctx: Ctx, cell: str, x, ztop, w, h, y=-0.004, atlas="decals_grime"):
    """Facade decal quad (front plane), top edge at ztop."""
    import city_mats as CM
    r = CM.atlas_cell(atlas, cell)
    front_rect(ctx.decals, x - w / 2, ztop - h, x + w / 2, ztop, y, "decals", WHITE, atlas_uv(r, 0.004))


def wall_with_holes(mb: MB, x0, x1, z0, z1, holes, mat, tint=WHITE, y=0.0, depth=0.22,
                    reveal_depth=None, max_cell=0.4, reveal_mat=None):
    """Front faces of a wall with rectangular openings + the opening reveals (jambs/head/sill)."""
    for cx0, cz0, cx1, cz1 in G.wall_cells(x0, x1, z0, z1, holes, max_cell):
        front_rect(mb, cx0, cz0, cx1, cz1, y, mat, tint)
    rd = depth if reveal_depth is None else reveal_depth
    rm = reveal_mat or mat
    for hx0, hz0, hx1, hz1 in holes:
        y1 = y + rd
        quad_n(mb, [(hx0, y, hz0), (hx0, y1, hz0), (hx0, y1, hz1), (hx0, y, hz1)], rm, tint, (1, 0, 0))
        quad_n(mb, [(hx1, y, hz0), (hx1, y1, hz0), (hx1, y1, hz1), (hx1, y, hz1)], rm, tint, (-1, 0, 0))
        quad_n(mb, [(hx0, y, hz1), (hx1, y, hz1), (hx1, y1, hz1), (hx0, y1, hz1)], rm, tint, (0, 0, -1))
        if hz0 > z0 + 1e-3:
            quad_n(mb, [(hx0, y, hz0), (hx1, y, hz0), (hx1, y1, hz0), (hx0, y1, hz0)], rm, tint, (0, 0, 1))


def plain_wall(mb: MB, p0, u_axis, length, height, mat, tint=WHITE, n=None, max_cell=0.5):
    """Subdivided rectangle starting at p0 along u_axis (unit) and +Z."""
    p0 = V(p0)
    u = V(u_axis).normalized()
    nu = max(1, int(math.ceil(length / max_cell)))
    nv = max(1, int(math.ceil(height / max_cell)))
    for i in range(nu):
        for j in range(nv):
            a = p0 + u * (length * i / nu) + V((0, 0, height * j / nv))
            b = p0 + u * (length * (i + 1) / nu) + V((0, 0, height * j / nv))
            c = b + V((0, 0, height / nv))
            d = a + V((0, 0, height / nv))
            quad_n(mb, [a, b, c, d], mat, tint, n)


# ---------------------------------------------------------------------------
# Mouldings
# ---------------------------------------------------------------------------
CORNICE_PROFILES = {
    # (out, up) pairs from the wall (out=0) bottom to top; out toward the street
    "classic": [(0, 0), (0.03, 0.0), (0.03, 0.04), (0.06, 0.06), (0.09, 0.12), (0.2, 0.17), (0.22, 0.2),
                (0.22, 0.26), (0.0, 0.26)],
    "band": [(0, 0), (0.05, 0.0), (0.06, 0.02), (0.06, 0.13), (0.05, 0.15), (0.0, 0.15)],
    "slim": [(0, 0), (0.04, 0.0), (0.06, 0.03), (0.08, 0.06), (0.08, 0.1), (0.0, 0.1)],
    "drip": [(0, 0), (0.12, 0.0), (0.14, 0.02), (0.14, 0.09), (0.0, 0.09)],
    "coping": [(-0.02, 0), (0.04, 0.0), (0.04, 0.05), (0.0, 0.07), (-0.02, 0.05)],
}


def cornice(ctx: Ctx, x0, x1, z, prof="classic", mat="stucco_detail", tint=WHITE, y=0.0, scale=1.0,
            collide=True, walk_surface="concrete"):
    P = [(o * scale, u * scale) for o, u in CORNICE_PROFILES[prof]]
    ctx.shell.prism(P, (x0, y, z), (x1, y, z), mat, tint)
    if collide:
        out = max(o for o, _ in P)
        top = max(u for _, u in P)
        if out > 0.05:
            ctx.col((x0, y - out, z), (x1, y, z + top), walk_surface)
    ctx.ledge(x0, x1, y, z, 0.6)


def pilaster(ctx: Ctx, xc, w, z0, z1, mat, tint=WHITE, proud=0.06, capital=True):
    ctx.shell.box((xc - w / 2, -proud, z0), (xc + w / 2, 0.001, z1), mat, tint, bevel=0.012, segs=1,
                  skip=("+y",))
    if capital:
        ctx.shell.box((xc - w / 2 - 0.04, -proud - 0.04, z1 - 0.16), (xc + w / 2 + 0.04, 0.001, z1 - 0.04),
                      "stucco_detail", tint, bevel=0.015, skip=("+y",))
        ctx.shell.box((xc - w / 2 - 0.02, -proud - 0.02, z0), (xc + w / 2 + 0.02, 0.001, z0 + 0.25),
                      "stucco_detail", tint, bevel=0.01, skip=("+y",))


# ---------------------------------------------------------------------------
# Windows, doors, shutters
# ---------------------------------------------------------------------------
GLASS_CELLS = ["lace", "floral", "room_shelf", "blinds", "pink", "dark_room", "boxes", "green_curtain"]


def glass_pane(ctx: Ctx, x0, z0, x1, z1, y, cell=None, lit=False):
    import city_mats as CM
    cell = cell or ctx.rng.choice(GLASS_CELLS)
    r = CM.atlas_cell("glass_interiors", cell)
    # use a random sub-window of the cell so repeated cells differ
    u0, v0, u1, v1 = r
    du, dv = (u1 - u0), (v1 - v0)
    aspect = max(0.2, (x1 - x0) / max(z1 - z0, 0.05))
    fw = min(1.0, 0.55 * aspect + 0.25)
    fh = min(1.0, 0.55 / max(aspect, 0.3) + 0.25)
    ou = ctx.rng.uniform(0, 1 - fw)
    ov = ctx.rng.uniform(0, 1 - fh)
    rr = (u0 + du * ou, v0 + dv * ov, u0 + du * (ou + fw), v0 + dv * (ov + fh))
    front_rect(ctx.detail, x0, z0, x1, z1, y, "glass_lit" if lit else "glass", WHITE, atlas_uv(rr, 0.001))


def frame_rect(mb: MB, x0, z0, x1, z1, y0, y1, bar, mat, tint=WHITE, mid_v=(), mid_h=(), bevel=0.0):
    """Rectangular frame of square bars (window frames, grilles)."""
    mb.box((x0, y0, z0), (x0 + bar, y1, z1), mat, tint, bevel=bevel)
    mb.box((x1 - bar, y0, z0), (x1, y1, z1), mat, tint, bevel=bevel)
    mb.box((x0 + bar, y0, z0), (x1 - bar, y1, z0 + bar), mat, tint, bevel=bevel)
    mb.box((x0 + bar, y0, z1 - bar), (x1 - bar, y1, z1), mat, tint, bevel=bevel)
    for x in mid_v:
        mb.box((x - bar / 2, y0, z0 + bar), (x + bar / 2, y1, z1 - bar), mat, tint, bevel=bevel)
    for z in mid_h:
        mb.box((x0 + bar, y0, z - bar / 2), (x1 - bar, y1, z + bar / 2), mat, tint, bevel=bevel)


def louvre_leaf(ctx: Ctx, w, h, mat, tint, M: Matrix, slat_pitch=0.055, panel_split=0.62):
    """One louvred shutter leaf built at origin (x 0..w, z 0..h, y = 0..-t), moved by M."""
    mb = ctx.detail
    mk = len(mb.bm.verts)
    t = 0.04
    st = 0.065
    frame_rect(mb, 0, 0, w, h, -t, 0, st, mat, tint, mid_h=(h * panel_split,), bevel=0.004)
    # slats (angled 40deg) in the two panels
    for za, zb in ((st, h * panel_split - st / 2), (h * panel_split + st / 2, h - st)):
        n = max(1, int((zb - za) / slat_pitch))
        for i in range(n):
            zc = za + (i + 0.5) * (zb - za) / n
            R = G.rot_x(-40, (0, -t / 2, zc))
            mb.box((st, -t / 2 - 0.028, zc - 0.005), (w - st, -t / 2 + 0.028, zc + 0.005), mat, tint,
                   xform=R, uvmode="grain_h")
    mb.bm.verts.ensure_lookup_table()
    for v in mb.bm.verts[mk:]:
        v.co = M @ v.co


def french_window(ctx: Ctx, cx, z, w, h, shutter_mat, state="open", wall_y=0.0, reveal=0.14,
                  trim_tint=WHITE, arch=False, sill=True, hood="cornice"):
    """Colonial tall window/door: architrave, sill, glazed casements, louvred shutters."""
    rng = ctx.rng
    x0, x1 = cx - w / 2, cx + w / 2
    stint = mul(WHITE, rng.uniform(0.85, 1.0))
    # architrave mouldings
    a = 0.12
    trim = "stucco_detail"
    prof = [(0, 0), (0.02, 0.0), (0.03, 0.02), (0.03, a - 0.02), (0.015, a), (0, a)]
    ctx.shell.box((x0 - a, wall_y - 0.025, z), (x0, wall_y + 0.001, z + h + a), trim, trim_tint, bevel=0.008,
                  skip=("+y",))
    ctx.shell.box((x1, wall_y - 0.025, z), (x1 + a, wall_y + 0.001, z + h + a), trim, trim_tint, bevel=0.008,
                  skip=("+y",))
    ctx.shell.box((x0, wall_y - 0.025, z + h), (x1, wall_y + 0.001, z + h + a), trim, trim_tint, bevel=0.008,
                  skip=("+y",))
    if hood == "cornice":
        cornice(ctx, x0 - a - 0.06, x1 + a + 0.06, z + h + a, "slim", trim, trim_tint, collide=True)
        ctx.shell.box((cx - 0.07, wall_y - 0.06, z + h - 0.02), (cx + 0.07, wall_y + 0.001, z + h + a + 0.02),
                      trim, trim_tint, bevel=0.01, skip=("+y",))  # keystone
    elif hood == "pediment":
        ph = 0.28
        P = [(x0 - a - 0.08, z + h + a), (x1 + a + 0.08, z + h + a), (cx, z + h + a + ph)]
        bm_pts = [(p[0], wall_y - 0.07, p[1]) for p in P]
        ctx.shell.prism([(0, 0), (0.07, 0), (0.07, 0.06), (0, 0.06)], (x0 - a - 0.08, wall_y, z + h + a),
                        (x1 + a + 0.08, wall_y, z + h + a), trim, trim_tint)
        quad_n(ctx.shell, [bm_pts[0], bm_pts[1], bm_pts[2], bm_pts[2]], trim, trim_tint, (0, -1, 0))
        ctx.ledge(x0 - a, x1 + a, wall_y, z + h + a, 0.6)
    if sill:
        ctx.shell.box((x0 - 0.1, wall_y - 0.07, z - 0.07), (x1 + 0.1, wall_y + 0.02, z), trim, trim_tint,
                      bevel=0.012, skip=("+y",))
        ctx.col((x0 - 0.1, wall_y - 0.07, z - 0.07), (x1 + 0.1, wall_y + reveal, z), "concrete")
        ctx.ledge(x0 - 0.1, x1 + 0.1, wall_y, z - 0.07, 1.0)
    # frame + glazed casements inside the reveal
    fy = wall_y + reveal
    wood = shutter_mat
    frame_rect(ctx.detail, x0, z, x1, z + h, fy - 0.06, fy, 0.06, wood, stint, bevel=0.004)
    tr = h * 0.78
    ctx.detail.box((x0 + 0.06, fy - 0.06, z + tr - 0.03), (x1 - 0.06, fy, z + tr + 0.03), wood, stint)
    # casements: two leaves, each 3 panes, slightly open sometimes
    lw = (w - 0.12) / 2
    for side in (0, 1):
        lx0 = x0 + 0.06 + side * lw
        open_ang = rng.choice([0, 0, 0, 15, 30]) if state != "closed" else 0
        mk = len(ctx.detail.bm.verts)
        cy = fy - 0.04
        frame_rect(ctx.detail, lx0, z + 0.06, lx0 + lw, z + tr - 0.03, cy - 0.04, cy, 0.05, wood, stint,
                   mid_h=(z + 0.06 + (tr - 0.09) * 0.35, z + 0.06 + (tr - 0.09) * 0.68))
        ctx.detail.bm.verts.ensure_lookup_table()
        if open_ang:
            hx = lx0 if side == 0 else lx0 + lw
            M = G.rot_z(open_ang if side == 0 else -open_ang, (hx, cy, 0))
            for v in ctx.detail.bm.verts[mk:]:
                v.co = M @ v.co
    glass_pane(ctx, x0 + 0.06, z + 0.06, x1 - 0.06, z + tr - 0.03, fy - 0.06)
    glass_pane(ctx, x0 + 0.06, z + tr + 0.03, x1 - 0.06, z + h - 0.06, fy - 0.06, "dark_room")
    if arch:
        pass
    # louvred shutters mounted at the facade face
    sw = w / 2
    sh = h - 0.02
    for side in (0, 1):
        hinge_x = x0 if side == 0 else x1
        if state == "closed":
            ang = 0
        elif state == "half":
            ang = rng.uniform(60, 110)
        else:
            ang = rng.uniform(165, 178)
        if side == 0:
            M = Matrix.Translation((hinge_x, wall_y - 0.005, z + 0.01)) @ Matrix.Rotation(math.radians(ang), 4, "Z")
            if ang < 1:
                M = Matrix.Translation((hinge_x, wall_y - 0.005, z + 0.01))
            louvre_leaf(ctx, sw, sh, wood, stint, M)
        else:
            M = Matrix.Translation((hinge_x, wall_y - 0.005, z + 0.01)) @ Matrix.Rotation(math.radians(-ang), 4, "Z") \
                @ Matrix.Translation((-sw, 0, 0))
            louvre_leaf(ctx, sw, sh, wood, stint, M)
        # hinges / pintles
        for zz in (z + 0.25, z + h - 0.3):
            ctx.detail.box((hinge_x - 0.015, wall_y - 0.03, zz), (hinge_x + 0.015, wall_y, zz + 0.04), "iron_wrought")
    # closed shutters make the whole opening a flat-ish surface; collider for the reveal
    ctx.col((x0, wall_y, z), (x1, wall_y + reveal, z + h), "wood", ("wall",))


def alu_window(ctx: Ctx, x0, z0, x1, z1, wall_y=0.0, reveal=0.12, tint=(0.85, 0.86, 0.86, 1), panes=None,
               sill=True, sill_mat="granite_red", lit=False, dark_frame=False):
    """Aluminium sliding window/door with glass (1990s/modern)."""
    rng = ctx.rng
    fy = wall_y + reveal
    w = x1 - x0
    panes = panes or max(2, int(round(w / 0.75)))
    ftint = (0.18, 0.18, 0.19, 1) if dark_frame else tint
    frame_rect(ctx.detail, x0, z0, x1, z1, fy - 0.07, fy, 0.045, "chrome", ftint)
    pw = (w - 0.09) / panes
    for i in range(panes):
        px0 = x0 + 0.045 + i * pw
        off = -0.035 if i % 2 else 0.0
        slide = rng.uniform(0, pw * 0.4) if (i % 2 and rng.random() < 0.3) else 0.0
        frame_rect(ctx.detail, px0 + slide, z0 + 0.045, px0 + pw + slide, z1 - 0.045, fy - 0.035 + off,
                   fy - 0.005 + off, 0.035, "chrome", ftint)
        glass_pane(ctx, px0 + 0.035 + slide, z0 + 0.08, px0 + pw - 0.035 + slide, z1 - 0.08, fy - 0.022 + off,
                   lit=lit)
    if sill:
        ctx.shell.box((x0 - 0.05, wall_y - 0.05, z0 - 0.03), (x1 + 0.05, fy, z0), sill_mat, WHITE, bevel=0.006)
        ctx.col((x0 - 0.05, wall_y - 0.05, z0 - 0.03), (x1 + 0.05, fy, z0), "tile")
        ctx.ledge(x0 - 0.05, x1 + 0.05, wall_y, z0 - 0.03, 0.8)
    ctx.col((x0, wall_y, z0), (x1, fy, z1), "metal", ("wall",))


def grille(ctx: Ctx, x0, z0, x1, z1, y, tint, pattern="bars", bar=0.016, proj=0.0):
    """Steel security grille ('khung bao ve'). proj > 0 -> box cage projecting proj from the wall."""
    mb = ctx.detail
    mat = "metal_painted"
    rng = ctx.rng
    yf = y - proj
    frame_rect(mb, x0, z0, x1, z1, yf - bar, yf, bar * 1.6, mat, tint)
    sp = rng.choice([0.11, 0.12, 0.13])
    n = max(1, int((x1 - x0) / sp))
    for i in range(1, n):
        x = x0 + i * (x1 - x0) / n
        mb.box((x - bar / 2, yf - bar, z0), (x + bar / 2, yf, z1), mat, tint)
    if pattern in ("bars_h", "diamond", "sun"):
        for z in (z0 + (z1 - z0) * 0.33, z0 + (z1 - z0) * 0.66):
            mb.box((x0, yf - bar, z - bar / 2), (x1, yf, z + bar / 2), mat, tint)
    if pattern == "diamond":
        cz = (z0 + z1) / 2
        hw = min((x1 - x0), (z1 - z0)) * 0.3
        cx = (x0 + x1) / 2
        pts = [(cx - hw, yf - bar / 2, cz), (cx, yf - bar / 2, cz + hw), (cx + hw, yf - bar / 2, cz),
               (cx, yf - bar / 2, cz - hw), (cx - hw, yf - bar / 2, cz)]
        mb.tube(pts, bar * 0.6, mat, tint, square=True)
    if pattern == "sun":
        cx, cz = (x0 + x1) / 2, z1 - 0.02
        for k in range(7):
            a = math.pi * (k + 0.5) / 7
            r = min((x1 - x0) / 2, (z1 - z0) * 0.45)
            mb.tube([(cx, yf - bar / 2, cz), (cx + math.cos(a) * r, yf - bar / 2, cz - math.sin(a) * r * 0.9)],
                    bar * 0.5, mat, tint, square=True)
        mb.tube([(cx + math.cos(a) * 0.25, yf - bar / 2, cz - math.sin(a) * 0.23)
                 for a in [math.pi * k / 12 for k in range(13)]], bar * 0.5, mat, tint, square=True)
    if proj > 0:
        # cage sides, top and bottom tray (walkable top for cats)
        for x in (x0, x1):
            mb.box((x - bar / 2, yf, z0), (x + bar / 2, y, z0 + bar * 1.6), mat, tint)
            mb.box((x - bar / 2, yf, z1 - bar * 1.6), (x + bar / 2, y, z1), mat, tint)
            for k in range(1, max(2, int(proj / 0.12))):
                yy = yf + k * proj / max(2, int(proj / 0.12))
                mb.box((x - bar / 2, yy - bar / 2, z0), (x + bar / 2, yy + bar / 2, z1), mat, tint)
        nt = max(2, int((x1 - x0) / 0.15))
        for k in range(nt + 1):
            x = x0 + k * (x1 - x0) / nt
            mb.box((x - bar / 2, yf, z1 - bar), (x + bar / 2, y, z1), mat, tint)
            mb.box((x - bar / 2, yf, z0), (x + bar / 2, y, z0 + bar), mat, tint)
        # sheet metal top (rain cover) on many cages
        if rng.random() < 0.6:
            corrugated_sheet(ctx, x0 - 0.03, x1 + 0.03, y + 0.01, yf - 0.06, z1 + 0.06, z1 + 0.01,
                             rng.choice(["corrugated_blue", "corrugated_rusted"]))
        ctx.col((x0, yf - bar, z1 - 0.02), (x1, y, z1 + 0.06), "metal")
        ctx.col((x0, yf - bar, z0), (x1, yf, z1), "metal")
        ctx.ledge(x0, x1, y, z0, 0.7)


def door_steel(ctx: Ctx, x0, z0, x1, z1, wall_y=0.0, reveal=0.12, tint=(0.25, 0.32, 0.3, 1)):
    """Steel-and-glass house door (2 leaves) with decorative grille."""
    fy = wall_y + reveal
    w = x1 - x0
    frame_rect(ctx.detail, x0, z0, x1, z1, fy - 0.06, fy, 0.05, "metal_painted", tint)
    lw = (w - 0.1) / 2
    for i in range(2):
        lx = x0 + 0.05 + i * lw
        ctx.detail.box((lx, fy - 0.05, z0 + 0.05), (lx + lw, fy - 0.01, z0 + 0.95), "metal_painted", tint,
                       bevel=0.004)
        for k in range(3):  # pressed panels
            ctx.detail.box((lx + 0.06, fy - 0.06, z0 + 0.12 + k * 0.27), (lx + lw - 0.06, fy - 0.05,
                                                                         z0 + 0.32 + k * 0.27), "metal_painted",
                           mul(tint, 0.9), bevel=0.005)
        glass_pane(ctx, lx + 0.04, z0 + 0.98, lx + lw - 0.04, z1 - 0.1, fy - 0.03, "dark_room")
        frame_rect(ctx.detail, lx, z0 + 0.95, lx + lw, z1 - 0.05, fy - 0.05, fy - 0.01, 0.04, "metal_painted",
                   tint)
        grille(ctx, lx + 0.05, z0 + 1.0, lx + lw - 0.05, z1 - 0.1, fy - 0.05, tint, "diamond", 0.012)
    ctx.detail.box((x0 + w / 2 - 0.08, fy - 0.09, z0 + 1.0), (x0 + w / 2 - 0.05, fy - 0.05, z0 + 1.12), "chrome")
    ctx.col((x0, wall_y, z0), (x1, fy, z1), "metal", ("wall",))


def door_wood_panel(ctx: Ctx, x0, z0, x1, z1, mat, wall_y=0.0, reveal=0.12, leaves=2, open_frac=0.0):
    """Traditional wooden panel doors (old houses)."""
    fy = wall_y + reveal
    frame_rect(ctx.detail, x0, z0, x1, z1, fy - 0.08, fy, 0.08, mat, WHITE, bevel=0.005)
    w = (x1 - x0 - 0.16) / leaves
    for i in range(leaves):
        lx = x0 + 0.08 + i * w
        mk = len(ctx.detail.bm.verts)
        ctx.detail.box((lx, fy - 0.07, z0 + 0.02), (lx + w, fy - 0.03, z1 - 0.08), mat, WHITE, bevel=0.004,
                       uvmode="grain_v")
        for k in range(3):
            pz0 = z0 + 0.15 + k * (z1 - z0 - 0.35) / 3
            ctx.detail.box((lx + 0.07, fy - 0.08, pz0), (lx + w - 0.07, fy - 0.07, pz0 + (z1 - z0 - 0.5) / 3),
                           mat, mul(WHITE, 0.92), bevel=0.008, uvmode="grain_v")
        if open_frac > 0 and i == leaves - 1:
            ctx.detail.bm.verts.ensure_lookup_table()
            M = G.rot_z(-80 * open_frac, (lx + w, fy - 0.05, 0))
            for v in ctx.detail.bm.verts[mk:]:
                v.co = M @ v.co
    ctx.col((x0, wall_y, z0), (x1, fy, z1), "wood", ("wall",))


# ---------------------------------------------------------------------------
# Balconies & railings
# ---------------------------------------------------------------------------
def balcony_slab(ctx: Ctx, x0, x1, z, proj, thick=0.14, mat="concrete_weathered", edge_mat=None,
                 edge_tint=WHITE, floor_mat="terrazzo", corbels=0, corbel_tint=WHITE, wall_y=0.0):
    yf = wall_y - proj
    sh = ctx.shell
    em = edge_mat or mat
    sh.box((x0, yf, z - thick), (x1, wall_y + 0.001, z), em, edge_tint, bevel=0.015, skip=("+y",))
    # floor finish
    sh.box((x0 + 0.02, yf + 0.02, z), (x1 - 0.02, wall_y, z + 0.015), floor_mat, WHITE, skip=("+y", "-z"))
    # drip groove + soffit tint handled by vertex grime
    for k in range(corbels):
        cx = x0 + 0.15 + k * (x1 - x0 - 0.3) / max(corbels - 1, 1)
        prof = [(0.0, 0.0), (0.04, 0.0), (0.06, 0.12), (0.15, 0.24), (proj * 0.85, 0.3), (proj * 0.85, 0.34),
                (0.0, 0.34)]
        ctx.shell.prism(prof, (cx - 0.07, wall_y, z - thick - 0.34), (cx + 0.07, wall_y, z - thick - 0.34),
                        "stucco_detail", corbel_tint)
    ctx.col((x0, yf, z - thick), (x1, wall_y, z + 0.015), "tile")
    ctx.ledge(x0, x1, yf, z - thick, 1.2)
    ctx.ledge(x0, x1, wall_y, z - thick, 0.5)


def scroll_points(cx, cz, r, turns=1.4, start=0.0, flip=1, n=22):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        a = start + flip * t * turns * 2 * math.pi
        rr = r * (1 - 0.75 * t)
        pts.append((cx + math.cos(a) * rr, cz + math.sin(a) * rr))
    return pts


def railing_wrought(ctx: Ctx, x0, x1, y, z, h=1.0, style=0, sides=None):
    """Colonial cast/wrought iron balustrade with scroll panels. sides: (depth_y) adds returns."""
    mb = ctx.detail
    mat = "iron_wrought"
    t = WHITE
    rng = ctx.rng
    # top rail (flat bar + round handrail), bottom rail
    mb.box((x0, y - 0.025, z + h - 0.03), (x1, y + 0.025, z + h), mat, t, bevel=0.006)
    mb.box((x0, y - 0.012, z + 0.06), (x1, y + 0.012, z + 0.09), mat, t)
    mb.box((x0, y - 0.012, z + h - 0.16), (x1, y + 0.012, z + h - 0.14), mat, t)
    n_posts = max(2, int(round((x1 - x0) / 1.2)) + 1)
    for i in range(n_posts):
        x = x0 + i * (x1 - x0) / (n_posts - 1)
        mb.box((x - 0.022, y - 0.022, z), (x + 0.022, y + 0.022, z + h), mat, t, bevel=0.004)
        mb.box((x - 0.035, y - 0.035, z + h), (x + 0.035, y + 0.035, z + h + 0.04), mat, t, bevel=0.01)
    # balusters + scroll pairs per bay
    bays = n_posts - 1
    for b in range(bays):
        bx0 = x0 + b * (x1 - x0) / bays
        bx1 = bx0 + (x1 - x0) / bays
        nb = max(3, int((bx1 - bx0) / 0.11))
        for k in range(1, nb):
            x = bx0 + k * (bx1 - bx0) / nb
            if style == 0 or k % 2 == 0:
                mb.box((x - 0.006, y - 0.006, z + 0.09), (x + 0.006, y + 0.006, z + h - 0.16), mat, t)
        # scroll frieze in the top band
        nsc = max(1, int((bx1 - bx0) / 0.26))
        for k in range(nsc):
            cx = bx0 + (k + 0.5) * (bx1 - bx0) / nsc
            for flip in (1, -1):
                pts = scroll_points(cx + flip * 0.05, z + h - 0.085, 0.045, 1.2, math.pi if flip > 0 else 0, flip)
                mb.tube([(px, y, pz) for px, pz in pts], 0.004, mat, t, square=True)
        # central medallion: double C-scroll
        mx = (bx0 + bx1) / 2
        mz = z + 0.09 + (h - 0.25) * 0.5
        for flip in (1, -1):
            pts = scroll_points(mx, mz + flip * 0.12, 0.11, 1.0, -math.pi / 2 * flip, flip, 26)
            mb.tube([(px, y, pz) for px, pz in pts], 0.005, mat, t, square=True)
        mb.tube([(mx - 0.14, y, mz), (mx + 0.14, y, mz)], 0.005, mat, t, square=True)
    if sides:
        for xs in (x0, x1):
            mb.box((xs - 0.025, y, z + h - 0.03), (xs + 0.025, y + sides, z + h), mat, t)
            mb.box((xs - 0.012, y, z + 0.06), (xs + 0.012, y + sides, z + 0.09), mat, t)
            nb = max(2, int(sides / 0.11))
            for k in range(1, nb):
                yy = y + k * sides / nb
                mb.box((xs - 0.006, yy - 0.006, z + 0.09), (xs + 0.006, yy + 0.006, z + h - 0.03), mat, t)
    ctx.col((x0, y - 0.03, z), (x1, y + 0.03, z + h + 0.04), "metal")
    if sides:
        ctx.col((x0 - 0.03, y, z), (x0 + 0.03, y + sides, z + h), "metal")
        ctx.col((x1 - 0.03, y, z), (x1 + 0.03, y + sides, z + h), "metal")


def railing_steel(ctx: Ctx, x0, x1, y, z, h=1.0, tint=(0.2, 0.35, 0.3, 1), sides=None, stainless=False):
    """1990s steel/stainless tube railing with simple ornament."""
    mb = ctx.detail
    mat = "chrome" if stainless else "metal_painted"
    t = (0.75, 0.76, 0.77, 1) if stainless else tint
    r = 0.022 if stainless else 0.016
    mb.tube([(x0, y, z + h), (x1, y, z + h)], r, mat, t, sides=8)
    mb.tube([(x0, y, z + 0.1), (x1, y, z + 0.1)], r * 0.7, mat, t, sides=6)
    mb.tube([(x0, y, z + h * 0.55), (x1, y, z + h * 0.55)], r * 0.6, mat, t, sides=6)
    n = max(2, int((x1 - x0) / (0.12 if not stainless else 0.15)))
    for k in range(n + 1):
        x = x0 + k * (x1 - x0) / n
        mb.tube([(x, y, z), (x, y, z + h)], r * (1.0 if k in (0, n) else 0.55), mat, t, sides=6)
    if not stainless:
        # rings between rails
        for k in range(n):
            x = x0 + (k + 0.5) * (x1 - x0) / n
            pts = [(x + math.cos(a) * 0.04, y, z + h * 0.775 + math.sin(a) * 0.04)
                   for a in [2 * math.pi * i / 10 for i in range(11)]]
            if k % 2 == 0:
                mb.tube(pts, 0.005, mat, t, sides=4, caps=False)
    if sides:
        for xs in (x0, x1):
            mb.tube([(xs, y, z + h), (xs, y + sides, z + h)], r, mat, t, sides=8)
            mb.tube([(xs, y, z + 0.1), (xs, y + sides, z + 0.1)], r * 0.7, mat, t, sides=6)
            for k in range(1, max(2, int(sides / 0.12))):
                yy = y + k * sides / max(2, int(sides / 0.12))
                mb.tube([(xs, yy, z), (xs, yy, z + h)], r * 0.55, mat, t, sides=6)
    ctx.col((x0, y - 0.03, z), (x1, y + 0.03, z + h + r), "metal")
    if sides:
        ctx.col((x0 - 0.03, y, z), (x0 + 0.03, y + sides, z + h), "metal")
        ctx.col((x1 - 0.03, y, z), (x1 + 0.03, y + sides, z + h), "metal")


def railing_glass(ctx: Ctx, x0, x1, y, z, h=1.05):
    mb = ctx.detail
    mb.box((x0, y - 0.01, z + 0.05), (x1, y + 0.01, z + h - 0.04), "glass_clear", (0.8, 0.9, 0.9, 1))
    mb.tube([(x0, y, z + h), (x1, y, z + h)], 0.024, "chrome", sides=10)
    for x in (x0 + 0.05, x1 - 0.05):
        mb.box((x - 0.02, y - 0.03, z), (x + 0.02, y + 0.03, z + 0.12), "chrome")
    ctx.col((x0, y - 0.03, z), (x1, y + 0.03, z + h + 0.024), "metal")


def masonry_parapet(ctx: Ctx, x0, x1, y0, y1, z, h, mat, tint=WHITE, coping="concrete_weathered",
                    surface="concrete"):
    """Low wall (balcony front / roof parapet). y0 < y1."""
    sh = ctx.shell
    sh.box((x0, y0, z), (x1, y1, z + h), mat, tint, bevel=0.01)
    sh.box((x0 - 0.02, y0 - 0.025, z + h), (x1 + 0.02, y1 + 0.025, z + h + 0.05), coping, WHITE, bevel=0.01)
    ctx.col((x0 - 0.02, y0 - 0.025, z), (x1 + 0.02, y1 + 0.025, z + h + 0.05), surface)


# ---------------------------------------------------------------------------
# Clutter
# ---------------------------------------------------------------------------
def ac_unit(ctx: Ctx, cx, z, wall_y=0.0, facing=(0, -1, 0), bracket=True, w=0.78, h=0.55, d=0.27,
            pipe_side=1, tint=None, drip=True, nap=True, pipe_up=None):
    """Outdoor condenser on L-brackets: casing, fan grille, side louvres, pipes, drain hose, grime.
    Built facing -Y at (cx, wall_y, z=bottom)."""
    mb = ctx.clutter
    rng = ctx.rng
    tint = tint or mul((0.93, 0.92, 0.87, 1), rng.uniform(0.85, 1.0))
    gap = 0.1
    y0 = wall_y - gap - d
    y1 = wall_y - gap
    x0, x1 = cx - w / 2, cx + w / 2
    mb.box((x0, y0, z), (x1, y1, z + h), "metal_painted", tint, bevel=0.012, segs=2)
    # front fan grille: dark well + concentric rings + spokes
    fx = x0 + w * 0.38
    fz = z + h * 0.5
    R = h * 0.4
    mb.cylinder((fx, y0 + 0.002, fz), (0, 1, 0), R * 1.02, 0.004, "dark", sides=24)
    for k in range(1, 6):
        rr = R * k / 5
        pts = [(fx + math.cos(a) * rr, y0 - 0.008, fz + math.sin(a) * rr)
               for a in [2 * math.pi * i / 24 for i in range(25)]]
        mb.tube(pts, 0.0028, "metal_painted", mul(tint, 0.5), sides=4, caps=False)
    for k in range(6):
        a = math.pi * k / 6
        mb.tube([(fx - math.cos(a) * R, y0 - 0.008, fz - math.sin(a) * R),
                 (fx + math.cos(a) * R, y0 - 0.008, fz + math.sin(a) * R)], 0.003, "metal_painted",
                mul(tint, 0.5), sides=4)
    for k in range(3):  # fan blades
        a = 2 * math.pi * k / 3 + rng.uniform(0, 1)
        p = V((fx, y0 + 0.03, fz))
        d1 = V((math.cos(a), 0, math.sin(a)))
        d2 = V((math.cos(a + 0.6), 0, math.sin(a + 0.6)))
        quad_n(mb, [p + d1 * 0.03, p + d1 * R * 0.9, p + d2 * R * 0.9, p + d2 * 0.03], "plastic",
               (0.25, 0.25, 0.25, 1), (0, -1, 0))
    # front panel louvres on the right part + brand-less badge
    for k in range(8):
        zz = z + 0.08 + k * (h - 0.16) / 8
        mb.box((x0 + w * 0.76, y0 - 0.006, zz), (x1 - 0.04, y0, zz + 0.012), "metal_painted", mul(tint, 0.85))
    mb.box((x0 + w * 0.78, y0 - 0.004, z + h - 0.07), (x0 + w * 0.92, y0, z + h - 0.045), "plastic",
           (0.6, 0.62, 0.65, 1))
    # side grille (back coil) and top dust
    for k in range(10):
        zz = z + 0.05 + k * (h - 0.1) / 10
        mb.box((x1, y0 + 0.03, zz), (x1 + 0.004, y1 - 0.03, zz + 0.01), "metal_painted", mul(tint, 0.7))
    # service valve cover + pipes
    px = x1 if pipe_side > 0 else x0
    mb.box((px - 0.02 if pipe_side > 0 else px - 0.06, y0 + 0.05, z + 0.05),
           (px + 0.06 if pipe_side > 0 else px + 0.02, y1 - 0.02, z + 0.2), "metal_painted", tint, bevel=0.005)
    pr = 0.016
    ptint = mul((0.9, 0.9, 0.88, 1), rng.uniform(0.7, 1.0))
    for k, zz in enumerate((z + 0.09, z + 0.15)):
        sx = px + 0.04 * pipe_side
        up = pipe_up if pipe_up is not None else rng.uniform(0.3, 1.2)
        pts = [(sx, y1 - 0.06 - k * 0.04, zz), (sx + 0.08 * pipe_side, y1 - 0.06 - k * 0.04, zz),
               (sx + 0.1 * pipe_side, wall_y - 0.03 - k * 0.035, zz + 0.05),
               (sx + 0.1 * pipe_side, wall_y - 0.03 - k * 0.035, zz + up),
               (sx + 0.1 * pipe_side, wall_y + 0.02, zz + up + 0.03)]
        mb.tube(pts, pr, "plastic_matte", ptint, sides=6)
    # drain hose dangling
    hx = x0 + 0.06 if pipe_side > 0 else x1 - 0.06
    mb.tube([(hx, y0 + 0.08, z), (hx, y0 + 0.06, z - 0.15), (hx + 0.03, y0 + 0.1, z - rng.uniform(0.3, 0.9))],
            0.008, "rubber", sides=5)
    if bracket:
        for bx in (x0 + 0.08, x1 - 0.08):
            mb.box((bx - 0.02, y0 - 0.02, z - 0.04), (bx + 0.02, wall_y, z), "metal_painted",
                   (0.35, 0.33, 0.3, 1))
            mb.tube([(bx, y0 + 0.02, z - 0.03), (bx, wall_y - 0.01, z - 0.32)], 0.012, "metal_painted",
                    (0.35, 0.33, 0.3, 1), square=True)
            mb.box((bx - 0.03, wall_y - 0.01, z - 0.36), (bx + 0.03, wall_y, z - 0.05), "metal_painted",
                   (0.35, 0.33, 0.3, 1))
    ctx.col((x0, y0, z), (x1, y1, z + h), "metal")
    if bracket:
        ctx.col((x0, y1, z - 0.04), (x1, wall_y, z), "metal")
    if nap:
        ctx.nap.append(V((cx, (y0 + y1) / 2, z + h)))
    ctx.ledge(x0, x1, wall_y, z, 1.4)
    if drip:
        decal(ctx, "ac_drip", cx + rng.uniform(-0.1, 0.1), z - 0.02, w * 0.9, rng.uniform(1.2, 2.4), wall_y - 0.004)


def drainpipe(ctx: Ctx, x, z0, z1, wall_y=0.0, mat="plastic", tint=(0.72, 0.73, 0.72, 1), r=0.045,
              offset=0.07, top_out=0.25):
    """Vertical downpipe with clips, top elbow to the roof edge and a shoe. Climbable."""
    mb = ctx.clutter
    y = wall_y - offset
    mb.tube([(x, y, z0 + 0.12), (x, y, z1)], r, mat, tint, sides=10)
    mb.tube([(x, y, z0 + 0.12), (x, y - 0.06, z0 + 0.03), (x, y - 0.12, z0 + 0.02)], r, mat, tint, sides=10)
    mb.tube([(x, y, z1), (x, y, z1 + 0.1), (x, wall_y - top_out * 0.2, z1 + 0.22), (x, wall_y + 0.05, z1 + 0.25)],
            r, mat, tint, sides=10)
    z = z0 + 1.2
    while z < z1 - 0.3:
        mb.box((x - r - 0.012, y - r - 0.012, z), (x + r + 0.012, wall_y, z + 0.03), "metal_painted",
               (0.4, 0.38, 0.35, 1))
        z += ctx.rng.uniform(1.4, 2.0)
    ctx.col((x - r, y - r, z0), (x + r, wall_y, z1 + 0.25), "plastic" if mat == "plastic" else "metal", ("climb",))
    ctx.climb.append(V((x, y - r, z0 + 0.3)))
    ctx.climb.append(V((x, y - r, z1)))
    if ctx.rng.random() < 0.7:
        decal(ctx, "streak_1", x, z0 + 0.6, 0.6, 0.6, wall_y - 0.003)


def cable_run(ctx: Ctx, x0, x1, z, wall_y=0.0, n=5, sag=0.08, drops=()):
    """Bundle of cables clamped along a wall with sagging spans + vertical drops."""
    mb = ctx.clutter
    rng = ctx.rng
    span = rng.uniform(1.2, 1.8)
    nsp = max(1, int(abs(x1 - x0) / span))
    for c in range(n):
        r = rng.choice([0.004, 0.006, 0.006, 0.008, 0.011])
        col = rng.choice([(1, 1, 1, 1), (1, 1, 1, 1), (1, 1, 1, 1), (6, 6, 6, 1), (2.5, 2.5, 2.3, 1)])
        yy = wall_y - 0.03 - c * 0.012
        dz = rng.uniform(-0.03, 0.03)
        pts = []
        for s in range(nsp):
            a = (x0 + (x1 - x0) * s / nsp, yy, z + dz)
            b = (x0 + (x1 - x0) * (s + 1) / nsp, yy, z + dz)
            seg = G.catenary(a, b, sag * rng.uniform(0.5, 1.6) + c * 0.01, 8, 0.004, rng)
            pts.extend(seg if not pts else seg[1:])
        mb.tube(pts, r, "rubber", col, sides=5, caps=False)
    for s in range(nsp + 1):
        cx = x0 + (x1 - x0) * s / nsp
        mb.box((cx - 0.02, wall_y - 0.03 - n * 0.012, z - 0.02), (cx + 0.02, wall_y, z + 0.03), "metal_painted",
               (0.3, 0.3, 0.3, 1))
    for (dx, dz0) in drops:
        for c in range(rng.randint(2, 4)):
            r = rng.choice([0.005, 0.007])
            xx = dx + c * 0.018
            pts = [(xx, wall_y - 0.03, z), (xx + rng.uniform(-0.02, 0.02), wall_y - 0.025, (z + dz0) / 2),
                   (xx, wall_y - 0.02, dz0)]
            mb.tube(pts, r, "rubber", WHITE, sides=5, caps=False)
    ctx.ledge(min(x0, x1), max(x0, x1), wall_y, z, 0.3)


def meter_cluster(ctx: Ctx, cx, z, wall_y=0.0, n=4):
    """Electricity meters in a grey steel cabinet with clear windows (very common on piers)."""
    mb = ctx.clutter
    rng = ctx.rng
    w, h = 0.16 * n + 0.08, 0.5
    mb.box((cx - w / 2, wall_y - 0.16, z), (cx + w / 2, wall_y, z + h), "metal_painted", (0.62, 0.64, 0.62, 1),
           bevel=0.01)
    for k in range(n):
        x = cx - w / 2 + 0.06 + k * 0.16
        mb.box((x, wall_y - 0.17, z + 0.12), (x + 0.12, wall_y - 0.16, z + 0.32), "glass_clear", WHITE)
        mb.box((x + 0.02, wall_y - 0.166, z + 0.2), (x + 0.1, wall_y - 0.165, z + 0.26), "plastic",
               (0.9, 0.9, 0.85, 1))
    mb.box((cx - w / 2 + 0.02, wall_y - 0.2, z + h), (cx + w / 2 - 0.02, wall_y, z + h + 0.03), "metal_painted",
           (0.5, 0.5, 0.48, 1))
    ctx.col((cx - w / 2, wall_y - 0.2, z), (cx + w / 2, wall_y, z + h + 0.03), "metal")
    ctx.ledge(cx - w / 2, cx + w / 2, wall_y, z, 1.0)


def corrugated_sheet(ctx: Ctx, x0, x1, y_back, y_front, z_back, z_front, mat="corrugated_rusted", pitch=0.076,
                     amp=0.009, mb=None, collide=False, tint=WHITE):
    """Corrugated metal sheet: waves run along x, slope from back (y_back,z_back) to front.
    UVs: V along the slope (rust streaks flow downhill)."""
    mb = mb or ctx.clutter
    import bmesh
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    nx = max(2, int(abs(x1 - x0) / pitch * 6))
    a = V((0, y_back, z_back))
    b = V((0, y_front, z_front))
    L = (b - a).length
    nrm = (b - a).cross(V((1, 0, 0))).normalized()
    if nrm.z < 0:
        nrm = -nrm
    rows_b, rows_f = [], []
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        off = math.sin((x - x0) / pitch * 2 * math.pi) * amp
        rows_b.append(bm.verts.new(V((x, a.y, a.z)) + nrm * off))
        rows_f.append(bm.verts.new(V((x, b.y, b.z)) + nrm * off))
    tm = 2.0
    for i in range(nx):
        f = bm.faces.new([rows_b[i], rows_b[i + 1], rows_f[i + 1], rows_f[i]])
        xa = x0 + (x1 - x0) * i / nx
        xb = x0 + (x1 - x0) * (i + 1) / nx
        uvs = [(xa / tm, L / tm), (xb / tm, L / tm), (xb / tm, 0), (xa / tm, 0)]
        for l, uv in zip(f.loops, uvs):
            l[uvl].uv = uv
        if f.normal.dot(nrm) < 0:
            f.normal_flip()
    # underside copy (flipped) so it is visible from below
    bm2 = bm.copy()
    for f in bm2.faces:
        f.normal_flip()
    for v in bm2.verts:
        v.co -= nrm * 0.0015
    mb.add_bm(bm, mat, tint, "keep", src_uv=True, smooth=True)
    mb.add_bm(bm2, mat, mul(tint, 0.6), "keep", src_uv=True, smooth=True)
    if collide:
        M, L = slope_xform(a, b)
        ctx.col((x0, -L / 2, -0.02), (x1, L / 2, 0.02), "metal", (), M)


def roof_plane(ctx: Ctx, x0, x1, y_low, z_low, y_high, z_high, mat="roof_tile_terracotta", mb=None,
               rows=True, row_len=0.333, tint=WHITE, collide=True, surface="roof_tile", thick=0.05):
    """Tiled pitched-roof plane between an eave line (y_low,z_low) and the upper line. UV V upslope
    (texture rows align with real tile courses). rows=True adds a small step per course so the
    silhouette at the verges/eaves shows real overlapping tiles."""
    mb = mb or ctx.shell
    import bmesh
    a = V((0, y_low, z_low))
    b = V((0, y_high, z_high))
    L = (b - a).length
    d = (b - a).normalized()
    nrm = V((1, 0, 0)).cross(d)
    if nrm.z < 0:
        nrm = -nrm
    tm = 2.0
    nrow = max(1, int(round(L / row_len))) if rows else 1
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    step = 0.018
    for r in range(nrow):
        p0 = a + d * (L * r / nrow)
        p1 = a + d * (L * (r + 1) / nrow)
        lift = nrm * step if rows else V((0, 0, 0))
        q = [V((x0, 0, 0)) + p0 + lift, V((x1, 0, 0)) + p0 + lift, V((x1, 0, 0)) + p1, V((x0, 0, 0)) + p1]
        vs = [bm.verts.new(v) for v in q]
        f = bm.faces.new(vs)
        v0 = L * r / nrow / tm
        v1 = L * (r + 1) / nrow / tm
        for l, uv in zip(f.loops, [(x0 / tm, v0), (x1 / tm, v0), (x1 / tm, v1), (x0 / tm, v1)]):
            l[uvl].uv = uv
        if rows:  # course lip (vertical-ish face at the bottom of each course)
            lip = [V((x0, 0, 0)) + p0 + lift, V((x1, 0, 0)) + p0 + lift, V((x1, 0, 0)) + p0 - nrm * 0.004,
                   V((x0, 0, 0)) + p0 - nrm * 0.004]
            vs2 = [bm.verts.new(v) for v in lip]
            f2 = bm.faces.new(vs2)
            for l, uv in zip(f2.loops, [(x0 / tm, v0), (x1 / tm, v0), (x1 / tm, v0 + 0.004), (x0 / tm, v0 + 0.004)]):
                l[uvl].uv = uv
            if f2.normal.dot(-d) < 0:
                f2.normal_flip()
    for f in bm.faces:
        if f.normal.dot(nrm) < -0.5:
            f.normal_flip()
    mb.add_bm(bm, mat, tint, "keep", src_uv=True)
    # underside (eave soffit) + edges
    q = [V((x0, 0, 0)) + a - nrm * thick, V((x1, 0, 0)) + a - nrm * thick, V((x1, 0, 0)) + b - nrm * thick,
         V((x0, 0, 0)) + b - nrm * thick]
    quad_n(mb, q, "wood_brown", (0.7, 0.7, 0.7, 1), -nrm)
    quad_n(mb, [V((x0, 0, 0)) + a - nrm * thick, V((x1, 0, 0)) + a - nrm * thick, V((x1, 0, 0)) + a + nrm * step,
                V((x0, 0, 0)) + a + nrm * step], "wood_brown", WHITE, -d)
    for xs, sgn in ((x0, -1), (x1, 1)):
        quad_n(mb, [V((xs, 0, 0)) + a - nrm * thick, V((xs, 0, 0)) + b - nrm * thick, V((xs, 0, 0)) + b + nrm * step,
                    V((xs, 0, 0)) + a + nrm * step], "wood_brown", WHITE, (sgn, 0, 0))
    if collide:
        M, L = slope_xform(a, b)
        ctx.col((x0, -L / 2, -thick), (x1, L / 2, step + 0.005), surface, (), M)


def awning_tile(ctx: Ctx, x0, x1, z, proj, slope_deg=22, wall_y=0.0, brackets=True):
    """Colonial terracotta-tile pent roof over the sidewalk on cast-iron brackets."""
    dz = math.tan(math.radians(slope_deg)) * proj
    roof_plane(ctx, x0, x1, wall_y - proj, z, wall_y + 0.02, z + dz, "roof_tile_terracotta", ctx.shell,
               row_len=0.333)
    # ridge flashing against the wall
    ctx.shell.box((x0, wall_y - 0.08, z + dz - 0.02), (x1, wall_y + 0.01, z + dz + 0.06), "cement_render",
                  WHITE, bevel=0.01)
    # fascia board
    ctx.shell.box((x0, wall_y - proj - 0.03, z - 0.12), (x1, wall_y - proj + 0.01, z + 0.01), "wood_brown",
                  WHITE, uvmode="grain_h")
    if brackets:
        nb = max(2, int((x1 - x0) / 1.6) + 1)
        for k in range(nb):
            bx = x0 + 0.1 + k * (x1 - x0 - 0.2) / (nb - 1)
            pts = [(bx, wall_y, z - 0.75), (bx, wall_y - proj * 0.5, z - 0.3), (bx, wall_y - proj + 0.05, z - 0.06)]
            ctx.detail.tube(pts, 0.012, "iron_wrought", square=True)
            ctx.detail.tube([(bx, wall_y, z - 0.02), (bx, wall_y - proj + 0.05, z - 0.04)], 0.014, "iron_wrought",
                            square=True)
            sc = scroll_points(0, 0, 0.12, 1.1, 0, 1, 18)
            ctx.detail.tube([(bx, wall_y - 0.15 - sx * 0.8, z - 0.25 + sz) for sx, sz in sc], 0.006, "iron_wrought",
                            square=True)
            ctx.detail.box((bx - 0.04, wall_y - 0.02, z - 0.8), (bx + 0.04, wall_y, z - 0.6), "iron_wrought")
    ctx.ledge(x0, x1, wall_y - proj, z - 0.12, 1.0)
    ctx.nap.append(V(((x0 + x1) / 2 + ctx.rng.uniform(-0.5, 0.5), wall_y - proj * 0.5, z + dz * 0.5 + 0.03)))


def awning_corrugated(ctx: Ctx, x0, x1, z, proj, slope_deg=10, wall_y=0.0, mat="corrugated_blue"):
    dz = math.tan(math.radians(slope_deg)) * proj
    corrugated_sheet(ctx, x0, x1, wall_y + 0.01, wall_y - proj, z + dz, z, mat, mb=ctx.shell, collide=False)
    # steel angle frame + braces
    t = (0.3, 0.3, 0.3, 1)
    ctx.detail.box((x0, wall_y - proj - 0.01, z - 0.05), (x1, wall_y - proj + 0.03, z - 0.01), "metal_painted", t)
    ctx.detail.box((x0, wall_y - 0.04, z + dz - 0.06), (x1, wall_y, z + dz - 0.02), "metal_painted", t)
    nb = max(2, int((x1 - x0) / 1.5) + 1)
    for k in range(nb):
        bx = x0 + 0.05 + k * (x1 - x0 - 0.1) / (nb - 1)
        ctx.detail.tube([(bx, wall_y, z + dz - 0.04), (bx, wall_y - proj, z - 0.03)], 0.015, "metal_painted", t,
                        square=True)
        ctx.detail.tube([(bx, wall_y, z - 0.6), (bx, wall_y - proj * 0.6, z - 0.03)], 0.012, "metal_painted", t,
                        square=True)
    M, L = slope_xform((0, wall_y - proj, z), (0, wall_y, z + dz))
    ctx.col((x0, -L / 2, -0.03), (x1, L / 2, 0.025), "metal", (), M)
    ctx.ledge(x0, x1, wall_y - proj, z, 1.0)
    ctx.nap.append(V(((x0 + x1) / 2, wall_y - proj * 0.5, z + dz * 0.5 + 0.02)))


def awning_canvas(ctx: Ctx, x0, x1, z, proj, color, slope_deg=25, wall_y=0.0, valance=0.22, scallop=True):
    """Fabric awning with valance on steel arms (tinted canvas)."""
    import bmesh
    dz = math.tan(math.radians(slope_deg)) * proj
    mb = ctx.shell
    # main fabric with slight sag between arms
    nx = max(4, int((x1 - x0) / 0.25))
    ny = 4
    bm = bmesh.new()
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            x = x0 + (x1 - x0) * u
            y = wall_y - proj * v
            zz = z + dz * (1 - v) - 0.03 * math.sin(math.pi * v) * (0.6 + 0.4 * abs(math.sin(u * math.pi * 3)))
            row.append(bm.verts.new((x, y, zz)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new([grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]])
            if f.normal.z < 0:
                f.normal_flip()
    bm2 = bm.copy()
    for f in bm2.faces:
        f.normal_flip()
    mb.add_bm(bm, "fabric_canvas", color)
    mb.add_bm(bm2, "fabric_canvas", mul(color, 0.75))
    # valance (front skirt), scalloped edge
    vb = bmesh.new()
    n = max(6, int((x1 - x0) / 0.06))
    top = [vb.verts.new((x0 + (x1 - x0) * i / n, wall_y - proj, z)) for i in range(n + 1)]
    bot = []
    for i in range(n + 1):
        u = i / n
        sc = (0.05 * (1 - abs(math.sin(u * (x1 - x0) / 0.3 * math.pi)))) if scallop else 0
        bot.append(vb.verts.new((x0 + (x1 - x0) * u, wall_y - proj, z - valance + sc)))
    for i in range(n):
        f = vb.faces.new([top[i], top[i + 1], bot[i + 1], bot[i]])
        if f.normal.y > 0:
            f.normal_flip()
    vb2 = vb.copy()
    for f in vb2.faces:
        f.normal_flip()
    mb.add_bm(vb, "fabric_canvas", color)
    mb.add_bm(vb2, "fabric_canvas", mul(color, 0.7))
    t = (0.25, 0.25, 0.25, 1)
    ctx.detail.tube([(x0, wall_y - proj, z), (x1, wall_y - proj, z)], 0.012, "metal_painted", t)
    for bx in (x0 + 0.05, x1 - 0.05):
        ctx.detail.tube([(bx, wall_y, z + dz), (bx, wall_y - proj, z)], 0.012, "metal_painted", t)
        ctx.detail.tube([(bx, wall_y, z - 0.5), (bx, wall_y - proj * 0.7, z + dz * 0.3)], 0.01, "metal_painted", t)
    M, L = slope_xform((0, wall_y - proj, z), (0, wall_y, z + dz))
    ctx.col((x0, -L / 2, -0.03), (x1, L / 2, 0.0), "fabric", (), M)
    ctx.ledge(x0, x1, wall_y - proj, z - valance, 0.6)


def rolling_shutter(ctx: Ctx, x0, x1, z0, z1, open_frac, wall_y=0.0, tint=None):
    """Steel roller shutter: box housing, guide rails, curtain lowered to (1-open_frac)."""
    rng = ctx.rng
    tint = tint or rng.choice([(1, 1, 1, 1), (1, 1, 1, 1), (0.55, 0.7, 0.85, 1), (0.6, 0.78, 0.62, 1),
                               (0.95, 0.88, 0.7, 1)])
    hb = 0.32
    ctx.detail.box((x0 - 0.05, wall_y - 0.33, z1 - hb), (x1 + 0.05, wall_y + 0.01, z1), "metal_painted",
                   mul(tint, 0.9), bevel=0.01)
    for x in (x0, x1 - 0.06):
        ctx.detail.box((x, wall_y - 0.1, z0), (x + 0.06, wall_y - 0.02, z1 - hb), "metal_painted", mul(tint, 0.8))
    zc = z0 + (z1 - hb - z0) * open_frac
    if zc < z1 - hb - 0.05:
        # curtain plane with slat texture (V along height)
        uvs = [(x0, zc), (x1, zc), (x1, z1 - hb), (x0, z1 - hb)]
        uvs = [(u, v) for u, v in uvs]
        front_rect(ctx.detail, x0 + 0.02, zc, x1 - 0.02, z1 - hb, wall_y - 0.06, "steel_shutter", tint)
        front_rect(ctx.detail, x0 + 0.02, zc, x1 - 0.02, z1 - hb, wall_y - 0.055, "steel_shutter", mul(tint, 0.5),
                   n=(0, 1, 0))
        ctx.detail.box((x0 + 0.02, wall_y - 0.085, zc), (x1 - 0.02, wall_y - 0.035, zc + 0.06), "metal_painted",
                       mul(tint, 0.7), bevel=0.006)
        if open_frac < 0.02:
            for hx in (x0 + (x1 - x0) * 0.35, x0 + (x1 - x0) * 0.65):
                ctx.detail.box((hx - 0.03, wall_y - 0.1, zc + 0.02), (hx + 0.03, wall_y - 0.085, zc + 0.1), "chrome")
        ctx.col((x0, wall_y - 0.09, zc), (x1, wall_y - 0.03, z1 - hb), "metal", ("wall",))
    ctx.col((x0 - 0.05, wall_y - 0.33, z1 - hb), (x1 + 0.05, wall_y, z1), "metal")
    return zc


def shop_interior(ctx: Ctx, x0, x1, z0, z1, depth, kind="grocery", wall_y=0.0, floor_mat="terrazzo",
                  lit=True, back_cells=None):
    """Shallow shop interior behind the shopfront so the opening is never a flat black plane."""
    import city_mats as CM
    sh, de = ctx.shell, ctx.detail
    rng = ctx.rng
    yb = wall_y + depth
    # floor + threshold step
    sh.box((x0, wall_y - 0.3, 0), (x1, yb, z0), floor_mat, WHITE, skip=("-z", "+y"))
    sh.box((x0 - 0.02, wall_y - 0.32, 0), (x1 + 0.02, wall_y - 0.28, z0 + 0.005), "granite_red", WHITE)
    # walls + ceiling
    wt = (0.92, 0.9, 0.84, 1)
    for xs, n in ((x0, (1, 0, 0)), (x1, (-1, 0, 0))):
        quad_n(sh, [(xs, wall_y, z0), (xs, yb, z0), (xs, yb, z1), (xs, wall_y, z1)], "plaster_white", wt, n)
    quad_n(sh, [(x0, wall_y, z1), (x1, wall_y, z1), (x1, yb, z1), (x0, yb, z1)], "plaster_white",
           (0.6, 0.6, 0.58, 1), (0, 0, -1))
    # back wall with goods
    cells = back_cells or {
        "grocery": ["grocery", "noodles", "snacks", "drinks"], "pho": ["kitchen", "wall_tile", "altar"],
        "rattan": ["calendar_wall", "altar", "dark_back"], "pharmacy": ["pharmacy", "pharmacy", "snacks"],
        "hardware": ["hardware", "paint_cans", "hardware"], "phones": ["phones", "phones", "calendar_wall"],
        "tailor": ["fabric", "fabric", "calendar_wall"], "cafe": ["calendar_wall", "drinks", "dark_back"],
        "home": ["calendar_wall", "altar", "dark_back"], "gold": ["altar", "dark_back", "phones"],
    }.get(kind, ["grocery", "drinks"])
    nseg = len(cells)
    for i, c in enumerate(cells):
        a = x0 + (x1 - x0) * i / nseg
        b = x0 + (x1 - x0) * (i + 1) / nseg
        r = CM.atlas_cell("goods_atlas", c)
        front_rect(sh, a, z0, b, z1 - 0.3, yb, "goods", WHITE, atlas_uv(r, 0.004))
        front_rect(sh, a, z1 - 0.3, b, z1, yb, "plaster_white", (0.5, 0.5, 0.48, 1))
    # shelves along the side walls with goods faces
    if kind not in ("home", "cafe", "pho"):
        for xs, sgn in ((x0, 1), (x1, -1)):
            for k in range(4):
                zz = z0 + 0.4 + k * 0.42
                if zz > z1 - 0.4:
                    break
                de.box((min(xs, xs + sgn * 0.35), wall_y + 0.2, zz), (max(xs, xs + sgn * 0.35), yb - 0.05, zz + 0.025),
                       "wood_brown", WHITE)
                if kind == "rattan":
                    yy_ = wall_y + 0.45
                    while yy_ < yb - 0.3:
                        rr = rng.uniform(0.09, 0.14)
                        basket(de, xs + sgn * 0.16, yy_, zz + 0.025, rr, rr * 0.8, mul(WHITE, rng.uniform(0.75, 1.05)),
                               rng.choice(["bowl", "bowl", "jar"]))
                        yy_ += rr * 2.2
                    continue
                r = CM.atlas_cell("goods_atlas", rng.choice(cells))
                u0, v0, u1, v1 = r
                vv = v0 + (v1 - v0) * rng.uniform(0, 0.6)
                quad_n(de, [(xs + sgn * 0.3, wall_y + 0.2, zz + 0.025), (xs + sgn * 0.3, yb - 0.05, zz + 0.025),
                            (xs + sgn * 0.3, yb - 0.05, zz + 0.33), (xs + sgn * 0.3, wall_y + 0.2, zz + 0.33)],
                       "goods", WHITE, (sgn, 0, 0), ([(u0, vv), (u1, vv), (u1, vv + (v1 - v0) * 0.35),
                                                      (u0, vv + (v1 - v0) * 0.35)] if sgn > 0 else
                                                     [(u1, vv), (u0, vv), (u0, vv + (v1 - v0) * 0.35),
                                                      (u1, vv + (v1 - v0) * 0.35)]))
    if kind == "rattan":  # stacks of big baskets and trays against the back wall
        sx = x0 + 0.45
        while sx < x1 - 0.4:
            rr = rng.uniform(0.22, 0.32)
            zz = z0
            for q in range(rng.randint(3, 7)):
                basket(de, sx, yb - 0.4, zz, rr, rr * 0.6, mul(WHITE, rng.uniform(0.75, 1.05)), "bowl")
                zz += rr * 0.22
                rr *= 0.97
            sx += 0.62
    # counter / glass cabinet near the front
    if kind in ("grocery", "pharmacy", "phones", "gold", "tailor"):
        cx0 = x0 + 0.1 if rng.random() < 0.5 else x1 - 1.4
        de.box((cx0, wall_y + 0.5, z0), (cx0 + 1.3, wall_y + 1.0, z0 + 0.9), "wood_brown", WHITE, bevel=0.01)
        de.box((cx0 + 0.02, wall_y + 0.52, z0 + 0.9), (cx0 + 1.28, wall_y + 0.98, z0 + 0.92), "glass_clear")
        ctx.col((cx0, wall_y + 0.5, z0), (cx0 + 1.3, wall_y + 1.0, z0 + 0.92), "wood")
    if kind == "pho":
        de.box((x0 + 0.2, wall_y + 0.3, z0), (x0 + 1.2, wall_y + 0.8, z0 + 0.8), "stainless", WHITE, bevel=0.01)
        de.cylinder((x0 + 0.5, wall_y + 0.55, z0 + 0.8), (0, 0, 1), 0.22, 0.45, "stainless", sides=16)
        ctx.col((x0 + 0.2, wall_y + 0.3, z0), (x0 + 1.2, wall_y + 0.8, z0 + 0.8), "metal")
    # fluorescent tube
    lx = (x0 + x1) / 2
    de.box((lx - 0.6, wall_y + depth * 0.5 - 0.03, z1 - 0.06), (lx + 0.6, wall_y + depth * 0.5 + 0.03, z1 - 0.02),
           "lamp" if lit else "plastic", WHITE)
    if lit:
        ctx.lights.append(V((lx, wall_y + depth * 0.5, z1 - 0.25)))
    # colliders: floor, back wall, side walls, ceiling
    ctx.col((x0, wall_y - 0.3, 0), (x1, yb, z0), "tile")
    ctx.col((x0, yb, z0), (x1, yb + 0.1, z1), "concrete", ("wall",))
    ctx.col((x0 - 0.1, wall_y, z0), (x0, yb, z1), "concrete", ("wall",))
    ctx.col((x1, wall_y, z0), (x1 + 0.1, yb, z1), "concrete", ("wall",))
    ctx.entr.append(V(((x0 + x1) / 2, wall_y - 0.2, z0)))


def sign_board(ctx: Ctx, x0, x1, z0, z1, sign_id, wall_y=0.0, proj=0.08, frame_tint=(0.35, 0.33, 0.3, 1), lit=False):
    import city_mats as CM
    r = CM.atlas_cell("signs_a", sign_id)
    y = wall_y - proj
    ctx.clutter.box((x0, y + 0.005, z0), (x1, wall_y - 0.01, z1), "metal_painted", frame_tint, bevel=0.008,
                    skip=("+y",))
    front_rect(ctx.clutter, x0 + 0.02, z0 + 0.02, x1 - 0.02, z1 - 0.02, y, "signs_lit" if lit else "signs", WHITE,
               atlas_uv(r, 0.002))
    for x in (x0 + 0.15, x1 - 0.15):
        ctx.clutter.box((x - 0.02, wall_y - 0.02, z1 - 0.05), (x + 0.02, wall_y, z1 + 0.05), "metal_painted", frame_tint)
    ctx.col((x0, y, z0), (x1, wall_y, z1), "metal")
    ctx.ledge(x0, x1, wall_y, z0, 0.8)
    if ctx.rng.random() < 0.5:
        decal(ctx, "rust_streak", x0 + 0.1, z0, 0.2, 0.7, wall_y - 0.003)


def vsign(ctx: Ctx, x, z0, cell, wall_y=0.0, out=0.55, w=0.32, h=1.3):
    """Vertical blade sign projecting from the facade (double sided)."""
    import city_mats as CM
    r = CM.atlas_cell("signs_v", cell)
    y0 = wall_y - out
    mb = ctx.clutter
    mb.box((x - 0.03, y0 - 0.005, z0 - 0.02), (x + 0.03, y0 + w + 0.005, z0 + h + 0.02), "metal_painted",
           (0.3, 0.3, 0.3, 1), bevel=0.008)
    for s in (-1, 1):
        xs = x + s * 0.031
        quad_n(mb, [(xs, y0, z0), (xs, y0 + w, z0), (xs, y0 + w, z0 + h), (xs, y0, z0 + h)], "signs_v", WHITE,
               (s, 0, 0), [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])] if s < 0 else
               [(r[2], r[1]), (r[0], r[1]), (r[0], r[3]), (r[2], r[3])])
    mb.tube([(x, wall_y, z0 + h + 0.15), (x, y0 + 0.05, z0 + h)], 0.008, "metal_painted", (0.3, 0.3, 0.3, 1))
    mb.box((x - 0.04, wall_y - 0.02, z0 + h * 0.3), (x + 0.04, wall_y, z0 + h * 0.7), "metal_painted")
    mb.box((x - 0.012, y0 + w, z0 + h * 0.45), (x + 0.012, wall_y, z0 + h * 0.5), "metal_painted")
    ctx.col((x - 0.035, y0, z0), (x + 0.035, y0 + w, z0 + h), "metal")


def house_number(ctx: Ctx, x, z, num_cell, wall_y=0.0):
    import city_mats as CM
    r = CM.atlas_cell("signs_v", num_cell)
    front_rect(ctx.clutter, x - 0.1, z, x + 0.1, z + 0.12, wall_y - 0.006, "signs_v", WHITE, atlas_uv(r, 0.002))


# ---------------------------------------------------------------------------
# Plants, laundry
# ---------------------------------------------------------------------------
def foliage_card(ctx: Ctx, cx, cy, z, w, h, cell, rot_deg=0.0, tint=WHITE, lean=0.0):
    import city_mats as CM
    r = CM.atlas_cell("foliage_atlas", cell)
    a = math.radians(rot_deg)
    dx, dy = math.cos(a) * w / 2, math.sin(a) * w / 2
    top_off = V((-math.sin(a) * lean, math.cos(a) * lean, 0))
    pts = [V((cx - dx, cy - dy, z)), V((cx + dx, cy + dy, z)), V((cx + dx, cy + dy, z + h)) + top_off,
           V((cx - dx, cy - dy, z + h)) + top_off]
    ctx.foliage.quad(pts, "foliage", tint, uvs=atlas_uv(r, 0.003))


def potted_plant(ctx: Ctx, x, y, z, size=0.5, kind=None, pot="terracotta"):
    rng = ctx.rng
    kind = kind or rng.choice(["leafy", "leafy", "fern", "bougainvillea"])
    pr = size * rng.uniform(0.28, 0.38)
    ph = size * rng.uniform(0.45, 0.6)
    ptint = {"terracotta": (0.62, 0.32, 0.2, 1), "white": (0.85, 0.85, 0.82, 1), "blue": (0.2, 0.32, 0.55, 1),
             "styro": (0.92, 0.92, 0.9, 1)}[pot]
    if pot == "styro":
        ctx.clutter.box((x - size * 0.4, y - size * 0.3, z), (x + size * 0.4, y + size * 0.3, z + ph * 0.7),
                        "plastic_matte", ptint, bevel=0.01)
    else:
        ctx.clutter.tube([(x, y, z), (x, y, z + ph)], pr, "plastic_matte" if pot != "terracotta" else "plastic_matte",
                         ptint, sides=12, radii=[pr * 0.75, pr])
    ctx.clutter.cylinder((x, y, z + ph * 0.92), (0, 0, 1), pr * 0.95, 0.01, "dark", sides=12)
    tint = mul(WHITE, rng.uniform(0.75, 1.05))
    hh = size * rng.uniform(1.0, 1.6)
    for k in range(3):
        foliage_card(ctx, x, y, z + ph * 0.6, size * 1.25, hh, kind, rng.uniform(0, 180), tint)


def bougainvillea_cascade(ctx: Ctx, x0, x1, z_top, wall_y, drop=1.6):
    """Bougainvillea spilling over a balcony rail + trailing vines."""
    rng = ctx.rng
    x = x0
    while x < x1:
        w = rng.uniform(0.6, 1.1)
        foliage_card(ctx, x + w / 2, wall_y - 0.06, z_top - drop * rng.uniform(0.5, 0.9), w * 1.2, drop,
                     "bougainvillea", rng.uniform(-10, 10), mul(WHITE, rng.uniform(0.8, 1.0)), lean=-0.15)
        foliage_card(ctx, x + w / 2, wall_y - 0.15, z_top - 0.2, w, 0.7, "bougainvillea", rng.uniform(60, 120))
        if rng.random() < 0.6:
            foliage_card(ctx, x + w * 0.3, wall_y - 0.08, z_top - drop * 1.2, 0.5, drop * 1.1, "vine", 0)
        x += w * rng.uniform(0.7, 1.0)


def laundry_line(ctx: Ctx, a, b, sag=0.06, density=0.7):
    import city_mats as CM
    rng = ctx.rng
    pts = G.catenary(a, b, sag, 10)
    ctx.clutter.tube(pts, 0.003, "rubber", (3, 3, 3, 1), sides=4, caps=False)
    A, B = V(a), V(b)
    L = (B - A).length
    d = (B - A).normalized()
    cells = list(CM.ATLAS["laundry_atlas"]["cells"].keys())
    t = rng.uniform(0.05, 0.2)
    while t < 0.95:
        gw = rng.uniform(0.35, 0.6)
        gh = gw * rng.uniform(1.0, 1.6)
        if rng.random() < density:
            p = A.lerp(B, t)
            p.z -= sag * 4 * t * (1 - t)
            c = rng.choice(cells)
            r = CM.atlas_cell("laundry_atlas", c)
            side = V((-d.y, d.x, 0)) * rng.uniform(-0.03, 0.03)
            p0 = p - d * gw / 2
            p1 = p + d * gw / 2
            pts4 = [p0 - V((0, 0, gh)) + side, p1 - V((0, 0, gh)) + side, p1, p0]
            ctx.foliage.quad(pts4, "laundry", mul(WHITE, rng.uniform(0.8, 1.0)), uvs=atlas_uv(r, 0.003))
            for q in (p0, p1):  # pegs
                ctx.clutter.box(q - V((0.008, 0.008, 0.04)), q + V((0.008, 0.008, 0.01)), "plastic",
                                rng.choice([(0.9, 0.2, 0.2, 1), (0.2, 0.5, 0.9, 1), (0.95, 0.8, 0.2, 1)]))
        t += (gw + rng.uniform(0.05, 0.25)) / L


# ---------------------------------------------------------------------------
# Rooftop pieces
# ---------------------------------------------------------------------------
def water_tank(ctx: Ctx, x, y, z, kind="horizontal", nap=True):
    mb = ctx.clutter
    rng = ctx.rng
    if kind == "horizontal":
        L, r = rng.choice([(1.6, 0.48), (1.9, 0.5), (1.4, 0.45)])
        st = (0.3, 0.3, 0.3, 1)
        for sx in (x - L * 0.35, x + L * 0.35):  # saddle stand
            mb.box((sx - 0.03, y - r * 0.8, z), (sx + 0.03, y + r * 0.8, z + 0.35), "metal_painted", st)
        mb.box((x - L * 0.45, y - r * 0.85, z), (x + L * 0.45, y - r * 0.8, z + 0.05), "metal_painted", st)
        mb.box((x - L * 0.45, y + r * 0.8, z), (x + L * 0.45, y + r * 0.85, z + 0.05), "metal_painted", st)
        cz = z + 0.35 + r
        mb.tube([(x - L / 2, y, cz), (x + L / 2, y, cz)], r, "stainless", sides=24, smooth=True)
        for sx, sg in ((x - L / 2, -1), (x + L / 2, 1)):  # dished ends
            mb.tube([(sx, y, cz), (sx + sg * 0.06, y, cz)], r * 0.98, "stainless", sides=24,
                    radii=[r, r * 0.6])
        for sx in (x - L * 0.25, x + L * 0.25):  # rings
            mb.tube([(sx, y, cz), (sx + 0.03, y, cz)], r * 1.012, "stainless", sides=24, caps=False)
        mb.cylinder((x, y, cz + r * 0.95), (0, 0, 1), 0.12, 0.08, "stainless", sides=16)
        mb.tube([(x + L / 2 - 0.1, y + r * 0.6, cz - r * 0.6), (x + L / 2 + 0.2, y + r * 0.6, cz - r * 0.7),
                 (x + L / 2 + 0.25, y + r * 0.6, z + 0.05)], 0.02, "plastic", (0.85, 0.85, 0.8, 1), sides=8)
        ctx.col((x - L / 2, y - r, z + 0.35), (x + L / 2, y + r, cz + r), "metal")
        ctx.col((x - L * 0.45, y - r * 0.85, z), (x + L * 0.45, y + r * 0.85, z + 0.35), "metal")
        if nap:
            ctx.nap.append(V((x, y, cz + r)))
        return cz + r
    else:
        H, r = 1.3, 0.55
        mb.tube([(x, y, z + 0.25), (x, y, z + 0.25 + H)], r, "stainless", sides=24)
        mb.tube([(x, y, z + 0.25 + H), (x, y, z + 0.25 + H + 0.18)], r, "stainless", sides=24, radii=[r, 0.15])
        for k in range(4):
            a = math.pi / 2 * k + 0.4
            mb.box((x + math.cos(a) * r * 0.8 - 0.03, y + math.sin(a) * r * 0.8 - 0.03, z),
                   (x + math.cos(a) * r * 0.8 + 0.03, y + math.sin(a) * r * 0.8 + 0.03, z + 0.3), "metal_painted",
                   (0.3, 0.3, 0.3, 1))
        ctx.col((x - r, y - r, z), (x + r, y + r, z + 0.25 + H + 0.1), "metal")
        if nap:
            ctx.nap.append(V((x, y, z + 0.25 + H + 0.1)))
        return z + 0.25 + H + 0.18


def solar_heater(ctx: Ctx, x, y, z, ntubes=14, facing_deg=0.0):
    """Evacuated-tube solar water heater: tank on top, inclined glass tubes, steel frame."""
    mb = ctx.clutter
    mk = len(mb.bm.verts)
    W = ntubes * 0.075
    tilt = math.radians(35)
    L = 1.75
    tank_r = 0.2
    tz = z + math.sin(tilt) * L + 0.25
    ty = y + math.cos(tilt) * L * 0.0
    mb.tube([(x - W / 2 - 0.1, ty, tz), (x + W / 2 + 0.1, ty, tz)], tank_r, "stainless", sides=18)
    for i in range(ntubes):
        tx = x - W / 2 + (i + 0.5) * W / ntubes
        a = V((tx, ty - 0.08, tz - 0.12))
        b = V((tx, ty - 0.08 - math.cos(tilt) * L, tz - 0.12 - math.sin(tilt) * L))
        mb.tube([a, b], 0.029, "solar", sides=8)
    st = (0.75, 0.76, 0.76, 1)
    for sx in (x - W / 2 - 0.02, x + W / 2 + 0.02):
        mb.tube([(sx, ty, tz - 0.2), (sx, ty - math.cos(tilt) * L - 0.05, z + 0.1)], 0.015, "chrome", st, square=True)
        mb.tube([(sx, ty, tz - 0.2), (sx, ty + 0.05, z)], 0.015, "chrome", st, square=True)
        mb.tube([(sx, ty - math.cos(tilt) * L - 0.05, z + 0.1), (sx, ty - math.cos(tilt) * L - 0.05, z)], 0.015,
                "chrome", st, square=True)
        mb.tube([(sx, ty - math.cos(tilt) * L - 0.05, z + 0.02), (sx, ty + 0.05, z + 0.02)], 0.012, "chrome", st,
                square=True)
    mb.box((x - W / 2, ty - math.cos(tilt) * L - 0.12, z + 0.08), (x + W / 2, ty - math.cos(tilt) * L + 0.0,
                                                                     z + 0.14), "chrome", st)
    mb.bm.verts.ensure_lookup_table()
    M = G.rot_z(facing_deg, (x, y, z))
    for v in mb.bm.verts[mk:]:
        v.co = M @ v.co
    Ms, Ls = slope_xform((0, ty - 0.08, tz - 0.12), (0, ty - 0.08 - math.cos(tilt) * L, tz - 0.12 - math.sin(tilt) * L),
                         x)
    Mc = G.rot_z(facing_deg, (x, y, z)) @ Ms
    ctx.col((-W / 2, -Ls / 2, -0.04), (W / 2, Ls / 2, 0.04), "metal", (), Mc)
    ctx.col((x - W / 2 - 0.3, ty - tank_r, tz - tank_r), (x + W / 2 + 0.3, ty + tank_r, tz + tank_r), "metal", (),
            G.rot_z(facing_deg, (x, y, z)))


def antenna(ctx: Ctx, x, y, z, h=3.0):
    mb = ctx.clutter
    rng = ctx.rng
    t = (0.65, 0.66, 0.66, 1)
    mb.tube([(x, y, z), (x, y, z + h)], 0.018, "chrome", t, sides=6)
    mb.box((x - 0.08, y - 0.08, z), (x + 0.08, y + 0.08, z + 0.03), "metal_painted", (0.3, 0.3, 0.3, 1))
    for k in range(2):
        zz = z + h - 0.15 - k * 0.6
        a = rng.uniform(0, math.pi)
        d = V((math.cos(a), math.sin(a), 0))
        p = V((x, y, zz))
        mb.tube([p - d * 0.7, p + d * 0.7], 0.008, "chrome", t, sides=4)
        perp = V((-d.y, d.x, 0))
        for j in range(8):
            q = p - d * 0.65 + d * (1.3 * j / 7)
            ln = 0.4 - j * 0.03
            mb.tube([q - perp * ln, q + perp * ln], 0.004, "chrome", t, sides=4)
    for k in range(3):  # guy wires
        a = 2 * math.pi * k / 3 + 0.3
        mb.tube([(x, y, z + h * 0.6), (x + math.cos(a) * 1.0, y + math.sin(a) * 1.0, z + 0.02)], 0.002, "chrome", t,
                sides=3)
    # coax cable down
    mb.tube([(x + 0.02, y, z + h - 0.2), (x + 0.025, y, z + 0.3), (x + 0.3, y + 0.2, z + 0.02)], 0.004, "rubber",
            sides=4)


def ladder(ctx: Ctx, x, y, z0, z1, bamboo=False, lean_y=0.0):
    """Ladder from (x,y,z0) to top (x, y+lean_y, z1). Climbable collider."""
    mb = ctx.clutter
    w = 0.42
    if bamboo:
        mat, tint, r = "wood_brown", (1.9, 1.6, 0.9, 1), 0.028
    else:
        mat, tint, r = "metal_painted", (0.35, 0.36, 0.36, 1), 0.016
    for sx in (-w / 2, w / 2):
        mb.tube([(x + sx, y, z0), (x + sx, y + lean_y, z1 + 0.4)], r, mat, tint, sides=8 if bamboo else 4,
                square=not bamboo)
    n = int((z1 - z0) / 0.28)
    for k in range(1, n + 1):
        t = k / (n + 1.4)
        zz = z0 + (z1 + 0.4 - z0) * t
        yy = y + lean_y * t
        mb.tube([(x - w / 2, yy, zz), (x + w / 2, yy, zz)], r * 0.75, mat, tint, sides=6 if bamboo else 4,
                square=not bamboo)
        if bamboo:  # rope lashing
            for sx in (-w / 2, w / 2):
                mb.tube([(x + sx, yy - 0.035, zz - 0.02), (x + sx, yy + 0.035, zz + 0.02)], 0.012, "fabric_canvas",
                        (0.7, 0.6, 0.4, 1), sides=4)
    ang = math.atan2(lean_y, z1 + 0.4 - z0)
    L = math.hypot(lean_y, z1 + 0.4 - z0)
    M = Matrix.Translation((x, y + lean_y / 2, (z0 + z1 + 0.4) / 2)) @ Matrix.Rotation(-ang, 4, "X")
    ctx.col((-w / 2, -0.04, -L / 2), (w / 2, 0.04, L / 2), "wood" if bamboo else "metal", ("climb",), M)
    ctx.climb.append(V((x, y - 0.1, z0 + 0.2)))
    ctx.climb.append(V((x, y + lean_y, z1)))


def plank(ctx: Ctx, a, b, w=0.28, t=0.035):
    """Wooden plank bridging two rooftops (a->b at deck level)."""
    A, B = V(a), V(b)
    d = (B - A)
    L = d.length
    ang = math.atan2(d.y, d.x)
    pitch = math.atan2(d.z, math.hypot(d.x, d.y))
    M = Matrix.Translation((A + B) / 2) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Rotation(-pitch, 4, "Y")
    mk = len(ctx.clutter.bm.verts)
    ctx.clutter.box((-L / 2, -w / 2, 0), (L / 2, w / 2, t), "wood_brown", (1.5, 1.4, 1.2, 1), bevel=0.006,
                    uvmode="grain_h")
    ctx.clutter.bm.verts.ensure_lookup_table()
    for v in ctx.clutter.bm.verts[mk:]:
        v.co = M @ v.co
    ctx.col((-L / 2, -w / 2, 0), (L / 2, w / 2, t), "wood", (), M)


def roof_shed(ctx: Ctx, x0, x1, y0, y1, z, h=2.1, mat="corrugated_rusted", walls=True):
    """Lean-to shed of corrugated sheets on steel posts (rooftop storage / laundry cover)."""
    mb = ctx.clutter
    t = (0.32, 0.3, 0.28, 1)
    h_low = h - 0.35
    for x in (x0, x1):
        for y, hh in ((y0, h_low), (y1, h)):
            mb.box((x - 0.03, y - 0.03, z), (x + 0.03, y + 0.03, z + hh), "metal_painted", t)
    mb.box((x0, y0 - 0.03, z + h_low - 0.05), (x1, y0 + 0.03, z + h_low), "metal_painted", t)
    mb.box((x0, y1 - 0.03, z + h - 0.05), (x1, y1 + 0.03, z + h), "metal_painted", t)
    corrugated_sheet(ctx, x0 - 0.1, x1 + 0.1, y1 + 0.1, y0 - 0.15, z + h + 0.01, z + h_low - 0.04, mat)
    if walls:
        import bmesh
        for xs, n in ((x0, (-1, 0, 0)), (x1, (1, 0, 0))):
            for k in range(int((y1 - y0) / 0.9) + 1):
                ya = y0 + k * 0.9
                yb = min(y1, ya + 0.9)
                quad_n(mb, [(xs, ya, z + 0.05), (xs, yb, z + 0.05), (xs, yb, z + h_low), (xs, ya, z + h_low)],
                       mat, WHITE, n)
                quad_n(mb, [(xs, ya, z + 0.05), (xs, yb, z + 0.05), (xs, yb, z + h_low), (xs, ya, z + h_low)],
                       mat, (0.5, 0.5, 0.5, 1), (-n[0], 0, 0))
        ctx.col((x0 - 0.02, y0, z), (x0 + 0.02, y1, z + h_low), "metal", ("wall",))
        ctx.col((x1 - 0.02, y0, z), (x1 + 0.02, y1, z + h_low), "metal", ("wall",))
    M, L = slope_xform((0, y0, z + h_low), (0, y1, z + h), (x0 + x1) / 2)
    ctx.col((-(x1 - x0) / 2 - 0.1, -L / 2 - 0.1, -0.02), ((x1 - x0) / 2 + 0.1, L / 2 + 0.1, 0.03), "metal", (), M)
    ctx.nap.append(V(((x0 + x1) / 2, (y0 + y1) / 2, z + (h + h_low) / 2 + 0.03)))


def stair_head(ctx: Ctx, x0, x1, y0, y1, z, h, wall_mat, wall_tint=WHITE):
    """'Tum': rooftop stair-head room with a steel door and small window, flat roof + low parapet."""
    sh = ctx.shell
    holes_door = [((x0 + x1) / 2 - 0.4, z, (x0 + x1) / 2 + 0.4, z + 2.05)]
    # front face (toward street, -Y) with door
    wall_with_holes(sh, x0, x1, z, z + h, holes_door, wall_mat, wall_tint, y=y0, depth=0.15)
    door_steel(ctx, (x0 + x1) / 2 - 0.4, z, (x0 + x1) / 2 + 0.4, z + 2.05, wall_y=y0, reveal=0.1,
               tint=(0.35, 0.42, 0.45, 1))
    plain_wall(sh, (x0, y1, z), (1, 0, 0), x1 - x0, h, wall_mat, wall_tint, (0, 1, 0))
    plain_wall(sh, (x0, y0, z), (0, 1, 0), y1 - y0, h, wall_mat, wall_tint, (-1, 0, 0))
    plain_wall(sh, (x1, y0, z), (0, 1, 0), y1 - y0, h, wall_mat, wall_tint, (1, 0, 0))
    sh.box((x0 - 0.05, y0 - 0.05, z + h), (x1 + 0.05, y1 + 0.05, z + h + 0.12), "concrete_weathered", WHITE,
           bevel=0.01)
    for (a, b) in (((x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 + 0.07)), ((x0 - 0.05, y1 - 0.07), (x1 + 0.05, y1 + 0.05)),
                   ((x0 - 0.05, y0), (x0 + 0.07, y1)), ((x1 - 0.07, y0), (x1 + 0.05, y1))):
        sh.box((a[0], a[1], z + h + 0.12), (b[0], b[1], z + h + 0.42), "cement_render", WHITE, bevel=0.01)
    ctx.col((x0, y0, z), (x1, y1, z + h + 0.12), "concrete", ("wall",))
    for (a, b) in (((x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 + 0.07)), ((x0 - 0.05, y1 - 0.07), (x1 + 0.05, y1 + 0.05)),
                   ((x0 - 0.05, y0), (x0 + 0.07, y1)), ((x1 - 0.07, y0), (x1 + 0.05, y1))):
        ctx.col((a[0], a[1], z + h + 0.12), (b[0], b[1], z + h + 0.42), "concrete")
    ctx.ledge(x0, x1, y0, z + h, 1.0)
    ctx.entr.append(V(((x0 + x1) / 2, y0 - 0.3, z)))
    return z + h + 0.12


# ---------------------------------------------------------------------------
# Grime model (vertex colours)
# ---------------------------------------------------------------------------
def make_grime(ctx: Ctx, height: float, seed: int, base_tint=(1, 1, 1), dirt=1.0):
    """Returns grime(co, normal, mat) -> rgb multiplier: macro variation, splash zone, soot under
    ledges, sun-bleaching on top, darker soffits, dust on up-facing surfaces."""
    ledges = list(ctx.ledges)
    off = V((seed * 0.37 % 10, seed * 0.11 % 10, 0))
    no_grime = ("glass", "glass_lit", "signs", "signs_lit", "signs_v", "decals", "foliage", "laundry", "lamp", "goods",
                "dark", "solar")

    def f(co, n, mat):
        if mat in no_grime:
            return (1.0, 1.0, 1.0)
        p = V(co) + off
        m = noise.noise(p * 0.35) * 0.07 + noise.noise(p * 1.3) * 0.035
        m += noise.noise(V((p.x * 0.45, p.y * 0.45, p.z * 0.08))) * 0.09   # tall rain-wash bands
        g = 1.0 + m
        z = co.z
        vertical = abs(n.z) < 0.5
        if vertical:
            g *= 1.0 - 0.28 * dirt * math.exp(-max(z, 0) / 0.55)          # splash zone
            g *= 1.0 - 0.10 * dirt * math.exp(-max(z, 0) / 2.5)
            g *= 1.0 + 0.05 * min(1.0, z / max(height, 1))                  # sun-bleached top
            acc = 0.0
            for a, b, k in ledges:
                if z >= a.z - 0.01:
                    continue
                ab = b - a
                L2 = ab.x * ab.x + ab.y * ab.y
                if L2 < 1e-6:
                    continue
                t = ((co.x - a.x) * ab.x + (co.y - a.y) * ab.y) / L2
                if t < -0.05 or t > 1.05:
                    continue
                px, py = a.x + ab.x * t, a.y + ab.y * t
                dist = math.hypot(co.x - px, co.y - py)
                if dist > 0.5:
                    continue
                dz = a.z - z
                edge = min(1.0, min(t + 0.05, 1.05 - t) * 6)
                streak = 0.6 + 0.4 * noise.noise(V((co.x * 6.0, co.y * 6.0, 0.0)) + off)
                acc += k * math.exp(-dz / 1.1) * edge * streak * (1 - dist / 0.5)
            g *= 1.0 - min(0.38, 0.22 * acc * dirt)
        elif n.z < -0.5:
            g *= 0.72                                                        # soffits
        else:
            g *= 0.96 + 0.04 * noise.noise(p * 3.0)                          # dust on top faces
        return (g * base_tint[0], g * base_tint[1], g * base_tint[2])
    return f


# ---------------------------------------------------------------------------
# Hang May rattan shop display (baskets, trays, conical hats hanging under the awning)
# ---------------------------------------------------------------------------
def basket(mb: MB, x, y, z, r, h, tint=WHITE, kind="bowl"):
    """Woven basket/tray/hat as a lathe (tube with radii profile), rattan material. z = bottom."""
    if kind == "bowl":
        prof = [(0.0, r * 0.55), (0.08, r * 0.8), (0.4, r * 0.97), (0.85, r), (1.0, r * 1.03)]
    elif kind == "tray":
        prof = [(0.0, r * 0.85), (0.6, r), (1.0, r * 1.02)]
    elif kind == "hat":  # non la: cone, apex up
        prof = [(0.0, r), (0.15, r * 0.82), (0.5, r * 0.45), (0.85, r * 0.12), (1.0, 0.004)]
    elif kind == "jar":
        prof = [(0.0, r * 0.6), (0.3, r), (0.7, r * 0.9), (0.9, r * 0.55), (1.0, r * 0.6)]
    else:
        prof = [(0.0, r), (1.0, r)]
    pts = [(x, y, z + t * h) for t, _ in prof]
    mb.tube(pts, r, "rattan", tint, sides=14, caps=kind not in ("bowl", "tray"), radii=[q for _, q in prof])
    if kind in ("bowl", "tray"):
        mb.cylinder((x, y, z), (0, 0, 1), prof[0][1], 0.004, "rattan", mul(tint, 0.8), sides=14)
        # rim ring
        mb.tube([(x + math.cos(a) * prof[-1][1], y + math.sin(a) * prof[-1][1], z + h)
                 for a in [2 * math.pi * i / 16 for i in range(17)]], 0.008, "rattan", mul(tint, 0.85), sides=4,
                caps=False)


def rattan_display(ctx: Ctx, x0, x1, z_rail, wall_y=0.0, out=0.55, floor_stack=True):
    """Goods hung from a pole under the awning + stacks on the sidewalk edge in front of the shop."""
    rng = ctx.rng
    mb = ctx.clutter
    y = wall_y - out
    mb.tube([(x0, y, z_rail), (x1, y, z_rail)], 0.018, "wood_brown", (1.6, 1.3, 0.9, 1), sides=6)
    for xs in (x0, x1):
        mb.tube([(xs, y, z_rail), (xs, wall_y, z_rail + 0.15)], 0.012, "metal_painted", (0.3, 0.3, 0.3, 1), sides=5)
    x = x0 + 0.15
    while x < x1 - 0.15:
        kind = rng.choice(["bowl", "tray", "hat", "bowl", "jar"])
        r = {"bowl": rng.uniform(0.12, 0.22), "tray": rng.uniform(0.18, 0.28), "hat": rng.uniform(0.2, 0.24),
             "jar": rng.uniform(0.08, 0.13)}[kind]
        drop = rng.uniform(0.12, 0.5)
        tint = mul(WHITE, rng.uniform(0.75, 1.1))
        mb.tube([(x, y, z_rail), (x, y, z_rail - drop)], 0.002, "rubber", (3, 3, 3, 1), sides=3, caps=False)
        if kind == "tray":
            mk = len(mb.bm.verts)
            basket(mb, x, y, z_rail - drop - r, r, 0.04, tint, "tray")
            mb.bm.verts.ensure_lookup_table()
            M = G.rot_x(90, (x, y, z_rail - drop - r))
            for v in mb.bm.verts[mk:]:
                v.co = M @ v.co
            x += 0.05 + r * 0.2
        elif kind == "hat":
            basket(mb, x, y, z_rail - drop - 0.18, r, 0.18, tint, "hat")
            x += r * 2.05
        else:
            hgt = r * (0.9 if kind == "bowl" else 2.2)
            basket(mb, x, y, z_rail - drop - hgt, r, hgt, tint, kind)
            x += r * 2.1
    if floor_stack:
        sx = x0 + 0.3
        for q in range(rng.randint(2, 4)):
            r = rng.uniform(0.18, 0.3)
            z = 0.0
            for s_ in range(rng.randint(2, 5)):
                basket(mb, sx, wall_y - 0.45, z, r, r * 0.7, mul(WHITE, rng.uniform(0.8, 1.05)), "bowl")
                z += r * 0.25
                r *= 0.94
            sx += r * 2.3 + 0.05
            if sx > x1 - 0.3:
                break
        ctx.col((x0 + 0.1, wall_y - 0.75, 0.0), (min(sx, x1), wall_y - 0.15, 0.5), "wood")


def drainpipe_path(ctx: Ctx, pts, mat="plastic", tint=(0.72, 0.73, 0.72, 1), r=0.045):
    """Downpipe following a polyline (top -> bottom) with clips; the longest vertical run is climbable."""
    mb = ctx.clutter
    P = [V(p) for p in pts]
    mb.tube(P, r, mat, tint, sides=10)
    best = None
    for a, b in zip(P[:-1], P[1:]):
        if abs(a.x - b.x) < 1e-3 and abs(a.y - b.y) < 1e-3:
            z0, z1 = min(a.z, b.z), max(a.z, b.z)
            z = z0 + 0.8
            while z < z1 - 0.3:
                mb.box((a.x - r - 0.012, a.y - r - 0.012, z), (a.x + r + 0.012, a.y + 0.07, z + 0.03),
                       "metal_painted", (0.4, 0.38, 0.35, 1))
                z += ctx.rng.uniform(1.4, 2.0)
            if best is None or (z1 - z0) > (best[2] - best[1]):
                best = (a, z0, z1)
            ctx.col((a.x - r, a.y - r, z0), (a.x + r, a.y + r, z1), "plastic" if mat == "plastic" else "metal",
                    ("climb",))
    if best:
        a, z0, z1 = best
        ctx.climb.append(V((a.x, a.y - r, z0 + 0.3)))
        ctx.climb.append(V((a.x, a.y - r, z1)))
    mb.tube([P[-1], P[-1] + V((0, -0.08, -0.08)), P[-1] + V((0, -0.14, -0.1))], r, mat, tint, sides=10)


def wall_altar(ctx: Ctx, x, z, wall_y=0.0):
    """Small red outdoor altar shelf (ban tho thien) with incense bowl and sticks, beside a door."""
    mb = ctx.clutter
    red = (0.55, 0.08, 0.06, 1)
    mb.box((x - 0.2, wall_y - 0.22, z), (x + 0.2, wall_y, z + 0.03), "wood_brown", red, bevel=0.005)
    mb.box((x - 0.2, wall_y - 0.22, z + 0.03), (x - 0.18, wall_y, z + 0.32), "wood_brown", red)
    mb.box((x + 0.18, wall_y - 0.22, z + 0.03), (x + 0.2, wall_y, z + 0.32), "wood_brown", red)
    mb.box((x - 0.2, wall_y - 0.22, z + 0.32), (x + 0.2, wall_y, z + 0.35), "wood_brown", red)
    mb.box((x - 0.17, wall_y - 0.01, z + 0.03), (x + 0.17, wall_y, z + 0.32), "signs_v" if False else "plastic",
           (0.85, 0.6, 0.15, 1))
    mb.cylinder((x, wall_y - 0.11, z + 0.03), (0, 0, 1), 0.05, 0.06, "plastic_matte", (0.75, 0.7, 0.55, 1), sides=10)
    for k in range(5):
        a = k * 1.3
        mb.tube([(x + math.cos(a) * 0.012, wall_y - 0.11 + math.sin(a) * 0.012, z + 0.08),
                 (x + math.cos(a) * 0.03, wall_y - 0.11 + math.sin(a) * 0.03, z + 0.26)], 0.0025, "plastic",
                (0.75, 0.2, 0.15, 1), sides=3)
    ctx.col((x - 0.2, wall_y - 0.22, z), (x + 0.2, wall_y, z + 0.35), "wood")
