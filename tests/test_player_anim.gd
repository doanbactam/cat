extends "res://tests/test_player_base.gd"
## Animation layer: real cat.glb clips + loop flags, AnimationTree state mapping, gait speed
## matching, skeleton-modifier stack (foot IK reacting to the ground, head look-at, spring
## bones), mouth / eye sockets.

const CONTRACT_CLIPS: Array[StringName] = [
	&"idle", &"idle_look", &"walk", &"trot", &"run", &"sneak", &"sneak_idle", &"jump_crouch",
	&"jump_up", &"fall", &"land", &"land_hard", &"sit_down", &"sit_idle", &"stand_up", &"lie_down",
	&"sleep", &"groom", &"meow", &"hiss", &"swipe", &"scratch", &"climb", &"turn_left_90",
	&"turn_right_90", &"drink", &"eat", &"knead", &"stretch", &"balance_walk", &"pickup", &"knock",
]
const LOOPS: Array[StringName] = [&"idle", &"walk", &"trot", &"run", &"sneak", &"fall", &"sit_idle", &"sleep", &"groom", &"climb", &"balance_walk"]


func _anim() -> Node:
	return player.call(&"get_animator")


## Godot 4.7 restores the animated (pre-modifier) pose after each skeleton update, so the result
## of the SkeletonModifier3D stack (IK, look-at, springs) is only observable inside
## `skeleton_updated`. Returns the bone's world transform as rendered on the next update.
func _posed(sk: Skeleton3D, bone: int) -> Transform3D:
	var out: Array[Transform3D] = []
	var cb := func() -> void:
		if out.is_empty():
			out.append(sk.global_transform * sk.get_bone_global_pose(bone))
	sk.skeleton_updated.connect(cb)
	for i in 30:
		await tree.process_frame
		if not out.is_empty():
			break
	sk.skeleton_updated.disconnect(cb)
	return out[0] if not out.is_empty() else sk.global_transform * sk.get_bone_global_pose(bone)


func test_uses_real_cat_model() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var model: Node3D = p.call(&"get_model")
	assert_not_null(model, "cat.glb instanced under Visual")
	assert_true(model.scene_file_path == "res://assets/models/cat/cat.glb", "model from the contract path (%s)" % model.scene_file_path)
	var a := _anim()
	assert_not_null(a, "animator")
	assert_not_null(a.get(&"skeleton"), "skeleton found")
	assert_not_null(a.get(&"tree"), "AnimationTree built")


func test_clips_and_loops() -> void:
	ground()
	spawn_player(Vector3.ZERO)
	await settle()
	var a := _anim()
	for c in CONTRACT_CLIPS:
		assert_true(bool(a.call(&"has_clip", c)), "clip " + String(c))
	var ap: AnimationPlayer = a.get(&"anim_player")
	for c in LOOPS:
		assert_eq(ap.get_animation(c).loop_mode, Animation.LOOP_LINEAR, "loop " + String(c))
	assert_eq(ap.get_animation(&"land").loop_mode, Animation.LOOP_NONE, "land is one-shot")


func test_state_drives_tree() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var a := _anim()
	assert_eq(a.get(&"_current_input"), &"loco")
	hold(&"jump")
	await step(4)
	assert_eq(a.get(&"_current_input"), &"jump_crouch", "crouch clip while charging")
	release(&"jump")
	await step(3)
	assert_eq(a.get(&"_current_input"), &"jump_up", "jump clip in the air")
	await wait_until(func() -> bool: return int(p.call(&"get_mode")) == 0, 2.0)
	await step(2)
	assert_true(a.get(&"_current_input") in [&"land", &"loco"], "land / loco after touching down")


func test_gait_playback_matches_speed() -> void:
	ground(60.0)
	var p := spawn_player(Vector3.ZERO)
	await settle()
	hold(&"move_forward")
	await seconds(1.2)
	var a := _anim()
	var tree: AnimationTree = a.get(&"tree")
	var pos: float = tree.get(&"parameters/loco/gait/blend_position")
	var ts: float = tree.get(&"parameters/loco/loco_ts/scale")
	var spd := absf(float(p.call(&"get_speed_along_facing")))
	assert_near(pos, 1.6, 0.08, "full stick lands on the trot clip")
	assert_near(ts * pos, spd, 0.12, "time scale × authored speed = real speed (no foot sliding)")
	var ph0: float = p.call(&"get_gait_phase")
	await step(6)
	assert_true(absf(float(p.call(&"get_gait_phase")) - ph0) > 0.01, "gait phase advances")


func test_foot_ik_lifts_paw_on_raised_ground() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	await seconds(0.4)
	var a := _anim()
	var sk: Skeleton3D = a.get(&"skeleton")
	var hand := sk.find_bone("hand_L")
	var flat_y := (await _posed(sk, hand)).origin.y
	# a 4 cm tile under the left front paw only
	var paw := sk.global_transform * sk.get_bone_global_pose(sk.find_bone("finger_L")).origin
	box(Vector3(paw.x + 0.015, 0.02, paw.z - 0.01), Vector3(0.07, 0.04, 0.11))
	await seconds(0.5)
	var raised_y := (await _posed(sk, hand)).origin.y
	assert_true(raised_y > flat_y + 0.02, "IK lifts the paw onto the tile (%.3f → %.3f)" % [flat_y, raised_y])
	var ik: TwoBoneIK3D = a.get(&"foot_ik")
	assert_not_null(ik, "TwoBoneIK3D present")
	assert_eq(ik.setting_count, 4, "4 legs")


func test_head_looks_at_target() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var a := _anim()
	var sk: Skeleton3D = a.get(&"skeleton")
	var head := sk.find_bone("head")
	var look: Node3D = p.call(&"get_look_target")
	# force a point of interest to the cat's left (+X), then compare the head direction
	var rig: Node3D = p.call(&"get_camera_rig")
	rig.set(&"yaw", -PI * 0.5)   # camera looks along +X → the cat glances there
	await seconds(1.0)
	var fwd_left := (await _posed(sk, head)).basis.y
	rig.set(&"yaw", PI * 0.5)    # camera looks along -X
	await seconds(1.0)
	var fwd_right := (await _posed(sk, head)).basis.y
	assert_not_null(look)
	assert_true(fwd_left.x > fwd_right.x + 0.3, "head turns with the look target (%.2f vs %.2f)" % [fwd_left.x, fwd_right.x])


func test_spring_bones_and_sockets() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var a := _anim()
	var springs: SpringBoneSimulator3D = a.get(&"springs")
	assert_not_null(springs, "SpringBoneSimulator3D present")
	assert_eq(springs.setting_count, 3, "tail + 2 ears")
	assert_eq(springs.get_root_bone_name(0), "tail_01")
	var mouth: Node3D = p.call(&"get_mouth_attachment")
	assert_true(mouth is BoneAttachment3D and (mouth as BoneAttachment3D).bone_name == "mouth_socket", "mouth socket on mouth_socket bone")
	var eye: Transform3D = p.call(&"get_eye_transform_interpolated")
	assert_true(eye.origin.y > 0.2 and eye.origin.y < 0.34, "eye socket height (%.3f)" % eye.origin.y)
	assert_true(eye.origin.z > 0.12, "eyes at the front of the head (%.3f)" % eye.origin.z)


func test_fur_built_from_settings() -> void:
	ground()
	var p := spawn_player(Vector3.ZERO)
	await settle()
	var fur: FurShells = p.get_node(^"Fur") as FurShells
	assert_not_null(fur, "FurShells node")
	assert_eq(fur.get_active_shell_count(), 24, "default graphics/fur_shells = 24")
	assert_true(fur.mesh_instance != null and fur.mesh_instance.name == "CatBody", "on CatBody")
	assert_true(fur.mesh_instance.material_override is ShaderMaterial, "fur base material")
	var n := 0
	var m: Material = fur.mesh_instance.material_override
	while m.next_pass != null:
		n += 1
		m = m.next_pass
	assert_eq(n, 24, "24 shell passes chained")
	fur.set_shell_count(0)
	assert_true(fur.mesh_instance.material_override.next_pass == null, "0 disables shells")
