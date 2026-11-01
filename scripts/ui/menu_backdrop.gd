extends Node3D
## Live 3D backdrop of the main menu: an old-quarter rooftop at dusk. Cam sleeps curled on a
## parapet in the foreground; behind him the street drops away to the opposite row of shophouses,
## a string of silk lanterns sways across the street and the low sun burns through the haze.
## Built from the city-houses kit (assets/models/city) and the cat (assets/models/cat/cat.glb).
## Everything degrades gracefully: missing modules are skipped, a missing cat leaves the ledge empty.

const CITY := "res://assets/models/city/"
const CAT_GLB := "res://assets/models/cat/cat.glb"
const FUR_SCRIPT := "res://scripts/player/fur_shells.gd"

## Near row (camera side, facing the street = +Z) and far row (rotated 180°, across the street).
@export var near_row: PackedStringArray = PackedStringArray([
	"tube90s_5f_w3_5_white", "tube90s_4f_w4_green", "colonial_3f_w4_5_ochre", "tube90s_4f_w5_pink",
	"tube90s_6f_w5_yellow", "colonial_2f_w4_yellow", "tube90s_5f_w3_5_blue"])
@export var far_row: PackedStringArray = PackedStringArray([
	"colonial_3f_w5_white", "tube90s_6f_w5_blue", "tube90s_4f_w4_pink", "colonial_2f_w6_yellow",
	"modern_5f_w4_white", "tube90s_3f_w4_5_green", "colonial_corner_3f_yellow", "tube90s_5f_w3_5_yellow",
	"tube90s_4f_w5_green"])
## Index (in near_row) of the house the cat sleeps on.
@export var hero_index := 1
@export var street_width := 13.5
@export var sun_elevation_deg := 7.0
@export var sun_azimuth_deg := 205.0
@export var drift_amount := 0.22
@export var use_dof := true

var camera: Camera3D
var cat: Node3D = null
var _cat_anim: AnimationPlayer = null
var _t := 0.0
var _cam_base := Transform3D.IDENTITY
var _look_target := Vector3.ZERO
var _lanterns: Array[Node3D] = []
var _catalog: Dictionary = {}
var _hero_origin := Vector3.ZERO
var _hero_width := 4.0
var _env: Environment
var _ready_done := false


func _ready() -> void:
	add_to_group(&"graphics_settings_listener")
	_load_catalog()
	_build_environment()
	_build_rows()
	_build_ground()
	_build_lantern_string()
	_build_roof_clutter()
	camera = Camera3D.new()
	camera.name = "MenuCamera"
	camera.fov = 38.0
	camera.near = 0.03
	camera.far = 900.0
	add_child(camera)
	camera.make_current()
	_place_camera_default()
	_settle_and_place_cat.call_deferred()


func apply_graphics_settings() -> void:
	if _env != null:
		var s := get_node_or_null(^"/root/Settings")
		if s != null:
			s.call("configure_environment", _env)
		_env.sdfgi_enabled = false  # small static set: cheaper fixed ambient


func _load_catalog() -> void:
	var path := CITY + "catalog.json"
	if not FileAccess.file_exists(path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if parsed is Array:
		for m: Variant in parsed:
			if m is Dictionary:
				_catalog[String((m as Dictionary).get("id", ""))] = m


func _module(id: String) -> Dictionary:
	return _catalog.get(id, {})


func _build_environment() -> void:
	var we := WorldEnvironment.new()
	we.name = "MenuEnvironment"
	_env = Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color("#22263f")
	sm.sky_horizon_color = Color("#e7905e")
	sm.sky_curve = 0.09
	sm.sky_energy_multiplier = 1.15
	sm.ground_bottom_color = Color("#20160f")
	sm.ground_horizon_color = Color("#d78a5c")
	sm.ground_curve = 0.05
	sm.sun_angle_max = 28.0
	sm.sun_curve = 0.08
	sky.sky_material = sm
	_env.background_mode = Environment.BG_SKY
	_env.sky = sky
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	_env.ambient_light_energy = 0.75
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	_env.tonemap_mode = Environment.TONE_MAPPER_AGX
	_env.tonemap_exposure = 1.05
	_env.glow_enabled = true
	_env.glow_intensity = 0.9
	_env.glow_strength = 1.05
	_env.glow_bloom = 0.08
	_env.glow_hdr_threshold = 1.1
	_env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	_env.ssao_enabled = true
	_env.ssao_radius = 1.2
	_env.ssao_intensity = 1.6
	_env.fog_enabled = true
	_env.fog_mode = Environment.FOG_MODE_DEPTH
	_env.fog_light_color = Color("#d98e62")
	_env.fog_light_energy = 0.9
	_env.fog_sun_scatter = 0.35
	_env.fog_density = 0.6
	_env.fog_depth_begin = 18.0
	_env.fog_depth_end = 260.0
	_env.fog_depth_curve = 1.6
	_env.fog_sky_affect = 0.25
	_env.volumetric_fog_enabled = true
	_env.volumetric_fog_density = 0.012
	_env.volumetric_fog_albedo = Color("#f2c9a8")
	_env.volumetric_fog_anisotropy = 0.6
	_env.volumetric_fog_length = 90.0
	_env.adjustment_enabled = true
	_env.adjustment_saturation = 1.06
	_env.adjustment_contrast = 1.04
	we.environment = _env
	if use_dof:
		var attr := CameraAttributesPractical.new()
		attr.dof_blur_far_enabled = true
		attr.dof_blur_far_distance = 3.2
		attr.dof_blur_far_transition = 6.0
		attr.dof_blur_amount = 0.09
		we.camera_attributes = attr
	add_child(we)
	apply_graphics_settings()
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color("#ffb27a")
	sun.light_energy = 2.2
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 80.0
	sun.shadow_blur = 1.5
	sun.light_angular_distance = 1.2
	sun.rotation_degrees = Vector3(-sun_elevation_deg, sun_azimuth_deg, 0.0)
	add_child(sun)
	var fill := DirectionalLight3D.new()
	fill.name = "SkyFill"
	fill.light_color = Color("#6f80b8")
	fill.light_energy = 0.25
	fill.rotation_degrees = Vector3(-55.0, 20.0, 0.0)
	add_child(fill)


func _instance_module(id: String) -> Node3D:
	var path := CITY + id + ".glb"
	if not ResourceLoader.exists(path):
		return null
	var ps := load(path) as PackedScene
	if ps == null:
		return null
	return ps.instantiate() as Node3D


func _build_rows() -> void:
	var x := 0.0
	var widths: Array[float] = []
	for id in near_row:
		widths.append(float(_module(id).get("width", 4.0)))
	# centre the hero house on x = 0
	var hero_left := 0.0
	for i in hero_index:
		hero_left += widths[i]
	x = -hero_left - widths[hero_index] * 0.5 if hero_index < widths.size() else 0.0
	for i in near_row.size():
		var w := widths[i]
		var m := _instance_module(near_row[i])
		if m != null:
			add_child(m)
			m.position = Vector3(x + w * 0.5, 0.0, 0.0)
			if i == hero_index:
				_hero_origin = m.position
				_hero_width = w
		x += w
	x = -24.0
	for id in far_row:
		var w := float(_module(id).get("width", 4.0))
		var m := _instance_module(id)
		if m != null:
			add_child(m)
			m.position = Vector3(x + w * 0.5, 0.0, street_width)
			m.rotation.y = PI
		x += w


func _build_ground() -> void:
	var g := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(200, 120)
	g.mesh = pm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("#3b3330")
	mat.roughness = 0.85
	var tex := "res://assets/textures/architecture/concrete_weathered_albedo.jpg"
	if ResourceLoader.exists(tex):
		mat.albedo_texture = load(tex)
		mat.uv1_scale = Vector3(60, 36, 1)
		mat.albedo_color = Color(0.55, 0.5, 0.48)
	g.material_override = mat
	g.position = Vector3(0, 0.0, street_width * 0.5)
	add_child(g)


func _build_lantern_string() -> void:
	# A catenary of silk lanterns across the street, a little in front of the hero roofline.
	var a := Vector3(_hero_origin.x - 9.0, 11.6, 0.6)
	var b := Vector3(_hero_origin.x + 7.0, 12.4, street_width - 0.6)
	var count := 16
	var wire_pts: PackedVector3Array = []
	for i in count + 1:
		var u := float(i) / float(count)
		var p := a.lerp(b, u)
		p.y -= sin(u * PI) * 1.6
		wire_pts.append(p)
	_add_wire(wire_pts, 0.012)
	var colors := [Color("#e8402a"), Color("#f08a2a"), Color("#e8402a"), Color("#f2c04a")]
	for i in range(1, count):
		var p := wire_pts[i]
		var l := _make_lantern(colors[i % colors.size()], i % 3 == 0)
		add_child(l)
		l.position = p + Vector3(0, -0.28, 0)
		_lanterns.append(l)
	# second, higher wire with no lanterns (power cables) for depth
	var c := Vector3(_hero_origin.x - 14.0, 13.8, 0.3)
	var d := Vector3(_hero_origin.x + 16.0, 14.6, street_width - 0.3)
	for k in 3:
		var pts: PackedVector3Array = []
		for i in 25:
			var u := float(i) / 24.0
			var p := (c + Vector3(0, -0.25 * k, 0.4 * k)).lerp(d + Vector3(0, -0.3 * k, -0.2 * k), u)
			p.y -= sin(u * PI) * (1.1 + 0.3 * k)
			pts.append(p)
		_add_wire(pts, 0.009)


func _add_wire(pts: PackedVector3Array, radius: float) -> void:
	var im := ImmediateMesh.new()
	var mi := MeshInstance3D.new()
	mi.mesh = im
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("#0d0b0a")
	mat.roughness = 0.6
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	var sides := 5
	for i in pts.size() - 1:
		var p0 := pts[i]
		var p1 := pts[i + 1]
		var dir := (p1 - p0).normalized()
		var side := dir.cross(Vector3.UP).normalized()
		var up := side.cross(dir).normalized()
		for s in sides:
			var a0 := TAU * float(s) / float(sides)
			var a1 := TAU * float(s + 1) / float(sides)
			var o0 := (side * cos(a0) + up * sin(a0)) * radius
			var o1 := (side * cos(a1) + up * sin(a1)) * radius
			im.surface_set_normal(o0.normalized())
			im.surface_add_vertex(p0 + o0)
			im.surface_add_vertex(p1 + o0)
			im.surface_add_vertex(p1 + o1)
			im.surface_add_vertex(p0 + o0)
			im.surface_add_vertex(p1 + o1)
			im.surface_add_vertex(p0 + o1)
	im.surface_end()
	add_child(mi)


func _make_lantern(color: Color, with_light: bool) -> Node3D:
	var root := Node3D.new()
	var body := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.17
	sm.height = 0.36
	sm.radial_segments = 16
	sm.rings = 10
	body.mesh = sm
	body.scale = Vector3(1.0, 1.05, 1.0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color.darkened(0.2)
	mat.emission_enabled = true
	mat.emission = color.lerp(Color("#ffcf8a"), 0.35)
	mat.emission_energy_multiplier = 2.6
	mat.roughness = 0.7
	mat.rim_enabled = true
	mat.rim = 0.4
	body.material_override = mat
	body.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(body)
	for yy in [0.19, -0.19]:
		var cap := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.07
		cm.bottom_radius = 0.07
		cm.height = 0.035
		cap.mesh = cm
		var capm := StandardMaterial3D.new()
		capm.albedo_color = Color("#3a2410")
		capm.metallic = 0.3
		capm.roughness = 0.5
		cap.material_override = capm
		cap.position.y = yy
		root.add_child(cap)
	var tassel := MeshInstance3D.new()
	var tm := CylinderMesh.new()
	tm.top_radius = 0.012
	tm.bottom_radius = 0.03
	tm.height = 0.16
	tassel.mesh = tm
	var tmat := StandardMaterial3D.new()
	tmat.albedo_color = color.darkened(0.35)
	tassel.material_override = tmat
	tassel.position.y = -0.29
	root.add_child(tassel)
	var cord := MeshInstance3D.new()
	var cdm := CylinderMesh.new()
	cdm.top_radius = 0.004
	cdm.bottom_radius = 0.004
	cdm.height = 0.12
	cord.mesh = cdm
	cord.material_override = tmat
	cord.position.y = 0.26
	root.add_child(cord)
	if with_light:
		var l := OmniLight3D.new()
		l.light_color = Color("#ff9a52")
		l.light_energy = 1.6
		l.omni_range = 4.5
		l.omni_attenuation = 1.4
		l.shadow_enabled = false
		root.add_child(l)
	return root


func _build_roof_clutter() -> void:
	# Water tank stand and solar heater on neighbouring roofs, a plank bridge between roofs.
	var items := [
		["roofprop_tank_stand", Vector3(_hero_origin.x + _hero_width * 0.5 + 2.3, -1.0, -6.0), 0.4],
		["roofprop_solar", Vector3(_hero_origin.x - _hero_width * 0.5 - 1.8, -1.0, -8.0), 2.6],
		["roofprop_tank_stand", Vector3(_hero_origin.x - 6.0, -1.0, street_width + 6.0), 1.2],
		["roofprop_solar", Vector3(_hero_origin.x + 3.0, -1.0, street_width + 8.0), -0.4],
	]
	for it: Array in items:
		var m := _instance_module(String(it[0]))
		if m == null:
			continue
		add_child(m)
		m.position = it[1]
		m.rotation.y = float(it[2])
		_drop_to_roof.call_deferred(m)


func _drop_to_roof(n: Node3D) -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	var y := _ray_down(Vector3(n.global_position.x, 60.0, n.global_position.z), [n])
	if y > -INF:
		n.global_position.y = y


func _ray_down(from: Vector3, exclude_nodes: Array = []) -> float:
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3(0, -80, 0))
	q.collision_mask = 0xFFFFFFFF
	var ex: Array[RID] = []
	for n: Node in exclude_nodes:
		for b in n.find_children("*", "CollisionObject3D", true, false):
			ex.append((b as CollisionObject3D).get_rid())
	q.exclude = ex
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return -INF
	return (hit["position"] as Vector3).y


func _place_camera_default() -> void:
	var top := float(_module(near_row[hero_index] if hero_index < near_row.size() else "").get("height", 14.7))
	var cat_pos := _hero_origin + Vector3(-_hero_width * 0.5 + 0.6, top, 0.15)
	_set_shot(cat_pos)


func _set_shot(cat_pos: Vector3) -> void:
	# Low camera on the roof behind/beside the cat, looking across the street toward the sun.
	var cam_pos := cat_pos + Vector3(1.25, 0.32, -1.45)
	_look_target = cat_pos + Vector3(-0.9, 0.05, 1.4)
	_cam_base = Transform3D(Basis.IDENTITY, cam_pos).looking_at(_look_target, Vector3.UP)
	camera.global_transform = _cam_base


func _settle_and_place_cat() -> void:
	for i in 3:
		await get_tree().physics_frame
	var top_guess := float(_module(near_row[hero_index] if hero_index < near_row.size() else "").get("height", 14.7))
	# Front parapet: probe along the facade for the highest surface near the roof line.
	var best := Vector3.ZERO
	var best_y := -INF
	for xi in range(-3, 4):
		for zi in [0.05, 0.12, 0.2, 0.3]:
			var px := _hero_origin.x - _hero_width * 0.5 + 0.55 + float(xi + 3) * 0.12
			var y := _ray_down(Vector3(px, top_guess + 6.0, _hero_origin.z - float(zi)))
			if y > best_y and y < top_guess + 1.5 and y > top_guess - 3.0:
				best_y = y
				best = Vector3(px, y, _hero_origin.z - float(zi))
	if best_y == -INF:
		best = _hero_origin + Vector3(-_hero_width * 0.5 + 0.6, top_guess, -0.15)
	_spawn_cat(best)
	_set_shot(best)
	_ready_done = true


func _spawn_cat(pos: Vector3) -> void:
	if not ResourceLoader.exists(CAT_GLB):
		return
	var ps := load(CAT_GLB) as PackedScene
	if ps == null:
		return
	cat = ps.instantiate() as Node3D
	cat.name = "SleepingCam"
	add_child(cat)
	cat.global_position = pos
	# Lying along the parapet, head toward the camera side.
	cat.rotation.y = deg_to_rad(-100.0)
	var players := cat.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		_cat_anim = players[0] as AnimationPlayer
		for a in [&"sleep", &"lie_down", &"idle"]:
			if _cat_anim.has_animation(a):
				var anim := _cat_anim.get_animation(a)
				if a != &"lie_down":
					anim.loop_mode = Animation.LOOP_LINEAR
				_cat_anim.play(a)
				break
	if ResourceLoader.exists(FUR_SCRIPT):
		var fur_script := load(FUR_SCRIPT) as Script
		if fur_script != null:
			var fur: Node = fur_script.new()
			if "use_game_state_wetness" in fur:
				fur.set("use_game_state_wetness", false)
			add_child(fur)
			if fur.has_method("attach_to_model"):
				fur.call("attach_to_model", cat, cat)


func _process(delta: float) -> void:
	_t += delta
	if camera != null and _ready_done:
		var off := Vector3(sin(_t * 0.11) * drift_amount, sin(_t * 0.17) * drift_amount * 0.25, cos(_t * 0.09) * drift_amount * 0.4)
		var xf := _cam_base
		xf.origin += xf.basis * off
		camera.global_transform = xf.looking_at(_look_target + Vector3(sin(_t * 0.07) * 0.08, 0, 0), Vector3.UP)
	for i in _lanterns.size():
		var l := _lanterns[i]
		l.rotation.z = sin(_t * 1.1 + float(i) * 0.8) * 0.06
		l.rotation.x = sin(_t * 0.8 + float(i) * 1.3) * 0.05
