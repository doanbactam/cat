// Cat-sense post effect (owner: player). Full-screen quad (QuadMesh 2×2 under the camera,
// transparent pass, drawn before the cat-sense highlights / scent motes):
//  * dichromatic "cat vision": luminance + a blue↔yellow axis, red/green collapsed;
//  * whisker-edge: depth discontinuities glow softly, strongest within ~1–5 m (what whiskers and
//    hearing would map), so walls, ledges and gaps read as a silvery line drawing;
//  * vignette that pulls attention to the centre; faint breathing shimmer.
// Driven by the global `cat_sense` (0..1) set by scripts/player/cat_sense.gd.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform vec4 edge_color : source_color = vec4(0.62, 0.86, 1.0, 1.0);
uniform vec4 shadow_tint : source_color = vec4(0.16, 0.2, 0.3, 1.0);
uniform float edge_strength = 0.7;
uniform float near_range = 6.0;
uniform float vignette = 0.62;
global uniform float cat_sense;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

float lin_depth(vec2 uv, mat4 inv_proj) {
	float d = textureLod(depth_tex, uv, 0.0).r;
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
	return -v.z / v.w;
}

void fragment() {
	float k = clamp(cat_sense, 0.0, 1.0);
	vec3 col = textureLod(screen_tex, SCREEN_UV, 0.0).rgb;
	if (k < 0.002) {
		ALBEDO = col;
	} else {
		float lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
		float yb = (col.r + col.g) * 0.5 - col.b;
		vec3 cat_col = vec3(lum) + vec3(0.42, 0.36, -0.5) * yb * 0.5;
		cat_col = mix(cat_col, shadow_tint.rgb * lum * 2.0, smoothstep(0.25, 0.0, lum) * 0.5);
		// whisker edges from linear depth
		vec2 px = 1.5 / VIEWPORT_SIZE;
		float d0 = lin_depth(SCREEN_UV, INV_PROJECTION_MATRIX);
		float dx = lin_depth(SCREEN_UV + vec2(px.x, 0.0), INV_PROJECTION_MATRIX) - lin_depth(SCREEN_UV - vec2(px.x, 0.0), INV_PROJECTION_MATRIX);
		float dy = lin_depth(SCREEN_UV + vec2(0.0, px.y), INV_PROJECTION_MATRIX) - lin_depth(SCREEN_UV - vec2(0.0, px.y), INV_PROJECTION_MATRIX);
		float g = length(vec2(dx, dy)) / max(d0, 0.05);
		float edge = smoothstep(0.03, 0.18, g);
		float near = 1.0 - smoothstep(near_range * 0.25, near_range, d0);
		float shimmer = 0.85 + 0.15 * sin(TIME * 2.4 + d0 * 3.0);
		vec2 c = SCREEN_UV - 0.5;
		float vig = 1.0 - smoothstep(0.25, 0.75, length(c * vec2(1.0, 0.82))) * vignette;
		vec3 outc = cat_col * vig + edge_color.rgb * edge * near * edge_strength * shimmer;
		ALBEDO = mix(col, outc, k);
	}
	ALPHA = 1.0;
}
