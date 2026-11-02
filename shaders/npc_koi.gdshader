shader_type spatial;
// Koi body (owner: world-life). Model space: nose at +Z (0.5), tail at -Z (-0.5), mesh built by
// scripts/npc/koi_school.gd. Swim undulation travels head→tail with amplitude growing toward the
// tail; procedural koi varieties (kohaku / showa / ogon / sanke-like) from per-instance params;
// wet scales: tight specular, subtle scale pattern, under-water darkening.
render_mode cull_disabled, depth_draw_opaque;

instance uniform float swim_phase = 0.0;
instance uniform float swim_speed = 1.0;   // 0..2 (0 = drifting)
instance uniform float turn = 0.0;         // -1..1 body curl
instance uniform float pattern_seed = 0.0;
instance uniform float variety = 0.0;      // 0 kohaku, 1 showa, 2 ogon, 3 sanke, 4 chagoi
uniform float water_depth_tint = 0.35;

varying vec3 v_local;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
	vec2 i = floor(p); vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p) { float v = 0.0; float a = 0.5; for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; } return v; }

void vertex() {
	v_local = VERTEX;
	float tailw = clamp(0.5 - VERTEX.z, 0.0, 1.0);          // 0 at nose .. 1 at tail
	float amp = (0.02 + 0.10 * tailw * tailw) * (0.35 + swim_speed);
	float wave = sin(swim_phase - VERTEX.z * 7.0);
	VERTEX.x += wave * amp + turn * tailw * tailw * 0.18;
	NORMAL = normalize(NORMAL + vec3(cos(swim_phase - VERTEX.z * 7.0) * amp * 4.0, 0.0, 0.0));
}

void fragment() {
	vec3 p = v_local;
	vec2 uv = vec2(p.z * 3.0, atan(p.x, p.y) * 0.8) + vec2(pattern_seed * 7.13, pattern_seed * 3.7);
	float blot = smoothstep(0.48, 0.56, fbm(uv * 2.2));
	float spots = smoothstep(0.62, 0.68, fbm(uv * 5.0 + 11.0));
	vec3 white = vec3(0.93, 0.92, 0.88);
	vec3 red = vec3(0.86, 0.22, 0.06);
	vec3 orange = vec3(0.95, 0.55, 0.10);
	vec3 black = vec3(0.04, 0.04, 0.05);
	vec3 gold = vec3(0.95, 0.75, 0.35);
	vec3 col;
	int v = int(variety + 0.5);
	if (v == 0) { col = mix(white, red, blot); }
	else if (v == 1) { col = mix(mix(black, white, smoothstep(0.4, 0.6, fbm(uv * 1.7 + 4.0))), red, blot * 0.9); }
	else if (v == 2) { col = gold * (0.85 + 0.3 * fbm(uv * 8.0)); }
	else if (v == 3) { col = mix(mix(white, red, blot), black, spots); }
	else { col = mix(vec3(0.55, 0.42, 0.25), vec3(0.42, 0.30, 0.16), fbm(uv * 3.0)); }
	// belly lighter, back darker; under-water tint
	float up = clamp(p.y * 4.0 + 0.5, 0.0, 1.0);
	col *= mix(1.08, 0.86, up);
	col = mix(col, col * vec3(0.55, 0.75, 0.7), water_depth_tint);
	// scale pattern
	vec2 sc = vec2(p.z * 60.0, atan(p.x, p.y) * 9.0);
	float scale_line = smoothstep(0.85, 1.0, abs(sin(sc.x + sin(sc.y) * 0.8)));
	ALBEDO = col * (1.0 - scale_line * 0.08);
	ROUGHNESS = 0.22 + scale_line * 0.2;
	SPECULAR = 0.6;
	METALLIC = (v == 2) ? 0.35 : 0.05;
	// thin translucent fins near the tail
	float fin = smoothstep(0.42, 0.5, abs(p.z + 0.02) ) * step(p.z, -0.3);
	SSS_STRENGTH = 0.3 + fin * 0.4;
}
