class_name UIInputGlyph
extends Control
## Draws the binding of an input action as a key cap (keyboard), a mouse (mouse buttons) or a
## gamepad button (Xbox-style layout: A/B/X/Y colours, LB/RB/LT/RT, sticks, d-pad, menu).
## Switches automatically when Settings.input_device_changed fires.
## Set `action` (InputMap name) or `fixed_label` (raw text such as "Enter") before adding.

@export var action: StringName = &""
@export var fixed_label := ""
@export var glyph_height := 34.0
## Force a device (-1 auto, 0 keyboard/mouse, 1 gamepad).
@export var force_device := -1

const PAD_NAMES := {
	JOY_BUTTON_A: "A", JOY_BUTTON_B: "B", JOY_BUTTON_X: "X", JOY_BUTTON_Y: "Y",
	JOY_BUTTON_LEFT_SHOULDER: "LB", JOY_BUTTON_RIGHT_SHOULDER: "RB", JOY_BUTTON_BACK: "View",
	JOY_BUTTON_START: "Menu", JOY_BUTTON_LEFT_STICK: "LS", JOY_BUTTON_RIGHT_STICK: "RS",
	JOY_BUTTON_DPAD_UP: "↑", JOY_BUTTON_DPAD_DOWN: "↓", JOY_BUTTON_DPAD_LEFT: "←", JOY_BUTTON_DPAD_RIGHT: "→",
	JOY_BUTTON_GUIDE: "⌂", JOY_BUTTON_MISC1: "Share",
}
const FACE_COLORS := {
	"A": Color("#6dbb58"), "B": Color("#e0503c"), "X": Color("#4a8fe0"), "Y": Color("#e8c23a"),
}

var _kind := &"key"      # key | mouse | pad_face | pad_shoulder | pad_stick | pad_other | none
var _text := ""
var _mouse_button := 0
var _font: Font
var _font_size := 18


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_font = UIStyle.font(&"bold")
	var s := get_node_or_null(^"/root/Settings")
	if s != null and s.has_signal(&"input_device_changed"):
		s.connect(&"input_device_changed", func(_p: bool) -> void: refresh())
	if s != null and s.has_signal(&"bindings_changed"):
		s.connect(&"bindings_changed", refresh)
	refresh()


func set_action(a: StringName) -> void:
	action = a
	fixed_label = ""
	refresh()


func refresh() -> void:
	var pad := UIStyle.using_gamepad() if force_device < 0 else force_device == 1
	_kind = &"none"
	_text = ""
	if fixed_label != "":
		_kind = &"key"
		_text = fixed_label
	elif action != &"" and InputMap.has_action(action):
		var ev := _pick_event(pad)
		if ev == null and pad:
			ev = _pick_event(false)
		_describe(ev)
	_font_size = int(glyph_height * 0.5)
	custom_minimum_size = Vector2(_glyph_width(), glyph_height)
	update_minimum_size()
	queue_redraw()


func _pick_event(pad: bool) -> InputEvent:
	for ev in InputMap.action_get_events(action):
		var is_pad := ev is InputEventJoypadButton or ev is InputEventJoypadMotion
		if is_pad == pad:
			return ev
	return null


func _describe(ev: InputEvent) -> void:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		_kind = &"key"
		_text = key_label(k)
	elif ev is InputEventMouseButton:
		_kind = &"mouse"
		_mouse_button = int((ev as InputEventMouseButton).button_index)
		match _mouse_button:
			MOUSE_BUTTON_WHEEL_UP:
				_text = "▲"
			MOUSE_BUTTON_WHEEL_DOWN:
				_text = "▼"
			_:
				_text = ""
	elif ev is InputEventJoypadButton:
		var b := int((ev as InputEventJoypadButton).button_index)
		_text = String(PAD_NAMES.get(b, str(b)))
		if _text in ["A", "B", "X", "Y"]:
			_kind = &"pad_face"
		elif _text in ["LB", "RB"]:
			_kind = &"pad_shoulder"
		elif _text in ["LS", "RS"]:
			_kind = &"pad_stick"
		else:
			_kind = &"pad_other"
	elif ev is InputEventJoypadMotion:
		var m := ev as InputEventJoypadMotion
		match m.axis:
			JOY_AXIS_TRIGGER_LEFT:
				_kind = &"pad_shoulder"
				_text = "LT"
			JOY_AXIS_TRIGGER_RIGHT:
				_kind = &"pad_shoulder"
				_text = "RT"
			JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y:
				_kind = &"pad_stick"
				_text = "LS"
			_:
				_kind = &"pad_stick"
				_text = "RS"


static func key_label(k: InputEventKey) -> String:
	var code := k.physical_keycode if k.physical_keycode != KEY_NONE else k.keycode
	if k.physical_keycode != KEY_NONE and DisplayServer.get_name() != "headless":
		var mapped := DisplayServer.keyboard_get_keycode_from_physical(k.physical_keycode)
		if mapped != KEY_NONE:
			code = mapped
	match code:
		KEY_SPACE:
			return "Space"
		KEY_ESCAPE:
			return "Esc"
		KEY_ENTER, KEY_KP_ENTER:
			return "Enter"
		KEY_SHIFT:
			return "Shift"
		KEY_CTRL:
			return "Ctrl"
		KEY_ALT:
			return "Alt"
		KEY_TAB:
			return "Tab"
		KEY_UP:
			return "↑"
		KEY_DOWN:
			return "↓"
		KEY_LEFT:
			return "←"
		KEY_RIGHT:
			return "→"
		KEY_BACKSPACE:
			return "⌫"
	return OS.get_keycode_string(code)


## Short text form of an action's binding (for the controls list and plain-text prompts).
static func action_text(a: StringName, pad: bool) -> String:
	if not InputMap.has_action(a):
		return "—"
	for ev in InputMap.action_get_events(a):
		var is_pad := ev is InputEventJoypadButton or ev is InputEventJoypadMotion
		if is_pad != pad:
			continue
		if ev is InputEventKey:
			return key_label(ev as InputEventKey)
		if ev is InputEventMouseButton:
			match int((ev as InputEventMouseButton).button_index):
				MOUSE_BUTTON_LEFT:
					return TranslationServer.translate("KEY_MOUSE_LEFT")
				MOUSE_BUTTON_RIGHT:
					return TranslationServer.translate("KEY_MOUSE_RIGHT")
				MOUSE_BUTTON_MIDDLE:
					return TranslationServer.translate("KEY_MOUSE_MIDDLE")
				MOUSE_BUTTON_WHEEL_UP:
					return TranslationServer.translate("KEY_WHEEL_UP")
				MOUSE_BUTTON_WHEEL_DOWN:
					return TranslationServer.translate("KEY_WHEEL_DOWN")
			return "Mouse %d" % int((ev as InputEventMouseButton).button_index)
		if ev is InputEventJoypadButton:
			return String(PAD_NAMES.get(int((ev as InputEventJoypadButton).button_index), "?"))
		if ev is InputEventJoypadMotion:
			match (ev as InputEventJoypadMotion).axis:
				JOY_AXIS_TRIGGER_LEFT:
					return "LT"
				JOY_AXIS_TRIGGER_RIGHT:
					return "RT"
				JOY_AXIS_LEFT_X, JOY_AXIS_LEFT_Y:
					return "LS"
			return "RS"
	return "—"


func _glyph_width() -> float:
	var h := glyph_height
	match _kind:
		&"none":
			return 0.0
		&"pad_face", &"pad_stick":
			return h
		&"mouse":
			return h * 0.78
		_:
			var tw := _font.get_string_size(_text, HORIZONTAL_ALIGNMENT_LEFT, -1, _font_size).x if _font != null else 10.0
			return maxf(h, tw + h * 0.62)


func _draw() -> void:
	var h := glyph_height
	var w := _glyph_width()
	var r := Rect2(Vector2(0, (size.y - h) * 0.5), Vector2(w, h))
	match _kind:
		&"key":
			_draw_key(r)
		&"mouse":
			_draw_mouse(r)
		&"pad_face":
			var c := r.get_center()
			draw_circle(c + Vector2(0, 1.5), h * 0.5, Color(0, 0, 0, 0.45))
			draw_circle(c, h * 0.5, Color("#1d1814"))
			draw_arc(c, h * 0.5 - 1.0, 0, TAU, 32, Color(1, 1, 1, 0.18), 1.5, true)
			_draw_text_centered(r, _text, FACE_COLORS.get(_text, UIStyle.TEXT))
		&"pad_stick":
			var c := r.get_center()
			draw_circle(c, h * 0.5, Color("#1d1814"))
			draw_arc(c, h * 0.36, 0, TAU, 32, Color(1, 1, 1, 0.45), 2.0, true)
			_draw_text_centered(r, _text, UIStyle.TEXT)
		&"pad_shoulder", &"pad_other":
			var sb := UIStyle.flat_box(Color("#1d1814"), int(h * 0.3), Color(1, 1, 1, 0.22), 1)
			draw_style_box(sb, r)
			_draw_text_centered(r, _text, UIStyle.TEXT)


func _draw_key(r: Rect2) -> void:
	var shadow := UIStyle.flat_box(Color(0, 0, 0, 0.5), 7)
	draw_style_box(shadow, Rect2(r.position + Vector2(0, 2.5), r.size))
	var cap := UIStyle.flat_box(Color("#efe2c4"), 7, Color("#8a6a32"), 1)
	cap.border_width_bottom = 3
	draw_style_box(cap, r)
	_draw_text_centered(Rect2(r.position + Vector2(0, -1), r.size), _text, UIStyle.TEXT_INK)


func _draw_mouse(r: Rect2) -> void:
	var body := Rect2(r.position + Vector2(r.size.x * 0.08, 0), Vector2(r.size.x * 0.84, r.size.y))
	var sb := UIStyle.flat_box(Color("#efe2c4"), int(body.size.x * 0.45), Color("#8a6a32"), 1)
	draw_style_box(sb, body)
	var mid := body.position.x + body.size.x * 0.5
	var top := body.position.y
	var split := top + body.size.y * 0.42
	draw_line(Vector2(body.position.x + 2, split), Vector2(body.end.x - 2, split), Color("#8a6a32"), 1.2)
	draw_line(Vector2(mid, top + 2), Vector2(mid, split), Color("#8a6a32"), 1.2)
	var hl := Color("#c8452a")
	match _mouse_button:
		MOUSE_BUTTON_LEFT:
			draw_rect(Rect2(body.position + Vector2(3, 3), Vector2(body.size.x * 0.5 - 4, split - top - 4)), hl)
		MOUSE_BUTTON_RIGHT:
			draw_rect(Rect2(Vector2(mid + 1, top + 3), Vector2(body.size.x * 0.5 - 4, split - top - 4)), hl)
		_:
			draw_rect(Rect2(Vector2(mid - 2.5, top + 4), Vector2(5, split - top - 8)), hl)
			if _text != "":
				_draw_text_centered(Rect2(Vector2(body.position.x, split), Vector2(body.size.x, body.end.y - split)), _text, UIStyle.TEXT_INK)


func _draw_text_centered(r: Rect2, t: String, c: Color) -> void:
	if _font == null or t == "":
		return
	var fs := _font_size if t.length() <= 2 else int(_font_size * 0.86)
	var ts := _font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
	var asc := _font.get_ascent(fs)
	var desc := _font.get_descent(fs)
	var pos := Vector2(r.position.x + (r.size.x - ts.x) * 0.5, r.position.y + (r.size.y + asc - desc) * 0.5)
	draw_string(_font, pos, t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, c)
