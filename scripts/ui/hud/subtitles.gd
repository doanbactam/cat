class_name HudSubtitles
extends VBoxContainer
## Subtitles (bottom centre) for ambient lines and barks: GameEvents.subtitle_requested(speaker,
## text, duration). Respects gameplay/subtitles and gameplay/subtitle_size. Max 2 lines stacked.

const SIZES := {"small": 22, "medium": 26, "large": 32}

var _lines: Array[Control] = []


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	alignment = BoxContainer.ALIGNMENT_END
	add_theme_constant_override(&"separation", 6)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"subtitle_requested", show_line)


func show_line(speaker: String, text: String, duration: float = 3.5) -> void:
	if not bool(UIStyle.settings_value("gameplay", "subtitles", true)):
		return
	while _lines.size() >= 2:
		var old: Control = _lines.pop_front()
		if is_instance_valid(old):
			old.queue_free()
	var fs: int = SIZES.get(String(UIStyle.settings_value("gameplay", "subtitle_size", "medium")), 26)
	var r := UIStyle.rich("", fs, UIStyle.TEXT, &"body")
	r.fit_content = true
	r.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	r.custom_minimum_size = Vector2(1100, 0)
	r.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	r.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
	r.add_theme_constant_override(&"outline_size", 7)
	var who := "[color=#f2cf7e]%s:[/color] " % tr(speaker) if speaker != "" else ""
	r.text = "[center]%s%s[/center]" % [who, text]
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(r)
	_lines.append(r)
	r.modulate.a = 0.0
	var tw := r.create_tween()
	tw.tween_property(r, "modulate:a", 1.0, 0.2)
	tw.tween_interval(maxf(1.2, duration))
	tw.tween_property(r, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func() -> void:
		_lines.erase(r)
		r.queue_free())


func line_count() -> int:
	return _lines.size()
