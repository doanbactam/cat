// Hàng Mây sky: physically-flavoured gradient sky with sun disc, moon (with phase), stars,
// two layers of drifting clouds and humid horizon haze. Owner: world.
// LIGHT0 = Sun, LIGHT1 = Moon (DirectionalLight3D order in the scene). The SkyController sets
// cloud_coverage / overcast / storm_flash / moon_phase / star_strength from TimeOfDay + weather.
shader_type sky;
render_mode use_half_res_pass;

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;   // noise_rgba.png
uniform vec4 zenith_day : source_color = vec4(0.22, 0.42, 0.78, 1.0);
uniform vec4 horizon_day : source_color = vec4(0.70, 0.78, 0.86, 1.0);
uniform vec4 zenith_night : source_color = vec4(0.010, 0.016, 0.040, 1.0);
uniform vec4 horizon_night : source_color = vec4(0.045, 0.055, 0.085, 1.0);
uniform vec4 sunset_color : source_color = vec4(1.0, 0.48, 0.22, 1.0);
uniform vec4 ground_color : source_color = vec4(0.16, 0.15, 0.14, 1.0);
uniform float sky_energy = 1.0;
uniform float cloud_coverage : hint_range(0.0, 1.0) = 0.35;
uniform float overcast : hint_range(0.0, 1.0) = 0.0;      // greys the whole dome (rain/storm/fog)
uniform float haze : hint_range(0.0, 1.0) = 0.45;          // humid Hanoi haze at the horizon
uniform float storm_flash = 0.0;                           // lightning (0..1)
uniform float star_strength = 0.0;
uniform float moon_phase = 0.5;                            // 0 new .. 0.5 full .. 1 new
uniform float moon_size = 0.035;
uniform float sun_disc_size = 0.012;
uniform vec2 cloud_wind = vec2(0.004, 0.0015);

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float clouds(vec3 dir, float t) {
	if (dir.y <= 0.0) return 0.0;
	vec2 p = dir.xz / (dir.y + 0.12);            // project on a plane
	vec2 w = cloud_wind * t;
	float n = texture(noise_tex, p * 0.18 + w).r * 0.55;
	n += texture(noise_tex, p * 0.43 - w * 1.6).g * 0.30;
	n += texture(noise_tex, p * 1.30 + w * 2.5).a * 0.15;
	float cov = mix(0.72, 0.18, cloud_coverage);
	float c = smoothstep(cov, cov + 0.22, n);
	return c * smoothstep(0.0, 0.12, dir.y);
}

void sky() {
	vec3 d = EYEDIR;
	vec3 sun = LIGHT0_ENABLED ? LIGHT0_DIRECTION : vec3(0.0, -1.0, 0.0);
	vec3 moon = LIGHT1_ENABLED ? LIGHT1_DIRECTION : vec3(0.0, -1.0, 0.0);
	float sun_h = sun.y;
	float day = smoothstep(-0.18, 0.15, sun_h);
	float golden = smoothstep(0.45, 0.0, abs(sun_h - 0.02)) * smoothstep(-0.2, 0.0, sun_h);

	float h = clamp(d.y, -1.0, 1.0);
	float horizon_t = pow(1.0 - max(h, 0.0), 3.5);
	vec3 zen = mix(zenith_night.rgb, zenith_day.rgb, day);
	vec3 hor = mix(horizon_night.rgb, horizon_day.rgb, day);
	vec3 col = mix(zen, hor, horizon_t);

	// sunset glow concentrated toward the sun azimuth
	float sun_dot = dot(d, sun);
	float toward = pow(max(sun_dot, 0.0), 3.0);
	col = mix(col, sunset_color.rgb * (0.6 + 0.6 * day), golden * (horizon_t * 0.75 + toward * 0.5) * 0.9);
	// Mie halo around the sun
	col += LIGHT0_COLOR * pow(max(sun_dot, 0.0), 24.0) * 0.35 * day * (1.0 - overcast);

	// stars
	if (star_strength > 0.001 && h > 0.0) {
		vec3 sd = d * 420.0;
		vec3 cell = floor(sd);
		float s = hash(cell);
		float star = step(0.9965, s) * smoothstep(0.0, 0.3, h);
		float tw = 0.6 + 0.4 * sin(TIME * (2.0 + s * 9.0) + s * 40.0);
		col += vec3(0.9, 0.92, 1.0) * star * tw * star_strength * 3.0 * (1.0 - overcast);
		// faint milky band
		float band = exp(-pow(dot(d, normalize(vec3(0.3, 0.5, 0.8))) * 3.0, 2.0));
		col += vec3(0.05, 0.055, 0.07) * band * texture(noise_tex, d.xz * 2.0).g * star_strength * (1.0 - overcast);
	}

	// sun disc
	float sun_disc = smoothstep(cos(sun_disc_size), cos(sun_disc_size * 0.8), sun_dot);
	col += LIGHT0_COLOR * sun_disc * 60.0 * smoothstep(-0.03, 0.02, sun_h) * (1.0 - overcast * 0.95);

	// moon disc with phase terminator
	float moon_dot = dot(d, moon);
	if (moon_dot > cos(moon_size * 1.5) && moon.y > -0.05) {
		vec3 right = normalize(cross(moon, vec3(0.0, 1.0, 0.0)));
		vec3 up = cross(right, moon);
		vec3 rel = d - moon * moon_dot;
		vec2 mp = vec2(dot(rel, right), dot(rel, up)) / sin(moon_size);
		float r2 = dot(mp, mp);
		if (r2 < 1.0) {
			float z = sqrt(1.0 - r2);
			float ang = (moon_phase - 0.5) * 6.2831853;           // 0 at full
			vec3 ldir = vec3(sin(ang), 0.0, cos(ang));
			float lit = smoothstep(-0.05, 0.08, dot(vec3(mp, z), ldir));
			float maria = texture(noise_tex, mp * 0.35 + vec2(0.3)).r;
			vec3 mc = vec3(0.95, 0.93, 0.86) * (0.75 + maria * 0.35) * lit;
			float edge = smoothstep(1.0, 0.96, r2);
			col = mix(col, mc * 4.0 + col * 0.2, edge * (1.0 - overcast * 0.85));
		}
		col += vec3(0.6, 0.65, 0.75) * pow(max(moon_dot, 0.0), 400.0) * 0.6 * (1.0 - overcast) * (1.0 - day);
	}

	// clouds (lit by sun/moon, darker when overcast)
	float c = clouds(d, TIME);
	float c_over = mix(c, 1.0, overcast * 0.85);
	vec3 cloud_lit = mix(vec3(0.05, 0.06, 0.08), vec3(0.95, 0.94, 0.92), day);
	cloud_lit = mix(cloud_lit, sunset_color.rgb * 1.1, golden * 0.55);
	cloud_lit *= mix(1.0, 0.45, overcast);
	float silver = pow(max(sun_dot, 0.0), 6.0) * 0.6 * day;
	vec3 cloud_col = cloud_lit * (0.75 + silver) + LIGHT1_COLOR * (1.0 - day) * 0.04;
	col = mix(col, cloud_col, c_over * smoothstep(-0.02, 0.08, h));
	col += vec3(0.75, 0.8, 1.0) * storm_flash * (0.4 + c_over) * 3.0;

	// humid haze & below-horizon ground
	// by night the haze carries the city's sodium/neon light pollution (warm, dim)
	vec3 haze_col = mix(hor, vec3(0.8, 0.78, 0.72) * (0.04 + 0.96 * day), 0.5) + sunset_color.rgb * golden * 0.3
		+ vec3(0.05, 0.032, 0.018) * (1.0 - day) * (0.6 + overcast);
	col = mix(col, haze_col, haze * pow(1.0 - abs(h), 10.0));
	if (h < 0.0) {
		col = mix(haze_col, ground_color.rgb * (0.08 + 0.9 * day), smoothstep(0.0, 0.25, -h));
	}
	COLOR = col * sky_energy;
}
