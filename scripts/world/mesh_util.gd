extends RefCounted
## Static procedural-mesh helpers for the world builder (owner: world).
## All functions append triangles to a SurfaceTool already begun with PRIMITIVE_TRIANGLES.
## UVs are in metres / tile so textures keep a constant texel density.


## Axis-aligned (in xf space) box. `tile` metres per UV unit. `skip` = faces to omit
## ("top","bottom","px","nx","pz","nz").
static func box(st: SurfaceTool, xf: Transform3D, size: Vector3, tile: float = 1.0, skip: PackedStringArray = PackedStringArray(), uv_offset: Vector2 = Vector2.ZERO) -> void:
	var h := size * 0.5
	var faces := {
		"top": [Vector3.UP, Vector3(-h.x, h.y, -h.z), Vector3(h.x, h.y, -h.z), Vector3(h.x, h.y, h.z), Vector3(-h.x, h.y, h.z)],
		"bottom": [Vector3.DOWN, Vector3(-h.x, -h.y, h.z), Vector3(h.x, -h.y, h.z), Vector3(h.x, -h.y, -h.z), Vector3(-h.x, -h.y, -h.z)],
		"pz": [Vector3.BACK, Vector3(-h.x, h.y, h.z), Vector3(h.x, h.y, h.z), Vector3(h.x, -h.y, h.z), Vector3(-h.x, -h.y, h.z)],
		"nz": [Vector3.FORWARD, Vector3(h.x, h.y, -h.z), Vector3(-h.x, h.y, -h.z), Vector3(-h.x, -h.y, -h.z), Vector3(h.x, -h.y, -h.z)],
		"px": [Vector3.RIGHT, Vector3(h.x, h.y, h.z), Vector3(h.x, h.y, -h.z), Vector3(h.x, -h.y, -h.z), Vector3(h.x, -h.y, h.z)],
		"nx": [Vector3.LEFT, Vector3(-h.x, h.y, -h.z), Vector3(-h.x, h.y, h.z), Vector3(-h.x, -h.y, h.z), Vector3(-h.x, -h.y, -h.z)],
	}
	for key: String in faces:
		if key in skip:
			continue
		var f: Array = faces[key]
		var n: Vector3 = f[0]
		var c: Array[Vector3] = [f[1], f[2], f[3], f[4]]
		var uvs: Array[Vector2] = []
		for p in c:
			var uv: Vector2
			if absf(n.y) > 0.5:
				uv = Vector2(p.x, p.z)
			elif absf(n.z) > 0.5:
				uv = Vector2(p.x * signf(n.z), -p.y)
			else:
				uv = Vector2(-p.z * signf(n.x), -p.y)
			uvs.append(uv / tile + uv_offset)
		quad(st, xf * c[0], xf * c[1], xf * c[2], xf * c[3], (xf.basis * n).normalized(), uvs)


## Quad from 4 corners (counter-clockwise seen from the normal side... Godot front faces are CW
## in screen space, so corners are given in the order a,b,c,d going clockwise seen from outside).
static func quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3, uvs: Array[Vector2]) -> void:
	var idx := [0, 1, 2, 0, 2, 3]
	var pts := [a, b, c, d]
	for i: int in idx:
		st.set_normal(n)
		st.set_uv(uvs[i])
		st.add_vertex(pts[i])


## Horizontal rectangle (world UV = xz / tile), facing up.
static func rect_xz(st: SurfaceTool, x0: float, z0: float, x1: float, z1: float, y: float, tile: float = 1.0, uv_offset: Vector2 = Vector2.ZERO) -> void:
	var a := Vector3(x0, y, z0)
	var b := Vector3(x1, y, z0)
	var c := Vector3(x1, y, z1)
	var d := Vector3(x0, y, z1)
	var uv: Array[Vector2] = []
	for p in [a, b, c, d]:
		uv.append(Vector2(p.x, p.z) / tile + uv_offset)
	quad(st, a, b, c, d, Vector3.UP, uv)


## Tube along a polyline with per-point radius (parallel-transport frames). V along the length.
static func tube(st: SurfaceTool, pts: PackedVector3Array, radii: PackedFloat32Array, sides: int = 6, v_tile: float = 1.0, u_tile: float = 1.0, cap_end: bool = false) -> void:
	var n := pts.size()
	if n < 2:
		return
	var rings: Array[PackedVector3Array] = []
	var norms: Array[PackedVector3Array] = []
	var t0 := (pts[1] - pts[0]).normalized()
	var ref := Vector3.UP if absf(t0.y) < 0.9 else Vector3.RIGHT
	var nrm := t0.cross(ref).normalized()
	var vacc := PackedFloat32Array()
	var acc := 0.0
	for i in n:
		var t: Vector3
		if i == 0:
			t = (pts[1] - pts[0]).normalized()
		elif i == n - 1:
			t = (pts[i] - pts[i - 1]).normalized()
		else:
			t = (pts[i + 1] - pts[i - 1]).normalized()
		# transport the normal
		nrm = (nrm - t * nrm.dot(t)).normalized()
		if nrm.length() < 0.5:
			nrm = t.cross(ref).normalized()
		var bi := t.cross(nrm).normalized()
		var ring := PackedVector3Array()
		var rn := PackedVector3Array()
		for s in sides + 1:
			var a := TAU * float(s) / float(sides)
			var dir := nrm * cos(a) + bi * sin(a)
			ring.append(pts[i] + dir * radii[i])
			rn.append(dir)
		rings.append(ring)
		norms.append(rn)
		if i > 0:
			acc += pts[i].distance_to(pts[i - 1])
		vacc.append(acc)
	for i in n - 1:
		for s in sides:
			var u0 := float(s) / float(sides) * u_tile
			var u1 := float(s + 1) / float(sides) * u_tile
			var v0 := vacc[i] / v_tile
			var v1 := vacc[i + 1] / v_tile
			var a := rings[i][s]
			var b := rings[i][s + 1]
			var c := rings[i + 1][s + 1]
			var d := rings[i + 1][s]
			_v(st, a, norms[i][s], Vector2(u0, v0))
			_v(st, c, norms[i + 1][s + 1], Vector2(u1, v1))
			_v(st, b, norms[i][s + 1], Vector2(u1, v0))
			_v(st, a, norms[i][s], Vector2(u0, v0))
			_v(st, d, norms[i + 1][s], Vector2(u0, v1))
			_v(st, c, norms[i + 1][s + 1], Vector2(u1, v1))
	if cap_end:
		var last := rings[n - 1]
		var tc := (pts[n - 1] - pts[n - 2]).normalized()
		for s in sides:
			_v(st, pts[n - 1], tc, Vector2(0.5, 0.5))
			_v(st, last[s], tc, Vector2(0.5 + cos(TAU * s / sides) * 0.5, 0.5))
			_v(st, last[s + 1], tc, Vector2(0.5, 0.5 + sin(TAU * s / sides) * 0.5))


static func _v(st: SurfaceTool, p: Vector3, n: Vector3, uv: Vector2) -> void:
	st.set_normal(n)
	st.set_uv(uv)
	st.add_vertex(p)


## Sagging cable between a and b (parabolic approximation of a catenary; sag in metres).
static func catenary(a: Vector3, b: Vector3, sag: float, segments: int = 16) -> PackedVector3Array:
	var out := PackedVector3Array()
	for i in segments + 1:
		var t := float(i) / float(segments)
		out.append(a.lerp(b, t) + Vector3.DOWN * sag * 4.0 * t * (1.0 - t))
	return out


## Surface of revolution around local Y. profile: Array of Vector2(radius, y) bottom→top.
static func lathe(st: SurfaceTool, xf: Transform3D, profile: Array[Vector2], sides: int = 16, v_tile: float = 1.0) -> void:
	var n := profile.size()
	var vacc := 0.0
	var vs := PackedFloat32Array([0.0])
	for i in range(1, n):
		vacc += profile[i].distance_to(profile[i - 1])
		vs.append(vacc)
	for i in n - 1:
		var p0 := profile[i]
		var p1 := profile[i + 1]
		var slope := Vector2(p1.y - p0.y, -(p1.x - p0.x)).normalized()   # outward normal in (r, y)
		for s in sides:
			var a0 := TAU * float(s) / float(sides)
			var a1 := TAU * float(s + 1) / float(sides)
			var d0 := Vector3(cos(a0), 0, sin(a0))
			var d1 := Vector3(cos(a1), 0, sin(a1))
			var n0 := (d0 * slope.x + Vector3.UP * slope.y).normalized()
			var n1 := (d1 * slope.x + Vector3.UP * slope.y).normalized()
			var A := xf * (d0 * p0.x + Vector3.UP * p0.y)
			var B := xf * (d1 * p0.x + Vector3.UP * p0.y)
			var C := xf * (d1 * p1.x + Vector3.UP * p1.y)
			var D := xf * (d0 * p1.x + Vector3.UP * p1.y)
			var u0 := float(s) / float(sides)
			var u1 := float(s + 1) / float(sides)
			var bn0 := (xf.basis * n0).normalized()
			var bn1 := (xf.basis * n1).normalized()
			_v(st, A, bn0, Vector2(u0, vs[i] / v_tile))
			_v(st, B, bn1, Vector2(u1, vs[i] / v_tile))
			_v(st, C, bn1, Vector2(u1, vs[i + 1] / v_tile))
			_v(st, A, bn0, Vector2(u0, vs[i] / v_tile))
			_v(st, C, bn1, Vector2(u1, vs[i + 1] / v_tile))
			_v(st, D, bn0, Vector2(u0, vs[i + 1] / v_tile))


## Commit a SurfaceTool into a new ArrayMesh surface (tangents generated).
static func commit(st: SurfaceTool, mat: Material, mesh: ArrayMesh = null) -> ArrayMesh:
	st.generate_tangents()
	var m := st.commit(mesh)
	m.surface_set_material(m.get_surface_count() - 1, mat)
	return m


static func new_st() -> SurfaceTool:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	return st
