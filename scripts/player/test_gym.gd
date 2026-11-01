extends Node3D
## Player test gym (owner: player) — scenes/player/test_gym.tscn.
##
## A sunlit courtyard built at runtime from the architecture texture sets: a row of ledges
## 0.15–2.0 m, stairs, 20°/32° ramps, a beam / pipe / cable between platforms, a climbable brick
## wall with a drainpipe and a tree trunk (layer 6), AC units stepping up a facade to a roof, a
## raised pool (water Area3D on layer 7), a table with knockable cups and a chair, a low car-like
## gap to crawl under, and one interactable of each systems type. Sky + sun + SDFGI + SSAO, AgX.
##
## Screenshot hooks (tools/screenshot.sh … call=<method>): demo_tpp, demo_fpp, demo_aim,
## demo_sense, demo_wet, demo_beam, demo_close.

const PLAYER_SCENE := "res://scenes/player/cat_player.tscn"
const TEX := "res://assets/textures/architecture/"
const CSV := "res://data/i18n/requests/systems.csv"
const L_WORLD := 1
const L_PROPS := 1 << 3
const L_CLIMB := 1 << 5
const L_WATER := 1 << 6
const L_CAMERA_BLOCK := 1 << 8

@export var spawn_player := true
@export var spawn_transform := Transform3D(Basis.IDENTITY, Vector3(0.0, 0.0, -1.0))

var player: CharacterBody3D = null
var cups: Array[Node] = []
var _mats := {}
var _tile := {}


func _ready() -> void:
	_load_translation()
	_load_material_table()
	_build_environment()
	_build_ground()
	_build_ledges()
	_build_stairs_and_ramps()
	_build_beams()
	_build_climbables()
	_build_facade_with_ac()
	_build_pool()
	_build_table()
	_build_low_gap()
	_build_interactables()
	_build_dressing()
	var spawn := Marker3D.new()
	spawn.name = "PlayerSpawn"
	spawn.add_to_group(&"player_spawn")
	add_child(spawn)
	spawn.transform = spawn_transform
	if spawn_player:
		var ps := load(PLAYER_SCENE) as PackedScene
		player = ps.instantiate() as CharacterBody3D
		add_child(player)
		player.call(&"teleport", spawn.global_transform)


# =============================================================================================
# Screenshot / demo hooks
# =============================================================================================

func _place(pos: Vector3, yaw_deg: float, cam_yaw_deg: float, cam_pitch_deg: float, dist := -1.0) -> void:
	if player == null:
		return
	Input.action_release(&"jump")
	player.call(&"teleport", Transform3D(Basis(Vector3.UP, deg_to_rad(yaw_deg)), pos))
	var rig: Node3D = player.call(&"get_camera_rig")
	if rig != null:
		rig.call(&"set_mode", &"third_person", true)
		rig.set(&"yaw", deg_to_rad(cam_yaw_deg))
		rig.set(&"pitch", deg_to_rad(cam_pitch_deg))
		if dist > 0.0:
			rig.set(&"_distance", dist)
			rig.set(&"_distance_target", dist)
		rig.call(&"snap_to_target")


func demo_tpp() -> void:
	_place(Vector3(-0.6, 0.0, 0.6), 160.0, 200.0, -12.0, 1.25)


func demo_close() -> void:
	_place(Vector3(-0.6, 0.0, 0.6), 120.0, 250.0, -6.0, 0.75)


func demo_fpp() -> void:
	_place(Vector3(-1.2, 0.0, 0.9), 0.0, 180.0, -8.0)
	player.call(&"set_camera_mode", &"first_person")
	var rig: Node3D = player.call(&"get_camera_rig")
	rig.call(&"set_mode", &"first_person", true)


func demo_fpp_down() -> void:
	demo_fpp()
	var rig: Node3D = player.call(&"get_camera_rig")
	rig.set(&"pitch", deg_to_rad(-62.0))


func demo_aim() -> void:
	# crouched in front of the 0.8 m ledge, jump held → reticle + arc on the ledge top
	_place(Vector3(-0.85, 0.0, 1.25), 0.0, 215.0, -14.0, 1.35)
	Input.action_press(&"jump")


func demo_portrait() -> void:
	# sunny 3/4 portrait for fur / material review
	_place(Vector3(-1.6, 0.0, 0.2), 200.0, 130.0, -8.0, 0.62)


func demo_sense() -> void:
	demo_tpp()
	await get_tree().physics_frame
	var sense: Node = player.get_node_or_null(^"CatSense")
	if sense != null:
		sense.call(&"activate")


func demo_wet() -> void:
	demo_close()
	GameState.wetness = 1.0


func demo_beam() -> void:
	_place(Vector3(-0.8, 1.0, 6.5), 90.0, 300.0, -16.0, 1.3)


# =============================================================================================
# Building blocks
# =============================================================================================

func _load_material_table() -> void:
	var p := TEX + "materials.json"
	if not FileAccess.file_exists(p):
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
	if d is Dictionary:
		for k: String in d:
			_tile[k] = float((d[k] as Dictionary).get("tile_m", 1.0))


func _mat(set_name: String, tint := Color(1, 1, 1)) -> Material:
	var key := "%s_%s" % [set_name, tint.to_html()]
	if _mats.has(key):
		return _mats[key]
	var m := ORMMaterial3D.new()
	var a := TEX + set_name + "_albedo.jpg"
	if ResourceLoader.exists(a):
		m.albedo_texture = load(a)
		var n := TEX + set_name + "_normal.png"
		if ResourceLoader.exists(n):
			m.normal_enabled = true
			m.normal_texture = load(n)
		var o := TEX + set_name + "_orm.jpg"
		if ResourceLoader.exists(o):
			m.orm_texture = load(o)
	else:
		m.roughness = 0.8
	m.albedo_color = tint
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_triplanar_sharpness = 4.0
	var t: float = _tile.get(set_name, 1.0)
	m.uv1_scale = Vector3.ONE / t
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_mats[key] = m
	return m


func _box(nm: String, center: Vector3, size: Vector3, mat: Material, layers := L_WORLD | L_CAMERA_BLOCK, surface := &"concrete", parent: Node = null) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = nm
	body.collision_layer = layers
	body.collision_mask = 0
	body.set_meta(&"surface", surface)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	body.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	body.add_child(mi)
	(parent if parent != null else self).add_child(body)
	body.position = center
	return body


func _cyl(nm: String, center: Vector3, radius: float, height: float, mat: Material, axis := Vector3.UP, layers := L_WORLD | L_CAMERA_BLOCK, surface := &"metal") -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = nm
	body.collision_layer = layers
	body.collision_mask = 0
	body.set_meta(&"surface", surface)
	var cs := CollisionShape3D.new()
	var sh := CylinderShape3D.new()
	sh.radius = radius
	sh.height = height
	cs.shape = sh
	body.add_child(cs)
	var mi := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = radius
	cm.bottom_radius = radius
	cm.height = height
	cm.radial_segments = 24 if radius > 0.05 else 12
	mi.mesh = cm
	mi.material_override = mat
	body.add_child(mi)
	add_child(body)
	body.position = center
	if not axis.is_equal_approx(Vector3.UP):
		body.basis = _basis_y_to(axis)
	return body


static func _basis_y_to(a: Vector3) -> Basis:
	var y := a.normalized()
	var ref := Vector3.FORWARD if absf(y.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT
	var x := ref.cross(y).normalized()
	var z := x.cross(y).normalized()
	return Basis(x, y, z)


## Translated label text with an English fallback while the key is not merged yet.
func _t(key: String, fallback: String) -> String:
	var s := tr(key)
	return fallback if s == key else s


func _label(text: String, pos: Vector3, yaw_deg := 180.0) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = 48
	l.pixel_size = 0.0016
	l.outline_size = 10
	l.modulate = Color(1, 0.97, 0.9)
	l.position = pos
	l.rotation_degrees = Vector3(0, yaw_deg, 0)
	add_child(l)


# =============================================================================================
# Environment
# =============================================================================================

func _build_environment() -> void:
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var psm := PhysicalSkyMaterial.new()
	psm.turbidity = 7.0
	psm.mie_coefficient = 0.006
	psm.mie_eccentricity = 0.82
	psm.rayleigh_coefficient = 2.2
	psm.ground_color = Color(0.32, 0.3, 0.28)
	psm.energy_multiplier = 1.0
	sky.sky_material = psm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.ssao_enabled = true
	env.ssao_radius = 0.6
	env.ssao_intensity = 1.6
	env.ssao_detail = 0.6
	env.sdfgi_enabled = true
	env.sdfgi_use_occlusion = true
	env.sdfgi_min_cell_size = 0.08
	env.sdfgi_cascades = 4
	env.sdfgi_energy = 1.0
	env.glow_enabled = true
	env.glow_intensity = 0.25
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.4
	env.fog_enabled = true
	env.fog_light_color = Color(0.78, 0.8, 0.86)
	env.fog_density = 0.0025
	env.fog_aerial_perspective = 0.6
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.04
	env.adjustment_contrast = 1.03
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-38.0, -32.0, 0.0)
	sun.light_color = Color(1.0, 0.93, 0.82)
	sun.light_energy = 2.4
	sun.light_angular_distance = 0.6
	sun.shadow_enabled = true
	sun.shadow_bias = 0.02
	sun.shadow_normal_bias = 0.6
	sun.shadow_blur = 1.2
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 40.0
	sun.directional_shadow_split_1 = 0.05
	sun.directional_shadow_split_2 = 0.16
	sun.directional_shadow_split_3 = 0.45
	sun.directional_shadow_blend_splits = true
	add_child(sun)


func _build_ground() -> void:
	_box("Ground", Vector3(0, -0.25, 2.0), Vector3(30, 0.5, 26), _mat("concrete_weathered"), L_WORLD | L_CAMERA_BLOCK, &"concrete")
	# terrazzo courtyard patch (slightly raised 1 cm: a tiny step the controller must ignore)
	_box("Terrazzo", Vector3(-2.0, 0.005, -2.0), Vector3(7.0, 0.01, 4.0), _mat("terrazzo"), L_WORLD, &"tile")
	# enclosing walls
	var wall := _mat("plaster_ochre")
	_box("WallNorth", Vector3(0, 2.0, 14.0), Vector3(30, 4.0, 0.3), wall)
	_box("WallWest", Vector3(-14.5, 2.0, 2.0), Vector3(0.3, 4.0, 26), _mat("plaster_green"))
	_box("WallSouth", Vector3(0, 1.0, -10.5), Vector3(30, 2.0, 0.3), _mat("cement_render"))


func _build_ledges() -> void:
	var heights: Array[float] = [0.15, 0.3, 0.5, 0.8, 1.0, 1.3, 1.6, 2.0]
	var mats := ["cement_render", "plaster_ochre", "brick_exposed", "plaster_yellow"]
	var x := -5.2
	for i in heights.size():
		var h := heights[i]
		var b := _box("Ledge_%d" % int(h * 100), Vector3(x, h * 0.5, 2.4), Vector3(0.9, h, 1.0), _mat(mats[i % mats.size()]), L_WORLD | L_CAMERA_BLOCK, &"concrete")
		b.set_meta(&"ledge_height", h)
		# cement coping slab: slight overhang + darker edge reads as built masonry, not a box
		var cap := MeshInstance3D.new()
		var cm := BoxMesh.new()
		cm.size = Vector3(0.96, 0.035, 1.06)
		cap.mesh = cm
		cap.material_override = _mat("cement_render", Color(0.82, 0.8, 0.76))
		cap.position = Vector3(0, h * 0.5 - 0.0175 + 0.001, 0)
		b.add_child(cap)
		_label("%.2f m" % h, Vector3(x, h + 0.12, 1.88))
		x += 1.45


func _build_stairs_and_ramps() -> void:
	var stone := _mat("granite_red")
	for i in 8:
		var top := 0.16 * float(i + 1)
		_box("Step_%d" % i, Vector3(7.6, top * 0.5, 0.0 + 0.3 * float(i)), Vector3(1.1, top, 0.3), stone, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_box("StairLanding", Vector3(7.6, 0.64, 3.0), Vector3(1.1, 1.28, 1.2), stone, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_label(_t("GYM_STAIRS", "stairs 0.16 m"), Vector3(7.6, 0.3, -0.4))
	# ramps
	for spec: Array in [[20.0, -9.2], [32.0, -11.0]]:
		var ang: float = deg_to_rad(spec[0])
		var length := 2.6
		var rise := sin(ang) * length
		var r := _box("Ramp_%d" % int(spec[0]), Vector3.ZERO, Vector3(1.0, 0.1, length), _mat("wood_brown"), L_WORLD | L_CAMERA_BLOCK, &"wood")
		r.basis = Basis(Vector3.RIGHT, -ang)
		r.position = Vector3(spec[1], rise * 0.5 - 0.02, 1.0 + cos(ang) * length * 0.5)
		_box("RampTop_%d" % int(spec[0]), Vector3(spec[1], rise * 0.5, 1.0 + cos(ang) * length + 0.6), Vector3(1.0, rise, 1.2), _mat("cement_render"))
		_label("%d°" % int(spec[0]), Vector3(spec[1], 0.25, 0.7))


func _build_beams() -> void:
	var plinth := _mat("cement_render")
	_box("PlatformA", Vector3(-3.0, 0.5, 6.5), Vector3(1.0, 1.0, 1.0), plinth)
	_box("PlatformB", Vector3(1.4, 0.5, 6.5), Vector3(1.0, 1.0, 1.0), plinth)
	_box("PlatformC", Vector3(5.2, 0.5, 6.5), Vector3(1.0, 1.0, 1.0), plinth)
	# 9 cm wooden beam A→B (top at 1.0 m)
	_box("Beam", Vector3(-0.8, 0.955, 6.5), Vector3(3.4, 0.09, 0.09), _mat("wood_brown"), L_WORLD, &"wood")
	# 5 cm pipe B→C and a 2.4 cm cable slightly offset (balance-walkable)
	_cyl("Pipe", Vector3(3.3, 0.975, 6.38), 0.025, 2.8, _mat("metal_painted"), Vector3.RIGHT, L_WORLD, &"metal")
	_cyl("Cable", Vector3(3.3, 0.988, 6.68), 0.012, 2.8, _mat("iron_wrought", Color(0.25, 0.25, 0.25)), Vector3.RIGHT, L_WORLD, &"metal")
	_label(_t("GYM_BEAM", "beam 9 cm"), Vector3(-0.8, 1.15, 6.1))
	_label(_t("GYM_PIPE_CABLE", "pipe / cable"), Vector3(3.3, 1.15, 6.1))


func _build_climbables() -> void:
	# rough brick wall (climbable) with a walkable top and a drainpipe
	_box("ClimbWall", Vector3(-1.0, 1.2, 10.4), Vector3(3.0, 2.4, 0.35), _mat("brick_exposed"), L_WORLD | L_CLIMB | L_CAMERA_BLOCK, &"concrete")
	_cyl("Drainpipe", Vector3(1.1, 1.4, 10.18), 0.045, 2.8, _mat("metal_painted", Color(0.75, 0.78, 0.8)), Vector3.UP, L_WORLD | L_CLIMB, &"metal")
	_label(_t("GYM_CLIMB", "climb (brick, drainpipe)"), Vector3(-1.0, 0.25, 10.1))
	# tree trunk
	var bark := _mat("wood_brown", Color(0.55, 0.47, 0.4))
	_cyl("TreeTrunk", Vector3(-6.0, 1.75, 8.0), 0.16, 3.5, bark, Vector3.UP, L_WORLD | L_CLIMB | L_CAMERA_BLOCK, &"wood")
	_box("TreeFork", Vector3(-6.0, 3.52, 8.0), Vector3(0.7, 0.06, 0.5), bark, L_WORLD, &"wood")


func _build_facade_with_ac() -> void:
	# a building block: facade facing -X, roof at 3.6 m
	_box("Building", Vector3(12.0, 1.8, 7.0), Vector3(3.0, 3.6, 6.0), _mat("plaster_yellow"))
	_box("Roof", Vector3(12.0, 3.62, 7.0), Vector3(3.2, 0.04, 6.2), _mat("roof_tile_terracotta"), L_WORLD | L_CAMERA_BLOCK, &"roof_tile")
	var metal := _mat("metal_painted", Color(0.92, 0.92, 0.9))
	var specs := [[Vector3(10.32, 1.175, 5.0), 1.45], [Vector3(10.32, 1.975, 6.4), 2.25], [Vector3(10.32, 2.875, 7.8), 3.15]]
	for i in specs.size():
		var c: Vector3 = specs[i][0]
		var ac := _box("AC_%d" % i, c, Vector3(0.36, 0.55, 0.8), metal, L_WORLD | L_CAMERA_BLOCK, &"metal")
		# grille + fan disc for a bit of realism
		var grille := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.19
		cm.bottom_radius = 0.19
		cm.height = 0.01
		grille.mesh = cm
		grille.material_override = _mat("iron_wrought", Color(0.3, 0.3, 0.3))
		grille.rotation_degrees = Vector3(0, 0, 90)
		grille.position = Vector3(-0.181, 0.0, 0.12)
		ac.add_child(grille)
		# support brackets
		_box("ACBracket_%d" % i, c + Vector3(0.0, -0.3, 0.0), Vector3(0.36, 0.04, 0.7), _mat("iron_wrought", Color(0.35, 0.3, 0.28)), L_WORLD, &"metal")
	_label(_t("GYM_AC_ROOF", "AC units → roof 3.6 m"), Vector3(10.2, 0.3, 4.2), -90.0)


func _build_pool() -> void:
	var c := Vector3(-8.0, 0.0, -4.0)
	var size := Vector2(3.0, 2.2)
	var rim_h := 0.35
	var t := 0.15
	var tile := _mat("tile_mosaic_blue")
	_box("PoolWallN", c + Vector3(0, rim_h * 0.5, size.y * 0.5 - t * 0.5), Vector3(size.x, rim_h, t), tile, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_box("PoolWallS", c + Vector3(0, rim_h * 0.5, -size.y * 0.5 + t * 0.5), Vector3(size.x, rim_h, t), tile, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_box("PoolWallE", c + Vector3(size.x * 0.5 - t * 0.5, rim_h * 0.5, 0), Vector3(t, rim_h, size.y - 2.0 * t), tile, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_box("PoolWallW", c + Vector3(-size.x * 0.5 + t * 0.5, rim_h * 0.5, 0), Vector3(t, rim_h, size.y - 2.0 * t), tile, L_WORLD | L_CAMERA_BLOCK, &"tile")
	_box("PoolFloor", c + Vector3(0, 0.01, 0), Vector3(size.x - 2.0 * t, 0.02, size.y - 2.0 * t), tile, L_WORLD, &"tile")
	var level := 0.25
	var area := Area3D.new()
	area.name = "PoolWater"
	area.collision_layer = L_WATER
	area.collision_mask = 0
	area.monitorable = true
	area.monitoring = false
	area.add_to_group(&"water")
	area.set_meta(&"water_level", level)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(size.x - 2.0 * t, level, size.y - 2.0 * t)
	cs.shape = bs
	cs.position = Vector3(0, level * 0.5, 0)
	area.add_child(cs)
	add_child(area)
	area.position = c
	var water := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(size.x - 2.0 * t, size.y - 2.0 * t)
	water.mesh = pm
	var wm := StandardMaterial3D.new()
	wm.albedo_color = Color(0.12, 0.3, 0.33, 0.55)
	wm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	wm.roughness = 0.04
	wm.metallic_specular = 0.6
	var nt := NoiseTexture2D.new()
	nt.seamless = true
	nt.as_normal_map = true
	nt.bump_strength = 2.0
	var fn := FastNoiseLite.new()
	fn.frequency = 0.04
	nt.noise = fn
	wm.normal_enabled = true
	wm.normal_texture = nt
	wm.normal_scale = 0.35
	wm.uv1_scale = Vector3(3, 3, 3)
	wm.refraction_enabled = true
	wm.refraction_scale = 0.03
	water.material_override = wm
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	water.position = c + Vector3(0, level, 0)
	add_child(water)
	_label(_t("GYM_POOL", "pool"), c + Vector3(0, 0.55, -size.y * 0.5 - 0.05))


func _build_table() -> void:
	var c := Vector3(3.2, 0.0, -2.2)
	var wood := _mat("wood_brown")
	_box("TableTop", c + Vector3(0, 0.71, 0), Vector3(1.2, 0.04, 0.7), wood, L_WORLD | L_CAMERA_BLOCK, &"wood")
	for sx: float in [-0.55, 0.55]:
		for sz: float in [-0.3, 0.3]:
			_box("TableLeg", c + Vector3(sx, 0.345, sz), Vector3(0.05, 0.69, 0.05), wood, L_WORLD, &"wood")
	# plastic stool as a step (0.45 m)
	var stool_mat := StandardMaterial3D.new()
	stool_mat.albedo_color = Color(0.12, 0.32, 0.62)
	stool_mat.roughness = 0.45
	_box("Stool", c + Vector3(-1.0, 0.225, -0.1), Vector3(0.32, 0.45, 0.32), stool_mat, L_WORLD | L_CAMERA_BLOCK, &"plastic")
	var glaze := StandardMaterial3D.new()
	glaze.albedo_color = Color(0.9, 0.88, 0.82)
	glaze.roughness = 0.12
	var glaze_blue := StandardMaterial3D.new()
	glaze_blue.albedo_color = Color(0.2, 0.36, 0.6)
	glaze_blue.roughness = 0.15
	var spots := [Vector3(-0.35, 0.73, -0.24), Vector3(0.05, 0.73, -0.27), Vector3(0.45, 0.73, -0.22)]
	for i in spots.size():
		var cup := Pushable.new()
		cup.name = "Cup_%d" % i
		cup.object_id = StringName("gym_cup_%d" % i)
		cup.material_kind = &"ceramic"
		cup.set_meta(&"mass", 0.22)
		var cs := CollisionShape3D.new()
		var sh := CylinderShape3D.new()
		sh.radius = 0.04
		sh.height = 0.09
		cs.shape = sh
		cs.position.y = 0.045
		cup.add_child(cs)
		var mi := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.042
		cm.bottom_radius = 0.033
		cm.height = 0.09
		mi.mesh = cm
		mi.position.y = 0.045
		mi.material_override = glaze if i != 1 else glaze_blue
		cup.add_child(mi)
		add_child(cup)
		cup.position = c + spots[i]
		cups.append(cup)


func _build_low_gap() -> void:
	# a "parked car" slab: 0.17 m clearance → crawl/squeeze under
	var c := Vector3(6.5, 0.0, -4.0)
	var paint := StandardMaterial3D.new()
	paint.albedo_color = Color(0.55, 0.05, 0.05)
	paint.metallic = 0.6
	paint.roughness = 0.3
	_box("CarBody", c + Vector3(0, 0.6, 0), Vector3(1.7, 0.86, 3.6), paint, L_WORLD | L_CAMERA_BLOCK, &"metal")
	var tyre := StandardMaterial3D.new()
	tyre.albedo_color = Color(0.05, 0.05, 0.05)
	tyre.roughness = 0.9
	for sx: float in [-0.78, 0.78]:
		for sz: float in [-1.2, 1.2]:
			_cyl("Wheel", c + Vector3(sx, 0.3, sz), 0.3, 0.18, tyre, Vector3.RIGHT, L_WORLD, &"plastic")
	_label(_t("GYM_CRAWL", "crawl under (0.17 m)"), Vector3(c.x, 0.1, c.z - 1.9))


func _build_interactables() -> void:
	# food bowl
	var bowl := FoodSource.new()
	bowl.name = "FoodBowl"
	bowl.source_id = &"gym_bowl"
	bowl.food_amount = 25.0
	bowl.servings = -1
	var bm := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.075
	cm.bottom_radius = 0.06
	cm.height = 0.045
	bm.mesh = cm
	bm.position.y = 0.0225
	bm.material_override = _mat("stainless")
	bowl.add_child(bm)
	add_child(bowl)
	bowl.position = Vector3(1.6, 0.0, -2.6)
	# a fish to carry in the mouth
	var fish := PickupItem.new()
	fish.name = "Fish"
	fish.item_id = &"fish"
	add_child(fish)
	fish.position = Vector3(0.6, 0.0, -1.9)
	# nap cushion
	var nap := NapSpot.new()
	nap.name = "Cushion"
	nap.spot_id = &"gym_cushion"
	var cush := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.24
	cyl.bottom_radius = 0.26
	cyl.height = 0.07
	cush.mesh = cyl
	cush.position.y = 0.035
	cush.material_override = _mat("fabric_canvas", Color(0.85, 0.55, 0.45))
	nap.add_child(cush)
	add_child(nap)
	nap.position = Vector3(-2.6, 0.0, -2.8)
	# scratch post
	var post := ScratchPost.new()
	post.name = "ScratchPost"
	post.post_id = &"gym_post"
	add_child(post)
	post.position = Vector3(-4.3, 0.0, -1.6)
	_cyl("ScratchPostMesh", Vector3(-4.3, 0.35, -1.75), 0.06, 0.7, _mat("rattan"), Vector3.UP, L_WORLD, &"fabric")
	# territory spot at the wall corner
	var terr := TerritorySpot.new()
	terr.name = "Territory"
	terr.spot_id = &"gym_corner"
	add_child(terr)
	terr.position = Vector3(-13.9, 0.0, -9.8)
	# bottle cap collectible
	var cap := Collectible.new()
	cap.name = "Cap"
	cap.collectible_id = &"gym_cap"
	cap.kind = &"caps"
	cap.item_id = &"cap"
	add_child(cap)
	cap.position = Vector3(-1.6, 0.0, -1.0)
	# quest target for the cat-sense scent trail demo
	var qt := Marker3D.new()
	qt.name = "QuestTargetDemo"
	qt.add_to_group(&"quest_target")
	qt.set_meta(&"target_id", "gym_demo")
	add_child(qt)
	qt.position = Vector3(12.0, 3.64, 7.0)


func _build_dressing() -> void:
	# a few potted plants and a crate so screenshots read at cat scale
	var pot := _mat("granite_red", Color(0.75, 0.42, 0.3))
	for p: Vector3 in [Vector3(-12.5, 0, 12.5), Vector3(4.5, 0, 12.6), Vector3(-6.8, 0, -9.6)]:
		_cyl("Pot", p + Vector3(0, 0.22, 0), 0.22, 0.44, pot, Vector3.UP, L_WORLD | L_CAMERA_BLOCK, &"tile")
		var leaves := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.38
		sm.height = 0.6
		leaves.mesh = sm
		var lm := StandardMaterial3D.new()
		lm.albedo_color = Color(0.16, 0.3, 0.12)
		lm.roughness = 0.75
		leaves.material_override = lm
		leaves.position = p + Vector3(0, 0.72, 0)
		add_child(leaves)
	_box("Crate", Vector3(-12.0, 0.25, -6.0), Vector3(0.6, 0.5, 0.45), _mat("wood_green"), L_WORLD | L_CAMERA_BLOCK, &"wood")


func _load_translation() -> void:
	if not FileAccess.file_exists(CSV):
		return
	var f := FileAccess.open(CSV, FileAccess.READ)
	var header := f.get_csv_line()
	var trs: Array[Translation] = []
	for i in range(1, header.size()):
		var t := Translation.new()
		t.locale = header[i]
		trs.append(t)
	while not f.eof_reached():
		var row := f.get_csv_line()
		if row.size() < header.size() or row[0] == "":
			continue
		for i in trs.size():
			trs[i].add_message(row[0], row[i + 1])
	for t in trs:
		TranslationServer.add_translation(t)
