extends Node
## QuestManager — data-driven quests (owner: systems). Definitions: data/quests/<id>.json,
## format in data/quests/_schema.md.
##
## Objective types: reach_location, collect_item, deliver_item, talk_to, interact, mark_territory,
## nap, knock_objects, catch_prey, flag_set, time_window, event (generic), condition (generic).
## Objectives can be optional / hidden, gated by "when" conditions or a "time_window", grouped
## into stages (sequential by default). Quests have prerequisites, rewards, next-quest chaining,
## auto-start, fail conditions, tracking and a target-position resolver for the HUD marker.
## Progress comes from GameEvents (auto) and report(event, data) (manual).

const STATE_INACTIVE := &"inactive"
const STATE_ACTIVE := &"active"
const STATE_COMPLETED := &"completed"
const STATE_FAILED := &"failed"
const OBJECTIVE_TYPES: Array[String] = [
	"reach_location", "collect_item", "deliver_item", "talk_to", "interact", "mark_territory", "nap",
	"knock_objects", "catch_prey", "flag_set", "time_window", "event", "condition",
]
## Objective types completed from game state rather than events (count is always 1).
const STATE_TYPES: Array[String] = ["flag_set", "time_window", "condition"]
const SINGLE_TYPES: Array[String] = ["reach_location", "talk_to", "flag_set", "time_window", "condition"]
const CATEGORY_ORDER := {"main": 0, "trial": 1, "side": 2, "misc": 3}

var quest_dirs: PackedStringArray = ["res://data/quests"]
var autosave_on_progress := true
var reach_poll_interval := 0.5
var default_reach_radius := 3.0
## Toasts for quest start/objective/completion (GameEvents.notify).
var notifications_enabled := true

var _defs: Dictionary = {}           # id -> normalized definition
var _rt: Dictionary = {}             # id -> runtime state
var _tracked: StringName = &""
var _pending_starts: Dictionary = {} # chained quest ids waiting for prerequisites
var _poll_t := 0.0
var _last_interact_key := ""
var _last_interact_frame := -1
var _evaluating := false
var _dirty := false
var _target_cache: Dictionary = {}   # cache key -> {"node": WeakRef, "msec": int}


func _ready() -> void:
	reload_definitions()
	GameState.register_save_provider("quests", self)
	GameEvents.location_discovered.connect(func(id: StringName, _n: String) -> void: report(&"reach_location", {"location_id": id}))
	GameEvents.area_entered.connect(func(id: StringName) -> void: report(&"reach_location", {"location_id": id}))
	GameEvents.item_picked_up.connect(func(id: StringName, n: int) -> void: report(&"collect_item", {"item_id": id, "amount": n}))
	GameEvents.item_delivered.connect(func(id: StringName, to: StringName) -> void: report(&"deliver_item", {"item_id": id, "recipient_id": to}))
	GameEvents.interacted.connect(_on_interacted)
	GameEvents.territory_marked.connect(func(id: StringName) -> void: report(&"mark_territory", {"spot_id": id}))
	GameEvents.cat_napped.connect(func(id: StringName, h: float) -> void: report(&"nap", {"spot_id": id, "hours": h}))
	GameEvents.object_knocked_off.connect(func(_o: Node3D, id: StringName, h: float) -> void: report(&"knock_object", {"object_id": id, "height": h}))
	GameEvents.prey_caught.connect(func(kind: StringName) -> void: report(&"catch_prey", {"prey_kind": kind}))
	GameEvents.dialogue_started.connect(func(did: StringName, sp: StringName) -> void: report(&"talk_to", {"npc_id": sp, "dialogue_id": did}))
	GameEvents.collectible_found.connect(func(id: StringName) -> void: report(&"collectible", {"collectible_id": id}))
	GameEvents.inventory_changed.connect(func(_i: StringName, _c: int) -> void: _request_evaluate())
	GameEvents.flag_changed.connect(func(_f: StringName, _v: Variant) -> void: _request_evaluate())
	GameEvents.level_up.connect(func(_l: int) -> void: _request_evaluate())
	GameEvents.skill_unlocked.connect(func(_s: StringName) -> void: _request_evaluate())
	GameEvents.reputation_changed.connect(func(_f: StringName, _v: int) -> void: _request_evaluate())
	GameEvents.attribute_changed.connect(func(_a: StringName, _v: int) -> void: _request_evaluate())
	GameEvents.time_tick.connect(func(_h: float, _d: int) -> void: _request_evaluate())
	GameEvents.phase_of_day_changed.connect(func(_p: StringName) -> void: _request_evaluate())
	GameEvents.mouth_item_changed.connect(func(_i: StringName) -> void: _target_cache.clear())
	GameEvents.counter_changed.connect(func(_c: StringName, _v: int) -> void: _request_evaluate())


func _process(delta: float) -> void:
	_poll_t -= delta
	if _poll_t > 0.0:
		return
	_poll_t = reach_poll_interval
	_poll_reach_objectives()


# =============================================================================================
# Definitions
# =============================================================================================

func reload_definitions() -> void:
	_defs.clear()
	for dir in quest_dirs:
		load_quest_dir(dir)


## Loads every <id>.json in `path` (files starting with "_" are skipped). Returns count loaded.
func load_quest_dir(path: String) -> int:
	var d := DirAccess.open(path)
	if d == null:
		return 0
	var n := 0
	for f in d.get_files():
		if f.ends_with(".json") and not f.begins_with("_"):
			var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path.path_join(f)))
			if parsed is Dictionary:
				if register_quest(parsed, path.path_join(f)):
					n += 1
			else:
				push_error("QuestManager: invalid JSON " + path.path_join(f))
	return n


## Registers a quest definition (also used by tests / mods). Returns false if unusable.
func register_quest(def: Dictionary, source: String = "") -> bool:
	var d := _normalize(def, source)
	var errs := validate_quest(d)
	for e in errs:
		push_warning("QuestManager %s: %s" % [source if source != "" else d.get("id", "?"), e])
	if String(d["id"]) == "" or (d["objectives"] as Array).is_empty():
		return false
	_defs[String(d["id"])] = d
	return true


func unregister_quest(id: StringName) -> void:
	_defs.erase(String(id))
	_rt.erase(String(id))


func clear_definitions() -> void:
	_defs.clear()


func has_quest(id: StringName) -> bool:
	return _defs.has(String(id))


func get_quest_ids() -> PackedStringArray:
	return PackedStringArray(_defs.keys())


func get_quest_def(id: StringName) -> Dictionary:
	return _defs.get(String(id), {})


func _normalize(def: Dictionary, source: String) -> Dictionary:
	var d := def.duplicate(true)
	var id := String(d.get("id", source.get_file().get_basename()))
	d["id"] = id
	var up := id.to_upper()
	d["title_key"] = String(d.get("title_key", "QUEST_%s_TITLE" % up))
	d["desc_key"] = String(d.get("desc_key", "QUEST_%s_DESC" % up))
	d["category"] = String(d.get("category", "side"))
	d["sequential"] = bool(d.get("sequential", true))
	d["auto_start"] = bool(d.get("auto_start", false))
	d["track_on_start"] = bool(d.get("track_on_start", d["category"] == "main"))
	d["retry_on_fail"] = bool(d.get("retry_on_fail", false))
	d["prerequisites"] = d.get("prerequisites", {}) if d.get("prerequisites", {}) is Dictionary else {}
	d["rewards"] = d.get("rewards", {}) if d.get("rewards", {}) is Dictionary else {}
	var nxt: Variant = d.get("next", [])
	if nxt is String:
		nxt = [nxt] if nxt != "" else []
	d["next"] = nxt if nxt is Array else []
	var objs: Array = []
	var raw: Variant = d.get("objectives", [])
	if raw is Array:
		var i := 0
		for o: Variant in raw:
			if not o is Dictionary:
				continue
			var od: Dictionary = (o as Dictionary).duplicate(true)
			var oid := String(od.get("id", "obj_%d" % i))
			od["id"] = oid
			od["type"] = String(od.get("type", "event"))
			od["count"] = 1 if od["type"] in SINGLE_TYPES else maxi(1, int(od.get("count", 1)))
			od["stage"] = int(od.get("stage", i if d["sequential"] else 0))
			od["optional"] = bool(od.get("optional", false))
			od["hidden"] = bool(od.get("hidden", false))
			od["desc_key"] = String(od.get("desc_key", "QUEST_%s_OBJ_%s" % [up, oid.to_upper()]))
			objs.append(od)
			i += 1
	d["objectives"] = objs
	return d


## Validation of a (normalized or raw) quest definition. Empty array = valid.
func validate_quest(def: Dictionary) -> PackedStringArray:
	var errs: PackedStringArray = []
	var id := String(def.get("id", ""))
	if id == "":
		errs.append("missing id")
	var objs: Variant = def.get("objectives", [])
	if not objs is Array or (objs as Array).is_empty():
		errs.append("no objectives")
		return errs
	var ids := {}
	var required := 0
	for o: Variant in objs:
		if not o is Dictionary:
			errs.append("objective is not a dictionary")
			continue
		var od: Dictionary = o
		var oid := String(od.get("id", ""))
		var t := String(od.get("type", ""))
		if ids.has(oid):
			errs.append("duplicate objective id '%s'" % oid)
		ids[oid] = true
		if not bool(od.get("optional", false)):
			required += 1
		if t not in OBJECTIVE_TYPES:
			errs.append("objective '%s': unknown type '%s'" % [oid, t])
			continue
		var need: Array = []
		match t:
			"reach_location": need = ["target"]
			"collect_item": need = ["item"]
			"deliver_item": need = ["item", "to"]
			"talk_to": need = ["npc"]
			"flag_set": need = ["flag"]
			"time_window": need = ["from", "to"]
			"event": need = ["event"]
			"condition": need = ["if"]
		for k: String in need:
			if not od.has(k):
				errs.append("objective '%s' (%s): missing '%s'" % [oid, t, k])
		if t in ["collect_item", "deliver_item"] and od.has("item") and not GameState.item_exists(StringName(str(od["item"]))):
			errs.append("objective '%s': unknown item '%s'" % [oid, str(od["item"])])
		if od.has("when"):
			errs.append_array(GameConditions.validate(od["when"], "%s/%s.when" % [id, oid]))
		if od.has("if"):
			errs.append_array(GameConditions.validate(od["if"], "%s/%s.if" % [id, oid]))
		errs.append_array(GameEffects.validate(od.get("effects", []), "%s/%s.effects" % [id, oid]))
	if required == 0:
		errs.append("quest has no required objective")
	var pre: Variant = def.get("prerequisites", {})
	if pre is Dictionary and (pre as Dictionary).has("if"):
		errs.append_array(GameConditions.validate(pre["if"], id + ".prerequisites"))
	var rw: Variant = def.get("rewards", {})
	if rw is Dictionary:
		var items: Variant = (rw as Dictionary).get("items", {})
		if items is Dictionary:
			for it: String in items:
				if not GameState.item_exists(StringName(it)):
					errs.append("reward: unknown item '%s'" % it)
		errs.append_array(GameEffects.validate((rw as Dictionary).get("effects", []), id + ".rewards"))
	if def.has("fail_if"):
		errs.append_array(GameConditions.validate(def["fail_if"], id + ".fail_if"))
	errs.append_array(GameEffects.validate(def.get("on_start", []), id + ".on_start"))
	return errs


# =============================================================================================
# State queries
# =============================================================================================

func get_state(id: StringName) -> StringName:
	var r: Dictionary = _rt.get(String(id), {})
	return StringName(String(r.get("state", STATE_INACTIVE)))


func is_active(id: StringName) -> bool:
	return get_state(id) == STATE_ACTIVE


func is_completed(id: StringName) -> bool:
	return get_state(id) == STATE_COMPLETED


func is_failed(id: StringName) -> bool:
	return get_state(id) == STATE_FAILED


func get_active_quests() -> Array[StringName]:
	var out: Array[StringName] = []
	for id: String in _rt:
		if String(_rt[id].get("state", "")) == "active" and _defs.has(id):
			out.append(StringName(id))
	out.sort_custom(func(a: StringName, b: StringName) -> bool:
		var ca: int = CATEGORY_ORDER.get(String(_defs[String(a)]["category"]), 9)
		var cb: int = CATEGORY_ORDER.get(String(_defs[String(b)]["category"]), 9)
		if ca != cb:
			return ca < cb
		return float(_rt[String(a)].get("started_at", 0.0)) < float(_rt[String(b)].get("started_at", 0.0)))
	return out


func get_completed_quests() -> Array[StringName]:
	var out: Array[StringName] = []
	for id: String in _rt:
		if String(_rt[id].get("state", "")) == "completed":
			out.append(StringName(id))
	return out


func prerequisites_met(id: StringName) -> bool:
	var def := get_quest_def(id)
	if def.is_empty():
		return false
	var p: Dictionary = def["prerequisites"]
	for q: Variant in p.get("quests", []):
		if not is_completed(StringName(str(q))):
			return false
	var flags: Variant = p.get("flags", {})
	if flags is Dictionary:
		for f: String in flags:
			if not GameConditions._loose_equal(GameState.get_flag(StringName(f), null), flags[f]):
				return false
	if GameState.level < int(p.get("level", 1)):
		return false
	if p.has("if") and not GameConditions.evaluate(p["if"], {"quest_id": String(id)}):
		return false
	return true


func can_start(id: StringName) -> bool:
	var def := get_quest_def(id)
	if def.is_empty():
		return false
	var st := get_state(id)
	if st == STATE_ACTIVE or st == STATE_COMPLETED:
		return false
	if st == STATE_FAILED and not bool(def["retry_on_fail"]):
		return false
	return prerequisites_met(id)


## UI view of a quest: definition + runtime merged, texts translated.
func get_quest(id: StringName) -> Dictionary:
	var def := get_quest_def(id)
	if def.is_empty():
		return {}
	var view := {
		"id": String(id),
		"title": tr(String(def["title_key"])),
		"description": tr(String(def["desc_key"])),
		"category": def["category"],
		"giver": String(def.get("giver", "")),
		"state": String(get_state(id)),
		"tracked": _tracked == id,
		"rewards": def["rewards"].duplicate(true),
		"objectives": get_objectives(id),
	}
	return view


## Objective views: id, type, text, progress, required, done, active, optional, hidden, missed.
func get_objectives(id: StringName) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var def := get_quest_def(id)
	if def.is_empty():
		return out
	var objs: Array = def["objectives"]
	for i in objs.size():
		var o: Dictionary = objs[i]
		var r := _obj_rt(id, String(o["id"]))
		var progress := int(r.get("progress", 0))
		var hidden := bool(o["hidden"]) and not bool(r.get("revealed", false)) and not bool(r.get("done", false))
		out.append({
			"id": String(o["id"]), "type": String(o["type"]),
			"text": tr(String(o["desc_key"])).format({"count": int(o["count"]), "progress": progress}),
			"progress": progress, "required": int(o["count"]), "done": bool(r.get("done", false)),
			"active": _is_obj_active(id, i), "optional": bool(o["optional"]), "hidden": hidden,
			"missed": bool(r.get("missed", false)),
		})
	return out


func is_objective_done(quest_id: StringName, objective_id: StringName) -> bool:
	return bool(_obj_rt(quest_id, String(objective_id)).get("done", false))


func is_objective_active(quest_id: StringName, objective_id: StringName) -> bool:
	var i := _obj_index(quest_id, String(objective_id))
	return i >= 0 and _is_obj_active(quest_id, i)


func get_objective_progress(quest_id: StringName, objective_id: StringName) -> int:
	return int(_obj_rt(quest_id, String(objective_id)).get("progress", 0))


# =============================================================================================
# Lifecycle
# =============================================================================================

func start_quest(id: StringName, force: bool = false) -> bool:
	var k := String(id)
	var def := get_quest_def(id)
	if def.is_empty():
		push_warning("QuestManager.start_quest: unknown quest " + k)
		return false
	var st := get_state(id)
	if st == STATE_ACTIVE or st == STATE_COMPLETED:
		return false
	if st == STATE_FAILED and not bool(def["retry_on_fail"]) and not force:
		return false
	if not force and not prerequisites_met(id):
		return false
	var objs := {}
	for o: Dictionary in def["objectives"]:
		objs[String(o["id"])] = {"progress": 0, "done": false, "seen": [], "revealed": false, "activated": false, "missed": false}
	_rt[k] = {"state": "active", "objectives": objs, "started_day": TimeOfDay.day,
		"started_at": TimeOfDay.get_absolute_minutes(), "finished_day": -1}
	_pending_starts.erase(k)
	GameEvents.quest_started.emit(id)
	_notify("NOTIFY_QUEST_STARTED", {"title": tr(String(def["title_key"]))}, &"quest")
	GameEffects.apply(def.get("on_start", []), {"quest_id": k})
	if bool(def["track_on_start"]) or _tracked == &"" or not is_active(_tracked):
		track(id)
	_activate_new_objectives(id)
	_request_evaluate()
	_autosave("quest_started")
	return true


## Completes the quest now (remaining required objectives are marked done) and grants rewards.
func complete_quest(id: StringName) -> bool:
	if not is_active(id):
		return false
	var r: Dictionary = _rt[String(id)]
	for o: Dictionary in get_quest_def(id)["objectives"]:
		if not bool(o["optional"]):
			var orr: Dictionary = r["objectives"][String(o["id"])]
			orr["done"] = true
			orr["progress"] = int(o["count"])
	_complete(id)
	return true


func fail_quest(id: StringName) -> bool:
	if not is_active(id):
		return false
	var r: Dictionary = _rt[String(id)]
	r["state"] = "failed"
	r["finished_day"] = TimeOfDay.day
	GameEffects.apply(get_quest_def(id).get("on_fail", []), {"quest_id": String(id)})
	GameEvents.quest_failed.emit(id)
	_notify("NOTIFY_QUEST_FAILED", {"title": tr(String(get_quest_def(id)["title_key"]))}, &"quest")
	if _tracked == id:
		_tracked = &""
		_auto_track()
	return true


## Forget all progress on a quest (debug / repeatable side activities).
func reset_quest(id: StringName) -> void:
	_rt.erase(String(id))
	if _tracked == id:
		_tracked = &""
		GameEvents.tracked_quest_changed.emit(&"")


func advance_objective(quest_id: StringName, objective_id: StringName, amount: int = 1) -> bool:
	var i := _obj_index(quest_id, String(objective_id))
	if i < 0 or not _is_obj_active(quest_id, i):
		return false
	_progress(quest_id, i, amount)
	return true


func complete_objective(quest_id: StringName, objective_id: StringName) -> bool:
	var i := _obj_index(quest_id, String(objective_id))
	if i < 0 or not is_active(quest_id) or bool(_obj_rt(quest_id, String(objective_id)).get("done", false)):
		return false
	_progress(quest_id, i, 0, int(get_quest_def(quest_id)["objectives"][i]["count"]))
	return true


# =============================================================================================
# Tracking & target markers
# =============================================================================================

func track(id: StringName) -> bool:
	if id != &"" and not is_active(id):
		return false
	if _tracked != id:
		_tracked = id
		_target_cache.clear()
		GameEvents.tracked_quest_changed.emit(id)
	return true


func untrack() -> void:
	track(&"")


func get_tracked() -> StringName:
	return _tracked


## First visible, active, unfinished objective of the tracked quest ({} if none).
func get_tracked_objective() -> Dictionary:
	if _tracked == &"" or not is_active(_tracked):
		return {}
	for o in get_objectives(_tracked):
		if o["active"] and not o["done"] and not o["hidden"]:
			return o
	return {}


## World position of the tracked quest's current objective target, Vector3.INF if none.
## Resolves target ids via nodes in group "quest_target" (meta/property target_id), then
## "location" markers (meta location_id), NPCs (group "npc", npc_id) and interactables.
func get_tracked_target_position() -> Vector3:
	if _tracked == &"" or not is_active(_tracked):
		return Vector3.INF
	# A save can track a quest whose JSON no longer exists.
	var objs: Array = get_quest_def(_tracked).get("objectives", [])
	for i in objs.size():
		var o: Dictionary = objs[i]
		if not _is_obj_active(_tracked, i):
			continue
		var r := _obj_rt(_tracked, String(o["id"]))
		if bool(o["hidden"]) and not bool(r.get("revealed", false)):
			continue
		var pos := get_objective_target_position(_tracked, StringName(String(o["id"])))
		if pos != Vector3.INF:
			return pos
	return Vector3.INF


func get_objective_target_position(quest_id: StringName, objective_id: StringName) -> Vector3:
	var i := _obj_index(quest_id, String(objective_id))
	if i < 0:
		return Vector3.INF
	var o: Dictionary = get_quest_def(quest_id)["objectives"][i]
	var cache_key := "%s/%s/%s" % [quest_id, objective_id, String(GameState.mouth_item)]
	var c: Dictionary = _target_cache.get(cache_key, {})
	if not c.is_empty() and Time.get_ticks_msec() - int(c["msec"]) < 500:
		var cached: Variant = (c["node"] as WeakRef).get_ref()
		if cached is Node3D and (cached as Node3D).is_inside_tree():
			return (cached as Node3D).global_position
	var node := _resolve_objective_node(quest_id, o)
	if node == null:
		_target_cache.erase(cache_key)
		return Vector3.INF
	_target_cache[cache_key] = {"node": weakref(node), "msec": Time.get_ticks_msec()}
	return node.global_position


func _resolve_objective_node(quest_id: StringName, o: Dictionary) -> Node3D:
	var explicit: Variant = o.get("target_id", null)
	if explicit != null:
		var ids: Array = explicit if explicit is Array else [explicit]
		var best: Node3D = null
		for tid: Variant in ids:
			var n := find_target_node(StringName(str(tid)))
			if n != null and (best == null or _dist_to_player(n) < _dist_to_player(best)):
				best = n
		return best
	var r := _obj_rt(quest_id, String(o["id"]))
	match String(o["type"]):
		"reach_location":
			return find_target_node(StringName(str(o["target"])))
		"talk_to":
			return find_target_node(StringName(str(o["npc"])))
		"interact":
			return find_target_node(StringName(str(o.get("target", "")))) if String(o.get("target", "")) != "" else null
		"deliver_item":
			var item := StringName(str(o["item"]))
			if GameState.has_item(item):
				return find_target_node(StringName(str(o["to"])))
			return _nearest_matching(&"interactable", func(n: Node) -> bool: return _prop(n, "item_id") == String(item))
		"collect_item":
			var item2 := String(o["item"])
			return _nearest_matching(&"interactable", func(n: Node) -> bool: return _prop(n, "item_id") == item2)
		"nap":
			var spot := String(o.get("spot", ""))
			if spot != "":
				return find_target_node(StringName(spot))
			return _nearest_matching(&"interactable", func(n: Node) -> bool: return n is NapSpot)
		"mark_territory":
			var spots: Array = o.get("spots", [])
			var seen: Array = r.get("seen", [])
			return _nearest_matching(&"interactable", func(n: Node) -> bool:
				if not n is TerritorySpot:
					return false
				var sid := _prop(n, "spot_id")
				return not GameState.is_territory_marked(StringName(sid)) and sid not in seen and (spots.is_empty() or sid in spots))
		"knock_objects":
			var seen2: Array = r.get("seen", [])
			return _nearest_matching(&"pushable", func(n: Node) -> bool: return _prop(n, "object_id") not in seen2)
		"catch_prey":
			var prey := String(o.get("prey", ""))
			return _nearest_matching(&"prey", func(n: Node) -> bool:
				return prey == "" or str(n.get_meta(&"prey_kind", _prop(n, "prey_kind"))) == prey)
	return null


## Finds the node (nearest to the player) representing a target id.
func find_target_node(target_id: StringName) -> Node3D:
	if target_id == &"":
		return null
	var t := String(target_id)
	var n := _nearest_matching(&"quest_target", func(x: Node) -> bool:
		return str(x.get_meta(&"target_id", "")) == t or _prop(x, "target_id") == t)
	if n != null:
		return n
	n = _nearest_matching(&"location", func(x: Node) -> bool: return str(x.get_meta(&"location_id", "")) == t)
	if n != null:
		return n
	n = _nearest_matching(&"npc", func(x: Node) -> bool:
		return str(x.get_meta(&"npc_id", "")) == t or _prop(x, "npc_id") == t)
	if n != null:
		return n
	return _nearest_matching(&"interactable", func(x: Node) -> bool:
		for p in ["speaker_id", "spot_id", "collectible_id", "source_id", "post_id", "location_id"]:
			if _prop(x, p) == t:
				return true
		return false)


func _nearest_matching(group: StringName, pred: Callable) -> Node3D:
	if not is_inside_tree():
		return null
	var best: Node3D = null
	var best_d := INF
	for n in get_tree().get_nodes_in_group(group):
		var n3 := n as Node3D
		if n3 == null or not n3.is_inside_tree() or not pred.call(n3):
			continue
		var d := _dist_to_player(n3)
		if d < best_d:
			best_d = d
			best = n3
	return best


func _dist_to_player(n: Node3D) -> float:
	var p := GameState.get_player()
	if p == null:
		return 0.0
	return p.global_position.distance_to(n.global_position)


static func _prop(n: Object, prop: String) -> String:
	if prop in n:
		return str(n.get(prop))
	return ""


# =============================================================================================
# Delivery
# =============================================================================================

## Called by Talkable: if Cam carries an item an active deliver objective wants for this
## recipient, hand it over. Returns true if something was delivered.
func try_deliver(recipient_id: StringName) -> bool:
	for qid in get_active_quests():
		var objs: Array = get_quest_def(qid)["objectives"]
		for i in objs.size():
			var o: Dictionary = objs[i]
			if String(o["type"]) != "deliver_item" or not _is_obj_active(qid, i):
				continue
			if String(o["to"]) != String(recipient_id) or not _gate_ok(o, String(qid)):
				continue
			var item := StringName(str(o["item"]))
			var from_mouth := bool(o.get("from_mouth", true))
			if (from_mouth and GameState.mouth_item == item) or (not from_mouth and GameState.has_item(item)):
				return deliver_item(item, recipient_id)
	return false


## Gives `item_id` to `recipient_id`: removes it (unless the matching objective says
## "consume": false) and emits GameEvents.item_delivered (which advances deliver objectives).
func deliver_item(item_id: StringName, recipient_id: StringName) -> bool:
	if not GameState.has_item(item_id):
		return false
	var consume := true
	for qid in get_active_quests():
		for o: Dictionary in get_quest_def(qid)["objectives"]:
			if String(o["type"]) == "deliver_item" and String(o["item"]) == String(item_id) and String(o["to"]) == String(recipient_id):
				consume = bool(o.get("consume", true))
	if consume:
		GameState.remove_item(item_id, 1)
	GameEvents.item_delivered.emit(item_id, recipient_id)
	return true


# =============================================================================================
# Progress
# =============================================================================================

## Report a gameplay event. Built-in events (also fed automatically from GameEvents):
## reach_location{location_id} collect_item{item_id,amount} deliver_item{item_id,recipient_id}
## talk_to{npc_id,dialogue_id} interact{verb,target_id} mark_territory{spot_id} nap{spot_id,hours}
## knock_object{object_id,height} catch_prey{prey_kind}; any other name feeds "event" objectives.
func report(event: StringName, data: Dictionary = {}) -> void:
	var ev := String(event)
	if ev == "knock_objects":
		ev = "knock_object"
	for qid in get_active_quests():
		var objs: Array = get_quest_def(qid)["objectives"]
		# Snapshot: objectives activated by this very event must not consume it as well.
		var active_now: Array[int] = []
		for i in objs.size():
			if _is_obj_active(qid, i):
				active_now.append(i)
		for i in active_now:
			if not is_active(qid) or not _is_obj_active(qid, i):
				continue
			var amount := _match_event(qid, objs[i], ev, data)
			if amount > 0:
				_progress(qid, i, amount)


func _match_event(qid: StringName, o: Dictionary, ev: String, data: Dictionary) -> int:
	var t := String(o["type"])
	if t in STATE_TYPES:
		return 0
	var r := _obj_rt(qid, String(o["id"]))
	var amount := 0
	match t:
		"reach_location":
			if ev == "reach_location" and str(data.get("location_id", "")) == str(o["target"]):
				amount = 1
		"collect_item":
			if String(o.get("mode", "inventory")) == "pickup" and ev == "collect_item" and str(data.get("item_id", "")) == str(o["item"]):
				amount = maxi(1, int(data.get("amount", 1)))
		"deliver_item":
			if ev == "deliver_item" and str(data.get("item_id", "")) == str(o["item"]) \
					and (str(o.get("to", "")) == "" or str(data.get("recipient_id", "")) == str(o["to"])):
				amount = 1
		"talk_to":
			if ev == "talk_to" and str(data.get("npc_id", "")) == str(o["npc"]) \
					and (str(o.get("dialogue", "")) == "" or str(data.get("dialogue_id", "")) == str(o["dialogue"])):
				amount = 1
		"interact":
			if ev == "interact" and (str(o.get("verb", "")) == "" or str(data.get("verb", "")) == str(o["verb"])) \
					and (str(o.get("target", "")) == "" or str(data.get("target_id", "")) == str(o["target"])):
				amount = _unique(o, r, str(data.get("target_id", "")), bool(o.get("unique", false)))
		"mark_territory":
			if ev == "mark_territory":
				var spot := str(data.get("spot_id", ""))
				var spots: Array = o.get("spots", [])
				if spots.is_empty() or spot in spots:
					amount = _unique(o, r, spot, true)
		"nap":
			if ev == "nap" and (str(o.get("spot", "")) == "" or str(data.get("spot_id", "")) == str(o["spot"])) \
					and float(data.get("hours", 0.0)) >= float(o.get("min_hours", 0.0)):
				amount = _unique(o, r, str(data.get("spot_id", "")), bool(o.get("unique", false)))
		"knock_objects":
			if ev == "knock_object" and float(data.get("height", 99.0)) >= float(o.get("min_height", 0.0)):
				amount = _unique(o, r, str(data.get("object_id", "")), bool(o.get("unique", true)))
		"catch_prey":
			if ev == "catch_prey" and (str(o.get("prey", "")) == "" or str(data.get("prey_kind", "")) == str(o["prey"])):
				amount = 1
		"event":
			if ev == str(o["event"]) and _data_matches(data, o.get("match", {})):
				amount = maxi(1, int(data.get("amount", 1)))
	if amount > 0 and not _gate_ok(o, String(qid)):
		return 0
	return amount


## Counts `key` only once per objective when unique; records it in the runtime "seen" list.
func _unique(_o: Dictionary, r: Dictionary, key: String, unique: bool) -> int:
	if not unique or key == "":
		return 1
	var seen: Array = r.get("seen", [])
	if key in seen:
		return 0
	seen.append(key)
	r["seen"] = seen
	return 1


static func _data_matches(data: Dictionary, match_d: Variant) -> bool:
	if not match_d is Dictionary:
		return true
	for k: Variant in match_d:
		if not data.has(k) or str(data[k]) != str(match_d[k]):
			return false
	return true


## Objective gating: "when" condition and/or "time_window" {from,to} (+ "festival": true).
func _gate_ok(o: Dictionary, qid: String) -> bool:
	if o.has("when") and not GameConditions.evaluate(o["when"], {"quest_id": qid}):
		return false
	var tw: Variant = o.get("time_window", null)
	if tw is Dictionary and not TimeOfDay.is_hour_between(float(tw.get("from", 0.0)), float(tw.get("to", 24.0))):
		return false
	if bool(o.get("festival", false)) and not TimeOfDay.is_festival_day():
		return false
	return true


func _progress(qid: StringName, i: int, amount: int, set_value: int = -1) -> void:
	if not is_active(qid):
		return
	var o: Dictionary = get_quest_def(qid)["objectives"][i]
	var r := _obj_rt(qid, String(o["id"]))
	if r.is_empty() or bool(r.get("done", false)):
		return
	var req := int(o["count"])
	var newp := set_value if set_value >= 0 else int(r.get("progress", 0)) + amount
	newp = clampi(newp, 0, req)
	if newp == int(r.get("progress", 0)) and newp < req:
		return
	r["progress"] = newp
	if bool(o["hidden"]) and not bool(r.get("revealed", false)) and newp > 0:
		r["revealed"] = true
		GameEvents.quest_objective_revealed.emit(qid, StringName(String(o["id"])))
	GameEvents.quest_objective_updated.emit(qid, StringName(String(o["id"])), newp, req)
	if newp >= req:
		_finish_objective(qid, i)


func _finish_objective(qid: StringName, i: int) -> void:
	var def := get_quest_def(qid)
	var o: Dictionary = def["objectives"][i]
	var r := _obj_rt(qid, String(o["id"]))
	r["done"] = true
	r["revealed"] = true
	_target_cache.clear()
	_apply_rewards(o.get("rewards", {}), qid)
	GameEffects.apply(o.get("effects", []), {"quest_id": String(qid)})
	if not is_active(qid):
		return  # an effect completed/failed the quest
	if _all_required_done(qid):
		_complete(qid)
	else:
		_notify("NOTIFY_OBJECTIVE_DONE", {"objective": tr(String(o["desc_key"])).format({"count": int(o["count"]), "progress": int(o["count"])})}, &"objective")
		_activate_new_objectives(qid)
		_request_evaluate()
		_autosave("objective")


func _complete(qid: StringName) -> void:
	var k := String(qid)
	var def := get_quest_def(qid)
	var r: Dictionary = _rt[k]
	r["state"] = "completed"
	r["finished_day"] = TimeOfDay.day
	for o: Dictionary in def["objectives"]:
		var orr: Dictionary = r["objectives"].get(String(o["id"]), {})
		if bool(o["optional"]) and not bool(orr.get("done", false)):
			orr["missed"] = true
	_apply_rewards(def["rewards"], qid)
	GameEvents.quest_completed.emit(qid)
	_notify("NOTIFY_QUEST_COMPLETED", {"title": tr(String(def["title_key"]))}, &"quest_complete")
	if _tracked == qid:
		_tracked = &""
	for n: Variant in def["next"]:
		_pending_starts[str(n)] = true
	_try_pending_starts()
	if _tracked == &"":
		_auto_track()
	if _tracked == &"":
		GameEvents.tracked_quest_changed.emit(&"")
	_request_evaluate()
	_autosave("quest_completed")


func _apply_rewards(rw: Variant, qid: StringName) -> void:
	if not rw is Dictionary or (rw as Dictionary).is_empty():
		return
	var d: Dictionary = rw
	if int(d.get("xp", 0)) > 0:
		GameState.add_xp(int(d["xp"]), "quest:" + String(qid))
	if int(d.get("caps", 0)) > 0:
		GameState.add_item(&"cap", int(d["caps"]))
	var items: Variant = d.get("items", {})
	if items is Dictionary:
		for it: String in items:
			GameState.add_item(StringName(it), int(items[it]))
	var flags: Variant = d.get("flags", {})
	if flags is Dictionary:
		for f: String in flags:
			GameState.set_flag(StringName(f), flags[f])
	var rep: Variant = d.get("reputation", {})
	if rep is Dictionary:
		for fa: String in rep:
			GameState.add_reputation(StringName(fa), int(rep[fa]))
	if int(d.get("skill_points", 0)) > 0:
		GameState.add_skill_points(int(d["skill_points"]))
	if int(d.get("attribute_points", 0)) > 0:
		GameState.add_attribute_points(int(d["attribute_points"]))
	for s: Variant in d.get("skills", []):
		GameState.grant_skill(StringName(str(s)))
	GameEffects.apply(d.get("effects", []), {"quest_id": String(qid)})


func _all_required_done(qid: StringName) -> bool:
	for o: Dictionary in get_quest_def(qid)["objectives"]:
		if not bool(o["optional"]) and not bool(_obj_rt(qid, String(o["id"])).get("done", false)):
			return false
	return true


func _current_stage(qid: StringName) -> int:
	var stage := 1 << 30
	for o: Dictionary in get_quest_def(qid)["objectives"]:
		if not bool(o["optional"]) and not bool(_obj_rt(qid, String(o["id"])).get("done", false)):
			stage = mini(stage, int(o["stage"]))
	return stage


func _is_obj_active(qid: StringName, i: int) -> bool:
	if not is_active(qid):
		return false
	var o: Dictionary = get_quest_def(qid)["objectives"][i]
	if bool(_obj_rt(qid, String(o["id"])).get("done", false)):
		return false
	return int(o["stage"]) <= _current_stage(qid)


func _activate_new_objectives(qid: StringName) -> void:
	var objs: Array = get_quest_def(qid)["objectives"]
	for i in objs.size():
		var o: Dictionary = objs[i]
		var r := _obj_rt(qid, String(o["id"]))
		if r.is_empty() or bool(r.get("activated", false)) or not _is_obj_active(qid, i):
			continue
		r["activated"] = true
		# A quest started (or advanced) mid-conversation counts "talk to <that NPC>" at once:
		# Cam is already talking to them (dialogue_started fired before the objective existed).
		if String(o["type"]) == "talk_to" and DialogueManager.is_active() \
				and String(DialogueManager.get_current_speaker_id()) == str(o["npc"]) \
				and (str(o.get("dialogue", "")) == "" or String(DialogueManager.get_current_dialogue()) == str(o["dialogue"])) \
				and _gate_ok(o, String(qid)):
			_progress(qid, i, 1)
			if not is_active(qid):
				return
			continue
		if bool(o.get("count_existing", false)):
			var existing := _existing_count(o)
			if existing > 0:
				_progress(qid, i, 0, existing)
				if not is_active(qid):
					return
				continue
		GameEvents.quest_objective_updated.emit(qid, StringName(String(o["id"])), int(r.get("progress", 0)), int(o["count"]))


func _existing_count(o: Dictionary) -> int:
	match String(o["type"]):
		"mark_territory":
			var spots: Array = o.get("spots", [])
			var c := 0
			for s in GameState.get_marked_territory():
				if spots.is_empty() or s in spots:
					c += 1
			return c
		"nap":
			return GameState.get_counter(&"nap_spots_unique")
		"knock_objects":
			return GameState.get_counter(&"knocked_unique")
		"catch_prey":
			var prey := String(o.get("prey", ""))
			return GameState.get_counter(StringName("prey_" + prey) if prey != "" else &"prey_caught")
	return 0


## Re-evaluates state-driven objectives, inventory collect objectives, fail conditions and
## auto-starting quests. Re-entrancy safe (coalesces nested requests).
func _request_evaluate() -> void:
	if _evaluating:
		_dirty = true
		return
	_evaluating = true
	var guard := 0
	while true:
		_dirty = false
		_evaluate_once()
		guard += 1
		if not _dirty or guard >= 8:
			break
	_evaluating = false


func _evaluate_once() -> void:
	for qid in get_active_quests():
		var def := get_quest_def(qid)
		if def.has("fail_if") and GameConditions.evaluate(def["fail_if"], {"quest_id": String(qid)}):
			fail_quest(qid)
			continue
		var objs: Array = def["objectives"]
		for i in objs.size():
			if not is_active(qid):
				break
			if not _is_obj_active(qid, i):
				continue
			var o: Dictionary = objs[i]
			match String(o["type"]):
				"flag_set":
					if GameConditions._loose_equal(GameState.get_flag(StringName(str(o["flag"])), null), o.get("value", true)) and _gate_ok(o, String(qid)):
						_progress(qid, i, 1)
				"time_window":
					if TimeOfDay.is_hour_between(float(o["from"]), float(o["to"])) and _gate_ok(o, String(qid)):
						_progress(qid, i, 1)
				"condition":
					if GameConditions.evaluate(o["if"], {"quest_id": String(qid)}) and _gate_ok(o, String(qid)):
						_progress(qid, i, 1)
				"collect_item":
					if String(o.get("mode", "inventory")) == "inventory":
						var have := GameState.item_count(StringName(str(o["item"])))
						var r := _obj_rt(qid, String(o["id"]))
						if mini(have, int(o["count"])) != int(r.get("progress", 0)) and _gate_ok(o, String(qid)):
							_progress(qid, i, 0, mini(have, int(o["count"])))
	_try_pending_starts()
	for id: String in _defs:
		if bool(_defs[id]["auto_start"]) and get_state(StringName(id)) == STATE_INACTIVE and prerequisites_met(StringName(id)):
			start_quest(StringName(id))


func _try_pending_starts() -> void:
	for id: String in _pending_starts.keys():
		if not _defs.has(id) or get_state(StringName(id)) == STATE_ACTIVE or get_state(StringName(id)) == STATE_COMPLETED:
			_pending_starts.erase(id)
		elif prerequisites_met(StringName(id)):
			start_quest(StringName(id))


func _auto_track() -> void:
	var act := get_active_quests()
	if not act.is_empty():
		track(act[0])


func _poll_reach_objectives() -> void:
	var player := GameState.get_player()
	if player == null:
		return
	for qid in get_active_quests():
		var objs: Array = get_quest_def(qid)["objectives"]
		for i in objs.size():
			var o: Dictionary = objs[i]
			if String(o["type"]) != "reach_location" or not _is_obj_active(qid, i):
				continue
			var n := find_target_node(StringName(str(o["target"])))
			if n == null:
				continue
			var radius := float(o.get("radius", n.get_meta(&"radius", default_reach_radius)))
			if player.global_position.distance_to(n.global_position) <= radius and _gate_ok(o, String(qid)):
				_progress(qid, i, 1)


# =============================================================================================
# Signal handlers
# =============================================================================================

func _on_interacted(target: Node, verb: StringName) -> void:
	var tid := _target_id_of(target)
	var key := "%s|%s|%d" % [verb, tid, target.get_instance_id() if target != null else 0]
	var frame := Engine.get_process_frames()
	if key == _last_interact_key and frame == _last_interact_frame:
		return  # same interaction reported twice in one frame
	_last_interact_key = key
	_last_interact_frame = frame
	report(&"interact", {"verb": verb, "target_id": tid})


static func _target_id_of(target: Node) -> String:
	if target == null:
		return ""
	if "target_id" in target and str(target.get("target_id")) != "":
		return str(target.get("target_id"))
	if target.has_meta(&"target_id"):
		return str(target.get_meta(&"target_id"))
	return String(target.name)


# =============================================================================================
# Save provider
# =============================================================================================

func get_save_data() -> Dictionary:
	return {"version": 1, "quests": _rt.duplicate(true), "tracked": String(_tracked), "pending": _pending_starts.keys()}


func load_save_data(d: Dictionary) -> void:
	_rt.clear()
	_pending_starts.clear()
	_target_cache.clear()
	var qs: Variant = d.get("quests", {})
	if qs is Dictionary:
		for id: String in qs:
			var raw: Variant = qs[id]
			if not raw is Dictionary:
				continue
			var st := String(raw.get("state", "inactive"))
			if st not in ["inactive", "active", "completed", "failed"]:
				st = "inactive"
			var objs := {}
			var raw_objs: Variant = raw.get("objectives", {})
			if raw_objs is Dictionary:
				for oid: String in raw_objs:
					var ro: Variant = raw_objs[oid]
					if ro is Dictionary:
						objs[oid] = {"progress": int(ro.get("progress", 0)), "done": bool(ro.get("done", false)),
							"seen": (ro.get("seen", []) as Array).duplicate() if ro.get("seen", []) is Array else [],
							"revealed": bool(ro.get("revealed", false)), "activated": bool(ro.get("activated", false)),
							"missed": bool(ro.get("missed", false))}
			# Objectives added to the quest after the save was made start fresh.
			if _defs.has(id):
				for o: Dictionary in _defs[id]["objectives"]:
					if not objs.has(String(o["id"])):
						objs[String(o["id"])] = {"progress": 0, "done": st == "completed", "seen": [], "revealed": false, "activated": false, "missed": false}
			_rt[id] = {"state": st, "objectives": objs, "started_day": int(raw.get("started_day", 1)),
				"started_at": float(raw.get("started_at", 0.0)), "finished_day": int(raw.get("finished_day", -1))}
	var pend: Variant = d.get("pending", [])
	if pend is Array:
		for p: Variant in pend:
			_pending_starts[str(p)] = true
	_tracked = StringName(String(d.get("tracked", "")))
	if _tracked != &"" and not is_active(_tracked):
		_tracked = &""
	if _tracked == &"":
		_auto_track()
	GameEvents.tracked_quest_changed.emit(_tracked)
	# Auto-start quests whose prerequisites hold (e.g. the opening chapter on a new game),
	# resume chained quests and refresh state-driven objectives.
	_request_evaluate()


func reset_state() -> void:
	load_save_data({})


# =============================================================================================
# Helpers
# =============================================================================================

func _obj_index(qid: StringName, oid: String) -> int:
	var def := get_quest_def(qid)
	if def.is_empty():
		return -1
	var objs: Array = def["objectives"]
	for i in objs.size():
		if String(objs[i]["id"]) == oid:
			return i
	return -1


func _obj_rt(qid: StringName, oid: String) -> Dictionary:
	var r: Dictionary = _rt.get(String(qid), {})
	var objs: Dictionary = r.get("objectives", {})
	return objs.get(oid, {})


func _notify(key: String, args: Dictionary, icon: StringName) -> void:
	if notifications_enabled:
		GameEvents.notify.emit(tr(key).format(args), icon)


func _autosave(reason: String) -> void:
	if autosave_on_progress:
		GameState.autosave(reason)
