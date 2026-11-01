extends "res://tests/fixtures/systems_test_base.gd"
## End-to-end: plays the GDD main story ("Đêm Trăng Rằm") and two side quests through real
## interactables (Talkable, PickupItem, Collectible, TerritorySpot, NapSpot) and the story
## dialogue graphs in tests/fixtures/story — proving the systems express the whole design.

const STORY_QUESTS := "res://tests/fixtures/story/quests"
const STORY_DIALOGUE := "res://tests/fixtures/story/dialogue"

var player: FakePlayer
var _talkables: Dictionary = {}


func before_each() -> void:
	super.before_each()
	QuestManager.quest_dirs = PackedStringArray([STORY_QUESTS])
	QuestManager.reload_definitions()
	DialogueManager.dialogue_dirs = PackedStringArray([STORY_DIALOGUE])
	DialogueManager.clear_cache()
	_talkables.clear()


func _talkable(npc: String) -> Talkable:
	if not _talkables.has(npc):
		var t := Talkable.new()
		t.name = "Talk_" + npc
		t.speaker_id = StringName(npc)
		t.dialogue_id = StringName(npc)
		t.cooldown = 0.0
		spawn(t)
		_talkables[npc] = t
	var tk: Talkable = _talkables[npc]
	tk.global_position = player.global_position + Vector3(0.5, 0, 0)
	return tk


## Talk to an NPC and play the dialogue: picks choices whose action is in `actions` (in order),
## otherwise advances. Returns the node ids that were shown.
func talk(npc: String, actions: Array = []) -> Array:
	var shown := []
	var t := _talkable(npc)
	assert_true(t.can_interact(player), "can talk to " + npc)
	t.interact(player)
	var guard := 0
	var queue := actions.duplicate()
	while DialogueManager.is_active() and guard < 20:
		guard += 1
		shown.append(DialogueManager.get_current_line()["node_id"])
		var choices := DialogueManager.get_choices()
		if choices.is_empty():
			DialogueManager.advance()
			continue
		var picked := false
		if not queue.is_empty():
			for i in choices.size():
				if choices[i]["action"] == queue[0] and choices[i]["enabled"]:
					queue.pop_front()
					DialogueManager.choose(i)
					picked = true
					break
		if not picked:
			# default: first enabled choice
			for i in choices.size():
				if choices[i]["enabled"]:
					DialogueManager.choose(i)
					picked = true
					break
		if not picked:
			DialogueManager.stop()
	assert_false(DialogueManager.is_active(), "dialogue with %s ended" % npc)
	return shown


func test_story_data_is_valid() -> void:
	var ids := QuestManager.get_quest_ids()
	assert_eq(ids.size(), 11)
	for id in ids:
		var errs := QuestManager.validate_quest(QuestManager.get_quest_def(StringName(id)))
		assert_true(errs.is_empty(), "%s: %s" % [id, str(errs)])
	for d in DirAccess.get_files_at(STORY_DIALOGUE):
		var def := DialogueManager.get_dialogue(StringName(d.get_basename()))
		assert_false(def.is_empty(), d)
		assert_true(DialogueManager.validate_dialogue(def).is_empty(), "%s: %s" % [d, str(DialogueManager.validate_dialogue(def))])


func test_story_keys_translated() -> void:
	var rows := {}
	var f := FileAccess.open("res://data/i18n/requests/systems.csv", FileAccess.READ)
	while not f.eof_reached():
		var r := f.get_csv_line()
		if r.size() >= 3:
			rows[r[0]] = true
	var missing: PackedStringArray = []
	for id in QuestManager.get_quest_ids():
		var q := QuestManager.get_quest_def(StringName(id))
		for k in [q["title_key"], q["desc_key"]]:
			if not rows.has(k): missing.append(k)
		for o: Dictionary in q["objectives"]:
			if not rows.has(o["desc_key"]): missing.append(o["desc_key"])
	for d in DirAccess.get_files_at(STORY_DIALOGUE):
		var def := DialogueManager.get_dialogue(StringName(d.get_basename()))
		for nid: String in def["nodes"]:
			var n: Dictionary = def["nodes"][nid]
			if n.has("text_key") and not rows.has(n["text_key"]): missing.append(n["text_key"])
			for c: Dictionary in n.get("choices", []):
				if c.has("text_key") and not rows.has(c["text_key"]): missing.append(c["text_key"])
		var sp := String(def.get("speaker", ""))
		if not rows.has("NPC_" + sp.to_upper()): missing.append("NPC_" + sp.to_upper())
	assert_true(missing.is_empty(), "missing: " + ", ".join(missing))


func test_full_main_story_playthrough() -> void:
	player = spawn_player(Vector3(0, 6, 0))
	GameState.new_game()   # providers reset → opening chapter auto-starts
	TimeOfDay.set_time(1, 6.0)
	assert_true(QuestManager.is_active(&"main_01_morning"), "opening chapter auto-starts")
	assert_eq(QuestManager.get_tracked(), &"main_01_morning")

	# --- 1. Sáng sớm: climb down, greet Grandma (breakfast), sniff the counter
	player.global_position = Vector3(4, 0, 2)
	spawn_marker("tea_stall", Vector3(4.5, 0, 2.5), &"location", &"location_id")
	QuestManager._poll_reach_objectives()
	assert_true(QuestManager.is_objective_done(&"main_01_morning", &"climb_down"))
	GameState.set_stat(&"hunger", 50.0)
	var nodes := talk("ba_tu", ["meow"])
	assert_true("morning" in nodes and "missing" in nodes, str(nodes))
	assert_true(bool(GameState.get_flag(&"fed_breakfast")))
	assert_true(GameState.get_stat(&"hunger") > 80.0, "Grandma fed Cam")
	var counter := Interactable.new()
	counter.verb = &"sniff"
	counter.target_id = &"stall_counter"
	spawn(counter)
	GameEvents.interacted.emit(counter, &"sniff")  # the player emits this when interacting
	assert_true(QuestManager.is_completed(&"main_01_morning"))
	assert_true(QuestManager.is_active(&"main_02_rumours"), "chained")
	assert_true(QuestManager.is_active(&"side_knock_it_off"), "auto-started side activity")

	# --- 2. Tin đồn: Bông → banyan → Lão Quạ
	talk("bong", ["chirp"])
	assert_true(bool(GameState.get_flag(&"heard_crows")))
	GameEvents.area_entered.emit(&"banyan")
	nodes = talk("lao_qua", ["meow"])
	assert_true("terms" in nodes, str(nodes))
	assert_true(QuestManager.is_completed(&"main_02_rumours"))
	assert_true(QuestManager.is_active(&"main_03_fish_market"))

	# --- 3. Chợ cá: charm cô Hoa (Charm 3), gather 10 caps, pay the crow
	nodes = talk("co_hoa", ["leave"])
	assert_true("stall" in nodes)
	assert_false(GameState.has_item(&"fish"), "charm 2: sitting pretty is locked")
	GameState.add_attribute_points(1)
	assert_true(GameState.raise_attribute(&"charm"))
	talk("co_hoa", ["sit"])
	assert_eq(GameState.mouth_item, &"fish", "Miss Hoa gave a fish")
	assert_true(QuestManager.is_objective_done(&"main_03_fish_market", &"charmed"), "hidden optional revealed+done")
	for i in 3:
		var c := Collectible.new()
		c.collectible_id = StringName("caps_market_%d" % i)
		c.kind = &"caps"
		c.amount = 4
		spawn(c)
		c.global_position = player.global_position
		c.interact(player)
	assert_true(GameState.get_caps() >= 10)
	assert_true(QuestManager.is_objective_active(&"main_03_fish_market", &"give_fish"))
	nodes = talk("lao_qua", ["offer_item"])
	assert_true("pay" in nodes and "secret" in nodes, str(nodes))
	assert_false(GameState.has_item(&"fish"), "fish delivered on talk")
	assert_eq(GameState.get_caps(), 2)
	assert_true(QuestManager.is_completed(&"main_03_fish_market"))

	# --- 4. Thử thách mái nhà
	nodes = talk("mun", ["slow_blink"])
	assert_true("challenge" in nodes and "trials" in nodes)
	nodes = talk("mun")
	assert_true("not_yet" in nodes, "trials not done yet")
	for s in ["roof_ridge", "ac_unit_row", "laundry_line"]:
		var spot := TerritorySpot.new()
		spot.spot_id = StringName(s)
		spawn(spot)
		spot.global_position = player.global_position
		spot.interact(player)
	GameEvents.area_entered.emit(&"water_tower")
	QuestManager.report(&"rooftop_race_won", {"rival": "mun"})
	nodes = talk("mun")
	assert_true("respect" in nodes, str(nodes))
	assert_true(QuestManager.is_completed(&"main_04_rooftop_trials"))
	assert_true(bool(GameState.get_flag(&"rooftops_open")))
	assert_true(QuestManager.is_active(&"main_05_festival_night"))

	# --- 5. Đêm hội: wait for the festival night (nap until then), temple roof, nest, home
	TimeOfDay.set_time(3, 12.0)
	GameEvents.area_entered.emit(&"temple_roof")
	assert_false(QuestManager.is_objective_done(&"main_05_festival_night", &"wait_festival"))
	var bed := NapSpot.new()
	bed.spot_id = &"stall_counter_box"
	bed.sleep_until_hour = 19.0
	bed.cooldown = 0.0
	spawn(bed)
	bed.global_position = player.global_position
	var night_box := NapSpot.new()
	night_box.spot_id = &"warm_vent"
	night_box.sleep_until_hour = 6.0
	night_box.cooldown = 0.0
	spawn(night_box)
	night_box.global_position = player.global_position
	bed.interact(player)        # day 3 19:00 — not the festival yet
	assert_false(QuestManager.is_objective_done(&"main_05_festival_night", &"wait_festival"))
	night_box.interact(player)  # day 4 06:00
	bed.interact(player)        # day 4 19:00 — festival night
	assert_eq(TimeOfDay.day, 4)
	assert_true(TimeOfDay.is_festival_night())
	assert_true(QuestManager.is_objective_done(&"main_05_festival_night", &"wait_festival"))
	GameEvents.area_entered.emit(&"temple_roof")
	assert_true(QuestManager.is_objective_done(&"main_05_festival_night", &"climb_temple"))
	var fig := PickupItem.new()
	fig.item_id = &"lucky_cat_figurine"
	spawn(fig)
	fig.global_position = player.global_position
	fig.interact(player)
	assert_eq(GameState.mouth_item, &"lucky_cat_figurine")
	nodes = talk("ba_tu")
	assert_true("finale" in nodes and "finale2" in nodes, str(nodes))
	assert_true(QuestManager.is_completed(&"main_05_festival_night"))
	assert_true(bool(GameState.get_flag(&"story_complete")))
	assert_false(GameState.has_item(&"lucky_cat_figurine"), "returned to Grandma")
	for q in ["main_01_morning", "main_02_rumours", "main_03_fish_market", "main_04_rooftop_trials", "main_05_festival_night"]:
		assert_true(QuestManager.is_completed(StringName(q)), q)
	assert_true(GameState.level >= 4, "level after the story: %d (xp %d)" % [GameState.level, GameState.xp])
	assert_true(GameState.get_reputation(&"rooftop_cats") >= 25)
	# The finale is shown once; afterwards Grandma is back to normal.
	nodes = talk("ba_tu", ["leave"])
	assert_true("idle" in nodes, str(nodes))


func test_side_quests_bin_and_xam() -> void:
	player = spawn_player(Vector3.ZERO)
	GameState.new_game()
	QuestManager.start_quest(&"main_01_morning")
	QuestManager.complete_quest(&"main_01_morning")
	TimeOfDay.set_time(1, 10.0)
	talk("bin", ["headbutt"])
	assert_true(QuestManager.is_active(&"side_bins_key"))
	assert_true(QuestManager.is_objective_done(&"side_bins_key", &"meet_bin"), "talking started & counted")
	var key := PickupItem.new()
	key.item_id = &"key"
	spawn(key)
	key.global_position = player.global_position
	key.interact(player)
	TimeOfDay.set_hour(22.0)
	talk("bin")
	assert_false(QuestManager.is_completed(&"side_bins_key"), "too late — Bin is home asleep (07–21)")
	assert_true(GameState.has_item(&"key"))
	TimeOfDay.set_hour(8.0)
	nodes_has(talk("bin"), "play")  # the key is handed over before the dialogue picks its entry
	assert_true(QuestManager.is_completed(&"side_bins_key"))
	assert_true(GameState.has_item(&"toy_mouse"))
	# Xám: start through dialogue, swap the toy for the band, return it
	talk("xam", ["chirp"])
	assert_true(QuestManager.is_active(&"side_xam_leg_band"))
	var band := PickupItem.new()
	band.item_id = &"leg_band"
	spawn(band)
	band.global_position = player.global_position
	band.interact(player)   # mouth had the toy mouse → swapped
	assert_eq(GameState.mouth_item, &"leg_band")
	talk("xam")
	assert_true(QuestManager.is_completed(&"side_xam_leg_band"))
	assert_true(GameState.get_reputation(&"birds") > 0)


func nodes_has(nodes: Array, id: String) -> void:
	assert_true(id in nodes, "%s in %s" % [id, str(nodes)])


func test_memories_side_quest_auto_starts_and_tracks_count() -> void:
	player = spawn_player(Vector3.ZERO)
	GameState.new_game()
	assert_false(QuestManager.is_active(&"side_memories"))
	for i in range(1, 13):
		var m := Collectible.new()
		m.collectible_id = StringName("memory_%02d" % i)
		spawn(m)
		m.global_position = player.global_position
		m.interact(player)
		if i == 1:
			assert_true(QuestManager.is_active(&"side_memories"), "starts with the first photo")
	assert_true(QuestManager.is_completed(&"side_memories"))
	assert_true(GameState.has_achievement(&"memory_keeper"))
	assert_true(bool(GameState.get_flag(&"memories_complete")))


func test_story_save_midway_and_resume() -> void:
	player = spawn_player(Vector3(1, 0, 1))
	GameState.new_game()
	QuestManager.complete_quest(&"main_01_morning")
	talk("bong", ["chirp"])
	GameState.save_game(1)
	GameState.new_game()
	assert_true(QuestManager.is_active(&"main_01_morning"), "fresh game")
	assert_true(GameState.load_game(1))
	assert_true(QuestManager.is_active(&"main_02_rumours"))
	assert_true(QuestManager.is_objective_done(&"main_02_rumours", &"ask_bong"))
	assert_true(DialogueManager.has_seen(&"bong"))
	GameEvents.area_entered.emit(&"banyan")
	talk("lao_qua", ["meow"])
	assert_true(QuestManager.is_active(&"main_03_fish_market"), "story continues after load")
