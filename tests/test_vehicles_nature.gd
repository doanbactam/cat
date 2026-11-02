extends "res://tests/test_base.gd"
## vehicles-nature: catalog contracts, import results (shared materials, wind vertex colours,
## colliders on the right layers, named wheel nodes with hub origins) and physics checks that
## the advertised nap spots / climb points are really supported.

const NATURE := "res://assets/models/nature/catalog.json"
const VEHICLES := "res://assets/models/vehicles/catalog.json"
const SURFACES: Array[StringName] = [&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt",
	&"water", &"roof_tile", &"fabric", &"plastic"]
const LAYER_WORLD := 1
const LAYER_PROPS := 1 << 3
const LAYER_CLIMB := 1 << 5
const LAYER_VEHICLES := 1 << 7
const TREES: Array[String] = ["banyan", "flame_tree", "sao_tree", "frangipani", "coconut_palm", "areca_palm",
	"weeping_willow", "bamboo_clump"]
const PLANTS: Array[String] = ["shrub_ixora", "hedge_trimmed", "bougainvillea_wall", "bougainvillea_cascade",
	"fern_clump", "grass_tuft_a", "grass_tuft_b", "weeds_crack_a", "weeds_crack_b", "moss_patch", "leaf_litter",
	"lotus_cluster", "water_hyacinth"]
const CARS: Array[String] = ["scooter_auto", "underbone_step", "manual_classic", "bicycle_city", "cyclo",
	"cargo_trike", "taxi_hatch", "delivery_van"]
const HELMETS: Array[String] = ["helmet_half", "helmet_open"]


func _load(path: String) -> Array:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return []
	var data: Variant = JSON.parse_string(f.get_as_text())
	return data if data is Array else []


func _by_id(cat: Array) -> Dictionary:
	var out := {}
	for e: Variant in cat:
		out[String((e as Dictionary)["id"])] = e
	return out


func _vec(a: Variant) -> Vector3:
	var arr := a as Array
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))


func test_nature_catalog_contract() -> void:
	var cat := _load(NATURE)
	var ids := _by_id(cat)
	for id in TREES + PLANTS:
		assert_true(ids.has(id), "nature catalog has " + id)
	for e: Variant in cat:
		var d := e as Dictionary
		for k in ["id", "file", "kind", "width", "depth", "height", "climb_points", "nap_spots", "entrances", "tris"]:
			assert_true(d.has(k), "%s missing %s" % [d.get("id", "?"), k])
		assert_true(ResourceLoader.exists(String(d["file"])), "file exists " + String(d["file"]))
		assert_true(float(d["height"]) > 0.0, String(d["id"]) + " height")
		assert_true(int(d["tris"]) < 60000, "%s tris %d" % [d["id"], int(d["tris"])])
	for id in ["banyan", "flame_tree", "sao_tree", "coconut_palm", "weeping_willow"]:
		if ids.has(id):
			assert_true((ids[id]["climb_points"] as Array).size() >= 2, id + " climb points")
	if ids.has("banyan"):
		var b: Dictionary = ids["banyan"]
		assert_true((b["nap_spots"] as Array).size() >= 3, "banyan nap spots")
		assert_true(float(b["width"]) > 12.0 and float(b["height"]) > 8.0, "banyan is a giant: %sx%s" % [b["width"], b["height"]])


func test_vehicle_catalog_contract() -> void:
	var cat := _load(VEHICLES)
	var ids := _by_id(cat)
	for id in CARS + HELMETS:
		assert_true(ids.has(id), "vehicle catalog has " + id)
	for id in CARS:
		if not ids.has(id):
			continue
		var d: Dictionary = ids[id]
		assert_true(int(d["tris"]) <= 25000, "%s tris %d <= 25k" % [id, int(d["tris"])])
		assert_true((d["wheels"] as Array).size() >= 2, id + " wheels listed")
		assert_true(d.has("seat") and (d["seat"] as Array).size() == 3, id + " seat marker")
		assert_true(float(d["mass"]) > 0.0, id + " mass")
	# real-world sizes (length along Godot Z)
	var sizes := {"scooter_auto": [1.7, 2.0], "underbone_step": [1.8, 2.05], "bicycle_city": [1.6, 1.9],
		"cyclo": [2.1, 2.5], "taxi_hatch": [3.4, 3.9], "delivery_van": [4.2, 4.8]}
	for id: String in sizes:
		if ids.has(id):
			var L := float(ids[id]["length"])
			assert_true(L >= sizes[id][0] and L <= sizes[id][1], "%s length %.2f" % [id, L])
	for id in HELMETS:
		if ids.has(id):
			assert_true(bool(ids[id]["dynamic"]) and float(ids[id]["mass"]) > 0.0, id + " dynamic prop with mass")


func test_nature_imports_use_shared_wind_materials() -> void:
	for e: Variant in _load(NATURE):
		var d := e as Dictionary
		var ps := load(String(d["file"])) as PackedScene
		assert_not_null(ps, String(d["id"]))
		if ps == null:
			continue
		var inst := ps.instantiate()
		var shader_mats := 0
		var with_colors := 0
		var bad_surface := 0
		for n in inst.find_children("*", "", true, false):
			if n is MeshInstance3D:
				var mesh := (n as MeshInstance3D).mesh
				for s in mesh.get_surface_count():
					if mesh.surface_get_material(s) is ShaderMaterial:
						shader_mats += 1
						var arrays := mesh.surface_get_arrays(s)
						if arrays[Mesh.ARRAY_COLOR] != null and (arrays[Mesh.ARRAY_COLOR] as PackedColorArray).size() > 0:
							with_colors += 1
			elif n is StaticBody3D:
				var sb := n as StaticBody3D
				if not (sb.get_meta(&"surface", &"") in SURFACES):
					bad_surface += 1
				assert_true(sb.collision_layer & LAYER_WORLD, String(d["id"]) + " collider on world layer")
		assert_true(shader_mats > 0, String(d["id"]) + " uses the shared nature shader materials")
		assert_eq(with_colors, shader_mats, String(d["id"]) + " wind vertex colours on every plant surface")
		assert_eq(bad_surface, 0, String(d["id"]) + " collider surfaces")
		inst.free()


func test_vehicle_imports() -> void:
	var ids := _by_id(_load(VEHICLES))
	for id: String in ids:
		var d: Dictionary = ids[id]
		var ps := load(String(d["file"])) as PackedScene
		assert_not_null(ps, id)
		if ps == null:
			continue
		var inst := ps.instantiate() as Node3D
		var std_shared := 0
		var bodies := 0
		for n in inst.find_children("*", "", true, false):
			if n is MeshInstance3D:
				var mesh := (n as MeshInstance3D).mesh
				for s in mesh.get_surface_count():
					var m := mesh.surface_get_material(s)
					if m != null and m.resource_path.begins_with("res://assets/models/vehicles/materials/"):
						std_shared += 1
			elif n is StaticBody3D:
				bodies += 1
				var want := LAYER_PROPS if String(d["kind"]) == "helmet" else LAYER_VEHICLES
				assert_eq((n as StaticBody3D).collision_layer, want, id + " collider layer")
				assert_true((n as StaticBody3D).get_meta(&"surface", &"") in SURFACES, id + " collider surface")
		assert_true(std_shared > 0, id + " uses shared vehicle materials")
		assert_true(bodies > 0, id + " has colliders")
		for w: Variant in d["wheels"]:
			var wd := w as Dictionary
			var node := inst.find_child(String(wd["node"]), true, false) as Node3D
			assert_not_null(node, "%s wheel node %s" % [id, wd["node"]])
			if node != null:
				assert_near(node.position.y, float(wd["radius"]), 0.03, "%s %s hub at wheel radius" % [id, wd["node"]])
				var mi := node as MeshInstance3D
				if mi != null:
					var aabb := mi.get_aabb()
					assert_near(aabb.get_center().y, 0.0, 0.03, "%s %s origin is the hub" % [id, wd["node"]])
					assert_near(aabb.size.y * 0.5, float(wd["radius"]), 0.03, "%s %s radius" % [id, wd["node"]])
		if String(d["kind"]) != "helmet":
			assert_true(inst.find_children("SEAT_*", "", true, false).size() >= 1, id + " seat markers")
		if String(d["kind"]) in ["car", "van"]:
			# closed cabins: tinted glass + lamp materials (world-life raises lamp emission at night)
			var mats: Array[String] = []
			for n in inst.find_children("*", "MeshInstance3D", true, false):
				var mesh := (n as MeshInstance3D).mesh
				for s in mesh.get_surface_count():
					var m := mesh.surface_get_material(s)
					if m != null:
						mats.append(m.resource_path.get_file().get_basename())
			for want in ["veh_glass", "veh_light_head", "veh_light_tail"]:
				assert_true(want in mats, "%s uses %s" % [id, want])
		# every catalogued lamp became a hidden, switchable light (SpotLight3D head / OmniLight3D tail)
		for l: Variant in d.get("lights", []):
			var ld := l as Dictionary
			var mount := inst.find_child(String(ld["node"]), true, false) as Node3D
			assert_not_null(mount, "%s light mount %s" % [id, ld["node"]])
			if mount == null:
				continue
			var want_cls := "SpotLight3D" if String(ld["kind"]) == "head" else "OmniLight3D"
			var lights := mount.find_children("*", want_cls, false, false)
			assert_eq(lights.size(), 1, "%s %s has a %s" % [id, ld["node"], want_cls])
			if lights.size() == 1:
				var lt := lights[0] as Light3D
				assert_false(lt.visible, id + " lights start off")
				assert_true(lt.is_in_group(&"vehicle_light") and float(lt.get_meta(&"night_energy", 0.0)) > 0.0,
					id + " light group/meta")
				if lt is SpotLight3D:
					var fwd := (mount.transform.basis * lt.transform.basis) * Vector3(0.0, 0.0, -1.0)
					assert_true(fwd.z > 0.9, "%s head light aims along +Z (front): %s" % [id, fwd])
		if String(d["kind"]) in ["car", "van", "scooter", "motorbike"]:
			assert_true((d.get("lights", []) as Array).size() >= 2, id + " has head + tail lights")
		inst.free()


func _physics_check(cat_path: String, label: String) -> void:
	for e: Variant in _load(cat_path):
		var d := e as Dictionary
		if (d["nap_spots"] as Array).is_empty() and (d["climb_points"] as Array).is_empty():
			continue
		var ps := load(String(d["file"])) as PackedScene
		if ps == null:
			continue
		var inst := ps.instantiate() as Node3D
		tree.root.add_child(inst)
		await tree.physics_frame
		await tree.physics_frame
		var space := inst.get_world_3d().direct_space_state
		for p: Variant in d["nap_spots"]:
			var v := _vec(p)
			var q := PhysicsRayQueryParameters3D.create(v + Vector3(0, 0.3, 0), v - Vector3(0, 0.35, 0), 0xFFFFFFFF)
			var hit := space.intersect_ray(q)
			assert_false(hit.is_empty(), "%s %s nap spot %s unsupported" % [label, d["id"], v])
		for p: Variant in d["climb_points"]:
			var v := _vec(p)
			var sq := PhysicsShapeQueryParameters3D.new()
			var sph := SphereShape3D.new()
			sph.radius = 0.15
			sq.shape = sph
			sq.transform = Transform3D(Basis.IDENTITY, v)
			sq.collision_mask = LAYER_CLIMB
			assert_false(space.intersect_shape(sq, 4).is_empty(), "%s %s climb point %s not climbable" % [label, d["id"], v])
		inst.queue_free()
		await tree.process_frame


func test_nature_nap_and_climb_supported() -> void:
	await _physics_check(NATURE, "nature")


func test_vehicle_nap_spots_supported() -> void:
	await _physics_check(VEHICLES, "vehicle")


func test_showcase_scenes_load() -> void:
	for p in ["res://assets/models/nature/preview/nature_showcase.tscn",
			"res://assets/models/nature/preview/nature_garden.tscn",
			"res://assets/models/vehicles/preview/vehicles_showcase.tscn",
			"res://assets/models/vehicles/preview/vehicles_street.tscn"]:
		var ps := load(p) as PackedScene
		assert_not_null(ps, p)
		if ps == null:
			continue
		var inst := ps.instantiate()
		tree.root.add_child(inst)
		await tree.process_frame
		assert_true(inst.get_child_count() > 5, p + " populated")
		inst.queue_free()
		await tree.process_frame
