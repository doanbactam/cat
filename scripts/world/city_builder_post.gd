extends RefCounted
## Post-physics stage of the city build (owner: world). Needs the built city inside a SceneTree
## with physics stepped once. Measures rooftops with ray casts, links the rooftop network
## (crate stairs at height steps, planks over alley gaps, walkable cable bundles over streets),
## adds decorative overhead cables from poles, Mun's rooftop patrol, and bakes the NavRegion.
## Verifies jumpability: rules = horizontal gap ≤ 2.0 m and step-up ≤ 1.5 m (or a connector).

const L := preload("res://scripts/world/city_layout.gd")
const CS := preload("res://scripts/world/city_structures.gd")

const MAX_GAP := 2.0
const MAX_STEP := 1.5
const SAMPLE_STEP := 1.0

var b: Object                     # the CityBuilder instance
var space: PhysicsDirectSpaceState3D
var samples: Array = []           # [{p: Vector3, m: int}]
var by_module: Dictionary = {}    # module index -> Array of sample indices
var parent: PackedInt32Array = PackedInt32Array()
var report: Dictionary = {}
var _exclude: Array[RID] = []


func _init(builder: Object, s: PhysicsDirectSpaceState3D) -> void:
	b = builder
	space = s


func run() -> Dictionary:
	_measure_roofs()
	_connect_by_rules()
	var before := _net_coverage()
	_add_crate_stairs()
	_add_planks()
	_add_walkable_cables()
	_add_tower_access()
	_bridge_components()
	var after := _net_coverage()
	_add_decorative_cables()
	_add_mun_patrol()
	report["rows_in_main_network"] = _row_membership()
	report["net_coverage_before"] = before
	report["net_coverage_after"] = after
	return report


# --- measurement ---------------------------------------------------------------------------------

func _ray_down(x: float, z: float, from_y: float = 45.0, to_y: float = 2.0) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, from_y, z), Vector3(x, to_y, z), 1)
	q.collide_with_areas = false
	return space.intersect_ray(q)


func _measure_roofs() -> void:
	var placed: Array = b.get(&"placed")
	for mi in placed.size():
		var m: Dictionary = placed[mi]
		if not bool(m["net"]):
			continue
		var xf: Transform3D = m["xf"]
		var w: float = m["w"]
		var d: float = m["d"]
		var idx: Array = []
		var x := -w * 0.5 + 0.3
		while x <= w * 0.5 - 0.3 + 0.001:
			var z := -0.25
			while z >= -d + 0.4:
				var wp := xf * Vector3(x, 0, z)
				var hit := _ray_down(wp.x, wp.z)
				if not hit.is_empty() and (hit["normal"] as Vector3).y > 0.7 and (hit["position"] as Vector3).y > 3.0:
					samples.append({"p": hit["position"], "m": mi})
					idx.append(samples.size() - 1)
				z -= SAMPLE_STEP
			x += SAMPLE_STEP if w > 3.0 else (w - 0.6)
		by_module[mi] = idx
	parent.resize(samples.size())
	for i in samples.size():
		parent[i] = i
	report["roof_samples"] = samples.size()
	_dump_samples()


func _dump_samples() -> void:
	var placed: Array = b.get(&"placed")
	var mods: Array = []
	for m: Dictionary in placed:
		var xf: Transform3D = m["xf"]
		mods.append({"id": m["id"], "row": m["row"], "w": m["w"], "d": m["d"], "h": m["h"], "net": m["net"],
			"o": [xf.origin.x, xf.origin.z], "ax": [xf.basis.x.x, xf.basis.x.z], "fz": [xf.basis.z.x, xf.basis.z.z]})
	var ss: Array = []
	for smp: Dictionary in samples:
		var p: Vector3 = smp["p"]
		ss.append([snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01), smp["m"]])
	# measured roof deck (median sample height) per module id → used by the next build's row picker
	var per_id: Dictionary = {}
	for smp: Dictionary in samples:
		var id: String = placed[smp["m"]]["id"]
		if not per_id.has(id):
			per_id[id] = []
		(per_id[id] as Array).append((smp["p"] as Vector3).y)
	var decks: Dictionary = {}
	for id: String in per_id:
		var arr: Array = per_id[id]
		arr.sort()
		decks[id] = snappedf(float(arr[arr.size() / 2]), 0.05)
	var df := FileAccess.open("res://scenes/world/module_decks.json", FileAccess.WRITE)
	if df != null:
		df.store_string(JSON.stringify(decks, "  ", true))
	var f := FileAccess.open("res://qa/out/world/roof_samples.json", FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify({"modules": mods, "samples": ss}))


func _find(i: int) -> int:
	while parent[i] != i:
		parent[i] = parent[parent[i]]
		i = parent[i]
	return i


func _union(a: int, c: int) -> void:
	var ra := _find(a)
	var rc := _find(c)
	if ra != rc:
		parent[ra] = rc


func _connect_by_rules() -> void:
	# spatial hash 2 m cells
	var grid: Dictionary = {}
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 2.0), floori(p.z / 2.0))
		if not grid.has(key):
			grid[key] = []
		(grid[key] as Array).append(i)
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 2.0), floori(p.z / 2.0))
		for dx in range(-1, 2):
			for dz in range(-1, 2):
				var k2 := key + Vector2i(dx, dz)
				if not grid.has(k2):
					continue
				for j: int in grid[k2]:
					if j <= i:
						continue
					var q: Vector3 = samples[j]["p"]
					var hd := Vector2(p.x - q.x, p.z - q.z).length()
					var same: bool = samples[i]["m"] == samples[j]["m"]
					var lim := SAMPLE_STEP * 1.5 if same else MAX_GAP
					if hd <= lim and absf(p.y - q.y) <= MAX_STEP:
						_union(i, j)


## Fraction of net modules (with roof samples) that belong to the largest rooftop component.
func _net_coverage() -> float:
	var comp_modules: Dictionary = {}
	for mi: int in by_module:
		var seen: Dictionary = {}
		for si: int in by_module[mi]:
			seen[_find(si)] = true
		for r: int in seen:
			if not comp_modules.has(r):
				comp_modules[r] = {}
			comp_modules[r][mi] = true
	var best := 0
	for r: int in comp_modules:
		best = maxi(best, (comp_modules[r] as Dictionary).size())
	var total := 0
	for mi: int in by_module:
		if not (by_module[mi] as Array).is_empty():
			total += 1
	return float(best) / maxf(1.0, float(total))


func _row_membership() -> Dictionary:
	var placed: Array = b.get(&"placed")
	var count: Dictionary = {}
	for i in samples.size():
		var r := _find(i)
		count[r] = int(count.get(r, 0)) + 1
	var big := -1
	var bn := -1
	for r: int in count:
		if int(count[r]) > bn:
			bn = count[r]
			big = r
	var out: Dictionary = {}
	for mi: int in by_module:
		var row := str(placed[mi]["row"])
		var inbig := false
		for si: int in by_module[mi]:
			if _find(si) == big:
				inbig = true
				break
		if not out.has(row):
			out[row] = [0, 0]
		out[row][1] += 1
		if inbig:
			out[row][0] += 1
	return out


func _module_roots(mi: int) -> Dictionary:
	var out: Dictionary = {}
	for si: int in by_module.get(mi, []):
		out[_find(si)] = true
	return out


# --- connectors --------------------------------------------------------------------------------------

## Links touching modules (any rows) whose roofs differ by more than a jump: crate stairs for
## steps ≤ 4.2 m, a climbable drainpipe (layers 1+6) on the taller wall above that.
func _add_crate_stairs() -> void:
	var rng: RandomNumberGenerator = b.get(&"rng")
	var grid: Dictionary = {}
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 2.0), floori(p.z / 2.0))
		if not grid.has(key):
			grid[key] = []
		(grid[key] as Array).append(i)
	var best: Dictionary = {}       # module pair -> [score, low, high]
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 2.0), floori(p.z / 2.0))
		for dx in range(-1, 2):
			for dz in range(-1, 2):
				for j: int in grid.get(key + Vector2i(dx, dz), []):
					if j <= i or samples[i]["m"] == samples[j]["m"]:
						continue
					var q: Vector3 = samples[j]["p"]
					var hd := Vector2(p.x - q.x, p.z - q.z).length()
					var dy := absf(p.y - q.y)
					if hd > MAX_GAP or dy > 14.0:
						continue
					var mk := Vector2i(mini(samples[i]["m"], samples[j]["m"]), maxi(samples[i]["m"], samples[j]["m"]))
					var score := dy + hd * 0.3
					if not best.has(mk) or score < float(best[mk][0]):
						best[mk] = [score, i if p.y < q.y else j, j if p.y < q.y else i]
	var keys := best.keys()
	keys.sort_custom(func(a: Vector2i, c: Vector2i) -> bool: return float(best[a][0]) < float(best[c][0]))
	var stairs := 0
	var pipes := 0
	for mk: Vector2i in keys:
		var lo_i: int = best[mk][1]
		var hi_i: int = best[mk][2]
		if _find(lo_i) == _find(hi_i):
			continue
		var lo: Vector3 = samples[lo_i]["p"]
		var hi: Vector3 = samples[hi_i]["p"]
		var dy := hi.y - lo.y
		var toward := Vector3(hi.x - lo.x, 0, hi.z - lo.z)
		if toward.length() < 0.05:
			toward = Vector3.FORWARD
		toward = toward.normalized()
		var parent_node := b.call(&"grp", "Connectors") as Node3D
		if dy <= MAX_STEP:
			_union(lo_i, hi_i)
			continue
		if dy <= 4.2:
			var stair := CS.make_crate_stair(dy - 0.4, rng)
			stair.transform = Transform3D(Basis.looking_at(toward, Vector3.UP, true), lo)
			parent_node.add_child(stair)
			stairs += 1
		else:
			var pipe := CS.make_drainpipe(dy + 0.1)
			# against the taller wall, just in front of it
			var at := hi - toward * 0.25
			pipe.transform = Transform3D(Basis.looking_at(-toward, Vector3.UP, true), Vector3(at.x, lo.y, at.z) - toward * 0.25)
			parent_node.add_child(pipe)
			pipes += 1
		_union(lo_i, hi_i)
	report["crate_stairs"] = stairs
	report["climb_pipes"] = pipes


func _add_planks() -> void:
	# candidate pairs: roof samples of different modules, 2.0 < horizontal distance ≤ 4.2, |dy| ≤ 1.0,
	# currently in different components; clear line between them.
	var grid: Dictionary = {}
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 4.0), floori(p.z / 4.0))
		if not grid.has(key):
			grid[key] = []
		(grid[key] as Array).append(i)
	var cands: Array = []
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var key := Vector2i(floori(p.x / 4.0), floori(p.z / 4.0))
		for dx in range(-1, 2):
			for dz in range(-1, 2):
				for j: int in grid.get(key + Vector2i(dx, dz), []):
					if j <= i or samples[i]["m"] == samples[j]["m"]:
						continue
					var q: Vector3 = samples[j]["p"]
					var hd := Vector2(p.x - q.x, p.z - q.z).length()
					if hd > MAX_GAP and hd <= 4.5 and absf(p.y - q.y) <= MAX_STEP:
						cands.append([hd + absf(p.y - q.y) * 0.5, i, j])
	cands.sort_custom(func(a: Array, c: Array) -> bool: return float(a[0]) < float(c[0]))
	var planks := 0
	var used_pairs: Dictionary = {}
	for c: Array in cands:
		var i: int = c[1]
		var j: int = c[2]
		if _find(i) == _find(j):
			continue
		var pair_key := Vector2i(mini(samples[i]["m"], samples[j]["m"]), maxi(samples[i]["m"], samples[j]["m"]))
		if used_pairs.has(pair_key):
			continue
		var p: Vector3 = samples[i]["p"]
		var q: Vector3 = samples[j]["p"]
		var ray := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.35, q + Vector3.UP * 0.35, 1)
		if not space.intersect_ray(ray).is_empty():
			continue
		var plank := CS.make_plank(p + Vector3.UP * 0.03, q + Vector3.UP * 0.03)
		(b.call(&"grp", "Connectors") as Node3D).add_child(plank)
		_union(i, j)
		used_pairs[pair_key] = true
		planks += 1
		if planks >= 60:
			break
	report["planks"] = planks


func _candidate_pairs(rows_a: Array, rows_b: Array, min_d: float, max_d: float, max_dy: float) -> Array:
	var placed: Array = b.get(&"placed")
	var A: Array = []
	var B: Array = []
	for i in samples.size():
		var row := str(placed[samples[i]["m"]]["row"])
		if row in rows_a:
			A.append(i)
		if row in rows_b:
			B.append(i)
	var out: Array = []
	for i: int in A:
		var p: Vector3 = samples[i]["p"]
		for j: int in B:
			var q: Vector3 = samples[j]["p"]
			var hd := Vector2(p.x - q.x, p.z - q.z).length()
			if hd < min_d or hd > max_d or absf(p.y - q.y) > max_dy:
				continue
			out.append([hd + absf(p.y - q.y), i, j])
	out.sort_custom(func(a: Array, c: Array) -> bool: return float(a[0]) < float(c[0]))
	return out


func _cable_between(i: int, j: int, wires: int) -> bool:
	var rng: RandomNumberGenerator = b.get(&"rng")
	var p: Vector3 = samples[i]["p"] + Vector3.UP * 1.1
	var q: Vector3 = samples[j]["p"] + Vector3.UP * 1.1
	var ray := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.35, q + Vector3.UP * 0.35, 1)
	if not space.intersect_ray(ray).is_empty():
		return false
	var cab := CS.make_cable_bundle(p, q, wires, rng, true)
	(b.call(&"grp", "Cables") as Node3D).add_child(cab)
	var WMs: GDScript = load("res://scripts/world/world_materials.gd")
	for e: Vector3 in [p, q]:
		var post := Node3D.new()
		post.name = "CableAnchor"
		var k := CS.Kit.new(post)
		var steel: Material = WMs.call(&"flat", "anchor_steel", Color(0.25, 0.25, 0.25), 0.5, 0.8)
		k.box(steel, Transform3D(Basis(), e - Vector3(0, 0.55, 0)), Vector3(0.07, 1.15, 0.07), 1.0, &"metal")
		k.box(steel, Transform3D(Basis(), e - Vector3(0, 1.1, 0)), Vector3(0.25, 0.04, 0.25), 1.0)
		k.finish("AnchorMesh")
		(b.call(&"grp", "Cables") as Node3D).add_child(post)
	_union(i, j)
	return true


func _add_walkable_cables() -> void:
	var n := 0
	var pairs := [
		[["pho_ho_w"], ["main_south_lake"], 9.0, 24.0, 4.0],
		[["dinh_north_w"], ["dinh_south_w"], 12.0, 24.0, 4.0],
		[["main_south_w"], ["main_north"], 13.0, 24.0, 4.0],
		[["main_south_lake"], ["main_north"], 13.0, 24.0, 4.0],
		[["hem_a_w_n"], ["hem_a_e_n"], 2.5, 9.0, 2.0],
		[["hem_a_w_s"], ["hem_a_e_s"], 2.5, 9.0, 2.0],
		[["hem_b_n"], ["hem_b_s"], 2.5, 9.0, 2.0],
		[["pho_ho_w"], ["dinh_north_w"], 2.5, 12.0, 3.0],
		[["main_south_w"], ["pho_ho_w"], 2.5, 12.0, 3.0],
	]
	for pr: Array in pairs:
		var cands := _candidate_pairs(pr[0], pr[1], pr[2], pr[3], pr[4])
		var ok := false
		var tries := 0
		for c: Array in cands:
			if tries > 60:
				break
			if _find(c[1]) == _find(c[2]) and tries > 0:
				continue
			tries += 1
			if _cable_between(c[1], c[2], 7):
				ok = true
				n += 1
				break
		if not ok:
			(report.get_or_add("cable_misses", []) as Array).append(str(pr[0]) + "→" + str(pr[1]))
	report["walkable_cables"] = n


## Join leftover rooftop islands (≥ 2 modules) to the main network with the shortest clear
## walkable cable (or a plank when short and level).
func _bridge_components() -> void:
	var bridged := 0
	for iter in 20:
		var count: Dictionary = {}
		var mods_of: Dictionary = {}
		for i in samples.size():
			var r := _find(i)
			count[r] = int(count.get(r, 0)) + 1
			if not mods_of.has(r):
				mods_of[r] = {}
			mods_of[r][samples[i]["m"]] = true
		var main := -1
		var mn := -1
		for r: int in count:
			if int(count[r]) > mn:
				mn = count[r]
				main = r
		var islands: Array = []
		for r: int in mods_of:
			if r != main and (mods_of[r] as Dictionary).size() >= 2:
				islands.append(r)
		if islands.is_empty():
			break
		islands.sort_custom(func(a: int, c: int) -> bool: return (mods_of[a] as Dictionary).size() > (mods_of[c] as Dictionary).size())
		var progress := false
		for isl: int in islands:
			var A: Array = []
			var B: Array = []
			for i in samples.size():
				var r := _find(i)
				if r == isl:
					A.append(i)
				elif r == main:
					B.append(i)
			# subsample for speed
			var cands: Array = []
			for ii in range(0, A.size(), 2):
				var i: int = A[ii]
				var p: Vector3 = samples[i]["p"]
				for jj in range(0, B.size(), 2):
					var j: int = B[jj]
					var q: Vector3 = samples[j]["p"]
					var hd := Vector2(p.x - q.x, p.z - q.z).length()
					var dy := absf(p.y - q.y)
					if hd < 1.0 or hd > 26.0 or dy > 4.0:
						continue
					cands.append([hd + dy * 2.0, i, j, hd, dy])
			cands.sort_custom(func(a: Array, c: Array) -> bool: return float(a[0]) < float(c[0]))
			var tries := 0
			for c: Array in cands:
				tries += 1
				if tries > 80:
					break
				var i: int = c[1]
				var j: int = c[2]
				if float(c[3]) <= 4.5 and float(c[4]) <= minf(MAX_STEP, float(c[3]) * 0.55):
					var p: Vector3 = samples[i]["p"]
					var q: Vector3 = samples[j]["p"]
					var ray := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 0.35, q + Vector3.UP * 0.35, 1)
					if space.intersect_ray(ray).is_empty():
						(b.call(&"grp", "Connectors") as Node3D).add_child(CS.make_plank(p + Vector3.UP * 0.03, q + Vector3.UP * 0.03))
						_union(i, j)
						bridged += 1
						progress = true
						break
				if _cable_between(i, j, 6):
					bridged += 1
					progress = true
					break
			if progress:
				break
		if not progress:
			break
	report["island_bridges"] = bridged


func _add_tower_access() -> void:
	var tower: Node3D = b.get(&"water_tower")
	if tower == null:
		return
	var cat_y := float(tower.get_meta(&"catwalk_y", 13.6))
	var tp := tower.position + Vector3(0, cat_y + 0.6, 0)
	var best := -1
	var best_d := INF
	for i in samples.size():
		var p: Vector3 = samples[i]["p"]
		var hd := Vector2(p.x - tp.x, p.z - tp.z).length()
		if hd < 6.0 or hd > 20.0 or absf(p.y - cat_y) > 4.0:
			continue
		if hd < best_d:
			best_d = hd
			best = i
	if best < 0:
		report["tower_cable"] = "none"
		return
	var p: Vector3 = samples[best]["p"]
	var dir := Vector3(tp.x - p.x, 0, tp.z - p.z).normalized()
	var end := Vector3(tower.position.x, cat_y + 0.05, tower.position.z) - dir * 3.6
	var rng: RandomNumberGenerator = b.get(&"rng")
	var cab := CS.make_cable_bundle(p + Vector3.UP * 0.6, end + Vector3.UP * 0.65, 6, rng, true)
	(b.call(&"grp", "Cables") as Node3D).add_child(cab)
	report["tower_cable"] = "%.1f m" % best_d


## Decorative pole-to-pole bundles + pole-to-facade drops (not walkable).
func _add_decorative_cables() -> void:
	var rng: RandomNumberGenerator = b.get(&"rng")
	var poles: Array = b.get(&"poles")
	var n := 0
	var by_street: Dictionary = {}
	for pe: Array in poles:
		if not by_street.has(pe[1]):
			by_street[pe[1]] = []
		(by_street[pe[1]] as Array).append(pe[0])
	for sid: String in by_street:
		var arr: Array = by_street[sid]
		for i in arr.size() - 1:
			var a: Node3D = arr[i]
			var c: Node3D = arr[i + 1]
			for side in ["ATTACH_BUNDLE_L", "ATTACH_BUNDLE_R"]:
				var na := a.get_node_or_null(side) as Node3D
				var nc := c.get_node_or_null(side) as Node3D
				var pa: Vector3 = (a.transform * na.position) if na != null else a.position + Vector3(0, 7.2, 0)
				var pc: Vector3 = (c.transform * nc.position) if nc != null else c.position + Vector3(0, 7.2, 0)
				var cab := CS.make_cable_bundle(pa, pc, rng.randi_range(5, 9), rng, false)
				(b.call(&"grp", "Cables") as Node3D).add_child(cab)
				n += 1
			# drop lines from the pole to the nearest facades (2–3 per pole)
			for k in rng.randi_range(2, 3):
				var line := a.get_node_or_null("ATTACH_LINE_%02d" % rng.randi_range(0, 7)) as Node3D
				var from: Vector3 = (a.transform * line.position) if line != null else a.position + Vector3(0, 6.8, 0)
				var dir := Vector3(rng.randf_range(-1, 1), 0, rng.randf_range(-1, 1)).normalized()
				var q := PhysicsRayQueryParameters3D.create(from, from + dir * 14.0 + Vector3(0, -1.5, 0), 1)
				var hit := space.intersect_ray(q)
				if hit.is_empty():
					continue
				var cab := CS.make_cable_bundle(from, hit["position"] + (hit["normal"] as Vector3) * 0.05, rng.randi_range(1, 3), rng, false)
				(b.call(&"grp", "Cables") as Node3D).add_child(cab)
				n += 1
	# across-street spans between facades at 6–8 m (the typical tangle over Phố Hàng Mây)
	for s: Array in L.STREETS:
		if s[1] != "x":
			continue
		var c: float = s[2]
		var x := -110.0
		while x < 110.0:
			var y := rng.randf_range(5.5, 8.0)
			var half := float(s[5]) * 0.5 + float(s[6]) + 1.0
			var h1 := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, y, c), Vector3(x, y, c - half), 1))
			var h2 := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(x, y, c), Vector3(x + rng.randf_range(-3, 3), y + rng.randf_range(-0.8, 0.8), c + half), 1))
			if not h1.is_empty() and not h2.is_empty():
				var cab := CS.make_cable_bundle(h1["position"], h2["position"], rng.randi_range(2, 6), rng, false)
				(b.call(&"grp", "Cables") as Node3D).add_child(cab)
				n += 1
			x += rng.randf_range(6.0, 14.0)
	report["decorative_cable_spans"] = n


func _add_mun_patrol() -> void:
	var placed: Array = b.get(&"placed")
	var pts: Array = []
	var spawn: Vector3 = b.get(&"cam_nap_pos")
	for i in samples.size():
		var mi: int = samples[i]["m"]
		if str(placed[mi]["row"]) != "main_south_w":
			continue
		if _find(i) != _find(_nearest_sample(spawn)):
			continue
		pts.append(samples[i]["p"])
	pts.sort_custom(func(a: Vector3, c: Vector3) -> bool: return a.x < c.x)
	var path := Path3D.new()
	path.name = "Patrol_mun"
	path.add_to_group(&"patrol_path")
	path.set_meta(&"npc_id", "mun")
	var curve := Curve3D.new()
	var step := maxi(1, pts.size() / 10)
	for k in range(0, pts.size(), step):
		curve.add_point(pts[k] + Vector3.UP * 0.05)
	path.curve = curve
	(b.call(&"grp", "Markers") as Node3D).add_child(path)
	report["mun_patrol_points"] = curve.point_count


func _nearest_sample(p: Vector3) -> int:
	var best := 0
	var bd := INF
	for i in samples.size():
		var d := (samples[i]["p"] as Vector3).distance_squared_to(p)
		if d < bd:
			bd = d
			best = i
	return best


# --- navigation -------------------------------------------------------------------------------------

static func bake_nav(root: Node3D) -> NavigationRegion3D:
	var region := NavigationRegion3D.new()
	region.name = "NavRegion"
	region.add_to_group(&"nav_region")
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = 1
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_ROOT_NODE_CHILDREN
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.agent_radius = 0.35
	nm.agent_height = 1.6
	nm.agent_max_climb = 0.25
	nm.agent_max_slope = 40.0
	nm.region_min_size = 4.0
	nm.filter_baking_aabb = AABB(Vector3(-124.0, -0.45, -102.0), Vector3(248.0, 3.0, 204.0))
	var src := NavigationMeshSourceGeometryData3D.new()
	NavigationServer3D.parse_source_geometry_data(nm, src, root)
	NavigationServer3D.bake_from_source_geometry_data(nm, src)
	region.navigation_mesh = nm
	return region
