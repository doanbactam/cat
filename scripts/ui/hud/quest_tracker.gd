class_name HudQuestTracker
extends VBoxContainer
## Tracked quest (top right): category caption, title, visible objectives with check marks and
## progress. Refreshes on quest signals; finished objectives strike through then fade away.

var _caption: Label
var _title: Label
var _objs: VBoxContainer
var _quest: StringName = &""
var _dirty := true
var _refresh_t := 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_constant_override(&"separation", 4)
	alignment = BoxContainer.ALIGNMENT_BEGIN
	_caption = UIStyle.label("", &"semibold", 15, UIStyle.GOLD)
	_caption.uppercase = true
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_shadow(_caption)
	add_child(_caption)
	_title = UIStyle.label("", &"heading", 30, UIStyle.TEXT)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_shadow(_title)
	add_child(_title)
	_objs = VBoxContainer.new()
	_objs.add_theme_constant_override(&"separation", 6)
	_objs.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_objs)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		for sig: StringName in [&"quest_started", &"quest_completed", &"quest_failed", &"tracked_quest_changed", &"settings_changed", &"game_loaded"]:
			ge.connect(sig, _mark_dirty.unbind(1))
		ge.connect(&"quest_objective_revealed", _mark_dirty.unbind(2))
		ge.connect(&"quest_objective_updated", _mark_dirty.unbind(4))
		ge.connect(&"new_game_started", _mark_dirty)
	refresh()


func _mark_dirty() -> void:
	_dirty = true


static func _shadow(l: Label) -> void:
	l.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.7))
	l.add_theme_constant_override(&"shadow_outline_size", 7)
	l.add_theme_constant_override(&"shadow_offset_y", 2)


func _process(delta: float) -> void:
	_refresh_t -= delta
	if _dirty and _refresh_t <= 0.0:
		_dirty = false
		_refresh_t = 0.15
		refresh()


func refresh() -> void:
	var qm := get_node_or_null(^"/root/QuestManager")
	_quest = qm.call("get_tracked") if qm != null else &""
	for c in _objs.get_children():
		c.queue_free()
	if _quest == &"" or qm == null:
		visible = false
		return
	var q: Dictionary = qm.call("get_quest", _quest)
	if q.is_empty() or String(q.get("state", "")) != "active":
		visible = false
		return
	visible = true
	_caption.text = tr("QUEST_CATEGORY_" + String(q.get("category", "misc")).to_upper())
	_title.text = String(q.get("title", ""))
	var shown := 0
	for o: Dictionary in q.get("objectives", []):
		if bool(o.get("hidden", false)) or not bool(o.get("active", false)):
			if not bool(o.get("done", false)):
				continue
		if bool(o.get("done", false)) and shown > 0:
			continue  # keep the list short: only the current step(s)
		if bool(o.get("done", false)):
			continue
		_objs.add_child(_objective_row(o))
		shown += 1
		if shown >= 3:
			break


func _objective_row(o: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_END
	row.add_theme_constant_override(&"separation", 10)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var text := String(o.get("text", ""))
	var req := int(o.get("required", 1))
	if req > 1:
		text += "  %d/%d" % [int(o.get("progress", 0)), req]
	if bool(o.get("optional", false)):
		text += "  (" + tr("JOURNAL_OPTIONAL") + ")"
	var l := UIStyle.label(text, &"medium", 21, UIStyle.TEXT if not bool(o.get("optional", false)) else UIStyle.TEXT_DIM)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(380, 0)
	_shadow(l)
	row.add_child(l)
	var box := _CheckMark.new()
	box.done = bool(o.get("done", false))
	box.custom_minimum_size = Vector2(20, 20)
	box.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(box)
	return row


func get_tracked_quest() -> StringName:
	return _quest


class _CheckMark extends Control:
	var done := false

	func _draw() -> void:
		var r := Rect2(Vector2(1, 1), size - Vector2(2, 2))
		draw_rect(r.grow(1.5), Color(0, 0, 0, 0.45), true)
		draw_rect(r, Color(UIStyle.GOLD_LIGHT, 0.95), false, 1.6)
		if done:
			draw_polyline(PackedVector2Array([Vector2(4, 10), Vector2(8, 15), Vector2(17, 4)]), UIStyle.JADE, 2.6, true)
