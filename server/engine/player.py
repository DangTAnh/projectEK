"""Player: tay bài + trạng thái sống/chết + các flag hiệu ứng lên người."""

from .cards import Card


class Player:
    def __init__(self, name: str) -> None:
        self.name = name
        self.hand: list[Card] = []
        self.alive = True
        self.faceup: list[Card] = []   # thẻ lật công khai trước mặt (barkingkitten)
        self.blind = False             # curseofthecatbutt: không xem tay tới khi rút thành công
        self.marked_id: str | None = None  # mark: 1 lá cụ thể bị đánh dấu (công khai)
        self.illtake_by: str | None = None  # illtakethat: lá rút kế tiếp thuộc về ai
        self.extra_turns = 0           # lượt cộng dồn từ attack/targetattack/attackofthedead
        self.standby_defuse = False    # godcat đặt làm Defuse dự phòng trên bàn

    def has_type(self, ctype: str) -> bool:
        return any(c.type == ctype for c in self.hand)

    def find(self, card_id: str) -> Card | None:
        return next((c for c in self.hand if c.id == card_id), None)
