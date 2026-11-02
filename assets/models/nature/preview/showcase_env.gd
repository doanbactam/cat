extends RefCounted
## Shared daylight environment + textured ground for the vehicles-nature showcase scenes.
## Usage: `preload("res://assets/models/nature/preview/showcase_env.gd").build(self, "asphalt_", 0.25)`.

const GROUND_DIR := "res://assets/textures/ground/"


static func build(parent: Node3D, ground_set: String, tiles_per_m: float, sun_elev_deg := 42.0,
		sun_azimuth_deg := -38.0) -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var psm := ProceduralSkyMaterial.new()
	psm.sky_top_color = Color(0.3, 0.46, 0.72)
	psm.sky_horizon_color = Color(0.72, 0.76, 0.8)
	psm.ground_horizon_color = Color(0.6, 0.58, 0.55)
	psm.ground_bottom_color = Color(0.25, 0.24, 0.22)
	psm.sun_angle_max = 20.0
	sky.sky_material = psm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 1.0
	env.ssao_intensity = 1.8
	env.ssil_enabled = true
	env.ssr_enabled = true
	env.glow_enabled = true
	env.glow_intensity = 0.25
	env.fog_enabled = true
	env.fog_light_color = Color(0.74, 0.77, 0.8)
	env.fog_density = 0.0018
	env.fog_sky_affect = 0.1
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	parent.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_energy = 2.5
	sun.light_color = Color(1.0, 0.94, 0.84)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 90.0
	sun.rotation = Vector3(deg_to_rad(-sun_elev_deg), deg_to_rad(sun_azimuth_deg), 0.0)
	parent.add_child(sun)
	RenderingServer.global_shader_parameter_set(&"wind_strength", 0.35)
	RenderingServer.global_shader_parameter_set(&"wind_direction", Vector3(1.0, 0.0, 0.3).normalized())
	_ground(parent, ground_set, tiles_per_m)


static func _ground(parent: Node3D, ground_set: String, tiles_per_m: float) -> void:
	var size := 140.0
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	var pm := PlaneMesh.new()
	pm.size = Vector2(size, size)
	mi.mesh = pm
	var mat := ORMMaterial3D.new()
	var base := GROUND_DIR + ground_set
	if ResourceLoader.exists(base + "albedo.jpg"):
		mat.albedo_texture = load(base + "albedo.jpg")
		if ResourceLoader.exists(base + "normal.png"):
			mat.normal_enabled = true
			mat.normal_texture = load(base + "normal.png")
		if ResourceLoader.exists(base + "orm.jpg"):
			mat.orm_texture = load(base + "orm.jpg")
		var s := size * tiles_per_m
		mat.uv1_scale = Vector3(s, s, s)
		mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	else:
		mat.albedo_color = Color(0.42, 0.4, 0.37)
		mat.roughness = 0.85
	mi.material_override = mat
	parent.add_child(mi)
	var body := StaticBody3D.new()
	body.name = "GroundBody"
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(size, 0.2, size)
	cs.shape = bs
	cs.position.y = -0.1
	body.add_child(cs)
	parent.add_child(body)
