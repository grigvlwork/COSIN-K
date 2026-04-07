extends Control

# --- Константы и Пути ---
const CARD_SCENE = preload("res://scenes/AchievementCard.tscn")
const ALBUM_BG_PATH = "res://assets/achievements/album/"
# --- Словарь перевода категорий ---
const CATEGORY_TRANSLATIONS = {
	"progress": "Прогресс",
	"cards": "Карты",
	"exploration": "Исследование",
	"suits": "Масти",
	"resilience": "Стойкость",
	"perfection": "Совершенство",
	"speed": "Скорость",
	"streak": "Везение"
}

# Настройки Карусели (под твои размеры)
const CARD_WIDTH: float = 400.0   # Ширина твоей карты
const CARD_HEIGHT: float = 576.0  # Высота твоей карты
const CARD_GAP: float = 40.0      # Расстояние между картами
const SIDE_SCALE: float = 0.75    # Масштаб боковых карт
const SIDE_ALPHA: float = 0.7     # Прозрачность боковых карт

const SKIN_FILES = {
	"classic": "beige.png",
	"wood": "old_style.png",
	"leather": "old_style.png",
	"velvet": "royal.png",
	"cyberpunk": "cyberpunk.png",
	"cosmos": "cosmos.png"
}

# --- Узлы ---
@onready var background: TextureRect = $Background
@onready var cards_container: Control = $MarginContainer/VBoxContainer/CardsContainer
@onready var btn_menu: Button = $MarginContainer/VBoxContainer/Footer/BtnMenu
@onready var http_request: HTTPRequest = $HTTPRequest
@onready var gold_particles: GPUParticles2D = $GoldParticles

# --- Переменные ---
var all_achievements: Array = []
var current_index: int = 0
var card_nodes: Array = [] # Массив из 3 узлов: [Left, Center, Right]
var is_animating: bool = false

# Смещения для позиций карусели
var pos_left_x: float
var pos_center_x: float
var pos_right_x: float

signal close_requested

func _ready():
	# ВАЖНО: Ждем один кадр, чтобы Godot рассчитал реальные размеры VBoxContainer и CardsContainer.
	# Без этого cards_container.size.x будет равен 0, и карты уедут за левый край.
	await get_tree().process_frame
	
	# Расчет координат (теперь size.x имеет корректное значение)
	var center = cards_container.size.x / 2
	pos_center_x = center - (CARD_WIDTH / 2)
	
	# Левая позиция (учитывая масштаб боковой карты)
	pos_left_x = pos_center_x - (CARD_WIDTH * SIDE_SCALE) - CARD_GAP + (CARD_WIDTH * (1.0 - SIDE_SCALE) / 2)
	
	# Правая позиция
	pos_right_x = pos_center_x + CARD_WIDTH + CARD_GAP - (CARD_WIDTH * (1.0 - SIDE_SCALE) / 2)

	# Связи
	btn_menu.pressed.connect(_on_menu_pressed)
	http_request.request_completed.connect(_on_http_request_request_completed)
	
	# Запрос данных
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
		
		# --- Логика открытия на новой карте ---
		var start_index = 0
		if Global.has_new_achievement:
			var target_id = Global.last_achievement_id
			# Ищем индекс
			for i in range(all_achievements.size()):
				if all_achievements[i].get("id") == target_id:
					start_index = i
					break
			
			# Сбрасываем флаг в Global
			Global.has_new_achievement = false
			Global.last_achievement_id = ""
			
			# Запускаем эффект
			start_celebration()
		
		current_index = start_index
		setup_carousel()

# --- Настройка карусели ---

func setup_carousel():
	# Очистка старого
	for child in cards_container.get_children():
		child.queue_free()
	card_nodes.clear()
	
	# Создаем 3 карты
	for i in range(3):
		var card = CARD_SCENE.instantiate()
		cards_container.add_child(card)
		card_nodes.append(card)
		
		# Скрываем, если достижений нет
		if all_achievements.is_empty():
			card.visible = false
			continue
			
		card.visible = true
	
	update_cards_data(true)

func update_cards_data(instant: bool = false):
	# Индексы данных для 3 карт
	var idx_left = current_index - 1
	var idx_center = current_index
	var idx_right = current_index + 1
	
	# Обновляем данные и позиции
	for i in range(3):
		var card = card_nodes[i]
		var data_index: int
		
		if i == 0: data_index = idx_left
		elif i == 1: data_index = idx_center
		else: data_index = idx_right
		
		# Если индекс валиден - показываем, иначе скрываем
		if data_index >= 0 and data_index < all_achievements.size():
			card.visible = true
			setup_card_view(card, all_achievements[data_index])
		else:
			card.visible = false
		
		# Применяем позицию и масштаб
		if instant:
			apply_card_transform(card, i, 0.0)
		else:
			# Анимация не нужна при обновлении данных, только при скролле
			apply_card_transform(card, i, 0.0)

func apply_card_transform(card: Control, pos_type: int, duration: float):
	# pos_type: 0=Left, 1=Center, 2=Right
	var target_x: float
	var target_scale: float
	var target_modulate: Color = Color(1, 1, 1, 1)
	
	match pos_type:
		0: # Left
			target_x = pos_left_x
			target_scale = SIDE_SCALE
			target_modulate = Color(1, 1, 1, SIDE_ALPHA)
		1: # Center
			target_x = pos_center_x
			target_scale = 1.0
		2: # Right
			target_x = pos_right_x
			target_scale = SIDE_SCALE
			target_modulate = Color(1, 1, 1, SIDE_ALPHA)
	
	if duration > 0:
		var tween = create_tween().set_parallel(true)
		tween.tween_property(card, "position:x", target_x, duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_QUART)
		tween.tween_property(card, "scale", Vector2(target_scale, target_scale), duration).set_ease(Tween.EASE_OUT)
		tween.tween_property(card, "modulate", target_modulate, duration)
	else:
		card.position.x = target_x
		card.position.y = (cards_container.size.y - CARD_HEIGHT) / 2 # Центрирование по вертикали
		card.scale = Vector2(target_scale, target_scale)
		card.modulate = target_modulate

# --- Анимация переключения ---

func move_carousel(direction: int):
	# direction: -1 (влево), 1 (вправо)
	if is_animating: return
	
	var new_index = current_index + direction
	
	# Проверка границ
	if new_index < 0 or new_index >= all_achievements.size():
		return # Можно добавить "резиновый" эффект возврата
		
	is_animating = true
	current_index = new_index
	
	# Анимация перемещения узлов
	# Логика "Конвейера"
	
	# 1. Сдвигаем текущие 3 карты
	for i in range(3):
		var card = card_nodes[i]
		# Если двигаемся вправо (->), то Left улетает, Center становится Left, Right становится Center
		# Индексы анимации: 0->-1 (out), 1->0 (left), 2->1 (center)
		var anim_type = i - direction 
		if anim_type >= 0 and anim_type <= 2:
			apply_card_transform(card, anim_type, 0.3)
		else:
			# Улетает за край
			var out_tween = create_tween()
			var out_x = pos_left_x - CARD_WIDTH if direction > 0 else pos_right_x + CARD_WIDTH
			out_tween.tween_property(card, "position:x", out_x, 0.3)
	
	# 2. Ждем конца анимации, чтобы обновить данные и переставить узлы
	await get_tree().create_timer(0.3).timeout
	
	# Перестановка узлов в массиве для реюзинга (для бесконечного скролла)
	# Если шли вправо: 0-й узел (левый) стал не нужен, его делаем правым
	if direction > 0:
		var left_card = card_nodes.pop_front()
		card_nodes.append(left_card)
	# Если шли влево: 2-й узел (правый) стал не нужен, его делаем левым
	else:
		var right_card = card_nodes.pop_back()
		card_nodes.push_front(right_card)
		
	# Обновляем данные у "новых" карт (у того, который только что телепортировался)
	# Нам нужно обновить только одну карту, которая появилась с края
	if direction > 0:
		# Обновляем последнюю карту (Right)
		update_single_card(card_nodes[2], current_index + 1)
		card_nodes[2].position.x = pos_right_x + CARD_WIDTH # Телепортируем за правый край перед появлением (если нужно)
	else:
		# Обновляем первую карту (Left)
		update_single_card(card_nodes[0], current_index - 1)
		card_nodes[0].position.x = pos_left_x - CARD_WIDTH # Телепортируем за левый край
	
	is_animating = false

func update_single_card(card: Control, data_idx: int):
	if data_idx >= 0 and data_idx < all_achievements.size():
		setup_card_view(card, all_achievements[data_idx])
		card.visible = true
		# Сброс масштаба для следующего появления
		card.scale = Vector2(SIDE_SCALE, SIDE_SCALE)
		card.modulate = Color(1, 1, 1, SIDE_ALPHA)
	else:
		card.visible = false

# --- Настройка контента карты ---

func setup_card_view(card, data: Dictionary):
	card.setup(data)
	if card.has_node("CurrentScore") and card.has_node("TargetScore"):
		var p = data.get("progress", 0)
		var t = data.get("target", 1)
		card.get_node("CurrentScore").text = format_big_number(p)
		card.get_node("TargetScore").text = format_big_number(t)

# --- Эффекты ---

func start_celebration():
	# Получаем глобальные координаты области карт, чтобы поставить эмиттер четко над ней
	var container_rect = cards_container.get_global_rect()
	
	# Ставим эмиттер по центру ширине, и в самый верх по высоте
	gold_particles.global_position = Vector2(
		container_rect.position.x + (container_rect.size.x / 2),
		container_rect.position.y
	)
	
	gold_particles.emitting = true

# --- Обработка ввода ---

func _input(event):
	# Перехват колеса мыши
	if event is InputEventMouseButton:
		if event.is_pressed():
			# Проверяем, что мышь над контейнером карт
			var rect = cards_container.get_global_rect()
			if rect.has_point(event.global_position):
				if event.button_index == MOUSE_BUTTON_WHEEL_UP:
					move_carousel(1) # Вправо
				elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
					move_carousel(-1) # Влево

func _on_menu_pressed():
	emit_signal("close_requested")
	get_tree().change_scene_to_file("res://scenes/menu.tscn")

# --- Вспомогательные ---

func apply_skin(skin_id: String):
	var file_name = SKIN_FILES.get(skin_id, "beige.png")
	var path = ALBUM_BG_PATH + file_name
	if ResourceLoader.exists(path):
		background.texture = load(path)

func format_big_number(value: int) -> String:
	if value >= 1000000:
		return "%dМ" % int(value / 1000000)
	elif value >= 1000:
		return "%dК" % int(value / 1000)
	return str(value)
