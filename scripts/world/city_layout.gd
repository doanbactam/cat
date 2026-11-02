extends RefCounted
## Hàng Mây map data (owner: world). Godot space: +X east, -Z north, metres. Sidewalk level y = 0,
## road surface y = ROAD_Y. The quarter is ≈ 240 × 200 m (x −120…120, z −100…100).
## Everything the builder places is derived from these tables, so tweaking the map = editing here.

const ROAD_Y := -0.15
const MAP_MIN := Vector2(-120.0, -100.0)
const MAP_MAX := Vector2(120.0, 100.0)

## Streets: axis "x" runs east-west (center = z), axis "z" runs north-south (center = x).
## [id, axis, center, from, to, road_width, sidewalk_width, speed_limit, kinds]
const STREETS := [
	["pho_hang_may", "x", -70.0, -130.0, 130.0, 8.0, 3.0, 8.0, ["scooter", "bicycle", "cyclo", "car"]],
	["pho_dinh", "x", 62.0, -130.0, 130.0, 8.0, 3.0, 7.0, ["scooter", "bicycle", "cyclo"]],
	["pho_ho", "z", -55.0, -66.0, 58.0, 6.0, 3.0, 6.0, ["scooter", "bicycle"]],
	["pho_cho", "z", 50.0, -66.0, 58.0, 6.0, 3.0, 5.0, ["scooter", "bicycle"]],
]

## Lake Hồ Gương.
const LAKE_CENTER := Vector2(-2.0, 4.0)
const LAKE_RADII := Vector2(36.0, 30.0)
const LAKE_WATER_Y := -0.35
const LAKE_DEPTH := 2.0
const PROMENADE_W := 5.0
const ISLET_CENTER := Vector2(16.0, 2.0)
const ISLET_RADII := Vector2(6.5, 5.0)

## Alleys (rects x0, z0, x1, z1) in the west maze.
const HEM_A := Rect2(-91.1, -63.0, 2.2, 118.0)       # main N-S hẻm, tea stall at its north mouth
const HEM_B := Rect2(-120.0, -6.0, 59.0, 2.0)        # E-W hẻm to Phố Hồ
const NGO_C := Rect2(-110.6, -19.0, 1.2, 13.0)       # 1.2 m ngõ into the water-tower court
const TOWER_COURT := Rect2(-119.0, -49.0, 15.0, 30.0)
const WATER_TOWER_POS := Vector2(-112.0, -34.0)

## Temple compound (Đình Hàng Mây) on the south side of Phố Đình.
const TEMPLE_RECT := Rect2(-34.0, 69.0, 68.0, 31.0)
const TEMPLE_HALL_CENTER := Vector2(0.0, 90.0)
const TEMPLE_BANYAN := Vector2(-19.0, 81.0)
const BELL_PAVILION := Vector2(20.0, 79.0)

## Market (Chợ Hàng Mây) inside the east block.
const MARKET_RECT := Rect2(58.0, -48.0, 60.0, 88.0)
const MARKET_HALL := Rect2(64.0, -42.0, 36.0, 34.0)
const FISH_LANE_Z := 8.0

## Building rows: [name, start(x,z) = local −X end of the front line, facing(x,z), length,
##   max_depth, style weights {style: w}, gaps [[from,to] along row], corner_at_end, rooftop_net]
## facing = direction the facades look (toward the street). Rows run along local +X.
const ROWS := [
	# Phố Hàng Mây north side (facing south, +Z): continuous; heart of the north rooftop network
	["main_north", Vector2(-120.0, -77.0), Vector2(0, 1), 240.0, 16.0,
		{"colonial": 3.0, "tube90s": 3.0, "modern": 1.0, "old_tile": 0.6}, [], false, true],
	# Phố Hàng Mây south side, maze segment (facing north): local +X = west. Gap = hẻm A mouth.
	["main_south_w", Vector2(-61.0, -63.0), Vector2(0, -1), 59.0, 13.0,
		{"colonial": 2.0, "tube90s": 3.0, "old_tile": 1.0}, [[27.9, 30.1]], false, true],
	# lake segment, corner (café-style chamfer) at the Phố Hồ end
	["main_south_lake", Vector2(44.0, -63.0), Vector2(0, -1), 93.0, 14.0,
		{"colonial": 3.0, "tube90s": 2.0, "modern": 1.0}, [], true, true],
	# market segment: corner = Bông's café at Phố Chợ
	["main_south_market", Vector2(120.0, -63.0), Vector2(0, -1), 64.0, 14.0,
		{"colonial": 2.0, "tube90s": 2.0, "modern": 1.0}, [], true, false],
	# Phố Hồ west side (maze east edge), facing east: local +X = south. Gap = hẻm B mouth.
	["pho_ho_w", Vector2(-61.0, 45.0), Vector2(1, 0), 94.0, 14.0,
		{"tube90s": 3.0, "colonial": 1.5, "old_tile": 1.0}, [[49.0, 51.0]], false, true],
	# Phố Chợ east side (market west edge), facing west: local +X = north. Gap = market entrance + fish lane.
	["pho_cho_e", Vector2(56.0, -49.0), Vector2(-1, 0), 104.0, 14.0,
		{"tube90s": 2.0, "colonial": 2.0, "modern": 1.0}, [[11.0, 37.0], [55.0, 59.0]], false, false],
	# Phố Đình north side, maze segment (facing south): corner at Phố Hồ end
	["dinh_north_w", Vector2(-120.0, 55.0), Vector2(0, 1), 59.0, 14.0,
		{"old_tile": 1.5, "colonial": 2.0, "tube90s": 2.0}, [[28.9, 31.1]], true, true],
	# Phố Đình north side, market segment
	["dinh_north_e", Vector2(70.0, 55.0), Vector2(0, 1), 50.0, 14.0,
		{"tube90s": 2.0, "colonial": 1.5, "modern": 1.0}, [], false, false],
	# Phố Đình south side, west of the temple (facing north): local +X = west
	["dinh_south_w", Vector2(-36.0, 69.0), Vector2(0, -1), 84.0, 16.0,
		{"colonial": 2.0, "tube90s": 2.0, "old_tile": 1.5, "modern": 0.7}, [], false, true],
	["dinh_south_e", Vector2(120.0, 69.0), Vector2(0, -1), 84.0, 16.0,
		{"colonial": 2.0, "tube90s": 2.0, "modern": 1.0}, [], false, false],
	# --- west maze interior (rooftop network) ---
	["hem_a_w_n", Vector2(-91.1, -6.0), Vector2(1, 0), 43.0, 13.0, {"tube90s": 3.0, "old_tile": 1.5, "colonial": 1.2}, [], false, true],
	["hem_a_w_s", Vector2(-91.1, 41.0), Vector2(1, 0), 45.0, 13.0, {"tube90s": 3.0, "old_tile": 1.5, "colonial": 1.2}, [], false, true],
	["hem_a_e_n", Vector2(-88.9, -49.0), Vector2(-1, 0), 43.0, 13.0, {"tube90s": 3.0, "old_tile": 1.0, "colonial": 1.2}, [], false, true],
	["hem_a_e_s", Vector2(-88.9, -4.0), Vector2(-1, 0), 45.0, 13.0, {"tube90s": 3.0, "old_tile": 1.0, "colonial": 1.2}, [], false, true],
	["hem_b_n", Vector2(-120.0, -6.0), Vector2(0, 1), 16.0, 13.0, {"old_tile": 2.0, "tube90s": 2.0, "colonial": 1.2}, [[9.4, 10.6]], false, true],
	["hem_b_s", Vector2(-104.0, -4.0), Vector2(0, -1), 16.0, 13.0, {"old_tile": 2.0, "tube90s": 2.0, "colonial": 1.2}, [], false, true],
]

## Low alley walls (kind "alley") lining ngõ C and the tower court; rear walls closing block
## interiors / map edge: [start, facing, length, kind]
const WALL_RUNS := [
	[Vector2(-104.6, -49.0), Vector2(-1, 0), 30.0, "wall"],      # backs of hẻm A west rows → tower court
	[Vector2(-120.0, -95.0), Vector2(0, 1), 240.0, "wall"],      # behind the north row (map edge)
	[Vector2(-121.5, 41.0), Vector2(1, 0), 104.0, "wall"],       # west map edge, facing into the maze
	[Vector2(121.5, -63.0), Vector2(-1, 0), 118.0, "wall"],      # east map edge, facing into the market
	[Vector2(120.0, 86.5), Vector2(0, -1), 84.0, "wall"],        # behind the temple-street south rows
	[Vector2(-36.0, 86.5), Vector2(0, -1), 84.0, "wall"],
]

## Location markers: [location_id, display_name_key, x, y, z, radius]
const LOCATIONS := [
	["tea_stall", "LOC_TEA_STALL", -87.0, 0.0, -64.6, 4.0],
	["pho_hang_may", "LOC_MAIN_STREET", -20.0, 0.0, -70.0, 14.0],
	["cafe_bong", "LOC_CAFE", 58.0, 0.0, -61.0, 6.0],
	["hem_maze", "LOC_WEST_ALLEYS", -90.0, 0.0, -20.0, 10.0],
	["rooftops", "LOC_ROOFTOPS", -70.0, 12.0, -88.0, 12.0],
	["water_tower", "LOC_WATER_TOWER", -112.0, 15.0, -34.0, 4.0],
	["ho_guong", "LOC_LAKE", -2.0, 0.0, -30.0, 12.0],
	["banyan", "LOC_BANYAN", 13.0, 0.3, 2.0, 6.0],
	["riddle_bridge", "LOC_BRIDGE", 28.5, 1.0, 2.0, 3.0],
	["islet_shrine", "LOC_ISLET_SHRINE", 18.5, 0.3, 4.5, 4.0],
	["cho_hang_may", "LOC_MARKET", 82.0, 0.0, -25.0, 16.0],
	["fish_street", "LOC_FISH_STREET", 80.0, 0.0, 8.0, 8.0],
	["pho_dinh", "LOC_TEMPLE_STREET", 0.0, 0.0, 62.0, 14.0],
	["dinh_hang_may", "LOC_TEMPLE", 0.0, 0.0, 78.0, 12.0],
	["temple_roof", "LOC_TEMPLE_ROOF", 0.0, 9.0, 90.0, 4.0],
	["riddle_bell", "LOC_BELL_PAVILION", 20.0, 0.0, 79.0, 3.0],
	["riddle_sun", "LOC_SUN_STEPS", 33.0, 0.0, 22.0, 3.0],
]
