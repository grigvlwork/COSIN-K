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
const CARD_GAP: float = 80.0
const SIDE_SCALE: float = 0.6
# sconst SIDE_SCALE: float = 0.75    # Масштаб боковых карт
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
	var indices = []

	for offset in [-1, 0, 1]:
		var idx = (current_index + offset + N) % N  # wrap-around
		indices.append(idx)

	for i in range(3):
		var card = card_nodes[i]
		var data_index = indices[i]

		if data_index >= 0 and data_index < N:
			card.visible = true
			setup_card_view(card, all_achievements[data_index])
		else:
			card.visible = false

		# позиция и масштаб
		if instant:
			apply_card_transform(card, i, 0.0)
		else:
			apply_card_transform(card, i, 0.25)

func apply_card_transform(card: Control, pos_type: int, duration: float):
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
	
	# Центрируем по вертикали **по середине контейнера**:
	var y_center = cards_container.size.y / 2
	var y = y_center - CARD_HEIGHT / 2.0  # фиксируем верхнюю координату независимо от масштаба

	if duration > 0:
		var tween = create_tween().set_parallel(true)
		tween.tween_property(card, "position:x", target_x, duration).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_QUART)
		tween.tween_property(card, "scale", Vector2(target_scale, target_scale), duration).set_ease(Tween.EASE_OUT)
		tween.tween_property(card, "modulate", target_modulate, duration)
	else:
		card.position = Vector2(target_x, y)
		card.scale = Vector2(target_scale, target_scale)
		match pos_type:
			0: card.z_index = 1
			1: card.z_index = 2
			2: card.z_index = 1
# --- Анимация переключения ---

func move_carousel(direction: int):
	if is_animating: return
	
	var new_index = current_index + direction
	if new_index < 0 or new_index >= all_achievements.size(): return

	is_animating = true
	current_index = clamp(new_index, 0, all_achievements.size() - 1)

	# анимация текущих 3 карт
	for i in range(3):
		var card = card_nodes[i]
		var anim_type = i - direction 
		if anim_type >= 0 and anim_type <= 2:
			apply_card_transform(card, anim_type, 0.3)
		else:
			var out_tween = create_tween()
			var out_x = pos_left_x - CARD_WIDTH if direction > 0 else pos_right_x + CARD_WIDTH
			out_tween.tween_property(card, "position:x", out_x, 0.3)

	await get_tree().create_timer(0.3).timeout

	# переставляем узлы
	if direction > 0:
		# идём вправо → левая карта уходит → переносим её за правый край
		var left_card = card_nodes.pop_front()
		card_nodes.append(left_card)
		var new_idx = (current_index + 1) % all_achievements.size()
		update_single_card(left_card, new_idx)
		left_card.position.x = pos_right_x + CARD_WIDTH  # появляется справа
	else:
		# идём влево → правая карта уходит → переносим её за левый край
		var right_card = card_nodes.pop_back()
		card_nodes.push_front(right_card)
		var new_idx = (current_index - 1 + all_achievements.size()) % all_achievements.size()
		update_single_card(right_card, new_idx)
		right_card.position.x = pos_left_x - CARD_WIDTH  # появляется слева

	# финальная анимация всех карт
	for i in range(3):
		apply_card_transform(card_nodes[i], i, 0.25)

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
