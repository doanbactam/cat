# city-landmarks — temple, market, lake, shrines, café, tea stall

Owner area: `city-landmarks` · paths: `blender/landmarks/`, `blender/lib/landmarks_*.py`,
`assets/models/landmarks/`, `assets/textures/landmarks/`, `tests/test_city_landmarks.gd`.

Everything is procedural and seeded (numpy/Pillow textures, headless Blender 5.2 geometry, a Godot
post-import script). The kit is built **on top of the city-houses pipeline, used read-only**: its bmesh
builder (`city_geo.MB`), component library (`city_parts`: grime/vertex-colour weathering, decals,
foliage cards, railings, drainpipes, ladders, corrugated sheets…), material conventions (`city_mats`) and
its tileable texture library in `assets/textures/architecture/`. Landmark-specific textures live in
`assets/textures/landmarks/`. Both kits share textures by URI (no embedded copies).

## What was built (16 GLBs, `assets/models/landmarks/catalog.json`)

| id | what | size (m) | tris | notes |
|---|---|---|---|---|
| `dinh_hang_may` | **Đình Hàng Mây** communal temple complex | 26 × 37, ridge 9.6 | ~91 k | three-entrance gate (tam quan) with two-tier + side roofs, plaque "ĐÌNH HÀNG MÂY", gilt couplet boards (procedural pseudo-glyphs, no real text), plank doors with gilt bosses standing open; two flag pillars with lantern heads; 2.4 m courtyard walls with tile coping (walkable), green ceramic vent blocks, pilasters, weathering decals; Bát Tràng brick courtyard + bluestone path; banyan planter (**marker only**, tree from vehicles-nature); bell pavilion with bronze bell + striker log; bronze tripod incense burner on a stepped bluestone plinth with smoking sticks; glazed pots with shrubs; main hall on a 0.75 m stone platform with 5-step stair + cloud-scroll cheeks, 5 bays of red-lacquered columns on carved bluestone bases, veranda beams with gilt cloud brackets, 20 carved door leaves (two atlas panel designs, central bay open), round lattice windows, interior altar (gilt tabernacle, candles, fruit, incense, plaque, couplets, mats); **concave hip roof with upturned corners** (fish-scale tiles, tile-end row, soffits + rafters), ridge band with gilt cloud frieze, cloud-horn end finials, sun-disc centre ornament with flame curls, hip ridges ending in curled tips; **crow nest on the ridge** (woven twig rings, alpha twig cards, bottle caps, spoon, marble, key, foil, brass bell, coins); east lean-to store shed = the roof route (wall coping 2.55 → shed roof 3.35 → hall eave ~3.9 → climbable upper roof bands → walkable ridge). |
| `cho_market_hall` | covered market (Chợ) | 24.6 × 18.6, ridge 8.8 | ~40 k | concrete columns on a 6 m grid, 5 steel Pratt trusses (walkable 5.2 m bottom chords + top chords), purlins, individually laid corrugated sheets (mostly rusted, some newer blue) with a raised ventilation monitor + louvres, gutters; wet floor (trowelled concrete with wet low-roughness patches) and drain grating; 8 tiled fish counters (white glazed tile, ice + fish display, basins with water + aerator hose, scales, price cards, styrofoam boxes, red basins, stools, hanging bulbs), cô Hoa's counter with her sign "CÁ TƯƠI CÔ HOA"; 10 wooden produce platforms with bamboo trays of greens/tomatoes/chilli/oranges/dragon fruit/bananas/herbs/dry goods, sacks; striped tarps tied under trusses; crate stack + steel service ladder + downpipe = climb routes to the trusses; back brick half-wall. |
| `cho_stall_lane` | 12 m open-air stall row | 12 × 3.2 | ~17.5 k | 4 stalls (2 big market umbrellas with slack panels, scalloped valance, stretchers + runner; 2 wrinkled striped/orange tarps on bamboo poles with droopy front valances), boards on crates, produce trays, price cards, stools, baskets, conical hats, crates. |
| `cho_gate_arch` | market-street gate arch | 9 × 0.8, h 6.5 | ~9 k | two plaster pillars on stone plinths (climbable), arched beam, "CHỢ HÀNG MÂY" sign both faces, small tiled canopy with curled ends + sun disc, red lanterns (night lights), star lantern. |
| `ho_embank_straight_4m` / `ho_embank_curve_30` / `ho_embank_steps_4m` | Hồ Gương embankment | 4 × 3 | 0.3–0.9 k | battered ashlar wall with waterline algae band, bluestone coping blocks (individually jittered), brick paving 3 m deep; steps: 6 bluestone steps to a landing at -0.85 with cheek walls and lotus-capped posts. |
| `ho_railing_4m` | lake railing | 4 | 0.7 k | bluestone posts with lotus caps, two green steel rails (top rail = cat balance beam), sagging chain. |
| `ho_bridge` | red wooden arched bridge (cầu) | 3.4 × 17.6, rise 1.55 | ~15 k | individual deck planks on 4 curved stringers, 6 post-pair piers with cross bracing and algae bands, balustrade with lattice + posts with caps, walkable handrails, stone abutments with end posts. |
| `ho_islet_shrine` | islet + tiny shrine | 9 × 7 | ~8 k | irregular stone-edged islet, leaf-litter dome, stepping-stone path from the bridge landing, pavilion on a two-step plinth with 4 lacquered columns, lattice side screens, back panel with gilt glyph medallion, stone altar with incense, fruit and vase, curled hip roof with gilt finial, old frangipani (climbable), shrubs, stone stools. |
| `ho_lamp_post` | lake promenade lamp | h 3.55 | 2 k | cast-iron fluted post, three opal globes on scroll arms (night emissive + `LIGHT_NIGHT`). |
| `ho_bench` | promenade bench | 1.8 | 1 k | cast-iron scroll frames, wooden slats. |
| `shrine_wall_box` | wall altar box | 0.6 | 5 k | red lacquered shrine on iron brackets: tiny curled roof, gilt columns + frieze, back panel, two gilt figures, incense, electric candles (always lit), cups, fruit. |
| `shrine_tree` | post/tree shrine (am thờ) | h 1.9 | 4 k | concrete post with red cloth band, same shrine house, incense pot at the foot. |
| `cafe_bong` | **Bông's café** (upscale) | 6 × 10, 2 floors + roof terrace | ~13 k | city-compatible shop module: white render facade, black steel-framed glazing, folding glass doors open, real 3D interior 4.4 m deep (wood floor, exposed-brick side walls, L counter with espresso machine, pastry case, grinder, shelves with cups and jars, pendant lamps, rattan chairs, terrazzo tables, **Bông's window cushion** = nap spot + `MARKER_bong_spot`), lit sign "Bông café" in the transom, dark-green canvas awning, wooden terrace deck with planters, bistro tables + chalkboard menu, wall lanterns, balcony with planter boxes, bougainvillea cascade and hanging pothos, steel railing, roof terrace with pergola + vines + string lights, lounger cushion (nap), plants, water tank, climbable downpipe. |
| `quan_tra_ba_tu` | **Grandma Tư's tea stall** (quán trà) | 4 × 2.8 | ~12.5 k | the emotional home: wrinkled, sagging faded blue tarp + an older striped tarp (torn corner hanging off the side) layered on a batten and two bamboo poles with guy ropes, a front valance that droops between its ties, hand-painted sign "TRÀ ĐÁ · TRÀ NÓNG / QUÁN BÀ TƯ", old teal-painted open-fronted counter with a glass display box of sweets, four snack jars (peanut candy, sunflower seeds, ô mai, rice crackers), tray of upturned tea glasses, teapot in a padded rattan warmer, two vacuum flasks, a radio, a plate of peanut candy, a rattan fan; **Cam's cardboard bed with a folded cushion under the counter** + Cam's blue enamel bowl; Grandma's low wooden chair, nón lá on a nail, wall calendar, menu board, "lost duck" poster; honeycomb-briquette brazier with a big dented aluminium kettle (warm nap spot), iced-tea cooler on a styrofoam ice box, water cans; two low blue tables with iced tea + sunflower seeds, 8 scattered red/blue plastic stools + a stack; hanging bulb (night light), bunch of bananas, strings of snack packets, paint-can herb pots, a star lantern. |

### Materials (`assets/textures/landmarks/`, 1024² tiles, ≥ 512 px/m)
`lacquer_red`, `gilt` (gold leaf rubbed through to red lacquer, crazed), `wood_aged`, `bluestone` (tooling,
calcite veins, worn polish), `brick_paving` (30 cm Bát Tràng tiles, mossy joints), `plaster_temple`
(ochre lime wash, peeling), `bronze` (verdigris, soot), `stone_embank` (coursed ashlar + waterline algae),
`stone_plinth`, `wood_red_paint` (bridge), `leaves_ground`, `tile_white` (fish counters), `market_floor`
(wet patches), `steel_green`, `tarp_stripe` / `tarp_blue` / `tarp_orange` (woven PE, UV-faded). Generated by
`gen_textures.py`, partly through the city generator functions (`wood`, `tiles`, `plaster`,
`painted_metal`) with the output dir redirected.
**Atlas** `landmarks_atlas.png` (+ `_normal.png` from carved relief height): carved door panels (cloud
medallion / lotus, lattice tops, leaf scrolls), cloud frieze, temple plaque, couplet boards, market gate sign,
café sign + chalk menu, tea-stall sign + menu, shrine back panel, calendar, snack piles, fish on ice,
shrimp, produce piles, price cards, fish-stall sign, nest twigs (alpha), café interior, lantern paper, tea
label, "lost duck" poster. All lettering is fictional; ornaments (cloud curls, leaf scrolls, lotus, sun disc)
are drawn by the generator — no copied designs.

## How to regenerate
```bash
python3 blender/landmarks/gen_textures.py [--only lacquer_red,...] [--sheet]   # ~1.5 min, PBR sets + materials.json
python3 blender/landmarks/gen_atlas.py [--sheet]                              # ~10 s, atlas + atlas.json
python3 blender/landmarks/write_texture_imports.py                            # Godot .import presets
tools/blender_run.sh blender/landmarks/build_landmarks.py [--only id-prefix,...] [--preview [all]]   # ~6 min all
tools/godot_import.sh && tools/run_tests.sh city_landmarks
```
Needs the city-houses textures (`assets/textures/architecture/`) present. `--preview` writes Cycles QA
renders to `qa/out/city-landmarks/<id>[_n].png` (lake pieces get a preview-only water plane).
In-engine QA: `assets/models/landmarks/preview/landmarks_showcase.tscn` (day) and
`landmarks_showcase_night.tscn` (night lights / emissives on).

## API / conventions for other areas
- **Catalog** (`catalog.json`, JSON array): the city keys (`id, file, kind, width, depth, height, floors,
  style, climb_points, nap_spots, entrances`, Godot space relative to origin) plus `markers`
  (`{name: [[x,y,z], …]}`), `zones` (shelter / reverb boxes), `origin` (text), `category`, `colliders`, `tris`.
  `kind`: `landmark` (most), `shop` (café, tea stall), `roof_prop` (shrine boxes).
- **Origins / facing**: front faces Godot +Z. Temple: gate front centre; lake pieces: water-side top edge,
  water toward +Z, walkway 0, water -1.0; bridge: midpoint (spans Z); islet: centre; café: city module
  convention; tea stall: front centre, wall 2.8 m behind.
- **Post-import** (`assets/models/landmarks/_import/landmarks_post_import.gd`): materials as the city kit
  (`arch_*`/`lm_*` opaque with vertex colour, `dec_*` alpha blend incl. glass jars, `fol_*` scissor,
  `lit_*` night emissive with meta `night_emission_energy`; `lit_lamp` always on); colliders → StaticBody3D
  + one BoxShape3D (layer 1, +6 & group `climbable` for `climb`, +9 for `wall`), meta `surface`; markers:
  `NAP_*`/`CLIMB_*`/`ENTRANCE_*` (groups `landmark_*` and `city_*`), `QUEST_<id>` → group `quest_target` +
  meta `target_id` (`crow_nest`, `fish_stall`), `MARKER_<id>` → group `landmark_marker` + meta `marker_id`,
  `LIGHT_SHOP_*` (always-on fill), `LIGHT_NIGHT_*` (group `landmark_night_light`, energy 0, meta
  `night_energy`), `LIGHT_ALTAR_*`, `SHELTER_*` → `Area3D` in group `shelter` with a BoxShape3D,
  `REVERB_<Bus>_*` → `Area3D` with `reverb_bus_enabled` (Temple / Market / Interior), layer 10.
- Story markers: `QUEST_crow_nest` (temple ridge, y ≈ 9.5), `MARKER_banyan`, `MARKER_bell`, `MARKER_burner`,
  `MARKER_altar`, `MARKER_temple_roof`, `MARKER_roof_route`, `MARKER_fish_stall` (+ `QUEST_fish_stall`),
  `MARKER_cam_bed`, `MARKER_bowl`, `MARKER_stall_counter`, `MARKER_grandma`, `MARKER_tea_stall`,
  `MARKER_bong_spot`, `MARKER_cafe`, `MARKER_riddle_bridge`, `MARKER_islet_shrine`, `MARKER_bridge_landing`,
  `MARKER_pigeons`, `MARKER_water_access`, `MARKER_shrine`, `MARKER_market_gate`, `MARKER_market_hall`.

## Tests / verification
`tests/test_city_landmarks.gd` (7 tests): catalog contract + required ids + story markers; every GLB imports
through the landmark post-import with only BoxShape3D colliders, valid surfaces, vertex-colour materials and
climbable colliders when climb points exist; **physics**: every nap spot has support 0–0.35 m below, every
climb point touches a layer-6 collider; the crow nest is a `quest_target` up on the ridge with a collider
under it and a walkable ridge next to it, temple shelters/reverb zone/altar light exist; bridge deck is
walkable end to end with `wood` surface; textures are shared files (not embedded); showcase scene loads.

## Visual QA log (`qa/out/city-landmarks/`)
Cycles previews: `qa/out/city-landmarks/<id>[_n].png` (written by `--preview`). In-engine (Forward+,
lavapipe): `qa/out/city-landmarks/g/tour_<n>.png`, captured in ONE Godot launch with the showcase camera tour:
```bash
tools/screenshot.sh scene=res://assets/models/landmarks/preview/landmarks_showcase.tscn \
  out=$PWD/qa/out/city-landmarks/g/tour.png size=960x540 call=start_tour frames=40 shots=10 step=30
```
(poses in `landmarks_showcase.gd` `TOUR`: temple gate, courtyard, ridge/nest, tea stall, tea stall at cat
eye height, café, market interior, stall lane, lake + bridge, islet.)

Iterations (session 1 → session 2, newest last):
1. Session 1: textures/atlas sheets, per-module Cycles previews, roof curvature + ridge ornaments, market
   truss climb route, café interior, tea-stall dressing (see the git history of `blender/landmarks/`).
2. Critique of the session-1 renders: tea-stall tarp read as a flat slab, iced-tea glasses looked milky,
   market umbrellas were flat 8-sided cones, stall tarps were stiff, the wall-shrine roof tiles were at full
   building scale (4 rows on a 60 cm roof), stale embedded-texture copies (`dinh_hang_may_*.jpg/png`, 25 MB,
   left by an old import) sat next to the GLBs.
   Fixes: `sag_cloth()` gained `wrinkle` + a free hanging hem (`hem_droop`, `hem_ties` → catenary droop
   between tie points + pleats); tea-stall main tarp 24×14 grid with deeper sag, front valance tied at the
   poles/sign that droops and ripples, torn striped-tarp corner; tea liquid darkened to real trà đá amber;
   umbrellas rebuilt as slack panels between ribs with a scalloped valance, stretcher struts, finial and runner;
   stall/market tarps denser with wrinkles + droopy front valances; `HipRoof.build(tile_m=…)` → miniature
   tiles on the shrines; stale files removed (`assets/models/landmarks` 40 → 16 MB).
3. In-engine tour (first Godot screenshots of the kit): everything imports and lights correctly; found the
   eave soffits reading as black wedges from the courtyard (dark wood × 0.55 tint) and the temple plaque's
   tone marks (ĐÌNH/HÀNG) vanishing at street distance; fixes: soffit tint 0.85, plaque re-set in Lora 600
   with a 2 px stroke; showcase made robust when `cat.glb` is mid-rebuild (scale-reference cat optional).

## Known gaps (honest)
- Roof colliders are 5 rotated slabs per roof plane following the mean slope; near the upturned corners
  the visible roof rises up to ~0.8 m above the collider (cat may appear to sink at the very corner tips).
  The ridge, hip-free middle of each plane and the eaves are accurate.
- Roof tiles are a textured curved surface + a tile-end row at the eaves, not individual tile meshes.
- Carved door panels / friezes are atlas relief (albedo + normal), not geometry.
- The banyan tree itself is not part of this kit (marker only; vehicles-nature).
- Lake water surface is not included (world); preview scenes use a simple transparent plane.
- Café/temple interiors are shallow sets (café 4.4 m, hall interior fully modelled but sparsely furnished).
- The incense smoke, candle flicker and lantern glow animation are left to world/FX.
- Cloth (tarps, umbrellas, valances) is static sculpted geometry with a procedural catenary hem — no wind
  animation (world could add a vertex-shader sway via `wind_strength`, but imported GLB materials are
  StandardMaterial3D). Tarp colliders are single tilted slabs, so a cat on a tarp stands on the mean plane.
- Glass tumblers use the shared alpha `glass_jar` material; in Cycles previews the iced tea still reads a
  little milky through it (fine in Godot's alpha blend).
- In-engine QA uses the showcase's own sky/sun/SDFGI, not the final `world` environment; the screenshots
  are lit flatter than the real city will be. The showcase's scale-reference cats are skipped whenever
  `assets/models/cat/cat.glb` fails to load (it was being rebuilt by cat-asset during session 2).
- The fascia band under the eaves is a plain wood strip (no individual tile ends on the small roofs).
