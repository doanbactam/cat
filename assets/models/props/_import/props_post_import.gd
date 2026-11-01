@tool
extends EditorScenePostImport
## Post-import for every street-props GLB (assets/models/props/*.glb), wired through each GLB's
## .import file (written by blender/props/build_props.py). Reads the prop's entry from
## assets/models/props/catalog.json (by file name) and turns the raw glTF scene into a game-ready prop.
##
## Materials (glTF names written by blender/lib/props_bake.py):
##   <id>         opaque baked PBR (albedo / ORM / normal); AO comes from the ORM red channel.
##   <id>__2s     same textures, double sided (leaves, cloth, paper, film).
##   <id>__lit    same textures + emission from albedo; emission_energy_multiplier = 0 by day,
##                material meta "night_emission_energy"; MeshInstance3D meta "night_emissive" = true
##                (same convention as the city kit, so `world` can drive both kits).
##   glass_*      alpha-blended glass (no textures).
## Colliders: Blender "col_<surface>[_climb]_NN-convcolonly" -> StaticBody3D with an exact BoxShape3D
##   when the hull is a box; layer 1 (world) [+6 climbable], meta "surface".
## Dynamic props (catalog "dynamic": true): the root becomes a RigidBody3D running
##   res://scripts/systems/pushable.gd (knockable; layer 4 set by the script), with the collider
##   shapes as direct children, meta "mass"/"name_key", Pushable.material_kind from the catalog.
## Markers (empties): NAP_*, SIT_*, CLIMB_*, ATTACH_*/HANG_* -> groups prop_nap_spot, prop_sit_spot,
##   prop_climb_point, prop_attach_point. LIGHT_* -> OmniLight3D / SpotLight3D (group
##   "prop_night_light", energy 0 by day, meta "night_light_energy").
## Props with lights or lit materials get a "NightLight" child (assets/models/props/_runtime/
##   prop_night_light.gd) that fades them in at dusk from TimeOfDay (disable with `enabled = false`).

const CATALOG := "res://assets/models/props/catalog.json"
const PUSHABLE := "res://scripts/systems/pushable.gd"
const NIGHT_LIGHT := "res://assets/models/props/_runtime/prop_night_light.gd"
const LAYER_WORLD := 1
const LAYER_CLIMB := 1 << 5
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]

var _entry: Dictionary = {}
var _has_night := false


func _post_import(scene: Node) -> Object:
	var id := get_source_file().get_file().get_basename()
	_entry = _catalog_entry(id)
	_has_night = false
	var mats_done := {}
	_walk(scene, mats_done)
	var root: Node3D = scene as Node3D
	if bool(_entry.get("dynamic", false)):
		root = _make_dynamic(scene as Node3D)
	root.set_meta(&"prop_id", StringName(id))
	root.set_meta(&"prop_category", StringName(String(_entry.get("category", ""))))
	root.set_meta(&"surface", StringName(String(_entry.get("surface", "concrete"))))
	root.set_meta(&"name_key", String(_entry.get("name_key", "PROP_OBJECT")))
	if _entry.has("item_id"):
		root.set_meta(&"item_id", StringName(String(_entry["item_id"])))
	if _entry.has("mass"):
		root.set_meta(&"mass", float(_entry["mass"]))
	root.add_to_group(&"street_prop", true)
	if _has_night and ResourceLoader.exists(NIGHT_LIGHT):
		var ctl := Node.new()
		ctl.name = "NightLight"
		ctl.set_script(load(NIGHT_LIGHT))
		root.add_child(ctl)
		ctl.owner = root
	return root


func _catalog_entry(id: String) -> Dictionary:
	if not FileAccess.file_exists(CATALOG):
		return {}
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	if data is Array:
		for e: Variant in data:
			if e is Dictionary and String(e.get("id", "")) == id:
				return e
	return {}


func _walk(n: Node, mats_done: Dictionary) -> void:
	for c in n.get_children():
		_walk(c, mats_done)
	if n is MeshInstance3D:
		_fix_mesh(n as MeshInstance3D, mats_done)
	elif n is StaticBody3D:
		_fix_body(n as StaticBody3D)
	elif n.get_class() == "Node3D":
		var nm := String(n.name)
		if nm.begins_with("NAP"):
			n.add_to_group(&"prop_nap_spot", true)
		elif nm.begins_with("SIT"):
			n.add_to_group(&"prop_sit_spot", true)
		elif nm.begins_with("CLIMB"):
			n.add_to_group(&"prop_climb_point", true)
		elif nm.begins_with("ATTACH") or nm.begins_with("HANG"):
			n.add_to_group(&"prop_attach_point", true)
		elif nm.begins_with("LIGHT"):
			_add_light(n as Node3D)


func _fix_mesh(mi: MeshInstance3D, mats_done: Dictionary) -> void:
	var mesh := mi.mesh
	if mesh == null:
		return
	var lit := false
	var night_e := float(_entry.get("night_emission", 2.5))
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s) as StandardMaterial3D
		if m == null:
			continue
		var nm := m.resource_name
		if nm.ends_with("__lit"):
			lit = true
		if mats_done.has(m):
			continue
		mats_done[m] = true
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		if nm.begins_with("glass_"):
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.cull_mode = BaseMaterial3D.CULL_BACK
			m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY
			m.metallic = 0.0
			m.metallic_specular = 0.75
			m.roughness = clampf(m.roughness, 0.02, 0.2)
			if m.albedo_color.a > 0.6:
				m.albedo_color.a = 0.25
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			continue
		if m.roughness_texture != null:
			m.ao_enabled = true
			m.ao_texture = m.roughness_texture
			m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
			m.ao_light_affect = 0.0
		m.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
		if nm.ends_with("__2s") or nm.ends_with("__lit"):
			m.cull_mode = BaseMaterial3D.CULL_DISABLED
		if nm.ends_with("__2s"):
			m.backlight_enabled = true
			m.backlight = Color(0.18, 0.2, 0.12)
		if nm.ends_with("__lit"):
			# lantern film / silk / diffusers: some light passes through by day, glow at night
			m.backlight_enabled = true
			m.backlight = Color(0.35, 0.3, 0.25)
			m.emission_enabled = true
			m.emission = Color(1, 1, 1)
			if m.albedo_texture != null:
				m.emission_texture = m.albedo_texture
			m.emission_energy_multiplier = 0.0
			m.set_meta(&"night_emission_energy", night_e)
			_has_night = true
	if lit:
		mi.set_meta(&"night_emissive", true)
	var vr := float(_entry.get("visibility_range", 0.0))
	if vr <= 0.0:
		var h := float(_entry.get("height", 0.5))
		vr = clampf(30.0 + h * 40.0, 25.0, 200.0)
	mi.visibility_range_end = vr
	mi.visibility_range_end_margin = vr * 0.1
	mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF


func _fix_body(body: StaticBody3D) -> void:
	var parts := String(body.name).split("_")
	var surface := String(_entry.get("surface", "concrete"))
	if parts.size() >= 2 and parts[0] == "col":
		var s := parts[1]
		if s == "roof" and parts.size() >= 3 and parts[2] == "tile":
			s = "roof_tile"
		if s in SURFACES:
			surface = s
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
		if cvx == null or cvx.points.is_empty():
			continue
		var pts := cvx.points
		var aabb := AABB(pts[0], Vector3.ZERO)
		for p in pts:
			aabb = aabb.expand(p)
		if pts.size() == 8 and _is_box(pts, aabb):
			var bx := BoxShape3D.new()
			bx.size = aabb.size
			cs.shape = bx
			cs.position += cs.basis * aabb.get_center()


func _is_box(pts: PackedVector3Array, aabb: AABB) -> bool:
	var eps := 0.002
	for p in pts:
		var on_x := absf(p.x - aabb.position.x) < eps or absf(p.x - aabb.end.x) < eps
		var on_y := absf(p.y - aabb.position.y) < eps or absf(p.y - aabb.end.y) < eps
		var on_z := absf(p.z - aabb.position.z) < eps or absf(p.z - aabb.end.z) < eps
		if not (on_x and on_y and on_z):
			return false
	return true


func _add_light(marker: Node3D) -> void:
	var info := {}
	for l: Variant in _entry.get("lights", []):
		if l is Dictionary and String(l.get("name", "")) == String(marker.name):
			info = l
	var kind := String(info.get("kind", "omni"))
	var col_a: Array = info.get("color", [1.0, 0.82, 0.55])
	var light: Light3D
	if kind == "spot":
		var sp := SpotLight3D.new()
		sp.spot_range = float(info.get("range", 10.0))
		sp.spot_angle = float(info.get("angle", 55.0))
		sp.spot_attenuation = 1.0
		light = sp
		var d: Array = info.get("dir", [0.0, -1.0, 0.0])
		var dv := Vector3(float(d[0]), float(d[1]), float(d[2])).normalized()
		if absf(dv.dot(Vector3.UP)) > 0.99:
			sp.basis = Basis(Vector3.RIGHT, -PI * 0.5) if dv.y < 0.0 else Basis(Vector3.RIGHT, PI * 0.5)
		else:
			sp.basis = Basis.looking_at(dv, Vector3.UP)
	else:
		var om := OmniLight3D.new()
		om.omni_range = float(info.get("range", 3.0))
		om.omni_attenuation = 1.4
		light = om
	light.name = "Light"
	light.light_color = Color(float(col_a[0]), float(col_a[1]), float(col_a[2]))
	light.light_energy = 0.0
	light.light_indirect_energy = 0.8
	light.shadow_enabled = bool(info.get("shadow", false))
	light.distance_fade_enabled = true
	light.distance_fade_begin = float(info.get("fade", 40.0))
	light.distance_fade_length = 10.0
	light.set_meta(&"night_light_energy", float(info.get("energy", 1.0)))
	light.add_to_group(&"prop_night_light", true)
	marker.add_child(light)
	light.owner = marker.owner if marker.owner != null else marker
	_has_night = true


func _make_dynamic(scene: Node3D) -> Node3D:
	var rb := RigidBody3D.new()
	rb.name = scene.name
	if ResourceLoader.exists(PUSHABLE):
		rb.set_script(load(PUSHABLE))
	var mass := maxf(float(_entry.get("mass", 0.3)), 0.01)
	rb.mass = mass
	rb.set_meta(&"mass", mass)
	rb.set("material_kind", StringName(String(_entry.get("material_kind", "plastic"))))
	if _entry.has("break_height"):
		rb.set("break_height", float(_entry["break_height"]))
	var kids := scene.get_children()
	for c in kids:
		scene.remove_child(c)
		if c is StaticBody3D:
			var body := c as StaticBody3D
			for s in body.get_children():
				if s is CollisionShape3D:
					var cs := s as CollisionShape3D
					var xf := body.transform * cs.transform
					body.remove_child(cs)
					cs.transform = xf
					cs.name = "Shape_%s" % String(body.name)
					rb.add_child(cs)
			body.free()
		else:
			rb.add_child(c)
	_set_owner(rb, rb)
	scene.free()
	return rb


func _set_owner(n: Node, owner_node: Node) -> void:
	for c in n.get_children():
		c.owner = owner_node
		_set_owner(c, owner_node)
