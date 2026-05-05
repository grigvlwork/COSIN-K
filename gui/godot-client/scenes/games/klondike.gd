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
#var current_game_id = null	  # ID игры от сервера
var _current_game_id = null

var current_game_id:
	set(value):
		print("🧨 current_game_id SET:", value)
		print_stack()
		_current_game_id = value
	get:
		return _current_game_id

var current_seed = 0          # Переменная для хранения сида
var is_first_win = true	      # Переменная для хранения статуса победы
var is_replay_mode = false
var is_animating = false      # Флаг, что идет анимация (чтобы не кликать лишнего)
var pending_action_context = {} # Данные о текущем действии для анимации
var shadow_material = null # Кэшированный материал для теней
var _animating_cards: Dictionary = {}   # Ключ: "pile_name_index", значение: true
var drag_card_ids: Array = []       # Массив ID перетаскиваемых карт
var drag_head_card_id = ""     # ID головной карты
var _pending_new_game_params: Dictionary = {}


# ===== DRAG AND DROP =====
var is_dragging = false
var drag_source_pile = ""
var drag_card_data = null
var dragged_card_node = null # Ссылка на узел карты, которую тянем
var drag_offset = Vector2()  # Смещение, чтобы карта не прыгала центром к курсору
var drag_nodes = [] # Список всех перетаскиваемых узлов

var pressed_card_node = null
var pressed_card_data = null
var pressed_pile_name = ""
var press_mouse_pos = Vector2.ZERO

var drag_started = false
const DRAG_THRESHOLD = 10.0

const CARD_ASPECT_RATIO = 1.54 
const MIN_CARD_WIDTH = 80
const MAX_CARD_WIDTH = 140
const HORIZONTAL_MARGIN = 40
const MIN_OFFSET_RATIO = 0.15   # Минимальный допуск отступа (15% от высоты карты)
const TARGET_SHRINK_RATIO = 0.25 # Целевой отступ при уменьшении карты (25%)
const SCREEN_MARGIN = 20
const CRITICAL_OFFSET_RATIO = 0.15
const ANIMATION_FLIGHT_DURATION: float = 0.20
const ANIMATION_FLIP_DURATION: float = 0.30
const ANIMATION_WASTE_SHIFT_DURATION: float = 0.15

var animations_enabled: bool = true
var animate_flight: bool = true
var animate_flip: bool = true
var animate_waste_shift: bool = true
var is_auto_finishing: bool = false 


# Настройки отступов (в процентах от высоты карты)
var offset_hidden_ratio = 0.15   # Закрытые карты: 15% от высоты (компактно)
var offset_face_up_ratio = 0.25  # Открытые карты: 25% от высоты (удобно читать)

# Текущие вычисленные отступы (в пикселях)
var stack_offset_hidden = 20
var stack_offset_face_up = 35

# Текущие динамические размеры (будут меняться при ресайзе)
var card_width = 100  # Начальное значение
var card_height = 140
var tableau_available_height: float = 0.0
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
@onready var auto_finish_button = $Display/MainLayout/UpperRow/AutoFinishButton

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

	if auto_finish_button:
		auto_finish_button.pressed.connect(_on_auto_finish_pressed)
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
	#print("DEBUG SEED: ", GlobalState.get("seed"))
	#print("DEBUG GAME_DATA: ", GlobalState.get("game_data"))

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
	print("🎮 Запрос новой игры (force_new: %s, seed: %s)" % [force_new, specific_seed])
	print("is_game_active:", is_game_active, " current_game_id:", current_game_id)
	# === 1. Если есть ЛЮБАЯ незавершённая игра — сначала завершаем ===
	if current_game_id != null:
		print("🔄 Найдена незавершённая игра (game_id: %s), сначала завершаем..." % current_game_id)
		# Сохраняем параметры новой игры
		_pending_new_game_params = {
			"force_new": force_new,
			"specific_seed": specific_seed
		}
		_confirm_surrender()  # должен вызвать /game/end
		return
	# === 2. Чистый старт новой игры ===
	print("🆕 Старт новой игры")
	# Сброс локального состояния (НО game_id уже null, это важно)
	game_time = 0
	timer = 0
	first_move_made = false
	timer_active = false
	is_game_active = false
	update_time_display()
	if game_over_panel:
		game_over_panel.hide()
	var payload = {
		"variant": "klondike",
		"player_id": Global.player_id,
		"force_new": force_new
	}

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
	# === НОВОЕ: проверка начала drag ===
	if pressed_card_node and not drag_started:
		var dist = get_global_mouse_position().distance_to(press_mouse_pos)
		if dist > DRAG_THRESHOLD:
			_start_drag()
	if is_dragging and dragged_card_node:
		var mouse_pos = get_global_mouse_position()
		dragged_card_node.global_position = mouse_pos - drag_offset
		
		# Двигаем хвост
		for i in range(1, drag_nodes.size()):
			var node = drag_nodes[i]
			var offset_from_head = node.get_meta("drag_offset_from_head", Vector2.ZERO)
			node.global_position = dragged_card_node.global_position + offset_from_head

func _start_drag():
	if not pressed_card_node:
		return
	
	if pressed_card_node:
		pressed_card_node.set_pressed(false)
	is_dragging = true
	drag_started = true

	var card_node = pressed_card_node
	var card_data = pressed_card_data
	var pile_name = pressed_pile_name

	drag_source_pile = pile_name
	drag_card_data = card_data
	dragged_card_node = card_node

	var card_id = card_node.get_meta("card_id", card_data.get("id", -1))
	drag_head_card_id = card_id

	drag_nodes.clear()
	drag_nodes.append(card_node)
	drag_card_ids = [card_id]

	if pile_name.begins_with("tableau"):
		var slot = card_node.get_parent()
		if slot:
			var my_index = card_node.get_meta("card_index", 0)
			for child in slot.get_children():
				if not is_instance_valid(child):
					continue
				if child == card_node:
					continue
				if child.get_meta("card_index", 0) > my_index:
					drag_nodes.append(child)
					var child_card_id = child.get_meta("card_id", -1)
					if child_card_id != "":
						drag_card_ids.append(child_card_id)

	#drag_nodes.sort_custom(func(a, b): return a.get_meta("card_index", 0) < b.get_meta("card_index", 0))
	drag_nodes = drag_nodes.filter(func(n): return is_instance_valid(n))

	drag_nodes.sort_custom(func(a, b):
		return a.get_meta("card_index", 0) < b.get_meta("card_index", 0)
	)

	var head_pos = card_node.global_position
	for i in range(1, drag_nodes.size()):
		var node = drag_nodes[i]
		node.set_meta("drag_offset_from_head", node.global_position - head_pos)

	for node in drag_nodes:
		node.z_index = 100

	var mouse_pos = get_global_mouse_position()
	drag_offset = mouse_pos - card_node.global_position

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
		#print("📥 RESPONSE: ", data)
		# === ДОСТИЖЕНИЯ (ловим ВСЕГДА) ===
		if data.has("unlocked_achievements"):
			var unlocked = data["unlocked_achievements"]
			if unlocked.size() > 0:
				_handle_new_achievements(unlocked)
		# === ПРОВЕРКА УСПЕШНОСТИ ===
		if last_request_type == "new" and response_code == 200:
			if data.has("game_id"):
				current_game_id = data.game_id
				print("✅ current_game_id установлен: ", current_game_id)
				is_game_active = true
		if data.has("success"):
			if data["success"] == true:
				# --- УСПЕШНОЕ ЗАВЕРШЕНИЕ ИГРЫ ---
				if last_request_type == "end" and response_code == 200:
					print("✅ Игра завершена на сервере")
					current_game_id = null
					is_game_active = false
					# 🔥 новая игра
					if not _pending_new_game_params.is_empty():
						var params = _pending_new_game_params
						_pending_new_game_params.clear()
						print("🔁 Запускаем новую игру после завершения")
						start_new_game(params.force_new, params.specific_seed)
					return
				if last_request_type == "abandon" and response_code == 200:
					print("✅ Игра успешно сдана (abandon)")
					# Обрабатываем достижения
					if data.has("unlocked_achievements") and data.unlocked_achievements.size() > 0:
						_handle_new_achievements(data.unlocked_achievements)
					current_game_id = null
					is_game_active = false
					if _pending_new_game_params != null and not _pending_new_game_params.is_empty():
						var params = _pending_new_game_params
						_pending_new_game_params.clear()
						print("🔁 Запускаем новую игру после abandon")
						start_new_game(true)
					return
				# --- ОБНОВЛЕНИЕ СОСТОЯНИЯ ---
				if data.has("state") and data["state"] != null:
					game_state = data["state"]
				if data.has("seed"):
					current_seed = data.seed
					print("🌱 Сид обновлён: ", current_seed)
				# --- СТАРТ ТАЙМЕРА ---
				if not first_move_made and (last_request_type == "draw" or last_request_type == "auto_move" or last_request_type == "manual_move"):
					first_move_made = true
					timer_active = true
					is_game_active = true
				# --- ПОБЕДА ---
				var game_won = data.get("game_won", false)
				if game_won:
					is_first_win = data.get("is_first_win", true)

					is_game_active = false
					current_game_id = null
					last_request_type = "end"

					update_ui()
					draw_game()
					show_win()

					pending_action_context = {}
					return
				# === ОБРАБОТКА АВТОСБОРА ===
				elif last_request_type == "auto_finish":
					var final_state = data.get("state", null)

					# ⚠️ НЕ трогаем game_state!
					# ⚠️ НЕ вызываем draw_game()

					# 1. Считаем план анимации на основе ТЕКУЩЕГО состояния
					var plan = _build_auto_finish_plan(game_state)

					# 2. Запускаем анимацию и передаём финальное состояние
					_run_auto_finish_animation(plan, final_state)

					return
				# --- UI ---
				update_ui()
				# === АНИМАЦИИ ===
				var context_type = pending_action_context.get("type", "")
				if context_type == "manual_move":
					var nodes = pending_action_context.get("nodes", [])
					var target_pile = pending_action_context.get("target_pile", "")
					if nodes.size() > 0 and target_pile != "":
						_animate_success_flight(nodes, target_pile)
					else:
						draw_game()
				elif context_type == "auto_move":
					#print("🐛 DEBUG auto_move response: ", data)
					if data.has("move"):
						var move_info = data["move"]
						var target_pile = move_info["to"]
						var nodes = pending_action_context.get("nodes", [])
						if nodes.size() > 0:
							_animate_success_flight(nodes, target_pile)
						else:
							draw_game()
					else:
						draw_game()
				elif last_request_type == "draw":
					draw_game()
				else:
					draw_game()
				pending_action_context = {}
			else:
				# --- ОШИБКА ---
				var err_code = data.get("error")
				printerr("⚠️ Ошибка сервера: ", err_code)
				if last_request_type == "end" and not _pending_new_game_params.is_empty():
					print("⚠️ Игра уже завершена на сервере, но есть отложенный запуск. Сбрасываем локально и запускаем новую.")
					current_game_id = null
					is_game_active = false
					var params = _pending_new_game_params.duplicate() # Копируем перед очисткой
					_pending_new_game_params.clear()
					start_new_game(params.force_new, params.specific_seed)
					return # Выходим, чтобы не выполнять анимации ошибки
				var context_type = pending_action_context.get("type", "")
				if context_type == "auto_move":
					var nodes = pending_action_context.get("nodes", [])
					if nodes.size() > 0 and is_instance_valid(nodes[0]):
						_animate_shake(nodes[0])
				elif context_type == "manual_move":
					var nodes = pending_action_context.get("nodes", [])
					var positions = pending_action_context.get("start_positions", [])
					if nodes.size() > 0:
						_animate_return(nodes, positions)
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
		Global.clear_pending_save()
		#_delete_save_on_server()

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

func _on_auto_finish_pressed():
	if is_busy or is_animating or is_auto_finishing:
		print("⏳ Игра занята, автосбор невозможен")
		return
	
	print("🚀 Запрос автосбора...")
	is_busy = true
	last_request_type = "auto_finish"
	
	var body = JSON.new().stringify({
		"player_id": Global.player_id
	})
	var headers = ["Content-Type: application/json"]
	http.request(Global.server_url + "/auto_finish", headers, HTTPClient.METHOD_POST, body)

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
	
	# 2. РАСЧЕТ ОТСТУПОВ (только базовые, без scaling)
	var horizontal_sep = max(10, card_width * 0.1)
	var vertical_sep = max(10, card_height * 0.15)

	$Display/MainLayout.add_theme_constant_override("separation", vertical_sep)
	$Display/MainLayout/UpperRow.add_theme_constant_override("separation", horizontal_sep)
	$Display/MainLayout/LowerRow.add_theme_constant_override("separation", horizontal_sep)
	
	# БАЗОВЫЕ offsets (идеальные)
	stack_offset_hidden = card_height * offset_hidden_ratio
	stack_offset_face_up = card_height * offset_face_up_ratio
	
	# 3. РАСЧЕТ ДОСТУПНОЙ ВЫСОТЫ ДЛЯ ТАБЛО
	var vbox = $Display/MainLayout
	var vbox_sep = vbox.get_theme_constant("separation")
	
	var static_ui_height = $Display/MainLayout/CountersContainer.size.y + \
						   $Display/MainLayout/Buttons.size.y + \
						   (vbox_sep * 3) + \
						   SCREEN_MARGIN
	
	var available_vertical_space = viewport_size.y - static_ui_height
	
	# сколько остаётся под стопки (минус верхний ряд)
	tableau_available_height = available_vertical_space - card_height
	
	# 4. ПРИМЕНЕНИЕ
	_apply_slot_sizes()
	
	# 5. ПЕРЕРИСОВКА
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
	_update_auto_finish_visibility()

func _clear_cards_from_slot(slot: Control):
	for child in slot.get_children():
		if not is_instance_valid(child):
			continue
		# Проверяем, есть ли у карты id и не находится ли она в анимации
		if child.has_meta("card_id") and _is_card_animating(child.get_meta("card_id")):
			continue  # Не трогаем "летящую" карту
		child.queue_free()

func foundation_slots():
	return [foundation_0, foundation_1, foundation_2, foundation_3]

func draw_stock():
	if not game_state.has("stock") or not game_state.has("waste"):
		return

	var stock = game_state["stock"]
	var waste = game_state["waste"]

	# 🔥 1. ВСЕГДА очищаем слот перед перерисовкой
	for child in stock_slot.get_children():
		child.queue_free()

	# 2. Если есть карты в колоде — показываем верхнюю
	if stock["cards"].size() > 0:
		# ✔ берём ВЕРХ КОЛОДЫ (последнюю карту)
		var card = stock["cards"][-1]

		draw_card(card, stock_slot, "stock")
		
	# 2. Колода пуста, но в сбросе есть карты (можно перевернуть)
	elif waste["cards"].size() > 0:
		var empty_stock = TextureRect.new()
		empty_stock.name = "EmptyStock"
		empty_stock.texture = DeckManager.get_back_texture()
		empty_stock.modulate = Color(1, 1, 1, 0.3)
		empty_stock.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		empty_stock.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		var target_size = Vector2(card_width, card_height)
		empty_stock.custom_minimum_size = target_size
		empty_stock.size = target_size 
		empty_stock.mouse_filter = Control.MOUSE_FILTER_STOP
		empty_stock.gui_input.connect(_on_empty_stock_clicked)
		stock_slot.add_child(empty_stock)

func _on_empty_stock_clicked(event):
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if is_busy:
			return
		var body = '{}'
		var headers = ["Content-Type: application/json"]
		last_request_type = "draw"
		http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
		
func draw_waste():
	if not game_state.has("waste"):
		return
	var waste = game_state["waste"]
	var cards = waste["cards"]
	if cards.size() == 0:
		return
	var start_idx = max(0, cards.size() - 3)
	for i in range(start_idx, cards.size()):
		var card = cards[i]
		var offset = (i - start_idx) * (card_width * 0.15)
		if _is_card_animating(card.get("id", null)):
			continue  # Пропускаем — её заменяет призрак		
		draw_card(card, waste_slot, "waste", Vector2(offset, 0), i)

func draw_foundations():
	var slots = foundation_slots()
	for i in 4:
		var pile_name = "foundation_" + str(i)
		var slot_node = slots[i]

		if game_state.has("piles") and game_state["piles"].has(pile_name):
			var pile = game_state["piles"][pile_name]
			var cards = pile["cards"]

			for j in range(cards.size()):
				var card = cards[j]
				var card_id = card.get("id", j)

				# Проверяем анимацию по id
				if _is_card_animating(card_id):
					continue
				
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
			var current_y = 0.0

			# 🔥 считаем реальную высоту стопки
			var pile_height = _calculate_pile_height(cards, stack_offset_hidden, stack_offset_face_up)

			var local_hidden = stack_offset_hidden
			var local_face = stack_offset_face_up

			# 🔥 если не помещается — сжимаем
			if pile_height > tableau_available_height and pile_height > 0:
				var k = tableau_available_height / pile_height
				local_hidden *= k
				local_face *= k

			for j in range(cards.size()):
				var card = cards[j]
				
				# 🔥 проверяем анимацию по уникальному id карты
				if _is_card_animating(card.get("id", null)):
					if card["face_up"]:
						current_y += local_face
					else:
						current_y += local_hidden
					continue
				
				draw_card(card, slot_node, pile_name, Vector2(0, current_y), j)
				
				if card["face_up"]:
					current_y += local_face
				else:
					current_y += local_hidden

func draw_card(card_data: Dictionary, parent_slot: Control, pile_name: String, 
			   offset: Vector2 = Vector2(0, 0), card_index: int = 0) -> Control:
	"""
	Создает визуальный узел карты и добавляет его в слот.
	Поддерживает уникальный id карты для безопасного сопоставления с game_state.
	"""
	
	# ПРОВЕРКА: если карта уже в анимации — не рисуем её
	var card_id = card_data.get("id", card_index)
	if _is_card_animating(card_id):
		return null  # Или создаём невидимый placeholder

	# Загружаем сцену карты
	var card_scene = preload("res://scenes/Card.tscn")
	var card_control = card_scene.instantiate()

	# Добавляем в родителя
	parent_slot.add_child(card_control)
	
	# Настраиваем узел карты
	# Передаем: данные карты, имя стопки, индекс в стопке, размер, id
	card_control.setup(
		card_data, 
		pile_name, 
		card_index, 
		Vector2(card_width, card_height),
		card_id  # уникальный идентификатор карты
	)
	
	# Сохраняем id в meta для удобного доступа
	card_control.set_meta("card_id", card_id)
	card_control.set_meta("suit", card_data.get("suit"))
	card_control.set_meta("rank", card_data.get("rank"))
	
	# Устанавливаем позицию и подключаем сигнал клика
	card_control.position = offset
	card_control.card_clicked.connect(_on_card_clicked)
	
	return card_control

func _on_card_clicked(event, pile_name, card_data, card_node):
	
	# === Обработка нажатий ===
	if event is InputEventMouseButton and event.pressed:
		
		# --- Левая кнопка: Перетаскивание ---
		if event.button_index == MOUSE_BUTTON_LEFT:
			if is_busy or is_animating:
				return
			if pile_name == "stock":
				if is_busy or is_animating:
					return				
				_animate_stock_to_waste(card_node, card_data)
				return
			#if pile_name == "stock":
				#var body = '{}'
				#var headers = ["Content-Type: application/json"]
				#last_request_type = "draw"
				#http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
				#return
			if not card_data["face_up"]:
				return
			pressed_card_node = card_node
			pressed_card_data = card_data
			pressed_pile_name = pile_name
			press_mouse_pos = get_global_mouse_position()
			drag_started = false

			# визуально "приподнять"
			card_node.z_index = 50
			var card_id = card_node.get_meta("card_id", card_data.get("id", -1))		
			drag_card_ids = [card_id]
			
			if pile_name.begins_with("tableau"):
				var slot = card_node.get_parent()
				if slot:
					var my_index = card_node.get_meta("card_index", 0)
					for child in slot.get_children():
						if not is_instance_valid(child):
							continue
						if child == card_node: 
							continue
						if child.get_meta("card_index", 0) > my_index:
							drag_nodes.append(child)
							# Собираем ID каждой карты хвоста
							var child_card_id = child.get_meta("card_id", -1)
							if child_card_id != "":
								drag_card_ids.append(child_card_id)
			drag_nodes = drag_nodes.filter(func(n): return is_instance_valid(n))
			drag_nodes.sort_custom(func(a, b):
				return a.get_meta("card_index", 0) < b.get_meta("card_index", 0)
			)
			
			# 2. Запоминаем смещения хвоста
			var head_pos = card_node.global_position
			for i in range(1, drag_nodes.size()):
				var node = drag_nodes[i]
				node.set_meta("drag_offset_from_head", node.global_position - head_pos)
			
			# 3. ПРИМЕНЯЕМ ЭФФЕКТЫ (Z-index и ТЕНЬ)
			for node in drag_nodes:
				node.z_index = 100
			
			var mouse_pos = get_global_mouse_position()
			drag_offset = mouse_pos - card_node.global_position

	# === Обработка отпускания ===
	elif event is InputEventMouseButton and not event.pressed and event.button_index == MOUSE_BUTTON_LEFT:

		# === если был drag ===
		if is_dragging:
			_end_drag()

		# === если это клик ===
		elif pressed_card_node and not drag_started:
			_do_auto_move_click()

		# сброс
		pressed_card_node = null
		pressed_card_data = null
		pressed_pile_name = "" 

func _do_auto_move_click():
	if is_busy or is_animating:
		return

	var card_node = pressed_card_node
	var card_data = pressed_card_data
	var pile_name = pressed_pile_name

	if pile_name == "stock":
		return
	if not card_data["face_up"]:
		return

	var card_id: String = card_node.get_meta("card_id")

	var nodes_stack = [card_node]

	if pile_name.begins_with("tableau"):
		var slot = card_node.get_parent()
		if slot:
			var my_index = card_node.get_meta("card_index", 0)
			for child in slot.get_children():
				if not is_instance_valid(child):
					continue
				if child == card_node:
					continue
				if child.get_meta("card_index", 0) > my_index:
					nodes_stack.append(child)

	nodes_stack.sort_custom(func(a, b):
		return a.get_meta("card_index", 0) < b.get_meta("card_index", 0)
	)

	pending_action_context = {
		"type": "auto_move",
		"nodes": nodes_stack,
		"count": nodes_stack.size(),
		"card_id": card_id,
	}

	last_request_type = "auto_move"

	var body_dict = {
		"card_id": card_id,
		"player_id": Global.player_id,
		"game_type": "klondike"
	}
	var headers = ["Content-Type: application/json"]
	var body_json = JSON.stringify(body_dict)

	http.request(Global.server_url + "/auto_move", headers, HTTPClient.METHOD_POST, body_json)

func _end_drag():
	if not is_dragging:
		return
		
	# Сохраняем всё для анимации ПЕРЕД сбросом переменных
	var nodes_to_animate = drag_nodes.duplicate()
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
	
	if target_pile != "" and target_pile != drag_source_pile:
		#print("📂 Перенос карт по ID: ", drag_card_ids, " в: ", target_pile)
		
		# === ИЗМЕНЕНИЕ: Отправляем список ID карт вместо count ===
		pending_action_context = {
			"type": "manual_move",
			"nodes": nodes_to_animate,
			"start_positions": start_positions,
			"source_pile": drag_source_pile,
			"target_pile": target_pile,
			"card_ids": drag_card_ids,  # === ИЗМЕНЕНИЕ: Массив ID вместо count ===
			"head_card_id": drag_head_card_id  # ID первой карты (для сервера)
		}
		
		last_request_type = "manual_move"
		
		# === ИЗМЕНЕНИЕ: Отправляем card_ids вместо count ===
		var body = JSON.new().stringify({
			"from": drag_source_pile,
			"to": target_pile,
			"card_ids": drag_card_ids,  # === Массив ID перетаскиваемых карт ===
			"head_card_id": drag_head_card_id,  # ID головной карты (опционально)
			"player_id": Global.player_id
		})
		var headers = ["Content-Type: application/json"]
		http.request(Global.server_url + "/move", headers, HTTPClient.METHOD_POST, body)
		
		is_busy = true
	else:
		# Если отпустили в пустом месте — возвращаем на место
		draw_game()
	
	# Сброс переменных перетаскивания
	is_dragging = false
	drag_source_pile = ""
	drag_card_data = null
	dragged_card_node = null
	drag_nodes.clear()
	drag_card_ids.clear()  # === ДОБАВИТЬ очистку ===
	drag_head_card_id = -1  # === ДОБАВИТЬ очистку ===

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

func _animate_success_flight(nodes: Array, target_pile: String):
	"""Запускает анимацию полета карт к целевой стопке"""
	is_animating = true

	# 1. Сохраняем глобальные позиции ПЕРЕД любой перерисовкой
	var start_positions = []
	for node in nodes:
		start_positions.append(node.global_position)

	# 2. Создаем призраков на основе оригиналов (еще до draw_game)
	var flying_layer = Control.new()
	flying_layer.name = "FlyingLayer"
	flying_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flying_layer.z_index = 300
	$Display.add_child(flying_layer)

	var ghosts = []
	for i in range(nodes.size()):
		var original_node = nodes[i]
		if not is_instance_valid(original_node):
			continue
		var ghost = _create_ghost_card(original_node)
		ghost.global_position = start_positions[i]
		flying_layer.add_child(ghost)
		ghosts.append(ghost)

	# 3. ВЫЧИСЛЯЕМ целевые позиции из game_state
	var targets = []
	for i in range(nodes.size()):
		targets.append(_calculate_target_position(target_pile, i, nodes.size()))

	# 4. Помечаем карты для исключения из отрисовки
	_mark_cards_as_animating(nodes)
	
	for node in nodes:
		if is_instance_valid(node):
			node.visible = false

	# 5. Перерисовываем — перемещённые карты будут пропущены
	draw_game()

	# 6. Запускаем анимацию
	var tween = create_tween()
	tween.set_parallel(true)
	for i in range(ghosts.size()):
		tween.tween_property(ghosts[i], "global_position", targets[i], 0.25)\
			 .set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_QUAD)

	tween.set_parallel(false)
	tween.tween_interval(0.3)

	tween.tween_callback(func():
		flying_layer.queue_free()
		for node in nodes:
			if is_instance_valid(node):
				node.visible = true
		_clear_animating_marks()  # Снимаем пометки
		draw_game()  # Полная перерисовка
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
			node.z_index = 100 
			tween.tween_property(node, "global_position", positions[i], 0.2).set_ease(Tween.EASE_OUT)
	tween.set_parallel(false)
	tween.tween_callback(func():
		is_animating = false
		for node in nodes:
			if is_instance_valid(node):
				node.z_index = 0
		draw_game() 
	)

func _animate_stock_to_waste(card_node: Control, card_data: Dictionary) -> void:
	# Блокируем другие действия
	is_animating = true
	# --- 1. Создаем слой для анимации ---
	var flying_layer = Control.new()
	flying_layer.name = "FlyingLayer"
	flying_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flying_layer.z_index = 300
	$Display.add_child(flying_layer)
	
	# --- 2. Создаем ghost карты ---
	var ghost = _create_card_node(
		DeckManager.get_back_texture(),
		Vector2(card_width, card_height)
		)

	# добавим тень как в ghost
	var shadow = ColorRect.new()
	shadow.color = Color(0, 0, 0, 0.3)
	shadow.size = ghost.size
	shadow.position = Vector2(8, 8)
	shadow.material = _get_shadow_material()
	ghost.add_child(shadow)
	ghost.move_child(shadow, 0) # тень под картой
	flying_layer.add_child(ghost)
	ghost.global_position = card_node.global_position
	ghost.scale = Vector2(1.0, 1.0)
	
	# Прячем оригинал
	card_node.visible = false
	
	# --- 3. Получаем TextureRect внутри ghost ---
	var tex_rect := ghost.get_child(1) as TextureRect
	
	# --- 4. Готовим текстуры ---
	var back_texture = DeckManager.get_back_texture()
	var face_texture = DeckManager.get_card_texture(
		card_data["suit"],
		card_data["rank"],
		true
	)
	
	# Убеждаемся что стартуем с рубашки
	tex_rect.texture = back_texture
	
	# --- 5. Создаем tween ---
	var tween = create_tween()
	
	# === FLIP: схлопывание ===
	tween.tween_property(ghost, "scale:x", 0.0, 0.08)\
		.set_trans(Tween.TRANS_CUBIC)\
		.set_ease(Tween.EASE_IN)
	
	# === смена текстуры ===
	tween.tween_callback(func():
		tex_rect.texture = face_texture
	)
	
	# === раскрытие ===
	tween.tween_property(ghost, "scale:x", 1.0, 0.08)\
		.set_trans(Tween.TRANS_CUBIC)\
		.set_ease(Tween.EASE_OUT)
	
	# === небольшая пауза ===
	tween.tween_interval(0.05)
	
	# --- 6. Отправляем запрос на сервер ---
	tween.tween_callback(func():
		var body = '{}'
		var headers = ["Content-Type: application/json"]
		last_request_type = "draw"
		http.request(Global.server_url + "/draw", headers, HTTPClient.METHOD_POST, body)
	)
	
	# --- 7. Рассчитываем позицию назначения ---
	var target_pos = _calculate_target_position("waste", 0, 1)
	
	# === ПОЛЕТ ===
	tween.tween_property(ghost, "global_position", target_pos, 0.25)\
		.set_trans(Tween.TRANS_BACK)\
		.set_ease(Tween.EASE_OUT)
	
	# --- 8. Завершение ---
	tween.tween_callback(func():
		flying_layer.queue_free()
		draw_game()
		is_animating = false
	)

func _get_empty_foundation_slots(state: Dictionary) -> Array:
	var result: Array = []
	var slots = ["foundation_0", "foundation_1", "foundation_2", "foundation_3"]

	for slot in slots:
		var pile = state["piles"].get(slot, null)

		if pile == null:
			result.append(slot)
			continue

		var cards = pile.get("cards", [])
		if cards.size() == 0:
			result.append(slot)

	return result

func _collect_all_cards_on_table() -> Array:
	var result = []
	var all_slots = [waste_slot] + tableau_slots
	
	for slot in all_slots:
		for child in slot.get_children():
			if child.has_meta("card_id"):
				result.append(child)
	
	return result

func _build_foundation_suit_map() -> Dictionary:
	var map = {}
	
	for slot in foundation_slots():
		for child in slot.get_children():
			if child.has_meta("suit"):
				var suit = child.get_meta("suit")
				map[suit] = slot
				break
	
	return map

func _resolve_foundation_for_card(card_node: Control, suit_map: Dictionary, empty_slots: Array) -> Control:
	var suit = card_node.get_meta("suit")
	
	if suit_map.has(suit):
		return suit_map[suit]
	
	if empty_slots.size() > 0:
		var slot = empty_slots.pop_front()
		suit_map[suit] = slot
		return slot
	
	return foundation_slots()[0]

func _rank_to_value(rank: String) -> int:
	match rank:
		"A": return 1
		"2": return 2
		"3": return 3
		"4": return 4
		"5": return 5
		"6": return 6
		"7": return 7
		"8": return 8
		"9": return 9
		"10": return 10
		"J": return 11
		"Q": return 12
		"K": return 13
	return 0

func _build_auto_finish_plan(state: Dictionary) -> Array:
	var plan: Array = []

	# --- 1. Инициализация foundations ---
	var foundation_slots = ["foundation_0", "foundation_1", "foundation_2", "foundation_3"]

	# состояние баз:
	# slot -> { suit, top_rank }
	var foundations = {}

	for slot in foundation_slots:
		var pile = state["piles"].get(slot, {})
		var cards = pile.get("cards", [])

		if cards.size() == 0:
			foundations[slot] = { "suit": null, "top_rank": 0 }
		else:
			var top = cards[-1]
			foundations[slot] = {
				"suit": top["suit"],
				"top_rank": _rank_to_value(top["rank"])
			}

	# --- 2. Собираем ВСЕ карты из tableau ---
	var all_cards = []

	for i in range(7):
		var pile_name = "tableau_" + str(i)
		var pile = state["piles"].get(pile_name, {})
		var cards = pile.get("cards", [])

		for card in cards:
			if card["face_up"]:
				all_cards.append({
					"card": card,
					"from": pile_name
				})

	# --- 3. Сортируем по возрастанию ранга ---
	all_cards.sort_custom(func(a, b):
		return _rank_to_value(a.card["rank"]) < _rank_to_value(b.card["rank"])
	)

	# --- 4. Основной проход ---
	for item in all_cards:
		var card = item["card"]
		var from = item["from"]

		var suit = card["suit"]
		var rank_val = _rank_to_value(card["rank"])

		var target_slot = ""

		# 4.1 ищем базу с той же мастью
		for slot in foundation_slots:
			var f = foundations[slot]

			if f["suit"] == suit and f["top_rank"] == rank_val - 1:
				target_slot = slot
				break

		# 4.2 если не нашли — ищем пустую базу под туза
		if target_slot == "" and rank_val == 1:
			for slot in foundation_slots:
				var f = foundations[slot]
				if f["suit"] == null:
					target_slot = slot
					break

		# 4.3 если нашли — добавляем ход
		if target_slot != "":
			plan.append({
				"card_id": card["id"],
				"from": from,
				"to": target_slot
			})

			# обновляем состояние базы
			foundations[target_slot]["suit"] = suit
			foundations[target_slot]["top_rank"] = rank_val

	return plan

func _build_card_index() -> Dictionary:
	var map: Dictionary = {}

	# Все зоны, где могут быть карты
	var slots = []

	# stock / waste / foundations / tableau
	slots.append(stock_slot)
	slots.append(waste_slot)

	for f in foundation_slots():
		slots.append(f)

	for t in tableau_slots:
		slots.append(t)

	# обходим все узлы
	for slot in slots:
		if not is_instance_valid(slot):
			continue

		for child in slot.get_children():
			if not is_instance_valid(child):
				continue

			# важно: только реальные карты
			if not child.has_meta("card_id"):
				continue

			var id = str(child.get_meta("card_id"))
			map[id] = child

	return map

func _run_auto_finish_animation(plan: Array, final_state: Dictionary):
	is_auto_finishing = true
	is_animating = true

	var flying_layer = Control.new()
	flying_layer.name = "AutoFinishLayer"
	flying_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flying_layer.z_index = 300
	$Display.add_child(flying_layer)

	# 🔥 важно: фиксируем стартовое состояние
	var id_to_node = _build_card_index()

	for move in plan:

		var node = id_to_node.get(move.card_id, null)
		if node == null:
			continue

		# 1. создаём ghost
		var ghost = _create_ghost_card(node)
		ghost.global_position = node.global_position
		flying_layer.add_child(ghost)

		# 2. вычисляем цель (ОЧЕНЬ просто теперь)
		var target = _calculate_target_position(
			move.to,
			0,
			1
		)

		# 3. скрываем оригинал
		node.visible = false
		_mark_card_animating(move.card_id)

		# 4. анимация
		var tween = create_tween()
		tween.tween_property(ghost, "global_position", target, 0.12)
		tween.tween_callback(ghost.queue_free)

		await tween.finished

	# --- финал ---
	flying_layer.queue_free()
	_clear_animating_marks()

	game_state = final_state
	draw_game()
	show_win()

	is_auto_finishing = false
	is_animating = false

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
	
func _calculate_target_position(pile_name: String, card_offset: int, total_moved: int) -> Vector2:
	"""Вычисляет глобальную позицию карт без использования get_child()"""
	var slot_node = null
	var base_pos = Vector2.ZERO
	
	if pile_name == "waste":
		slot_node = waste_slot
		var waste_cards = game_state["waste"]["cards"]
		var card_idx = waste_cards.size() - total_moved + card_offset
		var start_idx = max(0, waste_cards.size() - 3)
		if card_idx >= start_idx:
			base_pos.x = (card_idx - start_idx) * (card_width * 0.15)
			
	elif pile_name.begins_with("foundation"):
		var idx = int(pile_name.split("_")[1])
		slot_node = foundation_slots()[idx]  # ← ИСПРАВЛЕНО: добавлены ()
		
	elif pile_name.begins_with("tableau"):
		var idx = int(pile_name.split("_")[1])
		slot_node = tableau_slots[idx]  # ← Это массив, тут всё верно
		
		var pile_data = game_state["piles"][pile_name]
		var cards = pile_data["cards"]
		var target_idx = cards.size() - total_moved + card_offset
		
		var y_offset = 0.0
		for i in range(target_idx):
			if i < cards.size():
				if cards[i]["face_up"]:
					y_offset += stack_offset_face_up
				else:
					y_offset += stack_offset_hidden
		base_pos.y = y_offset
	
	if slot_node:
		return slot_node.global_position + base_pos
	return Vector2.ZERO

func _update_auto_finish_visibility():
	if not game_state or not auto_finish_button or not waste_slot:
		return

	# 1. Проверяем базовые условия: колода и сброс должны быть пусты
	var stock_empty = not game_state.get("stock", {}).get("cards", []).size() > 0
	var waste_empty = not game_state.get("waste", {}).get("cards", []).size() > 0
	
	# 2. Условия для показа кнопки
	# Кнопка показывается только если сток и сброс пусты.
	# Сервер сам проверит, все ли карты открыты (can_auto_complete).
	if stock_empty and waste_empty and is_game_active:
		# Показываем кнопку, скрываем слот (или делаем его нулевым, но visible=false проще)
		auto_finish_button.visible = true
		waste_slot.visible = false
	else:
		# Скрываем кнопку, показываем слот
		auto_finish_button.visible = false
		waste_slot.visible = true

func _hide_target_cards(pile_name: String, count: int):
	"""Скрывает карты в целевом слоте, которые заменяются призраками"""
	var slot_node = null
	
	if pile_name == "waste":
		slot_node = waste_slot
	elif pile_name.begins_with("foundation"):
		var idx = int(pile_name.split("_")[1])
		slot_node = foundation_slots()[idx]  # ← ИСПРАВЛЕНО: добавлены ()
	elif pile_name.begins_with("tableau"):
		var idx = int(pile_name.split("_")[1])
		slot_node = tableau_slots[idx]  # ← Это массив, тут всё верно
	else:
		return
	
	if not slot_node:
		return
	
	# Находим индексы карт, которые нужно скрыть
	var pile_data = null
	if pile_name == "waste":
		pile_data = game_state["waste"]
	else:
		pile_data = game_state["piles"].get(pile_name)
	
	if not pile_data:
		return
	
	var total_cards = pile_data["cards"].size()
	var start_idx = total_cards - count
	
	# Скрываем нужные дочерние узлы
	for i in range(slot_node.get_child_count()):
		var child = slot_node.get_child(i)
		var card_index = child.card_index
		if card_index >= start_idx and card_index < total_cards:
			child.hide()

func _mark_cards_as_animating(nodes: Array) -> void:
	"""Помечает переданные узлы как находящиеся в анимации по их card_id"""
	_animating_cards.clear()
	for node in nodes:
		if node.has_meta("card_id"):
			var card_id = node.get_meta("card_id")
			_animating_cards[str(card_id)] = true


func _create_ghost_card(original_node: Control) -> Control:
	"""Создаёт копию карты для анимации полёта"""
	var ghost = Control.new()
	ghost.size = original_node.size
	
	# Тень
	var ghost_shadow = ColorRect.new()
	ghost_shadow.color = Color(0, 0, 0, 0.3)
	ghost_shadow.size = original_node.size
	ghost_shadow.position = Vector2(8, 8)
	ghost_shadow.material = _get_shadow_material()
	ghost.add_child(ghost_shadow)
	
	# Текстура карты
	var tex_rect = TextureRect.new()
	tex_rect.texture = original_node.get_node("Texture").texture
	tex_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	tex_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tex_rect.size = original_node.size
	ghost.add_child(tex_rect)
	
	return ghost

func _get_waste_card_position(card_index: int, total_cards: int) -> Vector2:
	"""
	Вычисляет позицию карты в сбросе.
	card_index: индекс в массиве waste.cards
	total_cards: общее количество карт в сбросе
	Возвращает: локальную позицию относительно waste_slot
	"""
	if total_cards == 0:
		return Vector2.ZERO
	var first_visible_idx = max(0, total_cards - 3)
	if card_index < first_visible_idx:
		return Vector2.ZERO
	var visible_idx = card_index - first_visible_idx
	var x_offset = visible_idx * (card_width * 0.15)
	return Vector2(x_offset, 0)

func _mark_card_animating(card_id: int):
	"""Помечает карту как находящуюся в анимации (не рисовать в draw_game)"""
	if card_id == null:
		return
	_animating_cards[str(card_id)] = true


func _unmark_card_animating(card_id: int):
	"""Снимает пометку анимации"""
	if card_id == null:
		return
	_animating_cards.erase(str(card_id))


func _clear_animating_marks():
	"""Очищает все пометки"""
	_animating_cards.clear()


func _is_card_animating(card_id) -> bool:
	# card_id может быть int или String (UUID)
	return _animating_cards.has(str(card_id))

func _create_card_node(texture: Texture2D, size: Vector2) -> Control:
	"""
	Создаёт базовый узел карты с текстурой и центральным pivot.
	Используется для призраков и анимаций.
	"""
	var node = Control.new()
	node.size = size
	node.pivot_offset = size / 2  # Центр вращения
	
	var tex_rect = TextureRect.new()
	tex_rect.texture = texture
	tex_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	tex_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	tex_rect.size = size
	tex_rect.pivot_offset = size / 2  # Тоже центрируем
	
	node.add_child(tex_rect)
	return node
	
func _get_card_textures(card_data: Dictionary) -> Dictionary:
	"""
	Возвращает словарь с текстурами рубашки и лица для карты.
	Для закрытой карты обе текстуры — рубашка.
	"""
	var is_face_up = card_data.get("face_up", false)
	var has_data = card_data.has("suit") and card_data.has("rank")
	
	var result = {
		"back": DeckManager.get_back_texture(),
		"face": null
	}
	
	if is_face_up and has_data:
		# Лицо карты
		result["face"] = DeckManager.get_card_texture(
			card_data["suit"], 
			card_data["rank"], 
			true
		)
	else:
		# Закрытая карта — лицо тоже рубашка (или можно null)
		result["face"] = result["back"]
	
	return result

func _handle_new_achievements(unlocked: Array):
	print("💡 New achievements:", unlocked)
	for ach in unlocked:
		show_achievement_notification(ach)
	
	# 👉 сохраняем последнее достижение для альбома
	var last = unlocked[-1]
	Global.has_new_achievement = true
	Global.last_achievement_id = last.get("id")

func show_achievement_notification(ach: Dictionary) -> void:
	var popup = Label.new()
	popup.text = "🏆 " + ach.get("name", "Достижение!")
	popup.modulate = Color(1, 1, 1, 0)
	popup.position = Vector2(50, 50)
	
	popup.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(popup)
	
	var tween = create_tween()
	tween.tween_property(popup, "modulate:a", 1.0, 0.3)
	tween.tween_interval(2.0)
	tween.tween_property(popup, "modulate:a", 0.0, 0.5)
	tween.tween_callback(popup.queue_free)

	# ✅ корректное подключение сигнала
	popup.gui_input.connect(Callable(self, "_on_popup_clicked").bind(popup))

func _on_popup_clicked(event: InputEvent, popup: Label) -> void:
	if event is InputEventMouseButton and event.pressed:
		open_achievements_album()
		if is_instance_valid(popup):
			popup.queue_free()
	
func open_achievements_album():
	var scene = load("res://scenes/AchievementsAlbum.tscn").instantiate()
	get_tree().root.add_child(scene)
	
	scene.close_requested.connect(func():
		scene.queue_free()
	)
