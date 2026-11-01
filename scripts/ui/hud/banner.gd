class_name HudBanner
extends VBoxContainer
## Centre-top banners: "location discovered" (caption + big serif name between gold dividers)
## and "new quest" (caption + quest title). Queued so two never overlap.

var _queue: Array[Dictionary] = []
var _busy := false
var _caption: Label
var _title: Label
var _line_top: TextureRect
var _line_bottom: TextureRect


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	alignment = BoxContainer.ALIGNMENT_CENTER
	add_theme_constant_override(&"separation", 6)
	_line_top = UIStyle.divider(520, Color(UIStyle.GOLD, 0.9))
	_line_top.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	add_child(_line_top)
	_caption = UIStyle.label("", &"semibold", 18, UIStyle.GOLD_LIGHT)
	_caption.uppercase = true
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	HudQuestTracker._shadow(_caption)
	add_child(_caption)
	_title = UIStyle.label("", &"title", 64, UIStyle.TEXT)
	_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.65))
	_title.add_theme_constant_override(&"shadow_outline_size", 12)
	_title.add_theme_constant_override(&"shadow_offset_y", 3)
	add_child(_title)
	_line_bottom = UIStyle.divider(360, Color(UIStyle.GOLD, 0.6))
	_line_bottom.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	add_child(_line_bottom)
	modulate.a = 0.0
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"location_discovered", _on_location)
		ge.connect(&"quest_started", _on_quest_started)


func _on_location(_id: StringName, display_name: String) -> void:
	show_banner(tr("HUD_DISCOVERED"), tr(display_name), 64)


func _on_quest_started(quest_id: StringName) -> void:
	var qm := get_node_or_null(^"/root/QuestManager")
	var title := String(quest_id)
	if qm != null:
		var q: Dictionary = qm.call("get_quest", quest_id)
		title = String(q.get("title", title))
	show_banner(tr("HUD_NEW_QUEST"), title, 46)


func show_banner(caption: String, title: String, size: int = 64) -> void:
	_queue.append({"caption": caption, "title": title, "size": size})
	if not _busy:
		_next()


func is_busy() -> bool:
	return _busy


func _next() -> void:
	if _queue.is_empty():
		_busy = false
		return
	_busy = true
	var d: Dictionary = _queue.pop_front()
	_caption.text = String(d["caption"])
	_title.text = String(d["title"])
	_title.add_theme_font_size_override(&"font_size", int(d["size"]))
	modulate.a = 0.0
	scale = Vector2.ONE
	_line_top.scale = Vector2(0.2, 1.0)
	_line_top.pivot_offset = _line_top.size * 0.5
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.set_parallel(true)
	tw.tween_property(self, "modulate:a", 1.0, 0.6)
	tw.tween_property(_line_top, "scale", Vector2.ONE, 1.0)
	tw.set_parallel(false)
	tw.tween_interval(3.0)
	tw.tween_property(self, "modulate:a", 0.0, 1.0)
	tw.tween_interval(0.3)
	tw.tween_callback(_next)
