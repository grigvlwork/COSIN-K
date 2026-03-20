extends Control

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var game_select = $MainContainer/GameSelectButton
@onready var start_button = $MainContainer/StartButton
@onready var stats_button = $MainContainer/StatsButton
@onready var achievements_button = $MainContainer/AchievementsButton
@onready var quit_button = $MainContainer/QuitButton

# ===== ЭЛЕМЕНТЫ ВЕРХНЕЙ ПАНЕЛИ =====
@onready var player_name_label = $MainContainer/TopPanel/PlayerNameLabel
@onready var edit_name_button = $MainContainer/TopPanel/EditNameButton

# ===== ДИАЛОГ ВОССТАНОВЛЕНИЯ =====
@onready var restore_dialog = $RestoreDialog

# ===== ПЕРЕМЕННЫЕ =====
var http: HTTPRequest
var games = ["Клондайк"]
var current_game_index = 0
const STATS_SCENE = "res://scenes/PlayerStats.tscn"
const ACHIEVEMENTS_SCENE = "res://scenes/AchievementsAlbum.tscn"

var pending_action = ""

# Флаг доступности сервера
var is_server_online = false

func _ready():
	# Создаём HTTP для запросов к серверу
	http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_http_completed)
	
	# Подключаем кнопки меню
	game_select.pressed.connect(_on_game_select_pressed)
	start_button.pressed.connect(_on_start_pressed)
	stats_button.pressed.connect(_on_stats_pressed)
	achievements_button.pressed.connect(_on_achievements_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	
	# Подключаем кнопку редактирования имени
	edit_name_button.pressed.connect(_on_edit_name_pressed)
	
	# Подключаем сигналы диалога восстановления
	if restore_dialog:
		restore_dialog.confirmed.connect(_on_restore_confirmed)
		restore_dialog.canceled.connect(_on_restore_declined)
	
	# Обновляем текст кнопки выбора игры
	update_game_button()
	
	# === НОВАЯ ЛОГИКА ===
	# Сразу отключаем кнопки, пока не проверим сервер
	set_ui_online_state(false)
	player_name_label.text = "📡 Проверка соединения..."
	
	# Инициализируем игрока (это и будет проверкой сервера)
	initialize_player()

# ===== УПРАВЛЕНИЕ СОСТОЯНИЕМ UI =====

func set_ui_online_state(is_online: bool):
	"""Включает или выключает кнопки, зависящие от сервера"""
	is_server_online = is_online
	
	start_button.disabled = !is_online
	stats_button.disabled = !is_online
	achievements_button.disabled = !is_online
	game_select.disabled = !is_online
	edit_name_button.disabled = !is_online
	
	if !is_online:
		player_name_label.text = "⚠️ Сервер недоступен"
		game_select.text = "📦 Офлайн"
	else:
		update_game_button()

# ===== ИНИЦИАЛИЗАЦИЯ И СЕТЬ =====

func initialize_player():
	"""Инициализация игрока при запуске"""
	if Global.is_player_loaded:
		player_name_label.text = "👤 " + Global.player_name
		connect_to_server()
	else:
		#player_name_label.text = "👤 Загрузка..." # Уже выставили выше
		request_new_identity()

func request_new_identity():
	"""Запросить новый UUID у сервера"""
	print("📡 Запрос нового UUID...")
	var url = Global.server_url + "/player/identity"
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)

	if error != OK:
		print("❌ Ошибка запроса UUID")
		# Если запрос даже не удалось отправить (внутренняя ошибка Godot)
		set_ui_online_state(false)

func connect_to_server():
	"""Подключиться к серверу с существующим UUID"""
	print("📡 Подключение к серверу с UUID: ", Global.player_id)
	var url = Global.server_url + "/player/identity?player_id=" + Global.player_id
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)

	if error != OK:
		print("❌ Ошибка подключения к серверу")
		set_ui_online_state(false)

# ===== ОБРАБОТКА ОТВЕТОВ =====

func _on_http_completed(result, response_code, headers, body):
	# === ПРОВЕРКА СОЕДИНЕНИЯ ===
	# result != RESULT_SUCCESS означает, что сервер не ответил вообще (таймаут, ошибка сети)
	if result != HTTPRequest.RESULT_SUCCESS:
		printerr("❌ Сервер недоступен (HTTP Result: ", result, ")")
		set_ui_online_state(false)
		return

	# Если мы здесь — сервер ответил, значит он онлайн
	set_ui_online_state(true)

	# Дальше стандартная обработка ответов
	if response_code == 409:
		print("⚠️ Конфликт: найдено активное сохранение")
		var response_text = body.get_string_from_utf8()
		var json = JSON.new()
		var error = json.parse(response_text)
		if error == OK:
			_show_restore_dialog(json.data)
		else:
			_proceed_to_game_scene("new")
		return
		
	if response_code != 200:
		print("⚠️ Ошибка сервера: ", response_code)
		var response_text = body.get_string_from_utf8()
		print("Тело ответа: ", response_text)
		
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
		
		if data.has("player_id"):
			var new_id = data["player_id"]
			var new_name = data.get("player_name", "Игрок")
			Global.save_player_identity(new_id, new_name)
			player_name_label.text = "👤 " + new_name
			print("✅ Получен UUID: ", new_id)
		
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
		
		elif pending_action == "load_save":
			if data.has("success") and data["success"]:
				print("📦 Отладка данных загрузки:")
				print("   Ключи data: ", data.keys())
				if data.has("state"):
					print("   Ключи data['state']: ", data["state"].keys())
				
				if data.has("state"):
					print("✅ Состояние загружено, передаем в игру")
					Global.set_pending_save(data["state"], data.get("time", 0), data.get("saved_game_id", 0))
					_proceed_to_game_scene("load")
				else:
					printerr("❌ В ответе нет ключа 'state'!")
					_proceed_to_game_scene("new")
			else:
				printerr("❌ Ошибка данных загрузки: ", data.get("error", "Unknown"))
				_proceed_to_game_scene("new")
		
		elif data.has("message") and data.has("player_name"):
			print("✅ Имя изменено")
			
	else:
		print("❌ Ошибка парсинга JSON: ", response_text)
		if pending_action == "check_save" or pending_action == "load_save":
			_proceed_to_game_scene("new")

# ===== ЛОГИКА ЗАПУСКА ИГРЫ =====

func _on_start_pressed():
	"""Кнопка 'Играть' - проверяем наличие сохранений"""
	# Добавляем проверку на случай, если пользователь нажмет кнопку до восстановления связи
	if not is_server_online:
		print("⚠️ Попытка начать игру без соединения с сервером")
		return

	print("🔍 Проверка сохранений перед стартом...")
	
	if not Global.is_player_loaded or Global.player_id.is_empty():
		print("⏳ Ожидание загрузки player_id...")
		await get_tree().create_timer(0.5).timeout
		if not Global.is_player_loaded:
			request_new_identity()
			await get_tree().create_timer(0.5).timeout
	
	if games[current_game_index] == "Клондайк":
		Global.current_variant = "klondike"
	
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
		var body = JSON.new().stringify({
			"player_id": Global.player_id,
			"save_id": save_id
		})
		var headers = ["Content-Type: application/json"]
		var err = http.request(Global.server_url + "/load/save", headers, HTTPClient.METHOD_POST, body)
		
		if err != OK:
			printerr("❌ Ошибка отправки запроса загрузки: ", err)
			_proceed_to_game_scene("new")
	else:
		printerr("❌ Неверный ID сохранения")
		_proceed_to_game_scene("new")

func _on_restore_declined():
	"""Игрок нажал 'Новая игра'"""
	print("➡️ Начинаем новую игру (удаление старой)")
	_proceed_to_game_scene("new")

func _proceed_to_game_scene(mode: String):
	"""Переключение на сцену игры"""
	print("\n=== 🎮 _proceed_to_game_scene ===")
	print("mode: ", mode)
	
	var scene_path = "res://scenes/games/klondike.tscn"
	
	if not ResourceLoader.exists(scene_path):
		printerr("❌ Файл сцены не найден: ", scene_path)
		return
	
	if mode == "new":
		Global.clear_pending_save()
	elif mode == "load":
		pass # pending state already set
	
	get_tree().change_scene_to_file(scene_path)

# ===== ДИАЛОГ ВОССТАНОВЛЕНИЯ =====

func _show_restore_dialog(save_data: Dictionary):
	"""Показать диалог восстановления"""
	if not restore_dialog:
		_proceed_to_game_scene("new")
		return
	
	var moves = save_data.get("moves", 0)
	var time_sec = save_data.get("time", 0)
	var score = save_data.get("score", 0)
	
	var text = "Найдена незаконченная игра!\n\n"
	text += "📊 Ходы: %d\n" % moves
	text += "⏱️ Время: %s\n" % _format_time(time_sec)
	text += "💰 Счет: %d\n\n" % score
	
	if save_data.get("is_suspended", false):
		text += "(Прошло более часа с последнего хода)"
	else:
		text += "(Игра была прервана)"
	
	text += "\nПродолжить?"
	
	restore_dialog.dialog_text = text
	restore_dialog.popup_centered()
	restore_dialog.set_meta("save_id", save_data.get("save_id", 0))

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

func _format_time(seconds: int) -> String:
	var m = seconds / 60
	var s = seconds % 60
	return "%02d:%02d" % [m, s]

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

func _on_achievements_pressed():
	print("🏆 Открываем альбом достижений...")
	if not ResourceLoader.exists(ACHIEVEMENTS_SCENE):
		printerr("❌ Сцена достижений не найдена: ", ACHIEVEMENTS_SCENE)
		return
		
	var album_scene = load(ACHIEVEMENTS_SCENE)
	var album_window = album_scene.instantiate()
	add_child(album_window)
	
	if album_window.has_signal("close_requested"):
		album_window.close_requested.connect(func(): album_window.queue_free())

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
