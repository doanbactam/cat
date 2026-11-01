extends "res://tests/test_player_base.gd"
## Locomotion: contract, walking/trotting/sprinting/sneaking, step-up, stairs, edge guard,
## turn-in-place, slope, crawl under a low gap.


func test_scene_contract() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await step(2)
	assert_true(p is CatPlayer, "root is CatPlayer")
	assert_true(p.is_in_group(&"player"), "group player")
	assert_eq(p.collision_layer, 2, "layer 2")
	assert_eq(p.collision_mask, 1 | 8 | 32 | 64 | 128, "mask 1|4|6|7|8")
	for m in ["set_input_enabled", "teleport", "get_camera_rig", "get_camera", "get_mouth_attachment", "get_state", "is_first_person", "set_camera_mode", "play_action"]:
		assert_true(p.has_method(m), "API " + m)
	assert_not_null(p.call(&"get_camera"), "camera exists")
	assert_not_null(p.call(&"get_camera_rig"), "camera rig exists")
	assert_not_null(p.call(&"get_mouth_attachment"), "mouth attachment exists")
	assert_eq(p.call(&"get_state"), &"idle", "starts idle")


func test_player_spawned_emitted() -> void:
	ground()
	watch(GameEvents.player_spawned, "spawned")
	spawn_player(Vector3.ZERO)
	await step(3)
	assert_eq(count_events("spawned"), 1, "player_spawned once")


func test_trot_moves_forward_and_stops() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	await seconds(1.5)
	var moved := p.global_position.z
	var spd: float = p.call(&"get_planar_speed")
	assert_true(moved > 1.4, "trotted forward (%.2f m)" % moved)
	assert_true(spd > 1.5 and spd < 2.6, "trot speed (%.2f m/s)" % spd)
	assert_eq(p.call(&"get_state"), &"trot", "trot state")
	release(&"move_forward")
	await seconds(0.6)
	assert_true(float(p.call(&"get_planar_speed")) < 0.05, "stopped")
	assert_true(absf(p.global_position.y) < 0.02, "stays on the floor")


func test_analog_walk() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward", 0.45)
	await seconds(1.2)
	var spd: float = p.call(&"get_planar_speed")
	assert_true(spd > 0.3 and spd < 0.8, "light push walks (%.2f)" % spd)
	assert_eq(p.call(&"get_state"), &"walk")


func test_sprint_and_sneak() -> void:
	ground(60.0)
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"sprint")
	hold(&"move_forward")
	await seconds(1.6)
	var run_spd: float = p.call(&"get_planar_speed")
	assert_true(run_spd > 4.0, "sprint (%.2f m/s)" % run_spd)
	assert_eq(p.call(&"get_state"), &"run")
	release(&"sprint")
	release(&"move_forward")
	await seconds(1.0)
	await tap(&"sneak")
	hold(&"move_forward")
	await seconds(1.0)
	var sneak_spd: float = p.call(&"get_planar_speed")
	assert_true(sneak_spd > 0.2 and sneak_spd < 0.6, "sneak (%.2f m/s)" % sneak_spd)
	assert_eq(p.call(&"get_state"), &"sneak")


func test_step_up_curb() -> void:
	ground()
	box(Vector3(0, 0.075, 1.6), Vector3(3, 0.15, 2))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	var ok := await wait_until(func() -> bool: return p.global_position.z > 1.2, 3.0)
	assert_true(ok, "walked onto the curb")
	assert_near(p.global_position.y, 0.15, 0.03, "standing on the 0.15 m curb")


func test_step_up_rejects_high_ledge() -> void:
	ground()
	box(Vector3(0, 0.15, 1.6), Vector3(3, 0.3, 2))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	await seconds(1.5)
	assert_true(p.global_position.y < 0.05, "0.3 m is not a step")
	assert_true(p.global_position.z < 0.62, "blocked by the ledge (z %.2f)" % p.global_position.z)


func test_stairs_up_and_down() -> void:
	ground()
	for i in 6:
		var top := 0.16 * float(i + 1)
		box(Vector3(0, top * 0.5, 1.0 + 0.3 * float(i)), Vector3(1.2, top, 0.3))
	box(Vector3(0, 0.48, 3.25), Vector3(1.2, 0.96, 1.2))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	var ok := await wait_until(func() -> bool: return p.global_position.z > 3.1, 5.0)
	assert_true(ok, "climbed the stairs (z %.2f)" % p.global_position.z)
	assert_near(p.global_position.y, 0.96, 0.03, "on the landing")
	release(&"move_forward")
	await seconds(0.3)
	# and back down without ever entering the air state for long
	var air_frames := 0
	hold(&"move_back")
	for i in 240:
		await tree.physics_frame
		if p.call(&"is_airborne"):
			air_frames += 1
		if p.global_position.z < 0.5:
			break
	assert_true(p.global_position.z < 0.8, "came back down")
	assert_true(air_frames < 20, "stays grounded on stairs (air frames %d)" % air_frames)


func test_edge_guard_on_high_platform() -> void:
	box(Vector3(0, 1.0, 0), Vector3(2, 2, 2))
	box(Vector3(0, -0.25, 0), Vector3(30, 0.5, 30))
	var p := spawn_player(Vector3(0, 2.0, 0))
	await settle()
	hold(&"move_forward")
	await seconds(2.0)
	assert_near(p.global_position.y, 2.0, 0.03, "walking does not step off a 2 m drop")
	assert_true(p.global_position.z < 1.0 and p.global_position.z > 0.75, "stopped at the lip (z %.2f)" % p.global_position.z)
	assert_false(p.call(&"is_airborne"))


func test_turn_in_place() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.player_state_changed, "state")
	hold(&"move_back")
	await step(4)
	var turned := false
	for e: Array in events:
		if String(e[2]).begins_with("turn_"):
			turned = true
	assert_true(turned, "turn-in-place clip state %s" % str(events))
	await seconds(1.2)
	var fwd := p.global_transform.basis.z
	assert_true(fwd.z < -0.8, "now facing backwards (%.2f)" % fwd.z)


func test_slope_walk_and_alignment() -> void:
	ground()
	var ramp := box(Vector3.ZERO, Vector3(2, 0.1, 4))
	ramp.basis = Basis(Vector3.RIGHT, -deg_to_rad(22.0))
	ramp.position = Vector3(0, 0.75 - 0.05, 2.5)
	var p := spawn_player(Vector3(0, 0, 0))
	await settle()
	hold(&"move_forward")
	var ok := await wait_until(func() -> bool: return p.global_position.y > 0.4, 4.0)
	assert_true(ok, "walks up a 22° ramp")
	await seconds(0.2)
	var vis: Node3D = p.call(&"get_visual")
	var pitch := vis.transform.basis.get_euler().x
	assert_true(pitch < -0.15, "body pitched nose-up on the ramp (%.2f rad)" % pitch)


func test_crawl_under_low_gap() -> void:
	ground()
	box(Vector3(0, 0.17 + 0.1, 1.8), Vector3(2.0, 0.2, 1.6))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	var ok := await wait_until(func() -> bool: return p.global_position.z > 2.8, 7.0)
	assert_true(ok, "squeezed under the 0.17 m gap (z %.2f)" % p.global_position.z)
	release(&"move_forward")
	await seconds(0.5)
	assert_false(p.call(&"is_crawling"), "stands up again after the gap")


func test_input_disabled() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	p.call(&"set_input_enabled", false)
	hold(&"move_forward")
	await seconds(0.6)
	assert_true(p.global_position.distance_to(Vector3.ZERO) < 0.02, "no movement while input is disabled")
	p.call(&"set_input_enabled", true)
	await seconds(0.6)
	assert_true(p.global_position.z > 0.3, "moves again")


func test_teleport() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await step(3)
	p.call(&"teleport", Transform3D(Basis(Vector3.UP, PI * 0.5), Vector3(3, 0, -2)))
	await step(2)
	assert_true(p.global_position.distance_to(Vector3(3, 0, -2)) < 0.03, "teleported")
	assert_true(p.global_transform.basis.z.dot(Vector3.RIGHT) > 0.95, "facing +X")
