extends Node3D
## LifeDirector (owner: world-life) — scenes/npc/life_director.tscn. Drop it into any world that
## follows the CLAUDE.md marker conventions and it spawns and runs the whole neighbourhood:
##
##   Marker3D "npc_spawn" (meta npc_kind / npc_id)  → pedestrians (ambient spawn/exit points),
##       named humans ba_tu / co_hoa / chu_sau / bin, Vện (dog), Mun / Bông / Ông Mướp + strays
##       (cat), Lão Quạ + crows (crow), pigeon flocks incl. Xám (pigeon_flock), mice (mouse),
##       koi (koi), sparrows on wires (sparrows — extension).
##   Path3D "traffic_lane" (meta vehicle_kinds, speed_limit) → pooled motorbikes/bicycles/cars.
##   Path3D "patrol_path" (meta npc_id)                     → Vện's route, Bin's roaming points.
##   Marker3D "pedestrian_poi" (meta activity sit|shop|chat|wait|look, optional capacity).
##   NavigationRegion3D "NavRegion" (group nav_region) → NavigationAgent3D pathing + avoidance.
##   Area3D "shelter" → where umbrella-less pedestrians wait out the rain.
## Plus a night-time gecko colony around Cam.
##
## Performance: AI level-of-detail by distance to the active camera and frustum (NEAR = every
## physics frame, MID ≈ 8 Hz, FAR ≈ 2 Hz cheap kinematics, ASLEEP = not processed/hidden), pooled
## pedestrians/vehicles (never freed, recycled), max counts per Settings graphics/quality, and a
## time-of-day population curve (busy mornings/evenings, near-empty streets after midnight).

const NpcUtil := preload("res://scripts/npc/npc_util.gd")
const PedestrianScript := preload("res://scripts/npc/pedestrian.gd")
const DogScript := preload("res://scripts/npc/dog.gd")
const NpcCatScript := preload("res://scripts/npc/npc_cat.gd")
const MouseScript := preload("res://scripts/npc/mouse.gd")
const VehicleScript := preload("res://scripts/npc/vehicle.gd")
const FlockScript := preload("res://scripts/npc/pigeon_flock.gd")
const CrowScript := preload("res://scripts/npc/crow.gd")
const SparrowScript := preload("res://scripts/npc/sparrow_wire.gd")
const KoiScript := preload("res://scripts/npc/koi_school.gd")
const GeckoScript := preload("res://scripts/npc/gecko_colony.gd")

const NAMED_HUMANS: Array[StringName] = [&"ba_tu", &"co_hoa", &"chu_sau", &"bin"]
const NAMED_CATS: Array[StringName] = [&"mun", &"bong", &"muop"]
## Fraction of the pedestrian cap wanted per hour (0..23).
const POPULATION_CURVE: Array[float] = [0.08, 0.05, 0.04, 0.04, 0.1, 0.35, 0.75, 1.0, 0.95, 0.8, 0.7, 0.75,
	0.8, 0.6, 0.6, 0.7, 0.85, 1.0, 1.0, 0.95, 0.85, 0.6, 0.35, 0.15]
const TRAFFIC_CURVE: Array[float] = [0.15, 0.08, 0.06, 0.06, 0.15, 0.45, 0.9, 1.0, 1.0, 0.8, 0.7, 0.75,
	0.8, 0.7, 0.7, 0.8, 0.95, 1.0, 1.0, 0.9, 0.75, 0.55, 0.4, 0.25]

@export var auto_start := true
@export var spawn_pedestrians := true
@export var spawn_traffic := true
@export var spawn_animals := true
@export var spawn_geckos := true
## Pedestrians spawn within / despawn beyond these distances from the reference point.
@export var spawn_radius := 55.0
@export var despawn_radius := 85.0
@export var lod_near := 18.0
@export var lod_mid := 40.0
@export var lod_far := 95.0
## When true (tests), ignore the time-of-day population curve.
@export var ignore_time_curves := false

var player: Node3D = null
var started := false
var pedestrians: Array[Node] = []       # active ambient pedestrians
var ped_pool: Array[Node] = []
var named: Dictionary = {}              # npc_id -> node
var agents: Array[Node] = []            # every CharacterBody agent (named + ambient + dog + cats + mice)
var vehicles: Array[Node] = []
var vehicle_pool: Array[Node] = []
var lanes: Array[Path3D] = []
var lane_members: Dictionary = {}       # Path3D -> Array[Node]
var flocks: Array[Node] = []
var crows: Array[Node] = []
var sparrow_wires: Array[Node] = []
var koi_schools: Array[Node] = []
var mice: Array[Node] = []
var geckos: Node = null
var pois: Array[Dictionary] = []        # {node, activity, capacity, occupants: Array}
var ped_spawns: Array[Node3D] = []
var shelters: Array[Area3D] = []
var patrol_paths: Dictionary = {}       # npc_id -> Path3D

var _rng := RandomNumberGenerator.new()
var _lod_t := 0.0
var _pop_t := 0.0
var _presence_t := 0.0
var _lod_cursor := 0
var _caps: Dictionary = {}
var _ped_serial := 0
var _veh_serial := 0


func _ready() -> void:
	_rng.randomize()
	add_to_group(&"life_director")
	var ge := get_node_or_null(^"/root/GameEvents")
	if ge != null:
		ge.player_landed.connect(_on_player_landed)
		ge.player_noise.connect(_on_player_noise)
		ge.settings_changed.connect(_on_settings_changed)
		ge.player_spawned.connect(_on_player_spawned)
	_read_caps()
	if auto_start:
		_start_deferred.call_deferred()


func _on_player_spawned(p: Node3D) -> void:
	player = p


func _start_deferred() -> void:
	# wait one physics frame so the navigation map and colliders exist
	await get_tree().physics_frame
	await get_tree().physics_frame
	start()


## Scans the world for markers and spawns everything. Safe to call once.
func start() -> void:
	if started or not is_inside_tree():
		return
	started = true
	player = get_player()
	_scan_markers()
	if spawn_animals:
		_spawn_named_and_animals()
	if spawn_traffic:
		_init_traffic()
	if spawn_pedestrians:
		_populate_pedestrians(true)
	if spawn_geckos:
		geckos = GeckoScript.new()
		geckos.set(&"director", self)
		add_child(geckos)
		geckos.call(&"setup", int(_caps.get("geckos", 6)))
	_update_lod(true)


func _read_caps() -> void:
	for k: String in ["pedestrians", "vehicles", "pigeons", "strays", "mice", "koi", "geckos", "sparrows"]:
		_caps[k] = NpcUtil.cap(k)


func _on_settings_changed(section: StringName) -> void:
	if section == &"graphics":
		_read_caps()


# ------------------------------------------------------------------------------------------
# Markers
# ------------------------------------------------------------------------------------------

func _in_my_world(n: Node) -> bool:
	return n is Node3D and (n as Node3D).is_inside_tree() and (n as Node3D).get_world_3d() == get_world_3d()


func _scan_markers() -> void:
	var tree := get_tree()
	for n: Node in NpcUtil.nodes_in(tree, &"pedestrian_poi"):
		if _in_my_world(n):
			var act := StringName(str(NpcUtil.meta_or(n, &"activity", "look")))
			var cap_default := 2 if act in [&"chat", &"shop", &"wait", &"look"] else 1
			pois.append({"node": n, "activity": act, "capacity": int(NpcUtil.meta_or(n, &"capacity", cap_default)), "occupants": []})
	for n: Node in NpcUtil.nodes_in(tree, &"traffic_lane"):
		if n is Path3D and _in_my_world(n) and (n as Path3D).curve != null and (n as Path3D).curve.point_count >= 2:
			lanes.append(n)
			lane_members[n] = []
	for n: Node in NpcUtil.nodes_in(tree, &"patrol_path"):
		if n is Path3D and _in_my_world(n):
			patrol_paths[StringName(str(NpcUtil.meta_or(n, &"npc_id", "")))] = n
	for n: Node in NpcUtil.nodes_in(tree, &"shelter"):
		if n is Area3D and _in_my_world(n):
			shelters.append(n)
	for n: Node in NpcUtil.nodes_in(tree, &"npc_spawn"):
		if not _in_my_world(n):
			continue
		var kind := str(NpcUtil.meta_or(n, &"npc_kind", "pedestrian"))
		var id := str(NpcUtil.meta_or(n, &"npc_id", ""))
		if kind == "pedestrian" and id == "":
			ped_spawns.append(n)


func _spawn_named_and_animals() -> void:
	var stray_markers: Array[Node3D] = []
	var cat_homes: Array[Vector3] = []
	for n: Node in NpcUtil.nodes_in(get_tree(), &"npc_spawn"):
		if not _in_my_world(n):
			continue
		var m := n as Node3D
		var kind := str(NpcUtil.meta_or(m, &"npc_kind", "pedestrian"))
		var id := StringName(str(NpcUtil.meta_or(m, &"npc_id", "")))
		if m.has_meta(&"npc_alias"):
			id = StringName(str(m.get_meta(&"npc_alias")))
		if id == &"ong_muop":
			id = &"muop"
		match kind:
			"pedestrian", "vendor":
				if id in NAMED_HUMANS and not named.has(id):
					var p := _new_pedestrian(id)
					p.call(&"init_from_marker", m)
					if id == &"bin" and patrol_paths.has(id):
						p.set(&"roam_path", patrol_paths[id])
					named[id] = p
			"dog":
				var dog_id := id if id != &"" else &"ven"
				if not named.has(dog_id):
					var d := DogScript.new()
					d.name = "Ven" if dog_id == &"ven" else String(dog_id)
					d.set(&"npc_id", dog_id)
					d.set(&"director", self)
					add_child(d)
					d.call(&"init_from_marker", m, patrol_paths.get(dog_id, patrol_paths.get(&"", null)))
					named[dog_id] = d
					agents.append(d)
			"cat":
				cat_homes.append(m.global_position)
				if id in NAMED_CATS:
					if not named.has(id):
						named[id] = _new_cat(id, m)
						if patrol_paths.has(id):
							named[id].call(&"set_route", patrol_paths[id])
				else:
					stray_markers.append(m)
			"crow":
				var c := CrowScript.new()
				c.set(&"director", self)
				add_child(c)
				c.call(&"setup", m, id)
				crows.append(c)
				if id != &"":
					named[id] = c
			"pigeon_flock", "pigeon":
				var f := FlockScript.new()
				f.name = "PigeonFlock%d" % flocks.size()
				f.set(&"director", self)
				add_child(f)
				var count := int(NpcUtil.meta_or(m, &"count", 10))
				count = mini(count, int(_caps["pigeons"]))
				f.call(&"setup", m.global_position, maxi(count, 3), {"radius": float(NpcUtil.meta_or(m, &"radius", 3.5)),
					"xam": id == &"xam", "perch_points": NpcUtil.meta_or(m, &"perch_points", [])})
				flocks.append(f)
				if id == &"xam":
					named[&"xam"] = f
			"sparrows", "sparrow":
				var s := SparrowScript.new()
				s.set(&"director", self)
				add_child(s)
				s.call(&"setup", m, mini(int(NpcUtil.meta_or(m, &"count", 7)), int(_caps["sparrows"])))
				sparrow_wires.append(s)
			"mouse":
				if mice.size() < int(_caps["mice"]):
					var mo := MouseScript.new()
					mo.name = "Mouse%d" % mice.size()
					mo.set(&"director", self)
					add_child(mo)
					mo.call(&"init_from_marker", m)
					mice.append(mo)
					agents.append(mo)
			"koi":
				var k := KoiScript.new()
				k.name = "Koi%d" % koi_schools.size()
				k.set(&"director", self)
				add_child(k)
				k.call(&"setup", m, mini(int(NpcUtil.meta_or(m, &"count", 10)), int(_caps["koi"])))
				koi_schools.append(k)
	# ambient strays: markers first, then near the named cats / POIs
	var want := mini(int(_caps["strays"]), 4)
	var made := 0
	for m: Node3D in stray_markers:
		if made >= want:
			break
		_new_cat(&"", m)
		made += 1
	while made < want and (not cat_homes.is_empty() or not pois.is_empty()):
		var base: Vector3 = cat_homes[_rng.randi() % cat_homes.size()] if not cat_homes.is_empty() \
			else (pois[_rng.randi() % pois.size()]["node"] as Node3D).global_position
		var mk := Marker3D.new()
		add_child(mk)
		mk.global_position = NpcUtil.random_nav_point(get_world_3d(), base, 12.0)
		_new_cat(&"", mk)
		mk.queue_free()
		made += 1


func _new_cat(id: StringName, m: Node3D) -> Node:
	var c := NpcCatScript.new()
	c.name = String(id).capitalize() if id != &"" else "Stray%d" % agents.size()
	c.set(&"npc_id", id)
	c.set(&"director", self)
	add_child(c)
	c.call(&"init_from_marker", m)
	agents.append(c)
	return c


func _new_pedestrian(id: StringName = &"") -> Node:
	var p := PedestrianScript.new()
	_ped_serial += 1
	p.name = String(id).capitalize().replace(" ", "") if id != &"" else "Pedestrian%d" % _ped_serial
	p.set(&"npc_id", id)
	p.set(&"director", self)
	add_child(p)
	agents.append(p)
	return p


# ------------------------------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if not started:
		return
	get_player()
	_lod_t -= delta
	if _lod_t <= 0.0:
		_lod_t = 0.25
		_update_lod(false)
	_pop_t -= delta
	if _pop_t <= 0.0:
		_pop_t = 1.0
		if spawn_pedestrians:
			_populate_pedestrians(false)
		if spawn_traffic:
			_maintain_traffic()
	_presence_t -= delta
	if _presence_t <= 0.0:
		_presence_t = 2.0
		for id: StringName in NAMED_HUMANS:
			var n: Node = named.get(id)
			if n != null and is_instance_valid(n) and n.has_method(&"update_presence"):
				n.call(&"update_presence")


func get_player() -> Node3D:
	if player == null or not is_instance_valid(player) or player.is_queued_for_deletion() or not player.is_inside_tree():
		player = null
		for n: Node in get_tree().get_nodes_in_group(&"player"):
			if n is Node3D and not n.is_queued_for_deletion() and _in_my_world(n):
				player = n
				break
	return player


func reference_point() -> Vector3:
	var cam := get_viewport().get_camera_3d() if is_inside_tree() else null
	if get_player() != null:
		return player.global_position
	if cam != null:
		return cam.global_position
	return global_position


func _update_lod(all: bool) -> void:
	var ref := reference_point()
	var cam := get_viewport().get_camera_3d()
	var everything: Array[Node] = []
	everything.append_array(agents)
	everything.append_array(vehicles)
	everything.append_array(flocks)
	everything.append_array(crows)
	everything.append_array(sparrow_wires)
	everything.append_array(koi_schools)
	for n: Node in everything:
		if n == null or not is_instance_valid(n):
			continue
		var n3 := n as Node3D
		var pos := n3.global_position
		if n.has_method(&"wire_point"):
			pos = n.call(&"wire_point", 0.5)
		elif "center" in n:
			pos = n.get(&"center")
		var d := pos.distance_to(ref)
		var in_view := cam == null or cam.is_position_in_frustum(pos) or d < 6.0
		var l := 0
		var interval := 0.0
		if d < lod_near:
			l = 0
		elif d < lod_mid:
			l = 1 if in_view else 2
			interval = 0.12 if in_view else 0.4
		elif d < lod_far:
			l = 2
			interval = 0.5
		else:
			l = 3
			interval = 1.0
		if l == 0:
			interval = 0.0
		if n.has_method(&"set_lod"):
			n.call(&"set_lod", l, interval)
		# Perf: skeletal animation is the single biggest NPC cost (~128 mixers). Only animate what
		# can actually be seen; set_lod above only hides far agents, their mixers kept running.
		var visible_now := l < 3 and (d < 8.0 or _sphere_in_view(cam, pos, 4.0))
		_set_anim_active(n, visible_now)


## Frustum test with a radius (agents/flocks are bodies, not points). Planes point outward.
func _sphere_in_view(cam: Camera3D, pos: Vector3, radius: float) -> bool:
	if cam == null:
		return true
	for pl: Plane in cam.get_frustum():
		if pl.distance_to(pos) > radius:
			return false
	return true


## Enables/disables every AnimationMixer under `n` (cached in meta; refreshed if a model was swapped).
func _set_anim_active(n: Node, on: bool) -> void:
	var mixers: Array = n.get_meta(&"_lod_mixers", [])
	var stale := not n.has_meta(&"_lod_mixers")
	for m: Variant in mixers:
		if not is_instance_valid(m):
			stale = true
			break
	if stale:
		mixers = n.find_children("*", "AnimationMixer", true, false)
		n.set_meta(&"_lod_mixers", mixers)
	for m: Variant in mixers:
		var mx := m as AnimationMixer
		if mx.active != on:
			mx.active = on


func _hour_index() -> int:
	return clampi(int(NpcUtil.hour()), 0, 23)


func target_pedestrians() -> int:
	var cap := int(_caps.get("pedestrians", 16))
	if ignore_time_curves:
		return cap
	var f := POPULATION_CURVE[_hour_index()]
	var rain := NpcUtil.rain_amount()
	f *= 1.0 - 0.45 * rain
	return int(round(float(cap) * f))


func _populate_pedestrians(initial: bool) -> void:
	var ref := reference_point()
	# despawn far ones
	for i in range(pedestrians.size() - 1, -1, -1):
		var p := pedestrians[i] as Node3D
		if p == null or not is_instance_valid(p):
			pedestrians.remove_at(i)
			continue
		if p.global_position.distance_to(ref) > despawn_radius:
			despawn(p)
	var want := target_pedestrians()
	var budget := 6 if initial else 1
	if initial:
		budget = want
	while pedestrians.size() < want and budget > 0:
		budget -= 1
		var sp := _pick_spawn_point(ref, initial)
		if sp == Vector3.INF:
			break
		var p: Node = ped_pool.pop_back() if not ped_pool.is_empty() else _new_pedestrian()
		p.call(&"set_active", true)
		p.call(&"teleport_to", sp, _rng.randf() * TAU)
		p.set(&"home_pos", sp)
		p.call(&"_enter", 0)    # S.IDLE
		pedestrians.append(p)
	# too many (evening → night): send the extras home
	if pedestrians.size() > want + 1:
		var extra := pedestrians.size() - want
		for p: Node in pedestrians:
			if extra <= 0:
				break
			if int(p.get(&"state")) != 8 and p.has_method(&"_go_home"):    # 8 = S.GO_HOME
				p.call(&"_go_home")
				extra -= 1


func _pick_spawn_point(ref: Vector3, initial: bool) -> Vector3:
	var cam := get_viewport().get_camera_3d()
	var candidates: Array[Vector3] = []
	for m: Node3D in ped_spawns:
		candidates.append(m.global_position)
	for pd: Dictionary in pois:
		candidates.append((pd["node"] as Node3D).global_position)
	if candidates.is_empty():
		for i in 6:
			candidates.append(NpcUtil.random_nav_point(get_world_3d(), ref, spawn_radius * 0.8))
	candidates.shuffle()
	for c: Vector3 in candidates:
		var d := c.distance_to(ref)
		if d > spawn_radius:
			continue
		if not initial and cam != null and cam.is_position_in_frustum(c + Vector3.UP) and d < 30.0:
			continue    # don't pop into view
		var jitter := NpcUtil.random_nav_point(get_world_3d(), c, 1.5)
		return jitter
	return candidates[0] if initial and not candidates.is_empty() else Vector3.INF


func despawn(p: Node) -> void:
	if p == null or not is_instance_valid(p):
		return
	var idx := pedestrians.find(p)
	if idx < 0:
		return
	pedestrians.remove_at(idx)
	p.call(&"on_despawn")
	p.call(&"set_active", false)
	ped_pool.append(p)


# ------------------------------------------------------------------------------------------
# POIs / destinations
# ------------------------------------------------------------------------------------------

func claim_poi(activity: StringName, near: Vector3, agent: Node) -> Node3D:
	var best: Dictionary = {}
	var best_score := INF
	for pd: Dictionary in pois:
		if pd["activity"] != activity:
			continue
		var occ: Array = pd["occupants"]
		_clean(occ)
		if occ.size() >= int(pd["capacity"]):
			continue
		var d := (pd["node"] as Node3D).global_position.distance_to(near)
		if d > 60.0:
			continue
		var score := d + _rng.randf() * 15.0 - (8.0 if activity == &"chat" and occ.size() == 1 else 0.0)
		if score < best_score:
			best_score = score
			best = pd
	if best.is_empty():
		return null
	(best["occupants"] as Array).append(agent)
	return best["node"]


func release_poi(node: Node3D, agent: Node) -> void:
	for pd: Dictionary in pois:
		if pd["node"] == node:
			(pd["occupants"] as Array).erase(agent)


func poi_occupants(node: Node3D) -> Array:
	for pd: Dictionary in pois:
		if pd["node"] == node:
			_clean(pd["occupants"])
			return pd["occupants"]
	return []


func poi_slot_offset(node: Node3D, agent: Node) -> Vector3:
	var occ := poi_occupants(node)
	var i := maxi(occ.find(agent), 0)
	var side := node.global_basis.x.normalized()
	return side * (0.55 if i % 2 == 0 else -0.55)


func _clean(arr: Array) -> void:
	for i in range(arr.size() - 1, -1, -1):
		if arr[i] == null or not is_instance_valid(arr[i]) or not bool((arr[i] as Node).get(&"active")):
			arr.remove_at(i)


func random_destination(from: Vector3, radius: float) -> Vector3:
	if not pois.is_empty() and _rng.randf() < 0.5:
		var pd: Dictionary = pois[_rng.randi() % pois.size()]
		var p := (pd["node"] as Node3D).global_position
		if p.distance_to(from) < radius * 2.0:
			return NpcUtil.random_nav_point(get_world_3d(), p + Vector3(_rng.randf_range(-2, 2), 0, _rng.randf_range(-2, 2)), 1.0)
	if not ped_spawns.is_empty() and _rng.randf() < 0.3:
		return ped_spawns[_rng.randi() % ped_spawns.size()].global_position
	return NpcUtil.random_nav_point(get_world_3d(), from, radius)


func exit_point(from: Vector3) -> Vector3:
	var best := Vector3.INF
	var bd := INF
	for m: Node3D in ped_spawns:
		var d := m.global_position.distance_to(from)
		if d < bd and d > 4.0:
			bd = d
			best = m.global_position
	if best == Vector3.INF:
		best = NpcUtil.random_nav_point(get_world_3d(), from + Vector3(_rng.randf_range(-30, 30), 0, _rng.randf_range(-30, 30)), 2.0)
	return best


func find_shelter(from: Vector3) -> Vector3:
	var best := Vector3.INF
	var bd := 40.0
	for a: Area3D in shelters:
		if not is_instance_valid(a):
			continue
		var c := a.global_position
		for cs: Node in a.get_children():
			if cs is CollisionShape3D:
				c = (cs as CollisionShape3D).global_position
				break
		var y := NpcUtil.ground_y(get_world_3d(), c, 0.5, 8.0)
		if not is_nan(y):
			c.y = y
		var d := c.distance_to(from)
		if d < bd:
			bd = d
			best = c
	if best != Vector3.INF:
		best = NpcUtil.random_nav_point(get_world_3d(), best, 0.6)
	return best


func get_agents_near(pos: Vector3, r: float) -> Array:
	var out: Array = []
	var r2 := r * r
	for a: Node in agents:
		if a == null or not is_instance_valid(a) or not bool(a.get(&"active")):
			continue
		if (a as Node3D).global_position.distance_squared_to(pos) < r2:
			out.append(a)
	return out


# ------------------------------------------------------------------------------------------
# Traffic
# ------------------------------------------------------------------------------------------

func _lane_kinds(lane: Path3D) -> PackedStringArray:
	var k: Variant = NpcUtil.meta_or(lane, &"vehicle_kinds", PackedStringArray(["motorbike", "bicycle", "car"]))
	if k is PackedStringArray:
		return k
	if k is Array:
		return PackedStringArray(k)
	return PackedStringArray([str(k)])


## Lane `vehicle_kinds` may name sub-kinds (world uses scooter/cyclo/…): they map to the three
## driving models and pick a matching catalog GLB (variant).
const KIND_ALIASES := {"motorbike": "motorbike", "scooter": "motorbike", "xe_may": "motorbike", "moto": "motorbike",
	"underbone": "motorbike", "bicycle": "bicycle", "cyclo": "bicycle", "tricycle": "bicycle", "cargo_trike": "bicycle",
	"car": "car", "taxi": "car", "van": "car"}
const KIND_WEIGHTS := {"motorbike": 0.5, "scooter": 0.5, "bicycle": 0.08, "cyclo": 0.05, "tricycle": 0.03,
	"car": 0.12, "taxi": 0.06, "van": 0.04}


static func base_kind(k: String) -> StringName:
	return StringName(KIND_ALIASES.get(k, "motorbike"))


func lane_accepts(lane: Path3D, base: StringName) -> bool:
	for k: String in _lane_kinds(lane):
		if base_kind(k) == base:
			return true
	return false


## Returns the raw (sub-)kind picked for a lane, e.g. &"scooter" or &"cyclo".
func _pick_kind(lane: Path3D) -> StringName:
	var kinds := _lane_kinds(lane)
	var total := 0.0
	for k: String in kinds:
		total += float(KIND_WEIGHTS.get(k, 0.1))
	var r := _rng.randf() * total
	for k: String in kinds:
		r -= float(KIND_WEIGHTS.get(k, 0.1))
		if r <= 0.0:
			return StringName(k)
	return StringName(kinds[0]) if not kinds.is_empty() else &"motorbike"


func target_vehicles() -> int:
	var cap := int(_caps.get("vehicles", 12))
	var total_len := 0.0
	for l: Path3D in lanes:
		total_len += l.curve.get_baked_length()
	var by_len := int(total_len / 14.0)
	var f := 1.0 if ignore_time_curves else TRAFFIC_CURVE[_hour_index()]
	return mini(cap, int(round(float(by_len) * f)))


func _init_traffic() -> void:
	if lanes.is_empty():
		return
	var want := target_vehicles()
	# distribute along lanes, spaced
	var tries := want * 4
	while vehicles.size() < want and tries > 0:
		tries -= 1
		var lane: Path3D = lanes[_rng.randi() % lanes.size()]
		var L := lane.curve.get_baked_length()
		var off := _rng.randf_range(0.0, L * 0.9)
		if _lane_clear(lane, off, 7.0):
			_spawn_vehicle(lane, off, _rng.randf_range(2.0, 6.0))


func _lane_clear(lane: Path3D, off: float, gap: float) -> bool:
	for v: Node in lane_members.get(lane, []):
		if absf(float(v.get(&"offset")) - off) < gap:
			return false
	# keep spawns out of Cam's face
	if player != null and is_instance_valid(player):
		var p := lane.to_global(lane.curve.sample_baked(off, true))
		if p.distance_to(player.global_position) < 4.0:
			return false
	return true


func _spawn_vehicle(lane: Path3D, off: float, speed: float) -> Node:
	var variant := _pick_kind(lane)
	var kind := base_kind(String(variant))
	var v: Node = null
	for i in vehicle_pool.size():
		if vehicle_pool[i].get(&"kind") == kind and vehicle_pool[i].get(&"variant") == variant:
			v = vehicle_pool[i]
			vehicle_pool.remove_at(i)
			break
	if v == null:
		v = VehicleScript.new()
		_veh_serial += 1
		v.name = "%s%d" % [String(kind).capitalize(), _veh_serial]
		v.set(&"director", self)
		add_child(v)
		v.call(&"setup", kind, _rng.randi(), variant)
	v.call(&"set_active", true)
	v.call(&"place_on_lane", lane, off, speed)
	vehicles.append(v)
	(lane_members[lane] as Array).append(v)
	return v


func _maintain_traffic() -> void:
	if lanes.is_empty():
		return
	var want := target_vehicles()
	if vehicles.size() < want:
		var lane: Path3D = lanes[_rng.randi() % lanes.size()]
		if _lane_clear(lane, 0.0, 8.0):
			_spawn_vehicle(lane, 0.0, _rng.randf_range(3.0, 6.0))


func vehicle_finished(v: Node) -> void:
	lane_remove(v)
	var want := target_vehicles()
	if vehicles.size() <= want:
		# re-enter on a lane start (any lane accepting this kind)
		var candidates: Array[Path3D] = []
		for l: Path3D in lanes:
			if lane_accepts(l, v.get(&"kind")) and _lane_clear(l, 0.0, 8.0):
				candidates.append(l)
		if not candidates.is_empty():
			var lane: Path3D = candidates[_rng.randi() % candidates.size()]
			v.call(&"place_on_lane", lane, 0.0, float(v.get(&"speed")))
			(lane_members[lane] as Array).append(v)
			return
	v.call(&"set_active", false)
	vehicles.erase(v)
	vehicle_pool.append(v)


func lane_remove(v: Node) -> void:
	for l: Variant in lane_members:
		(lane_members[l] as Array).erase(v)


## Returns [leader_vehicle_or_null, gap_metres] for `v` on its lane.
func lane_leader(v: Node) -> Array:
	var lane: Path3D = v.get(&"lane")
	if lane == null or not lane_members.has(lane):
		return [null, INF]
	var my := float(v.get(&"offset"))
	var L := float(v.get(&"lane_length"))
	var closed := bool(v.get(&"lane_closed"))
	var best: Node = null
	var best_gap := INF
	for o: Node in lane_members[lane]:
		if o == v or not bool(o.get(&"active")):
			continue
		var d := float(o.get(&"offset")) - my
		if closed:
			d = fposmod(d, L)
		if d <= 0.0:
			continue
		var gap := d - (float(v.get(&"length")) + float(o.get(&"length"))) * 0.5
		if gap < best_gap:
			best_gap = gap
			best = o
	return [best, best_gap]


# ------------------------------------------------------------------------------------------
# Events
# ------------------------------------------------------------------------------------------

func _on_player_landed(_impact: float, _surface: StringName) -> void:
	var p := get_player()
	if p == null:
		return
	for f: Node in flocks:
		if (f as Node3D) != null and (f.get(&"center") as Vector3).distance_to(p.global_position) < 8.0:
			f.call(&"check_pounce", p.global_position)
	for m: Node in mice:
		if is_instance_valid(m) and (m as Node3D).global_position.distance_to(p.global_position) < 1.0:
			m.call(&"check_pounce", p.global_position)


func _on_player_noise(pos: Vector3, loud: float) -> void:
	if loud < 0.35:
		return
	for f: Node in flocks:
		if (f.get(&"center") as Vector3).distance_to(pos) < 4.0 + loud * 10.0:
			f.call(&"startle", pos, 6.0)


## Horns / bangs: startle birds around `pos`.
func startle(pos: Vector3, r: float) -> void:
	for f: Node in flocks:
		if (f.get(&"center") as Vector3).distance_to(pos) < r + 4.0:
			f.call(&"startle", pos, r)
	for s: Node in sparrow_wires:
		if ((s.call(&"wire_point", 0.5)) as Vector3).distance_to(pos) < r + 3.0:
			s.call(&"scatter", pos)


func get_named(id: StringName) -> Node:
	return named.get(id)


func get_stats() -> Dictionary:
	return {"pedestrians": pedestrians.size(), "pool": ped_pool.size(), "vehicles": vehicles.size(),
		"vehicle_pool": vehicle_pool.size(), "named": named.keys(), "flocks": flocks.size(), "crows": crows.size(),
		"mice": mice.size(), "koi_schools": koi_schools.size(), "sparrow_wires": sparrow_wires.size(), "agents": agents.size()}
