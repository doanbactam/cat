extends "res://tests/test_base.gd"
## Audio area tests: bank integrity, contract API behaviour, footstep/landing/meow resolution,
## bus layout, ambience/music directors.

const REQUIRED_BUSES := [&"Master", &"Music", &"SFX", &"Ambience", &"UI", &"Voice", &"Alley", &"Temple", &"Interior", &"Market"]


func _am() -> Node:
	return tree.root.get_node("AudioManager")


func test_bank_loaded_and_large() -> void:
	var am := _am()
	var names: PackedStringArray = am.get_sound_names()
	assert_true(names.size() >= 170, "bank has %d sounds" % names.size())
	for n in ["cat_meow_short", "cat_purr_loop", "step_asphalt", "land_hard_metal", "impact_ceramic", "amb_street_day",
			"rain_heavy_loop", "thunder_near", "mus_menu", "mus_tension", "ui_click", "scooter_pass", "tokay_call"]:
		assert_true(am.has_sound(StringName(n)), "missing " + n)


func test_every_bank_file_exists_and_loads_sample() -> void:
	var am := _am()
	var missing := 0
	var total := 0
	for n in am.get_sound_names():
		var info: Dictionary = am.get_sound_info(StringName(n))
		for f: String in info.get("files", []):
			total += 1
			if not ResourceLoader.exists(f):
				missing += 1
				_failures.append("%s: file not importable %s" % [_current, f])
	assert_true(total >= 450, "variant files: %d" % total)
	assert_eq(missing, 0)
	# actually load one variant of a sample of sounds from every category
	for n in ["cat_meow_loud", "step_tile", "impact_glass_break", "amb_alley", "mus_night", "ui_level_up", "dog_bark"]:
		var s: AudioStream = am.get_stream(StringName(n))
		assert_not_null(s, "stream " + n)
		if s != null:
			assert_true(s.get_length() > 0.02, "%s length %f" % [n, s.get_length()])


func test_meow_variants_at_least_eight() -> void:
	var am := _am()
	var kinds := 0
	var variants := 0
	for n in am.get_sound_names():
		if n.begins_with("cat_meow_") or n == "cat_yowl":
			kinds += 1
			variants += am.get_variant_count(StringName(n))
	assert_true(kinds >= 8, "meow kinds %d" % kinds)
	assert_true(variants >= 24, "meow variants %d" % variants)


func test_footstep_surfaces_have_four_plus_variants() -> void:
	var am := _am()
	for s: StringName in am.SURFACES:
		var n := StringName("step_%s" % s)
		assert_true(am.has_sound(n), "missing " + String(n))
		assert_true(am.get_variant_count(n) >= 4, "%s variants" % n)


func test_loops_are_flagged_looping() -> void:
	var am := _am()
	for n in ["amb_market", "mus_morning", "cat_purr_loop", "rain_light_loop", "scooter_idle_loop"]:
		var s: AudioStream = am.get_stream(StringName(n), 0)
		assert_true(s is AudioStreamOggVorbis, n + " is ogg")
		if s is AudioStreamOggVorbis:
			assert_true((s as AudioStreamOggVorbis).loop, n + " loops")
	var one: AudioStream = am.get_stream(&"cat_meow_short", 0)
	if one is AudioStreamOggVorbis:
		assert_false((one as AudioStreamOggVorbis).loop, "one-shot must not loop")


func test_unknown_names_are_silent_noops() -> void:
	var am := _am()
	var before: int = am.active_voice_count()
	am.play_sfx(&"definitely_not_a_sound", Vector3(1, 2, 3))
	am.play_sfx(&"definitely_not_a_sound")
	am.play_ui(&"no_such_ui")
	am.play_music(&"no_such_track", 0.0)
	am.set_ambience(&"no_such_bed", 0.0)
	am.play_footstep(&"lava", Vector3.ZERO, 0.5)  # unknown surface falls back, still plays a real step
	assert_false(am.has_sound(&"definitely_not_a_sound"))
	assert_true(am._warned.has(&"definitely_not_a_sound"), "warned once")
	assert_true(am.active_voice_count() >= before)


func test_play_footstep_resolves_surfaces() -> void:
	var am := _am()
	assert_eq(am.resolve_footstep_sound(&"asphalt", 0.4), &"step_asphalt")
	assert_eq(am.resolve_footstep_sound(&"roof_tile", 0.3), &"step_roof_tile")
	assert_eq(am.resolve_footstep_sound(&"wood", 0.95), &"step_wood_run")
	assert_eq(am.resolve_footstep_sound(&"lava", 0.4), &"step_concrete")
	assert_eq(am.resolve_footstep_sound(&"", 0.4), &"step_concrete")
	assert_eq(am.resolve_footstep_sound(&"Tin", 0.4), &"step_metal")
	assert_eq(am.resolve_footstep_sound(&"puddle", 0.4), &"step_water")
	assert_eq(am.resolve_footstep_sound(&"carpet", 0.4), &"step_fabric")
	for s: StringName in am.SURFACES:
		assert_true(am.has_sound(am.resolve_footstep_sound(s, 0.4)), String(s))
		assert_true(am.has_sound(am.resolve_footstep_sound(s, 1.0)), String(s) + " run")
		am.play_footstep(s, Vector3(0, 0, -2), 0.5)


func test_landing_and_meow_resolution() -> void:
	var am := _am()
	assert_eq(am.resolve_landing_sound(&"metal", 7.0), &"land_hard_metal")
	assert_eq(am.resolve_landing_sound(&"grass", 2.0), &"land_soft_soft")
	assert_eq(am.resolve_landing_sound(&"asphalt", 3.0), &"land_soft_stone")
	assert_eq(am.resolve_landing_sound(&"roof_tile", 6.0), &"land_hard_roof")
	for s: StringName in am.SURFACES:
		assert_true(am.has_sound(am.resolve_landing_sound(s, 2.0)), "soft " + String(s))
		assert_true(am.has_sound(am.resolve_landing_sound(s, 8.0)), "hard " + String(s))
	for k in [&"short", &"chirp", &"loud", &"purr", &"question", &"demand", &"hiss", &"growl", &"weird"]:
		assert_true(am.has_sound(am.resolve_meow_sound(k)), "meow " + String(k))


func test_bus_layout() -> void:
	for b in REQUIRED_BUSES:
		assert_true(AudioServer.get_bus_index(b) >= 0, "bus " + String(b))
	assert_eq(AudioServer.get_bus_send(AudioServer.get_bus_index(&"Voice")), &"SFX")
	assert_eq(AudioServer.get_bus_send(AudioServer.get_bus_index(&"Alley")), &"SFX")
	var am := _am()
	assert_not_null(am._find_effect(&"Music", "Duck"), "music duck effect")
	assert_not_null(am._find_effect(&"SFX", "Muffle"), "sfx muffle effect")


func test_bus_levels_follow_slider() -> void:
	var am := _am()
	var idx := AudioServer.get_bus_index(&"UI")
	var prev_db := AudioServer.get_bus_volume_db(idx)
	am.set_bus_level(&"UI", 0.5)
	assert_near(AudioServer.get_bus_volume_db(idx), -12.04, 0.1)
	am.set_bus_level(&"UI", 0.0)
	assert_true(AudioServer.is_bus_mute(idx))
	am.set_bus_level(&"UI", 1.0)
	assert_false(AudioServer.is_bus_mute(idx))
	assert_near(AudioServer.get_bus_volume_db(idx), 0.0, 0.01)
	AudioServer.set_bus_volume_db(idx, prev_db)
	am._apply_volumes()


func test_pool_bounded_and_priority() -> void:
	var am := _am()
	for i in 120:
		am.play_sfx(&"step_concrete", Vector3(i * 0.7, 0, 0), -20.0)
	assert_true(am.active_voice_count() <= am.POOL_3D_SIZE + am.POOL_2D_SIZE)
	var p: Node = am.play_at(&"cat_meow_loud", Vector3(0, 0, 3))
	assert_not_null(p, "high priority voice steals a low priority one")


func test_ambience_resolution() -> void:
	var am := _am()
	assert_eq(am.area_key_for(&"hem_ba_tu"), &"alley")
	assert_eq(am.area_key_for(&"cho_hang_may"), &"market")
	assert_eq(am.area_key_for(&"ho_guong"), &"lake")
	assert_eq(am.area_key_for(&"dinh_hang_may"), &"temple")
	assert_eq(am.area_key_for(&"rooftops_west"), &"rooftop")
	assert_eq(am.area_key_for(&"something_else"), &"street")
	var r: Dictionary = am.resolve_ambience(&"street", &"day", &"clear", 0.0)
	assert_eq(r["base"][0], &"amb_street_day")
	assert_eq(r["weather"][0], &"")
	r = am.resolve_ambience(&"street", &"night", &"clear", 0.0)
	assert_eq(r["base"][0], &"amb_street_night")
	r = am.resolve_ambience(&"lake", &"night", &"rain", 0.3)
	assert_eq(r["base"][0], &"amb_lake")
	assert_eq(r["overlay"][0], &"amb_night_insects")
	assert_eq(r["weather"][0], &"rain_light_loop")
	r = am.resolve_ambience(&"alley", &"day", &"storm", 1.0, true)
	assert_eq(r["weather"][0], &"rain_heavy_loop")
	assert_eq(r["shelter"][0], &"rain_tin_loop")
	assert_eq(r["wind"][0], &"wind_storm_loop")
	r = am.resolve_ambience(&"market", &"night", &"clear", 0.0, false, true)
	assert_eq(r["base"][0], &"amb_festival")
	r = am.resolve_ambience(&"street", &"dawn", &"clear", 0.0)
	assert_eq(r["overlay"][0], &"amb_dawn_chorus")
	for layer in r:
		var nm: StringName = r[layer][0]
		if nm != &"":
			assert_true(am.has_sound(nm), "bed exists " + String(nm))


func test_events_drive_ambience_and_music() -> void:
	var am := _am()
	var ge := tree.root.get_node("GameEvents")
	ge.weather_changed.emit(&"rain", 0.8)
	assert_eq(am.get_layer_sound(&"weather"), &"rain_heavy_loop")
	ge.area_entered.emit(&"hem_7")
	assert_eq(am.get_current_ambience(), &"amb_alley")
	ge.weather_changed.emit(&"clear", 0.0)
	assert_eq(am.get_layer_sound(&"weather"), &"")
	am.set_ambience(&"amb_temple", 0.0)
	assert_eq(am.get_current_ambience(), &"amb_temple")
	am.set_ambience(&"", 0.0)
	am.play_music(&"mus_menu", 0.0)
	assert_eq(am.get_current_music(), &"mus_menu")
	am.play_music(&"mus_night", 0.1)
	assert_eq(am.get_current_music(), &"mus_night")
	for i in 5:
		await tree.process_frame
	am.stop_music(0.0)
	assert_eq(am.get_current_music(), &"")
	# dialogue ducking
	ge.dialogue_started.emit(&"test", &"ba_tu")
	assert_true(am._ducks.has(&"dialogue"))
	ge.dialogue_ended.emit(&"test")
	assert_false(am._ducks.has(&"dialogue"))
	# player events with no player in the tree must not error
	ge.player_meowed.emit(&"loud")
	ge.player_landed.emit(6.0, &"metal")
	ge.player_jumped.emit(0.7)
	ge.ui_menu_opened.emit(&"pause")
	ge.ui_menu_closed.emit(&"pause")
	ge.area_entered.emit(&"main_street")
