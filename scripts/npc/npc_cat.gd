extends "res://scripts/npc/npc_base.gd"
## NPC cats — Mun, Bông, Ông Mướp and ambient strays (owner: world-life).
##
## Uses the real cat (assets/models/cat/cat.glb, same rig & clips as Cam) with a variant coat
## (cat_albedo_{black,white,grey_tabby,calico}.png), iris variant and the player's shell fur
## (scripts/player/fur_shells.gd, read-only reuse with LOD).
## Behaviours: wander, sit, groom, nap in the sun (sun-ray test against the Sun light), stretch,
## hiss at strangers who come too close, flee from a charging cat (strays), follow / lead Cam for
## quests (`start_follow(target)`, `lead_to(pos)`, `stop_escort()`), talk via Talkable.

enum S { IDLE, WANDER, SIT, GROOM, NAP, HISS, FLEE, FOLLOW, LEAD, PERCH }

const CAT_SCENE := "res://assets/models/cat/cat.glb"
const TEX := "res://assets/models/cat/textures/"
const FUR_SCRIPT := "res://scripts/player/fur_shells.gd"

const PROFILES := {
	&"mun": {"coat": "cat_albedo_black.png", "iris": "cat_eye_iris_green.png", "scale": 1.06, "talk": &"mun",
		"friend_flag": &"mun_friend", "hostile": 0.8, "roam": 10.0, "prefers_high": true, "pitch": 0.85},
	&"bong": {"coat": "cat_albedo_white.png", "iris": "cat_eye_iris_blue.png", "scale": 1.0, "talk": &"bong",
		"friend_flag": &"", "hostile": 0.0, "roam": 3.0, "prefers_high": false, "pitch": 1.15, "fluffy": 1.35},
	&"muop": {"coat": "cat_albedo_grey_tabby.png", "iris": "cat_eye_iris_copper.png", "scale": 1.04, "talk": &"ong_muop",
		"friend_flag": &"", "hostile": 0.0, "roam": 4.0, "prefers_high": false, "pitch": 0.82, "old": true},
}
const STRAY_COATS: Array[String] = ["cat_albedo_calico.png", "cat_albedo_grey_tabby.png", "cat_albedo_black.png",
	"cat_albedo_white.png", "cat_albedo.png"]
const STRAY_IRIS: Array[String] = ["cat_eye_iris_green.png", "cat_eye_iris_copper.png", "cat_eye_iris.png", "cat_eye_iris_blue.png"]

## Gait speeds the clips are authored for.
const WALK := 0.7
const TROT := 1.6
const RUN := 4.5

var state: S = S.IDLE
var state_t := 0.0
var dur := 5.0
var profile: Dictionary = {}
var home := Vector3.ZERO
var roam_radius := 8.0
var hostility := 0.5
var escort_target: Node3D = null
var lead_goal := Vector3.INF
var model: Node3D = null
var anim_player: AnimationPlayer = null
var fur: Node = null
var _cur_clip: StringName = &""
var _queued_clip: StringName = &""
var _rng := RandomNumberGenerator.new()
var _hiss_cd := 0.0
var _pitch := 1.0
var _sun: DirectionalLight3D = null
## Rooftop route (Mun): patrol_path points walked with direct steering.
var route: PackedVector3Array = PackedVector3Array()
var _route_i := 0


func _setup() -> void:
	_rng.randomize()
	npc_kind = &"cat"
	set_meta(&"npc_kind", "cat")
	add_to_group(&"npc_cat")
	body_radius = 0.12
	body_height = 0.3
	walk_speed = WALK
	run_speed = RUN
	turn_rate = 6.0
	arrive_radius = 0.2
	for c: Node in get_children():
		if c is CollisionShape3D:
			var cs := c as CollisionShape3D
			var sph := SphereShape3D.new()
			sph.radius = 0.12
			cs.shape = sph
			cs.position = Vector3(0, 0.13, 0)
	if nav != null:
		nav.radius = 0.15
		nav.height = 0.3
	perception.eye_height = 0.22
	perception.fov_deg = 200.0
	perception.sight_range = 9.0
	perception.proximity_radius = 0.7
	profile = PROFILES.get(npc_id, {})
	if profile.is_empty():
		profile = {"coat": STRAY_COATS[_rng.randi() % STRAY_COATS.size()], "iris": STRAY_IRIS[_rng.randi() % STRAY_IRIS.size()],
			"scale": _rng.randf_range(0.88, 1.0), "talk": &"", "friend_flag": &"", "hostile": _rng.randf_range(0.3, 0.9),
			"roam": 9.0, "prefers_high": false, "pitch": _rng.randf_range(0.95, 1.12)}
	hostility = float(profile["hostile"])
	roam_radius = float(profile["roam"])
	_pitch = float(profile.get("pitch", 1.0))
	_build_model()
	if StringName(profile["talk"]) != &"":
		add_talkable(StringName(profile["talk"]), StringName(profile["talk"]), 1.2, Vector3(0, 0.15, 0.1))


func _build_model() -> void:
	if not ResourceLoader.exists(CAT_SCENE):
		make_visual("human", {"height": 0.3})    # cannot happen in a complete checkout
		return
	var vis := Node3D.new()
	vis.name = "Visual"
	add_child(vis)
	visual = null    # we drive the AnimationPlayer directly
	model = (load(CAT_SCENE) as PackedScene).instantiate() as Node3D
	model.name = "Model"
	var sc := float(profile["scale"])
	model.scale = Vector3.ONE * sc
	vis.add_child(model)
	anim_player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if anim_player != null:
		for a: StringName in [&"idle", &"idle_look", &"walk", &"trot", &"run", &"sneak", &"sit_idle", &"sleep", &"groom",
				&"knead", &"scratch", &"fall", &"balance_walk", &"sneak_idle"]:
			if anim_player.has_animation(a):
				anim_player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
		anim_player.playback_default_blend_time = 0.3
		anim_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
		anim_player.animation_finished.connect(_on_clip_finished)
	_apply_coat()
	if ResourceLoader.exists(FUR_SCRIPT):
		var fs := load(FUR_SCRIPT) as Script
		fur = fs.new() as Node
		fur.name = "Fur"
		var coat_path := TEX + str(profile["coat"])
		if ResourceLoader.exists(coat_path):
			fur.set(&"albedo_override", load(coat_path))
		fur.set(&"use_game_state_wetness", false)
		fur.set(&"enable_lod", true)
		if profile.has("fluffy"):
			fur.set(&"fur_length", 0.02 * float(profile["fluffy"]))
		add_child(fur)
		fur.call(&"attach_to_model", model, self)
	_play_clip(&"idle")


func _apply_coat() -> void:
	var coat_path := TEX + str(profile["coat"])
	var iris_path := TEX + str(profile["iris"])
	for mi: Node in model.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.name == "CatBody" and ResourceLoader.exists(coat_path):
			var src := m.mesh.surface_get_material(0) as StandardMaterial3D
			if src != null:
				var nm := src.duplicate() as StandardMaterial3D
				nm.albedo_texture = load(coat_path)
				m.set_surface_override_material(0, nm)
		elif m.name == "CatEyes" and ResourceLoader.exists(iris_path):
			var src2 := m.mesh.surface_get_material(0) as StandardMaterial3D
			if src2 != null:
				var nm2 := src2.duplicate() as StandardMaterial3D
				nm2.albedo_texture = load(iris_path)
				if nm2.emission_enabled:
					nm2.emission_texture = nm2.albedo_texture
				m.set_surface_override_material(0, nm2)


func set_route(path: Path3D) -> void:
	route = PackedVector3Array()
	if path == null or path.curve == null:
		return
	for i in path.curve.point_count:
		route.append(path.to_global(path.curve.get_point_position(i)))


func init_from_marker(m: Node3D) -> void:
	home = m.global_position
	if m.has_meta(&"roam_radius"):
		roam_radius = float(m.get_meta(&"roam_radius"))
	teleport_to(m.global_position, m.global_rotation.y)
	_enter(S.SIT if _rng.randf() < 0.5 else S.IDLE, _rng.randf_range(3.0, 10.0))


# ------------------------------------------------------------------------------------------
# Animation (cat.glb clips)
# ------------------------------------------------------------------------------------------

func _play_clip(c: StringName, then: StringName = &"") -> void:
	_queued_clip = then
	if anim_player == null or not anim_player.has_animation(c):
		return
	if c == _cur_clip and anim_player.is_playing():
		return
	_cur_clip = c
	anim_player.play(c)


func _on_clip_finished(c: StringName) -> void:
	if _queued_clip != &"" and c == _cur_clip:
		var q := _queued_clip
		_queued_clip = &""
		_play_clip(q)


func play_anim(a: StringName) -> void:
	# NpcBase API → cat clips
	var map := {&"talk": &"sit_idle", &"idle": &"idle", &"walk": &"walk", &"run": &"run"}
	_play_clip(StringName(map.get(a, a)))


func play_anim_for(a: StringName, _seconds: float) -> void:
	play_anim(a)


func _locomotion_clip() -> void:
	var v := NpcUtil.flat(velocity).length()
	if anim_player == null:
		return
	if v < 0.08:
		return
	var clip := &"walk"
	var authored := WALK
	if v > 2.6:
		clip = &"run"
		authored = RUN
	elif v > 1.05:
		clip = &"trot"
		authored = TROT
	_play_clip(clip)
	anim_player.speed_scale = clampf(v / authored, 0.6, 1.6)


# ------------------------------------------------------------------------------------------
# AI
# ------------------------------------------------------------------------------------------

func _enter(s: S, duration := 5.0) -> void:
	state = s
	state_t = 0.0
	dur = duration
	if anim_player != null:
		anim_player.speed_scale = 1.0
	match s:
		S.SIT:
			stop_moving()
			_play_clip(&"sit_down", &"sit_idle")
		S.GROOM:
			stop_moving()
			_play_clip(&"groom")
		S.NAP:
			stop_moving()
			_play_clip(&"lie_down", &"sleep")
		S.HISS:
			stop_moving()
			_play_clip(&"hiss", &"idle")
		S.IDLE:
			stop_moving()
			_play_clip(&"idle_look" if _rng.randf() < 0.4 else &"idle")


func is_friend() -> bool:
	var flag := StringName(profile.get("friend_flag", &""))
	var gs := get_node_or_null(^"/root/GameState")
	if flag != &"" and gs != null and gs.has_method(&"get_flag"):
		return bool(gs.call(&"get_flag", flag, false))
	return hostility < 0.2


func _think(dt: float) -> void:
	state_t += dt
	_hiss_cd = maxf(_hiss_cd - dt, 0.0)
	if in_dialogue:
		var p0 := get_player()
		if p0 != null:
			face_point = p0.global_position
		if state != S.SIT:
			_enter(S.SIT, 999.0)
		return
	var player := get_player()
	if player != null and state not in [S.FOLLOW, S.LEAD, S.FLEE, S.HISS]:
		_react_to_player(player)
	match state:
		S.IDLE:
			if state_t > dur:
				_choose_next()
		S.WANDER:
			_locomotion_clip()
			if arrived(0.25) or state_t > 25.0:
				_enter(S.IDLE, _rng.randf_range(2.0, 6.0))
		S.SIT, S.GROOM:
			if state_t > dur:
				_play_clip(&"stand_up")
				_enter(S.IDLE, 1.2)
		S.NAP:
			if state_t > dur:
				_play_clip(&"stretch", &"idle")
				_enter(S.IDLE, 2.5)
		S.HISS:
			if player != null:
				face_point = player.global_position
			if state_t > 1.6:
				# strays back off after hissing, gang leaders hold their ground
				if hostility > 0.6 and npc_id == &"" and player != null:
					_flee_from(player.global_position)
				else:
					_enter(S.SIT, 6.0)
		S.FLEE:
			_locomotion_clip()
			if arrived(0.3) or state_t > 6.0:
				_enter(S.IDLE, 3.0)
		S.FOLLOW:
			_do_follow()
		S.LEAD:
			_do_lead()


func _choose_next() -> void:
	var r := _rng.randf()
	var h := NpcUtil.hour()
	if has_meta(&"nap_after") and bool(get_meta(&"nap_after")):
		set_meta(&"nap_after", false)
		_enter(S.NAP, _rng.randf_range(30.0, 90.0))
		return
	var sleepy := (h >= 12.0 and h < 15.5) or h >= 23.0 or h < 5.0 or profile.has("old")
	if sleepy and r < 0.45:
		var spot := _find_sunny_spot() if (h > 6.5 and h < 17.5 and not bool(profile.get("prefers_high", false))) else home
		if NpcUtil.flat_dist(spot, global_position) > 0.6:
			go_to(spot, WALK)
			_enter(S.WANDER)
			# nap once there
			dur = 0.0
			set_meta(&"nap_after", true)
			return
		_enter(S.NAP, _rng.randf_range(30.0, 90.0))
		return
	if r < 0.45 and not route.is_empty():
		_route_i = (_route_i + 1) % route.size()
		direct_steering = true
		go_to(route[_route_i], WALK if _rng.randf() < 0.75 else TROT)
		_enter(S.WANDER)
	elif r < 0.35 and bool(profile.get("prefers_high", false)):
		# gang leader keeps his high ground: short pacing along it instead of wandering off
		_enter(S.GROOM if _rng.randf() < 0.5 else S.SIT, _rng.randf_range(6.0, 14.0))
	elif r < 0.35:
		var dest := NpcUtil.random_nav_point(get_world_3d(), home, roam_radius)
		go_to(dest, WALK if _rng.randf() < 0.8 else TROT)
		_enter(S.WANDER)
	elif r < 0.6:
		_enter(S.SIT, _rng.randf_range(6.0, 20.0))
	elif r < 0.8:
		_enter(S.GROOM, _rng.randf_range(5.0, 12.0))
	else:
		_enter(S.IDLE, _rng.randf_range(3.0, 7.0))


func _react_to_player(player: Node3D) -> void:
	var d := NpcUtil.flat_dist(player.global_position, global_position)
	var pv := NpcUtil.player_velocity(player)
	var approaching := pv.length() > 0.4 and NpcUtil.flat(pv).normalized().dot(NpcUtil.flat(global_position - player.global_position).normalized()) > 0.6
	if d < 4.0 and perception.can_see_player and state in [S.IDLE, S.SIT, S.GROOM]:
		face_point = player.global_position
	if is_friend():
		return
	# strays bolt from a charging cat
	if npc_id == &"" and approaching and pv.length() > 2.5 and d < 3.0:
		_flee_from(player.global_position)
		return
	if d < 1.1 and _hiss_cd <= 0.0 and _rng.randf() < hostility and (state != S.NAP or d < 0.6):
		_hiss_cd = 8.0
		face_point = player.global_position
		_enter(S.HISS)
		var am := get_node_or_null(^"/root/AudioManager")
		if am != null and am.has_method(&"play_meow"):
			am.call(&"play_meow", &"hiss", global_position + Vector3.UP * 0.2, _pitch)
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null:
			ge.npc_alerted.emit(self, 0.6)


func _flee_from(p: Vector3) -> void:
	var away := NpcUtil.flat(global_position - p).normalized()
	if away.length() < 0.1:
		away = Vector3.FORWARD
	var dest := NpcUtil.random_nav_point(get_world_3d(), global_position + away * 6.0, 1.5)
	go_to(dest, RUN * 0.85)
	_enter(S.FLEE)


func _find_sunny_spot() -> Vector3:
	if _sun == null:
		for n: Node in NpcUtil.nodes_in(get_tree(), &"sun"):
			if n is DirectionalLight3D:
				_sun = n
		if _sun == null:
			var root := get_tree().current_scene if get_tree().current_scene != null else get_tree().root
			_sun = root.find_child("Sun", true, false) as DirectionalLight3D
	if _sun == null:
		return home
	var to_sun := _sun.global_basis.z.normalized()    # light shines along -Z
	for i in 8:
		var p := NpcUtil.random_nav_point(get_world_3d(), home, roam_radius)
		var hit := NpcUtil.ray(get_world_3d(), p + Vector3.UP * 0.15, p + to_sun * 60.0, NpcUtil.SIGHT_MASK)
		if hit.is_empty():
			return p
	return home


# --- escort (quests) ----------------------------------------------------------------------------

## Follows `target` (usually Cam) at ~1 m until stop_escort().
func start_follow(target: Node3D) -> void:
	escort_target = target
	_enter(S.FOLLOW)


## Walks ahead of Cam to `goal`, waiting whenever Cam lags more than 4 m. Emits
## GameEvents.area_entered("<npc_id>_lead_done") on arrival (quests can listen / report).
func lead_to(goal: Vector3, target: Node3D = null) -> void:
	lead_goal = goal
	escort_target = target if target != null else get_player()
	_enter(S.LEAD)


func stop_escort() -> void:
	escort_target = null
	lead_goal = Vector3.INF
	_enter(S.IDLE, 2.0)


func _do_follow() -> void:
	if escort_target == null or not is_instance_valid(escort_target):
		stop_escort()
		return
	var d := NpcUtil.flat_dist(escort_target.global_position, global_position)
	if d > 1.3:
		var speed := WALK if d < 2.5 else (TROT if d < 6.0 else RUN * 0.8)
		go_to(escort_target.global_position, speed)
		_locomotion_clip()
	else:
		stop_moving()
		face_point = escort_target.global_position
		_play_clip(&"idle")


func _do_lead() -> void:
	if lead_goal == Vector3.INF:
		stop_escort()
		return
	var p := escort_target
	if NpcUtil.flat_dist(global_position, lead_goal) < 0.5:
		stop_moving()
		_play_clip(&"sit_down", &"sit_idle")
		var ge := get_node_or_null(^"/root/GameEvents")
		if ge != null:
			ge.area_entered.emit(StringName(String(npc_id) + "_lead_done"))
		lead_goal = Vector3.INF
		_enter(S.SIT, 20.0)
		return
	if p != null and NpcUtil.flat_dist(p.global_position, global_position) > 4.0:
		stop_moving()
		face_point = p.global_position
		_play_clip(&"sit_idle" if state_t > 3.0 else &"idle_look")
		if fmod(state_t, 6.0) < 0.15:
			var am := get_node_or_null(^"/root/AudioManager")
			if am != null and am.has_method(&"play_meow"):
				am.call(&"play_meow", &"chirp", global_position + Vector3.UP * 0.2, _pitch)
		return
	go_to(lead_goal, TROT * 0.8)
	_locomotion_clip()


func _physics_process(delta: float) -> void:
	super._physics_process(delta)
	if anim_player != null and state in [S.WANDER, S.FLEE, S.FOLLOW, S.LEAD]:
		if NpcUtil.flat(velocity).length() < 0.06 and _cur_clip in [&"walk", &"trot", &"run"]:
			_play_clip(&"idle")
			anim_player.speed_scale = 1.0


func set_lod(l: Lod, interval: float) -> void:
	super.set_lod(l, interval)
	var vis := get_node_or_null(^"Visual") as Node3D
	if vis != null:
		vis.visible = l != Lod.ASLEEP
	if anim_player != null:
		anim_player.active = l <= Lod.MID


func on_swiped(by: Node) -> void:
	if by is Node3D and not is_friend():
		_hiss_cd = 0.0
		_enter(S.HISS)
		var am := get_node_or_null(^"/root/AudioManager")
		if am != null and am.has_method(&"play_meow"):
			am.call(&"play_meow", &"hiss", global_position + Vector3.UP * 0.2, _pitch)
