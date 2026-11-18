"""Game: state machine ván Exploding Kitty — thuần Python đồng bộ, không biết HTTP/WS.

Hiệu ứng thẻ theo resources/cards_desc/*.txt.
Pending/decision points dùng continuation: _ask(kind, owner, data, cont) đặt pending;
Room đẩy respond() -> cont(payload) -> có thể _ask tiếp (chuỗi quyết định nối tiếp).
"""

import random

from .cards import CARD_META, GODCAT_BANNED, RESCUE_ORDER, Card
from .deck import Deck
from .player import Player

BOMBS = {"explodingkitten", "implodingkitten"}


class GameError(Exception):
    """Lệnh không hợp lệ — server trả {type:"error"}, state không đổi."""


class Game:
    def __init__(self, names: list[str], desk: str = "original") -> None:
        self.names = list(names)
        self.desk_name = desk
        self.players: dict[str, Player] = {n: Player(n) for n in names}
        self.order: list[str] = list(names)  # thứ tự lượt
        self.deck = Deck()
        self.grave: list[Card] = []          # top = cuối
        self.stash: list[Card] = []          # Tower of Power: 6 lá dưới vương miện
        self.tower_wearer: str | None = None  # người đang đội Tower of Power
        self.playmat: list[dict] = []        # godcat/devilcat công khai: {name, type}
        self.phase = "playing"
        self.winner: str | None = None
        self.turn_index = 0
        self.direction = 1
        self.turns_left = 1
        self.pending: dict | None = None
        self._cont = None
        self.nope: dict | None = None        # {actor, card, stack:[Card], responded:set, effect}
        self.nope_deadline: float | None = None  # Room gán epoch seconds
        self.revealed: list[Card] = []
        self.private_peeks: dict[str, list[dict]] = {}  # name -> cards chỉ người đó thấy
        self.bomb_watchers: set[str] = set()  # clairvoyance: thấy vị trí bomb trong deck
        self.log: list[str] = []  # tương thích: chỉ dòng công khai
        self.private_log: dict[str, list[str]] = {}  # name -> dòng log chỉ người đó thấy
        self.log_entries: list[tuple[int, str, str | None]] = []  # (seq, text, viewer)
        self.log_seq = 0

    # ---------- helpers ----------

    def _say(self, msg: str, private: str | None = None) -> None:
        self.log_seq += 1
        self.log_entries.append((self.log_seq, msg, private))
        if len(self.log_entries) > 1000:
            del self.log_entries[:-1000]
        if private is None:
            self.log.append(msg)
        else:
            self.private_log.setdefault(private, []).append(msg)

    def announce_desk(self, desk: str) -> None:
        self._say(f"🃏 Bộ bài: {desk}")

    def log_for(self, name: str) -> list[str]:
        """Nhật ký theo thời gian của một người xem: công khai + riêng tư của họ."""
        visible = [text for _, text, viewer in self.log_entries
                   if viewer is None or viewer == name]
        return visible[-30:]

    def alive(self) -> list[Player]:
        return [self.players[n] for n in self.order if self.players[n].alive]

    def current(self) -> Player:
        return self.players[self.order[self.turn_index]]

    def _is_current(self, p: Player) -> bool:
        return self.order[self.turn_index] == p.name

    def _meta(self, ctype: str) -> dict:
        return CARD_META[ctype]

    def _to_grave(self, card: Card) -> None:
        self.grave.append(card)

    def _leave_hand(self, p: Player, card: Card) -> None:
        """Rời tay ở mọi tình huống — gỡ mark nếu đúng lá đó."""
        p.hand.remove(card)
        if p.marked_id == card.id:
            p.marked_id = None
        # Streaking Kitten rời tay (trộm/combo/favor/potluck/...): EK trên tay nổ
        if card.type == "streakingkitten" and self.phase == "playing":
            carried = next((c for c in p.hand if c.type == "explodingkitten"), None)
            if carried is not None:
                self._leave_hand(p, carried)
                self._say(f"💥 {p.name} mất Streaking Kitten — Exploding Kitten trên tay nổ!")
                self._handle_bomb(p, carried, remaining=1, end_after=False)

    def _peek_for(self, name: str, cards: list[Card]) -> None:
        if cards:
            self.private_peeks[name] = [c.to_dict() for c in cards]

    def _check_win(self) -> bool:
        alives = self.alive()
        if len(alives) <= 1:
            self.phase = "ended"
            self.winner = alives[0].name if alives else None
            self.pending = None
            self._cont = None
            self.nope = None
            if self.winner:
                self._say(f"🎉 {self.winner} thắng ván này!")
            return True
        return False

    def _clear_transient(self) -> None:
        self.revealed = []
        self.private_peeks = {}

    def _ask(self, kind: str, owner: str, data: dict, cont) -> None:
        self.pending = {"kind": kind, "owner": owner, "data": data}
        self._cont = cont

    def _require(self, cond: bool, msg: str) -> None:
        if not cond:
            raise GameError(msg)

    def _get(self, name: str) -> Player:
        self._require(name in self.players, f"Không có người chơi {name}")
        return self.players[name]

    def _next_alive(self, p: Player) -> Player | None:
        n = len(self.order)
        idx = self.turn_index
        for _ in range(n):
            idx = (idx + self.direction) % n
            cand = self.players[self.order[idx]]
            if cand.alive:
                return cand
        return None

    def _steal_pick(self, thief: Player, victim_name: str) -> None:
        """Trộm đôi: kẻ trộm xem tay victim và tự chọn lá lấy."""
        victim = self._get(victim_name)
        if victim.name == self.tower_wearer and self.stash:
            self._take_tower_card(thief, victim)
            return
        if not victim.hand:
            self._say(f"{victim_name} hết thẻ — không trộm được.")
            return
        self._ask("pick_card", thief.name,
                  {"source": "victim_hand", "victim": victim_name, "count": len(victim.hand)},
                  lambda r, pl=thief, tg=victim: self._steal_take(pl, tg, r["position"]))

    def _steal_take(self, thief: Player, target: Player, position: int) -> None:
        # thief chỉ gửi vị trí (úp bài) — không biết mặt lá, server tự lấy theo index
        self._require(isinstance(position, int) and 0 <= position < len(target.hand),
                      "Vị trí không hợp lệ")
        card = target.hand[position]
        self._leave_hand(target, card)
        self._receive_card(thief, card)
        self._say(f"{thief.name} trộm 1 thẻ từ tay {target.name}!")

    def _receive_card(self, p: Player, card: Card) -> None:
        """Nhận 1 lá vào tay từ người khác — nếu là bomb thì nổ ngay (phải cứu hoặc chết)."""
        if card.type in BOMBS:
            self._receive_bomb(p, card)
        else:
            p.hand.append(card)

    def _receive_bomb(self, p: Player, bomb: Card, start: int = 0) -> None:
        label = CARD_META[bomb.type]["name"]
        for i in range(start, len(RESCUE_ORDER)):
            t = RESCUE_ORDER[i]
            if not p.has_type(t):
                continue
            if t == "defuse":
                dfuse = next(c for c in p.hand if c.type == "defuse")
                self._leave_hand(p, dfuse)
                self._to_grave(dfuse)
                self._say(f"{p.name} dùng Defuse cho {label} nhận được!")
                self._ask(
                    "pick_index", p.name,
                    {"reason": "defuse_receive", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                    lambda r, b=bomb: self._finish_receive_insert(b, r),
                )
                return
            if t == "streakingkitten":
                self._ask(
                    "yes_no", p.name,
                    {"question": f"Giữ {label} trên tay (bỏ Streaking Kitten)?"},
                    lambda r, b=bomb, pl=p, j=i + 1: (
                        self._streaking_keep_received(pl, b) if r.get("value")
                        else self._receive_bomb(pl, b, start=j)
                    ),
                )
                return
            if t == "zombiekitten":
                self._ask(
                    "yes_no", p.name,
                    {"question": "Dùng Zombie Kitten: chèn bom lại deck và hồi sinh 1 người?"},
                    lambda r, b=bomb, pl=p, j=i + 1: (
                        self._zombie_use_received(pl, b) if r.get("value")
                        else self._receive_bomb(pl, b, start=j)
                    ),
                )
                return
            if t == "godcat":
                self._ask(
                    "yes_no", p.name,
                    {"question": "Dùng Godcat như Defuse?"},
                    lambda r, b=bomb, pl=p, j=i + 1: (
                        self._godcat_defuse_received(pl, b) if r.get("value")
                        else self._receive_bomb(pl, b, start=j)
                    ),
                )
                return
        self._kill(p, bomb=bomb)

    def _streaking_keep_received(self, p: Player, bomb: Card) -> None:
        # streaking.txt: giữ bom MIỄN LÀ streaking còn trên tay — KHÔNG bỏ streaking
        p.hand.append(bomb)
        self._say(f"{p.name} GIỮ {CARD_META[bomb.type]['name']} nhận được nhờ Streaking Kitten!")

    def _zombie_use_received(self, p: Player, bomb: Card) -> None:
        self._zombie_use(p, bomb, 0, False)

    def _godcat_defuse_received(self, p: Player, bomb: Card) -> None:
        self._godcat_defuse(p, bomb, 0, False)

    def _finish_receive_insert(self, bomb: Card, resp: dict) -> None:
        index = max(0, min(int(resp.get("index", 0)), self.deck.size()))
        self.deck.insert(bomb, index)
        self._say(f"{CARD_META[bomb.type]['name']} chèn vào vị trí {index} từ đỉnh.")

    def _defuse_or_die(self, target: Player) -> None:
        dfuse = next((c for c in target.hand if c.type == "defuse"), None)
        if dfuse:
            self._leave_hand(target, dfuse)
            self._to_grave(dfuse)
            self._say(f"{target.name} phải dùng Defuse cho Barking Kitten!")
        else:
            self._say(f"💥 {target.name} không có Defuse trước Barking Kitten!")
            self._kill(target)

    def _kill(self, p: Player, bomb: Card | None = None) -> None:
        p.alive = False
        if bomb is not None:
            self._to_grave(bomb)
        self._say(f"💥 BOOM! {p.name} nổ tung và bị loại!")
        self._check_win()

    # ---------- lifecycle ----------

    def start(self) -> None:
        """Chia bài: pool thường xáo -> mỗi người 4; +1 Defuse/người; thừa về đáy; N-1 bom
        (N bom nếu deck có Streaking Kitten — cho phép 1 người ôm EK)."""
        self.deck.load_pool(self.desk_name)
        # original.json chứa sẵn 20 bom + 6 defuse: tách cả hai, bom do engine tự chia
        defuses = [c for c in self.deck.cards if c.type == "defuse"]
        has_streaking = any(c.type == "streakingkitten" for c in self.deck.cards)
        self.deck.cards = [c for c in self.deck.cards if c.type not in ("defuse", *BOMBS)]
        self.deck.shuffle()

        for name in self.order:  # mỗi người rút 4 từ pool thường
            for _ in range(4):
                card = self.deck.draw_top()
                if card:
                    self.players[name].hand.append(card)

        n = len(self.order)
        for name in self.order:  # mỗi người 1 Defuse
            if defuses:
                self.players[name].hand.append(defuses.pop())
        for d in defuses:  # Defuse thừa về đáy
            self.deck.insert_bottom(d)

        # Streaking Kitten trong pool -> thêm 1 EK (tổng = số người chơi)
        n_bombs = n if has_streaking else n - 1
        ek_variants = [0, 1, 2, 3]
        for _ in range(n_bombs):
            bomb = Card(id="", type="explodingkitten", variant=random.choice(ek_variants))
            self.deck.insert(bomb, random.randint(0, self.deck.size()))

        # Tower of Power stash: 6 lá thường dưới vương miện
        normals = [c for c in self.deck.cards if c.type not in BOMBS][:6]
        for c in normals:
            self.deck.cards.remove(c)
        self.stash = normals

        self._assign_ids()
        self.deck.shuffle()
        self.turn_index = random.randrange(len(self.order))
        self.direction = 1
        self.turns_left = 1
        self.phase = "playing"
        self._say(f"Ván bắt đầu! {self.current().name} đi trước.")

    def _assign_ids(self) -> None:
        seq = 0
        everywhere = list(self.deck.cards) + list(self.stash) + [
            c for p in self.players.values() for c in p.hand]
        for card in everywhere:
            seq += 1
            card.id = f"{card.type}.{card.variant}.{seq}"

    @staticmethod
    def _fuzzy_type(query: str) -> str | None:
        """Match tên bài mơ hồ → card type bằng F1 score (character bigram)."""
        q = query.strip().lower()
        if not q:
            return None
        if q in CARD_META:  # khớp chính xác trước tiên
            return q
        def bigrams(s):
            return [s[i:i + 2] for i in range(len(s) - 1)] or [s]
        qb = set(bigrams(q))
        best, best_score = None, 0.0
        for ctype in CARD_META:
            # thưởng khớp tên hiển thị hoặc type (strip số/nối chữ)
            name = CARD_META[ctype].get("name", ctype).lower()
            for cand in (ctype.lower(), name):
                cb = set(bigrams(cand))
                inter = len(qb & cb)
                if not inter:
                    continue
                prec = inter / len(qb)
                rec = inter / len(cb)
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
                # thưởng nếu query là substring của candidate (gõ "attack" -> attack2x)
                if q in cand:
                    f1 += 0.35
                if f1 > best_score:
                    best, best_score = ctype, f1
        # ngưỡng F1: chấp nhận khi đủ gần
        return best if best_score >= 0.55 else None

    def debug_give(self, name: str, ctype: str, variant: int = 0) -> None:
        """Debug-only: đưa trực tiếp 1 lá vào tay người chơi, không qua luật lượt."""
        p = self._get(name)
        resolved = self._fuzzy_type(ctype)
        self._require(resolved is not None, f"Không tìm thấy thẻ '{ctype}' — gõ lại gần tên hơn")
        # id duy nhất: đếm mọi lá hiện có + 1
        everywhere = len(self.deck.cards) + len(self.stash) + sum(
            len(q.hand) for q in self.players.values())
        card = Card(id=f"{resolved}.{variant}.{everywhere + 1}", type=resolved, variant=variant)
        self._receive_card(p, card)
        self._say(f"[debug] {name} nhận {resolved}")

    def _resolve_godcat(self, as_type: str | None) -> tuple[str, dict]:
        self._require(isinstance(as_type, str) and as_type, "Thiếu loại thẻ muốn hóa thân")
        resolved = self._fuzzy_type(as_type)
        self._require(resolved is not None, f"Không nhận ra thẻ '{as_type}'")
        self._require(resolved not in GODCAT_BANNED, f"Godcat không thể thành {resolved}")
        if resolved != "defuse":
            self._require(CARD_META[resolved].get("is_action"), f"{resolved} không đánh trực tiếp được")
        return resolved, CARD_META[resolved]

    # ---------- commands ----------

    def play_card(self, name: str, card_id: str, as_type: str | None = None) -> None:
        self._clear_transient()
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        self._require(self._is_current(p), "Chưa tới lượt bạn")

        if p.blind:  # curse: chơi mù — server tự chọn lá ngẫu nhiên
            self._require(p.hand, "Bạn không còn thẻ nào")
            card = random.choice(p.hand)
            self._say(f"{name} (bị mù) chơi ngẫu nhiên 1 lá...")
        else:
            card = p.find(card_id)
            self._require(card is not None, "Không có thẻ này trên tay")
        meta = self._meta(card.type)
        if p.blind and not meta.get("is_action"):
            # mù chơi trúng lá không dùng được (nope/cat): lãng phí vào grave
            self._leave_hand(p, card)
            self._to_grave(card)
            self._say(f"{name} (bị mù) lãng phí 1 lá vào graveyard.")
            return

        eff_type = card.type
        if meta.get("as_any_card"):  # godcat biến thành thẻ khác
            eff_type, meta = self._resolve_godcat(as_type)
        else:
            self._require(meta.get("is_action"), f"{meta['name']} không đánh trực tiếp được")
            self._require(card.type != "nope", "Nope chỉ dùng trong cửa sổ Nope")
        if meta.get("needs_dead"):
            self._require(any(not self.players[n2].alive for n2 in self.order),
                          "Cần có người đã chết")
        if meta.get("needs_playmat_kitten"):
            mat_types = {e["card"]["type"] for e in self.playmat}
            self._require({"godcat", "devilcat"} <= mat_types,
                          "Armageddon cần cả Godcat và Devilcat trên bàn")
        # Bury: không dùng được khi đang dính bẫy I'll Take That
        if eff_type == "bury":
            self._require(p.illtake_by is None,
                          "Bạn đang bị I'll Take That — không dùng được Bury.")

        # combo cat pair (đánh đơn lá mèo không được — dùng play_combo)
        self._require(not meta.get("combo_only"), "Mèo phải đánh theo cặp/bộ ba (combo)")
        clone_beneath = self.grave[-1] if eff_type == "clone" and self.grave else None

        # rời tay: godcat/devilcat lên playmat, barking có thể lên mặt bàn, còn lại vào grave
        self._leave_hand(p, card)
        if card.type == "godcat":
            self.playmat.append({"name": name, "card": card.to_dict()})
            self._say(f"{name} dùng Godcat như {CARD_META[eff_type]['name']}!")
        elif card.type == "devilcat":
            self.playmat.append({"name": name, "card": card.to_dict()})
            self._say(f"{name} đặt Devilcat lên bàn — Armageddon đã sẵn sàng...")
        elif card.type == "barkingkitten":
            pass  # xử lý trong _apply_barking (có thể về faceup)
        else:
            self._to_grave(card)

        if eff_type == "clone":
            effect = lambda: self._apply_clone(p, card, clone_beneath)  # noqa: E731
        elif card.type == "barkingkitten":
            effect = lambda: self._apply_barking(p, card)  # noqa: E731
        else:
            effect = lambda: self._apply_effect(p, eff_type, card)  # noqa: E731

        if meta.get("nopeable") and len([a for a in self.alive() if a.name != name]) > 0:
            self.nope = {"actor": name, "card": card, "stack": [], "responded": set(),
                         "effect": effect}
            return  # Room mở timer 5s rồi gọi resolve_nope()
        effect()

    def play_combo(self, name: str, combo: str, card_ids: list) -> None:
        """Combo: pair (2 lá cùng tên) hoặc three (3 lá cùng tên) — feralcat là wildcard."""
        self._clear_transient()
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive and self._is_current(p), "Chưa tới lượt bạn")
        self._require(not p.blind, "Bị mù không đánh combo được")
        self._require(combo in ("pair", "three"), "Combo không hợp lệ")
        need = 2 if combo == "pair" else 3
        self._require(len(card_ids) == need, f"Cần chọn đúng {need} lá")
        cards = []
        for cid in card_ids:
            card = p.find(cid)
            self._require(card is not None, f"Không có thẻ {cid}")
            cards.append(card)
        core_types = [c.type for c in cards if c.type not in ("feralcat", "clone")]
        if core_types:
            self._require(len(set(core_types)) == 1, "Các lá không cùng loại")
            # Feral Cat / Clone chỉ thay thế lá Cat, không dùng cho Shuffle/Attack/...
            if any(c.type in ("feralcat", "clone") for c in cards):
                self._require(core_types[0] == "cat", "Feral Cat/Clone chỉ thay thế lá Cat")
        named = core_types[0] if core_types else "feralcat"

        for c in cards:
            self._leave_hand(p, c)
            self._to_grave(c)
        self._say(f"{name} đánh bộ {'đôi' if combo == 'pair' else 'ba'} {CARD_META[named]['name']}!")

        if combo == "pair":
            def effect_pair():
                cands = [o.name for o in self.alive()
                         if o.name != p.name and (o.hand or (o.name == self.tower_wearer and self.stash))]
                if not cands:
                    self._say("Không có ai để ăn trộm.")
                    return
                self._ask("pick_player", p.name, {"candidates": cands, "reason": "steal"},
                          lambda r, pl=p: self._steal_pick(pl, r["player"]))
            effect = effect_pair
        else:
            def effect_three():
                cands = [o.name for o in self.alive()
                         if o.name != p.name and (o.hand or (o.name == self.tower_wearer and self.stash))]
                if not cands:
                    return
                self._ask("pick_player", p.name, {"candidates": cands, "reason": "call_card"},
                          lambda r, pl=p: self._three_call(pl, r["player"]))
            effect = effect_three

        self.nope = {"actor": name, "card": cards[0], "stack": [], "responded": set(),
                     "effect": effect}

    def _take_tower_card(self, taker: Player, wearer: Player) -> None:
        card = random.choice(self.stash)
        self.stash.remove(card)
        self._receive_card(taker, card)
        self._say(f"{taker.name} trộm mù 1 thẻ từ Tower of Power của {wearer.name}!")

    def _three_call(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        if target.name == self.tower_wearer and self.stash:
            self._take_tower_card(p, target)
            return
        if not target.hand:
            self._say(f"{target_name} hết thẻ — không trộm được.")
            return
        # kẻ trộm nhập tên bài tự do (fuzzy match) — có trong tay victim thì lấy, không thì bỏ
        self._ask("input_card", p.name,
                  {"victim": target_name, "reason": "three_called"},
                  lambda r, pl=p, tg=target: self._three_resolve(pl, tg, r.get("text", "")))

    def _three_resolve(self, p: Player, target: Player, query: str) -> None:
        ctype = self._fuzzy_type(query)
        if ctype is None:
            self._say(f"Không nhận ra tên bài '{query}'.")
            return
        # feralcat chỉ thay bài Cat — gọi "skip"/... không moi được feral của victim.
        cards = [c for c in target.hand
                 if c.type == ctype or (c.type == "feralcat" and ctype in ("cat", "feralcat"))]
        if not cards:
            self._say(f"{target.name} không có {CARD_META[ctype]['name']} — chẳng nhận được gì.")
            return
        card = cards[0]
        self._leave_hand(target, card)
        self._receive_card(p, card)
        self._say(f"{target.name} đưa {p.name} 1 thẻ.")

    def draw(self, name: str) -> None:
        self._clear_transient()
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        self._require(self._is_current(p), "Chưa tới lượt bạn")
        self._resolve_draw(p, "top", 1, end_after=True)

    def play_now(self, name: str, card_id: str, as_type: str | None = None) -> None:
        """Thẻ anytime: shufflenow, clairvoyance, alter3xnow, feedthedead, godcat-as-card."""
        self._clear_transient()
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        card = p.find(card_id)
        self._require(card is not None, "Không có thẻ này trên tay")
        meta = self._meta(card.type)
        self._require(meta.get("anytime") or meta.get("as_any_card"),
                      f"{meta['name']} không phải thẻ anytime")
        # Người chết chỉ còn Clairvoyance và Feed the Dead theo luật.
        self._require(p.alive or card.type in ("clairvoyance", "feedthedead"),
                      "Người chết chỉ dùng được Clairvoyance/Feed the Dead")

        if meta.get("as_any_card"):
            eff_type, eff_meta = self._resolve_godcat(as_type)
            if eff_meta.get("needs_dead"):
                self._require(any(not self.players[n2].alive for n2 in self.order),
                              "Cần có người đã chết")
            if eff_meta.get("needs_playmat_kitten"):
                mat_types = {e["card"]["type"] for e in self.playmat}
                self._require({"godcat", "devilcat"} <= mat_types,
                              "Armageddon cần cả Godcat và Devilcat trên bàn")
            clone_beneath = self.grave[-1] if eff_type == "clone" and self.grave else None
            self._leave_hand(p, card)
            self.playmat.append({"name": name, "card": card.to_dict()})
            self._say(f"{name} dùng Godcat như {eff_meta['name']} (ngoài lượt)!")
            if eff_type == "clone":
                effect = lambda: self._apply_clone(p, card, clone_beneath)  # noqa: E731
            elif eff_type == "personalattack3x":
                # Không cướp lượt hiện tại: cộng lượt thưởng cho chính người dùng Godcat.
                effect = lambda: self._godcat_personal(p)  # noqa: E731
            else:
                effect = lambda: self._apply_effect(p, eff_type, card)  # noqa: E731
            meta = eff_meta
        else:
            self._leave_hand(p, card)
            self._to_grave(card)
            self._say(f"{name} chơi {meta['name']} (ngoài lượt)!")
            effect = lambda: self._apply_anytime(p, card.type)  # noqa: E731
        if meta.get("nopeable") and len([a for a in self.alive() if a.name != name]) > 0:
            self.nope = {"actor": name, "card": card, "stack": [], "responded": set(),
                         "effect": effect}
            return
        effect()

    def _godcat_personal(self, p: Player) -> None:
        p.extra_turns += 2
        self._say(f"{p.name} dùng Godcat như Personal Attack — thêm 2 lượt thưởng!")

    def _pending_for(self, name: str) -> dict | None:
        """Chỉ owner mới thấy chi tiết pending; người khác chỉ thấy marker."""
        pending = self.pending
        if pending is None or pending.get("owner") == name:
            return pending
        data = pending.get("data") or {}
        return {
            "kind": pending.get("kind"),
            "owner": pending.get("owner"),
            "data": {"reason": data.get("reason")},
        }

    def _validate_pending_response(self, pending: dict, payload: dict) -> None:
        kind = pending.get("kind")
        data = pending.get("data") or {}
        if not isinstance(data, dict):
            raise GameError("Quyết định không hợp lệ")
        if kind == "pick_index":
            index = payload.get("index")
            if isinstance(index, bool) or not isinstance(index, int):
                raise GameError("Vị trí phải là số nguyên")
            low, high = data.get("min", 0), data.get("max", 0)
            if not isinstance(low, int) or not isinstance(high, int):
                raise GameError("Quyết định không hợp lệ")
            self._require(low <= index <= high, "Vị trí không hợp lệ")
        elif kind == "yes_no":
            if not isinstance(payload.get("value"), bool):
                raise GameError("Cần trả lời có/không")
        elif kind == "pick_player":
            target_name = payload.get("player")
            candidates = data.get("candidates")
            if not isinstance(target_name, str) or not isinstance(candidates, list):
                raise GameError("Người chơi không hợp lệ")
            self._require(target_name in candidates, "Người chơi không hợp lệ")
            self._validate_pending_target(pending, target_name)
        elif kind == "pick_card":
            source = data.get("source")
            if source == "victim_hand":
                victim = self._get(data.get("victim", ""))
                position = payload.get("position")
                if isinstance(position, bool) or not isinstance(position, int):
                    raise GameError("Vị trí không hợp lệ")
                self._require(0 <= position < len(victim.hand), "Vị trí không hợp lệ")
            elif source == "own_hand":
                owner = self._get(pending.get("owner", ""))
                self._require(owner.alive, "Bạn đã chết")
                card_id = payload.get("card_id")
                if not isinstance(card_id, str) or owner.find(card_id) is None:
                    raise GameError("Thẻ không có trong tay bạn")
            else:
                raise GameError("Quyết định không hợp lệ")
        elif kind == "input_card":
            if not isinstance(payload.get("text"), str):
                raise GameError("Tên thẻ không hợp lệ")
        elif kind == "reorder":
            order = payload.get("order")
            expected = [c.get("id") for c in data.get("cards", [])]
            if (not isinstance(order, list) or not expected
                    or len(order) != len(expected)
                    or any(not isinstance(item, str) for item in order)
                    or set(order) != set(expected)):
                raise GameError("Danh sách reorder không khớp các thẻ trên cùng")
        else:
            raise GameError("Quyết định không hợp lệ")

    def _validate_pending_target(self, pending: dict, target_name: str) -> None:
        data = pending.get("data") or {}
        reason = data.get("reason")
        owner = pending.get("owner")
        target = self._get(target_name)
        if reason == "revive":
            self._require(not target.alive, "Người chơi này chưa chết")
            return
        self._require(target.alive, "Người chơi này đã chết")
        self._require(target.name != owner, "Không thể chọn chính mình")
        if reason == "favor":
            self._require(target.hand, "Người này không còn thẻ")
        elif reason == "mark":
            self._require(target.hand, "Người này không còn thẻ")
        elif reason == "illtakethat":
            self._require(not target.illtake_by, "Người này đã có bẫy")
        elif reason in ("steal", "call_card"):
            has_hand = bool(target.hand)
            has_crown = target.name == self.tower_wearer and bool(self.stash)
            self._require(has_hand or has_crown, "Người này không còn gì để lấy")

    def respond(self, name: str, payload: dict) -> None:
        self._clear_transient()
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is not None, "Không có quyết định đang chờ")
        self._require(self.pending["owner"] == name, "Không phải lượt quyết định của bạn")
        self._require(isinstance(payload, dict), "Payload quyết định không hợp lệ")
        self._validate_pending_response(self.pending, payload)
        snap = self.pending
        cont = self._cont
        self.pending = None
        self._cont = None
        try:
            cont(payload)
        except GameError:
            self.pending, self._cont = snap, cont  # chọn sai -> được chọn lại
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            self.pending, self._cont = snap, cont  # payload hỏng không được xóa pending
            raise GameError("Payload quyết định không hợp lệ") from exc

    def stack_nope(self, name: str) -> None:
        self._clear_transient()
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        self._require(self.phase == "playing", "Ván đã kết thúc")
        self._require(name != self.nope["actor"], "Không nope được chính mình")
        self._require(name not in self.nope["responded"], "Bạn đã phản hồi rồi")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        nope_card = next((c for c in p.hand if c.type == "nope"), None)
        self._require(nope_card is not None, "Bạn không có thẻ Nope")
        self._leave_hand(p, nope_card)
        self.nope["stack"].append(nope_card)
        self.nope["responded"].add(name)
        self._say(f"{name} tung Nope! ({len(self.nope['stack'])} chồng)")

    def pass_nope(self, name: str) -> None:
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        self._require(name != self.nope["actor"], "Actor không cần phản hồi")
        self._require(name not in self.nope["responded"], "Bạn đã phản hồi rồi")
        self._get(name)
        self.nope["responded"].add(name)

    def nope_all_responded(self) -> bool:
        others = [p.name for p in self.alive() if p.name != self.nope["actor"]]
        return all(n in self.nope["responded"] for n in others)

    def resolve_nope(self) -> None:
        """Đóng cửa sổ nope: số Nope lẻ => hành động bị hủy; chẵn => hiệu ứng chạy."""
        self._clear_transient()
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        noped = len(self.nope["stack"]) % 2 == 1
        actor_name, card, stack, effect = (
            self.nope["actor"], self.nope["card"], self.nope["stack"], self.nope["effect"])
        label = CARD_META.get(card.type, {}).get("name", card.type)
        self.nope = None
        self.nope_deadline = None
        for c in stack:
            self._to_grave(c)
        if noped:
            self._say(f"❌ {label} của {actor_name} bị Nope!")
            return
        effect()

    # ---------- turn flow ----------

    def _end_turn(self, drew: bool, force: bool = False) -> None:
        if force:
            self.turns_left = 0
        else:
            self.turns_left -= 1
        if self.turns_left <= 0:
            self._advance()

    def _advance(self) -> None:
        nxt = self._next_alive(self.current())
        if nxt is None:
            self._check_win()
            return
        self.turn_index = self.order.index(nxt.name)
        self.turns_left = 1 + nxt.extra_turns
        nxt.extra_turns = 0
        self._say(f"— Tới lượt {nxt.name} ({self.turns_left} lượt)")

    # ---------- draw resolution ----------

    def _take_from_deck(self, source: str) -> Card | None:
        card = self.deck.draw_bottom() if source == "bottom" else self.deck.draw_top()
        if card is None and self.grave:  # deck cạn: xáo grave thành deck mới
            self.deck.cards = self.grave[:]
            self.grave = []
            self.deck.shuffle()
            self._say("Deck cạn — xáo graveyard thành deck mới.")
            card = self.deck.draw_bottom() if source == "bottom" else self.deck.draw_top()
        return card

    def _resolve_draw(self, p: Player, source: str, remaining: int, end_after: bool) -> None:
        card = self._take_from_deck(source)
        if card is None:
            self._say("Không còn thẻ để rút.")
            if end_after:
                self._end_turn(drew=False)
            return

        # I'll Take That: chặn lá rút kế tiếp của target
        if p.illtake_by:
            actor = self.players.get(p.illtake_by)
            p.illtake_by = None
            if actor and actor.alive and actor is not p:
                if card.type == "explodingkitten":
                    self._say(f"{p.name} rút phải bom nhưng bị {actor.name} chặn lấy!")
                    self._handle_bomb(actor, card, remaining=1, end_after=False)
                    if self.phase == "playing":
                        self._after_one_draw(p, remaining, end_after)
                    return
                if card.type != "implodingkitten":  # ponytail: imploding không intercept
                    actor.hand.append(card)
                    self._say(f"{p.name} rút thẻ nhưng bị {actor.name} giật mất!")
                    self._after_one_draw(p, remaining, end_after)
                    return

        ctype = card.type
        if ctype in BOMBS:
            if ctype == "implodingkitten" and not card.faceup:
                self._handle_imploding_first(p, card, remaining, end_after)
            else:
                self._handle_bomb(p, card, remaining, end_after)
            return

        # thẻ thường vào tay
        p.hand.append(card)
        p.blind = False  # rút thành công không nổ -> khỏi mù
        self._say(f"Bạn rút {CARD_META[ctype]['name']}", private=p.name)
        self._after_one_draw(p, remaining, end_after)

    def _after_one_draw(self, p: Player, remaining: int, end_after: bool) -> None:
        if self.phase != "playing":
            return
        if not p.alive:
            if self._is_current(p):
                self._advance()
            return
        if remaining > 1:
            self._resolve_draw(p, "top", remaining - 1, end_after)
        elif end_after:
            self._end_turn(drew=True)

    def _handle_imploding_first(self, p: Player, bomb: Card, remaining: int,
                                end_after: bool) -> None:
        """Lần đầu rút Imploding Kitten (mặt dưới): đặt lại vào deck MẶT LÊN, không tốn Defuse."""
        bomb.faceup = True
        self.revealed = [bomb]
        self._say(f"😼 {p.name} rút phải Imploding Kitten — đặt lại vào deck MẶT LÊN!")
        self._ask(
            "pick_index", p.name,
            {"reason": "imploding", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
            lambda r, b=bomb, pl=p, rem=remaining, ea=end_after: self._finish_insert(pl, b, r, rem, ea),
        )

    def _handle_bomb(self, p: Player, bomb: Card, remaining: int, end_after: bool,
                     start: int = 0) -> None:
        label = CARD_META[bomb.type]["name"]
        # Imploding Kitten MẶT NGỬA: nổ ngay, không Defuse/Streaking/Zombie/Godcat cứu được
        if bomb.type == "implodingkitten" and bomb.faceup:
            self._say(f"😼 {p.name} rút phải Imploding Kitten MẶT NGỬA — nổ ngay, không cứu được!")
            self._kill(p, bomb=bomb)
            self._after_one_draw(p, remaining, end_after)
            return
        for i in range(start, len(RESCUE_ORDER)):
            t = RESCUE_ORDER[i]
            if not p.has_type(t):
                continue
            if t == "defuse":
                dfuse = next(c for c in p.hand if c.type == "defuse")
                self._leave_hand(p, dfuse)
                self._to_grave(dfuse)
                self._say(f"{p.name} dùng Defuse cho {label}!")
                if bomb.type == "implodingkitten":
                    self.deck.insert(bomb, 0)  # lên đỉnh
                    self._say("Imploding Kitten đặt lên đỉnh deck.")
                    self._after_one_draw(p, remaining, end_after)
                else:
                    self._ask_pick_insert(p, bomb, "defuse", remaining, end_after)
                return
            if t == "streakingkitten":
                self._ask(
                    "yes_no", p.name,
                    {"question": f"Giữ {label} trên tay (bỏ Streaking Kitten)?"},
                    lambda r, b=bomb, pl=p, rem=remaining, ea=end_after, j=i + 1: (
                        self._streaking_keep(pl, b, rem, ea) if r.get("value")
                        else self._handle_bomb(pl, b, rem, ea, start=j)
                    ),
                )
                return
            if t == "zombiekitten":
                self._ask(
                    "yes_no", p.name,
                    {"question": "Dùng Zombie Kitten: chèn bom lại deck và hồi sinh 1 người?"},
                    lambda r, b=bomb, pl=p, rem=remaining, ea=end_after, j=i + 1: (
                        self._zombie_use(pl, b, rem, ea) if r.get("value")
                        else self._handle_bomb(pl, b, rem, ea, start=j)
                    ),
                )
                return
            if t == "godcat":
                self._ask(
                    "yes_no", p.name,
                    {"question": "Dùng Godcat như Defuse?"},
                    lambda r, b=bomb, pl=p, rem=remaining, ea=end_after, j=i + 1: (
                        self._godcat_defuse(pl, b, rem, ea) if r.get("value")
                        else self._handle_bomb(pl, b, rem, ea, start=j)
                    ),
                )
                return
        self._kill(p, bomb=bomb)
        self._after_one_draw(p, remaining, end_after)

    def _ask_pick_insert(self, p: Player, bomb: Card, reason: str,
                         remaining: int, end_after: bool) -> None:
        self._ask(
            "pick_index", p.name,
            {"reason": reason, "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
            lambda r, b=bomb, pl=p, rem=remaining, ea=end_after: self._finish_insert(pl, b, r, rem, ea),
        )

    def _finish_insert(self, p: Player, bomb: Card, resp: dict,
                       remaining: int, end_after: bool, then=None) -> None:
        index = max(0, min(int(resp.get("index", 0)), self.deck.size()))
        self.deck.insert(bomb, index)
        self._say(f"{CARD_META[bomb.type]['name']} chèn vào vị trí {index} từ đỉnh.")
        if then:
            then(p, remaining, end_after)
            return
        self._after_one_draw(p, remaining, end_after)

    def _streaking_keep(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        # streaking.txt: giữ bom MIỄN LÀ streaking còn trên tay — KHÔNG bỏ streaking
        p.hand.append(bomb)
        self._say(f"{p.name} GIỮ {CARD_META[bomb.type]['name']} trên tay nhờ Streaking Kitten!")
        self._after_one_draw(p, remaining, end_after)

    def _zombie_use(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        zomb = next(c for c in p.hand if c.type == "zombiekitten")
        self._leave_hand(p, zomb)
        self._to_grave(zomb)
        self._say(f"🧟 {p.name} dùng Zombie Kitten — bom chèn lại deck!")
        self._ask(
            "pick_index", p.name,
            {"reason": "zombie", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
            lambda r, b=bomb, pl=p, rem=remaining, ea=end_after: (
                self._finish_insert(pl, b, r, rem, ea, then=self._zombie_revive)),
        )

    def _zombie_revive(self, p: Player, remaining: int, end_after: bool) -> None:
        dead = [n for n in self.order if not self.players[n].alive]
        if not dead:
            self._after_one_draw(p, remaining, end_after)
            return
        self._ask(
            "pick_player", p.name, {"candidates": dead, "reason": "revive"},
            lambda r, pl=p, rem=remaining, ea=end_after: self._finish_revive(pl, r["player"], rem, ea),
        )

    def _finish_revive(self, p: Player, target_name: str, remaining: int, end_after: bool) -> None:
        self._get(target_name).alive = True
        self._say(f"👻 {target_name} hồi sinh!")
        self._after_one_draw(p, remaining, end_after)

    def _godcat_defuse(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        god = next(c for c in p.hand if c.type == "godcat")
        self._leave_hand(p, god)
        self.playmat.append({"name": p.name, "card": god.to_dict()})
        self._say(f"{p.name} dùng Godcat như Defuse!")
        self._ask_pick_insert(p, bomb, "godcat_defuse", remaining, end_after)

    # ---------- effects ----------

    def _apply_effect(self, p: Player, eff_type: str, card: Card) -> None:
        if eff_type == "barkingkitten":
            self._apply_barking(p, card)
            return
        t = eff_type

        if t == "defuse":
            self._require(card.type in ("godcat", "clone"), "Defuse không đánh trực tiếp được")
            self._say(f"{p.name} giữ {CARD_META[card.type]['name']} như Defuse dự phòng trên bàn.")
            return
        if t in ("skip", "superskip"):
            self._end_turn(drew=False, force=(t == "superskip"))
        elif t == "shuffle" or t == "shufflenow":
            self.deck.shuffle()
            self._say("Deck được xáo.")
        elif t == "clairvoyance":
            self.bomb_watchers.add(p.name)
            self._say(f"{p.name} mở con mắt tiên tri — thấy vị trí các quả bom trong deck!")
        elif t == "alter3xnow":
            self._ask_reorder(p, 3, then=lambda: None)
        elif t == "attack2x":
            nxt = self._next_alive(p)
            if nxt:
                # targetattack.txt: nạn nhân gánh lượt còn dư + 2 (chồng attack: 4 rồi 6...).
                nxt.extra_turns += self.turns_left
                self._say(f"{nxt.name} nhận tổng cộng {1 + nxt.extra_turns} lượt!")
            self._end_turn(drew=False, force=True)
        elif t == "targetattack2x":
            cands = [o.name for o in self.alive() if o.name != p.name]
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "targetattack"},
                      lambda r, pl=p: self._do_targetattack(pl, r["player"]))
        elif t == "personalattack3x":
            # Lượt hiện tại đã tính là lượt đầu, chỉ cần thêm 2 lượt nữa để tổng là 3.
            self.turns_left += 2
            self._say(f"{p.name} tự tấn công — tổng cộng 3 lượt liên tiếp!")
        elif t == "attackofthedead":
            dead = sum(1 for n in self.order if not self.players[n].alive)
            nxt = self._next_alive(p)
            if nxt:
                # lượt còn dư + 3 mỗi người chết (T=1, D=1 -> tổng 3 như cũ).
                nxt.extra_turns += self.turns_left + 3 * dead - 2
                self._say(f"{nxt.name} bị ép tổng cộng {1 + nxt.extra_turns} lượt ({dead} người chết x 3)!")
            self._end_turn(drew=False, force=True)
        elif t == "reverse":
            self.direction *= -1
            self._say("Chiều lượt ĐẢO NGƯỢC! Hết lượt không rút.")
            self._end_turn(drew=False)  # giống skip: chỉ hết 1 trong n lượt
        elif t == "drawfromthebottom":
            self._resolve_draw(p, "bottom", 1, end_after=True)
        elif t == "seethefuture3x":
            self._peek_for(p.name, self.deck.peek(3))
            self._say(f"{p.name} nhìn trộm 3 thẻ trên cùng.")
        elif t == "seethefuture5x":
            self._peek_for(p.name, self.deck.peek(5))
            self._say(f"{p.name} nhìn trộm 5 thẻ trên cùng.")
        elif t == "revealthefuture3x":
            self.revealed = self.deck.peek(3)
            self._say("3 thẻ trên cùng bị lật cho cả bàn!")
        elif t == "sharethefuture3x":
            self._ask_reorder(p, 3, then=lambda pl=p: self._share_show(pl))
        elif t in ("alter3x", "alter5x"):
            self._ask_reorder(p, 3 if t == "alter3x" else 5, then=lambda: None)
        elif t == "digdeeper":
            card_dug = self._take_from_deck("top")
            if card_dug is None:
                self._end_turn(drew=False)
                return
            self._peek_for(p.name, [card_dug])
            self._ask(
                "yes_no", p.name, {"question": f"Giữ lá vừa đào ({'ẩn'})?"},
                lambda r, pl=p, cd=card_dug: self._dig_choice(pl, cd, bool(r.get("value"))),
            )
        elif t == "raisingheck":
            card_h = self._take_from_deck("bottom")
            if card_h is None:
                self._end_turn(drew=False, force=True)
                return
            self._peek_for(p.name, [card_h])
            self._ask(
                "yes_no", p.name, {"question": "Giữ lá đáy vừa lôi lên?"},
                lambda r, pl=p, ch=card_h: self._heck_choice(pl, ch, bool(r.get("value"))),
            )
        elif t == "bury":
            buried = self._take_from_deck("top")
            if buried is None:
                self._end_turn(drew=False)
                return
            self._peek_for(p.name, [buried])
            self._ask(
                "pick_index", p.name,
                {"reason": "bury", "min": 0, "max": self.deck.size(), "card": buried.to_dict()},
                lambda r, pl=p, b=buried: self._bury_place(pl, b, r),
            )
        elif t == "towerofpower":
            # Người chơi đội vương miện; stash ở yên trong crown, không vào tay.
            self.tower_wearer = p.name
            self.deck.insert(card, random.randint(0, self.deck.size()))
            self.deck.shuffle()
            self._say(f"{p.name} đội Tower of Power — stash vẫn nằm dưới vương miện ({len(self.stash)} lá).")
        elif t == "armageddon":
            self._do_armageddon(p)
        elif t == "favor":
            cands = [o.name for o in self.alive()
                     if o.name != p.name and (o.hand or (o.name == self.tower_wearer and self.stash))]
            if not cands:
                self._say("Không có ai có thẻ để xin.")
                return
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "favor"},
                      lambda r, pl=p: self._do_favor_pick(pl, r["player"]))
        elif t == "potluck":
            idx = self.order.index(p.name)
            step = self.direction
            givers = []
            n = len(self.order)
            for k in range(n):
                cand = self.players[self.order[(idx + step * k) % n]]
                if cand.alive and cand.hand:
                    givers.append(cand.name)
            self._chain_potluck(p, givers)
        elif t == "illtakethat":
            cands = [o.name for o in self.alive()
                     if o.name != p.name and not o.illtake_by]
            if not cands:
                self._say("Không có ai trống để đặt bẫy I'll Take That.")
                return
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "illtakethat"},
                      lambda r, pl=p: self._do_illtake(pl, r["player"]))
        elif t == "mark":
            cands = [o.name for o in self.alive() if o.name != p.name and o.hand]
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "mark"},
                      lambda r, pl=p: self._do_mark(pl, r["player"]))
        elif t == "curseofthecatbutt":
            cands = [o.name for o in self.alive() if o.name != p.name]
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "curse"},
                      lambda r: self._do_curse(r["player"]))
        elif t == "garbagecollection":
            participants = [p.name] if p.hand else []
            participants.extend(o.name for o in self.alive()
                                if o.name != p.name and o.hand)
            self._chain_into_deck(participants, then_shuffle=True)
        elif t == "graverobber":
            dead_with_cards = [n for n in self.order
                              if not self.players[n].alive and self.players[n].hand]
            if not dead_with_cards:
                self._say("Không người chết nào còn bài.")
                return
            self._chain_into_deck(dead_with_cards, then_shuffle=True)
        elif t == "feedthedead":
            self._do_feed(p)
        elif t == "catomicbomb":
            # catomicbomb.txt: chỉ Exploding Kittens — Imploding ở yên trong deck
            bombs_in_deck = [c for c in self.deck.cards if c.type == "explodingkitten"]
            rest = [c for c in self.deck.cards if c.type != "explodingkitten"]
            random.shuffle(rest)
            self.revealed = list(bombs_in_deck)
            self.deck.cards = rest + bombs_in_deck  # mọi bom chồng lên đỉnh
            self._say(f"💣 CATOMIC BOMB! {len(bombs_in_deck)} quả bom lộ diện và xếp chồng lên đỉnh deck!")
            self._end_turn(drew=False, force=True)
        elif t == "swaptopandbottom":
            if self.deck.size() >= 2:
                self.deck.cards[0], self.deck.cards[-1] = self.deck.cards[-1], self.deck.cards[0]
                self._say("Top ↔ Bottom deck hoán đổi úp (không ai được xem).")
        else:
            self._say(f"{CARD_META[t]['name']} không có hiệu ứng (chưa cài đặt).")

    def _apply_anytime(self, actor: Player, ctype: str) -> None:
        if ctype == "shufflenow":
            self.deck.shuffle()
            self._say("Deck được xáo (NOW).")
        elif ctype == "clairvoyance":
            self.bomb_watchers.add(actor.name)
            self._say(f"{actor.name} mở con mắt tiên tri — thấy vị trí các quả bom trong deck!")
        elif ctype == "alter3xnow":
            self._ask_reorder(actor, 3, then=lambda: None)
        elif ctype == "feedthedead":
            self._do_feed(actor)

    def _apply_barking(self, p: Player, card: Card) -> None:
        holder = next((o for o in self.alive()
                       if o.name != p.name and o.has_type("barkingkitten")), None)
        faceup_owner = None
        if holder is None:
            faceup_owner = next((o for o in self.alive()
                                 if o.name != p.name and o.faceup
                                 and any(c.type == "barkingkitten" for c in o.faceup)), None)
        if holder is None and faceup_owner is None:
            mine = next((c for c in p.faceup if c.type == "barkingkitten"), None)
            if mine is not None:
                # có cả đôi -> chọn bất kỳ ai làm mục tiêu; bỏ cả hai lá sau resolve
                self._to_grave(card)
                p.faceup.remove(mine)
                self._to_grave(mine)
                cands = [o.name for o in self.alive() if o.name != p.name]
                self._ask("pick_player", p.name, {"candidates": cands, "reason": "barking"},
                          lambda r: self._defuse_or_die(self._get(r["player"])))
                return
            # không ai có lá kia: lá nằm lật trước mặt
            p.faceup.append(card)
            self._say(f"{p.name} đặt Barking Kitten lật trước mặt, chờ lá kia...")
            return
        target = holder or faceup_owner
        self._to_grave(card)
        if holder:
            bk = next(c for c in holder.hand if c.type == "barkingkitten")
            self._leave_hand(holder, bk)
            self._to_grave(bk)
        if faceup_owner:
            fk = next(c for c in faceup_owner.faceup if c.type == "barkingkitten")
            faceup_owner.faceup.remove(fk)
            self._to_grave(fk)
        self._say(f"🐶 Barking Kittens gặp nhau — {target.name} phải Defuse hoặc nổ!")
        self._defuse_or_die(target)

    def _apply_clone(self, p: Player, card: Card, beneath: Card | None = None) -> None:
        if beneath is None or beneath.type == "clone":
            self._say("Clone vô hiệu — không có thẻ hợp lệ bên dưới.")
            return
        if beneath.type == "armageddon":
            mat_types = {e["card"]["type"] for e in self.playmat}
            if not ({"godcat", "devilcat"} <= mat_types):
                self._say("Clone vô hiệu — Armageddon cần cả Godcat và Devilcat trên bàn.")
                return
        self._say(f"Clone hóa thành {CARD_META[beneath.type]['name']}!")
        self._apply_effect(p, beneath.type, card)  # lá vật lý là Clone, chỉ mượn hiệu ứng

    def _do_armageddon(self, p: Player) -> None:
        god_index = next(i for i, e in enumerate(self.playmat)
                         if e["card"]["type"] == "godcat")
        devil_index = next(i for i, e in enumerate(self.playmat)
                           if e["card"]["type"] == "devilcat")
        god_entry = self.playmat.pop(god_index)
        if devil_index > god_index:
            devil_index -= 1
        devil_entry = self.playmat.pop(devil_index)
        god_data, devil_data = god_entry["card"], devil_entry["card"]
        dealt = [
            Card(id=god_data["id"], type="godcat", variant=god_data["variant"]),
            Card(id=devil_data["id"], type="devilcat", variant=devil_data["variant"]),
        ]
        random.shuffle(dealt)
        actor_card, target_card = dealt
        cands = [o.name for o in self.alive() if o.name != p.name]
        if not cands:
            self.playmat.extend([god_entry, devil_entry])
            raise GameError("Cần ít nhất một người chơi khác cho Armageddon")
        self._say("☄️ ARMAGEDDON! Hai lá playmat được chia úp cho hai người!")
        self._ask("pick_player", p.name,
                  {"candidates": cands, "reason": "armageddon_target"},
                  lambda r, pl=p, ac=actor_card, tc=target_card:
                  self._armageddon_assign(pl, r["player"], ac, tc))

    def _armageddon_assign(self, actor: Player, target_name: str,
                           actor_card: Card, target_card: Card) -> None:
        target = self._get(target_name)
        self._ask("yes_no", target.name,
                  {"reason": "armageddon_keep",
                   "question": f"Giữ lá úp trước mặt hay đổi với {actor.name}?"},
                  lambda r, ac=actor, tg=target, a=actor_card, t=target_card:
                  self._resolve_armageddon(ac, tg, a, t, bool(r.get("value"))))

    def _resolve_armageddon(self, actor: Player, target: Player,
                            actor_card: Card, target_card: Card, keep: bool) -> None:
        actor_final = actor_card if keep else target_card
        target_final = target_card if keep else actor_card
        self._resolve_armageddon_fate(actor, actor_final)
        if self.phase == "playing":
            self._resolve_armageddon_fate(target, target_final)
        devil_id = actor_card.id if actor_card.type == "devilcat" else target_card.id
        devil_entry = next((e for e in (actor_card, target_card) if e.id == devil_id), None)
        if devil_entry is not None:
            self.playmat.append({"name": "-", "card": devil_entry.to_dict()})
        # armageddon.txt: chỉ hết 1 lượt (kể cả khi đang gánh nhiều lượt attack).
        self._end_turn(drew=False)

    def _resolve_armageddon_fate(self, holder: Player, card: Card) -> None:
        if card.type == "godcat":
            holder.hand.append(card)
            self._say(f"😇 {holder.name} NHẬN GODCAT!")
            return
        dfuse = next((c for c in holder.hand if c.type == "defuse"), None)
        if dfuse:
            self._leave_hand(holder, dfuse)
            self._to_grave(dfuse)
            self._say(f"{holder.name} bỏ Defuse để sống sót trước Devilcat.")
            return
        zomb = next((c for c in holder.hand if c.type == "zombiekitten"), None)
        if zomb is not None:  # godcat.txt: Defuse hoặc Zombie cứu khỏi Devilcat
            self._leave_hand(holder, zomb)
            self._to_grave(zomb)
            self._say(f"{holder.name} dùng Zombie Kitten để sống sót trước Devilcat.")
            return
        self._say(f"😈 {holder.name} lật trúng DEVILCAT!")
        self._kill(holder)

    def _do_targetattack(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        target.extra_turns += self.turns_left  # lượt còn dư + 2
        self._say(f"{target.name} bị tấn công — nhận tổng cộng {1 + target.extra_turns} lượt!")
        self._end_turn(drew=False, force=True)

    def _do_favor_pick(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        if target.name == self.tower_wearer and self.stash:
            self._take_tower_card(p, target)
            return
        self._ask(
            "pick_card", target_name,
            {"source": "own_hand", "give_to": p.name, "reason": "favor"},
            lambda r, pl=p, tg=target: self._transfer_choice(tg, r["card_id"], pl),
        )

    def _transfer_choice(self, src: Player, card_id: str, dst: Player) -> None:
        card = src.find(card_id)
        self._require(card is not None, "Thẻ không có trong tay nguồn")
        self._leave_hand(src, card)
        self._receive_card(dst, card)
        self._say(f"{src.name} đưa {dst.name} 1 thẻ.")

    def _after_quiesce(self, tail) -> None:
        """Chạy tiếp chuỗi give sau khi các prompt bom lồng nhau lắng xuống.

        Cho Streaking Kitten đi khi còn ôm EK sẽ mở prompt cứu bom ngay trong
        step; hỏi người tiếp theo luôn sẽ ghi đè pending đó và làm mất lá bom.
        """
        if self.pending is None:
            tail()
            return
        prev = self._cont

        def wrapped(resp, _prev=prev, _tail=tail):
            _prev(resp)
            if self.phase != "playing":
                return
            if self.pending is None:
                _tail()
            else:  # quyết định lồng nhau (defuse -> chọn vị trí): gài lại
                self._after_quiesce(_tail)

        self._cont = wrapped

    def _chain_potluck(self, receiver_ign: Player, names: list[str]) -> None:
        names = [n for n in names if self.players[n].alive and self.players[n].hand]
        if not names:
            return
        head, rest = names[0], names[1:]
        giver = self.players[head]

        def step(resp: dict, gv=giver, tail=rest) -> None:
            card = gv.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._leave_hand(gv, card)
            self.deck.insert(card, 0)  # lên đỉnh deck
            self._say(f"{gv.name} đặt 1 thẻ lên ĐỈNH deck (Potluck).")
            self._after_quiesce(lambda: self._chain_potluck(None, tail))

        self._ask("pick_card", head, {"source": "own_hand", "reason": "potluck"}, step)

    def _do_illtake(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        self._require(not target.illtake_by,
                      f"{target_name} đã có bẫy I'll Take That trước mặt.")
        target.illtake_by = p.name
        self._say(f"{p.name} đặt bẫy trước {target_name}: lá rút kế tiếp thuộc về {p.name}!")

    def _do_mark(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        card = random.choice(target.hand)
        target.marked_id = card.id
        self._say(f"📌 {target.name} bị Mark: lá {CARD_META[card.type]['name']} lộ diện đến khi played/stolen!")

    def _do_curse(self, target_name: str) -> None:
        self._get(target_name).blind = True
        self._say(f"😼 Curse of the Cat Butt: {target_name} bị MÙ — úp bài tới khi rút thành công!")

    def _chain_into_deck(self, names: list[str], then_shuffle: bool) -> None:
        names = [n for n in names if self.players[n].hand]
        if not names:
            if then_shuffle:
                self.deck.shuffle()
            return
        head, rest = names[0], names[1:]
        contributor = self.players[head]

        def step(resp: dict, ct=contributor, tail=rest) -> None:
            card = ct.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._leave_hand(ct, card)
            self.deck.insert(card, random.randint(0, self.deck.size()))
            self._say(f"{ct.name} cài lén 1 thẻ vào deck.")
            self._after_quiesce(lambda: self._chain_into_deck(tail, then_shuffle=then_shuffle))

        self._ask("pick_card", head, {"source": "own_hand", "reason": "into_deck"}, step)

    def _do_feed(self, actor: Player) -> None:
        dead = [n for n in self.order if not self.players[n].alive]
        if not dead:
            self._say("Không có ai đã chết.")
            return
        self._ask(
            "pick_player", actor.name, {"candidates": dead, "reason": "revive"},
            lambda r, pl=actor: self._feed_chain(pl, r["player"]),
        )

    def _feed_chain(self, actor: Player, dead_name: str) -> None:
        givers = [o.name for o in self.alive() if o.name != actor.name and o.hand]
        target = self._get(dead_name)

        def finish() -> None:
            target.alive = True
            self._say(f"👻 {dead_name} hồi sinh với {len(target.hand)} thẻ được tặng!")

        if not givers:
            finish()
            return

        def step(resp: dict, giver_name=givers[0], rest=givers[1:]) -> None:
            giver = self.players[giver_name]
            card = giver.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._leave_hand(giver, card)
            target.hand.append(card)
            self._say(f"{giver.name} dâng 1 thẻ cho {dead_name}.")
            rest = [n for n in rest if self.players[n].alive and self.players[n].hand]
            if rest:
                self._after_quiesce(lambda: self._chain_givers(target, rest, finish))
            else:
                self._after_quiesce(finish)

        self._ask("pick_card", givers[0],
                  {"source": "own_hand", "give_to": dead_name, "reason": "feedthedead"}, step)

    def _chain_givers(self, target: Player, names: list[str], finish) -> None:
        names = [n for n in names if self.players[n].alive and self.players[n].hand]
        if not names:
            self._after_quiesce(finish)
            return
        head, rest = names[0], names[1:]

        def step(resp: dict, gv=self.players[head], tail=rest) -> None:
            card = gv.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._leave_hand(gv, card)
            target.hand.append(card)
            self._say(f"{gv.name} dâng 1 thẻ cho {target.name}.")
            if tail:
                self._after_quiesce(lambda: self._chain_givers(target, tail, finish))
            else:
                self._after_quiesce(finish)

        self._ask("pick_card", head,
                  {"source": "own_hand", "give_to": target.name, "reason": "feedthedead"}, step)

    def _dig_choice(self, p: Player, card: Card, keep: bool) -> None:
        if keep:
            if card.type in BOMBS:
                # digdeeper.txt: giữ lá đào = rút nó — bom phải nổ (Defuse/chết)
                self._say(f"{p.name} giữ lá vừa đào... là {CARD_META[card.type]['name']}!")
                self._handle_bomb(p, card, remaining=1, end_after=False)
                if self.phase == "playing":
                    self._after_one_draw(p, 1, end_after=True)
                return
            p.hand.append(card)
            p.blind = False
            self._say(f"{p.name} giữ lá vừa đào. Hết lượt!")
            self._after_one_draw(p, 1, end_after=True)
        else:
            self.deck.insert(card, 0)  # trả lên đúng ĐỈNH (top = cuối list)
            self._say(f"{p.name} từ chối — phải rút lá kế tiếp!")
            self._resolve_draw(p, "top", 1, end_after=True)

    def _heck_choice(self, p: Player, card: Card, keep: bool) -> None:
        if keep:
            if card.type in BOMBS:
                # raisingheck: giữ lá đáy = rút nó — bom phải nổ (Defuse/chết)
                self._say(f"{p.name} giữ lá đáy... là {CARD_META[card.type]['name']}!")
                self._handle_bomb(p, card, remaining=1, end_after=False)
                if self.phase == "playing":
                    self._end_turn(drew=False, force=True)
                return
            p.hand.append(card)
            p.blind = False
            self._say(f"{p.name} giữ lá đáy.")
        else:
            self.deck.cards.append(card)  # lên đỉnh deck
            self._say(f"{p.name} đặt lá đáy lên đỉnh deck.")
        self._end_turn(drew=False, force=True)

    def _bury_place(self, p: Player, card: Card, resp: dict) -> None:
        index = max(0, min(int(resp.get("index", 0)), self.deck.size()))
        self.deck.insert(card, index)
        self._say(f"{p.name} vùi lặng 1 lá vào vị trí {index} từ đỉnh. Hết lượt!")
        self._after_one_draw(p, 1, end_after=True)

    def _share_show(self, p: Player) -> None:
        nxt = self._next_alive(p)
        if nxt:
            self._peek_for(nxt.name, self.deck.peek(3))
            self._say(f"{p.name} chia sẻ 3 thẻ trên cùng cho {nxt.name} xem.")

    def _ask_reorder(self, p: Player, n: int, then) -> None:
        top = self.deck.peek(min(n, self.deck.size()))
        self._ask(
            "reorder", p.name,
            {"cards": [c.to_dict() for c in top]},
            lambda r, pl=p, cb=then, tp=top: self._do_reorder(pl, r.get("order", []), cb, tp),
        )

    def _do_reorder(self, p: Player, order_ids: list, then, top: list[Card]) -> None:
        ids = [c.id for c in top]
        self._require(len(order_ids) == len(ids) and set(order_ids) == set(ids),
                      "Danh sách reorder không khớp các thẻ trên cùng")
        by_id = {c.id: c for c in top}
        new_top = [by_id[i] for i in order_ids]
        self.deck.cards[-len(top):] = list(reversed(new_top))  # top = cuối list
        self._say(f"{p.name} sắp xếp lại {len(top)} thẻ trên cùng (riêng tư).")
        then()

    # ---------- snapshot ----------

    def _bomb_positions(self) -> list[int]:
        size = self.deck.size()
        return [size - 1 - i for i, c in enumerate(self.deck.cards) if c.type in BOMBS]

    def view(self, name: str) -> dict:
        me = self.players[name]
        you = {
            "name": me.name, "alive": me.alive,
            "hand": [] if me.blind else [c.to_dict() for c in me.hand],
            "blind": me.blind,
            "marked": None if me.blind else next(
                (c.to_dict() for c in me.hand if c.id == me.marked_id), None),
            "illtake_by": me.illtake_by,
            "extra_turns": me.extra_turns,
        }
        if name in self.private_peeks:
            you["peek"] = self.private_peeks[name]
        if name in self.bomb_watchers:
            you["bomb_positions"] = self._bomb_positions()
        return {
            "phase": self.phase,
            "winner": self.winner,
            "you": you,
            "players": [
                {
                    "name": self.players[n2].name,
                    "alive": self.players[n2].alive,
                    "count": len(self.players[n2].hand),
                    "is_turn": n2 == self.order[self.turn_index],
                    "blind": self.players[n2].blind,
                    "faceup": [c.to_dict() for c in self.players[n2].faceup],
                    "marked": next((c.to_dict() for c in self.players[n2].hand
                                    if c.id == self.players[n2].marked_id), None),
                    "extra_turns": self.players[n2].extra_turns,
                }
                for n2 in self.order
            ],
            "deck_count": self.deck.size(),
            "stash_count": len(self.stash),
            "tower_wearer": self.tower_wearer,
            # lá đỉnh deck — chỉ công khai khi là Imploding Kitten úp mặt
            "deck_top": (lambda t: t.to_dict() if t and t.type == "implodingkitten" and t.faceup else None)(
                self.deck.peek(1)[0] if self.deck.size() else None),
            "grave_top": [c.to_dict() for c in reversed(self.grave[-10:])],
            # grave đầy đủ cho list overlay, mới nhất trước
            "grave": [c.to_dict() for c in reversed(self.grave)],
            "revealed": [c.to_dict() for c in self.revealed],
            "playmat": self.playmat,
            "turn": {"current": self.order[self.turn_index],
                     "direction": self.direction, "turns_left": self.turns_left},
            "pending": self._pending_for(name),
            "nope_window": ({
                "actor": self.nope["actor"],
                "card": self.nope["card"].to_dict(),
                "stacked": len(self.nope["stack"]),
                "ends_ms": int(self.nope_deadline * 1000) if self.nope_deadline else None,
            } if self.nope else None),
            "log": self.log_for(name),
        }
