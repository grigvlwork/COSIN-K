"""
Pile — стопка карт с дополнительными методами доступа.
"""

from typing import List, Optional, Iterator
from .card import Card


class Pile(List[Card]):
    """
    Стопка карт, расширяющая list.
    Поддерживает именованный доступ и специфичные операции пасьянса.
    """

    def __init__(self, name: str = "", cards: Optional[List[Card]] = None):
        super().__init__(cards or [])
        self.name = name

    # === Доступ к картам ===

    def peek(self, n: int = 1) -> List[Card]:
        """Посмотреть верхние n карт не удаляя их."""
        if n <= 0:
            return []
        return self[-n:] if len(self) >= n else self[:]

    def top(self) -> Optional[Card]:
        """Верхняя карта или None если пусто."""
        return self[-1] if self else None

    def bottom(self) -> Optional[Card]:
        """Нижняя карта или None если пусто."""
        return self[0] if self else None

    # === Извлечение карт ===

    def take(self, n: int = 1) -> List[Card]:
        """Извлечь верхние n карт."""
        if n <= 0 or not self:
            return []

        taken = self[-n:]
        del self[-n:]
        return taken

    def take_from(self, index: int) -> List[Card]:
        """
        Извлечь карты начиная с индекса (включительно) до конца.
        Для пасьянса: взять открытые карты с конца стопки.
        """
        if index < 0 or index >= len(self):
            return []

        taken = self[index:]
        del self[index:]
        return taken

    # === Добавление карт ===

    def add(self, cards: List[Card]) -> None:
        """Добавить карты сверху."""
        self.extend(cards)

    def put(self, card: Card) -> None:
        """Положить одну карту сверху."""
        self.append(card)

    # === Проверки ===

    def is_empty(self) -> bool:
        """Пустая ли стопка."""
        return len(self) == 0

    def size(self) -> int:
        """Количество карт."""
        return len(self)

    def face_up_count(self) -> int:
        """Сколько открытых карт сверху (подряд)."""
        count = 0
        for card in reversed(self):
            if card.face_up:
                count += 1
            else:
                break
        return count

    def all_face_up(self) -> bool:
        """Все ли карты открыты."""
        return all(c.face_up for c in self)

    def all_face_down(self) -> bool:
        """Все ли карты закрыты."""
        return all(not c.face_up for c in self)

    # === Манипуляции ===

    def flip_top(self) -> bool:
        """
        Перевернуть верхнюю карту (закрытую → открытую).
        Возвращает True если перевернули.
        """
        if self and not self[-1].face_up:
            self[-1] = self[-1].flip()
            return True
        return False

    def flip_all(self, face_up: bool = True) -> None:
        """Оптимизированное массовое переворачивание"""
        if face_up:
            # Все карты лицом вверх
            for i in range(len(self)):
                if not self[i].face_up:
                    self[i] = self[i].make_face_up()
        else:
            # Все карты лицом вниз
            for i in range(len(self)):
                if self[i].face_up:
                    self[i] = self[i].make_face_down()

    # === Итераторы ===

    def face_up_cards(self) -> Iterator[Card]:
        """Итератор по открытым картам сверху вниз."""
        for card in reversed(self):
            if card.face_up:
                yield card
            else:
                break

    def face_down_cards(self) -> Iterator[Card]:
        """Итератор по закрытым картам снизу вверх."""
        for card in self:
            if not card.face_up:
                yield card
            else:
                break

    # === Копирование ===

    def copy(self) -> "Pile":
        """Глубокая копия стопки."""
        new_pile = Pile(self.name)
        new_pile.extend([Card(c.suit, c.rank, c.face_up) for c in self])
        return new_pile

    # === Представление ===

    def __repr__(self) -> str:
        cards_str = " ".join(str(c) for c in self)
        return f"Pile({self.name!r}, [{cards_str}])"

    def __str__(self) -> str:
        if not self:
            return f"[{self.name}: empty]"
        return f"[{self.name}: {len(self)} cards, top={self.top()}]"