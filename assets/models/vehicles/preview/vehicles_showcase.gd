extends Node3D
## vehicles-nature vehicle showcase (tools/screenshot.sh scene=res://assets/models/vehicles/preview/vehicles_showcase.tscn).
## layout "lineup": every catalog vehicle side by side (helmets in front) - per-asset QA.
## layout "street": a parked-street vignette (vehicles_street.tscn) - asphalt lane, kerb + pavement with
## scooters parked nose-out the Hanoi way, the taxi and van at the kerb, helmets on seats/ground.
## A cat (assets/models/cat/cat.glb, if present) gives scale.

const Env := preload("res://assets/models/nature/preview/showcase_env.gd")
const CAT_PATH := "res://assets/models/cat/cat.glb"

@export var catalog_path := "res://assets/models/vehicles/catalog.json"
@export var only_ids: PackedStringArray = []
@export_enum("lineup", "street") var layout := "lineup"

var _entries: Dictionary = {}


func _ready() -> void:
	Env.build(self, "asphalt_", 0.25, 40.0, -150.0 if layout == "street" else -38.0)
	_load_catalog()
	if layout == "street":
		_street()
	else:
		_lineup()
	if ResourceLoader.exists(CAT_PATH):
		var cat := (load(CAT_PATH) as PackedScene).instantiate() as Node3D
		cat.name = "ScaleCat"
		add_child(cat)
		if layout == "street":
			cat.position = Vector3(-0.9, 0.15, 3.6)
			cat.rotation.y = deg_to_rad(150.0)
		else:
			cat.position = Vector3(0.6, 0.0, 3.0)
			cat.rotation.y = deg_to_rad(-60.0)


func _load_catalog() -> void:
	var f := FileAccess.open(catalog_path, FileAccess.READ)
	if f == null:
		push_warning("vehicles showcase: no catalog at %s" % catalog_path)
		return
	var data: Variant = JSON.parse_string(f.get_as_text())
	if data is Array:
		for e: Variant in data:
			var d := e as Dictionary
			_entries[String(d["id"])] = d


func _spawn(id: String, pos: Vector3, yaw_deg := 0.0) -> Node3D:
	if not _entries.has(id):
		return null
	var ps := load(String((_entries[id] as Dictionary)["file"])) as PackedScene
	if ps == null:
		return null
	var n := ps.instantiate() as Node3D
	n.name = id
	add_child(n)
	n.position = pos
	n.rotation.y = deg_to_rad(yaw_deg)
	return n


func _lineup() -> void:
	var x := -6.0
	var hx := -1.0
	for id: String in _entries:
		if only_ids.size() > 0 and not (id in only_ids):
			continue
		var d := _entries[id] as Dictionary
		if String(d.get("kind", "")) == "helmet":
			_spawn(id, Vector3(hx, 0.0, 2.2), 30.0)
			hx += 0.5
			continue
		var w := float(d.get("width", 1.0))
		_spawn(id, Vector3(x + w * 0.5, 0.0, 0.0), -25.0)
		x += w + 0.6


func _street() -> void:
	# pavement (z > 2.2, raised 0.15) with a granite kerb; road toward -Z
	_slab(Vector3(0.0, 0.075, 6.2), Vector3(40.0, 0.15, 8.0), "concrete_alley_", 0.5)
	_slab(Vector3(0.0, 0.075, 2.3), Vector3(40.0, 0.15, 0.25), "granite_curb_", 1.0)
	_box(Vector3(0.0, 2.0, 10.4), Vector3(40.0, 4.0, 0.4), Color(0.8, 0.68, 0.42))
	# scooters parked nose-out on the pavement, slightly irregular
	var bikes := ["scooter_auto", "underbone_step", "manual_classic", "scooter_auto", "underbone_step"]
	var bx := -6.5
	for i: int in bikes.size():
		_spawn(bikes[i], Vector3(bx, 0.15, 4.2 + (0.15 if i % 2 == 0 else -0.1)), 180.0 + (i * 7 % 13) - 6.0)
		bx += 0.85 + (0.1 if i % 2 == 0 else 0.0)
	_spawn("bicycle_city", Vector3(-0.6, 0.15, 5.6), 160.0)
	_spawn("helmet_half", Vector3(-1.6, 0.15, 3.1), 40.0)
	_spawn("helmet_open", Vector3(-1.2, 0.15, 3.3), -20.0)
	# kerbside: taxi and van parked along the road, a cyclo and cargo trike waiting
	_spawn("taxi_hatch", Vector3(3.8, 0.0, 0.9), 90.0)
	_spawn("delivery_van", Vector3(10.5, 0.0, 1.0), 90.0)
	_spawn("cyclo", Vector3(-9.5, 0.0, 0.9), 75.0)
	_spawn("cargo_trike", Vector3(-3.5, 0.0, -1.6), -95.0)


func _slab(pos: Vector3, size: Vector3, tex_set: String, tiles_per_m: float) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	var mat := ORMMaterial3D.new()
	var base := Env.GROUND_DIR + tex_set
	if ResourceLoader.exists(base + "albedo.jpg"):
		mat.albedo_texture = load(base + "albedo.jpg")
		if ResourceLoader.exists(base + "normal.png"):
			mat.normal_enabled = true
			mat.normal_texture = load(base + "normal.png")
		if ResourceLoader.exists(base + "orm.jpg"):
			mat.orm_texture = load(base + "orm.jpg")
		mat.uv1_triplanar = true
		mat.uv1_scale = Vector3.ONE * tiles_per_m
	else:
		mat.albedo_color = Color(0.5, 0.5, 0.48)
	mi.material_override = mat
	mi.position = pos
	add_child(mi)
	_collider(pos, size)


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
	_collider(pos, size)


func _collider(pos: Vector3, size: Vector3) -> void:
	var sb := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = size
	cs.shape = bs
	sb.add_child(cs)
	sb.position = pos
	add_child(sb)
