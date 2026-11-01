extends SceneTree
## QA helper: prints the imported node tree of street props (types, materials, shapes, metas).
## tools/godot_lock.sh godot --headless --path . --script res://assets/models/props/preview/dump_props.gd -- [id ...]

func _init() -> void:
	_run.call_deferred()


func _run() -> void:
	await process_frame
	var ids := OS.get_cmdline_user_args()
	if ids.is_empty():
		var data: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://assets/models/props/catalog.json"))
		for e: Variant in data:
			ids.append(String(e["id"]))
	for id in ids:
		var ps := load("res://assets/models/props/%s.glb" % id) as PackedScene
		if ps == null:
			print("MISSING ", id)
			continue
		var n := ps.instantiate()
		print("== ", id, " root=", n.get_class(), " script=", n.get_script(), " metas=", n.get_meta_list())
		_dump(n, 1)
		n.free()
	quit(0)


func _dump(n: Node, depth: int) -> void:
	for c in n.get_children():
		var line := "  ".repeat(depth) + "%s (%s)" % [c.name, c.get_class()]
		if c is MeshInstance3D:
			var mi := c as MeshInstance3D
			for s in mi.mesh.get_surface_count():
				var m := mi.mesh.surface_get_material(s) as StandardMaterial3D
				if m:
					line += " [%s cull=%d tr=%d ao=%s em=%s/%0.1f alb=%s]" % [m.resource_name, m.cull_mode, m.transparency, m.ao_enabled, m.emission_enabled, m.emission_energy_multiplier, m.albedo_texture.resource_path if m.albedo_texture else "-"]
			line += " vis_end=%0.0f aabb=%s" % [mi.visibility_range_end, mi.get_aabb()]
		elif c is CollisionShape3D:
			line += " shape=%s pos=%s" % [(c as CollisionShape3D).shape.get_class(), (c as Node3D).position]
		elif c is CollisionObject3D:
			line += " layer=%d metas=%s" % [(c as CollisionObject3D).collision_layer, c.get_meta_list()]
		elif c is Light3D:
			line += " energy=%0.2f meta=%s" % [(c as Light3D).light_energy, c.get_meta(&"night_light_energy", 0.0)]
		print(line)
		_dump(c, depth + 1)
