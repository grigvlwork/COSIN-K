extends Control

@onready var game_select = $MainContainer/GameSelectButton
@onready var start_button = $MainContainer/StartButton
@onready var quit_button = $MainContainer/QuitButton

# Список доступных игр (пока только одна)
var games = ["Клондайк"]
var current_game_index = 0

func _ready():
	# Подключаем кнопки
	game_select.pressed.connect(_on_game_select_pressed)
	start_button.pressed.connect(_on_start_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	
	# Обновляем текст кнопки
	update_game_button()

func update_game_button():
	"""Обновляем текст на кнопке выбора игры"""
	game_select.text = "📦 " + games[current_game_index]

func _on_game_select_pressed():
	"""Переключение между играми"""
	# Пока только Клондайк, но готовим на будущее
	current_game_index = (current_game_index + 1) % games.size()
	update_game_button()

	# Показываем, что выбрали
	print("✅ Выбрана игра: ", games[current_game_index])

func _on_start_pressed():
	"""Начать игру"""
	print("🎮 Запуск: ", games[current_game_index])

	# Сохраняем выбранную игру в глобальные настройки
	if has_node("/root/Global"):
		if games[current_game_index] == "Клондайк":
			Global.current_variant = "klondike"

	# Переходим на экран игры
	get_tree().change_scene_to_file("res://game.tscn")

func _on_quit_pressed():
	"""Выход из игры"""
	print("👋 До свидания!")
	get_tree().quit()
