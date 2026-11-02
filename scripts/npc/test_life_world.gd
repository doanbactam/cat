extends Node3D
## Runtime script of scenes/npc/test_life.tscn (owner: world-life): a compact street block with
## every marker convention so the LifeDirector can be tested standalone. Drives the sun/moon from
## TimeOfDay, spawns Cam at PlayerSpawn (unless `spawn_player` is false, as in tests) and offers
## screenshot helpers: `call=rain`, `call=night`, `call=dusk`, `call=overview`.

@export var spawn_player := true
@export var start_hour := 8.5
@export var drive_time := true

var player: Node3D = null
var _sun: DirectionalLight3D = null
var _moon: DirectionalLight3D = null
var _env: WorldEnvironment = null
var _rain: GPUParticles3D = null


func _ready() -> void:
	_sun = get_node_or_null(^"Sun") as DirectionalLight3D
	_moon = get_node_or_null(^"Moon") as DirectionalLight3D
	_env = get_node_or_null(^"WorldEnvironment") as WorldEnvironment
	var tod := get_node_or_null(^"/root/TimeOfDay")
	if tod != null and drive_time and tod.has_method(&"set_hour"):
		tod.call(&"set_hour", start_hour)
	if spawn_player and get_tree().get_first_node_in_group(&"player") == null and ResourceLoader.exists("res://scenes/player/cat_player.tscn"):
		var spawn := get_node_or_null(^"PlayerSpawn") as Node3D
		player = (load("res://scenes/player/cat_player.tscn") as PackedScene).instantiate() as Node3D
		add_child(player)
		if spawn != null:
			if player.has_method(&"teleport"):
				player.call(&"teleport", spawn.global_transform)
			else:
				player.global_transform = spawn.global_transform
	_update_sky()


func _process(_delta: float) -> void:
	_update_sky()


func _update_sky() -> void:
	var tod := get_node_or_null(^"/root/TimeOfDay")
	var h := 12.0
	if tod != null:
		h = float(tod.get(&"hour"))
	# sun path: rises east (+X) at 6, sets west at 18, tilted south
	var t := (h - 6.0) / 12.0
	var elev := sin(clampf(t, 0.0, 1.0) * PI) * 68.0
	var az := lerpf(-90.0, 90.0, clampf(t, 0.0, 1.0))
	if _sun != null:
		_sun.rotation_degrees = Vector3(-maxf(elev, -10.0), az + 180.0, 0.0)
		var day := clampf(elev / 15.0, 0.0, 1.0)
		_sun.light_energy = 1.6 * day
		_sun.visible = day > 0.01
		var warm := 1.0 - clampf(elev / 35.0, 0.0, 1.0)
		_sun.light_color = Color(1.0, 0.95, 0.86).lerp(Color(1.0, 0.62, 0.36), warm)
	if _moon != null:
		var night := 1.0 - clampf((elev + 5.0) / 10.0, 0.0, 1.0)
		_moon.visible = night > 0.01
		_moon.light_energy = 0.18 * night
	if _env != null and _env.environment != null:
		var e := _env.environment
		var day2 := clampf((elev + 4.0) / 20.0, 0.0, 1.0)
		e.background_energy_multiplier = lerpf(0.05, 1.0, day2)
		e.ambient_light_energy = lerpf(0.12, 0.6, day2)
	for l: Node in get_tree().get_nodes_in_group(&"street_light"):
		if l is Light3D:
			(l as Light3D).visible = h >= 17.8 or h < 6.2


func rain() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and gs.has_method(&"set_weather_state"):
		gs.call(&"set_weather_state", &"rain", 0.8)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.weather_changed.emit(&"rain", 0.8)
	if _rain == null:
		_rain = GPUParticles3D.new()
		_rain.amount = 6000
		_rain.lifetime = 1.2
		_rain.visibility_aabb = AABB(Vector3(-30, -15, -30), Vector3(60, 30, 60))
		var pm := ParticleProcessMaterial.new()
		pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
		pm.emission_box_extents = Vector3(25, 0.5, 25)
		pm.direction = Vector3(0.05, -1, 0)
		pm.spread = 2.0
		pm.initial_velocity_min = 14.0
		pm.initial_velocity_max = 17.0
		pm.gravity = Vector3(0, -9.8, 0)
		_rain.process_material = pm
		var qm := QuadMesh.new()
		qm.size = Vector2(0.012, 0.35)
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.albedo_color = Color(0.8, 0.85, 0.9, 0.35)
		m.billboard_mode = BaseMaterial3D.BILLBOARD_FIXED_Y
		qm.material = m
		_rain.draw_pass_1 = qm
		_rain.position = Vector3(0, 14, 0)
		add_child(_rain)
	if _env != null and _env.environment != null:
		_env.environment.fog_enabled = true
		_env.environment.fog_density = 0.012
	# wet ground look
	for n: Node in find_children("Ground*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		var mat := mi.material_override as StandardMaterial3D
		if mat != null:
			var w := mat.duplicate() as StandardMaterial3D
			w.albedo_color = mat.albedo_color.darkened(0.35)
			w.roughness = 0.12
			mi.material_override = w


func night() -> void:
	var tod := get_node_or_null(^"/root/TimeOfDay")
	if tod != null:
		tod.call(&"set_hour", 21.0)
	_update_sky()


func dusk() -> void:
	var tod := get_node_or_null(^"/root/TimeOfDay")
	if tod != null:
		tod.call(&"set_hour", 17.6)
	_update_sky()
