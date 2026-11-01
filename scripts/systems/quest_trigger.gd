class_name QuestTrigger
extends Interactable
## Reports to QuestManager when Cam walks in (mode ENTER, a trigger volume on layer 10) or when he
## interacts with it (mode INTERACT, a normal interactable). Can also discover a location, start a
## quest and set a flag. With event "reach_location" it emits GameEvents.area_entered(location_id).

enum Mode { ENTER, INTERACT }

@export var mode: Mode = Mode.ENTER
## Event reported to QuestManager.report(). "reach_location" → area_entered(location_id).
@export var event: StringName = &"reach_location"
## Extra event data (merged with location_id / target_id).
@export var event_data: Dictionary = {}
@export var location_id: StringName = &""
## Discover location_id (GameState.discover_location) on trigger.
@export var discover_location := true
@export var start_quest: StringName = &""
@export var set_flag: StringName = &""
## Only fires while this quest is active (empty = always).
@export var required_quest_active: StringName = &""
## Fire only once (persisted when persistent_id is set).
@export var trigger_once := false
## Size of the auto-created box volume in ENTER mode.
@export var box_size := Vector3(3.0, 2.5, 3.0)

var fired_count := 0


func _ready() -> void:
	if location_id == &"" and event == &"reach_location":
		location_id = target_id if target_id != &"" else StringName(String(name).to_snake_case())
	if target_id == &"" and location_id != &"":
		target_id = location_id
	if mode == Mode.ENTER and auto_collision_shape:
		_ensure_box()
	super._ready()
	if mode == Mode.ENTER:
		remove_from_group(&"interactable")
		collision_layer = LAYER_TRIGGERS
		collision_mask = LAYER_PLAYER
		monitoring = true
		monitorable = false
		body_entered.connect(_on_body_entered)
	if location_id != &"":
		set_meta(&"location_id", String(location_id))


func _ensure_box() -> void:
	for c in get_children():
		if c is CollisionShape3D or c is CollisionPolygon3D:
			return
	var cs := CollisionShape3D.new()
	cs.name = "AutoBox"
	var b := BoxShape3D.new()
	b.size = box_size
	cs.shape = b
	cs.position = Vector3(0.0, box_size.y * 0.5, 0.0)
	add_child(cs)


func _on_body_entered(body: Node3D) -> void:
	if body.is_in_group(&"player"):
		fire(body)


func _extra_checks(_player: Node) -> bool:
	return _can_fire()


func _do_interact(player: Node) -> void:
	fire(player, true)


func _can_fire() -> bool:
	if not enabled:
		return false
	if trigger_once and (fired_count > 0 or (persistent_id != &"" and bool(GameState.get_world_state(persistent_id).get("fired", false)))):
		return false
	if required_quest_active != &"" and not QuestManager.is_active(required_quest_active):
		return false
	return true


## Fires the trigger (also callable from scripts/cutscenes). Returns false when blocked.
func fire(player: Node = null, from_interact: bool = false) -> bool:
	if not _can_fire():
		return false
	fired_count += 1
	if persistent_id != &"":
		var st := GameState.get_world_state(persistent_id)
		st["fired"] = true
		GameState.set_world_state(persistent_id, st)
	if location_id != &"" and discover_location:
		var key := display_name_key if display_name_key != "" else "LOC_" + String(location_id).to_upper()
		GameState.discover_location(location_id, tr(key))
	if event == &"reach_location":
		GameEvents.area_entered.emit(location_id)
	elif event != &"":
		var data := event_data.duplicate()
		data["target_id"] = String(target_id)
		if location_id != &"":
			data["location_id"] = String(location_id)
		QuestManager.report(event, data)
	if start_quest != &"":
		QuestManager.start_quest(start_quest)
	if set_flag != &"":
		GameState.set_flag(set_flag, true)
	if not from_interact:
		used.emit(player)
	if trigger_once:
		enabled = false
	return true
