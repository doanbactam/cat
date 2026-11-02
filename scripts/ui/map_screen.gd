extends UIScreen
## Map (Bản đồ) of Hàng Mây: the live city captured top-down once (UIMapCapture) and redrawn as
## ink & wash on rice paper (paper_map.gdshader). Markers: Cam (arrow + heading), the tracked
## quest target (star lantern), discovered places with names, home (Grandma Tư's stall), nap
## spots. Pan: drag / left stick / WASD; zoom: wheel / LB·RB / + −; centre on Cam: C / R3.

const MIN_ZOOM := 1.0
const MAX_ZOOM := 5.0

var _view: _MapView
var _status: Label
var _legend: VBoxContainer
var _capturing := false


func _init() -> void:
	menu_id = &"map"


func build() -> void:
	var frame := make_frame("MAP_TITLE", &"map")
	var header: HBoxContainer = frame["header"]
	var sub := UIStyle.label(tr("MAP_SUBTITLE"), &"heading_italic", 26, UIStyle.GOLD_LIGHT)
	sub.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	header.add_child(sub)
	header.move_child(sub, 2)
	var content: Control = frame["content"]
	var h := HBoxContainer.new()
	h.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	h.add_theme_constant_override(&"separation", 24)
	content.add_child(h)
	var map_frame := PanelContainer.new()
	map_frame.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color("#2a1a12"), 6, UIStyle.GOLD_DIM, 2, 6.0))
	map_frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(map_frame)
	_view = _MapView.new()
	_view.clip_contents = true
	_view.focus_mode = Control.FOCUS_ALL
	map_frame.add_child(_view)
	var side := VBoxContainer.new()
	side.custom_minimum_size = Vector2(380, 0)
	side.add_theme_constant_override(&"separation", 14)
	h.add_child(side)
	var lp := PanelContainer.new()
	lp.theme_type_variation = &"SmallLacquerPanel"
	side.add_child(lp)
	_legend = VBoxContainer.new()
	_legend.add_theme_constant_override(&"separation", 10)
	lp.add_child(_legend)
	var lt := UIStyle.label(tr("MAP_LEGEND"), &"semibold", 16, UIStyle.GOLD)
	lt.uppercase = true
	_legend.add_child(lt)
	_legend_row(&"player_arrow", UIStyle.LANTERN_GLOW, "MAP_YOU")
	_legend_row(&"quest", UIStyle.LANTERN, "MAP_QUEST")
	_legend_row(&"home", UIStyle.SEAL_RED, "MAP_HOME")
	_legend_row(&"location", UIStyle.TEXT_INK, "MAP_PLACE", true)
	_legend_row(&"nap", UIStyle.TEAL, "MAP_NAP")
	_status = UIStyle.label("", &"prose_italic", 21, UIStyle.TEXT_DIM)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	side.add_child(_status)
	var center := Button.new()
	center.text = tr("UI_CENTER")
	center.icon = UIStyle.glyph(&"cat")
	center.pressed.connect(func() -> void: _view.center_on_player())
	side.add_child(center)
	(frame["hints"] as UIHintBar).set_hints([["@WASD|LS", "UI_PAN"], ["@+ / −|LB / RB", "UI_ZOOM"], ["@C|R3", "UI_CENTER"], [&"ui_cancel", "UI_BACK"]])
	_start_capture.call_deferred()


func _legend_row(glyph: StringName, col: Color, key: String, on_paper := false) -> void:
	var r := HBoxContainer.new()
	r.add_theme_constant_override(&"separation", 12)
	var disc := PanelContainer.new()
	disc.add_theme_stylebox_override(&"panel", UIStyle.flat_box(Color("#efe2c4") if on_paper else Color(0, 0, 0, 0), 16, Color(0, 0, 0, 0), 0, 2.0))
	disc.custom_minimum_size = Vector2(34, 34)
	disc.add_child(UIStyle.icon_rect(UIStyle.glyph(glyph), 26, col))
	r.add_child(disc)
	r.add_child(UIStyle.label(tr(key), &"medium", 20, UIStyle.TEXT))
	_legend.add_child(r)


func default_focus() -> Control:
	return _view


func _start_capture() -> void:
	if _capturing:
		return
	_capturing = true
	_status.text = ""
	var res := 2048
	var q := String(UIStyle.settings_value("graphics", "quality", "high"))
	if q == "low":
		res = 1024
	var data: Dictionary = await UIMapCapture.capture(self, res)
	_capturing = false
	if not is_inside_tree():
		return
	if data.is_empty():
		_view.set_map(null, UIMapCapture.compute_bounds(get_tree().current_scene))
		_status.text = tr("MAP_NO_CITY")
	else:
		_view.set_map(data["texture"], data["bounds"])
	_view.center_on_player()


func _unhandled_input(event: InputEvent) -> void:
	if not visible or is_closing:
		return
	if event is InputEventJoypadButton and event.is_pressed():
		var jb := event as InputEventJoypadButton
		if jb.button_index == JOY_BUTTON_LEFT_SHOULDER:
			_view.zoom_by(1.0 / 1.25)
			get_viewport().set_input_as_handled()
		elif jb.button_index == JOY_BUTTON_RIGHT_SHOULDER:
			_view.zoom_by(1.25)
			get_viewport().set_input_as_handled()
		elif jb.button_index == JOY_BUTTON_RIGHT_STICK:
			_view.center_on_player()
			get_viewport().set_input_as_handled()
	elif event is InputEventKey and event.is_pressed():
		var k := (event as InputEventKey).physical_keycode
		if k in [KEY_EQUAL, KEY_KP_ADD, KEY_PLUS]:
			_view.zoom_by(1.25)
			get_viewport().set_input_as_handled()
		elif k in [KEY_MINUS, KEY_KP_SUBTRACT]:
			_view.zoom_by(1.0 / 1.25)
			get_viewport().set_input_as_handled()
		elif k == KEY_C:
			_view.center_on_player()
			get_viewport().set_input_as_handled()


class _MapView extends Control:
	var texture: Texture2D = null
	var bounds := UIMapCapture.DEFAULT_BOUNDS
	var zoom := 1.4
	var center := Vector2.ZERO          # world XZ at the view centre
	var _tex_rect: TextureRect
	var _overlay: Control
	var _dragging := false
	var _t := 0.0
	var _paper: Texture2D

	func _ready() -> void:
		_paper = UIStyle.ui_tex("map_paper")
		_tex_rect = TextureRect.new()
		_tex_rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		_tex_rect.stretch_mode = TextureRect.STRETCH_SCALE
		_tex_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_tex_rect.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		var mat := ShaderMaterial.new()
		mat.shader = load("res://scripts/ui/shaders/paper_map.gdshader")
		mat.set_shader_parameter(&"paper", _paper)
		mat.set_shader_parameter(&"grain", UIStyle.ui_tex("paper_grain"))
		_tex_rect.material = mat
		add_child(_tex_rect)
		_overlay = Control.new()
		_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_overlay.draw.connect(_draw_markers)
		add_child(_overlay)
		center = bounds.get_center()

	func set_map(tex: Texture2D, b: Rect2) -> void:
		texture = tex
		bounds = b
		_tex_rect.texture = tex
		_tex_rect.visible = tex != null
		if tex != null:
			var m := _tex_rect.material as ShaderMaterial
			m.set_shader_parameter(&"texel", Vector2(1.0 / float(tex.get_width()), 1.0 / float(tex.get_height())) * 1.5)
		center = bounds.get_center()
		_layout()

	func px_per_m() -> float:
		var fit := minf(size.x / bounds.size.x, size.y / bounds.size.y) if bounds.size.x > 0.0 else 1.0
		return fit * zoom

	func world_to_view(p: Vector2) -> Vector2:
		return size * 0.5 + (p - center) * px_per_m()

	func view_to_world(v: Vector2) -> Vector2:
		return center + (v - size * 0.5) / px_per_m()

	func zoom_by(f: float) -> void:
		zoom = clampf(zoom * f, 1.0, 5.0)
		_layout()

	func center_on_player() -> void:
		var p := get_tree().get_first_node_in_group(&"player") as Node3D
		if p != null:
			center = Vector2(p.global_position.x, p.global_position.z)
		_layout()

	func _layout() -> void:
		var half := (size * 0.5) / px_per_m()
		center.x = clampf(center.x, bounds.position.x + minf(half.x, bounds.size.x * 0.5), bounds.end.x - minf(half.x, bounds.size.x * 0.5))
		center.y = clampf(center.y, bounds.position.y + minf(half.y, bounds.size.y * 0.5), bounds.end.y - minf(half.y, bounds.size.y * 0.5))
		var tl := world_to_view(bounds.position)
		_tex_rect.position = tl
		_tex_rect.size = bounds.size * px_per_m()
		queue_redraw()
		_overlay.queue_redraw()

	func _notification(what: int) -> void:
		if what == NOTIFICATION_RESIZED:
			_layout()

	func _process(delta: float) -> void:
		_t += delta
		if has_focus() or is_visible_in_tree():
			var mv := Input.get_vector(&"move_left", &"move_right", &"move_forward", &"move_back")
			if mv.length() > 0.05:
				center += mv * delta * 420.0 / px_per_m()
				_layout()
		_overlay.queue_redraw()

	func _gui_input(event: InputEvent) -> void:
		if event is InputEventMouseButton:
			var mb := event as InputEventMouseButton
			if mb.pressed and mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				var before := view_to_world(mb.position)
				zoom_by(1.15)
				center += before - view_to_world(mb.position)
				_layout()
				accept_event()
			elif mb.pressed and mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				zoom_by(1.0 / 1.15)
				accept_event()
			elif mb.button_index == MOUSE_BUTTON_LEFT:
				_dragging = mb.pressed
				grab_focus()
				accept_event()
		elif event is InputEventMouseMotion and _dragging:
			center -= (event as InputEventMouseMotion).relative / px_per_m()
			_layout()
			accept_event()

	func _draw() -> void:
		# rice-paper base under (and around) the captured city
		if _paper != null:
			draw_texture_rect(_paper, Rect2(Vector2.ZERO, size), true, Color(1, 1, 1, 1))
		else:
			draw_rect(Rect2(Vector2.ZERO, size), Color("#eadbb8"))

	func _draw_markers() -> void:
		var o := _overlay
		var f := UIStyle.font(&"heading_italic")
		var fb := UIStyle.font(&"semibold")
		var gs := get_node_or_null(^"/root/GameState")
		# compass rose
		var rose := Vector2(size.x - 70, 80)
		o.draw_circle(rose, 34, Color(0.95, 0.9, 0.78, 0.6))
		o.draw_arc(rose, 34, 0, TAU, 48, Color(0.35, 0.22, 0.12, 0.8), 1.5, true)
		o.draw_colored_polygon(PackedVector2Array([rose + Vector2(0, -30), rose + Vector2(7, 0), rose + Vector2(0, -6), rose + Vector2(-7, 0)]), Color("#b8321f"))
		o.draw_colored_polygon(PackedVector2Array([rose + Vector2(0, 30), rose + Vector2(7, 0), rose + Vector2(0, 6), rose + Vector2(-7, 0)]), Color(0.3, 0.2, 0.12, 0.8))
		var nt := tr("COMPASS_N")
		o.draw_string(fb, rose + Vector2(-6, -38), nt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color("#2b211a"))
		# scale bar (20 m)
		var m20 := 20.0 * px_per_m()
		var sb0 := Vector2(30, size.y - 34)
		o.draw_line(sb0, sb0 + Vector2(m20, 0), Color("#2b211a"), 3.0)
		o.draw_line(sb0 + Vector2(0, -6), sb0 + Vector2(0, 6), Color("#2b211a"), 2.0)
		o.draw_line(sb0 + Vector2(m20, -6), sb0 + Vector2(m20, 6), Color("#2b211a"), 2.0)
		o.draw_string(fb, sb0 + Vector2(m20 + 8, 6), "20 m", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("#2b211a"))
		# nap spots
		var nap_icon := UIStyle.glyph(&"nap")
		for n in get_tree().get_nodes_in_group(&"interactable"):
			var n3 := n as Node3D
			if n3 == null or n3.get_script() == null or (n3.get_script() as Script).get_global_name() != &"NapSpot":
				continue
			var v := world_to_view(Vector2(n3.global_position.x, n3.global_position.z))
			if nap_icon != null:
				o.draw_texture_rect(nap_icon, Rect2(v - Vector2(10, 10), Vector2(20, 20)), false, Color(UIStyle.TEAL, 0.85))
		# discovered places
		var loc_icon := UIStyle.glyph(&"location")
		var home_icon := UIStyle.glyph(&"home")
		for n in get_tree().get_nodes_in_group(&"location"):
			var n3 := n as Node3D
			if n3 == null:
				continue
			var id := StringName(str(n3.get_meta(&"location_id", n3.name)))
			if gs != null and not bool(gs.call("is_location_discovered", id)):
				continue
			var v := world_to_view(Vector2(n3.global_position.x, n3.global_position.z))
			var home := id == &"tea_stall"
			var ic := home_icon if home else loc_icon
			var s := 30.0 if home else 24.0
			o.draw_circle(v, s * 0.62, Color(0.94, 0.88, 0.75, 0.85))
			if ic != null:
				o.draw_texture_rect(ic, Rect2(v - Vector2(s, s) * 0.5, Vector2(s, s)), false, Color("#b8321f") if home else Color("#2b211a"))
			var name_key := String(n3.get_meta(&"display_name_key", ""))
			var label := tr(name_key) if name_key != "" else String(id)
			var ts := f.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20)
			o.draw_string_outline(f, v + Vector2(-ts.x * 0.5, s * 0.6 + 20), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, 5, Color(0.94, 0.88, 0.75, 0.9))
			o.draw_string(f, v + Vector2(-ts.x * 0.5, s * 0.6 + 20), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("#2b211a"))
		# tracked quest
		var qm := get_node_or_null(^"/root/QuestManager")
		if qm != null:
			var qp: Vector3 = qm.call("get_tracked_target_position")
			if qp != Vector3.INF:
				var v := world_to_view(Vector2(qp.x, qp.z))
				var pulse := 0.5 + 0.5 * sin(_t * 3.0)
				o.draw_arc(v, 22.0 + pulse * 8.0, 0, TAU, 40, Color(UIStyle.LANTERN, 0.6 * (1.0 - pulse)), 3.0, true)
				var qi := UIStyle.glyph(&"quest")
				if qi != null:
					o.draw_texture_rect(qi, Rect2(v - Vector2(17, 19), Vector2(34, 34)), false, UIStyle.LANTERN)
		# Cam
		var p := get_tree().get_first_node_in_group(&"player") as Node3D
		if p != null:
			var v := world_to_view(Vector2(p.global_position.x, p.global_position.z))
			var heading := 0.0
			var cam := get_viewport().get_camera_3d()
			if cam != null:
				var fw := -cam.global_basis.z
				heading = atan2(fw.x, -fw.z)
			var arrow := UIStyle.glyph(&"player_arrow")
			o.draw_circle(v, 20, Color(0.1, 0.06, 0.04, 0.35))
			o.draw_set_transform(v, heading, Vector2.ONE)
			if arrow != null:
				o.draw_texture_rect(arrow, Rect2(Vector2(-15, -17), Vector2(30, 30)), false, Color("#e2683a"))
			o.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
