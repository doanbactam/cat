extends "res://tests/test_base.gd"
## city-landmarks: catalog contract, every landmark imports with box colliders + valid surfaces,
## nap spots / climb points are physically supported, story markers exist (crow nest on the temple
## ridge, banyan, fish stall, Cam's bed + bowl at the tea stall), shelters become Area3D boxes,
## and the showcase scene loads.

const CATALOG := "res://assets/models/landmarks/catalog.json"
const KINDS: Array[String] = ["house", "shop", "corner", "landmark", "alley", "roof_prop", "wall"]
const SURFACES: Array[StringName] = [&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt",
	&"water", &"roof_tile", &"fabric", &"plastic"]
const LAYER_CLIMB := 1 << 5
const REQUIRED: Array[String] = ["dinh_hang_may", "cho_market_hall", "cho_stall_lane", "cho_gate_arch",
	"ho_embank_straight_4m", "ho_embank_curve_30", "ho_embank_steps_4m", "ho_railing_4m", "ho_bridge",
	"ho_islet_shrine", "ho_lamp_post", "ho_bench", "shrine_wall_box", "shrine_tree", "cafe_bong", "quan_tra_ba_tu"]


func _catalog() -> Array:
	var f := FileAccess.open(CATALOG, FileAccess.READ)
	if f == null:
		return []
	var data: Variant = JSON.parse_string(f.get_as_text())
	return data if data is Array else []


func _entry(id: String) -> Dictionary:
	for e: Variant in _catalog():
		if String((e as Dictionary)["id"]) == id:
			return e
	return {}


func _vec(a: Variant) -> Vector3:
	var arr := a as Array
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))


func _find_named(root: Node, prefix: String) -> Array[Node]:
	var out: Array[Node] = []
	for n in root.find_children(prefix + "*", "", true, false):
		out.append(n)
	return out


func test_catalog_contract() -> void:
	var cat := _catalog()
	assert_true(cat.size() >= REQUIRED.size(), "catalog has %d modules" % cat.size())
	var ids := {}
	for e: Variant in cat:
		var d := e as Dictionary
		for k in ["id", "file", "kind", "width", "depth", "height", "floors", "style", "climb_points",
				"nap_spots", "entrances", "markers"]:
			assert_true(d.has(k), "%s missing key %s" % [d.get("id", "?"), k])
		var id := String(d["id"])
		assert_false(ids.has(id), "duplicate id " + id)
		ids[id] = true
		assert_true(String(d["kind"]) in KINDS, id + " kind " + String(d["kind"]))
		assert_true(float(d["width"]) > 0.2 and float(d["height"]) > 0.0, id + " dims")
		assert_true(ResourceLoader.exists(String(d["file"])), id + " file " + String(d["file"]))
		for key in ["climb_points", "nap_spots", "entrances"]:
			for p: Variant in d[key]:
				assert_eq((p as Array).size(), 3, id + " point size")
	for id in REQUIRED:
		assert_true(ids.has(id), "required landmark " + id)
	# story markers advertised in the catalog
	assert_true((_entry("dinh_hang_may").get("markers", {}) as Dictionary).has("QUEST_crow_nest"), "crow nest marker")
	assert_true((_entry("dinh_hang_may").get("markers", {}) as Dictionary).has("MARKER_banyan"), "banyan marker")
	assert_true((_entry("cho_market_hall").get("markers", {}) as Dictionary).has("MARKER_fish_stall"), "fish stall")
	var tea := _entry("quan_tra_ba_tu").get("markers", {}) as Dictionary
	for m in ["MARKER_cam_bed", "MARKER_bowl", "MARKER_stall_counter", "MARKER_grandma"]:
		assert_true(tea.has(m), "tea stall marker " + m)
	assert_true((_entry("dinh_hang_may")["nap_spots"] as Array).size() >= 4, "temple nap spots")


func test_modules_import_with_box_colliders() -> void:
	for e: Variant in _catalog():
		var d := e as Dictionary
		var id := String(d["id"])
		var ps := load(String(d["file"])) as PackedScene
		assert_not_null(ps, id)
		if ps == null:
			continue
		var inst := ps.instantiate()
		assert_true(inst.has_meta(&"landmark_module"), id + " went through the landmark post-import")
		var bodies := 0
		var boxes := 0
		var bad_surface := 0
		var climbable := 0
		var vc_mats := 0
		var meshes := 0
		for n in inst.find_children("*", "", true, false):
			if n is StaticBody3D:
				bodies += 1
				var s: StringName = n.get_meta(&"surface", &"")
				if not (s in SURFACES):
					bad_surface += 1
				if (n as StaticBody3D).collision_layer & LAYER_CLIMB:
					climbable += 1
				for c in n.get_children():
					if c is CollisionShape3D and (c as CollisionShape3D).shape is BoxShape3D:
						boxes += 1
			elif n is MeshInstance3D:
				meshes += 1
				var mesh := (n as MeshInstance3D).mesh
				for i in mesh.get_surface_count():
					var m := mesh.surface_get_material(i) as StandardMaterial3D
					if m and m.vertex_color_use_as_albedo:
						vc_mats += 1
					if m:
						assert_true(m.albedo_texture != null or m.resource_name.begins_with("lit_")
							or m.resource_name.begins_with("dec_") or m.resource_name.begins_with("arch_")
							or m.resource_name.begins_with("lm_"), id + " material " + m.resource_name)
		assert_true(meshes >= 1, id + " has meshes")
		assert_true(bodies >= 1, "%s has %d collider bodies" % [id, bodies])
		assert_eq(boxes, bodies, id + ": every collider must be a single BoxShape3D")
		assert_eq(bad_surface, 0, id + ": colliders with unknown surface")
		assert_true(vc_mats > 0, id + ": vertex-colour materials")
		if (d["climb_points"] as Array).size() > 0:
			assert_true(climbable > 0, id + ": climb points but no climbable collider")
		inst.free()


func test_points_are_physically_supported() -> void:
	for e: Variant in _catalog():
		var d := e as Dictionary
		var ps := load(String(d["file"])) as PackedScene
		if ps == null:
			continue
		var inst := ps.instantiate() as Node3D
		tree.root.add_child(inst)
		await tree.physics_frame
		await tree.physics_frame
		var space := inst.get_world_3d().direct_space_state
		var id := String(d["id"])
		for p: Variant in d["nap_spots"]:
			var v := _vec(p)
			var q := PhysicsRayQueryParameters3D.create(v + Vector3(0, 0.3, 0), v - Vector3(0, 0.35, 0), 1)
			assert_false(space.intersect_ray(q).is_empty(), "%s nap spot %s has no support" % [id, v])
		for p: Variant in d["climb_points"]:
			var v := _vec(p)
			var sq := PhysicsShapeQueryParameters3D.new()
			var sph := SphereShape3D.new()
			sph.radius = 0.15
			sq.shape = sph
			sq.transform = Transform3D(Basis.IDENTITY, v)
			sq.collision_mask = LAYER_CLIMB
			assert_false(space.intersect_shape(sq, 4).is_empty(), "%s climb point %s not climbable" % [id, v])
		inst.queue_free()
		await tree.process_frame


func test_temple_nest_on_walkable_ridge() -> void:
	var ps := load("res://assets/models/landmarks/dinh_hang_may.glb") as PackedScene
	assert_not_null(ps)
	if ps == null:
		return
	var inst := ps.instantiate() as Node3D
	tree.root.add_child(inst)
	await tree.physics_frame
	await tree.physics_frame
	var nest: Node3D = null
	for n in inst.find_children("QUEST_crow_nest", "", true, false):
		nest = n as Node3D
	assert_not_null(nest, "QUEST_crow_nest node")
	if nest != null:
		assert_true(nest.is_in_group(&"quest_target"), "nest in group quest_target")
		assert_eq(String(nest.get_meta(&"target_id", "")), "crow_nest")
		assert_true(nest.global_position.y > 8.0, "nest is up on the roof ridge (y=%.2f)" % nest.global_position.y)
		var space := inst.get_world_3d().direct_space_state
		var p := nest.global_position
		var q := PhysicsRayQueryParameters3D.create(p + Vector3(0, 0.4, 0), p - Vector3(0, 0.6, 0), 1)
		assert_false(space.intersect_ray(q).is_empty(), "nest sits on a collider")
		# the ridge beside the nest is walkable too
		var q2 := PhysicsRayQueryParameters3D.create(p + Vector3(-1.5, 0.6, 0), p + Vector3(-1.5, -1.2, 0), 1)
		assert_false(space.intersect_ray(q2).is_empty(), "ridge walkable next to the nest")
	var shelters := 0
	var reverbs := 0
	for a in inst.find_children("*", "Area3D", true, false):
		if a.is_in_group(&"shelter"):
			shelters += 1
			var cs := a.get_child(0) as CollisionShape3D
			assert_true(cs != null and cs.shape is BoxShape3D, "shelter has a box shape")
		if (a as Area3D).reverb_bus_enabled:
			reverbs += 1
			assert_eq(String((a as Area3D).reverb_bus_name), "Temple")
	assert_true(shelters >= 2, "temple shelters: %d" % shelters)
	assert_eq(reverbs, 1, "temple reverb zone")
	var lights := inst.find_children("*", "OmniLight3D", true, false)
	assert_true(lights.size() >= 1, "altar light")
	inst.queue_free()
	await tree.process_frame


func test_lake_pieces_tile_and_bridge_is_walkable() -> void:
	var st := _entry("ho_embank_straight_4m")
	assert_near(float(st.get("width", 0.0)), 4.0, 0.001, "straight piece is 4 m")
	var ps := load("res://assets/models/landmarks/ho_bridge.glb") as PackedScene
	assert_not_null(ps)
	if ps == null:
		return
	var inst := ps.instantiate() as Node3D
	tree.root.add_child(inst)
	await tree.physics_frame
	await tree.physics_frame
	var space := inst.get_world_3d().direct_space_state
	# walk the deck from end to end: always a collider within 0.3 m below the arch line
	for i in 9:
		var z := -7.6 + i * 1.9
		var q := PhysicsRayQueryParameters3D.create(Vector3(0, 3.0, z), Vector3(0, -0.5, z), 1)
		var hit := space.intersect_ray(q)
		assert_false(hit.is_empty(), "bridge deck at z=%.1f" % z)
		if not hit.is_empty():
			assert_true(hit["collider"].get_meta(&"surface", &"") == &"wood", "deck surface wood")
	inst.queue_free()
	await tree.process_frame


func test_textures_are_shared_not_embedded() -> void:
	# GLBs reference assets/textures/{landmarks,architecture} by URI -> imported materials use those files
	var ps := load("res://assets/models/landmarks/quan_tra_ba_tu.glb") as PackedScene
	if ps == null:
		assert_true(false, "tea stall glb")
		return
	var inst := ps.instantiate()
	var shared := 0
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		var mesh := (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			var m := mesh.surface_get_material(i) as StandardMaterial3D
			if m and m.albedo_texture and m.albedo_texture.resource_path.begins_with("res://assets/textures/"):
				shared += 1
	assert_true(shared >= 5, "tea stall materials using shared textures: %d" % shared)
	inst.free()


func test_showcase_scene_loads() -> void:
	var ps := load("res://assets/models/landmarks/preview/landmarks_showcase.tscn") as PackedScene
	assert_not_null(ps, "landmarks_showcase.tscn")
	if ps == null:
		return
	var inst := ps.instantiate()
	tree.root.add_child(inst)
	await tree.process_frame
	var n := 0
	for c in inst.get_children():
		if c.has_meta(&"landmark_id"):
			n += 1
	assert_true(n >= 16, "showcase placed %d landmarks" % n)
	inst.queue_free()
	await tree.process_frame
