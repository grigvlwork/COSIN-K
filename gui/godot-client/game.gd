extends Node2D

var http = HTTPRequest.new()
var game_state = null

# Константы для отрисовки
const CARD_SCALE = 0.2
const CARD_WIDTH = 500 * CARD_SCALE
const CARD_HEIGHT = 726 * CARD_SCALE
const STACK_OFFSET = 30  # Сдвиг для стопок

# Позиции на столе
var stock_pos = Vector2(100, 100)
var waste_pos = Vector2(250, 100)
var tableau_start_x = 100
var tableau_start_y = 300
var foundation_start_x = 500
var foundation_y = 100

func _ready():
	add_child(http)
	http.request_completed.connect(_on_request_completed)
	
	# Запускаем игру!
	create_new_game()

func create_new_game():
	print("🎮 Создаем новую игру")
	var body = '{"variant":"klondike"}'
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/new", headers, HTTPClient.METHOD_POST, body)

func get_game_state():
	print("📥 Запрашиваем состояние")
	http.request(Global.server_url + "/state")

func _on_request_completed(result, response_code, headers, body):
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)
	
	if error == OK:
		var data = json.data
		if data.has("success"):
			if data.has("variant"):  # /new
				print("✅ Игра создана")
				get_game_state()
			elif data.has("state"):  # /state
				print("✅ Состояние получено")
				game_state = data["state"]
				draw_game()

func draw_game():
	# Очищаем старые карты
	for child in get_children():
		if child is Sprite2D:
			child.queue_free()
	
	# Рисуем КОЛОДУ (stock)
	var stock = game_state["stock"]
	if stock["cards"].size() > 0:
		var card = stock["cards"][0]
		draw_card(card, stock_pos, false)
	
	# Рисуем СБРОС (waste)
	var waste = game_state["waste"]
	if waste["cards"].size() > 0:
		var card = waste["cards"][-1]  # верхняя карта
		draw_card(card, waste_pos, true)
	
	# Рисуем СТОЛБЦЫ (tableau)
	for i in range(7):
		var pile_name = "tableau_" + str(i)
		var pile = game_state["piles"][pile_name]
		var cards = pile["cards"]
		
		var x = tableau_start_x + i * (CARD_WIDTH + 20)
		for j in range(cards.size()):
			var card = cards[j]
			var y = tableau_start_y + j * STACK_OFFSET
			draw_card(card, Vector2(x, y), card["face_up"])

func draw_card(card_data, position, face_up):
	var sprite = Sprite2D.new()
	
	if face_up:
		var suit = card_data["suit"]
		var rank = int(card_data["rank"])  # ← ВОТ ГЛАВНОЕ ИСПРАВЛЕНИЕ!
		
		# Словарь для преобразования
		var rank_names = {
			1: "ace",
			11: "jack", 
			12: "queen",
			13: "king"
		}
		
		var suit_names = {
			"HEARTS": "hearts",
			"DIAMONDS": "diamonds",
			"CLUBS": "clubs", 
			"SPADES": "spades"
		}
		
		var rank_str = rank_names.get(rank, str(rank))
		var suit_str = suit_names[suit]
		var filename = rank_str + "_of_" + suit_str + ".png"
		
		var texture = load("res://assets/cards/" + filename)
		if texture:
			sprite.texture = texture
		else:
			print("❌ Нет файла: ", filename)
	else:
		var texture = load("res://assets/cards/back.png")
		if texture:
			sprite.texture = texture
	
	sprite.position = position
	sprite.scale = Vector2(CARD_SCALE, CARD_SCALE)
	add_child(sprite)
