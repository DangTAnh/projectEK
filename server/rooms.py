"""Room: bọc Game với kết nối WebSocket, timer cửa sổ Nope, reconnect theo tên."""

import asyncio
import logging
import os
import random
import secrets
import time
from collections import Counter

from fastapi import WebSocket

from .engine import Game, GameError
from .engine.deck import available_desks

logger = logging.getLogger(__name__)

MAX_PLAYERS = 9
NOPE_SECONDS = 2
SEND_TIMEOUT = 5.0
MAX_ROOMS = 500
EMPTY_LOBBY_TTL_SECONDS = 300
LOBBY_TTL_SECONDS = 3600
GAME_TTL_SECONDS = 900
LOBBY_SESSION_TTL_SECONDS = 120
MAX_DISCONNECTED_LOBBY_SESSIONS = 64
TAKEOVER_CLOSE_CODE = 4001
AUTH_CLOSE_CODE = 4401
ROOM_UNAVAILABLE_CLOSE_CODE = 4403
UNKNOWN_ROOM_CLOSE_CODE = 4404

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
    def __init__(self, code: str) -> None:
        self.code = code
        self.votes: dict[str, str] = {}  # name -> desk được vote (lobby)
        self.avatars: dict[str, dict[str, str]] = {}  # name -> cấu hình mèo tuỳ chỉnh
        self.game: Game | None = None
        self.conns: dict[str, WebSocket] = {}  # name -> ws hiện tại
        self.sessions: dict[str, str] = {}  # name -> token reconnect không đoán được
        self._disconnected_at: dict[str, float] = {}  # lobby: thời điểm ngắt kết nối
        self.last_active = time.time()
        self._lock = asyncio.Lock()
        self._nope_task: asyncio.Task | None = None

    def touch(self) -> None:
        self.last_active = time.time()

    def _prune_lobby_sessions(self, now: float | None = None) -> None:
        """Dọn session lobby đã rời quá hạn hoặc vượt ngưỡng để tránh rò bộ nhớ."""
        if self.game is not None:
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
            if self.game is not None and clean not in self.game.names:
                raise RoomUnavailableError(
                    "Ván đã bắt đầu, không vào được nữa", code="GAME_STARTED"
                )
            return self.register(clean, ws, session)

    def register(self, name: str, ws: WebSocket, session: str | None = None) -> str:
        """Đăng ký socket cho một tên, chống chiếm đoạt bằng session token."""
        clean = (name or "").strip()
        if not clean or len(clean) > 64:
            raise SessionError("Tên không hợp lệ", code="INVALID_NAME")
        self.touch()
        self._prune_lobby_sessions()
        current = self.conns.get(clean)
        if current is None:
            if len(self.conns) >= MAX_PLAYERS:
                raise RoomFullError("Phòng đã đầy (tối đa 9)")
            if clean in self.sessions and session == self.sessions[clean]:
                # chủ token cũ nhận lại ghế: giữ nguyên token
                self._disconnected_at.pop(clean, None)
                self.conns[clean] = ws
                return self.sessions[clean]
            if self.game is not None and clean in self.sessions:
                raise SessionError(
                    "Cần mã phiên hợp lệ để kết nối lại ghế đang chơi",
                    code="SESSION_INVALID",
                )
            # tên mới hoặc nhận lại ghế theo tên ở lobby: luôn cấp token mới,
            # không nhận token do client tự đưa (chống fixation)
            token = secrets.token_urlsafe(16)
            self._disconnected_at.pop(clean, None)
            self.sessions[clean] = token
            self.conns[clean] = ws
            return token
        if session is not None and session == self.sessions.get(clean):
            old = current
            self._disconnected_at.pop(clean, None)
            self.conns[clean] = ws
            if old is not None and old is not ws:
                self._close_later(old, TAKEOVER_CLOSE_CODE)
            return session
        raise SessionError("Tên đã có người dùng ở kết nối khác", code="NAME_TAKEN")

    def leave(self, name: str, ws: WebSocket, *, clear_session: bool = False) -> bool:
        clean = (name or "").strip()
        if self.conns.get(clean) is ws:
            del self.conns[clean]
            self.touch()
            if self.game is None:
                # Rời lobby hẳn thì vote cũ không còn hiệu lực.
                self.votes.pop(clean, None)
                if clear_session:
                    self.sessions.pop(clean, None)
                    self._disconnected_at.pop(clean, None)
                    self.avatars.pop(clean, None)
                else:
                    self._disconnected_at[clean] = time.time()
            elif clear_session and self.game.phase == "ended":
                self.sessions.pop(clean, None)
                self._disconnected_at.pop(clean, None)
                self.avatars.pop(clean, None)
            return True
        return False

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
                del self.conns[name]
                if self.game is None:
                    # socket chết rớt khỏi lobby thì vote của họ cũng hết hiệu lực
                    self.votes.pop(name, None)
                    self._disconnected_at[name] = time.time()
                failed.append((name, ws))
        for name, ws in failed:
            logger.warning("Dropping failed socket for %s in room %s", name, self.code)
            self._close_later(ws, 1011)
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

    def _view_for(self, name: str) -> dict:
        debug_enabled = _is_debug_enabled()
        if self.game is None:
            # cùng shape với game.view() để frontend không phải đoán
            return {
                "phase": "lobby",
                "debug_enabled": debug_enabled,
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
                "you": {
                    "name": name,
                    "alive": True,
                    "hand": [],
                    "hand_count": 0,
                    "session": self.sessions.get(name),
                },
            }
        view = self.game.view(name)
        view["debug_enabled"] = debug_enabled
        view["you"]["session"] = self.sessions.get(name)
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
            "code": self.code,
            "started": self.game is not None,
            "phase": self.game.phase if self.game else "lobby",
            "connected_players": sorted(self.conns),
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
                if self.game is not None:
                    raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
                await self._start_game_locked()
                return self._debug_snapshot_locked()
            if op == "return_lobby":
                self._cancel_nope_timer()
                self.game = None
                self.votes = {}
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

            await self._after_action_locked()
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
            if act == "leave":
                if self.game is not None and self.game.phase != "ended":
                    raise GameError("Không thể rời ghế khi ván đang diễn ra")
                clean = (name or "").strip()
                if ws is not None:
                    self.leave(clean, ws, clear_session=True)
                else:
                    self.conns.pop(clean, None)
                    self.sessions.pop(clean, None)
                    self._disconnected_at.pop(clean, None)
                    self.votes.pop(clean, None)
                    self.touch()
                await self._broadcast_locked()
                if ws is not None:
                    self._close_later(ws, 1000)
                return
            if act == "start":
                if self.game is not None:
                    raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
                await self._start_game_locked()
                return
            if act == "rematch":
                if self.game is None or self.game.phase != "ended":
                    raise GameError("Chỉ có thể chơi lại khi ván đã kết thúc")
                await self._start_game_locked(
                    preferred_desk=getattr(self.game, "desk_name", None)
                )
                return
            if act == "return_lobby":
                if self.game is None or self.game.phase != "ended":
                    raise GameError("Chỉ có thể về phòng chờ khi ván đã kết thúc")
                self._cancel_nope_timer()
                self.game = None
                self.votes = {}
                self.sessions = {n: t for n, t in self.sessions.items() if n in self.conns}
                self._disconnected_at.clear()
                await self._broadcast_locked()
                return
            if act == "vote_desk":
                desk = msg.get("desk") or ""
                if desk not in available_desks():
                    raise GameError(f"Không có bộ bài {desk}")
                if self.game is None:
                    self.votes[name] = desk
                    await self._broadcast_locked()
                return
            if act == "set_avatar":
                clean_avatar = sanitize_avatar(msg.get("avatar"))
                self.avatars[name] = clean_avatar
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
                player = g.players.get(name)
                if player is not None and player.blind:
                    if raw_card_id is not None and not isinstance(raw_card_id, str):
                        raise GameError("card_id không hợp lệ")
                    card_id = raw_card_id or ""
                else:
                    card_id = self._need_text(msg, "card_id")
                g.play_card(name, card_id, as_type=as_type)
            elif act == "combo":
                combo = self._need_text(msg, "combo")
                if combo not in ("pair", "three"):
                    raise GameError("Combo không hợp lệ")
                need = 2 if combo == "pair" else 3
                g.play_combo(name, combo, self._need_name_list(msg, "card_ids", need))
            elif act == "draw":
                g.draw(name)
            elif act == "respond":
                payload = msg.get("payload", {})
                if payload is None:
                    payload = {}
                if not isinstance(payload, dict):
                    raise GameError("Payload quyết định không hợp lệ")
                g.respond(name, payload)
            elif act == "nope":
                g.stack_nope(name)
            elif act == "pass_nope":
                g.pass_nope(name)
            elif act == "play_now":
                as_type = msg.get("as_type")
                if as_type is not None and not isinstance(as_type, str):
                    raise GameError("as_type không hợp lệ")
                g.play_now(name, self._need_text(msg, "card_id"), as_type=as_type)
            elif act == "debug_give":
                if not _is_debug_enabled():
                    raise GameError("Debug đã tắt")
                ctype = self._need_text(msg, "ctype")
                raw_variant = msg.get("variant", 0)
                try:
                    variant = int(raw_variant or 0)
                except (TypeError, ValueError):
                    raise GameError("variant không hợp lệ") from None
                g.debug_give(name, ctype, variant)
            else:
                raise InvalidActionError(f"Lệnh lạ: {act}")
            await self._after_action_locked()

    def _require_game(self) -> Game:
        if self.game is None:
            raise GameError("Ván chưa bắt đầu")
        return self.game

    async def start_game(self) -> None:
        async with self._lock:
            if self.game is not None:
                raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
            await self._start_game_locked()

    async def _start_game_locked(self, *, preferred_desk: str | None = None) -> None:
        names = sorted(self.conns)
        if not (2 <= len(names) <= MAX_PLAYERS):
            raise GameError("Cần 2–9 người trong phòng")
        self._cancel_nope_timer()
        desks = available_desks()
        if not desks:
            raise GameError("Chưa có bộ bài nào")
        if self.votes:  # desk được vote nhiều nhất; hoà thì cái đầu tiên
            desk = Counter(self.votes.values()).most_common(1)[0][0]
        elif preferred_desk and preferred_desk in desks:
            desk = preferred_desk
        else:  # không ai vote -> ngẫu nhiên
            desk = random.choice(desks)
        # dựng + chia bài xong mới gán: start() hỏng thì lobby/vote còn nguyên
        game = Game(names, desk=desk)
        game.start()
        game.announce_desk(desk)
        self.game = game
        self.votes = {}
        self.sessions = {n: t for n, t in self.sessions.items() if n in self.conns}
        self._disconnected_at.clear()
        logger.info("Started game in room %s with %d players (desk=%s)", self.code, len(names), desk)
        await self._broadcast_locked()

    async def _after_action_locked(self) -> None:
        """Sau mọi lệnh: đồng bộ timer cửa sổ Nope rồi broadcast."""
        g = self.game
        if g is None:
            await self._broadcast_locked()
            return
        self._sync_nope_timer_locked(g)
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

    # ---------- timer ----------

    def _cancel_nope_timer(self) -> None:
        task = self._nope_task
        if task:
            task.cancel()
        self._nope_task = None

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
                await self._broadcast_locked()
        except Exception:
            logger.exception("Unhandled error in Nope timer for room %s", self.code)

    def is_idle(self, now: float | None = None) -> bool:
        if self.conns:
            return False
        idle_for = (now if now is not None else time.time()) - self.last_active
        if self.game is None:
            return idle_for > EMPTY_LOBBY_TTL_SECONDS
        if self.game.phase == "ended":
            return idle_for > LOBBY_TTL_SECONDS
        return idle_for > GAME_TTL_SECONDS


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}

    def create(self) -> str:
        self.prune()
        if len(self.rooms) >= MAX_ROOMS:
            raise GameError("Máy chủ đã đầy phòng, hãy thử lại sau")
        while True:
            code = "".join(random.choices(CODE_ALPHABET, k=4))
            if code not in self.rooms:
                break
        self.rooms[code] = Room(code)
        logger.info("Created room %s (total=%d)", code, len(self.rooms))
        return code

    def get(self, code: str) -> Room | None:
        self.prune()
        room = self.rooms.get((code or "").upper())
        if room is not None and room.is_idle():
            room._cancel_nope_timer()
            del self.rooms[room.code]
            logger.info("Pruned idle room %s on lookup", room.code)
            return None
        return room

    def active_rooms(self) -> list[Room]:
        self.prune()
        return list(self.rooms.values())

    def prune(self, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        for code in [code for code, room in self.rooms.items() if room.is_idle(moment)]:
            room = self.rooms.pop(code, None)
            if room is not None:
                room._cancel_nope_timer()
                logger.info("Pruned idle room %s", code)


MANAGER = RoomManager()
