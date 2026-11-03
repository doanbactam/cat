extends SceneTree
## Collision-hole probe: casts rays straight down on a grid over the map bounds against the world
## colliders the player collides with, and reports cells with no ground (fall-out-of-world) or
## ground far below street level. Also checks visible ground meshes without a collider beneath.
## Usage: godot --path . --script res://tools/hole_probe.gd -- [step=1.0]

const PLAYER_MASK := 1 | 4 | 32 | 64 | 128  # world, props, climbable, water, vehicles (cat_player MOVE_MASK-ish)

var _frame := 0
var _step := 1.0
var _off := 0.0
var _city: Node = null


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("step="):
			_step = float(a.substr(5))
		elif a.begins_with("offset="):
			_off = float(a.substr(7))
	_city = (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(_city)
	current_scene = _city


func _physics_process(_d: float) -> bool:
	_frame += 1
	if _frame < 20:
		return false
	var pl := get_first_node_in_group(&"player")
	var mask := PLAYER_MASK
	if pl != null:
		mask = int(pl.get(&"collision_mask"))
	var space := (_city as Node3D).get_world_3d().direct_space_state
	var b: Rect2 = _city.get_meta(&"map_bounds", Rect2(-124, -98, 248, 212))
	var holes: Array[Vector2] = []
	var deep: Array[Vector2] = []
	var n := 0
	var x := b.position.x + _off
	while x <= b.end.x:
		var z := b.position.y + _off
		while z <= b.end.y:
			n += 1
			var q := PhysicsRayQueryParameters3D.create(Vector3(x, 80.0, z), Vector3(x, -30.0, z), mask)
			var hit := space.intersect_ray(q)
			if hit.is_empty():
				holes.append(Vector2(x, z))
			elif str((hit["collider"] as Node).name) == "SafetyFloor":
				deep.append(Vector2(x, z))
			z += _step
		x += _step
	print("HOLES mask=%d cells=%d no_ground=%d only_safety_floor=%d" % [mask, n, holes.size(), deep.size()])
	_report("NOGROUND", holes)
	_report("FALLTHROUGH", deep)
	quit()
	return true


## Groups neighbouring cells into clusters and prints each cluster's bbox + size.
func _report(tag: String, pts: Array[Vector2]) -> void:
	var left := pts.duplicate()
	var clusters: Array = []
	while not left.is_empty():
		var seed: Vector2 = left.pop_back()
		var cl: Array[Vector2] = [seed]
		var i := 0
		while i < cl.size():
			var c := cl[i]
			for j in range(left.size() - 1, -1, -1):
				if (left[j] as Vector2).distance_to(c) <= _step * 1.5:
					cl.append(left[j])
					left.remove_at(j)
			i += 1
		clusters.append(cl)
	clusters.sort_custom(func(a: Array, c: Array) -> bool: return a.size() > c.size())
	for k in mini(25, clusters.size()):
		var cl: Array = clusters[k]
		var r := Rect2(cl[0], Vector2.ZERO)
		for p: Vector2 in cl:
			r = r.expand(p)
		print("%s cluster %2d: %4d cells  x[%.0f..%.0f] z[%.0f..%.0f]" % [tag, k, cl.size(), r.position.x, r.end.x, r.position.y, r.end.y])
