// Landing reticle for precision jumps (owner: player). A soft double ring lying on the landing
// surface with a slow inward pulse and charge fill; subtle by design (low alpha, warm white),
// drawn on a quad aligned to the surface normal, slightly lifted to avoid z-fighting.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.93, 0.8, 1.0);
uniform float opacity = 0.6;
uniform float charge = 0.0;
uniform float narrow = 0.0;

void fragment() {
	vec2 p = (UV - 0.5) * 2.0;
	// beams/rails: squash the ring along the surface's long axis
	p.x *= mix(1.0, 1.6, narrow);
	float r = length(p);
	float aa = fwidth(r) * 1.5 + 0.01;
	float outer = smoothstep(0.82 + aa, 0.82, r) * smoothstep(0.70 - aa, 0.70, r);
	float pulse_r = 0.62 - fract(TIME * 0.9) * 0.45;
	float pulse = smoothstep(pulse_r + 0.05, pulse_r, r) * smoothstep(pulse_r - 0.06, pulse_r, r) * (1.0 - fract(TIME * 0.9));
	float dot_c = smoothstep(0.09 + aa, 0.09, r);
	float fill = smoothstep(charge * 0.68 + aa, charge * 0.68, r) * 0.18;
	float a = max(max(outer, pulse * 0.6), max(dot_c * 0.8, fill));
	ALBEDO = color.rgb;
	ALPHA = a * opacity;
}
