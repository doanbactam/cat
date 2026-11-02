# Placeholders in use

| Path | Owner | Replaced by |
|---|---|---|
| Procedural item stand-ins (runtime meshes in `PickupItem._procedural_visual`, used only when `assets/models/props/item_<id>.glb` is missing) | systems (code) / street-props (meshes) | `res://assets/models/props/item_<id>.glb` per items.json `mesh` — requested in docs/requests/systems.md |
| Procedural water tower (`scripts/world/city_structures.gd::make_water_tower`, placed by `city_builder.gd` when no landmarks catalog entry matches `water_tower`/`thap_nuoc`) | world (code) / city-landmarks (asset) | `assets/models/landmarks/` entry with id containing `water_tower` — the builder picks it up on the next `build_city.gd` run (catwalk height from meta `catwalk_y`) |
