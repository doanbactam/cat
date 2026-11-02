extends "res://tests/test_player_base.gd"
## Interaction: focus selection + events, pickup into the mouth (visual on the mouth socket),
## dropping, knocking a cup off a table, meowing, food source, cat-sense toggle.


func test_focus_and_pickup_into_mouth() -> void:
	ground()
	watch(GameEvents.interactable_focused, "focus")
	watch(GameEvents.interacted, "interacted")
	watch(GameEvents.item_picked_up, "picked")
	var fish := PickupItem.new()
	fish.item_id = &"fish"
	world.add_child(fish)
	fish.position = Vector3(0, 0, 0.45)
	var p := spawn_player(Vector3.ZERO)
	await settle()
	await seconds(0.3)
	assert_true(count_events("focus") >= 1, "fish focused")
	var f := last_event("focus")
	assert_true(not f.is_empty() and f[1] == fish, "focused the fish")
	assert_true(not f.is_empty() and String(f[2]) != "", "prompt text given")
	await tap(&"interact", 2)
	await step(3)
	assert_eq(GameState.mouth_item, &"fish", "fish in the mouth")
	assert_eq(count_events("interacted"), 1, "GameEvents.interacted emitted")
	assert_eq(count_events("picked"), 1)
	var mouth: Node3D = p.call(&"get_mouth_attachment")
	assert_not_null(mouth.get_node_or_null(^"HeldItem"), "item visual attached to the mouth socket")
	var d := mouth.global_position.distance_to(p.global_position + p.global_transform.basis.z * 0.2 + Vector3.UP * 0.2)
	assert_true(d < 0.12, "mouth socket at the muzzle (%.3f)" % d)


func test_drop_mouth_item() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	GameState.add_item(&"fish", 1)
	GameState.set_mouth_item(&"fish")
	await step(2)
	watch(GameEvents.item_dropped, "dropped")
	await tap(&"pickup_drop", 2)
	await step(3)
	assert_eq(GameState.mouth_item, &"", "mouth empty")
	assert_eq(count_events("dropped"), 1, "item_dropped emitted")
	var found := false
	for c in world.get_children():
		if c is PickupItem and (c as PickupItem).item_id == &"fish":
			found = true
	assert_true(found, "a fish pickup lies in the world")
	var mouth: Node3D = p.call(&"get_mouth_attachment")
	assert_true(mouth.get_node_or_null(^"HeldItem") == null, "held visual removed")


func test_swipe_knocks_cup_off_table() -> void:
	ground()
	# table top 0.7 m, z 0..1; the cat stands on it facing +Z, the cup 0.26 m from the far edge
	box(Vector3(0, 0.35, 0.5), Vector3(1.0, 0.7, 1.0))
	var cup := Pushable.new()
	cup.object_id = &"test_cup"
	cup.set_meta(&"mass", 0.2)
	world.add_child(cup)
	cup.position = Vector3(0.0, 0.7, 0.74)
	watch(GameEvents.object_knocked_off, "knocked")
	var p := spawn_player(Vector3(0, 0.7, 0.38))
	await settle()
	await tap(&"swipe", 2)
	await step(2)
	assert_true(cup.is_armed() or count_events("knocked") > 0, "cup was swiped")
	var ok := await wait_until(func() -> bool: return count_events("knocked") > 0, 4.0)
	assert_true(ok, "cup fell off the table (y %.2f)" % cup.global_position.y)


func test_meow_short_and_loud() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.player_meowed, "meow")
	watch(GameEvents.player_noise, "noise")
	await tap(&"meow", 2)
	await step(2)
	assert_eq(count_events("meow"), 1, "short meow")
	assert_true(String(last_event("meow")[1]) in ["short", "chirp"], "short/chirp kind")
	hold(&"meow")
	await seconds(0.5)
	release(&"meow")
	await step(2)
	assert_eq(count_events("meow"), 2, "loud meow on hold")
	assert_eq(last_event("meow")[1], &"loud")
	var loud_noise := last_event("noise")
	assert_true(not loud_noise.is_empty() and float(loud_noise[2]) > 0.5, "loud meow is loud")


func test_eat_at_food_source() -> void:
	ground()
	GameState.set_stat(&"hunger", 40.0)
	var bowl := FoodSource.new()
	bowl.source_id = &"test_bowl"
	bowl.food_amount = 30.0
	world.add_child(bowl)
	bowl.position = Vector3(0, 0, 0.4)
	var p := spawn_player(Vector3.ZERO)
	await settle()
	await seconds(0.2)
	await tap(&"interact", 2)
	await step(3)
	assert_eq(p.call(&"get_state"), &"eat", "eat animation state")
	assert_true(GameState.get_stat(&"hunger") > 60.0, "hunger restored (%.1f)" % GameState.get_stat(&"hunger"))


func test_cat_sense_toggle() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.cat_sense_toggled, "sense")
	var e0 := GameState.get_stat(&"energy")
	await tap(&"cat_sense", 2)
	await seconds(0.6)
	assert_eq(count_events("sense"), 1, "cat_sense_toggled(true)")
	assert_true(GameState.get_stat(&"energy") < e0, "costs energy")
	var sense: Node = p.get_node(^"CatSense")
	assert_true(sense.call(&"is_active"))
	assert_true(float(sense.call(&"get_value")) > 0.9, "global cat_sense ramped up")
	await tap(&"cat_sense", 2)
	await seconds(0.6)
	assert_false(sense.call(&"is_active"))
	assert_true(float(sense.call(&"get_value")) < 0.05, "faded out")
