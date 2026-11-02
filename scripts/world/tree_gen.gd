extends RefCounted
## Procedural trees for Hàng Mây (owner: world): street trees (sấu / xà cừ-like), the two giant
## banyans (đa) with buttress roots and hanging aerial roots, small ornamental trees, and lotus.
## Used only while assets/models/nature/ has no matching catalog entry (logged in
## docs/placeholders.md); the builder prefers nature catalog models when they exist.
##
## make_tree(kind, seed) → Node3D with "Trunk" (bark), "Leaves" (alpha cards, foliage shader),
## and a StaticBody3D "Collision" (trunk cylinder on layers 1+6 = climbable; banyans also get box
## colliders along their main limbs so the cat can walk out on them).

const MU := preload("res://scripts/world/mesh_util.gd")

const LEAF_CELLS := {
	&"street": Rect2(0.0, 0.0, 0.5, 0.5),
	&"ficus": Rect2(0.5, 0.0, 0.5, 0.5),
	&"twig": Rect2(0.0, 0.5, 0.5, 0.5),
}

static var _bark_mat: Material
static var _leaf_mats: Dictionary = {}


static func bark_material() -> Material:
	if _bark_mat == null:
		var m := StandardMaterial3D.new()
		m.resource_name = "world_bark"
		m.albedo_texture = load("res://assets/textures/ground/bark_albedo.jpg")
		m.normal_enabled = true
		m.normal_texture = load("res://assets/textures/ground/bark_normal.png")
		m.normal_scale = 1.4
		m.roughness_texture = load("res://assets/textures/ground/bark_orm.jpg")
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.ao_enabled = true
		m.ao_texture = m.roughness_texture
		m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
		_bark_mat = m
	return _bark_mat


static func leaf_material(tint: Color) -> Material:
	var key := tint.to_html()
	if not _leaf_mats.has(key):
		var m := ShaderMaterial.new()
		m.resource_name = "world_leaves"
		m.shader = load("res://shaders/foliage.gdshader")
		m.set_shader_parameter(&"albedo_tex", load("res://assets/textures/ground/leaf_cluster_albedo.png"))
		m.set_shader_parameter(&"normal_tex", load("res://assets/textures/ground/leaf_cluster_normal.png"))
		m.set_shader_parameter(&"tint", tint)
		_leaf_mats[key] = m
	return _leaf_mats[key]


class Branch:
	var pts: PackedVector3Array
	var radii: PackedFloat32Array
	var depth: int


static func make_tree(kind: StringName, seed: int) -> Node3D:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var p := _params(kind, rng)
	var root := Node3D.new()
	root.name = "Tree_%s" % kind
	root.set_meta(&"tree_kind", kind)
	var branches: Array[Branch] = []
	var tips: Array = []     # [pos, dir, size]
	# trunk
	var trunk_h: float = p.trunk_h
	var trunk_r: float = p.trunk_r
	var lean: Vector3 = Vector3(rng.randf_range(-1, 1), 0, rng.randf_range(-1, 1)).normalized() * float(p.lean)
	var trunk := _grow_segment(Vector3.ZERO, (Vector3.UP + lean).normalized(), trunk_h, trunk_r, trunk_r * 0.72, 7, rng, 0.05)
	trunk.depth = 0
	branches.append(trunk)
	var top := trunk.pts[trunk.pts.size() - 1]
	# limbs
	var n_limbs: int = rng.randi_range(p.limbs_min, p.limbs_max)
	var limb_infos: Array = []
	for i in n_limbs:
		var a := TAU * (float(i) + rng.randf() * 0.6) / float(n_limbs)
		var up: float = rng.randf_range(p.limb_up_min, p.limb_up_max)
		var d := Vector3(cos(a), up, sin(a)).normalized()
		var start_t := rng.randf_range(0.7, 1.0)
		var start := trunk.pts[int(start_t * (trunk.pts.size() - 1))]
		var L: float = rng.randf_range(p.limb_len * 0.75, p.limb_len * 1.2)
		var b := _grow_segment(start, d, L, trunk_r * 0.62, trunk_r * 0.22, 6, rng, p.wiggle)
		b.depth = 1
		branches.append(b)
		limb_infos.append(b)
		_sub_branches(b, 2, int(p.depth), rng, p, branches, tips)
	# buttress roots / flare
	if p.buttress > 0:
		for i in int(p.buttress):
			var a := TAU * (float(i) + rng.randf() * 0.5) / float(p.buttress)
			var d := Vector3(cos(a), 0.0, sin(a))
			var pts := PackedVector3Array()
			var rad := PackedFloat32Array()
			for k in 6:
				var t := float(k) / 5.0
				pts.append(d * (trunk_r * 0.4 + t * trunk_r * 2.6) + Vector3.UP * (trunk_r * 1.6 * (1.0 - t) * (1.0 - t)) + Vector3(0, -0.05 * t, 0))
				rad.append(lerpf(trunk_r * 0.45, 0.08, t))
			var b := Branch.new()
			b.pts = pts
			b.radii = rad
			b.depth = 1
			branches.append(b)
	# aerial roots (banyan)
	if p.aerial > 0:
		for i in int(p.aerial):
			var src: Branch = branches[rng.randi_range(1, branches.size() - 1)]
			var sp := src.pts[rng.randi_range(1, src.pts.size() - 1)]
			if sp.y < 3.0:
				continue
			var reach_ground := rng.randf() < 0.45
			var end_y := 0.0 if reach_ground else sp.y * rng.randf_range(0.2, 0.7)
			var pts := PackedVector3Array()
			var rad := PackedFloat32Array()
			var segs := 6
			var drift := Vector3(rng.randf_range(-0.3, 0.3), 0, rng.randf_range(-0.3, 0.3))
			for k in segs + 1:
				var t := float(k) / float(segs)
				pts.append(sp + Vector3(0, (end_y - sp.y) * t, 0) + drift * t + Vector3(sin(t * 7.0 + i) * 0.05, 0, cos(t * 5.0 + i) * 0.05))
				rad.append(lerpf(0.035, 0.012, t) * (3.0 if reach_ground else 1.0))
			var b := Branch.new()
			b.pts = pts
			b.radii = rad
			b.depth = 3
			branches.append(b)
	# --- meshes ---
	var st := MU.new_st()
	for b in branches:
		var sides := 10 if b.depth == 0 else (7 if b.depth == 1 else 5)
		if b.depth >= 3:
			sides = 4
		MU.tube(st, b.pts, b.radii, sides, 1.6, maxf(1.0, roundf(b.radii[0] * 6.0)))
	var trunk_mesh := MU.commit(st, bark_material())
	var tm := MeshInstance3D.new()
	tm.name = "Trunk"
	tm.mesh = trunk_mesh
	root.add_child(tm)
	# leaves: card clusters at tips
	var lst := SurfaceTool.new()
	lst.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cell: Rect2 = LEAF_CELLS[p.leaf]
	var card_count := 0
	for tip: Array in tips:
		var pos: Vector3 = tip[0]
		var size: float = tip[2]
		for c in int(p.cards_per_tip):
			var off := Vector3(rng.randf_range(-1, 1), rng.randf_range(-0.4, 0.6), rng.randf_range(-1, 1)) * size * 0.45
			var yaw := rng.randf() * TAU
			var pitch := rng.randf_range(-0.6, 0.6)
			var basis := Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch)
			_card(lst, pos + off, basis, size * rng.randf_range(0.8, 1.2), cell, rng.randf())
			card_count += 1
	if card_count > 0:
		lst.generate_tangents()
		var lm := lst.commit()
		lm.surface_set_material(0, leaf_material(p.leaf_tint))
		var li := MeshInstance3D.new()
		li.name = "Leaves"
		li.mesh = lm
		li.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		root.add_child(li)
	# --- collision ---
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = 1 | (1 << 5)        # world + climbable
	body.collision_mask = 0
	body.set_meta(&"surface", &"wood")
	body.add_to_group(&"climbable")
	root.add_child(body)
	var cs := CollisionShape3D.new()
	var cyl := CylinderShape3D.new()
	cyl.radius = trunk_r * 0.95
	cyl.height = trunk_h
	cs.shape = cyl
	cs.position = Vector3(0, trunk_h * 0.5, 0) + lean * trunk_h * 0.5
	if lean.length() > 0.01:
		cs.basis = Basis(Vector3.UP.cross((Vector3.UP + lean).normalized()).normalized(), Vector3.UP.angle_to((Vector3.UP + lean).normalized())) if Vector3.UP.cross(lean).length() > 0.0001 else Basis()
	body.add_child(cs)
	if bool(p.walk_limbs):
		# flat-topped boxes along the first part of each limb (walkable, not climbable)
		var limb_body := StaticBody3D.new()
		limb_body.name = "LimbCollision"
		limb_body.collision_layer = 1
		limb_body.collision_mask = 0
		limb_body.set_meta(&"surface", &"wood")
		root.add_child(limb_body)
		for b: Branch in limb_infos:
			for k in range(0, b.pts.size() - 2):
				var a := b.pts[k]
				var c2 := b.pts[k + 1]
				var mid := (a + c2) * 0.5
				var seg := c2 - a
				if seg.length() < 0.05:
					continue
				var horiz := Vector3(seg.x, 0, seg.z)
				if horiz.length() < 0.05:
					continue
				var bs := BoxShape3D.new()
				var r := b.radii[k] * 0.9
				bs.size = Vector3(maxf(r * 1.4, 0.14), 0.12, seg.length())
				var shape := CollisionShape3D.new()
				shape.shape = bs
				shape.transform = Transform3D(Basis.looking_at(seg.normalized(), Vector3.UP), mid + Vector3.UP * (r - 0.06))
				limb_body.add_child(shape)
	root.set_meta(&"canopy_radius", p.limb_len * 1.1)
	root.set_meta(&"trunk_radius", trunk_r)
	root.set_meta(&"height", trunk_h + p.limb_len)
	return root


static func _params(kind: StringName, rng: RandomNumberGenerator) -> Dictionary:
	match kind:
		&"banyan":
			return {"trunk_h": 4.2, "trunk_r": 1.05, "lean": 0.08, "limbs_min": 6, "limbs_max": 8,
				"limb_up_min": 0.12, "limb_up_max": 0.55, "limb_len": 8.5, "depth": 4, "wiggle": 0.12,
				"buttress": 7, "aerial": 70, "leaf": &"ficus", "leaf_tint": Color(0.88, 0.95, 0.85),
				"cards_per_tip": 5, "tip_size": 2.6, "walk_limbs": true}
		&"street":
			return {"trunk_h": rng.randf_range(4.2, 5.6), "trunk_r": rng.randf_range(0.2, 0.28), "lean": 0.06,
				"limbs_min": 3, "limbs_max": 5, "limb_up_min": 0.5, "limb_up_max": 1.2, "limb_len": 3.6,
				"depth": 3, "wiggle": 0.1, "buttress": 0, "aerial": 0, "leaf": &"street",
				"leaf_tint": Color(0.95, 1.0, 0.9), "cards_per_tip": 4, "tip_size": 1.9, "walk_limbs": false}
		&"small":
			return {"trunk_h": 1.8, "trunk_r": 0.1, "lean": 0.1, "limbs_min": 3, "limbs_max": 4,
				"limb_up_min": 0.6, "limb_up_max": 1.4, "limb_len": 1.6, "depth": 2, "wiggle": 0.12,
				"buttress": 0, "aerial": 0, "leaf": &"street", "leaf_tint": Color(1.0, 1.0, 0.92),
				"cards_per_tip": 3, "tip_size": 1.2, "walk_limbs": false}
		_:
			return {"trunk_h": 5.0, "trunk_r": 0.32, "lean": 0.04, "limbs_min": 4, "limbs_max": 6,
				"limb_up_min": 0.4, "limb_up_max": 1.0, "limb_len": 4.5, "depth": 3, "wiggle": 0.1,
				"buttress": 3, "aerial": 0, "leaf": &"street", "leaf_tint": Color(0.92, 1.0, 0.88),
				"cards_per_tip": 4, "tip_size": 2.2, "walk_limbs": false}


static func _grow_segment(start: Vector3, dir: Vector3, length: float, r0: float, r1: float, segs: int, rng: RandomNumberGenerator, wiggle: float) -> Branch:
	var b := Branch.new()
	var pts := PackedVector3Array()
	var rad := PackedFloat32Array()
	var p := start
	var d := dir.normalized()
	for i in segs + 1:
		var t := float(i) / float(segs)
		pts.append(p)
		rad.append(lerpf(r0, r1, t))
		d = (d + Vector3(rng.randf_range(-1, 1), rng.randf_range(-0.3, 0.5), rng.randf_range(-1, 1)) * wiggle).normalized()
		# gentle droop of long horizontal limbs
		d.y -= 0.02 * t
		p += d * (length / float(segs))
	b.pts = pts
	b.radii = rad
	return b


static func _sub_branches(parent: Branch, depth: int, max_depth: int, rng: RandomNumberGenerator, p: Dictionary, out: Array[Branch], tips: Array) -> void:
	var n := parent.pts.size()
	var end := parent.pts[n - 1]
	var dir := (parent.pts[n - 1] - parent.pts[n - 2]).normalized()
	var r_end := parent.radii[n - 1]
	if depth > max_depth or r_end < 0.025:
		tips.append([end, dir, float(p.tip_size)])
		return
	var kids := rng.randi_range(2, 3)
	var plen := parent.pts[0].distance_to(end)
	for k in kids:
		var side := Vector3(rng.randf_range(-1, 1), rng.randf_range(0.0, 0.9), rng.randf_range(-1, 1)).normalized()
		var d := (dir * 0.7 + side * 0.6).normalized()
		var from_t := rng.randf_range(0.55, 1.0)
		var start := parent.pts[int(from_t * (n - 1))]
		var L := plen * rng.randf_range(0.55, 0.75)
		var b := _grow_segment(start, d, L, r_end * 0.95, r_end * 0.55, 4, rng, float(p.wiggle) * 1.3)
		b.depth = depth
		out.append(b)
		_sub_branches(b, depth + 1, max_depth, rng, p, out, tips)
	# a few tips along the parent too (fuller crown)
	if depth >= 2:
		tips.append([parent.pts[int(n * 0.6)], dir, float(p.tip_size) * 0.8])


static func _card(st: SurfaceTool, center: Vector3, basis: Basis, size: float, cell: Rect2, rnd: float) -> void:
	var hx := basis.x * size * 0.5
	var hy := basis.y * size * 0.5
	var n := basis.z
	var a := center - hx + hy
	var b := center + hx + hy
	var c := center + hx - hy
	var d := center - hx - hy
	var u0 := cell.position.x
	var u1 := cell.position.x + cell.size.x
	var v0 := cell.position.y
	var v1 := cell.position.y + cell.size.y
	var pts := [a, b, c, a, c, d]
	var uvs := [Vector2(u0, v0), Vector2(u1, v0), Vector2(u1, v1), Vector2(u0, v0), Vector2(u1, v1), Vector2(u0, v1)]
	var sw := [1.0, 1.0, 0.5, 1.0, 0.5, 0.5]
	for i in 6:
		st.set_color(Color(sw[i], rnd, 0.0))
		st.set_normal((n + (pts[i] - center).normalized() * 0.6).normalized())  # rounded crown normals
		st.set_uv(uvs[i])
		st.add_vertex(pts[i])


## Lotus field as a MultiMesh of pads (+ a few flowers). Returns a Node3D centred at origin.
static func make_lotus_patch(radius: float, count: int, seed: int) -> Node3D:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var root := Node3D.new()
	root.name = "Lotus"
	var pad := QuadMesh.new()
	pad.size = Vector2(1.0, 1.0)
	pad.orientation = PlaneMesh.FACE_Y
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/foliage.gdshader")
	m.set_shader_parameter(&"albedo_tex", load("res://assets/textures/ground/leaf_cluster_albedo.png"))
	m.set_shader_parameter(&"normal_tex", load("res://assets/textures/ground/leaf_cluster_normal.png"))
	m.set_shader_parameter(&"sway", 0.02)
	m.set_shader_parameter(&"translucency", 0.2)
	pad.material = m
	# UV to the lotus cell (bottom-right quarter): bake via a uv-transformed ArrayMesh
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var corners := [Vector3(-0.5, 0, -0.5), Vector3(0.5, 0, -0.5), Vector3(0.5, 0, 0.5), Vector3(-0.5, 0, 0.5)]
	var uvs := [Vector2(0.5, 0.5), Vector2(1.0, 0.5), Vector2(1.0, 1.0), Vector2(0.5, 1.0)]
	for i: int in [0, 1, 2, 0, 2, 3]:
		st.set_color(Color(0.2, 0.5, 0))
		st.set_normal(Vector3.UP)
		st.set_uv(uvs[i])
		st.add_vertex(corners[i])
	st.generate_tangents()
	var pad_mesh := st.commit()
	pad_mesh.surface_set_material(0, m)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = pad_mesh
	mm.instance_count = count
	for i in count:
		var a := rng.randf() * TAU
		var r := sqrt(rng.randf()) * radius
		var s := rng.randf_range(0.35, 0.75)
		var basis := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(s, 1, s))
		var raised := rng.randf() < 0.15
		var pos := Vector3(cos(a) * r, 0.01 + (rng.randf_range(0.15, 0.5) if raised else 0.0), sin(a) * r)
		if raised:
			basis = basis * Basis(Vector3.RIGHT, rng.randf_range(-0.5, 0.5))
		mm.set_instance_transform(i, Transform3D(basis, pos))
		mm.set_instance_color(i, Color(1, 1, 1))
	var mmi := MultiMeshInstance3D.new()
	mmi.name = "Pads"
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mmi)
	# flowers: pink lathe buds on stems
	var fst := MU.new_st()
	var fcount := maxi(3, count / 12)
	for i in fcount:
		var a := rng.randf() * TAU
		var r := sqrt(rng.randf()) * radius * 0.9
		var base := Vector3(cos(a) * r, 0.0, sin(a) * r)
		var h := rng.randf_range(0.35, 0.7)
		MU.tube(fst, PackedVector3Array([base, base + Vector3(0.02, h, 0.01)]), PackedFloat32Array([0.008, 0.006]), 4)
		var prof: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.05, 0.03), Vector2(0.075, 0.08), Vector2(0.06, 0.13), Vector2(0.0, 0.17)]
		MU.lathe(fst, Transform3D(Basis(), base + Vector3(0.02, h, 0.01)), prof, 8)
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.93, 0.62, 0.72)
	fm.roughness = 0.6
	fm.rim_enabled = true
	fm.rim = 0.3
	var fmesh := MU.commit(fst, fm)
	var fmi := MeshInstance3D.new()
	fmi.name = "Flowers"
	fmi.mesh = fmesh
	root.add_child(fmi)
	return root
