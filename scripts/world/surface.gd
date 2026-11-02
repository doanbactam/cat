extends RefCounted
## Surface lookup for footsteps / landing sounds / dust / fur wetness (owner: world).
##
## Usage: `load("res://scripts/world/surface.gd").get_surface(collider)` (static).
## Resolution order: metadata `surface` on the collider or any ancestor (stops at the scene root),
## a PhysicsMaterial whose resource_name is a known surface, water layer (7) → `water`,
## otherwise `concrete`.

const SURFACES: Array[StringName] = [
	&"asphalt", &"concrete", &"tile", &"wood", &"metal", &"grass", &"dirt", &"water",
	&"roof_tile", &"fabric", &"plastic",
]
const LAYER_WATER := 1 << 6
const DEFAULT_SURFACE := &"concrete"


static func get_surface(collider: Object) -> StringName:
	if collider == null:
		return DEFAULT_SURFACE
	var n := collider as Node
	var depth := 0
	while n != null and depth < 8:
		if n.has_meta(&"surface"):
			return normalize(StringName(str(n.get_meta(&"surface"))))
		n = n.get_parent()
		depth += 1
		if n is Window:
			break
	var sb := collider as StaticBody3D
	if sb != null and sb.physics_material_override != null:
		var pm_name := StringName(sb.physics_material_override.resource_name)
		if pm_name in SURFACES:
			return pm_name
	var co := collider as CollisionObject3D
	if co != null and (co.collision_layer & LAYER_WATER) != 0:
		return &"water"
	return DEFAULT_SURFACE


## Maps loose names (e.g. "stone", "brick", "pavers") onto the contract set.
static func normalize(s: StringName) -> StringName:
	if s in SURFACES:
		return s
	match String(s):
		"stone", "granite", "pavers", "paver", "brick", "terrazzo", "ceramic":
			return &"tile"
		"soil", "mud", "sand":
			return &"dirt"
		"leaves", "moss", "lawn":
			return &"grass"
		"glass", "steel", "iron":
			return &"metal"
		"cloth", "canvas", "carpet":
			return &"fabric"
		"roof", "rooftile":
			return &"roof_tile"
	return DEFAULT_SURFACE
