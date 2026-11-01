class_name NapSpot
extends Interactable
## A place where Cam curls up and sleeps: time fast-forwards, energy/warmth/health recover at
## sleep rates, the spot becomes the faint-respawn point, first nap here grants XP, and
## GameEvents.cat_napped (→ nap objectives) fires. Autosaves.

@export var spot_id: StringName = &""
## Hours slept (ignored when sleep_until_hour ≥ 0).
@export_range(0.5, 12.0, 0.25) var sleep_hours := 2.0
## Sleep until this hour (e.g. 6.0 = next morning). < 0 disables.
@export var sleep_until_hour := -1.0
## Dry spot (under a roof/awning). False → uses the live shelter test.
@export var sheltered := true
## Extra warmth per game hour (sunny ledge, warm stove, cushion).
@export var warmth_bonus := 0.0
## Energy regen multiplier (a soft cushion > a hard ledge).
@export_range(0.5, 2.0, 0.05) var comfort := 1.0
## Where Cam wakes up, relative to this node.
@export var wake_offset := Vector3(0.0, 0.0, 0.25)


func _ready() -> void:
	if verb == &"interact":
		verb = &"sleep"
	if spot_id == &"":
		spot_id = StringName(String(name).to_snake_case())
	if target_id == &"":
		target_id = spot_id
	if player_action == &"":
		player_action = &"lie_down"
	if sfx == &"":
		sfx = &"cat_yawn"
	super._ready()
	add_to_group(&"nap_spot")


func get_prompt(player: Node) -> String:
	if prompt_key != "":
		return super.get_prompt(player)
	if sleep_until_hour >= 0.0:
		return tr("PROMPT_SLEEP_UNTIL").format({"time": "%02d:%02d" % [int(sleep_until_hour), int(fmod(sleep_until_hour, 1.0) * 60.0)]})
	var h := str(int(sleep_hours)) if is_equal_approx(fmod(sleep_hours, 1.0), 0.0) else "%.1f" % sleep_hours
	return tr("PROMPT_SLEEP").format({"hours": h})


func _extra_checks(_player: Node) -> bool:
	return not DialogueManager.is_active()


func get_wake_transform() -> Transform3D:
	return global_transform * Transform3D(Basis.IDENTITY, wake_offset)


func _do_interact(_player: Node) -> void:
	var opts := {
		"sheltered": sheltered or GameState.is_sheltered(),
		"warmth_bonus": warmth_bonus,
		"energy_mult": comfort,
	}
	if sleep_until_hour >= 0.0:
		opts["until_hour"] = sleep_until_hour
	GameState.nap(sleep_hours, spot_id, get_wake_transform(), opts)
