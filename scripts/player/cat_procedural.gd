extends SkeletonModifier3D
## Procedural layer on top of Cam's clips (owner: player). Runs first in the modifier stack.
##
## * Breathing: rib-cage expansion on `chest` (children compensated), rate/depth from activity
##   (calm 0.4 Hz → panting after running, slow & deep while sleeping).
## * Spine bend into turns: yaw rate distributed along spine_01…neck (a turning cat curves).
## * Blinks with occasional slow blinks (eyelid bones), suppressed while sleeping (lids closed).
## * Crawl crouch: lowers the body; the foot IK keeps the paws planted so the legs fold.
## * Foot IK targets: for each leg, a ray finds the ground under the animated paw; planted paws
##   get a vertical correction (in the slope-aligned visual frame), the pelvis/root drops by the
##   lowest correction, and Marker3D targets/poles feed the TwoBoneIK3D that runs next.

const UP := Vector3.UP
const SOLID_MASK := 1 | (1 << 3) | (1 << 5) | (1 << 7)

@export var breath_depth := 0.012
@export var ik_max_delta := 0.11
@export var pelvis_max_drop := 0.08
@export var blink_axis_sign := -1.0
@export var blink_close_deg := 38.0

var player: Node = null
var animator: Node = null
var ik: TwoBoneIK3D = null
var _bones := {}
var _legs: Array[Dictionary] = []
var _breath_phase := 0.0
var _breath_rate := 0.4
var _breath_amp := 1.0
var _exertion := 0.0
var _spine_bend := 0.0
var _root_drop := 0.0
var _crawl := 0.0
var _ik_weight := 0.0
var _blink_t := 0.0
var _blink_next := 2.5
var _blink_len := 0.16
var _blink_slow := false
var _ray := PhysicsRayQueryParameters3D.new()


func setup(p_player: Node, p_animator: Node) -> void:
	player = p_player
	animator = p_animator
	var skel := get_skeleton()
	if skel == null:
		skel = get_parent() as Skeleton3D
	for i in skel.get_bone_count():
		_bones[skel.get_bone_name(i)] = i
	_ray.collision_mask = SOLID_MASK
	if player is CollisionObject3D:
		_ray.exclude = [(player as CollisionObject3D).get_rid()]
	var defs := [
		["L", "thigh_L", "shin_L", "foot_L", "toe_L", false],
		["R", "thigh_R", "shin_R", "foot_R", "toe_R", false],
		["L", "upperarm_L", "forearm_L", "hand_L", "finger_L", true],
		["R", "upperarm_R", "forearm_R", "hand_R", "finger_R", true],
	]
	for d: Array in defs:
		if not (_bones.has(d[1]) and _bones.has(d[2]) and _bones.has(d[3])):
			continue
		var target := Marker3D.new()
		target.name = "IKTarget_" + String(d[3])
		target.top_level = true
		add_child(target)
		var pole := Marker3D.new()
		pole.name = "IKPole_" + String(d[3])
		pole.top_level = true
		add_child(pole)
		_legs.append({
			"root": d[1], "mid": d[2], "end": d[3],
			"contact": d[4] if _bones.has(d[4]) else d[3],
			"front": d[5], "target": target, "pole": pole, "delta": 0.0,
		})


func get_leg_defs() -> Array[Dictionary]:
	return _legs


func set_ik(p_ik: TwoBoneIK3D) -> void:
	ik = p_ik


func _bone(n: String) -> int:
	return int(_bones.get(n, -1))


func _process_modification_with_delta(delta: float) -> void:
	var skel := get_skeleton()
	if skel == null or player == null:
		return
	var state: StringName = player.call(&"get_state")
	var mode: int = player.call(&"get_mode")
	var spd := absf(float(player.call(&"get_speed_along_facing")))
	_update_breathing(skel, delta, state, spd)
	_update_spine_bend(skel, delta, mode)
	_update_blink(skel, delta, state)
	_update_feet(skel, delta, mode, state)


# --- breathing ------------------------------------------------------------------------------

func _update_breathing(skel: Skeleton3D, delta: float, state: StringName, spd: float) -> void:
	var exert_goal := clampf((spd - 1.0) / 4.0, 0.0, 1.0)
	if state == &"jump" or state == &"scramble" or state == &"climb" or state == &"swim":
		exert_goal = 1.0
	# exertion builds quickly and fades over ~20 s (panting after a sprint)
	_exertion = lerpf(_exertion, exert_goal, 1.0 - exp(-delta * (0.9 if exert_goal > _exertion else 0.05)))
	var sleeping := state == &"sleep"
	var rate := lerpf(0.42, 1.6, _exertion)
	var amp := lerpf(1.0, 1.9, _exertion)
	if sleeping:
		rate = 0.3
		amp = 1.6
	_breath_rate = lerpf(_breath_rate, rate, 1.0 - exp(-delta * 1.5))
	_breath_amp = lerpf(_breath_amp, amp, 1.0 - exp(-delta * 1.5))
	_breath_phase = fmod(_breath_phase + delta * _breath_rate, 1.0)
	# inhale quicker than exhale
	var p := _breath_phase
	var w := sin(PI * pow(p, 0.8))
	var a := breath_depth * _breath_amp * w
	var chest := _bone("chest")
	if chest < 0:
		return
	var sc := Vector3(1.0 + a, 1.0 + a * 0.15, 1.0 + a)
	skel.set_bone_pose_scale(chest, skel.get_bone_pose_scale(chest) * sc)
	var inv := Vector3(1.0 / sc.x, 1.0 / sc.y, 1.0 / sc.z)
	for c in skel.get_bone_children(chest):
		skel.set_bone_pose_scale(c, skel.get_bone_pose_scale(c) * inv)
	var belly := _bone("spine_02")
	if belly >= 0:
		var b2 := Vector3(1.0 + a * 0.6, 1.0, 1.0 + a * 0.6)
		skel.set_bone_pose_scale(belly, skel.get_bone_pose_scale(belly) * b2)
		var inv2 := Vector3(1.0 / b2.x, 1.0, 1.0 / b2.z)
		for c in skel.get_bone_children(belly):
			skel.set_bone_pose_scale(c, skel.get_bone_pose_scale(c) * inv2)


# --- spine bend in turns ----------------------------------------------------------------------

func _update_spine_bend(skel: Skeleton3D, delta: float, mode: int) -> void:
	var yaw_rate := float(player.call(&"get_yaw_rate"))
	var goal := clampf(yaw_rate * 0.11, -0.45, 0.45)
	if mode == 2 or mode == 4:  # AIR, CLIMB: keep straight
		goal *= 0.3
	_spine_bend = lerpf(_spine_bend, goal, 1.0 - exp(-delta * 8.0))
	if absf(_spine_bend) < 0.002:
		return
	var up_skel := _skel_up(skel)
	var chain: Array[Array] = [["spine_01", 0.12], ["spine_02", 0.2], ["spine_03", 0.22], ["chest", 0.2], ["neck", 0.26]]
	for e: Array in chain:
		_rotate_global(skel, _bone(e[0]), up_skel, _spine_bend * float(e[1]))
	# hips counter-rotate a little so the hind end swings out of the turn
	_rotate_global(skel, _bone("pelvis"), up_skel, -_spine_bend * 0.12)


func _skel_up(skel: Skeleton3D) -> Vector3:
	var v := skel.global_basis.inverse() * (player as Node3D).global_basis.y
	return v.normalized() if v.length_squared() > 0.0001 else UP


## Rotates bone `idx` about a skeleton-space axis through its own head.
func _rotate_global(skel: Skeleton3D, idx: int, axis_skel: Vector3, angle: float) -> void:
	if idx < 0 or absf(angle) < 0.00001:
		return
	var parent := skel.get_bone_parent(idx)
	var pb := skel.get_bone_global_pose(parent).basis.orthonormalized() if parent >= 0 else Basis.IDENTITY
	var local_axis := (pb.inverse() * axis_skel).normalized()
	var q := Quaternion(local_axis, angle) * skel.get_bone_pose_rotation(idx)
	skel.set_bone_pose_rotation(idx, q.normalized())


# --- blinks -------------------------------------------------------------------------------------

func _update_blink(skel: Skeleton3D, delta: float, state: StringName) -> void:
	var up_l := _bone("eyelid_L")
	var up_r := _bone("eyelid_R")
	if up_l < 0 or up_r < 0:
		return
	if state == &"sleep":
		return  # the sleep clip keeps the lids closed
	_blink_t += delta
	var close := 0.0
	if _blink_t > _blink_next:
		var t := (_blink_t - _blink_next) / _blink_len
		if t >= 1.0:
			_blink_t = 0.0
			_blink_slow = randf() < 0.18
			_blink_len = 0.55 if _blink_slow else 0.15
			_blink_next = randf_range(2.5, 7.0)
		else:
			close = sin(PI * t)
			if _blink_slow:
				close = minf(1.0, close * 1.4) * 0.92
	if close < 0.01:
		return
	# blend towards the absolute closed pose (clips may already narrow the eyes)
	var up_ang := deg_to_rad(blink_close_deg) * blink_axis_sign
	for idx: int in [up_l, up_r]:
		var closed := skel.get_bone_rest(idx).basis.get_rotation_quaternion() * Quaternion(Vector3.RIGHT, up_ang)
		skel.set_bone_pose_rotation(idx, skel.get_bone_pose_rotation(idx).slerp(closed, close))
	for nm: String in ["eyelid_low_L", "eyelid_low_R"]:
		var li := _bone(nm)
		if li >= 0:
			var closed_lo := skel.get_bone_rest(li).basis.get_rotation_quaternion() * Quaternion(Vector3.RIGHT, -up_ang * 14.0 / 38.0)
			skel.set_bone_pose_rotation(li, skel.get_bone_pose_rotation(li).slerp(closed_lo, close))


# --- feet ----------------------------------------------------------------------------------------

func _update_feet(skel: Skeleton3D, delta: float, mode: int, state: StringName) -> void:
	if _legs.is_empty():
		return
	# IK weight: on in ground modes, off in the air / climbing / swimming / mantling
	var on := mode in [0, 1, 6, 7, 8]  # GROUND, CROUCH, TURN, ACTION, REST
	if state == &"sleep" or state == &"lie_down" or state == &"lie":
		on = false
	_ik_weight = move_toward(_ik_weight, 1.0 if on else 0.0, delta * 5.0)
	var crawling: bool = player.call(&"is_crawling")
	_crawl = move_toward(_crawl, 1.0 if crawling else 0.0, delta * 4.0)
	var visual: Node3D = player.call(&"get_visual")
	if visual == null:
		return
	var vis_xf := visual.global_transform
	var vis_inv := vis_xf.affine_inverse()
	var skel_xf := skel.global_transform
	var space := skel.get_world_3d().direct_space_state
	var min_delta := 0.0
	var deltas: Array[float] = []
	for L: Dictionary in _legs:
		var contact := skel_xf * skel.get_bone_global_pose(_bone(L["contact"])).origin
		var local := vis_inv * contact
		var lift := local.y
		var d := 0.0
		if _ik_weight > 0.0:
			_ray.from = contact + vis_xf.basis.y * 0.18
			_ray.to = contact - vis_xf.basis.y * 0.22
			var hit := space.intersect_ray(_ray)
			if not hit.is_empty() and (hit["normal"] as Vector3).y > 0.5:
				var hl := vis_inv * (hit["position"] as Vector3)
				var planted := 1.0 - smoothstep(0.02, 0.07, lift)
				d = clampf(hl.y, -ik_max_delta, ik_max_delta) * planted
		L["delta"] = lerpf(float(L["delta"]), d, 1.0 - exp(-delta * 18.0))
		deltas.append(float(L["delta"]))
		min_delta = minf(min_delta, float(L["delta"]))
	var drop_goal := clampf(min_delta, -pelvis_max_drop, 0.0) - _crawl * 0.05
	_root_drop = lerpf(_root_drop, drop_goal * _ik_weight + (-_crawl * 0.05) * (1.0 - _ik_weight), 1.0 - exp(-delta * 12.0))
	var root_idx := _bone("root")
	if root_idx >= 0 and absf(_root_drop) > 0.0001:
		var up_skel := _skel_up(skel)
		skel.set_bone_pose_position(root_idx, skel.get_bone_pose_position(root_idx) + _parent_space(skel, root_idx, up_skel) * _root_drop)
	# targets: animated end-bone head + the paw's correction, poles at the animated knee/elbow
	var fwd := vis_xf.basis.z
	for i in _legs.size():
		var L: Dictionary = _legs[i]
		var end_w := skel_xf * skel.get_bone_global_pose(_bone(L["end"])).origin
		var mid_w := skel_xf * skel.get_bone_global_pose(_bone(L["mid"])).origin
		var target: Marker3D = L["target"]
		target.global_position = end_w + vis_xf.basis.y * (deltas[i] - _root_drop) * _ik_weight
		var pole: Marker3D = L["pole"]
		var bend := -fwd if bool(L["front"]) else fwd
		pole.global_position = mid_w + bend * 0.25
	if ik != null:
		ik.influence = _ik_weight


func _parent_space(skel: Skeleton3D, idx: int, v_skel: Vector3) -> Vector3:
	var parent := skel.get_bone_parent(idx)
	if parent < 0:
		return v_skel
	return skel.get_bone_global_pose(parent).basis.inverse() * v_skel
