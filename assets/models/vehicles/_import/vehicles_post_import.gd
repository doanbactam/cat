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
## Lights: LIGHT_head_<i> / LIGHT_tail_<i> empties (lamp lens centres) get a child light, hidden and at
##   energy 0 until a night/traffic system switches it on: SpotLight3D "HeadLight" aimed along +Z (model
##   front) and slightly down, OmniLight3D "TailLight" (red, short range). Lights are in group
##   "vehicle_light" with meta "night_energy" (energy to use when on) and "light_kind" (head|tail).

const LAYER_PROPS := 1 << 3
const LAYER_VEHICLES := 1 << 7
const MAT_DIR := "res://assets/models/vehicles/materials/"
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]


func _post_import(scene: Node) -> Object:
	var helmet := String(scene.name).to_lower().contains("helmet") or _has_helmet_mesh(scene)
	_walk(scene, {}, helmet, scene)
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


func _walk(n: Node, cache: Dictionary, helmet: bool, root: Node) -> void:
	for c in n.get_children():
		_walk(c, cache, helmet, root)
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
		elif nm.begins_with("LIGHT_"):
			_add_light(n as Node3D, nm, root)


func _add_light(at: Node3D, nm: String, root: Node) -> void:
	var kind := nm.split("_")[1] if nm.split("_").size() > 1 else "head"
	var l: Light3D
	if kind == "head":
		var sp := SpotLight3D.new()
		sp.name = "HeadLight"
		sp.spot_range = 22.0
		sp.spot_angle = 32.0
		sp.spot_attenuation = 1.2
		sp.light_color = Color(1.0, 0.94, 0.82)
		sp.set_meta(&"night_energy", 6.0)
		# SpotLight3D shines along its local -Z: aim it along the model front (+Z), 7 degrees down
		sp.transform = Transform3D(Basis.looking_at(Vector3(0.0, -0.12, 1.0)), Vector3(0.0, 0.0, 0.03))
		l = sp
	else:
		var om := OmniLight3D.new()
		om.name = "TailLight"
		om.omni_range = 2.2
		om.light_color = Color(1.0, 0.08, 0.05)
		om.set_meta(&"night_energy", 1.2)
		om.position = Vector3(0.0, 0.0, -0.05)
		l = om
	l.light_energy = 0.0
	l.visible = false
	l.shadow_enabled = false
	l.distance_fade_enabled = true
	l.distance_fade_begin = 40.0
	l.distance_fade_length = 10.0
	l.set_meta(&"light_kind", StringName(kind))
	l.add_to_group(&"vehicle_light", true)
	at.add_child(l)
	l.owner = root
	at.add_to_group(&"vehicle_light_mount", true)


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
