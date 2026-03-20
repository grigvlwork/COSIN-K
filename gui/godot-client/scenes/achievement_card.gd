extends Control
class_name AchievementCard

# --- Пути к ресурсам ---
const FRAMES_PATH = "res://assets/achievements/frames/"
const ICONS_PATH = "res://assets/achievements/"
const PLACEHOLDERS_PATH = "res://assets/achievements/placeholders/"
const BACKGROUNDS_PATH = "res://assets/achievements/backgrounds/"

# --- Цвета текста Даты (для Header) ---
const DATE_COLORS = {
	"bronze": Color(0.8, 0.5, 0.2),
	"silver": Color(0.75, 0.75, 0.75),
	"gold": Color(1.0, 0.84, 0.0),
	"diamond": Color(0.6, 0.85, 1.0),
	"cosmos": Color(0.8, 0.4, 1.0)
}

# --- Маппинг текстур фона к уровню ---
const TIER_BG_FILES = {
	"bronze": "wood.png",
	"silver": "blue_velvet.png",
	"gold": "green_stone.png",
	"diamond": "purple.png",
	"cosmos": "cosmos.png"
}

# --- Ссылки на узлы ---
@onready var frame_rect: TextureRect = $FrameRect
@onready var header: PanelContainer = $MarginContainer/VBoxContainer/Header
@onready var header_label: Label = $MarginContainer/VBoxContainer/Header/HeaderLabel

# Обратите внимание на путь к узлам внутри IconPanel
@onready var bg_texture: TextureRect = $MarginContainer/VBoxContainer/IconPanel/BgTexture
@onready var icon_rect: TextureRect = $MarginContainer/VBoxContainer/IconPanel/IconRect

@onready var name_label: Label = $MarginContainer/VBoxContainer/NameLabel
@onready var desc_label: Label = $MarginContainer/VBoxContainer/DescLabel
@onready var quote_label: Label = $MarginContainer/VBoxContainer/QuoteLabel

var card_data: Dictionary = {}

func setup(data: Dictionary):
	card_data = data
	
	# 1. Устанавливаем РАМКУ (Tier)
	var tier = data.get("frame_tier", "bronze")
	var frame_path = FRAMES_PATH + "frame_%s.png" % tier
	if ResourceLoader.exists(frame_path):
		frame_rect.texture = load(frame_path)
	
	# 2. Логика отображения
	var is_unlocked = data.get("unlocked", false)
	
	if is_unlocked:
		setup_unlocked_view(data, tier)
	else:
		setup_locked_view(data, tier) # Передаем tier, чтобы показать фон следующего уровня
	
	# 3. Текстовые данные
	if data.get("is_secret") and not is_unlocked:
		name_label.text = "???"
		desc_label.text = "Секретное достижение"
		quote_label.text = "\"...\""
	else:
		name_label.text = data.get("name", "Unknown")
		desc_label.text = data.get("description", "")
		quote_label.text = "\"%s\"" % data.get("quote", "История умалчивает...")

func setup_unlocked_view(data: Dictionary, tier: String):
	# --- Header (Дата) ---
	setup_header_style(false, tier, data.get("unlocked_at", ""))
	
	# --- Background (Текстура уровня) ---
	load_background(tier)
	
	# --- Icon ---
	load_icon(data.get("icon", ""))
	
	modulate = Color(1, 1, 1)

func setup_locked_view(data: Dictionary, tier: String):
	# --- Header (Прогресс) ---
	var progress = data.get("progress", 0)
	var target = data.get("target", 1)
	setup_header_style(true, "", "%d / %d" % [progress, target])
	
	# --- Background (Текстура уровня - затемненная) ---
	# Карта-цель показывает текстуру уровня, к которому она принадлежит
	load_background(tier)
	
	# --- Icon (Заглушка) ---
	load_placeholder(data.get("category", "general"))
	
	# Затемняем карту, чтобы было видно, что она не активна
	modulate = Color(0.6, 0.6, 0.6)

# Вспомогательная функция настройки хедера
func setup_header_style(is_progress: bool, tier: String, text: String):
	var style = StyleBoxFlat.new()
	
	if is_progress:
		# Черная полоса для прогресса
		style.bg_color = Color(0, 0, 0)
		header_label.add_theme_color_override("font_color", Color.WHITE)
	else:
		# Полупрозрачный для даты
		style.bg_color = Color(0, 0, 0, 0.3)
		header_label.add_theme_color_override("font_color", DATE_COLORS.get(tier, Color.WHITE))
	
	header.add_theme_stylebox_override("panel", style)
	header_label.text = text

func load_background(tier: String):
	var file = TIER_BG_FILES.get(tier, "wood.png") # По умолчанию дерево
	var path = BACKGROUNDS_PATH + file
	
	if ResourceLoader.exists(path):
		bg_texture.texture = load(path)
	else:
		printerr("Background texture not found: ", path)

func load_icon(filename: String):
	if filename == "": return
	var path = ICONS_PATH + filename + ".png"
	if ResourceLoader.exists(path):
		icon_rect.texture = load(path)
	elif ResourceLoader.exists(ICONS_PATH + filename):
		icon_rect.texture = load(ICONS_PATH + filename)

func load_placeholder(category: String):
	var mapping = {
		"progress": "cat_wins.png",
		"suits": "cat_suits.png",
		"cards": "cat_cards.png",
		"exploration": "cat_explore.png",
		"resilience": "cat_loss.png",
		"perfection": "cat_perfect.png",
		"speed": "cat_speed.png",
		"streak": "cat_streak.png"
	}
	var file = mapping.get(category, "cat_default.png")
	var path = PLACEHOLDERS_PATH + file
	if ResourceLoader.exists(path):
		icon_rect.texture = load(path)
