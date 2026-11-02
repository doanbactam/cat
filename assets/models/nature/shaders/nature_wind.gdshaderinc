// Shared wind for every vehicles-nature plant (trees, shrubs, grass, aquatic).
// Vertex colour (COLOR, linear) written by blender/lib/nature_tree.py:
//   R = sway weight (0 trunk base .. 1 twig tips), G = phase, B = flutter weight (leaf-card tips).
// Driven by the project shader globals wind_strength / wind_direction (world area animates them).
global uniform float wind_strength;
global uniform vec3 wind_direction;
global uniform float wetness;

vec3 nature_wind(vec3 v, vec4 col, mat4 model, vec3 nrm, float t, float sway_amp, float flutter_amp) {
	vec3 wp = (model * vec4(v, 1.0)).xyz;
	vec3 wd = vec3(wind_direction.x, 0.0, wind_direction.z);
	float wl = length(wd);
	wd = wl > 1e-4 ? wd / wl : vec3(1.0, 0.0, 0.0);
	mat3 inv = inverse(mat3(model));
	vec3 md = normalize(inv * wd);
	vec3 side = normalize(inv * cross(wd, vec3(0.0, 1.0, 0.0)));
	float s = clamp(wind_strength, 0.0, 2.0);
	float ph = col.g * 6.2831853;
	float tree_ph = dot(model[3].xyz, vec3(0.071, 0.0, 0.113));
	// slow travelling gust front + per-limb oscillation
	float gust = 0.55 + 0.45 * sin(t * 0.42 - dot(wp, wd) * 0.08 + tree_ph);
	float w2 = col.r * col.r;
	float sway = w2 * s * (0.65 * gust + 0.3 * sin(t * (1.1 + 0.25 * col.r) + ph + tree_ph));
	v += md * sway * 0.32 * sway_amp;
	v += side * w2 * s * 0.07 * sway_amp * sin(t * 1.63 + ph * 1.7 + tree_ph);
	v.y -= abs(sway) * 0.06 * sway_amp * col.r;
	// leaf flutter along the normal, stronger at card tips
	float fl = col.b * s * (0.012 + 0.025 * s) * flutter_amp;
	v += nrm * fl * sin(t * 7.3 + ph * 11.0 + wp.x * 2.1 + wp.z * 1.7);
	return v;
}
