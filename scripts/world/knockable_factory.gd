extends RefCounted
## Builds the small knockable props used on ledges/tables (owner: world) and saves them as
## res://scenes/props/knock_<kind>.tscn — RigidBody3D roots with scripts/systems/pushable.gd,
## a lathe-turned mesh at real size and a cylinder collider. Called by build_city.gd.

const MU := preload("res://scripts/world/mesh_util.gd")

## kind -> [profile (r, y) bottom→top, material spec, mass kg, name_key, break_height]
const KINDS := {
	"cup": [[Vector2(0.0, 0.0), Vector2(0.026, 0.0), Vector2(0.028, 0.004), Vector2(0.034, 0.05), Vector2(0.036, 0.062), Vector2(0.033, 0.062), Vector2(0.031, 0.01), Vector2(0.0, 0.01)],
		["glaze", Color(0.93, 0.93, 0.9), 0.15], 0.09, "PROP_TEA_CUP", 1.2],
	"glass": [[Vector2(0.0, 0.0), Vector2(0.03, 0.0), Vector2(0.036, 0.1), Vector2(0.034, 0.1), Vector2(0.028, 0.006), Vector2(0.0, 0.006)],
		["glass", Color(0.8, 0.9, 0.88, 0.35), 0.05], 0.16, "PROP_GLASS", 0.9],
	"can": [[Vector2(0.0, 0.0), Vector2(0.027, 0.0), Vector2(0.033, 0.01), Vector2(0.033, 0.11), Vector2(0.028, 0.122), Vector2(0.0, 0.122)],
		["can", Color(0.72, 0.1, 0.08), 0.3], 0.03, "PROP_CAN", -1.0],
	"bowl": [[Vector2(0.0, 0.0), Vector2(0.035, 0.0), Vector2(0.035, 0.01), Vector2(0.07, 0.05), Vector2(0.075, 0.058), Vector2(0.068, 0.058), Vector2(0.03, 0.016), Vector2(0.0, 0.016)],
		["glaze_blue", Color(0.86, 0.9, 0.95), 0.12], 0.2, "PROP_BOWL", 1.2],
	"pot": [[Vector2(0.0, 0.0), Vector2(0.06, 0.0), Vector2(0.065, 0.01), Vector2(0.085, 0.15), Vector2(0.095, 0.155), Vector2(0.095, 0.17), Vector2(0.08, 0.17), Vector2(0.07, 0.14), Vector2(0.0, 0.14)],
		["terracotta", Color(0.66, 0.36, 0.24), 0.75], 1.1, "PROP_FLOWER_POT", 1.5],
	"bottle": [[Vector2(0.0, 0.0), Vector2(0.03, 0.0), Vector2(0.032, 0.15), Vector2(0.012, 0.21), Vector2(0.012, 0.25), Vector2(0.0, 0.25)],
		["glass_green", Color(0.18, 0.42, 0.22, 0.75), 0.05], 0.35, "PROP_BOTTLE", 1.0],
}


static func _material(spec: Array) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.resource_name = "knock_" + str(spec[0])
	var c: Color = spec[1]
	m.albedo_color = c
	m.roughness = float(spec[2])
	if c.a < 0.99:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.metallic_specular = 0.7
	if str(spec[0]) == "can":
		m.metallic = 0.6
	if str(spec[0]).begins_with("glaze"):
		m.clearcoat_enabled = true
		m.clearcoat = 0.8
	return m


static func build_all() -> PackedStringArray:
	var out := PackedStringArray()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://scenes/props"))
	for kind: String in KINDS:
		var d: Array = KINDS[kind]
		var prof: Array[Vector2] = []
		for p: Vector2 in d[0]:
			prof.append(p)
		var st := MU.new_st()
		MU.lathe(st, Transform3D(), prof, 20, 0.2)
		var mesh := MU.commit(st, _material(d[1]))
		if kind == "pot":
			# soil + a small leafy plant
			var soil := MU.new_st()
			MU.lathe(soil, Transform3D(Basis(), Vector3(0, 0.14, 0)), [Vector2(0.075, 0.0), Vector2(0.0, 0.012)] as Array[Vector2], 14)
			var sm := StandardMaterial3D.new()
			sm.albedo_color = Color(0.22, 0.16, 0.11)
			sm.roughness = 0.95
			MU.commit(soil, sm, mesh)
			var leaves := MU.new_st()
			var rng := RandomNumberGenerator.new()
			rng.seed = 99
			for i in 9:
				var a := TAU * i / 9.0
				var base := Vector3(0, 0.15, 0)
				var tip := base + Vector3(cos(a) * 0.12, rng.randf_range(0.12, 0.22), sin(a) * 0.12)
				MU.tube(leaves, PackedVector3Array([base, (base + tip) * 0.5 + Vector3(0, 0.03, 0), tip]), PackedFloat32Array([0.012, 0.022, 0.004]), 4)
			var lm := StandardMaterial3D.new()
			lm.albedo_color = Color(0.25, 0.45, 0.18)
			lm.roughness = 0.6
			MU.commit(leaves, lm, mesh)
		var body := RigidBody3D.new()
		body.name = "Knock_" + kind
		body.set_script(load("res://scripts/systems/pushable.gd"))
		body.mass = float(d[2])
		body.set_meta(&"mass", float(d[2]))
		body.set_meta(&"name_key", str(d[3]))
		body.set(&"break_height", float(d[4]))
		body.can_sleep = true
		body.sleeping = true
		var mi := MeshInstance3D.new()
		mi.name = "Mesh"
		mi.mesh = mesh
		mi.visibility_range_end = 45.0
		mi.visibility_range_end_margin = 5.0
		body.add_child(mi)
		mi.owner = body
		var cs := CollisionShape3D.new()
		cs.name = "Shape"
		var cyl := CylinderShape3D.new()
		var r := 0.0
		var h := 0.0
		for p: Vector2 in prof:
			r = maxf(r, p.x)
			h = maxf(h, p.y)
		cyl.radius = r
		cyl.height = h
		cs.shape = cyl
		cs.position = Vector3(0, h * 0.5, 0)
		body.add_child(cs)
		cs.owner = body
		var ps := PackedScene.new()
		ps.pack(body)
		var path := "res://scenes/props/knock_%s.tscn" % kind
		ResourceSaver.save(ps, path)
		body.free()
		out.append(path)
	return out
