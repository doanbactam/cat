# Mèo Cam: Phố Cũ — project contract

Open-city RPG: you are **Cam**, a young orange tabby street cat exploring a dense,
fictional Vietnamese-inspired old quarter ("Phố Cũ Hàng Mây"). Seamless switch between
**third-person** (orbit) and **first-person** (cat eye height ≈ 0.22 m) cameras.
Target: the most realistic, detailed result this toolchain can produce.

This is an ORIGINAL game. Do not copy any existing game's characters, story, UI, names,
levels or signature mechanics (in particular: no robots, drones, "Zurks", walled
cyber-cities, or anything from *Stray*). Brands/logos must be fictional.

## Toolchain (already installed — never reinstall)
| Tool | Path | Notes |
|---|---|---|
| Godot 4.7.2 stable | `/usr/local/bin/godot` | Forward+, Jolt physics. Class reference XML: `/opt/tools/godot-docs/doc/classes/<Class>.xml` — **grep it before using any API you are not 100 % sure exists in 4.7** |
| Blender 5.2.3 LTS | `/usr/local/bin/blender` | Python API; Cycles CPU for bakes/previews (EEVEE is ~50× slower here) |
| Software Vulkan | lavapipe via `tools/env.sh` | rendering works headless under Xvfb, slowly |
| Python 3.13 + numpy + Pillow | `python3` | texture/audio synthesis |

Skills for this repo (read the relevant SKILL.md before starting):
`.claude/skills/godot-dev/SKILL.md`, `.claude/skills/blender-assets/SKILL.md`,
`.claude/skills/visual-qa/SKILL.md`.

## Tools (always use these; they serialize Godot access with a lock)
- `tools/godot_import.sh` — headless import (run after adding/changing assets)
- `tools/validate.sh [dir] [path-filter]` — load every .gd/.tscn/.tres/.glb; non-zero exit on parse/load errors
- `tools/run_tests.sh [filter]` — runs `tests/test_*.gd` (see `tests/test_base.gd`)
- `tools/screenshot.sh scene=res://… out=/abs.png [frames=60] [cam=x,y,z look=x,y,z] [hour=17.5] [size=1600x900]`
- `tools/blender_run.sh blender/<area>/<script>.py [-- args]`
- Blender shared helpers: `blender/lib/common.py` (read it; lead-owned, do not edit)

Godot invocations MUST go through the tools above (or `tools/godot_lock.sh godot …`)
so concurrent agents never corrupt `.godot/`. Always pass `</dev/null` to raw godot runs.

## Git rules for agents
Agents never run `git add/commit/push/checkout/stash/reset`. The lead commits between phases.
Never delete or rewrite files outside your ownership area (table below). If you need a
change in someone else's file, write the request into `docs/requests/<your-area>.md`.

## Directory ownership (phase 1)
Tests: every area owns `tests/test_<area>*.gd` (e.g. `tests/test_player_jump.gd`). Docs: `docs/areas/<area>.md`.
| Area | Paths |
|---|---|
| `cat-asset` | `blender/cat/`, `blender/lib/cat_*.py`, `assets/models/cat/` |
| `city-houses` | `blender/city/`, `blender/lib/city_*.py`, `assets/models/city/`, `assets/textures/architecture/` |
| `city-landmarks` | `blender/landmarks/`, `blender/lib/landmarks_*.py`, `assets/models/landmarks/`, `assets/textures/landmarks/` |
| `street-props` | `blender/props/`, `blender/lib/props_*.py`, `assets/models/props/`, `assets/textures/props/` |
| `vehicles-nature` | `blender/nature/`, `blender/vehicles/`, `blender/lib/{nature,vehicles}_*.py`, `assets/models/{vehicles,nature}/`, `assets/textures/{vehicles,nature}/` |
| `creatures` | `blender/npc/`, `blender/lib/npc_*.py`, `assets/models/npc/` |
| `systems` | `scripts/autoload/{game_state,time_of_day,quest_manager,dialogue_manager}.gd`, `scripts/systems/`, `data/items/`, `data/skills/`, `data/quests/_schema.md`, `data/dialogue/_schema.md`, `tests/fixtures/` |
| `player` | `scripts/player/`, `scripts/camera/`, `scenes/player/`, `shaders/fur*`, `shaders/player_*`, `shaders/cat_sense*` |
| `ui` | `scripts/autoload/{settings,scene_loader}.gd`, `scripts/ui/`, `scenes/ui/`, `scenes/main/`, `assets/fonts/`, `assets/ui/`, `data/i18n/strings.csv` |
| `world` (layout+env) | `scripts/world/`, `scenes/world/`, `scenes/props/`, `shaders/` (except fur/player/cat_sense/npc), `assets/textures/ground/`, `assets/textures/decals/` |
| `world-life` (AI) | `scripts/npc/`, `scenes/npc/`, `shaders/npc_*` |
| `audio` | `tools/audio/`, `assets/audio/`, `scripts/autoload/audio_manager.gd`, `default_bus_layout.tres` |
| lead (contracts) | `CLAUDE.md`, `project.godot`, `scripts/autoload/game_events.gd`, `tools/*.sh`, `tools/*.gd`, `tests/test_base.gd`, `tests/run_tests.gd`, `tests/test_smoke.gd`, `blender/lib/common.py`, `docs/GDD.md` |

`project.godot` changes (new autoload, new setting) → ask via `docs/requests/`. Exception:
the `systems`/`ui`/`audio` owners may *implement* their pre-registered autoload files.
`scripts/autoload/game_events.gd` is append-only: any agent may ADD a signal (never rename/remove).

## Global conventions
- **Units**: metres, kilograms, seconds. Godot Y-up. Blender Z-up; glTF export converts.
- **Facing**: every asset's front faces Blender **-Y** → Godot **+Z** (`Vector3.MODEL_FRONT`).
  Gameplay code rotating a model to face direction `d` uses `Basis.looking_at(d, Vector3.UP, true)`.
- **Origins**: ground contact point (bottom centre) unless stated otherwise.
- **Collision**: Blender meshes named `*-colonly` (trimesh), `*-convcolonly` (convex) become
  colliders on import. Keep colliders simple (boxes/convex). Physics layers are named in
  `project.godot` (1 world, 2 player, 3 npc, 4 props_dynamic, 5 interactable, 6 climbable,
  7 water, 8 vehicles, 9 camera_blocker, 10 triggers).
- **Scale reference**: adult cat shoulder height 0.25 m, nose→tail-base 0.46 m, tail 0.28 m.
  Human 1.55–1.75 m. Door 2.1 m. Storey 3.3–3.6 m. Sidewalk curb 0.15 m.
- **Texel density**: architecture tiling sets ≥ 512 px/m; props ≥ 1024 px/m; cat 2048² over the body.
  Texture sizes power of two; ≤ 2048 except cat albedo may be 4096.
- **File budgets**: any single file < 40 MB; whole `assets/` < 600 MB. Prefer JPEG (q90) inside
  GLBs for albedo/ORM, PNG for normals.
- **GDScript**: Godot 4.7 syntax, static typing everywhere (`var x: float`, `-> void`),
  `class_name` only for genuinely shared types, tabs for indentation, `snake_case` files.
  No `@tool` unless needed. No editor-only APIs in runtime code. No plugins/addons downloads
  (everything is written here) unless the lead approves.
- **Scenes**: hand-written `.tscn` files must omit `uid=` on `ext_resource` (path only) — or build
  scenes from a script with `PackedScene.pack()` + `ResourceSaver.save()`.
- **UI text** goes through `tr("KEY")`; strings live in `data/i18n/strings.csv` (columns `keys,en,vi`).
  Vietnamese is the default language. Agents other than `ui` append their keys to
  `data/i18n/requests/<area>.csv` (same columns); `ui` merges them.
- **No placeholders shipped as final**: a placeholder is allowed only while the real asset is being
  built in the same phase, and must be logged in `docs/placeholders.md`.

## Runtime contracts

### Autoloads (singletons, registered in project.godot)
| Name | Owner | Key API (must exist) |
|---|---|---|
| `GameEvents` | lead | signal bus — see `scripts/autoload/game_events.gd` |
| `Settings` | ui | `get_value(section: String, key: String, default = null)`, `set_value(section, key, value)`, `save()`, `apply_all()`; keys listed below |
| `GameState` | systems | stats/attributes/xp/inventory/flags/save — see "GameState" below |
| `TimeOfDay` | systems | `hour: float` (0–24), `day: int`, `time_scale: float` (game-min per real-sec, default 1.0 ⇒ 24 min/day), `paused: bool`, `set_hour(h)`, `get_phase() -> StringName`, `get_sun_progress() -> float`; emits `GameEvents.time_tick`, `phase_of_day_changed` |
| `QuestManager` | systems | `start_quest(id)`, `is_active(id)`, `is_completed(id)`, `report(event: StringName, data: Dictionary)`, `get_tracked() -> StringName`, `get_quest(id) -> Dictionary`, `get_tracked_target_position() -> Vector3` (`Vector3.INF` if none; resolves objective targets via nodes in group `"quest_target"` with metadata `target_id`) |
| `DialogueManager` | systems | `start(dialogue_id: StringName, speaker: Node = null)`, `choose(index: int)`, `advance()`, `is_active() -> bool` |
| `AudioManager` | audio | `play_sfx(name: StringName, pos: Vector3 = Vector3.INF, volume_db := 0.0, pitch_jitter := 0.05) -> void`, `play_ui(name)`, `play_footstep(surface: StringName, pos: Vector3, intensity: float)`, `set_ambience(name: StringName, fade := 2.0)`, `play_music(name: StringName, fade := 2.0)`, `stop_music(fade := 2.0)` — unknown names must be a silent no-op (warn once) |
| `SceneLoader` | ui | `change_scene(path: String, show_loading := true)`, `reload_current()`; threaded load with progress screen |

### Settings keys (section/key → default)
`graphics/quality` "high" (low|medium|high|ultra), `graphics/fullscreen` false, `graphics/vsync` true,
`graphics/max_fps` 0, `graphics/render_scale` 1.0, `graphics/upscaler` "fsr2" (off|fsr|fsr2),
`graphics/fov` 75.0, `graphics/sdfgi` true, `graphics/ssr` true, `graphics/ssao` true, `graphics/ssil` false,
`graphics/volumetric_fog` true, `graphics/fur_shells` 24, `graphics/shadow_quality` "high",
`graphics/motion_blur` false, `controls/mouse_sensitivity` 0.25, `controls/invert_y` false,
`controls/gamepad_sensitivity` 3.0, `camera/default_mode` "third_person", `camera/head_bob` 1.0,
`audio/master` 1.0, `audio/music` 0.7, `audio/sfx` 1.0, `audio/ambience` 0.9, `audio/ui` 0.8,
`gameplay/language` "vi", `gameplay/subtitles` true, `gameplay/hints` true.
Any system that depends on a setting listens to `GameEvents.settings_changed(section)`.
World-environment nodes in group `"graphics_settings_listener"` get `apply_graphics_settings()` called.

### GameState (owner: systems)
- Vital stats (0..max): `health` (100), `hunger` (100 = full), `energy` (100), `warmth` (100, drops in rain).
  `get_stat(name) -> float`, `get_stat_max(name)`, `modify_stat(name, delta)` → emits `stat_changed`.
- Attributes (int 1..10): `agility`, `stealth`, `charm`, `hunting`. `get_attribute(name) -> int`.
- Progress: `xp`, `level`, `skill_points`; `add_xp(amount, reason)`; skills from `data/skills/skills.json`;
  `has_skill(id) -> bool`, `unlock_skill(id) -> bool`.
- Inventory: `add_item(id, n := 1)`, `remove_item(id, n := 1) -> bool`, `has_item(id, n := 1)`, `item_count(id)`;
  items from `data/items/items.json`. A cat carries ONE item in its mouth: `mouth_item: StringName`
  (`&""` = empty), `set_mouth_item(id)`; other items are "stashed" collectibles/currency (bottle caps `cap`).
- Flags: `set_flag(name, value := true)`, `get_flag(name, default = false)`.
- Locations/collectibles: `discover_location(id, display_name)`, `mark_collectible(id)`.
- Save/load: `save_game(slot := 0) -> bool`, `load_game(slot := 0) -> bool`, `has_save(slot)`, `new_game()`;
  JSON at `user://saves/slot_<n>.json`; includes player transform (`player_transform`), time, weather, quests.
  Other systems register save providers: `register_save_provider(key: String, obj: Object)` where obj has
  `get_save_data() -> Dictionary` and `load_save_data(d: Dictionary)`.

### Player (owner: player)
- Scene `res://scenes/player/cat_player.tscn`, root `CatPlayer` (`CharacterBody3D`, script
  `scripts/player/cat_player.gd`, `class_name CatPlayer`, group `"player"`).
- Collision: layer 2 (player); mask 1|4|6|7|8.
- Public API: `set_input_enabled(enabled: bool)`, `teleport(xform: Transform3D)`,
  `get_camera_rig() -> Node3D`, `get_camera() -> Camera3D`, `get_mouth_attachment() -> Node3D`,
  `get_state() -> StringName`, `is_first_person() -> bool`, `set_camera_mode(mode: StringName)`.
- Interaction: the player raycasts/area-scans for nodes in group `"interactable"` and calls the
  Interactable API below; emits `GameEvents.interactable_focused/unfocused/interacted`.
- Emits `player_noise(pos, loudness)` on landings, sprinting, meows, knocking props.
- The cat visual is `assets/models/cat/cat.glb` (see Cat asset contract). Fur via shell shader
  (`shaders/fur_shell.gdshader`), shell count from `graphics/fur_shells`.

### Interactable API (owner: systems; base classes in `scripts/systems/`)
Base `class_name Interactable extends Area3D` (collision layer 5 "interactable"), in group `"interactable"`:
`get_prompt(player: Node) -> String` (already translated), `can_interact(player: Node) -> bool`,
`interact(player: Node) -> void`, `@export var verb: StringName = &"interact"`,
`@export var interact_distance := 1.2`, `@export var highlight_target: NodePath` (mesh outlined by cat-sense).
Subclasses provided by systems: `PickupItem` (item_id, amount, goes to mouth or stash),
`Talkable` (dialogue_id, speaker_id), `NapSpot` (restores energy, advances time), `FoodSource`
(restores hunger), `ScratchPost`, `TerritorySpot` (scent-marking), `QuestTrigger` (reports to QuestManager),
`Pushable` (cat can knock it off ledges: RigidBody3D helper).

### Data formats (owner: systems documents them in `data/quests/_schema.md`)
- `data/items/items.json` — `{ "<id>": {"name_key": "ITEM_FISH", "desc_key": "...", "icon": "res://…",
  "mouth": true, "stack": 1, "food": 25, "mesh": "res://…glb"} }`
- `data/skills/skills.json`, `data/quests/<quest_id>.json`, `data/dialogue/<dialogue_id>.json`.

### World (owner: world)
- Playable world scene `res://scenes/world/city.tscn` (root `City`, Node3D). Must contain:
  `WorldEnvironment`, `Sun` (DirectionalLight3D), `Moon`, a `WeatherSystem` node (group `"weather"`,
  `set_weather(kind: StringName, intensity: float)`, `get_weather() -> StringName`),
  `PlayerSpawn` (Marker3D, group `"player_spawn"`), and named location markers
  (`Marker3D` in group `"location"`, metadata `location_id`, `display_name_key`).
- Surface types for footsteps/fur-wetness: physics material or metadata `surface` on colliders:
  `&"asphalt"`, `&"concrete"`, `&"tile"`, `&"wood"`, `&"metal"`, `&"grass"`, `&"dirt"`, `&"water"`,
  `&"roof_tile"`, `&"fabric"`, `&"plastic"`. Query helper: `scripts/world/surface.gd` (`static func get_surface(collider: Object) -> StringName`).
- The game scene (`scenes/main/game.tscn`, built in phase 2) instances city + player + HUD + `scenes/npc/life_director.tscn`.
- **Marker conventions** (placed by `world` in city.tscn, consumed by `world-life`/quests):
  `Path3D` group `"traffic_lane"` (meta `vehicle_kinds: PackedStringArray`, `speed_limit: float`);
  `Path3D` group `"patrol_path"` (meta `npc_id`); `Marker3D` group `"npc_spawn"` (meta `npc_kind`:
  pedestrian|vendor|cat|dog|crow|pigeon_flock|mouse|koi, `npc_id` e.g. `ba_tu`, `mun`, `bong`, `muop`, `lao_qua`,
  `ven`, `co_hoa`, `chu_sau`, `bin`, `xam`); `Marker3D` group `"pedestrian_poi"` (meta `activity`: sit|shop|chat|wait|look);
  `Marker3D` group `"quest_target"` (meta `target_id`); `NavigationRegion3D` named `NavRegion` (group `"nav_region"`)
  covering streets/sidewalks/courtyards; `Area3D` group `"shelter"` (dry under awnings — rain doesn't wet the cat).
- Global shader parameters (declared in `project.godot [shader_globals]`; use `global uniform float wetness;` in shaders,
  set with `RenderingServer.global_shader_parameter_set`): `wetness` (0..1, world), `night_factor` (0..1, world),
  `wind_strength`, `wind_direction` (vec3, world), `player_position` (vec3, player), `cat_sense` (0..1, player).
  Imported GLB materials are StandardMaterial3D and cannot read globals — `world` handles wetness for them by
  modulating unique materials' roughness/albedo at runtime.

## Asset contracts (Blender → Godot)

### Cat (`assets/models/cat/cat.glb`, owner cat-asset)
- Nodes: armature `CatRig` (Skeleton3D in Godot), skinned meshes `CatBody` (UV'd, 25–45 k tris),
  `CatEyes` (2 eyeballs, separate cornea/iris material), `CatWhiskers` (alpha-clipped strips), optional `CatClaws`.
- Real-world size per scale reference. Origin on the ground between all four paws; faces -Y in Blender.
- Required bone names (more allowed): `root`, `pelvis`, `spine_01`, `spine_02`, `spine_03`, `chest`,
  `neck`, `head`, `jaw`, `ear_L`, `ear_R`, `eyelid_L`, `eyelid_R`, `tail_01`…`tail_06`,
  `upperarm_L/R`, `forearm_L/R`, `hand_L/R` (front paws), `thigh_L/R`, `shin_L/R`, `foot_L/R`, `toe_L/R` (hind).
- Required in-place animations (no root motion), exact names; loop ones marked (L):
  `idle`(L), `idle_look`(L), `walk`(L), `trot`(L), `run`(L), `sneak`(L), `sneak_idle`(L), `jump_crouch`,
  `jump_up`, `fall`(L), `land`, `land_hard`, `sit_down`, `sit_idle`(L), `stand_up`, `lie_down`, `sleep`(L),
  `groom`(L), `meow`, `hiss`, `swipe`, `scratch`(L), `climb`(L), `turn_left_90`, `turn_right_90`,
  `drink`(L), `eat`(L), `knead`(L), `stretch`, `balance_walk`(L), `pickup`, `knock`.
  Gait speeds (m/s) the anims are authored for: walk 0.7, trot 1.6, run 4.5, sneak 0.45.
- Textures: tabby albedo 2048–4096 (orange mackerel/classic tabby with cream chin/chest),
  normal, roughness, plus `assets/models/cat/textures/cat_fur_mask.png` (R = fur length 0..1,
  G = fur density, B = stripe/pattern mask) for the shell shader. Variant albedos for NPC cats:
  `cat_albedo_black.png`, `cat_albedo_white.png`, `cat_albedo_calico.png`, `cat_albedo_grey_tabby.png`.

### Architecture (`assets/models/city/`, owner city-arch)
- Each module = one `.glb`, front facade toward -Y (Blender), origin at the **front facade
  bottom-centre** at sidewalk level. Width along X, depth extends behind the facade (Blender +Y → Godot -Z).
- `assets/models/city/catalog.json` lists every module:
  `{"id": "...", "file": "res://assets/models/city/x.glb", "kind": "house|shop|corner|landmark|alley|roof_prop|wall",
    "width": 4.0, "depth": 12.0, "height": 13.6, "floors": 4, "style": "colonial|tube90s|modern|old_tile|temple|market",
    "climb_points": [[x,y,z], …], "nap_spots": [[x,y,z], …], "entrances": [[x,y,z], …]}`
  (coordinates in Godot space relative to origin: x right, y up, z toward street = +Z).
- Rooftops, balconies, AC units, awnings, window ledges must have accurate colliders so the cat
  can traverse them (this is the core gameplay space).

### Landmarks / props / vehicles / nature / creatures
- Catalogs (same shape as the city catalog, plus prop fields): `assets/models/landmarks/catalog.json`,
  `assets/models/props/catalog.json`, `assets/models/vehicles/catalog.json`, `assets/models/nature/catalog.json`.
- One `.glb` per prop under its folder; catalog `assets/models/props/catalog.json` (same shape:
  `id, file, kind, footprint, height, dynamic(bool), mass, surface`). Dynamic (knockable) props
  have a `-convcolonly` collider and metadata `mass`.
- NPC models: `assets/models/npc/<name>.glb` with `Armature`/Skeleton3D and named animations
  (humans: `idle`, `walk`, `sit`, `talk`, `sell`, `pet_cat`, `shoo`; birds: `idle`, `peck`, `walk`, `fly`, `takeoff`, `land`;
  dog: `idle`, `walk`, `run`, `bark`, `sleep`; mouse: `idle`, `run`; fish: `swim`).

## Definition of done (every agent)
1. Your outputs exist at the contracted paths; `tools/validate.sh` passes; your tests pass.
2. Visual work: you rendered previews/screenshots, LOOKED at them (Read the PNG), and iterated
   at least twice on what looked wrong. Keep final previews in `qa/out/<area>/` (git-ignored)
   and copy 1–3 best ones to `docs/gallery/<area>_*.png` (≤ 1 MB each, JPEG/PNG).
3. Write `docs/areas/<area>.md`: what you built, how to regenerate, API, known gaps (be honest).
