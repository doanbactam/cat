class_name Interactable
extends Area3D
## Base class for everything Cam can interact with (owner: systems).
##
## Lives on physics layer 5 "interactable" in group "interactable" (and "quest_target", meta
## target_id). The player scans for these, shows get_prompt(), checks can_interact() and calls
## interact(); the PLAYER emits GameEvents.interacted (QuestManager listens to it).
## Subclasses override _do_interact(player) (and optionally get_display_name / _extra_checks).
## If no CollisionShape3D child is present a small sphere is created automatically.

signal used(player: Node)

const LAYER_WORLD := 1
const LAYER_PLAYER := 1 << 1
const LAYER_NPC := 1 << 2
const LAYER_PROPS := 1 << 3
const LAYER_INTERACTABLE := 1 << 4
const LAYER_CLIMBABLE := 1 << 5
const LAYER_WATER := 1 << 6
const LAYER_VEHICLES := 1 << 7
const LAYER_TRIGGERS := 1 << 9

@export var verb: StringName = &"interact"
## Max distance (m) from the player's origin to this node's origin.
@export var interact_distance := 1.2
## Mesh outlined by cat-sense / focus highlight (defaults to the first MeshInstance3D found).
@export var highlight_target: NodePath
## Id used by quests ("interact" objectives, markers). Defaults to the node name.
@export var target_id: StringName = &""
## Translation key override for the prompt; default "PROMPT_<VERB>" formatted with {name}.
@export var prompt_key: String = ""
## Translation key of the thing's display name ({name} in the prompt).
@export var display_name_key: String = ""
@export var enabled := true
## Disable after the first successful use.
@export var one_shot := false
## Real seconds between two uses.
@export var cooldown := 0.5
## When set, one_shot usage is remembered in the save (GameState world state).
@export var persistent_id: StringName = &""

@export_group("Requirements")
## Condition (see GameConditions) that must hold, e.g. {"flag": "met_mun"} or {"attribute": "charm", "gte": 3}.
@export var requirement: Dictionary = {}
## Show the prompt (greyed, with the requirement) even when the requirement is not met.
@export var show_when_locked := true

@export_group("Feedback")
## XP granted on the first use only.
@export var first_use_xp := 0
## GameEvents.player_noise loudness (0..1) emitted on use (scaled by the noise_mult modifier).
@export_range(0.0, 1.0, 0.01) var noise_loudness := 0.0
@export var sfx: StringName = &""
## Animation the player should play (calls player.play_action(name) when the player has it).
@export var player_action: StringName = &""

@export_group("Collision")
@export var auto_collision_shape := true
@export var shape_radius := 0.3
@export var shape_offset := Vector3(0.0, 0.15, 0.0)

var _last_used_msec := -1000000
var use_count := 0


func _ready() -> void:
	add_to_group(&"interactable")
	collision_layer = LAYER_INTERACTABLE
	collision_mask = 0
	monitorable = true
	monitoring = false
	if target_id == &"":
		target_id = StringName(String(name))
	set_meta(&"target_id", String(target_id))
	add_to_group(&"quest_target")
	if auto_collision_shape:
		_ensure_shape()
	if persistent_id != &"" and bool(GameState.get_world_state(persistent_id).get("used", false)):
		_on_restored_used()


## Translated prompt, e.g. "Ngậm cá". Locked prompts append the requirement.
func get_prompt(_player: Node) -> String:
	var key := prompt_key if prompt_key != "" else "PROMPT_" + String(verb).to_upper()
	var text := tr(key).format({"name": get_display_name()})
	var reason := get_lock_reason(_player)
	if reason != "":
		text += " (%s)" % reason
	return text


func can_interact(player: Node) -> bool:
	if not enabled or not is_inside_tree():
		return false
	if Time.get_ticks_msec() - _last_used_msec < int(cooldown * 1000.0):
		return false
	if GameState.is_fainted:
		return false
	if player is Node3D and (player as Node3D).global_position.distance_to(global_position) > interact_distance + 0.35:
		return false
	if not requirement.is_empty() and not GameConditions.evaluate(requirement, {"target_id": String(target_id)}):
		return false
	return _extra_checks(player)


## Whether the player should show this at all (focus candidates).
func is_visible_to(player: Node) -> bool:
	if not enabled:
		return false
	if not requirement.is_empty() and not show_when_locked and not GameConditions.evaluate(requirement):
		return false
	return _extra_checks(player) or show_when_locked


## Translated reason why interaction is blocked ("" when it isn't, or when it's not explainable).
func get_lock_reason(_player: Node) -> String:
	if not requirement.is_empty() and not GameConditions.evaluate(requirement):
		return GameConditions.describe(requirement)
	return ""


func interact(player: Node) -> void:
	if not can_interact(player):
		return
	_last_used_msec = Time.get_ticks_msec()
	use_count += 1
	if player_action != &"" and player != null and player.has_method("play_action"):
		player.call("play_action", player_action)
	if sfx != &"":
		GameEffects.play_sfx(sfx, global_position)
	if noise_loudness > 0.0:
		GameEvents.player_noise.emit(global_position, clampf(noise_loudness * GameState.get_modifier(&"noise_mult"), 0.0, 1.0))
	if first_use_xp > 0 and not _was_used_before():
		GameState.add_xp(first_use_xp, String(verb))
	_mark_used()
	_do_interact(player)
	used.emit(player)
	if one_shot:
		enabled = false


func get_display_name() -> String:
	if display_name_key != "":
		return tr(display_name_key)
	return tr("PROP_OBJECT")


## The node to outline when focused / in cat-sense.
func get_highlight_node() -> Node3D:
	if not highlight_target.is_empty():
		var n := get_node_or_null(highlight_target) as Node3D
		if n != null:
			return n
	var m := _find_mesh(self)
	if m == null and get_parent() != null:
		m = _find_mesh(get_parent())
	return m


## Where the UI prompt / quest marker should float.
func get_interaction_position() -> Vector3:
	return global_position + shape_offset


# --- virtuals ----------------------------------------------------------------------------------

func _do_interact(_player: Node) -> void:
	pass


func _extra_checks(_player: Node) -> bool:
	return true


## Called in _ready when the persistent state says this was used (one_shot) in a loaded game.
func _on_restored_used() -> void:
	if one_shot:
		enabled = false


# --- helpers -----------------------------------------------------------------------------------

func _was_used_before() -> bool:
	if persistent_id != &"":
		return bool(GameState.get_world_state(persistent_id).get("used", false))
	return use_count > 1


func _mark_used() -> void:
	if persistent_id != &"":
		var st := GameState.get_world_state(persistent_id)
		st["used"] = true
		st["count"] = int(st.get("count", 0)) + 1
		GameState.set_world_state(persistent_id, st)


func _ensure_shape() -> void:
	for c in get_children():
		if c is CollisionShape3D or c is CollisionPolygon3D:
			return
	var cs := CollisionShape3D.new()
	cs.name = "AutoShape"
	var sh := SphereShape3D.new()
	sh.radius = shape_radius
	cs.shape = sh
	cs.position = shape_offset
	add_child(cs)


static func _find_mesh(root: Node) -> MeshInstance3D:
	if root is MeshInstance3D:
		return root
	for c in root.get_children():
		if c is Interactable:
			continue
		var m := _find_mesh(c)
		if m != null:
			return m
	return null
