extends "res://tests/test_base.gd"
## street-props: catalog integrity (contract fields, files, textures, budgets), every items.json mesh
## exists, dynamic props import as Pushable RigidBody3D with mass, static props carry colliders with a
## valid surface, lit props have NightLight wiring.

const CATALOG := "res://assets/models/props/catalog.json"
const ITEMS := "res://data/items/items.json"
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]
const MATERIAL_KINDS: Array[String] = ["ceramic", "metal", "plastic", "wood", "glass", "cardboard", "soft"]


func _catalog() -> Array:
	var f := FileAccess.open(CATALOG, FileAccess.READ)
	if f == null:
		return []
	var data: Variant = JSON.parse_string(f.get_as_text())
	return data if data is Array else []


func _find_all(n: Node, cls: String, out: Array[Node]) -> void:
	if n.is_class(cls):
		out.append(n)
	for c in n.get_children():
		_find_all(c, cls, out)


func test_catalog_contract() -> void:
	var cat := _catalog()
	assert_true(cat.size() >= 45, "catalog has %d props (need >= 45)" % cat.size())
	var ids := {}
	var cats := {}
	for e: Variant in cat:
		var d := e as Dictionary
		for k in ["id", "file", "kind", "category", "footprint", "height", "dynamic", "mass", "surface",
				"material_kind", "name_key", "tris", "textures", "texture_size", "texel_density"]:
			assert_true(d.has(k), "%s missing key %s" % [d.get("id", "?"), k])
		var id := String(d["id"])
		assert_false(ids.has(id), "duplicate id " + id)
		ids[id] = true
		cats[String(d["category"])] = true
		assert_true(String(d["file"]) == "res://assets/models/props/%s.glb" % id, id + " file path")
		assert_true(FileAccess.file_exists(String(d["file"])), id + " glb exists")
		assert_true(String(d["surface"]) in SURFACES, id + " surface " + String(d["surface"]))
		assert_true(String(d["material_kind"]) in MATERIAL_KINDS, id + " material_kind " + String(d["material_kind"]))
		var fp := d["footprint"] as Array
		assert_eq(fp.size(), 2, id + " footprint")
		assert_true(float(fp[0]) > 0.0 and float(fp[1]) > 0.0 and float(d["height"]) > 0.0, id + " dims > 0")
		assert_true(float(d["height"]) < 6.0 and float(fp[0]) < 4.0, id + " dims plausible")
		assert_true(int(d["tris"]) > 12 and int(d["tris"]) < 120000, id + " tris %d" % int(d["tris"]))
		var ts := int(d["texture_size"])
		assert_true(ts >= 256 and ts <= 2048 and (ts & (ts - 1)) == 0, id + " texture size pow2 <= 2048")
		for t: Variant in d["textures"]:
			assert_true(FileAccess.file_exists(String(t)), id + " texture " + String(t))
		if bool(d["dynamic"]):
			assert_true(float(d["mass"]) > 0.0 and float(d["mass"]) < 40.0, id + " dynamic mass")
	for c in ["street", "utility", "sign", "container", "stall", "furniture", "home", "plant", "festival",
			"clutter", "item"]:
		assert_true(cats.has(c), "category present: " + c)


func test_required_props_present() -> void:
	var ids := {}
	for e: Variant in _catalog():
		ids[String((e as Dictionary)["id"])] = e
	for id in ["lamp_post_colonial", "lamp_post_modern", "electric_pole_concrete", "trash_bin_municipal",
			"cardboard_box_open", "plastic_crate_blue", "food_cart_xoi", "banh_mi_cart", "stool_plastic_red",
			"stool_plastic_blue", "stool_plastic_green", "star_lantern_red", "silk_lantern_round", "carp_lantern",
			"lantern_string", "pot_snake_plant", "cup_ceramic", "book_stack", "fire_hydrant", "traffic_cone"]:
		assert_true(ids.has(id), "required prop " + id)
	# lamp posts expose their light emitter position
	for id in ["lamp_post_colonial", "lamp_post_modern"]:
		if ids.has(id):
			var d := ids[id] as Dictionary
			assert_true(d.has("light_pos") and (d["light_pos"] as Array).size() == 3, id + " light_pos")
			assert_true(float((d["light_pos"] as Array)[1]) > 2.5, id + " light high up")
	# the open box is a nap spot
	if ids.has("cardboard_box_open"):
		assert_true(((ids["cardboard_box_open"] as Dictionary)["nap_spots"] as Array).size() > 0, "box nap spot")


func test_every_item_has_a_mesh() -> void:
	var f := FileAccess.open(ITEMS, FileAccess.READ)
	assert_not_null(f, "items.json")
	if f == null:
		return
	var items: Dictionary = JSON.parse_string(f.get_as_text())
	for id: Variant in items:
		var mesh := String((items[id] as Dictionary).get("mesh", ""))
		if mesh.is_empty():
			continue
		assert_true(ResourceLoader.exists(mesh), "item %s mesh %s" % [id, mesh])


func test_dynamic_props_import_as_pushable() -> void:
	var n_dyn := 0
	for e: Variant in _catalog():
		var d := e as Dictionary
		var ps := load(String(d["file"])) as PackedScene
		assert_not_null(ps, String(d["id"]) + " loads")
		if ps == null:
			continue
		var root := ps.instantiate()
		var id := String(d["id"])
		assert_eq(String(root.get_meta(&"prop_id", "")), id, id + " prop_id meta")
		var meshes: Array[Node] = []
		_find_all(root, "MeshInstance3D", meshes)
		assert_true(meshes.size() > 0, id + " has meshes")
		if bool(d["dynamic"]):
			n_dyn += 1
			assert_true(root is RigidBody3D, id + " dynamic root is RigidBody3D")
			if root is RigidBody3D:
				assert_near((root as RigidBody3D).mass, maxf(float(d["mass"]), 0.01), 0.01, id + " mass")
				assert_true(root.is_in_group(&"knockable") or root.get_script() != null, id + " pushable script")
			var shapes: Array[Node] = []
			_find_all(root, "CollisionShape3D", shapes)
			assert_true(shapes.size() > 0, id + " dynamic collider")
		elif int(d.get("colliders", 0)) > 0:
			var bodies: Array[Node] = []
			_find_all(root, "StaticBody3D", bodies)
			assert_true(bodies.size() > 0, id + " static colliders")
			for b in bodies:
				assert_true(String(b.get_meta(&"surface", "")) in SURFACES, id + " collider surface")
		if bool(d.get("emissive", false)) or d.has("lights"):
			assert_not_null(root.get_node_or_null("NightLight"), id + " NightLight controller")
		root.free()
	assert_true(n_dyn >= 10, "knockable props: %d" % n_dyn)
