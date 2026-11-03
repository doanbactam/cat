extends SceneTree
## Times each step of LifeDirector.start() inside the real game scene.
## Usage: godot --path . --script res://tools/perf_director.gd

var _frame := 0
var _ld: Node = null


func _initialize() -> void:
	var inst := (load("res://scenes/main/game.tscn") as PackedScene).instantiate()
	_ld = inst.find_child("LifeDirector", true, false)
	_ld.set("auto_start", false)
	root.add_child(inst)
	current_scene = inst


func _t(label: String, c: Callable) -> void:
	var t := Time.get_ticks_usec()
	c.call()
	print("DIRECTOR %-28s %7.1f ms" % [label, (Time.get_ticks_usec() - t) / 1000.0])


func _physics_process(_delta: float) -> bool:
	_frame += 1
	if _frame != 30:
		return false
	_ld.set("started", true)
	_ld.set("player", _ld.call("get_player"))
	var keep: Array = []
	_t("preload npc/vehicle glbs", func() -> void:
		for dir: String in ["res://assets/models/npc/", "res://assets/models/vehicles/"]:
			for f: String in ResourceLoader.list_directory(dir):
				if f.ends_with(".glb"):
					keep.append(load(dir + f)))
	print("DIRECTOR preloaded %d glbs" % keep.size())
	_t("_scan_markers", func() -> void: _ld.call("_scan_markers"))
	_t("_spawn_named_and_animals", func() -> void: _ld.call("_spawn_named_and_animals"))
	_t("_init_traffic", func() -> void: _ld.call("_init_traffic"))
	_t("_populate_pedestrians", func() -> void: _ld.call("_populate_pedestrians", true))
	_t("_update_lod", func() -> void: _ld.call("_update_lod", true))
	quit()
	return true
