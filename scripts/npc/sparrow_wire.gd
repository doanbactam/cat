extends Node3D
## Sparrows on an overhead wire (owner: world-life). Spawned at an `npc_spawn` marker with
## npc_kind "sparrows" (extension of the contract list); the wire runs from the marker to
## marker + meta `wire_end` (Vector3, marker-local; default 6 m along local X), sagging by meta
## `sag` (default 0.25 m). Birds sit spaced along the catenary, shuffle sideways, chirp, and burst
## off together when Cam comes close (≤ 2.5 m, e.g. climbing a pole/balcony) or a loud noise
## happens; they return one by one a few seconds later.

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")

var a := Vector3.ZERO
var b := Vector3.ZERO
var sag := 0.25
var birds: Array[Dictionary] = []
var director: Node = null
var lod := 0
var _rng := RandomNumberGenerator.new()
var _chirp_cd := 2.0
## For tests.
var scatter_count := 0


func setup(marker: Node3D, n: int) -> void:
	_rng.randomize()
	add_to_group(&"npc")
	set_meta(&"npc_kind", "sparrow")
	a = marker.global_position
	var end_local: Vector3 = NpcUtil.meta_or(marker, &"wire_end", Vector3(6, 0, 0))
	b = marker.global_transform * end_local
	sag = float(NpcUtil.meta_or(marker, &"sag", 0.25))
	for i in n:
		var v := NpcVisualScript.new()
		v.name = "Sparrow%d" % i
		add_child(v)
		v.top_level = true
		v.call(&"setup", "sparrow", {"model_names": ["sparrow", "sparrow_"]})
		var u := clampf((float(i) + 0.5) / float(n) + _rng.randf_range(-0.03, 0.03), 0.04, 0.96)
		var d := {"node": v, "u": u, "home_u": u, "state": 0, "pos": wire_point(u), "vel": Vector3.ZERO, "t": _rng.randf() * 3.0}
		birds.append(d)
		v.global_position = d["pos"]
		_face_wire(v, _rng.randf() < 0.5)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_noise.connect(_on_noise)


func wire_point(u: float) -> Vector3:
	return a.lerp(b, u) - Vector3.UP * sag * 4.0 * u * (1.0 - u)


func _face_wire(v: Node3D, flip: bool) -> void:
	var side := NpcUtil.flat(b - a).normalized().cross(Vector3.UP)
	v.rotation = Vector3(0, NpcUtil.yaw_of(-side if flip else side), 0)


func _physics_process(delta: float) -> void:
	if lod >= 3 or birds.is_empty():
		return
	_chirp_cd -= delta
	var player := _player()
	if player != null:
		var mid := wire_point(0.5)
		var closest := INF
		for d: Dictionary in birds:
			if int(d["state"]) == 0:
				closest = minf(closest, (d["pos"] as Vector3).distance_to(player.global_position))
		if closest < (1.5 if NpcUtil.player_is_sneaking(player) else 2.6):
			scatter(player.global_position)
		elif _chirp_cd <= 0.0 and mid.distance_to(player.global_position) < 25.0:
			_chirp_cd = _rng.randf_range(1.5, 5.0)
			NpcUtil.sfx(&"sparrow_chirp", mid, -12.0, 0.15)
	for d: Dictionary in birds:
		var v := d["node"] as Node3D
		d["t"] = float(d["t"]) + delta
		match int(d["state"]):
			0:    # sitting
				if float(d["t"]) > 3.0 and _rng.randf() < 0.01:
					d["u"] = clampf(float(d["u"]) + _rng.randf_range(-0.04, 0.04), 0.03, 0.97)
					d["t"] = 0.0
					_face_wire(v, _rng.randf() < 0.5)
				var target := wire_point(float(d["u"]))
				d["pos"] = (d["pos"] as Vector3).lerp(target, 1.0 - exp(-10.0 * delta))
				v.global_position = d["pos"]
				v.call(&"play", &"peck" if fmod(float(d["t"]), 5.0) > 4.4 else &"idle")
			1:    # flying away
				var vel: Vector3 = d["vel"]
				vel += Vector3(0, 1.0, 0) * delta
				d["pos"] = (d["pos"] as Vector3) + vel * delta
				d["vel"] = vel
				v.global_transform = Transform3D(NpcUtil.basis_facing(vel), d["pos"])
				v.call(&"play", &"fly")
				if float(d["t"]) > _rng.randf_range(5.0, 9.0):
					d["state"] = 2
					d["t"] = 0.0
			2:    # returning
				var target2 := wire_point(float(d["home_u"]))
				var to := target2 - (d["pos"] as Vector3)
				if to.length() < 0.08:
					d["state"] = 0
					d["u"] = d["home_u"]
					d["t"] = 0.0
					_face_wire(v, _rng.randf() < 0.5)
				else:
					var vel2 := to.normalized() * clampf(to.length() * 2.0, 0.8, 6.0)
					d["pos"] = (d["pos"] as Vector3) + vel2 * delta
					v.global_transform = Transform3D(NpcUtil.basis_facing(vel2), d["pos"])
					v.call(&"play", &"land" if to.length() < 1.0 else &"fly")
		if lod <= 1:
			v.call(&"tick", delta)


func scatter(from: Vector3) -> void:
	var any := false
	for d: Dictionary in birds:
		if int(d["state"]) != 0:
			continue
		any = true
		var away := NpcUtil.flat((d["pos"] as Vector3) - from).normalized()
		if away.length() < 0.1:
			away = Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)).normalized()
		d["vel"] = away * _rng.randf_range(4.0, 7.0) + Vector3.UP * _rng.randf_range(1.5, 3.0)
		d["state"] = 1
		d["t"] = 0.0
	if any:
		scatter_count += 1
		NpcUtil.sfx(&"flock_takeoff", wire_point(0.5), -8.0, 0.2)


func _on_noise(pos: Vector3, loud: float) -> void:
	if loud > 0.3 and pos.distance_to(wire_point(0.5)) < 6.0 + loud * 8.0:
		scatter(pos)


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func set_lod(l: int, _interval: float) -> void:
	lod = l
	visible = l < 3
	for d: Dictionary in birds:
		(d["node"] as Node3D).visible = l < 3
