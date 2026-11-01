"""Dev: rebuild selected clips from the weights stage and render frames.
Usage: tools/blender_run.sh blender/cat/dev_anim.py -- clip1,clip2 [views] [frames_per]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import importlib
import bpy
import common as C
argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
clips = argv[0].split(",")
views = argv[1].split(",") if len(argv) > 1 else ["side"]
fper = int(argv[2]) if len(argv) > 2 else 4
bpy.ops.wm.open_mainfile(filepath=C.qa_path("cat-asset/cache/stage_weights.blend"))
import cat_anim as AN, cat_clips as CL, cat_qa as Q
rig = bpy.data.objects["CatRig"]
solver = AN.Solver(rig)
defs = CL.clip_defs()
Q.studio()
body = bpy.data.objects["CatBody"]
body.data.materials.clear(); body.data.materials.append(Q.clay())
for name in clips:
    nf, fn, loop = defs[name]
    act = AN.write_action(solver, name, nf, fn, loop)
    rig.animation_data.action = act
    for k in range(fper):
        fr = int(round(k * nf / fper)) if loop else int(round(k * nf / max(1, fper - 1)))
        bpy.context.scene.frame_set(fr)
        for v in views:
            Q.camera_for(v, (480, 300))
            Q.render(C.qa_path(f"cat-asset/anim/d_{name}_{k}_{v}.png"), samples=8)
