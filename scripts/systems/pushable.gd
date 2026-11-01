class_name Pushable
extends RigidBody3D
## A small dynamic prop Cam can knock over / push off ledges (cups, pots, cans, slippers...).
## knock(direction) applies a paw-swipe impulse; when the object then drops at least
## `min_fall_height` metres and comes to rest (or hits something) it counts as "knocked off a
## ledge": GameState.register_knock (counters, achievement "knock_it_off"), GameEvents.
## object_knocked_off (→ knock_objects objectives), a noise event for NPC hearing and an impact SFX.
## Layer 4 "props_dynamic"; collides with world, player, other props and vehicles. An Interactable
## child (verb "knock") is created so the player's interaction scan finds it.

signal knocked(by: Node)
signal fell_off_ledge(height: float)

const LAYER_WORLD := 1
const LAYER_PLAYER := 1 << 1
const LAYER_PROPS := 1 << 3
const LAYER_VEHICLES := 1 << 7

## Stable id (dedupes the "knocked N different objects" counters). Defaults to the node path.
@export var object_id: StringName = &""
## Swipe impulse, as velocity change in m/s (multiplied by mass). With the default friction
## (0.45, ceramic on wood) a 2 m/s swipe slides a cup ≈ 0.45 m — enough to clear a ledge edge.
@export var knock_speed := 2.0
@export var min_fall_height := 0.5
## Loudness (0..1) of the landing at 1 m fall; scales with height and mass.
@export_range(0.0, 1.0, 0.01) var noise_loudness := 0.6
## Impact sound = "<impact_sfx>_<material_kind>" from the audio bank (impact_ceramic, impact_metal,
## impact_plastic, impact_wood, impact_cardboard, impact_soft, impact_glass_clink).
@export var impact_sfx: StringName = &"impact"
@export var material_kind: StringName = &"ceramic"
@export var break_sfx: StringName = &"impact_glass_break"
## Break into nothing (freed) after a fall higher than this. < 0 = never breaks.
@export var break_height := -1.0
## Create the "knock" interaction area automatically.
@export var add_interact_area := true
@export var interact_radius := 0.35
## Count as knocked also when the player simply walks it off a ledge (body contact).
@export var count_player_bumps := true

var _armed := false
var _armed_time := 0.0
var _start_y := 0.0
var _max_drop := 0.0
var _rest_time := 0.0
var _impact_speed := 0.0
var _prev_velocity := Vector3.ZERO
var _interact: Interactable = null


func _ready() -> void:
	add_to_group(&"pushable")
	add_to_group(&"knockable")
	collision_layer = LAYER_PROPS
	collision_mask = LAYER_WORLD | LAYER_PLAYER | LAYER_PROPS | LAYER_VEHICLES
	contact_monitor = true
	max_contacts_reported = maxi(max_contacts_reported, 4)
	continuous_cd = true
	if has_meta(&"mass"):
		mass = float(get_meta(&"mass"))
	if object_id == &"":
		object_id = StringName(String(get_path()).trim_prefix("/root/"))
	if physics_material_override == null:
		var pm := PhysicsMaterial.new()
		pm.friction = 0.45
		pm.bounce = 0.12
		physics_material_override = pm
	_ensure_shape()
	body_entered.connect(_on_body_entered)
	if add_interact_area:
		_create_interact_area()


func _ensure_shape() -> void:
	for c in get_children():
		if c is CollisionShape3D or c is CollisionPolygon3D:
			return
	var cs := CollisionShape3D.new()
	cs.name = "AutoShape"
	var sh := CylinderShape3D.new()
	sh.radius = 0.04
	sh.height = 0.1
	cs.shape = sh
	cs.position.y = 0.05
	add_child(cs)


func _create_interact_area() -> void:
	var a := Interactable.new()
	a.name = "KnockArea"
	a.verb = &"knock"
	a.target_id = object_id
	a.shape_radius = interact_radius
	a.shape_offset = Vector3(0.0, 0.05, 0.0)
	a.interact_distance = 0.9
	a.player_action = &"knock"
	a.display_name_key = String(get_meta(&"name_key", "PROP_OBJECT"))
	a.used.connect(_on_knock_area_used)
	add_child(a)
	_interact = a


func _on_knock_area_used(player: Node) -> void:
	var dir := Vector3.FORWARD
	if player is Node3D:
		dir = global_position - (player as Node3D).global_position
	knock(dir, 1.0, player)


## Swipe the object along `direction` (horizontal component used). strength 0..2.
func knock(direction: Vector3, strength: float = 1.0, by: Node = null) -> void:
	var d := Vector3(direction.x, 0.0, direction.z)
	if d.length_squared() < 0.0001:
		d = Vector3.FORWARD
	d = d.normalized()
	_arm()
	sleeping = false
	var impulse := (d + Vector3.UP * 0.12) * knock_speed * clampf(strength, 0.0, 2.0) * mass
	# Hit a little above the centre of mass so it tips and tumbles like a real swipe.
	apply_impulse(impulse, Vector3(0.0, 0.04, 0.0))
	apply_torque_impulse(d.cross(Vector3.UP) * -0.02 * mass * strength)
	GameEvents.player_noise.emit(global_position, clampf(0.12 * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))
	knocked.emit(by)


func _arm() -> void:
	if not _armed:
		_start_y = global_position.y
		_max_drop = 0.0
	_armed = true
	_armed_time = 0.0
	_rest_time = 0.0
	_impact_speed = 0.0


func is_armed() -> bool:
	return _armed


func _physics_process(delta: float) -> void:
	if not _armed:
		return
	_armed_time += delta
	var drop := _start_y - global_position.y
	_max_drop = maxf(_max_drop, drop)
	var v := linear_velocity.length()
	if v < 0.12:
		_rest_time += delta
	else:
		_rest_time = 0.0
	if drop >= min_fall_height and (_rest_time > 0.25 or _impact_speed > 0.0):
		_register_fall(drop)
	elif _armed_time > 8.0 or (_rest_time > 1.0 and drop < min_fall_height):
		_armed = false
	_prev_velocity = linear_velocity


func _on_body_entered(body: Node) -> void:
	if body.is_in_group(&"player"):
		if count_player_bumps and not _armed:
			_arm()
		return
	if _armed and _start_y - global_position.y >= min_fall_height * 0.8:
		_impact_speed = maxf(_impact_speed, _prev_velocity.length())


func _register_fall(height: float) -> void:
	_armed = false
	var speed := maxf(_impact_speed, sqrt(2.0 * 9.8 * height))
	var loud := clampf(noise_loudness * (0.5 + height * 0.5) * clampf(mass / 0.4, 0.4, 1.6), 0.05, 1.0)
	GameState.register_knock(object_id)
	GameEvents.player_noise.emit(global_position, loud)
	GameEffects.play_sfx(StringName("%s_%s" % [impact_sfx, material_kind]), global_position, linear_to_db(clampf(speed / 6.0, 0.2, 1.0)))
	GameEvents.object_knocked_off.emit(self, object_id, height)
	fell_off_ledge.emit(height)
	if break_height >= 0.0 and height >= break_height:
		GameEffects.play_sfx(break_sfx, global_position)
		queue_free()
