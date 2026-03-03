extends Control

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var game_select = $MainContainer/GameSelectButton
@onready var start_button = $MainContainer/StartButton
@onready var stats_button = $MainContainer/StatsButton
@onready var quit_button = $MainContainer/QuitButton

# ===== ЭЛЕМЕНТЫ ВЕРХНЕЙ ПАНЕЛИ =====
@onready var player_name_label = $MainContainer/TopPanel/PlayerNameLabel
@onready var edit_name_button = $MainContainer/TopPanel/EditNameButton

# ===== ПЕРЕМЕННЫЕ =====
var http: HTTPRequest
var games = ["Клондайк"]
var current_game_index = 0
const STATS_SCENE = "res://scenes/PlayerStats.tscn"

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
	
	# Обновляем текст кнопки выбора игры
	update_game_button()
	
	# Инициализируем игрока
	initialize_player()

# ===== МЕТОДЫ ИНИЦИАЛИЗАЦИИ =====

func initialize_player():
	"""Инициализация игрока при запуске"""
	if Global.is_player_loaded:
		# Уже есть UUID - обновляем отображение
		player_name_label.text = "👤 " + Global.player_name
		# Подключаемся к серверу для обновления статистики
		connect_to_server()
	else:
		# Нет UUID - запрашиваем новый
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
	else:
		print("❌ Ошибка парсинга JSON")

func handle_success_response(data: Dictionary):
	"""Обработка успешных ответов от сервера"""
	
	# Ответ с UUID
	if data.has("player_id"):
		var new_id = data["player_id"]
		var new_name = data.get("player_name", "Игрок")
		Global.save_player_identity(new_id, new_name)
		player_name_label.text = "👤 " + new_name
		print("✅ Получен UUID: ", new_id)
		
		if data.has("is_new") and data["is_new"]:
			print("🎉 Добро пожаловать, новый игрок!")
			# Можно показать приветственное сообщение
			show_welcome_message()
	
	# Ответ со статистикой
	if data.has("games_played"):
		# Обновляем отображение, если нужно
		pass

func show_welcome_message():
	"""Показать приветственное сообщение (опционально)"""
	# Можно создать всплывающее уведомление
	print("🌟 Добро пожаловать в игру!")

# ===== ОБРАБОТЧИКИ КНОПОК =====

func _on_game_select_pressed():
	"""Переключение между играми"""
	current_game_index = (current_game_index + 1) % games.size()
	update_game_button()
	print("✅ Выбрана игра: ", games[current_game_index])

func _on_start_pressed():
	"""Начать игру"""
	print("🎮 Запуск: ", games[current_game_index])
	
	# Сохраняем выбранную игру в глобальные настройки
	if games[current_game_index] == "Клондайк":
		Global.current_variant = "klondike"
	
	# Переходим на экран игры
	var scene_path = "res://scenes/games/klondike.tscn"
	
	if not ResourceLoader.exists(scene_path):
		printerr("❌ Файл сцены не найден: ", scene_path)
		return
	
	get_tree().change_scene_to_file(scene_path)

func _on_stats_pressed():
	"""Открыть окно статистики"""
	print("📊 Открываем статистику...")
	
	if not ResourceLoader.exists(STATS_SCENE):
		printerr("❌ Сцена статистики не найдена: ", STATS_SCENE)
		return
	
	var stats_scene = load(STATS_SCENE)
	var stats_window = stats_scene.instantiate()
	add_child(stats_window)
	stats_window.popup_centered()

func _on_edit_name_pressed():
	"""Редактирование имени игрока"""
	print("✏️ Редактирование имени")
	
	# Создаём простой диалог ввода (без отдельной сцены)
	var dialog = AcceptDialog.new()
	dialog.title = "Изменение имени"
	dialog.dialog_text = "Введите новое имя:"
	
	# Добавляем поле ввода
	var line_edit = LineEdit.new()
	line_edit.text = Global.player_name
	line_edit.custom_minimum_size = Vector2(300, 30)
	dialog.add_child(line_edit)
	
	# Настраиваем диалог
	dialog.size = Vector2(400, 150)
	
	# Подключаем сигнал подтверждения
	dialog.confirmed.connect(func():
		var new_name = line_edit.text.strip_edges()
		if new_name.length() > 0 and new_name != Global.player_name:
			change_player_name(new_name)
	)
	
	add_child(dialog)
	dialog.popup_centered()

func change_player_name(new_name: String):
	"""Отправить новое имя на сервер"""
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
	
	# Временно обновляем локально
	Global.player_name = new_name
	player_name_label.text = "👤 " + new_name

func _on_quit_pressed():
	"""Выход из игры"""
	print("👋 До свидания!")
	get_tree().quit()

# ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====

func update_game_button():
	"""Обновляем текст на кнопке выбора игры"""
	game_select.text = "📦 " + games[current_game_index]
