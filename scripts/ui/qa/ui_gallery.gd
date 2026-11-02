extends Node3D
## QA gallery for the UI area (res://scenes/ui/qa/ui_gallery.tscn). Builds a believable game
## state (story quest fixtures, items, xp, discovered places) over the live rooftop backdrop and
## opens one screen chosen on the command line, so every screen can be captured with
##   tools/screenshot.sh scene=res://scenes/ui/qa/ui_gallery.tscn out=/abs.png -- screen=<id> [lang=en]
## screen ids: menu, splash, loading, hud, hud_events, dialogue, pause, inventory, skills, journal,
## journal_memories, map, settings, settings_audio, settings_controls, settings_gameplay,
## save_slots, credits, confirm. `world=city` swaps the rooftop backdrop for the real
## res://scenes/world/city.tscn (camera + "player" proxy at PlayerSpawn, the city's own location
## markers) — used to QA the map capture. Not shipped gameplay — a capture/test harness only.

const BACKDROP := "res://scenes/ui/menu_backdrop.tscn"
const HUD := "res://scenes/ui/hud.tscn"
const MAIN := "res://scenes/main/main.tscn"
const STORY_QUESTS := "res://tests/fixtures/story/quests"
const STORY_DIALOGUE := "res://tests/fixtures/story/dialogue"

const CITY := "res://scenes/world/city.tscn"

var screen_id := "hud"
var world_id := "backdrop"
var hud: CanvasLayer = null


func _ready() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() == 2:
			args[kv[0]] = kv[1]
	screen_id = String(args.get("screen", "hud"))
	world_id = String(args.get("world", "backdrop"))
	var lang := String(args.get("lang", ""))
	if lang != "":
		TranslationServer.set_locale(lang)
	get_tree().current_scene = self
	_run.call_deferred()


func _run() -> void:
	if screen_id in ["menu", "splash"]:
		var m := (load(MAIN) as PackedScene).instantiate()
		if screen_id == "menu":
			var loader := get_node_or_null(^"/root/SceneLoader")
			if loader != null:
				loader.set("skip_splash_once", true)
		add_child(m)
		return
	if screen_id == "loading":
		var ls := (load("res://scenes/ui/loading_screen.tscn") as PackedScene).instantiate() as Control
		var cl := CanvasLayer.new()
		add_child(cl)
		cl.add_child(ls)
		if ls.has_method("set_progress"):
			ls.call("set_progress", 0.62)
		return
	if world_id == "city" and ResourceLoader.exists(CITY):
		_add_city()
		_populate_state()
	else:
		add_child((load(BACKDROP) as PackedScene).instantiate())
		_populate_state()
		_add_markers()
	hud = (load(HUD) as PackedScene).instantiate() as CanvasLayer
	add_child(hud)
	await get_tree().process_frame
	await get_tree().process_frame
	match screen_id:
		"hud":
			_hud_idle()
		"hud_events":
			_hud_events()
		"dialogue":
			_dialogue()
		"settings_audio", "settings_controls", "settings_gameplay":
			var s: UIScreen = hud.call("open_screen", &"settings")
			var tab := {"settings_audio": 1, "settings_controls": 2, "settings_gameplay": 3}[screen_id] as int
			for i in tab:
				s.on_tab_input(1)
		"journal_memories":
			var j: UIScreen = hud.call("open_screen", &"journal")
			j.on_tab_input(1)
		"confirm":
			var host: UIMenuHost = hud.get("host")
			host.push_screen(UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_BODY", true))
		"credits":
			var host2: UIMenuHost = hud.get("host")
			host2.push_screen("res://scenes/ui/credits.tscn")
		_:
			var sc: UIScreen = hud.call("open_screen", StringName(screen_id))
			if sc != null and screen_id == "save_slots":
				sc.set("mode", &"save")


func _populate_state() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	var qm := get_node_or_null(^"/root/QuestManager")
	var dm := get_node_or_null(^"/root/DialogueManager")
	if qm != null:
		qm.call("load_quest_dir", STORY_QUESTS)
	if dm != null:
		var dirs: PackedStringArray = dm.get("dialogue_dirs")
		if not dirs.has(STORY_DIALOGUE):
			dirs.append(STORY_DIALOGUE)
			dm.set("dialogue_dirs", dirs)
	if gs == null:
		return
	gs.call("new_game")
	gs.call("add_xp", 380, "qa")
	gs.call("add_item", &"cap", 37)
	for id: StringName in [&"dried_fish", &"shrimp", &"quail_egg", &"toy_mouse", &"yarn",
			&"glass_marble", &"brass_bell", &"pigeon_feather", &"collar_red", &"catnip", &"letter"]:
		gs.call("add_item", id, 1)
	gs.call("add_item", &"shrimp", 2)
	gs.call("add_item", &"fish", 1)
	gs.call("set_mouth_item", &"fish")
	gs.call("modify_stat", &"hunger", -38.0)
	gs.call("modify_stat", &"energy", -22.0)
	gs.call("modify_stat", &"warmth", -55.0)
	gs.call("discover_location", &"tea_stall", "LOC_TEA_STALL")
	gs.call("discover_location", &"fish_street", "LOC_FISH_STREET")
	gs.call("discover_location", &"temple", "LOC_TEMPLE")
	gs.call("mark_collectible", &"memory_01")
	gs.call("mark_collectible", &"memory_04")
	var skills: Dictionary = gs.call("get_all_skills")
	var n := 0
	for sid: String in skills.keys():
		if n >= 3:
			break
		if bool(gs.call("can_unlock_skill", StringName(sid))):
			gs.call("unlock_skill", StringName(sid))
			n += 1
	gs.call("add_skill_points", 2)
	if qm != null:
		for q: StringName in [&"main_01_morning", &"side_letter", &"side_bins_key"]:
			if bool(qm.call("has_quest", q)):
				qm.call("start_quest", q, true)
		if bool(qm.call("has_quest", &"side_knock_it_off")):
			qm.call("start_quest", &"side_knock_it_off", true)
			qm.call("complete_quest", &"side_knock_it_off")
		qm.call("track", &"main_01_morning")


func _add_city() -> void:
	var city := (load(CITY) as PackedScene).instantiate() as Node3D
	add_child(city)
	var spawn := get_tree().get_first_node_in_group(&"player_spawn") as Node3D
	var xf := spawn.global_transform if spawn != null else Transform3D.IDENTITY
	# Stand-in for the player so the map arrow and compass have something to follow.
	var proxy := Node3D.new()
	proxy.name = "PlayerProxy"
	proxy.add_to_group(&"player")
	add_child(proxy)
	proxy.global_transform = xf
	var cam := Camera3D.new()
	cam.name = "QACamera"
	add_child(cam)
	cam.global_position = xf.origin + xf.basis.z * 3.0 + Vector3.UP * 1.6
	cam.look_at(xf.origin + Vector3.UP * 0.4)
	cam.current = true
	var gs := get_node_or_null(^"/root/GameState")
	# Discover every city location so the map shows the full set of labels.
	for m in get_tree().get_nodes_in_group(&"location"):
		var id: StringName = StringName(str(m.get_meta(&"location_id", m.name)))
		if gs != null:
			gs.call_deferred("discover_location", id, str(m.get_meta(&"display_name_key", "")))


func _add_markers() -> void:
	var cam := get_viewport().get_camera_3d()
	var base := cam.global_position if cam != null else Vector3.ZERO
	var fwd := -cam.global_basis.z if cam != null else Vector3.FORWARD
	var right := cam.global_basis.x if cam != null else Vector3.RIGHT
	var defs := [
		["tea_stall", "LOC_TEA_STALL", fwd * 40.0 + right * 12.0, true],
		["fish_street", "LOC_FISH_STREET", -fwd * 30.0 + right * 50.0, false],
		["temple", "LOC_TEMPLE", fwd * 25.0 - right * 30.0, false],
	]
	for d: Array in defs:
		var m := Marker3D.new()
		m.name = "Loc_" + String(d[0])
		m.add_to_group(&"location")
		m.set_meta(&"location_id", StringName(d[0]))
		m.set_meta(&"display_name_key", String(d[1]))
		add_child(m)
		m.global_position = base + (d[2] as Vector3)
	var t := Marker3D.new()
	t.name = "QuestTarget"
	t.add_to_group(&"quest_target")
	t.set_meta(&"target_id", &"ba_tu")
	add_child(t)
	t.global_position = base + fwd * 40.0 + right * 12.0


func _hud_idle() -> void:
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge == null:
		return
	ge.emit_signal(&"interactable_focused", self, tr("PROMPT_TALK").format({"name": "Bà Tư"}))
	ge.emit_signal(&"notify", "%s ×2" % tr("ITEM_SHRIMP"), &"shrimp")
	ge.emit_signal(&"notify", tr("NOTIFY_TERRITORY_MARKED").format({"count": 3}), &"paw")
	ge.emit_signal(&"subtitle_requested", "Bà Tư", "Con mèo cam lại về đấy à? Lại đây, bà để phần cá cho này." if TranslationServer.get_locale().begins_with("vi") else "Back again, little orange one? Come here, I saved you some fish.", 30.0)


func _hud_events() -> void:
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge == null:
		return
	ge.emit_signal(&"location_discovered", &"fish_street", tr("LOC_FISH_STREET"))
	await get_tree().create_timer(0.1).timeout
	var cel: Node = hud.get("celebration")
	cel.call("show_level_up", 4, 1)


func _dialogue() -> void:
	var dm := get_node_or_null(^"/root/DialogueManager")
	if dm == null:
		return
	dm.call("start", &"ba_tu", null, &"ba_tu")
	await get_tree().create_timer(0.2).timeout
	var box: Node = hud.get("dialogue")
	# Walk to the first node that offers choices so the capture shows the full layout.
	for i in 6:
		box.call("finish_typing")
		await get_tree().process_frame
		if (box.call("get_choice_buttons") as Array).size() > 0:
			break
		dm.call("advance")
		await get_tree().create_timer(0.1).timeout
	box.call("finish_typing")
