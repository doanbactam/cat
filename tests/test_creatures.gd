extends "res://tests/test_base.gd"
## Contract checks for the NPC creature models (owner: creatures): every GLB in
## assets/models/npc/ loads, has an `Armature/Skeleton3D`, the required bones, a skinned mesh,
## the clip names from CLAUDE.md (+ the creatures brief), loop flags on looping clips,
## and a plausible real-world size.

const DIR := "res://assets/models/npc/"
const HUMAN_BONES: Array[String] = ["root", "pelvis", "spine_01", "spine_02", "chest", "neck", "head", "jaw",
	"clavicle_L", "upperarm_L", "forearm_L", "hand_L", "fingers_L", "thumb_L", "clavicle_R", "upperarm_R",
	"forearm_R", "hand_R", "fingers_R", "thumb_R", "thigh_L", "shin_L", "foot_L", "toe_L", "thigh_R", "shin_R",
	"foot_R", "toe_R"]
const HUMAN_CLIPS: Array[String] = ["idle", "walk", "sit", "talk", "sell", "pet_cat", "shoo", "look_around",
	"carry", "phone"]
const QUAD_BONES: Array[String] = ["root", "pelvis", "spine_01", "spine_02", "chest", "neck", "head", "jaw",
	"ear_L", "ear_R", "tail_01", "upperarm_L", "forearm_L", "hand_L", "thigh_L", "shin_L", "foot_L", "toe_L",
	"upperarm_R", "forearm_R", "hand_R", "thigh_R", "shin_R", "foot_R", "toe_R"]
const BIRD_BONES: Array[String] = ["root", "pelvis", "chest", "neck_01", "neck_02", "head", "jaw", "tail",
	"upperarm_L", "forearm_L", "hand_L", "upperarm_R", "forearm_R", "hand_R", "thigh_L", "shin_L", "foot_L",
	"toe_L", "thigh_R", "shin_R", "foot_R", "toe_R", "wingfold_L", "wingfold_R"]
const BIRD_CLIPS: Array[String] = ["idle", "peck", "walk", "fly", "takeoff", "land"]
const FISH_BONES: Array[String] = ["root", "head", "jaw", "spine_01", "spine_06", "tail_fin", "pectoral_L",
	"pectoral_R", "dorsal"]
const NON_LOOPING: Array[String] = ["takeoff", "land", "bark", "caw", "hop"]

## id -> [bones, clips, min height (m), max height (m)]
var SPECS := {
	"ba_tu": [HUMAN_BONES, HUMAN_CLIPS, 1.40, 1.60],
	"co_hoa": [HUMAN_BONES, HUMAN_CLIPS, 1.50, 1.85],
	"chu_sau": [HUMAN_BONES, HUMAN_CLIPS, 1.58, 1.78],
	"bin": [HUMAN_BONES, HUMAN_CLIPS, 1.15, 1.40],
	"ped_office": [HUMAN_BONES, HUMAN_CLIPS, 1.60, 1.80],
	"ped_student": [HUMAN_BONES, HUMAN_CLIPS, 1.50, 1.70],
	"ped_elder_man": [HUMAN_BONES, HUMAN_CLIPS, 1.50, 1.70],
	"ped_helmet_woman": [HUMAN_BONES, HUMAN_CLIPS, 1.52, 1.75],
	"ped_shopper": [HUMAN_BONES, HUMAN_CLIPS, 1.42, 1.62],
	"ped_xeom": [HUMAN_BONES, HUMAN_CLIPS, 1.60, 1.85],
	"dog": [QUAD_BONES, ["idle", "walk", "run", "bark", "sleep", "sniff", "growl"], 0.55, 0.85],
	"mouse": [QUAD_BONES, ["idle", "run"], 0.025, 0.07],
	"gecko": [QUAD_BONES, ["idle", "run"], 0.006, 0.03],
	"pigeon": [BIRD_BONES, BIRD_CLIPS, 0.18, 0.30],
	"crow": [BIRD_BONES, BIRD_CLIPS + ["caw", "hop"], 0.24, 0.40],
	"sparrow": [BIRD_BONES, BIRD_CLIPS, 0.08, 0.15],
	"koi": [FISH_BONES, ["swim"], 0.09, 0.20],
}

var _inst: Node3D


func after_each() -> void:
	if is_instance_valid(_inst):
		_inst.free()


func _load(id: String) -> Node3D:
	var ps := load(DIR + id + ".glb") as PackedScene
	if ps == null:
		return null
	return ps.instantiate() as Node3D


func _player(n: Node) -> AnimationPlayer:
	var found := n.find_children("*", "AnimationPlayer", true, false)
	return found[0] as AnimationPlayer if found.size() > 0 else null


func _check(id: String) -> void:
	var spec: Array = SPECS[id]
	_inst = _load(id)
	assert_not_null(_inst, id + ".glb must load")
	if _inst == null:
		return
	var sk := _inst.get_node_or_null("Armature/Skeleton3D") as Skeleton3D
	assert_not_null(sk, id + ": Armature/Skeleton3D")
	if sk == null:
		return
	for b: String in spec[0]:
		assert_true(sk.find_bone(b) >= 0, "%s: bone %s" % [id, b])
	# skinned visible mesh
	var meshes := _inst.find_children("*", "MeshInstance3D", true, false)
	assert_true(meshes.size() >= 1, id + ": has meshes")
	var skinned := 0
	var aabb := AABB()
	var first := true
	for m: MeshInstance3D in meshes:
		if m.skin != null or m.get_parent() is Skeleton3D:
			skinned += 1
		var bb := m.get_aabb()
		aabb = bb if first else aabb.merge(bb)
		first = false
	assert_true(skinned >= 1, id + ": skinned mesh under the skeleton")
	var hgt := aabb.size.y
	assert_true(hgt >= float(spec[2]) and hgt <= float(spec[3]),
		"%s: height %.3f m outside [%.2f, %.2f]" % [id, hgt, spec[2], spec[3]])
	# facing: the model's front is +Z (nose/face at the +Z end of the bounds for walkers)
	assert_true(aabb.position.z + aabb.size.z > 0.0, id + ": front extends to +Z")
	var ap := _player(_inst)
	assert_not_null(ap, id + ": AnimationPlayer")
	if ap == null:
		return
	for c: String in spec[1]:
		assert_true(ap.has_animation(c), "%s: clip %s" % [id, c])
		if ap.has_animation(c):
			var a := ap.get_animation(c)
			assert_true(a.length > 0.05, "%s: clip %s has length" % [id, c])
			var want_loop := not NON_LOOPING.has(c)
			assert_eq(a.loop_mode != Animation.LOOP_NONE, want_loop, "%s: loop flag of %s" % [id, c])


func test_ba_tu() -> void: _check("ba_tu")
func test_co_hoa() -> void: _check("co_hoa")
func test_chu_sau() -> void: _check("chu_sau")
func test_bin() -> void: _check("bin")
func test_ped_office() -> void: _check("ped_office")
func test_ped_student() -> void: _check("ped_student")
func test_ped_elder_man() -> void: _check("ped_elder_man")
func test_ped_helmet_woman() -> void: _check("ped_helmet_woman")
func test_ped_shopper() -> void: _check("ped_shopper")
func test_ped_xeom() -> void: _check("ped_xeom")
func test_dog() -> void: _check("dog")
func test_mouse() -> void: _check("mouse")
func test_gecko() -> void: _check("gecko")
func test_pigeon() -> void: _check("pigeon")
func test_crow() -> void: _check("crow")
func test_sparrow() -> void: _check("sparrow")
func test_koi() -> void: _check("koi")


func test_catalog() -> void:
	var f := FileAccess.open(DIR + "catalog.json", FileAccess.READ)
	assert_not_null(f, "catalog.json exists")
	if f == null:
		return
	var data = JSON.parse_string(f.get_as_text())
	assert_true(data is Array, "catalog is an array")
	if not (data is Array):
		return
	var ids: Array[String] = []
	for e in data:
		ids.append(String(e.get("id", "")))
		assert_true(ResourceLoader.exists(String(e.get("file", ""))), "catalog file exists: " + str(e.get("file")))
	for id: String in SPECS:
		assert_true(ids.has(id), "catalog lists " + id)


func test_walk_root_in_place() -> void:
	# clips are in place: the root bone never translates more than a few cm
	_inst = _load("ba_tu")
	if _inst == null:
		return
	var ap := _player(_inst)
	var a := ap.get_animation("walk")
	var idx := a.find_track(NodePath("Armature/Skeleton3D:root"), Animation.TYPE_POSITION_3D)
	if idx >= 0:
		var p0: Vector3 = a.position_track_interpolate(idx, 0.0)
		var p1: Vector3 = a.position_track_interpolate(idx, a.length * 0.5)
		assert_true(p0.distance_to(p1) < 0.05, "root moves %.3f" % p0.distance_to(p1))
