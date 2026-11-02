"""Dev/QA: clay renders of a cached stage's game mesh (default stage_low) in the rest pose.
Usage: tools/blender_run.sh blender/cat/dev_low.py -- [stage] [views,comma] [tag]"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bpy  # noqa: E402

import common as C  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
stage = argv[0] if argv else "low"
views = argv[1].split(",") if len(argv) > 1 else ["hd_eye", "hd_q", "hd_front"]
tag = argv[2] if len(argv) > 2 else stage
bpy.ops.wm.open_mainfile(filepath=C.qa_path(f"cat-asset/cache/stage_{stage}.blend"))
import cat_qa as Q  # noqa: E402

body = bpy.data.objects["CatBody"]
body.data.materials.clear()
body.data.materials.append(Q.clay())
Q.studio()
for v in views:
    Q.camera_for(v, (480, 300))
    Q.render(C.qa_path(f"cat-asset/shape/{tag}_{v}.png"), samples=12)
print("DEV_LOW done")
