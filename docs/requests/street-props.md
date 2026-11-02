# Requests from street-props

## ui
- Merge `data/i18n/requests/street-props.csv` (PROP_* display names, en + vi) into `data/i18n/strings.csv`.
  Item names already use the existing `ITEM_*` keys.

## world
- Props live in `assets/models/props/catalog.json` (108 entries). Lit props (`emissive: true` or `lights`) carry a
  `NightLight` controller that reads `TimeOfDay`; lights/materials are also in groups `prop_night_light` /
  mesh meta `night_emissive` if you prefer to drive them yourself (set `NightLight.enabled = false`).
- Hanging props (`origin: "hang_point"`: lanterns, bird cage, wind chime, lantern_string with ATTACH_01/02 ends 3.2 m apart)
  must be placed with their origin at the hook / cable point.
- `umbrella_tarp` meta `shelter_radius` (1.25 m) — please add an `Area3D` in group `shelter` when you place one.
- Knockable clutter (category `clutter`, stools, tea_set, slippers, boxes) is `dynamic` → RigidBody3D Pushable;
  place it on ledges/tables at cat height for the "knock it off" mischief.

## systems
- All `item_<id>.glb` meshes from items.json exist now (memory_01..12 share `item_memory_photo.glb`); the
  placeholder stand-ins in `PickupItem` can be retired (docs/placeholders.md row).

## world-life
- Done: handheld umbrella `res://assets/models/props/umbrella.glb` (navy) and `umbrella_red.glb` — origin at the
  hand grip, shaft along +Y, open canopy Ø 1.02 m with its top at y ≈ 0.86, strap loop hangs to y = -0.17.
  No colliders (safe to parent to a `BoneAttachment3D` on `hand_R`); catalog `kind: "handheld"`, meta `origin: "grip"`.
