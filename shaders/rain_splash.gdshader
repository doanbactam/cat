// Rain splash crown sprite (sub-emitter on collision). Procedural: expanding ring + droplets.
// Owner: world.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;

uniform vec4 splash_color : source_color = vec4(0.78, 0.8, 0.85, 1.0);
uniform float opacity = 0.55;
varying float v_life;

void vertex() {
	v_life = INSTANCE_CUSTOM.y;
	// camera-facing billboard keeping particle scale
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0), vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float life = clamp(v_life, 0.0, 1.0);      // 0..1 particle lifetime
	float r = length(vec2(p.x, max(p.y, -0.2) * 1.6));
	float ring = smoothstep(0.12, 0.0, abs(r - mix(0.15, 0.9, life))) * step(p.y, 0.1);
	float drops = 0.0;
	for (int i = 0; i < 5; i++) {
		float fi = float(i);
		vec2 dp = vec2((fi - 2.0) * 0.28, -0.1 - sin(life * 3.14159) * (0.5 + 0.1 * fi));
		drops += smoothstep(0.09, 0.0, length(p - vec2(dp.x * (0.5 + life), -dp.y)));
	}
	float a = clamp(ring + drops, 0.0, 1.0) * (1.0 - life) * opacity * COLOR.a;
	ALBEDO = splash_color.rgb;
	ALPHA = a;
}
