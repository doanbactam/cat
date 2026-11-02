# Requests from world-life

## lead
- **Placeholders** (please add to `docs/placeholders.md`; world-life may not edit it):
  | Path | Owner | Replaced by |
  |---|---|---|
  | Procedural stand-in rigs for humans, Vện, pigeons/crows/sparrows, mice, geckos (`scripts/npc/standin_builder.gd` + `proc_animator.gd`, used only when no GLB exists) | world-life (code) / creatures (meshes) | `assets/models/npc/<name>.glb` — names below |
  | Procedural stand-in motorbike / bicycle / car with riders (same files) | world-life / vehicles-nature | `assets/models/vehicles/<name>.glb` — names below |
  | Procedural koi mesh (`koi_school.gd::_fish_mesh`, shaded by `shaders/npc_koi.gdshader`) | world-life / creatures | `assets/models/npc/koi.glb` (optional — the shader koi already look right) |
- `scenes/main/game.tscn` (phase 2): instance `res://scenes/npc/life_director.tscn` as a child of the game root
  (it scans the whole tree for markers, so its position in the tree does not matter).

## creatures (assets/models/npc/)
NpcVisual (`scripts/npc/npc_visual.gd`) loads the first existing file, otherwise the stand-in:
| Who | File names tried (in order) | Clips used (fallbacks exist) |
|---|---|---|
| Bà Tư / Cô Hoa / Chú Sáu / Bin | `ba_tu.glb` → `human_elder_woman`, `co_hoa` → `human_vendor_woman`, `chu_sau` → `human_vendor_man`, `bin` → `human_kid` | idle walk sit talk sell pet_cat shoo (+ optional run, wave, squat) |
| Ambient pedestrians | any `human_*.glb` / `pedestrian_*.glb` (picked per NPC, deterministic) | same |
| Vện | `ven.glb` → `dog.glb` → `dog_*.glb` | idle walk run bark sleep (+ optional sit) |
| Pigeons / Xám | `pigeon.glb` → `pigeon_*.glb` | idle peck walk fly takeoff land |
| Crows / Lão Quạ | `lao_qua.glb` → `crow.glb` → `crow_*.glb` | idle peck fly takeoff land (+ optional caw) |
| Sparrows | `sparrow.glb` | idle peck fly land |
| Mice | `mouse.glb` | idle run |
| Gecko | `gecko.glb` | idle walk (crawl) |
| Koi | `koi.glb` | swim |
Front +Z (Blender −Y), origin at ground contact (birds: feet), real scale. Animations in place.

## vehicles-nature (assets/models/vehicles/)
- Names tried: `motorbike.glb`/`scooter.glb`/`motorbike_*.glb`, `bicycle.glb`/`bicycle_*.glb`, `car.glb`/`taxi.glb`/`car_*.glb`.
- Wheels: please name wheel nodes `Wheel*` (one node per wheel, origin at the hub, rotating around local X) — they
  are spun from the distance travelled. Riders may be baked in or omitted (stand-in riders are not added to GLBs).
- Optional handheld umbrella prop `assets/models/props/umbrella.glb` (handle at origin, shaft +Y) — used by
  pedestrians in the rain (stand-in canopy otherwise).

## world (scenes/world/city.tscn)
LifeDirector consumes exactly the CLAUDE.md marker conventions, plus these optional extras:
- `npc_spawn` kinds also accepted: `vendor` (same as pedestrian with npc_id), `sparrows` (meta `wire_end`
  Vector3 marker-local end of the wire, `sag` m, `count`), `pigeon` (= pigeon_flock).
- Optional metas: `count` (flocks/koi/sparrows), `radius` (flock ground radius), `perch_points` (Array[Vector3] world
  positions for pigeons/crows), `roam_radius` (cats/mice/Bin), `work_hours` (Vector2 for vendors),
  `day_active` (mice), `snap_to_surface` (crow marker raycasts down onto the roof), `dialogue_id` (override).
- `koi` marker: put it ON the water surface; meta `volume_size` Vector3 (x, depth, z) of the swim box below it.
- Lão Quạ's marker (`npc_kind crow`, `npc_id lao_qua`) sits on his banyan branch (exact perch height).
- NPC ids used: ba_tu, co_hoa, chu_sau, bin (pedestrian/vendor), ven (dog), mun, bong, muop (cat — Mướp talks with
  dialogue `ong_muop`), lao_qua (crow), xam (pigeon_flock marker → Xám joins that flock).
  `patrol_path` with `npc_id ven` = Vện's route; with `npc_id bin` = Bin's roaming points.
- Street lamps: put the `OmniLight3D`/`SpotLight3D` of lamps in group `street_light` (geckos gather there at night).
- Sun: DirectionalLight3D named `Sun` (or in group `sun`) — NPC cats look for sunny nap spots.
- NavRegion: bake with agent_radius 0.25, agent_max_climb ≥ 0.2 (curbs), include sidewalks, plazas, courtyards and
  road surface (pedestrians cross), exclude water.

## player
- Please add `CatPlayer.apply_knockback(impulse: Vector3) -> void` (vehicle bumps and Vện's nip use it; until
  then world-life adds the impulse to `velocity` directly, which the ground controller damps quickly).
- `is_airborne()`, `is_sneaking()`, `get_state()` are read by NPC perception — keep them.
