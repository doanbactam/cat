extends Node3D
## Small physical effects around Cam (owner: player): landing/take-off dust puffs tinted by the
## surface, water splashes (droplets + expanding ring), swim ripples and drips from wet fur.
## One-shot GPUParticles3D are spawned into the world and freed after their lifetime.

const SURFACE_DUST := {
	&"asphalt": Color(0.36, 0.35, 0.33), &"concrete": Color(0.55, 0.53, 0.5), &"dirt": Color(0.45, 0.36, 0.26),
	&"roof_tile": Color(0.55, 0.36, 0.27), &"wood": Color(0.48, 0.4, 0.3), &"tile": Color(0.6, 0.58, 0.55),
	&"grass": Color(0.35, 0.42, 0.25), &"fabric": Color(0.6, 0.58, 0.55),
}

var _soft_tex: GradientTexture2D
var _dust_mat: StandardMaterial3D
var _water_mat: StandardMaterial3D
var _ring_mat: StandardMaterial3D
var _quad: QuadMesh
var _drop_mesh: QuadMesh


func _ready() -> void:
	top_level = true
	global_transform = Transform3D.IDENTITY
	_soft_tex = GradientTexture2D.new()
	_soft_tex.fill = GradientTexture2D.FILL_RADIAL
	_soft_tex.fill_from = Vector2(0.5, 0.5)
	_soft_tex.fill_to = Vector2(1.0, 0.5)
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(1, 1, 1, 0))
	_soft_tex.gradient = g
	_soft_tex.width = 64
	_soft_tex.height = 64
	_dust_mat = _particle_material(_soft_tex, false)
	_water_mat = _particle_material(_soft_tex, false)
	_water_mat.albedo_color = Color(0.85, 0.92, 0.95, 0.7)
	_water_mat.metallic_specular = 0.9
	_water_mat.roughness = 0.1
	_water_mat.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
	_ring_mat = StandardMaterial3D.new()
	_ring_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_ring_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_ring_mat.vertex_color_use_as_albedo = true
	_ring_mat.albedo_texture = _ring_texture()
	_ring_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_quad = QuadMesh.new()
	_quad.size = Vector2(0.12, 0.12)
	_drop_mesh = QuadMesh.new()
	_drop_mesh.size = Vector2(0.012, 0.018)


func _particle_material(tex: Texture2D, additive: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if additive else BaseMaterial3D.BLEND_MODE_MIX
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.vertex_color_use_as_albedo = true
	m.albedo_texture = tex
	m.proximity_fade_enabled = true
	m.proximity_fade_distance = 0.05
	return m


func _ring_texture() -> GradientTexture2D:
	var t := GradientTexture2D.new()
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.72, 0.86, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, 0), Color(1, 1, 1, 0.8), Color(1, 1, 1, 0)])
	t.gradient = g
	t.width = 128
	t.height = 128
	return t


func _world_parent() -> Node:
	var p := get_parent()
	if p != null and p.get_parent() != null:
		return p.get_parent()
	return get_tree().current_scene if get_tree() != null else null


func _spawn(parts: GPUParticles3D, pos: Vector3, life: float) -> void:
	var parent := _world_parent()
	if parent == null:
		parts.free()
		return
	parent.add_child(parts)
	parts.global_position = pos
	parts.one_shot = true
	parts.emitting = true
	get_tree().create_timer(life + parts.lifetime + 0.2).timeout.connect(parts.queue_free)


## Dust kicked up by take-offs and landings (strength 0..1.5).
func puff(pos: Vector3, strength: float, surface: StringName) -> void:
	if surface == &"water" or surface == &"metal" or surface == &"plastic":
		return
	var col: Color = SURFACE_DUST.get(surface, Color(0.55, 0.53, 0.5))
	if GameState.get_weather() in [&"rain", &"storm"]:
		return  # wet ground does not dust
	var p := GPUParticles3D.new()
	p.amount = int(8 + 16 * clampf(strength, 0.0, 1.5))
	p.lifetime = 0.9
	p.explosiveness = 0.92
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pm.emission_ring_axis = Vector3.UP
	pm.emission_ring_radius = 0.1
	pm.emission_ring_inner_radius = 0.04
	pm.emission_ring_height = 0.01
	pm.direction = Vector3(0, 0.3, 0)
	pm.spread = 80.0
	pm.flatness = 0.7
	pm.initial_velocity_min = 0.15 * strength
	pm.initial_velocity_max = 0.55 * strength
	pm.gravity = Vector3(0, -0.15, 0)
	pm.damping_min = 1.2
	pm.damping_max = 2.2
	pm.scale_min = 0.5
	pm.scale_max = 1.4
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.4))
	sc.add_point(Vector2(1, 1.6))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.set_color(0, Color(col.r, col.g, col.b, 0.32 * clampf(strength, 0.3, 1.0)))
	grad.set_color(1, Color(col.r, col.g, col.b, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	p.draw_pass_1 = _quad
	p.material_override = _dust_mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_spawn(p, pos + Vector3.UP * 0.02, 0.1)


## Falling into water: droplet crown + expanding ring.
func splash(pos: Vector3, strength: float) -> void:
	var p := GPUParticles3D.new()
	p.amount = int(30 + 50 * clampf(strength, 0.0, 1.5))
	p.lifetime = 0.9
	p.explosiveness = 0.95
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pm.emission_ring_axis = Vector3.UP
	pm.emission_ring_radius = 0.12
	pm.emission_ring_inner_radius = 0.05
	pm.emission_ring_height = 0.01
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 28.0
	pm.initial_velocity_min = 1.2 * strength
	pm.initial_velocity_max = 2.6 * strength
	pm.gravity = Vector3(0, -9.8, 0)
	pm.scale_min = 0.6
	pm.scale_max = 1.3
	var grad := Gradient.new()
	grad.set_color(0, Color(0.9, 0.95, 1.0, 0.85))
	grad.set_color(1, Color(0.9, 0.95, 1.0, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var drop := QuadMesh.new()
	drop.size = Vector2(0.018, 0.03)
	p.draw_pass_1 = drop
	p.material_override = _water_mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_spawn(p, pos, 0.1)
	ripple(pos, 1.6 * strength)
	ripple(pos, 1.0 * strength)


## Expanding ring on the water surface.
func ripple(pos: Vector3, size: float) -> void:
	var p := GPUParticles3D.new()
	p.amount = 1
	p.lifetime = 1.3
	p.explosiveness = 1.0
	var pm := ParticleProcessMaterial.new()
	pm.particle_flag_disable_z = false
	pm.gravity = Vector3.ZERO
	pm.initial_velocity_min = 0.0
	pm.initial_velocity_max = 0.0
	pm.scale_min = 1.0
	pm.scale_max = 1.0
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.15))
	sc.add_point(Vector2(1, 1.0))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.set_color(0, Color(0.9, 0.95, 1.0, 0.55))
	grad.set_color(1, Color(0.9, 0.95, 1.0, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	var plane := PlaneMesh.new()
	plane.size = Vector2(0.5, 0.5) * maxf(size, 0.3)
	p.draw_pass_1 = plane
	p.material_override = _ring_mat
	p.local_coords = true
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_spawn(p, pos + Vector3.UP * 0.004, 0.1)


## A couple of drops falling from wet fur.
func drip(pos: Vector3) -> void:
	var p := GPUParticles3D.new()
	p.amount = 2
	p.lifetime = 0.5
	p.explosiveness = 0.6
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = Vector3(0.05, 0.02, 0.12)
	pm.direction = Vector3.DOWN
	pm.spread = 5.0
	pm.initial_velocity_min = 0.0
	pm.initial_velocity_max = 0.1
	pm.gravity = Vector3(0, -9.8, 0)
	var grad := Gradient.new()
	grad.set_color(0, Color(0.9, 0.95, 1.0, 0.7))
	grad.set_color(1, Color(0.9, 0.95, 1.0, 0.4))
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	p.draw_pass_1 = _drop_mesh
	p.material_override = _water_mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_spawn(p, pos, 0.1)
