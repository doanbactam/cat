extends UIScreen
## Belongings (Đồ đạc) — Cam's den stash. Category tabs; a grid of rice-paper slots (item art,
## count, "in mouth" / "worn" marks); a detail page with the big illustration, description and
## actions (carry in mouth / put away, eat, use, wear / take off). Footer: caps + active effects.

const CATEGORIES: Array = [
	["INV_TAB_ALL", ""], ["CAT_FOOD", "food"], ["CAT_QUEST", "quest"], ["CAT_TOY", "toy"],
	["CAT_SHINY", "shiny"], ["CAT_COSMETIC", "cosmetic"], ["CAT_CONSUMABLE", "consumable"],
	["CAT_MEMORY", "memory"], ["CAT_TROPHY", "trophy"],
]
const COLS := 5

var _tab := 0
var _tabs_bar: HBoxContainer
var _grid: GridContainer
var _scroll: ScrollContainer
var _empty: Label
var _detail_icon: TextureRect
var _detail_name: Label
var _detail_cat: Label
var _detail_desc: RichTextLabel
var _detail_stats: VBoxContainer
var _actions: HBoxContainer
var _caps_label: Label
var _buffs_box: HBoxContainer
var _selected: StringName = &""
var _slots: Array[Button] = []
var _frame: Dictionary


func _init() -> void:
	menu_id = &"inventory"


func build() -> void:
	_frame = make_frame("INV_TITLE", &"inventory")
	var keys: PackedStringArray = []
	for c: Array in CATEGORIES:
		keys.append(String(c[0]))
	_tabs_bar = make_tabs(keys, [], _select_tab)
	var content: Control = _frame["content"]
	var v := VBoxContainer.new()
	v.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	v.add_theme_constant_override(&"separation", 14)
	content.add_child(v)
	v.add_child(_tabs_bar)
	var h := HBoxContainer.new()
	h.size_flags_vertical = Control.SIZE_EXPAND_FILL
	h.add_theme_constant_override(&"separation", 34)
	v.add_child(h)
	var left := PanelContainer.new()
	left.theme_type_variation = &"GlassPanel"
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 1.25
	h.add_child(left)
	var lv := VBoxContainer.new()
	left.add_child(lv)
	_scroll = ScrollContainer.new()
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.follow_focus = true
	lv.add_child(_scroll)
	_grid = GridContainer.new()
	_grid.columns = COLS
	_grid.add_theme_constant_override(&"h_separation", 14)
	_grid.add_theme_constant_override(&"v_separation", 14)
	_scroll.add_child(_grid)
	_empty = UIStyle.label(tr("INV_EMPTY"), &"prose_italic", 24, UIStyle.TEXT_DIM)
	_empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_empty.visible = false
	lv.add_child(_empty)
	# detail page
	var page := PanelContainer.new()
	page.theme_type_variation = &"PaperPanel"
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.size_flags_stretch_ratio = 1.0
	h.add_child(page)
	var pv := VBoxContainer.new()
	pv.add_theme_constant_override(&"separation", 10)
	page.add_child(pv)
	_detail_icon = UIStyle.icon_rect(null, 220)
	_detail_icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	pv.add_child(_detail_icon)
	_detail_cat = UIStyle.label("", &"semibold", 16, UIStyle.SEAL_RED)
	_detail_cat.uppercase = true
	_detail_cat.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	pv.add_child(_detail_cat)
	_detail_name = UIStyle.label("", &"heading", 38, UIStyle.TEXT_INK)
	_detail_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_detail_name.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pv.add_child(_detail_name)
	var d := UIStyle.divider(360, Color(UIStyle.GOLD_DIM, 0.9))
	d.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	pv.add_child(d)
	_detail_desc = UIStyle.rich("", 24, UIStyle.TEXT_INK, &"prose")
	_detail_desc.theme_type_variation = &"InkProseText"
	_detail_desc.add_theme_font_size_override(&"normal_font_size", 24)
	_detail_desc.add_theme_font_size_override(&"italics_font_size", 24)
	pv.add_child(_detail_desc)
	_detail_stats = VBoxContainer.new()
	_detail_stats.add_theme_constant_override(&"separation", 4)
	pv.add_child(_detail_stats)
	var sp := Control.new()
	sp.size_flags_vertical = Control.SIZE_EXPAND_FILL
	pv.add_child(sp)
	_actions = HBoxContainer.new()
	_actions.alignment = BoxContainer.ALIGNMENT_CENTER
	_actions.add_theme_constant_override(&"separation", 14)
	pv.add_child(_actions)
	# footer
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override(&"separation", 20)
	v.add_child(foot)
	foot.add_child(UIStyle.icon_rect(UIStyle.item_icon(&"cap"), 36))
	_caps_label = UIStyle.label("", &"semibold", 22, UIStyle.TEXT)
	foot.add_child(_caps_label)
	var vs := VSeparator.new()
	foot.add_child(vs)
	foot.add_child(UIStyle.label(tr("INV_BUFFS"), &"semibold", 18, UIStyle.GOLD))
	_buffs_box = HBoxContainer.new()
	_buffs_box.add_theme_constant_override(&"separation", 16)
	foot.add_child(_buffs_box)
	var hint := UIStyle.label(tr("INV_MOUTH_HINT"), &"body_italic", 19, UIStyle.TEXT_MUTED)
	hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	foot.add_child(hint)
	(_frame["hints"] as UIHintBar).set_hints([[&"ui_accept", "UI_SELECT"], ["@Q / E|LB / RB", "UI_TABS"], [&"ui_cancel", "UI_BACK"]])
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"inventory_changed", func(_i: StringName, _c: int) -> void: _refresh.call_deferred())
		ge.connect(&"mouth_item_changed", func(_i: StringName) -> void: _refresh.call_deferred())
	_refresh()


func _gs() -> Node:
	return get_node_or_null(^"/root/GameState")


func _select_tab(i: int) -> void:
	_tab = i
	_selected = &""
	_refresh()
	_focus_first.call_deferred()


func on_tab_input(dir: int) -> bool:
	var n := posmod(_tab + dir, CATEGORIES.size())
	(_tabs_bar.get_child(n) as Button).button_pressed = true
	_select_tab(n)
	return true


func default_focus() -> Control:
	return _slots[0] if not _slots.is_empty() else (_tabs_bar.get_child(0) as Control)


func _focus_first() -> void:
	var f := default_focus()
	if f != null:
		f.grab_focus()


func _items_for_tab() -> Array[StringName]:
	var out: Array[StringName] = []
	var gs := _gs()
	if gs == null:
		return out
	var inv: Dictionary = gs.call("get_inventory")
	var cat := String(CATEGORIES[_tab][1])
	var ids: Array = inv.keys()
	ids.sort_custom(func(a: Variant, b: Variant) -> bool:
		var da: Dictionary = gs.call("get_item_def", StringName(str(a)))
		var db: Dictionary = gs.call("get_item_def", StringName(str(b)))
		var ca := String(da.get("category", ""))
		var cb := String(db.get("category", ""))
		if ca != cb:
			return ca < cb
		return str(a) < str(b))
	for id: Variant in ids:
		var sid := StringName(str(id))
		if sid == &"cap":
			continue
		var d: Dictionary = gs.call("get_item_def", sid)
		if cat != "" and String(d.get("category", "")) != cat:
			continue
		if int(inv[id]) <= 0:
			continue
		out.append(sid)
	return out


func _refresh() -> void:
	if _grid == null:
		return
	var had_focus := get_viewport().gui_get_focus_owner() if is_inside_tree() else null
	var focus_id: StringName = had_focus.get_meta(&"item_id", &"") if had_focus != null and had_focus.has_meta(&"item_id") else &""
	for c in _grid.get_children():
		_grid.remove_child(c)
		c.queue_free()
	_slots.clear()
	var gs := _gs()
	var items := _items_for_tab()
	_empty.visible = items.is_empty()
	for id in items:
		_grid.add_child(_make_slot(id))
	if gs != null:
		_caps_label.text = tr("INV_CAPS").format({"n": int(gs.call("get_caps"))})
	_refresh_buffs()
	UIStyle.wire_sounds(_grid)
	if _selected == &"" or not items.has(_selected):
		_selected = items[0] if not items.is_empty() else &""
	_show_detail(_selected)
	for s in _slots:
		if s.get_meta(&"item_id") == focus_id:
			s.grab_focus.call_deferred()


func _make_slot(id: StringName) -> Button:
	var gs := _gs()
	var b := Button.new()
	b.theme_type_variation = &"SlotButton"
	b.custom_minimum_size = Vector2(132, 132)
	b.set_meta(&"item_id", id)
	b.tooltip_text = String(gs.call("get_item_name", id, false)) if gs != null else String(id)
	var ic := UIStyle.icon_rect(UIStyle.item_icon(id), 104)
	ic.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ic.offset_left = 14
	ic.offset_top = 12
	ic.offset_right = -14
	ic.offset_bottom = -16
	b.add_child(ic)
	var count := int(gs.call("item_count", id)) if gs != null else 1
	if count > 1:
		var badge := UIStyle.label("×%d" % count, &"bold", 18, UIStyle.TEXT_INK)
		badge.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
		badge.offset_left = -56
		badge.offset_top = -32
		badge.offset_right = -10
		badge.offset_bottom = -6
		badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		b.add_child(badge)
	var mark := ""
	if gs != null and StringName(gs.get("mouth_item")) == id:
		mark = "mouth"
	elif gs != null and gs.has_method("get_equipped"):
		var d: Dictionary = gs.call("get_item_def", id)
		var slot := StringName(String(d.get("equip", "collar")))
		if String(d.get("category", "")) == "cosmetic" and StringName(gs.call("get_equipped", slot)) == id:
			mark = "worn"
	if mark != "":
		var m := UIStyle.icon_rect(UIStyle.glyph(&"mouth" if mark == "mouth" else &"check"), 28, UIStyle.SEAL_RED)
		m.position = Vector2(8, 8)
		b.add_child(m)
	b.focus_entered.connect(func() -> void: _show_detail(id))
	b.pressed.connect(func() -> void: _primary_action(id))
	_slots.append(b)
	return b


func _show_detail(id: StringName) -> void:
	_selected = id
	for c in _actions.get_children():
		c.queue_free()
	for c in _detail_stats.get_children():
		c.queue_free()
	var gs := _gs()
	if id == &"" or gs == null:
		_detail_icon.texture = UIStyle.glyph(&"inventory")
		_detail_icon.modulate = Color(UIStyle.TEXT_INK, 0.25)
		_detail_name.text = ""
		_detail_cat.text = ""
		_detail_desc.text = "[i]" + tr("INV_EMPTY") + "[/i]"
		return
	var d: Dictionary = gs.call("get_item_def", id)
	_detail_icon.modulate = Color.WHITE
	_detail_icon.texture = UIStyle.item_icon(id)
	_detail_name.text = String(gs.call("get_item_name", id, false))
	_detail_cat.text = tr("CAT_" + String(d.get("category", "quest")).to_upper())
	var desc := tr(String(d.get("desc_key", "")))
	if String(d.get("category", "")) == "memory":
		var story_key := String(id).to_upper() + "_STORY"
		if TranslationServer.translate(story_key) != story_key:
			desc = tr(story_key)
	_detail_desc.text = desc
	if int(d.get("food", 0)) > 0:
		_stat_line(&"hunger", tr("INV_FOOD_VALUE").format({"n": int(d.get("food", 0))}))
	if int(d.get("value", 0)) > 0 and bool(d.get("sellable", false)):
		_stat_line(&"cap", tr("INV_VALUE").format({"n": int(d.get("value", 0))}))
	if StringName(gs.get("mouth_item")) == id:
		_stat_line(&"mouth", tr("INV_IN_MOUTH"))
	# actions
	var cat := String(d.get("category", ""))
	if bool(d.get("mouth", false)):
		if StringName(gs.get("mouth_item")) == id:
			_action("INV_PUT_AWAY", func() -> void: gs.call("set_mouth_item", &""))
		else:
			_action("INV_CARRY", func() -> void: gs.call("set_mouth_item", id), true)
	if cat == "food" and int(d.get("food", 0)) > 0:
		_action("INV_EAT", func() -> void:
			if bool(gs.call("use_item", id)):
				_notify(tr("INV_ATE").format({"item": String(gs.call("get_item_name", id, false))}), &"hunger"))
	elif cat in ["consumable", "toy"] and d.has("use"):
		_action("INV_USE", func() -> void:
			if bool(gs.call("use_item", id)):
				_notify(tr("INV_USED").format({"item": String(gs.call("get_item_name", id, false))}), &"item"))
	if cat == "cosmetic":
		var slot := StringName(String(d.get("equip", "collar")))
		if StringName(gs.call("get_equipped", slot)) == id:
			_action("INV_UNEQUIP", func() -> void:
				gs.call("unequip_slot", slot)
				_refresh())
		else:
			_action("INV_EQUIP", func() -> void:
				gs.call("equip_item", id)
				_refresh(), true)
	UIStyle.wire_sounds(_actions)


func _stat_line(icon: StringName, text: String) -> void:
	var r := HBoxContainer.new()
	r.alignment = BoxContainer.ALIGNMENT_CENTER
	r.add_theme_constant_override(&"separation", 8)
	r.add_child(UIStyle.icon_rect(UIStyle.glyph(icon), 22, UIStyle.TEXT_INK_DIM))
	r.add_child(UIStyle.label(text, &"medium", 20, UIStyle.TEXT_INK_DIM))
	_detail_stats.add_child(r)


func _action(key: String, cb: Callable, primary := false) -> void:
	var b := Button.new()
	b.text = tr(key)
	b.theme_type_variation = &"PrimaryButton" if primary else &"Button"
	b.custom_minimum_size = Vector2(200, 52)
	b.pressed.connect(func() -> void:
		cb.call()
		_refresh.call_deferred())
	_actions.add_child(b)


func _primary_action(id: StringName) -> void:
	_show_detail(id)
	var first: Button = (_actions.get_child(0) as Button) if _actions.get_child_count() > 0 else null
	if first != null:
		first.grab_focus()


func _refresh_buffs() -> void:
	for c in _buffs_box.get_children():
		c.queue_free()
	var gs := _gs()
	if gs == null:
		return
	var buffs: Dictionary = gs.call("get_buffs")
	if buffs.is_empty():
		_buffs_box.add_child(UIStyle.label(tr("INV_NO_BUFFS"), &"body_italic", 19, UIStyle.TEXT_MUTED))
		return
	for id: Variant in buffs:
		var bd: Dictionary = buffs[id] if buffs[id] is Dictionary else {}
		var r := HBoxContainer.new()
		r.add_theme_constant_override(&"separation", 6)
		r.add_child(UIStyle.icon_rect(UIStyle.glyph(&"buff"), 22, UIStyle.JADE))
		var mins := int(gs.call("get_buff_remaining_minutes", StringName(str(id))))
		var nm := tr(String(bd.get("name_key", "BUFF_" + str(id).to_upper())))
		r.add_child(UIStyle.label("%s · %s" % [nm, tr("INV_BUFF_LEFT").format({"min": mins})], &"medium", 19, UIStyle.TEXT))
		_buffs_box.add_child(r)


func _notify(text: String, icon: StringName) -> void:
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.emit_signal(&"notify", text, icon)
