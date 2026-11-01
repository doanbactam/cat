extends Node3D
## Systems sandbox: one of every interactable type on a small test set, for visual QA of the
## systems layer and as a drop-in test bed for the player area (instance the cat at PlayerSpawn).
## Loads data/i18n/requests/systems.csv as a runtime translation so prompts show real text.
## Screenshot: tools/screenshot.sh scene=res://tests/fixtures/systems_sandbox.tscn out=/abs.png
##             call=demo_knock frames=90   (knocks the cups off the table first)

const CSV := "res://data/i18n/requests/systems.csv"

var _labels: Array[Array] = []   # [Label3D, Interactable]
var cups: Array[Pushable] = []
var locale := "vi"


func _ready() -> void:
	_load_translation()
	TranslationServer.set_locale(locale)
	_build_environment()
	_build_set()
	_build_interactables()
	var spawn := Marker3D.new()
	spawn.name = "PlayerSpawn"
	spawn.add_to_group(&"player_spawn")
	add_child(spawn)
	spawn.position = Vector3(0, 0, 1.2)


func _process(_delta: float) -> void:
	for pair in _labels:
		var l: Label3D = pair[0]
		var it: Interactable = pair[1]
		if is_instance_valid(it) and is_instance_valid(l):
			l.text = it.get_prompt(null)
			l.modulate = Color(1, 1, 1, 1) if it.get_lock_reason(null) == "" else Color(1, 0.75, 0.6, 1)


## Swipe every cup off the table (used by the screenshot tool via call=demo_knock).
func demo_knock() -> void:
	# Only the blue cup goes over the edge; the white one stays for the before/after.
	cups[1].knock(Vector3.RIGHT, 1.3)


func _load_translation() -> void:
	if not FileAccess.file_exists(CSV):
		return
	var f := FileAccess.open(CSV, FileAccess.READ)
	var header := f.get_csv_line()
	var trs: Array[Translation] = []
	for i in range(1, header.size()):
		var t := Translation.new()
		t.locale = header[i]
		trs.append(t)
	while not f.eof_reached():
		var row := f.get_csv_line()
		if row.size() < header.size() or row[0] == "":
			continue
		for i in trs.size():
			trs[i].add_message(row[0], row[i + 1])
	for t in trs:
		TranslationServer.add_translation(t)


# --- set dressing --------------------------------------------------------------------------------

func _mat(albedo: Color, rough: float, metal: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = albedo
	m.roughness = rough
	m.metallic = metal
	return m


func _box(size: Vector3, pos: Vector3, mat: Material, collide: bool = true) -> Node3D:
	var root: Node3D = StaticBody3D.new() if collide else Node3D.new()
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	root.add_child(mi)
	if collide:
		var cs := CollisionShape3D.new()
		var sh := BoxShape3D.new()
		sh.size = size
		cs.shape = sh
		root.add_child(cs)
	add_child(root)
	root.position = pos
	return root


func _build_environment() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ProceduralSkyMaterial.new()
	sm.sky_top_color = Color(0.38, 0.52, 0.72)
	sm.sky_horizon_color = Color(0.85, 0.78, 0.66)
	sm.ground_horizon_color = Color(0.6, 0.55, 0.48)
	sky.sky_material = sm
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_energy = 2.2
	sun.light_color = Color(1.0, 0.9, 0.78)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 12.0
	add_child(sun)
	sun.rotation_degrees = Vector3(-38, -35, 0)
	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.fov = 60.0
	add_child(cam)
	cam.position = Vector3(0.05, 0.95, 1.95)
	cam.look_at(Vector3(0.05, 0.36, -0.25))
	cam.make_current()


func _build_set() -> void:
	# Worn concrete floor, a wooden table (the "ledge") and a tin awning (shelter volume).
	_box(Vector3(40, 0.2, 40), Vector3(0, -0.1, 0), _mat(Color(0.47, 0.45, 0.42), 0.92))
	_box(Vector3(0.9, 0.04, 0.55), Vector3(0.75, 0.72, -0.35), _mat(Color(0.42, 0.27, 0.16), 0.6))
	for x in [0.35, 1.15]:
		for z in [-0.58, -0.12]:
			_box(Vector3(0.04, 0.7, 0.04), Vector3(x, 0.35, z), _mat(Color(0.36, 0.23, 0.14), 0.65))
	var awning := _box(Vector3(2.4, 0.03, 1.2), Vector3(-0.9, 1.9, -0.9), _mat(Color(0.25, 0.45, 0.42), 0.5, 0.6), false)
	awning.rotation_degrees.x = 8.0
	var shelter := Area3D.new()
	shelter.name = "AwningShelter"
	shelter.add_to_group(&"shelter")
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = Vector3(2.4, 1.9, 1.2)
	cs.shape = sh
	shelter.add_child(cs)
	add_child(shelter)
	shelter.position = Vector3(-0.9, 0.95, -0.9)
	var loc := Marker3D.new()
	loc.name = "TeaStall"
	loc.add_to_group(&"location")
	loc.set_meta(&"location_id", "tea_stall")
	loc.set_meta(&"display_name_key", "LOC_TEA_STALL")
	add_child(loc)


func _label(it: Interactable, height: float) -> void:
	var l := Label3D.new()
	l.pixel_size = 0.0009
	l.font_size = 40
	l.outline_size = 14
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	it.add_child(l)
	l.position = Vector3(0, height, 0)
	_labels.append([l, it])


func _build_interactables() -> void:
	# Ceramic cups on the table edge → Pushable
	for i in 2:
		var cup := Pushable.new()
		cup.name = "Cup%d" % i
		cup.object_id = StringName("sandbox_cup_%d" % i)
		cup.mass = 0.22
		var mi := MeshInstance3D.new()
		var cy := CylinderMesh.new()
		cy.top_radius = 0.042
		cy.bottom_radius = 0.034
		cy.height = 0.085
		mi.mesh = cy
		mi.position.y = 0.0425
		mi.material_override = _mat(Color(0.86, 0.84, 0.78) if i == 0 else Color(0.32, 0.5, 0.62), 0.25)
		cup.add_child(mi)
		var cs := CollisionShape3D.new()
		var sh := CylinderShape3D.new()
		sh.radius = 0.04
		sh.height = 0.085
		cs.shape = sh
		cs.position.y = 0.0425
		cup.add_child(cs)
		add_child(cup)
		cup.position = Vector3(1.08, 0.74, -0.25 - 0.18 * i)
		cups.append(cup)
	_label(cups[0].get_node("KnockArea") as Interactable, 0.2)
	# Items on the floor
	var items := [[&"fish", Vector3(-0.15, 0, 0.35)], [&"cap", Vector3(0.25, 0, 0.55)],
		[&"lucky_cat_figurine", Vector3(0.55, 0, 0.2)]]
	for spec in items:
		var p := PickupItem.new()
		p.item_id = spec[0]
		p.name = "Pickup_" + String(spec[0])
		add_child(p)
		p.position = spec[1]
		_label(p, 0.2)
	var mem := Collectible.new()
	mem.collectible_id = &"memory_07"
	add_child(mem)
	mem.position = Vector3(-0.45, 0, 0.6)
	mem.rotation_degrees.y = 25.0
	_label(mem, 0.14)
	# Nap cushion under the awning
	var nap := NapSpot.new()
	nap.name = "StallCushion"
	nap.sleep_hours = 2.0
	var cushion := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.24
	cm.bottom_radius = 0.26
	cm.height = 0.07
	cushion.mesh = cm
	cushion.position.y = 0.035
	cushion.material_override = _mat(Color(0.62, 0.18, 0.16), 0.9)
	nap.add_child(cushion)
	add_child(nap)
	nap.position = Vector3(-1.3, 0, -0.7)
	_label(nap, 0.35)
	# Grandma's food bowl
	var bowl := FoodSource.new()
	bowl.name = "GrandmaBowl"
	bowl.display_name_key = "ITEM_FISH"
	var bmi := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.075
	bm.bottom_radius = 0.05
	bm.height = 0.045
	bmi.mesh = bm
	bmi.position.y = 0.0225
	bmi.material_override = _mat(Color(0.9, 0.9, 0.86), 0.2)
	bowl.add_child(bmi)
	add_child(bowl)
	bowl.position = Vector3(-0.75, 0, 0.05)
	_label(bowl, 0.22)
	# Scratch post and a territory spot
	var post := ScratchPost.new()
	post.name = "RattanPost"
	post.display_name_key = "PROP_OBJECT"
	var pmi := MeshInstance3D.new()
	var pm := CylinderMesh.new()
	pm.top_radius = 0.05
	pm.bottom_radius = 0.055
	pm.height = 0.6
	pmi.mesh = pm
	pmi.position.y = 0.3
	pmi.material_override = _mat(Color(0.66, 0.52, 0.32), 0.95)
	post.add_child(pmi)
	add_child(post)
	post.position = Vector3(-1.75, 0, 0.1)
	_label(post, 0.72)
	var spot := TerritorySpot.new()
	spot.spot_id = &"sandbox_corner"
	add_child(spot)
	spot.position = Vector3(1.6, 0, 0.35)
	_label(spot, 0.2)
