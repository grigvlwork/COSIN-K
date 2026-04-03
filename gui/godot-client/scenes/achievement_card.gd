# \gui\godot-client\scenes\achievement_card.gd
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
@onready var frame_rect: TextureRect = $FrameRect
@onready var bg_texture: TextureRect = $IconPanel/BgTexture
@onready var icon_rect: TextureRect = $IconPanel/IconRect
@onready var header_label: Label = $HeaderLabel
@onready var name_label: Label = $CategoryLabel
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
	if is_unlocked:
		setup_unlocked_view(data, tier)
	else:
		setup_locked_view(data, tier)

	# --- Текстовые данные ---
	if data.get("is_secret") and not is_unlocked:
		name_label.text = "???"
		desc_label.text = "Секретное достижение"
		quote_label.text = "\"...\""
	else:
		name_label.text = data.get("name", "Unknown")
		desc_label.text = data.get("description", "")
		quote_label.text = "\"%s\"" % data.get("quote", "История умалчивает...")

func setup_unlocked_view(data: Dictionary, tier: String):
	# --- Header ---
	setup_header_style(false, tier, data.get("unlocked_at", ""))

	# --- Фон уровня ---
	load_background(tier)

	# --- Иконка достижения ---
	load_icon(data.get("icon", ""))

	# --- Текущий и целевой счет ---
	current_score_label.text = format_number_short(data.get("current", 0))
	target_score_label.text = format_number_short(data.get("target", 0))

	modulate = Color(1, 1, 1)

func setup_locked_view(data: Dictionary, tier: String):
	# --- Header (Прогресс) ---
	var progress = data.get("progress", 0)
	var target = data.get("target", 1)
	setup_header_style(true, "", "%d / %d" % [progress, target])

	# --- Фон уровня ---
	load_background(tier)

	# --- Заглушка для иконки ---
	load_placeholder(data.get("category", "general"))

	# --- Текущий и целевой счет ---
	current_score_label.text = format_number_short(progress)
	target_score_label.text = format_number_short(target)

	modulate = Color(0.6, 0.6, 0.6)

# --- Header ---
func setup_header_style(is_progress: bool, tier: String, text: String):
	var style = StyleBoxFlat.new()
	if is_progress:
		style.bg_color = Color(0, 0, 0)
		header_label.add_theme_color_override("font_color", Color.WHITE)
	else:
		style.bg_color = Color(0, 0, 0, 0.3)
		header_label.add_theme_color_override("font_color", DATE_COLORS.get(tier, Color.WHITE))
	header_label.add_theme_stylebox_override("panel", style)
	header_label.text = text

# --- Фон уровня ---
func load_background(tier: String):
	var file = TIER_BG_FILES.get(tier, "wood.png")
	var path = BACKGROUNDS_PATH + file
	if ResourceLoader.exists(path):
		bg_texture.texture = load(path)
	else:
		printerr("Background texture not found: ", path)

# --- Иконка ---
func load_icon(filename: String):
	if filename == "":
		return
	var path = ICONS_PATH + filename + ".png"
	if ResourceLoader.exists(path):
		icon_rect.texture = load(path)
	elif ResourceLoader.exists(ICONS_PATH + filename):
		icon_rect.texture = load(ICONS_PATH + filename)

# --- Заглушка ---
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

# --- Сокращение больших чисел ---
func format_number_short(value: int) -> String:
	if value >= 1000000:
		return str(round(value / 100000.0) / 10.0) + "M"
	elif value >= 1000:
		return str(round(value / 100.0) / 10.0) + "K"
	else:
		return str(value)
