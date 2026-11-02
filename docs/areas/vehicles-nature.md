# Area: vehicles-nature

Vehicles (8 + 2 helmets) and vegetation (8 trees/palms/bamboo + 13 small plants) for Phố Cũ Hàng Mây,
all generated procedurally (Blender 5.2 Python + numpy/Pillow texture painters), exported to GLB and
wired into Godot through post-import scripts and shared materials.

## What exists

### Nature — `assets/models/nature/<id>.glb`, catalog `assets/models/nature/catalog.json`
| id | kind | notes |
|---|---|---|
| `banyan` | tree | cây đa: 15 × 17 m crown, 11 m tall, buttressed fused-root trunk (r 1.15 m, 7 lobes), 8 spreading limbs, ~45 hanging aerial roots + 5 lignified prop roots reaching the ground (climbable colliders), root-fringe cards, fig sprigs. 7 nap spots (trunk crotch + thick limbs), 4 climb points. |
| `flame_tree` | tree | phượng vĩ: 3.4 m trunk, umbrella crown 11 m, bipinnate frond cards + scarlet flower clusters. 5 nap spots. |
| `sao_tree` | tree | sao đen street tree, 12.8 m, straight furrowed trunk, high narrow crown (clearance for traffic). |
| `frangipani` | tree | hoa sứ: 3.5 m, true candelabra (4 fork levels, every fork at the blunt tip of the previous succulent branch, ~40 tips) carrying leaf rosettes + white/yellow flower clusters. |
| `coconut_palm`, `areca_palm` | palm | curved ringed trunks, 20/10 fronds built as rachis tube + two V-angled half-frond leaflet strips, coconuts / green crownshaft. Climbable trunks. |
| `weeping_willow` | tree | liễu rủ for the lake: leaning furrowed trunk, arching limbs with negative gravitropism, long hanging strand cards (1.2–2.1× atlas size) with randomised facing so the curtain stays see-through. |
| `bamboo_clump` | bamboo | 24 culms 6–9.5 m with node rings, arching, leaf sprigs at nodes; clump-base collider (not climbable). |
| `shrub_ixora`, `hedge_trimmed` | shrub | ixora with red flower heads; trimmed hedge (box collider, nap spot on top). Dark inner core mesh hides see-through gaps. |
| `bougainvillea_wall`, `bougainvillea_cascade` | climber | magenta hoa giấy trained up a wall (back of plant at +Z… wall behind, origin at wall foot) and cascading from a rail (origin = rail top). |
| `fern_clump`, `grass_tuft_a/b`, `weeds_crack_a/b`, `moss_patch` | groundcover | small cards; meshes named `small_*` get a 45 m visibility range. Weeds are laid along X for cracks / wall feet. |
| `leaf_litter` | litter | 140 curled single-leaf quads (decal-like, no shadows). |
| `lotus_cluster`, `water_hyacinth` | aquatic | origin = water surface. Floating + emergent lotus leaves on petioles, open flowers (3 petal rings, seed pod, stamens) and a bud; floating hyacinth rosettes with lavender spikes. |

### Vehicles — `assets/models/vehicles/<id>.glb`, catalog `assets/models/vehicles/catalog.json`
All original, unbranded designs (fictional makers "SAOLA", "SÓC 110", "HẠC 125"; fictional plates;
"TAXI HÀNG MÂY", "GIAO NHANH PHỐ CŨ" liveries; repair-shop sticker "SỬA XE CHÚ SÁU").
| id | size L×W×H (m) | tris | wheels |
|---|---|---|---|
| `scooter_auto` (retro automatic scooter, cast 14" wheels, disc brake) | 1.90 × 0.83 × 1.31 | ~10 k | wheel_front, wheel_rear |
| `underbone_step` (step-through 110, spoked 17", chrome rack) | 1.95 × 0.81 × 1.30 | ~10 k | wheel_front, wheel_rear |
| `manual_classic` (old two-stroke standard, cradle frame, finned engine, rust) | 1.96 × 0.88 × 1.38 | ~11 k | wheel_front, wheel_rear |
| `bicycle_city` (26" step-through, basket + rack) | 1.80 × 0.69 × 1.10 | ~8 k | wheel_front, wheel_rear |
| `cyclo` (xích lô: passenger tub in front, rider behind) | 2.28 × 0.96 × 1.12 | ~11 k | wheel_front_L, wheel_front_R, wheel_rear |
| `cargo_trike` (pedal ba gác, wooden bed + rice sacks) | 2.57 × 1.13 × 1.10 | ~11 k | wheel_front, wheel_rear_L, wheel_rear_R |
| `taxi_hatch` (5-door hatchback taxi: one lofted shell with window openings on edge loops, painted A/B/C pillars, tinted glass, door/bonnet/hatch shut lines, projected lamps/grille/handles/fuel flap, wrap bumpers, roof sign, interior) | 3.86 × 1.92 (mirrors) × 1.69 | ~18.6 k | wheel_front_L/R, wheel_rear_L/R |
| `delivery_van` (cab-over 1-tonne panel van: driver above the front axle, sliding side door, twin rear doors with hinges, roof rails, big mirrors on arms, livery) | 4.74 × 2.07 × 2.04 | ~18 k | wheel_front_L/R, wheel_rear_L/R |
| `helmet_half`, `helmet_open` | 0.29 × 0.34 × 0.17/0.20 | ~1.7 k | — (dynamic props, mass 0.45 / 0.9 kg) |

## Runtime API / contracts
* **Wheels**: MeshInstance3D children named as above, origin at the hub, spin about **local X**
  (`wheel.rotate_x(distance / radius)`), group `vehicle_wheel`. Catalog `wheels: [{node, radius, position}]`,
  `wheel_spin_axis: "x"`.
* **Seats**: empties `SEAT_<role>` (group `vehicle_seat`, meta `seat_role`), and catalog `seat` (main rider /
  driver, Godot coords relative to origin) + `seats {role: [x,y,z]}` + `rider_pose` (scooter|motorbike|bicycle|car).
  Left-hand-drive (Vietnam): driver at x = −0.36/−0.4.
* **Nap spots** (cats sleep on scooter seats, car roofs/hoods, the hedge top, tree forks/limbs): catalog
  `nap_spots` + empties `NAP_*` (groups `vehicle_nap_spot` / `nature_nap_spot`). Every nap spot is physically
  supported by a collider (tested).
* **Climb points**: tree / palm trunks; every point touches a layer-6 climbable collider (tested).
* **Colliders**: `col_<surface>[_climb]_*` convex bodies. Nature: layer 1 world (+6 climbable), group
  `climbable`. Vehicles: layer 8 `vehicles`; helmets: layer 4 `props_dynamic` (root meta `dynamic`, `mass`).
  All bodies carry meta `surface` (wood, grass, metal, plastic, fabric).
* **Lights**: vehicle lamp materials have emission on at energy 0 and the MeshInstance has meta
  `vehicle_lights = true`; world-life can raise `emission_energy_multiplier` on a duplicated material at night.
  Real light nodes: every head/tail lamp lens gets an empty `LIGHT_head_<i>` / `LIGHT_tail_<i>` (group
  `vehicle_light_mount`) with a child `HeadLight` (SpotLight3D, aimed along +Z and 7° down, range 22 m) or
  `TailLight` (OmniLight3D, red, 2.2 m). They start `visible = false`, energy 0, in group `vehicle_light`,
  meta `night_energy` (6.0 / 1.2) and `light_kind`. Catalog: `lights: [{node, kind, position}]`.
  Switch on: `for l in vehicle.find_children("*", "Light3D"): l.visible = true; l.light_energy = l.get_meta(&"night_energy")`.
* **Wind** (all plants): vertex colour COLOR R = sway weight, G = phase, B = flutter. The shared shaders
  `assets/models/nature/shaders/nature_foliage.gdshader` / `nature_bark.gdshader` (+ `nature_wind.gdshaderinc`)
  read the project globals `wind_strength`, `wind_direction`, `wetness` — no per-instance setup needed.
  Materials: `assets/models/nature/materials/*.tres` (one per atlas / bark, shared by all plants).
  Bark: moss on upward faces near the ground, rain darkening/gloss. Foliage: alpha scissor, translucency
  (BACKLIGHT from a painted translucency map), per-instance hue variation, wetness.
* Vehicle materials: `assets/models/vehicles/materials/*.tres` (ORMMaterial3D). Paint = clearcoat;
  vertex colour `vc` (baked AO + mud rising from the wheels/underside) multiplies albedo.

## How to regenerate
```bash
python3 blender/nature/gen_textures.py            # leaf/flower atlases + bark sets  -> assets/textures/nature/
python3 blender/nature/write_materials.py         # .tres + texture .import presets
tools/blender_run.sh blender/nature/build_trees.py  [-- banyan ... --nopreview]
tools/blender_run.sh blender/nature/build_plants.py [-- lotus_cluster ...]
python3 blender/vehicles/gen_textures.py          # paint/metal/rubber/vinyl/... + decal atlas -> assets/textures/vehicles/
python3 blender/vehicles/write_materials.py
tools/blender_run.sh blender/vehicles/build_vehicles.py [-- taxi_hatch ...]
tools/godot_import.sh && tools/validate.sh "" assets/models/nature && tools/run_tests.sh vehicles_nature
```
Builders merge their entries into the catalogs, so single assets can be rebuilt. Blender previews land in
`qa/out/vehicles-nature/` (cars also get a `_front.png` low front 3/4 view). Godot showcases (shared daylight
environment `assets/models/nature/preview/showcase_env.gd`: AgX, SSAO/SSIL/SSR, procedural sky, textured ground):
* `assets/models/nature/preview/nature_showcase.tscn` — every plant in rows (QA lineup);
* `assets/models/nature/preview/nature_garden.tscn` — composed courtyard vignette (banyan, frangipani, bamboo,
  palms, bougainvillea on a wall, hedge/ixora/ferns, kerb weeds, grass, moss, litter, lotus pond + willow);
* `assets/models/vehicles/preview/vehicles_showcase.tscn` — every vehicle in a row + helmets;
* `assets/models/vehicles/preview/vehicles_street.tscn` — parked street: scooters nose-out on the pavement,
  bicycle, helmets, taxi + van at the kerb, cyclo and cargo trike in the lane.

Cat-eye screenshots (cat eye height 0.22 m):
```bash
SKIP_IMPORT=1 tools/screenshot.sh scene=res://assets/models/nature/preview/nature_garden.tscn out=$PWD/qa/out/vehicles-nature/garden_eye.png frames=40 size=1280x720 cam=0.4,0.22,4.6 look=-0.5,1.6,-6
SKIP_IMPORT=1 tools/screenshot.sh scene=res://assets/models/vehicles/preview/vehicles_street.tscn out=$PWD/qa/out/vehicles-nature/street_eye.png frames=40 size=1280x720 cam=-2.6,0.37,6.8 look=1.5,0.7,2.0
```

Code: `blender/lib/nature_tree.py` (recursive generator with gravitropism/phototropism, parallel-transport
sweeps, cards, colliders), `nature_atlas.py` (atlas layout shared by painter and generator),
`nature_paint.py` (analytic leaf painter), `nature_godot.py` (export / .import / .tres / catalog),
`vehicles_lib.py` (lofts, lathes, tubes, wheels/tyres, decals, wear bake), `vehicles_decals.py`,
`vehicles_car.py` (car shell generator: key stations → Catmull-Rom interpolated cross-sections with named
bands (sill, belt moulding, glass, roof rail, roof) so windows/pillars fall on edge loops; BVH-projected
detail patches (lamps, grilles, handles, decals) and panel-gap ribbons that follow the curved panels).

## Known gaps (honest)
* Tree generator is recursive (not space colonisation). Crowns read well from street level, but up close
  in first person the leaf cards are visibly flat planes and branch joints are simple overlaps (no welded
  junction geometry).
* No dedicated LOD meshes / impostors: Godot's importer auto-LOD is enabled; far banyans are still ~36 k tris.
* Vehicles have no separate steering node (front fork/handlebar are part of `body`), no doors that open,
  interiors are simple (seats, dash, console, steering wheel, parcel shelf) — readable through the tinted
  glass but not first-person quality. Panel gaps are thin dark ribbons, not cut geometry.
* Lights are created hidden; nothing in this area switches them on (world-life / world decide when).
* Wear (mud/AO) is per-vertex, so it is soft; there are no texture-space scratches beyond the tiling sets.
* Helmets have no chin-strap physics.
