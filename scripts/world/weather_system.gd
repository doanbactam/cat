extends Node3D
## WeatherSystem (owner: world) — group "weather".
##
## Kinds: clear, cloudy, rain, storm, fog. `set_weather(kind, intensity)` blends all parameters over
## `transition_time` seconds. Drives: rain GPU particles that follow the active camera (collide with
## a heightfield so it does not rain under roofs/awnings) + splashes, lightning flashes and thunder,
## the `wetness` global shader parameter (ramps up while raining, dries slowly), runtime wetness on
## imported StandardMaterial3Ds (darker albedo, lower roughness), puddle decals, the lake's rain
## ripples and the `wind_strength` / `wind_direction` globals. Emits GameEvents.weather_changed.

const KINDS: Array[StringName] = [&"clear", &"cloudy", &"rain", &"storm", &"fog"]

## kind -> [cloud, overcast, rain, fog, wind]
const PRESETS := {
	&"clear": [0.22, 0.0, 0.0, 0.0, 0.22],
	&"cloudy": [0.75, 0.45, 0.0, 0.05, 0.4],
	&"rain": [0.95, 0.8, 0.7, 0.15, 0.5],
	&"storm": [1.0, 1.0, 1.0, 0.2, 1.0],
	&"fog": [0.5, 0.35, 0.0, 1.0, 0.08],
}

@export var transition_time := 20.0
## Seconds of steady heavy rain to soak the city; drying takes dry_time.
@export var soak_time := 60.0
@export var dry_time := 240.0
@export var auto_weather := true
@export var rain_amount := 9000
@export var rain_area := 34.0

var kind: StringName = &"clear"
var intensity := 0.0
var wetness := 0.0

var _cur := [0.22, 0.0, 0.0, 0.0, 0.22]
var _target := [0.22, 0.0, 0.0, 0.0, 0.22]
var _rain: GPUParticles3D
var _splash: GPUParticles3D
var _collision: GPUParticlesCollisionHeightField3D
var _flash := 0.0
var _next_lightning := 8.0
var _thunder_queue: Array = []        # [time_left, name, pos]
var _wind_phase := 0.0
var wind_direction := Vector3(1, 0, 0.3)
var wind_strength := 0.22
var _wet_mats: Dictionary = {}       # StandardMaterial3D -> [albedo Color, roughness float, metallic]
var _last_wet_applied := -1.0
var _puddles: Array[Decal] = []
var _lake_mats: Array[ShaderMaterial] = []
var _rng := RandomNumberGenerator.new()
var _last_auto_day := -1
var _last_auto_slot := -1


func _ready() -> void:
	add_to_group(&"weather")
	_rng.seed = 7741
	_build_rain()
	_collect.call_deferred()
	var tod: Node = get_node_or_null(^"/root/TimeOfDay")
	if tod != null and not GameEvents.time_tick.is_connected(_on_time_tick):
		GameEvents.time_tick.connect(_on_time_tick)
	_apply_globals()


func _exit_tree() -> void:
	# restore shared imported materials (they are cached resources shared with other scenes)
	_apply_wet_materials(0.0, true)
	RenderingServer.global_shader_parameter_set(&"wetness", 0.0)


# --- public API -----------------------------------------------------------------------------------

func set_weather(p_kind: StringName, p_intensity: float = 1.0) -> void:
	if not p_kind in KINDS:
		push_warning("WeatherSystem: unknown weather '%s'" % p_kind)
		p_kind = &"clear"
	kind = p_kind
	intensity = clampf(p_intensity, 0.0, 1.0)
	var pr: Array = PRESETS[kind]
	_target = pr.duplicate()
	if kind in [&"rain", &"storm"]:
		_target[2] = float(pr[2]) * lerpf(0.35, 1.0, intensity)
	elif kind == &"fog":
		_target[3] = float(pr[3]) * lerpf(0.4, 1.0, intensity)
	GameEvents.weather_changed.emit(kind, intensity)


func get_weather() -> StringName:
	return kind


func get_intensity() -> float:
	return intensity


func get_wetness() -> float:
	return wetness


func get_rain_amount() -> float:
	return float(_cur[2])


## Jump straight to the target state (no blend). Used by save-load, screenshots and tests.
func snap(p_wetness: float = -1.0) -> void:
	_cur = _target.duplicate()
	if p_wetness >= 0.0:
		wetness = clampf(p_wetness, 0.0, 1.0)
	elif float(_cur[2]) > 0.0:
		wetness = clampf(float(_cur[2]) * 1.1, 0.0, 1.0)
	_apply_globals()
	_apply_wet_materials(wetness, true)


func set_weather_immediate(p_kind: StringName, p_intensity: float = 1.0, p_wetness: float = -1.0) -> void:
	set_weather(p_kind, p_intensity)
	snap(p_wetness)


func trigger_lightning(distance: float = -1.0) -> void:
	_flash = 1.0
	var d := distance if distance >= 0.0 else _rng.randf_range(300.0, 2500.0)
	var cam := get_viewport().get_camera_3d() if get_viewport() != null else null
	var pos := Vector3.INF
	if cam != null:
		var dir := Vector3(_rng.randf_range(-1, 1), 0.0, _rng.randf_range(-1, 1)).normalized()
		pos = cam.global_position + dir * minf(d, 60.0) + Vector3.UP * 20.0
	_thunder_queue.append([d / 343.0, &"thunder_near" if d < 900.0 else &"thunder_far", pos, clampf(1.0 - d / 3000.0, 0.2, 1.0)])


# --- simulation -----------------------------------------------------------------------------------

func _process(delta: float) -> void:
	var k := clampf(delta / maxf(transition_time, 0.01) * 3.0, 0.0, 1.0)
	for i in _cur.size():
		_cur[i] = lerpf(float(_cur[i]), float(_target[i]), k)
	var rain := float(_cur[2])
	if rain > 0.02:
		wetness = minf(1.0, wetness + delta * rain / soak_time)
	else:
		wetness = maxf(0.0, wetness - delta / dry_time)
	# lightning
	if kind == &"storm" and float(_cur[1]) > 0.6:
		_next_lightning -= delta
		if _next_lightning <= 0.0:
			_next_lightning = _rng.randf_range(6.0, 22.0)
			trigger_lightning()
	if _flash > 0.0:
		_flash = maxf(0.0, _flash - delta * 3.5)
	for q: Array in _thunder_queue:
		q[0] = float(q[0]) - delta
	while not _thunder_queue.is_empty() and float(_thunder_queue[0][0]) <= 0.0:
		var q: Array = _thunder_queue.pop_front()
		var am: Node = get_node_or_null(^"/root/AudioManager")
		if am != null:
			am.call(&"play_sfx", q[1], q[2], linear_to_db(float(q[3])), 0.08)
	_wind_phase += delta
	_follow_camera()
	_apply_globals()
	if absf(wetness - _last_wet_applied) > 0.015:
		_apply_wet_materials(wetness, false)


func _flash_value() -> float:
	# double-strike flicker
	var f := _flash
	return f * (0.6 + 0.4 * sin(f * 40.0)) if f > 0.0 else 0.0


func _apply_globals() -> void:
	var rain := float(_cur[2])
	RenderingServer.global_shader_parameter_set(&"wetness", wetness)
	var gust := 0.5 + 0.5 * sin(_wind_phase * 0.37) * sin(_wind_phase * 0.11 + 1.3)
	var wind := float(_cur[4]) * lerpf(0.75, 1.25, gust)
	wind_strength = wind
	RenderingServer.global_shader_parameter_set(&"wind_strength", wind)
	var a := 0.35 + sin(_wind_phase * 0.02) * 0.25
	wind_direction = Vector3(cos(a), 0.0, sin(a))
	RenderingServer.global_shader_parameter_set(&"wind_direction", wind_direction)
	var env_ctrl := get_tree().get_first_node_in_group(&"world_environment_controller") if is_inside_tree() else null
	if env_ctrl != null:
		env_ctrl.call(&"set_weather_look", float(_cur[0]), float(_cur[1]), float(_cur[3]), _flash_value())
	if _rain != null:
		var target_amount := rain
		_rain.emitting = target_amount > 0.02
		_rain.amount_ratio = clampf(target_amount, 0.0, 1.0)
		var pm := _rain.process_material as ParticleProcessMaterial
		if pm != null:
			pm.direction = (Vector3.DOWN + wind_direction * wind * 0.25).normalized()
	for m in _lake_mats:
		m.set_shader_parameter(&"rain", rain)
	for d in _puddles:
		if is_instance_valid(d):
			var a2 := smoothstep(0.15, 0.6, wetness)
			d.visible = a2 > 0.01
			d.modulate = Color(1, 1, 1, a2)


func _on_time_tick(hour: float, day: int) -> void:
	if not auto_weather:
		return
	var gs: Node = get_node_or_null(^"/root/GameState")
	if gs != null and bool(gs.call(&"get_flag", &"weather_locked", false)):
		return
	# re-roll every 4 in-game hours, deterministically per day/slot
	var slot := int(hour / 4.0)
	if day == _last_auto_day and slot == _last_auto_slot:
		return
	var first := _last_auto_day < 0
	_last_auto_day = day
	_last_auto_slot = slot
	if first:
		return               # keep whatever the save/scene set on load
	var r := RandomNumberGenerator.new()
	r.seed = hash(Vector2i(day, slot))
	var roll := r.randf()
	var tod: Node = get_node_or_null(^"/root/TimeOfDay")
	var festival := tod != null and tod.has_method(&"is_festival_day") and bool(tod.call(&"is_festival_day"))
	var k: StringName
	if festival and hour > 14.0:
		k = &"clear"         # the festival night stays dry
	elif roll < 0.45:
		k = &"clear"
	elif roll < 0.68:
		k = &"cloudy"
	elif roll < 0.85:
		k = &"rain"
	elif roll < 0.93:
		k = &"storm"
	else:
		k = &"fog" if hour < 9.0 else &"cloudy"
	set_weather(k, r.randf_range(0.4, 1.0))


# --- rain particles -----------------------------------------------------------------------------

func _build_rain() -> void:
	_rain = GPUParticles3D.new()
	_rain.name = "Rain"
	_rain.amount = rain_amount
	_rain.lifetime = 1.6
	_rain.preprocess = 1.0
	_rain.fixed_fps = 0
	_rain.local_coords = false
	_rain.emitting = false
	_rain.visibility_aabb = AABB(Vector3(-rain_area, -30, -rain_area), Vector3(rain_area * 2, 45, rain_area * 2))
	_rain.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_rain.collision_base_size = 0.02
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(rain_area, 0.5, rain_area)
	pm.direction = Vector3.DOWN
	pm.spread = 2.0
	pm.initial_velocity_min = 11.0
	pm.initial_velocity_max = 13.0
	pm.gravity = Vector3(0, -4.0, 0)
	pm.particle_flag_align_y = true
	pm.collision_mode = ParticleProcessMaterial.COLLISION_HIDE_ON_CONTACT
	pm.collision_use_scale = false
	pm.sub_emitter_mode = ParticleProcessMaterial.SUB_EMITTER_AT_COLLISION
	pm.sub_emitter_amount_at_collision = 1
	_rain.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(1.0, 1.0)
	q.center_offset = Vector3(0, 0.5, 0)
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/rain_streak.gdshader")
	q.material = sm
	_rain.draw_pass_1 = q
	add_child(_rain)

	_splash = GPUParticles3D.new()
	_splash.name = "RainSplash"
	_splash.amount = 3000
	_splash.lifetime = 0.3
	_splash.local_coords = false
	_splash.emitting = false        # driven by the sub-emitter
	_splash.visibility_aabb = _rain.visibility_aabb
	_splash.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var spm := ParticleProcessMaterial.new()
	spm.gravity = Vector3.ZERO
	spm.initial_velocity_min = 0.0
	spm.initial_velocity_max = 0.0
	spm.scale_min = 0.06
	spm.scale_max = 0.12
	_splash.process_material = spm
	var sq := QuadMesh.new()
	sq.size = Vector2(1.0, 1.0)
	sq.center_offset = Vector3(0, 0.3, 0)
	var ssm := ShaderMaterial.new()
	ssm.shader = load("res://shaders/rain_splash.gdshader")
	sq.material = ssm
	_splash.draw_pass_1 = sq
	add_child(_splash)
	_rain.sub_emitter = _rain.get_path_to(_splash)

	_collision = GPUParticlesCollisionHeightField3D.new()
	_collision.name = "RainCollision"
	_collision.size = Vector3(rain_area * 2.0 + 4.0, 60.0, rain_area * 2.0 + 4.0)
	_collision.resolution = GPUParticlesCollisionHeightField3D.RESOLUTION_512
	_collision.update_mode = GPUParticlesCollisionHeightField3D.UPDATE_MODE_WHEN_MOVED
	_collision.follow_camera_enabled = true
	add_child(_collision)


func _follow_camera() -> void:
	if _rain == null or not _rain.emitting:
		return
	var vp := get_viewport()
	var cam := vp.get_camera_3d() if vp != null else null
	if cam == null:
		return
	var p := cam.global_position
	var fwd := -cam.global_basis.z
	fwd.y = 0.0
	_rain.global_position = Vector3(p.x, p.y + 14.0, p.z) + fwd.normalized() * 8.0
	_rain.sub_emitter = _rain.get_path_to(_splash)


# --- wet materials ------------------------------------------------------------------------------

func _collect() -> void:
	_wet_mats.clear()
	_puddles.clear()
	_lake_mats.clear()
	var root := get_parent()
	if root == null:
		return
	for n in get_tree().get_nodes_in_group(&"puddle_decal"):
		if n is Decal:
			_puddles.append(n)
	for n in get_tree().get_nodes_in_group(&"lake_water"):
		var gi := n as GeometryInstance3D
		if gi != null and gi.material_override is ShaderMaterial:
			_lake_mats.append(gi.material_override)
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for c in n.get_children():
			stack.append(c)
		var mi := n as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.get_active_material(i) as StandardMaterial3D
			if m == null or _wet_mats.has(m):
				continue
			var nm := m.resource_name
			if nm.begins_with("lit_") or nm.begins_with("glass") or m.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA:
				continue
			_wet_mats[m] = [m.albedo_color, m.roughness, m.metallic]
	_last_wet_applied = -1.0
	_apply_wet_materials(wetness, true)


func _apply_wet_materials(w: float, force: bool) -> void:
	if not force and absf(w - _last_wet_applied) < 0.015:
		return
	_last_wet_applied = w
	for m: StandardMaterial3D in _wet_mats.keys():
		if not is_instance_valid(m):
			continue
		var base: Array = _wet_mats[m]
		var porous := 1.0 - float(base[2]) * 0.7        # metals darken less
		var c: Color = base[0]
		var k := w * porous
		m.albedo_color = Color(c.r * lerpf(1.0, 0.62, k), c.g * lerpf(1.0, 0.62, k), c.b * lerpf(1.0, 0.64, k), c.a)
		var r0: float = base[1]
		m.roughness = lerpf(r0, r0 * 0.35 + 0.05, w)


func get_wet_material_count() -> int:
	return _wet_mats.size()
