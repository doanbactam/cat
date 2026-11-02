extends Control
## Loading screen (instanced by SceneLoader). A painted full-moon night over the old quarter's
## rooftops: a power line strung with silk lanterns crosses the screen and Cam's silhouette
## balance-walks along it — the cat's position and the lit lanterns show the load progress.
## A rotating tip (TIP_01..) sits at the bottom.

const TIP_COUNT := 24
const TIP_SECONDS := 7.0
const LANTERNS := 9

var progress := 0.0
var _shown := 0.0          # smoothed progress the cat follows
var _t := 0.0
var _tip_t := 0.0
var _tip_index := -1
var _rng := RandomNumberGenerator.new()
var _skyline: Array[Dictionary] = []
var _stars: PackedVector2Array = []
var _sky: TextureRect
var _tip_label: RichTextLabel
var _status: Label
var _percent: Label
var _lantern_tex: Texture2D
var _glow_tex: Texture2D


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	theme = UIStyle.theme()
	_rng.seed = 7341
	_lantern_tex = UIStyle.ui_tex("lantern")
	_glow_tex = UIStyle.ui_tex("glow_soft")
	_build()
	_tip_index = randi() % TIP_COUNT
	_show_tip()
	resized.connect(_build_skyline)
	_build_skyline()


func set_progress(p: float) -> void:
	progress = clampf(p, 0.0, 1.0)
	if _percent != null:
		_percent.text = "%d%%" % int(round(_shown * 100.0))


func _build() -> void:
	_sky = TextureRect.new()
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.45, 0.78, 1.0])
	g.colors = PackedColorArray([Color("#0b0d1a"), Color("#1a1626"), Color("#3a2420"), Color("#5a3220")])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill_from = Vector2(0.5, 0.0)
	gt.fill_to = Vector2(0.5, 1.0)
	gt.width = 16
	gt.height = 256
	_sky.texture = gt
	_sky.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_sky.stretch_mode = TextureRect.STRETCH_SCALE
	_sky.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_sky.show_behind_parent = true
	_sky.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_sky)

	var bottom := VBoxContainer.new()
	bottom.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	bottom.anchor_left = 0.15
	bottom.anchor_right = 0.85
	bottom.anchor_top = 1.0
	bottom.anchor_bottom = 1.0
	bottom.offset_top = -170
	bottom.offset_bottom = -48
	bottom.alignment = BoxContainer.ALIGNMENT_END
	bottom.add_theme_constant_override(&"separation", 10)
	add_child(bottom)
	var cap := UIStyle.label(tr("UI_TIP_HEADER"), &"semibold", 17, UIStyle.GOLD)
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.uppercase = true
	bottom.add_child(cap)
	_tip_label = UIStyle.rich("", 27, UIStyle.TEXT, &"prose")
	_tip_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_tip_label.add_theme_font_override(&"normal_font", UIStyle.font(&"prose_italic"))
	bottom.add_child(_tip_label)

	var status_box := HBoxContainer.new()
	status_box.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	status_box.offset_left = -360
	status_box.offset_top = -64
	status_box.offset_right = -56
	status_box.offset_bottom = -30
	status_box.alignment = BoxContainer.ALIGNMENT_END
	add_child(status_box)
	_status = UIStyle.label(tr("UI_LOADING"), &"medium", 20, UIStyle.TEXT_DIM)
	status_box.add_child(_status)
	_percent = UIStyle.label("0%", &"semibold", 20, UIStyle.GOLD_LIGHT)
	status_box.add_child(_percent)

	var title := UIStyle.label(tr("GAME_TITLE"), &"heading_italic", 30, Color(UIStyle.TEXT, 0.75))
	title.position = Vector2(56, 40)
	add_child(title)


func _build_skyline() -> void:
	_skyline.clear()
	_stars.clear()
	var w := size.x if size.x > 0.0 else 1920.0
	var h := size.y if size.y > 0.0 else 1080.0
	_rng.seed = 7341
	var x := -20.0
	while x < w + 40.0:
		var bw := _rng.randf_range(70.0, 170.0)
		var bh := _rng.randf_range(0.16, 0.36) * h
		var b := {"x": x, "w": bw, "h": bh, "tank": _rng.randf() < 0.35, "antenna": _rng.randf() < 0.3,
			"roof": _rng.randi() % 3, "windows": []}
		var wins: Array = []
		var rows := int(bh / 46.0)
		var cols := int(bw / 34.0)
		for r in rows:
			for c in cols:
				if _rng.randf() < 0.22:
					wins.append(Vector2(x + 12.0 + c * 32.0, h - bh + 26.0 + r * 46.0))
		b["windows"] = wins
		_skyline.append(b)
		x += bw + _rng.randf_range(-6.0, 4.0)
	for i in 90:
		_stars.append(Vector2(_rng.randf() * w, _rng.randf() * h * 0.45))


func _process(delta: float) -> void:
	_t += delta
	_shown = move_toward(_shown, progress, delta * 0.9)
	if _percent != null:
		_percent.text = "%d%%" % int(round(_shown * 100.0))
	_tip_t += delta
	if _tip_t > TIP_SECONDS:
		_tip_t = 0.0
		_tip_index = (_tip_index + 1) % TIP_COUNT
		_show_tip()
	queue_redraw()


func _show_tip() -> void:
	var key := "TIP_%02d" % (_tip_index + 1)
	_tip_label.text = "[center]" + tr(key) + "[/center]"
	_tip_label.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(_tip_label, "modulate:a", 1.0, 0.6)


func _wire_y(x: float, w: float, h: float) -> float:
	var y0 := h * 0.50
	var y1 := h * 0.47
	var u := x / w
	return lerpf(y0, y1, u) + sin(u * PI) * h * 0.07


func _draw() -> void:
	var w := size.x
	var h := size.y
	if w < 8.0 or h < 8.0:
		return  # not laid out yet (first frame / headless)
	# stars
	for i in _stars.size():
		var tw := 0.45 + 0.55 * absf(sin(_t * 0.7 + float(i) * 1.37))
		draw_circle(_stars[i], 1.2 + float(i % 3) * 0.5, Color(1.0, 0.95, 0.85, 0.35 * tw))
	# full moon with halo (Mid-Autumn)
	var moon := Vector2(w * 0.78, h * 0.2)
	if _glow_tex != null:
		draw_texture_rect(_glow_tex, Rect2(moon - Vector2(260, 260), Vector2(520, 520)), false, Color(1.0, 0.85, 0.6, 0.22))
	draw_circle(moon, 62.0, Color("#f6e2b4"))
	draw_circle(moon + Vector2(-16, -10), 13.0, Color("#e8d0a0"))
	draw_circle(moon + Vector2(18, 14), 9.0, Color("#ead3a4"))
	draw_circle(moon + Vector2(6, -26), 6.0, Color("#e9d2a2"))
	# skyline silhouettes
	var sil := Color("#120d0c")
	for b: Dictionary in _skyline:
		var x := float(b["x"])
		var bw := float(b["w"])
		var bh := float(b["h"])
		var top := h - bh
		draw_rect(Rect2(x, top, bw, bh), sil)
		match int(b["roof"]):
			1:
				draw_colored_polygon(PackedVector2Array([Vector2(x - 6, top), Vector2(x + bw * 0.5, top - 26), Vector2(x + bw + 6, top)]), sil)
			2:
				draw_rect(Rect2(x + bw * 0.1, top - 10, bw * 0.8, 10), sil)
		if b["tank"]:
			draw_rect(Rect2(x + bw * 0.55, top - 34, 30, 22), sil)
			draw_line(Vector2(x + bw * 0.57, top - 12), Vector2(x + bw * 0.57, top), sil, 3)
			draw_line(Vector2(x + bw * 0.55 + 28, top - 12), Vector2(x + bw * 0.55 + 28, top), sil, 3)
		if b["antenna"]:
			draw_line(Vector2(x + bw * 0.25, top), Vector2(x + bw * 0.25, top - 46), sil, 2)
			draw_line(Vector2(x + bw * 0.25 - 14, top - 38), Vector2(x + bw * 0.25 + 14, top - 38), sil, 2)
		for wp: Vector2 in b["windows"]:
			var flick := 0.8 + 0.2 * sin(_t * 0.5 + wp.x * 0.01)
			draw_rect(Rect2(wp, Vector2(14, 20)), Color(1.0, 0.68, 0.32, 0.55 * flick))
	# far wires
	for k in 3:
		var pts: PackedVector2Array = []
		for i in 33:
			var x := w * float(i) / 32.0
			pts.append(Vector2(x, h * (0.58 + 0.05 * k) + sin(float(i) / 32.0 * PI) * h * 0.04))
		draw_polyline(pts, Color(0.02, 0.015, 0.012, 0.85), 1.6, true)
	# the lantern wire
	var wire: PackedVector2Array = []
	for i in 65:
		var x := w * float(i) / 64.0
		wire.append(Vector2(x, _wire_y(x, w, h)))
	draw_polyline(wire, Color("#0a0706"), 3.0, true)
	# lanterns (lit up to the progress)
	var margin := w * 0.08
	for i in LANTERNS:
		var u := float(i) / float(LANTERNS - 1)
		var x := lerpf(margin, w - margin, u)
		var y := _wire_y(x, w, h)
		var lit := clampf((_shown - u * 0.98) * 12.0, 0.0, 1.0)
		var swing := sin(_t * 1.3 + float(i)) * 3.0
		var ls := 0.62
		var lsz := Vector2(96, 160) * ls
		var pos := Vector2(x - lsz.x * 0.5 + swing, y - 2)
		if lit > 0.0 and _glow_tex != null:
			var g := 150.0 + 12.0 * sin(_t * 3.0 + float(i) * 2.1)
			draw_texture_rect(_glow_tex, Rect2(pos + lsz * Vector2(0.5, 0.48) - Vector2(g, g), Vector2(g, g) * 2.0), false,
				Color(1.0, 0.55, 0.25, 0.42 * lit))
		if _lantern_tex != null:
			var c := Color(0.22, 0.12, 0.1, 1.0).lerp(Color(1, 1, 1, 1), lit)
			draw_texture_rect(_lantern_tex, Rect2(pos, lsz), false, c)
	# the cat balance-walking on the wire
	var cx := lerpf(margin * 0.4, w - margin * 1.2, _shown)
	var cy := _wire_y(cx, w, h)
	var moving := absf(progress - _shown) > 0.002 or _shown < 0.999
	var phase := _t * (1.15 if moving else 0.0)
	var cat_col := Color("#060404")
	CatSilhouette.draw(self, Vector2(cx, cy - 1.0), 0.72, phase, 1.0, cat_col, &"walk", _t)
