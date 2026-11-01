class_name HudPrompt
extends PanelContainer
## Interaction prompt (bottom centre): [input glyph] + the interactable's (already translated)
## prompt. The glyph follows the active device. Verb "pickup" shows the pick-up/drop binding.
## Second line: the current secondary action (e.g. "drop" while carrying an item) when hints are on.

var _glyph: UIInputGlyph
var _label: Label
var _target: Node = null
var _shown := false
var _tween: Tween


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sb := UIStyle.flat_box(Color(0.05, 0.035, 0.026, 0.78), 26, Color(UIStyle.GOLD, 0.45), 1, 16.0)
	sb.content_margin_left = 12
	sb.content_margin_right = 26
	sb.content_margin_top = 8
	sb.content_margin_bottom = 8
	sb.shadow_color = Color(0, 0, 0, 0.3)
	sb.shadow_size = 10
	add_theme_stylebox_override(&"panel", sb)
	var h := HBoxContainer.new()
	h.add_theme_constant_override(&"separation", 14)
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(h)
	_glyph = UIInputGlyph.new()
	_glyph.glyph_height = 38.0
	_glyph.action = &"interact"
	_glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	h.add_child(_glyph)
	_label = UIStyle.label("", &"semibold", 24, UIStyle.TEXT)
	_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	h.add_child(_label)
	modulate.a = 0.0
	visible = false
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.connect(&"interactable_focused", _on_focused)
		ge.connect(&"interactable_unfocused", _on_unfocused)
		ge.connect(&"dialogue_started", func(_d: StringName, _s: StringName) -> void: hide_prompt())


func _on_focused(target: Node, prompt: String) -> void:
	show_prompt(target, prompt)


func _on_unfocused(target: Node) -> void:
	if target == _target or _target == null or not is_instance_valid(_target):
		hide_prompt()


func show_prompt(target: Node, prompt: String) -> void:
	_target = target
	var verb := &"interact"
	if target != null and is_instance_valid(target) and target.get(&"verb") != null:
		verb = StringName(str(target.get(&"verb")))
	_glyph.set_action(&"pickup_drop" if verb == &"pickup" and InputMap.has_action(&"pickup_drop") else &"interact")
	_label.text = prompt
	if not _shown:
		_shown = true
		visible = true
		_fade(1.0)


func hide_prompt() -> void:
	_target = null
	if _shown:
		_shown = false
		_fade(0.0)


func is_showing() -> bool:
	return _shown


func get_text() -> String:
	return _label.text


func _fade(a: float) -> void:
	if _tween != null and _tween.is_valid():
		_tween.kill()
	_tween = create_tween()
	_tween.tween_property(self, "modulate:a", a, 0.15 if a > 0.5 else 0.25)
	if a < 0.5:
		_tween.tween_callback(func() -> void:
			if not _shown:
				visible = false)
