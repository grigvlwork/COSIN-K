extends Node2D

func _ready():
	print("🎴 Загружаем карты...")
	draw_test_cards()

func draw_test_cards():
	# ТУЗ ПИК (A♠)
	var card1 = Sprite2D.new()
	var texture1 = load("res://assets/cards/ace_of_spades2.png")
	if texture1:
		card1.texture = texture1
		card1.position = Vector2(200, 200)
		card1.scale = Vector2(0.2, 0.2)  # уменьшим если слишком большие
		add_child(card1)
		print("✅ Загружен: ace_of_spades2.png")
	else:
		print("❌ Не найден: ace_of_spades2.png")
	
	# 2♥ (2_of_hearts)
	var card2 = Sprite2D.new()
	var texture2 = load("res://assets/cards/2_of_hearts.png")
	if texture2:
		card2.texture = texture2
		card2.position = Vector2(400, 200)
		card2.scale = Vector2(0.2, 0.2)
		add_child(card2)
		print("✅ Загружен: 2_of_hearts.png")
	
	# КОРОЛЬ ТРЕФ (K♣)
	var card3 = Sprite2D.new()
	var texture3 = load("res://assets/cards/king_of_clubs2.png")
	if texture3:
		card3.texture = texture3
		card3.position = Vector2(600, 200)
		card3.scale = Vector2(0.2, 0.2)
		print(texture3.get_size())
		add_child(card3)
		print("✅ Загружен: king_of_clubs2.png")
	
	# РУБАШКА
	var card4 = Sprite2D.new()
	var texture4 = load("res://assets/cards/back.png")
	if texture4:
		card4.texture = texture4
		card4.position = Vector2(600, 350)
		card4.scale = Vector2(0.205, 0.23)
		add_child(card4)
		print("✅ Загружен: back.png")
