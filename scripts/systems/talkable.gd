class_name Talkable
extends Interactable
## Lets Cam "talk" to an NPC or animal: delivers a carried quest item if an active objective
## wants it, then opens the dialogue (or reports talk_to when there is no dialogue).
## Usually a child Area3D of the NPC; the parent is the speaker node (animations/facing hooks:
## on_dialogue_started(id), on_dialogue_ended(id), play_dialogue_anim(name)).

@export var dialogue_id: StringName = &""
## NPC id (ba_tu, mun, bong, lao_qua, ...). Also used as the quest target id.
@export var speaker_id: StringName = &""
## Node that speaks (defaults to the parent).
@export var speaker_path: NodePath
## Hand over the mouth item to an active deliver objective before the dialogue starts.
@export var deliver_on_talk := true


func _ready() -> void:
	if verb == &"interact":
		verb = &"talk"
	if interact_distance == 1.2:
		interact_distance = 1.6
	if speaker_id == &"" and get_parent() != null:
		var p := get_parent()
		if "npc_id" in p and str(p.get("npc_id")) != "":
			speaker_id = StringName(str(p.get("npc_id")))
		elif p.has_meta(&"npc_id"):
			speaker_id = StringName(str(p.get_meta(&"npc_id")))
	if target_id == &"" and speaker_id != &"":
		target_id = speaker_id
	if display_name_key == "" and speaker_id != &"":
		display_name_key = "NPC_" + String(speaker_id).to_upper()
	super._ready()
	set_meta(&"speaker_id", String(speaker_id))


func get_speaker_node() -> Node:
	if not speaker_path.is_empty():
		var n := get_node_or_null(speaker_path)
		if n != null:
			return n
	return get_parent() if get_parent() != null else self


func _extra_checks(_player: Node) -> bool:
	return not DialogueManager.is_active()


func _do_interact(_player: Node) -> void:
	if deliver_on_talk:
		QuestManager.try_deliver(speaker_id)
	if dialogue_id != &"" and DialogueManager.has_dialogue(dialogue_id):
		DialogueManager.start(dialogue_id, get_speaker_node(), speaker_id)
	else:
		QuestManager.report(&"talk_to", {"npc_id": speaker_id})
