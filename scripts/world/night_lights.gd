extends Node
## Switches the city's artificial lights with the time of day (owner: world).
##
## * Street lamps: Light3D nodes in group "street_lamp" (meta `base_energy`, `switch_at` 0..1 =
##   night_factor threshold so lamps come on staggered at dusk). Their lamp-head emissive material
##   (meta `lamp_material` on the light) follows. Only the `max_shadowed` lamps nearest the camera
##   cast shadows.
## * Shop lights from the city kit (group "city_shop_light") brighten at night.
## * Kit materials named lit_* with meta `night_emission_energy` (lit signs, lit windows) are scaled
##   by night_factor; windows switch per-material so the quarter lights up gradually.
## * Festival: nodes in group "festival_lantern" are shown on the festival night (or when
##   GameState flag `festival_active` / `festival_forced` is set) and glow at night.

@export var max_shadowed := 4
@export var update_interval := 0.25

var night := 0.0
var festival := false
var _festival_override := -1
var _lamps: Array[Light3D] = []
var _shop_lights: Array[Light3D] = []
var _lit_materials: Array[BaseMaterial3D] = []
var _lit_base: Dictionary = {}          # material -> night energy
var _lanterns: Array[Node3D] = []
var _lantern_lights: Array[Light3D] = []
var _timer := 0.0
var _shadow_timer := 0.0


func _ready() -> void:
	add_to_group(&"night_lights")
	refresh_nodes.call_deferred()


func refresh_nodes() -> void:
	_lamps.clear()
	for n in get_tree().get_nodes_in_group(&"street_lamp"):
		if n is Light3D:
			_lamps.append(n)
			if not n.has_meta(&"base_energy"):
				n.set_meta(&"base_energy", (n as Light3D).light_energy)
	_shop_lights.clear()
	for n in get_tree().get_nodes_in_group(&"city_shop_light"):
		if n is Light3D:
			_shop_lights.append(n)
			if not n.has_meta(&"base_energy"):
				n.set_meta(&"base_energy", (n as Light3D).light_energy)
	_lanterns.clear()
	_lantern_lights.clear()
	for n in get_tree().get_nodes_in_group(&"festival_lantern"):
		if n is Light3D:
			_lantern_lights.append(n)
			if not n.has_meta(&"base_energy"):
				n.set_meta(&"base_energy", (n as Light3D).light_energy)
		elif n is Node3D:
			_lanterns.append(n)
	_collect_lit_materials()
	_apply(true)


func _collect_lit_materials() -> void:
	_lit_materials.clear()
	_lit_base.clear()
	var root := get_parent()
	if root == null:
		return
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var n: Node = stack.pop_back()
		for c in n.get_children():
			stack.append(c)
		var mi := n as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.get_active_material(i) as BaseMaterial3D
			if m == null or _lit_base.has(m):
				continue
			if m.has_meta(&"night_emission_energy") or m.resource_name.begins_with("lit_"):
				var e := float(m.get_meta(&"night_emission_energy", 2.0))
				if m.resource_name.begins_with("lit_lamp"):
					continue          # shop tubes burn all day
				_lit_base[m] = e
				_lit_materials.append(m)


## Force the festival look (tests / screenshots). -1 = automatic.
func set_festival_override(state: int) -> void:
	_festival_override = state
	_apply(true)


func _process(delta: float) -> void:
	_timer -= delta
	if _timer <= 0.0:
		_timer = update_interval
		_apply(false)
	_shadow_timer -= delta
	if _shadow_timer <= 0.0:
		_shadow_timer = 1.0
		_update_shadow_casters()


func _is_festival() -> bool:
	if _festival_override >= 0:
		return _festival_override == 1
	var gs: Node = get_node_or_null(^"/root/GameState")
	if gs != null and (bool(gs.call(&"get_flag", &"festival_active", false)) or bool(gs.call(&"get_flag", &"festival_forced", false))):
		return true
	var tod: Node = get_node_or_null(^"/root/TimeOfDay")
	if tod != null and tod.has_method(&"is_festival_night"):
		return bool(tod.call(&"is_festival_night"))
	return false


func _apply(force: bool) -> void:
	var env := get_tree().get_first_node_in_group(&"world_environment_controller")
	var nf := float(env.get(&"night_factor")) if env != null else 0.0
	if not force and absf(nf - night) < 0.004 and festival == _is_festival():
		return
	night = nf
	festival = _is_festival()
	for l in _lamps:
		if not is_instance_valid(l):
			continue
		var thr := float(l.get_meta(&"switch_at", 0.35))
		var on := smoothstep(thr, thr + 0.08, night)
		l.light_energy = float(l.get_meta(&"base_energy", 1.0)) * on
		l.visible = on > 0.01
		var lm: Variant = l.get_meta(&"lamp_material", null)
		if lm is StandardMaterial3D:
			(lm as StandardMaterial3D).emission_energy_multiplier = 4.0 * on
	for l in _shop_lights:
		if is_instance_valid(l):
			l.light_energy = float(l.get_meta(&"base_energy", 1.0)) * lerpf(0.6, 1.25, night)
	for m in _lit_materials:
		var e: float = _lit_base[m]
		# per-material stagger so windows don't all switch at once
		var thr := 0.2 + float(hash(m.resource_name) % 100) / 100.0 * 0.5
		m.emission_energy_multiplier = e * smoothstep(thr, thr + 0.15, night)
	for n in _lanterns:
		if is_instance_valid(n):
			n.visible = festival
	for l in _lantern_lights:
		if is_instance_valid(l):
			l.visible = festival and night > 0.2
			l.light_energy = float(l.get_meta(&"base_energy", 1.0)) * smoothstep(0.2, 0.5, night)


func _update_shadow_casters() -> void:
	var cam := get_viewport().get_camera_3d() if get_viewport() != null else null
	if cam == null or _lamps.is_empty():
		return
	var p := cam.global_position
	var lit: Array[Light3D] = []
	for l in _lamps:
		if is_instance_valid(l) and l.visible:
			lit.append(l)
	lit.sort_custom(func(a: Light3D, b: Light3D) -> bool: return a.global_position.distance_squared_to(p) < b.global_position.distance_squared_to(p))
	for i in lit.size():
		lit[i].shadow_enabled = i < max_shadowed
