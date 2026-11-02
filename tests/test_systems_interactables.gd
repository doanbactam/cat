extends "res://tests/fixtures/systems_test_base.gd"
## Scene-level tests of Interactable subclasses with a fake player in the tree (+ Jolt physics
## for QuestTrigger, auto-collect caps and Pushable "knocked off a ledge").

func test_base_interactable_defaults() -> void:
	var it := Interactable.new()
	it.name = "Bell"
	spawn(it)
	assert_true(it.is_in_group(&"interactable"))
	assert_true(it.is_in_group(&"quest_target"))
	assert_eq(it.collision_layer, 1 << 4, "layer 5 interactable")
	assert_eq(it.target_id, &"Bell")
	var shapes := it.get_children().filter(func(c: Node) -> bool: return c is CollisionShape3D)
	assert_eq(shapes.size(), 1, "auto collision shape")
	assert_eq(it.get_prompt(null), tr("PROMPT_INTERACT").format({"name": tr("PROP_OBJECT")}))
	assert_eq(it.get_display_name(), tr("PROP_OBJECT"), "never shows raw node names")


func test_distance_requirement_cooldown_one_shot() -> void:
	var p := spawn_player(Vector3(0, 0, 0))
	var it := Interactable.new()
	it.requirement = {"attribute": "charm", "gte": 3}
	it.one_shot = true
	it.first_use_xp = 7
	it.persistent_id = &"fx_once"
	spawn(it)
	it.global_position = Vector3(3, 0, 0)
	assert_false(it.can_interact(p), "too far")
	it.global_position = Vector3(0.8, 0, 0)
	assert_false(it.can_interact(p), "charm too low")
	assert_true(it.get_prompt(p).contains(tr("ATTR_CHARM")), "lock reason in prompt")
	GameState.set_attribute(&"charm", 3)
	assert_true(it.can_interact(p))
	var fired := [0]
	it.used.connect(func(_pl: Node) -> void: fired[0] += 1)
	it.interact(p)
	assert_eq(fired[0], 1)
	assert_eq(GameState.xp, 7)
	assert_false(it.enabled, "one shot")
	it.interact(p)
	assert_eq(fired[0], 1)
	var again := Interactable.new()
	again.one_shot = true
	again.persistent_id = &"fx_once"
	spawn(again)
	assert_false(again.enabled, "one_shot state persisted in world state")


func test_pickup_mouth_item_and_swap() -> void:
	var p := spawn_player()
	capture(&"item_picked_up")
	var root := Node3D.new()
	spawn(root)
	var fish := PickupItem.new()
	fish.item_id = &"fish"
	root.add_child(fish)
	assert_eq(fish.verb, &"pickup")
	assert_eq(fish.get_prompt(p), tr("PROMPT_PICKUP_MOUTH").format({"name": GameState.get_item_name(&"fish", true)}))
	assert_not_null(fish.get_highlight_node(), "procedural/GLB visual created")
	fish.interact(p)
	assert_eq(GameState.mouth_item, &"fish")
	assert_true(p.actions.has(&"pickup"))
	await tree.process_frame
	assert_false(is_instance_valid(fish), "freed after pickup")
	var letter := PickupItem.new()
	letter.item_id = &"letter"
	root.add_child(letter)
	letter.global_position = Vector3(0.5, 0, 0)
	assert_eq(letter.get_prompt(p), tr("PROMPT_SWAP").format({"held": GameState.get_item_name(&"fish", true), "name": GameState.get_item_name(&"letter", true)}))
	assert_true(letter.can_interact(p))
	letter.interact(p)
	assert_eq(GameState.mouth_item, &"letter")
	assert_false(GameState.has_item(&"fish"), "fish dropped")
	var dropped := root.get_children().filter(func(c: Node) -> bool: return c is PickupItem and c.item_id == &"fish")
	assert_eq(dropped.size(), 1, "dropped fish is a new pickup")
	assert_eq(events_named(&"item_picked_up").size(), 2)


func test_pickup_no_swap_blocks() -> void:
	var p := spawn_player()
	GameState.add_item(&"key")
	var yarn := PickupItem.new()
	yarn.item_id = &"yarn"
	yarn.swap_if_mouth_full = false
	spawn(yarn)
	assert_false(yarn.can_interact(p))
	assert_eq(yarn.get_lock_reason(p), tr("REQ_MOUTH_EMPTY"))


func test_pickup_stash_persistent_and_respawn() -> void:
	var p := spawn_player()
	var caps := PickupItem.new()
	caps.item_id = &"cap"
	caps.amount = 3
	caps.persistent_id = &"fx_caps_1"
	spawn(caps)
	caps.interact(p)
	assert_eq(GameState.get_caps(), 3)
	await tree.process_frame
	var again := PickupItem.new()
	again.item_id = &"cap"
	again.persistent_id = &"fx_caps_1"
	spawn(again)
	await tree.process_frame
	assert_false(is_instance_valid(again), "picked persistent items stay gone")
	var shrimp := PickupItem.new()
	shrimp.item_id = &"shrimp"
	shrimp.respawn_hours = 2.0
	shrimp.cooldown = 0.0
	spawn(shrimp)
	shrimp.interact(p)
	assert_false(shrimp.visible)
	assert_false(shrimp.can_interact(p))
	TimeOfDay.advance_hours(2.5)
	assert_true(shrimp.visible, "respawned")
	GameState.drop_mouth_item()
	assert_true(shrimp.can_interact(p))


func test_spawn_dropped_snaps_to_ground() -> void:
	var ground := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = Vector3(4, 0.2, 4)
	cs.shape = b
	ground.add_child(cs)
	spawn(ground)
	ground.global_position = Vector3(0, 0.4, 0)  # top at y = 0.5
	await tree.physics_frame
	await tree.physics_frame
	var host := Node3D.new()
	spawn(host)
	var d := PickupItem.spawn_dropped(&"toy_mouse", Transform3D(Basis.IDENTITY, Vector3(0.3, 1.5, 0)), host)
	assert_near(d.global_position.y, 0.5, 0.01)


func test_talkable_delivers_and_starts_dialogue() -> void:
	var p := spawn_player()
	capture(&"dialogue_started")
	var npc := Node3D.new()
	npc.name = "Crow"
	npc.set_meta(&"npc_id", "fx_crow")
	spawn(npc)
	var t := Talkable.new()
	t.dialogue_id = &"fx_bong_hi"
	npc.add_child(t)
	assert_eq(t.speaker_id, &"fx_crow", "speaker id from parent meta")
	assert_eq(t.target_id, &"fx_crow")
	assert_eq(t.get_prompt(p), tr("PROMPT_TALK").format({"name": "NPC_FX_CROW"}))
	QuestManager.start_quest(&"fx_collect")
	GameState.add_item(&"cap", 5)
	GameState.add_item(&"fish")
	t.interact(p)
	assert_true(QuestManager.is_completed(&"fx_collect"), "fish delivered on talk")
	assert_true(DialogueManager.is_active())
	assert_eq(events_named(&"dialogue_started")[0][2], &"fx_crow")
	assert_false(t.can_interact(p), "busy while talking")
	DialogueManager.advance()
	var silent := Talkable.new()
	silent.speaker_id = &"fx_bong"
	spawn(silent)
	QuestManager.start_quest(&"fx_chain_next", true)
	await tree.create_timer(0.6).timeout  # cooldown of the first talkable irrelevant; new node
	silent.interact(p)
	assert_true(QuestManager.is_completed(&"fx_chain_next"), "no dialogue → talk_to reported")


func test_nap_spot() -> void:
	var p := spawn_player()
	var spot := NapSpot.new()
	spot.name = "RoofBox"
	spot.sleep_hours = 3.0
	spot.wake_offset = Vector3(0, 0, 0.5)
	spawn(spot)
	spot.global_position = Vector3(2, 8, 1)
	p.global_position = Vector3(2, 8, 1.4)
	assert_eq(spot.spot_id, &"roof_box")
	assert_true(spot.is_in_group(&"nap_spot"))
	GameState.set_stat(&"energy", 20.0)
	spot.interact(p)
	assert_near(TimeOfDay.hour, 13.0)
	assert_true(GameState.get_stat(&"energy") > 85.0)
	assert_eq(GameState.get_last_nap_spot(), &"roof_box")
	assert_true((GameState.get_last_nap_transform() as Transform3D).origin.is_equal_approx(Vector3(2, 8, 1.5)))
	assert_true(p.actions.has(&"lie_down"))
	var until := NapSpot.new()
	until.sleep_until_hour = 6.0
	spawn(until)
	await tree.create_timer(0.55).timeout
	until.interact(null)
	assert_eq(TimeOfDay.day, 2)
	assert_near(TimeOfDay.hour, 6.0)


func test_food_source_servings_refill_and_stealing() -> void:
	var p := spawn_player()
	capture(&"player_noise")
	var bowl := FoodSource.new()
	bowl.name = "BaTuBowl"
	bowl.food_amount = 30.0
	bowl.servings = 1
	bowl.refill_hours = 12.0
	bowl.cooldown = 0.0
	spawn(bowl)
	GameState.set_stat(&"hunger", 40.0)
	assert_eq(bowl.verb, &"eat")
	bowl.interact(p)
	assert_near(GameState.get_stat(&"hunger"), 70.0)
	assert_false(bowl.can_interact(p), "empty")
	assert_eq(bowl.get_lock_reason(p), tr("REQ_EMPTY"))
	TimeOfDay.advance_hours(12.5)
	assert_true(bowl.can_interact(p), "refilled")
	var stall := FoodSource.new()
	stall.is_stealing = true
	stall.food_amount = 10.0
	stall.cooldown = 0.0
	spawn(stall)
	stall.interact(p)
	assert_eq(GameState.get_reputation(&"humans"), -2)
	assert_eq(events_named(&"player_noise").size(), 1)
	var vendor := FoodSource.new()
	vendor.gives_item = &"fish"
	vendor.required_charm = 3
	vendor.cooldown = 0.0
	spawn(vendor)
	assert_false(vendor.can_interact(p))
	GameState.set_attribute(&"charm", 3)
	assert_true(vendor.can_interact(p))
	vendor.interact(p)
	assert_eq(GameState.mouth_item, &"fish")
	var water := FoodSource.new()
	water.is_water = true
	water.servings = -1
	water.cooldown = 0.0
	spawn(water)
	assert_eq(water.verb, &"drink")
	GameState.set_stat(&"energy", 50.0)
	water.interact(p)
	water.interact(p)
	assert_near(GameState.get_stat(&"energy"), 58.0)
	# persistence of servings
	var bowl2 := FoodSource.new()
	bowl2.name = "BaTuBowl"
	bowl2.servings = 1
	bowl2.refill_hours = 12.0
	spawn(bowl2)
	assert_eq(bowl2.get_servings_left(), 1, "state shared through world state (refilled)")


func test_scratch_post_and_territory_spot() -> void:
	var p := spawn_player()
	var post := ScratchPost.new()
	post.name = "BanyanTrunk"
	post.marks_territory = true
	post.cooldown = 0.0
	spawn(post)
	post.interact(p)
	assert_true(GameState.has_buff(&"sharp_claws"))
	assert_true(GameState.is_territory_marked(&"banyan_trunk"))
	var xp_after_first := GameState.xp
	assert_eq(xp_after_first, 5 + 15)
	post.interact(p)
	assert_eq(GameState.xp, xp_after_first, "daily xp only once, territory once")
	var visual := Node3D.new()
	visual.name = "Scent"
	var spot := TerritorySpot.new()
	spot.spot_id = &"roof_ridge"
	spot.add_child(visual)
	spot.marked_visual = ^"Scent"
	spawn(spot)
	assert_false(visual.visible)
	assert_true(spot.can_interact(p))
	spot.interact(p)
	assert_true(visual.visible)
	assert_true(spot.is_marked())
	assert_false(spot.can_interact(p))
	assert_eq(spot.get_lock_reason(p), tr("REQ_ALREADY_MARKED"))
	assert_true(GameState.get_reputation(&"rooftop_cats") >= 5)


func test_quest_trigger_enter_with_physics() -> void:
	var p := spawn_player(Vector3(0, 0, -10))
	capture(&"area_entered")
	QuestManager.start_quest(&"fx_reach")
	var trig := QuestTrigger.new()
	trig.location_id = &"fx_lake"
	trig.display_name_key = "LOC_LAKE"
	spawn(trig)
	trig.global_position = Vector3(0, 0, 0)
	assert_false(trig.is_in_group(&"interactable"), "enter triggers aren't focusable")
	assert_eq(trig.collision_layer, 1 << 9)
	for i in 4:
		await tree.physics_frame
	p.global_position = Vector3(0, 0.2, 0)
	for i in 6:
		await tree.physics_frame
	assert_eq(events_named(&"area_entered").size(), 1, "body_entered fired")
	assert_true(GameState.is_location_discovered(&"fx_lake"))
	assert_true(QuestManager.is_completed(&"fx_reach"))


func test_quest_trigger_interact_mode() -> void:
	var p := spawn_player()
	QuestManager.start_quest(&"fx_gated")
	TimeOfDay.set_hour(23.0)
	var t := QuestTrigger.new()
	t.mode = QuestTrigger.Mode.INTERACT
	t.event = &"fx_race"
	t.event_data = {"track": "rooftops"}
	t.set_flag = &"fx_race_started"
	t.trigger_once = true
	t.required_quest_active = &"fx_gated"
	spawn(t)
	assert_true(t.is_in_group(&"interactable"))
	t.interact(p)
	assert_true(QuestManager.is_objective_done(&"fx_gated", &"race"))
	assert_true(bool(GameState.get_flag(&"fx_race_started")))
	assert_false(t.fire(), "once")


func test_collectible_memory_and_caps_touch() -> void:
	var p := spawn_player(Vector3(0, 0, -10))
	capture(&"collectible_found")
	var mem := Collectible.new()
	mem.collectible_id = &"memory_04"
	mem.position = Vector3(0.5, 0, -10)
	spawn(mem)
	assert_eq(mem.item_id, &"memory_04")
	mem.interact(p)
	assert_true(GameState.has_item(&"memory_04"))
	assert_true(GameState.is_collectible_found(&"memory_04"))
	assert_eq(GameState.xp, 40)
	await tree.process_frame
	var dup := Collectible.new()
	dup.collectible_id = &"memory_04"
	spawn(dup)
	await tree.process_frame
	assert_false(is_instance_valid(dup), "found collectibles don't come back")
	var caps := Collectible.new()
	caps.collectible_id = &"caps_alley_1"
	caps.kind = &"caps"
	caps.amount = 4
	caps.auto_collect_on_touch = true
	spawn(caps)
	for i in 4:
		await tree.physics_frame
	p.global_position = Vector3(0, 0.1, 0)
	for i in 6:
		await tree.physics_frame
	assert_eq(GameState.get_caps(), 4, "auto-collected by touch")
	assert_eq(events_named(&"collectible_found").size(), 2)


func _make_ledge() -> void:
	# Floor at y=0 and a 1 m high table/ledge (top at y = 1.0) spanning x ∈ [-0.5, 0.5].
	for spec: Array in [[Vector3(10, 0.2, 10), Vector3(0, -0.1, 0)], [Vector3(1, 1, 1), Vector3(0, 0.5, 0)]]:
		var sb := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var b := BoxShape3D.new()
		b.size = spec[0]
		cs.shape = b
		sb.add_child(cs)
		spawn(sb)
		sb.global_position = spec[1]


func _make_cup() -> Pushable:
	var cup := Pushable.new()
	cup.name = "Cup"
	cup.object_id = &"fx_cup"
	cup.mass = 0.25
	spawn(cup)
	return cup


func test_pushable_knocked_off_ledge() -> void:
	capture(&"object_knocked_off")
	capture(&"player_noise")
	QuestManager.register_quest({"id": "fx_knock1", "objectives": [{"id": "k", "type": "knock_objects", "count": 1}]})
	QuestManager.start_quest(&"fx_knock1")
	_make_ledge()
	var cup := _make_cup()
	cup.global_position = Vector3(0.38, 1.0, 0)
	assert_true(cup.is_in_group(&"pushable"))
	assert_eq(cup.collision_layer, 1 << 3, "props_dynamic layer")
	assert_not_null(cup.get_node_or_null("KnockArea"), "interaction area for the knock verb")
	for i in 10:
		await tree.physics_frame
	cup.knock(Vector3.RIGHT, 1.0)
	var t := 0
	while events_named(&"object_knocked_off").is_empty() and t < 240:
		await tree.physics_frame
		t += 1
	assert_eq(events_named(&"object_knocked_off").size(), 1, "fell off the ledge (frames: %d, y: %.2f)" % [t, cup.global_position.y])
	if not events_named(&"object_knocked_off").is_empty():
		assert_near(float(events_named(&"object_knocked_off")[0][3]), 1.0, 0.15, "fall height ≈ 1 m")
	assert_true(cup.global_position.y < 0.2, "on the floor")
	assert_eq(GameState.get_counter(&"knocked_unique"), 1)
	assert_true(QuestManager.is_completed(&"fx_knock1"))
	assert_true(events_named(&"player_noise").size() >= 2, "swipe + landing noise")


func test_pushable_nudged_on_flat_ground_does_not_count() -> void:
	capture(&"object_knocked_off")
	_make_ledge()
	var cup := _make_cup()
	cup.global_position = Vector3(-3, 0.0, 0)
	for i in 10:
		await tree.physics_frame
	cup.knock(Vector3.LEFT, 0.5)
	for i in 90:
		await tree.physics_frame
	assert_eq(events_named(&"object_knocked_off").size(), 0)
	assert_false(cup.is_armed(), "disarmed after resting")


func test_pushable_knock_area_uses_player_direction() -> void:
	var p := spawn_player(Vector3(-0.3, 1.0, 0))
	capture(&"object_knocked_off")
	_make_ledge()
	var cup := _make_cup()
	cup.global_position = Vector3(0.3, 1.0, 0)
	for i in 10:
		await tree.physics_frame
	var area := cup.get_node("KnockArea") as Interactable
	assert_eq(area.verb, &"knock")
	area.interact(p)
	assert_true(p.actions.has(&"knock"))
	var t := 0
	while events_named(&"object_knocked_off").is_empty() and t < 240:
		await tree.physics_frame
		t += 1
	assert_eq(events_named(&"object_knocked_off").size(), 1, "pushed away from the cat, off the ledge")


func test_prompts_use_sentence_case_item_names() -> void:
	var loc := TranslationServer.get_locale()
	var t := Translation.new()
	t.locale = "vi"
	t.add_message("ITEM_CAP", "Nắp chai")
	t.add_message("ITEM_KEY", "Chìa khóa của Bin")
	t.add_message("PROMPT_PICKUP", "Nhặt {name}")
	t.add_message("PROMPT_SLEEP", "Ngủ một giấc ({hours} giờ)")
	TranslationServer.add_translation(t)
	TranslationServer.set_locale("vi")
	var cap := PickupItem.new()
	cap.item_id = &"cap"
	spawn(cap)
	assert_eq(cap.get_prompt(null), "Nhặt nắp chai")
	assert_eq(GameState.get_item_name(&"key", true), "Chìa khóa của Bin", "proper names keep their capital")
	var nap := NapSpot.new()
	spawn(nap)
	assert_eq(nap.get_prompt(null), "Ngủ một giấc (2 giờ)")
	TranslationServer.remove_translation(t)
	TranslationServer.set_locale(loc)
