# scenes/ui/player_stats.gd
extends Window

signal stats_updated

# ===== ССЫЛКИ НА ЭЛЕМЕНТЫ UI =====
@onready var player_name_label = $MainContainer/HBoxContainer/PlayerNameLabel
@onready var edit_name_button = $MainContainer/HBoxContainer/EditNameButton

# Вкладки
@onready var stats_tabs = $MainContainer/StatsTabs

# Элементы вкладки "Обзор"
@onready var games_played_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/GamesPlayedValue
@onready var games_won_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/GamesWonValue
@onready var win_rate_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/WinRateValue
@onready var total_score_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/TotalScoreValue
@onready var highest_score_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/HighestScoreValue
@onready var total_hours_value = $MainContainer/StatsTabs/OverviewTab/GridContainer/TotalHoursValue

# Серии (теперь их 4 значения)
@onready var current_win_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/CurrentWinStreakValue
@onready var max_win_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/MaxWinStreakValue
@onready var current_loose_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/CurrentLooseStreakValue
@onready var max_loose_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/MaxLooseStreakValue

# Элементы вкладки "История"
@onready var history_list = $MainContainer/StatsTabs/HistoryTab/HistoryList

# Элементы вкладки "Достижения"
@onready var achievements_list = $MainContainer/StatsTabs/AchievementsTab/AchievementsList

# Кнопка закрытия
@onready var close_button = $MainContainer/FooterPanel/Button

# HTTP запросы
var http: HTTPRequest

func _ready():
	# ===== УСТАНАВЛИВАЕМ НАЗВАНИЯ ВКЛАДОК =====
	stats_tabs.set_tab_title(0, "Обзор")
	stats_tabs.set_tab_title(1, "История")
	stats_tabs.set_tab_title(2, "Достижения")
	
	# Создаём HTTP для запросов
	http = HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(_on_stats_completed)
	
	# Подключаем кнопки
	edit_name_button.pressed.connect(_on_edit_name_pressed)
	close_button.pressed.connect(_on_close_pressed)
	
	# Загружаем статистику
	load_stats()

func load_stats():
	"""Загрузить статистику с сервера"""
	if not Global.player_id:
		show_offline_message()
		return
	
	# Показываем имя игрока
	player_name_label.text = Global.player_name
	
	# Запрашиваем статистику
	var url = Global.server_url + "/player/stats?player_id=" + Global.player_id
	var error = http.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)
	
	if error != OK:
		print("❌ Ошибка запроса статистики")
		show_offline_message()

func show_offline_message():
	"""Показать сообщение для офлайн режима"""
	player_name_label.text = "Офлайн режим"
	
	# Очищаем все значения
	games_played_value.text = "-"
	games_won_value.text = "-"
	win_rate_value.text = "-"
	total_score_value.text = "-"
	highest_score_value.text = "-"
	total_hours_value.text = "-"
	
	current_win_streak_value.text = "-"
	max_win_streak_value.text = "-"
	current_loose_streak_value.text = "-"
	max_loose_streak_value.text = "-"
	
	history_list.add_item("Нет подключения к серверу")
	history_list.add_item("Статистика недоступна")

func _on_stats_completed(result, response_code, headers, body):
	if response_code != 200:
		print("❌ Ошибка загрузки статистики: ", response_code)
		return
	
	var response_text = body.get_string_from_utf8()
	var json = JSON.new()
	var error = json.parse(response_text)
	
	if error == OK:
		var data = json.data
		if data.has("success") and data["success"]:
			update_stats_display(data)
		else:
			print("⚠️ Ошибка сервера: ", data.get("error", "Unknown"))
	else:
		print("❌ Ошибка парсинга статистики")

func update_stats_display(data: Dictionary):
	"""Обновить отображение статистики"""
	
	# Основная статистика
	games_played_value.text = "%d" % data.get("games_played", 0)
	games_won_value.text = "%d" % data.get("games_won", 0)
	win_rate_value.text = str(data.get("win_rate", "0%"))
	total_score_value.text = "%d" % data.get("total_score", 0)
	highest_score_value.text = "%d" % data.get("highest_score", 0)
	total_hours_value.text = str(data.get("total_hours", "0"))
	
	# Серии побед и поражений
	# Используем форматирование %d для целых чисел
	current_win_streak_value.text = "%d" % data.get("current_win_streak", 0)
	max_win_streak_value.text = "%d" % data.get("best_win_streak", 0)
	current_loose_streak_value.text = "%d" % data.get("current_loose_streak", 0)
	max_loose_streak_value.text = "%d" % data.get("best_loose_streak", 0)
	
	# История игр
	if data.has("recent_games"):
		history_list.clear()
		var games = data["recent_games"]
		
		if games.size() == 0:
			history_list.add_item("Нет завершённых игр")
		else:
			for game in games:
				var game_text = "%s - %s (%d очков)" % [
					game.get("date", "???"),
					"Победа" if game.get("result") == "won" else "Поражение",
					game.get("score", 0)
				]
				history_list.add_item(game_text)
	
	# Достижения (пока заглушка)
	if data.has("achievements"):
		achievements_list.clear()
		var achievements = data["achievements"]
		if achievements.size() == 0:
			achievements_list.add_item("Пока нет достижений")
			achievements_list.add_item("Играйте и побеждайте!")
		else:
			for ach in achievements:
				achievements_list.add_item(ach)

func _on_edit_name_pressed():
	"""Редактирование имени игрока"""
	print("✏️ Редактирование имени")
	
	# Создаём диалог ввода
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
	player_name_label.text = new_name
	
	# Сигнал для обновления меню
	stats_updated.emit()

func _on_close_pressed():
	"""Закрыть окно статистики"""
	queue_free()
