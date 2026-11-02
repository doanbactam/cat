extends Node3D
## In-engine preview of cat.glb (cat-asset QA). Plays `anim` on the instanced cat with FurShells.
## Optional: `variant` swaps the body albedo for an NPC coat (black/white/calico/grey_tabby).

@export var anim: StringName = &"walk"
@export var variant: String = ""
@export var seek_time: float = -1.0
@export var use_fur: bool = true

var _fur: FurShells = null


func _ready() -> void:
	var cat := get_node_or_null("Cat") as Node3D
	if cat == null:
		return
	var players := cat.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		var ap := players[0] as AnimationPlayer
		if ap.has_animation(anim):
			ap.play(anim)
			if seek_time >= 0.0:
				ap.seek(seek_time, true)
	if use_fur:
		_fur = FurShells.new()
		_fur.name = "Fur"
		_fur.shell_count = 32
		_fur.use_game_state_wetness = false
		if variant != "":
			_fur.albedo_override = load("res://assets/models/cat/textures/cat_albedo_%s.png" % variant) as Texture2D
		add_child(_fur)
		_fur.attach_to_model(cat, cat)
	elif variant != "":
		var body := cat.find_child("CatBody", true, false) as MeshInstance3D
		var tex := load("res://assets/models/cat/textures/cat_albedo_%s.png" % variant) as Texture2D
		if body != null and tex != null:
			var mat := body.get_active_material(0).duplicate() as StandardMaterial3D
			mat.albedo_texture = tex
			body.set_surface_override_material(0, mat)


func _play_at(a: StringName, t: float) -> void:
	var cat := get_node_or_null("Cat")
	if cat == null:
		return
	var players := cat.find_children("*", "AnimationPlayer", true, false)
	if players.size() == 0:
		return
	var ap := players[0] as AnimationPlayer
	if ap.has_animation(a):
		ap.play(a)
		ap.seek(t, true)
		ap.pause()


## Helpers for tools/screenshot.sh call=<name>
func pose_idle() -> void:
	_play_at(&"idle", 0.0)


func pose_sit() -> void:
	_play_at(&"sit_idle", 0.5)


func pose_face() -> void:
	_play_at(&"sit_idle", 0.5)
	var cam := get_node_or_null("Camera3D") as Camera3D
	if cam != null:
		cam.look_at_from_position(Vector3(0.14, 0.34, 0.45), Vector3(0.0, 0.28, 0.18), Vector3.UP)
		cam.fov = 32.0


func pose_walk() -> void:
	_play_at(&"walk", 0.22)


func pose_sleep() -> void:
	_play_at(&"sleep", 0.0)


func pose_run() -> void:
	_play_at(&"run", 0.1)


func pose_meow() -> void:
	_play_at(&"meow", 0.4)


func _coat(v: String) -> void:
	variant = v
	var cat := get_node_or_null("Cat") as Node3D
	var tex := load("res://assets/models/cat/textures/cat_albedo_%s.png" % v) as Texture2D
	if _fur != null and tex != null and cat != null:
		_fur.albedo_override = tex
		_fur.attach_to_model(cat, cat)
		return
	var body := cat.find_child("CatBody", true, false) as MeshInstance3D if cat else null
	if body != null and tex != null:
		var mat := body.get_active_material(0).duplicate() as StandardMaterial3D
		mat.albedo_texture = tex
		body.set_surface_override_material(0, mat)


func coat_black() -> void:
	_coat("black")
	_play_at(&"sit_idle", 0.5)


func coat_white() -> void:
	_coat("white")
	_play_at(&"sit_idle", 0.5)


func coat_calico() -> void:
	_coat("calico")
	_play_at(&"sit_idle", 0.5)


func coat_grey_tabby() -> void:
	_coat("grey_tabby")
	_play_at(&"sit_idle", 0.5)
