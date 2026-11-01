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
uniform float strand_tiling = 22.0;
uniform float clump_tiling = 4.5;
// 1 = this shell also renders into shadow maps / probes (only every few shells do).
uniform float shadow_shell = 1.0;
uniform float gravity_droop = 0.28;
uniform float tip_lighten = 0.10;

varying float v_len;

void vertex() {
	v_wet = fur_wet();
	vec4 m = textureLod(fur_mask, UV, 0.0);
	float len = fur_length * m.r * mix(1.0, 0.5, v_wet);
	vec3 dir = fur_strand_dir(NORMAL, TANGENT, BINORMAL, UV, v_wet);
	mat3 inv_model = inverse(mat3(MODEL_MATRIX));
	vec3 g = inv_model * vec3(0.0, -1.0, 0.0) * mix(gravity_droop, 0.75, v_wet);
	vec3 wdir = length(wind_direction) > 0.001 ? normalize(wind_direction) : vec3(1.0, 0.0, 0.0);
	float gust = 0.55 + 0.45 * sin(TIME * 3.3 + dot(VERTEX, vec3(37.0, 23.0, 41.0)));
	vec3 wind = inv_model * (wdir * wind_strength * 0.35 * gust * (1.0 - v_wet * 0.7));
	vec3 inr = inv_model * inertia;
	float h = shell_h;
	VERTEX += dir * len * h + (g + wind + inr) * len * h * h;
	v_strand = normalize((MODELVIEW_MATRIX * vec4(normalize(dir + (g + wind + inr) * h), 0.0)).xyz);
	v_len = m.r;
}

void fragment() {
	if (shadow_shell < 0.5 && !fur_is_main_pass(CAMERA_POSITION_WORLD)) {
		discard;
	}
	vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	fur_fpp_discard(world_pos, CAMERA_POSITION_WORLD);
	vec4 m = texture(fur_mask, UV);
	if (m.r < 0.03) {
		discard;
	}
	// strands: finer where the coat is denser
	vec2 suv = UV * strand_tiling * mix(1.25, 1.0, m.g);
	float s = texture(strand_tex, suv).r;
	float clump = texture(strand_tex, UV * clump_tiling + vec2(0.37, 0.11)).r;
	s = mix(s, clump * 1.05, v_wet * 0.7);
	s *= mix(0.62, 1.0, m.g);
	// short fur (face, paws) gets proportionally thicker strands so it still reads
	s = mix(s, sqrt(max(s, 0.0)), (1.0 - m.r) * 0.5);
	ALPHA = clamp(s - shell_h + 0.5, 0.0, 1.0);
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	vec3 alb = texture(albedo_tex, UV).rgb * tint.rgb;
	float ao = mix(0.38, 1.0, pow(shell_h, 0.75));
	alb *= ao;
	alb = mix(alb, alb * (1.0 + tip_lighten) + vec3(0.012), smoothstep(0.6, 1.0, shell_h) * (1.0 - v_wet));
	alb *= mix(1.0, wet_darken, v_wet);
	ALBEDO = alb;
	ROUGHNESS = mix(0.8, 0.32, v_wet);
	SPECULAR = mix(0.3, 0.5, v_wet);
	METALLIC = 0.0;
}
