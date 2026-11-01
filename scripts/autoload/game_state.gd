extends Node
## GameState — Cam's RPG state (owner: systems).
##
## Vitals simulation (health / hunger / energy / warmth + cat wetness), attributes, XP & levels,
## skills and the modifier system (`get_modifier(name)`), inventory + mouth slot, flags,
## reputation, locations / collectibles / territory / naps, buffs, equipment, achievements,
## faint & revive, and versioned JSON save/load with pluggable save providers.
## Full API and tuning tables: docs/areas/systems.md.

const SAVE_VERSION := 1
const AUTOSAVE_SLOT := 0
const MANUAL_SLOTS := 3
const MAX_LEVEL := 10
const ITEMS_PATH := "res://data/items/items.json"
const SKILLS_PATH := "res://data/skills/skills.json"

const STATS: Array[StringName] = [&"health", &"hunger", &"energy", &"warmth"]
const ATTRIBUTES: Array[StringName] = [&"agility", &"stealth", &"charm", &"hunting"]
const FACTIONS: Array[StringName] = [&"humans", &"rooftop_cats", &"birds"]
const BASE_STAT_MAX := 100.0
const ATTRIBUTE_MIN := 1
const ATTRIBUTE_MAX := 10
const START_ATTRIBUTES := {"agility": 3, "stealth": 2, "charm": 2, "hunting": 1}
const START_SKILL_POINTS := 1
const START_CAPS := 0
const REPUTATION_MIN := -100
const REPUTATION_MAX := 100
## Extra skill point awarded on reaching these levels (on top of 1 per level).
const MILESTONE_LEVELS: Array[int] = [5, 10]

## XP granted by the core systems (quests define their own rewards).
const XP_REWARDS := {
	"location": 15, "memory": 40, "collectible": 5, "nap_first": 20, "territory": 15,
	"knock_first": 3, "prey": 10, "achievement": 50, "scratch_daily": 5,
}

## Vitals rates per GAME HOUR for each activity. hunger is a drain (positive = loses hunger),
## energy is signed (negative = drains). 1 game hour = 1 real minute at time_scale 1.
const ACTIVITY_RATES := {
	"idle": {"hunger": 1.0, "energy": -0.6},
	"rest": {"hunger": 0.8, "energy": 3.0},
	"walk": {"hunger": 1.25, "energy": -1.5},
	"trot": {"hunger": 1.5, "energy": -2.5},
	"run": {"hunger": 2.0, "energy": -6.0},
	"sneak": {"hunger": 1.2, "energy": -1.6},
	"climb": {"hunger": 1.8, "energy": -5.0},
	"swim": {"hunger": 2.2, "energy": -9.0},
	"sleep": {"hunger": 0.6, "energy": 25.0},
}
## Player-state names (from GameEvents.player_state_changed) → activity.
const STATE_TO_ACTIVITY := {
	"idle": "idle", "idle_look": "idle", "turn": "idle", "meow": "idle", "jump_crouch": "idle",
	"fall": "idle", "land": "idle", "land_hard": "idle", "swipe": "idle", "hiss": "idle",
	"sit": "rest", "sit_idle": "rest", "sit_down": "rest", "groom": "rest", "lie": "rest",
	"lie_down": "rest", "knead": "rest", "eat": "rest", "drink": "rest", "stretch": "rest",
	"walk": "walk", "balance": "walk", "balance_walk": "walk", "scratch": "walk", "carry": "walk",
	"trot": "trot", "run": "run", "sprint": "run", "jump": "run", "jump_up": "run", "air": "run",
	"pounce": "run", "sneak": "sneak", "sneak_idle": "idle", "crouch": "sneak",
	"climb": "climb", "climbing": "climb", "scramble": "climb", "ledge_grab": "climb",
	"swim": "swim", "sleep": "sleep", "sleeping": "sleep", "nap": "sleep",
}
const SPEED_ACTIVITIES := ["run"]

## Achievements tracked from counters.
const ACHIEVEMENTS := {
	"knock_it_off": {"counter": "knocked_unique", "target": 20},
	"memory_keeper": {"counter": "memories_found", "target": 12},
	"nap_connoisseur": {"counter": "nap_spots_unique", "target": 8},
	"rooftop_royalty": {"counter": "territory_marked", "target": 10},
	"night_prowler": {"counter": "prey_caught", "target": 10},
}

# --- tunables -----------------------------------------------------------------------------
## Run the real-time vitals simulation in _process (tests switch it off and call simulate()).
var simulation_enabled := true
var autosave_enabled := true
var autosave_min_interval_s := 20.0
var save_dir := "user://saves"
## Seconds (real) between fainting and waking up at the last nap spot.
var faint_wake_delay := 2.5
## Game hours that pass while Cam is passed out.
var faint_hours := 3.0
## Auto-discover `location` markers (group "location", meta location_id) when Cam gets close.
var location_poll_enabled := true
## -1 = detect shelter from Area3D nodes in group "shelter"; 0/1 force (tests, cutscenes).
var shelter_override := -1

# --- state ---------------------------------------------------------------------------------
var _stats: Dictionary = {}            # "health" -> float
var _attributes: Dictionary = {}       # "agility" -> int
var attribute_points := 0
var xp := 0
var level := 1
var skill_points := START_SKILL_POINTS
var _skills: Dictionary = {}           # skill_id -> true
var _items: Dictionary = {}            # item_id -> int (everything owned, incl. the mouth item)
var mouth_item: StringName = &""
var _equipped: Dictionary = {}         # slot -> item_id
var _flags: Dictionary = {}
var _reputation: Dictionary = {}
var _locations: Dictionary = {}        # location_id -> display name
var _collectibles: Dictionary = {}     # id -> day found
var _territory: Dictionary = {}        # spot_id -> day marked
var _nap_spots: Dictionary = {}        # spot_id -> times slept
var _last_nap_spot: StringName = &""
var _last_nap_transform: Variant = null  # Transform3D or null
var _counters: Dictionary = {}
var _achievements: Dictionary = {}
var _buffs: Dictionary = {}            # id -> {"modifiers": {}, "expires": abs_min, "name_key": ""}
var _world: Dictionary = {}            # persistent world-object state, id -> Dictionary
var wetness := 0.0                     # 0 dry .. 1 soaked
var activity: StringName = &"idle"
var is_fainted := false
var is_sleeping := false
var faints_today := 0
var playtime_s := 0.0
var current_area: StringName = &""

# --- data ------------------------------------------------------------------------------------
var _item_defs: Dictionary = {}
var _skill_defs: Dictionary = {}
var _tree_defs: Dictionary = {}
var _buff_defs: Dictionary = {}
var _modifier_specs: Dictionary = {}
var _skill_mods: Dictionary = {}       # cached sum of unconditional skill effects
var _skill_conditional: Array = []     # [{when, effects}]

# --- runtime ---------------------------------------------------------------------------------
var _providers: Dictionary = {}        # key -> Object
var _pending_provider_data: Dictionary = {}
var _pending_player_transform: Variant = null
var _pending_weather: Dictionary = {}
var _weather_kind: StringName = &"clear"
var _weather_intensity := 0.0
var _sheltered_cache := false
var _shelter_timer := 0.0
var _location_timer := 0.0
var _last_emitted: Dictionary = {}
var _warned: Dictionary = {}
var _warning_state: Dictionary = {}
var _last_autosave_msec := -1000000
var _sleep_ctx: Dictionary = {}
var _last_damage_source: StringName = &"injury"
var _faint_queued := false
var _autosave_pending := false


func _ready() -> void:
	_load_data()
	_reset_state()
	GameEvents.player_state_changed.connect(_on_player_state_changed)
	GameEvents.player_jumped.connect(_on_player_jumped)
	GameEvents.player_damaged.connect(_on_player_damaged)
	GameEvents.player_landed.connect(_on_player_landed)
	GameEvents.player_spawned.connect(_on_player_spawned)
	GameEvents.cat_sense_toggled.connect(_on_cat_sense_toggled)
	GameEvents.weather_changed.connect(_on_weather_changed)
	GameEvents.time_skipped.connect(_on_time_skipped)
	GameEvents.day_changed.connect(_on_day_changed)
	GameEvents.area_entered.connect(func(area_id: StringName) -> void: current_area = area_id)


func _process(delta: float) -> void:
	if get_tree().paused:
		return
	playtime_s += delta
	_shelter_timer -= delta
	if _shelter_timer <= 0.0:
		_shelter_timer = 0.25
		_sheltered_cache = _compute_sheltered()
	if location_poll_enabled:
		_location_timer -= delta
		if _location_timer <= 0.0:
			_location_timer = 0.5
			_poll_locations()
	if _autosave_pending and not is_fainted and Time.get_ticks_msec() - _last_autosave_msec >= int(autosave_min_interval_s * 1000.0):
		autosave("deferred")
	if simulation_enabled and not is_fainted:
		var tod := _tod()
		if tod != null and not tod.is_paused():
			var hours: float = delta * float(tod.time_scale) / 60.0
			if hours > 0.0:
				simulate(hours)


# =============================================================================================
# Data
# =============================================================================================

func _load_data() -> void:
	_item_defs = _read_json_dict(ITEMS_PATH)
	var sk := _read_json_dict(SKILLS_PATH)
	_skill_defs = sk.get("skills", {})
	_tree_defs = sk.get("trees", {})
	_buff_defs = sk.get("buffs", {})
	_modifier_specs = sk.get("modifiers", {})
	if _item_defs.is_empty():
		push_error("GameState: items.json missing or invalid")
	if _skill_defs.is_empty():
		push_error("GameState: skills.json missing or invalid")


static func _read_json_dict(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var txt := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(txt)
	if parsed is Dictionary:
		return parsed
	push_error("GameState: invalid JSON in " + path)
	return {}


func get_item_def(id: StringName) -> Dictionary:
	return _item_defs.get(String(id), {})


func item_exists(id: StringName) -> bool:
	return _item_defs.has(String(id))


func get_all_item_ids() -> PackedStringArray:
	return PackedStringArray(_item_defs.keys())


## Translated item name. in_sentence = true lower-cases the first letter for use inside a
## prompt ("Ngậm cá tươi", "Pick up bottle cap") unless the item has "proper_name": true.
func get_item_name(id: StringName, in_sentence: bool = false) -> String:
	var d := get_item_def(id)
	var n := tr(String(d.get("name_key", String(id))))
	if in_sentence and n != "" and not bool(d.get("proper_name", false)):
		n = n.left(1).to_lower() + n.substr(1)
	return n


func is_mouth_item(id: StringName) -> bool:
	return bool(get_item_def(id).get("mouth", false))


func get_skill_def(id: StringName) -> Dictionary:
	return _skill_defs.get(String(id), {})


func get_all_skills() -> Dictionary:
	return _skill_defs


func get_skill_trees() -> Dictionary:
	return _tree_defs


func get_skills_in_tree(tree: StringName) -> PackedStringArray:
	var out := PackedStringArray()
	for id: String in _skill_defs:
		if String(_skill_defs[id].get("tree", "")) == String(tree):
			out.append(id)
	return out


func get_buff_def(id: StringName) -> Dictionary:
	return _buff_defs.get(String(id), {})


func get_modifier_names() -> PackedStringArray:
	return PackedStringArray(_modifier_specs.keys())


# =============================================================================================
# New game / reset
# =============================================================================================

func new_game() -> void:
	_reset_state()
	_pending_provider_data.clear()
	_pending_player_transform = null
	_pending_weather = {}
	_autosave_pending = false
	for key: String in _providers.keys():
		var p: Object = _providers[key]
		if not is_instance_valid(p):
			_providers.erase(key)
			continue
		if p.has_method("reset_state"):
			p.call("reset_state")
		elif p.has_method("load_save_data"):
			p.call("load_save_data", {})
	GameEvents.new_game_started.emit()
	for s in STATS:
		_emit_stat(s, true)


func _reset_state() -> void:
	_stats.clear()
	for s in STATS:
		_stats[String(s)] = BASE_STAT_MAX
	_attributes = START_ATTRIBUTES.duplicate()
	attribute_points = 0
	xp = 0
	level = 1
	skill_points = START_SKILL_POINTS
	_skills.clear()
	_items.clear()
	if START_CAPS > 0:
		_items["cap"] = START_CAPS
	mouth_item = &""
	_equipped.clear()
	_flags.clear()
	_reputation.clear()
	for f in FACTIONS:
		_reputation[String(f)] = 0
	_locations.clear()
	_collectibles.clear()
	_territory.clear()
	_nap_spots.clear()
	_last_nap_spot = &""
	_last_nap_transform = null
	_counters.clear()
	_achievements.clear()
	_buffs.clear()
	_world.clear()
	wetness = 0.0
	activity = &"idle"
	is_fainted = false
	is_sleeping = false
	faints_today = 0
	playtime_s = 0.0
	current_area = &""
	_warning_state.clear()
	_last_emitted.clear()
	_rebuild_skill_cache()


# =============================================================================================
# Vital stats
# =============================================================================================

func get_stat(stat: StringName) -> float:
	return float(_stats.get(String(stat), 0.0))


func get_stat_max(stat: StringName) -> float:
	return BASE_STAT_MAX + get_modifier(StringName("max_" + String(stat)))


func get_stat_ratio(stat: StringName) -> float:
	var m := get_stat_max(stat)
	return get_stat(stat) / m if m > 0.0 else 0.0


func set_stat(stat: StringName, value: float) -> void:
	var k := String(stat)
	if not _stats.has(k):
		push_warning("GameState.set_stat: unknown stat " + k)
		return
	_stats[k] = clampf(value, 0.0, get_stat_max(stat))
	_emit_stat(stat, true)
	_check_vital_warnings()
	_check_faint()


func modify_stat(stat: StringName, delta: float) -> void:
	set_stat(stat, get_stat(stat) + delta)


func _add_stat_silent(stat: StringName, delta: float) -> void:
	var k := String(stat)
	_stats[k] = clampf(float(_stats.get(k, 0.0)) + delta, 0.0, get_stat_max(stat))


func _emit_stat(stat: StringName, force := false) -> void:
	var v := get_stat(stat)
	var k := String(stat)
	var last: float = _last_emitted.get(k, -999.0)
	var m := get_stat_max(stat)
	if force or absf(v - last) >= 0.25 or (v != last and (v <= 0.0 or v >= m)):
		_last_emitted[k] = v
		GameEvents.stat_changed.emit(stat, v, m)


func is_exhausted() -> bool:
	return get_stat(&"energy") < 15.0


func is_starving() -> bool:
	return get_stat(&"hunger") <= 0.0


## Multiplier (≤ 1) applied to speed-type modifiers: low vitals make Cam slower.
func get_vitals_speed_factor() -> float:
	var f := 1.0
	if get_stat(&"energy") < 15.0:
		f *= lerpf(0.75, 0.9, get_stat(&"energy") / 15.0)
	if get_stat(&"hunger") < 15.0:
		f *= 0.9
	if get_stat(&"warmth") < 25.0:
		f *= 0.92
	if get_stat(&"health") < 25.0:
		f *= 0.85
	if mouth_item != &"":
		f *= float(get_item_def(mouth_item).get("carry_speed", 1.0))
	return f


## Multiplier (≥ 1) applied to noise-type modifiers: tired/cold cats are clumsy and noisy.
func get_vitals_noise_factor() -> float:
	var f := 1.0
	if get_stat(&"energy") < 15.0:
		f *= 1.25
	if get_stat(&"warmth") < 25.0:
		f *= 1.1
	if get_stat(&"health") < 25.0:
		f *= 1.1
	return f


# --- environment -----------------------------------------------------------------------------

func set_activity(new_activity: StringName) -> void:
	var a := String(new_activity)
	if not ACTIVITY_RATES.has(a):
		a = _guess_activity(a)
	activity = StringName(a)


func _guess_activity(state: String) -> String:
	if STATE_TO_ACTIVITY.has(state):
		return STATE_TO_ACTIVITY[state]
	for key: String in ["sleep", "climb", "sneak", "run", "sprint", "trot", "walk", "swim", "sit", "lie"]:
		if state.contains(key):
			match key:
				"sprint": return "run"
				"sit", "lie": return "rest"
				_: return key
	return "idle"


func get_weather() -> StringName:
	return _weather_kind


func get_weather_intensity() -> float:
	return _weather_intensity


func set_weather_state(kind: StringName, intensity: float) -> void:
	_weather_kind = kind
	_weather_intensity = clampf(intensity, 0.0, 1.0)


func is_sheltered() -> bool:
	if shelter_override >= 0:
		return shelter_override == 1
	return _sheltered_cache


## Rain reaching Cam right now (0 when dry weather or sheltered). Storms count 1.5×.
func get_exposed_rain() -> float:
	if is_sheltered():
		return 0.0
	match _weather_kind:
		&"rain":
			return _weather_intensity if _weather_intensity > 0.0 else 0.6
		&"storm":
			return maxf(_weather_intensity, 0.8) * 1.5
	return 0.0


func is_wet() -> bool:
	return wetness > 0.05


## Instantly soak the cat (fell into the lake, splashed by a motorbike...).
func soak(amount: float = 1.0) -> void:
	wetness = clampf(wetness + amount, 0.0, 1.0)


## Grooming dries a little fur and makes Cam presentable.
func groom() -> void:
	wetness = maxf(0.0, wetness - 0.15)
	add_buff(&"groomed")
	increment_counter(&"grooms")


func _compute_sheltered() -> bool:
	var player := get_player()
	if player == null:
		return false
	var p: Vector3 = player.global_position + Vector3(0.0, 0.15, 0.0)
	for n in get_tree().get_nodes_in_group(&"shelter"):
		if n is Area3D:
			var a := n as Area3D
			if a.monitoring and player is PhysicsBody3D and a.overlaps_body(player):
				return true
			if _point_in_area(a, p):
				return true
		elif n is Node3D and n.has_meta(&"radius"):
			if (n as Node3D).global_position.distance_to(p) <= float(n.get_meta(&"radius")):
				return true
	return false


static func _point_in_area(area: Area3D, p: Vector3) -> bool:
	for c in area.get_children():
		var cs := c as CollisionShape3D
		if cs == null or cs.disabled or cs.shape == null:
			continue
		var lp: Vector3 = cs.global_transform.affine_inverse() * p
		var sh := cs.shape
		if sh is BoxShape3D:
			var h: Vector3 = (sh as BoxShape3D).size * 0.5
			if absf(lp.x) <= h.x and absf(lp.y) <= h.y and absf(lp.z) <= h.z:
				return true
		elif sh is SphereShape3D:
			if lp.length() <= (sh as SphereShape3D).radius:
				return true
		elif sh is CylinderShape3D:
			var cy := sh as CylinderShape3D
			if Vector2(lp.x, lp.z).length() <= cy.radius and absf(lp.y) <= cy.height * 0.5:
				return true
		elif sh is CapsuleShape3D:
			var ca := sh as CapsuleShape3D
			if Vector2(lp.x, lp.z).length() <= ca.radius and absf(lp.y) <= ca.height * 0.5:
				return true
		elif sh is ConvexPolygonShape3D:
			var pts := (sh as ConvexPolygonShape3D).points
			if pts.size() > 0:
				var aabb := AABB(pts[0], Vector3.ZERO)
				for q in pts:
					aabb = aabb.expand(q)
				if aabb.has_point(lp):
					return true
	return false


# --- simulation --------------------------------------------------------------------------------

## Advance the vitals simulation by `hours` game hours (sub-stepped). Public for tests/tools.
func simulate(hours: float, check_faint: bool = true) -> void:
	var remaining := hours
	while remaining > 0.0:
		var h := minf(remaining, 0.25)
		remaining -= h
		_simulate_step(h)
	_expire_buffs()
	for s in STATS:
		_emit_stat(s)
	_check_vital_warnings()
	if check_faint:
		_check_faint()


func _simulate_step(h: float) -> void:
	var sleeping := is_sleeping or activity == &"sleep"
	var act := "sleep" if sleeping else String(activity)
	var rates: Dictionary = ACTIVITY_RATES.get(act, ACTIVITY_RATES["idle"])
	var sheltered: bool = bool(_sleep_ctx.get("sheltered", is_sheltered())) if is_sleeping else is_sheltered()
	var night := false
	var tod := _tod()
	if tod != null:
		night = tod.is_night()
	# Hunger
	var hunger_rate: float = float(rates["hunger"]) * get_modifier(&"hunger_drain")
	_add_stat_silent(&"hunger", -hunger_rate * h)
	# Energy
	var e: float = float(rates["energy"])
	if e < 0.0:
		e *= get_modifier(&"energy_drain")
		if act in SPEED_ACTIVITIES:
			e *= get_modifier(&"sprint_energy_mult")
		if get_stat(&"warmth") < 30.0:
			e *= 1.4
		if get_stat(&"hunger") < 15.0:
			e *= 1.3
	else:
		e *= get_modifier(&"energy_regen")
		if sleeping:
			e *= float(_sleep_ctx.get("energy_mult", 1.0))
			if sheltered:
				e *= 1.1
			if get_stat(&"hunger") < 10.0:
				e *= 0.5
			if wetness > 0.3:
				e *= 0.7
	_add_stat_silent(&"energy", e * h)
	# Wetness
	var rain := 0.0 if (is_sleeping and sheltered) else get_exposed_rain()
	if rain > 0.0:
		wetness = minf(1.0, wetness + rain * 1.6 * get_modifier(&"wet_rate") * h)
	else:
		var dry := 0.45
		if sheltered:
			dry += 0.6
		if sleeping:
			dry += 0.4
		if not night and _weather_kind == &"clear":
			dry += 0.5
		wetness = maxf(0.0, wetness - dry * h)
	# Warmth
	var warm_drain := get_modifier(&"warmth_drain")
	if wetness > 0.05 and not sheltered:
		_add_stat_silent(&"warmth", -(4.0 + 14.0 * wetness) * (1.3 if night else 1.0) * warm_drain * h)
	elif wetness > 0.05:
		_add_stat_silent(&"warmth", -1.0 * wetness * warm_drain * h)
	else:
		var gain := 6.0 + (10.0 if sleeping else 0.0) + (2.0 if sheltered else 0.0)
		gain += float(_sleep_ctx.get("warmth_bonus", 0.0)) if is_sleeping else 0.0
		if night and not sheltered and not sleeping:
			gain *= 0.6
		_add_stat_silent(&"warmth", gain * h)
	# Health
	var hunger_v := get_stat(&"hunger")
	var warmth_v := get_stat(&"warmth")
	if hunger_v > 40.0 and warmth_v > 30.0:
		_add_stat_silent(&"health", 2.0 * get_modifier(&"health_regen") * (2.0 if sleeping else 1.0) * h)
	if hunger_v <= 0.0:
		_last_damage_source = &"hunger"
		_add_stat_silent(&"health", -4.0 * h)
	if warmth_v <= 5.0:
		_last_damage_source = &"cold"
		_add_stat_silent(&"health", -3.0 * h)


func _on_time_skipped(hours: float) -> void:
	# Time fast-forward (sleep / faint). Vitals follow the sleeping context if set.
	if hours <= 0.0:
		return
	var prev_sleep := is_sleeping
	if not _sleep_ctx.is_empty():
		is_sleeping = true
	# While passed out the sim still runs, but cannot trigger another faint.
	simulate(hours, not is_fainted)
	is_sleeping = prev_sleep


func _check_vital_warnings() -> void:
	_warn_threshold(&"hunger", 25.0, "NOTIFY_HUNGRY")
	_warn_threshold(&"energy", 15.0, "NOTIFY_TIRED")
	_warn_threshold(&"warmth", 25.0, "NOTIFY_COLD")
	_warn_threshold(&"health", 25.0, "NOTIFY_HURT")


func _warn_threshold(stat: StringName, threshold: float, key: String) -> void:
	var low := get_stat(stat) < threshold
	var k := String(stat)
	var was_low: bool = _warning_state.get(k, false)
	if low and not was_low:
		_warning_state[k] = true
		GameEvents.notify.emit(tr(key), stat)
	elif not low and was_low and get_stat(stat) > threshold + 10.0:
		_warning_state[k] = false


# --- signal handlers ---------------------------------------------------------------------------

func _on_player_state_changed(_old: StringName, new_state: StringName) -> void:
	set_activity(new_state)


func _on_player_jumped(charge: float) -> void:
	_add_stat_silent(&"energy", -(0.3 + 0.4 * clampf(charge, 0.0, 1.0)) * get_modifier(&"energy_drain"))
	_emit_stat(&"energy")


func _on_cat_sense_toggled(active: bool) -> void:
	if active:
		_add_stat_silent(&"energy", -1.5 * get_modifier(&"cat_sense_cost"))
		_emit_stat(&"energy")


func _on_player_damaged(amount: float, source: StringName) -> void:
	_last_damage_source = source if source != &"" else &"injury"
	modify_stat(&"health", -absf(amount))


func _on_player_landed(_impact: float, surface: StringName) -> void:
	if surface == &"water":
		soak(1.0)


func _on_weather_changed(kind: StringName, intensity: float) -> void:
	set_weather_state(kind, intensity)


func _on_day_changed(_day: int) -> void:
	faints_today = 0


# =============================================================================================
# Modifiers (skills, attributes, buffs, equipment, vitals)
# =============================================================================================

## Returns the effective value of a gameplay modifier (see data/skills/skills.json "modifiers").
## value = base + Σ per_attribute·(attr−1) + skills + conditional skills + buffs + equipment,
## then × vitals factor for "speed"/"noise" modifiers, then clamped to [min, max].
func get_modifier(mod_name: StringName) -> float:
	var k := String(mod_name)
	var spec: Dictionary = _modifier_specs.get(k, {})
	if spec.is_empty() and not _warned.has(k):
		_warned[k] = true
		push_warning("GameState.get_modifier: unknown modifier '%s'" % k)
	var v: float = float(spec.get("base", 1.0 if k.ends_with("_mult") else 0.0))
	var per: Dictionary = spec.get("per_attribute", {})
	for attr: String in per:
		v += float(per[attr]) * float(int(_attributes.get(attr, 1)) - 1)
	v += float(_skill_mods.get(k, 0.0))
	for entry: Dictionary in _skill_conditional:
		var fx: Dictionary = entry.get("effects", {})
		if fx.has(k) and GameConditions.evaluate(entry.get("when", {})):
			v += float(fx[k])
	for b: Dictionary in _buffs.values():
		v += float((b.get("modifiers", {}) as Dictionary).get(k, 0.0))
	for slot: String in _equipped:
		var em: Dictionary = get_item_def(StringName(_equipped[slot])).get("equip_modifiers", {})
		v += float(em.get(k, 0.0))
	match String(spec.get("vitals", "")):
		"speed":
			v *= get_vitals_speed_factor()
		"noise":
			v *= get_vitals_noise_factor()
	if spec.has("min"):
		v = maxf(v, float(spec["min"]))
	if spec.has("max"):
		v = minf(v, float(spec["max"]))
	return v


## True when an ability-style modifier (e.g. "wall_jump", "catch_birds") is > 0.
func has_ability(mod_name: StringName) -> bool:
	return get_modifier(mod_name) > 0.0


func _rebuild_skill_cache() -> void:
	_skill_mods.clear()
	_skill_conditional.clear()
	for id: String in _skills:
		var d: Dictionary = _skill_defs.get(id, {})
		var fx: Dictionary = d.get("effects", {})
		for m: String in fx:
			_skill_mods[m] = float(_skill_mods.get(m, 0.0)) + float(fx[m])
		for c: Variant in d.get("conditional_effects", []):
			if c is Dictionary:
				_skill_conditional.append(c)


# =============================================================================================
# Attributes / XP / levels / skills
# =============================================================================================

func get_attribute(attr: StringName) -> int:
	return int(_attributes.get(String(attr), ATTRIBUTE_MIN))


## Attribute plus skill/buff/equipment bonuses (only charm has a bonus modifier: charm_bonus).
func get_effective_attribute(attr: StringName) -> int:
	var v := get_attribute(attr)
	if attr == &"charm":
		v += roundi(get_modifier(&"charm_bonus"))
	return v


func set_attribute(attr: StringName, value: int) -> void:
	var k := String(attr)
	if not START_ATTRIBUTES.has(k):
		push_warning("GameState.set_attribute: unknown attribute " + k)
		return
	_attributes[k] = clampi(value, ATTRIBUTE_MIN, ATTRIBUTE_MAX)
	GameEvents.attribute_changed.emit(attr, int(_attributes[k]))


func add_attribute(attr: StringName, delta: int) -> void:
	set_attribute(attr, get_attribute(attr) + delta)


## Spend one attribute point (earned on level-up) to raise an attribute by 1.
func raise_attribute(attr: StringName) -> bool:
	if attribute_points <= 0 or not START_ATTRIBUTES.has(String(attr)):
		return false
	if get_attribute(attr) >= ATTRIBUTE_MAX:
		return false
	attribute_points -= 1
	set_attribute(attr, get_attribute(attr) + 1)
	GameEvents.skill_points_changed.emit(skill_points, attribute_points)
	return true


## Cumulative XP required to REACH `lvl` (level 1 = 0). Formula: 25·(L−1)·(L+2).
## L2 100 · L3 250 · L4 450 · L5 700 · L6 1000 · L7 1350 · L8 1750 · L9 2200 · L10 2700.
static func xp_for_level(lvl: int) -> int:
	if lvl <= 1:
		return 0
	return 25 * (lvl - 1) * (lvl + 2)


func get_xp_to_next_level() -> int:
	if level >= MAX_LEVEL:
		return 0
	return xp_for_level(level + 1) - xp


## 0..1 progress inside the current level.
func get_level_progress() -> float:
	if level >= MAX_LEVEL:
		return 1.0
	var a := xp_for_level(level)
	var b := xp_for_level(level + 1)
	return clampf(float(xp - a) / float(b - a), 0.0, 1.0)


func add_xp(amount: int, reason: String = "") -> void:
	if amount <= 0:
		return
	var gained := roundi(float(amount) * get_modifier(&"xp_mult"))
	xp += gained
	GameEvents.xp_gained.emit(gained, reason)
	while level < MAX_LEVEL and xp >= xp_for_level(level + 1):
		level += 1
		skill_points += 1
		if level in MILESTONE_LEVELS:
			skill_points += 1
		attribute_points += 1
		GameEvents.level_up.emit(level)
		GameEvents.notify.emit(tr("NOTIFY_LEVEL_UP").format({"level": level}), &"level_up")
		GameEvents.skill_points_changed.emit(skill_points, attribute_points)


func add_skill_points(n: int) -> void:
	skill_points = maxi(0, skill_points + n)
	GameEvents.skill_points_changed.emit(skill_points, attribute_points)


func add_attribute_points(n: int) -> void:
	attribute_points = maxi(0, attribute_points + n)
	GameEvents.skill_points_changed.emit(skill_points, attribute_points)


func has_skill(id: StringName) -> bool:
	return _skills.has(String(id))


func get_unlocked_skills() -> PackedStringArray:
	return PackedStringArray(_skills.keys())


## Returns "" when the skill can be unlocked now, else a translated reason.
func get_skill_lock_reason(id: StringName) -> String:
	var d := get_skill_def(id)
	if d.is_empty():
		return tr("REQ_UNKNOWN_SKILL")
	if has_skill(id):
		return tr("REQ_ALREADY_UNLOCKED")
	var reasons: PackedStringArray = []
	for req: String in d.get("requires", []):
		if not has_skill(StringName(req)):
			reasons.append(tr("REQ_SKILL").format({"skill": tr(String(get_skill_def(StringName(req)).get("name_key", req)))}))
	if level < int(d.get("min_level", 1)):
		reasons.append(tr("REQ_LEVEL").format({"level": int(d.get("min_level", 1))}))
	var attrs: Dictionary = d.get("attributes", {})
	for a: String in attrs:
		if get_attribute(StringName(a)) < int(attrs[a]):
			reasons.append(tr("REQ_ATTRIBUTE").format({"attribute": tr("ATTR_" + a.to_upper()), "value": int(attrs[a])}))
	if skill_points < int(d.get("cost", 1)):
		reasons.append(tr("REQ_SKILL_POINTS").format({"points": int(d.get("cost", 1))}))
	return ", ".join(reasons)


func can_unlock_skill(id: StringName) -> bool:
	return get_skill_lock_reason(id) == ""


## &"unlocked", &"available" (can buy now), or &"locked".
func get_skill_state(id: StringName) -> StringName:
	if has_skill(id):
		return &"unlocked"
	return &"available" if can_unlock_skill(id) else &"locked"


func unlock_skill(id: StringName) -> bool:
	if not can_unlock_skill(id):
		return false
	var d := get_skill_def(id)
	skill_points -= int(d.get("cost", 1))
	_grant_skill(id)
	GameEvents.skill_points_changed.emit(skill_points, attribute_points)
	return true


## Grants a skill without cost/prerequisite checks (quest rewards, debug, load).
func grant_skill(id: StringName) -> bool:
	if has_skill(id) or get_skill_def(id).is_empty():
		return false
	_grant_skill(id)
	return true


func _grant_skill(id: StringName) -> void:
	_skills[String(id)] = true
	_rebuild_skill_cache()
	for s in STATS:
		_stats[String(s)] = minf(get_stat(s), get_stat_max(s))
		_emit_stat(s, true)
	GameEvents.skill_unlocked.emit(id)
	GameEvents.notify.emit(tr("NOTIFY_SKILL_UNLOCKED").format({"skill": tr(String(get_skill_def(id).get("name_key", id)))}), &"skill")


# =============================================================================================
# Inventory & mouth slot
# =============================================================================================

## Adds items (clamped to the item's stack size). Mouth-type items go straight into the mouth
## when it is empty; otherwise they are kept in Cam's den stash. Returns the number added.
func add_item(id: StringName, n: int = 1) -> int:
	if n <= 0:
		return 0
	var k := String(id)
	var d := get_item_def(id)
	if d.is_empty():
		push_warning("GameState.add_item: unknown item " + k)
	var stack: int = int(d.get("stack", 999))
	if stack <= 0:
		stack = 999
	var have := int(_items.get(k, 0))
	var added := clampi(n, 0, stack - have)
	if added <= 0:
		return 0
	_items[k] = have + added
	if String(d.get("category", "")) == "memory":
		set_counter(&"memories_found", count_items_in_category(&"memory"))
	GameEvents.inventory_changed.emit(id, int(_items[k]))
	if bool(d.get("mouth", false)) and mouth_item == &"":
		set_mouth_item(id)
	return added


func remove_item(id: StringName, n: int = 1) -> bool:
	var k := String(id)
	if n <= 0:
		return true
	var have := int(_items.get(k, 0))
	if have < n:
		return false
	have -= n
	if have <= 0:
		_items.erase(k)
		for slot: String in _equipped.keys():
			if String(_equipped[slot]) == k:
				_equipped.erase(slot)
	else:
		_items[k] = have
	if mouth_item == id and have <= 0:
		mouth_item = &""
		GameEvents.mouth_item_changed.emit(&"")
	GameEvents.inventory_changed.emit(id, have)
	return true


func has_item(id: StringName, n: int = 1) -> bool:
	return item_count(id) >= n


func item_count(id: StringName) -> int:
	return int(_items.get(String(id), 0))


func get_caps() -> int:
	return item_count(&"cap")


func get_inventory() -> Dictionary:
	return _items.duplicate()


func count_items_in_category(category: StringName) -> int:
	var c := 0
	for k: String in _items:
		if String(get_item_def(StringName(k)).get("category", "")) == String(category):
			c += int(_items[k])
	return c


## Put an owned mouth-type item in Cam's mouth ("" empties the mouth, item stays owned).
func set_mouth_item(id: StringName) -> bool:
	if id == &"":
		if mouth_item != &"":
			mouth_item = &""
			GameEvents.mouth_item_changed.emit(&"")
		return true
	if not has_item(id) or not is_mouth_item(id):
		return false
	if mouth_item != id:
		mouth_item = id
		GameEvents.mouth_item_changed.emit(id)
	return true


## Drops the mouth item into the world (removes it from the inventory). Returns its id or "".
## The caller (player) spawns the world pickup, e.g. PickupItem.spawn_dropped().
func drop_mouth_item() -> StringName:
	if mouth_item == &"":
		return &""
	var id := mouth_item
	remove_item(id, 1)
	if mouth_item == id:
		mouth_item = &""
		GameEvents.mouth_item_changed.emit(&"")
	GameEvents.item_dropped.emit(id, 1)
	return id


## Eat food: restores hunger × food_value. Returns hunger restored.
func eat(food_amount: float, source_id: StringName = &"", health_amount: float = 0.0) -> float:
	var before := get_stat(&"hunger")
	_add_stat_silent(&"hunger", food_amount * get_modifier(&"food_value"))
	if health_amount != 0.0:
		_add_stat_silent(&"health", health_amount)
	var restored := get_stat(&"hunger") - before
	_emit_stat(&"hunger", true)
	_emit_stat(&"health", true)
	if get_stat_ratio(&"hunger") >= 0.9 and food_amount >= 15.0:
		add_buff(&"well_fed")
	increment_counter(&"meals")
	GameEvents.food_eaten.emit(source_id, restored)
	_check_vital_warnings()
	return restored


## Use an item: eat food, apply a consumable, or play with a toy.
func use_item(id: StringName) -> bool:
	if not has_item(id):
		return false
	var d := get_item_def(id)
	var used := false
	var use: Dictionary = d.get("use", {})
	if float(d.get("food", 0.0)) > 0.0:
		eat(float(d["food"]), id, float(use.get("health", 0.0)))
		used = true
	else:
		if use.has("health"):
			modify_stat(&"health", float(use["health"]))
			used = true
	if use.has("warmth"):
		modify_stat(&"warmth", float(use["warmth"]))
		used = true
	if use.has("energy"):
		modify_stat(&"energy", float(use["energy"]))
		used = true
	if use.has("buff"):
		add_buff(StringName(use["buff"]), float(use.get("buff_hours", -1.0)))
		used = true
	if use.has("skill_points"):
		add_skill_points(int(use["skill_points"]))
		used = true
	if not used:
		return false
	var consumable := String(d.get("category", "")) in ["food", "consumable"]
	if consumable:
		remove_item(id, 1)
	GameEvents.item_used.emit(id)
	return true


# --- equipment -----------------------------------------------------------------------------

func equip_item(id: StringName) -> bool:
	var d := get_item_def(id)
	var slot := String(d.get("equip", ""))
	if slot == "" or not has_item(id):
		return false
	_equipped[slot] = String(id)
	GameEvents.item_used.emit(id)
	return true


func unequip_slot(slot: StringName) -> void:
	_equipped.erase(String(slot))


func get_equipped(slot: StringName) -> StringName:
	return StringName(_equipped.get(String(slot), ""))


# --- trading (Lão Quạ) -----------------------------------------------------------------------

func get_buy_price(id: StringName) -> int:
	return maxi(1, ceili(float(get_item_def(id).get("value", 1)) * get_modifier(&"price_mult")))


func get_sell_price(id: StringName) -> int:
	var v := float(get_item_def(id).get("value", 0))
	return maxi(0, floori(v * 0.5 * (2.0 - get_modifier(&"price_mult"))))


func buy_item(id: StringName, price: int = -1) -> bool:
	var p := get_buy_price(id) if price < 0 else price
	if get_caps() < p or not item_exists(id):
		return false
	var d := get_item_def(id)
	if item_count(id) >= int(d.get("stack", 999)):
		return false
	remove_item(&"cap", p)
	add_item(id, 1)
	increment_counter(&"items_bought")
	return true


func sell_item(id: StringName, price: int = -1) -> int:
	var d := get_item_def(id)
	if not has_item(id) or not bool(d.get("sellable", true)):
		return 0
	var p := get_sell_price(id) if price < 0 else price
	remove_item(id, 1)
	add_item(&"cap", p)
	return p


# =============================================================================================
# Buffs
# =============================================================================================

## Adds/refreshes a timed buff. hours < 0 → default duration from skills.json "buffs".
func add_buff(id: StringName, hours: float = -1.0, modifiers: Dictionary = {}) -> void:
	var def := get_buff_def(id)
	var h := hours if hours > 0.0 else float(def.get("hours", 1.0))
	var mods: Dictionary = modifiers if not modifiers.is_empty() else def.get("modifiers", {})
	var was := _buffs.has(String(id))
	_buffs[String(id)] = {"modifiers": mods.duplicate(), "expires": _abs_minutes() + h * 60.0,
		"name_key": String(def.get("name_key", "BUFF_" + String(id).to_upper()))}
	if not was:
		GameEvents.buff_changed.emit(id, true)


func remove_buff(id: StringName) -> void:
	if _buffs.erase(String(id)):
		GameEvents.buff_changed.emit(id, false)


func has_buff(id: StringName) -> bool:
	return _buffs.has(String(id))


func get_buffs() -> Dictionary:
	return _buffs.duplicate(true)


## Game minutes left on a buff (0 if inactive).
func get_buff_remaining_minutes(id: StringName) -> float:
	if not has_buff(id):
		return 0.0
	return maxf(0.0, float(_buffs[String(id)]["expires"]) - _abs_minutes())


func _expire_buffs() -> void:
	var now := _abs_minutes()
	for id: String in _buffs.keys():
		if float(_buffs[id]["expires"]) <= now:
			_buffs.erase(id)
			GameEvents.buff_changed.emit(StringName(id), false)


func _abs_minutes() -> float:
	var tod := _tod()
	return tod.get_absolute_minutes() if tod != null else 0.0


# =============================================================================================
# Flags / reputation / counters / world state
# =============================================================================================

func set_flag(flag: StringName, value: Variant = true) -> void:
	var k := String(flag)
	if _flags.has(k) and typeof(_flags[k]) == typeof(value) and _flags[k] == value:
		return
	_flags[k] = value
	GameEvents.flag_changed.emit(flag, value)


func get_flag(flag: StringName, default: Variant = false) -> Variant:
	return _flags.get(String(flag), default)


func has_flag(flag: StringName) -> bool:
	return _flags.has(String(flag))


func clear_flag(flag: StringName) -> void:
	if _flags.erase(String(flag)):
		GameEvents.flag_changed.emit(flag, null)


func get_flags() -> Dictionary:
	return _flags.duplicate(true)


func get_reputation(faction: StringName) -> int:
	return int(_reputation.get(String(faction), 0))


## Positive gains are scaled by rep_gain_mult (charm). Emits reputation_changed.
func add_reputation(faction: StringName, delta: int) -> void:
	var d := float(delta)
	if d > 0.0:
		d *= get_modifier(&"rep_gain_mult")
	var v := clampi(get_reputation(faction) + roundi(d), REPUTATION_MIN, REPUTATION_MAX)
	_reputation[String(faction)] = v
	GameEvents.reputation_changed.emit(faction, v)


## &"hostile" (≤ −50) &"wary" (< −10) &"neutral" &"friendly" (≥ 25) &"beloved" (≥ 60).
func get_reputation_tier(faction: StringName) -> StringName:
	var v := get_reputation(faction)
	if v <= -50:
		return &"hostile"
	if v < -10:
		return &"wary"
	if v >= 60:
		return &"beloved"
	if v >= 25:
		return &"friendly"
	return &"neutral"


func get_counter(counter: StringName) -> int:
	return int(_counters.get(String(counter), 0))


func increment_counter(counter: StringName, n: int = 1) -> int:
	return set_counter(counter, get_counter(counter) + n)


func set_counter(counter: StringName, value: int) -> int:
	var changed := int(_counters.get(String(counter), 0)) != value
	_counters[String(counter)] = value
	_check_achievements(String(counter))
	if changed:
		GameEvents.counter_changed.emit(counter, value)
	return value


func get_world_state(id: StringName) -> Dictionary:
	return _world.get(String(id), {})


func set_world_state(id: StringName, data: Dictionary) -> void:
	_world[String(id)] = data.duplicate(true)


func has_achievement(id: StringName) -> bool:
	return _achievements.has(String(id))


func get_achievements() -> PackedStringArray:
	return PackedStringArray(_achievements.keys())


func _check_achievements(counter: String) -> void:
	for id: String in ACHIEVEMENTS:
		var a: Dictionary = ACHIEVEMENTS[id]
		if String(a["counter"]) != counter or _achievements.has(id):
			continue
		if get_counter(StringName(counter)) >= int(a["target"]):
			_achievements[id] = true
			set_flag(StringName("ach_" + id), true)
			GameEvents.achievement_unlocked.emit(StringName(id))
			GameEvents.notify.emit(tr("NOTIFY_ACHIEVEMENT").format({"name": tr("ACH_" + id.to_upper())}), &"achievement")
			add_xp(int(XP_REWARDS["achievement"]), "achievement")


# =============================================================================================
# Locations, collectibles, territory, naps, knocks, prey
# =============================================================================================

func discover_location(id: StringName, display_name: String = "") -> bool:
	var k := String(id)
	current_area = id
	if _locations.has(k):
		return false
	var dn := display_name if display_name != "" else tr("LOC_" + k.to_upper())
	_locations[k] = dn
	GameEvents.location_discovered.emit(id, dn)
	GameEvents.notify.emit(tr("NOTIFY_LOCATION_DISCOVERED").format({"name": dn}), &"location")
	add_xp(int(XP_REWARDS["location"]), "location")
	increment_counter(&"locations_discovered")
	return true


func is_location_discovered(id: StringName) -> bool:
	return _locations.has(String(id))


func get_discovered_locations() -> Dictionary:
	return _locations.duplicate()


func _poll_locations() -> void:
	var player := get_player()
	if player == null:
		return
	var p: Vector3 = player.global_position
	for n in get_tree().get_nodes_in_group(&"location"):
		var n3 := n as Node3D
		if n3 == null or not n3.has_meta(&"location_id"):
			continue
		var r := float(n3.get_meta(&"radius", 8.0))
		if n3.global_position.distance_to(p) <= r:
			var lid := StringName(str(n3.get_meta(&"location_id")))
			current_area = lid
			if not is_location_discovered(lid):
				var key := str(n3.get_meta(&"display_name_key", "LOC_" + String(lid).to_upper()))
				discover_location(lid, tr(key))


## Records a found collectible (memory photo, cap stash...). Returns true when new.
func mark_collectible(id: StringName) -> bool:
	var k := String(id)
	if _collectibles.has(k):
		return false
	_collectibles[k] = _day()
	increment_counter(&"collectibles_found")
	GameEvents.collectible_found.emit(id)
	return true


func is_collectible_found(id: StringName) -> bool:
	return _collectibles.has(String(id))


func count_collectibles(prefix: String = "") -> int:
	if prefix == "":
		return _collectibles.size()
	var c := 0
	for k: String in _collectibles:
		if k.begins_with(prefix):
			c += 1
	return c


## Scent-mark a territory spot. Returns true when newly marked.
func mark_territory(spot_id: StringName) -> bool:
	var k := String(spot_id)
	if _territory.has(k):
		return false
	_territory[k] = _day()
	set_counter(&"territory_marked", _territory.size())
	GameEvents.territory_marked.emit(spot_id)
	return true


func is_territory_marked(spot_id: StringName) -> bool:
	return _territory.has(String(spot_id))


func get_marked_territory() -> PackedStringArray:
	return PackedStringArray(_territory.keys())


## Sleep at a nap spot: fast-forwards time, restores vitals (sleep rates), records the spot as
## the faint-respawn point, first-time XP, autosave. opts: sheltered, warmth_bonus, energy_mult,
## until_hour (≥0 → sleep until that hour instead of `hours`). Returns hours slept.
func nap(hours: float, spot_id: StringName = &"", wake_transform: Variant = null, opts: Dictionary = {}) -> float:
	if is_fainted:
		return 0.0
	_sleep_ctx = {
		"sheltered": bool(opts.get("sheltered", true)),
		"warmth_bonus": float(opts.get("warmth_bonus", 0.0)),
		"energy_mult": float(opts.get("energy_mult", 1.0)),
	}
	var slept := 0.0
	var tod := _tod()
	var until_h := float(opts.get("until_hour", -1.0))
	if tod != null:
		# "Sleep until X" when it's (almost) X already → an ordinary nap of `hours`.
		if until_h >= 0.0 and tod.hours_until(until_h) >= 0.25:
			slept = tod.sleep_until(until_h)
		else:
			slept = tod.skip_hours(hours)
	else:
		slept = hours
		_on_time_skipped(hours)
	_sleep_ctx = {}
	if spot_id != &"":
		var k := String(spot_id)
		var first := not _nap_spots.has(k)
		_nap_spots[k] = int(_nap_spots.get(k, 0)) + 1
		_last_nap_spot = spot_id
		if wake_transform is Transform3D:
			_last_nap_transform = wake_transform
		if first:
			add_xp(int(XP_REWARDS["nap_first"]), "nap")
		set_counter(&"nap_spots_unique", _nap_spots.size())
	if bool(opts.get("sheltered", true)) and slept >= 1.0:
		add_buff(&"warm_nap")
	increment_counter(&"naps")
	GameEvents.cat_napped.emit(spot_id, slept)
	autosave("nap")
	return slept


func get_last_nap_spot() -> StringName:
	return _last_nap_spot


## Transform3D of the last nap spot, or null if Cam hasn't napped yet.
func get_last_nap_transform() -> Variant:
	return _last_nap_transform


func set_respawn_point(spot_id: StringName, xform: Transform3D) -> void:
	_last_nap_spot = spot_id
	_last_nap_transform = xform


## Called by Pushable when a knocked object falls off a ledge. Returns true if first time.
func register_knock(object_id: StringName) -> bool:
	increment_counter(&"knocked_objects")
	var key := "knocked:" + String(object_id)
	if _world.has(key):
		return false
	_world[key] = {"day": _day()}
	add_xp(int(XP_REWARDS["knock_first"]), "knock")
	increment_counter(&"knocked_unique")
	return true


## Called by the player / prey AI when Cam catches (and releases) prey.
func register_prey_catch(prey_kind: StringName) -> void:
	increment_counter(&"prey_caught")
	increment_counter(StringName("prey_" + String(prey_kind)))
	add_xp(roundi(float(XP_REWARDS["prey"]) * get_modifier(&"prey_xp_mult")), "prey")
	if prey_kind == &"pigeon" and randf() < 0.5:
		add_item(&"pigeon_feather", 1)
	GameEvents.prey_caught.emit(prey_kind)


# =============================================================================================
# Faint & revive
# =============================================================================================

func _check_faint() -> void:
	if is_fainted:
		return
	if get_stat(&"health") <= 0.0:
		_request_faint(_last_damage_source)
	elif get_stat(&"energy") <= 0.0:
		_request_faint(&"exhaustion")


func _request_faint(cause: StringName) -> void:
	if _faint_queued:
		return
	_faint_queued = true
	_deferred_faint.call_deferred(cause)


func _deferred_faint(cause: StringName) -> void:
	_faint_queued = false
	if get_stat(&"health") <= 0.0 or get_stat(&"energy") <= 0.0:
		faint(cause)


## Cam faints: loses a few caps (unless a free "Nine Lives" faint is available), then wakes
## at the last nap spot after `faint_wake_delay` seconds and `faint_hours` game hours.
func faint(cause: StringName = &"exhaustion", immediate: bool = false) -> void:
	_faint_queued = false
	if is_fainted:
		return
	is_fainted = true
	var caps_lost := 0
	var free_faints := int(floor(get_modifier(&"free_faints_per_day")))
	if faints_today < free_faints:
		GameEvents.notify.emit(tr("NOTIFY_NINE_LIVES"), &"skill")
	else:
		var caps := get_caps()
		if caps > 0:
			caps_lost = clampi(ceili(float(caps) * 0.1 * get_modifier(&"faint_cap_loss_mult")), 0, 15)
			if caps_lost > 0:
				remove_item(&"cap", caps_lost)
	faints_today += 1
	increment_counter(&"faints")
	var player := get_player()
	if player != null and player.has_method("set_input_enabled"):
		player.call("set_input_enabled", false)
	GameEvents.player_died.emit()
	GameEvents.player_fainted.emit(cause, caps_lost)
	if immediate or faint_wake_delay <= 0.0:
		_wake_from_faint()
	else:
		get_tree().create_timer(faint_wake_delay, false).timeout.connect(_wake_from_faint)


func _wake_from_faint() -> void:
	if not is_fainted:
		return
	var tod := _tod()
	_sleep_ctx = {"sheltered": true, "energy_mult": 0.5}
	if tod != null:
		tod.skip_hours(faint_hours)
	_sleep_ctx = {}
	_stats["health"] = maxf(get_stat(&"health"), get_stat_max(&"health") * 0.35)
	_stats["energy"] = maxf(get_stat(&"energy"), 40.0)
	_stats["warmth"] = maxf(get_stat(&"warmth"), 50.0)
	_stats["hunger"] = maxf(get_stat(&"hunger"), 25.0)
	wetness = 0.0
	_warning_state.clear()
	is_fainted = false
	var xf := get_respawn_transform()
	var player := get_player()
	if player != null:
		if player.has_method("teleport"):
			player.call("teleport", xf)
		else:
			player.global_transform = xf
		if player.has_method("set_input_enabled"):
			player.call("set_input_enabled", true)
	for s in STATS:
		_emit_stat(s, true)
	GameEvents.player_revived.emit(xf)
	GameEvents.notify.emit(tr("NOTIFY_WOKE_UP"), &"faint")


## Where Cam wakes up after fainting: last nap spot, else the PlayerSpawn marker, else origin.
func get_respawn_transform() -> Transform3D:
	if _last_nap_transform is Transform3D:
		return _last_nap_transform
	var spawn := get_tree().get_first_node_in_group(&"player_spawn") as Node3D
	if spawn != null:
		return spawn.global_transform
	return Transform3D.IDENTITY


# =============================================================================================
# Save / load
# =============================================================================================

func register_save_provider(key: String, obj: Object) -> void:
	_providers[key] = obj
	if _pending_provider_data.has(key) and obj.has_method("load_save_data"):
		var d: Variant = _pending_provider_data[key]
		_pending_provider_data.erase(key)
		obj.call("load_save_data", d if d is Dictionary else {})


func unregister_save_provider(key: String) -> void:
	_providers.erase(key)


func get_save_path(slot: int) -> String:
	return save_dir.path_join("slot_%d.json" % slot)


func has_save(slot: int = 0) -> bool:
	return FileAccess.file_exists(get_save_path(slot))


## Deletes a slot together with its backup (otherwise load_game would restore the backup).
func delete_save(slot: int) -> bool:
	var p := get_save_path(slot)
	var existed := FileAccess.file_exists(p)
	for f in [p, p + ".bak", p + ".tmp"]:
		if FileAccess.file_exists(f):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(f))
	return existed


## Summary for the load menu: {exists, version, saved_at, playtime_s, level, day, hour, location, quest}.
func get_save_info(slot: int) -> Dictionary:
	var d := _read_save_file(get_save_path(slot))
	if d.is_empty():
		return {"exists": false, "slot": slot}
	var info: Dictionary = (d.get("summary", {}) as Dictionary).duplicate()
	info["exists"] = true
	info["slot"] = slot
	info["version"] = int(d.get("version", 0))
	info["saved_at"] = String(d.get("saved_at", ""))
	info["playtime_s"] = float(d.get("playtime_s", 0.0))
	return info


## Saves to the autosave slot. Calls closer together than autosave_min_interval_s are
## coalesced: the save is deferred until the interval has passed (never dropped).
func autosave(reason: String = "") -> bool:
	if not autosave_enabled:
		return false
	var now := Time.get_ticks_msec()
	if now - _last_autosave_msec < int(autosave_min_interval_s * 1000.0):
		_autosave_pending = true
		return false
	_autosave_pending = false
	_last_autosave_msec = now
	var ok := save_game(AUTOSAVE_SLOT)
	if ok and reason != "":
		print_verbose("GameState: autosaved (%s)" % reason)
	return ok


func build_save_data() -> Dictionary:
	var state := {
		"stats": _stats.duplicate(),
		"attributes": _attributes.duplicate(),
		"attribute_points": attribute_points,
		"xp": xp,
		"level": level,
		"skill_points": skill_points,
		"skills": _skills.keys(),
		"items": _items.duplicate(),
		"mouth_item": String(mouth_item),
		"equipped": _equipped.duplicate(),
		"flags": _flags.duplicate(true),
		"reputation": _reputation.duplicate(),
		"locations": _locations.duplicate(),
		"collectibles": _collectibles.duplicate(),
		"territory": _territory.duplicate(),
		"nap_spots": _nap_spots.duplicate(),
		"last_nap_spot": String(_last_nap_spot),
		"last_nap_transform": _xform_to_array(_last_nap_transform) if _last_nap_transform is Transform3D else null,
		"counters": _counters.duplicate(),
		"achievements": _achievements.keys(),
		"buffs": _buffs.duplicate(true),
		"world": _world.duplicate(true),
		"wetness": wetness,
		"faints_today": faints_today,
		"current_area": String(current_area),
	}
	var providers := _pending_provider_data.duplicate(true)
	for key: String in _providers.keys():
		var p: Object = _providers[key]
		if is_instance_valid(p) and p.has_method("get_save_data"):
			providers[key] = p.call("get_save_data")
		elif not is_instance_valid(p):
			_providers.erase(key)
	var player := get_player()
	var pxf: Variant = null
	if player != null:
		pxf = _xform_to_array(player.global_transform)
	elif _pending_player_transform is Transform3D:
		pxf = _xform_to_array(_pending_player_transform)
	var weather := {"kind": String(_weather_kind), "intensity": _weather_intensity}
	var wnode := get_tree().get_first_node_in_group(&"weather")
	if wnode != null and wnode.has_method("get_weather"):
		weather["kind"] = String(wnode.call("get_weather"))
		if wnode.has_method("get_intensity"):
			weather["intensity"] = float(wnode.call("get_intensity"))
	var tod := _tod()
	var summary := {
		"level": level, "caps": get_caps(),
		"day": tod.day if tod != null else 1, "hour": tod.hour if tod != null else 0.0,
		"location": String(_locations.get(String(current_area), "")),
		"quest": "",
	}
	var qm := get_node_or_null(^"/root/QuestManager")
	if qm != null and qm.has_method("get_tracked"):
		summary["quest"] = String(qm.call("get_tracked"))
	return {
		"game": "meo_cam",
		"version": SAVE_VERSION,
		"saved_at": Time.get_datetime_string_from_system(false, true),
		"saved_at_unix": Time.get_unix_time_from_system(),
		"playtime_s": playtime_s,
		"summary": summary,
		"state": state,
		"player_transform": pxf,
		"weather": weather,
		"providers": providers,
	}


func save_game(slot: int = 0) -> bool:
	var data := build_save_data()
	var dir_abs := ProjectSettings.globalize_path(save_dir)
	if DirAccess.make_dir_recursive_absolute(dir_abs) != OK and not DirAccess.dir_exists_absolute(dir_abs):
		push_error("GameState.save_game: cannot create " + save_dir)
		return false
	var path := get_save_path(slot)
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		push_error("GameState.save_game: cannot write %s (%s)" % [tmp, error_string(FileAccess.get_open_error())])
		return false
	f.store_string(JSON.stringify(data, "\t", false))
	f.close()
	var abs_path := ProjectSettings.globalize_path(path)
	if FileAccess.file_exists(path):
		var bak := abs_path + ".bak"
		if FileAccess.file_exists(path + ".bak"):
			DirAccess.remove_absolute(bak)
		DirAccess.rename_absolute(abs_path, bak)
	if DirAccess.rename_absolute(ProjectSettings.globalize_path(tmp), abs_path) != OK:
		push_error("GameState.save_game: rename failed for " + path)
		return false
	GameEvents.game_saved.emit(slot)
	return true


func load_game(slot: int = 0) -> bool:
	var path := get_save_path(slot)
	var data := _read_save_file(path)
	if data.is_empty():
		data = _read_save_file(path + ".bak")
		if data.is_empty():
			return false
		push_warning("GameState.load_game: main save unreadable, loaded backup")
	apply_save_data(data)
	GameEvents.game_loaded.emit(slot)
	return true


func _read_save_file(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		push_warning("GameState: corrupt save " + path)
		return {}
	var d: Dictionary = parsed
	if not d.has("state") and not d.has("version"):
		return {}
	return d


## Applies a save dictionary (robust to missing keys / older versions).
func apply_save_data(data: Dictionary) -> void:
	data = _migrate(data)
	_reset_state()
	var s: Dictionary = _dict(data.get("state"))
	var stats := _dict(s.get("stats"))
	for st in STATS:
		_stats[String(st)] = float(stats.get(String(st), BASE_STAT_MAX))
	var attrs := _dict(s.get("attributes"))
	for a: String in START_ATTRIBUTES:
		_attributes[a] = clampi(int(attrs.get(a, START_ATTRIBUTES[a])), ATTRIBUTE_MIN, ATTRIBUTE_MAX)
	attribute_points = maxi(0, int(s.get("attribute_points", 0)))
	xp = maxi(0, int(s.get("xp", 0)))
	level = clampi(int(s.get("level", 1)), 1, MAX_LEVEL)
	skill_points = maxi(0, int(s.get("skill_points", START_SKILL_POINTS)))
	for id: Variant in _arr(s.get("skills")):
		if _skill_defs.has(String(id)):
			_skills[String(id)] = true
	var items := _dict(s.get("items"))
	for id: String in items:
		var n := int(items[id])
		if n > 0:
			_items[id] = n
	var mi := String(s.get("mouth_item", ""))
	mouth_item = StringName(mi) if (mi != "" and _items.has(mi)) else &""
	_equipped = _dict(s.get("equipped")).duplicate()
	_flags = _dict(s.get("flags")).duplicate(true)
	var rep := _dict(s.get("reputation"))
	for f: String in rep:
		_reputation[f] = clampi(int(rep[f]), REPUTATION_MIN, REPUTATION_MAX)
	_locations = _dict(s.get("locations")).duplicate()
	_collectibles = _dict(s.get("collectibles")).duplicate()
	_territory = _dict(s.get("territory")).duplicate()
	var naps := _dict(s.get("nap_spots"))
	for k: String in naps:
		_nap_spots[k] = int(naps[k])
	_last_nap_spot = StringName(String(s.get("last_nap_spot", "")))
	_last_nap_transform = _array_to_xform(s.get("last_nap_transform"))
	var counters := _dict(s.get("counters"))
	for k: String in counters:
		_counters[k] = int(counters[k])
	for a: Variant in _arr(s.get("achievements")):
		_achievements[String(a)] = true
	var buffs := _dict(s.get("buffs"))
	for k: String in buffs:
		var b := _dict(buffs[k])
		if not b.is_empty():
			_buffs[k] = {"modifiers": _dict(b.get("modifiers")), "expires": float(b.get("expires", 0.0)),
				"name_key": String(b.get("name_key", ""))}
	_world = _dict(s.get("world")).duplicate(true)
	wetness = clampf(float(s.get("wetness", 0.0)), 0.0, 1.0)
	faints_today = int(s.get("faints_today", 0))
	current_area = StringName(String(s.get("current_area", "")))
	playtime_s = float(data.get("playtime_s", 0.0))
	_rebuild_skill_cache()
	for st in STATS:
		_stats[String(st)] = clampf(get_stat(st), 0.0, get_stat_max(st))
	# Providers (time, quests, dialogue, world systems...). Unregistered ones stay pending.
	_pending_provider_data.clear()
	var providers := _dict(data.get("providers"))
	for key: String in providers:
		var p: Object = _providers.get(key)
		if p != null and is_instance_valid(p) and p.has_method("load_save_data"):
			p.call("load_save_data", _dict(providers[key]))
		else:
			_pending_provider_data[key] = providers[key]
	for key: String in _providers:
		if not providers.has(key):
			var p2: Object = _providers[key]
			if is_instance_valid(p2) and p2.has_method("load_save_data"):
				p2.call("load_save_data", {})
	# Weather
	var w := _dict(data.get("weather"))
	if not w.is_empty():
		_pending_weather = {"kind": String(w.get("kind", "clear")), "intensity": float(w.get("intensity", 0.0))}
		set_weather_state(StringName(_pending_weather["kind"]), float(_pending_weather["intensity"]))
		_apply_pending_weather()
	# Player transform
	_pending_player_transform = _array_to_xform(data.get("player_transform"))
	var player := get_player()
	if player != null and _pending_player_transform is Transform3D:
		_apply_player_transform(player)
	for st in STATS:
		_emit_stat(st, true)


func _migrate(data: Dictionary) -> Dictionary:
	var v := int(data.get("version", 0))
	if v > SAVE_VERSION:
		push_warning("GameState: save version %d is newer than %d; loading best-effort" % [v, SAVE_VERSION])
	# v0 (pre-release) saves stored the state at the top level.
	if v == 0 and not data.has("state"):
		data = {"version": SAVE_VERSION, "state": data}
	return data


## Transform from the last load not yet applied to a player (the game scene can consume it).
func get_pending_player_transform() -> Variant:
	return _pending_player_transform


func consume_pending_player_transform() -> Variant:
	var t: Variant = _pending_player_transform
	_pending_player_transform = null
	return t


func _on_player_spawned(player: Node3D) -> void:
	if _pending_player_transform is Transform3D:
		_apply_player_transform(player)
	_apply_pending_weather()


func _apply_player_transform(player: Node3D) -> void:
	var xf: Transform3D = _pending_player_transform
	_pending_player_transform = null
	if player.has_method("teleport"):
		player.call("teleport", xf)
	else:
		player.global_transform = xf
		player.reset_physics_interpolation()


func _apply_pending_weather() -> void:
	if _pending_weather.is_empty():
		return
	var wnode := get_tree().get_first_node_in_group(&"weather")
	if wnode != null and wnode.has_method("set_weather"):
		wnode.call("set_weather", StringName(_pending_weather["kind"]), float(_pending_weather["intensity"]))
		_pending_weather = {}


# =============================================================================================
# Helpers
# =============================================================================================

func get_player() -> Node3D:
	if not is_inside_tree():
		return null
	return get_tree().get_first_node_in_group(&"player") as Node3D


func _tod() -> Node:
	return get_node_or_null(^"/root/TimeOfDay")


func _day() -> int:
	var tod := _tod()
	return int(tod.day) if tod != null else 1


static func _dict(v: Variant) -> Dictionary:
	return v if v is Dictionary else {}


static func _arr(v: Variant) -> Array:
	return v if v is Array else []


static func _xform_to_array(t: Transform3D) -> Array:
	var b := t.basis
	return [b.x.x, b.x.y, b.x.z, b.y.x, b.y.y, b.y.z, b.z.x, b.z.y, b.z.z, t.origin.x, t.origin.y, t.origin.z]


static func _array_to_xform(v: Variant) -> Variant:
	if not v is Array or (v as Array).size() != 12:
		return null
	var a: Array = v
	for e: Variant in a:
		if typeof(e) != TYPE_FLOAT and typeof(e) != TYPE_INT:
			return null
	var b := Basis(Vector3(a[0], a[1], a[2]), Vector3(a[3], a[4], a[5]), Vector3(a[6], a[7], a[8]))
	return Transform3D(b, Vector3(a[9], a[10], a[11]))
