"""Dev/QA: numeric foot-contact analysis of the locomotion clips straight from the solver.

For every leg the contact point is the paw's ball (finger_* head for the forelegs, toe_* head
for the hind legs) and the toe tip.  A paw is "in stance" while its ball is within 4 mm of its
lowest height; stance slip = |forward foot speed + gait speed| (clips are in place, so a
planted paw must move backwards at exactly the gait speed).  With --mesh the lowest skinned
vertex of each paw is also tracked through the integer frames (ground penetration check).

Usage: tools/blender_run.sh blender/cat/dev_gait.py -- walk,trot,run [substeps] [--mesh]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import common as C  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
clips = argv[0].split(",") if argv else ["walk", "trot", "run"]
sub = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 4
use_mesh = "--mesh" in argv
bpy.ops.wm.open_mainfile(filepath=C.qa_path("cat-asset/cache/stage_weights.blend"))
import cat_anatomy as A  # noqa: E402
import cat_anim as AN  # noqa: E402
import cat_clips as CL  # noqa: E402

rig = bpy.data.objects["CatRig"]
S = AN.Solver(rig)
defs = CL.clip_defs()
LEGS = {"FL": "finger_L", "FR": "finger_R", "HL": "toe_L", "HR": "toe_R"}


def analyse(name):
    nf, fn, loop = defs[name]
    v = A.GAIT_SPEED.get(name, 0.0)
    ts = np.arange(0, nf * sub) / sub
    ball = {k: [] for k in LEGS}
    tipz = {k: [] for k in LEGS}
    rs = {k: [] for k in LEGS}
    for f in ts:
        S.stats = []
        Acc, H = S.solve(fn(f, f / nf))
        for r, tag in S.stats:
            rs[tag].append(r)
        for k, b in LEGS.items():
            ball[k].append(H[b].copy())
            tipz[k].append(S.tip(Acc, H, b).z)
    dt = 1.0 / (A.FPS * sub)
    out = []
    for k in LEGS:
        P = np.array([[p.x, p.y, p.z] for p in ball[k]])
        z = P[:, 2]
        f = -P[:, 1]
        zmin = z.min()
        st = z < zmin + 0.004
        vel = (np.roll(f, -1) - f) / dt
        both = st & np.roll(st, -1)
        slip = np.abs(vel[both] + v) if both.any() else np.array([0.0])
        r = np.array(rs[k])
        ri = np.nonzero(st)[0]
        rtxt = f"reach stance max {r[st].max():.3f} (first {r[ri[0]]:.3f} last {r[ri[-1]]:.3f}) swing max {r[~st].max() if (~st).any() else 0:.3f}"
        out.append(f"{k}: duty {st.mean():.2f} ball zmin {zmin * 1000:.1f}mm tip zmin {min(tipz[k]) * 1000:.1f}mm "
                   f"stance travel {(f[st].max() - f[st].min()) if st.any() else 0:.3f}m slip mean {slip.mean():.3f} "
                   f"max {slip.max():.3f} m/s " + rtxt)
    print(f"GAIT {name} v={v} frames={nf}")
    for o in out:
        print("   ", o)


def mesh_floor(name):
    """Lowest skinned vertex per paw through the integer frames of the written action."""
    nf, fn, loop = defs[name]
    act = AN.write_action(S, name, nf, fn, loop)
    rig.animation_data.action = act
    body = bpy.data.objects["CatBody"]
    groups = {"FL": ("hand_L", "finger_L"), "FR": ("hand_R", "finger_R"), "HL": ("toe_L",), "HR": ("toe_R",)}
    vg = {g.name: g.index for g in body.vertex_groups}
    sel = {}
    for k, gs in groups.items():
        idx = [vg[g] for g in gs if g in vg]
        sel[k] = np.array([v.index for v in body.data.vertices if any(e.group in idx and e.weight > 0.5 for e in v.groups)])
    lows = {k: [] for k in groups}
    for fr in range(nf * AN.KEY_RATE):
        bpy.context.scene.frame_set(fr)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        ev.to_mesh_clear()
        for k in groups:
            lows[k].append(co[sel[k], 2].min())
    print(f"MESH {name}: " + " ".join(f"{k} min {min(l) * 1000:.1f}mm" for k, l in lows.items()))
    rig.animation_data.action = None


for c in clips:
    analyse(c)
    if use_mesh:
        mesh_floor(c)
