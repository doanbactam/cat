class_name HudVitalRing
extends Control
## One vital (health / hunger / energy / warmth) as a small elegant ring around a glyph.
## Fades out when full and steady; reappears on change; pulses gently when low (< 25 %).

@export var stat: StringName = &"health"
@export var diameter := 66.0

var ratio := 1.0
var shown_ratio := 1.0
var _visible_t := 1.0      # 0..1 fade
var _since_change := 99.0
var _pulse := 0.0
var _flash := 0.0
var _icon: Texture2D
var _color := Color.WHITE
var always_visible := false


func _ready() -> void:
	custom_minimum_size = Vector2(diameter, diameter)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_icon = UIStyle.glyph(UIStyle.VITAL_ICONS.get(stat, &"health"))
	_color = UIStyle.VITAL_COLORS.get(stat, UIStyle.GOLD)
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and gs.has_method("get_stat_ratio"):
		ratio = float(gs.call("get_stat_ratio", stat))
		shown_ratio = ratio
	_visible_t = 0.0 if ratio >= 0.98 else 1.0


func set_ratio(r: float, animate := true) -> void:
	r = clampf(r, 0.0, 1.0)
	if absf(r - ratio) > 0.0005:
		if r < ratio - 0.02:
			_flash = 1.0
		_since_change = 0.0
	ratio = r
	if not animate:
		shown_ratio = r


func is_faded_out() -> bool:
	return _visible_t < 0.02


func _process(delta: float) -> void:
	_since_change += delta
	shown_ratio = move_toward(shown_ratio, ratio, delta * 0.6)
	var want := 1.0
	if not always_visible and ratio >= 0.98 and _since_change > 3.5:
		want = 0.0
	_visible_t = move_toward(_visible_t, want, delta * (2.5 if want > _visible_t else 0.8))
	_pulse += delta * (4.0 if ratio < 0.15 else 2.4)
	_flash = maxf(0.0, _flash - delta * 2.0)
	modulate.a = _visible_t
	queue_redraw()


func _draw() -> void:
	var c := size * 0.5
	var r := diameter * 0.5
	var low := ratio < 0.25
	var pulse := (0.5 + 0.5 * sin(_pulse)) if low else 0.0
	# soft dark disc behind for legibility over the bright city
	draw_circle(c, r + 2.0, Color(0.03, 0.02, 0.015, 0.55))
	draw_circle(c, r - 7.0, Color(0.08, 0.055, 0.04, 0.55))
	# track
	var w := 5.0
	draw_arc(c, r - w * 0.5 - 1.0, 0.0, TAU, 64, Color(_color, 0.18), w, true)
	# value arc (clockwise from top)
	var col := _color.lerp(Color("#ff5a3c"), pulse * 0.6) if low else _color
	if _flash > 0.0:
		col = col.lerp(Color.WHITE, _flash * 0.6)
	if shown_ratio > 0.002:
		draw_arc(c, r - w * 0.5 - 1.0, -PI * 0.5, -PI * 0.5 + TAU * shown_ratio, maxi(8, int(64 * shown_ratio)), col, w, true)
		# bright tip
		var tip := c + Vector2.from_angle(-PI * 0.5 + TAU * shown_ratio) * (r - w * 0.5 - 1.0)
		draw_circle(tip, w * 0.62, col.lightened(0.35))
	if low:
		draw_arc(c, r + 3.0 + pulse * 4.0, 0.0, TAU, 64, Color(col, 0.35 * (1.0 - pulse)), 2.0, true)
	if _icon != null:
		var isz := diameter * 0.40
		var ic := col.lerp(Color.WHITE, 0.25) if not low else col.lerp(Color.WHITE, 0.4 * pulse)
		draw_texture_rect(_icon, Rect2(c - Vector2(isz, isz) * 0.5, Vector2(isz, isz)), false, ic)
