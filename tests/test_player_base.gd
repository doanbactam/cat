extends "res://tests/test_base.gd"
## Shared helpers for tests/test_player_*.gd (owner: player). Not a test file itself (no test_*).
## Builds a tiny physics world per test, spawns the real scenes/player/cat_player.tscn, simulates
## input with Input.action_press/release and steps real physics frames.

const PLAYER_SCENE := "res://scenes/player/cat_player.tscn"
const ALL_ACTIONS: Array[StringName] = [
	&"move_forward", &"move_back", &"move_left", &"move_right", &"look_up", &"look_down",
	&"look_left", &"look_right", &"sprint", &"sneak", &"jump", &"interact", &"pickup_drop",
	&"meow", &"swipe", &"aim_jump", &"cat_sense", &"sit_groom", &"toggle_camera", &"zoom_in", &"zoom_out",
]

var world: Node3D = null
var player: CharacterBody3D = null
var events: Array = []
var _conns: Array = []


func before_each() -> void:
	release_all()
	GameState.autosave_enabled = false
	GameState.simulation_enabled = false
	GameState.location_poll_enabled = false
	TimeOfDay.paused = true
	GameState.new_game()
	GameState.wetness = 0.0
	world = Node3D.new()
	world.name = "PlayerTestWorld"
	tree.root.add_child(world)
	events.clear()


func after_each() -> void:
	release_all()
	for c: Array in _conns:
		var sig: Signal = c[0]
		if sig.is_connected(c[1]):
			sig.disconnect(c[1])
	_conns.clear()
	if is_instance_valid(world):
		world.free()
	world = null
	player = null
	GameState.wetness = 0.0
	GameState.autosave_enabled = true
	GameState.simulation_enabled = true
	GameState.location_poll_enabled = true
	TimeOfDay.paused = false
	RenderingServer.global_shader_parameter_set(&"cat_sense", 0.0)


func release_all() -> void:
	for a in ALL_ACTIONS:
		if InputMap.has_action(a):
			Input.action_release(a)


## Records every emission of `sig` as [name, args...] into `events`.
func watch(sig: Signal, label: String) -> void:
	var cb := func(a: Variant = null, b: Variant = null, c: Variant = null) -> void:
		events.append([label, a, b, c])
	sig.connect(cb)
	_conns.append([sig, cb])


func count_events(label: String) -> int:
	var n := 0
	for e: Array in events:
		if e[0] == label:
			n += 1
	return n


func last_event(label: String) -> Array:
	for i in range(events.size() - 1, -1, -1):
		if events[i][0] == label:
			return events[i]
	return []


func box(center: Vector3, size: Vector3, layers := 1, surface := &"concrete") -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = layers
	b.collision_mask = 0
	b.set_meta(&"surface", surface)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	b.add_child(cs)
	world.add_child(b)
	b.position = center
	return b


func ground(size := 30.0) -> StaticBody3D:
	return box(Vector3(0, -0.25, 0), Vector3(size, 0.5, size))


func spawn_player(pos: Vector3, yaw := 0.0) -> CharacterBody3D:
	var ps := load(PLAYER_SCENE) as PackedScene
	player = ps.instantiate() as CharacterBody3D
	world.add_child(player)
	player.call(&"teleport", Transform3D(Basis(Vector3.UP, yaw), pos))
	return player


## Wait until the freshly spawned cat stands on the floor (bodies of the previous test may
## linger in the physics space for a step).
func settle(timeout := 1.5) -> void:
	await step(2)
	await wait_until(func() -> bool: return player != null and player.is_on_floor() and int(player.call(&"get_mode")) == 0 and player.call(&"get_state") in [&"idle", &"idle_look", &"sneak_idle", &"balance"], timeout)
	await step(2)


func step(n: int) -> void:
	for i in n:
		await tree.physics_frame


func seconds(s: float) -> void:
	await step(int(ceil(s * float(Engine.physics_ticks_per_second))))


func hold(action: StringName, strength := 1.0) -> void:
	Input.action_press(action, strength)


func release(action: StringName) -> void:
	Input.action_release(action)


## Press for a few physics frames then release (a "tap").
func tap(action: StringName, frames := 3) -> void:
	Input.action_press(action)
	await step(frames)
	Input.action_release(action)


## Waits until cond() is true or `timeout` seconds passed. Returns whether it became true.
func wait_until(cond: Callable, timeout := 3.0) -> bool:
	var n := int(timeout * float(Engine.physics_ticks_per_second))
	for i in n:
		if cond.call():
			return true
		await tree.physics_frame
	return bool(cond.call())
