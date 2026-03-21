# gui/godot-client/scenes/card.gd

extends Control

signal card_clicked(event, pile_name, card_data, card_node)

var card_data: Dictionary
var pile_name: String
var card_index: int

@onready var texture_rect: TextureRect = $Texture
@onready var shadow: ColorRect = $Shadow

var shadow_material: ShaderMaterial

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

func setup(data: Dictionary, pile: String, index: int, size: Vector2):
	card_data = data
	pile_name = pile
	card_index = index
	
	set_meta("card_index", index) # ← ВОТ ЭТОГО НЕ ХВАТАЛО
	
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
