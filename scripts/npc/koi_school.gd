extends Node3D
## Koi school in the lake (owner: world-life). Spawned at an `npc_spawn` marker with npc_kind koi;
## the marker sits on the WATER SURFACE; the swim volume is a box of meta `volume_size`
## (default 8 × 0.8 × 6 m, marker-local, centred in XZ, extending downward).
## Boids (separation / alignment / cohesion + wander + soft volume walls), swim-wave shader with
## per-fish variety (shaders/npc_koi.gdshader). Curious koi gather and rise toward Cam when she
## sits still at the edge; they scatter when she swipes/splashes or moves suddenly close by.

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const SHADER := preload("res://shaders/npc_koi.gdshader")

var size := Vector3(5, 0.8, 4)
## Marker-local Y of the water surface (0 when the marker sits on it) and of the lake bed.
var surface_y := 0.0
var bed_y := -INF
var fish: Array[Dictionary] = []
var director: Node = null
var lod := 0
var _mat: ShaderMaterial = null
var _rng := RandomNumberGenerator.new()
var _scare_t := 0.0
var _scare_from := Vector3.ZERO
static var _mesh: ArrayMesh = null


func setup(marker: Node3D, n: int) -> void:
	_rng.randomize()
	add_to_group(&"npc")
	set_meta(&"npc_kind", "koi")
	global_transform = marker.global_transform
	var vs: Variant = NpcUtil.meta_or(marker, &"volume_size", size)
	if vs is Vector3:
		size = vs
	_fit_to_water(marker)
	_mat = ShaderMaterial.new()
	_mat.shader = SHADER
	var glb := "res://assets/models/npc/koi.glb"
	for i in n:
		var mi := MeshInstance3D.new()
		mi.name = "Koi%d" % i
		var length := _rng.randf_range(0.32, 0.62)
		var scl := length
		if ResourceLoader.exists(glb):
			var inst := NpcUtil.scene(glb).instantiate() as Node3D
			mi.add_child(inst)
			scl = length / 0.5          # creatures' koi is authored ~0.5 m long
			var ap := inst.find_child("AnimationPlayer", true, false) as AnimationPlayer
			if ap != null and ap.has_animation(&"swim"):
				ap.get_animation(&"swim").loop_mode = Animation.LOOP_LINEAR
				ap.play(&"swim")
				ap.seek(_rng.randf() * ap.current_animation_length, true)
		else:
			mi.mesh = _fish_mesh()
			mi.material_override = _mat
		mi.scale = Vector3.ONE * scl
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		var variety := float([0, 0, 0, 1, 2, 3, 3, 4][_rng.randi() % 8])
		if mi.mesh != null:
			mi.set_instance_shader_parameter(&"pattern_seed", _rng.randf() * 10.0)
			mi.set_instance_shader_parameter(&"variety", variety)
		var p := Vector3(_rng.randf_range(-0.4, 0.4) * size.x, surface_y - _rng.randf_range(0.2, 0.8) * size.y, _rng.randf_range(-0.4, 0.4) * size.z)
		var v := Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)).normalized() * 0.25
		fish.append({"node": mi, "pos": p, "vel": v, "phase": _rng.randf() * TAU, "len": scl, "wander": _rng.randf() * TAU})
		mi.position = p
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_noise.connect(_on_noise)


## Uses the world's water Area3D (group "water", meta water_level) and a ray to the lake bed so a
## marker placed anywhere in the lake (surface or mid-water) yields a valid swim volume.
func _fit_to_water(marker: Node3D) -> void:
	var p := marker.global_position
	for a: Node in NpcUtil.nodes_in(get_tree(), &"water"):
		if a is Node3D and a.has_meta(&"water_level"):
			var wy := float(a.get_meta(&"water_level"))
			if absf(wy - p.y) < 3.0:
				surface_y = wy - p.y
				break
	var hit := NpcUtil.ray(get_world_3d(), p + Vector3.UP * (surface_y + 0.05), p - Vector3.UP * 6.0, NpcUtil.LAYER_WORLD)
	if not hit.is_empty():
		bed_y = (hit["position"] as Vector3).y - p.y
		if bed_y > surface_y - 0.3:
			bed_y = -INF    # marker sits on solid ground: ignore, trust volume_size


## Lathe-built koi: elliptical cross-sections along Z (+Z nose), forked tail fin, pectoral fins.
static func _fish_mesh() -> ArrayMesh:
	if _mesh != null:
		return _mesh
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings := 18
	var segs := 14
	var prof := func(t: float) -> Vector2:   # t 0 nose .. 1 tail-root → (half width, half height)
		var w := sin(clampf(t, 0.0, 1.0) * PI * 0.92 + 0.12) * (1.0 - t * 0.55)
		return Vector2(0.085 * w + 0.004, 0.105 * w + 0.004)
	var verts: Array[PackedVector3Array] = []
	for r in rings + 1:
		var t := float(r) / float(rings)
		var z := 0.5 - t * 0.78
		var wh: Vector2 = prof.call(t)
		var ring := PackedVector3Array()
		for s in segs:
			var a := TAU * float(s) / float(segs)
			ring.append(Vector3(cos(a) * wh.x, sin(a) * wh.y - (0.02 * wh.y if sin(a) < 0.0 else 0.0), z))
		verts.append(ring)
	for r in rings:
		for s in segs:
			var s2 := (s + 1) % segs
			var a0 := verts[r][s]
			var a1 := verts[r][s2]
			var b0 := verts[r + 1][s]
			var b1 := verts[r + 1][s2]
			st.add_vertex(a0); st.add_vertex(b0); st.add_vertex(a1)
			st.add_vertex(a1); st.add_vertex(b0); st.add_vertex(b1)
	# tail fin (two lobes, double-sided via shader cull_disabled)
	var root_z := 0.5 - 0.78
	var tail := [Vector3(0, 0.0, root_z + 0.02), Vector3(0, 0.12, -0.5), Vector3(0, 0.02, -0.4),
		Vector3(0, -0.12, -0.5)]
	st.add_vertex(tail[0]); st.add_vertex(tail[1]); st.add_vertex(tail[2])
	st.add_vertex(tail[0]); st.add_vertex(tail[2]); st.add_vertex(tail[3])
	# dorsal fin
	st.add_vertex(Vector3(0, 0.09, 0.15)); st.add_vertex(Vector3(0, 0.13, -0.02)); st.add_vertex(Vector3(0, 0.07, -0.15))
	# pectoral fins
	for sx: float in [-1.0, 1.0]:
		st.add_vertex(Vector3(sx * 0.07, -0.05, 0.28)); st.add_vertex(Vector3(sx * 0.17, -0.08, 0.2)); st.add_vertex(Vector3(sx * 0.07, -0.05, 0.18))
	st.generate_normals()
	_mesh = st.commit()
	return _mesh


func _physics_process(delta: float) -> void:
	if lod >= 3:
		return
	_scare_t = maxf(_scare_t - delta, 0.0)
	var player := _player()
	var lp := to_local(player.global_position) if player != null else Vector3.INF
	var curious := false
	if player != null and _scare_t <= 0.0:
		var still := NpcUtil.player_velocity(player).length() < 0.15
		var near_edge := absf(lp.y) < 1.2 and absf(lp.x) < size.x * 0.5 + 1.2 and absf(lp.z) < size.z * 0.5 + 1.2
		curious = still and near_edge
		if near_edge and NpcUtil.player_velocity(player).length() > 2.0 and Vector2(lp.x, lp.z).length() < size.length() * 0.5:
			scare(player.global_position)
	var hx := size.x * 0.5
	var hz := size.z * 0.5
	for i in fish.size():
		var f: Dictionary = fish[i]
		var pos: Vector3 = f["pos"]
		var vel: Vector3 = f["vel"]
		var steer := Vector3.ZERO
		var coh := Vector3.ZERO
		var ali := Vector3.ZERO
		var n := 0
		for j in fish.size():
			if j == i:
				continue
			var o: Dictionary = fish[j]
			var d: Vector3 = (o["pos"] as Vector3) - pos
			var dl := d.length()
			if dl < 1.6:
				coh += o["pos"]
				ali += o["vel"]
				n += 1
				if dl < 0.45 and dl > 0.001:
					steer -= d / dl * (0.45 - dl) * 2.5
		if n > 0:
			steer += ((coh / n) - pos) * 0.15 + ((ali / n) - vel) * 0.4
		f["wander"] = float(f["wander"]) + _rng.randf_range(-1.0, 1.0) * delta * 2.0
		var w := float(f["wander"])
		steer += Vector3(cos(w), 0, sin(w)) * 0.12
		# volume walls (soft)
		if pos.x > hx - 0.6: steer.x -= (pos.x - hx + 0.6) * 2.0
		if pos.x < -hx + 0.6: steer.x += (-hx + 0.6 - pos.x) * 2.0
		if pos.z > hz - 0.6: steer.z -= (pos.z - hz + 0.6) * 2.0
		if pos.z < -hz + 0.6: steer.z += (-hz + 0.6 - pos.z) * 2.0
		var top := surface_y - 0.12
		var bottom := maxf(surface_y - size.y + 0.1, bed_y + 0.12)
		if pos.y > top: steer.y -= (pos.y - top) * 4.0
		if pos.y < bottom: steer.y += (bottom - pos.y) * 4.0
		var max_sp := 0.45
		if curious:
			var tgt := Vector3(clampf(lp.x, -hx + 0.3, hx - 0.3), surface_y - 0.15, clampf(lp.z, -hz + 0.3, hz - 0.3))
			steer += (tgt - pos).normalized() * 0.5
		if _scare_t > 0.0:
			var away := pos - to_local(_scare_from)
			away.y = -0.5
			steer += away.normalized() * 3.0
			max_sp = 1.8
		vel += steer * delta
		var sp := vel.length()
		if sp > max_sp:
			vel = vel / sp * max_sp
		elif sp < 0.08:
			vel = vel / maxf(sp, 0.001) * 0.08
		pos += vel * delta
		f["pos"] = pos
		f["vel"] = vel
		var speed_n := clampf(vel.length() / 0.45, 0.0, 2.0)
		f["phase"] = float(f["phase"]) + delta * (2.5 + speed_n * 7.0)
		var node := f["node"] as MeshInstance3D
		var fwd := Vector3(vel.x, vel.y * 0.4, vel.z)
		var basis := NpcUtil.basis_facing(fwd)
		var old_fwd := node.basis.z.normalized()
		var turn := clampf(old_fwd.cross(basis.z.normalized()).y * 30.0, -1.0, 1.0)
		node.transform = Transform3D(basis.scaled(Vector3.ONE * float(f["len"])), pos)
		if lod <= 1 and node.mesh != null:
			node.set_instance_shader_parameter(&"swim_phase", float(f["phase"]))
			node.set_instance_shader_parameter(&"swim_speed", speed_n)
			node.set_instance_shader_parameter(&"turn", turn)


func scare(from: Vector3) -> void:
	_scare_t = 2.5
	_scare_from = from
	NpcUtil.sfx(&"splash_small", from, -10.0)


func _on_noise(pos: Vector3, loud: float) -> void:
	if loud > 0.25 and pos.distance_to(global_position) < maxf(size.x, size.z) * 0.5 + 2.0:
		scare(pos)


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func set_lod(l: int, _interval: float) -> void:
	lod = l
	visible = l < 3


func mean_speed() -> float:
	var s := 0.0
	for f: Dictionary in fish:
		s += (f["vel"] as Vector3).length()
	return s / maxf(fish.size(), 1)
