extends SceneTree
## Perf probe: loads the game scene with the clock frozen, then measures frame cost with ONE
## feature toggled at a time (each toggle is reverted before the next), splitting primitives and
## draw calls into the visible pass and the shadow pass.
## Usage: godot --path . --script res://tools/perf_probe.gd -- [hour=10] [only=baseline,-sdfgi]

const PHASE_SEC := 5.0
const WARMUP_SEC := 10.0

var _root_node: Node = null
var _env: Environment = null
var _phases: Array[Dictionary] = []
var _phase_i := -1
var _t := 0.0
var _frames := 0
var _acc := {}
var _worst := 0.0
var _vp: RID
var _undo: Callable = Callable()


func _initialize() -> void:
	var hour := 10.0
	var only: PackedStringArray = []
	for a in OS.get_cmdline_user_args():
		if a.begins_with("hour="):
			hour = float(a.substr(5))
		elif a.begins_with("only="):
			only = a.substr(5).split(",")
	var t0 := Time.get_ticks_msec()
	_root_node = (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	root.add_child(_root_node)
	current_scene = _root_node
	print("PERF load+ready=%d ms" % (Time.get_ticks_msec() - t0))
	var tod := root.get_node_or_null(^"TimeOfDay")
	if tod != null:
		tod.call("set_hour", hour)
		tod.set("paused", true)
	_vp = root.get_viewport_rid()
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	RenderingServer.viewport_set_measure_render_time(_vp, true)
	var we := _root_node.find_children("*", "WorldEnvironment", true, false)
	if not we.is_empty():
		_env = (we[0] as WorldEnvironment).environment
	var all: Array[Dictionary] = [
		{"name": "baseline", "on": func() -> Callable: return Callable()},
		{"name": "-sdfgi", "on": func() -> Callable: return _set_env("sdfgi_enabled", false)},
		{"name": "-volfog", "on": func() -> Callable: return _set_env("volumetric_fog_enabled", false)},
		{"name": "-ssr", "on": func() -> Callable: return _set_env("ssr_enabled", false)},
		{"name": "-ssao", "on": func() -> Callable: return _set_env("ssao_enabled", false)},
		{"name": "-decals", "on": func() -> Callable: return _hide_class("Decal")},
		{"name": "-refl_probes", "on": func() -> Callable: return _hide_class("ReflectionProbe")},
		{"name": "-omni/spot", "on": func() -> Callable: return _hide_class("OmniLight3D", "SpotLight3D")},
		{"name": "-sun_shadow", "on": func() -> Callable: return _sun_shadow_off()},
		{"name": "sun_2_splits", "on": func() -> Callable: return _sun_splits()},
		{"name": "-npcs", "on": func() -> Callable: return _disable_named("LifeDirector")},
		{"name": "-player_fur", "on": func() -> Callable: return _hide_script("fur_shells.gd")},
		{"name": "scale_0.77", "on": func() -> Callable: return _render_scale(0.77)},
		{"name": "-occluders", "on": func() -> Callable: return _hide_class("OccluderInstance3D")},
		{"name": "-pedestrian", "on": func() -> Callable: return _disable_script("npc/pedestrian.gd")},
		{"name": "-vehicle", "on": func() -> Callable: return _disable_script("npc/vehicle.gd")},
		{"name": "-npc_cat", "on": func() -> Callable: return _disable_script("npc/npc_cat.gd")},
		{"name": "-crow", "on": func() -> Callable: return _disable_script("npc/crow.gd")},
		{"name": "-pigeons", "on": func() -> Callable: return _disable_script("npc/pigeon_flock.gd")},
		{"name": "-koi", "on": func() -> Callable: return _disable_script("npc/koi_school.gd")},
		{"name": "-mouse", "on": func() -> Callable: return _disable_script("npc/mouse.gd")},
		{"name": "-gecko", "on": func() -> Callable: return _disable_script("npc/gecko_colony.gd")},
		{"name": "-dog", "on": func() -> Callable: return _disable_script("npc/dog.gd")},
		{"name": "-director_only", "on": func() -> Callable: return _disable_script("npc/life_director.gd", false)},
		{"name": "sun4_90m", "on": func() -> Callable: return _sun_cfg(DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS, 90.0)},
		{"name": "sun2_100m", "on": func() -> Callable: return _sun_cfg(DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS, 100.0)},
		{"name": "sun4_90_4k", "on": func() -> Callable: return _sun_cfg(DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS, 90.0, 4096)},
		{"name": "sdfgi_4casc", "on": func() -> Callable: return _set_env("sdfgi_cascades", 4)},
		{"name": "lights_fade45", "on": func() -> Callable: return _lights_fade(45.0)},
		{"name": "sdfgi_light8", "on": func() -> Callable:
			RenderingServer.environment_set_sdfgi_frames_to_update_light(RenderingServer.ENV_SDFGI_UPDATE_LIGHT_IN_8_FRAMES)
			return func() -> void: RenderingServer.environment_set_sdfgi_frames_to_update_light(RenderingServer.ENV_SDFGI_UPDATE_LIGHT_IN_4_FRAMES)},
		{"name": "sdfgi_noocc", "on": func() -> Callable: return _set_env("sdfgi_use_occlusion", false)},
		{"name": "sdfgi_half", "on": func() -> Callable:
			RenderingServer.gi_set_use_half_resolution(true)
			return func() -> void: RenderingServer.gi_set_use_half_resolution(false)},
		{"name": "-env_process", "on": func() -> Callable: return _noproc("WorldEnvironment")},
		{"name": "-weather_proc", "on": func() -> Callable: return _noproc("WeatherSystem")},
		{"name": "-nightlights_proc", "on": func() -> Callable: return _noproc("NightLights")},
		{"name": "-hud", "on": func() -> Callable: return _disable_named("HUD")},
		{"name": "sky_incremental", "on": func() -> Callable:
			var sky := _env.sky
			var old := sky.process_mode
			sky.process_mode = Sky.PROCESS_MODE_INCREMENTAL
			return func() -> void: sky.process_mode = old},
		{"name": "sky_rad128", "on": func() -> Callable:
			var sky := _env.sky
			var old := sky.radiance_size
			sky.radiance_size = Sky.RADIANCE_SIZE_128
			return func() -> void: sky.radiance_size = old},
		{"name": "-npc_anims", "on": func() -> Callable: return _npc_anims_off()},
		{"name": "-pushables", "on": func() -> Callable: return _disable_script("systems/pushable.gd", false)},
	]
	_phases = [{"name": "warmup", "dur": WARMUP_SEC, "on": func() -> Callable: return Callable()}]
	for p in all:
		if only.is_empty() or String(p["name"]) in only:
			_phases.append(p)
	print("PERF occlusion_culling=%s" % str(ProjectSettings.get_setting("rendering/occlusion_culling/use_occlusion_culling")))
	_next_phase()


func _ri(kind: int, what: int) -> int:
	return RenderingServer.viewport_get_render_info(_vp, kind, what)


func _add(k: String, v: float) -> void:
	_acc[k] = float(_acc.get(k, 0.0)) + v


func _process(delta: float) -> bool:
	_t += delta
	_frames += 1
	_add("cpu", RenderingServer.viewport_get_measured_render_time_cpu(_vp))
	_add("gpu", RenderingServer.viewport_get_measured_render_time_gpu(_vp))
	_add("proc", Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0)
	_add("phys", Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0)
	var V := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
	var S := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW
	_add("vprim", _ri(V, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME))
	_add("sprim", _ri(S, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME))
	_add("vdraw", _ri(V, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME))
	_add("sdraw", _ri(S, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME))
	_add("vobj", _ri(V, RenderingServer.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME))
	_worst = maxf(_worst, delta * 1000.0)
	var dur: float = _phases[_phase_i].get("dur", PHASE_SEC)
	if _t >= dur:
		var n := float(maxi(_frames, 1))
		print("PERF %-14s fps=%5.1f frame=%5.1fms worst=%6.1f | rcpu=%5.1f gpu=%5.1f | proc=%5.1f phys=%5.1f | vis %4dk tri %4d draws %4d obj | shadow %5dk tri %4d draws" % [
			_phases[_phase_i]["name"], _frames / _t, _t * 1000.0 / n, _worst,
			_acc["cpu"] / n, _acc["gpu"] / n, _acc["proc"] / n, _acc["phys"] / n,
			int(_acc["vprim"] / n / 1000.0), int(_acc["vdraw"] / n), int(_acc["vobj"] / n),
			int(_acc["sprim"] / n / 1000.0), int(_acc["sdraw"] / n)])
		if _undo.is_valid():
			_undo.call()
			_undo = Callable()
		if _phase_i + 1 >= _phases.size():
			return true
		_next_phase()
	return false


func _next_phase() -> void:
	_phase_i += 1
	_t = 0.0
	_frames = 0
	_acc = {}
	_worst = 0.0
	_undo = (_phases[_phase_i]["on"] as Callable).call()


func _set_env(prop: String, v: Variant) -> Callable:
	if _env == null:
		return Callable()
	var old: Variant = _env.get(prop)
	_env.set(prop, v)
	return func() -> void: _env.set(prop, old)


func _nodes_of(classes: Array) -> Array[Node]:
	var out: Array[Node] = []
	var stack: Array[Node] = [_root_node]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for c in n.get_children():
			stack.append(c)
		for cls: String in classes:
			if n.is_class(cls):
				out.append(n)
				break
	return out


func _hide_class(a: String, b: String = "") -> Callable:
	var classes := [a] if b == "" else [a, b]
	var arr := _nodes_of(classes)
	var was: Array[bool] = []
	var vis := 0
	for n in arr:
		was.append((n as Node3D).visible)
		if (n as Node3D).visible:
			vis += 1
		(n as Node3D).visible = false
	print("PERF   (%s: %d nodes, %d were visible)" % [str(classes), arr.size(), vis])
	return func() -> void:
		for i in arr.size():
			if is_instance_valid(arr[i]):
				(arr[i] as Node3D).visible = was[i]


func _hide_script(file: String) -> Callable:
	var arr: Array[Node] = []
	for n in _nodes_of(["Node3D"]):
		var s: Script = n.get_script()
		if s != null and s.resource_path.ends_with(file):
			arr.append(n)
	for n in arr:
		(n as Node3D).visible = false
	return func() -> void:
		for n in arr:
			if is_instance_valid(n):
				(n as Node3D).visible = true


func _sun() -> DirectionalLight3D:
	return _root_node.find_child("Sun", true, false) as DirectionalLight3D


func _sun_shadow_off() -> Callable:
	var s := _sun()
	s.shadow_enabled = false
	return func() -> void: s.shadow_enabled = true


func _sun_splits() -> Callable:
	var s := _sun()
	var old := s.directional_shadow_mode
	s.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	return func() -> void: s.directional_shadow_mode = old


func _render_scale(v: float) -> Callable:
	var old := root.scaling_3d_scale
	var old_mode := root.scaling_3d_mode
	root.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
	root.scaling_3d_scale = v
	return func() -> void:
		root.scaling_3d_scale = old
		root.scaling_3d_mode = old_mode


func _disable_named(nm: String) -> Callable:
	var n := _root_node.find_child(nm, true, false)
	if n == null:
		return Callable()
	n.process_mode = Node.PROCESS_MODE_DISABLED
	(n as Node3D).visible = false
	return func() -> void:
		n.process_mode = Node.PROCESS_MODE_INHERIT
		(n as Node3D).visible = true


func _disable_script(file: String, hide: bool = true) -> Callable:
	var arr: Array[Node] = []
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for c in n.get_children():
			stack.append(c)
		var sc: Script = n.get_script()
		if sc != null and sc.resource_path.ends_with(file):
			arr.append(n)
	for n in arr:
		n.process_mode = Node.PROCESS_MODE_DISABLED
		if hide and n is Node3D:
			(n as Node3D).visible = false
	print("PERF   (%s x%d)" % [file, arr.size()])
	return func() -> void:
		for n in arr:
			if is_instance_valid(n):
				n.process_mode = Node.PROCESS_MODE_INHERIT
				if hide and n is Node3D:
					(n as Node3D).visible = true


func _npc_anims_off() -> Callable:
	var ld := _root_node.find_child("LifeDirector", true, false)
	var arr: Array[Node] = []
	for n in ld.find_children("*", "AnimationMixer", true, false):
		if (n as AnimationMixer).active:
			arr.append(n)
			(n as AnimationMixer).active = false
	print("PERF   (npc anim mixers x%d)" % arr.size())
	return func() -> void:
		for n in arr:
			if is_instance_valid(n):
				(n as AnimationMixer).active = true


func _sun_cfg(mode: int, dist: float, atlas: int = 0) -> Callable:
	var s := _sun()
	var om := s.directional_shadow_mode
	var od := s.directional_shadow_max_distance
	s.directional_shadow_mode = mode
	s.directional_shadow_max_distance = dist
	if atlas > 0:
		RenderingServer.directional_shadow_atlas_set_size(atlas, true)
	return func() -> void:
		s.directional_shadow_mode = om
		s.directional_shadow_max_distance = od
		if atlas > 0:
			RenderingServer.directional_shadow_atlas_set_size(8192, true)


func _lights_fade(dist: float) -> Callable:
	var arr := _nodes_of(["OmniLight3D", "SpotLight3D"])
	var changed: Array[Light3D] = []
	for n in arr:
		var l := n as Light3D
		if not l.distance_fade_enabled:
			l.distance_fade_enabled = true
			l.distance_fade_begin = dist
			l.distance_fade_length = 10.0
			changed.append(l)
	print("PERF   (lights given fade x%d of %d)" % [changed.size(), arr.size()])
	return func() -> void:
		for l in changed:
			l.distance_fade_enabled = false


func _noproc(nm: String) -> Callable:
	var n := _root_node.find_child(nm, true, false)
	n.set_process(false)
	n.set_physics_process(false)
	return func() -> void:
		n.set_process(true)
		n.set_physics_process(true)
