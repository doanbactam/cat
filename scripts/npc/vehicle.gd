extends AnimatableBody3D
## Traffic vehicle following a `traffic_lane` Path3D (owner: world-life).
##
## * Car-following with the Intelligent Driver Model against the lane leader (LifeDirector keeps
##   per-lane ordering), plus obstacles in a forward corridor: Cam, pedestrians, dogs, NPC cats.
## * Slows/stops for the cat, honks (horn_motorbike / horn_car / bicycle_bell) with a cooldown.
## * If the cat is struck at speed it is knocked back with small damage (GameState health,
##   GameEvents.player_damaged, source &"vehicle") — never lethal on its own.
## * Wheels spin from distance travelled; motorbikes lean into curves; rider stand-ins animate.
## Collision layer 8 "vehicles" (the cat can stand on a stopped car).

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const NpcVisualScript := preload("res://scripts/npc/npc_visual.gd")
const ProcAnim := preload("res://scripts/npc/proc_animator.gd")

const SPECS := {
	&"motorbike": {"length": 1.85, "width": 0.7, "height": 1.15, "v0": 8.5, "a": 2.6, "b": 4.5, "s0": 1.0, "T": 0.9,
		"models": ["motorbike", "scooter", "motorbike_", "scooter_"]},
	&"bicycle": {"length": 1.7, "width": 0.6, "height": 1.1, "v0": 4.2, "a": 1.0, "b": 3.0, "s0": 0.8, "T": 1.0,
		"models": ["bicycle", "bicycle_"]},
	&"car": {"length": 3.85, "width": 1.7, "height": 1.5, "v0": 9.0, "a": 2.0, "b": 4.0, "s0": 2.0, "T": 1.3,
		"models": ["car", "taxi", "car_", "taxi_"]},
}

enum Lod { NEAR, MID, FAR, ASLEEP }

var kind: StringName = &"motorbike"
## Lane sub-kind this vehicle was spawned for (scooter, cyclo, taxi …) — picks the catalog GLB.
var variant: StringName = &""
var lane: Path3D = null
var lane_length := 1.0
var lane_closed := false
var offset := 0.0
var speed := 0.0
var v0 := 8.0
var length := 1.85
var half_width := 0.35
var director: Node = null
var visual: Node3D = null
var lod: Lod = Lod.NEAR
var active := true
## Debug/test state.
var blocked_by_cat := false
var obstacle_gap := INF
var leader: Node3D = null

var _spec: Dictionary = {}
var _riders: Array = []          # [ProcAnim]
var _honk_cd := 0.0
var _hit_cd := 0.0
var _wait_t := 0.0
var _prev_yaw := 0.0
var _lean := 0.0
var _loop: AudioStreamPlayer3D = null
var _light: SpotLight3D = null
var _personal := 1.0
var _rng := RandomNumberGenerator.new()
var _lamp_mats: Array = []       # [[BaseMaterial3D, night_energy]]
var _lamps_on := false


func setup(p_kind: StringName, seed_value: int, p_variant: StringName = &"") -> void:
	kind = p_kind if SPECS.has(p_kind) else &"motorbike"
	variant = p_variant if p_variant != &"" else kind
	_spec = SPECS[kind]
	_rng.seed = seed_value
	length = float(_spec["length"])
	half_width = float(_spec["width"]) * 0.5
	_personal = _rng.randf_range(0.8, 1.12)
	collision_layer = NpcUtil.LAYER_VEHICLES
	collision_mask = 0
	sync_to_physics = false
	add_to_group(&"vehicle")
	set_meta(&"npc_kind", String(kind))
	var cs := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	var h := float(_spec["height"])
	bs.size = Vector3(float(_spec["width"]), h * (0.75 if kind == &"car" else 0.55), length)
	cs.shape = bs
	cs.position = Vector3(0, bs.size.y * 0.5 + (0.12 if kind == &"car" else 0.25), 0)
	add_child(cs)
	var entry := _pick_catalog_entry()
	var names: Array = _spec["models"]
	if not entry.is_empty():
		names = [str(entry["id"])] + names
		length = float(entry.get("length", length))
		half_width = float(entry.get("width", half_width * 2.0)) * 0.5
		bs.size = Vector3(half_width * 2.0, bs.size.y, length)
	visual = NpcVisualScript.new()
	visual.name = "Visual"
	add_child(visual)
	visual.call(&"setup", String(kind), {"model_names": names, "seed": seed_value})
	if not bool(visual.get(&"is_standin")):
		_setup_glb(entry)
	var rig: Dictionary = visual.call(&"get_rig")
	for n: String in ["Rider", "Passenger"]:
		var r := rig.get(n) as Node3D
		if r != null and r.has_meta(&"rig"):
			var pa := ProcAnim.new()
			pa.setup(r)
			pa.play(&"cycle" if kind == &"bicycle" and n == "Rider" else (&"ride" if n == "Rider" else &"passenger"))
			_riders.append(pa)


static var _catalog: Array = []

const CATALOG_KINDS := {&"motorbike": ["scooter", "motorbike"], &"bicycle": ["bicycle", "cyclo", "tricycle"],
	&"car": ["car", "van"]}
## Preferred catalog kinds per lane sub-kind (falls back to CATALOG_KINDS of the base kind).
const VARIANT_CATALOG := {&"scooter": ["scooter"], &"cyclo": ["cyclo"], &"tricycle": ["tricycle"], &"cargo_trike": ["tricycle"],
	&"taxi": ["car"], &"van": ["van"], &"bicycle": ["bicycle"], &"car": ["car", "van"], &"underbone": ["motorbike"]}


func _pick_catalog_entry() -> Dictionary:
	if _catalog.is_empty():
		var path := "res://assets/models/vehicles/catalog.json"
		if FileAccess.file_exists(path):
			var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
			if data is Array:
				_catalog = data
			elif data is Dictionary:
				_catalog = (data as Dictionary).get("vehicles", [])
	var options: Array = []
	for want: Variant in [VARIANT_CATALOG.get(variant, []), CATALOG_KINDS[kind]]:
		for e: Variant in _catalog:
			if e is Dictionary and str((e as Dictionary).get("kind", "")) in (want as Array) \
					and ResourceLoader.exists(str((e as Dictionary).get("file", ""))):
				options.append(e)
		if not options.is_empty():
			break
	if options.is_empty():
		return {}
	return options[_rng.randi() % options.size()]


## Real vehicle GLB: wheel nodes/radii from the catalog and a seated human rider.
func _setup_glb(entry: Dictionary) -> void:
	var model := visual.get(&"model") as Node3D
	# the GLB's own static colliders would be teleported every frame; this body's box replaces them
	for co: Node in model.find_children("*", "CollisionObject3D", true, false):
		co.get_parent().remove_child(co)
		co.queue_free()
	_collect_lamp_materials(model)
	var wheels: Array = []
	for w: Variant in entry.get("wheels", []):
		var wd := w as Dictionary
		var n := model.find_child(str(wd.get("node", "")), true, false) as Node3D
		if n != null:
			n.set_meta(&"radius", float(wd.get("radius", 0.3)))
			wheels.append(n)
	if not wheels.is_empty():
		visual.set(&"_glb_wheels", wheels)
		visual.set(&"_glb_wheels_scanned", true)
	if kind == &"car":
		return
	var seats: Dictionary = entry.get("seats", {})
	var seat_arr: Variant = seats.get("rider", entry.get("seat", null))
	if not seat_arr is Array or (seat_arr as Array).size() < 3:
		return
	var seat := Vector3(float(seat_arr[0]), float(seat_arr[1]), float(seat_arr[2]))
	_add_glb_rider("Rider", seat, &"cycle" if kind == &"bicycle" else &"ride")
	var pil: Variant = seats.get("pillion", seats.get("passenger", null))
	if pil is Array and _rng.randf() < (0.6 if seats.has("passenger") else 0.3):
		_add_glb_rider("Passenger", Vector3(float(pil[0]), float(pil[1]), float(pil[2])), &"passenger")


## Lamp surfaces (meta `vehicle_lights`, materials veh_light_head/tail): unique copies whose
## emission is raised at night (vehicles-nature hand-off).
func _collect_lamp_materials(model: Node3D) -> void:
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.get_active_material(i) as BaseMaterial3D
			if m == null:
				continue
			var nm := m.resource_name.to_lower()
			var head := "light_head" in nm
			var tail := "light_tail" in nm
			if not (head or tail) and not (mi.has_meta(&"vehicle_lights") and m.emission_enabled):
				continue
			var dup := m.duplicate() as BaseMaterial3D
			dup.emission_enabled = true
			mi.set_surface_override_material(i, dup)
			_lamp_mats.append([dup, 5.0 if head else 2.5])


func _set_lamps(on: bool) -> void:
	if on == _lamps_on:
		return
	_lamps_on = on
	for e: Array in _lamp_mats:
		(e[0] as BaseMaterial3D).emission_energy_multiplier = float(e[1]) if on else 0.0


func _add_glb_rider(n: String, seat: Vector3, pose: StringName) -> void:
	var r := NpcVisualScript.new()
	r.name = n
	visual.add_child(r)
	r.call(&"setup", "human", {"model_names": ["ped_xeom", "ped_helmet_woman", "ped_student", "ped_office", "ped_"],
		"seed": _rng.randi(), "hat": "helmet", "long_sleeves": true})
	if bool(r.get(&"is_standin")):
		var m := r.get(&"model") as Node3D
		r.position = Vector3(seat.x, seat.y - float(m.get_meta(&"leg_len", 0.78)) - 0.03, seat.z)
		var pa := ProcAnim.new()
		pa.setup(m)
		pa.play(pose)
		_riders.append(pa)
	else:
		# creatures' `sit` clip: pelvis 0.34 m above the origin
		r.position = seat - Vector3(0, 0.34, 0)
		r.call(&"play", &"sit")


func place_on_lane(p_lane: Path3D, p_offset: float, p_speed: float) -> void:
	lane = p_lane
	lane_length = maxf(lane.curve.get_baked_length(), 0.1)
	var c := lane.curve
	lane_closed = c.point_count > 2 and c.get_point_position(0).distance_to(c.get_point_position(c.point_count - 1)) < 0.6
	offset = p_offset
	var limit := float(NpcUtil.meta_or(lane, &"speed_limit", 8.0))
	v0 = minf(float(_spec["v0"]), limit) * _personal
	speed = clampf(p_speed, 0.0, v0)
	_apply_transform(0.0, true)
	reset_physics_interpolation()


func lane_point(o: float) -> Vector3:
	var c := lane.curve
	var oo := fposmod(o, lane_length) if lane_closed else clampf(o, 0.0, lane_length)
	return lane.to_global(c.sample_baked(oo, true))


func _apply_transform(dt: float, snap: bool) -> void:
	var p := lane_point(offset)
	var ahead := lane_point(offset + 1.2)
	if not lane_closed and offset + 1.2 > lane_length:
		var back := lane_point(offset - 1.2)
		ahead = p + (p - back)
	var dir := ahead - p
	if dir.length_squared() < 1e-5:
		dir = global_basis.z
	var flat_dir := NpcUtil.flat(dir).normalized()
	var yaw := NpcUtil.yaw_of(flat_dir)
	var pitch := -atan2(dir.y, NpcUtil.flat(dir).length())
	if not snap and dt > 0.0:
		var yaw_rate := wrapf(yaw - _prev_yaw, -PI, PI) / dt
		if kind != &"car":
			var target_lean := clampf(-speed * yaw_rate / 9.8, -0.45, 0.45)
			_lean = lerpf(_lean, target_lean, 1.0 - exp(-6.0 * dt))
	_prev_yaw = yaw
	var b := Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, pitch) * Basis(Vector3.BACK, _lean)
	global_transform = Transform3D(b, p)


func _physics_process(delta: float) -> void:
	if not active or lane == null:
		return
	_honk_cd = maxf(_honk_cd - delta, 0.0)
	_hit_cd = maxf(_hit_cd - delta, 0.0)
	# --- car following (IDM) -------------------------------------------------------------
	var gap := INF
	var dv := 0.0
	leader = null
	if director != null and director.has_method(&"lane_leader"):
		var info: Array = director.call(&"lane_leader", self)
		if info.size() == 2 and info[0] != null:
			leader = info[0] as Node3D
			gap = float(info[1])
			dv = speed - float(leader.get(&"speed"))
	var obs := _corridor_obstacle()
	obstacle_gap = float(obs["gap"])
	blocked_by_cat = bool(obs["cat"]) and obstacle_gap < 12.0
	if obstacle_gap < gap:
		gap = obstacle_gap
		dv = speed
	var a := float(_spec["a"])
	var b := float(_spec["b"])
	var s0 := float(_spec["s0"])
	var T := float(_spec["T"])
	var s_star := s0 + speed * T + speed * dv / (2.0 * sqrt(a * b))
	var acc := a * (1.0 - pow(speed / maxf(v0, 0.1), 4.0))
	if gap < INF:
		acc -= a * pow(maxf(s_star, 0.0) / maxf(gap, 0.05), 2.0)
	acc = clampf(acc, -9.0, a)
	speed = maxf(speed + acc * delta, 0.0)
	if gap < 0.05 and speed < 1.0:
		speed = 0.0
	var ds := speed * delta
	offset += ds
	if not lane_closed and offset >= lane_length:
		if director != null and director.has_method(&"vehicle_finished"):
			director.call(&"vehicle_finished", self)
			return
		offset = 0.0
	if lane_closed:
		offset = fposmod(offset, lane_length)
	_apply_transform(delta, false)
	# --- reactions --------------------------------------------------------------------------
	if blocked_by_cat:
		_wait_t += delta if speed < 0.3 else 0.0
		if _honk_cd <= 0.0 and (obstacle_gap < 9.0 and speed > 1.0 or _wait_t > 1.2):
			_honk()
	else:
		_wait_t = 0.0
	_check_hit()
	# --- visuals --------------------------------------------------------------------------
	if lod <= Lod.MID and visual != null:
		visual.call(&"spin_wheels", ds)
		var rig: Dictionary = visual.call(&"get_rig")
		var crank := rig.get("Crank") as Node3D
		if crank != null:
			crank.rotate_object_local(Vector3.RIGHT, ds / 0.33 * 0.55)
		for r: Variant in _riders:
			var pa := r as ProcAnim
			pa.speed = speed * 0.35
			pa.tick(delta)
	_update_audio()


func _corridor_obstacle() -> Dictionary:
	var out := {"gap": INF, "cat": false}
	var inv := global_transform.affine_inverse()
	var reach := 6.0 + speed * 1.6
	var p := _player()
	if p != null:
		var l := inv * p.global_position
		if l.z > 0.0 and l.z < reach + length * 0.5 and absf(l.x) < half_width + 0.45 and l.y > -1.0 and l.y < 1.2:
			out["gap"] = maxf(l.z - length * 0.5 - 0.15, 0.0)
			out["cat"] = true
	if director != null and director.has_method(&"get_agents_near") and lod <= Lod.MID:
		var center := global_position + global_basis.z * (length * 0.5 + reach * 0.5)
		for ag: Variant in director.call(&"get_agents_near", center, reach * 0.5 + 1.0):
			var n := ag as Node3D
			if n == null or n == self or n.is_in_group(&"vehicle"):
				continue
			var l2 := inv * n.global_position
			if l2.z > 0.0 and absf(l2.x) < half_width + 0.5 and absf(l2.y) < 1.5:
				var g := maxf(l2.z - length * 0.5 - 0.3, 0.0)
				if g < float(out["gap"]):
					out["gap"] = g
					out["cat"] = false
	return out


func _player() -> Node3D:
	if director != null and director.has_method(&"get_player"):
		return director.call(&"get_player") as Node3D
	return NpcUtil.get_player(self)


func _honk() -> void:
	_honk_cd = _rng.randf_range(2.5, 5.0)
	var snd := &"horn_motorbike"
	if kind == &"car":
		snd = &"horn_car"
	elif kind == &"bicycle":
		snd = &"bicycle_bell"
	NpcUtil.sfx(snd, global_position + Vector3.UP * 0.9, 0.0, 0.08)
	# the horn startles nearby birds
	if director != null and director.has_method(&"startle"):
		director.call(&"startle", global_position, 7.0)


func _check_hit() -> void:
	if _hit_cd > 0.0 or speed < 1.0:
		return
	var p := _player()
	if p == null:
		return
	var l := global_transform.affine_inverse() * p.global_position
	if l.z > length * 0.5 - 0.35 and l.z < length * 0.5 + 0.3 and absf(l.x) < half_width + 0.12 and l.y > -0.3 and l.y < 0.9:
		_hit_cd = 2.0
		var fwd := global_basis.z.normalized()
		var side := global_basis.x.normalized() * (1.0 if l.x >= 0.0 else -1.0)
		var dmg := 3.0 + speed * 1.2 * (1.6 if kind == &"car" else 1.0)
		NpcUtil.hurt_player(p, dmg, &"vehicle", fwd * speed * 0.8 + side * 1.8 + Vector3.UP * 2.6)
		NpcUtil.sfx(&"impact_plastic", p.global_position, -4.0)
		speed *= 0.3
		_honk()


func _update_audio() -> void:
	var want := lod == Lod.NEAR and kind != &"bicycle"
	if want and _loop == null:
		_loop = NpcUtil.loop(&"scooter_ride_loop" if kind == &"motorbike" else &"motorbike_ride_loop", self,
			-6.0 if kind == &"motorbike" else -9.0, 1.0, true)
	elif not want and _loop != null:
		NpcUtil.stop_loop(_loop, 0.4)
		_loop = null
	if _loop != null and is_instance_valid(_loop):
		_loop.pitch_scale = clampf(0.75 + speed / 14.0, 0.7, 1.5)
		_loop.volume_db = -14.0 + clampf(speed / v0, 0.0, 1.0) * 8.0
	# headlight at night for close vehicles
	_set_lamps(NpcUtil.night_factor() > 0.4 and lod <= Lod.MID)
	var night := NpcUtil.night_factor() > 0.5 and lod == Lod.NEAR
	if night and _light == null:
		_light = SpotLight3D.new()
		_light.spot_range = 14.0
		_light.spot_angle = 32.0
		_light.light_energy = 2.5 if kind == &"car" else 1.4
		_light.light_color = Color(1.0, 0.94, 0.82)
		_light.shadow_enabled = false
		_light.position = Vector3(0, 0.95 if kind != &"car" else 0.75, length * 0.5)
		_light.rotation = Vector3(-0.12, PI, 0)
		add_child(_light)
	elif _light != null:
		_light.visible = night


func set_lod(l: int, _interval: float) -> void:
	@warning_ignore("int_as_enum_without_cast")
	lod = l
	visible = l != Lod.ASLEEP
	if l == Lod.ASLEEP:
		NpcUtil.stop_loop(_loop, 0.2)
		_loop = null


func set_active(on: bool) -> void:
	active = on
	visible = on
	set_physics_process(on)
	collision_layer = NpcUtil.LAYER_VEHICLES if on else 0
	if not on:
		NpcUtil.stop_loop(_loop, 0.2)
		_loop = null
		if director != null and director.has_method(&"lane_remove"):
			director.call(&"lane_remove", self)
