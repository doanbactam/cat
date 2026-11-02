extends Node3D
## Street-props showcase: lays out catalog props in rows (one row per category) on a ground plane,
## with sky, sun and a self-framing camera. Used for in-engine QA screenshots:
##   tools/screenshot.sh scene=res://assets/models/props/preview/props_showcase.tscn out=/abs.png \
##       size=1280x720 frames=40 [hour=21] -- props=stall,furniture
## User args (after `--`, read from the command line): `props=` comma list of categories or ids
## (prefix match with `*`), `cols=` max props per row, `night=1` forces night lighting.

const CATALOG := "res://assets/models/props/catalog.json"

var _filter: PackedStringArray = []
var _cols := 10
var _night := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"props":
				_filter = kv[1].split(",", false)
			"cols":
				_cols = maxi(1, int(kv[1]))
			"night":
				_night = kv[1] == "1"
			"hour":
				_night = float(kv[1]) > 18.5 or float(kv[1]) < 5.5
	_build_env()
	var extent := _layout()
	_frame_camera(extent)


func _want(e: Dictionary) -> bool:
	if _filter.is_empty():
		return true
	var id := String(e["id"])
	for f in _filter:
		if f == String(e.get("category", "")) or f == id:
			return true
		if f.ends_with("*") and id.begins_with(f.trim_suffix("*")):
			return true
	return false


func _layout() -> AABB:
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	var rows := {}
	var order: Array[String] = []
	for e: Variant in data:
		var d := e as Dictionary
		if not _want(d):
			continue
		var c := String(d.get("category", "misc"))
		if not rows.has(c):
			rows[c] = []
			order.append(c)
		(rows[c] as Array).append(d)
	var z := 0.0
	var box := AABB()
	var first := true
	for c in order:
		var list: Array = rows[c]
		var chunks: Array = []
		for i in range(0, list.size(), _cols):
			chunks.append(list.slice(i, i + _cols))
		for chunk: Array in chunks:
			var widths: Array[float] = []
			var depth := 0.0
			for d: Dictionary in chunk:
				var fp := d["footprint"] as Array
				widths.append(float(fp[0]))
				depth = maxf(depth, float(fp[1]))
			var gap := clampf(depth * 0.35, 0.08, 0.6)
			var total := 0.0
			for w in widths:
				total += w + gap
			var x := -total * 0.5
			for i in chunk.size():
				var d: Dictionary = chunk[i]
				var ps := load(String(d["file"])) as PackedScene
				if ps == null:
					continue
				var n := ps.instantiate() as Node3D
				if n is RigidBody3D:
					(n as RigidBody3D).freeze = true
				var bmin := d.get("bounds_min", [0, 0, 0]) as Array
				var bmax := d.get("bounds_max", [0, 0, 0]) as Array
				var cx := (float(bmin[0]) + float(bmax[0])) * 0.5
				var lift := -float(bmin[1]) if float(bmin[1]) < -0.001 else 0.0
				add_child(n)
				n.position = Vector3(x + widths[i] * 0.5 - cx, lift, z)
				var lb := Label3D.new()
				lb.text = String(d["id"])
				lb.font_size = 28
				lb.pixel_size = clampf(widths[i] * 0.0012, 0.0004, 0.002)
				lb.position = Vector3(x + widths[i] * 0.5, 0.004, z + float((d["footprint"] as Array)[1]) * 0.5 + 0.04)
				lb.rotation_degrees = Vector3(-90, 0, 0)
				lb.modulate = Color(1, 1, 1, 0.8)
				add_child(lb)
				var h := float(d["height"]) + lift
				var b := AABB(Vector3(x, 0, z - depth * 0.5), Vector3(widths[i], maxf(h, 0.01), depth))
				box = b if first else box.merge(b)
				first = false
				x += widths[i] + gap
			z -= depth + gap * 2.0
	return box


func _build_env() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.32, 0.5, 0.78) if not _night else Color(0.01, 0.015, 0.04)
	sm.sky_horizon_color = Color(0.75, 0.78, 0.8) if not _night else Color(0.04, 0.04, 0.07)
	sm.ground_horizon_color = sm.sky_horizon_color
	sm.ground_bottom_color = Color(0.2, 0.18, 0.16)
	sky.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0 if not _night else 0.25
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.glow_enabled = true
	env.glow_bloom = 0.05 if not _night else 0.15
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-42, -35, 0)
	sun.light_energy = 1.6 if not _night else 0.05
	sun.light_color = Color(1.0, 0.95, 0.88)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 40.0
	add_child(sun)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	ground.mesh = pm
	var gmat := StandardMaterial3D.new()
	gmat.albedo_color = Color(0.36, 0.35, 0.33)
	gmat.roughness = 0.9
	gmat.albedo_color = Color(0.42, 0.41, 0.39)
	gmat.roughness = 0.85
	ground.material_override = gmat
	add_child(ground)
	if _night:
		# light every prop night emitter right away (the NightLight controllers fade over time)
		await get_tree().process_frame
		for l: Node in get_tree().get_nodes_in_group(&"prop_night_light"):
			(l as Light3D).light_energy = float(l.get_meta(&"night_light_energy", 1.0))
		_light_materials(self)


func _light_materials(n: Node) -> void:
	if n is MeshInstance3D:
		var mi := n as MeshInstance3D
		if mi.mesh != null:
			for s in mi.mesh.get_surface_count():
				var m := mi.mesh.surface_get_material(s) as StandardMaterial3D
				if m != null and m.has_meta(&"night_emission_energy"):
					m.emission_energy_multiplier = float(m.get_meta(&"night_emission_energy"))
	for c in n.get_children():
		_light_materials(c)


func _frame_camera(box: AABB) -> void:
	var cam := Camera3D.new()
	cam.fov = 40.0
	cam.near = 0.01
	cam.far = 400.0
	add_child(cam)
	var c := box.get_center()
	var r := maxf(box.size.x, maxf(box.size.y * 1.6, box.size.z))
	var dist := r * 0.5 / tan(deg_to_rad(cam.fov * 0.5)) * 0.78 + 0.15
	cam.position = c + Vector3(0.0, dist * 0.55, dist * 0.95)
	cam.look_at(c + Vector3(0, box.size.y * 0.1, 0), Vector3.UP)
	cam.make_current()
