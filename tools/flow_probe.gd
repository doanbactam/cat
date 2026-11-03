extends SceneTree
## Flow probe: boots main.tscn like the real game, presses "New Game" through SceneLoader after a
## few seconds, and reports load progress, the time to the game scene, and any stall > 60 s.
## Usage: godot --path . --script res://tools/flow_probe.gd -- [after=20]

var _t := 0.0
var _started := false
var _start_at := 6.0
var _after := 20.0
var _t_req := 0.0
var _t_changed := -1.0
var _last_print := 0.0
var _worst := 0.0


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("after="):
			_after = float(a.substr(6))
	var ps := load("res://scenes/main/main.tscn") as PackedScene
	var n := ps.instantiate()
	root.add_child(n)
	current_scene = n
	var sl := root.get_node(^"SceneLoader")
	sl.connect("scene_changed", func(_s: Node) -> void:
		_t_changed = _t
		print("FLOW scene_changed after %.1f s (current=%s)" % [_t - _t_req, current_scene.name]))
	sl.connect("load_failed", func(p: String) -> void: print("FLOW load_failed " + p))


func _process(delta: float) -> bool:
	_t += delta
	_worst = maxf(_worst, delta)
	var sl := root.get_node(^"SceneLoader")
	if not _started and _t >= _start_at:
		_started = true
		_t_req = _t
		print("FLOW start_new_game at %.1f s -> %s" % [_t, str(sl.call("start_new_game"))])
	if _t - _last_print >= 2.0:
		_last_print = _t
		print("FLOW t=%5.1f loading=%s progress=%.2f fade=%.2f worst_frame=%.0f ms fps=%d" % [
			_t, str(sl.call("is_loading")), float(sl.call("get_progress")), float(sl.call("get_fade_alpha")),
			_worst * 1000.0, Engine.get_frames_per_second()])
		_worst = 0.0
	if _started and _t_changed < 0.0 and _t - _t_req > 120.0:
		print("FLOW STALL: still loading after 120 s")
		return true
	if _t_changed >= 0.0 and _t - _t_changed > _after:
		print("FLOW done")
		return true
	return false
