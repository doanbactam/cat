# Dialogue data format — `data/dialogue/<dialogue_id>.json`

Owner: **systems** (`scripts/autoload/dialogue_manager.gd`). One JSON graph per file; the file
name is the dialogue id. Only translation keys are stored (`text_key`), never text.

**Cam never talks.** NPCs speak lines; Cam answers with *cat actions* (choices). The UI shows
each action as a label such as `[Meo]`, optionally followed by a short description
(`text_key`) of *how* he does it ("[Meo] — kêu thật ngọt").

## Top level

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Dialogue id (defaults to the file name). |
| `speaker` | string | Default speaker id for nodes without `speaker` (and the speaker id reported in `dialogue_started` when the caller gives none). |
| `speakers` | object | `{"ba_tu": {"name_key": "NPC_BA_TU", "portrait": "res://…png"}}` — optional; otherwise the name key is `NPC_<SPEAKER>`. `"narrator"` / `""` = no name. `"cam"` = Cam (use for thought-like captions only). |
| `start` | string \| array | Entry node id, or conditional entries `[{"if": <condition>, "node": "id"}, …, {"node": "fallback"}]` — first match wins. |
| `nodes` | object | `node_id → node`. The id `"end"` is reserved (ends the dialogue). |

## Nodes

| Field | Meaning |
|---|---|
| `speaker` | Speaker id for this line. |
| `text_key` | Line text key (`tr`, then `.format()` with `{caps} {level} {day} {time} {cam} {mouth}` + `text_args`). A node with `text_key` is *shown* and waits for `advance()` / `choose()`. |
| `text_args` | Extra format values (UPPERCASE values are translated as keys). |
| `next` | Node after this one (default `end`). |
| `choices` | Cam's replies (see below). A node with choices can't be advanced, only chosen. |
| `effects` | Effects applied when the node is entered (before it is shown). |
| `if` / `else` | Node is skipped (→ `else`, or `next`) when the condition fails. |
| `once` | Show only the first time ever (persisted in the save); afterwards → `else` / `next`. |
| `branch` | `[{"if": <condition>, "next": "id"}, …, {"next": "fallback"}]` — invisible routing node. |
| `anim` | Calls `speaker.play_dialogue_anim(name)` (e.g. `pet_cat`, `talk`, `shoo`). |
| `sfx` | Plays a sound at the speaker (AudioManager). |
| `emote`, `camera` | Hints passed through to the UI (`dialogue_node_shown`). |

### Choices (Cam's actions)
`{"action": "meow", "text_key": "…", "if": <condition>, "show_locked": true, "once": true,
"effects": [ … ], "next": "node"}`

Actions: `meow purr headbutt ignore chirp trill slow_blink rub hiss sit knead follow leave
roll_over offer_item swipe groom stare yowl wait` (labels `DLG_ACT_<ACTION>`). A choice whose
`if` fails is hidden, unless `show_locked` — then it is shown disabled with the requirement
(e.g. "(Duyên 3) [Gừ gừ]"). `once` choices disappear after being picked. Choosing an action
emits `GameEvents.dialogue_choice_made(dialogue_id, action)` (the player plays the matching
animation) and the action's sound (`cat_meow`, `cat_purr`, …).

## Conditions (shared with quests, skills and interactables — `GameConditions`)
A condition is `null`/`{}` (true), a flag name string (`"met_mun"`, `"!met_mun"`), an array
(ALL must hold) or a dictionary with one primary key plus comparators (`gte gt lte lt eq ne`):

| Key | Example |
|---|---|
| `flag` / `not_flag` | `{"flag": "met_mun"}`, `{"flag": "visits", "gte": 3}`, `{"flag": "mood", "value": "happy"}` |
| `item` | `{"item": "fish", "count": 1}` (owned, mouth or den stash) |
| `mouth` / `mouth_empty` | `{"mouth": "fish"}`, `{"mouth_empty": true}` |
| `caps` | `{"caps": 10}` (≥ 10 bottle caps) |
| `attribute` | `{"attribute": "charm", "gte": 3}` — *effective* value (charm includes skill/collar bonuses) |
| `skill` / `not_skill` | `{"skill": "tieng_keu_dang_yeu"}` |
| `reputation` | `{"reputation": "humans", "gte": 10}` (factions `humans`, `rooftop_cats`, `birds`) |
| `quest` | `{"quest": "main_02", "state": "active"}` — states `inactive active completed failed not_started started not_completed available` |
| `objective` | `{"objective": "get_fish", "quest": "main_03", "done": true}` |
| `level`, `day` | `{"level": 3}`, `{"day": 4}` (≥) |
| `stat` | `{"stat": "hunger", "lte": 30}` |
| `phase`, `time` | `{"phase": ["dusk", "night"]}`, `{"time": {"from": 19, "to": 5}}` |
| `festival`, `festival_night` | `{"festival_night": true}` |
| `weather`, `sheltered` | `{"weather": ["rain", "storm"]}` |
| `location`, `collectible`, `territory` | `{"location": "lake"}` (discovered) |
| `dialogue_seen` | `{"dialogue_seen": "bong_intro"}` or `"bong_intro/gossip"` (a node) |
| `buff`, `equipped`, `counter`, `speaker` | `{"counter": "knocked_unique", "gte": 5}` |
| `any` / `all` / `not` | `{"any": [{"skill": "mat_dem"}, {"phase": "day"}]}` |

## Effects (shared with quests — `GameEffects`)
An array of single-type dictionaries:
`set_flag` (`value`), `clear_flag`, `give_item` (`count`), `take_item` (`count`), `set_mouth`,
`deliver` (`to` — removes the item and advances `deliver_item` objectives), `start_quest`,
`advance_quest` (`objective`, `amount`), `complete_objective` (`quest`), `complete_quest`,
`fail_quest`, `track_quest`, `add_xp` (`reason`), `add_rep` (`amount`), `add_skill_points`,
`add_attribute_points`, `add_attribute` (`amount`), `grant_skill`, `modify_stat` (`amount`),
`eat` (`health`), `add_buff` (`hours`), `report` (`data` → `QuestManager.report`), `notify`
(`icon`), `discover_location` (`name_key`), `advance_time` (hours), `sleep_until` (hour), `sfx`,
`speaker_call` (`args` → method on the speaker node), `buy` / `sell` (`price`, caps),
`set_weather` (`intensity`), `mark_collectible`, `counter` (`amount`), and
`{"if": <condition>, "then": [effects], "else": [effects]}`.

## Signals for the UI (GameEvents)
`dialogue_started(dialogue_id, speaker_id)`, `dialogue_line(speaker_name, text, choices: PackedStringArray)`,
`dialogue_node_shown(info)` (rich: `speaker_id, speaker_name, text, portrait, emote, camera,
choices: [{text, action, enabled, requirement}], can_advance`), `dialogue_choice_made`,
`dialogue_ended(dialogue_id)`. The clock is paused while a dialogue is open. Drive it with
`DialogueManager.advance()` and `DialogueManager.choose(index)`.

## Example — Grandma Tư at breakfast

```json
{
	"id": "ba_tu_breakfast",
	"speaker": "ba_tu",
	"speakers": {"ba_tu": {"name_key": "NPC_BA_TU", "portrait": "res://assets/ui/portraits/ba_tu.png"}},
	"start": [
		{"if": {"quest": "main_01_morning", "state": "completed"}, "node": "worried"},
		{"node": "hello"}
	],
	"nodes": {
		"hello": {"text_key": "DLG_BATU_HELLO", "anim": "talk", "next": "offer"},
		"offer": {"text_key": "DLG_BATU_OFFER", "choices": [
			{"action": "meow", "text_key": "DLG_BATU_C_MEOW_SWEET", "next": "fed"},
			{"action": "headbutt", "effects": [{"add_rep": "humans", "amount": 2}], "next": "fed"},
			{"action": "slow_blink", "if": {"attribute": "charm", "gte": 3}, "show_locked": true,
			 "effects": [{"add_rep": "humans", "amount": 5}, {"add_xp": 10}], "next": "fed_extra"},
			{"action": "ignore", "next": "end"}
		]},
		"fed": {"text_key": "DLG_BATU_FED", "anim": "pet_cat", "effects": [{"eat": 35}], "next": "end"},
		"fed_extra": {"text_key": "DLG_BATU_FED_EXTRA", "anim": "pet_cat",
			"effects": [{"eat": 35}, {"give_item": "dried_fish"}], "next": "end"},
		"worried": {"text_key": "DLG_BATU_WORRIED", "once": true, "else": "worried_again",
			"effects": [{"start_quest": "main_02_rumours"}], "next": "end"},
		"worried_again": {"text_key": "DLG_BATU_WORRIED_AGAIN"}
	}
}
```

## Example — Lão Quạ the trader

```json
{
	"id": "lao_qua_trade",
	"speaker": "lao_qua",
	"start": "gate",
	"nodes": {
		"gate": {"branch": [
			{"if": {"mouth": "fish"}, "next": "fish"},
			{"if": {"reputation": "birds", "lt": -10}, "next": "rude"},
			{"next": "shop"}
		]},
		"fish": {"text_key": "DLG_QUA_FISH", "choices": [
			{"action": "offer_item", "if": {"caps": 10}, "show_locked": true,
			 "effects": [{"deliver": "fish", "to": "lao_qua"}, {"take_item": "cap", "count": 10},
			             {"set_flag": "crow_told_secret"}], "next": "secret"},
			{"action": "leave"}
		]},
		"secret": {"text_key": "DLG_QUA_SECRET", "effects": [{"advance_quest": "main_02_rumours", "objective": "pay_crow"}]},
		"shop": {"text_key": "DLG_QUA_SHOP", "choices": [
			{"action": "meow", "text_key": "DLG_QUA_BUY_COLLAR", "if": {"caps": 15}, "show_locked": true,
			 "effects": [{"buy": "collar_red", "price": 15}], "next": "thanks"},
			{"action": "chirp", "text_key": "DLG_QUA_BUY_TONIC", "if": {"caps": 60}, "show_locked": true,
			 "effects": [{"buy": "skill_tonic"}], "next": "thanks"},
			{"action": "leave"}
		]},
		"thanks": {"text_key": "DLG_QUA_THANKS"},
		"rude": {"text_key": "DLG_QUA_RUDE"}
	}
}
```
