extends Control

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var game_select = $MainContainer/GameSelectButton
@onready var start_button = $MainContainer/StartButton
@onready var stats_button = $MainContainer/StatsButton
@onready var quit_button = $MainContainer/QuitButton

# ===== ЭЛЕМЕНТЫ ВЕРХНЕЙ ПАНЕЛИ =====
@onready var player_name_label = $MainContainer/TopPanel/PlayerNameLabel
@onready var edit_name_button = $MainContainer/TopPanel/EditNameButton

# ===== ДИАЛОГ ВОССТАНОВЛЕНИЯ =====
# Убедись, что узел RestoreDialog добавлен в сцену!
@onready var restore_dialog = $RestoreDialog

# ===== ПЕРЕМЕННЫЕ =====
var http: HTTPRequest
var games = ["Клондайк"]
var current_game_index = 0
const STATS_SCENE = "res://scenes/PlayerStats.tscn"

# Режим ожидания ответа (чтобы знать, что делать с HTTP ответом)
var pending_action = "" # "check_save", "load_save", "new_game"

func _ready():
	# Создаём HTTP для запросов к серверу
	http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_http_completed)
	
	# Подключаем кнопки меню
	game_select.pressed.connect(_on_game_select_pressed)
	start_button.pressed.connect(_on_start_pressed)
	stats_button.pressed.connect(_on_stats_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	
	# Подключаем кнопку редактирования имени
	edit_name_button.pressed.connect(_on_edit_name_pressed)
	
	# Подключаем сигналы диалога восстановления
	if restore_dialog:
		restore_dialog.confirmed.connect(_on_restore_confirmed)
		restore_dialog.canceled.connect(_on_restore_declined)
	
	# Обновляем текст кнопки выбора игры
	update_game_button()
	
	# Инициализируем игрока
	initialize_player()

# ===== МЕТОДЫ ИНИЦИАЛИЗАЦИИ =====

func initialize_player():
	"""Инициализация игрока при запуске"""
	if Global.is_player_loaded:
		player_name_label.text = "👤 " + Global.player_name
		connect_to_server()
	else:
		player_name_label.text = "👤 Загрузка..."
		request_new_identity()

func request_new_identity():
	"""Запросить новый UUID у сервера"""
	print("📡 Запрос нового UUID...")
	var url = Global.server_url + "/player/identity"
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)

	if error != OK:
		print("❌ Ошибка запроса UUID")
		player_name_label.text = "👤 Офлайн режим"

func connect_to_server():
	"""Подключиться к серверу с существующим UUID"""
	print("📡 Подключение к серверу с UUID: ", Global.player_id)
	var url = Global.server_url + "/player/identity?player_id=" + Global.player_id
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)

	if error != OK:
		print("❌ Ошибка подключения к серверу")
		player_name_label.text = "👤 " + Global.player_name + " (офлайн)"

# ===== ОБРАБОТКА ОТВЕТОВ =====

func _on_http_completed(result, response_code, headers, body):
	# Если сервер вернул код ошибки (не 200)
	print("\n=== _on_http_completed ===")
	print("response_code: ", response_code)
	print("pending_action: ", pending_action)
	print("headers: ", headers)
	if response_code == 409:
		print("⚠️ Конфликт: найдено активное сохранение")
		var response_text = body.get_string_from_utf8()
		var json = JSON.new()
		var error = json.parse(response_text)
		if error == OK:
			_show_restore_dialog(json.data)
		else:
			# Если не удалось распарсить, просто начинаем новую
			_proceed_to_game_scene("new")
		return
	if response_code != 200:
		print("⚠️ Ошибка сервера: ", response_code)
		var response_text = body.get_string_from_utf8()
		print("Тело ответа: ", response_text)
		
		# Если была попытка загрузить сохранение и произошла ошибка — запускаем новую игру
		if pending_action == "load_save":
			print("❌ Не удалось загрузить сохранение, начинаем новую игру")
			_proceed_to_game_scene("new")
		elif pending_action == "check_save":
			_proceed_to_game_scene("new")
		return

		
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)
	
	if error == OK:
		var data = json.data
		
		# 1. Обработка ответа от сервера (UUID / Connect)
		if data.has("player_id"):
			var new_id = data["player_id"]
			var new_name = data.get("player_name", "Игрок")
			Global.save_player_identity(new_id, new_name)
			player_name_label.text = "👤 " + new_name
			print("✅ Получен UUID: ", new_id)
		
		# 2. Проверка наличия сохранения (GET /load)
		elif pending_action == "check_save":
			if data.has("success") and data["success"]:
				if data.has("has_save") and data["has_save"]:
					print("💾 Найдено сохранение!")
					_show_restore_dialog(data)
				else:
					print("🆕 Сохранений нет, начинаем новую игру")
					_proceed_to_game_scene("new")
			else:
				print("⚠️ Ошибка при проверке сохранения: ", data.get("error", "Unknown"))
				_proceed_to_game_scene("new")
		
		# 3. Загрузка сохранения (POST /load/save)
		# 3. Загрузка сохранения (POST /load/save)
		elif pending_action == "load_save":
			if data.has("success") and data["success"]:
				# ВАЖНО: Смотрим, что пришло внутри ответа
				print("📦 Отладка данных загрузки:")
				print("   Ключи data: ", data.keys())
				
				# Смотрим, что внутри 'state' (если он есть)
				if data.has("state"):
					print("   Ключи data['state']: ", data["state"].keys())
				
				if data.has("state"):
					print("✅ Состояние загружено, передаем в игру")
					print("   Размер state: ", data["state"].size() if data["state"] is Dictionary else "не словарь!")
					# Передаем state, время и ID (saved_game_id из сервера!)
					Global.set_pending_save(data["state"], data.get("time", 0), data.get("saved_game_id", 0))
					_proceed_to_game_scene("load")
				else:
					printerr("❌ В ответе нет ключа 'state'!")
					_proceed_to_game_scene("new")
			else:
				printerr("❌ Ошибка данных загрузки: ", data.get("error", "Unknown"))
				_proceed_to_game_scene("new")
		
		# 4. Ответ смены имени (опционально)
		elif data.has("message") and data.has("player_name"):
			print("✅ Имя изменено")
			
	else:
		print("❌ Ошибка парсинга JSON: ", response_text)
		# Если парсинг упал, просто идем в новую игру
		if pending_action == "check_save" or pending_action == "load_save":
			_proceed_to_game_scene("new")

func handle_success_response(data: Dictionary):
	"""Обработка успешных ответов от сервера"""

	# 1. Ответ с UUID
	if data.has("player_id"):
		var new_id = data["player_id"]
		var new_name = data.get("player_name", "Игрок")
		Global.save_player_identity(new_id, new_name)
		player_name_label.text = "👤 " + new_name
		print("✅ Получен UUID: ", new_id)
	
	# 2. Ответ проверки сохранения
	elif pending_action == "check_save":
		if data.has("has_save") and data["has_save"]:
			print("💾 Найдено сохранение!")
			_show_restore_dialog(data)
		else:
			print("🆕 Сохранений нет, начинаем новую игру")
			_proceed_to_game_scene("new")
	
	# 3. Ответ загрузки сохранения (получен state)
	elif pending_action == "load_save":
		if data.has("state"):
			print("✅ Состояние загружено, передаем в игру")
			Global.set_pending_save(data["state"], data.get("time", 0), data.get("game_id", 0))
			_proceed_to_game_scene("load")
	
	# 4. Ответ смены имени
	elif data.has("message") and data.has("player_name"):
		print("✅ Имя изменено")

# ===== ЛОГИКА ЗАПУСКА ИГРЫ =====

func _on_start_pressed():
	"""Кнопка 'Играть' - проверяем наличие сохранений"""
	print("🔍 Проверка сохранений перед стартом...")
	
	# Ждем, пока загрузится player_id
	if not Global.is_player_loaded or Global.player_id.is_empty():
		print("⏳ Ожидание загрузки player_id...")
		# Показываем индикатор загрузки или просто ждем
		await get_tree().create_timer(0.5).timeout
		if not Global.is_player_loaded:
			# Если все еще не загружен, пробуем запросить заново
			request_new_identity()
			await get_tree().create_timer(0.5).timeout
	
	# Определяем тип игры
	if games[current_game_index] == "Клондайк":
		Global.current_variant = "klondike"
	
	# Запрашиваем у сервера информацию о сохранениях
	pending_action = "check_save"
	var url = Global.server_url + "/load?player_id=" + Global.player_id + "&game_type=" + Global.current_variant
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)
	
	if error != OK:
		_proceed_to_game_scene("new")

func _on_restore_confirmed():
	"""Игрок нажал 'Продолжить'"""
	print("➡️ Загрузка сохранения...")
	var save_id = restore_dialog.get_meta("save_id", 0)
	
	if save_id > 0:
		pending_action = "load_save"
		
		# ВАЖНО: Правильный JSON и Headers
		var body = JSON.new().stringify({
			"player_id": Global.player_id,
			"save_id": save_id
		})
		var headers = ["Content-Type: application/json"]
		
		# Используем наш http объект
		var err = http.request(Global.server_url + "/load/save", headers, HTTPClient.METHOD_POST, body)
		
		if err != OK:
			printerr("❌ Ошибка отправки запроса загрузки: ", err)
			# Если ошибка запроса, просто идем в новую игру
			_proceed_to_game_scene("new")
	else:
		printerr("❌ Неверный ID сохранения")
		_proceed_to_game_scene("new")

func _on_restore_declined():
	"""Игрок нажал 'Новая игра'"""
	print("➡️ Начинаем новую игру (удаление старой)")
	# Мы не удаляем сохранение отдельным запросом, 
	# просто говорим игре начать новую (force_new=true)
	_proceed_to_game_scene("new")

func _proceed_to_game_scene(mode: String):
	"""Переключение на сцену игры"""
	print("\n=== 🎮 _proceed_to_game_scene ===")
	print("mode: ", mode)
	print("Текущий Global.pending_game_state размер: ", Global.pending_game_state.size())
	print("Global.has_pending_save(): ", Global.has_pending_save())
	
	var scene_path = "res://scenes/games/klondike.tscn"
	print("Путь к сцене: ", scene_path)
	print("Сцена существует: ", ResourceLoader.exists(scene_path))
	
	if not ResourceLoader.exists(scene_path):
		printerr("❌ Файл сцены не найден: ", scene_path)
		return
	
	# Если режим "new", очищаем возможный pending state
	if mode == "new":
		print("🧹 Режим new - очищаем pending state")
		Global.clear_pending_save()
	elif mode == "load":
		print("📦 Режим load - проверяем pending state")
		print("  - Размер state: ", Global.pending_game_state.size())
		print("  - Время: ", Global.pending_game_time)
		print("  - ID: ", Global.pending_game_id)
		print("  - Ключи state: ", Global.pending_game_state.keys() if Global.pending_game_state.size() > 0 else "нет ключей")
	
	# Переход
	print("🎬 Вызываем change_scene_to_file...")
	var result = get_tree().change_scene_to_file(scene_path)
	print("Результат change_scene_to_file: ", result)
	print("=== Конец _proceed_to_game_scene ===\n")

# ===== ДИАЛОГ ВОССТАНОВЛЕНИЯ =====

func _show_restore_dialog(save_data: Dictionary):
	"""Показать диалог восстановления"""
	print("\n=== _show_restore_dialog ===")
	print("Получены save_data: ", save_data)
	print("Ключи save_data: ", save_data.keys())
	
	if not restore_dialog:
		printerr("❌ RestoreDialog не найден в сцене!")
		_proceed_to_game_scene("new")
		return
	
	# Извлечем данные с проверкой
	var moves = save_data.get("moves", 0)
	var time_sec = save_data.get("time", 0)
	var score = save_data.get("score", 0)
	
	print("Извлеченные данные:")
	print("  - moves: ", moves, " (тип: ", typeof(moves), ")")
	print("  - time: ", time_sec, " (тип: ", typeof(time_sec), ")")
	print("  - score: ", score, " (тип: ", typeof(score), ")")
	
	# Формируем текст
	var text = "Найдена незаконченная игра!\n\n"
	text += "📊 Ходы: %d\n" % moves
	text += "⏱️ Время: %s\n" % _format_time(time_sec)
	text += "💰 Счет: %d\n\n" % score
	
	# Добавим информацию о статусе
	if save_data.get("is_suspended", false):
		text += "(Прошло более часа с последнего хода)"
	else:
		text += "(Игра была прервана)"
	
	text += "\nПродолжить?"
	
	print("Сформированный текст диалога:")
	print(text)
	
	restore_dialog.dialog_text = text
	restore_dialog.popup_centered()
	
	# Сохраняем ID сохранения для использования в колбэках
	var save_id = save_data.get("save_id", 0)
	print("Сохраняем save_id в meta: ", save_id)
	restore_dialog.set_meta("save_id", save_id)
	
	print("=== Конец _show_restore_dialog ===\n")

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

func _format_time(seconds: int) -> String:
	var m = seconds / 60
	var s = seconds % 60
	return "%02d:%02d" % [m, s]

# ===== ОСТАЛЬНЫЕ МЕТОДЫ (без изменений) =====

func _on_game_select_pressed():
	current_game_index = (current_game_index + 1) % games.size()
	update_game_button()
	print("✅ Выбрана игра: ", games[current_game_index])

func _on_stats_pressed():
	print("📊 Открываем статистику...")
	if not ResourceLoader.exists(STATS_SCENE):
		printerr("❌ Сцена статистики не найдена: ", STATS_SCENE)
		return
	var stats_scene = load(STATS_SCENE)
	var stats_window = stats_scene.instantiate()
	add_child(stats_window)
	stats_window.popup_centered()

func _on_edit_name_pressed():
	print("✏️ Редактирование имени")
	var dialog = AcceptDialog.new()
	dialog.title = "Изменение имени"
	dialog.dialog_text = "Введите новое имя:"
	var line_edit = LineEdit.new()
	line_edit.text = Global.player_name
	line_edit.custom_minimum_size = Vector2(300, 30)
	dialog.add_child(line_edit)
	dialog.size = Vector2(400, 150)
	dialog.confirmed.connect(func():
		var new_name = line_edit.text.strip_edges()
		if new_name.length() > 0 and new_name != Global.player_name:
			change_player_name(new_name)
	)
	add_child(dialog)
	dialog.popup_centered()

func change_player_name(new_name: String):
	if not Global.player_id:
		return
	var url = Global.server_url + "/player/rename"
	var data = {
		"player_id": Global.player_id,
		"new_name": new_name
	}
	var body = JSON.new().stringify(data)
	var headers = Global.get_player_headers()
	http.request(url, headers, HTTPClient.METHOD_POST, body)
	Global.player_name = new_name
	player_name_label.text = "👤 " + new_name

func _on_quit_pressed():
	print("👋 До свидания!")
	get_tree().quit()

func update_game_button():
	game_select.text = "📦 " + games[current_game_index]
