// Cat-sense highlight (owner: player), applied as material_overlay on interactables / animals
// while cat-sense is active. Additive fresnel rim + faint fill + a slow scan band rising through
// the object; scaled by the global `cat_sense`. render_priority is set above the post quad so the
// glow keeps its colour on top of the desaturated cat-vision image.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

uniform vec4 glow_color : source_color = vec4(1.0, 0.72, 0.32, 1.0);
uniform float strength = 1.0;
global uniform float cat_sense;

void fragment() {
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.2);
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float band = smoothstep(0.12, 0.0, abs(fract(wp.y * 1.5 - TIME * 0.45) - 0.5) - 0.38);
	float a = (fres * 0.9 + 0.12 + band * 0.25) * strength * clamp(cat_sense, 0.0, 1.0);
	ALBEDO = glow_color.rgb * a;
}
