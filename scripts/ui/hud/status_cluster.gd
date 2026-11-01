class_name HudStatus
extends VBoxContainer
## Bottom-left status: mouth-item card (what Cam is carrying), the four vital rings, and the
## level badge + XP bar (+XP floating gains). Buff glyphs sit next to the rings; a caps counter
## pops up when bottle caps change. Everything listens to GameEvents.

var rings: Dictionary = {}          # stat -> HudVitalRing
var _mouth_card: PanelContainer
var _mouth_icon: TextureRect
var _mouth_name: Label
var _level_badge: _LevelBadge
var _xp_bar: _XpBar
var _xp_gain: Label
var _caps: HBoxContainer
var _caps_label: Label
var _buffs: HBoxContainer
var _xp_tween: Tween
var _caps_tween: Tween
var _last_caps := -1


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	alignment = BoxContainer.ALIGNMENT_END
	add_theme_constant_override(&"separation", 12)
	# --- mouth item card + caps -----------------------------------------------------------------
	var top := HBoxContainer.new()
	top.add_theme_constant_override(&"separation", 12)
	top.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(top)
	_mouth_card = PanelContainer.new()
	_mouth_card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sb := UIStyle.flat_box(Color(0.05, 0.035, 0.026, 0.72), 30, Color(UIStyle.GOLD, 0.4), 1, 10.0)
	sb.content_margin_left = 6
	sb.content_margin_right = 20
	sb.content_margin_top = 6
	sb.content_margin_bottom = 6
	_mouth_card.add_theme_stylebox_override(&"panel", sb)
	top.add_child(_mouth_card)
	var mh := HBoxContainer.new()
	mh.add_theme_constant_override(&"separation", 10)
	mh.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mouth_card.add_child(mh)
	var disc := PanelContainer.new()
	disc.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color("#efe2c4"), 24, Color(UIStyle.GOLD, 0.8), 2, 4.0))
	disc.custom_minimum_size = Vector2(48, 48)
	disc.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mh.add_child(disc)
	_mouth_icon = UIStyle.icon_rect(null, 40)
	disc.add_child(_mouth_icon)
	var mv := VBoxContainer.new()
	mv.add_theme_constant_override(&"separation", -2)
	mv.alignment = BoxContainer.ALIGNMENT_CENTER
	mv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mh.add_child(mv)
	var cap := UIStyle.label(tr("HUD_MOUTH"), &"semibold", 14, UIStyle.GOLD)
	cap.uppercase = true
	mv.add_child(cap)
	_mouth_name = UIStyle.label("", &"semibold", 21, UIStyle.TEXT)
	mv.add_child(_mouth_name)
	_mouth_card.visible = false
	_caps = HBoxContainer.new()
	_caps.add_theme_constant_override(&"separation", 6)
	_caps.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_caps.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_caps.add_child(UIStyle.icon_rect(UIStyle.glyph(&"cap"), 28, Color("#e2e6e8")))
	_caps_label = UIStyle.label("0", &"bold", 24, UIStyle.TEXT)
	HudQuestTracker._shadow(_caps_label)
	_caps.add_child(_caps_label)
	_caps.modulate.a = 0.0
	top.add_child(_caps)
	# --- rings + buffs ----------------------------------------------------------------------------
	var rr := HBoxContainer.new()
	rr.add_theme_constant_override(&"separation", 12)
	rr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(rr)
	for st in UIStyle.STATS:
		var r := HudVitalRing.new()
		r.stat = st
		rr.add_child(r)
		rings[st] = r
	_buffs = HBoxContainer.new()
	_buffs.add_theme_constant_override(&"separation", 6)
	_buffs.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_buffs.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rr.add_child(_buffs)
	# --- level + xp -------------------------------------------------------------------------------
	var xr := HBoxContainer.new()
	xr.add_theme_constant_override(&"separation", 12)
	xr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(xr)
	_level_badge = _LevelBadge.new()
	_level_badge.custom_minimum_size = Vector2(46, 46)
	xr.add_child(_level_badge)
	var xv := VBoxContainer.new()
	xv.alignment = BoxContainer.ALIGNMENT_CENTER
	xv.add_theme_constant_override(&"separation", 2)
	xv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	xr.add_child(xv)
	_xp_bar = _XpBar.new()
	_xp_bar.custom_minimum_size = Vector2(300, 10)
	xv.add_child(_xp_bar)
	_xp_gain = UIStyle.label("", &"semibold", 17, UIStyle.GOLD_LIGHT)
	HudQuestTracker._shadow(_xp_gain)
	_xp_gain.modulate.a = 0.0
	xv.add_child(_xp_gain)
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"stat_changed", _on_stat_changed)
		ge.connect(&"xp_gained", _on_xp_gained)
		ge.connect(&"level_up", func(_l: int) -> void: refresh_xp())
		ge.connect(&"mouth_item_changed", func(_id: StringName) -> void: refresh_mouth())
		ge.connect(&"inventory_changed", _on_inventory_changed)
		ge.connect(&"buff_changed", func(_id: StringName, _a: bool) -> void: refresh_buffs())
		ge.connect(&"game_loaded", func(_s: int) -> void: refresh_all())
		ge.connect(&"new_game_started", refresh_all)
	refresh_all()


func refresh_all() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null:
		for st: StringName in rings:
			(rings[st] as HudVitalRing).set_ratio(float(gs.call("get_stat_ratio", st)), false)
		_last_caps = int(gs.call("get_caps"))
		_caps_label.text = str(_last_caps)
	refresh_xp()
	refresh_mouth()
	refresh_buffs()


func _on_stat_changed(stat: StringName, value: float, max_value: float) -> void:
	if rings.has(stat):
		(rings[stat] as HudVitalRing).set_ratio(value / maxf(max_value, 0.001))


func _on_xp_gained(amount: int, _reason: String) -> void:
	refresh_xp()
	_xp_gain.text = tr("HUD_XP_GAIN").format({"n": amount})
	_xp_bar.flash = 1.0
	if _xp_tween != null and _xp_tween.is_valid():
		_xp_tween.kill()
	_xp_tween = create_tween()
	_xp_tween.tween_property(_xp_gain, "modulate:a", 1.0, 0.2)
	_xp_tween.tween_interval(2.0)
	_xp_tween.tween_property(_xp_gain, "modulate:a", 0.0, 0.8)


func refresh_xp() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null:
		return
	_level_badge.level = int(gs.get("level"))
	_xp_bar.target = float(gs.call("get_level_progress"))
	_level_badge.queue_redraw()


func refresh_mouth() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	var id: StringName = gs.get("mouth_item") if gs != null else &""
	if id == &"":
		if _mouth_card.visible:
			var tw := create_tween()
			tw.tween_property(_mouth_card, "modulate:a", 0.0, 0.25)
			tw.tween_callback(func() -> void: _mouth_card.visible = false)
		return
	_mouth_icon.texture = UIStyle.item_icon(id)
	_mouth_name.text = String(gs.call("get_item_name", id, false))
	_mouth_card.visible = true
	_mouth_card.modulate.a = 0.0
	var tw2 := create_tween()
	tw2.tween_property(_mouth_card, "modulate:a", 1.0, 0.25)


func _on_inventory_changed(item_id: StringName, count: int) -> void:
	if item_id != &"cap":
		return
	var delta := count - _last_caps if _last_caps >= 0 else 0
	_last_caps = count
	_caps_label.text = str(count) if delta == 0 else "%d  (%s%d)" % [count, "+" if delta > 0 else "", delta]
	if _caps_tween != null and _caps_tween.is_valid():
		_caps_tween.kill()
	_caps_tween = create_tween()
	_caps_tween.tween_property(_caps, "modulate:a", 1.0, 0.2)
	_caps_tween.tween_interval(3.0)
	_caps_tween.tween_callback(func() -> void: _caps_label.text = str(_last_caps))
	_caps_tween.tween_property(_caps, "modulate:a", 0.0, 0.8)


func refresh_buffs() -> void:
	for c in _buffs.get_children():
		c.queue_free()
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null or not gs.has_method("get_buffs"):
		return
	var buffs: Dictionary = gs.call("get_buffs")
	for id: Variant in buffs:
		var ic := UIStyle.icon_rect(UIStyle.glyph(&"buff"), 26, UIStyle.JADE)
		ic.tooltip_text = tr(String((buffs[id] as Dictionary).get("name_key", str(id)))) if buffs[id] is Dictionary else str(id)
		_buffs.add_child(ic)


## Shows every ring regardless of the "fade when full" rule (pause/photo previews).
func set_rings_always_visible(on: bool) -> void:
	for r: HudVitalRing in rings.values():
		r.always_visible = on


class _LevelBadge extends Control:
	var level := 1

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.5
		draw_circle(c, r, Color(0.05, 0.035, 0.026, 0.8))
		draw_arc(c, r - 1.5, 0.0, TAU, 48, UIStyle.GOLD, 2.0, true)
		draw_arc(c, r - 5.0, 0.0, TAU, 48, Color(UIStyle.GOLD, 0.35), 1.0, true)
		var f := UIStyle.font(&"title")
		var t := str(level)
		var fs := 24
		var ts := f.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
		draw_string(f, Vector2(c.x - ts.x * 0.5, c.y + f.get_ascent(fs) * 0.36), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, UIStyle.GOLD_LIGHT)


class _XpBar extends Control:
	var target := 0.0
	var value := 0.0
	var flash := 0.0

	func _process(delta: float) -> void:
		if target < value - 0.5:
			value = 0.0  # level wrapped
		value = move_toward(value, target, delta * 0.5)
		flash = maxf(0.0, flash - delta * 1.5)
		queue_redraw()

	func _draw() -> void:
		var r := Rect2(Vector2(0, size.y * 0.5 - 3), Vector2(size.x, 6))
		draw_rect(r.grow(1.5), Color(0, 0, 0, 0.5))
		draw_rect(r, Color(UIStyle.GOLD_DIM, 0.45))
		var fill := Rect2(r.position, Vector2(r.size.x * clampf(value, 0.0, 1.0), r.size.y))
		draw_rect(fill, UIStyle.GOLD.lerp(Color.WHITE, flash * 0.5))
		for i in range(1, 10):
			var x := r.position.x + r.size.x * float(i) / 10.0
			draw_line(Vector2(x, r.position.y), Vector2(x, r.end.y), Color(0, 0, 0, 0.35), 1.0)
