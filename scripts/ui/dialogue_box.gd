class_name DialogueBox
extends Control
## Dialogue UI. Bottom band of warm lacquer with a red name tag, a speaker medallion, the line
## typed out in Lora (speed = gameplay/text_speed), and Cam's replies as cat-action chips with
## glyphs (meow, purr, slow blink…). Locked choices show their requirement. Driven entirely by
## GameEvents.dialogue_started / dialogue_node_shown / dialogue_ended; answers with
## DialogueManager.advance() / choose(i).

signal line_finished()

const BASE_CPS := 42.0
const SPEAKER_GLYPHS := {
	"mun": &"cat", "bong": &"cat", "ong_muop": &"cat", "cam": &"cat",
	"lao_qua": &"crow", "xam": &"crow", "ven": &"dog",
}

var active := false
var typing := false
var _info: Dictionary = {}
var _chars := 0.0
var _total := 0
var _band: Control
var _panel: PanelContainer
var _name_tag: PanelContainer
var _name_label: Label
var _medallion: _Medallion
var _text: RichTextLabel
var _choices: VBoxContainer
var _continue: HBoxContainer
var _continue_glyph: UIInputGlyph
var _blink := 0.0
var _choice_buttons: Array[Button] = []
var _input_cooldown := 0.0
var _prev_mouse_mode := Input.MOUSE_MODE_VISIBLE


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	process_mode = Node.PROCESS_MODE_ALWAYS
	theme = UIStyle.theme()
	_build()
	visible = false
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"dialogue_started", _on_started)
		ge.connect(&"dialogue_node_shown", show_node)
		ge.connect(&"dialogue_ended", _on_ended)


func _build() -> void:
	_band = Control.new()
	_band.anchor_left = 0.0
	_band.anchor_right = 1.0
	_band.anchor_top = 1.0
	_band.anchor_bottom = 1.0
	_band.offset_top = -420
	_band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_band)
	# soft dark gradient rising from the bottom edge
	var grad := TextureRect.new()
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	g.colors = PackedColorArray([Color(0.03, 0.02, 0.015, 0.0), Color(0.03, 0.02, 0.015, 0.55), Color(0.03, 0.02, 0.015, 0.86)])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill_from = Vector2(0.5, 0.0)
	gt.fill_to = Vector2(0.5, 1.0)
	gt.width = 4
	gt.height = 128
	grad.texture = gt
	grad.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	grad.stretch_mode = TextureRect.STRETCH_SCALE
	grad.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	grad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_band.add_child(grad)

	var row := HBoxContainer.new()
	row.anchor_left = 0.5
	row.anchor_right = 0.5
	row.anchor_top = 1.0
	row.anchor_bottom = 1.0
	row.offset_left = -820
	row.offset_right = 820
	row.offset_top = -330
	row.offset_bottom = -48
	row.add_theme_constant_override(&"separation", 28)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_band.add_child(row)

	_medallion = _Medallion.new()
	_medallion.custom_minimum_size = Vector2(150, 150)
	_medallion.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	row.add_child(_medallion)

	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override(&"separation", 10)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(col)
	_name_tag = PanelContainer.new()
	var tag := StyleBoxTexture.new()
	tag.texture = UIStyle.ui_tex("nameplate")
	tag.texture_margin_left = 28
	tag.texture_margin_right = 28
	tag.texture_margin_top = 18
	tag.texture_margin_bottom = 18
	tag.content_margin_left = 30
	tag.content_margin_right = 30
	tag.content_margin_top = 6
	tag.content_margin_bottom = 8
	_name_tag.add_theme_stylebox_override(&"panel", tag)
	_name_tag.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_name_tag.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(_name_tag)
	_name_label = UIStyle.label("", &"heading", 30, Color("#fff3dc"))
	_name_tag.add_child(_name_label)
	_text = UIStyle.rich("", 31, UIStyle.TEXT, &"prose")
	_text.theme_type_variation = &"ProseText"
	_text.add_theme_font_size_override(&"normal_font_size", 31)
	_text.add_theme_font_size_override(&"italics_font_size", 31)
	_text.add_theme_font_size_override(&"bold_font_size", 31)
	_text.add_theme_constant_override(&"line_separation", 9)
	_text.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.6))
	_text.add_theme_constant_override(&"shadow_offset_y", 2)
	_text.add_theme_constant_override(&"shadow_outline_size", 4)
	_text.fit_content = true
	_text.custom_minimum_size = Vector2(0, 120)
	_text.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(_text)
	_continue = HBoxContainer.new()
	_continue.alignment = BoxContainer.ALIGNMENT_END
	_continue.add_theme_constant_override(&"separation", 10)
	_continue.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(_continue)
	var paw := UIStyle.icon_rect(UIStyle.glyph(&"paw"), 22, UIStyle.LANTERN_GLOW)
	_continue.add_child(paw)
	_continue_glyph = UIInputGlyph.new()
	_continue_glyph.action = &"interact"
	_continue_glyph.glyph_height = 30.0
	_continue.add_child(_continue_glyph)
	_continue.add_child(UIStyle.label(tr("DLG_CONTINUE"), &"medium", 19, UIStyle.TEXT_DIM))

	_choices = VBoxContainer.new()
	_choices.custom_minimum_size = Vector2(560, 0)
	_choices.size_flags_vertical = Control.SIZE_SHRINK_END
	_choices.add_theme_constant_override(&"separation", 8)
	row.add_child(_choices)


func _on_started(_dialogue_id: StringName, _speaker_id: StringName) -> void:
	active = true
	visible = true
	_input_cooldown = 0.25
	if DisplayServer.get_name() != "headless":
		_prev_mouse_mode = Input.mouse_mode
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	modulate.a = 0.0
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(self, "modulate:a", 1.0, 0.25)


func _on_ended(_dialogue_id: StringName) -> void:
	active = false
	typing = false
	_clear_choices()
	if DisplayServer.get_name() != "headless" and _prev_mouse_mode == Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(self, "modulate:a", 0.0, 0.25)
	tw.tween_callback(func() -> void:
		if not active:
			visible = false)


## Shows one dialogue node (DialogueManager's info dictionary). Public for previews/tests.
func show_node(info: Dictionary) -> void:
	if not active:
		active = true
		visible = true
		modulate.a = 1.0
	_info = info
	var speaker := String(info.get("speaker_name", ""))
	_name_label.text = speaker
	_name_tag.visible = speaker != ""
	_medallion.setup(String(info.get("speaker_id", "")), speaker, String(info.get("portrait", "")))
	_text.text = String(info.get("text", ""))
	_total = _text.get_total_character_count()
	_chars = 0.0
	_text.visible_characters = 0
	typing = true
	_clear_choices()
	_continue.visible = false
	if bool(UIStyle.settings_value("gameplay", "subtitles", true)) == false:
		pass  # dialogue is always shown; the setting only affects ambient subtitles


func _clear_choices() -> void:
	for c in _choices.get_children():
		c.queue_free()
	_choice_buttons.clear()


func finish_typing() -> void:
	if not typing:
		return
	typing = false
	_text.visible_characters = -1
	line_finished.emit()
	_show_after_text()


func _show_after_text() -> void:
	var choices: Array = _info.get("choices", [])
	if choices.is_empty():
		_continue.visible = true
		return
	var i := 0
	for c: Dictionary in choices:
		var b := Button.new()
		b.theme_type_variation = &"ChipButton"
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		b.custom_minimum_size = Vector2(640, 58)
		var txt := String(c.get("text", ""))
		if not bool(c.get("enabled", true)):
			txt += "\n" + tr("DLG_REQUIRES").format({"req": String(c.get("requirement", ""))})
			b.disabled = true
		b.text = txt
		b.icon = UIStyle.glyph(StringName(String(c.get("action", "meow"))), "actions")
		b.expand_icon = false
		var idx := i
		b.pressed.connect(func() -> void: _choose(idx))
		_choices.add_child(b)
		_choice_buttons.append(b)
		b.modulate.a = 0.0
		var tw := b.create_tween()
		tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
		tw.tween_property(b, "modulate:a", 1.0, 0.2).set_delay(0.06 * i)
		i += 1
	for j in _choice_buttons.size():
		var b := _choice_buttons[j]
		b.focus_neighbor_top = b.get_path_to(_choice_buttons[(j - 1 + _choice_buttons.size()) % _choice_buttons.size()])
		b.focus_neighbor_bottom = b.get_path_to(_choice_buttons[(j + 1) % _choice_buttons.size()])
	UIStyle.wire_sounds(_choices)
	for b in _choice_buttons:
		if not b.disabled:
			b.grab_focus.call_deferred()
			break


func _choose(index: int) -> void:
	var dm := get_node_or_null(^"/root/DialogueManager")
	if dm != null:
		dm.call("choose", index)


func _advance() -> void:
	if typing:
		finish_typing()
		return
	if not (_info.get("choices", []) as Array).is_empty():
		return
	UIStyle.sfx(&"ui_dialogue_next")
	var dm := get_node_or_null(^"/root/DialogueManager")
	if dm != null:
		dm.call("advance")


func get_choice_buttons() -> Array[Button]:
	return _choice_buttons


func _process(delta: float) -> void:
	_input_cooldown = maxf(0.0, _input_cooldown - delta)
	if typing:
		var speed := BASE_CPS * float(UIStyle.settings_value("gameplay", "text_speed", 1.0))
		_chars += delta * speed
		_text.visible_characters = int(_chars)
		if int(_chars) >= _total:
			finish_typing()
	_blink += delta
	if _continue.visible:
		_continue.modulate.a = 0.55 + 0.45 * sin(_blink * 4.0)
	_medallion.queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if not active or _input_cooldown > 0.0 or not event.is_pressed() or event.is_echo():
		return
	var adv := event.is_action_pressed(&"interact") or event.is_action_pressed(&"ui_accept")
	if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		adv = true
	if adv and (typing or (_info.get("choices", []) as Array).is_empty()):
		get_viewport().set_input_as_handled()
		_advance()


## Speaker medallion: portrait if assets/ui/portraits/<id>.png exists, else a glyph (cats, crows,
## the dog) or an engraved monogram for people, on a lacquer disc with a gold rim.
class _Medallion extends Control:
	var _tex: Texture2D = null
	var _glyph: Texture2D = null
	var _mono := ""
	var t := 0.0

	func setup(speaker_id: String, speaker_name: String, portrait: String) -> void:
		_tex = null
		_glyph = null
		_mono = ""
		var p := portrait if portrait != "" else "res://assets/ui/portraits/%s.png" % speaker_id
		_tex = UIStyle.tex(p)
		if _tex == null:
			var gname: StringName = DialogueBox.SPEAKER_GLYPHS.get(speaker_id, &"")
			if gname != &"":
				_glyph = UIStyle.glyph(gname)
			else:
				var words := speaker_name.strip_edges().split(" ", false)
				_mono = words[words.size() - 1].left(1).to_upper() if words.size() > 0 else "?"
		visible = true
		queue_redraw()

	func _draw() -> void:
		t += 0.016
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.5 - 4.0
		draw_circle(c + Vector2(0, 4), r, Color(0, 0, 0, 0.45))
		draw_circle(c, r, Color("#2a1a12"))
		draw_circle(c, r - 8.0, Color("#3a2217"))
		if _tex != null:
			draw_texture_rect(_tex, Rect2(c - Vector2(r - 8, r - 8), Vector2(r - 8, r - 8) * 2.0), false)
		elif _glyph != null:
			var s := r * 1.05
			draw_texture_rect(_glyph, Rect2(c - Vector2(s, s) * 0.5, Vector2(s, s)), false, Color("#f2cf7e"))
		elif _mono != "":
			var f := UIStyle.font(&"title")
			var fs := int(r * 1.1)
			var ts := f.get_string_size(_mono, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
			draw_string(f, Vector2(c.x - ts.x * 0.5, c.y + f.get_ascent(fs) * 0.36), _mono, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color("#f2cf7e"))
		draw_arc(c, r, 0.0, TAU, 64, Color("#d9a441"), 3.0, true)
		draw_arc(c, r - 8.0, 0.0, TAU, 64, Color("#d9a441", 0.45), 1.2, true)
		for i in 8:
			var a := TAU * float(i) / 8.0 + PI / 8.0
			draw_circle(c + Vector2.from_angle(a) * (r - 4.0), 1.8, Color("#f2cf7e"))
