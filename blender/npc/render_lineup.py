"""Gallery render: import every exported NPC GLB into one scene, pose each on a chosen clip
frame, add a cat-sized reference box and render with Cycles.
Usage: tools/blender_run.sh blender/npc/render_lineup.py -- [humans|animals|all] [samples] [WxH]"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import common as C  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
WHICH = argv[0] if argv else "humans"
SAMPLES = int(argv[1]) if len(argv) > 1 else 48
RES = tuple(int(v) for v in argv[2].split("x")) if len(argv) > 2 else (1600, 800)

HUMANS = [("ped_office", "phone", 20), ("ped_student", "idle", 30), ("co_hoa", "sell", 30), ("ba_tu", "idle", 40),
          ("bin", "talk", 20), ("chu_sau", "talk", 50), ("ped_elder_man", "idle", 10),
          ("ped_helmet_woman", "look_around", 40), ("ped_shopper", "idle", 60), ("ped_xeom", "idle", 80)]
ANIMALS = [("dog", "idle", 20), ("crow", "idle", 10), ("pigeon", "peck", 14), ("sparrow", "idle", 30),
           ("mouse", "idle", 10), ("gecko", "idle", 10), ("koi", "swim", 10)]


def import_npc(cid, clip, frame, loc, rot_z=0.0):
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=C.asset_path(f"models/npc/{cid}.glb"))
    new = [o for o in bpy.data.objects if o not in before]
    new_acts = [a for a in bpy.data.actions if a not in acts_before]
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    roots = [o for o in new if o.parent is None]
    for r in roots:
        r.location = Vector(loc)
        r.rotation_mode = "XYZ"
        r.rotation_euler = (0, 0, math.radians(rot_z))
    if arm is not None:
        cands = [a for a in new_acts if a.name.split(".")[0].split("|")[-1] == clip or
                 a.name.split("|")[-1].split(".")[0] == clip]
        act = cands[0] if cands else None
        if act is None:
            print("no action", clip, "in", [a.name for a in new_acts][:12])
        if arm.animation_data:
            for tr in list(arm.animation_data.nla_tracks):
                arm.animation_data.nla_tracks.remove(tr)
        if act is not None:
            if arm.animation_data is None:
                arm.animation_data_create()
            arm.animation_data.action = act
            try:
                if act.slots:
                    arm.animation_data.action_slot = act.slots[0]
            except Exception:  # noqa
                pass
            act["_frame"] = frame
    return arm


def main():
    C.reset_scene()
    sc = bpy.context.scene
    items = []
    if WHICH in ("humans", "all"):
        n = len(HUMANS)
        for i, (cid, clip, fr) in enumerate(HUMANS):
            items.append((cid, clip, fr, ((i - (n - 1) / 2) * 0.72, 0.0, 0.0), 0))
    if WHICH in ("animals", "all"):
        place = {"dog": (-0.75, 0.15, 0, -75), "crow": (-0.05, 0.1, 0, -30), "pigeon": (0.33, 0.05, 0, -35),
                 "sparrow": (0.62, 0.0, 0, -30), "mouse": (0.84, -0.05, 0, -50), "gecko": (1.02, -0.1, 0, -60),
                 "koi": (0.25, -0.45, 0.06, -75)}
        for cid, clip, fr in ANIMALS:
            x, y, z, rz = place[cid]
            if WHICH == "all":
                y -= 0.9
            items.append((cid, clip, fr, (x, y, z), rz))
    arms = []
    for cid, clip, fr, loc, rz in items:
        arms.append((import_npc(cid, clip, fr, loc, rz), fr))
    # one shared frame: offset each action so that its chosen frame lands on scene frame 1
    for arm, fr in arms:
        if arm is not None and arm.animation_data and arm.animation_data.action:
            pass
    sc.frame_set(1)
    for arm, fr in arms:
        if arm is not None and arm.animation_data and arm.animation_data.action:
            # evaluate this armature at its own frame by baking the pose
            sc.frame_set(fr)
            for pb in arm.pose.bones:
                pb.matrix_basis = pb.matrix_basis.copy()
            mats = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
            arm.animation_data.action = None
            for pb in arm.pose.bones:
                pb.matrix_basis = mats[pb.name]
    bpy.context.view_layer.update()
    # cat-sized reference box (0.46 x 0.13 x 0.25 m), orange
    xs = [it[3][0] for it in items]
    box = C.box("cat_ref", (0.13, 0.46, 0.25), (min(xs) - 0.5, -0.2 if WHICH != "animals" else 0.0, 0))
    C.assign(box, C.principled("cat_ref_mat", (0.8, 0.38, 0.1, 1), 0.7))
    # the real player cat next to the box (read-only use of the cat-asset model), if it exists
    cat_glb = C.asset_path("models/cat/cat.glb")
    if os.path.exists(cat_glb):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=cat_glb)
        for o in [o for o in bpy.data.objects if o not in before]:
            if o.animation_data:
                o.animation_data.action = None
            if o.parent is None:
                o.location = Vector((min(xs) - 0.25, 0.45 if WHICH != "animals" else -0.55, 0))
                o.rotation_mode = "XYZ"
                o.rotation_euler = (0, 0, math.radians(-60))
    if WHICH == "animals":
        tgt, dist, pitch, lens = (-0.25, -0.15, 0.2), 3.4, 14, 40
    elif WHICH == "humans":
        tgt, dist, pitch, lens = (-0.2, 0.0, 0.85), 11.8, 6, 50
    else:
        tgt, dist, pitch, lens = (0.0, -0.4, 0.7), 9.5, 10, 50
    C.preview_render(C.qa_path(f"creatures/lineup_{WHICH}.png"), target=tgt, distance=dist, yaw_deg=0,
                     pitch_deg=pitch, res=RES, samples=SAMPLES, lens=lens, sun_strength=3.5, world_strength=0.8)


main()
