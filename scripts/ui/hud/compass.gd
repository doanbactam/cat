class_name HudCompass
extends Control
## Compass strip (top centre). Heading comes from the active Camera3D (Godot -Z = north).
## Ticks every 15°, localized cardinal letters, markers for the tracked quest target
## (QuestManager.get_tracked_target_position, with distance), discovered locations (group
## "location", meta location_id) and home (tea_stall). Off-strip quest targets cling to the edge.

const SPAN_DEG := 150.0
const LOCATION_RANGE := 140.0

var heading := 0.0                  # degrees, 0 = north, 90 = east
var quest_target := Vector3.INF
var _player_pos := Vector3.ZERO
var _locations: Array[Dictionary] = []   # {"pos": Vector3, "id": StringName, "home": bool}
var _poll_t := 0.0
var _font: Font
var _font_b: Font
var _quest_icon: Texture2D
var _loc_icon: Texture2D
var _home_icon: Texture2D
var _quest_pulse := 0.0
var fixed_heading := -1.0           # tests / previews: force a heading


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(700, 64)
	_font = UIStyle.font(&"semibold")
	_font_b = UIStyle.font(&"bold")
	_quest_icon = UIStyle.glyph(&"quest")
	_loc_icon = UIStyle.glyph(&"location")
	_home_icon = UIStyle.glyph(&"home")


func _process(delta: float) -> void:
	_quest_pulse += delta
	var cam := get_viewport().get_camera_3d()
	if fixed_heading >= 0.0:
		heading = fixed_heading
	elif cam != null:
		var f := -cam.global_basis.z
		heading = fposmod(rad_to_deg(atan2(f.x, -f.z)), 360.0)
	var p := get_tree().get_first_node_in_group(&"player") as Node3D
	if p != null:
		_player_pos = p.global_position
	elif cam != null:
		_player_pos = cam.global_position
	_poll_t -= delta
	if _poll_t <= 0.0:
		_poll_t = 0.25
		_poll()
	queue_redraw()


func _poll() -> void:
	var qm := get_node_or_null(^"/root/QuestManager")
	if qm != null and qm.has_method("get_tracked_target_position"):
		quest_target = qm.call("get_tracked_target_position")
	_locations.clear()
	var gs := get_node_or_null(^"/root/GameState")
	for n in get_tree().get_nodes_in_group(&"location"):
		var n3 := n as Node3D
		if n3 == null:
			continue
		var id := StringName(str(n3.get_meta(&"location_id", n3.name)))
		var discovered := gs == null or not gs.has_method("is_location_discovered") or bool(gs.call("is_location_discovered", id))
		if not discovered:
			continue
		var pos := n3.global_position
		if pos.distance_to(_player_pos) > LOCATION_RANGE and id != &"tea_stall":
			continue
		_locations.append({"pos": pos, "id": id, "home": id == &"tea_stall"})


func bearing_to(target: Vector3) -> float:
	var d := target - _player_pos
	return fposmod(rad_to_deg(atan2(d.x, -d.z)), 360.0)


## Screen x (relative to the strip) of a world bearing; returns NAN when off the strip.
func x_for_bearing(b: float) -> float:
	var rel := wrapf(b - heading, -180.0, 180.0)
	if absf(rel) > SPAN_DEG * 0.5:
		return NAN
	return size.x * 0.5 + rel / (SPAN_DEG * 0.5) * (size.x * 0.5 - 20.0)


func _draw() -> void:
	var w := size.x
	var cy := 24.0
	# background band fading at the ends
	var steps := 48
	for i in steps:
		var x0 := w * float(i) / steps
		var x1 := w * float(i + 1) / steps
		var u := absf((x0 + x1) * 0.5 / w - 0.5) * 2.0
		var a := 0.42 * clampf(1.0 - pow(u, 3.0), 0.0, 1.0)
		draw_rect(Rect2(x0, cy - 15, x1 - x0 + 0.5, 30), Color(0.05, 0.035, 0.025, a))
	draw_line(Vector2(w * 0.08, cy + 15), Vector2(w * 0.92, cy + 15), Color(UIStyle.GOLD, 0.35), 1.0, true)
	# ticks + letters
	var letters := {0: "COMPASS_N", 45: "COMPASS_NE", 90: "COMPASS_E", 135: "COMPASS_SE", 180: "COMPASS_S",
		225: "COMPASS_SW", 270: "COMPASS_W", 315: "COMPASS_NW"}
	for deg in range(0, 360, 15):
		var x := x_for_bearing(float(deg))
		if is_nan(x):
			continue
		var edge := absf(x / w - 0.5) * 2.0
		var fade := clampf(1.0 - pow(edge, 4.0), 0.0, 1.0)
		if letters.has(deg):
			var main := deg % 90 == 0
			var t := tr(String(letters[deg]))
			var fs := 22 if main else 15
			var f := _font_b if main else _font
			var ts := f.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
			var col := (UIStyle.LANTERN_GLOW if deg == 0 else UIStyle.TEXT) if main else UIStyle.TEXT_DIM
			col.a *= fade
			draw_string_outline(f, Vector2(x - ts.x * 0.5, cy + fs * 0.36), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color(0, 0, 0, 0.55 * fade))
			draw_string(f, Vector2(x - ts.x * 0.5, cy + fs * 0.36), t, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
		else:
			draw_line(Vector2(x, cy - 5), Vector2(x, cy + 5), Color(UIStyle.TEXT, 0.45 * fade), 1.5, true)
	# centre notch
	draw_colored_polygon(PackedVector2Array([Vector2(w * 0.5 - 7, cy - 21), Vector2(w * 0.5 + 7, cy - 21), Vector2(w * 0.5, cy - 13)]), UIStyle.GOLD_LIGHT)
	# location markers
	for l: Dictionary in _locations:
		var b := bearing_to(l["pos"])
		var x := x_for_bearing(b)
		if is_nan(x):
			continue
		var icon := _home_icon if bool(l["home"]) else _loc_icon
		var sz := 20.0 if bool(l["home"]) else 16.0
		var c := Color(UIStyle.GOLD_LIGHT, 0.85) if bool(l["home"]) else Color(UIStyle.TEXT, 0.6)
		if icon != null:
			draw_texture_rect(icon, Rect2(Vector2(x - sz * 0.5, cy + 17), Vector2(sz, sz)), false, c)
	# tracked quest marker
	if quest_target != Vector3.INF:
		var b := bearing_to(quest_target)
		var x := x_for_bearing(b)
		var clamped := false
		if is_nan(x):
			clamped = true
			var rel := wrapf(b - heading, -180.0, 180.0)
			x = 22.0 if rel < 0.0 else w - 22.0
		var pulse := 0.5 + 0.5 * sin(_quest_pulse * 3.0)
		var sz := 30.0
		var col := UIStyle.LANTERN_GLOW.lerp(Color.WHITE, 0.25 * pulse)
		var glow := UIStyle.ui_tex("glow_soft")
		if glow != null:
			draw_texture_rect(glow, Rect2(Vector2(x - 28, cy - 28), Vector2(56, 56)), false, Color(1.0, 0.55, 0.25, 0.35 + 0.2 * pulse))
		if _quest_icon != null:
			draw_texture_rect(_quest_icon, Rect2(Vector2(x - sz * 0.5, cy - sz * 0.5 - 2), Vector2(sz, sz)), false, col)
		if clamped:
			var dir := -1.0 if x < w * 0.5 else 1.0
			draw_colored_polygon(PackedVector2Array([Vector2(x + dir * 20, cy - 6), Vector2(x + dir * 28, cy), Vector2(x + dir * 20, cy + 6)]), col)
		var dist := Vector2(quest_target.x - _player_pos.x, quest_target.z - _player_pos.z).length()
		var dt := tr("HUD_DISTANCE").format({"m": int(round(dist))})
		var ts := _font.get_string_size(dt, HORIZONTAL_ALIGNMENT_LEFT, -1, 16)
		var dy := cy + 34.0
		var dx := clampf(x - ts.x * 0.5, 0.0, w - ts.x)
		draw_string_outline(_font, Vector2(dx, dy), dt, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, 4, Color(0, 0, 0, 0.6))
		draw_string(_font, Vector2(dx, dy), dt, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, UIStyle.GOLD_LIGHT)
