shader_type canvas_item;
render_mode blend_mix;

// Параметры, которые можно менять из кода
uniform vec4 outline_color : source_color = vec4(0.0, 0.0, 0.0, 1.0); // Цвет по умолчанию
uniform float outline_width : hint_range(0.0, 4.0) = 1.0; // Толщина по умолчанию

void fragment() {
    vec4 tex_color = texture(TEXTURE, UV);
    
    // Если текстура непрозрачная, просто рисуем её (чтобы не затемнять саму карту)
    if (tex_color.a > 0.01) {
        COLOR = tex_color;
    } 
    else {
        // Если пиксель прозрачный, проверяем соседей
        vec2 ps = TEXTURE_PIXEL_SIZE;
        float alpha = 0.0;
        
        // Смотрим вверх, вниз, влево, вправо
        alpha += texture(TEXTURE, UV + vec2(0.0, -outline_width) * ps).a;
        alpha += texture(TEXTURE, UV + vec2(0.0, outline_width) * ps).a;
        alpha += texture(TEXTURE, UV + vec2(-outline_width, 0.0) * ps).a;
        alpha += texture(TEXTURE, UV + vec2(outline_width, 0.0) * ps).a;
        
        // Если нашлись непрозрачные соседи, рисуем цвет контура
        if (alpha > 0.0) {
            COLOR = outline_color;
        } else {
            discard; // Иначе оставляем прозрачным
        }
    }
}