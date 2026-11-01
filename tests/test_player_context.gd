extends "res://tests/test_player_base.gd"
## Contextual movement: balance on a beam, climbing layer-6 surfaces (incl. mantle at the top),
## water (splash → swim → scramble out, wet fur), contextual idles.


func _pool() -> Area3D:
	# raised basin: rim 0.35 m, water level 0.25 m
	ground()
	box(Vector3(0, 0.175, 1.0), Vector3(2.4, 0.35, 0.15))
	box(Vector3(0, 0.175, -1.0), Vector3(2.4, 0.35, 0.15))
	box(Vector3(1.2, 0.175, 0), Vector3(0.15, 0.35, 2.0))
	box(Vector3(-1.2, 0.175, 0), Vector3(0.15, 0.35, 2.0))
	var a := Area3D.new()
	a.collision_layer = 1 << 6
	a.collision_mask = 0
	a.monitorable = true
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(2.25, 0.25, 1.85)
	cs.shape = bs
	cs.position = Vector3(0, 0.125, 0)
	a.add_child(cs)
	world.add_child(a)
	return a


func test_fall_into_water_swim_and_scramble_out() -> void:
	_pool()
	watch(GameEvents.player_landed, "landed")
	var p := spawn_player(Vector3(0, 0.9, 0))
	var ok := await wait_until(func() -> bool: return p.call(&"get_state") == &"swim", 2.0)
	assert_true(ok, "falling in → swim")
	var water_landing := false
	for e: Array in events:
		if e[0] == "landed" and e[2] == &"water":
			water_landing = true
	assert_true(water_landing, "player_landed(…, &\"water\")")
	assert_true(GameState.wetness > 0.9, "fur soaked (%.2f)" % GameState.wetness)
	await seconds(0.5)
	assert_near(p.global_position.y, 0.25 - 0.13, 0.04, "floats at the surface")
	# paddle to the +Z rim and scramble out
	hold(&"move_forward")
	var out := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0 and p.global_position.y > 0.3, 5.0)
	assert_true(out, "scrambled out over the rim (state %s, y %.2f)" % [p.call(&"get_state"), p.global_position.y])


func test_climb_wall_and_mantle_top() -> void:
	ground()
	box(Vector3(0, 0.75, 0.5), Vector3(1.5, 1.5, 0.3), 1 | (1 << 5))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	var climbing := await wait_until(func() -> bool: return p.call(&"get_state") == &"climb", 2.0)
	assert_true(climbing, "starts climbing the layer-6 wall")
	var y0 := p.global_position.y
	await seconds(0.6)
	assert_true(p.global_position.y > y0 + 0.2, "climbs up (%.2f → %.2f)" % [y0, p.global_position.y])
	var top := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0 and p.global_position.y > 1.4, 5.0)
	assert_true(top, "mantled onto the top (y %.2f, state %s)" % [p.global_position.y, p.call(&"get_state")])
	assert_near(p.global_position.y, 1.5, 0.04, "standing on the wall top")


func test_non_climbable_wall_is_not_climbed() -> void:
	ground()
	box(Vector3(0, 0.75, 0.5), Vector3(1.5, 1.5, 0.3), 1)
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	await seconds(1.0)
	assert_true(p.call(&"get_state") != &"climb", "plain walls are not climbable")
	assert_true(p.global_position.y < 0.05)


func test_climb_jump_off() -> void:
	ground()
	box(Vector3(0, 1.5, 0.5), Vector3(1.5, 3.0, 0.3), 1 | (1 << 5))
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	await wait_until(func() -> bool: return p.call(&"get_state") == &"climb", 2.0)
	await seconds(0.5)
	release(&"move_forward")
	await tap(&"jump", 2)
	var off := await wait_until(func() -> bool: return bool(p.call(&"is_airborne")), 0.5)
	assert_true(off, "jumped off the wall")
	var landed := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0, 3.0)
	assert_true(landed, "landed after jumping off")
	assert_true(p.global_position.z < 0.2, "pushed away from the wall")


func test_balance_on_beam() -> void:
	ground()
	box(Vector3(0, 0.56, 1.5), Vector3(0.08, 0.08, 5.0))
	var p := spawn_player(Vector3(0, 0.6, -0.5))
	await settle()
	hold(&"move_forward", 0.8)
	var bal := await wait_until(func() -> bool: return bool(p.call(&"is_balancing")), 2.0)
	assert_true(bal, "narrow support → balance mode")
	await seconds(1.5)
	assert_near(p.global_position.y, 0.6, 0.03, "still on the beam")
	assert_true(absf(p.global_position.x) < 0.03, "kept centred (x %.3f)" % p.global_position.x)
	var spd: float = p.call(&"get_planar_speed")
	assert_true(spd < 0.6, "slow balance walk (%.2f)" % spd)


func test_balance_centring_on_offset_entry() -> void:
	ground()
	box(Vector3(0, 0.56, 1.5), Vector3(0.1, 0.08, 5.0))
	var p := spawn_player(Vector3(0.03, 0.6, -0.5))
	await settle()
	hold(&"move_forward", 0.7)
	await seconds(2.0)
	assert_true(absf(p.global_position.x) < 0.02, "drifted back to the beam centre (x %.3f)" % p.global_position.x)
	assert_near(p.global_position.y, 0.6, 0.03)


func test_idle_sits_after_inactivity() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	p.set(&"idle_sit_after", 0.6)
	p.set(&"idle_look_after", 0.3)
	var ok := await wait_until(func() -> bool: return p.call(&"get_state") in [&"sit_down", &"sit"], 2.0)
	assert_true(ok, "sits after inactivity")
	hold(&"move_forward")
	var up := await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0, 2.0)
	assert_true(up, "gets up when the player moves")


func test_sit_groom_toggle() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	await tap(&"sit_groom", 2)
	var sat := await wait_until(func() -> bool: return p.call(&"get_state") in [&"sit_down", &"sit"], 1.0)
	assert_true(sat, "tap → sit")
	hold(&"sit_groom")
	await seconds(0.6)
	release(&"sit_groom")
	var groom := await wait_until(func() -> bool: return p.call(&"get_state") == &"groom", 2.0)
	assert_true(groom, "hold → groom")
