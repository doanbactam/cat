shader_type canvas_item;
// Frosted backdrop for menus over the live game: mip-blurred screen, warm darkening, vignette.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float blur_lod : hint_range(0.0, 6.0) = 3.2;
uniform float dim : hint_range(0.0, 1.0) = 0.62;
uniform vec4 tint : source_color = vec4(0.09, 0.055, 0.035, 1.0);
uniform float vignette : hint_range(0.0, 2.0) = 0.9;

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 c = textureLod(screen_tex, uv, blur_lod).rgb * 0.5;
	c += textureLod(screen_tex, uv + vec2(0.004, 0.0), blur_lod).rgb * 0.125;
	c += textureLod(screen_tex, uv - vec2(0.004, 0.0), blur_lod).rgb * 0.125;
	c += textureLod(screen_tex, uv + vec2(0.0, 0.006), blur_lod).rgb * 0.125;
	c += textureLod(screen_tex, uv - vec2(0.0, 0.006), blur_lod).rgb * 0.125;
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(c, vec3(l), 0.35);
	c = mix(c, tint.rgb, dim);
	vec2 d = (uv - 0.5) * vec2(1.25, 1.0);
	float v = clamp(1.0 - dot(d, d) * vignette, 0.0, 1.0);
	COLOR = vec4(c * mix(0.55, 1.0, v), 1.0);
}
