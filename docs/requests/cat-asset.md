# Requests / hand-off notes from `cat-asset`

## To `player` (fur shells, animator, controller)

1. **Fur flow sign** — `assets/models/cat/textures/cat_fur_flow.png` stores the comb direction in
   *exactly the same tangent frame as `cat_normal.png`*: `R = dot(flow, TANGENT)`, `G = dot(flow, B)`
   where `B` is the normal map's +Y (green) axis, i.e. Godot's `BINORMAL` (Godot applies normal maps as
   `TANGENT*x + BINORMAL*y + NORMAL*z`). So the decode should be
   `comb = TANGENT * (fl.x) + BINORMAL * (fl.y)` → `flow_sign_x = 1.0`, **`flow_sign_y = +1.0`**
   (`shaders/fur_common.gdshaderinc` currently defaults to `-1.0`). B channel is a constant 0.5.
2. **Fur length** — mask R = 1 corresponds to `FUR_MAX_LENGTH = 0.016 m` (matches your `fur_length`).
   R is 0 on bare skin (nose leather, paw pads, lips, mouth, tongue, teeth, eye sockets) — please
   discard shells there. G = density (inner ears ~0.3, belly ~0.8). B = stripe mask (1 = dark marking).
3. **Mesh is "skin + compressed fur"**: silhouette is already correct without shells; shells only add
   the soft outer layer, so shell offset ≤ R × 0.016 m is right.
4. **Loop modes are already set in the import** (`cat.glb.import` `_subresources`, see
   `blender/cat/configure_import.py`); setting them again at runtime is harmless.
5. **Jaw**: every clip keys the jaw; the bind/rest pose has the mouth 4° open (modelling choice so lips
   separate cleanly). If you build poses procedurally, rotate `jaw` by −4…−5° about its local X to close.
6. **Turns** `turn_left_90` / `turn_right_90` (0.667 s): authored assuming the controller yaws the model
   **linearly** by ±90° over the clip; planted paws counter-rotate so they stay fixed in the world.
7. **Climb** (`climb`, 0.6 s loop): wall plane at Godot local **z = +0.075** (cat belly faces the wall,
   body vertical), authored for **0.5 m/s** upward speed. **Scratch**: surface at Godot z = **+0.12**.
8. **Sockets**: `mouth_socket` (child of `jaw`, between the canines) and `fpp_eye` (child of `head`,
   midway between the eyes; at rest it is ~0.28 m high, ~0.24 m in walk). Extra useful bones:
   `eye_L/R` (aim eyeballs), `eyelid_L/R` + `eyelid_low_L/R` (blink: +38° / −14° about the bone's
   local X), `ear_L/R` + `ear_tip_L/R`, `whisker_L/R` (pad protraction), `scapula_L/R`,
   `tail_01…tail_08`, `tongue_01/02`.
9. **NPC variants**: same mesh/UVs; swap the body albedo with `cat_albedo_{black,white,calico,grey_tabby}.png`.
   Iris variants for NPC eyes: `cat_eye_iris_{green,copper,blue}.png` (CatEyes surface 0).
