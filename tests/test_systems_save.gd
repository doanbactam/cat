extends "res://tests/fixtures/systems_test_base.gd"
## Save → load round trip of the full RPG state + providers + player transform + weather;
## robustness (missing keys, garbage, corrupt file → backup, old version), slot helpers.

class FakeProvider extends RefCounted:
	var value := 0
	var loaded_with: Variant = null
	func get_save_data() -> Dictionary:
		return {"value": value}
	func load_save_data(d: Dictionary) -> void:
		loaded_with = d
		value = int(d.get("value", 0))


class FakeWeather extends Node:
	var kind: StringName = &"clear"
	var intensity := 0.0
	func _ready() -> void:
		add_to_group(&"weather")
	func set_weather(k: StringName, i: float) -> void:
		kind = k
		intensity = i
	func get_weather() -> StringName:
		return kind
	func get_intensity() -> float:
		return intensity


func before_each() -> void:
	super.before_each()
	for s in range(0, 4):
		GameState.delete_save(s)


func _populate() -> void:
	GameState.add_xp(300, "test")
	GameState.add_attribute_points(1)
	GameState.raise_attribute(&"charm")
	GameState.unlock_skill(&"mat_dem")
	GameState.add_item(&"cap", 42)
	GameState.add_item(&"fish")
	GameState.add_item(&"letter")
	GameState.add_item(&"memory_05")
	GameState.add_item(&"collar_jade")
	GameState.equip_item(&"collar_jade")
	GameState.set_flag(&"met_mun")
	GameState.set_flag(&"visits", 3)
	GameState.add_reputation(&"rooftop_cats", 15)
	GameState.discover_location(&"lake", "Hồ Gương")
	GameState.mark_collectible(&"memory_05")
	GameState.mark_territory(&"roof_7")
	GameState.register_knock(&"cup_9")
	GameState.set_respawn_point(&"water_tank", Transform3D(Basis(Vector3.UP, 1.2), Vector3(4, 9, -3)))
	GameState.add_buff(&"sharp_claws", 2.0)
	GameState.set_world_state(&"food:pho_bowl", {"servings": 0, "refill_at": 999.0})
	GameState.set_stat(&"hunger", 61.5)
	GameState.set_stat(&"warmth", 44.0)
	GameState.wetness = 0.4
	QuestManager.start_quest(&"fx_collect")
	QuestManager.start_quest(&"fx_reach")
	GameEvents.area_entered.emit(&"fx_lake")
	TimeOfDay.set_time(3, 21.5)


func test_full_round_trip() -> void:
	var p := spawn_player(Vector3(12.5, 3.25, -7.75))
	p.rotation.y = 0.7
	var w := FakeWeather.new()
	spawn(w)
	w.set_weather(&"rain", 0.65)
	var prov := FakeProvider.new()
	prov.value = 77
	GameState.register_save_provider("fx_provider", prov)
	_populate()
	DialogueManager.start(&"fx_bong_hi")
	DialogueManager.advance()
	capture(&"game_saved")
	capture(&"game_loaded")
	assert_true(GameState.save_game(1))
	assert_true(GameState.has_save(1))
	assert_eq(events_named(&"game_saved").size(), 1)
	var expect_level := GameState.level
	var expect_sp := GameState.skill_points
	var expect_xp := GameState.xp
	var expect_rep := GameState.get_reputation(&"rooftop_cats")
	assert_eq(expect_xp, 300 + 15 + 30 + 3, "xp: populate + location + fx_reach reward + first knock")
	assert_eq(expect_rep, 17, "15 × rep_gain (charm 3 → 1.04, jade collar +0.1)")
	# wreck everything
	GameState.new_game()
	TimeOfDay.set_time(1, 6.0)
	prov.value = 0
	p.global_position = Vector3.ZERO
	w.set_weather(&"clear", 0.0)
	assert_eq(GameState.get_caps(), 0)
	assert_false(QuestManager.is_active(&"fx_collect"))
	# load
	assert_true(GameState.load_game(1))
	assert_eq(events_named(&"game_loaded").size(), 1)
	assert_eq(GameState.level, expect_level)
	assert_eq(GameState.xp, expect_xp)
	assert_eq(GameState.skill_points, expect_sp)
	assert_eq(GameState.get_attribute(&"charm"), 3)
	assert_true(GameState.has_skill(&"mat_dem"))
	assert_eq(GameState.get_caps(), 42)
	assert_eq(GameState.mouth_item, &"fish")
	assert_true(GameState.has_item(&"letter"))
	assert_eq(GameState.get_equipped(&"collar"), &"collar_jade")
	assert_true(bool(GameState.get_flag(&"met_mun")))
	assert_eq(int(GameState.get_flag(&"visits")), 3)
	assert_eq(GameState.get_reputation(&"rooftop_cats"), expect_rep)
	assert_true(GameState.is_location_discovered(&"lake"))
	assert_true(GameState.is_collectible_found(&"memory_05"))
	assert_true(GameState.is_territory_marked(&"roof_7"))
	assert_eq(GameState.get_counter(&"knocked_unique"), 1)
	assert_eq(GameState.get_last_nap_spot(), &"water_tank")
	var nx: Transform3D = GameState.get_last_nap_transform()
	assert_true(nx.origin.is_equal_approx(Vector3(4, 9, -3)))
	assert_near(nx.basis.get_euler().y, 1.2, 0.0001)
	assert_true(GameState.has_buff(&"sharp_claws"))
	assert_eq(int(GameState.get_world_state(&"food:pho_bowl")["servings"]), 0)
	assert_near(GameState.get_stat(&"hunger"), 61.5)
	assert_near(GameState.get_stat(&"warmth"), 44.0)
	assert_near(GameState.wetness, 0.4)
	assert_eq(TimeOfDay.day, 3)
	assert_near(TimeOfDay.hour, 21.5)
	assert_true(QuestManager.is_active(&"fx_collect"))
	assert_true(QuestManager.is_completed(&"fx_reach"))
	assert_eq(QuestManager.get_tracked(), &"fx_collect")
	assert_true(DialogueManager.has_seen(&"fx_bong_hi"))
	assert_eq(prov.value, 77, "custom provider restored")
	assert_true(p.global_position.is_equal_approx(Vector3(12.5, 3.25, -7.75)), "player transform")
	assert_near(p.rotation.y, 0.7, 0.0001)
	assert_eq(w.kind, &"rain")
	assert_near(w.intensity, 0.65)
	GameState.unregister_save_provider("fx_provider")


func test_player_transform_applied_when_player_spawns_later() -> void:
	var p := spawn_player(Vector3(1, 2, 3))
	GameState.save_game(2)
	_spawned.erase(p)
	tree.root.remove_child(p)
	p.free()
	GameState.load_game(2)
	assert_true(GameState.get_pending_player_transform() is Transform3D)
	var p2 := spawn_player(Vector3.ZERO)
	GameEvents.player_spawned.emit(p2)
	assert_true(p2.global_position.is_equal_approx(Vector3(1, 2, 3)))
	assert_true(GameState.get_pending_player_transform() == null)


func test_provider_registered_after_load_gets_pending_data() -> void:
	var prov := FakeProvider.new()
	prov.value = 5
	GameState.register_save_provider("fx_late", prov)
	GameState.save_game(1)
	GameState.unregister_save_provider("fx_late")
	GameState.load_game(1)
	var late := FakeProvider.new()
	GameState.register_save_provider("fx_late", late)
	assert_eq(late.value, 5, "pending provider data delivered on registration")
	GameState.save_game(1)  # pending data must survive a save before registration too
	GameState.unregister_save_provider("fx_late")


func test_missing_keys_and_garbage_are_tolerated() -> void:
	GameState.apply_save_data({"version": 1, "state": {"xp": 120, "items": {"cap": 3, "fish": "lots", "letter": -2},
		"mouth_item": "key", "stats": {"health": 500}, "attributes": {"charm": 42}, "skills": ["not_a_skill", "mat_dem"],
		"last_nap_transform": [1, 2, "x"]}})
	assert_eq(GameState.xp, 120)
	assert_eq(GameState.get_caps(), 3)
	assert_false(GameState.has_item(&"letter"))
	assert_eq(GameState.mouth_item, &"", "mouth item not owned → empty")
	assert_near(GameState.get_stat(&"health"), 100.0, 0.001, "clamped")
	assert_near(GameState.get_stat(&"hunger"), 100.0, 0.001, "missing → full")
	assert_eq(GameState.get_attribute(&"charm"), 10)
	assert_eq(GameState.get_attribute(&"stealth"), 2, "missing → start value")
	assert_true(GameState.has_skill(&"mat_dem"))
	assert_false(GameState.has_skill(&"not_a_skill"))
	assert_true(GameState.get_last_nap_transform() == null)
	GameState.apply_save_data({})
	assert_eq(GameState.level, 1)


func test_version0_saves_migrate() -> void:
	GameState.apply_save_data({"xp": 260, "level": 3, "flags": {"old": true}})
	assert_eq(GameState.level, 3)
	assert_true(bool(GameState.get_flag(&"old")))


func test_corrupt_save_falls_back_to_backup() -> void:
	GameState.add_item(&"cap", 9)
	assert_true(GameState.save_game(3))
	GameState.add_item(&"cap", 1)
	assert_true(GameState.save_game(3))  # previous file becomes .bak
	var f := FileAccess.open(GameState.get_save_path(3), FileAccess.WRITE)
	f.store_string("{ this is not json")
	f.close()
	GameState.new_game()
	assert_true(GameState.load_game(3))
	assert_eq(GameState.get_caps(), 9, "loaded the backup")
	assert_false(GameState.load_game(0), "no save in slot 0")


func test_save_info_and_delete() -> void:
	GameState.add_xp(150)
	TimeOfDay.set_time(2, 8.0)
	GameState.discover_location(&"tea_stall", "Quán trà")
	QuestManager.start_quest(&"fx_collect")
	GameState.save_game(1)
	var info := GameState.get_save_info(1)
	assert_true(info["exists"])
	assert_eq(int(info["level"]), 2)
	assert_eq(int(info["day"]), 2)
	assert_eq(String(info["location"]), "Quán trà")
	assert_eq(String(info["quest"]), "fx_collect")
	assert_eq(int(info["version"]), GameState.SAVE_VERSION)
	assert_true(String(info["saved_at"]) != "")
	GameState.save_game(1)  # creates a .bak of the previous file
	assert_true(GameState.delete_save(1))
	assert_false(GameState.has_save(1))
	assert_false(GameState.load_game(1), "backup removed too")
	assert_false(GameState.get_save_info(1)["exists"])


func test_autosave_throttled() -> void:
	GameState.autosave_enabled = true
	GameState._last_autosave_msec = -1000000
	assert_true(GameState.autosave("test"))
	assert_true(GameState.has_save(GameState.AUTOSAVE_SLOT))
	GameState.add_item(&"cap", 33)
	assert_false(GameState.autosave("again"), "throttled → deferred")
	assert_true(GameState._autosave_pending)
	GameState._last_autosave_msec -= int(GameState.autosave_min_interval_s * 1000.0) + 10
	await tree.process_frame
	await tree.process_frame
	assert_false(GameState._autosave_pending, "deferred autosave ran")
	assert_eq(int(GameState.get_save_info(GameState.AUTOSAVE_SLOT)["caps"]), 33)
	GameState.autosave_enabled = false
