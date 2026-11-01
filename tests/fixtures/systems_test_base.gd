extends "res://tests/test_base.gd"
## Shared setup for tests/test_systems_*.gd: deterministic, isolated RPG state.
## Redirects saves to user://test_saves, loads fixture quests/dialogues, pauses the clock and the
## real-time vitals simulation, and restores production defaults afterwards so other areas'
## tests see a normal game.

const FIXTURE_QUESTS := "res://tests/fixtures/quests"
const FIXTURE_DIALOGUE := "res://tests/fixtures/dialogue"

var _spawned: Array[Node] = []
var _events: Array = []
var _connections: Array = []


## Stand-in for CatPlayer: records the contract calls systems make on the player.
class FakePlayer extends CharacterBody3D:
	var teleported_to: Variant = null
	var input_enabled := true
	var actions: Array[StringName] = []

	func _init() -> void:
		name = "FakePlayer"
		collision_layer = 1 << 1
		collision_mask = 1
		var cs := CollisionShape3D.new()
		var sh := CapsuleShape3D.new()
		sh.radius = 0.12
		sh.height = 0.4
		cs.shape = sh
		cs.position.y = 0.2
		add_child(cs)

	func _ready() -> void:
		add_to_group(&"player")

	func teleport(xf: Transform3D) -> void:
		teleported_to = xf
		global_transform = xf

	func set_input_enabled(e: bool) -> void:
		input_enabled = e

	func play_action(a: StringName) -> void:
		actions.append(a)


func before_each() -> void:
	GameState.autosave_enabled = false
	GameState.save_dir = "user://test_saves"
	GameState.simulation_enabled = false
	GameState.location_poll_enabled = false
	GameState.faint_wake_delay = 0.0
	GameState.shelter_override = -1
	TimeOfDay.paused = true
	QuestManager.autosave_on_progress = false
	QuestManager.quest_dirs = PackedStringArray([FIXTURE_QUESTS])
	QuestManager.reload_definitions()
	DialogueManager.dialogue_dirs = PackedStringArray([FIXTURE_DIALOGUE])
	DialogueManager.clear_cache()
	if DialogueManager.is_active():
		DialogueManager.stop()
	GameState.new_game()
	TimeOfDay.set_time(1, 10.0)
	GameState.set_weather_state(&"clear", 0.0)
	_events.clear()


func after_each() -> void:
	for c: Array in _connections:
		var sig: Signal = c[0]
		if sig.is_connected(c[1]):
			sig.disconnect(c[1])
	_connections.clear()
	if DialogueManager.is_active():
		DialogueManager.stop()
	for n in _spawned:
		if is_instance_valid(n):
			if n.get_parent() != null:
				n.get_parent().remove_child(n)
			n.free()
	_spawned.clear()
	# Restore production defaults for whoever runs next.
	QuestManager.quest_dirs = PackedStringArray(["res://data/quests"])
	QuestManager.reload_definitions()
	QuestManager.autosave_on_progress = true
	DialogueManager.dialogue_dirs = PackedStringArray(["res://data/dialogue"])
	DialogueManager.clear_cache()
	GameState.new_game()
	GameState.save_dir = "user://saves"
	GameState.autosave_enabled = true
	GameState.simulation_enabled = true
	GameState.location_poll_enabled = true
	GameState.faint_wake_delay = 2.5
	GameState.shelter_override = -1
	TimeOfDay.paused = false
	TimeOfDay.set_time(1, TimeOfDay.START_HOUR)


## Adds a node to the scene root and frees it in after_each.
func spawn(n: Node, parent: Node = null) -> Node:
	(parent if parent != null else tree.root).add_child(n)
	_spawned.append(n)
	return n


func spawn_player(pos: Vector3 = Vector3.ZERO) -> FakePlayer:
	var p := FakePlayer.new()
	p.position = pos  # set before entering the tree so physics never sees it at the origin
	spawn(p)
	return p


## Records every emission of a GameEvents signal into _events as [signal_name, args...].
func capture(sig_name: StringName) -> void:
	var sig: Signal = GameEvents.get(sig_name)
	var argc: int = 0
	for s in GameEvents.get_signal_list():
		if s["name"] == String(sig_name):
			argc = (s["args"] as Array).size()
	var cb: Callable
	match argc:
		0: cb = func() -> void: _events.append([sig_name])
		1: cb = func(a: Variant) -> void: _events.append([sig_name, a])
		2: cb = func(a: Variant, b: Variant) -> void: _events.append([sig_name, a, b])
		3: cb = func(a: Variant, b: Variant, c: Variant) -> void: _events.append([sig_name, a, b, c])
		_: cb = func(a: Variant, b: Variant, c: Variant, d: Variant) -> void: _events.append([sig_name, a, b, c, d])
	sig.connect(cb)
	_connections.append([sig, cb])


func events_named(sig_name: StringName) -> Array:
	return _events.filter(func(e: Array) -> bool: return e[0] == sig_name)


## Places a quest-target marker (group quest_target, meta target_id).
func spawn_marker(target_id: String, pos: Vector3, group: StringName = &"quest_target", meta_key: StringName = &"target_id") -> Marker3D:
	var m := Marker3D.new()
	m.name = "Marker_" + target_id
	m.add_to_group(group)
	m.set_meta(meta_key, target_id)
	spawn(m)
	m.global_position = pos
	return m
