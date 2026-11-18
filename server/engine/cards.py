"""Registry 45 loại thẻ Exploding Kitty — metadata theo resources/cards_desc/*.txt.

is_action: chơi từ tay trên lượt mình; anytime: chơi được cả ngoài lượt (play_now);
nopeable: có thể bị Nope; wild_cat: feral cat dùng làm mèo bất kỳ trong combo.
"""

from dataclasses import dataclass, field


@dataclass
class Card:
    """Một lá thẻ vật lý (id duy nhất trong ván)."""

    id: str
    type: str
    variant: int
    faceup: bool = False  # riêng implodingkitten: đã lật mặt lên

    def to_dict(self) -> dict:
        d = {"id": self.id, "type": self.type, "variant": self.variant}
        if self.type == "implodingkitten":
            d["faceup"] = self.faceup
        return d


CARD_META = {
    # --- Bom & cứu nguy ---
    "explodingkitten": {"name": "Exploding Kitten", "is_action": False, "nopeable": False},
    "implodingkitten": {"name": "Imploding Kitten", "is_action": False, "nopeable": False},
    "defuse": {"name": "Defuse", "is_action": False, "nopeable": False},
    "streakingkitten": {"name": "Streaking Kitten", "is_action": False, "nopeable": False},
    "zombiekitten": {"name": "Zombie Kitten", "is_action": False, "nopeable": False},
    "godcat": {"name": "Godcat", "is_action": True, "nopeable": True, "anytime": True,
               "as_any_card": True},
    "devilcat": {"name": "Devilcat", "is_action": True, "nopeable": False, "to_playmat": True},
    "barkingkitten": {"name": "Barking Kitten", "is_action": True, "nopeable": False},

    # --- Hành động cơ bản ---
    "skip": {"name": "Skip", "is_action": True, "nopeable": True},
    "superskip": {"name": "Super Skip", "is_action": True, "nopeable": True},
    "shuffle": {"name": "Shuffle", "is_action": True, "nopeable": True},
    "shufflenow": {"name": "Shuffle NOW", "is_action": True, "anytime": True, "nopeable": True},
    "attack2x": {"name": "Attack 2x", "is_action": True, "nopeable": True},
    "targetattack2x": {"name": "Targeted Attack 2x", "is_action": True, "nopeable": True,
                       "needs_target": True},
    "personalattack3x": {"name": "Personal Attack 3x", "is_action": True, "nopeable": True},
    "attackofthedead": {"name": "Attack of the Dead", "is_action": True, "nopeable": True,
                        "needs_dead": True},
    "reverse": {"name": "Reverse", "is_action": True, "nopeable": True},
    "drawfromthebottom": {"name": "Draw From the Bottom", "is_action": True, "nopeable": True},
    "digdeeper": {"name": "Dig Deeper", "is_action": True, "nopeable": True},
    "raisingheck": {"name": "Raising Heck", "is_action": True, "nopeable": True},
    "bury": {"name": "Bury", "is_action": True, "nopeable": True},
    "towerofpower": {"name": "Tower of Power", "is_action": True, "nopeable": True},
    "catomicbomb": {"name": "Catomic Bomb", "is_action": True, "nopeable": True},
    "armageddon": {"name": "Armageddon", "is_action": True, "nopeable": True,
                   "needs_playmat_kitten": True},
    "feralcat": {"name": "Feral Cat", "is_action": False, "nopeable": True, "wild_cat": True},

    # --- Nhìn/xáo deck ---
    "seethefuture3x": {"name": "See the Future 3x", "is_action": True, "nopeable": True},
    "seethefuture5x": {"name": "See the Future 5x", "is_action": True, "nopeable": True},
    "revealthefuture3x": {"name": "Reveal the Future 3x", "is_action": True, "nopeable": True},
    "sharethefuture3x": {"name": "Share the Future 3x", "is_action": True, "nopeable": True},
    "alter3x": {"name": "Alter the Future 3x", "is_action": True, "nopeable": True},
    "alter5x": {"name": "Alter the Future 5x", "is_action": True, "nopeable": True},
    "alter3xnow": {"name": "Alter the Future 3x NOW", "is_action": True, "anytime": True,
                   "nopeable": True},
    "clairvoyance": {"name": "Clairvoyance", "is_action": True, "anytime": True, "nopeable": True},

    # --- Combo / trộm bài ---
    "cat": {"name": "Cat", "is_action": False, "wild_cat": False, "combo_only": True,
            "nopeable": True},
    "favor": {"name": "Favor", "is_action": True, "nopeable": True, "needs_target": True},
    "potluck": {"name": "Potluck", "is_action": True, "nopeable": True},
    "illtakethat": {"name": "I'll Take That", "is_action": True, "nopeable": False,
                    "needs_target": True},
    "mark": {"name": "Mark", "is_action": True, "nopeable": True, "needs_target": True},
    "curseofthecatbutt": {"name": "Curse of the Cat Butt", "is_action": True, "nopeable": True,
                          "needs_target": True},
    "garbagecollection": {"name": "Garbage Collection", "is_action": True, "nopeable": True},
    "graverobber": {"name": "Grave Robber", "is_action": True, "nopeable": True,
                    "needs_dead": True},
    "clone": {"name": "Clone", "is_action": True, "nopeable": True},
    "swaptopandbottom": {"name": "Swap Top and Bottom", "is_action": True, "nopeable": True},
    "nope": {"name": "Nope", "is_action": True, "nopeable": False},

    # --- Hồi sinh ---
    "feedthedead": {"name": "Feed the Dead", "is_action": True, "anytime": True, "nopeable": True,
                    "needs_dead": True},
}

# Godcat không được biến thành các thẻ sau (theo godcat.txt NOTES)
GODCAT_BANNED = {"nope", "explodingkitten", "implodingkitten", "streakingkitten",
                 "barkingkitten", "godcat", "devilcat", "towerofpower"}

# Thứ tự cứu khi rút bom
RESCUE_ORDER = ["defuse", "streakingkitten", "zombiekitten", "godcat"]
