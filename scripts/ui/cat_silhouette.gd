class_name CatSilhouette
extends RefCounted
## Procedural side-view cat silhouette with a walk cycle (loading screen, splash, credits).
## draw(ci, foot_pos, scale, phase, facing, color, mode) draws onto any CanvasItem inside _draw().
## mode: &"walk" (four-beat walk, tail up for balance), &"sit" (sitting, tail curled, ear twitch).
## Units: 1.0 scale ≈ 150 px nose→tail-base, matching a real cat's 0.46 m proportions.

const BODY_HIP := Vector2(-36, -50)
const BODY_CHEST := Vector2(32, -50)


static func draw(ci: CanvasItem, foot: Vector2, s: float, phase: float, facing: float, color: Color, mode: StringName = &"walk", t: float = 0.0) -> void:
	if mode == &"sit":
		_draw_sit(ci, foot, s, facing, color, t)
		return
	var xf := Transform2D(0.0, Vector2(facing * s, s), 0.0, foot)
	# vertical bob: two bobs per cycle
	var bob := sin(phase * TAU * 2.0) * 1.6
	var body_off := Vector2(0, bob)
	# --- legs (far side first, darker) -------------------------------------------------------
	# four-beat walk: LH 0, LF 0.25, RH 0.5, RF 0.75
	var legs := [
		{"hip": Vector2(-34, -44), "off": 0.5, "front": false, "far": true},
		{"hip": Vector2(30, -44), "off": 0.75, "front": true, "far": true},
		{"hip": Vector2(-30, -44), "off": 0.0, "front": false, "far": false},
		{"hip": Vector2(34, -44), "off": 0.25, "front": true, "far": false},
	]
	for leg: Dictionary in legs:
		var c := color.darkened(0.25) if leg["far"] else color
		_draw_leg(ci, xf, (leg["hip"] as Vector2) + body_off, phase + float(leg["off"]), bool(leg["front"]), c)
	# --- tail: held up and out for balance, gentle sway ---------------------------------------
	var sway := sin(phase * TAU) * 6.0 + sin(t * 1.7) * 4.0
	var tail_pts: PackedVector2Array = []
	var p0 := Vector2(-58, -58) + body_off
	var p1 := Vector2(-86, -78 + sway * 0.3) + body_off
	var p2 := Vector2(-104, -104 + sway) + body_off
	var p3 := Vector2(-96 + sway * 0.6, -128 + sway * 0.4) + body_off
	for i in 16:
		var u := float(i) / 15.0
		tail_pts.append(_bezier(p0, p1, p2, p3, u))
	for i in tail_pts.size() - 1:
		var w := lerpf(9.0, 4.5, float(i) / 15.0)
		ci.draw_line(xf * tail_pts[i], xf * tail_pts[i + 1], color, w * s, true)
		ci.draw_circle(xf * tail_pts[i + 1], w * 0.5 * s, color)
	# --- body ------------------------------------------------------------------------------------
	var body := PackedVector2Array()
	var n := 28
	for i in n:
		var a := TAU * float(i) / float(n)
		var x := cos(a) * 52.0
		var y := sin(a) * 17.0
		# deeper chest, tucked belly, slight back arch
		if y > 0.0:
			y *= 1.0 + 0.35 * clampf(x / 52.0, 0.0, 1.0) - 0.25 * (1.0 - absf(x) / 52.0)
		else:
			y *= 1.05 + 0.1 * (1.0 - absf(x) / 52.0)
		body.append(xf * (Vector2(x - 2, y - 52) + body_off))
	ci.draw_colored_polygon(body, color)
	ci.draw_circle(xf * (BODY_CHEST + Vector2(4, 2) + body_off), 19.0 * s, color)
	ci.draw_circle(xf * (BODY_HIP + Vector2(-2, -1) + body_off), 18.0 * s, color)
	# --- neck + head ----------------------------------------------------------------------------
	var nod := sin(phase * TAU * 2.0 + 0.6) * 1.5
	var head_c := Vector2(66, -74 + nod) + body_off
	var neck := PackedVector2Array([
		xf * (Vector2(30, -68) + body_off), xf * (head_c + Vector2(-6, -10)), xf * (head_c + Vector2(4, 10)),
		xf * (Vector2(46, -40) + body_off)])
	ci.draw_colored_polygon(neck, color)
	ci.draw_circle(xf * head_c, 15.0 * s, color)
	# muzzle
	var muzzle := PackedVector2Array()
	for i in 12:
		var a := TAU * float(i) / 12.0
		muzzle.append(xf * (head_c + Vector2(12, 4) + Vector2(cos(a) * 8.0, sin(a) * 6.0)))
	ci.draw_colored_polygon(muzzle, color)
	# ears
	ci.draw_colored_polygon(PackedVector2Array([xf * (head_c + Vector2(-9, -9)), xf * (head_c + Vector2(-6, -27)),
		xf * (head_c + Vector2(3, -12))]), color)
	ci.draw_colored_polygon(PackedVector2Array([xf * (head_c + Vector2(1, -12)), xf * (head_c + Vector2(8, -28)),
		xf * (head_c + Vector2(13, -8))]), color)
	# whiskers (thin, lighter)
	var wc := Color(color.lightened(0.35), 0.55)
	for k in 3:
		var a0 := xf * (head_c + Vector2(16, 6))
		var a1 := xf * (head_c + Vector2(34, 1 + k * 5))
		ci.draw_line(a0, a1, wc, maxf(1.0, 1.1 * s), true)


static func _draw_leg(ci: CanvasItem, xf: Transform2D, hip: Vector2, ph: float, front: bool, c: Color) -> void:
	var a := sin(ph * TAU)                # swing (-1..1)
	var lift := maxf(0.0, cos(ph * TAU))  # foot up while swinging forward
	var upper := 22.0
	var lower := 24.0
	var swing := a * 0.42
	var knee_bend := (0.35 if front else -0.55) + lift * (0.5 if front else -0.6)
	var dir1 := Vector2(sin(swing), cos(swing))
	var knee := hip + dir1 * upper
	var dir2 := dir1.rotated(-knee_bend)
	var foot := knee + dir2 * lower
	foot.y = minf(foot.y, -lift * 7.0)
	if foot.y > 0.0:
		foot.y = 0.0
	var w1 := 10.0 if not front else 9.0
	ci.draw_line(xf * hip, xf * knee, c, w1 * absf(xf.get_scale().y), true)
	ci.draw_line(xf * knee, xf * foot, c, 7.0 * absf(xf.get_scale().y), true)
	ci.draw_circle(xf * knee, w1 * 0.5 * absf(xf.get_scale().y), c)
	ci.draw_circle(xf * foot, 4.6 * absf(xf.get_scale().y), c)


static func _draw_sit(ci: CanvasItem, foot: Vector2, s: float, facing: float, color: Color, t: float) -> void:
	var xf := Transform2D(0.0, Vector2(facing * s, s), 0.0, foot)
	var breathe := sin(t * 1.9) * 1.2
	# haunch + chest as a pear shape
	var body := PackedVector2Array()
	var n := 32
	for i in n:
		var a := TAU * float(i) / float(n)
		var r := 30.0 + 12.0 * maxf(0.0, sin(a)) + breathe * 0.3
		var x := cos(a) * r * 0.95
		var y := sin(a) * 40.0
		body.append(xf * Vector2(x - 4, y - 42))
	ci.draw_colored_polygon(body, color)
	ci.draw_circle(xf * Vector2(10, -80 - breathe * 0.5), 20.0 * s, color)
	# front legs
	ci.draw_line(xf * Vector2(14, -60), xf * Vector2(16, -2), color, 9.0 * s, true)
	ci.draw_line(xf * Vector2(24, -60), xf * Vector2(26, -2), color.darkened(0.2), 8.0 * s, true)
	# head
	var hc := Vector2(18, -104 - breathe * 0.6)
	ci.draw_circle(xf * hc, 15.0 * s, color)
	var twitch := 0.0
	var tt := fmod(t, 4.3)
	if tt < 0.18:
		twitch = sin(tt / 0.18 * PI) * 5.0
	ci.draw_colored_polygon(PackedVector2Array([xf * (hc + Vector2(-11, -6)), xf * (hc + Vector2(-9 - twitch, -26)),
		xf * (hc + Vector2(0, -12))]), color)
	ci.draw_colored_polygon(PackedVector2Array([xf * (hc + Vector2(2, -13)), xf * (hc + Vector2(9, -27)),
		xf * (hc + Vector2(13, -5))]), color)
	# tail curled around the paws
	var sway := sin(t * 1.1) * 5.0
	var pts: PackedVector2Array = []
	for i in 18:
		var u := float(i) / 17.0
		pts.append(_bezier(Vector2(-30, -8), Vector2(-50, 6), Vector2(10 + sway, 10), Vector2(40 + sway, -4 - sway * 0.4), u))
	for i in pts.size() - 1:
		var w := lerpf(10.0, 5.0, float(i) / 17.0)
		ci.draw_line(xf * pts[i], xf * pts[i + 1], color, w * s, true)
		ci.draw_circle(xf * pts[i + 1], w * 0.5 * s, color)


static func _bezier(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, u: float) -> Vector2:
	var v := 1.0 - u
	return p0 * v * v * v + p1 * 3.0 * v * v * u + p2 * 3.0 * v * u * u + p3 * u * u * u
