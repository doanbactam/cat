class_name UIMapCapture
extends RefCounted
## Renders a top-down orthographic picture of the current 3D world once (SubViewport sharing the
## main World3D, flat ambient light, no fog/post), caches it per scene instance and returns
## {"texture": Texture2D, "bounds": Rect2 (world XZ: position = min x/z, size = width/depth)}.
## Bounds: current scene meta "map_bounds" (Rect2) if present, else the union of its visual AABBs
## (things larger than 1 km ignored), else the GDD quarter size (240 × 200 m).

const DEFAULT_BOUNDS := Rect2(-120.0, -100.0, 240.0, 200.0)
const MAX_EXTENT := 600.0

static var _cache_tex: Texture2D = null
static var _cache_bounds := Rect2()
static var _cache_scene := 0


static func clear_cache() -> void:
	_cache_tex = null
	_cache_scene = 0


static func get_cached(scene: Node) -> Dictionary:
	if _cache_tex != null and scene != null and _cache_scene == scene.get_instance_id():
		return {"texture": _cache_tex, "bounds": _cache_bounds}
	return {}


static func compute_bounds(scene: Node) -> Rect2:
	if scene == null:
		return DEFAULT_BOUNDS
	var meta: Variant = scene.get_meta(&"map_bounds") if scene.has_meta(&"map_bounds") else null
	if not (meta is Rect2) and scene.is_inside_tree():
		var city_node := scene.get_tree().get_first_node_in_group(&"city")
		if city_node != null and city_node.has_meta(&"map_bounds"):
			meta = city_node.get_meta(&"map_bounds")
	if meta is Rect2:
		return meta
	var have := false
	var r := Rect2()
	for n in scene.find_children("*", "VisualInstance3D", true, false):
		var vi := n as VisualInstance3D
		if not vi.is_visible_in_tree() or vi is Light3D:
			continue
		var ab := vi.global_transform * vi.get_aabb()
		if ab.size.x > 1000.0 or ab.size.z > 1000.0 or ab.size.x <= 0.0:
			continue
		var rr := Rect2(ab.position.x, ab.position.z, ab.size.x, ab.size.z)
		if not have:
			r = rr
			have = true
		else:
			r = r.merge(rr)
	if not have:
		return DEFAULT_BOUNDS
	r = r.grow(6.0)
	if r.size.x > MAX_EXTENT or r.size.y > MAX_EXTENT:
		var c := r.get_center()
		r = Rect2(c - Vector2(MAX_EXTENT, MAX_EXTENT) * 0.5, Vector2(MAX_EXTENT, MAX_EXTENT)).intersection(r)
	return r


## Awaitable. Returns {} in headless mode or when there is no 3D world.
static func capture(host: Node, resolution: int = 2048) -> Dictionary:
	var tree := host.get_tree()
	var scene: Node = tree.current_scene
	if scene == null:
		scene = tree.get_first_node_in_group(&"city")
	if scene == null:
		scene = host.owner if host.owner != null else tree.root
	var cached := get_cached(scene)
	if not cached.is_empty():
		return cached
	if DisplayServer.get_name() == "headless" or scene == null:
		return {}
	var world := host.get_viewport().world_3d
	if world == null:
		return {}
	var bounds := compute_bounds(scene)
	var side := maxf(bounds.size.x, bounds.size.y)
	var square := Rect2(bounds.get_center() - Vector2(side, side) * 0.5, Vector2(side, side))
	var sv := SubViewport.new()
	sv.size = Vector2i(resolution, resolution)
	sv.world_3d = world
	sv.own_world_3d = false
	sv.transparent_bg = false
	sv.msaa_3d = Viewport.MSAA_4X
	sv.render_target_update_mode = SubViewport.UPDATE_ONCE
	sv.positional_shadow_atlas_size = 0
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.keep_aspect = Camera3D.KEEP_HEIGHT
	cam.size = side
	cam.near = 0.5
	cam.far = 600.0
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("#d8c7a0")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(1.0, 0.97, 0.92)
	env.ambient_light_energy = 1.25
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.fog_enabled = false
	env.volumetric_fog_enabled = false
	env.sdfgi_enabled = false
	env.ssao_enabled = true
	env.ssao_radius = 3.0
	env.ssao_intensity = 2.5
	env.glow_enabled = false
	cam.environment = env
	sv.add_child(cam)
	host.add_child(sv)
	cam.global_transform = Transform3D(Basis.from_euler(Vector3(-PI * 0.5, 0.0, 0.0)), Vector3(square.get_center().x, 250.0, square.get_center().y))
	cam.current = true
	var saved_vis: Array = []
	for n in scene.find_children("*", "GeometryInstance3D", true, false):
		var gi := n as GeometryInstance3D
		if gi != null and gi.visibility_range_end > 0.0:
			saved_vis.append([gi, gi.visibility_range_end, gi.visibility_range_end_margin])
			gi.visibility_range_end = 0.0
			gi.visibility_range_end_margin = 0.0
	for i in 3:
		await RenderingServer.frame_post_draw
	for item: Array in saved_vis:
		var gi := item[0] as GeometryInstance3D
		if is_instance_valid(gi):
			gi.visibility_range_end = float(item[1])
			gi.visibility_range_end_margin = float(item[2])
	var img := sv.get_texture().get_image()
	sv.queue_free()
	if img == null or img.is_empty():
		return {}
	img.generate_mipmaps()
	var tex := ImageTexture.create_from_image(img)
	_cache_tex = tex
	_cache_bounds = square
	_cache_scene = scene.get_instance_id()
	return {"texture": tex, "bounds": square}
