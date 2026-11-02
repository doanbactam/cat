class_name HudCelebration
extends Control
## Centre-screen moments: LEVEL UP (radial lantern glow, rotating rays, big level number, points
## gained) and QUEST COMPLETE (red seal stamp slamming in + quest title + XP reward).
## Queued; each lasts ~3.6 s; never blocks input.

var _queue: Array[Dictionary] = []
var _busy := false
var _t := 0.0
var _mode := &""
var _box: VBoxContainer
var _caption: Label
var _big: Label
var _sub: Label
var _seal: TextureRect
var _alpha := 0.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_box = VBoxContainer.new()
	_box.set_anchors_preset(Control.PRESET_CENTER)
	_box.anchor_left = 0.5
	_box.anchor_right = 0.5
	_box.anchor_top = 0.42
	_box.anchor_bottom = 0.42
	_box.offset_left = -600
	_box.offset_right = 600
	_box.offset_top = -170
	_box.offset_bottom = 170
	_box.alignment = BoxContainer.ALIGNMENT_CENTER
	_box.add_theme_constant_override(&"separation", 4)
	_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_box)
	_seal = UIStyle.icon_rect(UIStyle.ui_tex("seal_check"), 120)
	_seal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_seal.pivot_offset = Vector2(60, 60)
	_box.add_child(_seal)
	_caption = UIStyle.label("", &"bold", 22, UIStyle.GOLD_LIGHT)
	_caption.uppercase = true
	_caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	HudQuestTracker._shadow(_caption)
	_box.add_child(_caption)
	_big = UIStyle.label("", &"title", 96, UIStyle.TEXT)
	_big.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_big.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.6))
	_big.add_theme_constant_override(&"shadow_outline_size", 14)
	_big.add_theme_constant_override(&"shadow_offset_y", 4)
	_box.add_child(_big)
	_sub = UIStyle.label("", &"medium", 24, UIStyle.TEXT)
	_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	HudQuestTracker._shadow(_sub)
	_box.add_child(_sub)
	_box.modulate.a = 0.0
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"level_up", _on_level_up)
		ge.connect(&"quest_completed", _on_quest_completed)


func _on_level_up(level: int) -> void:
	var sp := 1 + (1 if level in [5, 10] else 0)
	show_level_up(level, sp)


func _on_quest_completed(quest_id: StringName) -> void:
	var qm := get_node_or_null(^"/root/QuestManager")
	var title := String(quest_id)
	var xp := 0
	if qm != null:
		var q: Dictionary = qm.call("get_quest", quest_id)
		title = String(q.get("title", title))
		var rw: Variant = q.get("rewards", {})
		if rw is Dictionary:
			xp = int((rw as Dictionary).get("xp", 0))
	show_quest_complete(title, xp)


func show_level_up(level: int, skill_points: int = 1) -> void:
	_queue.append({"mode": &"level", "level": level, "sp": skill_points})
	if not _busy:
		_next()


func show_quest_complete(title: String, xp: int = 0) -> void:
	_queue.append({"mode": &"quest", "title": title, "xp": xp})
	if not _busy:
		_next()


func is_busy() -> bool:
	return _busy


func _next() -> void:
	if _queue.is_empty():
		_busy = false
		_mode = &""
		return
	_busy = true
	var d: Dictionary = _queue.pop_front()
	_mode = d["mode"]
	_t = 0.0
	if _mode == &"level":
		_seal.visible = false
		_caption.text = tr("HUD_LEVEL_UP")
		_big.text = tr("HUD_LEVEL").format({"level": int(d["level"])})
		_sub.text = tr("HUD_LEVEL_UP_SUB").format({"level": int(d["level"]), "sp": int(d["sp"])})
		_big.add_theme_color_override(&"font_color", UIStyle.GOLD_LIGHT)
	else:
		_seal.visible = true
		_caption.text = tr("HUD_QUEST_COMPLETE")
		_big.text = String(d["title"])
		_big.add_theme_color_override(&"font_color", UIStyle.TEXT)
		_sub.text = tr("HUD_REWARD_XP").format({"n": int(d["xp"])}) if int(d["xp"]) > 0 else ""
		_seal.scale = Vector2(2.2, 2.2)
		_seal.modulate.a = 0.0
		var st := create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		st.set_parallel(true)
		st.tween_property(_seal, "scale", Vector2.ONE, 0.35).set_delay(0.15)
		st.tween_property(_seal, "modulate:a", 1.0, 0.2).set_delay(0.15)
	_big.add_theme_font_size_override(&"font_size", 96 if _mode == &"level" else 64)
	_box.modulate.a = 0.0
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(_box, "modulate:a", 1.0, 0.45)
	tw.tween_interval(2.8)
	tw.tween_property(_box, "modulate:a", 0.0, 0.8)
	tw.tween_interval(0.25)
	tw.tween_callback(_next)


func _process(delta: float) -> void:
	_t += delta
	_alpha = _box.modulate.a if _busy else 0.0
	queue_redraw()


func _draw() -> void:
	if _alpha <= 0.01:
		return
	var c := Vector2(size.x * 0.5, size.y * 0.42)
	var glow := UIStyle.ui_tex("glow_soft")
	if _mode == &"level":
		if glow != null:
			var r := 420.0 + 30.0 * sin(_t * 2.0)
			draw_texture_rect(glow, Rect2(c - Vector2(r, r * 0.7), Vector2(r * 2.0, r * 1.4)), false, Color(1.0, 0.62, 0.28, 0.33 * _alpha))
		# slow rotating rays
		var rays := 18
		for i in rays:
			var a := _t * 0.15 + TAU * float(i) / rays
			var p0 := c + Vector2.from_angle(a) * 120.0
			var p1 := c + Vector2.from_angle(a) * 380.0
			draw_line(p0, p1, Color(1.0, 0.82, 0.5, 0.10 * _alpha), 3.0, true)
	else:
		if glow != null:
			draw_texture_rect(glow, Rect2(c - Vector2(480, 220), Vector2(960, 440)), false, Color(0.0, 0.0, 0.0, 0.45 * _alpha))
			draw_texture_rect(glow, Rect2(c - Vector2(300, 160), Vector2(600, 320)), false, Color(1.0, 0.45, 0.25, 0.18 * _alpha))
