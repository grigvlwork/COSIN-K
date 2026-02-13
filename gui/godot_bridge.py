"""
Godot Bridge — HTTP мост между Godot и движком пасьянса.
Godot выбирает игру, сервер подстраивается.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import SolitaireEngine
from model.rules.factory import GameFactory


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

            # Card - ИСПРАВЛЕНО!
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

    🔥 ВАЖНО: Godot сам выбирает игру!
    Сервер не имеет предустановленной игры.
    """

    # Словарь игр для каждого подключения
    # Ключ: ID сессии, Значение: движок
    games = {}

    def _get_session_id(self):
        """Получить или создать ID сессии."""
        # Можно использовать IP или передавать ID в запросе
        return self.client_address[0]

    def _get_engine(self, session_id):
        """Получить движок для сессии."""
        return self.games.get(session_id)

    def _create_engine(self, session_id, variant):
        """Создать новый движок для сессии."""
        try:
            # ИСПОЛЬЗУЕМ ПРАВИЛЬНЫЙ МЕТОД create()
            from model.rules.factory import GameFactory

            rules = GameFactory.create(variant)
            # print(f"📦 [{session_id}] Создана игра: {variant}")

            engine = SolitaireEngine(rules)
            engine.new_game()
            self.games[session_id] = engine
            return engine

        except Exception as e:
            # print(f"❌ [{session_id}] Ошибка создания игры {variant}: {e}")
            return None

    def _send_response(self, data, status=200):
        """Отправить JSON ответ."""
        try:
            response = json.dumps(data, cls=GameStateEncoder)
            response_bytes = response.encode('utf-8')

            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_bytes)))  # ЯВНО УКАЗЫВАЕМ ДЛИНУ!
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            self.wfile.write(response_bytes)
            self.wfile.flush()

            print(f"✅ Отправлено {len(response_bytes)} байт: {response[:100]}...")

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

        if parsed.path == '/variants':
            # 🔥 Godot запрашивает список доступных игр
            variants = GameFactory.available_games()
            self._send_response({
                'success': True,
                'variants': variants,
                'default': 'klondike'
            })



        elif parsed.path == '/state':
            # Получить состояние текущей игры
            engine = self._get_engine(session_id)
            if engine and engine.state:
                # 👇 ТЕПЕРЬ ОТПРАВЛЯЕМ РЕАЛЬНОЕ СОСТОЯНИЕ!
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

            print(f"📥 Получен запрос /new для {variant}")  # ОТЛАДКА

            # Создаем новый движок для этой сессии
            engine = self._create_engine(session_id, variant)

            if engine:
                response_data = {
                    'success': True,
                    'variant': variant,
                    'score': 0,
                    'moves': 0
                }
                print(f"📤 Отправка ответа: {response_data}")  # ОТЛАДКА
                self._send_response(response_data)
            else:
                self._send_response({
                    'success': False,
                    'error': f'Failed to create game: {variant}'
                }, 400)

            return

        # ===== ВСЕ ОСТАЛЬНЫЕ ДЕЙСТВИЯ =====
        # Требуют существующей игры!
        engine = self._get_engine(session_id)

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

            success = engine.move(from_pile, to_pile, count)

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

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0
            })

        # ----- ОТМЕНА -----
        elif parsed.path == '/undo':
            success = engine.undo()

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
                'score': engine.state.score if won else 0
            })

        else:
            self._send_response({
                'success': False,
                'error': f'Unknown path: {parsed.path}'
            }, 404)

    def log_message(self, format, *args):
        """Минимальное логирование."""
        # Просто игнорируем - не выводим ничего
        pass


def start_server(host='localhost', port=8080):
    """Запуск HTTP сервера."""
    print("=" * 50)
    print("🎮 Solitaire Engine Server")
    print("=" * 50)
    print(f"📡 Сервер: http://{host}:{port}")
    print(f"🆔 Режим: Мультисессионный")
    print(f"🎲 Игры:   {', '.join(GameFactory.available_games())}")
    print("=" * 50)
    print("🔥 Godot сам выбирает игру при /new")
    print("💡 Каждый клиент - отдельная сессия")
    print("=" * 50)

    server = HTTPServer((host, port), GodotBridgeHandler)

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