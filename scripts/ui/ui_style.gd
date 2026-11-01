class_name UIStyle
extends RefCounted
## Shared look & helpers for every UI screen of Mèo Cam (owner: ui).
## Palette "lantern, paper & ochre": lacquer-black panels, rice-paper cards, gold hairlines,
## lantern red accents. Fonts: Playfair Display (titles), Be Vietnam Pro (UI), Lora (prose).

const THEME_PATH := "res://assets/ui/theme.tres"
const TEX := "res://assets/ui/textures/"
const ICONS := "res://assets/ui/icons/"

# --- palette ----------------------------------------------------------------------------------
const INK := Color("#16110d")
const INK_SOFT := Color("#241b15")
const LACQUER := Color("#5a1e16")
const LANTERN := Color("#e2683a")
const LANTERN_GLOW := Color("#ffb46a")
const SEAL_RED := Color("#b8321f")
const GOLD := Color("#d9a441")
const GOLD_LIGHT := Color("#f2cf7e")
const GOLD_DIM := Color("#8a6a32")
const PAPER := Color("#f1e4c6")
const PAPER_DARK := Color("#d8c39a")
const TEXT := Color("#f4e9d2")
const TEXT_DIM := Color("#c9b996")
const TEXT_MUTED := Color("#8f8068")
const TEXT_INK := Color("#2b211a")
const TEXT_INK_DIM := Color("#6b5944")
const TEAL := Color("#4f9a90")
const JADE := Color("#8cc084")
const DANGER := Color("#e0604a")

const VITAL_COLORS := {
	&"health": Color("#e9604f"),
	&"hunger": Color("#e3b448"),
	&"energy": Color("#79c3cc"),
	&"warmth": Color("#f2883c"),
}
const VITAL_ICONS := {&"health": &"health", &"hunger": &"hunger", &"energy": &"energy", &"warmth": &"warmth"}
const STATS: Array[StringName] = [&"health", &"hunger", &"energy", &"warmth"]

# --- fonts ------------------------------------------------------------------------------------
const FONT_FILES := {
	&"title": "res://assets/fonts/PlayfairDisplay-700.ttf",
	&"heading": "res://assets/fonts/PlayfairDisplay-600.ttf",
	&"heading_regular": "res://assets/fonts/PlayfairDisplay-400.ttf",
	&"heading_italic": "res://assets/fonts/PlayfairDisplay-400i.ttf",
	&"light": "res://assets/fonts/BeVietnamPro-300.ttf",
	&"body": "res://assets/fonts/BeVietnamPro-400.ttf",
	&"body_italic": "res://assets/fonts/BeVietnamPro-400i.ttf",
	&"medium": "res://assets/fonts/BeVietnamPro-500.ttf",
	&"semibold": "res://assets/fonts/BeVietnamPro-600.ttf",
	&"bold": "res://assets/fonts/BeVietnamPro-700.ttf",
	&"prose": "res://assets/fonts/Lora-400.ttf",
	&"prose_italic": "res://assets/fonts/Lora-400i.ttf",
	&"prose_bold": "res://assets/fonts/Lora-600.ttf",
}

static var _font_cache: Dictionary = {}
static var _tex_cache: Dictionary = {}
static var _theme: Theme = null


static func font(kind: StringName) -> Font:
	if _font_cache.has(kind):
		return _font_cache[kind]
	var path: String = FONT_FILES.get(kind, FONT_FILES[&"body"])
	var f: Font = load(path) as Font if ResourceLoader.exists(path) else ThemeDB.fallback_font
	_font_cache[kind] = f
	return f


static func theme() -> Theme:
	if _theme == null and ResourceLoader.exists(THEME_PATH):
		_theme = load(THEME_PATH) as Theme
	return _theme


## Cached texture loader; returns null when the file does not exist (never errors).
static func tex(path: String) -> Texture2D:
	if _tex_cache.has(path):
		return _tex_cache[path]
	var t: Texture2D = null
	if path != "" and ResourceLoader.exists(path):
		t = load(path) as Texture2D
	_tex_cache[path] = t
	return t


static func ui_tex(name: String) -> Texture2D:
	return tex(TEX + name + ".png")


## White glyph icon (tint with modulate / self_modulate). Groups: glyphs, actions, skills.
static func glyph(name: StringName, group: String = "glyphs") -> Texture2D:
	var t := tex(ICONS + group + "/" + String(name) + ".png")
	if t == null and group != "glyphs":
		t = tex(ICONS + "glyphs/" + String(name) + ".png")
	return t


## Item illustration: items.json "icon" path, else assets/ui/icons/items/<id>.png, else memory
## photo for memories, else a generic glyph.
static func item_icon(item_id: StringName) -> Texture2D:
	var gs: Node = _autoload(&"GameState")
	var path := ""
	if gs != null and gs.has_method("get_item_def"):
		var d: Dictionary = gs.call("get_item_def", item_id)
		path = String(d.get("icon", ""))
		if String(d.get("category", "")) == "memory" and not ResourceLoader.exists(path):
			path = ICONS + "items/memory_photo.png"
	var t := tex(path)
	if t == null:
		t = tex(ICONS + "items/" + String(item_id) + ".png")
	if t == null and String(item_id).begins_with("memory"):
		t = tex(ICONS + "items/memory_photo.png")
	if t == null:
		t = glyph(&"item")
	return t


static func skill_icon(skill_id: StringName) -> Texture2D:
	var t := tex(ICONS + "skills/" + String(skill_id) + ".png")
	return t if t != null else glyph(&"skill")


# --- autoload access (null-safe, so screens work in isolation and in tests) ------------------

static func _autoload(n: StringName) -> Node:
	var ml := Engine.get_main_loop() as SceneTree
	if ml == null or ml.root == null:
		return null
	return ml.root.get_node_or_null(NodePath(String(n)))


static func sfx(name: StringName) -> void:
	var am := _autoload(&"AudioManager")
	if am != null and am.has_method("play_ui"):
		am.call("play_ui", name)


static func settings_value(section: String, key: String, default: Variant = null) -> Variant:
	var s := _autoload(&"Settings")
	if s == null:
		return default
	return s.call("get_value", section, key, default)


static func using_gamepad() -> bool:
	var s := _autoload(&"Settings")
	return s != null and bool(s.call("is_using_gamepad"))


# --- small builders ---------------------------------------------------------------------------

static func label(text: String, kind: StringName = &"body", size: int = 24, color: Color = TEXT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override(&"font", font(kind))
	l.add_theme_font_size_override(&"font_size", size)
	l.add_theme_color_override(&"font_color", color)
	return l


static func rich(text: String = "", size: int = 24, color: Color = TEXT, kind: StringName = &"body") -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.fit_content = true
	r.scroll_active = false
	r.text = text
	r.add_theme_font_override(&"normal_font", font(kind))
	r.add_theme_font_override(&"bold_font", font(&"semibold" if kind == &"body" else &"prose_bold"))
	r.add_theme_font_override(&"italics_font", font(&"body_italic" if kind == &"body" else &"prose_italic"))
	r.add_theme_font_size_override(&"normal_font_size", size)
	r.add_theme_font_size_override(&"bold_font_size", size)
	r.add_theme_font_size_override(&"italics_font_size", size)
	r.add_theme_color_override(&"default_color", color)
	return r


static func icon_rect(t: Texture2D, size: float, tint: Color = Color.WHITE) -> TextureRect:
	var r := TextureRect.new()
	r.texture = t
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	r.custom_minimum_size = Vector2(size, size)
	r.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	r.modulate = tint
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


static func lacquer_box(alpha: float = 0.92, small: bool = false) -> StyleBoxTexture:
	var sb := StyleBoxTexture.new()
	sb.texture = ui_tex("panel_lacquer_small" if small else "panel_lacquer")
	var m := 28.0 if small else 56.0
	sb.texture_margin_left = m
	sb.texture_margin_right = m
	sb.texture_margin_top = m
	sb.texture_margin_bottom = m
	sb.content_margin_left = 30.0 if small else 44.0
	sb.content_margin_right = 30.0 if small else 44.0
	sb.content_margin_top = 22.0 if small else 36.0
	sb.content_margin_bottom = 22.0 if small else 36.0
	sb.modulate_color = Color(1, 1, 1, alpha)
	return sb


static func paper_box(deckle: bool = true) -> StyleBoxTexture:
	var sb := StyleBoxTexture.new()
	sb.texture = ui_tex("panel_paper" if deckle else "panel_paper_plain")
	sb.texture_margin_left = 48.0
	sb.texture_margin_right = 48.0
	sb.texture_margin_top = 48.0
	sb.texture_margin_bottom = 48.0
	sb.content_margin_left = 40.0
	sb.content_margin_right = 40.0
	sb.content_margin_top = 32.0
	sb.content_margin_bottom = 32.0
	return sb


static func flat_box(bg: Color, radius: int = 10, border: Color = Color(0, 0, 0, 0), border_w: int = 0, pad: float = 12.0) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(radius)
	sb.corner_detail = 8
	sb.anti_aliasing = true
	if border_w > 0:
		sb.border_color = border
		sb.set_border_width_all(border_w)
	sb.content_margin_left = pad
	sb.content_margin_right = pad
	sb.content_margin_top = pad * 0.6
	sb.content_margin_bottom = pad * 0.6
	return sb


static func panel(style: StyleBox) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override(&"panel", style)
	return p


static func divider(width: float = 420.0, tint: Color = GOLD) -> TextureRect:
	var r := TextureRect.new()
	r.texture = ui_tex("divider")
	r.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	r.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	r.custom_minimum_size = Vector2(width, 22)
	r.modulate = tint
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return r


## Hover/focus/press sounds + "mouse hover grabs focus" for every BaseButton/Slider under root,
## so mouse and gamepad share one highlight. Safe to call more than once.
static func wire_sounds(root: Node) -> void:
	for n in root.find_children("*", "Control", true, false):
		_wire_one(n as Control)
	if root is Control:
		_wire_one(root as Control)


static func _wire_one(c: Control) -> void:
	if c.has_meta(&"_ui_wired"):
		return
	if c is BaseButton or c is Range or c is OptionButton:
		c.set_meta(&"_ui_wired", true)
		if c.focus_mode != Control.FOCUS_NONE:
			c.mouse_entered.connect(func() -> void:
				if c.is_visible_in_tree() and not (c is BaseButton and (c as BaseButton).disabled):
					c.grab_focus())
		c.focus_entered.connect(func() -> void: sfx(&"ui_hover"))
		if c is BaseButton:
			(c as BaseButton).pressed.connect(func() -> void:
				if not c.has_meta(&"silent"):
					sfx(&"ui_click"))
		elif c is Range and not c is ScrollBar:
			(c as Range).value_changed.connect(func(_v: float) -> void: sfx(&"ui_slider"))


## First focusable visible control under root (for gamepad entry focus).
static func first_focusable(root: Node) -> Control:
	for n in root.find_children("*", "Control", true, false):
		var c := n as Control
		if c.focus_mode == Control.FOCUS_ALL and c.is_visible_in_tree():
			if c is BaseButton and (c as BaseButton).disabled:
				continue
			return c
	return null


static func fmt_playtime(seconds: float) -> String:
	var s := int(seconds)
	return "%d:%02d" % [s / 3600, (s / 60) % 60] if s >= 3600 else "%d:%02d" % [s / 60, s % 60]


static func fmt_hour(hour: float) -> String:
	var h := int(floor(hour)) % 24
	var m := int((hour - floor(hour)) * 60.0)
	return "%02d:%02d" % [h, m]


## Animated appear: fade + small rise. Returns the tween.
static func pop_in(c: CanvasItem, dur: float = 0.35, rise: float = 18.0) -> Tween:
	var t := c.create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	c.modulate.a = 0.0
	t.tween_property(c, "modulate:a", 1.0, dur)
	if c is Control and rise != 0.0:
		var ctrl := c as Control
		var y := ctrl.position.y
		ctrl.position.y = y + rise
		t.tween_property(ctrl, "position:y", y, dur)
	return t


# --- skill / modifier formatting --------------------------------------------------------------

const MOD_FLAT := ["charm_bonus", "max_health", "max_hunger", "max_energy", "max_warmth", "free_faints_per_day"]
const MOD_METRES := ["safe_fall_height"]
const MOD_UNLOCK := ["wall_jump", "catch_birds", "night_vision", "sense_collectibles", "purr_heal"]
## Modifiers where a negative number is the good direction (shown in green when negative).
const MOD_LOWER_IS_BETTER := ["fall_damage_mult", "noise_mult", "landing_noise_mult", "detection_mult", "cat_sense_cost",
	"energy_drain", "sprint_energy_mult", "hunger_drain", "warmth_drain", "wet_rate", "price_mult", "faint_cap_loss_mult"]


## "+15% Jump distance", "−30% Noise you make", "+1 Charm", "+1.5 m Safe fall height",
## "Unlocks: Wall jump". Returns [text, is_good].
static func format_effect(mod: String, value: float) -> Array:
	var name := TranslationServer.translate("MOD_" + mod.to_upper())
	if mod in MOD_UNLOCK:
		return [TranslationServer.translate("MOD_UNLOCKS").format({"what": name}), true]
	var sign_s := "+" if value >= 0.0 else "−"
	var mag := absf(value)
	var num := ""
	if mod in MOD_FLAT:
		num = "%s%s" % [sign_s, str(int(round(mag))) if absf(mag - round(mag)) < 0.01 else "%.1f" % mag]
	elif mod in MOD_METRES:
		num = "%s%.1f m" % [sign_s, mag]
	else:
		num = "%s%d%%" % [sign_s, int(round(mag * 100.0))]
	var good := (value < 0.0) if mod in MOD_LOWER_IS_BETTER else (value > 0.0)
	return ["%s %s" % [num, name], good]
