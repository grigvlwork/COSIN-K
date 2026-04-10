# gui/godot-client/scenes/achievements_album.gd
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
const CARD_WIDTH: float = 320.0
const CARD_HEIGHT: float = 460.0
const CARD_GAP: float = 60.0
#const SIDE_SCALE: float = 0.6
const SIDE_SCALE: float = 0.7    # Масштаб боковых карт
const SIDE_ALPHA: float = 0.6     # Прозрачность боковых карт
const CARD_VERTICAL_OFFSET: float = -120.0 

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
	# 1. Настраиваем поведение контейнера ДО расчётов
	cards_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cards_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cards_container.custom_minimum_size = Vector2(1100, CARD_HEIGHT + 20)
	cards_container.clip_contents = false
	if cards_container.get_parent() is Control:
		cards_container.get_parent().clip_contents = false
	
	# 2. Ждём, пока Godot 4 применит layout (иногда нужно 2 кадра)
	await get_tree().process_frame
	await get_tree().process_frame
	cards_container.set_anchors_preset(Control.PRESET_FULL_RECT)
	cards_container.size = get_viewport().get_visible_rect().size
	# 3. Рассчитываем позиции
	_calculate_positions()
	
	# 4. Инициализация
	btn_menu.pressed.connect(_on_menu_pressed)
	http_request.request_completed.connect(_on_http_request_request_completed)
	
	request_album_data()

func _calculate_positions():
	# Получаем ширину с защитой от нулевого размера
	var w = cards_container.size.x
	if w < 100:
		# Фоллбэк: берём ширину окна, если контейнер ещё не растянулся
		w = get_viewport().get_visible_rect().size.x - 100
	print("REAL WIDTH:", cards_container.size.x)
		
	var center = w / 2.0

	pos_center_x = center - CARD_WIDTH / 2.0

	var side_width = CARD_WIDTH * SIDE_SCALE

	# 🔥 ДОБАВЛЯЕМ РЕАЛЬНЫЙ ОТСТУП
	var safe_gap = CARD_GAP + 40  # <-- ключевая строка

	pos_left_x = pos_center_x - side_width - safe_gap
	pos_right_x = pos_center_x + CARD_WIDTH + safe_gap
	cards_container.position.y = 50
	
	print("📏 Container: %.0fpx | L:%.0f C:%.0f R:%.0f" % [w, pos_left_x, pos_center_x, pos_right_x])

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
	# Очистка
	for child in cards_container.get_children():
		child.queue_free()
	card_nodes.clear()
	
	for i in range(3):
		var card = CARD_SCENE.instantiate()
		cards_container.add_child(card)
		card_nodes.append(card)
		
		# 🔥 ОТКЛЮЧАЕМ АВТО-ЛЕЙАУТ КОНТЕЙНЕРА (3 = LAYOUT_MODE_POSITION)
		card.layout_mode = 3
		
		# 🎯 Масштабирование от центра карты, а не от левого верхнего угла
		#card.pivot_offset = Vector2(CARD_WIDTH / 2.0, CARD_HEIGHT / 2.0)
		
		if all_achievements.is_empty():
			card.visible = false
			continue
			
		card.visible = true
	
	update_cards_data(true)

func update_cards_data(instant: bool = false):
	if all_achievements.size() == 0:
		for c in card_nodes:
			c.visible = false
		return

	var N = all_achievements.size()
	var left_idx = current_index - 1
	var center_idx = current_index
	var right_idx = current_index + 1

	# Левая карточка
	if left_idx >= 0:
		card_nodes[0].visible = true
		setup_card_view(card_nodes[0], all_achievements[left_idx])
		apply_card_transform(card_nodes[0], 0, 0.0 if instant else 0.25)
	else:
		card_nodes[0].visible = false
		card_nodes[0].position = Vector2(pos_left_x - CARD_WIDTH * 2, _get_card_y())

	# Центральная всегда есть
	card_nodes[1].visible = true
	setup_card_view(card_nodes[1], all_achievements[center_idx])
	apply_card_transform(card_nodes[1], 1, 0.0 if instant else 0.25)

	# Правая карточка
	if right_idx < N:
		card_nodes[2].visible = true
		setup_card_view(card_nodes[2], all_achievements[right_idx])
		apply_card_transform(card_nodes[2], 2, 0.0 if instant else 0.25)
	else:
		card_nodes[2].visible = false
		card_nodes[2].position = Vector2(pos_right_x + CARD_WIDTH * 2, _get_card_y())

func move_carousel(direction: int):
	if is_animating or all_achievements.size() < 2:
		return
	
	var N = all_achievements.size()
	var new_index = current_index + direction
	
	# Проверяем границы — если у края, не листаем
	if new_index < 0 or new_index >= N:
		return
	
	is_animating = true
	current_index = new_index

	# Считаем индексы для новых позиций
	var left_idx = current_index - 1
	var center_idx = current_index
	var right_idx = current_index + 1
	
	# Проверяем существование левой и правой карточек
	var has_left = left_idx >= 0
	var has_right = right_idx < N

	if direction > 0:  # → вправо (смотрим следующую карточку)
		var old_left = card_nodes[0]
		
		# Анимируем уходящую влево (исчезает)
		var out_tween = create_tween()
		out_tween.set_parallel(true)
		out_tween.tween_property(old_left, "position:x", pos_left_x - CARD_WIDTH * 1.5, 0.25)
		out_tween.tween_property(old_left, "modulate:a", 0.0, 0.25)
		
		# Сдвигаем оставшиеся: центр→лево, право→центр
		apply_card_transform(card_nodes[1], 0, 0.3)  # был центр, станет левым
		apply_card_transform(card_nodes[2], 1, 0.3)  # был правым, станет центром
		
		await get_tree().create_timer(0.3).timeout
		
		# Переставляем массив
		card_nodes.pop_front()
		card_nodes.append(old_left)
		
		# Готовим новую правую карточку (если есть)
		if has_right:
			update_single_card(old_left, right_idx)
			# Появляется справа
			old_left.position = Vector2(pos_right_x + CARD_WIDTH * 1.5, _get_card_y())
			old_left.modulate = Color(1, 1, 1, 0)
			apply_card_transform(old_left, 2, 0.25)  # 2 = Right
		else:
			# Нет карточки справа — просто прячем
			old_left.visible = false
			old_left.position = Vector2(pos_right_x + CARD_WIDTH * 2, _get_card_y())  # за экран
		
	else:  # ← влево
		var old_right = card_nodes[2]
		
		# Анимируем уходящую вправо (исчезает)
		var out_tween = create_tween()
		out_tween.set_parallel(true)
		out_tween.tween_property(old_right, "position:x", pos_right_x + CARD_WIDTH * 1.5, 0.25)
		out_tween.tween_property(old_right, "modulate:a", 0.0, 0.25)
		
		# Сдвигаем оставшиеся: лево→центр, центр→право
		apply_card_transform(card_nodes[0], 1, 0.3)  # был левым, станет центром
		apply_card_transform(card_nodes[1], 2, 0.3)  # был центром, станет правым
		
		await get_tree().create_timer(0.3).timeout
		
		# Переставляем массив
		card_nodes.pop_back()
		card_nodes.push_front(old_right)
		
		# Готовим новую левую карточку (если есть)
		if has_left:
			update_single_card(old_right, left_idx)
			# Появляется слева
			old_right.position = Vector2(pos_left_x - CARD_WIDTH * 1.5, _get_card_y())
			old_right.modulate = Color(1, 1, 1, 0)
			apply_card_transform(old_right, 0, 0.25)  # 0 = Left
		else:
			# Нет карточки слева — просто прячем
			old_right.visible = false
			old_right.position = Vector2(pos_left_x - CARD_WIDTH * 2, _get_card_y())  # за экран
	
	is_animating = false

# Вспомогательная функция для Y-позиции
func _get_card_y() -> float:
	var y_center = cards_container.size.y / 2
	return y_center - CARD_HEIGHT / 2.0 + CARD_VERTICAL_OFFSET

# Исправленный apply_card_transform с z_index и Y
func apply_card_transform(card: Control, pos_type: int, duration: float):
	var target_x: float
	var target_scale: float
	var target_z: int
	var target_modulate: Color = Color(1, 1, 1, 1)
	
	match pos_type:
		0: # Left
			target_x = pos_left_x
			target_scale = SIDE_SCALE
			target_z = 1
			target_modulate = Color(1, 1, 1, SIDE_ALPHA)
		1: # Center
			target_x = pos_center_x
			target_scale = 1.0
			target_z = 2
		2: # Right
			target_x = pos_right_x
			target_scale = SIDE_SCALE
			target_z = 1
			target_modulate = Color(1, 1, 1, SIDE_ALPHA)
	
	var target_y = _get_card_y()
	var target_pos = Vector2(target_x, target_y)
	
	card.z_index = target_z  # Всегда обновляем z_index
	
	if duration > 0:
		var tween = create_tween().set_parallel(true)
		tween.tween_property(card, "position", target_pos, duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_QUART)
		tween.tween_property(card, "scale", Vector2(target_scale, target_scale), duration).set_ease(Tween.EASE_OUT)
		tween.tween_property(card, "modulate", target_modulate, duration)
	else:
		card.position = target_pos
		card.scale = Vector2(target_scale, target_scale)
		card.modulate = target_modulate

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
