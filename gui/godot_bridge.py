"""
Godot Bridge — HTTP мост между Godot и движком пасьянса.
Godot выбирает игру, сервер подстраивается.

🔢 СТАТИСТИКА: Теперь с поддержкой идентификации игроков и сбора статистики!
"""

import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os
from typing import Optional, Dict, Any
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import SolitaireEngine
from model.rules.factory import GameFactory
from stats.api import StatsAPI


class GameStateEncoder(json.JSONEncoder):
    """Сериализация GameState в JSON для отправки в Godot."""

    def default(self, obj):
        if hasattr(obj, '__dict__'):
            # GameState
            if hasattr(obj, 'piles') and hasattr(obj, 'stock') and hasattr(obj, 'waste'):
                result = {
                    'piles': {},
                    'score': obj.score,
                    'moves_count': obj.moves_count,
                    'time_elapsed': getattr(obj, 'time_elapsed', 0)
                }

                for name, pile in obj.piles.items():
                    result['piles'][name] = self.default(pile)

                result['stock'] = self.default(obj.stock)
                result['waste'] = self.default(obj.waste)

                return result

            # Pile
            elif hasattr(obj, 'name') and isinstance(obj, list):
                return {
                    'name': obj.name,
                    'cards': [self.default(card) for card in obj]
                }

            # Card
            elif hasattr(obj, 'suit') and hasattr(obj, 'rank') and hasattr(obj, 'face_up'):
                return {
                    'suit': obj.suit.name,
                    'suit_symbol': obj.suit.value,
                    'rank': obj.rank.value,
                    'rank_name': obj.rank.name,
                    'face_up': obj.face_up,
                    'color': obj.color
                }

            return {key: value for key, value in obj.__dict__.items()
                   if not key.startswith('_')}

        return super().default(obj)


class GodotBridgeHandler(BaseHTTPRequestHandler):
    """
    Обработчик HTTP запросов от Godot.

    🔥 Godot сам выбирает игру!
    Сервер не имеет предустановленной игры.

    📊 Статистика:
        - /player/identity - получение/создание UUID игрока
        - /game/end - завершение игры и запись статистики
    """

    # Словарь игр для каждого подключения
    # Ключ: ID сессии (IP), Значение: движок
    games = {}

    # Словарь для хранения game_id (ID в БД) для каждой сессии
    game_ids = {}

    # API статистики (инициализируется при запуске сервера)
    stats_api = None

    def _get_session_id(self):
        """Получить ID сессии (IP адрес клиента)."""
        return self.client_address[0]

    def _get_engine(self, session_id):
        """Получить движок для сессии."""
        return self.games.get(session_id)

    def _get_game_id(self, session_id):
        """Получить ID игры в БД для сессии."""
        return self.game_ids.get(session_id)

    def _create_engine(self, session_id, variant):
        """Создать новый движок для сессии."""
        try:
            # Определяем тип игры для статистики
            game_type = "klondike"
            game_variant = "standard"

            if variant == "klondike-3":
                variant = "klondike"
                game_variant = "draw-three"

            # Создаём правила через фабрику
            rules = GameFactory.create(variant)
            print(f"📦 [{session_id}] Создана игра: {variant}")

            engine = SolitaireEngine(rules)
            engine.new_game()

            # Сохраняем движок
            self.games[session_id] = engine

            # Сохраняем вариант для статистики
            engine._game_variant = game_variant
            engine._game_type = game_type

            return engine

        except Exception as e:
            print(f"❌ [{session_id}] Ошибка создания игры {variant}: {e}")
            return None

    def _get_suits_completed(self, state) -> list:
        """
        Определить, какие масти уже собраны.
        Проверяет все 4 базы, если в базе 13 карт - масть собрана.
        """
        suits_completed = []
        suit_names = ['HEARTS', 'DIAMONDS', 'CLUBS', 'SPADES']

        for i in range(4):
            pile_name = f"foundation_{i}"
            pile = state.piles.get(pile_name)
            if pile and len(pile) == 13:  # Все карты масти
                # Определяем масть по верхней карте
                if not pile.is_empty():
                    top_card = pile.top()
                    suits_completed.append(top_card.suit.name)

        return suits_completed

    def _check_perfect_game(self, engine, state) -> bool:
        """
        Проверить, была ли игра идеальной:
        - Нет отмен (undo)
        - Нет подсказок (hints)
        - Минимальное количество ходов (можно проверить по соотношению)
        """
        if not engine or not state:
            return False

        # Если были отмены или подсказки - не идеально
        if getattr(state, 'undos_used', 0) > 0 or getattr(state, 'hints_used', 0) > 0:
            return False

        # TODO: Добавить проверку на минимальное количество ходов
        # Для Клондайка минимальное количество ходов можно рассчитать

        return True

    def _send_response(self, data, status=200):
        """Отправить JSON ответ."""
        try:
            response = json.dumps(data, cls=GameStateEncoder)
            response_bytes = response.encode('utf-8')

            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            self.wfile.write(response_bytes)
            self.wfile.flush()

        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """GET запросы."""
        parsed = urlparse(self.path)
        session_id = self._get_session_id()
        query = parse_qs(parsed.query)

        # ===== ИДЕНТИФИКАЦИЯ ИГРОКА =====
        if parsed.path == '/player/identity':
            """Получить или создать identity игрока."""
            player_id = query.get('player_id', [None])[0]

            if player_id:
                # Клиент прислал свой UUID
                result = self.stats_api.connect(player_id)
                if result and result.get('success'):
                    self._send_response(result)
                else:
                    # UUID не найден - создаём нового игрока
                    result = self.stats_api.get_or_create_player(player_id)
                    self._send_response(result)
            else:
                # Клиент запрашивает новый UUID
                result = self.stats_api.init_client()
                self._send_response(result)

            return

        # ===== СПИСОК ИГР =====
        if parsed.path == '/variants':
            """Godot запрашивает список доступных игр."""
            variants = GameFactory.available_games()
            self._send_response({
                'success': True,
                'variants': variants,
                'default': 'klondike'
            })
            return

        # ===== СОСТОЯНИЕ ТЕКУЩЕЙ ИГРЫ =====
        if parsed.path == '/state':
            """Получить состояние текущей игры."""
            engine = self._get_engine(session_id)
            if engine and engine.state:
                self._send_response({
                    'success': True,
                    'state': engine.state,
                    'score': engine.state.score,
                    'moves': engine.state.moves_count
                })
            else:
                self._send_response({
                    'success': False,
                    'error': 'No active game'
                }, 404)
            return

        # ===== СТАТИСТИКА ИГРОКА =====
        if parsed.path == '/player/stats':
            """Получить статистику игрока."""
            player_id = query.get('player_id', [None])[0]
            if not player_id:
                self._send_response({
                    'success': False,
                    'error': 'Missing player_id'
                }, 400)
                return

            stats = self.stats_api.get_player_stats_summary(player_id)
            self._send_response(stats)
            return

        # ===== ТАБЛИЦА ЛИДЕРОВ =====
        if parsed.path == '/leaderboard':
            """Получить таблицу лидеров."""
            criterion = query.get('by', ['games_won'])[0]
            limit = int(query.get('limit', [10])[0])

            leaders = self.stats_api.get_leaderboard(criterion, limit)
            self._send_response({
                'success': True,
                'criterion': criterion,
                'players': leaders
            })
            return

        # Неизвестный путь
        self._send_response({
            'success': False,
            'error': f'Unknown path: {parsed.path}'
        }, 404)

    def do_POST(self):
        """POST запросы: действия и создание игры."""
        parsed = urlparse(self.path)
        session_id = self._get_session_id()

        # Читаем тело запроса
        content_length = int(self.headers.get('Content-Length', 0))
        command = {}
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length)
                command = json.loads(post_data.decode('utf-8'))
            except:
                pass

        # ===== СОЗДАНИЕ НОВОЙ ИГРЫ =====
        if parsed.path == '/new':
            """Godot выбирает и запускает новую игру."""
            variant = command.get('variant', 'klondike')
            player_id = command.get('player_id')

            print(f"📥 [{session_id}] Запрос /new для {variant} (player: {player_id})")

            # Создаем новый движок
            engine = self._create_engine(session_id, variant)

            if engine:
                # Если есть player_id - регистрируем игру в статистике
                game_id = None
                if player_id and self.stats_api:
                    game_type = "klondike"
                    game_variant = "standard"
                    if hasattr(engine, '_game_variant'):
                        game_variant = engine._game_variant

                    result = self.stats_api.start_game(
                        player_id=player_id,
                        game_type=game_type,
                        variant=game_variant
                    )
                    if result.get('success'):
                        game_id = result.get('game_id')
                        self.game_ids[session_id] = game_id
                        print(f"📊 [{session_id}] Игра зарегистрирована в статистике, ID: {game_id}")

                response_data = {
                    'success': True,
                    'variant': variant,
                    'score': 0,
                    'moves': 0
                }
                if game_id:
                    response_data['game_id'] = game_id

                self._send_response(response_data)
            else:
                self._send_response({
                    'success': False,
                    'error': f'Failed to create game: {variant}'
                }, 400)

            return

        # ===== ЗАВЕРШЕНИЕ ИГРЫ =====
        if parsed.path == '/game/end':
            """Завершить игру и записать статистику."""
            player_id = command.get('player_id')
            result = command.get('result', 'abandoned')
            score = command.get('score', 0)
            moves = command.get('moves', 0)

            # Получаем движок для дополнительной статистики
            engine = self._get_engine(session_id)
            game_id = self._get_game_id(session_id)

            suits_completed = []
            was_perfect = False

            if engine and engine.state:
                suits_completed = self._get_suits_completed(engine.state)
                was_perfect = self._check_perfect_game(engine, engine.state)

            # Записываем статистику
            if game_id and self.stats_api:
                stats_result = self.stats_api.end_game(
                    game_id=game_id,
                    result=result,
                    score=score,
                    moves=moves,
                    game_type="klondike",
                    suits_completed=suits_completed,
                    was_perfect=was_perfect
                )

                # Очищаем данные сессии
                if session_id in self.games:
                    del self.games[session_id]
                if session_id in self.game_ids:
                    del self.game_ids[session_id]

                self._send_response(stats_result)
            else:
                # Если нет статистики, просто подтверждаем завершение
                self._send_response({
                    'success': True,
                    'game_completed': True,
                    'result': result
                })

            return
        # ===== СМЕНА ИМЕНИ ИГРОКА =====
        if parsed.path == '/player/rename':
            """Изменить имя игрока."""
            player_id = command.get('player_id')
            new_name = command.get('new_name')

            if not player_id or not new_name:
                self._send_response({
                    'success': False,
                    'error': 'Missing player_id or new_name'
                }, 400)
                return

            # Валидация имени
            new_name = new_name.strip()
            if len(new_name) < 1 or len(new_name) > 50:
                self._send_response({
                    'success': False,
                    'error': 'Name must be between 1 and 50 characters'
                }, 400)
                return

            result = self.stats_api.rename_player(player_id, new_name)
            self._send_response(result)
            return
        # ===== ВСЕ ОСТАЛЬНЫЕ ДЕЙСТВИЯ =====
        # Требуют существующей игры!
        engine = self._get_engine(session_id)
        game_id = self._get_game_id(session_id)

        if not engine:
            self._send_response({
                'success': False,
                'error': 'No active game. Call /new first!',
                'need_init': True
            }, 404)
            return

        # ----- ХОДЫ -----
        if parsed.path == '/move':
            from_pile = command.get('from')
            to_pile = command.get('to')
            count = command.get('count', 1)

            if not from_pile or not to_pile:
                self._send_response({
                    'success': False,
                    'error': 'Missing from or to pile'
                }, 400)
                return

            # Сохраняем состояние до хода для подсчёта очков
            from model.move import Move
            move = Move(from_pile=from_pile, to_pile=to_pile,
                       cards=[], from_index=0)  # Упрощённо

            success = engine.move(from_pile, to_pile, count)

            # Обновляем прогресс в статистике
            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(
                    game_id=game_id,
                    moves=engine.state.moves_count,
                    undos=getattr(engine.state, 'undos_used', 0)
                )

            # Получаем доступные ходы для подсказок
            available = []
            if success and hasattr(engine.rules, 'get_available_moves'):
                available = engine.rules.get_available_moves(engine.state)

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0,
                'available_moves': len(available) if success else 0,
                'game_won': engine.rules.check_win(engine.state) if success else False
            })

        # ----- ВЗЯТЬ КАРТЫ -----
        elif parsed.path == '/draw':
            success = engine.draw()

            # Обновляем прогресс
            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(
                    game_id=game_id,
                    moves=engine.state.moves_count
                )

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0
            })

        # ----- ОТМЕНА -----
        elif parsed.path == '/undo':
            success = engine.undo()

            # Обновляем счётчик отмен
            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(
                    game_id=game_id,
                    undos=getattr(engine.state, 'undos_used', 0)
                )

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0
            })

        # ----- ПОВТОР -----
        elif parsed.path == '/redo':
            success = engine.redo()
            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0
            })

        # ----- АВТО-ХОД -----
        elif parsed.path == '/auto_move':
            from_pile = command.get('from')

            if not from_pile:
                self._send_response({
                    'success': False,
                    'error': 'Missing from pile'
                }, 400)
                return

            moves = engine.rules.get_available_moves(engine.state)
            from_moves = [m for m in moves if m.from_pile == from_pile]

            if not from_moves:
                self._send_response({
                    'success': False,
                    'error': f'No moves from {from_pile}'
                })
                return

            # Приоритет: foundation > tableau
            foundation_moves = [m for m in from_moves if m.to_pile.startswith('foundation_')]
            tableau_moves = [m for m in from_moves if m.to_pile.startswith('tableau_')]

            selected_move = None
            if foundation_moves:
                selected_move = foundation_moves[0]
            elif tableau_moves:
                tableau_moves.sort(key=lambda m: int(m.to_pile.split('_')[1]), reverse=True)
                selected_move = tableau_moves[0]

            if selected_move:
                success = engine.move(
                    selected_move.from_pile,
                    selected_move.to_pile,
                    len(selected_move.cards)
                )

                # Обновляем прогресс
                if success and game_id and self.stats_api:
                    self.stats_api.update_game_progress(
                        game_id=game_id,
                        moves=engine.state.moves_count
                    )

                self._send_response({
                    'success': success,
                    'move': {
                        'from': selected_move.from_pile,
                        'to': selected_move.to_pile,
                        'count': len(selected_move.cards)
                    },
                    'state': engine.state if success else None,
                    'score': engine.state.score if success else 0,
                    'moves': engine.state.moves_count if success else 0
                })
            else:
                self._send_response({
                    'success': False,
                    'error': 'No suitable move'
                })

        # ----- ПОДСКАЗКА -----
        elif parsed.path == '/hint':
            hint = engine.rules.get_hint(engine.state)
            if hint:
                # Увеличиваем счётчик подсказок
                if game_id and self.stats_api:
                    self.stats_api.update_game_progress(
                        game_id=game_id,
                        hints=getattr(engine.state, 'hints_used', 0) + 1
                    )

                self._send_response({
                    'success': True,
                    'hint': {
                        'from': hint.from_pile,
                        'to': hint.to_pile,
                        'count': len(hint.cards)
                    }
                })
            else:
                self._send_response({
                    'success': False,
                    'error': 'No hints available'
                })

        # ----- ПРОВЕРКА ПОБЕДЫ -----
        elif parsed.path == '/check_win':
            won = engine.rules.check_win(engine.state)
            self._send_response({
                'success': True,
                'game_won': won,
                'score': engine.state.score if won else 0,
                'suits_completed': self._get_suits_completed(engine.state) if won else []
            })

        else:
            self._send_response({
                'success': False,
                'error': f'Unknown path: {parsed.path}'
            }, 404)

    def log_message(self, format, *args):
        """Минимальное логирование."""
        pass


def start_server(host='127.0.0.1', port=8080):
    """Запуск HTTP сервера с поддержкой статистики."""
    print("=" * 50)
    print("🎮 Solitaire Engine Server")
    print("=" * 50)
    print(f"📡 Сервер: http://{host}:{port}")
    print(f"🆔 Режим: Мультисессионный")
    print(f"🎲 Игры:   {', '.join(GameFactory.available_games())}")

    # Инициализируем статистику
    print("📊 Статистика: Загрузка...")
    GodotBridgeHandler.stats_api = StatsAPI(storage_path="./stats_data")
    print("✅ Статистика: Готова")

    print("=" * 50)
    print("🔥 Godot сам выбирает игру при /new")
    print("👤 Игроки идентифицируются по UUID")
    print("📈 Статистика сохраняется в БД")
    print("=" * 50)

    server = ThreadingHTTPServer((host, port), GodotBridgeHandler)

    try:
        print("✅ Сервер готов к работе!")
        print("⏳ Ожидание подключений...")
        print("=" * 50)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    start_server(args.host, args.port)