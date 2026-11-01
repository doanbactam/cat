extends "res://tests/fixtures/systems_test_base.gd"
## QuestManager: every objective type, stages, optional/hidden, prerequisites, rewards, chaining,
## tracking + target markers, gating (time windows / when), fail_if, auto_start, save provider.

func test_fixtures_load_and_validate() -> void:
	for id in ["fx_reach", "fx_collect", "fx_chain_next", "fx_interact", "fx_state", "fx_gated", "fx_auto", "fx_existing", "fx_pickup_mode"]:
		assert_true(QuestManager.has_quest(StringName(id)), id)
		assert_true(QuestManager.validate_quest(QuestManager.get_quest_def(StringName(id))).is_empty(), id + " valid")


func test_validation_catches_errors() -> void:
	var errs := QuestManager.validate_quest({"id": "bad", "objectives": [
		{"id": "a", "type": "teleport"}, {"id": "a", "type": "collect_item", "item": "unicorn"},
		{"id": "b", "type": "deliver_item", "item": "fish"}]})
	assert_true(errs.size() >= 4, "errors: %s" % str(errs))
	assert_false(QuestManager.register_quest({"id": "empty", "objectives": []}))


func test_reach_location_by_event_and_hidden_optional() -> void:
	capture(&"quest_completed")
	capture(&"quest_objective_revealed")
	assert_true(QuestManager.start_quest(&"fx_reach"))
	assert_true(QuestManager.is_active(&"fx_reach"))
	assert_false(QuestManager.start_quest(&"fx_reach"), "already active")
	var objs := QuestManager.get_objectives(&"fx_reach")
	assert_true(objs[1]["hidden"], "hidden until progressed")
	GameState.add_item(&"memory_02")
	assert_eq(events_named(&"quest_objective_revealed").size(), 1)
	assert_true(QuestManager.is_objective_done(&"fx_reach", &"find_memory"))
	assert_true(QuestManager.is_active(&"fx_reach"), "optional doesn't complete the quest")
	GameEvents.area_entered.emit(&"fx_lake")
	assert_true(QuestManager.is_completed(&"fx_reach"))
	assert_eq(events_named(&"quest_completed").size(), 1)
	assert_eq(GameState.xp, 30)


func test_reach_location_by_proximity_polling() -> void:
	var p := spawn_player(Vector3(0, 0, 0))
	spawn_marker("fx_lake", Vector3(10, 0, 0), &"location", &"location_id")
	QuestManager.start_quest(&"fx_reach")
	QuestManager._poll_reach_objectives()
	assert_false(QuestManager.is_objective_done(&"fx_reach", &"go_lake"))
	p.global_position = Vector3(8.5, 0, 0)
	QuestManager._poll_reach_objectives()
	assert_true(QuestManager.is_completed(&"fx_reach"), "within radius 2")


func test_collect_then_deliver_rewards_and_chain() -> void:
	capture(&"quest_started")
	capture(&"item_delivered")
	assert_false(QuestManager.can_start(&"fx_chain_next"), "prerequisite not met")
	assert_false(QuestManager.start_quest(&"fx_chain_next"))
	QuestManager.start_quest(&"fx_collect")
	assert_eq(QuestManager.get_tracked(), &"fx_collect", "main quests auto-track")
	GameState.add_item(&"cap", 3)
	assert_eq(QuestManager.get_objective_progress(&"fx_collect", &"caps"), 3)
	assert_false(QuestManager.is_objective_active(&"fx_collect", &"give_fish"), "stage 2 locked")
	GameState.add_item(&"cap", 4)
	assert_true(QuestManager.is_objective_done(&"fx_collect", &"caps"))
	assert_true(QuestManager.is_objective_active(&"fx_collect", &"give_fish"))
	assert_false(QuestManager.try_deliver(&"fx_crow"), "no fish in mouth")
	GameState.add_item(&"fish")
	assert_false(QuestManager.try_deliver(&"someone_else"))
	assert_true(QuestManager.try_deliver(&"fx_crow"))
	assert_false(GameState.has_item(&"fish"), "fish consumed")
	assert_eq(events_named(&"item_delivered").size(), 1)
	assert_true(QuestManager.is_completed(&"fx_collect"))
	# rewards
	assert_eq(GameState.get_caps(), 7 + 3)
	assert_true(GameState.has_item(&"catnip"))
	assert_true(bool(GameState.get_flag(&"fx_collect_done")))
	assert_eq(GameState.get_reputation(&"birds"), 10)
	assert_eq(GameState.skill_points, 1 + 1 + 1, "start + level 2 + reward")
	assert_eq(GameState.level, 2)
	# chain
	assert_true(QuestManager.is_active(&"fx_chain_next"), "next quest auto-started")
	assert_eq(QuestManager.get_tracked(), &"fx_chain_next")
	GameEvents.dialogue_started.emit(&"whatever", &"fx_bong")
	assert_true(QuestManager.is_completed(&"fx_chain_next"))


func test_interact_territory_nap_knock_catch_sequence() -> void:
	QuestManager.start_quest(&"fx_interact")
	var post := Node3D.new()
	post.name = "fx_post"
	spawn(post)
	GameEvents.interacted.emit(post, &"knock")
	assert_false(QuestManager.is_objective_done(&"fx_interact", &"scratch"), "wrong verb")
	GameEvents.interacted.emit(post, &"scratch")
	assert_true(QuestManager.is_objective_done(&"fx_interact", &"scratch"))
	GameState.mark_territory(&"spot_a")
	GameEvents.territory_marked.emit(&"spot_a")  # duplicate → unique spots only
	assert_eq(QuestManager.get_objective_progress(&"fx_interact", &"mark"), 1)
	GameState.mark_territory(&"spot_b")
	assert_true(QuestManager.is_objective_done(&"fx_interact", &"mark"))
	GameState.nap(0.5, &"short_nap")
	assert_false(QuestManager.is_objective_done(&"fx_interact", &"nap"), "min_hours 1")
	GameState.nap(2.0, &"good_nap")
	assert_true(QuestManager.is_objective_done(&"fx_interact", &"nap"))
	GameEvents.object_knocked_off.emit(null, &"cup_1", 1.2)
	GameEvents.object_knocked_off.emit(null, &"cup_1", 1.2)
	assert_eq(QuestManager.get_objective_progress(&"fx_interact", &"knock"), 1, "same cup twice counts once")
	GameEvents.object_knocked_off.emit(null, &"pot_2", 2.0)
	assert_true(QuestManager.is_objective_done(&"fx_interact", &"knock"))
	GameState.register_prey_catch(&"mouse")
	assert_false(QuestManager.is_objective_done(&"fx_interact", &"catch"), "needs a pigeon")
	GameState.register_prey_catch(&"pigeon")
	assert_true(QuestManager.is_completed(&"fx_interact"))
	assert_eq(GameState.attribute_points, 1 + 1, "reward + level up")


func test_one_event_does_not_cascade_through_stages() -> void:
	QuestManager.register_quest({"id": "fx_two_talks", "objectives": [
		{"id": "t1", "type": "talk_to", "npc": "ba_tu"}, {"id": "t2", "type": "talk_to", "npc": "ba_tu"}]})
	QuestManager.start_quest(&"fx_two_talks")
	QuestManager.report(&"talk_to", {"npc_id": "ba_tu"})
	assert_true(QuestManager.is_objective_done(&"fx_two_talks", &"t1"))
	assert_false(QuestManager.is_objective_done(&"fx_two_talks", &"t2"))
	QuestManager.report(&"talk_to", {"npc_id": "ba_tu"})
	assert_true(QuestManager.is_completed(&"fx_two_talks"))


func test_state_objectives_flag_time_condition_and_hidden_event() -> void:
	TimeOfDay.set_hour(12.0)
	QuestManager.start_quest(&"fx_state")
	assert_false(QuestManager.is_objective_done(&"fx_state", &"door"))
	GameState.set_flag(&"fx_door_open")
	assert_true(QuestManager.is_objective_done(&"fx_state", &"door"))
	TimeOfDay.set_hour(20.0)
	assert_true(QuestManager.is_objective_done(&"fx_state", &"night"))
	QuestManager.report(&"fx_secret")
	assert_true(QuestManager.is_objective_done(&"fx_state", &"secret"))
	assert_true(bool(GameState.get_flag(&"fx_secret_found")), "objective effects")
	assert_eq(GameState.xp, 15, "objective rewards")
	assert_true(QuestManager.is_active(&"fx_state"))
	GameState.set_attribute(&"charm", 3)
	assert_true(QuestManager.is_completed(&"fx_state"))


func test_state_objective_already_satisfied_at_start() -> void:
	GameState.set_flag(&"fx_door_open")
	GameState.set_attribute(&"charm", 4)
	TimeOfDay.set_hour(23.0)
	QuestManager.start_quest(&"fx_state")
	assert_true(QuestManager.is_completed(&"fx_state"))


func test_when_gating_match_and_fail_if() -> void:
	QuestManager.start_quest(&"fx_gated")
	TimeOfDay.set_hour(12.0)
	QuestManager.report(&"fx_race", {"track": "rooftops"})
	assert_false(QuestManager.is_objective_done(&"fx_gated", &"race"), "only at night")
	TimeOfDay.set_hour(22.0)
	QuestManager.report(&"fx_race", {"track": "street"})
	assert_false(QuestManager.is_objective_done(&"fx_gated", &"race"), "data must match")
	QuestManager.report(&"fx_race", {"track": "rooftops"})
	assert_true(QuestManager.is_objective_done(&"fx_gated", &"race"))
	TimeOfDay.set_festival_day(1)
	TimeOfDay.set_time(2, 20.0)
	QuestManager.report(&"interact", {"verb": "light", "target_id": "lantern"})
	assert_false(QuestManager.is_completed(&"fx_gated"), "not festival day")
	TimeOfDay.set_festival_day(2)
	TimeOfDay.set_hour(17.0)
	QuestManager.report(&"interact", {"verb": "light", "target_id": "lantern"})
	assert_false(QuestManager.is_completed(&"fx_gated"), "outside 18–23")
	TimeOfDay.set_hour(19.0)
	QuestManager.report(&"interact", {"verb": "light", "target_id": "lantern"})
	assert_true(QuestManager.is_completed(&"fx_gated"))
	TimeOfDay.set_festival_day(4)
	QuestManager.reset_quest(&"fx_gated")
	capture(&"quest_failed")
	QuestManager.start_quest(&"fx_gated")
	GameState.set_flag(&"fx_fail")
	assert_true(QuestManager.is_failed(&"fx_gated"))
	assert_false(QuestManager.start_quest(&"fx_gated"), "no retry")
	assert_eq(events_named(&"quest_failed").size(), 1)


func test_auto_start_on_prerequisites() -> void:
	capture(&"quest_started")
	GameState.set_flag(&"something_else")
	assert_false(QuestManager.is_active(&"fx_auto"))
	GameState.set_flag(&"fx_auto_go")
	assert_true(QuestManager.is_active(&"fx_auto"))
	GameEvents.dialogue_started.emit(&"other_dialogue", &"fx_bong")
	assert_false(QuestManager.is_completed(&"fx_auto"), "needs that dialogue")
	GameEvents.dialogue_started.emit(&"fx_bong_hi", &"fx_bong")
	assert_true(QuestManager.is_completed(&"fx_auto"))


func test_count_existing_territory() -> void:
	GameState.mark_territory(&"roof_a")
	GameState.mark_territory(&"roof_b")
	GameState.mark_territory(&"street_x")
	QuestManager.start_quest(&"fx_existing")
	assert_eq(QuestManager.get_objective_progress(&"fx_existing", &"mark3"), 2, "only listed spots")
	GameState.mark_territory(&"roof_d")
	assert_true(QuestManager.is_completed(&"fx_existing"))


func test_collect_pickup_mode() -> void:
	GameState.add_item(&"cap", 10)
	QuestManager.start_quest(&"fx_pickup_mode")
	assert_eq(QuestManager.get_objective_progress(&"fx_pickup_mode", &"pick"), 0, "pickup mode ignores inventory")
	GameEvents.item_picked_up.emit(&"cap", 2)
	GameEvents.item_picked_up.emit(&"fish", 1)
	GameEvents.item_picked_up.emit(&"cap", 1)
	assert_true(QuestManager.is_completed(&"fx_pickup_mode"))


func test_manual_advance_complete_and_fail() -> void:
	QuestManager.start_quest(&"fx_interact")
	assert_true(QuestManager.advance_objective(&"fx_interact", &"scratch"))
	assert_false(QuestManager.advance_objective(&"fx_interact", &"catch"), "not active yet")
	assert_true(QuestManager.complete_objective(&"fx_interact", &"mark"))
	assert_true(QuestManager.complete_quest(&"fx_interact"))
	assert_true(QuestManager.is_completed(&"fx_interact"))
	assert_false(QuestManager.fail_quest(&"fx_interact"))


func test_get_quest_view() -> void:
	QuestManager.start_quest(&"fx_collect")
	var q := QuestManager.get_quest(&"fx_collect")
	assert_eq(q["state"], "active")
	assert_true(q["tracked"])
	assert_eq((q["objectives"] as Array).size(), 2)
	assert_eq(q["objectives"][0]["required"], 5)
	assert_true(q["objectives"][0]["active"])
	assert_false(q["objectives"][1]["active"])
	assert_eq(String(q["title"]), "QUEST_FX_COLLECT_TITLE")
	assert_true(QuestManager.get_quest(&"nope").is_empty())


func test_tracking_and_target_positions() -> void:
	spawn_player(Vector3.ZERO)
	assert_eq(QuestManager.get_tracked_target_position(), Vector3.INF, "nothing tracked")
	QuestManager.start_quest(&"fx_reach")
	spawn_marker("fx_lake", Vector3(40, 0, -20), &"location", &"location_id")
	assert_true(QuestManager.get_tracked_target_position().is_equal_approx(Vector3(40, 0, -20)))
	capture(&"tracked_quest_changed")
	QuestManager.start_quest(&"fx_collect")
	assert_eq(QuestManager.get_tracked(), &"fx_collect", "main quest takes tracking")
	# collect objective → nearest PickupItem with that item_id
	var far := PickupItem.new()
	far.item_id = &"cap"
	spawn(far)
	far.global_position = Vector3(30, 0, 0)
	var near := PickupItem.new()
	near.item_id = &"cap"
	spawn(near)
	near.global_position = Vector3(5, 0, 0)
	assert_true(QuestManager.get_tracked_target_position().is_equal_approx(Vector3(5, 0, 0)))
	GameState.add_item(&"cap", 5)
	# deliver objective uses explicit target_id marker
	spawn_marker("fx_crow_marker", Vector3(-7, 3, 2))
	assert_true(QuestManager.get_tracked_target_position().is_equal_approx(Vector3(-7, 3, 2)))
	assert_true(QuestManager.track(&"fx_reach"))
	assert_false(QuestManager.track(&"fx_interact"), "can't track inactive quests")
	assert_true(QuestManager.get_tracked_target_position().is_equal_approx(Vector3(40, 0, -20)))
	assert_true(events_named(&"tracked_quest_changed").size() >= 2)
	assert_eq(QuestManager.get_tracked_objective()["id"], "go_lake")


func test_find_target_node_by_npc_and_quest_target() -> void:
	spawn_player(Vector3.ZERO)
	var npc := Node3D.new()
	npc.add_to_group(&"npc")
	npc.set_meta(&"npc_id", "ba_tu")
	spawn(npc)
	npc.global_position = Vector3(2, 0, 3)
	assert_eq(QuestManager.find_target_node(&"ba_tu"), npc)
	var qt := spawn_marker("ba_tu", Vector3(9, 0, 9))
	assert_eq(QuestManager.find_target_node(&"ba_tu"), qt, "quest_target markers win")
	assert_null_or_eq(QuestManager.find_target_node(&"nobody"))


func assert_null_or_eq(v: Variant) -> void:
	assert_true(v == null, "expected null")


func test_save_provider_round_trip() -> void:
	QuestManager.start_quest(&"fx_collect")
	GameState.add_item(&"cap", 2)
	QuestManager.start_quest(&"fx_reach")
	QuestManager.track(&"fx_reach")
	GameEvents.area_entered.emit(&"fx_lake")
	var d := QuestManager.get_save_data()
	var json := JSON.parse_string(JSON.stringify(d)) as Dictionary  # floats/strings like a real save
	QuestManager.reset_state()
	assert_false(QuestManager.is_active(&"fx_collect"))
	QuestManager.load_save_data(json)
	assert_true(QuestManager.is_active(&"fx_collect"))
	assert_true(QuestManager.is_completed(&"fx_reach"))
	assert_eq(QuestManager.get_objective_progress(&"fx_collect", &"caps"), 2)
	assert_eq(QuestManager.get_tracked(), &"fx_collect", "tracked falls back to an active quest")
	QuestManager.load_save_data({"quests": {"fx_collect": {"state": "bogus", "objectives": "x"}, "removed_quest": {"state": "active"}}})
	assert_eq(QuestManager.get_state(&"fx_collect"), &"inactive", "robust to garbage")
	assert_eq(QuestManager.get_active_quests().size(), 0, "unknown quest ids ignored")


func test_interacted_dedupe_same_frame() -> void:
	QuestManager.register_quest({"id": "fx_scratch3", "objectives": [{"id": "s", "type": "interact", "verb": "scratch", "count": 3}]})
	QuestManager.start_quest(&"fx_scratch3")
	var post := Node3D.new()
	spawn(post)
	GameEvents.interacted.emit(post, &"scratch")
	GameEvents.interacted.emit(post, &"scratch")
	assert_eq(QuestManager.get_objective_progress(&"fx_scratch3", &"s"), 1, "double emit in one frame")
	# Two frames: if the previous test ended inside a physics step, the first process_frame
	# still belongs to the same main-loop iteration.
	await tree.process_frame
	await tree.process_frame
	GameEvents.interacted.emit(post, &"scratch")
	assert_eq(QuestManager.get_objective_progress(&"fx_scratch3", &"s"), 2)
