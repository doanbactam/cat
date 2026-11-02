extends "res://tests/test_base.gd"
## world-life: LifeDirector + AI behaviours. Small purpose-built worlds (ground + baked navmesh +
## markers) keep each test fast; one test loads the full scenes/npc/test_life.tscn.

const DirectorScene := preload("res://scenes/npc/life_director.tscn")
const Perception := preload("res://scripts/npc/perception.gd")


class StubPlayer extends CharacterBody3D:
	var sneaking := false
	var state: StringName = &"idle"
	func is_sneaking() -> bool:
		return sneaking
	func get_state() -> StringName:
		return state
	func is_airborne() -> bool:
		return false


var _world: Node3D = null
var _conns: Array = []


func _connect(sig: Signal, cb: Callable) -> void:
	sig.connect(cb)
	_conns.append([sig, cb])


func before_each() -> void:
	var gs := tree.root.get_node_or_null("GameState")
	if gs != null and gs.has_method(&"new_game"):
		gs.call(&"new_game")
	var tod := tree.root.get_node_or_null("TimeOfDay")
	if tod != null:
		tod.set(&"paused", true)
		tod.call(&"set_hour", 10.0)


func after_each() -> void:
	for c: Array in _conns:
		if (c[0] as Signal).is_connected(c[1]):
			(c[0] as Signal).disconnect(c[1])
	_conns.clear()
	if _world != null and is_instance_valid(_world):
		if _world.get_parent() != null:
			_world.get_parent().remove_child(_world)
		_world.queue_free()
		_world = null
	var tod := tree.root.get_node_or_null("TimeOfDay")
	if tod != null:
		tod.set(&"paused", false)


# --------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------

func _frames(n: int) -> void:
	for i in n:
		await tree.physics_frame


func _box(parent: Node3D, center: Vector3, size: Vector3) -> StaticBody3D:
	var sb := StaticBody3D.new()
	sb.position = center
	sb.collision_layer = 1
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	parent.add_child(sb)
	return sb


## Flat 60×60 m world with a baked navmesh. `extra` boxes: Array of [center, size].
func _make_world(extra: Array = []) -> Node3D:
	_world = Node3D.new()
	_world.name = "LifeTestWorld"
	tree.root.add_child(_world)
	var geo := Node3D.new()
	geo.name = "Geo"
	geo.add_to_group(&"nav_src")
	_world.add_child(geo)
	_box(geo, Vector3(0, -0.25, 0), Vector3(60, 0.5, 60))
	for e: Array in extra:
		_box(geo, e[0], e[1])
	var nr := NavigationRegion3D.new()
	nr.name = "NavRegion"
	nr.add_to_group(&"nav_region")
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = &"nav_src"
	nm.agent_radius = 0.25
	nm.agent_max_climb = 0.25
	nr.navigation_mesh = nm
	_world.add_child(nr)
	nr.bake_navigation_mesh(false)
	return _world


func _marker(group: StringName, pos: Vector3, meta: Dictionary, yaw := 0.0) -> Marker3D:
	var m := Marker3D.new()
	m.add_to_group(group)
	for k: String in meta:
		m.set_meta(StringName(k), meta[k])
	_world.add_child(m)
	m.global_position = pos
	m.rotation.y = yaw
	return m


func _player(pos: Vector3) -> StubPlayer:
	var p := StubPlayer.new()
	p.name = "StubPlayer"
	p.add_to_group(&"player")
	p.collision_layer = 2
	var cs := CollisionShape3D.new()
	var sp := SphereShape3D.new()
	sp.radius = 0.12
	cs.shape = sp
	cs.position = Vector3(0, 0.13, 0)
	p.add_child(cs)
	_world.add_child(p)
	p.global_position = pos
	return p


func _director(opts: Dictionary = {}) -> Node:
	var d := DirectorScene.instantiate()
	d.set(&"auto_start", false)
	d.set(&"ignore_time_curves", true)
	for k: String in opts:
		d.set(StringName(k), opts[k])
	_world.add_child(d)
	return d


# --------------------------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------------------------

func test_perception_vision_cone_and_occlusion() -> void:
	_make_world([[Vector3(0, 1, 4), Vector3(4, 2, 0.3)]])
	var watcher := Node3D.new()
	_world.add_child(watcher)
	watcher.global_position = Vector3(0, 0, 0)
	var per := Perception.new(watcher)
	per.eye_height = 1.5
	per.sight_range = 12.0
	var target := _player(Vector3(2.5, 0, 2.5))
	await _frames(2)
	assert_true(per.compute_visibility(target) > 0.0, "cat in front, in range, unoccluded is visible")
	target.global_position = Vector3(0, 0, 8)
	await _frames(2)
	assert_eq(per.compute_visibility(target), 0.0, "wall between eye and cat blocks sight")
	target.global_position = Vector3(0, 0, -5)
	await _frames(2)
	assert_eq(per.compute_visibility(target), 0.0, "behind the watcher (outside cone)")
	target.global_position = Vector3(8, 0, 6)
	await _frames(2)
	var normal := per.compute_visibility(target)
	target.sneaking = true
	var sneak := per.compute_visibility(target)
	assert_true(normal > 0.0 and sneak < normal, "sneaking reduces visibility (%f -> %f)" % [normal, sneak])
	# hearing raises awareness
	var a0 := per.awareness
	per.notify_noise(Vector3(2, 0, 2), 0.9)
	assert_true(per.awareness > a0, "loud noise nearby raises awareness")


func test_director_spawns_full_test_world() -> void:
	var ps := load("res://scenes/npc/test_life.tscn") as PackedScene
	assert_not_null(ps, "test_life.tscn loads")
	_world = ps.instantiate() as Node3D
	_world.set(&"spawn_player", false)
	tree.root.add_child(_world)
	var p := _player(Vector3(4, 0.3, 7))
	var d := _world.get_node("LifeDirector")
	d.set(&"ignore_time_curves", true)
	await _frames(200)
	assert_true(bool(d.get(&"started")), "director started")
	for id: String in ["ba_tu", "co_hoa", "chu_sau", "bin", "ven", "mun", "bong", "muop", "lao_qua", "xam"]:
		assert_not_null(d.call(&"get_named", StringName(id)), "named npc spawned: " + id)
	var stats: Dictionary = d.call(&"get_stats")
	assert_true(int(stats["vehicles"]) > 0, "traffic spawned")
	assert_true(int(stats["pedestrians"]) > 0, "pedestrians spawned")
	assert_eq(int(stats["flocks"]), 1)
	assert_eq(int(stats["koi_schools"]), 1)
	assert_true(int(stats["mice"]) >= 1)
	assert_true(int(stats["sparrow_wires"]) == 1)
	# named NPCs have a Talkable with their dialogue id
	var ba_tu := d.call(&"get_named", &"ba_tu") as Node
	var talk := ba_tu.get_node_or_null("Talkable")
	assert_not_null(talk, "ba_tu has a Talkable")
	if talk != null:
		assert_eq(talk.get(&"dialogue_id"), &"ba_tu")
	var muop := d.call(&"get_named", &"muop") as Node
	assert_eq((muop.get_node("Talkable")).get(&"dialogue_id"), &"ong_muop", "Mướp uses the ong_muop dialogue")
	# everyone is grouped for cat-sense
	assert_true(ba_tu.is_in_group(&"npc") and str(ba_tu.get_meta(&"npc_id")) == "ba_tu")
	assert_true((d.call(&"get_named", &"ven") as Node).is_in_group(&"dog"))
	p.queue_free()


func test_pedestrians_walk_along_navmesh() -> void:
	_make_world()
	for x: float in [-12.0, 12.0]:
		_marker(&"npc_spawn", Vector3(x, 0, -10), {"npc_kind": "pedestrian"})
		_marker(&"pedestrian_poi", Vector3(x, 0, 10), {"activity": "look"})
		_marker(&"pedestrian_poi", Vector3(x * 0.5, 0, 0), {"activity": "chat"})
	_player(Vector3(0, 0.1, 0))
	var d := _director({"spawn_traffic": false, "spawn_animals": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(10)
	var peds: Array = d.get(&"pedestrians")
	assert_true(peds.size() >= 4, "pedestrians spawned (%d)" % peds.size())
	var start_pos: Array[Vector3] = []
	for p: Node3D in peds:
		start_pos.append(p.global_position)
	await _frames(360)
	var moved := 0
	var on_mesh := 0
	var map := _world.get_world_3d().navigation_map
	for i in peds.size():
		var p := peds[i] as Node3D
		if p.global_position.distance_to(start_pos[i]) > 1.5:
			moved += 1
		var cp := NavigationServer3D.map_get_closest_point(map, p.global_position)
		if Vector2(cp.x - p.global_position.x, cp.z - p.global_position.z).length() < 0.6:
			on_mesh += 1
	assert_true(moved >= peds.size() / 2, "most pedestrians walked somewhere (%d/%d)" % [moved, peds.size()])
	assert_eq(on_mesh, peds.size(), "pedestrians stay on the navmesh")


func test_pigeons_flee_fast_approach_but_not_sneaking() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 0, 0), {"npc_kind": "pigeon_flock", "count": 8, "radius": 2.0})
	var p := _player(Vector3(0, 0.05, 14))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(30)
	var flock: Node = (d.get(&"flocks") as Array)[0]
	assert_eq(int(flock.call(&"ground_bird_count")), 8, "all pigeons on the ground at rest")
	# sneaking slowly to ~3 m: they stay
	p.sneaking = true
	for i in 90:
		p.velocity = Vector3(0, 0, -0.45)
		p.global_position.z = maxf(p.global_position.z - 0.45 / 60.0 * 8.0, 4.5)
		await tree.physics_frame
	assert_eq(int(flock.call(&"airborne_bird_count")), 0, "sneaking cat at ~2.5 m from the nearest bird does not flush the flock")
	# running at them: they take off
	p.sneaking = false
	for i in 60:
		p.velocity = Vector3(0, 0, -4.5)
		p.global_position.z -= 4.5 / 60.0
		await tree.physics_frame
	assert_true(int(flock.call(&"airborne_bird_count")) >= 6, "running cat flushes the flock (%d up)" % int(flock.call(&"airborne_bird_count")))
	assert_true(int(flock.get(&"takeoffs")) >= 1)


func test_dog_chases_on_noise_and_gives_up_on_high_ground() -> void:
	_make_world([[Vector3(6, 0.75, 0), Vector3(1.0, 1.5, 1.0)]])
	_marker(&"npc_spawn", Vector3(-6, 0, 0), {"npc_kind": "dog", "npc_id": "ven"}, PI)   # facing away (-Z)
	var p := _player(Vector3(-6, 0.05, 7))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(20)
	var dog: Node3D = d.call(&"get_named", &"ven")
	assert_not_null(dog)
	var d0 := dog.global_position.distance_to(p.global_position)
	var ge := tree.root.get_node("GameEvents")
	var alerts := [0]
	_connect(ge.npc_alerted, func(n: Object, lvl: float) -> void:
		if is_instance_valid(n) and n == dog and lvl >= 0.85:
			alerts[0] += 1)
	ge.player_noise.emit(p.global_position, 1.0)
	await _frames(2)
	ge.player_noise.emit(p.global_position, 1.0)
	await _frames(60)
	assert_eq(String(dog.call(&"get_state_name")), "CHASE", "loud noise behind Vện starts a chase")
	assert_true(alerts[0] >= 1, "npc_alerted emitted for chase music")
	var d1 := dog.global_position.distance_to(p.global_position)
	assert_true(d1 < d0 - 1.0, "Vện closes the distance (%f -> %f)" % [d0, d1])
	# cat jumps on the 1.5 m box: out of reach → bark at the base, then lose interest
	p.global_position = Vector3(6, 1.55, 0)
	await _frames(120)
	assert_eq(String(dog.call(&"get_state_name")), "BARK_UP", "high ground is unreachable")
	await _frames(560)
	assert_true(String(dog.call(&"get_state_name")) in ["RETURN", "PATROL"], "Vện loses interest")


func test_dog_nip_is_never_lethal() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 0, 0), {"npc_kind": "dog", "npc_id": "ven"})
	var p := _player(Vector3(0, 0.05, 3))
	var gs := tree.root.get_node("GameState")
	gs.call(&"set_stat", &"health", 4.0)
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(10)
	var dog: Node3D = d.call(&"get_named", &"ven")
	dog.get(&"perception").call(&"force_awareness", 1.0, p.global_position)
	await _frames(150)
	assert_true(int(dog.get(&"nips")) >= 1, "a cat that stands still gets nipped")
	assert_true(float(gs.call(&"get_stat", &"health")) >= 1.0, "nip never knocks the cat out")
	assert_true(String(dog.call(&"get_state_name")) in ["RETURN", "PATROL"], "satisfied after the nip")


func test_traffic_stops_for_cat_and_follows_leader() -> void:
	_make_world()
	var lane := Path3D.new()
	lane.add_to_group(&"traffic_lane")
	lane.set_meta(&"vehicle_kinds", PackedStringArray(["motorbike"]))
	lane.set_meta(&"speed_limit", 8.0)
	var c := Curve3D.new()
	c.add_point(Vector3(-28, 0, 0))
	c.add_point(Vector3(28, 0, 0))
	lane.curve = c
	_world.add_child(lane)
	var p := _player(Vector3(0, 0.05, 0))
	var d := _director({"spawn_pedestrians": false, "spawn_animals": false, "spawn_geckos": false, "spawn_traffic": false})
	d.call(&"start")
	await _frames(2)
	# two bikes behind the cat
	var v1: Node = d.call(&"_spawn_vehicle", lane, 8.0, 7.0)
	var v2: Node = d.call(&"_spawn_vehicle", lane, 1.0, 7.0)
	await _frames(480)
	var cat_x := p.global_position.x
	var front_x := (v1 as Node3D).global_position.x + float(v1.get(&"length")) * 0.5
	assert_true(bool(v1.get(&"blocked_by_cat")), "lead bike sees the cat")
	assert_true(float(v1.get(&"speed")) < 0.3, "lead bike stopped (speed %f)" % float(v1.get(&"speed")))
	assert_true(front_x < cat_x - 0.1, "stopped before reaching the cat (front %f, cat %f)" % [front_x, cat_x])
	assert_true(float(v2.get(&"speed")) < 0.5, "follower stopped behind the leader")
	assert_true((v2 as Node3D).global_position.x < (v1 as Node3D).global_position.x - 2.0, "follower keeps a gap")
	var vis := v1.get(&"visual") as Node
	var wheel := (vis.call(&"get_rig") as Dictionary).get("WheelF") as Node3D
	if wheel == null and not bool(vis.get(&"is_standin")):
		var ws: Array = vis.call(&"_find_glb_wheels")
		assert_true(ws.size() >= 2, "GLB vehicle wheels found (%d)" % ws.size())
		wheel = ws[0] as Node3D if not ws.is_empty() else null
	var spin_before := wheel.transform.basis if wheel != null else Basis.IDENTITY
	# cat leaves the road: traffic resumes and wheels turn
	p.global_position = Vector3(0, 0.05, 6)
	await _frames(120)
	assert_true(float(v1.get(&"speed")) > 2.0, "bike drives on once the cat is gone")
	if wheel != null:
		assert_false(wheel.transform.basis.is_equal_approx(spin_before), "wheels spin")


func test_vehicle_hit_knocks_cat_back_with_small_damage() -> void:
	_make_world()
	var lane := Path3D.new()
	lane.add_to_group(&"traffic_lane")
	lane.set_meta(&"vehicle_kinds", PackedStringArray(["motorbike"]))
	var c := Curve3D.new()
	c.add_point(Vector3(-28, 0, 0))
	c.add_point(Vector3(28, 0, 0))
	lane.curve = c
	_world.add_child(lane)
	var p := _player(Vector3(20, 0.05, 6))
	var d := _director({"spawn_pedestrians": false, "spawn_animals": false, "spawn_geckos": false, "spawn_traffic": false})
	d.call(&"start")
	await _frames(2)
	var v: Node3D = d.call(&"_spawn_vehicle", lane, 10.0, 8.0)
	var gs := tree.root.get_node("GameState")
	var hp0 := float(gs.call(&"get_stat", &"health"))
	var hits := [0]
	_connect(tree.root.get_node("GameEvents").player_damaged, func(_a: float, src: StringName) -> void:
		if src == &"vehicle":
			hits[0] += 1)
	await _frames(2)
	# the cat darts out right under the front wheel
	p.global_position = v.global_position + Vector3(float(v.get(&"length")) * 0.5 + 0.05, 0.05, 0)
	await _frames(2)
	assert_true(hits[0] >= 1, "collision reported via player_damaged")
	var hp1 := float(gs.call(&"get_stat", &"health"))
	assert_true(hp1 < hp0 and hp1 > hp0 - 25.0, "small damage (%f -> %f)" % [hp0, hp1])
	assert_true(p.velocity.length() > 2.0, "cat knocked back")


func test_lod_sleeps_far_agents() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 0, 0), {"npc_kind": "cat"})
	_marker(&"npc_spawn", Vector3(25, 0, 25), {"npc_kind": "mouse", "day_active": true})
	var p := _player(Vector3(0, 0.05, 2))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.set(&"lod_mid", 15.0)
	d.set(&"lod_far", 20.0)
	d.call(&"start")
	await _frames(30)
	var mouse: Node = (d.get(&"mice") as Array)[0]
	assert_eq(int(mouse.get(&"lod")), 3, "far mouse is asleep")
	assert_false(mouse.is_physics_processing(), "asleep agents are not processed")
	p.global_position = Vector3(24, 0.05, 23)
	await _frames(30)
	assert_true(int(mouse.get(&"lod")) <= 1, "mouse wakes when Cam comes close")


func test_npc_cats_use_variant_coats_and_fur() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 0, 0), {"npc_kind": "cat", "npc_id": "mun"})
	_marker(&"npc_spawn", Vector3(3, 0, 0), {"npc_kind": "cat", "npc_id": "bong"})
	_player(Vector3(0, 0.05, 6))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(5)
	var mun: Node = d.call(&"get_named", &"mun")
	assert_not_null(mun.get(&"model"), "Mun uses cat.glb")
	assert_not_null(mun.get(&"anim_player"), "with its animations")
	var fur: Node = mun.get(&"fur")
	if fur != null:
		var base: Variant = fur.call(&"get_base_material")
		assert_not_null(base, "fur shells attached")
	else:
		var body := (mun.get(&"model") as Node).find_child("CatBody", true, false) as MeshInstance3D
		var m := body.get_surface_override_material(0) as StandardMaterial3D
		assert_true(m != null and m.albedo_texture.resource_path.ends_with("cat_albedo_black.png"), "black coat")
	assert_eq(String((d.call(&"get_named", &"bong") as Node).get(&"profile")["coat"]), "cat_albedo_white.png")


func test_mouse_flees_and_can_be_caught() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 0, 0), {"npc_kind": "mouse", "day_active": true, "roam_radius": 3.0})
	var p := _player(Vector3(0, 0.05, 10))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(10)
	var mouse: Node3D = (d.get(&"mice") as Array)[0]
	p.global_position = mouse.global_position + Vector3(1.0, 0, 0)
	await _frames(20)
	assert_true(int(mouse.get(&"flee_count")) >= 1, "mouse flees from a close cat")
	# catching: max hunting → high chance; several attempts must succeed at least once
	var gs := tree.root.get_node("GameState")
	gs.call(&"set_attribute", &"hunting", 10)
	var caught := false
	for i in 12:
		mouse.call(&"_enter", 1)    # FORAGE (visible)
		if bool(mouse.call(&"_try_catch")):
			caught = true
			break
	assert_true(caught, "mouse can be caught")
	assert_true(int(gs.call(&"get_counter", &"prey_mouse")) >= 1 if gs.has_method(&"get_counter") else true, "catch registered")


func test_koi_and_sparrows_react() -> void:
	_make_world()
	_marker(&"npc_spawn", Vector3(0, 2, 0), {"npc_kind": "koi", "volume_size": Vector3(6, 0.8, 4), "count": 6})
	_marker(&"npc_spawn", Vector3(-3, 5, -8), {"npc_kind": "sparrows", "wire_end": Vector3(6, 0, 0), "count": 5})
	var p := _player(Vector3(0, 0.05, 12))
	var d := _director({"spawn_traffic": false, "spawn_pedestrians": false, "spawn_geckos": false})
	d.call(&"start")
	await _frames(60)
	var koi: Node = (d.get(&"koi_schools") as Array)[0]
	assert_eq((koi.get(&"fish") as Array).size(), 6)
	for f: Dictionary in koi.get(&"fish"):
		var lp: Vector3 = f["pos"]
		assert_true(lp.y < 0.0 and lp.y > -0.9 and absf(lp.x) < 3.2 and absf(lp.z) < 2.2, "koi stays in its water volume %s" % str(lp))
	var calm := float(koi.call(&"mean_speed"))
	tree.root.get_node("GameEvents").player_noise.emit(Vector3(1, 0, 1), 0.8)
	await _frames(40)
	assert_true(float(koi.call(&"mean_speed")) > calm, "koi dart away from a splash")
	var wire: Node = (d.get(&"sparrow_wires") as Array)[0]
	p.global_position = Vector3(0, 4.8, -8)
	await _frames(10)
	assert_true(int(wire.get(&"scatter_count")) >= 1, "sparrows burst off the wire when Cam climbs close")


## city.tscn is saved with non-persistent groups: markers must be found from their metadata, and
## lane sub-kinds (scooter, cyclo) must map onto the driving models and keep recycling.
func test_markers_without_groups_and_lane_subkinds() -> void:
	_make_world()
	var markers := Node3D.new()
	markers.name = "Markers"
	_world.add_child(markers)
	var lane := Path3D.new()
	lane.name = "Lane_test"
	lane.set_meta(&"vehicle_kinds", PackedStringArray(["scooter", "cyclo"]))
	lane.set_meta(&"speed_limit", 8.0)
	var c := Curve3D.new()
	c.add_point(Vector3(-28, 0, -6))
	c.add_point(Vector3(28, 0, -6))
	lane.curve = c
	markers.add_child(lane)
	var ped_spawn := Marker3D.new()
	ped_spawn.set_meta(&"npc_kind", "pedestrian")
	ped_spawn.set_meta(&"npc_id", "")
	markers.add_child(ped_spawn)
	ped_spawn.global_position = Vector3(5, 0, 5)
	var dog := Marker3D.new()
	dog.set_meta(&"npc_kind", "dog")
	dog.set_meta(&"npc_id", "ven")
	markers.add_child(dog)
	dog.global_position = Vector3(-5, 0, 5)
	var poi := Marker3D.new()
	poi.set_meta(&"activity", "look")
	markers.add_child(poi)
	poi.global_position = Vector3(10, 0, 10)
	_player(Vector3(0, 0.05, 20))
	var d := _director({"spawn_geckos": false})
	d.call(&"start")
	await _frames(30)
	assert_not_null(d.call(&"get_named", &"ven"), "dog marker found without a group")
	assert_eq((d.get(&"lanes") as Array).size(), 1, "lane found from vehicle_kinds metadata")
	assert_eq((d.get(&"pois") as Array).size(), 1, "poi found from activity metadata")
	var vs: Array = d.get(&"vehicles")
	assert_true(vs.size() > 0, "vehicles spawned on a scooter/cyclo lane")
	for v: Node in vs:
		assert_true(v.get(&"kind") in [&"motorbike", &"bicycle"], "sub-kind mapped to a driving model: %s" % v.get(&"kind"))
		assert_true(v.get(&"variant") in [&"scooter", &"cyclo"], "variant kept: %s" % v.get(&"variant"))
	assert_true(bool(d.call(&"lane_accepts", lane, &"motorbike")), "scooter lane accepts motorbikes")
	assert_true(bool(d.call(&"lane_accepts", lane, &"bicycle")), "cyclo lane accepts bicycles")
	assert_false(bool(d.call(&"lane_accepts", lane, &"car")), "no cars on this lane")
	# a vehicle reaching the lane end is recycled (back on the lane start, or into the pool)
	var v0: Node = vs[0]
	v0.set(&"offset", float(v0.get(&"lane_length")) - 0.05)
	v0.set(&"speed", 5.0)
	await _frames(4)
	var recycled := (bool(v0.get(&"active")) and float(v0.get(&"offset")) < 5.0) or (d.get(&"vehicle_pool") as Array).has(v0)
	assert_true(recycled, "vehicle at the lane end re-entered the lane or went back to the pool")
