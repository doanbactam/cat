extends Node
## SceneLoader autoload (owner: ui). Threaded scene changes with fades and a loading screen.
##
## Contract: change_scene(path, show_loading := true), reload_current().
## Extras: go_to_main_menu(skip_splash := true), start_new_game(), continue_game(slot),
##         get_game_scene_path(), is_loading(), get_progress(), fade_out(t)/fade_in(t) (awaitable).
## Flow: fade to black → loading screen (tips + cat walking a lantern wire, progress = lanterns
## lighting up) → ResourceLoader.load_threaded_request → swap current scene → settle frames →
## fade in. The tree is unpaused before the swap (pause menus may have paused it).

signal load_started(path: String)
signal load_progress(progress: float)
signal load_finished(path: String)
signal load_failed(path: String)
signal scene_changed(scene: Node)
## Internal: emitted when the current fade completes or is interrupted by a newer fade.
signal _fade_done

const LOADING_SCREEN := "res://scenes/ui/loading_screen.tscn"
const MAIN_MENU_SCENE := "res://scenes/main/main.tscn"
## Game scene (built by the lead in phase 2), then fallbacks while it does not exist yet.
const GAME_SCENES: PackedStringArray = ["res://scenes/main/game.tscn", "res://scenes/world/city.tscn"]

## Seconds of each fade.
var fade_time := 0.45
## Minimum time the loading screen stays up (so tips can be read and the cat can walk).
var min_loading_time := 1.6
## Frames to wait after instancing the new scene before fading in (shader compilation, SDFGI).
var settle_frames := 4
## Set by go_to_main_menu(): the boot scene skips the splash once.
var skip_splash_once := false

var _loading := false
var _path := ""
var _progress := 0.0
var _layer: CanvasLayer = null
var _fade: ColorRect = null
var _screen: Control = null
var _fade_tween: Tween = null


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_layer = CanvasLayer.new()
	_layer.name = "SceneLoaderLayer"
	_layer.layer = 120
	add_child(_layer)
	_fade = ColorRect.new()
	_fade.name = "Fade"
	_fade.color = Color(0.035, 0.025, 0.02, 1.0)
	_fade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_fade.modulate.a = 0.0
	_layer.add_child(_fade)


# =============================================================================================
# Contract API
# =============================================================================================

## Loads `path` on a worker thread and replaces the current scene. Returns immediately; await
## the `scene_changed` signal if you need the new scene.
func change_scene(path: String, show_loading: bool = true) -> void:
	if _loading:
		push_warning("SceneLoader: already loading %s, ignored %s" % [_path, path])
		return
	if not ResourceLoader.exists(path):
		push_error("SceneLoader: scene not found " + path)
		load_failed.emit(path)
		return
	_run_change(path, show_loading)


func reload_current() -> void:
	var cur := get_tree().current_scene
	if cur == null or cur.scene_file_path == "":
		push_warning("SceneLoader.reload_current: current scene has no file")
		return
	change_scene(cur.scene_file_path, true)


# =============================================================================================
# Extras
# =============================================================================================

func is_loading() -> bool:
	return _loading


func get_progress() -> float:
	return _progress


func get_loading_path() -> String:
	return _path


## First existing game scene ("" if none yet).
func get_game_scene_path() -> String:
	for p in GAME_SCENES:
		if ResourceLoader.exists(p):
			return p
	return ""


func go_to_main_menu(skip_splash: bool = true) -> void:
	skip_splash_once = skip_splash
	change_scene(MAIN_MENU_SCENE, false)


## GameState.new_game() + load the game scene. Returns false when no game scene exists.
func start_new_game() -> bool:
	var p := get_game_scene_path()
	if p == "":
		return false
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and gs.has_method("new_game"):
		gs.call("new_game")
	change_scene(p, true)
	return true


## Loads a save slot then the game scene (GameState applies the player transform on spawn).
func continue_game(slot: int) -> bool:
	var p := get_game_scene_path()
	if p == "":
		return false
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null or not gs.has_method("load_game") or not bool(gs.call("load_game", slot)):
		return false
	change_scene(p, true)
	return true


func fade_out(t: float = -1.0) -> void:
	await _fade_to(1.0, fade_time if t < 0.0 else t)


func fade_in(t: float = -1.0) -> void:
	await _fade_to(0.0, fade_time if t < 0.0 else t)


func get_fade_alpha() -> float:
	return _fade.modulate.a


# =============================================================================================
# Internals
# =============================================================================================

func _run_change(path: String, show_loading: bool) -> void:
	_loading = true
	_path = path
	_progress = 0.0
	load_started.emit(path)
	_fade.mouse_filter = Control.MOUSE_FILTER_STOP
	await _fade_to(1.0, fade_time)
	get_tree().paused = false
	if show_loading:
		_show_screen()
	# use_sub_threads=false: with sub-threads the loader deadlocks on the big city scene (main thread
	# froze forever at ~13 % in Godot 4.8-beta2 while other code load()ed shared resources).
	var err := ResourceLoader.load_threaded_request(path, "PackedScene", false)
	var t0 := Time.get_ticks_msec()
	if show_loading:
		await _fade_to(0.0, 0.3)
	var ps: PackedScene = null
	if err != OK:
		push_warning("SceneLoader: threaded request failed (%s), loading synchronously" % error_string(err))
		ps = load(path) as PackedScene
		_set_progress(1.0)
	else:
		while true:
			var prog: Array = []
			var st := ResourceLoader.load_threaded_get_status(path, prog)
			if prog.size() > 0:
				_set_progress(float(prog[0]))
			if st == ResourceLoader.THREAD_LOAD_LOADED:
				ps = ResourceLoader.load_threaded_get(path) as PackedScene
				break
			if st == ResourceLoader.THREAD_LOAD_FAILED or st == ResourceLoader.THREAD_LOAD_INVALID_RESOURCE:
				break
			await get_tree().process_frame
	if ps == null:
		push_error("SceneLoader: failed to load " + path)
		_finish_failed(path)
		return
	_set_progress(1.0)
	if show_loading:
		# Let the progress animation finish and keep the screen up long enough to read a tip.
		while float(Time.get_ticks_msec() - t0) / 1000.0 < min_loading_time:
			await get_tree().process_frame
		await _fade_to(1.0, 0.3)
	var tree := get_tree()
	var old := tree.current_scene
	if old != null:
		old.queue_free()
		await tree.process_frame
	var inst := ps.instantiate()
	tree.root.add_child(inst)
	tree.current_scene = inst
	_hide_screen()
	for i in settle_frames:
		await tree.process_frame
	_loading = false
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	scene_changed.emit(inst)
	load_finished.emit(path)
	await _fade_to(0.0, fade_time)


func _finish_failed(path: String) -> void:
	_hide_screen()
	_loading = false
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	load_failed.emit(path)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.emit_signal(&"notify", tr("UI_LOAD_FAILED"), &"warning")
	await _fade_to(0.0, fade_time)


func _set_progress(p: float) -> void:
	_progress = clampf(p, 0.0, 1.0)
	load_progress.emit(_progress)
	if _screen != null and _screen.has_method("set_progress"):
		_screen.call("set_progress", _progress)


func _show_screen() -> void:
	_hide_screen()
	if not ResourceLoader.exists(LOADING_SCREEN):
		return
	var ps := load(LOADING_SCREEN) as PackedScene
	if ps == null:
		return
	_screen = ps.instantiate() as Control
	_layer.add_child(_screen)
	_layer.move_child(_screen, 0)
	if _screen.has_method("set_progress"):
		_screen.call("set_progress", 0.0)


func _hide_screen() -> void:
	if _screen != null and is_instance_valid(_screen):
		_screen.queue_free()
	_screen = null


func _fade_to(alpha: float, t: float) -> void:
	if _fade_tween != null and _fade_tween.is_valid():
		_fade_tween.kill()
		# A killed tween never emits `finished`; release whoever awaited the interrupted fade so
		# that coroutine (e.g. _run_change) cannot hang forever with _loading stuck at true.
		_fade_done.emit()
	if t <= 0.0 or not is_inside_tree():
		_fade.modulate.a = alpha
		return
	_fade_tween = create_tween()
	_fade_tween.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_fade_tween.tween_property(_fade, "modulate:a", alpha, t).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_fade_tween.finished.connect(_fade_done.emit)
	await _fade_done
