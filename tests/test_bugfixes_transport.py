"""Hồi quy transport cho server/main.py + server/rooms.py (không sửa test cũ)."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from server.engine import Game, GameError
from server.main import app
from server.rooms import MANAGER, Room, RoomFullError, SessionError

client = TestClient(app)


class StubSocket:
    def __init__(self, fail_send=False):
        self.sent = []
        self.closed = []
        self.fail_send = fail_send

    async def send_json(self, payload):
        if self.fail_send:
            raise RuntimeError("dead socket")
        self.sent.append(payload)

    async def close(self, code=1000):
        self.closed.append(code)


def _recv_state(ws, limit=50):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == "state":
            return msg["view"]
    raise AssertionError("không nhận được state")


def test_fresh_join_ignores_client_supplied_token():
    room = Room("FIX1")
    issued = room.register("An", StubSocket(), "attacker-chosen-token")
    assert issued != "attacker-chosen-token"
    assert room.sessions["An"] == issued


def test_token_owner_reclaims_same_token():
    room = Room("FIX2")
    ws = StubSocket()
    token = room.register("An", ws)
    assert room.leave("An", ws) is True
    assert room.register("An", StubSocket(), token) == token


def test_disconnected_name_reclaimable_by_name():
    room = Room("FIX3")
    ws = StubSocket()
    old = room.register("An", ws)
    assert room.leave("An", ws) is True
    new = room.register("An", StubSocket())
    assert new and new != old
    assert room.conns["An"] is not ws


def test_whitespace_name_matches_existing_session():
    room = Room("FIX4")
    ws = StubSocket()
    token = room.register("An", ws)
    assert token
    assert room.leave("  An  ", ws) is True
    assert "An" not in room.conns
    token2 = room.register("An", ws)
    with pytest.raises(SessionError):
        room.register(" An ", StubSocket())
    room._require_sender(" An ", ws, token2)


def test_register_enforces_capacity():
    room = Room("FIX5")
    for i in range(9):
        room.register(f"P{i}", StubSocket())
    with pytest.raises(RoomFullError):
        room.register("Late", StubSocket())
    assert "Late" not in room.conns
    assert issubclass(RoomFullError, SessionError)


def test_failed_broadcast_clears_ghost_vote():
    room = Room("FIX6")
    room.register("An", StubSocket())
    room.register("Binh", StubSocket(fail_send=True))
    room.votes = {"An": "original", "Binh": "original"}
    asyncio.run(room.push_all())
    assert "Binh" not in room.conns
    assert room.votes == {"An": "original"}


def test_start_build_failure_keeps_lobby(monkeypatch):
    room = Room("FIX7")
    room.register("An", StubSocket())
    room.register("Binh", StubSocket())
    room.votes = {"An": "original", "Binh": "original"}

    def boom(self):
        raise GameError("chia bài lỗi")

    monkeypatch.setattr(Game, "start", boom)
    with pytest.raises(GameError):
        asyncio.run(room.start_game())
    assert room.game is None
    assert room.votes == {"An": "original", "Binh": "original"}


def test_empty_desk_list_rejected(monkeypatch):
    room = Room("FIX8")
    room.register("An", StubSocket())
    room.register("Binh", StubSocket())
    monkeypatch.setattr("server.rooms.available_desks", lambda: [])
    with pytest.raises(GameError):
        asyncio.run(room.start_game())
    assert room.game is None


def test_nope_timer_clears_task_reference():
    room = Room("FIX9")
    game = SimpleNamespace(nope=None, nope_deadline=time.time())
    room.game = game

    async def go():
        room._nope_task = asyncio.current_task()
        await room._nope_timer(game)

    asyncio.run(go())
    assert room._nope_task is None


def test_blank_name_rejected_over_ws():
    code = MANAGER.create()
    with client.websocket_connect("/ws/%s?name=%%20%%20" % code) as ws:
        assert ws.receive_json()["type"] == "error"


def test_full_room_rejected_over_ws():
    code = MANAGER.create()
    room = MANAGER.get(code)
    for i in range(9):
        room.register(f"P{i}", StubSocket())
    with client.websocket_connect(f"/ws/{code}?name=Late") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "đầy" in msg["message"]


def test_disconnect_broadcasts_roster_to_remaining():
    code = MANAGER.create()
    with client.websocket_connect(f"/ws/{code}?name=An") as a:
        _recv_state(a)
        with client.websocket_connect(f"/ws/{code}?name=Binh") as b:
            _recv_state(b)
            _recv_state(a)
        view = _recv_state(a)
        assert [p["name"] for p in view["players"]] == ["An"]
