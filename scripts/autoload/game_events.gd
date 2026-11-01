extends Node
## Global signal bus. CONTRACT FILE — agents may ADD signals, never rename/remove.
## Emit with `GameEvents.some_signal.emit(...)`; connect from any system.

# --- Player / cat ---------------------------------------------------------
signal player_spawned(player: Node3D)
signal player_state_changed(old_state: StringName, new_state: StringName)
signal player_landed(impact_speed: float, surface: StringName)
signal player_jumped(charge: float)
signal player_meowed(kind: StringName)          # &"short", &"chirp", &"loud", &"purr"
signal player_noise(position: Vector3, loudness: float)  # 0..1, used by NPC hearing
signal player_damaged(amount: float, source: StringName)
signal player_died()
signal camera_mode_changed(mode: StringName)    # &"first_person" / &"third_person"
signal cat_sense_toggled(active: bool)

# --- Interaction -----------------------------------------------------------
signal interactable_focused(target: Node, prompt: String)
signal interactable_unfocused(target: Node)
signal interacted(target: Node, verb: StringName)
signal item_picked_up(item_id: StringName, amount: int)
signal item_dropped(item_id: StringName, amount: int)
signal item_used(item_id: StringName)
signal item_delivered(item_id: StringName, recipient_id: StringName)

# --- RPG progression -------------------------------------------------------
signal stat_changed(stat: StringName, value: float, max_value: float)
signal xp_gained(amount: int, reason: String)
signal level_up(new_level: int)
signal skill_unlocked(skill_id: StringName)
signal reputation_changed(faction: StringName, value: int)
signal collectible_found(collectible_id: StringName)
signal territory_marked(spot_id: StringName)
signal location_discovered(location_id: StringName, display_name: String)

# --- Quests / dialogue -----------------------------------------------------
signal quest_started(quest_id: StringName)
signal quest_objective_updated(quest_id: StringName, objective_id: StringName, progress: int, required: int)
signal quest_completed(quest_id: StringName)
signal quest_failed(quest_id: StringName)
signal tracked_quest_changed(quest_id: StringName)
signal dialogue_started(dialogue_id: StringName, speaker_id: StringName)
signal dialogue_line(speaker_name: String, text: String, choices: PackedStringArray)
signal dialogue_ended(dialogue_id: StringName)

# --- World -----------------------------------------------------------------
signal time_tick(hour: float, day: int)        # emitted every in-game minute
signal phase_of_day_changed(phase: StringName)  # &"dawn", &"day", &"dusk", &"night"
signal weather_changed(weather: StringName, intensity: float)  # &"clear", &"cloudy", &"rain", &"storm", &"fog"
signal npc_alerted(npc: Node, alert_level: float)
signal npc_befriended(npc_id: StringName)
signal area_entered(area_id: StringName)

# --- Meta / UI -------------------------------------------------------------
signal notify(text: String, icon: StringName)   # toast notification
signal game_saved(slot: int)
signal game_loaded(slot: int)
signal settings_changed(section: StringName)
signal pause_requested(paused: bool)
signal ui_menu_opened(menu: StringName)
signal ui_menu_closed(menu: StringName)
