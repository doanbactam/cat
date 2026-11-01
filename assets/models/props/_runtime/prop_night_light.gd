extends Node
## Night lighting for a street prop (added by the props post-import to lamps and lanterns).
## Fades the prop's lights (group "prop_night_light", meta "night_light_energy") and its emissive
## materials (MeshInstance3D meta "night_emissive"; material meta "night_emission_energy") in at dusk
## and out at dawn, from the TimeOfDay clock. Materials are shared by every instance of the same
## prop, so all copies switch together (cheap). Set `enabled = false` if the world drives them itself.

@export var enabled := true
## Hours (0..24) when the lights reach full brightness / start fading out.
@export var on_hour := 18.0
@export var off_hour := 5.75
@export var fade_hours := 0.6
## Also light up whenever GameState flag "festival_active" is true and it is dark-ish.
@export var follow_festival := true
@export var update_interval := 0.5

var _lights: Array[Light3D] = []
var _light_energy: Array[float] = []
var _mats: Array[StandardMaterial3D] = []
var _mat_energy: Array[float] = []
var _accum := 0.0
var _last := -1.0


func _ready() -> void:
	var root := get_parent()
	if root == null:
		return
	_collect(root)
	_apply(_night_factor())


func _collect(n: Node) -> void:
	for c in n.get_children():
		_collect(c)
	if n is Light3D and n.is_in_group(&"prop_night_light"):
		_lights.append(n as Light3D)
		_light_energy.append(float(n.get_meta(&"night_light_energy", 1.0)))
	elif n is MeshInstance3D and n.has_meta(&"night_emissive"):
		var mesh := (n as MeshInstance3D).mesh
		if mesh == null:
			return
		for s in mesh.get_surface_count():
			var m := mesh.surface_get_material(s) as StandardMaterial3D
			if m != null and m.emission_enabled and not _mats.has(m):
				_mats.append(m)
				_mat_energy.append(float(m.get_meta(&"night_emission_energy", 2.0)))


func _process(delta: float) -> void:
	if not enabled:
		return
	_accum += delta
	if _accum < update_interval:
		return
	_accum = 0.0
	_apply(_night_factor())


func _night_factor() -> float:
	var tod := get_node_or_null(^"/root/TimeOfDay")
	if tod == null:
		return 0.0
	var h := float(tod.get("hour"))
	var f := 0.0
	if h >= on_hour - fade_hours or h < off_hour:
		f = 1.0
		if h >= on_hour - fade_hours and h < on_hour:
			f = smoothstep(on_hour - fade_hours, on_hour, h)
	elif h < off_hour + fade_hours:
		f = 1.0 - smoothstep(off_hour, off_hour + fade_hours, h)
	if follow_festival and f < 1.0:
		var gs := get_node_or_null(^"/root/GameState")
		if gs != null and gs.has_method(&"get_flag") and bool(gs.call(&"get_flag", &"festival_active", false)):
			f = maxf(f, smoothstep(16.5, 17.5, h))
	return f


func _apply(f: float) -> void:
	if absf(f - _last) < 0.005:
		return
	_last = f
	for i in _lights.size():
		if is_instance_valid(_lights[i]):
			_lights[i].light_energy = _light_energy[i] * f
			_lights[i].visible = f > 0.01
	for i in _mats.size():
		_mats[i].emission_energy_multiplier = _mat_energy[i] * f


## Force a factor (0..1) — handy for showcases and tests.
func set_night_factor(f: float) -> void:
	enabled = false
	_last = -1.0
	_apply(clampf(f, 0.0, 1.0))
