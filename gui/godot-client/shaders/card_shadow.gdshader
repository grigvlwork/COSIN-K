shader_type canvas_item;

void fragment() {
	vec2 pixel_size = TEXTURE_PIXEL_SIZE;

	float alpha_sum = 0.0;

	for (int x = -1; x <= 1; x++) {
		for (int y = -1; y <= 1; y++) {
			vec2 offset = vec2(float(x), float(y)) * pixel_size * 2.0;
			alpha_sum += texture(TEXTURE, UV + offset).a;
		}
	}

	float avg_alpha = alpha_sum / 9.0;

	COLOR = vec4(0.0, 0.0, 0.0, avg_alpha * 0.5);
}