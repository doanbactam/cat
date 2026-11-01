extends "res://tests/test_player_base.gd"
## Jumping: precision targeting onto a 1 m ledge, free jumps, landing states (soft / hard with
## damage), ledge scramble, coyote time and jump buffering.


func test_targeted_jump_onto_1m_ledge() -> void:
	ground()
	box(Vector3(0, 0.5, 1.15), Vector3(1.2, 1.0, 1.0))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.player_jumped, "jumped")
	watch(GameEvents.player_landed, "landed")
	hold(&"jump")
	await seconds(0.35)
	assert_eq(p.call(&"get_state"), &"jump_crouch", "crouching while jump is held")
	var target: Dictionary = p.call(&"get_jump_target")
	assert_false(target.is_empty(), "found a landing target")
	if not target.is_empty():
		var tp: Vector3 = target["point"]
		assert_near(tp.y, 1.0, 0.02, "target on the ledge top")
		assert_true(tp.z > 0.7 and tp.z < 1.6, "target on the ledge (z %.2f)" % tp.z)
	var reticle: Node = p.get_node_or_null(^"JumpReticle")
	assert_true(reticle != null and bool(reticle.call(&"is_showing")), "landing reticle shown")
	release(&"jump")
	var ok := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0 and p.is_on_floor(), 2.0)
	assert_true(ok, "landed")
	assert_near(p.global_position.y, 1.0, 0.03, "standing on the 1 m ledge")
	if not target.is_empty():
		var tp2: Vector3 = target["point"]
		var err := Vector2(p.global_position.x - tp2.x, p.global_position.z - tp2.z).length()
		assert_true(err < 0.06, "landed where it aimed (error %.3f m)" % err)
	assert_eq(count_events("jumped"), 1, "player_jumped emitted")
	assert_true(count_events("landed") >= 1, "player_landed emitted")


func test_targeted_jump_down_and_across_gap() -> void:
	ground()
	box(Vector3(0, 0.6, 0), Vector3(1.0, 1.2, 1.0))      # start platform (1.2 m)
	box(Vector3(0, 0.6, 2.2), Vector3(1.0, 1.2, 1.0))    # across a 1.2 m gap, same height
	var p := spawn_player(Vector3(0, 1.2, 0))
	await settle()
	hold(&"move_forward", 0.3)
	await step(2)
	release(&"move_forward")
	hold(&"jump")
	await seconds(0.3)
	var target: Dictionary = p.call(&"get_jump_target")
	assert_false(target.is_empty(), "gap target found")
	release(&"jump")
	var ok := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0 and p.is_on_floor() and p.global_position.z > 1.5, 2.5)
	assert_true(ok, "crossed the gap")
	assert_near(p.global_position.y, 1.2, 0.03, "on the far platform")


func test_free_jump_on_flat_ground() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.player_landed, "landed")
	var max_y := 0.0
	await tap(&"jump", 2)
	for i in 90:
		await tree.physics_frame
		max_y = maxf(max_y, p.global_position.y)
		if count_events("landed") > 0:
			break
	assert_true(max_y > 0.2, "went up (%.2f m)" % max_y)
	assert_eq(count_events("landed"), 1, "landed once")
	assert_near(p.global_position.y, 0.0, 0.02, "back on the ground")


func test_soft_and_hard_landing() -> void:
	ground()
	var p := spawn_player(Vector3(0, 0.6, 0))
	watch(GameEvents.player_state_changed, "state")
	watch(GameEvents.player_landed, "landed")
	watch(GameEvents.player_damaged, "damaged")
	watch(GameEvents.player_noise, "noise")
	await wait_until(func() -> bool: return count_events("landed") > 0, 2.0)
	var states: Array = events.filter(func(e: Array) -> bool: return e[0] == "state").map(func(e: Array) -> StringName: return e[2])
	assert_true(&"land" in states, "soft landing from 0.6 m (%s)" % str(states))
	assert_true(count_events("noise") >= 1, "landing makes noise")
	events.clear()
	p.call(&"teleport", Transform3D(Basis.IDENTITY, Vector3(0, 3.2, 0)))
	await wait_until(func() -> bool: return count_events("landed") > 0, 3.0)
	var states2: Array = events.filter(func(e: Array) -> bool: return e[0] == "state").map(func(e: Array) -> StringName: return e[2])
	assert_true(&"land_hard" in states2, "hard landing from 3.2 m (%s)" % str(states2))
	var landed := last_event("landed")
	assert_true(not landed.is_empty() and float(landed[1]) > 6.0, "impact speed reported")
	assert_true(count_events("damaged") == 1, "fall above the safe height hurts")


func test_scramble_onto_ledge() -> void:
	ground()
	box(Vector3(0, 0.275, 0.55), Vector3(1.2, 0.55, 0.5))
	var p := spawn_player(Vector3(0, 0.3, 0.12))
	await wait_until(func() -> bool: return bool(p.call(&"is_airborne")), 1.0)
	p.velocity = Vector3(0, 0.6, 1.2)
	watch(GameEvents.player_state_changed, "state")
	var ok := await wait_until(func() -> bool: return p.call(&"get_state") == &"scramble", 1.0)
	assert_true(ok, "chest hit the ledge → scramble")
	var on_top := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0 and p.global_position.y > 0.5, 2.0)
	assert_true(on_top, "pulled itself up")
	assert_near(p.global_position.y, 0.55, 0.03, "standing on the ledge")


func test_coyote_time() -> void:
	box(Vector3(0, 0.5, 0), Vector3(1.0, 1.0, 2.0))
	box(Vector3(0, -0.25, 0), Vector3(30, 0.5, 30))
	var p := spawn_player(Vector3(0, 1.0, 0.3))
	await settle()
	watch(GameEvents.player_jumped, "jumped")
	hold(&"sprint")
	hold(&"move_forward")
	var left := await wait_until(func() -> bool: return bool(p.call(&"is_airborne")), 2.0)
	assert_true(left, "ran off the edge")
	await step(3)
	await tap(&"jump", 2)
	await step(2)
	assert_eq(count_events("jumped"), 1, "jump allowed just after leaving the ledge")


func test_jump_buffer() -> void:
	ground()
	var p := spawn_player(Vector3(0, 0.9, 0))
	watch(GameEvents.player_jumped, "jumped")
	watch(GameEvents.player_landed, "landed")
	await wait_until(func() -> bool: return p.global_position.y < 0.12, 2.0)
	await tap(&"jump", 2)   # pressed a few frames before touching down
	await wait_until(func() -> bool: return count_events("landed") > 0, 1.0)
	await step(3)
	assert_eq(count_events("jumped"), 1, "buffered jump fired on landing")
