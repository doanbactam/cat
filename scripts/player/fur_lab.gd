extends Node3D
## Fur / look-dev stage for Cam (owner: player) — scenes/player/fur_lab.tscn.
## The real cat.glb with FurShells under a warm late-afternoon sun, sky light and a soft bounce,
## on a weathered concrete slab, framed by a close camera. Used for fur/shading QA and gallery
## shots. Hooks (tools/screenshot.sh … call=<hook>): view_side, view_front, view_close,
## view_back, pose_sit, pose_walk, make_wet, no_shells, debug_shells.

const MODEL := "res://assets/models/cat/cat.glb"
const TEX := "res://assets/textures/architecture/"

@export var anim := &"idle"
@export var anim_time := 1.2

var cat: Node3D
var fur: FurShells
var cam: Camera3D
var ap: AnimationPlayer


func _ready() -> void:
	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var psm := PhysicalSkyMaterial.new()
	psm.turbidity = 8.0
	psm.ground_color = Color(0.3, 0.28, 0.26)
	sky.sky_material = psm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.ssao_radius = 0.25
	env.ssao_intensity = 1.4
	env.glow_enabled = true
	env.glow_intensity = 0.2
	env.glow_hdr_threshold = 1.5
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-28.0, -55.0, 0.0)
	sun.light_energy = 2.6
	sun.light_color = Color(1.0, 0.9, 0.76)
	sun.light_angular_distance = 0.8
	sun.shadow_enabled = true
	sun.shadow_bias = 0.01
	sun.shadow_normal_bias = 0.4
	sun.directional_shadow_max_distance = 6.0
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	add_child(sun)
	# warm ground bounce + cool sky fill so the shadow side keeps its form
	var bounce := OmniLight3D.new()
	bounce.position = Vector3(0.4, 0.05, 0.6)
	bounce.light_color = Color(1.0, 0.82, 0.62)
	bounce.light_energy = 0.25
	bounce.omni_range = 1.6
	add_child(bounce)
	var floor_mi := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(8, 8)
	floor_mi.mesh = pm
	var fm := ORMMaterial3D.new()
	if ResourceLoader.exists(TEX + "concrete_weathered_albedo.jpg"):
		fm.albedo_texture = load(TEX + "concrete_weathered_albedo.jpg")
		fm.normal_enabled = true
		fm.normal_texture = load(TEX + "concrete_weathered_normal.png")
		fm.orm_texture = load(TEX + "concrete_weathered_orm.jpg")
		fm.uv1_scale = Vector3(4, 4, 4)
	floor_mi.material_override = fm
	add_child(floor_mi)
	var wall := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(8, 3, 0.2)
	wall.mesh = bm
	var wm := ORMMaterial3D.new()
	if ResourceLoader.exists(TEX + "plaster_ochre_albedo.jpg"):
		wm.albedo_texture = load(TEX + "plaster_ochre_albedo.jpg")
		wm.normal_enabled = true
		wm.normal_texture = load(TEX + "plaster_ochre_normal.png")
		wm.orm_texture = load(TEX + "plaster_ochre_orm.jpg")
		wm.uv1_triplanar = true
		wm.uv1_world_triplanar = true
		wm.uv1_scale = Vector3(0.5, 0.5, 0.5)
	wall.material_override = wm
	wall.position = Vector3(0, 1.5, -1.2)
	add_child(wall)
	cat = (load(MODEL) as PackedScene).instantiate() as Node3D
	add_child(cat)
	var aps := cat.find_children("*", "AnimationPlayer", true, false)
	if not aps.is_empty():
		ap = aps[0] as AnimationPlayer
		_pose(anim, anim_time)
	fur = FurShells.new()
	add_child(fur)
	fur.attach_to_model(cat, cat)
	cam = Camera3D.new()
	cam.fov = 35.0
	cam.near = 0.01
	add_child(cam)
	cam.make_current()
	view_side()


func _pose(clip: StringName, t: float) -> void:
	if ap == null or not ap.has_animation(clip):
		return
	ap.play(clip)
	ap.seek(t, true)
	ap.pause()


func _frame(eye: Vector3, target: Vector3, fov := 35.0) -> void:
	cam.fov = fov
	cam.global_position = eye
	cam.look_at(target, Vector3.UP)


func view_side() -> void:
	_frame(Vector3(0.62, 0.3, 0.5), Vector3(0.0, 0.17, 0.0))


func view_front() -> void:
	_frame(Vector3(0.18, 0.27, 0.72), Vector3(0.0, 0.21, 0.08))


func view_close() -> void:
	_frame(Vector3(0.2, 0.3, 0.46), Vector3(0.0, 0.25, 0.15), 30.0)


func view_back() -> void:
	_frame(Vector3(-0.45, 0.38, -0.62), Vector3(0.0, 0.16, 0.0))


func pose_sit() -> void:
	_pose(&"sit_idle", 1.0)
	_frame(Vector3(0.55, 0.28, 0.55), Vector3(0.0, 0.17, 0.05))


func pose_walk() -> void:
	_pose(&"trot", 0.2)
	view_side()


func make_wet() -> void:
	GameState.wetness = 1.0
	view_side()


func no_shells() -> void:
	fur.set_shell_count(0)
	view_side()


func debug_shells() -> void:
	for i in fur.get_shell_materials().size():
		fur.get_shell_materials()[i].set_shader_parameter(&"tint", Color(1.0, 0.15 + 0.85 * float(i) / 24.0, 0.15))
	view_close()
