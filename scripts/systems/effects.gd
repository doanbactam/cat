class_name GameEffects
extends RefCounted
## Shared effect executor (dialogue nodes/choices, quest objective & completion rewards).
## An effect list is an Array of Dictionaries; each Dictionary has ONE type key whose value is the
## primary argument, plus optional extra arguments. Full reference: data/dialogue/_schema.md.
##   {"set_flag": "met_bong"} {"set_flag": "x", "value": 2}   {"clear_flag": "x"}
##   {"give_item": "fish", "count": 1}  {"take_item": "cap", "count": 10}  {"set_mouth": "fish"}
##   {"deliver": "fish", "to": "lao_qua"}   (removes the item, emits item_delivered)
##   {"start_quest": "main_03"} {"advance_quest": "main_03", "objective": "get_fish", "amount": 1}
##   {"complete_objective": "get_fish", "quest": "main_03"} {"complete_quest": "x"} {"fail_quest": "x"}
##   {"track_quest": "x"}  {"add_xp": 25, "reason": "dialogue"}  {"add_rep": "humans", "amount": 5}
##   {"add_skill_points": 1} {"add_attribute_points": 1} {"add_attribute": "charm", "amount": 1}
##   {"grant_skill": "mat_dem"} {"modify_stat": "hunger", "amount": 30} {"eat": 30, "health": 5}
##   {"add_buff": "catnip", "hours": 1.0}  {"report": "interact", "data": {...}}
##   {"notify": "NOTIFY_KEY", "icon": "quest"} {"discover_location": "lake", "name_key": "LOC_LAKE"}
##   {"advance_time": 1.5}  {"sleep_until": 6.0}  {"sfx": "cat_purr"}
##   {"speaker_call": "play_anim", "args": ["pet_cat"]}  {"buy": "collar_red", "price": 15}
##   {"sell": "silver_spoon", "price": 6}  {"set_weather": "rain", "intensity": 0.7}
##   {"mark_collectible": "memory_03"}  {"counter": "gifts", "amount": 1}
##   {"if": <condition>, "then": [effects], "else": [effects]}

const TYPES: Array[String] = [
	"set_flag", "clear_flag", "give_item", "take_item", "set_mouth", "deliver", "start_quest",
	"advance_quest", "complete_objective", "complete_quest", "fail_quest", "track_quest", "add_xp",
	"add_rep", "add_skill_points", "add_attribute_points", "add_attribute", "grant_skill",
	"modify_stat", "eat", "add_buff", "report", "notify", "discover_location", "advance_time",
	"sleep_until", "sfx", "speaker_call", "buy", "sell", "set_weather", "mark_collectible", "counter",
	"if",
]
const ARG_KEYS: Array[String] = [
	"value", "count", "to", "objective", "amount", "quest", "reason", "hours", "data", "icon",
	"name_key", "args", "price", "intensity", "health", "then", "else",
]


## Applies a list of effects (or a single effect dictionary). ctx may hold "speaker" (Node),
## "speaker_id", "dialogue_id", "quest_id". Returns false if any effect failed (e.g. buy w/o caps).
static func apply(effects: Variant, ctx: Dictionary = {}) -> bool:
	if effects == null:
		return true
	if effects is Dictionary:
		return apply_one(effects, ctx)
	var ok := true
	if effects is Array:
		for e: Variant in effects:
			if e is Dictionary:
				ok = apply_one(e, ctx) and ok
			else:
				push_warning("GameEffects: effect must be a dictionary: " + str(e))
	return ok


static func apply_one(e: Dictionary, ctx: Dictionary = {}) -> bool:
	if e.has("if"):
		if GameConditions.evaluate(e["if"], ctx):
			return apply(e.get("then", []), ctx)
		return apply(e.get("else", []), ctx)
	var type := _type_of(e)
	if type == "":
		push_warning("GameEffects: unknown effect " + str(e))
		return false
	var v: Variant = e[type]
	var sv := StringName(str(v))
	match type:
		"set_flag":
			GameState.set_flag(sv, e.get("value", true))
		"clear_flag":
			GameState.clear_flag(sv)
		"give_item":
			GameState.add_item(sv, int(e.get("count", 1)))
		"take_item":
			return GameState.remove_item(sv, int(e.get("count", 1)))
		"set_mouth":
			return GameState.set_mouth_item(sv)
		"deliver":
			return QuestManager.deliver_item(sv, StringName(str(e.get("to", ctx.get("speaker_id", "")))))
		"start_quest":
			return QuestManager.start_quest(sv)
		"advance_quest":
			return QuestManager.advance_objective(sv, StringName(str(e.get("objective", ""))), int(e.get("amount", 1)))
		"complete_objective":
			return QuestManager.complete_objective(StringName(str(e.get("quest", ctx.get("quest_id", "")))), sv)
		"complete_quest":
			return QuestManager.complete_quest(sv)
		"fail_quest":
			return QuestManager.fail_quest(sv)
		"track_quest":
			return QuestManager.track(sv)
		"add_xp":
			GameState.add_xp(int(GameConditions._num(v)), String(e.get("reason", ctx.get("dialogue_id", "effect"))))
		"add_rep":
			GameState.add_reputation(sv, int(e.get("amount", 1)))
		"add_skill_points":
			GameState.add_skill_points(int(GameConditions._num(v)))
		"add_attribute_points":
			GameState.add_attribute_points(int(GameConditions._num(v)))
		"add_attribute":
			GameState.add_attribute(sv, int(e.get("amount", 1)))
		"grant_skill":
			GameState.grant_skill(sv)
		"modify_stat":
			GameState.modify_stat(sv, float(e.get("amount", 0.0)))
		"eat":
			GameState.eat(GameConditions._num(v), StringName(str(ctx.get("speaker_id", ""))), float(e.get("health", 0.0)))
		"add_buff":
			GameState.add_buff(sv, float(e.get("hours", -1.0)))
		"report":
			var data: Dictionary = e.get("data", {}) if e.get("data", {}) is Dictionary else {}
			QuestManager.report(sv, data)
		"notify":
			GameEvents.notify.emit(TranslationServer.translate(sv), StringName(str(e.get("icon", "info"))))
		"discover_location":
			GameState.discover_location(sv, String(TranslationServer.translate(StringName(str(e.get("name_key", "LOC_" + str(v).to_upper()))))))
		"advance_time":
			TimeOfDay.skip_hours(GameConditions._num(v))
		"sleep_until":
			TimeOfDay.sleep_until(GameConditions._num(v))
		"sfx":
			var pos := Vector3.INF
			var sp: Variant = ctx.get("speaker")
			if sp is Node3D and is_instance_valid(sp):
				pos = (sp as Node3D).global_position
			play_sfx(sv, pos)
		"speaker_call":
			var sp: Variant = ctx.get("speaker")
			if sp is Object and is_instance_valid(sp) and (sp as Object).has_method(String(sv)):
				(sp as Object).callv(String(sv), e.get("args", []) if e.get("args", []) is Array else [])
		"buy":
			return GameState.buy_item(sv, int(e.get("price", -1)))
		"sell":
			return GameState.sell_item(sv, int(e.get("price", -1))) > 0
		"set_weather":
			var w := Engine.get_main_loop() as SceneTree
			var wn: Node = w.get_first_node_in_group(&"weather") if w != null else null
			GameState.set_weather_state(sv, float(e.get("intensity", 0.6)))
			if wn != null and wn.has_method("set_weather"):
				wn.call("set_weather", sv, float(e.get("intensity", 0.6)))
		"mark_collectible":
			GameState.mark_collectible(sv)
		"counter":
			GameState.increment_counter(sv, int(e.get("amount", 1)))
	return true


## Plays a sound through AudioManager if it is implemented (silent no-op otherwise).
static func play_sfx(sfx_name: StringName, pos: Vector3 = Vector3.INF, volume_db: float = 0.0) -> void:
	if sfx_name == &"":
		return
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null:
		return
	var am := tree.root.get_node_or_null(^"AudioManager")
	if am != null and am.has_method("play_sfx"):
		am.call("play_sfx", sfx_name, pos, volume_db)


static func _type_of(e: Dictionary) -> String:
	for key: Variant in e:
		var k := String(key)
		if k in TYPES:
			return k
	return ""


## Returns a list of problems in an effect list (unknown types, multiple types, bad args).
static func validate(effects: Variant, where: String = "") -> PackedStringArray:
	var errs: PackedStringArray = []
	if effects == null:
		return errs
	var list: Array = effects if effects is Array else [effects]
	for e: Variant in list:
		if not e is Dictionary:
			errs.append("%s: effect is not a dictionary: %s" % [where, str(e)])
			continue
		var d: Dictionary = e
		var types := 0
		for key: Variant in d:
			var k := String(key)
			if k in TYPES:
				types += 1
			elif k not in ARG_KEYS:
				errs.append("%s: unknown effect key '%s' in %s" % [where, k, str(d)])
		if types != 1:
			errs.append("%s: effect must have exactly one type key: %s" % [where, str(d)])
		if d.has("if"):
			errs.append_array(GameConditions.validate(d["if"], where))
			errs.append_array(validate(d.get("then", []), where))
			errs.append_array(validate(d.get("else", []), where))
	return errs
