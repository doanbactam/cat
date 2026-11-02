extends Node3D
## House geckos (thạch sùng) on walls at night (owner: world-life). One colony is created by the
## LifeDirector. After dusk it keeps up to `max_count` geckos on vertical walls within ~14 m of
## Cam, preferring walls near lights (they hunt moths there): positions are found with
## horizontal raycasts against the world layer. Geckos idle, make short crawling bursts on the
## wall plane, chirp ("tặc lưỡi", gecko_chirp / tokay_call) and dart upward when Cam comes within
## ~1 m. At dawn they disappear. Not catchable (they stay out of reach on the walls).

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")

var max_count := 6
var director: Node = null
var geckos: Array[Dictionary] = []
var lod := 0
var _rng := RandomNumberGenerator.new()
var _place_t := 0.0
var _chirp_cd := 4.0
## For tests: number of successful wall placements.
var placed := 0


func setup(p_max: int) -> void:
	_rng.randomize()
	max_count = p_max
	name = "Geckos"


func _physics_process(delta: float) -> void:
	var player := _player()
	if player == null:
		return
	var night := NpcUtil.night_factor() > 0.55
	_place_t -= delta
	if not night:
		for g: Dictionary in geckos:
			(g["node"] as Node3D).queue_free()
		geckos.clear()
		return
	# recycle far geckos, place new ones
	for i in range(geckos.size() - 1, -1, -1):
		var gg: Dictionary = geckos[i]
		if (gg["pos"] as Vector3).distance_to(player.global_position) > 22.0:
			(gg["node"] as Node3D).queue_free()
			geckos.remove_at(i)
	if geckos.size() < max_count and _place_t <= 0.0:
		_place_t = 0.5
		_try_place(player.global_position)
	_chirp_cd -= delta
	if _chirp_cd <= 0.0 and not geckos.is_empty():
		_chirp_cd = _rng.randf_range(5.0, 14.0)
		var g0: Dictionary = geckos[_rng.randi() % geckos.size()]
		NpcUtil.sfx(&"gecko_chirp" if _rng.randf() < 0.85 else &"tokay_call", g0["pos"], -12.0, 0.1)
	for g: Dictionary in geckos:
		_step(g, delta, player)


func _try_place(around: Vector3) -> void:
	var world := get_world_3d()
	var origin := around + Vector3.UP * _rng.randf_range(1.2, 3.2)
	# prefer near lights
	var lights := get_tree().get_nodes_in_group(&"street_light")
	if lights.is_empty():
		var root := get_tree().current_scene if get_tree().current_scene != null else get_tree().root
		for l: Node in root.find_children("*", "OmniLight3D", true, false):
			if (l as Node3D).global_position.distance_to(around) < 16.0 and (l as Node3D).is_visible_in_tree():
				lights.append(l)
			if lights.size() > 6:
				break
	if not lights.is_empty() and _rng.randf() < 0.7:
		var l := lights[_rng.randi() % lights.size()] as Node3D
		origin = l.global_position + Vector3(_rng.randf_range(-1, 1), _rng.randf_range(-1.2, 0.3), _rng.randf_range(-1, 1))
	var a := _rng.randf() * TAU
	var dir := Vector3(cos(a), 0, sin(a))
	var hit := NpcUtil.ray(world, origin, origin + dir * 8.0, NpcUtil.LAYER_WORLD)
	if hit.is_empty():
		return
	var n: Vector3 = hit["normal"]
	if absf(n.y) > 0.25:
		return
	var p: Vector3 = (hit["position"] as Vector3) + n * 0.004
	if p.y < around.y + 0.6:
		return
	var v := NpcVisualScript.new()
	v.name = "Gecko%d" % placed
	add_child(v)
	v.top_level = true
	v.call(&"setup", "gecko", {"model_names": ["gecko", "gecko_"]})
	v.add_to_group(&"npc")
	v.set_meta(&"npc_kind", "gecko")
	var up_dir := _rng.randf_range(-PI, PI)
	var g := {"node": v, "pos": p, "normal": n, "head": up_dir, "t": 0.0, "move": 0.0, "speed": 0.0}
	geckos.append(g)
	placed += 1
	_orient(g)


func _orient(g: Dictionary) -> void:
	var n: Vector3 = g["normal"]
	var tangent_x := Vector3.UP.cross(n).normalized()
	var wall_up := n.cross(tangent_x).normalized()
	var head := float(g["head"])
	var fwd := (wall_up * cos(head) + tangent_x * sin(head)).normalized()
	# model: belly −Y, front +Z → Y = wall normal, Z = heading
	var x := n.cross(fwd).normalized()
	(g["node"] as Node3D).global_transform = Transform3D(Basis(x, n, fwd), g["pos"])


func _step(g: Dictionary, delta: float, player: Node3D) -> void:
	var v := g["node"] as Node3D
	g["t"] = float(g["t"]) + delta
	var d := (g["pos"] as Vector3).distance_to(player.global_position + Vector3.UP * 0.2)
	if d < 1.1 and float(g["move"]) <= 0.0:
		g["head"] = 0.0 + _rng.randf_range(-0.4, 0.4)   # dart up the wall
		g["move"] = 0.8
		g["speed"] = 0.9
	elif float(g["move"]) <= 0.0 and float(g["t"]) > _rng.randf_range(2.0, 6.0) and _rng.randf() < 0.02:
		g["head"] = float(g["head"]) + _rng.randf_range(-1.2, 1.2)
		g["move"] = _rng.randf_range(0.3, 0.9)
		g["speed"] = _rng.randf_range(0.15, 0.35)
		g["t"] = 0.0
	if float(g["move"]) > 0.0:
		g["move"] = float(g["move"]) - delta
		var n: Vector3 = g["normal"]
		var tangent_x := Vector3.UP.cross(n).normalized()
		var wall_up := n.cross(tangent_x).normalized()
		var head := float(g["head"])
		var fwd := (wall_up * cos(head) + tangent_x * sin(head)).normalized()
		var np: Vector3 = (g["pos"] as Vector3) + fwd * float(g["speed"]) * delta
		# stay on the wall: re-project onto the surface
		var hit := NpcUtil.ray(get_world_3d(), np + n * 0.1, np - n * 0.2, NpcUtil.LAYER_WORLD)
		if hit.is_empty() or absf((hit["normal"] as Vector3).y) > 0.25:
			g["move"] = 0.0
			g["head"] = head + PI
		else:
			g["pos"] = (hit["position"] as Vector3) + (hit["normal"] as Vector3) * 0.004
			g["normal"] = hit["normal"]
		v.call(&"play", &"crawl")
		v.call(&"set_move_speed", float(g["speed"]))
	else:
		v.call(&"play", &"idle")
		v.call(&"set_move_speed", 0.0)
	_orient(g)
	v.call(&"tick", delta)


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func set_lod(l: int, _interval: float) -> void:
	lod = l
