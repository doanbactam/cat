class_name HudToasts
extends VBoxContainer
## Toast notifications (GameEvents.notify(text, icon)): small lacquer pills with an icon that
## slide in from the left, stack (max 4), and fade after a few seconds. Toasts whose icon has a
## bigger HUD moment (level_up, quest_complete, location) are left to the banners.

const MAX_TOASTS := 4
const LIFETIME := 4.6
## notify icon -> [glyph name, glyph group, tint]
const ICONS := {
	&"quest": [&"quest", "glyphs", Color("#ffb46a")],
	&"objective": [&"objective", "glyphs", Color("#8cc084")],
	&"skill": [&"skill", "glyphs", Color("#f2cf7e")],
	&"achievement": [&"achievement", "glyphs", Color("#f2cf7e")],
	&"memory": [&"memory", "glyphs", Color("#e8d0a0")],
	&"collectible": [&"memory", "glyphs", Color("#e8d0a0")],
	&"territory": [&"territory", "glyphs", Color("#e2683a")],
	&"health": [&"health", "glyphs", Color("#e9604f")],
	&"hunger": [&"hunger", "glyphs", Color("#e3b448")],
	&"energy": [&"energy", "glyphs", Color("#79c3cc")],
	&"warmth": [&"warmth", "glyphs", Color("#f2883c")],
	&"faint": [&"faint", "glyphs", Color("#c9b996")],
	&"save": [&"save", "glyphs", Color("#c9b996")],
	&"item": [&"item", "glyphs", Color("#f2cf7e")],
	&"caps": [&"cap", "glyphs", Color("#d4d8dc")],
	&"warning": [&"warning", "glyphs", Color("#e0604a")],
	&"info": [&"info", "glyphs", Color("#c9b996")],
}
## Icons that get their own banner/celebration instead of a toast.
const SUPPRESSED: Array[StringName] = [&"level_up", &"quest_complete", &"location"]

var suppress_banner_icons := true


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_theme_constant_override(&"separation", 10)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"notify", _on_notify)


func _on_notify(text: String, icon: StringName) -> void:
	if suppress_banner_icons and icon in SUPPRESSED:
		return
	push_toast(text, icon)


func push_toast(text: String, icon: StringName = &"info") -> Control:
	while get_child_count() >= MAX_TOASTS:
		var old := get_child(0)
		remove_child(old)
		old.queue_free()
	var spec: Array = ICONS.get(icon, ICONS[&"info"])
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sb := UIStyle.flat_box(Color(0.06, 0.042, 0.03, 0.82), 12, Color(UIStyle.GOLD, 0.35), 1, 14.0)
	sb.border_width_left = 3
	sb.border_color = spec[2]
	sb.content_margin_left = 14
	sb.content_margin_right = 22
	sb.content_margin_top = 10
	sb.content_margin_bottom = 10
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 8
	p.add_theme_stylebox_override(&"panel", sb)
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 12)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(h)
	var ic := UIStyle.icon_rect(UIStyle.glyph(spec[0], spec[1]), 30, spec[2])
	ic.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(ic)
	var l := UIStyle.label(text, &"medium", 21, UIStyle.TEXT)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(0, 0)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(l)
	p.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	p.custom_minimum_size = Vector2(0, 0)
	l.custom_minimum_size = Vector2(minf(UIStyle.font(&"medium").get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x + 4.0, 520.0), 0)
	add_child(p)
	p.modulate.a = 0.0
	var tw := p.create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.25)
	tw.tween_interval(LIFETIME)
	tw.tween_property(p, "modulate:a", 0.0, 0.6)
	tw.tween_callback(p.queue_free)
	return p
