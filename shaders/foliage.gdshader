// Alpha-tested foliage cards with wind sway, translucency and rain darkening. Owner: world.
// Vertex colour R = sway weight (0 at the branch, 1 at the card tip), G = per-card random.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

global uniform float wind_strength;
global uniform vec3 wind_direction;
global uniform float wetness;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float alpha_cut = 0.45;
uniform float sway = 0.12;
uniform float translucency = 0.55;

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float w = COLOR.r;
	float rnd = COLOR.g;
	float t = TIME * (1.1 + rnd * 0.6);
	float gust = sin(t * 0.7 + wp.x * 0.05) * 0.5 + 0.5;
	vec3 wd = normalize(wind_direction + vec3(0.0001));
	float amp = sway * (0.3 + wind_strength * 1.6) * w;
	vec3 disp = wd * (gust * amp);
	disp += vec3(sin(t * 3.1 + rnd * 20.0), sin(t * 2.3 + rnd * 7.0) * 0.5, cos(t * 2.7 + rnd * 13.0)) * amp * 0.25;
	VERTEX += (inverse(mat3(MODEL_MATRIX)) * disp);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec3 c = a.rgb * tint.rgb * mix(0.85, 1.12, COLOR.g);
	c *= mix(1.0, 0.75, wetness);
	ALBEDO = c;
	ALPHA = a.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = 0.6;
	ROUGHNESS = mix(0.62, 0.25, wetness);
	SPECULAR = 0.35;
	BACKLIGHT = c * translucency;
	AO = mix(0.55, 1.0, COLOR.r);
	AO_LIGHT_AFFECT = 0.4;
}
