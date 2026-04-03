extends Control

# --- Константы и Пути ---
const CARD_SCENE = preload("res://scenes/AchievementCard.tscn") # путь к сцене карты
const ALBUM_BG_PATH = "res://assets/achievements/album/"

const CARDS_PER_PAGE = 10 # 2 ряда по 5 карт
const COLUMNS = 5

# --- Маппинг ID скинов (от сервера) к файлам текстур ---
const SKIN_FILES = {
	"classic": "beige.png",
	"wood": "old_style.png",
	"leather": "old_style.png",
	"velvet": "royal.png",
	"cyberpunk": "cyberpunk.png",
	"cosmos": "cosmos.png"
}

# --- Ссылки на узлы ---
@onready var background: TextureRect = $Background
@onready var grid: GridContainer = $MarginContainer/VBoxContainer/ScrollContainer/GridContainer
@onready var btn_prev: Button = $MarginContainer/VBoxContainer/Footer/BtnPrev
@onready var btn_next: Button = $MarginContainer/VBoxContainer/Footer/BtnNext
@onready var btn_menu: Button = $MarginContainer/VBoxContainer/Footer/BtnMenu
@onready var page_label: Label = $MarginContainer/VBoxContainer/Footer/PageLabel
@onready var http_request: HTTPRequest = $HTTPRequest

# --- Переменные ---
var all_achievements: Array = []
var current_page: int = 0
var total_pages: int = 0

signal close_requested

func _ready():
	btn_prev.visible = false
	btn_next.visible = false
	grid.columns = COLUMNS
	
	btn_prev.pressed.connect(_on_prev_pressed)
	btn_next.pressed.connect(_on_next_pressed)
	btn_menu.pressed.connect(_on_menu_pressed)
	http_request.request_completed.connect(_on_http_request_request_completed)
	
	request_album_data()
	

func request_album_data():
	var player_id = Global.player_id
	var url = Global.server_url + "/player/achievements/album?player_id=" + player_id
	http_request.request(url)


func _on_http_request_request_completed(result, response_code, headers, body):
	var json = JSON.new()
	var err = json.parse(body.get_string_from_utf8())
	if err != OK:
		print("JSON Parse Error")
		return
	
	var response = json.get_data()
	if response.success:
		var current_skin = response.get("current_skin", "classic")
		apply_skin(current_skin)
		
		all_achievements = response.get("achievements", [])
		current_page = 0
		calculate_pages()
		render_page()


func apply_skin(skin_id: String):
	var file_name = SKIN_FILES.get(skin_id, "beige.png")
	var path = ALBUM_BG_PATH + file_name
	
	if ResourceLoader.exists(path):
		background.texture = load(path)
	else:
		printerr("Album background not found: ", path)
		background.texture = load(ALBUM_BG_PATH + "beige.png")


func calculate_pages():
	if all_achievements.size() == 0:
		total_pages = 1
	else:
		total_pages = ceil(float(all_achievements.size()) / CARDS_PER_PAGE)


func render_page():
	# Очистка старых карточек
	for child in grid.get_children():
		child.queue_free()
	
	var start_idx = current_page * CARDS_PER_PAGE
	var end_idx = min(start_idx + CARDS_PER_PAGE, all_achievements.size())
	
	for i in range(start_idx, end_idx):
		var card_data = all_achievements[i]
		var card = CARD_SCENE.instantiate()
		grid.add_child(card)
		
		# --- Настройка карточки ---
		card.setup(card_data)
		
		# --- Категория ---
		if card.has_node("CategoryLabel"):
			var cat_label: Label = card.get_node("CategoryLabel")
			cat_label.text = card_data.get("category", "Общее")
		
		# --- Текущий и целевой прогресс ---
		if card.has_node("CurrentScore") and card.has_node("TargetScore"):
			var current_label: Label = card.get_node("CurrentScore")
			var target_label: Label = card.get_node("TargetScore")
			
			var progress = card_data.get("progress", 0)
			var target = card_data.get("target", 1)
			
			current_label.text = format_big_number(progress)
			target_label.text = format_big_number(target)
	
	# Обновление страницы
	page_label.text = "Стр. %d / %d" % [current_page + 1, total_pages]
	btn_prev.visible = current_page > 0
	btn_next.visible = (current_page + 1) < total_pages


# --- Кнопки ---
func _on_prev_pressed():
	if current_page > 0:
		current_page -= 1
		render_page()

func _on_next_pressed():
	if (current_page + 1) < total_pages:
		current_page += 1
		render_page()

func _on_menu_pressed():
	emit_signal("close_requested")


# --- Вспомогательные функции ---
func format_big_number(value: int) -> String:
	if value >= 1000000:
		return "%dМ" % int(value / 1000000)
	elif value >= 1000:
		return "%dК" % int(value / 1000)
	return str(value)
