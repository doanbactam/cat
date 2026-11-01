extends Node
## DialogueManager — JSON dialogue graphs (owner: systems). Files: data/dialogue/<id>.json,
## format in data/dialogue/_schema.md.
##
## NPC lines are text (translated with tr); Cam never speaks — his "lines" are cat actions
## (meow, purr, headbutt, ignore, chirp, slow_blink, rub, hiss, ...). Nodes can branch on
## conditions, run effects (flags, items, quests, xp, reputation, events) and be shown once.
## UI listens to GameEvents.dialogue_started / dialogue_line / dialogue_node_shown / dialogue_ended
## and calls advance() / choose(index).

signal line_shown(info: Dictionary)

const END := "end"
const MAX_HOPS := 64
## Cam's possible "replies" (choice actions). Labels: DLG_ACT_<ACTION> in the string table.
const ACTIONS: Array[String] = [
	"meow", "purr", "headbutt", "ignore", "chirp", "trill", "slow_blink", "rub", "hiss", "sit",
	"knead", "follow", "leave", "roll_over", "offer_item", "swipe", "groom", "stare", "yowl", "wait",
]
## Sound + GameEvents.player_meowed kind emitted for some actions.
const ACTION_SFX := {
	"meow": "cat_meow_greet", "purr": "cat_purr", "chirp": "cat_meow_chirp", "trill": "cat_meow_trill",
	"hiss": "cat_hiss", "yowl": "cat_yowl", "swipe": "cat_swipe", "stare": "", "knead": "",
}
const ACTION_MEOW_KIND := {"meow": &"short", "purr": &"purr", "chirp": &"chirp", "trill": &"chirp", "yowl": &"loud"}

var dialogue_dirs: PackedStringArray = ["res://data/dialogue"]
## Stop the game clock while a conversation is open.
var pause_time_during_dialogue := true
## Play action SFX for Cam's replies here (the player should only play the animation).
var play_action_sfx := true

var _cache: Dictionary = {}
var _active := false
var _dialogue_id: StringName = &""
var _def: Dictionary = {}
var _node_id := ""
var _speaker_node: Node = null
var _speaker_id: StringName = &""
var _choices: Array[Dictionary] = []   # visible choices of the current node
var _current: Dictionary = {}
var _seen_nodes: Dictionary = {}       # "dialogue_id/node_id" -> times shown
var _seen_choices: Dictionary = {}     # "dialogue_id/node_id/choice_index" -> true
var _finished: Dictionary = {}         # dialogue_id -> times finished
var _history: Array[Dictionary] = []


func _ready() -> void:
	GameState.register_save_provider("dialogue", self)


# =============================================================================================
# Public API
# =============================================================================================

## Starts a dialogue. `speaker` is the NPC node (used for effects/animations); its id comes from
## `speaker_id` arg, else its property/meta speaker_id / npc_id, else the dialogue's "speaker".
func start(dialogue_id: StringName, speaker: Node = null, speaker_id: StringName = &"") -> bool:
	if _active:
		push_warning("DialogueManager.start: dialogue '%s' already active" % _dialogue_id)
		return false
	var def := get_dialogue(dialogue_id)
	if def.is_empty():
		push_warning("DialogueManager.start: unknown dialogue " + String(dialogue_id))
		return false
	var entry := _resolve_entry(def)
	if entry == "" or entry == END:
		return false
	_active = true
	_dialogue_id = dialogue_id
	_def = def
	_speaker_node = speaker
	_speaker_id = speaker_id if speaker_id != &"" else _speaker_id_of(speaker, def)
	_history.clear()
	if pause_time_during_dialogue:
		TimeOfDay.push_pause(&"dialogue")
	if speaker != null and is_instance_valid(speaker) and speaker.has_method("on_dialogue_started"):
		speaker.call("on_dialogue_started", dialogue_id)
	GameEvents.dialogue_started.emit(dialogue_id, _speaker_id)
	_goto(entry)
	return true


## Continue past a line without choices. Returns false if the current node needs a choice.
func advance() -> bool:
	if not _active:
		return false
	if not _choices.is_empty():
		return false
	var node := _node(_node_id)
	_goto(String(node.get("next", END)))
	return true


## Pick one of the visible choices of the current node (index into get_choices()).
func choose(index: int) -> bool:
	if not _active or index < 0 or index >= _choices.size():
		return false
	var c: Dictionary = _choices[index]
	if not bool(c["enabled"]):
		return false
	var raw: Dictionary = c["_raw"]
	var action := String(raw.get("action", "meow"))
	_seen_choices["%s/%s/%d" % [_dialogue_id, _node_id, int(c["_index"])]] = true
	_history.append({"speaker": "cam", "action": action, "text": String(c["text"])})
	GameEvents.dialogue_choice_made.emit(_dialogue_id, StringName(action))
	if play_action_sfx and ACTION_SFX.has(action):
		GameEffects.play_sfx(StringName(ACTION_SFX[action]), _player_pos())
	if ACTION_MEOW_KIND.has(action):
		var p := GameState.get_player()
		if p != null:
			GameEvents.player_noise.emit(p.global_position, 0.25 if action == "purr" else 0.5)
	GameEffects.apply(raw.get("effects", []), _ctx())
	if not _active:
		return true  # an effect ended the dialogue
	var node := _node(_node_id)
	_goto(String(raw.get("next", node.get("next", END))))
	return true


func is_active() -> bool:
	return _active


## Ends the current dialogue immediately.
func stop() -> void:
	if _active:
		_end()


func get_current_dialogue() -> StringName:
	return _dialogue_id if _active else &""


## Id of the NPC Cam is talking to (&"" when no dialogue is open).
func get_current_speaker_id() -> StringName:
	return _speaker_id if _active else &""


## Info of the line on screen: dialogue_id, node_id, speaker_id, speaker_name, text, portrait,
## choices (Array of {text, action, enabled, requirement}), can_advance.
func get_current_line() -> Dictionary:
	return _current.duplicate(true)


func get_choices() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for c in _choices:
		out.append({"text": c["text"], "action": c["action"], "enabled": c["enabled"], "requirement": c["requirement"]})
	return out


## Lines shown in the current conversation (for a backlog view).
func get_history() -> Array[Dictionary]:
	return _history.duplicate(true)


## True when the dialogue was finished before ("id") or a node was shown ("id/node").
func has_seen(key: StringName) -> bool:
	var k := String(key)
	if k.contains("/"):
		return _seen_nodes.has(k)
	return _finished.has(k)


func get_times_finished(dialogue_id: StringName) -> int:
	return int(_finished.get(String(dialogue_id), 0))


func has_dialogue(dialogue_id: StringName) -> bool:
	return not get_dialogue(dialogue_id).is_empty()


## Loads (cached) a dialogue definition from dialogue_dirs, or one registered from code.
func get_dialogue(dialogue_id: StringName) -> Dictionary:
	var k := String(dialogue_id)
	if _cache.has(k):
		return _cache[k]
	for dir in dialogue_dirs:
		var p := dir.path_join(k + ".json")
		if FileAccess.file_exists(p):
			var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(p))
			if parsed is Dictionary:
				var d: Dictionary = parsed
				if not d.has("id"):
					d["id"] = k
				for e in validate_dialogue(d):
					push_warning("DialogueManager %s: %s" % [p, e])
				_cache[k] = d
				return d
			push_error("DialogueManager: invalid JSON " + p)
	return {}


## Registers a dialogue from code (tests / procedural barks).
func register_dialogue(def: Dictionary) -> void:
	_cache[String(def.get("id", ""))] = def


func clear_cache() -> void:
	_cache.clear()


## Returns problems with a dialogue definition (missing nodes, bad conditions/effects). [] = valid.
func validate_dialogue(def: Dictionary) -> PackedStringArray:
	var errs: PackedStringArray = []
	var id := String(def.get("id", "?"))
	var nodes: Variant = def.get("nodes", {})
	if not nodes is Dictionary or (nodes as Dictionary).is_empty():
		errs.append(id + ": no nodes")
		return errs
	var nd: Dictionary = nodes
	var start: Variant = def.get("start", "")
	var entries: Array = start if start is Array else [{"node": start}]
	for en: Variant in entries:
		var target := String(en.get("node", "")) if en is Dictionary else str(en)
		if target != END and not nd.has(target):
			errs.append("%s: start node '%s' missing" % [id, target])
		if en is Dictionary and (en as Dictionary).has("if"):
			errs.append_array(GameConditions.validate(en["if"], id + ".start"))
	for nid: String in nd:
		var n: Variant = nd[nid]
		if not n is Dictionary:
			errs.append("%s/%s: node is not a dictionary" % [id, nid])
			continue
		var node: Dictionary = n
		var w := "%s/%s" % [id, nid]
		for key in ["next", "else"]:
			if node.has(key) and String(node[key]) != END and not nd.has(String(node[key])):
				errs.append("%s: %s → missing node '%s'" % [w, key, node[key]])
		if node.has("if"):
			errs.append_array(GameConditions.validate(node["if"], w))
		errs.append_array(GameEffects.validate(node.get("effects", []), w))
		if node.has("branch"):
			for b: Variant in node["branch"]:
				if not b is Dictionary or not (b as Dictionary).has("next"):
					errs.append(w + ": branch entries need 'next'")
					continue
				if String(b["next"]) != END and not nd.has(String(b["next"])):
					errs.append("%s: branch → missing node '%s'" % [w, b["next"]])
				errs.append_array(GameConditions.validate(b.get("if"), w + ".branch"))
		if node.has("choices"):
			var i := 0
			for c: Variant in node["choices"]:
				var cw := "%s.choices[%d]" % [w, i]
				i += 1
				if not c is Dictionary:
					errs.append(cw + ": not a dictionary")
					continue
				var cd: Dictionary = c
				if String(cd.get("action", "")) not in ACTIONS:
					errs.append("%s: unknown action '%s'" % [cw, cd.get("action", "")])
				if cd.has("next") and String(cd["next"]) != END and not nd.has(String(cd["next"])):
					errs.append("%s: next → missing node '%s'" % [cw, cd["next"]])
				errs.append_array(GameConditions.validate(cd.get("if"), cw))
				errs.append_array(GameEffects.validate(cd.get("effects", []), cw))
		if not node.has("text_key") and not node.has("branch") and not node.has("effects") and not node.has("next"):
			errs.append(w + ": node has no text_key, branch, effects or next")
	return errs


# =============================================================================================
# Graph walking
# =============================================================================================

func _resolve_entry(def: Dictionary) -> String:
	var start: Variant = def.get("start", "")
	if start is Array:
		for en: Variant in start:
			if en is Dictionary:
				if GameConditions.evaluate((en as Dictionary).get("if"), _ctx_for(def)):
					return String(en.get("node", END))
			elif en is String:
				return en
		return ""
	return str(start)


func _goto(node_id: String) -> void:
	var hops := 0
	var nid := node_id
	while _active:
		hops += 1
		if hops > MAX_HOPS:
			push_error("DialogueManager: too many hops in %s (loop?)" % _dialogue_id)
			_end()
			return
		if nid == "" or nid == END:
			_end()
			return
		var node := _node(nid)
		if node.is_empty():
			push_warning("DialogueManager: missing node '%s' in %s" % [nid, _dialogue_id])
			_end()
			return
		var seen_key := "%s/%s" % [_dialogue_id, nid]
		if node.has("if") and not GameConditions.evaluate(node["if"], _ctx()):
			nid = String(node.get("else", node.get("next", END)))
			continue
		if bool(node.get("once", false)) and _seen_nodes.has(seen_key):
			nid = String(node.get("else", node.get("next", END)))
			continue
		_node_id = nid
		_seen_nodes[seen_key] = int(_seen_nodes.get(seen_key, 0)) + 1
		GameEffects.apply(node.get("effects", []), _ctx())
		if not _active:
			return
		if node.has("anim"):
			_speaker_anim(String(node["anim"]))
		if node.has("sfx"):
			GameEffects.play_sfx(StringName(String(node["sfx"])), _speaker_pos())
		if node.has("branch"):
			var target := END
			for b: Variant in node["branch"]:
				if b is Dictionary and GameConditions.evaluate((b as Dictionary).get("if"), _ctx()):
					target = String(b["next"])
					break
			nid = target
			continue
		if node.has("text_key"):
			_show(node)
			return
		nid = String(node.get("next", END))


func _show(node: Dictionary) -> void:
	_choices.clear()
	var raw_choices: Array = node.get("choices", []) if node.get("choices", []) is Array else []
	for i in raw_choices.size():
		var c: Variant = raw_choices[i]
		if not c is Dictionary:
			continue
		var cd: Dictionary = c
		if bool(cd.get("once", false)) and _seen_choices.has("%s/%s/%d" % [_dialogue_id, _node_id, i]):
			continue
		var ok := GameConditions.evaluate(cd.get("if"), _ctx())
		if not ok and not bool(cd.get("show_locked", false)):
			continue
		var action := String(cd.get("action", "meow"))
		var label := tr("DLG_ACT_" + action.to_upper())
		var text := label
		if cd.has("text_key"):
			text = "%s — %s" % [label, _format(tr(String(cd["text_key"])), cd)]
		var req := "" if ok else GameConditions.describe(cd.get("if"))
		_choices.append({"text": text, "action": action, "enabled": ok, "requirement": req, "_raw": cd, "_index": i})
	var speaker_key := String(node.get("speaker", _def.get("speaker", "")))
	var speaker_name := _speaker_display_name(speaker_key)
	var text := _format(tr(String(node["text_key"])), node)
	var plain: PackedStringArray = []
	for c in _choices:
		plain.append(String(c["text"]) if bool(c["enabled"]) else "(%s) %s" % [c["requirement"], c["text"]])
	_current = {
		"dialogue_id": String(_dialogue_id), "node_id": _node_id, "speaker_id": speaker_key,
		"speaker_name": speaker_name, "text": text, "text_key": String(node["text_key"]),
		"portrait": String(_speaker_def(speaker_key).get("portrait", "")),
		"emote": String(node.get("emote", "")), "camera": String(node.get("camera", "")),
		"choices": get_choices(), "can_advance": _choices.is_empty(),
	}
	_history.append({"speaker": speaker_key, "speaker_name": speaker_name, "text": text})
	GameEvents.dialogue_line.emit(speaker_name, text, plain)
	GameEvents.dialogue_node_shown.emit(_current.duplicate(true))
	line_shown.emit(_current)


func _end() -> void:
	var id := _dialogue_id
	var sp := _speaker_node
	_active = false
	_choices.clear()
	_current = {}
	_finished[String(id)] = int(_finished.get(String(id), 0)) + 1
	if pause_time_during_dialogue:
		TimeOfDay.pop_pause(&"dialogue")
	if sp != null and is_instance_valid(sp) and sp.has_method("on_dialogue_ended"):
		sp.call("on_dialogue_ended", id)
	_speaker_node = null
	_def = {}
	_node_id = ""
	GameEvents.dialogue_ended.emit(id)


func _node(nid: String) -> Dictionary:
	var nodes: Dictionary = _def.get("nodes", {})
	var n: Variant = nodes.get(nid, {})
	return n if n is Dictionary else {}


# =============================================================================================
# Helpers
# =============================================================================================

func _ctx() -> Dictionary:
	return {"speaker": _speaker_node, "speaker_id": String(_speaker_id), "dialogue_id": String(_dialogue_id)}


func _ctx_for(def: Dictionary) -> Dictionary:
	return {"speaker_id": String(def.get("speaker", "")), "dialogue_id": String(def.get("id", ""))}


func _speaker_id_of(speaker: Node, def: Dictionary) -> StringName:
	if speaker != null and is_instance_valid(speaker):
		for p in ["speaker_id", "npc_id"]:
			if p in speaker and str(speaker.get(p)) != "":
				return StringName(str(speaker.get(p)))
			if speaker.has_meta(StringName(p)):
				return StringName(str(speaker.get_meta(StringName(p))))
	return StringName(String(def.get("speaker", "")))


func _speaker_def(key: String) -> Dictionary:
	var sp: Variant = _def.get("speakers", {})
	if sp is Dictionary and (sp as Dictionary).has(key):
		var d: Variant = sp[key]
		if d is Dictionary:
			return d
		if d is String:
			return {"name_key": d}
	return {}


func _speaker_display_name(key: String) -> String:
	if key == "" or key == "narrator":
		return ""
	var d := _speaker_def(key)
	return tr(String(d.get("name_key", "NPC_" + key.to_upper())))


func _format(text: String, node: Dictionary) -> String:
	var vars := {
		"caps": GameState.get_caps(), "level": GameState.level, "day": TimeOfDay.day,
		"time": TimeOfDay.get_time_string(), "cam": tr("NPC_CAM"),
		"mouth": GameState.get_item_name(GameState.mouth_item) if GameState.mouth_item != &"" else "",
	}
	var args: Variant = node.get("text_args", {})
	if args is Dictionary:
		for k: Variant in args:
			vars[k] = tr(str(args[k])) if str(args[k]).to_upper() == str(args[k]) else args[k]
	return text.format(vars)


func _speaker_anim(anim: String) -> void:
	if _speaker_node != null and is_instance_valid(_speaker_node) and _speaker_node.has_method("play_dialogue_anim"):
		_speaker_node.call("play_dialogue_anim", StringName(anim))


func _speaker_pos() -> Vector3:
	if _speaker_node is Node3D and is_instance_valid(_speaker_node):
		return (_speaker_node as Node3D).global_position
	return Vector3.INF


func _player_pos() -> Vector3:
	var p := GameState.get_player()
	return p.global_position if p != null else Vector3.INF


# =============================================================================================
# Save provider
# =============================================================================================

func get_save_data() -> Dictionary:
	return {"seen_nodes": _seen_nodes.duplicate(), "seen_choices": _seen_choices.duplicate(), "finished": _finished.duplicate()}


func load_save_data(d: Dictionary) -> void:
	if _active:
		_end()
	_seen_nodes.clear()
	_seen_choices.clear()
	_finished.clear()
	var sn: Variant = d.get("seen_nodes", {})
	if sn is Dictionary:
		for k: String in sn:
			_seen_nodes[k] = int(sn[k])
	var sc: Variant = d.get("seen_choices", {})
	if sc is Dictionary:
		for k: String in sc:
			_seen_choices[k] = true
	var fi: Variant = d.get("finished", {})
	if fi is Dictionary:
		for k: String in fi:
			_finished[k] = int(fi[k])


func reset_state() -> void:
	load_save_data({})
