extends WorldEnvironment
## Day/night + atmosphere controller for Hàng Mây (owner: world).
##
## Drives the Sun and Moon DirectionalLight3Ds, the custom sky shader, fog/volumetric fog, exposure
## and the `night_factor` global shader parameter from TimeOfDay. WeatherSystem pushes cloudiness,
## overcast, extra fog and lightning flashes through set_weather_look(). Implements the
## graphics_settings_listener contract (apply_graphics_settings()).

const KELVIN_SUN_NOON := 5900.0

@export var sun_path: NodePath = ^"../Sun"
@export var moon_path: NodePath = ^"../Moon"
## Azimuth tilt of the sun path toward the south (+Z): Hanoi in September, sun slightly south at noon.
@export var south_tilt := 0.22
## Base humid haze (volumetric fog density) on a clear day.
@export var base_fog_density := 0.0045
@export var day_exposure := 1.0
@export var night_exposure := 1.35

var sun: DirectionalLight3D
var moon: DirectionalLight3D
var sky_mat: ShaderMaterial

# weather look (smoothed by WeatherSystem before it calls us)
var cloud_coverage := 0.3
var overcast := 0.0
var fog_extra := 0.0
var flash := 0.0
var _hour_override := -1.0
## Last computed 0 (day) .. 1 (night); mirrors the `night_factor` shader global.
var night_factor := 0.0
var _shadow_quality := "high"


func _ready() -> void:
	add_to_group(&"graphics_settings_listener")
	add_to_group(&"world_environment_controller")
	sun = get_node_or_null(sun_path) as DirectionalLight3D
	moon = get_node_or_null(moon_path) as DirectionalLight3D
	if environment != null and environment.sky != null:
		sky_mat = environment.sky.sky_material as ShaderMaterial
	if not GameEvents.settings_changed.is_connected(_on_settings_changed):
		GameEvents.settings_changed.connect(_on_settings_changed)
	apply_graphics_settings()
	update_lighting()


func _process(_delta: float) -> void:
	update_lighting()


func _on_settings_changed(section: StringName) -> void:
	if section == &"graphics":
		apply_graphics_settings()


## Called by Settings for every node in group "graphics_settings_listener".
func apply_graphics_settings() -> void:
	if environment == null:
		return
	var s: Node = get_node_or_null(^"/root/Settings")
	if s == null:
		return
	environment.sdfgi_enabled = bool(s.call("get_value", "graphics", "sdfgi", true))
	environment.ssr_enabled = bool(s.call("get_value", "graphics", "ssr", true))
	environment.ssao_enabled = bool(s.call("get_value", "graphics", "ssao", true))
	environment.ssil_enabled = bool(s.call("get_value", "graphics", "ssil", false))
	environment.volumetric_fog_enabled = bool(s.call("get_value", "graphics", "volumetric_fog", true))
	var quality := str(s.call("get_value", "graphics", "quality", "high"))
	_shadow_quality = str(s.call("get_value", "graphics", "shadow_quality", "high"))
	match quality:
		"low":
			environment.sdfgi_cascades = 4
			environment.ssr_max_steps = 32
			environment.glow_enabled = true
		"medium":
			environment.sdfgi_cascades = 4
			environment.ssr_max_steps = 48
		"ultra":
			environment.sdfgi_cascades = 6
			environment.ssr_max_steps = 96
		_:
			environment.sdfgi_cascades = 5
			environment.ssr_max_steps = 64
	_apply_shadow_quality()


func _apply_shadow_quality() -> void:
	var dist := 140.0
	var atlas := 8192
	match _shadow_quality:
		"low":
			dist = 70.0
			atlas = 2048
		"medium":
			dist = 100.0
			atlas = 4096
		"ultra":
			dist = 200.0
			atlas = 8192
	for l: DirectionalLight3D in [sun, moon]:
		if l == null:
			continue
		l.directional_shadow_max_distance = dist
		l.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS if _shadow_quality != "low" else DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	RenderingServer.directional_shadow_atlas_set_size(atlas, true)


## Weather → look. All inputs 0..1 except flash (0..1+).
func set_weather_look(p_cloud: float, p_overcast: float, p_fog: float, p_flash: float) -> void:
	cloud_coverage = clampf(p_cloud, 0.0, 1.0)
	overcast = clampf(p_overcast, 0.0, 1.0)
	fog_extra = clampf(p_fog, 0.0, 1.0)
	flash = maxf(p_flash, 0.0)


## For previews/tests without the TimeOfDay autoload ticking.
func set_hour_override(h: float) -> void:
	_hour_override = h
	update_lighting()


func get_hour() -> float:
	if _hour_override >= 0.0:
		return _hour_override
	var tod: Node = get_node_or_null(^"/root/TimeOfDay")
	if tod != null:
		return float(tod.get(&"hour"))
	return 12.0


## Sun elevation (deg) for an hour — same curve as TimeOfDay.get_sun_elevation_deg().
static func sun_elevation_for_hour(h: float) -> float:
	var p := (h - 5.85) / (18.1 - 5.85)
	return sin(p * PI) * 75.0


## Unit vector pointing FROM the scene TOWARD the sun. East = +X, south = +Z.
func sun_direction_for_hour(h: float) -> Vector3:
	var p := (h - 5.85) / (18.1 - 5.85)
	var elev := deg_to_rad(sun_elevation_for_hour(h))
	var az := p * PI                      # 0 east → PI west
	var horiz := Vector3(cos(az), 0.0, south_tilt + 0.15 * sin(az)).normalized()
	return (horiz * cos(elev) + Vector3.UP * sin(elev)).normalized()


func update_lighting() -> void:
	var h := get_hour()
	var tod: Node = get_node_or_null(^"/root/TimeOfDay")
	var sun_dir := sun_direction_for_hour(h)
	var elev := sun_elevation_for_hour(h)
	var night := clampf(1.0 - (elev + 6.0) / 12.0, 0.0, 1.0)
	night_factor = night
	RenderingServer.global_shader_parameter_set(&"night_factor", night)

	# --- sun ---
	var cloud_dim := 1.0 - overcast * 0.78
	if sun != null:
		_orient(sun, sun_dir)
		var k := _sun_kelvin(elev)
		sun.light_color = kelvin_to_rgb(k)
		var e := smoothstep(-3.0, 12.0, elev)
		sun.light_energy = lerpf(0.0, 1.55, e) * cloud_dim + flash * 0.0
		sun.visible = elev > -4.0
		sun.shadow_enabled = elev > -1.0
		sun.light_angular_distance = lerpf(0.5, 3.0, overcast)  # soft shadows under cloud
	# --- moon ---
	var moon_phase := 0.5
	var moon_illum := 1.0
	if tod != null and tod.has_method(&"get_moon_phase"):
		moon_phase = float(tod.call(&"get_moon_phase"))
		moon_illum = float(tod.call(&"get_moon_illumination"))
	# moon trails the sun by phase × 24 h (full moon rises at sunset)
	var moon_h := fposmod(h - moon_phase * 24.0, 24.0)
	var moon_dir := sun_direction_for_hour(moon_h)
	moon_dir = Vector3(moon_dir.x, sun_elevation_for_hour(moon_h) / 75.0 * 0.9, moon_dir.z * 0.6 + 0.1).normalized()
	if moon != null:
		_orient(moon, moon_dir)
		var above := smoothstep(-0.02, 0.15, moon_dir.y)
		moon.light_energy = 0.11 * (0.25 + 0.75 * moon_illum) * above * night * (1.0 - overcast * 0.85)
		moon.light_color = Color(0.62, 0.72, 1.0)
		moon.visible = night > 0.05 and above > 0.0
		moon.shadow_enabled = moon.visible and (sun == null or not sun.shadow_enabled)
	# --- sky ---
	if sky_mat != null:
		sky_mat.set_shader_parameter(&"cloud_coverage", lerpf(cloud_coverage, 1.0, overcast * 0.7))
		sky_mat.set_shader_parameter(&"overcast", overcast)
		sky_mat.set_shader_parameter(&"storm_flash", flash)
		sky_mat.set_shader_parameter(&"star_strength", night * (1.0 - overcast))
		sky_mat.set_shader_parameter(&"moon_phase", moon_phase)
		sky_mat.set_shader_parameter(&"haze", lerpf(0.45, 0.9, maxf(overcast, fog_extra)))
		sky_mat.set_shader_parameter(&"sky_energy", lerpf(1.0, 0.55, overcast) * lerpf(1.0, 0.6, night))
	# --- environment ---
	if environment != null:
		var env := environment
		var golden := clampf(1.0 - absf(elev - 4.0) / 14.0, 0.0, 1.0) * (1.0 - night)
		env.ambient_light_energy = lerpf(1.0, 0.32, night) * lerpf(1.0, 0.85, overcast) + flash * 2.0
		env.tonemap_exposure = lerpf(day_exposure, night_exposure, night) * lerpf(1.0, 1.15, overcast)
		var fog_day := Color(0.78, 0.80, 0.80)
		var fog_gold := Color(0.95, 0.72, 0.52)
		var fog_night := Color(0.11, 0.12, 0.16)
		var fc := fog_day.lerp(fog_gold, golden * 0.8).lerp(fog_night, night)
		fc = fc.lerp(Color(0.55, 0.58, 0.6) * (1.0 - night * 0.8), overcast * 0.6)
		env.fog_light_color = fc
		env.fog_density = lerpf(0.0012, 0.0045, maxf(overcast * 0.6, fog_extra)) + fog_extra * 0.012
		env.fog_sun_scatter = lerpf(0.15, 0.4, golden) * (1.0 - overcast)
		env.volumetric_fog_density = base_fog_density * lerpf(1.0, 2.2, golden) * lerpf(1.0, 1.6, night) + fog_extra * 0.035 + overcast * 0.004
		env.volumetric_fog_albedo = Color(0.9, 0.9, 0.88).lerp(Color(0.95, 0.82, 0.7), golden * 0.5)
		env.volumetric_fog_emission = Color(0.0, 0.0, 0.0)
		env.adjustment_saturation = lerpf(1.03, 0.82, overcast) * lerpf(1.0, 0.85, night)
		env.glow_intensity = lerpf(0.35, 0.9, night)


static func _orient(light: DirectionalLight3D, toward: Vector3) -> void:
	var dir := -toward.normalized()                    # light travels along -Z of the node
	var up := Vector3.UP if absf(dir.y) < 0.98 else Vector3.FORWARD
	light.global_basis = Basis.looking_at(dir, up)


static func _sun_kelvin(elev: float) -> float:
	if elev <= 0.0:
		return 1900.0
	if elev < 6.0:
		return lerpf(1900.0, 3000.0, elev / 6.0)
	if elev < 20.0:
		return lerpf(3000.0, 4700.0, (elev - 6.0) / 14.0)
	if elev < 45.0:
		return lerpf(4700.0, KELVIN_SUN_NOON, (elev - 20.0) / 25.0)
	return KELVIN_SUN_NOON


## Tanner Helland's blackbody approximation (sRGB, normalised).
static func kelvin_to_rgb(kelvin: float) -> Color:
	var t := clampf(kelvin, 1000.0, 40000.0) / 100.0
	var r: float
	var g: float
	var b: float
	if t <= 66.0:
		r = 255.0
		g = 99.4708025861 * log(t) - 161.1195681661
		b = 0.0 if t <= 19.0 else 138.5177312231 * log(t - 10.0) - 305.0447927307
	else:
		r = 329.698727446 * pow(t - 60.0, -0.1332047592)
		g = 288.1221695283 * pow(t - 60.0, -0.0755148492)
		b = 255.0
	return Color(clampf(r, 0.0, 255.0) / 255.0, clampf(g, 0.0, 255.0) / 255.0, clampf(b, 0.0, 255.0) / 255.0)
