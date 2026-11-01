extends "res://tests/fixtures/systems_test_base.gd"
## Vitals simulation: hunger/energy/warmth/health, shelter & rain, faint & revive.

func test_hunger_drains_about_one_per_hour_idle_and_more_running() -> void:
	GameState.set_activity(&"idle")
	GameState.simulate(10.0)
	assert_near(GameState.get_stat(&"hunger"), 90.0, 0.01, "idle ≈ 1/h")
	GameState.set_stat(&"hunger", 100.0)
	GameState.set_activity(&"run")
	GameState.simulate(10.0)
	assert_near(GameState.get_stat(&"hunger"), 80.0, 0.01, "running ≈ 2/h (≈1 more)")


func test_player_state_maps_to_activity() -> void:
	GameEvents.player_state_changed.emit(&"idle", &"sprint")
	assert_eq(GameState.activity, &"run")
	GameEvents.player_state_changed.emit(&"sprint", &"climbing_wall")
	assert_eq(GameState.activity, &"climb", "fuzzy match")
	GameEvents.player_state_changed.emit(&"x", &"sit_idle")
	assert_eq(GameState.activity, &"rest")
	GameEvents.player_state_changed.emit(&"x", &"wobble")
	assert_eq(GameState.activity, &"idle", "unknown → idle")


func test_energy_drains_with_activity_and_regains_sleeping() -> void:
	GameState.set_activity(&"run")
	GameState.simulate(5.0)
	var after_run := GameState.get_stat(&"energy")
	assert_near(after_run, 70.0, 0.01, "run drains 6/h")
	GameState.set_activity(&"walk")
	GameState.simulate(2.0)
	assert_near(GameState.get_stat(&"energy"), 67.0, 0.01)
	GameState.set_activity(&"sleep")
	GameState.simulate(1.0)
	assert_true(GameState.get_stat(&"energy") > 90.0, "sleep restores ~25/h")
	GameState.set_stat(&"energy", 50.0)
	GameEvents.player_jumped.emit(1.0)
	assert_near(GameState.get_stat(&"energy"), 49.3, 0.01, "jump costs energy")


func test_deep_sleep_skill_speeds_energy_regain() -> void:
	GameState.set_stat(&"energy", 20.0)
	GameState.set_activity(&"sleep")
	GameState.simulate(1.0)
	var base_gain := GameState.get_stat(&"energy") - 20.0
	GameState.set_stat(&"energy", 20.0)
	GameState.grant_skill(&"ngu_sau")
	GameState.simulate(1.0)
	var gain := GameState.get_stat(&"energy") - 20.0
	assert_near(gain / base_gain, 1.5, 0.01, "energy_regen +0.5")


func test_rain_wets_and_chills_unsheltered_cat() -> void:
	GameState.shelter_override = 0
	GameState.set_weather_state(&"rain", 0.8)
	GameState.simulate(1.0)
	assert_true(GameState.is_wet(), "wet in rain")
	assert_true(GameState.get_stat(&"warmth") < 95.0, "warmth drops: %f" % GameState.get_stat(&"warmth"))


func test_shelter_keeps_cat_dry_and_warm() -> void:
	GameState.shelter_override = 1
	GameState.set_weather_state(&"storm", 1.0)
	GameState.set_stat(&"warmth", 80.0)
	GameState.simulate(2.0)
	assert_false(GameState.is_wet())
	assert_true(GameState.get_stat(&"warmth") > 80.0, "recovers when dry under shelter")


func test_warmth_recovers_once_dry() -> void:
	GameState.shelter_override = 0
	GameState.set_weather_state(&"rain", 1.0)
	GameState.simulate(2.0)
	var cold := GameState.get_stat(&"warmth")
	GameState.set_weather_state(&"clear", 0.0)
	GameState.simulate(6.0)
	assert_false(GameState.is_wet(), "dried off")
	assert_true(GameState.get_stat(&"warmth") > cold + 5.0, "warmed up")


func test_thick_coat_reduces_chill() -> void:
	GameState.shelter_override = 0
	GameState.set_weather_state(&"rain", 1.0)
	GameState.simulate(1.0)
	var plain := 100.0 - GameState.get_stat(&"warmth")
	GameState.new_game()
	GameState.shelter_override = 0
	GameState.set_weather_state(&"rain", 1.0)
	GameState.grant_skill(&"long_day")
	GameState.simulate(1.0)
	var coat := 100.0 - GameState.get_stat(&"warmth")
	assert_true(coat < plain * 0.75, "coat %f vs plain %f" % [coat, plain])


func test_shelter_area_detection() -> void:
	var p := spawn_player(Vector3(10, 0, 10))
	var a := Area3D.new()
	a.add_to_group(&"shelter")
	var cs := CollisionShape3D.new()
	var b := BoxShape3D.new()
	b.size = Vector3(2, 3, 2)
	cs.shape = b
	a.add_child(cs)
	spawn(a)
	a.global_position = Vector3(10, 1, 10)
	assert_true(GameState._compute_sheltered(), "inside awning volume")
	p.global_position = Vector3(20, 0, 10)
	assert_false(GameState._compute_sheltered(), "outside")


func test_health_regen_when_fed_and_starvation_damage() -> void:
	GameState.set_stat(&"health", 50.0)
	GameState.simulate(2.0)
	assert_near(GameState.get_stat(&"health"), 54.0, 0.01, "+2/h when fed & warm")
	GameState.set_stat(&"hunger", 0.0)
	GameState.set_stat(&"health", 50.0)
	GameState.simulate(1.0)
	assert_true(GameState.get_stat(&"health") < 50.0, "starving hurts")


func test_low_vitals_make_cat_slower_and_noisier() -> void:
	var fast := GameState.get_modifier(&"sprint_speed")
	var quiet := GameState.get_modifier(&"noise_mult")
	GameState.set_stat(&"energy", 5.0)
	GameState.set_stat(&"hunger", 5.0)
	assert_true(GameState.get_modifier(&"sprint_speed") < fast * 0.85)
	assert_true(GameState.get_modifier(&"noise_mult") > quiet * 1.2)


func test_carrying_fish_slows_slightly() -> void:
	var v := GameState.get_modifier(&"move_speed")
	GameState.add_item(&"fish")
	assert_near(GameState.get_modifier(&"move_speed"), v * 0.9, 0.001)


func test_damage_signal_applies_health() -> void:
	GameEvents.player_damaged.emit(30.0, &"fall")
	assert_near(GameState.get_stat(&"health"), 70.0)


func test_low_vitals_notify_once() -> void:
	capture(&"notify")
	GameState.set_stat(&"hunger", 20.0)
	GameState.set_stat(&"hunger", 19.0)
	GameState.set_stat(&"hunger", 18.0)
	var n := events_named(&"notify").filter(func(e: Array) -> bool: return e[2] == &"hunger")
	assert_eq(n.size(), 1, "hysteresis")


func test_faint_wakes_at_last_nap_spot_and_loses_some_caps() -> void:
	var p := spawn_player(Vector3(5, 0, 5))
	capture(&"player_fainted")
	capture(&"player_revived")
	GameState.add_item(&"cap", 40)
	var nap_xf := Transform3D(Basis.IDENTITY, Vector3(1, 6, -2))
	GameState.set_respawn_point(&"roof_nap", nap_xf)
	GameState.set_stat(&"health", 0.0)
	await tree.process_frame  # faint is deferred
	assert_eq(events_named(&"player_fainted").size(), 1)
	assert_eq(GameState.get_caps(), 36, "lost 10% of caps")
	assert_eq(events_named(&"player_fainted")[0][2], 4)
	assert_eq(events_named(&"player_revived").size(), 1)
	assert_false(GameState.is_fainted)
	assert_true(p.teleported_to is Transform3D and (p.teleported_to as Transform3D).origin.is_equal_approx(Vector3(1, 6, -2)))
	assert_true(p.input_enabled)
	assert_true(GameState.get_stat(&"health") >= 35.0)
	assert_true(TimeOfDay.hour > 12.9, "time passed while passed out")


func test_exhaustion_faint_and_nine_lives() -> void:
	GameState.add_item(&"cap", 20)
	GameState.grant_skill(&"chin_mang")
	GameState.faint(&"exhaustion", true)
	assert_eq(GameState.get_caps(), 20, "first faint of the day is free with Nine Lives")
	GameState.faint(&"exhaustion", true)
	assert_eq(GameState.get_caps(), 19, "second costs caps (halved by skill: ceil(2*0.5)=1)")
	GameEvents.day_changed.emit(2)
	assert_eq(GameState.faints_today, 0, "resets daily")


func test_nap_restores_and_records_respawn() -> void:
	capture(&"cat_napped")
	GameState.set_stat(&"energy", 30.0)
	var xf := Transform3D(Basis.IDENTITY, Vector3(3, 4, 5))
	var h := GameState.nap(2.0, &"tea_stall_box", xf, {"sheltered": true})
	assert_near(h, 2.0)
	assert_true(GameState.get_stat(&"energy") > 75.0, "slept: %f" % GameState.get_stat(&"energy"))
	assert_eq(GameState.get_last_nap_spot(), &"tea_stall_box")
	assert_true((GameState.get_last_nap_transform() as Transform3D).origin.is_equal_approx(Vector3(3, 4, 5)))
	assert_eq(GameState.xp, 20, "first nap XP")
	GameState.nap(1.0, &"tea_stall_box", xf)
	assert_eq(GameState.xp, 20, "only first time")
	assert_eq(events_named(&"cat_napped").size(), 2)
	assert_true(GameState.has_buff(&"warm_nap"))
	assert_near(TimeOfDay.hour, 13.0)


func test_soak_in_water_and_groom() -> void:
	GameEvents.player_landed.emit(2.0, &"water")
	assert_near(GameState.wetness, 1.0)
	GameState.groom()
	assert_near(GameState.wetness, 0.85)
	assert_true(GameState.has_buff(&"groomed"))


func test_realtime_simulation_uses_time_scale() -> void:
	GameState.simulation_enabled = true
	TimeOfDay.paused = false
	TimeOfDay.time_scale = 600.0  # 10 game hours per real second
	GameState.set_activity(&"idle")
	await tree.create_timer(0.2).timeout
	GameState.simulation_enabled = false
	TimeOfDay.paused = true
	TimeOfDay.time_scale = 1.0
	var lost := 100.0 - GameState.get_stat(&"hunger")
	assert_true(lost > 1.0 and lost < 4.0, "lost %.2f hunger in ~2 game hours" % lost)
