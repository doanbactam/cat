extends RefCounted
## Material factory for world-generated geometry (owner: world). Cached per key so every builder
## call shares one resource (one draw-call state per material).
##   ground(key)  → ShaderMaterial (shaders/ground.gdshader) with world/ground textures
##   arch(set)    → StandardMaterial3D from assets/textures/architecture/<set>_* (city-houses kit,
##                  used read-only) — UVs are generated in metres / tile_m by the builder
##   flat(name, colour, roughness, metallic) → plain StandardMaterial3D for small painted parts

const GROUND_DIR := "res://assets/textures/ground/"
const ARCH_DIR := "res://assets/textures/architecture/"

## key -> [texture set, tile metres, puddles, macro strength, roughness mul, tint]
const GROUND := {
	&"asphalt": ["asphalt", 4.0, 1.0, 0.22, 1.0, Color(1, 1, 1)],
	&"pavers": ["pavers", 2.0, 0.8, 0.2, 1.0, Color(1, 1, 1)],
	&"granite": ["granite_curb", 1.0, 0.0, 0.12, 1.0, Color(1, 1, 1)],
	&"concrete": ["concrete_alley", 2.0, 1.0, 0.25, 1.0, Color(1, 1, 1)],
	&"gutter": ["concrete_alley", 2.0, 1.0, 0.3, 0.9, Color(0.72, 0.7, 0.66)],
	&"brick": ["brick_courtyard", 2.0, 0.9, 0.18, 1.0, Color(1, 1, 1)],
	&"grass": ["grass", 2.0, 0.4, 0.3, 1.0, Color(1, 1, 1)],
	&"embankment": ["stone_embankment", 2.0, 0.0, 0.15, 1.0, Color(1, 1, 1)],
	&"wood": ["wood_deck", 1.0, 0.3, 0.1, 1.0, Color(1, 1, 1)],
	&"lakebed": ["lakebed", 4.0, 0.0, 0.1, 1.0, Color(1, 1, 1)],
}

static var _cache: Dictionary = {}


static func tile_of(key: StringName) -> float:
	if GROUND.has(key):
		return float(GROUND[key][1])
	return 2.0


static func ground(key: StringName) -> ShaderMaterial:
	var ck := "g_" + String(key)
	if _cache.has(ck):
		return _cache[ck]
	var d: Array = GROUND[key]
	var m := ShaderMaterial.new()
	m.resource_name = "world_ground_" + String(key)
	m.shader = load("res://shaders/ground.gdshader")
	var set_name: String = d[0]
	m.set_shader_parameter(&"albedo_tex", load(GROUND_DIR + set_name + "_albedo.jpg"))
	m.set_shader_parameter(&"normal_tex", load(GROUND_DIR + set_name + "_normal.png"))
	m.set_shader_parameter(&"orm_tex", load(GROUND_DIR + set_name + "_orm.jpg"))
	m.set_shader_parameter(&"noise_tex", load(GROUND_DIR + "noise_rgba.png"))
	m.set_shader_parameter(&"ripple_tex", load(GROUND_DIR + "rain_ripples.png"))
	m.set_shader_parameter(&"puddle_amount", float(d[2]))
	m.set_shader_parameter(&"macro_strength", float(d[3]))
	m.set_shader_parameter(&"roughness_mul", float(d[4]))
	m.set_shader_parameter(&"tint", d[5])
	_cache[ck] = m
	return m


static func arch(set_name: String, tint: Color = Color(1, 1, 1)) -> StandardMaterial3D:
	var ck := "a_%s_%s" % [set_name, tint.to_html()]
	if _cache.has(ck):
		return _cache[ck]
	var m := StandardMaterial3D.new()
	m.resource_name = "world_" + set_name
	m.albedo_texture = load(ARCH_DIR + set_name + "_albedo.jpg")
	m.albedo_color = tint
	m.normal_enabled = true
	m.normal_texture = load(ARCH_DIR + set_name + "_normal.png")
	var orm: Texture2D = load(ARCH_DIR + set_name + "_orm.jpg")
	m.roughness_texture = orm
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.metallic_texture = orm
	m.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
	m.metallic = 1.0
	m.ao_enabled = true
	m.ao_texture = orm
	m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_cache[ck] = m
	return m


## Ground-texture StandardMaterial (for vertical/procedural structures that should still get the
## runtime wet modulation, e.g. embankment walls, bridge deck, crates).
static func ground_std(key: StringName, tint: Color = Color(1, 1, 1)) -> StandardMaterial3D:
	var ck := "gs_%s_%s" % [key, tint.to_html()]
	if _cache.has(ck):
		return _cache[ck]
	var d: Array = GROUND[key]
	var set_name: String = d[0]
	var m := StandardMaterial3D.new()
	m.resource_name = "world_" + set_name
	m.albedo_texture = load(GROUND_DIR + set_name + "_albedo.jpg")
	m.albedo_color = tint
	m.normal_enabled = true
	m.normal_texture = load(GROUND_DIR + set_name + "_normal.png")
	var orm: Texture2D = load(GROUND_DIR + set_name + "_orm.jpg")
	m.roughness_texture = orm
	m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	m.ao_enabled = true
	m.ao_texture = orm
	m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_cache[ck] = m
	return m


static func flat(mat_name: String, color: Color, roughness: float = 0.6, metallic: float = 0.0) -> StandardMaterial3D:
	var ck := "f_" + mat_name
	if _cache.has(ck):
		return _cache[ck]
	var m := StandardMaterial3D.new()
	m.resource_name = "world_" + mat_name
	m.albedo_color = color
	m.roughness = roughness
	m.metallic = metallic
	_cache[ck] = m
	return m


static func emissive(mat_name: String, color: Color, energy: float, transparent: bool = false) -> StandardMaterial3D:
	var ck := "e_" + mat_name
	if _cache.has(ck):
		return _cache[ck]
	var m := StandardMaterial3D.new()
	m.resource_name = "world_" + mat_name
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = energy
	m.roughness = 0.4
	if transparent:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	_cache[ck] = m
	return m


static func water() -> ShaderMaterial:
	if _cache.has("water"):
		return _cache["water"]
	var m := ShaderMaterial.new()
	m.resource_name = "world_lake_water"
	m.shader = load("res://shaders/water_lake.gdshader")
	m.set_shader_parameter(&"wave_normal", load(GROUND_DIR + "water_normal.png"))
	m.set_shader_parameter(&"ripple_tex", load(GROUND_DIR + "rain_ripples.png"))
	m.set_shader_parameter(&"noise_tex", load(GROUND_DIR + "noise_rgba.png"))
	_cache["water"] = m
	return m


static func clear_cache() -> void:
	_cache.clear()
