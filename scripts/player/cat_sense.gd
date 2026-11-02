extends Node
## Cat-sense (owner: player): a brief stylised scent/sound overlay (GDD "Cat-sense (R)").
##
## toggle() → GameEvents.cat_sense_toggled(true) (GameState charges the energy), the global shader
## parameter `cat_sense` eases 0 → 1 (post effect shaders/cat_sense.gdshader on a full-screen quad
## under the camera: cat vision + whisker edges + vignette), interactables in range get a warm
## glow and animals/prey a cool one (material_overlay via OverlayUtil), and a trail of drifting
## scent motes flows from Cam towards QuestManager.get_tracked_target_position() along the
## navigation path when a nav map exists (straight line otherwise). Auto-ends after `duration`.

const OverlayUtil := preload("res://scripts/player/overlay_util.gd")
const POST_SHADER := preload("res://shaders/cat_sense.gdshader")
const HIGHLIGHT_SHADER := preload("res://shaders/cat_sense_highlight.gdshader")
const ANIMAL_KINDS: Array[String] = ["cat", "dog", "crow", "pigeon", "pigeon_flock", "mouse", "koi", "bird"]

@export var duration := 8.0
@export var cooldown := 1.2
@export var base_range := 14.0
@export var fade_time := 0.45
@export var trail_points := 64

var active := false
var _player: Node3D
var _value := 0.0
var _t := 0.0
var _cool := 0.0
var _post: MeshInstance3D = null
var _post_mat: ShaderMaterial
var _glow_mat: ShaderMaterial
var _animal_mat: ShaderMaterial
var _highlighted: Array[Node] = []
var _trail: GPUParticles3D = null
var _trail_t := 0.0
var _rescan_t := 0.0


func _ready() -> void:
	_player = get_parent() as Node3D
	_post_mat = ShaderMaterial.new()
	_post_mat.shader = POST_SHADER
	_post_mat.render_priority = -20
	_glow_mat = ShaderMaterial.new()
	_glow_mat.shader = HIGHLIGHT_SHADER
	_glow_mat.render_priority = 20
	_animal_mat = ShaderMaterial.new()
	_animal_mat.shader = HIGHLIGHT_SHADER
	_animal_mat.render_priority = 20
	_animal_mat.set_shader_parameter(&"glow_color", Color(0.45, 0.8, 1.0))
	_animal_mat.set_shader_parameter(&"strength", 0.8)
	RenderingServer.global_shader_parameter_set(&"cat_sense", 0.0)


func toggle() -> void:
	if active:
		deactivate()
	else:
		activate()


func activate() -> void:
	if active or _cool > 0.0:
		return
	active = true
	_t = 0.0
	_ensure_post()
	_scan_highlights()
	_update_trail(true)
	GameEvents.cat_sense_toggled.emit(true)
	var am := get_node_or_null(^"/root/AudioManager")
	if am != null and am.has_method(&"play_sfx"):
		am.call(&"play_sfx", &"cat_sniff", _player.global_position + Vector3.UP * 0.2)


func deactivate() -> void:
	if not active:
		return
	active = false
	_cool = cooldown
	GameEvents.cat_sense_toggled.emit(false)
	if _trail != null:
		_trail.emitting = false


func is_active() -> bool:
	return active


func get_value() -> float:
	return _value


func _process(delta: float) -> void:
	_cool = maxf(0.0, _cool - delta)
	var goal := 1.0 if active else 0.0
	var prev := _value
	_value = move_toward(_value, goal, delta / maxf(fade_time, 0.01))
	if _value != prev:
		var eased := _value * _value * (3.0 - 2.0 * _value)
		RenderingServer.global_shader_parameter_set(&"cat_sense", eased)
	if _post != null:
		_post.visible = _value > 0.001
		_attach_post_to_camera()
	if not active:
		if _value <= 0.0 and not _highlighted.is_empty():
			_clear_highlights()
		return
	_t += delta
	if _t >= duration:
		deactivate()
		return
	_rescan_t += delta
	if _rescan_t > 0.5:
		_rescan_t = 0.0
		_scan_highlights()
	_trail_t += delta
	if _trail_t > 1.0:
		_trail_t = 0.0
		_update_trail(false)


# --- post quad ----------------------------------------------------------------------------------

func _ensure_post() -> void:
	if _post != null:
		return
	_post = MeshInstance3D.new()
	_post.name = "CatSensePost"
	var q := QuadMesh.new()
	q.size = Vector2(2.0, 2.0)
	q.flip_faces = true
	_post.mesh = q
	_post.material_override = _post_mat
	_post.extra_cull_margin = 16384.0
	_post.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_post.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	_attach_post_to_camera()


func _attach_post_to_camera() -> void:
	var cam := _camera()
	if cam == null or _post == null:
		return
	if _post.get_parent() != cam:
		if _post.get_parent() != null:
			_post.get_parent().remove_child(_post)
		cam.add_child(_post)
		_post.position = Vector3(0.0, 0.0, -0.5)


func _camera() -> Camera3D:
	if _player != null and _player.has_method(&"get_camera"):
		var c: Camera3D = _player.call(&"get_camera")
		if c != null:
			return c
	return get_viewport().get_camera_3d() if get_viewport() != null else null


# --- highlights ---------------------------------------------------------------------------------

func _range() -> float:
	return base_range * GameState.get_modifier(&"scent_range")


func _scan_highlights() -> void:
	var r := _range()
	var r2 := r * r
	var origin := _player.global_position
	var keep: Array[Node] = []
	for n in get_tree().get_nodes_in_group(&"interactable"):
		var n3 := n as Node3D
		if n3 == null or not n3.is_visible_in_tree() or n3.global_position.distance_squared_to(origin) > r2:
			continue
		if n.has_method(&"is_visible_to") and not bool(n.call(&"is_visible_to", _player)):
			continue
		var h: Node = n.call(&"get_highlight_node") if n.has_method(&"get_highlight_node") else null
		if h != null and _too_big(h):
			h = null  # a fallback that resolved to level geometry (floor, wall): never glow the world
		if h != null:
			OverlayUtil.set_layer(h, &"sense", _glow_mat)
			keep.append(h)
	for group: StringName in [&"npc", &"prey"]:
		for n in get_tree().get_nodes_in_group(group):
			var n3 := n as Node3D
			if n3 == null or n3.global_position.distance_squared_to(origin) > r2:
				continue
			var kind := String(n.get_meta(&"npc_kind", "prey" if group == &"prey" else ""))
			if group == &"npc" and not kind in ANIMAL_KINDS:
				continue
			OverlayUtil.set_layer(n3, &"sense_npc", _animal_mat)
			keep.append(n3)
	for old in _highlighted:
		if is_instance_valid(old) and not old in keep:
			OverlayUtil.clear_layer(old, &"sense")
			OverlayUtil.clear_layer(old, &"sense_npc")
	_highlighted = keep


func _too_big(n: Node) -> bool:
	var vi := n as VisualInstance3D
	if vi == null:
		return false
	var sz := vi.get_aabb().size * vi.global_basis.get_scale().abs()
	return maxf(sz.x, maxf(sz.y, sz.z)) > 4.0


func _clear_highlights() -> void:
	for n in _highlighted:
		if is_instance_valid(n):
			OverlayUtil.clear_layer(n, &"sense")
			OverlayUtil.clear_layer(n, &"sense_npc")
	_highlighted.clear()


# --- scent trail --------------------------------------------------------------------------------

func _target_position() -> Vector3:
	var qm := get_node_or_null(^"/root/QuestManager")
	if qm != null and qm.has_method(&"get_tracked_target_position"):
		return qm.call(&"get_tracked_target_position")
	return Vector3.INF


func _path_to(target: Vector3) -> PackedVector3Array:
	var from := _player.global_position
	var world := _player.get_world_3d()
	var pts := PackedVector3Array()
	if world != null:
		var map := world.navigation_map
		if map.is_valid() and NavigationServer3D.map_get_regions(map).size() > 0:
			pts = NavigationServer3D.map_get_path(map, from, target, true)
	if pts.size() < 2:
		pts = PackedVector3Array([from, target])
	return pts


func _update_trail(force: bool) -> void:
	var target := _target_position()
	if target == Vector3.INF:
		if _trail != null:
			_trail.emitting = false
		return
	var path := _path_to(target)
	# resample: only the first ~12 m of the path (the scent fades with distance)
	var max_len := minf(12.0, _range())
	var samples := PackedVector3Array()
	var normals := PackedVector3Array()
	var acc := 0.0
	var step := max_len / float(trail_points)
	var i := 0
	var cursor := path[0]
	var seg := 1
	while samples.size() < trail_points and seg < path.size():
		var nxt := path[seg]
		var d := cursor.distance_to(nxt)
		if d < 0.0001:
			seg += 1
			continue
		var dir := (nxt - cursor) / d
		if d >= step:
			cursor += dir * step
			acc += step
			samples.append(cursor + Vector3.UP * (0.12 + 0.05 * sin(acc * 2.0)))
			normals.append(dir)
		else:
			cursor = nxt
			seg += 1
		i += 1
		if i > 4000:
			break
	if samples.is_empty():
		return
	if _trail == null:
		_trail = _make_trail()
	var origin := _player.global_position
	var img := Image.create_empty(samples.size(), 1, false, Image.FORMAT_RGBF)
	var nimg := Image.create_empty(samples.size(), 1, false, Image.FORMAT_RGBF)
	for k in samples.size():
		var p := samples[k] - origin
		img.set_pixel(k, 0, Color(p.x, p.y, p.z))
		var n := normals[k]
		nimg.set_pixel(k, 0, Color(n.x, n.y, n.z))
	var pm := _trail.process_material as ParticleProcessMaterial
	pm.emission_point_texture = ImageTexture.create_from_image(img)
	pm.emission_normal_texture = ImageTexture.create_from_image(nimg)
	pm.emission_point_count = samples.size()
	_trail.global_position = origin
	if force or not _trail.emitting:
		_trail.restart()
	_trail.emitting = true


func _make_trail() -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = "ScentTrail"
	p.amount = 220
	p.lifetime = 2.4
	p.preprocess = 0.8
	p.visibility_aabb = AABB(Vector3(-15, -5, -15), Vector3(30, 10, 30))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_DIRECTED_POINTS
	pm.direction = Vector3(0, 0, 1)
	pm.spread = 12.0
	pm.initial_velocity_min = 0.25
	pm.initial_velocity_max = 0.55
	pm.gravity = Vector3(0, 0.04, 0)
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.6
	pm.turbulence_noise_scale = 2.2
	pm.turbulence_influence_min = 0.05
	pm.turbulence_influence_max = 0.15
	pm.scale_min = 0.5
	pm.scale_max = 1.2
	var sc := Curve.new()
	sc.add_point(Vector2(0.0, 0.0))
	sc.add_point(Vector2(0.25, 1.0))
	sc.add_point(Vector2(1.0, 0.2))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.3, 1.0])
	grad.colors = PackedColorArray([Color(1.0, 0.85, 0.5, 0.0), Color(1.0, 0.78, 0.4, 0.9), Color(0.6, 0.85, 1.0, 0.0)])
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var quad := QuadMesh.new()
	quad.size = Vector2(0.035, 0.035)
	p.draw_pass_1 = quad
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	var tex := GradientTexture2D.new()
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	var g2 := Gradient.new()
	g2.set_color(0, Color(1, 1, 1, 1))
	g2.set_color(1, Color(1, 1, 1, 0))
	tex.gradient = g2
	mat.albedo_texture = tex
	mat.render_priority = 25
	p.material_override = mat
	# lives in the world (not under the moving cat) so motes stay where the scent is
	var world_parent := _player.get_parent() if _player.get_parent() != null else _player
	world_parent.add_child(p)
	return p


func _exit_tree() -> void:
	_clear_highlights()
	if _trail != null and is_instance_valid(_trail):
		_trail.queue_free()
	RenderingServer.global_shader_parameter_set(&"cat_sense", 0.0)
