class_name TerritorySpot
extends Interactable
## A scent-marking spot (cheek-rub / scratch). Marking it claims it for Cam: reputation with the
## rooftop cats, XP, GameEvents.territory_marked (→ mark_territory objectives). An optional
## `marked_visual` node (e.g. a subtle scent decal visible in cat-sense) is shown once marked.

@export var spot_id: StringName = &""
@export var faction: StringName = &"rooftop_cats"
@export var reputation_amount := 3
## Node shown when the spot is marked (hidden before).
@export var marked_visual: NodePath
## Cat who "owns" the spot before Cam (flavour for dialogue/AI, e.g. "mun").
@export var rival_owner: StringName = &""


func _ready() -> void:
	if verb == &"interact":
		verb = &"mark"
	if spot_id == &"":
		spot_id = StringName(String(name).to_snake_case())
	if target_id == &"":
		target_id = spot_id
	if player_action == &"":
		player_action = &"rub"
	if noise_loudness == 0.0:
		noise_loudness = 0.05
	super._ready()
	add_to_group(&"territory_spot")
	_update_visual()


func is_marked() -> bool:
	return GameState.is_territory_marked(spot_id)


func _extra_checks(_player: Node) -> bool:
	return not is_marked()


func get_lock_reason(player: Node) -> String:
	if is_marked():
		return tr("REQ_ALREADY_MARKED")
	return super.get_lock_reason(player)


func _do_interact(_player: Node) -> void:
	if GameState.mark_territory(spot_id):
		GameState.add_reputation(faction, reputation_amount)
		GameState.add_xp(int(GameState.XP_REWARDS["territory"]), "territory")
		GameEvents.notify.emit(tr("NOTIFY_TERRITORY_MARKED").format({"count": GameState.get_counter(&"territory_marked")}), &"territory")
	_update_visual()


func _update_visual() -> void:
	if marked_visual.is_empty():
		return
	var v := get_node_or_null(marked_visual) as Node3D
	if v != null:
		v.visible = is_marked()
