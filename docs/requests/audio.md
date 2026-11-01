# Requests from area: audio

## 1. (lead / cat-asset) Godot headless import is blocked by `.blend` files under `qa/out/cat-asset/cache/`
`tools/godot_import.sh` currently imports **nothing**: the scan reaches
`qa/out/cat-asset/cache/stage_*.blend`, the glTF-Blender importer errors in headless mode
(`Blender path is invalid or not set ... editor_scene_importer_blend.cpp:552`) and the editor exits without
running the reimport step. Every new asset of every area stays unimported (no `.import` files).
Fix (any one): `touch qa/out/cat-asset/.gdignore` (cat-asset; audio/systems/city-houses already ignore their
qa dirs), or a lead-owned `qa/.gdignore` (qa/out is never game content), or set
`filesystem/import/blender/enabled=false` in `project.godot`.

## 2. (player) Footsteps / landings / meows
AudioManager plays landing (`player_landed`), jump effort (`player_jumped`) and meow (`player_meowed`) sounds
**automatically** — do not also call `play_sfx` for those. Footsteps are NOT automatic: call
`AudioManager.play_footstep(surface, foot_world_pos, intensity)` from gait/anim events
(intensity ≈ sneak 0.2, walk 0.4, trot 0.6, run 0.9). Optional: `AudioManager.set_sheltered(true/false)` when the
cat enters/leaves a `"shelter"` Area3D (rain-on-tin layer), `AudioManager.footstep_gain_db = -6` with the silent-paws skill.

## 3. (world) Reverb zones and area ids
Reverb `Area3D`s: `reverb_bus_enabled = true`, `reverb_bus_name` one of `Alley`, `Temple`, `Interior`, `Market`,
`reverb_bus_amount` 0.3–0.6, collision layer 1 or 10. Emit `GameEvents.area_entered(area_id)` with ids containing
market/cho, lake/ho_/guong, temple/dinh, alley/hem/ngo, roof — or call `AudioManager.register_area_ambience(id, &"amb_…")`.
Static emitters: `AudioManager.play_loop(&"ac_unit_loop", ac_node)`, `&"neon_buzz_loop"` on shop signs.

## 4. (world-life) Vehicles, animals, people
Moving scooters: `AudioManager.play_loop(&"scooter_ride_loop", bike, 0.0, rpm_pitch, true)` (Doppler on), `&"scooter_idle_loop"`
when parked; horns `&"horn_motorbike"`. Dog Vện: put the node in group `"dog"` (or meta `npc_kind = "dog"`) so
`npc_alerted(npc, ≥0.85)` switches to the chase music. Reactions: `human_shoo`, `human_surprise`, `human_aww`,
`human_laugh`, `dog_bark`, `crow_caw`, `pigeon_takeoff`, `flock_takeoff` … (full list in docs/areas/audio.md).

## 5. (ui / systems)
Main menu: `AudioManager.play_music(&"mus_menu")`; gameplay resumes automatic music on `player_spawned`
(or call `AudioManager.resume_auto_music()`). Festival night: `GameState.set_flag(&"festival_active", true)`;
`AudioManager.play_stinger(&"stinger_festival")` at its start. UI widgets: `play_ui(&"ui_hover"|"ui_click"|…)`.
