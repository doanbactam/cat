// Rain streak for GPUParticles3D (particle Y axis aligned to velocity by the process material).
// Billboards each quad around its own velocity axis and fades it softly. Owner: world.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, skip_vertex_transform, shadows_disabled;

global uniform float night_factor;
uniform float width = 0.012;
uniform float length_scale = 0.55;
uniform vec4 rain_color : source_color = vec4(0.62, 0.66, 0.72, 1.0);
uniform float opacity = 0.32;

varying float v_y;
varying float v_x;

void vertex() {
	vec3 center = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec3 axis = normalize(MODEL_MATRIX[1].xyz);
	vec3 to_cam = normalize(CAMERA_POSITION_WORLD - center);
	vec3 right = normalize(cross(axis, to_cam));
	vec3 wp = center + right * VERTEX.x * width * 2.0 + axis * VERTEX.y * length_scale;
	VERTEX = (VIEW_MATRIX * vec4(wp, 1.0)).xyz;
	v_y = UV.y;
	v_x = UV.x;
}

void fragment() {
	float across = 1.0 - abs(v_x * 2.0 - 1.0);
	float along = smoothstep(0.0, 0.35, v_y) * smoothstep(1.0, 0.55, v_y);
	float a = across * across * along * opacity * COLOR.a;
	// streaks pick up city light at night, sky light by day
	vec3 c = rain_color.rgb * mix(1.0, 0.35, night_factor);
	ALBEDO = c * a;
	ALPHA = a;
}
