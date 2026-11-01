shader_type canvas_item;
// Turns the orthographic top-down capture of the city into an ink-and-wash map on rice paper:
// edge-detected ink lines, posterised & desaturated wash, paper grain, fog of war mask.
uniform sampler2D paper : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D grain : filter_linear_mipmap, repeat_enable;
uniform vec2 texel = vec2(0.001, 0.001);
uniform float ink_strength : hint_range(0.0, 3.0) = 1.15;
uniform float wash_strength : hint_range(0.0, 1.0) = 0.78;
uniform vec4 ink_color : source_color = vec4(0.17, 0.11, 0.07, 1.0);
uniform vec2 paper_scale = vec2(2.0, 2.0);

float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }

void fragment() {
	vec4 src = texture(TEXTURE, UV);
	vec3 c = src.rgb;
	// Sobel on luminance
	float tl = lum(texture(TEXTURE, UV + texel * vec2(-1.0, -1.0)).rgb);
	float t  = lum(texture(TEXTURE, UV + texel * vec2( 0.0, -1.0)).rgb);
	float tr = lum(texture(TEXTURE, UV + texel * vec2( 1.0, -1.0)).rgb);
	float l  = lum(texture(TEXTURE, UV + texel * vec2(-1.0,  0.0)).rgb);
	float r  = lum(texture(TEXTURE, UV + texel * vec2( 1.0,  0.0)).rgb);
	float bl = lum(texture(TEXTURE, UV + texel * vec2(-1.0,  1.0)).rgb);
	float b  = lum(texture(TEXTURE, UV + texel * vec2( 0.0,  1.0)).rgb);
	float br = lum(texture(TEXTURE, UV + texel * vec2( 1.0,  1.0)).rgb);
	float gx = -tl - 2.0 * l - bl + tr + 2.0 * r + br;
	float gy = -tl - 2.0 * t - tr + bl + 2.0 * b + br;
	float edge = clamp(sqrt(gx * gx + gy * gy) * ink_strength, 0.0, 1.0);
	vec3 p = texture(paper, UV * paper_scale).rgb;
	float g = texture(grain, UV * 3.0).r;
	// posterised, desaturated wash of the scene colour
	float L = lum(c);
	vec3 wash = mix(vec3(L), c, 0.55);
	wash = floor(wash * 6.0 + 0.5) / 6.0;
	vec3 col = mix(p, p * (wash * 1.25 + 0.15), wash_strength * src.a);
	col = mix(col, ink_color.rgb, edge * 0.85 * src.a);
	col *= 0.92 + 0.16 * g;
	COLOR = vec4(col, 1.0);
}
