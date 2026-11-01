extends Node3D
## In-engine preview of cat.glb (cat-asset QA). Plays `anim` on the instanced cat.
## Optional: `variant` swaps the body albedo for an NPC coat (black/white/calico/grey_tabby).

@export var anim: StringName = &"walk"
@export var variant: String = ""
@export var seek_time: float = -1.0


func _ready() -> void:
	var cat := get_node_or_null("Cat")
	if cat == null:
		return
	var players := cat.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		var ap := players[0] as AnimationPlayer
		if ap.has_animation(anim):
			ap.play(anim)
			if seek_time >= 0.0:
				ap.seek(seek_time, true)
	if variant != "":
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


func pose_sleep() -> void:
	_play_at(&"sleep", 0.0)


func pose_run() -> void:
	_play_at(&"run", 0.1)


func pose_meow() -> void:
	_play_at(&"meow", 0.4)
