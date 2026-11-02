shader_type spatial;
// Opaque bark / stems / roots with the shared wind (branches sway with the leaves attached to them)
// and rain wetness (darker, glossier, more on upward-facing bark).
render_mode depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://assets/models/nature/shaders/nature_wind.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float normal_strength : hint_range(0.0, 3.0) = 1.2;
uniform float moss_amount : hint_range(0.0, 1.0) = 0.0;
uniform vec4 moss_color : source_color = vec4(0.22, 0.28, 0.08, 1.0);
uniform float sway_amp = 1.0;

varying vec3 v_wnormal;
varying float v_height;

void vertex() {
	VERTEX = nature_wind(VERTEX, COLOR, MODEL_MATRIX, NORMAL, TIME, sway_amp, 0.0);
	v_wnormal = normalize(mat3(MODEL_MATRIX) * NORMAL);
	v_height = VERTEX.y;
}

void fragment() {
	vec3 col = texture(albedo_tex, UV).rgb * tint.rgb;
	vec3 orm = texture(orm_tex, UV).rgb;
	float up = clamp(v_wnormal.y, 0.0, 1.0);
	// moss on the upward / lower trunk faces (humid old quarter)
	float moss = moss_amount * smoothstep(0.35, 0.9, up * 0.7 + (1.0 - orm.r) * 0.6) * smoothstep(5.0, 0.5, v_height);
	col = mix(col, moss_color.rgb * (0.7 + 0.6 * orm.r), clamp(moss, 0.0, 1.0));
	float wet = clamp(wetness, 0.0, 1.0);
	float wet_here = wet * (0.6 + 0.4 * up);
	ALBEDO = col * mix(1.0, 0.55, wet_here);
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = mix(orm.g, 0.22, wet_here);
	METALLIC = 0.0;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength * (1.0 - 0.4 * wet_here);
}
