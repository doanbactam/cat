// Cat skin / undercoat layer (owner: player). The opaque base under the shell fur: albedo,
// tangent-space normal (pores + strand micro-normal baked by cat-asset), ORM, fur-aware lighting
// (fur_common), wet darkening, first-person head hiding.
shader_type spatial;
render_mode depth_draw_opaque, cull_back;

#include "res://shaders/fur_common.gdshaderinc"

uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform float normal_strength = 0.85;
uniform float roughness_scale = 1.0;
// Under thick body shells the base reads as the dense warm undercoat; on short face/ear fur
// (m.r < 0.25) it stays at 1.0 so there is zero brightness step at bare/short-fur boundaries.
uniform float undercoat_darken = 0.94;

void vertex() {
	v_wet = fur_wet();
	vec3 dir = fur_strand_dir(NORMAL, TANGENT, BINORMAL, UV, v_wet);
	v_strand = normalize((MODELVIEW_MATRIX * vec4(dir, 0.0)).xyz);
}

void fragment() {
	vec3 world_pos = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	fur_fpp_discard(world_pos, CAMERA_POSITION_WORLD);
	vec4 m = texture(fur_mask, UV);
	vec3 alb = texture(albedo_tex, UV).rgb * tint.rgb;
	float thick_fur = smoothstep(0.24, 0.65, m.r);
	float furry = smoothstep(0.02, 0.20, m.r);
	vec3 warm_under = mix(vec3(1.0), vec3(0.96, 0.90, 0.84) * undercoat_darken, thick_fur);
	alb *= warm_under;
	alb *= mix(1.0, wet_darken, v_wet * furry);
	ALBEDO = alb;
	vec3 orm = texture(orm_tex, UV).rgb;
	AO = mix(0.45, 1.0, orm.r);
	AO_LIGHT_AFFECT = 0.22;
	ROUGHNESS = clamp(orm.g * roughness_scale * mix(1.0, 0.68, v_wet), mix(0.45, 0.28, v_wet), 1.0);
	METALLIC = 0.0;
	SPECULAR = mix(0.38, 0.46, v_wet);
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength * mix(1.0, 0.6, v_wet);
}
