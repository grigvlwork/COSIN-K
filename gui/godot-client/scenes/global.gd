extends Node

# Глобальные переменные
var server_url = "http://127.0.0.1:8080"
var current_variant = "klondike"  # По умолчанию Клондайк
var draw_three = false            # 1 карта

# Названия игр для отображения
var game_names = {
	"klondike": "Клондайк (1 карта)",
	"klondike-3": "Клондайк (3 карты)"
}

func _ready():
	print("🌍 Глобальный менеджер загружен")
	print("📡 Сервер: ", server_url)
	print("🎮 Игра: ", get_current_game_name())

func get_current_game_name() -> String:
	"""Получить название текущей игры"""
	return game_names.get(current_variant, current_variant)

func set_game(variant: String):
	"""Сменить игру"""
	current_variant = variant
	print("🎮 Выбрана игра: ", get_current_game_name())
