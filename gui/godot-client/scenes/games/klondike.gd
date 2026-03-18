# gui/godot-client/scenes/games/klondike.gd

extends Control

var http = HTTPRequest.new()
var game_state = null
var timer = 0.0
var game_time = 0
var is_busy = false
var first_move_made = false
var timer_active = false
var last_request_type = ""
var is_game_active = false	  # Игра началась (первый ход сделан)
var current_game_id = null	  # ID игры от сервера
var current_seed = 0          # Переменная для хранения сида
var is_first_win = true	      # Переменная для хранения статуса победы
var is_replay_mode = false
# ===== DRAG AND DROP =====
var is_dragging = false
var drag_source_pile = ""
var drag_card_data = null
var dragged_card_node = null # Ссылка на узел карты, которую тянем
var drag_offset = Vector2()  # Смещение, чтобы карта не прыгала центром к курсору
var drag_nodes = [] # Список всех перетаскиваемых узлов

const CARD_ASPECT_RATIO = 1.4 

const MIN_CARD_WIDTH = 80
const MAX_CARD_WIDTH = 180
const HORIZONTAL_MARGIN = 40

# Настройки отступов (в процентах от высоты карты)
var offset_hidden_ratio = 0.15   # Закрытые карты: 15% от высоты (компактно)
var offset_face_up_ratio = 0.25  # Открытые карты: 25% от высоты (удобно читать)

# Текущие вычисленные отступы (в пикселях)
var stack_offset_hidden = 20
var stack_offset_face_up = 35

# Текущие динамические размеры (будут меняться при ресайзе)
var card_width = 100  # Начальное значение
var card_height = 140
#var stack_offset_y = 30  # Смещение карт в стопке по вертикали
#var stack_offset_waste = 10 # Смещение в сбросе (веер)

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var score_label = $Display/MainLayout/CountersContainer/ScoreLabel
@onready var moves_label = $Display/MainLayout/CountersContainer/MovesLabel
@onready var time_label = $Display/MainLayout/CountersContainer/TimeLabel
@onready var game_over_panel = $Display/GameOverPanel
@onready var win_label = $Display/GameOverPanel/VBoxContainer/WinLabel
@onready var final_score = $Display/GameOverPanel/VBoxContainer/FinalScoreLabel
@onready var seed_label = $Display/MainLayout/CountersContainer/SeedLabel

@onready var new_game_button = $Display/MainLayout/Buttons/NewGameButton
@onready var undo_button = $Display/MainLayout/Buttons/UndoButton
@onready var menu_button = $Display/MainLayout/Buttons/MenuButton
@onready var surrender_button = $Display/MainLayout/Buttons/SurrenderButton
@onready var replay_button = $Display/MainLayout/Buttons/ReplayButton

# ===== ССЫЛКИ НА ИГРОВЫЕ ЭЛЕМЕНТЫ =====
@onready var stock_slot = $Display/MainLayout/UpperRow/StockSlot
@onready var waste_slot = $Display/MainLayout/UpperRow/WasteSlot

@onready var foundation_0 = $Display/MainLayout/UpperRow/Foundation0
@onready var foundation_1 = $Display/MainLayout/UpperRow/Foundation1
@onready var foundation_2 = $Display/MainLayout/UpperRow/Foundation2
@onready var foundation_3 = $Display/MainLayout/UpperRow/Foundation3

@onready var tableau_slots = [
	$Display/MainLayout/LowerRow/Tableau_0,
	$Display/MainLayout/LowerRow/Tableau_1,
	$Display/MainLayout/LowerRow/Tableau_2,
	$Display/MainLayout/LowerRow/Tableau_3,
	$Display/MainLayout/LowerRow/Tableau_4,
	$Display/MainLayout/LowerRow/Tableau_5,
	$Display/MainLayout/LowerRow/Tableau_6,
]

func _ready():
	add_child(http)
	http.request_completed.connect(_on_request_completed)

	# Подключаем кнопки
	new_game_button.pressed.connect(_on_new_game_pressed)
	undo_button.pressed.connect(_on_undo_pressed)
	menu_button.pressed.connect(_on_menu_pressed)

	if surrender_button:
		surrender_button.pressed.connect(_on_surrender_pressed)
		
	if replay_button:
		replay_button.pressed.connect(_on_replay_pressed)

		# Настройка фильтров мыши
	stock_slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	waste_slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for slot in foundation_slots():
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for slot in tableau_slots:
		slot.mouse_filter = Control.MOUSE_FILTER_IGNORE
		
	if game_over_panel:
		game_over_panel.hide()

	# === ЛОГИКА СТАРТА ===
	# Проверяем, передали ли нам состояние для загрузки из Меню
	if Global.has_pending_save():
		print("📥 Загрузка переданного состояния...")
		_load_from_global_state()
	else:
		print("🆕 Запрос новой игры...")
		start_new_game(true)
	update_layout()

func _resized():
	# Эта функция вызывается Godot-ом автоматически при изменении размеров узла
	update_layout()

# ===== УПРАВЛЕНИЕ ИГРОЙ =====

func _load_from_global_state():
	"""Загрузить игру из данных, переданных через Global"""
	print("📦 _load_from_global_state() вызван")
	
	# Сначала копируем данные
	game_state = Global.pending_game_state.duplicate(true)  # Глубокая копия!
	game_time = Global.pending_game_time
	current_game_id = Global.pending_game_id
	current_seed = Global.pending_game_state.get("seed", 0)
	
	print("   game_state скопирован. Размер: ", game_state.size())
	print("   game_time: ", game_time)
	print("   current_game_id: ", current_game_id)
	print("   current_seed: ", current_seed)
	
	
	# --- ДИАГНОСТИКА ---
	if game_state:
		print("📦 Загруженное состояние. Ключи: ", game_state.keys())
		# Проверим наличие важных ключей
		var required_keys = ["piles", "stock", "waste", "score", "moves_count"]
		for key in required_keys:
			print("   has '", key, "': ", game_state.has(key))
	else:
		printerr("❌ game_state is null!")
		return
	# -------------------
	
	# ТЕПЕРЬ можно очистить Global
	Global.clear_pending_save()
	
	update_ui()
	update_time_display()
	update_layout()
	
	var moves = game_state.get("moves_count", 0)
	
	if moves > 0:
		is_game_active = true
		first_move_made = true
		timer_active = true
		print("✅ Игра восстановлена. Ходов: ", moves)

func update_ui():
	if game_state:
		var score = game_state.get("score", 0)
		var moves = game_state.get("moves_count", 0)
		
		score_label.text = "Счет: %d" % score
		moves_label.text = "Ходы: %d" % moves
		
		# Если вы хотите помечать игры, запущенные через кнопку "Replay"
		if seed_label:
			if is_replay_mode: # Эта переменная должна быть объявлена как var is_replay_mode = false
				seed_label.text = "Сид: %d (Повтор)" % current_seed
			else:
				seed_label.text = "Сид: %d" % current_seed

func start_new_game(force_new: bool = true, specific_seed = null):
	# <--- [7] Добавлен аргумент specific_seed для возможности перезапуска
	print("🎮 Запрос новой игры (force_new: %s, seed: %s)" % [force_new, specific_seed])
	game_time = 0
	timer = 0
	first_move_made = false
	timer_active = false
	is_game_active = false
	current_game_id = null
	update_time_display()
	if game_over_panel:
		game_over_panel.hide()

	var payload = {
		"variant": "klondike", 
		"player_id": Global.player_id,
		"force_new": force_new
	}
	
	# <--- [8] Если передан конкретный сид, добавляем его в запрос
	if specific_seed != null and specific_seed > 0:
		payload["seed"] = specific_seed

	var body = JSON.new().stringify(payload)
	var headers = ["Content-Type: application/json"]
	last_request_type = "new"
	http.request(Global.server_url + "/new", headers, HTTPClient.METHOD_POST, body)

func _process(delta):
	# Опционально: Автосохранение каждые 60 секунд
	#if game_time % 60 == 0:
		#_auto_save()
	# Таймер
	if game_state and (not game_over_panel or not game_over_panel.visible) and timer_active:
		timer += delta
		if timer >= 1.0:
			timer = 0
			game_time += 1
			update_time_display()
	# Перетаскивание
	if is_dragging and dragged_card_node:
		var mouse_pos = get_global_mouse_position()
		dragged_card_node.global_position = mouse_pos - drag_offset
		
		# Двигаем хвост
		for i in range(1, drag_nodes.size()):
			var node = drag_nodes[i]
			var offset_from_head = node.get_meta("drag_offset_from_head", Vector2.ZERO)
			node.global_position = dragged_card_node.global_position + offset_from_head

func update_time_display():
	var minutes = game_time / 60
	var seconds = game_time % 60
	time_label.text = "Время: %02d:%02d" % [minutes, seconds]

# ===== СЕТЕВОЕ ВЗАИМОДЕЙСТВИЕ =====
func _auto_save():
	if not is_game_active or not game_state:
		return
		
	# ИСПРАВЛЕНО: Используем .get()
	var moves = game_state.get("moves_count", 0)
	print("💾 Автосохранение... (Ходов: %d, Время: %d)" % [moves, game_time])
	
	var body = JSON.new().stringify({
		"player_id": Global.player_id,
		"game_type": "klondike",
		"time_elapsed": game_time
	})
	var headers = ["Content-Type: application/json"]
	var save_http = HTTPRequest.new()
	add_child(save_http)
	save_http.request(Global.server_url + "/save", headers, HTTPClient.METHOD_POST, body)

func _on_request_completed(result, response_code, headers, body):
	is_busy = false
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)

	if error == OK:
		var data = json.data
		if data.has("success"):
			if data["success"] == true:
				# === Успешный ответ ===

				# 1. Создана новая игра
				if last_request_type == "new":
					print("✅ Новая игра создана")
					if data.has("state"):
						game_state = data.state
						current_game_id = data.get("game_id")
						
						# === ИСПРАВЛЕНИЕ: Поиск сида ===
						# 1. Сначала ищем сид в корне ответа (сервера обычно шлют его тут)
						var received_seed = data.get("seed", 0)
						
						# 2. Если в корне нет, ищем внутри state
						if received_seed == 0 and game_state.has("seed"):
							received_seed = game_state.get("seed", 0)
						
						current_seed = received_seed
						print("📝 Получен сид: ", current_seed)
						# ================================
						
						update_ui()
						update_layout()
					return
				
				# 2. Сдача (Abandon)
				if last_request_type == "abandon":
					print("🏳️ Игра сдана")
					return
				
				# 3. Ход / Отмена / Взятие карты
				if data.has("state") and data["state"] != null:
					var game_won = data.get("game_won", false)
					game_state = data["state"]
					update_ui()
					update_layout()
					
					# Запуск таймера при первом ходе
					if not first_move_made and (last_request_type == "move" or last_request_type == "draw"):
						first_move_made = true
						timer_active = true
						is_game_active = true
						print("⏱️ Таймер запущен")
					
					# Победа
					if game_won:
						# Сохраняем статус победы (первая или повторная)
						is_first_win = data.get("is_first_win", true)
						show_win()
						
			else:
				# === Ошибка логики ===
				var err_code = data.get("error")
				printerr("⚠️ Ошибка сервера: ", err_code)
				# Тут можно добавить обработку ошибок (например, показать Alert)
		else:
			printerr("⚠️ Некорректный формат ответа")
	else:
		printerr("❌ Ошибка парсинга JSON")


func show_win():
	if game_over_panel:
		game_over_panel.show()
		
		# Проверяем флаг первой победы
		if is_first_win:
			# --- ПЕРВАЯ ПОБЕДА (Зачетная) ---
			win_label.text = "🎉 ПОБЕДА!"
			final_score.text = "Счет: " + str(game_state["score"])
			# Можно добавить эффекты или звуки победы
		else:
			# --- ПОВТОРНАЯ ПОБЕДА (Практика) ---
			win_label.text = "🏆 ПОВТОРНЫЙ РЕКОРД"
			final_score.text = "Счет: " + str(game_state["score"]) + " (Практика)"
			
		timer_active = false
		is_game_active = false

# ===== ОБРАБОТЧИКИ КНОПОК =====

func _on_new_game_pressed():
	# Если игра уже идет, спросить подтверждение
	is_replay_mode = false
	if is_game_active:
		var dialog = ConfirmationDialog.new()
		dialog.dialog_text = "Начать новую игру? Текущий прогресс будет потерян."
		dialog.title = "Новая игра"
		dialog.confirmed.connect(start_new_game.bind(true))
		add_child(dialog)
		dialog.popup_centered()
	else:
		start_new_game(true)
	last_request_type = ""

func _on_undo_pressed():
	print("↩ Отмена хода")
	var body = '{}'
	var headers = ["Content-Type: application/json"]
	last_request_type = "undo"
	http.request(Global.server_url + "/undo", headers, HTTPClient.METHOD_POST, body)

func _on_menu_pressed():
	print("🏠 Возврат в меню")
	# Автосохранение перед выходом
	_auto_save()
	# Небольшая задержка для отправки запроса
	await get_tree().create_timer(0.2).timeout
	get_tree().change_scene_to_file("res://scenes/menu.tscn")

func _on_surrender_pressed():
	print("🏳️ Сдаться")
	var dialog = ConfirmationDialog.new()
	dialog.dialog_text = "Вы уверены, что хотите сдаться? Игра будет засчитана как проигрыш."
	dialog.title = "Сдаться"
	dialog.confirmed.connect(_confirm_surrender)
	add_child(dialog)
	dialog.popup_centered()

func _on_replay_pressed():
	print("🔄 Повтор игры с сидом: ", current_seed)
	is_replay_mode = true
	# Если игра активна, можно спросить подтверждение, но обычно это не требуется, 
	# так как игрок намеренно хочет переиграть.
	start_new_game(true, current_seed)

func _confirm_surrender():
	last_request_type = "abandon"
	is_game_active = false
	timer_active = false  # ← ОСТАНОВИТЬ ТАЙМЕР!
	var body = JSON.new().stringify({
		"player_id": Global.player_id,
		"game_type": "klondike",
		"time": game_time
	})
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/abandon", headers, HTTPClient.METHOD_POST, body)

# Уведомление о закрытии окна
func _notification(what):
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		print("💾 Сохранение перед выходом...")
		_auto_save()
		get_tree().quit()

# ===== ОТРИСОВКА =====

# ============================================================
# ЭТАП 3: МАСШТАБИРОВАНИЕ И РАЗМЕТКА
# ============================================================

# Функция пересчета размеров. Вызывается при старте и ресайзе.
func update_layout():
	# 1. Получаем доступную ширину для игрового поля (7 колонок)
	# Используем LowerRow, так как там 7 колонок
	var available_width = $Display/MainLayout/LowerRow.size.x
	# === ИЗМЕНЕНИЕ: Вычитаем отступы по краям ===
	available_width -= HORIZONTAL_MARGIN
	
	# Учитываем отступы между колонками (separation)
	var separation = $Display/MainLayout/LowerRow.get_theme_constant("separation")
	var total_separation = separation * 6 # 6 промежутков между 7 колонками
	
	# Ширина одной колонки (слота)
	# Делим (Доступная ширина - Отступы) на 7 колонок
	var calculated_width = (available_width - total_separation) / 7
	
	# 2. Применяем ограничения (Limits)
	calculated_width = clamp(calculated_width, MIN_CARD_WIDTH, MAX_CARD_WIDTH)
	
	# Обновляем глобальные переменные размера
	card_width = calculated_width
	card_height = card_width * CARD_ASPECT_RATIO
	
	# 3. Рассчитываем "идеальные" отступы (в пикселях)
	# Идеальные отступы до того, как мы узнаем, влезают ли они
	var ideal_hidden = card_height * offset_hidden_ratio
	var ideal_face_up = card_height * offset_face_up_ratio
	
	# 4. Проверка на переполнение высоты (Smart Compression)
	# Нам нужно найти самую длинную стопку и убедиться, что она влезает
	var available_height = $Display/MainLayout/LowerRow.size.y
	
	# Если игра уже идет (есть state), проверяем стопки
	if game_state and game_state.has("piles"):
		# Находим максимальную высоту среди всех 7 колонок
		var max_content_height = 0
		
		for i in range(7):
			var pile_name = "tableau_" + str(i)
			if game_state["piles"].has(pile_name):
				var pile = game_state["piles"][pile_name]
				# Считаем высоту этой стопки при ИДЕАЛЬНЫХ отступах
				var h = _calculate_pile_height(pile["cards"], ideal_hidden, ideal_face_up)
				if h > max_content_height:
					max_content_height = h
		
		# Сравниваем с доступной высотой
		# +50 пикселей запаса снизу, чтобы не прилипало к краю
		if max_content_height > (available_height - 50):
			# НЕ ВЛЕЗАЕТ! Включаем сжатие.
			# Вычисляем коэффициент сжатия
			var scale_factor = (available_height - 50) / max_content_height
			
			# Уменьшаем отступы пропорционально
			ideal_hidden *= scale_factor
			ideal_face_up *= scale_factor
			
			# Жесткий ограничитель: отступ не может быть меньше 5 пикселей
			if ideal_hidden < 5: ideal_hidden = 5
			if ideal_face_up < 5: ideal_face_up = 5
	
	# Применяем итоговые значения
	stack_offset_hidden = ideal_hidden
	stack_offset_face_up = ideal_face_up
	
	# 5. Применяем размеры к слотам (чтобы контейнеры перестроились)
	_apply_slot_sizes()
	
	# 6. Перерисовываем карты, если игра идет
	if game_state:
		draw_game()


# Вспомогательная функция: считает высоту стопки
# cards: массив карт
# o_hidden: отступ для закрытых
# o_face_up: отступ для открытых
func _calculate_pile_height(cards: Array, o_hidden: float, o_face_up: float) -> float:
	if cards.size() == 0:
		return 0
	
	# Высота начинается с одной карты (высота последней карты)
	var total_height = card_height
	
	# Проходим по всем картам, кроме последней (снизу вверх), и добавляем отступы
	# Логика: отступ зависит от карты, которая лежит НИЖЕ (текущая в цикле)
	for i in range(cards.size() - 1):
		var current_card = cards[i]
		
		if current_card["face_up"]:
			total_height += o_face_up
		else:
			total_height += o_hidden
			
	return total_height


# Применение размеров к узлам-слотам
func _apply_slot_sizes():
	var slot_size = Vector2(card_width, card_height)
	
	# Верхний ряд
	stock_slot.custom_minimum_size = slot_size
	waste_slot.custom_minimum_size = slot_size
	for f in foundation_slots():
		f.custom_minimum_size = slot_size
	
	# Нижний ряд (Табло)
	for t in tableau_slots:
		t.custom_minimum_size = slot_size



func draw_game():
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
	# 1. Очищаем слой карт (CardLayer)
	var card_layer = slot.get_node_or_null("CardLayer")
	if card_layer:
		for child in card_layer.get_children():
			child.queue_free()
	
	# 2. Очищаем всё, что лежит прямо в слоте (карты или EmptyStock)
	for child in slot.get_children():
		# Удаляем карты и индикатор пустой колоды
		if child.name.begins_with("Card_") or child.name == "EmptyStock":
			child.queue_free()

func foundation_slots():
	return [foundation_0, foundation_1, foundation_2, foundation_3]

func draw_stock():
	if not game_state.has("stock") or not game_state.has("waste"):
		return

	var stock = game_state["stock"]
	var waste = game_state["waste"]

	# 1. В колоде есть карты
	if stock["cards"].size() > 0:
		var card = stock["cards"][0]
		draw_card(card, stock_slot, "stock")
		
	# 2. Колода пуста, но в сбросе есть карты (можно перевернуть)
	elif waste["cards"].size() > 0:
		# Очистка теперь происходит в draw_game -> _clear_cards...
		# Поэтому просто создаем индикатор
		var empty_stock = TextureRect.new()
		empty_stock.name = "EmptyStock"
		empty_stock.texture = DeckManager.get_back_texture()
		empty_stock.modulate = Color(1, 1, 1, 0.3)
		empty_stock.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		empty_stock.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		empty_stock.custom_minimum_size = Vector2(card_width, card_height)
		empty_stock.mouse_filter = Control.MOUSE_FILTER_STOP
		empty_stock.gui_input.connect(_on_empty_stock_clicked)
		stock_slot.add_child(empty_stock)
		
	# 3. Колода пуста И сброс пуст (всё разобрано)
	# -> Ничего не делаем, функция _clear_cards_from_slot всё убрала

func _on_empty_stock_clicked(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if is_busy:
			return
		print("🃏 Recycle: Взять карту из сброса")
		var body = '{}'
		var headers = ["Content-Type: application/json"]
		last_request_type = "draw"
		http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
		
func draw_waste():
	if not game_state.has("waste"):
		return
	var waste = game_state["waste"]
	if waste["cards"].size() > 0:
		var cards = waste["cards"]
		var start_idx = max(0, cards.size() - 3)
		for i in range(start_idx, cards.size()):
			var card = cards[i]
			var offset = (i - start_idx) * (card_width * 0.15)
			var pos = Vector2(offset, 0)
			draw_card(card, waste_slot, "waste", pos)

func draw_foundations():
	var slots = foundation_slots()
	for i in 4:
		var pile_name = "foundation_" + str(i)
		var slot_node = slots[i]
		
		# Используем .has для проверки
		if game_state.has("piles") and game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			if pile["cards"].size() > 0:
				var card = pile["cards"][-1]
				draw_card(card, slot_node, pile_name)

func draw_tableau():
	if not game_state.has("piles"):
		return

	for i in range(7):
		var pile_name = "tableau_" + str(i)
		
		if game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			var cards = pile["cards"]
			var slot_node = tableau_slots[i]

			# Начальная координата Y для первой карты
			var current_y = 0.0

			for j in range(cards.size()):
				var card = cards[j]
				
				# Рисуем карту в текущей позиции
				# Передаем j как индекс, так как вычислить его из координат теперь нельзя
				draw_card(card, slot_node, pile_name, Vector2(0, current_y), j)
				
				# Вычисляем отступ для СЛЕДУЮЩЕЙ карты
				# Логика: если текущая карта открыта, следующая сдвигается сильнее
				if card["face_up"]:
					current_y += stack_offset_face_up
				else:
					current_y += stack_offset_hidden

func draw_card(card_data, parent_slot: Control, pile_name: String, offset: Vector2 = Vector2(0, 0), card_index: int = 0):
	var card_layer = parent_slot.get_node_or_null("CardLayer")
	if card_layer == null:
		card_layer = Node2D.new()
		card_layer.name = "CardLayer"
		parent_slot.add_child(card_layer)
	
	var card_id = str(card_data.get("suit", "")) + "_" + str(card_data.get("rank", ""))
	var card_control = Control.new()
	card_control.name = "Card_" + card_id + "_" + str(randi())
	card_control.position = offset
	
	# === ИЗМЕНЕНИЕ 1: Устанавливаем размер корневого контрола ===
	# Это нужно, чтобы область клика (mouse_filter) совпадала с визуальным размером карты
	card_control.custom_minimum_size = Vector2(card_width, card_height)
	card_control.size = Vector2(card_width, card_height) 
	card_control.mouse_filter = Control.MOUSE_FILTER_STOP
	
	# === НОВОЕ: Запоминаем индекс карты в стопке ===
	card_control.set_meta("card_index", card_index)

	# --- Создаем визуальную часть (текстуру) ---
	var texture_rect = TextureRect.new()
	texture_rect.name = "Texture"
	
	var suit = card_data["suit"]
	var rank = int(card_data["rank"])
	texture_rect.texture = DeckManager.get_card_texture(suit, rank, card_data["face_up"])

	if texture_rect.texture == null:
		texture_rect.modulate = Color.RED
	
	# === ИЗМЕНЕНИЕ 2: Настраиваем масштабирование текстуры ===
	# Текстура должна заполнить весь card_control, сохраняя пропорции
	texture_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	
	# Размер текстуры равен размеру карты
	texture_rect.custom_minimum_size = Vector2(card_width, card_height)
	texture_rect.size = Vector2(card_width, card_height)
	# -------------------------------------------------------

	card_control.add_child(texture_rect)

	# Подключаем сигнал
	card_control.gui_input.connect(_on_card_clicked.bind(pile_name, card_data, card_control))
	card_layer.add_child(card_control)
	
	return card_control

func _on_card_clicked(event, pile_name, card_data, card_node):
	
	# === Обработка нажатий ===
	if event is InputEventMouseButton and event.pressed:
		
		# --- Левая кнопка: Перетаскивание ---
		if event.button_index == MOUSE_BUTTON_LEFT:
			if is_busy:
				return
			if pile_name == "stock":
				print("🃏 Клик по колоде -> Взять карту")
				var body = '{}'
				var headers = ["Content-Type: application/json"]
				last_request_type = "draw"
				http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
				return
			if not card_data["face_up"]:
				return
			print("🖱️ Начало перетаскивания из: ", pile_name)
			is_dragging = true
			drag_source_pile = pile_name
			drag_card_data = card_data 
			dragged_card_node = card_node
			# Находим все карты ниже (для стопок) ===
			drag_nodes.clear() # Очищаем список перед использованием
			drag_nodes.append(card_node) # Добавляем саму карту
			# Если это tableau, ищем карты под ней в том же слое
			if pile_name.begins_with("tableau"):
				var card_layer = card_node.get_parent()
				if card_layer:
					# Получаем индекс текущей карты
					var my_index = card_node.get_meta("card_index", 0)
					# Проходим по всем детям слоя и добавляем те, что ниже
					for child in card_layer.get_children():
						if child == card_node: continue
						if child.get_meta("card_index", -1) > my_index:
							drag_nodes.append(child)
			# Сортируем по индексу, чтобы они красиво летели вместе
			drag_nodes.sort_custom(func(a, b): return a.get_meta("card_index", 0) < b.get_meta("card_index", 0))
			# Запоминаем смещения хвоста относительно головы
			var head_pos = card_node.global_position
			for i in range(1, drag_nodes.size()):
				var node = drag_nodes[i]
				# Сохраняем разницу в координатах
				node.set_meta("drag_offset_from_head", node.global_position - head_pos)
			# Эффекты
			for node in drag_nodes:
				node.z_index = 100
			
			var mouse_pos = get_global_mouse_position()
			drag_offset = mouse_pos - card_node.global_position
			
		# --- Правая кнопка: Авто-ход ---
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			if is_busy:
				return
			
			if pile_name == "stock":
				return 

			if not card_data["face_up"]:
				return

			print("🃏 Авто-ход (ПКМ) из: ", pile_name)
			last_request_type = "move"
			var body = JSON.new().stringify({"from": pile_name})
			var headers = ["Content-Type: application/json"]
			http.request(Global.server_url + "/auto_move", headers, HTTPClient.METHOD_POST, body)
	
	# === Обработка отпускания ===
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if is_dragging:
			print("🏁 Отпускание карты")
			# Здесь будет логика сброса карты
			_end_drag() 
			
func _end_drag():
	if not is_dragging:
		return
	# Сбрасываем Z-index
	for node in drag_nodes:
		node.z_index = 0
	# Очищаем метаданные (опционально, для порядка)
	for node in drag_nodes:
		if node.has_meta("drag_offset_from_head"):
			node.remove_meta("drag_offset_from_head")
	var target_pile = _get_pile_under_mouse()
	# Считаем количество карт ===
	var move_count = drag_nodes.size()
	if target_pile != "" and target_pile != drag_source_pile:
		print("📂 Перенос ", move_count, " карт в: ", target_pile)
		last_request_type = "move"
		var body = JSON.new().stringify({
			"from": drag_source_pile,
			"to": target_pile,
			"count": move_count  # <--- ОТПРАВЛЯЕМ КОЛИЧЕСТВО
		})
		var headers = ["Content-Type: application/json"]
		http.request(Global.server_url + "/move", headers, HTTPClient.METHOD_POST, body)
		
		is_busy = true
	else:
		draw_game()
	# Сброс переменных
	is_dragging = false
	drag_source_pile = ""
	drag_card_data = null
	dragged_card_node = null
	drag_nodes.clear() # Очищаем список

func _get_pile_under_mouse() -> String:
	var mouse_pos = get_global_mouse_position()
	
	# Список всех стопок для проверки
	var all_slots = []
	
	# 1. Foundations (дома)
	for i in range(4):
		var node = foundation_slots()[i]
		all_slots.append({"name": "foundation_" + str(i), "node": node})
	
	# 2. Tableau (колонки)
	for i in range(7):
		var node = tableau_slots[i]
		all_slots.append({"name": "tableau_" + str(i), "node": node})
	
	# 3. Waste (сброс)
	all_slots.append({"name": "waste", "node": waste_slot})
	
	# Проверяем попадание
	for slot_info in all_slots:
		var node = slot_info["node"]
		var rect = node.get_global_rect()
		
		# ВАЖНО: Для Tableau расширим зону захвата вниз до конца экрана
		if slot_info["name"].begins_with("tableau"):
			# Получаем высоту видимой области экрана
			var screen_height = get_viewport().get_visible_rect().size.y
			# Новая высота = (Низ экрана) - (Верхняя граница слота)
			# Это гарантирует, что зона захвата продлится до самого низа окна
			rect.size.y = screen_height - rect.position.y
		
		if rect.has_point(mouse_pos):
			return slot_info["name"]
			
	return ""
