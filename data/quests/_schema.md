# Quest data format — `data/quests/<quest_id>.json`

Owner: **systems** (`scripts/autoload/quest_manager.gd`). One JSON file per quest; the file
name (without `.json`) is the default id. Files starting with `_` are ignored. Text is never
stored here — only translation keys (`data/i18n/strings.csv`, columns `keys,en,vi`).
Conditions and effects use the shared formats documented in `data/dialogue/_schema.md`.

## Top-level fields

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | file name | Unique quest id (`snake_case`, prefix by arc: `main_`, `side_`, `trial_`). |
| `title_key` / `desc_key` | string | `QUEST_<ID>_TITLE` / `_DESC` | Journal texts. |
| `category` | string | `side` | `main`, `trial`, `side`, `misc` — journal grouping & tracking priority. |
| `giver` | string | — | NPC id that gives it (journal/UI only). |
| `objectives` | array | **required** | See below. At least one non-optional objective. |
| `sequential` | bool | `true` | Objectives unlock in order (objective *i* gets `stage` *i*). `false` → all at once. |
| `prerequisites` | object | `{}` | `{"quests": [ids completed], "flags": {name: value}, "level": n, "if": <condition>}` |
| `auto_start` | bool | `false` | Start by itself as soon as prerequisites are met. |
| `track_on_start` | bool | `category == "main"` | Becomes the tracked quest when started. |
| `rewards` | object | `{}` | `{"xp", "caps", "items": {id: n}, "flags": {name: value}, "reputation": {faction: n}, "skill_points", "attribute_points", "skills": [ids], "effects": [<effect>]}` |
| `next` | string \| array | — | Quest(s) started when this one completes (once their prerequisites hold). |
| `on_start` / `on_fail` | effects | — | Effects run when the quest starts / fails. |
| `fail_if` | condition | — | Quest fails as soon as this holds (checked on every state change). |
| `retry_on_fail` | bool | `false` | A failed quest may be started again. |

## Objectives

Common fields: `id` (unique in the quest), `type`, `desc_key` (default
`QUEST_<ID>_OBJ_<OBJID>`; may use `{progress}` / `{count}`), `count` (default 1),
`optional` (doesn't block completion), `hidden` (not shown until it gets progress),
`stage` (int; objectives with the same stage run in parallel; the current stage is the lowest
stage that still has an unfinished required objective), `target_id` (string or array —
explicit id(s) for the HUD marker), `when` (condition that must hold for progress to count),
`time_window` `{"from": h, "to": h}` (wraps midnight), `festival` (only on festival day),
`rewards` (same shape as quest rewards, given when the objective completes), `effects`.

| `type` | Extra fields | Progresses on |
|---|---|---|
| `reach_location` | `target` (location / marker id), `radius` (m, default 3 or the marker's meta `radius`) | `GameEvents.location_discovered`, `area_entered`, `report("reach_location", {location_id})`, or the player standing within `radius` of a node in group `quest_target` (meta `target_id`) / `location` (meta `location_id`). |
| `collect_item` | `item`, `count`, `mode` (`inventory` default \| `pickup`) | `inventory`: progress = how many Cam owns (caps collected earlier count). `pickup`: counts `item_picked_up` after the quest started. |
| `deliver_item` | `item`, `to` (npc id), `from_mouth` (default true), `consume` (default true) | Talking to `to` while carrying the item (Talkable → `QuestManager.try_deliver`), the dialogue effect `{"deliver": item, "to": npc}`, or `GameEvents.item_delivered`. |
| `talk_to` | `npc`, `dialogue` (optional dialogue id) | `GameEvents.dialogue_started(dialogue_id, speaker_id)` or `report("talk_to", {npc_id})`. |
| `interact` | `verb` (optional), `target` (optional target id), `unique` | `GameEvents.interacted(target, verb)` (emitted by the player) or `report("interact", {verb, target_id})`. |
| `mark_territory` | `count`, `spots` (optional whitelist), `count_existing` | `GameEvents.territory_marked` (unique spots). |
| `nap` | `count`, `spot` (optional), `min_hours`, `unique`, `count_existing` | `GameEvents.cat_napped(spot_id, hours)`. |
| `knock_objects` | `count`, `min_height`, `unique` (default true, by object id), `count_existing` | `GameEvents.object_knocked_off` (Pushable fell ≥ its `min_fall_height`). |
| `catch_prey` | `count`, `prey` (optional: `mouse`, `pigeon`, `gecko`…), `count_existing` | `GameEvents.prey_caught` (`GameState.register_prey_catch`). |
| `flag_set` | `flag`, `value` (default true) | Whenever `GameState.get_flag(flag) == value`. |
| `time_window` | `from`, `to` (hours) | Whenever the clock is inside the window (e.g. "wait until night": 19 → 5). |
| `event` | `event` (name), `match` (data subset) | `QuestManager.report(event, data)` — for scripted beats such as a race. |
| `condition` | `if` (condition) | Whenever the condition holds (e.g. `{"attribute": "charm", "gte": 3}`). |

`count_existing: true` seeds progress from what Cam has already done (marked spots, naps,
knocked objects, catches) when the objective activates.

## Runtime API (QuestManager)
`start_quest(id, force := false)`, `is_active/is_completed/is_failed(id)`, `get_state(id)`,
`can_start(id)`, `report(event, data)`, `advance_objective(q, obj, n)`, `complete_objective(q, obj)`,
`complete_quest(id)`, `fail_quest(id)`, `track(id)`, `get_tracked()`, `get_quest(id)` (UI view),
`get_objectives(id)`, `get_tracked_objective()`, `get_tracked_target_position()` (`Vector3.INF` if
none), `try_deliver(npc)`, `deliver_item(item, npc)`, `validate_quest(def)`, `register_quest(def)`.

## Example — story chapter with parallel trials

```json
{
	"id": "main_04_rooftop_trials",
	"category": "main",
	"giver": "mun",
	"prerequisites": {"quests": ["main_03_fish_market"]},
	"objectives": [
		{"id": "meet_mun", "type": "talk_to", "npc": "mun", "stage": 0},
		{"id": "mark_three", "type": "mark_territory", "count": 3, "stage": 1, "count_existing": true,
		 "desc_key": "QUEST_MAIN_04_OBJ_MARK_THREE"},
		{"id": "water_tower", "type": "reach_location", "target": "water_tower", "radius": 2.5, "stage": 1},
		{"id": "race", "type": "event", "event": "rooftop_race_won", "match": {"rival": "mun"}, "stage": 1,
		 "when": {"phase": ["dusk", "night"]}},
		{"id": "show_off", "type": "knock_objects", "count": 3, "optional": true, "hidden": true, "stage": 1,
		 "rewards": {"xp": 25, "reputation": {"rooftop_cats": 5}}},
		{"id": "report_back", "type": "talk_to", "npc": "mun", "stage": 2}
	],
	"rewards": {"xp": 200, "skill_points": 1, "reputation": {"rooftop_cats": 25},
		"flags": {"rooftops_open": true}},
	"next": "main_05_festival_night"
}
```

## Example — side quest with a delivery, gated by time

```json
{
	"id": "side_bins_key",
	"category": "side",
	"giver": "bin",
	"objectives": [
		{"id": "find_key", "type": "collect_item", "item": "key", "target_id": "bins_key_spot"},
		{"id": "return_key", "type": "deliver_item", "item": "key", "to": "bin",
		 "time_window": {"from": 7, "to": 21}}
	],
	"rewards": {"xp": 60, "caps": 5, "reputation": {"humans": 8}, "items": {"toy_mouse": 1}}
}
```
