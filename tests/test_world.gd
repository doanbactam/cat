extends "res://tests/test_base.gd"
## world: city.tscn contract — loads, required nodes / groups / markers exist with the CLAUDE.md
## metadata, PlayerSpawn stands on solid ground, every location / npc spawn / quest target is inside
## the map, WeatherSystem API + wetness ramp, TimeOfDay lighting response, surface helper.
## The city is instanced once (static) and freed by the last test.

const CITY := "res://scenes/world/city.tscn"
const NAMED_NPCS: Array[String] = ["ba_tu", "mun", "bong", "muop", "lao_qua", "ven", "co_hoa", "chu_sau", "bin", "xam"]
const NPC_KINDS: Array[String] = ["pedestrian", "vendor", "cat", "dog", "crow", "pigeon_flock", "mouse", "koi"]
const SURFACES: Array[StringName] = [&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt",
	&"water", &"roof_tile", &"fabric", &"plastic"]

static var _city: Node3D


func _get_city() -> Node3D:
	if _city == null or not is_instance_valid(_city):
		var ps := load(CITY) as PackedScene
		if ps == null:
			return null
		_city = ps.instantiate() as Node3D
		tree.root.add_child(_city)
		for i in 4:
			await tree.physics_frame
	return _city


func _group_in_city(g: StringName) -> Array:
	var out: Array = []
	for n in tree.get_nodes_in_group(g):
		if _city != null and (_city == n or _city.is_ancestor_of(n)):
			out.append(n)
	return out


func _in_map(p: Vector3) -> bool:
	return absf(p.x) <= 125.0 and p.z >= -105.0 and p.z <= 115.0 and p.y > -3.0 and p.y < 40.0


func test_a_city_loads_with_required_nodes() -> void:
	var city: Node3D = await _get_city()
	assert_not_null(city, "city.tscn loads")
	if city == null:
		return
	assert_eq(String(city.name), "City")
	assert_true(city.get_node_or_null(^"WorldEnvironment") is WorldEnvironment, "WorldEnvironment")
	assert_true(city.get_node_or_null(^"Sun") is DirectionalLight3D, "Sun")
	assert_true(city.get_node_or_null(^"Moon") is DirectionalLight3D, "Moon")
	var ws := city.get_node_or_null(^"WeatherSystem")
	assert_not_null(ws, "WeatherSystem")
	assert_true(ws != null and ws.is_in_group(&"weather"), "WeatherSystem in group weather")
	assert_eq(_group_in_city(&"graphics_settings_listener").size() >= 1, true, "graphics_settings_listener")
	var nav := _group_in_city(&"nav_region")
	assert_eq(nav.size(), 1, "one NavRegion")
	if nav.size() == 1:
		var nr := nav[0] as NavigationRegion3D
		assert_eq(String(nr.name), "NavRegion")
		assert_true(nr.navigation_mesh != null and nr.navigation_mesh.get_polygon_count() > 1000, "baked navmesh")


func test_b_markers_follow_conventions() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var spawns := _group_in_city(&"player_spawn")
	assert_eq(spawns.size(), 1, "one PlayerSpawn")
	assert_true(spawns.size() == 1 and spawns[0] is Marker3D and String(spawns[0].name) == "PlayerSpawn", "PlayerSpawn Marker3D")
	var locs := _group_in_city(&"location")
	assert_true(locs.size() >= 8, "location markers: %d" % locs.size())
	var loc_ids := {}
	for l: Node in locs:
		assert_true(l is Marker3D and l.has_meta(&"location_id") and l.has_meta(&"display_name_key"), "location meta " + String(l.name))
		loc_ids[str(l.get_meta(&"location_id", ""))] = true
		assert_true(_in_map((l as Node3D).global_position), "location in map " + String(l.name))
	for id in ["tea_stall", "banyan", "water_tower", "temple_roof", "riddle_bridge", "riddle_bell", "riddle_sun"]:
		assert_true(loc_ids.has(id), "story location " + id)
	# npc spawns
	var named := {}
	var kinds := {}
	for m: Node in _group_in_city(&"npc_spawn"):
		var k := str(m.get_meta(&"npc_kind", ""))
		assert_true(k in NPC_KINDS or k in ["sparrows", "pigeon"], "npc_kind valid: " + k)
		kinds[k] = true
		var id := str(m.get_meta(&"npc_id", ""))
		if id != "":
			named[id] = true
		assert_true(_in_map((m as Node3D).global_position), "npc spawn in map " + String(m.name))
	for id in NAMED_NPCS:
		assert_true(named.has(id), "npc_spawn for " + id)
	for k in ["pedestrian", "pigeon_flock", "koi", "mouse", "cat", "dog", "crow"]:
		assert_true(kinds.has(k), "npc kind present " + k)
	# paths
	var ven := false
	for p: Node in _group_in_city(&"patrol_path"):
		assert_true(p is Path3D and (p as Path3D).curve != null and (p as Path3D).curve.point_count >= 3, "patrol curve")
		if str(p.get_meta(&"npc_id", "")) == "ven":
			ven = true
	assert_true(ven, "patrol_path for ven")
	var lanes := _group_in_city(&"traffic_lane")
	assert_true(lanes.size() >= 4, "traffic lanes: %d" % lanes.size())
	for l: Node in lanes:
		assert_true(l.get_meta(&"vehicle_kinds", null) is PackedStringArray, "lane vehicle_kinds")
		assert_true(float(l.get_meta(&"speed_limit", 0.0)) > 0.0, "lane speed_limit")
	var pois := _group_in_city(&"pedestrian_poi")
	assert_true(pois.size() >= 10, "pedestrian POIs")
	for p: Node in pois:
		assert_true(str(p.get_meta(&"activity", "")) in ["sit", "shop", "chat", "wait", "look"], "poi activity")
	var qt := {}
	for q: Node in _group_in_city(&"quest_target"):
		qt[str(q.get_meta(&"target_id", ""))] = true
	for id in ["tea_stall", "crow_nest", "fish_stall", "water_tower", "stall_counter", "bins_key_spot", "leg_band_spot",
			"postman_bag", "race_start", "temple_roof", "banyan"]:
		assert_true(qt.has(id), "quest_target " + id)
	assert_true(_group_in_city(&"shelter").size() >= 20, "shelter areas")


func test_c_interactables_counts() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var naps := 0
	var terr := 0
	var memories := 0
	var caps := 0
	var food := 0
	var push := 0
	for n: Node in _group_in_city(&"interactable"):
		var sc: Script = n.get_script()
		var path := sc.resource_path if sc != null else ""
		if path.ends_with("nap_spot.gd"):
			naps += 1
		elif path.ends_with("territory_spot.gd"):
			terr += 1
		elif path.ends_with("collectible.gd"):
			if str(n.get(&"kind")) == "memory":
				memories += 1
			elif str(n.get(&"kind")) == "caps":
				caps += 1
		elif path.ends_with("food_source.gd"):
			food += 1
	for n: Node in city.get_node(^"Interactables").get_children():
		if n is RigidBody3D:
			push += 1
	assert_true(naps >= 8, "nap spots %d" % naps)
	assert_true(terr >= 10, "territory spots %d" % terr)
	assert_eq(memories, 12, "memories")
	assert_eq(caps, 30, "bottle cap stashes")
	assert_true(food >= 4, "food/water sources %d" % food)
	assert_true(push >= 20, "knockables %d" % push)


func test_d_spawn_on_solid_ground() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var spawn := _group_in_city(&"player_spawn")
	if spawn.is_empty():
		return
	var p := (spawn[0] as Node3D).global_position
	var space := city.get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.3, p + Vector3.DOWN * 1.0, 1)
	var hit := space.intersect_ray(q)
	assert_false(hit.is_empty(), "solid ground under spawn %s" % p)
	if not hit.is_empty():
		assert_true(absf((hit["position"] as Vector3).y - p.y) < 0.4, "spawn close to ground (%.2f vs %.2f)" % [p.y, (hit["position"] as Vector3).y])
		assert_true((hit["normal"] as Vector3).y > 0.7, "walkable normal under spawn")
		assert_true(p.y > 3.0, "spawn is on a rooftop")
	# room to stand: a cat-sized box just above the spawn is free
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.3, 0.25, 0.5)
	var sq := PhysicsShapeQueryParameters3D.new()
	sq.shape = shape
	sq.transform = Transform3D(Basis(), p + Vector3.UP * 0.2)
	sq.collision_mask = 1
	assert_true(space.intersect_shape(sq, 4).is_empty(), "no geometry intersecting the cat at spawn")


func test_e_ground_and_surfaces() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var space := city.get_world_3d().direct_space_state
	var surf: GDScript = load("res://scripts/world/surface.gd")
	# sample street, sidewalk, alley, lake water volume
	var probes := {Vector3(-20.0, 0, -70.0): [&"asphalt"], Vector3(-90.0, 0, -20.0): [&"concrete", &"tile"]}
	for p: Vector3 in probes:
		var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.5, p + Vector3.DOWN * 1.0, 1)
		var hit := space.intersect_ray(q)
		assert_false(hit.is_empty(), "ground at %s" % p)
		if not hit.is_empty():
			var s: StringName = surf.call(&"get_surface", hit["collider"])
			assert_true(s in SURFACES, "valid surface %s" % s)
			assert_true(s in probes[p], "surface at %s is %s" % [p, s])
	# water volume on layer 7 with water_level
	var found := false
	for a: Node in _group_in_city(&"water"):
		if a is Area3D and (a as Area3D).collision_layer & (1 << 6) and a.has_meta(&"water_level"):
			found = true
			assert_near(float(a.get_meta(&"water_level")), -1.0, 0.05, "lake water level")
	assert_true(found, "lake water Area3D on layer 7")


func test_f_weather_api() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var ws := city.get_node_or_null(^"WeatherSystem")
	if ws == null:
		return
	ws.set(&"auto_weather", false)
	for k: StringName in [&"clear", &"cloudy", &"rain", &"storm", &"fog"]:
		ws.call(&"set_weather", k, 0.7)
		assert_eq(ws.call(&"get_weather"), k, "get_weather " + String(k))
	assert_near(float(ws.call(&"get_intensity")), 0.7, 0.001, "get_intensity")
	ws.call(&"set_weather_immediate", &"rain", 1.0, 0.8)
	await tree.process_frame
	await tree.process_frame
	var w: float = float(ws.call(&"get_wetness"))
	assert_true(w > 0.5, "wetness after rain: %f" % w)
	assert_true(int(ws.call(&"get_wet_material_count")) > 10, "imported materials registered for wetness")
	ws.call(&"set_weather_immediate", &"clear", 0.0, 0.0)
	await tree.process_frame
	await tree.process_frame
	w = float(ws.call(&"get_wetness"))
	assert_true(w < 0.05, "dry after clear: %f" % w)
	var wind := float(ws.get(&"wind_strength"))
	assert_true(wind > 0.0 and wind < 0.6, "clear-day wind_strength %f" % wind)
	ws.call(&"set_weather_immediate", &"storm", 1.0, 1.0)
	await tree.process_frame
	assert_true(float(ws.get(&"wind_strength")) > 0.7, "storm wind")
	ws.call(&"set_weather_immediate", &"clear", 0.0, 0.0)
	await tree.process_frame


func test_g_time_of_day_lighting() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var env := city.get_node(^"WorldEnvironment")
	var sun := city.get_node(^"Sun") as DirectionalLight3D
	env.call(&"set_hour_override", 12.5)
	var noon_energy := sun.light_energy
	var noon_night: float = env.get(&"night_factor")
	var noon_dir := -sun.global_transform.basis.z
	env.call(&"set_hour_override", 23.0)
	var night_energy := sun.light_energy
	var night_nf: float = env.get(&"night_factor")
	assert_true(noon_energy > 1.0, "sun bright at noon: %f" % noon_energy)
	assert_true(night_energy < 0.05 or not sun.visible, "sun off at night")
	assert_true(noon_night < 0.05 and night_nf > 0.95, "night_factor %f -> %f" % [noon_night, night_nf])
	assert_true(noon_dir.y < -0.7, "noon sun shines downward")
	env.call(&"set_hour_override", 6.5)
	var dawn_col := sun.light_color
	assert_true(dawn_col.r > dawn_col.b, "warm dawn light")
	var nl := city.get_node_or_null(^"NightLights")
	assert_not_null(nl, "NightLights controller")
	env.call(&"set_hour_override", 12.0)


func test_h_rooftop_network_and_cables() -> void:
	var city: Node3D = await _get_city()
	if city == null:
		return
	var conn := city.get_node_or_null(^"Connectors")
	assert_true(conn != null and conn.get_child_count() > 5, "rooftop connectors (planks / crate stairs)")
	var balance := _group_in_city(&"balance_cable")
	assert_true(balance.size() >= 3, "walkable cable bundles: %d" % balance.size())
	for b: Node in balance:
		assert_true(b is CollisionObject3D and (b as CollisionObject3D).collision_layer & 1 != 0, "cable on world layer")
		assert_true(bool(b.get_meta(&"balance", false)), "cable meta balance")
	var f := FileAccess.open("res://qa/out/world/build_report.json", FileAccess.READ)
	if f != null:
		var rep: Variant = JSON.parse_string(f.get_as_text())
		if rep is Dictionary and (rep as Dictionary).has("post"):
			var cov := float((rep["post"] as Dictionary).get("net_coverage_after", 0.0))
			assert_true(cov >= 0.9, "rooftop network: largest component covers %.0f%% of net modules" % (cov * 100.0))


func test_z_cleanup() -> void:
	if _city != null and is_instance_valid(_city):
		_city.queue_free()
		await tree.process_frame
		_city = null
	RenderingServer.global_shader_parameter_set(&"wetness", 0.0)
