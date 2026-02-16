extends Node2D

var http = HTTPRequest.new()
var game_state = null
var timer = 0.0
var game_time = 0

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var score_label = $UI/ScoreLabel
@onready var moves_label = $UI/MovesLabel
@onready var time_label = $UI/TimeLabel
@onready var game_over_panel = $UI/GameOverPanel
@onready var win_label = $UI/GameOverPanel/WinLabel
@onready var final_score = $UI/GameOverPanel/FinalScoreLabel

@onready var new_game_button = $UI/Buttons/NewGameButton
@onready var undo_button = $UI/Buttons/UndoButton
@onready var menu_button = $UI/Buttons/MenuButton

# ===== ССЫЛКИ НА ИГРОВЫЕ ЭЛЕМЕНТЫ (ВСЕ ВНУТРИ Deck) =====
@onready var stock_holder = $Deck/StockHolder
@onready var waste_holder = $Deck/WasteHolder

# Базы внутри Deck
@onready var foundation_hearts = $Deck/FoundationHearts
@onready var foundation_diamonds = $Deck/FoundationDiamonds
@onready var foundation_clubs = $Deck/FoundationClubs
@onready var foundation_spades = $Deck/FoundationSpades

# Позиции для карт (используем Holder'ы как позиции)
@onready var stock_pos = $Deck/StockHolder
@onready var waste_pos = $Deck/WasteHolder

# TableauPositions в корне
@onready var tableau_positions = $TableauPositions

const CARD_SCALE = 0.2
const CARD_WIDTH = 500 * CARD_SCALE
const CARD_HEIGHT = 726 * CARD_SCALE
const STACK_OFFSET = 30

func _ready():
	add_child(http)
	http.request_completed.connect(_on_request_completed)
	
	# Подключаем кнопки
	new_game_button.pressed.connect(_on_new_game_pressed)
	undo_button.pressed.connect(_on_undo_pressed)
	menu_button.pressed.connect(_on_menu_pressed)
	
	# СОЗДАЕМ КЛИКАБЕЛЬНУЮ ОБЛАСТЬ ДЛЯ КОЛОДЫ
	var click_area = Area2D.new()
	var collision = CollisionShape2D.new()
	var rect = RectangleShape2D.new()
	rect.size = Vector2(100, 145)  # размер карты
	collision.shape = rect
	
	click_area.add_child(collision)
	click_area.position = Vector2(0, 0)
	click_area.input_pickable = true
	click_area.connect("input_event", _on_stock_clicked)
	
	stock_holder.add_child(click_area)
	print("✅ Кликабельная область добавлена на колоду")
	
	start_new_game()

func start_new_game():
	print("🎮 Новая игра")
	game_time = 0
	timer = 0
	game_over_panel.hide()
	var body = '{"variant":"klondike"}'
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/new", headers, HTTPClient.METHOD_POST, body)

func _process(delta):
	if game_state and not game_over_panel.visible:
		timer += delta
		if timer >= 1.0:
			timer = 0
			game_time += 1
			update_time_display()

func update_time_display():
	var minutes = game_time / 60
	var seconds = game_time % 60
	time_label.text = "Время: %02d:%02d" % [minutes, seconds]

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
				update_ui()
				draw_game()
				
				# Проверяем победу
				if data.has("game_won") and data["game_won"]:
					show_win()

func update_ui():
	if game_state:
		score_label.text = "Счет: " + str(game_state["score"])
		moves_label.text = "Ходы: " + str(game_state["moves_count"])

func show_win():
	game_over_panel.show()
	win_label.text = "🎉 ПОБЕДА!"
	final_score.text = "Счет: " + str(game_state["score"])

# ===== КЛИКИ И КНОПКИ =====

func _on_stock_clicked(viewport, event, shape_idx):
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			print("🃏 Взять карту из колоды")
			var body = '{}'
			var headers = ["Content-Type: application/json"]
			http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)

func _on_new_game_pressed():
	start_new_game()

func _on_undo_pressed():
	print("↩ Отмена хода")
	var body = '{}'
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/undo", headers, HTTPClient.METHOD_POST, body)

func _on_menu_pressed():
	print("🏠 Возврат в меню")
	get_tree().change_scene_to_file("res://menu.tscn")

# ===== ОТРИСОВКА =====

func draw_game():
	for child in get_children():
		if child.name.begins_with("Card_"):
			child.queue_free()
	
	draw_stock()
	draw_waste()
	draw_foundations()
	draw_tableau()

func draw_stock():
	var stock = game_state["stock"]
	if stock["cards"].size() > 0:
		var card = stock["cards"][0]
		draw_card(card, stock_pos.position, false)

func draw_waste():
	var waste = game_state["waste"]
	if waste["cards"].size() > 0:
		var cards = waste["cards"]
		var start_idx = max(0, cards.size() - 3)
		for i in range(start_idx, cards.size()):
			var offset = (i - start_idx) * 10
			var pos = waste_pos.position + Vector2(offset, -offset)
			draw_card(cards[i], pos, cards[i]["face_up"])

func draw_foundations():
	var foundations = [
		{"node": foundation_hearts, "suit": "HEARTS"},
		{"node": foundation_diamonds, "suit": "DIAMONDS"},
		{"node": foundation_clubs, "suit": "CLUBS"},
		{"node": foundation_spades, "suit": "SPADES"}
	]
	
	for f in foundations:
		var pile_name = "foundation_" + f["suit"]
		if game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			if pile["cards"].size() > 0:
				var card = pile["cards"][-1]
				draw_card(card, f["node"].position, true)

func draw_tableau():
	for i in range(7):
		var pile_name = "tableau_" + str(i)
		var pile = game_state["piles"][pile_name]
		var cards = pile["cards"]
		
		var x = tableau_positions.position.x + i * (CARD_WIDTH + 20)
		for j in range(cards.size()):
			var card = cards[j]
			var y = tableau_positions.position.y + j * STACK_OFFSET
			draw_card(card, Vector2(x, y), card["face_up"])

func draw_card(card_data, position, face_up):
	var sprite = Sprite2D.new()
	sprite.name = "Card_" + str(randi())
	
	if face_up:
		var suit = card_data["suit"]
		var rank = int(card_data["rank"])
		
		var rank_names = {1: "ace", 11: "jack", 12: "queen", 13: "king"}
		var suit_names = {
			"HEARTS": "hearts", "DIAMONDS": "diamonds",
			"CLUBS": "clubs", "SPADES": "spades"
		}
		
		var filename = rank_names.get(rank, str(rank)) + "_of_" + suit_names[suit] + ".png"
		sprite.texture = load("res://assets/cards/" + filename)
	else:
		sprite.texture = load("res://assets/cards/back.png")
	
	sprite.position = position
	sprite.scale = Vector2(CARD_SCALE, CARD_SCALE)
	add_child(sprite)
