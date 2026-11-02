extends "res://scripts/npc/npc_base.gd"
## Pedestrians and named humans (owner: world-life).
##
## Ambient people follow a daily routine driven by TimeOfDay (commute/stroll, shop, sit on low
## stools, chat in pairs, wait, look at things, go home at night) using `pedestrian_poi` markers
## claimed through the LifeDirector. In rain most open umbrellas; the rest hurry to `shelter`s.
## They react to Cam: stop and look, crouch and pet if charmed (Charm attribute + a meow nearby),
## shoo the cat when mischief happens nearby (knocked-off objects, swipes, stolen food).
##
## Named humans (role = vendor | kid): ba_tu (tea stall), co_hoa (fish stall), chu_sau (bánh mì
## cart) stay at their station during work hours; bin (kid) roams near the lake / his patrol path.
## They carry a systems Talkable (dialogue id = npc id, see tests/fixtures/story/dialogue).

enum S { IDLE, TRAVEL, ACTIVITY, LOOK_CAT, APPROACH_PET, PET, SHOO, SHELTER, GO_HOME, STATION, ROAM }

const NAMED := {
	&"ba_tu": {"role": "vendor", "female": true, "elder": true, "height": 1.52, "shirt": Color(0.42, 0.5, 0.62),
		"pants": Color(0.12, 0.12, 0.13), "hat": "", "station_anim": &"sit_idle", "hours": Vector2(5.5, 23.0),
		"model_names": ["ba_tu", "ped_elder_woman", "ped_"]},
	&"co_hoa": {"role": "vendor", "female": true, "height": 1.56, "shirt": Color(0.86, 0.6, 0.62), "pants": Color(0.25, 0.24, 0.3),
		"hat": "non_la", "apron": Color(0.25, 0.42, 0.55), "station_anim": &"sell", "hours": Vector2(4.5, 19.0),
		"model_names": ["co_hoa", "ped_shopper", "ped_"]},
	&"chu_sau": {"role": "vendor", "female": false, "height": 1.68, "shirt": Color(0.93, 0.93, 0.9), "pants": Color(0.3, 0.27, 0.22),
		"hat": "cap", "apron": Color(0.85, 0.82, 0.75), "station_anim": &"sell", "hours": Vector2(6.0, 22.0),
		"model_names": ["chu_sau", "ped_elder_man", "ped_"]},
	&"bin": {"role": "kid", "female": false, "height": 1.22, "girth": 0.85, "shirt": Color(0.95, 0.75, 0.15), "pants": Color(0.2, 0.3, 0.55),
		"shorts": true, "hat": "", "station_anim": &"idle", "hours": Vector2(7.0, 20.0),
		"model_names": ["bin", "ped_student", "ped_"]},
}

const UMBRELLA_COLORS: Array[Color] = [Color(0.12, 0.18, 0.42), Color(0.55, 0.08, 0.1), Color(0.1, 0.1, 0.1),
	Color(0.2, 0.45, 0.3), Color(0.85, 0.7, 0.2), Color(0.6, 0.35, 0.6)]

var role := "ambient"
var state: S = S.IDLE
var state_t := 0.0
var activity := &""
var poi: Node3D = null
var home_pos := Vector3.ZERO
var station_xform := Transform3D.IDENTITY
var station_anim: StringName = &"idle"
var work_hours := Vector2(0.0, 24.0)
var roam_path: Path3D = null
var roam_radius := 10.0
var chat_partner: Node3D = null
var personality := 0.5        # 0 shy .. 1 cat lover
var umbrella_user := true
var _activity_time := 0.0
var _pet_cooldown := 0.0
var _look_cooldown := 0.0
var _shoo_cooldown := 0.0
var _pet_target := Vector3.ZERO
var _rng := RandomNumberGenerator.new()
var _rain_checked := -1.0
var _sitting_offset := Vector3.ZERO
var _petted_today: Dictionary = {}


func _setup() -> void:
	_rng.randomize()
	personality = _rng.randf()
	umbrella_user = _rng.randf() < 0.75
	perception.eye_height = 1.5
	perception.fov_deg = 150.0
	perception.sight_range = 9.0
	perception.hearing_range = 10.0
	perception.sight_gain = 1.2
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_meowed.connect(_on_player_meowed)
		ge.object_knocked_off.connect(_on_object_knocked_off)
	var opts: Dictionary = {"seed": _rng.randi()}
	if NAMED.has(npc_id):
		var cfg: Dictionary = NAMED[npc_id]
		role = str(cfg["role"])
		opts.merge(cfg, true)
		station_anim = cfg["station_anim"]
		work_hours = cfg["hours"]
		personality = 0.9 if role == "kid" else 0.6
		umbrella_user = true
	else:
		opts["model_names"] = ["ped_", "human_", "pedestrian_"]
		if _rng.randf() < 0.18:
			opts["hat"] = "non_la"
		elif _rng.randf() < 0.15:
			opts["hat"] = "cap"
		if _rng.randf() < 0.15:
			opts["elder"] = true
	if role == "kid":
		walk_speed = 1.1
		run_speed = 3.2
		body_height = 1.2
	make_visual("human", opts)
	if npc_id != &"":
		var dlg := StringName(str(NpcUtil.meta_or(self, &"dialogue_id", String(npc_id))))
		add_talkable(dlg, npc_id, 1.8 if role == "vendor" else 1.6, Vector3(0, 0.35, 0.25))


## Configures from a marker (npc_spawn with npc_id, or a pedestrian spawn).
func init_from_marker(m: Node3D) -> void:
	home_pos = m.global_position
	station_xform = m.global_transform
	if m.has_meta(&"work_hours"):
		var wh: Variant = m.get_meta(&"work_hours")
		if wh is Vector2:
			work_hours = wh
	if m.has_meta(&"roam_radius"):
		roam_radius = float(m.get_meta(&"roam_radius"))
	teleport_to(m.global_position, m.global_rotation.y)
	if role == "vendor":
		_enter(S.STATION)
	elif role == "kid":
		_enter(S.ROAM)


# ------------------------------------------------------------------------------------------
# AI
# ------------------------------------------------------------------------------------------

func _think(dt: float) -> void:
	state_t += dt
	_pet_cooldown = maxf(_pet_cooldown - dt, 0.0)
	_look_cooldown = maxf(_look_cooldown - dt, 0.0)
	_shoo_cooldown = maxf(_shoo_cooldown - dt, 0.0)
	if in_dialogue:
		var pl := get_player()
		if pl != null:
			face_point = pl.global_position
			look_at_point(pl.global_position)
		return
	_update_weather()
	if role != "ambient":
		_update_named_presence()
		if not active:
			return
	var player := get_player()
	_cat_awareness(player)
	match state:
		S.IDLE:
			play_anim(&"idle")
			if state_t > 0.5:
				_choose_next()
		S.TRAVEL:
			play_anim(&"run" if desired_speed > walk_speed * 1.6 else &"walk")
			if arrived(0.45):
				_arrive_at_poi()
			elif state_t > 90.0:
				_release_poi()
				_enter(S.IDLE)
		S.ACTIVITY:
			_do_activity(dt)
		S.LOOK_CAT:
			stop_moving()
			if player != null:
				face_point = player.global_position
				look_at_point(player.global_position)
			play_anim(&"idle")
			if state_t > 2.8 or player == null or not perception.can_see_player:
				look_at_point(Vector3.INF)
				face_point = Vector3.INF
				_resume()
		S.APPROACH_PET:
			if player == null:
				_resume()
				return
			var to_cat := NpcUtil.flat(player.global_position - global_position)
			var d := to_cat.length()
			var reach := 0.75 if (visual != null and bool(visual.get(&"is_standin"))) else 0.5
			if d < reach:
				stop_moving()
				face_point = player.global_position
				_pet_target = player.global_position
				_enter(S.PET)
			elif state_t > 8.0 or d > 6.0:
				_resume()
			else:
				go_to(player.global_position - to_cat.normalized() * (reach - 0.12), walk_speed * 0.8)
				play_anim(&"walk")
		S.PET:
			stop_moving()
			face_point = _pet_target
			play_anim(&"pet_cat")
			look_at_point(_pet_target)
			if player != null and NpcUtil.flat_dist(player.global_position, _pet_target) > 0.9:
				_resume()     # the cat walked away
			elif state_t > 4.0:
				_finish_pet()
		S.SHOO:
			stop_moving()
			if player != null:
				face_point = player.global_position
				look_at_point(player.global_position)
			play_anim(&"shoo")
			if state_t > 2.4:
				look_at_point(Vector3.INF)
				_resume()
		S.SHELTER:
			if arrived(0.6):
				stop_moving()
				play_anim(&"idle")
				if NpcUtil.rain_amount() <= 0.0 and state_t > 5.0:
					_enter(S.IDLE)
			else:
				play_anim(&"run")
		S.GO_HOME:
			play_anim(&"walk")
			if arrived(0.8) or state_t > 120.0:
				if director != null and director.has_method(&"despawn"):
					director.call(&"despawn", self)
		S.STATION:
			_do_station(dt)
		S.ROAM:
			_do_roam(dt)


func _enter(s: S) -> void:
	state = s
	state_t = 0.0


func _resume() -> void:
	look_at_point(Vector3.INF)
	face_point = Vector3.INF
	match role:
		"vendor":
			_enter(S.STATION)
		"kid":
			_enter(S.ROAM)
		_:
			if poi != null and is_instance_valid(poi) and _activity_time > 0.0:
				_enter(S.TRAVEL)
				go_to(_poi_stand_point(), walk_speed)
			else:
				_enter(S.IDLE)


# --- routine ------------------------------------------------------------------------------

func _hour_weights(h: float) -> Dictionary:
	if h >= 23.0 or h < 5.0:
		return {"home": 1.0}
	if h < 8.0:
		return {"walk": 0.5, "sit": 0.35, "shop": 0.1, "look": 0.05}
	if h < 11.0:
		return {"shop": 0.35, "walk": 0.3, "chat": 0.2, "look": 0.1, "wait": 0.05}
	if h < 13.5:
		return {"sit": 0.5, "chat": 0.2, "walk": 0.25, "shop": 0.05}
	if h < 17.0:
		return {"walk": 0.35, "shop": 0.25, "chat": 0.2, "wait": 0.1, "look": 0.1}
	if h < 21.0:
		return {"sit": 0.4, "chat": 0.3, "walk": 0.2, "shop": 0.1}
	return {"home": 0.55, "sit": 0.3, "chat": 0.15}


func _choose_next() -> void:
	var w := _hour_weights(NpcUtil.hour())
	if NpcUtil.rain_amount() > 0.0:
		w["walk"] = float(w.get("walk", 0.0)) + 0.3
		w.erase("look")
	var total := 0.0
	for k: String in w:
		total += float(w[k])
	var r := _rng.randf() * total
	var pick := "walk"
	for k: String in w:
		r -= float(w[k])
		if r <= 0.0:
			pick = k
			break
	if pick == "home":
		_go_home()
		return
	if pick != "walk" and director != null and director.has_method(&"claim_poi"):
		var p := director.call(&"claim_poi", StringName(pick), global_position, self) as Node3D
		if p != null:
			poi = p
			activity = StringName(pick)
			_activity_time = _rng.randf_range(12.0, 45.0) if pick != "sit" else _rng.randf_range(30.0, 120.0)
			go_to(_poi_stand_point(), walk_speed * _rng.randf_range(0.85, 1.1))
			_enter(S.TRAVEL)
			return
	# stroll somewhere
	poi = null
	activity = &"walk"
	var dest := Vector3.INF
	if director != null and director.has_method(&"random_destination"):
		dest = director.call(&"random_destination", global_position, 35.0)
	if dest == Vector3.INF:
		dest = NpcUtil.random_nav_point(get_world_3d(), global_position, 25.0)
	go_to(dest, walk_speed * _rng.randf_range(0.85, 1.15) * (1.35 if NpcUtil.rain_amount() > 0.0 and not _umbrella_up() else 1.0))
	_enter(S.TRAVEL)


func _poi_stand_point() -> Vector3:
	if poi == null or not is_instance_valid(poi):
		return global_position
	var p := poi.global_position
	if activity == &"chat" and director != null and director.has_method(&"poi_slot_offset"):
		p += director.call(&"poi_slot_offset", poi, self) as Vector3
	elif activity == &"shop" or activity == &"look":
		p += poi.global_basis.z.normalized() * 0.6    # stand in front of the counter / thing
	return p


func _arrive_at_poi() -> void:
	stop_moving()
	if poi == null or activity == &"walk":
		_enter(S.IDLE)
		return
	_enter(S.ACTIVITY)
	match activity:
		&"sit":
			face_point = global_position + poi.global_basis.z
			_yaw = poi.global_rotation.y
		&"shop", &"look":
			face_point = poi.global_position
		&"chat":
			chat_partner = null
			if director != null and director.has_method(&"poi_occupants"):
				for o: Variant in director.call(&"poi_occupants", poi):
					if o != self and is_instance_valid(o):
						chat_partner = o as Node3D
			face_point = chat_partner.global_position if chat_partner != null else poi.global_position


func _do_activity(_dt: float) -> void:
	match activity:
		&"sit":
			play_anim(&"sit_idle" if personality > 0.4 else &"sit")
		&"shop":
			play_anim(&"talk" if fmod(state_t, 9.0) < 4.0 else &"look_down")
		&"chat":
			if chat_partner != null and is_instance_valid(chat_partner) and chat_partner.get(&"state") == S.ACTIVITY:
				face_point = chat_partner.global_position
				look_at_point(chat_partner.global_position + Vector3.UP * 1.5)
				play_anim(&"talk" if fmod(state_t + personality * 7.0, 8.0) < 4.0 else &"idle")
				if _rng.randf() < 0.004:
					NpcUtil.sfx(&"human_laugh", global_position + Vector3.UP * 1.5, -8.0)
			else:
				play_anim(&"idle")
				if director != null and director.has_method(&"poi_occupants"):
					for o: Variant in director.call(&"poi_occupants", poi):
						if o != self and is_instance_valid(o):
							chat_partner = o as Node3D
		&"wait":
			play_anim(&"idle")
		&"look":
			play_anim(&"look_down")
		_:
			play_anim(&"idle")
	if state_t > _activity_time:
		look_at_point(Vector3.INF)
		_release_poi()
		face_point = Vector3.INF
		_enter(S.IDLE)


func _release_poi() -> void:
	if poi != null and director != null and director.has_method(&"release_poi"):
		director.call(&"release_poi", poi, self)
	poi = null
	_activity_time = 0.0
	chat_partner = null


func _go_home() -> void:
	_release_poi()
	var dest := home_pos
	if director != null and director.has_method(&"exit_point"):
		dest = director.call(&"exit_point", global_position)
	go_to(dest, walk_speed)
	_enter(S.GO_HOME)


# --- named humans ---------------------------------------------------------------------------

func _in_work_hours() -> bool:
	var h := NpcUtil.hour()
	if work_hours.x <= work_hours.y:
		return h >= work_hours.x and h < work_hours.y
	return h >= work_hours.x or h < work_hours.y


## Named humans: shows/hides them by work hours (called by the director even while hidden).
func update_presence() -> void:
	if role != "ambient":
		_update_named_presence()


func _update_named_presence() -> void:
	var should := _in_work_hours() or in_dialogue
	if should != visible:
		set_active(should)
		if should:
			teleport_to(station_xform.origin, station_xform.basis.get_euler().y)
			_resume()


func _do_station(_dt: float) -> void:
	var st := station_xform.origin
	if NpcUtil.flat_dist(global_position, st) > 0.5:
		go_to(st, walk_speed)
		play_anim(&"walk")
		return
	stop_moving()
	var player := get_player()
	if player != null and perception.can_see_player and NpcUtil.flat_dist(player.global_position, global_position) < 5.0:
		face_point = player.global_position
		look_at_point(player.global_position)
	else:
		face_point = st + station_xform.basis.z
		look_at_point(Vector3.INF)
	var a := station_anim
	if station_anim == &"sell" and fmod(state_t, 14.0) > 9.0:
		a = &"idle"
	play_anim(a)
	if npc_id == &"co_hoa" and fmod(state_t, 25.0) < 0.3 and _rng.randf() < 0.3:
		NpcUtil.sfx(&"human_call", global_position + Vector3.UP * 1.5, -6.0)


func _do_roam(_dt: float) -> void:
	# Bin: wanders between points of his patrol path or around his spawn (the lake)
	if move_target == Vector3.INF or arrived(0.5):
		if state_t > _activity_time:
			var dest := Vector3.INF
			if roam_path != null and roam_path.curve != null and roam_path.curve.point_count > 0:
				var i := _rng.randi() % roam_path.curve.point_count
				dest = roam_path.to_global(roam_path.curve.get_point_position(i))
			else:
				dest = NpcUtil.random_nav_point(get_world_3d(), station_xform.origin, roam_radius)
			go_to(dest, run_speed * 0.8 if _rng.randf() < 0.3 else walk_speed)
			_activity_time = state_t + _rng.randf_range(3.0, 9.0)
		else:
			stop_moving()
			play_anim(&"idle" if fmod(state_t, 6.0) < 3.0 else &"look_down")
			return
	play_anim(&"run" if desired_speed > walk_speed * 1.5 else &"walk")


# --- cat reactions ----------------------------------------------------------------------------

func _cat_awareness(player: Node3D) -> void:
	if player == null or state in [S.PET, S.APPROACH_PET, S.SHOO, S.GO_HOME]:
		return
	if state == S.ACTIVITY and activity == &"sit" and personality < 0.3:
		return
	var d := NpcUtil.flat_dist(player.global_position, global_position)
	if perception.can_see_player and d < 5.0 and _look_cooldown <= 0.0 and state != S.LOOK_CAT:
		if role == "vendor":
			return    # vendors look from their station (_do_station)
		if state == S.TRAVEL or state == S.IDLE or state == S.ROAM or (state == S.ACTIVITY and activity != &"chat"):
			if _rng.randf() < 0.25 + 0.5 * personality:
				_look_cooldown = _rng.randf_range(15.0, 30.0)
				_enter(S.LOOK_CAT)
			else:
				_look_cooldown = 6.0
	# kids and cat lovers come to pet a friendly cat sitting near them without being asked
	if role == "kid" and d < 3.5 and perception.can_see_player and _pet_cooldown <= 0.0 and state != S.LOOK_CAT:
		if NpcUtil.player_is_resting(player) or NpcUtil.player_velocity(player).length() < 0.3:
			_pet_cooldown = 25.0
			_enter(S.APPROACH_PET)


func charm_chance() -> float:
	var charm := float(NpcUtil.attribute(&"charm")) + NpcUtil.modifier(&"charm_bonus", 0.0)
	var c := 0.12 + 0.075 * charm + 0.25 * personality + 0.3 * NpcUtil.modifier(&"meow_charm", 0.0)
	if role == "kid":
		c += 0.3
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and gs.has_method(&"get_reputation"):
		c += clampf(float(gs.call(&"get_reputation", &"humans")) / 200.0, -0.2, 0.2)
	return clampf(c, 0.05, 0.95)


func _on_player_meowed(_kind: StringName) -> void:
	if not active or in_dialogue or lod >= Lod.FAR:
		return
	var player := get_player()
	if player == null:
		return
	var d := NpcUtil.flat_dist(player.global_position, global_position)
	if d > 5.0 or _pet_cooldown > 0.0 or state in [S.PET, S.APPROACH_PET, S.SHOO, S.GO_HOME, S.SHELTER]:
		return
	if role == "vendor" and npc_id != &"ba_tu":
		_pet_cooldown = 10.0
		look_at_point(player.global_position)
		return
	perception.force_awareness(maxf(perception.awareness, 0.5), player.global_position)
	_pet_cooldown = _rng.randf_range(20.0, 35.0)
	if _rng.randf() < charm_chance():
		_release_poi()
		NpcUtil.sfx(&"human_aww", global_position + Vector3.UP * 1.5, -4.0)
		_enter(S.APPROACH_PET)
	else:
		_enter(S.LOOK_CAT)


func _finish_pet() -> void:
	var gs := get_node_or_null(^"/root/GameState")
	var day := 0
	var tod := get_node_or_null(^"/root/TimeOfDay")
	if tod != null:
		day = int(tod.get(&"day"))
	var key := str(day)
	if gs != null and not _petted_today.has(key):
		_petted_today[key] = true
		if gs.has_method(&"add_reputation"):
			gs.call(&"add_reputation", &"humans", 1)
		if gs.has_method(&"modify_stat"):
			gs.call(&"modify_stat", &"energy", 3.0)
		if gs.has_method(&"increment_counter"):
			gs.call(&"increment_counter", &"petted_by_humans")
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_meowed.emit(&"purr")
	_resume()


func shoo(reason_pos: Vector3) -> void:
	if not active or _shoo_cooldown > 0.0 or in_dialogue:
		return
	_shoo_cooldown = 8.0
	_release_poi()
	face_point = reason_pos
	NpcUtil.sfx(&"human_shoo" if _rng.randf() < 0.6 else &"human_clap_shoo", global_position + Vector3.UP * 1.5, -2.0)
	var gs := get_node_or_null(^"/root/GameState")
	if gs != null and gs.has_method(&"add_reputation") and role == "vendor":
		gs.call(&"add_reputation", &"humans", -1)
	_enter(S.SHOO)


func _on_object_knocked_off(obj: Node3D, _id: StringName, _h: float) -> void:
	if not active or obj == null or lod >= Lod.FAR:
		return
	var player := get_player()
	if player == null:
		return
	if obj.global_position.distance_to(global_position) < 8.0 and player.global_position.distance_to(global_position) < 9.0:
		perception.force_awareness(0.9, player.global_position)
		if _rng.randf() < 0.5 + 0.4 * (1.0 if role == "vendor" else 0.0):
			shoo(player.global_position)
		else:
			NpcUtil.sfx(&"human_surprise", global_position + Vector3.UP * 1.5, -4.0)
			_enter(S.LOOK_CAT)


func on_swiped(by: Node) -> void:
	if by is Node3D:
		shoo((by as Node3D).global_position)


## Vendors shoo the cat when it steals from their stall (FoodSource steal noise → npc_alerted).
func _on_alert_changed(_old: int, new_level: int) -> void:
	if new_level == Perception.Level.ALERTED and role == "vendor" and perception.heard_this_tick > 0.25:
		shoo(perception.last_stimulus_pos)


# --- weather ------------------------------------------------------------------------------------

func _umbrella_up() -> bool:
	return visual != null and bool(visual.get(&"_umbrella_on"))


func _update_weather() -> void:
	var rain := NpcUtil.rain_amount()
	if absf(rain - _rain_checked) < 0.01:
		return
	_rain_checked = rain
	var raining := rain > 0.0
	var sheltered_role := role == "vendor"   # stalls have their own awning
	if visual != null:
		visual.call(&"set_umbrella", raining and umbrella_user and not sheltered_role,
			UMBRELLA_COLORS[absi(hash(name)) % UMBRELLA_COLORS.size()])
	if raining and not umbrella_user and role == "ambient" and state in [S.IDLE, S.TRAVEL, S.ACTIVITY]:
		if director != null and director.has_method(&"find_shelter"):
			var sp := director.call(&"find_shelter", global_position) as Vector3
			if sp != Vector3.INF:
				_release_poi()
				go_to(sp, run_speed * 0.8)
				_enter(S.SHELTER)


func on_despawn() -> void:
	_release_poi()
	super.on_despawn()
	_enter(S.IDLE)
