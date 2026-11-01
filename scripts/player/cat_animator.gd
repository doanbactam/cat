extends Node
## Cam's animation layer (owner: player).
##
## Builds, at runtime, an AnimationTree over the clips imported with assets/models/cat/cat.glb:
##   loco  = BlendSpace1D gait (idle 0 · walk 0.7 · trot 1.6 · run 4.5, synced) ⨉ Blend2 with a
##           sneak BlendSpace1D (sneak_idle · sneak) → TimeScale (playback matched to the real
##           speed: no foot sliding at any gait speed or GameState speed modifier)
##   state = AnimationNodeTransition over loco + every contextual clip (jump_crouch, jump_up, fall,
##           land(_hard), climb, balance BlendSpace, turns, sit/lie/sleep/groom sequences,
##           actions…) with per-transition cross-fade times → TimeScale → OneShot (meow; filtered to
##           the head/jaw/ears so the cat can meow while walking) → output.
## Loop flags are set on the imported Animation resources at runtime (glTF has none).
## Skeleton modifier stack (children of the Skeleton3D, processed in order):
##   CatProcedural (breathing, spine bend into turns, blinks, crawl crouch, foot-IK targets +
##   pelvis drop) → TwoBoneIK3D (4 legs) → LookAtModifier3D neck + head (+ eyes) towards the
##   player's look target → SpringBoneSimulator3D (tail + ears react to motion).
## Sockets: BoneAttachment3D on `mouth_socket` (held items) and `fpp_eye` (first-person camera).

const ProceduralScript := preload("res://scripts/player/cat_procedural.gd")

const LOOPING: Array[StringName] = [
	&"idle", &"idle_look", &"walk", &"trot", &"run", &"sneak", &"sneak_idle", &"fall", &"sit_idle",
	&"sleep", &"groom", &"scratch", &"climb", &"drink", &"eat", &"knead", &"balance_walk",
]
## Authored gait speeds (m/s) — CLAUDE.md cat contract.
const GAIT := {&"walk": 0.7, &"trot": 1.6, &"run": 4.5, &"sneak": 0.45, &"balance_walk": 0.4}

## state → [transition input, cross-fade seconds]
const STATE_MAP := {
	&"idle": [&"loco", 0.25], &"walk": [&"loco", 0.22], &"trot": [&"loco", 0.22], &"run": [&"loco", 0.2],
	&"sneak": [&"loco", 0.25], &"sneak_idle": [&"loco", 0.25], &"crawl": [&"loco", 0.25],
	&"idle_look": [&"idle_look", 0.45], &"balance": [&"balance", 0.25],
	&"turn_left_90": [&"turn_left_90", 0.12], &"turn_right_90": [&"turn_right_90", 0.12],
	&"jump_crouch": [&"jump_crouch", 0.1], &"jump": [&"jump_up", 0.05], &"fall": [&"fall", 0.28],
	&"land": [&"land", 0.05], &"land_hard": [&"land_hard", 0.04], &"scramble": [&"scramble", 0.08],
	&"climb": [&"climb", 0.18], &"swim": [&"swim", 0.25],
	&"sit_down": [&"sit_down", 0.22], &"sit": [&"sit_idle", 0.3], &"stand_up": [&"stand_up", 0.12],
	&"lie_down": [&"lie_down", 0.3], &"lie": [&"lie_down", 0.3], &"sleep": [&"sleep", 0.8],
	&"groom": [&"groom", 0.4], &"knead": [&"knead", 0.35], &"stretch": [&"stretch", 0.25],
	&"eat": [&"eat", 0.3], &"drink": [&"drink", 0.3], &"scratch": [&"scratch", 0.25],
	&"pickup": [&"pickup", 0.15], &"knock": [&"knock", 0.12], &"swipe": [&"swipe", 0.08],
	&"hiss": [&"hiss", 0.12], &"rub": [&"rub", 0.3], &"meow": [&"loco", 0.2],
}
## Inputs that play a different clip than their name.
const INPUT_CLIP := {&"scramble": &"climb", &"swim": &"trot", &"rub": &"idle_look"}
const HEAD_BONES: Array[String] = [
	"neck", "neck_02", "head", "jaw", "tongue_01", "tongue_02", "ear_L", "ear_R", "ear_tip_L",
	"ear_tip_R", "eyelid_L", "eyelid_R", "eyelid_low_L", "eyelid_low_R", "whisker_L", "whisker_R",
]

var player: Node = null
var model: Node3D = null
var skeleton: Skeleton3D = null
var anim_player: AnimationPlayer = null
var tree: AnimationTree = null
var procedural: SkeletonModifier3D = null
var foot_ik: TwoBoneIK3D = null
var look_neck: LookAtModifier3D = null
var look_head: LookAtModifier3D = null
var look_eyes: Array[LookAtModifier3D] = []
var springs: SpringBoneSimulator3D = null
var mouth_socket: BoneAttachment3D = null
var eye_socket: BoneAttachment3D = null

var _inputs: Array[StringName] = []
var _transition: AnimationNodeTransition
var _current_input: StringName = &"loco"
var _state_speed := 1.0
var _gait_phase := 0.0
var _sneak_amount := 0.0
var _hidden_fpp := false
var _fpp_meshes: Array[GeometryInstance3D] = []
var _missing_warned := {}


# =============================================================================================
# Setup
# =============================================================================================

func setup(p_model: Node3D, p_player: Node) -> bool:
	model = p_model
	player = p_player
	var skels := model.find_children("*", "Skeleton3D", true, false)
	if skels.is_empty():
		push_warning("CatAnimator: no Skeleton3D in the cat model")
		return false
	skeleton = skels[0] as Skeleton3D
	var aps := model.find_children("*", "AnimationPlayer", true, false)
	if not aps.is_empty():
		anim_player = aps[0] as AnimationPlayer
	_set_loops()
	_build_sockets()
	if anim_player != null and anim_player.get_animation_list().size() > 0:
		_build_tree()
	_build_modifiers()
	for mi in model.find_children("*", "GeometryInstance3D", true, false):
		var nm := String(mi.name).to_lower()
		if nm.contains("eye") or nm.contains("whisker"):
			_fpp_meshes.append(mi as GeometryInstance3D)
	return true


func _set_loops() -> void:
	if anim_player == null:
		return
	for clip in LOOPING:
		if anim_player.has_animation(clip):
			anim_player.get_animation(clip).loop_mode = Animation.LOOP_LINEAR
	for clip in anim_player.get_animation_list():
		if not StringName(clip) in LOOPING:
			anim_player.get_animation(clip).loop_mode = Animation.LOOP_NONE


func has_clip(clip: StringName) -> bool:
	return anim_player != null and anim_player.has_animation(clip)


func get_clip_length(clip: StringName) -> float:
	if has_clip(clip):
		return anim_player.get_animation(clip).length
	return -1.0


func _clip_or_fallback(clip: StringName) -> StringName:
	if has_clip(clip):
		return clip
	if not _missing_warned.has(clip):
		_missing_warned[clip] = true
		push_warning("CatAnimator: clip '%s' missing in cat.glb, using fallback" % clip)
	for fb: StringName in [&"idle", &"sit_idle", &"walk"]:
		if has_clip(fb):
			return fb
	var list := anim_player.get_animation_list()
	return StringName(list[0]) if list.size() > 0 else &""


func _anim(clip: StringName) -> AnimationNodeAnimation:
	var a := AnimationNodeAnimation.new()
	a.animation = _clip_or_fallback(clip)
	return a


func _build_tree() -> void:
	var root := AnimationNodeBlendTree.new()
	# --- locomotion ---------------------------------------------------------------------
	var loco := AnimationNodeBlendTree.new()
	var gait := AnimationNodeBlendSpace1D.new()
	gait.min_space = 0.0
	gait.max_space = 4.5
	gait.sync = true
	gait.add_blend_point(_anim(&"idle"), 0.0, -1, &"idle")
	gait.add_blend_point(_anim(&"walk"), GAIT[&"walk"], -1, &"walk")
	gait.add_blend_point(_anim(&"trot"), GAIT[&"trot"], -1, &"trot")
	gait.add_blend_point(_anim(&"run"), GAIT[&"run"], -1, &"run")
	var sneak := AnimationNodeBlendSpace1D.new()
	sneak.min_space = 0.0
	sneak.max_space = 0.45
	sneak.sync = true
	sneak.add_blend_point(_anim(&"sneak_idle"), 0.0, -1, &"sneak_idle")
	sneak.add_blend_point(_anim(&"sneak"), GAIT[&"sneak"], -1, &"sneak")
	loco.add_node(&"gait", gait, Vector2(0, 0))
	loco.add_node(&"sneak", sneak, Vector2(0, 200))
	loco.add_node(&"sneak_blend", AnimationNodeBlend2.new(), Vector2(250, 100))
	loco.add_node(&"loco_ts", AnimationNodeTimeScale.new(), Vector2(450, 100))
	loco.connect_node(&"sneak_blend", 0, &"gait")
	loco.connect_node(&"sneak_blend", 1, &"sneak")
	loco.connect_node(&"loco_ts", 0, &"sneak_blend")
	loco.connect_node(&"output", 0, &"loco_ts")
	root.add_node(&"loco", loco, Vector2(0, 0))
	# --- balance (stand still ↔ balance walk) -------------------------------------------------
	var bal := AnimationNodeBlendSpace1D.new()
	bal.min_space = 0.0
	bal.max_space = 0.4
	bal.sync = true
	bal.add_blend_point(_anim(&"sneak_idle"), 0.0, -1, &"still")
	bal.add_blend_point(_anim(&"balance_walk"), GAIT[&"balance_walk"], -1, &"balance_walk")
	root.add_node(&"balance", bal, Vector2(0, 150))
	# --- contextual clips -------------------------------------------------------------------
	_inputs = [&"loco", &"balance"]
	var seen := {&"loco": true, &"balance": true}
	for st: StringName in STATE_MAP:
		var inp: StringName = STATE_MAP[st][0]
		if seen.has(inp):
			continue
		seen[inp] = true
		var clip: StringName = INPUT_CLIP.get(inp, inp)
		root.add_node(inp, _anim(clip), Vector2(0, 300 + 60 * _inputs.size()))
		_inputs.append(inp)
	_transition = AnimationNodeTransition.new()
	_transition.xfade_time = 0.2
	_transition.allow_transition_to_self = false
	for i in _inputs.size():
		_transition.add_input(_inputs[i])
	root.add_node(&"state", _transition, Vector2(500, 300))
	for i in _inputs.size():
		root.connect_node(&"state", i, _inputs[i])
	root.add_node(&"state_ts", AnimationNodeTimeScale.new(), Vector2(700, 300))
	root.connect_node(&"state_ts", 0, &"state")
	# --- meow one-shot on the head only ------------------------------------------------------
	var shot := AnimationNodeOneShot.new()
	shot.fadein_time = 0.08
	shot.fadeout_time = 0.18
	shot.filter_enabled = true
	var skel_path := String(model.get_path_to(skeleton))
	for b in HEAD_BONES:
		if skeleton.find_bone(b) >= 0:
			shot.set_filter_path(NodePath("%s:%s" % [skel_path, b]), true)
	root.add_node(&"head_shot", shot, Vector2(900, 300))
	root.add_node(&"meow", _anim(&"meow"), Vector2(700, 450))
	root.connect_node(&"head_shot", 0, &"state_ts")
	root.connect_node(&"head_shot", 1, &"meow")
	root.connect_node(&"output", 0, &"head_shot")

	tree = AnimationTree.new()
	tree.name = "AnimationTree"
	tree.tree_root = root
	model.add_child(tree)
	tree.anim_player = tree.get_path_to(anim_player)
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
	tree.active = true
	anim_player.active = false
	tree.set(&"parameters/state_ts/scale", 1.0)
	tree.set(&"parameters/loco/loco_ts/scale", 1.0)
	tree.set(&"parameters/state/transition_request", "loco")


func _build_sockets() -> void:
	var mb := "mouth_socket" if skeleton.find_bone("mouth_socket") >= 0 else ("jaw" if skeleton.find_bone("jaw") >= 0 else "")
	if mb != "":
		mouth_socket = BoneAttachment3D.new()
		mouth_socket.name = "MouthSocket"
		mouth_socket.bone_name = mb
		skeleton.add_child(mouth_socket)
	var eb := "fpp_eye" if skeleton.find_bone("fpp_eye") >= 0 else ("head" if skeleton.find_bone("head") >= 0 else "")
	if eb != "":
		eye_socket = BoneAttachment3D.new()
		eye_socket.name = "EyeSocket"
		eye_socket.bone_name = eb
		skeleton.add_child(eye_socket)


func get_mouth_socket() -> Node3D:
	return mouth_socket


func get_eye_socket() -> Node3D:
	return eye_socket


func _build_modifiers() -> void:
	# 1) procedural layer + foot IK target computation
	procedural = ProceduralScript.new()
	procedural.name = "CatProcedural"
	skeleton.add_child(procedural)
	procedural.call(&"setup", player, self)
	# 2) foot IK (targets/poles are Marker3Ds driven by CatProcedural)
	var legs: Array = procedural.call(&"get_leg_defs")
	if legs.size() > 0:
		foot_ik = TwoBoneIK3D.new()
		foot_ik.name = "FootIK"
		skeleton.add_child(foot_ik)
		foot_ik.setting_count = legs.size()
		for i in legs.size():
			var L: Dictionary = legs[i]
			foot_ik.set_root_bone_name(i, L["root"])
			foot_ik.set_middle_bone_name(i, L["mid"])
			foot_ik.set_end_bone_name(i, L["end"])
			foot_ik.set_target_node(i, foot_ik.get_path_to(L["target"]))
			foot_ik.set_pole_node(i, foot_ik.get_path_to(L["pole"]))
		procedural.call(&"set_ik", foot_ik)
	# 3) look-at: neck takes part of the turn, the head finishes it, eyes track
	var look_target: Node3D = player.call(&"get_look_target") if player != null and player.has_method(&"get_look_target") else null
	if look_target != null:
		var neck_bone := "neck_02" if skeleton.find_bone("neck_02") >= 0 else "neck"
		if skeleton.find_bone(neck_bone) >= 0:
			look_neck = _make_look(neck_bone, look_target, 40.0, 25.0, 0.45, 0.3)
		if skeleton.find_bone("head") >= 0:
			look_head = _make_look("head", look_target, 70.0, 40.0, 0.85, 0.22)
		for e: String in ["eye_L", "eye_R"]:
			if skeleton.find_bone(e) >= 0:
				look_eyes.append(_make_look(e, look_target, 22.0, 14.0, 1.0, 0.08))
	# 4) spring bones: tail + ears
	springs = SpringBoneSimulator3D.new()
	springs.name = "TailEarSprings"
	skeleton.add_child(springs)
	var chains: Array[Array] = []
	var last_tail := ""
	for i in range(1, 13):
		var b := "tail_%02d" % i
		if skeleton.find_bone(b) >= 0:
			last_tail = b
	if last_tail != "" and skeleton.find_bone("tail_01") >= 0:
		chains.append(["tail_01", last_tail, 1.1, 0.42, 0.0, 0.014, 0.035])
	for s: String in ["L", "R"]:
		if skeleton.find_bone("ear_" + s) >= 0:
			var tip := "ear_tip_" + s if skeleton.find_bone("ear_tip_" + s) >= 0 else "ear_" + s
			chains.append(["ear_" + s, tip, 7.0, 0.7, 0.0, 0.006, 0.012])
	springs.setting_count = chains.size()
	for i in chains.size():
		var c: Array = chains[i]
		springs.set_root_bone_name(i, c[0])
		springs.set_end_bone_name(i, c[1])
		springs.set_extend_end_bone(i, true)
		springs.set_end_bone_direction(i, SkeletonModifier3D.BONE_DIRECTION_FROM_PARENT)
		springs.set_end_bone_length(i, c[6])
		springs.set_stiffness(i, c[2])
		springs.set_drag(i, c[3])
		springs.set_gravity(i, c[4])
		springs.set_radius(i, c[5])


func _make_look(bone: String, target: Node3D, yaw_deg: float, pitch_deg: float, influence: float, duration: float) -> LookAtModifier3D:
	var m := LookAtModifier3D.new()
	m.name = "Look_" + bone
	skeleton.add_child(m)
	m.bone_name = bone
	m.forward_axis = SkeletonModifier3D.BONE_AXIS_PLUS_Y
	m.primary_rotation_axis = Vector3.AXIS_Z
	m.use_secondary_rotation = true
	m.use_angle_limitation = true
	m.symmetry_limitation = true
	m.primary_limit_angle = deg_to_rad(yaw_deg) * 2.0
	m.primary_damp_threshold = 0.6
	m.secondary_limit_angle = deg_to_rad(pitch_deg) * 2.0
	m.secondary_damp_threshold = 0.6
	m.duration = duration
	m.transition_type = Tween.TRANS_SINE
	m.ease_type = Tween.EASE_IN_OUT
	m.influence = influence
	m.target_node = m.get_path_to(target)
	return m


# =============================================================================================
# Runtime
# =============================================================================================

func on_state_changed(_old: StringName, new_state: StringName) -> void:
	if tree == null:
		return
	var entry: Array = STATE_MAP.get(new_state, [&"loco", 0.25])
	var inp: StringName = entry[0]
	if not inp in _inputs:
		inp = &"loco"
	_transition.xfade_time = float(entry[1])
	if inp != _current_input:
		_current_input = inp
		tree.set(&"parameters/state/transition_request", String(inp))


func play_oneshot(clip: StringName, _upper_only := true) -> void:
	if tree == null:
		return
	if clip == &"meow" and has_clip(&"meow"):
		tree.set(&"parameters/head_shot/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)


func notify(_what: StringName, _value: Variant) -> void:
	pass


func set_first_person(amount: float) -> void:
	var hide := amount > 0.85
	if hide == _hidden_fpp:
		return
	_hidden_fpp = hide
	for gi in _fpp_meshes:
		if is_instance_valid(gi):
			gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if hide else GeometryInstance3D.SHADOW_CASTING_SETTING_ON


func get_gait_phase() -> float:
	return _gait_phase


func reset_dynamics() -> void:
	if springs != null:
		springs.reset()


func _process(delta: float) -> void:
	if player == null:
		return
	var spd := absf(float(player.call(&"get_speed_along_facing")))
	var state: StringName = player.call(&"get_state")
	var sneaking: bool = player.call(&"is_sneaking")
	_sneak_amount = move_toward(_sneak_amount, 1.0 if sneaking else 0.0, delta * 4.0)
	var gait_pos := _gait_coord(spd)
	var ts := 1.0
	if gait_pos > 0.05:
		ts = clampf(spd / gait_pos, 0.5, 2.0)
	var sneak_pos := minf(spd, GAIT[&"sneak"])
	var sneak_ts := clampf(spd / maxf(sneak_pos, 0.05), 0.5, 2.0) if spd > 0.05 else 1.0
	var loco_ts := lerpf(ts, sneak_ts, _sneak_amount)
	if tree != null:
		tree.set(&"parameters/loco/gait/blend_position", gait_pos)
		tree.set(&"parameters/loco/sneak/blend_position", sneak_pos)
		tree.set(&"parameters/loco/sneak_blend/blend_amount", _sneak_amount)
		tree.set(&"parameters/loco/loco_ts/scale", loco_ts)
		tree.set(&"parameters/balance/blend_position", minf(spd, GAIT[&"balance_walk"]))
		tree.set(&"parameters/state_ts/scale", _state_time_scale(state, spd))
	# gait phase (head-bob, footsteps): dominant clip's normalised time
	var clip := &"walk"
	if sneaking:
		clip = &"sneak"
	elif gait_pos > (GAIT[&"trot"] + GAIT[&"run"]) * 0.5:
		clip = &"run"
	elif gait_pos > (GAIT[&"walk"] + GAIT[&"trot"]) * 0.5:
		clip = &"trot"
	var length := get_clip_length(clip)
	if length <= 0.0:
		length = 1.0
	if spd > 0.03 and _current_input == &"loco":
		_gait_phase = fmod(_gait_phase + delta * loco_ts / length, 1.0)


## Speed → blend-space coordinate so that each of the player's gait speeds lands exactly on the
## authored clip (the TimeScale then makes the feet match the real ground speed).
func _gait_coord(spd: float) -> float:
	var ws: float = player.get(&"walk_speed")
	var ts: float = player.get(&"trot_speed")
	var rs: float = player.get(&"run_speed")
	if spd <= ws:
		return spd / ws * GAIT[&"walk"]
	if spd <= ts:
		return lerpf(GAIT[&"walk"], GAIT[&"trot"], (spd - ws) / maxf(ts - ws, 0.01))
	return lerpf(GAIT[&"trot"], GAIT[&"run"], clampf((spd - ts) / maxf(rs - ts, 0.01), 0.0, 1.0))


func _state_time_scale(state: StringName, spd: float) -> float:
	match state:
		&"turn_left_90", &"turn_right_90":
			var tl: float = player.call(&"get_turn_duration")
			var cl := get_clip_length(state)
			return clampf(cl / maxf(tl, 0.1), 0.6, 2.2) if cl > 0.0 else 1.0
		&"climb":
			var cs: float = player.get(&"climb_speed")
			return clampf(spd / maxf(cs, 0.1), 0.0, 1.8)
		&"scramble":
			return 1.9
		&"swim":
			return 0.75
		&"land_hard":
			return 1.15
		&"stand_up":
			return 1.3
		&"stretch":
			return 1.2
		_:
			return 1.0
