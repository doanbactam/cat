# street-props — street furniture, stall kit, home extras, festival lanterns, clutter & gameplay items

Owner area: `street-props`. Everything is generated procedurally by Blender Python (no hand-placed
geometry, no downloaded assets): one `.glb` per prop under `assets/models/props/`, its baked texture set
under `assets/textures/props/`, and one entry per prop in `assets/models/props/catalog.json`.

## What is built (106 props)

| Category | Props |
|---|---|
| street (15) | `traffic_cone`, `lamp_post_colonial`, `lamp_post_modern` (both with `light_pos`/`lights`), `construction_barrier`, `trash_bin_municipal`, `trash_bin_household`, `drain_grate`, `manhole_cover`, `fire_hydrant`, `mailbox`, `bicycle_rack` |
| sign | `sign_aframe_com` (Cơm tấm Cô Ba), `sign_aframe_cafe` (Cà phê Gác Mái chalkboard), `sign_lightbox` (Bún chả Hàng Mây), `banner_standing` (Trà chanh giã tay) |
| utility | `electric_pole_concrete` (transformer box + cable-bundle stubs, ATTACH points), `cable_coil_small`, `cable_coil_large`, `cable_drum`, `ac_unit`, `gas_cylinder` |
| container | `cardboard_box_open` (NAP/SIT spot inside, towel), `cardboard_box_closed` (knockable), `cardboard_flat_pile`, `styrofoam_box`, `plastic_crate_blue/red`, `wooden_crate`, `recycling_sack`, `bucket_plastic`, `basin_plastic`, `rice_sack`, `bottle_crate` |
| stall | `food_cart_xoi` & `banh_mi_cart` (glass display case, trays of food, bicycle wheels, printed skirt), `pho_pot_stove` (stock pot on a charcoal stove, ember light), `umbrella_tarp`, `tea_set` (knockable), `fruit_basket` (mango, dragon fruit, banana, rambutan), `flower_bucket`, `fish_basin` (live fish, `water_level` meta) |
| furniture | `stool_plastic_red/blue/green` (knockable, SIT/NAP), `table_plastic_low` (chopsticks, tissue box, chili jar) |
| home / plant | brooms (2), slippers, honeycomb sandals, canvas shoes, `bird_cage`, `wind_chime`, `altar_box` (ông Địa altar, candle glow), `laundry_rack`, `food_bowl`, `water_bowl`; plants `pot_snake_plant`, `pot_chili`, `pot_bonsai`, `pot_aloe` |
| festival | `star_lantern_red/yellow/multi` (cellophane on bamboo, paper fringes), `silk_lantern_round/oval` (Hội An), `carp_lantern`, `lantern_string` (3.2 m, ATTACH_01/02 ends) — all skins are `__lit` (emissive at night) + omni light markers |
| clutter (knockable) | `cup_ceramic` (blue-white), `mug_enamel`, `glass_tra_da` (glass + iced tea), `vase_flower` (chrysanthemums), `cactus_pot`, `bottle_fish_sauce`, `bottle_soy`, `bottle_water`, `phone`, `tv_remote`, `book_single`, `book_stack`, `can_condensed_milk` |
| item (26 files) | `item_<id>.glb` for every `mesh` in `data/items/items.json`: fish, dried_fish (anchovy bundle), shrimp, gio_lua, pate_crust, quail_egg, mooncake_crumb, cap, lucky_cat_figurine (original design), letter, key, leg_band, toy_mouse, yarn, silver_spoon, hair_clip, glass_marble, brass_bell, pigeon_feather, memory_photo (shared by memory_01..12), collar_red / collar_bell / collar_jade, catnip, herbal_tonic, skill_tonic |

All shop names, brands, phone numbers and print are fictional (see `blender/props/gen_labels.py`).

## Pipeline / how to regenerate

```
python3 blender/props/gen_labels.py                 # Pillow label/print sheets -> blender/props/labels/*.png
tools/blender_run.sh blender/props/build_props.py -- [--only id1,id2,pre*] [--category stall,item] \
        [--missing] [--preview] [--list]
BLENDER_TIMEOUT=7200 for long batches (each prop bakes in 30 s – 3 min on a loaded 4-core box).
python3 blender/props/contact_sheet.py qa/out/street-props/sheet.png [id,id,...] [--cols N]
python3 blender/props/gen_i18n.py                   # data/i18n/requests/street-props.csv (PROP_* names)
tools/godot_import.sh && tools/validate.sh "" assets/models/props && tools/run_tests.sh street_props
tools/screenshot.sh scene=res://assets/models/props/preview/props_showcase.tscn out=$PWD/qa/out/street-props/x.png \
        size=1280x720 frames=40 props=stall,furniture [hour=21]
```

Debug env: `PROPS_UVONLY=1` (geometry + UV stats only, no bake), `PROPS_FAST=256` (tiny 1-sample bake).
Several build processes may run in parallel (catalog writes are `flock`ed).

Code layout:
- `blender/lib/props_bake.py` — registry (`@prop`/`register`), join → cull ground faces → weighted normals →
  atlas unwrap with texel-importance weights → Cycles bakes (geometry masks AO/convex-edge/cavity, then albedo,
  ORM, tangent normal) → GLB export → texture externalisation (`../../textures/props/<id>_{albedo.jpg,orm.jpg,normal.png}`)
  → `.import` files (post-import script, LODs, shadow meshes) → catalog entry.
- `blender/lib/props_nodes.py` — layered material recipes (plastic with sun-fade/scuffs/stress-whitening,
  painted metal with primer chips/rust streaks, bare metals, wood, bamboo, weave, ceramic, terracotta, concrete,
  cardboard, paper, fabric, rubber, styrofoam, cellophane film, silk, tinted glass, fish skin, organics, leaves,
  soil) all driven by the baked masks; `label` overlays a print sheet through the `LabelUV` layer.
- `blender/lib/props_geo.py` — bevelled primitives, lathe/tube/extrude, deformers (wobble, dent, lean), colliders
  (`col_<surface>[_climb]_NN-convcolonly`), markers, label projections.
- `blender/props/p_street.py`, `p_utility.py`, `p_home.py`, `p_stall.py`, `p_festival.py`, `p_clutter.py`, `p_items.py`.

## Godot side / API

- Post-import `assets/models/props/_import/props_post_import.gd` (per-GLB, reads the catalog):
  - materials `<id>` (opaque PBR, AO from ORM.r), `<id>__2s` (double-sided + backlight: leaves, paper, cloth),
    `<id>__lit` (double-sided, backlit, emission = albedo, energy 0 by day, meta `night_emission_energy`,
    mesh meta `night_emissive`), `glass_*` (alpha-blended, no shadow).
  - colliders → `StaticBody3D` (layer 1, +6 climbable when tagged `climb`), exact `BoxShape3D` when the hull is a box,
    meta `surface` (one of the contract surfaces).
  - `dynamic: true` props → root `RigidBody3D` with `res://scripts/systems/pushable.gd` (`Pushable`), `mass`,
    `material_kind`, optional `break_height` — i.e. ready for the "knock it off" mischief.
  - markers: `NAP_*` → group `prop_nap_spot`, `SIT_*` → `prop_sit_spot`, `CLIMB_*` → `prop_climb_point`,
    `ATTACH_*`/`HANG_*` → `prop_attach_point`, `LIGHT_*` → Omni/SpotLight3D (group `prop_night_light`, meta
    `night_light_energy`, energy 0 by day).
  - lit props get a `NightLight` child (`_runtime/prop_night_light.gd`) that fades emission + lights in at dusk
    from `TimeOfDay`.
  - root metas: `prop_id`, `prop_category`, `surface`, `name_key`, `mass`, `item_id` (items); root in group `street_prop`.
- Catalog entry fields: `id, file, kind, category, footprint [w,d], width, depth, height, bounds_min/max (Godot),
  dynamic, mass, surface, material_kind, name_key, tris, materials, texture_size, texel_density, textures,
  colliders, climb_points, nap_spots, entrances, sit_spots?, lights?[{name,pos,kind,range,energy,color,...}],
  light_pos?, attach_points?, emissive?, tags, variant_of?, item_id?, break_height?` plus prop-specific metas
  (`origin: "hang_point"` for hanging props — geometry hangs below the origin; `water_level`, `shelter_radius`, `vendor`...).
- Hanging props (`grounded: false`: bird cage, wind chime, lanterns, lantern string) have their origin at the hang point.
- Showcase: `assets/models/props/preview/props_showcase.tscn` (args `props=<categories|ids|prefix*>`, `cols=`, `hour=`).
- QA dump: `tools/godot_lock.sh godot --headless --path . --script res://assets/models/props/preview/dump_props.gd -- [ids]`.
- Tests: `tests/test_street_props.gd` (catalog contract, required props, every items.json mesh exists, dynamic props
  import as Pushable RigidBody3D with mass, static colliders have valid surfaces, lit props have NightLight).
- i18n: `data/i18n/requests/street-props.csv` (PROP_* names, en + vi). Item names use the existing `ITEM_*` keys.

## Known gaps (honest)

- Large props (food carts, umbrella, pho stove) are capped at a 2048² set, so their texel density is ~600–900 px/m
  rather than ≥1024 (small props and items are 1500–4000 px/m). Undersides are de-weighted but not split into
  separate texture sets.
- Glass is a simple alpha-blended material (no refraction/transmission); bottles are baked "opaque glass".
- Shell-level details such as plant leaves and lantern fringes are single-sided sheets rendered double-sided;
  no wind animation (world may add a vertex-wind shader later).
- One texture set per prop (3 files each, ~106 sets): there is no shared trim atlas, so draw calls are 1–3 per prop
  instance. MultiMesh scattering is up to `world`.
- `item_memory_photo` is shared by `memory_01..12` (same print). The brass bell is a jingle bell rather than
  a temple wind-bell clapper.
