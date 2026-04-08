# gui/godot-client/scenes/achievement_card.gd
extends Control
class_name AchievementCard

# --- Пути к ресурсам ---
const FRAMES_PATH = "res://assets/achievements/frames/"
const ICONS_PATH = "res://assets/achievements/"
const PLACEHOLDERS_PATH = "res://assets/achievements/placeholders/"
const BACKGROUNDS_PATH = "res://assets/achievements/backgrounds/"

# --- Цвета текста даты ---
const DATE_COLORS = {
	"bronze": Color(0.8, 0.5, 0.2),
	"silver": Color(0.75, 0.75, 0.75),
	"gold": Color(1.0, 0.84, 0.0),
	"diamond": Color(0.6, 0.85, 1.0),
	"cosmos": Color(0.8, 0.4, 1.0)
}

# --- Текстуры фона по уровню ---
const TIER_BG_FILES = {
	"bronze": "wood.png",
	"silver": "blue_velvet.png",
	"gold": "green_stone.png",
	"diamond": "purple.png",
	"cosmos": "cosmos.png"
}

# --- Узлы ---
# ВНИМАНИЕ: Имена переменных должны совпадать с новыми именами в .tscn
# HeaderLabel -> Название достижения
@onready var name_label: Label = $HeaderLabel 
# OpenedAt -> Дата или Статус
@onready var status_label: Label = $OpenedAt 

@onready var frame_rect: TextureRect = $FrameRect
@onready var bg_texture: TextureRect = $IconPanel/BgTexture
@onready var icon_rect: TextureRect = $IconPanel/IconRect
@onready var desc_label: Label = $DescLabel
@onready var quote_label: Label = $QuoteLabel
@onready var current_score_label: Label = $CurrentScore
@onready var target_score_label: Label = $TargetScore

var card_data: Dictionary = {}

func setup(data: Dictionary):
	card_data = data

	# --- Рамка ---
	var tier = data.get("frame_tier", "bronze")
	var frame_path = FRAMES_PATH + "frame_%s.png" % tier
	if ResourceLoader.exists(frame_path):
		frame_rect.texture = load(frame_path)

	# --- Разблокированное или заблокированное ---
	var is_unlocked = data.get("unlocked", false)
	
	# Устанавливаем название (всегда видно, если не секрет)
	if data.get("is_secret") and not is_unlocked:
		name_label.text = "???"
		desc_label.text = "Секретное достижение"
		quote_label.text = "\"...\""
	else:
		name_label.text = data.get("name", "Unknown")
		desc_label.text = data.get("description", "")
		quote_label.text = "\"%s\"" % data.get("quote", "История умалчивает...")

	if is_unlocked:
		setup_unlocked_view(data, tier)
	else:
		setup_locked_view(data, tier)

func setup_unlocked_view(data: Dictionary, tier: String):
	# --- Статус (Дата) ---
	# Форматируем дату из "2026-03-26T..." в "26.03.2026"
	var date_str = format_date(data.get("unlocked_at", ""))
	setup_status_style(false, tier, date_str)

	# --- Фон уровня ---
	load_background(tier)

	# --- Иконка достижения ---
	load_icon(data.get("icon", ""))

	# --- Счет (Скрываем, так как достижение получено) ---
	current_score_label.visible = false
	target_score_label.visible = false
	
	# Визуальный режим
	modulate = Color(1, 1, 1)

func setup_locked_view(data: Dictionary, tier: String):
	# --- Статус (В процессе) ---
	setup_status_style(true, "", "В процессе")

	# --- Фон уровня ---
	load_background(tier)

	# --- Заглушка для иконки ---
	load_placeholder(data.get("category", "general"))

	# --- Счет (Показываем прогресс) ---
	var progress = data.get("progress", 0)
	var target = data.get("target", 1)
	
	current_score_label.visible = true
	target_score_label.visible = true
	
	current_score_label.text = format_number_short(progress)
	target_score_label.text = format_number_short(target)

	# Визуальный режим (Затемнение)
	modulate = Color(0.6, 0.6, 0.6)

# --- Статус (Бывший Header) ---
func setup_status_style(is_progress: bool, tier: String, text: String):
	# Настройка фона и цвета текста для узла OpenedAt
	var style = StyleBoxFlat.new()
	if is_progress:
		style.bg_color = Color(0, 0, 0)
		status_label.add_theme_color_override("font_color", Color.WHITE)
	else:
		style.bg_color = Color(0, 0, 0, 0.3)
		status_label.add_theme_color_override("font_color", DATE_COLORS.get(tier, Color.WHITE))
	
	status_label.add_theme_stylebox_override("panel", style)
	status_label.text = text

# --- Фон уровня ---
func load_background(tier: String):
	var file = TIER_BG_FILES.get(tier, "wood.png")
	var path = BACKGROUNDS_PATH + file
	if ResourceLoader.exists(path):
		bg_texture.texture = load(path)

# --- Иконка ---
func load_icon(filename: String):
	if filename == "": return
	var path = ICONS_PATH + filename + ".png"
	if ResourceLoader.exists(path):
		icon_rect.texture = load(path)
	elif ResourceLoader.exists(ICONS_PATH + filename):
		icon_rect.texture = load(ICONS_PATH + filename)

# --- Заглушка ---
func load_placeholder(category: String):
	var mapping = {
		"progress": "wins.png",      # был "cat_wins.png"
		"suits": "suits.png",            # был "cat_suits.png"
		"cards": "cards.png",            # был "cat_cards.png"
		"exploration": "exploration.png", # был "cat_explore.png"
		"resilience": "resilience.png",        # был "cat_loss.png" (или resilience.png)
		"perfection": "perfect.png",  # был "cat_perfect.png"
		"speed": "speed.png",            # был "cat_speed.png"
		"streak": "streak.png"           # был "cat_streak.png"
	}
	var file = mapping.get(category, "cat_default.png")
	var path = PLACEHOLDERS_PATH + file
	if ResourceLoader.exists(path):
		icon_rect.texture = load(path)

# --- Форматирование даты ---
func format_date(iso_date: String) -> String:
	if iso_date == "" or iso_date == null: return ""
	# Превращает "2026-03-26T23:03:05..." в словарь
	var dict = Time.get_datetime_dict_from_datetime_string(iso_date, false)
	# Возвращает "26.03.2026"
	return "%02d.%02d.%04d" % [dict.day, dict.month, dict.year]

# --- Сокращение больших чисел ---
func format_number_short(value: int) -> String:
	if value >= 1000000:
		return str(round(value / 100000.0) / 10.0) + "M"
	elif value >= 1000:
		return str(round(value / 100.0) / 10.0) + "K"
	else:
		return str(value)
