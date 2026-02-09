from itertools import product
from random import shuffle, choice

SUITS = 'ЧБКП'
RANKS = ('Т', '2', '3', '4', '5', '6',
         '7', '8', '9', '10', 'В', 'Д', 'К')


class Card:
    def __init__(self, rank, suit, revealed=False):
        self.suit = suit
        self.rank = rank
        self.revealed = revealed

    def is_red(self):
        return self.suit in 'ЧБ'

    def is_black(self):
        return self.suit in 'ПК'

    def reveal(self):
        self.revealed = True


class Deck:
    def __init__(self, back='XX'):
        self.cards = []
        self.back = back
        for row in product(RANKS, SUITS):
            self.cards.append(Card(*row))

    def shuffle(self):
        shuffle(self.cards)

class Pile:
    def __init__(self):
        self.cards = []

class Rule:
    def can_reveal(self):
        pass
    def can_move_on(self, card):
        pass



d = Deck()
print(d.cards[0].rank + d.cards[0].suit)
d.shuffle()
print(d.cards[0].rank + d.cards[0].suit)
