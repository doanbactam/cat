class_name UIScreen
extends Control
## Base class for full-screen menus (settings, journal, inventory, map, ...). Screens are pushed
## onto a UIMenuHost which handles back/cancel, focus restore and open/close animation.
## Subclasses override build() (create children), default_focus(), handle_back() and
## on_tab_input(dir) (LB/RB or Q/E when the screen has tabs).

signal closed(screen: UIScreen)

## Id sent with GameEvents.ui_menu_opened/closed (e.g. &"inventory", &"map").
@export var menu_id: StringName = &""
## Dim + blur the game behind the screen.
@export var dim_background := true

var host: Node = null
var is_closing := false
var _built := false
var _backdrop: ColorRect = null


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	process_mode = Node.PROCESS_MODE_ALWAYS
	if theme == null:
		theme = UIStyle.theme()
	if dim_background:
		_backdrop = ColorRect.new()
		_backdrop.name = "Backdrop"
		_backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		_backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var mat := ShaderMaterial.new()
		mat.shader = preload("res://scripts/ui/shaders/blur_dim.gdshader")
		_backdrop.material = mat
		add_child(_backdrop)
		move_child(_backdrop, 0)
	if not _built:
		_built = true
		build()
	UIStyle.wire_sounds(self)


## Create the screen's children here.
func build() -> void:
	pass


## Control that gets keyboard/gamepad focus when the screen opens.
func default_focus() -> Control:
	return UIStyle.first_focusable(self)


## Return true when the back press was consumed (e.g. closing an inner panel).
func handle_back() -> bool:
	return false


## dir = -1 (LB / Q) or +1 (RB / E). Return true when consumed.
func on_tab_input(_dir: int) -> bool:
	return false


## Called by the host after the screen is in the tree.
func on_opened() -> void:
	modulate.a = 0.0
	var tw := create_tween().set_parallel(true).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(self, "modulate:a", 1.0, 0.22)
	focus_default.call_deferred()


func focus_default() -> void:
	if not is_inside_tree():
		return
	var f := default_focus()
	if f != null and f.is_visible_in_tree():
		f.grab_focus()


## Ask the host to close this screen (plays the close animation).
func request_close() -> void:
	if is_closing:
		return
	if host != null and host.has_method("pop_screen"):
		host.call("pop_screen", self)
	else:
		close_now()


func close_now() -> void:
	if is_closing:
		return
	is_closing = true
	var tw := create_tween()
	tw.set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	tw.tween_property(self, "modulate:a", 0.0, 0.16)
	tw.tween_callback(func() -> void:
		closed.emit(self)
		queue_free())


# --- shared layout helpers for subclasses ----------------------------------------------------

## Standard screen frame: title + optional tab strip + content area + hint bar.
## Returns {"root": MarginContainer, "header": HBoxContainer, "content": Control, "hints": UIHintBar}.
func make_frame(title_key: String, icon: StringName = &"") -> Dictionary:
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override(&"margin_left", 96)
	margin.add_theme_constant_override(&"margin_right", 96)
	margin.add_theme_constant_override(&"margin_top", 60)
	margin.add_theme_constant_override(&"margin_bottom", 40)
	add_child(margin)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 18)
	margin.add_child(v)
	var header := HBoxContainer.new()
	header.add_theme_constant_override(&"separation", 18)
	v.add_child(header)
	if icon != &"":
		var ic := UIStyle.icon_rect(UIStyle.glyph(icon), 44, UIStyle.GOLD)
		header.add_child(ic)
	var t := Label.new()
	t.theme_type_variation = &"HeadingLabel"
	t.text = tr(title_key)
	t.name = "Title"
	header.add_child(t)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	var line := UIStyle.divider(1200, Color(UIStyle.GOLD, 0.7))
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.custom_minimum_size = Vector2(0, 18)
	line.stretch_mode = TextureRect.STRETCH_SCALE
	v.add_child(line)
	var content := Control.new()
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.name = "Content"
	v.add_child(content)
	var hints := UIHintBar.new()
	v.add_child(hints)
	return {"root": margin, "header": header, "content": content, "hints": hints, "vbox": v}


## A row of TabButtons (toggle group). Returns the HBox; `on_select` receives the index.
func make_tabs(keys: PackedStringArray, icons: Array, on_select: Callable) -> HBoxContainer:
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override(&"separation", 6)
	var group := ButtonGroup.new()
	for i in keys.size():
		var b := Button.new()
		b.theme_type_variation = &"TabButton"
		b.toggle_mode = true
		b.button_group = group
		b.text = tr(keys[i])
		if i < icons.size() and icons[i] != &"":
			b.icon = UIStyle.glyph(icons[i])
			b.expand_icon = false
			b.add_theme_constant_override(&"icon_max_width", 26)
		var idx := i
		b.pressed.connect(func() -> void: on_select.call(idx))
		bar.add_child(b)
	if bar.get_child_count() > 0:
		(bar.get_child(0) as Button).button_pressed = true
	return bar
