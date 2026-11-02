extends UIScreen
## Journal (Nhật ký): Quests (list + rice-paper page with objectives, rewards, Track),
## Memories (12 old photographs; found ones open Grandma Tư's story), Places (discovered
## locations), Cam (attributes, reputation, achievements, little numbers).

const TABS: PackedStringArray = ["JOURNAL_TAB_QUESTS", "JOURNAL_TAB_MEMORIES", "JOURNAL_TAB_PLACES", "JOURNAL_TAB_CAM"]
const TAB_ICONS: Array = [&"quest", &"memory", &"location", &"cat"]

var _tab := 0
var _tabs_bar: HBoxContainer
var _body: Control
var _selected_quest: StringName = &""
var _frame: Dictionary


func _init() -> void:
	menu_id = &"journal"


func build() -> void:
	_frame = make_frame("JOURNAL_TITLE", &"journal")
	_tabs_bar = make_tabs(TABS, TAB_ICONS, _select_tab)
	(_frame["header"] as HBoxContainer).add_child(_tabs_bar)
	_body = Control.new()
	_body.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	(_frame["content"] as Control).add_child(_body)
	(_frame["hints"] as UIHintBar).set_hints([[&"ui_accept", "UI_SELECT"], ["@Q / E|LB / RB", "UI_TABS"], [&"ui_cancel", "UI_BACK"]])
	_populate()


func _select_tab(i: int) -> void:
	_tab = i
	_populate()
	focus_default.call_deferred()


func on_tab_input(dir: int) -> bool:
	var n := posmod(_tab + dir, TABS.size())
	(_tabs_bar.get_child(n) as Button).button_pressed = true
	_select_tab(n)
	return true


func default_focus() -> Control:
	var f := UIStyle.first_focusable(_body)
	return f if f != null else (_tabs_bar.get_child(_tab) as Control)


func _populate() -> void:
	for c in _body.get_children():
		_body.remove_child(c)
		c.queue_free()
	match _tab:
		0:
			_build_quests()
		1:
			_build_memories()
		2:
			_build_places()
		3:
			_build_cam()
	UIStyle.wire_sounds(_body)


func _split() -> Array[Control]:
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.add_theme_constant_override(&"separation", 34)
	_body.add_child(h)
	var left := PanelContainer.new()
	left.theme_type_variation = &"GlassPanel"
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 0.8
	h.add_child(left)
	var page := PanelContainer.new()
	page.theme_type_variation = &"PaperPanel"
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.size_flags_stretch_ratio = 1.2
	h.add_child(page)
	return [left, page]


# --- quests ------------------------------------------------------------------------------------

func _build_quests() -> void:
	var parts := _split()
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	parts[0].add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_theme_constant_override(&"separation", 6)
	scroll.add_child(list)
	var page_v := VBoxContainer.new()
	page_v.add_theme_constant_override(&"separation", 10)
	parts[1].add_child(page_v)
	var qm := get_node_or_null(^"/root/QuestManager")
	if qm == null:
		return
	var active: Array = qm.call("get_active_quests")
	var done: Array = qm.call("get_completed_quests")
	var first: Button = null
	if active.is_empty() and done.is_empty():
		var l := UIStyle.label(tr("JOURNAL_NO_QUESTS"), &"prose_italic", 24, UIStyle.TEXT_DIM)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		list.add_child(l)
		_quest_page(page_v, &"")
		return
	for section: Array in [["JOURNAL_ACTIVE", active], ["JOURNAL_COMPLETED", done]]:
		var ids: Array = section[1]
		if ids.is_empty():
			continue
		var cap := UIStyle.label(tr(String(section[0])), &"semibold", 16, UIStyle.GOLD)
		cap.uppercase = true
		list.add_child(cap)
		for qid: Variant in ids:
			var q: Dictionary = qm.call("get_quest", StringName(str(qid)))
			var b := Button.new()
			b.theme_type_variation = &"ChipButton"
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.text = String(q.get("title", qid))
			b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			b.custom_minimum_size = Vector2(0, 54)
			var glyph := &"objective" if String(q.get("state", "")) == "completed" else &"quest"
			b.icon = UIStyle.glyph(glyph)
			if bool(q.get("tracked", false)):
				b.add_theme_color_override(&"font_color", UIStyle.LANTERN_GLOW)
			var id := StringName(str(qid))
			b.focus_entered.connect(func() -> void: _quest_page(page_v, id))
			b.pressed.connect(func() -> void: _quest_page(page_v, id))
			list.add_child(b)
			if first == null:
				first = b
	var sel := _selected_quest
	if sel == &"" or not (active.has(sel) or done.has(sel)):
		sel = StringName(qm.call("get_tracked"))
		if sel == &"" and not active.is_empty():
			sel = StringName(str(active[0]))
	_quest_page(page_v, sel)


func _quest_page(page: VBoxContainer, qid: StringName) -> void:
	for c in page.get_children():
		c.queue_free()
	_selected_quest = qid
	var qm := get_node_or_null(^"/root/QuestManager")
	if qid == &"" or qm == null:
		var l := UIStyle.label(tr("JOURNAL_SELECT_QUEST"), &"prose_italic", 24, UIStyle.TEXT_INK_DIM)
		page.add_child(l)
		return
	var q: Dictionary = qm.call("get_quest", qid)
	var cap := UIStyle.label(tr("QUEST_CATEGORY_" + String(q.get("category", "misc")).to_upper()), &"semibold", 16, UIStyle.SEAL_RED)
	cap.uppercase = true
	page.add_child(cap)
	var t := UIStyle.label(String(q.get("title", qid)), &"heading", 40, UIStyle.TEXT_INK)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	page.add_child(t)
	var giver := String(q.get("giver", ""))
	if giver != "":
		page.add_child(UIStyle.label(tr("JOURNAL_GIVER").format({"name": tr("NPC_" + giver.to_upper())}), &"prose_italic", 21, UIStyle.TEXT_INK_DIM))
	page.add_child(UIStyle.divider(520, Color(UIStyle.GOLD_DIM, 0.9)))
	var desc := UIStyle.rich(String(q.get("description", "")), 24, UIStyle.TEXT_INK, &"prose")
	desc.theme_type_variation = &"InkProseText"
	desc.add_theme_font_size_override(&"normal_font_size", 24)
	page.add_child(desc)
	var objs := VBoxContainer.new()
	objs.add_theme_constant_override(&"separation", 8)
	page.add_child(objs)
	for o: Dictionary in q.get("objectives", []):
		if bool(o.get("hidden", false)):
			continue
		if not bool(o.get("done", false)) and not bool(o.get("active", false)):
			continue
		var r := HBoxContainer.new()
		r.add_theme_constant_override(&"separation", 12)
		var done := bool(o.get("done", false))
		r.add_child(UIStyle.icon_rect(UIStyle.glyph(&"objective" if done else &"ring"), 24, UIStyle.JADE.darkened(0.3) if done else UIStyle.TEXT_INK_DIM))
		var text := String(o.get("text", ""))
		var req := int(o.get("required", 1))
		if req > 1:
			text += "  (%d/%d)" % [int(o.get("progress", 0)), req]
		if bool(o.get("optional", false)):
			text += "  — " + tr("JOURNAL_OPTIONAL")
		var l := UIStyle.label(text, &"medium", 21, UIStyle.TEXT_INK_DIM if done else UIStyle.TEXT_INK)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		r.add_child(l)
		objs.add_child(r)
	var rw: Variant = q.get("rewards", {})
	if rw is Dictionary and not (rw as Dictionary).is_empty():
		var rh := UIStyle.label(tr("JOURNAL_REWARDS"), &"semibold", 16, UIStyle.TEXT_INK_DIM)
		rh.uppercase = true
		page.add_child(rh)
		var rr := HBoxContainer.new()
		rr.add_theme_constant_override(&"separation", 18)
		page.add_child(rr)
		var rd: Dictionary = rw
		if int(rd.get("xp", 0)) > 0:
			rr.add_child(UIStyle.label(tr("HUD_REWARD_XP").format({"n": int(rd["xp"])}), &"bold", 21, UIStyle.SEAL_RED))
		var items: Variant = rd.get("items", {})
		if items is Dictionary:
			for iid: Variant in items:
				var ib := HBoxContainer.new()
				ib.add_theme_constant_override(&"separation", 4)
				ib.add_child(UIStyle.icon_rect(UIStyle.item_icon(StringName(str(iid))), 34))
				ib.add_child(UIStyle.label("×%d" % int(items[iid]), &"semibold", 19, UIStyle.TEXT_INK))
				rr.add_child(ib)
	if String(q.get("state", "")) == "active":
		var sp := Control.new()
		sp.size_flags_vertical = Control.SIZE_EXPAND_FILL
		page.add_child(sp)
		var tracked := bool(q.get("tracked", false))
		if tracked:
			# Already tracked: an ink stamp instead of a greyed-out button (unreadable on paper).
			var badge := HBoxContainer.new()
			badge.size_flags_horizontal = Control.SIZE_SHRINK_END
			badge.add_theme_constant_override(&"separation", 10)
			badge.add_child(UIStyle.icon_rect(UIStyle.glyph(&"quest"), 28, Color("#a8321e")))
			var bl := UIStyle.label(tr("JOURNAL_TRACKED"), &"semibold", 21, Color("#a8321e"))
			badge.add_child(bl)
			page.add_child(badge)
		else:
			var tb := Button.new()
			tb.theme_type_variation = &"PrimaryButton"
			tb.text = tr("JOURNAL_TRACK")
			tb.icon = UIStyle.glyph(&"quest")
			tb.custom_minimum_size = Vector2(300, 54)
			tb.size_flags_horizontal = Control.SIZE_SHRINK_END
			tb.pressed.connect(func() -> void:
				qm.call("track", qid)
				UIStyle.sfx(&"ui_confirm")
				_populate()
				focus_default.call_deferred())
			page.add_child(tb)
		UIStyle.wire_sounds(page)


# --- memories ----------------------------------------------------------------------------------

func _build_memories() -> void:
	var parts := _split()
	var gs := get_node_or_null(^"/root/GameState")
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 12)
	parts[0].add_child(v)
	var found := 0
	var ids: Array[StringName] = []
	for i in 12:
		ids.append(StringName("memory_%02d" % (i + 1)))
	for id in ids:
		if gs != null and (bool(gs.call("has_item", id)) or bool(gs.call("is_collectible_found", id))):
			found += 1
	v.add_child(UIStyle.label(tr("JOURNAL_MEMORIES_COUNT").format({"n": found}), &"semibold", 19, UIStyle.GOLD))
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override(&"h_separation", 12)
	grid.add_theme_constant_override(&"v_separation", 12)
	v.add_child(grid)
	var page := VBoxContainer.new()
	page.add_theme_constant_override(&"separation", 12)
	parts[1].add_child(page)
	for idx in ids.size():
		var id := ids[idx]
		var has := gs != null and (bool(gs.call("has_item", id)) or bool(gs.call("is_collectible_found", id)))
		var b := Button.new()
		b.theme_type_variation = &"FlatButton"
		b.custom_minimum_size = Vector2(150, 168)
		var photo := _Photo.new()
		photo.found = has
		photo.number = idx + 1
		photo.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		photo.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.add_child(photo)
		b.focus_entered.connect(func() -> void: _memory_page(page, id, has))
		b.pressed.connect(func() -> void: _memory_page(page, id, has))
		grid.add_child(b)
	_memory_page(page, ids[0], gs != null and (bool(gs.call("has_item", ids[0])) or bool(gs.call("is_collectible_found", ids[0]))))


func _memory_page(page: VBoxContainer, id: StringName, found: bool) -> void:
	for c in page.get_children():
		c.queue_free()
	var gs := get_node_or_null(^"/root/GameState")
	var big := _Photo.new()
	big.found = found
	big.number = int(String(id).right(2))
	big.custom_minimum_size = Vector2(300, 340)
	big.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	page.add_child(big)
	if not found:
		page.add_child(UIStyle.label(tr("JOURNAL_MEMORY_LOCKED"), &"heading", 34, UIStyle.TEXT_INK_DIM))
		var l := UIStyle.label(tr("JOURNAL_MEMORY_LOCKED_HINT"), &"prose_italic", 23, UIStyle.TEXT_INK_DIM)
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		page.add_child(l)
		return
	var nm := String(gs.call("get_item_name", id, false)) if gs != null else String(id)
	page.add_child(UIStyle.label(nm, &"heading", 34, UIStyle.TEXT_INK))
	var key := String(id).to_upper() + "_STORY"
	var txt := tr(key)
	if txt == key and gs != null:
		txt = tr(String((gs.call("get_item_def", id) as Dictionary).get("desc_key", "")))
	var r := UIStyle.rich(txt, 24, UIStyle.TEXT_INK, &"prose")
	r.theme_type_variation = &"InkProseText"
	r.add_theme_font_size_override(&"normal_font_size", 24)
	page.add_child(r)


# --- places ------------------------------------------------------------------------------------

func _build_places() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	var locs: Dictionary = gs.call("get_discovered_locations") if gs != null else {}
	var panel := PanelContainer.new()
	panel.theme_type_variation = &"PaperPanel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_body.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 14)
	panel.add_child(v)
	v.add_child(UIStyle.label(tr("JOURNAL_PLACES_COUNT").format({"n": locs.size()}), &"heading", 34, UIStyle.TEXT_INK))
	v.add_child(UIStyle.divider(520, Color(UIStyle.GOLD_DIM, 0.9)))
	if locs.is_empty():
		v.add_child(UIStyle.label(tr("JOURNAL_NO_PLACES"), &"prose_italic", 24, UIStyle.TEXT_INK_DIM))
		return
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override(&"h_separation", 40)
	grid.add_theme_constant_override(&"v_separation", 14)
	v.add_child(grid)
	var names: Array = []
	for id: Variant in locs:
		names.append([tr(String(locs[id])) if String(locs[id]) != "" else tr("LOC_" + str(id).to_upper()), str(id)])
	names.sort_custom(func(a: Array, b: Array) -> bool: return String(a[0]) < String(b[0]))
	for n: Array in names:
		var r := HBoxContainer.new()
		r.add_theme_constant_override(&"separation", 10)
		r.add_child(UIStyle.icon_rect(UIStyle.glyph(&"home" if n[1] == "tea_stall" else &"location"), 26, UIStyle.SEAL_RED))
		r.add_child(UIStyle.label(String(n[0]), &"medium", 23, UIStyle.TEXT_INK))
		grid.add_child(r)


# --- Cam ---------------------------------------------------------------------------------------

func _build_cam() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.add_theme_constant_override(&"separation", 30)
	_body.add_child(h)
	var col1 := PanelContainer.new()
	col1.theme_type_variation = &"PaperPanel"
	col1.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(col1)
	var v1 := VBoxContainer.new()
	v1.add_theme_constant_override(&"separation", 10)
	col1.add_child(v1)
	v1.add_child(UIStyle.label(tr("JOURNAL_ATTRIBUTES"), &"heading", 30, UIStyle.TEXT_INK))
	if gs != null:
		for a: StringName in [&"agility", &"stealth", &"charm", &"hunting"]:
			var r := HBoxContainer.new()
			var l := UIStyle.label(tr("ATTR_" + String(a).to_upper()), &"medium", 22, UIStyle.TEXT_INK)
			l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			r.add_child(l)
			r.add_child(UIStyle.label(str(int(gs.call("get_attribute", a))), &"title", 26, UIStyle.SEAL_RED))
			v1.add_child(r)
		v1.add_child(UIStyle.divider(420, Color(UIStyle.GOLD_DIM, 0.9)))
		v1.add_child(UIStyle.label(tr("JOURNAL_REPUTATION"), &"heading", 30, UIStyle.TEXT_INK))
		for f: StringName in [&"humans", &"rooftop_cats", &"birds"]:
			var rep := int(gs.call("get_reputation", f))
			var tier := String(gs.call("get_reputation_tier", f))
			var r2 := VBoxContainer.new()
			r2.add_theme_constant_override(&"separation", 2)
			var top := HBoxContainer.new()
			var fl := UIStyle.label(tr("FACTION_" + String(f).to_upper()), &"medium", 21, UIStyle.TEXT_INK)
			fl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			top.add_child(fl)
			top.add_child(UIStyle.label(tr("REP_TIER_" + tier.to_upper()), &"body_italic", 19, UIStyle.TEXT_INK_DIM))
			r2.add_child(top)
			var bar := _RepBar.new()
			bar.value = rep
			bar.custom_minimum_size = Vector2(0, 14)
			r2.add_child(bar)
			v1.add_child(r2)
	var col2 := PanelContainer.new()
	col2.theme_type_variation = &"PaperPanel"
	col2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(col2)
	var v2 := VBoxContainer.new()
	v2.add_theme_constant_override(&"separation", 8)
	col2.add_child(v2)
	v2.add_child(UIStyle.label(tr("JOURNAL_ACHIEVEMENTS"), &"heading", 30, UIStyle.TEXT_INK))
	if gs != null:
		var consts: Dictionary = (gs.get_script() as Script).get_script_constant_map() if gs.get_script() != null else {}
		var achs: Dictionary = consts.get("ACHIEVEMENTS", {}) if consts.get("ACHIEVEMENTS", {}) is Dictionary else {}
		for id: Variant in achs:
			var has := bool(gs.call("has_achievement", StringName(str(id))))
			var spec: Dictionary = achs[id]
			var prog := "  %d/%d" % [mini(int(gs.call("get_counter", StringName(String(spec.get("counter", ""))))), int(spec.get("target", 1))), int(spec.get("target", 1))]
			var r := HBoxContainer.new()
			r.add_theme_constant_override(&"separation", 10)
			r.add_child(UIStyle.icon_rect(UIStyle.glyph(&"achievement"), 30, UIStyle.SEAL_RED if has else Color(UIStyle.TEXT_INK_DIM, 0.4)))
			var av := VBoxContainer.new()
			av.add_theme_constant_override(&"separation", -2)
			av.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			av.add_child(UIStyle.label(tr("ACH_" + str(id).to_upper()) + ("" if has else prog), &"semibold", 21, UIStyle.TEXT_INK if has else UIStyle.TEXT_INK_DIM))
			var dl := UIStyle.label(tr("ACH_" + str(id).to_upper() + "_DESC") if has else tr("ACH_LOCKED") + " · " + tr("ACH_" + str(id).to_upper() + "_DESC"), &"body", 18, UIStyle.TEXT_INK_DIM)
			dl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			av.add_child(dl)
			r.add_child(av)
			v2.add_child(r)
		v2.add_child(UIStyle.divider(420, Color(UIStyle.GOLD_DIM, 0.9)))
		v2.add_child(UIStyle.label(tr("JOURNAL_STATS"), &"heading", 30, UIStyle.TEXT_INK))
		var tod := get_node_or_null(^"/root/TimeOfDay")
		var stats := [
			["STAT_DAYS", str(int(tod.get("day")) if tod != null else 1)],
			["STAT_PLAYTIME", UIStyle.fmt_playtime(float(gs.get("playtime_s")))],
			["STAT_KNOCKED", str(int(gs.call("get_counter", &"knocked_objects")))],
			["STAT_NAPS", str(int(gs.call("get_counter", &"naps")))],
			["STAT_TERRITORY", str(int(gs.call("get_counter", &"territory_marked")))],
			["STAT_PREY", str(int(gs.call("get_counter", &"prey_caught")))],
			["STAT_CAPS", str(int(gs.call("get_caps")))],
		]
		for s: Array in stats:
			var r := HBoxContainer.new()
			var l := UIStyle.label(tr(String(s[0])), &"medium", 20, UIStyle.TEXT_INK)
			l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			r.add_child(l)
			r.add_child(UIStyle.label(String(s[1]), &"semibold", 20, UIStyle.SEAL_RED))
			v2.add_child(r)


class _Photo extends Control:
	var found := false
	var number := 1

	func _draw() -> void:
		var r := Rect2(Vector2(8, 6), size - Vector2(16, 12))
		var rot := deg_to_rad(-2.0 + float(number % 3) * 2.0)
		draw_set_transform(size * 0.5, rot, Vector2.ONE)
		var rr := Rect2(r.position - size * 0.5, r.size)
		draw_rect(Rect2(rr.position + Vector2(3, 5), rr.size), Color(0, 0, 0, 0.35))
		draw_rect(rr, Color("#efe4cc") if found else Color("#cbbd9f"))
		var inner := Rect2(rr.position + Vector2(10, 10), rr.size - Vector2(20, 40))
		if found:
			var tex := UIStyle.tex(UIStyle.ICONS + "items/memory_photo.png")
			draw_rect(inner, Color("#9a774a"))
			if tex != null:
				draw_texture_rect_region(tex, inner, Rect2(Vector2(48, 44), Vector2(160, 140)), Color(1, 1, 1, 0.95))
		else:
			draw_rect(inner, Color("#5c4a36"))
			var f := UIStyle.font(&"title")
			var fs := int(inner.size.y * 0.45)
			var ts := f.get_string_size("?", HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
			draw_string(f, inner.get_center() + Vector2(-ts.x * 0.5, fs * 0.36), "?", HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color("#efe4cc", 0.4))
		var f2 := UIStyle.font(&"prose_italic")
		var label := "%02d" % number
		draw_string(f2, Vector2(rr.position.x + 12, rr.end.y - 10), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("#6b5944"))
		draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)


class _RepBar extends Control:
	var value := 0

	func _draw() -> void:
		var r := Rect2(Vector2(0, size.y * 0.5 - 4), Vector2(size.x, 8))
		draw_rect(r, Color(0.3, 0.22, 0.14, 0.25))
		var mid := r.position.x + r.size.x * 0.5
		draw_line(Vector2(mid, r.position.y - 3), Vector2(mid, r.end.y + 3), Color(0.3, 0.22, 0.14, 0.6), 1.5)
		var w := r.size.x * 0.5 * clampf(absf(float(value)) / 100.0, 0.0, 1.0)
		var col := UIStyle.JADE.darkened(0.25) if value >= 0 else UIStyle.SEAL_RED
		if value >= 0:
			draw_rect(Rect2(Vector2(mid, r.position.y), Vector2(w, r.size.y)), col)
		else:
			draw_rect(Rect2(Vector2(mid - w, r.position.y), Vector2(w, r.size.y)), col)
