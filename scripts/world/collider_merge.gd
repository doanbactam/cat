extends RefCounted
## Merges the many one-box StaticBody3Ds inside instanced asset scenes (city modules have ~40 each)
## into one StaticBody3D per (layer, mask, surface, groups) per instance. Run BEFORE the nodes
## enter the tree (city.gd does it in _enter_tree) so Jolt never creates the original bodies:
## the whole quarter would otherwise exceed Jolt's max body count. Owner: world.


## Returns the number of bodies removed.
static func merge_under(container: Node) -> int:
	var removed := 0
	for inst in container.get_children():
		if inst.scene_file_path == "":
			continue
		removed += merge_instance(inst)
	return removed


static func merge_instance(inst: Node) -> int:
	var buckets: Dictionary = {}
	var bodies: Array[StaticBody3D] = []
	for c in inst.get_children():
		var sb := c as StaticBody3D
		if sb == null or sb.get_script() != null:
			continue
		bodies.append(sb)
	if bodies.size() < 3:
		return 0
	for sb in bodies:
		var groups: Array = []
		for g in sb.get_groups():
			if not String(g).begins_with("_"):
				groups.append(String(g))
		groups.sort()
		var pm := sb.physics_material_override
		var key := "%d|%d|%s|%s|%s|%s" % [sb.collision_layer, sb.collision_mask, str(sb.get_meta(&"surface", "")),
			",".join(PackedStringArray(groups)), str(sb.get_meta(&"balance", false)), str(pm.get_instance_id() if pm else 0)]
		if not buckets.has(key):
			var nb := StaticBody3D.new()
			nb.name = "Merged_" + str(sb.get_meta(&"surface", "col")) + "_%d" % buckets.size()
			nb.collision_layer = sb.collision_layer
			nb.collision_mask = sb.collision_mask
			nb.physics_material_override = pm
			for m in sb.get_meta_list():
				nb.set_meta(m, sb.get_meta(m))
			for g: String in groups:
				nb.add_to_group(StringName(g))
			buckets[key] = nb
		var target: StaticBody3D = buckets[key]
		var body_xf := sb.transform
		for s in sb.get_children():
			var cs := s as CollisionShape3D
			if cs == null:
				continue
			var shape := CollisionShape3D.new()
			shape.shape = cs.shape
			shape.disabled = cs.disabled
			shape.transform = body_xf * cs.transform
			target.add_child(shape)
	var n := 0
	for sb in bodies:
		inst.remove_child(sb)
		sb.free()
		n += 1
	for key: String in buckets:
		inst.add_child(buckets[key])
		n -= 1
	return n
