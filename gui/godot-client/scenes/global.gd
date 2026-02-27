extends Node

# Глобальные переменные
var server_url = "http://127.0.0.1:8080"
var current_variant = "klondike"  # По умолчанию Клондайк
var draw_three = false            # 1 карта

# ===== НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ UUID =====
var player_id: String = ""
var player_name: String = ""
var is_player_loaded: bool = false
const PLAYER_DATA_FILE = "user://player.identity"

# Названия игр для отображения
var game_names = {
	"klondike": "Клондайк (1 карта)",
	"klondike-3": "Клондайк (3 карты)"
}

func _ready():
	print("🌍 Глобальный менеджер загружен")
	print("📡 Сервер: ", server_url)
	print("🎮 Игра: ", get_current_game_name())
	
	# ===== НОВОЕ: Загружаем UUID при старте =====
	load_player_identity()

# ===== НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С UUID =====

func load_player_identity() -> void:
	"""Загрузить UUID из файла"""
	if FileAccess.file_exists(PLAYER_DATA_FILE):
		var file = FileAccess.open(PLAYER_DATA_FILE, FileAccess.READ)
		if file:
			var data = JSON.new().parse_string(file.get_as_text())
			if data and data.has("player_id"):
				player_id = data["player_id"]
				player_name = data.get("player_name", "Игрок")
				is_player_loaded = true
				print("✅ Загружен UUID: ", player_id)
				return
	
	print("ℹ️ UUID не найден, будет создан при подключении к серверу")
	is_player_loaded = false

func save_player_identity(id: String, name: String = "") -> void:
	"""Сохранить UUID в файл"""
	var data = {
		"player_id": id,
		"player_name": name if name else "Игрок_" + id.left(6),
		"first_seen": Time.get_datetime_string_from_system(),
		"last_seen": Time.get_datetime_string_from_system()
	}
	
	var file = FileAccess.open(PLAYER_DATA_FILE, FileAccess.WRITE)
	if file:
		file.store_string(JSON.new().stringify(data))
		player_id = id
		player_name = data["player_name"]
		is_player_loaded = true
		print("✅ Сохранён UUID: ", id)

func get_player_headers() -> PackedStringArray:
	"""Получить заголовки HTTP с UUID"""
	var headers = PackedStringArray([
		"Content-Type: application/json"
	])
	return headers

func get_player_data() -> Dictionary:
	"""Получить данные игрока для отправки на сервер"""
	return {
		"player_id": player_id
	}

# Существующие методы
func get_current_game_name() -> String:
	"""Получить название текущей игры"""
	return game_names.get(current_variant, current_variant)

func set_game(variant: String):
	"""Сменить игру"""
	current_variant = variant
	print("🎮 Выбрана игра: ", get_current_game_name())
