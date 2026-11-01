extends Node
## Settings autoload (owner: ui). Persistent player options in user://settings.cfg.
##
## Contract (CLAUDE.md): get_value(section, key, default = null), set_value(section, key, value),
## save(), apply_all(). Every change emits GameEvents.settings_changed(section); graphics changes
## also call apply_graphics_settings() on nodes in group "graphics_settings_listener".
##
## Extras used by the UI and other areas:
##   apply_quality_preset(name)           low | medium | high | ultra (sets every preset key)
##   get_quality_preset_values(name)      the preset table row
##   reset_section(section) / reset_all()
##   configure_environment(env)           static helper: SDFGI/SSR/SSAO/SSIL/volumetric fog toggles
##   is_using_gamepad() + signal input_device_changed(is_gamepad)
##   rebind_action(action, event) / reset_bindings() / get_action_events(action, gamepad)
## Writes are batched: set_value() marks the file dirty and save() writes it (the settings menu
## saves on close; autosave_delay_s also flushes pending changes shortly after the last change).

signal input_device_changed(is_gamepad: bool)
signal bindings_changed()

const SETTINGS_PATH := "user://settings.cfg"
const GRAPHICS_LISTENER_GROUP := &"graphics_settings_listener"
const QUALITY_LEVELS: PackedStringArray = ["low", "medium", "high", "ultra"]
const LANGUAGES: PackedStringArray = ["vi", "en"]
const TRANSLATION_FILES: PackedStringArray = [
	"res://data/i18n/strings.vi.translation",
	"res://data/i18n/strings.en.translation",
]
const AUDIO_BUSES := {"master": &"Master", "music": &"Music", "sfx": &"SFX", "ambience": &"Ambience", "ui": &"UI"}
## Actions shown/rebindable in Settings › Controls (order = display order).
const REBINDABLE_ACTIONS: PackedStringArray = [
	"move_forward", "move_back", "move_left", "move_right", "jump", "sprint", "sneak", "interact",
	"pickup_drop", "meow", "swipe", "aim_jump", "cat_sense", "sit_groom", "toggle_camera",
	"inventory", "journal", "map", "pause", "quick_save", "quick_load", "screenshot",
]

## section -> key -> default value. Keys from the CLAUDE.md contract plus UI extras.
const DEFAULTS := {
	"graphics": {
		"quality": "high",
		"fullscreen": false,
		"vsync": true,
		"max_fps": 0,
		"render_scale": 1.0,
		"upscaler": "fsr2",
		"fsr_sharpness": 0.2,
		"anti_aliasing": "taa",
		"fov": 75.0,
		"sdfgi": true,
		"ssr": true,
		"ssao": true,
		"ssil": false,
		"volumetric_fog": true,
		"fur_shells": 24,
		"shadow_quality": "high",
		"motion_blur": false,
		"lod_bias": 1.0,
		"anisotropic": 8,
		"film_grain": true,
	},
	"controls": {
		"mouse_sensitivity": 0.25,
		"invert_y": false,
		"invert_x": false,
		"gamepad_sensitivity": 3.0,
		"vibration": true,
	},
	"camera": {
		"default_mode": "third_person",
		"head_bob": 1.0,
		"auto_center": true,
	},
	"audio": {
		"master": 1.0,
		"music": 0.7,
		"sfx": 1.0,
		"ambience": 0.9,
		"ui": 0.8,
	},
	"gameplay": {
		"language": "vi",
		"subtitles": true,
		"subtitle_size": "medium",
		"hints": true,
		"compass": true,
		"text_speed": 1.0,
		"ui_scale": 1.0,
		"hud_opacity": 1.0,
	},
	"input": {},
}

## Keys driven by graphics/quality. Changing one by hand turns quality into "custom".
const QUALITY_PRESETS := {
	"low": {
		"render_scale": 0.67, "upscaler": "fsr", "anti_aliasing": "fxaa", "sdfgi": false, "ssr": false,
		"ssao": false, "ssil": false, "volumetric_fog": false, "fur_shells": 8, "shadow_quality": "low",
		"lod_bias": 2.0, "anisotropic": 2,
	},
	"medium": {
		"render_scale": 0.77, "upscaler": "fsr2", "anti_aliasing": "taa", "sdfgi": false, "ssr": false,
		"ssao": true, "ssil": false, "volumetric_fog": true, "fur_shells": 16, "shadow_quality": "medium",
		"lod_bias": 1.5, "anisotropic": 4,
	},
	"high": {
		"render_scale": 1.0, "upscaler": "fsr2", "anti_aliasing": "taa", "sdfgi": true, "ssr": true,
		"ssao": true, "ssil": false, "volumetric_fog": true, "fur_shells": 24, "shadow_quality": "high",
		"lod_bias": 1.0, "anisotropic": 8,
	},
	"ultra": {
		"render_scale": 1.0, "upscaler": "fsr2", "anti_aliasing": "taa", "sdfgi": true, "ssr": true,
		"ssao": true, "ssil": true, "volumetric_fog": true, "fur_shells": 32, "shadow_quality": "ultra",
		"lod_bias": 0.75, "anisotropic": 16,
	},
}

## Option lists for enum-like keys (used by the settings menu and for validation).
const CHOICES := {
	"graphics/quality": ["low", "medium", "high", "ultra", "custom"],
	"graphics/upscaler": ["off", "fsr", "fsr2"],
	"graphics/anti_aliasing": ["off", "fxaa", "smaa", "taa"],
	"graphics/shadow_quality": ["low", "medium", "high", "ultra"],
	"graphics/max_fps": [0, 30, 60, 90, 120, 144, 165, 240],
	"graphics/anisotropic": [2, 4, 8, 16],
	"camera/default_mode": ["third_person", "first_person"],
	"gameplay/language": ["vi", "en"],
	"gameplay/subtitle_size": ["small", "medium", "large"],
}

## Numeric ranges (min, max) — values are clamped on set/load.
const RANGES := {
	"graphics/render_scale": Vector2(0.5, 1.0),
	"graphics/fsr_sharpness": Vector2(0.0, 2.0),
	"graphics/fov": Vector2(60.0, 100.0),
	"graphics/fur_shells": Vector2(0, 48),
	"graphics/lod_bias": Vector2(0.25, 4.0),
	"controls/mouse_sensitivity": Vector2(0.02, 1.0),
	"controls/gamepad_sensitivity": Vector2(0.5, 8.0),
	"camera/head_bob": Vector2(0.0, 1.0),
	"audio/master": Vector2(0.0, 1.0),
	"audio/music": Vector2(0.0, 1.0),
	"audio/sfx": Vector2(0.0, 1.0),
	"audio/ambience": Vector2(0.0, 1.0),
	"audio/ui": Vector2(0.0, 1.0),
	"gameplay/text_speed": Vector2(0.25, 3.0),
	"gameplay/ui_scale": Vector2(0.75, 1.3),
	"gameplay/hud_opacity": Vector2(0.2, 1.0),
}

## Path of the config file; tests point this somewhere else before calling load_settings().
var config_path := SETTINGS_PATH
## Seconds after the last set_value() before pending changes are written (<= 0 disables).
var autosave_delay_s := 2.0
## When false, apply_* functions only emit signals (tests / headless tools).
var apply_to_engine := true

var _cfg := ConfigFile.new()
var _dirty := false
var _dirty_t := 0.0
var _using_gamepad := false
var _default_bindings: Dictionary = {}   # action -> Array[InputEvent] (project defaults)
var _suspend_signals := 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_register_translations()
	_capture_default_bindings()
	load_settings()
	apply_all()
	set_process(true)


func _process(delta: float) -> void:
	if _dirty and autosave_delay_s > 0.0:
		_dirty_t += delta
		if _dirty_t >= autosave_delay_s:
			save()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		if _dirty:
			save()


func _input(event: InputEvent) -> void:
	var pad := _using_gamepad
	if event is InputEventJoypadButton:
		pad = true
	elif event is InputEventJoypadMotion:
		if absf((event as InputEventJoypadMotion).axis_value) > 0.45:
			pad = true
	elif event is InputEventKey or event is InputEventMouseButton:
		pad = false
	elif event is InputEventMouseMotion:
		if (event as InputEventMouseMotion).relative.length() > 6.0:
			pad = false
	if pad != _using_gamepad:
		_using_gamepad = pad
		input_device_changed.emit(pad)


# =============================================================================================
# Contract API
# =============================================================================================

## Returns the stored value, else the built-in default, else `default`.
func get_value(section: String, key: String, default: Variant = null) -> Variant:
	if _cfg.has_section_key(section, key):
		return _cfg.get_value(section, key)
	var sec: Dictionary = DEFAULTS.get(section, {})
	if sec.has(key):
		return sec[key]
	return default


## Stores a value (validated/clamped), applies it to the engine and emits settings_changed.
func set_value(section: String, key: String, value: Variant) -> void:
	var v: Variant = sanitize(section, key, value)
	var old: Variant = get_value(section, key)
	if old != null and typeof(old) == typeof(v) and old == v and _cfg.has_section_key(section, key):
		return
	_cfg.set_value(section, key, v)
	_mark_dirty()
	if section == "graphics":
		if key == "quality":
			if String(v) in QUALITY_LEVELS:
				_apply_preset_values(String(v))
		elif _is_preset_key(key):
			_update_custom_quality()
	_apply_key(section, key)
	_emit_changed(section)


## Writes user://settings.cfg (only keys that differ from defaults are meaningful, but all
## set keys are written so the file documents the player's choices).
func save() -> bool:
	_dirty = false
	_dirty_t = 0.0
	var err := _cfg.save(config_path)
	if err != OK:
		push_warning("Settings: cannot write %s (%s)" % [config_path, error_string(err)])
		return false
	return true


## Applies every setting to the engine and notifies every listener.
func apply_all() -> void:
	_apply_window()
	_apply_render()
	_apply_audio()
	_apply_language()
	_apply_bindings()
	_apply_ui_scale()
	for section: String in ["graphics", "controls", "camera", "audio", "gameplay"]:
		_emit_changed(section)


# =============================================================================================
# Extras
# =============================================================================================

func load_settings() -> void:
	_cfg = ConfigFile.new()
	if FileAccess.file_exists(config_path):
		var err := _cfg.load(config_path)
		if err != OK:
			push_warning("Settings: %s unreadable (%s) — using defaults" % [config_path, error_string(err)])
			_cfg = ConfigFile.new()
	# Validate everything that was loaded (hand-edited files, older versions).
	for section in _cfg.get_sections():
		if section == "input":
			continue
		for key in _cfg.get_section_keys(section):
			_cfg.set_value(section, key, sanitize(section, key, _cfg.get_value(section, key)))
	_dirty = false


## Clamps / validates a value for section/key. Unknown keys pass through unchanged.
func sanitize(section: String, key: String, value: Variant) -> Variant:
	var path := section + "/" + key
	var def: Variant = (DEFAULTS.get(section, {}) as Dictionary).get(key, null)
	if def == null:
		return value
	var v: Variant = value
	match typeof(def):
		TYPE_BOOL:
			v = bool(value) if typeof(value) in [TYPE_BOOL, TYPE_INT, TYPE_FLOAT] else (str(value).to_lower() in ["true", "1", "yes", "on"])
		TYPE_INT:
			v = int(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL] else int(str(value))
		TYPE_FLOAT:
			v = float(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT, TYPE_BOOL] else float(str(value))
		TYPE_STRING:
			v = str(value)
	if RANGES.has(path):
		var r: Vector2 = RANGES[path]
		if typeof(v) == TYPE_INT:
			v = clampi(int(v), int(r.x), int(r.y))
		elif typeof(v) == TYPE_FLOAT:
			v = clampf(float(v), r.x, r.y)
	if CHOICES.has(path):
		var opts: Array = CHOICES[path]
		if not opts.has(v):
			if typeof(def) == TYPE_INT and path == "graphics/max_fps":
				v = maxi(0, int(v))  # any non-negative fps cap is valid; list is only for the menu
			else:
				v = def
	return v


func get_default(section: String, key: String) -> Variant:
	return (DEFAULTS.get(section, {}) as Dictionary).get(key, null)


func get_quality_preset_values(level: String) -> Dictionary:
	return (QUALITY_PRESETS.get(level, {}) as Dictionary).duplicate()


## Sets graphics/quality and every key of that preset in one go.
func apply_quality_preset(level: String) -> void:
	if not level in QUALITY_LEVELS:
		push_warning("Settings: unknown quality preset " + level)
		return
	_suspend_signals += 1
	_cfg.set_value("graphics", "quality", level)
	_apply_preset_values(level)
	_suspend_signals -= 1
	_mark_dirty()
	_apply_render()
	_emit_changed("graphics")


## The preset whose values all match the current graphics keys, or "custom".
func detect_quality_preset() -> String:
	for level in QUALITY_LEVELS:
		var row: Dictionary = QUALITY_PRESETS[level]
		var ok := true
		for k: String in row:
			if not _values_equal(get_value("graphics", k), row[k]):
				ok = false
				break
		if ok:
			return level
	return "custom"


func reset_section(section: String) -> void:
	if _cfg.has_section(section):
		_cfg.erase_section(section)
	_mark_dirty()
	if section == "input":
		_apply_bindings()
		bindings_changed.emit()
		return
	match section:
		"graphics":
			_apply_window()
			_apply_render()
		"audio":
			_apply_audio()
		"gameplay":
			_apply_language()
			_apply_ui_scale()
	_emit_changed(section)


func reset_all() -> void:
	_cfg = ConfigFile.new()
	_mark_dirty()
	apply_all()
	bindings_changed.emit()


func is_using_gamepad() -> bool:
	return _using_gamepad


## Forces the glyph mode (tests, or a UI that wants to preview gamepad glyphs).
func set_using_gamepad(pad: bool) -> void:
	if pad != _using_gamepad:
		_using_gamepad = pad
		input_device_changed.emit(pad)


func is_dirty() -> bool:
	return _dirty


## Linear 0..1 volume for a bus key (master, music, sfx, ambience, ui).
func get_volume(bus_key: String) -> float:
	return float(get_value("audio", bus_key, 1.0))


## Configures an Environment from the graphics settings (for the world area / menu backdrop).
## Only toggles features; artistic parameters of the environment are left untouched.
static func configure_environment(env: Environment) -> void:
	if env == null:
		return
	var s: Node = (Engine.get_main_loop() as SceneTree).root.get_node_or_null(^"/root/Settings")
	if s == null:
		return
	env.sdfgi_enabled = bool(s.call("get_value", "graphics", "sdfgi"))
	env.ssr_enabled = bool(s.call("get_value", "graphics", "ssr"))
	env.ssao_enabled = bool(s.call("get_value", "graphics", "ssao"))
	env.ssil_enabled = bool(s.call("get_value", "graphics", "ssil"))
	env.volumetric_fog_enabled = bool(s.call("get_value", "graphics", "volumetric_fog"))


# --- Input bindings ---------------------------------------------------------------------------

## Events currently bound to an action, filtered to keyboard/mouse (gamepad = false) or gamepad.
func get_action_events(action: String, gamepad: bool = false) -> Array[InputEvent]:
	var out: Array[InputEvent] = []
	if not InputMap.has_action(action):
		return out
	for ev in InputMap.action_get_events(action):
		var is_pad := ev is InputEventJoypadButton or ev is InputEventJoypadMotion
		if is_pad == gamepad:
			out.append(ev)
	return out


## Replaces the primary keyboard/mouse binding (gamepad = false) or the primary gamepad binding
## of an action with `event`. Persisted in [input] of settings.cfg.
func rebind_action(action: String, event: InputEvent) -> bool:
	if not InputMap.has_action(action) or event == null:
		return false
	var pad := event is InputEventJoypadButton or event is InputEventJoypadMotion
	var stored := _serialize_event(event)
	if stored.is_empty():
		return false
	var key := action + ("/pad" if pad else "/kbm")
	_cfg.set_value("input", key, stored)
	_mark_dirty()
	_apply_binding(action)
	bindings_changed.emit()
	_emit_changed("controls")
	return true


func reset_bindings() -> void:
	reset_section("input")
	_emit_changed("controls")


## Which action (if any) already uses an equivalent event (conflict warning in the menu).
func find_action_for_event(event: InputEvent, exclude_action: String = "") -> String:
	for action in REBINDABLE_ACTIONS:
		if action == exclude_action or not InputMap.has_action(action):
			continue
		for ev in InputMap.action_get_events(action):
			if _events_match(ev, event):
				return action
	return ""


# =============================================================================================
# Internals
# =============================================================================================

func _mark_dirty() -> void:
	_dirty = true
	_dirty_t = 0.0


func _emit_changed(section: String) -> void:
	if _suspend_signals > 0:
		return
	var ge: Node = get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.emit_signal(&"settings_changed", StringName(section))
	if section == "graphics" and is_inside_tree():
		for n in get_tree().get_nodes_in_group(GRAPHICS_LISTENER_GROUP):
			if n.has_method("apply_graphics_settings"):
				n.call("apply_graphics_settings")


func _is_preset_key(key: String) -> bool:
	return (QUALITY_PRESETS["high"] as Dictionary).has(key)


func _apply_preset_values(level: String) -> void:
	var row: Dictionary = QUALITY_PRESETS[level]
	for k: String in row:
		_cfg.set_value("graphics", k, row[k])


func _update_custom_quality() -> void:
	_cfg.set_value("graphics", "quality", detect_quality_preset())


static func _values_equal(a: Variant, b: Variant) -> bool:
	if typeof(a) in [TYPE_INT, TYPE_FLOAT] and typeof(b) in [TYPE_INT, TYPE_FLOAT]:
		return absf(float(a) - float(b)) < 0.0001
	return typeof(a) == typeof(b) and a == b


func _apply_key(section: String, key: String) -> void:
	match section:
		"graphics":
			if key in ["fullscreen", "vsync", "max_fps"]:
				_apply_window()
			else:
				_apply_render()
		"audio":
			_apply_audio()
		"gameplay":
			if key == "language":
				_apply_language()
			elif key == "ui_scale":
				_apply_ui_scale()


func _can_touch_display() -> bool:
	return apply_to_engine and DisplayServer.get_name() != "headless"


func _apply_window() -> void:
	Engine.max_fps = int(get_value("graphics", "max_fps"))
	if not _can_touch_display():
		return
	var fs := bool(get_value("graphics", "fullscreen"))
	var mode := DisplayServer.window_get_mode()
	var is_fs := mode == DisplayServer.WINDOW_MODE_FULLSCREEN or mode == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN
	if fs and not is_fs:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	elif not fs and is_fs:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if bool(get_value("graphics", "vsync")) else DisplayServer.VSYNC_DISABLED)


func _apply_render() -> void:
	if not apply_to_engine or not is_inside_tree():
		return
	var vp := get_tree().root
	var scale := float(get_value("graphics", "render_scale"))
	# The upscaler only engages below native resolution; at 1.0 the AA setting decides (TAA by
	# default), which keeps native rendering identical to the project's defaults.
	vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
	if scale < 0.999:
		match String(get_value("graphics", "upscaler")):
			"fsr":
				vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR
			"fsr2":
				vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
	vp.scaling_3d_scale = scale
	vp.fsr_sharpness = float(get_value("graphics", "fsr_sharpness"))
	var aa := String(get_value("graphics", "anti_aliasing"))
	vp.use_taa = aa == "taa" and vp.scaling_3d_mode != Viewport.SCALING_3D_MODE_FSR2
	vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA if aa == "fxaa" else (Viewport.SCREEN_SPACE_AA_SMAA if aa == "smaa" else Viewport.SCREEN_SPACE_AA_DISABLED)
	vp.mesh_lod_threshold = float(get_value("graphics", "lod_bias"))
	match int(get_value("graphics", "anisotropic")):
		2:
			vp.anisotropic_filtering_level = Viewport.ANISOTROPY_2X
		4:
			vp.anisotropic_filtering_level = Viewport.ANISOTROPY_4X
		16:
			vp.anisotropic_filtering_level = Viewport.ANISOTROPY_16X
		_:
			vp.anisotropic_filtering_level = Viewport.ANISOTROPY_8X
	# Shadows: atlas sizes + soft filter quality.
	var sq := String(get_value("graphics", "shadow_quality"))
	var dir_size := 8192
	var pos_size := 4096
	var filt := RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM
	match sq:
		"low":
			dir_size = 2048
			pos_size = 1024
			filt = RenderingServer.SHADOW_QUALITY_SOFT_VERY_LOW
		"medium":
			dir_size = 4096
			pos_size = 2048
			filt = RenderingServer.SHADOW_QUALITY_SOFT_LOW
		"high":
			dir_size = 8192
			pos_size = 4096
			filt = RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM
		"ultra":
			dir_size = 8192
			pos_size = 8192
			filt = RenderingServer.SHADOW_QUALITY_SOFT_HIGH
	RenderingServer.directional_shadow_atlas_set_size(dir_size, true)
	RenderingServer.directional_soft_shadow_filter_set_quality(filt)
	RenderingServer.positional_soft_shadow_filter_set_quality(filt)
	vp.positional_shadow_atlas_size = pos_size
	# Effect quality knobs that scale with the preset.
	var q := String(get_value("graphics", "quality"))
	var ultra := q == "ultra"
	var low := q == "low"
	RenderingServer.environment_set_ssao_quality(
		RenderingServer.ENV_SSAO_QUALITY_ULTRA if ultra else (RenderingServer.ENV_SSAO_QUALITY_LOW if low else RenderingServer.ENV_SSAO_QUALITY_MEDIUM),
		not ultra, 0.5, 2, 50.0, 300.0)
	RenderingServer.environment_set_ssil_quality(
		RenderingServer.ENV_SSIL_QUALITY_HIGH if ultra else RenderingServer.ENV_SSIL_QUALITY_MEDIUM,
		not ultra, 0.5, 4, 50.0, 300.0)
	RenderingServer.environment_set_volumetric_fog_volume_size(128 if ultra else (48 if low else 64), 96 if ultra else (48 if low else 64))
	RenderingServer.environment_set_volumetric_fog_filter_active(not low)


func _apply_audio() -> void:
	for key: String in AUDIO_BUSES:
		var idx := AudioServer.get_bus_index(AUDIO_BUSES[key])
		if idx < 0:
			continue
		var lin := clampf(float(get_value("audio", key)), 0.0, 1.0)
		AudioServer.set_bus_mute(idx, lin <= 0.001)
		AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(lin, 0.0001)))


func _apply_language() -> void:
	var lang := String(get_value("gameplay", "language"))
	if TranslationServer.get_locale() != lang:
		TranslationServer.set_locale(lang)


func _apply_ui_scale() -> void:
	if not apply_to_engine or not is_inside_tree():
		return
	get_tree().root.content_scale_factor = float(get_value("gameplay", "ui_scale"))


func _register_translations() -> void:
	for path in TRANSLATION_FILES:
		if not ResourceLoader.exists(path):
			continue
		var t := load(path) as Translation
		if t != null and not TranslationServer.has_translation(t):
			TranslationServer.add_translation(t)


func _capture_default_bindings() -> void:
	_default_bindings.clear()
	for action in REBINDABLE_ACTIONS:
		if not InputMap.has_action(action):
			continue
		var evs: Array[InputEvent] = []
		for ev in InputMap.action_get_events(action):
			evs.append(ev.duplicate() as InputEvent)
		_default_bindings[action] = evs


func _apply_bindings() -> void:
	for action: String in _default_bindings:
		_apply_binding(action)


func _apply_binding(action: String) -> void:
	if not _default_bindings.has(action) or not InputMap.has_action(action):
		return
	var defaults: Array = _default_bindings[action]
	InputMap.action_erase_events(action)
	var kbm_override: InputEvent = _deserialize_event(_cfg.get_value("input", action + "/kbm", {}))
	var pad_override: InputEvent = _deserialize_event(_cfg.get_value("input", action + "/pad", {}))
	var kbm_done := false
	var pad_done := false
	for ev: InputEvent in defaults:
		var is_pad := ev is InputEventJoypadButton or ev is InputEventJoypadMotion
		if is_pad and pad_override != null:
			if not pad_done:
				InputMap.action_add_event(action, pad_override)
				pad_done = true
			continue
		if not is_pad and kbm_override != null:
			if not kbm_done:
				InputMap.action_add_event(action, kbm_override)
				kbm_done = true
			continue
		InputMap.action_add_event(action, ev.duplicate() as InputEvent)
	if kbm_override != null and not kbm_done:
		InputMap.action_add_event(action, kbm_override)
	if pad_override != null and not pad_done:
		InputMap.action_add_event(action, pad_override)


static func _serialize_event(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		var code := k.physical_keycode if k.physical_keycode != KEY_NONE else k.keycode
		return {"type": "key", "code": int(code)}
	if ev is InputEventMouseButton:
		return {"type": "mouse", "button": int((ev as InputEventMouseButton).button_index)}
	if ev is InputEventJoypadButton:
		return {"type": "joy_button", "button": int((ev as InputEventJoypadButton).button_index)}
	if ev is InputEventJoypadMotion:
		var m := ev as InputEventJoypadMotion
		return {"type": "joy_axis", "axis": int(m.axis), "value": signf(m.axis_value) if m.axis_value != 0.0 else 1.0}
	return {}


static func _deserialize_event(d: Variant) -> InputEvent:
	if not d is Dictionary or (d as Dictionary).is_empty():
		return null
	var dd: Dictionary = d
	match String(dd.get("type", "")):
		"key":
			var k := InputEventKey.new()
			k.physical_keycode = int(dd.get("code", 0)) as Key
			return k
		"mouse":
			var m := InputEventMouseButton.new()
			m.button_index = int(dd.get("button", 1)) as MouseButton
			return m
		"joy_button":
			var j := InputEventJoypadButton.new()
			j.button_index = int(dd.get("button", 0)) as JoyButton
			return j
		"joy_axis":
			var a := InputEventJoypadMotion.new()
			a.axis = int(dd.get("axis", 0)) as JoyAxis
			a.axis_value = float(dd.get("value", 1.0))
			return a
	return null


static func _events_match(a: InputEvent, b: InputEvent) -> bool:
	if a is InputEventKey and b is InputEventKey:
		var ka := a as InputEventKey
		var kb := b as InputEventKey
		var ca := ka.physical_keycode if ka.physical_keycode != KEY_NONE else ka.keycode
		var cb := kb.physical_keycode if kb.physical_keycode != KEY_NONE else kb.keycode
		return ca == cb
	if a is InputEventMouseButton and b is InputEventMouseButton:
		return (a as InputEventMouseButton).button_index == (b as InputEventMouseButton).button_index
	if a is InputEventJoypadButton and b is InputEventJoypadButton:
		return (a as InputEventJoypadButton).button_index == (b as InputEventJoypadButton).button_index
	if a is InputEventJoypadMotion and b is InputEventJoypadMotion:
		var ma := a as InputEventJoypadMotion
		var mb := b as InputEventJoypadMotion
		return ma.axis == mb.axis and signf(ma.axis_value) == signf(mb.axis_value)
	return false
