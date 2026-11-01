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
uniform float strand_tiling = 12.0;
uniform float clump_tiling = 3.0;
// shells span [0, guard_extent] × local length: guard hairs poke out past the undercoat
uniform float guard_extent = 1.35;
// 1 = this shell also renders into shadow maps / probes (only every few shells do).
uniform float shadow_shell = 1.0;
uniform float gravity_droop = 0.28;
uniform float tip_lighten = 0.10;

varying float v_len;

void vertex() {
	v_wet = fur_wet();
	vec4 m = textureLod(fur_mask, UV, 0.0);
	float len = fur_length * fur_len_factor(UV) * mix(1.0, 0.55, v_wet);
	vec3 dir = fur_strand_dir(NORMAL, TANGENT, BINORMAL, UV, v_wet);
	mat3 inv_model = inverse(mat3(MODEL_MATRIX));
	vec3 g = inv_model * vec3(0.0, -1.0, 0.0) * mix(gravity_droop, 0.75, v_wet);
	vec3 wdir = length(wind_direction) > 0.001 ? normalize(wind_direction) : vec3(1.0, 0.0, 0.0);
	float gust = 0.55 + 0.45 * sin(TIME * 3.3 + dot(VERTEX, vec3(37.0, 23.0, 41.0)));
	vec3 wind = inv_model * (wdir * wind_strength * 0.35 * gust * (1.0 - v_wet * 0.7));
	vec3 inr = inv_model * inertia;
	float h = shell_h * guard_extent;
	VERTEX += dir * len * h + (g + wind + inr) * len * h * h;
	v_strand = normalize((MODELVIEW_MATRIX * vec4(normalize(dir + (g + wind + inr) * h), 0.0)).xyz);
	v_len = fur_len_factor(UV);
}

void fragment() {
	if (shadow_shell < 0.5 && !fur_is_main_pass(CAMERA_POSITION_WORLD)) {
		discard;
	}
	vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	fur_fpp_discard(world_pos, CAMERA_POSITION_WORLD);
	vec4 m = texture(fur_mask, UV);
	if (m.r < 0.03 || v_len < 0.02) {
		discard;
	}
	// strands: finer on short / dense coat (face, paws), tufted into locks, sparse guard hairs
	float fine = mix(1.9, 1.0, smoothstep(0.12, 0.5, m.r)) * mix(1.2, 1.0, m.g);
	vec2 suv = UV * strand_tiling * fine;
	vec4 st = texture(strand_tex, suv);
	float lock = texture(strand_tex, UV * clump_tiling + vec2(0.37, 0.11)).b;
	float under = st.r * mix(0.78, 1.12, lock);
	under = mix(under, lock * 1.05, v_wet * 0.6);       // wet: strands clump into spikes
	under *= mix(0.6, 1.0, m.g);
	float guard = st.g * guard_extent * (1.0 - v_wet * 0.5) * smoothstep(0.2, 0.45, m.r);
	float s = max(under, guard);
	float hn = shell_h * guard_extent;
	ALPHA = clamp(s - hn + 0.5, 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	vec3 alb = texture(albedo_tex, UV).rgb * tint.rgb;
	float ao = mix(0.4, 1.0, pow(clamp(hn, 0.0, 1.0), 0.75));
	alb *= ao;
	alb = mix(alb, alb * (1.0 + tip_lighten) + vec3(0.012), smoothstep(0.6, 1.0, hn) * (1.0 - v_wet));
	// guard hairs are a touch lighter / less saturated (agouti tips on an orange coat)
	float is_guard = step(under + 0.02, guard);
	alb = mix(alb, mix(alb, vec3(dot(alb, vec3(0.33))), 0.25) * 1.12, is_guard * 0.7);
	alb *= mix(1.0, wet_darken, v_wet);
	ALBEDO = alb;
	ROUGHNESS = mix(0.8, 0.46, v_wet);
	SPECULAR = mix(0.3, 0.5, v_wet);
	METALLIC = 0.0;
}
