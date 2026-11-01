extends "res://tests/test_base.gd"
## city-houses: catalog contract + every module imports with simple box colliders that actually
## support the advertised nap spots / climb points (physics queries, not just counts).

const CATALOG := "res://assets/models/city/catalog.json"
const KINDS: Array[String] = ["house", "shop", "corner", "landmark", "alley", "roof_prop", "wall"]
const STYLES: Array[String] = ["colonial", "tube90s", "modern", "old_tile", "temple", "market"]
const SURFACES: Array[StringName] = [&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt",
	&"water", &"roof_tile", &"fabric", &"plastic"]
const LAYER_CLIMB := 1 << 5


func _catalog() -> Array:
	var f := FileAccess.open(CATALOG, FileAccess.READ)
	if f == null:
		return []
	var data: Variant = JSON.parse_string(f.get_as_text())
	return data if data is Array else []


func _vec(a: Variant) -> Vector3:
	var arr := a as Array
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))


func test_catalog_contract() -> void:
	var cat := _catalog()
	assert_true(cat.size() >= 40, "catalog has %d modules" % cat.size())
	var ids := {}
	var styles := {}
	var bases := {}
	for e: Variant in cat:
		var d := e as Dictionary
		for k in ["id", "file", "kind", "width", "depth", "height", "floors", "style", "climb_points",
				"nap_spots", "entrances"]:
			assert_true(d.has(k), "%s missing key %s" % [d.get("id", "?"), k])
		var id := String(d["id"])
		assert_false(ids.has(id), "duplicate id " + id)
		ids[id] = true
		assert_true(String(d["kind"]) in KINDS, id + " kind")
		assert_true(String(d["style"]) in STYLES, id + " style")
		assert_true(float(d["width"]) > 0.2 and float(d["height"]) > 0.0, id + " dims")
		assert_true(ResourceLoader.exists(String(d["file"])), id + " file " + String(d["file"]))
		for key in ["climb_points", "nap_spots", "entrances"]:
			for p: Variant in d[key]:
				assert_eq((p as Array).size(), 3, id + " point size")
		styles[String(d["style"])] = true
		if String(d["kind"]) in ["house", "shop", "corner"]:
			bases[String(d.get("variant_of", id))] = true
	assert_true(bases.size() >= 14, "distinct house/shop modules: %d" % bases.size())
	for s in ["colonial", "tube90s", "modern", "old_tile"]:
		assert_true(styles.has(s), "style present " + s)


func test_points_inside_module_bounds() -> void:
	for e: Variant in _catalog():
		var d := e as Dictionary
		var hw := float(d["width"]) * 0.5 + 1.5
		var h := float(d["height"]) + 4.5
		var depth := float(d["depth"]) + 1.0
		for key in ["climb_points", "nap_spots", "entrances"]:
			for p: Variant in d[key]:
				var v := _vec(p)
				var ok := absf(v.x) <= hw and v.y >= -0.5 and v.y <= h and v.z <= 2.5 and v.z >= -depth - 2.0
				assert_true(ok, "%s %s point %s outside bounds" % [d["id"], key, v])


func test_modules_have_box_colliders_and_surfaces() -> void:
	for e: Variant in _catalog():
		var d := e as Dictionary
		var ps := load(String(d["file"])) as PackedScene
		assert_not_null(ps, String(d["id"]))
		if ps == null:
			continue
		var inst := ps.instantiate()
		var bodies := 0
		var boxes := 0
		var bad_surface := 0
		var climbable := 0
		var vc_mats := 0
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
				var mesh := (n as MeshInstance3D).mesh
				for i in mesh.get_surface_count():
					var m := mesh.surface_get_material(i) as StandardMaterial3D
					if m and m.vertex_color_use_as_albedo:
						vc_mats += 1
		var id := String(d["id"])
		var min_bodies := 8 if String(d["kind"]) in ["house", "shop", "corner"] else 1
		assert_true(bodies >= min_bodies, "%s has %d collider bodies" % [id, bodies])
		assert_eq(boxes, bodies, id + ": every collider must be a single BoxShape3D")
		assert_eq(bad_surface, 0, id + ": colliders with unknown surface")
		assert_true(vc_mats > 0, id + ": vertex-colour materials")
		if (d["climb_points"] as Array).size() > 0:
			assert_true(climbable > 0, id + ": climb points but no climbable collider")
		inst.free()


func test_nap_spots_and_climb_points_are_supported() -> void:
	# Physics check per module: every nap spot has a collider just below it, every climb point
	# touches a climbable (layer 6) collider.
	for e: Variant in _catalog():
		var d := e as Dictionary
		var ps := load(String(d["file"])) as PackedScene
		if ps == null:
			continue
		var inst := ps.instantiate() as Node3D
		tree.root.add_child(inst)
		inst.global_position = Vector3(0, 0, 0)
		await tree.physics_frame
		await tree.physics_frame
		var space := inst.get_world_3d().direct_space_state
		var id := String(d["id"])
		for p: Variant in d["nap_spots"]:
			var v := _vec(p)
			var q := PhysicsRayQueryParameters3D.create(v + Vector3(0, 0.3, 0), v - Vector3(0, 0.35, 0), 1)
			var hit := space.intersect_ray(q)
			assert_false(hit.is_empty(), "%s nap spot %s has no support" % [id, v])
		for p: Variant in d["climb_points"]:
			var v := _vec(p)
			var sq := PhysicsShapeQueryParameters3D.new()
			var sph := SphereShape3D.new()
			sph.radius = 0.15
			sq.shape = sph
			sq.transform = Transform3D(Basis.IDENTITY, v)
			sq.collision_mask = LAYER_CLIMB
			var res := space.intersect_shape(sq, 4)
			assert_false(res.is_empty(), "%s climb point %s not on a climbable collider" % [id, v])
		inst.queue_free()
		await tree.process_frame


func test_street_row_preview_scene_loads() -> void:
	var ps := load("res://assets/models/city/preview/street_row.tscn") as PackedScene
	assert_not_null(ps, "street_row.tscn")
	if ps == null:
		return
	var inst := ps.instantiate()
	tree.root.add_child(inst)
	await tree.process_frame
	var modules := 0
	for c in inst.get_children():
		if c.has_meta(&"city_module"):
			modules += 1
	assert_true(modules >= 8, "street row instanced %d modules" % modules)
	inst.queue_free()
	await tree.process_frame
