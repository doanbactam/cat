extends UIScreen
## Credits (Đội ngũ): a slowly scrolling scroll of rice paper with the studio, disciplines, tools,
## fonts and licences; Cam's silhouette walks along the bottom. Up/down (or the stick) scrolls
## manually; it loops.

const SPEED := 46.0

var _scroll_root: Control
var _column: VBoxContainer
var _offset := 0.0
var _manual := 0.0
var _t := 0.0
var _walker: Control


func _init() -> void:
	menu_id = &"credits"


func build() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.035, 0.028, 0.88)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	_scroll_root = Control.new()
	_scroll_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_scroll_root.clip_contents = true
	_scroll_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_scroll_root)
	_column = VBoxContainer.new()
	_column.custom_minimum_size = Vector2(1000, 0)
	_column.add_theme_constant_override(&"separation", 10)
	_scroll_root.add_child(_column)
	_fill()
	var hints := UIHintBar.new()
	hints.set_hints([["@↑ / ↓|LS", "UI_SCROLL"], [&"ui_cancel", "UI_BACK"]])
	hints.anchor_left = 0.0
	hints.anchor_right = 1.0
	hints.anchor_top = 1.0
	hints.anchor_bottom = 1.0
	hints.offset_top = -70
	hints.offset_bottom = -30
	hints.offset_right = -72
	add_child(hints)
	_walker = _Walker.new()
	_walker.anchor_left = 0.0
	_walker.anchor_right = 1.0
	_walker.anchor_top = 1.0
	_walker.anchor_bottom = 1.0
	_walker.offset_top = -120
	_walker.offset_bottom = -76
	_walker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_walker)
	var close := Button.new()
	close.text = tr("BTN_CLOSE")
	close.position = Vector2(72, 48)
	close.pressed.connect(request_close)
	add_child(close)


func _add(text: String, kind: StringName, size: int, color: Color, gap: int = 0) -> void:
	if gap > 0:
		var s := Control.new()
		s.custom_minimum_size = Vector2(0, gap)
		_column.add_child(s)
	var l := UIStyle.label(text, kind, size, color)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size = Vector2(1000, 0)
	_column.add_child(l)


func _fill() -> void:
	var top := Control.new()
	top.custom_minimum_size = Vector2(0, 1080)
	_column.add_child(top)
	var seal := UIStyle.icon_rect(UIStyle.ui_tex("seal_stamp"), 110)
	seal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_column.add_child(seal)
	_add(tr("GAME_TITLE"), &"title", 76, UIStyle.TEXT, 10)
	_add(tr("CREDITS_A_GAME_BY"), &"prose_italic", 28, UIStyle.TEXT_DIM, 4)
	_add(tr("STUDIO_NAME"), &"heading", 46, UIStyle.GOLD_LIGHT)
	var sections := [
		["CREDITS_DIRECTION", ["CREDITS_DIRECTION_BODY"]],
		["CREDITS_DESIGN", ["CREDITS_DESIGN_BODY"]],
		["CREDITS_CAT", ["CREDITS_CAT_BODY"]],
		["CREDITS_CITY", ["CREDITS_CITY_BODY"]],
		["CREDITS_PLAYER", ["CREDITS_PLAYER_BODY"]],
		["CREDITS_SYSTEMS", ["CREDITS_SYSTEMS_BODY"]],
		["CREDITS_LIFE", ["CREDITS_LIFE_BODY"]],
		["CREDITS_AUDIO", ["CREDITS_AUDIO_BODY"]],
		["CREDITS_UI", ["CREDITS_UI_BODY"]],
		["CREDITS_TOOLS", ["CREDITS_TOOLS_BODY"]],
		["CREDITS_FONTS", ["CREDITS_FONTS_BODY"]],
		["CREDITS_THANKS", ["CREDITS_THANKS_BODY"]],
	]
	for s: Array in sections:
		var d := UIStyle.divider(360, Color(UIStyle.GOLD, 0.55))
		d.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		var gap := Control.new()
		gap.custom_minimum_size = Vector2(0, 46)
		_column.add_child(gap)
		_column.add_child(d)
		_add(tr(String(s[0])), &"semibold", 20, UIStyle.GOLD)
		for body: String in s[1]:
			_add(tr(body), &"prose", 27, UIStyle.TEXT, 2)
	_add(tr("CREDITS_ORIGINAL"), &"body_italic", 20, UIStyle.TEXT_MUTED, 60)
	_add(tr("CREDITS_END"), &"heading_italic", 40, UIStyle.TEXT, 120)
	var bottom := Control.new()
	bottom.custom_minimum_size = Vector2(0, 700)
	_column.add_child(bottom)


func default_focus() -> Control:
	return null


func _process(delta: float) -> void:
	_t += delta
	var axis := Input.get_axis(&"ui_up", &"ui_down")
	_manual = lerpf(_manual, axis * 900.0, clampf(delta * 6.0, 0.0, 1.0))
	_offset += (SPEED + _manual) * delta
	var total := _column.get_combined_minimum_size().y
	if total > 0.0:
		_offset = fposmod(_offset, total)
	var w := size.x if size.x > 0.0 else 1920.0
	_column.position = Vector2((w - 1000.0) * 0.5, -_offset)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_offset += 90.0
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_offset -= 90.0


class _Walker extends Control:
	var t := 0.0

	func _process(delta: float) -> void:
		t += delta
		queue_redraw()

	func _draw() -> void:
		var w := size.x
		var y := size.y
		draw_line(Vector2(0, y - 1), Vector2(w, y - 1), Color(0.85, 0.64, 0.25, 0.35), 1.5, true)
		var x := fposmod(t * 70.0, w + 300.0) - 150.0
		CatSilhouette.draw(self, Vector2(x, y - 2), 0.32, t * 1.2, 1.0, Color(0.95, 0.89, 0.78, 0.85), &"walk", t)
