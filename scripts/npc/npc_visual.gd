extends Node3D
## Visual layer of an NPC (owner: world-life): loads the creatures-area GLB when present
## (AnimationPlayer with the contract clip names), otherwise builds a procedural stand-in rig
## (standin_builder.gd + proc_animator.gd). Both paths share one API:
##   setup(kind, opts) · play(anim) · set_move_speed(mps) · set_head_look(yaw, pitch) · tick(dt)
## Front faces +Z. Animation is advanced from the owner's physics tick (physics interpolation on).

const Builder := preload("res://scripts/npc/standin_builder.gd")
const ProcAnim := preload("res://scripts/npc/proc_animator.gd")
const NpcUtil := preload("res://scripts/npc/npc_util.gd")

const NPC_DIR := "res://assets/models/npc/"
const VEHICLE_DIR := "res://assets/models/vehicles/"

## Authored gait speeds assumed for GLB clips (m/s) — used to scale playback to real speed.
const AUTHORED_SPEED := {
	"human": {"walk": 1.3, "run": 3.2, "carry": 1.3},
	"dog": {"walk": 1.1, "run": 3.6},
	"bird": {"walk": 0.3},
	"mouse": {"run": 1.0},
	"gecko": {"run": 0.6},
}
## Clip fallbacks when a GLB lacks a name.
const FALLBACKS := {
	&"run": [&"walk"], &"trot": [&"walk"], &"ride": [&"sit", &"idle"], &"passenger": [&"sit", &"idle"],
	&"cycle": [&"sit", &"walk"], &"squat": [&"pet_cat", &"idle"], &"pet_cat": [&"idle"], &"sell": [&"talk", &"idle"],
	&"talk": [&"idle"], &"shoo": [&"talk", &"idle"], &"wave": [&"talk", &"idle"], &"sit_idle": [&"sit", &"idle"],
	&"look_down": [&"look_around", &"idle"], &"sleep": [&"idle"], &"bark": [&"idle"], &"sit": [&"idle"],
	&"peck": [&"idle"], &"fly": [&"idle"], &"takeoff": [&"fly", &"idle"], &"land": [&"fly", &"idle"],
	&"glide": [&"fly", &"idle"], &"caw": [&"idle"], &"crawl": [&"walk", &"run", &"idle"], &"swim": [&"idle"],
}
const LOOPING: Array[StringName] = [&"idle", &"walk", &"run", &"sit", &"talk", &"sell", &"pet_cat", &"fly",
	&"peck", &"sleep", &"swim", &"bark"]

var kind := "human"
var model: Node3D = null
var is_standin := true
var anim_player: AnimationPlayer = null
var proc: RefCounted = null
var current_anim: StringName = &""
var move_speed := 0.0
var umbrella: Node3D = null
var _umbrella_on := false


## kind: human | dog | pigeon | crow | sparrow | mouse | gecko | motorbike | bicycle | car
## opts: model_names (Array of candidate GLB base names, first match wins), plus builder opts.
func setup(p_kind: String, opts: Dictionary = {}) -> void:
	kind = p_kind
	var path := _resolve_model(opts.get("model_names", []) as Array)
	if path != "":
		var ps := NpcUtil.scene(path)
		if ps != null:
			model = ps.instantiate() as Node3D
			is_standin = false
	if model == null:
		model = _build_standin(opts)
		is_standin = true
		NpcUtil.warn_once("standin_" + kind, "world-life: using procedural stand-in for '%s' (no GLB yet)" % kind)
	model.name = "Model"
	add_child(model)
	if is_standin:
		proc = ProcAnim.new()
		proc.call(&"setup", model)
	else:
		anim_player = model.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if anim_player != null:
			for a: StringName in LOOPING:
				if anim_player.has_animation(a):
					anim_player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
			anim_player.playback_default_blend_time = 0.25
			anim_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	play(&"idle")


func _resolve_model(names: Array) -> String:
	for n: Variant in names:
		var s := str(n)
		if s.begins_with("res://"):
			if ResourceLoader.exists(s):
				return s
			continue
		for dir: String in [NPC_DIR, VEHICLE_DIR]:
			var p := dir + s + ".glb"
			if ResourceLoader.exists(p):
				return p
	# prefix scan (e.g. "human_" picks any human_*.glb), deterministic per node name
	for n: Variant in names:
		var s := str(n)
		if not s.ends_with("_"):
			continue
		for dir: String in [NPC_DIR, VEHICLE_DIR]:
			var found := _scan_prefix(dir, s)
			if not found.is_empty():
				return found[absi(hash(str(get_parent().name if get_parent() else name))) % found.size()]
	return ""


static var _scan_cache: Dictionary = {}

static func _scan_prefix(dir: String, prefix: String) -> PackedStringArray:
	var key := dir + prefix
	if _scan_cache.has(key):
		return _scan_cache[key]
	var out := PackedStringArray()
	if DirAccess.dir_exists_absolute(dir):
		for f: String in DirAccess.get_files_at(dir):
			var base := f.trim_suffix(".import").trim_suffix(".remap")
			if base.begins_with(prefix) and base.ends_with(".glb") and not out.has(dir + base):
				out.append(dir + base)
	_scan_cache[key] = out
	return out


func _build_standin(opts: Dictionary) -> Node3D:
	match kind:
		"dog":
			return Builder.dog(opts)
		"pigeon", "crow", "sparrow":
			return Builder.bird(kind, opts)
		"mouse":
			return Builder.mouse()
		"gecko":
			return Builder.gecko()
		"motorbike":
			return Builder.motorbike(opts)
		"bicycle":
			return Builder.bicycle(opts)
		"car":
			return Builder.car(opts)
		_:
			return Builder.human(opts)


func get_rig() -> Dictionary:
	if model != null and model.has_meta(&"rig"):
		return model.get_meta(&"rig")
	return {}


func play(a: StringName) -> void:
	if a == current_anim:
		return
	current_anim = a
	if proc != null:
		proc.call(&"play", a)
		return
	if anim_player == null:
		return
	var name_to_play := a
	if not anim_player.has_animation(name_to_play):
		name_to_play = &""
		for alt: StringName in FALLBACKS.get(a, []):
			if anim_player.has_animation(alt):
				name_to_play = alt
				break
	if name_to_play != &"":
		anim_player.play(name_to_play)


func set_move_speed(v: float) -> void:
	move_speed = v
	if proc != null:
		proc.set(&"speed", v)
	elif anim_player != null and anim_player.is_playing():
		var table: Dictionary = AUTHORED_SPEED.get(_anim_family(), {})
		var cur := String(anim_player.current_animation)
		if table.has(cur) and v > 0.05:
			anim_player.speed_scale = clampf(v / float(table[cur]), 0.5, 2.0)
		else:
			anim_player.speed_scale = 1.0


func _anim_family() -> String:
	if kind in ["pigeon", "crow", "sparrow"]:
		return "bird"
	return kind


func set_head_look(yaw: float, pitch := 0.0) -> void:
	if proc != null:
		proc.set(&"head_yaw", clampf(yaw, -1.2, 1.2))
		proc.set(&"head_pitch", clampf(pitch, -0.5, 0.6))


func set_umbrella(on: bool, color := Color(0.15, 0.2, 0.45)) -> void:
	if on == _umbrella_on:
		return
	_umbrella_on = on
	if on and umbrella == null:
		umbrella = _make_umbrella(color)
	if umbrella != null:
		umbrella.visible = on
	if proc != null:
		proc.set(&"holding_umbrella", on)


func _make_umbrella(color: Color) -> Node3D:
	var u: Node3D = null
	for p: String in ["res://assets/models/props/umbrella.glb", "res://assets/models/props/umbrella_handheld.glb"]:
		if ResourceLoader.exists(p):
			var ps := NpcUtil.scene(p)
			if ps != null:
				u = ps.instantiate() as Node3D
				break
	if u == null:
		u = Builder.umbrella(color)
	var rig := get_rig()
	var hand := rig.get("HandR") as Node3D
	var skel := model.find_child("Skeleton3D", true, false) as Skeleton3D if model != null and not is_standin else null
	if skel != null and skel.find_bone("hand_R") >= 0:
		var ba := BoneAttachment3D.new()
		ba.bone_name = "hand_R"
		skel.add_child(ba)
		ba.add_child(u)
	elif hand != null:
		hand.add_child(u)
		u.position = Vector3(0, -0.02, 0)
		u.rotation = Vector3(PI * 0.5 - 0.05, 0, 0)   # forearm points forward when holding
	else:
		add_child(u)
		u.position = Vector3(0.18, 1.0, 0.1)
	return u


func tick(dt: float) -> void:
	if proc != null:
		proc.call(&"tick", dt)
	if _umbrella_on and umbrella != null and umbrella.is_inside_tree():
		# keep the canopy upright over the head whatever the arm pose is, slightly tilted forward
		var yaw := global_rotation.y
		umbrella.global_basis = Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, 0.12)


func spin_wheels(distance_moved: float) -> void:
	if model == null:
		return
	var wheels: Array = model.get_meta(&"wheels", []) if model.has_meta(&"wheels") else _find_glb_wheels()
	for w: Variant in wheels:
		var n := w as Node3D
		if n == null:
			continue
		var r := float(n.get_meta(&"radius", 0.3))
		n.rotate_object_local(Vector3.RIGHT, distance_moved / maxf(r, 0.05))


var _glb_wheels: Array = []
var _glb_wheels_scanned := false

func _find_glb_wheels() -> Array:
	if _glb_wheels_scanned:
		return _glb_wheels
	_glb_wheels_scanned = true
	for n: Node in model.find_children("*", "Node3D", true, false):
		var nm := String(n.name).to_lower()
		if "wheel" in nm and not "well" in nm:
			# only the top-most wheel node of a hierarchy
			var par := n.get_parent()
			if par != null and "wheel" in String(par.name).to_lower():
				continue
			if not n.has_meta(&"radius"):
				var aabb := _aabb_of(n as Node3D)
				n.set_meta(&"radius", maxf(aabb.size.y * 0.5, 0.1))
			_glb_wheels.append(n)
	return _glb_wheels


func _aabb_of(n: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for mi: Node in n.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var a := m.get_aabb()
		if first:
			out = a
			first = false
		else:
			out = out.merge(a)
	if n is MeshInstance3D:
		out = (n as MeshInstance3D).get_aabb()
	return out
