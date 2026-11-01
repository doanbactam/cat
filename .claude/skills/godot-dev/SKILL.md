---
name: godot-dev
description: Godot 4.7 development playbook for this repo — API lookup, GDScript/shader gotchas, headless verification, scene building from scripts. Use for any Godot code, scene or shader work in Mèo Cam.
---

# Godot 4.7 development playbook

## 1. Never guess an API — look it up (4.7 has APIs your memory may lack or misremember)
```bash
D=/opt/tools/godot-docs/doc/classes
grep -n '<method name="move_and_slide"' -A6 $D/CharacterBody3D.xml
grep -n '<member name=' $D/SpringBoneSimulator3D.xml | head -50
ls $D | grep -i ik            # TwoBoneIK3D, FABRIK3D, CCDIK3D, SplineIK3D, ChainIK3D, IKModifier3D ...
grep -rn 'name="rendering/' $D/ProjectSettings.xml | head
```
Notable 4.7 features worth using: `SkeletonModifier3D` stack (`TwoBoneIK3D` for paw IK,
`LookAtModifier3D`/`AimModifier3D` for head, `SpringBoneSimulator3D` for the tail/ears),
`Environment.TONE_MAPPER_AGX`, SMAA (`screen_space_aa`), Jolt physics (project default here),
physics interpolation (ON in this project), `FoliageShader`-style vertex wind in custom shaders,
`Decal`, `FogVolume`, `ReflectionProbe`, `VoxelGI`/`SDFGI`, `GPUParticles3D` with collision,
`NavigationRegion3D` + `NavigationAgent3D` (avoidance), `AnimationTree` state machines with
`AnimationNodeStateMachine`/`BlendSpace1D/2D`.

## 2. Verification loop (mandatory)
1. `tools/validate.sh` (or `tools/validate.sh "" scripts/player` to filter) — catches parse errors.
2. `tools/run_tests.sh <filter>` — write tests in `tests/test_<area>*.gd` extending `tests/test_base.gd`.
   Tests run headless with autoloads in the tree; instantiate scenes with `tree.root.add_child(...)`,
   step physics with `await tree.physics_frame`, free them afterwards.
3. `tools/screenshot.sh scene=res://… out=/abs/path.png frames=60 size=1280x720` then **Read the PNG**.
   Rendering is software Vulkan (lavapipe): ~1–5 s/frame at 720p. Use small sizes while iterating,
   `frames` ≥ 30 so TAA/SDFGI converge. `cam=` / `look=` override the camera.
4. Never leave a script that only "should" work. Run it.

Run raw Godot only via the lock: `tools/godot_lock.sh godot --headless --path . --script res://x.gd </dev/null`.
SceneTree scripts: do work in a deferred call (`_run.call_deferred()` from `_init`), `await process_frame`
once so autoloads are ready, and always `quit()`.

## 3. GDScript 4.7 gotchas
- Static typing everywhere; typed arrays `Array[StringName]`; `@export_range(0, 1, 0.01)`; `@onready`.
- Signals: `sig.emit(a)`, `sig.connect(callable)`; `await sig`. `is_instance_valid(n)` before using stale refs.
- `CharacterBody3D`: set `velocity` then `move_and_slide()` (no args). `floor_snap_length`, `floor_max_angle`,
  `apply_floor_snap()`, `get_floor_normal()`, `is_on_floor()`, `get_slide_collision(i)`.
  Small characters (cat ≈ 0.25 m) need `safe_margin` ~0.001–0.004 and short `floor_snap_length` (~0.15).
- Physics interpolation is ON: in `_process` read `global_transform` of physics bodies via
  `get_global_transform_interpolated()`; after teleporting call `reset_physics_interpolation()`.
  Cameras following bodies should update in `_process` using interpolated transforms.
- Imported glTF animations: loop flags are NOT set by Blender export. At runtime:
  `anim_player.get_animation(&"walk").loop_mode = Animation.LOOP_LINEAR` for looping clips.
  Skeleton path is `<ArmatureName>/Skeleton3D`; bone tracks look like `CatRig/Skeleton3D:spine_01`.
- `Basis.looking_at(dir, Vector3.UP, true)` makes +Z face `dir` (model front convention here).
- Strings shown to players: `tr("KEY")`. Avoid string-typed node paths across scenes; use groups.
- `PackedScene.pack(root)`: every node you want saved must have `owner = root` (set recursively after add_child).
- Don't use `OS.delay_msec` / blocking loops; don't use `@tool` unless editor-time behaviour is needed.
- `DisplayServer.get_name() == "headless"` → skip GPU-only work (e.g. `get_image()` on viewports).

## 4. Shaders (Godot shading language)
- `shader_type spatial; render_mode depth_draw_opaque, cull_back;`
- Textures: `uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;`
  normal maps `: hint_normal` and write `NORMAL_MAP`; ORM channels → `AO`, `ROUGHNESS`, `METALLIC`.
- Skinning happens before `vertex()`: `VERTEX`/`NORMAL` are already skinned (model space) — shell fur can
  offset `VERTEX += NORMAL * shell_offset`.
- Alpha-tested foliage/fur: `ALPHA` + `ALPHA_SCISSOR_THRESHOLD` (stays in opaque pass, sorts correctly, works with TAA).
- Material chains: `material.next_pass = other_material` renders the same mesh again (used for fur shells).
- Global time `TIME`; world position in fragment: `(INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz`.
- Wetness: darken albedo (×0.6), roughness → 0.05–0.15 on upward faces, add ripple normal when raining.

## 5. Scene & performance rules
- Big repeated props → `MultiMeshInstance3D`; set `visibility_range_end` on small props (fade 5–10 m margin);
  enable mesh LOD (auto on import). Occluders (`OccluderInstance3D`) for building blocks.
- Lights: one `DirectionalLight3D` sun (PSSM 4 splits, `shadow_max_distance` ~ 120), street lamps as
  `OmniLight3D`/`SpotLight3D` with `distance_fade_enabled` and shadows only on the nearest few.
- Never block the main thread on loading big scenes: `ResourceLoader.load_threaded_request`.
