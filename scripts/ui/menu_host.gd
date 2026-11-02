class_name UIMenuHost
extends Control
## Stack of UIScreens (used by the main menu and the in-game HUD). Handles back/cancel,
## LB/RB tab switching, focus restore, GameEvents.ui_menu_opened/closed and the open/close
## sounds. Screens are full-rect children; only the top one receives input.

signal stack_changed(depth: int)

var _stack: Array[UIScreen] = []
var _focus_memory: Dictionary = {}  # screen instance id -> Control that had focus


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	process_mode = Node.PROCESS_MODE_ALWAYS


func depth() -> int:
	return _stack.size()


func top() -> UIScreen:
	return _stack[-1] if not _stack.is_empty() else null


func has_screen(menu_id: StringName) -> bool:
	for s in _stack:
		if s.menu_id == menu_id:
			return true
	return false


## Instantiates (if given a path/PackedScene) and pushes a screen. Returns the screen.
func push_screen(screen_or_path: Variant) -> UIScreen:
	var screen: UIScreen = null
	if screen_or_path is UIScreen:
		screen = screen_or_path
	elif screen_or_path is PackedScene:
		screen = (screen_or_path as PackedScene).instantiate() as UIScreen
	elif screen_or_path is String:
		var ps := load(String(screen_or_path)) as PackedScene
		if ps != null:
			screen = ps.instantiate() as UIScreen
	if screen == null:
		push_warning("UIMenuHost: cannot open %s" % str(screen_or_path))
		return null
	var cur := top()
	if cur != null:
		var f := get_viewport().gui_get_focus_owner()
		if f != null and cur.is_ancestor_of(f):
			_focus_memory[cur.get_instance_id()] = f
		cur.visible = false
	screen.host = self
	add_child(screen)
	_stack.append(screen)
	screen.closed.connect(_on_screen_closed)
	screen.on_opened()
	if screen.menu_id != &"":
		_emit(&"ui_menu_opened", screen.menu_id)
	if screen.menu_id == &"map":
		UIStyle.sfx(&"ui_map_open")
	elif screen.menu_id != &"pause":
		UIStyle.sfx(&"ui_menu_open")
	stack_changed.emit(_stack.size())
	return screen


## Closes `screen` (default: top) with its animation.
func pop_screen(screen: UIScreen = null) -> void:
	if screen == null:
		screen = top()
	if screen == null or screen.is_closing:
		return
	if screen.menu_id == &"map":
		UIStyle.sfx(&"ui_map_close")
	elif screen.menu_id != &"pause":
		UIStyle.sfx(&"ui_back")
	screen.close_now()


## Closes every screen immediately (e.g. when the game resumes from the pause menu shortcut).
func clear() -> void:
	for s in _stack.duplicate():
		s.close_now()


func _on_screen_closed(screen: UIScreen) -> void:
	var i := _stack.find(screen)
	if i < 0:
		return
	_stack.remove_at(i)
	if screen.menu_id != &"":
		_emit(&"ui_menu_closed", screen.menu_id)
	var cur := top()
	if cur != null:
		cur.visible = true
		var f: Control = _focus_memory.get(cur.get_instance_id(), null)
		_focus_memory.erase(cur.get_instance_id())
		if f != null and is_instance_valid(f) and f.is_visible_in_tree():
			f.grab_focus.call_deferred()
		else:
			cur.focus_default.call_deferred()
		if cur.has_method("on_resumed"):
			cur.call("on_resumed")
	stack_changed.emit(_stack.size())


func _emit(sig: StringName, id: StringName) -> void:
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.emit_signal(sig, id)


func _unhandled_input(event: InputEvent) -> void:
	var cur := top()
	if cur == null or cur.is_closing or not event.is_pressed() or event.is_echo():
		return
	if event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		if not cur.handle_back():
			pop_screen(cur)
		return
	var tab := 0
	if event is InputEventJoypadButton:
		var jb := event as InputEventJoypadButton
		if jb.button_index == JOY_BUTTON_LEFT_SHOULDER:
			tab = -1
		elif jb.button_index == JOY_BUTTON_RIGHT_SHOULDER:
			tab = 1
	elif event is InputEventKey:
		var k := event as InputEventKey
		if k.physical_keycode == KEY_Q:
			tab = -1
		elif k.physical_keycode == KEY_E:
			tab = 1
	if tab != 0 and cur.on_tab_input(tab):
		UIStyle.sfx(&"ui_page")
		get_viewport().set_input_as_handled()
