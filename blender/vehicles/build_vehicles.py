"""Build the vehicles of Mèo Cam (original, unbranded designs at real-world dimensions).

    tools/blender_run.sh blender/vehicles/build_vehicles.py [-- id ... [--nopreview]]

ids: scooter_auto, underbone_step, manual_classic, bicycle_city, cyclo, cargo_trike, taxi_hatch,
     delivery_van, helmet_half, helmet_open
Output: assets/models/vehicles/<id>.glb (+ .import with the vehicles post-import script) and entries
merged into assets/models/vehicles/catalog.json.  Wheels are separate nodes (wheel_front, wheel_rear,
wheel_front_L ...) with the origin on the hub and spin axis = local X.  Seat markers are empties
SEAT_<role>.  Requires blender/vehicles/gen_textures.py output.
"""
from __future__ import annotations

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common as C          # noqa: E402
import nature_godot as G    # noqa: E402
import vehicles_lib as V    # noqa: E402

OUT = "models/vehicles"
CATALOG = C.asset_path(f"{OUT}/catalog.json")


# ---------------------------------------------------------------------------
# shared part helpers
# ---------------------------------------------------------------------------
def fender(name, center, radius, width, a0, a1, material, segs=18, thick=0.004, lip=0.012):
    """Curved U-channel mudguard around a wheel (angles in degrees, 0 = front (-Y), 90 = top)."""
    bm = bmesh.new()
    cy, cz = center[1], center[2]
    prof = [(-width / 2, lip), (-width / 2, 0.0), (-width * 0.3, -0.006), (0, -0.008), (width * 0.3, -0.006),
            (width / 2, 0.0), (width / 2, lip)]
    rings = []
    for i in range(segs + 1):
        a = math.radians(a0 + (a1 - a0) * i / segs)
        dy, dz = -math.cos(a), math.sin(a)
        ring = []
        for x, off in prof:
            r = radius - off
            ring.append(bm.verts.new((center[0] + x, cy + dy * r, cz + dz * r)))
        rings.append(ring)
    for i in range(segs):
        for k in range(len(prof) - 1):
            bm.faces.new([rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]])
    ob = V._obj(name, bm, material, None, 0)
    m = ob.modifiers.new("s", "SOLIDIFY")
    m.thickness = thick
    m.offset = 0
    C.apply_modifiers(ob)
    C.uv_cube_project(ob, 1.0)
    C.shade_smooth(ob, 50)
    return ob


def lamp(name, center, r, depth, material, axis="Y", flip=False, bezel="veh_chrome"):
    """Round lamp: chrome bezel ring + domed lens. axis Y: faces -Y (front) unless flip."""
    s = 1 if flip else -1
    lens = V.lathe(name + "_lens", [(0.0, s * depth * 0.55), (r * 0.6, s * depth * 0.5), (r * 0.92, s * depth * 0.3),
                                    (r * 0.95, 0.0)], center, axis, material, 24, 60)
    ring = V.lathe(name + "_bezel", [(r * 0.93, s * depth * 0.35), (r * 1.08, s * depth * 0.2), (r * 1.1, -s * depth * 0.6),
                                     (r * 0.9, -s * depth * 0.8)], center, axis, bezel, 24, 40)
    return [lens, ring]


def kickstand(x, y, z_top, material="veh_steel_dark"):
    return V.tube("stand", [(x, y, z_top), (x + 0.12, y + 0.08, 0.015)], 0.009, material, 6, 0)


def finish(vid, body_parts, wheels, colliders, markers, entry, preview=True, mud=0.5, view=None, wear_seed=1):
    body = V.finish_body(body_parts, f"{vid}_body")
    V.bake_wear([body], mud=mud, wheels=wheels, seed=wear_seed)
    objs = [body] + list(wheels) + list(colliders) + list(markers)
    path = C.asset_path(f"{OUT}/{vid}.glb")
    G.export_glb(path, objs)
    G.glb_import(path, "vehicles")
    st = G.glb_stats(path)
    xs, ys, zs = [], [], []
    for o in [body] + list(wheels):
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            xs.append(w.x)
            ys.append(w.y)
            zs.append(w.z)
    base = {
        "id": vid, "file": f"res://assets/models/vehicles/{vid}.glb",
        "width": round(max(xs) - min(xs), 3), "depth": round(max(ys) - min(ys), 3), "height": round(max(zs), 3),
        "length": round(max(ys) - min(ys), 3), "footprint": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)],
        "floors": 0, "style": "vehicle", "climb_points": [], "nap_spots": [], "entrances": [],
        "wheels": [{"node": w.name, "radius": round(w.get("radius", 0.3), 3),
                    "position": G.to_godot(w.location)} for w in wheels],
        "wheel_spin_axis": "x", "tris": st["tris"], "materials": st["materials"], "dynamic": False,
        "surface": "metal",
    }
    base.update(entry)
    G.write_catalog(CATALOG, [base])
    print(f"BUILT {vid}: tris={st['tris']} size={base['width']}x{base['length']}x{base['height']}")
    if preview:
        L = max(base["length"], base["height"])
        v = view or {}
        C.preview_render(C.qa_path(f"vehicles-nature/veh_{vid}.png"), target=v.get("target", (0, 0, base["height"] * 0.45)),
                         distance=v.get("distance", L * 1.9), yaw_deg=v.get("yaw", 55), pitch_deg=v.get("pitch", 12),
                         res=(640, 480), samples=24, lens=45, sun_strength=4.0, world_strength=0.9)
    return base


def wheel(name, center, r_out, tyre_w, r_rim, style, **kw):
    w = V.make_wheel(name, center, r_out, tyre_w, r_rim, style, **kw)
    w["radius"] = r_out
    return w


def plate(name, rect, center, size, facing="+Y"):
    return V.decal(name, rect, center, size, facing)


def new():
    C.reset_scene()


# ---------------------------------------------------------------------------
# 1. automatic scooter (125 cc class)  L 1.86  W 0.69  H 1.13  WB 1.27  seat 0.77
# ---------------------------------------------------------------------------
def scooter_auto(preview=True, paint="red"):
    new()
    P = f"veh_paint_{paint}"
    WB, RF, RR = 1.27, 0.25, 0.258
    yf, yr = -WB / 2, WB / 2
    parts = []
    # floorboard + its rubber mat
    parts.append(V.rbox("floor", (0.34, 0.5, 0.05), (0, -0.05, 0.335), "veh_plastic_black", 0.015))
    parts.append(V.rbox("floormat", (0.3, 0.44, 0.006), (0, -0.05, 0.362), "veh_rubber", 0.002))
    # front leg shield / apron (curved), front nose
    parts.append(V.loft("apron", [(-0.55, 0, 0.66, 0.15, 0.26, 2.6), (-0.52, 0, 0.64, 0.19, 0.32, 2.8),
                                  (-0.47, 0, 0.63, 0.21, 0.34, 3.2), (-0.42, 0, 0.62, 0.2, 0.33, 3.2),
                                  (-0.4, 0, 0.6, 0.17, 0.29, 3.0)], P, 28))
    parts.append(V.loft("nose", [(-0.6, 0, 0.82, 0.06, 0.05, 2.2), (-0.585, 0, 0.78, 0.11, 0.1, 2.4),
                                 (-0.55, 0, 0.75, 0.14, 0.13, 2.6)], P, 20))
    # handlebar cover with headlight
    parts.append(V.loft("hcover", [(-0.6, 0, 1.0, 0.14, 0.06, 2.4), (-0.56, 0, 1.01, 0.27, 0.075, 2.6),
                                   (-0.47, 0, 1.03, 0.29, 0.08, 2.8), (-0.4, 0, 1.04, 0.22, 0.07, 2.6),
                                   (-0.36, 0, 1.03, 0.12, 0.05, 2.4)], P, 24))
    parts.append(V.loft("dash", [(-0.43, 0, 1.08, 0.12, 0.025, 2.4), (-0.38, 0, 1.075, 0.1, 0.02, 2.4)],
                        "veh_plastic_black", 16))
    parts += lamp("headlight", (0, -0.612, 1.0), 0.06, 0.04, "veh_light_head")
    for sx in (-1, 1):
        parts.append(V.rbox(f"blinkF{sx}", (0.06, 0.03, 0.025), (sx * 0.2, -0.59, 0.99), "veh_light_amber", 0.008))
        parts.append(V.tube(f"bar{sx}", [(sx * 0.2, -0.47, 1.04), (sx * 0.33, -0.44, 1.045)], 0.011, "veh_chrome", 8, 0))
        parts.append(V.cyl(f"grip{sx}", 0.017, 0.12, (sx * 0.355, -0.44, 1.045), "X", "veh_rubber", 12))
        parts.append(V.tube(f"lever{sx}", [(sx * 0.27, -0.48, 1.06), (sx * 0.35, -0.5, 1.05)], 0.006, "veh_alloy", 6, 0))
        parts.append(V.tube(f"mstalk{sx}", [(sx * 0.22, -0.43, 1.07), (sx * 0.26, -0.45, 1.2), (sx * 0.28, -0.46, 1.24)],
                            0.006, "veh_chrome", 6, 0.03))
        parts.append(V.sphere(f"mirror{sx}", 0.06, (sx * 0.3, -0.46, 1.27), "veh_plastic_black", (1.0, 0.25, 0.65), 12, 8))
        parts.append(V.sphere(f"mglass{sx}", 0.052, (sx * 0.3, -0.447, 1.27), "veh_mirror", (1.0, 0.05, 0.6), 12, 8))
    # steering column + front fork, front mudguard
    parts.append(V.tube("column", [(0, -0.47, 0.98), (0, -0.53, 0.78)], 0.025, "veh_steel_dark", 10, 0))
    for sx in (-1, 1):
        parts.append(V.tube(f"fork{sx}", [(sx * 0.07, -0.53, 0.8), (sx * 0.07, yf + 0.02, RF + 0.02)], 0.019,
                            "veh_alloy", 10, 0))
    parts.append(fender("fenderF", (0, yf, RF), RF + 0.035, 0.12, 25, 150, P))
    # rear body (under-seat storage + side panels) and tail
    parts.append(V.loft("rearbody", [(-0.2, 0, 0.47, 0.13, 0.12, 2.6, 0.3), (0.0, 0, 0.55, 0.17, 0.17, 3.0, 0.2),
                                     (0.25, 0, 0.6, 0.19, 0.17, 3.2), (0.5, 0, 0.64, 0.18, 0.13, 3.0),
                                     (0.72, 0, 0.68, 0.14, 0.09, 2.8), (0.86, 0, 0.71, 0.1, 0.06, 2.6),
                                     (0.93, 0, 0.72, 0.06, 0.04, 2.4)], P, 32))
    parts.append(V.loft("seat", [(-0.08, 0, 0.73, 0.1, 0.04, 2.6), (0.02, 0, 0.765, 0.16, 0.055, 3.2),
                                 (0.3, 0, 0.765, 0.165, 0.055, 3.4), (0.45, 0, 0.775, 0.16, 0.055, 3.2),
                                 (0.66, 0, 0.785, 0.14, 0.05, 3.0), (0.8, 0, 0.78, 0.09, 0.035, 2.6)],
                        "veh_vinyl_black", 28))
    parts.append(V.tube("grabrail", [(-0.16, 0.6, 0.76), (-0.15, 0.85, 0.77), (0, 0.9, 0.78), (0.15, 0.85, 0.77),
                                     (0.16, 0.6, 0.76)], 0.012, "veh_plastic_black", 8, 0.06))
    parts.append(V.rbox("taillight", (0.17, 0.05, 0.06), (0, 0.935, 0.71), "veh_light_tail", 0.015))
    for sx in (-1, 1):
        parts.append(V.rbox(f"blinkR{sx}", (0.05, 0.03, 0.025), (sx * 0.12, 0.93, 0.66), "veh_light_amber", 0.008))
    # engine / CVT swing-arm unit (left) + exhaust (right) + rear mudguard + plate
    parts.append(V.loft("cvt", [(0.08, -0.11, 0.33, 0.06, 0.09, 2.6), (0.2, -0.115, 0.32, 0.075, 0.12, 3.0),
                                (0.5, -0.115, 0.28, 0.07, 0.11, 3.0), (yr, -0.115, RR, 0.06, 0.075, 2.6)],
                        "veh_engine", 20))
    parts.append(V.cyl("airbox", 0.07, 0.22, (-0.12, 0.42, 0.5), "Y", "veh_plastic_black", 14))
    parts.append(V.tube("exhpipe", [(0.04, 0.12, 0.2), (0.12, 0.25, 0.2), (0.15, 0.4, 0.28)], 0.022, "veh_steel_dark", 8, 0.05))
    parts.append(V.cyl("muffler", 0.05, 0.38, (0.16, 0.6, 0.32), "Y", "veh_steel_dark", 16, r2=0.042))
    parts.append(V.rbox("heatshield", (0.025, 0.3, 0.07), (0.215, 0.58, 0.34), "veh_chrome", 0.01))
    parts.append(V.cyl("exhtip", 0.025, 0.05, (0.16, 0.8, 0.32), "Y", "veh_chrome", 12))
    parts.append(V.tube("shock", [(0.1, yr - 0.08, 0.32), (0.11, 0.42, 0.56)], 0.018, "veh_alloy", 8, 0))
    parts.append(fender("fenderR", (0, yr, RR), RR + 0.03, 0.12, 95, 185, "veh_plastic_black"))
    parts.append(V.rbox("plateholder", (0.21, 0.02, 0.16), (0, 0.985, 0.52), "veh_plastic_black", 0.008))
    parts.append(plate("plate", "plate_moto_a", (0, 0.996, 0.52), (0.19, 0.14), "+Y"))
    parts.append(V.rbox("platelight", (0.06, 0.03, 0.025), (0, 0.98, 0.615), "veh_light_tail", 0.006))
    parts.append(kickstand(-0.1, 0.05, 0.3))
    for sx in (-1, 1):
        parts.append(V.decal(f"brand{sx}", "brand_saola", (sx * 0.192, 0.35, 0.6), (0.22, 0.07), "+X" if sx > 0 else "-X"))
        parts.append(V.rbox(f"peg{sx}", (0.07, 0.04, 0.02), (sx * 0.2, 0.42, 0.42), "veh_plastic_black", 0.006))
    wheels = [wheel("wheel_front", (0, yf, RF), RF, 0.085, 0.178, "cast", spokes=5, disc=0.11),
              wheel("wheel_rear", (0, yr, RR), RR, 0.095, 0.178, "cast", spokes=5)]
    cols = [V.box_col("col_plastic_seat", (0, 0.36, 0.83), (0.32, 0.88, 0.12)),
            V.box_col("col_plastic_floor", (0, -0.05, 0.37), (0.34, 0.5, 0.08)),
            V.box_col("col_metal_body", (0, 0.3, 0.71), (0.36, 1.25, 0.6)),
            V.box_col("col_metal_front", (0, -0.47, 0.98), (0.46, 0.3, 0.98))]
    mk = [V.marker("SEAT_rider", (0, 0.25, 0.82)), V.marker("SEAT_pillion", (0, 0.62, 0.84)),
          V.marker("NAP_seat", (0, 0.4, 0.83))]
    return finish("scooter_auto", parts, wheels, cols, mk, {
        "kind": "scooter", "name_key": "VEH_SCOOTER", "wheelbase": WB, "seat": [0.0, 0.82, -0.25],
        "seats": {"rider": [0.0, 0.82, -0.25], "pillion": [0.0, 0.84, -0.62]}, "rider_pose": "scooter",
        "nap_spots": [[0.0, 0.83, -0.4]], "mass": 112.0, "paint": paint, "max_speed": 16.0}, preview)



# ---------------------------------------------------------------------------
# 2. underbone step-through (110 cc)  L 1.9  W 0.7  H 1.06  WB 1.23, 17" spoked wheels, chrome rack
# ---------------------------------------------------------------------------
def underbone_step(preview=True, paint="blue"):
    new()
    P = f"veh_paint_{paint}"
    WB, R = 1.23, 0.285
    yf, yr = -WB / 2, WB / 2
    parts = []
    # leg shield (thin curved plate) + spine cover over the backbone
    parts.append(V.loft("legshield", [(-0.45, 0, 0.6, 0.18, 0.24, 2.4), (-0.43, 0, 0.6, 0.22, 0.28, 2.8),
                                      (-0.405, 0, 0.6, 0.21, 0.27, 2.8), (-0.39, 0, 0.6, 0.17, 0.23, 2.4)], P, 28))
    parts.append(V.loft("spine", [(-0.47, 0, 0.82, 0.05, 0.06, 2.2), (-0.38, 0, 0.62, 0.07, 0.1, 2.4),
                                  (-0.25, 0, 0.46, 0.08, 0.08, 2.4), (-0.05, 0, 0.44, 0.09, 0.07, 2.4),
                                  (0.08, 0, 0.5, 0.1, 0.09, 2.4)], P, 20))
    parts.append(V.tube("frame", [(0, -0.5, 0.93), (0, -0.48, 0.8), (0, -0.3, 0.47), (0, 0.05, 0.44), (0, 0.25, 0.62),
                                  (0, 0.85, 0.72)], 0.024, "veh_steel_dark", 8, 0.08))
    # side covers + rear body, seat, chrome rack
    parts.append(V.loft("rearbody", [(0.05, 0, 0.6, 0.1, 0.11, 2.4), (0.2, 0, 0.62, 0.14, 0.12, 2.8),
                                     (0.45, 0, 0.66, 0.13, 0.1, 2.8), (0.7, 0, 0.7, 0.09, 0.07, 2.6),
                                     (0.86, 0, 0.72, 0.06, 0.045, 2.4)], P, 24))
    parts.append(V.loft("seat", [(0.0, 0, 0.74, 0.1, 0.035, 2.6), (0.08, 0, 0.765, 0.15, 0.05, 3.2),
                                 (0.4, 0, 0.775, 0.15, 0.05, 3.2), (0.62, 0, 0.775, 0.13, 0.045, 3.0),
                                 (0.72, 0, 0.76, 0.08, 0.03, 2.6)], "veh_vinyl_black", 24))
    for sx in (-1, 1):
        parts.append(V.tube(f"rackside{sx}", [(sx * 0.12, 0.55, 0.75), (sx * 0.13, 0.7, 0.8), (sx * 0.13, 0.98, 0.8),
                                              (sx * 0.05, 1.02, 0.8)], 0.008, "veh_chrome", 6, 0.03))
        parts.append(V.tube(f"rackleg{sx}", [(sx * 0.13, 0.9, 0.8), (sx * 0.12, yr + 0.05, R + 0.02)], 0.007,
                            "veh_chrome", 6, 0))
    for k in range(5):
        y = 0.72 + k * 0.065
        parts.append(V.tube(f"rackbar{k}", [(-0.13, y, 0.802), (0.13, y, 0.802)], 0.006, "veh_chrome", 6, 0))
    # front: telescopic fork, handlebar cover with round headlight, front mudguard
    parts.append(V.loft("hcover", [(-0.6, 0, 1.0, 0.1, 0.07, 2.2), (-0.56, 0, 1.0, 0.16, 0.08, 2.6),
                                   (-0.48, 0, 1.02, 0.15, 0.07, 2.6), (-0.42, 0, 1.03, 0.09, 0.05, 2.2)], P, 22))
    parts += lamp("headlight", (0, -0.62, 1.0), 0.065, 0.04, "veh_light_head")
    parts.append(V.rbox("speedo", (0.12, 0.08, 0.02), (0, -0.48, 1.075), "veh_plastic_black", 0.008))
    for sx in (-1, 1):
        parts.append(V.tube(f"bar{sx}", [(sx * 0.12, -0.5, 1.03), (sx * 0.32, -0.46, 1.04)], 0.011, "veh_chrome", 8, 0))
        parts.append(V.cyl(f"grip{sx}", 0.017, 0.11, (sx * 0.35, -0.455, 1.04), "X", "veh_rubber", 12))
        parts.append(V.tube(f"mstalk{sx}", [(sx * 0.2, -0.48, 1.05), (sx * 0.25, -0.5, 1.22)], 0.006, "veh_chrome", 6, 0))
        parts.append(V.cyl(f"mirror{sx}", 0.05, 0.02, (sx * 0.255, -0.505, 1.25), "Y", "veh_chrome", 16))
        parts.append(V.cyl(f"mglass{sx}", 0.045, 0.004, (sx * 0.255, -0.517, 1.25), "Y", "veh_mirror", 16))
        parts.append(V.rbox(f"blinkF{sx}", (0.05, 0.04, 0.03), (sx * 0.14, -0.6, 0.96), "veh_light_amber", 0.01))
        parts.append(V.tube(f"fork{sx}", [(sx * 0.07, -0.5, 0.9), (sx * 0.07, yf - 0.02, R + 0.03)], 0.02, "veh_chrome", 10, 0))
        parts.append(V.tube(f"forkboot{sx}", [(sx * 0.07, -0.55, 0.65), (sx * 0.07, -0.585, 0.46)], 0.024,
                            "veh_rubber", 10, 0))
    parts.append(fender("fenderF", (0, yf, R), R + 0.03, 0.1, 20, 160, P))
    # engine: horizontal single + finned cylinder + crankcase covers, chain case, exhaust
    parts.append(V.rbox("crankcase", (0.22, 0.28, 0.2), (0, 0.04, 0.3), "veh_engine", 0.04, 3))
    parts.append(V.lathe("clutchcover", [(0.0, 0.0), (0.08, 0.0), (0.095, -0.02), (0.1, -0.05)], (0.12, 0.05, 0.3),
                         "X", "veh_alloy", 24))
    parts.append(V.lathe("magneto", [(0.0, 0.0), (0.07, 0.0), (0.085, 0.02), (0.09, 0.05)], (-0.12, 0.06, 0.3),
                         "X", "veh_alloy", 24))
    for k in range(6):
        parts.append(V.rbox(f"fin{k}", (0.14, 0.012, 0.13), (0, -0.12 - k * 0.022, 0.3), "veh_engine", 0.004, 1,
                            rot=(math.radians(-70), 0, 0)))
    parts.append(V.loft("chaincase", [(0.12, -0.11, 0.3, 0.025, 0.05, 2.6), (0.4, -0.11, R + 0.01, 0.025, 0.045, 2.6),
                                      (yr, -0.11, R, 0.025, 0.045, 2.6)], "veh_plastic_black", 14))
    parts.append(V.tube("exhpipe", [(0, -0.2, 0.25), (0.06, -0.2, 0.16), (0.12, 0.05, 0.16), (0.16, 0.3, 0.27)], 0.02,
                        "veh_chrome", 10, 0.06))
    parts.append(V.cyl("muffler", 0.048, 0.45, (0.16, 0.55, 0.29), "Y", "veh_chrome", 16, r2=0.04))
    parts.append(V.rbox("heatshield", (0.02, 0.25, 0.06), (0.21, 0.4, 0.3), "veh_chrome", 0.008))
    for sx in (-1, 1):
        parts.append(V.tube(f"swing{sx}", [(sx * 0.1, 0.12, 0.3), (sx * 0.1, yr, R)], 0.018, "veh_steel_dark", 8, 0))
        parts.append(V.tube(f"shock{sx}", [(sx * 0.12, yr - 0.02, R + 0.03), (sx * 0.12, yr - 0.12, 0.72)], 0.022,
                            "veh_chrome", 10, 0))
        parts.append(V.rbox(f"peg{sx}", (0.1, 0.03, 0.025), (sx * 0.17, 0.06, 0.29), "veh_rubber", 0.008))
        parts.append(V.decal(f"brand{sx}", "brand_soc", (sx * 0.142, 0.3, 0.6), (0.16, 0.05), "+X" if sx > 0 else "-X"))
    parts.append(fender("fenderR", (0, yr, R), R + 0.035, 0.11, 75, 200, P))
    parts += lamp("taillight", (0, 0.9, 0.7), 0.04, 0.03, "veh_light_tail", flip=True)
    parts.append(V.rbox("plateholder", (0.21, 0.015, 0.16), (0, 0.96, 0.55), "veh_steel_dark", 0.005))
    parts.append(plate("plate", "plate_moto_b", (0, 0.97, 0.55), (0.19, 0.14), "+Y"))
    parts.append(kickstand(-0.1, 0.1, 0.27))
    wheels = [wheel("wheel_front", (0, yf, R), R, 0.065, 0.216, "spoked", spokes=36, hub_w=0.1),
              wheel("wheel_rear", (0, yr, R), R, 0.072, 0.216, "spoked", spokes=36, hub_w=0.12)]
    cols = [V.box_col("col_plastic_seat", (0, 0.38, 0.81), (0.3, 0.75, 0.1)),
            V.box_col("col_metal_rack", (0, 0.86, 0.81), (0.28, 0.32, 0.03)),
            V.box_col("col_metal_body", (0, 0.35, 0.6), (0.3, 1.1, 0.4)),
            V.box_col("col_metal_front", (0, -0.47, 0.95), (0.42, 0.25, 0.9))]
    mk = [V.marker("SEAT_rider", (0, 0.3, 0.81)), V.marker("SEAT_pillion", (0, 0.6, 0.82)),
          V.marker("NAP_seat", (0, 0.42, 0.81))]
    return finish("underbone_step", parts, wheels, cols, mk, {
        "kind": "motorbike", "name_key": "VEH_UNDERBONE", "wheelbase": WB, "seat": [0.0, 0.81, -0.3],
        "seats": {"rider": [0.0, 0.81, -0.3], "pillion": [0.0, 0.82, -0.6]}, "rider_pose": "motorbike",
        "nap_spots": [[0.0, 0.81, -0.42]], "mass": 98.0, "paint": paint, "max_speed": 14.0}, preview, mud=0.6,
        wear_seed=2)


# ---------------------------------------------------------------------------
# 3. older manual standard (125 cc two-stroke look)  L 2.0  W 0.78  H 1.1  WB 1.3, 18" wheels, tank, cradle frame
# ---------------------------------------------------------------------------
def manual_classic(preview=True, paint="maroon"):
    new()
    P = f"veh_paint_{paint}"
    WB, R = 1.3, 0.305
    yf, yr = -WB / 2, WB / 2
    parts = []
    # cradle frame
    for sx in (-1, 1):
        parts.append(V.tube(f"cradle{sx}", [(0, -0.48, 0.95), (sx * 0.05, -0.42, 0.55), (sx * 0.08, -0.3, 0.2),
                                            (sx * 0.08, 0.2, 0.2), (sx * 0.08, 0.32, 0.45), (sx * 0.1, 0.9, 0.78)],
                            0.016, "veh_steel_dark", 8, 0.08))
        parts.append(V.tube(f"subframe{sx}", [(sx * 0.08, 0.25, 0.5), (sx * 0.1, 0.62, 0.62)], 0.012, "veh_steel_dark", 6, 0))
    parts.append(V.tube("backbone", [(0, -0.48, 0.97), (0, 0.15, 0.85), (0, 0.4, 0.75)], 0.022, "veh_steel_dark", 8, 0.1))
    # teardrop fuel tank with knee recesses + chrome cap
    parts.append(V.loft("tank", [(-0.48, 0, 0.92, 0.05, 0.05, 2.2), (-0.4, 0, 0.94, 0.13, 0.1, 2.4),
                                 (-0.22, 0, 0.95, 0.155, 0.12, 2.6), (-0.05, 0, 0.92, 0.14, 0.11, 2.6),
                                 (0.08, 0, 0.88, 0.09, 0.08, 2.4), (0.12, 0, 0.86, 0.05, 0.05, 2.2)], P, 28))
    parts.append(V.cyl("tankcap", 0.035, 0.02, (0, -0.25, 1.065), "Z", "veh_chrome", 16))
    for sx in (-1, 1):
        parts.append(V.decal(f"tankbadge{sx}", "brand_hac", (sx * 0.152, -0.22, 0.95), (0.14, 0.045), "+X" if sx > 0 else "-X"))
        parts.append(V.rbox(f"kneepad{sx}", (0.012, 0.12, 0.06), (sx * 0.14, -0.08, 0.9), "veh_rubber", 0.01))
        parts.append(V.rbox(f"sidepanel{sx}", (0.02, 0.22, 0.16), (sx * 0.12, 0.35, 0.66), P, 0.015))
    parts.append(V.loft("seat", [(0.08, 0, 0.86, 0.08, 0.03, 2.4), (0.15, 0, 0.87, 0.14, 0.05, 3.2),
                                 (0.7, 0, 0.88, 0.14, 0.05, 3.2), (0.86, 0, 0.87, 0.11, 0.04, 2.8)], "veh_vinyl_brown", 24))
    parts.append(V.tube("seatstrap", [(-0.14, 0.45, 0.9), (0, 0.45, 0.93), (0.14, 0.45, 0.9)], 0.008, "veh_vinyl_black", 6, 0.05))
    # engine: finned cylinder, crankcase, carb
    parts.append(V.rbox("crankcase", (0.2, 0.34, 0.22), (0, -0.02, 0.3), "veh_engine", 0.05, 3))
    parts.append(V.lathe("cover", [(0.0, 0.0), (0.1, 0.0), (0.11, -0.03), (0.11, -0.06)], (0.11, 0.02, 0.3), "X",
                         "veh_alloy", 24))
    for k in range(9):
        parts.append(V.rbox(f"fin{k}", (0.16, 0.16, 0.01), (0, -0.16, 0.42 + k * 0.024), "veh_engine", 0.02, 2,
                            rot=(math.radians(-12), 0, 0)))
    parts.append(V.cyl("barrel", 0.05, 0.24, (0, -0.15, 0.53), "Z", "veh_engine", 14))
    parts.append(V.cyl("carb", 0.03, 0.12, (-0.05, 0.05, 0.52), "Y", "veh_alloy", 12))
    # expansion-chamber exhaust (aged chrome / rust)
    parts.append(V.tube("exh", [(0, -0.22, 0.55), (0.08, -0.32, 0.42), (0.12, -0.3, 0.22), (0.14, 0.05, 0.2),
                                (0.17, 0.4, 0.3)], 0.025, "veh_rust", 10, 0.08))
    parts.append(V.cyl("silencer", 0.04, 0.5, (0.17, 0.62, 0.33), "Y", "veh_chrome", 14, r2=0.034))
    # front end: fork + gaiters, chrome headlight bucket, high bars, speedo
    for sx in (-1, 1):
        parts.append(V.tube(f"fork{sx}", [(sx * 0.08, -0.47, 1.05), (sx * 0.08, yf - 0.03, R + 0.03)], 0.02, "veh_chrome", 10, 0))
        parts.append(V.tube(f"gaiter{sx}", [(sx * 0.08, -0.55, 0.72), (sx * 0.08, -0.59, 0.5)], 0.027, "veh_rubber", 10, 0))
        parts.append(V.tube(f"bar{sx}", [(0, -0.45, 1.1), (sx * 0.2, -0.43, 1.12), (sx * 0.32, -0.36, 1.18),
                                         (sx * 0.37, -0.32, 1.18)], 0.011, "veh_chrome", 8, 0.06))
        parts.append(V.cyl(f"grip{sx}", 0.018, 0.12, (sx * 0.38, -0.31, 1.18), "X", "veh_rubber", 12))
        parts.append(V.tube(f"mstalk{sx}", [(sx * 0.25, -0.41, 1.14), (sx * 0.29, -0.43, 1.3)], 0.006, "veh_chrome", 6, 0))
        parts.append(V.cyl(f"mirror{sx}", 0.045, 0.02, (sx * 0.295, -0.435, 1.33), "Y", "veh_chrome", 16))
        parts.append(V.rbox(f"blink{sx}", (0.04, 0.05, 0.035), (sx * 0.13, -0.58, 0.97), "veh_light_amber", 0.012))
        parts.append(V.tube(f"shock{sx}", [(sx * 0.13, yr - 0.02, R + 0.03), (sx * 0.12, yr - 0.15, 0.78)], 0.022,
                            "veh_chrome", 10, 0))
        parts.append(V.tube(f"swing{sx}", [(sx * 0.1, 0.25, 0.3), (sx * 0.1, yr, R)], 0.017, "veh_steel_dark", 8, 0))
        parts.append(V.rbox(f"peg{sx}", (0.1, 0.03, 0.025), (sx * 0.18, 0.12, 0.3), "veh_rubber", 0.008))
    parts.append(V.lathe("lampbucket", [(0.0, 0.1), (0.07, 0.09), (0.085, 0.02), (0.085, -0.02)], (0, -0.58, 0.97),
                         "Y", "veh_chrome", 24))
    parts += lamp("headlight", (0, -0.6, 0.97), 0.08, 0.035, "veh_light_head")
    parts.append(V.cyl("speedo", 0.04, 0.05, (0, -0.5, 1.15), "Z", "veh_chrome", 16))
    parts.append(fender("fenderF", (0, yf, R), R + 0.035, 0.1, 30, 150, "veh_chrome"))
    parts.append(fender("fenderR", (0, yr, R), R + 0.04, 0.12, 70, 205, "veh_rust"))
    parts += lamp("taillight", (0, 0.95, 0.68), 0.04, 0.03, "veh_light_tail", flip=True)
    parts.append(V.rbox("plateholder", (0.21, 0.015, 0.16), (0, 0.98, 0.56), "veh_steel_dark", 0.005))
    parts.append(plate("plate", "plate_moto_c", (0, 0.99, 0.56), (0.19, 0.14), "+Y"))
    parts.append(V.decal("sticker", "sticker_b", (0.153, -0.33, 0.9), (0.08, 0.05), "+X"))
    parts.append(kickstand(-0.1, 0.15, 0.25))
    wheels = [wheel("wheel_front", (0, yf, R), R, 0.075, 0.229, "spoked", spokes=36, hub_w=0.13),
              wheel("wheel_rear", (0, yr, R), R, 0.085, 0.229, "spoked", spokes=36, hub_w=0.15)]
    cols = [V.box_col("col_plastic_seat", (0, 0.48, 0.93), (0.28, 0.8, 0.1)),
            V.box_col("col_metal_tank", (0, -0.2, 1.0), (0.3, 0.55, 0.2)),
            V.box_col("col_metal_body", (0, 0.1, 0.6), (0.34, 1.3, 0.6))]
    mk = [V.marker("SEAT_rider", (0, 0.3, 0.92)), V.marker("SEAT_pillion", (0, 0.7, 0.93)),
          V.marker("NAP_seat", (0, 0.5, 0.92))]
    return finish("manual_classic", parts, wheels, cols, mk, {
        "kind": "motorbike", "name_key": "VEH_MANUAL_BIKE", "wheelbase": WB, "seat": [0.0, 0.92, -0.3],
        "seats": {"rider": [0.0, 0.92, -0.3], "pillion": [0.0, 0.93, -0.7]}, "rider_pose": "motorbike",
        "nap_spots": [[0.0, 0.92, -0.5]], "mass": 105.0, "paint": paint, "max_speed": 15.0}, preview, mud=0.75,
        wear_seed=3)


# ---------------------------------------------------------------------------
# 4. city bicycle (26", step-through, basket + rack)  L 1.78  WB 1.08
# ---------------------------------------------------------------------------
def bicycle_city(preview=True, paint="teal"):
    new()
    P = f"veh_paint_{paint}"
    WB, R = 1.08, 0.33
    yf, yr = -WB / 2, WB / 2
    parts = []
    head_t, head_b = Vector((0, -0.4, 0.95)), Vector((0, -0.43, 0.8))
    bb = Vector((0, 0.05, 0.28))
    seat_t = Vector((0, 0.22, 0.88))
    parts.append(V.tube("downtube", [head_b, (0, -0.25, 0.45), bb], 0.02, P, 10, 0.15))
    parts.append(V.tube("lowtube", [head_t, (0, -0.3, 0.7), (0, -0.05, 0.38), (0, 0.13, 0.5)], 0.016, P, 10, 0.12))
    parts.append(V.tube("seattube", [bb, seat_t], 0.018, P, 10, 0))
    parts.append(V.tube("headtube", [head_t, head_b], 0.022, P, 10, 0))
    for sx in (-1, 1):
        parts.append(V.tube(f"chainstay{sx}", [bb + Vector((sx * 0.02, 0, 0)), (sx * 0.06, yr, R)], 0.01, P, 8, 0))
        parts.append(V.tube(f"seatstay{sx}", [seat_t - Vector((-sx * 0.015, 0.0, 0.08)), (sx * 0.06, yr, R)], 0.009, P, 8, 0))
        parts.append(V.tube(f"fork{sx}", [head_b + Vector((sx * 0.03, 0, 0)), (sx * 0.05, -0.47, 0.6),
                                          (sx * 0.05, yf, R)], 0.011, P, 8, 0.05))
        parts.append(V.tube(f"rackstay{sx}", [(sx * 0.07, yr, R + 0.02), (sx * 0.08, 0.6, 0.75)], 0.006, "veh_chrome", 6, 0))
        parts.append(V.tube(f"pedalarm{sx}", [bb + Vector((sx * 0.07, 0, 0)), bb + Vector((sx * 0.07, 0.15 * sx, -0.06 * sx))],
                            0.009, "veh_chrome", 6, 0))
        parts.append(V.rbox(f"pedal{sx}", (0.09, 0.05, 0.02), bb + Vector((sx * 0.12, 0.15 * sx, -0.06 * sx)),
                            "veh_plastic_black", 0.005))
        parts.append(V.cyl(f"grip{sx}", 0.016, 0.1, (sx * 0.29, -0.28, 1.06), "X", "veh_rubber", 10))
    # stem + swept-back handlebar, bell, saddle
    parts.append(V.tube("stem", [head_t, (0, -0.42, 1.05)], 0.012, "veh_chrome", 8, 0))
    parts.append(V.tube("handlebar", [(-0.34, -0.28, 1.06), (-0.22, -0.36, 1.06), (0, -0.42, 1.05), (0.22, -0.36, 1.06),
                                      (0.34, -0.28, 1.06)], 0.011, "veh_chrome", 8, 0.07))
    parts.append(V.lathe("bell", [(0.0, 0.015), (0.022, 0.012), (0.026, 0.0)], (0.18, -0.38, 1.08), "Z", "veh_chrome", 16))
    parts.append(V.tube("seatpost", [seat_t, (0, 0.24, 0.98)], 0.012, "veh_chrome", 8, 0))
    parts.append(V.loft("saddle", [(0.13, 0, 0.995, 0.03, 0.02, 2.4), (0.18, 0, 1.0, 0.06, 0.03, 2.6),
                                   (0.28, 0, 1.0, 0.12, 0.035, 3.0), (0.32, 0, 0.995, 0.11, 0.03, 2.6)], "veh_vinyl_brown", 18))
    for sx in (-1, 1):
        parts.append(V.tube(f"spring{sx}", [(sx * 0.06, 0.3, 0.97), (sx * 0.06, 0.3, 0.93)], 0.012, "veh_chrome", 6, 0))
    # chainring + guard, fenders, rack, basket, kickstand
    parts.append(V.lathe("chainring", [(0.0, -0.004), (0.1, -0.004), (0.1, 0.004), (0.0, 0.004)], bb + Vector((0.05, 0, 0)),
                         "X", "veh_alloy", 32))
    parts.append(V.loft("chainguard", [(-0.05, 0.08, 0.3, 0.01, 0.07, 2.4), (0.3, 0.08, R + 0.02, 0.01, 0.04, 2.4),
                                       (0.45, 0.08, R + 0.01, 0.01, 0.03, 2.4)], P, 10))
    parts.append(fender("fenderF", (0, yf, R), R + 0.03, 0.055, 20, 165, "veh_chrome"))
    parts.append(fender("fenderR", (0, yr, R), R + 0.03, 0.06, 60, 200, "veh_chrome"))
    for k in range(5):
        x = -0.07 + k * 0.035
        parts.append(V.tube(f"rack{k}", [(x, 0.32, 0.76), (x, 0.82, 0.76)], 0.005, "veh_chrome", 6, 0))
    bx0, by0, bz0 = -0.17, -0.72, 0.85
    for i in range(7):
        x = bx0 + i * 0.34 / 6
        parts.append(V.tube(f"bskx{i}", [(x, by0, bz0), (x, by0 + 0.26, bz0), (x, by0 + 0.26, bz0 + 0.22)], 0.003, "veh_chrome",
                            4, 0.01))
        parts.append(V.tube(f"bskf{i}", [(x, by0, bz0), (x, by0, bz0 + 0.22)], 0.003, "veh_chrome", 4, 0))
    for j in range(4):
        z = bz0 + j * 0.22 / 3
        parts.append(V.tube(f"bskr{j}", [(bx0, by0, z), (-bx0, by0, z), (-bx0, by0 + 0.26, z), (bx0, by0 + 0.26, z),
                                         (bx0, by0, z)], 0.003, "veh_chrome", 4, 0.01))
    parts.append(V.tube("bskmount", [(0, by0 + 0.26, bz0 + 0.1), (0, -0.43, 1.0)], 0.006, "veh_chrome", 6, 0))
    parts.append(V.rbox("rearreflector", (0.06, 0.01, 0.03), (0, 0.84, 0.72), "veh_light_tail", 0.004))
    parts.append(V.tube("kick", [(-0.05, 0.25, 0.3), (-0.1, 0.35, 0.01)], 0.008, "veh_steel_dark", 6, 0))
    wheels = [wheel("wheel_front", (0, yf, R), R, 0.042, 0.29, "spoked", spokes=36, hub_w=0.09),
              wheel("wheel_rear", (0, yr, R), R, 0.045, 0.29, "spoked", spokes=36, hub_w=0.12)]
    cols = [V.box_col("col_metal_rack", (0, 0.57, 0.775), (0.18, 0.5, 0.03)),
            V.box_col("col_metal_basket", (0, -0.59, 0.96), (0.34, 0.26, 0.24)),
            V.box_col("col_metal_frame", (0, 0.0, 0.55), (0.12, 1.4, 0.5))]
    mk = [V.marker("SEAT_rider", (0, 0.25, 1.02)), V.marker("NAP_basket", (0, -0.59, 0.88))]
    return finish("bicycle_city", parts, wheels, cols, mk, {
        "kind": "bicycle", "name_key": "VEH_BICYCLE", "wheelbase": WB, "seat": [0.0, 1.02, -0.25],
        "seats": {"rider": [0.0, 1.02, -0.25]}, "rider_pose": "bicycle", "nap_spots": [[0.0, 0.88, 0.59]],
        "mass": 18.0, "paint": paint, "max_speed": 4.5}, preview, mud=0.4, wear_seed=4)


# ---------------------------------------------------------------------------
# 5. cyclo / xích lô: passenger chair between two front wheels, rider pedals behind  L 2.3  W 0.98  H 1.25
# ---------------------------------------------------------------------------
def cyclo(preview=True, paint="green"):
    new()
    P = f"veh_paint_{paint}"
    R = 0.33
    yf, yr = -0.72, 0.78
    TR = 0.86
    parts = []
    # passenger tub: painted sheet-metal sides, seat, backrest, footboard
    for sx in (-1, 1):
        parts.append(V.extrude(f"side{sx}", [(-0.95, 0.42), (-0.62, 0.42), (-0.45, 0.62), (-0.3, 0.98), (-0.12, 1.02),
                                             (-0.1, 0.95), (-0.2, 0.62), (-0.3, 0.32), (-0.88, 0.3), (-0.98, 0.34)],
                               0.02, "YZ", sx * 0.36, P, 0.008))
        parts.append(V.tube(f"armrest{sx}", [(sx * 0.37, -0.62, 0.66), (sx * 0.37, -0.4, 0.66), (sx * 0.37, -0.2, 0.98)],
                            0.012, "veh_chrome", 8, 0.06))
        parts.append(V.tube(f"axlearm{sx}", [(sx * 0.3, -0.5, 0.4), (sx * (TR / 2 - 0.05), yf, R)], 0.02,
                            "veh_steel_dark", 8, 0))
        parts.append(fender(f"fenderF{sx}", (sx * TR / 2, yf, R), R + 0.04, 0.07, 10, 170, P))
    parts.append(V.rbox("seat", (0.7, 0.4, 0.1), (0, -0.48, 0.5), "veh_vinyl_red", 0.04, 3))
    parts.append(V.rbox("backrest", (0.68, 0.1, 0.42), (0, -0.25, 0.78), "veh_vinyl_red", 0.04, 3, rot=(math.radians(-14), 0, 0)))
    parts.append(V.rbox("backshell", (0.72, 0.04, 0.5), (0, -0.18, 0.78), P, 0.015, 2, rot=(math.radians(-14), 0, 0)))
    parts.append(V.rbox("floor", (0.72, 0.42, 0.03), (0, -0.78, 0.33), "veh_wood", 0.006))
    parts.append(V.rbox("footboard", (0.62, 0.22, 0.02), (0, -1.02, 0.2), "veh_steel_dark", 0.004,
                        rot=(math.radians(-12), 0, 0)))
    parts.append(V.tube("footbar", [(-0.3, -1.12, 0.22), (-0.3, -0.92, 0.34)], 0.01, "veh_steel_dark", 6, 0))
    parts.append(V.tube("footbar2", [(0.3, -1.12, 0.22), (0.3, -0.92, 0.34)], 0.01, "veh_steel_dark", 6, 0))
    # folded canopy hood (accordion of fabric hoops behind the backrest)
    for k in range(4):
        a0 = math.radians(-10 - k * 8)
        parts.append(V.loft(f"hood{k}", [(-0.22 + k * 0.04, 0, 1.0 - k * 0.02, 0.38, 0.06, 2.2),
                                         (-0.14 + k * 0.04, 0, 1.02 - k * 0.02, 0.4, 0.08, 2.2),
                                         (-0.08 + k * 0.04, 0, 1.0 - k * 0.02, 0.38, 0.05, 2.2)],
                            "veh_fabric_black", 18))
    # rider frame: spine from tub to rear wheel, seat tube, saddle, crank, handlebar on the tub back
    parts.append(V.tube("spine", [(0, -0.15, 0.45), (0, 0.15, 0.42), (0, 0.38, 0.32), (0, yr, R)], 0.025, "veh_steel_dark", 10, 0.1))
    parts.append(V.tube("toptube", [(0, -0.15, 0.95), (0, 0.3, 0.92), (0, 0.42, 0.98)], 0.02, "veh_steel_dark", 10, 0.1))
    parts.append(V.tube("seattube", [(0, 0.38, 0.32), (0, 0.48, 1.0)], 0.02, "veh_steel_dark", 10, 0))
    parts.append(V.tube("seatpost", [(0, 0.48, 1.0), (0, 0.5, 1.07)], 0.013, "veh_chrome", 8, 0))
    parts.append(V.loft("saddle", [(0.4, 0, 1.075, 0.03, 0.02, 2.4), (0.46, 0, 1.08, 0.07, 0.03, 2.6),
                                   (0.56, 0, 1.08, 0.12, 0.035, 3.0), (0.6, 0, 1.075, 0.11, 0.03, 2.6)], "veh_vinyl_black", 18))
    for sx in (-1, 1):
        parts.append(V.tube(f"stay{sx}", [(0, 0.48, 0.95), (sx * 0.06, yr, R)], 0.011, "veh_steel_dark", 8, 0))
        parts.append(V.tube(f"cstay{sx}", [(0, 0.38, 0.32), (sx * 0.06, yr, R)], 0.011, "veh_steel_dark", 8, 0))
        parts.append(V.tube(f"crank{sx}", [(sx * 0.07, 0.38, 0.32), (sx * 0.07, 0.38 + 0.16 * sx, 0.32 - 0.05 * sx)],
                            0.009, "veh_chrome", 6, 0))
        parts.append(V.rbox(f"pedal{sx}", (0.09, 0.05, 0.02), (sx * 0.12, 0.38 + 0.16 * sx, 0.32 - 0.05 * sx),
                            "veh_plastic_black", 0.005))
        parts.append(V.cyl(f"grip{sx}", 0.018, 0.12, (sx * 0.3, -0.05, 1.08), "X", "veh_rubber", 10))
    parts.append(V.tube("handlebar", [(-0.36, -0.05, 1.08), (-0.2, -0.12, 1.05), (0.2, -0.12, 1.05), (0.36, -0.05, 1.08)],
                        0.012, "veh_chrome", 8, 0.05))
    parts.append(V.lathe("chainring", [(0.0, -0.004), (0.1, -0.004), (0.1, 0.004), (0.0, 0.004)], (0.05, 0.38, 0.32),
                         "X", "veh_alloy", 28))
    parts.append(fender("fenderR", (0, yr, R), R + 0.03, 0.06, 60, 200, P))
    parts.append(V.rbox("lantern", (0.06, 0.06, 0.1), (0.4, -0.9, 0.55), "veh_light_amber", 0.01))
    parts.append(plate("plate", "plate_moto_d", (0, 0.86, 0.45), (0.19, 0.14), "+Y"))
    parts.append(V.decal("sticker", "sticker_a", (0.372, -0.7, 0.5), (0.13, 0.08), "+X"))
    wheels = [wheel("wheel_front_L", (-TR / 2, yf, R), R, 0.045, 0.29, "spoked", spokes=36, hub_w=0.1, mirror=True),
              wheel("wheel_front_R", (TR / 2, yf, R), R, 0.045, 0.29, "spoked", spokes=36, hub_w=0.1),
              wheel("wheel_rear", (0, yr, R), R, 0.045, 0.29, "spoked", spokes=36, hub_w=0.12)]
    cols = [V.box_col("col_plastic_seat", (0, -0.48, 0.56), (0.7, 0.42, 0.14)),
            V.box_col("col_metal_side_L", (-0.36, -0.55, 0.7), (0.04, 0.8, 0.45)),
            V.box_col("col_metal_side_R", (0.36, -0.55, 0.7), (0.04, 0.8, 0.45)),
            V.box_col("col_fabric_hood", (0, -0.1, 1.1), (0.8, 0.25, 0.2)),
            V.box_col("col_metal_frame", (0, 0.35, 0.65), (0.15, 0.9, 0.5))]
    mk = [V.marker("SEAT_passenger", (0, -0.48, 0.56)), V.marker("SEAT_rider", (0, 0.52, 1.1)),
          V.marker("NAP_seat", (0, -0.5, 0.56))]
    return finish("cyclo", parts, wheels, cols, mk, {
        "kind": "cyclo", "name_key": "VEH_CYCLO", "wheelbase": yr - yf, "track": TR, "seat": [0.0, 1.1, -0.52],
        "seats": {"rider": [0.0, 1.1, -0.52], "passenger": [0.0, 0.56, 0.48]}, "rider_pose": "bicycle",
        "nap_spots": [[0.0, 0.56, 0.5]], "mass": 65.0, "paint": paint, "max_speed": 3.5}, preview, mud=0.45,
        wear_seed=5)


# ---------------------------------------------------------------------------
# 6. cargo tricycle (xe ba gác, pedal): bicycle front, wooden bed over two rear wheels
# ---------------------------------------------------------------------------
def cargo_trike(preview=True, paint="sky"):
    new()
    P = f"veh_paint_{paint}"
    R = 0.31
    yf, yr = -0.8, 0.62
    TR = 1.0
    parts = []
    # front bicycle half
    parts.append(V.tube("downtube", [(0, -0.62, 0.85), (0, -0.4, 0.4), (0, -0.25, 0.28)], 0.022, P, 10, 0.1))
    parts.append(V.tube("toptube", [(0, -0.62, 0.95), (0, -0.3, 0.88), (0, -0.2, 0.9)], 0.02, P, 10, 0.05))
    parts.append(V.tube("seattube", [(0, -0.25, 0.28), (0, -0.18, 0.95)], 0.02, P, 10, 0))
    parts.append(V.tube("headtube", [(0, -0.62, 0.98), (0, -0.66, 0.8)], 0.024, P, 10, 0))
    for sx in (-1, 1):
        parts.append(V.tube(f"fork{sx}", [(sx * 0.03, -0.66, 0.8), (sx * 0.05, -0.74, 0.6), (sx * 0.05, yf, R)], 0.012, P, 8, 0.05))
        parts.append(V.cyl(f"grip{sx}", 0.017, 0.1, (sx * 0.3, -0.52, 1.08), "X", "veh_rubber", 10))
        parts.append(V.tube(f"crank{sx}", [(sx * 0.07, -0.25, 0.28), (sx * 0.07, -0.25 + 0.16 * sx, 0.28 - 0.05 * sx)],
                            0.009, "veh_chrome", 6, 0))
        parts.append(V.rbox(f"pedal{sx}", (0.09, 0.05, 0.02), (sx * 0.12, -0.25 + 0.16 * sx, 0.28 - 0.05 * sx),
                            "veh_plastic_black", 0.005))
        parts.append(V.tube(f"bedarm{sx}", [(0, -0.2, 0.42), (sx * 0.3, 0.0, 0.5)], 0.02, "veh_steel_dark", 8, 0))
    parts.append(V.tube("handlebar", [(-0.34, -0.5, 1.08), (-0.2, -0.58, 1.07), (0, -0.62, 1.06), (0.2, -0.58, 1.07),
                                      (0.34, -0.5, 1.08)], 0.012, "veh_chrome", 8, 0.06))
    parts.append(V.tube("stem", [(0, -0.62, 0.98), (0, -0.62, 1.06)], 0.013, "veh_chrome", 8, 0))
    parts.append(V.tube("seatpost", [(0, -0.18, 0.95), (0, -0.17, 1.02)], 0.013, "veh_chrome", 8, 0))
    parts.append(V.loft("saddle", [(-0.26, 0, 1.025, 0.03, 0.02, 2.4), (-0.2, 0, 1.03, 0.07, 0.03, 2.6),
                                   (-0.1, 0, 1.03, 0.12, 0.035, 3.0), (-0.07, 0, 1.025, 0.11, 0.03, 2.6)], "veh_vinyl_black", 18))
    parts.append(fender("fenderF", (0, yf, R), R + 0.03, 0.06, 20, 160, P))
    # chassis + wooden bed with low side boards
    parts.append(V.tube("axle", [(-TR / 2, yr, R), (TR / 2, yr, R)], 0.02, "veh_steel_dark", 8, 0))
    for sx in (-1, 1):
        parts.append(V.tube(f"rail{sx}", [(sx * 0.5, 0.0, 0.52), (sx * 0.5, 1.4, 0.52)], 0.02, "veh_rust", 8, 0))
        parts.append(V.tube(f"spring{sx}", [(sx * TR / 2 - sx * 0.08, yr - 0.25, R + 0.02), (sx * 0.48, yr - 0.2, 0.5)],
                            0.02, "veh_steel_dark", 8, 0))
        parts.append(V.rbox(f"sideboard{sx}", (0.025, 1.44, 0.16), (sx * 0.54, 0.7, 0.68), "veh_wood", 0.006))
        parts.append(fender(f"fenderR{sx}", (sx * TR / 2, yr, R), R + 0.02, 0.07, 40, 140, "veh_rust"))
    parts.append(V.rbox("bed", (1.1, 1.45, 0.04), (0, 0.7, 0.57), "veh_wood", 0.006))
    parts.append(V.rbox("frontboard", (1.1, 0.025, 0.24), (0, -0.02, 0.71), "veh_wood", 0.006))
    parts.append(V.rbox("tailboard", (1.1, 0.025, 0.14), (0, 1.42, 0.66), "veh_wood", 0.006))
    # load: two rice sacks + rope
    for k, (x, y, rz) in enumerate([(-0.2, 0.45, 0.2), (0.22, 0.55, -0.3), (0.0, 1.05, 0.1)]):
        s = V.sphere(f"sack{k}", 0.2, (x, y, 0.72), "veh_fabric_sack", (1.0, 1.5, 0.55), 14, 9)
        s.rotation_euler = (0, 0, rz)
        C.apply_transforms(s)
        parts.append(s)
    parts.append(V.tube("rope", [(-0.5, 0.3, 0.6), (-0.1, 0.5, 0.86), (0.3, 0.7, 0.86), (0.5, 0.9, 0.6)], 0.006,
                        "veh_vinyl_brown", 5, 0.1))
    parts.append(plate("plate", "plate_moto_d", (0, 1.44, 0.45), (0.19, 0.14), "+Y"))
    parts.append(V.rbox("reflector", (0.06, 0.01, 0.03), (0.4, 1.44, 0.6), "veh_light_tail", 0.004))
    wheels = [wheel("wheel_front", (0, yf, R), R, 0.045, 0.27, "spoked", spokes=36, hub_w=0.1),
              wheel("wheel_rear_L", (-TR / 2, yr, R), R, 0.055, 0.27, "spoked", spokes=36, hub_w=0.1, mirror=True),
              wheel("wheel_rear_R", (TR / 2, yr, R), R, 0.055, 0.27, "spoked", spokes=36, hub_w=0.1)]
    cols = [V.box_col("col_wood_bed", (0, 0.7, 0.59), (1.1, 1.45, 0.06)),
            V.box_col("col_wood_side_L", (-0.54, 0.7, 0.76), (0.03, 1.45, 0.18)),
            V.box_col("col_wood_side_R", (0.54, 0.7, 0.76), (0.03, 1.45, 0.18)),
            V.box_col("col_fabric_sacks", (0, 0.75, 0.75), (0.8, 1.0, 0.3)),
            V.box_col("col_metal_frame", (0, -0.45, 0.6), (0.14, 0.7, 0.5))]
    mk = [V.marker("SEAT_rider", (0, -0.15, 1.06)), V.marker("NAP_sacks", (0.0, 0.75, 0.9))]
    return finish("cargo_trike", parts, wheels, cols, mk, {
        "kind": "tricycle", "name_key": "VEH_CARGO_TRIKE", "wheelbase": yr - yf, "track": TR,
        "seat": [0.0, 1.06, 0.15], "seats": {"rider": [0.0, 1.06, 0.15]}, "rider_pose": "bicycle",
        "nap_spots": [[0.0, 0.9, -0.75]], "mass": 70.0, "paint": paint, "max_speed": 3.0}, preview, mud=0.7,
        wear_seed=6)



# ---------------------------------------------------------------------------
# car helpers
# ---------------------------------------------------------------------------
def arch_cut(body, centers, r, width=0.5):
    """Boolean-cut wheel arches into a lofted body."""
    for i, c in enumerate(centers):
        cutter = V.cyl(f"_cut{i}", r, width, c, "X", None, 32)
        m = body.modifiers.new(f"arch{i}", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = cutter
        C.apply_modifiers(body)
        bpy.data.objects.remove(cutter, do_unlink=True)
        bpy.context.view_layer.update()
    C.uv_cube_project(body, 1.0)
    C.shade_smooth(body, 40)


def arch_liner(name, c, r, width):
    return V.lathe(name, [(r, -width / 2), (r, width / 2)], c, "X", "veh_plastic_black", 28, 40)


def steering_wheel(c, tilt=-0.45):
    w = V.lathe("steer", [(0.17, -0.012), (0.19, 0.0), (0.17, 0.012), (0.15, 0.0), (0.17, -0.012)], (0, 0, 0), "Y",
                "veh_plastic_black", 24, 60)
    hub = V.cyl("steerhub", 0.05, 0.05, (0, 0, 0), "Y", "veh_plastic_black", 12)
    ob = C.join([w, hub], "steerwheel")
    ob.rotation_euler = (tilt, 0, 0)
    ob.location = c
    C.apply_transforms(ob, loc=True)
    return ob


# ---------------------------------------------------------------------------
# 7. small taxi hatchback  L 3.6  W 1.6  H 1.52  WB 2.4  track 1.38
# ---------------------------------------------------------------------------
def taxi_hatch(preview=True, paint="white"):
    new()
    P = f"veh_paint_{paint}"
    WB, TR, R = 2.4, 1.38, 0.29
    yf, yr = -WB / 2, WB / 2
    parts = []
    body = V.loft("lower", [(-1.8, 0, 0.56, 0.66, 0.2, 3.0), (-1.76, 0, 0.6, 0.75, 0.28, 4.0),
                            (-1.6, 0, 0.62, 0.79, 0.33, 5.0), (-1.2, 0, 0.63, 0.8, 0.34, 6.0),
                            (-0.7, 0, 0.64, 0.8, 0.36, 6.0), (0.4, 0, 0.64, 0.8, 0.36, 6.0),
                            (1.3, 0, 0.65, 0.8, 0.36, 6.0), (1.62, 0, 0.67, 0.78, 0.34, 5.0),
                            (1.76, 0, 0.69, 0.74, 0.3, 4.0), (1.8, 0, 0.7, 0.66, 0.24, 3.0)], P, 40)
    arch_cut(body, [(0, yf, R), (0, yr, R)], R + 0.05, 2.0)
    parts.append(body)
    for sx in (-1, 1):
        for yy in (yf, yr):
            parts.append(arch_liner(f"liner{sx}{yy}", (sx * 0.64, yy, R), R + 0.045, 0.3))
    glass = V.loft("greenhouse", [(-0.86, 0, 1.0, 0.75, 0.02, 4.0), (-0.55, 0, 1.12, 0.73, 0.14, 4.0),
                                  (-0.2, 0, 1.23, 0.71, 0.25, 4.5), (0.8, 0, 1.24, 0.7, 0.26, 4.5),
                                  (1.35, 0, 1.2, 0.68, 0.22, 4.0), (1.62, 0, 1.08, 0.66, 0.09, 3.5),
                                  (1.68, 0, 1.0, 0.64, 0.02, 3.0)], "veh_glass", 32)
    parts.append(glass)
    parts.append(V.loft("roof", [(-0.22, 0, 1.475, 0.66, 0.02, 3.0), (-0.1, 0, 1.49, 0.69, 0.025, 4.0),
                                 (1.1, 0, 1.49, 0.68, 0.025, 4.0), (1.42, 0, 1.45, 0.64, 0.03, 3.5),
                                 (1.5, 0, 1.4, 0.6, 0.025, 3.0)], P, 24))
    for sx in (-1, 1):
        parts.append(V.tube(f"apillar{sx}", [(sx * 0.735, -0.86, 1.01), (sx * 0.69, -0.55, 1.2), (sx * 0.655, -0.2, 1.44),
                                             (sx * 0.64, -0.1, 1.48)], 0.03, P, 8, 0.12))
        parts.append(V.rbox(f"bpillar{sx}", (0.04, 0.09, 0.5), (sx * 0.7, 0.42, 1.23), "veh_plastic_black", 0.01))
        parts.append(V.extrude(f"cpillar{sx}", [(1.05, 1.0), (1.66, 1.0), (1.5, 1.42), (1.15, 1.47)], 0.04, "YZ",
                               sx * 0.685, P, 0.01))
        parts.append(V.rbox(f"rub{sx}", (0.025, 2.2, 0.05), (sx * 0.805, 0.15, 0.62), "veh_plastic_black", 0.01))
        parts.append(V.rbox(f"mirror{sx}", (0.16, 0.08, 0.1), (sx * 0.86, -0.62, 1.07), P, 0.03))
        parts.append(V.rbox(f"mglass{sx}", (0.13, 0.01, 0.075), (sx * 0.87, -0.585, 1.07), "veh_mirror", 0.004))
        for hy in (-0.15, 0.85):
            parts.append(V.rbox(f"handle{sx}{hy}", (0.02, 0.13, 0.03), (sx * 0.805, hy, 0.95), "veh_chrome", 0.008))
        parts.append(V.rbox(f"headlamp{sx}", (0.28, 0.06, 0.11), (sx * 0.5, -1.765, 0.8), "veh_light_head", 0.025,
                            rot=(math.radians(-8), 0, sx * 0.18)))
        parts.append(V.rbox(f"lampbezel{sx}", (0.3, 0.05, 0.13), (sx * 0.5, -1.75, 0.8), "veh_chrome", 0.02,
                            rot=(math.radians(-8), 0, sx * 0.18)))
        parts.append(V.rbox(f"taillamp{sx}", (0.12, 0.06, 0.25), (sx * 0.66, 1.76, 0.98), "veh_light_tail", 0.02))
        parts.append(V.rbox(f"fog{sx}", (0.12, 0.03, 0.05), (sx * 0.55, -1.83, 0.45), "veh_light_amber", 0.01))
        dec = V.decal(f"livery{sx}", "taxi_door", (sx * 0.8, 0.2, 0.84), (1.75, 0.36), "+X" if sx > 0 else "-X", offset=0.0)
        V.conform_decal_to(dec, body)
        parts.append(dec)
    # bumpers, grille, plates, wipers, roof sign
    parts.append(V.loft("bumperF", [(-1.86, 0, 0.47, 0.7, 0.1, 3.0), (-1.8, 0, 0.47, 0.8, 0.13, 4.0),
                                    (-1.68, 0, 0.47, 0.81, 0.13, 4.0)], "veh_plastic_black", 24))
    parts.append(V.loft("bumperR", [(1.66, 0, 0.5, 0.81, 0.13, 4.0), (1.8, 0, 0.5, 0.8, 0.13, 4.0),
                                    (1.86, 0, 0.5, 0.7, 0.1, 3.0)], "veh_plastic_black", 24))
    parts.append(V.rbox("grillebox", (0.6, 0.06, 0.13), (0, -1.79, 0.67), "veh_plastic_black", 0.02))
    for k in range(4):
        parts.append(V.rbox(f"slat{k}", (0.58, 0.012, 0.012), (0, -1.822, 0.62 + k * 0.03), "veh_chrome", 0.004))
    parts.append(V.decal("plateF", "plate_car_a", (0, -1.875, 0.45), (0.52, 0.11), "-Y"))
    parts.append(V.decal("plateR", "plate_car_b", (0, 1.875, 0.52), (0.52, 0.11), "+Y"))
    for sx in (-0.3, 0.25):
        parts.append(V.tube(f"wiper{sx}", [(sx, -0.86, 1.02), (sx + 0.45, -0.8, 1.05)], 0.008, "veh_plastic_black", 5, 0))
    parts.append(V.rbox("roofsign", (0.46, 0.16, 0.15), (0, 0.5, 1.58), "veh_plastic_grey", 0.03))
    parts.append(V.rbox("roofsignbase", (0.5, 0.2, 0.03), (0, 0.5, 1.5), "veh_plastic_black", 0.01))
    parts.append(V.decal("signF", "taxi_roof", (0, 0.419, 1.58), (0.42, 0.13), "-Y"))
    parts.append(V.decal("signR", "taxi_roof", (0, 0.581, 1.58), (0.42, 0.13), "+Y"))
    # interior (visible through the glass)
    parts.append(V.rbox("dash", (1.36, 0.4, 0.18), (0, -0.62, 0.98), "veh_plastic_black", 0.05))
    parts.append(steering_wheel((-0.36, -0.42, 1.08)))
    for sx in (-0.36, 0.36):
        parts.append(V.rbox(f"seatF{sx}", (0.48, 0.5, 0.14), (sx, 0.15, 0.62), "veh_vinyl_black", 0.05))
        parts.append(V.rbox(f"backF{sx}", (0.48, 0.12, 0.55), (sx, 0.42, 0.95), "veh_vinyl_black", 0.05,
                            rot=(math.radians(-12), 0, 0)))
    parts.append(V.rbox("seatR", (1.2, 0.48, 0.14), (0, 1.0, 0.64), "veh_vinyl_black", 0.05))
    parts.append(V.rbox("backR", (1.2, 0.12, 0.5), (0, 1.3, 0.95), "veh_vinyl_black", 0.05, rot=(math.radians(-10), 0, 0)))
    parts.append(V.rbox("floorpan", (1.4, 3.2, 0.04), (0, 0.0, 0.3), "veh_steel_dark", 0.01))
    wheels = [wheel(f"wheel_{n}", (sx * TR / 2, yy, R), R, 0.165, 0.178, "steel", mirror=sx < 0)
              for n, sx, yy in (("front_L", -1, yf), ("front_R", 1, yf), ("rear_L", -1, yr), ("rear_R", 1, yr))]
    cols = [V.box_col("col_metal_body", (0, 0.0, 0.625), (1.6, 3.6, 0.73)),
            V.box_col("col_metal_cabin", (0, 0.5, 1.24), (1.42, 2.2, 0.5)),
            V.box_col("col_plastic_sign", (0, 0.5, 1.59), (0.46, 0.16, 0.18))]
    mk = [V.marker("SEAT_driver", (-0.36, 0.15, 0.95)), V.marker("SEAT_front", (0.36, 0.15, 0.95)),
          V.marker("SEAT_rear", (0.0, 1.0, 0.95)), V.marker("NAP_roof", (0.25, 1.05, 1.49)),
          V.marker("NAP_hood", (0.0, -1.25, 0.99))]
    return finish("taxi_hatch", parts, wheels, cols, mk, {
        "kind": "car", "name_key": "VEH_TAXI", "wheelbase": WB, "track": TR, "seat": [-0.36, 0.95, -0.15],
        "seats": {"driver": [-0.36, 0.95, -0.15], "front": [0.36, 0.95, -0.15], "rear": [0.0, 0.95, -1.0]},
        "rider_pose": "car", "nap_spots": [[0.25, 1.49, -1.05], [0.0, 0.99, 1.25]], "mass": 950.0, "paint": paint,
        "max_speed": 11.0, "climb_points": []}, preview, mud=0.35, view={"distance": 7.5}, wear_seed=7)


# ---------------------------------------------------------------------------
# 8. delivery panel van  L 4.4  W 1.7  H 1.98  WB 2.6  track 1.45
# ---------------------------------------------------------------------------
def delivery_van(preview=True, paint="cream"):
    new()
    P = f"veh_paint_{paint}"
    WB, TR, R = 2.6, 1.45, 0.32
    yf, yr = -WB / 2, WB / 2
    parts = []
    body = V.loft("lower", [(-2.2, 0, 0.62, 0.7, 0.22, 3.0), (-2.15, 0, 0.66, 0.8, 0.3, 4.5),
                            (-1.9, 0, 0.68, 0.85, 0.36, 6.0), (1.0, 0, 0.68, 0.85, 0.38, 8.0),
                            (2.15, 0, 0.68, 0.85, 0.38, 8.0), (2.2, 0, 0.68, 0.8, 0.36, 6.0)], P, 40)
    arch_cut(body, [(0, yf, R), (0, yr, R)], R + 0.05, 2.0)
    parts.append(body)
    box = V.loft("cargobox", [(-0.98, 0, 1.33, 0.845, 0.63, 10.0), (-0.95, 0, 1.33, 0.855, 0.65, 12.0),
                              (2.18, 0, 1.33, 0.855, 0.65, 12.0), (2.21, 0, 1.33, 0.83, 0.63, 10.0)], P, 48)
    arch_cut(box, [(0, yr, R)], R + 0.05, 2.0)
    parts.append(box)
    parts.append(V.loft("cab", [(-1.95, 0, 1.06, 0.82, 0.04, 6.0), (-1.75, 0, 1.08, 0.83, 0.07, 6.0),
                                (-1.55, 0, 1.1, 0.83, 0.1, 6.0)], P, 32))
    parts.append(V.loft("windshield", [(-1.56, 0, 1.18, 0.8, 0.03, 6.0), (-1.3, 0, 1.45, 0.79, 0.3, 6.0),
                                       (-1.0, 0, 1.5, 0.79, 0.43, 7.0)], "veh_glass", 32))
    parts.append(V.loft("cabroof", [(-1.25, 0, 1.92, 0.78, 0.03, 6.0), (-0.96, 0, 1.96, 0.82, 0.03, 8.0)], P, 24))
    for sx in (-1, 1):
        for yy in (yf, yr):
            parts.append(arch_liner(f"liner{sx}{yy}", (sx * 0.7, yy, R), R + 0.045, 0.3))
        parts.append(V.rbox(f"sidewin{sx}", (0.012, 0.5, 0.42), (sx * 0.852, -1.2, 1.42), "veh_glass", 0.01))
        parts.append(V.tube(f"apillar{sx}", [(sx * 0.785, -1.56, 1.19), (sx * 0.775, -1.3, 1.6), (sx * 0.78, -1.0, 1.9)],
                            0.035, P, 8, 0.1))
        parts.append(V.rbox(f"mirror{sx}", (0.08, 0.06, 0.2), (sx * 0.95, -1.45, 1.38), "veh_plastic_black", 0.02))
        parts.append(V.tube(f"mirrorarm{sx}", [(sx * 0.85, -1.45, 1.3), (sx * 0.93, -1.45, 1.32)], 0.01, "veh_plastic_black", 6, 0))
        parts.append(V.rbox(f"handle{sx}", (0.02, 0.14, 0.03), (sx * 0.855, -0.95, 1.08), "veh_plastic_black", 0.008))
        parts.append(V.rbox(f"seam{sx}", (0.006, 0.006, 0.95), (sx * 0.853, -0.88, 1.18), "veh_plastic_black", 0.0))
        parts.append(V.rbox(f"headlamp{sx}", (0.28, 0.06, 0.16), (sx * 0.56, -2.17, 0.88), "veh_light_head", 0.03))
        parts.append(V.rbox(f"blink{sx}", (0.1, 0.05, 0.07), (sx * 0.78, -2.13, 0.88), "veh_light_amber", 0.015))
        parts.append(V.rbox(f"taillamp{sx}", (0.1, 0.05, 0.35), (sx * 0.76, 2.2, 1.05), "veh_light_tail", 0.015))
        parts.append(V.rbox(f"rub{sx}", (0.025, 3.6, 0.07), (sx * 0.86, 0.3, 0.7), "veh_plastic_black", 0.01))
        dec = V.decal(f"livery{sx}", "van_side", (sx * 0.852, 0.6, 1.45), (2.6, 0.57), "+X" if sx > 0 else "-X", offset=0.003)
        parts.append(dec)
        parts.append(V.rbox(f"step{sx}", (0.22, 0.26, 0.04), (sx * 0.78, -0.8, 0.32), "veh_steel_dark", 0.01))
    parts.append(V.rbox("rearseam", (0.006, 0.006, 1.3), (0, 2.205, 1.3), "veh_plastic_black", 0.0))
    for sx in (-0.08, 0.08):
        parts.append(V.rbox(f"rearhandle{sx}", (0.03, 0.03, 0.14), (sx, 2.215, 1.15), "veh_chrome", 0.008))
    parts.append(V.loft("bumperF", [(-2.27, 0, 0.5, 0.78, 0.1, 3.0), (-2.2, 0, 0.5, 0.86, 0.13, 4.0),
                                    (-2.05, 0, 0.5, 0.86, 0.13, 4.0)], "veh_plastic_black", 24))
    parts.append(V.rbox("bumperR", (1.7, 0.12, 0.16), (0, 2.25, 0.48), "veh_steel_dark", 0.03))
    parts.append(V.rbox("grillebox", (0.8, 0.06, 0.2), (0, -2.19, 0.74), "veh_plastic_black", 0.02))
    for k in range(5):
        parts.append(V.rbox(f"slat{k}", (0.78, 0.012, 0.014), (0, -2.222, 0.66 + k * 0.04), "veh_steel_dark", 0.004))
    parts.append(V.decal("plateF", "plate_car_b", (0, -2.275, 0.5), (0.52, 0.11), "-Y"))
    parts.append(V.decal("plateR", "plate_car_a", (0, 2.315, 0.58), (0.52, 0.11), "+Y"))
    parts.append(V.decal("sticker", "sticker_b", (0.4, 2.203, 1.65), (0.2, 0.12), "+Y"))
    parts.append(V.tube("wiper", [(-0.4, -1.55, 1.2), (0.1, -1.45, 1.35)], 0.008, "veh_plastic_black", 5, 0))
    parts.append(V.rbox("dash", (1.5, 0.35, 0.2), (0, -1.38, 1.12), "veh_plastic_black", 0.05))
    parts.append(steering_wheel((-0.4, -1.15, 1.25), -0.9))
    for sx in (-0.4, 0.4):
        parts.append(V.rbox(f"seat{sx}", (0.5, 0.48, 0.14), (sx, -0.85, 0.72), "veh_vinyl_black", 0.05))
        parts.append(V.rbox(f"back{sx}", (0.5, 0.12, 0.6), (sx, -0.6, 1.05), "veh_vinyl_black", 0.05))
    parts.append(V.rbox("bulkhead", (1.6, 0.04, 1.0), (0, -0.5, 1.3), "veh_steel_dark", 0.01))
    wheels = [wheel(f"wheel_{n}", (sx * TR / 2, yy, R), R, 0.185, 0.19, "steel", mirror=sx < 0)
              for n, sx, yy in (("front_L", -1, yf), ("front_R", 1, yf), ("rear_L", -1, yr), ("rear_R", 1, yr))]
    cols = [V.box_col("col_metal_body", (0, 0.0, 0.68), (1.7, 4.4, 0.76)),
            V.box_col("col_metal_cargo", (0, 0.62, 1.5), (1.7, 3.16, 0.96)),
            V.box_col("col_metal_cab", (0, -1.27, 1.45), (1.62, 0.6, 1.0))]
    mk = [V.marker("SEAT_driver", (-0.4, -0.85, 1.05)), V.marker("SEAT_front", (0.4, -0.85, 1.05)),
          V.marker("NAP_roof", (0.0, 1.0, 1.98)), V.marker("NAP_bumper", (0.4, 2.25, 0.56))]
    return finish("delivery_van", parts, wheels, cols, mk, {
        "kind": "van", "name_key": "VEH_VAN", "wheelbase": WB, "track": TR, "seat": [-0.4, 1.05, 0.85],
        "seats": {"driver": [-0.4, 1.05, 0.85], "front": [0.4, 1.05, 0.85]}, "rider_pose": "car",
        "nap_spots": [[0.0, 1.98, -1.0], [0.4, 0.56, -2.25]], "mass": 1450.0, "paint": paint,
        "max_speed": 10.0}, preview, mud=0.45, view={"distance": 9.0}, wear_seed=8)


# ---------------------------------------------------------------------------
# 9/10. helmets (knockable props): half-shell "nón bảo hiểm nửa đầu" and open-face 3/4
# ---------------------------------------------------------------------------
def helmet(kind, preview=True, paint="yellow"):
    new()
    P = f"veh_paint_{paint}"
    parts = []
    if kind == "helmet_half":
        prof = [(0.0, 0.165), (0.06, 0.162), (0.1, 0.148), (0.125, 0.124), (0.14, 0.09), (0.146, 0.05), (0.146, 0.012)]
    else:
        prof = [(0.0, 0.2), (0.06, 0.197), (0.1, 0.183), (0.13, 0.155), (0.147, 0.115), (0.152, 0.07), (0.15, 0.02),
                (0.145, 0.0)]
    shell = V.lathe("helmet_shell", [(r, z) for r, z in prof], (0, 0, 0), "Z", P, 32, 50)
    for v in shell.data.vertices:
        v.co.x *= 0.9
        v.co.y *= 1.08
    if kind == "helmet_open":
        cutter = V.rbox("_cut", (0.36, 0.2, 0.14), (0, -0.16, 0.05), None, 0.03)
        m = shell.modifiers.new("cut", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = cutter
        C.apply_modifiers(shell)
        bpy.data.objects.remove(cutter, do_unlink=True)
        bpy.context.view_layer.update()
        sm = shell.modifiers.new("t", "SOLIDIFY")
        sm.thickness = 0.008
        C.apply_modifiers(shell)
    else:
        sm = shell.modifiers.new("t", "SOLIDIFY")
        sm.thickness = 0.006
        C.apply_modifiers(shell)
    C.uv_cube_project(shell, 1.0)
    parts.append(shell)
    rim_z = 0.012 if kind == "helmet_half" else 0.0
    rim = V.lathe("helmet_rim", [(0.147, rim_z - 0.004), (0.152, rim_z + 0.004), (0.14, rim_z + 0.01),
                                 (0.135, rim_z)], (0, 0, 0), "Z", "veh_fabric_black", 32, 50)
    for v in rim.data.vertices:
        v.co.x *= 0.9
        v.co.y *= 1.08
    parts.append(rim)
    parts.append(V.lathe("helmet_liner", [(0.0, 0.15), (0.11, 0.12), (0.135, 0.05), (0.135, 0.01)], (0, 0, 0), "Z",
                         "veh_fabric_black", 24, 50))
    if kind == "helmet_half":
        peak = V.lathe("helmet_peak", [(0.15, 0.03), (0.2, 0.012), (0.205, 0.008)], (0, 0, 0), "Z",
                       "veh_plastic_black", 40, 50)
        bm = bmesh.new()
        bm.from_mesh(peak.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > -0.075], context="VERTS")
        bm.to_mesh(peak.data)
        bm.free()
        for v in peak.data.vertices:
            v.co.x *= 0.9
            v.co.y *= 1.08
        sm = peak.modifiers.new("t", "SOLIDIFY")
        sm.thickness = 0.003
        C.apply_modifiers(peak)
        parts.append(peak)
        parts.append(V.decal("helmet_sticker", "sticker_a", (0, 0.177, 0.1), (0.07, 0.045), "+Y", offset=0.0))
        V.conform_decal_to(parts[-1], shell)
    else:
        visor = V.lathe("helmet_visor", [(0.168, 0.155), (0.172, 0.02)], (0, 0, 0), "Z", "veh_glass", 32, 50)
        bm = bmesh.new()
        bm.from_mesh(visor.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > -0.04], context="VERTS")
        bm.to_mesh(visor.data)
        bm.free()
        for v in visor.data.vertices:
            v.co.x *= 0.92
            v.co.y *= 1.08
        parts.append(visor)
        for sx in (-1, 1):
            parts.append(V.cyl(f"pivot{sx}", 0.016, 0.01, (sx * 0.142, -0.02, 0.08), "X", "veh_plastic_black", 12))
    for sx in (-1, 1):
        parts.append(V.tube(f"strap{sx}", [(sx * 0.128, 0.0, 0.02), (sx * 0.1, -0.02, -0.0), (sx * 0.05, -0.06, 0.004)],
                            0.004, "veh_fabric_black", 4, 0.02))
    parts.append(V.rbox("buckle", (0.035, 0.02, 0.008), (0.03, -0.065, 0.006), "veh_plastic_black", 0.003))
    # resting on its rim: lift so nothing is below z = 0
    zmin = min((o.matrix_world @ v.co).z for o in parts for v in o.data.vertices)
    for o in parts:
        o.location.z -= zmin
    C.apply_transforms(parts[0], loc=True)
    name = kind
    body = V.finish_body(parts, f"{name}_mesh")
    V.bake_wear([body], mud=0.05, mud_height=0.05, seed=9)
    hull = body.copy()
    hull.data = body.data.copy()
    bpy.context.scene.collection.objects.link(hull)
    hull.name = "col_plastic_helmet-convcolonly"
    bm = bmesh.new()
    bm.from_mesh(hull.data)
    ch = bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=[g for g in ch["geom_interior"] + ch["geom_unused"] if isinstance(g, bmesh.types.BMVert)],
                     context="VERTS")
    d = bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(12), verts=bm.verts, edges=bm.edges)
    bm.to_mesh(hull.data)
    bm.free()
    hull.data.materials.clear()
    hull.hide_render = True
    path = C.asset_path(f"{OUT}/{name}.glb")
    G.export_glb(path, [body, hull])
    G.glb_import(path, "vehicles")
    st = G.glb_stats(path)
    h = max(v.co.z for v in body.data.vertices)
    entry = {"id": name, "file": f"res://assets/models/vehicles/{name}.glb", "kind": "helmet",
             "name_key": "VEH_HELMET_HALF" if kind == "helmet_half" else "VEH_HELMET_OPEN",
             "width": 0.29, "depth": 0.34, "height": round(h, 3), "footprint": [0.29, 0.34], "floors": 0,
             "style": "vehicle", "climb_points": [], "nap_spots": [], "entrances": [], "wheels": [],
             "dynamic": True, "mass": 0.45 if kind == "helmet_half" else 0.9, "surface": "plastic",
             "tris": st["tris"], "materials": st["materials"], "paint": paint}
    G.write_catalog(CATALOG, [entry])
    print(f"BUILT {name}: tris={st['tris']}")
    if preview:
        C.preview_render(C.qa_path(f"vehicles-nature/veh_{name}.png"), target=(0, 0, 0.09), distance=0.75, yaw_deg=40,
                         pitch_deg=20, res=(480, 360), samples=24, lens=50)
    return entry


BUILDERS = {"scooter_auto": scooter_auto, "underbone_step": underbone_step, "manual_classic": manual_classic,
            "bicycle_city": bicycle_city, "cyclo": cyclo, "cargo_trike": cargo_trike, "taxi_hatch": taxi_hatch,
            "delivery_van": delivery_van, "helmet_half": lambda pv: helmet("helmet_half", pv, "yellow"),
            "helmet_open": lambda pv: helmet("helmet_open", pv, "white")}

if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--nopreview" not in argv
    ids = [a for a in argv if not a.startswith("--")] or list(BUILDERS)
    for vid in ids:
        BUILDERS[vid](preview)
