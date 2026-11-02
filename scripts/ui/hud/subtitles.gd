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
	var speaker_txt := tr(speaker) if speaker != "" else ""
	# Size the line to its text (max 1100 px) so the soft backing hugs it.
	var plain := ("%s: %s" % [speaker_txt, text]) if speaker_txt != "" else text
	var body_font := UIStyle.font(&"body")
	var tw_px := body_font.get_string_size(plain, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x if body_font != null else 1100.0
	r.custom_minimum_size = Vector2(minf(1100.0, tw_px + 12.0), 0)
	r.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	r.add_theme_color_override(&"font_outline_color", Color(0, 0, 0, 0.85))
	r.add_theme_constant_override(&"outline_size", 6)
	var who := "[color=#f2cf7e]%s:[/color] " % speaker_txt if speaker_txt != "" else ""
	r.text = "[center]%s%s[/center]" % [who, text]
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var panel := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.04, 0.03, 0.025, 0.5)
	sb.set_corner_radius_all(10)
	sb.content_margin_left = 18
	sb.content_margin_right = 18
	sb.content_margin_top = 6
	sb.content_margin_bottom = 8
	sb.shadow_color = Color(0, 0, 0, 0.18)
	sb.shadow_size = 12
	panel.add_theme_stylebox_override(&"panel", sb)
	panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(r)
	add_child(panel)
	_lines.append(panel)
	panel.modulate.a = 0.0
	var tw := panel.create_tween()
	tw.tween_property(panel, "modulate:a", 1.0, 0.2)
	tw.tween_interval(maxf(1.2, duration))
	tw.tween_property(panel, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func() -> void:
		_lines.erase(panel)
		panel.queue_free())


func line_count() -> int:
	return _lines.size()
