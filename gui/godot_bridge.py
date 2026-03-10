# gui/godot_bridge.py
"""
Godot Bridge — HTTP мост между Godot и движком пасьянса.
Godot выбирает игру, сервер подстраивается.

🔢 СТАТИСТИКА: Теперь с поддержкой идентификации игроков и сбора статистики!
💾 СОХРАНЕНИЯ: Автосохранение, загрузка, проверка статуса (active/suspended).
"""

import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import SolitaireEngine
from model.rules.factory import GameFactory
from stats.api import StatsAPI


class GameStateEncoder(json.JSONEncoder):
    """Сериализация GameState в JSON для отправки в Godot."""

    def default(self, obj):
        # Если у объекта есть наш новый метод to_dict, используем его
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()

        # Fallback для старой логики (на всякий случай)
        if hasattr(obj, '__dict__'):
            # GameState (старый формат)
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

            # Pile (старый формат)
            elif hasattr(obj, 'name') and isinstance(obj, list):
                return {
                    'name': obj.name,
                    'cards': [self.default(card) for card in obj]
                }

            # Card (старый формат)
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
    """

    games = {}
    game_ids = {}
    stats_api = None
    SUSPENDED_THRESHOLD_HOURS = 1  # Порог для перевода в suspended

    def _get_session_id(self):
        return self.client_address[0]

    def _get_engine(self, session_id):
        return self.games.get(session_id)

    def _get_game_id(self, session_id):
        return self.game_ids.get(session_id)

    def _create_engine(self, session_id, variant):
        try:
            game_type = "klondike"
            game_variant = "standard"
            if variant == "klondike-3":
                variant = "klondike"
                game_variant = "draw-three"

            rules = GameFactory.create(variant)
            print(f"📦 [{session_id}] Создана игра: {variant}")

            engine = SolitaireEngine(rules)
            engine.new_game()

            self.games[session_id] = engine
            engine._game_variant = game_variant
            engine._game_type = game_type

            return engine

        except Exception as e:
            print(f"❌ [{session_id}] Ошибка создания игры {variant}: {e}")
            return None

    def _get_suits_completed(self, state) -> list:
        suits_completed = []
        for i in range(4):
            pile_name = f"foundation_{i}"
            pile = state.piles.get(pile_name)
            if pile and len(pile) == 13:
                if not pile.is_empty():
                    top_card = pile.top()
                    suits_completed.append(top_card.suit.name)
        return suits_completed

    def _check_perfect_game(self, engine, state) -> bool:
        if not engine or not state:
            return False
        if getattr(state, 'undos_used', 0) > 0 or getattr(state, 'hints_used', 0) > 0:
            return False
        return True

    def _send_response(self, data, status=200):
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
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        session_id = self._get_session_id()
        query = parse_qs(parsed.query)

        if parsed.path == '/player/identity':
            player_id = query.get('player_id', [None])[0]
            if player_id:
                result = self.stats_api.connect(player_id)
                if result and result.get('success'):
                    self._send_response(result)
                else:
                    result = self.stats_api.get_or_create_player(player_id)
                    self._send_response(result)
            else:
                result = self.stats_api.init_client()
                self._send_response(result)
            return

        if parsed.path == '/variants':
            variants = GameFactory.available_games()
            self._send_response({
                'success': True,
                'variants': variants,
                'default': 'klondike'
            })
            return

        # ===== ЗАГРУЗКА / ПРОВЕРКА СОХРАНЕННОЙ ИГРЫ =====
        if parsed.path == '/load':
            """Проверить наличие сохранения и загрузить, если есть."""

            player_id = query.get('player_id', [None])[0]
            game_type = query.get('game_type', ['klondike'])[0]

            if not player_id:
                self._send_response({'success': False, 'error': 'Missing player_id'}, 400)
                return

            # Ищем сохранение в БД
            saves = self.stats_api.get_player_saves(player_id, game_type)
            autosaves = [s for s in saves if s.get('save_type') == 'autosave']
            print(f"📂 [{session_id}] Запрос /load от player_id: {player_id}, game_type: {game_type}")
            print(f"   Найдено сохранений: {len(autosaves)}")
            if not autosaves:
                self._send_response({'success': True, 'has_save': False})
                return

            save = autosaves[0]  # Берем последнее автосохранение

            # Проверяем время (Suspended logic)
            last_played_str = save.get('updated_at') or save.get('created_at')
            is_suspended = False

            if last_played_str:
                try:
                    # Предполагаем формат ISO 8601
                    last_played = datetime.fromisoformat(last_played_str)
                    if datetime.now() - last_played > timedelta(hours=self.SUSPENDED_THRESHOLD_HOURS):
                        is_suspended = True
                except:
                    pass # Если дата не парсится, считаем активной

            self._send_response({
                'success': True,
                'has_save': True,
                'save_id': save['id'],
                'is_suspended': is_suspended,
                'moves': save.get('moves', 0),
                'time': save.get('time', 0),
                'score': save.get('score', 0),
                'date': last_played_str
            })
            return

        if parsed.path == '/state':
            engine = self._get_engine(session_id)
            if engine and engine.state:
                self._send_response({
                    'success': True,
                    'state': engine.state,
                    'score': engine.state.score,
                    'moves': engine.state.moves_count,
                    'time': engine.state.time_elapsed
                })
            else:
                self._send_response({'success': False, 'error': 'No active game'}, 404)
            return

        if parsed.path == '/player/stats':
            player_id = query.get('player_id', [None])[0]
            if not player_id:
                self._send_response({'success': False, 'error': 'Missing player_id'}, 400)
                return
            stats = self.stats_api.get_player_stats_summary(player_id)
            self._send_response(stats)
            return

        if parsed.path == '/leaderboard':
            criterion = query.get('by', ['games_won'])[0]
            limit = int(query.get('limit', [10])[0])
            leaders = self.stats_api.get_leaderboard(criterion, limit)
            self._send_response({'success': True, 'criterion': criterion, 'players': leaders})
            return

        if parsed.path == '/player/saves':
            player_id = query.get('player_id', [None])[0]
            game_type = query.get('game_type', [None])[0]
            if not player_id:
                self._send_response({'success': False, 'error': 'Missing player_id'}, 400)
                return
            saves = self.stats_api.get_player_saves(player_id, game_type)
            self._send_response({'success': True, 'saves': saves, 'count': len(saves)})
            return

        self._send_response({'success': False, 'error': f'Unknown path: {parsed.path}'}, 404)


    def do_POST(self):
        parsed = urlparse(self.path)
        session_id = self._get_session_id()

        content_length = int(self.headers.get('Content-Length', 0))
        command = {}
        if content_length > 0:
            try:
                post_data = self.rfile.read(content_length)
                command = json.loads(post_data.decode('utf-8'))
            except:
                pass

        # ===== СОХРАНЕНИЕ ИГРЫ =====
        if parsed.path == '/save':
            """Принудительное сохранение (автосохранение от клиента)."""
            print(f"💾 [{session_id}] Запрос /save от player_id: {command.get('player_id')}")
            print(f"   game_type: {command.get('game_type', 'klondike')}")
            print(f"   time_elapsed: {command.get('time_elapsed', 0)}")
            player_id = command.get('player_id')
            game_type = command.get('game_type', 'klondike')

            # Время от клиента (важно!)
            # Мы обновляем время в состоянии движка перед сохранением
            time_elapsed = command.get('time_elapsed', 0)

            engine = self._get_engine(session_id)

            if not engine or not engine.state:
                self._send_response({'success': False, 'error': 'No active game to save'}, 400)
                return

            # 1. Синхронизируем время (чтобы сохранилось актуальное)
            engine.update_play_time(time_elapsed)

            # 2. Сериализуем состояние через новый метод
            # Этот метод вернет словарь со всеми данными (score, moves, time)
            state_dict = engine.state.to_dict()

            # 3. Сохраняем через API
            # Передаем только то, что принимает метод
            result = self.stats_api.save_game(
                player_id=player_id,
                game_type=game_type,
                game_state=state_dict,  # Внутри уже есть score, moves, time
                save_type='autosave'
            )
            print(f"   Результат сохранения: {result}")
            self._send_response(result)
            return

        # ===== ЗАГРУЗКА СОХРАНЕННОЙ ИГРЫ В ПАМЯТЬ =====
        if parsed.path == '/load/save':
            """Загрузить сохранение в движок и начать игру."""
            player_id = command.get('player_id')
            save_id = command.get('save_id')

            if not save_id:
                self._send_response({'success': False, 'error': 'Missing save_id'}, 400)
                return

            # 1. Получаем данные из БД
            save_data = self.stats_api.load_saved_game(int(save_id))

            if not save_data or not save_data.get('success'):
                self._send_response({'success': False, 'error': 'Save not found in DB'}, 404)
                return

            # 2. Определяем тип игры
            variant = "klondike"
            if save_data.get('game_type') == 'klondike-3':
                variant = "klondike-3"

            # 3. Создаем НОВЫЙ движок для этой сессии
            # Важно: мы не ищем игру в self.games, мы создаем новую сессию
            engine = self._create_engine(session_id, variant)
            if not engine:
                self._send_response({'success': False, 'error': 'Failed to create engine'}, 500)
                return

            # 4. Восстанавливаем состояние из БД
            state_dict = save_data['game_state']

            # Преобразуем время, если оно пришло как строка (на всякий случай)
            if 'time_elapsed' in save_data:
                time_val = save_data['time_elapsed']
                if isinstance(time_val, str):
                    # Обработка если нужно, обычно int
                    pass
                engine.update_play_time(int(time_val))

            if engine.restore_state(state_dict):
                # 5. Удаляем сохранение из БД, так как мы его загрузили
                # (Опционально: можно оставить, чтобы можно было переиграть)
                # Пока оставим.

                state_dict = engine.state.to_dict()

                self._send_response({
                    'success': True,
                    'state': state_dict,  # ← ИСПРАВЛЕНО: словарь!
                    'score': engine.state.score,
                    'moves': engine.state.moves_count,
                    'time': engine.state.time_elapsed,
                    'saved_game_id': save_id  # ← Добавлено для меню
                })
            else:
                self._send_response({'success': False, 'error': 'Failed to restore state'}, 500)
            return

        # ===== СДАТЬСЯ (ABANDON) =====
        if parsed.path == '/abandon':
            """Сдаться и удалить сохранение."""
            player_id = command.get('player_id')
            game_type = command.get('game_type', 'klondike')

            engine = self._get_engine(session_id)
            game_id = self._get_game_id(session_id)

            # 1. Записываем проигрыш в статистику, если игра была начата
            if game_id and engine:
                 self.stats_api.end_game(
                    game_id=game_id,
                    result='lost', # Или 'abandoned'
                    score=engine.state.score,
                    moves=engine.state.moves_count,
                    game_type=game_type
                )

            # 2. Удаляем сохранение
            # (Нужно реализовать метод в stats_api или просто вызвать delete_saved_game)
            # Упрощенно: удаляем через delete_saved_game, если знаем ID сохранения
            # Но надежнее очистить все автосохранения игрока для этого типа
            self.stats_api.delete_autosave(player_id, game_type) # Нужно будет добавить этот метод

            # 3. Очищаем сессию
            if session_id in self.games:
                del self.games[session_id]
            if session_id in self.game_ids:
                del self.game_ids[session_id]

            self._send_response({'success': True, 'message': 'Game abandoned'})
            return

        # ===== СОЗДАНИЕ НОВОЙ ИГРЫ =====
        if parsed.path == '/new':
            variant = command.get('variant', 'klondike')
            player_id = command.get('player_id')
            force_new = command.get('force_new', False) # Флаг принудительного начала новой игры

            print(f"📥 [{session_id}] Запрос /new для {variant}")

            # Проверяем наличие сохранения
            if not force_new and player_id:
                saves = self.stats_api.get_player_saves(player_id, variant)
                autosaves = [s for s in saves if s.get('save_type') == 'autosave']
                if autosaves:
                    # Нашли сохранение! Возвращаем конфликт.
                    save = autosaves[0]
                    self._send_response({
                        'success': False,
                        'error': 'active_game_exists',
                        'save_id': save['id'],
                        'moves': save.get('moves', 0),
                        'time': save.get('time', 0),
                        'score': save.get('score', 0)
                    }, 409) # HTTP 409 Conflict
                    return

            # Создаем новый движок
            engine = self._create_engine(session_id, variant)

            if engine:
                game_id = None
                if player_id and self.stats_api:
                    result = self.stats_api.start_game(player_id, variant)
                    if result.get('success'):
                        game_id = result.get('game_id')
                        self.game_ids[session_id] = game_id

                response_data = {
                    'success': True,
                    'variant': variant,
                    'state': engine.state,
                    'score': 0,
                    'moves': 0
                }
                if game_id:
                    response_data['game_id'] = game_id

                self._send_response(response_data)
            else:
                self._send_response({'success': False, 'error': f'Failed to create game: {variant}'}, 400)
            return

        # ===== ЗАВЕРШЕНИЕ ИГРЫ =====
        if parsed.path == '/game/end':
            print(f"🏁 /game/end вызван с result={command.get('result')}")
            player_id = command.get('player_id')
            result_str = command.get('result', 'abandoned')
            score = command.get('score', 0)
            moves = command.get('moves', 0)
            time_val = command.get('time', 0) # Получаем время от клиента

            engine = self._get_engine(session_id)
            game_id = self._get_game_id(session_id)

            suits_completed = []
            was_perfect = False

            if engine and engine.state:
                # Синхронизируем время на случай, если /save не вызывали
                engine.update_play_time(time_val)

                suits_completed = self._get_suits_completed(engine.state)
                was_perfect = self._check_perfect_game(engine, engine.state)

            if game_id and self.stats_api:
                stats_result = self.stats_api.end_game(
                    game_id=game_id,
                    result=result_str,
                    score=score,
                    moves=moves,
                    game_type="klondike",
                    suits_completed=suits_completed,
                    was_perfect=was_perfect,
                    # time_elapsed=time_val # Передаем время
                )

                # Удаляем сохранение после победы
                if result_str == 'won':
                    self.stats_api.delete_autosave(player_id, "klondike")

                if session_id in self.games:
                    del self.games[session_id]
                if session_id in self.game_ids:
                    del self.game_ids[session_id]

                self._send_response(stats_result)
            else:
                self._send_response({'success': True, 'game_completed': True, 'result': result_str})
            return

        # ===== СМЕНА ИМЕНИ ИГРОКА =====
        if parsed.path == '/player/rename':
            player_id = command.get('player_id')
            new_name = command.get('new_name')
            if not player_id or not new_name:
                self._send_response({'success': False, 'error': 'Missing data'}, 400)
                return
            result = self.stats_api.rename_player(player_id, new_name)
            self._send_response(result)
            return

        # ===== ИГРОВЫЕ ДЕЙСТВИЯ =====
        engine = self._get_engine(session_id)
        game_id = self._get_game_id(session_id)

        if not engine:
            self._send_response({'success': False, 'error': 'No active game. Call /new first!', 'need_init': True}, 404)
            return

        # Передаем время от клиента при любом действии (для актуальности state)
        if 'time_elapsed' in command:
            engine.update_play_time(command['time_elapsed'])

        # ----- ХОДЫ -----
        if parsed.path == '/move':
            from_pile = command.get('from')
            to_pile = command.get('to')
            count = command.get('count', 1)

            if not from_pile or not to_pile:
                self._send_response({'success': False, 'error': 'Missing from or to pile'}, 400)
                return

            success = engine.move(from_pile, to_pile, count)

            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(game_id, moves=engine.state.moves_count)

            available = []
            if success and hasattr(engine.rules, 'get_available_moves'):
                available = engine.rules.get_available_moves(engine.state)
            # ПОСЛЕ хода проверяем победу
            game_won = engine.rules.check_win(engine.state) if success else False

            # ЕСЛИ ПОБЕДА - вызываем end_game!
            if game_won and game_id and self.stats_api:
                print(f"🏆 ПОБЕДА! game_id={game_id}")
                self.stats_api.end_game(
                    game_id=game_id,
                    result='won',
                    score=engine.state.score,
                    moves=engine.state.moves_count,
                    game_type="klondike",
                    suits_completed=self._get_suits_completed(engine.state),
                    was_perfect=self._check_perfect_game(engine, engine.state)
                )
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
            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(game_id, moves=engine.state.moves_count)

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0,
                'game_won': engine.rules.check_win(engine.state) if success else False
            })

        # ----- ОТМЕНА -----
        elif parsed.path == '/undo':
            success = engine.undo()
            if success and game_id and self.stats_api:
                self.stats_api.update_game_progress(game_id, undos=getattr(engine.state, 'undos_used', 0))

            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0,
                'game_won': engine.rules.check_win(engine.state) if success else False
            })

        # ----- ПОВТОР -----
        elif parsed.path == '/redo':
            success = engine.redo()
            self._send_response({
                'success': success,
                'state': engine.state if success else None,
                'score': engine.state.score if success else 0,
                'moves': engine.state.moves_count if success else 0,
                'game_won': engine.rules.check_win(engine.state) if success else False
            })

        # ----- АВТО-ХОД -----
        elif parsed.path == '/auto_move':
            from_pile = command.get('from')
            if not from_pile:
                self._send_response({'success': False, 'error': 'Missing from pile'}, 400)
                return

            moves = engine.rules.get_available_moves(engine.state)
            from_moves = [m for m in moves if m.from_pile == from_pile]

            if not from_moves:
                self._send_response({'success': False, 'error': f'No moves from {from_pile}'})
                return

            foundation_moves = [m for m in from_moves if m.to_pile.startswith('foundation_')]
            tableau_moves = [m for m in from_moves if m.to_pile.startswith('tableau_')]

            selected_move = None
            if foundation_moves:
                selected_move = foundation_moves[0]
            elif tableau_moves:
                tableau_moves.sort(key=lambda m: int(m.to_pile.split('_')[1]), reverse=True)
                selected_move = tableau_moves[0]

            if selected_move:
                success = engine.move(selected_move.from_pile, selected_move.to_pile, len(selected_move.cards))
                if success and game_id and self.stats_api:
                    self.stats_api.update_game_progress(game_id, moves=engine.state.moves_count)
                    # ПОСЛЕ хода проверяем победу
                    game_won = engine.rules.check_win(engine.state) if success else False

                    # ЕСЛИ ПОБЕДА - вызываем end_game!
                    if game_won and game_id and self.stats_api:
                        print(f"🏆 ПОБЕДА! game_id={game_id}")
                        self.stats_api.end_game(
                            game_id=game_id,
                            result='won',
                            score=engine.state.score,
                            moves=engine.state.moves_count,
                            game_type="klondike",
                            suits_completed=self._get_suits_completed(engine.state),
                            was_perfect=self._check_perfect_game(engine, engine.state)
                        )
                self._send_response({
                    'success': success,
                    'move': {'from': selected_move.from_pile, 'to': selected_move.to_pile,
                             'count': len(selected_move.cards)},
                    'state': engine.state if success else None,
                    'score': engine.state.score if success else 0,
                    'moves': engine.state.moves_count if success else 0,
                    'game_won': engine.rules.check_win(engine.state) if success else False
                })
            else:
                self._send_response({'success': False, 'error': 'No suitable move'})

        # ----- ПОДСКАЗКА -----
        elif parsed.path == '/hint':
            hint = engine.rules.get_hint(engine.state)
            if hint:
                if game_id and self.stats_api:
                    self.stats_api.update_game_progress(game_id, hints=getattr(engine.state, 'hints_used', 0) + 1)
                self._send_response({'success': True, 'hint': {'from': hint.from_pile, 'to': hint.to_pile, 'count': len(hint.cards)}})
            else:
                self._send_response({'success': False, 'error': 'No hints available'})

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
            self._send_response({'success': False, 'error': f'Unknown path: {parsed.path}'}, 404)

    def log_message(self, format, *args):
        pass


def start_server(host='127.0.0.1', port=8080):
    print("=" * 50)
    print("🎮 Solitaire Engine Server")
    print("=" * 50)
    print(f"📡 Сервер: http://{host}:{port}")
    print(f"🆔 Режим: Мультисессионный")
    print(f"🎲 Игры:   {', '.join(GameFactory.available_games())}")
    print("📊 Статистика: Загрузка...")
    GodotBridgeHandler.stats_api = StatsAPI(storage_path="./stats_data")
    print("✅ Статистика: Готова")
    print("=" * 50)
    print("🔥 Godot сам выбирает игру при /new")
    print("👤 Игроки идентифицируются по UUID")
    print("📈 Статистика сохраняется в БД")
    print("💾 Автосохранение и загрузка активны")
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