extends Node
## Interaction focus for Cam (owner: player).
##
## A sphere Area3D on the player watches layer 5 ("interactable"). Every few physics ticks the
## candidates (nodes in group "interactable" implementing the Interactable API) are scored by
## distance (relative to each one's interact_distance) and by angle from where the cat — or, in
## first person, the camera — is looking, with a line-of-sight check and hysteresis so focus does
## not flicker between two close objects. The winner gets a subtle rim highlight and
## GameEvents.interactable_focused(target, prompt) (re-emitted when the prompt text changes);
## interact_focused() calls can_interact()/interact() and emits GameEvents.interacted.

const OverlayUtil := preload("res://scripts/player/overlay_util.gd")
const FOCUS_SHADER := preload("res://shaders/player_focus.gdshader")
const L_WORLD := 1
const L_INTERACT := 1 << 4

@export var scan_radius := 2.4
@export var scan_interval := 0.08
@export var max_angle_deg := 105.0
@export var hysteresis := 0.12

var focused: Node = null
var _prompt := ""
var _player: CharacterBody3D
var _area: Area3D
var _t := 0.0
var _ray := PhysicsRayQueryParameters3D.new()
var _focus_mat: ShaderMaterial
var _highlighted: Node = null


func _ready() -> void:
	_player = get_parent() as CharacterBody3D
	_focus_mat = ShaderMaterial.new()
	_focus_mat.shader = FOCUS_SHADER
	_area = Area3D.new()
	_area.name = "InteractScan"
	_area.collision_layer = 0
	_area.collision_mask = L_INTERACT
	_area.monitoring = true
	_area.monitorable = false
	var cs := CollisionShape3D.new()
	var sph := SphereShape3D.new()
	sph.radius = scan_radius
	cs.shape = sph
	cs.position = Vector3(0.0, 0.15, 0.0)
	_area.add_child(cs)
	if _player != null:
		_player.add_child.call_deferred(_area)
		_ray.exclude = [_player.get_rid()]
	_ray.collision_mask = L_WORLD
	_ray.collide_with_areas = false


func _physics_process(delta: float) -> void:
	_t += delta
	if _t < scan_interval:
		return
	_t = 0.0
	rescan()


func _exit_tree() -> void:
	_set_highlight(null)


## Re-evaluates the best interactable now (also called before interacting).
func rescan() -> void:
	if _player == null or not _player.is_inside_tree():
		return
	var best: Node = null
	var best_score := INF
	var cur_score := INF
	var enabled: bool = _player.call(&"is_input_enabled") if _player.has_method(&"is_input_enabled") else true
	if enabled:
		for c in _candidates():
			var s := _score(c)
			if s < best_score:
				best_score = s
				best = c
			if c == focused:
				cur_score = s
	# hysteresis: keep the current focus unless the new one is clearly better
	if focused != null and is_instance_valid(focused) and best != focused and cur_score < INF and best_score > cur_score - hysteresis:
		best = focused
	_set_focus(best)


func _candidates() -> Array[Node]:
	var out: Array[Node] = []
	if _area.is_inside_tree() and _area.monitoring:
		for a in _area.get_overlapping_areas():
			if a.is_in_group(&"interactable") and a.has_method(&"can_interact"):
				out.append(a)
	return out


func _score(c: Node) -> float:
	var n3 := c as Node3D
	if n3 == null or not n3.is_visible_in_tree():
		return INF
	if c.has_method(&"is_visible_to") and not bool(c.call(&"is_visible_to", _player)):
		return INF
	var ipos: Vector3 = c.call(&"get_interaction_position") if c.has_method(&"get_interaction_position") else n3.global_position
	var reach := float(c.get(&"interact_distance")) + 0.35 if c.get(&"interact_distance") != null else 1.5
	var origin := _player.global_position
	var dist := origin.distance_to(n3.global_position)
	if dist > reach:
		return INF
	var head := origin + Vector3.UP * 0.2
	var facing := _facing()
	var to := ipos - head
	var flat := Vector3(to.x, 0.0, to.z)
	var ang := 0.0
	if flat.length() > 0.12:
		ang = acos(clampf(facing.dot(flat.normalized()), -1.0, 1.0))
		if ang > deg_to_rad(max_angle_deg):
			return INF
	# line of sight (ignore the object itself and its owner body)
	_ray.from = head
	_ray.to = ipos
	var hit := _player.get_world_3d().direct_space_state.intersect_ray(_ray)
	if not hit.is_empty():
		var col := hit.get("collider") as Node
		if col != null and not _related(col, c):
			if (hit["position"] as Vector3).distance_to(ipos) > 0.12:
				return INF
	var s := dist / maxf(reach, 0.1) + ang * 0.5
	if not bool(c.call(&"can_interact", _player)):
		s += 0.6
	return s


func _facing() -> Vector3:
	var f := _player.global_transform.basis.z
	if _player.has_method(&"is_first_person") and bool(_player.call(&"is_first_person")):
		var cam: Camera3D = _player.call(&"get_camera")
		if cam != null:
			f = -cam.global_transform.basis.z
	f.y = 0.0
	return f.normalized() if f.length_squared() > 0.0001 else Vector3.BACK


static func _related(a: Node, b: Node) -> bool:
	if a == b:
		return true
	if a.is_ancestor_of(b) or b.is_ancestor_of(a):
		return true
	var pa := a.get_parent()
	var pb := b.get_parent()
	return pa != null and pa == pb


func _set_focus(n: Node) -> void:
	if n != null and not is_instance_valid(n):
		n = null
	if n == focused:
		if n != null:
			var p := _prompt_of(n)
			if p != _prompt:
				_prompt = p
				GameEvents.interactable_focused.emit(n, _prompt)
		return
	if focused != null and is_instance_valid(focused):
		GameEvents.interactable_unfocused.emit(focused)
	focused = n
	_prompt = ""
	if focused != null:
		_prompt = _prompt_of(focused)
		GameEvents.interactable_focused.emit(focused, _prompt)
	_set_highlight(focused)


func _prompt_of(n: Node) -> String:
	return String(n.call(&"get_prompt", _player)) if n.has_method(&"get_prompt") else ""


func _set_highlight(n: Node) -> void:
	if _highlighted != null and is_instance_valid(_highlighted):
		OverlayUtil.clear_layer(_highlighted, &"focus")
	_highlighted = null
	if n == null or not n.has_method(&"get_highlight_node"):
		return
	var h: Node3D = n.call(&"get_highlight_node")
	if h == null:
		return
	_highlighted = h
	OverlayUtil.set_layer(h, &"focus", _focus_mat)


## Interacts with the focused object. `verb_filter` (e.g. &"pickup") restricts which verbs the
## button may trigger. Returns true when an interaction happened.
func interact_focused(verb_filter: StringName = &"") -> bool:
	rescan()
	if focused == null or not is_instance_valid(focused):
		return false
	var verb := StringName(str(focused.get(&"verb"))) if focused.get(&"verb") != null else &"interact"
	if verb_filter != &"" and verb != verb_filter:
		return false
	if not bool(focused.call(&"can_interact", _player)):
		if _player.has_method(&"on_interaction_refused"):
			_player.call(&"on_interaction_refused", focused)
		return false
	var target := focused
	if _player.has_method(&"face_point") and target is Node3D:
		_player.call(&"face_point", (target as Node3D).global_position)
	target.call(&"interact", _player)
	GameEvents.interacted.emit(target, verb)
	# the object may have been freed / changed: refresh focus right away
	if not is_instance_valid(target) or not target.is_inside_tree():
		focused = null
		_set_highlight(null)
	rescan()
	return true


func get_focused() -> Node:
	return focused if focused != null and is_instance_valid(focused) else null


func get_focus_point() -> Vector3:
	var f := get_focused()
	if f == null:
		return Vector3.INF
	if f.has_method(&"get_interaction_position"):
		return f.call(&"get_interaction_position")
	return (f as Node3D).global_position


func get_prompt() -> String:
	return _prompt


func has_npc_nearby(radius := 3.5) -> bool:
	if _player == null:
		return false
	for n in _player.get_tree().get_nodes_in_group(&"npc"):
		var n3 := n as Node3D
		if n3 != null and n3.global_position.distance_squared_to(_player.global_position) < radius * radius:
			return true
	return false
