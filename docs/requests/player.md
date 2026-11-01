# Requests from player

Everything below is what `CatPlayer` (scenes/player/cat_player.tscn) expects from other areas.
Full API and behaviour: `docs/areas/player.md`.

## world
- **Water**: make water volumes `Area3D` on layer 7 ("water", `collision_layer = 1 << 6`,
  `monitorable = true`) with a `BoxShape3D` whose top face is the water surface, or set metadata
  `water_level` (float, world Y). The cat swims at `water_level - 0.13`, splashes on entry,
  paddles to the nearest edge and mantles out over rims up to ~0.5 m above the water. A
  StaticBody on layer 7 *without* layer 1 is also treated as water when the cat lands on it.
- **Surfaces**: metadata `surface` (StringName) on colliders (or a parent) — footsteps, landing
  sounds and dust colour use it; `scripts/world/surface.gd` (`static get_surface(collider)`) is
  used automatically when it exists.
- **Climbable** surfaces (trees, drainpipes, rough walls): put the collider on layer 6
  **in addition to** layer 1. The face must be near-vertical (|normal.y| < 0.45). A walkable top
  (normal.y > 0.72, ≥ 0.15 m deep, ≥ 0.2 m head-room) lets the cat mantle over the top.
- **Beams / rails / cables**: plain colliders on layer 1 (box or cylinder, ≥ 2 cm). Anything
  narrower than ~12 cm switches the cat to balance-walk with centring assist.
- **Camera blockers**: thin things the camera should not pass through but the cat may
  (awnings, laundry, foliage cards) → layer 9; solid world on layer 1 also blocks the camera.
- **Ledges**: keep collider tops flat and aligned with the visual top (the jump planner
  ray-casts top faces; a bevelled visual with a box collider is ideal).

## ui
- Settings keys read: `graphics/fur_shells` (0 disables shells), `graphics/fov` (TPP; FPP uses
  max(fov + 5, 80)), `controls/mouse_sensitivity`, `controls/gamepad_sensitivity`,
  `controls/invert_y`, `camera/default_mode`, `camera/head_bob`. The player re-reads them on
  `GameEvents.settings_changed`.
- The camera captures the mouse in-game and releases it on `ui_menu_opened` /
  `pause_requested(true)`; recaptures on `ui_menu_closed` / `pause_requested(false)`.
- Interaction prompt: show the `prompt` from `GameEvents.interactable_focused(target, prompt)`
  (re-emitted whenever the text changes), hide on `interactable_unfocused`.
- Please merge `data/i18n/requests/player.csv` (test-gym labels).

## audio
Names the player plays through `AudioManager.play_sfx(name, pos, volume_db)`:
`cat_meow_short cat_meow_loud cat_meow_greet cat_meow_chirp cat_meow_trill cat_meow_complain
cat_jump_effort cat_swipe cat_drop cat_scratch cat_shake_wet cat_sniff splash_small splash_big
land_soft_<m> land_hard_<m>` with `<m>` ∈ `stone tile wood metal roof plastic water soft`.
Footsteps: `AudioManager.play_footstep(surface, pos, intensity)` 4× per gait cycle
(intensity 0.08–1, ×0.35 when sneaking).

## world-life
- NPC cats: reuse the fur with a variant albedo —
  `var fur := FurShells.new(); fur.albedo_override = load("res://assets/models/cat/textures/cat_albedo_black.png"); fur.use_game_state_wetness = false; fur.enable_lod = true; add_child(fur); fur.attach_to_model(cat_instance, npc_body)`.
- Swipeable NPCs/prey: implement `on_swiped(by: Node)`; the player's paw swipe (0.16 m sphere
  ~0.26 m in front) calls it.
- Cat-sense highlights animals in groups `npc` (meta `npc_kind` cat/dog/crow/pigeon/
  pigeon_flock/mouse/koi/bird) and `prey`.

## lead
- Nothing blocking. Note: `qa/` has no `.gdignore`, so preview images written there get
  `.import` files; harmless but noisy (see city-houses' request).
