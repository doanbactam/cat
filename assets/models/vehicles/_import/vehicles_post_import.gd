@tool
extends EditorScenePostImport
## Post-import for every vehicles-nature vehicle / helmet (.glb in assets/models/vehicles/).
## Wired through each glb's .import file (import_script/path), written by blender/vehicles/build_vehicles.py.
##
## Materials: every glTF material named veh_* is replaced by the shared resource
##   res://assets/models/vehicles/materials/<name>.tres (ORMMaterial3D: tiling paint/metal/rubber sets,
##   clearcoat on veh_paint_*, vertex colour "vc" = baked AO + mud multiplied into albedo).
##   Lamp materials (veh_light_head/tail/amber) have emission enabled at energy 0; the MeshInstance3D
##   that uses them gets meta "vehicle_lights" = true so world-life can switch lights on at night.
## Colliders ("col_<surface>_<tag>-convcolonly"): exact boxes -> BoxShape3D, StaticBody3D on layer 8
##   "vehicles" (helmets: layer 4 props_dynamic), meta "surface".
## Nodes: wheel_* -> group "vehicle_wheel" (spin about local X); SEAT_* empties -> group "vehicle_seat"
##   (meta "seat_role"); NAP_* -> group "vehicle_nap_spot". Root: meta "vehicle" = true.

const LAYER_PROPS := 1 << 3
const LAYER_VEHICLES := 1 << 7
const MAT_DIR := "res://assets/models/vehicles/materials/"
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]


func _post_import(scene: Node) -> Object:
	var helmet := String(scene.name).to_lower().contains("helmet") or _has_helmet_mesh(scene)
	_walk(scene, {}, helmet)
	scene.set_meta(&"vehicle", not helmet)
	if helmet:
		scene.set_meta(&"dynamic", true)
		scene.set_meta(&"mass", 0.45)
	return scene


func _has_helmet_mesh(n: Node) -> bool:
	for c in n.get_children():
		if String(c.name).to_lower().contains("helmet"):
			return true
	return false


func _walk(n: Node, cache: Dictionary, helmet: bool) -> void:
	for c in n.get_children():
		_walk(c, cache, helmet)
	var nm := String(n.name)
	if n is MeshInstance3D:
		_fix_mesh(n as MeshInstance3D, cache)
		if nm.begins_with("wheel_"):
			n.add_to_group(&"vehicle_wheel", true)
	elif n is StaticBody3D:
		_fix_body(n as StaticBody3D, helmet)
	elif n is Node3D:
		if nm.begins_with("wheel_"):
			n.add_to_group(&"vehicle_wheel", true)
		elif nm.begins_with("SEAT_"):
			n.add_to_group(&"vehicle_seat", true)
			n.set_meta(&"seat_role", StringName(nm.substr(5)))
		elif nm.begins_with("NAP_"):
			n.add_to_group(&"vehicle_nap_spot", true)


func _fix_mesh(mi: MeshInstance3D, cache: Dictionary) -> void:
	var mesh := mi.mesh
	if mesh == null:
		return
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s)
		if m == null:
			continue
		var nm := m.resource_name
		if not nm.begins_with("veh_"):
			continue
		if not cache.has(nm):
			var path := MAT_DIR + nm + ".tres"
			cache[nm] = load(path) if ResourceLoader.exists(path) else null
		if cache[nm] != null:
			mesh.surface_set_material(s, cache[nm])
		if nm.begins_with("veh_light_"):
			mi.set_meta(&"vehicle_lights", true)


func _fix_body(body: StaticBody3D, helmet: bool) -> void:
	var parts := String(body.name).split("_")
	var surface := "metal"
	if parts.size() >= 2 and parts[0] == "col" and parts[1] in SURFACES:
		surface = parts[1]
	body.set_meta(&"surface", StringName(surface))
	body.collision_layer = LAYER_PROPS if helmet else LAYER_VEHICLES
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
