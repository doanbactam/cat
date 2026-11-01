extends RefCounted
## Shared material_overlay arbitration for highlight effects (owner: player).
## Several systems (interaction focus, cat-sense) may want to outline the same mesh; each sets a
## named layer here and the highest-priority active layer wins. The mesh's original overlay is
## restored when every layer is cleared.

const META_ORIG := &"_ovl_orig"
const META_LAYERS := &"_ovl_layers"

## Lower number = higher priority.
const PRIORITY := {&"focus": 0, &"sense": 1, &"sense_npc": 2}


static func set_layer(node: Node, layer: StringName, mat: Material) -> void:
	for gi in _geometry(node):
		if not gi.has_meta(META_LAYERS):
			gi.set_meta(META_ORIG, gi.material_overlay)
			gi.set_meta(META_LAYERS, {})
		var layers: Dictionary = gi.get_meta(META_LAYERS)
		layers[layer] = mat
		gi.set_meta(META_LAYERS, layers)
		_refresh(gi)


static func clear_layer(node: Node, layer: StringName) -> void:
	if node == null or not is_instance_valid(node):
		return
	for gi in _geometry(node):
		if not gi.has_meta(META_LAYERS):
			continue
		var layers: Dictionary = gi.get_meta(META_LAYERS)
		layers.erase(layer)
		if layers.is_empty():
			gi.material_overlay = gi.get_meta(META_ORIG) as Material
			gi.remove_meta(META_LAYERS)
			gi.remove_meta(META_ORIG)
		else:
			gi.set_meta(META_LAYERS, layers)
			_refresh(gi)


static func _refresh(gi: GeometryInstance3D) -> void:
	var layers: Dictionary = gi.get_meta(META_LAYERS)
	var best: Material = null
	var best_p := 1 << 20
	for k: StringName in layers:
		var p: int = PRIORITY.get(k, 10)
		if p < best_p:
			best_p = p
			best = layers[k]
	gi.material_overlay = best


static func _geometry(node: Node) -> Array[GeometryInstance3D]:
	var out: Array[GeometryInstance3D] = []
	if node == null or not is_instance_valid(node):
		return out
	if node is GeometryInstance3D:
		out.append(node as GeometryInstance3D)
	for c in node.find_children("*", "GeometryInstance3D", true, false):
		out.append(c as GeometryInstance3D)
	return out
