extends "res://tests/test_base.gd"
## UI area: every UI scene instantiates and builds focusable content, the boot scene builds
## its menu, the menu host stack works (back closes, focus restore), confirm dialogs emit, the
## loading screen accepts progress and SceneLoader performs a threaded scene change.

const SCREENS := [
	"res://scenes/ui/pause_menu.tscn", "res://scenes/ui/inventory_screen.tscn",
	"res://scenes/ui/skill_tree_screen.tscn", "res://scenes/ui/journal_screen.tscn",
	"res://scenes/ui/map_screen.tscn", "res://scenes/ui/settings_menu.tscn",
	"res://scenes/ui/save_slots.tscn", "res://scenes/ui/credits.tscn",
]
const PROBE := "res://scenes/ui/qa/loader_probe.tscn"


func _frames(n: int) -> void:
	for i in n:
		await tree.process_frame


## Real-time wait (headless frames run unthrottled, tweens are time based).
func _wait(sec: float) -> void:
	await tree.create_timer(sec, true).timeout


func test_every_screen_instantiates_with_focus() -> void:
	tree.root.get_node("GameState").call("new_game")
	var host := UIMenuHost.new()
	host.theme = UIStyle.theme()
	tree.root.add_child(host)
	for path: String in SCREENS:
		assert_true(ResourceLoader.exists(path), path)
		var s := host.push_screen(path)
		assert_not_null(s, "push " + path)
		if s == null:
			continue
		await _frames(3)
		assert_true(s.get_child_count() > 1, "%s built children" % path)
		var f := s.default_focus()
		assert_not_null(f, "%s has a focusable control" % path)
		if f != null:
			assert_true(f.focus_mode != Control.FOCUS_NONE, "%s focus mode" % path)
		host.pop_screen(s)
		await _wait(0.4)
		assert_eq(host.depth(), 0, "%s closed" % path)
	host.free()


func test_settings_tabs_cycle() -> void:
	var host := UIMenuHost.new()
	tree.root.add_child(host)
	var s := host.push_screen("res://scenes/ui/settings_menu.tscn")
	await _frames(2)
	var moved := 0
	for i in 4:
		if s.on_tab_input(1):
			moved += 1
		await _frames(1)
	assert_true(moved >= 3, "settings has ≥4 tabs (moved %d)" % moved)
	host.free()


func test_menu_host_stack_and_back() -> void:
	var host := UIMenuHost.new()
	tree.root.add_child(host)
	var a := host.push_screen("res://scenes/ui/pause_menu.tscn")
	await _frames(2)
	var d := UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_BODY", true)
	var got := [false]
	d.confirmed.connect(func() -> void: got[0] = true)
	host.push_screen(d)
	await _frames(2)
	assert_eq(host.depth(), 2)
	assert_false(a.visible, "lower screen hidden")
	# ui_cancel closes the top screen only
	var ev := InputEventAction.new()
	ev.action = &"ui_cancel"
	ev.pressed = true
	host._unhandled_input(ev)
	await _wait(0.4)
	assert_eq(host.depth(), 1)
	assert_true(a.visible, "lower screen visible again")
	assert_false(got[0], "cancel does not confirm")
	var d2 := UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_BODY")
	var got2 := [false]
	d2.confirmed.connect(func() -> void: got2[0] = true)
	host.push_screen(d2)
	await _frames(2)
	var btn := d2.default_focus() as Button
	assert_not_null(btn, "safe default focus (No)")
	for b: Button in d2.find_children("*", "Button", true, false):
		if b != btn:
			b.pressed.emit()  # the "Yes" button
			break
	await _wait(0.4)
	assert_true(got2[0], "confirm button emits confirmed")
	host.free()


func test_boot_scene_builds_menu() -> void:
	var loader := tree.root.get_node("SceneLoader")
	loader.set("skip_splash_once", true)
	var m := (load("res://scenes/main/main.tscn") as PackedScene).instantiate()
	m.set("show_splash", false)
	tree.root.add_child(m)
	await _frames(4)
	var menu: Control = m.get("menu")
	assert_not_null(menu, "main menu instanced")
	if menu != null:
		assert_true(menu.visible)
		var buttons := menu.find_children("*", "Button", true, false)
		assert_true(buttons.size() >= 4, "menu buttons: %d" % buttons.size())
		var texts := []
		for b: Button in buttons:
			texts.append(b.text)
		assert_true(texts.has(tr("MENU_SETTINGS")) or texts.has(TranslationServer.translate("MENU_SETTINGS")), "settings entry: %s" % str(texts))
	m.free()


func test_loading_screen_progress() -> void:
	var ls := (load("res://scenes/ui/loading_screen.tscn") as PackedScene).instantiate() as Control
	tree.root.add_child(ls)
	await _frames(2)
	ls.call("set_progress", 0.5)
	await _frames(2)
	assert_true(ls.has_method("set_progress"))
	ls.free()


func test_scene_loader_threaded_change() -> void:
	var loader := tree.root.get_node("SceneLoader")
	var old_fade: float = loader.get("fade_time")
	var old_min: float = loader.get("min_loading_time")
	loader.set("fade_time", 0.05)
	loader.set("min_loading_time", 0.1)
	var prog: Array[float] = []
	var pcb := func(p: float) -> void: prog.append(p)
	loader.connect(&"load_progress", pcb)
	var prev_scene := tree.current_scene
	loader.call("change_scene", PROBE, true)
	assert_true(bool(loader.call("is_loading")), "loading flag set")
	var t := 0
	while bool(loader.call("is_loading")) and t < 600:
		await tree.process_frame
		t += 1
	assert_false(bool(loader.call("is_loading")), "finished within 600 frames")
	var cur := tree.current_scene
	assert_not_null(cur)
	if cur != null:
		assert_eq(cur.name, &"LoaderProbe")
	assert_true(prog.size() >= 1 and is_equal_approx(prog[-1], 1.0), "progress reached 1.0 (%s)" % str(prog))
	loader.disconnect(&"load_progress", pcb)
	# bad path fails gracefully
	var failed := [false]
	var fcb := func(_p: String) -> void: failed[0] = true
	loader.connect(&"load_failed", fcb)
	loader.call("change_scene", "res://does/not/exist.tscn", true)
	assert_true(failed[0], "load_failed emitted")
	assert_false(bool(loader.call("is_loading")))
	loader.disconnect(&"load_failed", fcb)
	for i in 20:
		await tree.process_frame
	if cur != null and is_instance_valid(cur):
		cur.queue_free()
	tree.current_scene = prev_scene if is_instance_valid(prev_scene) else null
	loader.set("fade_time", old_fade)
	loader.set("min_loading_time", old_min)
	await tree.process_frame
