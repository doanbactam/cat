extends SceneTree
## Map probe: loads the game, waits, opens the Map screen (game.open_map) and logs frame times,
## whether the capture finished, and the player's height (falling through the world shows here).
## Usage: godot --path . --script res://tools/map_probe.gd -- [open_at=8] [secs=30] [walk=1]

var _game: Node = null
var _t := 0.0
var _open_at := 8.0
var _secs := 30.0
var _walk := false
var _opened := false
var _worst := 0.0
var _last := 0.0
var _min_y := INF


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("open_at="):
			_open_at = float(a.substr(8))
		elif a.begins_with("secs="):
			_secs = float(a.substr(5))
		elif a == "walk=1":
			_walk = true
	_game = (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(_game)
	current_scene = _game


func _player() -> Node3D:
	return get_first_node_in_group(&"player") as Node3D


func _process(delta: float) -> bool:
	_t += delta
	_worst = maxf(_worst, delta)
	if _opened and delta > 0.1:
		print("MAP   long frame %.0f ms at t=%.2f" % [delta * 1000.0, _t])
	if _opened and _t >= _open_at + 4.0 and _t - delta < _open_at + 4.0:
		print("MAP closing map (ui_cancel)")
		var ev := InputEventAction.new()
		ev.action = &"ui_cancel"
		ev.pressed = true
		Input.parse_input_event(ev)
	if _opened and _t >= _open_at + 7.0 and _t - delta < _open_at + 7.0:
		print("MAP reopening map")
		_game.call(&"open_map")
	var p := _player()
	if p != null:
		_min_y = minf(_min_y, p.global_position.y)
	if _walk and _t > 3.0:
		Input.action_press(&"move_forward")
	if not _opened and _t >= _open_at:
		_opened = true
		var t0 := Time.get_ticks_msec()
		_game.call(&"open_map")
		print("MAP open_map() returned in %d ms" % (Time.get_ticks_msec() - t0))
	if _t - _last >= 1.0:
		_last = _t
		var ms: Node = null
		for n in root.find_children("*", "", true, false):
			if n.get_script() != null and str((n.get_script() as Script).resource_path).ends_with("map_screen.gd"):
				ms = n
				break
		var cap := "-"
		if ms != null:
			cap = "capturing" if bool(ms.get(&"_capturing")) else "done"
		print("MAP t=%5.1f worst=%6.0f ms fps=%d paused=%s map=%s player=%s min_y=%.2f" % [
			_t, _worst * 1000.0, Engine.get_frames_per_second(), str(paused), cap,
			str(p.global_position.snapped(Vector3.ONE * 0.01)) if p != null else "none", _min_y])
		_worst = 0.0
	return _t >= _secs
