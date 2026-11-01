extends Node3D
## Preview / QA scene for the city-houses kit: a short old-quarter street built from catalog.json.
## North row (facing +Z) and an opposite south row (rotated 180 deg) across a 7.5 m road with
## 3 m sidewalks. Preview-only lighting/ground; the real city is assembled by the `world` area.
## Screenshot: tools/screenshot.sh scene=res://assets/models/city/preview/street_row.tscn out=/abs.png
##   cam=x,y,z look=x,y,z (row x positions are printed as PREVIEW_ROW lines).

const CATALOG := "res://assets/models/city/catalog.json"
const TEX := "res://assets/textures/architecture/"

## The 8 hero modules of the QA row (centre), padded with more modules at both ends so the street
## recedes into the distance like a real one.
@export var north_row: PackedStringArray = PackedStringArray([
	"tube90s_4f_w5_green", "colonial_3f_w5_white", "oldtile_1f_w4_white", "colonial_2f_w4_ochre",
	"tube90s_4f_w4_blue", "tube90s_5f_w3_5_yellow", "colonial_3f_w5_pink", "modern_5f_w4_white",
	"tube90s_3f_w4_5_green", "tube90s_6f_w5_white", "colonial_2f_w4_blue", "tube90s_5f_w3_5_white",
	"modern_4f_w6_white"])
@export var south_row: PackedStringArray = PackedStringArray([
	"tube90s_6f_w5_yellow", "colonial_2f_w4_yellow", "tube90s_4f_w5_pink", "colonial_2f_w6_yellow",
	"tube90s_4f_w4_green", "oldtile_1f_w5_shop_yellow", "modern_4f_w6_dark", "colonial_3f_w4_5_ochre",
	"tube90s_3f_w4_5_pink", "oldtile_1f_w4_yellow", "tube90s_6f_w5_blue", "colonial_3f_w5_ochre"])
## x positions (relative to the street centre) of cable bundles strung across the street
@export var cable_x: PackedFloat32Array = PackedFloat32Array([-24.0, -13.5, -6.0, 3.5, 12.0, 21.0])
@export var use_sdfgi := true
## alley mode: no curbs/road, plain concrete ground, short cable spans (alley_row.tscn)
@export var alley_mode := false
@export var cable_module := "res://assets/models/city/roofprop_cables_street.glb"
@export var cable_height := 6.2
@export var sidewalk_w := 3.0
@export var road_w := 7.5
@export var sun_elevation_deg := 54.0
@export var sun_azimuth_deg := 28.0

var _catalog: Dictionary = {}


func _ready() -> void:
	_load_catalog()
	_build_environment()
	var north_len := _build_row(north_row, Vector3.ZERO, false)
	var far_z := sidewalk_w * 2.0 + road_w
	var south_len := _build_row(south_row, Vector3(0.0, 0.0, far_z), true)
	_build_ground(maxf(north_len, south_len) + 16.0, far_z)
	_add_cables(far_z)
	_add_scale_reference()


func _add_cables(far_z: float) -> void:
	var path := cable_module
	if not ResourceLoader.exists(path):
		return
	var ps := load(path) as PackedScene
	var i := 0
	for x in cable_x:
		var c := ps.instantiate() as Node3D
		add_child(c)
		c.rotation.y = PI * 0.5 + (0.08 if i % 2 == 0 else -0.06)
		c.position = Vector3(x, cable_height + 0.5 * float(i % 3), far_z * 0.5)
		i += 1


func _load_catalog() -> void:
	var f := FileAccess.open(CATALOG, FileAccess.READ)
	if f == null:
		push_error("street_row: catalog missing")
		return
	var data: Variant = JSON.parse_string(f.get_as_text())
	if data is Array:
		for e: Variant in data:
			var d := e as Dictionary
			_catalog[String(d["id"])] = d


func _build_row(ids: PackedStringArray, origin: Vector3, flipped: bool) -> float:
	var x := 0.0
	var total := 0.0
	for id in ids:
		if _catalog.has(id):
			total += float(_catalog[id]["width"])
	x = -total * 0.5
	for id in ids:
		if not _catalog.has(id):
			push_warning("street_row: unknown module " + id)
			continue
		var e: Dictionary = _catalog[id]
		var w := float(e["width"])
		var ps := load(String(e["file"])) as PackedScene
		if ps == null:
			continue
		var inst := ps.instantiate() as Node3D
		add_child(inst)
		var cx := x + w * 0.5
		if flipped:
			inst.position = origin + Vector3(-cx, 0.0, 0.0)
			inst.rotation.y = PI
		else:
			inst.position = origin + Vector3(cx, 0.0, 0.0)
		print("PREVIEW_ROW %s x=%.2f z=%.2f h=%.1f flipped=%s" % [id, inst.position.x, inst.position.z,
			float(e["height"]), flipped])
		x += w
	return total


func _tex_mat(set_name: String, tint: Color, scale_m: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_texture = load(TEX + set_name + "_albedo.jpg") as Texture2D
	m.normal_enabled = true
	m.normal_texture = load(TEX + set_name + "_normal.png") as Texture2D
	var orm := load(TEX + set_name + "_orm.jpg") as Texture2D
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


func _box(size: Vector3, pos: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	body.add_child(cs)
	body.position = pos
	add_child(body)


func _build_ground(length: float, far_z: float) -> void:
	if alley_mode:
		var conc := _tex_mat("concrete_weathered", Color(0.75, 0.74, 0.72), 2.0)
		_box(Vector3(length, 0.3, far_z + 2.0), Vector3(0, -0.15, far_z * 0.5), conc)
		return
	var paving := _tex_mat("terrazzo", Color(0.78, 0.6, 0.52), 0.5)
	var curb := _tex_mat("granite_red", Color(0.55, 0.55, 0.55), 1.0)
	var road := _tex_mat("concrete_weathered", Color(0.34, 0.34, 0.35), 2.0)
	_box(Vector3(length, 0.3, sidewalk_w + 2.0), Vector3(0, -0.15, sidewalk_w * 0.5 - 1.0), paving)
	_box(Vector3(length, 0.3, sidewalk_w + 2.0), Vector3(0, -0.15, far_z - sidewalk_w * 0.5 + 1.0), paving)
	_box(Vector3(length, 0.3, 0.18), Vector3(0, -0.15, sidewalk_w + 0.09), curb)
	_box(Vector3(length, 0.3, 0.18), Vector3(0, -0.15, far_z - sidewalk_w - 0.09), curb)
	_box(Vector3(length, 0.3, road_w), Vector3(0, -0.3, sidewalk_w + road_w * 0.5), road)


func _build_environment() -> void:
	var env := Environment.new()
	var sky := Sky.new()
	var psm := ProceduralSkyMaterial.new()
	psm.sky_top_color = Color(0.32, 0.47, 0.72)
	psm.sky_horizon_color = Color(0.72, 0.76, 0.8)
	psm.ground_horizon_color = Color(0.6, 0.58, 0.55)
	psm.ground_bottom_color = Color(0.25, 0.24, 0.22)
	psm.sun_angle_max = 30.0
	sky.sky_material = psm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.2
	env.ssil_enabled = true
	env.ssr_enabled = false
	env.sdfgi_enabled = use_sdfgi
	env.sdfgi_use_occlusion = true
	env.sdfgi_energy = 1.0
	env.sdfgi_cascades = 4
	env.sdfgi_min_cell_size = 0.2
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = Color(0.74, 0.76, 0.78)
	env.fog_depth_begin = 40.0
	env.fog_depth_end = 260.0
	env.fog_density = 0.4
	env.fog_sky_affect = 0.15
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.05
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.93, 0.82)
	sun.light_energy = 2.6
	sun.light_angular_distance = 0.6
	sun.shadow_enabled = true
	sun.shadow_bias = 0.03
	sun.shadow_normal_bias = 1.0
	sun.directional_shadow_max_distance = 90.0
	sun.rotation_degrees = Vector3(-sun_elevation_deg, sun_azimuth_deg, 0.0)
	add_child(sun)


func _add_scale_reference() -> void:
	# A cat for scale when the cat asset exists, otherwise an orange 0.25 m shoulder-height block.
	var cat_path := "res://assets/models/cat/cat.glb"
	var pos := Vector3(1.0, 0.0, 1.6)
	if ResourceLoader.exists(cat_path):
		var cat := (load(cat_path) as PackedScene).instantiate() as Node3D
		cat.position = pos
		cat.rotation.y = 0.6
		add_child(cat)
	else:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.85, 0.45, 0.15)
		var mi := MeshInstance3D.new()
		var cm := CapsuleMesh.new()
		cm.radius = 0.09
		cm.height = 0.46
		mi.mesh = cm
		mi.material_override = mat
		mi.rotation_degrees = Vector3(0, 30, 90)
		mi.position = pos + Vector3(0, 0.2, 0)
		add_child(mi)
