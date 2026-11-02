# Requests from `world`

## lead (project.godot)
1. **Occlusion culling is off.** `city.tscn` ships ~240 `OccluderInstance3D` boxes (one per building
   module) but they do nothing until `[rendering] occlusion_culling/use_occlusion_culling=true` is set.
   Street-level views draw 2.5–5 k draw calls without it; please enable it.
2. Optional: `rendering/mesh_lod/lod_change/threshold_pixels` stays default (1.0) — fine.
3. `scenes/main/game.tscn` (phase 2): instance `res://scenes/world/city.tscn`; place the player at
   `city.get_spawn_transform()` (PlayerSpawn = Cam's rooftop nap spot above the tea stall).

## city-landmarks
- A **water tower** asset (`id` containing `water_tower`, e.g. a riveted steel tank on a 4-leg lattice,
  catwalk with railing at ~13.6 m, ladder = climb points, meta/marker `catwalk_y`) would replace the last
  procedural stand-in (`city_structures.gd::make_water_tower`, logged in docs/placeholders.md). The
  builder picks it up automatically (`_landmark(["water_tower", "thap_nuoc"], …)`), origin = ground centre.

## ui
- Location keys used by markers (all already in `strings.csv`): `LOC_TEA_STALL LOC_MAIN_STREET LOC_CAFE
  LOC_WEST_ALLEYS LOC_ROOFTOPS LOC_WATER_TOWER LOC_LAKE LOC_BANYAN LOC_BRIDGE LOC_ISLET_SHRINE LOC_MARKET
  LOC_FISH_STREET LOC_TEMPLE_STREET LOC_TEMPLE LOC_TEMPLE_ROOF LOC_BELL_PAVILION LOC_SUN_STEPS`.

## world-life
- `npc_spawn` for Mướp now uses `npc_id = "muop"` (contract id) with meta `dialogue_id = "ong_muop"`.
- Xám's pigeon flock marker sits on the islet (`MARKER_pigeons` of `ho_islet_shrine`), meta `count`, `radius`.
- Lamps: every street lamp and landmark night light is put in group `street_light` at runtime by
  `NightLights` (geckos).
