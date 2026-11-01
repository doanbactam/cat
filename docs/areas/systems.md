# Area: systems — RPG core

Owner paths: `scripts/autoload/{game_state,time_of_day,quest_manager,dialogue_manager}.gd`,
`scripts/systems/`, `data/items/`, `data/skills/`, `data/quests/_schema.md`,
`data/dialogue/_schema.md`, `tests/fixtures/`, `tests/test_systems*.gd`,
`data/i18n/requests/systems.csv`.

Pure GDScript (Godot 4.7, static typing), data-driven via JSON. No visual assets of its own —
the only rendered output is the QA sandbox (`tests/fixtures/systems_sandbox.tscn`).

## What was built

| Piece | File | Summary |
|---|---|---|
| GameState | `scripts/autoload/game_state.gd` | Vitals simulation, attributes, XP/levels, skills + modifier system, inventory with mouth slot, equipment, buffs, flags, reputation, locations/collectibles/territory/naps, counters + achievements, faint & revive, trading, versioned JSON save/load with providers. |
| TimeOfDay | `scripts/autoload/time_of_day.gd` | Clock, phases, day counter, `sleep_until`, `skip_hours`, festival day, moon phase, sun progress/elevation, night factor, pause stack. |
| QuestManager | `scripts/autoload/quest_manager.gd` | Data-driven quests: 13 objective types, stages, optional/hidden, `when`/time-window gating, prerequisites, rewards, chaining, auto-start, fail conditions, tracking + target marker resolver, delivery, save provider. |
| DialogueManager | `scripts/autoload/dialogue_manager.gd` | JSON dialogue graphs: conditional entries, branches, once-nodes, cat-action choices (locked/hidden/once), effects, speaker hooks, rich UI signal, save provider. |
| GameConditions / GameEffects | `scripts/systems/{conditions,effects}.gd` | Shared condition evaluator (30 keys, comparators, any/all/not, human-readable `describe()`, validation) and effect executor (33 effect types + if/then/else, validation). |
| Interactables | `scripts/systems/*.gd` | `Interactable` base + `PickupItem`, `Talkable`, `NapSpot`, `FoodSource`, `ScratchPost`, `TerritorySpot`, `QuestTrigger`, `Collectible`, `Pushable` (RigidBody3D). |
| Data | `data/items/items.json` (37 items), `data/skills/skills.json` (26 skills / 5 trees, 6 buffs, 45 modifier specs) | |
| Docs | `data/quests/_schema.md`, `data/dialogue/_schema.md` | Formats with examples (examples are machine-validated by tests). |
| Strings | `data/i18n/requests/systems.csv` | 413 keys, EN + VI (items, memory stories, skills, prompts, notifications, requirements, cat actions, NPCs, locations, story quests & dialogue). |
| Story (proposed content) | `tests/fixtures/story/` | Full GDD main story (5 chapters) + 6 side quests + 8 NPC dialogues, played end-to-end by `tests/test_systems_story.gd`. See docs/requests/systems.md (lead) to ship it. |
| Tests | `tests/test_systems_*.gd` (10 files, 130 tests) + `tests/fixtures/` (fixture quests/dialogues, story, test base, QA sandbox) | |

## How to regenerate / verify
- Data files are hand-authored JSON; `items.json`/`skills.json` were generated once by small
  Python snippets but are now the source of truth — edit them directly.
- `tools/validate.sh "" scripts` and `tools/validate.sh "" tests` — parse/load check.
- `tools/run_tests.sh test_systems` — all systems tests (≈ 40 s, includes real Jolt physics).
- `tools/screenshot.sh scene=res://tests/fixtures/systems_sandbox.tscn out=$PWD/qa/out/systems/x.png frames=90 size=960x540 call=demo_knock`
  — every interactable with live Vietnamese prompts; `demo_knock` swipes the cups off the table.

## Design & tuning

### Vitals (per GAME hour; 1 game h = 1 real min at `time_scale` 1)
| Activity | hunger drain | energy |
|---|---|---|
| idle | 1.0 | −0.6 |
| rest (sit/lie/groom) | 0.8 | +3 |
| walk / trot | 1.25 / 1.5 | −1.5 / −2.5 |
| run (sprint, jump) | **2.0** (≈1/h more) | −6 × sprint_energy_mult |
| sneak / climb / swim | 1.2 / 1.8 / 2.2 | −1.6 / −5 / −9 |
| sleep | 0.6 | **+25** × energy_regen × comfort (×1.1 sheltered, ×0.5 if starving, ×0.7 if soaked) |

- Jump −(0.3 + 0.4·charge); cat-sense toggle −1.5 × cat_sense_cost.
- Energy drains ×1.4 when cold (<30 warmth), ×1.3 when hungry (<15).
- **Wetness** 0..1: rises by `rain·1.6·wet_rate`/h when exposed (rain = intensity, storm = 1.5×,
  0 in a `shelter` area); dries at 0.45/h (+0.6 sheltered, +0.4 asleep, +0.5 sunny day).
  `soak()` on water landings, `groom()` −0.15.
- **Warmth**: wet & exposed −(4 + 14·wet)·(1.3 at night)·warmth_drain; wet & sheltered −1·wet;
  dry +6 (+10 asleep, +2 sheltered, ×0.6 exposed at night).
- **Health**: +2/h × health_regen (×2 asleep) when hunger > 40 and warmth > 30; −4/h starving;
  −3/h freezing (warmth ≤ 5); `player_damaged` applies directly.
- **Faint** when health or energy hits 0: lose `ceil(10% caps × faint_cap_loss_mult)` (max 15;
  first faint of the day free with *Chín mạng*), `faint_hours` (3) pass, wake at the last nap
  spot (else `PlayerSpawn`) with ≥35% health, ≥40 energy, ≥50 warmth, ≥25 hunger.
- Low vitals: speed-type modifiers × vitals factor (energy<15 → ×0.75–0.9, hunger<15 ×0.9,
  warmth<25 ×0.92, health<25 ×0.85, × carried item `carry_speed`), noise-type × up to 1.25·1.1·1.1.
  One-shot notifications with hysteresis (`NOTIFY_HUNGRY/TIRED/COLD/HURT`).

### Progression
- XP to reach level L: `25·(L−1)·(L+2)` → L2 100 · L3 250 · L4 450 · L5 700 · L6 1000 · L7 1350 ·
  L8 1750 · L9 2200 · L10 2700 (max). Each level: +1 skill point, +1 attribute point; +1 extra
  skill point at L5 and L10. Start: 1 skill point; attributes Agility 3, Stealth 2, Charm 2,
  Hunting 1 (1..10).
- XP sources: quests (story total ≈ 840 incl. objectives), location 15, memory photo 40, other
  collectible 5, first nap at a spot 20, territory 15, first knock of an object 3, prey 10 ×
  prey_xp_mult, achievement 50, daily scratch 5. A full story run lands at level 4–5; all side
  content ≈ level 8–10.
- 26 skills, 5 trees (Agility 6, Stealth 5, Charm 5, Hunting 5, Survival 5), tiers 1–3, total
  cost 43 points vs ≈ 15–20 obtainable → real choices. Tier-3 skills need level 4 and attribute 5.
- **Modifiers** (`GameState.get_modifier(name)`): `base + Σ per_attribute·(attr−1) + skills +
  conditional skills (e.g. night) + buffs + equipment`, × vitals factor for `speed`/`noise`
  modifiers, clamped to `[min,max]` — all specified in `skills.json → modifiers`. Key ones:
  `jump_distance jump_height move_speed sprint_speed sneak_speed climb_speed wire_speed balance
  fall_damage_mult safe_fall_height wall_jump noise_mult landing_noise_mult detection_mult
  night_vision charm_bonus meow_charm food_gift_chance rep_gain_mult price_mult purr_heal
  catch_chance catch_birds pounce_distance pounce_speed scent_range hearing_range cat_sense_cost
  sense_collectibles prey_xp_mult energy_regen energy_drain sprint_energy_mult hunger_drain
  food_value warmth_drain wet_rate health_regen free_faints_per_day faint_cap_loss_mult
  max_health max_hunger max_energy max_warmth xp_mult`.
- Buffs (timed in game minutes): catnip, playful (toys), sharp_claws (scratch post), well_fed,
  warm_nap, groomed. Collars (equip slot `collar`) carry `equip_modifiers`.

### Inventory & mouth
Everything owned is counted in one inventory; **one** mouth-type item (`items.json "mouth": true`)
is carried in `mouth_item`. Picking up a mouth item when the mouth is full swaps (the old item
is dropped as a new `PickupItem`). Mouth items received while the mouth is busy (quest rewards)
go to Cam's den stash; `set_mouth_item(id)` switches. Deliveries require the item in the mouth.
Caps (`cap`, stack 999) are the currency (Lão Quạ: `buy_item`, `sell_item`, charm-based prices).

### Save format (`user://saves/slot_<n>.json`, slot 0 = autosave, 1–3 manual)
`{game, version: 1, saved_at, saved_at_unix, playtime_s, summary{level,caps,day,hour,location,quest},
state{stats, attributes, attribute_points, xp, level, skill_points, skills[], items{}, mouth_item,
equipped{}, flags{}, reputation{}, locations{}, collectibles{}, territory{}, nap_spots{},
last_nap_spot, last_nap_transform[12], counters{}, achievements[], buffs{}, world{}, wetness,
faints_today, current_area}, player_transform[12], weather{kind,intensity},
providers{time, quests, dialogue, …}}`. Written to `.tmp` then renamed; the previous file is kept
as `.bak` and used if the main file is corrupt. Every key is optional on load (defaults), values
are type-checked/clamped, unknown skills/quests ignored, v0 (state at top level) migrated.
Providers registered later receive their pending data on `register_save_provider`. The player
transform/weather are applied when `player_spawned` fires if the player didn't exist at load.
Autosave: on naps, quest start/objective/complete; throttled to 20 s but deferred, never dropped.

## API quick reference
**GameState**: `get_stat/get_stat_max/get_stat_ratio/set_stat/modify_stat`, `simulate(h)`,
`set_activity`, `is_sheltered`, `get_exposed_rain`, `soak`, `groom`, `get_vitals_speed_factor`,
`get_attribute/get_effective_attribute/set_attribute/add_attribute/raise_attribute`,
`xp_for_level(L)`, `add_xp(n, reason)`, `get_level_progress`, `get_xp_to_next_level`,
`add_skill_points/add_attribute_points`, `has_skill/unlock_skill/grant_skill/can_unlock_skill/
get_skill_state/get_skill_lock_reason/get_all_skills/get_skill_trees/get_skills_in_tree`,
`get_modifier(name)`, `has_ability(name)`, `add_item/remove_item/has_item/item_count/get_caps/
get_inventory/get_item_def/get_item_name(id, in_sentence)/is_mouth_item/set_mouth_item/
drop_mouth_item/use_item/eat/equip_item/unequip_slot/get_equipped/buy_item/sell_item/
get_buy_price/get_sell_price`, `add_buff/remove_buff/has_buff/get_buffs`,
`set_flag/get_flag/has_flag/clear_flag`, `add_reputation/get_reputation/get_reputation_tier`,
`discover_location/is_location_discovered`, `mark_collectible/is_collectible_found/
count_collectibles`, `mark_territory/is_territory_marked`, `nap(hours, spot_id, wake_xform, opts)`,
`get_last_nap_transform`, `set_respawn_point`, `register_knock`, `register_prey_catch`,
`get_counter/increment_counter/set_counter`, `has_achievement`, `get_world_state/set_world_state`,
`faint(cause, immediate)`, `get_respawn_transform`, `save_game/load_game/has_save/delete_save/
get_save_info/autosave/new_game/register_save_provider/unregister_save_provider/
consume_pending_player_transform`, `get_player()`.
**TimeOfDay**: `hour day time_scale paused festival_day`, `set_hour/set_time/advance_minutes/
advance_hours/skip_hours/sleep_until/hours_until`, `get_phase/phase_for_hour`, `is_night/
is_daytime/is_hour_between/hour_in_window`, `get_sun_progress[_unclamped]/get_sun_elevation_deg/
get_night_factor/get_day_fraction/get_absolute_minutes`, `is_festival_day/is_festival_night/
set_festival_day/days_until_festival/get_moon_phase/get_moon_illumination`, `get_time_string`,
`push_pause/pop_pause/is_paused`.
**QuestManager / DialogueManager**: see `data/quests/_schema.md` and `data/dialogue/_schema.md`.
**Interactables**: see the header comment of each script in `scripts/systems/`; every one has
`@export` configuration and creates a default collision shape if none is given (Interactables:
sphere r 0.3 on layer 5; QuestTrigger ENTER: 3×2.5×3 box on layer 10 watching layer 2;
Pushable: small cylinder on layer 4, friction 0.45, contact monitoring, auto "knock" area).

## Integration contract notes
- The **player** emits `GameEvents.interacted(target, verb)` after calling `interact()`; the
  interactables don't (QuestManager also de-duplicates identical events in one frame).
- `talk_to` objectives count via `dialogue_started`; a quest started *during* a conversation with
  that NPC counts its "talk to <them>" objective immediately.
- Everything GameState needs from other areas is optional (no hard references): player via
  group `player`, weather via group `weather`, AudioManager via `has_method`.
- Sounds use names from the audio area's bank (`tools/audio`): `cat_meow_greet cat_purr
  cat_meow_chirp cat_meow_trill cat_hiss cat_yowl cat_swipe cat_pickup stinger_memory cat_scratch
  cat_yawn cat_eat_crunch impact_<material> impact_glass_break`.
- Requests to other areas: `docs/requests/systems.md`.

## Known gaps (honest)
- **Story content lives in `tests/fixtures/story/`**, not in `data/quests` / `data/dialogue`
  (not systems-owned paths) — the lead must copy it (request filed). The world must place the
  matching location ids / interactables for it to be playable in the city.
- Item **meshes** and **icons** don't exist yet (street-props / ui); `PickupItem` shows small
  procedural stand-ins sized like the real objects (logged in docs/placeholders.md).
- The systems were tested headless with a stand-in player (`FakePlayer` in the test base); the
  real `CatPlayer` integration (state names, `play_action`, knock/drop hooks) depends on the
  player area following docs/requests/systems.md.
- Vitals rates are first-pass tuning from paper maths, not from playtesting.
- Dialogue has no per-line voice/audio barks or typewriter timing (UI concern); no conversation
  camera logic (only a `camera` hint string per node).
- The `.tmp → rename` save is atomic on the same filesystem but there is no fsync; a power cut
  mid-write can still leave only the `.bak` (which load falls back to).
- Prices/charm discounts are linear and simple; no haggling mini-game.
