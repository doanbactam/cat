# Mèo Cam: Phố Cũ — Game Design Document

## Pitch
A grounded, beautiful open-neighbourhood RPG. You are **Cam**, a one-year-old orange tabby who lives
under the counter of Grandma Tư's tea stall in a fictional Vietnamese old quarter, **Hàng Mây**.
Explore at cat scale — alleys, balconies, tangled power lines, tiled rooftops, a market, a lake and a
temple — in **third person** or **first person** (cat eye height, wide FOV, whiskers' world).
Days pass, it rains, the market opens and closes, people and animals live their routines.

Pillars: **1. Be a cat** (physical, curious, mischievous, nap anywhere) · **2. Vertical city**
(every ledge is a path) · **3. Living neighbourhood** (routines, weather, sound) · **4. Warmth**
(small, kind story; no combat-heavy design).

## Main story — "Đêm Trăng Rằm" (Full-Moon Night), ~2–3 h
Grandma Tư's little golden lucky-cat figurine (*mèo thần tài*) has vanished from her stall three days
before the Mid-Autumn lantern festival. Without it she is sad and the stall is quiet.
1. **Sáng sớm (Early morning)** — tutorial. Wake on a rooftop nap spot, learn move/jump/camera switch/meow,
   climb down via AC units & awning to the tea stall. Grandma feeds Cam. The figurine is gone.
2. **Tin đồn (Rumours)** — Bông (pampered white cafe cat) says the crows collect shiny things.
   Meet **Lão Quạ** (Old Crow) at the lake's banyan: he'll talk only for *a fresh fish and 10 bottle caps*.
3. **Chợ cá (Fish market)** — get a fish from cô Hoa's stall: charm her (meow + sit, needs Charm 3)
   or steal it while **Vện** the market dog patrols (stealth). Bottle caps are scattered around town.
4. **Thử thách mái nhà (Rooftop trials)** — Lão Quạ's nest is on the temple roof; the only route is the
   rooftop network controlled by **Mun** (black cat, rooftop gang leader). Mun sets 3 trials: mark 3
   territory spots, reach the water tower, and race him across the rooftops.
5. **Đêm hội (Festival night)** — at night during the lantern festival, climb the temple roof, recover
   the figurine from the nest (and a few other "borrowed" items), bring it back to Grandma. The quarter
   lights up with star lanterns. Credits → free roam continues with side content.

## Side content
- 12 **Kỷ niệm** (memories: old photographs) hidden around town — each unlocks a short story line about Grandma.
- **Nap spots** (8): sleeping passes time, restores energy, first time grants XP.
- **Territory spots** (10): scent-marking (scratch/rub) — reputation with the rooftop cats.
- **Knock it off** — knock 20 objects off ledges (cat mischief achievement); humans react.
- Helper quests: Xám the pigeon's lost leg-band; the kid Bin's lost key; ông Mướp's (old temple cat)
  riddles leading to the best nap spot; deliver a letter in your mouth.
- **Trading**: Lão Quạ buys/sells shiny things for bottle caps (cosmetic collars, skill tonics).

## Characters (original)
| Name | Who | Role |
|---|---|---|
| Cam | orange tabby, 1 yr | player |
| Bà Tư | elderly tea-stall owner | Cam's human, quest giver |
| Mun | black cat | rooftop gang leader, rival → friend |
| Bông | white fluffy cafe cat | gossip, hints |
| Ông Mướp | old grey tabby at the temple | wise mentor, riddles |
| Lão Quạ | old crow | trader, antagonist-ish |
| Xám | pigeon | side quest |
| Vện | brindle market dog | patrol obstacle (chases, never hurts badly) |
| Cô Hoa | fishmonger | charm/stealth target |
| Chú Sáu | bánh mì vendor | food source |
| Bin | kid | side quest, pets the cat |

## Map — Hàng Mây quarter (~240 m × 200 m, Godot +X east, -Z north)
```
            N (-Z)
  +-------------------------------------------------------------+
  |  PHỐ HÀNG MÂY (main street, shophouses, rattan shops)        |
  |  [tea stall @ alley mouth]                     [cafe Bông]  |
  |-----+   +----------------------------+   +------------------|
  | West|   |                            |   |  CHỢ (market     |
  | alley   |      HỒ GƯƠNG (lake)       |   |  hall + stalls,  |
  | maze|   |   banyan, bridge, islet    |   |  fish street)    |
  | (hẻm)   |   shrine, pigeons          |   |  Vện patrols     |
  | rooftop |                            |   |                  |
  | network +----------------------------+   +------------------|
  |-----+   PHỐ ĐÌNH (temple street)                            |
  |        [ĐÌNH HÀNG MÂY temple + courtyard + big banyan]       |
  +-------------------------------------------------------------+
            S (+Z)
```
- Streets: main roads 7–8 m with 2.5–3.5 m sidewalks; alleys 1.2–3 m; motorbikes everywhere.
- Verticality: continuous rooftops over the west blocks and the north street; water tanks, solar heaters,
  laundry lines, planks between buildings, power-line bundles (balance-walkable), awnings, AC units,
  balconies with plants, tiled roofs of the temple.

## Core systems
- **Movement**: walk/trot/run/sneak with momentum, turn-in-place, charged precise jumps (hold to crouch,
  release to leap; aim assist toward valid ledges), ledge grab-scramble, balance on thin beams/wires,
  squeeze under cars/through gaps, climb vertical surfaces marked climbable (trees, rough walls, drainpipes).
- **Cat actions**: meow (short/loud/chirp), purr, sit, groom, lie down/sleep, knead, scratch, swipe,
  pick up / drop items in mouth, knock objects, drink, eat, hiss.
- **Cat-sense** (R): brief stylised scent/sound overlay — highlights interactables, scent trails toward
  objectives, nearby animals; costs a little energy.
- **Vitals**: health, hunger, energy, warmth (rain lowers it; dry under awnings). Low vitals = slower,
  noisier; never punishing death — a cat "faints" and wakes at the last nap spot (lose some caps).
- **RPG progression**: XP from exploration, quests, discoveries; levels grant skill points.
  Attributes Agility / Stealth / Charm / Hunting (1–10). Skill tree (examples): *Bước nhung* (silent
  paws), *Nhảy xa* (long jump), *Mắt đêm* (night vision in FPP), *Tiếng kêu đáng yêu* (charm meow),
  *Chín mạng* (one free faint per day), *Thợ săn* (catch pigeons/mice), *Chân bám* (better climbing),
  *Ngủ sâu* (faster energy regain).
- **Reputation** with factions: humans, rooftop cats, birds.
- **Day/night & weather**: 24 real minutes per day by default; dawn/day/dusk/night routines;
  clear/cloudy/rain/storm/fog with wet surfaces, puddles, drips, umbrellas on NPCs.
- **Camera**: TPP orbit (collision-aware, auto-framing on jumps) ⇄ FPP (cat eye height ~0.22 m,
  FOV 80, head-bob synced to gait, paws visible when looking down, whisker vignette in cat-sense).
- **Save**: autosave on sleep/quest steps + 3 manual slots.

## Art direction
Photoreal-leaning, warm and humid. Golden-hour ochre walls, teal shutters, terracotta, mossy concrete,
neon and fluorescent shop light at night, star lanterns during the festival. Volumetric light shafts
through alleys, rain sheen on asphalt, humid haze. AgX tonemapping, gentle film grain, no oversaturation.

## Audio direction
Layered city ambience (motorbikes, distant horns, vendors' calls as non-verbal murmurs, birds at dawn,
crickets/geckos at night, rain on corrugated roofs), detailed cat foley (paw pads on each surface,
landings, purr), sparse acoustic music (đàn bầu/đàn tranh-inspired motifs synthesised, lo-fi warmth).
