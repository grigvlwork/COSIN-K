extends Node2D

var http = HTTPRequest.new()
var game_state = null
var timer = 0.0
var game_time = 0
var is_busy = false

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

	# === ВОЗВРАЩАЕМ ПОСТОЯННУЮ ОБЛАСТЬ ДЛЯ КОЛОДЫ ===
	# Она нужна, чтобы кликать по пустому месту (для переворота колоды)
	var click_area = Area2D.new()
	click_area.name = "StockClickArea" # Даем имя, чтобы не путать с картами
	var collision = CollisionShape2D.new()
	var rect = RectangleShape2D.new()

	# Размер области (подбираем под размер карты)
	rect.size = Vector2(100, 145) 
	collision.shape = rect

	click_area.add_child(collision)
	# Важно: отключаем центрирование коллизии, чтобы она вставала ровно в (0,0)
	collision.position = Vector2(rect.size.x / 2, rect.size.y / 2)

	click_area.input_pickable = true
	click_area.connect("input_event", _on_stock_clicked)

	# Добавляем её ВНУТРЬ stock_holder
	stock_holder.add_child(click_area)

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
	is_busy = false # Снимаем блокировку

	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)

	if error == OK:
		var data = json.data

		# 1. Если это ответ на /new (создание игры)
		if data.has("variant"):
			print("✅ Игра создана, запрашиваем состояние...")
			get_game_state() # Запрашиваем полное состояние отдельным запросом
			return
		
		# 2. Если это ответ на /state или ход
		if data.has("success"):
			if data["success"] == true:
				if data.has("state") and data["state"] != null:
					game_state = data["state"]
					update_ui()
					draw_game()
					
					if data.has("game_won") and data["game_won"]:
						show_win()
			else:
				# Если success: false, выводим ошибку, но не ломаем игру
				printerr("⚠️ Ошибка сервера: ", data.get("error", "Unknown error"))
	else:
		printerr("❌ Ошибка парсинга JSON")

func update_ui():
	if game_state:
		# Используем %d для форматирования как целое число
		score_label.text = "Счет: %d" % game_state["score"]
		moves_label.text = "Ходы: %d" % game_state["moves_count"]

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
	# Удаляем только карты из колоды
	for child in $Deck.get_children():
		if child.name.begins_with("Card_"):
			child.queue_free()
	
	# Удаляем карты из табло (если они там есть)
	# Примечание: если TableauPositions не контейнер, карты могут быть в корне или Deck
	# Для надежности можно очистить и корень, если карты там остались от старого кода
	for child in get_children():
		if child.name.begins_with("Card_"):
			child.queue_free()
	
	draw_stock()
	draw_waste()
	draw_foundations()
	draw_tableau()

func draw_stock():
	var stock = game_state["stock"]
	var waste = game_state["waste"]

	# 1. Очищаем старые карты из StockHolder (кроме нашей постоянной области)
	for child in stock_holder.get_children():
		if child.name.begins_with("Card_"):
			child.queue_free()
			
	# 2. Если в колоде есть карты - рисуем верхнюю
	if stock["cards"].size() > 0:
		var card = stock["cards"][0]
		draw_card(card, Vector2(0, 0), false, stock_holder, "stock")
	
	# 3. Если колода ПУСТА, но в сбросе ЕСТЬ карты - рисуем "пустую" заглушку
	# (Клик по ней сработает через нашу постоянную область из _ready)
	elif waste["cards"].size() > 0:
		# Можно нарисовать специальную карту-заглушку, обозначающую переворот
		# Используем карту с рубашкой, но полупрозрачную, или специальный спрайт
		var sprite = Sprite2D.new()
		sprite.name = "Card_EmptyStock"
		sprite.texture = DeckManager.get_back_texture() # Или load("res://assets/refresh_icon.png")
		sprite.modulate = Color(1, 1, 1, 0.3) # Полупрозрачная, чтобы понять, что карт нет
		sprite.centered = false
		sprite.scale = Vector2(CARD_SCALE, CARD_SCALE)
		stock_holder.add_child(sprite)

func draw_waste():
	var waste = game_state["waste"]
	if waste["cards"].size() > 0:
		var cards = waste["cards"]
		var start_idx = max(0, cards.size() - 3)
		for i in range(start_idx, cards.size()):
			var offset = (i - start_idx) * 10
			var pos = waste_pos.position + Vector2(offset, -offset)
			# Передаем "waste" как имя стопки
			draw_card(cards[i], pos, cards[i]["face_up"], $Deck, "waste")

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
				# Передаем pile_name
				draw_card(card, f["node"].position, true, $Deck, pile_name)
	
func draw_tableau():
	for i in range(7):
		var pile_name = "tableau_" + str(i)
		var pile = game_state["piles"][pile_name]
		var cards = pile["cards"]
		
		var base_x = ($TableauPositions.position.x - $Deck.position.x) + i * (CARD_WIDTH + 20)
		
		for j in range(cards.size()):
			var card = cards[j]
			var y = ($TableauPositions.position.y - $Deck.position.y) + j * STACK_OFFSET
			# Передаем pile_name
			draw_card(card, Vector2(base_x, y), card["face_up"], $Deck, pile_name)

# Добавили аргумент parent_node
# Добавил аргумент pile_name
func draw_card(card_data, position, face_up, parent_node, pile_name):
	var area = Area2D.new()
	area.name = "Card_" + str(randi())
	area.position = position
	area.scale = Vector2(CARD_SCALE, CARD_SCALE)

	# 1. Спрайт
	var sprite = Sprite2D.new()
	var suit = card_data["suit"]
	var rank = int(card_data["rank"])
	sprite.texture = DeckManager.get_card_texture(suit, rank, face_up)

	if sprite.texture == null:
		sprite.modulate = Color.RED

	# Настраиваем спрайт: рисуем от левого верхнего угла (0,0)
	sprite.centered = false 

	area.add_child(sprite)

	# 2. Коллизия
	var collision = CollisionShape2D.new()
	var rect = RectangleShape2D.new()

	if sprite.texture:
		var w = sprite.texture.get_width()
		var h = sprite.texture.get_height()
		rect.size = Vector2(w, h)
		
		# Так как спрайт начинается в (0,0) и идет до (w,h),
		# центр коллизии должен быть в (w/2, h/2)
		collision.position = Vector2(w / 2.0, h / 2.0)

	collision.shape = rect
	area.add_child(collision)

	# 3. Сигнал
	area.input_event.connect(_on_card_clicked.bind(pile_name, card_data))

	parent_node.add_child(area)

func _on_card_clicked(viewport, event, shape_idx, pile_name, card_data):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Защита от спама кликами
		if is_busy:
			return
		# === 1. СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ КОЛОДЫ (STOCK) ===
		# Клик по колоде всегда означает "взять карту", независимо от face_up
		if pile_name == "stock":
			print("🃏 Клик по колоде -> Взять карту")
			var body = '{}'
			var headers = ["Content-Type: application/json"]
			http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
			return # Выходим, не проверяя face_up

		# === 2. ПРОВЕРКА ЗАКРЫТОЙ КАРТЫ ===
		# Для всех остальных стопок (tableau, waste) по закрытым картам ходить нельзя
		if not card_data["face_up"]:
			print("ℹ️ Карта закрыта. Автоход невозможен.")
			return

		# === 3. ОБЫЧНЫЙ АВТОХОД ===
		print("🃏 Клик по карте: ", card_data["rank"], " ", card_data["suit"], " из стопки: ", pile_name)

		var body = JSON.new().stringify({"from": pile_name})
		var headers = ["Content-Type: application/json"]
		http.request(Global.server_url + "/auto_move", headers, HTTPClient.METHOD_POST, body)

		# Отправляем запрос на сервер для автохода
