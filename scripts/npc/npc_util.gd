extends RefCounted
## Shared static helpers for the living-neighbourhood AI (owner: world-life).
## Use via `const NpcUtil := preload("res://scripts/npc/npc_util.gd")`.

const LAYER_WORLD := 1
const LAYER_PLAYER := 1 << 1
const LAYER_NPC := 1 << 2
const LAYER_PROPS := 1 << 3
const LAYER_INTERACTABLE := 1 << 4
const LAYER_CLIMBABLE := 1 << 5
const LAYER_WATER := 1 << 6
const LAYER_VEHICLES := 1 << 7
const LAYER_CAMERA_BLOCKER := 1 << 8
const LAYER_TRIGGERS := 1 << 9
## What blocks line of sight (walls, buildings, props, parked/moving vehicles).
const SIGHT_MASK := LAYER_WORLD | LAYER_PROPS | LAYER_VEHICLES | LAYER_CLIMBABLE
const GROUND_MASK := LAYER_WORLD | LAYER_CLIMBABLE | LAYER_PROPS

## Max simultaneous agents per graphics quality.
const QUALITY_CAPS := {
	"low": {"pedestrians": 8, "vehicles": 6, "pigeons": 8, "strays": 2, "mice": 2, "koi": 6, "geckos": 2, "sparrows": 6},
	"medium": {"pedestrians": 14, "vehicles": 10, "pigeons": 12, "strays": 3, "mice": 3, "koi": 9, "geckos": 4, "sparrows": 9},
	"high": {"pedestrians": 22, "vehicles": 16, "pigeons": 16, "strays": 4, "mice": 4, "koi": 12, "geckos": 6, "sparrows": 12},
	"ultra": {"pedestrians": 32, "vehicles": 24, "pigeons": 22, "strays": 4, "mice": 6, "koi": 16, "geckos": 8, "sparrows": 16},
}

static var _warned: Dictionary = {}


static func quality() -> String:
	var q := "high"
	var s := _autoload("Settings")
	if s != null and s.has_method(&"get_value"):
		q = str(s.call(&"get_value", "graphics", "quality", "high"))
	return q if QUALITY_CAPS.has(q) else "high"


static func cap(kind: String) -> int:
	return int((QUALITY_CAPS[quality()] as Dictionary).get(kind, 8))


static func _autoload(n: String) -> Node:
	var ml := Engine.get_main_loop() as SceneTree
	if ml == null or ml.root == null:
		return null
	return ml.root.get_node_or_null(n)


static func get_player(from: Node) -> Node3D:
	if from == null or not from.is_inside_tree():
		return null
	return from.get_tree().get_first_node_in_group(&"player") as Node3D


## Planar (XZ) distance.
static func flat_dist(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


static func flat(v: Vector3) -> Vector3:
	return Vector3(v.x, 0.0, v.z)


## Yaw (radians) whose basis makes +Z face `dir` (model front convention).
static func yaw_of(dir: Vector3) -> float:
	return atan2(dir.x, dir.z)


static func basis_facing(dir: Vector3) -> Basis:
	var d := flat(dir)
	if d.length_squared() < 1e-6:
		return Basis.IDENTITY
	return Basis.looking_at(d.normalized(), Vector3.UP, true)


## Moves angle `a` toward `b` by at most `step` (radians), wrapping correctly.
static func approach_angle(a: float, b: float, step: float) -> float:
	var diff := wrapf(b - a, -PI, PI)
	if absf(diff) <= step:
		return b
	return a + signf(diff) * step


static func ray(world: World3D, from: Vector3, to: Vector3, mask: int, exclude: Array[RID] = []) -> Dictionary:
	if world == null:
		return {}
	var q := PhysicsRayQueryParameters3D.create(from, to, mask, exclude)
	q.collide_with_areas = false
	return world.direct_space_state.intersect_ray(q)


## Ground height under `p` (searching from p.y+up down to p.y-down). Returns NAN when nothing hit.
static func ground_y(world: World3D, p: Vector3, up := 1.0, down := 6.0, mask := GROUND_MASK) -> float:
	var hit := ray(world, p + Vector3.UP * up, p - Vector3.UP * down, mask)
	if hit.is_empty():
		return NAN
	return (hit["position"] as Vector3).y


## Detection multiplier from GameState skills/attributes/buffs (lower = stealthier).
static func detection_mult() -> float:
	var gs := _autoload("GameState")
	if gs == null:
		return 1.0
	var m := 1.0
	if gs.has_method(&"get_modifier"):
		m = float(gs.call(&"get_modifier", &"detection_mult"))
	# (stealth attribute, skills and buffs are already folded into the modifier)
	return clampf(m, 0.15, 2.0)


static func modifier(name: StringName, default := 0.0) -> float:
	var gs := _autoload("GameState")
	if gs == null or not gs.has_method(&"get_modifier"):
		return default
	return float(gs.call(&"get_modifier", name))


static func has_ability(name: StringName) -> bool:
	var gs := _autoload("GameState")
	return gs != null and gs.has_method(&"has_ability") and bool(gs.call(&"has_ability", name))


## Cam tries to catch prey of `kind`. Returns true on success (and registers the catch).
static func try_catch(kind: StringName, difficulty := 0.0) -> bool:
	if kind in [&"pigeon", &"sparrow", &"crow"] and not has_ability(&"catch_birds"):
		return false
	var chance := clampf(modifier(&"catch_chance", 0.3) - difficulty, 0.02, 0.98)
	if randf() >= chance:
		return false
	var gs := _autoload("GameState")
	if gs != null and gs.has_method(&"register_prey_catch"):
		gs.call(&"register_prey_catch", kind)
	return true


static func attribute(name: StringName) -> int:
	var gs := _autoload("GameState")
	if gs == null:
		return 1
	if gs.has_method(&"get_effective_attribute"):
		return int(gs.call(&"get_effective_attribute", name))
	if gs.has_method(&"get_attribute"):
		return int(gs.call(&"get_attribute", name))
	return 1


static func player_is_sneaking(p: Node) -> bool:
	if p == null:
		return false
	if p.has_method(&"is_sneaking") and bool(p.call(&"is_sneaking")):
		return true
	if p.has_method(&"is_crawling") and bool(p.call(&"is_crawling")):
		return true
	if p.has_method(&"get_state"):
		var s := String(p.call(&"get_state"))
		return s.begins_with("sneak") or s == "crawl" or s == "crouch"
	return false


static func player_is_resting(p: Node) -> bool:
	if p == null or not p.has_method(&"get_state"):
		return false
	var s := String(p.call(&"get_state"))
	return s in ["sit", "sit_idle", "lie", "lie_down", "sleep", "rest", "groom", "nap"]


static func player_velocity(p: Node) -> Vector3:
	if p is CharacterBody3D:
		return (p as CharacterBody3D).velocity
	if p != null and "velocity" in p:
		var v: Variant = p.get("velocity")
		if v is Vector3:
			return v
	return Vector3.ZERO


static func night_factor() -> float:
	var t := _autoload("TimeOfDay")
	if t != null and t.has_method(&"get_night_factor"):
		return clampf(float(t.call(&"get_night_factor")), 0.0, 1.0)
	return 0.0


static func hour() -> float:
	var t := _autoload("TimeOfDay")
	if t != null and "hour" in t:
		return float(t.get("hour"))
	return 12.0


static func weather() -> StringName:
	var gs := _autoload("GameState")
	if gs != null and gs.has_method(&"get_weather"):
		return StringName(gs.call(&"get_weather"))
	return &"clear"


static func rain_amount() -> float:
	var w := weather()
	if w != &"rain" and w != &"storm":
		return 0.0
	var gs := _autoload("GameState")
	if gs != null and gs.has_method(&"get_weather_intensity"):
		return clampf(float(gs.call(&"get_weather_intensity")), 0.2, 1.0)
	return 0.7


static func sfx(name: StringName, pos: Vector3, volume_db := 0.0, pitch_jitter := 0.06) -> void:
	var am := _autoload("AudioManager")
	if am != null and am.has_method(&"play_sfx"):
		am.call(&"play_sfx", name, pos, volume_db, pitch_jitter)


static func sfx_pitched(name: StringName, pos: Vector3, volume_db: float, pitch: float) -> void:
	var am := _autoload("AudioManager")
	if am == null:
		return
	if am.has_method(&"play_at"):
		am.call(&"play_at", name, pos, volume_db, pitch, 0.05)
	elif am.has_method(&"play_sfx"):
		am.call(&"play_sfx", name, pos, volume_db, 0.05)


static func loop(name: StringName, target: Node3D, volume_db := 0.0, pitch := 1.0, doppler := false) -> AudioStreamPlayer3D:
	var am := _autoload("AudioManager")
	if am != null and am.has_method(&"play_loop"):
		return am.call(&"play_loop", name, target, volume_db, pitch, doppler) as AudioStreamPlayer3D
	return null


static func stop_loop(p: AudioStreamPlayer3D, fade := 0.3) -> void:
	if p == null or not is_instance_valid(p):
		return
	var am := _autoload("AudioManager")
	if am != null and am.has_method(&"stop_loop"):
		am.call(&"stop_loop", p, fade)
	else:
		p.stop()


static func subtitle(speaker_key: String, text_key: String, duration := 2.5) -> void:
	var ge := _autoload("GameEvents")
	if ge != null and ge.has_signal(&"subtitle_requested"):
		var tr_obj := Engine.get_main_loop() as SceneTree
		var sp := speaker_key
		var tx := text_key
		if tr_obj != null:
			sp = tr_obj.root.tr(speaker_key) if speaker_key != "" else ""
			tx = tr_obj.root.tr(text_key)
		ge.emit_signal(&"subtitle_requested", sp, tx, duration)


## Small knock-back + damage to the cat (never lethal on its own: clamps at 1 HP by default).
static func hurt_player(player: Node, amount: float, source: StringName, push: Vector3, allow_faint := false) -> void:
	if player == null:
		return
	var gs := _autoload("GameState")
	if gs != null and gs.has_method(&"get_stat"):
		var hp := float(gs.call(&"get_stat", &"health"))
		var dmg := amount if allow_faint else minf(amount, maxf(hp - 1.0, 0.0))
		if dmg > 0.0:
			gs.call(&"modify_stat", &"health", -dmg)
		var ge := _autoload("GameEvents")
		if ge != null:
			ge.emit_signal(&"player_damaged", dmg, source)
	if player.has_method(&"apply_knockback"):
		player.call(&"apply_knockback", push)
	elif player is CharacterBody3D:
		var cb := player as CharacterBody3D
		cb.velocity += push


static func warn_once(key: String, msg: String) -> void:
	if _warned.has(key):
		return
	_warned[key] = true
	push_warning(msg)


static func meta_or(n: Node, key: StringName, default: Variant) -> Variant:
	if n != null and n.has_meta(key):
		return n.get_meta(key)
	return default


## Random point on the navigation map near `center` (falls back to a jittered centre).
static func random_nav_point(world: World3D, center: Vector3, radius: float) -> Vector3:
	var p := center + Vector3(randf_range(-radius, radius), 0.0, randf_range(-radius, radius))
	if world == null:
		return p
	var map := world.navigation_map
	if NavigationServer3D.map_get_iteration_id(map) == 0:
		return p
	return NavigationServer3D.map_get_closest_point(map, p)


static func nav_ready(world: World3D) -> bool:
	return world != null and NavigationServer3D.map_get_iteration_id(world.navigation_map) > 0 \
		and NavigationServer3D.map_get_regions(world.navigation_map).size() > 0
