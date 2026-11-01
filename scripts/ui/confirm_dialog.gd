class_name UIConfirmDialog
extends UIScreen
## Modal yes/no dialog on a lacquer card. Push it on a UIMenuHost:
##   var d := UIConfirmDialog.make("CONFIRM_QUIT_TITLE", "CONFIRM_QUIT_BODY")
##   d.confirmed.connect(...); host.push_screen(d)
## The "No" button has default focus (safe choice); Esc/B cancels.

signal confirmed()
signal cancelled()

var title_key := ""
var body_key := ""
var body_args: Dictionary = {}
var yes_key := "CONFIRM_YES"
var no_key := "CONFIRM_NO"
var danger := false
var _no: Button
var _answered := false


static func make(t_key: String, b_key: String, is_danger: bool = false, args: Dictionary = {}) -> UIConfirmDialog:
	var d := UIConfirmDialog.new()
	d.title_key = t_key
	d.body_key = b_key
	d.danger = is_danger
	d.body_args = args
	d.menu_id = &"confirm"
	return d


func build() -> void:
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var card := PanelContainer.new()
	card.theme_type_variation = &"LacquerPanel"
	card.custom_minimum_size = Vector2(760, 0)
	center.add_child(card)
	var v := VBoxContainer.new()
	v.add_theme_constant_override(&"separation", 20)
	card.add_child(v)
	var seal := UIStyle.icon_rect(UIStyle.ui_tex("seal_stamp"), 64)
	seal.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	v.add_child(seal)
	var t := Label.new()
	t.theme_type_variation = &"HeadingLabel"
	t.add_theme_font_size_override(&"font_size", 38)
	t.text = tr(title_key)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(t)
	if body_key != "":
		var b := Label.new()
		b.theme_type_variation = &"MutedLabel"
		b.add_theme_font_size_override(&"font_size", 23)
		b.text = tr(body_key).format(body_args)
		b.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		v.add_child(b)
	v.add_child(UIStyle.divider(420, Color(UIStyle.GOLD, 0.6)))
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override(&"separation", 24)
	v.add_child(row)
	var yes := Button.new()
	yes.text = tr(yes_key)
	yes.theme_type_variation = &"DangerButton" if danger else &"PrimaryButton"
	yes.custom_minimum_size = Vector2(220, 56)
	yes.pressed.connect(_on_yes)
	row.add_child(yes)
	_no = Button.new()
	_no.text = tr(no_key)
	_no.custom_minimum_size = Vector2(220, 56)
	_no.pressed.connect(_on_no)
	row.add_child(_no)
	yes.focus_neighbor_right = yes.get_path_to(_no)
	_no.focus_neighbor_left = _no.get_path_to(yes)
	UIStyle.sfx(&"ui_notify")


func default_focus() -> Control:
	return _no


func handle_back() -> bool:
	_on_no()
	return true


func _on_yes() -> void:
	if _answered:
		return
	_answered = true
	UIStyle.sfx(&"ui_confirm")
	request_close()
	confirmed.emit()


func _on_no() -> void:
	if _answered:
		return
	_answered = true
	request_close()
	cancelled.emit()
