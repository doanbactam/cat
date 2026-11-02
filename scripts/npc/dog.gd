extends "res://scripts/npc/npc_base.gd"
## Vện — brindle market dog (owner: world-life). Patrol obstacle that chases but never hurts badly.
##
## States: PATROL (walks its `patrol_path` Path3D, pausing to sniff), REST (naps at its spawn in
## the midday heat and at night — far less perceptive), INVESTIGATE (suspicious: walks to the last
## stimulus and sniffs), CHASE (alerted: barks, runs at Cam), BARK_UP (cat on high ground / out of
## reach: barks at the base, loses interest), RETURN (cool-down, back to the route).
## A catch is a nip: small damage + knock-back, then Vện is satisfied for a while.
## Stealth works: sneaking shrinks the vision cone range, noise draws him, high ground (> 0.9 m
## above him) is unreachable. Group "dog" + npc_kind "dog" → AudioManager chase music on npc_alerted.

enum S { PATROL, REST, INVESTIGATE, CHASE, BARK_UP, RETURN }

const CHASE_SPEED := 4.2          # the cat's run is 4.5 m/s: a running cat can just escape
const GIVE_UP_DIST := 18.0
const NIP_DIST := 0.6
const HIGH_GROUND := 0.9

var state: S = S.PATROL
var state_t := 0.0
var patrol_path: Path3D = null
var patrol_points: PackedVector3Array = PackedVector3Array()
var patrol_index := 0
var home_xform := Transform3D.IDENTITY
var _pause_t := 0.0
var _bark_cd := 0.0
var _satisfied_t := 0.0
var _chase_lost_t := 0.0
var _pant: AudioStreamPlayer3D = null
var _rng := RandomNumberGenerator.new()
## For tests / debugging: how many times Vện caught the cat.
var nips := 0


func _setup() -> void:
	_rng.randomize()
	npc_kind = &"dog"
	set_meta(&"npc_kind", "dog")
	add_to_group(&"dog")
	walk_speed = 1.25
	run_speed = CHASE_SPEED
	body_radius = 0.22
	body_height = 0.6
	turn_rate = 8.0
	for c: Node in get_children():
		if c is CollisionShape3D:
			var cap := (c as CollisionShape3D).shape as CapsuleShape3D
			if cap != null:
				cap.radius = 0.2
				cap.height = 0.6
				(c as CollisionShape3D).position = Vector3(0, 0.3, 0)
	if nav != null:
		nav.radius = 0.25
		nav.height = 0.6
	perception.eye_height = 0.5
	perception.fov_deg = 220.0     # dogs have wide vision
	perception.sight_range = 11.0
	perception.hearing_range = 20.0
	perception.hearing_gain = 1.4
	perception.sight_gain = 1.6
	perception.proximity_radius = 1.4   # smell
	make_visual("dog", {"model_names": ["ven", "dog", "dog_"]})


func init_from_marker(m: Node3D, path: Path3D) -> void:
	home_xform = m.global_transform
	patrol_path = path
	patrol_points = PackedVector3Array()
	if path != null and path.curve != null:
		for i in path.curve.point_count:
			patrol_points.append(path.to_global(path.curve.get_point_position(i)))
	teleport_to(m.global_position, m.global_rotation.y)
	_enter(S.PATROL)


func _enter(s: S) -> void:
	state = s
	state_t = 0.0
	if s == S.CHASE:
		_chase_lost_t = 0.0


func _rest_hours() -> bool:
	var h := NpcUtil.hour()
	return h >= 23.0 or h < 5.0 or (h >= 12.5 and h < 14.0)


func _think(dt: float) -> void:
	state_t += dt
	_bark_cd = maxf(_bark_cd - dt, 0.0)
	_satisfied_t = maxf(_satisfied_t - dt, 0.0)
	var player := get_player()
	perception.deafness = 0.6 if state == S.REST else 0.0
	perception.enabled = _satisfied_t <= 0.0
	# --- transitions driven by perception -----------------------------------------------------
	if state in [S.PATROL, S.REST, S.INVESTIGATE, S.RETURN] and perception.enabled:
		if perception.is_alerted() and player != null:
			_start_chase()
		elif perception.is_suspicious() and state != S.INVESTIGATE and perception.last_stimulus_pos != Vector3.INF:
			if state == S.REST:
				play_anim_for(&"sit", 1.0)
			_enter(S.INVESTIGATE)
			NpcUtil.sfx(&"dog_growl", global_position + Vector3.UP * 0.4, -6.0)
	match state:
		S.PATROL:
			_patrol(dt)
		S.REST:
			stop_moving()
			play_anim(&"sleep")
			if not _rest_hours():
				play_anim_for(&"sit", 1.5)
				_enter(S.PATROL)
		S.INVESTIGATE:
			var tgt := perception.last_stimulus_pos
			if tgt == Vector3.INF or state_t > 12.0 or not perception.is_suspicious():
				_enter(S.RETURN)
			elif NpcUtil.flat_dist(global_position, tgt) < 0.9:
				stop_moving()
				play_anim(&"idle")
				face_point = tgt
			else:
				go_to(tgt, walk_speed * 1.2)
				play_anim(&"walk")
		S.CHASE:
			_chase(dt, player)
		S.BARK_UP:
			stop_moving()
			if player != null:
				face_point = player.global_position
				look_at_point(player.global_position)
			play_anim(&"bark")
			_maybe_bark(1.4)
			var reach := _reachable(player)
			if reach and player != null and NpcUtil.flat_dist(player.global_position, global_position) < 6.0:
				_enter(S.CHASE)
			elif state_t > _rng.randf_range(5.0, 8.0) or player == null:
				_lose_interest()
		S.RETURN:
			var back := _nearest_patrol_point()
			if NpcUtil.flat_dist(global_position, back) < 0.8 or state_t > 25.0:
				_enter(S.REST if _rest_hours() else S.PATROL)
			else:
				go_to(back, walk_speed)
				play_anim(&"walk")
	_update_pant()


func _patrol(dt: float) -> void:
	if _rest_hours():
		var home := home_xform.origin
		if NpcUtil.flat_dist(global_position, home) < 0.8:
			_enter(S.REST)
		else:
			go_to(home, walk_speed)
			play_anim(&"walk")
		return
	if patrol_points.is_empty():
		if move_target == Vector3.INF or arrived():
			go_to(NpcUtil.random_nav_point(get_world_3d(), home_xform.origin, 8.0), walk_speed)
		play_anim(&"walk")
		return
	if _pause_t > 0.0:
		_pause_t -= dt
		stop_moving()
		play_anim(&"idle" if _pause_t > 1.0 else &"sit")
		look_at_point(Vector3.INF)
		return
	var tgt := patrol_points[patrol_index]
	if NpcUtil.flat_dist(global_position, tgt) < 0.6:
		patrol_index = (patrol_index + 1) % patrol_points.size()
		if _rng.randf() < 0.35:
			_pause_t = _rng.randf_range(2.0, 5.0)    # sniff a corner
		tgt = patrol_points[patrol_index]
	go_to(tgt, walk_speed)
	play_anim(&"walk")


func _start_chase() -> void:
	_enter(S.CHASE)
	NpcUtil.sfx(&"dog_bark_series", global_position + Vector3.UP * 0.45, 0.0)
	_bark_cd = 1.5
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.npc_alerted.emit(self, 1.0)


func _chase(dt: float, player: Node3D) -> void:
	if player == null:
		_lose_interest()
		return
	var pp := player.global_position
	var d := NpcUtil.flat_dist(pp, global_position)
	if perception.can_see_player:
		_chase_lost_t = 0.0
		perception.force_awareness(1.0, pp)
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null and fmod(state_t, 2.0) < dt:
			ge.npc_alerted.emit(self, 1.0)   # keeps the chase music alive
	else:
		_chase_lost_t += dt
		pp = perception.last_seen_pos if perception.last_seen_pos != Vector3.INF else pp
	if not _reachable(player):
		_enter(S.BARK_UP)
		return
	if d > GIVE_UP_DIST or _chase_lost_t > 4.0 or state_t > 30.0:
		_lose_interest()
		return
	if d < NIP_DIST and absf(player.global_position.y - global_position.y) < 0.5:
		_nip(player)
		return
	go_to(pp, CHASE_SPEED)
	play_anim(&"run")
	_maybe_bark(2.2)


func _reachable(player: Node3D) -> bool:
	if player == null:
		return false
	var dy := player.global_position.y - global_position.y
	if dy > HIGH_GROUND:
		return false
	if nav != null and NpcUtil.nav_ready(get_world_3d()):
		var map := get_world_3d().navigation_map
		var cp := NavigationServer3D.map_get_closest_point(map, player.global_position)
		if cp.distance_to(player.global_position) > 1.0:
			return false
	return true


func _nip(player: Node3D) -> void:
	nips += 1
	stop_moving()
	play_anim_for(&"bark", 1.2)
	NpcUtil.sfx(&"dog_growl", global_position + Vector3.UP * 0.4, 0.0)
	var away := NpcUtil.flat(player.global_position - global_position).normalized()
	NpcUtil.hurt_player(player, 6.0, &"dog", away * 3.2 + Vector3.UP * 2.2)
	_satisfied_t = 14.0
	perception.force_awareness(0.0)
	_enter(S.RETURN)


func _lose_interest() -> void:
	NpcUtil.sfx(&"dog_whine", global_position + Vector3.UP * 0.4, -8.0)
	perception.force_awareness(0.2)
	_satisfied_t = 6.0
	look_at_point(Vector3.INF)
	face_point = Vector3.INF
	_enter(S.RETURN)


func _maybe_bark(interval: float) -> void:
	if _bark_cd > 0.0:
		return
	_bark_cd = interval * _rng.randf_range(0.8, 1.4)
	NpcUtil.sfx(&"dog_bark" if _rng.randf() < 0.6 else &"dog_bark_series", global_position + Vector3.UP * 0.45, -1.0)


func _nearest_patrol_point() -> Vector3:
	if patrol_points.is_empty():
		return home_xform.origin
	var best := patrol_points[0]
	var bd := INF
	for i in patrol_points.size():
		var d := patrol_points[i].distance_squared_to(global_position)
		if d < bd:
			bd = d
			best = patrol_points[i]
			patrol_index = i
	return best


func _update_pant() -> void:
	var want := state == S.CHASE and lod == Lod.NEAR
	if want and _pant == null:
		_pant = NpcUtil.loop(&"dog_pant_loop", self, -10.0)
	elif not want and _pant != null:
		NpcUtil.stop_loop(_pant, 0.6)
		_pant = null


func on_swiped(_by: Node) -> void:
	perception.force_awareness(1.0, get_player().global_position if get_player() != null else Vector3.INF)
	if _satisfied_t <= 0.0:
		_start_chase()


func get_state_name() -> StringName:
	return StringName(S.keys()[state])
