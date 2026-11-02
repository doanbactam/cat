extends "res://tests/test_base.gd"
## Foot-contact quality of the exported locomotion clips (owner: cat-asset).
## Evaluates the imported tracks exactly as Godot interpolates them (240 samples per clip):
## * the ball of each paw (finger_* head for the forelegs, toe_* head for the hind legs) is "in
##   stance" while within 4 mm of its lowest height; stance slip = |forward speed + gait speed|
##   (clips are in place, a planted paw must move backwards at exactly the gait speed);
## * the skinned paw vertices (CPU skinning of the real mesh) never go below the ground.
## Prints a table (also used for docs/areas/cat-asset.md).  Requires the import option
## animation/fps = 120 (blender/cat/configure_import.py): Godot re-bakes glTF tracks at that rate.

const CAT_PATH := "res://assets/models/cat/cat.glb"
const GAITS := {"walk": 0.7, "trot": 1.6, "run": 4.5, "sneak": 0.45, "balance_walk": 0.4}
const BALLS: Array[String] = ["finger_L", "finger_R", "toe_L", "toe_R"]
const SAMPLES := 240
## max allowed mean stance slip (m/s) and duty range per gait
const LIMITS := {
	"walk": [0.05, 0.50, 0.75], "trot": [0.06, 0.40, 0.60], "run": [0.16, 0.22, 0.45],
	"sneak": [0.05, 0.60, 0.85], "balance_walk": [0.05, 0.55, 0.80],
}

var _cat: Node3D
var _sk: Skeleton3D
var _anim: Animation
var _tracks := {}


func before_each() -> void:
	var ps := load(CAT_PATH) as PackedScene
	if ps != null:
		_cat = ps.instantiate() as Node3D
		_sk = _cat.get_node_or_null("CatRig/Skeleton3D") as Skeleton3D


func after_each() -> void:
	if is_instance_valid(_cat):
		_cat.free()


func _player() -> AnimationPlayer:
	var found := _cat.find_children("*", "AnimationPlayer", true, false)
	return found[0] as AnimationPlayer if found.size() > 0 else null


func _index_tracks() -> void:
	_tracks.clear()
	for ti in _anim.get_track_count():
		var p := str(_anim.track_get_path(ti))
		var bn := p.substr(p.rfind(":") + 1)
		if not _tracks.has(bn):
			_tracks[bn] = {}
		_tracks[bn][_anim.track_get_type(ti)] = ti


func _local(bi: int, t: float) -> Transform3D:
	var rest := _sk.get_bone_rest(bi)
	var pos := rest.origin
	var rot := rest.basis.get_rotation_quaternion()
	var scl := rest.basis.get_scale()
	var tr: Dictionary = _tracks.get(_sk.get_bone_name(bi), {})
	if tr.has(Animation.TYPE_POSITION_3D):
		pos = _anim.position_track_interpolate(tr[Animation.TYPE_POSITION_3D], t)
	if tr.has(Animation.TYPE_ROTATION_3D):
		rot = _anim.rotation_track_interpolate(tr[Animation.TYPE_ROTATION_3D], t)
	if tr.has(Animation.TYPE_SCALE_3D):
		scl = _anim.scale_track_interpolate(tr[Animation.TYPE_SCALE_3D], t)
	return Transform3D(Basis(rot).scaled(scl), pos)


func _poses(t: float) -> Array[Transform3D]:
	var out: Array[Transform3D] = []
	out.resize(_sk.get_bone_count())
	for bi in _sk.get_bone_count():   # glTF skeletons list parents before children
		var p := _sk.get_bone_parent(bi)
		out[bi] = _local(bi, t) if p < 0 else out[p] * _local(bi, t)
	return out


func _paw_vertices(body: MeshInstance3D) -> Dictionary:
	var arr := body.mesh.surface_get_arrays(0)
	var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var bones: PackedInt32Array = arr[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
	var stride := bones.size() / verts.size()
	var idx := PackedInt32Array()
	for i in verts.size():
		if verts[i].y < 0.025:
			idx.append(i)
	return {"v": verts, "b": bones, "w": weights, "s": stride, "idx": idx}


func test_gait_contacts() -> void:
	assert_not_null(_sk, "skeleton")
	if _sk == null:
		return
	var ap := _player()
	var body := _sk.find_child("CatBody", true, false) as MeshInstance3D
	var skin := body.skin
	var bind_bone := PackedInt32Array()
	var bind_pose: Array[Transform3D] = []
	for i in skin.get_bind_count():
		var bb := skin.get_bind_bone(i)
		if bb < 0:
			bb = _sk.find_bone(skin.get_bind_name(i))
		bind_bone.append(bb)
		bind_pose.append(skin.get_bind_pose(i))
	var paws := _paw_vertices(body)
	var idx: PackedInt32Array = paws["idx"]
	print("  gait          paw   duty  stance-travel  slip mean/max (m/s)  ball min  mesh min")
	for gname: String in GAITS:
		var v: float = GAITS[gname]
		_anim = ap.get_animation(StringName(gname))
		assert_not_null(_anim, gname)
		if _anim == null:
			continue
		_index_tracks()
		var ys := {}
		var zs := {}
		for b in BALLS:
			ys[b] = PackedFloat32Array()
			zs[b] = PackedFloat32Array()
		var mesh_min := 1.0
		for k in SAMPLES + 1:
			var t := _anim.length * k / SAMPLES
			var poses := _poses(t)
			for b in BALLS:
				var o := poses[_sk.find_bone(b)].origin
				ys[b].append(o.y)
				zs[b].append(o.z)
			if k % 4 == 0:
				var skm: Array[Transform3D] = []
				for i in bind_bone.size():
					skm.append(poses[bind_bone[i]] * bind_pose[i])
				var vv: PackedVector3Array = paws["v"]
				var bo: PackedInt32Array = paws["b"]
				var we: PackedFloat32Array = paws["w"]
				var st: int = paws["s"]
				for i in idx:
					var p := Vector3.ZERO
					for j in st:
						var w := we[i * st + j]
						if w > 0.0:
							p += (skm[bo[i * st + j]] * vv[i]) * w
					mesh_min = minf(mesh_min, p.y)
		var dt := _anim.length / SAMPLES
		var lim: Array = LIMITS[gname]
		for b in BALLS:
			var y: PackedFloat32Array = ys[b]
			var z: PackedFloat32Array = zs[b]
			var ymin := 1.0
			for q in y:
				ymin = minf(ymin, q)
			var n_st := 0
			var slip := 0.0
			var slip_max := 0.0
			var n_sl := 0
			var zmin := 1e9
			var zmax := -1e9
			for i in SAMPLES:
				if y[i] < ymin + 0.004:
					n_st += 1
					zmin = minf(zmin, z[i])
					zmax = maxf(zmax, z[i])
					if y[i + 1] < ymin + 0.004:
						var s := absf((z[i + 1] - z[i]) / dt + v)
						slip += s
						slip_max = maxf(slip_max, s)
						n_sl += 1
			var duty := float(n_st) / SAMPLES
			var mean := slip / maxf(1.0, n_sl)
			print("  %-13s %-8s %.2f   %.3f m        %.3f / %.3f        %5.1f mm  %5.1f mm" % [
				gname, b, duty, zmax - zmin, mean, slip_max, ymin * 1000.0, mesh_min * 1000.0])
			assert_true(mean <= lim[0], "%s %s stance slip %.3f m/s (limit %.2f)" % [gname, b, mean, lim[0]])
			assert_true(duty >= lim[1] and duty <= lim[2], "%s %s duty %.2f" % [gname, b, duty])
			assert_true(ymin > 0.0, "%s %s ball above ground" % [gname, b])
		assert_true(mesh_min > -0.0015, "%s paw mesh min %.1f mm (no ground penetration)" % [gname, mesh_min * 1000.0])
