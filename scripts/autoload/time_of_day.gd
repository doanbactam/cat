extends Node
## TimeOfDay — game clock (owner: systems).
##
## `hour` 0..24, `day` counter (day 1 = the first morning), `time_scale` in game-minutes per real
## second (1.0 ⇒ a full day lasts 24 real minutes). Emits GameEvents.time_tick every in-game
## minute, phase_of_day_changed, day_changed, and time_skipped when sleeping fast-forwards.
## The Mid-Autumn lantern festival ("Đêm hội") falls on `festival_day`; the moon is full then.

const MINUTES_PER_DAY := 1440.0
const START_HOUR := 6.0
const START_DAY := 1
## Hanoi, mid-September (Mid-Autumn): sunrise ≈ 05:50, sunset ≈ 18:05.
const SUNRISE := 5.85
const SUNSET := 18.1
## Phase boundaries (hours): dawn [5.0, 6.75) · day [6.75, 17.25) · dusk [17.25, 18.75) · night.
const DAWN_START := 5.0
const DAY_START := 6.75
const DUSK_START := 17.25
const NIGHT_START := 18.75
const LUNAR_CYCLE_DAYS := 29.53
## Max time_tick signals emitted in one frame when time runs very fast (the rest are coalesced).
const MAX_TICKS_PER_FRAME := 30

var hour: float = START_HOUR
var day: int = START_DAY
var time_scale: float = 1.0
var paused: bool = false
## Day of the lantern festival (story: the figurine vanished three days before).
var festival_day: int = 4

var _phase: StringName = &""
var _last_minute: int = -1
var _pause_reasons: Dictionary = {}


func _ready() -> void:
	_phase = get_phase()
	_last_minute = _minute_index()
	GameState.register_save_provider("time", self)


func _process(delta: float) -> void:
	if is_paused():
		return
	advance_minutes(delta * time_scale)


# --- pausing -------------------------------------------------------------------------------------

## True when the clock is stopped (manual `paused` or any push_pause() reason).
func is_paused() -> bool:
	return paused or not _pause_reasons.is_empty()


## Stack-style pause used by dialogue/cutscenes so they never fight over `paused`.
func push_pause(reason: StringName) -> void:
	_pause_reasons[reason] = true


func pop_pause(reason: StringName) -> void:
	_pause_reasons.erase(reason)


# --- advancing -----------------------------------------------------------------------------------

## Advance the clock by game minutes, emitting ticks / phase / day signals along the way.
func advance_minutes(minutes: float) -> void:
	if minutes <= 0.0:
		return
	var total := hour * 60.0 + minutes
	var days_passed := int(floor(total / MINUTES_PER_DAY))
	hour = fposmod(total, MINUTES_PER_DAY) / 60.0
	for i in days_passed:
		day += 1
		GameEvents.day_changed.emit(day)
	var m := _minute_index()
	if m != _last_minute:
		var steps := m - _last_minute
		if steps < 0 or steps > MAX_TICKS_PER_FRAME:
			GameEvents.time_tick.emit(hour, day)
		else:
			for i in steps:
				GameEvents.time_tick.emit(hour, day)
		_last_minute = m
	_update_phase()


func advance_hours(hours: float) -> void:
	advance_minutes(hours * 60.0)


## Fast-forward `hours` (sleep, faint). Emits time_skipped(hours) first so vitals can simulate
## the skipped period, then the clock signals. Returns the hours skipped.
func skip_hours(hours: float) -> float:
	if hours <= 0.0:
		return 0.0
	GameEvents.time_skipped.emit(hours)
	advance_minutes(hours * 60.0)
	return hours


## Sleep until the next occurrence of `target_hour` (today if still ahead, else tomorrow).
## Returns the number of hours slept.
func sleep_until(target_hour: float) -> float:
	var h := hours_until(target_hour)
	if h <= 0.0:
		return 0.0
	return skip_hours(h)


## Hours from now until the next occurrence of target_hour (0 if already exactly there).
func hours_until(target_hour: float) -> float:
	var h := fposmod(fposmod(target_hour, 24.0) - hour, 24.0)
	return 0.0 if h < 0.0001 else h


func set_hour(h: float) -> void:
	hour = fposmod(h, 24.0)
	_last_minute = _minute_index()
	_update_phase()
	GameEvents.time_tick.emit(hour, day)


func set_time(new_day: int, new_hour: float) -> void:
	var day_changed := new_day != day
	day = maxi(1, new_day)
	if day_changed:
		GameEvents.day_changed.emit(day)
	set_hour(new_hour)


# --- queries -------------------------------------------------------------------------------------

func get_phase() -> StringName:
	return phase_for_hour(hour)


static func phase_for_hour(h: float) -> StringName:
	if h >= DAWN_START and h < DAY_START:
		return &"dawn"
	if h >= DAY_START and h < DUSK_START:
		return &"day"
	if h >= DUSK_START and h < NIGHT_START:
		return &"dusk"
	return &"night"


func is_night() -> bool:
	return get_phase() == &"night"


func is_daytime() -> bool:
	return hour >= SUNRISE and hour < SUNSET


## Sun arc progress: 0 at sunrise, 0.5 at solar noon, 1 at sunset (clamped; 0/1 at night).
func get_sun_progress() -> float:
	return clampf(get_sun_progress_unclamped(), 0.0, 1.0)


## Like get_sun_progress() but continues below 0 before sunrise and above 1 after sunset.
func get_sun_progress_unclamped() -> float:
	return (hour - SUNRISE) / (SUNSET - SUNRISE)


## Sun elevation in degrees (≈ 0 at sunrise/sunset, ~75° at noon in Hanoi in September,
## negative at night). Handy for the world's DirectionalLight3D.
func get_sun_elevation_deg() -> float:
	var p := get_sun_progress_unclamped()
	return sin(p * PI) * 75.0


## Smooth 0 (full day) .. 1 (deep night) factor including twilight.
func get_night_factor() -> float:
	var e := get_sun_elevation_deg()
	return clampf(1.0 - (e + 6.0) / 12.0, 0.0, 1.0)


## 0..1 fraction of the day (midnight = 0).
func get_day_fraction() -> float:
	return hour / 24.0


## Game minutes since day 1 00:00 (monotonic; used for buff/respawn timers).
func get_absolute_minutes() -> float:
	return float(day - 1) * MINUTES_PER_DAY + hour * 60.0


## True when `hour` lies in [from, to), wrapping over midnight (e.g. 19 → 5).
func is_hour_between(from: float, to: float) -> bool:
	return hour_in_window(hour, from, to)


static func hour_in_window(h: float, from: float, to: float) -> bool:
	var f := fposmod(from, 24.0)
	var t := fposmod(to, 24.0)
	if is_equal_approx(f, t):
		return true
	if f < t:
		return h >= f and h < t
	return h >= f or h < t


func is_festival_day() -> bool:
	return day == festival_day or bool(GameState.get_flag(&"festival_forced", false))


## Festival evening: the lantern procession runs from dusk until 23:30.
func is_festival_night() -> bool:
	return is_festival_day() and hour_in_window(hour, DUSK_START, 23.5)


func set_festival_day(d: int) -> void:
	festival_day = maxi(1, d)


func days_until_festival() -> int:
	return festival_day - day


## Lunar phase 0..1 (0 new moon, 0.5 full moon). Full on the festival night (rằm tháng Tám).
func get_moon_phase() -> float:
	var days := float(day - festival_day) + (hour - 20.0) / 24.0
	return fposmod(0.5 + days / LUNAR_CYCLE_DAYS, 1.0)


## Fraction of the moon disc lit (0 new .. 1 full).
func get_moon_illumination() -> float:
	return 0.5 - 0.5 * cos(get_moon_phase() * TAU)


func get_time_string() -> String:
	var total := int(floor(hour * 60.0))
	return "%02d:%02d" % [total / 60, total % 60]


# --- save provider -------------------------------------------------------------------------------

func get_save_data() -> Dictionary:
	return {"hour": hour, "day": day, "time_scale": time_scale, "festival_day": festival_day}


func load_save_data(d: Dictionary) -> void:
	day = maxi(1, int(d.get("day", START_DAY)))
	hour = fposmod(float(d.get("hour", START_HOUR)), 24.0)
	time_scale = maxf(0.0, float(d.get("time_scale", 1.0)))
	festival_day = maxi(1, int(d.get("festival_day", 4)))
	_last_minute = _minute_index()
	_update_phase(true)
	GameEvents.time_tick.emit(hour, day)


func reset_state() -> void:
	load_save_data({})
	_pause_reasons.clear()
	paused = false


# --- internals -----------------------------------------------------------------------------------

func _minute_index() -> int:
	return int(floor(hour * 60.0))


func _update_phase(force: bool = false) -> void:
	var p := get_phase()
	if p != _phase or force:
		_phase = p
		GameEvents.phase_of_day_changed.emit(p)
