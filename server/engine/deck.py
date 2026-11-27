"""Deck: list thẻ, đỉnh = cuối list. Xây từ file desk JSON (resources/desk/*.json)."""

import json
import random
from pathlib import Path

from .cards import Card

DESK_DIR = Path(__file__).resolve().parents[2] / "resources" / "desk"


_PINNED_DESKS = ("original", "web")


def available_desks() -> list[str]:
    """Tên các bộ bài có sẵn (resources/desk/*.json), ưu tiên original/web trước."""
    stems = {p.stem for p in DESK_DIR.glob("*.json")}
    pinned = [d for d in _PINNED_DESKS if d in stems]
    others = sorted(stems - set(pinned))
    return pinned + others


def desk_catalog() -> list[dict]:
    """Metadata chi tiết cho từng bộ bài trong available_desks()."""
    catalog: list[dict] = []
    for stem in available_desks():
        data = json.loads((DESK_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        cards = data.get("cards", {})
        computed_count = sum(sum(int(cnt) for cnt in v.values()) for v in cards.values())
        default_desc = (
            "Bộ bài cổ điển 56 lá nguyên bản."
            if stem == "original"
            else "Bộ bài tổng hợp toàn bộ lá bài mở rộng trên web."
            if stem == "web"
            else ""
        )
        catalog.append(
            {
                "id": stem,
                "title": data.get("title")
                or (
                    "Original Classic"
                    if stem == "original"
                    else "Web Full Expansion"
                    if stem == "web"
                    else stem
                ),
                "deck_type": data.get("deck_type") or "Standalone",
                "base_merged": bool(data.get("base_merged", False)),
                "card_count": int(data.get("card_count") or computed_count),
                "expansion_card_count": data.get("expansion_card_count"),
                "description": data.get("description") or default_desc,
                "theme_color": data.get("theme_color")
                or ("#e65c2c" if stem == "original" else "#22c55e"),
                "source_url": data.get("source_url"),
            }
        )
    return catalog


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
