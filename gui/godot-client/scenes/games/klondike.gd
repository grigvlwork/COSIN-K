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

	# === ОБЛАСТЬ ДЛЯ КЛИКА ПО КОЛОДЕ (ИСПРАВЛЕНО) ===
# Используем Control вместо Area2D для совместимости с Control-иерархией
	var stock_click_area = Control.new()
	stock_click_area.name = "StockClickArea"

# Задаём размер области (под размер карты)
	stock_click_area.custom_minimum_size = Vector2(100, 145)

# Останавливаем события здесь
	stock_click_area.mouse_filter = Control.MOUSE_FILTER_STOP

# ✅ Подключаем gui_input (вместо input_event!)
	stock_click_area.gui_input.connect(_on_stock_clicked)

	stock_slot.add_child(stock_click_area)
	# Для каждого слота (можно добавить в _ready после инициализации):
	stock_slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	waste_slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for slot in foundation_slots():
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for slot in tableau_slots:
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
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

#func _on_stock_clicked(viewport, event, shape_idx):
	#if event is InputEventMouseButton and event.pressed:
		#if event.button_index == MOUSE_BUTTON_LEFT:
			#print("🃏 Взять карту из колоды")
			#var body = '{}'
			#var headers = ["Content-Type: application/json"]
			#last_request_type = "draw"
			#http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)

# ✅ Подпись для gui_input (1 параметр)
func _on_stock_clicked(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
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
	# 1. Ищем CardLayer внутри слота
	var card_layer = slot.get_node_or_null("CardLayer")
	if card_layer:
		# 2. Очищаем карты внутри CardLayer
		for child in card_layer.get_children():
			if child.name.begins_with("Card_"):
				child.queue_free()
	# 3. На всякий случай чистим и прямых детей (защита от старого кода)
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
	if card_layer == null:
		card_layer = Node2D.new()
		card_layer.name = "CardLayer"
		parent_slot.add_child(card_layer)
	
	# === СОЗДАЁМ КАРТУ КАК Control (не Area2D!) ===
	var card_control = Control.new()
	card_control.name = "Card_" + str(randi())
	card_control.position = offset
	card_control.mouse_filter = Control.MOUSE_FILTER_STOP  # Останавливаем события здесь
	card_control.z_index = 100  # Поверх других
	
	# === СПРАЙТ ===
	var sprite = Sprite2D.new()
	var suit = card_data["suit"]
	var rank = int(card_data["rank"])
	sprite.texture = DeckManager.get_card_texture(suit, rank, card_data["face_up"])

	if sprite.texture == null:
		sprite.modulate = Color.RED
	
	sprite.centered = false
	sprite.scale = Vector2(CARD_SCALE, CARD_SCALE)
	# Размер контрола = размеру спрайта
	if sprite.texture:
		card_control.custom_minimum_size = Vector2(
			sprite.texture.get_width() * CARD_SCALE,
			sprite.texture.get_height() * CARD_SCALE
		)
	
	card_control.add_child(sprite)
	
	# === КОЛЛИЗИЯ (для Area2D не нужна, но оставим для совместимости) ===
	# Можно убрать, если используешь только gui_input
	
	# === ПОДКЛЮЧАЕМ gui_input (вместо input_event!) ===
	card_control.gui_input.connect(_on_card_clicked.bind(pile_name, card_data))
	
	# === ДОБАВЛЯЕМ В CardLayer ===
	card_layer.add_child(card_control)

# ✅ Подпись для gui_input: 1 параметр (event) + 2 bound = 3 всего
func _on_card_clicked(event, pile_name, card_data):
	print("🖱️ Клик зарегистрирован! pile_name=", pile_name)

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

# ✅ Правильная подпись для Godot 4.x
#func _on_card_clicked(viewport, event, shape_idx, pile_name, card_data):
	## Проверяем, что это клик левой кнопкой мыши
	#print("🖱️ Клик зарегистрирован! pile_name=", pile_name)
	#if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		#if is_busy:
			#return
		#
		#if pile_name == "stock":
			#print("🃏 Клик по колоде -> Взять карту")
			#var body = '{}'
			#var headers = ["Content-Type: application/json"]
			#http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
			#return
#
		#if not card_data["face_up"]:
			#print("ℹ️ Карта закрыта. Автоход невозможен.")
			#return
#
		#print("🃏 Клик по карте: ", card_data["rank"], " ", card_data["suit"], " из стопки: ", pile_name)
		#last_request_type = "move"
		#var body = JSON.new().stringify({"from": pile_name})
		#var headers = ["Content-Type: application/json"]
		#http.request(Global.server_url + "/auto_move", headers, HTTPClient.METHOD_POST, body)
