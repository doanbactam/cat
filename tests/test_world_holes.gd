extends "res://tests/test_base.gd"
## world: no fall-through gaps in the city ground, and the player is rescued if it ever falls out.
## Regression for "bug xuyên map": tree pits and the lake-block north row had no collider, the cat
## dropped onto the SafetyFloor (y -5.5) under the city and was stuck there.

const CITY := "res://scenes/world/city.tscn"
const PLAYER := "res://scenes/player/cat_player.tscn"

static var _city: Node3D


func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _get_city() -> Node3D:
	if _city == null or not is_instance_valid(_city):
		_city = (load(CITY) as PackedScene).instantiate() as Node3D
		_tree().root.add_child(_city)
		for i in 4:
			await _tree().physics_frame
	return _city


func _ground_hit(city: Node3D, x: float, z: float) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, 80.0, z), Vector3(x, -30.0, z), 1 | 4 | 32 | 64 | 128)
	return city.get_world_3d().direct_space_state.intersect_ray(q)


func _pit_center(city: Node3D) -> Vector3:
	var lakebed := city.get_node(^"Ground/Ground_lakebed") as MeshInstance3D
	var faces := lakebed.mesh.get_faces()
	for i in range(0, faces.size(), 3):
		if absf(faces[i].y + 0.04) < 0.005 and absf(faces[i + 1].y + 0.04) < 0.005 and absf(faces[i + 2].y + 0.04) < 0.005:
			return (faces[i] + faces[i + 1] + faces[i + 2]) / 3.0
	return Vector3.INF


func _drop_player(city: Node3D, at: Vector3, seconds: float) -> Node3D:
	var p := (load(PLAYER) as PackedScene).instantiate() as Node3D
	p.set(&"create_camera", false)
	city.add_child(p)
	p.call(&"set_input_enabled", false)
	p.call(&"teleport", Transform3D(Basis(), at))
	var frames := int(seconds * Engine.physics_ticks_per_second)
	for i in frames:
		await _tree().physics_frame
	return p


func test_a_no_fall_through_gaps() -> void:
	var city: Node3D = await _get_city()
	var b: Rect2 = city.get_meta(&"map_bounds", Rect2(-124, -98, 248, 212))
	var bad: Array[Vector2] = []
	var x := b.position.x + 0.13
	while x <= b.end.x:
		var z := b.position.y + 0.13
		while z <= b.end.y:
			var h := _ground_hit(city, x, z)
			if h.is_empty() or str((h["collider"] as Node).name) == "SafetyFloor":
				bad.append(Vector2(x, z))
			z += 1.0
		x += 1.0
	assert_eq(bad.size(), 0, "ground under every map cell (first gaps: %s)" % str(bad.slice(0, 5)))


func test_b_cat_stands_in_tree_pit_and_north_row() -> void:
	var city: Node3D = await _get_city()
	var pit := _pit_center(city)
	assert_true(pit != Vector3.INF, "a tree pit exists")
	var p: Node3D = await _drop_player(city, pit + Vector3(0.35, 1.0, 0.35), 1.5)
	assert_true(p.global_position.y > -0.5, "cat stays on tree-pit soil (y=%.2f)" % p.global_position.y)
	p.queue_free()
	# former gap between the north-row houses and the lake park (z -63..-49)
	for gx: float in [-44.0, -12.0, 36.0]:
		var h := _ground_hit(city, gx, -50.5)
		assert_true(not h.is_empty() and (h["position"] as Vector3).y > -0.5, "ground at (%.0f, -50.5)" % gx)


func test_c_player_rescued_when_out_of_world() -> void:
	var city: Node3D = await _get_city()
	var spawn := _tree().get_first_node_in_group(&"player_spawn") as Node3D
	var p: Node3D = await _drop_player(city, spawn.global_position + Vector3(0, 0.3, 0), 1.0)
	var safe_y := p.global_position.y
	p.call(&"teleport", Transform3D(Basis(), Vector3(spawn.global_position.x, -5.0, spawn.global_position.z)))
	for i in 20:
		await _tree().physics_frame
	assert_true(p.global_position.y > -1.0, "rescued above ground (y=%.2f, last safe %.2f)" % [p.global_position.y, safe_y])
	p.queue_free()


func test_z_cleanup() -> void:
	if _city != null and is_instance_valid(_city):
		_city.queue_free()
	_city = null
	await _tree().process_frame
