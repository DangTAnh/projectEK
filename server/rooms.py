"""Room: bọc Game với kết nối WebSocket, timer cửa sổ Nope, reconnect theo tên."""

import asyncio
import os
import random
import secrets
import string
import time
from collections import Counter

from fastapi import WebSocket

from .engine import Game, GameError
from .engine.deck import available_desks

NOPE_SECONDS = 5
SEND_TIMEOUT = 5.0
MAX_ROOMS = 500
LOBBY_TTL_SECONDS = 3600
GAME_TTL_SECONDS = 900
TAKEOVER_CLOSE_CODE = 4001
AUTH_CLOSE_CODE = 4401
ROOM_UNAVAILABLE_CLOSE_CODE = 4403
UNKNOWN_ROOM_CLOSE_CODE = 4404
DEBUG_ENABLED = os.environ.get("EK_DEBUG") == "1"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ I/1/O/0


class SessionError(GameError):
    """Lỗi phiên/kết nối: client phải dừng retry với mã đóng terminal."""

class RoomFullError(SessionError):
    """Phòng đã đầy: client phải dừng retry với mã đóng terminal riêng."""


class Room:
    def __init__(self, code: str) -> None:
        self.code = code
        self.votes: dict[str, str] = {}  # name -> desk được vote (lobby)
        self.game: Game | None = None
        self.conns: dict[str, WebSocket] = {}  # name -> ws hiện tại
        self.sessions: dict[str, str] = {}  # name -> token reconnect không đoán được
        self.last_active = time.time()
        self._lock = asyncio.Lock()
        self._nope_task: asyncio.Task | None = None

    def touch(self) -> None:
        self.last_active = time.time()

    # ---------- phiên ----------

    def register(self, name: str, ws: WebSocket, session: str | None = None) -> str:
        """Đăng ký socket cho một tên, chống chiếm đoạt bằng session token."""
        clean = (name or "").strip()
        if not clean or len(clean) > 64:
            raise SessionError("Tên không hợp lệ")
        self.touch()
        current = self.conns.get(clean)
        if current is None:
            if clean in self.sessions and session == self.sessions[clean]:
                # chủ token cũ nhận lại ghế: giữ nguyên token
                self.conns[clean] = ws
                return self.sessions[clean]
            if clean not in self.sessions and len(self.conns) >= 9:
                raise RoomFullError("Phòng đã đầy (tối đa 9)")
            # tên mới hoặc nhận lại ghế theo tên: luôn cấp token mới,
            # không nhận token do client tự đưa (chống fixation)
            token = secrets.token_urlsafe(16)
            self.sessions[clean] = token
            self.conns[clean] = ws
            return token
        if session is not None and session == self.sessions.get(clean):
            old = current
            self.conns[clean] = ws
            if old is not None and old is not ws:
                self._close_later(old, TAKEOVER_CLOSE_CODE)
            return session
        raise SessionError("Tên đã có người dùng ở kết nối khác")

    def leave(self, name: str, ws: WebSocket) -> bool:
        clean = (name or "").strip()
        if self.conns.get(clean) is ws:
            del self.conns[clean]
            self.touch()
            if self.game is None:
                # Rời lobby hẳn thì vote cũ không còn hiệu lực.
                self.votes.pop(clean, None)
            return True
        return False

    def _require_sender(self, name: str, ws: WebSocket | None, session: str | None) -> None:
        clean = (name or "").strip()
        expected = self.sessions.get(clean)
        if expected is None or session != expected:
            raise SessionError("Phiên không hợp lệ, hãy vào lại phòng")
        if ws is not None and self.conns.get(clean) is not ws:
            raise SessionError("Kết nối đã cũ")

    # ---------- gửi ----------

    async def push_all(self) -> None:
        async with self._lock:
            await self._broadcast_locked()

    async def _broadcast_locked(self) -> None:
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
                failed.append((name, ws))
        for _, ws in failed:
            self._close_later(ws, 1011)

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
        if self.game is None:
            # cùng shape với game.view() để frontend không phải đoán
            return {
                "phase": "lobby",
                "players": [{"name": n, "count": 0, "alive": True} for n in sorted(self.conns)],
                "deck_count": 0,
                "stash_count": 0,
                "votes": dict(self.votes),
                "you": {
                    "name": name,
                    "alive": True,
                    "hand": [],
                    "session": self.sessions.get(name),
                },
            }
        view = self.game.view(name)
        view["you"]["session"] = self.sessions.get(name)
        return view

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
            raise GameError("Gói tin không hợp lệ")
        async with self._lock:
            self._require_sender(name, ws, session)
            self.touch()
            act = msg.get("action")
            if not isinstance(act, str) or not act:
                raise GameError("Thiếu action")
            if act == "start":
                if self.game is not None:
                    raise GameError("Ván đã bắt đầu, không thể bắt đầu lại")
                await self._start_game_locked()
                return
            if act == "vote_desk":
                desk = msg.get("desk") or ""
                if desk not in available_desks():
                    raise GameError(f"Không có bộ bài {desk}")
                if self.game is None:
                    self.votes[name] = desk
                    await self._broadcast_locked()
                return
            g = self._require_game()
            if act == "play":
                as_type = msg.get("as_type")
                if as_type is not None and not isinstance(as_type, str):
                    raise GameError("as_type không hợp lệ")
                g.play_card(name, self._need_text(msg, "card_id"), as_type=as_type)
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
                if not DEBUG_ENABLED:
                    raise GameError("Debug đã tắt")
                ctype = self._need_text(msg, "ctype")
                raw_variant = msg.get("variant", 0)
                try:
                    variant = int(raw_variant or 0)
                except (TypeError, ValueError):
                    raise GameError("variant không hợp lệ") from None
                g.debug_give(name, ctype, variant)
            else:
                raise GameError(f"Lệnh lạ: {act}")
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

    async def _start_game_locked(self) -> None:
        names = sorted(self.conns)
        if not (2 <= len(names) <= 9):
            raise GameError("Cần 2–9 người trong phòng")
        self._cancel_nope_timer()
        desks = available_desks()
        if not desks:
            raise GameError("Chưa có bộ bài nào")
        if self.votes:  # desk được vote nhiều nhất; hoà thì cái đầu tiên
            desk = Counter(self.votes.values()).most_common(1)[0][0]
        else:  # không ai vote -> ngẫu nhiên
            desk = random.choice(desks)
        # dựng + chia bài xong mới gán: start() hỏng thì lobby/vote còn nguyên
        game = Game(names, desk=desk)
        game.start()
        game.announce_desk(desk)
        self.game = game
        self.votes = {}
        await self._broadcast_locked()

    async def _after_action_locked(self) -> None:
        """Sau mọi lệnh: nếu cửa sổ Nope vừa mở -> đặt deadline + timer."""
        g = self.game
        if g is None:
            await self._broadcast_locked()
            return
        if g.nope is not None and g.nope_deadline is not None \
                and g.nope_all_responded():
            self._cancel_nope_timer()
            g.resolve_nope()
        elif g.nope is not None and g.nope_deadline is None:
            g.nope_deadline = time.time() + NOPE_SECONDS
            self._nope_task = asyncio.create_task(self._nope_timer(g))
        await self._broadcast_locked()

    # ---------- timer ----------

    def _cancel_nope_timer(self) -> None:
        task = self._nope_task
        if task:
            task.cancel()
        self._nope_task = None

    async def _nope_timer(self, game: Game) -> None:
        try:
            wait = max(0.0, (game.nope_deadline or 0) - time.time())
            await asyncio.sleep(wait)
        except asyncio.CancelledError:
            return
        async with self._lock:
            if self._nope_task is asyncio.current_task():
                self._nope_task = None
            if self.game is not game or game.nope is None:
                return
            game.resolve_nope()
            await self._broadcast_locked()

    def is_idle(self, now: float | None = None) -> bool:
        if self.conns:
            return False
        idle_for = (now if now is not None else time.time()) - self.last_active
        if self.game is None or self.game.phase == "ended":
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
        return code

    def get(self, code: str) -> Room | None:
        self.prune()
        room = self.rooms.get((code or "").upper())
        if room is not None and room.is_idle():
            del self.rooms[room.code]
            return None
        return room

    def active_rooms(self) -> list[Room]:
        self.prune()
        return list(self.rooms.values())

    def prune(self, now: float | None = None) -> None:
        moment = now if now is not None else time.time()
        for code in [code for code, room in self.rooms.items() if room.is_idle(moment)]:
            del self.rooms[code]


MANAGER = RoomManager()
