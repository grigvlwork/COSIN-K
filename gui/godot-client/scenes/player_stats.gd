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

# Серии
@onready var current_win_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/CurrentWinStreakValue
@onready var max_win_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/MaxWinStreakValue
@onready var current_loose_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/CurrentLooseStreakValue
@onready var max_loose_streak_value = $MainContainer/StatsTabs/OverviewTab/StreaksPanel/HBoxContainer/MaxLooseStreakValue

# Элементы вкладки "История"
@onready var history_list = $MainContainer/StatsTabs/HistoryTab/HistoryList

# Элементы вкладки "Достижения" (ОБНОВЛЕНО)
@onready var achievements_container = $MainContainer/StatsTabs/AchievementsTab/AchievementsScroll/AchievementsContainer

# Кнопка закрытия
@onready var close_button = $MainContainer/FooterPanel/Button

# HTTP запросы
var http_stats: HTTPRequest
var http_achievements: HTTPRequest

func _ready():
	# ===== УСТАНАВЛИВАЕМ НАЗВАНИЯ ВКЛАДОК =====
	stats_tabs.set_tab_title(0, "Обзор")
	stats_tabs.set_tab_title(1, "История")
	stats_tabs.set_tab_title(2, "Достижения")
	
	# Создаём HTTP ноды
	http_stats = HTTPRequest.new()
	add_child(http_stats)
	http_stats.request_completed.connect(_on_stats_completed)
	
	http_achievements = HTTPRequest.new()
	add_child(http_achievements)
	http_achievements.request_completed.connect(_on_achievements_completed)
	
	# Подключаем кнопки
	edit_name_button.pressed.connect(_on_edit_name_pressed)
	close_button.pressed.connect(_on_close_pressed)
	
	# Загружаем данные
	load_stats()
	load_achievements()

func load_stats():
	"""Загрузить статистику с сервера"""
	if not Global.player_id:
		show_offline_message()
		return
	
	player_name_label.text = Global.player_name
	
	var url = Global.server_url + "/player/stats?player_id=" + Global.player_id
	var error = http_stats.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)
	
	if error != OK:
		print("❌ Ошибка запроса статистики")

func load_achievements():
	"""Загрузить достижения с сервера"""
	if not Global.player_id:
		return
		
	var url = Global.server_url + "/player/achievements?player_id=" + Global.player_id
	var error = http_achievements.request(url, Global.get_player_headers(), HTTPClient.METHOD_GET)
	
	if error != OK:
		print("❌ Ошибка запроса достижений")

func show_offline_message():
	"""Показать сообщение для офлайн режима"""
	player_name_label.text = "Офлайн режим"
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
	
	# Сообщение в достижениях
	for child in achievements_container.get_children():
		child.queue_free()
	var lbl = Label.new()
	lbl.text = "Достижения недоступны в офлайне"
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	achievements_container.add_child(lbl)

func _on_stats_completed(result, response_code, headers, body):
	if response_code != 200:
		print("❌ Ошибка загрузки статистики: ", response_code)
		return
	
	var json = JSON.new()
	var error = json.parse(body.get_string_from_utf8())
	
	if error == OK:
		var data = json.data
		if data.has("success") and data["success"]:
			update_stats_display(data)

func _on_achievements_completed(result, response_code, headers, body):
	if response_code != 200:
		print("❌ Ошибка загрузки достижений: ", response_code)
		return
	
	var json = JSON.new()
	var error = json.parse(body.get_string_from_utf8())
	
	if error == OK:
		var data = json.data
		if data.has("success") and data["success"]:
			render_achievements(data)

func update_stats_display(data: Dictionary):
	"""Обновить отображение статистики"""
	games_played_value.text = "%d" % data.get("games_played", 0)
	games_won_value.text = "%d" % data.get("games_won", 0)
	win_rate_value.text = str(data.get("win_rate", "0%"))
	total_score_value.text = "%d" % data.get("total_score", 0)
	highest_score_value.text = "%d" % data.get("highest_score", 0)
	total_hours_value.text = str(data.get("total_hours", "0"))
	
	current_win_streak_value.text = "%d" % data.get("current_win_streak", 0)
	max_win_streak_value.text = "%d" % data.get("best_win_streak", 0)
	current_loose_streak_value.text = "%d" % data.get("current_loose_streak", 0)
	max_loose_streak_value.text = "%d" % data.get("best_loose_streak", 0)
	
	# История
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

# ===== НОВАЯ ЛОГИКА ОТРИСОВКИ ДОСТИЖЕНИЙ =====

func render_achievements(data: Dictionary):
	"""Отрисовка списка достижений"""
	# Очищаем старые карточки
	for child in achievements_container.get_children():
		child.queue_free()
	
	var achievements = data.get("achievements", [])
	
	if achievements.size() == 0:
		var lbl = Label.new()
		lbl.text = "Пока нет достижений"
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		achievements_container.add_child(lbl)
		return
	
	for ach in achievements:
		var card = _create_achievement_card(ach)
		achievements_container.add_child(card)

func _create_achievement_card(data: Dictionary) -> Control:
	"""Создание одной карточки достижения"""
	# Основной контейнер карточки (с рамкой)
	var panel = PanelContainer.new()
	
	# Стиль карточки
	var style = StyleBoxFlat.new()
	style.bg_color = Color(0.15, 0.15, 0.2) # Темный фон
	style.border_color = Color(0.3, 0.3, 0.35)
	style.set_border_width_all(1)
	style.set_corner_radius_all(5)
	
	# Если получено - делаем светлее или золотистым
	if data.get("unlocked", false):
		style.bg_color = Color(0.2, 0.2, 0.25)
		style.border_color = Color(0.6, 0.5, 0.2) # Золотистая рамка
	
	panel.add_theme_stylebox_override("panel", style)
	panel.custom_minimum_size.y = 80
	
	# Внутренний отступ
	var margin = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_top", 5)
	margin.add_theme_constant_override("margin_right", 10)
	margin.add_theme_constant_override("margin_bottom", 5)
	panel.add_child(margin)
	
	# Горизонтальный контейнер (Иконка | Текст)
	var hbox = HBoxContainer.new()
	margin.add_child(hbox)
	
	# 1. Иконка
	var icon_rect = TextureRect.new()
	icon_rect.custom_minimum_size = Vector2(64, 64)
	icon_rect.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	icon_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	
	# Загрузка иконки (пока заглушка, если файла нет)
	# Предполагаем, что иконки лежат в res://assets/achievements/
	var icon_name = data.get("icon", "default")
	var icon_path = "res://assets/achievements/" + icon_name + ".png"
	
	if ResourceLoader.exists(icon_path):
		icon_rect.texture = load(icon_path)
	else:
		# Заглушка (квадрат цвета)
		var img = Image.create(64, 64, false, Image.FORMAT_RGBA8)
		img.fill(Color.GRAY)
		var tex = ImageTexture.create_from_image(img)
		icon_rect.texture = tex
	
	# Если не получено и скрыто - затемняем иконку
	if not data.get("unlocked", false):
		icon_rect.modulate = Color(0.5, 0.5, 0.5)
	
	hbox.add_child(icon_rect)
	
	# Разделитель
	hbox.add_spacer(false)
	
	# 2. Текстовый блок
	var vbox = VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(vbox)
	
	# Название
	var name_label = Label.new()
	name_label.text = data.get("name", "???")
	name_label.add_theme_font_size_override("font_size", 16)
	if data.get("unlocked", false):
		name_label.add_theme_color_override("font_color", Color(1, 0.85, 0.4)) # Золотой
	else:
		name_label.add_theme_color_override("font_color", Color(0.7, 0.7, 0.7))
	vbox.add_child(name_label)
	
	# Описание
	var desc_label = Label.new()
	desc_label.text = data.get("description", "")
	desc_label.add_theme_font_size_override("font_size", 12)
	desc_label.add_theme_color_override("font_color", Color(0.6, 0.6, 0.6))
	vbox.add_child(desc_label)
	
	# Прогресс бар (если цель > 0)
	var target = data.get("target", 0)
	if target > 0:
		var progress_hbox = HBoxContainer.new()
		vbox.add_child(progress_hbox)
		
		var progress_bar = ProgressBar.new()
		progress_bar.min_value = 0
		progress_bar.max_value = target
		progress_bar.value = data.get("progress", 0)
		progress_bar.show_percentage = false
		progress_bar.custom_minimum_size.y = 10
		progress_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		progress_hbox.add_child(progress_bar)
		
		# Текст прогресса справа
		var progress_text = Label.new()
		progress_text.text = "%d / %d" % [data.get("progress", 0), target]
		progress_text.add_theme_font_size_override("font_size", 10)
		progress_hbox.add_child(progress_text)
		
		# Если получено, но хотим скрыть бар
		if data.get("unlocked", false):
			progress_bar.value = target # Полный
	
	return panel

func _on_edit_name_pressed():
	"""Редактирование имени игрока"""
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
	"""Отправить новое имя на сервер"""
	if not Global.player_id:
		return
	
	var url = Global.server_url + "/player/rename"
	var data_to_send = {
		"player_id": Global.player_id,
		"new_name": new_name
	}
	var body = JSON.new().stringify(data_to_send)
	var headers = Global.get_player_headers()
	# Используем http_stats или создаем новый запрос для rename
	# Здесь использовал http_stats для простоты, но лучше отдельный
	var http_rename = HTTPRequest.new()
	add_child(http_rename)
	http_rename.request(url, headers, HTTPClient.METHOD_POST, body)
	
	Global.player_name = new_name
	player_name_label.text = new_name
	
	stats_updated.emit()

func _on_close_pressed():
	"""Закрыть окно статистики"""
	queue_free()
