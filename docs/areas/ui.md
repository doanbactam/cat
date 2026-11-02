# Area: ui — menus, HUD, settings, scene loading, localisation

Art direction: "lantern, paper & ochre" — lacquer-black panels with gold hairlines, rice-paper
cards, lantern-red accents and ink-brush highlights; Playfair Display for titles, Be Vietnam Pro for
UI text, Lora for prose/dialogue (all OFL, full Vietnamese diacritics, see `assets/fonts/LICENSES.md`).
Vietnamese is the default language; every visible string goes through `tr()`.

## What exists

### Autoloads
| File | API |
|---|---|
| `scripts/autoload/settings.gd` (`Settings`) | Contract: `get_value(section, key, default)`, `set_value(section, key, value)`, `save()`, `apply_all()`. Extras: `load_settings()`, `sanitize()`, `get_default()`, `apply_quality_preset(level)`, `get_quality_preset_values(level)`, `detect_quality_preset()`, `reset_section()`, `reset_all()`, `is_dirty()`, `get_volume(bus_key)`, `get_action_events(action, gamepad)`, `rebind_action(action, event)`, `reset_bindings()`, `find_action_for_event()`, `is_using_gamepad()` + `signal input_device_changed(is_gamepad)`, `signal bindings_changed()`. Vars for tests/tools: `config_path`, `autosave_delay_s`, `apply_to_engine`. |
| `scripts/autoload/scene_loader.gd` (`SceneLoader`) | Contract: `change_scene(path, show_loading := true)`, `reload_current()`. Extras: `go_to_main_menu(skip_splash)`, `start_new_game()`, `continue_game(slot)`, `get_game_scene_path()` (`scenes/main/game.tscn`, falls back to `scenes/world/city.tscn`), `is_loading()`, `get_progress()`, awaitable `fade_out()/fade_in()`. Signals `load_started/load_progress/load_finished/load_failed/scene_changed`. |

**Settings** — `ConfigFile` at `user://settings.cfg`; defaults table = every contract key plus UI extras
(`graphics/anti_aliasing, fsr_sharpness, lod_bias, anisotropic, film_grain`, `controls/invert_x, vibration`,
`camera/auto_center`, `gameplay/subtitle_size, compass, text_speed, ui_scale, hud_opacity`, `input/*` bindings).
Values are clamped/validated (`RANGES`, `CHOICES`) on set and on load (hand-edited files are repaired).
Quality presets low/medium/high/ultra set render scale, upscaler, AA, SDFGI, SSR, SSAO, SSIL, volumetric fog,
fur shells, shadow quality, LOD bias, anisotropy; editing one of those keys turns quality into `custom`.
`apply_all()` applies window mode, vsync, max fps, render scale + FSR/FSR2 (viewport scaling 3D mode), MSAA/
FXAA/SMAA/TAA, shadow atlas sizes, LOD threshold, anisotropic filtering, audio bus volumes (Master/Music/SFX/
Ambience/UI), locale via `TranslationServer`, key bindings and UI scale, then calls `apply_graphics_settings()` on
group `graphics_settings_listener` and emits `GameEvents.settings_changed(section)` for every section.
Writes are debounced (2 s) and flushed on quit.

**SceneLoader** — fade to black → loading screen → `ResourceLoader.load_threaded_request` with progress →
swap `current_scene` → settle frames (shader compile/SDFGI) → fade in. Unpauses the tree before swapping.
A missing path emits `load_failed` and a toast; it never leaves the screen black.

### Scenes (`scenes/ui/`, `scenes/main/`)
| Scene | Script | Notes |
|---|---|---|
| `scenes/main/main.tscn` (boot) | `scripts/ui/main.gd` | splash → main menu over the live 3D backdrop; `mus_menu` + `amb_rooftop` |
| `splash.tscn` | `splash.gd` | studio "Xưởng Mái Ngói" (Roof-Tile Workshop): ink roof tiles, a cat on the ridge, rising moon; any input skips |
| `main_menu.tscn` | `main_menu.gd` | title + red seal, drifting lantern bokeh, ink-wash shade, Continue (latest slot summary) / New game (confirm if saves exist) / Load / Settings / Credits / Quit |
| `menu_backdrop.tscn` | `menu_backdrop.gd` | dusk rooftop built from the city-houses kit, lantern string with lights, haze; Cam (`cat.glb`, `sleep`/`lie_down`/`idle` anim + fur shells when the player fur script exists) on the parapet |
| `loading_screen.tscn` | `loading_screen.gd` | full-moon skyline, Cam's procedural silhouette (`cat_silhouette.gd`) balance-walks a lantern wire; lanterns light with progress; rotating tips |
| `hud.tscn` | `hud.gd` + `scripts/ui/hud/*` | see HUD below; also hosts dialogue box + all in-game menus |
| `dialogue_box.tscn` | `dialogue_box.gd` | name tag, speaker medallion (portrait or glyph), typewriter text (`gameplay/text_speed`), cat-action choice chips with glyphs, locked choices show the requirement |
| `pause_menu.tscn` | `pause_menu.gd` | menu + "Cam today" card (vitals, level, caps, tracked quest) |
| `inventory_screen.tscn` | `inventory_screen.gd` | category tabs, slot grid, detail page with actions (carry/put away/eat/use/wear), caps + buffs |
| `skill_tree_screen.tscn` | `skill_tree_screen.gd` | 5 trees of medallions with prerequisite ink lines, skill page (effects, requirements, cost, Learn), attributes with Raise |
| `journal_screen.tscn` | `journal_screen.gd` | Quests (active/completed, objectives, rewards, Track) / Memories (12 photos) / Places / Cam (attributes, reputation, achievements) |
| `map_screen.tscn` | `map_screen.gd` + `map_capture.gd` + `shaders/paper_map.gdshader` | runtime orthographic SubViewport capture of the current world → ink-wash on rice paper; Cam arrow, quest target, places, home; pan/zoom/centre |
| `settings_menu.tscn` | `settings_menu.gd` | tabs Graphics (preset + every toggle) / Audio / Controls (sensitivities, invert, rebinding list for KB/M and pad with conflict warnings) / Gameplay (language, subtitles + size, hints, compass, text speed, UI scale, HUD opacity, default camera, head bob); help column |
| `save_slots.tscn` | `save_slots_screen.gd` | autosave + 3 manual slots with `GameState.get_save_info()` summaries; overwrite/delete confirm |
| `credits.tscn` | `credits_screen.gd` | scrolling rice-paper credits, licences, walking cat |
| — | `confirm_dialog.gd` (`UIConfirmDialog.make(title_key, body_key, danger)`) | "No" has default focus |

Framework: `UIScreen` (base, frame/tab helpers, open/close animation) pushed on a `UIMenuHost` (stack, Esc/B back,
Q/E or LB/RB tabs, focus memory, `GameEvents.ui_menu_opened/closed`, UI sounds). `UIStyle` (palette, fonts, theme,
icon/texture loaders, `sfx()` → `AudioManager.play_ui`, silent if missing). `UIInputGlyph` draws key caps, mouse or
Xbox-style pad buttons for any action and switches on `Settings.input_device_changed`. `UIHintBar` footer hints.
`UISelector` ‹ option › picker.

### HUD (`scenes/ui/hud.tscn`, CanvasLayer 10; dialogue 15; menus 20)
- **Vitals** (`vital_ring.gd`, `status_cluster.gd`): four rings health/hunger/energy/warmth, fade out when full and
  unchanged, pulse when low; buff glyphs; mouth-item card; level badge + XP bar with floating +XP; caps counter.
- **Compass** (`compass.gd`): heading from the active camera, ticks/letters (localised), tracked quest target via
  `QuestManager.get_tracked_target_position()` with distance (edge-clamped), discovered `location` markers, home.
- **Quest tracker** (`quest_tracker.gd`), **toasts** (`toasts.gd`, `GameEvents.notify`; item ids show the item art),
  **banners** (location discovered / new quest), **celebrations** (level-up, quest complete seal),
  **interaction prompt** (`prompt.gd`, glyph auto-switches KB/pad), **subtitles** (`subtitle_requested`),
  save indicator (`game_saved`).
- Input handled: `pause`, `inventory`, `journal`, `map`, `quick_save`, `quick_load`. Opening a menu pauses the tree
  and emits `pause_requested(true)`; HUD fades during dialogue and on `hud_visibility_requested(false)`.
- `hud.open_screen(id)`, `close_all_menus()`, `is_menu_open()`; public widget refs `status, compass, tracker, toasts,
  banner, celebration, prompt, subtitles, dialogue, host`.

### Theme, fonts, icons, textures
- `assets/ui/theme.tres` — generated by `scripts/ui/build/build_theme.gd` (type variations listed in its header).
- `assets/fonts/` — Be Vietnam Pro (300–700), Playfair Display (400–700), Lora (400/600) — OFL.
- `assets/ui/icons/{glyphs,actions,items,skills}/*.png` — hand-authored SVG (`gen_icons.py` writes the sources to
  `assets/ui/icons/src/`), rasterised by Godot (`rasterize_icons.gd`). Items follow systems' request
  (`items/<item_id>.png`, `memory_photo.png`, `skills/<skill_id>.png`, `tree_<tree>.png`).
- `assets/ui/textures/*.png` — painted panels, paper grain, lacquer, brush highlights, seals, map paper, controls
  (`gen_ui_textures.py`, numpy/Pillow).

### Localisation
- UI strings: `scripts/ui/build/ui_strings.py` (source of truth) → `data/i18n/requests/ui.csv`.
- **Merge procedure** (run after any area adds keys):
  `python3 scripts/ui/build/ui_strings.py && python3 scripts/ui/build/merge_i18n.py && tools/godot_import.sh`
  `merge_i18n.py --check` reports without writing. Rules: columns `keys,en,vi`; ui.csv wins conflicts, then
  alphabetical area order; conflicting definitions are reported; keys present only in `strings.csv` are kept;
  missing translations fall back to the other language and are reported. Request CSVs must have an `.import`
  with `importer="keep"` so Godot does not build translations from them.
- Current merge: ui 475 + systems 413 + player 7 = 895 keys, 0 problems.

## Regenerate
```bash
python3 scripts/ui/build/gen_ui_textures.py
python3 scripts/ui/build/gen_icons.py && tools/godot_lock.sh godot --headless --path . --script res://scripts/ui/build/rasterize_icons.gd </dev/null
tools/godot_lock.sh godot --headless --path . --script res://scripts/ui/build/build_theme.gd </dev/null
python3 scripts/ui/build/ui_strings.py && python3 scripts/ui/build/merge_i18n.py
tools/godot_import.sh
```

## QA / verification
- `tools/run_tests.sh test_ui` — `tests/test_ui_settings.gd` (defaults, persistence round trip, sanitising of
  bad values/files, presets, custom detection, signals + graphics listeners, translations, strings.csv integrity),
  `tests/test_ui_hud.gd` (all widgets, prompt, toasts, banner/level-up, vital rings, mouth item, subtitles, quest
  tracker, full dialogue run with a locked choice, menu pause/resume), `tests/test_ui_menus.gd` (every screen builds
  with keyboard/pad focus, settings tabs, menu stack + back + confirm, boot menu, loading screen, threaded
  SceneLoader change + graceful failure).
- Screenshot harness (not gameplay): `scenes/ui/qa/ui_gallery.tscn` builds a believable game state from the
  story fixtures over the rooftop backdrop and opens one screen:
  `tools/screenshot.sh scene=res://scenes/ui/qa/ui_gallery.tscn out=/abs.png frames=40 screen=<id> [lang=en]`
  with `<id>` ∈ menu, splash, loading, hud, hud_events, dialogue, pause, inventory, skills, journal,
  journal_memories, map, settings, settings_audio, settings_controls, settings_gameplay, save_slots, credits,
  confirm. `scenes/ui/qa/loader_probe.tscn` is the SceneLoader test target.
- Captures in `qa/out/ui/` (v2 = this pass); best in `docs/gallery/ui_*.jpg`.

## For other areas
- **lead / phase 2**: instance `res://scenes/ui/hud.tscn` once in `scenes/main/game.tscn`; boot scene is
  `res://scenes/main/main.tscn` (should be `run/main_scene`). Input actions used: `pause`, `inventory`, `journal`,
  `map`, `quick_save`, `quick_load`, `interact`, plus `ui_*`.
- **world**: give `city.tscn` root meta `map_bounds: Rect2` (XZ) for a tight map capture; otherwise visual AABBs are used.
- **systems**: notify icons understood: quest, objective, skill, achievement, memory/collectible, territory, health,
  hunger, energy, warmth, faint, save, item, caps, warning, info, any glyph name, or any item id.
- Portraits: `res://assets/ui/portraits/<npc_id>.png` are used when present (dialogue medallion), else a glyph.

## Known gaps (honest)
- No NPC portraits yet (NPC models not built) — the dialogue medallion draws a species glyph instead.
- The menu backdrop plays `cat.glb`'s `sleep` loop; in captures Cam reads as a sphinx lie with head up rather
  than a tight curl (the cat asset approximates the curl) — fine at menu distance, not a hero shot.
- Map uses the menu backdrop / whatever world is loaded; with no `city.tscn` yet the real city map is untested.
- Rendering-heavy screens were verified at 1600×900 and 1280×720 under lavapipe only; no real-GPU pass.
- Gamepad navigation is verified via focus neighbours and tests, not with physical hardware.
