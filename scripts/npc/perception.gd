extends RefCounted
## Perception model shared by every AI that cares about Cam (owner: world-life).
##
## * Vision: cone (half-angle `fov_deg/2`, range `sight_range`) with peripheral falloff, an occlusion
##   raycast from the eye to the cat's chest and head, darkness (TimeOfDay night factor, softened
##   near light sources via `lit_bonus`), sneaking (×0.55), resting cats (×0.8) and GameState's
##   detection multiplier (stealth attribute + skills/buffs).
## * Hearing: GameEvents.player_noise(pos, loudness) heard within loudness × `hearing_range`
##   (× detection multiplier, halved through walls). `player_noise` already includes noise_mult.
## * Awareness 0..1 rises while the cat is perceived and decays otherwise. Alert levels:
##   0 UNAWARE < 0.3 ≤ SUSPICIOUS < 0.85 ≤ ALERTED. Crossing a level calls `on_level_changed`.
##
## The owner calls `update(dt)` at its AI tick rate and `notify_noise()` from the signal.

const NpcUtil := preload("res://scripts/npc/npc_util.gd")

enum Level { UNAWARE, SUSPICIOUS, ALERTED }

const SUSPICIOUS_AT := 0.3
const ALERTED_AT := 0.85

var owner: Node3D
var eye_height := 1.55
var fov_deg := 140.0
var sight_range := 14.0
## Within this radius the cat is noticed regardless of the cone (feel/peripheral).
var proximity_radius := 0.9
var hearing_range := 16.0
## Awareness gained per second at point-blank full visibility.
var sight_gain := 2.2
var hearing_gain := 1.0
var decay := 0.18
## Remember the cat for this long after losing it.
var memory_s := 6.0

var awareness := 0.0
var level: Level = Level.UNAWARE
var can_see_player := false
var visibility := 0.0
var last_seen_pos := Vector3.INF
var last_heard_pos := Vector3.INF
var last_stimulus_pos := Vector3.INF
var time_since_seen := 1e6
var time_since_heard := 1e6
var heard_this_tick := 0.0
## Ignored when false (vendors busy, sleeping dogs partially deaf…).
var enabled := true
var deafness := 0.0
## Called with (old_level, new_level).
var on_level_changed: Callable

var _exclude: Array[RID] = []


func _init(p_owner: Node3D) -> void:
	owner = p_owner
	if p_owner is CollisionObject3D:
		_exclude.append((p_owner as CollisionObject3D).get_rid())


func add_exclude(rid: RID) -> void:
	_exclude.append(rid)


func get_eye_position() -> Vector3:
	return owner.global_position + Vector3.UP * eye_height


func get_forward() -> Vector3:
	return owner.global_basis.z.normalized()


func notify_noise(pos: Vector3, loudness: float) -> void:
	if not enabled or owner == null or not owner.is_inside_tree():
		return
	var r := loudness * hearing_range * NpcUtil.detection_mult() * (1.0 - deafness)
	if r <= 0.05:
		return
	var d := get_eye_position().distance_to(pos + Vector3.UP * 0.2)
	if d > r:
		return
	var through_wall := not NpcUtil.ray(owner.get_world_3d(), get_eye_position(), pos + Vector3.UP * 0.25,
		NpcUtil.LAYER_WORLD, _exclude).is_empty()
	var strength := loudness * (1.0 - d / r) * (0.5 if through_wall else 1.0)
	heard_this_tick = maxf(heard_this_tick, strength)
	awareness = clampf(awareness + strength * hearing_gain * (1.6 if loudness > 0.6 else 1.0), 0.0, 1.0)
	last_heard_pos = pos
	last_stimulus_pos = pos
	time_since_heard = 0.0
	_refresh_level()


## Returns visibility 0..1 of `target` (a Node3D standing on the ground, ~0.25 m tall cat).
func compute_visibility(target: Node3D) -> float:
	if target == null or owner == null:
		return 0.0
	var eye := get_eye_position()
	var tp := target.global_position
	var to := tp + Vector3.UP * 0.15 - eye
	var dist := to.length()
	var mult := NpcUtil.detection_mult()
	if NpcUtil.player_is_sneaking(target):
		mult *= 0.55
	elif NpcUtil.player_is_resting(target):
		mult *= 0.8
	var night := NpcUtil.night_factor()
	var dark := 1.0 - 0.45 * night
	var rng := sight_range * mult * dark
	if dist > rng and dist > proximity_radius:
		return 0.0
	var fwd := get_forward()
	var flat_to := NpcUtil.flat(to)
	var ang := 0.0
	if flat_to.length() > 0.01:
		ang = rad_to_deg(NpcUtil.flat(fwd).normalized().angle_to(flat_to.normalized()))
	var in_close := dist <= proximity_radius * mult * 1.4
	if ang > fov_deg * 0.5 and not in_close:
		return 0.0
	# occlusion: chest and head samples
	var world := owner.get_world_3d()
	var vis_samples := 0
	for off: Vector3 in [Vector3.UP * 0.14, Vector3.UP * 0.26 + fwd * 0.0]:
		var hit := NpcUtil.ray(world, eye, tp + off, NpcUtil.SIGHT_MASK, _exclude)
		if hit.is_empty():
			vis_samples += 1
	if vis_samples == 0:
		return 0.0
	var cover := float(vis_samples) / 2.0
	var dist_f := 1.0 - clampf(dist / maxf(rng, 0.01), 0.0, 1.0)
	var periph := 1.0 - smoothstep(fov_deg * 0.25, fov_deg * 0.5, ang) * 0.6
	return clampf((0.25 + 0.75 * dist_f) * periph * cover, 0.0, 1.0)


func update(dt: float, target: Node3D) -> void:
	time_since_seen += dt
	time_since_heard += dt
	if not enabled:
		can_see_player = false
		visibility = 0.0
		awareness = maxf(awareness - decay * dt, 0.0)
		_refresh_level()
		return
	visibility = compute_visibility(target)
	can_see_player = visibility > 0.0
	if can_see_player:
		awareness = clampf(awareness + visibility * visibility * sight_gain * dt + 0.05 * dt, 0.0, 1.0)
		last_seen_pos = target.global_position
		last_stimulus_pos = last_seen_pos
		time_since_seen = 0.0
	elif heard_this_tick <= 0.0:
		var k := decay * (0.4 if time_since_seen < memory_s else 1.0)
		awareness = maxf(awareness - k * dt, 0.0)
	heard_this_tick = 0.0
	_refresh_level()


func force_awareness(v: float, pos: Vector3 = Vector3.INF) -> void:
	awareness = clampf(v, 0.0, 1.0)
	if pos != Vector3.INF:
		last_stimulus_pos = pos
	_refresh_level()


func _refresh_level() -> void:
	var nl: Level = Level.UNAWARE
	if awareness >= ALERTED_AT:
		nl = Level.ALERTED
	elif awareness >= SUSPICIOUS_AT:
		nl = Level.SUSPICIOUS
	# hysteresis: drop a level only clearly below its threshold
	if nl < level:
		if level == Level.ALERTED and awareness > ALERTED_AT - 0.25:
			nl = Level.ALERTED
		elif level == Level.SUSPICIOUS and awareness > SUSPICIOUS_AT - 0.15:
			nl = Level.SUSPICIOUS
	if nl != level:
		var old := level
		level = nl
		if on_level_changed.is_valid():
			on_level_changed.call(old, nl)


func is_alerted() -> bool:
	return level == Level.ALERTED


func is_suspicious() -> bool:
	return level >= Level.SUSPICIOUS
