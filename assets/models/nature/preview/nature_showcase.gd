extends Node3D
## vehicles-nature showcase: instances every entry of a catalog in a lit test yard so assets can be
## judged in-engine at cat eye height (tools/screenshot.sh scene=res://assets/models/nature/preview/nature_showcase.tscn).
## Layout: trees/palms/bamboo on the back rows, shrubs/climbers/ground cover in front, aquatic plants on a
## pond. A cat (assets/models/cat/cat.glb, if present) stands at the origin for scale.

@export var catalog_path := "res://assets/models/nature/catalog.json"
@export var only_ids: PackedStringArray = []

const GROUND_TEX := "res://assets/textures/ground/pavers_"


func _ready() -> void:
	_build_environment()
	_build_ground()
	_place_assets()
	var cat_path := "res://assets/models/cat/cat.glb"
	if ResourceLoader.exists(cat_path):
		var cat := (load(cat_path) as PackedScene).instantiate() as Node3D
		cat.name = "ScaleCat"
		add_child(cat)
		cat.position = Vector3(0.6, 0.0, 3.0)
		cat.rotation.y = deg_to_rad(-60.0)


func _build_environment() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.32, 0.5, 0.78)
	sm.sky_horizon_color = Color(0.72, 0.78, 0.84)
	sm.ground_horizon_color = Color(0.6, 0.6, 0.58)
	sm.ground_bottom_color = Color(0.25, 0.24, 0.22)
	sky.sky_material = sm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.9
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 0.8
	env.ssil_enabled = false
	env.fog_enabled = true
	env.fog_density = 0.0025
	env.fog_light_color = Color(0.75, 0.8, 0.86)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_energy = 1.6
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 80.0
	sun.rotation_degrees = Vector3(-48.0, -35.0, 0.0)
	add_child(sun)
	RenderingServer.global_shader_parameter_set(&"wind_strength", 0.35)


func _build_ground() -> void:
	var mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(120, 120)
	mi.mesh = pm
	var mat := StandardMaterial3D.new()
	if ResourceLoader.exists(GROUND_TEX + "albedo.jpg"):
		mat.albedo_texture = load(GROUND_TEX + "albedo.jpg")
		if ResourceLoader.exists(GROUND_TEX + "normal.png"):
			mat.normal_enabled = true
			mat.normal_texture = load(GROUND_TEX + "normal.png")
		mat.uv1_scale = Vector3(110, 110, 110)
	else:
		mat.albedo_color = Color(0.42, 0.4, 0.37)
	mat.roughness = 0.85
	mi.material_override = mat
	add_child(mi)
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(120, 0.2, 120)
	cs.shape = bs
	cs.position.y = -0.1
	body.add_child(cs)
	add_child(body)


func _place_assets() -> void:
	var f := FileAccess.open(catalog_path, FileAccess.READ)
	if f == null:
		return
	var cat: Array = JSON.parse_string(f.get_as_text())
	var x_back := -40.0
	var x_mid := -6.0
	var x_front := -3.0
	var pond_x := 7.0
	var pond := false
	for e: Variant in cat:
		var d := e as Dictionary
		var id := String(d["id"])
		if only_ids.size() > 0 and not (id in only_ids):
			continue
		var ps := load(String(d["file"])) as PackedScene
		if ps == null:
			continue
		var n := ps.instantiate() as Node3D
		n.name = id
		add_child(n)
		var w := maxf(float(d.get("width", 1.0)), 0.5)
		var kind := String(d.get("kind", ""))
		if kind in ["tree", "palm", "bamboo"]:
			n.position = Vector3(x_back + w * 0.5, 0.0, -12.0)
			x_back += w + 0.5
		elif kind == "aquatic":
			pond = true
			n.position = Vector3(pond_x, 0.02, 2.0)
			pond_x += 2.6
		elif kind in ["climber"]:
			n.position = Vector3(x_mid + w * 0.5, 2.6 if String(d.get("mount", "")).begins_with("rail") else 0.0, -2.5)
			x_mid += w + 0.5
		else:
			n.position = Vector3(x_front + w * 0.5, 0.0, 1.5)
			x_front += w + 0.4
	if pond:
		var wm := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(7.0, 4.0)
		wm.mesh = pm
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.12, 0.2, 0.18, 0.85)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.roughness = 0.05
		mat.metallic_specular = 0.9
		wm.material_override = mat
		wm.position = Vector3(9.6, 0.015, 2.0)
		add_child(wm)
