class_name ScratchPost
extends Interactable
## A good scratching surface (tree trunk, rattan chair, wooden post). Scratching sharpens claws
## (timed "sharp_claws" buff: faster climbing), grants a little XP once per day and makes a bit
## of noise. Optionally also counts as a territory mark.

@export var post_id: StringName = &""
## Buff granted (skills.json "buffs").
@export var buff_id: StringName = &"sharp_claws"
@export var buff_hours := -1.0
## Also scent-marks this spot as territory (see TerritorySpot).
@export var marks_territory := false
@export var territory_faction: StringName = &"rooftop_cats"


func _ready() -> void:
	if verb == &"interact":
		verb = &"scratch"
	if post_id == &"":
		post_id = StringName(String(name).to_snake_case())
	if target_id == &"":
		target_id = post_id
	if player_action == &"":
		player_action = &"scratch"
	if noise_loudness == 0.0:
		noise_loudness = 0.2
	if sfx == &"":
		sfx = &"cat_scratch"
	super._ready()


func _do_interact(_player: Node) -> void:
	GameState.add_buff(buff_id, buff_hours)
	GameState.increment_counter(&"scratches")
	var key := StringName("scratch_day:" + String(post_id))
	var st := GameState.get_world_state(key)
	if int(st.get("day", -1)) != TimeOfDay.day:
		GameState.set_world_state(key, {"day": TimeOfDay.day})
		GameState.add_xp(int(GameState.XP_REWARDS["scratch_daily"]), "scratch")
	if marks_territory and GameState.mark_territory(post_id):
		GameState.add_reputation(territory_faction, 2)
		GameState.add_xp(int(GameState.XP_REWARDS["territory"]), "territory")
