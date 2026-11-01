extends "res://tests/test_player_base.gd"
## Camera rig: toggle TPP ⇄ FPP (input + API), FPP at the eyes, TPP spring-arm collision.


func test_toggle_camera_to_first_person() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	watch(GameEvents.camera_mode_changed, "cam")
	assert_false(p.call(&"is_first_person"), "starts in third person")
	await tap(&"toggle_camera", 2)
	await step(2)
	assert_true(p.call(&"is_first_person"), "toggle → first person")
	assert_eq(count_events("cam"), 1, "camera_mode_changed emitted")
	assert_eq(last_event("cam")[1], &"first_person")
	await seconds(0.8)
	var cam: Camera3D = p.call(&"get_camera")
	var eye: Transform3D = p.call(&"get_eye_transform_interpolated")
	var d := cam.global_position.distance_to(eye.origin)
	assert_true(d < 0.05, "camera sits at the eyes (%.3f m)" % d)
	assert_true(cam.near <= 0.02, "near clip for FPP (%.3f)" % cam.near)
	assert_true(cam.fov >= 79.0, "FPP fov ≥ 80 (%.1f)" % cam.fov)
	assert_true(eye.origin.y > 0.15 and eye.origin.y < 0.35, "eye height at cat scale (%.2f)" % eye.origin.y)
	await tap(&"toggle_camera", 2)
	await seconds(0.8)
	assert_false(p.call(&"is_first_person"), "toggle back")
	var dist := cam.global_position.distance_to(p.global_position)
	assert_true(dist > 0.8, "third-person orbit distance (%.2f)" % dist)


func test_set_camera_mode_api() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	p.call(&"set_camera_mode", &"first_person")
	await step(2)
	assert_true(p.call(&"is_first_person"))
	p.call(&"set_camera_mode", &"third_person")
	await step(2)
	assert_false(p.call(&"is_first_person"))


func test_tpp_camera_collides_with_wall() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var cam: Camera3D = p.call(&"get_camera")
	await seconds(0.3)
	var free_d := cam.global_position.distance_to(p.global_position)
	# wall right behind the cat (camera side is -Z)
	box(Vector3(0, 1.0, -0.6), Vector3(4, 2, 0.2))
	await seconds(0.5)
	var d := cam.global_position.distance_to(p.global_position)
	assert_true(d < free_d - 0.3, "spring arm pulled in (%.2f → %.2f)" % [free_d, d])
	assert_true(cam.global_position.z > -0.5, "camera stays in front of the wall (z %.2f)" % cam.global_position.z)


func test_camera_relative_movement() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var rig: Node3D = p.call(&"get_camera_rig")
	rig.set(&"yaw", PI * 0.5 + PI)   # camera looking along +X
	await step(2)
	hold(&"move_forward")
	await seconds(1.2)
	assert_true(p.global_position.x > 0.8, "forward = camera forward (+X), pos %s" % str(p.global_position))
	assert_true(absf(p.global_position.z) < 0.4)
