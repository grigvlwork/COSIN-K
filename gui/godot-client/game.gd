extends Node2D

var http = HTTPRequest.new()
var game_state = null

func _ready():
	add_child(http)
	http.request_completed.connect(_on_request_completed)
	
	# СОЗДАЕМ НОВУЮ ИГРУ!
	create_new_game()

func create_new_game():
	print("🎮 Создаем новую игру: ", Global.current_variant)
	
	var body = '{"variant":"' + Global.current_variant + '"}'
	var headers = ["Content-Type: application/json"]
	
	http.request(
		Global.server_url + "/new",
		headers,
		HTTPClient.METHOD_POST,
		body
	)

func get_game_state():
	print("📥 Запрашиваем состояние игры...")
	http.request(Global.server_url + "/state")

func _on_request_completed(result, response_code, headers, body):
	var response_text = body.get_string_from_utf8()
	
	var json = JSON.new()
	var error = json.parse(response_text)
	
	if error == OK:
		var data = json.data
		
		if data.has("success"):
			if data.has("variant"):  # /new
				print("🎉 ИГРА СОЗДАНА!")
				print("📊 Счет: ", data.get("score", 0))
				print("🎯 Ходов: ", data.get("moves", 0))
				get_game_state()
			
			elif data.has("state"):  # /state с картами!
				print("✅ ПОЛУЧЕНЫ КАРТЫ!")
				game_state = data["state"]
				
				# ВЫВОДИМ ПЕРВУЮ КАРТУ ДЛЯ ТЕСТА
				var stock = game_state["stock"]
				if stock["cards"].size() > 0:
					var first_card = stock["cards"][0]
					print("🃏 Первая карта в колоде: ", first_card)
				
				# СЧИТАЕМ ОТКРЫТЫЕ КАРТЫ В СТОЛБЦАХ
				for i in range(7):
					var pile_name = "tableau_" + str(i)
					if game_state["piles"].has(pile_name):
						var pile = game_state["piles"][pile_name]
						var face_up_count = 0
						for card in pile["cards"]:
							if card["face_up"]:
								face_up_count += 1
						print("📌 Столбец ", i, ": ", pile["cards"].size(), " карт, ", face_up_count, " открыто")
	else:
		print("❌ Ошибка парсинга JSON")
