extends SceneTree
## Builds assets/ui/theme.tres (the single UI theme of Mèo Cam) from code so it is reproducible.
## Run: tools/godot_lock.sh godot --headless --path . --script res://scripts/ui/build/build_theme.gd </dev/null
##
## Type variations (set Control.theme_type_variation):
##   Labels:  TitleLabel, HeadingLabel, SubheadingLabel, CaptionLabel, MutedLabel, ProseLabel,
##            InkLabel, InkHeadingLabel, InkMutedLabel, HudLabel, HudCaption
##   Buttons: MenuItemButton (big serif, red ink-brush focus), TabButton, ChipButton (dialogue choices),
##            FlatButton (icon/text without frame), DangerButton, PrimaryButton
##   Panels:  LacquerPanel, PaperPanel, SlotPanel, GlassPanel

const OUT := "res://assets/ui/theme.tres"
const TEX := "res://assets/ui/textures/"
const F := "res://assets/fonts/"

const INK := Color("#16110d")
const INK_SOFT := Color("#241b15")
const GOLD := Color("#d9a441")
const GOLD_LIGHT := Color("#f2cf7e")
const GOLD_DIM := Color("#8a6a32")
const TEXT := Color("#f4e9d2")
const TEXT_DIM := Color("#c9b996")
const TEXT_MUTED := Color("#8f8068")
const TEXT_INK := Color("#2b211a")
const TEXT_INK_DIM := Color("#6b5944")
const LANTERN := Color("#e2683a")
const RED := Color("#a8331d")

var th := Theme.new()


func _init() -> void:
	_run.call_deferred()


func _font(n: String) -> Font:
	return load(F + n + ".ttf") as Font


func _tex(n: String) -> Texture2D:
	return load(TEX + n + ".png") as Texture2D


func _flat(bg: Color, radius: int = 10, border: Color = Color(0, 0, 0, 0), bw: int = 0, pad := Vector4(16, 10, 16, 10)) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.corner_detail = 8
	sb.anti_aliasing = true
	if bw > 0:
		sb.border_color = border
		sb.set_border_width_all(bw)
	sb.content_margin_left = pad.x
	sb.content_margin_top = pad.y
	sb.content_margin_right = pad.z
	sb.content_margin_bottom = pad.w
	return sb


func _empty(pad := Vector4(16, 8, 16, 8)) -> StyleBoxEmpty:
	var sb := StyleBoxEmpty.new()
	sb.content_margin_left = pad.x
	sb.content_margin_top = pad.y
	sb.content_margin_right = pad.z
	sb.content_margin_bottom = pad.w
	return sb


func _texbox(t: String, margins: Vector4, content: Vector4, modulate := Color.WHITE) -> StyleBoxTexture:
	var sb := StyleBoxTexture.new()
	sb.texture = _tex(t)
	sb.texture_margin_left = margins.x
	sb.texture_margin_top = margins.y
	sb.texture_margin_right = margins.z
	sb.texture_margin_bottom = margins.w
	sb.content_margin_left = content.x
	sb.content_margin_top = content.y
	sb.content_margin_right = content.z
	sb.content_margin_bottom = content.w
	sb.modulate_color = modulate
	return sb


func _label_var(name: String, font: String, size: int, color: Color, shadow := false, line_spacing := 0) -> void:
	th.set_type_variation(name, "Label")
	th.set_font("font", name, _font(font))
	th.set_font_size("font_size", name, size)
	th.set_color("font_color", name, color)
	if shadow:
		th.set_color("font_shadow_color", name, Color(0, 0, 0, 0.75))
		th.set_constant("shadow_offset_x", name, 0)
		th.set_constant("shadow_offset_y", name, 2)
		th.set_constant("shadow_outline_size", name, 6)
	if line_spacing != 0:
		th.set_constant("line_spacing", name, line_spacing)


func _button_colors(t: String, normal: Color, hover: Color, pressed: Color, disabled: Color) -> void:
	th.set_color("font_color", t, normal)
	th.set_color("font_hover_color", t, hover)
	th.set_color("font_focus_color", t, hover)
	th.set_color("font_pressed_color", t, pressed)
	th.set_color("font_hover_pressed_color", t, pressed)
	th.set_color("font_disabled_color", t, disabled)
	th.set_color("icon_normal_color", t, normal)
	th.set_color("icon_hover_color", t, hover)
	th.set_color("icon_focus_color", t, hover)
	th.set_color("icon_pressed_color", t, pressed)
	th.set_color("icon_hover_pressed_color", t, pressed)
	th.set_color("icon_disabled_color", t, disabled)


func _run() -> void:
	th.default_font = _font("BeVietnamPro-400")
	th.default_font_size = 24

	# --- Label ------------------------------------------------------------------------------
	th.set_color("font_color", "Label", TEXT)
	th.set_constant("line_spacing", "Label", 4)
	_label_var("TitleLabel", "PlayfairDisplay-700", 84, TEXT, true)
	_label_var("HeadingLabel", "PlayfairDisplay-600", 44, TEXT)
	_label_var("SubheadingLabel", "PlayfairDisplay-400i", 28, GOLD_LIGHT)
	_label_var("CaptionLabel", "BeVietnamPro-600", 17, GOLD)
	_label_var("MutedLabel", "BeVietnamPro-400", 21, TEXT_DIM)
	_label_var("ProseLabel", "Lora-400", 26, TEXT, false, 6)
	_label_var("InkLabel", "BeVietnamPro-400", 23, TEXT_INK)
	_label_var("InkHeadingLabel", "PlayfairDisplay-600", 38, TEXT_INK)
	_label_var("InkMutedLabel", "BeVietnamPro-400", 20, TEXT_INK_DIM)
	_label_var("HudLabel", "BeVietnamPro-500", 24, TEXT, true)
	_label_var("HudCaption", "BeVietnamPro-600", 16, GOLD_LIGHT, true)

	# --- RichTextLabel --------------------------------------------------------------------------
	th.set_color("default_color", "RichTextLabel", TEXT)
	th.set_font("normal_font", "RichTextLabel", _font("BeVietnamPro-400"))
	th.set_font("bold_font", "RichTextLabel", _font("BeVietnamPro-600"))
	th.set_font("italics_font", "RichTextLabel", _font("BeVietnamPro-400i"))
	th.set_font_size("normal_font_size", "RichTextLabel", 24)
	th.set_font_size("bold_font_size", "RichTextLabel", 24)
	th.set_font_size("italics_font_size", "RichTextLabel", 24)
	th.set_constant("line_separation", "RichTextLabel", 4)
	th.set_stylebox("normal", "RichTextLabel", _empty(Vector4.ZERO))
	th.set_stylebox("focus", "RichTextLabel", _empty(Vector4.ZERO))
	th.set_type_variation("ProseText", "RichTextLabel")
	th.set_font("normal_font", "ProseText", _font("Lora-400"))
	th.set_font("bold_font", "ProseText", _font("Lora-600"))
	th.set_font("italics_font", "ProseText", _font("Lora-400i"))
	th.set_font_size("normal_font_size", "ProseText", 27)
	th.set_font_size("bold_font_size", "ProseText", 27)
	th.set_font_size("italics_font_size", "ProseText", 27)
	th.set_constant("line_separation", "ProseText", 8)
	th.set_type_variation("InkProseText", "ProseText")
	th.set_color("default_color", "InkProseText", TEXT_INK)

	# --- Button (secondary: hairline gold pill) ---------------------------------------------
	var b_normal := _flat(Color(INK_SOFT, 0.78), 9, Color(GOLD_DIM, 0.9), 2, Vector4(22, 10, 22, 10))
	var b_hover := _flat(Color("#3a1d14", 0.95), 9, GOLD, 2, Vector4(22, 10, 22, 10))
	var b_pressed := _flat(Color("#5a1e16", 1.0), 9, GOLD_LIGHT, 2, Vector4(22, 11, 22, 9))
	var b_disabled := _flat(Color(INK_SOFT, 0.45), 9, Color(GOLD_DIM, 0.35), 2, Vector4(22, 10, 22, 10))
	var b_focus := _flat(Color(0, 0, 0, 0), 11, GOLD_LIGHT, 2, Vector4(22, 10, 22, 10))
	b_focus.draw_center = false
	b_focus.expand_margin_left = 3
	b_focus.expand_margin_right = 3
	b_focus.expand_margin_top = 3
	b_focus.expand_margin_bottom = 3
	th.set_stylebox("normal", "Button", b_normal)
	th.set_stylebox("hover", "Button", b_hover)
	th.set_stylebox("pressed", "Button", b_pressed)
	th.set_stylebox("hover_pressed", "Button", b_pressed)
	th.set_stylebox("disabled", "Button", b_disabled)
	th.set_stylebox("focus", "Button", b_focus)
	th.set_font("font", "Button", _font("BeVietnamPro-500"))
	th.set_font_size("font_size", "Button", 23)
	th.set_constant("h_separation", "Button", 12)
	th.set_constant("icon_max_width", "Button", 32)
	_button_colors("Button", TEXT, GOLD_LIGHT, Color.WHITE, TEXT_MUTED)

	# PrimaryButton: lacquer red
	th.set_type_variation("PrimaryButton", "Button")
	th.set_stylebox("normal", "PrimaryButton", _flat(Color("#8e2a1a", 0.95), 9, Color(GOLD, 0.9), 2, Vector4(26, 11, 26, 11)))
	th.set_stylebox("hover", "PrimaryButton", _flat(Color("#b23a22", 1.0), 9, GOLD_LIGHT, 2, Vector4(26, 11, 26, 11)))
	th.set_stylebox("pressed", "PrimaryButton", _flat(Color("#6e1e12", 1.0), 9, GOLD_LIGHT, 2, Vector4(26, 12, 26, 10)))
	th.set_stylebox("disabled", "PrimaryButton", _flat(Color("#4a2018", 0.5), 9, Color(GOLD_DIM, 0.4), 2, Vector4(26, 11, 26, 11)))
	th.set_font("font", "PrimaryButton", _font("BeVietnamPro-600"))
	_button_colors("PrimaryButton", TEXT, Color.WHITE, Color.WHITE, TEXT_MUTED)

	th.set_type_variation("DangerButton", "Button")
	th.set_stylebox("hover", "DangerButton", _flat(Color("#7a1a12", 1.0), 9, Color("#ff8a6a"), 2, Vector4(22, 10, 22, 10)))
	_button_colors("DangerButton", Color("#f0a090"), Color("#ffd0c0"), Color.WHITE, TEXT_MUTED)

	# FlatButton: no frame, text/icon only
	th.set_type_variation("FlatButton", "Button")
	for st in ["normal", "hover", "pressed", "hover_pressed", "disabled"]:
		th.set_stylebox(st, "FlatButton", _empty(Vector4(10, 6, 10, 6)))
	var flat_focus := _flat(Color(1, 1, 1, 0.06), 8, Color(GOLD_LIGHT, 0.8), 2, Vector4(10, 6, 10, 6))
	th.set_stylebox("focus", "FlatButton", flat_focus)
	_button_colors("FlatButton", TEXT_DIM, GOLD_LIGHT, Color.WHITE, TEXT_MUTED)

	# MenuItemButton (main/pause menu items): big serif text, red brush stroke behind on focus/hover
	th.set_type_variation("MenuItemButton", "Button")
	var brush := _texbox("brush_highlight_red", Vector4(90, 0, 90, 0), Vector4(40, 6, 60, 10), Color(1, 1, 1, 0.92))
	brush.expand_margin_left = 28
	brush.expand_margin_right = 10
	brush.axis_stretch_horizontal = StyleBoxTexture.AXIS_STRETCH_MODE_STRETCH
	th.set_stylebox("normal", "MenuItemButton", _empty(Vector4(40, 6, 60, 10)))
	th.set_stylebox("hover", "MenuItemButton", brush)
	th.set_stylebox("pressed", "MenuItemButton", brush)
	th.set_stylebox("hover_pressed", "MenuItemButton", brush)
	th.set_stylebox("disabled", "MenuItemButton", _empty(Vector4(40, 6, 60, 10)))
	th.set_stylebox("focus", "MenuItemButton", brush)
	th.set_font("font", "MenuItemButton", _font("PlayfairDisplay-600"))
	th.set_font_size("font_size", "MenuItemButton", 40)
	th.set_constant("outline_size", "MenuItemButton", 0)
	_button_colors("MenuItemButton", TEXT_DIM, Color("#fff3dc"), Color.WHITE, Color(TEXT_MUTED, 0.55))

	# TabButton (top tab strips in menus)
	th.set_type_variation("TabButton", "Button")
	var tab_n := _empty(Vector4(22, 10, 22, 14))
	var tab_sel := _flat(Color(0, 0, 0, 0), 0, GOLD, 0, Vector4(22, 10, 22, 14))
	tab_sel.draw_center = false
	tab_sel.border_width_bottom = 3
	tab_sel.border_color = LANTERN
	var tab_hover := _flat(Color(1, 1, 1, 0.04), 6, GOLD, 0, Vector4(22, 10, 22, 14))
	th.set_stylebox("normal", "TabButton", tab_n)
	th.set_stylebox("hover", "TabButton", tab_hover)
	th.set_stylebox("pressed", "TabButton", tab_sel)
	th.set_stylebox("hover_pressed", "TabButton", tab_sel)
	th.set_stylebox("disabled", "TabButton", tab_n)
	var tab_focus := _flat(Color(0, 0, 0, 0), 6, GOLD_LIGHT, 2, Vector4(22, 10, 22, 14))
	tab_focus.draw_center = false
	th.set_stylebox("focus", "TabButton", tab_focus)
	th.set_font("font", "TabButton", _font("BeVietnamPro-600"))
	th.set_font_size("font_size", "TabButton", 22)
	_button_colors("TabButton", TEXT_MUTED, GOLD_LIGHT, TEXT, Color(TEXT_MUTED, 0.5))

	# ChipButton (dialogue choices / list rows): dark row, red brush on focus
	th.set_type_variation("ChipButton", "Button")
	var chip_n := _flat(Color(1, 1, 1, 0.035), 10, Color(GOLD_DIM, 0.45), 1, Vector4(18, 12, 22, 12))
	var chip_h := _flat(Color("#7a2416", 0.92), 10, GOLD, 2, Vector4(18, 12, 22, 12))
	var chip_d := _flat(Color(0, 0, 0, 0.2), 10, Color(GOLD_DIM, 0.25), 1, Vector4(18, 12, 22, 12))
	th.set_stylebox("normal", "ChipButton", chip_n)
	th.set_stylebox("hover", "ChipButton", chip_h)
	th.set_stylebox("pressed", "ChipButton", chip_h)
	th.set_stylebox("hover_pressed", "ChipButton", chip_h)
	th.set_stylebox("focus", "ChipButton", chip_h)
	th.set_stylebox("disabled", "ChipButton", chip_d)
	th.set_font("font", "ChipButton", _font("BeVietnamPro-500"))
	th.set_font_size("font_size", "ChipButton", 23)
	th.set_constant("h_separation", "ChipButton", 14)
	th.set_constant("icon_max_width", "ChipButton", 34)
	_button_colors("ChipButton", TEXT, Color.WHITE, Color.WHITE, Color(TEXT_MUTED, 0.85))

	# SlotButton (inventory slots / skill nodes)
	th.set_type_variation("SlotButton", "Button")
	var slot := _texbox("slot_frame", Vector4(20, 20, 20, 20), Vector4(10, 10, 10, 10))
	var slot_h := _texbox("slot_frame", Vector4(20, 20, 20, 20), Vector4(10, 10, 10, 10), Color(1.08, 1.0, 0.86))
	var slot_focus := _flat(Color(0, 0, 0, 0), 12, LANTERN, 3, Vector4(10, 10, 10, 10))
	slot_focus.draw_center = false
	slot_focus.expand_margin_left = 4
	slot_focus.expand_margin_right = 4
	slot_focus.expand_margin_top = 4
	slot_focus.expand_margin_bottom = 4
	th.set_stylebox("normal", "SlotButton", slot)
	th.set_stylebox("hover", "SlotButton", slot_h)
	th.set_stylebox("pressed", "SlotButton", slot_h)
	th.set_stylebox("hover_pressed", "SlotButton", slot_h)
	th.set_stylebox("disabled", "SlotButton", _texbox("slot_frame", Vector4(20, 20, 20, 20), Vector4(10, 10, 10, 10), Color(1, 1, 1, 0.4)))
	th.set_stylebox("focus", "SlotButton", slot_focus)
	_button_colors("SlotButton", TEXT_INK, TEXT_INK, TEXT_INK, TEXT_INK_DIM)

	# --- Check / toggle -----------------------------------------------------------------------
	for t in ["CheckButton", "CheckBox"]:
		th.set_stylebox("normal", t, _empty(Vector4(8, 6, 8, 6)))
		th.set_stylebox("hover", t, _empty(Vector4(8, 6, 8, 6)))
		th.set_stylebox("pressed", t, _empty(Vector4(8, 6, 8, 6)))
		th.set_stylebox("hover_pressed", t, _empty(Vector4(8, 6, 8, 6)))
		th.set_stylebox("disabled", t, _empty(Vector4(8, 6, 8, 6)))
		var cf := _flat(Color(1, 1, 1, 0.05), 8, Color(GOLD_LIGHT, 0.9), 2, Vector4(8, 6, 8, 6))
		th.set_stylebox("focus", t, cf)
		_button_colors(t, TEXT, GOLD_LIGHT, TEXT, TEXT_MUTED)
	th.set_icon("checked", "CheckButton", _tex("toggle_on"))
	th.set_icon("unchecked", "CheckButton", _tex("toggle_off"))
	th.set_icon("checked_disabled", "CheckButton", _tex("toggle_on"))
	th.set_icon("unchecked_disabled", "CheckButton", _tex("toggle_off"))
	th.set_icon("checked", "CheckBox", _tex("check_on"))
	th.set_icon("unchecked", "CheckBox", _tex("check_off"))
	th.set_icon("radio_checked", "CheckBox", _tex("radio_on"))
	th.set_icon("radio_unchecked", "CheckBox", _tex("radio_off"))

	# --- Sliders ----------------------------------------------------------------------------------
	var track := _flat(Color("#0e0a08", 0.85), 4, Color(GOLD_DIM, 0.7), 1, Vector4(0, 4, 0, 4))
	var fill := _flat(Color("#c8452a", 1.0), 4, Color(0, 0, 0, 0), 0, Vector4(0, 4, 0, 4))
	var fill_h := _flat(Color("#e2683a", 1.0), 4, Color(0, 0, 0, 0), 0, Vector4(0, 4, 0, 4))
	th.set_stylebox("slider", "HSlider", track)
	th.set_stylebox("grabber_area", "HSlider", fill)
	th.set_stylebox("grabber_area_highlight", "HSlider", fill_h)
	th.set_icon("grabber", "HSlider", _tex("grabber"))
	th.set_icon("grabber_highlight", "HSlider", _tex("grabber_hl"))
	th.set_icon("grabber_disabled", "HSlider", _tex("grabber"))
	th.set_constant("center_grabber", "HSlider", 1)

	# --- OptionButton + popup -------------------------------------------------------------------
	th.set_icon("arrow", "OptionButton", load("res://assets/ui/icons/glyphs/chevron_down.png") as Texture2D)
	th.set_constant("arrow_margin", "OptionButton", 14)
	th.set_constant("modulate_arrow", "OptionButton", 1)
	var pop := _texbox("panel_lacquer_small", Vector4(28, 28, 28, 28), Vector4(10, 12, 10, 12))
	th.set_stylebox("panel", "PopupMenu", pop)
	th.set_stylebox("hover", "PopupMenu", _flat(Color("#7a2416", 0.95), 6, Color(0, 0, 0, 0), 0, Vector4(8, 4, 8, 4)))
	th.set_font("font", "PopupMenu", _font("BeVietnamPro-500"))
	th.set_font_size("font_size", "PopupMenu", 22)
	th.set_color("font_color", "PopupMenu", TEXT)
	th.set_color("font_hover_color", "PopupMenu", Color.WHITE)
	th.set_constant("v_separation", "PopupMenu", 10)
	th.set_constant("item_start_padding", "PopupMenu", 14)
	th.set_constant("item_end_padding", "PopupMenu", 14)

	# --- Panels ---------------------------------------------------------------------------------
	var lacquer := _texbox("panel_lacquer", Vector4(56, 56, 56, 56), Vector4(44, 36, 44, 36))
	th.set_stylebox("panel", "PanelContainer", lacquer)
	th.set_stylebox("panel", "Panel", lacquer)
	th.set_type_variation("LacquerPanel", "PanelContainer")
	th.set_stylebox("panel", "LacquerPanel", lacquer)
	th.set_type_variation("PaperPanel", "PanelContainer")
	th.set_stylebox("panel", "PaperPanel", _texbox("panel_paper", Vector4(48, 48, 48, 48), Vector4(40, 32, 40, 32)))
	th.set_type_variation("SlotPanel", "PanelContainer")
	th.set_stylebox("panel", "SlotPanel", _texbox("slot_frame", Vector4(20, 20, 20, 20), Vector4(12, 12, 12, 12)))
	th.set_type_variation("GlassPanel", "PanelContainer")
	th.set_stylebox("panel", "GlassPanel", _flat(Color(0.06, 0.045, 0.035, 0.72), 14, Color(GOLD_DIM, 0.55), 1, Vector4(20, 14, 20, 14)))
	th.set_type_variation("SmallLacquerPanel", "PanelContainer")
	th.set_stylebox("panel", "SmallLacquerPanel", _texbox("panel_lacquer_small", Vector4(28, 28, 28, 28), Vector4(26, 20, 26, 20)))

	# --- Scrollbars -------------------------------------------------------------------------------
	for t in ["VScrollBar", "HScrollBar"]:
		th.set_stylebox("scroll", t, _flat(Color(0, 0, 0, 0.25), 4, Color(0, 0, 0, 0), 0, Vector4(3, 3, 3, 3)))
		th.set_stylebox("scroll_focus", t, _flat(Color(0, 0, 0, 0.25), 4, Color(0, 0, 0, 0), 0, Vector4(3, 3, 3, 3)))
		th.set_stylebox("grabber", t, _flat(Color(GOLD_DIM, 0.85), 4, Color(0, 0, 0, 0), 0, Vector4(3, 3, 3, 3)))
		th.set_stylebox("grabber_highlight", t, _flat(GOLD, 4, Color(0, 0, 0, 0), 0, Vector4(3, 3, 3, 3)))
		th.set_stylebox("grabber_pressed", t, _flat(GOLD_LIGHT, 4, Color(0, 0, 0, 0), 0, Vector4(3, 3, 3, 3)))
		var empty_icon := ImageTexture.create_from_image(Image.create(1, 1, false, Image.FORMAT_RGBA8))
		for ic in ["increment", "increment_highlight", "increment_pressed", "decrement", "decrement_highlight", "decrement_pressed"]:
			th.set_icon(ic, t, empty_icon)

	# --- ProgressBar ----------------------------------------------------------------------------
	th.set_stylebox("background", "ProgressBar", _flat(Color(0, 0, 0, 0.45), 3, Color(GOLD_DIM, 0.5), 1, Vector4(0, 0, 0, 0)))
	th.set_stylebox("fill", "ProgressBar", _flat(GOLD, 3, Color(0, 0, 0, 0), 0, Vector4(0, 0, 0, 0)))
	th.set_color("font_color", "ProgressBar", TEXT)

	# --- LineEdit ---------------------------------------------------------------------------------
	th.set_stylebox("normal", "LineEdit", _flat(Color(0, 0, 0, 0.4), 8, Color(GOLD_DIM, 0.8), 1, Vector4(14, 8, 14, 8)))
	th.set_stylebox("focus", "LineEdit", _flat(Color(0, 0, 0, 0), 8, GOLD_LIGHT, 2, Vector4(14, 8, 14, 8)))
	th.set_color("font_color", "LineEdit", TEXT)
	th.set_color("caret_color", "LineEdit", GOLD_LIGHT)

	# --- Tooltip ----------------------------------------------------------------------------------
	th.set_stylebox("panel", "TooltipPanel", _flat(Color(0.07, 0.05, 0.04, 0.96), 8, Color(GOLD_DIM, 0.8), 1, Vector4(14, 10, 14, 10)))
	th.set_color("font_color", "TooltipLabel", TEXT)
	th.set_font_size("font_size", "TooltipLabel", 20)

	# --- Separators -------------------------------------------------------------------------------
	var sep := StyleBoxLine.new()
	sep.color = Color(GOLD_DIM, 0.6)
	sep.thickness = 1
	th.set_stylebox("separator", "HSeparator", sep)
	th.set_constant("separation", "HSeparator", 18)
	var vsep := StyleBoxLine.new()
	vsep.color = Color(GOLD_DIM, 0.6)
	vsep.thickness = 1
	vsep.vertical = true
	th.set_stylebox("separator", "VSeparator", vsep)

	# --- Containers -------------------------------------------------------------------------------
	th.set_constant("separation", "VBoxContainer", 10)
	th.set_constant("separation", "HBoxContainer", 12)

	var err := ResourceSaver.save(th, OUT)
	print("THEME saved ", OUT, " ", error_string(err))
	quit(0 if err == OK else 1)
