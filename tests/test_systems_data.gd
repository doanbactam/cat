extends "res://tests/fixtures/systems_test_base.gd"
## Data integrity: JSON files parse, i18n coverage for every key systems code/data references,
## and the examples in the schema docs are valid (so the docs can't rot).

const CSV_PATH := "res://data/i18n/requests/systems.csv"
const SOURCES := [
	"res://scripts/autoload/game_state.gd", "res://scripts/autoload/time_of_day.gd",
	"res://scripts/autoload/quest_manager.gd", "res://scripts/autoload/dialogue_manager.gd",
	"res://scripts/systems/conditions.gd", "res://scripts/systems/effects.gd",
	"res://scripts/systems/interactable.gd", "res://scripts/systems/pickup_item.gd",
	"res://scripts/systems/talkable.gd", "res://scripts/systems/nap_spot.gd",
	"res://scripts/systems/food_source.gd", "res://scripts/systems/scratch_post.gd",
	"res://scripts/systems/territory_spot.gd", "res://scripts/systems/quest_trigger.gd",
	"res://scripts/systems/pushable.gd", "res://scripts/systems/collectible.gd",
]


func _csv() -> Dictionary:
	var out := {}
	var f := FileAccess.open(CSV_PATH, FileAccess.READ)
	var header := f.get_csv_line()
	assert_eq(Array(header), ["keys", "en", "vi"])
	while not f.eof_reached():
		var row := f.get_csv_line()
		if row.size() < 3 or row[0] == "":
			continue
		out[row[0]] = [row[1], row[2]]
	return out


func test_json_files_parse() -> void:
	for p in ["res://data/items/items.json", "res://data/skills/skills.json"]:
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
		assert_true(v is Dictionary, p)


func test_csv_rows_complete_and_placeholders_match() -> void:
	var rows := _csv()
	assert_true(rows.size() > 250, "rows: %d" % rows.size())
	var re := RegEx.create_from_string("\\{(\\w+)\\}")
	for k: String in rows:
		var en: String = rows[k][0]
		var vi: String = rows[k][1]
		assert_true(en.strip_edges() != "" and vi.strip_edges() != "", k)
		var a: Array = re.search_all(en).map(func(m: RegExMatch) -> String: return m.get_string(1))
		var b: Array = re.search_all(vi).map(func(m: RegExMatch) -> String: return m.get_string(1))
		a.sort()
		b.sort()
		assert_eq(a, b, "placeholders differ in " + k)


func test_every_data_key_is_translated() -> void:
	var rows := _csv()
	var missing: PackedStringArray = []
	var need: PackedStringArray = []
	for id in GameState.get_all_item_ids():
		var d := GameState.get_item_def(StringName(id))
		need.append(String(d["name_key"]))
		need.append(String(d["desc_key"]))
		if d.has("story_key"):
			need.append(String(d["story_key"]))
	var skills := GameState.get_all_skills()
	for id: String in skills:
		need.append(String(skills[id]["name_key"]))
		need.append(String(skills[id]["desc_key"]))
	var trees := GameState.get_skill_trees()
	for t: String in trees:
		need.append(String(trees[t]["name_key"]))
		need.append(String(trees[t]["desc_key"]))
	for b in ["catnip", "playful", "sharp_claws", "well_fed", "warm_nap", "groomed"]:
		var key := String(GameState.get_buff_def(StringName(b))["name_key"])
		need.append(key)
		need.append(key + "_DESC")
	for a in DialogueManager.ACTIONS:
		need.append("DLG_ACT_" + a.to_upper())
	for a in GameState.ATTRIBUTES:
		need.append("ATTR_" + String(a).to_upper())
	for s in GameState.STATS:
		need.append("STAT_" + String(s).to_upper())
	for f in GameState.FACTIONS:
		need.append("FACTION_" + String(f).to_upper())
	for ph in ["dawn", "day", "dusk", "night"]:
		need.append("PHASE_" + ph.to_upper())
	for ach: String in GameState.ACHIEVEMENTS:
		need.append("ACH_" + ach.to_upper())
		need.append("ACH_" + ach.to_upper() + "_DESC")
	for npc in ["cam", "ba_tu", "mun", "bong", "ong_muop", "lao_qua", "xam", "ven", "co_hoa", "chu_sau", "bin"]:
		need.append("NPC_" + npc.to_upper())
	for verb in ["interact", "pickup", "talk", "sleep", "eat", "drink", "scratch", "mark", "collect", "knock"]:
		need.append("PROMPT_" + verb.to_upper())
	for k in need:
		if not rows.has(k):
			missing.append(k)
	assert_true(missing.is_empty(), "missing keys: %s" % ", ".join(missing))


func test_every_literal_tr_key_in_code_is_translated() -> void:
	var rows := _csv()
	var re := RegEx.create_from_string("(?:\\btr|_t)\\(\"([A-Z][A-Z0-9_]+)\"\\)")
	var re2 := RegEx.create_from_string("\"((?:PROMPT|REQ|NOTIFY)_[A-Z0-9_]+)\"")
	var missing: PackedStringArray = []
	for src: String in SOURCES:
		var raw := FileAccess.get_file_as_string(src)
		assert_true(raw != "", src)
		var code_lines: PackedStringArray = []
		for line in raw.split("\n"):
			if not line.strip_edges().begins_with("#"):
				code_lines.append(line)
		var text := "\n".join(code_lines)
		for m in re.search_all(text) + re2.search_all(text):
			var k := m.get_string(1)
			if k.ends_with("_") or k == "PROMPT_" or k == "REQ_":
				continue
			if not rows.has(k) and k not in missing:
				missing.append(k)
	assert_true(missing.is_empty(), "untranslated literal keys: %s" % ", ".join(missing))


func _json_blocks(md_path: String) -> Array:
	var text := FileAccess.get_file_as_string(md_path)
	var out := []
	var parts := text.split("```json")
	for i in range(1, parts.size()):
		var block := parts[i].split("```")[0]
		var v: Variant = JSON.parse_string(block)
		assert_true(v is Dictionary, "example %d in %s parses" % [i, md_path])
		if v is Dictionary:
			out.append(v)
	return out


func test_quest_schema_examples_are_valid() -> void:
	var blocks := _json_blocks("res://data/quests/_schema.md")
	assert_eq(blocks.size(), 2)
	for q: Dictionary in blocks:
		var errs := QuestManager.validate_quest(q)
		assert_true(errs.is_empty(), "%s: %s" % [q.get("id"), str(errs)])
		assert_true(QuestManager.register_quest(q))


func test_dialogue_schema_examples_are_valid() -> void:
	var blocks := _json_blocks("res://data/dialogue/_schema.md")
	assert_eq(blocks.size(), 2)
	for d: Dictionary in blocks:
		var errs := DialogueManager.validate_dialogue(d)
		assert_true(errs.is_empty(), "%s: %s" % [d.get("id"), str(errs)])


func test_schema_example_trials_play_through() -> void:
	# The documented rooftop-trials quest really works with parallel stage objectives.
	var q: Dictionary = _json_blocks("res://data/quests/_schema.md")[0]
	q["prerequisites"] = {}
	QuestManager.register_quest(q)
	assert_true(QuestManager.start_quest(&"main_04_rooftop_trials"))
	QuestManager.report(&"talk_to", {"npc_id": "mun"})
	for s in ["r1", "r2", "r3"]:
		GameState.mark_territory(StringName(s))
	GameEvents.area_entered.emit(&"water_tower")
	TimeOfDay.set_hour(12.0)
	QuestManager.report(&"rooftop_race_won", {"rival": "mun"})
	assert_false(QuestManager.is_objective_done(&"main_04_rooftop_trials", &"race"), "race only at dusk/night")
	TimeOfDay.set_hour(19.0)
	QuestManager.report(&"rooftop_race_won", {"rival": "mun"})
	assert_true(QuestManager.is_objective_active(&"main_04_rooftop_trials", &"report_back"))
	QuestManager.report(&"talk_to", {"npc_id": "mun"})
	assert_true(QuestManager.is_completed(&"main_04_rooftop_trials"))
	assert_true(bool(GameState.get_flag(&"rooftops_open")))
	assert_true(QuestManager.get_objectives(&"main_04_rooftop_trials")[4]["missed"], "optional show_off missed")
