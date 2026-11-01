extends "res://tests/fixtures/systems_test_base.gd"
## XP curve, levels, skill points, attributes, skills (prereqs/costs), modifiers.

func test_xp_curve_documented_values() -> void:
	var expect := [0, 0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700]
	for lvl in range(1, 11):
		assert_eq(GameState.xp_for_level(lvl), expect[lvl], "level %d" % lvl)


func test_level_ups_grant_points() -> void:
	capture(&"level_up")
	assert_eq(GameState.level, 1)
	assert_eq(GameState.skill_points, 1, "starts with one skill point")
	GameState.add_xp(99, "test")
	assert_eq(GameState.level, 1)
	assert_eq(GameState.get_xp_to_next_level(), 1)
	GameState.add_xp(160, "test")  # 259 → level 3
	assert_eq(GameState.level, 3)
	assert_eq(GameState.skill_points, 3)
	assert_eq(GameState.attribute_points, 2)
	assert_eq(events_named(&"level_up").size(), 2)
	assert_near(GameState.get_level_progress(), 9.0 / 200.0, 0.001)


func test_max_level_and_milestones() -> void:
	GameState.add_xp(100000, "test")
	assert_eq(GameState.level, GameState.MAX_LEVEL)
	assert_eq(GameState.skill_points, 1 + 9 + 2, "1 start + 9 levels + milestones 5 & 10")
	assert_eq(GameState.attribute_points, 9)
	assert_near(GameState.get_level_progress(), 1.0)
	assert_eq(GameState.get_xp_to_next_level(), 0)


func test_attributes_and_raise() -> void:
	assert_eq(GameState.get_attribute(&"agility"), 3)
	assert_eq(GameState.get_attribute(&"charm"), 2)
	assert_false(GameState.raise_attribute(&"charm"), "no points")
	GameState.add_attribute_points(1)
	assert_true(GameState.raise_attribute(&"charm"))
	assert_eq(GameState.get_attribute(&"charm"), 3)
	GameState.set_attribute(&"charm", 99)
	assert_eq(GameState.get_attribute(&"charm"), 10, "clamped to 10")
	GameState.add_attribute_points(1)
	assert_false(GameState.raise_attribute(&"charm"), "already max")


func test_skill_data_has_at_least_16_skills_in_5_trees() -> void:
	var skills := GameState.get_all_skills()
	assert_true(skills.size() >= 16, "skills: %d" % skills.size())
	var trees := {}
	for id: String in skills:
		trees[String(skills[id]["tree"])] = true
	for t in ["agility", "stealth", "charm", "hunting", "survival"]:
		assert_true(trees.has(t), "tree " + t)
		assert_true(GameState.get_skills_in_tree(StringName(t)).size() >= 3, "≥3 skills in " + t)


func test_skill_definitions_are_consistent() -> void:
	var mods := GameState.get_modifier_names()
	var skills := GameState.get_all_skills()
	for id: String in skills:
		var s: Dictionary = skills[id]
		for m: String in s["effects"]:
			assert_true(m in mods, "%s: unknown modifier %s" % [id, m])
		for c: Dictionary in s.get("conditional_effects", []):
			for m: String in c["effects"]:
				assert_true(m in mods, "%s: unknown conditional modifier %s" % [id, m])
			assert_true(GameConditions.validate(c["when"]).is_empty(), id + " conditional when")
		for r: String in s["requires"]:
			assert_true(skills.has(r), "%s requires unknown %s" % [id, r])
			assert_true(int(skills[r]["tier"]) < int(s["tier"]), "%s prereq %s must be lower tier" % [id, r])
		assert_true(int(s["cost"]) >= 1)
	for b: String in ["catnip", "playful", "sharp_claws", "well_fed", "warm_nap", "groomed"]:
		assert_false(GameState.get_buff_def(StringName(b)).is_empty(), "buff " + b)


func test_unlock_skill_rules() -> void:
	capture(&"skill_unlocked")
	assert_eq(GameState.get_skill_state(&"nhay_xa"), &"available")
	assert_eq(GameState.get_skill_state(&"dap_mem"), &"locked", "needs nhay_xa")
	assert_true(GameState.unlock_skill(&"nhay_xa"))
	assert_eq(GameState.skill_points, 0)
	assert_false(GameState.unlock_skill(&"nhay_xa"), "already owned")
	assert_false(GameState.unlock_skill(&"dap_mem"), "no points left")
	assert_true(GameState.get_skill_lock_reason(&"dap_mem") != "")
	GameState.add_skill_points(1)
	assert_true(GameState.unlock_skill(&"dap_mem"))
	assert_true(GameState.has_skill(&"dap_mem"))
	assert_eq(events_named(&"skill_unlocked").size(), 2)
	# Tier-3: level 4 and agility 5 plus 3 points
	GameState.add_skill_points(3)
	assert_false(GameState.unlock_skill(&"bat_tuong"), "level/attribute gate")
	GameState.add_xp(450)
	GameState.set_attribute(&"agility", 5)
	assert_true(GameState.unlock_skill(&"bat_tuong"))
	assert_true(GameState.has_ability(&"wall_jump"))


func test_requested_modifiers_exist_with_sane_defaults() -> void:
	var expect := {"jump_distance": 1.06, "noise_mult": 0.96, "sprint_speed": 1.04, "climb_speed": 1.06,
		"night_vision": 0.0, "charm_bonus": 0.0, "energy_regen": 1.0}
	for m: String in expect:
		assert_near(GameState.get_modifier(StringName(m)), expect[m], 0.0001, m)


func test_modifiers_stack_skills_attributes_buffs_equipment() -> void:
	GameState.grant_skill(&"nhay_xa")
	assert_near(GameState.get_modifier(&"jump_distance"), 1.06 + 0.15, 0.0001)
	GameState.set_attribute(&"agility", 6)
	assert_near(GameState.get_modifier(&"jump_distance"), 1.0 + 0.15 + 0.15, 0.0001)
	GameState.add_buff(&"catnip")
	assert_near(GameState.get_modifier(&"jump_distance"), 1.4, 0.0001)
	GameState.grant_skill(&"mat_dem")
	assert_near(GameState.get_modifier(&"night_vision"), 1.0)
	GameState.grant_skill(&"buoc_nhung")
	var noise := GameState.get_modifier(&"noise_mult")
	GameState.add_item(&"collar_bell")
	assert_true(GameState.equip_item(&"collar_bell"))
	assert_near(GameState.get_modifier(&"noise_mult"), noise + 0.15, 0.0001, "bell collar is noisy")
	assert_near(GameState.get_modifier(&"charm_bonus"), 1.0 - 1.0, 0.0001, "bell +1, catnip −1")
	GameState.remove_buff(&"catnip")
	assert_eq(GameState.get_effective_attribute(&"charm"), 3, "charm 2 + bell 1")


func test_modifiers_are_clamped() -> void:
	GameState.set_attribute(&"stealth", 10)
	for s in ["buoc_nhung", "lan_tron", "bong_ma"]:
		GameState.grant_skill(StringName(s))
	assert_true(GameState.get_modifier(&"noise_mult") >= 0.15)
	assert_true(GameState.get_modifier(&"detection_mult") >= 0.2)


func test_conditional_skill_effect_at_night() -> void:
	GameState.grant_skill(&"bong_dem")
	TimeOfDay.set_hour(12.0)
	var day := GameState.get_modifier(&"detection_mult")
	TimeOfDay.set_hour(22.0)
	var night := GameState.get_modifier(&"detection_mult")
	assert_near(day - night, 0.25, 0.0001, "night bonus only at night")


func test_buff_expires_with_game_time() -> void:
	GameState.add_buff(&"sharp_claws", 1.0)
	assert_true(GameState.has_buff(&"sharp_claws"))
	assert_near(GameState.get_buff_remaining_minutes(&"sharp_claws"), 60.0)
	TimeOfDay.advance_hours(1.5)
	GameState.simulate(0.01)
	assert_false(GameState.has_buff(&"sharp_claws"))


func test_max_stat_skill() -> void:
	GameState.add_skill_points(1)
	GameState.grant_skill(&"ngu_sau")
	GameState.grant_skill(&"suc_ben")
	assert_near(GameState.get_stat_max(&"energy"), 120.0)
	GameState.set_stat(&"energy", 500.0)
	assert_near(GameState.get_stat(&"energy"), 120.0)


func test_reputation_and_tiers() -> void:
	capture(&"reputation_changed")
	GameState.add_reputation(&"humans", 30)
	assert_eq(GameState.get_reputation(&"humans"), 31, "charm 2 → rep_gain 1.02 → 30.6 → 31")
	assert_eq(GameState.get_reputation_tier(&"humans"), &"friendly")
	GameState.add_reputation(&"birds", -60)
	assert_eq(GameState.get_reputation(&"birds"), -60, "losses not scaled")
	assert_eq(GameState.get_reputation_tier(&"birds"), &"hostile")
	GameState.add_reputation(&"birds", -500)
	assert_eq(GameState.get_reputation(&"birds"), -100)
	assert_eq(events_named(&"reputation_changed").size(), 3)


func test_locations_collectibles_territory() -> void:
	capture(&"location_discovered")
	assert_true(GameState.discover_location(&"lake", "Hồ Gương"))
	assert_false(GameState.discover_location(&"lake", "Hồ Gương"))
	assert_eq(GameState.xp, 15)
	assert_eq(events_named(&"location_discovered").size(), 1)
	assert_true(GameState.mark_collectible(&"memory_01"))
	assert_false(GameState.mark_collectible(&"memory_01"))
	assert_eq(GameState.count_collectibles("memory_"), 1)
	assert_true(GameState.mark_territory(&"roof_1"))
	assert_false(GameState.mark_territory(&"roof_1"))
	assert_eq(GameState.get_counter(&"territory_marked"), 1)


func test_location_polling_from_markers() -> void:
	spawn_player(Vector3(0, 0, 0))
	var m := spawn_marker("fx_market", Vector3(3, 0, 0), &"location", &"location_id")
	m.set_meta(&"display_name_key", "LOC_MARKET")
	m.set_meta(&"radius", 5.0)
	GameState._poll_locations()
	assert_true(GameState.is_location_discovered(&"fx_market"))
	assert_eq(GameState.current_area, &"fx_market")


func test_knock_achievement() -> void:
	capture(&"achievement_unlocked")
	for i in 20:
		GameState.register_knock(StringName("cup_%d" % i))
	GameState.register_knock(&"cup_0")
	assert_eq(GameState.get_counter(&"knocked_unique"), 20)
	assert_eq(GameState.get_counter(&"knocked_objects"), 21)
	assert_true(GameState.has_achievement(&"knock_it_off"))
	assert_true(bool(GameState.get_flag(&"ach_knock_it_off")))
	assert_eq(events_named(&"achievement_unlocked").size(), 1)


func test_prey_catch() -> void:
	capture(&"prey_caught")
	GameState.register_prey_catch(&"mouse")
	assert_eq(GameState.get_counter(&"prey_mouse"), 1)
	assert_eq(GameState.xp, 10)
	GameState.grant_skill(&"vua_san_moi")
	GameState.register_prey_catch(&"mouse")
	assert_eq(GameState.xp, 25, "prey_xp_mult 1.5")
	assert_eq(events_named(&"prey_caught").size(), 2)
