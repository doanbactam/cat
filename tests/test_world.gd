extends "res://tests/test_base.gd"
## world: city scene loads, contract nodes/groups exist, spawn stands on solid ground, markers and
## interactables per the CLAUDE.md conventions, weather API + wetness, time-of-day lighting,
## rooftop-network connectors and walkable cables, navmesh baked, surface helper.

const CITY := "res://scenes/world/city.tscn"
const SURFACES: Array[StringName] = [&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt",
	&"water", &"roof_tile", &"fabric", &"plastic"]

static var _city: Node3D = null


func _get_city() -> Node3D:
	if _city != null and is_instance_valid(_city):
		return _city
	var ps := load(CITY) as PackedScene
	if ps == null:
		return null
	_city = ps.instantiate() as Node3D
	tree.root.add_child(_city)
	return _city


func _settle(frames: int = 3) -> void:
	for i in frames:
		await tree.physics_frame


func test_a_scene_loads_with_contract_nodes() -> void:
	var city := _get_city()
	assert_not_null(city, "city.tscn loads")
	if city == null:
		return
	assert_eq(city.name, &"City")
	assert_true(city.get_node_or_null("WorldEnvironment") is WorldEnvironment, "WorldEnvironment")
	assert_true(city.get_node_or_null("Sun") is DirectionalLight3D, "Sun")
	assert_true(city.get_node_or_null("Moon") is DirectionalLight3D, "Moon")
	var ws := city.get_node_or_null("WeatherSystem")
	assert_not_null(ws, "WeatherSystem")
	assert_true(ws != null and ws.is_in_group(&"weather"), "weather group")
	var spawn := tree.get_first_node_in_group(&"player_spawn")
	assert_true(spawn is Marker3D, "PlayerSpawn marker")
	assert_eq(String(spawn.name), "PlayerSpawn")
	var nav := tree.get_first_node_in_group(&"nav_region")
	assert_true(nav is NavigationRegion3D and nav.name == &"NavRegion", "NavRegion")
	if nav is NavigationRegion3D:
		var nm := (nav as NavigationRegion3D).navigation_mesh
		assert_true(nm != null and nm.get_polygon_count() > 500, "navmesh baked (%d polys)" % (nm.get_polygon_count() if nm else 0))
	assert_true(city.get_node_or_null("WorldEnvironment").is_in_group(&"graphics_settings_listener"), "env listens to settings")


func test_b_markers() -> void:
	var city := _get_city()
	await _settle(1)
	var locs := tree.get_nodes_in_group(&"location")
	assert_true(locs.size() >= 8, "≥8 locations (%d)" % locs.size())
	var ids := {}
	for n in locs:
		assert_true(n is Marker3D, "location is Marker3D")
		assert_true(n.has_meta(&"location_id") and n.has_meta(&"display_name_key"), "location meta")
		ids[str(n.get_meta(&"location_id"))] = true
	for want in ["tea_stall", "banyan", "water_tower", "temple_roof", "riddle_bridge", "riddle_bell", "riddle_sun"]:
		assert_true(ids.has(want), "location " + want)
	var npc_ids := {}
	var kinds := {}
	for n in tree.get_nodes_in_group(&"npc_spawn"):
		npc_ids[str(n.get_meta(&"npc_id", ""))] = true
		kinds[str(n.get_meta(&"npc_kind", ""))] = true
	for want in ["ba_tu", "mun", "bong", "ong_muop", "lao_qua", "ven", "co_hoa", "chu_sau", "bin", "xam"]:
		assert_true(npc_ids.has(want), "npc spawn " + want)
	for k in ["pedestrian", "pigeon_flock", "koi", "mouse", "cat", "dog", "crow", "vendor"]:
		assert_true(kinds.has(k), "npc kind " + k)
	var patrol_ids := {}
	for p in tree.get_nodes_in_group(&"patrol_path"):
		assert_true(p is Path3D and (p as Path3D).curve.point_count >= 2, "patrol path has points")
		patrol_ids[str(p.get_meta(&"npc_id", ""))] = true
	assert_true(patrol_ids.has("ven"), "Vện patrol")
	var lanes := tree.get_nodes_in_group(&"traffic_lane")
	assert_true(lanes.size() >= 8, "traffic lanes")
	for l in lanes:
		assert_true(l.get_meta(&"vehicle_kinds") is PackedStringArray and l.has_meta(&"speed_limit"), "lane meta")
	assert_true(tree.get_nodes_in_group(&"pedestrian_poi").size() >= 12, "pedestrian POIs")
	var targets := {}
	for q in tree.get_nodes_in_group(&"quest_target"):
		targets[str(q.get_meta(&"target_id", ""))] = true
	for want in ["tea_stall", "crow_nest", "fish_stall", "water_tower", "bins_key_spot", "leg_band_spot", "postman_bag", "race_start", "stall_counter"]:
		assert_true(targets.has(want), "quest target " + want)
	assert_true(tree.get_nodes_in_group(&"shelter").size() >= 10, "shelters")
	# QuestManager resolves targets in the city
	var qm := tree.root.get_node_or_null("QuestManager")
	if qm != null and qm.has_method(&"find_target_node"):
		assert_not_null(qm.call(&"find_target_node", &"crow_nest"), "QuestManager finds crow_nest")


func test_c_interactables() -> void:
	_get_city()
	await _settle(1)
	var naps := 0
	var terr := 0
	var mems := 0
	var caps := 0
	var food := 0
	for n in tree.get_nodes_in_group(&"interactable"):
		var s := n.get_script() as Script
		if s == null:
			continue
		var path := s.resource_path
		if path.ends_with("nap_spot.gd"):
			naps += 1
		elif path.ends_with("territory_spot.gd"):
			terr += 1
		elif path.ends_with("collectible.gd"):
			if str(n.get(&"kind")) == "memory":
				mems += 1
			elif str(n.get(&"kind")) == "caps":
				caps += 1
		elif path.ends_with("food_source.gd"):
			food += 1
	assert_true(naps >= 8, "8 nap spots (%d)" % naps)
	assert_true(terr >= 10, "10 territory spots (%d)" % terr)
	assert_eq(mems, 12, "12 memories")
	assert_true(caps >= 30, "30 cap stashes (%d)" % caps)
	assert_true(food >= 4, "food/water sources (%d)" % food)
	var knock := tree.get_nodes_in_group(&"pushable").size()
	assert_true(knock >= 20, "≥20 knockables (%d)" % knock)
	var muop := false
	for n in tree.get_nodes_in_group(&"interactable"):
		if str(n.get(&"spot_id")) == "muop_secret_nap":
			muop = true
	assert_true(muop, "muop_secret_nap exists")


func test_d_spawn_on_solid_ground() -> void:
	var city := _get_city()
	await _settle(3)
	var spawn := tree.get_first_node_in_group(&"player_spawn") as Marker3D
	if spawn == null:
		assert_true(false, "no spawn")
		return
	var space := city.get_world_3d().direct_space_state
	var p := spawn.global_position
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.5, p + Vector3.DOWN * 1.0, 1)
	var hit := space.intersect_ray(q)
	assert_false(hit.is_empty(), "solid ground under spawn")
	if not hit.is_empty():
		assert_true(absf((hit["position"] as Vector3).y - p.y) < 0.4, "spawn close to the surface")
		assert_true((hit["normal"] as Vector3).y > 0.7, "walkable surface")
		assert_true(p.y > 5.0, "spawn is on a rooftop (y=%.1f)" % p.y)
	# no collider occupying the spawn volume
	var sq := PhysicsShapeQueryParameters3D.new()
	var sph := SphereShape3D.new()
	sph.radius = 0.12
	sq.shape = sph
	sq.transform = Transform3D(Basis(), p + Vector3.UP * 0.2)
	sq.collision_mask = 1
	assert_true(space.intersect_shape(sq, 1).is_empty(), "spawn volume is free")
	# tea stall is reachable on the ground (navmesh near it)
	var nav := tree.get_first_node_in_group(&"nav_region") as NavigationRegion3D
	if nav != null:
		var map := nav.get_navigation_map()
		await tree.physics_frame
		var cp := NavigationServer3D.map_get_closest_point(map, Vector3(-87.4, 0.0, -66.0))
		assert_true(cp.distance_to(Vector3(-87.4, 0.0, -66.0)) < 1.0, "navmesh at the tea stall (%s)" % cp)


func test_e_weather_api() -> void:
	var city := _get_city()
	await _settle(1)
	var ws := tree.get_first_node_in_group(&"weather")
	assert_true(ws.has_method(&"set_weather") and ws.has_method(&"get_weather") and ws.has_method(&"get_intensity"), "weather API")
	var got := []
	var cb := func(k: StringName, i: float) -> void: got.append([k, i])
	GameEvents.weather_changed.connect(cb)
	ws.call(&"set_weather", &"rain", 0.8)
	assert_eq(ws.call(&"get_weather"), &"rain")
	assert_near(float(ws.call(&"get_intensity")), 0.8)
	assert_true(got.size() == 1 and got[0][0] == &"rain", "weather_changed emitted")
	ws.call(&"snap")
	await tree.process_frame
	assert_true(float(ws.call(&"get_wetness")) > 0.5, "wetness ramps up in rain")
	assert_true(float(ws.call(&"get_wet_material_count")) > 20, "imported materials tracked for wetness")
	ws.call(&"set_weather_immediate", &"clear", 0.0, 0.0)
	await tree.process_frame
	assert_near(float(ws.call(&"get_wetness")), 0.0, 0.01, "dry again")
	ws.call(&"set_weather", &"nonsense", 1.0)
	assert_eq(ws.call(&"get_weather"), &"clear", "unknown kind falls back to clear")
	GameEvents.weather_changed.disconnect(cb)
	assert_eq(GameState.get_weather(), &"clear", "GameState follows weather")


func test_f_time_of_day_lighting() -> void:
	var city := _get_city()
	await _settle(1)
	var env := city.get_node("WorldEnvironment")
	var sun := city.get_node("Sun") as DirectionalLight3D
	var moon := city.get_node("Moon") as DirectionalLight3D
	TimeOfDay.set_hour(12.5)
	env.call(&"update_lighting")
	var noon_energy := sun.light_energy
	var noon_dir := -sun.global_basis.z
	assert_true(noon_energy > 1.0, "bright noon sun (%.2f)" % noon_energy)
	assert_true(noon_dir.y < -0.8, "noon sun high (light points down)")
	assert_true(float(env.get(&"night_factor")) < 0.05, "day → night_factor 0")
	TimeOfDay.set_hour(17.8)
	env.call(&"update_lighting")
	assert_true(sun.light_color.b < 0.8, "golden hour sun is warm (%s)" % sun.light_color)
	assert_true((-sun.global_basis.z).x > 0.3, "evening sun in the west (light travels east)")
	TimeOfDay.set_hour(23.0)
	env.call(&"update_lighting")
	assert_true(float(env.get(&"night_factor")) > 0.95, "night_factor 1 at night")
	assert_true(sun.light_energy < 0.01, "sun off at night")
	assert_true((env as WorldEnvironment).environment.tonemap_exposure > 1.3, "night exposure raised")
	TimeOfDay.set_hour(8.0)
	env.call(&"update_lighting")


func test_g_rooftop_network_and_cables() -> void:
	var city := _get_city()
	await _settle(1)
	var conn := city.get_node_or_null("Connectors")
	assert_true(conn != null and conn.get_child_count() > 5, "rooftop connectors (planks/crates) placed")
	var balance := tree.get_nodes_in_group(&"balance_cable")
	assert_true(balance.size() >= 3, "≥3 walkable cable bundles (%d)" % balance.size())
	for b in balance:
		assert_true((b as CollisionObject3D).collision_layer & 1 != 0, "cable on world layer")
		assert_true(bool(b.get_meta(&"balance", false)), "cable meta balance")
	var f := FileAccess.open("res://qa/out/world/build_report.json", FileAccess.READ)
	if f != null:
		var rep: Variant = JSON.parse_string(f.get_as_text())
		if rep is Dictionary and (rep as Dictionary).has("post"):
			var cov := float(rep["post"].get("net_coverage_after", 0.0))
			assert_true(cov >= 0.6, "rooftop network: largest component covers %.0f%% of net modules" % (cov * 100.0))


func test_h_surfaces_and_water() -> void:
	var city := _get_city()
	await _settle(2)
	var surf: Variant = load("res://scripts/world/surface.gd")
	var space := city.get_world_3d().direct_space_state
	var probes := {Vector3(-20, 1, -70): &"asphalt", Vector3(-20, 1, -75.5): &"tile", Vector3(-90, 1, 10): &"concrete", Vector3(-40, 1, 40): &"grass"}
	for p: Vector3 in probes:
		var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(p, p + Vector3.DOWN * 3.0, 1))
		assert_false(hit.is_empty(), "ground at %s" % p)
		if not hit.is_empty():
			var s: StringName = surf.call(&"get_surface", hit["collider"])
			assert_true(s in SURFACES, "valid surface")
			assert_eq(s, probes[p], "surface at %s" % p)
	var water := false
	for a in tree.get_nodes_in_group(&"water"):
		if a is Area3D and ((a as Area3D).collision_layer & (1 << 6)) != 0 and a.has_meta(&"water_level"):
			water = true
	assert_true(water, "lake water volume on layer 7 with water_level")


func test_z_cleanup() -> void:
	if _city != null and is_instance_valid(_city):
		_city.queue_free()
		_city = null
	await tree.process_frame
	assert_true(true)
