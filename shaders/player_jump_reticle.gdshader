// Landing reticle for precision jumps (owner: player). A soft double ring lying on the landing
// surface with a slow inward pulse and charge fill. Warm-white strokes sit on a faint dark halo so
// the mark reads on sunlit pale stone as well as on dark tiles, while staying subtle.
// Drawn on a quad aligned to the surface normal, slightly lifted to avoid z-fighting.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.93, 0.8, 1.0);
uniform vec4 halo_color : source_color = vec4(0.08, 0.05, 0.03, 1.0);
uniform float opacity = 0.75;
uniform float charge = 0.0;
uniform float narrow = 0.0;

float band(float r, float a, float b, float aa) {
	return smoothstep(a - aa, a, r) * smoothstep(b + aa, b, r);
}

void fragment() {
	vec2 p = (UV - 0.5) * 2.0;
	// beams/rails: squash the ring along the surface's long axis
	p.x *= mix(1.0, 1.6, narrow);
	float r = length(p);
	float aa = fwidth(r) * 1.5 + 0.01;
	float outer = band(r, 0.72, 0.82, aa);
	float pulse_f = fract(TIME * 0.9);
	float pulse_r = 0.62 - pulse_f * 0.45;
	float pulse = band(r, pulse_r - 0.05, pulse_r + 0.04, aa) * (1.0 - pulse_f);
	float dot_c = smoothstep(0.08 + aa, 0.08, r);
	float fill = smoothstep(charge * 0.66 + aa, charge * 0.66, r) * 0.22;
	float light = max(max(outer, pulse * 0.65), max(dot_c * 0.9, fill));
	// soft dark halo around the strokes (wider, low alpha)
	float halo = max(band(r, 0.62, 0.92, 0.07), smoothstep(0.2, 0.08, r)) * 0.42;
	float a = max(light, halo);
	ALBEDO = mix(halo_color.rgb, color.rgb, clamp(light / max(a, 0.001), 0.0, 1.0));
	ALPHA = a * opacity;
}
