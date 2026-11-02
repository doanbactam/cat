extends SceneTree
## Builds and saves res://scenes/world/city.tscn (owner: world).
## Run:  tools/godot_lock.sh godot --headless --path . --script res://scripts/world/tools/build_city.gd </dev/null
## Options (after --): no_nav (skip navmesh bake), no_post (skip rooftop/cable pass)
##
## Steps: knockable prop scenes → CityBuilder.build() → add to tree, step physics →
## CityBuilderPost (rooftop measurement, connectors, cables, patrol) → NavRegion bake →
## generated meshes/shapes saved as binary .res under scenes/world/generated/ → pack + save.
## Writes qa/out/world/build_report.json.

const OUT := "res://scenes/world/city.tscn"
const GEN_DIR := "res://scenes/world/generated"

var _owned: Dictionary = {}


func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	await process_frame
	var args := OS.get_cmdline_user_args()
	var t0 := Time.get_ticks_msec()
	var kf: Variant = load("res://scripts/world/knockable_factory.gd")
	print("BUILD knockables: ", kf.call(&"build_all"))
	var builder: Object = load("res://scripts/world/city_builder.gd").new()
	var city: Node3D = builder.call(&"build")
	print("BUILD stage1 done in %d ms" % (Time.get_ticks_msec() - t0))
	_own(city, city)
	root.add_child(city)
	for i in 3:
		await physics_frame
	var post_report: Dictionary = {}
	if not "no_post" in args:
		var snapshot := _snapshot(city)
		var post: Object = load("res://scripts/world/city_builder_post.gd").new(builder, city.get_world_3d().direct_space_state)
		post_report = post.call(&"run")
		_own_new(city, snapshot)
		print("BUILD post done in %d ms: %s" % [Time.get_ticks_msec() - t0, post_report])
	if not "no_nav" in args:
		var region: NavigationRegion3D = load("res://scripts/world/city_builder_post.gd").call(&"bake_nav", city)
		city.add_child(region)
		region.owner = city
		var nm := region.navigation_mesh
		ResourceSaver.save(nm, "res://scenes/world/city_navmesh.res", ResourceSaver.FLAG_CHANGE_PATH | ResourceSaver.FLAG_COMPRESS)
		post_report["nav_polygons"] = nm.get_polygon_count()
		print("BUILD nav baked: %d polygons (%d ms)" % [nm.get_polygon_count(), Time.get_ticks_msec() - t0])
	_save_generated(city)
	var ps := PackedScene.new()
	var err := ps.pack(city)
	if err != OK:
		printerr("BUILD pack failed: ", err)
		quit(1)
		return
	err = ResourceSaver.save(ps, OUT)
	if err != OK:
		printerr("BUILD save failed: ", err)
		quit(1)
		return
	var rep: Dictionary = builder.get(&"report")
	rep["post"] = post_report
	rep["build_ms"] = Time.get_ticks_msec() - t0
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://qa/out/world"))
	var f := FileAccess.open("res://qa/out/world/build_report.json", FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(rep, "  "))
	print("BUILD saved ", OUT, " in ", rep["build_ms"], " ms")
	print("BUILD report: ", JSON.stringify(rep))
	city.queue_free()
	await process_frame
	quit(0)


## Own every node of the generated tree, but never descend into instanced scenes.
func _own(n: Node, owner_root: Node) -> void:
	for c in n.get_children():
		c.owner = owner_root
		_owned[c] = true
		if c.scene_file_path == "":
			_own(c, owner_root)


func _snapshot(city: Node) -> Dictionary:
	return _owned.duplicate()


## After the post pass: own only the nodes the builder added (children of build groups), not the
## runtime nodes created by scripts' _ready (rain particles, interact areas …).
func _own_new(city: Node3D, before: Dictionary) -> void:
	for gname in ["Connectors", "Cables", "Markers"]:
		var g := city.get_node_or_null(gname)
		if g == null:
			continue
		for c in g.get_children():
			if before.has(c):
				continue
			c.owner = city
			_owned[c] = true
			if c.scene_file_path == "":
				_own_subtree(c, city)


func _own_subtree(n: Node, owner_root: Node) -> void:
	for c in n.get_children():
		c.owner = owner_root
		_owned[c] = true
		if c.scene_file_path == "":
			_own_subtree(c, owner_root)


func _save_generated(city: Node3D) -> void:
	var abs_dir := ProjectSettings.globalize_path(GEN_DIR)
	DirAccess.make_dir_recursive_absolute(abs_dir)
	var d := DirAccess.open(abs_dir)
	if d != null:
		for f in d.get_files():
			if f.ends_with(".res"):
				d.remove(f)
	var idx := 0
	var saved: Dictionary = {}
	for n: Node in _owned:
		if not is_instance_valid(n) or n.owner != city:
			continue
		var res: Resource = null
		if n is MeshInstance3D:
			res = (n as MeshInstance3D).mesh
		elif n is MultiMeshInstance3D:
			res = (n as MultiMeshInstance3D).multimesh
		elif n is CollisionShape3D and (n as CollisionShape3D).shape is ConcavePolygonShape3D:
			res = (n as CollisionShape3D).shape
		if res == null or res.resource_path != "" or saved.has(res):
			continue
		var path := "%s/%s_%04d.res" % [GEN_DIR, n.name.to_snake_case().left(24), idx]
		var err := ResourceSaver.save(res, path, ResourceSaver.FLAG_CHANGE_PATH | ResourceSaver.FLAG_COMPRESS)
		if err == OK:
			saved[res] = true
			idx += 1
	print("BUILD saved %d generated resources" % idx)
