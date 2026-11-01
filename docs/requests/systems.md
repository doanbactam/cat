# Requests from systems (RPG core)

Everything below is optional-to-integrate, but the listed hooks are what the systems code calls
or listens for. Full API: `docs/areas/systems.md`.

## lead
1. **Story content ready to adopt**: the complete GDD main story (5 chapters) + 6 side quests and
   8 NPC dialogues are authored and tested end-to-end in `tests/fixtures/story/{quests,dialogue}/`
   (`tests/test_systems_story.gd` plays the whole story through real interactables). Their strings
   (EN + VI) are already in `data/i18n/requests/systems.csv`. To ship them, copy
   `tests/fixtures/story/quests/*.json` → `data/quests/` and `tests/fixtures/story/dialogue/*.json`
   → `data/dialogue/` (those two folders are outside systems ownership), or grant systems ownership.
2. **Exports**: JSON data is loaded at runtime with `FileAccess`; the export preset must include
   non-resource files: `include_filter="data/*.json, data/**/*.json"`.
3. `scripts/autoload/game_events.gd`: systems appended signals (inventory_changed, mouth_item_changed,
   flag_changed, attribute_changed, skill_points_changed, buff_changed, achievement_unlocked,
   player_fainted, player_revived, cat_napped, food_eaten, object_knocked_off, prey_caught,
   time_skipped, day_changed, new_game_started, dialogue_node_shown, dialogue_choice_made,
   quest_objective_revealed, counter_changed). Nothing renamed/removed.
4. `data/i18n/requests/systems.csv.import` uses `importer="keep"` so Godot does not build a
   translation resource from the request file. Other areas' request CSVs probably want the same.

## player
- Emit `GameEvents.player_spawned(self)` when the cat enters the game scene: GameState then
  applies a loaded save's `player_transform` and weather (or call
  `GameState.consume_pending_player_transform()` yourself).
- Emit `GameEvents.player_state_changed(old, new)` with state names such as `idle walk trot run
  sprint sneak climb balance jump fall sit lie_down sleep swim eat drink scratch` (GameState maps
  them to vitals activity; unknown names fall back sensibly). Or call `GameState.set_activity()`.
- Emit `player_jumped(charge)` (energy cost), `player_damaged(amount, source)` (GameState applies
  it to health — don't also call modify_stat), `player_landed(speed, surface)` (`&"water"` soaks
  the fur), `cat_sense_toggled(true)` (energy cost).
- Multiply movement by modifiers every frame: `GameState.get_modifier(&"move_speed" / "sprint_speed"
  / "sneak_speed" / "jump_distance" / "jump_height" / "climb_speed" / "wire_speed" / "balance" /
  "pounce_distance" / "noise_mult" / "landing_noise_mult" / "safe_fall_height" / "fall_damage_mult"
  / "night_vision" / "scent_range")`; `GameState.has_ability(&"wall_jump")`. Low vitals and the
  carried item are already folded into the speed/noise modifiers.
- Interaction: scan group `"interactable"` (layer 5), show `get_prompt(self)`, call
  `can_interact(self)` / `interact(self)`, then emit `GameEvents.interacted(target, target.verb)`.
  Outline `target.get_highlight_node()`. Optional: implement `play_action(name: StringName)` — the
  interactables call it with `pickup lie_down eat drink scratch rub knock`.
- Knocking: nodes in group `"pushable"` (class `Pushable`) have `knock(direction, strength, by)`;
  the "knock" verb interactable on them calls it for you.
- Dropping the mouth item: `var id := GameState.drop_mouth_item()` then
  `PickupItem.spawn_dropped(id, get_mouth_attachment().global_transform, get_parent())`.
  Show the carried item with `PickupItem.create_item_visual(GameState.mouth_item)` on
  `get_mouth_attachment()` (listen to `GameEvents.mouth_item_changed`).
- Catching prey: call `GameState.register_prey_catch(&"mouse" / &"pigeon" / ...)`.
- Grooming (sit_groom action finished): `GameState.groom()`.
- Dialogue: disable movement between `dialogue_started` and `dialogue_ended`; play the animation for
  `dialogue_choice_made(id, action)` (`meow purr headbutt rub knead sit roll_over slow_blink hiss
  swipe groom`…). DialogueManager already plays the action's sound.
- Fainting: on `player_fainted` play a collapse; GameState disables input, then calls
  `teleport(xform)` + `set_input_enabled(true)` and emits `player_revived(xform)`.

## ui
- Merge `data/i18n/requests/systems.csv` (413 keys: items, skills, prompts, notifications,
  requirements, cat actions, NPC/location names, buffs, achievements, story quests & dialogue).
- HUD: `stat_changed`, `notify(text, icon)`, `xp_gained`, `level_up`, `buff_changed`,
  `mouth_item_changed`; quest tracker: `QuestManager.get_tracked_objective()`,
  `get_tracked_target_position()` (Vector3.INF = hide marker), `quest_*` signals.
- Dialogue box: `dialogue_node_shown(info)` gives speaker name, text, portrait and choices with
  `enabled` + `requirement`; call `DialogueManager.advance()` / `choose(i)`.
- Skill tree: `GameState.get_skill_trees()`, `get_all_skills()` (`tree`, `tier`, `pos` [col,row],
  `requires`, `cost`), `get_skill_state(id)`, `get_skill_lock_reason(id)`, `unlock_skill(id)`,
  `raise_attribute(attr)`, `skill_points`, `attribute_points`.
- Inventory: `GameState.get_inventory()`, `get_item_def(id)` (`icon`, `category`, `mouth`),
  `set_mouth_item(id)`, `use_item(id)`, `equip_item(id)`, buff list `get_buffs()`.
- Save menu: slot 0 = autosave, 1–3 manual; `get_save_info(slot)` (level, day, hour, location,
  quest title id, playtime_s, saved_at), `save_game/load_game/delete_save/has_save`, `new_game()`.
- Icons expected at `res://assets/ui/icons/items/<item_id>.png` (memories share
  `memory_photo.png`), `res://assets/ui/icons/skills/<skill_id>.png` and `tree_<tree>.png`;
  portraits `res://assets/ui/portraits/<npc_id>.png`. Missing files must not break the UI.

## street-props
- Item meshes (carried in the mouth / lying in the world), origin at bottom centre, real size:
  `res://assets/models/props/item_<id>.glb` for `fish dried_fish shrimp gio_lua pate_crust
  quail_egg mooncake_crumb cap lucky_cat_figurine letter key leg_band toy_mouse yarn silver_spoon
  hair_clip glass_marble brass_bell memory_photo pigeon_feather collar_red collar_bell collar_jade
  catnip herbal_tonic skill_tonic`. Until they exist PickupItem shows small procedural stand-ins
  (logged in docs/placeholders.md).
- Knockable props: give the scene root `script = res://scripts/systems/pushable.gd` (or instance the
  GLB under a `Pushable`), set `object_id`, `material_kind` (ceramic/metal/plastic/wood/glass) and
  metadata `mass`.

## world
- Location markers (`Marker3D`, group `location`, meta `location_id`, `display_name_key`, optional
  `radius` in m, default 8) are auto-discovered by GameState when Cam comes close. Story ids used:
  `tea_stall banyan water_tower temple_roof riddle_bridge riddle_bell riddle_sun` (+ the `LOC_*`
  keys in systems.csv).
- Place interactables (scripts in `scripts/systems/`): 8 `NapSpot`s (one `spot_id =
  muop_secret_nap`), 10 `TerritorySpot`s, 12 `Collectible`s `memory_01..memory_12`, scattered
  `Collectible` cap stashes (`kind = caps`, `auto_collect_on_touch = true`), `FoodSource`s (Grandma's
  bowl, fish stall with `gives_item = fish` + `is_stealing = true`, lake water `is_water`),
  `ScratchPost`s (banyan trunk, rattan chairs), `Pushable` cups/pots on ledges, a
  `quest_target` marker for `crow_nest`, `bins_key_spot`, `leg_band_spot`, `postman_bag`,
  `race_start`, and an `Interactable` with `verb = sniff`, `target_id = stall_counter`.
- `shelter` Area3Ds: GameState tests the player position against their CollisionShape3D boxes
  (monitoring/mask not required).
- WeatherSystem: please also expose `get_intensity() -> float` so saves restore the exact rain.

## world-life
- NPC roots: group `npc`, meta `npc_id`; add a `Talkable` child (`dialogue_id` = npc id when using
  the story files). Optional hooks on the NPC: `on_dialogue_started(id)`, `on_dialogue_ended(id)`,
  `play_dialogue_anim(name)` (`talk pet_cat shoo give sad hug_cat`).
- Prey: group `prey`, meta `prey_kind`; on a successful catch call
  `GameState.register_prey_catch(kind)` (catch chance: `GameState.get_modifier(&"catch_chance")`,
  pigeons need `has_ability(&"catch_birds")`).
- Hearing/vision: scale with `GameState.get_modifier(&"detection_mult")`; `player_noise` already
  includes `noise_mult`.

## audio
Systems already uses names from your bank (tools/audio): `cat_meow_greet cat_purr cat_meow_chirp
cat_meow_trill cat_hiss cat_yowl cat_swipe` (dialogue actions), `cat_pickup` (pickups),
`stinger_memory` (memory photo found), `cat_scratch`, `cat_yawn` (nap), `cat_eat_crunch` (food),
`impact_<material>` / `impact_glass_break` (Pushable landings). Nothing new needed; for glass
props set `material_kind = glass_clink`. UI sounds (`ui_item_get`, `ui_quest_*`, `ui_level_up`,
`ui_skill_unlock`) are left to the UI on the matching GameEvents signals.
