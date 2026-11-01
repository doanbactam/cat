---
name: visual-qa
description: How to capture and critique in-engine screenshots and Blender previews for Mèo Cam — capture commands, critique checklist, and iteration discipline. Use whenever judging or improving visual quality.
---

# Visual QA

## Capture
- Godot: `tools/screenshot.sh scene=res://scenes/world/city.tscn out=$PWD/qa/out/world/x.png frames=60 size=1280x720 cam=10,3,10 look=0,1,0 hour=17.5`
  (`hour` needs `TimeOfDay.set_hour`; `weather=rain` needs a `set_weather` node). `shots=4 step=20` captures a sequence.
- Blender: `C.preview_render(C.qa_path("area/x.png"), target=(0,0,0.3), distance=2.0)`.
- Always **Read the PNG** after capturing. A run that "succeeded" can still be black, overexposed, or empty.

## Critique checklist (score each 1–5, fix anything ≤ 3)
1. Exposure & tonemapping: no crushed blacks/blown highlights; AgX; sky and sun intensity plausible.
2. Lighting: contact shadows, AO in corners, GI bounce colour, no light leaks, shadow acne/peter-panning.
3. Scale: compare to the cat (0.25 m shoulder) and doors (2.1 m). Cat FPP should feel tiny.
4. Materials: roughness variation, believable albedo, normal maps not inverted, no stretched UVs,
   no obvious tiling (break with decals/vertex colour/macro variation).
5. Density & storytelling: does it look lived-in (clutter, wear, signage, plants, wires)?
6. Composition/readability: player and interactables readable; HUD not covering focus.
7. Artifacts: z-fighting, floating/intersecting objects, popping LODs, missing textures (magenta), seams.
8. Atmosphere: fog/volumetrics, time-of-day colour, weather effects visible.

## Discipline
- Iterate at least twice on anything you judge ≤ 3. Keep before/after images in `qa/out/<area>/`.
- Copy the best 1–3 final images into `docs/gallery/` as `<area>_<what>.png|jpg` (≤ 1 MB each; downscale with PIL).
- Report honestly: list remaining visual weaknesses in `docs/areas/<area>.md`.
