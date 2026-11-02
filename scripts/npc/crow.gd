extends Node3D
## Crows and Lão Quạ (owner: world-life). Spawned at `npc_spawn` markers with npc_kind crow.
##
## Ambient crows perch on high points (marker + `perch_points` meta or auto-found rooftops),
## hop along the perch, preen, caw (crow_caw / crow_caw_series / crow_rattle), watch Cam, and hop
## off to another perch when the cat gets too close or noisy; at dawn/dusk they sometimes drop to
## the ground to scavenge near the marker.
## Lão Quạ (npc_id lao_qua) is the old trader crow at the lake banyan: he never flees from Cam,
## shuffles between 3 favourite spots on his branch, greets Cam with a caw series, sleeps with
## his head tucked at night, and when Cam carries something shiny in her mouth he flutters down
## to inspect it (ground spot next to the trunk) — then returns to his branch. Talkable "lao_qua".

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")
const TALKABLE_PATH := "res://scripts/systems/talkable.gd"

enum S { PERCH, HOP, FLY, GROUND, SLEEP }

var npc_id: StringName = &""
var director: Node = null
var visual: Node3D = null
var state: S = S.PERCH
var state_t := 0.0
var home := Vector3.ZERO
var home_yaw := 0.0
var spots: Array[Vector3] = []
var spot_index := 0
var lod := 0
var _pos := Vector3.ZERO
var _vel := Vector3.ZERO
var _goal := Vector3.ZERO
var _after_fly: S = S.PERCH
var _caw_cd := 3.0
var _greeted := false
var _rng := RandomNumberGenerator.new()
var _yaw := 0.0
var talkable: Node = null


func setup(marker: Node3D, p_npc_id: StringName) -> void:
	_rng.randomize()
	npc_id = p_npc_id
	name = String(npc_id) if npc_id != &"" else "Crow"
	add_to_group(&"npc")
	set_meta(&"npc_kind", "crow")
	if npc_id != &"":
		set_meta(&"npc_id", String(npc_id))
	home = marker.global_position
	if bool(NpcUtil.meta_or(marker, &"snap_to_surface", false)) and marker.is_inside_tree():
		var hit := NpcUtil.ray(marker.get_world_3d(), home + Vector3.UP * 0.3, home - Vector3.UP * 40.0, NpcUtil.LAYER_WORLD | NpcUtil.LAYER_CLIMBABLE)
		if not hit.is_empty():
			home = hit["position"]
	home_yaw = marker.global_rotation.y
	_yaw = home_yaw
	spots.append(home)
	for pp: Variant in NpcUtil.meta_or(marker, &"perch_points", []):
		if pp is Vector3:
			spots.append(pp)
	if spots.size() < 3:
		# shuffle spots along the branch/ridge either side of the marker
		var side := Basis(Vector3.UP, home_yaw).x
		spots.append(home + side * 0.45)
		spots.append(home - side * 0.4 + Vector3.UP * 0.05)
	visual = NpcVisualScript.new()
	visual.name = "Visual"
	add_child(visual)
	var scale_f := 1.12 if npc_id == &"lao_qua" else 1.0
	visual.call(&"setup", "crow", {"model_names": ([String(npc_id)] if npc_id != &"" else []) + ["crow", "crow_"]})
	visual.scale = Vector3.ONE * scale_f
	_pos = home
	global_position = home
	rotation.y = _yaw
	if npc_id != &"" and ResourceLoader.exists(TALKABLE_PATH):
		talkable = (load(TALKABLE_PATH) as Script).new() as Node
		talkable.name = "Talkable"
		talkable.set(&"dialogue_id", npc_id)
		talkable.set(&"speaker_id", npc_id)
		talkable.set(&"interact_distance", 2.2)
		talkable.set(&"shape_radius", 0.35)
		talkable.set(&"shape_offset", Vector3(0, 0.15, 0))
		add_child(talkable)


func is_special() -> bool:
	return npc_id == &"lao_qua"


func _physics_process(delta: float) -> void:
	if lod >= 3:
		return
	state_t += delta
	_caw_cd = maxf(_caw_cd - delta, 0.0)
	var player := _player()
	var in_dialogue := talkable != null and _dialogue_active()
	match state:
		S.PERCH:
			_perch(delta, player, in_dialogue)
		S.HOP:
			var t := clampf(state_t / 0.35, 0.0, 1.0)
			var p := _pos.lerp(_goal, t) + Vector3.UP * sin(t * PI) * 0.12
			global_position = p
			visual.call(&"play", &"takeoff")
			if t >= 1.0:
				_pos = _goal
				_enter(S.PERCH)
		S.FLY:
			_fly(delta)
		S.GROUND:
			_ground(delta, player)
		S.SLEEP:
			visual.call(&"play", &"idle")
			visual.call(&"set_head_look", 2.6, 0.4)     # head tucked over the back
			if not _is_night():
				visual.call(&"set_head_look", 0.0, 0.0)
				_enter(S.PERCH)
	rotation.y = NpcUtil.approach_angle(rotation.y, _yaw, 5.0 * delta)
	if lod <= 1:
		visual.call(&"tick", delta)


func _enter(s: S) -> void:
	state = s
	state_t = 0.0


func _perch(_delta: float, player: Node3D, in_dialogue: bool) -> void:
	global_position = _pos
	var d := player.global_position.distance_to(_pos) if player != null else INF
	if in_dialogue and player != null:
		_yaw = NpcUtil.yaw_of(NpcUtil.flat(player.global_position - _pos))
		visual.call(&"play", &"caw" if fmod(state_t, 3.0) < 0.6 else &"idle")
		return
	if _is_night() and state_t > 4.0 and (d > 3.0 or is_special()):
		_enter(S.SLEEP)
		return
	if player != null and d < 8.0:
		var look := wrapf(NpcUtil.yaw_of(NpcUtil.flat(player.global_position - _pos)) - rotation.y, -PI, PI)
		visual.call(&"set_head_look", look, 0.3)
		if is_special():
			if not _greeted and d < 5.0:
				_greeted = true
				_caw(&"crow_caw_series")
			if _carrying_shiny() and d < 6.0 and state_t > 2.0:
				_fly_to(_ground_spot_near(player.global_position), S.GROUND)
				return
		else:
			var loud := NpcUtil.player_velocity(player).length() > 1.8 and not NpcUtil.player_is_sneaking(player)
			if d < (1.6 if NpcUtil.player_is_sneaking(player) else 3.2) or (loud and d < 5.0):
				_caw(&"crow_caw")
				_flee_perch(player.global_position)
				return
	elif d > 12.0:
		_greeted = false
	# idle life on the perch
	if state_t > _rng.randf_range(4.0, 9.0):
		var r := _rng.randf()
		if r < 0.35:
			spot_index = (spot_index + 1 + _rng.randi() % maxi(spots.size() - 1, 1)) % spots.size()
			_goal = spots[spot_index]
			_yaw = NpcUtil.yaw_of(NpcUtil.flat(_goal - _pos)) if NpcUtil.flat(_goal - _pos).length() > 0.05 else _yaw
			_enter(S.HOP)
			return
		elif r < 0.55 and _caw_cd <= 0.0:
			_caw(&"crow_caw" if _rng.randf() < 0.7 else &"crow_rattle")
		elif r < 0.7 and not is_special() and _is_twilight():
			_fly_to(_ground_spot_near(home), S.GROUND)
			return
		state_t = 0.0
	visual.call(&"play", &"caw" if _caw_cd > 2.2 else (&"peck" if fmod(state_t, 7.0) > 6.0 else &"idle"))


func _ground(_delta: float, player: Node3D) -> void:
	global_position = _pos
	visual.call(&"play", &"peck" if fmod(state_t, 3.0) < 1.6 else &"idle")
	var d := player.global_position.distance_to(_pos) if player != null else INF
	if player != null:
		_yaw = NpcUtil.yaw_of(NpcUtil.flat(player.global_position - _pos)) if d < 4.0 else _yaw
	var leave := state_t > 14.0
	if is_special():
		leave = (not _carrying_shiny() and state_t > 3.0) or d > 7.0
	elif player != null and d < 2.4:
		leave = true
	if leave:
		_fly_to(spots[spot_index], S.PERCH)


func _fly_to(goal: Vector3, then: S) -> void:
	_goal = goal
	_after_fly = then
	_vel = Vector3.UP * 2.0 + NpcUtil.flat(goal - _pos).normalized() * 1.5
	NpcUtil.sfx(&"pigeon_takeoff", _pos, -6.0, 0.15)
	_enter(S.FLY)


func _fly(delta: float) -> void:
	var to := _goal - _pos
	var d := to.length()
	var desired := to.normalized() * clampf(d * 1.5, 1.2, 7.0)
	if d > 3.0 and to.y < 1.0:
		desired.y += 1.5      # arc over obstacles
	_vel = _vel.lerp(desired, 1.0 - exp(-3.0 * delta))
	_pos += _vel * delta
	global_position = _pos
	if NpcUtil.flat(_vel).length() > 0.1:
		_yaw = NpcUtil.yaw_of(_vel)
	visual.call(&"play", &"land" if d < 1.5 else &"fly")
	if d < 0.1 or state_t > 10.0:
		_pos = _goal
		global_position = _pos
		_enter(_after_fly)


func _flee_perch(from: Vector3) -> void:
	var best := home + Vector3.UP * 4.0
	var best_d := -1.0
	for s: Vector3 in spots:
		var dd := s.distance_to(from)
		if dd > best_d:
			best_d = dd
			best = s
	if best_d < 4.0:
		best = best + Vector3.UP * 2.5
	_fly_to(best, S.PERCH)


func _ground_spot_near(p: Vector3) -> Vector3:
	var off := NpcUtil.flat(home - p)
	var g := p + (off.normalized() * 0.9 if off.length() > 0.1 else Vector3(0.9, 0, 0))
	var y := NpcUtil.ground_y(get_world_3d(), g, 1.0, 6.0)
	return Vector3(g.x, p.y if is_nan(y) else y, g.z)


func _caw(snd: StringName) -> void:
	_caw_cd = 2.8
	NpcUtil.sfx(snd, _pos + Vector3.UP * 0.2, -3.0 if is_special() else -6.0)


func _carrying_shiny() -> bool:
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null:
		return false
	var item := StringName(gs.get(&"mouth_item"))
	if item == &"":
		return false
	var def: Dictionary = gs.call(&"get_item_def", item) if gs.has_method(&"get_item_def") else {}
	var cat := str(def.get("category", ""))
	return bool(def.get("shiny", false)) or cat == "shiny" or cat == "trinket" or "shiny" in str(def.get("tags", ""))


func _dialogue_active() -> bool:
	var dm := get_node_or_null(^"/root/DialogueManager")
	return dm != null and dm.has_method(&"is_active") and bool(dm.call(&"is_active")) and _player() != null \
		and _player().global_position.distance_to(_pos) < 3.0


func _is_night() -> bool:
	return NpcUtil.night_factor() > 0.7


func _is_twilight() -> bool:
	var h := NpcUtil.hour()
	return (h > 5.5 and h < 7.5) or (h > 17.0 and h < 18.5)


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func set_lod(l: int, _interval: float) -> void:
	lod = l
	visible = l < 3


func on_dialogue_started(_id: StringName) -> void:
	_caw(&"crow_caw_series")


func on_dialogue_ended(_id: StringName) -> void:
	pass
