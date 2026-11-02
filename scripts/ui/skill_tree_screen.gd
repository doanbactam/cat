extends UIScreen
## Skills (Kỹ năng). Five trees side by side (Agility, Stealth, Charm, Hunting, Survival), each a
## 3×3 lattice of medallions placed by skills.json `pos` with ink lines for prerequisites.
## Node states: learned (filled tree colour), available (pulsing gold ring), locked (dim).
## Bottom: the selected skill's page (description, effects, requirements, cost, Learn) and the
## attributes panel (pips + Raise when attribute points are available).

const NODE := 84.0
const COL_W := 104.0
const ROW_H := 142.0

var _trees_row: HBoxContainer
var _nodes: Dictionary = {}        # skill_id -> _SkillNode
var _canvases: Array[Control] = []
var _selected: StringName = &""
var _d_icon: TextureRect
var _d_name: Label
var _d_tier: Label
var _d_desc: RichTextLabel
var _d_effects: VBoxContainer
var _d_req: Label
var _learn: Button
var _sp_label: Label
var _ap_label: Label
var _attr_box: VBoxContainer
var _frame: Dictionary


func _init() -> void:
	menu_id = &"skills"


func _gs() -> Node:
	return get_node_or_null(^"/root/GameState")


func build() -> void:
	_frame = make_frame("SKILLS_TITLE", &"skill")
	var header: HBoxContainer = _frame["header"]
	var pts := HBoxContainer.new()
	pts.add_theme_constant_override(&"separation", 26)
	header.add_child(pts)
	_sp_label = _points_badge(pts, "SKILLS_POINTS", UIStyle.LANTERN_GLOW)
	_ap_label = _points_badge(pts, "SKILLS_ATTR_POINTS", UIStyle.JADE)
	var content: Control = _frame["content"]
	var v := VBoxContainer.new()
	v.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	v.add_theme_constant_override(&"separation", 16)
	content.add_child(v)
	_trees_row = HBoxContainer.new()
	_trees_row.add_theme_constant_override(&"separation", 12)
	_trees_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(_trees_row)
	var bottom := HBoxContainer.new()
	bottom.add_theme_constant_override(&"separation", 18)
	bottom.custom_minimum_size = Vector2(0, 250)
	v.add_child(bottom)
	# detail page
	var page := PanelContainer.new()
	page.theme_type_variation = &"PaperPanel"
	page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bottom.add_child(page)
	var ph := HBoxContainer.new()
	ph.add_theme_constant_override(&"separation", 26)
	page.add_child(ph)
	var medal := PanelContainer.new()
	medal.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color("#2a1a12"), 64, UIStyle.GOLD, 3, 14.0))
	medal.custom_minimum_size = Vector2(128, 128)
	medal.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	ph.add_child(medal)
	_d_icon = UIStyle.icon_rect(null, 84, UIStyle.GOLD_LIGHT)
	medal.add_child(_d_icon)
	var dv := VBoxContainer.new()
	dv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	dv.add_theme_constant_override(&"separation", 4)
	ph.add_child(dv)
	_d_tier = UIStyle.label("", &"semibold", 15, UIStyle.SEAL_RED)
	_d_tier.uppercase = true
	dv.add_child(_d_tier)
	_d_name = UIStyle.label("", &"heading", 34, UIStyle.TEXT_INK)
	dv.add_child(_d_name)
	_d_desc = UIStyle.rich("", 22, UIStyle.TEXT_INK, &"prose")
	_d_desc.theme_type_variation = &"InkProseText"
	_d_desc.add_theme_font_size_override(&"normal_font_size", 22)
	dv.add_child(_d_desc)
	_d_req = UIStyle.label("", &"medium", 19, UIStyle.SEAL_RED)
	_d_req.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dv.add_child(_d_req)
	var ev := VBoxContainer.new()
	ev.custom_minimum_size = Vector2(380, 0)
	ev.add_theme_constant_override(&"separation", 6)
	ph.add_child(ev)
	var eh := UIStyle.label(tr("SKILLS_EFFECTS"), &"semibold", 16, UIStyle.TEXT_INK_DIM)
	eh.uppercase = true
	ev.add_child(eh)
	_d_effects = VBoxContainer.new()
	_d_effects.add_theme_constant_override(&"separation", 4)
	ev.add_child(_d_effects)
	var sp := Control.new()
	sp.size_flags_vertical = Control.SIZE_EXPAND_FILL
	ev.add_child(sp)
	_learn = Button.new()
	_learn.theme_type_variation = &"PrimaryButton"
	_learn.text = tr("SKILLS_LEARN")
	_learn.custom_minimum_size = Vector2(260, 54)
	_learn.size_flags_horizontal = Control.SIZE_SHRINK_END
	_learn.pressed.connect(_on_learn)
	ev.add_child(_learn)
	# attributes
	var ap := PanelContainer.new()
	ap.theme_type_variation = &"SmallLacquerPanel"
	ap.custom_minimum_size = Vector2(520, 0)
	bottom.add_child(ap)
	var av := VBoxContainer.new()
	av.add_theme_constant_override(&"separation", 6)
	ap.add_child(av)
	var at := UIStyle.label(tr("SKILLS_ATTRIBUTES"), &"semibold", 16, UIStyle.GOLD)
	at.uppercase = true
	av.add_child(at)
	_attr_box = VBoxContainer.new()
	_attr_box.add_theme_constant_override(&"separation", 4)
	av.add_child(_attr_box)
	(_frame["hints"] as UIHintBar).set_hints([[&"ui_accept", "UI_SELECT"], [&"ui_cancel", "UI_BACK"]])
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"skill_points_changed", func(_a: int, _b: int) -> void: _refresh_states())
		ge.connect(&"attribute_changed", func(_a: StringName, _v: int) -> void: _refresh_states())
	_build_trees()
	_refresh_states()


func _points_badge(parent: Control, key: String, col: Color) -> Label:
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 8)
	parent.add_child(h)
	var n := UIStyle.label("0", &"title", 34, col)
	h.add_child(n)
	var l := UIStyle.label(tr(key), &"medium", 19, UIStyle.TEXT_DIM)
	l.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(l)
	return n


func _build_trees() -> void:
	var gs := _gs()
	if gs == null:
		return
	var trees: Dictionary = gs.call("get_skill_trees")
	var skills: Dictionary = gs.call("get_all_skills")
	for tree_id: String in ["agility", "stealth", "charm", "hunting", "survival"]:
		if not trees.has(tree_id):
			continue
		var td: Dictionary = trees[tree_id]
		var col := Color(String(td.get("color", "#d9a441")))
		var panel := PanelContainer.new()
		panel.theme_type_variation = &"GlassPanel"
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_trees_row.add_child(panel)
		var tv := VBoxContainer.new()
		tv.add_theme_constant_override(&"separation", 6)
		panel.add_child(tv)
		var th := HBoxContainer.new()
		th.add_theme_constant_override(&"separation", 10)
		th.alignment = BoxContainer.ALIGNMENT_CENTER
		tv.add_child(th)
		th.add_child(UIStyle.icon_rect(UIStyle.skill_icon(StringName("tree_" + tree_id)), 34, col))
		th.add_child(UIStyle.label(tr(String(td.get("name_key", tree_id))), &"heading", 27, UIStyle.TEXT))
		var attr := String(td.get("attribute", ""))
		var sub := UIStyle.label("" if attr == "" else "%s %d" % [tr("ATTR_" + attr.to_upper()), int(gs.call("get_attribute", StringName(attr)))],
			&"medium", 17, Color(col, 0.95))
		sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		sub.set_meta(&"attr", attr)
		tv.add_child(sub)
		var canvas := _TreeCanvas.new()
		canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
		canvas.custom_minimum_size = Vector2(3 * COL_W, 3 * ROW_H)
		canvas.tree_color = col
		tv.add_child(canvas)
		_canvases.append(canvas)
		for sid: String in gs.call("get_skills_in_tree", StringName(tree_id)):
			var sd: Dictionary = skills[sid]
			var node := _SkillNode.new()
			node.skill_id = StringName(sid)
			node.tree_color = col
			node.icon_tex = UIStyle.skill_icon(StringName(sid))
			node.custom_minimum_size = Vector2(NODE, NODE)
			node.size = Vector2(NODE, NODE)
			var pos: Array = sd.get("pos", [0, 0])
			node.grid = Vector2i(int(pos[0]), int(pos[1]))
			node.tooltip_text = tr(String(sd.get("name_key", sid)))
			canvas.add_child(node)
			canvas.nodes[StringName(sid)] = node
			canvas.requires[StringName(sid)] = sd.get("requires", [])
			node.focus_entered.connect(_select.bind(StringName(sid)))
			node.pressed.connect(_on_node_pressed.bind(StringName(sid)))
			_nodes[StringName(sid)] = node
	UIStyle.wire_sounds(_trees_row)


func default_focus() -> Control:
	var gs := _gs()
	if gs != null:
		for sid: StringName in _nodes:
			if StringName(gs.call("get_skill_state", sid)) == &"available":
				return _nodes[sid]
	for sid: StringName in _nodes:
		return _nodes[sid]
	return null


func _refresh_states() -> void:
	var gs := _gs()
	if gs == null:
		return
	_sp_label.text = str(int(gs.get("skill_points")))
	_ap_label.text = str(int(gs.get("attribute_points")))
	for sid: StringName in _nodes:
		(_nodes[sid] as _SkillNode).state = StringName(gs.call("get_skill_state", sid))
		(_nodes[sid] as _SkillNode).queue_redraw()
	for c in _canvases:
		c.queue_redraw()
	for sub in _trees_row.find_children("*", "Label", true, false):
		if sub.has_meta(&"attr") and String(sub.get_meta(&"attr")) != "":
			var a := String(sub.get_meta(&"attr"))
			(sub as Label).text = "%s %d" % [tr("ATTR_" + a.to_upper()), int(gs.call("get_attribute", StringName(a)))]
	_build_attributes()
	if _selected != &"":
		_select(_selected)


func _build_attributes() -> void:
	for c in _attr_box.get_children():
		c.queue_free()
	var gs := _gs()
	var points := int(gs.get("attribute_points"))
	for a: StringName in [&"agility", &"stealth", &"charm", &"hunting"]:
		var row := HBoxContainer.new()
		row.add_theme_constant_override(&"separation", 10)
		_attr_box.add_child(row)
		var l := UIStyle.label(tr("ATTR_" + String(a).to_upper()), &"medium", 21, UIStyle.TEXT)
		l.custom_minimum_size = Vector2(150, 0)
		row.add_child(l)
		var pips := _Pips.new()
		pips.value = int(gs.call("get_attribute", a))
		pips.custom_minimum_size = Vector2(200, 30)
		pips.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(pips)
		var vlab := UIStyle.label(str(pips.value), &"bold", 21, UIStyle.GOLD_LIGHT)
		vlab.custom_minimum_size = Vector2(30, 0)
		row.add_child(vlab)
		var b := Button.new()
		b.text = "+"
		b.custom_minimum_size = Vector2(48, 38)
		b.disabled = points <= 0 or pips.value >= 10
		b.tooltip_text = tr("ATTR_" + String(a).to_upper() + "_DESC")
		var attr := a
		b.pressed.connect(func() -> void:
			if bool(gs.call("raise_attribute", attr)):
				UIStyle.sfx(&"ui_skill_unlock")
			_refresh_states())
		row.add_child(b)
	UIStyle.wire_sounds(_attr_box)


func _select(sid: StringName) -> void:
	_selected = sid
	var gs := _gs()
	if gs == null:
		return
	var sd: Dictionary = gs.call("get_skill_def", sid)
	var tree: Dictionary = (gs.call("get_skill_trees") as Dictionary).get(String(sd.get("tree", "")), {})
	_d_icon.texture = UIStyle.skill_icon(sid)
	_d_icon.modulate = Color(String(tree.get("color", "#f2cf7e"))).lightened(0.25)
	_d_name.text = tr(String(sd.get("name_key", sid)))
	_d_tier.text = "%s · %s" % [tr(String(tree.get("name_key", ""))), tr("SKILLS_TIER").format({"n": int(sd.get("tier", 1))})]
	_d_desc.text = tr(String(sd.get("desc_key", "")))
	for c in _d_effects.get_children():
		c.queue_free()
	var eff: Dictionary = sd.get("effects", {})
	for mod: String in eff:
		var fe := UIStyle.format_effect(mod, float(eff[mod]))
		var r := HBoxContainer.new()
		r.add_theme_constant_override(&"separation", 8)
		r.add_child(UIStyle.icon_rect(UIStyle.glyph(&"buff"), 18, UIStyle.JADE.darkened(0.3) if bool(fe[1]) else UIStyle.SEAL_RED))
		r.add_child(UIStyle.label(String(fe[0]), &"medium", 20, UIStyle.TEXT_INK))
		_d_effects.add_child(r)
	var state := StringName(gs.call("get_skill_state", sid))
	match state:
		&"unlocked":
			_d_req.text = tr("SKILLS_LEARNED")
			_d_req.add_theme_color_override(&"font_color", UIStyle.JADE.darkened(0.35))
			_learn.disabled = true
			_learn.text = tr("SKILLS_LEARNED")
		&"available":
			_d_req.text = tr("SKILLS_COST").format({"n": int(sd.get("cost", 1))})
			_d_req.add_theme_color_override(&"font_color", UIStyle.TEXT_INK_DIM)
			_learn.disabled = false
			_learn.text = tr("SKILLS_LEARN")
		_:
			_d_req.text = tr("SKILLS_REQUIRES").format({"req": String(gs.call("get_skill_lock_reason", sid))})
			_d_req.add_theme_color_override(&"font_color", UIStyle.SEAL_RED)
			_learn.disabled = true
			_learn.text = tr("SKILLS_LOCKED")


func _on_node_pressed(sid: StringName) -> void:
	_select(sid)
	if not _learn.disabled:
		_learn.grab_focus()


func _on_learn() -> void:
	var gs := _gs()
	if gs == null or _selected == &"":
		return
	if bool(gs.call("unlock_skill", _selected)):
		var n: _SkillNode = _nodes.get(_selected)
		if n != null:
			n.flash = 1.0
			n.grab_focus()
	_refresh_states()


# --- drawing helpers ---------------------------------------------------------------------------

class _TreeCanvas extends Control:
	var nodes: Dictionary = {}
	var requires: Dictionary = {}
	var tree_color := Color.WHITE

	func _notification(what: int) -> void:
		if what == NOTIFICATION_RESIZED or what == NOTIFICATION_READY:
			_layout()

	func _layout() -> void:
		var cw := size.x / 3.0
		var rh := minf(size.y / 3.0, 150.0)
		var top := maxf(0.0, (size.y - rh * 3.0) * 0.5)
		for sid: StringName in nodes:
			var n: Control = nodes[sid]
			var g: Vector2i = n.get("grid")
			n.position = Vector2(cw * (g.x + 0.5), top + rh * (g.y + 0.5)) - n.size * 0.5

	func _draw() -> void:
		for sid: StringName in requires:
			if not nodes.has(sid):
				continue
			var b: Control = nodes[sid]
			for r: Variant in requires[sid]:
				var rid := StringName(str(r))
				if not nodes.has(rid):
					continue
				var a: Control = nodes[rid]
				var p0 := a.position + a.size * 0.5
				var p1 := b.position + b.size * 0.5
				var learned := StringName(a.get("state")) == &"unlocked"
				var col := Color(tree_color, 0.85) if learned else Color(UIStyle.TEXT_MUTED, 0.45)
				var dir := (p1 - p0).normalized()
				var s0 := p0 + dir * (a.size.x * 0.5 + 4.0)
				var s1 := p1 - dir * (b.size.x * 0.5 + 4.0)
				draw_line(s0, s1, Color(0, 0, 0, 0.45), 6.0, true)
				draw_line(s0, s1, col, 3.0 if learned else 2.0, true)


class _SkillNode extends Button:
	var skill_id: StringName = &""
	var state: StringName = &"locked"
	var tree_color := Color.WHITE
	var icon_tex: Texture2D
	var grid := Vector2i.ZERO
	var flash := 0.0
	var _t := 0.0

	func _init() -> void:
		flat = true
		focus_mode = Control.FOCUS_ALL
		add_theme_stylebox_override(&"focus", StyleBoxEmpty.new())

	func _process(delta: float) -> void:
		_t += delta
		flash = maxf(0.0, flash - delta * 1.2)
		if state == &"available" or has_focus() or flash > 0.0:
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.5 - 3.0
		draw_circle(c + Vector2(0, 3), r, Color(0, 0, 0, 0.5))
		match state:
			&"unlocked":
				draw_circle(c, r, tree_color.darkened(0.35))
				draw_circle(c, r - 5.0, tree_color.darkened(0.1))
				draw_arc(c, r, 0.0, TAU, 48, UIStyle.GOLD_LIGHT, 2.5, true)
			&"available":
				draw_circle(c, r, Color("#2a1a12"))
				var p := 0.5 + 0.5 * sin(_t * 3.0)
				draw_arc(c, r, 0.0, TAU, 48, UIStyle.GOLD.lerp(UIStyle.GOLD_LIGHT, p), 3.0, true)
				draw_arc(c, r + 4.0 + p * 3.0, 0.0, TAU, 48, Color(UIStyle.LANTERN_GLOW, 0.35 * (1.0 - p)), 2.0, true)
			_:
				draw_circle(c, r, Color("#1a1310"))
				draw_arc(c, r, 0.0, TAU, 48, Color(UIStyle.TEXT_MUTED, 0.5), 1.5, true)
		if icon_tex != null:
			var s := r * 1.15
			var ic := Color.WHITE if state == &"unlocked" else (UIStyle.GOLD_LIGHT if state == &"available" else Color(UIStyle.TEXT_MUTED, 0.7))
			draw_texture_rect(icon_tex, Rect2(c - Vector2(s, s) * 0.5, Vector2(s, s)), false, ic)
		if state == &"locked":
			var lk := UIStyle.glyph(&"lock")
			if lk != null:
				draw_texture_rect(lk, Rect2(c + Vector2(r * 0.42, r * 0.42) - Vector2(11, 11), Vector2(22, 22)), false, Color(UIStyle.TEXT_DIM, 0.9))
		if has_focus():
			draw_arc(c, r + 7.0, 0.0, TAU, 48, UIStyle.LANTERN, 3.0, true)
		if flash > 0.0:
			draw_circle(c, r + 18.0 * (1.0 - flash), Color(1.0, 0.9, 0.6, 0.45 * flash))


class _Pips extends Control:
	var value := 1

	func _draw() -> void:
		var n := 10
		var w := size.x / n
		for i in n:
			var c := Vector2(w * (i + 0.5), size.y * 0.5)
			if i < value:
				draw_circle(c, 7.0, UIStyle.GOLD)
				draw_circle(c, 3.0, UIStyle.GOLD_LIGHT)
			else:
				draw_arc(c, 6.0, 0.0, TAU, 20, Color(UIStyle.TEXT_MUTED, 0.6), 1.5, true)
