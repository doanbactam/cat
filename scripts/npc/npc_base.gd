extends CharacterBody3D
## Base for every walking NPC (people, Vện, NPC cats, mice) — owner: world-life.
##
## * Movement: NavigationAgent3D (with RVO avoidance) toward `move_target` at `desired_speed`, or
##   straight-line steering when no navmesh exists; gravity; smooth yaw (model front = +Z).
## * AI: `_think(dt)` is called at the LOD tick rate set by LifeDirector (`think_interval`);
##   movement and animation run every physics frame while awake. Far agents use cheap
##   kinematic motion (no move_and_slide); sleeping agents are not processed at all.
## * Perception (scripts/npc/perception.gd) wired to GameEvents.player_noise.
## * Dialogue hooks used by scripts/systems/talkable.gd / DialogueManager:
##   on_dialogue_started(id), on_dialogue_ended(id), play_dialogue_anim(name).
## Groups: "npc" (+ meta npc_id, npc_kind) — cat-sense highlights these.

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const Perception := preload("res://scripts/npc/perception.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")
const TALKABLE_PATH := "res://scripts/systems/talkable.gd"

enum Lod { NEAR, MID, FAR, ASLEEP }

@export var npc_id: StringName = &""
@export var npc_kind: StringName = &"pedestrian"
@export var walk_speed := 1.25
@export var run_speed := 3.0
@export var turn_rate := 7.0
@export var body_radius := 0.25
@export var body_height := 1.6
@export var use_navigation := true

var director: Node = null
var visual: Node3D = null
var perception: Perception = null
var nav: NavigationAgent3D = null
var talkable: Node = null

var lod: Lod = Lod.NEAR
var think_interval := 0.0
var move_target := Vector3.INF
var desired_speed := 0.0
## When set, the body turns to face this point while standing (Vector3.INF = face velocity).
var face_point := Vector3.INF
var in_dialogue := false
var active := true
var gravity := 9.8
var arrive_radius := 0.35
## Walk straight at move_target (rooftop routes, ledges) instead of using the navmesh.
var direct_steering := false

var _think_accum := 0.0
var _safe_velocity := Vector3.ZERO
var _has_safe := false
var _last_nav_target := Vector3.INF
var _stuck_t := 0.0
var _last_pos := Vector3.ZERO
var _anim_override: StringName = &""
var _anim_override_t := 0.0
var _yaw := 0.0
var _avoid_block_t := 0.0


func _ready() -> void:
	add_to_group(&"npc")
	set_meta(&"npc_kind", String(npc_kind))
	if npc_id != &"":
		set_meta(&"npc_id", String(npc_id))
	collision_layer = NpcUtil.LAYER_NPC
	collision_mask = NpcUtil.LAYER_WORLD
	floor_snap_length = 0.35
	floor_max_angle = deg_to_rad(50.0)
	safe_margin = 0.02
	_ensure_shape()
	perception = Perception.new(self)
	perception.on_level_changed = _on_perception_level
	if use_navigation:
		_make_nav()
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_noise.connect(_on_player_noise)
	_yaw = rotation.y
	_last_pos = global_position
	_setup()


## Subclasses build visuals/talkables here.
func _setup() -> void:
	pass


func _ensure_shape() -> void:
	for c: Node in get_children():
		if c is CollisionShape3D:
			return
	var cs := CollisionShape3D.new()
	cs.name = "Shape"
	var cap := CapsuleShape3D.new()
	cap.radius = body_radius
	cap.height = maxf(body_height, body_radius * 2.0 + 0.01)
	cs.shape = cap
	cs.position = Vector3(0, cap.height * 0.5, 0)
	add_child(cs)


func _make_nav() -> void:
	nav = NavigationAgent3D.new()
	nav.name = "Nav"
	nav.radius = maxf(body_radius, 0.12)
	nav.height = body_height
	nav.path_desired_distance = 0.45
	nav.target_desired_distance = arrive_radius
	nav.max_speed = run_speed * 1.2
	nav.avoidance_enabled = true
	nav.neighbor_distance = 6.0
	nav.max_neighbors = 6
	nav.time_horizon_agents = 1.2
	nav.path_max_distance = 3.0
	nav.velocity_computed.connect(_on_velocity_computed)
	add_child(nav)


func make_visual(kind: String, opts: Dictionary) -> Node3D:
	visual = NpcVisualScript.new()
	visual.name = "Visual"
	add_child(visual)
	visual.call(&"setup", kind, opts)
	return visual


## Adds a systems Talkable (if the systems area provides it) so Cam can "talk" to this NPC.
func add_talkable(dialogue_id: StringName, speaker_id: StringName, distance := 1.6, offset := Vector3(0, 0.3, 0)) -> Node:
	if not ResourceLoader.exists(TALKABLE_PATH):
		NpcUtil.warn_once("no_talkable", "world-life: scripts/systems/talkable.gd missing; NPC talk disabled")
		return null
	var script := load(TALKABLE_PATH) as Script
	var t := script.new() as Node
	t.name = "Talkable"
	t.set(&"dialogue_id", dialogue_id)
	t.set(&"speaker_id", speaker_id)
	t.set(&"interact_distance", distance)
	t.set(&"shape_radius", 0.5)
	t.set(&"shape_offset", offset)
	add_child(t)
	talkable = t
	return t


# ------------------------------------------------------------------------------------------
# Per-frame
# ------------------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if not active:
		return
	_think_accum += delta
	if _think_accum >= think_interval:
		var dt := _think_accum
		_think_accum = 0.0
		if perception != null and lod <= Lod.MID:
			perception.update(dt, get_player())
		_think(dt)
	_move(delta)
	if _anim_override_t > 0.0:
		_anim_override_t -= delta
		if _anim_override_t <= 0.0:
			_anim_override = &""
	if visual != null and lod <= Lod.MID:
		visual.call(&"tick", delta)


func _think(_dt: float) -> void:
	pass


func get_player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func _move(delta: float) -> void:
	var pos := global_position
	var want := Vector3.ZERO
	if move_target != Vector3.INF and desired_speed > 0.01 and not in_dialogue:
		var next := move_target
		if nav != null and not direct_steering and NpcUtil.nav_ready(get_world_3d()) and lod <= Lod.MID:
			if _last_nav_target == Vector3.INF or _last_nav_target.distance_squared_to(move_target) > 0.09:
				nav.target_position = move_target
				_last_nav_target = move_target
			if not nav.is_navigation_finished():
				next = nav.get_next_path_position()
		var to := NpcUtil.flat(next - pos)
		var dist_goal := NpcUtil.flat_dist(pos, move_target)
		if dist_goal > arrive_radius and to.length() > 0.001:
			var slow := clampf(dist_goal / 0.8, 0.35, 1.0)
			want = to.normalized() * desired_speed * slow
	var hv := want
	if nav != null and not direct_steering and nav.avoidance_enabled and lod == Lod.NEAR:
		nav.velocity = want
		if _has_safe:
			hv = _safe_velocity
			# never let avoidance push us faster than intended
			if hv.length() > desired_speed * 1.1 + 0.01:
				hv = hv.normalized() * desired_speed * 1.1
			# RVO can deadlock (zero velocity) — fall back to the plain path velocity after a moment
			if want.length() > 0.2 and hv.length() < want.length() * 0.15:
				_avoid_block_t += delta
				if _avoid_block_t > 0.4:
					hv = want
			else:
				_avoid_block_t = 0.0
	var cur := NpcUtil.flat(velocity)
	var accel := 6.0 if hv.length() > cur.length() else 9.0
	cur = cur.move_toward(NpcUtil.flat(hv), accel * delta)
	if lod >= Lod.FAR:
		# cheap kinematic motion far away
		global_position += cur * delta
		velocity = cur
	else:
		velocity.x = cur.x
		velocity.z = cur.z
		if is_on_floor():
			velocity.y = -0.5
		else:
			velocity.y -= gravity * delta
		move_and_slide()
	_update_facing(delta, cur)
	var moved := NpcUtil.flat_dist(global_position, _last_pos)
	_last_pos = global_position
	if visual != null:
		visual.call(&"set_move_speed", moved / maxf(delta, 1e-4))
	# stuck detection → subclasses can repath
	if want.length() > 0.2 and moved < want.length() * delta * 0.15:
		_stuck_t += delta
		if _stuck_t > 2.0:
			_stuck_t = 0.0
			_on_stuck()
	else:
		_stuck_t = maxf(_stuck_t - delta, 0.0)


func _update_facing(delta: float, hv: Vector3) -> void:
	var target_yaw := _yaw
	if face_point != Vector3.INF and hv.length() < 0.3:
		var d := NpcUtil.flat(face_point - global_position)
		if d.length() > 0.05:
			target_yaw = NpcUtil.yaw_of(d)
	elif hv.length() > 0.08:
		target_yaw = NpcUtil.yaw_of(hv)
	_yaw = NpcUtil.approach_angle(_yaw, target_yaw, turn_rate * delta)
	rotation = Vector3(0.0, _yaw, 0.0)


func _on_velocity_computed(v: Vector3) -> void:
	_safe_velocity = v
	_has_safe = true


func _on_stuck() -> void:
	# nudge sideways and re-request the path
	_last_nav_target = Vector3.INF
	if move_target != Vector3.INF:
		var side := NpcUtil.flat(move_target - global_position).normalized().cross(Vector3.UP)
		global_position += side * randf_range(-0.3, 0.3)


func go_to(p: Vector3, speed: float) -> void:
	move_target = p
	desired_speed = speed


func stop_moving() -> void:
	move_target = Vector3.INF
	desired_speed = 0.0


func arrived(radius := -1.0) -> bool:
	if move_target == Vector3.INF:
		return true
	var r := arrive_radius if radius < 0.0 else radius
	return NpcUtil.flat_dist(global_position, move_target) <= r + 0.05


func play_anim(a: StringName) -> void:
	if _anim_override != &"":
		return
	if visual != null:
		visual.call(&"play", a)


## Plays `a` for `seconds`, ignoring play_anim() calls meanwhile.
func play_anim_for(a: StringName, seconds: float) -> void:
	_anim_override = &""
	if visual != null:
		visual.call(&"play", a)
	_anim_override = a
	_anim_override_t = seconds


func set_lod(l: Lod, interval: float) -> void:
	lod = l
	think_interval = interval
	var awake := l != Lod.ASLEEP
	set_physics_process(awake and active)
	if visual != null:
		visual.visible = awake or in_dialogue
	if nav != null:
		nav.avoidance_enabled = l == Lod.NEAR


func set_active(on: bool) -> void:
	active = on
	visible = on
	set_physics_process(on and lod != Lod.ASLEEP)
	process_mode = Node.PROCESS_MODE_INHERIT if on else Node.PROCESS_MODE_DISABLED
	collision_layer = NpcUtil.LAYER_NPC if on else 0
	if talkable != null:
		talkable.set(&"enabled", on)
		(talkable as Area3D).monitorable = on


func teleport_to(p: Vector3, yaw := NAN) -> void:
	global_position = p
	if not is_nan(yaw):
		_yaw = yaw
		rotation = Vector3(0, yaw, 0)
	velocity = Vector3.ZERO
	_last_pos = p
	_last_nav_target = Vector3.INF
	reset_physics_interpolation()


# ------------------------------------------------------------------------------------------
# Perception / events
# ------------------------------------------------------------------------------------------

func _on_player_noise(pos: Vector3, loudness: float) -> void:
	if not active or perception == null or lod >= Lod.FAR:
		return
	if global_position.distance_squared_to(pos) > 1600.0:
		return
	perception.notify_noise(pos, loudness)


func _on_perception_level(old_level: int, new_level: int) -> void:
	if new_level > old_level:
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null:
			ge.npc_alerted.emit(self, perception.awareness)
	_on_alert_changed(old_level, new_level)


func _on_alert_changed(_old_level: int, _new_level: int) -> void:
	pass


## Angle (radians, signed) from our facing to `p`, for head look.
func head_yaw_to(p: Vector3) -> float:
	var d := NpcUtil.flat(p - global_position)
	if d.length() < 0.01:
		return 0.0
	return wrapf(NpcUtil.yaw_of(d) - _yaw, -PI, PI)


func look_at_point(p: Vector3) -> void:
	if visual == null:
		return
	if p == Vector3.INF:
		visual.call(&"set_head_look", 0.0, 0.0)
		return
	var y := head_yaw_to(p)
	var dy := p.y - (global_position.y + body_height * 0.9)
	var pitch := atan2(-dy, maxf(NpcUtil.flat_dist(p, global_position), 0.1))
	visual.call(&"set_head_look", y, pitch)


# Dialogue hooks (systems Talkable / DialogueManager)
func on_dialogue_started(_id: StringName) -> void:
	in_dialogue = true
	stop_moving()
	var p := get_player()
	if p != null:
		face_point = p.global_position
		look_at_point(p.global_position)
	play_anim(&"talk")


func on_dialogue_ended(_id: StringName) -> void:
	in_dialogue = false
	face_point = Vector3.INF


func play_dialogue_anim(anim_name: StringName) -> void:
	var map := {&"give": &"sell", &"sad": &"look_down", &"hug_cat": &"pet_cat"}
	play_anim_for(StringName(map.get(anim_name, anim_name)), 2.5)


## Called by the director when this agent is recycled into the pool.
func on_despawn() -> void:
	stop_moving()
	face_point = Vector3.INF
	if perception != null:
		perception.force_awareness(0.0)
