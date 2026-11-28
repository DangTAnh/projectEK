"""Room: bọc Game với kết nối WebSocket, timer cửa sổ Nope, reconnect theo tên."""

import asyncio
import json
import logging
import os
from pathlib import Path
import random
import secrets
import time
from collections import Counter

from fastapi import WebSocket

from .engine import Game, GameError
from .engine.cards import CARD_META
from .engine.deck import DESK_DIR, available_desks, desk_detail

logger = logging.getLogger(__name__)

MAX_PLAYERS = 9
MAX_SPECTATORS = 20
MAX_CUSTOM_DESKS = 12
MAX_CUSTOM_CARD_TOTAL = 200
MIN_CUSTOM_NONBOMB_CARDS = 10
MAX_PER_CARD_TYPE = 30
NOPE_SECONDS = 2
_INITIAL_TURN_SECONDS = float(os.environ.get("ROOM_TURN_SECONDS", "30"))
TURN_SECONDS = _INITIAL_TURN_SECONDS
LOADING_TIMEOUT_SECONDS = 15.0
SEND_TIMEOUT = 5.0
MAX_ROOMS = 500
EMPTY_LOBBY_TTL_SECONDS = 300
EMPTY_DISCONNECT_TTL_SECONDS = 5.0
LOBBY_TTL_SECONDS = 3600
GAME_TTL_SECONDS = 900
LOBBY_SESSION_TTL_SECONDS = 120
MAX_DISCONNECTED_LOBBY_SESSIONS = 64
TAKEOVER_CLOSE_CODE = 4001
AUTH_CLOSE_CODE = 4401
ROOM_UNAVAILABLE_CLOSE_CODE = 4403
UNKNOWN_ROOM_CLOSE_CODE = 4404

CARDS_DIR = Path(__file__).resolve().parents[1] / "resources" / "cards"


def _turn_seconds() -> float:
    """Đọc thời lượng lượt (hỗ trợ cả monkeypatch TURN_SECONDS và env ROOM_TURN_SECONDS)."""
    if TURN_SECONDS != _INITIAL_TURN_SECONDS:
        return max(0.01, float(TURN_SECONDS))
    raw = os.environ.get("ROOM_TURN_SECONDS")
    if raw is not None:
        try:
            return max(0.01, float(raw))
        except ValueError:
            pass
    return max(0.01, float(TURN_SECONDS))


def desk_image_urls(desk: str, custom_cards: dict | None = None) -> list[str]:
    """Liệt kê URL ảnh lá bài (và mặt sau) cần preload cho bộ bài desk."""
    urls: list[str] = []
    seen: set[str] = set()

    def add_url(url: str) -> None:
        if url not in seen:
            seen.add(url)
            urls.append(url)

    def add_card_variant(ctype: str, variant: int | str) -> None:
        v_str = str(variant)
        if (CARDS_DIR / ctype / f"{v_str}.jpg").is_file():
            add_url(f"/static/cards/{ctype}/{v_str}.jpg")
        elif (CARDS_DIR / ctype / "0.jpg").is_file():
            add_url(f"/static/cards/{ctype}/0.jpg")

    add_url("/backside.jpg")
    cards_map: dict[str, dict] = {}
    if isinstance(custom_cards, dict):
        cards_map = custom_cards
    else:
        desk_path = DESK_DIR / f"{desk}.json"
        try:
            data = json.loads(desk_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("cards"), dict):
                cards_map = data["cards"]
        except (OSError, ValueError):
            cards_map = {}

    for ctype, variants in cards_map.items():
        if not isinstance(variants, dict):
            continue
        for variant_str, count in variants.items():
            try:
                if int(count) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            add_card_variant(ctype, variant_str)

    # Game.start() luôn chèn Exploding Kitten với các variant 0..3
    for ek_var in (0, 1, 2, 3):
        add_card_variant("explodingkitten", ek_var)

    # Armageddon có thể sinh Devilcat / Godcat
    if "armageddon" in cards_map:
        add_card_variant("devilcat", 0)
        add_card_variant("godcat", 0)

    return urls

AVATAR_ALLOWED: dict[str, set[str]] = {
    "fur": {"ginger", "cream", "gray", "charcoal", "calico", "pink", "mint", "sky", "potato", "sphynx"},
    "pattern": {"none", "tabby", "tuxedo", "calico", "siamese", "cow", "hairy", "bandaid", "sweat"},
    "eyes": {"derp", "happy", "angry", "wide", "chill", "star", "spiral", "lasers"},
    "mouth": {"cat", "blep", "fangs", "scream", "smug", "beard", "rainbow", "drool"},
    "hat": {"none", "taco", "melon", "crown", "wizard", "bomb", "party", "beanie", "cone", "poop", "underwear", "toast", "tin"},
    "acc": {"none", "shades", "bowtie", "scarf", "monocle", "collar", "knife", "fish", "stink"},
}


def sanitize_avatar(raw) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise GameError("Avatar không hợp lệ")
    clean: dict[str, str] = {}
    for key, allowed in AVATAR_ALLOWED.items():
        val = raw.get(key)
        if isinstance(val, str) and val in allowed:
            clean[key] = val
    if not clean:
        raise GameError("Avatar không hợp lệ")
    return clean


def _card_variants(ctype: str) -> list[int]:
    try:
        files = (CARDS_DIR / ctype).glob("*.jpg")
        found = sorted(int(p.stem) for p in files if p.stem.isdigit())
        return found or [0]
    except OSError:
        return [0]


def _distribute_card_variants(
    ctype: str,
    count: int,
    base_variants: dict | None = None,
) -> dict[str, int]:
    """Phân bổ số lượng lá vào các biến thể artwork; giữ nguyên biến thể preset nếu khớp."""
    if count <= 0:
        return {}
    if isinstance(base_variants, dict):
        clean_base: dict[str, int] = {}
        for var, cnt in base_variants.items():
            try:
                v_int = int(var)
                c_int = int(cnt)
            except (TypeError, ValueError):
                continue
            if c_int > 0:
                clean_base[str(v_int)] = c_int
        if sum(clean_base.values()) == count:
            return clean_base

    variants = _card_variants(ctype)
    out: dict[str, int] = {}
    if isinstance(base_variants, dict):
        for var, cnt in base_variants.items():
            try:
                v_str = str(int(var))
                c_int = int(cnt)
            except (TypeError, ValueError):
                continue
            if c_int > 0:
                out[v_str] = c_int

    cur = sum(out.values())
    if cur > count:
        # Giảm bớt từ các biến thể cuối về 0
        for v_str in list(reversed(list(out.keys()))):
            if cur <= count:
                break
            take = min(out[v_str], cur - count)
            out[v_str] -= take
            cur -= take
            if out[v_str] <= 0:
                del out[v_str]
        return out

    # Tăng thêm: riêng `cat` gom theo bộ 4 lá cùng biến thể để đánh được combo
    if ctype == "cat":
        idx = 0
        while cur < count:
            v_str = str(variants[idx % len(variants)])
            room_in_group = max(1, 4 - (out.get(v_str, 0) % 4))
            add = min(count - cur, room_in_group)
            out[v_str] = out.get(v_str, 0) + add
            cur += add
            idx += 1
        return out

    idx = 0
    while cur < count:
        v_str = str(variants[idx % len(variants)])
        out[v_str] = out.get(v_str, 0) + 1
        cur += 1
        idx += 1
    return out


def build_custom_desk_spec(raw: dict, *, creator: str, desk_id: str) -> dict:
    """Validate và dựng custom desk hoàn chỉnh từ counts hoặc từ một preset."""
    if not isinstance(raw, dict):
        raise GameError("Dữ liệu Custom Desk không hợp lệ")
    raw_title = raw.get("title")
    title = raw_title.strip() if isinstance(raw_title, str) else ""
    if not title or len(title) > 40:
        raise GameError("Tên bộ bài phải từ 1 đến 40 ký tự")

    raw_preset = raw.get("preset")
    preset: str | None = None
    preset_detail: dict | None = None
    if raw_preset is not None and raw_preset != "":
        if not isinstance(raw_preset, str) or raw_preset not in available_desks():
            raise GameError(f"Không có bộ bài preset '{raw_preset}'")
        preset = raw_preset
        preset_detail = desk_detail(preset)

    raw_counts = raw.get("counts")
    raw_cards = raw.get("cards")
    if not isinstance(raw_counts, dict) and isinstance(raw_cards, dict):
        raw_counts = {
            ctype: sum(int(cnt) for cnt in variants.values())
            for ctype, variants in raw_cards.items()
            if isinstance(variants, dict)
        }
    if not isinstance(raw_counts, dict):
        raise GameError("Thiếu danh sách số lượng lá bài")

    preset_cards = preset_detail.get("cards", {}) if preset_detail else {}
    cards_map: dict[str, dict[str, int]] = {}
    counts: dict[str, int] = {}
    non_bomb_total = 0
    grand_total = 0

    for ctype, raw_cnt in raw_counts.items():
        if not isinstance(ctype, str) or ctype not in CARD_META:
            raise GameError(f"Loại thẻ không hợp lệ: {ctype}")
        if isinstance(raw_cnt, bool):
            raise GameError(f"Số lượng thẻ '{ctype}' không hợp lệ")
        try:
            cnt = int(raw_cnt)
        except (TypeError, ValueError):
            raise GameError(f"Số lượng thẻ '{ctype}' không hợp lệ") from None
        if cnt < 0 or cnt > MAX_PER_CARD_TYPE:
            raise GameError(f"Số lượng '{ctype}' phải từ 0 đến {MAX_PER_CARD_TYPE}")
        if ctype == "explodingkitten":
            # Game.start() tự chèn N-1/N Exploding Kitten theo số người chơi
            continue
        if cnt == 0:
            continue
        base_vars = (
            raw_cards.get(ctype)
            if isinstance(raw_cards, dict) and isinstance(raw_cards.get(ctype), dict)
            else preset_cards.get(ctype)
        )
        cards_map[ctype] = _distribute_card_variants(ctype, cnt, base_vars)
        counts[ctype] = cnt
        grand_total += cnt
        if ctype != "implodingkitten":
            non_bomb_total += cnt

    if non_bomb_total < MIN_CUSTOM_NONBOMB_CARDS:
        raise GameError(f"Bộ bài cần tối thiểu {MIN_CUSTOM_NONBOMB_CARDS} lá thường")
    if grand_total > MAX_CUSTOM_CARD_TOTAL:
        raise GameError(f"Bộ bài không được vượt quá {MAX_CUSTOM_CARD_TOTAL} lá")

    raw_desc = raw.get("description")
    if isinstance(raw_desc, str) and raw_desc.strip():
        description = raw_desc.strip()[:140]
    elif preset_detail:
        description = f"Tùy chỉnh từ {preset_detail['title']} · bởi {creator}"
    else:
        description = f"Bộ bài tự tạo ({grand_total} lá) · bởi {creator}"

    theme_color = (
        preset_detail.get("theme_color")
        if preset_detail and preset_detail.get("theme_color")
        else "#f25c3b"
    )
    return {
        "id": desk_id,
        "title": title,
        "deck_type": "Custom",
        "preset": preset,
        "created_by": creator,
        "card_count": grand_total,
        "description": description,
        "theme_color": theme_color,
        "counts": counts,
        "cards": cards_map,
    }
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I/1/O/0


def _is_debug_enabled() -> bool:
    return os.environ.get("EK_DEBUG") == "1"


DEBUG_ENABLED = _is_debug_enabled()


class SessionError(GameError):
    """Lỗi phiên/kết nối: client phải dừng retry với mã đóng terminal."""

    def __init__(self, message: str, code: str = "SESSION_INVALID") -> None:
        super().__init__(message)
        self.code = code


class RoomUnavailableError(SessionError):
    """Phòng không vào được (đầy hoặc đã bắt đầu): mã đóng terminal 4403."""

    def __init__(self, message: str, code: str = "ROOM_UNAVAILABLE") -> None:
        super().__init__(message, code=code)


class RoomFullError(RoomUnavailableError):
    """Phòng đã đầy: client phải dừng retry với mã đóng terminal riêng."""

    def __init__(self, message: str, code: str = "ROOM_FULL") -> None:
        super().__init__(message, code=code)


class InvalidActionError(GameError):
    """Gói tin hoặc lệnh WebSocket không hợp lệ."""

    def __init__(self, message: str, code: str = "INVALID_ACTION") -> None:
        super().__init__(message)
        self.code = code


class Room:
    def __init__(self, code: str, manager: "RoomManager | None" = None) -> None:
        self.code = code
        self.display_code = code
        self.real_code = code
        self._manager = manager
        self.votes: dict[str, str] = {}  # name -> desk được vote (lobby)
        self.custom_desks: dict[str, dict] = {}  # id -> custom desk spec trong phòng
        self._custom_desk_seq: int = 0
        self.avatars: dict[str, dict[str, str]] = {}  # name -> cấu hình mèo tuỳ chỉnh
        self.game: Game | None = None
        self.conns: dict[str, WebSocket] = {}  # name -> ws hiện tại
        self.sessions: dict[str, str] = {}  # name -> token reconnect không đoán được
        self.spectators: set[str] = set()
        self._disconnected_at: dict[str, float] = {}  # lobby: thời điểm ngắt kết nối
        self.last_active = time.time()
        self._lock = asyncio.Lock()
        self._nope_task: asyncio.Task | None = None
        self._turn_timer_task: asyncio.Task | None = None
        self._turn_timer_deadline: float | None = None
        self._turn_timer_key: tuple | None = None
        self._turn_timer_seq: int = 0
        self._loading: dict | None = None
        self._loading_task: asyncio.Task | None = None
        self._empty_since: float | None = None
        self._empty_seq: int = 0
        self._empty_task: asyncio.Task | None = None

    def touch(self) -> None:
        self.last_active = time.time()

    def _mark_occupied(self) -> None:
        self._empty_since = None
        self._empty_seq += 1
        self._cancel_empty_timer()

    def _is_spectator(self, name: str) -> bool:
        if self.game is not None:
            return name not in self.game.names
        if self._loading is not None:
            return name not in self._loading["players"]
        return False

    def is_started(self) -> bool:
        return self.game is not None or self._loading is not None

    def current_phase(self) -> str:
        if self.game is not None:
            return self.game.phase
        if self._loading is not None:
            return "loading"
        return "lobby"

    def player_count(self) -> int:
        return len([n for n in self.conns if not self._is_spectator(n)])

    def spectator_count(self) -> int:
        return len([n for n in self.conns if self._is_spectator(n)])

    def _sync_spectators_set(self) -> None:
        self.spectators = {n for n in self.conns if self._is_spectator(n)}

    def _rotate_rematch_code(self) -> str:
        if self._manager is not None:
            return self._manager.reallocate_room(self)
        old_real = self.real_code
        while True:
            new_real = "".join(random.choices(CODE_ALPHABET, k=4))
            if new_real != old_real:
                break
        self.real_code = new_real
        return new_real

    def _prune_lobby_sessions(self, now: float | None = None) -> None:
        """Dọn session lobby đã rời quá hạn hoặc vượt ngưỡng để tránh rò bộ nhớ."""
        if self.game is not None or self._loading is not None:
            return
        moment = now if now is not None else time.time()
        expired = [
            n for n, ts in self._disconnected_at.items()
            if n not in self.conns and (moment - ts) > LOBBY_SESSION_TTL_SECONDS
        ]
        for n in expired:
            self._disconnected_at.pop(n, None)
            self.sessions.pop(n, None)
            self.avatars.pop(n, None)
        disconnected = [
            (ts, n) for n, ts in self._disconnected_at.items() if n not in self.conns
        ]
        if len(disconnected) > MAX_DISCONNECTED_LOBBY_SESSIONS:
            disconnected.sort()
            for _, n in disconnected[:-MAX_DISCONNECTED_LOBBY_SESSIONS]:
                self._disconnected_at.pop(n, None)
                self.sessions.pop(n, None)
                self.avatars.pop(n, None)

    # ---------- phiên ----------

    async def join(self, name: str, ws: WebSocket, session: str | None = None) -> str:
        """Kiểm tra điều kiện vào phòng và đăng ký socket nguyên tử dưới lock."""
        async with self._lock:
            clean = (name or "").strip()
            if not clean or len(clean) > 64:
                raise SessionError("Tên không hợp lệ", code="INVALID_NAME")
            return self.register(clean, ws, session)

    def register(self, name: str, ws: WebSocket, session: str | None = None) -> str:
        """Đăng ký socket cho một tên, chống chiếm đoạt socket đang hoạt động."""
        clean = (name or "").strip()
        if not clean or len(clean) > 64:
            raise SessionError("Tên không hợp lệ", code="INVALID_NAME")
        self.touch()
        self._prune_lobby_sessions()
        is_spec = self._is_spectator(clean)
        current = self.conns.get(clean)
        if current is None:
            if is_spec:
                if self.spectator_count() >= MAX_SPECTATORS:
                    raise RoomFullError("Phòng khán giả đã đầy (tối đa 20)")
            elif self.game is None and self._loading is None:
                if len(self.conns) >= MAX_PLAYERS:
                    raise RoomFullError("Phòng đã đầy (tối đa 9)")

            if clean in self.sessions and session == self.sessions[clean]:
                # chủ token cũ nhận lại ghế: giữ nguyên token
                self._disconnected_at.pop(clean, None)
                self.conns[clean] = ws
                self._mark_occupied()
                self._sync_spectators_set()
                return self.sessions[clean]

            # tên mới, khán giả mới, hoặc người chơi trong ván mất kết nối quay lại:
            # luôn cấp token mới không đoán được (chống fixation)
            token = secrets.token_urlsafe(16)
            self._disconnected_at.pop(clean, None)
            self.sessions[clean] = token
            self.conns[clean] = ws
            self._mark_occupied()
            self._sync_spectators_set()
            return token
        if session is not None and session == self.sessions.get(clean):
            old = current
            self._disconnected_at.pop(clean, None)
            self.conns[clean] = ws
            self._mark_occupied()
            self._sync_spectators_set()
            if old is not None and old is not ws:
                self._close_later(old, TAKEOVER_CLOSE_CODE)
            return session
        raise SessionError("Tên đã có người dùng ở kết nối khác", code="NAME_TAKEN")

    def leave(self, name: str, ws: WebSocket, *, clear_session: bool = False) -> bool:
        clean = (name or "").strip()
        if self.conns.get(clean) is ws:
            is_spec = self._is_spectator(clean)
            del self.conns[clean]
            self.spectators.discard(clean)
            self.touch()
            if not self.conns:
                self._empty_since = time.time()
            if self.game is None and self._loading is None:
                # Rời lobby hẳn thì vote cũ không còn hiệu lực.
                self.votes.pop(clean, None)
                if clear_session:
                    self.sessions.pop(clean, None)
                    self._disconnected_at.pop(clean, None)
                    self.avatars.pop(clean, None)
                else:
                    self._disconnected_at[clean] = time.time()
            elif is_spec:
                self.sessions.pop(clean, None)
                self._disconnected_at.pop(clean, None)
                self.avatars.pop(clean, None)
            elif clear_session and (
                (self.game is not None and self.game.phase == "ended")
                or self._loading is not None
            ):
                self.sessions.pop(clean, None)
                self._disconnected_at.pop(clean, None)
                self.avatars.pop(clean, None)
            elif self.game is not None and self.game.phase == "playing":
                player = self.game.players.get(clean)
                if player is not None and not player.alive:
                    self.game.auto_resolve_dead_pending(include_revive=True)
            return True
        return False

    async def handle_disconnect(self, name: str, ws: WebSocket) -> None:
        """Xử lý ngắt kết nối dưới lock: rời ghế, auto-resolve dead pending, đồng bộ timer và broadcast."""
        async with self._lock:
            if not self.leave(name, ws):
                return
            if not self.conns:
                self._sync_empty_timer_locked()
            if self._loading is not None:
                connected_players = [n for n in self._loading["players"] if n in self.conns]
                if len(connected_players) < 2 or all(n in self._loading["ready"] for n in connected_players):
                    await self._finish_loading_locked()
                    return
            if self.game is not None and self.game.phase == "playing":
                self._sync_nope_timer_locked(self.game)
                self._sync_turn_timer_locked(self.game, reset=False)
            await self._broadcast_locked()

    def _require_sender(self, name: str, ws: WebSocket | None, session: str | None) -> None:
        clean = (name or "").strip()
        expected = self.sessions.get(clean)
        if expected is None or session != expected:
            raise SessionError("Phiên không hợp lệ, hãy vào lại phòng", code="SESSION_INVALID")
        if ws is not None and self.conns.get(clean) is not ws:
            raise SessionError("Kết nối đã cũ", code="SESSION_INVALID")

    # ---------- gửi ----------

    async def push_all(self) -> None:
        async with self._lock:
            await self._broadcast_locked()

    async def _broadcast_locked(self, _depth: int = 0) -> None:
        targets = list(self.conns.items())
        if not targets:
            return
        payloads = [(name, ws, {"type": "state", "view": self._view_for(name)})
                    for name, ws in targets]
        results = await asyncio.gather(
            *(self._send_one(ws, payload) for _, ws, payload in payloads),
            return_exceptions=True,
        )
        failed: list[tuple[str, WebSocket]] = []
        for (name, ws, _), result in zip(payloads, results):
            if result is not None and self.conns.get(name) is ws:
                was_spec = self._is_spectator(name)
                del self.conns[name]
                self.spectators.discard(name)
                if self.game is None and self._loading is None:
                    # socket chết rớt khỏi lobby thì vote của họ cũng hết hiệu lực
                    self.votes.pop(name, None)
                    self._disconnected_at[name] = time.time()
                elif was_spec:
                    self.sessions.pop(name, None)
                    self.avatars.pop(name, None)
                failed.append((name, ws))
        for name, ws in failed:
            logger.warning("Dropping failed socket for %s in room %s", name, self.code)
            self._close_later(ws, 1011)
        if failed and not self.conns:
            self._sync_empty_timer_locked()
        if failed and self.conns and _depth < 2:
            # Báo ngay cho người còn lại biết roster/connected đã cập nhật.
            await self._broadcast_locked(_depth=_depth + 1)

    @staticmethod
    async def _send_one(ws: WebSocket, payload: dict) -> Exception | None:
        try:
            await asyncio.wait_for(ws.send_json(payload), timeout=SEND_TIMEOUT)
            return None
        except Exception as exc:  # socket chậm/chết: dọn ở caller, không chặn phòng
            return exc

    @staticmethod
    def _close_later(ws: WebSocket, code: int) -> None:
        async def _close() -> None:
            try:
                await ws.close(code=code)
            except Exception:
                pass

        task = asyncio.create_task(_close())
        task.add_done_callback(lambda _: task.exception() if not task.cancelled() else None)

    def _turn_timer_view(self) -> dict | None:
        g = self.game
        if (
            g is None
            or g.phase != "playing"
            or g.nope is not None
            or g.pending is not None
            or self._turn_timer_deadline is None
        ):
            return None
        now_ms = int(time.time() * 1000)
        ends_ms = int(self._turn_timer_deadline * 1000)
        return {
            "actor": g.order[g.turn_index],
            "ends_ms": ends_ms,
            "server_now_ms": now_ms,
            "remaining_ms": max(0, ends_ms - now_ms),
            "duration_ms": int(round(_turn_seconds() * 1000)),
        }

    def _view_for(self, name: str) -> dict:
        debug_enabled = _is_debug_enabled()
        spec_count = self.spectator_count()
        if self._loading is not None:
            is_spec = name not in self._loading["players"]
            now_ms = int(time.time() * 1000)
            ends_ms = int(self._loading["ends_at"] * 1000)
            return {
                "phase": "loading",
                "debug_enabled": debug_enabled,
                "display_code": self.display_code,
                "real_code": self.real_code,
                "spectator_count": spec_count,
                "turn_timer": None,
                "loading": {
                    "desk": self._loading["desk"],
                    "images": list(self._loading["images"]),
                    "ready": sorted(self._loading["ready"]),
                    "players": list(self._loading["players"]),
                    "total": len(self._loading["players"]),
                    "ends_ms": ends_ms,
                    "server_now_ms": now_ms,
                    "remaining_ms": max(0, ends_ms - now_ms),
                },
                "players": [
                    {
                        "name": n,
                        "count": 0,
                        "alive": True,
                        "connected": n in self.conns,
                        "avatar": self.avatars.get(n),
                    }
                    for n in self._loading["players"]
                ],
                "deck_count": 0,
                "stash_count": 0,
                "votes": dict(self.votes),
                "custom_desks": [
                    {k: v for k, v in d.items() if k != "cards"}
                    for d in self.custom_desks.values()
                ],
                "you": {
                    "name": name,
                    "alive": not is_spec,
                    "spectator": is_spec,
                    "hand": [],
                    "hand_count": 0,
                    "blind": False,
                    "marked": None,
                    "illtake_by": None,
                    "extra_turns": 0,
                    "session": self.sessions.get(name),
                },
            }
        if self.game is None:
            # cùng shape với game.view() để frontend không phải đoán
            return {
                "phase": "lobby",
                "debug_enabled": debug_enabled,
                "display_code": self.display_code,
                "real_code": self.real_code,
                "spectator_count": 0,
                "turn_timer": None,
                "players": [
                    {
                        "name": n,
                        "count": 0,
                        "alive": True,
                        "connected": True,
                        "avatar": self.avatars.get(n),
                    }
                    for n in sorted(self.conns)
                ],
                "deck_count": 0,
                "stash_count": 0,
                "votes": dict(self.votes),
                "custom_desks": [
                    {k: v for k, v in d.items() if k != "cards"}
                    for d in self.custom_desks.values()
                ],
                "you": {
                    "name": name,
                    "alive": True,
                    "spectator": False,
                    "hand": [],
                    "hand_count": 0,
                    "session": self.sessions.get(name),
                },
            }

        is_spec = name not in self.game.names
        if is_spec:
            view = self.game.view(self.game.order[0])
            view["you"] = {
                "name": name,
                "alive": False,
                "spectator": True,
                "hand": [],
                "hand_count": 0,
                "blind": False,
                "marked": None,
                "illtake_by": None,
                "extra_turns": 0,
                "session": self.sessions.get(name),
            }
            public_entries = [
                {"seq": seq, "text": text}
                for seq, text, viewer in self.game.log_entries
                if viewer is None
            ][-30:]
            view["log_entries"] = public_entries
            view["log"] = [e["text"] for e in public_entries]
            pending = view.get("pending")
            if isinstance(pending, dict):
                pdata = pending.get("data") or {}
                reason = pdata.get("reason")
                view["pending"] = {
                    "kind": pending.get("kind"),
                    "owner": pending.get("owner"),
                    "data": {"reason": reason} if reason is not None else {},
                }
            if isinstance(view.get("nope_window"), dict):
                view["nope_window"]["you_responded"] = False
            for p in view.get("players", []):
                gp = self.game.players.get(p["name"])
                if gp is not None:
                    p["marked"] = next(
                        (c.to_dict() for c in gp.hand if c.id == gp.marked_id),
                        None,
                    )
        else:
            view = self.game.view(name)
            view["you"]["spectator"] = False
            view["you"]["session"] = self.sessions.get(name)

        view["debug_enabled"] = debug_enabled
        view["display_code"] = self.display_code
        view["real_code"] = self.real_code
        view["spectator_count"] = spec_count
        for p in view.get("players", []):
            p["connected"] = p["name"] in self.conns
            p["avatar"] = self.avatars.get(p["name"])
        nw = view.get("nope_window")
        if isinstance(nw, dict):
            now_ms = int(time.time() * 1000)
            nw["server_now_ms"] = now_ms
            ends_ms = nw.get("ends_ms")
            if isinstance(ends_ms, (int, float)):
                nw["remaining_ms"] = max(0, int(ends_ms) - now_ms)
        view["turn_timer"] = self._turn_timer_view()
        return view

    # ---------- debug orchestration (EK_DEBUG=1) ----------

    @staticmethod
    def _parse_int(raw, key: str, default: int = 0) -> int:
        if raw is None or raw == "":
            return default
        if isinstance(raw, bool):
            raise GameError(f"{key} không hợp lệ")
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise GameError(f"{key} không hợp lệ") from None

    def _debug_snapshot_locked(self) -> dict:
        return {
            "code": self.display_code,
            "display_code": self.display_code,
            "real_code": self.real_code,
            "started": self.is_started(),
            "phase": self.current_phase(),
            "connected_players": sorted(n for n in self.conns if not self._is_spectator(n)),
            "spectator_count": self.spectator_count(),
            "votes": dict(self.votes),
            "debug_enabled": _is_debug_enabled(),
            "game": self.game.debug_snapshot() if self.game else None,
        }

    async def debug_inspect(self) -> dict:
        async with self._lock:
            if not _is_debug_enabled():
                raise GameError("Debug đã tắt")
            return self._debug_snapshot_locked()

    async def debug_exec(self, op: str, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise GameError("Payload debug không hợp lệ")
        async with self._lock:
            if not _is_debug_enabled():
                raise GameError("Debug đã tắt")
            self.touch()
            if op == "start":
                if self.is_started():
                    raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
                await self._start_game_locked()
                return self._debug_snapshot_locked()
            if op == "return_lobby":
                self._cancel_timers()
                self._loading = None
                self.game = None
                self.votes = {}
                self.spectators.clear()
                self._disconnected_at.clear()
                self.sessions = {n: t for n, t in self.sessions.items() if n in self.conns}
                await self._broadcast_locked()
                return self._debug_snapshot_locked()

            game_ops = {
                "give",
                "put_deck",
                "remove_card",
                "set_turn",
                "toggle_blind",
                "resolve_nope",
                "clear_pending",
                "force_draw",
                "scenario_boom",
            }
            if op not in game_ops:
                raise GameError(f"Debug op lạ: {op}")

            g = self._require_game()
            if op == "give":
                target = self._need_text(payload, "target")
                ctype = self._need_text(payload, "ctype")
                variant = self._parse_int(payload.get("variant", 0), "variant", default=0)
                g.debug_give(target, ctype, variant)
            elif op == "put_deck":
                ctype = self._need_text(payload, "ctype")
                index = self._parse_int(payload.get("index", 0), "index", default=0)
                variant = self._parse_int(payload.get("variant", 0), "variant", default=0)
                faceup = bool(payload.get("faceup", False))
                g.debug_put_deck(ctype, index=index, variant=variant, faceup=faceup)
            elif op == "remove_card":
                target = self._need_text(payload, "target")
                card_id = self._need_text(payload, "card_id")
                g.debug_remove_card(target, card_id)
            elif op == "set_turn":
                target = self._need_text(payload, "target")
                turns_left = self._parse_int(payload.get("turns_left", 1), "turns_left", default=1)
                g.debug_set_turn(target, turns_left)
            elif op == "toggle_blind":
                target = self._need_text(payload, "target")
                g.debug_toggle_blind(target)
            elif op == "resolve_nope":
                if g.nope:
                    g.resolve_nope()
            elif op == "clear_pending":
                g.pending = None
                g._cont = None
                g._say("[debug] đã hủy pending")
            elif op == "force_draw":
                target = payload.get("target") or g.current().name
                if not isinstance(target, str):
                    raise GameError("target không hợp lệ")
                g.draw(target)
            elif op == "scenario_boom":
                target = payload.get("target") or g.current().name
                if not isinstance(target, str):
                    raise GameError("target không hợp lệ")
                bomb_type = payload.get("bomb_type") or "explodingkitten"
                if bomb_type not in ("explodingkitten", "implodingkitten"):
                    raise GameError("bomb_type phải là explodingkitten hoặc implodingkitten")
                raw_faceup = payload.get("faceup")
                faceup = (bomb_type == "implodingkitten") if raw_faceup is None else bool(raw_faceup)
                keep_defuse = bool(payload.get("keep_defuse", False))
                auto_draw = bool(payload.get("auto_draw", False))

                g._require(g.phase == "playing", "Ván chưa/không diễn ra")
                p = g._get(target)
                g._require(p.alive, f"{target} đã chết")

                g.pending = None
                g._cont = None
                g.nope = None
                g.nope_deadline = None
                g.debug_set_turn(target, 1)

                rescue_types = {"defuse", "zombiekitten", "godcat", "streakingkitten"}
                if not keep_defuse:
                    kept = []
                    for card in p.hand:
                        if card.type in rescue_types:
                            if p.marked_id == card.id:
                                p.marked_id = None
                            g._to_grave(card)
                        else:
                            kept.append(card)
                    p.hand = kept
                    p.standby_defuse = False
                elif not p.has_type("defuse"):
                    g.debug_give(target, "defuse")

                g.debug_put_deck(bomb_type, index=0, faceup=faceup)
                if auto_draw:
                    g.draw(target)

            await self._after_action_locked(reset_turn_timer=True)
            return self._debug_snapshot_locked()

    # ---------- kiểm tra gói tin ----------

    @staticmethod
    def _need_text(msg: dict, key: str) -> str:
        value = msg.get(key)
        if not isinstance(value, str) or not value:
            raise GameError(f"Thiếu {key}")
        return value

    @staticmethod
    def _need_name_list(msg: dict, key: str, need: int) -> list[str]:
        value = msg.get(key)
        if not isinstance(value, list) or len(value) != need:
            raise GameError(f"Cần chọn đúng {need} lá")
        if any(not isinstance(item, str) or not item for item in value):
            raise GameError(f"Danh sách {key} không hợp lệ")
        return value

    # ---------- hành động ----------

    async def handle(self, name: str, msg: dict, ws: WebSocket | None = None,
                     session: str | None = None) -> None:
        """Xử lý 1 lệnh từ client; raise GameError ra ngoài nếu sai."""
        if not isinstance(msg, dict):
            raise InvalidActionError("Gói tin không hợp lệ")
        async with self._lock:
            self._require_sender(name, ws, session)
            self.touch()
            act = msg.get("action")
            if not isinstance(act, str) or not act:
                raise InvalidActionError("Thiếu action")
            clean = (name or "").strip()
            is_spec = self._is_spectator(clean)

            if act == "leave":
                if self.game is not None and self.game.phase != "ended" and not is_spec:
                    raise GameError("Không thể rời ghế khi ván đang diễn ra")
                if ws is not None:
                    self.leave(clean, ws, clear_session=True)
                else:
                    self.conns.pop(clean, None)
                    self.sessions.pop(clean, None)
                    self.spectators.discard(clean)
                    self._disconnected_at.pop(clean, None)
                    self.votes.pop(clean, None)
                    self.touch()
                if not self.conns:
                    self._delete_now_locked()
                    if ws is not None:
                        self._close_later(ws, 1000)
                    return
                if self._loading is not None and not is_spec:
                    if clean in self._loading["players"]:
                        self._loading["players"].remove(clean)
                    self._loading["ready"].discard(clean)
                    if len(self._loading["players"]) < 2:
                        self._cancel_loading_timer()
                        self._loading = None
                        self.spectators.clear()
                    else:
                        connected_players = [n for n in self._loading["players"] if n in self.conns]
                        if len(connected_players) >= 2 and all(n in self._loading["ready"] for n in connected_players):
                            await self._finish_loading_locked()
                            if ws is not None:
                                self._close_later(ws, 1000)
                            return
                await self._broadcast_locked()
                if ws is not None:
                    self._close_later(ws, 1000)
                return

            if is_spec:
                raise GameError("Đang ở chế độ khán giả — chờ ván sau")

            if act == "start":
                if self.is_started():
                    raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
                preload = bool(msg.get("preload", False))
                players = sorted(self.conns)
                if preload:
                    await self._begin_loading_locked(players=players, preferred_desk=None, is_rematch=False)
                else:
                    await self._start_game_locked(players=players)
                return
            if act == "rematch":
                if self._loading is not None or self.game is None or self.game.phase != "ended":
                    raise GameError("Chỉ có thể chơi lại khi ván đã kết thúc")
                old_connected = [n for n in self.game.names if n in self.conns]
                spec_connected = [n for n in sorted(self.conns) if n not in self.game.names]
                players = (old_connected + spec_connected)[:MAX_PLAYERS]
                if not (2 <= len(players) <= MAX_PLAYERS):
                    raise GameError("Cần 2–9 người trong phòng")
                preferred_desk = getattr(self.game, "desk_name", None)
                preload = bool(msg.get("preload", False))
                if preload:
                    await self._begin_loading_locked(
                        players=players,
                        preferred_desk=preferred_desk,
                        is_rematch=True,
                    )
                else:
                    await self._start_game_locked(
                        preferred_desk=preferred_desk,
                        players=players,
                        rotate_code=True,
                    )
                return
            if act == "return_lobby":
                if self._loading is not None or self.game is None or self.game.phase != "ended":
                    raise GameError("Chỉ có thể về phòng chờ khi ván đã kết thúc")
                old_names = set(self.game.names)
                self._cancel_timers()
                self.game = None
                self._loading = None
                self.votes = {}
                self.spectators.clear()
                self._disconnected_at.clear()
                if len(self.conns) > MAX_PLAYERS:
                    keep = [n for n in self.conns if n in old_names]
                    extras = [n for n in sorted(self.conns) if n not in old_names]
                    allowed = set((keep + extras)[:MAX_PLAYERS])
                    for drop_name in list(self.conns):
                        if drop_name not in allowed:
                            drop_ws = self.conns.pop(drop_name, None)
                            self.avatars.pop(drop_name, None)
                            if drop_ws is not None:
                                self._close_later(drop_ws, ROOM_UNAVAILABLE_CLOSE_CODE)
                self.sessions = {n: t for n, t in self.sessions.items() if n in self.conns}
                await self._broadcast_locked()
                return
            if act == "assets_ready":
                if self._loading is None:
                    if self.game is not None and self.game.phase == "playing":
                        return
                    raise GameError("Không ở trạng thái tải bộ bài")
                if clean in self._loading["players"]:
                    self._loading["ready"].add(clean)
                    connected_players = [n for n in self._loading["players"] if n in self.conns]
                    if len(connected_players) >= 2 and all(n in self._loading["ready"] for n in connected_players):
                        await self._finish_loading_locked()
                        return
                await self._broadcast_locked()
                return
            if act == "vote_desk":
                desk = msg.get("desk") or ""
                if desk not in available_desks() and desk not in self.custom_desks:
                    raise GameError(f"Không có bộ bài {desk}")
                if not self.is_started():
                    self.votes[clean] = desk
                    await self._broadcast_locked()
                return
            if act == "save_custom_desk":
                if self.is_started():
                    raise GameError("Không thể chỉnh sửa bộ bài khi ván đã bắt đầu")
                raw_id = msg.get("id")
                if raw_id is not None and raw_id != "":
                    if not isinstance(raw_id, str) or raw_id not in self.custom_desks:
                        raise GameError("Không tìm thấy bộ bài tùy chỉnh cần sửa")
                    if self.custom_desks[raw_id].get("created_by") != clean:
                        raise GameError("Chỉ người tạo mới có thể sửa bộ bài này")
                    desk_id = raw_id
                    next_seq = self._custom_desk_seq
                else:
                    if len(self.custom_desks) >= MAX_CUSTOM_DESKS:
                        raise GameError(f"Mỗi phòng chỉ lưu tối đa {MAX_CUSTOM_DESKS} bộ bài tùy chỉnh")
                    next_seq = self._custom_desk_seq + 1
                    desk_id = f"custom:{next_seq}"
                spec = build_custom_desk_spec(msg, creator=clean, desk_id=desk_id)
                self._custom_desk_seq = next_seq
                self.custom_desks[desk_id] = spec
                if msg.get("vote", True):
                    self.votes[clean] = desk_id
                await self._broadcast_locked()
                return
            if act == "delete_custom_desk":
                if self.is_started():
                    raise GameError("Không thể xóa bộ bài khi ván đã bắt đầu")
                desk_id = self._need_text(msg, "id")
                existing = self.custom_desks.get(desk_id)
                if existing is None:
                    raise GameError("Không tìm thấy bộ bài tùy chỉnh")
                if existing.get("created_by") != clean:
                    raise GameError("Chỉ người tạo mới có thể xóa bộ bài này")
                del self.custom_desks[desk_id]
                for voter in [v for v, voted in self.votes.items() if voted == desk_id]:
                    del self.votes[voter]
                await self._broadcast_locked()
                return
            if act == "set_avatar":
                clean_avatar = sanitize_avatar(msg.get("avatar"))
                self.avatars[clean] = clean_avatar
                await self._broadcast_locked()
                return
            if act not in ("play", "combo", "draw", "respond", "nope", "pass_nope", "play_now", "debug_give"):
                raise InvalidActionError(f"Lệnh lạ: {act}")
            g = self._require_game()
            if act == "play":
                as_type = msg.get("as_type")
                if as_type is not None and not isinstance(as_type, str):
                    raise GameError("as_type không hợp lệ")
                raw_card_id = msg.get("card_id")
                player = g.players.get(clean)
                if player is not None and player.blind:
                    if raw_card_id is not None and not isinstance(raw_card_id, str):
                        raise GameError("card_id không hợp lệ")
                    card_id = raw_card_id or ""
                else:
                    card_id = self._need_text(msg, "card_id")
                g.play_card(clean, card_id, as_type=as_type)
            elif act == "combo":
                combo = self._need_text(msg, "combo")
                if combo not in ("pair", "three"):
                    raise GameError("Combo không hợp lệ")
                need = 2 if combo == "pair" else 3
                g.play_combo(clean, combo, self._need_name_list(msg, "card_ids", need))
            elif act == "draw":
                g.draw(clean)
            elif act == "respond":
                payload = msg.get("payload", {})
                if payload is None:
                    payload = {}
                if not isinstance(payload, dict):
                    raise GameError("Payload quyết định không hợp lệ")
                g.respond(clean, payload)
            elif act == "nope":
                g.stack_nope(clean)
            elif act == "pass_nope":
                g.pass_nope(clean)
            elif act == "play_now":
                as_type = msg.get("as_type")
                if as_type is not None and not isinstance(as_type, str):
                    raise GameError("as_type không hợp lệ")
                g.play_now(clean, self._need_text(msg, "card_id"), as_type=as_type)
            elif act == "debug_give":
                if not _is_debug_enabled():
                    raise GameError("Debug đã tắt")
                ctype = self._need_text(msg, "ctype")
                raw_variant = msg.get("variant", 0)
                try:
                    variant = int(raw_variant or 0)
                except (TypeError, ValueError):
                    raise GameError("variant không hợp lệ") from None
                g.debug_give(clean, ctype, variant)
            else:
                raise InvalidActionError(f"Lệnh lạ: {act}")
            await self._after_action_locked(reset_turn_timer=True)

    def _require_game(self) -> Game:
        if self.game is None:
            raise GameError("Ván chưa bắt đầu")
        return self.game

    def _pick_desk(self, preferred_desk: str | None = None) -> str:
        desks = available_desks()
        if not desks and not self.custom_desks:
            raise GameError("Chưa có bộ bài nào")
        valid_votes = [
            d for d in self.votes.values()
            if d in desks or d in self.custom_desks
        ]
        if valid_votes:  # desk được vote nhiều nhất; hoà thì cái đầu tiên
            return Counter(valid_votes).most_common(1)[0][0]
        if preferred_desk and (preferred_desk in desks or preferred_desk in self.custom_desks):
            return preferred_desk
        return random.choice(desks)

    async def start_game(self) -> None:
        async with self._lock:
            if self.is_started():
                raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
            await self._start_game_locked()

    async def _begin_loading_locked(
        self,
        *,
        players: list[str],
        preferred_desk: str | None = None,
        is_rematch: bool = False,
    ) -> None:
        if not (2 <= len(players) <= MAX_PLAYERS):
            raise GameError("Cần 2–9 người trong phòng")
        desk = self._pick_desk(preferred_desk)
        custom = self.custom_desks.get(desk)
        images = desk_image_urls(desk, custom_cards=custom["cards"] if custom else None)
        self._cancel_timers()
        if is_rematch:
            self._rotate_rematch_code()
        self.game = None
        self.votes = {}
        self._disconnected_at.clear()
        self._loading = {
            "desk": desk,
            "images": images,
            "players": list(players),
            "ready": set(),
            "ends_at": time.time() + LOADING_TIMEOUT_SECONDS,
            "is_rematch": is_rematch,
        }
        self._sync_spectators_set()
        self._loading_task = asyncio.create_task(self._loading_timeout_timer(self._loading))
        await self._broadcast_locked()

    async def _finish_loading_locked(self) -> None:
        loading = self._loading
        if loading is None:
            return
        self._cancel_loading_timer()
        players = [n for n in loading["players"] if n in self.conns]
        if len(players) < 2:
            self._loading = None
            self.spectators.clear()
            await self._broadcast_locked()
            return
        desk = loading["desk"]
        self._loading = None
        await self._start_game_locked(preferred_desk=desk, players=players, forced_desk=desk)

    async def _start_game_locked(
        self,
        *,
        preferred_desk: str | None = None,
        players: list[str] | None = None,
        forced_desk: str | None = None,
        rotate_code: bool = False,
    ) -> None:
        names = list(players) if players is not None else sorted(self.conns)
        if not (2 <= len(names) <= MAX_PLAYERS):
            raise GameError("Cần 2–9 người trong phòng")
        desk = forced_desk or self._pick_desk(preferred_desk)
        custom = self.custom_desks.get(desk)
        # dựng + chia bài xong mới gán: start() hỏng thì lobby/vote còn nguyên
        game = Game(names, desk=desk, custom_desk=custom)
        game.start()
        game.announce_desk(custom["title"] if custom else desk)
        self._cancel_timers()
        if rotate_code:
            self._rotate_rematch_code()
        self._loading = None
        self.game = game
        self.votes = {}
        self.sessions = {n: t for n, t in self.sessions.items() if n in self.conns}
        self._disconnected_at.clear()
        self._sync_spectators_set()
        self._sync_turn_timer_locked(game, reset=True)
        logger.info("Started game in room %s (real=%s) with %d players (desk=%s)",
                    self.display_code, self.real_code, len(names), desk)
        await self._broadcast_locked()

    async def _after_action_locked(self, *, reset_turn_timer: bool = True) -> None:
        """Sau mọi lệnh: đồng bộ timer cửa sổ Nope, timer lượt rồi broadcast."""
        g = self.game
        if g is None:
            self._cancel_turn_timer()
            await self._broadcast_locked()
            return
        self._sync_nope_timer_locked(g)
        self._sync_turn_timer_locked(g, reset=reset_turn_timer)
        await self._broadcast_locked()

    def _sync_nope_timer_locked(self, g: Game) -> None:
        if g.nope is None:
            self._cancel_nope_timer()
            return
        if g.nope_deadline is not None and g.nope_all_responded():
            self._cancel_nope_timer()
            g.resolve_nope()
            return
        if g.nope_deadline is None:
            # Cửa sổ Nope mới hoặc vừa chồng thêm Nope -> huỷ timer cũ và đặt lại 2s.
            self._cancel_nope_timer()
            g.nope_deadline = time.time() + NOPE_SECONDS
            self._nope_task = asyncio.create_task(self._nope_timer(g))

    def _sync_turn_timer_locked(self, g: Game, *, reset: bool = False) -> None:
        if g.phase != "playing" or g.nope is not None or g.pending is not None:
            self._cancel_turn_timer()
            return
        actor = g.order[g.turn_index]
        if not reset and self._turn_timer_task is not None and self._turn_timer_deadline is not None:
            return
        self._cancel_turn_timer()
        self._turn_timer_seq += 1
        duration = _turn_seconds()
        deadline = time.time() + duration
        key = (id(g), g.turn_index, g.turns_left, actor, self._turn_timer_seq)
        self._turn_timer_deadline = deadline
        self._turn_timer_key = key
        self._turn_timer_task = asyncio.create_task(self._turn_timer(g, key, deadline))

    # ---------- timer ----------

    def _cancel_nope_timer(self) -> None:
        task = self._nope_task
        if task:
            task.cancel()
        self._nope_task = None

    def _cancel_turn_timer(self) -> None:
        task = self._turn_timer_task
        if task:
            task.cancel()
        self._turn_timer_task = None
        self._turn_timer_deadline = None
        self._turn_timer_key = None

    def _cancel_loading_timer(self) -> None:
        task = self._loading_task
        if task:
            task.cancel()
        self._loading_task = None

    def _cancel_empty_timer(self) -> None:
        task = self._empty_task
        if task:
            task.cancel()
        self._empty_task = None

    def _cancel_timers(self) -> None:
        self._cancel_nope_timer()
        self._cancel_turn_timer()
        self._cancel_loading_timer()
        self._cancel_empty_timer()

    def _sync_empty_timer_locked(self) -> None:
        if self.conns:
            self._mark_occupied()
            return
        if self._empty_since is None:
            self._empty_since = time.time()
        if self._manager is None:
            return
        self._cancel_empty_timer()
        self._empty_seq += 1
        seq = self._empty_seq
        deadline = self._empty_since + EMPTY_DISCONNECT_TTL_SECONDS
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._empty_task = asyncio.create_task(self._empty_room_timer(seq, deadline))

    def _delete_now_locked(self) -> None:
        self._cancel_timers()
        self._loading = None
        if self._manager is not None:
            self._manager.delete_room(self)

    async def _nope_timer(self, game: Game) -> None:
        wait = max(0.0, (game.nope_deadline or 0) - time.time())
        await asyncio.sleep(wait)
        try:
            async with self._lock:
                if self._nope_task is asyncio.current_task():
                    self._nope_task = None
                if self.game is not game or game.nope is None:
                    return
                game.resolve_nope()
                self._sync_turn_timer_locked(game, reset=True)
                await self._broadcast_locked()
        except Exception:
            logger.exception("Unhandled error in Nope timer for room %s", self.code)

    async def _turn_timer(self, game: Game, expected_key: tuple, deadline: float) -> None:
        wait = max(0.0, deadline - time.time())
        await asyncio.sleep(wait)
        try:
            async with self._lock:
                if self._turn_timer_task is asyncio.current_task():
                    self._turn_timer_task = None
                if self.game is not game:
                    return
                if game.phase != "playing" or game.nope is not None or game.pending is not None:
                    return
                if self._turn_timer_key != expected_key:
                    return
                self._turn_timer_deadline = None
                self._turn_timer_key = None
                actor = game.order[game.turn_index]
                game._say(f"⏱️ Hết giờ lượt {actor} — tự động rút bài.")
                game.draw(actor)
                await self._after_action_locked(reset_turn_timer=True)
        except Exception:
            logger.exception("Unhandled error in Turn timer for room %s", self.code)

    async def _loading_timeout_timer(self, loading_ref: dict) -> None:
        wait = max(0.0, loading_ref["ends_at"] - time.time())
        await asyncio.sleep(wait)
        try:
            async with self._lock:
                if self._loading_task is asyncio.current_task():
                    self._loading_task = None
                if self._loading is not loading_ref:
                    return
                await self._finish_loading_locked()
        except Exception:
            logger.exception("Unhandled error in Loading timer for room %s", self.code)

    async def _empty_room_timer(self, expected_seq: int, deadline: float) -> None:
        wait = max(0.0, deadline - time.time())
        await asyncio.sleep(wait)
        try:
            async with self._lock:
                if self._empty_task is asyncio.current_task():
                    self._empty_task = None
                if self._empty_seq != expected_seq or self.conns or self._empty_since is None:
                    return
                self._delete_now_locked()
        except Exception:
            logger.exception("Unhandled error in Empty room timer for room %s", self.code)

    def is_idle(self, now: float | None = None) -> bool:
        if self.conns:
            return False
        moment = now if now is not None else time.time()
        if self._empty_since is not None:
            return (moment - self._empty_since) >= EMPTY_DISCONNECT_TTL_SECONDS
        idle_for = moment - self.last_active
        if self.game is None and self._loading is None:
            return idle_for > EMPTY_LOBBY_TTL_SECONDS
        if self.game is not None and self.game.phase == "ended":
            return idle_for > LOBBY_TTL_SECONDS
        return idle_for > GAME_TTL_SECONDS


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.aliases: dict[str, str] = {}  # display_code -> real_code

    def create(self) -> str:
        self.prune()
        if len(self.rooms) >= MAX_ROOMS:
            raise GameError("Máy chủ đã đầy phòng, hãy thử lại sau")
        while True:
            code = "".join(random.choices(CODE_ALPHABET, k=4))
            if code not in self.rooms and code not in self.aliases:
                break
        room = Room(code, manager=self)
        self.rooms[code] = room
        self.aliases[code] = code
        logger.info("Created room %s (total=%d)", code, len(self.rooms))
        return code

    def delete_room(self, room: Room) -> bool:
        room._cancel_timers()
        removed = False
        if self.rooms.get(room.real_code) is room:
            del self.rooms[room.real_code]
            removed = True
        if self.aliases.get(room.display_code) == room.real_code:
            del self.aliases[room.display_code]
        if removed:
            logger.info("Deleted room %s (real=%s)", room.display_code, room.real_code)
        return removed

    def reallocate_room(self, room: Room) -> str:
        """Cấp real_code mới khi rematch, giữ nguyên display_code trong aliases."""
        self.prune()
        old_real = room.real_code
        while True:
            new_real = "".join(random.choices(CODE_ALPHABET, k=4))
            if new_real not in self.rooms and new_real not in self.aliases:
                break
        if self.rooms.get(old_real) is room:
            del self.rooms[old_real]
        room.real_code = new_real
        self.rooms[new_real] = room
        self.aliases[room.display_code] = new_real
        logger.info("Reallocated rematch room %s -> real_code=%s", room.display_code, new_real)
        return new_real

    def get(self, code: str) -> Room | None:
        self.prune()
        upper = (code or "").upper()
        real = self.aliases.get(upper, upper)
        room = self.rooms.get(real)
        if room is not None and room.is_idle():
            self.delete_room(room)
            return None
        return room

    def active_rooms(self) -> list[Room]:
        self.prune()
        return list(self.rooms.values())

    def prune(self, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        for room in [r for r in self.rooms.values() if r.is_idle(moment)]:
            self.delete_room(room)


MANAGER = RoomManager()
