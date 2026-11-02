extends "res://tests/test_base.gd"
## UI area: Settings autoload — defaults table, persistence round trip, sanitising, quality presets,
## settings_changed signal, graphics listeners and translations.

const TEST_CFG := "user://test_ui_settings.cfg"

var _s: Node
var _orig_path := ""
var _orig_apply := true
var _orig_autosave := 0.0


func before_each() -> void:
	_s = tree.root.get_node("Settings")
	_orig_path = _s.get("config_path")
	_orig_apply = _s.get("apply_to_engine")
	_orig_autosave = _s.get("autosave_delay_s")
	_s.set("config_path", TEST_CFG)
	_s.set("apply_to_engine", false)
	_s.set("autosave_delay_s", 0.0)
	if FileAccess.file_exists(TEST_CFG):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_CFG))
	_s.call("load_settings")


func after_each() -> void:
	if FileAccess.file_exists(TEST_CFG):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_CFG))
	_s.set("config_path", _orig_path)
	_s.call("load_settings")
	_s.set("apply_to_engine", _orig_apply)
	_s.set("autosave_delay_s", _orig_autosave)


func test_contract_defaults() -> void:
	var expect := {
		"graphics/quality": "high", "graphics/fullscreen": false, "graphics/vsync": true, "graphics/max_fps": 0,
		"graphics/render_scale": 1.0, "graphics/upscaler": "fsr2", "graphics/fov": 75.0, "graphics/sdfgi": true,
		"graphics/ssr": true, "graphics/ssao": true, "graphics/ssil": false, "graphics/volumetric_fog": true,
		"graphics/fur_shells": 24, "graphics/shadow_quality": "high", "graphics/motion_blur": false,
		"controls/mouse_sensitivity": 0.25, "controls/invert_y": false, "controls/gamepad_sensitivity": 3.0,
		"camera/default_mode": "third_person", "camera/head_bob": 1.0, "audio/master": 1.0, "audio/music": 0.7,
		"audio/sfx": 1.0, "audio/ambience": 0.9, "audio/ui": 0.8, "gameplay/language": "vi",
		"gameplay/subtitles": true, "gameplay/hints": true,
	}
	for k: String in expect:
		var p := k.split("/")
		var v: Variant = _s.call("get_value", p[0], p[1])
		assert_eq(v, expect[k], k)
	assert_eq(_s.call("get_value", "nope", "missing", 42), 42, "unknown key falls back to caller default")


func test_persistence_round_trip() -> void:
	_s.call("set_value", "audio", "music", 0.35)
	_s.call("set_value", "controls", "invert_y", true)
	_s.call("set_value", "gameplay", "language", "en")
	_s.call("set_value", "graphics", "fov", 88.0)
	assert_true(bool(_s.call("is_dirty")), "dirty after set")
	assert_true(bool(_s.call("save")), "save ok")
	assert_true(FileAccess.file_exists(TEST_CFG), "file written")
	var cf := ConfigFile.new()
	assert_eq(cf.load(TEST_CFG), OK)
	assert_near(float(cf.get_value("audio", "music", -1.0)), 0.35)
	_s.call("set_value", "audio", "music", 0.9)  # in-memory change, not saved
	_s.call("load_settings")
	assert_near(float(_s.call("get_value", "audio", "music")), 0.35, 0.0001, "reloaded from disk")
	assert_eq(_s.call("get_value", "controls", "invert_y"), true)
	assert_eq(_s.call("get_value", "gameplay", "language"), "en")
	assert_near(float(_s.call("get_value", "graphics", "fov")), 88.0)
	_s.call("set_value", "gameplay", "language", "vi")


func test_sanitize_clamps_and_rejects() -> void:
	_s.call("set_value", "graphics", "fov", 400.0)
	assert_near(float(_s.call("get_value", "graphics", "fov")), 100.0, 0.001, "fov clamped")
	_s.call("set_value", "audio", "sfx", -3.0)
	assert_near(float(_s.call("get_value", "audio", "sfx")), 0.0)
	_s.call("set_value", "graphics", "upscaler", "dlss")
	assert_eq(_s.call("get_value", "graphics", "upscaler"), "fsr2", "invalid choice -> default")
	_s.call("set_value", "graphics", "fur_shells", 12.7)
	assert_eq(typeof(_s.call("get_value", "graphics", "fur_shells")), TYPE_INT, "int key stays int")
	# a hand-edited, broken file is sanitised on load
	var cf := ConfigFile.new()
	cf.set_value("graphics", "render_scale", 7.0)
	cf.set_value("gameplay", "language", "klingon")
	cf.save(TEST_CFG)
	_s.call("load_settings")
	assert_near(float(_s.call("get_value", "graphics", "render_scale")), 1.0)
	assert_eq(_s.call("get_value", "gameplay", "language"), "vi")


func test_quality_presets_map_to_keys() -> void:
	for level: String in ["low", "medium", "high", "ultra"]:
		_s.call("apply_quality_preset", level)
		assert_eq(_s.call("get_value", "graphics", "quality"), level)
		var row: Dictionary = _s.call("get_quality_preset_values", level)
		assert_true(row.size() >= 8, "preset %s has keys" % level)
		for k: String in row:
			var v: Variant = _s.call("get_value", "graphics", k)
			if typeof(row[k]) == TYPE_FLOAT:
				assert_near(float(v), float(row[k]), 0.0001, "%s/%s" % [level, k])
			else:
				assert_eq(v, row[k], "%s/%s" % [level, k])
		assert_eq(_s.call("detect_quality_preset"), level)
	# ordering sanity: low is cheaper than ultra
	var lo: Dictionary = _s.call("get_quality_preset_values", "low")
	var ul: Dictionary = _s.call("get_quality_preset_values", "ultra")
	assert_true(int(lo["fur_shells"]) < int(ul["fur_shells"]))
	assert_false(bool(lo["sdfgi"]))
	assert_true(bool(ul["ssil"]))


func test_manual_change_makes_quality_custom() -> void:
	_s.call("apply_quality_preset", "high")
	_s.call("set_value", "graphics", "ssr", false)
	assert_eq(_s.call("get_value", "graphics", "quality"), "custom")
	_s.call("set_value", "graphics", "quality", "medium")
	assert_eq(_s.call("get_value", "graphics", "ssr"), false)
	assert_eq(int(_s.call("get_value", "graphics", "fur_shells")), 16)


func test_settings_changed_signal_and_listeners() -> void:
	var ge := tree.root.get_node("GameEvents")
	var seen: Array[StringName] = []
	var cb := func(section: StringName) -> void: seen.append(section)
	ge.connect(&"settings_changed", cb)
	var listener := _Listener.new()
	listener.add_to_group(&"graphics_settings_listener")
	tree.root.add_child(listener)
	_s.call("set_value", "audio", "ambience", 0.4)
	_s.call("set_value", "graphics", "ssao", false)
	_s.call("apply_quality_preset", "low")
	ge.disconnect(&"settings_changed", cb)
	assert_true(seen.has(&"audio"), "audio section signalled")
	assert_true(seen.has(&"graphics"), "graphics section signalled")
	assert_true(listener.calls >= 1, "apply_graphics_settings called on group (calls=%d)" % listener.calls)
	listener.queue_free()


func test_reset_section() -> void:
	_s.call("set_value", "audio", "master", 0.2)
	_s.call("reset_section", "audio")
	assert_near(float(_s.call("get_value", "audio", "master")), 1.0)


func test_translations_vi_and_en() -> void:
	var prev := TranslationServer.get_locale()
	TranslationServer.set_locale("vi")
	var vi := String(TranslationServer.translate("TITLE_SUB"))
	TranslationServer.set_locale("en")
	var en := String(TranslationServer.translate("TITLE_SUB"))
	TranslationServer.set_locale(prev)
	assert_eq(vi, "Phố Cũ", "vi translation loaded")
	assert_eq(en, "Old Quarter", "en translation loaded")


func test_strings_csv_complete() -> void:
	var f := FileAccess.open("res://data/i18n/strings.csv", FileAccess.READ)
	assert_not_null(f)
	if f == null:
		return
	var header := f.get_csv_line()
	assert_eq(Array(header), ["keys", "en", "vi"])
	var n := 0
	var empty := 0
	var keys := {}
	while not f.eof_reached():
		var row := f.get_csv_line()
		if row.size() < 3 or row[0] == "":
			continue
		n += 1
		assert_false(keys.has(row[0]), "duplicate key " + row[0])
		keys[row[0]] = true
		if row[1].strip_edges() == "" or row[2].strip_edges() == "":
			empty += 1
	assert_true(n >= 800, "strings: %d" % n)
	assert_eq(empty, 0, "rows missing en or vi")


class _Listener extends Node:
	var calls := 0

	func apply_graphics_settings() -> void:
		calls += 1
