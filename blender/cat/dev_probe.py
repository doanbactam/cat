"""Dev: print key landmark positions + per-leg reach for named poses (no rendering)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bpy
import common as C
bpy.ops.wm.open_mainfile(filepath=C.qa_path("cat-asset/cache/stage_weights.blend"))
import cat_anim as AN, cat_clips as CL
from mathutils import Vector
rig = bpy.data.objects["CatRig"]
S = AN.Solver(rig)
def report(name, prm):
    S.stats = []
    Acc, H = S.solve(prm)
    per = {}
    for r, t in S.stats: per[t] = max(per.get(t, 0), r)
    def pt(b, local=None):
        v = H[b] if local is None else H[b] + Acc[b] @ (Vector(local) - S.head[b])
        return "(f%.3f z%.3f)" % (-v.y, v.z)
    rump = H["pelvis"] + Acc["pelvis"] @ (Vector((0, 0.205, 0.150)) - S.head["pelvis"])
    belly = H["spine_02"] + Acc["spine_02"] @ (Vector((0, 0.05, 0.112)) - S.head["spine_02"])
    chin = S.tip(Acc, H, "jaw")
    print(f"{name:10s} reach " + " ".join(f"{k}:{v:.2f}" for k, v in sorted(per.items())),
          "shoulderL", pt("upperarm_L"), "hipL", pt("thigh_L"), "rump z%.3f" % rump.z, "belly z%.3f" % belly.z,
          "chin (f%.3f z%.3f)" % (-chin.y, chin.z), "eye", pt("fpp_eye"), "tail1 tip", pt("tail_02"))
names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = [n for n in names if n != "--"]
for n in names:
    report(n, getattr(CL, n) if hasattr(CL, n) else eval(n, vars(CL)))
