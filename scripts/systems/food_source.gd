class_name FoodSource
extends Interactable
## Something Cam can eat or drink from: a bowl, a vendor's scraps, a puddle, a fish basket.
## Servings refill every `refill_hours`. Optionally hands an item (into the mouth) instead of
## being eaten on the spot, can require charm (a vendor feeding the cat) or count as stealing
## (noise + lower human reputation). State persists via persistent_id.

@export var source_id: StringName = &""
## Hunger restored (scaled by the food_value modifier).
@export var food_amount := 30.0
@export var health_amount := 3.0
## Drinking water: restores a little energy/health instead of hunger.
@export var is_water := false
## -1 = infinite.
@export var servings := 1
@export var refill_hours := 24.0
## When set, Cam receives this item instead of eating here (e.g. "fish" from the fish stall).
@export var gives_item: StringName = &""
## NPC who owns this food (vendor). Used for stealing / charm reactions.
@export var owner_npc_id: StringName = &""
## Effective charm needed for the owner to share (0 = free food).
@export_range(0, 10) var required_charm := 0
## Taking it is stealing: noise, -reputation with humans, GameEvents.npc_alerted is up to the AI.
@export var is_stealing := false
@export_range(0.0, 1.0, 0.01) var steal_noise := 0.45
@export var steal_reputation_penalty := 2

var _servings_left := 0
var _refill_at := -1.0


func _ready() -> void:
	if verb == &"interact":
		verb = &"drink" if is_water else &"eat"
	if source_id == &"":
		source_id = StringName(String(name).to_snake_case())
	if target_id == &"":
		target_id = source_id
	if persistent_id == &"":
		persistent_id = StringName("food:" + String(source_id))
	if player_action == &"":
		player_action = &"drink" if is_water else &"eat"
	if sfx == &"" and not is_water:
		sfx = &"cat_eat_crunch"
	super._ready()
	_servings_left = servings
	var st := GameState.get_world_state(persistent_id)
	if st.has("servings"):
		_servings_left = int(st["servings"])
		_refill_at = float(st.get("refill_at", -1.0))
	_try_refill()


func get_prompt(player: Node) -> String:
	if prompt_key != "":
		return super.get_prompt(player)
	var key := "PROMPT_DRINK" if is_water else ("PROMPT_STEAL" if is_stealing else "PROMPT_EAT")
	if gives_item != &"" and not is_stealing:
		key = "PROMPT_TAKE"
	var text := tr(key).format({"name": get_display_name()})
	var reason := get_lock_reason(player)
	return text if reason == "" else "%s (%s)" % [text, reason]


func get_display_name() -> String:
	if display_name_key.begins_with("ITEM_"):
		var n := tr(display_name_key)
		return n.left(1).to_lower() + n.substr(1)  # food names are common nouns mid-sentence
	if display_name_key != "":
		return tr(display_name_key)
	if gives_item != &"":
		return GameState.get_item_name(gives_item, true)
	return tr("ITEM_WATER") if is_water else tr("ITEM_FOOD")


func get_lock_reason(player: Node) -> String:
	var r := super.get_lock_reason(player)
	if r != "":
		return r
	if not _has_serving():
		return tr("REQ_EMPTY")
	if required_charm > 0 and GameState.get_effective_attribute(&"charm") < required_charm:
		return tr("REQ_ATTRIBUTE").format({"attribute": tr("ATTR_CHARM"), "value": required_charm})
	return ""


func _extra_checks(_player: Node) -> bool:
	_try_refill()
	if not _has_serving():
		return false
	if required_charm > 0 and GameState.get_effective_attribute(&"charm") < required_charm:
		return false
	if gives_item != &"" and GameState.is_mouth_item(gives_item) and GameState.mouth_item != &"":
		return false
	return true


func get_servings_left() -> int:
	return _servings_left


func _has_serving() -> bool:
	return servings < 0 or _servings_left > 0


func _do_interact(_player: Node) -> void:
	if gives_item != &"":
		var added := GameState.add_item(gives_item, 1)
		if added > 0:
			GameEvents.item_picked_up.emit(gives_item, added)
	elif is_water:
		GameState.modify_stat(&"energy", 4.0)
		GameState.modify_stat(&"health", 2.0)
		GameState.increment_counter(&"drinks")
	else:
		var amount := food_amount
		if not is_stealing and owner_npc_id != &"" and randf() < GameState.get_modifier(&"food_gift_chance"):
			amount *= 1.5  # the vendor adds a little extra for such a sweet cat
		GameState.eat(amount, source_id, health_amount)
	if is_stealing:
		GameEvents.player_noise.emit(global_position, clampf(steal_noise * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))
		GameState.add_reputation(&"humans", -absi(steal_reputation_penalty))
		GameState.increment_counter(&"food_stolen")
	elif owner_npc_id != &"":
		GameState.add_reputation(&"humans", 1)
	if servings >= 0:
		_servings_left -= 1
		if _servings_left <= 0 and refill_hours > 0.0:
			_refill_at = TimeOfDay.get_absolute_minutes() + refill_hours * 60.0
	_save()


func _try_refill() -> void:
	if servings >= 0 and _servings_left <= 0 and _refill_at >= 0.0 and TimeOfDay.get_absolute_minutes() >= _refill_at:
		_servings_left = servings
		_refill_at = -1.0
		_save()


func _save() -> void:
	var st := GameState.get_world_state(persistent_id)
	st["servings"] = _servings_left
	st["refill_at"] = _refill_at
	GameState.set_world_state(persistent_id, st)
