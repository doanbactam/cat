// Hồ Gương lake water. Owner: world.
// Opaque on purpose (the lake is a murky jade-green urban lake) so it is drawn in the opaque pass:
// SSR, reflection probes and SDFGI all reflect off it. Depth colour is computed analytically from
// the elliptical basin (lake_center / lake_radii / max_depth) and the shore foam from the same
// distance. Ripples: two scrolling normal maps + wind; rain drops when the world is wet.
shader_type spatial;
render_mode depth_draw_opaque, cull_back, specular_schlick_ggx;

global uniform float wetness;
global uniform float wind_strength;
global uniform vec3 wind_direction;
global uniform float night_factor;

uniform sampler2D wave_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D ripple_tex : filter_linear_mipmap, repeat_enable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec4 shallow_color : source_color = vec4(0.30, 0.38, 0.22, 1.0);
uniform vec4 deep_color : source_color = vec4(0.06, 0.12, 0.08, 1.0);
uniform vec4 foam_color : source_color = vec4(0.62, 0.62, 0.55, 1.0);
uniform vec2 lake_center = vec2(0.0, 0.0);
uniform vec2 lake_radii = vec2(40.0, 30.0);
uniform float max_depth = 2.2;
uniform float rain = 0.0;              // set by WeatherSystem (0..1 rain intensity)
uniform float wave_scale = 0.06;
uniform float roughness_base = 0.035;

varying vec3 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	// gentle swell (cheap; amplitude a few mm so the embankment line stays clean)
	float s = sin(world_pos.x * 0.35 + TIME * 0.9) * cos(world_pos.z * 0.29 + TIME * 0.7);
	VERTEX.y += s * 0.006 * (0.4 + wind_strength);
}

vec3 rain_drops(vec2 p, float t) {
	vec4 r1 = texture(ripple_tex, p);
	vec4 r2 = texture(ripple_tex, p * 0.71 + vec2(0.13, 0.57));
	float f1 = fract(t * 1.4 + r1.b);
	float f2 = fract(t * 1.2 + r2.b + 0.5);
	vec2 n = (r1.rg * 2.0 - 1.0) * (1.0 - f1) * step(0.02, r1.a) + (r2.rg * 2.0 - 1.0) * (1.0 - f2) * step(0.02, r2.a);
	return vec3(n, 1.0);
}

void fragment() {
	vec2 wd = normalize(wind_direction.xz + vec2(0.0001));
	float ws = 0.2 + wind_strength;
	vec2 uv1 = world_pos.xz * wave_scale + wd * TIME * 0.018 * ws;
	vec2 uv2 = world_pos.xz * wave_scale * 2.3 - vec2(wd.y, -wd.x) * TIME * 0.025 * ws;
	vec2 uv3 = world_pos.xz * wave_scale * 7.0 + wd * TIME * 0.06;
	vec3 n1 = texture(wave_normal, uv1).rgb * 2.0 - 1.0;
	vec3 n2 = texture(wave_normal, uv2).rgb * 2.0 - 1.0;
	vec3 n3 = texture(wave_normal, uv3).rgb * 2.0 - 1.0;
	vec3 n = normalize(vec3(n1.xy + n2.xy * 0.7 + n3.xy * 0.35 * ws, 1.0));
	// wind gust patches (cat's-paw darker ruffles)
	float gust = smoothstep(0.55, 0.8, texture(noise_tex, world_pos.xz * 0.02 + wd * TIME * 0.01).r) * wind_strength;
	n.xy *= 0.6 + gust * 1.5;
	float r = clamp(rain, 0.0, 1.0);
	if (r > 0.01) {
		vec3 rd = rain_drops(world_pos.xz * 0.45, TIME);
		n.xy += rd.xy * 0.9 * r;
	}
	n = normalize(n);

	// analytic basin depth
	vec2 q = (world_pos.xz - lake_center) / lake_radii;
	float d = length(q);                  // 0 centre .. 1 at the wall
	float depth = max_depth * clamp(1.0 - d * d, 0.0, 1.0) + 0.35;
	float dn = clamp(depth / (max_depth + 0.35), 0.0, 1.0);
	float murk = texture(noise_tex, world_pos.xz * 0.013).g;
	vec3 col = mix(shallow_color.rgb, deep_color.rgb, smoothstep(0.0, 0.7, dn));
	col *= 0.85 + murk * 0.3;
	// floating pollen/scum near the shore
	float shore = smoothstep(0.93, 0.995, d);
	float scum = smoothstep(0.5, 0.75, texture(noise_tex, world_pos.xz * 0.15 + vec2(TIME * 0.003)).b) * smoothstep(0.85, 0.98, d);
	col = mix(col, foam_color.rgb * 0.7, scum * 0.35);
	col = mix(col, foam_color.rgb, shore * 0.25 * (0.5 + 0.5 * sin(TIME * 1.5 + world_pos.x)));

	ALBEDO = col;
	METALLIC = 0.0;
	SPECULAR = 0.5;
	ROUGHNESS = clamp(roughness_base + gust * 0.08 + r * 0.05 + shore * 0.2, 0.02, 1.0);
	NORMAL_MAP = n * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 1.0;
	// subsurface-ish glow of the green water facing the sun (cheap)
	BACKLIGHT = col * 0.25;
}
