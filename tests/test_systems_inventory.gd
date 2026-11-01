extends "res://tests/fixtures/systems_test_base.gd"
## Inventory, mouth slot, stacks, eating/using, trading, equipment.

func test_items_json_contains_gdd_items() -> void:
	for id in ["fish", "cap", "letter", "key", "lucky_cat_figurine", "leg_band", "toy_mouse", "yarn",
			"dried_fish", "shrimp", "gio_lua", "pate_crust", "quail_egg", "mooncake_crumb"]:
		assert_true(GameState.item_exists(StringName(id)), id)
	for i in range(1, 13):
		var mid := "memory_%02d" % i
		assert_true(GameState.item_exists(StringName(mid)), mid)
		assert_eq(String(GameState.get_item_def(StringName(mid))["category"]), "memory")
	for id in GameState.get_all_item_ids():
		var d := GameState.get_item_def(StringName(id))
		for k in ["name_key", "desc_key", "icon", "mouth", "stack", "food", "mesh", "category", "value"]:
			assert_true(d.has(k), "%s.%s" % [id, k])
		if float(d["food"]) > 0.0:
			assert_eq(String(d["category"]), "food", id)


func test_add_remove_count() -> void:
	capture(&"inventory_changed")
	assert_eq(GameState.add_item(&"cap", 5), 5)
	assert_true(GameState.has_item(&"cap", 5))
	assert_false(GameState.has_item(&"cap", 6))
	assert_false(GameState.remove_item(&"cap", 6))
	assert_true(GameState.remove_item(&"cap", 2))
	assert_eq(GameState.item_count(&"cap"), 3)
	assert_eq(events_named(&"inventory_changed").size(), 2)


func test_stack_limits() -> void:
	assert_eq(GameState.add_item(&"memory_01", 3), 1, "unique photo stacks to 1")
	assert_eq(GameState.add_item(&"cap", 2000), 999)
	assert_eq(GameState.add_item(&"catnip", 9), 5)


func test_mouth_slot() -> void:
	capture(&"mouth_item_changed")
	assert_eq(GameState.mouth_item, &"")
	GameState.add_item(&"fish")
	assert_eq(GameState.mouth_item, &"fish", "mouth item goes straight to the mouth")
	GameState.add_item(&"letter")
	assert_eq(GameState.mouth_item, &"fish", "mouth busy → letter goes to the den stash")
	assert_true(GameState.has_item(&"letter"))
	assert_true(GameState.set_mouth_item(&"letter"))
	assert_eq(GameState.mouth_item, &"letter")
	assert_false(GameState.set_mouth_item(&"cap"), "caps aren't carried in the mouth")
	assert_false(GameState.set_mouth_item(&"key"), "not owned")
	GameState.add_item(&"cap", 3)
	assert_eq(GameState.mouth_item, &"letter", "stash items never touch the mouth")
	assert_true(events_named(&"mouth_item_changed").size() >= 2)


func test_drop_and_remove_clear_mouth() -> void:
	capture(&"item_dropped")
	GameState.add_item(&"toy_mouse")
	assert_eq(GameState.drop_mouth_item(), &"toy_mouse")
	assert_eq(GameState.mouth_item, &"")
	assert_false(GameState.has_item(&"toy_mouse"))
	assert_eq(events_named(&"item_dropped").size(), 1)
	assert_eq(GameState.drop_mouth_item(), &"")
	GameState.add_item(&"key")
	GameState.remove_item(&"key")
	assert_eq(GameState.mouth_item, &"")


func test_eat_food_item() -> void:
	capture(&"food_eaten")
	GameState.set_stat(&"hunger", 40.0)
	GameState.add_item(&"fish")
	assert_true(GameState.use_item(&"fish"))
	assert_near(GameState.get_stat(&"hunger"), 75.0)
	assert_false(GameState.has_item(&"fish"))
	assert_eq(GameState.mouth_item, &"")
	assert_eq(events_named(&"food_eaten").size(), 1)
	GameState.grant_skill(&"bung_khoe")
	GameState.set_stat(&"hunger", 10.0)
	GameState.eat(20.0)
	assert_near(GameState.get_stat(&"hunger"), 35.0, 0.001, "food_value 1.25")


func test_well_fed_buff() -> void:
	GameState.set_stat(&"hunger", 70.0)
	GameState.eat(30.0)
	assert_true(GameState.has_buff(&"well_fed"))


func test_use_consumables_and_toys() -> void:
	GameState.add_item(&"skill_tonic")
	var sp := GameState.skill_points
	assert_true(GameState.use_item(&"skill_tonic"))
	assert_eq(GameState.skill_points, sp + 1)
	assert_false(GameState.has_item(&"skill_tonic"))
	GameState.add_item(&"yarn")
	assert_true(GameState.use_item(&"yarn"))
	assert_true(GameState.has_buff(&"playful"))
	assert_true(GameState.has_item(&"yarn"), "toys are kept")
	assert_false(GameState.use_item(&"letter"), "not owned")
	GameState.add_item(&"letter")
	assert_false(GameState.use_item(&"letter"), "no use")


func test_trading() -> void:
	GameState.add_item(&"cap", 30)
	assert_eq(GameState.get_buy_price(&"collar_red"), 15)
	assert_true(GameState.buy_item(&"collar_red"))
	assert_eq(GameState.get_caps(), 15)
	assert_false(GameState.buy_item(&"collar_red"), "unique stack")
	assert_false(GameState.buy_item(&"collar_jade"), "too expensive")
	GameState.add_item(&"silver_spoon")
	var p := GameState.sell_item(&"silver_spoon")
	assert_eq(p, 6)
	assert_eq(GameState.get_caps(), 21)
	GameState.add_item(&"lucky_cat_figurine")
	assert_eq(GameState.sell_item(&"lucky_cat_figurine"), 0, "Grandma's figurine is not for sale")
	GameState.grant_skill(&"ban_cua_pho")
	assert_true(GameState.get_buy_price(&"collar_jade") < 40)


func test_equipment_unequips_when_removed() -> void:
	GameState.add_item(&"collar_red")
	assert_true(GameState.equip_item(&"collar_red"))
	assert_eq(GameState.get_equipped(&"collar"), &"collar_red")
	assert_false(GameState.equip_item(&"fish"), "not equippable")
	GameState.remove_item(&"collar_red")
	assert_eq(GameState.get_equipped(&"collar"), &"")


func test_memory_counter() -> void:
	GameState.add_item(&"memory_03")
	GameState.add_item(&"memory_07")
	assert_eq(GameState.get_counter(&"memories_found"), 2)
	assert_eq(GameState.count_items_in_category(&"memory"), 2)


func test_flags() -> void:
	capture(&"flag_changed")
	assert_eq(GameState.get_flag(&"x"), false)
	assert_eq(GameState.get_flag(&"x", 7), 7)
	GameState.set_flag(&"x")
	GameState.set_flag(&"x")
	assert_eq(events_named(&"flag_changed").size(), 1, "no duplicate signal")
	GameState.set_flag(&"count", 3)
	assert_eq(GameState.get_flag(&"count"), 3)
	GameState.clear_flag(&"x")
	assert_false(GameState.has_flag(&"x"))
