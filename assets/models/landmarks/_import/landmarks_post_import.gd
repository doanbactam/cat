@tool
extends EditorScenePostImport
## Post-import for every landmark (.glb in assets/models/landmarks/), wired through each glb's
## .import file (import_script/path), written by blender/landmarks/build_landmarks.py.
##
## Materials (by glTF material name prefix) — same conventions as the city-houses kit:
##   arch_* / lm_*  opaque, vertex colour multiplies albedo (tint + baked macro grime), anisotropic.
##   dec_*          alpha-blended (grime decals, glass jars); MeshInstance without shadows if all-decal.
##   fol_*          alpha-scissor, double-sided (foliage cards, nest twigs) with backlight.
##   lit_*          emissive. `lit_lamp` (altar candles, shop tubes) burns all the time; every other lit_*
##                  (lake lamp globes, bulbs, lit signs) ships with emission_energy_multiplier = 0 and meta
##                  `night_emission_energy`; the MeshInstance3D gets meta `night_emissive = true` so the
##                  world can scale it with `night_factor`.
## Colliders: "<col_<surface>[_climb][_wall]_NNN>-convcolonly" boxes -> StaticBody3D with one exact
##   BoxShape3D, layer 1 (+6 climbable, group "climbable") (+9 camera_blocker), meta `surface`.
## Markers (empties):
##   NAP_* / CLIMB_* / ENTRANCE_*  -> groups landmark_nap_spot / landmark_climb_point / landmark_entrance
##                                  (+ the city_* groups so world code can treat both kits alike)
##   LIGHT_SHOP_*   warm shadowless OmniLight3D, always on (group city_shop_light)
##   LIGHT_NIGHT_*  lamp OmniLight3D, energy 0 by day; group landmark_night_light, meta night_energy
##   LIGHT_ALTAR_*  small red-orange altar glow, always on
##   QUEST_<id>     group quest_target, meta target_id = <id> (QuestManager target resolution)
##   MARKER_<id>    group landmark_marker, meta marker_id = <id> (banyan, fish stall, bowl, ...)
##   SHELTER_*      Area3D box (group "shelter": rain does not wet the cat), layer 10 triggers
##   REVERB_<Bus>_* Area3D box with reverb_bus_enabled -> audio bus <Bus> (Temple/Market/Interior)

const LAYER_WORLD := 1
const LAYER_CLIMB := 1 << 5
const LAYER_CAMERA := 1 << 8
const LAYER_TRIGGER := 1 << 9
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]


func _post_import(scene: Node) -> Object:
	var mats_done := {}
	_walk(scene, mats_done)
	scene.set_meta(&"landmark_module", true)
	return scene


func _walk(n: Node, mats_done: Dictionary) -> void:
	for c in n.get_children():
		_walk(c, mats_done)
	if n is MeshInstance3D:
		_fix_mesh(n as MeshInstance3D, mats_done)
	elif n is StaticBody3D:
		_fix_body(n as StaticBody3D)
	elif n.get_class() == "Node3D":
		_fix_marker(n as Node3D)


func _owner_of(n: Node) -> Node:
	return n.owner if n.owner != null else n


func _fix_marker(n: Node3D) -> void:
	var nm := String(n.name)
	if nm.begins_with("NAP_"):
		n.add_to_group(&"landmark_nap_spot", true)
		n.add_to_group(&"city_nap_spot", true)
	elif nm.begins_with("CLIMB_"):
		n.add_to_group(&"landmark_climb_point", true)
		n.add_to_group(&"city_climb_point", true)
	elif nm.begins_with("ENTRANCE_"):
		n.add_to_group(&"landmark_entrance", true)
		n.add_to_group(&"city_entrance", true)
	elif nm.begins_with("QUEST_"):
		n.add_to_group(&"quest_target", true)
		n.set_meta(&"target_id", nm.substr(6))
	elif nm.begins_with("MARKER_"):
		n.add_to_group(&"landmark_marker", true)
		n.set_meta(&"marker_id", nm.substr(7))
	elif nm.begins_with("LIGHT_"):
		_add_light(n, nm)
	elif nm.begins_with("SHELTER_") or nm.begins_with("REVERB_"):
		_add_zone(n, nm)


func _add_light(n: Node3D, nm: String) -> void:
	var l := OmniLight3D.new()
	l.shadow_enabled = false
	l.distance_fade_enabled = true
	l.distance_fade_begin = 50.0
	l.distance_fade_length = 15.0
	if nm.begins_with("LIGHT_NIGHT_"):
		l.name = "NightLight"
		l.light_color = Color(1.0, 0.82, 0.58)
		l.light_energy = 0.0
		l.light_indirect_energy = 0.8
		l.omni_range = 9.0
		l.omni_attenuation = 1.4
		l.set_meta(&"night_energy", 2.2)
		l.add_to_group(&"landmark_night_light", true)
	elif nm.begins_with("LIGHT_ALTAR_"):
		l.name = "AltarLight"
		l.light_color = Color(1.0, 0.55, 0.32)
		l.light_energy = 0.7
		l.omni_range = 3.2
		l.omni_attenuation = 1.6
		l.add_to_group(&"city_shop_light", true)
	else:
		l.name = "ShopLight"
		l.light_color = Color(1.0, 0.93, 0.82)
		l.light_energy = 0.9
		l.light_indirect_energy = 0.6
		l.omni_range = 4.0
		l.omni_attenuation = 1.2
		l.add_to_group(&"city_shop_light", true)
	n.add_child(l)
	l.owner = _owner_of(n)


func _add_zone(n: Node3D, nm: String) -> void:
	var size := n.scale.abs() * 2.0
	n.scale = Vector3.ONE
	var a := Area3D.new()
	a.collision_layer = LAYER_TRIGGER
	a.collision_mask = 0
	a.monitoring = false
	a.monitorable = false
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = size
	cs.shape = bx
	a.add_child(cs)
	if nm.begins_with("SHELTER_"):
		a.name = "Shelter"
		a.add_to_group(&"shelter", true)
	else:
		var parts := nm.split("_")
		a.name = "Reverb"
		a.reverb_bus_enabled = true
		a.reverb_bus_name = StringName(parts[1] if parts.size() > 1 else "Temple")
		a.reverb_bus_amount = 0.45
		a.reverb_bus_uniformity = 0.3
		a.add_to_group(&"reverb_zone", true)
	n.add_child(a)
	a.owner = _owner_of(n)
	cs.owner = _owner_of(n)


func _fix_mesh(mi: MeshInstance3D, mats_done: Dictionary) -> void:
	var mesh := mi.mesh
	if mesh == null:
		return
	var all_decal := true
	var has_lit := false
	for s in mesh.get_surface_count():
		var m := mesh.surface_get_material(s) as StandardMaterial3D
		if m == null:
			all_decal = false
			continue
		var nm := m.resource_name
		if not nm.begins_with("dec_"):
			all_decal = false
		if nm.begins_with("lit_") and nm != "lit_lamp":
			has_lit = true
		if mats_done.has(m):
			continue
		mats_done[m] = true
		var am := mesh as ArrayMesh
		var fmt: int = am.surface_get_format(s) if am != null else 0
		m.vertex_color_use_as_albedo = (fmt & Mesh.ARRAY_FORMAT_COLOR) != 0
		m.vertex_color_is_srgb = false
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		if nm.begins_with("dec_"):
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.cull_mode = BaseMaterial3D.CULL_BACK
			m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY
			m.render_priority = 1
			if nm == "dec_lm_glass":
				m.roughness = 0.05
				m.metallic_specular = 0.7
		elif nm.begins_with("fol_"):
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
			m.alpha_scissor_threshold = 0.5
			m.alpha_antialiasing_mode = BaseMaterial3D.ALPHA_ANTIALIASING_OFF
			m.cull_mode = BaseMaterial3D.CULL_DISABLED
			m.backlight_enabled = true
			m.backlight = Color(0.25, 0.3, 0.15)
		else:
			m.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
			m.cull_mode = BaseMaterial3D.CULL_BACK
		if nm.begins_with("lit_"):
			m.emission_enabled = true
			if m.emission_texture == null and m.albedo_texture != null:
				m.emission_texture = m.albedo_texture
			if nm == "lit_lamp":
				m.emission_energy_multiplier = 1.5
				m.set_meta(&"night_emission_energy", 2.0)
			else:
				m.emission_energy_multiplier = 0.0
				m.set_meta(&"night_emission_energy", 3.0 if nm != "lit_lm_atlas" else 1.6)
	if all_decal:
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if has_lit:
		mi.set_meta(&"night_emissive", true)
	var lname := String(mi.name).to_lower()
	if lname.contains("decals"):
		mi.visibility_range_end = 70.0
		mi.visibility_range_end_margin = 10.0
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	elif lname.contains("foliage") or lname.contains("clutter"):
		mi.visibility_range_end = 120.0
		mi.visibility_range_end_margin = 15.0
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF


func _fix_body(body: StaticBody3D) -> void:
	var nm := String(body.name)
	var parts := nm.split("_")
	var surface := "concrete"
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
	if "wall" in parts:
		layer |= LAYER_CAMERA
	if surface == "water":
		layer = 1 << 6
	body.collision_layer = layer
	body.collision_mask = 0
	for c in body.get_children():
		var cs := c as CollisionShape3D
		if cs == null:
			continue
		var cvx := cs.shape as ConvexPolygonShape3D
		if cvx == null:
			continue
		var pts := cvx.points
		var aabb := AABB(pts[0], Vector3.ZERO)
		for p in pts:
			aabb = aabb.expand(p)
		if _is_box(pts, aabb):
			var bx := BoxShape3D.new()
			bx.size = aabb.size
			cs.shape = bx
			cs.position += aabb.get_center()


func _is_box(pts: PackedVector3Array, aabb: AABB) -> bool:
	var eps := 0.002
	for p in pts:
		var on_x := absf(p.x - aabb.position.x) < eps or absf(p.x - aabb.end.x) < eps
		var on_y := absf(p.y - aabb.position.y) < eps or absf(p.y - aabb.end.y) < eps
		var on_z := absf(p.z - aabb.position.z) < eps or absf(p.z - aabb.end.z) < eps
		if not (on_x and on_y and on_z):
			return false
	return true
