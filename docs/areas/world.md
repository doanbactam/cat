# world — Hàng Mây layout, ground, water, lighting, sky, day/night, weather

Owner area `world`: `scripts/world/`, `scenes/world/`, `scenes/props/`, `shaders/` (except
fur/player/cat_sense/npc), `assets/textures/ground/`, `assets/textures/decals/`, `tests/test_world*.gd`.

The playable quarter `res://scenes/world/city.tscn` (root `City`, `scripts/world/city.gd`) is **generated**:
`scripts/world/tools/build_city.gd` runs `CityBuilder` over the five asset catalogs and saves the scene.
Never hand-edit `city.tscn`; change the builder / layout tables and rebuild.

## How to regenerate
```bash
python3 scripts/world/tools/gen_ground_textures.py [--only asphalt,pavers] [--sheet]   # ground PBR + decals (~1 min)
tools/godot_import.sh                                                                  # after texture/asset changes
tools/godot_lock.sh godot --headless --path . --script res://scripts/world/tools/build_city.gd </dev/null
#   options after `--`: no_nav (skip navmesh bake), no_post (skip rooftop/cable pass); ~15 s + lock wait
tools/run_tests.sh test_world.gd                                                       # 9 tests
scripts/world/tools/qa_shots.sh $PWD/qa/out/world/rN [only=street_tpp,rain] [frames=20] [size=800x450]
```
`build_city.gd` writes `qa/out/world/build_report.json` (counts, placeholders, rooftop-network report) and
`scenes/world/city_navmesh.res`, plus binary meshes/shapes under `scenes/world/generated/` (so the
.tscn stays ~17 MB). The build is deterministic (seeded RNG, seeded shuffles); re-running it after other
areas change their catalogs picks up new/changed assets automatically (entries whose file does not exist
yet are skipped).

## What is built (generator files)
| File | Role |
|---|---|
| `city_layout.gd` | **Map data** (≈240 × 210 m, +X east, −Z north): 4 streets with widths/speed limits/vehicle kinds, the lake ellipse + islet, alleys (hẻm A 2.2 m, hẻm B 2 m, ngõ C 1.2 m), tower court, temple garden, market hall/stall lanes, 16 building rows (style weights, gaps, corner flags, rooftop-network flag), wall runs, 17 named locations, forced landmark modules per row (`ROW_RESERVED`: Bông's café). |
| `city_builder.gd` | Stage 1: environment nodes, ground meshes, lake, building rows, landmarks, nature, street furniture, festival lanterns, decals, markers, interactables, knockables, zones/shelters, reflection probes, occluders. |
| `city_builder_post.gd` | Stage 2 (physics in tree): ray-measures 10 k rooftop samples, links the rooftop network (gap ≤ 2.0 m, step ≤ 1.5 m rule) with crate stairs, planks, climbable pipes and walkable cable bundles, decorative cable spans between poles/facades, Mun's rooftop patrol, snaps knockables onto real table/wall tops, bakes `NavRegion`. |
| `city_structures.gd`, `tree_gen.gd`, `mesh_util.gd`, `world_materials.gd` | procedural geometry kit (walls, planks, crates, cables, lantern strings, carts …) and materials; procedural landmark/tree builders are **fallbacks only** when a catalog asset is missing. |
| `knockable_factory.gd` | lathe-turned knockable props (`scenes/props/knock_{cup,glass,can,bowl,pot,bottle}.tscn`, `Pushable` roots). |
| `city.gd` | runtime root: merges per-box asset colliders before Jolt sees them (body count), applies size-based visibility ranges, QA hooks (`qa_rain/qa_storm/qa_fog/qa_festival/qa_perf`). |
| `world_environment.gd` | day/night: Sun/Moon orientation from hour (Hanoi-ish solar path, south tilt), Kelvin colour curve, intensity, exposure, sky shader params, fog / volumetric fog humid haze, `night_factor` global; `apply_graphics_settings()` (group `graphics_settings_listener`). |
| `weather_system.gd` | `WeatherSystem` (group `weather`). |
| `night_lights.gd` | street lamps / landmark lights / lit materials / festival lanterns vs. `night_factor`. |
| `surface.gd` | `static get_surface(collider) -> StringName` (meta `surface` on the collider or a parent, normalised to the 11 contract names). |
| `area_zone.gd` | `Area3D` zones that emit `GameEvents.area_entered(area_id)` + reverb buses. |

### Layout (GDD map)
- **Phố Hàng Mây** (north, E–W, 8 m road): continuous north row (52 modules, heart of the rooftop
  network), south side split into the maze segment (hẻm A mouth), lake segment and market segment that
  ends in **Bông's café** (`cafe_bong`, forced into the row at the Phố Chợ corner).
- **Grandma Tư's tea stall** (`quan_tra_ba_tu`) leans on the facade right beside hẻm A's mouth; Cam's
  rooftop nap spot (PlayerSpawn) is on the roof above it.
- **West alley maze**: hẻm A (2.2 m, N–S), hẻm B (2 m, E–W), ngõ C (1.2 m) into the water-tower court;
  rows on both sides of every alley are rooftop-network rows.
- **Hồ Gương** (ellipse 72 × 60 m): landmark kit embankment laid as 52 × 4 m chords (water y −1.0,
  walkway 0, bed −1.6…−2.7), 3 water-step landings, railings, promenade lamps + benches, brick promenade
  ring, park lawn with flame/sao trees, palms and weeping willows, lotus & water-hyacinth patches,
  the **islet shrine** + **red bridge** to the east shore, the **old banyan** on the south lawn (Lão Quạ).
- **Phố Đình** (south): `dinh_hang_may` complex (gate on the street, courtyard banyan in the kit planter,
  bell pavilion, burner, hall with the crow nest on the ridge) inside a walled 68 × 41 m temple garden
  (frangipani, areca/coconut palms, bamboo, hedges, bougainvillea).
- **Market quarter** (east): `cho_market_hall` facing Phố Chợ, 18 `cho_stall_lane` rows (incl. the
  fish lane under the `cho_gate_arch`), crates/sacks/basins, umbrella vendors (with shelters), scooter rows.
- Block interiors are closed by module backs + wall runs; map edges have wall runs and invisible bounds.

### Rooftop network (core traversal)
Post pass rule check: horizontal gap ≤ 2.0 m, step-up ≤ 1.5 m, otherwise a connector is added (crate
stairs for steps, planks for alley gaps, walkable cable bundles across streets — `StaticBody3D`
on layer 1, group `balance_cable`, meta `balance = true`, thin capsule colliders). Last build:
net coverage 9 % → **100 %** of rooftop-network modules in one connected component
(`build_report.json → post.net_coverage_after`), ~28 crate stairs, ~36 planks, 8 walkable cables,
an 8.8 m cable to the water-tower catwalk.

### Ground & decals
Generated textures (`gen_ground_textures.py`, numpy/Pillow, tileable, 1024², ≥ 512 px/m): asphalt
(patches, cracks, oil), Hanoi square pavers (some broken/missing), granite curb, alley concrete with moss,
courtyard brick, grass, lake bed, stone embankment, wood deck, bark/leaf atlas, noise. Ground shader
`shaders/ground.gdshader` (macro variation, wetness darkening/roughness, puddles in low spots with
rain ripples). Roads 0.15 m below sidewalks with granite curbs, gutters, drain grates, manholes, tree
pits. ~560 decals: cracks (with normals), oil stains, tyre marks, worn lane paint, leaves, damp/rust/
food stains, posters (fictional Vietnamese texts), chalk hopscotch, puddles (weather-driven).

### Water
`shaders/water_lake.gdshader`: opaque jade-green murky lake (deliberately opaque so SSR, reflection
probes and SDFGI all work on it), analytic basin depth colour, 3 scrolling normal layers + wind gust
patches, rain-drop ripple rings while it rains (`rain` param from WeatherSystem), shore scum/foam band,
tiny vertex swell. Water volume: `Area3D` `LakeVolume` on layer 7, group `water`, meta `water_level = -1.0`
(player contract). Small puddles: ground-shader puddles + puddle decals that fade in with wetness.

### Overhead power lines
Catenary cable bundles (2–6 wires, sag by span) between electric poles and facade anchors with
insulator/anchor meshes (`Cables` group, 90 decorative spans), plus walkable bundles (above).

### Lighting, sky, atmosphere
Sun + Moon `DirectionalLight3D`s driven every frame from `TimeOfDay.hour` (sunrise ≈ 5:50, sunset ≈ 18:06,
max elevation 75°, azimuth east→west tilted south), colour temperature 1900 K (horizon) → 5900 K,
moon phase from TimeOfDay. Custom sky shader `shaders/sky_hangmay.gdshader`: gradient + Mie halo, sun
disc, moon with phase, twinkling stars + faint galactic band, 2 cloud layers (coverage/overcast from
weather), humid horizon haze, warm light-pollution glow at night, lightning flash. Environment: AgX,
SDFGI (5 cascades), SSAO, SSR, SSIL optional, glow, exponential fog with aerial perspective, volumetric
fog (humid haze, denser at golden hour/night/fog weather), adjustments. 7 box-projected
`ReflectionProbe`s (main street ×2, hẻm A, lake, market, temple, temple street).
`NightLights`: street lamps (staggered switch-on with `night_factor`, nearest 4 cast shadows), landmark
kit lights (`landmark_night_light`, meta `night_energy`), lit `lit_*` materials (shop signs, windows
switch on per-material at different times), festival lanterns (strings over both main streets + temple
garden) shown when `GameState` flag `festival_active`/`festival_forced` or `TimeOfDay.is_festival_night()`.
**Graphics settings** (`apply_graphics_settings`, also on `GameEvents.settings_changed("graphics")`):
`sdfgi`, `ssr`, `ssao`, `ssil`, `volumetric_fog`, `quality` (SDFGI cascades, SSR steps, visibility-range
multiplier), `shadow_quality` (shadow distance / atlas / splits).

### Weather (`WeatherSystem`, group `weather`)
API: `set_weather(kind: StringName, intensity: float)`, `get_weather() -> StringName`,
`get_intensity() -> float`, `get_wetness() -> float`, `get_rain_amount()`, `set_weather_immediate(kind,
intensity, wetness := -1)`, `snap()`, `trigger_lightning(distance := -1)`; export `auto_weather`
(re-rolls every 4 game hours, deterministic per day; festival nights stay dry; GameState flag
`weather_locked` stops it). Kinds `clear cloudy rain storm fog`, smooth transitions (`transition_time`).
Drives: rain `GPUParticles3D` streaks following the camera with a `GPUParticlesCollisionHeightField3D`
(no rain under roofs/awnings) + splash particles, lightning flashes (sky + ambient) with delayed thunder
via `AudioManager.play_sfx(&"thunder_near"/&"thunder_far")`, `wetness` global ramp (soak 60 s, dry
240 s), runtime wet modulation of every imported `StandardMaterial3D` (albedo × ~0.6, roughness down on
up-facing materials; restored on exit), puddle decals, lake rain ripples, `wind_strength`/`wind_direction`
globals (gusts; storms > 1). Emits `GameEvents.weather_changed`.

### Gameplay markers & interactables (CLAUDE.md conventions)
- `PlayerSpawn` (group `player_spawn`) on Cam's rooftop nap spot above the tea stall (ray-verified).
- 17 `location` markers (`location_id`, `display_name_key`, `radius`), incl. story ids `tea_stall banyan
  water_tower temple_roof riddle_bridge riddle_bell riddle_sun`.
- `npc_spawn`: ba_tu (tea stall `MARKER_grandma`), mun (rooftops), bong (café cushion), muop (temple hall,
  `dialogue_id ong_muop`), lao_qua (lake banyan branch), ven (market), co_hoa (`MARKER_fish_stall`),
  chu_sau (bánh mì cart), bin, xam (pigeon flock on the islet) + 26 pedestrians, 5 pigeon flocks, 6 koi
  (on the water surface with `volume_size`), 6 mice, 4 cats, 3 crows.
- `patrol_path` `ven` through the market aisles; Mun's rooftop path; 8 `traffic_lane` Path3Ds (one per
  direction per street, `vehicle_kinds`, `speed_limit`, `street_id`); 20 `pedestrian_poi`.
- `quest_target`: tea_stall, temple_roof, water_tower, race_finish, banyan, cafe, market, fish_street,
  islet_shrine, bell, + kit markers (`crow_nest`, `fish_stall`) + every interactable's `target_id`
  (stall_counter, bins_key_spot, leg_band_spot, postman_bag, race_start …).
- `shelter` Area3Ds: front strip of every shop module, banyan crowns, market umbrellas, + kit SHELTER zones.
- `NavRegion` (group `nav_region`): baked from ground/landmark colliders (agent radius 0.25, max climb 0.25),
  ~5.4 k polygons, streets + sidewalks + plazas + courtyards + promenade, water excluded.
- Zones (`area_zone.gd`): street/maze/lake/market/temple/rooftop ids for audio ambience; reverb `Alley`,
  `Market`, `Temple`.
- Interactables (systems classes): 8 `NapSpot` (incl. `muop_secret_nap` on the temple shed roof),
  10 `TerritorySpot`, 12 memory `Collectible`s, 30 cap stashes (`auto_collect_on_touch`), food/water
  (Grandma's bowl, cô Hoa's fish counter `is_stealing`, bánh mì crumbs, market scraps, lake steps,
  temple basin), `ScratchPost`s (both banyans, café rattan, tea-stall leg), sniff `stall_counter`,
  crow-nest pickups (festival-locked), key / leg band / letter pickups, race & temple-roof triggers,
  25 knockables on tables, wall copings and rooftop parapets (ray-snapped to the real surfaces).

## Performance
- Repeated small vegetation (weeds, moss, tufts, leaf litter: ~1.3 k instances) → `MultiMeshInstance3D`
  with visibility ranges; decals fade at 45–55 m.
- `city.gd` gives every instanced asset mesh a size-based `visibility_range_end` (< 0.6 m → 32 m,
  < 1.6 m → 55 m, < 4 m → 95 m, < 9 m → 170 m; × quality multiplier).
- Per-module `BoxOccluder3D`s (needs project setting `occlusion_culling/use_occlusion_culling`, requested
  from the lead), per-instance collider merging (Jolt body count), only 4 lamp shadows at a time.
- Measured (lavapipe, 800×450, see `qa/out/world/perf.txt`): see the table at the end of this file.

## Known gaps (honest)
- Water tower is still the procedural stand-in (no landmarks asset; logged in docs/placeholders.md).
- The lake water is opaque (murky by design, keeps SSR/SDFGI) — there is no screen-texture refraction;
  the bed is only visible as depth colour.
- The ellipse embankment is made of straight 4 m kit chords: behind the coping, adjacent pieces fan
  apart by up to ~0.35 m (covered by the promenade brick at −5 mm, visible only from above).
- Rooftop jumpability is verified by ray sampling + rules, not by simulating the player controller.
- Lavapipe makes every capture slow (≈1 fps); final look on real GPUs (SDFGI/volumetrics) is untested.
