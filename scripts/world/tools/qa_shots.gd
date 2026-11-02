extends SceneTree
## World visual QA: loads city.tscn once and captures a list of named views (owner: world).
## Run (under the Godot lock, with a display):
##   flock /tmp/meocam_godot.lock xvfb-run -a -s "-screen 0 960x540x24" godot --path . --resolution 960x540 \
##     --script res://scripts/world/tools/qa_shots.gd -- out=/abs/dir [only=name,name] [frames=24] </dev/null
## Each shot: [name, cam, look, hour, weather, festival]. Prints PERF lines (draw calls / primitives).

const SHOTS := [
	["street_tpp", Vector3(-30.0, 1.6, -67.2), Vector3(-12.0, 2.2, -71.0), 10.0, &"clear", false],
	["cat_eye", Vector3(-84.6, 0.22, -67.6), Vector3(-86.8, 0.6, -64.5), 16.5, &"clear", false],
	["rooftop_vista", Vector3(-82.0, 14.0, -58.0), Vector3(-20.0, 4.0, -10.0), 17.2, &"clear", false],
	["alley", Vector3(-90.0, 1.4, -40.0), Vector3(-90.0, 1.6, -20.0), 11.0, &"clear", false],
	["lake_dawn", Vector3(-34.0, 1.6, -22.0), Vector3(14.0, 1.0, 2.0), 6.2, &"clear", false],
	["lake_bridge", Vector3(37.0, 2.2, 10.0), Vector3(14.0, 0.0, 1.0), 8.0, &"clear", false],
	["market_noon", Vector3(58.0, 1.7, -14.0), Vector3(72.0, 2.0, -26.0), 12.5, &"clear", false],
	["night_lamps", Vector3(-80.0, 1.6, -68.0), Vector3(-87.0, 1.0, -64.5), 21.0, &"clear", false],
	["rain", Vector3(-20.0, 1.5, -66.5), Vector3(5.0, 1.0, -71.0), 15.0, &"rain", false],
	["temple", Vector3(0.0, 1.7, 58.0), Vector3(0.0, 4.0, 80.0), 9.0, &"clear", false],
	["festival_night", Vector3(-6.0, 1.7, 57.0), Vector3(10.0, 3.5, 66.0), 20.5, &"clear", true],
	["overview", Vector3(-60.0, 60.0, -95.0), Vector3(0.0, 0.0, 0.0), 15.0, &"clear", false],
]

var _args := {}


func _init() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() == 2:
			_args[kv[0]] = kv[1]
	_run.call_deferred()


func _run() -> void:
	await process_frame
	var out: String = _args.get("out", "/tmp/qa_world")
	DirAccess.make_dir_recursive_absolute(out)
	var only: PackedStringArray = PackedStringArray(str(_args.get("only", "")).split(",", false))
	var frames := int(_args.get("frames", "24"))
	var city: Node3D = (load("res://scenes/world/city.tscn") as PackedScene).instantiate()
	root.add_child(city)
	var ws: Node = city.get_node_or_null(^"WeatherSystem")
	if ws != null:
		ws.set(&"auto_weather", false)
	var env: Node = city.get_node_or_null(^"WorldEnvironment")
	var nl: Node = city.get_node_or_null(^"NightLights")
	var tod: Node = root.get_node_or_null(^"TimeOfDay")
	if tod != null:
		tod.set(&"paused", true)
	var cam := Camera3D.new()
	cam.fov = 70.0
	cam.far = 1500.0
	root.add_child(cam)
	cam.make_current()
	for s: Array in SHOTS:
		if not only.is_empty() and not str(s[0]) in only:
			continue
		var hour := float(s[3])
		if tod != null and tod.has_method(&"set_hour"):
			tod.call(&"set_hour", hour)
		if env != null:
			env.call(&"set_hour_override", hour)
		if ws != null:
			if s[4] == &"rain":
				ws.call(&"set_weather_immediate", &"rain", 0.9, 0.9)
			else:
				ws.call(&"set_weather_immediate", s[4], 0.0 if s[4] == &"clear" else 0.8, 0.0)
		if nl != null:
			nl.call(&"set_festival_override", 1 if bool(s[5]) else 0)
		cam.global_position = s[1]
		cam.look_at(s[2], Vector3.UP)
		for i in frames:
			await process_frame
		await RenderingServer.frame_post_draw
		var img := root.get_viewport().get_texture().get_image()
		var path := out.path_join(str(s[0]) + ".png")
		img.save_png(path)
		print("QA shot %s draw_calls=%d primitives=%d objects=%d fps=%.2f" % [path,
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
			Performance.get_monitor(Performance.TIME_FPS)])
	city.queue_free()
	await process_frame
	quit(0)
