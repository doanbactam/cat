#!/usr/bin/env python3
"""SVG icon library of Mèo Cam (owner: ui). Hand-authored vector art, written as code.

Writes SVG sources to assets/ui/icons/src/<group>/<name>.svg (a .gdignore keeps them out of the
Godot import). scripts/ui/build/rasterize_icons.gd then renders PNGs with Godot's SVG renderer:
  glyphs  -> assets/ui/icons/glyphs/<name>.png   (white, tinted in engine; 128 px)
  actions -> assets/ui/icons/actions/<name>.png  (dialogue cat actions; 128 px)
  skills  -> assets/ui/icons/skills/<id>.png     (skill + tree glyphs; 128 px)
  items   -> assets/ui/icons/items/<id>.png      (full-colour illustrations; 256 px)

Run:  python3 scripts/ui/build/gen_icons.py && tools/godot_lock.sh godot --headless --path . \
        --script res://scripts/ui/build/rasterize_icons.gd </dev/null && tools/godot_import.sh
"""
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(ROOT, "assets", "ui", "icons", "src")

W = "#ffffff"
SW = 4.5  # glyph stroke width (64 px grid)


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def svg(body, size=64, defs=""):
    d = f"<defs>{defs}</defs>" if defs else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}">{d}{body}</svg>')


def S(d, w=SW, color=W, extra=""):
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round" {extra}/>')


def F(d, color=W, rule="nonzero", extra=""):
    return f'<path d="{d}" fill="{color}" fill-rule="{rule}" {extra}/>'


def C(cx, cy, r, fill=W, stroke=None, w=SW, extra=""):
    st = f'stroke="{stroke}" stroke-width="{w}"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" {st} {extra}/>'


def E(cx, cy, rx, ry, fill=W, stroke=None, w=SW, rot=0, extra=""):
    st = f'stroke="{stroke}" stroke-width="{w}"' if stroke else ""
    tr = f'transform="rotate({rot} {cx} {cy})"' if rot else ""
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" {st} {tr} {extra}/>'


def circ_path(cx, cy, r):
    """Circle as a path (for even-odd holes)."""
    return f"M{cx + r} {cy} A{r} {r} 0 1 0 {cx - r} {cy} A{r} {r} 0 1 0 {cx + r} {cy} Z"


def ell_path(cx, cy, rx, ry):
    return f"M{cx + rx} {cy} A{rx} {ry} 0 1 0 {cx - rx} {cy} A{rx} {ry} 0 1 0 {cx + rx} {cy} Z"


def star_pts(cx, cy, r_out, r_in, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180.0 / n)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def poly(pts, close=True):
    s = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in pts)
    return s + (" Z" if close else "")


def paw(cx, cy, s, color=W):
    """Filled paw print centred at (cx, cy), s ~ overall width."""
    k = s / 64.0
    out = []
    # main pad: soft trapezoid
    out.append(F(f"M{cx - 13 * k} {cy + 14 * k} C{cx - 20 * k} {cy + 8 * k} {cx - 14 * k} {cy - 2 * k} {cx} {cy - 3 * k} "
                 f"C{cx + 14 * k} {cy - 2 * k} {cx + 20 * k} {cy + 8 * k} {cx + 13 * k} {cy + 14 * k} "
                 f"C{cx + 8 * k} {cy + 19 * k} {cx - 8 * k} {cy + 19 * k} {cx - 13 * k} {cy + 14 * k} Z", color))
    for (tx, ty, rx, ry, rot) in [(-19, -6, 5.6, 7.2, -20), (-8, -17, 5.8, 7.6, -6), (8, -17, 5.8, 7.6, 6), (19, -6, 5.6, 7.2, 20)]:
        out.append(E(cx + tx * k, cy + ty * k, rx * k, ry * k, color, rot=rot))
    return "".join(out)


def cat_head_path(cx=32, cy=34, s=1.0):
    k = s
    return (f"M{cx - 18 * k} {cy - 10 * k} L{cx - 17 * k} {cy - 27 * k} L{cx - 6 * k} {cy - 17 * k} "
            f"Q{cx} {cy - 19 * k} {cx + 6 * k} {cy - 17 * k} L{cx + 17 * k} {cy - 27 * k} L{cx + 18 * k} {cy - 10 * k} "
            f"Q{cx + 24 * k} {cy} {cx + 20 * k} {cy + 10 * k} Q{cx + 14 * k} {cy + 21 * k} {cx} {cy + 21 * k} "
            f"Q{cx - 14 * k} {cy + 21 * k} {cx - 20 * k} {cy + 10 * k} Q{cx - 24 * k} {cy} {cx - 18 * k} {cy - 10 * k} Z")


def cat_eye_path(cx, cy, rx, ry):
    return f"M{cx - rx} {cy} Q{cx} {cy - ry * 2} {cx + rx} {cy} Q{cx} {cy + ry * 2} {cx - rx} {cy} Z"


# ---------------------------------------------------------------------------------------------
# Glyphs (HUD / menus / markers) — white on transparent, 64 grid
# ---------------------------------------------------------------------------------------------

def heart_path(cx=32, cy=33, s=1.0):
    k = s
    return (f"M{cx} {cy + 21 * k} C{cx - 20 * k} {cy + 7 * k} {cx - 26 * k} {cy - 3 * k} {cx - 22 * k} {cy - 13 * k} "
            f"C{cx - 18 * k} {cy - 23 * k} {cx - 6 * k} {cy - 24 * k} {cx} {cy - 15 * k} "
            f"C{cx + 6 * k} {cy - 24 * k} {cx + 18 * k} {cy - 23 * k} {cx + 22 * k} {cy - 13 * k} "
            f"C{cx + 26 * k} {cy - 3 * k} {cx + 20 * k} {cy + 7 * k} {cx} {cy + 21 * k} Z")


def fish_path(cx=32, cy=32, s=1.0):
    k = s
    body = (f"M{cx - 25 * k} {cy} C{cx - 17 * k} {cy - 13 * k} {cx + 2 * k} {cy - 16 * k} {cx + 14 * k} {cy - 5 * k} "
            f"L{cx + 25 * k} {cy - 14 * k} L{cx + 22 * k} {cy} L{cx + 25 * k} {cy + 14 * k} L{cx + 14 * k} {cy + 5 * k} "
            f"C{cx + 2 * k} {cy + 16 * k} {cx - 17 * k} {cy + 13 * k} {cx - 25 * k} {cy} Z")
    eye = circ_path(cx - 14 * k, cy - 2.5 * k, 2.8 * k)
    gill = (f"M{cx - 7 * k} {cy - 8 * k} Q{cx - 3 * k} {cy} {cx - 7 * k} {cy + 8 * k} "
            f"L{cx - 9.5 * k} {cy + 8 * k} Q{cx - 5.5 * k} {cy} {cx - 9.5 * k} {cy - 8 * k} Z")
    return body + " " + eye + " " + gill


GLYPHS = {}


def glyph(name):
    def deco(fn):
        GLYPHS[name] = fn
        return fn
    return deco


@glyph("health")
def _():
    return svg(F(heart_path()))


@glyph("hunger")
def _():
    return svg(F(fish_path(32, 33, 1.0), rule="evenodd"))


@glyph("energy")
def _():
    return svg(F("M37 4 L13 37 L29 37 L25 60 L51 25 L35 25 Z", extra='stroke="#fff" stroke-width="2" stroke-linejoin="round"'))


@glyph("warmth")
def _():
    outer = ("M32 59 C18 59 11 49 13 38 C15 28 23 24 23 12 C31 16 37 24 35 32 C39 30 41 25 40 20 "
             "C49 28 54 40 50 49 C47 55 40 59 32 59 Z")
    inner = ("M32 53 C26.5 53 24 48 25.5 43.5 C27 39.5 31 37 31 32 C35.5 36 40 42 38.5 46.5 "
             "C37.5 50.5 35 53 32 53 Z")
    return svg(F(outer + " " + inner, rule="evenodd"))


@glyph("xp")
def _():
    pts = []
    for i in range(8):
        r = 27 if i % 2 == 0 else 7.5
        a = math.radians(-90 + i * 45)
        pts.append((32 + math.cos(a) * r, 32 + math.sin(a) * r))
    small = []
    for i in range(8):
        r = 8 if i % 2 == 0 else 2.5
        a = math.radians(-90 + i * 45)
        small.append((51 + math.cos(a) * r, 13 + math.sin(a) * r))
    return svg(F(poly(pts)) + F(poly(small)))


@glyph("star")
def _():
    return svg(F(poly(star_pts(32, 34, 27, 11.5)), extra='stroke="#fff" stroke-width="3" stroke-linejoin="round"'))


@glyph("paw")
def _():
    return svg(paw(32, 36, 60))


@glyph("cap")
def _():
    pts = []
    n = 21
    for i in range(n * 2):
        r = 27 if i % 2 == 0 else 23.5
        a = math.radians(i * 180.0 / n)
        pts.append((32 + math.cos(a) * r, 32 + math.sin(a) * r))
    ring = circ_path(32, 32, 18.5)
    inner = circ_path(32, 32, 15)
    return svg(F(poly(pts) + " " + ring, rule="evenodd") + F(inner + " " + poly(star_pts(32, 32.8, 9.5, 4)), rule="evenodd"))


@glyph("map_pin")
def _():
    outer = "M32 61 C32 61 11 39 11 24.5 A21 21 0 0 1 53 24.5 C53 39 32 61 32 61 Z"
    return svg(F(outer + " " + circ_path(32, 24.5, 8), rule="evenodd"))


@glyph("quest")
def _():
    # star lantern (đèn ông sao) on a stick — the tracked-quest marker
    star = poly(star_pts(32, 26, 27, 12))
    hole = poly(star_pts(32, 26, 12.5, 5.6))
    return svg(F(star + " " + hole, rule="evenodd", extra='stroke="#fff" stroke-width="2" stroke-linejoin="round"') +
               C(32, 27.5, 4.5) + S("M32 50 L32 62", 4.5))


@glyph("location")
def _():
    # pagoda-style roof over a pin dot: discovered places
    roof = "M6 27 Q20 24 32 9 Q44 24 58 27 L54 30 Q42 28 32 19 Q22 28 10 30 Z"
    return svg(F(roof) + S("M16 33 L16 55 M48 33 L48 55 M10 55 L54 55", 4.5) + C(32, 42, 6))


@glyph("nap")
def _():
    moon = "M40 10 A24 24 0 1 0 54 44 A19 19 0 1 1 40 10 Z"
    z1 = "M38 18 L50 18 L38 30 L50 30"
    return svg(F(moon) + S(z1, 3.6) + S("M48 6 L55 6 L48 13 L55 13", 2.8))


@glyph("home")
def _():
    roof = "M4 30 Q18 27 32 11 Q46 27 60 30 L56 33 Q44 31 32 20 Q20 31 8 33 Z"
    body = "M13 33 L13 56 L51 56 L51 33 L32 22 Z M27 56 L27 42 Q32 37 37 42 L37 56 Z"
    return svg(F(roof) + F(body, rule="evenodd"))


@glyph("cat")
def _():
    head = cat_head_path(32, 36, 1.05)
    eyes = cat_eye_path(23.5, 37, 4.5, 2.6) + " " + cat_eye_path(40.5, 37, 4.5, 2.6)
    nose = "M29.5 45 L34.5 45 L32 48 Z"
    return svg(F(head + " " + eyes + " " + nose, rule="evenodd"))


@glyph("mouth")
def _():
    # cat head holding something: the mouth-item slot
    head = cat_head_path(32, 30, 0.9)
    eyes = cat_eye_path(24.5, 31, 4, 2.3) + " " + cat_eye_path(39.5, 31, 4, 2.3)
    return svg(F(head + " " + eyes, rule="evenodd") + C(32, 52, 8, fill="none", stroke=W, w=4) + S("M24 52 L40 52", 3))


@glyph("skill")
def _():
    return svg(S("M32 54 L32 34 M32 34 L16 18 M32 34 L48 18 M32 42 L46 46", 4.2) +
               C(32, 54, 5.5) + C(16, 18, 6.5) + C(48, 18, 6.5) + C(32, 34, 5) + C(46, 46, 4.5))


@glyph("achievement")
def _():
    ribbon = "M20 4 L28 4 L34 22 L26 24 Z M44 4 L36 4 L30 22 L38 24 Z"
    return svg(F(ribbon) + F(circ_path(32, 40, 18) + " " + poly(star_pts(32, 41, 10.5, 4.5)), rule="evenodd"))


@glyph("memory")
def _():
    frame = "M8 14 L56 14 L56 52 L8 52 Z M13 19 L13 41 L51 41 L51 19 Z"
    scene = "M13 41 L24 30 L31 36 L39 26 L51 39 L51 41 Z"
    return svg(F(frame, rule="evenodd") + F(scene) + C(22, 26, 3.5))


@glyph("territory")
def _():
    return svg(S("M18 10 Q12 32 16 54", 5) + S("M32 8 Q26 32 30 56", 5) + S("M46 10 Q40 32 44 54", 5))


@glyph("objective")
def _():
    return svg(C(32, 32, 24, fill="none", stroke=W, w=4.5) + S("M20 33 L28.5 41.5 L45 24", 5.5))


@glyph("check")
def _():
    return svg(S("M12 34 L26 48 L53 17", 7))


@glyph("cross")
def _():
    return svg(S("M16 16 L48 48 M48 16 L16 48", 6.5))


@glyph("warning")
def _():
    tri = "M32 6 L60 56 L4 56 Z"
    bang = "M29 22 L35 22 L34 40 L30 40 Z " + circ_path(32, 47, 3.4)
    return svg(F(tri + " " + bang, rule="evenodd", extra='stroke="#fff" stroke-width="3" stroke-linejoin="round"'))


@glyph("info")
def _():
    return svg(F(circ_path(32, 32, 26) + " " + circ_path(32, 19, 3.6) + " M28.5 27 L35.5 27 L35.5 47 L28.5 47 Z", rule="evenodd"))


@glyph("lock")
def _():
    body = "M14 28 L50 28 L50 58 L14 58 Z " + circ_path(32, 41, 4.5) + " M30 44 L34 44 L34 51 L30 51 Z"
    return svg(F(body, rule="evenodd") + S("M21 28 L21 19 A11 11 0 0 1 43 19 L43 28", 5))


@glyph("plus")
def _():
    return svg(S("M32 12 L32 52 M12 32 L52 32", 7))


@glyph("minus")
def _():
    return svg(S("M12 32 L52 32", 7))


@glyph("chevron_left")
def _():
    return svg(S("M40 12 L20 32 L40 52", 6.5))


@glyph("chevron_right")
def _():
    return svg(S("M24 12 L44 32 L24 52", 6.5))


@glyph("chevron_down")
def _():
    return svg(S("M12 24 L32 44 L52 24", 6.5))


@glyph("compass")
def _():
    return svg(C(32, 32, 26, fill="none", stroke=W, w=3.5) + F("M32 8 L39 32 L32 30 L25 32 Z") +
               F("M32 56 L25 32 L32 34 L39 32 Z", extra='fill-opacity="0.45"'))


@glyph("gear")
def _():
    pts = []
    n = 8
    for i in range(n * 4):
        a = math.radians(i * 360.0 / (n * 4) - 5.6)
        r = 28 if (i % 4) in (1, 2) else 21
        pts.append((32 + math.cos(a) * r, 32 + math.sin(a) * r))
    return svg(F(poly(pts) + " " + circ_path(32, 32, 9.5), rule="evenodd"))


@glyph("journal")
def _():
    book = "M10 10 Q22 8 32 14 Q42 8 54 10 L54 52 Q42 50 32 56 Q22 50 10 52 Z M32 18 L32 50"
    return svg(S(book, 4.2) + S("M16 20 Q22 19 27 21 M16 28 Q22 27 27 29 M37 21 Q42 19 48 20 M37 29 Q42 27 48 28", 2.6))


@glyph("map")
def _():
    m = "M6 14 L22 8 L42 14 L58 8 L58 50 L42 56 L22 50 L6 56 Z"
    return svg(S(m, 4.2) + S("M22 8 L22 50 M42 14 L42 56", 3.2) + C(32, 28, 3.6) + S("M14 40 Q22 30 30 34", 2.4, extra='stroke-dasharray="3 4"'))


@glyph("inventory")
def _():
    # woven rattan basket (giỏ mây)
    body = "M8 24 L56 24 L50 56 L14 56 Z"
    weave = "M14 34 L52 34 M15.5 44 L50.5 44 M22 24 L24 56 M32 24 L32 56 M42 24 L40 56"
    handle = "M16 24 Q32 0 48 24"
    return svg(S(body, 4.2) + S(weave, 2.4) + S(handle, 4.2))


@glyph("skills")
def _():
    return GLYPHS["skill"]()


@glyph("graphics")
def _():
    return svg(S("M6 12 L58 12 L58 44 L6 44 Z", 4.2) + S("M22 54 L42 54 M32 44 L32 54", 4.2) +
               F("M14 38 L26 24 L34 32 L40 26 L50 38 Z") + C(46, 20, 3.5))


@glyph("audio")
def _():
    return svg(F("M8 24 L18 24 L32 12 L32 52 L18 40 L8 40 Z") + S("M40 24 Q46 32 40 40", 4) + S("M46 16 Q58 32 46 48", 4))


@glyph("controls")
def _():
    body = ("M18 18 L46 18 Q58 18 60 34 Q62 50 54 52 Q48 53 42 44 L22 44 Q16 53 10 52 Q2 50 4 34 Q6 18 18 18 Z")
    return svg(S(body, 4) + S("M16 28 L16 38 M11 33 L21 33", 3.4) + C(44, 29, 3.2) + C(50, 35, 3.2))


@glyph("gameplay")
def _():
    return GLYPHS["paw"]()


@glyph("language")
def _():
    return svg(C(32, 32, 25, fill="none", stroke=W, w=3.8) + S("M7 32 L57 32 M32 7 Q18 32 32 57 M32 7 Q46 32 32 57", 3.2) +
               S("M12 19 Q32 25 52 19 M12 45 Q32 39 52 45", 2.6))


@glyph("pause")
def _():
    return svg(F("M16 10 L27 10 L27 54 L16 54 Z M37 10 L48 10 L48 54 L37 54 Z"))


@glyph("play")
def _():
    return svg(F("M18 8 L54 32 L18 56 Z", extra='stroke="#fff" stroke-width="3" stroke-linejoin="round"'))


@glyph("save")
def _():
    # stitched notebook with paw (save game)
    return svg(S("M12 6 L46 6 L54 14 L54 58 L12 58 Z", 4.2) + paw(33, 36, 26))


@glyph("load")
def _():
    return svg(S("M8 16 L26 16 L31 22 L56 22 L56 52 L8 52 Z", 4.2) + S("M32 46 L32 30 M25 37 L32 30 L39 37", 4))


@glyph("quit")
def _():
    return svg(S("M28 8 L10 8 L10 56 L28 56", 4.5) + S("M24 32 L56 32 M46 22 L56 32 L46 42", 5))


@glyph("back")
def _():
    return svg(S("M26 16 L10 32 L26 48 M10 32 L54 32", 5.5))


@glyph("eye")
def _():
    return svg(F(cat_eye_path(32, 32, 27, 13) + " " + ell_path(32, 32, 5, 11.5), rule="evenodd"))


@glyph("time")
def _():
    return svg(C(32, 32, 25, fill="none", stroke=W, w=4.2) + S("M32 16 L32 33 L43 40", 4.5))


@glyph("sun")
def _():
    rays = " ".join(f"M{32 + math.cos(math.radians(a)) * 19:.1f} {32 + math.sin(math.radians(a)) * 19:.1f} "
                    f"L{32 + math.cos(math.radians(a)) * 27:.1f} {32 + math.sin(math.radians(a)) * 27:.1f}" for a in range(0, 360, 45))
    return svg(C(32, 32, 12) + S(rays, 4.2))


@glyph("moon")
def _():
    return svg(F("M38 6 A26 26 0 1 0 58 42 A20 20 0 1 1 38 6 Z"))


@glyph("rain")
def _():
    cloud = "M16 36 A10 10 0 0 1 18 16 A14 14 0 0 1 44 14 A11 11 0 0 1 48 36 Z"
    return svg(F(cloud) + S("M20 44 L16 54 M32 44 L28 56 M44 44 L40 54", 4))


@glyph("caps")
def _():
    return GLYPHS["cap"]()


@glyph("item")
def _():
    # little bundle wrapped in cloth (generic item)
    return svg(F("M12 30 Q32 22 52 30 L48 54 Q32 60 16 54 Z") + F("M22 30 Q26 14 32 20 Q38 14 42 30 Z"))


@glyph("faint")
def _():
    return svg(S("M10 32 Q18 22 26 32 T42 32 T58 32", 4.2) + S("M14 46 Q20 40 26 46 M38 46 Q44 40 50 46", 3.6) +
               F(poly(star_pts(47, 14, 7, 3))) + F(poly(star_pts(18, 13, 5, 2.2))))


@glyph("buff")
def _():
    return svg(S("M32 54 L32 14 M18 28 L32 14 L46 28", 5.5) + S("M14 54 L50 54", 4))


@glyph("keyboard")
def _():
    keys = " ".join(f"M{x} {y} L{x + 4} {y}" for y in (24, 32) for x in range(12, 52, 8))
    return svg(S("M4 14 L60 14 L60 50 L4 50 Z", 4) + S(keys, 3.4) + S("M18 41 L46 41", 3.4))


@glyph("mouse_device")
def _():
    return svg(S("M20 10 Q32 4 44 10 L46 44 Q32 62 18 44 Z", 4) + S("M32 7 L32 24 M19 24 L45 24", 3.4))


@glyph("gamepad")
def _():
    return GLYPHS["controls"]()


@glyph("dog")
def _():
    head = ("M16 18 Q10 12 6 20 Q4 30 12 34 L14 44 Q20 56 32 56 Q44 56 50 44 L52 34 Q60 30 58 20 Q54 12 48 18 "
            "Q40 12 32 12 Q24 12 16 18 Z")
    eyes = circ_path(24, 32, 3) + " " + circ_path(40, 32, 3)
    nose = "M27 42 Q32 38 37 42 Q35 47 32 47 Q29 47 27 42 Z"
    return svg(F(head + " " + eyes + " " + nose, rule="evenodd"))


@glyph("crow")
def _():
    bird = ("M6 30 Q14 26 22 28 Q28 16 40 16 Q48 16 52 22 L60 24 L52 27 Q50 36 42 40 L48 52 L40 46 L36 52 L34 42 "
            "Q22 42 14 36 Z")
    return svg(F(bird + " " + circ_path(44, 22, 2.2), rule="evenodd"))


@glyph("letter")
def _():
    return svg(S("M6 14 L58 14 L58 50 L6 50 Z", 4) + S("M6 14 L32 34 L58 14", 4))


@glyph("ring")
def _():
    # small circle (minimal marker)
    return svg(C(32, 32, 20, fill="none", stroke=W, w=7))


@glyph("dot")
def _():
    return svg(C(32, 32, 16))


@glyph("arrow_up")
def _():
    return svg(F("M32 6 L54 34 L40 34 L40 58 L24 58 L24 34 L10 34 Z"))


@glyph("player_arrow")
def _():
    # map marker for Cam: chevron arrow with notch
    return svg(F("M32 4 L54 56 L32 44 L10 56 Z", extra='stroke="#fff" stroke-width="2" stroke-linejoin="round"'))


@glyph("credits")
def _():
    return svg(F(heart_path(32, 34, 0.9)) + S("M10 10 L16 16 M54 10 L48 16 M32 4 L32 10", 3.5))


@glyph("new_game")
def _():
    return GLYPHS["sun"]()


@glyph("delete")
def _():
    return svg(S("M10 16 L54 16 M24 16 L26 8 L38 8 L40 16 M16 16 L19 58 L45 58 L48 16 M27 26 L28 48 M37 26 L36 48", 4))


@glyph("sense")
def _():
    # whiskers + nose: cat-sense
    return svg(F("M26 30 L38 30 L32 38 Z") + S("M24 36 L4 30 M24 40 L4 42 M24 44 L6 52 M40 36 L60 30 M40 40 L60 42 M40 44 L58 52", 3.2))


# ---------------------------------------------------------------------------------------------
# Dialogue cat-action glyphs
# ---------------------------------------------------------------------------------------------

ACTIONS = {}


def action(name):
    def deco(fn):
        ACTIONS[name] = fn
        return fn
    return deco


def bubble(extra_holes=""):
    b = "M10 10 L54 10 Q60 10 60 16 L60 40 Q60 46 54 46 L28 46 L16 58 L18 46 L10 46 Q4 46 4 40 L4 16 Q4 10 10 10 Z"
    return b + " " + extra_holes


@action("meow")
def _():
    hole = "M14 30 Q20 22 26 30 Q32 38 38 30 Q44 22 50 30 L50 33 Q44 26 38 34 Q32 42 26 34 Q20 26 14 33 Z"
    return svg(F(bubble(hole), rule="evenodd"))


@action("purr")
def _():
    return svg(C(16, 32, 7) + S("M28 20 Q36 32 28 44", 4.2) + S("M38 14 Q50 32 38 50", 4.2) + S("M48 8 Q64 32 48 56", 4.2))


@action("headbutt")
def _():
    head = cat_head_path(38, 36, 0.85)
    eyes = cat_eye_path(31, 37, 3.6, 2) + " " + cat_eye_path(45, 37, 3.6, 2)
    return svg(F(head + " " + eyes, rule="evenodd") + S("M4 26 L14 26 M2 36 L14 36 M4 46 L14 46", 3.6))


@action("ignore")
def _():
    return svg(S("M8 30 Q32 52 56 30", 5) + S("M16 40 L11 48 M32 46 L32 55 M48 40 L53 48", 4) +
               S("M42 8 L52 8 L42 18 L52 18", 3.4))


@action("chirp")
def _():
    return svg(F(ell_path(22, 48, 9, 7)) + S("M30 46 L30 10 Q40 14 46 22", 4.5))


@action("trill")
def _():
    return svg(F(ell_path(16, 48, 8, 6.5)) + F(ell_path(44, 42, 8, 6.5)) + S("M23 46 L23 14 L51 8 L51 40", 4.5) +
               S("M23 22 L51 16", 4.5))


@action("slow_blink")
def _():
    return svg(F(cat_eye_path(32, 34, 26, 10)) + F("M4 30 Q32 6 60 30 Q32 18 4 30 Z") + S("M6 28 Q32 16 58 28", 4.5))


@action("rub")
def _():
    return svg(S("M12 52 Q10 24 32 22 Q50 22 50 40 Q50 52 38 52 Q28 52 30 42", 4.5) + S("M54 10 L58 6 M46 8 L48 3 M58 18 L62 16", 3.2))


@action("hiss")
def _():
    mouth = "M6 24 Q32 8 58 24 Q50 50 32 52 Q14 50 6 24 Z"
    fangs = "M18 24 L22 36 L26 24 Z M38 24 L42 36 L46 24 Z"
    return svg(F(mouth + " " + "M14 26 Q32 16 50 26 Q44 44 32 45 Q20 44 14 26 Z", rule="evenodd") + F(fangs))


@action("sit")
def _():
    cat = ("M26 58 Q14 58 14 46 Q14 34 22 28 L20 16 Q20 8 26 6 L28 12 L34 12 L36 6 Q42 8 42 16 L40 26 "
           "Q48 34 48 46 Q48 52 44 56 Q56 56 58 48 Q60 42 56 40 Q62 40 62 46 Q62 60 46 60 Z")
    return svg(F(cat))


@action("knead")
def _():
    return svg(paw(20, 40, 30) + paw(44, 26, 30))


@action("follow")
def _():
    return svg(paw(14, 50, 18) + paw(30, 36, 18) + paw(46, 22, 18) + S("M50 54 L58 54 L58 46", 3.6))


@action("leave")
def _():
    return svg(S("M28 8 L10 8 L10 56 L28 56", 4.5) + S("M24 32 L56 32 M46 22 L56 32 L46 42", 5))


@action("roll_over")
def _():
    return svg(S("M50 20 A22 22 0 1 0 54 36", 5) + F("M44 8 L58 22 L42 26 Z"))


@action("offer_item")
def _():
    return svg(paw(22, 38, 34) + C(48, 40, 8) + S("M38 22 L44 16 M44 26 L52 24", 3))


@action("swipe")
def _():
    return svg(S("M10 18 Q30 22 44 50", 5) + S("M22 10 Q42 16 54 42", 5) + S("M8 32 Q24 36 32 56", 5))


@action("groom")
def _():
    drop = "M32 6 Q48 28 48 40 A16 16 0 0 1 16 40 Q16 28 32 6 Z M26 40 Q26 48 32 50 L32 46 Q30 45 30 40 Z"
    return svg(F(drop, rule="evenodd"))


@action("stare")
def _():
    return svg(F(cat_eye_path(32, 32, 28, 15) + " " + ell_path(32, 32, 4.5, 13), rule="evenodd"))


@action("yowl")
def _():
    hole = "M29 16 L35 16 L34 32 L30 32 Z " + circ_path(32, 38.5, 3)
    return svg(F(bubble(hole), rule="evenodd"))


@action("wait")
def _():
    return svg(S("M16 6 L48 6 M16 58 L48 58", 4.5) + S("M20 6 Q20 24 32 32 Q44 24 44 6 M20 58 Q20 40 32 32 Q44 40 44 58", 4.2) +
               F("M24 54 Q32 44 40 54 Z"))


@action("headbutt_soft")
def _():
    return ACTIONS["headbutt"]()


# ---------------------------------------------------------------------------------------------
# Skill glyphs
# ---------------------------------------------------------------------------------------------

SKILLS = {}


def skill(name):
    def deco(fn):
        SKILLS[name] = fn
        return fn
    return deco


@skill("tree_agility")
def _():
    # leaping cat silhouette
    cat = ("M4 44 Q14 40 20 34 Q28 26 40 26 L46 18 L48 24 L54 22 L52 30 Q56 36 50 38 Q44 38 40 36 "
           "Q34 40 32 46 L36 54 L30 54 L26 46 Q20 48 14 52 L18 58 L12 58 L8 50 Q4 48 4 44 Z")
    return svg(F(cat) + S("M2 28 L14 28 M6 20 L16 20", 3.2))


@skill("tree_stealth")
def _():
    return svg(F("M40 6 A26 26 0 1 0 58 44 A20 20 0 1 1 40 6 Z") + F(cat_eye_path(26, 34, 9, 4.5)))


@skill("tree_charm")
def _():
    return svg(F(heart_path(32, 34, 1.05)))


@skill("tree_hunting")
def _():
    return svg(S("M14 8 Q30 22 24 56", 5.5) + S("M30 6 Q46 22 40 56", 5.5) + S("M46 8 Q60 22 54 50", 5.5))


@skill("tree_survival")
def _():
    leaf = "M10 54 Q8 18 54 8 Q56 48 10 54 Z"
    return svg(F(leaf + " M14 50 Q30 34 46 16 L48 18 Q32 36 16 52 Z", rule="evenodd"))


@skill("nhay_xa")
def _():
    return svg(S("M8 52 Q30 2 54 46", 4.5, extra='stroke-dasharray="1 9"') + S("M46 40 L55 48 L58 36", 4.5) + paw(12, 54, 16))


@skill("chan_bam")
def _():
    return svg(S("M10 4 L10 60", 5) + S("M22 14 Q32 22 30 34 M30 10 Q42 20 40 34 M38 16 Q50 26 48 38", 4.5) + paw(40, 50, 18))


@skill("dap_mem")
def _():
    return svg(paw(32, 22, 28) + S("M8 46 Q32 62 56 46", 5) + S("M14 54 Q32 66 50 54", 3, extra='stroke-opacity="0.6"'))


@skill("chay_mai")
def _():
    return svg(S("M4 50 L18 36 L32 50 L46 36 L60 50", 5) + S("M4 24 L26 24 M12 16 L36 16 M20 8 L44 8", 4))


@skill("thang_bang")
def _():
    return svg(S("M2 40 Q32 48 62 40", 4) + paw(32, 28, 24) + S("M12 22 Q8 30 12 36 M52 22 Q56 30 52 36", 3.4))


@skill("bat_tuong")
def _():
    return svg(S("M56 4 L56 60", 5) + S("M8 56 L48 22 L20 8", 4.5) + S("M14 4 L20 8 L14 14", 4.5) +
               S("M50 18 L56 22 M50 26 L56 22", 3))


@skill("buoc_nhung")
def _():
    return svg(paw(32, 26, 40) + S("M12 50 L22 50 M28 56 L36 56 M42 50 L52 50", 4, extra='stroke-opacity="0.7"'))


@skill("mat_dem")
def _():
    return svg(F(cat_eye_path(28, 38, 22, 11) + " " + ell_path(28, 38, 3.5, 10), rule="evenodd") +
               F("M50 4 A12 12 0 1 0 60 20 A9 9 0 1 1 50 4 Z"))


@skill("lan_tron")
def _():
    return svg(F(cat_eye_path(32, 32, 26, 12) + " " + ell_path(32, 32, 4, 10), rule="evenodd", extra='fill-opacity="0.55"') +
               S("M10 54 L54 10", 5.5))


@skill("bong_dem")
def _():
    return svg(F("M36 6 A26 26 0 1 0 58 40 A20 20 0 1 1 36 6 Z") + F(poly(star_pts(50, 14, 5, 2))) +
               F(poly(star_pts(56, 28, 3.5, 1.5))))


@skill("bong_ma")
def _():
    ghost = "M14 58 L14 28 A18 18 0 0 1 50 28 L50 58 L44 52 L38 58 L32 52 L26 58 L20 52 Z"
    return svg(F(ghost + " " + circ_path(25, 30, 3.5) + " " + circ_path(39, 30, 3.5), rule="evenodd", extra='fill-opacity="0.8"'))


@skill("tieng_keu_dang_yeu")
def _():
    return svg(F(bubble(heart_path(32, 30, 0.45)), rule="evenodd"))


@skill("ru_ru")
def _():
    return svg(F(heart_path(24, 34, 0.7)) + S("M44 20 Q50 32 44 44", 4) + S("M52 14 Q62 32 52 50", 4))


@skill("mat_long_lanh")
def _():
    return svg(F(cat_eye_path(28, 38, 22, 11) + " " + circ_path(28, 38, 7), rule="evenodd") + C(28, 38, 3) +
               F(poly([(52, 4), (55, 13), (64, 16), (55, 19), (52, 28), (49, 19), (40, 16), (49, 13)])))


@skill("ban_cua_pho")
def _():
    roof = "M4 28 Q18 25 32 10 Q46 25 60 28 L56 31 Q44 29 32 19 Q20 29 8 31 Z"
    return svg(F(roof) + S("M13 32 L13 56 L51 56 L51 32", 4.2) + F(heart_path(32, 43, 0.38)))


@skill("ngoi_sao_pho_cu")
def _():
    rays = " ".join(f"M{32 + math.cos(math.radians(a)) * 27:.1f} {34 + math.sin(math.radians(a)) * 27:.1f} "
                    f"L{32 + math.cos(math.radians(a)) * 31:.1f} {34 + math.sin(math.radians(a)) * 31:.1f}" for a in range(-54, 306, 72))
    return svg(F(poly(star_pts(32, 34, 22, 9.5))) + S(rays, 3.4))


@skill("tho_san")
def _():
    bird = "M10 28 Q20 18 32 26 Q44 18 54 28 Q44 24 32 34 Q20 24 10 28 Z"
    return svg(C(32, 32, 26, fill="none", stroke=W, w=3.4) + F(bird) + S("M32 2 L32 10 M32 54 L32 62 M2 32 L10 32 M54 32 L62 32", 3.4))


@skill("vo_chop")
def _():
    return svg(S("M6 44 Q22 4 46 30", 4.5) + S("M40 28 L48 32 L50 24", 4) + S("M38 42 Q46 48 44 58 M48 40 Q56 46 54 56", 4.2))


@skill("mui_thinh")
def _():
    nose = "M18 40 L38 40 L28 52 Z"
    return svg(F(nose) + S("M36 30 Q42 24 48 30 T60 30 M34 20 Q40 14 46 20 T58 20 M38 10 Q44 4 50 10", 3.6))


@skill("ria_nhay")
def _():
    return svg(C(32, 34, 5) + S("M26 30 L4 20 M26 34 L2 34 M26 38 L4 48 M38 30 L60 20 M38 34 L62 34 M38 38 L60 48", 3.4))


@skill("vua_san_moi")
def _():
    crown = "M8 48 L6 18 L20 30 L32 10 L44 30 L58 18 L56 48 Z M10 52 L54 52 L54 58 L10 58 Z"
    return svg(F(crown) + C(32, 38, 4, fill="#000", extra='fill-opacity="0"'))


@skill("ngu_sau")
def _():
    return GLYPHS["nap"]()


@skill("bung_khoe")
def _():
    bowl = "M6 34 L58 34 Q56 54 32 56 Q8 54 6 34 Z"
    return svg(F(bowl) + S("M22 26 Q18 20 22 14 Q26 8 22 2 M34 26 Q30 20 34 14 Q38 8 34 2", 3.6))


@skill("long_day")
def _():
    drop = "M42 4 Q54 20 54 28 A12 12 0 0 1 30 28 Q30 20 42 4 Z"
    return svg(S("M6 56 Q10 40 6 30 M16 58 Q20 40 16 26 M26 58 Q30 44 26 34", 4.5) + F(drop, extra='fill-opacity="0.85"'))


@skill("suc_ben")
def _():
    return svg(C(32, 32, 27, fill="none", stroke=W, w=4) + F("M35 10 L18 36 L30 36 L27 54 L46 28 L34 28 Z"))


@skill("chin_mang")
def _():
    nine = circ_path(32, 28, 8) + " " + circ_path(32, 28, 3.6)
    return svg(S(heart_path(32, 33, 1.0), 4) + F(nine, rule="evenodd") + S("M40 28 Q40 44 28 44", 4.2))


# ---------------------------------------------------------------------------------------------
# Item illustrations (full colour, 128 grid, ink outline)
# ---------------------------------------------------------------------------------------------

INK = "#2b1d14"
OW = 3.2  # outline width

ITEMS = {}


def item(name):
    def deco(fn):
        ITEMS[name] = fn
        return fn
    return deco


def lg(id_, stops, x1=0, y1=0, x2=0, y2=1):
    st = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{st}</linearGradient>'


def rg(id_, stops, cx=0.5, cy=0.5, r=0.5, fx=None, fy=None):
    fx = cx if fx is None else fx
    fy = cy if fy is None else fy
    st = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
    return f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}" fx="{fx}" fy="{fy}">{st}</radialGradient>'


def P(d, fill, stroke=INK, w=OW, extra=""):
    st = f'stroke="{stroke}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"' if stroke else ""
    return f'<path d="{d}" fill="{fill}" {st} {extra}/>'


def shadow(cx=64, cy=112, rx=40, ry=7):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#000" fill-opacity="0.22"/>'


def isvg(body, defs=""):
    return svg(body, 128, defs)


@item("cap")
def _():
    defs = (lg("capside", [(0, "#8f969c", 1), (0.5, "#e2e6e8", 1), (1, "#6c7378", 1)], 0, 0, 1, 0) +
            rg("captop", [(0, "#e84a32", 1), (0.7, "#b8281a", 1), (1, "#7c160e", 1)], 0.42, 0.38, 0.65))
    teeth = []
    n = 21
    for i in range(n * 2 + 1):
        a = math.radians(i * 180.0 / n)
        r = 46 if i % 2 == 0 else 41
        teeth.append((64 + math.cos(a) * r, 74 + math.sin(a) * r * 0.52))
    body = shadow(64, 102, 46, 8)
    body += P(poly(teeth) + " L18 78 L18 64 Z", "url(#capside)", extra="")
    body += P("M18 64 L18 76 Q64 104 110 76 L110 64 Z", "url(#capside)")
    top = ell_path(64, 62, 46, 24)
    body += P(top, "url(#captop)")
    body += E(64, 62, 33, 17, fill="none", stroke="#f2cf7e", w=2.2)
    body += P(poly(star_pts(64, 62, 13, 5.5, 5, -90)).replace("M", "M").replace(" Z", " Z"), "#f2cf7e", stroke=None,
              extra='transform="translate(0 0) scale(1 1)"')
    body += E(52, 52, 14, 5, fill="#ffffff", extra='fill-opacity="0.35"', rot=-12)
    return isvg(body, defs)


@item("fish")
def _():
    defs = (lg("fishbody", [(0, "#3d5f78", 1), (0.38, "#7d97a6", 1), (0.55, "#cfd8dc", 1), (1, "#f4f1e8", 1)]) +
            lg("fishfin", [(0, "#d6b347", 1), (1, "#8a7a3a", 1)]))
    body = shadow(64, 100, 48, 7)
    tail = "M96 62 L122 40 Q116 62 124 86 L96 68 Z"
    body += P(tail, "url(#fishfin)")
    dfin = "M50 44 Q62 26 82 38 L80 46 Z"
    body += P(dfin, "url(#fishfin)")
    bfin = "M60 80 Q68 94 80 84 Z"
    body += P(bfin, "url(#fishfin)")
    fish = "M8 64 C20 40 60 34 86 48 Q96 54 100 64 Q96 74 86 80 C60 94 20 88 8 64 Z"
    body += P(fish, "url(#fishbody)")
    body += S("M28 62 Q60 56 96 64", 1.6, color="#2f4a5c", extra='stroke-opacity="0.6"')
    body += S("M30 48 Q24 64 30 80", 2.4, color=INK)
    body += C(19, 59, 6.2, fill="#f6f1e1", stroke=INK, w=2) + C(19.5, 59, 3.2, fill="#1b1410") + C(18, 57.5, 1.1, fill="#fff")
    body += P("M8 64 Q12 68 18 67", "none", w=2.2)
    for i, x in enumerate(range(40, 92, 8)):
        body += f'<path d="M{x} 50 q4 4 0 8" fill="none" stroke="#ffffff" stroke-opacity="0.18" stroke-width="1.6"/>'
    body += E(52, 56, 26, 5, fill="#ffffff", extra='fill-opacity="0.28"', rot=-4)
    return isvg(body, defs)


@item("dried_fish")
def _():
    defs = lg("df", [(0, "#a8732f", 1), (0.5, "#d9a75a", 1), (1, "#8c5a22", 1)])
    body = shadow(64, 104, 44, 7)
    for i, (y, rot) in enumerate([(46, -14), (58, -5), (70, 4), (82, 12)]):
        f = f"M18 {y} C30 {y - 9} 70 {y - 9} 92 {y - 2} L110 {y - 8} L104 {y} L110 {y + 8} L92 {y + 2} C70 {y + 9} 30 {y + 9} 18 {y} Z"
        body += f'<g transform="rotate({rot} 64 {y})">' + P(f, "url(#df)", w=2.4) + C(26, y - 1.5, 2.2, fill=INK) + \
            S(f"M30 {y} L86 {y}", 1.2, color="#5a3a14", extra='stroke-opacity="0.6"') + "</g>"
    body += P("M58 36 L66 36 L68 96 L56 96 Z", "#c9b48a", w=2.2)
    body += S("M56 52 L68 50 M56 64 L68 62 M56 76 L68 74", 1.6, color="#8a7350")
    return isvg(body, defs)


@item("shrimp")
def _():
    defs = (lg("sh", [(0, "#ffb08f", 1), (0.55, "#f2683f", 1), (1, "#b8361d", 1)], 0, 0, 1, 1) +
            lg("shb", [(0, "#ffd6c2", 1), (1, "#f08a68", 1)]))
    body = shadow(64, 106, 42, 7)
    # curled body made of 6 tapered segments along a C-curve
    cx, cy = 62, 62
    segs = []
    n = 6
    for i in range(n):
        a0 = math.radians(-150 + i * 34)
        a1 = math.radians(-150 + (i + 1) * 34 + 6)
        r_out0, r_out1 = 40 - i * 2.6, 40 - (i + 1) * 2.6
        r_in0, r_in1 = 18 + i * 1.6, 18 + (i + 1) * 1.6
        p = [(cx + math.cos(a0) * r_out0, cy + math.sin(a0) * r_out0),
             (cx + math.cos(a1) * r_out1, cy + math.sin(a1) * r_out1),
             (cx + math.cos(a1) * r_in1, cy + math.sin(a1) * r_in1),
             (cx + math.cos(a0) * r_in0, cy + math.sin(a0) * r_in0)]
        mid_o = ((a0 + a1) / 2)
        ro = (r_out0 + r_out1) / 2 + 3
        d = (f"M{p[0][0]:.1f} {p[0][1]:.1f} Q{cx + math.cos(mid_o) * ro:.1f} {cy + math.sin(mid_o) * ro:.1f} {p[1][0]:.1f} {p[1][1]:.1f} "
             f"L{p[2][0]:.1f} {p[2][1]:.1f} L{p[3][0]:.1f} {p[3][1]:.1f} Z")
        segs.append(d)
    # head/carapace at the start of the curve (upper left)
    head = "M20 52 C14 36 26 22 40 24 L46 30 C40 40 34 50 30 58 Z"
    body += P(head, "url(#sh)")
    for d in reversed(segs):
        body += P(d, "url(#sh)", w=2.4)
    # tail fan at the end of the curve (lower left)
    a_end = math.radians(-150 + n * 34 + 6)
    tx, ty = cx + math.cos(a_end) * 28, cy + math.sin(a_end) * 28
    fan = (f"M{tx + 6:.1f} {ty - 6:.1f} L{tx - 16:.1f} {ty - 2:.1f} Q{tx - 22:.1f} {ty + 8:.1f} {tx - 12:.1f} {ty + 14:.1f} "
           f"L{tx - 2:.1f} {ty + 8:.1f} L{tx + 2:.1f} {ty + 18:.1f} Q{tx + 12:.1f} {ty + 14:.1f} {tx + 10:.1f} {ty + 2:.1f} Z")
    body += P(fan, "url(#shb)", w=2.4)
    # legs (swimmerets) on the inner curve
    for i in range(5):
        a = math.radians(-120 + i * 30)
        x0, y0 = cx + math.cos(a) * 20, cy + math.sin(a) * 20
        x1, y1 = cx + math.cos(a) * 12, cy + math.sin(a) * 12
        body += S(f"M{x0:.1f} {y0:.1f} L{x1:.1f} {y1:.1f}", 1.8, color="#b8361d")
    # antennae & eye
    body += S("M22 38 Q4 20 10 4 M26 32 Q20 10 34 2", 1.6, color=INK)
    body += C(30, 34, 3.2, fill=INK) + C(29.2, 33.2, 1, fill="#fff")
    body += E(70, 30, 12, 4, fill="#fff", extra='fill-opacity="0.45"', rot=12)
    return isvg(body, defs)


@item("gio_lua")
def _():
    defs = (rg("gl", [(0, "#f1e2d0", 1), (0.8, "#e3cbb2", 1), (1, "#d5b496", 1)], 0.45, 0.4, 0.6))
    body = shadow(64, 102, 46, 8)
    body += P(ell_path(64, 70, 46, 26) + " ", "#7a9a3e")  # leaf edge (side)
    body += P("M18 70 L18 62 L110 62 L110 70", "#6c8c34", stroke=None)
    body += P(ell_path(64, 62, 46, 26), "#5f8a2e")
    body += P(ell_path(64, 62, 41, 22.5), "url(#gl)", w=2.4)
    for (x, y, r) in [(48, 56, 2), (70, 68, 1.6), (80, 54, 1.8), (58, 72, 1.4), (40, 66, 1.2), (86, 64, 1.3)]:
        body += C(x, y, r, fill="#c4a080", extra='fill-opacity="0.8"')
    body += C(66, 60, 2.6, fill="#2b1d14", extra='fill-opacity="0.6"')
    body += E(52, 52, 14, 4, fill="#fff", extra='fill-opacity="0.4"', rot=-8)
    return isvg(body, defs)


@item("pate_crust")
def _():
    defs = (lg("crust", [(0, "#e3a24a", 1), (0.6, "#b8702a", 1), (1, "#7e4518", 1)]) +
            rg("crumb", [(0, "#fbecc8", 1), (1, "#e9cf98", 1)]))
    body = shadow(64, 104, 46, 7)
    loaf = "M14 76 C14 50 50 36 92 40 C110 42 118 54 116 66 C114 80 92 90 60 90 C30 90 14 88 14 76 Z"
    body += P(loaf, "url(#crust)")
    for x in (40, 62, 84):
        body += S(f"M{x - 8} {46 + (x - 40) * 0.05} Q{x} 54 {x + 10} {44}", 2.4, color="#7e4518")
    face = ell_path(26, 74, 15, 18)
    body += P(face, "url(#crumb)", w=2.6)
    pate = "M16 70 Q22 58 32 64 Q40 70 34 82 Q26 90 18 84 Q12 78 16 70 Z"
    body += P(pate, "#8a5634", stroke="#5c3520", w=1.8)
    body += E(70, 50, 22, 5, fill="#fff", extra='fill-opacity="0.28"', rot=-8)
    return isvg(body, defs)


@item("quail_egg")
def _():
    defs = rg("egg", [(0, "#ffffff", 1), (0.7, "#efe8dc", 1), (1, "#cfc4b2", 1)], 0.4, 0.35, 0.7)
    body = shadow(64, 104, 36, 7)
    egg = "M64 18 C86 18 96 52 96 70 C96 90 82 102 64 102 C46 102 32 90 32 70 C32 52 42 18 64 18 Z"
    body += P(egg, "url(#egg)")
    body += E(52, 46, 7, 13, fill="#fff", extra='fill-opacity="0.85"', rot=-18)
    body += S("M44 86 Q64 98 84 86", 2, color="#b8ab96", extra='stroke-opacity="0.7"')
    return isvg(body, defs)


@item("mooncake_crumb")
def _():
    defs = (rg("mctop", [(0, "#e8b060", 1), (0.7, "#c27a32", 1), (1, "#8c4e1c", 1)], 0.35, 0.3, 0.8) +
            lg("paste", [(0, "#b98c52", 1), (1, "#8c6232", 1)]) +
            rg("yolk", [(0, "#ffd65a", 1), (1, "#e0861a", 1)], 0.4, 0.4, 0.6))
    body = shadow(64, 106, 46, 7)
    # a quarter wedge of a round mooncake seen from above-front: apex at the back
    apex = (40, 38)
    # cut face (front-left): paste with the salted yolk
    face = "M40 38 L40 66 L102 92 L102 64 Z"
    # crust side (rounded edge, right)
    body += P("M102 64 Q118 44 104 24 L104 50 Q116 70 102 92 Z", "#9a5a22")
    body += P(face, "url(#paste)")
    body += P("M52 58 Q64 50 80 62 Q84 74 70 78 Q54 76 52 58 Z", "url(#yolk)", w=2)
    body += S("M46 50 L96 72", 1.2, color="#6a4420", extra='stroke-opacity="0.4"')
    # top crust (quarter disc) with stamped pattern
    top = "M40 38 L102 64 Q120 44 104 24 Q80 6 40 38 Z"
    body += P(top, "url(#mctop)")
    body += S("M58 34 Q76 24 94 32 M62 44 Q80 36 98 46", 2, color="#7a4214", extra='stroke-opacity="0.7"')
    body += S("M70 28 q4 6 0 12 M84 30 q4 6 0 12", 1.6, color="#7a4214", extra='stroke-opacity="0.6"')
    body += S("M40 38 L102 64", 2.2, color="#f2c27a")
    body += E(76, 26, 12, 3.5, fill="#fff", extra='fill-opacity="0.35"', rot=-10)
    # crumbs
    for (x, y, r) in [(24, 96, 2.6), (32, 102, 1.8), (114, 98, 2.2), (18, 88, 1.4)]:
        body += C(x, y, r, fill="#c27a32", stroke=INK, w=1)
    return isvg(body, defs)


@item("lucky_cat_figurine")
def _():
    defs = (lg("gold", [(0, "#fff0b0", 1), (0.35, "#f2c94c", 1), (0.75, "#c48a1c", 1), (1, "#8a5a0c", 1)], 0, 0, 1, 1) +
            lg("goldside", [(0, "#c48a1c", 1), (1, "#7a4c08", 1)]))
    body = shadow(64, 112, 34, 6)
    base = "M34 98 L94 98 L96 110 L32 110 Z"
    body += P(base, "url(#goldside)")
    torso = "M38 98 C34 78 38 62 48 56 L80 56 C90 62 94 78 90 98 Z"
    body += P(torso, "url(#gold)")
    # raised paw (left from viewer's right side)
    arm = "M80 64 C88 56 92 44 90 32 C88 26 98 24 100 30 C104 42 98 58 88 70 Z"
    body += P(arm, "url(#gold)")
    body += E(95, 28, 8, 7, fill="url(#gold)", stroke=INK, w=OW)
    head = cat_head_path(62, 42, 1.25)
    body += P(head, "url(#gold)")
    body += S("M50 44 Q54 40 58 44 M66 44 Q70 40 74 44", 2.6, color=INK)
    body += P("M59 50 L65 50 L62 53 Z", INK, w=1)
    body += S("M62 53 Q58 57 55 55 M62 53 Q66 57 69 55", 1.8, color=INK)
    body += S("M44 48 L34 46 M44 51 L34 52 M80 48 L90 46 M80 51 L90 52", 1.4, color=INK)
    # collar & bell
    body += P("M44 62 Q64 70 84 62 L84 67 Q64 75 44 67 Z", "#c8321e", w=2.2)
    body += C(64, 74, 6.5, fill="url(#gold)", stroke=INK, w=2.2) + S("M60 75 L68 75", 1.6, color=INK)
    # coin held in the other paw
    body += E(52, 86, 11, 9, fill="url(#gold)", stroke=INK, w=2.4) + S("M47 86 L57 86 M52 81 L52 91", 1.6, color="#8a5a0c")
    body += E(50, 32, 6, 3, fill="#fff", extra='fill-opacity="0.6"', rot=-20)
    body += E(46, 74, 3, 10, fill="#fff", extra='fill-opacity="0.35"', rot=10)
    return isvg(body, defs)


@item("letter")
def _():
    defs = lg("env", [(0, "#f6ecd6", 1), (1, "#dcc9a2", 1)])
    body = shadow(64, 104, 48, 7)
    env = "M12 34 L116 28 L118 94 L14 100 Z"
    body += P(env, "url(#env)")
    body += S("M12 34 L64 70 L116 28", OW, color=INK)
    body += S("M14 100 L52 62 M118 94 L76 60", 2, color="#9c8660", extra='stroke-opacity="0.8"')
    body += P("M88 36 L108 35 L109 54 L89 55 Z", "#b8321f", w=1.8)
    body += S("M92 40 L105 39 M92 45 L105 44 M92 50 L105 49", 1.2, color="#f2cf7e")
    body += C(64, 70, 8, fill="#a02818", stroke=INK, w=2) + paw(64, 71, 9, "#e06048")
    return isvg(body, defs)


@item("key")
def _():
    defs = lg("brass", [(0, "#f6d77a", 1), (0.5, "#c9962e", 1), (1, "#7e5a14", 1)], 0, 0, 1, 1)
    body = shadow(64, 108, 40, 6)
    bow = ell_path(40, 46, 22, 22) + " " + ell_path(40, 46, 11, 11)
    body += P(bow, "url(#brass)", extra='fill-rule="evenodd"')
    shaft = "M58 56 L104 92 L98 98 L52 62 Z"
    body += P(shaft, "url(#brass)")
    teeth = "M86 84 L80 92 L86 96 L90 90 L94 94 L100 88 Z"
    body += P(teeth, "url(#brass)")
    body += S("M30 30 Q16 24 12 10", 3.4, color="#c8321e") + S("M12 10 Q6 20 10 30 M12 10 Q18 18 14 28", 2.4, color="#e05a3a")
    body += E(32, 38, 6, 3, fill="#fff", extra='fill-opacity="0.6"', rot=-40)
    return isvg(body, defs)


@item("leg_band")
def _():
    defs = (lg("al", [(0, "#f2f4f6", 1), (0.5, "#a9b2ba", 1), (1, "#6e7880", 1)], 0, 0, 1, 0) +
            lg("alin", [(0, "#5e676e", 1), (1, "#9aa4ac", 1)], 0, 0, 1, 0))
    body = shadow(64, 100, 38, 7)
    body += P(ell_path(64, 50, 36, 14), "url(#alin)")
    body += P("M28 50 L28 76 Q64 98 100 76 L100 50 Q64 72 28 50 Z", "url(#al)")
    body += P(ell_path(64, 50, 36, 14) + " " + ell_path(64, 50, 30, 10), "url(#al)", extra='fill-rule="evenodd"')
    body += S("M42 76 L42 84 M50 78 L50 87 M58 80 L58 89 M70 80 L70 89 M78 78 L78 87", 2.2, color="#4c555c")
    body += C(88, 74, 3, fill="#2f6f9a")
    return isvg(body, defs)


@item("toy_mouse")
def _():
    defs = rg("felt", [(0, "#b8b1a8", 1), (0.7, "#8f877d", 1), (1, "#6a635a", 1)], 0.4, 0.35, 0.7)
    body = shadow(60, 100, 44, 7)
    body += S("M100 82 Q118 92 112 106 Q106 118 122 120", 3, color="#c8321e")
    m = "M16 78 C20 58 44 44 72 48 C94 52 106 68 100 84 C94 96 40 98 16 78 Z"
    body += P(m, "url(#felt)")
    body += E(46, 50, 10, 12, fill="#f0b3b0", stroke=INK, w=2.6, rot=-20)
    body += E(30, 58, 8, 10, fill="#f0b3b0", stroke=INK, w=2.6, rot=-35)
    body += C(28, 70, 2.6, fill=INK) + C(15, 79, 3, fill="#e28a8a", stroke=INK, w=1.6)
    body += S("M18 80 L4 76 M18 82 L4 86", 1.4, color=INK)
    body += S("M40 86 L46 74 M58 90 L62 76 M76 88 L78 74", 1.4, color="#6a635a", extra='stroke-dasharray="2 3"')
    body += E(64, 58, 18, 5, fill="#fff", extra='fill-opacity="0.25"', rot=-6)
    return isvg(body, defs)


@item("yarn")
def _():
    defs = rg("yarn", [(0, "#ff8a5a", 1), (0.7, "#d9462a", 1), (1, "#9a2c18", 1)], 0.38, 0.35, 0.7)
    body = shadow(60, 104, 40, 7)
    body += S("M90 80 Q112 88 106 102 Q100 114 124 116", 3.2, color="#d9462a")
    body += C(60, 60, 38, fill="url(#yarn)", stroke=INK, w=OW)
    for d in ["M26 44 Q60 30 94 52", "M24 62 Q60 46 98 70", "M30 82 Q60 66 90 88", "M40 28 Q30 60 44 94",
              "M62 22 Q50 60 66 98", "M84 32 Q72 60 88 86"]:
        body += S(d, 2, color="#8a2410", extra='stroke-opacity="0.75"')
    body += S("M34 50 Q58 40 80 50", 1.6, color="#ffc0a0", extra='stroke-opacity="0.7"')
    return isvg(body, defs)


@item("silver_spoon")
def _():
    defs = lg("ag", [(0, "#ffffff", 1), (0.45, "#c8ced4", 1), (1, "#7d868e", 1)], 0, 0, 1, 1)
    body = shadow(64, 108, 40, 6)
    bowl = ell_path(40, 42, 18, 26)
    body += f'<g transform="rotate(-40 64 64)">' + P(bowl, "url(#ag)") + \
        P("M36 66 Q38 100 40 116 Q42 120 44 116 Q46 100 44 66 Z", "url(#ag)") + \
        E(34, 34, 5, 12, fill="#fff", extra='fill-opacity="0.8"') + "</g>"
    return isvg(body, defs)


@item("hair_clip")
def _():
    defs = rg("petal", [(0, "#ffd0e0", 1), (1, "#e2608c", 1)], 0.5, 0.5, 0.6)
    body = shadow(64, 104, 42, 6)
    body += P("M14 82 L112 66 L114 74 L16 90 Z", "#d4d8dc")
    body += S("M20 84 L106 70", 1.4, color="#ffffff", extra='stroke-opacity="0.8"')
    for i in range(5):
        a = math.radians(i * 72 - 90)
        cx, cy = 64 + math.cos(a) * 14, 54 + math.sin(a) * 14
        body += E(cx, cy, 12, 9, fill="url(#petal)", stroke=INK, w=2.4, rot=i * 72)
    body += C(64, 54, 7, fill="#ffd34a", stroke=INK, w=2.2)
    return isvg(body, defs)


@item("glass_marble")
def _():
    defs = (rg("gm", [(0, "#d8f4ff", 0.95), (0.6, "#5fb3c9", 0.9), (1, "#1f5e74", 1)], 0.42, 0.4, 0.62))
    body = shadow(64, 104, 34, 7)
    body += C(64, 62, 36, fill="url(#gm)", stroke=INK, w=OW)
    body += S("M40 72 Q56 40 80 56 Q92 66 80 82", 6, color="#f2a23a", extra='stroke-opacity="0.85"')
    body += S("M44 56 Q60 72 86 60", 3, color="#e8574a", extra='stroke-opacity="0.7"')
    body += E(52, 46, 10, 6, fill="#fff", extra='fill-opacity="0.85"', rot=-30)
    body += C(80, 80, 3, fill="#fff", extra='fill-opacity="0.5"')
    return isvg(body, defs)


@item("brass_bell")
def _():
    defs = rg("bb", [(0, "#fff0b0", 1), (0.45, "#e0b040", 1), (1, "#8a5c10", 1)], 0.38, 0.35, 0.7)
    body = shadow(64, 108, 34, 6)
    body += S("M64 14 L64 24", 4, color=INK) + E(64, 14, 7, 6, fill="none", stroke=INK, w=3.2)
    body += C(64, 64, 38, fill="url(#bb)", stroke=INK, w=OW)
    body += S("M28 64 Q64 76 100 64", 3, color=INK)
    body += P("M58 76 L70 76 L70 96 Q64 100 58 96 Z", "#2b1d14", w=1.4)
    body += C(64, 88, 5, fill="#2b1d14")
    body += E(48, 46, 10, 6, fill="#fff", extra='fill-opacity="0.7"', rot=-30)
    return isvg(body, defs)


@item("pigeon_feather")
def _():
    defs = (lg("fe", [(0, "#4a8a7a", 1), (0.3, "#7a6e9a", 1), (0.55, "#9aa2ac", 1), (1, "#d8dde2", 1)], 0, 1, 1, 0))
    body = shadow(64, 110, 40, 6)
    vane = "M24 110 C14 80 30 40 70 18 C96 6 112 14 112 14 C110 30 98 60 70 84 C52 98 36 104 24 110 Z"
    body += P(vane, "url(#fe)")
    body += S("M20 118 Q60 70 110 16", 3, color="#e8e4dc")
    for i in range(7):
        t = 0.2 + i * 0.1
        x = 20 + t * 90
        y = 118 - t * 102
        body += S(f"M{x:.1f} {y:.1f} l{-10 - i:.1f} {8 + i * 0.5:.1f}", 1.4, color="#ffffff", extra='stroke-opacity="0.45"')
        body += S(f"M{x:.1f} {y:.1f} l{9 + i * 0.6:.1f} {-2:.1f}", 1.2, color="#2b1d14", extra='stroke-opacity="0.25"')
    body += S("M78 52 L86 46", 3, color="#2b1d14", extra='stroke-opacity="0.0"')
    return isvg(body, defs)


@item("memory_photo")
def _():
    defs = (lg("sep", [(0, "#c9a777", 1), (0.6, "#9a774a", 1), (1, "#5e4426", 1)]) +
            rg("vig", [(0, "#000", 0), (0.75, "#000", 0.05), (1, "#000", 0.45)], 0.5, 0.5, 0.75))
    body = shadow(64, 112, 46, 6)
    body += '<g transform="rotate(-6 64 64)">'
    body += P("M16 14 L112 14 L112 112 L16 112 Z", "#f3ead6", w=2.6)
    body += P("M24 22 L104 22 L104 92 L24 92 Z", "url(#sep)", w=1.6)
    # rooftops + lantern string silhouette + a seated figure
    body += P("M24 70 L36 60 L48 70 L48 92 L24 92 Z M48 74 L62 62 L76 74 L76 92 L48 92 Z M76 66 L90 56 L104 66 L104 92 L76 92 Z",
              "#4a3420", stroke=None, extra='fill-opacity="0.8"')
    body += S("M24 40 Q64 52 104 38", 1.2, color="#3a2814")
    for x in (38, 54, 70, 86):
        body += C(x, 46 + (abs(64 - x) * -0.12) + 2, 3.4, fill="#e8d0a0", extra='fill-opacity="0.85"')
    body += P("M58 92 Q58 80 62 78 Q60 72 64 70 Q68 72 66 78 Q70 80 70 92 Z", "#2e2014", stroke=None)
    body += P("M24 22 L104 22 L104 92 L24 92 Z", "url(#vig)", stroke=None)
    body += S("M30 100 L78 100", 1.6, color="#8a7a60", extra='stroke-opacity="0.6"')
    body += "</g>"
    return isvg(body, defs)


def collar(strap_fill, strap_edge, pendant):
    body = shadow(64, 108, 44, 6)
    # inner back half of the strap (darker), then the front half over it
    body += P(ell_path(64, 56, 46, 34) + " " + ell_path(64, 56, 32, 22), strap_fill, extra='fill-rule="evenodd"')
    body += P("M18 56 Q18 22 64 22 Q110 22 110 56 Q100 34 64 34 Q28 34 18 56 Z", "#000", stroke=None, extra='fill-opacity="0.28"')
    body += E(64, 56, 39, 28, fill="none", stroke=strap_edge, w=1.8, extra='stroke-dasharray="4 3"')
    body += P("M14 46 L28 42 L32 66 L18 70 Z", "#e2dccb", w=2.4) + S("M20 50 L27 48 M21 58 L29 56", 1.6, color="#8a8270")
    return body + pendant


@item("collar_red")
def _():
    defs = lg("cr", [(0, "#e2503a", 1), (1, "#8e2014", 1)])
    pend = C(64, 96, 9, fill="#e8c24a", stroke=INK, w=2.4) + paw(64, 97, 10, "#8a5a0c")
    return isvg(collar("url(#cr)", "#ffb0a0", pend), defs)


@item("collar_bell")
def _():
    defs = lg("cb", [(0, "#3e5f8a", 1), (1, "#1c2e48", 1)]) + rg("gb", [(0, "#fff0b0", 1), (1, "#b8861c", 1)], 0.38, 0.35, 0.7)
    pend = C(64, 98, 12, fill="url(#gb)", stroke=INK, w=2.6) + S("M54 100 Q64 104 74 100", 2, color=INK) + C(64, 104, 2.4, fill=INK)
    return isvg(collar("url(#cb)", "#a0c0e8", pend), defs)


@item("collar_jade")
def _():
    defs = lg("cj", [(0, "#a07848", 1), (1, "#5e4222", 1)]) + rg("jd", [(0, "#c8f0d0", 1), (0.6, "#5aa878", 1), (1, "#2c6a48", 1)], 0.4, 0.35, 0.7)
    pend = P("M64 86 Q78 92 76 104 Q72 114 64 114 Q56 114 52 104 Q50 92 64 86 Z", "url(#jd)", w=2.4) + C(64, 101, 4, fill="#2c6a48")
    return isvg(collar("url(#cj)", "#e8c890", pend), defs)


@item("catnip")
def _():
    defs = lg("leaf", [(0, "#a6d36a", 1), (1, "#4f8a2e", 1)])
    body = shadow(64, 110, 36, 6)
    body += S("M64 116 Q60 80 66 20", 3.6, color="#5a7a2a")
    leaves = [(64, 30, 14, -30), (64, 30, 14, 30), (64, 54, 18, -40), (64, 54, 18, 40), (64, 80, 20, -45), (64, 80, 20, 45)]
    for (x, y, s, rot) in leaves:
        d = f"M{x} {y} C{x + s * 0.4} {y - s * 0.8} {x + s * 1.6} {y - s * 0.6} {x + s * 1.8} {y} C{x + s * 1.6} {y + s * 0.6} {x + s * 0.4} {y + s * 0.6} {x} {y} Z"
        body += f'<g transform="rotate({rot} {x} {y})">' + P(d, "url(#leaf)", w=2.2) + \
            S(f"M{x} {y} L{x + s * 1.6} {y}", 1.2, color="#3c6a20") + "</g>"
    for (x, y) in [(66, 14), (60, 10), (70, 9)]:
        body += C(x, y, 3.2, fill="#d8c0f0", stroke=INK, w=1.4)
    return isvg(body, defs)


def bottle(liquid_grad, label, extra=""):
    body = shadow(64, 112, 30, 6)
    glass = "M54 18 L74 18 L74 36 Q96 46 96 74 L96 100 Q96 110 86 110 L42 110 Q32 110 32 100 L32 74 Q32 46 54 36 Z"
    liquid = "M35 64 Q64 58 93 64 L93 100 Q93 107 86 107 L42 107 Q35 107 35 100 Z"
    body += P(glass, "#e9f2ee", extra='fill-opacity="0.35"')
    body += P(liquid, liquid_grad, stroke=None)
    body += P(glass, "none")
    body += P("M52 6 L76 6 L76 20 L52 20 Z", "#a87a48", w=2.4)
    body += label + extra
    body += E(44, 70, 4, 16, fill="#fff", extra='fill-opacity="0.55"')
    return body


@item("herbal_tonic")
def _():
    defs = lg("ht", [(0, "#d98a2a", 0.95), (1, "#7a3a10", 1)])
    label = P("M40 76 L88 76 L88 98 L40 98 Z", "#efe0bf", w=2) + S("M48 87 Q56 80 64 87 Q72 94 80 87", 2.2, color="#4f8a2e")
    return isvg(bottle("url(#ht)", label), defs)


@item("skill_tonic")
def _():
    defs = rg("st", [(0, "#fff6b0", 1), (0.5, "#f2c94c", 0.95), (1, "#c47a10", 1)], 0.5, 0.6, 0.6)
    label = F(poly(star_pts(64, 86, 13, 5.5)), color="#fff8d8", extra=f'stroke="{INK}" stroke-width="2" stroke-linejoin="round"')
    sparkle = S("M100 30 L100 42 M94 36 L106 36 M24 40 L24 48 M20 44 L28 44", 2.4, color="#f2cf7e")
    return isvg(bottle("url(#st)", label, sparkle), defs)


# ---------------------------------------------------------------------------------------------

def write_group(group, table):
    d = os.path.join(SRC, group)
    os.makedirs(d, exist_ok=True)
    for name, fn in table.items():
        with open(os.path.join(d, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(fn())
    return len(table)


def main():
    os.makedirs(SRC, exist_ok=True)
    with open(os.path.join(SRC, ".gdignore"), "w") as f:
        f.write("")
    n = write_group("glyphs", GLYPHS)
    n += write_group("actions", ACTIONS)
    n += write_group("skills", SKILLS)
    n += write_group("items", ITEMS)
    print("wrote", n, "svg icons to", SRC)


if __name__ == "__main__":
    main()
