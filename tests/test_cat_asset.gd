extends "res://tests/test_base.gd"
## Contract checks for assets/models/cat/cat.glb (owner: cat-asset).

const CAT_PATH := "res://assets/models/cat/cat.glb"
const BONES: Array[String] = [
	"root", "pelvis", "spine_01", "spine_02", "spine_03", "chest", "neck", "head", "jaw",
	"ear_L", "ear_R", "eyelid_L", "eyelid_R", "tail_01", "tail_02", "tail_03", "tail_04", "tail_05", "tail_06",
	"upperarm_L", "upperarm_R", "forearm_L", "forearm_R", "hand_L", "hand_R",
	"thigh_L", "thigh_R", "shin_L", "shin_R", "foot_L", "foot_R", "toe_L", "toe_R",
]
const EXTRA_BONES: Array[String] = ["mouth_socket", "fpp_eye", "scapula_L", "scapula_R", "tail_07", "tail_08",
	"eye_L", "eye_R", "eyelid_low_L", "eyelid_low_R", "tongue_01", "ear_tip_L", "whisker_L"]
const ANIMS: Array[String] = [
	"idle", "idle_look", "walk", "trot", "run", "sneak", "sneak_idle", "jump_crouch", "jump_up", "fall", "land",
	"land_hard", "sit_down", "sit_idle", "stand_up", "lie_down", "sleep", "groom", "meow", "hiss", "swipe",
	"scratch", "climb", "turn_left_90", "turn_right_90", "drink", "eat", "knead", "stretch", "balance_walk",
	"pickup", "knock",
]
const LOOPING: Array[String] = ["idle", "idle_look", "walk", "trot", "run", "sneak", "sneak_idle", "fall",
	"sit_idle", "sleep", "groom", "scratch", "climb", "drink", "eat", "knead", "balance_walk"]
const TEXTURES: Array[String] = ["cat_fur_mask.png", "cat_albedo_black.png", "cat_albedo_white.png",
	"cat_albedo_calico.png", "cat_albedo_grey_tabby.png", "cat_albedo.png", "cat_normal.png", "cat_fur_flow.png"]

var _cat: Node3D


func before_each() -> void:
	var ps := load(CAT_PATH) as PackedScene
	if ps != null:
		_cat = ps.instantiate() as Node3D


func after_each() -> void:
	if is_instance_valid(_cat):
		_cat.free()


func _skeleton() -> Skeleton3D:
	return _cat.get_node_or_null("CatRig/Skeleton3D") as Skeleton3D


func _anim_player() -> AnimationPlayer:
	var found := _cat.find_children("*", "AnimationPlayer", true, false)
	return found[0] as AnimationPlayer if found.size() > 0 else null


func test_scene_loads() -> void:
	assert_not_null(_cat, "cat.glb must load as a PackedScene")


func test_bones() -> void:
	var sk := _skeleton()
	assert_not_null(sk, "CatRig/Skeleton3D")
	if sk == null:
		return
	for b in BONES + EXTRA_BONES:
		assert_true(sk.find_bone(b) >= 0, "bone " + b)


func test_meshes() -> void:
	var sk := _skeleton()
	if sk == null:
		assert_true(false, "no skeleton")
		return
	for n in ["CatBody", "CatEyes", "CatWhiskers"]:
		var mi := sk.find_child(n, true, false) as MeshInstance3D
		assert_not_null(mi, "mesh " + n)
	var body := sk.find_child("CatBody", true, false) as MeshInstance3D
	if body == null:
		return
	var tris := 0
	for s in body.mesh.get_surface_count():
		var arr := body.mesh.surface_get_arrays(s)
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		tris += idx.size() / 3
	assert_true(tris >= 25000 and tris <= 45000, "CatBody triangles in 25k..45k, got %d" % tris)
	var eyes := sk.find_child("CatEyes", true, false) as MeshInstance3D
	assert_true(eyes.mesh.get_surface_count() >= 2, "CatEyes has separate iris + cornea surfaces")


func test_animations() -> void:
	var ap := _anim_player()
	assert_not_null(ap, "AnimationPlayer")
	if ap == null:
		return
	for a in ANIMS:
		assert_true(ap.has_animation(StringName(a)), "animation " + a)
	for a in LOOPING:
		if ap.has_animation(StringName(a)):
			assert_true(ap.get_animation(StringName(a)).loop_mode != Animation.LOOP_NONE, "loop " + a)
	# walk is two strides of 0.5 s
	if ap.has_animation(&"walk"):
		assert_near(ap.get_animation(&"walk").length, 1.0, 0.04, "walk length")


func test_scale_facing_origin() -> void:
	var sk := _skeleton()
	if sk == null:
		assert_true(false, "no skeleton")
		return
	var head := sk.get_bone_global_rest(sk.find_bone("head")).origin
	var pelvis := sk.get_bone_global_rest(sk.find_bone("pelvis")).origin
	assert_true(head.z > 0.10, "head towards +Z (MODEL_FRONT), z=%f" % head.z)
	assert_true(pelvis.z < -0.10, "pelvis behind the origin")
	var body := sk.find_child("CatBody", true, false) as MeshInstance3D
	var aabb := body.get_aabb()
	assert_near(aabb.position.y, 0.0, 0.01, "paws on the ground (origin at ground)")
	assert_true(aabb.size.y > 0.28 and aabb.size.y < 0.40, "height incl. ears, got %f" % aabb.size.y)
	assert_true(aabb.size.x < 0.16, "width, got %f" % aabb.size.x)
	var withers := sk.get_bone_global_rest(sk.find_bone("scapula_L")).origin.y
	assert_true(withers > 0.21 and withers < 0.26, "withers height ~0.25 m (scapula top %f)" % withers)


func test_textures_exist() -> void:
	for t in TEXTURES:
		var path := "res://assets/models/cat/textures/" + t
		assert_true(ResourceLoader.exists(path), path)
		var tex := load(path) as Texture2D
		assert_not_null(tex, path)
		if tex != null:
			assert_true(tex.get_width() >= 1024, "%s resolution" % t)


func test_key_rate() -> void:
	# Fast gaits need dense keys: Godot re-bakes glTF tracks at the import option animation/fps
	# (configure_import.py sets 120); at the default 30 the gallop's planted paws sink ~2 cm.
	var ap := _anim_player()
	if ap == null or not ap.has_animation(&"run"):
		assert_true(false, "run animation")
		return
	var run := ap.get_animation(&"run")
	var best := 0
	for ti in run.get_track_count():
		if run.track_get_type(ti) == Animation.TYPE_ROTATION_3D:
			best = maxi(best, run.track_get_key_count(ti))
	assert_true(best >= int(run.length * 110.0), "run keyed at >= 110 Hz (got %d keys over %.2f s)" % [best, run.length])
