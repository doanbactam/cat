extends RefCounted
## Procedural articulated stand-in models for NPCs/animals/vehicles (owner: world-life).
##
## Used ONLY when the real GLB (assets/models/npc|vehicles/…) does not exist yet — logged in
## docs/placeholders.md. Every builder returns a Node3D whose front faces +Z (MODEL_FRONT), origin
## at the ground contact point, real-world proportions, and a `rig` meta Dictionary of named pivot
## Node3Ds that scripts/npc/proc_animator.gd poses (walk/run/sit/peck/fly/pet/shoo …).

static var _mat_cache: Dictionary = {}
static var _noise_cache: Dictionary = {}


# -------------------------------------------------------------------------------------------
# Materials
# -------------------------------------------------------------------------------------------

static func mat(color: Color, rough := 0.8, metal := 0.0, key := "") -> StandardMaterial3D:
	var k := key if key != "" else "%s|%.2f|%.2f" % [color.to_html(), rough, metal]
	if _mat_cache.has(k):
		return _mat_cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	if metal > 0.3:
		m.metallic_specular = 0.6
	_mat_cache[k] = m
	return m


static func cloth(color: Color, rough := 0.88) -> StandardMaterial3D:
	var k := "cloth|" + color.to_html() + "|%.2f" % rough
	if _mat_cache.has(k):
		return _mat_cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.albedo_texture = _noise_tex("weave", 0.9)
	m.uv1_triplanar = true
	m.uv1_scale = Vector3(6, 6, 6)
	# sheen-ish soft rim for fabric
	m.rim_enabled = true
	m.rim = 0.25
	m.rim_tint = 0.6
	_mat_cache[k] = m
	return m


static func skin(color: Color) -> StandardMaterial3D:
	var k := "skin|" + color.to_html()
	if _mat_cache.has(k):
		return _mat_cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.62
	m.subsurf_scatter_enabled = true
	m.subsurf_scatter_strength = 0.35
	m.subsurf_scatter_skin_mode = true
	m.rim_enabled = true
	m.rim = 0.15
	_mat_cache[k] = m
	return m


static func paint(color: Color) -> StandardMaterial3D:
	var k := "paint|" + color.to_html()
	if _mat_cache.has(k):
		return _mat_cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.32
	m.metallic = 0.35
	m.clearcoat_enabled = true
	m.clearcoat = 0.8
	m.clearcoat_roughness = 0.15
	_mat_cache[k] = m
	return m


## Brindle / tabby / feather patterns: triplanar noise multiplied over a base colour.
static func patterned(base: Color, dark: Color, pattern: String, rough := 0.85, scale := 4.0) -> StandardMaterial3D:
	var k := "pat|%s|%s|%s|%.1f" % [base.to_html(), dark.to_html(), pattern, scale]
	if _mat_cache.has(k):
		return _mat_cache[k]
	var m := StandardMaterial3D.new()
	var tex := NoiseTexture2D.new()
	tex.width = 256
	tex.height = 256
	tex.seamless = true
	var n := FastNoiseLite.new()
	match pattern:
		"brindle":
			n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
			n.frequency = 0.03
			n.fractal_type = FastNoiseLite.FRACTAL_RIDGED
			n.fractal_octaves = 3
		"feather":
			n.noise_type = FastNoiseLite.TYPE_CELLULAR
			n.frequency = 0.06
		_:
			n.noise_type = FastNoiseLite.TYPE_SIMPLEX
			n.frequency = 0.05
	tex.noise = n
	var g := Gradient.new()
	g.set_color(0, dark)
	g.set_color(1, base)
	g.add_point(0.45, dark.lerp(base, 0.35))
	tex.color_ramp = g
	m.albedo_texture = tex
	m.uv1_triplanar = true
	m.uv1_scale = Vector3(scale, scale * (3.0 if pattern == "brindle" else 1.0), scale)
	m.roughness = rough
	_mat_cache[k] = m
	return m


static func _noise_tex(kind: String, contrast: float) -> NoiseTexture2D:
	if _noise_cache.has(kind):
		return _noise_cache[kind]
	var tex := NoiseTexture2D.new()
	tex.width = 128
	tex.height = 128
	tex.seamless = true
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_VALUE
	n.frequency = 0.35
	tex.noise = n
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1).darkened(0.18 * contrast))
	g.set_color(1, Color(1, 1, 1))
	tex.color_ramp = g
	_noise_cache[kind] = tex
	return tex


# -------------------------------------------------------------------------------------------
# Mesh helpers
# -------------------------------------------------------------------------------------------

static func piv(parent: Node3D, n: String, pos: Vector3, rig: Dictionary) -> Node3D:
	var p := Node3D.new()
	p.name = n
	p.position = pos
	parent.add_child(p)
	rig[n] = p
	return p


static func part(parent: Node3D, mesh: Mesh, m: Material, pos := Vector3.ZERO, rot_deg := Vector3.ZERO,
		scl := Vector3.ONE, shadows := true) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = m
	mi.position = pos
	mi.rotation_degrees = rot_deg
	mi.scale = scl
	if not shadows:
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	return mi


static func capsule(r: float, h: float, segs := 12) -> CapsuleMesh:
	var c := CapsuleMesh.new()
	c.radius = r
	c.height = maxf(h, r * 2.0)
	c.radial_segments = segs
	c.rings = 4
	return c


static func cyl(r_top: float, r_bot: float, h: float, segs := 12) -> CylinderMesh:
	var c := CylinderMesh.new()
	c.top_radius = r_top
	c.bottom_radius = r_bot
	c.height = h
	c.radial_segments = segs
	c.rings = 1
	return c


static func sphere(r: float, segs := 14) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r
	s.height = r * 2.0
	s.radial_segments = segs
	s.rings = maxi(segs / 2, 4)
	return s


static func box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


static func prism(size: Vector3) -> PrismMesh:
	var p := PrismMesh.new()
	p.size = size
	return p


static func torus(inner: float, outer: float, segs := 20) -> TorusMesh:
	var t := TorusMesh.new()
	t.inner_radius = inner
	t.outer_radius = outer
	t.rings = segs
	t.ring_segments = 8
	return t


static func _root(kind: String) -> Node3D:
	var r := Node3D.new()
	r.name = "StandIn"
	r.set_meta(&"rig_kind", kind)
	return r


# -------------------------------------------------------------------------------------------
# Humans
# -------------------------------------------------------------------------------------------

const SKIN_TONES: Array[Color] = [Color(0.80, 0.62, 0.48), Color(0.72, 0.53, 0.40), Color(0.86, 0.70, 0.56),
	Color(0.64, 0.46, 0.34), Color(0.78, 0.60, 0.47)]
const SHIRTS: Array[Color] = [Color(0.86, 0.84, 0.78), Color(0.33, 0.45, 0.62), Color(0.70, 0.30, 0.28),
	Color(0.92, 0.88, 0.70), Color(0.38, 0.52, 0.42), Color(0.20, 0.22, 0.26), Color(0.85, 0.62, 0.70),
	Color(0.55, 0.72, 0.80), Color(0.95, 0.95, 0.94), Color(0.62, 0.48, 0.66)]
const PANTS: Array[Color] = [Color(0.18, 0.20, 0.26), Color(0.28, 0.32, 0.45), Color(0.45, 0.40, 0.32),
	Color(0.12, 0.12, 0.13), Color(0.55, 0.52, 0.47), Color(0.32, 0.26, 0.22)]
const HAIR: Array[Color] = [Color(0.04, 0.035, 0.03), Color(0.09, 0.07, 0.05), Color(0.55, 0.55, 0.55),
	Color(0.85, 0.85, 0.84)]


## opts: height (m), skin, shirt, pants, hair, hat ("" | "non_la" | "cap" | "helmet"), female (bool),
## long_sleeves, apron (Color or null), elder (bool), seed.
static func human(opts: Dictionary = {}) -> Node3D:
	var rng := RandomNumberGenerator.new()
	rng.seed = int(opts.get("seed", randi()))
	var h: float = float(opts.get("height", rng.randf_range(1.55, 1.74)))
	var female: bool = bool(opts.get("female", rng.randf() < 0.5))
	var elder: bool = bool(opts.get("elder", false))
	var skin_c: Color = opts.get("skin", SKIN_TONES[rng.randi() % SKIN_TONES.size()])
	var shirt_c: Color = opts.get("shirt", SHIRTS[rng.randi() % SHIRTS.size()])
	var pants_c: Color = opts.get("pants", PANTS[rng.randi() % PANTS.size()])
	var hair_c: Color = opts.get("hair", HAIR[3 if elder else rng.randi() % 2])
	var hat: String = str(opts.get("hat", ""))
	var s := h / 1.65
	var w := s * (0.92 if female else 1.0) * float(opts.get("girth", 1.0))
	var rig := {}
	var root := _root("human")
	var skin_m := skin(skin_c)
	var shirt_m := cloth(shirt_c)
	var pants_m := cloth(pants_c, 0.92)
	var hair_m := mat(hair_c, 0.55, 0.0)
	var sandal_m := mat(Color(0.16, 0.12, 0.10) if rng.randf() < 0.6 else Color(0.25, 0.32, 0.55), 0.7)
	var leg_len := 0.47 * h
	var hips := piv(root, "Hips", Vector3(0, leg_len + 0.04 * s, 0), rig)
	part(hips, capsule(0.15 * w, 0.32 * w), pants_m, Vector3(0, 0.0, 0), Vector3(0, 0, 90), Vector3(1, 1, 0.75))
	var spine := piv(hips, "Spine", Vector3(0, 0.04 * s, 0), rig)
	var torso_h := 0.30 * h
	# torso: tapered (waist → chest), slightly flattened front-back
	var chest_r := (0.165 if female else 0.18) * w
	part(spine, cyl(chest_r, 0.145 * w, torso_h, 16), shirt_m, Vector3(0, torso_h * 0.5, 0), Vector3.ZERO, Vector3(1, 1, 0.68))
	part(spine, sphere(chest_r * 1.0, 16), shirt_m, Vector3(0, torso_h * 0.92, 0), Vector3.ZERO, Vector3(1.0, 0.45, 0.68))
	if opts.get("apron") is Color:
		part(spine, box(Vector3(0.30 * w, torso_h * 1.2, 0.01)), cloth(opts["apron"]), Vector3(0, torso_h * 0.35, chest_r * 0.70))
	var neck := piv(spine, "Neck", Vector3(0, torso_h * 1.02, 0.01), rig)
	part(neck, cyl(0.048 * s, 0.055 * s, 0.10 * s), skin_m, Vector3(0, 0.04 * s, 0))
	var head := piv(neck, "Head", Vector3(0, 0.09 * s, 0.0), rig)
	var hr := 0.098 * s
	part(head, sphere(hr, 18), skin_m, Vector3(0, hr * 1.05, 0.005), Vector3.ZERO, Vector3(0.92, 1.12, 1.0))
	# jaw / chin and nose for a readable face silhouette
	part(head, sphere(hr * 0.62, 12), skin_m, Vector3(0, hr * 0.55, hr * 0.32), Vector3.ZERO, Vector3(1.05, 0.9, 0.9))
	part(head, prism(Vector3(hr * 0.28, hr * 0.38, hr * 0.22)), skin_m, Vector3(0, hr * 1.0, hr * 0.95), Vector3(-90, 0, 0))
	var eye_m := mat(Color(0.05, 0.04, 0.035), 0.2)
	for sx: float in [-1.0, 1.0]:
		part(head, sphere(hr * 0.09, 8), eye_m, Vector3(sx * hr * 0.36, hr * 1.18, hr * 0.84), Vector3.ZERO, Vector3.ONE, false)
		part(head, sphere(hr * 0.2, 8), skin_m, Vector3(sx * hr * 0.92, hr * 1.05, 0), Vector3.ZERO, Vector3(0.4, 1, 0.7), false)
	# hair
	if elder and female:
		part(head, sphere(hr * 1.06, 16), hair_m, Vector3(0, hr * 1.22, -hr * 0.08), Vector3.ZERO, Vector3(0.95, 0.8, 1.0))
		part(head, sphere(hr * 0.42, 10), hair_m, Vector3(0, hr * 1.25, -hr * 1.0))   # bun
	elif female:
		part(head, sphere(hr * 1.07, 16), hair_m, Vector3(0, hr * 1.2, -hr * 0.1), Vector3.ZERO, Vector3(0.96, 0.85, 1.0))
		part(head, capsule(hr * 0.55, hr * 3.2), hair_m, Vector3(0, hr * 0.15, -hr * 0.62), Vector3.ZERO, Vector3(1.4, 1, 0.55))
	else:
		part(head, sphere(hr * 1.04, 16), hair_m, Vector3(0, hr * 1.3, -hr * 0.1), Vector3.ZERO, Vector3(0.95, 0.68, 1.0))
	match hat:
		"non_la":
			var straw := patterned(Color(0.86, 0.76, 0.52), Color(0.68, 0.56, 0.34), "weave", 0.9, 9.0)
			part(head, cyl(0.004, 0.25 * s, 0.17 * s, 24), straw, Vector3(0, hr * 1.95 + 0.06 * s, 0))
		"cap":
			var cap_m := cloth(SHIRTS[rng.randi() % SHIRTS.size()].darkened(0.2))
			part(head, sphere(hr * 1.09, 14), cap_m, Vector3(0, hr * 1.35, -hr * 0.05), Vector3.ZERO, Vector3(1, 0.62, 1.05))
			part(head, box(Vector3(hr * 1.4, 0.008, hr * 0.9)), cap_m, Vector3(0, hr * 1.42, hr * 1.1), Vector3(-8, 0, 0))
		"helmet":
			var hm := paint(Color.from_hsv(rng.randf(), 0.55, 0.8))
			var helm := part(head, sphere(hr * 1.28, 16), hm, Vector3(0, hr * 1.25, -hr * 0.05), Vector3.ZERO, Vector3(1, 0.85, 1.08))
			helm.name = "Helmet"
	# arms
	var arm_len := 0.17 * h
	var fore_len := 0.15 * h
	var arm_m := shirt_m if bool(opts.get("long_sleeves", rng.randf() < 0.45)) else skin_m
	for side: String in ["L", "R"]:
		var sx := 1.0 if side == "L" else -1.0
		var sh := piv(spine, "Shoulder" + side, Vector3(sx * (chest_r + 0.025 * s), torso_h * 0.93, 0), rig)
		part(sh, sphere(0.055 * w, 10), shirt_m, Vector3.ZERO)
		part(sh, capsule(0.046 * w, arm_len), shirt_m, Vector3(0, -arm_len * 0.45, 0), Vector3.ZERO, Vector3(1, 1, 1))
		var el := piv(sh, "Elbow" + side, Vector3(0, -arm_len * 0.92, 0), rig)
		part(el, capsule(0.038 * w, fore_len), arm_m, Vector3(0, -fore_len * 0.45, 0))
		var hand := piv(el, "Hand" + side, Vector3(0, -fore_len * 0.95, 0), rig)
		part(hand, sphere(0.042 * s, 10), skin_m, Vector3(0, -0.04 * s, 0.005), Vector3.ZERO, Vector3(0.7, 1.25, 0.95))
		sh.rotation.z = sx * 0.07
	# legs
	var thigh := 0.245 * h
	var shin := 0.235 * h
	for side: String in ["L", "R"]:
		var sx := 1.0 if side == "L" else -1.0
		var hip := piv(hips, "Hip" + side, Vector3(sx * 0.085 * w, -0.03 * s, 0), rig)
		part(hip, capsule(0.068 * w, thigh), pants_m, Vector3(0, -thigh * 0.48, 0))
		var knee := piv(hip, "Knee" + side, Vector3(0, -thigh * 0.95, 0), rig)
		var short := bool(opts.get("shorts", false))
		part(knee, capsule(0.052 * w, shin), skin_m if short else pants_m, Vector3(0, -shin * 0.48, 0))
		var ankle := piv(knee, "Ankle" + side, Vector3(0, -shin * 0.98, 0), rig)
		part(ankle, sphere(0.04 * s, 8), skin_m, Vector3(0, 0.0, 0))
		part(ankle, box(Vector3(0.085 * s, 0.03, 0.24 * s)), sandal_m, Vector3(0, -0.035 * s, 0.05 * s))
		part(ankle, capsule(0.035 * s, 0.17 * s), skin_m, Vector3(0, -0.015 * s, 0.06 * s), Vector3(90, 0, 0), Vector3(1.1, 1, 0.6))
	root.set_meta(&"rig", rig)
	root.set_meta(&"height", h)
	root.set_meta(&"leg_len", leg_len)
	return root


static func umbrella(color: Color) -> Node3D:
	var r := Node3D.new()
	r.name = "Umbrella"
	var canopy := cloth(color, 0.6)
	canopy.cull_mode = BaseMaterial3D.CULL_DISABLED
	part(r, cyl(0.0, 0.52, 0.22, 8), canopy, Vector3(0, 0.82, 0))
	part(r, cyl(0.007, 0.007, 0.85), mat(Color(0.2, 0.2, 0.22), 0.4, 0.8), Vector3(0, 0.42, 0))
	part(r, capsule(0.014, 0.10), mat(Color(0.1, 0.08, 0.07), 0.6), Vector3(0, 0.02, 0.0))
	return r


static func shoulder_pole_load(color: Color) -> Node3D:
	## Vendor's đòn gánh baskets (for vendors without a stall).
	var r := Node3D.new()
	r.name = "Gánh"
	var bamboo := mat(Color(0.72, 0.62, 0.38), 0.7)
	part(r, cyl(0.02, 0.02, 1.6), bamboo, Vector3.ZERO, Vector3(90, 0, 0))
	var basket := patterned(Color(0.72, 0.58, 0.36), Color(0.45, 0.33, 0.18), "weave", 0.95, 10.0)
	for z: float in [-0.75, 0.75]:
		part(r, cyl(0.26, 0.2, 0.18, 16), basket, Vector3(0, -0.7, z))
		part(r, sphere(0.2, 10), mat(color, 0.7), Vector3(0, -0.6, z), Vector3.ZERO, Vector3(1, 0.4, 1))
		for a: float in [0.0, 120.0, 240.0]:
			var off := Vector3(cos(deg_to_rad(a)) * 0.2, 0, sin(deg_to_rad(a)) * 0.2)
			var rope := part(r, cyl(0.004, 0.004, 0.62, 4), mat(Color(0.3, 0.25, 0.18), 0.9), Vector3(off.x * 0.5, -0.32, z + off.z * 0.5), Vector3.ZERO, Vector3.ONE, false)
			rope.rotation = Vector3(off.z * 0.5, 0, -off.x * 0.5)
	return r


# -------------------------------------------------------------------------------------------
# Dog (Vện, brindle mixed-breed ~ 0.5 m shoulder)
# -------------------------------------------------------------------------------------------

static func dog(opts: Dictionary = {}) -> Node3D:
	var rig := {}
	var root := _root("dog")
	var sh := float(opts.get("shoulder", 0.5))
	var s := sh / 0.5
	var coat := patterned(Color(0.55, 0.38, 0.20), Color(0.14, 0.09, 0.06), "brindle", 0.9, 3.0)
	var belly := mat(Color(0.75, 0.62, 0.45), 0.9)
	var nose_m := mat(Color(0.05, 0.04, 0.04), 0.3)
	var body := piv(root, "Body", Vector3(0, 0.40 * s, 0), rig)
	part(body, capsule(0.13 * s, 0.68 * s, 16), coat, Vector3(0, 0, -0.02 * s), Vector3(90, 0, 0), Vector3(0.95, 1, 1.05))
	part(body, sphere(0.15 * s, 14), coat, Vector3(0, 0.02 * s, 0.2 * s), Vector3.ZERO, Vector3(0.95, 1.05, 1.0))
	part(body, capsule(0.09 * s, 0.4 * s), belly, Vector3(0, -0.08 * s, 0.05 * s), Vector3(90, 0, 0), Vector3(0.9, 1, 0.7))
	var neck := piv(body, "Neck", Vector3(0, 0.08 * s, 0.27 * s), rig)
	part(neck, capsule(0.075 * s, 0.24 * s), coat, Vector3(0, 0.07 * s, 0.04 * s), Vector3(-50, 0, 0))
	var head := piv(neck, "Head", Vector3(0, 0.16 * s, 0.08 * s), rig)
	part(head, sphere(0.088 * s, 14), coat, Vector3(0, 0.02 * s, 0), Vector3.ZERO, Vector3(1, 0.95, 1.05))
	part(head, capsule(0.048 * s, 0.17 * s), coat, Vector3(0, -0.01 * s, 0.1 * s), Vector3(90, 0, 0), Vector3(1, 1, 0.85))
	part(head, sphere(0.022 * s, 8), nose_m, Vector3(0, 0.005 * s, 0.185 * s))
	var jaw := piv(head, "Jaw", Vector3(0, -0.035 * s, 0.03 * s), rig)
	part(jaw, capsule(0.03 * s, 0.13 * s), belly, Vector3(0, -0.005 * s, 0.07 * s), Vector3(90, 0, 0), Vector3(1, 1, 0.6))
	var eye_m := mat(Color(0.12, 0.07, 0.03), 0.15)
	for sx: float in [-1.0, 1.0]:
		part(head, sphere(0.013 * s, 8), eye_m, Vector3(sx * 0.045 * s, 0.04 * s, 0.07 * s), Vector3.ZERO, Vector3.ONE, false)
		var ear := piv(head, "Ear" + ("L" if sx > 0 else "R"), Vector3(sx * 0.055 * s, 0.075 * s, -0.02 * s), rig)
		part(ear, prism(Vector3(0.07 * s, 0.09 * s, 0.018 * s)), coat, Vector3(0, 0.035 * s, 0), Vector3(0, 0, sx * -15))
	var tail := piv(body, "Tail", Vector3(0, 0.06 * s, -0.37 * s), rig)
	part(tail, capsule(0.025 * s, 0.30 * s), coat, Vector3(0, 0.12 * s, -0.04 * s), Vector3(-20, 0, 0))
	var leg_m := coat
	for leg: Array in [["FL", 0.09, 0.22], ["FR", -0.09, 0.22], ["BL", 0.085, -0.25], ["BR", -0.085, -0.25]]:
		var n: String = leg[0]
		var hip := piv(body, "Leg" + n, Vector3(float(leg[1]) * s, -0.03 * s, float(leg[2]) * s), rig)
		part(hip, capsule(0.045 * s, 0.22 * s), leg_m, Vector3(0, -0.09 * s, 0))
		var knee := piv(hip, "Knee" + n, Vector3(0, -0.19 * s, 0), rig)
		part(knee, capsule(0.028 * s, 0.2 * s), leg_m, Vector3(0, -0.08 * s, 0))
		part(knee, sphere(0.033 * s, 8), belly, Vector3(0, -0.175 * s, 0.015 * s), Vector3.ZERO, Vector3(1, 0.6, 1.3))
	root.set_meta(&"rig", rig)
	return root


# -------------------------------------------------------------------------------------------
# Birds: pigeon (0.32 m), crow (0.46 m), sparrow (0.15 m)
# -------------------------------------------------------------------------------------------

static func bird(kind: String, opts: Dictionary = {}) -> Node3D:
	var rig := {}
	var root := _root("bird")
	var L := 0.32
	var body_m: StandardMaterial3D
	var wing_m: StandardMaterial3D
	var head_m: StandardMaterial3D
	var neck_m: StandardMaterial3D
	var beak_m := mat(Color(0.25, 0.22, 0.22), 0.5)
	var leg_m := mat(Color(0.75, 0.32, 0.3), 0.6)
	var eye_m := mat(Color(0.9, 0.45, 0.1), 0.1)
	match kind:
		"crow":
			L = 0.46
			body_m = mat(Color(0.035, 0.035, 0.045), 0.35, 0.0, "crow_body")
			body_m.rim_enabled = true
			body_m.rim = 0.4
			body_m.rim_tint = 0.2
			wing_m = body_m
			head_m = body_m
			neck_m = mat(Color(0.20, 0.21, 0.23), 0.6)   # grey nape (house crow)
			beak_m = mat(Color(0.03, 0.03, 0.03), 0.3)
			leg_m = mat(Color(0.05, 0.05, 0.05), 0.5)
			eye_m = mat(Color(0.06, 0.05, 0.04), 0.1)
		"sparrow":
			L = 0.15
			body_m = patterned(Color(0.62, 0.48, 0.32), Color(0.30, 0.20, 0.12), "feather", 0.9, 22.0)
			wing_m = patterned(Color(0.55, 0.40, 0.24), Color(0.18, 0.12, 0.08), "feather", 0.9, 30.0)
			head_m = mat(Color(0.40, 0.28, 0.18), 0.85)
			neck_m = mat(Color(0.80, 0.76, 0.68), 0.9)
			beak_m = mat(Color(0.18, 0.15, 0.12), 0.5)
			leg_m = mat(Color(0.55, 0.42, 0.35), 0.6)
			eye_m = mat(Color(0.03, 0.03, 0.03), 0.1)
		_:
			var tint: Color = opts.get("tint", Color(0.58, 0.60, 0.66))
			body_m = patterned(tint, tint.darkened(0.25), "feather", 0.8, 12.0)
			wing_m = patterned(tint.lightened(0.08), tint.darkened(0.45), "feather", 0.8, 9.0)
			head_m = mat(tint.darkened(0.12), 0.75)
			neck_m = mat(Color(0.30, 0.45, 0.38), 0.3, 0.45, "pigeon_neck")
			neck_m.rim_enabled = true
			neck_m.rim = 0.7
			neck_m.rim_tint = 1.0
	var s := L / 0.32
	var body := piv(root, "Body", Vector3(0, 0.085 * s, 0), rig)
	part(body, sphere(0.075 * s, 16), body_m, Vector3(0, 0, 0), Vector3(-12, 0, 0), Vector3(0.95, 0.9, 1.45))
	part(body, sphere(0.06 * s, 12), neck_m, Vector3(0, 0.045 * s, 0.07 * s), Vector3.ZERO, Vector3(1, 1.15, 1))
	var head := piv(body, "Head", Vector3(0, 0.085 * s, 0.1 * s), rig)
	part(head, sphere(0.034 * s, 12), head_m, Vector3(0, 0.018 * s, 0.01 * s), Vector3.ZERO, Vector3(0.95, 1, 1.15))
	var beak_len := 0.05 if kind == "crow" else 0.024
	part(head, cyl(0.002 * s, 0.009 * s * (1.6 if kind == "crow" else 1.0), beak_len * s, 6), beak_m,
		Vector3(0, 0.014 * s, 0.045 * s + beak_len * 0.5 * s), Vector3(90, 0, 0))
	for sx: float in [-1.0, 1.0]:
		part(head, sphere(0.0065 * s, 6), eye_m, Vector3(sx * 0.024 * s, 0.026 * s, 0.024 * s), Vector3.ZERO, Vector3.ONE, false)
	var tail := piv(body, "Tail", Vector3(0, 0.01 * s, -0.1 * s), rig)
	part(tail, box(Vector3(0.06 * s, 0.01 * s, 0.11 * s)), wing_m, Vector3(0, -0.005 * s, -0.05 * s), Vector3(10, 0, 0))
	for side: String in ["L", "R"]:
		var sx := 1.0 if side == "L" else -1.0
		var wing := piv(body, "Wing" + side, Vector3(sx * 0.055 * s, 0.03 * s, 0.03 * s), rig)
		# folded: wing lies along the body; flapping rotates around Z (local)
		var wm := part(wing, box(Vector3(0.20 * s, 0.012 * s, 0.10 * s)), wing_m, Vector3(sx * 0.09 * s, 0, -0.04 * s))
		wm.name = "WingMesh"
		part(wing, box(Vector3(0.12 * s, 0.008 * s, 0.07 * s)), wing_m, Vector3(sx * 0.2 * s, 0, -0.06 * s), Vector3(0, sx * 18, 0))
		var leg := piv(body, "Leg" + side, Vector3(sx * 0.022 * s, -0.045 * s, 0.01 * s), rig)
		part(leg, cyl(0.004 * s, 0.004 * s, 0.05 * s, 5), leg_m, Vector3(0, -0.025 * s, 0), Vector3.ZERO, Vector3.ONE, false)
		part(leg, box(Vector3(0.018 * s, 0.004 * s, 0.03 * s)), leg_m, Vector3(0, -0.05 * s, 0.01 * s), Vector3.ZERO, Vector3.ONE, false)
	if bool(opts.get("leg_band", false)):
		part(rig["LegL"], torus(0.004 * s, 0.008 * s, 8), mat(Color(0.95, 0.15, 0.1), 0.4), Vector3(0, -0.03 * s, 0))
	root.set_meta(&"rig", rig)
	root.set_meta(&"wing_span", 0.62 * s)
	return root


# -------------------------------------------------------------------------------------------
# Small life
# -------------------------------------------------------------------------------------------

static func mouse() -> Node3D:
	var rig := {}
	var root := _root("mouse")
	var fur := patterned(Color(0.42, 0.37, 0.33), Color(0.25, 0.21, 0.19), "noise", 0.95, 30.0)
	var pink := skin(Color(0.86, 0.62, 0.6))
	var body := piv(root, "Body", Vector3(0, 0.032, 0), rig)
	part(body, sphere(0.032, 12), fur, Vector3.ZERO, Vector3.ZERO, Vector3(0.9, 0.85, 1.6))
	var head := piv(body, "Head", Vector3(0, 0.008, 0.05), rig)
	part(head, sphere(0.02, 10), fur, Vector3(0, 0, 0.012), Vector3.ZERO, Vector3(0.9, 0.85, 1.5))
	part(head, sphere(0.005, 6), pink, Vector3(0, 0, 0.042), Vector3.ZERO, Vector3.ONE, false)
	for sx: float in [-1.0, 1.0]:
		part(head, sphere(0.012, 8), pink, Vector3(sx * 0.013, 0.017, 0.0), Vector3.ZERO, Vector3(1, 1, 0.3), false)
		part(head, sphere(0.004, 6), mat(Color(0.02, 0.02, 0.02), 0.1), Vector3(sx * 0.011, 0.007, 0.024), Vector3.ZERO, Vector3.ONE, false)
	var tail := piv(body, "Tail", Vector3(0, -0.005, -0.048), rig)
	part(tail, cyl(0.0015, 0.004, 0.09, 5), pink, Vector3(0, 0, -0.045), Vector3(90, 0, 0), Vector3.ONE, false)
	var tail2 := piv(tail, "Tail2", Vector3(0, 0, -0.09), rig)
	part(tail2, cyl(0.001, 0.0015, 0.07, 4), pink, Vector3(0, 0, -0.035), Vector3(90, 0, 0), Vector3.ONE, false)
	for leg: Array in [["FL", 0.018, 0.03], ["FR", -0.018, 0.03], ["BL", 0.02, -0.025], ["BR", -0.02, -0.025]]:
		var p := piv(body, "Leg" + str(leg[0]), Vector3(float(leg[1]), -0.02, float(leg[2])), rig)
		part(p, box(Vector3(0.008, 0.016, 0.012)), pink, Vector3(0, -0.006, 0.003), Vector3.ZERO, Vector3.ONE, false)
	root.set_meta(&"rig", rig)
	return root


static func gecko() -> Node3D:
	## Built lying in the XZ plane (belly −Y); the gecko script orients it onto walls.
	var rig := {}
	var root := _root("gecko")
	var m := patterned(Color(0.78, 0.72, 0.62), Color(0.55, 0.48, 0.40), "noise", 0.7, 40.0)
	m.subsurf_scatter_enabled = true
	m.subsurf_scatter_strength = 0.3
	var body := piv(root, "Body", Vector3(0, 0.008, 0), rig)
	part(body, sphere(0.011, 10), m, Vector3.ZERO, Vector3.ZERO, Vector3(1.0, 0.55, 2.8))
	part(body, sphere(0.009, 10), m, Vector3(0, 0.001, 0.038), Vector3.ZERO, Vector3(1.0, 0.6, 1.5))
	for sx: float in [-1.0, 1.0]:
		part(body, sphere(0.0028, 6), mat(Color(0.05, 0.05, 0.04), 0.1), Vector3(sx * 0.0065, 0.004, 0.042), Vector3.ZERO, Vector3.ONE, false)
	var tail := piv(body, "Tail", Vector3(0, 0, -0.03), rig)
	part(tail, cyl(0.001, 0.007, 0.06, 6), m, Vector3(0, 0, -0.03), Vector3(-90, 0, 0), Vector3(1, 1, 0.6), false)
	for leg: Array in [["FL", 1.0, 0.018], ["FR", -1.0, 0.018], ["BL", 1.0, -0.018], ["BR", -1.0, -0.018]]:
		var p := piv(body, "Leg" + str(leg[0]), Vector3(float(leg[1]) * 0.009, 0, float(leg[2])), rig)
		part(p, box(Vector3(0.016, 0.003, 0.004)), m, Vector3(float(leg[1]) * 0.008, -0.002, 0), Vector3(0, float(leg[1]) * -25.0, 0), Vector3.ONE, false)
	root.set_meta(&"rig", rig)
	return root


# -------------------------------------------------------------------------------------------
# Vehicles
# -------------------------------------------------------------------------------------------

static func _wheel(parent: Node3D, n: String, pos: Vector3, radius: float, width: float, rig: Dictionary, spokes := 5) -> Node3D:
	var w := piv(parent, n, pos, rig)
	var tyre := mat(Color(0.05, 0.05, 0.055), 0.85, 0.0, "tyre")
	var rim_m := mat(Color(0.62, 0.63, 0.66), 0.25, 0.9, "rim")
	part(w, torus(radius - width * 0.9, radius, 22), tyre, Vector3.ZERO, Vector3(0, 0, 90), Vector3(1, width / (width * 0.9) * 0.55, 1))
	part(w, cyl(radius * 0.18, radius * 0.18, width * 0.9, 10), rim_m, Vector3.ZERO, Vector3(0, 0, 90))
	for i in spokes:
		var a := TAU * float(i) / float(spokes)
		var sp := part(w, box(Vector3(width * 0.25, radius * 0.75, radius * 0.07)), rim_m,
			Vector3(0, cos(a) * radius * 0.42, sin(a) * radius * 0.42))
		sp.rotation.x = -a
	w.set_meta(&"radius", radius)
	return w


## Fictional Vietnamese commuter scooter (step-through), with rider.
static func motorbike(opts: Dictionary = {}) -> Node3D:
	var rig := {}
	var root := _root("motorbike")
	var rng := RandomNumberGenerator.new()
	rng.seed = int(opts.get("seed", randi()))
	var paints: Array[Color] = [Color(0.72, 0.08, 0.08), Color(0.08, 0.10, 0.14), Color(0.85, 0.85, 0.86),
		Color(0.12, 0.22, 0.55), Color(0.55, 0.56, 0.58), Color(0.95, 0.75, 0.15)]
	var body_m := paint(paints[rng.randi() % paints.size()])
	var black := mat(Color(0.06, 0.06, 0.07), 0.55)
	var chrome := mat(Color(0.8, 0.8, 0.82), 0.15, 1.0, "chrome")
	var seat_m := mat(Color(0.08, 0.07, 0.07), 0.45)
	var r := 0.28
	var wb := 1.24
	var fw := _wheel(root, "WheelF", Vector3(0, r, wb * 0.5), r, 0.085, rig, 3)
	var rw := _wheel(root, "WheelR", Vector3(0, r, -wb * 0.5), r, 0.095, rig, 3)
	var frame := piv(root, "Frame", Vector3.ZERO, rig)
	# rear body cowl + seat
	part(frame, capsule(0.17, 0.82, 16), body_m, Vector3(0, 0.64, -0.3), Vector3(90, 0, 0), Vector3(0.95, 1, 0.75))
	part(frame, capsule(0.15, 0.7, 12), seat_m, Vector3(0, 0.79, -0.22), Vector3(90, 0, 0), Vector3(0.9, 1, 0.38))
	part(frame, box(Vector3(0.24, 0.05, 0.22)), black, Vector3(0, 0.73, -0.72))     # rear rack
	part(frame, sphere(0.05, 8), mat(Color(0.8, 0.05, 0.05), 0.2, 0.0, "taillight"), Vector3(0, 0.66, -0.72), Vector3.ZERO, Vector3(1.6, 0.6, 0.5))
	# floorboard & leg shield
	part(frame, box(Vector3(0.32, 0.06, 0.48)), black, Vector3(0, 0.33, 0.12))
	part(frame, box(Vector3(0.36, 0.62, 0.06)), body_m, Vector3(0, 0.62, 0.38), Vector3(-22, 0, 0))
	part(frame, box(Vector3(0.18, 0.5, 0.18)), body_m, Vector3(0, 0.55, 0.5), Vector3(-22, 0, 0))
	# fork + mudguard + exhaust
	part(frame, cyl(0.022, 0.022, 0.62), chrome, Vector3(0, 0.6, 0.58), Vector3(-22, 0, 0))
	part(frame, cyl(0.31, 0.31, 0.09, 16), body_m, Vector3(0, r + 0.02, wb * 0.5), Vector3(0, 0, 90), Vector3(1, 1, 1))
	part(frame, cyl(0.035, 0.045, 0.52), chrome, Vector3(-0.15, 0.27, -0.38), Vector3(90, 0, 0))
	part(frame, box(Vector3(0.12, 0.2, 0.42)), black, Vector3(0.1, 0.32, -0.42))      # engine/swingarm
	var bar := piv(frame, "Handlebar", Vector3(0, 1.0, 0.46), rig)
	part(bar, cyl(0.014, 0.014, 0.66), black, Vector3.ZERO, Vector3(0, 0, 90))
	part(bar, box(Vector3(0.3, 0.14, 0.16)), body_m, Vector3(0, 0.03, 0.04))
	var head_m := mat(Color(1.0, 0.97, 0.88), 0.1, 0.0, "headlamp")
	head_m.emission_enabled = true
	head_m.emission = Color(1.0, 0.95, 0.8)
	head_m.emission_energy_multiplier = 1.5
	part(bar, sphere(0.06, 10), head_m, Vector3(0, 0.02, 0.13), Vector3.ZERO, Vector3(1.5, 0.8, 0.5))
	for sx: float in [-1.0, 1.0]:
		part(bar, cyl(0.006, 0.006, 0.22, 4), chrome, Vector3(sx * 0.22, 0.12, -0.02), Vector3(0, 0, sx * 10))
		part(bar, sphere(0.035, 8), chrome, Vector3(sx * 0.24, 0.23, -0.02), Vector3.ZERO, Vector3(1, 0.7, 0.3))
	if bool(opts.get("rider", true)):
		var hrider := human({"seed": rng.randi(), "hat": "helmet", "long_sleeves": true})
		hrider.name = "Rider"
		hrider.position = Vector3(0, 0.79 - float(hrider.get_meta(&"leg_len")) - 0.03, -0.18)
		frame.add_child(hrider)
		rig["Rider"] = hrider
		if rng.randf() < 0.3:
			var pas := human({"seed": rng.randi(), "hat": "helmet" if rng.randf() < 0.8 else "non_la"})
			pas.name = "Passenger"
			pas.position = Vector3(0, 0.81 - float(pas.get_meta(&"leg_len")) - 0.03, -0.55)
			frame.add_child(pas)
			rig["Passenger"] = pas
	if bool(opts.get("cargo", rng.randf() < 0.18)):
		var cargo := patterned(Color(0.75, 0.6, 0.35), Color(0.5, 0.36, 0.2), "weave", 0.9, 8.0)
		part(frame, box(Vector3(0.6, 0.45, 0.45)), cargo, Vector3(0, 1.0, -0.8))
	root.set_meta(&"rig", rig)
	root.set_meta(&"wheels", [fw, rw])
	root.set_meta(&"length", 1.85)
	return root


static func bicycle(opts: Dictionary = {}) -> Node3D:
	var rig := {}
	var root := _root("bicycle")
	var rng := RandomNumberGenerator.new()
	rng.seed = int(opts.get("seed", randi()))
	var frame_m := paint([Color(0.1, 0.25, 0.2), Color(0.55, 0.1, 0.1), Color(0.12, 0.12, 0.13), Color(0.75, 0.72, 0.6)][rng.randi() % 4])
	var chrome := mat(Color(0.8, 0.8, 0.82), 0.15, 1.0, "chrome")
	var r := 0.33
	var fw := _wheel(root, "WheelF", Vector3(0, r, 0.52), r, 0.035, rig, 12)
	var rw := _wheel(root, "WheelR", Vector3(0, r, -0.52), r, 0.035, rig, 12)
	var frame := piv(root, "Frame", Vector3.ZERO, rig)
	var bb := Vector3(0, 0.30, -0.02)
	var seat := Vector3(0, 0.84, -0.22)
	var head := Vector3(0, 0.86, 0.38)
	for seg: Array in [[bb, seat], [bb, head], [seat, head - Vector3(0, 0.08, 0)], [bb, Vector3(0, r, -0.52)],
			[seat - Vector3(0, 0.06, 0), Vector3(0, r, -0.52)], [head, Vector3(0, r, 0.52)]]:
		_rod(frame, seg[0], seg[1], 0.016, frame_m)
	part(frame, capsule(0.05, 0.22), mat(Color(0.08, 0.07, 0.06), 0.5), seat + Vector3(0, 0.03, 0), Vector3(90, 0, 0), Vector3(1, 1, 0.45))
	part(frame, cyl(0.012, 0.012, 0.56), chrome, head + Vector3(0, 0.12, -0.05), Vector3(0, 0, 90))
	var basket := patterned(Color(0.7, 0.58, 0.36), Color(0.45, 0.34, 0.2), "weave", 0.95, 12.0)
	if rng.randf() < 0.6:
		part(frame, box(Vector3(0.34, 0.22, 0.26)), basket, head + Vector3(0, 0.0, 0.2))
	var crank := piv(frame, "Crank", bb, rig)
	part(crank, cyl(0.09, 0.09, 0.01, 16), chrome, Vector3(0.05, 0, 0), Vector3(0, 0, 90))
	for sx: float in [-1.0, 1.0]:
		var arm := part(crank, box(Vector3(0.01, 0.17, 0.02)), chrome, Vector3(sx * 0.07, sx * 0.08, 0))
		arm.name = "Arm"
		part(crank, box(Vector3(0.09, 0.02, 0.05)), mat(Color(0.05, 0.05, 0.05), 0.6), Vector3(sx * 0.11, sx * 0.165, 0))
	if bool(opts.get("rider", true)):
		var hr := human({"seed": rng.randi(), "hat": "non_la" if rng.randf() < 0.4 else ""})
		hr.name = "Rider"
		hr.position = Vector3(0, seat.y + 0.03 - float(hr.get_meta(&"leg_len")) - 0.03, seat.z - 0.02)
		frame.add_child(hr)
		rig["Rider"] = hr
	root.set_meta(&"rig", rig)
	root.set_meta(&"wheels", [fw, rw])
	root.set_meta(&"length", 1.7)
	return root


static func _rod(parent: Node3D, a: Vector3, b: Vector3, radius: float, m: Material) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = cyl(radius, radius, a.distance_to(b), 6)
	mi.material_override = m
	parent.add_child(mi)
	var mid := (a + b) * 0.5
	var dir := (b - a).normalized()
	var up_ref := Vector3.FORWARD if absf(dir.dot(Vector3.FORWARD)) < 0.95 else Vector3.RIGHT
	var x := dir.cross(up_ref).normalized()
	var z := x.cross(dir).normalized()
	mi.transform = Transform3D(Basis(x, dir, z), mid)


## Small city hatchback / taxi.
static func car(opts: Dictionary = {}) -> Node3D:
	var rig := {}
	var root := _root("car")
	var rng := RandomNumberGenerator.new()
	rng.seed = int(opts.get("seed", randi()))
	var taxi := bool(opts.get("taxi", rng.randf() < 0.35))
	var col: Color = Color(0.92, 0.92, 0.9) if taxi else [Color(0.75, 0.75, 0.78), Color(0.1, 0.1, 0.12),
		Color(0.55, 0.08, 0.08), Color(0.2, 0.3, 0.5), Color(0.9, 0.9, 0.88)][rng.randi() % 5]
	var body_m := paint(col)
	var glass := mat(Color(0.08, 0.1, 0.12), 0.05, 0.2, "car_glass")
	var black := mat(Color(0.05, 0.05, 0.05), 0.6)
	var L := 3.85
	var W := 1.70
	var r := 0.31
	var wheels: Array[Node3D] = []
	for wpos: Vector3 in [Vector3(0.72, r, 1.25), Vector3(-0.72, r, 1.25), Vector3(0.72, r, -1.22), Vector3(-0.72, r, -1.22)]:
		wheels.append(_wheel(root, "Wheel%d" % wheels.size(), wpos, r, 0.2, rig, 5))
	var frame := piv(root, "Frame", Vector3.ZERO, rig)
	part(frame, box(Vector3(W, 0.62, L)), body_m, Vector3(0, 0.62, 0))
	part(frame, box(Vector3(W * 0.96, 0.2, L * 0.98)), body_m, Vector3(0, 0.38, 0))
	part(frame, box(Vector3(W * 0.88, 0.56, L * 0.52)), body_m, Vector3(0, 1.2, -0.25))
	part(frame, box(Vector3(W * 0.9, 0.46, L * 0.47)), glass, Vector3(0, 1.2, -0.25))
	part(frame, box(Vector3(W * 0.84, 0.5, 0.05)), glass, Vector3(0, 1.17, 0.78), Vector3(-30, 0, 0))
	part(frame, box(Vector3(W * 1.01, 0.16, 0.12)), black, Vector3(0, 0.42, L * 0.5))
	part(frame, box(Vector3(W * 1.01, 0.16, 0.12)), black, Vector3(0, 0.42, -L * 0.5))
	var lamp := mat(Color(1, 0.97, 0.9), 0.1, 0.0, "car_lamp")
	lamp.emission_enabled = true
	lamp.emission = Color(1, 0.95, 0.85)
	var tail := mat(Color(0.7, 0.04, 0.04), 0.15, 0.0, "car_tail")
	for sx: float in [-1.0, 1.0]:
		part(frame, box(Vector3(0.32, 0.12, 0.05)), lamp, Vector3(sx * 0.58, 0.74, L * 0.5 + 0.005))
		part(frame, box(Vector3(0.26, 0.14, 0.05)), tail, Vector3(sx * 0.62, 0.78, -L * 0.5 - 0.005))
		part(frame, box(Vector3(0.12, 0.08, 0.18)), black, Vector3(sx * (W * 0.5 + 0.05), 1.0, 0.55))
	if taxi:
		var sign_m := mat(Color(0.1, 0.55, 0.3), 0.4)
		sign_m.emission_enabled = true
		sign_m.emission = Color(0.2, 0.9, 0.5)
		sign_m.emission_energy_multiplier = 0.6
		part(frame, box(Vector3(0.5, 0.14, 0.18)), sign_m, Vector3(0, 1.55, -0.2))
	root.set_meta(&"rig", rig)
	root.set_meta(&"wheels", wheels)
	root.set_meta(&"length", L)
	return root
