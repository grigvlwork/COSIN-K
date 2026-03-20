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
var is_animating = false      # Флаг, что идет анимация (чтобы не кликать лишнего)
var pending_action_context = {} # Данные о текущем действии для анимации
var shadow_material = null # Кэшированный материал для теней

# ===== DRAG AND DROP =====
var is_dragging = false
var drag_source_pile = ""
var drag_card_data = null
var dragged_card_node = null # Ссылка на узел карты, которую тянем
var drag_offset = Vector2()  # Смещение, чтобы карта не прыгала центром к курсору
var drag_nodes = [] # Список всех перетаскиваемых узлов

const CARD_ASPECT_RATIO = 1.4 
const MIN_CARD_WIDTH = 80
const MAX_CARD_WIDTH = 140
const HORIZONTAL_MARGIN = 40
const MIN_OFFSET_RATIO = 0.15   # Минимальный допуск отступа (15% от высоты карты)
const TARGET_SHRINK_RATIO = 0.25 # Целевой отступ при уменьшении карты (25%)
const SCREEN_MARGIN = 20
const CRITICAL_OFFSET_RATIO = 0.15

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
	# Откладываем расчет на следующий кадр, чтобы Godot успел обновить размеры контейнеров
	call_deferred("update_layout")

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
		
		# === ПРОВЕРКА УСПЕШНОСТИ ===
		if data.has("success"):
			
			if data["success"] == true:
				# --- УСПЕШНЫЙ ХОД ---
				
				# 1. Обновляем данные
				if data.has("state") and data["state"] != null:
					game_state = data["state"]
				
				# 2. Запуск таймера (при первом ходе)
				if not first_move_made and (last_request_type == "draw" or last_request_type == "auto_move" or last_request_type == "manual_move"):
					first_move_made = true
					timer_active = true
					is_game_active = true

				# 3. Логика Победы
				var game_won = data.get("game_won", false)
				if game_won:
					is_first_win = data.get("is_first_win", true)
					update_ui()
					draw_game() # Финальная отрисовка
					show_win()
					pending_action_context = {}
					return # Выходим, дальше ничего делать не надо

				# 4. Обновляем интерфейс (счет, ходы)
				update_ui()
				
				# === АНИМАЦИЯ УСПЕХА (Шаг 3) ===
				var context_type = pending_action_context.get("type", "")
				
				if context_type == "manual_move":
					# Ручной ход
					var nodes = pending_action_context.get("nodes", [])
					var target_pile = pending_action_context.get("target_pile", "")
					var count = pending_action_context.get("count", 1)
					
					if nodes.size() > 0 and target_pile != "":
						_animate_success_flight(nodes, target_pile, count)
					else:
						draw_game()
						
				elif context_type == "auto_move":
					# Авто-ход: берем цель из ответа сервера
					if data.has("move"):
						var move_info = data["move"]
						var target_pile = move_info["to"]
						var count = move_info["count"]
						var nodes = pending_action_context.get("nodes", [])
						
						if nodes.size() > 0:
							_animate_success_flight(nodes, target_pile, count)
						else:
							draw_game()
					else:
						draw_game()
						
				elif last_request_type == "draw":
					# Для взятия карт пока оставляем мгновенную смену
					draw_game()
				else:
					# Для new, undo и т.д.
					draw_game()

				pending_action_context = {}
				
			else:
				# --- ОШИБКА ХОДА ---
				var err_code = data.get("error")
				printerr("⚠️ Ошибка сервера: ", err_code)
				
				# РАЗБИРАЕМ КОНТЕКСТ
				var context_type = pending_action_context.get("type", "")
				
				if context_type == "auto_move":
					# Авто-ход не удался -> Трясем карту
					# Берем первый узел из списка (карта, по которой кликнули)
					var nodes = pending_action_context.get("nodes", [])
					if nodes.size() > 0 and is_instance_valid(nodes[0]):
						_animate_shake(nodes[0])
				
				elif context_type == "manual_move":
					# Ручной ход не удался -> Возвращаем карты
					var nodes = pending_action_context.get("nodes", [])
					var positions = pending_action_context.get("start_positions", [])
					if nodes.size() > 0:
						_animate_return(nodes, positions)
				
				# Сбрасываем контекст после обработки ошибки
				pending_action_context = {}
				
		else:
			printerr("⚠️ Некорректный формат ответа (нет ключа success)")
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

func update_layout():
	# 1. РАСЧЕТ ШИРИНЫ
	var viewport_size = get_viewport().get_visible_rect().size
	var available_width = viewport_size.x - SCREEN_MARGIN * 2
	
	var separation = $Display/MainLayout/LowerRow.get_theme_constant("separation")
	var calculated_width = (available_width - separation * 6) / 7
	calculated_width = clamp(calculated_width, MIN_CARD_WIDTH, MAX_CARD_WIDTH)
	
	card_width = calculated_width
	card_height = card_width * CARD_ASPECT_RATIO
	
	# 2. РАСЧЕТ ВЫСОТЫ (Матеметически, без чтения size.y контейнеров)
	# Это разрывает петлю обратной связи!
	
	var vbox = $Display/MainLayout
	var vbox_sep = vbox.get_theme_constant("separation")
	
	# Высота, которую едят интерфейсы (кроме карт)
	var static_ui_height = $Display/MainLayout/CountersContainer.size.y + \
						   $Display/MainLayout/Buttons.size.y + \
						   (vbox_sep * 3) + \
						   SCREEN_MARGIN # Запас снизу
	
	# Свободное место для ВЕРТИКАЛЬНОЙ ЛОГИКИ:
	# Нам нужно вместить: 1 карту (UpperRow) + Стопку (LowerRow)
	var available_vertical_space = viewport_size.y - static_ui_height
	
	# 3. АНАЛИЗ СТОПОК
	var max_hidden = 0
	var max_face_up = 0
	
	if game_state and game_state.has("piles"):
		for i in range(7):
			var pile_name = "tableau_" + str(i)
			if game_state["piles"].has(pile_name):
				var pile = game_state["piles"][pile_name]
				var composition = _get_pile_composition(pile["cards"])
				if (composition.hidden + composition.face_up) > (max_hidden + max_face_up):
					max_hidden = composition.hidden
					max_face_up = composition.face_up
	
	# 4. ЛОГИКА МАСШТАБИРОВАНИЯ (Глобальная)
	
	# Считаем отступы (N-1)
	var hidden_offsets_count = max(0, max_hidden - 1)
	if max_hidden > 0 and max_face_up > 0:
		hidden_offsets_count += 1
	var face_up_offsets_count = max(0, max_face_up - 1)
	
	var ideal_r_h = offset_hidden_ratio
	var ideal_r_f = offset_face_up_ratio
	
	# Формула общей занимаемой высоты:
	# TotalHeight = UpperCard + LowerPile
	# TotalHeight = card_h + (card_h + card_h*(hidden_offs*r_h + face_up_offs*r_f))
	# TotalHeight = card_h * (2 + hidden_offs*r_h + face_up_offs*r_f)
	
	var total_height_factor = 2.0 + (hidden_offsets_count * ideal_r_h) + (face_up_offsets_count * ideal_r_f)
	var ideal_total_height = card_height * total_height_factor
	
	# Фактор для критического режима
	var critical_factor = 2.0 + (hidden_offsets_count * CRITICAL_OFFSET_RATIO) + (face_up_offsets_count * CRITICAL_OFFSET_RATIO)
	
	# --- ЭТАП 1: ИДЕАЛЬНО ---
	if ideal_total_height <= available_vertical_space:
		# Всё влезает, используем стандартные отступы
		stack_offset_hidden = card_height * ideal_r_h
		stack_offset_face_up = card_height * ideal_r_f
		
	# --- ЭТАП 2: СЖАТИЕ ОТСТУПОВ ---
	elif (card_height * critical_factor) <= available_vertical_space:
		# Влезает только если сжать отступы. Карту НЕ трогаем.
		# Нам нужно найти такие offset_r, чтобы:
		# card_h * (2 + hid*offset + face*offset) = available_space
		
		var needed_height_factor = available_vertical_space / card_height
		var available_offset_pool = needed_height_factor - 2.0 # То, что осталось на отступы
		
		var ideal_offset_pool = (hidden_offsets_count * ideal_r_h) + (face_up_offsets_count * ideal_r_f)
		
		if ideal_offset_pool > 0:
			var scale_k = available_offset_pool / ideal_offset_pool
			stack_offset_hidden = card_height * ideal_r_h * scale_k
			stack_offset_face_up = card_height * ideal_r_f * scale_k
			
			# Ограничитель
			var min_abs = card_height * CRITICAL_OFFSET_RATIO
			if stack_offset_hidden < min_abs: stack_offset_hidden = min_abs
			if stack_offset_face_up < min_abs: stack_offset_face_up = min_abs
		else:
			stack_offset_hidden = 0
			stack_offset_face_up = 0
			
	# --- ЭТАП 3: УМЕНЬШЕНИЕ КАРТЫ ---
	else:
		# Не влезает даже с минимальными отступами.
		# Считаем новый размер карты.
		# card_h_new * critical_factor = available_space
		
		var new_card_height = available_vertical_space / critical_factor
		
		card_height = new_card_height
		card_width = card_height / CARD_ASPECT_RATIO
		
		stack_offset_hidden = card_height * CRITICAL_OFFSET_RATIO
		stack_offset_face_up = card_height * CRITICAL_OFFSET_RATIO

	# 5. ПРИМЕНЕНИЕ
	_apply_slot_sizes()
	if game_state:
		draw_game()

# Вспомогательная функция для подсчета состава стопки
func _get_pile_composition(cards: Array) -> Dictionary:
	var hidden = 0
	var face_up = 0
	for card in cards:
		if card["face_up"]:
			face_up += 1
		else:
			hidden += 1
	return {"hidden": hidden, "face_up": face_up}


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
			child.queue_free() # Удаляем карты из памяти
			
	# 2. Очищаем всё, что лежит прямо в слоте (EmptyStock или "потерянные" карты)
	for child in slot.get_children():
		# Проверяем имя. CardLayer мы пропускаем, его удалять не надо, он часть слота.
		if child.name != "CardLayer":
			child.hide()              # 1. Скрываем визуально
			slot.remove_child(child)  # 2. ВЫБРАСЫВАЕМ из дерева (решает проблему призраков)
			child.queue_free()        # 3. Удаляем из памяти

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
		var empty_stock = TextureRect.new()
		empty_stock.name = "EmptyStock"
		empty_stock.texture = DeckManager.get_back_texture()
		empty_stock.modulate = Color(1, 1, 1, 0.3)
		empty_stock.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		empty_stock.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		
		# === ВАЖНО: Задаем и minimum, и реальный size ===
		var target_size = Vector2(card_width, card_height)
		empty_stock.custom_minimum_size = target_size
		empty_stock.size = target_size 
		# ==============================================
		
		empty_stock.mouse_filter = Control.MOUSE_FILTER_STOP
		empty_stock.gui_input.connect(_on_empty_stock_clicked)
		stock_slot.add_child(empty_stock)

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
			# Адаптивный отступ для веера (например, 10% от ширины карты)
			var offset = (i - start_idx) * (card_width * 0.15) 
			var pos = Vector2(offset, 0)
			draw_card(card, waste_slot, "waste", pos)

func draw_foundations():
	var slots = foundation_slots()
	for i in 4:
		var pile_name = "foundation_" + str(i)
		var slot_node = slots[i]

		if game_state.has("piles") and game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			var cards = pile["cards"]

			# --- ИЗМЕНЕНИЕ ---
			# Рисуем ВСЕ карты в стопке, а не только последнюю.
			# Карты накладываются друг на друга (offset = 0).
			# Порядок добавления (от 0 к последней) гарантирует,
			# что верхняя карта визуально перекроет нижние.
			for j in range(cards.size()):
				var card = cards[j]
				# Передаем индекс j, хотя для фундамента это не критично
				draw_card(card, slot_node, pile_name, Vector2(0, 0), j)

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
# === 1. СОЗДАЕМ ТЕНЬ (ПОД КАРТОЙ) ===
	var shadow_rect = TextureRect.new()
	shadow_rect.name = "Shadow"
	
	var suit = card_data["suit"]
	var rank = int(card_data["rank"])
	var card_texture = DeckManager.get_card_texture(suit, rank, card_data["face_up"])
	
	shadow_rect.texture = card_texture
	
	# === ПРИМЕНЯЕМ ШЕЙДЕР ВМЕСТО ПРОСТОГО ОКРАШИВАНИЯ ===
	shadow_rect.material = _get_shadow_material()
	
	# Смещение тени (эффект толщины карты)
	shadow_rect.position = Vector2(3, 3) 
	
	shadow_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	shadow_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	shadow_rect.custom_minimum_size = Vector2(card_width, card_height)
	shadow_rect.size = Vector2(card_width, card_height)
	shadow_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	
	card_control.add_child(shadow_rect)
	# === 2. СОЗДАЕМ ВИЗУАЛЬНУЮ ЧАСТЬ (ТЕКСТУРА КАРТЫ) ===
	var texture_rect = TextureRect.new()
	texture_rect.name = "Texture"
	texture_rect.texture = card_texture

	if texture_rect.texture == null:
		texture_rect.modulate = Color.RED
	
	texture_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	texture_rect.custom_minimum_size = Vector2(card_width, card_height)
	texture_rect.size = Vector2(card_width, card_height)
	
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
						# Сначала проверяем и выходим, если нельзя тянуть
			if not card_data["face_up"]:
				return
			
			print("🖱️ Начало перетаскивания из: ", pile_name)
			is_dragging = true
			drag_source_pile = pile_name
			drag_card_data = card_data 
			dragged_card_node = card_node
			
			# 1. ЗАПОЛНЯЕМ СПИСОК drag_nodes
			drag_nodes.clear() 
			drag_nodes.append(card_node) 
			
			if pile_name.begins_with("tableau"):
				var card_layer = card_node.get_parent()
				if card_layer:
					var my_index = card_node.get_meta("card_index", 0)
					for child in card_layer.get_children():
						if child == card_node: continue
						if child.get_meta("card_index", -1) > my_index:
							drag_nodes.append(child)
			
			drag_nodes.sort_custom(func(a, b): return a.get_meta("card_index", 0) < b.get_meta("card_index", 0))
			
			# 2. Запоминаем смещения хвоста
			var head_pos = card_node.global_position
			for i in range(1, drag_nodes.size()):
				var node = drag_nodes[i]
				node.set_meta("drag_offset_from_head", node.global_position - head_pos)
			
			# 3. ПРИМЕНЯЕМ ЭФФЕКТЫ (Z-index и ТЕНЬ) - ТЕПЕРЬ СПИСОК ПОЛОН
			for node in drag_nodes:
				node.z_index = 100
				# === УВЕЛИЧИВАЕМ ТЕНЬ ===
				var shadow = node.get_node_or_null("Shadow")
				if shadow:
					shadow.modulate = Color(1, 1, 1, 0.7) # Делаем тень чуть ярче поверх шейдера
					shadow.position = Vector2(10, 10)     # Смещаем тень (эффект подъема)
			
			var mouse_pos = get_global_mouse_position()
			drag_offset = mouse_pos - card_node.global_position
			
# --- Правая кнопка: Авто-ход ---
		elif event.button_index == MOUSE_BUTTON_RIGHT:
			if is_busy or is_animating:
				return
			
			if pile_name == "stock":
				return 

			if not card_data["face_up"]:
				return

			print("🃏 Авто-ход (ПКМ) из: ", pile_name)
			
			# === ИЗМЕНЕНИЕ: Собираем стек карт, как при перетаскивании ===
			var nodes_stack = [card_node] # Начинаем с той, на которую нажали
			
			# Если это tableau, ищем карты под ней (хвост)
			if pile_name.begins_with("tableau"):
				var card_layer = card_node.get_parent()
				if card_layer:
					var my_index = card_node.get_meta("card_index", 0)
					# Собираем все карты, у которых индекс больше нашего
					for child in card_layer.get_children():
						if child == card_node: continue
						if child.get_meta("card_index", -1) > my_index:
							nodes_stack.append(child)
			
			# Сортируем и запоминаем смещения (чтобы красиво летели кучей)
			nodes_stack.sort_custom(func(a, b): return a.get_meta("card_index", 0) < b.get_meta("card_index", 0))
			
			# Запоминаем взаимное расположение (чтобы "хвост" летел за "головой")
			# Это полезно, если анимация полета будет сложной, 
			# но для простого полета достаточно передать список узлов.
			
			# Сохраняем контекст
			pending_action_context = {
				"type": "auto_move",
				"source_pile": pile_name,
				"nodes": nodes_stack,  # <--- ТЕПЕРЬ ЭТО МАССИВ УЗЛОВ
				"count": nodes_stack.size()
			}
			last_request_type = "auto_move"
			
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
		
	# === ИЗМЕНЕНИЕ: Сохраняем всё, что нужно для анимации, ПЕРЕД сбросом переменных ===
	# Копируем список узлов, так как drag_nodes очистится
	var nodes_to_animate = drag_nodes.duplicate()
	
	# Запоминаем стартовые позиции (на случай возврата)
	var start_positions = []
	for node in nodes_to_animate:
		start_positions.append(node.global_position)
	
	# Сбрасываем Z-index
	for node in nodes_to_animate:
		node.z_index = 0
	
	# Очищаем метаданные
	for node in nodes_to_animate:
		if node.has_meta("drag_offset_from_head"):
			node.remove_meta("drag_offset_from_head")
			
	var target_pile = _get_pile_under_mouse()
	var move_count = nodes_to_animate.size()
	
	if target_pile != "" and target_pile != drag_source_pile:
		print("📂 Перенос ", move_count, " карт в: ", target_pile)
		
		# === СОХРАНЯЕМ КОНТЕКСТ ДЛЯ РУЧНОГО ХОДА ===
		pending_action_context = {
			"type": "manual_move",
			"nodes": nodes_to_animate,
			"start_positions": start_positions,
			"source_pile": drag_source_pile,
			"target_pile": target_pile,
			"count": move_count # <--- Добавить это
		}
		
		last_request_type = "manual_move"
		var body = JSON.new().stringify({
			"from": drag_source_pile,
			"to": target_pile,
			"count": move_count
		})
		var headers = ["Content-Type: application/json"]
		http.request(Global.server_url + "/move", headers, HTTPClient.METHOD_POST, body)
		
		is_busy = true
	else:
		# Если отпустили в пустом месте или в той же стопке — просто возвращаем на место
		draw_game()
	
	# Сброс переменных перетаскивания
	is_dragging = false
	drag_source_pile = ""
	drag_card_data = null
	dragged_card_node = null
	drag_nodes.clear()

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

# ===== АНИМАЦИИ =====

func _animate_success_flight(nodes: Array, target_pile: String, move_count: int):
	"""Запускает анимацию полета карт к целевой стопке"""
	is_animating = true
	
	# 1. Создаем слой для полета (поверх всего)
	var flying_layer = Control.new()
	flying_layer.name = "FlyingLayer"
	flying_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Добавляем в $Display, чтобы координаты совпадали
	$Display.add_child(flying_layer)
	
	# 2. Создаем "призраков" (копии летящих карт)
	var ghosts = []
	for i in range(nodes.size()):
		var original_node = nodes[i]
		if not is_instance_valid(original_node): continue
		
		var ghost = Control.new()
		ghost.size = original_node.size
		ghost.global_position = original_node.global_position
		
		# === ДОБАВЛЯЕМ ТЕНЬ К ПРИЗРАКУ ===
		var ghost_shadow = TextureRect.new()
		ghost_shadow.texture = original_node.get_node("Texture").texture
		
		# Применяем тот же шейдер размытия, что и у обычных карт
		ghost_shadow.material = _get_shadow_material() 
		
		ghost_shadow.position = Vector2(10, 10)  # Сильное смещение
		ghost_shadow.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		ghost_shadow.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ghost_shadow.size = original_node.size
		ghost_shadow.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ghost.add_child(ghost_shadow)
		
		# Копируем текстуру самой карты
		var tex_rect = TextureRect.new()
		tex_rect.texture = original_node.get_node("Texture").texture
		tex_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		tex_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tex_rect.size = original_node.size
		ghost.add_child(tex_rect) # Потом карта
		
		flying_layer.add_child(ghost)
		ghosts.append(ghost)
		
		original_node.hide()
	
	# 3. Рисуем новое состояние (карты появятся в новых местах)
	draw_game()
	
	# 4. Вычисляем, где оказались карты (и прячем их, чтобы показать призраков)
	# Нам нужно знать индексы в НОВОЙ стопке.
	# Карты добавляются в конец стопки.
	var pile_data = null
	if target_pile.begins_with("tableau"):
		pile_data = game_state["piles"][target_pile]
	elif target_pile.begins_with("foundation"):
		pile_data = game_state["piles"][target_pile]
	elif target_pile == "waste":
		pile_data = game_state["waste"]
		
	var targets = []
	if pile_data:
		var total_cards = pile_data["cards"].size()
		# Индекс первой летящей карты
		var start_idx = total_cards - move_count
		
		for i in range(move_count):
			var idx = start_idx + i
			var pos = _get_card_global_position(target_pile, idx)
			targets.append(pos)
			
			# Находим реальный узел в слоте и прячем его
			var slot = null
			if target_pile.begins_with("tableau"):
				var t_idx = int(target_pile.split("_")[1])
				slot = tableau_slots[t_idx]
			elif target_pile.begins_with("foundation"):
				var f_idx = int(target_pile.split("_")[1])
				slot = foundation_slots()[f_idx]
			elif target_pile == "waste":
				slot = waste_slot
			
			if slot:
				var card_layer = slot.get_node_or_null("CardLayer")
				if card_layer and card_layer.get_child_count() > idx:
					# Прячем реальную карту в конечной точке
					card_layer.get_child(idx).hide()
	
	# 5. Анимация Tween
	var tween = create_tween()
	tween.set_parallel(true)
	
	for i in range(ghosts.size()):
		if targets.size() > i:
			tween.tween_property(ghosts[i], "global_position", targets[i], 0.25).set_ease(Tween.EASE_OUT)
		else:
			ghosts[i].hide() # Если цель не найдена, просто исчезаем
			
	# Ждем окончания
	tween.set_parallel(false)
	tween.tween_interval(0.3)
	
	tween.tween_callback(func():
		flying_layer.queue_free() # Удаляем призраков
		draw_game() # Перерисовываем, чтобы реальные карты стали видимыми
		is_animating = false
	)

func _animate_shake(control_node: Control):
	"""Анимация тряски карты (отказ при авто-ходе)"""
	if not is_instance_valid(control_node): return
	is_animating = true
	
	var tween = create_tween()
	var start_pos = control_node.position
	var shake_amount = 10 # Амплитуда тряски
	var duration = 0.05
	
	# Трясем влево-вправо 3 раза
	tween.tween_property(control_node, "position", start_pos + Vector2(shake_amount, 0), duration)
	tween.tween_property(control_node, "position", start_pos + Vector2(-shake_amount, 0), duration)
	tween.tween_property(control_node, "position", start_pos + Vector2(shake_amount, 0), duration)
	tween.tween_property(control_node, "position", start_pos + Vector2(-shake_amount, 0), duration)
	tween.tween_property(control_node, "position", start_pos, duration)
	
	tween.tween_callback(func(): is_animating = false)

func _animate_return(nodes: Array, positions: Array):
	"""Анимация возврата карт на исходную позицию (ошибка перетаскивания)"""
	is_animating = true
	var tween = create_tween()
	tween.set_parallel(true) # Двигаем все карты одновременно
	
	for i in range(nodes.size()):
		var node = nodes[i]
		if is_instance_valid(node):
			# Поднимаем Z_index, чтобы карты летели поверх остальных
			node.z_index = 100 
			tween.tween_property(node, "global_position", positions[i], 0.2).set_ease(Tween.EASE_OUT)
	
	# В конце сбрасываем флаг и Z_index
	tween.set_parallel(false)
	tween.tween_callback(func():
		is_animating = false
		for node in nodes:
			if is_instance_valid(node):
				node.z_index = 0
		# Перерисовываем, чтобы карточки "встали" в слоты корректно
		draw_game() 
	)

func _get_card_global_position(pile_name: String, card_index: int) -> Vector2:
	"""Вычисляет глобальную позицию карты на основе состояния игры"""
	var slot_node = null
	var y_offset = 0.0
	
	# 1. Определяем узел слота и базовые смещения
	if pile_name == "waste":
		slot_node = waste_slot
		# Логика веера для waste (как в draw_waste)
		var cards = game_state["waste"]["cards"]
		var start_idx = max(0, cards.size() - 3)
		if card_index >= start_idx:
			y_offset = (card_index - start_idx) * (card_width * 0.15)
		else:
			# Если карта ушла в "тень" или не в веере, берем последнюю позицию веера
			y_offset = 2 * (card_width * 0.15) 

	elif pile_name.begins_with("foundation"):
		var idx = int(pile_name.split("_")[1])
		slot_node = foundation_slots()[idx]
		# В foundation смещения нет (карты лежат ровно)
		y_offset = 0
		
	elif pile_name.begins_with("tableau"):
		var idx = int(pile_name.split("_")[1])
		slot_node = tableau_slots[idx]
		# Для tableau суммируем отступы всех карт ВЫШЕ искомой
		var pile_data = game_state["piles"][pile_name]
		for i in range(card_index):
			if i < pile_data["cards"].size():
				var c = pile_data["cards"][i]
				if c["face_up"]:
					y_offset += stack_offset_face_up
				else:
					y_offset += stack_offset_hidden
	else:
		return Vector2.ZERO

	if not slot_node:
		return Vector2.ZERO
		
	# Глобальная позиция = Позиция слота + смещение внутри
	return slot_node.global_position + Vector2(0, y_offset)
	
func _get_shadow_material():
	# Если уже создавали, возвращаем готовый
	if shadow_material:
		return shadow_material
		
	# Создаем код шейдера
	var shader_code = """
	shader_type canvas_item;
	render_mode blend_mix; // Обычное смешивание

	void fragment() {
		// Простой эффект размытия краев (Box Blur 3x3)
		vec2 pixel_size = TEXTURE_PIXEL_SIZE;
		vec4 color = vec4(0.0); // Черный цвет

		float alpha_sum = 0.0;

		// Сэмплируем 9 точек вокруг для размытия
		for (int x = -1; x <= 1; x++) {
			for (int y = -1; y <= 1; y++) {
			    alpha_sum += texture(TEXTURE, UV + vec2(float(x), float(y)) * pixel_size * 2.0).a;
			}
		}
        
		// Усредняем и применяем прозрачность
		float avg_alpha = alpha_sum / 9.0;

		// Затемняем и делаем полупрозрачным
		COLOR = vec4(0.0, 0.0, 0.0, avg_alpha * 0.5); 
	}
	"""
	
	var shader = Shader.new()
	shader.code = shader_code
	
	shadow_material = ShaderMaterial.new()
	shadow_material.shader = shader
	
	return shadow_material
