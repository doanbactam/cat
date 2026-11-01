"""Dev/QA: mesh the SDF body at a given voxel size and render clay views.
Usage: tools/blender_run.sh blender/cat/dev_shape.py -- [h_mm] [tag] [views,comma]"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bpy
import numpy as np
import common as C
import cat_sdf as S
import cat_mesh as M
import cat_qa as Q

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
h = float(argv[0]) * 1e-3 if argv else 1.2e-3
tag = argv[1] if len(argv) > 1 else "dev"
views = argv[2].split(",") if len(argv) > 2 else ["side", "front", "top", "q_front", "q_back", "face"]

C.reset_scene()
t = time.time()
head_only = "hf_front" in views
bmin, bmax = ((-0.065, -0.275, 0.165), (0.065, -0.10, 0.34)) if head_only else (S.BBOX_MIN, S.BBOX_MAX)
v, q, tr = M.sdf_to_mesh(S.cat_sdf, bmin, bmax, h)
ob = M.mesh_from_arrays("CatHigh", v, [q, tr])
C.shade_smooth(ob, None)
ob.data.materials.append(Q.clay())
print("mesh", time.time() - t)
import cat_parts as P
iris = C.principled("_iris", (0.55, 0.42, 0.08, 1), 0.4)
corn = C.principled("_cornea", (1, 1, 1, 1), 0.02, **{"Transmission Weight": 1.0, "IOR": 1.376})
for side, nm in ((1, "L"), (-1, "R")):
    e = P.build_ear("CatEar_" + nm, side)
    C.shade_smooth(e, None)
    e.data.materials.append(Q.clay())
    eb, cb = P.build_eye(side)
    C.shade_smooth(eb, None); C.shade_smooth(cb, None)
    eb.data.materials.append(iris); cb.data.materials.append(corn)
np.savez_compressed(C.qa_path(f"cat-asset/cache/high_{tag}.npz"), v=v, q=q, t=tr)
Q.studio()
out = Q.render_views(C.qa_path(f"cat-asset/shape/{tag}"), views)
print("RENDERED", out)
