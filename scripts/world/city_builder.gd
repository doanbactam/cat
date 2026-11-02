extends RefCounted
## Hàng Mây city generator (owner: world).
##
## build() deterministically assembles the playable quarter from the asset catalogs
## (assets/models/{city,landmarks,props,vehicles,nature}/catalog.json) plus procedural world
## content (ground, lake, trees, procedural landmark stand-ins, street furniture, markers,
## interactables). post_physics() runs once the tree is inside a SceneTree with physics: it measures
## rooftops by ray casts, adds connectors (crate stairs / planks / walkable cable bundles) so the
## rooftop network is traversable, and bakes the navigation mesh. Re-running the builder picks up new
## or changed catalog entries automatically. Run via scripts/world/tools/build_city.gd.

const L := preload("res://scripts/world/city_layout.gd")
const MU := preload("res://scripts/world/mesh_util.gd")
const WM := preload("res://scripts/world/world_materials.gd")
const CS := preload("res://scripts/world/city_structures.gd")
const TG := preload("res://scripts/world/tree_gen.gd")

const CATALOGS := {
	"city": "res://assets/models/city/catalog.json",
	"landmarks": "res://assets/models/landmarks/catalog.json",
	"props": "res://assets/models/props/catalog.json",
	"vehicles": "res://assets/models/vehicles/catalog.json",
	"nature": "res://assets/models/nature/catalog.json",
}
const WIDTH_STEP := 0.5
const ROAD_Y := L.ROAD_Y

var seed_value := 20260915
var rng := RandomNumberGenerator.new()
var root: Node3D
var catalogs: Dictionary = {}
var placed: Array[Dictionary] = []        # building modules: id, entry, xf, w, d, row, net, node
var report: Dictionary = {"placeholders": [], "warnings": [], "counts": {}}
var _ground_sts: Dictionary = {}          # key -> SurfaceTool
var _ground_nodes: Dictionary = {}
var _groups: Dictionary = {}              # name -> Node3D container
var _scene_cache: Dictionary = {}
var _tree_count := 0
var decks: Dictionary = {}               # module id -> measured roof deck height (module_decks.json)
const DECKS_PATH := "res://scenes/world/module_decks.json"
const MAX_ROW_STEP := 3.6                # deck step between neighbours a crate stair can bridge


# =================================================================================================
# entry points
# =================================================================================================

func build() -> Node3D:
	rng.seed = seed_value
	WM.clear_cache()
	_load_catalogs()
	root = Node3D.new()
	root.name = "City"
	root.set_script(load("res://scripts/world/city.gd"))
	for g in ["Environment", "Ground", "Water", "Buildings", "Landmarks", "Nature", "StreetFurniture",
			"Cables", "Decals", "Lights", "Markers", "Interactables", "Zones", "Probes", "Occluders", "Festival", "Connectors"]:
		var n := Node3D.new()
		n.name = g
		root.add_child(n)
		_groups[g] = n
	_build_environment()
	_build_ground()
	_build_lake()
	_build_buildings()
	_build_landmarks()
	_build_nature()
	_build_street_furniture()
	_build_festival()
	_build_decals()
	_build_markers()
	_build_interactables()
	_build_zones()
	_build_probes_and_occluders()
	_finish_ground()
	return root


func grp(name: String) -> Node3D:
	return _groups[name]


# =================================================================================================
# catalogs
# =================================================================================================

func deck_of(e: Dictionary) -> float:
	var id := str(e.get("id", ""))
	if decks.has(id):
		return float(decks[id])
	# heuristic until measured: lowest high nap spot, else height - 1.3
	var h := float(e.get("height", 10.0))
	var best := INF
	for p: Variant in e.get("nap_spots", []):
		var y := float((p as Array)[1])
		if y >= h * 0.6:
			best = minf(best, y)
	return best if best < INF else h - 1.3


func _load_catalogs() -> void:
	if FileAccess.file_exists(DECKS_PATH):
		var dd: Variant = JSON.parse_string(FileAccess.get_file_as_string(DECKS_PATH))
		if dd is Dictionary:
			decks = dd
	for k: String in CATALOGS:
		var path: String = CATALOGS[k]
		var arr: Array = []
		if FileAccess.file_exists(path):
			var txt := FileAccess.get_file_as_string(path)
			var data: Variant = JSON.parse_string(txt)
			if data is Array:
				arr = data
			elif data is Dictionary:
				for key in ["modules", "items", "props", "entries", "assets"]:
					if (data as Dictionary).has(key) and data[key] is Array:
						arr = data[key]
						break
		# keep only entries whose file exists (other agents may still be writing)
		var ok: Array = []
		for e: Variant in arr:
			if e is Dictionary and ResourceLoader.exists(str(e.get("file", ""))):
				ok.append(e)
		catalogs[k] = ok
		report["counts"]["catalog_" + k] = ok.size()


func cat_find(cat: String, pred: Callable) -> Array:
	var out: Array = []
	for e: Dictionary in catalogs.get(cat, []):
		if pred.call(e):
			out.append(e)
	return out


func cat_by_id(cat: String, id: String) -> Dictionary:
	for e: Dictionary in catalogs.get(cat, []):
		if str(e.get("id", "")) == id:
			return e
	return {}


## First catalog entry (any of the given catalogs) whose id or tags contain any keyword.
func cat_keyword(cats: Array, keywords: Array) -> Dictionary:
	for c: String in cats:
		for e: Dictionary in catalogs.get(c, []):
			var hay := (str(e.get("id", "")) + " " + str(e.get("kind", "")) + " " + " ".join(PackedStringArray(e.get("tags", [])))).to_lower()
			for kw: String in keywords:
				if hay.contains(kw):
					return e
	return {}


func instance(file: String) -> Node3D:
	if not _scene_cache.has(file):
		_scene_cache[file] = load(file)
	var ps: PackedScene = _scene_cache[file]
	if ps == null:
		return null
	return ps.instantiate() as Node3D


func placeholder(what: String, why: String) -> void:
	(report["placeholders"] as Array).append("%s — %s" % [what, why])


# =================================================================================================
# environment: WorldEnvironment, Sun, Moon, WeatherSystem, NightLights
# =================================================================================================

func _build_environment() -> void:
	var g := grp("Environment")
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/sky_hangmay.gdshader")
	sm.set_shader_parameter(&"noise_tex", load("res://assets/textures/ground/noise_rgba.png"))
	sky.sky_material = sm
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	sky.process_mode = Sky.PROCESS_MODE_REALTIME
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.0
	env.ssr_enabled = true
	env.ssr_max_steps = 64
	env.ssr_fade_in = 0.15
	env.ssr_fade_out = 2.0
	env.ssr_depth_tolerance = 0.3
	env.ssao_enabled = true
	env.ssao_radius = 1.2
	env.ssao_intensity = 2.2
	env.ssao_power = 1.6
	env.ssao_detail = 0.6
	env.ssil_enabled = false
	env.sdfgi_enabled = true
	env.sdfgi_use_occlusion = true
	env.sdfgi_cascades = 5
	env.sdfgi_min_cell_size = 0.2
	env.sdfgi_y_scale = Environment.SDFGI_Y_SCALE_75_PERCENT
	env.sdfgi_energy = 1.0
	env.sdfgi_bounce_feedback = 0.5
	env.glow_enabled = true
	env.glow_intensity = 0.4
	env.glow_strength = 0.9
	env.glow_bloom = 0.04
	env.glow_hdr_threshold = 1.2
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_EXPONENTIAL
	env.fog_density = 0.0015
	env.fog_aerial_perspective = 0.35
	env.fog_sky_affect = 0.25
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.0045
	env.volumetric_fog_length = 96.0
	env.volumetric_fog_anisotropy = 0.55
	env.volumetric_fog_detail_spread = 2.0
	env.volumetric_fog_sky_affect = 0.15
	env.volumetric_fog_gi_inject = 0.6
	env.volumetric_fog_temporal_reprojection_enabled = true
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.04
	env.adjustment_saturation = 1.03
	var we := WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = env
	var ca := CameraAttributesPractical.new()
	ca.dof_blur_far_enabled = false
	we.camera_attributes = ca
	we.set_script(load("res://scripts/world/world_environment.gd"))
	root.add_child(we)
	# Sun first (LIGHT0 in the sky shader), Moon second (LIGHT1)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.shadow_enabled = true
	sun.light_angular_distance = 0.5
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 140.0
	sun.directional_shadow_split_1 = 0.06
	sun.directional_shadow_split_2 = 0.18
	sun.directional_shadow_split_3 = 0.45
	sun.directional_shadow_blend_splits = true
	sun.shadow_bias = 0.03
	sun.shadow_normal_bias = 1.2
	sun.light_volumetric_fog_energy = 1.4
	sun.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_AND_SKY
	root.add_child(sun)
	var moon := DirectionalLight3D.new()
	moon.name = "Moon"
	moon.shadow_enabled = false
	moon.light_energy = 0.0
	moon.light_color = Color(0.62, 0.72, 1.0)
	moon.directional_shadow_max_distance = 80.0
	moon.light_volumetric_fog_energy = 2.0
	root.add_child(moon)
	root.move_child(we, 0)
	root.move_child(sun, 1)
	root.move_child(moon, 2)
	var ws := Node3D.new()
	ws.name = "WeatherSystem"
	ws.set_script(load("res://scripts/world/weather_system.gd"))
	root.add_child(ws)
	var nl := Node.new()
	nl.name = "NightLights"
	nl.set_script(load("res://scripts/world/night_lights.gd"))
	root.add_child(nl)


# =================================================================================================
# ground
# =================================================================================================

func gst(key: StringName) -> SurfaceTool:
	if not _ground_sts.has(key):
		_ground_sts[key] = MU.new_st()
	return _ground_sts[key]


func grect(key: StringName, x0: float, z0: float, x1: float, z1: float, y: float) -> void:
	if x1 - x0 < 0.01 or z1 - z0 < 0.01:
		return
	MU.rect_xz(gst(key), x0, z0, x1, z1, y, WM.tile_of(key))


func gbox(key: StringName, center: Vector3, size: Vector3, yaw: float = 0.0, skip: PackedStringArray = PackedStringArray()) -> void:
	MU.box(gst(key), Transform3D(Basis(Vector3.UP, yaw), center), size, WM.tile_of(key), skip)


## Rect minus square holes (tree pits): splits along the long axis.
func grect_holes(key: StringName, x0: float, z0: float, x1: float, z1: float, y: float, holes: Array) -> void:
	var along_x := (x1 - x0) >= (z1 - z0)
	var cuts: Array = []
	for h: Rect2 in holes:
		if h.position.x >= x1 or h.end.x <= x0 or h.position.y >= z1 or h.end.y <= z0:
			continue
		cuts.append(h)
	cuts.sort_custom(func(a: Rect2, b: Rect2) -> bool: return (a.position.x < b.position.x) if along_x else (a.position.y < b.position.y))
	var cur := x0 if along_x else z0
	for h: Rect2 in cuts:
		if along_x:
			grect(key, cur, z0, h.position.x, z1, y)
			grect(key, h.position.x, z0, h.end.x, h.position.y, y)
			grect(key, h.position.x, h.end.y, h.end.x, z1, y)
			cur = h.end.x
		else:
			grect(key, x0, cur, x1, h.position.y, y)
			grect(key, x0, h.position.y, h.position.x, h.end.y, y)
			grect(key, h.end.x, h.position.y, x1, h.end.y, y)
			cur = h.end.y
	if along_x:
		grect(key, cur, z0, x1, z1, y)
	else:
		grect(key, x0, cur, x1, z1, y)


var tree_pits: Array = []        # Vector3 positions of street-tree pits


func _build_ground() -> void:
	# --- streets: asphalt, gutters, curbs, sidewalks with tree pits ---
	for s: Array in L.STREETS:
		var axis: String = s[1]
		var c: float = s[2]
		var a0: float = s[3]
		var a1: float = s[4]
		var rw: float = s[5]
		var sw: float = s[6]
		var hw := rw * 0.5
		if axis == "x":
			grect(&"asphalt", a0, c - hw, a1, c + hw, ROAD_Y)
		else:
			grect(&"asphalt", c - hw, a0, c + hw, a1, ROAD_Y)
		_street_edges(s)
	# intersections: fill the crossing squares are part of the N-S asphalt (z range overlaps)
	# --- block fills (alleys/courtyards at sidewalk level) ---
	grect(&"concrete", -121.0, -63.0, -61.0, 55.0, 0.0)          # west maze (alleys + light wells)
	grect(&"concrete", 56.0, -63.0, 122.0, 55.0, 0.0)            # market quarter
	grect(&"concrete", -122.0, -100.0, 122.0, -77.0, 0.0)        # behind the north row
	grect(&"concrete", -122.0, 69.0, -34.0, 100.0, 0.0)          # behind temple-street south rows
	grect(&"concrete", 34.0, 69.0, 122.0, 100.0, 0.0)
	grect(&"brick", -34.0, 69.0, 34.0, 100.0, 0.0)               # temple courtyard
	# market plaza: terrazzo-ish concrete under the hall is the same concrete; stall lanes get brick
	grect(&"brick", 60.0, 2.0, 116.0, 14.0, 0.005)               # fish lane paving
	# lake park lawn handled in _build_lake (needs the ellipse hole)


func _street_edges(s: Array) -> void:
	var id: String = s[0]
	var axis: String = s[1]
	var c: float = s[2]
	var a0: float = s[3]
	var a1: float = s[4]
	var hw: float = float(s[5]) * 0.5
	var sw: float = s[6]
	# sidewalk spans exclude crossings with perpendicular roads
	var crossings: Array = []
	for o: Array in L.STREETS:
		if o[1] != axis:
			var oc: float = o[2]
			var ohw: float = float(o[5]) * 0.5
			crossings.append([oc - ohw, oc + ohw, float(o[3]), float(o[4])])
	for side: float in [-1, 1]:
		var curb_line := c + side * hw
		var outer := c + side * (hw + sw)
		var spans: Array = [[a0, a1]]
		for cr: Array in crossings:
			# the perpendicular road crosses this sidewalk only if it reaches it
			var reach_lo: float = cr[2]
			var reach_hi: float = cr[3]
			var sw_lo := minf(curb_line, outer)
			var sw_hi := maxf(curb_line, outer)
			if reach_hi < sw_lo - 0.01 or reach_lo > sw_hi + 0.01:
				continue
			var new_spans: Array = []
			for sp: Array in spans:
				if cr[1] <= sp[0] or cr[0] >= sp[1]:
					new_spans.append(sp)
				else:
					if cr[0] > sp[0]:
						new_spans.append([sp[0], cr[0]])
					if cr[1] < sp[1]:
						new_spans.append([cr[1], sp[1]])
			spans = new_spans
		# N-S street sidewalks stop at the E-W sidewalks
		if axis == "z":
			spans = [[a0 + 3.0, a1 - 3.0]]
		for sp: Array in spans:
			var s0: float = sp[0]
			var s1: float = sp[1]
			if s1 - s0 < 0.5:
				continue
			var curb_in := curb_line + side * 0.2
			# street trees: pits every ~11 m on wide sidewalks (not in front of the lake block's park side)
			var holes: Array = []
			var t := s0 + 6.0
			while t < s1 - 3.0:
				var pit_c := curb_line + side * (0.2 + 0.8)
				var hole: Rect2
				if axis == "x":
					hole = Rect2(t - 0.6, pit_c - 0.6, 1.2, 1.2)
				else:
					hole = Rect2(pit_c - 0.6, t - 0.6, 1.2, 1.2)
				if rng.randf() < 0.8 and _tree_pit_allowed(id, side, t):
					holes.append(hole)
					tree_pits.append(Vector3(hole.get_center().x, 0.0, hole.get_center().y))
				t += rng.randf_range(10.0, 13.0)
			if axis == "x":
				grect_holes(&"pavers", s0, minf(curb_in, outer), s1, maxf(curb_in, outer), 0.0, holes)
				# curb (granite) between road and sidewalk
				var cz := curb_line + side * 0.1
				gbox(&"granite", Vector3((s0 + s1) * 0.5, ROAD_Y * 0.5 - 0.05, cz), Vector3(s1 - s0, -ROAD_Y + 0.1, 0.2), 0.0, PackedStringArray(["bottom"]))
				grect(&"gutter", s0, minf(curb_line, curb_line - side * 0.4), s1, maxf(curb_line, curb_line - side * 0.4), ROAD_Y + 0.004)
			else:
				var hs: Array = []
				for h: Rect2 in holes:
					hs.append(h)
				grect_holes(&"pavers", minf(curb_in, outer), s0, maxf(curb_in, outer), s1, 0.0, hs)
				var cx := curb_line + side * 0.1
				gbox(&"granite", Vector3(cx, ROAD_Y * 0.5 - 0.05, (s0 + s1) * 0.5), Vector3(0.2, -ROAD_Y + 0.1, s1 - s0), 0.0, PackedStringArray(["bottom"]))
				grect(&"gutter", minf(curb_line, curb_line - side * 0.4), s0, maxf(curb_line, curb_line - side * 0.4), s1, ROAD_Y + 0.004)
	# tree pits: soil + granite frame
	for p: Vector3 in tree_pits:
		grect(&"lakebed", p.x - 0.6, p.z - 0.6, p.x + 0.6, p.z + 0.6, -0.04)


func _tree_pit_allowed(_street: String, _side: int, _t: float) -> bool:
	return true


func _finish_ground() -> void:
	var g := grp("Ground")
	var surfaces := {&"asphalt": &"asphalt", &"pavers": &"tile", &"granite": &"concrete", &"concrete": &"concrete",
		&"gutter": &"concrete", &"brick": &"tile", &"grass": &"grass", &"embankment": &"concrete", &"wood": &"wood", &"lakebed": &"dirt"}
	for key: StringName in _ground_sts:
		var st: SurfaceTool = _ground_sts[key]
		st.generate_tangents()
		var mesh := st.commit()
		mesh.surface_set_material(0, WM.ground(key))
		var mi := MeshInstance3D.new()
		mi.name = "Ground_" + String(key)
		mi.mesh = mesh
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if key in [&"asphalt", &"pavers", &"gutter", &"concrete", &"brick", &"grass", &"lakebed"] else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		g.add_child(mi)
		if key == &"lakebed":
			continue          # tree pit soil & lake bed: lake bed collision is added separately
		var body := StaticBody3D.new()
		body.name = "GroundBody_" + String(key)
		body.collision_layer = 1
		body.collision_mask = 0
		body.set_meta(&"surface", surfaces.get(key, &"concrete"))
		body.add_to_group(&"nav_source")
		var cs := CollisionShape3D.new()
		cs.shape = mesh.create_trimesh_shape()
		body.add_child(cs)
		g.add_child(body)
	# safety floor far below (anything that falls through the world lands somewhere)
	var floor_body := StaticBody3D.new()
	floor_body.name = "SafetyFloor"
	floor_body.collision_layer = 1
	floor_body.set_meta(&"surface", &"dirt")
	var fcs := CollisionShape3D.new()
	var fbs := BoxShape3D.new()
	fbs.size = Vector3(300, 1, 260)
	fcs.shape = fbs
	fcs.position = Vector3(0, -6.0, 0)
	floor_body.add_child(fcs)
	g.add_child(floor_body)
	# map boundary (invisible walls at the street ends)
	var bound := StaticBody3D.new()
	bound.name = "MapBounds"
	bound.collision_layer = 1 | (1 << 8)
	for b: Array in [[Vector3(-126, 10, -70), Vector3(1, 30, 30)], [Vector3(126, 10, -70), Vector3(1, 30, 30)],
			[Vector3(-126, 10, 62), Vector3(1, 30, 30)], [Vector3(126, 10, 62), Vector3(1, 30, 30)]]:
		var c := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = b[1]
		c.shape = bs
		c.position = b[0]
		bound.add_child(c)
	g.add_child(bound)


# =================================================================================================
# lake: lawn with ellipse hole, promenade ring, embankment, water, bed, islet, bridge
# =================================================================================================

func _ell(t: float, scale: float = 1.0, center: Vector2 = L.LAKE_CENTER, radii: Vector2 = L.LAKE_RADII) -> Vector2:
	return center + Vector2(cos(t) * radii.x * scale, sin(t) * radii.y * scale)


func _in_ellipse(p: Vector2, center: Vector2, radii: Vector2, grow: float = 0.0) -> bool:
	var q := (p - center) / (radii + Vector2(grow, grow))
	return q.length_squared() < 1.0


func _build_lake() -> void:
	var cen: Vector2 = L.LAKE_CENTER
	var rad: Vector2 = L.LAKE_RADII
	var wy: float = L.LAKE_WATER_Y
	var segs := 96
	# lawn: 1 m cells over the park, skipping cells inside promenade outer ellipse
	var pw: float = L.PROMENADE_W
	var park := Rect2(-49.0, -49.0, 93.0, 104.0)
	var step := 1.0
	var x := park.position.x
	while x < park.end.x - 0.001:
		var z := park.position.y
		var run_start := NAN
		while z < park.end.y - 0.001:
			var inside := _in_ellipse(Vector2(x + step * 0.5, z + step * 0.5), cen, rad, pw - 0.6)
			if inside:
				if not is_nan(run_start):
					grect(&"grass", x, run_start, x + step, z, 0.0)
					run_start = NAN
			elif is_nan(run_start):
				run_start = z
			z += step
		if not is_nan(run_start):
			grect(&"grass", x, run_start, x + step, park.end.y, 0.0)
		x += step
	# promenade ring (brick) from the wall coping outward, slightly above the lawn
	var st := gst(&"brick")
	for i in segs:
		var t0 := TAU * i / segs
		var t1 := TAU * (i + 1) / segs
		var a0 := _ell(t0, 1.0)
		var a1 := _ell(t1, 1.0)
		var b0 := cen + (a0 - cen).normalized() * ((a0 - cen).length() + pw)
		var b1 := cen + (a1 - cen).normalized() * ((a1 - cen).length() + pw)
		var A := Vector3(a0.x, 0.01, a0.y)
		var B := Vector3(a1.x, 0.01, a1.y)
		var C := Vector3(b1.x, 0.01, b1.y)
		var D := Vector3(b0.x, 0.01, b0.y)
		var tile := WM.tile_of(&"brick")
		var uvs: Array[Vector2] = [Vector2(A.x, A.z) / tile, Vector2(D.x, D.z) / tile, Vector2(C.x, C.z) / tile, Vector2(B.x, B.z) / tile]
		MU.quad(st, A, D, C, B, Vector3.UP, uvs)
	# embankment: inner wall face (stone), coping (granite), collision boxes
	var wall_top := 0.12
	var bed_edge := wy - 0.55
	var est := gst(&"embankment")
	var cst := gst(&"granite")
	var ebody := StaticBody3D.new()
	ebody.name = "Embankment"
	ebody.collision_layer = 1
	ebody.set_meta(&"surface", &"concrete")
	grp("Water").add_child(ebody)
	for i in segs:
		var t0 := TAU * i / segs
		var t1 := TAU * (i + 1) / segs
		var p0 := _ell(t0)
		var p1 := _ell(t1)
		var top0 := Vector3(p0.x, wall_top, p0.y)
		var top1 := Vector3(p1.x, wall_top, p1.y)
		var bot0 := Vector3(p0.x, bed_edge - 0.3, p0.y)
		var bot1 := Vector3(p1.x, bed_edge - 0.3, p1.y)
		var inward := Vector3(cen.x - (p0.x + p1.x) * 0.5, 0, cen.y - (p0.y + p1.y) * 0.5).normalized()
		var seg_len := p0.distance_to(p1)
		var uvs: Array[Vector2] = [Vector2(0, 0), Vector2(seg_len / 2.0, 0), Vector2(seg_len / 2.0, (wall_top - bed_edge + 0.3) / 2.0), Vector2(0, (wall_top - bed_edge + 0.3) / 2.0)]
		uvs = [Vector2(i * seg_len / 2.0, 0), Vector2((i + 1) * seg_len / 2.0, 0), Vector2((i + 1) * seg_len / 2.0, 0.9), Vector2(i * seg_len / 2.0, 0.9)]
		# wall faces the water (inward). Order so the face is visible from inside.
		MU.quad(est, top1, top0, bot0, bot1, inward, uvs)
		# coping: 0.45 wide slab from the wall outward, 0.12 above the promenade
		var out0 := top0 - inward * 0.45
		var out1 := top1 - inward * 0.45
		var cuv: Array[Vector2] = [Vector2(0, 0), Vector2(seg_len, 0), Vector2(seg_len, 0.45), Vector2(0, 0.45)]
		MU.quad(cst, top0, top1, out1, out0, Vector3.UP, [Vector2(i * seg_len, 0), Vector2((i + 1) * seg_len, 0), Vector2((i + 1) * seg_len, 0.45), Vector2(i * seg_len, 0.45)])
		# coping outer lip down to the promenade
		var o0d := Vector3(out0.x, 0.0, out0.z)
		var o1d := Vector3(out1.x, 0.0, out1.z)
		MU.quad(cst, out0, out1, o1d, o0d, -inward, [Vector2(0, 0), Vector2(seg_len, 0), Vector2(seg_len, 0.12), Vector2(0, 0.12)])
		var mid := (top0 + top1) * 0.5 - inward * 0.2
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = Vector3(seg_len + 0.06, wall_top - bed_edge + 0.5, 0.45)
		cs.shape = bs
		cs.transform = Transform3D(Basis.looking_at(inward, Vector3.UP), Vector3(mid.x, (wall_top + bed_edge - 0.5) * 0.5, mid.z))
		ebody.add_child(cs)
	# lake bed (bowl)
	var bst := MU.new_st()
	var rings := 10
	for r in rings:
		for i in segs:
			var t0 := TAU * i / segs
			var t1 := TAU * (i + 1) / segs
			var s0 := float(r) / rings
			var s1 := float(r + 1) / rings
			var pts: Array[Vector3] = []
			for c: Array in [[t0, s1], [t1, s1], [t1, s0], [t0, s0]]:
				var q := _ell(float(c[0]), maxf(float(c[1]), 0.001) * 1.0 + 0.0)
				var dd: float = float(c[1])
				var y := wy - 0.55 - L.LAKE_DEPTH * (1.0 - dd * dd)
				pts.append(Vector3(q.x, y, q.y))
			MU.quad(bst, pts[0], pts[1], pts[2], pts[3], Vector3.UP, [Vector2(pts[0].x, pts[0].z) / 4.0, Vector2(pts[1].x, pts[1].z) / 4.0, Vector2(pts[2].x, pts[2].z) / 4.0, Vector2(pts[3].x, pts[3].z) / 4.0])
	bst.generate_normals()
	bst.generate_tangents()
	var bed_mesh := bst.commit()
	bed_mesh.surface_set_material(0, WM.ground(&"lakebed"))
	var bed := MeshInstance3D.new()
	bed.name = "LakeBed"
	bed.mesh = bed_mesh
	bed.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	grp("Water").add_child(bed)
	var bed_body := StaticBody3D.new()
	bed_body.name = "LakeBedBody"
	bed_body.collision_layer = 1
	bed_body.set_meta(&"surface", &"dirt")
	var bcs := CollisionShape3D.new()
	bcs.shape = bed_mesh.create_trimesh_shape()
	bed_body.add_child(bcs)
	grp("Water").add_child(bed_body)
	# water surface: fan of triangles slightly larger than the wall
	var wst := MU.new_st()
	for i in segs:
		var t0 := TAU * i / segs
		var t1 := TAU * (i + 1) / segs
		for r in 6:
			var s0 := float(r) / 6.0
			var s1 := float(r + 1) / 6.0
			var q00 := _ell(t0, s0 * 1.01)
			var q10 := _ell(t1, s0 * 1.01)
			var q11 := _ell(t1, s1 * 1.01)
			var q01 := _ell(t0, s1 * 1.01)
			var A := Vector3(q01.x, wy, q01.y)
			var B := Vector3(q11.x, wy, q11.y)
			var C := Vector3(q10.x, wy, q10.y)
			var D := Vector3(q00.x, wy, q00.y)
			MU.quad(wst, D, C, B, A, Vector3.UP, [Vector2(D.x, D.z), Vector2(C.x, C.z), Vector2(B.x, B.z), Vector2(A.x, A.z)])
	wst.generate_tangents()
	var wmesh := wst.commit()
	var wmat := WM.water()
	wmat.set_shader_parameter(&"lake_center", cen)
	wmat.set_shader_parameter(&"lake_radii", rad)
	wmat.set_shader_parameter(&"max_depth", L.LAKE_DEPTH)
	var water := MeshInstance3D.new()
	water.name = "LakeWater"
	water.mesh = wmesh
	water.material_override = wmat
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	water.add_to_group(&"lake_water")
	grp("Water").add_child(water)
	# water volume (layer 7) — top face = water surface, meta water_level
	var area := Area3D.new()
	area.name = "LakeVolume"
	area.collision_layer = 1 << 6
	area.collision_mask = 0
	area.monitorable = true
	area.monitoring = false
	area.set_meta(&"water_level", wy)
	area.set_meta(&"surface", &"water")
	area.add_to_group(&"water")
	var acs := CollisionShape3D.new()
	var abs := BoxShape3D.new()
	abs.size = Vector3(rad.x * 2.0, 3.0, rad.y * 2.0)
	acs.shape = abs
	acs.position = Vector3(cen.x, wy - 1.5, cen.y)
	area.add_child(acs)
	grp("Water").add_child(area)
	# water steps (bến) at two places: north-east & south-west
	for t: float in [-0.9, 2.3]:
		_lake_steps(t)
	# lotus patches
	for lp: Array in [[Vector2(-24, -8), 7.0, 140], [Vector2(-10, 24), 5.0, 80], [Vector2(6, -18), 4.0, 50]]:
		var lotus := TG.make_lotus_patch(lp[1], lp[2], int(lp[0].x * 13 + lp[0].y))
		lotus.position = Vector3(lp[0].x, wy, lp[0].y)
		grp("Water").add_child(lotus)
	_build_islet()


func _lake_steps(t: float) -> void:
	var p := _ell(t)
	var inward := (L.LAKE_CENTER - p).normalized()
	var yaw := atan2(inward.x, inward.y)
	var n := Node3D.new()
	n.name = "LakeSteps"
	n.position = Vector3(p.x, 0, p.y)
	n.rotation.y = yaw
	grp("Water").add_child(n)
	var k := CS.Kit.new(n)
	var stone := WM.ground_std(&"granite")
	for i in 4:
		var y := 0.12 - (i + 1) * 0.16
		k.box(stone, Transform3D(Basis(), Vector3(0, y - 0.1 + 0.08, 0.2 + i * 0.35)), Vector3(2.4, 0.2, 0.36), 1.0, &"concrete")
	k.finish("Steps")


func _build_islet() -> void:
	var c: Vector2 = L.ISLET_CENTER
	var r: Vector2 = L.ISLET_RADII
	var segs := 40
	var top := 0.25
	var gst_grass := gst(&"grass")
	var est := gst(&"embankment")
	var body := StaticBody3D.new()
	body.name = "Islet"
	body.collision_layer = 1
	body.set_meta(&"surface", &"grass")
	grp("Water").add_child(body)
	for i in segs:
		var t0 := TAU * i / segs
		var t1 := TAU * (i + 1) / segs
		var p0 := _ell(t0, 1.0, c, r)
		var p1 := _ell(t1, 1.0, c, r)
		var A := Vector3(c.x, top, c.y)
		var B := Vector3(p0.x, top, p0.y)
		var C := Vector3(p1.x, top, p1.y)
		# fan (clockwise from above) — top
		for v: Vector3 in [A, C, B]:
			gst_grass.set_normal(Vector3.UP)
			gst_grass.set_uv(Vector2(v.x, v.z) / 2.0)
			gst_grass.add_vertex(v)
		var outward := Vector3((p0.x + p1.x) * 0.5 - c.x, 0, (p0.y + p1.y) * 0.5 - c.y).normalized()
		var seg_len := p0.distance_to(p1)
		MU.quad(est, Vector3(p0.x, top, p0.y), Vector3(p1.x, top, p1.y), Vector3(p1.x, L.LAKE_WATER_Y - 1.0, p1.y), Vector3(p0.x, L.LAKE_WATER_Y - 1.0, p0.y), outward,
			[Vector2(i * seg_len / 2.0, 0), Vector2((i + 1) * seg_len / 2.0, 0), Vector2((i + 1) * seg_len / 2.0, 0.8), Vector2(i * seg_len / 2.0, 0.8)])
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = minf(r.x, r.y)
	cyl.height = 2.0
	cs.shape = cyl
	cs.position = Vector3(c.x, top - 1.0, c.y)
	cs.scale = Vector3.ONE
	body.add_child(cs)
	# fill the ellipse ends with boxes
	for sx: float in [-1, 1]:
		var bcs := CollisionShape3D.new()
		var bb := BoxShape3D.new()
		bb.size = Vector3(r.x - r.y + 0.6, 2.0, r.y * 1.2)
		bcs.shape = bb
		bcs.position = Vector3(c.x + sx * (r.y + (r.x - r.y) * 0.5 - 0.6), top - 1.0, c.y)
		body.add_child(bcs)


# =================================================================================================
# buildings
# =================================================================================================

func _module_pool(max_depth: float, styles: Dictionary) -> Array:
	return cat_find("city", func(e: Dictionary) -> bool:
		return str(e.get("kind", "")) in ["house", "shop"] and float(e.get("depth", 99)) <= max_depth + 0.01 \
			and styles.has(str(e.get("style", ""))))


func _reachable_lengths(widths: Array, max_len: float) -> Dictionary:
	var n := int(round(max_len / WIDTH_STEP))
	var reach := {0: true}
	for i in range(1, n + 1):
		for w: float in widths:
			var j := i - int(round(w / WIDTH_STEP))
			if j >= 0 and reach.has(j):
				reach[i] = true
				break
	return reach


func _build_buildings() -> void:
	for row: Array in L.ROWS:
		_fill_row(row)
	for wr: Array in L.WALL_RUNS:
		_wall_run(wr)
	report["counts"]["building_modules"] = placed.size()


func _row_basis(facing: Vector2) -> Basis:
	return Basis(Vector3.UP, atan2(facing.x, facing.y))


func _fill_row(row: Array) -> void:
	var name: String = row[0]
	var start: Vector2 = row[1]
	var facing: Vector2 = row[2]
	var length: float = row[3]
	var max_depth: float = row[4]
	var styles: Dictionary = row[5]
	var gaps: Array = row[6]
	var corner_end: bool = row[7]
	var net: bool = row[8]
	var basis := _row_basis(facing)
	var along := basis.x
	var origin := Vector3(start.x, 0.0, start.y)
	var pool := _module_pool(max_depth, styles)
	if pool.is_empty():
		report["warnings"].append("row %s: no modules for styles %s" % [name, styles.keys()])
		return
	var widths: Array = []
	for e: Dictionary in pool:
		var w := float(e["width"])
		if not w in widths:
			widths.append(w)
	# spans between gaps
	var spans: Array = []
	var cur := 0.0
	var sorted_gaps := gaps.duplicate()
	sorted_gaps.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	for g: Array in sorted_gaps:
		spans.append([cur, float(g[0])])
		cur = float(g[1])
	spans.append([cur, length])
	var corner_entry := {}
	if corner_end:
		var corners := cat_find("city", func(e: Dictionary) -> bool: return str(e.get("kind", "")) == "corner" and float(e.get("depth", 99)) <= max_depth + 0.01)
		if not corners.is_empty():
			corner_entry = corners[rng.randi_range(0, corners.size() - 1)]
	var prev_variant := ""
	var prev_h := -1.0
	for si in spans.size():
		var s0: float = spans[si][0]
		var s1: float = spans[si][1]
		if si == spans.size() - 1 and not corner_entry.is_empty():
			var cw := float(corner_entry["width"])
			_place_module(corner_entry, origin + along * (s1 - cw * 0.5), basis, name, net)
			s1 -= cw
		var span := s1 - s0
		var usable := floorf(span / WIDTH_STEP) * WIDTH_STEP
		var reach := _reachable_lengths(widths, usable)
		# fall back to the largest reachable length ≤ usable
		var target_steps := int(round(usable / WIDTH_STEP))
		while target_steps > 0 and not reach.has(target_steps):
			target_steps -= 1
		var filled := float(target_steps) * WIDTH_STEP
		var slack := span - filled
		var pos := s0 + slack * 0.5
		if slack > 0.05:
			_filler_pier(origin + along * (s0 + slack * 0.25), basis, slack * 0.5, name)
			_filler_pier(origin + along * (s1 - slack * 0.25), basis, slack * 0.5, name)
		var remaining_steps := target_steps
		while remaining_steps > 0:
			var cands: Array = []
			for e: Dictionary in pool:
				var ws := int(round(float(e["width"]) / WIDTH_STEP))
				if ws > remaining_steps or not reach.has(remaining_steps - ws):
					continue
				if str(e.get("variant_of", e["id"])) == prev_variant:
					continue
				cands.append(e)
			if cands.is_empty():
				for e: Dictionary in pool:
					var ws := int(round(float(e["width"]) / WIDTH_STEP))
					if ws <= remaining_steps and reach.has(remaining_steps - ws):
						cands.append(e)
			if cands.is_empty():
				break
			if net and prev_h > 0.0:
				var near: Array = cands.filter(func(e: Dictionary) -> bool: return absf(deck_of(e) - prev_h) <= MAX_ROW_STEP)
				if not near.is_empty():
					cands = near
				else:
					var ph := prev_h
					cands.sort_custom(func(a: Dictionary, c: Dictionary) -> bool: return absf(deck_of(a) - ph) < absf(deck_of(c) - ph))
					cands = cands.slice(0, 1)
			var pick := _weighted_pick(cands, styles, prev_h, net)
			var w := float(pick["width"])
			_place_module(pick, origin + along * (pos + w * 0.5), basis, name, net)
			pos += w
			remaining_steps -= int(round(w / WIDTH_STEP))
			prev_variant = str(pick.get("variant_of", pick["id"]))
			prev_h = deck_of(pick)


func _weighted_pick(cands: Array, styles: Dictionary, prev_h: float, net: bool) -> Dictionary:
	var total := 0.0
	var ws: Array = []
	for e: Dictionary in cands:
		var w := float(styles.get(str(e.get("style", "")), 0.5))
		if net and prev_h > 0.0:
			var dh := absf(deck_of(e) - prev_h)
			w *= 1.0 if dh <= 3.0 else (0.35 if dh <= 6.0 else 0.12)
		ws.append(w)
		total += w
	var r := rng.randf() * total
	for i in cands.size():
		r -= float(ws[i])
		if r <= 0.0:
			return cands[i]
	return cands[cands.size() - 1]


func _place_module(e: Dictionary, pos: Vector3, basis: Basis, row: String, net: bool) -> Node3D:
	var inst := instance(str(e["file"]))
	if inst == null:
		report["warnings"].append("cannot instance " + str(e["file"]))
		return null
	inst.name = "%s_%d" % [str(e["id"]), placed.size()]
	inst.transform = Transform3D(basis, pos)
	inst.set_meta(&"module_id", str(e["id"]))
	inst.set_meta(&"row", row)
	grp("Buildings").add_child(inst)
	placed.append({"id": str(e["id"]), "entry": e, "xf": inst.transform, "w": float(e["width"]),
		"d": float(e["depth"]), "h": float(e.get("height", 10.0)), "row": row, "net": net, "node": inst})
	return inst


## Narrow plaster pier filling < 0.5 m slack in a row (looks like a party-wall pilaster).
func _filler_pier(pos: Vector3, basis: Basis, width: float, row: String) -> void:
	if width < 0.02:
		return
	var n := Node3D.new()
	n.name = "Pier_" + row
	grp("Buildings").add_child(n)
	var k := CS.Kit.new(n)
	k.box(WM.arch("cement_render"), Transform3D(basis, pos + Vector3(0, 3.6, 0) - basis.z * 4.0), Vector3(width, 7.2, 8.0), 2.0, &"concrete")
	k.finish("PierMesh")


func _wall_run(wr: Array) -> void:
	var start: Vector2 = wr[0]
	var facing: Vector2 = wr[1]
	var length: float = wr[2]
	var kind: String = wr[3]
	if length <= 0.0:
		return
	var pool := cat_find("city", func(e: Dictionary) -> bool: return str(e.get("kind", "")) == kind)
	if pool.is_empty():
		return
	var basis := _row_basis(facing)
	var along := basis.x
	var origin := Vector3(start.x, 0.0, start.y)
	var pos := 0.0
	var prev := ""
	while pos < length - 1.0:
		var cands := pool.filter(func(e: Dictionary) -> bool: return str(e.get("id")) != prev)
		var e: Dictionary = cands[rng.randi_range(0, cands.size() - 1)]
		var w := float(e["width"])
		var inst := instance(str(e["file"]))
		if inst == null:
			return
		inst.name = "%s_wall_%d" % [str(e["id"]), int(pos)]
		inst.transform = Transform3D(basis, origin + along * (pos + w * 0.5))
		grp("Buildings").add_child(inst)
		prev = str(e["id"])
		pos += w


# =================================================================================================
# landmarks (catalog first, procedural stand-ins otherwise)
# =================================================================================================

var temple_hall: Node3D
var water_tower: Node3D


func _landmark(keywords: Array, fallback: Callable, pos: Vector3, yaw: float, label: String) -> Node3D:
	var e := cat_keyword(["landmarks"], keywords)
	var n: Node3D
	if not e.is_empty():
		n = instance(str(e["file"]))
		n.name = label
		n.set_meta(&"catalog_id", str(e["id"]))
	else:
		n = fallback.call()
		n.name = label
		placeholder("%s (procedural, scripts/world/city_structures.gd)" % label, "no landmarks catalog entry matching %s" % str(keywords))
	n.position = pos
	n.rotation.y = yaw
	grp("Landmarks").add_child(n)
	return n


func _build_landmarks() -> void:
	var tr: Rect2 = L.TEMPLE_RECT
	# temple hall faces north (toward the street & lake): yaw PI turns +Z front to -Z
	temple_hall = _landmark(["dinh", "temple_hall", "temple"], func() -> Node3D: return CS.make_temple_hall(), Vector3(L.TEMPLE_HALL_CENTER.x, 0, L.TEMPLE_HALL_CENTER.y), PI, "TempleHall")
	_landmark(["temple_gate", "tam_quan", "gate"], func() -> Node3D: return CS.make_temple_gate(), Vector3(0, 0, tr.position.y + 0.8), PI, "TempleGate")
	_landmark(["bell"], func() -> Node3D: return CS.make_bell_pavilion(), Vector3(L.BELL_PAVILION.x, 0, L.BELL_PAVILION.y), PI, "BellPavilion")
	_landmark(["incense", "burner"], func() -> Node3D: return CS.make_incense_burner(), Vector3(0, 0, 80.0), 0.0, "IncenseBurner")
	# compound walls (leave the gate opening)
	var walls := [
		[Vector3(tr.position.x, 0, tr.position.y + 0.8), Vector3(-6.4, 0, tr.position.y + 0.8)],
		[Vector3(6.4, 0, tr.position.y + 0.8), Vector3(tr.end.x, 0, tr.position.y + 0.8)],
		[Vector3(tr.position.x, 0, tr.position.y + 0.8), Vector3(tr.position.x, 0, tr.end.y - 0.5)],
		[Vector3(tr.end.x, 0, tr.position.y + 0.8), Vector3(tr.end.x, 0, tr.end.y - 0.5)],
		[Vector3(tr.position.x, 0, tr.end.y - 0.5), Vector3(tr.end.x, 0, tr.end.y - 0.5)],
	]
	for w: Array in walls:
		var wn := CS.make_wall(w[0], w[1])
		grp("Landmarks").add_child(wn)
	# market hall + stalls
	var mh: Rect2 = L.MARKET_HALL
	_landmark(["market_hall", "cho", "market"], func() -> Node3D: return CS.make_market_hall(mh.size.x, mh.size.y),
		Vector3(mh.get_center().x, 0, mh.get_center().y), 0.0, "MarketHall")
	_build_market_stalls()
	# water tower
	var wt: Vector2 = L.WATER_TOWER_POS
	water_tower = _landmark(["water_tower", "thap_nuoc", "tower"], func() -> Node3D: return CS.make_water_tower(), Vector3(wt.x, 0, wt.y), 0.0, "WaterTower")
	# bridge + islet shrine
	var ic: Vector2 = L.ISLET_CENTER
	var x0 := ic.x + L.ISLET_RADII.x - 0.6
	var x1 := L.LAKE_CENTER.x + L.LAKE_RADII.x * sqrt(1.0 - pow((ic.y - L.LAKE_CENTER.y) / L.LAKE_RADII.y, 2.0)) + 1.2
	var blen := x1 - x0
	_landmark(["bridge"], func() -> Node3D: return CS.make_bridge(blen, 2.4, 1.1), Vector3((x0 + x1) * 0.5, 0, ic.y), 0.0, "Bridge")
	_landmark(["shrine", "mieu"], func() -> Node3D: return CS.make_shrine(), Vector3(ic.x + 2.5, 0.25, ic.y + 1.5), -PI * 0.5, "IsletShrine")
	report["counts"]["bridge_length"] = blen


func _build_market_stalls() -> void:
	var mh: Rect2 = L.MARKET_HALL
	var kinds := ["veg", "fruit", "dry", "flowers", "veg", "fruit"]
	var n := 0
	# under the hall: 4 rows
	for row in 4:
		var z := mh.position.y + 5.0 + row * 7.5
		var x := mh.position.x + 3.0
		while x < mh.end.x - 3.0:
			var s := CS.make_stall(kinds[(row + int(x)) % kinds.size()], rng, false)
			s.position = Vector3(x, 0, z)
			s.rotation.y = 0.0 if row % 2 == 0 else PI
			grp("Landmarks").add_child(s)
			x += 3.2
			n += 1
	# fish lane (open air, tarps) — cô Hoa's stall is the first one
	var fx := 62.0
	var idx := 0
	while fx < 112.0:
		var s := CS.make_stall("fish" if idx % 3 != 2 else "veg", rng, true)
		s.position = Vector3(fx, 0, L.FISH_LANE_Z - 3.2)
		s.rotation.y = 0.0
		if idx == 0:
			s.name = "FishStall_CoHoa"
			s.set_meta(&"stall", "co_hoa")
		grp("Landmarks").add_child(s)
		var s2 := CS.make_stall(["fruit", "flowers", "dry"][idx % 3], rng, true)
		s2.position = Vector3(fx + 1.5, 0, L.FISH_LANE_Z + 3.2)
		s2.rotation.y = PI
		grp("Landmarks").add_child(s2)
		fx += 4.2
		idx += 1
		n += 2
	report["counts"]["market_stalls"] = n


# =================================================================================================
# nature: street trees, park trees, banyans
# =================================================================================================

func _tree(kind: StringName, pos: Vector3, yaw: float, seed_i: int) -> Node3D:
	var keywords: Array = {&"banyan": ["banyan", "da_"], &"street": ["street_tree", "sau", "xa_cu", "tree"], &"small": ["small_tree", "shrub", "frangipani"], &"park": ["park_tree", "tree"]}.get(kind, ["tree"])
	var e := cat_keyword(["nature"], keywords)
	var n: Node3D
	if not e.is_empty():
		n = instance(str(e["file"]))
	else:
		n = TG.make_tree(kind, seed_i)
		_tree_count += 1
	n.position = pos
	n.rotation.y = yaw
	grp("Nature").add_child(n)
	return n


var temple_banyan: Node3D
var lake_banyan: Node3D


func _build_nature() -> void:
	if cat_keyword(["nature"], ["tree"]).is_empty():
		placeholder("Trees & banyans (procedural, scripts/world/tree_gen.gd)", "no assets/models/nature catalog yet")
	var i := 0
	for p: Vector3 in tree_pits:
		_tree(&"street", p, rng.randf() * TAU, 1000 + i)
		i += 1
	# park ring trees between promenade and streets
	for k in 34:
		var t := TAU * k / 34.0 + rng.randf_range(-0.05, 0.05)
		var q := _ell(t, 1.0)
		var dir := (q - L.LAKE_CENTER).normalized()
		var p := q + dir * (L.PROMENADE_W + rng.randf_range(2.0, 5.0))
		if p.x < -47.0 or p.x > 42.0 or p.y < -47.5 or p.y > 53.0:
			continue
		_tree(&"park" if k % 3 != 0 else &"street", Vector3(p.x, 0, p.y), rng.randf() * TAU, 2000 + k)
	temple_banyan = _tree(&"banyan", Vector3(L.TEMPLE_BANYAN.x, 0, L.TEMPLE_BANYAN.y), 0.6, 77)
	lake_banyan = _tree(&"banyan", Vector3(L.ISLET_CENTER.x - 2.0, 0.25, L.ISLET_CENTER.y - 0.5), 2.1, 4242)
	# small ornamental trees in the temple courtyard & market corners
	for p: Vector2 in [Vector2(24, 88), Vector2(-26, 92), Vector2(14, 74), Vector2(108, 30), Vector2(64, 36)]:
		_tree(&"small", Vector3(p.x, 0, p.y), rng.randf() * TAU, int(p.x * 7 + p.y))
	report["counts"]["procedural_trees"] = _tree_count


# =================================================================================================
# street furniture: lamps, poles, manholes, drains, bins, signs, benches, stall, carts
# =================================================================================================

var poles: Array = []          # [Node3D pole, street id, side]


func _prop(id: String, pos: Vector3, yaw: float, parent: Node3D = null) -> Node3D:
	var e := cat_by_id("props", id)
	if e.is_empty():
		return null
	var n := instance(str(e["file"]))
	if n == null:
		return null
	n.position = pos
	n.rotation.y = yaw
	(parent if parent != null else grp("StreetFurniture")).add_child(n)
	return n


func _build_street_furniture() -> void:
	var sf := grp("StreetFurniture")
	for s: Array in L.STREETS:
		var id: String = s[0]
		var axis: String = s[1]
		var c: float = s[2]
		var hw: float = float(s[5]) * 0.5
		var a0 := maxf(float(s[3]), -118.0)
		var a1 := minf(float(s[4]), 118.0)
		# street lamps alternate sides every ~18 m
		var t := a0 + 7.0
		var side := 1
		while t < a1 - 4.0:
			var off := c + side * (hw + 0.55)
			var pos := Vector3(t, 0, off) if axis == "x" else Vector3(off, 0, t)
			var yaw := (0.0 if side < 0 else PI) if axis == "x" else (PI * 0.5 if side < 0 else -PI * 0.5)
			var lamp_id := "lamp_post_colonial" if id in ["pho_dinh", "pho_ho"] else "lamp_post_modern"
			if _prop(lamp_id, pos, yaw) == null:
				_fallback_lamp(pos)
			t += 18.0
			side = -side
		# electric poles every ~32 m on one side (cable spans between them)
		var pole_side := -1 if id != "pho_dinh" else 1
		t = a0 + 14.0
		var prev_pole: Node3D = null
		while t < a1 - 4.0:
			var off := c + pole_side * (hw + 0.45)
			var pos := Vector3(t, 0, off) if axis == "x" else Vector3(off, 0, t)
			var yaw := PI * 0.5 if axis == "x" else 0.0
			var p := _prop("electric_pole_concrete", pos, yaw)
			if p != null:
				poles.append([p, id, pole_side])
			t += rng.randf_range(28.0, 34.0)
		# manholes in the road, drain grates in the gutter
		t = a0 + 10.0
		while t < a1 - 4.0:
			var mpos := Vector3(t, ROAD_Y, c + rng.randf_range(-1.5, 1.5)) if axis == "x" else Vector3(c + rng.randf_range(-1.2, 1.2), ROAD_Y, t)
			_prop("manhole_cover", mpos, rng.randf() * TAU)
			for sd: float in [-1, 1]:
				var g := c + sd * (hw - 0.22)
				var dpos := Vector3(t + 6.0, ROAD_Y, g) if axis == "x" else Vector3(g, ROAD_Y, t + 6.0)
				_prop("drain_grate", dpos, 0.0 if axis == "x" else PI * 0.5)
			t += rng.randf_range(24.0, 32.0)
		# bins, hydrants, mailboxes, signs along the building side of sidewalks
		t = a0 + 5.0
		while t < a1 - 3.0:
			var sd := -1 if rng.randf() < 0.5 else 1
			var off := c + sd * (hw + float(s[6]) - 0.6)
			var pos := Vector3(t, 0, off) if axis == "x" else Vector3(off, 0, t)
			var yaw := (0.0 if sd < 0 else PI) if axis == "x" else (PI * 0.5 if sd < 0 else -PI * 0.5)
			var choice := rng.randf()
			var pid := "trash_bin_municipal"
			if choice < 0.18:
				pid = "fire_hydrant"
			elif choice < 0.3:
				pid = "mailbox"
			elif choice < 0.5:
				pid = ["sign_aframe_com", "sign_aframe_cafe", "sign_lightbox", "banner_standing"][rng.randi_range(0, 3)]
			elif choice < 0.62:
				pid = "bicycle_rack"
			elif choice < 0.75:
				pid = "gas_cylinder"
			_prop(pid, pos, yaw + rng.randf_range(-0.2, 0.2))
			t += rng.randf_range(7.0, 14.0)
	# roadwork corner on Phố Hồ
	_prop("construction_barrier", Vector3(-54.0, ROAD_Y, 20.0), PI * 0.5)
	_prop("traffic_cone", Vector3(-54.0, ROAD_Y, 18.6), 0.0)
	_prop("traffic_cone", Vector3(-54.6, ROAD_Y, 21.6), 0.4)
	_prop("cable_drum", Vector3(-50.3, 0, 23.0), 0.3)
	# lake benches
	for k in 14:
		var tt := TAU * (k + 0.5) / 14.0
		var q := _ell(tt, 1.0)
		var dir := (q - L.LAKE_CENTER).normalized()
		var p := q + dir * (L.PROMENADE_W - 0.6)
		var b := CS.make_bench(1.8)
		b.position = Vector3(p.x, 0.01, p.y)
		b.rotation.y = atan2(-dir.x, -dir.y)
		sf.add_child(b)
	# Grandma Tư's tea stall at hẻm A's north mouth (on the main-street south sidewalk)
	var stall := CS.make_tea_stall()
	stall.name = "TeaStall"
	stall.position = Vector3(-87.4, 0.0, -64.3)
	stall.rotation.y = PI
	sf.add_child(stall)
	# chú Sáu's bánh mì cart on Phố Hàng Mây (north sidewalk)
	var cart := CS.make_banh_mi_cart()
	cart.position = Vector3(18.0, 0.0, -75.3)
	cart.rotation.y = 0.0
	sf.add_child(cart)
	# Bông's café terrace (rattan chairs) at the corner café (Phố Chợ × Hàng Mây)
	for k in 6:
		var ch := CS.make_rattan_chair()
		ch.name = "CafeChair_%d" % k
		ch.position = Vector3(58.5 + (k % 3) * 1.1, 0, -64.6 - (k / 3) * 1.0)
		ch.rotation.y = rng.randf_range(-0.6, 0.6) + (PI if k / 3 == 1 else 0.0)
		sf.add_child(ch)
	# parked scooters / bicycles from the vehicles catalog (if any)
	var bikes := cat_find("vehicles", func(e: Dictionary) -> bool: return str(e.get("id", "")).contains("scooter") or str(e.get("id", "")).contains("bike") or str(e.get("kind", "")) in ["scooter", "bicycle", "motorbike"])
	if not bikes.is_empty():
		var n := 0
		for s: Array in L.STREETS:
			var axis: String = s[1]
			var c: float = s[2]
			var hw: float = float(s[5]) * 0.5
			var t := float(s[3]) + 9.0
			while t < float(s[4]) - 9.0 and n < 90:
				if rng.randf() < 0.55:
					var e: Dictionary = bikes[rng.randi_range(0, bikes.size() - 1)]
					var sd := 1 if rng.randf() < 0.5 else -1
					var off := c + sd * (hw + 1.0)
					var pos := Vector3(t, 0, off) if axis == "x" else Vector3(off, 0, t)
					var yaw := (PI * 0.5 if axis == "x" else 0.0) + rng.randf_range(-0.25, 0.25) + (PI if rng.randf() < 0.5 else 0.0)
					var b := instance(str(e["file"]))
					b.position = pos
					b.rotation.y = yaw
					sf.add_child(b)
					n += 1
				t += rng.randf_range(2.2, 6.0)
		report["counts"]["parked_vehicles"] = n
	else:
		placeholder("Parked scooters", "no vehicles catalog yet — streets have none until vehicles-nature delivers (rebuild picks them up)")


func _fallback_lamp(pos: Vector3) -> void:
	var l := OmniLight3D.new()
	l.position = pos + Vector3(0, 4.2, 0)
	l.omni_range = 12.0
	l.light_energy = 1.6
	l.light_color = Color(1.0, 0.78, 0.5)
	l.add_to_group(&"street_lamp")
	grp("Lights").add_child(l)


# =================================================================================================
# festival lanterns (shown on the festival night by NightLights)
# =================================================================================================

func _build_festival() -> void:
	var fg := grp("Festival")
	fg.add_to_group(&"festival_lantern")
	var spans := 0
	for s: Array in L.STREETS:
		if not s[0] in ["pho_hang_may", "pho_dinh"]:
			continue
		var c: float = s[2]
		var half := float(s[5]) * 0.5 + float(s[6]) - 0.3
		var x := -110.0
		while x < 110.0:
			var a := Vector3(x, 5.4, c - half)
			var b := Vector3(x + rng.randf_range(-1.5, 1.5), 5.6, c + half)
			var ls := CS.make_lantern_string(a, b, 9, rng)
			fg.add_child(ls)
			if spans % 3 == 0:
				var l := OmniLight3D.new()
				l.name = "LanternGlow"
				l.position = (a + b) * 0.5 + Vector3(0, -0.8, 0)
				l.omni_range = 9.0
				l.light_energy = 1.3
				l.light_color = Color(1.0, 0.55, 0.3)
				l.shadow_enabled = false
				l.distance_fade_enabled = true
				l.distance_fade_begin = 70.0
				l.add_to_group(&"festival_lantern")
				fg.add_child(l)
			spans += 1
			x += rng.randf_range(7.0, 10.0)
	# lantern strings across the temple courtyard
	for k in 5:
		var z := 72.0 + k * 3.5
		fg.add_child(CS.make_lantern_string(Vector3(-30, 4.2, z), Vector3(30, 4.2, z + 1.0), 18, rng))
	report["counts"]["lantern_spans"] = spans


# =================================================================================================
# decals
# =================================================================================================

func _decal(tex: String, pos: Vector3, size: Vector3, basis: Basis, group: StringName = &"", normal: String = "") -> Decal:
	var d := Decal.new()
	d.texture_albedo = load("res://assets/textures/decals/%s.png" % tex)
	if normal != "":
		d.texture_normal = load("res://assets/textures/decals/%s.png" % normal)
	d.size = size
	d.transform = Transform3D(basis, pos)
	d.distance_fade_enabled = true
	d.distance_fade_begin = 45.0
	d.distance_fade_length = 10.0
	d.cull_mask = 1
	d.upper_fade = 0.3
	d.lower_fade = 0.3
	if group != &"":
		d.add_to_group(group)
	grp("Decals").add_child(d)
	return d


func _ground_spot(on_road: bool) -> Vector3:
	var s: Array = L.STREETS[rng.randi_range(0, L.STREETS.size() - 1)]
	var axis: String = s[1]
	var c: float = s[2]
	var hw := float(s[5]) * 0.5
	var t := rng.randf_range(maxf(float(s[3]), -115.0), minf(float(s[4]), 115.0))
	var off: float
	if on_road:
		off = c + rng.randf_range(-hw + 0.5, hw - 0.5)
	else:
		var sd := 1 if rng.randf() < 0.5 else -1
		off = c + sd * (hw + rng.randf_range(0.4, float(s[6]) - 0.3))
	var y := ROAD_Y if on_road else 0.0
	return Vector3(t, y, off) if axis == "x" else Vector3(off, y, t)


func _build_decals() -> void:
	var up := Basis(Vector3.UP, 0.0)
	for i in 34:
		var p := _ground_spot(true)
		_decal(["oil_stain_a", "oil_stain_b"][i % 2], p, Vector3(rng.randf_range(0.8, 2.2), 0.5, rng.randf_range(0.8, 2.2)), Basis(Vector3.UP, rng.randf() * TAU))
	for i in 26:
		var p := _ground_spot(true)
		_decal(["crack_a", "crack_b", "crack_c"][i % 3], p, Vector3(rng.randf_range(1.5, 3.0), 0.5, rng.randf_range(1.5, 3.0)), Basis(Vector3.UP, rng.randf() * TAU), &"", ["crack_a_normal", "crack_b_normal", "crack_c_normal"][i % 3])
	for i in 24:
		var p := _ground_spot(false)
		_decal(["stain_damp", "stain_food", "stain_rust", "crack_b"][i % 4], p, Vector3(rng.randf_range(0.6, 1.4), 0.4, rng.randf_range(0.6, 1.4)), Basis(Vector3.UP, rng.randf() * TAU))
	for i in 10:
		var p := _ground_spot(true)
		_decal("tire_marks", p, Vector3(1.6, 0.4, rng.randf_range(3.0, 5.0)), Basis(Vector3.UP, rng.randf_range(-0.2, 0.2) + (0.0 if i % 2 == 0 else PI * 0.5)))
	# leaves under trees
	for n in grp("Nature").get_children():
		var r := float(n.get_meta(&"canopy_radius", 3.0)) * 0.6
		for k in 2:
			var off := Vector3(rng.randf_range(-r, r), 0, rng.randf_range(-r, r))
			_decal(["leaves_a", "leaves_b"][k], (n as Node3D).position + off, Vector3(r, 0.6, r), Basis(Vector3.UP, rng.randf() * TAU), &"", ["leaves_a_normal", "leaves_b_normal"][k])
	# puddles: only visible when wet (WeatherSystem fades them in)
	for i in 70:
		var on_road := rng.randf() < 0.6
		var p := _ground_spot(on_road)
		_decal(["puddle_a", "puddle_b"][i % 2], p, Vector3(rng.randf_range(0.8, 2.6), 0.3, rng.randf_range(0.8, 2.0)), Basis(Vector3.UP, rng.randf() * TAU), &"puddle_decal")
	for i in 16:
		var p := Vector3(rng.randf_range(-90.5, -89.5), 0.0, rng.randf_range(-55, 50))
		_decal(["puddle_a", "puddle_b"][i % 2], p, Vector3(0.9, 0.3, rng.randf_range(1.0, 2.2)), Basis(Vector3.UP, rng.randf_range(-0.2, 0.2)), &"puddle_decal")
	# chalk drawings: hẻm A and the lake promenade
	_decal("chalk_hopscotch", Vector3(-90.0, 0.0, 22.0), Vector3(1.9, 0.4, 1.9), Basis(Vector3.UP, PI * 0.5))
	var pq := _ell(PI * 0.5) + Vector2(0, 2.5)
	_decal("chalk_hopscotch", Vector3(pq.x, 0.01, pq.y), Vector3(2.4, 0.4, 2.4), Basis(Vector3.UP, 0.2))
	# posters on facades
	var posters := ["poster_rent", "poster_lost_cat", "poster_festival", "poster_lessons"]
	var k := 0
	for m: Dictionary in placed:
		if rng.randf() > 0.12:
			continue
		var xf: Transform3D = m["xf"]
		var basis: Basis = xf.basis
		var x := rng.randf_range(-float(m["w"]) * 0.35, float(m["w"]) * 0.35)
		var pos := xf.origin + basis.x * x + basis.z * 0.12 + Vector3(0, rng.randf_range(1.5, 2.1), 0)
		var db := basis * Basis(Vector3.RIGHT, PI * 0.5) * Basis(Vector3.UP, rng.randf_range(-0.06, 0.06))
		_decal(posters[k % posters.size()], pos, Vector3(0.48, 0.5, 0.66), db)
		k += 1
	report["counts"]["decals"] = grp("Decals").get_child_count()


# =================================================================================================
# markers: PlayerSpawn, locations, npc spawns, patrol/traffic paths, POIs, quest targets
# =================================================================================================

var cam_nap_pos := Vector3.ZERO


func _marker(name: String, pos: Vector3, group: StringName, meta: Dictionary, yaw: float = 0.0, parent: Node3D = null) -> Marker3D:
	var m := Marker3D.new()
	m.name = name
	m.position = pos
	m.rotation.y = yaw
	if group != &"":
		m.add_to_group(group)
	for k: String in meta:
		m.set_meta(StringName(k), meta[k])
	(parent if parent != null else grp("Markers")).add_child(m)
	return m


func module_world_points(m: Dictionary, key: String) -> Array:
	var out: Array = []
	var xf: Transform3D = m["xf"]
	for p: Variant in (m["entry"] as Dictionary).get(key, []):
		if p is Array and (p as Array).size() >= 3:
			out.append(xf * Vector3(float(p[0]), float(p[1]), float(p[2])))
	return out


## Highest catalog nap spot on the module nearest `near` (rooftop of Cam's home building).
func _rooftop_nap_near(near: Vector3, rows: Array) -> Vector3:
	var best := Vector3.INF
	var best_d := INF
	for m: Dictionary in placed:
		if not str(m["row"]) in rows:
			continue
		var o: Vector3 = (m["xf"] as Transform3D).origin
		var d := Vector2(o.x - near.x, o.z - near.z).length()
		if d > 12.0:
			continue
		for p: Vector3 in module_world_points(m, "nap_spots"):
			if p.y < 5.0:
				continue
			var score := d - p.y * 0.05
			if score < best_d:
				best_d = score
				best = p
	return best


func _build_markers() -> void:
	var mk := grp("Markers")
	# --- player spawn: Cam's rooftop nap spot above the tea stall ---
	cam_nap_pos = _rooftop_nap_near(Vector3(-84.0, 0, -58.0), ["main_south_w"])
	if cam_nap_pos == Vector3.INF:
		cam_nap_pos = Vector3(-84.0, 10.0, -58.0)
		report["warnings"].append("no rooftop nap spot near the tea stall; spawn fallback")
	_marker("PlayerSpawn", cam_nap_pos + Vector3(0, 0.05, 0), &"player_spawn", {"spot_id": "cam_rooftop"}, PI)
	# --- locations ---
	for l: Array in L.LOCATIONS:
		var pos := Vector3(float(l[2]), float(l[3]), float(l[4]))
		if l[0] == "water_tower" and water_tower != null:
			pos = water_tower.position + Vector3(0, float(water_tower.get_meta(&"catwalk_y", 13.6)) + 0.1, 3.5)
		if l[0] == "temple_roof" and temple_hall != null:
			pos = temple_hall.position + Vector3(0, float(temple_hall.get_meta(&"roof_ridge_y", 9.7)), 0)
		_marker("Loc_" + str(l[0]), pos, &"location", {"location_id": str(l[0]), "display_name_key": str(l[1]), "radius": float(l[5])})
	# --- npc spawns ---
	var npcs := [
		["ba_tu", "vendor", Vector3(-87.4, 0, -63.6), PI],
		["mun", "cat", cam_nap_pos + Vector3(14.0, 0.0, 0.0), 0.0],
		["bong", "cat", Vector3(57.6, 0, -62.4), PI],
		["ong_muop", "cat", Vector3(4.0, 0.8, 82.5), PI],
		["lao_qua", "crow", lake_banyan.position + Vector3(0, 4.5, 0) if lake_banyan != null else Vector3(14, 4, 2), 0.0],
		["ven", "dog", Vector3(80.0, 0, -4.0), 0.0],
		["co_hoa", "vendor", Vector3(62.0, 0, L.FISH_LANE_Z - 4.4), 0.0],
		["chu_sau", "vendor", Vector3(18.0, 0, -76.1), 0.0],
		["bin", "pedestrian", Vector3(-89.8, 0, 18.0), PI * 0.5],
		["xam", "pigeon_flock", Vector3(-2.0, 0.0, -27.5), 0.0],
	]
	for n: Array in npcs:
		var meta := {"npc_kind": str(n[1]), "npc_id": str(n[0])}
		if n[0] == "ong_muop":
			meta["npc_alias"] = "muop"
		_marker("NPC_" + str(n[0]), n[2], &"npc_spawn", meta, n[3])
	# generic spawns: pedestrians, pigeons, koi, mice, cats, crows
	var generic := [
		["pedestrian", 26], ["pigeon_flock", 5], ["koi", 6], ["mouse", 6], ["cat", 4], ["crow", 3],
	]
	for g: Array in generic:
		for i in int(g[1]):
			var pos := _generic_spawn(str(g[0]), i)
			_marker("Spawn_%s_%02d" % [g[0], i], pos, &"npc_spawn", {"npc_kind": str(g[0]), "npc_id": ""}, rng.randf() * TAU)
	# --- Vện's patrol through the market ---
	var patrol := Path3D.new()
	patrol.name = "Patrol_ven"
	patrol.add_to_group(&"patrol_path")
	patrol.set_meta(&"npc_id", "ven")
	var curve := Curve3D.new()
	for p: Vector3 in [Vector3(80, 0, -4), Vector3(100, 0, -4), Vector3(104, 0, 6), Vector3(108, 0, 8), Vector3(62, 0, 8),
			Vector3(60, 0, -10), Vector3(66, 0, -46), Vector3(98, 0, -46), Vector3(102, 0, -20), Vector3(80, 0, -4)]:
		curve.add_point(p)
	patrol.curve = curve
	mk.add_child(patrol)
	# Mun's rooftop patrol (north row roofs) is generated after rooftop measurement (post_physics).
	# --- traffic lanes (one per direction per street) ---
	for s: Array in L.STREETS:
		var axis: String = s[1]
		var c: float = s[2]
		var hw := float(s[5]) * 0.5
		for dir: float in [-1, 1]:
			var lane := Path3D.new()
			lane.name = "Lane_%s_%s" % [s[0], "a" if dir > 0 else "b"]
			lane.add_to_group(&"traffic_lane")
			lane.set_meta(&"vehicle_kinds", PackedStringArray(s[8]))
			lane.set_meta(&"speed_limit", float(s[7]))
			lane.set_meta(&"street_id", str(s[0]))
			var lc := Curve3D.new()
			var off := c + dir * hw * 0.45 * (1 if axis == "x" else -1)
			var a0 := float(s[3]) + 4.0
			var a1 := float(s[4]) - 4.0
			var pts: Array[Vector3] = []
			var n := int((a1 - a0) / 10.0)
			for i in n + 1:
				var t := a0 + (a1 - a0) * float(i) / n
				pts.append(Vector3(t, ROAD_Y + 0.02, off) if axis == "x" else Vector3(off, ROAD_Y + 0.02, t))
			if dir < 0:
				pts.reverse()
			for p in pts:
				lc.add_point(p)
			lane.curve = lc
			mk.add_child(lane)
	# --- pedestrian points of interest ---
	var pois := [
		["sit", Vector3(-87.4, 0, -62.2)], ["sit", Vector3(-86.7, 0, -62.0)], ["shop", Vector3(18.0, 0, -74.4)],
		["chat", Vector3(-30.0, 0, -75.5)], ["wait", Vector3(-55.0, 0, -64.5)], ["look", Vector3(0.0, 0, -26.5)],
		["sit", Vector3(58.6, 0, -64.6)], ["sit", Vector3(59.7, 0, -64.6)], ["shop", Vector3(70.0, 0, L.FISH_LANE_Z)],
		["shop", Vector3(85.0, 0, -20.0)], ["shop", Vector3(76.0, 0, -32.0)], ["chat", Vector3(92.0, 0, L.FISH_LANE_Z)],
		["look", Vector3(30.5, 0, 2.0)], ["look", Vector3(0.0, 0, 76.0)], ["chat", Vector3(-20.0, 0, 67.0)],
		["wait", Vector3(48.0, 0, 64.5)], ["look", Vector3(-35.0, 0, 30.0)], ["sit", Vector3(-30.0, 0, -32.0)],
		["chat", Vector3(-90.0, 0, -30.0)], ["look", Vector3(10.0, 0, 76.5)],
	]
	for i in pois.size():
		_marker("POI_%02d_%s" % [i, pois[i][0]], pois[i][1], &"pedestrian_poi", {"activity": str(pois[i][0])})
	# --- quest targets ---
	var hall_roof := temple_hall.position + Vector3(0, float(temple_hall.get_meta(&"roof_ridge_y", 9.7)) + 0.35, 0) if temple_hall != null else Vector3(0, 10, 90)
	var qts := [
		["tea_stall", Vector3(-87.4, 0.9, -64.3)], ["stall_counter", Vector3(-87.4, 0.95, -64.3)],
		["crow_nest", hall_roof + Vector3(5.0, 0.2, 0.0)], ["temple_roof", hall_roof],
		["fish_stall", Vector3(62.0, 0.85, L.FISH_LANE_Z - 3.2)],
		["water_tower", water_tower.position + Vector3(0, float(water_tower.get_meta(&"catwalk_y", 13.6)) + 0.1, 3.5) if water_tower != null else Vector3(-112, 14, -30)],
		["bins_key_spot", Vector3(-104.5, 0.05, -10.0)], ["leg_band_spot", Vector3(12.0, 0.3, 75.0)],
		["postman_bag", Vector3(34.6, 0.05, -76.0)], ["race_start", cam_nap_pos + Vector3(6.0, 0, 0)],
		["race_finish", hall_roof + Vector3(-6.0, 0, 0)], ["banyan", lake_banyan.position + Vector3(0, 0.1, 1.6) if lake_banyan != null else Vector3(14, 0.3, 3)],
		["cafe", Vector3(57.6, 0.0, -62.0)], ["market", Vector3(82.0, 0, -25.0)],
	]
	for q: Array in qts:
		_marker("QT_" + str(q[0]), q[1], &"quest_target", {"target_id": str(q[0])})


func _generic_spawn(kind: String, i: int) -> Vector3:
	match kind:
		"pedestrian":
			return _ground_spot(false)
		"pigeon_flock":
			return [Vector3(0, 0, -28), Vector3(0, 0, 74), Vector3(-30, 0, 30), Vector3(84, 0, -1), Vector3(-60, 0, -72)][i % 5]
		"koi":
			var q := _ell(TAU * i / 6.0, 0.6)
			return Vector3(q.x, L.LAKE_WATER_Y - 0.4, q.y)
		"mouse":
			return [Vector3(-90.2, 0, -40), Vector3(-110, 0, -12), Vector3(-90.4, 0, 30), Vector3(70, 0, 6.0), Vector3(96, 0, -44), Vector3(-108, 0, -40)][i % 6]
		"cat":
			return [Vector3(-90, 0, 0), Vector3(-40, 0, -70.5), Vector3(100, 0, 64), Vector3(-25, 0, 90)][i % 4]
		"crow":
			return [Vector3(0, 11, 90), Vector3(-19, 9, 81), Vector3(14, 8, 2)][i % 3]
	return Vector3.ZERO


# =================================================================================================
# interactables (systems classes): naps, territory, memories, caps, food, scratch, knockables
# =================================================================================================

func _ia(script_path: String, name: String, pos: Vector3, props: Dictionary, parent: Node3D = null) -> Node3D:
	if not ResourceLoader.exists(script_path):
		return null
	var n := Area3D.new()
	n.set_script(load(script_path))
	n.name = name
	n.position = pos
	for k: String in props:
		n.set(StringName(k), props[k])
	(parent if parent != null else grp("Interactables")).add_child(n)
	return n


func _roof_points(rows: Array, min_y: float = 5.0) -> Array:
	var out: Array = []
	for m: Dictionary in placed:
		if not rows.is_empty() and not str(m["row"]) in rows:
			continue
		for p: Vector3 in module_world_points(m, "nap_spots"):
			if p.y >= min_y:
				out.append(p)
	return out


func _build_interactables() -> void:
	var S := "res://scripts/systems/"
	# ---- nap spots (8) ----
	var naps := [
		["cam_rooftop", cam_nap_pos, {"sleep_hours": 2.0, "comfort": 1.2}],
		["tea_stall_cushion", Vector3(-87.4, 0.17, -64.3), {"sleep_hours": 2.0, "comfort": 1.4, "warmth_bonus": 10.0}],
		["temple_veranda", Vector3(-6.0, 0.8, 84.6), {"sleep_hours": 3.0}],
		["banyan_roots", lake_banyan.position + Vector3(1.2, 0.05, 1.0) if lake_banyan != null else Vector3(15, 0.3, 3), {"sleep_hours": 2.0, "sheltered": true}],
		["market_rice_sacks", Vector3(66.0, 0.85, -40.0), {"sleep_hours": 2.0, "sheltered": true}],
		["cafe_window", Vector3(59.6, 0.05, -65.4), {"sleep_hours": 1.5, "comfort": 1.3}],
		["muop_secret_nap", Vector3(L.BELL_PAVILION.x, 3.6, L.BELL_PAVILION.y), {"sleep_hours": 3.0, "comfort": 1.6, "sheltered": true}],
	]
	var roof_naps := _roof_points(["hem_a_w_n", "hem_a_e_s", "pho_ho_w", "main_north"], 6.0)
	if not roof_naps.is_empty():
		naps.append(["sunny_rooftop", roof_naps[rng.randi_range(0, roof_naps.size() - 1)], {"sleep_hours": 2.0, "sheltered": false}])
	for n: Array in naps:
		var props: Dictionary = n[2]
		props["spot_id"] = StringName(n[0])
		_ia(S + "nap_spot.gd", "Nap_" + str(n[0]), n[1], props)
	# ---- territory spots (10) ----
	var terr: Array = []
	var roof_all := _roof_points(["main_south_w", "main_north", "hem_a_w_n", "hem_a_w_s", "hem_a_e_n", "hem_a_e_s", "pho_ho_w", "dinh_north_w"], 6.0)
	roof_all.shuffle()
	for i in mini(5, roof_all.size()):
		terr.append(["roof_%02d" % (i + 1), roof_all[i]])
	terr.append(["alley_corner", Vector3(-90.0, 0.0, -5.0)])
	terr.append(["tower_base", Vector3(L.WATER_TOWER_POS.x + 2.8, 0.0, L.WATER_TOWER_POS.y)])
	terr.append(["temple_wall", Vector3(-33.8, 2.4, 80.0)])
	terr.append(["market_crates", Vector3(101.5, 0.0, -44.0)])
	terr.append(["lake_bench", Vector3(_ell(1.0).x + 3.0, 0.0, _ell(1.0).y + 3.0)])
	for t: Array in terr:
		_ia(S + "territory_spot.gd", "Territory_" + str(t[0]), t[1], {"spot_id": StringName(t[0]), "faction": &"rooftop_cats"})
	report["counts"]["territory_spots"] = terr.size()
	# ---- memories (12 old photographs) ----
	var mem_spots := [
		Vector3(-87.9, 0.13, -64.4), Vector3(-112.0, 0.05, -30.5), Vector3(-90.3, 0.05, 35.0), Vector3(-4.0, 0.8, 85.0),
		Vector3(L.ISLET_CENTER.x + 2.5, 0.75, L.ISLET_CENTER.y + 2.5), Vector3(-30.0, 0.45, 70.3), Vector3(76.0, 0.83, -37.0),
		Vector3(110.0, 0.05, 50.0), Vector3(30.0, 0.05, -48.0), Vector3(-58.8, 0.05, -10.0), Vector3(118.0, 0.05, -50.0),
	]
	if not roof_naps.is_empty():
		mem_spots.append(roof_naps[roof_naps.size() / 2])
	else:
		mem_spots.append(Vector3(-100.0, 0.05, 0.0))
	for i in mem_spots.size():
		var id := "memory_%02d" % (i + 1)
		_ia(S + "collectible.gd", "Memory_%02d" % (i + 1), mem_spots[i], {"collectible_id": StringName(id), "kind": &"memory"})
	# ---- bottle caps (30 stashes) ----
	var caps: Array = []
	for i in 18:
		caps.append(_ground_spot(false) + Vector3(0, 0.03, 0))
	var roofs := _roof_points([], 5.0)
	roofs.shuffle()
	for i in mini(8, roofs.size()):
		caps.append(roofs[i] + Vector3(0.3, 0.02, 0.2))
	for p: Vector3 in [Vector3(-90.0, 0.03, -50.0), Vector3(-105.0, 0.03, -5.0), Vector3(84.0, 0.03, 4.0), Vector3(-12.0, 0.03, 74.0)]:
		caps.append(p)
	while caps.size() < 30:
		caps.append(_ground_spot(false) + Vector3(0, 0.03, 0))
	for i in caps.size():
		_ia(S + "collectible.gd", "Caps_%02d" % i, caps[i], {"collectible_id": StringName("caps_%02d" % i), "kind": &"caps",
			"amount": 1 + (i % 3), "auto_collect_on_touch": true})
	report["counts"]["cap_stashes"] = caps.size()
	# ---- food & water ----
	_ia(S + "food_source.gd", "Food_GrandmaBowl", Vector3(-86.6, 0.02, -63.4), {"source_id": &"grandma_bowl", "food_amount": 40.0, "servings": 2, "refill_hours": 8.0, "owner_npc_id": &"ba_tu"})
	_ia(S + "food_source.gd", "Food_FishStall", Vector3(62.0, 0.85, L.FISH_LANE_Z - 3.2), {"source_id": &"fish_stall", "gives_item": &"fish", "is_stealing": true, "owner_npc_id": &"co_hoa", "food_amount": 30.0})
	_ia(S + "food_source.gd", "Food_BanhMi", Vector3(18.0, 0.02, -74.6), {"source_id": &"banh_mi_crumbs", "food_amount": 15.0, "servings": 3, "refill_hours": 6.0, "owner_npc_id": &"chu_sau"})
	var lake_drink := _lake_step_pos(-0.9)
	_ia(S + "food_source.gd", "Water_Lake", lake_drink, {"source_id": &"lake_water", "is_water": true, "food_amount": 0.0, "servings": 99, "verb": &"drink"})
	_ia(S + "food_source.gd", "Water_TempleBasin", Vector3(-8.0, 0.0, 77.0), {"source_id": &"temple_basin", "is_water": true, "food_amount": 0.0, "servings": 99, "verb": &"drink"})
	_ia(S + "food_source.gd", "Food_MarketScraps", Vector3(98.0, 0.02, -46.5), {"source_id": &"market_scraps", "food_amount": 20.0, "servings": 2, "refill_hours": 12.0})
	# ---- scratch posts ----
	if temple_banyan != null:
		_ia(S + "scratch_post.gd", "Scratch_TempleBanyan", temple_banyan.position + Vector3(0, 0.3, 1.25), {"post_id": &"temple_banyan", "marks_territory": true})
	if lake_banyan != null:
		_ia(S + "scratch_post.gd", "Scratch_LakeBanyan", lake_banyan.position + Vector3(0, 0.3, 1.25), {"post_id": &"lake_banyan"})
	_ia(S + "scratch_post.gd", "Scratch_CafeChair", Vector3(58.5, 0.15, -64.6), {"post_id": &"cafe_rattan"})
	_ia(S + "scratch_post.gd", "Scratch_StallLeg", Vector3(-86.8, 0.15, -64.1), {"post_id": &"tea_stall_leg"})
	# ---- story interactables ----
	_ia(S + "interactable.gd", "Sniff_StallCounter", Vector3(-87.4, 0.95, -64.3), {"verb": &"sniff", "target_id": &"stall_counter", "interact_distance": 1.4})
	var nest := hall_roof_pos() + Vector3(5.0, 0.2, 0.0)
	var nest_node := Node3D.new()
	nest_node.name = "CrowNest"
	nest_node.position = nest
	grp("Landmarks").add_child(nest_node)
	_crow_nest_visual(nest_node)
	var fest := {"quest": "main_05_festival_night", "state": "active"}
	_ia(S + "pickup_item.gd", "Pickup_Figurine", nest + Vector3(0, 0.12, 0), {"item_id": &"lucky_cat_figurine", "requirement": fest, "show_when_locked": false, "target_id": &"crow_nest"})
	_ia(S + "pickup_item.gd", "Pickup_HairClip", nest + Vector3(0.25, 0.1, 0.15), {"item_id": &"hair_clip", "requirement": fest, "show_when_locked": false})
	_ia(S + "pickup_item.gd", "Pickup_BinsKey", Vector3(-104.5, 0.05, -10.0), {"item_id": &"key", "target_id": &"bins_key_spot"})
	_ia(S + "pickup_item.gd", "Pickup_LegBand", Vector3(12.0, 0.3, 75.0), {"item_id": &"leg_band", "target_id": &"leg_band_spot"})
	_ia(S + "pickup_item.gd", "Pickup_Letter", Vector3(34.6, 0.05, -76.0), {"item_id": &"letter", "target_id": &"postman_bag"})
	_ia(S + "quest_trigger.gd", "Trigger_RaceStart", cam_nap_pos + Vector3(6.0, 0.0, 0.0), {"event": &"reach_location", "location_id": &"race_start", "target_id": &"race_start", "discover_location": false})
	_ia(S + "quest_trigger.gd", "Trigger_TempleRoof", hall_roof_pos(), {"event": &"reach_location", "location_id": &"temple_roof", "box_size": Vector3(10.0, 3.0, 4.0)})
	# ---- knockable objects (~25) ----
	_build_knockables()


func hall_roof_pos() -> Vector3:
	if temple_hall != null:
		return temple_hall.position + Vector3(0, float(temple_hall.get_meta(&"roof_ridge_y", 9.7)) + 0.5, 0)
	return Vector3(0, 10, 90)


func _lake_step_pos(t: float) -> Vector3:
	var p := _ell(t)
	var inward := (L.LAKE_CENTER - p).normalized()
	var q := p + inward * 1.25
	return Vector3(q.x, -0.36, q.y)


func _crow_nest_visual(parent: Node3D) -> void:
	var k := CS.Kit.new(parent)
	var twig := WM.flat("twigs", Color(0.32, 0.24, 0.16), 0.9)
	for i in 40:
		var a := rng.randf() * TAU
		var r := rng.randf_range(0.18, 0.32)
		var p0 := Vector3(cos(a) * r, rng.randf_range(0.0, 0.12), sin(a) * r)
		var p1 := p0 + Vector3(rng.randf_range(-0.25, 0.25), rng.randf_range(-0.03, 0.05), rng.randf_range(-0.25, 0.25))
		MU.tube(k.st(twig), PackedVector3Array([p0, p1]), PackedFloat32Array([0.008, 0.006]), 3)
	var glint := WM.flat("nest_glint", Color(0.85, 0.75, 0.4), 0.2, 1.0)
	k.box(glint, Transform3D(Basis(Vector3.UP, 0.4), Vector3(0.05, 0.06, -0.05)), Vector3(0.05, 0.005, 0.03), 1.0)
	k.box(WM.flat("foil", Color(0.8, 0.8, 0.82), 0.15, 1.0), Transform3D(Basis(Vector3.UP, 1.2), Vector3(-0.08, 0.07, 0.04)), Vector3(0.06, 0.004, 0.05), 1.0)
	k.col(&"wood", Transform3D(Basis(), Vector3(0, 0.05, 0)), Vector3(0.7, 0.12, 0.7))
	k.finish("Nest")


func _build_knockables() -> void:
	var spots: Array = []
	# tea stall table & counter
	spots.append(["cup", Vector3(-87.2, 0.44, -65.25), "ceramic"])
	spots.append(["cup", Vector3(-87.55, 0.44, -65.2), "ceramic"])
	spots.append(["glass", Vector3(-87.0, 0.945, -64.15), "glass"])
	# café terrace tables & window sill
	spots.append(["cup", Vector3(59.0, 0.32, -64.6), "ceramic"])
	spots.append(["glass", Vector3(60.1, 0.32, -64.6), "glass"])
	# market stall tables
	for i in 4:
		spots.append(["can", Vector3(67.0 + i * 6.4, 0.81, L.MARKET_HALL.position.y + 5.3), "metal"])
	# temple: incense pot & offering bowls on the altar wall ledge / wall coping
	spots.append(["bowl", Vector3(-33.8, 2.42, 76.0), "ceramic"])
	spots.append(["pot", Vector3(33.8, 2.42, 84.0), "ceramic"])
	# flower pots on rooftop parapets (from module nap spots high up)
	var roofs := _roof_points(["main_south_w", "main_north", "hem_a_w_n", "hem_a_e_s", "pho_ho_w"], 6.0)
	roofs.shuffle()
	for i in mini(10, roofs.size()):
		spots.append(["pot", roofs[i] + Vector3(-0.35, 0.0, 0.0), "ceramic"])
	# bins & bottles on the street
	for i in 4:
		spots.append(["bottle", _ground_spot(false) + Vector3(0, 0.0, 0), "glass"])
	var n := 0
	for s: Array in spots:
		var node := _knockable(str(s[0]), str(s[2]), n)
		if node == null:
			continue
		node.position = s[1]
		grp("Interactables").add_child(node)
		n += 1
	# household bins (catalog prop) stand in the alleys
	for p: Vector3 in [Vector3(-90.4, 0, -12.0), Vector3(-89.6, 0, 26.0), Vector3(-108.5, 0, -8.0)]:
		_prop("trash_bin_household", p, rng.randf() * TAU)
	report["counts"]["knockables"] = n


func _knockable(kind: String, material_kind: String, idx: int) -> Node3D:
	var path := "res://scenes/props/knock_%s.tscn" % kind
	if not ResourceLoader.exists(path):
		return null
	var n := (load(path) as PackedScene).instantiate() as Node3D
	n.name = "Knock_%s_%02d" % [kind, idx]
	n.set(&"object_id", StringName("knock_%s_%02d" % [kind, idx]))
	n.set(&"material_kind", StringName(material_kind))
	return n


# =================================================================================================
# zones: area ids (ambience/reverb), shelters
# =================================================================================================

func _zone(id: String, center: Vector3, size: Vector3, reverb: String = "", amount: float = 0.0, fallback: String = "") -> void:
	var a := Area3D.new()
	a.name = "Zone_" + id
	a.set_script(load("res://scripts/world/area_zone.gd"))
	a.set(&"area_id", StringName(id))
	a.set(&"fallback_area_id", StringName(fallback))
	if reverb != "":
		a.reverb_bus_enabled = true
		a.reverb_bus_name = StringName(reverb)
		a.reverb_bus_amount = amount
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	a.add_child(cs)
	a.position = center
	grp("Zones").add_child(a)


func _build_zones() -> void:
	_zone("pho_hang_may", Vector3(0, 4, -70), Vector3(250, 8, 14))
	_zone("pho_dinh", Vector3(0, 4, 62), Vector3(250, 8, 14))
	_zone("pho_ho", Vector3(-55, 4, -4), Vector3(12, 8, 118))
	_zone("pho_cho", Vector3(50, 4, -4), Vector3(12, 8, 118))
	_zone("hem_maze", Vector3(-90, 4, -4), Vector3(58, 8, 116), "Alley", 0.45)
	_zone("ho_guong", Vector3(-2, 4, 4), Vector3(92, 8, 100))
	_zone("cho_hang_may", Vector3(88, 4, -4), Vector3(62, 8, 116), "Market", 0.4)
	_zone("dinh_hang_may", Vector3(0, 6, 84.5), Vector3(68, 12, 31), "Temple", 0.5)
	_zone("mai_nha_rooftops", Vector3(0, 20, 0), Vector3(250, 16, 210), "", 0.0)
	# shelters under awnings: one per shop module (front strip, ~1.2 m deep, below 3.2 m)
	var sg := grp("Zones")
	var count := 0
	for m: Dictionary in placed:
		if str((m["entry"] as Dictionary).get("kind", "")) != "shop":
			continue
		var xf: Transform3D = m["xf"]
		var a := Area3D.new()
		a.name = "Shelter_%d" % count
		a.add_to_group(&"shelter")
		a.collision_layer = 1 << 9
		a.collision_mask = 0
		a.monitoring = false
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = Vector3(float(m["w"]) - 0.2, 3.0, 1.6)
		cs.shape = bs
		a.add_child(cs)
		a.transform = Transform3D(xf.basis, xf.origin + xf.basis.z * 0.5 + Vector3(0, 1.5, 0))
		sg.add_child(a)
		count += 1
	report["counts"]["shelters"] = count


# =================================================================================================
# reflection probes & occluders
# =================================================================================================

func _build_probes_and_occluders() -> void:
	var pg := grp("Probes")
	var probes := [
		["MainStreetW", Vector3(-70, 4, -70), Vector3(60, 14, 16)], ["MainStreetE", Vector3(40, 4, -70), Vector3(80, 14, 16)],
		["HemA", Vector3(-90, 4, -4), Vector3(8, 12, 110)], ["Lake", Vector3(-2, 3, 4), Vector3(90, 14, 80)],
		["Market", Vector3(82, 4, -25), Vector3(40, 10, 40)], ["Temple", Vector3(0, 5, 84), Vector3(66, 14, 30)],
		["TempleStreet", Vector3(0, 4, 62), Vector3(200, 14, 16)],
	]
	for p: Array in probes:
		var rp := ReflectionProbe.new()
		rp.name = "Probe_" + str(p[0])
		rp.position = p[1]
		rp.size = p[2]
		rp.box_projection = true
		rp.update_mode = ReflectionProbe.UPDATE_ONCE
		rp.intensity = 0.9
		rp.max_distance = 120.0
		rp.blend_distance = 3.0
		rp.enable_shadows = false
		pg.add_child(rp)
	# occluders: one box per module, inset from the facade (party walls coincide)
	var og := grp("Occluders")
	for m: Dictionary in placed:
		var xf: Transform3D = m["xf"]
		var h: float = minf(float(m["h"]) * 0.7, 9.0)
		var occ := OccluderInstance3D.new()
		var box := BoxOccluder3D.new()
		box.size = Vector3(float(m["w"]) - 0.4, h, float(m["d"]) - 2.5)
		occ.occluder = box
		occ.transform = Transform3D(xf.basis, xf.origin - xf.basis.z * (float(m["d"]) * 0.5 + 0.5) + Vector3(0, h * 0.5, 0))
		og.add_child(occ)
