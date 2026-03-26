# gui/godot-client/scenes/card.gd

extends Control

signal card_clicked(event, pile_name, card_data, card_node)

var card_data: Dictionary
var pile_name: String
var card_index: int

@onready var texture_rect: TextureRect = $Texture
@onready var shadow: ColorRect = $Shadow

var shadow_material: ShaderMaterial
var outline_material: ShaderMaterial

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================
func _ready():
	# 1. ПОДКЛЮЧАЕМ СИГНАЛЫ НАВЕДЕНИЯ
	# Это критически важная часть, без этого функции ниже не вызовутся
	mouse_entered.connect(_on_mouse_entered)
	mouse_exited.connect(_on_mouse_exited)
	
	# 2. НАСТРАИВАЕМ ФИЛЬТРЫ МЫШИ
	# Корневой узел карты должен "ловить" мышь (STOP)
	self.mouse_filter = Control.MOUSE_FILTER_STOP
	
	# Внутренняя текстура должна быть "прозрачной" для мыши (IGNORE),
	# иначе она может перехватывать наведение и блокировать сигнал корневому узлу
	if texture_rect:
		texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE

func setup(data: Dictionary, pile: String, index: int, size: Vector2, card_id: Variant = null):
	card_data = data
	pile_name = pile
	card_index = index
	
	set_meta("card_index", index)
	set_meta("pile_name", pile_name)
	set_meta("card_id", card_id if card_id != null else data.get("id", index))
	
	self.set_anchors_preset(Control.PRESET_TOP_LEFT)
	self.size = size
	self.custom_minimum_size = size
	
	var tex = DeckManager.get_card_texture(
		data["suit"],
		int(data["rank"]),
		data["face_up"]
	)
	texture_rect.texture = tex
	
	_apply_shadow_shader(tex)
	_apply_outline_shader(tex)

# ============================================================
# ШЕЙДЕР ТЕНИ
# ============================================================

func _apply_shadow_shader(tex: Texture2D):
	if shadow_material == null:
		var shader = load("res://shaders/card_shadow.gdshader")
		shadow_material = ShaderMaterial.new()
		shadow_material.shader = shader
	
	shadow.material = shadow_material
	
	# Передаем текстуру карты в шейдер
	shadow_material.set_shader_parameter("TEXTURE", tex)

# ============================================================
# ШЕЙДЕР КОНТУРА 
# ============================================================

func _apply_outline_shader(tex: Texture2D):
	# Создаем материал один раз
	if outline_material == null:
		var shader = load("res://shaders/card_outline.gdshader")
		outline_material = ShaderMaterial.new()
		outline_material.shader = shader
		
		# Устанавливаем черный цвет по умолчанию
		outline_material.set_shader_parameter("outline_color", Color.BLACK)
		outline_material.set_shader_parameter("outline_width", 5.0)
	
	# Применяем материал к текстуре карты
	texture_rect.material = outline_material

# ============================================================
# УПРАВЛЕНИЕ ЦВЕТОМ ПОДСВЕТКИ
# ============================================================

# Вызовите эту функцию извне (например, из klondike.gd), чтобы покрасить контур
# color = null вернет черный цвет по умолчанию
func set_highlight(color: Variant = null):
	if outline_material:
		if color is Color:
			# Меняем цвет на указанный (зеленый, синий и т.д.)
			outline_material.set_shader_parameter("outline_color", color)
		else:
			# Возвращаем черный цвет
			outline_material.set_shader_parameter("outline_color", Color.BLACK)

# ============================================================
# ВЗАИМОДЕЙСТВИЕ
# ============================================================

func _gui_input(event):
	emit_signal("card_clicked", event, pile_name, card_data, self)

# ============================================================
# ЭФФЕКТЫ (Drag / Hover)
# ============================================================

func set_dragging(active: bool):
	if active:
		z_index = 100
		scale = Vector2(1.05, 1.05)
		# Тень на всю карту без отступов, но с прозрачностью
		shadow.offset_left = 0
		shadow.offset_top = 0
		shadow.offset_right = 0
		shadow.offset_bottom = 0
		shadow.modulate = Color(0, 0, 0, 0.6)
	else:
		z_index = 0
		scale = Vector2(1, 1)
		# Возвращаем исходную тень (меньше карты, смещённую)
		shadow.offset_left = 6
		shadow.offset_top = 6
		shadow.offset_right = -6
		shadow.offset_bottom = -6
		shadow.modulate = Color(1, 1, 1, 0.5)
		
# ============================================================
# ОБРАБОТКА НАВЕДЕНИЯ МЫШИ (АВТОПОДСВЕТКА)
# ============================================================

func _on_mouse_entered():
	# При наведении делаем контур зеленым
	# Если карта "лицом вниз", возможно, подсвечивать не нужно, добавьте проверку:
	# if not card_data.get("face_up", true): return 
	
	set_highlight(Color.GREEN) # Или Color(0, 1, 0.5) для более приятного оттенка

func _on_mouse_exited():
	# Когда мышь уходит, возвращаем черный
	set_highlight()
