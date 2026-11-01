class_name Collectible
extends Interactable
## A unique, persistent collectible: a memory photograph (Kỷ niệm 1–12), a cap stash, a feather...
## Collecting records it (GameState.mark_collectible), adds the item to the stash, grants XP and
## shows a toast; it never respawns. Caps can be auto-collected by touch.

@export var collectible_id: StringName = &""
## &"memory", &"caps" or &"item".
@export var kind: StringName = &"memory"
## Item added to the stash (memory → memory_03, caps → cap).
@export var item_id: StringName = &""
@export_range(1, 999) var amount := 1
## XP for finding it (−1 = default: memory 40, others 5).
@export var xp_reward := -1
## Collect by simply walking over it (good for scattered caps).
@export var auto_collect_on_touch := false
@export var spawn_visual := true

var _collected := false


func _ready() -> void:
	if collectible_id == &"":
		collectible_id = StringName(String(name).to_snake_case())
	if item_id == &"":
		item_id = &"cap" if kind == &"caps" else collectible_id
	if verb == &"interact":
		verb = &"collect"
	if target_id == &"":
		target_id = collectible_id
	if player_action == &"":
		player_action = &"pickup"
	super._ready()
	if GameState.is_collectible_found(collectible_id):
		queue_free()
		return
	add_to_group(&"collectible")
	if spawn_visual:
		var has_visual := false
		for c in get_children():
			if c is Node3D and not c is CollisionShape3D:
				has_visual = true
		if not has_visual:
			var v := PickupItem.create_item_visual(item_id)
			if v != null:
				add_child(v)
	if auto_collect_on_touch:
		monitoring = true
		collision_mask = LAYER_PLAYER
		body_entered.connect(_on_body_entered)


func get_display_name() -> String:
	if display_name_key != "":
		return tr(display_name_key)
	var n := GameState.get_item_name(item_id, true)
	return n if amount <= 1 else "%s ×%d" % [n, amount]


func _extra_checks(_player: Node) -> bool:
	return not _collected


func _on_body_entered(body: Node3D) -> void:
	if body.is_in_group(&"player") and not _collected and enabled:
		collect(body)


func _do_interact(player: Node) -> void:
	collect(player)


## Collects it (callable directly). Returns false if already collected.
func collect(_player: Node = null) -> bool:
	if _collected or not GameState.mark_collectible(collectible_id):
		_collected = true
		queue_free()
		return false
	_collected = true
	var added := GameState.add_item(item_id, amount)
	if added > 0:
		GameEvents.item_picked_up.emit(item_id, added)
	var xp := xp_reward
	if xp < 0:
		xp = int(GameState.XP_REWARDS["memory"]) if kind == &"memory" else int(GameState.XP_REWARDS["collectible"])
	GameState.add_xp(xp, "collectible")
	if kind == &"memory":
		GameEvents.notify.emit(tr("NOTIFY_MEMORY_FOUND").format({"name": GameState.get_item_name(item_id),
			"count": GameState.count_items_in_category(&"memory")}), &"memory")
		GameEffects.play_sfx(&"stinger_memory")
	else:
		GameEffects.play_sfx(StringName(String(GameState.get_item_def(item_id).get("pickup_sfx", "cat_pickup"))), global_position)
	visible = false
	enabled = false
	queue_free()
	return true
