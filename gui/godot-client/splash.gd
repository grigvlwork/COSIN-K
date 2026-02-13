extends Node2D

@onready var timer = $SplashTimer

func _ready():
	# Запускаем таймер
	timer.start()

func _on_timer_timeout():
	# Переходим в меню
	get_tree().change_scene_to_file("res://menu.tscn")

func _input(event):
	# Нажатие любой клавиши или мыши - пропускаем заставку
	if event.is_pressed():
		_on_timer_timeout()
