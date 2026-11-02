"""Build animal NPC GLBs (owner: creatures).
Usage: tools/blender_run.sh blender/npc/build_animals.py -- <id> [<id> ...] [--fast] [--poses]
Ids: dog (Vện), mouse, gecko, pigeon, crow (Lão Quạ), sparrow, koi.
Output: assets/models/npc/<id>.glb, previews in qa/out/creatures/."""
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import common as C  # noqa: E402
import npc_anim as AN  # noqa: E402
import npc_build as B  # noqa: E402
import npc_eyes as EY  # noqa: E402
import npc_quad as Q  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
FAST = "--fast" in argv
ids = [a for a in argv if not a.startswith("--")]
TEXDIR = C.qa_path("creatures/tex/x")[:-1]

# id: (module, h voxel, tris, albedo size, normal size, eye spec)
SPECIES = {
    "dog": dict(mod="npc_dog", h=0.0028, tris=14000, alb=2048, nrm=1024,
                eye=dict(col="#5a3417", sclera="#3a2a20", iris_r=0.42, pupil_r=0.17, ring="#8a5a28"),
                cam=dict(target=(0, -0.05, 0.38), distance=1.9, yaw=55)),
    "mouse": dict(mod="npc_mouse", h=0.0009, tris=3000, alb=512, nrm=512,
                  eye=dict(col="#0c0a0a", sclera="#0c0a0a", iris_r=0.45, pupil_r=0.2, full=True),
                  cam=dict(target=(0, 0.0, 0.025), distance=0.35, yaw=55)),
    "gecko": dict(mod="npc_gecko", h=0.0007, tris=3000, alb=512, nrm=512,
                  eye=dict(col="#8a7a5a", sclera="#6a5e48", iris_r=0.48, pupil_r=0.16, slit=True, full=True),
                  cam=dict(target=(0, 0.0, 0.01), distance=0.32, yaw=40, pitch=40)),
    "pigeon": dict(mod="npc_bird", h=0.0016, tris=6000, alb=1024, nrm=1024,
                   eye=dict(col="#c4561c", sclera="#c4561c", iris_r=0.46, pupil_r=0.17, full=True, ring="#e8a040"),
                   cam=dict(target=(0, 0.0, 0.15), distance=0.95, yaw=55)),
    "crow": dict(mod="npc_bird", h=0.0019, tris=7000, alb=1024, nrm=1024,
                 eye=dict(col="#2a2018", sclera="#1a1410", iris_r=0.46, pupil_r=0.2, full=True),
                 cam=dict(target=(0, 0.0, 0.2), distance=1.2, yaw=55)),
    "sparrow": dict(mod="npc_bird", h=0.0009, tris=4000, alb=512, nrm=512,
                    eye=dict(col="#1a1210", sclera="#1a1210", iris_r=0.46, pupil_r=0.2, full=True),
                    cam=dict(target=(0, 0.0, 0.07), distance=0.5, yaw=55)),
    "koi": dict(mod="npc_fish", h=0.0016, tris=5000, alb=1024, nrm=1024,
                eye=dict(col="#1a1410", sclera="#c8b070", iris_r=0.40, pupil_r=0.2, ring="#d8b060"),
                cam=dict(target=(0, 0.0, 0.0), distance=1.0, yaw=60, pitch=30)),
}


def build(cid):
    t0 = time.time()
    sp = SPECIES[cid]
    mod = importlib.import_module(sp["mod"])
    C.reset_scene()
    kit = mod.kit(cid) if hasattr(mod, "kit") else None
    if kit is None:
        lm = mod.landmarks()
        kit = dict(lm=lm, model=mod.build_model(lm), bones=Q.quad_bones(lm, mod.N_TAIL),
                   tex=Q.FurTex(None, mod.colour, seed=7), anim=mod.DogAnim(lm, mod.N_TAIL),
                   eyes=[(lm["eye_L"], 0.0108, (0.35, -1, 0.05)), (lm["eye_R"], 0.0108, (-0.35, -1, 0.05))],
                   warp=[(lm["head_base"] + np.array([0, -0.08, 0]), 0.12, 1.5)], meta={"speeds": mod.SPEEDS})
    M = kit["model"]
    if kit["tex"].model is None:
        kit["tex"].model = M
        kit["tex"].names = M.label_names()
    h = sp["h"] * (1.6 if FAST else 1.0)
    arm = B.make_armature("Armature", kit["bones"])
    bones = [b.name for b in arm.data.bones]
    if "parts" in kit:
        objs = []
        for i, (pm, hf, tf) in enumerate(kit["parts"]):
            o = B.build_mesh(pm, f"{cid}_part{i}", h * hf, int(sp["tris"] * tf))
            B.apply_weights(o, arm, B.skin_weights(o, pm, bones), bones)
            objs.append(o)
        for o in objs[1:]:
            for m in list(o.modifiers):
                o.modifiers.remove(m)
        body = C.join(objs, "Body") if len(objs) > 1 else objs[0]
        if not any(m.type == "ARMATURE" for m in body.modifiers):
            mm = body.modifiers.new("Armature", "ARMATURE")
            mm.object = arm
    else:
        body = B.build_mesh(M, f"{cid}_body", h, sp["tris"])
        W = B.skin_weights(body, M, bones)
        B.apply_weights(body, arm, W, bones)
    body.name = "Body"
    meshes = [body]
    eyes = []
    for i, (c, r, fwd) in enumerate(kit["eyes"]):
        eyes.append(B.eye_mesh(f"eye_{i}", c, r, fwd, segs=16, rings=10))
    eye_ob = C.join(eyes, "Eyes")
    B.rigid_bind(eye_ob, arm, kit.get("eye_bone", "head"))
    meshes.append(eye_ob)
    for extra in kit.get("extra_meshes", []):
        meshes.append(extra(arm))
    B.unwrap(body, kit.get("warp", []))
    prefix = os.path.join(TEXDIR, cid)
    sizes = (min(sp["alb"], 1024), min(sp["nrm"], 512)) if FAST else (sp["alb"], sp["nrm"])
    paths = B.synthesize_textures(body, M, kit["tex"], prefix, sizes[0], sizes[1])
    mat = B.pbr_material(f"{cid}_mat", paths["albedo"], paths["normal"], paths["orm"], spec=0.4,
                         sheen=kit.get("sheen", 0.0))
    C.assign(body, mat)
    e = sp["eye"]
    iris = EY.iris_texture(prefix + "_eye.jpg", e["col"], e["sclera"], iris_r=e["iris_r"], pupil_r=e["pupil_r"],
                           slit=e.get("slit", False), full_iris=e.get("full", False), ring_col=e.get("ring"),
                           size=128)
    emat = B.pbr_material(f"{cid}_eye", iris, None, None, spec=0.7)
    next(n for n in emat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs["Roughness"].default_value = 0.05
    C.assign(eye_ob, emat)
    anim = AN.Animator(arm)
    kit["anim"].bake_all(anim)
    out = C.asset_path(f"models/npc/{cid}.glb")
    B.export(out, arm, meshes)
    meta = dict(id=cid, tris=sum(B.tri_count(m) for m in meshes), **kit.get("meta", {}))
    with open(os.path.join(TEXDIR, f"{cid}_meta.json"), "w") as f:
        json.dump(meta, f)
    print(f"{cid}: {meta['tris']} tris, {time.time() - t0:.0f}s")
    cam = sp["cam"]
    anim.set_pose(kit["anim"].idle(0.4))
    C.preview_render(C.qa_path(f"creatures/{cid}_idle.png"), target=cam["target"], distance=cam["distance"],
                     yaw_deg=cam["yaw"], pitch_deg=cam.get("pitch", 8), res=(560, 420), samples=24, lens=50)
    if "--poses" in argv:
        files = []
        for nm in kit["anim"].pose_list() if hasattr(kit["anim"], "pose_list") else \
                [(n, 0.3) for n in getattr(mod, "CLIPS")]:
            tag, tt = nm
            anim.set_pose(getattr(kit["anim"], tag)(tt))
            f = C.qa_path(f"creatures/pose_{cid}_{tag}.png")
            C.preview_render(f, target=cam["target"], distance=cam["distance"] * 1.1, yaw_deg=cam["yaw"] + 25,
                             pitch_deg=cam.get("pitch", 8), res=(240, 180), samples=6, lens=50)
            files.append(f)
        print("POSES", " ".join(files))


for cid in ids:
    build(cid)
