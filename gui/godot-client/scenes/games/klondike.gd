extends Control

var http = HTTPRequest.new()
var game_state = null
var timer = 0.0
var game_time = 0
var is_busy = false
var first_move_made = false
var timer_active = false
var last_request_type = ""

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var score_label = $Display/MainLayout/CountersContainer/ScoreLabel
@onready var moves_label = $Display/MainLayout/CountersContainer/MovesLabel
@onready var time_label = $Display/MainLayout/CountersContainer/TimeLabel
@onready var game_over_panel = $Display/MainLayout/GameOverPanel  # Если есть
@onready var win_label = $Display/MainLayout/GameOverPanel/WinLabel
@onready var final_score = $Display/MainLayout/GameOverPanel/FinalScoreLabel

@onready var new_game_button = $Display/MainLayout/Buttons/NewGameButton
@onready var undo_button = $Display/MainLayout/Buttons/UndoButton
@onready var menu_button = $Display/MainLayout/Buttons/MenuButton

# ===== ССЫЛКИ НА ИГРОВЫЕ ЭЛЕМЕНТЫ =====
@onready var stock_slot = $Display/MainLayout/UpperRow/StockSlot
@onready var waste_slot = $Display/MainLayout/UpperRow/WasteSlot

# === БАЗЫ ПО ИНДЕКСАМ ===
@onready var foundation_0 = $Display/MainLayout/UpperRow/FoundationsGroup/Foundation0
@onready var foundation_1 = $Display/MainLayout/UpperRow/FoundationsGroup/Foundation1
@onready var foundation_2 = $Display/MainLayout/UpperRow/FoundationsGroup/Foundation2
@onready var foundation_3 = $Display/MainLayout/UpperRow/FoundationsGroup/Foundation3

# === TABLEAU СЛОТЫ ===
@onready var tableau_slots = [
	$Display/MainLayout/LowerRow/Tableau_0,
	$Display/MainLayout/LowerRow/Tableau_1,
	$Display/MainLayout/LowerRow/Tableau_2,
	$Display/MainLayout/LowerRow/Tableau_3,
	$Display/MainLayout/LowerRow/Tableau_4,
	$Display/MainLayout/LowerRow/Tableau_5,
	$Display/MainLayout/LowerRow/Tableau_6,
]

const CARD_SCALE = 0.2
const STACK_OFFSET = 30  # Вертикальный отступ между картами в столбце

func _ready():
	add_child(http)
	http.request_completed.connect(_on_request_completed)

	# Подключаем кнопки
	new_game_button.pressed.connect(_on_new_game_pressed)
	undo_button.pressed.connect(_on_undo_pressed)
	menu_button.pressed.connect(_on_menu_pressed)

	# === ОБЛАСТЬ ДЛЯ КЛИКА ПО КОЛОДЕ ===
	var click_area = Area2D.new()
	click_area.name = "StockClickArea"
	var collision = CollisionShape2D.new()
	var rect = RectangleShape2D.new()
	rect.size = Vector2(100, 145)
	collision.shape = rect
	click_area.add_child(collision)
	collision.position = Vector2(rect.size.x / 2, rect.size.y / 2)
	click_area.input_pickable = true
	click_area.connect("input_event", _on_stock_clicked)
	stock_slot.add_child(click_area)
# === ОТЛАДКА ПОЗИЦИЙ ===
	print("📍 Глобальные позиции слотов:")
	print("  StockSlot: ", stock_slot.global_position)
	print("  Foundation0: ", foundation_0.global_position)
	print("  Tableau_0: ", tableau_slots[0].global_position)
	start_new_game()

func start_new_game():
	print("🎮 Новая игра (Klondike)")
	game_time = 0
	timer = 0
	first_move_made = false
	timer_active = false
	update_time_display()
	if game_over_panel:
		game_over_panel.hide()
	var body = '{"variant":"klondike"}'
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/new", headers, HTTPClient.METHOD_POST, body)

func _process(delta):
	if game_state and (not game_over_panel or not game_over_panel.visible) and timer_active:
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
	is_busy = false
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)

	if error == OK:
		var data = json.data
		if data.has("variant"):
			print("✅ Игра создана, запрашиваем состояние...")
			get_game_state()
			return
		
		if data.has("success"):
			if data["success"] == true:
				if data.has("state") and data["state"] != null:
					game_state = data["state"]
					update_ui()
					draw_game()
					if not first_move_made and (last_request_type == "move" or last_request_type == "draw"):
						first_move_made = true
						timer_active = true
						print("⏱️ Первый ход сделан (" + last_request_type + "), таймер запущен")
					
					if data.has("game_won") and data["game_won"]:
						show_win()
			else:
				printerr("⚠️ Ошибка сервера: ", data.get("error", "Unknown error"))
	else:
		printerr("❌ Ошибка парсинга JSON")

func update_ui():
	if game_state:
		score_label.text = "Счет: %d" % game_state["score"]
		moves_label.text = "Ходы: %d" % game_state["moves_count"]

func show_win():
	if game_over_panel:
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
			last_request_type = "draw"
			http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)

func _on_new_game_pressed():
	start_new_game()
	last_request_type = ""

func _on_undo_pressed():
	print("↩ Отмена хода")
	var body = '{}'
	var headers = ["Content-Type: application/json"]
	last_request_type = "undo"
	http.request(Global.server_url + "/undo", headers, HTTPClient.METHOD_POST, body)

func _on_menu_pressed():
	print("🏠 Возврат в меню")
	get_tree().change_scene_to_file("res://scenes/menu.tscn")

# ===== ОТРИСОВКА =====

func draw_game():
	# Очищаем старые карты из всех слотов
	_clear_cards_from_slot(stock_slot)
	_clear_cards_from_slot(waste_slot)
	
	for i in 4:
		_clear_cards_from_slot(foundation_slots()[i])
	
	for slot in tableau_slots:
		_clear_cards_from_slot(slot)
	
	draw_stock()
	draw_waste()
	draw_foundations()
	draw_tableau()

func _clear_cards_from_slot(slot: Control):
	for child in slot.get_children():
		if child.name.begins_with("Card_"):
			child.queue_free()

func foundation_slots():
	return [foundation_0, foundation_1, foundation_2, foundation_3]

func draw_stock():
	var stock = game_state["stock"]
	var waste = game_state["waste"]

	if stock["cards"].size() > 0:
		var card = stock["cards"][0]
		draw_card(card, stock_slot, "stock")
	elif waste["cards"].size() > 0:
		# Рисуем заглушку для пустой колоды
		var sprite = Sprite2D.new()
		sprite.name = "Card_EmptyStock"
		sprite.texture = DeckManager.get_back_texture()
		sprite.modulate = Color(1, 1, 1, 0.3)
		sprite.centered = false
		sprite.scale = Vector2(CARD_SCALE, CARD_SCALE)
		stock_slot.add_child(sprite)

func draw_waste():
	var waste = game_state["waste"]
	if waste["cards"].size() > 0:
		var cards = waste["cards"]
		var start_idx = max(0, cards.size() - 3)
		for i in range(start_idx, cards.size()):
			var card = cards[i]
			var offset = (i - start_idx) * 10
			var pos = Vector2(offset, -offset)
			draw_card(card, waste_slot, "waste", pos)

func draw_foundations():
	var slots = foundation_slots()
	
	for i in 4:
		var pile_name = "foundation_" + str(i)
		var slot_node = slots[i]
		
		if game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			if pile["cards"].size() > 0:
				var card = pile["cards"][-1]  # Верхняя карта
				draw_card(card, slot_node, pile_name)
			# Если база пуста — ничего не рисуем (нейтральный слот)

func draw_tableau():
	for i in range(7):
		var pile_name = "tableau_" + str(i)
		var pile = game_state["piles"][pile_name]
		var cards = pile["cards"]
		var slot_node = tableau_slots[i]
		
		for j in range(cards.size()):
			var card = cards[j]
			var y_offset = j * STACK_OFFSET
			var pos = Vector2(0, y_offset)
			draw_card(card, slot_node, pile_name, pos)

# Было:
# parent_slot.add_child(area)

# Стало:
func draw_card(card_data, parent_slot: Control, pile_name: String, offset: Vector2 = Vector2(0, 0)):
	# === НАЙДИ CardLayer ВНУТРИ СЛОТА ===
	var card_layer = parent_slot.get_node_or_null("CardLayer")
	
	# Если CardLayer нет — создаём его на лету (защита от ошибок)
	if card_layer == null:
		card_layer = Node2D.new()
		card_layer.name = "CardLayer"
		parent_slot.add_child(card_layer)
	
	# === СОЗДАЁМ КАРТУ ===
	var area = Area2D.new()
	area.name = "Card_" + str(randi())
	area.position = offset  # Позиция относительно CardLayer
	area.scale = Vector2(CARD_SCALE, CARD_SCALE)

	var sprite = Sprite2D.new()
	var suit = card_data["suit"]
	var rank = int(card_data["rank"])
	sprite.texture = DeckManager.get_card_texture(suit, rank, card_data["face_up"])

	if sprite.texture == null:
		sprite.modulate = Color.RED

	sprite.centered = false
	area.add_child(sprite)

	var collision = CollisionShape2D.new()
	var rect = RectangleShape2D.new()

	if sprite.texture:
		var w = sprite.texture.get_width()
		var h = sprite.texture.get_height()
		rect.size = Vector2(w, h)
		collision.position = Vector2(w / 2.0, h / 2.0)

	collision.shape = rect
	area.add_child(collision)

	area.input_event.connect(_on_card_clicked.bind(pile_name, card_data))

	# === ДОБАВЛЯЕМ В CardLayer, А НЕ В СЛОТ НАПРЯМУЮ ===
	card_layer.add_child(area)

func _on_card_clicked(viewport, event, shape_idx, pile_name, card_data):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if is_busy:
			return
		
		if pile_name == "stock":
			print("🃏 Клик по колоде -> Взять карту")
			var body = '{}'
			var headers = ["Content-Type: application/json"]
			http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
			return

		if not card_data["face_up"]:
			print("ℹ️ Карта закрыта. Автоход невозможен.")
			return

		print("🃏 Клик по карте: ", card_data["rank"], " ", card_data["suit"], " из стопки: ", pile_name)
		last_request_type = "move"
		var body = JSON.new().stringify({"from": pile_name})
		var headers = ["Content-Type: application/json"]
		http.request(Global.server_url + "/auto_move", headers, HTTPClient.METHOD_POST, body)
