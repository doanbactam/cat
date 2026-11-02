extends "res://tests/test_base.gd"
## UI area: HUD reacts to GameEvents (prompt, toasts, banner, celebrations, vitals, mouth item,
## subtitles, quest tracker), dialogue box follows DialogueManager, menus pause the tree.

const STORY_QUESTS := "res://tests/fixtures/story/quests"
const STORY_DIALOGUE := "res://tests/fixtures/story/dialogue"

var hud: CanvasLayer
var ge: Node


func before_each() -> void:
	ge = tree.root.get_node("GameEvents")
	tree.root.get_node("GameState").call("new_game")
	hud = (load("res://scenes/ui/hud.tscn") as PackedScene).instantiate() as CanvasLayer
	tree.root.add_child(hud)


func after_each() -> void:
	var dm := tree.root.get_node("DialogueManager")
	if bool(dm.call("is_active")):
		dm.call("stop")
	if is_instance_valid(hud):
		hud.free()
	tree.paused = false


func _frames(n: int) -> void:
	for i in n:
		await tree.process_frame


## Real-time wait (headless frames run unthrottled, tweens are time based).
func _wait(sec: float) -> void:
	await tree.create_timer(sec, true).timeout


func test_hud_builds_all_widgets() -> void:
	await _frames(2)
	for w in ["status", "compass", "tracker", "toasts", "banner", "celebration", "prompt", "subtitles", "dialogue", "host"]:
		assert_not_null(hud.get(w), "widget " + w)
	assert_true(hud.is_in_group(&"hud"))
	# Regression: full-rect controls created inside a CanvasLayer must really fill the screen
	# (set_anchors_preset() alone kept their zero size, hiding the dialogue box and menu cards).
	var vp := tree.root.get_visible_rect().size
	var dlg: Control = hud.get("dialogue")
	var host: Control = hud.get("host")
	assert_true(dlg.size.x >= vp.x - 1.0 and dlg.size.y >= vp.y - 1.0, "dialogue box size %s" % str(dlg.size))
	assert_true(host.size.x >= vp.x - 1.0, "menu host size %s" % str(host.size))
	var s: UIScreen = hud.call("open_screen", &"pause")
	await _frames(3)
	assert_true(s.size.x >= vp.x - 1.0 and s.size.y >= vp.y - 1.0, "pause screen size %s" % str(s.size))
	hud.call("close_all_menus")
	await _wait(0.4)


func test_prompt_follows_focus_events() -> void:
	await _frames(1)
	var target := Node3D.new()
	tree.root.add_child(target)
	ge.emit_signal(&"interactable_focused", target, "Ngửi bát cơm")
	await _frames(2)
	var p: Node = hud.get("prompt")
	assert_true(bool(p.call("is_showing")), "prompt visible")
	assert_eq(String(p.call("get_text")), "Ngửi bát cơm")
	ge.emit_signal(&"interactable_unfocused", target)
	await _frames(2)
	assert_false(bool(p.call("is_showing")), "prompt hidden")
	target.free()


func test_toasts_stack_and_cap() -> void:
	await _frames(1)
	var t: Control = hud.get("toasts")
	for i in 6:
		ge.emit_signal(&"notify", "Toast %d" % i, &"info")
	ge.emit_signal(&"notify", "item toast", &"shrimp")
	ge.emit_signal(&"notify", "level", &"level_up")   # suppressed: has its own celebration
	await _frames(2)
	assert_true(t.get_child_count() >= 1 and t.get_child_count() <= 4, "toast count %d" % t.get_child_count())


func test_location_banner_and_level_up() -> void:
	await _frames(1)
	ge.emit_signal(&"location_discovered", &"fish_street", "Dãy hàng cá")
	ge.emit_signal(&"level_up", 3)
	await _frames(3)
	assert_true(bool(hud.get("banner").call("is_busy")), "banner showing")
	assert_true(bool(hud.get("celebration").call("is_busy")), "celebration showing")


func test_vitals_react_to_stat_changes() -> void:
	await _frames(1)
	var gs := tree.root.get_node("GameState")
	var status: Node = hud.get("status")
	gs.call("modify_stat", &"hunger", -60.0)
	await _frames(3)
	assert_true(status.has_method("get_ring"), "status exposes get_ring")
	if status.has_method("get_ring"):
		var ring: Node = status.call("get_ring", &"hunger")
		assert_not_null(ring)
		if ring != null:
			assert_true(float(ring.get("ratio")) < 0.5, "hunger ring value %s" % str(ring.get("ratio")))


func test_mouth_item_indicator() -> void:
	await _frames(1)
	var gs := tree.root.get_node("GameState")
	gs.call("add_item", &"fish", 1)
	assert_true(bool(gs.call("set_mouth_item", &"fish")), "fish into mouth")
	await _frames(3)
	var status: Node = hud.get("status")
	assert_eq(StringName(status.get("mouth_item")), &"fish")
	gs.call("set_mouth_item", &"")
	await _frames(2)
	assert_eq(StringName(status.get("mouth_item")), &"")


func test_subtitles() -> void:
	await _frames(1)
	ge.emit_signal(&"subtitle_requested", "Bà Tư", "Mèo ơi!", 2.0)
	await _frames(1)
	assert_eq(int(hud.get("subtitles").call("line_count")), 1)


func test_quest_tracker_shows_tracked_quest() -> void:
	var qm := tree.root.get_node("QuestManager")
	qm.call("load_quest_dir", STORY_QUESTS)
	assert_true(bool(qm.call("start_quest", &"main_01_morning", true)), "quest started")
	qm.call("track", &"main_01_morning")
	await _frames(4)
	var tr_node: Control = hud.get("tracker")
	assert_true(tr_node.has_method("get_title_text"), "tracker exposes get_title_text")
	if tr_node.has_method("get_title_text"):
		assert_true(String(tr_node.call("get_title_text")) != "", "tracker title filled")
	qm.call("reset_quest", &"main_01_morning")


func test_dialogue_box_follows_manager() -> void:
	var dm := tree.root.get_node("DialogueManager")
	var dirs: PackedStringArray = dm.get("dialogue_dirs")
	if not dirs.has(STORY_DIALOGUE):
		dirs.append(STORY_DIALOGUE)
		dm.set("dialogue_dirs", dirs)
	var qm := tree.root.get_node("QuestManager")
	qm.call("load_quest_dir", STORY_QUESTS)
	qm.call("start_quest", &"main_01_morning", true)
	assert_true(bool(dm.call("start", &"ba_tu", null, &"ba_tu")), "dialogue started")
	await _frames(2)
	var box: DialogueBox = hud.get("dialogue")
	assert_true(box.active and box.visible, "box visible")
	box.finish_typing()
	var guard := 0
	while box.get_choice_buttons().is_empty() and bool(dm.call("is_active")) and guard < 8:
		dm.call("advance")
		await _frames(1)
		box.finish_typing()
		guard += 1
	assert_true(box.get_choice_buttons().size() >= 2, "choices shown: %d" % box.get_choice_buttons().size())
	var locked := 0
	for b in box.get_choice_buttons():
		if b.disabled:
			locked += 1
	assert_true(locked >= 1, "charm-gated choice is shown locked")
	box.get_choice_buttons()[0].pressed.emit()
	await _frames(2)
	while bool(dm.call("is_active")) and guard < 20:
		box.finish_typing()
		if not box.get_choice_buttons().is_empty():
			box.get_choice_buttons()[0].pressed.emit()
		else:
			dm.call("advance")
		await _frames(1)
		guard += 1
	assert_false(bool(dm.call("is_active")), "dialogue ended")
	await _wait(0.5)
	assert_false(box.active, "box inactive")
	qm.call("reset_quest", &"main_01_morning")


func test_menu_open_pauses_and_close_resumes() -> void:
	await _frames(1)
	var opened: Array[StringName] = []
	var cb := func(m: StringName) -> void: opened.append(m)
	ge.connect(&"ui_menu_opened", cb)
	var s: UIScreen = hud.call("open_screen", &"pause")
	assert_not_null(s)
	await _frames(2)
	assert_true(tree.paused, "tree paused by menu")
	assert_true(bool(hud.call("is_menu_open")))
	assert_true(opened.has(&"pause"))
	hud.call("close_all_menus")
	await _wait(0.5)
	assert_false(bool(hud.call("is_menu_open")))
	assert_false(tree.paused, "tree resumed")
	ge.disconnect(&"ui_menu_opened", cb)
