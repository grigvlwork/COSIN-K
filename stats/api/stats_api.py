# stats/api/stats_api.py
"""
API для взаимодействия Godot клиента с модулем статистики.
"""

import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from stats.services.player_identity import PlayerIdentity
from stats.services.stats_service import StatsService
from stats.models import Player, Game, SavedGame, PlayerStats


class StatsAPI:
    """
    Единый API для всех операций со статистикой.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.identity = PlayerIdentity(storage_path)
        self.stats = StatsService()
        self._active_games: Dict[int, Dict[str, Any]] = {}

    # ===== ИДЕНТИФИКАЦИЯ =====

    def init_client(self) -> Dict[str, Any]:
        player_id = self.identity.get_or_create_client_identity()
        player = self.identity.get_current_player()
        return {
            'success': True,
            'player_id': player_id,
            'player_name': player.name if player else f"Player_{player_id[:8]}",
            'is_new': player is None
        }

    def connect(self, player_id: str) -> Optional[Dict[str, Any]]:
        player = self.identity.authenticate(player_id)
        if player:
            return {
                'success': True,
                'player_id': player.id,
                'player_name': player.name,
                'games_played': player.games_started,
                'games_won': player.games_won,
                'total_score': player.total_score
            }
        return {'success': False, 'error': 'Player not found'}

    def get_or_create_player(self, player_id: str) -> Dict[str, Any]:
        player = self.identity.get_or_create_server_player(player_id)
        return {
            'success': True,
            'player_id': player.id,
            'player_name': player.name,
            'is_new': True,
            'games_played': 0,
            'games_won': 0
        }

    def rename_player(self, player_id: str, new_name: str) -> Dict[str, Any]:
        success = self.identity.rename_player(player_id, new_name)
        if success:
            player = self.identity.get_player(player_id)
            return {
                'success': True,
                'player_id': player_id,
                'player_name': player.name if player else new_name,
                'message': 'Имя успешно изменено'
            }
        return {'success': False, 'error': 'Не удалось изменить имя'}

    # ===== УПРАВЛЕНИЕ ИГРАМИ =====

    def start_game(self, player_id: str, game_type: str = "klondike",
                   variant: str = "standard", seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Начать новую игру.

        Args:
            seed: Сид генерации (если переигрываем)
        """
        if game_type == "klondike" and variant == "draw-three":
            stats_game_type = "klondike_3"
        else:
            stats_game_type = game_type

        # Передаем сид в сервис
        game_id = self.stats.start_game(player_id, stats_game_type, seed=seed)

        if game_id:
            self._active_games[game_id] = {
                'player_id': player_id,
                'game_type': stats_game_type,
                'seed': seed,  # Сохраняем сид в сессии API
                'started_at': datetime.now(),
                'moves': 0,
                'undos': 0,
                'hints': 0,
                'deck_cycles': 0
            }

            return {
                'success': True,
                'game_id': game_id,
                'game_type': game_type,
                'variant': variant,
                'seed': seed,  # Возвращаем сид клиенту
                'message': f'Игра {game_type} начата'
            }

        return {'success': False, 'error': 'Не удалось создать игру'}

    def end_game(self, game_id: int, result: str, score: int = 0,
                 moves: int = 0, game_type: str = "klondike",
                 suits_completed: Optional[List[str]] = None,
                 was_perfect: bool = False,
                 cards_moved: int = 0,      # <--- ДОБАВЛЕНО
                 cards_flipped: int = 0     # <--- ДОБАВЛЕНО
                 ) -> Dict[str, Any]:

        print(f"\n=== StatsAPI.end_game ===")
        print(f"  game_id: {game_id}, result: {result}")

        session = self._active_games.pop(game_id, {})
        total_moves = moves or session.get('moves', 0)

        # Завершаем игру через сервис
        end_result = self.stats.end_game(
            game_id=game_id,
            result=result,
            score=score,
            suits_completed=suits_completed,
            cards_moved=cards_moved,
            cards_flipped=cards_flipped,
            was_perfect=was_perfect
        )

        success = end_result.get('success', False)
        is_first_win = end_result.get('is_first_win', False)
        unlocked_ids = end_result.get('unlocked_achievements', [])

        if success:
            player_id = session.get('player_id')
            if player_id:
                stats = self.stats.get_player_stats(player_id)
                if stats:
                    return {
                        'success': True,
                        'game_completed': True,
                        'result': result,
                        'score': score,
                        'moves': total_moves,
                        'is_first_win': is_first_win,
                        'unlocked_achievements': unlocked_ids,
                        'player_stats': {
                            'games_won': stats.player.games_won,
                            'games_played': stats.player.games_started,
                            'total_score': stats.player.total_score,
                            'current_streak': stats.player.current_win_streak,
                            'best_streak': stats.player.best_win_streak
                        }
                    }
            return {
                'success': True,
                'game_completed': True,
                'result': result,
                'score': score,
                'is_first_win': is_first_win,
                'unlocked_achievements': unlocked_ids
            }

        return {'success': False, 'error': 'Не удалось завершить игру'}

    def update_game_progress(self, game_id: int, **kwargs) -> bool:
        if game_id in self._active_games:
            for key, value in kwargs.items():
                if key in self._active_games[game_id]:
                    self._active_games[game_id][key] = value
            return True
        return False

    # ===== СОХРАНЕНИЯ =====

    def save_game(self, player_id: str, game_type: str,
                  game_state: Dict[str, Any],
                  seed: Optional[int] = None,
                  save_type: str = 'autosave',
                  description: str = '') -> Dict[str, Any]:
        """
        Сохранить игру.

        Args:
            seed: Сид текущей игры
        """
        score = game_state.get('score', 0)
        moves = game_state.get('moves_count', 0)
        time_elapsed = game_state.get('time_elapsed', 0)

        print(f"📊 Сохраняем игру: score={score}, seed={seed}")

        saved_id = self.stats.save_game(
            player_id=player_id,
            game_type=game_type,
            game_state=game_state,
            seed=seed,
            save_type=save_type,
            description=description,
            score=score,
            moves_count=moves,
            time_played_seconds=time_elapsed
        )

        if saved_id:
            return {'success': True, 'saved_game_id': saved_id, 'message': 'Игра сохранена'}

        return {'success': False, 'error': 'Не удалось сохранить игру'}

    def load_saved_game(self, saved_game_id: int) -> Optional[Dict[str, Any]]:
        saved = self.stats.load_saved_game(saved_game_id)
        if saved:
            return {
                'success': True,
                'game_id': saved.id,
                'game_type': saved.game_type,
                'game_state': saved.game_state,
                'seed': saved.seed,
                'moves': saved.moves_count,
                'time': saved.time_played_seconds,
                'score': saved.score,
                'save_type': saved.save_type,
                'saved_at': saved.updated_at.isoformat() if saved.updated_at else None
            }
        return {'success': False, 'error': 'Сохранение не найдено'}

    def get_player_saves(self, player_id: str,
                         game_type: Optional[str] = None) -> List[Dict[str, Any]]:
        saves = self.stats.get_player_saves(player_id, game_type)
        return [{
            'id': s.id,
            'game_type': s.game_type,
            'save_type': s.save_type,
            'seed': s.seed,
            'moves': s.moves_count,
            'time': s.time_played_seconds,
            'score': s.score,
            'description': s.description,
            'is_favorite': s.is_favorite,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None
        } for s in saves]

    # ===== СТАТИСТИКА =====

    def get_player_stats_summary(self, player_id: str) -> Dict[str, Any]:
        summary = self.stats.get_statistics_summary(player_id)
        return {'success': True, **summary}

    def get_leaderboard(self, criterion: str = 'games_won',
                        limit: int = 10) -> List[Dict[str, Any]]:
        players = self.stats.get_leaderboard(criterion, limit)
        return [{
            'player_id': p.id,
            'player_name': p.name,
            'games_won': p.games_won,
            'total_score': p.total_score
        } for p in players]

    def get_game_history(self, player_id: str,
                         limit: int = 50) -> List[Dict[str, Any]]:
        games = self.stats.get_game_history(player_id, limit)
        return [{
            'id': g.id,
            'game_type': g.game_type,
            'result': g.result,
            'seed': g.seed,
            'score': g.score,
            'moves': g.moves_count,
            'duration': g.duration_seconds,
            'date': g.ended_at.isoformat() if g.ended_at else None
        } for g in games]

    # ===== ДОСТИЖЕНИЯ =====

    def get_achievements(self, player_id: str) -> Dict[str, Any]:
        """
        Получить список достижений игрока.
        Скрывает название/описание для секретных (не полученных) достижений.
        """
        all_achievements = self.stats.achievement_repo.get_all()
        player_progress = self.stats.player_achievement_repo.get_by_player(player_id)
        progress_map = {pa.achievement_id: pa for pa in player_progress}

        result_list = []
        for ach in all_achievements:
            pa = progress_map.get(ach.id)
            is_unlocked = pa.unlocked if pa else False

            item = {
                'id': ach.id,
                'icon': ach.icon,
                'category': ach.category,
                'unlocked': is_unlocked,
                'progress': pa.progress if pa else 0,
                'target': ach.target
            }

            if is_unlocked or not ach.is_hidden:
                item['name'] = ach.name
                item['description'] = ach.description
            else:
                item['name'] = "???"
                item['description'] = "Секретное достижение"

            if is_unlocked and pa.unlocked_at:
                item['unlocked_at'] = pa.unlocked_at.isoformat()
            else:
                item['unlocked_at'] = None

            result_list.append(item)

        return {
            'success': True,
            'achievements': result_list,
            'total_count': len(all_achievements),
            'unlocked_count': sum(1 for x in result_list if x['unlocked'])
        }

    def get_achievements_album(self, player_id: str) -> Dict[str, Any]:
        """Получить достижения для режима 'Альбом' (только видимые)."""
        visible_list = self.stats.get_achievement_album(player_id)

        # Возвращаем в том же формате, что и раньше, для совместимости
        return {
            'success': True,
            'achievements': visible_list,
            'total_count': len(visible_list),
            'unlocked_count': sum(1 for x in visible_list if x['unlocked'])
        }

    # ===== АДМИНИСТРИРОВАНИЕ =====

    def delete_autosave(self, player_id: str, game_type: str) -> Dict[str, Any]:
        saves = self.stats.get_player_saves(player_id, game_type)
        autosave = next((s for s in saves if s.save_type == 'autosave'), None)

        if autosave:
            success = self.stats.delete_saved_game(autosave.id)
            if success:
                return {'success': True}
            return {'success': False, 'error': 'Failed to delete save'}
        return {'success': True}