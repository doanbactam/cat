extends Control
## Main menu over the live 3D rooftop backdrop: title with a red seal, ink-wash shade, drifting
## lantern bokeh, and a column of serif menu items (Continue / New game / Load / Settings /
## Credits / Quit). Sub-screens open on an internal UIMenuHost.

const SETTINGS_SCREEN := "res://scenes/ui/settings_menu.tscn"
const SAVE_SLOTS := "res://scenes/ui/save_slots.tscn"
const CREDITS := "res://scenes/ui/credits.tscn"

var host: UIMenuHost
var _menu_box: VBoxContainer
var _buttons: Array[Button] = []
var _continue_btn: Button = null
var _continue_detail: Label = null
var _title_block: Control
var _toast: Label
var _hints: UIHintBar
var _paw: TextureRect
var _bokeh: Control
var _revealed := false


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	theme = UIStyle.theme()
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build()
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"settings_changed", _on_settings_changed)


func _build() -> void:
	# Left ink-wash shade for legibility + soft vignette over the 3D scene.
	var wash := TextureRect.new()
	wash.texture = UIStyle.ui_tex("ink_wash")
	wash.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	wash.stretch_mode = TextureRect.STRETCH_SCALE
	wash.anchor_bottom = 1.0
	wash.anchor_right = 0.62
	wash.offset_left = -80
	wash.offset_top = -60
	wash.offset_bottom = 60
	wash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(wash)
	var shade := TextureRect.new()
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.32, 0.62, 1.0])
	g.colors = PackedColorArray([Color(0.04, 0.025, 0.02, 0.82), Color(0.05, 0.03, 0.02, 0.62), Color(0.05, 0.03, 0.02, 0.18), Color(0.05, 0.03, 0.02, 0.0)])
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.width = 256
	gt.height = 4
	shade.texture = gt
	shade.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	shade.stretch_mode = TextureRect.STRETCH_SCALE
	shade.anchor_bottom = 1.0
	shade.anchor_right = 0.7
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var vig := TextureRect.new()
	vig.texture = UIStyle.ui_tex("vignette")
	vig.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	vig.stretch_mode = TextureRect.STRETCH_SCALE
	vig.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vig.modulate = Color(1, 1, 1, 0.75)
	vig.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(vig)
	_bokeh = _Bokeh.new()
	_bokeh.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_bokeh.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_bokeh)

	# Title block
	var title := VBoxContainer.new()
	title.position = Vector2(124, 96)
	title.add_theme_constant_override(&"separation", 0)
	add_child(title)
	_title_block = title
	var row := HBoxContainer.new()
	row.add_theme_constant_override(&"separation", 22)
	title.add_child(row)
	var seal := UIStyle.icon_rect(UIStyle.ui_tex("seal_stamp"), 92)
	seal.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(seal)
	var name_l := UIStyle.label(tr("TITLE_MAIN"), &"title", 112, UIStyle.TEXT)
	name_l.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.55))
	name_l.add_theme_constant_override(&"shadow_offset_y", 4)
	name_l.add_theme_constant_override(&"shadow_outline_size", 10)
	row.add_child(name_l)
	var sub := UIStyle.label(tr("TITLE_SUB"), &"heading_italic", 58, UIStyle.GOLD_LIGHT)
	sub.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.5))
	sub.add_theme_constant_override(&"shadow_outline_size", 8)
	var sub_m := MarginContainer.new()
	sub_m.add_theme_constant_override(&"margin_left", 118)
	sub_m.add_theme_constant_override(&"margin_top", -14)
	sub_m.add_child(sub)
	title.add_child(sub_m)
	var tag := UIStyle.label(tr("MENU_TAGLINE"), &"prose_italic", 28, Color(UIStyle.TEXT, 0.9))
	tag.add_theme_color_override(&"font_shadow_color", Color(0, 0, 0, 0.6))
	tag.add_theme_constant_override(&"shadow_outline_size", 6)
	var tag_m := MarginContainer.new()
	tag_m.add_theme_constant_override(&"margin_left", 120)
	tag_m.add_theme_constant_override(&"margin_top", 10)
	tag_m.add_child(tag)
	title.add_child(tag_m)

	# Menu column
	_menu_box = VBoxContainer.new()
	_menu_box.position = Vector2(100, 470)
	_menu_box.custom_minimum_size = Vector2(620, 0)
	_menu_box.add_theme_constant_override(&"separation", 2)
	add_child(_menu_box)
	_paw = UIStyle.icon_rect(UIStyle.glyph(&"paw"), 30, UIStyle.LANTERN_GLOW)
	_paw.visible = false
	add_child(_paw)
	_rebuild_items()

	# Footer: version + studio, hints
	var foot := HBoxContainer.new()
	foot.anchor_top = 1.0
	foot.anchor_bottom = 1.0
	foot.anchor_right = 1.0
	foot.offset_left = 124
	foot.offset_right = -72
	foot.offset_top = -78
	foot.offset_bottom = -36
	add_child(foot)
	var ver := UIStyle.label("v%s  ·  %s" % [str(ProjectSettings.get_setting("application/config/version", "0.1")), tr("STUDIO_NAME")],
		&"medium", 18, Color(UIStyle.TEXT_DIM, 0.8))
	ver.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	ver.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	foot.add_child(ver)
	_hints = UIHintBar.new()
	_hints.set_hints([[&"ui_accept", "UI_SELECT"], [&"ui_cancel", "UI_BACK"]])
	foot.add_child(_hints)

	_toast = UIStyle.label("", &"medium", 22, UIStyle.GOLD_LIGHT)
	_toast.anchor_left = 0.0
	_toast.anchor_right = 1.0
	_toast.anchor_top = 1.0
	_toast.anchor_bottom = 1.0
	_toast.offset_top = -140
	_toast.offset_bottom = -100
	_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast.modulate.a = 0.0
	add_child(_toast)

	host = UIMenuHost.new()
	host.name = "MenuHost"
	add_child(host)
	host.stack_changed.connect(_on_stack_changed)


func _latest_save_slot() -> int:
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null:
		return -1
	var best := -1
	var best_t := -1.0
	for slot in range(0, 4):
		if not bool(gs.call("has_save", slot)):
			continue
		var info: Dictionary = gs.call("get_save_info", slot)
		var t := float(info.get("saved_at_unix", 0.0))
		if t <= 0.0:
			t = float(slot)  # older saves: prefer any
		var path := String(gs.call("get_save_path", slot))
		var mod := float(FileAccess.get_modified_time(path))
		t = maxf(t, mod)
		if t > best_t:
			best_t = t
			best = slot
	return best


func _rebuild_items() -> void:
	for c in _menu_box.get_children():
		c.queue_free()
	_buttons.clear()
	_continue_btn = null
	var slot := _latest_save_slot()
	if slot >= 0:
		_continue_btn = _add_item("MENU_CONTINUE", _on_continue.bind(slot))
		_continue_detail = UIStyle.label(_save_detail(slot), &"medium", 19, Color(UIStyle.TEXT_DIM, 0.9))
		var m := MarginContainer.new()
		m.add_theme_constant_override(&"margin_left", 44)
		m.add_theme_constant_override(&"margin_top", -8)
		m.add_theme_constant_override(&"margin_bottom", 8)
		m.add_child(_continue_detail)
		_menu_box.add_child(m)
	_add_item("MENU_NEW_GAME", _on_new_game)
	_add_item("MENU_LOAD", _on_load).disabled = slot < 0
	_add_item("MENU_SETTINGS", _on_settings)
	_add_item("MENU_CREDITS", _on_credits)
	_add_item("MENU_QUIT", _on_quit)
	for i in _buttons.size():
		var b := _buttons[i]
		b.focus_neighbor_top = b.get_path_to(_buttons[(i - 1 + _buttons.size()) % _buttons.size()])
		b.focus_neighbor_bottom = b.get_path_to(_buttons[(i + 1) % _buttons.size()])
	UIStyle.wire_sounds(_menu_box)


func _save_detail(slot: int) -> String:
	var gs := get_node_or_null(^"/root/GameState")
	if gs == null:
		return ""
	var info: Dictionary = gs.call("get_save_info", slot)
	var parts: PackedStringArray = []
	parts.append(tr("SLOT_DAY").format({"day": int(info.get("day", 1))}))
	parts.append(UIStyle.fmt_hour(float(info.get("hour", 0.0))))
	var loc := String(info.get("location", ""))
	if loc != "":
		parts.append(tr(loc))
	parts.append(tr("HUD_LEVEL").format({"level": int(info.get("level", 1))}))
	return "  ·  ".join(parts)


func _add_item(key: String, cb: Callable) -> Button:
	var b := Button.new()
	b.theme_type_variation = &"MenuItemButton"
	b.text = tr(key)
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT
	b.custom_minimum_size = Vector2(560, 70)
	b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	b.pressed.connect(cb)
	b.focus_entered.connect(_on_item_focus.bind(b))
	_menu_box.add_child(b)
	_buttons.append(b)
	return b


func _on_item_focus(b: Button) -> void:
	_paw.visible = true
	await get_tree().process_frame
	if not is_instance_valid(b):
		return
	var target := b.global_position + Vector2(-34, b.size.y * 0.5 - 15)
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(_paw, "global_position", target, 0.18 if _paw.modulate.a > 0.5 else 0.0)
	_paw.modulate.a = 1.0
	_paw.rotation = deg_to_rad(-12)


## Animated entrance after the splash.
func reveal() -> void:
	_revealed = true
	_title_block.modulate.a = 0.0
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(_title_block, "modulate:a", 1.0, 1.4)
	var i := 0
	for c in _menu_box.get_children():
		var ci := c as Control
		ci.modulate.a = 0.0
		tw.tween_property(ci, "modulate:a", 1.0, 0.6).set_delay(0.5 + 0.08 * i)
		i += 1
	_focus_first.call_deferred()


func _focus_first() -> void:
	if not _buttons.is_empty() and host.depth() == 0:
		for b in _buttons:
			if not b.disabled:
				b.grab_focus()
				return


func _on_stack_changed(depth: int) -> void:
	var show := depth == 0
	_menu_box.visible = show
	_title_block.visible = show
	_paw.visible = show
	_hints.visible = show
	if show:
		_rebuild_items()
		_focus_first.call_deferred()


func show_toast(text: String) -> void:
	_toast.text = text
	var tw := create_tween()
	tw.tween_property(_toast, "modulate:a", 1.0, 0.25)
	tw.tween_interval(3.0)
	tw.tween_property(_toast, "modulate:a", 0.0, 0.6)


func _loader() -> Node:
	return get_node_or_null(^"/root/SceneLoader")


func _on_continue(slot: int) -> void:
	var l := _loader()
	if l == null or String(l.call("get_game_scene_path")) == "":
		show_toast(tr("UI_NO_GAME_SCENE"))
		return
	UIStyle.sfx(&"ui_confirm")
	if not bool(l.call("continue_game", slot)):
		show_toast(tr("UI_LOAD_FAILED"))


func _on_new_game() -> void:
	var l := _loader()
	if l == null or String(l.call("get_game_scene_path")) == "":
		show_toast(tr("UI_NO_GAME_SCENE"))
		return
	if _latest_save_slot() >= 0:
		var d := UIConfirmDialog.make("CONFIRM_NEW_GAME_TITLE", "CONFIRM_NEW_GAME_BODY")
		d.confirmed.connect(func() -> void:
			UIStyle.sfx(&"ui_confirm")
			l.call("start_new_game"))
		host.push_screen(d)
	else:
		UIStyle.sfx(&"ui_confirm")
		l.call("start_new_game")


func _on_load() -> void:
	var s := host.push_screen(SAVE_SLOTS)
	if s != null:
		s.set("mode", &"load")


func _on_settings() -> void:
	host.push_screen(SETTINGS_SCREEN)


func _on_credits() -> void:
	host.push_screen(CREDITS)


func _on_quit() -> void:
	var d := UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_MENU_BODY", true)
	d.confirmed.connect(func() -> void:
		var s := get_node_or_null(^"/root/Settings")
		if s != null and bool(s.call("is_dirty")):
			s.call("save")
		get_tree().quit())
	host.push_screen(d)


func _unhandled_input(event: InputEvent) -> void:
	if host.depth() > 0 or not _revealed:
		return
	if event.is_action_pressed(&"ui_cancel"):
		get_viewport().set_input_as_handled()
		_on_quit()


func _on_settings_changed(section: StringName) -> void:
	if section == &"gameplay" and host.depth() == 0:
		_rebuild_items()


## Drifting lantern bokeh (additive discs) in the screen layer — the menu's subtle motion.
class _Bokeh extends Control:
	var _p: Array[Dictionary] = []
	var _tex: Texture2D
	var _rng := RandomNumberGenerator.new()

	func _ready() -> void:
		_tex = UIStyle.ui_tex("bokeh")
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		material = mat
		_rng.seed = 42
		for i in 14:
			_p.append(_spawn(true))

	func _spawn(anywhere: bool) -> Dictionary:
		var w := size.x if size.x > 0 else 1920.0
		var h := size.y if size.y > 0 else 1080.0
		var warm := [Color("#ff8a3a"), Color("#ffb45a"), Color("#ff5a3a"), Color("#ffd27a")]
		return {
			"pos": Vector2(_rng.randf_range(w * 0.25, w * 1.05), _rng.randf_range(h * 0.35, h * 1.0) if anywhere else h + 60.0),
			"r": _rng.randf_range(8.0, 34.0),
			"v": Vector2(_rng.randf_range(-7.0, -1.5), _rng.randf_range(-10.0, -3.0)),
			"c": warm[_rng.randi() % warm.size()],
			"a": _rng.randf_range(0.03, 0.09),
			"ph": _rng.randf() * TAU,
		}

	func _process(delta: float) -> void:
		for i in _p.size():
			var d := _p[i]
			d["pos"] = (d["pos"] as Vector2) + (d["v"] as Vector2) * delta
			d["ph"] = float(d["ph"]) + delta * 0.6
			if (d["pos"] as Vector2).y < -80.0 or (d["pos"] as Vector2).x < -80.0:
				_p[i] = _spawn(false)
		queue_redraw()

	func _draw() -> void:
		if _tex == null:
			return
		for d in _p:
			var r := float(d["r"])
			var a := float(d["a"]) * (0.7 + 0.3 * sin(float(d["ph"])))
			var c: Color = d["c"]
			c.a = a
			draw_texture_rect(_tex, Rect2((d["pos"] as Vector2) - Vector2(r, r), Vector2(r, r) * 2.0), false, c)
