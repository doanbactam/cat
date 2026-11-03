extends SceneTree
## Node census: loads the game scene, waits a few seconds, then counts nodes by class and the
## ones doing (internal) process / physics process.
## Usage: godot --path . --script res://tools/perf_census.gd

var _t := 0.0
var _done := false


func _initialize() -> void:
	var n := (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(n)
	current_scene = n


func _process(delta: float) -> bool:
	_t += delta
	if _t < 5.0 or _done:
		return _done
	_done = true
	var by_class: Dictionary = {}
	var proc: Dictionary = {}
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var nd: Node = stack.pop_back()
		for c in nd.get_children():
			stack.append(c)
		var cls := nd.get_class()
		by_class[cls] = int(by_class.get(cls, 0)) + 1
		var flags := ""
		if nd.is_processing():
			flags += "P"
		if nd.is_physics_processing():
			flags += "F"
		if nd.is_processing_internal():
			flags += "p"
		if nd.is_physics_processing_internal():
			flags += "f"
		if flags != "":
			var key := "%s [%s]" % [cls, flags]
			proc[key] = int(proc.get(key, 0)) + 1
	print("CENSUS by class (top 30):")
	var keys := by_class.keys()
	keys.sort_custom(func(a: Variant, b: Variant) -> bool: return int(by_class[a]) > int(by_class[b]))
	for i in mini(30, keys.size()):
		print("CENSUS  %6d %s" % [by_class[keys[i]], keys[i]])
	print("CENSUS processing (P=process F=physics p=internal f=internal-physics):")
	var pk := proc.keys()
	pk.sort_custom(func(a: Variant, b: Variant) -> bool: return int(proc[a]) > int(proc[b]))
	for k in pk:
		print("CENSUS  %6d %s" % [proc[k], k])
	return true
