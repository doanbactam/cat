"""Textured turnaround of the exported game mesh (no strand fur) for QA / gallery.
Usage: tools/blender_run.sh blender/cat/render_turnaround.py -- [clip] [frame] [WxH] [samples] [views,comma] [tag]
Writes qa/out/cat-asset/turn/<tag><clip>_<view>.png (default: 6 views + face/paw close-ups;
head close-ups: hd_front,hd_side,hd_q,hd_eye,hd_low)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import bpy  # noqa: E402

import common as C  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
CLIP = argv[0] if argv else "idle"
FRAME = int(argv[1]) if len(argv) > 1 else 0
RES = tuple(int(x) for x in argv[2].split("x")) if len(argv) > 2 else (640, 400)
SAMPLES = int(argv[3]) if len(argv) > 3 else 24
VIEWS = argv[4].split(",") if len(argv) > 4 else ["q_front", "side", "front", "back", "q_back", "top", "hf_q", "paws"]
TAG = argv[5] if len(argv) > 5 else ""

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "cat.blend"))
import cat_qa as Q  # noqa: E402

rig = bpy.data.objects["CatRig"]
rig.animation_data_create()
rig.animation_data.action = bpy.data.actions.get(CLIP)
bpy.context.scene.frame_set(FRAME)
if CLIP == "rest_closed":           # rest pose with the jaw closed (the mesh is modelled 4 deg open)
    import math
    from mathutils import Quaternion
    import cat_anatomy as A
    pb = rig.pose.bones["jaw"]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion((1, 0, 0), math.radians(A.JAW_REST_OPEN_DEG + 3.0))
    bpy.context.view_layer.update()
cm = bpy.data.materials.get("CatEye_Cornea")
cb = next(nd for nd in cm.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
cb.inputs["Base Color"].default_value = (1, 1, 1, 1)
cb.inputs["Alpha"].default_value = 1.0
cb.inputs["Transmission Weight"].default_value = 1.0
Q.studio()
for v in VIEWS:
    Q.camera_for(v, RES)
    Q.render(C.qa_path(f"cat-asset/turn/{TAG}{CLIP}_{v}.png"), SAMPLES)
print("TURNAROUND done")
