extends CanvasLayer
## In-game UI root (res://scenes/ui/hud.tscn) — instance it once in the game scene.
## Layer 10: HUD widgets (compass, quest tracker, toasts, vitals/XP/mouth item, prompt, banners,
## celebrations, subtitles, save indicator). Layer 15: dialogue box. Layer 20: menu host with the
## pause menu, belongings, skills, journal, map, settings, save/load (opening any pauses the tree).
## Input (unhandled): pause, inventory, journal, map, quick_save, quick_load.
## Fades the HUD while a dialogue runs; GameEvents.hud_visibility_requested(false) hides it.

const SCREENS := {
	&"pause": "res://scenes/ui/pause_menu.tscn",
	&"inventory": "res://scenes/ui/inventory_screen.tscn",
	&"skills": "res://scenes/ui/skill_tree_screen.tscn",
	&"journal": "res://scenes/ui/journal_screen.tscn",
	&"map": "res://scenes/ui/map_screen.tscn",
	&"settings": "res://scenes/ui/settings_menu.tscn",
	&"save_slots": "res://scenes/ui/save_slots.tscn",
}

@export var pause_tree_in_menus := true

var root: Control
var status: HudStatus
var compass: HudCompass
var tracker: HudQuestTracker
var toasts: HudToasts
var banner: HudBanner
var celebration: HudCelebration
var prompt: HudPrompt
var subtitles: HudSubtitles
var dialogue: DialogueBox
var host: UIMenuHost
var _save_ind: HBoxContainer
var _save_icon: TextureRect
var _menu_layer: CanvasLayer
var _dialogue_layer: CanvasLayer
var _hud_alpha := 1.0
var _hidden_requests := false
var _paused_by_menu := false


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group(&"hud")
	root = Control.new()
	root.name = "Root"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UIStyle.theme()
	root.process_mode = Node.PROCESS_MODE_PAUSABLE
	add_child(root)
	_build_widgets()
	_dialogue_layer = CanvasLayer.new()
	_dialogue_layer.name = "DialogueLayer"
	_dialogue_layer.layer = 15
	add_child(_dialogue_layer)
	dialogue = DialogueBox.new()
	dialogue.name = "DialogueBox"
	_dialogue_layer.add_child(dialogue)
	_menu_layer = CanvasLayer.new()
	_menu_layer.name = "MenuLayer"
	_menu_layer.layer = 20
	_menu_layer.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(_menu_layer)
	host = UIMenuHost.new()
	host.name = "MenuHost"
	host.theme = UIStyle.theme()
	_menu_layer.add_child(host)
	host.stack_changed.connect(_on_stack_changed)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"game_saved", _on_game_saved)
		ge.connect(&"settings_changed", _on_settings_changed)
		ge.connect(&"hud_visibility_requested", func(v: bool) -> void: _hidden_requests = not v)
	_apply_settings()


func _build_widgets() -> void:
	compass = HudCompass.new()
	compass.name = "Compass"
	compass.anchor_left = 0.5
	compass.anchor_right = 0.5
	compass.offset_left = -360
	compass.offset_right = 360
	compass.offset_top = 22
	compass.offset_bottom = 92
	root.add_child(compass)

	tracker = HudQuestTracker.new()
	tracker.name = "QuestTracker"
	tracker.anchor_left = 1.0
	tracker.anchor_right = 1.0
	tracker.offset_left = -560
	tracker.offset_right = -60
	tracker.offset_top = 46
	tracker.offset_bottom = 300
	root.add_child(tracker)

	toasts = HudToasts.new()
	toasts.name = "Toasts"
	toasts.offset_left = 56
	toasts.offset_top = 52
	toasts.offset_right = 700
	toasts.offset_bottom = 420
	root.add_child(toasts)

	banner = HudBanner.new()
	banner.name = "Banner"
	banner.anchor_left = 0.5
	banner.anchor_right = 0.5
	banner.offset_left = -600
	banner.offset_right = 600
	banner.offset_top = 150
	banner.offset_bottom = 330
	root.add_child(banner)

	celebration = HudCelebration.new()
	celebration.name = "Celebration"
	root.add_child(celebration)

	status = HudStatus.new()
	status.name = "Status"
	status.anchor_top = 1.0
	status.anchor_bottom = 1.0
	status.offset_left = 56
	status.offset_right = 700
	status.offset_top = -330
	status.offset_bottom = -44
	root.add_child(status)

	prompt = HudPrompt.new()
	prompt.name = "Prompt"
	prompt.anchor_left = 0.5
	prompt.anchor_right = 0.5
	prompt.anchor_top = 1.0
	prompt.anchor_bottom = 1.0
	prompt.grow_horizontal = Control.GROW_DIRECTION_BOTH
	prompt.offset_top = -300
	prompt.offset_bottom = -244
	root.add_child(prompt)

	subtitles = HudSubtitles.new()
	subtitles.name = "Subtitles"
	subtitles.anchor_left = 0.5
	subtitles.anchor_right = 0.5
	subtitles.anchor_top = 1.0
	subtitles.anchor_bottom = 1.0
	subtitles.offset_left = -560
	subtitles.offset_right = 560
	subtitles.offset_top = -230
	subtitles.offset_bottom = -110
	root.add_child(subtitles)

	_save_ind = HBoxContainer.new()
	_save_ind.name = "SaveIndicator"
	_save_ind.anchor_left = 1.0
	_save_ind.anchor_right = 1.0
	_save_ind.anchor_top = 1.0
	_save_ind.anchor_bottom = 1.0
	_save_ind.offset_left = -300
	_save_ind.offset_right = -56
	_save_ind.offset_top = -92
	_save_ind.offset_bottom = -52
	_save_ind.alignment = BoxContainer.ALIGNMENT_END
	_save_ind.add_theme_constant_override(&"separation", 10)
	_save_ind.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_save_icon = UIStyle.icon_rect(UIStyle.glyph(&"paw"), 28, UIStyle.GOLD_LIGHT)
	_save_icon.pivot_offset = Vector2(14, 14)
	_save_ind.add_child(_save_icon)
	var sl := UIStyle.label(tr("HUD_SAVED"), &"medium", 19, UIStyle.TEXT_DIM)
	HudQuestTracker._shadow(sl)
	_save_ind.add_child(sl)
	_save_ind.modulate.a = 0.0
	root.add_child(_save_ind)


func _apply_settings() -> void:
	compass.visible = bool(UIStyle.settings_value("gameplay", "compass", true))
	_hud_alpha = float(UIStyle.settings_value("gameplay", "hud_opacity", 1.0))


func _on_settings_changed(section: StringName) -> void:
	if section == &"gameplay":
		_apply_settings()


func _process(delta: float) -> void:
	var dlg := dialogue != null and dialogue.active
	var want := 0.0 if (dlg or _hidden_requests or host.depth() > 0) else _hud_alpha
	root.modulate.a = move_toward(root.modulate.a, want, delta * 3.0)
	if _save_ind.modulate.a > 0.0:
		_save_icon.rotation += delta * 3.0


func _on_game_saved(_slot: int) -> void:
	var tw := create_tween()
	tw.tween_property(_save_ind, "modulate:a", 1.0, 0.2)
	tw.tween_interval(1.6)
	tw.tween_property(_save_ind, "modulate:a", 0.0, 0.6)


# =============================================================================================
# Menus
# =============================================================================================

func open_screen(id: StringName) -> UIScreen:
	if not SCREENS.has(id):
		return null
	if host.depth() > 0 and host.top() != null and host.top().menu_id == id:
		return host.top()
	return host.push_screen(SCREENS[id])


func close_all_menus() -> void:
	host.clear()


func is_menu_open() -> bool:
	return host.depth() > 0


func _on_stack_changed(depth: int) -> void:
	var ge := get_node_or_null(^"/root/GameEvents")
	if depth > 0 and not _paused_by_menu:
		_paused_by_menu = true
		if pause_tree_in_menus:
			get_tree().paused = true
		if ge != null:
			ge.emit_signal(&"pause_requested", true)
		UIStyle.sfx(&"ui_pause")
	elif depth == 0 and _paused_by_menu:
		_paused_by_menu = false
		if pause_tree_in_menus:
			get_tree().paused = false
		if ge != null:
			ge.emit_signal(&"pause_requested", false)
		UIStyle.sfx(&"ui_unpause")


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_pressed() or event.is_echo():
		return
	var loader := get_node_or_null(^"/root/SceneLoader")
	if loader != null and bool(loader.call("is_loading")):
		return
	var in_dialogue := dialogue != null and dialogue.active
	if event.is_action_pressed(&"pause"):
		get_viewport().set_input_as_handled()
		if host.depth() > 0:
			close_all_menus()
		elif not in_dialogue:
			open_screen(&"pause")
		return
	if host.depth() > 0 or in_dialogue:
		# Toggle the open screen with its own key (Tab closes the inventory, M the map, ...).
		for pair: Array in [[&"inventory", &"inventory"], [&"journal", &"journal"], [&"map", &"map"]]:
			if event.is_action_pressed(pair[0]) and host.top() != null and host.top().menu_id == pair[1]:
				get_viewport().set_input_as_handled()
				host.pop_screen()
				return
		return
	for pair: Array in [[&"inventory", &"inventory"], [&"journal", &"journal"], [&"map", &"map"]]:
		if event.is_action_pressed(pair[0]):
			get_viewport().set_input_as_handled()
			open_screen(pair[1])
			return
	if event.is_action_pressed(&"quick_save"):
		get_viewport().set_input_as_handled()
		var gs := get_node_or_null(^"/root/GameState")
		if gs != null and bool(gs.call("save_game", 1)):
			toasts.push_toast(tr("QUICK_SAVED"), &"save")
	elif event.is_action_pressed(&"quick_load"):
		get_viewport().set_input_as_handled()
		var gs2 := get_node_or_null(^"/root/GameState")
		if gs2 != null and bool(gs2.call("has_save", 1)) and loader != null:
			loader.call("continue_game", 1)
		else:
			toasts.push_toast(tr("QUICK_LOAD_NONE"), &"info")
