class_name CatPlayer
extends CharacterBody3D
## Cam, the orange tabby (owner: player). Contract: CLAUDE.md "Player".
##
## Physics proxy: a vertical cylinder (Jolt) — flat bottom so the cat stands perfectly still on
## ledge lips, beams and cables (no rounded-bottom edge jitter), rotation-invariant so turning in
## tight alleys never pushes the cat around. The long body is handled by probes: a nose probe
## stops the head before walls, an edge guard keeps a walking cat from stepping off big drops,
## step-up climbs kerbs/stairs ≤ max_step_height with a smoothed visual, and the visual node is
## pitched/rolled to the ground under the front and hind paws.
##
## Modes: GROUND (idle/walk/trot/run/sneak/balance/crawl/land), CROUCH (jump charge + precision
## targeting), AIR (analytic parabola for targeted leaps / free ballistic), SCRAMBLE (ledge mantle),
## CLIMB (layer-6 surfaces), SWIM (water: splash, paddle to the edge, wet fur), TURN (turn-in-place
## clips), ACTION (one-shot full-body actions), REST (sit/groom/lie/sleep sequences).
##
## Everything the world needs goes through GameEvents (player_state_changed, player_landed,
## player_jumped, player_noise, player_meowed, interactable_*, item_dropped, ...).

signal state_changed(old_state: StringName, new_state: StringName)
signal landed(impact_speed: float, fall_height: float)
signal leapt(targeted: bool, target: Vector3)

const JumpPlanner := preload("res://scripts/player/jump_planner.gd")
const CatAnimatorScript := preload("res://scripts/player/cat_animator.gd")
const CatInteractionScript := preload("res://scripts/player/cat_interaction.gd")
const FurShellsScript := preload("res://scripts/player/fur_shells.gd")

const MODEL_PATH := "res://assets/models/cat/cat.glb"

enum Mode { GROUND, CROUCH, AIR, SCRAMBLE, CLIMB, SWIM, TURN, ACTION, REST }

const L_WORLD := 1
const L_PLAYER := 1 << 1
const L_NPC := 1 << 2
const L_PROPS := 1 << 3
const L_INTERACT := 1 << 4
const L_CLIMB := 1 << 5
const L_WATER := 1 << 6
const L_VEHICLE := 1 << 7
const L_CAMERA_BLOCK := 1 << 8
## Solid things the cat stands on / bumps into (water excluded: handled as a volume).
const SOLID_MASK := L_WORLD | L_PROPS | L_CLIMB | L_VEHICLE
const MOVE_MASK := L_WORLD | L_PROPS | L_CLIMB | L_WATER | L_VEHICLE

@export_group("Gaits (m/s)")
@export var sneak_speed := 0.45
@export var walk_speed := 0.7
@export var trot_speed := 1.9
@export var run_speed := 5.0
@export var balance_speed := 0.42
@export var crawl_speed := 0.32
@export var swim_speed := 0.55
@export var climb_speed := 0.85
@export var carry_speed_mult := 0.92
@export_group("Acceleration")
@export var accel := 6.5
@export var run_accel := 8.5
@export var decel := 9.0
@export var brake_decel := 14.0
@export var air_control := 2.2
@export_group("Turning (rad/s)")
@export var turn_rate_slow := 7.5
@export var turn_rate_fast := 3.0
@export var turn_in_place_deg := 75.0
@export_group("Body")
@export var body_radius := 0.085
@export var body_height := 0.22
@export var crawl_height := 0.135
@export var max_step_height := 0.18
@export var nose_reach := 0.24
@export var edge_guard_drop := 0.9
@export_group("Jump")
@export var gravity := 14.0
@export var fall_gravity_mult := 1.12
@export var max_fall_speed := 16.0
@export var max_jump_height := 1.6
@export var max_jump_distance := 2.5
@export var free_jump_height := Vector2(0.28, 0.85)
@export var free_jump_push := Vector2(0.8, 2.3)
@export var charge_time := 0.55
@export var tap_time := 0.16
@export var coyote_time := 0.12
@export var jump_buffer_time := 0.15
@export var hard_land_height := 2.0
@export var max_scramble_height := 0.55
@export_group("Swim")
@export var swim_depth := 0.13
@export_group("Idle behaviour (s)")
@export var idle_look_after := 9.0
@export var idle_sit_after := 22.0
@export var idle_groom_after := 40.0
@export var idle_lie_after := 65.0
@export var idle_sleep_after := 95.0
@export_group("Visual")
@export var load_model := true
@export var create_camera := true

var state: StringName = &"idle"
var mode: Mode = Mode.GROUND

# --- nodes --------------------------------------------------------------------------------
var _shape_node: CollisionShape3D
var _shape: CylinderShape3D
var _visual: Node3D
var _model: Node3D
var _camera_rig: Node3D
var _anim: Node = null
var _interaction: Node = null
var _fur: Node = null
var _sense: Node = null
var _fx: Node3D = null
var _reticle: Node3D = null
var _mouth_attach: Node3D
var _eye_attach: Node3D
var _look_target: Node3D
var _held_visual: Node3D = null
var _planner: JumpPlanner
var _ray := PhysicsRayQueryParameters3D.new()
var _shape_q := PhysicsShapeQueryParameters3D.new()
var _point_q := PhysicsPointQueryParameters3D.new()

# --- input --------------------------------------------------------------------------------
var _input_enabled := true
var _dialogue_lock := false
var _move_input := Vector2.ZERO        # x right, y forward (analog)
var _move_dir := Vector3.ZERO          # world, length = analog magnitude
var _sprint_latched := false
var _sprint_release_t := 0.0
var _sneak_toggle := false
var _jump_down_t := -1.0               # seconds the jump button has been held (-1 = up)
var _jump_released_hold := 0.0
var _jump_buffer_t := 0.0
var _meow_t := -1.0
var _meow_loud_done := false
var _sit_t := -1.0
var _sit_hold_done := false
var _idle_t := 0.0

# --- motion state -------------------------------------------------------------------------
var _yaw := 0.0
var _yaw_rate := 0.0
var _speed := 0.0                      # signed speed along facing
var _time_since_ground := 0.0
var _ground_normal := Vector3.UP
var _floor_collider: Object = null
var _surface: StringName = &"concrete"
var _sneaking := false
var _crawling := false
var _balancing := false
var _balance_offset := 0.0
var _balance_yaw_err := 0.0
var _support_narrow_t := 0.0
var _land_t := 0.0
var _action_t := 0.0
var _action_len := 0.0
var _action_cancel_after := 99.0
var _action_name: StringName = &""
var _rest_phase: StringName = &""
var _rest_t := 0.0
var _rest_len := 0.0
var _rest_next: StringName = &""
var _turn_from := 0.0
var _turn_to := 0.0
var _turn_t := 0.0
var _turn_len := 0.5
var _charge := 0.0
var _target: Dictionary = {}
var _planner_tick := 0
var _air_targeted := false
var _air_t := 0.0
var _air_p0 := Vector3.ZERO
var _air_v0 := Vector3.ZERO
var _air_T := 0.0
var _air_apex_y := 0.0
var _air_from_jump := false
var _prev_velocity := Vector3.ZERO
var _scr_from := Vector3.ZERO
var _scr_to := Vector3.ZERO
var _scr_t := 0.0
var _scr_len := 0.4
var _scr_dir := Vector3.FORWARD
var _scr_exit_mode: Mode = Mode.GROUND
var _climb_normal := Vector3.BACK
var _climb_intent := 0.0
var _climb_cooldown := 0.0
var _water_level := -INF
var _in_water_volume := false
var _swim_t := 0.0
var _noise_t := 0.0
var _gait_phase := 0.0
var _step_count := 0
var _wet_drip_t := 0.0
var _face_goal := 0.0
var _face_active := false
var _refuse_t := 0.0
var _shelter_t := 0.0
var _sheltered := false

# --- visual state -------------------------------------------------------------------------
var _vis_pitch := 0.0
var _vis_roll := 0.0
var _vis_offset_y := 0.0
var _step_offset := 0.0
var _vis_climb := 0.0                  # 0..1 blend to the climbing orientation
var _vis_swim := 0.0
var _fpp_amount := 0.0
var _probe_front := -INF
var _probe_back := -INF
var _probe_left := -INF
var _probe_right := -INF
var _probe_center := -INF


func _ready() -> void:
	add_to_group(&"player")
	collision_layer = L_PLAYER
	collision_mask = MOVE_MASK
	safe_margin = 0.002
	floor_snap_length = max_step_height + 0.03
	floor_max_angle = deg_to_rad(48.0)
	floor_constant_speed = true
	floor_block_on_wall = true
	floor_stop_on_slope = true
	max_slides = 5
	wall_min_slide_angle = deg_to_rad(10.0)
	platform_on_leave = CharacterBody3D.PLATFORM_ON_LEAVE_ADD_UPWARD_VELOCITY
	_setup_shape()
	_setup_visual()
	_setup_helpers()
	_yaw = global_rotation.y
	_apply_yaw()
	_ray.collide_with_areas = false
	_ray.exclude = [get_rid()]
	_shape_q.exclude = [get_rid()]
	_point_q.collide_with_areas = true
	_point_q.collide_with_bodies = false
	_point_q.collision_mask = L_WATER
	GameEvents.dialogue_started.connect(_on_dialogue_started)
	GameEvents.dialogue_ended.connect(_on_dialogue_ended)
	GameEvents.dialogue_choice_made.connect(_on_dialogue_choice)
	GameEvents.mouth_item_changed.connect(_on_mouth_item_changed)
	GameEvents.player_fainted.connect(_on_fainted)
	GameEvents.player_revived.connect(_on_revived)
	_announce_spawn.call_deferred()


func _announce_spawn() -> void:
	if not is_inside_tree():
		return
	GameEvents.player_spawned.emit(self)
	if GameState.mouth_item != &"":
		_on_mouth_item_changed(GameState.mouth_item)


# =============================================================================================
# Setup
# =============================================================================================

func _setup_shape() -> void:
	_shape_node = get_node_or_null(^"BodyShape") as CollisionShape3D
	if _shape_node == null:
		_shape_node = CollisionShape3D.new()
		_shape_node.name = "BodyShape"
		add_child(_shape_node)
	_shape = CylinderShape3D.new()   # unique per instance (crawl changes its height)
	_shape.radius = body_radius
	_shape.height = body_height
	_shape_node.shape = _shape
	_shape_node.position = Vector3(0.0, body_height * 0.5, 0.0)


func _setup_visual() -> void:
	_visual = get_node_or_null(^"Visual") as Node3D
	if _visual == null:
		_visual = Node3D.new()
		_visual.name = "Visual"
		add_child(_visual)
	_model = _visual.get_node_or_null(^"Model") as Node3D
	if _model == null and load_model and ResourceLoader.exists(MODEL_PATH):
		var ps := load(MODEL_PATH) as PackedScene
		if ps != null:
			_model = ps.instantiate() as Node3D
			_model.name = "Model"
			_visual.add_child(_model)
	_look_target = Node3D.new()
	_look_target.name = "LookTarget"
	_look_target.top_level = true
	add_child(_look_target)
	# sockets: real bones when the model exists, rest-pose markers otherwise
	_mouth_attach = Node3D.new()
	_mouth_attach.name = "MouthFallback"
	_mouth_attach.position = Vector3(0.0, 0.215, 0.205)
	_visual.add_child(_mouth_attach)
	_eye_attach = Node3D.new()
	_eye_attach.name = "EyeFallback"
	_eye_attach.position = Vector3(0.0, 0.255, 0.20)
	_visual.add_child(_eye_attach)
	if _model != null:
		_anim = CatAnimatorScript.new()
		_anim.name = "Animator"
		add_child(_anim)
		if _anim.call(&"setup", _model, self):
			var m: Node3D = _anim.call(&"get_mouth_socket")
			if m != null:
				_mouth_attach = m
			var e: Node3D = _anim.call(&"get_eye_socket")
			if e != null:
				_eye_attach = e
		_fur = FurShellsScript.new()
		_fur.name = "Fur"
		add_child(_fur)
		_fur.call(&"attach_to_model", _model, self)


func _setup_helpers() -> void:
	_planner = JumpPlanner.new()
	_interaction = CatInteractionScript.new()
	_interaction.name = "Interaction"
	add_child(_interaction)
	_camera_rig = get_node_or_null(^"CameraRig") as Node3D
	if _camera_rig == null and create_camera:
		_camera_rig = (load("res://scripts/camera/camera_rig.gd") as GDScript).new() as Node3D
		_camera_rig.name = "CameraRig"
		add_child(_camera_rig)
	if _camera_rig != null:
		_camera_rig.call(&"set_target", self)
	_reticle = get_node_or_null(^"JumpReticle") as Node3D
	if _reticle == null and ResourceLoader.exists("res://scripts/player/jump_reticle.gd"):
		_reticle = (load("res://scripts/player/jump_reticle.gd") as GDScript).new() as Node3D
		_reticle.name = "JumpReticle"
		add_child(_reticle)
	_fx = get_node_or_null(^"FX") as Node3D
	if _fx == null and ResourceLoader.exists("res://scripts/player/cat_fx.gd"):
		_fx = (load("res://scripts/player/cat_fx.gd") as GDScript).new() as Node3D
		_fx.name = "FX"
		add_child(_fx)
	_sense = get_node_or_null(^"CatSense")
	if _sense == null and ResourceLoader.exists("res://scripts/player/cat_sense.gd"):
		_sense = (load("res://scripts/player/cat_sense.gd") as GDScript).new()
		_sense.name = "CatSense"
		add_child(_sense)


# =============================================================================================
# Public API (contract)
# =============================================================================================

func set_input_enabled(enabled: bool) -> void:
	_input_enabled = enabled
	if not enabled:
		_jump_down_t = -1.0
		_meow_t = -1.0
		_sit_t = -1.0
		_hide_reticle()
		if mode == Mode.CROUCH:
			_enter_ground()
	if _camera_rig != null:
		_camera_rig.call(&"set_input_enabled", enabled)


func is_input_enabled() -> bool:
	return _input_enabled and not _dialogue_lock


func teleport(xform: Transform3D) -> void:
	var fwd := xform.basis.z
	fwd.y = 0.0
	_yaw = atan2(fwd.x, fwd.z) if fwd.length_squared() > 0.0001 else 0.0
	global_transform = Transform3D(Basis(Vector3.UP, _yaw), xform.origin)
	velocity = Vector3.ZERO
	_speed = 0.0
	_step_offset = 0.0
	_vis_offset_y = 0.0
	_target = {}
	_hide_reticle()
	_set_crawl(false)
	if mode != Mode.REST:
		_enter_ground()
	reset_physics_interpolation()
	if _camera_rig != null:
		_camera_rig.yaw = _yaw + PI
		_camera_rig.call(&"snap_to_target")


func get_camera_rig() -> Node3D:
	return _camera_rig


func get_camera() -> Camera3D:
	return _camera_rig.call(&"get_camera") if _camera_rig != null else null


func get_mouth_attachment() -> Node3D:
	return _mouth_attach


func get_state() -> StringName:
	return state


func is_first_person() -> bool:
	return _camera_rig != null and bool(_camera_rig.call(&"is_first_person"))


func set_camera_mode(new_mode: StringName) -> void:
	if _camera_rig != null:
		_camera_rig.call(&"set_mode", new_mode)


func toggle_camera() -> void:
	if _camera_rig != null:
		_camera_rig.call(&"toggle_mode")


# --- helpers used by camera / animator / fur ------------------------------------------------

func get_planar_speed() -> float:
	return Vector2(velocity.x, velocity.z).length()


func get_speed_along_facing() -> float:
	return _speed


func is_airborne() -> bool:
	return mode == Mode.AIR


func is_sneaking() -> bool:
	return _sneaking or _crawling


func is_crawling() -> bool:
	return _crawling


func is_balancing() -> bool:
	return _balancing


func get_mode() -> Mode:
	return mode


func get_charge() -> float:
	return _charge


func get_jump_target() -> Dictionary:
	return _target


func get_climb_normal() -> Vector3:
	return _climb_normal


func get_surface() -> StringName:
	return _surface


func get_water_level() -> float:
	return _water_level


func get_yaw_rate() -> float:
	return _yaw_rate


func get_visual() -> Node3D:
	return _visual


func get_model() -> Node3D:
	return _model


func get_animator() -> Node:
	return _anim


func get_look_target() -> Node3D:
	return _look_target


func get_ground_heights() -> Dictionary:
	return {"front": _probe_front, "back": _probe_back, "left": _probe_left, "right": _probe_right, "center": _probe_center}


func get_gait_phase() -> float:
	if _anim != null and _anim.has_method(&"get_gait_phase"):
		return float(_anim.call(&"get_gait_phase"))
	return _gait_phase


func get_turn_duration() -> float:
	return _turn_len


## Turn to face a world point (used when interacting): eased over the next ticks.
func face_point(p: Vector3) -> void:
	var to := Vector3(p.x - global_position.x, 0.0, p.z - global_position.z)
	if to.length_squared() < 0.0004:
		return
	_face_goal = atan2(to.x, to.z)
	_face_active = true


## The focused interactable refused (locked / requirement not met): a small complaint.
func on_interaction_refused(_target: Node) -> void:
	if _refuse_t <= 0.0:
		_refuse_t = 1.2
		_play_sfx(&"cat_meow_complain", global_position + Vector3.UP * 0.22, -6.0)


func get_camera_focus_offset() -> Vector3:
	var off := Vector3.ZERO
	if _crawling:
		off.y -= 0.06
	if mode == Mode.CLIMB:
		off.y += 0.12
	elif mode == Mode.SWIM:
		off.y -= swim_depth * 0.7
	elif mode == Mode.REST and (_rest_phase == &"lie" or _rest_phase == &"sleep" or _rest_phase == &"lie_down"):
		off.y -= 0.08
	return off


## Eye socket, expressed relative to the physics-interpolated body (for a jitter-free FPP camera).
func get_eye_transform_interpolated() -> Transform3D:
	var rel := global_transform.affine_inverse() * _eye_attach.global_transform
	return get_global_transform_interpolated() * rel


## Called by the camera every frame: 0 = TPP, 1 = FPP. Hides head/eyes/whiskers near the camera.
func set_first_person_amount(amount: float, cam_pos: Vector3) -> void:
	_fpp_amount = amount
	if _fur != null:
		_fur.call(&"set_first_person", amount, cam_pos, _eye_attach.global_position)
	if _anim != null:
		_anim.call(&"set_first_person", amount)


# =============================================================================================
# Main loop
# =============================================================================================

func _physics_process(delta: float) -> void:
	_read_input(delta)
	_probe_water()
	match mode:
		Mode.GROUND:
			_physics_ground(delta)
		Mode.CROUCH:
			_physics_crouch(delta)
		Mode.AIR:
			_physics_air(delta)
		Mode.SCRAMBLE:
			_physics_scramble(delta)
		Mode.CLIMB:
			_physics_climb(delta)
		Mode.SWIM:
			_physics_swim(delta)
		Mode.TURN:
			_physics_turn(delta)
		Mode.ACTION:
			_physics_action(delta)
		Mode.REST:
			_physics_rest(delta)
	_handle_actions(delta)
	_update_visual(delta)
	_update_look_target()
	_update_gait_phase(delta)
	_update_shelter(delta)
	_prev_velocity = velocity
	RenderingServer.global_shader_parameter_set(&"player_position", global_position)


## Rain-on-tin ambience under awnings: GameState resolves the "shelter" areas, AudioManager mixes.
func _update_shelter(delta: float) -> void:
	_shelter_t -= delta
	if _shelter_t > 0.0:
		return
	_shelter_t = 0.3
	var sh := GameState.is_sheltered()
	if sh == _sheltered:
		return
	_sheltered = sh
	var am := get_node_or_null(^"/root/AudioManager")
	if am != null and am.has_method(&"set_sheltered"):
		am.call(&"set_sheltered", sh)


# =============================================================================================
# Input
# =============================================================================================

func _read_input(delta: float) -> void:
	if not is_input_enabled():
		_move_input = Vector2.ZERO
		_move_dir = Vector3.ZERO
		_jump_down_t = -1.0
		return
	var v := Input.get_vector(&"move_left", &"move_right", &"move_back", &"move_forward")
	_move_input = v
	var basis := Basis(Vector3.UP, _yaw + PI)
	if _camera_rig != null:
		basis = _camera_rig.call(&"get_yaw_basis")
	var fwd := -basis.z
	var right := basis.x
	_move_dir = (right * v.x + fwd * v.y)
	_move_dir.y = 0.0
	if _move_dir.length() > 1.0:
		_move_dir = _move_dir.normalized()
	# sprint: hold, or click-latched on gamepads until the stick is released
	if Input.is_action_just_pressed(&"sprint"):
		_sprint_latched = true
		_sneak_toggle = false
	if _move_input.length() < 0.2:
		_sprint_release_t += delta
		if _sprint_release_t > 0.3:
			_sprint_latched = false
	else:
		_sprint_release_t = 0.0
	if Input.is_action_just_pressed(&"sneak"):
		_sneak_toggle = not _sneak_toggle
		_sprint_latched = false
	# jump hold timer
	if Input.is_action_just_pressed(&"jump"):
		_jump_down_t = 0.0
	elif Input.is_action_pressed(&"jump"):
		if _jump_down_t >= 0.0:
			_jump_down_t += delta
	elif _jump_down_t >= 0.0:
		_jump_released_hold = _jump_down_t
		_jump_down_t = -1.0
	if v.length() > 0.1 or Input.is_action_pressed(&"jump") or Input.is_action_pressed(&"meow"):
		_idle_t = 0.0
	else:
		_idle_t += delta
	if Input.is_action_just_pressed(&"toggle_camera"):
		toggle_camera()


func _wants_sprint() -> bool:
	return is_input_enabled() and (_sprint_latched or Input.is_action_pressed(&"sprint")) and _move_input.length() > 0.3


func _jump_just_pressed() -> bool:
	return is_input_enabled() and Input.is_action_just_pressed(&"jump")


func _jump_just_released() -> bool:
	return is_input_enabled() and Input.is_action_just_released(&"jump")


func _aiming() -> bool:
	return is_input_enabled() and Input.is_action_pressed(&"aim_jump")


# =============================================================================================
# Ground locomotion
# =============================================================================================

func _physics_ground(delta: float) -> void:
	_time_since_ground = 0.0
	_land_t = maxf(0.0, _land_t - delta)
	_climb_cooldown = maxf(0.0, _climb_cooldown - delta)
	_probe_ground()
	_update_support(delta)
	_sneaking = _sneak_toggle and not _wants_sprint()
	_update_crawl()
	var mag := _move_dir.length()
	var target_speed := 0.0
	if mag > 0.08:
		target_speed = _gait_target_speed(mag)
	if state == &"land_hard":
		target_speed *= 0.0 if _land_t > 0.25 else 0.4
	elif state == &"land":
		target_speed *= 0.6
	# --- turning -----------------------------------------------------------------------
	var prev_yaw := _yaw
	if mag > 0.08:
		var desired := atan2(_move_dir.x, _move_dir.z)
		var diff := angle_difference(_yaw, desired)
		if absf(_speed) < 0.15 and absf(diff) > deg_to_rad(turn_in_place_deg) and _land_t <= 0.0 and not _balancing:
			_enter_turn(desired)
			return
		var t := clampf(absf(_speed) / run_speed, 0.0, 1.0)
		var rate := lerpf(turn_rate_slow, turn_rate_fast, sqrt(t))
		if _balancing:
			rate = 2.2
		# sharp reversal while fast: brake hard and pivot
		if absf(diff) > deg_to_rad(110.0) and _speed > trot_speed * 0.8:
			target_speed = 0.0
			rate *= 1.4
		_yaw += clampf(diff, -rate * delta, rate * delta)
		# speed falls off while the body is still pointing away from the input
		target_speed *= clampf(cos(diff) * 1.2, 0.15, 1.0)
	elif is_first_person() and absf(_speed) < 0.1 and _land_t <= 0.0 and not _balancing and _camera_rig != null:
		# first person, standing: the body follows the view once the neck can't turn further
		var view: Vector3 = _camera_rig.call(&"get_view_forward")
		view.y = 0.0
		if view.length_squared() > 0.01:
			var vyaw := atan2(view.x, view.z)
			if absf(angle_difference(_yaw, vyaw)) > deg_to_rad(80.0):
				_enter_turn(vyaw)
				return
	if _balancing:
		_yaw += clampf(_balance_yaw_err, -1.2 * delta, 1.2 * delta)
	_yaw = wrapf(_yaw, -PI, PI)
	_yaw_rate = lerpf(_yaw_rate, angle_difference(prev_yaw, _yaw) / maxf(delta, 0.0001), 1.0 - exp(-12.0 * delta))
	_apply_yaw()
	# --- speed along the facing -------------------------------------------------------
	var a := accel
	if target_speed > walk_speed * 1.2 and target_speed > _speed:
		a = run_accel * (1.0 - 0.45 * clampf(_speed / run_speed, 0.0, 1.0))
	elif target_speed < _speed:
		a = brake_decel if target_speed < 0.05 and _speed > trot_speed else decel
	_speed = move_toward(_speed, target_speed, a * delta)
	var fwd := _forward()
	var hv := fwd * _speed
	# --- balance centring ----------------------------------------------------------------
	if _balancing:
		var right := Vector3(-fwd.z, 0.0, fwd.x)  # cat's right (model faces +Z)
		hv += right * clampf(_balance_offset * 5.0, -0.25, 0.25)
	# --- probes that keep the long body honest -------------------------------------------
	hv = _apply_nose_probe(hv, delta)
	hv = _apply_edge_guard(hv, delta)
	velocity.x = hv.x
	velocity.z = hv.z
	velocity.y = minf(velocity.y, 0.0) - gravity * delta * 0.25
	# --- climb / jump entry --------------------------------------------------------------
	if _check_climb_start(delta):
		return
	if _handle_ground_jump(delta):
		return
	_try_step_up(delta)
	var y_before := global_position.y
	var was_on_floor := is_on_floor()
	move_and_slide()
	# floor snap dropped us down a step: ease the visual down instead of popping
	if was_on_floor and is_on_floor():
		var drop := y_before - global_position.y
		if drop > 0.03 and drop < max_step_height + 0.05:
			_step_offset += drop
	_after_move_ground(delta)


## Stepping down stairs / kerbs: drop onto a floor within max_step_height instead of falling.
## The cylinder's rounded rim can rest on the lip of the step we are leaving (a ~55° contact
## normal); sweeping slightly forward along the motion clears the lip and finds the tread below.
func _snap_down() -> bool:
	var hv := Vector3(velocity.x, 0.0, velocity.z)
	var fwd := hv.normalized() if hv.length() > 0.05 else _forward()
	var down := Vector3.DOWN * (max_step_height + 0.03)
	for motion: Vector3 in [down, down + fwd * 0.035, down + fwd * 0.07]:
		var col := KinematicCollision3D.new()
		if not test_move(global_transform, motion, col, safe_margin):
			continue
		if col.get_normal().y < cos(floor_max_angle):
			continue
		var travel := col.get_travel()
		if travel.y > -0.004:
			# resting on the same surface (lip contact): just stay grounded
			velocity.y = 0.0
			return true
		global_position += travel
		_step_offset += -travel.y
		velocity.y = 0.0
		apply_floor_snap()
		return true
	return false


func _gait_target_speed(mag: float) -> float:
	var mods := _speed_mods()
	if _crawling:
		return crawl_speed * mods["sneak"] * clampf(mag * 1.3, 0.3, 1.0)
	if _balancing:
		return balance_speed * mods["wire"] * clampf(mag * 1.2, 0.3, 1.0)
	if _sneaking:
		return sneak_speed * mods["sneak"] * clampf(mag * 1.2, 0.25, 1.0)
	var carry := carry_speed_mult if GameState.mouth_item != &"" else 1.0
	if _wants_sprint():
		return run_speed * mods["sprint"] * carry
	# analog: light push walks, full push trots
	var spd: float
	if mag < 0.6:
		spd = lerpf(walk_speed * 0.45, walk_speed, smoothstep(0.1, 0.6, mag))
	else:
		spd = lerpf(walk_speed, trot_speed, smoothstep(0.6, 0.95, mag))
	return spd * mods["move"] * carry


func _speed_mods() -> Dictionary:
	return {
		"move": GameState.get_modifier(&"move_speed"),
		"sprint": GameState.get_modifier(&"sprint_speed"),
		"sneak": GameState.get_modifier(&"sneak_speed"),
		"wire": GameState.get_modifier(&"wire_speed") * (0.8 + 0.4 * GameState.get_modifier(&"balance")),
	}


func _after_move_ground(delta: float) -> void:
	# don't "moonwalk" into walls: speed follows what actually happened
	var real := get_real_velocity()
	var along := real.dot(_forward())
	if _speed > 0.0 and along < _speed - 0.05:
		_speed = lerpf(_speed, maxf(along, 0.0), 1.0 - exp(-10.0 * delta))
	if is_on_floor():
		_ground_normal = get_floor_normal()
		_update_floor_surface()
		if _floor_is_water():
			_enter_swim(absf(_prev_velocity.y))
			return
	elif not _snap_down():
		# left the ground: walked off a ledge
		_enter_air(false)
		return
	if _in_water_volume and global_position.y < _water_level - swim_depth * 0.6:
		_enter_swim(absf(_prev_velocity.y))
		return
	_update_ground_state(delta)
	_emit_movement_noise(delta)


func _update_ground_state(_delta: float) -> void:
	if _land_t > 0.0 and (state == &"land" or state == &"land_hard"):
		return
	var spd := absf(_speed)
	var s: StringName
	if _balancing:
		s = &"balance"
	elif _crawling:
		s = &"crawl" if spd > 0.05 else &"sneak_idle"
	elif _sneaking:
		s = &"sneak" if spd > 0.05 else &"sneak_idle"
	elif spd < 0.05:
		s = &"idle_look" if _idle_t > idle_look_after else &"idle"
	elif spd < (walk_speed + trot_speed) * 0.5:
		s = &"walk"
	elif spd < (trot_speed + run_speed) * 0.5:
		s = &"trot"
	else:
		s = &"run"
	_set_state(s)
	# long inactivity → contextual idles
	if s == &"idle_look" and _idle_t > idle_sit_after and is_input_enabled():
		_enter_rest(&"sit")


func _emit_movement_noise(delta: float) -> void:
	if state == &"run":
		_noise_t += delta
		if _noise_t > 0.5:
			_noise_t = 0.0
			GameEvents.player_noise.emit(global_position, clampf(0.28 * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))
	else:
		_noise_t = 0.0


func _forward() -> Vector3:
	return Vector3(sin(_yaw), 0.0, cos(_yaw))


func _apply_yaw() -> void:
	rotation = Vector3(0.0, _yaw, 0.0)


# --- probes ---------------------------------------------------------------------------------

func _ray_hit(from: Vector3, to: Vector3, mask: int = SOLID_MASK) -> Dictionary:
	_ray.from = from
	_ray.to = to
	_ray.collision_mask = mask
	return get_world_3d().direct_space_state.intersect_ray(_ray)


func _ground_y_at(p: Vector3, up := 0.22, down := 0.45) -> float:
	var h := _ray_hit(p + Vector3.UP * up, p + Vector3.DOWN * down)
	if h.is_empty() or (h["normal"] as Vector3).y < 0.5:
		return -INF
	return float((h["position"] as Vector3).y)


func _probe_ground() -> void:
	var o := global_position
	var fwd := _forward()
	var right := Vector3(-fwd.z, 0.0, fwd.x)
	_probe_front = _ground_y_at(o + fwd * 0.16)
	_probe_back = _ground_y_at(o - fwd * 0.16)
	_probe_left = _ground_y_at(o - right * 0.06)
	_probe_right = _ground_y_at(o + right * 0.06)
	_probe_center = _ground_y_at(o)


## Narrow support (beam / rail / cable / wall top) → balance walk with centring + heading assist.
func _update_support(delta: float) -> void:
	var o := global_position
	var fwd := _forward()
	var right := Vector3(-fwd.z, 0.0, fwd.x)
	var base_y := o.y
	var offsets: Array[float] = [-0.1, -0.065, -0.035, 0.0, 0.035, 0.065, 0.1]
	var narrow_rows := 0
	var centers: Array[float] = []
	for row: float in [0.12, -0.12]:
		var lo := INF
		var hi := -INF
		var count := 0
		for off in offsets:
			var p := o + fwd * row + right * off
			var y := _ground_y_at(p, 0.12, 0.14)
			if y > base_y - 0.1:
				count += 1
				lo = minf(lo, off)
				hi = maxf(hi, off)
		if count > 0 and count <= 4 and lo > -0.1 and hi < 0.1:
			narrow_rows += 1
			centers.append((lo + hi) * 0.5)
		elif count > 0:
			centers.append(0.0)
	var narrow := narrow_rows == 2 and is_on_floor()
	_support_narrow_t = clampf(_support_narrow_t + (delta if narrow else -delta * 2.0), 0.0, 0.25)
	var was := _balancing
	_balancing = _support_narrow_t > 0.08
	if _balancing and centers.size() == 2:
		_balance_offset = (centers[0] + centers[1]) * 0.5
		# beam angled relative to the body → rotate towards it (only when moving along it)
		_balance_yaw_err = 0.0
		if absf(_speed) > 0.05:
			_balance_yaw_err = -atan2(centers[0] - centers[1], 0.24) * signf(_speed)
	else:
		_balance_offset = 0.0
		_balance_yaw_err = 0.0
	if _balancing != was and _anim != null:
		_anim.call(&"notify", &"balance", _balancing)


func _update_crawl() -> void:
	# low gap ahead or above → crawl (sneak posture, short collider)
	var o := global_position
	var fwd := _forward()
	var low_above := not _ray_hit(o + Vector3.UP * 0.05, o + Vector3.UP * (body_height + 0.03)).is_empty()
	var low_ahead := false
	if _move_dir.length() > 0.1 or _crawling:
		var hit := _ray_hit(o + Vector3.UP * (crawl_height + 0.02) + fwd * 0.0, o + Vector3.UP * (crawl_height + 0.02) + fwd * 0.3)
		var hit_hi := _ray_hit(o + Vector3.UP * (body_height + 0.02), o + Vector3.UP * (body_height + 0.02) + fwd * 0.3)
		low_ahead = hit.is_empty() and not hit_hi.is_empty()
	if not _crawling and (low_above or (low_ahead and _move_dir.length() > 0.1)):
		_set_crawl(true)
	elif _crawling and not low_above and not low_ahead:
		if _fits_height(body_height):
			_set_crawl(false)


func _set_crawl(on: bool) -> void:
	if on == _crawling:
		return
	_crawling = on
	var h := crawl_height if on else body_height
	_shape.height = h
	_shape_node.position = Vector3(0.0, h * 0.5, 0.0)


func _fits_height(h: float) -> bool:
	var cyl := CylinderShape3D.new()
	cyl.radius = body_radius * 0.95
	cyl.height = h - 0.02
	_shape_q.shape = cyl
	_shape_q.collision_mask = SOLID_MASK
	_shape_q.transform = Transform3D(Basis.IDENTITY, global_position + Vector3.UP * (h * 0.5 + 0.015))
	return get_world_3d().direct_space_state.intersect_shape(_shape_q, 1).is_empty()


func _apply_nose_probe(hv: Vector3, delta: float) -> Vector3:
	var fwd := _forward()
	var along := hv.dot(fwd)
	var h := 0.19 if not _crawling else 0.1
	var o := global_position + Vector3.UP * h
	var hit := _ray_hit(o, o + fwd * (nose_reach + 0.12))
	if hit.is_empty():
		return hv
	var nrm: Vector3 = hit["normal"]
	if nrm.y > 0.6:
		return hv
	nrm.y = 0.0
	nrm = nrm.normalized()
	var c := fwd.dot(-nrm)
	if c < 0.15:
		return hv
	# distance (along the wall normal) left before the nose tip touches the wall
	var dp := (o - (hit["position"] as Vector3)).dot(nrm)
	var room := dp - nose_reach * c
	if along > 0.0:
		var max_along := maxf(room, 0.0) / c / maxf(delta, 0.0001)
		if along > max_along:
			hv -= fwd * (along - max_along)
			_speed = minf(_speed, max_along + 0.05)
	if room < -0.015 and absf(along) < 0.1:
		# turned into a wall while standing: back off gently
		hv += nrm * minf(-room * 4.0, 0.25)
	return hv


func _apply_edge_guard(hv: Vector3, delta: float) -> Vector3:
	if _wants_sprint() and not _balancing:
		return hv
	var fwd := _forward()
	var along := hv.dot(fwd)
	if along <= 0.01:
		return hv
	var reach := 0.11 + along * delta * 2.0
	var p := global_position + fwd * reach
	var y := _ground_y_at(p, 0.15, edge_guard_drop)
	if y == -INF:
		hv -= fwd * along
		_speed = minf(_speed, 0.05)
	return hv


func _try_step_up(delta: float) -> void:
	var hv := Vector3(velocity.x, 0.0, velocity.z)
	if hv.length() < 0.05:
		return
	var probe := hv.normalized() * maxf(hv.length() * delta, 0.03)
	var xf := global_transform
	var col := KinematicCollision3D.new()
	if not test_move(xf, probe, col, safe_margin):
		return
	if col.get_normal().y > 0.7:
		return
	var up := Vector3.UP * (max_step_height + 0.01)
	var col2 := KinematicCollision3D.new()
	if test_move(xf, up, col2, safe_margin):
		up = col2.get_travel()
	if up.y < 0.03:
		return
	var xf_up := xf.translated(up)
	if test_move(xf_up, probe, null, safe_margin):
		return
	var xf_fwd := xf_up.translated(probe)
	var col3 := KinematicCollision3D.new()
	if not test_move(xf_fwd, -up - Vector3.UP * 0.02, col3, safe_margin):
		return
	if col3.get_normal().y < cos(floor_max_angle):
		return
	var step_h := (xf_fwd.origin + col3.get_travel()).y - xf.origin.y
	if step_h < 0.015 or step_h > max_step_height + 0.005:
		return
	global_position.y += step_h
	_step_offset -= step_h
	velocity.y = 0.0


# =============================================================================================
# Turn in place
# =============================================================================================

func _enter_turn(desired_yaw: float) -> void:
	mode = Mode.TURN
	_turn_from = _yaw
	var diff := angle_difference(_yaw, desired_yaw)
	_turn_to = _yaw + diff
	var clip := &"turn_left_90" if diff > 0.0 else &"turn_right_90"
	var base_len := _clip_length(clip, 0.6)
	_turn_len = clampf(base_len * clampf(absf(diff) / (PI * 0.5), 0.6, 1.6), 0.3, 0.9)
	_turn_t = 0.0
	_speed = 0.0
	_set_state(clip)


func _physics_turn(delta: float) -> void:
	_turn_t += delta
	var t := clampf(_turn_t / _turn_len, 0.0, 1.0)
	var e := t * t * (3.0 - 2.0 * t)
	var prev := _yaw
	_yaw = lerpf(_turn_from, _turn_to, e)
	_yaw_rate = angle_difference(prev, _yaw) / maxf(delta, 0.0001)
	_apply_yaw()
	velocity = Vector3(0.0, minf(velocity.y, 0.0) - gravity * delta * 0.25, 0.0)
	_probe_ground()
	move_and_slide()
	if not is_on_floor():
		_enter_air(false)
		return
	if _jump_just_pressed():
		_yaw = wrapf(_yaw, -PI, PI)
		_enter_crouch()
		return
	if t >= 1.0 or (t > 0.55 and _move_dir.length() > 0.1 and absf(angle_difference(_yaw, atan2(_move_dir.x, _move_dir.z))) < 0.5):
		_yaw = wrapf(_yaw, -PI, PI)
		_speed = 0.12 if _move_dir.length() > 0.1 else 0.0
		_enter_ground()


# =============================================================================================
# Jumping
# =============================================================================================

func _handle_ground_jump(_delta: float) -> bool:
	if not _jump_just_pressed():
		return false
	if _crawling and not _fits_height(body_height):
		return false
	if absf(_speed) > trot_speed + 0.6 or _balancing and absf(_speed) > 0.2:
		# running leap: no crouch, straight off the stride
		return _quick_leap()
	_enter_crouch()
	return true


func _enter_crouch() -> void:
	mode = Mode.CROUCH
	_charge = 0.0
	_target = {}
	_planner_tick = 0
	_set_state(&"jump_crouch")
	_update_planner(true)


func _physics_crouch(delta: float) -> void:
	_charge = clampf(_charge + delta / maxf(charge_time, 0.01), 0.0, 1.0)
	_probe_ground()
	# settle: decelerate to a stop, keep sliding friction
	_speed = move_toward(_speed, 0.0, brake_decel * delta)
	var fwd := _forward()
	velocity.x = fwd.x * _speed
	velocity.z = fwd.z * _speed
	velocity.y = minf(velocity.y, 0.0) - gravity * delta * 0.25
	_planner_tick += 1
	if _planner_tick % 2 == 0:
		_update_planner(false)
	# rotate towards the aim / target
	var aim := _aim_direction()
	var face := aim
	if not _target.is_empty():
		var tp: Vector3 = _target["point"]
		face = Vector3(tp.x - global_position.x, 0.0, tp.z - global_position.z)
	if face.length_squared() > 0.0004:
		var desired := atan2(face.x, face.z)
		var diff := angle_difference(_yaw, desired)
		var prev := _yaw
		_yaw += clampf(diff, -6.0 * delta, 6.0 * delta)
		_yaw_rate = angle_difference(prev, _yaw) / maxf(delta, 0.0001)
		_apply_yaw()
	move_and_slide()
	if not is_on_floor():
		_hide_reticle()
		_enter_air(false)
		return
	if _floor_is_water():
		_hide_reticle()
		_enter_swim(0.0)
		return
	if not is_input_enabled():
		_hide_reticle()
		_enter_ground()
		return
	if _jump_down_t < 0.0:
		var tap := _jump_released_hold < tap_time
		_launch(_charge if not tap else 0.35)


func _aim_direction() -> Vector3:
	if _move_dir.length() > 0.15:
		return _move_dir.normalized()
	if _camera_rig != null:
		var f: Vector3 = _camera_rig.call(&"get_view_forward")
		f.y = 0.0
		if f.length_squared() > 0.001:
			return f.normalized()
	return _forward()


func _update_planner(_force: bool) -> void:
	_configure_planner()
	var aim_point := Vector3.INF
	if _camera_rig != null and _move_dir.length() < 0.15:
		aim_point = _camera_rig.call(&"get_aim_point", _planner.max_distance + 1.5)
		if aim_point != Vector3.INF:
			var flat := Vector2(aim_point.x - global_position.x, aim_point.z - global_position.z).length()
			if flat > _planner.max_distance + 0.4:
				aim_point = Vector3.INF
	# plain floor spots are only targets in explicit aim mode (aim_jump): a long jump-hold with the
	# TPP camera looking down past the cat must still pick the ledge ahead, not the floor at its nose
	var deliberate := _aiming()
	_target = _planner.find_target(global_position, _aim_direction(), aim_point, deliberate)
	if _reticle != null:
		if _target.is_empty():
			_reticle.call(&"hide_target")
		else:
			_reticle.call(&"show_target", _target, global_position, gravity, _charge)


func _configure_planner() -> void:
	_planner.configure(get_world_3d().direct_space_state, [get_rid()] as Array[RID], body_radius, body_height)
	_planner.gravity = gravity
	_planner.max_height = max_jump_height * GameState.get_modifier(&"jump_height")
	_planner.max_distance = max_jump_distance * GameState.get_modifier(&"jump_distance")


func _hide_reticle() -> void:
	if _reticle != null:
		_reticle.call(&"hide_target")


## Immediate leap (running jump, buffered jump, coyote jump): target along the motion if any.
func _quick_leap() -> bool:
	_configure_planner()
	var dir := _move_dir.normalized() if _move_dir.length() > 0.15 else _forward()
	_target = _planner.find_target(global_position, dir, Vector3.INF)
	if not _target.is_empty():
		# a running cat only commits to targets roughly ahead
		var tp: Vector3 = _target["point"]
		var to := Vector3(tp.x - global_position.x, 0.0, tp.z - global_position.z)
		if to.length() > 0.05 and to.normalized().dot(dir) < 0.75:
			_target = {}
	_launch(0.6)
	return true


func _launch(charge: float) -> void:
	_hide_reticle()
	var p0 := global_position
	if not _target.is_empty():
		# re-validate (the world may have changed since the reticle was computed)
		var tp: Vector3 = _target["point"]
		var arc := _planner.validate(p0, tp)
		if arc.is_empty():
			_target = {}
		else:
			_target.merge(arc, true)
	_air_targeted = not _target.is_empty()
	_air_p0 = p0
	_air_t = 0.0
	if _air_targeted:
		_air_v0 = _target["v0"]
		_air_T = float(_target["time"])
		var tp2: Vector3 = _target["point"]
		var dir := Vector3(tp2.x - p0.x, 0.0, tp2.z - p0.z)
		if dir.length_squared() > 0.0001:
			_yaw = atan2(dir.x, dir.z)
			_apply_yaw()
		if _camera_rig != null:
			_camera_rig.call(&"frame_jump", p0, tp2)
	else:
		var hmod := GameState.get_modifier(&"jump_height")
		var dmod := GameState.get_modifier(&"jump_distance")
		var h := lerpf(free_jump_height.x, free_jump_height.y, charge) * hmod
		var push := lerpf(free_jump_push.x, free_jump_push.y, charge) * dmod
		var fwd := _forward()
		var carried := maxf(_speed, 0.0) * 0.9
		if _move_dir.length() < 0.1 and _speed < 0.1:
			push *= 0.35  # standing jump with no direction: mostly up
		var hs := minf(carried + push, run_speed * 1.25 * dmod)
		_air_v0 = fwd * hs + Vector3.UP * sqrt(2.0 * gravity * h)
		_air_T = 0.0
	velocity = _air_v0
	_speed = Vector2(velocity.x, velocity.z).length()
	_air_from_jump = true
	_air_apex_y = p0.y
	mode = Mode.AIR
	_set_crawl(false)
	_set_state(&"jump")
	GameEvents.player_jumped.emit(charge)  # AudioManager plays the jump effort
	if _fx != null:
		_fx.call(&"puff", global_position, 0.3 + 0.4 * charge, _surface)
	leapt.emit(_air_targeted, _target.get("point", Vector3.INF))


# =============================================================================================
# Air
# =============================================================================================

func _enter_air(from_jump: bool) -> void:
	mode = Mode.AIR
	_air_targeted = false
	_air_from_jump = from_jump
	_air_t = 0.0
	_air_apex_y = global_position.y
	_set_crawl(false)
	_hide_reticle()
	_set_state(&"fall")


func _physics_air(delta: float) -> void:
	_air_t += delta
	_time_since_ground += delta
	_jump_buffer_t = maxf(0.0, _jump_buffer_t - delta)
	_air_apex_y = maxf(_air_apex_y, global_position.y)
	if _jump_just_pressed():
		if not _air_from_jump and _time_since_ground < coyote_time:
			_quick_leap()
			return
		_jump_buffer_t = jump_buffer_time
	if _air_targeted:
		var t := _air_t
		if t <= _air_T:
			var p := JumpPlanner.arc_point(_air_p0, _air_v0, gravity, t)
			velocity = (p - global_position) / maxf(delta, 0.0001)
		else:
			# past the landing time (target moved / shaved): keep falling naturally
			velocity.y -= gravity * fall_gravity_mult * delta
	else:
		var g := gravity * (fall_gravity_mult if velocity.y < 0.0 else 1.0)
		velocity.y = maxf(velocity.y - g * delta, -max_fall_speed)
		# light air steering
		if _move_dir.length() > 0.1:
			var hv := Vector3(velocity.x, 0.0, velocity.z)
			var want := _move_dir * maxf(hv.length(), 0.6)
			hv = hv.move_toward(want, air_control * delta)
			velocity.x = hv.x
			velocity.z = hv.z
	var hvel := Vector3(velocity.x, 0.0, velocity.z)
	if hvel.length() > 0.2:
		var desired := atan2(hvel.x, hvel.z)
		var prev := _yaw
		_yaw += clampf(angle_difference(_yaw, desired), -5.0 * delta, 5.0 * delta)
		_yaw_rate = angle_difference(prev, _yaw) / maxf(delta, 0.0001)
		_apply_yaw()
	var pre_v := velocity
	move_and_slide()
	if velocity.y < -0.5 and state == &"jump":
		_set_state(&"fall")
	# water volume entered from above
	if _in_water_volume and global_position.y < _water_level:
		_enter_swim(absf(pre_v.y))
		return
	if is_on_floor() and pre_v.y <= 0.05:
		if _floor_is_water():
			_enter_swim(absf(pre_v.y))
		else:
			_land(absf(pre_v.y))
		return
	# a ledge in front of the chest → scramble up
	if is_on_wall() or _air_targeted == false:
		var dir := hvel.normalized() if hvel.length() > 0.2 else _forward()
		var ledge := _find_ledge(dir, max_scramble_height)
		if not ledge.is_empty() and (is_on_wall() or float(ledge["dist"]) < body_radius + 0.08):
			_start_scramble(ledge, Mode.GROUND)
			return
	# cling to climbable surfaces
	if _climb_cooldown <= 0.0 and is_on_wall():
		var c := _probe_climbable(hvel.normalized() if hvel.length() > 0.1 else _forward())
		if not c.is_empty():
			_enter_climb(c)
			return
	_climb_cooldown = maxf(0.0, _climb_cooldown - delta)


func _land(impact: float) -> void:
	var fall_h := maxf(_air_apex_y - global_position.y, 0.0)
	if _camera_rig != null:
		_camera_rig.call(&"end_frame_jump")
	_air_targeted = false
	_ground_normal = get_floor_normal()
	_update_floor_surface()
	var hard := fall_h > hard_land_height * GameState.get_modifier(&"jump_height")
	mode = Mode.GROUND
	_speed = minf(Vector2(velocity.x, velocity.z).length(), run_speed) * (0.35 if hard else 0.85)
	_land_t = _clip_length(&"land_hard", 0.7) * 0.85 if hard else _clip_length(&"land", 0.3) * 0.7
	_set_state(&"land_hard" if hard else &"land")
	var loud := clampf(impact / 9.0, 0.05, 1.0) * GameState.get_modifier(&"landing_noise_mult")
	GameEvents.player_landed.emit(impact, _surface)
	GameEvents.player_noise.emit(global_position, clampf(loud, 0.0, 1.0))
	if _fx != null:
		_fx.call(&"puff", global_position, clampf(impact / 6.0, 0.2, 1.2), _surface)
	if hard and _camera_rig != null:
		_camera_rig.call(&"add_trauma", clampf(0.25 + (impact - 6.0) * 0.06, 0.2, 0.55))
	var safe := GameState.get_modifier(&"safe_fall_height")
	if fall_h > safe:
		var dmg := (fall_h - safe) * 14.0 * GameState.get_modifier(&"fall_damage_mult")
		GameEvents.player_damaged.emit(dmg, &"fall")
	landed.emit(impact, fall_h)
	if _jump_buffer_t > 0.0:
		_jump_buffer_t = 0.0
		if not hard:
			_quick_leap()


# =============================================================================================
# Ledge scramble / mantle
# =============================================================================================

## Wall in front of the chest whose top is within reach and has room for the cat.
func _find_ledge(dir: Vector3, max_h: float) -> Dictionary:
	dir.y = 0.0
	if dir.length_squared() < 0.0001:
		return {}
	dir = dir.normalized()
	var o := global_position
	var chest := o + Vector3.UP * 0.12
	var wall := _ray_hit(chest, chest + dir * (body_radius + 0.3))
	if wall.is_empty():
		wall = _ray_hit(o + Vector3.UP * 0.04, o + Vector3.UP * 0.04 + dir * (body_radius + 0.3))
		if wall.is_empty():
			return {}
	var wn: Vector3 = wall["normal"]
	if wn.y > 0.5 or dir.dot(-Vector3(wn.x, 0.0, wn.z).normalized()) < 0.45:
		return {}
	var wp: Vector3 = wall["position"]
	var into := -Vector3(wn.x, 0.0, wn.z).normalized()
	var top_from := Vector3(wp.x, o.y + max_h + 0.2, wp.z) + into * 0.13
	var top := _ray_hit(top_from, Vector3(top_from.x, o.y + 0.05, top_from.z))
	if top.is_empty() or (top["normal"] as Vector3).y < 0.72:
		return {}
	var tp: Vector3 = top["position"]
	var h := tp.y - o.y
	if h < 0.1 or h > max_h:
		return {}
	# room on top (and the lip must not be under a ceiling)
	_shape_q.shape = _probe_cyl()
	_shape_q.collision_mask = SOLID_MASK
	_shape_q.transform = Transform3D(Basis.IDENTITY, tp + into * 0.04 + Vector3.UP * (body_height * 0.4 + 0.03))
	if not get_world_3d().direct_space_state.intersect_shape(_shape_q, 1).is_empty():
		return {}
	return {"top": tp + into * 0.04, "height": h, "dir": into, "dist": chest.distance_to(wp)}


var _probe_cyl_shape: CylinderShape3D = null


func _probe_cyl() -> CylinderShape3D:
	if _probe_cyl_shape == null:
		_probe_cyl_shape = CylinderShape3D.new()
		_probe_cyl_shape.radius = body_radius * 0.85
		_probe_cyl_shape.height = body_height * 0.8
	return _probe_cyl_shape


func _start_scramble(ledge: Dictionary, exit_mode: Mode) -> void:
	mode = Mode.SCRAMBLE
	_scr_from = global_position
	_scr_to = ledge["top"]
	_scr_dir = ledge["dir"]
	_scr_t = 0.0
	_scr_len = 0.3 + 0.45 * clampf(float(ledge["height"]) / max_scramble_height, 0.0, 1.0)
	_scr_exit_mode = exit_mode
	_yaw = atan2(_scr_dir.x, _scr_dir.z)
	_apply_yaw()
	velocity = Vector3.ZERO
	_air_targeted = false
	if _camera_rig != null:
		_camera_rig.call(&"end_frame_jump")
	_set_state(&"scramble")
	GameEvents.player_noise.emit(global_position, clampf(0.12 * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))


func _physics_scramble(delta: float) -> void:
	_scr_t += delta
	var t := clampf(_scr_t / _scr_len, 0.0, 1.0)
	# rise first (claws hooked on the lip), then pull the body over
	var rise := 1.0 - pow(1.0 - clampf(t / 0.7, 0.0, 1.0), 2.0)
	var over := smoothstep(0.35, 1.0, t)
	var p := Vector3(lerpf(_scr_from.x, _scr_to.x, over), lerpf(_scr_from.y, _scr_to.y + 0.01, rise), lerpf(_scr_from.z, _scr_to.z, over))
	velocity = (p - global_position) / maxf(delta, 0.0001)
	global_position = p
	if t >= 1.0:
		velocity = _scr_dir * 0.3
		_speed = 0.3
		_ground_normal = Vector3.UP
		_enter_ground()
		apply_floor_snap()


# =============================================================================================
# Climbing (layer 6)
# =============================================================================================

func _probe_climbable(dir: Vector3) -> Dictionary:
	dir.y = 0.0
	if dir.length_squared() < 0.0001:
		return {}
	dir = dir.normalized()
	var best: Dictionary = {}
	for h: float in [0.12, 0.2, 0.06]:
		var o := global_position + Vector3.UP * h
		var hit := _ray_hit(o, o + dir * (body_radius + 0.25), L_CLIMB)
		if hit.is_empty():
			continue
		var n: Vector3 = hit["normal"]
		if absf(n.y) > 0.45:
			continue
		best = hit
		break
	return best


func _check_climb_start(delta: float) -> bool:
	if _climb_cooldown > 0.0 or _move_dir.length() < 0.3:
		_climb_intent = 0.0
		return false
	var fwd := _forward()
	if _move_dir.normalized().dot(fwd) < 0.7:
		_climb_intent = 0.0
		return false
	var c := _probe_climbable(fwd)
	if c.is_empty():
		_climb_intent = 0.0
		return false
	var n: Vector3 = c["normal"]
	if fwd.dot(-Vector3(n.x, 0.0, n.z).normalized()) < 0.6:
		return false
	var dist := (global_position + Vector3.UP * 0.12).distance_to(c["position"])
	if dist > nose_reach + 0.06:
		return false
	_climb_intent += delta
	if _climb_intent > 0.12 or _jump_just_pressed():
		_climb_intent = 0.0
		_enter_climb(c)
		return true
	return false


func _enter_climb(hit: Dictionary) -> void:
	var n: Vector3 = hit["normal"]
	n.y = 0.0
	_climb_normal = n.normalized()
	mode = Mode.CLIMB
	_hide_reticle()
	_air_targeted = false
	if _camera_rig != null:
		_camera_rig.call(&"end_frame_jump")
	_yaw = atan2(-_climb_normal.x, -_climb_normal.z)
	_apply_yaw()
	velocity = Vector3.ZERO
	_speed = 0.0
	_set_crawl(false)
	# hug the wall
	var wp: Vector3 = hit["position"]
	var flat := Vector3(global_position.x - wp.x, 0.0, global_position.z - wp.z)
	var dist := flat.dot(_climb_normal)
	global_position += _climb_normal * (body_radius + 0.012 - dist)
	if is_on_floor():
		var lift := 0.14
		if not test_move(global_transform, Vector3.UP * lift):
			global_position.y += lift
	_set_state(&"climb")
	_play_sfx(&"cat_scratch", global_position, -8.0)


func _physics_climb(delta: float) -> void:
	var n := _climb_normal
	var right := (-n).cross(Vector3.UP).normalized()
	var spd := climb_speed * GameState.get_modifier(&"climb_speed")
	var up_in := _move_input.y
	var side_in := _move_input.x
	# moving the stick "away from the wall" in camera space also means down
	var v := Vector3.UP * up_in * spd + right * side_in * spd * 0.6
	v -= n * 0.4  # stay pressed on the surface
	velocity = v
	move_and_slide()
	_speed = absf(up_in) * spd
	_set_state(&"climb")
	# keep attached / follow curved trunks
	var o := global_position + Vector3.UP * 0.12
	var hit := _ray_hit(o, o - n * (body_radius + 0.25), L_CLIMB)
	if hit.is_empty():
		var lower := _ray_hit(global_position + Vector3.UP * 0.02, global_position + Vector3.UP * 0.02 - n * (body_radius + 0.25), L_CLIMB)
		if lower.is_empty():
			_detach_climb(false)
			return
		hit = lower
	var hn: Vector3 = hit["normal"]
	hn.y = 0.0
	if hn.length_squared() > 0.01:
		_climb_normal = _climb_normal.slerp(hn.normalized(), 1.0 - exp(-10.0 * delta)).normalized()
		_yaw = atan2(-_climb_normal.x, -_climb_normal.z)
		_apply_yaw()
	# top of the climbable surface → mantle over the top if possible
	if up_in > 0.2:
		var head := global_position + Vector3.UP * 0.36
		var top_hit := _ray_hit(head, head - n * (body_radius + 0.25), SOLID_MASK)
		if top_hit.is_empty():
			var ledge := _find_ledge_from_climb()
			if not ledge.is_empty():
				_start_scramble(ledge, Mode.GROUND)
				return
			velocity = Vector3.ZERO  # end of a pole: hold on
	# bottom
	if up_in < -0.2 and is_on_floor():
		_detach_climb(true)
		return
	if _jump_just_pressed():
		_climb_jump()
		return
	if is_input_enabled() and Input.is_action_just_pressed(&"sneak"):
		_detach_climb(false)


func _find_ledge_from_climb() -> Dictionary:
	var into := -_climb_normal
	var from := global_position + Vector3.UP * 0.6 + into * (body_radius + 0.14)
	var top := _ray_hit(from, from + Vector3.DOWN * 0.6)
	if top.is_empty() or (top["normal"] as Vector3).y < 0.72:
		return {}
	var tp: Vector3 = top["position"]
	if tp.y < global_position.y + 0.1:
		return {}
	_shape_q.shape = _probe_cyl()
	_shape_q.collision_mask = SOLID_MASK
	_shape_q.transform = Transform3D(Basis.IDENTITY, tp + Vector3.UP * (body_height * 0.4 + 0.03))
	if not get_world_3d().direct_space_state.intersect_shape(_shape_q, 1).is_empty():
		return {}
	return {"top": tp, "height": tp.y - global_position.y, "dir": into, "dist": 0.0}


func _detach_climb(on_ground: bool) -> void:
	_climb_cooldown = 0.35
	if on_ground:
		_yaw = atan2(_climb_normal.x, _climb_normal.z)
		_apply_yaw()
		global_position += _climb_normal * 0.05
		_enter_ground()
	else:
		velocity = _climb_normal * 0.6
		_enter_air(false)


func _climb_jump() -> void:
	_climb_cooldown = 0.4
	_configure_planner()
	var away := _climb_normal
	var aim := _aim_direction()
	if aim.dot(away) < 0.0:
		aim = away
	_target = _planner.find_target(global_position, aim, Vector3.INF)
	if _target.is_empty():
		_yaw = atan2(away.x, away.z)
		_apply_yaw()
		_target = {}
		_air_targeted = false
		velocity = away * 2.2 + Vector3.UP * 3.0
		_air_v0 = velocity
		_air_from_jump = true
		_air_apex_y = global_position.y
		mode = Mode.AIR
		_set_state(&"jump")
		GameEvents.player_jumped.emit(0.5)
	else:
		_launch(0.6)


# =============================================================================================
# Water
# =============================================================================================

func _probe_water() -> void:
	_in_water_volume = false
	if not is_inside_tree():
		return
	_point_q.position = global_position + Vector3.UP * 0.1
	var res := get_world_3d().direct_space_state.intersect_point(_point_q, 4)
	for r: Dictionary in res:
		var area := r.get("collider") as Area3D
		if area == null:
			continue
		_in_water_volume = true
		_water_level = _area_water_level(area)
		return
	if mode == Mode.SWIM and not _floor_is_water():
		# left the volume
		pass


static func _area_water_level(area: Area3D) -> float:
	if area.has_meta(&"water_level"):
		return float(area.get_meta(&"water_level"))
	for c in area.get_children():
		var cs := c as CollisionShape3D
		if cs == null or cs.shape == null:
			continue
		if cs.shape is BoxShape3D:
			var box := cs.shape as BoxShape3D
			return (cs.global_transform * Vector3(0.0, box.size.y * 0.5, 0.0)).y
		if cs.shape is CylinderShape3D:
			return (cs.global_transform * Vector3(0.0, (cs.shape as CylinderShape3D).height * 0.5, 0.0)).y
	return area.global_position.y


func _floor_is_water() -> bool:
	if not is_on_floor():
		return false
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		if c.get_normal().y < 0.6:
			continue
		var col := c.get_collider() as CollisionObject3D
		if col != null and (col.collision_layer & L_WATER) != 0 and (col.collision_layer & L_WORLD) == 0:
			_water_level = c.get_position().y
			return true
		if col != null and _surface_of(col) == &"water":
			_water_level = c.get_position().y
			return true
	return false


func _enter_swim(impact: float) -> void:
	mode = Mode.SWIM
	_hide_reticle()
	_air_targeted = false
	if _camera_rig != null:
		_camera_rig.call(&"end_frame_jump")
	_swim_t = 0.0
	_set_crawl(false)
	_set_state(&"swim")
	var pos := Vector3(global_position.x, _water_level, global_position.z)
	GameEvents.player_landed.emit(maxf(impact, 0.5), &"water")  # GameState soaks the fur
	GameEvents.player_noise.emit(pos, clampf(0.35 + impact * 0.08, 0.0, 1.0))
	_play_sfx(&"splash_big" if impact > 3.0 else &"splash_small", pos)
	if _fx != null:
		_fx.call(&"splash", pos, clampf(0.4 + impact / 6.0, 0.3, 1.5))


func _physics_swim(delta: float) -> void:
	_swim_t += delta
	var target_y := _water_level - swim_depth
	# buoyancy spring (critically damped-ish)
	var dy := target_y - global_position.y
	velocity.y = lerpf(velocity.y, dy * 7.0, 1.0 - exp(-8.0 * delta))
	var mag := _move_dir.length()
	if mag > 0.1:
		var desired := atan2(_move_dir.x, _move_dir.z)
		var prev := _yaw
		_yaw += clampf(angle_difference(_yaw, desired), -3.0 * delta, 3.0 * delta)
		_yaw_rate = angle_difference(prev, _yaw) / maxf(delta, 0.0001)
		_apply_yaw()
	# panicked paddling: even without input the cat heads for the nearest edge
	var spd_target := swim_speed * maxf(mag, 0.35 if _swim_t > 0.4 else 0.0)
	_speed = move_toward(_speed, spd_target, 2.0 * delta)
	if mag < 0.1 and _swim_t > 0.4:
		var edge := _nearest_water_edge()
		if edge != Vector3.INF:
			var to := Vector3(edge.x - global_position.x, 0.0, edge.z - global_position.z)
			if to.length_squared() > 0.0001:
				var prev2 := _yaw
				_yaw += clampf(angle_difference(_yaw, atan2(to.x, to.z)), -2.5 * delta, 2.5 * delta)
				_yaw_rate = angle_difference(prev2, _yaw) / maxf(delta, 0.0001)
				_apply_yaw()
	var fwd := _forward()
	velocity.x = fwd.x * _speed
	velocity.z = fwd.z * _speed
	move_and_slide()
	if _swim_t - floorf(_swim_t / 0.45) * 0.45 < delta and _fx != null:
		_fx.call(&"ripple", Vector3(global_position.x, _water_level, global_position.z), 0.6)
	# scramble out over the edge
	var ledge := _find_ledge(fwd, swim_depth + 0.5)
	if not ledge.is_empty() and (is_on_wall() or float(ledge["dist"]) < body_radius + 0.12):
		_start_scramble(ledge, Mode.GROUND)
		_play_sfx(&"cat_shake_wet", global_position, -4.0)
		return
	# walked out up a ramp / shallow bottom
	var still_in := _in_water_volume or _floor_is_water()
	if is_on_floor() and not _floor_is_water() and global_position.y > _water_level - swim_depth * 0.5:
		still_in = false
	if not still_in and _swim_t > 0.2:
		_enter_ground()
		_play_sfx(&"cat_shake_wet", global_position, -4.0)
		return
	_set_state(&"swim")


func _nearest_water_edge() -> Vector3:
	var best := Vector3.INF
	var best_d := INF
	var o := global_position + Vector3.UP * 0.12
	for i in 12:
		var a := TAU * float(i) / 12.0
		var d := Vector3(sin(a), 0.0, cos(a))
		var hit := _ray_hit(o, o + d * 6.0)
		if hit.is_empty():
			continue
		var dist := o.distance_to(hit["position"])
		if dist < best_d:
			best_d = dist
			best = hit["position"]
	return best


# =============================================================================================
# Actions & rest
# =============================================================================================

func _handle_actions(delta: float) -> void:
	_refuse_t = maxf(0.0, _refuse_t - delta)
	if mode == Mode.GROUND and _move_dir.length() < 0.1:
		_apply_face_goal(delta)
	elif mode == Mode.GROUND:
		_face_active = false
	if not is_input_enabled():
		return
	# meow: tap = short, hold = loud
	if Input.is_action_just_pressed(&"meow"):
		_meow_t = 0.0
		_meow_loud_done = false
	elif _meow_t >= 0.0:
		if Input.is_action_pressed(&"meow"):
			_meow_t += delta
			if _meow_t > 0.32 and not _meow_loud_done:
				_meow_loud_done = true
				meow(&"loud")
		else:
			if not _meow_loud_done:
				meow(&"short")
			_meow_t = -1.0
	# sit / groom: tap toggles sitting, hold grooms
	if Input.is_action_just_pressed(&"sit_groom"):
		_sit_t = 0.0
		_sit_hold_done = false
	elif _sit_t >= 0.0:
		if Input.is_action_pressed(&"sit_groom"):
			_sit_t += delta
			if _sit_t > 0.4 and not _sit_hold_done:
				_sit_hold_done = true
				if _can_rest():
					_enter_rest(&"groom")
		else:
			if not _sit_hold_done:
				if mode == Mode.REST:
					_exit_rest()
				elif _can_rest():
					_enter_rest(&"sit")
			_sit_t = -1.0
	if Input.is_action_just_pressed(&"swipe"):
		swipe()
	if Input.is_action_just_pressed(&"pickup_drop"):
		if GameState.mouth_item != &"":
			drop_mouth_item()
		elif _interaction != null:
			_interaction.call(&"interact_focused", &"pickup")
	if Input.is_action_just_pressed(&"interact") and _interaction != null:
		_interaction.call(&"interact_focused", &"")
	if Input.is_action_just_pressed(&"cat_sense") and _sense != null:
		_sense.call(&"toggle")


func _can_rest() -> bool:
	return (mode == Mode.GROUND and absf(_speed) < 0.3 and not _balancing and not _crawling) or mode == Mode.REST


func meow(kind: StringName = &"short") -> void:
	var loud := kind == &"loud"
	if kind == &"short":
		# variety: greet a nearby NPC, otherwise an occasional chirp/trill (AudioManager resolves
		# the kind to a sound on GameEvents.player_meowed — the player never plays it twice)
		if _interaction != null and _interaction.call(&"has_npc_nearby"):
			kind = &"greet"
		elif randf() < 0.25:
			kind = &"chirp"
	if _anim != null:
		_anim.call(&"play_oneshot", &"meow", true)
	GameEvents.player_meowed.emit(kind)
	GameEvents.player_noise.emit(global_position, clampf((0.85 if loud else 0.32) * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))


func swipe() -> void:
	if mode != Mode.GROUND and mode != Mode.REST:
		return
	if mode == Mode.REST:
		_exit_rest()
		return
	_enter_action(&"swipe", _clip_length(&"swipe", 0.55), 0.35)
	_play_sfx(&"cat_swipe", global_position + _forward() * 0.25)
	# paw reach: knock pushables / poke anything that wants it
	var fwd := _forward()
	var paw := global_position + fwd * 0.26 + Vector3.UP * 0.12
	var sph := SphereShape3D.new()
	sph.radius = 0.16
	_shape_q.shape = sph
	_shape_q.collision_mask = L_PROPS | L_NPC | L_INTERACT
	_shape_q.collide_with_areas = true
	_shape_q.transform = Transform3D(Basis.IDENTITY, paw)
	var hits := get_world_3d().direct_space_state.intersect_shape(_shape_q, 8)
	_shape_q.collide_with_areas = false
	var done: Array[Object] = []
	for h: Dictionary in hits:
		var obj: Object = h.get("collider")
		var n := obj as Node
		if n == null:
			continue
		var target: Node = n
		if not target.has_method(&"knock") and target.get_parent() != null and target.get_parent().has_method(&"knock"):
			target = target.get_parent()
		if target in done:
			continue
		done.append(target)
		if target.has_method(&"knock"):
			var side := Vector3(-fwd.z, 0.0, fwd.x) * (0.35 if randf() < 0.5 else -0.35)
			target.call(&"knock", fwd + side, 1.0, self)
		elif target.has_method(&"on_swiped"):
			target.call(&"on_swiped", self)
	GameEvents.player_noise.emit(global_position, clampf(0.08 * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))


func drop_mouth_item() -> void:
	var id := GameState.drop_mouth_item()
	if id == &"":
		return
	var xf := _mouth_attach.global_transform
	xf.basis = Basis(Vector3.UP, _yaw)
	var parent := get_parent() if get_parent() != null else get_tree().current_scene
	# (GameState.drop_mouth_item already emitted GameEvents.item_dropped)
	PickupItem.spawn_dropped(id, Transform3D(xf.basis, xf.origin + _forward() * 0.04), parent)
	if mode == Mode.GROUND and absf(_speed) < 0.5:
		_enter_action(&"pickup", _clip_length(&"pickup", 0.6) * 0.8, 0.3)


## Called by interactables / dialogue: pickup lie_down eat drink scratch rub knock, plus dialogue
## actions (meow purr headbutt rub knead sit roll_over slow_blink hiss swipe groom).
func play_action(action: StringName) -> void:
	match action:
		&"pickup", &"knock", &"swipe", &"hiss", &"stretch":
			_enter_action(action, _clip_length(action, 0.7), 0.4)
			if action == &"hiss":
				GameEvents.player_noise.emit(global_position, clampf(0.4 * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))
		&"eat", &"drink":
			_enter_action(action, 3.2, 0.9)
		&"scratch":
			_enter_action(&"scratch", 2.6, 0.8)
		&"rub", &"headbutt":
			_enter_action(&"rub", 1.8, 0.6)
		&"lie_down", &"sleep", &"nap":
			_enter_rest(&"lie")
		&"sit", &"slow_blink":
			_enter_rest(&"sit")
		&"groom":
			_enter_rest(&"groom")
		&"knead", &"roll_over":
			_enter_rest(&"knead")
		&"meow", &"purr":
			meow(&"short")
		_:
			pass


func _enter_action(action: StringName, length: float, cancel_after: float) -> void:
	if mode == Mode.AIR or mode == Mode.SWIM or mode == Mode.CLIMB or mode == Mode.SCRAMBLE:
		return
	_hide_reticle()
	mode = Mode.ACTION
	_action_name = action
	_action_t = 0.0
	_action_len = maxf(length, 0.2)
	_action_cancel_after = cancel_after
	_speed = 0.0
	_set_state(action)


func _apply_face_goal(delta: float) -> void:
	if not _face_active:
		return
	var diff := angle_difference(_yaw, _face_goal)
	if absf(diff) < 0.02:
		_face_active = false
		_yaw_rate = 0.0
		return
	var prev := _yaw
	_yaw += clampf(diff, -5.0 * delta, 5.0 * delta)
	_yaw_rate = angle_difference(prev, _yaw) / maxf(delta, 0.0001)
	_apply_yaw()


func _physics_action(delta: float) -> void:
	_action_t += delta
	_apply_face_goal(delta)
	velocity = Vector3(0.0, minf(velocity.y, 0.0) - gravity * delta * 0.25, 0.0)
	_probe_ground()
	move_and_slide()
	if not is_on_floor():
		_enter_air(false)
		return
	var cancel := _action_t > _action_cancel_after and (_move_dir.length() > 0.3 or _jump_just_pressed())
	if _action_t >= _action_len or cancel:
		_enter_ground()


func _enter_rest(kind: StringName) -> void:
	if mode == Mode.AIR or mode == Mode.SWIM or mode == Mode.CLIMB or mode == Mode.SCRAMBLE:
		return
	_hide_reticle()
	var from_rest := mode == Mode.REST
	mode = Mode.REST
	_speed = 0.0
	match kind:
		&"sit":
			if from_rest and (_rest_phase == &"sit" or _rest_phase == &"groom"):
				_rest_go(&"sit", -1.0)
			else:
				_rest_go(&"sit_down", _clip_length(&"sit_down", 0.8), &"sit")
		&"groom":
			if from_rest and (_rest_phase == &"sit" or _rest_phase == &"groom"):
				_rest_go(&"groom", 6.0, &"sit")
			else:
				_rest_go(&"sit_down", _clip_length(&"sit_down", 0.8), &"groom")
		&"knead":
			_rest_go(&"knead", 4.0, &"sit")
		&"lie":
			_rest_go(&"lie_down", _clip_length(&"lie_down", 1.2), &"lie")
		&"sleep":
			_rest_go(&"sleep", -1.0)


func _rest_go(phase: StringName, length: float, next: StringName = &"") -> void:
	_rest_phase = phase
	_rest_t = 0.0
	_rest_len = length
	_rest_next = next
	_set_state(phase)


func _exit_rest() -> void:
	match _rest_phase:
		&"sleep":
			_rest_go(&"stretch", _clip_length(&"stretch", 1.6) * 0.8, &"_done")
		&"lie", &"lie_down":
			_rest_go(&"stand_up", _clip_length(&"stand_up", 0.7) * 0.8, &"_done")
		&"sit", &"groom", &"sit_down", &"knead":
			_rest_go(&"stand_up", _clip_length(&"stand_up", 0.7) * 0.75, &"_done")
		_:
			_enter_ground()


func _physics_rest(delta: float) -> void:
	_rest_t += delta
	_apply_face_goal(delta)
	velocity = Vector3(0.0, minf(velocity.y, 0.0) - gravity * delta * 0.25, 0.0)
	_probe_ground()
	move_and_slide()
	if not is_on_floor():
		_enter_air(false)
		return
	var leaving := _rest_phase == &"stand_up" or _rest_phase == &"stretch"
	if not leaving and is_input_enabled() and (_move_dir.length() > 0.3 or _jump_just_pressed()):
		_idle_t = 0.0
		_exit_rest()
		return
	if _rest_len > 0.0 and _rest_t >= _rest_len:
		var nxt := _rest_next
		if nxt == &"_done" or (nxt == &"" and leaving):
			_enter_ground()
			return
		if nxt == &"":
			_rest_len = -1.0
			return
		if _rest_phase == &"groom":
			GameState.groom()
		match nxt:
			&"sit":
				_rest_go(&"sit", -1.0)
			&"groom":
				_rest_go(&"groom", 6.0, &"sit")
			&"lie":
				_rest_go(&"lie", -1.0)
			_:
				_rest_go(nxt, -1.0)
		return
	# deeper rest after long inactivity (only when the player left Cam alone)
	if _rest_len < 0.0 and is_input_enabled():
		if _rest_phase == &"sit" and _idle_t > idle_groom_after and _idle_t < idle_groom_after + 1.0:
			_rest_go(&"groom", 6.5, &"sit")
		elif _rest_phase == &"sit" and _idle_t > idle_lie_after:
			_rest_go(&"lie_down", _clip_length(&"lie_down", 1.2), &"lie")
		elif _rest_phase == &"lie" and _idle_t > idle_sleep_after:
			_rest_go(&"sleep", -1.0)


func _enter_ground() -> void:
	mode = Mode.GROUND
	_rest_phase = &""
	_action_name = &""
	_land_t = 0.0
	_hide_reticle()
	_update_ground_state(0.0)


# =============================================================================================
# Visual (slope alignment, step smoothing, lean, climb/swim orientation)
# =============================================================================================

func _update_visual(delta: float) -> void:
	if _visual == null:
		return
	var k := 1.0 - exp(-10.0 * delta)
	var pitch_t := 0.0
	var roll_t := 0.0
	var offset_t := 0.0
	var on_ground := mode in [Mode.GROUND, Mode.CROUCH, Mode.TURN, Mode.ACTION, Mode.REST]
	if on_ground:
		var base := global_position.y
		if _probe_front > -INF and _probe_back > -INF:
			var df := clampf(_probe_front - base, -0.25, 0.25)
			var db := clampf(_probe_back - base, -0.25, 0.25)
			pitch_t = atan2(db - df, 0.32)
		elif _probe_back > -INF and _probe_front == -INF:
			pitch_t = 0.0  # front paws over the edge: stay level, never dip into the void
		if _probe_left > -INF and _probe_right > -INF and not _balancing:
			roll_t = atan2(clampf(_probe_left - base, -0.1, 0.1) - clampf(_probe_right - base, -0.1, 0.1), 0.12)
		if _probe_center > -INF:
			offset_t = clampf(_probe_center - base, -0.1, 0.02)
		elif _probe_front > -INF and _probe_back > -INF:
			offset_t = clampf((_probe_front + _probe_back) * 0.5 - base, -0.1, 0.02)
		pitch_t = clampf(pitch_t, deg_to_rad(-35.0), deg_to_rad(35.0))
		roll_t = clampf(roll_t, deg_to_rad(-18.0), deg_to_rad(18.0))
		# lean into turns (running cats bank)
		roll_t += clampf(-_yaw_rate * absf(_speed) * 0.06, -0.2, 0.2)
		if _balancing:
			roll_t += sin(Time.get_ticks_msec() * 0.0021) * 0.025 * (1.0 - GameState.get_modifier(&"balance"))
	elif mode == Mode.AIR:
		# nose follows the flight path a little
		var hv := Vector2(velocity.x, velocity.z).length()
		pitch_t = clampf(-atan2(velocity.y, maxf(hv, 0.5)) * 0.35, -0.35, 0.45)
	_vis_pitch = lerpf(_vis_pitch, pitch_t, k)
	_vis_roll = lerpf(_vis_roll, roll_t, k)
	_vis_offset_y = lerpf(_vis_offset_y, offset_t, 1.0 - exp(-14.0 * delta))
	_step_offset = lerpf(_step_offset, 0.0, 1.0 - exp(-16.0 * delta))
	var climb_goal := 1.0 if mode == Mode.CLIMB else 0.0
	if mode == Mode.SCRAMBLE:
		climb_goal = 0.5 * (1.0 - clampf(_scr_t / _scr_len, 0.0, 1.0))
	_vis_climb = move_toward(_vis_climb, climb_goal, delta * 5.0)
	_vis_swim = move_toward(_vis_swim, 1.0 if mode == Mode.SWIM else 0.0, delta * 4.0)
	var b := Basis.from_euler(Vector3(_vis_pitch, 0.0, _vis_roll))
	var off := Vector3(0.0, _vis_offset_y + _step_offset, 0.0)
	if _vis_climb > 0.0:
		# belly to the wall, head up: rotate -90° about the body's right axis, feet on the wall
		var c := _vis_climb * _vis_climb * (3.0 - 2.0 * _vis_climb)
		b = Basis(Vector3.RIGHT, -PI * 0.5 * c) * b
		var wall_dist := body_radius + 0.012
		off += Vector3(0.0, 0.1 * c, wall_dist * c)
	if _vis_swim > 0.0:
		b = Basis(Vector3.RIGHT, -0.12 * _vis_swim) * b
	_visual.transform = Transform3D(b, off)


func _update_look_target() -> void:
	if _look_target == null:
		return
	var head := global_position + Vector3.UP * 0.24 + _forward() * 0.2
	var goal := head + _forward() * 2.0
	if _camera_rig != null:
		var f: Vector3 = _camera_rig.call(&"get_view_forward")
		# look where the player looks (within the neck's comfort zone)
		if f.dot(_forward()) > -0.2 or is_first_person():
			goal = head + f * 2.0
	if _interaction != null:
		var poi: Vector3 = _interaction.call(&"get_focus_point")
		if poi != Vector3.INF and not is_first_person():
			goal = poi
	if not _target.is_empty() and mode == Mode.CROUCH:
		goal = _target["point"]
	_look_target.global_position = _look_target.global_position.lerp(goal, 0.2) if _look_target.global_position.distance_to(goal) < 4.0 else goal


func _update_gait_phase(delta: float) -> void:
	var spd := absf(_speed) if mode == Mode.GROUND else 0.0
	var stride := 0.5
	if spd > walk_speed * 1.3:
		stride = 0.7 if spd < trot_speed * 1.4 else 1.4
	var prev := _gait_phase
	_gait_phase = fmod(_gait_phase + spd / stride * delta, 1.0)
	# footstep events (4 paw contacts per cycle)
	if spd > 0.05 and is_on_floor():
		var q_prev := int(floor(prev * 4.0))
		var q_now := int(floor(_gait_phase * 4.0))
		if q_prev != q_now:
			_footstep(spd)
	if GameState.wetness > 0.35 and mode == Mode.GROUND:
		_wet_drip_t += delta
		if _wet_drip_t > 0.35 and _fx != null:
			_wet_drip_t = 0.0
			_fx.call(&"drip", global_position + Vector3.UP * 0.12)


func _footstep(spd: float) -> void:
	_step_count += 1
	# AudioManager scale: sneak ≈ 0.2, walk ≈ 0.45, trot ≈ 0.65, run ≈ 0.9
	var intensity := clampf(0.25 + 0.65 * sqrt(clampf(spd / run_speed, 0.0, 1.0)), 0.08, 1.0)
	if _sneaking or _crawling:
		intensity *= 0.45
	var am := get_node_or_null(^"/root/AudioManager")
	if am != null and am.has_method(&"play_footstep"):
		am.call(&"play_footstep", _surface, global_position, intensity)


# =============================================================================================
# Misc helpers
# =============================================================================================

func _set_state(s: StringName) -> void:
	if s == state:
		return
	var old := state
	state = s
	state_changed.emit(old, s)
	GameEvents.player_state_changed.emit(old, s)
	if _anim != null:
		_anim.call(&"on_state_changed", old, s)


func _clip_length(clip: StringName, fallback: float) -> float:
	if _anim != null and _anim.has_method(&"get_clip_length"):
		var l := float(_anim.call(&"get_clip_length", clip))
		if l > 0.0:
			return l
	return fallback


func _update_floor_surface() -> void:
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		if c.get_normal().y > 0.6:
			_floor_collider = c.get_collider()
			_surface = _surface_of(_floor_collider)
			return


static var _surface_script: GDScript = null
static var _surface_checked := false


static func _surface_of(collider: Object) -> StringName:
	if collider == null:
		return &"concrete"
	if not _surface_checked:
		_surface_checked = true
		if ResourceLoader.exists("res://scripts/world/surface.gd"):
			_surface_script = load("res://scripts/world/surface.gd") as GDScript
	if _surface_script != null:
		var s: Variant = _surface_script.call(&"get_surface", collider)
		if s is StringName and s != &"":
			return s
		if s is String and s != "":
			return StringName(s)
	var n := collider as Node
	while n != null:
		if n.has_meta(&"surface"):
			return StringName(str(n.get_meta(&"surface")))
		n = n.get_parent()
		if n is Window:
			break
	var co := collider as CollisionObject3D
	if co != null and (co.collision_layer & L_WATER) != 0:
		return &"water"
	return &"concrete"


func _play_sfx(sfx_name: StringName, pos: Vector3, volume_db := 0.0) -> void:
	var am := get_node_or_null(^"/root/AudioManager")
	if am != null and am.has_method(&"play_sfx"):
		am.call(&"play_sfx", sfx_name, pos, volume_db)


func _on_dialogue_started(_id: StringName, _speaker: StringName) -> void:
	_dialogue_lock = true
	_hide_reticle()
	if mode == Mode.GROUND and absf(_speed) < 0.8:
		_enter_rest(&"sit")


func _on_dialogue_ended(_id: StringName) -> void:
	_dialogue_lock = false


func _on_dialogue_choice(_id: StringName, action: StringName) -> void:
	if action != &"":
		play_action(action)


func _on_mouth_item_changed(item_id: StringName) -> void:
	if _held_visual != null and is_instance_valid(_held_visual):
		_held_visual.queue_free()
	_held_visual = null
	if item_id == &"" or _mouth_attach == null:
		return
	var v := PickupItem.create_item_visual(item_id)
	if v == null:
		return
	_held_visual = Node3D.new()
	_held_visual.name = "HeldItem"
	_mouth_attach.add_child(_held_visual)
	_held_visual.add_child(v)
	# centre the item's bounds on the socket, long axis across the jaw (socket X = lateral)
	var ab := _local_aabb(v)
	if ab.size.x < ab.size.z:
		v.rotation.y = PI * 0.5
	v.position = -(v.basis * ab.get_center())
	for mi in v.find_children("*", "GeometryInstance3D", true, false):
		(mi as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON


## Bounds of every VisualInstance3D under `root`, in root's local space (root must be in the tree).
static func _local_aabb(root: Node3D) -> AABB:
	var out := AABB()
	var first := true
	var inv := root.global_transform.affine_inverse()
	for c in root.find_children("*", "VisualInstance3D", true, false):
		var vi := c as VisualInstance3D
		var ab := (inv * vi.global_transform) * vi.get_aabb()
		if first:
			out = ab
			first = false
		else:
			out = out.merge(ab)
	return out


func _on_fainted(_cause: StringName, _caps: int) -> void:
	_enter_rest(&"lie")
	_rest_go(&"lie_down", _clip_length(&"lie_down", 1.2), &"lie")


func _on_revived(_at: Transform3D) -> void:
	if mode == Mode.REST:
		_rest_go(&"stretch", _clip_length(&"stretch", 1.6) * 0.8, &"_done")
