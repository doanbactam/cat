extends SceneTree
## Writes the canonical input map into project.godot.
## Run: godot --headless --path . --script res://tools/setup_input.gd

func key(code: Key) -> InputEventKey:
	var e := InputEventKey.new(); e.physical_keycode = code; return e

func mouse(btn: MouseButton) -> InputEventMouseButton:
	var e := InputEventMouseButton.new(); e.button_index = btn; return e

func joy_btn(btn: JoyButton) -> InputEventJoypadButton:
	var e := InputEventJoypadButton.new(); e.button_index = btn; return e

func joy_axis(axis: JoyAxis, v: float) -> InputEventJoypadMotion:
	var e := InputEventJoypadMotion.new(); e.axis = axis; e.axis_value = v; return e

func _init() -> void:
	var map := {
		"move_forward": [key(KEY_W), key(KEY_UP), joy_axis(JOY_AXIS_LEFT_Y, -1.0)],
		"move_back": [key(KEY_S), key(KEY_DOWN), joy_axis(JOY_AXIS_LEFT_Y, 1.0)],
		"move_left": [key(KEY_A), key(KEY_LEFT), joy_axis(JOY_AXIS_LEFT_X, -1.0)],
		"move_right": [key(KEY_D), key(KEY_RIGHT), joy_axis(JOY_AXIS_LEFT_X, 1.0)],
		"look_up": [joy_axis(JOY_AXIS_RIGHT_Y, -1.0)],
		"look_down": [joy_axis(JOY_AXIS_RIGHT_Y, 1.0)],
		"look_left": [joy_axis(JOY_AXIS_RIGHT_X, -1.0)],
		"look_right": [joy_axis(JOY_AXIS_RIGHT_X, 1.0)],
		"sprint": [key(KEY_SHIFT), joy_btn(JOY_BUTTON_LEFT_STICK)],
		"sneak": [key(KEY_CTRL), key(KEY_C), joy_btn(JOY_BUTTON_RIGHT_STICK)],
		"jump": [key(KEY_SPACE), joy_btn(JOY_BUTTON_A)],
		"interact": [key(KEY_E), joy_btn(JOY_BUTTON_X)],
		"pickup_drop": [key(KEY_F), joy_btn(JOY_BUTTON_Y)],
		"meow": [key(KEY_Q), joy_btn(JOY_BUTTON_B)],
		"swipe": [mouse(MOUSE_BUTTON_LEFT), joy_axis(JOY_AXIS_TRIGGER_RIGHT, 1.0)],
		"aim_jump": [mouse(MOUSE_BUTTON_RIGHT), joy_axis(JOY_AXIS_TRIGGER_LEFT, 1.0)],
		"cat_sense": [key(KEY_R), joy_btn(JOY_BUTTON_DPAD_UP)],
		"sit_groom": [key(KEY_X), joy_btn(JOY_BUTTON_DPAD_DOWN)],
		"toggle_camera": [key(KEY_V), joy_btn(JOY_BUTTON_BACK)],
		"zoom_in": [mouse(MOUSE_BUTTON_WHEEL_UP), joy_btn(JOY_BUTTON_RIGHT_SHOULDER)],
		"zoom_out": [mouse(MOUSE_BUTTON_WHEEL_DOWN), joy_btn(JOY_BUTTON_LEFT_SHOULDER)],
		"inventory": [key(KEY_TAB), key(KEY_I), joy_btn(JOY_BUTTON_DPAD_LEFT)],
		"journal": [key(KEY_J), joy_btn(JOY_BUTTON_DPAD_RIGHT)],
		"map": [key(KEY_M)],
		"pause": [key(KEY_ESCAPE), joy_btn(JOY_BUTTON_START)],
		"quick_save": [key(KEY_F5)],
		"quick_load": [key(KEY_F9)],
		"screenshot": [key(KEY_F12)],
		"debug_overlay": [key(KEY_F3)],
	}
	for action in map:
		var events: Array = []
		for ev in map[action]:
			events.append(ev)
		ProjectSettings.set_setting("input/" + action, {"deadzone": 0.2, "events": events})
	var err := ProjectSettings.save()
	print("input map saved: ", err == OK, " actions=", map.size())
	quit()
