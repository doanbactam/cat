extends "res://tests/fixtures/systems_test_base.gd"
## TimeOfDay: phases, ticks, day rollover, sleep_until, sun/moon, festival, pause stack, save.

func test_phases_cover_the_day() -> void:
	var expect := {0.0: &"night", 4.9: &"night", 5.0: &"dawn", 6.5: &"dawn", 6.75: &"day", 12.0: &"day",
		17.2: &"day", 17.25: &"dusk", 18.5: &"dusk", 18.75: &"night", 23.9: &"night"}
	for h: float in expect:
		TimeOfDay.set_hour(h)
		assert_eq(TimeOfDay.get_phase(), expect[h], "hour %.2f" % h)


func test_set_hour_wraps_and_emits_phase() -> void:
	capture(&"phase_of_day_changed")
	TimeOfDay.set_hour(12.0)
	TimeOfDay.set_hour(26.0)  # wraps to 02:00
	assert_near(TimeOfDay.hour, 2.0)
	assert_eq(TimeOfDay.get_phase(), &"night")
	var ev := events_named(&"phase_of_day_changed")
	assert_true(ev.size() >= 1 and ev[-1][1] == &"night", "phase signal")


func test_ticks_every_game_minute() -> void:
	capture(&"time_tick")
	TimeOfDay.set_hour(10.0)
	_events.clear()
	TimeOfDay.advance_minutes(5.0)
	assert_eq(events_named(&"time_tick").size(), 5, "5 minutes → 5 ticks")
	TimeOfDay.advance_minutes(0.4)
	TimeOfDay.advance_minutes(0.4)
	assert_eq(events_named(&"time_tick").size(), 5, "sub-minute → no tick yet")
	TimeOfDay.advance_minutes(0.4)
	assert_eq(events_named(&"time_tick").size(), 6)


func test_day_rollover() -> void:
	capture(&"day_changed")
	TimeOfDay.set_time(1, 23.5)
	TimeOfDay.advance_hours(1.0)
	assert_eq(TimeOfDay.day, 2)
	assert_near(TimeOfDay.hour, 0.5)
	assert_eq(events_named(&"day_changed").size(), 1)
	TimeOfDay.advance_hours(48.0)
	assert_eq(TimeOfDay.day, 4)


func test_sleep_until_next_morning() -> void:
	capture(&"time_skipped")
	TimeOfDay.set_time(1, 22.0)
	var slept := TimeOfDay.sleep_until(6.0)
	assert_near(slept, 8.0)
	assert_eq(TimeOfDay.day, 2)
	assert_near(TimeOfDay.hour, 6.0)
	assert_eq(events_named(&"time_skipped").size(), 1)
	TimeOfDay.set_time(2, 6.0)
	assert_near(TimeOfDay.sleep_until(6.0), 0.0, 0.001, "already there")
	TimeOfDay.set_time(2, 9.0)
	assert_near(TimeOfDay.sleep_until(13.5), 4.5)


func test_hour_window_wraps_midnight() -> void:
	assert_true(TimeOfDay.hour_in_window(23.0, 19.0, 5.0))
	assert_true(TimeOfDay.hour_in_window(2.0, 19.0, 5.0))
	assert_false(TimeOfDay.hour_in_window(12.0, 19.0, 5.0))
	assert_true(TimeOfDay.hour_in_window(9.0, 8.0, 10.0))
	assert_false(TimeOfDay.hour_in_window(10.0, 8.0, 10.0), "end exclusive")


func test_sun_and_night_factor() -> void:
	TimeOfDay.set_hour(TimeOfDay.SUNRISE)
	assert_near(TimeOfDay.get_sun_progress(), 0.0)
	TimeOfDay.set_hour((TimeOfDay.SUNRISE + TimeOfDay.SUNSET) * 0.5)
	assert_near(TimeOfDay.get_sun_progress(), 0.5)
	assert_true(TimeOfDay.get_sun_elevation_deg() > 70.0, "high noon sun")
	assert_near(TimeOfDay.get_night_factor(), 0.0)
	TimeOfDay.set_hour(23.0)
	assert_near(TimeOfDay.get_sun_progress(), 1.0, 0.001, "clamped after sunset")
	assert_near(TimeOfDay.get_night_factor(), 1.0)
	assert_true(TimeOfDay.get_sun_elevation_deg() < 0.0)


func test_festival_and_full_moon() -> void:
	TimeOfDay.set_festival_day(4)
	TimeOfDay.set_time(3, 20.0)
	assert_false(TimeOfDay.is_festival_day())
	assert_eq(TimeOfDay.days_until_festival(), 1)
	TimeOfDay.set_time(4, 20.0)
	assert_true(TimeOfDay.is_festival_day())
	assert_true(TimeOfDay.is_festival_night())
	assert_near(TimeOfDay.get_moon_phase(), 0.5, 0.001, "full moon on festival night")
	assert_near(TimeOfDay.get_moon_illumination(), 1.0, 0.001)
	TimeOfDay.set_time(4, 10.0)
	assert_false(TimeOfDay.is_festival_night(), "festival night starts at dusk")
	TimeOfDay.set_time(2, 20.0)
	GameState.set_flag(&"festival_forced", true)
	assert_true(TimeOfDay.is_festival_day(), "story can force the festival")


func test_pause_stack() -> void:
	TimeOfDay.paused = false
	assert_false(TimeOfDay.is_paused())
	TimeOfDay.push_pause(&"dialogue")
	TimeOfDay.push_pause(&"cutscene")
	assert_true(TimeOfDay.is_paused())
	TimeOfDay.pop_pause(&"dialogue")
	assert_true(TimeOfDay.is_paused())
	TimeOfDay.pop_pause(&"cutscene")
	assert_false(TimeOfDay.is_paused())
	TimeOfDay.paused = true


func test_real_time_advances_with_time_scale() -> void:
	TimeOfDay.set_time(1, 10.0)
	TimeOfDay.paused = false
	TimeOfDay.time_scale = 60.0  # 1 game hour per real second
	await tree.create_timer(0.25).timeout
	TimeOfDay.paused = true
	TimeOfDay.time_scale = 1.0
	var advanced := TimeOfDay.hour - 10.0
	assert_true(advanced > 0.15 and advanced < 0.6, "advanced %.3f h in 0.25 s" % advanced)


func test_time_string_and_absolute_minutes() -> void:
	TimeOfDay.set_time(3, 7.5)
	assert_eq(TimeOfDay.get_time_string(), "07:30")
	assert_near(TimeOfDay.get_absolute_minutes(), 2 * 1440.0 + 450.0)


func test_save_provider_round_trip() -> void:
	TimeOfDay.set_time(3, 21.25)
	TimeOfDay.time_scale = 2.0
	var d := TimeOfDay.get_save_data()
	TimeOfDay.set_time(1, 6.0)
	TimeOfDay.time_scale = 1.0
	TimeOfDay.load_save_data(d)
	assert_eq(TimeOfDay.day, 3)
	assert_near(TimeOfDay.hour, 21.25)
	assert_near(TimeOfDay.time_scale, 2.0)
	TimeOfDay.load_save_data({})
	assert_eq(TimeOfDay.day, 1, "missing keys → defaults")
	assert_near(TimeOfDay.hour, TimeOfDay.START_HOUR)
	TimeOfDay.time_scale = 1.0
