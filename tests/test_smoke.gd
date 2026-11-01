extends "res://tests/test_base.gd"

func test_autoloads_present() -> void:
	for n in ["GameEvents", "Settings", "GameState", "TimeOfDay", "QuestManager", "DialogueManager", "AudioManager", "SceneLoader"]:
		assert_not_null(tree.root.get_node_or_null(n), "autoload " + n)

func test_input_actions_exist() -> void:
	for a in ["move_forward", "jump", "toggle_camera", "interact", "meow", "sprint", "sneak"]:
		assert_true(InputMap.has_action(a), a)

func test_async_supported() -> void:
	await tree.process_frame
	assert_true(true)
