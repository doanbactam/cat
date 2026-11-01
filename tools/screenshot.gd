extends SceneTree
## Headless-ish screenshot capture (run under Xvfb + lavapipe via tools/screenshot.sh).
## User args (after --): key=value pairs
##   scene=res://path.tscn   (required)
##   out=/abs/path.png       (required)
##   frames=30               frames to wait before capture (lets TAA/SDFGI settle)
##   cam=x,y,z look=x,y,z    optional override camera
##   fov=70                  optional camera fov
##   hour=14.5               optional: sets TimeOfDay.hour if autoload has `set_hour`
##   weather=rain            optional: calls TimeOfDay/WeatherSystem `set_weather` if present
##   call=method_name        optional: calls method on the scene root after load
##   shots=3 step=10         optional: multiple captures out_0.png.. every `step` frames

var _args := {}

func _init() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() == 2:
			_args[kv[0]] = kv[1]
	_run.call_deferred()

func _vec(s: String) -> Vector3:
	var p := s.split(",")
	return Vector3(float(p[0]), float(p[1]), float(p[2]))

func _run() -> void:
	var scene_path: String = _args.get("scene", "")
	var out: String = _args.get("out", "/tmp/shot.png")
	var ps := load(scene_path) as PackedScene
	if ps == null:
		printerr("SCREENSHOT: cannot load ", scene_path); quit(2); return
	var inst := ps.instantiate()
	root.add_child(inst)
	if _args.has("hour"):
		var tod = root.get_node_or_null("TimeOfDay")
		if tod and tod.has_method("set_hour"):
			tod.set_hour(float(_args["hour"]))
	if _args.has("weather"):
		for n in ["TimeOfDay", "Weather", "WeatherSystem"]:
			var w = root.get_node_or_null(n)
			if w and w.has_method("set_weather"):
				w.set_weather(StringName(_args["weather"]), 1.0); break
	if _args.has("call") and inst.has_method(_args["call"]):
		inst.call(_args["call"])
	if _args.has("cam"):
		var cam := Camera3D.new()
		root.add_child(cam)
		cam.global_position = _vec(_args["cam"])
		if _args.has("look"):
			cam.look_at(_vec(_args["look"]), Vector3.UP)
		cam.fov = float(_args.get("fov", "70"))
		cam.far = 1500.0
		cam.make_current()
	var frames := int(_args.get("frames", "30"))
	for i in frames:
		await process_frame
	var shots := int(_args.get("shots", "1"))
	var step := int(_args.get("step", "10"))
	for s in shots:
		await RenderingServer.frame_post_draw
		var img := root.get_viewport().get_texture().get_image()
		var path := out if shots == 1 else out.get_basename() + "_%d.png" % s
		img.save_png(path)
		print("SCREENSHOT saved ", path, " ", img.get_size())
		for i in step:
			await process_frame
	quit(0)
