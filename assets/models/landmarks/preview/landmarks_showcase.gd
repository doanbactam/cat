extends Node3D
## QA / showcase scene for the city-landmarks kit: every catalog module placed in a compact mini
## quarter (temple, market, lake with embankments + bridge + islet, tea stall, café) with preview-only
## ground, water and lighting. The real city is assembled by the `world` area.
## Screenshot: tools/screenshot.sh scene=res://assets/models/landmarks/preview/landmarks_showcase.tscn
##   out=/abs.png cam=x,y,z look=x,y,z  (placements are printed as PREVIEW_LM lines)

const CATALOG := "res://assets/models/landmarks/catalog.json"
const TEX := "res://assets/textures/architecture/"
const TEX_LM := "res://assets/textures/landmarks/"
const CAT := "res://assets/models/cat/cat.glb"

@export var use_sdfgi := true
@export var sun_elevation_deg := 48.0
@export var sun_azimuth_deg := 35.0
@export var night := false

## Lake rectangle (Godot): x LAKE_X0..LAKE_X1, z LAKE_Z0..LAKE_Z1, water level -1.0
const LAKE_X0 := -64.0
const LAKE_X1 := -24.0
const LAKE_Z0 := 0.0
const LAKE_Z1 := 40.0

var _catalog: Dictionary = {}
var placed: Array[Node3D] = []


func _ready() -> void:
	_load_catalog()
	_build_environment()
	_build_ground()
	_layout()
	_add_scale_reference()


func _load_catalog() -> void:
	var f := FileAccess.open(CATALOG, FileAccess.READ)
	if f == null:
		push_error("landmarks_showcase: catalog missing")
		return
	var data: Variant = JSON.parse_string(f.get_as_text())
	if data is Array:
		for e: Variant in data:
			var d := e as Dictionary
			_catalog[String(d["id"])] = d


func place(id: String, pos: Vector3, yaw_deg := 0.0) -> Node3D:
	if not _catalog.has(id):
		push_warning("landmarks_showcase: unknown module " + id)
		return null
	var ps := load(String(_catalog[id]["file"])) as PackedScene
	if ps == null:
		return null
	var inst := ps.instantiate() as Node3D
	add_child(inst)
	inst.position = pos
	inst.rotation.y = deg_to_rad(yaw_deg)
	inst.set_meta(&"landmark_id", id)
	placed.append(inst)
	print("PREVIEW_LM %s at %s yaw %.0f" % [id, pos, yaw_deg])
	return inst


func _layout() -> void:
	# temple: gate faces the street at z = 44, complex extends north (-Z)
	place("dinh_hang_may", Vector3(0, 0, 44))
	# market hall east, stall lane + gate arch in front
	place("cho_market_hall", Vector3(44, 0, 30))
	place("cho_stall_lane", Vector3(44, 0, 38), 180.0)
	place("cho_stall_lane", Vector3(56, 0, 38), 180.0)
	place("cho_gate_arch", Vector3(32, 0, 40), 90.0)
	# lake shores: north shore (water toward +Z), south shore (water toward -Z), east shore (-X)
	var x := LAKE_X0 + 2.0
	var k := 0
	while x < LAKE_X1 - 1.0:
		var id := "ho_embank_steps_4m" if k == 4 else "ho_embank_straight_4m"
		place(id, Vector3(x, 0, LAKE_Z0), 0.0)
		if k != 4:
			place("ho_railing_4m", Vector3(x, 0, LAKE_Z0), 0.0)
		place("ho_embank_straight_4m" if k != 2 else "ho_embank_steps_4m", Vector3(x, 0, LAKE_Z1), 180.0)
		x += 4.0
		k += 1
	var z := LAKE_Z0 + 2.0
	while z < LAKE_Z1 - 1.0:
		place("ho_embank_straight_4m", Vector3(LAKE_X1, 0, z), -90.0)
		place("ho_embank_straight_4m", Vector3(LAKE_X0, 0, z), 90.0)
		z += 4.0
	# a curved piece displayed on its own little pond corner model (QA of the arc)
	place("ho_embank_curve_30", Vector3(-12.0, 0, 70.0), 0.0)
	# bridge from the south shore to the islet
	place("ho_bridge", Vector3(-44.0, 0, 31.2))
	place("ho_islet_shrine", Vector3(-44.0, 0, 19.6))
	for i in 5:
		var lx := LAKE_X0 + 6.0 + i * 8.0
		place("ho_lamp_post", Vector3(lx, 0, LAKE_Z1 + 2.6))
		place("ho_bench", Vector3(lx + 3.0, 0, LAKE_Z1 + 2.4), 180.0)
	place("shrine_tree", Vector3(-20.5, 0, 44.0), 200.0)
	# shops: café module + tea stall against a plain wall at the alley mouth
	place("cafe_bong", Vector3(18.0, 0, 54.0))
	place("quan_tra_ba_tu", Vector3(9.0, 0, 54.0))
	_wall(Vector3(9.0, 2.0, 54.0 - 2.95), Vector3(4.6, 4.0, 0.3))
	place("shrine_wall_box", Vector3(11.0, 1.7, 54.0 - 2.8))


func _tex_mat(dir: String, set_name: String, tint: Color, scale_m: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(dir + set_name + "_albedo.jpg") as Texture2D
	m.normal_enabled = true
	m.normal_texture = load(dir + set_name + "_normal.png") as Texture2D
	var orm := load(dir + set_name + "_orm.jpg") as Texture2D
	m.roughness_texture = orm
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.ao_enabled = true
	m.ao_texture = orm
	m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.albedo_color = tint
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE / scale_m
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return m


func _box(size: Vector3, pos: Vector3, mat: Material, collide := true) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	if collide:
		var body := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var sh := BoxShape3D.new()
		sh.size = size
		cs.shape = sh
		body.add_child(cs)
		body.position = pos
		add_child(body)


func _wall(pos: Vector3, size: Vector3) -> void:
	_box(size, pos, _tex_mat(TEX, "plaster_yellow", Color(1, 1, 1), 2.0))


func _build_ground() -> void:
	var road := _tex_mat(TEX, "concrete_weathered", Color(0.5, 0.5, 0.5), 2.0)
	var pave := _tex_mat(TEX, "terrazzo", Color(0.78, 0.62, 0.55), 0.5)
	# ground around the lake hole (lake x -64..-24, z 0..40)
	_box(Vector3(200, 0.4, 60), Vector3(0, -0.2, 70), road)            # south band z 40..100
	_box(Vector3(200, 0.4, 60), Vector3(0, -0.2, -30), road)           # north band z -60..0
	_box(Vector3(36, 0.4, 40), Vector3(-82, -0.2, 20), road)           # west of lake
	_box(Vector3(124, 0.4, 40), Vector3(38, -0.2, 20), road)           # east of lake
	_box(Vector3(30, 0.02, 6), Vector3(10, 0.01, 57.5), pave, false)   # sidewalk at the shops
	# lake bed + water
	_box(Vector3(LAKE_X1 - LAKE_X0, 0.2, LAKE_Z1 - LAKE_Z0), Vector3((LAKE_X0 + LAKE_X1) * 0.5, -1.7,
		(LAKE_Z0 + LAKE_Z1) * 0.5), _tex_mat(TEX_LM, "leaves_ground", Color(0.4, 0.42, 0.35), 2.0))
	var water := StandardMaterial3D.new()
	water.albedo_color = Color(0.09, 0.14, 0.11, 0.86)
	water.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	water.roughness = 0.03
	water.metallic_specular = 0.8
	var wm := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(LAKE_X1 - LAKE_X0, LAKE_Z1 - LAKE_Z0)
	wm.mesh = pm
	wm.material_override = water
	wm.position = Vector3((LAKE_X0 + LAKE_X1) * 0.5, -1.0, (LAKE_Z0 + LAKE_Z1) * 0.5)
	add_child(wm)
	# small pond for the curve QA piece
	var pond := MeshInstance3D.new()
	var pp := PlaneMesh.new()
	pp.size = Vector2(16, 10)
	pond.mesh = pp
	pond.material_override = water
	pond.position = Vector3(-12.0, -0.02, 76.0)
	add_child(pond)


func _add_scale_reference() -> void:
	if not ResourceLoader.exists(CAT):
		return
	var ps := load(CAT) as PackedScene
	for p: Vector3 in [Vector3(9.4, 0.0, 54.6), Vector3(0.6, 0.0, 46.0), Vector3(-43.6, 1.56, 31.2)]:
		var c := ps.instantiate() as Node3D
		add_child(c)
		c.position = p
		c.rotation.y = deg_to_rad(200.0)


func _build_environment() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var psm := ProceduralSkyMaterial.new()
	psm.sky_top_color = Color(0.32, 0.47, 0.72) if not night else Color(0.02, 0.03, 0.06)
	psm.sky_horizon_color = Color(0.74, 0.76, 0.78) if not night else Color(0.06, 0.07, 0.1)
	psm.ground_horizon_color = Color(0.6, 0.58, 0.55)
	psm.ground_bottom_color = Color(0.25, 0.24, 0.22)
	sky.sky_material = psm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0 if not night else 0.25
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.0
	env.ssil_enabled = true
	env.ssr_enabled = true
	env.sdfgi_enabled = use_sdfgi
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 4
	env.sdfgi_min_cell_size = 0.2
	env.glow_enabled = true
	env.glow_intensity = 0.5 if night else 0.3
	env.fog_enabled = true
	env.fog_light_color = Color(0.74, 0.76, 0.78) if not night else Color(0.05, 0.06, 0.08)
	env.fog_density = 0.004
	env.fog_sky_affect = 0.15
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.93, 0.82) if not night else Color(0.55, 0.62, 0.85)
	sun.light_energy = 2.6 if not night else 0.12
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	sun.rotation = Vector3(deg_to_rad(-sun_elevation_deg), deg_to_rad(sun_azimuth_deg), 0.0)
	add_child(sun)
	if night:
		_light_up.call_deferred()


func _light_up() -> void:
	# night QA: raise every landmark night light / emissive material like the world would
	for l in get_tree().get_nodes_in_group(&"landmark_night_light"):
		(l as OmniLight3D).light_energy = float(l.get_meta(&"night_energy", 2.0))
	for mi in find_children("*", "MeshInstance3D", true, false):
		if not mi.has_meta(&"night_emissive"):
			continue
		var mesh := (mi as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			var m := mesh.surface_get_material(i) as StandardMaterial3D
			if m and m.has_meta(&"night_emission_energy"):
				m.emission_energy_multiplier = float(m.get_meta(&"night_emission_energy"))
