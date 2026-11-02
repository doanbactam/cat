"""Dev: mesh a human spec quickly and render front/side previews (no rig/textures).
Usage: tools/blender_run.sh blender/npc/dev_shape.py -- <character> [h]"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as C
import npc_build as B
import npc_human as HU
import human_specs as HS

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
name = argv[0] if argv else "ba_tu"
h = float(argv[1]) if len(argv) > 1 else 0.004
C.reset_scene()
spec = HS.SPECS[name]
body = HU.Body(spec)
M = body.build_model()
HS.dress(body)
ob = B.build_mesh(M, name, h, spec.tris)
C.assign(ob, C.principled("clay", (0.6, 0.45, 0.38, 1), 0.6))
for i, (yaw, tag) in enumerate(((0, "front"), (90, "side"), (25, "q"))):
    C.preview_render(C.qa_path(f"creatures/dev_{name}_{tag}.png"), target=(0, 0, spec.height * 0.55), distance=3.2,
                     yaw_deg=yaw, pitch_deg=5, res=(360, 480), samples=8, lens=50)
