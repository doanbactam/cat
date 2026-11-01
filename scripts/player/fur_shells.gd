class_name FurShells
extends Node
## Shell fur for any cat built from assets/models/cat/cat.glb (owner: player; reused by
## world-life for NPC cats with variant albedos).
##
## attach_to_model(model) finds the skinned body mesh (`CatBody`), replaces its imported
## StandardMaterial3D with fur_base.gdshader (undercoat: albedo/normal/ORM + fur lighting) and
## chains `shell_count` fur_shell.gdshader passes through next_pass. Length/density come from
## cat_fur_mask.png (R/G), comb direction from cat_fur_flow.png. Per-frame instance uniforms:
## wetness (GameState.wetness for the player or the global `wetness` for NPCs), body inertia (fur
## sways when the cat accelerates/turns), first-person head hiding. Shell count follows
## Settings graphics/fur_shells (0 disables) and a distance LOD for NPCs.
##
## NPC use:
##   var fur := FurShells.new()
##   fur.albedo_override = load("res://assets/models/cat/textures/cat_albedo_black.png")
##   fur.use_game_state_wetness = false
##   add_child(fur); fur.attach_to_model(cat_model_instance, npc_body)

const BASE_SHADER := preload("res://shaders/fur_base.gdshader")
const SHELL_SHADER := preload("res://shaders/fur_shell.gdshader")
const TEX_DIR := "res://assets/models/cat/textures/"
const BODY_MESH_NAMES: Array[String] = ["CatBody", "Body", "cat_body"]

## -1 = Settings graphics/fur_shells (default 24). 0 disables the shells (base layer only).
@export var shell_count := -1
@export var albedo_override: Texture2D
@export var tint := Color(1, 1, 1, 1)
## Metres of fur at mask R = 1 (cat-asset FUR_MAX_LENGTH).
@export var fur_length := 0.016
## Player: own wet state from GameState. NPCs: the world's global wetness × influence.
@export var use_game_state_wetness := true
@export_range(0.0, 1.0) var global_wet_influence := 0.75
## LOD: full shells within x m of the active camera, half within y, quarter within z, none beyond.
@export var lod_distances := Vector3(5.0, 12.0, 26.0)
@export var enable_lod := false

var mesh_instance: MeshInstance3D = null
var _body: Node3D = null
var _base_mat: ShaderMaterial = null
var _shells: Array[ShaderMaterial] = []
var _active_count := 0
var _requested := 24
var _prev_pos := Vector3.ZERO
var _prev_vel := Vector3.ZERO
var _inertia := Vector3.ZERO
var _fpp := Vector4.ZERO
var _lod_t := 0.0

static var _strand_tex: ImageTexture = null


func _ready() -> void:
	GameEvents.settings_changed.connect(_on_settings_changed)


## Finds the body mesh under `model` and builds the fur materials. Returns false when no
## suitable skinned mesh exists.
func attach_to_model(model: Node3D, body: Node3D = null) -> bool:
	_body = body if body != null else model
	mesh_instance = _find_body_mesh(model)
	if mesh_instance == null or mesh_instance.mesh == null:
		push_warning("FurShells: no body mesh under %s" % model.name)
		return false
	_build_base()
	_requested = _settings_shell_count()
	_rebuild_shells(_requested)
	_prev_pos = _body.global_position if _body.is_inside_tree() else Vector3.ZERO
	return true


func get_base_material() -> ShaderMaterial:
	return _base_mat


func get_shell_materials() -> Array[ShaderMaterial]:
	return _shells


func get_active_shell_count() -> int:
	return _active_count


func set_shell_count(n: int) -> void:
	shell_count = n
	_requested = _settings_shell_count()
	_rebuild_shells(_requested)


## First-person hiding: discard the head (sphere around `head_pos`) in the main camera pass.
func set_first_person(amount: float, cam_pos: Vector3, head_pos: Vector3) -> void:
	if amount > 0.85:
		var centre := head_pos + (head_pos - cam_pos) * 0.0
		_fpp = Vector4(centre.x, centre.y, centre.z, 0.085)
	else:
		_fpp = Vector4.ZERO


func _process(delta: float) -> void:
	if mesh_instance == null or not is_instance_valid(mesh_instance) or _body == null:
		return
	# body inertia: strands trail the motion and swing on acceleration
	var pos := _body.global_position
	var vel := Vector3.ZERO
	if _body is CharacterBody3D:
		vel = (_body as CharacterBody3D).velocity
	elif delta > 0.0:
		vel = (pos - _prev_pos) / delta
	_prev_pos = pos
	var acc := (vel - _prev_vel) / maxf(delta, 0.001)
	_prev_vel = vel
	var goal := (-vel * 0.05 - acc * 0.012).limit_length(0.9)
	_inertia = _inertia.lerp(goal, 1.0 - exp(-8.0 * delta))
	mesh_instance.set_instance_shader_parameter(&"inertia", _inertia)
	var wet := 0.0
	if use_game_state_wetness:
		wet = GameState.wetness
	mesh_instance.set_instance_shader_parameter(&"wet_self", wet)
	mesh_instance.set_instance_shader_parameter(&"fpp_hide", _fpp)
	var cam := mesh_instance.get_viewport().get_camera_3d() if mesh_instance.is_inside_tree() else null
	if cam != null:
		mesh_instance.set_instance_shader_parameter(&"main_cam", cam.global_position)
		if enable_lod:
			_lod_t += delta
			if _lod_t > 0.4:
				_lod_t = 0.0
				_update_lod(cam.global_position.distance_to(pos))


func _update_lod(dist: float) -> void:
	var n := _requested
	if dist > lod_distances.z:
		n = 0
	elif dist > lod_distances.y:
		n = maxi(_requested / 4, 4)
	elif dist > lod_distances.x:
		n = maxi(_requested / 2, 6)
	n = mini(n, _requested)
	if n != _active_count:
		_rebuild_shells(n)


# --- building -------------------------------------------------------------------------------

func _find_body_mesh(root: Node) -> MeshInstance3D:
	for nm in BODY_MESH_NAMES:
		var found := root.find_child(nm, true, false)
		if found is MeshInstance3D:
			return found
	# fallback: the skinned mesh with the most vertices
	var best: MeshInstance3D = null
	var best_n := -1
	for c in root.find_children("*", "MeshInstance3D", true, false):
		var mi := c as MeshInstance3D
		if mi.mesh == null or mi.skin == null and mi.get_parent() is not Skeleton3D:
			continue
		var n := 0
		for s in mi.mesh.get_surface_count():
			n += mi.mesh.surface_get_array_len(s)
		if n > best_n:
			best_n = n
			best = mi
	return best


func _build_base() -> void:
	var src: Material = mesh_instance.get_active_material(0)
	var std := src as BaseMaterial3D
	_base_mat = ShaderMaterial.new()
	_base_mat.shader = BASE_SHADER
	var albedo: Texture2D = albedo_override
	if albedo == null and std != null:
		albedo = std.albedo_texture
	if albedo == null:
		albedo = _load_tex("cat_albedo.png")
	var normal: Texture2D = std.normal_texture if std != null else null
	if normal == null:
		normal = _load_tex("cat_normal.png")
	var orm: Texture2D = _load_tex("cat_orm.png")
	_base_mat.set_shader_parameter(&"albedo_tex", albedo)
	_base_mat.set_shader_parameter(&"normal_tex", normal)
	_base_mat.set_shader_parameter(&"orm_tex", orm)
	_set_common(_base_mat, albedo)
	mesh_instance.material_override = _base_mat


func _set_common(m: ShaderMaterial, albedo: Texture2D) -> void:
	m.set_shader_parameter(&"albedo_tex", albedo)
	m.set_shader_parameter(&"fur_mask", _load_tex("cat_fur_mask.png"))
	m.set_shader_parameter(&"fur_flow", _load_tex("cat_fur_flow.png"))
	m.set_shader_parameter(&"tint", tint)
	m.set_shader_parameter(&"fur_length", fur_length)
	m.set_shader_parameter(&"global_wet_influence", 0.0 if use_game_state_wetness else global_wet_influence)


func _rebuild_shells(n: int) -> void:
	if _base_mat == null:
		return
	n = clampi(n, 0, 64)
	var albedo: Texture2D = _base_mat.get_shader_parameter(&"albedo_tex")
	# reuse existing shell materials where possible (keeps shader compile cost down)
	while _shells.size() < n:
		var sm := ShaderMaterial.new()
		sm.shader = SHELL_SHADER
		_set_common(sm, albedo)
		sm.set_shader_parameter(&"strand_tex", get_strand_texture())
		_shells.append(sm)
	var prev: Material = _base_mat
	for i in n:
		var sm := _shells[i]
		var h := float(i + 1) / float(n)
		sm.set_shader_parameter(&"shell_h", h)
		# every 4th shell (and the outermost) casts into shadow maps: soft fuzzy shadow edge
		sm.set_shader_parameter(&"shadow_shell", 1.0 if (i % 4 == 3 or i == n - 1) else 0.0)
		sm.next_pass = null
		prev.next_pass = sm
		prev = sm
	if n == 0:
		_base_mat.next_pass = null
	_active_count = n


func _settings_shell_count() -> int:
	if shell_count >= 0:
		return shell_count
	var s := get_node_or_null(^"/root/Settings")
	if s != null and s.has_method(&"get_value"):
		var v: Variant = s.call(&"get_value", "graphics", "fur_shells", 24)
		if v != null:
			return int(v)
	return 24


func _on_settings_changed(section: StringName) -> void:
	if section == &"graphics" or section == &"":
		var n := _settings_shell_count()
		if n != _requested:
			_requested = n
			_rebuild_shells(n)


static func _load_tex(file: String) -> Texture2D:
	var p := TEX_DIR + file
	if ResourceLoader.exists(p):
		return load(p) as Texture2D
	return null


## Tiling strand-height field: thousands of small cones (value 1 at the strand centre, falling to
## 0 at its edge, random length) with mipmaps. A shell at height h keeps texels where value > h,
## so strands taper towards their tips.
static func get_strand_texture() -> ImageTexture:
	if _strand_tex != null:
		return _strand_tex
	var size := 256
	var data := PackedFloat32Array()
	data.resize(size * size)
	var rng := RandomNumberGenerator.new()
	rng.seed = 90210
	var count := 2900
	for i in count:
		var cx := rng.randf() * size
		var cy := rng.randf() * size
		var r := rng.randf_range(1.7, 3.1)
		var hgt := rng.randf_range(0.55, 1.0)
		var ri := int(ceil(r))
		for dy in range(-ri, ri + 1):
			for dx in range(-ri, ri + 1):
				var d := sqrt(float(dx * dx + dy * dy)) / r
				if d >= 1.0:
					continue
				var v := hgt * (1.0 - d * d * 0.6 - d * 0.4)
				var px := posmod(int(cx) + dx, size)
				var py := posmod(int(cy) + dy, size)
				var idx := py * size + px
				if v > data[idx]:
					data[idx] = v
	var img := Image.create_empty(size, size, false, Image.FORMAT_L8)
	for y in size:
		for x in size:
			var v := clampf(data[y * size + x], 0.0, 1.0)
			img.set_pixel(x, y, Color(v, v, v, 1.0))
	img.generate_mipmaps()
	_strand_tex = ImageTexture.create_from_image(img)
	return _strand_tex
