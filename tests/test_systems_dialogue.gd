extends "res://tests/fixtures/systems_test_base.gd"
## DialogueManager: graph walking, cat-action choices, conditions (flag/item/attribute/skill/
## reputation/quest), locked & once choices, branches, effects, signals, validation, save.

func test_fixtures_valid_and_broken_detected() -> void:
	for id in ["fx_ba_tu", "fx_crow", "fx_bong_hi"]:
		var d := DialogueManager.get_dialogue(StringName(id))
		assert_false(d.is_empty(), id)
		assert_true(DialogueManager.validate_dialogue(d).is_empty(), "%s: %s" % [id, str(DialogueManager.validate_dialogue(d))])
	var broken: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(FIXTURE_DIALOGUE + "/fx_broken.json"))
	var errs := DialogueManager.validate_dialogue(broken)
	assert_true(errs.size() >= 5, "found: %s" % str(errs))


func test_full_conversation_flow_and_signals() -> void:
	capture(&"dialogue_started")
	capture(&"dialogue_line")
	capture(&"dialogue_node_shown")
	capture(&"dialogue_ended")
	capture(&"dialogue_choice_made")
	TimeOfDay.paused = false
	assert_true(DialogueManager.start(&"fx_ba_tu", null, &"ba_tu"))
	assert_true(DialogueManager.is_active())
	assert_true(TimeOfDay.is_paused(), "clock stops during dialogue")
	assert_eq(events_named(&"dialogue_started")[0][2], &"ba_tu")
	var line := DialogueManager.get_current_line()
	assert_eq(line["node_id"], "greet")
	assert_eq(line["speaker_name"], tr("NPC_BA_TU"))
	assert_true(line["can_advance"])
	assert_true(bool(GameState.get_flag(&"fx_greeted")), "node effects")
	assert_false(DialogueManager.choose(0), "no choices on this node")
	assert_true(DialogueManager.advance())
	line = DialogueManager.get_current_line()
	assert_eq(line["node_id"], "ask")
	assert_false(DialogueManager.advance(), "must choose")
	var choices := DialogueManager.get_choices()
	assert_eq(choices.size(), 4, "hiss hidden (condition false, not show_locked)")
	assert_eq(choices[0]["action"], "meow")
	assert_eq(choices[1]["action"], "purr")
	assert_false(choices[1]["enabled"], "charm 2 < 3 → locked")
	assert_true(String(choices[1]["requirement"]) != "")
	assert_false(DialogueManager.choose(1), "locked")
	var plain: PackedStringArray = events_named(&"dialogue_line")[-1][3]
	assert_eq(plain.size(), 4)
	assert_true(plain[1].begins_with("("), "locked choice shows requirement")
	# headbutt loops back once, then disappears
	assert_true(DialogueManager.choose(2))
	assert_eq(GameState.get_counter(&"fx_headbutts"), 1)
	assert_eq(DialogueManager.get_current_line()["node_id"], "ask")
	assert_eq(DialogueManager.get_choices().size(), 3, "once choice gone")
	assert_eq(events_named(&"dialogue_choice_made")[0][2], &"headbutt")
	# meow → fed (eat + give item) → end
	GameState.set_stat(&"hunger", 50.0)
	assert_true(DialogueManager.choose(0))
	assert_eq(GameState.get_reputation(&"humans"), 2)
	assert_eq(DialogueManager.get_current_line()["node_id"], "fed")
	assert_near(GameState.get_stat(&"hunger"), 80.0)
	assert_eq(GameState.mouth_item, &"dried_fish")
	assert_true(DialogueManager.advance())
	assert_false(DialogueManager.is_active())
	assert_eq(events_named(&"dialogue_ended").size(), 1)
	assert_false(TimeOfDay.is_paused(), "clock resumes")
	assert_true(DialogueManager.has_seen(&"fx_ba_tu"))
	assert_true(DialogueManager.has_seen(&"fx_ba_tu/fed"))
	assert_true(events_named(&"dialogue_node_shown").size() >= 3)
	TimeOfDay.paused = true


func test_charm_unlocks_purr_and_starts_quest() -> void:
	GameState.set_attribute(&"charm", 3)
	DialogueManager.start(&"fx_ba_tu")
	DialogueManager.advance()
	var choices := DialogueManager.get_choices()
	assert_true(choices[1]["enabled"])
	assert_true(String(choices[1]["text"]).contains("FX_PURR_SWEET"))
	assert_true(DialogueManager.choose(1))
	assert_true(bool(GameState.get_flag(&"fx_purred")))
	assert_eq(GameState.xp, 10)
	assert_true(QuestManager.is_active(&"fx_collect"), "start_quest effect")
	assert_true(DialogueManager.advance())
	assert_false(DialogueManager.is_active())


func test_charm_bonus_from_skill_counts() -> void:
	GameState.grant_skill(&"tieng_keu_dang_yeu")
	DialogueManager.start(&"fx_ba_tu")
	DialogueManager.advance()
	assert_true(DialogueManager.get_choices()[1]["enabled"], "charm 2 + skill bonus 1")
	DialogueManager.stop()


func test_conditional_entry_and_once_nodes() -> void:
	QuestManager.start_quest(&"fx_collect")
	QuestManager.complete_quest(&"fx_collect")
	DialogueManager.start(&"fx_ba_tu")
	assert_eq(DialogueManager.get_current_line()["node_id"], "thanks")
	DialogueManager.advance()
	DialogueManager.start(&"fx_ba_tu")
	assert_eq(DialogueManager.get_current_line()["node_id"], "thanks_again", "once node falls to else")
	DialogueManager.advance()
	assert_false(DialogueManager.is_active())


func test_branch_mouth_item_and_deliver_effect() -> void:
	capture(&"item_delivered")
	DialogueManager.start(&"fx_crow")
	assert_eq(DialogueManager.get_current_line()["node_id"], "poor")
	DialogueManager.advance()
	GameState.add_item(&"fish")
	QuestManager.start_quest(&"fx_collect")
	GameState.add_item(&"cap", 5)
	DialogueManager.start(&"fx_crow")
	assert_eq(DialogueManager.get_current_line()["node_id"], "has_fish")
	assert_eq(DialogueManager.get_choices()[0]["action"], "offer_item")
	DialogueManager.choose(0)
	assert_eq(events_named(&"item_delivered").size(), 1)
	assert_false(GameState.has_item(&"fish"))
	assert_true(QuestManager.is_completed(&"fx_collect"), "delivered through dialogue")
	assert_true(bool(GameState.get_flag(&"fx_crow_happy")), "if/then effect")
	DialogueManager.advance()


func test_caps_branch_and_buy_effect() -> void:
	GameState.add_item(&"cap", 12)
	DialogueManager.start(&"fx_crow")
	assert_eq(DialogueManager.get_current_line()["node_id"], "rich")
	assert_false(DialogueManager.get_choices()[0]["enabled"], "needs 15 caps")
	DialogueManager.stop()
	GameState.add_item(&"cap", 10)
	DialogueManager.start(&"fx_crow")
	assert_true(DialogueManager.choose(0))
	assert_true(GameState.has_item(&"collar_red"))
	assert_eq(GameState.get_caps(), 7)
	assert_false(DialogueManager.is_active())


func test_speaker_id_from_node_and_text_args() -> void:
	capture(&"dialogue_started")
	var npc := Node3D.new()
	npc.set_meta(&"npc_id", "fx_bong")
	spawn(npc)
	DialogueManager.start(&"fx_bong_hi", npc)
	assert_eq(events_named(&"dialogue_started")[0][2], &"fx_bong")
	assert_eq(DialogueManager.get_current_line()["speaker_name"], "NPC_FX_BONG")
	DialogueManager.advance()


func test_cannot_start_twice_or_unknown() -> void:
	assert_false(DialogueManager.start(&"does_not_exist"))
	assert_true(DialogueManager.start(&"fx_bong_hi"))
	assert_false(DialogueManager.start(&"fx_ba_tu"), "one at a time")
	DialogueManager.stop()
	assert_false(DialogueManager.is_active())


func test_conditions_module() -> void:
	var C := GameConditions
	assert_true(C.evaluate(null))
	assert_true(C.evaluate({}))
	assert_false(C.evaluate("met_mun"))
	GameState.set_flag(&"met_mun")
	assert_true(C.evaluate("met_mun"))
	assert_false(C.evaluate("!met_mun"))
	GameState.set_flag(&"visits", 3)
	assert_true(C.evaluate({"flag": "visits", "gte": 2}))
	assert_false(C.evaluate({"flag": "visits", "value": 2}))
	assert_true(C.evaluate({"attribute": "agility", "gte": 3}))
	assert_false(C.evaluate({"attribute": "agility", "gt": 3}))
	assert_true(C.evaluate({"skill": "mat_dem"}) == false)
	assert_true(C.evaluate({"not_skill": "mat_dem"}))
	GameState.add_reputation(&"rooftop_cats", 20)
	assert_true(C.evaluate({"reputation": "rooftop_cats", "gte": 20}))
	assert_true(C.evaluate({"quest": "fx_reach", "state": "not_started"}))
	assert_true(C.evaluate({"quest": "fx_reach", "state": "available"}))
	QuestManager.start_quest(&"fx_reach")
	assert_true(C.evaluate({"quest": "fx_reach", "state": "active"}))
	assert_true(C.evaluate({"objective": "go_lake", "quest": "fx_reach", "done": false}))
	assert_true(C.evaluate({"stat": "hunger", "gte": 99}))
	TimeOfDay.set_hour(21.0)
	assert_true(C.evaluate({"phase": ["dusk", "night"]}))
	assert_true(C.evaluate({"time": {"from": 19, "to": 5}}))
	assert_true(C.evaluate({"any": [{"flag": "nope"}, {"level": 1}]}))
	assert_false(C.evaluate({"not": {"level": 1}}))
	assert_true(C.evaluate([{"level": 1}, "met_mun", {"mouth_empty": true}]))
	assert_true(C.evaluate({"speaker": "mun"}, {"speaker_id": "mun"}))
	GameState.set_weather_state(&"rain", 0.5)
	assert_true(C.evaluate({"weather": ["rain", "storm"]}))
	assert_true(C.validate({"flag": "a", "colour": "red"}).size() == 1)
	assert_true(C.validate({"value": 3}).size() == 1, "no primary key")
	var desc := C.describe([{"attribute": "charm", "gte": 3}, {"caps": 10}, {"flag": "secret"}])
	assert_true(desc.contains(tr("REQ_ATTRIBUTE").format({"attribute": tr("ATTR_CHARM"), "value": 3})) and desc.contains(tr("REQ_CAPS").format({"count": 10})), desc)


func test_effects_module() -> void:
	var E := GameEffects
	assert_true(E.apply([{"set_flag": "a"}, {"give_item": "cap", "count": 4}, {"add_xp": 20},
		{"add_rep": "birds", "amount": 3}, {"modify_stat": "energy", "amount": -10},
		{"add_buff": "catnip"}, {"counter": "gifts", "amount": 2}, {"add_skill_points": 1}]))
	assert_true(bool(GameState.get_flag(&"a")))
	assert_eq(GameState.get_caps(), 4)
	assert_eq(GameState.xp, 20)
	assert_eq(GameState.get_reputation(&"birds"), 3)
	assert_near(GameState.get_stat(&"energy"), 90.0)
	assert_true(GameState.has_buff(&"catnip"))
	assert_eq(GameState.get_counter(&"gifts"), 2)
	assert_eq(GameState.skill_points, 2)
	assert_false(E.apply([{"take_item": "cap", "count": 99}]), "fails without enough caps")
	E.apply({"start_quest": "fx_interact"})
	assert_true(QuestManager.is_active(&"fx_interact"))
	E.apply({"advance_quest": "fx_interact", "objective": "scratch"})
	assert_true(QuestManager.is_objective_done(&"fx_interact", &"scratch"))
	E.apply({"advance_time": 2.0})
	assert_near(TimeOfDay.hour, 12.0)
	E.apply({"report": "catch_prey", "data": {"prey_kind": "pigeon"}})
	E.apply([{"if": {"flag": "a"}, "then": [{"set_flag": "b"}], "else": [{"set_flag": "c"}]}])
	assert_true(bool(GameState.get_flag(&"b")))
	assert_false(bool(GameState.get_flag(&"c")))
	assert_true(E.validate([{"set_flag": "a", "give_item": "b"}]).size() >= 1, "two types")
	assert_true(E.validate([{"teleport": "moon"}]).size() >= 1)
	assert_true(E.validate([{"give_item": "fish", "count": 2}]).is_empty())


func test_save_provider_round_trip() -> void:
	DialogueManager.start(&"fx_ba_tu")
	DialogueManager.advance()
	DialogueManager.choose(2)
	DialogueManager.stop()
	var d := DialogueManager.get_save_data()
	DialogueManager.reset_state()
	assert_false(DialogueManager.has_seen(&"fx_ba_tu"))
	DialogueManager.load_save_data(JSON.parse_string(JSON.stringify(d)))
	assert_true(DialogueManager.has_seen(&"fx_ba_tu"))
	DialogueManager.start(&"fx_ba_tu")
	DialogueManager.advance()
	assert_eq(DialogueManager.get_choices().size(), 3, "once-choice memory persisted")
	DialogueManager.stop()
