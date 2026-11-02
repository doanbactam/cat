// Shell fur (owner: player). One material per shell, chained with next_pass on the cat's skinned
// body material: each pass re-draws the (already skinned) mesh pushed out along the strand
// direction by `shell_h` of the local fur length (cat_fur_mask.png R), and keeps only the pixels
// inside a strand (procedural tiling strand-height texture, thinned by mask G = density).
// Strands bend with gravity (more when wet), wind (global wind_*), and body inertia (instance
// uniform from fur_shells.gd), clump and shorten when wet, and get darker at the root (AO) with
// lighter tips. Alpha-scissor → stays in the opaque pass (sorted, TAA-stable, casts shadows).
shader_type spatial;
render_mode depth_draw_opaque, cull_back;

#include "res://shaders/fur_common.gdshaderinc"

uniform float shell_h = 0.5;
uniform sampler2D strand_tex : filter_linear_mipmap, repeat_enable;
uniform float strand_tiling = 16.0;
uniform float clump_tiling = 3.5;
// shells span [0, guard_extent] × local length: guard hairs poke out past the undercoat
uniform float guard_extent = 1.28;
// 1 = this shell also renders into shadow maps / probes (only every few shells do).
uniform float shadow_shell = 1.0;
uniform float gravity_droop = 0.22;
uniform float tip_lighten = 0.12;
// Negative mip bias on the strand field: at gameplay distance the averaged mips fall under the
// alpha-scissor threshold for every shell at once and the coat turns into a smooth shell; keeping
// sharper mips preserves broken strand tips (TAA resolves the extra shimmer).
uniform float strand_lod_bias = -1.25;

varying float v_len;

void vertex() {
	v_wet = fur_wet();
	float lf = fur_len_factor(UV);
	float len = fur_length * lf * mix(1.0, 0.55, v_wet);
	vec3 dir = fur_strand_dir(NORMAL, TANGENT, BINORMAL, UV, v_wet);
	mat3 inv_model = inverse(mat3(MODEL_MATRIX));
	vec3 g = inv_model * vec3(0.0, -1.0, 0.0) * mix(gravity_droop, 0.72, v_wet);
	vec3 wdir = length(wind_direction) > 0.001 ? normalize(wind_direction) : vec3(1.0, 0.0, 0.0);
	float gust = 0.55 + 0.45 * sin(TIME * 3.3 + dot(VERTEX, vec3(37.0, 23.0, 41.0)));
	vec3 wind = inv_model * (wdir * wind_strength * 0.35 * gust * (1.0 - v_wet * 0.7));
	vec3 inr = inv_model * inertia;
	float h = shell_h * guard_extent;
	VERTEX += dir * len * h + (g + wind + inr) * len * h * h;
	v_strand = normalize((MODELVIEW_MATRIX * vec4(normalize(dir + (g + wind + inr) * h), 0.0)).xyz);
	v_len = lf;
}

void fragment() {
	if (shadow_shell < 0.5 && !fur_is_main_pass(CAMERA_POSITION_WORLD)) {
		discard;
	}
	vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	fur_fpp_discard(world_pos, CAMERA_POSITION_WORLD);
	vec4 m = texture(fur_mask, UV);
	if (m.r < 0.035 || v_len < 0.025) {
		discard;
	}
	// strands: finer on short / dense coat (face, paws), tufted into locks, sparse guard hairs
	float fine = mix(2.1, 1.05, smoothstep(0.12, 0.5, m.r)) * mix(1.25, 1.0, m.g);
	vec2 suv = UV * strand_tiling * fine;
	vec4 st = texture(strand_tex, suv, strand_lod_bias);
	float lock = texture(strand_tex, UV * clump_tiling + vec2(0.37, 0.11)).b;
	float under = st.r * mix(0.82, 1.12, lock);
	under = mix(under, lock * 1.05, v_wet * 0.6);       // wet: strands clump into spikes
	under *= mix(0.65, 1.0, m.g);
	float guard = st.g * guard_extent * (1.0 - v_wet * 0.5) * smoothstep(0.22, 0.48, m.r);
	float s = max(under, guard);
	float hn = shell_h * guard_extent;
	ALPHA = clamp(s - hn + 0.5, 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	vec3 alb = texture(albedo_tex, UV).rgb * tint.rgb;
	// Scale root AO by coat depth so short velvet face fur transitions into bare skin/ears seamlessly
	float coat_depth = smoothstep(0.14, 0.50, m.r);
	float root_t = pow(clamp(hn, 0.0, 1.0), 0.68);
	vec3 root_col = mix(vec3(0.97, 0.95, 0.93), vec3(0.72, 0.54, 0.38), coat_depth);
	vec3 warm_ao = mix(root_col, vec3(1.0), root_t);
	alb *= warm_ao;
	alb = mix(alb, alb * (1.0 + tip_lighten * coat_depth) + vec3(0.015, 0.010, 0.004) * coat_depth, smoothstep(0.55, 1.0, hn) * (1.0 - v_wet));
	// guard hairs have warm golden-cream agouti tips on an orange coat
	float is_guard = step(under + 0.02, guard) * coat_depth;
	alb = mix(alb, mix(alb, vec3(dot(alb, vec3(0.38, 0.34, 0.28))), 0.18) * 1.12, is_guard * 0.65);
	alb *= mix(1.0, wet_darken, v_wet);
	ALBEDO = alb;
	ROUGHNESS = mix(0.74, 0.44, v_wet);
	SPECULAR = mix(0.35, 0.52, v_wet);
	METALLIC = 0.0;
}
