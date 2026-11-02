"""Build human NPC GLBs (owner: creatures).
Usage: tools/blender_run.sh blender/npc/build_humans.py -- <id> [<id> ...] [--fast] [--no-preview]
Ids: see human_specs.SPECS. Output: assets/models/npc/<id>.glb (+ qa/out/creatures/<id>_*.png)."""
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
import npc_human as HU  # noqa: E402
import npc_human_anim as HA  # noqa: E402
import npc_human_tex as HT  # noqa: E402
import human_specs as HS  # noqa: E402

argv = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if a != "--"]
FAST = "--fast" in argv
NOPREV = "--no-preview" in argv
ids = [a for a in argv if not a.startswith("--")] or list(HS.SPECS)
TEXDIR = C.qa_path("creatures/tex/x")[:-1]


def build(cid: str):
    t0 = time.time()
    C.reset_scene()
    spec = HS.SPECS[cid]
    body = HU.Body(spec)
    M = body.build_model()
    HS.dress(body)
    h = 0.0045 if FAST else 0.003
    skin = B.build_mesh(M, f"{cid}_body", h, spec.tris)
    skin.name = "Body"
    skin.data.name = f"{cid}_body"
    # rig
    arm = B.make_armature("Armature", body.bones())
    bones = [b.name for b in arm.data.bones]
    W = B.skin_weights(skin, M, bones)
    B.apply_weights(skin, arm, W, bones)
    # eyes
    eyes = []
    for sd in "LR":
        e = B.eye_mesh(f"eye_{sd}", body.L[f"eye_{sd}"] + np.array([0, -0.0005, 0]), body.eye_r, (0.0, -1.0, -0.05),
                       segs=20, rings=12)
        eyes.append(e)
    eye_ob = C.join(eyes, "Eyes")
    B.rigid_bind(eye_ob, arm, "head")
    # UVs + textures
    B.unwrap(skin, [(body.h(0, -0.03, 1.47), 0.11 * body.hs, 1.9),
                    (body.L["wrist_L"], 0.08 * body.s, 1.3), (body.L["wrist_R"], 0.08 * body.s, 1.3)])
    tex = HT.HumanTex(body, M, HS.MATS.get(cid, {}))
    prefix = os.path.join(TEXDIR, cid)
    sz = (1024, 512) if FAST else (spec.tex_size, spec.nrm_size)
    paths = B.synthesize_textures(skin, M, tex, prefix, sz[0], sz[1])
    mat = B.pbr_material(f"{cid}_mat", paths["albedo"], paths["normal"], paths["orm"], subsurface=0.0, spec=0.45)
    C.assign(skin, mat)
    iris = EY.iris_texture(prefix + "_eye.jpg", spec.eye_col, "#d6cabd", iris_r=0.30, pupil_r=0.095, seed=spec.seed)
    emat = B.pbr_material(f"{cid}_eye", iris, None, None, spec=0.6)
    bsdf = next(n for n in emat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.06
    C.assign(eye_ob, emat)
    # animation
    anim = AN.Animator(arm)
    ha = HA.HumanAnim(body)
    if FAST:
        for nm in ("idle", "walk"):
            anim.bake_clip(nm, getattr(ha, nm), ha.clips[nm][0], ha.clips[nm][1])
    else:
        ha.bake_all(anim)
    out = C.asset_path(f"models/npc/{cid}.glb")
    arm["walk_speed"] = round(getattr(ha, "walk_speed_eff", spec.walk_speed), 3)
    B.export(out, arm, [skin, eye_ob])
    print(f"{cid}: body {B.tri_count(skin)} tris, eyes {B.tri_count(eye_ob)} tris, "
          f"walk {arm['walk_speed']} m/s, {time.time() - t0:.0f}s")
    meta = {"id": cid, "tris": B.tri_count(skin) + B.tri_count(eye_ob), "walk_speed": arm["walk_speed"],
            "height": spec.height}
    import json
    with open(os.path.join(TEXDIR, f"{cid}_meta.json"), "w") as f:
        json.dump(meta, f)
    if not NOPREV:
        preview(cid, spec, arm, anim, ha)


def preview(cid, spec, arm, anim, ha):
    H = spec.height
    anim.set_pose(ha.idle(0.5))
    C.preview_render(C.qa_path(f"creatures/{cid}_idle.png"), target=(0, 0, H * 0.53), distance=H * 1.9,
                     yaw_deg=25, pitch_deg=6, res=(420, 560), samples=24, lens=50)
    C.preview_render(C.qa_path(f"creatures/{cid}_face.png"), target=(0, -0.05, H * 0.925), distance=0.62,
                     yaw_deg=18, pitch_deg=2, res=(400, 400), samples=24, lens=60)
    if "--poses" in argv:
        tw = ha.clips["walk"][0] / 30.0
        poses = [("walk0", ha.walk(0.0)), ("walk1", ha.walk(tw * 0.25)), ("walk2", ha.walk(tw * 0.5)),
                 ("sit", ha.sit(1.0)), ("pet_cat", ha.pet_cat(0.4)), ("talk", ha.talk(0.6)), ("sell", ha.sell(0.5)),
                 ("shoo", ha.shoo(0.3)), ("carry", ha.carry(0.2)), ("phone", ha.phone(1.0)),
                 ("look", ha.look_around(1.5))]
        files = []
        for tag, p in poses:
            anim.set_pose(p)
            f = C.qa_path(f"creatures/pose_{cid}_{tag}.png")
            C.preview_render(f, target=(0, 0, H * 0.48), distance=H * 2.1, yaw_deg=60, pitch_deg=5,
                             res=(200, 260), samples=6, lens=50)
            files.append(f)
        print("POSES", " ".join(files))


for cid in ids:
    build(cid)
