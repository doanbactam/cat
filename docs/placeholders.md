# Placeholders in use

| Path | Owner | Replaced by |
|---|---|---|
| Procedural item stand-ins (runtime meshes in `PickupItem._procedural_visual`, used only when `assets/models/props/item_<id>.glb` is missing) | systems (code) / street-props (meshes) | `res://assets/models/props/item_<id>.glb` per items.json `mesh` — requested in docs/requests/systems.md |
