class_name PickupItem
extends Interactable
## An item lying in the world. Mouth-type items (items.json "mouth": true) go into Cam's mouth —
## if the mouth is full the carried item is dropped here in exchange (swap). Other items (caps,
## photos...) go to the stash. Emits GameEvents.item_picked_up. With a persistent_id a picked
## item stays gone after save/load; with respawn_hours > 0 it reappears after that many game hours.

@export var item_id: StringName = &"cap"
@export_range(1, 999) var amount := 1
## Drop the current mouth item here when picking up another mouth item.
@export var swap_if_mouth_full := true
## Instance the item's mesh (items.json "mesh") when this node has no visual child.
@export var spawn_visual := true
## Game hours until it reappears (≤ 0: never — the node is freed when picked up).
@export var respawn_hours := -1.0

var _visual: Node3D = null
var _respawn_at := -1.0


func _ready() -> void:
	if verb == &"interact":
		verb = &"pickup"
	if target_id == &"":
		target_id = StringName("pickup_" + String(item_id))
	super._ready()
	if spawn_visual:
		_ensure_visual()
	if persistent_id != &"":
		var st := GameState.get_world_state(persistent_id)
		if bool(st.get("picked", false)):
			if respawn_hours > 0.0 and float(st.get("respawn_at", -1.0)) >= 0.0:
				_respawn_at = float(st["respawn_at"])
				_set_present(false)
			else:
				queue_free()
				return
	GameEvents.time_tick.connect(_on_time_tick)


func get_display_name() -> String:
	var n := GameState.get_item_name(item_id, true)
	return n if amount <= 1 else "%s ×%d" % [n, amount]


func get_prompt(player: Node) -> String:
	var mouth := GameState.is_mouth_item(item_id)
	if mouth and GameState.mouth_item != &"" and GameState.mouth_item != item_id and swap_if_mouth_full:
		return tr("PROMPT_SWAP").format({"held": GameState.get_item_name(GameState.mouth_item, true), "name": get_display_name()})
	if prompt_key == "":
		return tr("PROMPT_PICKUP_MOUTH" if mouth else "PROMPT_PICKUP").format({"name": get_display_name()})
	return super.get_prompt(player)


func _extra_checks(_player: Node) -> bool:
	if not visible:
		return false
	if not GameState.item_exists(item_id):
		return false
	var def := GameState.get_item_def(item_id)
	if GameState.item_count(item_id) >= int(def.get("stack", 999)) and not bool(def.get("mouth", false)):
		return false
	if bool(def.get("mouth", false)) and GameState.mouth_item != &"":
		if GameState.mouth_item == item_id and int(def.get("stack", 1)) <= 1:
			return false
		return swap_if_mouth_full
	return true


func get_lock_reason(player: Node) -> String:
	var r := super.get_lock_reason(player)
	if r != "":
		return r
	if GameState.is_mouth_item(item_id) and GameState.mouth_item != &"" and not swap_if_mouth_full:
		return tr("REQ_MOUTH_EMPTY")
	return ""


func _do_interact(player: Node) -> void:
	var def := GameState.get_item_def(item_id)
	var mouth := bool(def.get("mouth", false))
	if mouth and GameState.mouth_item != &"" and GameState.mouth_item != item_id:
		var dropped := GameState.drop_mouth_item()
		if dropped != &"" and get_parent() != null:
			spawn_dropped(dropped, global_transform, get_parent())
	var added := GameState.add_item(item_id, amount)
	if mouth:
		GameState.set_mouth_item(item_id)
	if added > 0:
		GameEvents.item_picked_up.emit(item_id, added)
	if player != null and player.has_method("play_action") and player_action == &"":
		player.call("play_action", &"pickup")
	GameEffects.play_sfx(StringName(String(def.get("pickup_sfx", "cat_pickup"))), global_position)
	if respawn_hours > 0.0:
		_respawn_at = TimeOfDay.get_absolute_minutes() + respawn_hours * 60.0
		_set_present(false)
		_persist({"picked": true, "respawn_at": _respawn_at})
	else:
		_persist({"picked": true})
		queue_free()


func _persist(d: Dictionary) -> void:
	if persistent_id != &"":
		GameState.set_world_state(persistent_id, d)


func _set_present(present: bool) -> void:
	visible = present
	enabled = present
	set_deferred(&"monitorable", present)


func _on_time_tick(_hour: float, _day: int) -> void:
	if _respawn_at >= 0.0 and TimeOfDay.get_absolute_minutes() >= _respawn_at:
		_respawn_at = -1.0
		_set_present(true)
		_persist({"picked": false})


# --- visuals -------------------------------------------------------------------------------------

func _ensure_visual() -> void:
	for c in get_children():
		if c is VisualInstance3D or (c is Node3D and not c is CollisionShape3D):
			_visual = c
			return
	_visual = create_item_visual(item_id)
	if _visual != null:
		add_child(_visual)


## Visual for an item: its GLB from items.json "mesh" when it exists, otherwise a small
## procedural stand-in sized like the real object (logged in docs/placeholders.md).
static func create_item_visual(id: StringName) -> Node3D:
	var def := GameState.get_item_def(id)
	var path := String(def.get("mesh", ""))
	if path != "" and ResourceLoader.exists(path):
		var ps := load(path) as PackedScene
		if ps != null:
			var inst := ps.instantiate() as Node3D
			if inst != null:
				inst.name = "Visual"
				return inst
	return _procedural_visual(id, def)


static func _procedural_visual(id: StringName, def: Dictionary) -> Node3D:
	var mi := MeshInstance3D.new()
	mi.name = "Visual"
	var mat := StandardMaterial3D.new()
	mat.roughness = 0.55
	var cat := String(def.get("category", ""))
	var sid := String(id)
	if sid == "cap":
		var cy := CylinderMesh.new()
		cy.top_radius = 0.0135
		cy.bottom_radius = 0.0145
		cy.height = 0.006
		cy.radial_segments = 21  # crown-cork teeth
		mi.mesh = cy
		mi.position.y = 0.003
		mat.albedo_color = Color(0.62, 0.08, 0.07)
		mat.metallic = 0.85
		mat.roughness = 0.38
	elif cat == "memory":
		var bx := BoxMesh.new()
		bx.size = Vector3(0.089, 0.0015, 0.064)  # 3.5 × 2.5 inch print
		mi.mesh = bx
		mi.position.y = 0.001
		mat.albedo_color = Color(0.78, 0.69, 0.55)
		mat.roughness = 0.8
	elif sid in ["fish", "dried_fish"]:
		var cp := CapsuleMesh.new()
		cp.radius = 0.024 if sid == "fish" else 0.012
		cp.height = 0.22 if sid == "fish" else 0.13
		mi.mesh = cp
		mi.rotation_degrees = Vector3(0.0, 0.0, 90.0)
		mi.scale = Vector3(1.0, 1.0, 0.55)
		mi.position.y = cp.radius * 0.6
		mat.albedo_color = Color(0.55, 0.6, 0.62) if sid == "fish" else Color(0.55, 0.42, 0.25)
		mat.metallic = 0.35 if sid == "fish" else 0.0
		mat.roughness = 0.3 if sid == "fish" else 0.75
	elif sid == "lucky_cat_figurine":
		var cy2 := CapsuleMesh.new()
		cy2.radius = 0.03
		cy2.height = 0.1
		mi.mesh = cy2
		mi.position.y = 0.05
		mat.albedo_color = Color(0.83, 0.62, 0.2)
		mat.metallic = 1.0
		mat.roughness = 0.25
	else:
		var sp := SphereMesh.new()
		sp.radius = 0.025
		sp.height = 0.05
		mi.mesh = sp
		mi.position.y = 0.025
		mat.albedo_color = Color(0.7, 0.66, 0.6)
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	var root := Node3D.new()
	root.name = "Visual"
	mi.name = "Mesh"
	root.add_child(mi)
	return root


## Spawns a dropped item in the world, snapped to the ground below `at`. Returns the pickup.
static func spawn_dropped(id: StringName, at: Transform3D, parent: Node) -> PickupItem:
	var p := PickupItem.new()
	p.item_id = id
	p.amount = 1
	p.name = "Dropped_%s" % String(id)
	var pos := at.origin
	var vp: Viewport = parent.get_viewport() if parent.is_inside_tree() else null
	if vp != null:
		var world := vp.get_world_3d()
		if world != null:
			var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.3, pos + Vector3.DOWN * 3.0, LAYER_WORLD | LAYER_PROPS)
			var hit := world.direct_space_state.intersect_ray(q)
			if not hit.is_empty():
				pos = hit["position"]
	parent.add_child(p)
	var yaw := at.basis.get_euler().y
	p.global_transform = Transform3D(Basis(Vector3.UP, yaw), pos)
	return p
