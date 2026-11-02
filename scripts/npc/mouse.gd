extends "res://scripts/npc/npc_base.gd"
## Mouse (owner: world-life) — catchable prey around market alleys and drains.
## Forages near its hole (the spawn marker) in short dashes with sniff / rear-up pauses, mostly at
## dusk/night (in the daytime it stays hidden unless meta `day_active`). Flees from Cam (flee
## radius shrinks a lot when sneaking) back to its hole, where it hides for a while. A swipe or a
## pounce landing on it tries to catch it (GameState catch_chance, mice are easier than birds):
## success registers the prey and the mouse "escapes" into the hole and respawns later.

enum S { HIDDEN, FORAGE, PAUSE, FLEE }

var state: S = S.FORAGE
var state_t := 0.0
var hole := Vector3.ZERO
var forage_radius := 4.0
var day_active := false
var _rng := RandomNumberGenerator.new()
var _hide_for := 0.0
## For tests.
var flee_count := 0
var caught_count := 0


func _setup() -> void:
	_rng.randomize()
	npc_kind = &"mouse"
	set_meta(&"npc_kind", "mouse")
	add_to_group(&"prey")
	set_meta(&"prey_kind", "mouse")
	body_radius = 0.035
	body_height = 0.07
	walk_speed = 0.5
	run_speed = 2.6
	turn_rate = 14.0
	arrive_radius = 0.08
	use_navigation = false
	for c: Node in get_children():
		if c is CollisionShape3D:
			var sph := SphereShape3D.new()
			sph.radius = 0.035
			(c as CollisionShape3D).shape = sph
			(c as CollisionShape3D).position = Vector3(0, 0.036, 0)
	if nav != null:
		nav.queue_free()
		nav = null
	perception.eye_height = 0.04
	perception.fov_deg = 300.0
	perception.sight_range = 4.0
	perception.hearing_range = 12.0
	make_visual("mouse", {"model_names": ["mouse", "mouse_"]})
	var hb := preload("res://scripts/npc/prey_hitbox.gd").new()
	hb.name = "Hitbox"
	add_child(hb)
	hb.setup(self, 0, 0.07)


func init_from_marker(m: Node3D) -> void:
	hole = m.global_position
	forage_radius = float(NpcUtil.meta_or(m, &"roam_radius", 4.0))
	day_active = bool(NpcUtil.meta_or(m, &"day_active", false))
	teleport_to(hole, _rng.randf() * TAU)
	_enter(S.FORAGE)


func _enter(s: S) -> void:
	state = s
	state_t = 0.0
	if visual != null:
		visual.visible = s != S.HIDDEN


func _active_hours() -> bool:
	if day_active:
		return true
	var h := NpcUtil.hour()
	return h >= 17.5 or h < 6.5


func _think(dt: float) -> void:
	state_t += dt
	var player := get_player()
	var d := NpcUtil.flat_dist(player.global_position, global_position) if player != null else INF
	var r := 2.2 * NpcUtil.detection_mult()
	if player != null and NpcUtil.player_is_sneaking(player):
		r *= 0.4
	if state in [S.FORAGE, S.PAUSE] and (d < r or perception.heard_this_tick > 0.15 or perception.is_alerted()):
		_flee()
	match state:
		S.HIDDEN:
			stop_moving()
			if state_t > _hide_for and _active_hours() and d > 3.0:
				teleport_to(hole)
				_enter(S.FORAGE)
		S.FORAGE:
			play_anim(&"run")
			if move_target == Vector3.INF or arrived(0.1):
				_enter(S.PAUSE)
				stop_moving()
			elif state_t > 4.0:
				_enter(S.PAUSE)
		S.PAUSE:
			stop_moving()
			play_anim(&"idle")
			if state_t > _rng.randf_range(1.0, 3.5):
				if not _active_hours():
					go_to(hole, run_speed * 0.6)
					_enter(S.FLEE)
					return
				var off := Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)).normalized() * _rng.randf_range(0.4, 1.4)
				var g := global_position + off
				if NpcUtil.flat_dist(g, hole) > forage_radius:
					g = hole + NpcUtil.flat(g - hole).normalized() * forage_radius * 0.7
				go_to(g, _rng.randf_range(0.6, 1.4))
				_enter(S.FORAGE)
		S.FLEE:
			play_anim(&"run")
			if arrived(0.15) or state_t > 5.0:
				_hide(_rng.randf_range(8.0, 20.0))


func _flee() -> void:
	flee_count += 1
	NpcUtil.sfx(&"mouse_squeak", global_position, -10.0, 0.2)
	go_to(hole, run_speed)
	_enter(S.FLEE)


func _hide(t: float) -> void:
	_hide_for = t
	stop_moving()
	_enter(S.HIDDEN)


func on_part_swiped(_index: int, _by: Node) -> void:
	_try_catch()


func check_pounce(pos: Vector3) -> bool:
	if state == S.HIDDEN:
		return false
	if pos.distance_to(global_position) < 0.35 * NpcUtil.modifier(&"pounce_distance", 1.0):
		return _try_catch()
	return false


func _try_catch() -> bool:
	if state == S.HIDDEN:
		return false
	if NpcUtil.try_catch(&"mouse", -0.25):
		caught_count += 1
		NpcUtil.sfx(&"mouse_squeak", global_position, -4.0, 0.25)
		teleport_to(hole)
		_hide(_rng.randf_range(45.0, 120.0))
		return true
	_flee()
	return false


func set_lod(l: Lod, interval: float) -> void:
	super.set_lod(l, interval)
	if visual != null:
		visual.visible = l != Lod.ASLEEP and state != S.HIDDEN
