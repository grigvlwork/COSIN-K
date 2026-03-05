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
	if response_code != 200:
		print("⚠️ Ошибка сервера: ", response_code)
		# Если сервер недоступен, все равно даем играть (офлайн режим)
		if pending_action == "check_save":
			_proceed_to_game_scene("new")
		return
	
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)
	
	if error == OK:
		var data = json.data
		if data.has("success") and data["success"]:
			handle_success_response(data)
		else:
			print("⚠️ Ошибка: ", data.get("error", "Unknown"))
			# Если ошибка логики, все равно идем в игру
			if pending_action == "check_save":
				_proceed_to_game_scene("new")
	else:
		print("❌ Ошибка парсинга JSON")

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

	# Определяем тип игры
	if games[current_game_index] == "Клондайк":
		Global.current_variant = "klondike"
	
	# Запрашиваем у сервера информацию о сохранениях
	pending_action = "check_save"
	var url = Global.server_url + "/load?player_id=" + Global.player_id + "&game_type=" + Global.current_variant
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)
	
	if error != OK:
		# Если ошибка запроса, просто идем в игру (новую)
		_proceed_to_game_scene("new")

func _show_restore_dialog(save_data: Dictionary):
	"""Показать диалог восстановления"""
	if not restore_dialog:
		printerr("❌ RestoreDialog не найден в сцене!")
		# Если диалога нет, по умолчанию начинаем новую
		_proceed_to_game_scene("new")
		return
	
	# Формируем текст
	var text = "Найдена незаконченная игра!\n\n"
	text += "📊 Ходы: %d\n" % save_data.get("moves", 0)
	text += "⏱️ Время: %s\n" % _format_time(save_data.get("time", 0))
	text += "💰 Счет: %d\n\n" % save_data.get("score", 0)
	
	if save_data.get("is_suspended", false):
		text += "(Прошло более часа с последнего хода)"
	else:
		text += "(Игра была прервана)"
	
	text += "\nПродолжить?"
	
	restore_dialog.dialog_text = text
	restore_dialog.popup_centered()
	
	# Сохраняем ID сохранения для использования в колбэках
	restore_dialog.set_meta("save_id", save_data.save_id)

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
		var url = Global.server_url + "/load/save"
		http.request(url, Global.get_player_headers(), HTTPClient.METHOD_POST, body)
	else:
		_proceed_to_game_scene("new")

func _on_restore_declined():
	"""Игрок нажал 'Новая игра'"""
	print("➡️ Начинаем новую игру (удаление старой)")
	# Мы не удаляем сохранение отдельным запросом, 
	# просто говорим игре начать новую (force_new=true)
	_proceed_to_game_scene("new")

func _proceed_to_game_scene(mode: String):
	"""Переключение на сцену игры"""
	var scene_path = "res://scenes/games/klondike.tscn"
	
	if not ResourceLoader.exists(scene_path):
		printerr("❌ Файл сцены не найден: ", scene_path)
		return
	
	# Если режим "new", очищаем возможный pending state
	if mode == "new":
		Global.clear_pending_save()
	
	# Переход
	get_tree().change_scene_to_file(scene_path)

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
