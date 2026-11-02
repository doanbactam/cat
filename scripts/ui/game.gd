extends Node3D
## Game scene root (res://scenes/main/game.tscn): city + life director + HUD; spawns Cam at PlayerSpawn.
## A loaded save's transform still wins: GameState applies it on the (deferred) player_spawned signal.

const PLAYER_SCENE := "res://scenes/player/cat_player.tscn"
const MAP_BOUNDS := Rect2(-124.0, -98.0, 248.0, 212.0)

var city: Node3D
var life_director: Node3D
var hud: CanvasLayer
var player: Node3D


func _ready() -> void:
	set_meta(&"map_bounds", MAP_BOUNDS)
	city = get_node_or_null(^"City") as Node3D
	life_director = get_node_or_null(^"LifeDirector") as Node3D
	hud = get_node_or_null(^"HUD") as CanvasLayer
	var qm := get_node_or_null(^"/root/QuestManager")
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and qm != null:
		var active: Array = qm.call(&"get_active_quests")
		var done: Array = qm.call(&"get_completed_quests")
		if active.is_empty() and done.is_empty() and gs.call(&"get_pending_player_transform") == null:
			gs.call(&"new_game")
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Node3D
	player.name = "CatPlayer"
	var spawn := get_tree().get_first_node_in_group(&"player_spawn") as Node3D
	if spawn != null:
		player.transform = spawn.global_transform
	add_child(player)
	if spawn != null:
		player.call(&"teleport", spawn.global_transform)


func open_map() -> void:
	if hud != null:
		hud.call(&"open_screen", &"map")


func open_journal() -> void:
	if hud != null:
		hud.call(&"open_screen", &"journal")


func open_inventory() -> void:
	if hud != null:
		hud.call(&"open_screen", &"inventory")


func open_pause() -> void:
	if hud != null:
		hud.call(&"open_screen", &"pause")


func qa_rain() -> void:
	if city != null and city.has_method(&"qa_rain"):
		city.call(&"qa_rain")


func qa_festival() -> void:
	if city != null and city.has_method(&"qa_festival"):
		city.call(&"qa_festival")
