"""Game: state machine ván Exploding Kitty — thuần Python đồng bộ, không biết HTTP/WS.

Hiệu ứng thẻ theo resources/cards_desc/*.txt.
Pending/decision points dùng continuation: _ask(kind, owner, data, cont) đặt pending;
Room đẩy respond() -> cont(payload) -> có thể _ask tiếp (chuỗi quyết định nối tiếp).
"""

import copy
import random

from .cards import CARD_META, GODCAT_BANNED, RESCUE_ORDER, Card, card_display_name
from .deck import Deck
from .player import Player

BOMBS = {"explodingkitten", "implodingkitten"}
TURN_ENDING_TYPES = {
    "skip", "superskip", "reverse", "attack2x", "targetattack2x",
    "attackofthedead", "drawfromthebottom", "digdeeper", "raisingheck",
    "bury", "catomicbomb", "armageddon",
}
BLIND_BOMB_FATAL_TYPES = {
    "skip", "superskip", "reverse",
    "attack2x", "targetattack2x", "personalattack3x", "attackofthedead",
}
CLAIRVOYANCE_INSERT_REASONS = {"defuse", "defuse_receive", "zombie", "godcat_defuse"}
LOG_BUFFER_MAX = 300


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
        self.private_peek_meta: dict[str, dict] = {}  # name -> {seq, source, from}
        self._peek_seq = 0
        self.clairvoyance_targets: dict[str, set[str]] = {}  # watcher -> bomb card IDs đã soi
        self._pending_clairvoyance: set[str] = set()  # watcher đang soi lượt đặt bom hiện tại
        self._last_bomb_insert: dict | None = None  # {placer, bomb_id, label} vừa đặt gần nhất
        self.log: list[str] = []  # tương thích: chỉ dòng công khai
        self.private_log: dict[str, list[str]] = {}  # name -> dòng log chỉ người đó thấy
        self.log_entries: list[tuple[int, str, str | None]] = []  # (seq, text, viewer)
        self.log_seq = 0
        self._card_seq = 0
        self._boom_seq = 0
        self.last_boom: dict | None = None
        self._fx_seq = 0
        self._fx_events: list[dict] = []

    # ---------- helpers ----------

    def _emit_fx(
        self,
        kind: str,
        actor: str,
        target: str | None = None,
        card_type: str | None = None,
        source: str | None = None,
        count: int | None = None,
    ) -> None:
        self._fx_seq += 1
        ev: dict = {"seq": self._fx_seq, "kind": kind, "actor": actor}
        if target is not None:
            ev["target"] = target
        if card_type is not None:
            ev["card_type"] = card_type
        if source is not None:
            ev["source"] = source
        if count is not None:
            ev["count"] = count
        self._fx_events.append(ev)
        if len(self._fx_events) > 20:
            del self._fx_events[:-20]

    def _say(self, msg: str, private: str | None = None) -> None:
        self.log_seq += 1
        self.log_entries.append((self.log_seq, msg, private))
        if len(self.log_entries) > 1000:
            del self.log_entries[:-1000]
        if private is None:
            self.log.append(msg)
            if len(self.log) > LOG_BUFFER_MAX:
                del self.log[:-LOG_BUFFER_MAX]
        else:
            plog = self.private_log.setdefault(private, [])
            plog.append(msg)
            if len(plog) > LOG_BUFFER_MAX:
                del plog[:-LOG_BUFFER_MAX]

    def announce_desk(self, desk: str) -> None:
        self._say(f"🃏 Bộ bài: {desk}")

    def log_for(self, name: str) -> list[str]:
        """Nhật ký theo thời gian của một người xem: công khai + riêng tư của họ."""
        visible = [text for _, text, viewer in self.log_entries
                   if viewer is None or viewer == name]
        return visible[-30:]

    def log_entries_for(self, name: str) -> list[dict]:
        """Nhật ký theo thời gian kèm seq tăng dần của một người xem."""
        visible = [{"seq": seq, "text": text} for seq, text, viewer in self.log_entries
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
        # Streaking Kitten rời tay (trộm/combo/favor/potluck/...): EK trên tay nổ (chỉ khi còn sống)
        if card.type == "streakingkitten" and self.phase == "playing" and p.alive:
            carried = next((c for c in p.hand if c.type == "explodingkitten"), None)
            if carried is not None:
                self._leave_hand(p, carried)
                self._say(f"💥 {p.name} mất Streaking Kitten — Exploding Kitten trên tay nổ!")
                self._handle_bomb(p, carried, remaining=1, end_after=False)

    def _peek_for(
        self,
        name: str,
        cards: list[Card],
        *,
        source: str = "peek",
        shared_by: str | None = None,
    ) -> None:
        if cards:
            self._peek_seq += 1
            self.private_peeks[name] = [c.to_dict() for c in cards]
            meta: dict = {"seq": self._peek_seq, "source": source}
            if shared_by is not None:
                meta["from"] = shared_by
            self.private_peek_meta[name] = meta

    def _shuffle_deck(self) -> None:
        self.deck.shuffle()
        self.clairvoyance_targets.clear()
        self._last_bomb_insert = None

    def _is_clairvoyance_pending_for(self, name: str) -> bool:
        """True khi người chơi KHÁC đang ở bước pick_index đặt bom sau Defuse/Zombie Kitten."""
        if self.pending is None or self.pending.get("kind") != "pick_index":
            return False
        reason = (self.pending.get("data") or {}).get("reason")
        if reason not in CLAIRVOYANCE_INSERT_REASONS:
            return False
        return self.pending.get("owner") != name

    def _can_play_clairvoyance(self, name: str) -> bool:
        """Clairvoyance chỉ dùng khi người khác đang đặt bom sau Defuse/Zombie Kitten hoặc vừa đặt xong."""
        if self.phase != "playing" or self.nope is not None:
            return False
        if self._is_clairvoyance_pending_for(name):
            return name not in self._pending_clairvoyance
        if self.pending is not None:
            return False
        last = self._last_bomb_insert
        if not last or last.get("placer") == name:
            return False
        bomb_id = last.get("bomb_id")
        if not bomb_id or not any(c.id == bomb_id for c in self.deck.cards):
            return False
        return bomb_id not in self.clairvoyance_targets.get(name, set())

    def _apply_clairvoyance(self, actor: Player) -> None:
        self._emit_fx("card_fx", actor=actor.name, card_type="clairvoyance")
        if self._is_clairvoyance_pending_for(actor.name):
            owner = self.pending["owner"]
            self._pending_clairvoyance.add(actor.name)
            self._say(f"🔮 {actor.name} dùng Clairvoyance — đang nhìn lén vị trí {owner} đặt bom vào deck!")
            return
        last = self._last_bomb_insert
        if last and last.get("placer") != actor.name:
            bomb_id = last["bomb_id"]
            pos = self._bomb_position_by_id(bomb_id)
            if pos is not None:
                self.clairvoyance_targets.setdefault(actor.name, set()).add(bomb_id)
                self._say(f"🔮 {actor.name} dùng Clairvoyance — soi vị trí {last['placer']} vừa đặt bom!")
                self._say(
                    f"🔮 Clairvoyance: {last['placer']} đã đặt {last['label']} — hiện ở vị trí #{pos} từ đỉnh deck!",
                    private=actor.name,
                )
                return
        self._say(f"🔮 {actor.name} dùng Clairvoyance nhưng không còn bom vừa đặt để soi.")

    def _record_bomb_insert(self, placer: str, bomb: Card, index: int) -> None:
        """Ghi nhận lượt chèn bom sau Defuse/Zombie Kitten & thông báo cho các watcher Clairvoyance."""
        label = CARD_META[bomb.type]["name"]
        pos = index + 1  # 1-based từ đỉnh deck (#1 = lá kế tiếp)
        self._say(f"{placer} đã bí mật đặt lại {label} vào deck.")
        self._say(f"Bạn đã đặt {label} vào vị trí #{pos} từ đỉnh deck.", private=placer)
        if bomb.type == "explodingkitten":
            self._last_bomb_insert = {"placer": placer, "bomb_id": bomb.id, "label": label}
            watchers = sorted(w for w in self._pending_clairvoyance if w != placer)
            self._pending_clairvoyance.clear()
            for watcher in watchers:
                self.clairvoyance_targets.setdefault(watcher, set()).add(bomb.id)
                self._say(
                    f"🔮 Clairvoyance: {placer} vừa đặt {label} vào vị trí #{pos} từ đỉnh deck!",
                    private=watcher,
                )
        else:
            self._pending_clairvoyance.clear()

    def _check_win(self) -> bool:
        alives = self.alive()
        if len(alives) <= 1:
            self.phase = "ended"
            self.winner = alives[0].name if alives else None
            self.pending = None
            self._cont = None
            self.nope = None
            self._clear_transient()
            if self.winner:
                self._say(f"🎉 {self.winner} thắng ván này!")
            return True
        return False

    def _clear_transient(self, actor: str | None = None) -> None:
        self.revealed = []
        if actor is None:
            self.private_peeks = {}
            self.private_peek_meta = {}
        else:
            self.private_peeks.pop(actor, None)
            self.private_peek_meta.pop(actor, None)

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
        idx = self.order.index(p.name) if p.name in self.order else self.turn_index
        for _ in range(n - 1):
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
        self._emit_fx("transfer", actor=target.name, target=thief.name, card_type="steal")
        self._receive_card(thief, card)
        self._say(f"{thief.name} trộm 1 thẻ từ tay {target.name}!")

    def _receive_card(self, p: Player, card: Card) -> None:
        """Nhận 1 lá vào tay từ người khác — nếu là bomb thì nổ ngay (phải cứu hoặc chết)."""
        if card.type in BOMBS:
            self._receive_bomb(p, card)
        else:
            p.hand.append(card)

    def _has_defuse(self, p: Player) -> bool:
        return p.standby_defuse or p.has_type("defuse")

    def _consume_defuse(self, p: Player) -> str | None:
        if p.standby_defuse:
            p.standby_defuse = False
            return "Defuse dự phòng (Godcat)"
        dfuse = next((c for c in p.hand if c.type == "defuse"), None)
        if dfuse is not None:
            self._leave_hand(p, dfuse)
            self._to_grave(dfuse)
            return "Defuse"
        return None

    def _receive_bomb(self, p: Player, bomb: Card, start: int = 0) -> None:
        label = CARD_META[bomb.type]["name"]
        if p.blind and start == 0:
            if p.standby_defuse:
                used = self._consume_defuse(p)
                p.blind = False
                self._emit_fx("defuse", actor=p.name, card_type="defuse")
                self._say(f"{p.name} dùng {used} cho {label} nhận được và hết mù!")
                self._ask(
                    "pick_index", p.name,
                    {"reason": "defuse_receive", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                    lambda r, pl=p, b=bomb: self._finish_receive_insert(pl, b, r),
                )
                return
            if (bomb.type == "explodingkitten"
                    and p.has_type("streakingkitten")
                    and not p.has_type("explodingkitten")):
                self._streaking_keep_received(p, bomb)
                return
            self._say(f"💥 {p.name} (bị mù) nhận phải {label} — phải đánh bừa bài trên tay để tìm Defuse!")
            self._ask_blind_bomb_pick(p, [bomb], remaining=0, end_after=False)
            return
        for i in range(start, len(RESCUE_ORDER)):
            t = RESCUE_ORDER[i]
            has_rescue = self._has_defuse(p) if t == "defuse" else p.has_type(t)
            if not has_rescue:
                continue
            if t == "defuse":
                used = self._consume_defuse(p)
                self._emit_fx("defuse", actor=p.name, card_type="defuse")
                self._say(f"{p.name} dùng {used} cho {label} nhận được!")
                self._ask(
                    "pick_index", p.name,
                    {"reason": "defuse_receive", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                    lambda r, pl=p, b=bomb: self._finish_receive_insert(pl, b, r),
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
        self._emit_fx("defuse", actor=p.name, card_type="streakingkitten")
        self._say(f"{p.name} GIỮ {CARD_META[bomb.type]['name']} nhận được nhờ Streaking Kitten!")

    def _zombie_use_received(self, p: Player, bomb: Card) -> None:
        self._zombie_use(p, bomb, 0, False)

    def _godcat_defuse_received(self, p: Player, bomb: Card) -> None:
        self._godcat_defuse(p, bomb, 0, False)

    def _finish_receive_insert(self, p: Player, bomb: Card, resp: dict) -> None:
        index = max(0, min(int(resp.get("index", 0)), self.deck.size()))
        self.deck.insert(bomb, index)
        self._emit_fx("put_deck", actor=p.name, card_type=bomb.type)
        self._record_bomb_insert(p.name, bomb, index)

    def _defuse_or_die(self, target: Player) -> None:
        used = self._consume_defuse(target)
        if used:
            self._emit_fx("defuse", actor=target.name, card_type="defuse")
            self._say(f"{target.name} phải dùng {used} cho Barking Kitten!")
        else:
            self._say(f"💥 {target.name} không có Defuse trước Barking Kitten!")
            self._kill(target)

    def _kill(self, p: Player, bomb: Card | None = None, cause: str | None = None) -> None:
        p.alive = False
        if bomb is not None:
            self._to_grave(bomb)
        if cause == "imploding" or (bomb is not None and bomb.type == "implodingkitten"):
            variant = "imploding"
            self._say(f"🌌 BOOM! {p.name} nổ tung bởi Imploding Kitten và bị loại!")
        elif cause == "devilcat" or (bomb is not None and bomb.type == "devilcat"):
            variant = "devilcat"
            self._say(f"😈 BOOM! {p.name} nổ tung bởi Devilcat và bị loại!")
        else:
            variant = "exploding"
            self._say(f"💥 BOOM! {p.name} nổ tung và bị loại!")
        self._boom_seq += 1
        self.last_boom = {"seq": self._boom_seq, "who": p.name, "variant": variant}
        self._check_win()

    # ---------- lifecycle ----------

    def start(self) -> None:
        """Chia bài: pool thường xáo -> mỗi người 4; +1 lá cứu/người; thừa về đáy; N-1 bom
        (N bom nếu deck có Streaking Kitten — cho phép 1 người ôm EK), giữ nguyên Imploding Kitten."""
        self.deck.load_pool(self.desk_name)
        imploding_kittens = [c for c in self.deck.cards if c.type == "implodingkitten"]
        for imp in imploding_kittens:
            imp.faceup = False
        # original.json chứa sẵn 20 bom + 6 defuse: tách cả hai, bom do engine tự chia
        defuses = [c for c in self.deck.cards if c.type == "defuse"]
        has_streaking = any(c.type == "streakingkitten" for c in self.deck.cards)
        self.deck.cards = [c for c in self.deck.cards if c.type not in ("defuse", *BOMBS)]
        if len(defuses) == 0 and any(c.type == "zombiekitten" for c in self.deck.cards):
            rescue_type = "zombiekitten"
            rescue_cards = [c for c in self.deck.cards if c.type == "zombiekitten"]
            self.deck.cards = [c for c in self.deck.cards if c.type != "zombiekitten"]
        else:
            rescue_type = "defuse"
            rescue_cards = defuses
        self.deck.shuffle()

        for name in self.order:  # mỗi người rút 4 từ pool thường
            for _ in range(4):
                card = self.deck.draw_top()
                if card:
                    self.players[name].hand.append(card)

        n = len(self.order)
        for name in self.order:  # mỗi người 1 lá cứu (Defuse hoặc Zombie Kitten)
            if rescue_cards:
                self.players[name].hand.append(rescue_cards.pop())
            else:
                self.players[name].hand.append(Card(id="", type=rescue_type, variant=0))
        for r_card in rescue_cards:  # lá cứu thừa về đáy
            self.deck.insert_bottom(r_card)

        # Streaking Kitten trong pool -> thêm 1 EK (tổng = số người chơi)
        n_bombs = n if has_streaking else n - 1
        ek_variants = [0, 1, 2, 3]
        for _ in range(n_bombs):
            bomb = Card(id="", type="explodingkitten", variant=random.choice(ek_variants))
            self.deck.insert(bomb, random.randint(0, self.deck.size()))
        for imp in imploding_kittens:
            self.deck.insert(imp, random.randint(0, self.deck.size()))

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
        self._card_seq = seq

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
            # thưởng khớp tên hiển thị, tên biến thể (vd: Blind As A Bat) hoặc type
            meta = CARD_META[ctype]
            name = meta.get("name", ctype).lower()
            vnames = [v.lower() for v in (meta.get("variant_names") or {}).values()]
            for cand in (ctype.lower(), name, *vnames):
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
        self._card_seq += 1
        card = Card(id=f"{resolved}.{variant}.{self._card_seq}", type=resolved, variant=variant)
        self._receive_card(p, card)
        self._say(f"[debug] {name} nhận {resolved}")

    def debug_put_deck(self, ctype: str, index: int = 0, variant: int = 0, faceup: bool = False) -> Card:
        """Debug-only: chèn trực tiếp 1 lá vào deck tại vị trí tính từ đỉnh."""
        resolved = self._fuzzy_type(ctype)
        self._require(resolved is not None, f"Không tìm thấy thẻ '{ctype}' — gõ lại gần tên hơn")
        self._card_seq += 1
        v = int(variant)
        card = Card(id=f"{resolved}.{v}.{self._card_seq}", type=resolved, variant=v, faceup=bool(faceup))
        idx = max(0, min(len(self.deck.cards), int(index)))
        self.deck.insert(card, idx)
        self._say(f"[debug] đặt {resolved} vào deck (#{idx})")
        return card

    def debug_set_turn(self, name: str, turns_left: int = 1) -> None:
        """Debug-only: chuyển lượt trực tiếp cho 1 người chơi còn sống."""
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        p = self._get(name)
        self._require(p.alive, f"{name} đã chết")
        self._clear_transient()
        self.turn_index = self.order.index(name)
        self.turns_left = max(1, min(10, int(turns_left)))
        self._say(f"[debug] chuyển lượt cho {name} ({self.turns_left} lượt)")

    def debug_toggle_blind(self, name: str) -> bool:
        """Debug-only: bật/tắt trạng thái mù cho người chơi."""
        p = self._get(name)
        p.blind = not p.blind
        self._say(f"[debug] {name} {'bị mù' if p.blind else 'hết mù'}")
        return p.blind

    def debug_remove_card(self, name: str, card_id: str) -> None:
        """Debug-only: bỏ trực tiếp 1 lá trên tay người chơi vào graveyard."""
        p = self._get(name)
        card = p.find(card_id)
        self._require(card is not None, "Không có thẻ này trên tay")
        self._leave_hand(p, card)
        self._to_grave(card)
        self._say(f"[debug] bỏ {card.type} khỏi tay {name}")

    def debug_snapshot(self) -> dict:
        """Debug-only: ảnh chụp toàn tri trạng thái ván cho Debug Studio."""
        deck_top_first = list(reversed(self.deck.cards))[:30]
        grave_top_first = list(reversed(self.grave))[:20]
        return {
            "phase": self.phase,
            "desk_name": self.desk_name,
            "winner": self.winner,
            "turn": {
                "current": self.order[self.turn_index] if self.order else None,
                "turns_left": self.turns_left,
                "direction": self.direction,
            },
            "deck_count": self.deck.size(),
            "deck": [
                {
                    "id": c.id,
                    "type": c.type,
                    "variant": c.variant,
                    "faceup": c.faceup,
                }
                for c in deck_top_first
            ],
            "grave": [c.to_dict() for c in grave_top_first],
            "playmat": copy.deepcopy(self.playmat),
            "stash_count": len(self.stash),
            "tower_wearer": self.tower_wearer,
            "pending": copy.deepcopy(self.pending) if self.pending is not None else None,
            "nope": (
                {
                    "actor": self.nope["actor"],
                    "card": self.nope["card"].to_dict(),
                    "as_type": self.nope.get("as_type"),
                    "stacked": len(self.nope["stack"]),
                    "responded": sorted(self.nope["responded"]),
                    "ends_ms": int(self.nope_deadline * 1000) if self.nope_deadline else None,
                }
                if self.nope
                else None
            ),
            "players": [
                {
                    "name": self.players[n].name,
                    "alive": self.players[n].alive,
                    "blind": self.players[n].blind,
                    "extra_turns": self.players[n].extra_turns,
                    "illtake_by": self.players[n].illtake_by,
                    "marked_id": self.players[n].marked_id,
                    "standby_defuse": self.players[n].standby_defuse,
                    "count": len(self.players[n].hand),
                    "hand": [c.to_dict() for c in self.players[n].hand],
                }
                for n in self.order
            ],
            "log_entries": [
                {"seq": seq, "text": text, "private": viewer}
                for seq, text, viewer in self.log_entries[-50:]
            ],
        }

    def _resolve_godcat(self, as_type: str | None) -> tuple[str, dict]:
        self._require(isinstance(as_type, str) and as_type, "Thiếu loại thẻ muốn hóa thân")
        resolved = self._fuzzy_type(as_type)
        self._require(resolved is not None, f"Không nhận ra thẻ '{as_type}'")
        self._require(resolved not in GODCAT_BANNED, f"Godcat không thể thành {resolved}")
        if resolved != "defuse":
            self._require(CARD_META[resolved].get("is_action"), f"{resolved} không đánh trực tiếp được")
        return resolved, CARD_META[resolved]

    # ---------- commands ----------

    def _waste_blind_card(self, p: Player, card: Card) -> None:
        self._leave_hand(p, card)
        self._to_grave(card)
        self._say(f"{p.name} (bị mù) tự đánh nhầm {card_display_name(card)} và vứt vào graveyard!")

    def _resolve_blind_card(self, p: Player, card_id: str | None) -> Card:
        self._require(bool(p.hand), "Bạn không còn thẻ nào")
        if card_id is None or card_id == "":
            return random.choice(p.hand)
        if isinstance(card_id, str) and card_id.startswith("blind."):
            raw_idx = card_id.split(".", 1)[1]
            if raw_idx.isascii() and raw_idx.isdigit() and str(int(raw_idx)) == raw_idx:
                idx = int(raw_idx)
                if 0 <= idx < len(p.hand):
                    return p.hand[idx]
        raise GameError("Lá bài úp không hợp lệ")

    def play_card(self, name: str, card_id: str | None = "", as_type: str | None = None) -> None:
        self._clear_transient(actor=name)
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        self._require(self._is_current(p), "Chưa tới lượt bạn")

        if p.blind:  # curse: chơi mù — chọn lá úp theo slot blind.<idx> (hoặc ngẫu nhiên nếu rỗng)
            card = self._resolve_blind_card(p, card_id)
            if card_id:
                self._say(f"{name} (bị mù) chọn lật 1 lá úp...")
            else:
                self._say(f"{name} (bị mù) chơi ngẫu nhiên 1 lá...")
        else:
            card = p.find(card_id or "")
            self._require(card is not None, "Không có thẻ này trên tay")
        meta = self._meta(card.type)
        if p.blind:
            if card.type == "explodingkitten":
                self._leave_hand(p, card)
                self._say(f"💥 {name} (bị mù) tự đánh trúng Exploding Kitten trên tay — phải tìm Defuse!")
                self._handle_bomb(p, card, remaining=1, end_after=False, allow_streaking=False)
                return
            mat_types = {e["card"]["type"] for e in self.playmat}
            has_dead = any(not self.players[n2].alive for n2 in self.order)
            unplayable_blind = (
                not meta.get("is_action")
                or card.type == "nope"
                or meta.get("as_any_card")
                or meta.get("combo_only")
                or (meta.get("needs_dead") and not has_dead)
                or (meta.get("needs_playmat_kitten") and not ({"godcat", "devilcat"} <= mat_types))
                or (card.type == "bury" and p.illtake_by is not None)
                or (card.type == "clairvoyance" and not self._can_play_clairvoyance(p.name))
            )
            if unplayable_blind:
                self._waste_blind_card(p, card)
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
        if eff_type == "clairvoyance":
            self._require(
                self._can_play_clairvoyance(name),
                "Clairvoyance chỉ dùng khi người khác vừa Defuse/Zombie Kitten đặt bom lại vào deck",
            )

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

        effect = self._make_card_effect(p, card, eff_type, clone_beneath)

        if meta.get("nopeable") and len([a for a in self.alive() if a.name != name]) > 0:
            self.nope = {
                "actor": name,
                "card": card,
                "as_type": eff_type if card.type == "godcat" else None,
                "stack": [],
                "responded": set(),
                "effect": effect,
            }
            return  # Room mở timer 5s rồi gọi resolve_nope()
        effect()

    def play_combo(self, name: str, combo: str, card_ids: list) -> None:
        """Combo: pair (2 lá cùng tên) hoặc three (3 lá cùng tên) — feralcat là wildcard."""
        self._clear_transient(actor=name)
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive and self._is_current(p), "Chưa tới lượt bạn")
        self._require(not p.blind, "Bị mù không đánh combo được")
        self._require(combo in ("pair", "three"), "Combo không hợp lệ")
        need = 2 if combo == "pair" else 3
        self._require(len(card_ids) == need, f"Cần chọn đúng {need} lá")
        self._require(len(set(card_ids)) == need, "Không thể chọn trùng một lá bài")
        cards = []
        for cid in card_ids:
            card = p.find(cid)
            self._require(card is not None, f"Không có thẻ {cid}")
            cards.append(card)
        core_cards = [c for c in cards if c.type not in ("feralcat", "clone")]
        core_types = [c.type for c in core_cards]
        if core_types:
            self._require(len(set(core_types)) == 1, "Các lá không cùng loại")
            if core_types[0] == "cat":
                self._require(
                    len({c.variant for c in core_cards}) == 1,
                    "Các lá Mèo (Cat) phải cùng loại mèo (cùng hình) mới ghép combo được",
                )
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
                self._emit_fx("card_fx", actor=p.name, card_type="combo_pair", source=named, count=2)
                self._ask("pick_player", p.name, {"candidates": cands, "reason": "steal"},
                          lambda r, pl=p: self._steal_pick(pl, r["player"]))
            effect = effect_pair
        else:
            def effect_three():
                cands = [o.name for o in self.alive()
                         if o.name != p.name and (o.hand or (o.name == self.tower_wearer and self.stash))]
                if not cands:
                    return
                self._emit_fx("card_fx", actor=p.name, card_type="combo_three", source=named, count=3)
                self._ask("pick_player", p.name, {"candidates": cands, "reason": "call_card"},
                          lambda r, pl=p: self._three_call(pl, r["player"]))
            effect = effect_three

        if len([a for a in self.alive() if a.name != name]) > 0:
            self.nope = {
                "actor": name,
                "card": cards[0],
                "as_type": None,
                "stack": [],
                "responded": set(),
                "effect": effect,
            }
            return
        effect()

    def _take_tower_card(self, taker: Player, wearer: Player) -> None:
        card = random.choice(self.stash)
        self.stash.remove(card)
        self._emit_fx("transfer", actor=wearer.name, target=taker.name, card_type="tower")
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
        self._emit_fx("transfer", actor=target.name, target=p.name, card_type="three")
        self._receive_card(p, card)
        self._say(f"{target.name} đưa {p.name} 1 thẻ.")

    def draw(self, name: str) -> None:
        self._clear_transient(actor=name)
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.pending is None, "Đang chờ quyết định")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        self._require(self._is_current(p), "Chưa tới lượt bạn")
        self._resolve_draw(p, "top", 1, end_after=True)

    def play_now(self, name: str, card_id: str, as_type: str | None = None) -> None:
        """Thẻ anytime: shufflenow, clairvoyance, alter3xnow, feedthedead, godcat-as-card."""
        self._clear_transient(actor=name)
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
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
            if eff_type == "clairvoyance":
                self._require(
                    self._can_play_clairvoyance(name),
                    "Clairvoyance chỉ dùng khi người khác vừa Defuse/Zombie Kitten đặt bom lại vào deck",
                )
            else:
                self._require(self.pending is None, "Đang chờ quyết định")
            if eff_meta.get("needs_dead"):
                self._require(any(not self.players[n2].alive for n2 in self.order),
                              "Cần có người đã chết")
            if eff_meta.get("needs_playmat_kitten"):
                mat_types = {e["card"]["type"] for e in self.playmat}
                self._require({"godcat", "devilcat"} <= mat_types,
                              "Armageddon cần cả Godcat và Devilcat trên bàn")
            if eff_type == "bury":
                self._require(p.illtake_by is None,
                              "Bạn đang bị I'll Take That — không dùng được Bury.")
            clone_beneath = self.grave[-1] if eff_type == "clone" and self.grave else None
            if not self._is_current(p):
                self._require(
                    eff_type not in TURN_ENDING_TYPES,
                    f"Không thể dùng Godcat như {eff_meta['name']} ngoài lượt",
                )
                if eff_type == "clone" and clone_beneath is not None:
                    self._require(
                        clone_beneath.type not in TURN_ENDING_TYPES,
                        "Không thể dùng Godcat Clone thẻ kết thúc lượt ngoài lượt",
                    )
            self._leave_hand(p, card)
            self.playmat.append({"name": name, "card": card.to_dict()})
            self._say(f"{name} dùng Godcat như {eff_meta['name']} (ngoài lượt)!")
            effect = self._make_card_effect(p, card, eff_type, clone_beneath)
            meta = eff_meta
        else:
            if card.type == "clairvoyance":
                self._require(
                    self._can_play_clairvoyance(name),
                    "Clairvoyance chỉ dùng khi người khác vừa Defuse/Zombie Kitten đặt bom lại vào deck",
                )
            else:
                self._require(self.pending is None, "Đang chờ quyết định")
            self._leave_hand(p, card)
            self._to_grave(card)
            self._say(f"{name} chơi {meta['name']} (ngoài lượt)!")
            effect = lambda: self._apply_anytime(p, card.type)  # noqa: E731
        if meta.get("nopeable") and len([a for a in self.alive() if a.name != name]) > 0:
            self.nope = {
                "actor": name,
                "card": card,
                "as_type": eff_type if card.type == "godcat" else None,
                "stack": [],
                "responded": set(),
                "effect": effect,
            }
            return
        effect()

    def _make_card_effect(
        self, p: Player, card: Card, eff_type: str, clone_beneath: Card | None
    ):
        """Tạo closure thực thi hiệu ứng thẻ (chạy sau khi cửa sổ Nope thông qua)."""
        def effect() -> None:
            if card.type == "godcat":
                self._emit_fx("card_fx", actor=p.name, card_type="godcat", source=eff_type)
            if eff_type == "clone":
                self._apply_clone(p, card, clone_beneath)
            elif card.type == "barkingkitten":
                self._apply_barking(p, card)
            else:
                self._apply_effect(p, eff_type, card)

        return effect

    def _godcat_personal(self, p: Player) -> None:
        p.extra_turns += 2
        self._emit_fx("card_fx", actor=p.name, card_type="personalattack3x", count=2)
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
                reason = data.get("reason")
                if not data.get("allow_dead") and reason != "graverobber":
                    self._require(owner.alive, "Bạn đã chết")
                if payload.get("random") is True:
                    self._require(owner.blind, "Chỉ dùng chọn ngẫu nhiên khi bị mù")
                    self._require(bool(owner.hand), "Bạn không còn thẻ nào")
                    if reason in ("potluck", "into_deck"):
                        self._require(
                            any(c.type != "godcat" for c in owner.hand),
                            "Godcat không thể đưa vào bộ bài rút",
                        )
                elif owner.blind:
                    card_id = payload.get("card_id")
                    if not isinstance(card_id, str) or not card_id.startswith("blind."):
                        raise GameError("Lá bài úp không hợp lệ")
                    chosen = self._resolve_blind_card(owner, card_id)
                    if reason in ("potluck", "into_deck") and chosen.type == "godcat":
                        if any(c.type != "godcat" for c in owner.hand):
                            raise GameError("Lá úp này không thể đặt vào deck — hãy chọn lá úp khác!")
                        raise GameError("Godcat không thể đưa vào bộ bài rút")
                    payload["card_id"] = chosen.id
                else:
                    card_id = payload.get("card_id")
                    card = owner.find(card_id) if isinstance(card_id, str) else None
                    if card is None:
                        raise GameError("Thẻ không có trong tay bạn")
                    if reason in ("potluck", "into_deck") and card.type == "godcat":
                        raise GameError("Godcat không thể đưa vào bộ bài rút")
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
        self._clear_transient(actor=name)
        self._require(self.phase == "playing", "Ván chưa/không diễn ra")
        self._require(self.nope is None, "Đang có cửa sổ Nope")
        self._require(self.pending is not None, "Không có quyết định đang chờ")
        self._require(self.pending["owner"] == name, "Không phải lượt quyết định của bạn")
        self._require(isinstance(payload, dict), "Payload quyết định không hợp lệ")
        resolved_payload = dict(payload)
        self._validate_pending_response(self.pending, resolved_payload)
        snap = self.pending
        cont = self._cont
        if (snap.get("kind") == "pick_card"
                and (snap.get("data") or {}).get("source") == "own_hand"
                and resolved_payload.get("random") is True):
            owner = self._get(name)
            reason = (snap.get("data") or {}).get("reason")
            pool = (
                [c for c in owner.hand if c.type != "godcat"]
                if reason in ("potluck", "into_deck")
                else list(owner.hand)
            ) or list(owner.hand)
            chosen = random.choice(pool)
            resolved_payload = {**resolved_payload, "card_id": chosen.id}
        self.pending = None
        self._cont = None
        try:
            cont(resolved_payload)
        except GameError:
            self.pending, self._cont = snap, cont  # chọn sai -> được chọn lại
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            self.pending, self._cont = snap, cont  # payload hỏng không được xóa pending
            raise GameError("Payload quyết định không hợp lệ") from exc

    def auto_resolve_dead_pending(self, *, include_revive: bool = False) -> bool:
        """Tự động chọn ngẫu nhiên nếu pending hiện tại rơi vào người đã chết để tránh treo bàn."""
        resolved_any = False
        for _ in range(16):
            if self.phase != "playing" or self.pending is None or self.nope is not None:
                break
            owner_name = self.pending.get("owner")
            owner = self.players.get(owner_name or "")
            if owner is None or owner.alive:
                break
            kind = self.pending.get("kind")
            data = self.pending.get("data") or {}
            if not include_revive and kind == "pick_player" and data.get("reason") == "revive":
                break
            payload: dict | None = None
            if kind == "pick_card":
                source = data.get("source")
                if source == "own_hand":
                    reason = data.get("reason")
                    pool = (
                        [c for c in owner.hand if c.type != "godcat"]
                        if reason in ("potluck", "into_deck")
                        else list(owner.hand)
                    )
                    if not pool:
                        self.pending = None
                        self._cont = None
                        resolved_any = True
                        break
                    chosen = random.choice(pool)
                    cid = f"blind.{owner.hand.index(chosen)}" if owner.blind else chosen.id
                    payload = {"card_id": cid}
                elif source == "victim_hand":
                    cnt = int(data.get("count", 0) or 0)
                    if cnt <= 0:
                        self.pending = None
                        self._cont = None
                        resolved_any = True
                        break
                    payload = {"position": random.randrange(cnt)}
            elif kind == "pick_player":
                cands = list(data.get("candidates") or [])
                if not cands:
                    self.pending = None
                    self._cont = None
                    resolved_any = True
                    break
                payload = {"player": random.choice(cands)}
            elif kind == "pick_index":
                lo = int(data.get("min", 0))
                hi = int(data.get("max", lo))
                payload = {"index": random.randint(lo, max(lo, hi))}
            elif kind == "yes_no":
                payload = {"value": False}
            elif kind == "reorder":
                cards = data.get("cards") or []
                payload = {"order": [c["id"] for c in cards if isinstance(c, dict) and "id" in c]}
            elif kind == "input_card":
                payload = {"text": ""}
            if payload is None:
                break
            self._say(f"🪦 {owner.name} (đã chết) — hệ thống tự động chọn ngẫu nhiên để tiếp tục ván đấu.")
            try:
                self.respond(owner.name, payload)
                resolved_any = True
            except GameError:
                break
        return resolved_any

    def stack_nope(self, name: str) -> None:
        self._clear_transient(actor=name)
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        self._require(self.phase == "playing", "Ván đã kết thúc")
        if not self.nope["stack"]:
            self._require(name != self.nope["actor"], "Không nope được chính mình")
        self._require(name not in self.nope["responded"], "Bạn đã phản hồi rồi")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        nope_card = next((c for c in p.hand if c.type == "nope"), None)
        self._require(nope_card is not None, "Bạn không có thẻ Nope")
        self._leave_hand(p, nope_card)
        self.nope["stack"].append(nope_card)
        # Reset responded & deadline để mọi người sống khác (kể cả actor gốc) có thể phản Nope (Yup)
        self.nope["responded"] = {name}
        self.nope_deadline = None
        self._emit_fx("nope", actor=name, count=len(self.nope["stack"]))
        self._say(f"{name} tung Nope! ({len(self.nope['stack'])} chồng)")

    def pass_nope(self, name: str) -> None:
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        if not self.nope["stack"]:
            self._require(name != self.nope["actor"], "Actor không cần phản hồi")
        self._require(name not in self.nope["responded"], "Bạn đã phản hồi rồi")
        p = self._get(name)
        self._require(p.alive, "Bạn đã chết")
        self.nope["responded"].add(name)

    def nope_all_responded(self) -> bool:
        if self.nope["stack"]:
            others = [p.name for p in self.alive()]
        else:
            others = [p.name for p in self.alive() if p.name != self.nope["actor"]]
        return all(n in self.nope["responded"] for n in others)

    def resolve_nope(self) -> None:
        """Đóng cửa sổ nope: số Nope lẻ => hành động bị hủy; chẵn => hiệu ứng chạy."""
        self._require(self.nope is not None, "Không có cửa sổ Nope")
        actor_name, card, stack, effect = (
            self.nope["actor"], self.nope["card"], self.nope["stack"], self.nope["effect"])
        self._clear_transient(actor=actor_name)
        noped = len(stack) % 2 == 1
        label = card_display_name(card)
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

    def _refill_from_grave(self) -> bool:
        """Xáo graveyard thành deck mới — lọc bỏ bom đã nổ và Imploding mặt ngửa."""
        if not self.grave:
            return False
        recyclable = [
            c for c in self.grave
            if c.type != "explodingkitten"
            and not (c.type == "implodingkitten" and c.faceup)
        ]
        if not recyclable:
            return False
        recyclable_ids = {c.id for c in recyclable}
        self.deck.cards = recyclable
        self.grave = [c for c in self.grave if c.id not in recyclable_ids]
        self._shuffle_deck()
        self._say("Deck cạn — xáo graveyard thành deck mới.")
        return True

    def _take_from_deck(self, source: str) -> Card | None:
        card = self.deck.draw_bottom() if source == "bottom" else self.deck.draw_top()
        if card is None and self._refill_from_grave():
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
                    # illtakethat.txt: người rút xem lá trước khi đưa đi và hết mù (kể cả khi đưa EK)
                    p.blind = False
                    self._peek_for(p.name, [card], source="illtakethat", shared_by=actor.name)
                    self._say(
                        f"Bạn rút {card_display_name(card)} và phải đưa cho {actor.name} (I'll Take That)!",
                        private=p.name,
                    )
                    self._emit_fx(
                        "transfer", actor=p.name, target=actor.name,
                        card_type="illtakethat", source=source,
                    )
                    self._say(f"{p.name} rút phải bom nhưng bị {actor.name} chặn lấy!")
                    self._handle_bomb(actor, card, remaining=1, end_after=False)
                    if self.phase == "playing":
                        self._after_quiesce(
                            lambda pl=p, rem=remaining, ea=end_after: self._after_one_draw(pl, rem, ea)
                        )
                    return
                if card.type != "implodingkitten":  # ponytail: imploding không intercept
                    p.blind = False
                    self._peek_for(p.name, [card], source="illtakethat", shared_by=actor.name)
                    self._say(
                        f"Bạn rút {card_display_name(card)} và phải đưa cho {actor.name} (I'll Take That)!",
                        private=p.name,
                    )
                    actor.hand.append(card)
                    if not actor.blind:
                        self._say(
                            f"Bạn nhận {card_display_name(card)} từ {p.name} (I'll Take That)!",
                            private=actor.name,
                        )
                    self._emit_fx(
                        "transfer", actor=p.name, target=actor.name,
                        card_type="illtakethat", source=source,
                    )
                    self._say(f"{p.name} rút thẻ nhưng bị {actor.name} giật mất!")
                    self._after_one_draw(p, remaining, end_after)
                    return

        ctype = card.type
        if ctype in BOMBS:
            self._emit_fx("draw", actor=p.name, source=source)
            if ctype == "implodingkitten" and not card.faceup:
                self._handle_imploding_first(p, card, remaining, end_after)
            else:
                self._handle_bomb(p, card, remaining, end_after)
            return

        # thẻ thường vào tay
        p.hand.append(card)
        p.blind = False  # rút thành công không nổ -> khỏi mù
        self._emit_fx("draw", actor=p.name, source=source)
        self._say(f"Bạn rút {card_display_name(card)}", private=p.name)
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
        self._emit_fx("card_fx", actor=p.name, card_type="imploding_arm")
        self._say(f"😼 {p.name} rút phải Imploding Kitten — đặt lại vào deck MẶT LÊN!")
        self._ask(
            "pick_index", p.name,
            {"reason": "imploding", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
            lambda r, b=bomb, pl=p, rem=remaining, ea=end_after: self._finish_insert(pl, b, r, rem, ea),
        )

    def _handle_bomb(self, p: Player, bomb: Card, remaining: int, end_after: bool,
                     start: int = 0, allow_streaking: bool = True) -> None:
        label = CARD_META[bomb.type]["name"]
        # Imploding Kitten MẶT NGỬA: nổ ngay, không Defuse/Streaking/Zombie/Godcat cứu được
        if bomb.type == "implodingkitten" and bomb.faceup:
            self._say(f"😼 {p.name} rút phải Imploding Kitten MẶT NGỬA — nổ ngay, không cứu được!")
            self._kill(p, bomb=bomb)
            self._after_one_draw(p, remaining, end_after)
            return
        if p.blind and start == 0:
            # Defuse dự phòng (Godcat đặt công khai trên bàn) vẫn dùng được ngay
            if p.standby_defuse:
                used = self._consume_defuse(p)
                p.blind = False
                self._emit_fx("defuse", actor=p.name, card_type="defuse")
                self._say(f"{p.name} dùng {used} cho {label} và hết mù!")
                self._ask_pick_insert(p, bomb, "defuse", remaining, end_after)
                return
            # Streaking Kitten trên tay bảo vệ thụ động cho lá Exploding Kitten đầu tiên
            if (allow_streaking
                    and bomb.type == "explodingkitten"
                    and p.has_type("streakingkitten")
                    and not p.has_type("explodingkitten")):
                p.blind = False
                self._streaking_keep(p, bomb, remaining, end_after)
                return
            self._say(f"💥 {p.name} (bị mù) bốc phải {label} — phải chọn bừa lá úp trên tay để tìm Defuse!")
            self._ask_blind_bomb_pick(p, [bomb], remaining, end_after)
            return
        for i in range(start, len(RESCUE_ORDER)):
            t = RESCUE_ORDER[i]
            has_rescue = self._has_defuse(p) if t == "defuse" else p.has_type(t)
            if not has_rescue:
                continue
            if t == "defuse":
                used = self._consume_defuse(p)
                self._emit_fx("defuse", actor=p.name, card_type="defuse")
                self._say(f"{p.name} dùng {used} cho {label}!")
                if bomb.type == "implodingkitten":
                    self.deck.insert(bomb, 0)  # lên đỉnh
                    self._emit_fx("put_deck", actor=p.name, card_type=bomb.type)
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

    def _ask_blind_bomb_pick(
        self,
        p: Player,
        bombs: list[Card],
        remaining: int,
        end_after: bool,
        last_wasted: str | None = None,
    ) -> None:
        """Người chơi đang blind bốc phải bom: phải lật bừa từng lá úp cho tới khi trúng Defuse hoặc nổ."""
        bomb = bombs[0]
        rest = bombs[1:]
        if not p.hand:
            for extra in rest:
                self._to_grave(extra)
            self._say(f"💥 {p.name} (bị mù) hết bài trên tay mà chưa tìm thấy Defuse — nổ tung!")
            self._kill(p, bomb=bomb)
            self._after_one_draw(p, remaining, end_after)
            return
        data: dict = {
            "source": "own_hand",
            "reason": "blind_defuse",
            "card": bomb.to_dict(),
            "remaining_bombs": len(bombs),
        }
        if last_wasted:
            data["last_wasted"] = last_wasted
        self._ask(
            "pick_card",
            p.name,
            data,
            lambda r, pl=p, bs=list(bombs), rem=remaining, ea=end_after: self._blind_bomb_pick(
                pl, bs, r.get("card_id", ""), rem, ea
            ),
        )

    def _blind_bomb_pick(
        self,
        p: Player,
        bombs: list[Card],
        card_id: str,
        remaining: int,
        end_after: bool,
    ) -> None:
        bomb = bombs[0]
        next_bombs = list(bombs[1:])
        chosen = p.find(card_id)
        self._require(chosen is not None, "Thẻ không có trong tay bạn")

        # Gỡ khỏi tay trực tiếp (tự xử lý Streaking Kitten để không đè self.pending bằng đệ quy)
        p.hand.remove(chosen)
        if p.marked_id == chosen.id:
            p.marked_id = None
        if chosen.type == "streakingkitten":
            carried = next((c for c in p.hand if c.type == "explodingkitten"), None)
            if carried is not None:
                p.hand.remove(carried)
                if p.marked_id == carried.id:
                    p.marked_id = None
                next_bombs.append(carried)
                self._say(f"💥 {p.name} (bị mù) bỏ trúng Streaking Kitten — Exploding Kitten trên tay cũng phát nổ!")

        label = CARD_META[bomb.type]["name"]
        chosen_name = card_display_name(chosen)

        # 1. Trúng lá cứu bom hợp lệ (Defuse / Zombie Kitten / Godcat)
        if chosen.type in ("defuse", "zombiekitten", "godcat"):
            if not next_bombs:
                p.blind = False
            unblind_suffix = " và hết mù" if not next_bombs else ""
            after_insert = (
                (lambda pl, rem, ea, nb=next_bombs: self._ask_blind_bomb_pick(pl, nb, rem, ea))
                if next_bombs
                else None
            )
            if chosen.type == "defuse":
                self._to_grave(chosen)
                self._emit_fx("defuse", actor=p.name, card_type="defuse")
                self._say(f"🛡️ {p.name} (bị mù) đánh trúng Defuse — cứu sống khỏi {label}{unblind_suffix}!")
                self._ask(
                    "pick_index", p.name,
                    {"reason": "defuse", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                    lambda r, b=bomb, pl=p, rem=remaining, ea=end_after, nxt=after_insert: (
                        self._finish_insert(pl, b, r, rem, ea, then=nxt)
                    ),
                )
                return
            if chosen.type == "zombiekitten":
                self._to_grave(chosen)
                self._emit_fx("defuse", actor=p.name, card_type="zombiekitten")
                self._say(f"🧟 {p.name} (bị mù) đánh trúng Zombie Kitten — cứu sống khỏi {label}{unblind_suffix}!")

                def after_zombie_insert(pl: Player, rem: int, ea: bool, nb=next_bombs) -> None:
                    if not nb:
                        self._zombie_revive(pl, rem, ea)
                        return
                    self._zombie_revive(pl, 0, False)
                    if self.phase == "playing":
                        self._after_quiesce(lambda: self._ask_blind_bomb_pick(pl, nb, rem, ea))

                self._ask(
                    "pick_index", p.name,
                    {"reason": "zombie", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                    lambda r, b=bomb, pl=p, rem=remaining, ea=end_after: (
                        self._finish_insert(pl, b, r, rem, ea, then=after_zombie_insert)
                    ),
                )
                return
            # godcat
            self.playmat.append({"name": p.name, "card": chosen.to_dict()})
            self._emit_fx("defuse", actor=p.name, card_type="godcat")
            self._say(f"✨ {p.name} (bị mù) đánh trúng Godcat như Defuse — cứu sống khỏi {label}{unblind_suffix}!")
            self._ask(
                "pick_index", p.name,
                {"reason": "godcat_defuse", "min": 0, "max": self.deck.size(), "card": bomb.to_dict()},
                lambda r, b=bomb, pl=p, rem=remaining, ea=end_after, nxt=after_insert: (
                    self._finish_insert(pl, b, r, rem, ea, then=nxt)
                ),
            )
            return

        # 2. Trúng lá bỏ lượt (Skip, Super Skip, Reverse, Attack...) -> nổ ngay và bị loại
        if chosen.type in BLIND_BOMB_FATAL_TYPES:
            self._to_grave(chosen)
            for extra in next_bombs:
                self._to_grave(extra)
            self._say(f"💥 {p.name} (bị mù) đánh trúng {chosen_name} (lá bỏ lượt) khi đang gỡ bom — nổ tung!")
            self._kill(p, bomb=bomb)
            self._after_one_draw(p, remaining, end_after)
            return

        # 3. Trúng thêm Exploding Kitten trên tay -> phải gỡ cả 2 quả bom
        if chosen.type == "explodingkitten":
            next_bombs.append(chosen)
            self._say(
                f"💥 {p.name} (bị mù) lại lật trúng {chosen_name} trên tay — phải tìm Defuse cho cả {len(next_bombs) + 1} quả bom!"
            )
            self._ask_blind_bomb_pick(p, [bomb, *next_bombs], remaining, end_after, last_wasted=chosen_name)
            return

        # 4. Lá khác -> bỏ vào graveyard (mất hiệu lực), tiếp tục chọn bừa
        self._to_grave(chosen)
        self._say(f"🙈 {p.name} (bị mù) đánh trượt trúng {chosen_name} — mất hiệu lực, tiếp tục tìm Defuse!")
        self._ask_blind_bomb_pick(p, [bomb, *next_bombs], remaining, end_after, last_wasted=chosen_name)

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
        self._emit_fx("put_deck", actor=p.name, card_type=bomb.type)
        self._record_bomb_insert(p.name, bomb, index)
        if then:
            then(p, remaining, end_after)
            return
        self._after_one_draw(p, remaining, end_after)

    def _streaking_keep(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        # streaking.txt: giữ bom MIỄN LÀ streaking còn trên tay — KHÔNG bỏ streaking
        p.hand.append(bomb)
        self._emit_fx("defuse", actor=p.name, card_type="streakingkitten")
        self._say(f"{p.name} GIỮ {CARD_META[bomb.type]['name']} trên tay nhờ Streaking Kitten!")
        self._after_one_draw(p, remaining, end_after)

    def _zombie_use(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        zomb = next(c for c in p.hand if c.type == "zombiekitten")
        self._leave_hand(p, zomb)
        self._to_grave(zomb)
        self._emit_fx("defuse", actor=p.name, card_type="zombiekitten")
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
        self._emit_fx("card_fx", actor=p.name, target=target_name, card_type="zombiekitten")
        self._say(f"👻 {target_name} hồi sinh!")
        self._after_one_draw(p, remaining, end_after)

    def _godcat_defuse(self, p: Player, bomb: Card, remaining: int, end_after: bool) -> None:
        god = next(c for c in p.hand if c.type == "godcat")
        self._leave_hand(p, god)
        self.playmat.append({"name": p.name, "card": god.to_dict()})
        self._emit_fx("defuse", actor=p.name, card_type="godcat")
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
            p.standby_defuse = True
            self._say(f"{p.name} giữ {CARD_META[card.type]['name']} như Defuse dự phòng trên bàn.")
            return
        if t in ("skip", "superskip"):
            self._emit_fx("card_fx", actor=p.name, card_type=t)
            self._end_turn(drew=False, force=(t == "superskip"))
        elif t == "shuffle" or t == "shufflenow":
            self._shuffle_deck()
            self._emit_fx("card_fx", actor=p.name, card_type=t)
            self._say("Deck được xáo.")
        elif t == "clairvoyance":
            self._apply_clairvoyance(p)
        elif t == "alter3xnow":
            self._emit_fx("card_fx", actor=p.name, card_type="alter3xnow")
            self._ask_reorder(p, 3, then=lambda: None)
        elif t == "attack2x":
            nxt = self._next_alive(p)
            if nxt:
                # targetattack.txt: nạn nhân gánh lượt còn dư + 2 (chồng attack: 4 rồi 6...).
                nxt.extra_turns += self.turns_left
                self._say(f"{nxt.name} nhận tổng cộng {1 + nxt.extra_turns} lượt!")
            self._emit_fx(
                "card_fx", actor=p.name,
                target=nxt.name if nxt else None,
                card_type="attack2x",
                count=(1 + nxt.extra_turns) if nxt else 2,
            )
            self._end_turn(drew=False, force=True)
        elif t == "targetattack2x":
            cands = [o.name for o in self.alive() if o.name != p.name]
            if not cands:
                self._say("Không có mục tiêu để tấn công.")
                return
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "targetattack"},
                      lambda r, pl=p: self._do_targetattack(pl, r["player"]))
        elif t == "personalattack3x":
            if not self._is_current(p):
                # Ngoài lượt (vd Godcat / Godcat Clone Personal Attack): cộng lượt thưởng cho chính p.
                self._godcat_personal(p)
                return
            # Lượt thường (1) -> tổng 3 (+2); đã bị chồng lượt (>1) -> cộng đủ +3 lượt.
            self.turns_left += 2 if self.turns_left == 1 else 3
            self._emit_fx("card_fx", actor=p.name, card_type="personalattack3x", count=self.turns_left)
            self._say(f"{p.name} tự tấn công — tổng cộng {self.turns_left} lượt liên tiếp!")
        elif t == "attackofthedead":
            dead = sum(1 for n in self.order if not self.players[n].alive)
            if dead == 0:
                self._say("Attack of the Dead vô hiệu — không có người đã chết.")
                return
            nxt = self._next_alive(p)
            if nxt:
                # lượt còn dư + 3 mỗi người chết (T=1, D=1 -> tổng 3 như cũ).
                nxt.extra_turns += self.turns_left + 3 * dead - 2
                self._say(f"{nxt.name} bị ép tổng cộng {1 + nxt.extra_turns} lượt ({dead} người chết x 3)!")
            self._emit_fx(
                "card_fx", actor=p.name,
                target=nxt.name if nxt else None,
                card_type="attackofthedead",
                count=(1 + nxt.extra_turns) if nxt else None,
            )
            self._end_turn(drew=False, force=True)
        elif t == "reverse":
            self.direction *= -1
            self._emit_fx("card_fx", actor=p.name, card_type="reverse")
            self._say("Chiều lượt ĐẢO NGƯỢC! Hết lượt không rút.")
            self._end_turn(drew=False)  # giống skip: chỉ hết 1 trong n lượt
        elif t == "drawfromthebottom":
            self._resolve_draw(p, "bottom", 1, end_after=True)
        elif t == "seethefuture3x":
            self._peek_for(p.name, self.deck.peek(3))
            self._emit_fx("card_fx", actor=p.name, card_type="seethefuture3x")
            self._say(f"{p.name} nhìn trộm 3 thẻ trên cùng.")
        elif t == "seethefuture5x":
            self._peek_for(p.name, self.deck.peek(5))
            self._emit_fx("card_fx", actor=p.name, card_type="seethefuture5x")
            self._say(f"{p.name} nhìn trộm 5 thẻ trên cùng.")
        elif t == "revealthefuture3x":
            self.revealed = self.deck.peek(3)
            self._emit_fx("card_fx", actor=p.name, card_type="revealthefuture3x")
            self._say("3 thẻ trên cùng bị lật cho cả bàn!")
        elif t == "sharethefuture3x":
            self._emit_fx("card_fx", actor=p.name, card_type="sharethefuture3x")
            self._ask_reorder(p, 3, then=lambda pl=p: self._share_show(pl))
        elif t in ("alter3x", "alter5x"):
            self._emit_fx("card_fx", actor=p.name, card_type=t)
            self._ask_reorder(p, 3 if t == "alter3x" else 5, then=lambda: None)
        elif t == "digdeeper":
            self._emit_fx("card_fx", actor=p.name, card_type="digdeeper")
            card_dug = self._take_from_deck("top")
            if card_dug is None:
                self._end_turn(drew=False)
                return
            self._peek_for(p.name, [card_dug])
            self._ask(
                "yes_no", p.name,
                {"reason": "digdeeper", "question": "Giữ lá vừa đào?", "card": card_dug.to_dict()},
                lambda r, pl=p, cd=card_dug: self._dig_choice(pl, cd, bool(r.get("value"))),
            )
        elif t == "raisingheck":
            self._emit_fx("card_fx", actor=p.name, card_type="raisingheck")
            card_h = self._take_from_deck("bottom")
            if card_h is None:
                self._end_turn(drew=False)
                return
            self._peek_for(p.name, [card_h])
            self._ask(
                "yes_no", p.name,
                {"reason": "raisingheck", "question": "Giữ lá đáy vừa lôi lên?", "card": card_h.to_dict()},
                lambda r, pl=p, ch=card_h: self._heck_choice(pl, ch, bool(r.get("value"))),
            )
        elif t == "bury":
            self._emit_fx("card_fx", actor=p.name, card_type="bury")
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
            self._shuffle_deck()
            self._emit_fx("card_fx", actor=p.name, card_type="towerofpower")
            self._say(f"{p.name} đội Tower of Power — stash vẫn nằm dưới vương miện ({len(self.stash)} lá).")
        elif t == "armageddon":
            self._do_armageddon(p)
        elif t == "favor":
            cands = [o.name for o in self.alive()
                     if o.name != p.name and (o.hand or (o.name == self.tower_wearer and self.stash))]
            if not cands:
                self._say("Không có ai có thẻ để xin.")
                return
            self._emit_fx("card_fx", actor=p.name, card_type="favor")
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "favor"},
                      lambda r, pl=p: self._do_favor_pick(pl, r["player"]))
        elif t == "potluck":
            self._emit_fx("card_fx", actor=p.name, card_type="potluck")
            idx = self.order.index(p.name)
            step = self.direction
            givers = []
            n = len(self.order)
            for k in range(n):
                cand = self.players[self.order[(idx + step * k) % n]]
                if cand.alive and any(c.type != "godcat" for c in cand.hand):
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
            if not cands:
                self._say("Không có ai còn thẻ để Mark.")
                return
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "mark"},
                      lambda r, pl=p: self._do_mark(pl, r["player"]))
        elif t == "curseofthecatbutt":
            cands = [o.name for o in self.alive() if o.name != p.name]
            if not cands:
                self._say("Không có mục tiêu để Curse.")
                return
            label = card_display_name(card) if card.type == "curseofthecatbutt" else card_display_name("curseofthecatbutt")
            self._ask("pick_player", p.name, {"candidates": cands, "reason": "curse"},
                      lambda r, pl=p, lb=label: self._do_curse(pl.name, r["player"], lb))
        elif t == "garbagecollection":
            self._emit_fx("card_fx", actor=p.name, card_type="garbagecollection")
            participants = [p.name] if any(c.type != "godcat" for c in p.hand) else []
            participants.extend(
                o.name for o in self.alive()
                if o.name != p.name and any(c.type != "godcat" for c in o.hand)
            )
            self._chain_into_deck(participants, then_shuffle=True, allow_dead=False)
        elif t == "graverobber":
            self._emit_fx("card_fx", actor=p.name, card_type="graverobber")
            dead_with_cards = [
                n for n in self.order
                if not self.players[n].alive
                and any(c.type != "godcat" for c in self.players[n].hand)
            ]
            if not dead_with_cards:
                self._say("Không người chết nào còn bài.")
                return
            self._chain_into_deck(dead_with_cards, then_shuffle=True, allow_dead=True)
        elif t == "feedthedead":
            self._do_feed(p)
        elif t == "catomicbomb":
            # catomicbomb.txt: chỉ Exploding Kittens — Imploding ở yên trong deck
            bombs_in_deck = [c for c in self.deck.cards if c.type == "explodingkitten"]
            rest = [c for c in self.deck.cards if c.type != "explodingkitten"]
            random.shuffle(rest)
            self.revealed = list(bombs_in_deck)
            self.deck.cards = rest + bombs_in_deck  # mọi bom chồng lên đỉnh
            self.clairvoyance_targets.clear()
            self._last_bomb_insert = None
            self._emit_fx("card_fx", actor=p.name, card_type="catomicbomb")
            self._say(f"💣 CATOMIC BOMB! {len(bombs_in_deck)} quả bom lộ diện và xếp chồng lên đỉnh deck!")
            self._end_turn(drew=False, force=True)
        elif t == "devilcat":
            self._emit_fx("card_fx", actor=p.name, card_type="devilcat")
        elif t == "swaptopandbottom":
            self._emit_fx("card_fx", actor=p.name, card_type="swaptopandbottom")
            if self.deck.size() >= 2:
                self.deck.cards[0], self.deck.cards[-1] = self.deck.cards[-1], self.deck.cards[0]
                self._say("Top ↔ Bottom deck hoán đổi úp (không ai được xem).")
        else:
            self._say(f"{CARD_META[t]['name']} không có hiệu ứng (chưa cài đặt).")

    def _apply_anytime(self, actor: Player, ctype: str) -> None:
        if ctype == "shufflenow":
            self._shuffle_deck()
            self._emit_fx("card_fx", actor=actor.name, card_type="shufflenow")
            self._say("Deck được xáo (NOW).")
        elif ctype == "clairvoyance":
            self._apply_clairvoyance(actor)
        elif ctype == "alter3xnow":
            self._emit_fx("card_fx", actor=actor.name, card_type="alter3xnow")
            self._ask_reorder(actor, 3, then=lambda: None)
        elif ctype == "feedthedead":
            self._do_feed(actor)

    def _apply_barking(self, p: Player, card: Card) -> None:
        self._emit_fx("card_fx", actor=p.name, card_type="barkingkitten")
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
                if not cands:
                    return
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
        bmeta = CARD_META.get(beneath.type, {})
        if not bmeta.get("is_action") or beneath.type in ("nope", "godcat", "devilcat"):
            self._say(f"Clone vô hiệu — không thể sao chép {bmeta.get('name', beneath.type)}.")
            return
        if bmeta.get("needs_dead") and not any(not self.players[n2].alive for n2 in self.order):
            self._say(f"Clone vô hiệu — {bmeta['name']} cần có người đã chết.")
            return
        if beneath.type == "armageddon":
            mat_types = {e["card"]["type"] for e in self.playmat}
            if not ({"godcat", "devilcat"} <= mat_types):
                self._say("Clone vô hiệu — Armageddon cần cả Godcat và Devilcat trên bàn.")
                return
        if beneath.type == "bury" and p.illtake_by is not None:
            self._say("Clone vô hiệu — bạn đang bị I'll Take That, không dùng được Bury.")
            return
        self._emit_fx("card_fx", actor=p.name, card_type="clone", source=beneath.type)
        self._say(f"Clone hóa thành {bmeta['name']}!")
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
        self._emit_fx("card_fx", actor=p.name, card_type="armageddon")
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
            self._emit_fx("receive", actor=holder.name, card_type="godcat")
            self._say(f"😇 {holder.name} NHẬN GODCAT!")
            return
        used = self._consume_defuse(holder)
        if used:
            self._emit_fx("defuse", actor=holder.name, card_type="defuse")
            self._say(f"{holder.name} dùng {used} để sống sót trước Devilcat.")
            return
        zomb = next((c for c in holder.hand if c.type == "zombiekitten"), None)
        if zomb is not None:  # godcat.txt: Defuse hoặc Zombie cứu khỏi Devilcat
            self._leave_hand(holder, zomb)
            self._to_grave(zomb)
            self._emit_fx("defuse", actor=holder.name, card_type="zombiekitten")
            self._say(f"{holder.name} dùng Zombie Kitten để sống sót trước Devilcat.")
            return
        self._say(f"😈 {holder.name} lật trúng DEVILCAT!")
        self._kill(holder, cause="devilcat")

    def _do_targetattack(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        target.extra_turns += self.turns_left  # lượt còn dư + 2
        self._emit_fx(
            "card_fx", actor=p.name, target=target.name,
            card_type="targetattack2x", count=1 + target.extra_turns,
        )
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
        self._emit_fx("transfer", actor=src.name, target=dst.name, card_type="favor")
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
        names = [
            n for n in names
            if self.players[n].alive and any(c.type != "godcat" for c in self.players[n].hand)
        ]
        if not names:
            return
        head, rest = names[0], names[1:]
        giver = self.players[head]

        def step(resp: dict, gv=giver, tail=rest) -> None:
            card = gv.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._require(card.type != "godcat", "Godcat không thể đưa vào bộ bài rút")
            self._leave_hand(gv, card)
            self.deck.insert(card, 0)  # lên đỉnh deck
            self._emit_fx("put_deck", actor=gv.name, card_type="potluck")
            self._say(f"{gv.name} đặt 1 thẻ lên ĐỈNH deck (Potluck).")
            self._after_quiesce(lambda: self._chain_potluck(None, tail))

        self._ask("pick_card", head, {"source": "own_hand", "reason": "potluck"}, step)

    def _do_illtake(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        self._require(not target.illtake_by,
                      f"{target_name} đã có bẫy I'll Take That trước mặt.")
        target.illtake_by = p.name
        self._emit_fx("card_fx", actor=p.name, target=target.name, card_type="illtakethat")
        self._say(f"{p.name} đặt bẫy trước {target_name}: lá rút kế tiếp thuộc về {p.name}!")

    def _do_mark(self, p: Player, target_name: str) -> None:
        target = self._get(target_name)
        card = random.choice(target.hand)
        target.marked_id = card.id
        self._emit_fx("card_fx", actor=p.name, target=target.name, card_type="mark")
        self._say(f"📌 {target.name} bị Mark: lá {card_display_name(card)} lộ diện đến khi played/stolen!")

    def _do_curse(self, actor_name: str, target_name: str, card_label: str = "Curse of the Cat Butt") -> None:
        target = self._get(target_name)
        target.blind = True
        random.shuffle(target.hand)
        self._emit_fx("card_fx", actor=actor_name, target=target_name, card_type="curseofthecatbutt")
        self._say(f"😼 {card_label}: {target_name} bị MÙ — bài bị xáo úp tới khi rút thành công!")

    def _chain_into_deck(self, names: list[str], then_shuffle: bool,
                         allow_dead: bool = False) -> None:
        names = [
            n for n in names
            if ((not self.players[n].alive) if allow_dead else self.players[n].alive)
            and any(c.type != "godcat" for c in self.players[n].hand)
        ]
        if not names:
            if then_shuffle:
                self._shuffle_deck()
            return
        head, rest = names[0], names[1:]
        contributor = self.players[head]

        # Người chơi đã chết: tự động chọn ngẫu nhiên 1 thẻ hợp lệ (khác Godcat) để không làm treo bàn
        if not contributor.alive:
            eligible = [c for c in contributor.hand if c.type != "godcat"]
            if eligible:
                chosen = random.choice(eligible)
                self._leave_hand(contributor, chosen)
                self.deck.insert(chosen, random.randint(0, self.deck.size()))
                self._emit_fx(
                    "put_deck",
                    actor=contributor.name,
                    card_type="graverobber" if allow_dead else "garbagecollection",
                )
                label = "Grave Robber" if allow_dead else "cài bài vào deck"
                self._say(f"🪦 {contributor.name} (đã chết) tự động chọn ngẫu nhiên 1 thẻ cài vào deck ({label}).")
            self._after_quiesce(
                lambda: self._chain_into_deck(rest, then_shuffle=then_shuffle, allow_dead=allow_dead)
            )
            return

        def step(resp: dict, ct=contributor, tail=rest) -> None:
            card = ct.find(resp.get("card_id", ""))
            self._require(card is not None, "Thẻ không có trong tay bạn")
            self._require(card.type != "godcat", "Godcat không thể đưa vào bộ bài rút")
            self._leave_hand(ct, card)
            self.deck.insert(card, random.randint(0, self.deck.size()))
            self._emit_fx(
                "put_deck",
                actor=ct.name,
                card_type="graverobber" if allow_dead else "garbagecollection",
            )
            self._say(f"{ct.name} cài lén 1 thẻ vào deck.")
            self._after_quiesce(
                lambda: self._chain_into_deck(tail, then_shuffle=then_shuffle, allow_dead=allow_dead)
            )

        data = {"source": "own_hand", "reason": "into_deck"}
        if allow_dead:
            data["allow_dead"] = True
        self._ask("pick_card", head, data, step)

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
            self._emit_fx("card_fx", actor=actor.name, target=dead_name, card_type="feedthedead")
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
            self._emit_fx("transfer", actor=giver.name, target=target.name, card_type="feedthedead")
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
            self._emit_fx("transfer", actor=gv.name, target=target.name, card_type="feedthedead")
            self._say(f"{gv.name} dâng 1 thẻ cho {target.name}.")
            if tail:
                self._after_quiesce(lambda: self._chain_givers(target, tail, finish))
            else:
                self._after_quiesce(finish)

        self._ask("pick_card", head,
                  {"source": "own_hand", "give_to": target.name, "reason": "feedthedead"}, step)

    def _dig_choice(self, p: Player, card: Card, keep: bool) -> None:
        if keep:
            self._emit_fx("draw", actor=p.name, source="top")
            if card.type in BOMBS:
                # digdeeper.txt: giữ lá đào = rút nó — bom phải nổ (hoặc Imploding úp mặt)
                self._say(f"{p.name} giữ lá vừa đào... là {CARD_META[card.type]['name']}!")
                if card.type == "implodingkitten" and not card.faceup:
                    self._handle_imploding_first(p, card, remaining=1, end_after=True)
                else:
                    self._handle_bomb(p, card, remaining=1, end_after=True)
                return
            p.hand.append(card)
            p.blind = False
            self._say(f"{p.name} giữ lá vừa đào. Hết lượt!")
            self._after_one_draw(p, 1, end_after=True)
        else:
            # digdeeper.txt: rút lá KẾ TIẾP và đặt lá từ chối lên ĐỈNH deck
            if self.deck.size() == 0:
                self._refill_from_grave()
            if self.deck.size() >= 1:
                self.deck.insert(card, 1)  # đặt ngay dưới lá đỉnh -> rút lá đỉnh xong lá từ chối nằm trên đỉnh
                self._say(f"{p.name} từ chối — phải rút lá kế tiếp!")
                self._resolve_draw(p, "top", 1, end_after=True)
            else:
                self.deck.insert(card, 0)
                self._say(f"{p.name} từ chối nhưng không còn thẻ kế tiếp — trả thẻ lên đỉnh deck.")
                self._end_turn(drew=False)

    def _heck_choice(self, p: Player, card: Card, keep: bool) -> None:
        if keep:
            self._emit_fx("draw", actor=p.name, source="bottom")
            if card.type in BOMBS:
                # raisingheck: giữ lá đáy = rút nó — bom phải nổ (hoặc Imploding úp mặt)
                self._say(f"{p.name} giữ lá đáy... là {CARD_META[card.type]['name']}!")
                if card.type == "implodingkitten" and not card.faceup:
                    self._handle_imploding_first(p, card, remaining=1, end_after=True)
                else:
                    self._handle_bomb(p, card, remaining=1, end_after=True)
                return
            p.hand.append(card)
            p.blind = False
            self._say(f"{p.name} giữ lá đáy.")
        else:
            self.deck.cards.append(card)  # lên đỉnh deck
            self._say(f"{p.name} đặt lá đáy lên đỉnh deck.")
        self._end_turn(drew=False)

    def _bury_place(self, p: Player, card: Card, resp: dict) -> None:
        index = max(0, min(int(resp.get("index", 0)), self.deck.size()))
        self.deck.insert(card, index)
        self._emit_fx("put_deck", actor=p.name, card_type="bury")
        self._say(f"{p.name} vùi lặng 1 lá lại vào deck. Hết lượt!")
        self._say(f"Bạn đã vùi lá vào vị trí #{index + 1} từ đỉnh deck.", private=p.name)
        self._after_one_draw(p, 1, end_after=True)

    def _share_show(self, p: Player) -> None:
        nxt = self._next_alive(p)
        shared = self.deck.peek(3)
        if nxt and shared:
            self._peek_for(nxt.name, shared, source="share", shared_by=p.name)
            self._say(f"{p.name} chia sẻ {len(shared)} thẻ trên cùng cho {nxt.name} xem.")

    def _ask_reorder(self, p: Player, n: int, then) -> None:
        top = self.deck.peek(min(n, self.deck.size()))
        if not top:
            self._say("Deck không còn thẻ nào để sắp xếp.")
            then()
            return
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

    def _bomb_position_by_id(self, bomb_id: str) -> int | None:
        """Vị trí 1-based từ đỉnh deck (#1 = lá đỉnh kế tiếp) của 1 quả bom cụ thể."""
        size = self.deck.size()
        for i, c in enumerate(self.deck.cards):
            if c.id == bomb_id:
                return size - i
        return None

    def _bomb_positions_for(self, name: str) -> list[int]:
        """Các vị trí 1-based từ đỉnh deck của những quả bom người chơi này đã soi bằng Clairvoyance."""
        watched = self.clairvoyance_targets.get(name)
        if not watched:
            return []
        size = self.deck.size()
        return sorted(size - i for i, c in enumerate(self.deck.cards) if c.id in watched)

    def view(self, name: str) -> dict:
        me = self.players[name]
        you = {
            "name": me.name, "alive": me.alive,
            "hand": (
                [{"id": f"blind.{i}", "type": "hidden", "variant": 0, "blind_index": i}
                 for i in range(len(me.hand))]
                if me.blind
                else [c.to_dict() for c in me.hand]
            ),
            "hand_count": len(me.hand),
            "blind": me.blind,
            "marked": None if me.blind else next(
                (c.to_dict() for c in me.hand if c.id == me.marked_id), None),
            "illtake_by": me.illtake_by,
            "extra_turns": me.extra_turns,
        }
        if name in self.private_peeks:
            you["peek"] = self.private_peeks[name]
            if name in self.private_peek_meta:
                you["peek_meta"] = self.private_peek_meta[name]
        watched_positions = self._bomb_positions_for(name)
        if watched_positions:
            you["bomb_positions"] = watched_positions
        you["can_clairvoyance"] = self._can_play_clairvoyance(name)
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
                    "marked": (
                        None if (n2 == name and me.blind)
                        else next((c.to_dict() for c in self.players[n2].hand
                                   if c.id == self.players[n2].marked_id), None)
                    ),
                    "illtake_by": self.players[n2].illtake_by,
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
                "as_type": self.nope.get("as_type"),
                "stacked": len(self.nope["stack"]),
                "you_responded": name in self.nope["responded"],
                "ends_ms": int(self.nope_deadline * 1000) if self.nope_deadline else None,
            } if self.nope else None),
            "log": self.log_for(name),
            "log_entries": self.log_entries_for(name),
            "last_boom": self.last_boom,
            "fx_events": list(self._fx_events[-12:]),
        }
