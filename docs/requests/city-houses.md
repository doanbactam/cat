# Requests from city-houses

## 1. RESOLVED (lead added qa/.gdignore + import/blender/enabled=false) — headless import aborted on stray .blend files
`qa/out/cat-asset/cache/*.blend` (cat-asset scratch files) make `tools/godot_import.sh` print
`ERROR: Blender path is invalid or not set ... Cannot configure blender path in headless mode`
and then **no pending file is imported at all** (148 files stayed un-imported in my test, incl. every
new .glb/.png/.ogg of all areas). Any one of these fixes it:
- add `qa/.gdignore` (or `qa/out/.gdignore`) — qa/ is git-ignored scratch anyway (lead), or
- cat-asset adds `qa/out/cat-asset/.gdignore`, and/or
- `project.godot`: `[filesystem] import/blender/enabled=false` (we never import .blend directly).
city-houses already ships `qa/out/city-houses/.gdignore`.
