extends RefCounted
## Procedural structures for Hàng Mây (owner: world). Each make_* returns a Node3D whose origin is
## the ground contact point, front facing +Z, with visual meshes (architecture-kit textures) and
## simple box colliders (layer 1, metadata `surface`). Landmarks are used only while the
## city-landmarks catalog has no matching model (see docs/placeholders.md); small street furniture
## (tea stall, crates, planks, lanterns, stools, carts) is final world content.

const MU := preload("res://scripts/world/mesh_util.gd")
const WM := preload("res://scripts/world/world_materials.gd")

# ------------------------------------------------------------------------------------------------
# generic helpers
# ------------------------------------------------------------------------------------------------

## Accumulates meshes per material and colliders per surface, then emits nodes.
class Kit:
	var root: Node3D
	var sts: Dictionary = {}          # Material -> SurfaceTool
	var bodies: Dictionary = {}       # surface -> StaticBody3D
	var layer_extra: Dictionary = {}  # surface -> extra layer bits

	func _init(r: Node3D) -> void:
		root = r

	func st(m: Material) -> SurfaceTool:
		if not sts.has(m):
			var s := SurfaceTool.new()
			s.begin(Mesh.PRIMITIVE_TRIANGLES)
			sts[m] = s
		return sts[m]

	func box(m: Material, xf: Transform3D, size: Vector3, tile: float = 1.0, collide: StringName = &"", skip: PackedStringArray = PackedStringArray()) -> void:
		MU.box(st(m), xf, size, tile, skip)
		if collide != &"":
			col(collide, xf, size)

	func col(surface: StringName, xf: Transform3D, size: Vector3, extra_layers: int = 0) -> CollisionShape3D:
		var key := "%s_%d" % [surface, extra_layers]
		if not bodies.has(key):
			var b := StaticBody3D.new()
			b.name = "Col_%s%s" % [surface, "" if extra_layers == 0 else "_x%d" % extra_layers]
			b.collision_layer = 1 | extra_layers
			b.collision_mask = 0
			b.set_meta(&"surface", surface)
			if extra_layers & (1 << 5):
				b.add_to_group(&"climbable")
			root.add_child(b)
			bodies[key] = b
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = size
		cs.shape = bs
		cs.transform = xf
		(bodies[key] as StaticBody3D).add_child(cs)
		return cs

	func finish(mesh_name: String = "Mesh") -> MeshInstance3D:
		var mesh := ArrayMesh.new()
		for m: Material in sts:
			var s: SurfaceTool = sts[m]
			s.generate_tangents()
			s.commit(mesh)
			mesh.surface_set_material(mesh.get_surface_count() - 1, m)
		var mi := MeshInstance3D.new()
		mi.name = mesh_name
		mi.mesh = mesh
		root.add_child(mi)
		sts.clear()
		return mi


static func _xf(pos: Vector3, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0) -> Transform3D:
	var b := Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch) * Basis(Vector3.BACK, roll)
	return Transform3D(b, pos)


## A sloped roof plane from eave line (y_eave at z = depth/2) up to the ridge (y_ridge at z = 0),
## optionally with upturned corners (temple style). Emits visual quads and a walkable box collider.
static func _roof_slope(k: Kit, mat: Material, center: Vector3, width: float, run: float, rise: float, yaw: float, upturn: float, thick: float = 0.18) -> void:
	var slope_len := sqrt(run * run + rise * rise)
	var pitch := atan2(rise, run)
	var basis := Basis(Vector3.UP, yaw)
	var segs := 10
	var st := k.st(mat)
	# grid of quads across width (x) and down the slope (s); upturn lifts the eave corners
	var rows := 4
	for i in segs:
		for j in rows:
			var corners: Array[Vector3] = []
			var uvs: Array[Vector2] = []
			for c in [[i, j], [i + 1, j], [i + 1, j + 1], [i, j + 1]]:
				var u := float(c[0]) / segs
				var v := float(c[1]) / rows      # 0 ridge → 1 eave
				var x := (u - 0.5) * width
				var y := -v * rise
				var z := v * run
				var edge := absf(u - 0.5) * 2.0
				y += upturn * pow(edge, 4.0) * (0.3 + 0.7 * v)
				corners.append(center + basis * Vector3(x, y, z))
				uvs.append(Vector2(x / 2.0, v * slope_len / 2.0))
			var n := basis * Vector3(0, cos(pitch), sin(pitch))
			MU.quad(st, corners[0], corners[1], corners[2], corners[3], n.normalized(), uvs)
	# underside (soffit) — reuse wood
	var wood := WM.arch("wood_brown")
	var sst := k.st(wood)
	var a := center + basis * Vector3(-width / 2, -thick, 0)
	var b := center + basis * Vector3(width / 2, -thick, 0)
	var c2 := center + basis * Vector3(width / 2, -rise - thick, run)
	var d := center + basis * Vector3(-width / 2, -rise - thick, run)
	var uv: Array[Vector2] = [Vector2(0, 0), Vector2(width, 0), Vector2(width, slope_len), Vector2(0, slope_len)]
	MU.quad(sst, b, a, d, c2, (basis * Vector3(0, -cos(pitch), -sin(pitch))).normalized(), uv)
	# fascia board along the eave
	k.box(wood, Transform3D(basis, center + basis * Vector3(0, -rise - thick * 0.5, run)), Vector3(width, thick * 1.5, 0.08), 1.0)
	# collider: tilted box under the surface
	var mid := center + basis * Vector3(0, -rise * 0.5 - 0.08, run * 0.5)
	k.col(&"roof_tile", Transform3D(basis * Basis(Vector3.RIGHT, pitch), mid), Vector3(width, 0.16, slope_len))


static func _column(k: Kit, mat: Material, base: Vector3, h: float, r: float, collide: bool = true) -> void:
	var prof: Array[Vector2] = [Vector2(r * 1.25, 0.0), Vector2(r * 1.25, 0.12), Vector2(r * 1.05, 0.18), Vector2(r, 0.3), Vector2(r * 0.92, h - 0.1), Vector2(r * 1.1, h)]
	MU.lathe(k.st(mat), Transform3D(Basis(), base), prof, 12, 1.0)
	if collide:
		k.col(&"wood", Transform3D(Basis(), base + Vector3(0, h * 0.5, 0)), Vector3(r * 1.8, h, r * 1.8))


# ------------------------------------------------------------------------------------------------
# Temple (Đình Hàng Mây): gate, hall with upturned hip roof, courtyard walls, bell pavilion
# ------------------------------------------------------------------------------------------------

static func make_temple_hall() -> Node3D:
	var root := Node3D.new()
	root.name = "TempleHall"
	var k := Kit.new(root)
	var granite := WM.arch("granite_red")
	var stone := WM.ground_std(&"granite")
	var plaster := WM.arch("plaster_yellow")
	var lacquer := WM.arch("wood_brown", Color(0.75, 0.32, 0.22))
	var tile := WM.arch("roof_tile_old")
	var W := 22.0
	var D := 12.0
	var plat_h := 0.75
	# stepped stone platform
	k.box(stone, _xf(Vector3(0, plat_h * 0.5, 0)), Vector3(W + 2.0, plat_h, D + 2.0), 1.0, &"tile")
	for s in 4:
		var sh := plat_h * float(4 - s) / 4.0
		k.box(stone, _xf(Vector3(0, sh * 0.5, D * 0.5 + 1.0 + 0.35 * (s + 1) - 0.175)), Vector3(8.0, sh, 0.35), 1.0, &"tile")
	# floor
	k.box(WM.arch("terrazzo", Color(0.82, 0.72, 0.62)), _xf(Vector3(0, plat_h + 0.01, 0)), Vector3(W + 1.6, 0.02, D + 1.6), 1.0)
	# back + side walls (plaster) with a dado of granite
	var wall_h := 4.2
	k.box(plaster, _xf(Vector3(0, plat_h + wall_h * 0.5, -D * 0.5 + 0.2)), Vector3(W - 0.4, wall_h, 0.35), 2.0, &"concrete")
	for sx: float in [-1, 1]:
		k.box(plaster, _xf(Vector3(sx * (W * 0.5 - 0.2), plat_h + wall_h * 0.5, -D * 0.25)), Vector3(0.35, wall_h, D * 0.5), 2.0, &"concrete")
	k.box(granite, _xf(Vector3(0, plat_h + 0.45, -D * 0.5 + 0.4)), Vector3(W - 0.5, 0.9, 0.06), 1.0)
	# carved wooden front screen (lattice doors) between the inner columns
	var lattice := WM.arch("wood_teal", Color(0.7, 0.45, 0.3))
	for i in 5:
		var x := -8.0 + i * 4.0
		k.box(lattice, _xf(Vector3(x, plat_h + 1.6, 1.2)), Vector3(3.4, 3.2, 0.1), 1.0)
		for b in 6:
			k.box(lacquer, _xf(Vector3(x - 1.45 + b * 0.58, plat_h + 1.6, 1.27)), Vector3(0.06, 3.0, 0.06), 1.0)
	# altar inside (glimpsed through the doors)
	k.box(lacquer, _xf(Vector3(0, plat_h + 0.6, -D * 0.5 + 1.4)), Vector3(4.0, 1.2, 1.2), 1.0)
	k.box(WM.emissive("altar_glow", Color(1.0, 0.55, 0.25), 1.2), _xf(Vector3(0, plat_h + 1.6, -D * 0.5 + 1.0)), Vector3(1.4, 0.6, 0.3), 1.0)
	# columns: 4 × 6 grid
	for ix in 6:
		for iz in 4:
			var x := -W * 0.5 + 1.0 + ix * (W - 2.0) / 5.0
			var z := -D * 0.5 + 1.0 + iz * (D - 2.0) / 3.0
			var h := wall_h + 0.6 if (iz == 1 or iz == 2) and (ix > 0 and ix < 5) else wall_h
			_column(k, lacquer, Vector3(x, plat_h, z), h, 0.2 if iz in [1, 2] else 0.16)
	# beams
	for iz in 4:
		var z := -D * 0.5 + 1.0 + iz * (D - 2.0) / 3.0
		k.box(lacquer, _xf(Vector3(0, plat_h + wall_h + 0.15, z)), Vector3(W - 1.6, 0.3, 0.28), 1.0)
	# hip roof: two big slopes + two hip ends, upturned corners ("đao")
	var ridge_y := plat_h + wall_h + 4.0
	var eave_y := plat_h + wall_h + 0.35
	var rise := ridge_y - eave_y
	var over := 1.6
	_roof_slope(k, tile, Vector3(0, ridge_y, 0), W - 4.0 + over * 2.0, D * 0.5 + over, rise, 0.0, 1.3)
	_roof_slope(k, tile, Vector3(0, ridge_y, 0), W - 4.0 + over * 2.0, D * 0.5 + over, rise, PI, 1.3)
	_roof_slope(k, tile, Vector3(W * 0.5 - 6.0, ridge_y, 0), D + over * 2.0, 6.0 + over, rise, PI * 0.5, 1.1)
	_roof_slope(k, tile, Vector3(-(W * 0.5 - 6.0), ridge_y, 0), D + over * 2.0, 6.0 + over, rise, -PI * 0.5, 1.1)
	# ridge with raised ends (simplified dragon-tail curls) + central pearl
	var ridge_len := W - 4.0
	k.box(tile, _xf(Vector3(0, ridge_y + 0.25, 0)), Vector3(ridge_len, 0.5, 0.55), 1.0, &"roof_tile")
	var ornament := WM.arch("stucco_detail", Color(0.8, 0.76, 0.66))
	for sx: float in [-1, 1]:
		var pts := PackedVector3Array()
		var rad := PackedFloat32Array()
		for i in 9:
			var t := float(i) / 8.0
			pts.append(Vector3(sx * (ridge_len * 0.5 - 0.2 + t * 0.9), ridge_y + 0.4 + t * t * 1.4, 0))
			rad.append(lerpf(0.26, 0.08, t))
		MU.tube(k.st(ornament), pts, rad, 8)
	var pearl_prof: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.3, 0.05), Vector2(0.38, 0.35), Vector2(0.25, 0.65), Vector2(0.0, 0.75)]
	MU.lathe(k.st(WM.flat("temple_pearl", Color(0.86, 0.72, 0.38), 0.35, 0.6)), _xf(Vector3(0, ridge_y + 0.5, 0)), pearl_prof, 12)
	# corner eave tips (curled đao)
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			var base := Vector3(sx * (W * 0.5 + over - 0.3), eave_y + 0.9, sz * (D * 0.5 + over - 0.3))
			var pts := PackedVector3Array([base, base + Vector3(sx * 0.4, 0.5, sz * 0.4), base + Vector3(sx * 0.55, 1.1, sz * 0.55)])
			MU.tube(k.st(ornament), pts, PackedFloat32Array([0.16, 0.11, 0.05]), 6)
	k.finish("Hall")
	root.set_meta(&"roof_ridge_y", ridge_y)
	root.set_meta(&"size", Vector3(W, ridge_y, D))
	return root


static func make_temple_gate() -> Node3D:
	var root := Node3D.new()
	root.name = "TempleGate"
	var k := Kit.new(root)
	var plaster := WM.arch("plaster_ochre")
	var stucco := WM.arch("stucco_detail", Color(0.9, 0.82, 0.62))
	var tile := WM.arch("roof_tile_old")
	# three openings: centre 3.2 m, sides 1.6 m; four pillars
	var xs := [-5.4, -2.0, 2.0, 5.4]
	for i in xs.size():
		var x: float = xs[i]
		var pw := 1.0 if i in [1, 2] else 0.8
		var ph := 6.2 if i in [1, 2] else 4.6
		k.box(plaster, _xf(Vector3(x, ph * 0.5, 0)), Vector3(pw, ph, 1.0), 2.0, &"concrete")
		k.box(stucco, _xf(Vector3(x, ph + 0.2, 0)), Vector3(pw + 0.2, 0.4, 1.2), 1.0, &"concrete")
		# lotus-bud finial
		var prof: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.28, 0.05), Vector2(0.32, 0.3), Vector2(0.2, 0.6), Vector2(0.0, 0.85)]
		MU.lathe(k.st(stucco), _xf(Vector3(x, ph + 0.4, 0)), prof, 10)
	# lintel over the centre with a small tiled roof
	k.box(plaster, _xf(Vector3(0, 4.9, 0)), Vector3(3.2, 1.4, 0.9), 2.0, &"concrete")
	k.box(WM.arch("wood_brown", Color(0.5, 0.2, 0.15)), _xf(Vector3(0, 4.9, 0.47)), Vector3(2.4, 0.7, 0.04), 1.0)  # name board
	_roof_slope(k, tile, Vector3(0, 6.9, 0), 4.6, 1.0, 0.8, 0.0, 0.35)
	_roof_slope(k, tile, Vector3(0, 6.9, 0), 4.6, 1.0, 0.8, PI, 0.35)
	for sx: float in [-1, 1]:
		k.box(plaster, _xf(Vector3(sx * 3.7, 3.4, 0)), Vector3(2.6, 1.0, 0.8), 2.0, &"concrete")
		_roof_slope(k, tile, Vector3(sx * 3.7, 4.6, 0), 3.4, 0.9, 0.6, 0.0, 0.2)
		_roof_slope(k, tile, Vector3(sx * 3.7, 4.6, 0), 3.4, 0.9, 0.6, PI, 0.2)
	k.finish("Gate")
	return root


## Courtyard wall segment from a to b (on the ground), height h, with tile coping (walkable top).
static func make_wall(a: Vector3, b: Vector3, h: float = 2.3) -> Node3D:
	var root := Node3D.new()
	root.name = "Wall"
	var k := Kit.new(root)
	var dir := b - a
	var L := dir.length()
	var yaw := atan2(dir.x, dir.z) - PI * 0.5
	var mid := (a + b) * 0.5
	var basis := Basis(Vector3.UP, yaw)
	k.box(WM.arch("plaster_yellow"), Transform3D(basis, mid + Vector3(0, h * 0.5, 0)), Vector3(L, h, 0.3), 2.0, &"concrete")
	k.box(WM.arch("concrete_weathered"), Transform3D(basis, mid + Vector3(0, 0.25, 0)), Vector3(L + 0.02, 0.5, 0.34), 2.0)
	k.box(WM.arch("roof_tile_old"), Transform3D(basis, mid + Vector3(0, h + 0.1, 0)), Vector3(L + 0.1, 0.2, 0.55), 1.0, &"roof_tile")
	k.finish("WallMesh")
	return root


static func make_bell_pavilion() -> Node3D:
	var root := Node3D.new()
	root.name = "BellPavilion"
	var k := Kit.new(root)
	var lacquer := WM.arch("wood_brown", Color(0.72, 0.3, 0.2))
	k.box(WM.ground_std(&"granite"), _xf(Vector3(0, 0.2, 0)), Vector3(4.0, 0.4, 4.0), 1.0, &"tile")
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			_column(k, lacquer, Vector3(sx * 1.5, 0.4, sz * 1.5), 3.0, 0.13)
	k.box(lacquer, _xf(Vector3(0, 3.45, 0)), Vector3(3.4, 0.2, 3.4), 1.0)
	var tile := WM.arch("roof_tile_old")
	for i in 4:
		_roof_slope(k, tile, Vector3(0, 5.0, 0), 3.0, 2.3, 1.45, PI * 0.5 * i, 0.5)
	var bronze := WM.flat("bronze", Color(0.45, 0.32, 0.18), 0.35, 0.9)
	var prof: Array[Vector2] = [Vector2(0.5, 0.0), Vector2(0.48, 0.1), Vector2(0.4, 0.5), Vector2(0.36, 0.9), Vector2(0.3, 1.05), Vector2(0.0, 1.1)]
	MU.lathe(k.st(bronze), _xf(Vector3(0, 1.95, 0)), prof, 16)
	k.box(bronze, _xf(Vector3(0, 3.2, 0)), Vector3(0.08, 0.3, 0.08), 1.0)
	k.finish("Pavilion")
	return root


static func make_incense_burner() -> Node3D:
	var root := Node3D.new()
	root.name = "IncenseBurner"
	var k := Kit.new(root)
	var bronze := WM.flat("bronze", Color(0.45, 0.32, 0.18), 0.35, 0.9)
	var prof: Array[Vector2] = [Vector2(0.45, 0.0), Vector2(0.5, 0.15), Vector2(0.3, 0.3), Vector2(0.55, 0.45), Vector2(0.6, 0.8), Vector2(0.5, 0.95), Vector2(0.52, 1.0), Vector2(0.0, 1.0)]
	MU.lathe(k.st(bronze), _xf(Vector3(0, 0.4, 0)), prof, 18)
	k.box(WM.ground_std(&"granite"), _xf(Vector3(0, 0.2, 0)), Vector3(1.4, 0.4, 1.4), 1.0, &"tile")
	k.col(&"metal", _xf(Vector3(0, 0.9, 0)), Vector3(1.1, 1.0, 1.1))
	k.finish("Burner")
	return root


# ------------------------------------------------------------------------------------------------
# Market hall (open steel hall, corrugated double-pitch roof with clerestory)
# ------------------------------------------------------------------------------------------------

static func make_market_hall(W: float, D: float) -> Node3D:
	var root := Node3D.new()
	root.name = "MarketHall"
	var k := Kit.new(root)
	var steel := WM.arch("metal_painted", Color(0.55, 0.62, 0.58))
	var roof := WM.arch("corrugated_rusted")
	var roof2 := WM.arch("corrugated_blue")
	var col_h := 6.0
	var nx := int(W / 6.0)
	var nz := int(D / 6.0)
	for ix in nx + 1:
		for iz in nz + 1:
			var x := -W * 0.5 + ix * W / nx
			var z := -D * 0.5 + iz * D / nz
			k.box(steel, _xf(Vector3(x, col_h * 0.5, z)), Vector3(0.3, col_h, 0.3), 1.0, &"metal")
			k.box(WM.ground_std(&"concrete"), _xf(Vector3(x, 0.2, z)), Vector3(0.6, 0.4, 0.6), 1.0)
	# trusses across x
	for iz in nz + 1:
		var z := -D * 0.5 + iz * D / nz
		k.box(steel, _xf(Vector3(0, col_h, z)), Vector3(W, 0.35, 0.2), 1.0)
		for ix in nx * 2:
			var x := -W * 0.5 + (ix + 0.5) * W / (nx * 2)
			var y := col_h + 0.2 + (1.0 - absf(x) / (W * 0.5)) * 2.6
			k.box(steel, _xf(Vector3(x, (col_h + y) * 0.5, z)), Vector3(0.08, y - col_h, 0.08), 1.0)
	for ix in nx + 1:
		var x := -W * 0.5 + ix * W / nx
		k.box(steel, _xf(Vector3(x, col_h, 0)), Vector3(0.2, 0.3, D), 1.0)
	# roof: two pitched halves leaving a clerestory gap at the ridge, raised ridge cap
	var rise := 2.6
	var half := W * 0.5 + 1.2
	for s: float in [-1, 1]:
		var pitch := atan2(rise, half)
		var center := Vector3(s * half * 0.5, col_h + 0.35 + rise * 0.5, 0)
		var basis := Basis(Vector3.BACK, -s * pitch)
		k.box(roof if s < 0 else roof2, Transform3D(basis, center), Vector3(sqrt(half * half + rise * rise), 0.06, D + 2.0), 2.0, &"metal")
	k.box(roof2, _xf(Vector3(0, col_h + rise + 1.3, 0)), Vector3(3.6, 0.06, D + 2.0), 2.0, &"metal")
	for s: float in [-1, 1]:
		k.box(steel, _xf(Vector3(s * 1.7, col_h + rise + 0.8, 0)), Vector3(0.08, 1.0, D + 2.0), 1.0)
	k.finish("Hall")
	# shelter volume (rain does not reach under the roof)
	var shelter := Area3D.new()
	shelter.name = "Shelter"
	shelter.add_to_group(&"shelter")
	shelter.collision_layer = 1 << 9
	shelter.collision_mask = 0
	shelter.monitoring = false
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(W + 2.0, col_h, D + 2.0)
	cs.shape = bs
	cs.position = Vector3(0, col_h * 0.5, 0)
	shelter.add_child(cs)
	root.add_child(shelter)
	return root


## Market stall: table + tarp on poles + goods crates. kind: "fish", "veg", "fruit", "dry", "flowers"
static func make_stall(kind: String, rng: RandomNumberGenerator, with_tarp: bool = true) -> Node3D:
	var root := Node3D.new()
	root.name = "Stall_" + kind
	var k := Kit.new(root)
	var top_mat: Material = WM.arch("stainless") if kind == "fish" else WM.arch("wood_brown")
	k.box(top_mat, _xf(Vector3(0, 0.78, 0)), Vector3(2.0, 0.05, 1.0), 1.0, &"metal" if kind == "fish" else &"wood")
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			k.box(WM.arch("metal_painted"), _xf(Vector3(sx * 0.92, 0.38, sz * 0.44)), Vector3(0.05, 0.76, 0.05), 1.0)
	k.box(WM.arch("wood_brown"), _xf(Vector3(0, 0.25, 0)), Vector3(1.9, 0.03, 0.9), 1.0)
	var cols := {
		"veg": [Color(0.32, 0.55, 0.2), Color(0.5, 0.65, 0.25), Color(0.75, 0.25, 0.15)],
		"fruit": [Color(0.95, 0.75, 0.15), Color(0.85, 0.35, 0.1), Color(0.55, 0.7, 0.2)],
		"dry": [Color(0.75, 0.6, 0.4), Color(0.55, 0.35, 0.2), Color(0.9, 0.85, 0.7)],
		"flowers": [Color(0.9, 0.3, 0.4), Color(0.95, 0.85, 0.3), Color(0.95, 0.95, 0.9)],
		"fish": [Color(0.75, 0.78, 0.8), Color(0.6, 0.62, 0.66), Color(0.85, 0.5, 0.4)],
	}
	var palette: Array = cols.get(kind, cols["veg"])
	# baskets/trays heaped with produce (lathe baskets + small sphere-ish heaps)
	var rattan := WM.arch("rattan")
	for i in 3:
		var x := -0.62 + i * 0.62
		var prof: Array[Vector2] = [Vector2(0.18, 0.0), Vector2(0.27, 0.04), Vector2(0.3, 0.1), Vector2(0.29, 0.11)]
		MU.lathe(k.st(rattan if kind != "fish" else WM.flat("styro", Color(0.92, 0.93, 0.95), 0.8)), _xf(Vector3(x, 0.805, 0)), prof, 14)
		var heap := WM.flat("produce_%s_%d" % [kind, i], palette[i % palette.size()], 0.55 if kind != "fish" else 0.25, 0.0)
		var hp: Array[Vector2] = [Vector2(0.27, 0.0), Vector2(0.24, 0.06), Vector2(0.16, 0.12), Vector2(0.0, 0.15)]
		MU.lathe(k.st(heap), _xf(Vector3(x, 0.86, 0), rng.randf() * TAU), hp, 9)
	if kind == "fish":
		# fish on the tray: flattened lathe bodies
		var fishm := WM.flat("fish_skin", Color(0.7, 0.72, 0.74), 0.22, 0.35)
		for i in 7:
			var fx := Vector3(rng.randf_range(-0.85, 0.85), 0.83, rng.randf_range(-0.35, 0.35))
			var xf := Transform3D(Basis(Vector3.UP, rng.randf() * TAU) * Basis(Vector3.BACK, PI * 0.5).scaled(Vector3(1, 1, 0.45)), fx)
			var fp: Array[Vector2] = [Vector2(0.0, -0.14), Vector2(0.03, -0.1), Vector2(0.045, 0.0), Vector2(0.035, 0.09), Vector2(0.008, 0.13), Vector2(0.03, 0.17), Vector2(0.0, 0.175)]
			MU.lathe(k.st(fishm), xf, fp, 8)
		# ice tub
		k.box(WM.flat("styro", Color(0.92, 0.93, 0.95), 0.8), _xf(Vector3(1.4, 0.25, 0.1)), Vector3(0.6, 0.5, 0.45), 1.0, &"plastic")
	if with_tarp:
		var tarp_col: Color = [Color(0.2, 0.35, 0.7), Color(0.85, 0.45, 0.15), Color(0.7, 0.15, 0.12), Color(0.3, 0.55, 0.35)][rng.randi_range(0, 3)]
		var tarp := WM.arch("fabric_canvas", tarp_col)
		for sx: float in [-1, 1]:
			k.box(WM.arch("metal_painted"), _xf(Vector3(sx * 1.1, 1.2, -0.6)), Vector3(0.04, 2.4, 0.04), 1.0)
			k.box(WM.arch("metal_painted"), _xf(Vector3(sx * 1.1, 1.0, 0.7)), Vector3(0.04, 2.0, 0.04), 1.0)
		k.box(tarp, Transform3D(Basis(Vector3.RIGHT, 0.25), Vector3(0, 2.25, 0.05)), Vector3(2.6, 0.02, 1.6), 1.0)
		var cs := k.col(&"fabric", Transform3D(Basis(Vector3.RIGHT, 0.25), Vector3(0, 2.25, 0.05)), Vector3(2.6, 0.04, 1.6))
		# tarps are camera blockers, not floors
		cs.get_parent().set(&"collision_layer", 1 << 8)
		var shelter := Area3D.new()
		shelter.name = "Shelter"
		shelter.add_to_group(&"shelter")
		shelter.collision_layer = 1 << 9
		shelter.collision_mask = 0
		shelter.monitoring = false
		var scs := CollisionShape3D.new()
		var sbs := BoxShape3D.new()
		sbs.size = Vector3(2.6, 2.2, 1.6)
		scs.shape = sbs
		scs.position = Vector3(0, 1.1, 0.05)
		shelter.add_child(scs)
		root.add_child(shelter)
	k.finish("StallMesh")
	return root


# ------------------------------------------------------------------------------------------------
# Water tower (old colonial brick tower with a round tank and catwalk)
# ------------------------------------------------------------------------------------------------

static func make_water_tower() -> Node3D:
	var root := Node3D.new()
	root.name = "WaterTower"
	var k := Kit.new(root)
	var brick := WM.arch("brick_exposed")
	var conc := WM.arch("concrete_weathered")
	var steel := WM.arch("metal_painted", Color(0.35, 0.38, 0.36))
	var H := 13.0
	var prof: Array[Vector2] = [Vector2(2.6, 0.0), Vector2(2.6, 0.6), Vector2(2.35, 0.8), Vector2(2.0, H - 0.6), Vector2(2.3, H - 0.3), Vector2(2.3, H)]
	MU.lathe(k.st(brick), Transform3D(), prof, 24, 2.0)
	# tank
	var tprof: Array[Vector2] = [Vector2(2.3, H), Vector2(3.1, H + 0.6), Vector2(3.1, H + 3.6), Vector2(3.25, H + 3.75), Vector2(0.0, H + 4.6)]
	MU.lathe(k.st(conc), Transform3D(), tprof, 24, 2.0)
	# catwalk ring at H + 0.6 (walkable) with railing posts
	var ring_y := H + 0.6
	for i in 16:
		var a := TAU * i / 16.0
		var p := Vector3(cos(a) * 3.55, ring_y, sin(a) * 3.55)
		var yaw := -a
		k.box(steel, Transform3D(Basis(Vector3.UP, yaw + PI * 0.5), p), Vector3(1.45, 0.06, 0.8), 1.0, &"metal")
		k.box(steel, _xf(Vector3(cos(a) * 3.9, ring_y + 0.5, sin(a) * 3.9)), Vector3(0.04, 1.0, 0.04), 1.0)
		k.box(steel, Transform3D(Basis(Vector3.UP, yaw + PI * 0.5), Vector3(cos(a) * 3.9, ring_y + 1.0, sin(a) * 3.9)), Vector3(1.5, 0.04, 0.04), 1.0, &"metal")
	# access ladder on the south face (climbable) + door
	k.box(steel, _xf(Vector3(0, ring_y * 0.5, 2.55)), Vector3(0.5, ring_y, 0.06), 1.0)
	for r in int(ring_y / 0.3):
		k.box(steel, _xf(Vector3(0, 0.3 + r * 0.3, 2.62)), Vector3(0.45, 0.03, 0.03), 1.0)
	var lad := k.col(&"metal", _xf(Vector3(0, ring_y * 0.5, 2.6)), Vector3(0.5, ring_y, 0.12), 1 << 5)
	lad.get_parent().set_meta(&"climb", true)
	k.box(WM.arch("wood_green"), _xf(Vector3(0, 1.1, 2.52)), Vector3(1.0, 2.1, 0.08), 1.0)
	# colliders: tower body (octagon of boxes) + tank roof
	for i in 8:
		var a := TAU * i / 8.0
		k.col(&"concrete", Transform3D(Basis(Vector3.UP, -a), Vector3(cos(a) * 1.75, H * 0.5, sin(a) * 1.75)), Vector3(0.6, H, 1.7))
	k.col(&"concrete", _xf(Vector3(0, H + 1.9, 0)), Vector3(4.4, 3.8, 4.4))
	k.col(&"concrete", _xf(Vector3(0, H + 4.0, 0)), Vector3(3.0, 0.6, 3.0))
	k.finish("Tower")
	root.set_meta(&"catwalk_y", ring_y)
	return root


# ------------------------------------------------------------------------------------------------
# Lake bridge (wooden deck on stone piers, gentle arch, lacquered railings, lantern posts)
# ------------------------------------------------------------------------------------------------

static func make_bridge(length: float, width: float, rise: float) -> Node3D:
	var root := Node3D.new()
	root.name = "Bridge"
	var k := Kit.new(root)
	var deck := WM.ground_std(&"wood", Color(0.9, 0.85, 0.8))
	var red := WM.arch("wood_brown", Color(0.85, 0.22, 0.14))
	var stone := WM.ground_std(&"embankment")
	var segs := 12
	var prev := Vector3.ZERO
	for i in segs + 1:
		var t := float(i) / segs
		var x := (t - 0.5) * length
		var y := 0.15 + rise * (1.0 - pow(2.0 * t - 1.0, 2.0))
		var p := Vector3(x, y, 0)
		if i > 0:
			var mid := (p + prev) * 0.5
			var d := p - prev
			var pitch := atan2(d.y, d.x)
			var basis := Basis(Vector3.BACK, pitch)
			k.box(deck, Transform3D(basis, mid), Vector3(d.length() + 0.02, 0.12, width), 1.0, &"wood")
			# rails (walkable thin tops → balance)
			for sz: float in [-1, 1]:
				var rp := mid + Vector3(0, 0.95, sz * (width * 0.5 - 0.05))
				k.box(red, Transform3D(basis, rp), Vector3(d.length() + 0.02, 0.08, 0.09), 1.0)
				var rc := k.col(&"wood", Transform3D(basis, rp), Vector3(d.length() + 0.02, 0.08, 0.09))
				rc.get_parent().set_meta(&"balance", true)
				k.box(red, Transform3D(basis, mid + Vector3(0, 0.45, sz * (width * 0.5 - 0.05))), Vector3(d.length(), 0.05, 0.05), 1.0)
			# under-beams
			k.box(WM.arch("wood_brown"), Transform3D(basis, mid + Vector3(0, -0.14, 0)), Vector3(d.length(), 0.18, width - 0.3), 1.0)
		# posts
		for sz: float in [-1, 1]:
			k.box(red, _xf(p + Vector3(0, 0.5, sz * (width * 0.5 - 0.05))), Vector3(0.1, 1.05, 0.1), 1.0)
		prev = p
	# stone piers
	for t: float in [0.25, 0.5, 0.75]:
		var x: float = (t - 0.5) * length
		var y := 0.15 + rise * (1.0 - pow(2.0 * t - 1.0, 2.0))
		k.box(stone, _xf(Vector3(x, (y - 2.5) * 0.5, 0)), Vector3(0.9, y + 2.5, width - 0.4), 1.0)
	# lantern posts at both ends
	var lamp_mat := WM.emissive("bridge_lantern", Color(1.0, 0.72, 0.4), 0.0)
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			var base := Vector3(sx * (length * 0.5 - 0.1), 0.2, sz * (width * 0.5 + 0.05))
			k.box(red, _xf(base + Vector3(0, 0.8, 0)), Vector3(0.16, 1.6, 0.16), 1.0)
			k.box(lamp_mat, _xf(base + Vector3(0, 1.8, 0)), Vector3(0.3, 0.38, 0.3), 1.0)
			var l := OmniLight3D.new()
			l.name = "BridgeLamp"
			l.position = base + Vector3(0, 1.85, 0)
			l.omni_range = 7.0
			l.light_energy = 1.4
			l.light_color = Color(1.0, 0.72, 0.42)
			l.shadow_enabled = false
			l.distance_fade_enabled = true
			l.distance_fade_begin = 60.0
			l.add_to_group(&"street_lamp")
			l.set_meta(&"base_energy", 1.4)
			l.set_meta(&"switch_at", 0.3)
			l.set_meta(&"lamp_material", lamp_mat)
			root.add_child(l)
	k.finish("BridgeMesh")
	return root


# ------------------------------------------------------------------------------------------------
# Islet shrine (miếu) — small roofed altar
# ------------------------------------------------------------------------------------------------

static func make_shrine() -> Node3D:
	var root := Node3D.new()
	root.name = "Shrine"
	var k := Kit.new(root)
	k.box(WM.ground_std(&"granite"), _xf(Vector3(0, 0.25, 0)), Vector3(2.6, 0.5, 2.2), 1.0, &"tile")
	k.box(WM.arch("plaster_yellow"), _xf(Vector3(0, 1.3, -0.3)), Vector3(2.0, 1.6, 1.4), 2.0, &"concrete")
	k.box(WM.arch("wood_brown", Color(0.6, 0.18, 0.12)), _xf(Vector3(0, 1.2, 0.42)), Vector3(1.0, 1.2, 0.05), 1.0)
	k.box(WM.emissive("shrine_candle", Color(1.0, 0.5, 0.2), 1.5), _xf(Vector3(0, 0.85, 0.75)), Vector3(0.5, 0.08, 0.15), 1.0)
	var tile := WM.arch("roof_tile_old")
	_roof_slope(k, tile, Vector3(0, 2.75, -0.3), 2.8, 1.2, 0.6, 0.0, 0.25)
	_roof_slope(k, tile, Vector3(0, 2.75, -0.3), 2.8, 1.2, 0.6, PI, 0.25)
	k.finish("ShrineMesh")
	return root


# ------------------------------------------------------------------------------------------------
# Street furniture: tea stall, bánh mì cart, stools, low tables, benches, crates, planks
# ------------------------------------------------------------------------------------------------

static func make_plastic_stool(color: Color) -> Node3D:
	var root := Node3D.new()
	root.name = "Stool"
	var k := Kit.new(root)
	var m := WM.flat("stool_%s" % color.to_html(), color, 0.45)
	var prof: Array[Vector2] = [Vector2(0.15, 0.0), Vector2(0.14, 0.02), Vector2(0.12, 0.24), Vector2(0.135, 0.255), Vector2(0.135, 0.27), Vector2(0.0, 0.27)]
	MU.lathe(k.st(m), Transform3D(), prof, 4)
	k.col(&"plastic", _xf(Vector3(0, 0.135, 0)), Vector3(0.24, 0.27, 0.24))
	k.finish("StoolMesh")
	return root


static func make_tea_stall() -> Node3D:
	var root := Node3D.new()
	root.name = "TeaStall"
	var k := Kit.new(root)
	var wood := WM.arch("wood_teal", Color(0.85, 0.9, 0.85))
	var wood2 := WM.arch("wood_brown")
	var glass := WM.flat("jar_glass", Color(0.85, 0.92, 0.9, 0.35), 0.05)
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	# counter cabinet (open at the back: Cam sleeps under it)
	k.box(wood, _xf(Vector3(0, 0.45, 0.22)), Vector3(1.3, 0.9, 0.04), 1.0, &"wood")       # front panel
	for sx: float in [-1, 1]:
		k.box(wood, _xf(Vector3(sx * 0.63, 0.45, 0)), Vector3(0.04, 0.9, 0.48), 1.0, &"wood")
	k.box(wood2, _xf(Vector3(0, 0.92, 0)), Vector3(1.4, 0.04, 0.56), 1.0, &"wood")       # counter top
	k.box(wood2, _xf(Vector3(0, 0.12, 0)), Vector3(1.22, 0.03, 0.44), 1.0, &"wood")      # bottom shelf
	k.box(WM.arch("fabric_canvas", Color(0.7, 0.3, 0.25)), _xf(Vector3(0, 0.16, -0.02)), Vector3(0.6, 0.05, 0.38), 1.0)  # cushion
	# glass jars with snacks on the counter
	for i in 4:
		var x := -0.5 + i * 0.25
		var prof: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.08, 0.0), Vector2(0.085, 0.2), Vector2(0.05, 0.24), Vector2(0.05, 0.27), Vector2(0.0, 0.27)]
		MU.lathe(k.st(glass), _xf(Vector3(x, 0.94, -0.1)), prof, 12)
		var fill := WM.flat("jar_fill_%d" % i, [Color(0.75, 0.55, 0.3), Color(0.9, 0.8, 0.5), Color(0.5, 0.3, 0.2), Color(0.95, 0.9, 0.85)][i], 0.7)
		var fp: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.075, 0.0), Vector2(0.075, 0.14), Vector2(0.0, 0.15)]
		MU.lathe(k.st(fill), _xf(Vector3(x, 0.945, -0.1)), fp, 10)
	# kettle + thermos
	var alu := WM.arch("stainless")
	var kp: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.11, 0.0), Vector2(0.12, 0.08), Vector2(0.1, 0.17), Vector2(0.04, 0.2), Vector2(0.0, 0.21)]
	MU.lathe(k.st(alu), _xf(Vector3(0.5, 0.94, 0.12)), kp, 14)
	var tp: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(0.07, 0.0), Vector2(0.07, 0.32), Vector2(0.05, 0.36), Vector2(0.0, 0.37)]
	MU.lathe(k.st(WM.flat("thermos_red", Color(0.7, 0.12, 0.1), 0.35)), _xf(Vector3(-0.55, 0.94, 0.15)), tp, 12)
	# low table + stools in front (customers)
	k.box(wood2, _xf(Vector3(0.0, 0.42, 0.95)), Vector3(0.9, 0.04, 0.5), 1.0, &"wood")
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			k.box(wood2, _xf(Vector3(sx * 0.4, 0.2, 0.95 + sz * 0.2)), Vector3(0.04, 0.4, 0.04), 1.0)
	# canvas umbrella on a bamboo pole (shelter for Cam)
	var bamboo := WM.flat("bamboo", Color(0.62, 0.55, 0.32), 0.6)
	k.box(bamboo, _xf(Vector3(0.75, 1.15, 0.6)), Vector3(0.05, 2.3, 0.05), 1.0)
	var canvas := WM.arch("fabric_canvas", Color(0.85, 0.75, 0.45))
	var up: Array[Vector2] = [Vector2(1.5, 0.0), Vector2(0.9, 0.25), Vector2(0.0, 0.42)]
	var umb := WM.arch("fabric_canvas", Color(0.85, 0.75, 0.45))
	umb.cull_mode = BaseMaterial3D.CULL_DISABLED
	MU.lathe(k.st(umb), _xf(Vector3(0.75, 2.2, 0.6)), up, 8)
	var uc := k.col(&"fabric", _xf(Vector3(0.75, 2.35, 0.6)), Vector3(2.2, 0.05, 2.2))
	uc.get_parent().set(&"collision_layer", 1 << 8)
	var shelter := Area3D.new()
	shelter.name = "Shelter"
	shelter.add_to_group(&"shelter")
	shelter.collision_layer = 1 << 9
	shelter.collision_mask = 0
	shelter.monitoring = false
	var scs := CollisionShape3D.new()
	var sbs := BoxShape3D.new()
	sbs.size = Vector3(2.8, 2.2, 2.8)
	scs.shape = sbs
	scs.position = Vector3(0.4, 1.1, 0.4)
	shelter.add_child(scs)
	root.add_child(shelter)
	k.finish("StallMesh")
	for i in 4:
		var s := make_plastic_stool([Color(0.15, 0.35, 0.75), Color(0.75, 0.12, 0.1), Color(0.15, 0.35, 0.75), Color(0.9, 0.7, 0.15)][i])
		s.position = Vector3(-0.7 + i * 0.5 + (0.15 if i % 2 == 0 else -0.1), 0, 1.45 + (0.12 if i % 2 == 1 else 0.0))
		s.rotation.y = i * 0.6
		root.add_child(s)
	return root


static func make_banh_mi_cart() -> Node3D:
	var root := Node3D.new()
	root.name = "BanhMiCart"
	var k := Kit.new(root)
	var steel := WM.arch("stainless")
	var glass := WM.flat("cart_glass", Color(0.8, 0.9, 0.92, 0.3), 0.05)
	glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	k.box(steel, _xf(Vector3(0, 0.85, 0)), Vector3(1.2, 0.06, 0.6), 1.0, &"metal")
	k.box(steel, _xf(Vector3(0, 0.45, 0)), Vector3(1.15, 0.8, 0.55), 1.0, &"metal")
	k.box(glass, _xf(Vector3(0, 1.15, 0)), Vector3(1.1, 0.55, 0.5), 1.0)
	k.box(WM.arch("wood_green", Color(0.9, 0.85, 0.4)), _xf(Vector3(0, 1.45, 0)), Vector3(1.2, 0.05, 0.6), 1.0)
	k.box(WM.emissive("banhmi_sign", Color(1.0, 0.85, 0.3), 0.6), _xf(Vector3(0, 1.62, 0.25)), Vector3(1.0, 0.28, 0.03), 1.0)
	var bread := WM.flat("baguette", Color(0.85, 0.6, 0.3), 0.7)
	for i in 6:
		var bp: Array[Vector2] = [Vector2(0.0, -0.12), Vector2(0.035, -0.08), Vector2(0.04, 0.08), Vector2(0.0, 0.12)]
		MU.lathe(k.st(bread), Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(-0.4 + i * 0.16, 0.93, -0.05)), bp, 8)
	var tyre := WM.flat("tyre", Color(0.06, 0.06, 0.06), 0.85)
	for sx: float in [-1, 1]:
		var wp: Array[Vector2] = [Vector2(0.0, -0.03), Vector2(0.18, -0.03), Vector2(0.2, 0.0), Vector2(0.18, 0.03), Vector2(0.0, 0.03)]
		MU.lathe(k.st(tyre), Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(sx * 0.45, 0.2, 0.32)), wp, 12)
	k.finish("CartMesh")
	return root


static func make_bench(length: float = 1.8) -> Node3D:
	var root := Node3D.new()
	root.name = "Bench"
	var k := Kit.new(root)
	var stone := WM.ground_std(&"granite")
	k.box(stone, _xf(Vector3(0, 0.42, 0)), Vector3(length, 0.08, 0.42), 1.0, &"tile")
	for sx: float in [-1, 1]:
		k.box(stone, _xf(Vector3(sx * (length * 0.5 - 0.2), 0.2, 0)), Vector3(0.14, 0.4, 0.38), 1.0, &"tile")
	k.finish("BenchMesh")
	return root


## Stacked wooden / plastic crates forming a stair up to `height` (cat-sized steps ≤ 0.45 m).
static func make_crate_stair(height: float, rng: RandomNumberGenerator) -> Node3D:
	var root := Node3D.new()
	root.name = "CrateStair"
	var k := Kit.new(root)
	var wood := WM.ground_std(&"wood", Color(0.85, 0.78, 0.7))
	var blue := WM.flat("crate_blue", Color(0.12, 0.3, 0.62), 0.55)
	var red := WM.flat("crate_red", Color(0.62, 0.12, 0.1), 0.55)
	var step := 0.42
	var n := int(ceil(height / step))
	for i in n:
		# column i has i+1 crates; stair rises along +Z toward the wall
		for j in i + 1:
			var m: Material = wood if (i + j) % 3 == 0 else (blue if (i + j) % 3 == 1 else red)
			var y := step * (j + 0.5)
			if y > height + 0.01:
				break
			var pos := Vector3(rng.randf_range(-0.03, 0.03), y, -float(n - 1 - i) * 0.5)
			k.box(m, Transform3D(Basis(Vector3.UP, rng.randf_range(-0.05, 0.05)), pos), Vector3(0.55, step - 0.01, 0.48), 1.0, &"wood" if m == wood else &"plastic")
	k.finish("Crates")
	return root


## Wooden plank bridge between two points (top surface passes through a and b).
static func make_plank(a: Vector3, b: Vector3, width: float = 0.3) -> Node3D:
	var root := Node3D.new()
	root.name = "Plank"
	var k := Kit.new(root)
	var d := b - a
	var L := d.length() + 0.5
	var basis := Basis.looking_at(d.normalized(), Vector3.UP)
	var mid := (a + b) * 0.5 - Vector3(0, 0.03, 0)
	k.box(WM.ground_std(&"wood", Color(0.8, 0.72, 0.62)), Transform3D(basis, mid), Vector3(width, 0.05, L), 1.0, &"wood")
	k.box(WM.ground_std(&"wood", Color(0.7, 0.6, 0.52)), Transform3D(basis, mid + basis * Vector3(width * 0.5 + 0.12, 0.0, 0)), Vector3(0.18, 0.04, L * 0.96), 1.0, &"wood")
	k.finish("PlankMesh")
	root.set_meta(&"plank", true)
	return root


## Festival string of star lanterns (đèn ông sao) between a and b with sag.
static func make_lantern_string(a: Vector3, b: Vector3, count: int, rng: RandomNumberGenerator) -> Node3D:
	var root := Node3D.new()
	root.name = "LanternString"
	var k := Kit.new(root)
	var cable := WM.flat("lantern_cable", Color(0.05, 0.05, 0.05), 0.7)
	var pts := MU.catenary(a, b, 0.6, 20)
	MU.tube(k.st(cable), pts, _const_radii(pts.size(), 0.006), 4)
	var cols := [Color(0.95, 0.15, 0.1), Color(1.0, 0.75, 0.1), Color(0.95, 0.35, 0.55), Color(0.2, 0.6, 0.9)]
	for i in count:
		var t := (float(i) + 0.5) / float(count)
		var p := pts[int(t * (pts.size() - 1))] + Vector3(0, -0.18, 0)
		var c: Color = cols[rng.randi_range(0, cols.size() - 1)]
		var m := WM.emissive("star_%s" % c.to_html(), c, 2.2, false)
		_star(k.st(m), p, 0.22, rng.randf() * TAU)
		# tassel
		k.box(m, _xf(p + Vector3(0, -0.3, 0)), Vector3(0.015, 0.15, 0.015), 1.0)
	k.finish("Lanterns")
	return root


static func _const_radii(n: int, r: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(n)
	out.fill(r)
	return out


static func _star(st: SurfaceTool, c: Vector3, R: float, yaw: float) -> void:
	var basis := Basis(Vector3.UP, yaw)
	var r := R * 0.45
	var depth := R * 0.25
	var outline: Array[Vector3] = []
	for i in 10:
		var a := PI * 0.5 + TAU * i / 10.0
		var rr := R if i % 2 == 0 else r
		outline.append(Vector3(cos(a) * rr, sin(a) * rr, 0))
	for side: float in [-1, 1]:
		var apex := c + basis * Vector3(0, 0, side * depth)
		for i in 10:
			var p0 := c + basis * outline[i]
			var p1 := c + basis * outline[(i + 1) % 10]
			var n := ((p1 - p0).cross(apex - p0)).normalized() * -side
			for v in ([apex, p0, p1] if side > 0 else [apex, p1, p0]):
				st.set_normal(n)
				st.set_uv(Vector2(0.5, 0.5))
				st.add_vertex(v)


## Cable bundle mesh (several sagging wires + a few coils) from a to b; returns Node3D.
static func make_cable_bundle(a: Vector3, b: Vector3, wires: int, rng: RandomNumberGenerator, walkable: bool) -> Node3D:
	var root := Node3D.new()
	root.name = "Cables"
	var k := Kit.new(root)
	var black := WM.flat("cable_black", Color(0.035, 0.035, 0.035), 0.55)
	var grey := WM.flat("cable_grey", Color(0.2, 0.2, 0.2), 0.6)
	var L := a.distance_to(b)
	var base_sag := clampf(L * 0.035, 0.15, 1.2)
	var side := (b - a).cross(Vector3.UP).normalized()
	for w in wires:
		var off := side * rng.randf_range(-0.12, 0.12) + Vector3(0, rng.randf_range(-0.1, 0.1), 0)
		var sag := base_sag * rng.randf_range(0.85, 1.35)
		var pts := MU.catenary(a + off * 0.4, b + off * 0.4, sag, maxi(8, int(L / 1.0)))
		# twist the bundle around its centre
		for i in pts.size():
			var t := float(i) / float(pts.size() - 1)
			var ang := t * 6.0 + w
			pts[i] += off * (0.4 + 0.6 * sin(t * PI)) + side * cos(ang) * 0.02
		var r := rng.randf_range(0.006, 0.014)
		MU.tube(k.st(black if w % 4 != 3 else grey), pts, _const_radii(pts.size(), r), 4)
	k.finish("CableMesh")
	if walkable:
		# thin box chain following the bundle's core (balance-walk, layer 1, meta balance)
		var body := StaticBody3D.new()
		body.name = "BalanceCable"
		body.collision_layer = 1
		body.collision_mask = 0
		body.set_meta(&"surface", &"metal")
		body.set_meta(&"balance", true)
		body.add_to_group(&"balance_cable")
		root.add_child(body)
		var core := MU.catenary(a, b, base_sag, maxi(6, int(L / 1.5)))
		for i in core.size() - 1:
			var p0 := core[i]
			var p1 := core[i + 1]
			var cs := CollisionShape3D.new()
			var bs := BoxShape3D.new()
			bs.size = Vector3(0.05, 0.04, p0.distance_to(p1) + 0.03)
			cs.shape = bs
			cs.transform = Transform3D(Basis.looking_at((p1 - p0).normalized(), Vector3.UP), (p0 + p1) * 0.5)
			body.add_child(cs)
		root.set_meta(&"sag", base_sag)
	return root


## Low rattan café chair (scratchable).
static func make_rattan_chair() -> Node3D:
	var root := Node3D.new()
	root.name = "RattanChair"
	var k := Kit.new(root)
	var rattan := WM.arch("rattan")
	k.box(rattan, _xf(Vector3(0, 0.3, 0)), Vector3(0.45, 0.06, 0.45), 0.5, &"fabric")
	k.box(rattan, _xf(Vector3(0, 0.55, -0.21), 0, -0.15), Vector3(0.45, 0.5, 0.05), 0.5)
	for sx: float in [-1, 1]:
		for sz: float in [-1, 1]:
			k.box(rattan, _xf(Vector3(sx * 0.19, 0.14, sz * 0.19)), Vector3(0.04, 0.28, 0.04), 0.5)
	k.finish("ChairMesh")
	return root


## Cast-iron / PVC drainpipe with wall brackets (climbable, layers 1 + 6). Origin at the bottom,
## the pipe runs up +Y; its back (-Z) touches the wall.
static func make_drainpipe(height: float) -> Node3D:
	var root := Node3D.new()
	root.name = "Drainpipe"
	var k := Kit.new(root)
	var pipe := WM.flat("drainpipe", Color(0.28, 0.3, 0.29), 0.55, 0.3)
	MU.tube(k.st(pipe), PackedVector3Array([Vector3(0, 0.05, 0.0), Vector3(0, height, 0.0)]), PackedFloat32Array([0.055, 0.055]), 10, 1.0)
	MU.tube(k.st(pipe), PackedVector3Array([Vector3(0, 0.05, 0.0), Vector3(0, 0.05, 0.18)]), PackedFloat32Array([0.06, 0.06]), 10, 1.0)
	var bracket := WM.flat("bracket", Color(0.16, 0.16, 0.16), 0.5, 0.7)
	var y := 0.6
	while y < height - 0.2:
		k.box(bracket, _xf(Vector3(0, y, -0.06)), Vector3(0.16, 0.04, 0.1), 1.0)
		y += 1.4
	# hopper head at the top
	k.box(pipe, _xf(Vector3(0, height - 0.12, 0.0)), Vector3(0.2, 0.24, 0.16), 1.0)
	var cs := k.col(&"metal", _xf(Vector3(0, height * 0.5, -0.02)), Vector3(0.16, height, 0.16), 1 << 5)
	cs.get_parent().set_meta(&"climb", true)
	k.finish("PipeMesh")
	return root
