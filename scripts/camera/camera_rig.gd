extends Node3D
## Cam's camera (owner: player): third-person orbit ⇄ first-person at the cat's eyes.
##
## * TPP: collision-aware orbit (SpringArm3D vs. world + camera_blocker), critically-damped follow
##   of the physics-interpolated cat, separate vertical lag (no bobbing on steps), auto-framing
##   of precision jumps (start → landing midpoint), zoom, speed-based FOV, gentle recentering
##   behind the cat while moving, subtle trauma-based shake on hard landings.
## * FPP: camera at the `fpp_eye` socket (BoneAttachment3D on the head), positionally stabilised
##   (body-relative low-pass) with a small gait-synchronised head-bob; near clip 0.015 m; the
##   player hides head/eyes/whiskers while the paws and chest stay visible when looking down.
## * Smooth animated blend between both (position, orientation, FOV, near plane).
## Mouse + gamepad look; sensitivity / invert from Settings (`controls/*`, `camera/*`).
## The rig is top-level (it does not inherit the cat's yaw).

signal mode_changed(mode: StringName)

const MODE_TPP := &"third_person"
const MODE_FPP := &"first_person"
const LAYER_WORLD := 1
const LAYER_CAMERA_BLOCKER := 1 << 8

@export var tpp_distance := 1.35
@export var tpp_min_distance := 0.6
@export var tpp_max_distance := 3.4
## Orbit pivot above the cat's feet (the cat is ~0.25 m tall).
@export var tpp_pivot_height := 0.27
@export var tpp_shoulder_offset := 0.0
@export_range(-89.0, 0.0) var pitch_min_tpp := -72.0
@export_range(0.0, 89.0) var pitch_max_tpp := 38.0
@export_range(-89.0, 0.0) var pitch_min_fpp := -84.0
@export_range(0.0, 89.0) var pitch_max_fpp := 78.0
## Follow time constants (seconds to cover ~63 % of the gap).
@export var follow_lag_horizontal := 0.055
@export var follow_lag_vertical := 0.11
@export var follow_lag_vertical_air := 0.22
@export var transition_time := 0.55
@export var fov_speed_boost := 7.0
@export var recenter_delay := 1.8
@export var recenter_rate := 1.1
@export var zoom_step := 0.25
@export var tpp_near := 0.04
@export var fpp_near := 0.015
@export var capture_mouse := true
@export var collision_mask: int = LAYER_WORLD | LAYER_CAMERA_BLOCKER

var yaw := 0.0
var pitch := deg_to_rad(-14.0)
var mode: StringName = MODE_TPP

var _player: Node3D = null
var _camera: Camera3D
var _arm: SpringArm3D
var _arm_end: Node3D
var _blend := 0.0          # 0 = TPP, 1 = FPP (eased)
var _blend_lin := 0.0      # linear 0..1 progress
var _blend_dir := 0.0
var _distance := 1.35
var _distance_target := 1.35
var _pivot := Vector3.ZERO
var _pivot_vel := Vector3.ZERO
var _initialized := false
var _look_idle := 10.0
var _trauma := 0.0
var _shake_t := 0.0
var _frame_jump := false
var _frame_from := Vector3.ZERO
var _frame_to := Vector3.ZERO
var _frame_amount := 0.0
var _fpp_smooth := Vector3.ZERO
var _fpp_init := false
var _fov_base := 75.0
var _fov_current := 75.0
var _mouse_sens := 0.25
var _pad_sens := 3.0
var _invert_y := false
var _head_bob := 1.0
var _input_enabled := true
var _menu_open := 0
var _noise := FastNoiseLite.new()


func _ready() -> void:
	set_as_top_level(true)
	top_level = true
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	_noise.seed = 7
	_noise.frequency = 6.0
	_arm = SpringArm3D.new()
	_arm.name = "SpringArm"
	var sph := SphereShape3D.new()
	sph.radius = 0.07
	_arm.shape = sph
	_arm.margin = 0.04
	_arm.collision_mask = collision_mask
	_arm.spring_length = tpp_distance
	add_child(_arm)
	_arm_end = Node3D.new()
	_arm_end.name = "ArmEnd"
	_arm.add_child(_arm_end)
	_camera = Camera3D.new()
	_camera.name = "Camera"
	_camera.near = tpp_near
	_camera.far = 900.0
	_camera.set_as_top_level(true)
	_camera.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	add_child(_camera)
	_distance = tpp_distance
	_distance_target = tpp_distance
	_read_settings()
	GameEvents.settings_changed.connect(_on_settings_changed)
	GameEvents.ui_menu_opened.connect(_on_menu_opened)
	GameEvents.ui_menu_closed.connect(_on_menu_closed)
	GameEvents.pause_requested.connect(_on_pause_requested)
	var default_mode := StringName(_setting("camera", "default_mode", "third_person"))
	if default_mode == MODE_FPP:
		set_mode(MODE_FPP, true)
	if capture_mouse and DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


## The CatPlayer (or any Node3D with the optional helper methods) this camera follows.
func set_target(player: Node3D) -> void:
	_player = player
	if _player != null:
		_arm.clear_excluded_objects()
		if _player is CollisionObject3D:
			_arm.add_excluded_object((_player as CollisionObject3D).get_rid())
		yaw = _player.global_rotation.y + PI
		snap_to_target()


func get_camera() -> Camera3D:
	return _camera


func is_first_person() -> bool:
	return mode == MODE_FPP


## 0 = fully third person, 1 = fully first person (eased, animated).
func get_fpp_blend() -> float:
	return _blend


func set_mode(new_mode: StringName, instant := false) -> void:
	if new_mode != MODE_FPP and new_mode != MODE_TPP:
		return
	var changed := new_mode != mode
	mode = new_mode
	_blend_dir = 1.0 if mode == MODE_FPP else -1.0
	if instant:
		_blend_lin = 1.0 if mode == MODE_FPP else 0.0
		_blend = _blend_lin
	if mode == MODE_FPP:
		pitch = clampf(pitch, deg_to_rad(pitch_min_fpp), deg_to_rad(pitch_max_fpp))
		_fpp_init = false
	if changed:
		mode_changed.emit(mode)
		GameEvents.camera_mode_changed.emit(mode)


func toggle_mode() -> void:
	set_mode(MODE_TPP if mode == MODE_FPP else MODE_FPP)


func set_input_enabled(enabled: bool) -> void:
	_input_enabled = enabled


## Horizontal basis of the view (for camera-relative movement): -Z = view forward.
func get_yaw_basis() -> Basis:
	return Basis(Vector3.UP, yaw)


func get_view_forward() -> Vector3:
	return -_camera.global_transform.basis.z


## World point under the screen centre (or Vector3.INF), used for precision jump aiming.
func get_aim_point(max_dist := 6.0, mask := 1 | (1 << 3) | (1 << 5) | (1 << 7)) -> Vector3:
	if not is_inside_tree():
		return Vector3.INF
	var from := _camera.global_position
	var dir := -_camera.global_transform.basis.z
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * (max_dist + _distance * (1.0 - _blend)), mask)
	if _player is CollisionObject3D:
		q.exclude = [(_player as CollisionObject3D).get_rid()]
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	return hit["position"] if not hit.is_empty() else Vector3.INF


## Shake trauma 0..1 (squared falloff → subtle for small values).
func add_trauma(amount: float) -> void:
	_trauma = clampf(_trauma + amount, 0.0, 1.0)


## Frame a precision jump: the follow target leans towards the jump midpoint until landing.
func frame_jump(from: Vector3, to: Vector3) -> void:
	_frame_jump = true
	_frame_from = from
	_frame_to = to


func end_frame_jump() -> void:
	_frame_jump = false


func snap_to_target() -> void:
	if _player == null:
		return
	_pivot = _target_pivot()
	_pivot_vel = Vector3.ZERO
	_initialized = true
	_fpp_init = false
	_update_camera(0.0)


func _unhandled_input(event: InputEvent) -> void:
	if not _input_enabled or _menu_open > 0:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var mm := event as InputEventMouseMotion
		var s := deg_to_rad(_mouse_sens) * 0.6
		yaw -= mm.relative.x * s
		pitch -= mm.relative.y * s * (-1.0 if _invert_y else 1.0)
		_clamp_pitch()
		_look_idle = 0.0
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed and capture_mouse:
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED and DisplayServer.get_name() != "headless":
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _process(delta: float) -> void:
	if _player == null or not is_instance_valid(_player):
		return
	if not _initialized:
		snap_to_target()
	_handle_actions(delta)
	_update_camera(delta)


func _handle_actions(delta: float) -> void:
	if not _input_enabled or _menu_open > 0:
		return
	var look := Input.get_vector(&"look_left", &"look_right", &"look_up", &"look_down")
	if look.length() > 0.02:
		# response curve: fine aim near the centre, fast turns at full deflection
		var mag := look.length()
		var curved := look.normalized() * pow(mag, 1.6)
		yaw -= curved.x * _pad_sens * delta
		pitch -= curved.y * _pad_sens * 0.7 * delta * (-1.0 if _invert_y else 1.0)
		_clamp_pitch()
		_look_idle = 0.0
	else:
		_look_idle += delta
	if mode == MODE_TPP:
		if Input.is_action_just_pressed(&"zoom_in"):
			_distance_target = maxf(tpp_min_distance, _distance_target - zoom_step)
		if Input.is_action_just_pressed(&"zoom_out"):
			_distance_target = minf(tpp_max_distance, _distance_target + zoom_step)


func _clamp_pitch() -> void:
	var lo := lerpf(pitch_min_tpp, pitch_min_fpp, _blend)
	var hi := lerpf(pitch_max_tpp, pitch_max_fpp, _blend)
	if mode == MODE_FPP:
		lo = pitch_min_fpp
		hi = pitch_max_fpp
	pitch = clampf(pitch, deg_to_rad(lo), deg_to_rad(hi))


func _target_pivot() -> Vector3:
	var xf := _player.get_global_transform_interpolated()
	var p := xf.origin + Vector3.UP * tpp_pivot_height
	if _player.has_method(&"get_camera_focus_offset"):
		p += _player.call(&"get_camera_focus_offset")
	return p


func _update_camera(delta: float) -> void:
	# --- mode blend ----------------------------------------------------------------------
	if _blend_dir != 0.0 and delta > 0.0:
		_blend_lin = clampf(_blend_lin + _blend_dir * delta / maxf(transition_time, 0.01), 0.0, 1.0)
		if _blend_lin <= 0.0 or _blend_lin >= 1.0:
			_blend_dir = 0.0
	_blend = _blend_lin * _blend_lin * (3.0 - 2.0 * _blend_lin)
	var moving_speed := 0.0
	var airborne := false
	if _player.has_method(&"get_planar_speed"):
		moving_speed = float(_player.call(&"get_planar_speed"))
	if _player.has_method(&"is_airborne"):
		airborne = bool(_player.call(&"is_airborne"))

	# --- recentering (only while moving, after the player stopped looking) -----------------
	if mode == MODE_TPP and _look_idle > recenter_delay and moving_speed > 0.4 and delta > 0.0:
		var behind := _player.global_rotation.y + PI
		var diff := angle_difference(yaw, behind)
		var rate := recenter_rate * clampf(moving_speed / 2.0, 0.25, 1.0)
		yaw += clampf(diff, -rate * delta, rate * delta) * smoothstep(0.05, 0.6, absf(diff))
		var pitch_goal := deg_to_rad(-14.0)
		pitch = lerpf(pitch, pitch_goal, 1.0 - exp(-0.6 * delta))
	_clamp_pitch()

	# --- follow pivot (critically damped, split horizontal / vertical lag) ---------------
	var goal := _target_pivot()
	if _frame_jump:
		_frame_amount = move_toward(_frame_amount, 1.0, delta * 3.0)
	else:
		_frame_amount = move_toward(_frame_amount, 0.0, delta * 2.5)
	if _frame_amount > 0.0:
		var mid := (_frame_from + _frame_to) * 0.5 + Vector3.UP * tpp_pivot_height
		var framed := goal.lerp(mid, 0.45)
		framed.y = maxf(goal.y, mid.y) if _frame_to.y > _frame_from.y else lerpf(goal.y, mid.y, 0.4)
		goal = goal.lerp(framed, _frame_amount * (1.0 - _blend))
	if delta > 0.0:
		var lag_v := follow_lag_vertical_air if airborne else follow_lag_vertical
		var kh := 1.0 - exp(-delta / maxf(follow_lag_horizontal, 0.001))
		var kv := 1.0 - exp(-delta / maxf(lag_v, 0.001))
		var new_pivot := Vector3(lerpf(_pivot.x, goal.x, kh), lerpf(_pivot.y, goal.y, kv), lerpf(_pivot.z, goal.z, kh))
		# never lag more than 0.6 m (teleports, fast falls)
		if new_pivot.distance_to(goal) > 0.6:
			new_pivot = goal + (new_pivot - goal).limit_length(0.6)
		_pivot = new_pivot
	global_position = _pivot

	# --- TPP pose via the spring arm --------------------------------------------------------
	_distance = lerpf(_distance, _distance_target + _frame_amount * 0.35, 1.0 - exp(-8.0 * maxf(delta, 0.0)))
	_arm.spring_length = _distance
	# the lagged/shoulder-offset arm origin can sit inside a wall, where the arm's sweep cannot see
	# it: pull the origin back along the ray from the cat's real pivot
	var arm_origin := _pivot + _arm_side()
	var real := _target_pivot()
	var oq := PhysicsRayQueryParameters3D.create(real, arm_origin, collision_mask)
	var ohit := get_world_3d().direct_space_state.intersect_ray(oq)
	if not ohit.is_empty():
		arm_origin = real + (ohit["position"] - real).limit_length(maxf(real.distance_to(ohit["position"]) - 0.12, 0.0))
	_arm.global_transform = Transform3D(Basis.from_euler(Vector3(pitch, yaw, 0.0)), arm_origin)
	_arm.force_update_transform()
	var tpp_xf := Transform3D(_arm.global_transform.basis, _arm.global_position + _arm.global_transform.basis.z * _arm.get_hit_length())

	# --- FPP pose at the eyes ------------------------------------------------------------------
	var fpp_xf := tpp_xf
	if _player.has_method(&"get_eye_transform_interpolated"):
		var eye: Transform3D = _player.call(&"get_eye_transform_interpolated")
		var body_xf := _player.get_global_transform_interpolated()
		var local := body_xf.affine_inverse() * eye.origin
		if not _fpp_init or delta <= 0.0:
			_fpp_smooth = local
			_fpp_init = true
		else:
			# body-relative low-pass: keeps the view stable while the head bobs in the clip
			_fpp_smooth = _fpp_smooth.lerp(local, 1.0 - exp(-delta * 14.0))
		var bob := Vector3.ZERO
		if _player.has_method(&"get_gait_phase"):
			var ph: float = _player.call(&"get_gait_phase")
			var amp := clampf(moving_speed / 2.0, 0.0, 1.0) * 0.006 * _head_bob
			bob = Vector3(sin(ph * TAU) * amp * 0.5, absf(sin(ph * TAU)) * amp, 0.0)
		# looking down the cat tucks its chin: the eyes drop and pull back over the forepaws, so
		# the paws and chest come into view instead of the floor a body-length ahead
		var dip := smoothstep(deg_to_rad(35.0), deg_to_rad(80.0), -pitch)
		var tuck := Basis(Vector3.UP, yaw) * Vector3(0.0, -0.055 * dip, 0.045 * dip)
		var p := body_xf * (_fpp_smooth) + Basis(Vector3.UP, yaw) * bob + tuck
		fpp_xf = Transform3D(Basis.from_euler(Vector3(pitch, yaw, 0.0)), p)

	# --- blend --------------------------------------------------------------------------------
	var xf := tpp_xf
	if _blend > 0.0:
		var q := tpp_xf.basis.get_rotation_quaternion().slerp(fpp_xf.basis.get_rotation_quaternion(), _blend)
		# arc the position slightly upwards mid-transition so it never cuts through the body
		var pos := tpp_xf.origin.lerp(fpp_xf.origin, _blend)
		pos += Vector3.UP * sin(_blend * PI) * 0.06
		xf = Transform3D(Basis(q), pos)

	# --- shake --------------------------------------------------------------------------------
	if _trauma > 0.0 and delta > 0.0:
		_shake_t += delta
		var s := _trauma * _trauma
		var rot := Vector3(_noise.get_noise_2d(_shake_t * 60.0, 0.0), _noise.get_noise_2d(0.0, _shake_t * 60.0), _noise.get_noise_2d(_shake_t * 60.0, 50.0)) * s
		xf.basis = xf.basis * Basis.from_euler(rot * Vector3(0.05, 0.05, 0.03))
		xf.origin += xf.basis * Vector3(rot.y, rot.x, 0.0) * 0.015 * (1.0 - _blend * 0.6)
		_trauma = maxf(0.0, _trauma - delta * 1.6)
	_camera.global_transform = xf

	# --- lens -----------------------------------------------------------------------------------
	var fov_tpp := _fov_base + fov_speed_boost * clampf((moving_speed - 1.8) / 3.0, 0.0, 1.0)
	var fov_fpp := maxf(_fov_base + 5.0, 80.0) + fov_speed_boost * 0.8 * clampf((moving_speed - 1.8) / 3.0, 0.0, 1.0)
	var fov_goal := lerpf(fov_tpp, fov_fpp, _blend)
	_fov_current = lerpf(_fov_current, fov_goal, 1.0 - exp(-6.0 * maxf(delta, 0.0))) if delta > 0.0 else fov_goal
	_camera.fov = _fov_current
	_camera.near = lerpf(tpp_near, fpp_near, _blend)
	if _player.has_method(&"set_first_person_amount"):
		_player.call(&"set_first_person_amount", _blend, _camera.global_position)


func _arm_side() -> Vector3:
	if tpp_shoulder_offset == 0.0:
		return Vector3.ZERO
	return Basis(Vector3.UP, yaw) * Vector3(tpp_shoulder_offset, 0.0, 0.0) * (1.0 - _blend)


# --- settings ---------------------------------------------------------------------------------

func _setting(section: String, key: String, default: Variant) -> Variant:
	var s := get_node_or_null(^"/root/Settings")
	if s != null and s.has_method(&"get_value"):
		var v: Variant = s.call(&"get_value", section, key, default)
		return default if v == null else v
	return default


func _read_settings() -> void:
	_fov_base = float(_setting("graphics", "fov", 75.0))
	_mouse_sens = float(_setting("controls", "mouse_sensitivity", 0.25))
	_pad_sens = float(_setting("controls", "gamepad_sensitivity", 3.0))
	_invert_y = bool(_setting("controls", "invert_y", false))
	_head_bob = float(_setting("camera", "head_bob", 1.0))


func _on_settings_changed(_section: StringName) -> void:
	_read_settings()


func _on_menu_opened(_menu: StringName) -> void:
	_menu_open += 1
	if DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _on_menu_closed(_menu: StringName) -> void:
	_menu_open = maxi(0, _menu_open - 1)
	if _menu_open == 0 and capture_mouse and DisplayServer.get_name() != "headless":
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _on_pause_requested(paused: bool) -> void:
	if paused:
		_on_menu_opened(&"pause")
	else:
		_on_menu_closed(&"pause")
