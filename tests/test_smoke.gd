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

func test_production_story_data_and_game_scene() -> void:
	QuestManager.quest_dirs = PackedStringArray(["res://data/quests"])
	QuestManager.reload_definitions()
	DialogueManager.dialogue_dirs = PackedStringArray(["res://data/dialogue"])
	DialogueManager.clear_cache()
	assert_eq(QuestManager.get_quest_ids().size(), 11, "11 quests in data/quests")
	for d in ["ba_tu", "bin", "bong", "co_hoa", "lao_qua", "mun", "ong_muop", "xam"]:
		assert_false(DialogueManager.get_dialogue(StringName(d)).is_empty(), "dialogue in data/dialogue: " + d)
	GameState.new_game()
	assert_true(QuestManager.is_active(&"main_01_morning"), "main_01_morning auto-started on new_game")
	var game_ps := load("res://scenes/main/game.tscn") as PackedScene
	assert_not_null(game_ps, "scenes/main/game.tscn loads")
	var game := game_ps.instantiate()
	tree.root.add_child(game)
	await tree.process_frame
	await tree.physics_frame
	assert_not_null(game.get_node_or_null("City"), "Game has City")
	assert_not_null(game.get_node_or_null("LifeDirector"), "Game has LifeDirector")
	assert_not_null(game.get_node_or_null("HUD"), "Game has HUD")
	var player := tree.get_first_node_in_group(&"player") as Node3D
	assert_not_null(player, "CatPlayer spawned in Game")
	var spawn := tree.get_first_node_in_group(&"player_spawn") as Node3D
	assert_not_null(spawn, "PlayerSpawn marker in City")
	assert_true(player.global_position.distance_to(spawn.global_position) < 1.5, "CatPlayer spawned at PlayerSpawn")
	var bounds := UIMapCapture.compute_bounds(game)
	assert_true(bounds.size.x >= 200.0 and bounds.size.y >= 180.0, "UIMapCapture bounds from Game/City")
	game.queue_free()
	await tree.process_frame
