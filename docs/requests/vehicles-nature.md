# Requests from vehicles-nature

## To `world` (layout + env)
1. Vegetation placement (catalog `assets/models/nature/catalog.json`): giant `banyan` at the lake islet and in
   the Đình courtyard (GDD), `weeping_willow` + `lotus_cluster` + `water_hyacinth` on the lake (origin = water
   surface), `flame_tree` / `sao_tree` as street trees (sao crown starts ~6 m, clears traffic), `frangipani` in the
   temple courtyard, `areca_palm`/`coconut_palm`/`bamboo_clump` in courtyards, `bougainvillea_wall` against walls
   (plant front faces +Z, wall behind it) and `bougainvillea_cascade` on balcony rails (origin = rail top),
   `weeds_crack_*`/`moss_patch`/`grass_tuft_*` along kerbs and wall feet, `leaf_litter` under trees.
2. Wind: the plant shaders read the existing globals `wind_strength`, `wind_direction`, `wetness`
   (`assets/models/nature/shaders/nature_wind.gdshaderinc`). Please animate `wind_strength` (gusts 0.2–0.8,
   storms > 1) from the weather system; nothing else is needed. If `world` wants to own foliage shaders under
   `shaders/`, feel free to copy these — keep the vertex-colour convention (R sway, G phase, B flutter).
3. Mark `banyan`/`flame_tree` crowns as `shelter` areas if rain should not wet the cat under them.

## To `world-life` (traffic / NPC)
1. Vehicles: `assets/models/vehicles/catalog.json`. Wheels are nodes `wheel_*` (group `vehicle_wheel`), spin about
   local X: `w.rotate_x(speed * delta / radius)`. Seats: `SEAT_<role>` empties (group `vehicle_seat`, meta
   `seat_role`) + catalog `seats`/`rider_pose`. Colliders are on layer 8 `vehicles` (static bodies — wrap the
   instance in an AnimatableBody3D / move the scene root for traffic).
2. Lights: MeshInstances with meta `vehicle_lights` use `veh_light_head/tail/amber` (emission energy 0). For
   headlights at night duplicate the material on that instance (`set_surface_override_material`) and raise
   `emission_energy_multiplier` (~3–6), optionally add a SpotLight3D.
3. Parked scooters with `NAP_seat` are good cat nap spots (catalog `nap_spots`).

## To `ui`
Strings appended in `data/i18n/requests/vehicles-nature.csv` (catalog `name_key`s).
