extends Control
## Studio splash: "Xưởng Mái Ngói" (Roof-Tile Workshop) — an ink-drawn row of curved roof tiles
## with a little cat sitting on the ridge under a rising moon, then "Made with Godot Engine".
## Any key / click / button skips. Frees itself when done (main.gd awaits tree_exited).

const HOLD := 2.2
const FADE := 0.7

var _t := 0.0
var _skipping := false
var _logo: Control
var _card2: Control


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	theme = UIStyle.theme()
	var bg := ColorRect.new()
	bg.color = Color("#0d0907")
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var grain := TextureRect.new()
	grain.texture = UIStyle.ui_tex("vignette")
	grain.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	grain.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	grain.stretch_mode = TextureRect.STRETCH_SCALE
	grain.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(grain)

	_logo = VBoxContainer.new()
	_logo.set_anchors_preset(Control.PRESET_CENTER)
	_logo.anchor_left = 0.5
	_logo.anchor_right = 0.5
	_logo.anchor_top = 0.5
	_logo.anchor_bottom = 0.5
	_logo.offset_left = -420
	_logo.offset_right = 420
	_logo.offset_top = -230
	_logo.offset_bottom = 230
	(_logo as VBoxContainer).alignment = BoxContainer.ALIGNMENT_CENTER
	(_logo as VBoxContainer).add_theme_constant_override(&"separation", 14)
	add_child(_logo)
	var art := _LogoArt.new()
	art.custom_minimum_size = Vector2(420, 220)
	art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_logo.add_child(art)
	var name_l := UIStyle.label(tr("STUDIO_NAME"), &"heading", 58, UIStyle.TEXT)
	name_l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_logo.add_child(name_l)
	var sub := UIStyle.label(tr("STUDIO_TAGLINE"), &"semibold", 18, UIStyle.GOLD)
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.uppercase = true
	_logo.add_child(sub)
	_logo.modulate.a = 0.0

	_card2 = VBoxContainer.new()
	_card2.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	(_card2 as VBoxContainer).alignment = BoxContainer.ALIGNMENT_CENTER
	add_child(_card2)
	var made := UIStyle.label(tr("SPLASH_MADE_WITH"), &"light", 26, UIStyle.TEXT_DIM)
	made.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_card2.add_child(made)
	var engine := UIStyle.label("Godot Engine", &"heading", 52, UIStyle.TEXT)
	engine.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_card2.add_child(engine)
	var plus := UIStyle.label(tr("SPLASH_AND_BLENDER"), &"light", 22, UIStyle.TEXT_MUTED)
	plus.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_card2.add_child(plus)
	_card2.modulate.a = 0.0
	_sequence()


func _sequence() -> void:
	var tw := create_tween()
	tw.tween_property(_logo, "modulate:a", 1.0, FADE).set_trans(Tween.TRANS_SINE)
	tw.tween_interval(HOLD)
	tw.tween_property(_logo, "modulate:a", 0.0, FADE)
	tw.tween_property(_card2, "modulate:a", 1.0, FADE * 0.8)
	tw.tween_interval(1.3)
	tw.tween_property(_card2, "modulate:a", 0.0, FADE * 0.8)
	tw.tween_property(self, "modulate:a", 0.0, 0.5)
	tw.tween_callback(queue_free)


func _input(event: InputEvent) -> void:
	if _skipping:
		return
	var skip := (event is InputEventKey or event is InputEventMouseButton or event is InputEventJoypadButton) and event.is_pressed()
	if skip:
		_skipping = true
		get_viewport().set_input_as_handled()
		var tw := create_tween()
		tw.tween_property(self, "modulate:a", 0.0, 0.35)
		tw.tween_callback(queue_free)


class _LogoArt extends Control:
	var t := 0.0

	func _process(delta: float) -> void:
		t += delta
		queue_redraw()

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var ink := Color("#f1e4c6")
		var gold := Color("#d9a441")
		# moon
		var mc := Vector2(w * 0.68, h * 0.30)
		draw_circle(mc, 44.0, Color(gold, 0.18))
		draw_circle(mc, 34.0, Color("#e9c27a"))
		# roof ridge line (gentle upturned eaves typical of old-quarter tile roofs)
		var base_y := h * 0.80
		var ridge: PackedVector2Array = []
		for i in 41:
			var u := float(i) / 40.0
			var x := lerpf(w * 0.06, w * 0.94, u)
			var y := base_y - 10.0 - pow(absf(u - 0.5) * 2.0, 3.0) * 26.0
			ridge.append(Vector2(x, y))
		draw_polyline(ridge, ink, 3.0, true)
		# row of curved half-round tiles
		var n := 13
		for i in n:
			var u := (float(i) + 0.5) / float(n)
			var x := lerpf(w * 0.08, w * 0.92, u)
			var top := base_y - 6.0 - pow(absf(u - 0.5) * 2.0, 3.0) * 26.0
			var r := (w * 0.84) / float(n) * 0.5
			draw_arc(Vector2(x, top + r * 0.9), r * 0.92, PI, TAU, 18, ink, 2.4, true)
			draw_line(Vector2(x - r * 0.92, top + r * 0.9), Vector2(x - r * 0.92, base_y + 22.0), Color(ink, 0.55), 1.6, true)
		draw_line(Vector2(w * 0.08, base_y + 22.0), Vector2(w * 0.92, base_y + 22.0), Color(ink, 0.8), 2.0, true)
		# the cat sitting on the ridge, tail swaying, ear twitch
		var cat_x := w * 0.40
		var cat_y := base_y - 10.0 - pow(absf(cat_x / w - 0.5) * 2.0, 3.0) * 26.0
		CatSilhouette.draw(self, Vector2(cat_x, cat_y), 0.62, 0.0, 1.0, ink, &"sit", t)
		# little red seal under the name
		var seal := UIStyle.ui_tex("seal_stamp")
		if seal != null:
			draw_texture_rect(seal, Rect2(Vector2(w * 0.86, h * 0.02), Vector2(54, 54)), false)
