"""Textured turnaround of the exported game mesh (no strand fur) for QA / gallery.
Usage: tools/blender_run.sh blender/cat/render_turnaround.py -- [clip] [frame] [WxH] [samples]
Writes qa/out/cat-asset/turn/<clip>_<view>.png for 6 views + face/paw close-ups."""
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

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "cat.blend"))
import cat_qa as Q  # noqa: E402

rig = bpy.data.objects["CatRig"]
rig.animation_data_create()
rig.animation_data.action = bpy.data.actions.get(CLIP)
bpy.context.scene.frame_set(FRAME)
cm = bpy.data.materials.get("CatEye_Cornea")
cb = next(nd for nd in cm.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled")
cb.inputs["Base Color"].default_value = (1, 1, 1, 1)
cb.inputs["Alpha"].default_value = 1.0
cb.inputs["Transmission Weight"].default_value = 1.0
Q.studio()
views = ["q_front", "side", "front", "back", "q_back", "top", "hf_q", "paws"]
for v in views:
    Q.camera_for(v, RES)
    Q.render(C.qa_path(f"cat-asset/turn/{CLIP}_{v}.png"), SAMPLES)
print("TURNAROUND done")
