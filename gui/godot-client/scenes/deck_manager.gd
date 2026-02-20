# deck_manager.gd
extends Node

# === НАСТРОЙКИ ПО УМОЛЧАНИЮ ===
# Папка с базовой колодой (та, что у тебя сейчас в assets/cards)
const DEFAULT_DECK_PATH = "res://assets/decks/classic"

# Ключи для файла конфигурации
const SETTINGS_FILE = "user://settings.cfg"
const SETTINGS_SECTION = "game"
const SETTINGS_KEY = "current_deck_path"

# === ПЕРЕМЕННЫЕ ===
var current_deck_path: String = DEFAULT_DECK_PATH

func _ready():
	# При запуске игры загружаем сохраненную колоду
	load_settings()

# === УПРАВЛЕНИЕ НАСТРОЙКАМИ ===

func load_settings():
	var config = ConfigFile.new()
	# Пытаемся открыть файл настроек
	var err = config.load(SETTINGS_FILE)
	
	if err == OK:
		# Если файл есть, читаем путь
		var saved_path = config.get_value(SETTINGS_SECTION, SETTINGS_KEY, DEFAULT_DECK_PATH)
		# Можно добавить проверку, существует ли папка, но пока верим сохраненному значению
		current_deck_path = saved_path
		print("📦 Загружена колода: ", current_deck_path)
	else:
		# Если файла нет, используем дефолт и создаем файл
		current_deck_path = DEFAULT_DECK_PATH
		save_settings()
		print("📦 Создан файл настроек. Используем колоду по умолчанию.")

func save_settings():
	var config = ConfigFile.new()
	config.set_value(SETTINGS_SECTION, SETTINGS_KEY, current_deck_path)
	var err = config.save(SETTINGS_FILE)
	if err != OK:
		printerr("❌ Ошибка сохранения настроек колоды!")

# Функция для смены колоды (будет использоваться в редакторе/меню)
func set_deck(new_path: String):
	current_deck_path = new_path
	save_settings()
	print("🃏 Колода изменена на: ", new_path)

# === ЛОГИКА ТЕКСТУР ===

# Главная функция, которую будет вызывать game.gd
func get_card_texture(suit: String, rank: int, face_up: bool) -> Texture2D:
	var file_path = ""
	
	if face_up:
		# Формируем имя файла для лицевой стороны
		# Твоя логика: 1=ace, 11=jack, 12=queen, 13=king
		var rank_name = str(rank)
		match rank:
			1: rank_name = "ace"
			11: rank_name = "jack"
			12: rank_name = "queen"
			13: rank_name = "king"
		
		# Твоя логика: HEARTS -> hearts
		var suit_name = suit.to_lower()
		
		# Собираем путь: "res://assets/cards/ace_of_hearts.png"
		file_path = current_deck_path.path_join(rank_name + "_of_" + suit_name + ".png")
	else:
		# Рубашка карты
		file_path = current_deck_path.path_join("back.png")

	# Проверяем, существует ли файл
	if ResourceLoader.exists(file_path):
		return load(file_path)
	else:
		# Если файла нет (например, мод кривой), возвращаем заглушку или null
		printerr("⚠️ Файл текстуры не найден: ", file_path)
		return null

# В DeckManager.gd
func get_back_texture() -> Texture2D:
	var path = current_deck_path.path_join("back.png")
	if ResourceLoader.exists(path):
		return load(path)
	return null
