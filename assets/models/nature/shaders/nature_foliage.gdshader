shader_type spatial;
// Alpha-tested, double-sided leaf / flower / grass cards (vehicles-nature).
// Textures: atlas albedo (alpha), OpenGL normal map, ORM (R occlusion, G roughness), translucency.
render_mode depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

#include "res://assets/models/nature/shaders/nature_wind.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform sampler2D trans_tex : hint_default_white, filter_linear_mipmap, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float tint_variation : hint_range(0.0, 0.5) = 0.12;
uniform float alpha_cut : hint_range(0.05, 0.95) = 0.42;
uniform vec3 backlight_color : source_color = vec3(0.6, 0.75, 0.3);
uniform float backlight_strength : hint_range(0.0, 3.0) = 0.9;
uniform float normal_strength : hint_range(0.0, 3.0) = 1.0;
uniform float specular_level : hint_range(0.0, 1.0) = 0.35;
uniform float roughness_floor : hint_range(0.0, 1.0) = 0.5;
uniform float sway_amp = 1.0;
uniform float flutter_amp = 1.0;

varying float v_var;

void vertex() {
	VERTEX = nature_wind(VERTEX, COLOR, MODEL_MATRIX, NORMAL, TIME, sway_amp, flutter_amp);
	// per-instance / per-limb hue variation so repeated trees do not look cloned
	vec3 o = MODEL_MATRIX[3].xyz;
	v_var = fract(sin(dot(o.xz, vec2(12.9898, 78.233)) + COLOR.g * 3.1) * 43758.5453);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec3 col = a.rgb * tint.rgb;
	col *= mix(vec3(1.0), vec3(1.08, 1.04, 0.86), (v_var - 0.5) * 2.0 * tint_variation * 2.0);
	vec3 orm = texture(orm_tex, UV).rgb;
	float wet = clamp(wetness, 0.0, 1.0);
	ALBEDO = col * mix(1.0, 0.78, wet);
	ALPHA = a.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	AO = orm.r;
	AO_LIGHT_AFFECT = 0.25;
	ROUGHNESS = mix(max(orm.g, roughness_floor), 0.18, wet * 0.8);
	METALLIC = 0.0;
	SPECULAR = specular_level * 0.7;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_strength;
	BACKLIGHT = backlight_color * texture(trans_tex, UV).r * backlight_strength;
}
