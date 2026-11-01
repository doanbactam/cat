extends Node3D
## Precision-jump feedback (owner: player): a subtle landing ring on the target surface (aligned to
## its normal, squashed on beams) and a dotted preview of the solved arc. Fades in/out.

const JumpPlanner := preload("res://scripts/player/jump_planner.gd")
const RING_SHADER := preload("res://shaders/player_jump_reticle.gdshader")
const ARC_SHADER := preload("res://shaders/player_jump_arc.gdshader")
const ARC_DOTS := 16

var _ring: MeshInstance3D
var _ring_mat: ShaderMaterial
var _arc: MultiMeshInstance3D
var _arc_mat: ShaderMaterial
var _alpha := 0.0
var _visible_goal := false
var _ring_pos := Vector3.ZERO
var _has_pos := false


func _ready() -> void:
	top_level = true
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	global_transform = Transform3D.IDENTITY
	_ring_mat = ShaderMaterial.new()
	_ring_mat.shader = RING_SHADER
	_ring_mat.render_priority = 30
	var q := QuadMesh.new()
	q.size = Vector2(0.3, 0.3)
	q.orientation = PlaneMesh.FACE_Y
	_ring = MeshInstance3D.new()
	_ring.name = "Ring"
	_ring.mesh = q
	_ring.material_override = _ring_mat
	_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_ring.top_level = true
	add_child(_ring)
	_arc_mat = ShaderMaterial.new()
	_arc_mat.shader = ARC_SHADER
	_arc_mat.render_priority = 29
	var dot := QuadMesh.new()
	dot.size = Vector2(0.035, 0.035)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = dot
	mm.instance_count = ARC_DOTS
	_arc = MultiMeshInstance3D.new()
	_arc.name = "Arc"
	_arc.multimesh = mm
	_arc.material_override = _arc_mat
	_arc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_arc.extra_cull_margin = 8.0
	_arc.top_level = true
	add_child(_arc)
	_apply_alpha()


## target: JumpPlanner result (point, normal, v0, time, narrow); origin = the cat's feet.
func show_target(target: Dictionary, origin: Vector3, gravity: float, charge: float) -> void:
	var p: Vector3 = target["point"]
	var n: Vector3 = target.get("normal", Vector3.UP)
	if n.length_squared() < 0.01:
		n = Vector3.UP
	n = n.normalized()
	if not _has_pos or _ring_pos.distance_to(p) > 0.6:
		_ring_pos = p
	else:
		_ring_pos = _ring_pos.lerp(p, 0.5)
	_has_pos = true
	var flat := Vector3(p.x - origin.x, 0.0, p.z - origin.z)
	var fwd := flat.normalized() if flat.length_squared() > 0.0001 else Vector3.FORWARD
	var x := fwd.cross(n).normalized()
	var z := n.cross(x).normalized()
	var dist := origin.distance_to(p)
	var s := clampf(0.8 + dist * 0.18, 0.8, 1.35)
	_ring.global_transform = Transform3D(Basis(x, n, z).scaled(Vector3(s, 1.0, s)), _ring_pos + n * 0.006)
	_ring_mat.set_shader_parameter(&"charge", charge)
	_ring_mat.set_shader_parameter(&"narrow", 1.0 if bool(target.get("narrow", false)) else 0.0)
	# arc dots along the solved parabola
	if target.has("v0"):
		var v0: Vector3 = target["v0"]
		var t_total := float(target["time"])
		var mm := _arc.multimesh
		for i in ARC_DOTS:
			var f := float(i + 1) / float(ARC_DOTS + 1)
			var pt := JumpPlanner.arc_point(origin, v0, gravity, t_total * f) + Vector3.UP * 0.12 * (1.0 - f)
			mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, pt))
			mm.set_instance_custom_data(i, Color(f, 0.0, 0.0, 0.0))
		_arc.visible = true
	else:
		_arc.visible = false
	_visible_goal = true


func hide_target() -> void:
	_visible_goal = false


func is_showing() -> bool:
	return _visible_goal


func _process(delta: float) -> void:
	var goal := 1.0 if _visible_goal else 0.0
	_alpha = move_toward(_alpha, goal, delta / 0.12)
	_apply_alpha()


func _apply_alpha() -> void:
	_ring.visible = _alpha > 0.01
	_arc.visible = _arc.visible and _alpha > 0.01
	_ring_mat.set_shader_parameter(&"opacity", 0.6 * _alpha)
	_arc_mat.set_shader_parameter(&"opacity", 0.45 * _alpha)
	if _alpha <= 0.01:
		_has_pos = false
