# gui/godot-client/scenes/global.gd
extends Node

# ===== НАСТРОЙКИ СЕРВЕРА =====
var server_url = "http://127.0.0.1:8080"
var current_variant = "klondike"  # По умолчанию Клондайк
var draw_three = false            # 1 карта

# ===== ИДЕНТИФИКАЦИЯ ИГРОКА =====
var player_id: String = ""
var player_name: String = ""
var is_player_loaded: bool = false
const PLAYER_DATA_FILE = "user://player.identity"

# ===== ПЕРЕДАЧА ДАННЫХ МЕЖДУ СЦЕНАМИ =====
# Используется для загрузки сохранения из меню в игру
var pending_game_state: Dictionary = {}  # Само состояние (словарь)
var pending_game_time: int = 0           # Время игры из сохранения
var pending_game_id: int = 0             # ID игры (если нужен для API)

# Названия игр для отображения
var game_names = {
	"klondike": "Клондайк (1 карта)",
	"klondike-3": "Клондайк (3 карты)"
}

func _ready():
	print("🌍 Глобальный менеджер загружен")
	print("📡 Сервер: ", server_url)
	print("🎮 Игра: ", get_current_game_name())
	
	# Загружаем UUID при старте
	load_player_identity()

# ===== УПРАВЛЕНИЕ СОСТОЯНИЕМ ЗАГРУЗКИ =====

func set_pending_save(state: Dictionary, time: int, game_id: int) -> void:
	"""
	Сохранить данные игры для загрузки в сцене.
	Вызывается из menu.gd перед переключением сцены.
	"""
	print("\n=== 📦 Global.set_pending_save() ===")
	print("Входные параметры:")
	print("  - state тип: ", typeof(state))
	print("  - state размер: ", state.size())
	print("  - time: ", time)
	print("  - game_id: ", game_id)
	
	# Проверим структуру state
	if state.size() > 0:
		print("  - Ключи state: ", state.keys())
		# Проверим наличие критически важных ключей
		var required_keys = ["piles", "stock", "waste", "score", "moves_count"]
		for key in required_keys:
			print("    - has '", key, "': ", state.has(key))
	else:
		print("  ⚠️ state пустой!")
	
	pending_game_state = state
	pending_game_time = time
	pending_game_id = game_id
	
	print("✅ Данные сохранены:")
	print("  - pending_game_state размер: ", pending_game_state.size())
	print("  - pending_game_time: ", pending_game_time)
	print("  - pending_game_id: ", pending_game_id)
	print("  - has_pending_save(): ", has_pending_save())
	print("=== Конец set_pending_save ===\n")

func clear_pending_save() -> void:
	"""
	Очистить данные загрузки.
	Вызывается в klondike.gd после применения состояния.
	"""
	print("\n=== 🧹 Global.clear_pending_save() ===")
	print("До очистки:")
	print("  - pending_game_state размер: ", pending_game_state.size())
	print("  - pending_game_time: ", pending_game_time)
	print("  - pending_game_id: ", pending_game_id)
	print("  - has_pending_save(): ", has_pending_save())
	
	pending_game_state.clear()
	pending_game_time = 0
	pending_game_id = 0
	
	print("После очистки:")
	print("  - pending_game_state размер: ", pending_game_state.size())
	print("  - pending_game_time: ", pending_game_time)
	print("  - pending_game_id: ", pending_game_id)
	print("  - has_pending_save(): ", has_pending_save())
	print("=== Конец clear_pending_save ===\n")

func has_pending_save() -> bool:
	"""
	Проверить, есть ли данные для загрузки.
	"""
	var result = not pending_game_state.is_empty()
	print("🔍 Global.has_pending_save() = ", result, " (размер state: ", pending_game_state.size(), ")")
	return result

# ===== РАБОТА С ИДЕНТИФИКАЦИЕЙ =====

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

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

func get_current_game_name() -> String:
	"""Получить название текущей игры"""
	return game_names.get(current_variant, current_variant)

func set_game(variant: String):
	"""Сменить игру"""
	current_variant = variant
	print("🎮 Выбрана игра: ", get_current_game_name())
