extends RefCounted
## Precision jump targeting for Cam (owner: player).
##
## find_target() samples landing surfaces in a fan around an aim direction (ray grid + an exact
## probe under the camera aim point), keeps "interesting" spots (ledges up/down, gaps, beams),
## validates head-room and a collision-free parabolic arc, and returns the best one.
## solve_arc() gives the launch velocity that lands EXACTLY on a point; the player then follows
## the analytic parabola so numerical integration never misses the landing.

const LAYER_WORLD := 1
const LAYER_PROPS := 1 << 3
const LAYER_CLIMBABLE := 1 << 5
const LAYER_WATER := 1 << 6
const LAYER_VEHICLES := 1 << 7

## Surfaces the cat can land on (water is never a target — cats avoid it).
var mask: int = LAYER_WORLD | LAYER_PROPS | LAYER_CLIMBABLE | LAYER_VEHICLES
var space: PhysicsDirectSpaceState3D
var exclude: Array[RID] = []
var gravity := 14.0
var body_radius := 0.085
var body_height := 0.22
## Reach (already scaled by the GameState jump modifiers by the caller).
var max_height := 1.6
var max_distance := 2.5
var max_drop := 4.5
var min_distance := 0.28
var fan_half_angle := deg_to_rad(30.0)
var fan_rays := 7
var sample_step := 0.07
var max_horizontal_speed := 7.5
var floor_normal_min := 0.72

var _head_shape: CylinderShape3D
var _probe_sphere: SphereShape3D
var _ray := PhysicsRayQueryParameters3D.new()
var _shape_q := PhysicsShapeQueryParameters3D.new()


func _init() -> void:
	_head_shape = CylinderShape3D.new()
	_probe_sphere = SphereShape3D.new()
	_probe_sphere.radius = 0.035
	_ray.collide_with_areas = false
	_ray.hit_from_inside = false
	_shape_q.collide_with_areas = false


func configure(p_space: PhysicsDirectSpaceState3D, p_exclude: Array[RID], radius: float, height: float) -> void:
	space = p_space
	exclude = p_exclude
	body_radius = radius
	body_height = height
	_head_shape.radius = radius * 0.85
	_head_shape.height = height * 0.75


# ---------------------------------------------------------------------------------------------
# Arc maths
# ---------------------------------------------------------------------------------------------

## Launch velocity / flight time to go from p0 to p1 with an apex `apex_extra` above the higher of
## the two points. Returns {v0: Vector3, time: float, apex: float}.
static func solve_arc(p0: Vector3, p1: Vector3, g: float, apex_extra: float) -> Dictionary:
	var top := maxf(p0.y, p1.y) + maxf(apex_extra, 0.02)
	var vy := sqrt(2.0 * g * maxf(top - p0.y, 0.0005))
	var t_up := vy / g
	var t_down := sqrt(2.0 * maxf(top - p1.y, 0.0) / g)
	var t := maxf(t_up + t_down, 0.05)
	var dh := Vector3(p1.x - p0.x, 0.0, p1.z - p0.z)
	return {"v0": dh / t + Vector3.UP * vy, "time": t, "apex": top}


static func arc_point(p0: Vector3, v0: Vector3, g: float, t: float) -> Vector3:
	return p0 + v0 * t + Vector3.DOWN * (0.5 * g * t * t)


## Default apex clearance for a jump: higher for longer jumps and for jumps up onto ledges.
static func default_apex_extra(p0: Vector3, p1: Vector3) -> float:
	var d := Vector2(p1.x - p0.x, p1.z - p0.z).length()
	var up := p1.y - p0.y
	var extra := 0.10 + 0.09 * d
	if up > 0.0:
		extra = 0.13 + 0.05 * d  # clear the lip of the ledge, but no floaty lob
	elif up < -0.3:
		extra = 0.06 + 0.06 * d  # hop off, then drop
	return extra


# ---------------------------------------------------------------------------------------------
# Target search
# ---------------------------------------------------------------------------------------------

## origin: the cat's feet. aim_dir: horizontal unit direction. aim_point: exact camera-aim world
## point (Vector3.INF if none). Returns {} when nothing suitable, else
## {point, normal, collider, v0, time, apex, score, kind, narrow}.
## allow_flat_aim: also accept a plain spot on the same floor under the aim point (deliberate
## aiming); otherwise only ledges, drops, gaps and beams are targets.
func find_target(origin: Vector3, aim_dir: Vector3, aim_point: Vector3 = Vector3.INF, allow_flat_aim := false) -> Dictionary:
	if space == null:
		return {}
	aim_dir.y = 0.0
	if aim_dir.length_squared() < 0.0001:
		return {}
	aim_dir = aim_dir.normalized()
	var candidates: Array[Dictionary] = []
	# 1) fan of downward ray samples
	for i in fan_rays:
		var f := 0.0 if fan_rays == 1 else (float(i) / float(fan_rays - 1)) * 2.0 - 1.0
		var ang := f * fan_half_angle
		var dir := aim_dir.rotated(Vector3.UP, ang)
		_scan_direction(origin, dir, absf(ang), candidates)
	# 2) exact probe under the aim point (thin rails, cables, precise picks)
	if aim_point != Vector3.INF:
		var c := _probe_point(origin, aim_point)
		if not c.is_empty() and (allow_flat_aim or bool(c["interesting"])):
			c["aim_exact"] = true
			candidates.append(c)
	if candidates.is_empty():
		return {}
	# preliminary score, then validate the best few
	for c in candidates:
		c["score"] = _score(origin, aim_dir, aim_point, c)
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["score"]) > float(b["score"]))
	var tries := mini(candidates.size(), 8)
	for i in tries:
		var c: Dictionary = candidates[i]
		var arc := validate(origin, c["point"])
		if not arc.is_empty():
			c.merge(arc, true)
			return c
	return {}


## Head-room + arc check for landing at `point`. Returns arc dictionary or {} when blocked.
func validate(origin: Vector3, point: Vector3) -> Dictionary:
	if not _has_headroom(point):
		return {}
	var base_extra := default_apex_extra(origin, point)
	for extra_add: float in [0.0, 0.22, 0.45]:
		var extra: float = base_extra + extra_add
		var top := maxf(origin.y, point.y) + extra
		if top - origin.y > max_height + 0.35:
			break
		var arc := solve_arc(origin, point, gravity, extra)
		var v0: Vector3 = arc["v0"]
		if Vector2(v0.x, v0.z).length() > max_horizontal_speed:
			return {}
		if _arc_clear(origin, v0, float(arc["time"])):
			return arc
	return {}


func _scan_direction(origin: Vector3, dir: Vector3, ang: float, out: Array[Dictionary]) -> void:
	var top_y := origin.y + max_height + 0.25
	var bottom_y := origin.y - max_drop
	var n := int(ceil((max_distance - min_distance) / sample_step)) + 1
	var seg_y := 0.0
	var seg_hits: Array[Dictionary] = []
	# lowest surface crossed between the cat and the current segment (-INF = a void)
	var min_between := origin.y
	var seg_min_between := origin.y
	for s in n + 1:
		var d := min_distance + float(s) * sample_step
		var hit: Dictionary = {}
		if s < n:
			var p := origin + dir * d
			hit = _ray_down(Vector3(p.x, top_y, p.z), bottom_y)
			if not hit.is_empty() and (hit["normal"] as Vector3).y < floor_normal_min:
				hit = {}
		var y := float((hit["position"] as Vector3).y) if not hit.is_empty() else -INF
		var same := not hit.is_empty() and not seg_hits.is_empty() and absf(y - seg_y) < 0.045
		if not seg_hits.is_empty() and not same:
			var gap := seg_min_between < minf(origin.y, seg_y) - 0.35
			_emit_segment(origin, dir, ang, seg_hits, gap, out)
			min_between = minf(min_between, seg_y)
			seg_hits = []
		if hit.is_empty():
			min_between = -INF
			continue
		if seg_hits.is_empty():
			seg_y = y
			seg_min_between = min_between
		hit["dist"] = d
		seg_hits.append(hit)


func _emit_segment(origin: Vector3, dir: Vector3, ang: float, hits: Array[Dictionary], gap: bool, out: Array[Dictionary]) -> void:
	if hits.is_empty():
		return
	var first: Dictionary = hits[0]
	var y := float((first["position"] as Vector3).y)
	var dh := y - origin.y
	var interesting := absf(dh) > 0.16 or gap
	if not interesting:
		return
	if dh > max_height + 0.02 or dh < -max_drop:
		return
	var narrow := hits.size() <= 2
	var pick: Dictionary
	if narrow:
		# beam / rail / narrow wall top: land on its middle
		var pa: Vector3 = (hits[0] as Dictionary)["position"]
		var pb: Vector3 = (hits[hits.size() - 1] as Dictionary)["position"]
		pick = hits[0].duplicate()
		var mid := (pa + pb) * 0.5
		var refined := _ray_down(mid + Vector3.UP * 0.3, mid.y - 0.3)
		pick["position"] = refined["position"] if not refined.is_empty() else mid
	else:
		# ledge: land a little past the lip so the whole body is supported
		var inset := mini(int(ceil(0.13 / sample_step)), hits.size() - 1)
		inset = mini(inset, int(hits.size() / 2.0))
		pick = hits[inset].duplicate()
	var c := {
		"point": pick["position"],
		"normal": pick["normal"],
		"collider": pick.get("collider"),
		"angle": ang,
		"dist": float(pick.get("dist", 0.0)),
		"dh": float((pick["position"] as Vector3).y - origin.y),
		"gap": gap,
		"narrow": narrow,
		"kind": &"beam" if narrow else (&"up" if dh > 0.16 else (&"down" if dh < -0.16 else &"gap")),
	}
	out.append(c)


func _probe_point(origin: Vector3, aim_point: Vector3) -> Dictionary:
	var flat := Vector2(aim_point.x - origin.x, aim_point.z - origin.z)
	var d := flat.length()
	if d < min_distance or d > max_distance + 0.05:
		return {}
	var top_y := minf(aim_point.y + 0.35, origin.y + max_height + 0.25)
	# sphere-cast down so thin cables / rails under the crosshair are found
	var from := Vector3(aim_point.x, top_y, aim_point.z)
	var hit := _sphere_down(from, maxf(origin.y - max_drop, aim_point.y - 1.0))
	if hit.is_empty() or (hit["normal"] as Vector3).y < 0.35:
		return {}
	var p: Vector3 = hit["position"]
	var dh := p.y - origin.y
	if dh > max_height + 0.02 or dh < -max_drop:
		return {}
	var nrm: Vector3 = hit["normal"]
	# a void / big drop between the cat and the aim point makes it a gap jump
	var mid := origin.lerp(p, 0.5)
	var mid_hit := _ray_down(Vector3(mid.x, maxf(origin.y, p.y) + 0.2, mid.z), minf(origin.y, p.y) - 0.4)
	var gap := mid_hit.is_empty() or float((mid_hit["position"] as Vector3).y) < minf(origin.y, p.y) - 0.35
	var narrow := nrm.y < floor_normal_min
	return {
		"point": p, "normal": nrm if nrm.y >= floor_normal_min else Vector3.UP, "collider": hit.get("collider"),
		"angle": 0.0, "dist": d, "dh": dh, "gap": gap, "narrow": narrow,
		"interesting": absf(dh) > 0.16 or gap or narrow, "kind": &"aim",
	}


func _score(origin: Vector3, aim_dir: Vector3, aim_point: Vector3, c: Dictionary) -> float:
	var s := 0.0
	s += 2.0 * (1.0 - float(c["angle"]) / maxf(fan_half_angle, 0.01))
	var dh := float(c["dh"])
	if dh > 0.16:
		s += 1.2 + 0.25 * minf(dh, 1.2)
	elif dh < -0.16:
		s += 0.35
	if bool(c["gap"]):
		s += 0.5
	s -= 0.35 * float(c["dist"]) / maxf(max_distance, 0.1)
	if aim_point != Vector3.INF:
		var p: Vector3 = c["point"]
		s -= 4.0 * p.distance_to(aim_point)
		if bool(c.get("aim_exact", false)):
			s += 0.6
	return s


func _has_headroom(point: Vector3) -> bool:
	_shape_q.shape = _head_shape
	_shape_q.collision_mask = mask
	_shape_q.exclude = exclude
	_shape_q.margin = 0.0
	_shape_q.transform = Transform3D(Basis.IDENTITY, point + Vector3.UP * (_head_shape.height * 0.5 + 0.03))
	return space.intersect_shape(_shape_q, 1).is_empty()


func _arc_clear(origin: Vector3, v0: Vector3, t_total: float) -> bool:
	var steps := 12
	var lift := Vector3.UP * (body_height * 0.55)
	var prev := origin + lift
	for i in range(1, steps + 1):
		var t := t_total * float(i) / float(steps)
		var p := arc_point(origin, v0, gravity, t) + lift
		if i == steps:
			p = arc_point(origin, v0, gravity, t) + Vector3.UP * (body_height * 0.6)
		_ray.from = prev
		_ray.to = p
		_ray.collision_mask = mask
		_ray.exclude = exclude
		if not space.intersect_ray(_ray).is_empty():
			return false
		prev = p
	return true


func _ray_down(from: Vector3, bottom_y: float) -> Dictionary:
	_ray.from = from
	_ray.to = Vector3(from.x, bottom_y, from.z)
	_ray.collision_mask = mask
	_ray.exclude = exclude
	return space.intersect_ray(_ray)


func _sphere_down(from: Vector3, bottom_y: float) -> Dictionary:
	_shape_q.shape = _probe_sphere
	_shape_q.collision_mask = mask
	_shape_q.exclude = exclude
	_shape_q.margin = 0.0
	_shape_q.transform = Transform3D(Basis.IDENTITY, from)
	_shape_q.motion = Vector3(0.0, bottom_y - from.y, 0.0)
	var frac := space.cast_motion(_shape_q)
	_shape_q.motion = Vector3.ZERO
	if frac.size() < 2 or frac[1] >= 1.0:
		return {}
	_shape_q.transform = Transform3D(Basis.IDENTITY, from + Vector3(0.0, (bottom_y - from.y) * frac[1], 0.0))
	var info := space.get_rest_info(_shape_q)
	if info.is_empty():
		return {}
	var nrm: Vector3 = info["normal"]
	# refine the top with a ray straight down at the contact point
	var cp: Vector3 = info["point"]
	var r := _ray_down(Vector3(cp.x, from.y, cp.z), cp.y - 0.1)
	if not r.is_empty():
		return r
	return {"position": cp, "normal": nrm, "collider": instance_from_id(int(info.get("collider_id", 0)))}
