# Requests from city-landmarks

All landmark GLBs live in `assets/models/landmarks/` (catalog: `catalog.json`, same shape as the city
catalog plus `markers`, `zones`, `origin`, `category`). Marker positions in the catalog are Godot-space,
relative to each module's origin (rotate with the instance).

## world (layout + env)
1. **Placement / origins** (per catalog `origin` field):
   - `dinh_hang_may` — origin is the street-front centre of the tam quan gate; the complex extends 37 m
     toward -Z (26 m wide). Put it on PHỐ ĐÌNH facing the street (+Z = street).
   - Lake pieces: water side = +Z of each piece, origin on the top water-side edge at walkway level.
     Walkway y = 0, **water surface y = -1.0**, lake bed y = -1.6. Straight / steps pieces tile every 4 m
     along X; `ho_embank_curve_30` chains every 30° (radius 8 m, centre 8 m out over the water).
     `ho_railing_4m` sits on top of a straight piece with the same transform. Example layout:
     `assets/models/landmarks/preview/landmarks_showcase.gd` (`_layout()`).
   - `ho_bridge` midpoint at walkway level spans Z -8.8..8.8 (incl. abutments); `ho_islet_shrine` centre
     11.6 m from the bridge midpoint along the bridge axis (islet landing = +Z side of the islet).
   - `quan_tra_ba_tu` leans on a building wall 2.8 m behind its front edge (alley mouth on PHỐ HÀNG MÂY);
     `cafe_bong` is a 6 m city-compatible shop module (tiles with city rows).
2. **The lake water surface** is not part of the kit (your water shader). Water level -1.0 matters for the
   steps landing (-0.85) and the algae band on the embankment texture.
3. **Night lighting**: drive `OmniLight3D` nodes in group `landmark_night_light` (energy 0 by day, meta
   `night_energy`) and materials on MeshInstance3D with meta `night_emissive` (meta
   `night_emission_energy` on each `lit_*` material) with `night_factor` — the showcase's `_light_up()`
   shows the expected behaviour. `lit_lamp` (altar candles) is always on.
4. **Location markers** (`location` group) are yours; suggested positions from the catalog markers:
   `temple_roof` = `MARKER_temple_roof`, `banyan` = `MARKER_banyan`, `tea_stall` = `MARKER_tea_stall`,
   `riddle_bridge` = `MARKER_riddle_bridge`, `riddle_bell` = `MARKER_bell`.
5. **Interactables** suggested anchors: Grandma's bowl FoodSource at `MARKER_bowl`, `stall_counter`
   sniff Interactable at `MARKER_stall_counter`, fish stall FoodSource (`gives_item = fish`,
   `is_stealing = true`) at `MARKER_fish_stall`, a NapSpot on `MARKER_cam_bed` (Cam's cardboard bed under
   the counter) and on `MARKER_bong_spot` (café window cushion), PickupItem `lucky_cat_figurine` in the nest
   at `QUEST_crow_nest` (already in group `quest_target`, `target_id = crow_nest`).
6. `NavRegion` should include the temple courtyard (y≈0.02), the hall platform (+0.75 via the steps),
   the market floor (+0.12) and the lake promenade.

## vehicles-nature
- **Big banyan** for the temple courtyard: planter at `MARKER_banyan` (Blender (-7.5, 9) → Godot
  (-7.5, 0.42, -9) relative to the temple origin), kerb radius 2.0 m, soil top at y = 0.42. Aerial
  roots may hang over the wall coping (2.55 m) — the cat uses the wall top as a path.
- A second banyan / old tree at the lake's south shore is expected by the story (Lão Quạ's meeting spot);
  the islet already has a small frangipani modelled in.

## world-life
- NPC spawn hints in the catalog: `MARKER_grandma` (tea stall, behind the counter), `MARKER_fish_stall`
  (cô Hoa, in front of her counter), `MARKER_pigeons` (islet), `MARKER_bong_spot` (Bông).
- The market hall has walkable truss bottom chords at y = 5.2 (Vện cannot follow there).

## audio
- Reverb `Area3D`s ship inside the GLBs: `Temple` (hall interior), `Market` (whole hall), `Interior`
  (café ground floor); collision layer 10, monitoring off.
