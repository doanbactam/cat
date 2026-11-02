extends UIScreen
## Settings (Cài đặt): tabs Graphics / Audio / Controls / Gameplay. Every change applies live
## through the Settings autoload; the file is written when the screen closes.
## Right column: help panel describing the focused option. Controls tab: rebindable key list
## (keyboard/mouse and gamepad columns, conflict warning, reset).

const TABS: PackedStringArray = ["SET_TAB_GRAPHICS", "SET_TAB_AUDIO", "SET_TAB_CONTROLS", "SET_TAB_GAMEPLAY"]
const TAB_ICONS: Array = [&"graphics", &"audio", &"controls", &"gameplay"]

var _tab := 0
var _tabs_bar: HBoxContainer
var _scroll: ScrollContainer
var _list: VBoxContainer
var _help_title: Label
var _help_body: RichTextLabel
var _help_icon: TextureRect
var _rows: Dictionary = {}        # "section/key" -> {"control": Control, "row": Control}
var _capture: Dictionary = {}     # rebinding state {"action", "pad", "button"}
var _capture_label: Label
var _frame: Dictionary


func _init() -> void:
	menu_id = &"settings"


func build() -> void:
	_frame = make_frame("SETTINGS_TITLE", &"gear")
	var header: HBoxContainer = _frame["header"]
	_tabs_bar = make_tabs(TABS, TAB_ICONS, _select_tab)
	header.add_child(_tabs_bar)
	var content: Control = _frame["content"]
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.add_theme_constant_override(&"separation", 36)
	content.add_child(h)
	var left := PanelContainer.new()
	left.theme_type_variation = &"GlassPanel"
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 1.9
	h.add_child(left)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.follow_focus = true
	left.add_child(_scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override(&"separation", 4)
	_scroll.add_child(_list)
	var help := PanelContainer.new()
	help.theme_type_variation = &"LacquerPanel"
	help.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	help.size_flags_stretch_ratio = 1.0
	h.add_child(help)
	var hv := VBoxContainer.new()
	hv.add_theme_constant_override(&"separation", 16)
	help.add_child(hv)
	_help_icon = UIStyle.icon_rect(UIStyle.glyph(&"gear"), 56, UIStyle.GOLD)
	_help_icon.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	hv.add_child(_help_icon)
	_help_title = UIStyle.label("", &"heading", 34, UIStyle.TEXT)
	_help_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hv.add_child(_help_title)
	hv.add_child(UIStyle.divider(300, Color(UIStyle.GOLD, 0.6)))
	_help_body = UIStyle.rich("", 23, UIStyle.TEXT_DIM, &"body")
	hv.add_child(_help_body)
	_capture_label = UIStyle.label("", &"semibold", 22, UIStyle.LANTERN_GLOW)
	_capture_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hv.add_child(_capture_label)
	(_frame["hints"] as UIHintBar).set_hints([
		[&"ui_accept", "UI_SELECT"], ["@← / →|←/→", "UI_CHANGE"], ["@Q / E|LB / RB", "UI_TABS"], [&"ui_cancel", "UI_BACK"]])
	_populate()


func _select_tab(i: int) -> void:
	if _tab == i and _list.get_child_count() > 0:
		return
	_tab = i
	_populate()
	_focus_first_row.call_deferred()


func on_tab_input(dir: int) -> bool:
	if not _capture.is_empty():
		return false
	var n := posmod(_tab + dir, TABS.size())
	(_tabs_bar.get_child(n) as Button).button_pressed = true
	_select_tab(n)
	return true


func default_focus() -> Control:
	for r: Dictionary in _rows.values():
		var c: Control = r["control"]
		if c.focus_mode == Control.FOCUS_ALL and c.is_visible_in_tree():
			return c
	return null


func _focus_first_row() -> void:
	var f := UIStyle.first_focusable(_list)
	if f != null:
		f.grab_focus()


func handle_back() -> bool:
	if not _capture.is_empty():
		_end_capture(null)
		return true
	_save()
	return false


func _exit_tree() -> void:
	_save()


func _save() -> void:
	var s := get_node_or_null(^"/root/Settings")
	if s != null and bool(s.call("is_dirty")):
		s.call("save")


# =============================================================================================
# Rows
# =============================================================================================

func _s() -> Node:
	return get_node_or_null(^"/root/Settings")


func _sv_get(section: String, key: String) -> Variant:
	var s := _s()
	return s.call("get_value", section, key) if s != null else null


func _sv_set(section: String, key: String, v: Variant) -> void:
	var s := _s()
	if s != null:
		s.call("set_value", section, key, v)


func _populate() -> void:
	for c in _list.get_children():
		_list.remove_child(c)
		c.queue_free()
	_rows.clear()
	match _tab:
		0:
			_build_graphics()
		1:
			_build_audio()
		2:
			_build_controls()
		3:
			_build_gameplay()
	_wire_focus_chain()
	UIStyle.wire_sounds(_list)
	_show_help("", "", &"")


func _wire_focus_chain() -> void:
	var ctrls: Array[Control] = []
	for c in _list.find_children("*", "Control", true, false):
		var cc := c as Control
		if cc.focus_mode == Control.FOCUS_ALL:
			ctrls.append(cc)
	for i in ctrls.size():
		var c := ctrls[i]
		if i > 0:
			c.focus_neighbor_top = c.get_path_to(ctrls[i - 1])
		if i < ctrls.size() - 1:
			c.focus_neighbor_bottom = c.get_path_to(ctrls[i + 1])


func _header(key: String) -> void:
	var l := UIStyle.label(tr(key), &"semibold", 17, UIStyle.GOLD)
	l.uppercase = true
	var m := MarginContainer.new()
	m.add_theme_constant_override(&"margin_top", 18 if _list.get_child_count() > 0 else 4)
	m.add_theme_constant_override(&"margin_left", 10)
	m.add_theme_constant_override(&"margin_bottom", 4)
	m.add_child(l)
	_list.add_child(m)


func _row(label_key: String, control: Control, help_key: String, icon: StringName, path: String = "") -> HBoxContainer:
	var row := HBoxContainer.new()
	row.custom_minimum_size = Vector2(0, 60)
	row.add_theme_constant_override(&"separation", 16)
	var bg := PanelContainer.new()
	bg.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color(1, 1, 1, 0.0), 8, Color(0, 0, 0, 0), 0, 10.0))
	bg.mouse_filter = Control.MOUSE_FILTER_PASS
	bg.add_child(row)
	var l := UIStyle.label(tr(label_key), &"medium", 23, UIStyle.TEXT)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.size_flags_vertical = Control.SIZE_FILL
	row.add_child(l)
	control.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(control)
	_list.add_child(bg)
	var focus_target: Control = control
	if control is HBoxContainer:
		focus_target = UIStyle.first_focusable(control)
	if focus_target != null:
		focus_target.focus_entered.connect(func() -> void:
			bg.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color("#7a2416", 0.32), 8, Color(UIStyle.GOLD, 0.35), 1, 10.0))
			_show_help(label_key, help_key, icon))
		focus_target.focus_exited.connect(func() -> void:
			bg.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color(1, 1, 1, 0.0), 8, Color(0, 0, 0, 0), 0, 10.0)))
	if path != "":
		_rows[path] = {"control": control, "row": bg, "label": l}
	return row


func _show_help(title_key: String, help_key: String, icon: StringName) -> void:
	if title_key == "":
		_help_title.text = tr(TABS[_tab])
		_help_body.text = tr(TABS[_tab] + "_DESC")
		_help_icon.texture = UIStyle.glyph(TAB_ICONS[_tab])
		return
	_help_title.text = tr(title_key)
	_help_body.text = tr(help_key) if help_key != "" else ""
	_help_icon.texture = UIStyle.glyph(icon if icon != &"" else TAB_ICONS[_tab])
	if title_key == "SET_QUALITY":
		_help_body.text += "\n\n" + _preset_summary()


func _preset_summary() -> String:
	var s := _s()
	if s == null:
		return ""
	var q := String(s.call("get_value", "graphics", "quality"))
	if q == "custom":
		return "[i]" + tr("SET_QUALITY_CUSTOM_NOTE") + "[/i]"
	var row: Dictionary = s.call("get_quality_preset_values", q)
	var on: PackedStringArray = []
	for k in ["sdfgi", "ssr", "ssao", "ssil", "volumetric_fog"]:
		if bool(row.get(k, false)):
			on.append(tr("SET_SHORT_" + k.to_upper()))
	return "[color=#f2cf7e]%s[/color]\n%s: %d%%  ·  %s: %s\n%s: %s" % [
		tr("Q_" + q.to_upper()),
		tr("SET_RENDER_SCALE"), int(round(float(row.get("render_scale", 1.0)) * 100.0)),
		tr("SET_SHADOWS"), tr("Q_" + String(row.get("shadow_quality", "high")).to_upper()),
		tr("SET_EFFECTS_ON"), ", ".join(on) if not on.is_empty() else "—"]


func _toggle(section: String, key: String, label_key: String, icon: StringName = &"") -> void:
	var t := CheckButton.new()
	t.button_pressed = bool(_sv_get(section, key))
	t.custom_minimum_size = Vector2(90, 48)
	t.toggled.connect(func(on: bool) -> void:
		_sv_set(section, key, on)
		_after_change(section, key))
	_row(label_key, t, label_key + "_DESC", icon, section + "/" + key)


func _selector(section: String, key: String, label_key: String, opts: Array, icon: StringName = &"") -> UISelector:
	var sel := UISelector.new()
	sel.set_options(opts, _sv_get(section, key))
	sel.value_changed.connect(func(v: Variant) -> void:
		_sv_set(section, key, v)
		_after_change(section, key))
	_row(label_key, sel, label_key + "_DESC", icon, section + "/" + key)
	return sel


func _slider(section: String, key: String, label_key: String, min_v: float, max_v: float, step: float, fmt: Callable, icon: StringName = &"") -> void:
	var box := HBoxContainer.new()
	box.custom_minimum_size = Vector2(380, 48)
	box.add_theme_constant_override(&"separation", 14)
	var sl := HSlider.new()
	sl.min_value = min_v
	sl.max_value = max_v
	sl.step = step
	sl.value = float(_sv_get(section, key))
	sl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	sl.custom_minimum_size = Vector2(250, 36)
	sl.focus_mode = Control.FOCUS_ALL
	box.add_child(sl)
	var val := UIStyle.label(String(fmt.call(sl.value)), &"semibold", 21, UIStyle.GOLD_LIGHT)
	val.custom_minimum_size = Vector2(96, 0)
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	box.add_child(val)
	sl.value_changed.connect(func(v: float) -> void:
		val.text = String(fmt.call(v))
		var def: Variant = _s().call("get_default", section, key) if _s() != null else 0.0
		_sv_set(section, key, int(round(v)) if typeof(def) == TYPE_INT else v)
		_after_change(section, key))
	_row(label_key, box, label_key + "_DESC", icon, section + "/" + key)
	_rows[section + "/" + key]["slider"] = sl
	_rows[section + "/" + key]["value_label"] = val
	_rows[section + "/" + key]["fmt"] = fmt


func _button_row(label_key: String, button_key: String, cb: Callable, icon: StringName = &"", danger := false) -> void:
	var b := Button.new()
	b.text = tr(button_key)
	b.custom_minimum_size = Vector2(380, 50)
	if danger:
		b.theme_type_variation = &"DangerButton"
	b.pressed.connect(cb)
	_row(label_key, b, label_key + "_DESC", icon)


static func _pct(v: float) -> String:
	return "%d%%" % int(round(v * 100.0))


static func _deg(v: float) -> String:
	return "%d°" % int(round(v))


static func _mult(v: float) -> String:
	return "×%.2f" % v


func _opts(values: Array, label_prefix: String, upper := true) -> Array:
	var out: Array = []
	for v: Variant in values:
		var lbl := tr(label_prefix + (str(v).to_upper() if upper else str(v)))
		out.append({"value": v, "label": lbl})
	return out


# --- tabs -------------------------------------------------------------------------------------

func _build_graphics() -> void:
	_header("SET_HDR_DISPLAY")
	_selector("graphics", "quality", "SET_QUALITY", _opts(["low", "medium", "high", "ultra", "custom"], "Q_"), &"graphics")
	_toggle("graphics", "fullscreen", "SET_FULLSCREEN", &"graphics")
	_toggle("graphics", "vsync", "SET_VSYNC", &"graphics")
	var fps: Array = []
	for f: int in [0, 30, 60, 90, 120, 144, 165, 240]:
		fps.append({"value": f, "label": tr("SET_FPS_UNLIMITED") if f == 0 else "%d FPS" % f})
	_selector("graphics", "max_fps", "SET_MAX_FPS", fps, &"time")
	_slider("graphics", "fov", "SET_FOV", 60.0, 100.0, 1.0, _deg, &"eye")
	_header("SET_HDR_RESOLUTION")
	_slider("graphics", "render_scale", "SET_RENDER_SCALE", 0.5, 1.0, 0.01, _pct, &"graphics")
	_selector("graphics", "upscaler", "SET_UPSCALER", _opts(["off", "fsr", "fsr2"], "UPS_"), &"graphics")
	_slider("graphics", "fsr_sharpness", "SET_FSR_SHARPNESS", 0.0, 2.0, 0.05, func(v: float) -> String: return "%.2f" % v, &"graphics")
	_selector("graphics", "anti_aliasing", "SET_AA", _opts(["off", "fxaa", "smaa", "taa"], "AA_"), &"graphics")
	_header("SET_HDR_LIGHTING")
	_toggle("graphics", "sdfgi", "SET_SDFGI", &"sun")
	_toggle("graphics", "ssao", "SET_SSAO", &"sun")
	_toggle("graphics", "ssil", "SET_SSIL", &"sun")
	_toggle("graphics", "ssr", "SET_SSR", &"rain")
	_toggle("graphics", "volumetric_fog", "SET_VOLFOG", &"rain")
	_selector("graphics", "shadow_quality", "SET_SHADOWS", _opts(["low", "medium", "high", "ultra"], "Q_"), &"moon")
	_header("SET_HDR_DETAIL")
	var fur: Array = []
	for n: int in [0, 8, 16, 24, 32, 48]:
		fur.append({"value": n, "label": tr("SET_FUR_OFF") if n == 0 else tr("SET_FUR_N").format({"n": n})})
	_selector("graphics", "fur_shells", "SET_FUR", fur, &"cat")
	var lods: Array = [{"value": 2.0, "label": tr("LOD_NEAR")}, {"value": 1.5, "label": tr("LOD_MEDIUM")},
		{"value": 1.0, "label": tr("LOD_FAR")}, {"value": 0.75, "label": tr("LOD_VERY_FAR")}]
	_selector("graphics", "lod_bias", "SET_LOD", lods, &"map")
	var aniso: Array = []
	for a: int in [2, 4, 8, 16]:
		aniso.append({"value": a, "label": "%d×" % a})
	_selector("graphics", "anisotropic", "SET_ANISO", aniso, &"graphics")
	_toggle("graphics", "motion_blur", "SET_MOTION_BLUR", &"graphics")
	_toggle("graphics", "film_grain", "SET_FILM_GRAIN", &"graphics")
	_button_row("SET_RESET_TAB", "BTN_RESET", _reset_tab.bind("graphics"), &"back", true)


func _build_audio() -> void:
	_header("SET_HDR_VOLUME")
	_slider("audio", "master", "SET_VOL_MASTER", 0.0, 1.0, 0.01, _pct, &"audio")
	_slider("audio", "music", "SET_VOL_MUSIC", 0.0, 1.0, 0.01, _pct, &"audio")
	_slider("audio", "sfx", "SET_VOL_SFX", 0.0, 1.0, 0.01, _pct, &"audio")
	_slider("audio", "ambience", "SET_VOL_AMBIENCE", 0.0, 1.0, 0.01, _pct, &"audio")
	_slider("audio", "ui", "SET_VOL_UI", 0.0, 1.0, 0.01, _pct, &"audio")
	_header("SET_HDR_SUBTITLES")
	_toggle("gameplay", "subtitles", "SET_SUBTITLES", &"journal")
	_selector("gameplay", "subtitle_size", "SET_SUBTITLE_SIZE", _opts(["small", "medium", "large"], "SIZE_"), &"journal")
	_button_row("SET_RESET_TAB", "BTN_RESET", _reset_tab.bind("audio"), &"back", true)


func _build_controls() -> void:
	_header("SET_HDR_CAMERA")
	_slider("controls", "mouse_sensitivity", "SET_MOUSE_SENS", 0.02, 1.0, 0.01, func(v: float) -> String: return "%.2f" % v, &"mouse_device")
	_slider("controls", "gamepad_sensitivity", "SET_PAD_SENS", 0.5, 8.0, 0.1, func(v: float) -> String: return "%.1f" % v, &"gamepad")
	_toggle("controls", "invert_y", "SET_INVERT_Y", &"mouse_device")
	_toggle("controls", "invert_x", "SET_INVERT_X", &"mouse_device")
	_toggle("controls", "vibration", "SET_VIBRATION", &"gamepad")
	_selector("camera", "default_mode", "SET_CAMERA_DEFAULT", [
		{"value": "third_person", "label": tr("CAM_TPP")}, {"value": "first_person", "label": tr("CAM_FPP")}], &"eye")
	_slider("camera", "head_bob", "SET_HEAD_BOB", 0.0, 1.0, 0.05, _pct, &"eye")
	_toggle("camera", "auto_center", "SET_AUTO_CENTER", &"compass")
	_header("SET_BINDINGS")
	var s := _s()
	var actions: PackedStringArray = PackedStringArray()
	if s != null and s.get_script() != null:
		actions = (s.get_script() as Script).get_script_constant_map().get("REBINDABLE_ACTIONS", PackedStringArray())
	for a in actions:
		if InputMap.has_action(a):
			_binding_row(a)
	_button_row("SET_RESET_BINDINGS", "BTN_RESET", func() -> void:
		var st := _s()
		if st != null:
			st.call("reset_bindings")
		_populate()
		_focus_first_row(), &"keyboard", true)


func _binding_row(action: String) -> void:
	var box := HBoxContainer.new()
	box.add_theme_constant_override(&"separation", 10)
	box.custom_minimum_size = Vector2(380, 48)
	for pad in [false, true]:
		var b := Button.new()
		b.custom_minimum_size = Vector2(185, 46)
		b.text = UIInputGlyph.action_text(StringName(action), pad)
		b.icon = UIStyle.glyph(&"gamepad" if pad else &"keyboard")
		b.add_theme_constant_override(&"icon_max_width", 22)
		b.add_theme_font_size_override(&"font_size", 20)
		b.clip_text = true
		var is_pad: bool = pad
		b.pressed.connect(func() -> void: _begin_capture(action, is_pad, b))
		box.add_child(b)
	_row("ACTION_" + action.to_upper(), box, "SET_REBIND_DESC", &"keyboard", "input/" + action)


func _build_gameplay() -> void:
	_header("SET_HDR_LANGUAGE")
	_selector("gameplay", "language", "SET_LANGUAGE", [
		{"value": "vi", "label": "Tiếng Việt"}, {"value": "en", "label": "English"}], &"language")
	_header("SET_HDR_INTERFACE")
	_toggle("gameplay", "hints", "SET_HINTS", &"info")
	_toggle("gameplay", "compass", "SET_COMPASS", &"compass")
	_slider("gameplay", "text_speed", "SET_TEXT_SPEED", 0.25, 3.0, 0.05, _mult, &"journal")
	_slider("gameplay", "ui_scale", "SET_UI_SCALE", 0.75, 1.3, 0.05, _pct, &"graphics")
	_slider("gameplay", "hud_opacity", "SET_HUD_OPACITY", 0.2, 1.0, 0.05, _pct, &"eye")
	_header("SET_HDR_RESET")
	_button_row("SET_RESET_ALL", "BTN_RESET_ALL", _confirm_reset_all, &"back", true)


# =============================================================================================
# Changes
# =============================================================================================

func _after_change(section: String, key: String) -> void:
	if section == "graphics":
		_refresh_graphics_values()
		if key == "quality":
			_show_help("SET_QUALITY", "SET_QUALITY_DESC", &"graphics")
	elif section == "gameplay" and key == "language":
		# Every label changes: rebuild the screen in the new language, keep the tab.
		var keep := _tab
		_relocalize.call_deferred(keep)


func _relocalize(keep_tab: int) -> void:
	for c in get_children():
		if c != _backdrop:
			remove_child(c)
			c.queue_free()
	_rows.clear()
	_tab = keep_tab
	build()
	(_tabs_bar.get_child(keep_tab) as Button).button_pressed = true
	_populate()
	UIStyle.wire_sounds(self)
	var r: Dictionary = _rows.get("gameplay/language", {})
	if not r.is_empty():
		(r["control"] as Control).grab_focus.call_deferred()


func _refresh_graphics_values() -> void:
	for path: String in _rows:
		if not path.begins_with("graphics/"):
			continue
		var key := path.substr(9)
		var r: Dictionary = _rows[path]
		var c: Control = r["control"]
		var v: Variant = _sv_get("graphics", key)
		if c is UISelector:
			(c as UISelector).set_value_silent(v)
		elif c is CheckButton:
			(c as CheckButton).set_pressed_no_signal(bool(v))
		elif r.has("slider"):
			var sl: HSlider = r["slider"]
			sl.set_value_no_signal(float(v))
			(r["value_label"] as Label).text = String((r["fmt"] as Callable).call(float(v)))


func _reset_tab(section: String) -> void:
	var s := _s()
	if s == null:
		return
	if section == "audio":
		s.call("reset_section", "audio")
	elif section == "graphics":
		s.call("reset_section", "graphics")
	_populate()
	_focus_first_row.call_deferred()


func _confirm_reset_all() -> void:
	var d := UIConfirmDialog.make("CONFIRM_RESET_TITLE", "CONFIRM_RESET_BODY", true)
	d.confirmed.connect(func() -> void:
		var s := _s()
		if s != null:
			s.call("reset_all")
		_relocalize.call_deferred(_tab))
	if host != null:
		host.call("push_screen", d)


# --- key rebinding ----------------------------------------------------------------------------

func _begin_capture(action: String, pad: bool, button: Button) -> void:
	_capture = {"action": action, "pad": pad, "button": button}
	button.text = "…"
	_capture_label.text = tr("SET_REBIND_PROMPT").format({"action": tr("ACTION_" + action.to_upper())})
	UIStyle.sfx(&"ui_confirm")


func _end_capture(ev: InputEvent) -> void:
	if _capture.is_empty():
		return
	var action := String(_capture["action"])
	var pad := bool(_capture["pad"])
	var b: Button = _capture["button"]
	_capture = {}
	_capture_label.text = ""
	if ev != null:
		var s := _s()
		if s != null:
			var other := String(s.call("find_action_for_event", ev, action))
			s.call("rebind_action", action, ev)
			if other != "":
				_capture_label.text = tr("SET_REBIND_CONFLICT").format({"action": tr("ACTION_" + other.to_upper())})
	if is_instance_valid(b):
		b.text = UIInputGlyph.action_text(StringName(action), pad)
		b.grab_focus()


func _input(event: InputEvent) -> void:
	if _capture.is_empty() or not event.is_pressed() or event.is_echo():
		return
	var pad := bool(_capture["pad"])
	if event is InputEventKey and (event as InputEventKey).physical_keycode == KEY_ESCAPE:
		get_viewport().set_input_as_handled()
		_end_capture(null)
		return
	if not pad and (event is InputEventKey or event is InputEventMouseButton):
		if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			# A plain left click on the button itself would immediately rebind to LMB; only accept
			# it when the pointer is not over the capture button.
			var b: Button = _capture["button"]
			if b.get_global_rect().has_point((event as InputEventMouseButton).global_position):
				return
		get_viewport().set_input_as_handled()
		_end_capture(event)
	elif pad and (event is InputEventJoypadButton or (event is InputEventJoypadMotion and absf((event as InputEventJoypadMotion).axis_value) > 0.6)):
		get_viewport().set_input_as_handled()
		if event is InputEventJoypadButton and (event as InputEventJoypadButton).button_index == JOY_BUTTON_B:
			_end_capture(null)
		else:
			_end_capture(event)
