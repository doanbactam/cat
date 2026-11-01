extends UIScreen
## Pause menu over the frosted, darkened city. Left: serif menu (Resume, Journal, Map,
## Belongings, Skills, Settings, Save, Load, Main menu, Quit). Right: a rice-paper card "Cam
## today" — vitals with numbers, level & XP, caps, tracked quest and the current step.

var _items: Array[Button] = []
var _paw: TextureRect
var _status: Label


func _init() -> void:
	menu_id = &"pause"


func build() -> void:
	var left := VBoxContainer.new()
	left.position = Vector2(120, 110)
	left.add_theme_constant_override(&"separation", 0)
	add_child(left)
	var t := UIStyle.label(tr("PAUSE_TITLE"), &"title", 76, UIStyle.TEXT)
	left.add_child(t)
	_status = UIStyle.label(_status_text(), &"prose_italic", 25, UIStyle.GOLD_LIGHT)
	left.add_child(_status)
	var sp := Control.new()
	sp.custom_minimum_size = Vector2(0, 26)
	left.add_child(sp)
	var gs := get_node_or_null(^"/root/GameState")
	var sk := int(gs.get("skill_points")) if gs != null else 0
	_add(left, "PAUSE_RESUME", request_close)
	_add(left, "PAUSE_JOURNAL", _open.bind(&"journal"))
	_add(left, "PAUSE_MAP", _open.bind(&"map"))
	_add(left, "PAUSE_INVENTORY", _open.bind(&"inventory"))
	var skb := _add(left, "PAUSE_SKILLS", _open.bind(&"skills"))
	if sk > 0:
		skb.text += "   ✦ " + str(sk)
	_add(left, "PAUSE_SETTINGS", _open.bind(&"settings"))
	_add(left, "PAUSE_SAVE", _open_slots.bind(&"save"))
	_add(left, "PAUSE_LOAD", _open_slots.bind(&"load"))
	_add(left, "PAUSE_MAIN_MENU", _confirm_main_menu)
	_add(left, "PAUSE_QUIT", _confirm_quit)
	for i in _items.size():
		var b := _items[i]
		b.focus_neighbor_top = b.get_path_to(_items[(i - 1 + _items.size()) % _items.size()])
		b.focus_neighbor_bottom = b.get_path_to(_items[(i + 1) % _items.size()])
	_paw = UIStyle.icon_rect(UIStyle.glyph(&"paw"), 26, UIStyle.LANTERN_GLOW)
	_paw.rotation = deg_to_rad(-12)
	add_child(_paw)
	_paw.visible = false
	_build_card()
	var hints := UIHintBar.new()
	hints.set_hints([[&"ui_accept", "UI_SELECT"], [&"ui_cancel", "PAUSE_RESUME"]])
	hints.anchor_left = 0.0
	hints.anchor_right = 1.0
	hints.anchor_top = 1.0
	hints.anchor_bottom = 1.0
	hints.offset_top = -78
	hints.offset_bottom = -36
	hints.offset_right = -72
	add_child(hints)


func _add(parent: Control, key: String, cb: Callable) -> Button:
	var b := Button.new()
	b.theme_type_variation = &"MenuItemButton"
	b.add_theme_font_size_override(&"font_size", 36)
	b.text = tr(key)
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(520, 60)
	b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	b.pressed.connect(cb)
	b.focus_entered.connect(func() -> void:
		_paw.visible = true
		_paw.global_position = b.global_position + Vector2(-30, b.size.y * 0.5 - 13))
	parent.add_child(b)
	_items.append(b)
	return b


func _status_text() -> String:
	var tod := get_node_or_null(^"/root/TimeOfDay")
	var day := int(tod.get("day")) if tod != null else 1
	var hour := float(tod.get("hour")) if tod != null else 8.0
	var w := "clear"
	var wn := get_tree().get_first_node_in_group(&"weather") if is_inside_tree() else null
	if wn != null and wn.has_method("get_weather"):
		w = String(wn.call("get_weather"))
	else:
		var gs := get_node_or_null(^"/root/GameState")
		if gs != null and gs.has_method("get_weather"):
			w = String(gs.call("get_weather"))
	return tr("PAUSE_STATUS").format({"day": day, "time": UIStyle.fmt_hour(hour), "weather": tr("WEATHER_" + w.to_upper())})


func _build_card() -> void:
	var card := PanelContainer.new()
	card.theme_type_variation = &"PaperPanel"
	card.anchor_left = 1.0
	card.anchor_right = 1.0
	card.offset_left = -720
	card.offset_right = -120
	card.offset_top = 150
	add_child(card)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	card.add_child(v)
	var gs := get_node_or_null(^"/root/GameState")
	var head := HBoxContainer.new()
	head.add_theme_constant_override(&"separation", 14)
	v.add_child(head)
	head.add_child(UIStyle.icon_rect(UIStyle.glyph(&"cat"), 54, UIStyle.TEXT_INK))
	var hv := VBoxContainer.new()
	hv.add_theme_constant_override(&"separation", -4)
	head.add_child(hv)
	hv.add_child(UIStyle.label("Cam", &"heading", 40, UIStyle.TEXT_INK))
	if gs != null:
		var lvl := int(gs.get("level"))
		var to_next := int(gs.call("get_xp_to_next_level"))
		var key := "SKILLS_LEVEL_MAX" if to_next <= 0 else "SKILLS_LEVEL"
		hv.add_child(UIStyle.label(tr(key).format({"level": lvl, "xp": to_next}), &"medium", 19, UIStyle.TEXT_INK_DIM))
	v.add_child(UIStyle.divider(480, Color(UIStyle.GOLD_DIM, 0.9)))
	if gs != null:
		for st in UIStyle.STATS:
			var row := HBoxContainer.new()
			row.add_theme_constant_override(&"separation", 12)
			v.add_child(row)
			var col: Color = UIStyle.VITAL_COLORS[st]
			row.add_child(UIStyle.icon_rect(UIStyle.glyph(UIStyle.VITAL_ICONS[st]), 26, col.darkened(0.25)))
			var name_l := UIStyle.label(tr("STAT_" + String(st).to_upper()), &"medium", 21, UIStyle.TEXT_INK)
			name_l.custom_minimum_size = Vector2(150, 0)
			row.add_child(name_l)
			var bar := ProgressBar.new()
			bar.show_percentage = false
			bar.min_value = 0.0
			bar.max_value = 1.0
			bar.value = float(gs.call("get_stat_ratio", st))
			bar.custom_minimum_size = Vector2(220, 12)
			bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			bar.add_theme_stylebox_override(&"fill", UIStyle.flat_box(col.darkened(0.1), 3, Color(0, 0, 0, 0), 0, 0.0))
			bar.add_theme_stylebox_override(&"background", UIStyle.flat_box(Color(0.25, 0.18, 0.12, 0.25), 3, Color(0, 0, 0, 0), 0, 0.0))
			row.add_child(bar)
			var val := UIStyle.label("%d" % int(round(float(gs.call("get_stat", st)))), &"semibold", 20, UIStyle.TEXT_INK)
			val.custom_minimum_size = Vector2(46, 0)
			val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			row.add_child(val)
		var caps := HBoxContainer.new()
		caps.add_theme_constant_override(&"separation", 10)
		v.add_child(caps)
		caps.add_child(UIStyle.icon_rect(UIStyle.item_icon(&"cap"), 30))
		caps.add_child(UIStyle.label(tr("INV_CAPS").format({"n": int(gs.call("get_caps"))}), &"medium", 21, UIStyle.TEXT_INK))
	var qm := get_node_or_null(^"/root/QuestManager")
	if qm != null and StringName(qm.call("get_tracked")) != &"":
		v.add_child(UIStyle.divider(480, Color(UIStyle.GOLD_DIM, 0.9)))
		var q: Dictionary = qm.call("get_quest", qm.call("get_tracked"))
		var cap := UIStyle.label(tr("QUEST_CATEGORY_" + String(q.get("category", "misc")).to_upper()), &"semibold", 16, UIStyle.SEAL_RED)
		cap.uppercase = true
		v.add_child(cap)
		v.add_child(UIStyle.label(String(q.get("title", "")), &"heading", 30, UIStyle.TEXT_INK))
		var o: Dictionary = qm.call("get_tracked_objective")
		if not o.is_empty():
			var ol := UIStyle.label("❖  " + String(o.get("text", "")), &"prose_italic", 22, UIStyle.TEXT_INK_DIM)
			ol.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			ol.custom_minimum_size = Vector2(480, 0)
			v.add_child(ol)


func default_focus() -> Control:
	return _items[0] if not _items.is_empty() else null


func on_resumed() -> void:
	_status.text = _status_text()


func _hud() -> Node:
	return get_tree().get_first_node_in_group(&"hud")


func _open(id: StringName) -> void:
	var h := _hud()
	if h != null and h.has_method("open_screen"):
		h.call("open_screen", id)


func _open_slots(mode: StringName) -> void:
	var h := _hud()
	if h == null:
		return
	var s: UIScreen = h.call("open_screen", &"save_slots")
	if s != null:
		s.set("mode", mode)


func _confirm_main_menu() -> void:
	var d := UIConfirmDialog.make("CONFIRM_MAIN_MENU_TITLE", "CONFIRM_QUIT_BODY")
	d.confirmed.connect(func() -> void:
		var l := get_node_or_null(^"/root/SceneLoader")
		if l != null:
			l.call("go_to_main_menu", true))
	if host != null:
		host.call("push_screen", d)


func _confirm_quit() -> void:
	var d := UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_BODY", true)
	d.confirmed.connect(func() -> void: get_tree().quit())
	if host != null:
		host.call("push_screen", d)
