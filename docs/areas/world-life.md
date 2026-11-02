# world-life — living neighbourhood AI

Owner paths: `scripts/npc/`, `scenes/npc/`, `shaders/npc_*`, `tests/test_world_life*.gd`.

## What was built
| File | Purpose |
|---|---|
| `scenes/npc/life_director.tscn` / `scripts/npc/life_director.gd` | Drop into any world following the CLAUDE.md marker conventions; scans `npc_spawn`, `traffic_lane`, `patrol_path`, `pedestrian_poi`, `shelter`, NavRegion and spawns + runs everything. AI LOD, pooling, quality caps, time-of-day population/traffic curves, POI claiming, lane leader queries, pounce/noise/horn routing. |
| `scenes/npc/test_life.tscn` (built by `scripts/npc/build_test_life.gd`, runtime `test_life_world.gd`) | Standalone test block: 70 m street with city-houses modules both sides, sidewalks/curbs, tea stall, fish stall, bánh mì cart, lamp posts, poles + wire, awning shelter, park with lake/koi, banyan stand-in, low wall; 3 traffic lanes, Vện & Bin paths, 12 POIs, every NPC marker; baked NavigationMesh (≈590 polys). `call=rain|night|dusk` screenshot helpers. |
| `npc_util.gd` | Static helpers: layers, quality caps, rays, detection multiplier, catch rules, safe AudioManager/GameState access, hurt+knockback (never lethal). |
| `perception.gd` | Vision cone + 2-sample occlusion rays, darkness, sneaking/resting, GameState `detection_mult`; hearing from `player_noise` (walls halve); awareness 0..1 with UNAWARE/SUSPICIOUS/ALERTED + hysteresis; `npc_alerted` on rising level. |
| `npc_base.gd` | CharacterBody3D base: NavigationAgent3D + RVO avoidance (straight steering fallback), LOD tick rates, stuck recovery, facing, head look, Talkable hookup, dialogue hooks `on_dialogue_started/ended`, `play_dialogue_anim`. |
| `pedestrian.gd` | Daily routine by hour (stroll / shop / sit on stools / chat in pairs / wait / look / go home), umbrellas or shelter in rain, react to Cam: look, pet when charmed (Charm + `charm_bonus` + `meow_charm` + personality + human reputation, after a meow), shoo on mischief (`object_knocked_off`, swipes, stall theft noise). Named: Bà Tư (tea stall, sits sipping), Cô Hoa (fish stall, calls out), Chú Sáu (bánh mì cart), Bin (kid roaming the lake path, pets the cat unprompted) with work hours and Talkables. |
| `vehicle.gd` | Motorbike / bicycle / car on `traffic_lane` Path3D: IDM car-following, corridor obstacles (cat, pedestrians, animals), stop + honk (`horn_motorbike`, `horn_car`, `bicycle_bell`), hit → knock-back + small damage (`player_damaged`, source `vehicle`), wheel spin, motorbike lean, rider stand-ins (ride/pedal), engine loop with Doppler for near ones, headlight at night. |
| `dog.gd` | Vện: patrol → investigate → chase (bark, 4.2 m/s < cat run 4.5) → nip (6 HP, clamps ≥1) / bark-up when cat is >0.9 m higher or off-mesh → lose interest → return; naps midday & night (deafer). Group `dog` for chase music. |
| `npc_cat.gd` | Mun (black, green eyes, high ground, hostile until flag `mun_friend`), Bông (white, blue eyes, longer fur), Ông Mướp (grey tabby, old, naps), up to 4 strays (variant coats). Real `cat.glb` + `FurShells` with variant albedo/iris, clip-driven: wander, sit, groom, nap in the sun (sun-ray test), hiss, flee, `start_follow`, `lead_to`, `stop_escort`. |
| `pigeon_flock.gd` | Boids flock: ground walk w/ head-bob, peck, separation; flee radius grows with cat speed, ×0.3 when sneaking; staggered takeoff, escape→circle→perch (auto-found roofs)→return; prey with swipe/pounce catch (needs `catch_birds`). Xám = tame banded pigeon with Talkable. |
| `crow.gd` | Ambient crows (perch, hop, caw, flee, scavenge at twilight) and Lão Quạ (never flees, greets, sleeps at night, comes down to inspect shiny mouth items, Talkable). |
| `sparrow_wire.gd` | Sparrows on a sagging wire: shuffle, chirp, scatter on approach/noise, return. |
| `mouse.gd` | Forage near the hole, flee, hide, catchable (easier than birds). |
| `koi_school.gd` + `shaders/npc_koi.gdshader` | Lathe-built koi mesh with swim-wave vertex shader and procedural varieties (kohaku/showa/ogon/sanke/chagoi) via instance uniforms; boids in a water box; curious when Cam sits at the edge, scatter on noise. |
| `gecko_colony.gd` | Night geckos placed on walls near street lights by raycast, crawl/chirp/dart away. |
| `npc_visual.gd`, `standin_builder.gd`, `proc_animator.gd`, `prey_hitbox.gd` | GLB-or-stand-in visual layer with one API; procedural articulated stand-ins (humans with nón lá/caps/helmets, aprons, umbrellas; brindle dog; pigeon/crow/sparrow; mouse; gecko; scooter, bicycle, car) animated procedurally (walk/run/sit/squat-pet/shoo/talk/sell/ride/pedal, trot/gallop/bark/sleep, peck/flap/glide). |

## Running it
- In the game: instance `res://scenes/npc/life_director.tscn` anywhere in the world tree (lead, phase 2).
- Standalone: open `res://scenes/npc/test_life.tscn` (spawns Cam at PlayerSpawn).
- Rebuild the test world: `tools/godot_lock.sh godot --headless --path . --script res://scripts/npc/build_test_life.gd </dev/null`.
- Tests: `tools/run_tests.sh world_life`.
- Screenshots: `tools/screenshot.sh scene=res://scenes/npc/test_life.tscn out=$PWD/qa/out/world-life/x.png cam=… look=… hour=9`.

## API (LifeDirector)
`start()`, `get_player()`, `get_named(id)`, `get_stats()`, `get_agents_near(pos, r)`, `claim_poi/release_poi`,
`random_destination`, `exit_point`, `find_shelter`, `lane_leader(vehicle)`, `startle(pos, r)`, `despawn(ped)`.
Exports: `spawn_pedestrians/traffic/animals/geckos`, `spawn_radius`, `despawn_radius`, `lod_near/mid/far`,
`ignore_time_curves`. NPC cats: `start_follow(target)`, `lead_to(goal, target)` (emits
`GameEvents.area_entered("<id>_lead_done")`), `stop_escort()`. All NPCs: group `npc`, meta `npc_kind`/`npc_id`; prey in
group `prey` with `prey_kind`; swipes reach them via `on_swiped(by)`.

## Known gaps (honest)
See bottom section (kept up to date at the end of the phase).
