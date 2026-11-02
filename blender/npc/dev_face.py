"""Dev: mesh only the head of a human spec at high resolution and render clay close-ups.
Usage: tools/blender_run.sh blender/npc/dev_face.py -- <character>"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
import numpy as np
import common as C
import npc_build as B
import npc_human as HU
import human_specs as HS

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
name = argv[0] if argv else "ba_tu"
C.reset_scene()
spec = HS.SPECS[name]
body = HU.Body(spec)
M = body.build_model()
HS.dress(body)
c = body.h(0, 0.0, 1.47)
lo, hi = c - 0.16, c + np.array([0.16, 0.16, 0.2])
pts, quads, tris = B.sdf_to_mesh(M, lo, hi, 0.0022)
ob = B.mesh_from_arrays("head", pts, [quads, tris])
B.fix_normals(ob)
C.shade_smooth(ob, None)
C.assign(ob, C.principled("clay", (0.62, 0.47, 0.40, 1), 0.55))
for e in "LR":
    eo = B.eye_mesh("eye" + e, body.L["eye_" + e], body.eye_r, (0, -1, -0.05))
    C.assign(eo, C.principled("eyeclay", (0.9, 0.9, 0.9, 1), 0.2))
for yaw, tag in ((0, "front"), (90, "side"), (30, "q")):
    C.preview_render(C.qa_path(f"creatures/face_{name}_{tag}.png"), target=c + np.array([0, -0.03, 0.0]), distance=0.6,
                     yaw_deg=yaw, pitch_deg=3, res=(300, 340), samples=8, lens=60, ground=False)
