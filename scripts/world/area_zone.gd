extends Area3D
## Named city area (market, lake, temple, alley, rooftop …). Emits GameEvents.area_entered(area_id)
## when the player enters, so AudioManager switches ambience and GameState tracks current_area.
## Optional reverb via the Area3D reverb bus fields (set by the builder). Owner: world.

@export var area_id: StringName = &""
## Re-emit the parent area's id when leaving (nested zones, e.g. rooftops inside a street zone).
@export var fallback_area_id: StringName = &""

var _inside := false


func _ready() -> void:
	add_to_group(&"area_zone")
	collision_layer = 1 << 9           # triggers
	collision_mask = 1 << 1            # player
	monitoring = true
	monitorable = false
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


func _on_body_entered(body: Node3D) -> void:
	if not body.is_in_group(&"player"):
		return
	_inside = true
	GameEvents.area_entered.emit(area_id)


func _on_body_exited(body: Node3D) -> void:
	if not body.is_in_group(&"player"):
		return
	_inside = false
	if fallback_area_id != &"":
		GameEvents.area_entered.emit(fallback_area_id)


func is_player_inside() -> bool:
	return _inside
