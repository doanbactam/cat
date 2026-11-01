# Area: audio

Every sound in *Mèo Cam: Phố Cũ* is **synthesised procedurally** from code in `tools/audio/` (numpy/scipy,
no samples, no downloads) and played through the `AudioManager` autoload. Nothing here is a placeholder.

## What was built

| Part | Path |
|---|---|
| DSP toolkit (filters, STFT shaping, modal synthesis, band-limited impulses, Doppler moving sources, binaural-lite panning, synthetic room IRs, circular reverb for loops, compressor/limiter, ITU-R BS.1770 loudness, loop tools, Ogg encode) | `tools/audio/dsp.py` |
| Source–filter voice engines (additive harmonic voice with formant tracks; jittered glottal-pulse voice; shaped breath/whisper noise) | `tools/audio/voice.py` |
| Shared world sources (motorbike engine model, horns, non-verbal Vietnamese-tonal babble, birds, crickets, geckos, frogs, wind, rain, rain-on-tin, thunder, chimes, kitchen, TV, AC, neon) | `tools/audio/sources.py` |
| Generators | `gen_cat.py` (cat voice + body foley), `gen_foley.py` (paw steps per surface, landings, impacts, splashes), `gen_entities.py`, `gen_world.py` (ambience + weather), `gen_music.py` (5 tracks + stingers), `gen_ui.py` |
| Build + QA (render → normalise → encode → decode-verify → manifest → spectrograms) | `tools/audio/build_all.py`, `tools/audio/qa.py`, `tools/audio/build.sh` |
| Bus layout generator | `tools/audio/make_bus_layout.gd` → `default_bus_layout.tres` |
| Catalogue generator for this doc | `tools/audio/gen_docs.py` |
| Output | `assets/audio/{sfx/{cat,foley,impacts,entities},ambience/{,weather},music/{,stingers},ui}/*.ogg`, manifest `assets/audio/bank.json` |
| Runtime | `scripts/autoload/audio_manager.gd` |
| Tests | `tests/test_audio.gd` |

### Synthesis highlights
* **Meows** — source–filter: phase-coherent additive harmonics whose amplitudes follow time-varying formant
  tracks (mouth opening `m→a→o/w`, lip rounding), natural F0 contours with scoops, vibrato, jitter/shimmer,
  intermittent period-doubling (sub-harmonics) on loud calls, pitch-synchronous breath noise. Spectral balance was
  matched to real meow recordings (4–8 kHz ≈ −12…−18 dB re. total; checked by analysis). 10 kinds (short, soft,
  chirp, trill, loud, question, demand, greet, complain, yowl) × 3–5 variants, plus yawn, sniff, hiss (spit onset,
  optional growl underlay), growl (rough fry voice; one variant rises into a yowl).
* **Purr** — 23–28 Hz laryngeal pulse train (double burst per cycle) with separate exhale (louder, lower) and
  inhale (brighter, quieter) phases and the hitch between them, nasal/tract resonances, airflow noise; seamless loop.
* **Paw steps** — excitation (soft pad force pulse) × surface response: granular grit (asphalt/concrete),
  glazed-tile modes + occasional claw ticks, hollow plank modes + rare creaks (wood), damped sheet modes + flex
  "boing" (metal), terracotta "tok" + loose-tile clacks (roof), blade-brush micro events (grass), crumbly grains
  (dirt), slap + Minnaert bubbles + droplets (water), muffled brush (fabric), hollow plastic modes. 6 walk + 4 run
  variants per surface, plus a `step_wet` layer mixed in automatically while it rains.
* **Landings** — four paw contacts (front pair, hind pair 45–90 ms later) + body-mass thump; hard landings add a
  claw skid; metal families ring the whole sheet (tin-roof landing), water families splash.
* **Impacts** — modal synthesis with physical bounce sequences (restitution), crack transients and shard fields:
  ceramic smash/knock, glass clink/break, plastic bounces, metal clang with lid wobble (Euler's-disk acceleration),
  rolling can, wood thud, soft/cardboard, push scrape (stick-slip), splashes.
* **Motorbikes** — single-cylinder 4-stroke model: firing pulses at rpm/120 with combustion variability and
  misfires, exhaust/muffler resonances, valve clatter, intake hiss, CVT whine (scooters), tyre noise; rendered as
  moving sources with real propagation-delay Doppler, spreading loss, air absorption and binaural-lite panning.
* **People** — non-verbal only: babble streams of syllables with **Vietnamese tone contours** (ngang, sắc, huyền,
  hỏi, ngã, nặng) and vowel formants (unintelligible by construction), laughs, "ơi!" calls, "suỵt/xùy" shoos,
  surprised "ơ!", delighted "ôi~", humming.
* **Animals** — dog bark/series/growl/pant/whine (Vện), pigeon coo (rolled middle syllable) and wing claps, flock
  take-off, crow caws & rattle (Lão Quạ), tree sparrows, red-whiskered bulbul (chào mào), Asian koel (tu hú),
  rooster, house gecko (thạch sùng) chirp series, tokay (tắc kè) rattle + repeated "tắc-kè", frogs, mice.
* **Ambience** — stereo 60–96 s beds built from **periodic** noise layers (FFT-circular), events placed with
  wrap-around and a **circular-convolution** reverb, so every loop is seamless by construction (seam metric ≈ 0.2–0.8,
  1.0 = an ordinary sample step). Street day/night, market, lake, temple (tuned wind chimes), alley (echoey; TV,
  kitchen: wok sizzle/scrapes/chopping/dishes/tap, drips, AC), rooftop (gusty wind, laundry flaps, distant city),
  festival night (crowd with children, lion-dance drums & cymbals, toy-lantern tunes), dawn chorus and night insects
  overlays; weather: light/heavy rain, rain on corrugated iron, storm wind, near/far thunder, gusts.
* **Music** — 5 original loops in Vietnamese pentatonic modes (Bắc 0-2-5-7-9; Nam/oán 0-3.3-5-7-9.8 with
  microtonal degrees): đàn tranh (stretched additive partials, pluck-position comb, frequency-dependent decay,
  *nhấn* press-bends, *rung* vibrato, *vuốt* glissandi, natural damping), đàn bầu (harmonic tone, rod slides,
  wide vibrato, pickup colour), sáo trúc flute (breath, chiff, scoop, láy grace notes), quartal pentatonic pads,
  plucked bass, lo-fi kit, song loan clapper, mõ, lion-dance trống and chũm chọe. Mixed with soundboard EQ,
  synthetic hall, circular tape wow, saturation, crackle and glue compression; the reverb/ring tail is wrapped onto
  the loop start (perfect seam).

| Track | Mode / tempo / length | Use |
|---|---|---|
| `mus_menu` "Phố Cũ" | D Bắc · 72 bpm · 2:00 | main menu |
| `mus_morning` "Sáng Hàng Mây" | G Bắc · 90 bpm (swing) · 2:08 | dawn/day exploration |
| `mus_night` "Đêm Phố" | A Nam/oán · 64 bpm · 2:15 | dusk/night exploration |
| `mus_festival` "Đêm Trăng Rằm" | C Bắc · 112 bpm · 2:17 | festival night (flag `festival_active`) |
| `mus_tension` "Vện Đuổi" | E Nam · 128 bpm · 1:30 | light tension, dog chase |

### Loudness standard (measured on the decoded Ogg, ITU-R BS.1770 K-weighted; mono counted as dual-mono)
Music −17…−19 LUFS-I · ambience beds −24…−31 LUFS-I · rain −22…−28 · cat voice −13…−20 (max momentary) ·
steps −25…−31 M · landings −15…−24 M · impacts −15…−23 M · UI −15…−30 M. True peak ≤ −1 dBTP everywhere (the
build re-encodes with less gain if Vorbis overshoots). Per-file numbers: `qa/out/audio/report.md`.

## How to regenerate
```bash
tools/audio/build.sh                 # everything (clean rebuild, ~6 min on 4 CPUs); creates tools/audio/.venv on first run
tools/audio/build.sh --only 'cat_meow.*' --cards   # some sounds; --cards writes qa/out/audio/cards/<name>.png
tools/audio/.venv/bin/python tools/audio/gen_docs.py   # refresh the catalogue below
tools/godot_lock.sh godot --headless --path . --script res://tools/audio/make_bus_layout.gd </dev/null   # bus layout
tools/godot_import.sh && tools/run_tests.sh audio
```
Requirements: python3, ffmpeg with libvorbis. The venv (`numpy scipy soundfile Pillow`) is git-ignored.
Builds are deterministic (every variant is seeded from its name + index). QA output: `qa/out/audio/report.md`
(per-file duration, target vs. measured loudness, true peak, DC, loop seam), `sheet_*.png` contact sheets,
`cards/*.png` (spectrogram + waveform + loop-seam panel).

## Runtime API (`AudioManager`)
Contract (CLAUDE.md):
* `play_sfx(name, pos := Vector3.INF, volume_db := 0.0, pitch_jitter := 0.05)` — `INF` = non-positional.
* `play_ui(name)` · `play_footstep(surface, pos, intensity)` · `set_ambience(name, fade := 2.0)`
  (`&""` returns to automatic) · `play_music(name, fade := 2.0)` · `stop_music(fade := 2.0)`.
* Unknown names are a silent no-op (one `push_warning` per name).

Extras:
* `play_at(name, pos, volume_db, pitch_scale, pitch_jitter, bus_override, priority) -> Node` (returns the player).
* `play_loop(name, target: Node3D, volume_db, pitch_scale, doppler := false) -> AudioStreamPlayer3D` + `stop_loop(player, fade)`
  — attach emitters (scooter engines — animate `pitch_scale` with speed, AC units, neon signs, purr while petted).
* `play_landing(surface, pos, impact_speed)` (≥ 5 m/s = hard) · `play_meow(kind, pos, pitch_scale)`
  (kinds: short, chirp, trill, loud, question, demand, greet, complain, soft, purr, hiss, growl, yowl, yawn, sniff;
  NPC cats: pass `pitch_scale` 0.85 (Mun, Mướp) … 1.15 (Bông)).
* `play_stinger(name, duck_db := -10)` · `duck(reason, music_db, ambience_db, fade)` / `unduck(reason, fade)`.
* `resume_auto_music()` · `get_current_music()` · `get_current_ambience()` · `get_layer_sound(layer)`.
* `register_area_ambience(area_id, bed_key_or_name)` · `set_sheltered(bool)` (under awnings: rain-on-tin layer).
* `resolve_surface / resolve_footstep_sound / resolve_landing_sound / resolve_meow_sound / resolve_ambience` (pure).
* `has_sound`, `get_sound_names`, `get_sound_info`, `get_variant_count`, `get_stream(name, variant := -1)`,
  `set_bus_level(bus, 0..1)`, `active_voice_count()`.
* Exports: `react_to_events`, `music_auto`, `music_rest_range` (silence between auto plays), `spot_sounds_enabled`,
  `footstep_gain_db` (e.g. −6 for the *Bước nhung* silent-paws skill).

### What AudioManager does automatically (do NOT also call play_* for these)
| GameEvents signal | Sound |
|---|---|
| `player_landed(speed, surface)` | `play_landing` at the player |
| `player_jumped(charge)` | `cat_jump_effort` |
| `player_meowed(kind)` | `play_meow(kind)` at the player (`&"purr"` → `cat_purr`) |
| `item_picked_up` / `item_dropped` | `ui_item_get` / `cat_drop` |
| `quest_started` / `quest_completed` / `quest_objective_updated` | `ui_quest_start` / `ui_quest_complete` (+duck) / `ui_notify` |
| `level_up`, `skill_unlocked`, `collectible_found`, `location_discovered`, `game_saved`, `notify`, `territory_marked` | `ui_level_up`, `ui_skill_unlock`, `stinger_memory`, `ui_discover`, `ui_save`, `ui_notify` |
| `dialogue_started/ended`, `dialogue_line` | duck music −9 dB / ambience −5 dB; `ui_dialogue_next` |
| `ui_menu_opened/closed(menu)`, `pause_requested` | `ui_menu_open/close` (`ui_map_open/close` for `&"map"`), world SFX/ambience muffled (low-pass) while any menu/pause is open |
| `cat_sense_toggled` | `ui_cat_sense_on/off`, `cat_sniff`, duck music/ambience |
| `phase_of_day_changed`, `weather_changed`, `area_entered`, `player_spawned`, `game_loaded` | ambience/music directors |
| `npc_alerted(npc, ≥0.85)` where npc is a dog (group `dog`, meta/property `npc_kind == "dog"`) | `mus_tension`; after 8 s without alerts → `stinger_chase_end` |
| `settings_changed(&"audio")` | re-reads `audio/master, music, sfx, ambience, ui` (Voice follows SFX) |

Duplicate triggers of the same sound within 50 ms at the same spot are dropped, so an animation event and a signal
cannot double a sound. Footsteps are **not** automatic: the player calls `play_footstep` from gait/anim events.

### Directors
* **Ambience** — layers `base` (area + phase), `overlay` (dawn chorus / night insects in lake, temple, rooftop, alley),
  `weather` (rain light < 0.6 ≤ heavy/storm), `shelter` (rain on tin when `set_sheltered(true)`), `wind` (storm).
  Area ids map by substring: market/cho → market, lake/ho_/guong → lake, temple/dinh/pagoda/shrine → temple,
  alley/hem/ngo → alley, roof/mai → rooftop, festival → festival, otherwise street (override with
  `register_area_ambience`). Market at night falls back to the night street; with GameState flag `festival_active`
  the street/market/temple beds become `amb_festival` at dusk/night. Each layer crossfades (two players) and starts
  at a random offset. **Spot sounds**: per bed, random positional one-shots (horns, pass-bys, birds, geckos, drips,
  crows…) are placed 4–80 m around the camera on the Ambience bus; birds stay quiet in the rain. Storms schedule
  near/far thunder and gusts.
* **Music** — explicit `play_music` overrides; `player_spawned` resumes auto mode (dawn/day → `mus_morning`,
  dusk/night → `mus_night`, festival → `mus_festival`, dog chase → `mus_tension`). Exploration tracks fade out at
  their end and rest 35–80 s before the next (set `music_rest_range = Vector2.ZERO` to loop).

### Buses (`default_bus_layout.tres`)
`Master` (glue compressor + hard limiter −0.8 dB) ← `Music` [Duck, Muffle] · `SFX` [Muffle, subtle street reverb, Comp]
· `Ambience` [Duck, Muffle] · `UI` · `Voice` [Comp] → SFX · reverb-zone buses (wet only) `Alley` (flutter echo),
`Temple` (large), `Interior` (small room), `Market` (semi-open hall) → SFX.
**For `world`:** reverb zones are `Area3D` with `reverb_bus_enabled = true`, `reverb_bus_name = &"Alley"` (etc.),
`reverb_bus_amount` 0.3–0.6, on physics layer 1 or 10 (our players' `area_mask = 1 | 1<<9`).

## Sound catalogue (generated from bank.json)
<!-- BANK:BEGIN -->
**178 bank names, 472 variant files, 31.2 MB Ogg Vorbis.** Columns: variants · bus · loop · approx. length · 3D unit_size / max_distance (m).


### Cat — voice & body foley

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `cat_drop` | 3 | SFX |  | 0.3 | 2.5/20 | Drop item from mouth |
| `cat_eat_crunch` | 4 | SFX |  | 0.3 | 1.5/12 | Single crunchy bite |
| `cat_eat_loop` | 1 | SFX | yes | 6.4 | 1.5/12 | Crunchy dry-food chewing loop |
| `cat_eat_wet_loop` | 1 | SFX | yes | 6.0 | 1.5/12 | Wet food / fish chewing loop |
| `cat_groom_loop` | 1 | SFX | yes | 6.0 | 1.5/10 | Licking/grooming loop |
| `cat_growl` | 3 | Voice |  | 2.2 | 4/35 | Low rough growl (variant 3 rises into a yowl) |
| `cat_hiss` | 4 | Voice |  | 0.9 | 5/40 | Hiss with spit onset (odd variants have growl underlay) |
| `cat_jump_effort` | 4 | SFX |  | 0.2 | 2/15 | Push-off exhale + fur swish |
| `cat_knead_loop` | 1 | SFX | yes | 4.0 | 1.5/8 | Kneading a cushion loop |
| `cat_lap_loop` | 1 | SFX | yes | 5.0 | 1.5/10 | Lapping water loop |
| `cat_meow_chirp` | 4 | Voice |  | 0.3 | 3/35 | 'mrrp!' rising chirp (kind &"chirp") |
| `cat_meow_complain` | 3 | Voice |  | 0.9 | 4/45 | Long descending grumble |
| `cat_meow_demand` | 3 | Voice |  | 0.5 | 5/55 | Insistent 'MEOW!' (demanding food) |
| `cat_meow_greet` | 3 | Voice |  | 0.5 | 4/45 | Friendly 'mrr-aow' greeting |
| `cat_meow_loud` | 4 | Voice |  | 1.1 | 6/70 | Loud plaintive meow (kind &"loud") |
| `cat_meow_question` | 3 | Voice |  | 0.6 | 4/45 | 'mrrow?' questioning |
| `cat_meow_short` | 5 | Voice |  | 0.4 | 4/45 | Short 'mew/meow' (kind &"short") |
| `cat_meow_soft` | 3 | Voice |  | 0.2 | 3/30 | Tiny soft mew (affection) |
| `cat_meow_trill` | 3 | Voice |  | 0.5 | 3/35 | 'brrrrp' rolled trill greeting |
| `cat_pickup` | 3 | SFX |  | 0.2 | 2/15 | Grab item in mouth |
| `cat_purr` | 2 | Voice |  | 4.2 | 1.5/12 | Purr one-shot ~4 s (kind &"purr") |
| `cat_purr_loop` | 1 | Voice | yes | 16.0 | 1.5/12 | Purr loop (~25 Hz pulses, inhale/exhale) |
| `cat_scratch` | 3 | SFX |  | 1.5 | 2.5/25 | Claws on wood post, 4-6 strokes |
| `cat_scratch_fabric` | 2 | SFX |  | 1.8 | 2.5/25 | Claws on fabric/sofa |
| `cat_scratch_loop` | 1 | SFX | yes | 4.4 | 2.5/25 | Scratching loop for the scratch anim |
| `cat_shake_dry` | 2 | SFX |  | 0.8 | 2.5/20 | Dry fur shake + ear flaps |
| `cat_shake_wet` | 2 | SFX |  | 1.2 | 2.5/20 | Shake-off with water spray + ear flaps |
| `cat_sniff` | 3 | Voice |  | 0.5 | 1.5/10 | Quick sniffs (cat-sense) |
| `cat_swipe` | 4 | SFX |  | 0.2 | 2/15 | Paw swipe whoosh |
| `cat_yawn` | 2 | Voice |  | 1.2 | 3/25 | Squeaky yawn (waking from nap) |
| `cat_yowl` | 3 | Voice |  | 2.0 | 8/90 | Territorial caterwaul (rooftop rivals) |

### Footsteps & landings

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `land_hard_metal` | 3 | SFX |  | 1.1 | 3.5/45 | Hard landing on metal |
| `land_hard_plastic` | 3 | SFX |  | 0.3 | 3.5/45 | Hard landing on plastic |
| `land_hard_roof` | 3 | SFX |  | 0.3 | 3.5/45 | Hard landing on roof |
| `land_hard_soft` | 3 | SFX |  | 0.2 | 3.5/45 | Hard landing on soft |
| `land_hard_stone` | 3 | SFX |  | 0.2 | 3.5/45 | Hard landing on stone |
| `land_hard_tile` | 3 | SFX |  | 0.2 | 3.5/45 | Hard landing on tile |
| `land_hard_water` | 3 | SFX |  | 1.8 | 3.5/45 | Hard landing on water |
| `land_hard_wood` | 3 | SFX |  | 0.3 | 3.5/45 | Hard landing on wood |
| `land_soft_metal` | 3 | SFX |  | 1.1 | 2.5/30 | Soft landing on metal |
| `land_soft_plastic` | 3 | SFX |  | 0.3 | 2.5/30 | Soft landing on plastic |
| `land_soft_roof` | 3 | SFX |  | 0.3 | 2.5/30 | Soft landing on roof |
| `land_soft_soft` | 3 | SFX |  | 0.2 | 2.5/30 | Soft landing on soft |
| `land_soft_stone` | 3 | SFX |  | 0.2 | 2.5/30 | Soft landing on stone |
| `land_soft_tile` | 3 | SFX |  | 0.2 | 2.5/30 | Soft landing on tile |
| `land_soft_water` | 3 | SFX |  | 0.6 | 2.5/30 | Soft landing on water |
| `land_soft_wood` | 3 | SFX |  | 0.3 | 2.5/30 | Soft landing on wood |
| `step_asphalt` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on asphalt (walk/sneak/trot) |
| `step_asphalt_run` | 4 | SFX |  | 0.1 | 2/22 | Cat paw step on asphalt at a run |
| `step_concrete` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on concrete (walk/sneak/trot) |
| `step_concrete_run` | 4 | SFX |  | 0.1 | 2/22 | Cat paw step on concrete at a run |
| `step_dirt` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on dirt (walk/sneak/trot) |
| `step_dirt_run` | 4 | SFX |  | 0.1 | 2/22 | Cat paw step on dirt at a run |
| `step_fabric` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on fabric (walk/sneak/trot) |
| `step_fabric_run` | 4 | SFX |  | 0.1 | 2/22 | Cat paw step on fabric at a run |
| `step_grass` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on grass (walk/sneak/trot) |
| `step_grass_run` | 4 | SFX |  | 0.2 | 2/22 | Cat paw step on grass at a run |
| `step_metal` | 6 | SFX |  | 0.5 | 1.6/18 | Cat paw step on metal (walk/sneak/trot) |
| `step_metal_run` | 4 | SFX |  | 0.5 | 2/22 | Cat paw step on metal at a run |
| `step_plastic` | 6 | SFX |  | 0.2 | 1.6/18 | Cat paw step on plastic (walk/sneak/trot) |
| `step_plastic_run` | 4 | SFX |  | 0.2 | 2/22 | Cat paw step on plastic at a run |
| `step_roof_tile` | 6 | SFX |  | 0.2 | 1.6/18 | Cat paw step on roof_tile (walk/sneak/trot) |
| `step_roof_tile_run` | 4 | SFX |  | 0.2 | 2/22 | Cat paw step on roof_tile at a run |
| `step_tile` | 6 | SFX |  | 0.1 | 1.6/18 | Cat paw step on tile (walk/sneak/trot) |
| `step_tile_run` | 4 | SFX |  | 0.1 | 2/22 | Cat paw step on tile at a run |
| `step_water` | 6 | SFX |  | 0.2 | 1.6/18 | Cat paw step on water (walk/sneak/trot) |
| `step_water_run` | 4 | SFX |  | 0.2 | 2/22 | Cat paw step on water at a run |
| `step_wet` | 6 | SFX |  | 0.1 | 1.6/15 | Wet layer added to steps while ground is wet |
| `step_wood` | 6 | SFX |  | 0.2 | 1.6/18 | Cat paw step on wood (walk/sneak/trot) |
| `step_wood_run` | 4 | SFX |  | 0.2 | 2/22 | Cat paw step on wood at a run |

### Knock-over impacts, splashes

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `impact_cardboard` | 3 | SFX |  | 0.3 | 5/60 | Cardboard box thud |
| `impact_ceramic` | 4 | SFX |  | 0.9 | 5/60 | Ceramic pot/bowl smashes |
| `impact_ceramic_knock` | 3 | SFX |  | 0.9 | 5/60 | Ceramic knocked over, not broken |
| `impact_glass_break` | 3 | SFX |  | 1.8 | 5/60 | Glass shatters |
| `impact_glass_clink` | 4 | SFX |  | 1.6 | 5/60 | Glass/bottle clink and ring |
| `impact_metal` | 4 | SFX |  | 2.4 | 5/60 | Metal clang (even: pot/can, odd: lid wobble) |
| `impact_plastic` | 4 | SFX |  | 0.7 | 5/60 | Hollow plastic bounces |
| `impact_soft` | 3 | SFX |  | 0.2 | 5/60 | Fabric/bag/cushion thud |
| `impact_wood` | 4 | SFX |  | 0.4 | 5/60 | Wooden object thud (odd: tips over) |
| `metal_can_roll` | 2 | SFX |  | 2.5 | 5/60 | Tin can rolling away |
| `push_scrape` | 3 | SFX |  | 0.6 | 5/60 | Object pushed along a ledge by a paw |
| `splash_big` | 2 | SFX |  | 1.8 | 5/60 | Cat falls into water |
| `splash_small` | 3 | SFX |  | 0.6 | 5/60 | Small object / paw into water |

### World entities (vehicles, animals, people, places)

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `ac_unit_loop` | 2 | SFX | yes | 6.0 | 2/18 | AC condenser hum loop (emitter on AC units) |
| `bicycle_bell` | 3 | SFX |  | 1.7 | 6/60 | Thumb-lever bicycle bell |
| `bicycle_pass` | 2 | SFX |  | 4.0 | 3/30 | Bicycle freewheel ticking pass-by |
| `bulbul_song` | 4 | SFX |  | 0.8 | 6/70 | Red-whiskered bulbul (chào mào) phrase |
| `crow_caw` | 4 | SFX |  | 0.3 | 10/150 | Single caw (Lão Quạ) |
| `crow_caw_series` | 3 | SFX |  | 1.5 | 10/150 | 2-4 caws |
| `crow_rattle` | 2 | SFX |  | 0.8 | 5/50 | Corvid rattle/chuckle (Lão Quạ talking) |
| `dog_bark` | 6 | SFX |  | 0.2 | 8/120 | Single bark (Vện) |
| `dog_bark_series` | 3 | SFX |  | 1.3 | 8/120 | 3-5 barks |
| `dog_growl` | 3 | SFX |  | 2.0 | 4/35 | Low warning growl |
| `dog_pant_loop` | 1 | SFX | yes | 4.0 | 2/20 | Panting loop (after chase) |
| `dog_whine` | 2 | SFX |  | 0.9 | 4/40 | Whine |
| `door_creak` | 2 | SFX |  | 1.6 | 4/30 | Wooden door hinge creak + latch |
| `flock_takeoff` | 2 | SFX |  | 1.9 | 8/80 | Whole flock bursts up (stereo) |
| `frog_croak` | 3 | SFX |  | 0.9 | 5/60 | Frog croaks (lake, night) |
| `gecko_chirp` | 3 | SFX |  | 1.1 | 4/40 | House gecko (thạch sùng) chirps |
| `horn_car` | 2 | SFX |  | 0.6 | 14/220 | Car dual-tone horn |
| `horn_motorbike` | 4 | SFX |  | 0.5 | 12/200 | Motorbike horn: short, double, long |
| `human_aww` | 2 | SFX |  | 0.7 | 3/25 | Soft delighted 'ôi~' (petting the cat) |
| `human_call` | 4 | SFX |  | 0.8 | 8/80 | Non-verbal 'ơi!' call (even=female) |
| `human_clap_shoo` | 2 | SFX |  | 0.9 | 6/50 | Hand claps + shoo |
| `human_hum` | 2 | SFX |  | 2.6 | 3/25 | Vendor humming a little tune |
| `human_laugh` | 4 | SFX |  | 0.8 | 5/50 | Laugh/chuckle (even=female) |
| `human_shoo` | 3 | SFX |  | 0.5 | 5/40 | 'Suỵt!/Xùy!' shoo hiss |
| `human_surprise` | 4 | SFX |  | 0.3 | 5/50 | 'Ơ!' surprised (object knocked over) |
| `motorbike_ride_loop` | 2 | SFX | yes | 4.0 | 6/100 | Manual-gear motorbike cruising loop |
| `mouse_squeak` | 3 | SFX |  | 0.2 | 1.5/12 | Mouse squeaks |
| `neon_buzz_loop` | 1 | SFX | yes | 5.0 | 1.5/10 | Neon/fluorescent sign buzz loop |
| `pigeon_coo` | 4 | SFX |  | 1.3 | 3/30 | Rock dove coo |
| `pigeon_land` | 2 | SFX |  | 0.7 | 3/30 | Flutter and land |
| `pigeon_takeoff` | 3 | SFX |  | 0.9 | 4/40 | Wing claps on take-off |
| `rooster` | 2 | SFX |  | 1.3 | 12/200 | Rooster crow (dawn) |
| `scooter_idle_loop` | 2 | SFX | yes | 4.0 | 4/60 | Scooter idling (attach with play_loop; pitch_scale ~ rpm) |
| `scooter_pass` | 4 | SFX |  | 6.0 | 8/120 | Mono pass-by with baked Doppler |
| `scooter_ride_loop` | 2 | SFX | yes | 4.0 | 6/90 | Scooter cruising loop (CVT); use with doppler |
| `scooter_start` | 2 | SFX |  | 3.0 | 5/60 | Electric start, catch, idle |
| `shutter_close` | 2 | SFX |  | 3.8 | 8/80 | Roller shutter coming down + slam |
| `shutter_open` | 2 | SFX |  | 3.6 | 8/80 | Roller shutter going up |
| `sparrow_chirp` | 5 | SFX |  | 0.6 | 4/50 | Tree sparrow chirps |
| `temple_bell` | 2 | SFX |  | 10.0 | 20/300 | Bronze temple bell (stereo, long) |
| `temple_woodblock` | 3 | SFX |  | 0.8 | 6/60 | Mõ wood block knocks |
| `tokay_call` | 2 | SFX |  | 7.4 | 10/120 | Tokay gecko 'tắc kè' call |
| `water_drip` | 4 | SFX |  | 0.2 | 2/15 | Single drip into a puddle |

### Ambience beds (loops)

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `amb_alley` | 1 | Ambience | yes | 70.0 | – | Alley: echoey, TV murmur, kitchen sounds, drips, AC hum |
| `amb_dawn_chorus` | 1 | Ambience | yes | 60.0 | – | Overlay: dawn birds + distant roosters |
| `amb_festival` | 1 | Ambience | yes | 96.0 | – | Mid-Autumn festival night: crowd, children, lion-dance drums |
| `amb_lake` | 1 | Ambience | yes | 75.0 | – | Lake: water lapping, birds, leaves, distant city |
| `amb_market` | 1 | Ambience | yes | 90.0 | – | Market bustle: dense crowd, vendors' calls, clatter, slow scooters |
| `amb_night_insects` | 1 | Ambience | yes | 60.0 | – | Overlay: crickets, geckos, frogs (night, non-street areas) |
| `amb_rooftop` | 1 | Ambience | yes | 80.0 | – | Rooftop: wind, distant city, laundry flaps, pigeons |
| `amb_street_day` | 1 | Ambience | yes | 90.0 | – | Day street: motorbike flow, horns, vendor murmur, birds |
| `amb_street_night` | 1 | Ambience | yes | 80.0 | – | Night street: crickets, geckos, distant traffic, TV |
| `amb_temple` | 1 | Ambience | yes | 75.0 | – | Temple courtyard: wind chimes, quiet wind, birds |

### Weather

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `rain_heavy_loop` | 1 | Ambience | yes | 45.0 | – | Heavy rain loop |
| `rain_light_loop` | 1 | Ambience | yes | 45.0 | – | Light rain loop |
| `rain_tin_loop` | 1 | Ambience | yes | 40.0 | – | Rain drumming on corrugated iron (sheltered) |
| `thunder_far` | 3 | Ambience |  | 6.9 | – | Distant rolling thunder (stereo) |
| `thunder_near` | 3 | Ambience |  | 8.3 | – | Close thunder: crack + rumble (stereo) |
| `wind_gust` | 4 | Ambience |  | 4.4 | – | Wind gust one-shot (stereo) |
| `wind_storm_loop` | 1 | Ambience | yes | 60.0 | – | Storm wind loop |

### Music (loops)

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `mus_festival` | 1 | Music | yes | 137.1 | – | 'Đêm Trăng Rằm' festival night — C Bắc, 112 bpm, 2:17 |
| `mus_menu` | 1 | Music | yes | 120.0 | – | 'Phố Cũ' menu theme — D Bắc, 72 bpm, 2:00 |
| `mus_morning` | 1 | Music | yes | 128.0 | – | 'Sáng Hàng Mây' day exploration — G Bắc, 90 bpm, 2:08 |
| `mus_night` | 1 | Music | yes | 135.0 | – | 'Đêm Phố' night exploration — A Nam/oán, 64 bpm, 2:15 |
| `mus_tension` | 1 | Music | yes | 90.0 | – | 'Vện Đuổi' light tension for the dog chase — E Nam, 128 bpm, 1:30 |

### Music stingers (play_stinger)

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `stinger_chase_end` | 1 | Music |  | 5.0 | – | Escaped the dog — relief |
| `stinger_discovery` | 1 | Music |  | 7.5 | – | Location discovered |
| `stinger_festival` | 1 | Music |  | 6.0 | – | Festival begins |
| `stinger_memory` | 1 | Music |  | 10.2 | – | Kỷ niệm memory photograph found |
| `stinger_quest_complete` | 1 | Music |  | 7.2 | – | Main quest step complete (bigger than ui_quest_complete) |

### UI (play_ui)

| name | var | bus | loop | len s | unit/max | description |
|---|---|---|---|---|---|---|
| `ui_back` | 1 | UI |  | 0.8 | – | Back/cancel (falling pluck) |
| `ui_cat_sense_off` | 1 | UI |  | 0.6 | – | Cat-sense ends |
| `ui_cat_sense_on` | 1 | UI |  | 1.2 | – | Cat-sense activated |
| `ui_click` | 2 | UI |  | 0.3 | – | Button press |
| `ui_collectible` | 1 | UI |  | 2.6 | – | Collectible / memory found |
| `ui_confirm` | 1 | UI |  | 1.2 | – | Confirm/accept (rising pluck) |
| `ui_dialogue_next` | 3 | UI |  | 0.2 | – | Dialogue line advance blip |
| `ui_discover` | 1 | UI |  | 2.4 | – | New location discovered (short) |
| `ui_error` | 1 | UI |  | 0.5 | – | Not allowed / error (soft double knock) |
| `ui_hover` | 2 | UI |  | 0.2 | – | Focus/hover tick |
| `ui_item_get` | 1 | UI |  | 1.3 | – | Item obtained |
| `ui_level_up` | 1 | UI |  | 4.0 | – | Level up (sweep + bell chord) |
| `ui_map_close` | 1 | UI |  | 0.4 | – | Map folds |
| `ui_map_open` | 1 | UI |  | 1.8 | – | Map unfolds |
| `ui_menu_close` | 1 | UI |  | 0.8 | – | Menu closes |
| `ui_menu_open` | 1 | UI |  | 1.0 | – | Menu opens (swish + rising arpeggio) |
| `ui_notify` | 1 | UI |  | 2.2 | – | Toast notification (two bells) |
| `ui_page` | 2 | UI |  | 0.2 | – | Journal page turn |
| `ui_pause` | 1 | UI |  | 0.5 | – | Pause (world muffles) |
| `ui_quest_complete` | 1 | UI |  | 3.2 | – | Quest/objective complete |
| `ui_quest_start` | 1 | UI |  | 2.4 | – | Quest started |
| `ui_save` | 1 | UI |  | 1.8 | – | Game saved |
| `ui_skill_unlock` | 1 | UI |  | 2.6 | – | Skill unlocked |
| `ui_slider` | 2 | UI |  | 0.1 | – | Slider step tick |
| `ui_unpause` | 1 | UI |  | 0.5 | – | Unpause |
<!-- BANK:END -->

## Verification (this phase)
* `tools/audio/build.sh` (clean): 472 files, 0 problems — every file within ±1.5 LU of target or peak-limited,
  true peak ≤ −1 dBTP after decoding, DC < 0.002, every loop seam metric < 2 (most < 1).
* Analysis passes that changed the sound (see `qa/out/audio`): meows were too dark (cascade formant roll-off,
  > 8 kHz at −96 dB) → parallel formant model; sub-harmonic over-boost fixed; step thumps had a sub-bass "pump" →
  high-passed pads, more grit; wood/metal steps rang like marimbas → damped; street beds were sub-heavy with a 1–2 kHz
  hole → air-absorption model and traffic bed re-shaped; dawn pigeons too loud; night-street crickets too loud;
  đàn tranh notes were truncated while ringing (end clicks) → damping envelope; music too dark → presence EQ.
* Godot: validate OK, `tests/test_audio.gd` 13/13 pass (run in an isolated project copy because of the import
  blocker below); whole suite runs with AudioManager reacting to every GameEvents signal without script errors.
* Gallery: `docs/gallery/audio_spectrograms.png` (meow / street bed / music cards with loop-seam panels),
  `audio_cat_sheet.jpg`, `audio_foley_sheet.jpg`.

## Known gaps / honest notes
* **Import blocker (not audio's files):** at the time of writing `tools/godot_import.sh` imports nothing because
  `qa/out/cat-asset/cache/*.blend` makes Godot's headless Blender importer abort the reimport pass (request filed in
  `docs/requests/audio.md`). Until that is fixed the `.ogg` files have no `.import` files in the main checkout and
  `tests/test_audio.gd::test_every_bank_file_exists_and_loads_sample` fails there; AudioManager itself degrades
  gracefully (one warning per sound, no errors). Verified green in a clean copy of the project.
* With the Dummy audio driver (headless tests/servers) AudioManager resolves, routes and tracks every request but
  does not start playbacks (`output_enabled() == false`) — the Dummy driver never reaps them, which leaked objects.
* Everything is synthesised; there are no recorded samples. Voices (meows, barks, people) are convincing in
  spectral shape and dynamics but a trained ear will hear a synthetic quality, especially in the human babble
  (intentionally unintelligible) and the crow/dog timbres. Music uses modelled instruments, not sampled ones.
* Judged by analysis only (spectrograms, octave-band balance, loudness, seam metrics) — no listening was possible in
  this environment; final mix levels should be confirmed in-game by ear (bus volumes and `volume_db` in the bank).
* Spot-sound distances/rates and the 3D `unit_size` values are first estimates; tune once the city is populated.
* No occlusion/obstruction raycasts (sounds behind walls are not filtered beyond the reverb zones).
* `mus_morning`/`mus_night` loops restart into their intro; seamless, but the energy drops for 4 bars at the seam.
* Impulsive sounds (drops, crunches) may sit up to ~4 dB under their momentary-loudness target because the
  true-peak ceiling is reached first — this is expected and reported as "peak-limited".
