extends SceneTree
## Builds scenes/npc/test_life.tscn (owner: world-life): a compact old-quarter street block with
## every marker convention LifeDirector consumes, real city-houses modules / street props when
## present, a baked NavigationMesh, and an instance of scenes/npc/life_director.tscn.
## Run: tools/godot_lock.sh godot --headless --path . --script res://scripts/npc/build_test_life.gd </dev/null

const OUT := "res://scenes/npc/test_life.tscn"
const CITY := "res://assets/models/city/"
const PROPS := "res://assets/models/props/"
const LANDMARKS := "res://assets/models/landmarks/"
const GROUND_TEX := "res://assets/textures/ground/"
const ARCH_TEX := "res://assets/textures/architecture/"

var wroot: Node3D
var nav_root: Node3D
var _mats: Dictionary = {}
var lao_qua_pos := Vector3(25.4, 3.8, 17.0)
const NATURE := "res://assets/models/nature/"


func _init() -> void:
	_build.call_deferred()


func _own(n: Node) -> void:
	if n != wroot:
		n.owner = wroot
	if n.scene_file_path != "" and n != wroot:
		return
	for c: Node in n.get_children():
		_own(c)


func _add(parent: Node, n: Node) -> Node:
	parent.add_child(n)
	return n


func _build() -> void:
	await process_frame
	wroot = Node3D.new()
	wroot.name = "TestLife"
	wroot.set_script(load("res://scripts/npc/test_life_world.gd"))
	get_root().add_child(wroot)
	_environment()
	nav_root = Node3D.new()
	nav_root.name = "Geometry"
	nav_root.add_to_group(&"nav_source", true)
	wroot.add_child(nav_root)
	_ground()
	_buildings()
	_stalls_and_props()
	_lake_park()
	_markers()
	_lanes()
	_nav()
	var dir := (load("res://scenes/npc/life_director.tscn") as PackedScene).instantiate()
	dir.name = "LifeDirector"
	wroot.add_child(dir)
	_own(wroot)
	for c: Node in wroot.get_children():
		_own(c)
	var ps := PackedScene.new()
	var err := ps.pack(wroot)
	if err != OK:
		printerr("pack failed ", err)
		quit(1)
		return
	err = ResourceSaver.save(ps, OUT)
	print("BUILD test_life saved: ", err == OK, " -> ", OUT)
	quit(0 if err == OK else 1)


# --------------------------------------------------------------------------------------------
# Materials
# --------------------------------------------------------------------------------------------

func _tex_mat(dir: String, tex_name: String, metres_per_tile: float, fallback: Color, tint := Color.WHITE) -> StandardMaterial3D:
	var key := dir + tex_name + str(metres_per_tile) + tint.to_html()
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	var alb := dir + tex_name + "_albedo.jpg"
	if ResourceLoader.exists(alb):
		m.albedo_texture = load(alb)
		m.albedo_color = tint
		var nrm := dir + tex_name + "_normal.png"
		if ResourceLoader.exists(nrm):
			m.normal_enabled = true
			m.normal_texture = load(nrm)
		var orm := dir + tex_name + "_orm.jpg"
		if ResourceLoader.exists(orm):
			m.ao_enabled = true
			m.ao_texture = load(orm)
			m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
			m.roughness_texture = load(orm)
			m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
			m.roughness = 1.0
		else:
			m.roughness = 0.85
	else:
		m.albedo_color = fallback
		m.roughness = 0.85
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE / metres_per_tile
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	_mats[key] = m
	return m


func _col(c: Color, rough := 0.8, metal := 0.0) -> StandardMaterial3D:
	var key := c.to_html() + str(rough) + str(metal)
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	_mats[key] = m
	return m


# --------------------------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------------------------

func _box(parent: Node3D, n: String, center: Vector3, size: Vector3, mat: Material, collide := true, surface := "concrete",
		layer := 1) -> Node3D:
	var mi := MeshInstance3D.new()
	mi.name = n
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	if not collide:
		mi.position = center
		parent.add_child(mi)
		return mi
	var sb := StaticBody3D.new()
	sb.name = n + "Body"
	sb.position = center
	sb.collision_layer = layer
	sb.collision_mask = 0
	sb.set_meta(&"surface", surface)
	parent.add_child(sb)
	sb.add_child(mi)
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	return sb


func _mesh(parent: Node3D, n: String, mesh: Mesh, mat: Material, pos: Vector3, rot_deg := Vector3.ZERO) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = n
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.rotation_degrees = rot_deg
	parent.add_child(mi)
	return mi


func _cyl(r_top: float, r_bot: float, h: float, segs := 16) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r_top
	c.bottom_radius = r_bot
	c.height = h
	c.radial_segments = segs
	return c


func _glb(parent: Node3D, path: String, pos: Vector3, yaw_deg := 0.0, n := "") -> Node3D:
	if not ResourceLoader.exists(path):
		return null
	var inst := (load(path) as PackedScene).instantiate() as Node3D
	if n != "":
		inst.name = n
	inst.position = pos
	inst.rotation_degrees = Vector3(0, yaw_deg, 0)
	parent.add_child(inst)
	return inst


func _marker(n: String, group: String, pos: Vector3, yaw_deg: float, meta: Dictionary) -> Marker3D:
	var m := Marker3D.new()
	m.name = n
	m.position = pos
	m.rotation_degrees = Vector3(0, yaw_deg, 0)
	m.add_to_group(StringName(group), true)
	for k: String in meta:
		m.set_meta(StringName(k), meta[k])
	(wroot.get_node("Markers") as Node3D).add_child(m)
	return m


# --------------------------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------------------------

func _environment() -> void:
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var psm := ProceduralSkyMaterial.new()
	psm.sky_top_color = Color(0.28, 0.45, 0.72)
	psm.sky_horizon_color = Color(0.72, 0.76, 0.8)
	psm.ground_horizon_color = Color(0.55, 0.55, 0.55)
	psm.ground_bottom_color = Color(0.2, 0.19, 0.18)
	psm.sun_angle_max = 20.0
	sky.sky_material = psm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.6
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 1.6
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.fog_enabled = true
	env.fog_light_color = Color(0.72, 0.75, 0.8)
	env.fog_density = 0.004
	env.fog_aerial_perspective = 0.4
	we.environment = env
	wroot.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.add_to_group(&"sun", true)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 70.0
	sun.light_angular_distance = 0.6
	sun.rotation_degrees = Vector3(-50, 150, 0)
	sun.light_energy = 1.6
	wroot.add_child(sun)
	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.light_color = Color(0.62, 0.7, 0.95)
	moon.light_energy = 0.15
	moon.rotation_degrees = Vector3(-60, -30, 0)
	moon.shadow_enabled = true
	moon.visible = false
	wroot.add_child(moon)
	var cam := Camera3D.new()
	cam.name = "OverviewCam"
	cam.position = Vector3(-4, 10, 24)
	cam.fov = 60.0
	wroot.add_child(cam)
	cam.look_at_from_position(cam.position, Vector3(2, 0, 2), Vector3.UP)
	var mk := Node3D.new()
	mk.name = "Markers"
	wroot.add_child(mk)


func _ground() -> void:
	var g := Node3D.new()
	g.name = "Ground"
	nav_root.add_child(g)
	var asphalt := _tex_mat(GROUND_TEX, "asphalt", 4.0, Color(0.2, 0.2, 0.21))
	var pavers := _tex_mat(GROUND_TEX, "pavers", 1.6, Color(0.55, 0.5, 0.45))
	var curb := _tex_mat(GROUND_TEX, "granite_curb", 1.0, Color(0.5, 0.5, 0.5))
	# road (top at y = 0), 70 m long, 8 m wide
	_box(g, "GroundRoad", Vector3(0, -0.25, 0), Vector3(70, 0.5, 8), asphalt, true, "asphalt")
	# sidewalks (top at 0.15) with granite curbs
	_box(g, "GroundSidewalkN", Vector3(0, -0.175, -5.5), Vector3(70, 0.65, 3.0), pavers, true, "tile")
	_box(g, "GroundSidewalkS", Vector3(-17.5, -0.175, 5.5), Vector3(35, 0.65, 3.0), pavers, true, "tile")
	_box(g, "GroundCurbN", Vector3(0, 0.0, -4.07), Vector3(70, 0.3, 0.16), curb, true, "concrete")
	_box(g, "GroundCurbS", Vector3(-17.5, 0.0, 4.07), Vector3(35, 0.3, 0.16), curb, true, "concrete")
	# plaza in front of the park (pavers) east of x = 0
	_box(g, "GroundPlaza", Vector3(17.5, -0.175, 6.5), Vector3(35, 0.65, 5.0), pavers, true, "tile")
	_box(g, "GroundCurbPlaza", Vector3(17.5, 0.0, 4.07), Vector3(35, 0.3, 0.16), curb, true, "concrete")
	# back ground under the buildings
	var conc := _tex_mat(GROUND_TEX, "concrete_alley", 2.0, Color(0.45, 0.44, 0.42))
	_box(g, "GroundBackN", Vector3(0, -0.175, -18), Vector3(70, 0.65, 22), conc, true, "concrete")
	_box(g, "GroundBackS", Vector3(-17.5, -0.175, 18), Vector3(35, 0.65, 22), conc, true, "concrete")


func _buildings() -> void:
	var b := Node3D.new()
	b.name = "Buildings"
	nav_root.add_child(b)
	var north := ["tube90s_4f_w4_blue", "colonial_2f_w4_ochre", "oldtile_1f_w5_shop_yellow", "tube90s_5f_w3_5_white",
		"colonial_3f_w5_pink", "modern_5f_w4_white", "tube90s_3f_w4_5_green", "colonial_2f_w6_yellow", "tube90s_6f_w5_blue",
		"oldtile_1f_w4_blue", "colonial_3f_w4_5_green", "tube90s_4f_w5_pink", "modern_4f_w6_dark", "colonial_2f_w4_blue",
		"tube90s_5f_w3_5_yellow"]
	var south := ["colonial_3f_w5_ochre", "tube90s_4f_w4_green", "oldtile_1f_w4_yellow", "tube90s_6f_w5_white",
		"colonial_2f_w6_blue", "tube90s_3f_w4_5_pink", "modern_5f_w4_grey", "oldtile_1f_w5_shop_white"]
	var widths := {}
	if FileAccess.file_exists(CITY + "catalog.json"):
		var cat: Variant = JSON.parse_string(FileAccess.get_file_as_string(CITY + "catalog.json"))
		var arr: Array = cat if cat is Array else (cat as Dictionary).get("modules", [])
		for e: Dictionary in arr:
			widths[str(e["id"])] = float(e["width"])
	var x := -34.0
	for id: String in north:
		var w := float(widths.get(id, 4.5))
		if x + w > 34.0:
			break
		var node := _glb(b, CITY + id + ".glb", Vector3(x + w * 0.5, 0.15, -7.0), 0.0, "N_" + id)
		if node == null:
			_box(b, "N_" + id, Vector3(x + w * 0.5, 5.0, -13.0), Vector3(w - 0.05, 10.0, 12.0), _tex_mat(ARCH_TEX, "plaster_yellow", 3.0, Color(0.8, 0.7, 0.45)))
		x += w
	x = -34.0
	for id: String in south:
		var w := float(widths.get(id, 4.5))
		if x + w > -0.5:
			break
		var node := _glb(b, CITY + id + ".glb", Vector3(x + w * 0.5, 0.15, 7.0), 180.0, "S_" + id)
		if node == null:
			_box(b, "S_" + id, Vector3(x + w * 0.5, 5.0, 13.0), Vector3(w - 0.05, 10.0, 12.0), _tex_mat(ARCH_TEX, "plaster_ochre", 3.0, Color(0.8, 0.6, 0.4)))
		x += w


func _stool(parent: Node3D, pos: Vector3, c: Color) -> void:
	var colour := "red" if c.r > c.g and c.r > c.b else ("blue" if c.b > c.g else "green")
	if _glb(parent, PROPS + "stool_plastic_%s.glb" % colour, pos, randf_range(-20.0, 20.0), "Stool") != null:
		return
	var plastic := _col(c, 0.45)
	_mesh(parent, "StoolSeat", _cyl(0.15, 0.13, 0.03, 16), plastic, pos + Vector3(0, 0.27, 0))
	_mesh(parent, "StoolBody", _cyl(0.13, 0.16, 0.26, 12), plastic, pos + Vector3(0, 0.13, 0))


func _stalls_and_props() -> void:
	var p := Node3D.new()
	p.name = "StreetLife"
	nav_root.add_child(p)
	var canvas := _tex_mat(ARCH_TEX, "fabric_canvas", 2.0, Color(0.2, 0.4, 0.55))
	var wood := _tex_mat(ARCH_TEX, "wood_brown", 1.0, Color(0.45, 0.3, 0.2))
	var steel := _col(Color(0.55, 0.56, 0.58), 0.35, 0.8)
	# --- Bà Tư's tea stall (south sidewalk, x≈-10): low table, stools, umbrella-awning
	var tea := Node3D.new()
	tea.name = "TeaStall"
	tea.position = Vector3(-10, 0.15, 5.6)
	p.add_child(tea)
	_box(tea, "TeaTable", Vector3(0, 0.22, 0), Vector3(0.9, 0.06, 0.55), wood, true, "wood")
	for lx: float in [-0.4, 0.4]:
		for lz: float in [-0.22, 0.22]:
			_mesh(tea, "Leg", _cyl(0.02, 0.02, 0.2, 6), wood, Vector3(lx, 0.1, lz))
	if _glb(tea, PROPS + "tea_set.glb", Vector3(0.1, 0.25, 0.0), 15.0, "TeaSet") == null:
		_mesh(tea, "Teapot", _cyl(0.05, 0.07, 0.12, 12), _col(Color(0.85, 0.85, 0.8), 0.2), Vector3(0.15, 0.31, 0.05))
	for i in 3:
		_glb(tea, PROPS + "glass_tra_da.glb", Vector3(-0.32 + i * 0.12, 0.25, -0.16), 0.0, "TraDa%d" % i)
	_glb(tea, PROPS + "styrofoam_box.glb", Vector3(0.75, 0.0, 0.95), 10.0, "IceBox")
	_glb(tea, PROPS + "plastic_crate_red.glb", Vector3(-0.9, 0.0, 1.0), -8.0, "Crate")
	if _glb(tea, PROPS + "umbrella_tarp.glb", Vector3(0.0, 0.0, 0.95), 0.0, "Awning") == null:
		_mesh(tea, "AwningPole", _cyl(0.025, 0.025, 2.3, 8), steel, Vector3(0.0, 1.15, 0.9))
		_mesh(tea, "Awning", _cyl(0.02, 1.4, 0.35, 8), canvas, Vector3(0.0, 2.2, 0.9))
	# --- Cô Hoa's fish stall (north sidewalk, x≈-20)
	var fish := Node3D.new()
	fish.name = "FishStall"
	fish.position = Vector3(-20, 0.15, -5.4)
	p.add_child(fish)
	_box(fish, "FishTable", Vector3(0, 0.38, 0), Vector3(1.6, 0.08, 0.8), wood, true, "wood")
	_box(fish, "FishTableBase", Vector3(0, 0.17, 0), Vector3(1.5, 0.34, 0.7), _col(Color(0.3, 0.3, 0.32), 0.7), true, "wood")
	if _glb(fish, PROPS + "fish_basin.glb", Vector3(-0.25, 0.42, 0.0), 0.0, "FishBasin") == null:
		for i in 3:
			_mesh(fish, "Basin", _cyl(0.24, 0.18, 0.12, 20), _col(Color(0.15, 0.35, 0.6), 0.35), Vector3(-0.5 + i * 0.5, 0.48, 0.0))
			_mesh(fish, "Fish", _cyl(0.2, 0.2, 0.03, 16), _col(Color(0.62, 0.66, 0.7), 0.15, 0.5), Vector3(-0.5 + i * 0.5, 0.53, 0.0))
	_glb(fish, PROPS + "basin_plastic.glb", Vector3(0.55, 0.42, 0.05), 0.0, "Basin")
	_glb(fish, PROPS + "bucket_plastic.glb", Vector3(1.05, 0.0, -0.3), 0.0, "Bucket")
	_glb(fish, PROPS + "styrofoam_box.glb", Vector3(-1.1, 0.0, -0.25), 80.0, "IceBox")
	if _glb(fish, PROPS + "umbrella_tarp.glb", Vector3(0.0, 0.0, 0.35), 25.0, "Umbrella") == null:
		_mesh(fish, "Umbrella", _cyl(0.02, 1.3, 0.4, 10), _tex_mat(ARCH_TEX, "fabric_canvas", 2.0, Color(0.7, 0.15, 0.1), Color(1.0, 0.6, 0.55)), Vector3(0, 2.3, 0.2))
		_mesh(fish, "UmbrellaPole", _cyl(0.025, 0.025, 2.2, 8), steel, Vector3(0.7, 1.1, 0.2))
	# --- Chú Sáu's bánh mì cart (north sidewalk, x≈0)
	var cart := Node3D.new()
	cart.name = "BanhMiCart"
	cart.position = Vector3(0.5, 0.15, -5.0)
	p.add_child(cart)
	if _glb(cart, PROPS + "banh_mi_cart.glb", Vector3.ZERO, 180.0, "Cart") != null:
		_glb(cart, PROPS + "stool_plastic_blue.glb", Vector3(-0.2, 0.0, 0.85), 20.0, "VendorStool")
	else:
		_banh_mi_standin(cart)
	_stool(tea, Vector3(0.0, 0, 0.75), Color(0.15, 0.45, 0.25))   # Bà Tư's own stool
	# stools at the tea stall (sit POIs are right on them)
	for i in 3:
		_stool(tea, Vector3(-0.55 + i * 0.55, 0, 0.5 if i != 1 else -0.55), [Color(0.75, 0.1, 0.1), Color(0.1, 0.3, 0.7), Color(0.75, 0.1, 0.1)][i])
	_street_furniture(p)


func _banh_mi_standin(cart: Node3D) -> void:
	_box(cart, "CartBody", Vector3(0, 0.55, 0), Vector3(1.3, 0.7, 0.6), _col(Color(0.85, 0.82, 0.75), 0.4, 0.3), true, "metal")
	var glass := _col(Color(0.8, 0.9, 0.95), 0.05, 0.0)
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	glass.albedo_color.a = 0.3
	_box(cart, "CartGlass", Vector3(0, 1.15, 0), Vector3(1.25, 0.5, 0.55), glass, false)
	for i in 6:
		_mesh(cart, "Loaf", _cyl(0.035, 0.035, 0.26, 8), _col(Color(0.82, 0.58, 0.28), 0.6), Vector3(-0.4 + i * 0.16, 0.98, 0.0), Vector3(90, 0, 0))
	for wx: float in [-0.5, 0.5]:
		_mesh(cart, "Wheel", _cyl(0.2, 0.2, 0.05, 16), _col(Color(0.1, 0.1, 0.1), 0.8), Vector3(wx, 0.2, 0.32), Vector3(90, 0, 0))


func _street_furniture(p: Node3D) -> void:
	var canvas := _tex_mat(ARCH_TEX, "fabric_canvas", 2.0, Color(0.2, 0.4, 0.55))
	# lamp posts (props) + lights
	var lamp_path := PROPS + "lamp_post_colonial.glb"
	for lx: float in [-25.0, -12.0, 1.0, 14.0, 27.0]:
		for side: float in [-1.0, 1.0]:
			if side > 0 and lx > 0.0 and lx < 3.0:
				continue
			var pos := Vector3(lx, 0.15, side * 4.45)
			var lp := _glb(p, lamp_path, pos, 180.0 if side > 0 else 0.0, "Lamp")
			if lp == null:
				_mesh(p, "LampPole", _cyl(0.06, 0.08, 4.5, 10), _col(Color(0.12, 0.13, 0.12), 0.5, 0.6), pos + Vector3(0, 2.25, 0))
			var light := OmniLight3D.new()
			light.name = "LampLight"
			light.position = pos + Vector3(0, 4.2, -side * 0.6)
			light.omni_range = 11.0
			light.light_energy = 1.6
			light.light_color = Color(1.0, 0.82, 0.55)
			light.shadow_enabled = false
			light.distance_fade_enabled = true
			light.distance_fade_begin = 40.0
			light.add_to_group(&"street_light", true)
			light.visible = false
			p.add_child(light)
	# trash bins, cones etc. from street-props when present
	_glb(p, PROPS + "trash_bin_municipal.glb", Vector3(-22.5, 0.15, -6.2), 0.0)
	_glb(p, PROPS + "trash_bin_household.glb", Vector3(-6.0, 0.15, 6.4), 180.0)
	_glb(p, PROPS + "fire_hydrant.glb", Vector3(9.0, 0.15, 4.6), 0.0)
	_glb(p, PROPS + "bicycle_rack.glb", Vector3(6.0, 0.15, -6.0), 0.0)
	_glb(p, PROPS + "sign_aframe_cafe.glb", Vector3(9.5, 0.15, -4.8), 20.0)
	# concrete poles + overhead wire (sparrows)
	var pole := PROPS + "electric_pole_concrete.glb"
	for wx: float in [-6.0, 4.0]:
		if _glb(p, pole, Vector3(wx, 0.15, -6.7), 0.0, "Pole") == null:
			_mesh(p, "Pole", _cyl(0.1, 0.14, 8.0, 10), _col(Color(0.6, 0.6, 0.58), 0.8), Vector3(wx, 4.15, -6.7))
	var wire_mat := _col(Color(0.05, 0.05, 0.05), 0.6)
	var a := Vector3(-6.0, 6.6, -6.7)
	var bb := Vector3(4.0, 6.6, -6.7)
	var segs := 10
	for i in segs:
		var u0 := float(i) / segs
		var u1 := float(i + 1) / segs
		var p0 := a.lerp(bb, u0) - Vector3.UP * 0.3 * 4.0 * u0 * (1.0 - u0)
		var p1 := a.lerp(bb, u1) - Vector3.UP * 0.3 * 4.0 * u1 * (1.0 - u1)
		var w := _mesh(p, "Wire", _cyl(0.008, 0.008, p0.distance_to(p1), 4), wire_mat, (p0 + p1) * 0.5)
		w.look_at_from_position(w.position, p1, Vector3.UP)
		w.rotate_object_local(Vector3.RIGHT, PI * 0.5)
	# shelter: awning in front of the north shops (x -18..-12)
	var awn := _box(p, "ShopAwning", Vector3(-15.0, 2.6, -5.6), Vector3(6.0, 0.06, 2.4), canvas, true, "fabric")
	awn.rotation_degrees = Vector3(-8, 0, 0)
	var sh := Area3D.new()
	sh.name = "ShelterAwning"
	sh.add_to_group(&"shelter", true)
	sh.collision_layer = 1 << 9
	sh.collision_mask = 0
	sh.position = Vector3(-15.0, 1.3, -5.6)
	var scs := CollisionShape3D.new()
	var sbs := BoxShape3D.new()
	sbs.size = Vector3(6.0, 2.6, 2.4)
	scs.shape = sbs
	sh.add_child(scs)
	wroot.get_node("Markers").add_child(sh)


func _lake_park() -> void:
	var park := Node3D.new()
	park.name = "Park"
	nav_root.add_child(park)
	var grass := _tex_mat(GROUND_TEX, "grass", 2.0, Color(0.3, 0.42, 0.2))
	var stone := _tex_mat(GROUND_TEX, "stone_embankment", 1.5, Color(0.5, 0.48, 0.45))
	var lakebed := _tex_mat(GROUND_TEX, "lakebed", 3.0, Color(0.2, 0.2, 0.15))
	# park ground (top 0.15) around a lake basin x 9..25, z 13..25
	_box(park, "GroundGrassW", Vector3(4.5, -0.175, 22.0), Vector3(9.0, 0.65, 26.0), grass, true, "grass")
	_box(park, "GroundGrassE", Vector3(30.0, -0.175, 22.0), Vector3(10.0, 0.65, 26.0), grass, true, "grass")
	_box(park, "GroundGrassN", Vector3(17.0, -0.175, 11.0), Vector3(16.0, 0.65, 4.0), grass, true, "grass")
	_box(park, "GroundGrassS", Vector3(17.0, -0.175, 30.0), Vector3(16.0, 0.65, 10.0), grass, true, "grass")
	_box(park, "LakeBed", Vector3(17.0, -1.2, 19.0), Vector3(16.0, 0.4, 12.0), lakebed, true, "dirt")
	# embankment kerbs (low stone walls, 0.35 m) — high ground for cats, edge for koi watching
	_box(park, "EmbankN", Vector3(17.0, -0.3, 13.1), Vector3(16.4, 1.6, 0.3), stone, true, "concrete")
	_box(park, "EmbankS", Vector3(17.0, -0.3, 24.9), Vector3(16.4, 1.6, 0.3), stone, true, "concrete")
	_box(park, "EmbankW", Vector3(9.1, -0.3, 19.0), Vector3(0.3, 1.6, 12.0), stone, true, "concrete")
	_box(park, "EmbankE", Vector3(24.9, -0.3, 19.0), Vector3(0.3, 1.6, 12.0), stone, true, "concrete")
	var water := StandardMaterial3D.new()
	water.albedo_color = Color(0.12, 0.2, 0.18, 0.72)
	water.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	water.roughness = 0.04
	water.metallic = 0.15
	water.metallic_specular = 0.8
	var pm := PlaneMesh.new()
	pm.size = Vector2(15.6, 11.6)
	var wmi := _mesh(wroot, "LakeWater", pm, water, Vector3(17.0, -0.25, 19.0))
	wmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var lake_area := Area3D.new()
	lake_area.name = "LakeVolume"
	lake_area.collision_layer = 1 << 6
	lake_area.collision_mask = 0
	lake_area.monitoring = false
	lake_area.set_meta(&"water_level", -0.25)
	lake_area.set_meta(&"surface", &"water")
	lake_area.add_to_group(&"water", true)
	var lcs := CollisionShape3D.new()
	var lbs := BoxShape3D.new()
	lbs.size = Vector3(15.6, 1.0, 11.6)
	lcs.shape = lbs
	lake_area.add_child(lcs)
	lake_area.position = Vector3(17.0, -0.75, 19.0)
	wroot.add_child(lake_area)
	# banyan stand-in (trunk + aerial roots + canopy) — Lão Quạ's perch branch at ~3.6 m
	if ResourceLoader.exists(NATURE + "banyan.glb"):
		_glb(park, NATURE + "banyan.glb", Vector3(27.5, 0.15, 17.0), 0.0, "Banyan")
		lao_qua_pos = Vector3(27.5 - 0.188, 0.15 + 3.875, 17.0 + 0.496)
		_glb(park, NATURE + "frangipani.glb", Vector3(6.5, 0.15, 21.0), 30.0)
		_glb(park, NATURE + "areca_palm.glb", Vector3(7.0, 0.15, 30.0), 0.0)
		_glb(park, NATURE + "shrub_ixora.glb", Vector3(10.5, 0.15, 11.6), 0.0)
		_glb(park, NATURE + "shrub_ixora.glb", Vector3(23.0, 0.15, 11.6), 90.0)
		for lp: Vector3 in [Vector3(12.5, -0.25, 22.5), Vector3(21.0, -0.25, 15.5)]:
			_glb(wroot, NATURE + "lotus_cluster.glb", lp, randf() * 360.0)
	else:
		_banyan_standin(park)
	_box(park, "ParkWall", Vector3(4.5, 0.75, 16.0), Vector3(0.35, 1.2, 6.0), _tex_mat(ARCH_TEX, "brick_exposed", 1.0, Color(0.6, 0.35, 0.25)), true, "concrete")
	for bz: float in [10.2, 27.0]:
		# landmarks' lake bench: origin front-centre, seat toward +Z (Godot)
		if _glb(park, LANDMARKS + "ho_bench.glb", Vector3(14.0, 0.15, 10.85 if bz < 20.0 else 26.35), 0.0 if bz < 20.0 else 180.0, "Bench") == null:
			_box(park, "Bench", Vector3(14.0, 0.6, bz), Vector3(1.8, 0.08, 0.45), _tex_mat(ARCH_TEX, "wood_green", 1.0, Color(0.25, 0.4, 0.3)), true, "wood")


func _banyan_standin(park: Node3D) -> void:
	var tree := Node3D.new()
	tree.name = "Banyan"
	tree.position = Vector3(27.5, 0.15, 17.0)
	park.add_child(tree)
	var bark := _tex_mat(GROUND_TEX, "bark", 1.0, Color(0.35, 0.3, 0.25))
	var trunk := _box(tree, "Trunk", Vector3(0, 2.0, 0), Vector3(1.3, 4.0, 1.3), bark, true, "wood")
	trunk.get_child(0).set(&"mesh", _cyl(0.55, 0.85, 4.0, 18))
	for i in 7:
		var ang := TAU * i / 7.0
		_mesh(tree, "Root", _cyl(0.05, 0.08, 3.8, 6), bark, Vector3(cos(ang) * 1.3, 1.9, sin(ang) * 1.3))
	_mesh(tree, "Branch", _cyl(0.16, 0.24, 4.0, 10), bark, Vector3(-2.0, 3.45, 0.0), Vector3(0, 0, 80))
	var leaf := StandardMaterial3D.new()
	leaf.albedo_color = Color(0.17, 0.3, 0.12)
	leaf.roughness = 0.9
	var leaf2 := leaf.duplicate() as StandardMaterial3D
	leaf2.albedo_color = Color(0.22, 0.36, 0.14)
	for c: Array in [[Vector3(0, 6.2, 0), 3.4], [Vector3(-2.6, 5.4, 1.0), 2.4], [Vector3(2.0, 5.6, -1.2), 2.6],
			[Vector3(-1.0, 7.0, -1.8), 2.2], [Vector3(1.0, 5.2, 2.2), 2.0]]:
		var sm := SphereMesh.new()
		sm.radius = float(c[1])
		sm.height = float(c[1]) * 1.5
		_mesh(tree, "Canopy", sm, leaf if randf() < 0.5 else leaf2, c[0])


func _markers() -> void:
	var M := func(n: String, group: String, pos: Vector3, yaw: float, meta: Dictionary) -> Marker3D:
		return _marker(n, group, pos, yaw, meta)
	M.call("PlayerSpawn", "player_spawn", Vector3(4.0, 0.2, 7.0), 180.0, {})
	# named humans
	M.call("Spawn_ba_tu", "npc_spawn", Vector3(-10.0, 0.15, 6.35), 180.0, {"npc_kind": "vendor", "npc_id": "ba_tu"})
	M.call("Spawn_co_hoa", "npc_spawn", Vector3(-20.0, 0.15, -6.25), 0.0, {"npc_kind": "vendor", "npc_id": "co_hoa"})
	M.call("Spawn_chu_sau", "npc_spawn", Vector3(0.5, 0.15, -5.95), 0.0, {"npc_kind": "vendor", "npc_id": "chu_sau"})
	M.call("Spawn_bin", "npc_spawn", Vector3(12.0, 0.15, 11.0), 0.0, {"npc_kind": "pedestrian", "npc_id": "bin"})
	# ambient pedestrian spawn / exit points at the street ends
	for e: Array in [["PedSpawnW_N", Vector3(-32, 0.15, -5.5)], ["PedSpawnW_S", Vector3(-32, 0.15, 5.5)],
			["PedSpawnE_N", Vector3(32, 0.15, -5.5)], ["PedSpawnE_S", Vector3(32, 0.15, 6.5)]]:
		M.call(e[0], "npc_spawn", e[1], 0.0, {"npc_kind": "pedestrian"})
	# Vện + patrol path along the south sidewalk and plaza
	M.call("Spawn_ven", "npc_spawn", Vector3(-26.0, 0.15, 6.0), 90.0, {"npc_kind": "dog", "npc_id": "ven"})
	var patrol := Path3D.new()
	patrol.name = "PatrolVen"
	patrol.add_to_group(&"patrol_path", true)
	patrol.set_meta(&"npc_id", "ven")
	var pc := Curve3D.new()
	for pt: Vector3 in [Vector3(-26, 0.15, 6.0), Vector3(-14, 0.15, 6.2), Vector3(-4, 0.15, 5.6), Vector3(6, 0.15, 6.0),
			Vector3(6, 0.15, 5.0), Vector3(-4, 0.15, 5.0), Vector3(-18, 0.15, 5.0)]:
		pc.add_point(pt)
	patrol.curve = pc
	wroot.get_node("Markers").add_child(patrol)
	# Bin roams around the lake
	var bin_path := Path3D.new()
	bin_path.name = "RoamBin"
	bin_path.add_to_group(&"patrol_path", true)
	bin_path.set_meta(&"npc_id", "bin")
	var bc := Curve3D.new()
	for pt: Vector3 in [Vector3(7, 0.15, 12), Vector3(17, 0.15, 11.6), Vector3(27, 0.15, 12), Vector3(27, 0.15, 26),
			Vector3(17, 0.15, 26.5), Vector3(7, 0.15, 26)]:
		bc.add_point(pt)
	bin_path.curve = bc
	wroot.get_node("Markers").add_child(bin_path)
	# cats
	M.call("Spawn_mun", "npc_spawn", Vector3(4.5, 1.35, 16.0), 90.0, {"npc_kind": "cat", "npc_id": "mun", "roam_radius": 4.0})
	M.call("Spawn_bong", "npc_spawn", Vector3(9.0, 0.15, -5.6), 0.0, {"npc_kind": "cat", "npc_id": "bong"})
	M.call("Spawn_muop", "npc_spawn", Vector3(22.0, 0.15, 10.8), 200.0, {"npc_kind": "cat", "npc_id": "muop"})
	M.call("Spawn_stray1", "npc_spawn", Vector3(-17.0, 0.15, -6.3), 30.0, {"npc_kind": "cat"})
	M.call("Spawn_stray2", "npc_spawn", Vector3(-28.0, 0.15, 6.3), 120.0, {"npc_kind": "cat"})
	# birds
	M.call("Spawn_pigeons", "npc_spawn", Vector3(16.0, 0.15, 7.0), 0.0, {"npc_kind": "pigeon_flock", "npc_id": "xam", "count": 12, "radius": 3.2})
	M.call("Spawn_lao_qua", "npc_spawn", lao_qua_pos, -90.0, {"npc_kind": "crow", "npc_id": "lao_qua"})
	M.call("Spawn_crow", "npc_spawn", Vector3(-9.0, 30.0, -12.0), 0.0, {"npc_kind": "crow", "snap_to_surface": true})
	M.call("Spawn_sparrows", "npc_spawn", Vector3(-6.0, 6.6, -6.7), 0.0, {"npc_kind": "sparrows", "wire_end": Vector3(10, 0, 0), "sag": 0.3, "count": 8})
	# small life
	M.call("Spawn_mouse_market", "npc_spawn", Vector3(-21.5, 0.15, -6.6), 0.0, {"npc_kind": "mouse", "day_active": true, "roam_radius": 3.0})
	M.call("Spawn_mouse_park", "npc_spawn", Vector3(8.0, 0.15, 28.0), 0.0, {"npc_kind": "mouse", "roam_radius": 4.0})
	M.call("Spawn_koi", "npc_spawn", Vector3(17.0, -0.25, 19.0), 0.0, {"npc_kind": "koi", "volume_size": Vector3(14.5, 0.8, 10.5), "count": 12})
	# pedestrian POIs
	for i in 3:
		var sp := Vector3(-10.55 + i * 0.55, 0.15, 6.1 if i != 1 else 5.05)
		M.call("PoiTeaStool%d" % i, "pedestrian_poi", sp, 0.0 if i != 1 else 180.0, {"activity": "sit", "capacity": 1})
	M.call("PoiBench0", "pedestrian_poi", Vector3(14.0, 0.15, 10.6), 0.0, {"activity": "sit", "capacity": 2, "seat_height": 0.44})
	M.call("PoiBench1", "pedestrian_poi", Vector3(14.0, 0.15, 26.6), 180.0, {"activity": "sit", "capacity": 2, "seat_height": 0.44})
	M.call("PoiFishShop", "pedestrian_poi", Vector3(-20.0, 0.15, -4.6), 180.0, {"activity": "shop"})
	M.call("PoiBanhMi", "pedestrian_poi", Vector3(0.5, 0.15, -4.4), 180.0, {"activity": "shop"})
	M.call("PoiShopfront", "pedestrian_poi", Vector3(-27.0, 0.15, -6.2), 180.0, {"activity": "look"})
	M.call("PoiChatN", "pedestrian_poi", Vector3(-7.0, 0.15, -5.4), 0.0, {"activity": "chat"})
	M.call("PoiChatPlaza", "pedestrian_poi", Vector3(20.0, 0.15, 6.8), 90.0, {"activity": "chat"})
	M.call("PoiChatS", "pedestrian_poi", Vector3(-24.0, 0.15, 5.5), 0.0, {"activity": "chat"})
	M.call("PoiWaitBus", "pedestrian_poi", Vector3(12.0, 0.15, -5.3), 180.0, {"activity": "wait"})
	M.call("PoiLookLake", "pedestrian_poi", Vector3(19.0, 0.15, 12.4), 0.0, {"activity": "look"})
	# quest target + location for completeness
	M.call("LocLake", "location", Vector3(17, 0.15, 12), 0.0, {"location_id": "lake", "display_name_key": "LOC_LAKE"})


func _lanes() -> void:
	var lanes := Node3D.new()
	lanes.name = "TrafficLanes"
	wroot.add_child(lanes)
	for spec: Array in [["LaneEast", 2.0, -36.0, 36.0], ["LaneWest", -2.0, 36.0, -36.0]]:
		var path := Path3D.new()
		path.name = spec[0]
		path.add_to_group(&"traffic_lane", true)
		path.set_meta(&"vehicle_kinds", PackedStringArray(["motorbike", "bicycle", "car"]))
		path.set_meta(&"speed_limit", 8.0)
		var c := Curve3D.new()
		var z: float = spec[1]
		c.add_point(Vector3(spec[2], 0.0, z))
		c.add_point(Vector3(lerpf(spec[2], spec[3], 0.5), 0.0, z + (0.3 if z > 0 else -0.3)))
		c.add_point(Vector3(spec[3], 0.0, z))
		path.curve = c
		lanes.add_child(path)
	# motorbike-only lane hugging the kerb (scooters weave on the right)
	var p2 := Path3D.new()
	p2.name = "LaneEastKerb"
	p2.add_to_group(&"traffic_lane", true)
	p2.set_meta(&"vehicle_kinds", PackedStringArray(["motorbike", "bicycle"]))
	p2.set_meta(&"speed_limit", 6.5)
	var c2 := Curve3D.new()
	c2.add_point(Vector3(-36, 0.0, 3.2))
	c2.add_point(Vector3(36, 0.0, 3.2))
	p2.curve = c2
	lanes.add_child(p2)


func _nav() -> void:
	var nr := NavigationRegion3D.new()
	nr.name = "NavRegion"
	nr.add_to_group(&"nav_region", true)
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = &"nav_source"
	nm.agent_radius = 0.25
	nm.agent_height = 1.5
	nm.agent_max_climb = 0.25
	nm.agent_max_slope = 40.0
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nr.navigation_mesh = nm
	wroot.add_child(nr)
	nr.bake_navigation_mesh(false)
	print("NAV polygons: ", nm.get_polygon_count(), " vertices: ", nm.get_vertices().size())
