# Requests from ui

## street-props, vehicles-nature
- `data/i18n/requests/<area>.csv.import` uses `importer="csv_translation"`, so Godot builds stray
  `<area>.en/vi.translation` files next to it. They are harmless (only `strings.*.translation` are
  registered by `Settings`), but please switch the `.import` to `importer="keep"` (see
  `data/i18n/requests/systems.csv.import`) and delete the generated `.translation` files.
  Your keys ARE merged into `data/i18n/strings.csv`.

## world
- Weather display names: `WEATHER_CLEAR/CLOUDY/RAIN/STORM/FOG` are now yours alone (Title-case names
  from `world.csv`). The pause menu's in-sentence weather uses its own `PAUSE_WEATHER_*` keys.
- Optional: give `city.tscn` root a `map_bounds: Rect2` (XZ, metres) meta so the map capture is framed
  on the playable streets instead of every visual AABB (sky domes, far backdrops).

## lead (phase 2)
- `scenes/main/game.tscn`: instance `res://scenes/ui/hud.tscn` once (it hosts dialogue + all in-game
  menus). Boot scene is already `res://scenes/main/main.tscn`.
- After any area adds strings: `python3 scripts/ui/build/ui_strings.py && python3 scripts/ui/build/merge_i18n.py && tools/godot_import.sh`.
