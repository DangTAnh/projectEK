"""Deck: list thẻ, đỉnh = cuối list. Xây từ file desk JSON (resources/desk/*.json)."""

import json
import random
from pathlib import Path

from .cards import Card

DESK_DIR = Path(__file__).resolve().parents[2] / "resources" / "desk"


def available_desks() -> list[str]:
    """Tên các bộ bài có sẵn (resources/desk/*.json)."""
    return sorted(p.stem for p in DESK_DIR.glob("*.json"))


class Deck:
    def __init__(self) -> None:
        self.cards: list[Card] = []  # top = cuối list

    def load_pool(self, name: str = "web") -> None:
        """Đọc pool thẻ thường (không EK) từ resources/desk/{name}.json."""
        data = json.loads((DESK_DIR / f"{name}.json").read_text(encoding="utf-8"))
        for ctype, variants in data["cards"].items():
            for variant, count in variants.items():
                for _ in range(count):
                    self.cards.append(Card(id="", type=ctype, variant=int(variant)))

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def size(self) -> int:
        return len(self.cards)

    def draw_top(self) -> Card | None:
        return self.cards.pop() if self.cards else None

    def draw_bottom(self) -> Card | None:
        return self.cards.pop(0) if self.cards else None

    def peek(self, n: int) -> list[Card]:
        """n thẻ trên cùng theo thứ tự sẽ rút ([0] = đỉnh)."""
        return self.cards[:-n - 1:-1] if n else []

    def insert(self, card: Card, index: int) -> None:
        """Chèn vào vị trí index tính từ đỉnh (0 = lên đỉnh)."""
        self.cards.insert(len(self.cards) - min(index, len(self.cards)), card)

    def insert_bottom(self, card: Card) -> None:
        self.cards.insert(0, card)
