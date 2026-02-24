extends Node

# Настройки
@export var start_node: NodePath = NodePath(".")
@export var print_on_ready: bool = true
@export var max_depth: int = 10

func _ready():
	if print_on_ready:
		print_scene_tree(get_node_or_null(start_node) if start_node else self)

# Рекурсивная функция для вывода дерева
func print_scene_tree(node: Node, indent: int = 0, current_depth: int = 0):
	if node == null or current_depth > max_depth:
		return

	# ✅ ПРАВИЛЬНОЕ СОЗДАНИЕ ОТСТУПА (через цикл)
	var prefix = ""
	for i in range(indent):
		prefix += "    "
	
	# Получаем тип и имя
	var type_name = node.get_class()
	var node_name = node.name
	
	# Добавляем информацию о типе
	var extra_info = ""
	if node is Control:
		extra_info = " (Control)"
	elif node is Area2D:
		extra_info = " (Area2D)"
	elif node is Sprite2D:
		extra_info = " (Sprite2D)"
	
	# Вывод строки
	print(prefix + "├─ " + node_name + " [" + type_name + "]" + extra_info)
	
	# Рекурсивно обходим детей
	for child in node.get_children():
		print_scene_tree(child, indent + 1, current_depth + 1)

# Функция для поиска узла по имени
func find_node_by_name(target_name: String, node: Node = null) -> Node:
	if node == null:
		node = self
	
	if node.name == target_name:
		return node
	
	for child in node.get_children():
		var result = find_node_by_name(target_name, child)
		if result:
			return result
	
	return null
