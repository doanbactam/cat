extends Node3D
## Pigeon flock (owner: world-life) — spawned at an `npc_spawn` marker with npc_kind pigeon_flock.
##
## Ground birds walk with the pigeon head-bob, peck and idle inside `radius` of the marker,
## keeping personal space. They take off when Cam approaches fast or loud (flee radius grows with
## the cat's speed, shrinks a lot when sneaking and with Stealth/skills), when something honks or
## a loud noise lands nearby. In the air they flock with boids (separation, alignment, cohesion)
## plus escape → circle → perch on rooftops (`perch_points` meta or auto-found ledges) → return
## when the coast is clear. Each ground bird is prey (group "prey", prey_kind "pigeon"): a swipe or
## pounce on it tries GameState catch rules (needs the catch_birds ability; chance from
## catch_chance). Xám (npc_id xam) is a tame pigeon with a red leg band who never flees and
## carries the systems Talkable "xam".

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")
const Hitbox := preload("res://scripts/npc/prey_hitbox.gd")
const TALKABLE_PATH := "res://scripts/systems/talkable.gd"

enum B { GROUND, FLY, PERCH, LANDING, GONE }

@export var bird_kind := "pigeon"
@export var count := 12
@export var radius := 3.5
@export var flee_radius := 4.2
@export var walk_speed := 0.32
@export var fly_speed := 7.0

var director: Node = null
var center := Vector3.ZERO
var perch_points: Array[Vector3] = []
var birds: Array[Dictionary] = []
var lod := 0
var has_xam := false
var _think_t := 0.0
var _rng := RandomNumberGenerator.new()
var _calm_t := 0.0
var _airborne := false
## Statistics for tests.
var takeoffs := 0


func setup(p_center: Vector3, p_count: int, opts: Dictionary = {}) -> void:
	_rng.randomize()
	center = p_center
	count = p_count
	radius = float(opts.get("radius", radius))
	has_xam = bool(opts.get("xam", false))
	for pp: Variant in opts.get("perch_points", []):
		if pp is Vector3:
			perch_points.append(pp)
	add_to_group(&"npc")
	set_meta(&"npc_kind", "pigeon_flock")
	for i in count:
		_spawn_bird(i, i == 0 and has_xam)
	if perch_points.is_empty():
		_find_perches.call_deferred()


func _spawn_bird(i: int, is_xam: bool) -> void:
	var v := NpcVisualScript.new()
	v.name = "Xam" if is_xam else "Bird%d" % i
	add_child(v)
	v.top_level = true
	var tints: Array[Color] = [Color(0.58, 0.6, 0.66), Color(0.5, 0.52, 0.58), Color(0.66, 0.66, 0.68), Color(0.42, 0.40, 0.42),
		Color(0.70, 0.62, 0.55)]
	var tint := Color(0.62, 0.64, 0.7) if is_xam else tints[_rng.randi() % tints.size()]
	v.call(&"setup", bird_kind, {"model_names": [bird_kind, bird_kind + "_"], "tint": tint, "leg_band": is_xam})
	var p := _ground_point(center + _rand_disc(radius))
	v.global_position = p
	v.rotation.y = _rng.randf() * TAU
	v.add_to_group(&"npc")
	v.set_meta(&"npc_kind", "pigeon")
	if not is_xam:
		v.add_to_group(&"prey")
		v.set_meta(&"prey_kind", bird_kind)
	var hb := Hitbox.new()
	hb.name = "Hitbox"
	v.add_child(hb)
	hb.setup(self, i, 0.12)
	if is_xam:
		v.set_meta(&"npc_id", "xam")
		if ResourceLoader.exists(TALKABLE_PATH):
			var t := (load(TALKABLE_PATH) as Script).new() as Node
			t.name = "Talkable"
			t.set(&"dialogue_id", &"xam")
			t.set(&"speaker_id", &"xam")
			t.set(&"interact_distance", 1.2)
			t.set(&"shape_radius", 0.25)
			t.set(&"shape_offset", Vector3(0, 0.12, 0))
			v.add_child(t)
	birds.append({"node": v, "pos": p, "vel": Vector3.ZERO, "state": B.GROUND, "t": 0.0, "goal": p,
		"idle": _rng.randf_range(0.5, 3.0), "act": &"idle", "xam": is_xam, "delay": 0.0, "perch": Vector3.INF,
		"respawn": 0.0})


func _rand_disc(r: float) -> Vector3:
	var a := _rng.randf() * TAU
	var d := sqrt(_rng.randf()) * r
	return Vector3(cos(a) * d, 0.0, sin(a) * d)


func _ground_point(p: Vector3) -> Vector3:
	var y := NpcUtil.ground_y(get_world_3d(), p, 1.5, 4.0) if is_inside_tree() else NAN
	return Vector3(p.x, center.y if is_nan(y) else y, p.z)


## Finds rooftop ledges/eaves above the square to perch on (upward rays from a ring).
func _find_perches() -> void:
	if not is_inside_tree():
		return
	var world := get_world_3d()
	for i in 16:
		var a := TAU * float(i) / 16.0
		var p := center + Vector3(cos(a), 0, sin(a)) * _rng.randf_range(6.0, 14.0) + Vector3.UP * 25.0
		var hit := NpcUtil.ray(world, p, p - Vector3.UP * 30.0, NpcUtil.LAYER_WORLD | NpcUtil.LAYER_CLIMBABLE)
		if not hit.is_empty():
			var hp: Vector3 = hit["position"]
			if hp.y > center.y + 3.0 and (hit["normal"] as Vector3).y > 0.7:
				perch_points.append(hp)
	if perch_points.is_empty():
		perch_points.append(center + Vector3(0, 9, 0))


# ------------------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if lod >= 3:
		return
	_think_t += delta
	if _think_t >= 0.1:
		_think(_think_t)
		_think_t = 0.0
	var air_count := 0
	for i in birds.size():
		var b: Dictionary = birds[i]
		var st: int = b["state"]
		if st == B.GONE:
			b["respawn"] = float(b["respawn"]) - delta
			if float(b["respawn"]) <= 0.0 and not _airborne:
				_respawn_bird(b)
			continue
		if float(b["delay"]) > 0.0:
			b["delay"] = float(b["delay"]) - delta
			if float(b["delay"]) <= 0.0:
				_takeoff_bird(b)
		match st:
			B.GROUND:
				_ground_step(b, delta)
			B.FLY:
				air_count += 1
				_fly_step(b, i, delta)
			B.PERCH:
				var n := b["node"] as Node3D
				n.call(&"play", &"idle")
			B.LANDING:
				air_count += 1
				_land_step(b, delta)
		var node := b["node"] as Node3D
		if lod <= 1:
			node.call(&"tick", delta)
	_airborne = air_count > 0


func _think(dt: float) -> void:
	var player := _player()
	if player == null:
		return
	var pp := player.global_position
	var pv := NpcUtil.player_velocity(player).length()
	var r := flee_radius * NpcUtil.detection_mult()
	var airborne := player.has_method(&"is_airborne") and bool(player.call(&"is_airborne"))
	if NpcUtil.player_is_sneaking(player):
		r *= 0.3
	elif airborne:
		pass    # a pounce is fast but silent until it lands
	elif pv > 1.2:
		r *= 1.3 + minf(pv, 6.0) * 0.12
	var any_ground_near := false
	for b: Dictionary in birds:
		if b["xam"]:
			continue
		var st: int = b["state"]
		if st == B.GROUND and float(b["delay"]) <= 0.0:
			var d := (b["pos"] as Vector3).distance_to(pp)
			if d < r and absf(pp.y - (b["pos"] as Vector3).y) < 2.5:
				startle(pp, 6.0)
				return
			if d < 10.0:
				any_ground_near = true
	# return to the ground when calm
	var far := NpcUtil.flat_dist(pp, center) > maxf(radius + 5.0, 8.0)
	_calm_t = _calm_t + dt if far else 0.0
	if _calm_t > 6.0:
		for b: Dictionary in birds:
			var st2: int = b["state"]
			if (st2 == B.FLY and float(b["t"]) > 5.0) or (st2 == B.PERCH and _rng.randf() < 0.08):
				b["state"] = B.LANDING
				b["goal"] = _ground_point(center + _rand_disc(radius))
				b["t"] = 0.0
	if any_ground_near and _rng.randf() < 0.01:
		NpcUtil.sfx(&"pigeon_coo", center + Vector3.UP * 0.2, -10.0)


## Makes every ground bird within `r` of `from` take off (staggered).
func startle(from: Vector3, r: float) -> void:
	var n := 0
	for b: Dictionary in birds:
		if b["xam"] or int(b["state"]) != B.GROUND or float(b["delay"]) > 0.0:
			continue
		if (b["pos"] as Vector3).distance_to(from) < r + radius:
			b["delay"] = _rng.randf_range(0.12, 0.5) * (1.0 if n > 0 else 0.6)
			b["flee_from"] = from
			n += 1
	if n > 0:
		takeoffs += 1
		NpcUtil.sfx(&"flock_takeoff" if n > 3 else &"pigeon_takeoff", center + Vector3.UP * 0.5, -2.0)
		_calm_t = 0.0


func _takeoff_bird(b: Dictionary) -> void:
	var from: Vector3 = b.get("flee_from", _player().global_position if _player() != null else center)
	var away := NpcUtil.flat(b["pos"] - from)
	if away.length() < 0.05:
		away = Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1))
	away = away.normalized()
	b["vel"] = away * _rng.randf_range(2.5, 4.0) + Vector3.UP * _rng.randf_range(3.5, 5.0)
	b["state"] = B.FLY
	b["t"] = 0.0
	b["perch"] = perch_points[_rng.randi() % perch_points.size()] + _rand_disc(1.2) if not perch_points.is_empty() and _rng.randf() < 0.55 else Vector3.INF
	(b["node"] as Node3D).call(&"play", &"takeoff")


func _ground_step(b: Dictionary, delta: float) -> void:
	var node := b["node"] as Node3D
	var pos: Vector3 = b["pos"]
	b["t"] = float(b["t"]) + delta
	var goal: Vector3 = b["goal"]
	var to := NpcUtil.flat(goal - pos)
	if to.length() < 0.05:
		if float(b["t"]) > float(b["idle"]):
			# choose: wander a little, or peck, or idle
			var r := _rng.randf()
			b["t"] = 0.0
			if r < 0.45:
				var g := pos + _rand_disc(1.2)
				if NpcUtil.flat_dist(g, center) > radius:
					g = center + NpcUtil.flat(g - center).normalized() * radius * 0.8
				b["goal"] = _ground_point(g)
				b["act"] = &"walk"
			elif r < 0.8:
				b["act"] = &"peck"
				b["idle"] = _rng.randf_range(1.0, 3.5)
			else:
				b["act"] = &"idle"
				b["idle"] = _rng.randf_range(1.0, 4.0)
		node.call(&"play", b["act"] if b["act"] != &"walk" else &"idle")
		node.call(&"set_move_speed", 0.0)
	else:
		# separation from neighbours on the ground
		var sep := Vector3.ZERO
		for o: Dictionary in birds:
			if o == b or int(o["state"]) != B.GROUND:
				continue
			var dv := NpcUtil.flat(pos - (o["pos"] as Vector3))
			var dl := dv.length()
			if dl < 0.28 and dl > 0.001:
				sep += dv / dl * (0.28 - dl)
		var step := to.normalized() * walk_speed * delta + sep * 2.0 * delta
		pos += step
		pos.y = lerpf(pos.y, goal.y, 0.2)
		b["pos"] = pos
		node.rotation = Vector3(0, NpcUtil.yaw_of(to), 0)
		node.call(&"play", &"walk")
		node.call(&"set_move_speed", walk_speed)
	node.global_position = pos


func _fly_step(b: Dictionary, i: int, delta: float) -> void:
	var node := b["node"] as Node3D
	var pos: Vector3 = b["pos"]
	var vel: Vector3 = b["vel"]
	b["t"] = float(b["t"]) + delta
	var t := float(b["t"])
	var steer := Vector3.ZERO
	# boids among flying flock-mates
	var coh := Vector3.ZERO
	var ali := Vector3.ZERO
	var sep := Vector3.ZERO
	var n := 0
	for j in birds.size():
		if j == i:
			continue
		var o: Dictionary = birds[j]
		if int(o["state"]) != B.FLY:
			continue
		var d: Vector3 = (o["pos"] as Vector3) - pos
		var dl := d.length()
		if dl < 6.0:
			coh += o["pos"]
			ali += o["vel"]
			n += 1
			if dl < 0.8 and dl > 0.001:
				sep -= d / dl * (0.8 - dl) * 4.0
	if n > 0:
		steer += ((coh / n) - pos) * 0.6 + ((ali / n) - vel) * 0.8
	steer += sep * 3.0
	var perch: Vector3 = b["perch"]
	if t > 1.6 and perch != Vector3.INF:
		var tp := perch - pos
		if tp.length() < 0.6:
			b["state"] = B.PERCH
			b["pos"] = perch
			node.global_position = perch
			NpcUtil.sfx(&"pigeon_land", perch, -12.0)
			return
		steer += tp.normalized() * 6.0 - vel * 0.6
	elif t > 1.6:
		# circle above the square
		var alt := center.y + 9.0 + sin(float(i) * 1.7) * 2.0
		var rel := NpcUtil.flat(pos - center)
		var tang := Vector3(-rel.z, 0, rel.x).normalized()
		var radial := -rel.normalized() * (rel.length() - 9.0) * 0.6
		steer += tang * 5.0 + radial + Vector3.UP * (alt - pos.y) * 1.2
	else:
		steer += Vector3.UP * 3.0
	vel += steer * delta
	var sp := vel.length()
	var max_sp := fly_speed * (0.8 if perch != Vector3.INF and t > 1.6 else 1.0)
	if sp > max_sp:
		vel = vel / sp * max_sp
	elif sp < 2.5:
		vel = vel / maxf(sp, 0.01) * 2.5
	pos += vel * delta
	b["pos"] = pos
	b["vel"] = vel
	var bank := clampf(steer.dot(NpcUtil.flat(vel).cross(Vector3.UP).normalized()) * -0.05, -0.6, 0.6)
	node.global_transform = Transform3D(NpcUtil.basis_facing(vel) * Basis(Vector3.RIGHT, -clampf(vel.y * 0.08, -0.5, 0.5)) * Basis(Vector3.BACK, bank), pos)
	node.call(&"play", &"fly" if t > 0.8 or vel.y < 2.0 else &"takeoff")


func _land_step(b: Dictionary, delta: float) -> void:
	var node := b["node"] as Node3D
	var pos: Vector3 = b["pos"]
	var goal: Vector3 = b["goal"]
	var to := goal - pos
	var d := to.length()
	b["t"] = float(b["t"]) + delta
	var speed := clampf(d * 1.2, 0.8, fly_speed)
	var vel: Vector3 = (b["vel"] as Vector3).lerp(to.normalized() * speed, 1.0 - exp(-2.5 * delta))
	pos += vel * delta
	b["pos"] = pos
	b["vel"] = vel
	if d < 0.12 or float(b["t"]) > 12.0:
		b["pos"] = goal
		b["state"] = B.GROUND
		b["goal"] = goal
		b["t"] = 0.0
		b["act"] = &"idle"
		node.rotation = Vector3(0, NpcUtil.yaw_of(NpcUtil.flat(vel)) if NpcUtil.flat(vel).length() > 0.01 else node.rotation.y, 0)
		node.global_position = goal
		return
	node.global_transform = Transform3D(NpcUtil.basis_facing(vel if NpcUtil.flat(vel).length() > 0.05 else node.global_basis.z), pos)
	node.call(&"play", &"land" if d < 2.5 else &"glide")


func _respawn_bird(b: Dictionary) -> void:
	# a new pigeon glides in from a rooftop
	var start: Vector3 = perch_points[_rng.randi() % perch_points.size()] if not perch_points.is_empty() else center + Vector3(0, 8, 0)
	b["pos"] = start
	b["vel"] = Vector3.ZERO
	b["state"] = B.LANDING
	b["goal"] = _ground_point(center + _rand_disc(radius))
	b["t"] = 0.0
	(b["node"] as Node3D).visible = true


# --- catching ------------------------------------------------------------------------------

func on_part_swiped(index: int, _by: Node) -> void:
	_try_catch(index)


## Called by the director on player landings (pounce).
func check_pounce(pos: Vector3) -> bool:
	for i in birds.size():
		var b: Dictionary = birds[i]
		if int(b["state"]) == B.GROUND and not b["xam"] and (b["pos"] as Vector3).distance_to(pos) < 0.4 * NpcUtil.modifier(&"pounce_distance", 1.0):
			return _try_catch(i)
	return false


func _try_catch(index: int) -> bool:
	if index < 0 or index >= birds.size():
		return false
	var b: Dictionary = birds[index]
	if b["xam"] or int(b["state"]) != B.GROUND:
		return false
	var caught := NpcUtil.try_catch(StringName(bird_kind))
	if caught:
		b["state"] = B.GONE
		b["respawn"] = _rng.randf_range(40.0, 90.0)
		var node := b["node"] as Node3D
		# released: it flutters off out of sight
		node.visible = false
		NpcUtil.sfx(&"pigeon_takeoff", b["pos"], -3.0)
	startle(b["pos"], 6.0)
	return caught


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func set_lod(l: int, _interval: float) -> void:
	lod = l
	for b: Dictionary in birds:
		var n := b["node"] as Node3D
		if int(b["state"]) != B.GONE:
			n.visible = l < 3


func ground_bird_count() -> int:
	var c := 0
	for b: Dictionary in birds:
		if int(b["state"]) == B.GROUND:
			c += 1
	return c


func airborne_bird_count() -> int:
	var c := 0
	for b: Dictionary in birds:
		if int(b["state"]) in [B.FLY, B.PERCH, B.LANDING]:
			c += 1
	return c
