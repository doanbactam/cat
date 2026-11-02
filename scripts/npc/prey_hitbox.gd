extends Area3D
## Tiny swipe/pounce target attached to prey and small animals (owner: world-life).
## The player's paw swipe intersects areas on the NPC layer and calls `on_swiped(by)` on the
## collider itself; this forwards to the owning agent with the index of the animal it belongs to.

var agent: Object = null
var index := -1


func setup(p_agent: Object, p_index: int, radius: float) -> void:
	agent = p_agent
	index = p_index
	collision_layer = 1 << 2      # npc
	collision_mask = 0
	monitoring = false
	monitorable = true
	var cs := CollisionShape3D.new()
	var sph := SphereShape3D.new()
	sph.radius = radius
	cs.shape = sph
	cs.position = Vector3(0, radius, 0)
	add_child(cs)


func on_swiped(by: Node) -> void:
	if agent != null and is_instance_valid(agent) and agent.has_method(&"on_part_swiped"):
		agent.call(&"on_part_swiped", index, by)
