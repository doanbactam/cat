// Dotted trajectory preview for precision jumps (owner: player): camera-facing soft dots from a
// MultiMesh, fading towards both ends (INSTANCE_CUSTOM.x = 0..1 along the arc).
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.93, 0.8, 1.0);
uniform float opacity = 0.45;
varying float v_t;

void vertex() {
	v_t = INSTANCE_CUSTOM.x;
	// billboard: keep the instance position, face the camera
	vec3 world_origin = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float s = length(MODEL_MATRIX[0].xyz);
	vec3 right = INV_VIEW_MATRIX[0].xyz;
	vec3 up = INV_VIEW_MATRIX[1].xyz;
	vec3 wp = world_origin + (right * VERTEX.x + up * VERTEX.y) * s;
	POSITION = PROJECTION_MATRIX * VIEW_MATRIX * vec4(wp, 1.0);
}

void fragment() {
	float r = length(UV - 0.5) * 2.0;
	float a = smoothstep(1.0, 0.35, r);
	float ends = smoothstep(0.0, 0.18, v_t) * smoothstep(1.0, 0.8, v_t);
	ALBEDO = color.rgb;
	ALPHA = a * opacity * ends;
}
