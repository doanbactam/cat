@tool
extends EditorScenePostImport
## Post-import for every city-houses module (.glb in assets/models/city/).
## Wired through each glb's .import file (import_script/path), written by blender/city/build_city.py.
##
## Materials (by glTF material name prefix):
##   arch_*  opaque, vertex colour multiplies albedo (macro dirt/tint baked by the generator),
##           anisotropic filtering (facades are seen at grazing angles from the street).
##   dec_*   alpha-blended grime/poster decals; their MeshInstance casts no shadow.
##   fol_*   alpha-scissor, double-sided foliage / laundry with a little backlight.
##   lit_*   night emissive (signs, lamps, lit windows). Emission is enabled with
##           emission_energy_multiplier = 0.0; the `world` area raises it at night
##           (find materials via node meta "night_emissive" = true on the MeshInstance3D).
## Colliders (Blender "<name>-convcolonly" boxes, name = "col_<surface>[_<tag>...]_<n>"):
##   each 8-point convex hull is converted to an exact BoxShape3D; StaticBody3D gets
##   collision layer 1 (world) [+ 6 climbable if tag "climb"] [+ 9 camera_blocker if tag "wall"],
##   metadata "surface" (StringName) for footsteps, and group "climbable" when climbable.
## Markers (empties): NAP_*, CLIMB_*, ENTRANCE_* -> groups city_nap_spot / city_climb_point /
##   city_entrance (persistent groups so they survive packing).
##   LIGHT_SHOP_* -> a shadowless warm OmniLight3D (shop tube light fill, on day and night; group
##   "city_shop_light" so the world can dim/raise them).

const LAYER_WORLD := 1
const LAYER_CLIMB := 1 << 5
const LAYER_CAMERA := 1 << 8
const SURFACES: Array[String] = ["asphalt", "concrete", "tile", "wood", "metal", "grass", "dirt", "water",
	"roof_tile", "fabric", "plastic"]


func _post_import(scene: Node) -> Object:
	var mats_done := {}
	_walk(scene, mats_done)
	scene.set_meta(&"city_module", true)
	return scene


func _walk(n: Node, mats_done: Dictionary) -> void:
	for c in n.get_children():
		_walk(c, mats_done)
	if n is MeshInstance3D:
		_fix_mesh(n as MeshInstance3D, mats_done)
	elif n is StaticBody3D:
		_fix_body(n as StaticBody3D)
	elif n.get_class() == "Node3D":
		var nm := String(n.name)
		if nm.begins_with("NAP_"):
			n.add_to_group(&"city_nap_spot", true)
		elif nm.begins_with("CLIMB_"):
			n.add_to_group(&"city_climb_point", true)
		elif nm.begins_with("ENTRANCE_"):
			n.add_to_group(&"city_entrance", true)
		elif nm.begins_with("LIGHT_SHOP_"):
			var l := OmniLight3D.new()
			l.name = "ShopLight"
			l.light_color = Color(1.0, 0.95, 0.86)
			l.light_energy = 0.9
			l.light_indirect_energy = 0.6
			l.omni_range = 3.6
			l.omni_attenuation = 1.2
			l.shadow_enabled = false
			l.distance_fade_enabled = true
			l.distance_fade_begin = 45.0
			l.distance_fade_length = 15.0
			l.add_to_group(&"city_shop_light", true)
			n.add_child(l)
			l.owner = n.owner if n.owner != null else n


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
		if nm.begins_with("lit_"):
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
			# shop tube lights burn all day; signs / lit windows only at night (world drives them)
			m.emission_energy_multiplier = 1.5 if nm == "lit_lamp" else 0.0
			m.set_meta(&"night_emission_energy", 2.0 if nm != "lit_lamp" else 3.0)
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
		mi.visibility_range_end = 110.0
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
