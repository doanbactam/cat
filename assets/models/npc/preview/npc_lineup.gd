extends Node3D
## Creature preview line-up (owner: creatures). Instances every NPC GLB next to a cat-sized
## reference box (0.46 m long x 0.25 m shoulder height) and plays a clip on each.
## Screenshot hooks (tools/screenshot.sh call=...): show_idle, show_walk, show_special.

const HUMANS: Array[String] = ["ba_tu", "co_hoa", "chu_sau", "bin", "ped_office", "ped_student",
	"ped_elder_man", "ped_helmet_woman", "ped_shopper", "ped_xeom"]
const ANIMALS: Array[String] = ["dog", "pigeon", "crow", "sparrow", "mouse", "gecko", "koi"]
const SPECIAL := {
	"ba_tu": "sit", "co_hoa": "sell", "chu_sau": "talk", "bin": "pet_cat", "ped_office": "phone",
	"ped_student": "look_around", "ped_elder_man": "walk", "ped_helmet_woman": "carry", "ped_shopper": "shoo",
	"ped_xeom": "idle", "dog": "bark", "pigeon": "fly", "crow": "caw", "sparrow": "peck", "mouse": "run",
	"gecko": "run", "koi": "swim",
}

@export var human_spacing := 0.8
@export var animal_spacing := 0.75
@export var seek_time := 0.4

var _actors: Dictionary = {}


func _ready() -> void:
	var x0 := -human_spacing * (HUMANS.size() - 1) * 0.5
	for i in HUMANS.size():
		_spawn(HUMANS[i], Vector3(x0 + i * human_spacing, 0.0, 0.0))
	var a0 := -animal_spacing * (ANIMALS.size() - 1) * 0.5
	for i in ANIMALS.size():
		var pos := Vector3(a0 + i * animal_spacing, 0.0, 1.3)
		if ANIMALS[i] == "koi":
			pos.y = 0.05
		_spawn(ANIMALS[i], pos)
	show_idle()


func _spawn(id: String, pos: Vector3) -> void:
	var path := "res://assets/models/npc/%s.glb" % id
	if not ResourceLoader.exists(path):
		push_warning("lineup: missing " + path)
		return
	var ps := load(path) as PackedScene
	if ps == null:
		return
	var n := ps.instantiate() as Node3D
	n.name = id
	add_child(n)
	n.position = pos
	_actors[id] = n


func _player(n: Node) -> AnimationPlayer:
	var found := n.find_children("*", "AnimationPlayer", true, false)
	return found[0] as AnimationPlayer if found.size() > 0 else null


func _play(id: String, clip: String) -> void:
	var n: Node = _actors.get(id)
	if n == null:
		return
	var ap := _player(n)
	if ap == null:
		return
	if not ap.has_animation(clip):
		clip = "swim" if ap.has_animation("swim") else "idle"
	ap.play(clip)
	ap.seek(seek_time, true)


func show_idle() -> void:
	for id: String in _actors:
		_play(id, "idle")


func show_walk() -> void:
	for id: String in _actors:
		_play(id, "walk")


func show_special() -> void:
	for id: String in _actors:
		_play(id, SPECIAL.get(id, "idle"))
