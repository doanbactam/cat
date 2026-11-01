# city-houses — old-quarter architecture kit

Owner area: `city-houses` · paths: `blender/city/`, `blender/lib/city_*.py`, `assets/models/city/`,
`assets/textures/architecture/`, `tests/test_city_houses.gd`.

Everything is generated procedurally (seeded) from Python: numpy/Pillow for textures and atlases,
headless Blender 5.2 for geometry, a Godot post-import script for materials/colliders/markers.
No hand-made binary sources — rerun the three commands below and you get the same kit.

## What was built

### Modules (catalog: `assets/models/city/catalog.json`, 52 entries)
19 distinct base modules, each house/shop module in 2–3 palette/clutter variants (separate GLBs,
`variant_of` in the catalog names the base):

| Base module | Style | W × D (m) | Floors | Variants | Notes |
|---|---|---|---|---|---|
| `colonial_2f_w4` | colonial | 4 × 12 | 2 | ochre, blue, yellow | rattan shop (Hàng Mây!) with hanging baskets/hats/trays, tile awning on cast-iron brackets, wrought-iron balcony, balustrade + pediment, pitched tile roof |
| `colonial_3f_w5` | colonial | 5 × 14 | 3 | pink, ochre, white | tea shop, rolling shutter, solid parapet + pediment, balconettes |
| `colonial_2f_w6` | colonial | 6 × 12 | 2 | yellow, blue | double-bay (gold shop + pharmacy), 3 French windows |
| `colonial_3f_w4_5` | colonial | 4.5 × 13 | 3 | ochre, green | phở shop, canvas awning, balconies on every floor |
| `colonial_corner_3f` | colonial | 6 × 10 | 3 | ochre, yellow | **corner building**: front + side facade + 45° chamfer with café entrance, roof terrace |
| `tube90s_4f_w4` | tube90s | 4 × 14 | 4 | blue, pink, green | grocery (tạp hóa) with sign on the balcony front |
| `tube90s_5f_w3_5` | tube90s | 3.5 × 12 | 5 | yellow, white, blue | skinny house, alternating cage-window / balcony floors |
| `tube90s_3f_w4_5` | tube90s | 4.5 × 13 | 3 | green, pink | phone-repair shop, **half-open shutter** (cat can slip under) |
| `tube90s_6f_w5` | tube90s | 5 × 16 | 6 | white, blue, yellow | mini-hotel (nhà nghỉ) with blade sign, lit sign |
| `tube90s_4f_w5` | tube90s | 5 × 15 | 4 | pink, green | hardware (kim khí) shop |
| `modern_5f_w4` | modern | 4 × 14 | 5 | white, grey | render frame, full-height dark-alu glazing, glass railings, ACP fin, planters, louvres |
| `modern_4f_w6` | modern | 6 × 15 | 4 | dark, white | garage shutter, pergola on roof |
| `oldtile_1f_w4` | old_tile | 4 × 10 | 1 | white, yellow, blue | single-storey, fish-scale tile roof, exposed rafters, 4-leaf wooden doors, gutter + downpipe |
| `oldtile_1f_w5_shop` | old_tile | 5 × 11 | 1 | yellow, white | bánh cuốn shop, plank doors stacked aside |
| `alley_wall_4m` | alley | 4 × 0.3, h 4.2 | – | grey, yellow | door + steps, meters, cables, ads |
| `alley_wall_6m_gate` | alley | 6 × 0.3, h 3.2 | – | green, brick | steel courtyard gate, bougainvillea over the wall |
| `alley_wall_8m` | alley | 8 × 0.3, h 6.8 | 2 | grey, yellow | 2 doors, laundry on brackets, windows w/ cages |
| `rear_wall_4f_w4` / `rear_wall_3f_w6` | wall | 4–6 × 0.3, h 10–14 | 3–4 | 2 each | block-interior back facades: small windows, cages, AC, corrugated hoods, pipes |
| `roofprop_*` | roof_prop | – | – | 8 | plank bridge, bamboo ladder, steel ladder, corrugated shed, alley cables (3 m), **street cables (13.5 m)**, tank on stand, solar heater |

Every house module includes the full visible shell: front facade, both party walls (exposed above
lower neighbours), detailed rear wall, and a **complete walkable roof**: flat terraces with
parapets, stair-head room ("tum") with door, stainless water tank (horizontal or vertical), solar
heater, TV antenna, styrofoam vegetable boxes/pots, laundry lines, corrugated sheds, ladders — or
pitched tile roofs with ridge caps, gable copings and verges (colonial / old_tile).

Facade clutter baked into the modules (all with colliders where a cat can stand): AC condensers on
L-brackets (fan grille, coil louvres, insulated pipes into the wall, dangling drain hose, drip stain
below), downpipes with clips (dog-leg around balconies, **climbable**), electricity meter cabinets,
cable bundles with sagging spans and vertical drops, laundry, potted plants, bougainvillea cascades,
trailing vines, security grilles (bars / diamond / sunburst) and projecting cages with corrugated
rain hoods, house-number plates, blade signs, shop signs (16 fictional Vietnamese signs), posters,
stencil ads ("KHOAN CẮT BÊ TÔNG"), "CẤM ĐỔ RÁC", grime streaks, water stains, moss at bases,
peeling paint, cement patches, cracks.

Ground floors: rolling steel shutters (open / half-open / closed, with housing, guide rails, bottom
bar, padlock lugs), wooden folding doors, shallow lit shop interiors (terrazzo floor, granite step,
shelves with goods, counters, phở pot, Thần Tài altar, fluorescent tube) so no opening is a flat
black plane; tile / corrugated / canvas awnings; steps and tiled thresholds.

### Material library (`assets/textures/architecture/`)
31 tileable PBR sets, 1024² each, `<set>_albedo.jpg` (sRGB), `<set>_normal.png` (OpenGL/Godot +Y),
`<set>_orm.jpg` (R AO, G roughness, B metallic); texel density 512 px/m (2 m tiles) or 1024 px/m
(1 m tiles); tile sizes in `materials.json`. All with built-in macro variation:
plaster_{ochre,blue,pink,white,green,yellow} (aged lime wash: two paint layers peeling to bare
plaster, repair patches, hairline cracks, efflorescence, rain streaks), cement_render,
concrete_weathered, brick_exposed (220×105×60 bricks, mortar, plaster remnants), tile_mosaic_{blue,green},
tile_ceramic_beige, tile_strip_brown (gạch thẻ), roof_tile_terracotta (interlocking, course lips,
lichen, moss), roof_tile_old (fish-scale ngói mũi hài), corrugated_{rusted,blue}, metal_painted,
iron_wrought, stainless (brushed), steel_shutter, acp_panel, wood_{teal,green,brown}
(painted/peeling/crazed or varnished), terrazzo, granite_red, render_modern, stucco_detail,
fabric_canvas, rattan (woven basketry).
Atlases (`atlases.json` has the UV rects): `signs_a.jpg` (16 shop signs, Inter Black condensed,
weathered), `signs_v.png` (blade signs, enamel house numbers, notices), `glass_interiors.jpg`
(8 interiors seen through glass), `goods_atlas.jpg` (16 shop-interior cells), `decals_grime.png`
(16 alpha decals), `foliage_atlas.png`, `laundry_atlas.png`. All text/brands are fictional.

## How to regenerate
```bash
python3 blender/city/gen_textures.py [--only plaster_ochre,...] [--sheet]   # ~3 min, PBR sets + materials.json
python3 blender/city/gen_atlases.py [--sheet]                              # ~30 s, atlases + atlases.json
tools/blender_run.sh blender/city/build_city.py [--only <id-prefix>,...] [--preview [all]]   # ~6 min, 52 GLBs + catalog
tools/godot_import.sh && tools/run_tests.sh city_houses
```
Texture-only changes need no Blender rebuild (GLBs reference the shared files by URI).
`build_city.py` also writes each GLB's `.import` (post-import script, LODs, shadow meshes);
texture `.import` presets (VRAM compressed, normal maps as RGTC) are written by the snippet in the
"Pipeline" section (`city_glb.texture_import_params`).
Preview renders: `--preview` → `qa/out/city-houses/<id>.png` (Cycles); in-engine QA scenes:
`assets/models/city/preview/street_row.tscn` (25 modules, 2 rows, cables, cat-scale reference) and
`alley_row.tscn` (alley + rear walls facing each other 2.6 m apart).

## Pipeline / API for other areas

**Module placement** — origin = front facade bottom-centre at sidewalk level, facade faces Godot +Z,
depth toward −Z, width along X. Modules of one row tile seamlessly when placed at
`x += width` (party walls coincide; nothing protrudes beyond ±width/2 except the front).
Rotate 180° for the opposite side of a street. `corner` modules have their side street on +X.

**catalog.json** — top-level JSON array; each entry has exactly the CLAUDE.md keys
(`id, file, kind, width, depth, height, floors, style, climb_points, nap_spots, entrances`, Godot
space relative to the origin) plus informational `variant_of`, `colliders`, `tris`.

**Inside each imported module** (done by `assets/models/city/_import/city_post_import.gd`):
- Nodes `<id>_shell`, `_detail`, `_clutter` (visibility_range_end 110 m), `_decals` (70 m, no shadows),
  `_foliage` (110 m). Materials are StandardMaterial3D; textures are shared resources.
- Colliders: `StaticBody3D` named `col_<surface>[_wall|_climb]_NNN`, each with **one exact
  `BoxShape3D`** (converted from the Blender boxes, incl. rotated ones for awnings/roofs/ladders).
  `collision_layer` = 1 (world); +6 (climbable, group `"climbable"`) for downpipes and ladders;
  +9 (camera_blocker) for big walls/shutters. `collision_mask` = 0. Metadata
  `surface: StringName` ∈ concrete, tile, metal, wood, roof_tile, fabric, plastic.
- Markers (Node3D): `NAP_NN` (group `city_nap_spot`), `CLIMB_NN` (`city_climb_point`),
  `ENTRANCE_NN` (`city_entrance`), and `LIGHT_SHOP_NN` → child `OmniLight3D` "ShopLight"
  (shadowless, 3.6 m, group `city_shop_light`).
- Night lighting hook: materials named `lit_*` (lit signs, lit windows, shop tubes) have emission
  enabled from their albedo texture; `lit_signs`/`lit_glass` ship with
  `emission_energy_multiplier = 0`, `lit_lamp` with 1.5 (shop tubes burn all day). Each has meta
  `night_emission_energy`; MeshInstance3D with such materials carry meta `night_emissive = true` —
  `world` can scale `emission_energy_multiplier` by `night_factor`.
- Vertex colours (`vertex_color_use_as_albedo`) carry baked macro variation: splash zone, soot
  under every ledge/AC/sill (computed from the actual ledge list), sun-bleached tops, soffit AO,
  tall rain-wash bands. World wetness modulation of albedo/roughness still works on top.

**Pipeline details** — `blender/lib/city_glb.py`: after the Blender glTF export each GLB is
rewritten so images reference `../../textures/architecture/<file>` by URI (no embedded copies: the
whole kit shares one set of textures in memory), TANGENT attributes are stripped (Godot regenerates
them, `meshes/ensure_tangents`), and alpha modes are enforced by material prefix (`dec_` blend,
`fol_` mask). `blender/lib/city_geo.py` = fast bmesh builder (per-face material, tint, UV mode;
world-scale box UVs per material tile size; smooth-by-angle + weighted normals);
`city_parts.py` = components; `city_mats.py` = Blender materials (albedo × vertex colour, ORM with
glTF occlusion output); `city_texlib.py` = periodic noise/feature synthesis.

## Tests
`tools/run_tests.sh city_houses` (5 tests): catalog contract (keys, types, kinds/styles, files exist,
≥14 distinct house/shop modules, all 4 styles), points inside module bounds, every module has only
box colliders with valid `surface` + vertex-colour materials + climbable colliders when it lists
climb points, **physics check that every nap spot has a collider 0–0.35 m below it and every climb
point touches a layer-6 collider** (ray / shape queries per module), and the street-row scene loads
with ≥ 8 modules.

## Known gaps (honest)
- **Main-project import is currently blocked by another area's files**: `qa/out/cat-asset/cache/*.blend`
  make headless `--import` abort for every pending file (request filed in
  `docs/requests/city-houses.md`). All verification above was done in a mirror project
  (symlinks to my asset dirs + scripts/tests/tools/data) — same files, separate `.godot` cache.
- Interiors are shallow "stage sets" (≤ 3.5 m deep shop, curtains/rooms behind glass via an atlas);
  upper floors are not enterable.
- Pitched-roof tiles are a stepped plane per course + normal map, not individual tile meshes; ridge
  caps are simplified tubes.
- Party walls are full height on both sides even where a neighbour hides them (cheap, but overdraw).
- No baked lightmaps/AO textures per module; ambient occlusion comes from vertex colours, ORM AO,
  SSAO/SDFGI in engine.
- Wrought-iron scrollwork is square-section tube geometry (reads well ≥ 1 m away; very close up it
  is a little coarse).
- The street-level ground, road, poles, trees, vehicles, NPCs in the preview scenes are stand-ins /
  absent (other areas own them).
