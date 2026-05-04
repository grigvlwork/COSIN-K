# model/engine.py
from typing import List, Callable, Optional, Dict, Any, Tuple
import random
from dataclasses import dataclass, field

from .card import Card, Suit, Rank
from .pile import Pile
from .state import GameState
from .move import Move
from .history import HistoryManager
from .rules.base import RuleSet


class SolitaireEngine:
    """
    Движок пасьянса.
    Связывает правила, состояние и историю.
    """

    def __init__(self, rules: RuleSet, player_id: str = "player1"):
        self.rules = rules
        self.player_id = player_id
        self._state: Optional[GameState] = None
        self.history = HistoryManager(limit=5000)
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []
        self.cards_moved_count = 0
        self.cards_flipped_count = 0

    # === Свойства ===

    @property
    def state(self) -> Optional[GameState]:
        """Текущее состояние игры."""
        return self._state

    @property
    def is_game_active(self) -> bool:
        """Идёт ли игра."""
        return self._state is not None

    # === Управление игрой ===

    def new_game(self, seed: Optional[int] = None) -> None:
        """Начать новую игру."""
        # (Код без изменений)
        deck = self._create_shuffled_deck(seed)
        dealt_piles = self.rules.deal(deck)
        dealt_count = sum(len(p) for p in dealt_piles.values())
        stock_cards = deck[dealt_count:]
        self._state = GameState(
            piles=dealt_piles,
            stock=Pile("stock", stock_cards),
            waste=Pile("waste"),
            score=0,
            moves_count=0,
            time_elapsed=0
        )
        self.history.clear()
        self.history.push(self._state.copy(), move=None)
        self.cards_moved_count = 0
        self.cards_flipped_count = 0
        self._notify("game_started", {"seed": seed})

    def restore_state(self, state_dict: Dict[str, Any]) -> bool:
        """Восстановить игру из сохранения."""
        # (Код без изменений)
        try:
            self._state = GameState.from_dict(state_dict)
            self.history.clear()
            self.history.push(self._state.copy(), move=None)
            self.cards_moved_count = 0
            self.cards_flipped_count = 0
            self._notify("game_restored", {
                "moves": self._state.moves_count,
                "score": self._state.score
            })
            return True
        except Exception as e:
            print(f"❌ Ошибка восстановления игры: {e}")
            self._state = None
            return False

    def update_play_time(self, seconds: int) -> None:
        if self._state:
            self._state.time_elapsed = seconds

    def _create_shuffled_deck(self, seed: Optional[int] = None) -> List[Card]:
        rng = random.Random(seed)
        deck = [Card(suit=suit, rank=rank, face_up=False) for suit in Suit for rank in Rank]
        rng.shuffle(deck)
        return deck

    # === НОВАЯ ЛОГИКА ХОДОВ ===

    def _find_card_location(self, card_id: str) -> Optional[Tuple[str, Pile, int]]:
        """
        Находит карту по ID в текущем состоянии.
        Возвращает: (имя_стопки, объект_стопки, индекс_карты) или None.
        """
        if not self._state:
            return None

        # 1. Ищем в tableau и foundation (state.piles — словарь)
        for name, pile in self._state.piles.items():
            # Исправлено: pile сам по себе список карт
            for idx, card in enumerate(pile):
                if card.id == card_id:
                    return name, pile, idx

        # 2. Ищем в waste
        for idx, card in enumerate(self._state.waste):
            if card.id == card_id:
                return "waste", self._state.waste, idx

        # 3. Ищем в stock
        for idx, card in enumerate(self._state.stock):
            if card.id == card_id:
                return "stock", self._state.stock, idx

        return None

    def move(self, card_ids: List[str], target_pile: str) -> bool:
        """
        Выполнить ход по списку ID карт.

        Args:
            card_ids: Список ID карт (обычно 1 ID, или последовательность для tableau).
                      Первая карта в списке считается "ведущей".
            target_pile: Имя целевой стопки (tableau_N, foundation_N, waste).
        """
        if not self._state or not card_ids:
            return False

        # 1. Находим первую (ведущую) карту
        first_card_id = card_ids[0]
        location = self._find_card_location(first_card_id)

        if not location:
            print(f"❌ Move failed: Card ID {first_card_id} not found.")
            return False

        source_name, source_pile, start_index = location

        # 2. Нельзя двигать из stock (только через draw)
        if source_name == "stock":
            print(f"❌ Move failed: Cannot move directly from stock.")
            return False

        # 3. Проверка валидности последовательности
        # В Косынке мы можем двигать карту и все карты, лежащие на ней (start_index и выше).
        # Поэтому count = длина остатка стопки от найденного индекса.
        count = len(source_pile) - start_index

        # Если клиент передал несколько ID, проверяем, что они совпадают с тем, что на сервере
        if len(card_ids) > 1:
            # Проверяем, совпадают ли переданные ID с реальными картами "хвоста"
            actual_ids = [c.id for c in source_pile[start_index:]]
            if actual_ids != card_ids:
                print(f"❌ Move failed: ID sequence mismatch. Client: {card_ids}, Server: {actual_ids}")
                return False

        # Если передан 1 ID, но count > 1, это значит, мы тянем всю стопку.
        # Это ок, если правила разрешают.

        # 4. Проверка, что карта face_up (кроме waste, где это очевидно)
        card_to_move = source_pile[start_index]
        if not card_to_move.face_up:
            print(f"❌ Move failed: Card {first_card_id} is face down.")
            return False

        # 5. Создаем объект Move для проверки правилами
        preview_cards = source_pile.peek(count)
        move_obj = Move(
            from_pile=source_name,
            to_pile=target_pile,
            cards=preview_cards,
            from_index=start_index
        )

        # 6. Проверка правилами
        if not self.rules.can_move(self._state, move_obj):
            # Правила сами напечатают причину отказа, если нужно (или вернут False)
            return False

        # 7. Выполняем низкоуровневый ход
        try:
            new_state, executed_move = self._execute_move(source_name, target_pile, count)
        except ValueError as e:
            print(f"❌ Execute failed: {e}")
            return False

        # 8. Фиксируем изменения
        self._state = new_state
        self.history.push(self._state.copy(), executed_move)

        self._notify("move_made", {
            "from": source_name,
            "to": target_pile,
            "cards": [c.to_dict() for c in executed_move.cards],  # Отправляем полные данные карт
            "score": self._state.score
        })

        if self.rules.check_win(self._state):
            self._notify("game_won", {"score": self._state.score})

        return True

    # === Вспомогательные методы (draw, undo, redo и т.д.) ===

    def draw(self) -> bool:
        """Взять карту(ы) из колоды."""
        if not self._state or not self.rules.can_draw(self._state):
            return False

        new_state = self._state.copy()
        draw_count = self.rules.get_draw_count()

        # Recycle если колода пуста
        if new_state.stock.is_empty():
            if not self._recycle_stock(new_state):
                return False
            self._state = new_state
            return self.draw()

        # Нормальное взятие
        actual_count = min(draw_count, len(new_state.stock))
        cards = new_state.stock.take(actual_count)
        cards = [card.make_face_up() for card in cards]
        new_state.waste.add(cards)
        new_state.moves_count += 1

        # Создаём Move для истории
        move = Move(
            from_pile="stock",
            to_pile="waste",
            cards=cards,
            from_index=len(new_state.stock),  # Индекс после взятия (не важен для stock)
            flipped_cards=[],  # Карты перевернулись, но это часть хода draw
            score_delta=self.rules.score_draw(self._state, cards)
        )

        self._state = new_state
        self.history.push(self._state.copy(), move)
        self._notify("draw", {"cards": [c.to_dict() for c in cards]})
        return True

    def _execute_move(self, from_pile: str, to_pile: str, count: int) -> tuple[GameState, Move]:
        """
        Низкоуровневое выполнение хода.
        Возвращает (новое_состояние, объект Move).
        """
        new_state = self._state.copy()
        source = new_state.get_pile(from_pile)
        target = new_state.get_pile(to_pile)

        if source is None or target is None:
            raise ValueError(f"Invalid piles: {from_pile} or {to_pile}")

        previous_state = self._state

        # Берём карты
        cards = source.take(count)
        target.add(cards)

        self.cards_moved_count += count

        # Получаем переворот (из правил)
        flipped_cards = self.rules.get_flipped_cards(previous_state, Move(from_pile, to_pile, cards, len(source)))
        self.cards_flipped_count += len(flipped_cards)

        # Переворачиваем карту в источнике, если нужно
        for pile_name, card_index in flipped_cards:
            pile = new_state.get_pile(pile_name)
            if pile and card_index < len(pile):
                pile[card_index] = pile[card_index].make_face_up()

        # Считаем очки
        move_for_score = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=cards,
            from_index=len(source)  # Индекс изменился после take
        )
        score_delta = self.rules.score_move(new_state, move_for_score, previous_state)
        new_state.score += score_delta
        new_state.moves_count += 1

        # Создаём итоговый объект хода
        executed_move = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=cards,
            from_index=len(source),  # В истории храним, откуда ушли
            flipped_cards=flipped_cards,
            score_delta=score_delta
        )

        return new_state, executed_move

    def auto_complete_sequence(self) -> List[Move]:
        """Автосбор."""
        if not self._state or not hasattr(self.rules, "can_auto_complete"):
            return []
        if not self.rules.can_auto_complete(self._state):
            return []

        moves: List[Move] = []
        for _ in range(100):
            move = self._find_auto_move()
            if not move:
                break

            # Используем ID для вызова нового метода move
            # Но auto_complete должен быть мгновенным и без уведомлений?
            # Обычно да. Используем _execute_move напрямую.

            new_state, executed_move = self._execute_move(
                move.from_pile,
                move.to_pile,
                len(move.cards)
            )
            moves.append(executed_move)
            self._state = new_state

        return moves

    def _find_auto_move(self) -> Optional[Move]:
        # (Код без изменений)
        if not self._state: return None
        state = self._state
        for col in range(7):
            from_name = f"tableau_{col}"
            pile = state.get_pile(from_name)
            if not pile or pile.is_empty(): continue
            card = pile.top()
            for i in range(4):
                to_name = f"foundation_{i}"
                move = Move(from_pile=from_name, to_pile=to_name, cards=[card], from_index=len(pile) - 1)
                if self.rules.can_move(state, move):
                    return move
        return None

    def undo(self) -> bool:
        # (Код без изменений)
        if not self._state or not self.history.can_undo(): return False
        prev_state = self.history.undo()
        if prev_state:
            self._state = prev_state
            self._notify("undo", {})
            return True
        return False

    def redo(self) -> bool:
        # (Код без изменений)
        if not self._state or not self.history.can_redo(): return False
        next_state = self.history.redo()
        if next_state:
            self._state = next_state
            self._notify("redo", {})
            return True
        return False

    def check_win(self) -> bool:
        if not self._state: return False
        return self.rules.check_win(self._state)

    def get_hint(self) -> Optional[Move]:
        if not self._state: return None
        return self.rules.get_hint(self._state)

    def _recycle_stock(self, new_state: GameState) -> bool:
        # (Код без изменений)
        if new_state.waste.is_empty(): return False
        cards = new_state.waste.take(len(new_state.waste))
        cards.reverse()
        cards = [card.make_face_down() for card in cards]
        new_state.stock.add(cards)
        # Уведомления и история обрабатываются в вызывающем методе (draw)
        return True

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        if callback in self._listeners: self._listeners.remove(callback)

    def _notify(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        data = data or {}
        data["engine"] = self
        for listener in self._listeners:
            listener(event, data)

    def auto_complete_sequence(self) -> dict:
        """
        Выполняет автосбор игры.
        1. Проверяет условия (через rules).
        2. Запрашивает план ходов (через rules).
        3. Выполняет ходы через стандартный self.move() для сохранения статистики.
        """
        # 1. Проверка поддержки и условий
        if not hasattr(self.rules, 'can_auto_complete'):
            return {"success": False, "error": "Rules do not support auto-complete"}

        if not self.rules.can_auto_complete(self.state):
            return {"success": False, "error": "Conditions not met"}

        # 2. Получаем план ходов от правил
        # Правила (klondike.py) возвращают список объектов Move, рассчитанный на копии состояния
        moves_plan = self.rules.get_auto_finish_moves(self.state)

        if not moves_plan:
            return {"success": False, "error": "No moves generated"}

        performed_moves = []

        # 3. Выполняем каждый ход через движок
        for move in moves_plan:
            # Преобразуем объект Move в аргументы для engine.move()
            card_ids = [c.id for c in move.cards]
            target_pile = move.to_pile

            # Выполняем ход.
            # ВАЖНО: self.move() сам обновит очки, статистику и историю (undo).
            success = self.move(card_ids, target_pile)

            if success:
                # Сохраняем данные для анимации на клиенте
                performed_moves.append({
                    "card_ids": card_ids,
                    "from": move.from_pile,
                    "to": target_pile
                })
            else:
                # Если вдруг ход не прошел (теоретически невозможно при правильном планировании)
                print(f"⚠️ Auto-complete move failed unexpectedly: {move}")
                break

        # 4. Проверяем итог
        won = self.check_win()

        return {
            "success": won,
            "moves": performed_moves,
            "final_state": self.state
        }