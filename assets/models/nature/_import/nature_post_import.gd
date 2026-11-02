@tool
extends EditorScenePostImport
## Post-import for every vehicles-nature plant (.glb in assets/models/nature/).
## Wired through each glb's .import file (import_script/path), written by blender/nature/build_*.py.
##
## Materials (glTF material name -> shared resource, textures live in assets/textures/nature/):
##   nfol_<atlas>  -> res://assets/models/nature/materials/fol_<atlas>.tres (alpha-scissor foliage shader
##                    with wind from vertex colour + translucency + wetness)
##   nbark_<tex>   -> res://assets/models/nature/materials/<tex>.tres (bark shader with wind + wetness + moss)
##   nmat_*        -> kept (plain StandardMaterial3D from the glTF), vertex colour NOT used as albedo
##                    (COLOR_0 carries wind data).
## Colliders ("col_<surface>[_climb]_<n>-convcolonly"): StaticBody3D, layer 1 world [+ 6 climbable],
##   meta "surface", group "climbable" when climbable. Exact boxes become BoxShape3D.
## Markers (empties): NAP_*, CLIMB_* -> groups nature_nap_spot / nature_climb_point.
## Root gets meta "nature_asset" = true. Small plants (root meta via node name prefix "small_")
##   get a visibility range so ground cover fades out with distance.

const LAYER_WORLD := 1
const LAYER_CLIMB := 1 << 5
const MAT_DIR := "res://assets/models/nature/materials/"
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]


func _post_import(scene: Node) -> Object:
	var cache := {}
	_walk(scene, cache, scene)
	scene.set_meta(&"nature_asset", true)
	return scene


func _walk(n: Node, cache: Dictionary, root: Node) -> void:
	for c in n.get_children():
		_walk(c, cache, root)
	if n is MeshInstance3D:
		_fix_mesh(n as MeshInstance3D, cache)
	elif n is StaticBody3D:
		_fix_body(n as StaticBody3D)
	elif n.get_class() == "Node3D":
		var nm := String(n.name)
		if nm.begins_with("NAP_"):
			n.add_to_group(&"nature_nap_spot", true)
		elif nm.begins_with("CLIMB_"):
			n.add_to_group(&"nature_climb_point", true)


func _shared(name: String, cache: Dictionary) -> Material:
	if cache.has(name):
		return cache[name]
	var path := ""
	if name.begins_with("nfol_"):
		path = MAT_DIR + "fol_" + name.substr(5) + ".tres"
	elif name.begins_with("nbark_"):
		path = MAT_DIR + name.substr(6) + ".tres"
	var m: Material = null
	if path != "" and ResourceLoader.exists(path):
		m = load(path) as Material
	cache[name] = m
	return m


func _fix_mesh(mi: MeshInstance3D, cache: Dictionary) -> void:
	var mesh := mi.mesh
	if mesh == null:
		return
	var foliage := false
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s)
		if m == null:
			continue
		var nm := m.resource_name
		var shared := _shared(nm, cache)
		if shared != null:
			mesh.surface_set_material(s, shared)
			if nm.begins_with("nfol_"):
				foliage = true
		elif m is StandardMaterial3D:
			var sm := m as StandardMaterial3D
			sm.vertex_color_use_as_albedo = false
			sm.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var lname := String(mi.name).to_lower()
	if lname.begins_with("small_") or lname.contains("_small"):
		mi.visibility_range_end = 45.0
		mi.visibility_range_end_margin = 8.0
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if not lname.contains("litter") \
				else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if foliage:
		mi.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC


func _fix_body(body: StaticBody3D) -> void:
	var parts := String(body.name).split("_")
	var surface := "wood"
	if parts.size() >= 2 and parts[0] == "col" and parts[1] in SURFACES:
		surface = parts[1]
	body.set_meta(&"surface", StringName(surface))
	var layer := LAYER_WORLD
	if "climb" in parts:
		layer |= LAYER_CLIMB
		body.add_to_group(&"climbable", true)
	body.collision_layer = layer
	body.collision_mask = 0
	for c in body.get_children():
		var cs := c as CollisionShape3D
		if cs == null:
			continue
		var cvx := cs.shape as ConvexPolygonShape3D
		if cvx == null or cvx.points.size() != 8:
			continue
		var pts := cvx.points
		var aabb := AABB(pts[0], Vector3.ZERO)
		for p in pts:
			aabb = aabb.expand(p)
		var box := true
		for p in pts:
			var ox := absf(p.x - aabb.position.x) < 0.002 or absf(p.x - aabb.end.x) < 0.002
			var oy := absf(p.y - aabb.position.y) < 0.002 or absf(p.y - aabb.end.y) < 0.002
			var oz := absf(p.z - aabb.position.z) < 0.002 or absf(p.z - aabb.end.z) < 0.002
			if not (ox and oy and oz):
				box = false
				break
		if box:
			var bx := BoxShape3D.new()
			bx.size = aabb.size
			cs.shape = bx
			cs.position += aabb.get_center()
