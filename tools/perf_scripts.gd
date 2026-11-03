extends SceneTree
## Per-script CPU probe: loads the game scene, then disables processing for all nodes sharing a
## script (one script at a time) and reports how much TIME_PROCESS / TIME_PHYSICS_PROCESS drops.
## Usage: godot --path . --script res://tools/perf_scripts.gd

const PHASE_SEC := 3.0
const WARMUP_SEC := 10.0

var _root_node: Node = null
var _groups: Dictionary = {}  # script path -> Array[Node]
var _order: Array = []
var _i := -2  # -2 warmup, -1 baseline
var _t := 0.0
var _frames := 0
var _proc := 0.0
var _phys := 0.0
var _base_proc := 0.0
var _base_phys := 0.0
var _disabled: Array = []


func _initialize() -> void:
	var t0 := Time.get_ticks_msec()
	_root_node = (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(_root_node)
	current_scene = _root_node
	print("PERF load+ready=%d ms" % (Time.get_ticks_msec() - t0))


func _collect() -> void:
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for c in n.get_children():
			stack.append(c)
		var s: Script = n.get_script()
		if s == null:
			continue
		if not (n.is_processing() or n.is_physics_processing()):
			continue
		var p := s.resource_path
		if not _groups.has(p):
			_groups[p] = []
		(_groups[p] as Array).append(n)
	_order = _groups.keys()
	print("PERF processing scripts: %d" % _order.size())
	for p in _order:
		print("PERF   %4d x %s" % [(_groups[p] as Array).size(), p])


func _process(delta: float) -> bool:
	_t += delta
	_frames += 1
	_proc += Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
	_phys += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
	var dur := WARMUP_SEC if _i == -2 else PHASE_SEC
	if _t < dur:
		return false
	var n := float(maxi(_frames, 1))
	var pr := _proc / n
	var ph := _phys / n
	if _i == -2:
		_collect()
	elif _i == -1:
		_base_proc = pr
		_base_phys = ph
		print("PERF baseline process=%.1f physics=%.1f fps=%.1f" % [pr, ph, _frames / _t])
	else:
		print("PERF without %-55s process=%6.1f (%+6.1f) physics=%6.1f (%+6.1f)" % [
			_order[_i], pr, pr - _base_proc, ph, ph - _base_phys])
		for node in _disabled:
			if is_instance_valid(node):
				(node as Node).process_mode = Node.PROCESS_MODE_INHERIT
	_disabled.clear()
	_i += 1
	_t = 0.0
	_frames = 0
	_proc = 0.0
	_phys = 0.0
	if _i >= _order.size():
		return true
	if _i >= 0:
		for node in _groups[_order[_i]]:
			if is_instance_valid(node) and node != root:
				(node as Node).process_mode = Node.PROCESS_MODE_DISABLED
				_disabled.append(node)
	return false
