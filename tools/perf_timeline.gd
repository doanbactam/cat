extends SceneTree
## Timeline probe: loads the game scene and prints per-second frame stats with the in-game hour.
## Usage: godot --path . --script res://tools/perf_timeline.gd -- [hour=17.5] [scale=20] [secs=60]

var _t := 0.0
var _total := 0.0
var _frames := 0
var _proc := 0.0
var _phys := 0.0
var _worst := 0.0
var _secs := 60.0


func _initialize() -> void:
	var hour := -1.0
	var scale := -1.0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("hour="):
			hour = float(a.substr(5))
		elif a.begins_with("scale="):
			scale = float(a.substr(6))
		elif a.begins_with("secs="):
			_secs = float(a.substr(5))
	var t0 := Time.get_ticks_msec()
	var n := (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(n)
	current_scene = n
	print("PERF load+ready=%d ms" % (Time.get_ticks_msec() - t0))
	var tod := root.get_node_or_null(^"TimeOfDay")
	if tod != null:
		if hour >= 0.0:
			tod.call("set_hour", hour)
		if scale > 0.0:
			tod.set("time_scale", scale)


func _process(delta: float) -> bool:
	_t += delta
	_total += delta
	_frames += 1
	_proc += Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
	_phys += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
	_worst = maxf(_worst, delta * 1000.0)
	if _t >= 1.0:
		var tod := root.get_node_or_null(^"TimeOfDay")
		var h: float = tod.get("hour") if tod != null else -1.0
		var n := float(_frames)
		print("PERF t=%5.1f hour=%5.2f fps=%5.1f worst=%6.1f process=%6.1f physics=%5.1f objs=%d nodes=%d" % [
			_total, h, n / _t, _worst, _proc / n, _phys / n,
			int(Performance.get_monitor(Performance.OBJECT_COUNT)),
			int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))])
		_t = 0.0
		_frames = 0
		_proc = 0.0
		_phys = 0.0
		_worst = 0.0
	return _total >= _secs
