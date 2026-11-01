class_name UIHintBar
extends HBoxContainer
## Footer row of "[glyph] label" input hints (e.g. Select / Back / Switch tab). Glyphs follow
## the active input device. set_hints([[&"ui_accept", "UI_SELECT"], [&"ui_cancel", "UI_BACK"]]).
## A hint entry may use a raw label instead of an action: ["@Q/E", "UI_TABS"] or ["@LB/RB", ...];
## "@kbm|pad" picks per device ("@Q / E|LB / RB").

@export var align_right := true
@export var label_color := Color("#c9b996")

var _hints: Array = []


func _ready() -> void:
	add_theme_constant_override(&"separation", 26)
	alignment = BoxContainer.ALIGNMENT_END if align_right else BoxContainer.ALIGNMENT_BEGIN
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var s := get_node_or_null(^"/root/Settings")
	if s != null and s.has_signal(&"input_device_changed"):
		s.connect(&"input_device_changed", func(_p: bool) -> void: _rebuild())
	_rebuild()


func set_hints(hints: Array) -> void:
	_hints = hints
	if is_inside_tree():
		_rebuild()


func _rebuild() -> void:
	for c in get_children():
		c.queue_free()
	var pad := UIStyle.using_gamepad()
	for h: Array in _hints:
		var row := HBoxContainer.new()
		row.add_theme_constant_override(&"separation", 8)
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var src := String(h[0])
		var g := UIInputGlyph.new()
		g.glyph_height = 30.0
		if src.begins_with("@"):
			var raw := src.substr(1)
			if raw.contains("|"):
				var parts := raw.split("|")
				raw = parts[1] if pad else parts[0]
			g.fixed_label = raw
		else:
			g.action = StringName(src)
		row.add_child(g)
		var l := UIStyle.label(tr(String(h[1])), &"medium", 19, label_color)
		row.add_child(l)
		add_child(row)
