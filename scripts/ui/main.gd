extends Node
## Boot scene (res://scenes/main/main.tscn): studio splash → main menu over the live 3D rooftop
## backdrop. SceneLoader.go_to_main_menu() returns here and skips the splash.

const BACKDROP := "res://scenes/ui/menu_backdrop.tscn"
const MAIN_MENU := "res://scenes/ui/main_menu.tscn"
const SPLASH := "res://scenes/ui/splash.tscn"

@export var show_splash := true

var backdrop: Node3D = null
var menu: Control = null
var splash: Control = null
var _ui: CanvasLayer


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_tree().paused = false
	if ResourceLoader.exists(BACKDROP):
		backdrop = (load(BACKDROP) as PackedScene).instantiate() as Node3D
		add_child(backdrop)
	_ui = CanvasLayer.new()
	_ui.name = "UI"
	_ui.layer = 5
	add_child(_ui)
	menu = (load(MAIN_MENU) as PackedScene).instantiate() as Control
	_ui.add_child(menu)
	var loader := get_node_or_null(^"/root/SceneLoader")
	var skip := loader != null and bool(loader.get("skip_splash_once"))
	if loader != null:
		loader.set("skip_splash_once", false)
	_play_music()
	if show_splash and not skip and ResourceLoader.exists(SPLASH):
		menu.visible = false
		splash = (load(SPLASH) as PackedScene).instantiate() as Control
		_ui.add_child(splash)
		await splash.tree_exited
		splash = null
	menu.visible = true
	if menu.has_method("reveal"):
		menu.call("reveal")


## Skips the splash immediately (screenshot tool: call=skip_intro).
func skip_intro() -> void:
	if splash != null and is_instance_valid(splash):
		splash.queue_free()
	if menu != null:
		menu.visible = true


func _play_music() -> void:
	var am := get_node_or_null(^"/root/AudioManager")
	if am != null and am.has_method("play_music"):
		am.call("play_music", &"mus_menu", 3.0)
	if am != null and am.has_method("set_ambience"):
		am.call("set_ambience", &"amb_rooftop", 3.0)
