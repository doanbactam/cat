extends SceneTree
## Startup probe: times load / instantiate / enter-tree (+ _ready) of the game scene inside a real
## frame, then the first frame times.
## Usage: godot --path . --script res://tools/perf_startup.gd -- [scene=res://scenes/main/game.tscn]

var _scene := "res://scenes/main/game.tscn"
var _frame := 0
var _t_last := 0
var _drop: PackedStringArray = []


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("scene="):
			_scene = a.substr(6)
		elif a.begins_with("drop="):
			_drop = a.substr(5).split(",")


var _marks: Array = []


func _mark(tag: String) -> void:
	if _frame >= 3 and _frame <= 6:
		_marks.append([tag, Time.get_ticks_usec()])


func _process(_delta: float) -> bool:
	if _frame == 0:
		physics_frame.connect(func() -> void: _mark("physics_frame(start of physics step)"))
		process_frame.connect(func() -> void: _mark("process_frame(start of process)"))
		RenderingServer.frame_pre_draw.connect(func() -> void: _mark("pre_draw"))
		RenderingServer.frame_post_draw.connect(func() -> void: _mark("post_draw"))
	if _frame == 7:
		for i in range(1, _marks.size()):
			print("MARK %-40s +%7.1f ms" % [_marks[i][0], (_marks[i][1] - _marks[i - 1][1]) / 1000.0])
	_frame += 1
	var now := Time.get_ticks_usec()
	if _frame == 3:
		var t0 := Time.get_ticks_usec()
		var ps := load(_scene) as PackedScene
		var t1 := Time.get_ticks_usec()
		var inst := ps.instantiate()
		for d in _drop:
			var dn := inst.find_child(d, true, false)
			if dn != null:
				dn.get_parent().remove_child(dn)
				dn.free()
		if "nosdfgi" in OS.get_cmdline_user_args() or "novolfog" in OS.get_cmdline_user_args():
			var we := inst.find_children("*", "WorldEnvironment", true, false)
			if not we.is_empty():
				var env := (we[0] as WorldEnvironment).environment
				if "nosdfgi" in OS.get_cmdline_user_args():
					env.set_meta(&"x", 1)
					env.sdfgi_enabled = false
				if "novolfog" in OS.get_cmdline_user_args():
					env.volumetric_fog_enabled = false
		var t2 := Time.get_ticks_usec()
		root.add_child(inst)
		current_scene = inst
		if "cam" in OS.get_cmdline_user_args():
			var cam := Camera3D.new()
			inst.add_child(cam)
			var sp := inst.find_child("PlayerSpawn", true, false) as Node3D
			cam.global_position = sp.global_position + Vector3(0, 1.5, 3) if sp != null else Vector3(0, 2, 0)
			cam.make_current()
		var t3 := Time.get_ticks_usec()
		print("STARTUP load=%d ms instantiate=%d ms add_child(enter_tree+ready)=%d ms" % [
			(t1 - t0) / 1000, (t2 - t1) / 1000, (t3 - t2) / 1000])
		var c: Node = inst.find_child("City", true, false)
		if c != null:
			print("STARTUP merged_bodies=%s visibility_ranged=%s" % [str(c.get("merged_bodies")), str(c.get("visibility_ranged"))])
	elif _frame > 3 and _frame <= 40:
		print("STARTUP frame %d: %.1f ms  pipelines canvas=%d mesh=%d surface=%d draw=%d spec=%d" % [_frame, (now - _t_last) / 1000.0,
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_CANVAS),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_MESH),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SURFACE),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_DRAW),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_PIPELINE_COMPILATIONS_SPECIALIZATION)])
	_t_last = Time.get_ticks_usec()
	return _frame > 40
