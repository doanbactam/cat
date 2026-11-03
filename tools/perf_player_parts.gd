extends SceneTree
## Times the expensive pieces of the player setup in isolation.
## Usage: godot --path . --script res://tools/perf_player_parts.gd


func _initialize() -> void:
	var t := Time.get_ticks_usec()
	var fur: GDScript = load("res://scripts/player/fur_shells.gd")
	print("PARTS load fur_shells.gd %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	t = Time.get_ticks_usec()
	fur.call(&"get_strand_texture")
	print("PARTS strand texture gen %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	t = Time.get_ticks_usec()
	var ps := load("res://assets/models/cat/cat.glb") as PackedScene
	print("PARTS load cat.glb %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	t = Time.get_ticks_usec()
	var m := ps.instantiate()
	print("PARTS instantiate cat.glb %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	m.free()
	t = Time.get_ticks_usec()
	var pl := load("res://scenes/player/cat_player.tscn") as PackedScene
	print("PARTS load cat_player.tscn (rest) %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	var inst := pl.instantiate()
	t = Time.get_ticks_usec()
	root.add_child(inst)
	print("PARTS player add_child %d ms" % ((Time.get_ticks_usec() - t) / 1000))
	quit()
