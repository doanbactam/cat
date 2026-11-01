extends UIScreen
## Save / load slots (Lưu / Tải hành trình). mode = &"load" (main menu, pause menu) or &"save"
## (pause menu). Slot 0 = autosave (load only), 1–3 manual. Each slot is a paper card with the
## summary GameState.get_save_info() returns (level, day, time, place, tracked quest, play time,
## real date). Overwrite / delete ask for confirmation.

var mode: StringName = &"load":
	set(v):
		mode = v
		if is_inside_tree():
			_rebuild()

var _list: VBoxContainer
var _title: Label
var _frame: Dictionary
var _cards: Array[Button] = []


func _init() -> void:
	menu_id = &"save_slots"


func build() -> void:
	_frame = make_frame("LOAD_TITLE", &"save")
	_title = (_frame["header"] as HBoxContainer).get_node("Title") as Label
	var content: Control = _frame["content"]
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	content.add_child(center)
	_list = VBoxContainer.new()
	_list.add_theme_constant_override(&"separation", 18)
	_list.custom_minimum_size = Vector2(1180, 0)
	center.add_child(_list)
	(_frame["hints"] as UIHintBar).set_hints([[&"ui_accept", "UI_SELECT"], ["@Del|Y", "BTN_DELETE"], [&"ui_cancel", "UI_BACK"]])
	_rebuild()


func _gs() -> Node:
	return get_node_or_null(^"/root/GameState")


func _rebuild() -> void:
	if _list == null:
		return
	_title.text = tr("SAVE_TITLE" if mode == &"save" else "LOAD_TITLE")
	for c in _list.get_children():
		c.queue_free()
	_cards.clear()
	var first := 1 if mode == &"save" else 0
	for slot in range(first, 4):
		_list.add_child(_make_card(slot))
	for i in _cards.size():
		var b := _cards[i]
		b.focus_neighbor_top = b.get_path_to(_cards[maxi(0, i - 1)])
		b.focus_neighbor_bottom = b.get_path_to(_cards[mini(_cards.size() - 1, i + 1)])
	UIStyle.wire_sounds(_list)
	focus_default.call_deferred()


func _make_card(slot: int) -> Button:
	var gs := _gs()
	var info: Dictionary = gs.call("get_save_info", slot) if gs != null else {"exists": false}
	var exists := bool(info.get("exists", false))
	var b := Button.new()
	b.theme_type_variation = &"ChipButton"
	b.custom_minimum_size = Vector2(1180, 128)
	b.set_meta(&"slot", slot)
	b.disabled = mode == &"load" and not exists
	var h := HBoxContainer.new()
	h.set_anchors_preset(Control.PRESET_FULL_RECT)
	h.offset_left = 22
	h.offset_right = -22
	h.add_theme_constant_override(&"separation", 26)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(h)
	var badge := PanelContainer.new()
	badge.theme_type_variation = &"SlotPanel"
	badge.custom_minimum_size = Vector2(92, 92)
	badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(badge)
	var bi := UIStyle.icon_rect(UIStyle.glyph(&"time" if slot == 0 else &"paw"), 50, UIStyle.TEXT_INK if exists else Color(UIStyle.TEXT_INK, 0.3))
	badge.add_child(bi)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override(&"separation", 4)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(v)
	var name_key := "SLOT_AUTOSAVE" if slot == 0 else "SLOT_MANUAL"
	var nl := UIStyle.label(tr(name_key).format({"n": slot}), &"heading", 32, UIStyle.TEXT if exists or mode == &"save" else UIStyle.TEXT_MUTED)
	v.add_child(nl)
	if exists:
		var line1: PackedStringArray = []
		line1.append(tr("HUD_LEVEL").format({"level": int(info.get("level", 1))}))
		line1.append(tr("SLOT_DAY").format({"day": int(info.get("day", 1))}))
		line1.append(UIStyle.fmt_hour(float(info.get("hour", 0.0))))
		var loc := String(info.get("location", ""))
		if loc != "":
			line1.append(tr(loc))
		v.add_child(UIStyle.label("  ·  ".join(line1), &"medium", 21, UIStyle.TEXT_DIM))
		var q := String(info.get("quest", ""))
		var qm := get_node_or_null(^"/root/QuestManager")
		if q != "" and qm != null:
			var qd: Dictionary = qm.call("get_quest", StringName(q))
			if not qd.is_empty():
				var ql := UIStyle.label("❖ " + String(qd.get("title", q)), &"prose_italic", 21, UIStyle.GOLD_LIGHT)
				v.add_child(ql)
	else:
		v.add_child(UIStyle.label(tr("SLOT_EMPTY"), &"body_italic", 21, UIStyle.TEXT_MUTED))
	var right := VBoxContainer.new()
	right.alignment = BoxContainer.ALIGNMENT_CENTER
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.add_child(right)
	if exists:
		var pt := UIStyle.label(tr("SLOT_PLAYTIME").format({"time": UIStyle.fmt_playtime(float(info.get("playtime_s", 0.0)))}), &"medium", 19, UIStyle.TEXT_DIM)
		pt.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		right.add_child(pt)
		var at := String(info.get("saved_at", "")).replace("T", "  ")
		var al := UIStyle.label(at, &"light", 18, UIStyle.TEXT_MUTED)
		al.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		right.add_child(al)
	var act := UIStyle.label(tr("BTN_SAVE" if mode == &"save" else "BTN_LOAD"), &"semibold", 20, UIStyle.GOLD)
	act.uppercase = true
	act.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.add_child(act)
	b.pressed.connect(_on_slot.bind(slot, exists))
	b.gui_input.connect(func(ev: InputEvent) -> void:
		var del := false
		if ev is InputEventKey and (ev as InputEventKey).pressed and (ev as InputEventKey).physical_keycode in [KEY_DELETE, KEY_BACKSPACE]:
			del = true
		if ev is InputEventJoypadButton and (ev as InputEventJoypadButton).pressed and (ev as InputEventJoypadButton).button_index == JOY_BUTTON_Y:
			del = true
		if del and exists:
			b.accept_event()
			_on_delete(slot))
	_cards.append(b)
	return b


func default_focus() -> Control:
	for b in _cards:
		if not b.disabled:
			return b
	return null


func _on_slot(slot: int, exists: bool) -> void:
	if mode == &"save":
		if exists:
			var d := UIConfirmDialog.make("CONFIRM_OVERWRITE_TITLE", "CONFIRM_OVERWRITE_BODY")
			d.confirmed.connect(_do_save.bind(slot))
			host.call("push_screen", d)
		else:
			_do_save(slot)
	else:
		_do_load(slot)


func _do_save(slot: int) -> void:
	var gs := _gs()
	if gs != null and bool(gs.call("save_game", slot)):
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null:
			ge.emit_signal(&"notify", tr("SAVE_DONE"), &"save")
	_rebuild()


func _do_load(slot: int) -> void:
	var loader := get_node_or_null(^"/root/SceneLoader")
	if loader == null:
		return
	if String(loader.call("get_game_scene_path")) == "":
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null:
			ge.emit_signal(&"notify", tr("UI_NO_GAME_SCENE"), &"warning")
		return
	UIStyle.sfx(&"ui_confirm")
	loader.call("continue_game", slot)


func _on_delete(slot: int) -> void:
	var d := UIConfirmDialog.make("CONFIRM_DELETE_TITLE", "CONFIRM_DELETE_BODY", true)
	d.confirmed.connect(func() -> void:
		var gs := _gs()
		if gs != null:
			gs.call("delete_save", slot)
		_rebuild())
	host.call("push_screen", d)
