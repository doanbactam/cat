// Interaction-focus highlight (owner: player). Applied as GeometryInstance3D.material_overlay on the
// focused interactable's mesh: a soft warm fresnel rim with a slow breathing pulse. Additive and
// depth-tested, so it reads as "light catching the edge" rather than a cartoon outline.
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_back, shadows_disabled, ambient_light_disabled;

uniform vec4 rim_color : source_color = vec4(1.0, 0.78, 0.45, 1.0);
uniform float intensity = 0.55;
uniform float rim_power = 2.6;
uniform float pulse_speed = 2.2;

void fragment() {
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), rim_power);
	float pulse = 0.75 + 0.25 * sin(TIME * pulse_speed);
	ALBEDO = rim_color.rgb * fres * intensity * pulse;
}
