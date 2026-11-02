extends Node3D
## vehicles-nature plant showcase (tools/screenshot.sh scene=res://assets/models/nature/preview/nature_showcase.tscn).
## layout "lineup": every catalog entry in rows (trees/palms/bamboo at the back, climbers in the middle,
## shrubs/ground cover in front, aquatic plants on a pond) - for per-asset QA.
## layout "garden": a composed temple-courtyard vignette (nature_garden.tscn) for cat-eye-height shots:
## banyan, frangipani, bamboo, palms, hedge, ferns, weeds along a kerb, a lotus pond with a willow.
## A cat (assets/models/cat/cat.glb, if present) stands near the origin for scale.

const Env := preload("res://assets/models/nature/preview/showcase_env.gd")
const CAT_PATH := "res://assets/models/cat/cat.glb"

@export var catalog_path := "res://assets/models/nature/catalog.json"
@export var only_ids: PackedStringArray = []
@export_enum("lineup", "garden") var layout := "lineup"

var _entries: Dictionary = {}


func _ready() -> void:
	Env.build(self, "brick_courtyard_" if layout == "garden" else "pavers_", 0.5 if layout == "garden" else 0.92)
	_load_catalog()
	if layout == "garden":
		_garden()
	else:
		_lineup()
	if ResourceLoader.exists(CAT_PATH):
		var cat := (load(CAT_PATH) as PackedScene).instantiate() as Node3D
		cat.name = "ScaleCat"
		add_child(cat)
		cat.position = Vector3(0.6, 0.0, 3.0) if layout == "lineup" else Vector3(0.3, 0.0, 2.2)
		cat.rotation.y = deg_to_rad(-60.0 if layout == "lineup" else 200.0)


func _load_catalog() -> void:
	var f := FileAccess.open(catalog_path, FileAccess.READ)
	if f == null:
		push_warning("nature showcase: no catalog at %s" % catalog_path)
		return
	var data: Variant = JSON.parse_string(f.get_as_text())
	if data is Array:
		for e: Variant in data:
			var d := e as Dictionary
			_entries[String(d["id"])] = d


func _spawn(id: String, pos: Vector3, yaw_deg := 0.0, scale_f := 1.0) -> Node3D:
	if not _entries.has(id):
		return null
	var ps := load(String((_entries[id] as Dictionary)["file"])) as PackedScene
	if ps == null:
		return null
	var n := ps.instantiate() as Node3D
	add_child(n)
	n.position = pos
	n.rotation.y = deg_to_rad(yaw_deg)
	if scale_f != 1.0:
		n.scale = Vector3.ONE * scale_f
	return n


func _lineup() -> void:
	var x_back := -40.0
	var x_mid := -6.0
	var x_front := -3.0
	var pond_x := 7.0
	var pond := false
	for id: String in _entries:
		if only_ids.size() > 0 and not (id in only_ids):
			continue
		var d := _entries[id] as Dictionary
		var w := maxf(float(d.get("width", 1.0)), 0.5)
		var kind := String(d.get("kind", ""))
		if kind in ["tree", "palm", "bamboo"]:
			_spawn(id, Vector3(x_back + w * 0.5, 0.0, -12.0))
			x_back += w + 0.5
		elif kind == "aquatic":
			pond = true
			_spawn(id, Vector3(pond_x, 0.02, 2.0))
			pond_x += 2.6
		elif kind == "climber":
			var rail := String(d.get("mount", "")).begins_with("rail")
			_spawn(id, Vector3(x_mid + w * 0.5, 2.6 if rail else 0.0, -2.5))
			x_mid += w + 0.5
		else:
			_spawn(id, Vector3(x_front + w * 0.5, 0.0, 1.5))
			x_front += w + 0.4
	if pond:
		_pond(Vector3(9.6, 0.0, 2.0), Vector2(7.0, 4.0))


func _garden() -> void:
	# back: the old banyan with a shrine wall, bamboo and palms framing it
	_spawn("banyan", Vector3(-4.0, 0.0, -13.0), 20.0)
	_spawn("bamboo_clump", Vector3(9.0, 0.0, -7.5), 0.0)
	_spawn("areca_palm", Vector3(5.5, 0.0, -11.0), 40.0)
	_spawn("coconut_palm", Vector3(-15.0, 0.0, -4.0), 0.0)
	_spawn("flame_tree", Vector3(18.0, 0.0, -18.0), 0.0)
	_spawn("sao_tree", Vector3(-22.0, 0.0, -20.0), 0.0)
	_wall(Vector3(1.5, 0.0, -4.6), Vector3(9.0, 2.4, 0.3))
	_spawn("bougainvillea_wall", Vector3(1.0, 0.0, -4.39), 0.0)
	_spawn("bougainvillea_cascade", Vector3(4.2, 2.48, -4.38), 0.0)
	# middle: frangipani, hedge and flowering shrubs
	_spawn("frangipani", Vector3(-3.2, 0.0, -2.2), 60.0)
	_spawn("hedge_trimmed", Vector3(3.0, 0.0, -1.8), 0.0)
	_spawn("shrub_ixora", Vector3(-1.0, 0.0, -1.0), 30.0)
	_spawn("fern_clump", Vector3(0.9, 0.0, -0.6), 10.0)
	_spawn("fern_clump", Vector3(-4.6, 0.0, 0.4), 140.0, 0.85)
	# foreground at cat scale: kerb weeds, grass, moss, fallen leaves
	_kerb(Vector3(0.0, 0.0, 0.9), 14.0)
	_spawn("weeds_crack_a", Vector3(-1.4, 0.0, 1.12), 0.0)
	_spawn("weeds_crack_b", Vector3(1.6, 0.0, 1.1), 180.0)
	_spawn("grass_tuft_a", Vector3(-0.5, 0.0, 1.5), 0.0)
	_spawn("grass_tuft_b", Vector3(0.8, 0.0, 1.75), 70.0)
	_spawn("grass_tuft_a", Vector3(2.3, 0.0, 1.4), 200.0, 0.8)
	_spawn("moss_patch", Vector3(-2.2, 0.0, 1.6), 90.0)
	_spawn("leaf_litter", Vector3(-0.6, 0.0, 2.6), 0.0)
	_spawn("leaf_litter", Vector3(-3.5, 0.0, -0.6), 120.0)
	# right: lotus pond with a willow leaning over it
	_pond(Vector3(7.5, 0.0, 1.5), Vector2(7.0, 5.0))
	_spawn("lotus_cluster", Vector3(6.6, 0.0, 1.0), 0.0)
	_spawn("water_hyacinth", Vector3(8.8, 0.0, 2.6), 30.0)
	_spawn("weeping_willow", Vector3(11.5, 0.0, -1.0), 200.0)


func _pond(center: Vector3, size: Vector2) -> void:
	var wm := MeshInstance3D.new()
	wm.name = "Pond"
	var pm := PlaneMesh.new()
	pm.size = size
	wm.mesh = pm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.1, 0.17, 0.14, 0.88)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.roughness = 0.04
	mat.metallic_specular = 0.9
	wm.material_override = mat
	wm.position = center + Vector3(0.0, 0.012, 0.0)
	add_child(wm)
	# stone rim
	for s: int in [-1, 1]:
		_box(center + Vector3(0.0, 0.06, s * (size.y * 0.5 + 0.15)), Vector3(size.x + 0.6, 0.12, 0.3), Color(0.45, 0.44, 0.42))
		_box(center + Vector3(s * (size.x * 0.5 + 0.15), 0.06, 0.0), Vector3(0.3, 0.12, size.y), Color(0.45, 0.44, 0.42))


func _kerb(center: Vector3, length: float) -> void:
	_box(center + Vector3(0.0, 0.075, 0.0), Vector3(length, 0.15, 0.25), Color(0.5, 0.5, 0.48))


func _wall(center: Vector3, size: Vector3) -> void:
	_box(center + Vector3(0.0, size.y * 0.5, 0.0), size, Color(0.78, 0.66, 0.42))
	_box(center + Vector3(0.0, size.y + 0.04, 0.0), Vector3(size.x + 0.1, 0.08, size.z + 0.12), Color(0.55, 0.3, 0.22))


func _box(pos: Vector3, size: Vector3, color: Color) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = 0.9
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	var sb := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	sb.position = pos
	add_child(sb)
