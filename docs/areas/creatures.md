# Area: creatures — NPC humans & animals

All NPC models are generated procedurally by Blender scripts (no hand-made or downloaded data) and exported
as rigged, animated GLBs to `assets/models/npc/`. 17 models: 10 humans, 7 animals.

| id | who | tris | clips |
|---|---|---|---|
| `ba_tu` | **Bà Tư** — elderly tea-stall owner, 1.49 m, stooped; lavender floral *áo bà ba*, black satin trousers, leather sandals, grey bun | ~18 k | human set |
| `co_hoa` | **Cô Hoa** — fishmonger, 1.55 m; blue floral blouse, maroon plastic apron, white rubber boots, *nón lá* (conical palm-leaf hat with chin ribbon) | ~19 k | human set |
| `chu_sau` | **Chú Sáu** — bánh mì vendor, 1.66 m, heavier; navy polo with white collar, khaki trousers, flip-flops, red cap, stubble | ~18 k | human set |
| `bin` | **Bin** — 9-year-old, 1.28 m (same rig at child proportions); white school shirt, navy shorts, red Young-Pioneer scarf, sandals | ~16 k | human set |
| `ped_office` | office worker, 1.70 m; striped long-sleeve shirt tucked in, slacks, leather shoes, side-part hair, phone | ~16 k | human set |
| `ped_student` | student, 1.58 m; striped T-shirt, jeans, backpack, sneakers, ponytail, phone | ~16 k | human set |
| `ped_elder_man` | elderly man with cane, 1.62 m, stooped; plaid shirt, grey trousers, sandals, thin grey hair | ~16 k | human set |
| `ped_helmet_woman` | woman in pink sun-protection jacket, floral wrap sun-skirt over jeans, face mask, half-shell motorbike helmet | ~16 k | human set |
| `ped_shopper` | older woman with a red woven plastic market basket (greens inside), permed hair, floral blouse & trousers | ~16 k | human set |
| `ped_xeom` | xe ôm driver, 1.68 m; olive jacket with mandarin collar, green half-shell helmet, stubble | ~16 k | human set |
| `dog` | **Vện** — brindle Vietnamese street dog, 0.5 m at the withers, erect ears, sickle tail | ~15 k | `idle walk run bark sleep sniff growl` |
| `pigeon` | rock pigeon (Xám), iridescent green/purple neck, two black wing bars | ~7 k | `idle peck walk fly takeoff land` |
| `crow` | **Lão Quạ** — old house crow, grey collar, faded/ragged plumage, raised nape tufts, chipped upper mandible, notched tail | ~8 k | bird set + `caw hop` |
| `sparrow` | Eurasian tree sparrow (chestnut cap, black cheek spot, white collar) | ~4 k | bird set |
| `mouse` | house mouse 9 cm + tail | ~3 k | `idle run` |
| `gecko` | house gecko 11 cm, adhesive toe pads | ~3.5 k | `idle run` |
| `koi` | kohaku/sanke koi 0.45 m | ~5 k | `swim idle` |

Human clip set (all looping, in place): `idle walk sit talk sell pet_cat shoo look_around carry phone`.

## How it is built (regenerate)
```
tools/blender_run.sh blender/npc/build_humans.py -- <id ...>        # all humans if no id; --fast for a quick look
tools/blender_run.sh blender/npc/build_animals.py -- dog pigeon crow sparrow mouse gecko koi [--poses]
tools/godot_import.sh && python3 blender/npc/configure_import.py && tools/godot_import.sh
tools/run_tests.sh test_creatures
tools/screenshot.sh scene=res://assets/models/npc/preview/lineup.tscn out=$PWD/qa/out/creatures/lineup.png call=show_special
```
A human takes ~4–10 min (CPU, depends on machine load), an animal 1–3 min. `--poses` renders a contact sheet
of key poses to `qa/out/creatures/pose_<id>_<clip>.png`. Dev helpers: `blender/npc/dev_face.py <id>` (high-res
clay head), `blender/npc/dev_shape.py <id>` (clay body).

### Pipeline (`blender/lib/npc_*.py`)
1. **Shape = signed-distance model** (`npc_sdf.py`): each creature is a list of anatomical primitives
   (ellipsoids, tapered capsules, flattened cones, polygons …) smoothly unioned, minus carves (eye apertures,
   mouth slit, ear cups, feather notches), plus *layers* (garments, hair, hats, apron, plumage parts) that win
   their own texture label. Every primitive knows the bone that drives it.
2. **Mesh**: block-sparse sampling + OpenVDB marching (`npc_build.sdf_to_mesh`, 0.9–3 mm voxels), symmetric
   decimation to the triangle budget, tangential relaxation + re-projection onto the SDF.
3. **Rig & skinning**: armature from anatomical landmarks; weights come from the primitives themselves
   (soft-min over each primitive's distance → bone, Laplacian-smoothed, 4 influences) — no bone-heat failures,
   clean joints, garments follow the limbs they were offset from. Rigid accessories (hat, helmet, cane,
   basket, phone) are weighted 100 % to one bone. Eyes are separate UV-sphere meshes on `head`.
4. **UVs**: Smart-UV with local magnification of the face/hands (texel density ×1.9 on faces).
5. **Textures** (`synthesize_textures`): Cycles bakes per-texel object-space position / normal / tangent of the
   game mesh; numpy then evaluates — in 3D, so no seams — the SDF label (skin / lips / hair / each garment …),
   the high-detail SDF normal (facial features, hems, fingers that decimation removed), SDF ambient occlusion,
   and procedural materials: skin tone with blush zones, age spots, soft brows, lash line, lip border; hair
   with combed strand clumps flowing toward the bun/crown; prints (floral cells, plaid, stripes, denim twill),
   stitched hems, fabric folds and weave relief; nón lá palm-leaf ribs + bamboo rings + sun-bleach; rubber,
   plastic, leather; fur strands following per-primitive flow directions (brindle stripes perpendicular to the
   flow), feather scallops, pigeon neck iridescence, koi scales. Output: albedo (2048 humans/dog, JPEG),
   normal (PNG, OpenGL/+Y, matches glTF), ORM (AO / roughness / metal, JPEG, also wired to glTF occlusion).
6. **Animation** (`npc_anim.py` + `npc_human_anim.py`, `npc_dog.py`, `npc_bird.py`, …): poses are written as
   rotation deltas in armature axes; legs use analytic 2-bone IK in the sagittal plane with planted stance feet
   (no foot sliding at the catalog speed), heel-strike/toe-off foot roll, pelvis bob/sway/rotation and
   counter-rotating shoulders for humans; lateral-sequence walk, rotary gallop for the dog; head-bob walk for
   birds; travelling body wave for the koi; lateral undulation for the gecko. Clips are keyed every frame into
   one Action each (exported as Godot animations).
7. `blender/npc/configure_import.py` writes loop flags into the `.glb.import` files and the catalog.

## API / conventions for users of the models
See `docs/requests/creatures.md` (world-life hand-off): skeleton path `Armature/Skeleton3D`, clip list,
speeds in `assets/models/npc/catalog.json`, in-place clips, front +Z, origin on the ground, bird flight wings
driven by the `upperarm_*` scale, stool height for `sit`, cat position for `pet_cat`.

Bones — humans: `root pelvis spine_01 spine_02 chest neck head jaw clavicle_L/R upperarm_L/R forearm_L/R
hand_L/R fingers_L/R thumb_L/R thigh_L/R shin_L/R foot_L/R toe_L/R`. Quadrupeds: `root pelvis spine_01 spine_02
chest neck head jaw ear_L/R tail_01.. scapula_L/R upperarm/forearm/hand_L/R thigh/shin/foot/toe_L/R`. Birds:
`root pelvis chest neck_01 neck_02 head jaw tail wingfold_L/R upperarm/forearm/hand_L/R thigh/shin/foot/toe_L/R`.
Koi: `root head jaw spine_01..06 tail_fin dorsal anal pectoral_L/R pelvic_L/R`.

## Verification
* `tools/run_tests.sh test_creatures` — every GLB loads, skeleton + bones, skinned mesh, clip names, loop
  flags, real-world height range, catalog completeness, walk clip stays in place.
* Preview scene `assets/models/npc/preview/lineup.tscn` (all models next to a cat-sized 0.46 × 0.25 m box and,
  when present, the real player cat `assets/models/cat/cat.glb` for scale).
* Gallery: `docs/gallery/creatures_humans.jpg` (all 10 humans + cat box + Cam), `creatures_animals.jpg`
  (Vện, Lão Quạ, pigeon, koi, sparrow, mouse, gecko next to Cam and the cat box), `creatures_named.jpg`
  (named NPC faces + full bodies). Regenerate with `tools/blender_run.sh blender/npc/render_lineup.py -- humans|animals [samples] [WxH]`.

## Revision log
* Pass 2 (resume after usage-limit cut-off): faces got a mouth line with tucked corners, wider/fuller lips,
  upper-lid crease sockets, larger ears with a concha hollow and a slightly narrower jaw; Vện got a heavier
  build (deeper chest, thicker neck/legs, bigger skull), smaller almond eyes, sturdier ears and a rewritten
  brindle (irregular dorso-ventral tiger streaks + ticking instead of contour-like rings); Lão Quạ's grey
  house-crow shawl (nape/neck/upper breast) is now clearly readable. All GLBs rebuilt, tests re-run.

## Known gaps (honest)
* Faces still read slightly heavy in the cheeks/jaw and lips are subtle; the lip texture's vermilion fades
  to skin before the (widened) geometric mouth corners. Cô Hoa shows a small dark-red spot at a mouth
  corner in close-ups, Chú Sáu's cap brim edge is slightly jagged and Cô Hoa's hair has a pale hair-clip disc
  under the nón lá. Needs one more face pass + rebuild (≈35 min for all humans).
* Vện still stands with a fairly upright neck and long legs (lean village-dog look rather than stocky); ears
  are thin. Brindle reads well side-on; on end-on surfaces it fades into grizzle by design.
* Faces are deliberately soft / simplified (no facial rig beyond the jaw, eyes don't blink; eyelids are
  sculpted). Up close they read as stylised-realistic, not photoreal. Hair is a sculpted shell with a strand
  texture, not hair cards.
* Garments are rigid offsets of the body: no secondary cloth motion; loose garments can slightly intersect
  in extreme poses (deep `pet_cat` crouch, `sit`).
* Skin uses a standard glTF material (no subsurface in Godot; world-life may set
  `subsurf_scatter_enabled` on the `Body` surface for named characters).
* Bird flight wings are shown/hidden by bone scale (ground ↔ flight). Wing folding is not anatomical.
* Animals' fur is a texture + normal map only (no shell fur like Cam).
* Gecko/mouse are tiny; their detail is mostly texture.
* No LOD meshes authored by hand (Godot generates LODs on import).
