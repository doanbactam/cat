class_name GameConditions
extends RefCounted
## Shared condition evaluator (dialogue choices/entries, quest prerequisites & objective windows,
## skill conditional effects, interactable requirements). Format: data/dialogue/_schema.md.
##
## A condition is: null/{} (always true) · a bool · a String flag name ("!name" = flag false) ·
## an Array (ALL must hold) · or a Dictionary with one primary key plus optional comparators:
##   {"flag": "met_bong"}  {"flag": "x", "value": 3}  {"not_flag": "x"}
##   {"item": "fish", "count": 1}  {"mouth": "fish"}  {"mouth_empty": true}  {"caps": 10}
##   {"attribute": "charm", "gte": 3}  {"skill": "mat_dem"}  {"not_skill": "..."}
##   {"reputation": "humans", "gte": 10}  {"level": 3}  {"stat": "hunger", "lte": 30}
##   {"quest": "main_02", "state": "active|completed|failed|inactive|not_started|started|not_completed"}
##   {"objective": "talk_bong", "quest": "main_02", "done": true}
##   {"phase": "night"} or {"phase": ["dusk", "night"]}  {"time": {"from": 19, "to": 5}}
##   {"festival": true}  {"festival_night": true}  {"weather": "rain"} / ["rain", "storm"]
##   {"location": "tea_stall"}  {"collectible": "memory_03"}  {"territory": "roof_01"}
##   {"dialogue_seen": "ba_tu_morning"}  {"day": 3}  {"buff": "catnip"}  {"equipped": "collar_bell"}
##   {"counter": "knocked_unique", "gte": 5}  {"speaker": "ba_tu"}  {"sheltered": true}
##   {"any": [cond, ...]}  {"all": [...]}  {"not": cond}
## Comparators (numeric keys): gte, gt, lte, lt, eq, ne.

const PRIMARY_KEYS: Array[String] = [
	"flag", "not_flag", "item", "mouth", "mouth_empty", "caps", "attribute", "skill", "not_skill",
	"reputation", "quest", "objective", "level", "stat", "phase", "time", "festival", "festival_night",
	"weather", "location", "collectible", "territory", "dialogue_seen", "day", "buff", "equipped",
	"counter", "speaker", "sheltered", "any", "all", "not",
]
const MODIFIER_KEYS: Array[String] = ["value", "count", "gte", "gt", "lte", "lt", "eq", "ne", "state", "done", "quest"]
const COMPARATORS: Array[String] = ["gte", "gt", "lte", "lt", "eq", "ne"]


static func evaluate(cond: Variant, ctx: Dictionary = {}) -> bool:
	if cond == null:
		return true
	match typeof(cond):
		TYPE_BOOL:
			return cond
		TYPE_STRING, TYPE_STRING_NAME:
			var s := String(cond)
			if s == "":
				return true
			if s.begins_with("!"):
				return not _truthy(GameState.get_flag(StringName(s.substr(1)), false))
			return _truthy(GameState.get_flag(StringName(s), false))
		TYPE_ARRAY:
			for c: Variant in cond:
				if not evaluate(c, ctx):
					return false
			return true
		TYPE_DICTIONARY:
			var d: Dictionary = cond
			for key: Variant in d:
				var k := String(key)
				if k == "quest" and d.has("objective"):
					continue  # "quest" qualifies an objective condition here
				if k in PRIMARY_KEYS and not _eval_key(k, d, ctx):
					return false
			return true
	push_warning("GameConditions: unsupported condition " + str(cond))
	return false


static func _eval_key(k: String, d: Dictionary, ctx: Dictionary) -> bool:
	var v: Variant = d[k]
	match k:
		"flag":
			var fv: Variant = GameState.get_flag(StringName(str(v)), false)
			if _has_comparator(d):
				return _compare(_num(fv), d, 1.0)
			if d.has("value"):
				return _loose_equal(fv, d["value"])
			return _truthy(fv)
		"not_flag":
			return not _truthy(GameState.get_flag(StringName(str(v)), false))
		"item":
			var n := int(d.get("count", 1))
			if _has_comparator(d):
				return _compare(float(GameState.item_count(StringName(str(v)))), d, float(n))
			return GameState.has_item(StringName(str(v)), n)
		"mouth":
			return String(GameState.mouth_item) == str(v)
		"mouth_empty":
			return (GameState.mouth_item == &"") == _truthy(v)
		"caps":
			if _has_comparator(d):
				return _compare(float(GameState.get_caps()), d, 0.0)
			return GameState.get_caps() >= int(_num(v))
		"attribute":
			return _compare(float(GameState.get_effective_attribute(StringName(str(v)))), d, 1.0)
		"skill":
			return GameState.has_skill(StringName(str(v)))
		"not_skill":
			return not GameState.has_skill(StringName(str(v)))
		"reputation":
			return _compare(float(GameState.get_reputation(StringName(str(v)))), d, 0.0)
		"quest":
			return _quest_state_matches(StringName(str(v)), String(d.get("state", "completed")))
		"objective":
			var qid := StringName(str(d.get("quest", ctx.get("quest_id", ""))))
			var done := _truthy(d.get("done", true))
			return QuestManager.is_objective_done(qid, StringName(str(v))) == done
		"level":
			if _has_comparator(d):
				return _compare(float(GameState.level), d, 1.0)
			return GameState.level >= int(_num(v))
		"stat":
			return _compare(GameState.get_stat(StringName(str(v))), d, 0.0)
		"phase":
			var ph := String(TimeOfDay.get_phase())
			if v is Array:
				for p: Variant in v:
					if str(p) == ph:
						return true
				return false
			return ph == str(v)
		"time":
			if v is Dictionary:
				return TimeOfDay.is_hour_between(float(v.get("from", 0.0)), float(v.get("to", 24.0)))
			return true
		"festival":
			return TimeOfDay.is_festival_day() == _truthy(v)
		"festival_night":
			return TimeOfDay.is_festival_night() == _truthy(v)
		"weather":
			var w := String(GameState.get_weather())
			if v is Array:
				for x: Variant in v:
					if str(x) == w:
						return true
				return false
			return w == str(v)
		"location":
			return GameState.is_location_discovered(StringName(str(v)))
		"collectible":
			return GameState.is_collectible_found(StringName(str(v)))
		"territory":
			return GameState.is_territory_marked(StringName(str(v)))
		"dialogue_seen":
			return DialogueManager.has_seen(StringName(str(v)))
		"day":
			if _has_comparator(d):
				return _compare(float(TimeOfDay.day), d, 1.0)
			return TimeOfDay.day >= int(_num(v))
		"buff":
			return GameState.has_buff(StringName(str(v)))
		"equipped":
			for slot: String in ["collar"]:
				if String(GameState.get_equipped(StringName(slot))) == str(v):
					return true
			return false
		"counter":
			return _compare(float(GameState.get_counter(StringName(str(v)))), d, 1.0)
		"speaker":
			return String(ctx.get("speaker_id", "")) == str(v)
		"sheltered":
			return GameState.is_sheltered() == _truthy(v)
		"any":
			if v is Array:
				for c: Variant in v:
					if evaluate(c, ctx):
						return true
				return (v as Array).is_empty()
			return evaluate(v, ctx)
		"all":
			return evaluate(v if v is Array else [v], ctx)
		"not":
			return not evaluate(v, ctx)
	return true


static func _quest_state_matches(qid: StringName, wanted: String) -> bool:
	var st := String(QuestManager.get_state(qid))
	match wanted:
		"not_started":
			return st == "inactive"
		"started":
			return st == "active" or st == "completed"
		"not_completed":
			return st != "completed"
		"available":
			return st == "inactive" and QuestManager.can_start(qid)
	return st == wanted


static func _has_comparator(d: Dictionary) -> bool:
	for c in COMPARATORS:
		if d.has(c):
			return true
	return false


## Compare `value` against the dict's comparators; with none, value >= d.value (or `default`).
static func _compare(value: float, d: Dictionary, default: float) -> bool:
	var any := false
	if d.has("gte"):
		any = true
		if not value >= _num(d["gte"]): return false
	if d.has("gt"):
		any = true
		if not value > _num(d["gt"]): return false
	if d.has("lte"):
		any = true
		if not value <= _num(d["lte"]): return false
	if d.has("lt"):
		any = true
		if not value < _num(d["lt"]): return false
	if d.has("eq"):
		any = true
		if not is_equal_approx(value, _num(d["eq"])): return false
	if d.has("ne"):
		any = true
		if is_equal_approx(value, _num(d["ne"])): return false
	if not any:
		return value >= _num(d.get("value", default))
	return true


static func _num(v: Variant) -> float:
	match typeof(v):
		TYPE_INT, TYPE_FLOAT:
			return float(v)
		TYPE_BOOL:
			return 1.0 if v else 0.0
		TYPE_STRING, TYPE_STRING_NAME:
			return String(v).to_float()
	return 0.0


static func _truthy(v: Variant) -> bool:
	match typeof(v):
		TYPE_NIL:
			return false
		TYPE_BOOL:
			return v
		TYPE_INT, TYPE_FLOAT:
			return v != 0
		TYPE_STRING, TYPE_STRING_NAME:
			return String(v) != "" and String(v) != "false"
	return true


static func _loose_equal(a: Variant, b: Variant) -> bool:
	if typeof(a) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL] and typeof(b) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL]:
		return is_equal_approx(_num(a), _num(b))
	if typeof(a) in [TYPE_STRING, TYPE_STRING_NAME] and typeof(b) in [TYPE_STRING, TYPE_STRING_NAME]:
		return String(a) == String(b)
	if a == null:
		return not _truthy(b)
	return a == b


# --- human-readable requirements (for locked choices / skill tooltips) ----------------------------

## Translated, comma-separated description of what the player needs (flags are not revealed).
static func describe(cond: Variant) -> String:
	var parts: PackedStringArray = []
	_describe_into(cond, parts)
	return ", ".join(parts)


static func _describe_into(cond: Variant, parts: PackedStringArray) -> void:
	if cond is Array:
		for c: Variant in cond:
			_describe_into(c, parts)
		return
	if not cond is Dictionary:
		return
	var d: Dictionary = cond
	for key: Variant in d:
		var k := String(key)
		var v: Variant = d[key]
		match k:
			"attribute":
				parts.append(_t("REQ_ATTRIBUTE").format({"attribute": _t("ATTR_" + str(v).to_upper()),
					"value": int(_num(d.get("gte", d.get("value", 1))))}))
			"skill":
				parts.append(_t("REQ_SKILL").format({"skill": _t(String(GameState.get_skill_def(StringName(str(v))).get("name_key", str(v))))}))
			"item":
				parts.append(_t("REQ_ITEM").format({"item": GameState.get_item_name(StringName(str(v))), "count": int(d.get("count", 1))}))
			"mouth":
				parts.append(_t("REQ_MOUTH").format({"item": GameState.get_item_name(StringName(str(v)))}))
			"caps":
				parts.append(_t("REQ_CAPS").format({"count": int(_num(d.get("gte", v)))}))
			"reputation":
				parts.append(_t("REQ_REPUTATION").format({"faction": _t("FACTION_" + str(v).to_upper()),
					"value": int(_num(d.get("gte", d.get("value", 0))))}))
			"level":
				parts.append(_t("REQ_LEVEL").format({"level": int(_num(d.get("gte", v)))}))
			"phase":
				var phases: Array = v if v is Array else [v]
				var names: PackedStringArray = []
				for p: Variant in phases:
					names.append(_t("PHASE_" + str(p).to_upper()))
				parts.append(_t("REQ_PHASE").format({"phase": " / ".join(names)}))
			"time":
				if v is Dictionary:
					parts.append(_t("REQ_TIME").format({"from": "%02d:00" % int(_num(v.get("from", 0))), "to": "%02d:00" % int(_num(v.get("to", 24)))}))
			"festival", "festival_night":
				if _truthy(v):
					parts.append(_t("REQ_FESTIVAL"))
			"any":
				var sub: PackedStringArray = []
				for c: Variant in (v if v is Array else [v]):
					var s := describe(c)
					if s != "":
						sub.append(s)
				if not sub.is_empty():
					parts.append((" " + _t("REQ_OR") + " ").join(sub))
			"all":
				_describe_into(v, parts)


static func _t(key: String) -> String:
	return String(TranslationServer.translate(StringName(key)))


# --- validation --------------------------------------------------------------------------------

## Returns a list of problems with a condition (unknown keys, bad shapes). Empty = valid.
static func validate(cond: Variant, where: String = "") -> PackedStringArray:
	var errs: PackedStringArray = []
	_validate_into(cond, where, errs)
	return errs


static func _validate_into(cond: Variant, where: String, errs: PackedStringArray) -> void:
	if cond == null or cond is bool or cond is String:
		return
	if cond is Array:
		for c: Variant in cond:
			_validate_into(c, where, errs)
		return
	if not cond is Dictionary:
		errs.append("%s: condition must be dict/array/string, got %s" % [where, str(cond)])
		return
	var d: Dictionary = cond
	var primaries := 0
	for key: Variant in d:
		var k := String(key)
		if k == "quest" and d.has("objective"):
			continue
		if k in PRIMARY_KEYS:
			primaries += 1
			if k in ["any", "all", "not"]:
				_validate_into(d[key], where, errs)
		elif k not in MODIFIER_KEYS and k not in ["from", "to"]:
			errs.append("%s: unknown condition key '%s'" % [where, k])
	if primaries == 0 and not d.is_empty():
		errs.append("%s: condition has no primary key: %s" % [where, str(d)])
