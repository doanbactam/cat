// Shared fur shading (owner: player) — included by fur_base.gdshader and fur_shell.gdshader.
//
// Lighting: wrapped diffuse (fur scatters light past the terminator) + a warm subsurface band,
// Kajiya-Kay anisotropic specular with two shifted lobes (white primary, albedo-tinted secondary)
// along the combed strand direction, and a backlit rim "fuzz". Wetness (own wet state and/or the
// global `wetness`) darkens, sharpens the highlights and clumps/shortens the strands.
// First-person: fragments within `fpp_hide.w` of the head centre are discarded in the MAIN camera
// pass only (shadow / probe passes keep the head so it still casts a shadow).

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D fur_mask : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform sampler2D fur_flow : hint_default_black, filter_linear_mipmap, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform float fur_length = 0.016;
// flow map (tangent-space RG) → model space; flip if the source convention differs
uniform float flow_sign_x = 1.0;
uniform float flow_sign_y = -1.0;
// how upright the strands stand (0 = combed flat along the flow, 1 = straight out)
uniform float strand_lift = 0.38;
uniform float wet_darken = 0.58;
uniform float global_wet_influence = 0.0;
uniform float spec_primary = 0.16;
uniform float spec_secondary = 0.22;
uniform float rim_strength = 0.32;
uniform float wrap_diffuse = 0.42;

global uniform float wetness;
global uniform float cat_sense;
global uniform float wind_strength;
global uniform vec3 wind_direction;

instance uniform float wet_self = 0.0;
instance uniform vec3 inertia = vec3(0.0);
instance uniform vec4 fpp_hide = vec4(0.0, 0.0, 0.0, 0.0);
instance uniform vec3 main_cam = vec3(0.0, -10000.0, 0.0);

varying vec3 v_strand;
varying float v_wet;

float fur_wet() {
	return clamp(max(wet_self, wetness * global_wet_influence), 0.0, 1.0);
}

// Strand direction in model space from the normal + combed flow.
vec3 fur_strand_dir(vec3 n, vec3 t, vec3 b, vec2 uv, float wet) {
	vec2 fl = textureLod(fur_flow, uv, 0.0).rg * 2.0 - 1.0;
	vec3 comb = t * fl.x * flow_sign_x + b * fl.y * flow_sign_y;
	float cl = length(comb);
	comb = cl > 0.05 ? comb / cl : vec3(0.0);
	float lift = mix(strand_lift, strand_lift * 0.55, wet);
	return normalize(n * lift + comb * (1.0 - lift) + n * 0.0001);
}

bool fur_is_main_pass(vec3 cam_world) {
	return distance(cam_world, main_cam) < 0.05;
}

void fur_fpp_discard(vec3 world_pos, vec3 cam_world) {
	if (fpp_hide.w > 0.0 && fur_is_main_pass(cam_world) && distance(world_pos, fpp_hide.xyz) < fpp_hide.w) {
		discard;
	}
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float diff = clamp((ndl + wrap_diffuse) / (1.0 + wrap_diffuse), 0.0, 1.0);
	diff *= diff;
	// warm light bleeding through thin fur / ears at the terminator
	float band = smoothstep(-0.3, 0.15, ndl) * (1.0 - smoothstep(0.15, 0.6, ndl));
	vec3 sss = vec3(0.9, 0.38, 0.18) * band * 0.22;
	DIFFUSE_LIGHT += (vec3(diff) + sss) * ATTENUATION * LIGHT_COLOR / PI;
	// Kajiya-Kay along the strand
	vec3 T = normalize(v_strand);
	vec3 H = normalize(LIGHT + VIEW);
	float shift = mix(0.06, 0.02, v_wet);
	vec3 t1 = normalize(T + NORMAL * shift);
	vec3 t2 = normalize(T + NORMAL * (shift - 0.22));
	float th1 = dot(t1, H);
	float th2 = dot(t2, H);
	float e1 = mix(70.0, 220.0, v_wet);
	float e2 = mix(18.0, 60.0, v_wet);
	float s1 = pow(sqrt(max(0.0, 1.0 - th1 * th1)), e1);
	float s2 = pow(sqrt(max(0.0, 1.0 - th2 * th2)), e2);
	float vis = smoothstep(-0.1, 0.3, ndl);
	float wet_boost = mix(1.0, 2.6, v_wet);
	vec3 spec = (vec3(s1) * spec_primary * wet_boost + ALBEDO * s2 * spec_secondary) * vis;
	SPECULAR_LIGHT += spec * ATTENUATION * LIGHT_COLOR / PI;
	// backlit fuzz on the silhouette
	float rim = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	float back = clamp(dot(-VIEW, LIGHT) * 0.5 + 0.5, 0.0, 1.0);
	DIFFUSE_LIGHT += vec3(rim * back * back * rim_strength * (1.0 - v_wet * 0.6)) * ATTENUATION * LIGHT_COLOR / PI;
}
