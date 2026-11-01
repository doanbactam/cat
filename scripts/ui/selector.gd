class_name UISelector
extends Button
## Console-style option picker "‹  High  ›": left/right (keys, d-pad, stick) or clicking the
## arrows cycles through `options` ([{value, label}]); Enter/click cycles forward.
## Emits value_changed(value).

signal value_changed(value: Variant)

var options: Array = []      # [{"value": Variant, "label": String}]
var index := 0
var wrap := true
var _chev_l: Texture2D
var _chev_r: Texture2D


func _init() -> void:
	focus_mode = Control.FOCUS_ALL
	alignment = HORIZONTAL_ALIGNMENT_CENTER
	custom_minimum_size = Vector2(380, 52)
	clip_text = true
	set_meta(&"silent", true)


func _ready() -> void:
	_chev_l = UIStyle.glyph(&"chevron_left")
	_chev_r = UIStyle.glyph(&"chevron_right")
	pressed.connect(func() -> void: step(1))
	_refresh()


func set_options(opts: Array, current: Variant) -> void:
	options = opts
	index = 0
	for i in options.size():
		if _same(options[i]["value"], current):
			index = i
			break
	_refresh()


func set_value_silent(v: Variant) -> void:
	for i in options.size():
		if _same(options[i]["value"], v):
			index = i
			_refresh()
			return
	# value not in list (e.g. "custom")
	_refresh()


func get_value() -> Variant:
	return options[index]["value"] if index < options.size() else null


func step(d: int) -> void:
	if options.is_empty() or disabled:
		return
	var ni := index + d
	if wrap:
		ni = posmod(ni, options.size())
	else:
		ni = clampi(ni, 0, options.size() - 1)
	if ni == index:
		return
	index = ni
	_refresh()
	UIStyle.sfx(&"ui_slider")
	value_changed.emit(get_value())


func _refresh() -> void:
	text = String(options[index]["label"]) if index < options.size() else ""
	queue_redraw()


static func _same(a: Variant, b: Variant) -> bool:
	if typeof(a) in [TYPE_INT, TYPE_FLOAT] and typeof(b) in [TYPE_INT, TYPE_FLOAT]:
		return absf(float(a) - float(b)) < 0.0001
	return typeof(a) == typeof(b) and a == b


func _gui_input(event: InputEvent) -> void:
	if disabled:
		return
	if event.is_action_pressed(&"ui_left", true):
		step(-1)
		accept_event()
	elif event.is_action_pressed(&"ui_right", true):
		step(1)
		accept_event()
	elif event is InputEventMouseButton and (event as InputEventMouseButton).pressed and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		var x := (event as InputEventMouseButton).position.x
		if x < 56.0:
			step(-1)
			accept_event()
		elif x > size.x - 56.0:
			step(1)
			accept_event()


func _draw() -> void:
	var c := UIStyle.GOLD_LIGHT if has_focus() else Color(UIStyle.GOLD, 0.75)
	if disabled:
		c = Color(UIStyle.TEXT_MUTED, 0.5)
	var s := 22.0
	var y := (size.y - s) * 0.5
	if _chev_l != null and (wrap or index > 0):
		draw_texture_rect(_chev_l, Rect2(Vector2(16, y), Vector2(s, s)), false, c)
	if _chev_r != null and (wrap or index < options.size() - 1):
		draw_texture_rect(_chev_r, Rect2(Vector2(size.x - 16 - s, y), Vector2(s, s)), false, c)
	# position dots
	if options.size() > 1 and options.size() <= 8:
		var total := float(options.size() - 1) * 12.0
		var x0 := size.x * 0.5 - total * 0.5
		for i in options.size():
			var dc := UIStyle.LANTERN if i == index else Color(UIStyle.TEXT_MUTED, 0.5)
			draw_circle(Vector2(x0 + i * 12.0, size.y - 7.0), 2.6 if i == index else 2.0, dc)
