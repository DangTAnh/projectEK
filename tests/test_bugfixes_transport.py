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


def test_card_catalog_enriched_and_cached():
    from server.engine.cards import CARD_META, GODCAT_BANNED
    from server.main import _card_catalog

    first = _card_catalog()
    second = _card_catalog()
    assert first is second
    assert len(first) == len(CARD_META)
    skip = first["skip"]
    assert skip["type"] == "skip"
    assert skip["category"] == "action"
    assert skip["description"]
    assert skip["godcat_banned"] is False
    assert isinstance(skip["variants"], list) and 0 in skip["variants"]
    assert skip["image"].endswith(".jpg")
    for banned in GODCAT_BANNED:
        assert first[banned]["godcat_banned"] is True


def test_rest_health_room_lookup_and_enriched_cards():
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok" and isinstance(body["rooms"], int)

    missing = client.get("/api/rooms/ZZZZ")
    assert missing.status_code == 404
    assert missing.json()["code"] == "ROOM_NOT_FOUND"

    code = client.post("/api/rooms").json()["code"]
    found = client.get(f"/api/rooms/{code}")
    assert found.status_code == 200
    info = found.json()
    assert info["code"] == code
    assert info["player_count"] == 0
    assert info["max_players"] == 9
    assert info["started"] is False
    assert info["phase"] == "lobby"

    cards = client.get("/api/cards").json()
    assert cards["godcat"]["godcat_banned"] is True
    assert cards["skip"]["description"]
    assert isinstance(cards["skip"]["variants"], list)


def test_create_room_rate_limiter_unit():
    from server.main import CREATE_ROOM_RATE_LIMIT, _check_create_rate_limit, _create_room_hits

    ip = "198.51.100.77"
    _create_room_hits.pop(ip, None)
    try:
        t0 = 1000.0
        for _ in range(CREATE_ROOM_RATE_LIMIT):
            assert _check_create_rate_limit(ip, now=t0) is True
        assert _check_create_rate_limit(ip, now=t0 + 1.0) is False
        # sau khi cửa sổ trôi qua -> cho phép lại
        assert _check_create_rate_limit(ip, now=t0 + 61.0) is True
    finally:
        _create_room_hits.pop(ip, None)


def test_departed_lobby_player_cannot_bypass_capacity():
    room = Room("CAP1")
    ws_first = StubSocket()
    token = room.register("First", ws_first)
    assert room.leave("First", ws_first) is True
    for i in range(9):
        room.register(f"P{i}", StubSocket())
    with pytest.raises(RoomFullError) as exc_info:
        room.register("First", StubSocket(), token)
    assert exc_info.value.code == "ROOM_FULL"


def test_lobby_leave_clear_session_and_expiry():
    from server.rooms import LOBBY_SESSION_TTL_SECONDS

    room = Room("SES1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    room.register("An", ws_a)
    room.register("Binh", ws_b)
    assert room.leave("An", ws_a, clear_session=True) is True
    assert "An" not in room.sessions

    assert room.leave("Binh", ws_b) is True
    assert "Binh" in room.sessions
    room._prune_lobby_sessions(now=time.time() + LOBBY_SESSION_TTL_SECONDS + 5)
    assert "Binh" not in room.sessions


def test_active_game_disconnected_seat_requires_token():
    room = Room("ACT1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("An", ws_a)
    room.register("Binh", ws_b)
    room.game = Game(["An", "Binh"])
    room.game.start()

    assert room.leave("An", ws_a) is True
    with pytest.raises(SessionError) as exc_info:
        room.register("An", StubSocket())
    assert exc_info.value.code == "SESSION_INVALID"

    # Chủ token cũ vẫn kết nối lại được
    assert room.register("An", StubSocket(), tok_a) == tok_a


def test_prune_cancels_nope_timer_and_uses_empty_lobby_ttl():
    from server.rooms import EMPTY_LOBBY_TTL_SECONDS, RoomManager

    class FakeTask:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    mgr = RoomManager()
    room = Room("PRN1")
    fake = FakeTask()
    room._nope_task = fake
    room.last_active = 1000.0
    mgr.rooms["PRN1"] = room

    mgr.prune(now=1000.0 + EMPTY_LOBBY_TTL_SECONDS - 10)
    assert "PRN1" in mgr.rooms
    assert fake.cancelled is False

    mgr.prune(now=1000.0 + EMPTY_LOBBY_TTL_SECONDS + 1)
    assert "PRN1" not in mgr.rooms
    assert fake.cancelled is True
    assert room._nope_task is None


def test_view_injects_connected_and_nope_timing():
    room = Room("VW1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    room.register("An", ws_a)
    room.register("Binh", ws_b)

    lobby_view = room._view_for("An")
    assert all(p["connected"] is True for p in lobby_view["players"])
    assert lobby_view["you"]["hand_count"] == 0

    room.game = Game(["An", "Binh"])
    room.game.start()
    room.leave("Binh", ws_b)
    room.game.nope = {
        "actor": "An",
        "card": room.game.players["An"].hand[0],
        "stack": [],
        "responded": set(),
        "effect": lambda: None,
    }
    room.game.nope_deadline = time.time() + 4.5
    view = room._view_for("An")
    by_name = {p["name"]: p for p in view["players"]}
    assert by_name["An"]["connected"] is True
    assert by_name["Binh"]["connected"] is False
    nw = view["nope_window"]
    assert isinstance(nw["server_now_ms"], int)
    assert 0 <= nw["remaining_ms"] <= 5000


def test_rematch_and_return_lobby_flows():
    room = Room("REM1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("An", ws_a)
    tok_b = room.register("Binh", ws_b)

    async def flow():
        await room.handle("An", {"action": "vote_desk", "desk": "original"}, ws_a, tok_a)
        await room.handle("An", {"action": "start"}, ws_a, tok_a)
        first_game = room.game
        assert first_game is not None

        with pytest.raises(GameError):
            await room.handle("An", {"action": "rematch"}, ws_a, tok_a)
        with pytest.raises(GameError):
            await room.handle("An", {"action": "return_lobby"}, ws_a, tok_a)

        first_game.phase = "ended"
        first_game.winner = "An"
        await room.handle("An", {"action": "rematch"}, ws_a, tok_a)
        assert room.game is not first_game
        assert room.game.phase == "playing"
        assert room.game.desk_name == "original"

        room.game.phase = "ended"
        room.leave("Binh", ws_b)
        with pytest.raises(GameError):
            await room.handle("An", {"action": "rematch"}, ws_a, tok_a)

        await room.handle("An", {"action": "return_lobby"}, ws_a, tok_a)
        assert room.game is None
        assert "Binh" not in room.sessions
        assert ws_a.sent[-1]["view"]["phase"] == "lobby"
        assert [p["name"] for p in ws_a.sent[-1]["view"]["players"]] == ["An"]

    asyncio.run(flow())


def test_explicit_leave_action_in_lobby():
    room = Room("LV1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("An", ws_a)
    tok_b = room.register("Binh", ws_b)
    room.votes = {"An": "original", "Binh": "original"}

    async def flow():
        await room.handle("Binh", {"action": "leave"}, ws_b, tok_b)
        await asyncio.sleep(0)
        assert "Binh" not in room.conns
        assert "Binh" not in room.sessions
        assert "Binh" not in room.votes
        assert 1000 in ws_b.closed
        assert [p["name"] for p in ws_a.sent[-1]["view"]["players"]] == ["An"]

    asyncio.run(flow())


def test_stacked_nope_resets_timer_task():
    room = Room("NP1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    room.register("An", ws_a)
    room.register("Binh", ws_b)
    room.game = Game(["An", "Binh"])
    room.game.start()

    async def flow():
        g = room.game
        g.nope = {
            "actor": "An",
            "card": g.players["An"].hand[0],
            "stack": [],
            "responded": set(),
            "effect": lambda: None,
        }
        g.nope_deadline = None
        await room._after_action_locked()
        first_task = room._nope_task
        first_deadline = g.nope_deadline
        assert first_task is not None and first_deadline is not None

        # Giả lập stack_nope đặt lại nope_deadline = None
        g.nope_deadline = None
        await room._after_action_locked()
        second_task = room._nope_task
        assert second_task is not None and second_task is not first_task
        await asyncio.sleep(0)
        assert first_task.cancelled()
        room._cancel_nope_timer()

    asyncio.run(flow())


def test_blind_play_allows_empty_card_id():
    from server.engine.cards import Card

    room = Room("BLD1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("An", ws_a)
    room.register("Binh", ws_b)
    room.game = Game(["An", "Binh"])
    room.game.start()
    room.game.turn_index = room.game.order.index("An")
    room.game.players["An"].blind = True
    room.game.players["An"].hand = [Card(id="skip.0.blind", type="skip", variant=0)]

    async def flow():
        await room.handle("An", {"action": "play", "card_id": ""}, ws_a, tok_a)
        assert room.game.players["An"].hand == []

    asyncio.run(flow())


def test_blind_manual_slot_play_respond_and_opaque_view():
    from server.engine.cards import Card

    room = Room("BLD2")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("An", ws_a)
    tok_b = room.register("Binh", ws_b)
    room.game = Game(["An", "Binh"])
    room.game.start()
    room.game.turn_index = room.game.order.index("An")
    room.game.players["An"].blind = True
    c_defuse = Card(id="defuse.0.t0", type="defuse", variant=0)
    c_skip = Card(id="skip.0.t1", type="skip", variant=0)
    room.game.players["An"].hand = [c_defuse, c_skip]
    room.game.players["Binh"].blind = True
    b0 = Card(id="cat.0.b0", type="cat", variant=0)
    b1 = Card(id="favor.0.b1", type="favor", variant=0)
    room.game.players["Binh"].hand = [b0, b1]

    async def flow():
        # Verify opaque view before play
        view_a = room._view_for("An")
        assert view_a["you"]["hand"] == [
            {"id": "blind.0", "type": "hidden", "variant": 0, "blind_index": 0},
            {"id": "blind.1", "type": "hidden", "variant": 0, "blind_index": 1},
        ]
        # Manual blind play: slot 0 wastes exact defuse
        await room.handle("An", {"action": "play", "card_id": "blind.0"}, ws_a, tok_a)
        assert room.game.grave[-1].id == c_defuse.id
        assert [c.id for c in room.game.players["An"].hand] == [c_skip.id]
        # Broadcasted view to An only exposes 1 opaque blind.0 slot
        last_a = ws_a.sent[-1]["view"]["you"]["hand"]
        assert last_a == [{"id": "blind.0", "type": "hidden", "variant": 0, "blind_index": 0}]

        # Manual blind respond on favor: Binh gives exact blind.1 (b1) to An
        room.game._do_favor_pick(room.game.players["An"], "Binh")
        await room.handle("Binh", {"action": "respond", "payload": {"card_id": "blind.1"}}, ws_b, tok_b)
        assert room.game.pending is None
        assert [c.id for c in room.game.players["Binh"].hand] == [b0.id]
        assert any(c.id == b1.id for c in room.game.players["An"].hand)
        room._cancel_nope_timer()

    asyncio.run(flow())


def test_structured_error_codes_over_ws():
    with client.websocket_connect("/ws/ZZZZ?name=An") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error" and msg["code"] == "ROOM_NOT_FOUND"

    code = MANAGER.create()
    with client.websocket_connect(f"/ws/{code}?name=%20%20") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error" and msg["code"] == "INVALID_NAME"

    with client.websocket_connect(f"/ws/{code}?name=An") as a:
        _recv_state(a)
        with client.websocket_connect(f"/ws/{code}?name=An") as dup:
            msg = dup.receive_json()
            assert msg["type"] == "error" and msg["code"] == "NAME_TAKEN"
        a.send_json({"action": "unknown_xyz"})
        err = a.receive_json()
        assert err["type"] == "error" and err["code"] == "INVALID_ACTION"


def test_debug_flag_read_dynamically(monkeypatch):
    from server.rooms import _is_debug_enabled

    monkeypatch.delenv("EK_DEBUG", raising=False)
    assert _is_debug_enabled() is False
    monkeypatch.setenv("EK_DEBUG", "1")
    assert _is_debug_enabled() is True


def test_debug_rest_disabled_returns_403_and_health_flag(monkeypatch):
    monkeypatch.delenv("EK_DEBUG", raising=False)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["debug_enabled"] is False

    for method, path, kwargs in (
        ("get", "/api/debug/rooms", {}),
        ("get", "/api/debug/rooms/ABCD", {}),
        ("post", "/api/debug/rooms/ABCD/action", {"json": {"op": "start"}}),
    ):
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 403
        assert resp.json()["code"] == "DEBUG_DISABLED"

    room = Room("DBG0")
    room.register("Alice", StubSocket())
    assert room._view_for("Alice")["debug_enabled"] is False

    monkeypatch.setenv("EK_DEBUG", "1")
    assert client.get("/api/health").json()["debug_enabled"] is True
    assert room._view_for("Alice")["debug_enabled"] is True
    assert client.get("/api/debug/rooms/ZZZZ").status_code == 404
    assert client.post("/api/debug/rooms/ZZZZ/action", json={"op": "start"}).status_code == 404


def test_debug_rest_full_workflow_when_enabled(monkeypatch):
    monkeypatch.setenv("EK_DEBUG", "1")

    code = client.post("/api/rooms").json()["code"]
    room = MANAGER.get(code)
    assert room is not None
    ws_a = StubSocket()
    ws_b = StubSocket()
    room.register("Alice", ws_a)
    room.register("Bob", ws_b)

    rooms_resp = client.get("/api/debug/rooms")
    assert rooms_resp.status_code == 200
    entry = next(r for r in rooms_resp.json() if r["code"] == code)
    assert entry["players"] == ["Alice", "Bob"]
    assert entry["started"] is False
    assert entry["phase"] == "lobby"

    inspect_lobby = client.get(f"/api/debug/rooms/{code}")
    assert inspect_lobby.status_code == 200
    lobby_snap = inspect_lobby.json()
    assert lobby_snap["started"] is False
    assert lobby_snap["game"] is None
    assert lobby_snap["debug_enabled"] is True

    # Invalid JSON & missing op & unknown op
    bad_json = client.post(
        f"/api/debug/rooms/{code}/action",
        content=b"{not-json",
        headers={"content-type": "application/json"},
    )
    assert bad_json.status_code == 400
    assert bad_json.json()["code"] == "INVALID_JSON"

    no_op = client.post(f"/api/debug/rooms/{code}/action", json={})
    assert no_op.status_code == 400
    assert no_op.json()["code"] == "INVALID_ACTION"

    unknown_op = client.post(f"/api/debug/rooms/{code}/action", json={"op": "nope_xyz"})
    assert unknown_op.status_code == 400
    assert unknown_op.json()["code"] == "GAME_ERROR"

    # Start game
    started = client.post(f"/api/debug/rooms/{code}/action", json={"op": "start"})
    assert started.status_code == 200
    snap = started.json()
    assert snap["started"] is True
    assert snap["phase"] == "playing"
    assert snap["game"]["phase"] == "playing"
    assert ws_a.sent[-1]["view"]["debug_enabled"] is True

    # give
    gave = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "give", "target": "Alice", "ctype": "skip", "variant": 0},
    )
    assert gave.status_code == 200
    alice_hand = next(p["hand"] for p in gave.json()["game"]["players"] if p["name"] == "Alice")
    skip_card = next(c for c in alice_hand if c["type"] == "skip")

    # remove_card
    removed = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "remove_card", "target": "Alice", "card_id": skip_card["id"]},
    )
    assert removed.status_code == 200
    alice_ids = [c["id"] for c in next(p["hand"] for p in removed.json()["game"]["players"] if p["name"] == "Alice")]
    assert skip_card["id"] not in alice_ids

    # put_deck
    put = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "put_deck", "ctype": "implodingkitten", "index": 0, "faceup": True},
    )
    assert put.status_code == 200
    top = put.json()["game"]["deck"][0]
    assert top["type"] == "implodingkitten" and top["faceup"] is True

    # set_turn & toggle_blind
    turned = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "set_turn", "target": "Bob", "turns_left": 2},
    )
    assert turned.status_code == 200
    assert turned.json()["game"]["turn"]["current"] == "Bob"
    assert turned.json()["game"]["turn"]["turns_left"] == 2

    blinded = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "toggle_blind", "target": "Bob"},
    )
    assert blinded.status_code == 200
    assert next(p["blind"] for p in blinded.json()["game"]["players"] if p["name"] == "Bob") is True

    # clear_pending
    room.game.pending = {"kind": "yes_no", "owner": "Bob", "data": {"question": "?"}}
    cleared = client.post(f"/api/debug/rooms/{code}/action", json={"op": "clear_pending"})
    assert cleared.status_code == 200
    assert cleared.json()["game"]["pending"] is None

    # scenario_boom (keep_defuse=False, auto_draw=False) + force_draw
    staged = client.post(
        f"/api/debug/rooms/{code}/action",
        json={
            "op": "scenario_boom",
            "target": "Alice",
            "bomb_type": "explodingkitten",
            "keep_defuse": False,
            "auto_draw": False,
        },
    )
    assert staged.status_code == 200
    staged_game = staged.json()["game"]
    assert staged_game["turn"]["current"] == "Alice"
    assert staged_game["deck"][0]["type"] == "explodingkitten"
    alice_state = next(p for p in staged_game["players"] if p["name"] == "Alice")
    assert alice_state["alive"] is True
    assert all(c["type"] != "defuse" for c in alice_state["hand"])

    drawn = client.post(
        f"/api/debug/rooms/{code}/action",
        json={"op": "force_draw", "target": "Alice"},
    )
    assert drawn.status_code == 200
    ended_game = drawn.json()["game"]
    assert ended_game["phase"] == "ended"
    assert ended_game["winner"] == "Bob"
    assert next(p["alive"] for p in ended_game["players"] if p["name"] == "Alice") is False

    # return_lobby & restart & scenario_boom with auto_draw=True
    lobby = client.post(f"/api/debug/rooms/{code}/action", json={"op": "return_lobby"})
    assert lobby.status_code == 200
    assert lobby.json()["started"] is False
    assert lobby.json()["game"] is None

    assert client.post(f"/api/debug/rooms/{code}/action", json={"op": "start"}).status_code == 200
    instant = client.post(
        f"/api/debug/rooms/{code}/action",
        json={
            "op": "scenario_boom",
            "target": "Bob",
            "bomb_type": "implodingkitten",
            "faceup": True,
            "keep_defuse": True,
            "auto_draw": True,
        },
    )
    assert instant.status_code == 200
    assert instant.json()["game"]["phase"] == "ended"
    assert instant.json()["game"]["winner"] == "Alice"


def test_set_avatar_syncs_in_lobby_and_game_and_validates():
    room = Room("CAT1")
    ws_a = StubSocket()
    ws_b = StubSocket()
    tok_a = room.register("Alice", ws_a)
    tok_b = room.register("Bob", ws_b)

    async def flow():
        with pytest.raises(GameError):
            await room.handle("Alice", {"action": "set_avatar", "avatar": "bad"}, ws_a, tok_a)
        with pytest.raises(GameError):
            await room.handle(
                "Alice",
                {"action": "set_avatar", "avatar": {"fur": "unknown_color"}},
                ws_a,
                tok_a,
            )

        await room.handle(
            "Alice",
            {
                "action": "set_avatar",
                "avatar": {
                    "fur": "ginger",
                    "pattern": "tabby",
                    "eyes": "derp",
                    "mouth": "beard",
                    "hat": "taco",
                    "acc": "shades",
                    "ignored_field": "evil",
                },
            },
            ws_a,
            tok_a,
        )
        lobby_view = room._view_for("Bob")
        alice_lobby = next(p for p in lobby_view["players"] if p["name"] == "Alice")
        assert alice_lobby["avatar"] == {
            "fur": "ginger",
            "pattern": "tabby",
            "eyes": "derp",
            "mouth": "beard",
            "hat": "taco",
            "acc": "shades",
        }
        assert "ignored_field" not in alice_lobby["avatar"]

        await room.handle("Alice", {"action": "vote_desk", "desk": "original"}, ws_a, tok_a)
        await room.handle("Alice", {"action": "start"}, ws_a, tok_a)
        game_view = room._view_for("Bob")
        alice_game = next(p for p in game_view["players"] if p["name"] == "Alice")
        assert alice_game["avatar"]["hat"] == "taco"

        await room.handle(
            "Bob",
            {
                "action": "set_avatar",
                "avatar": {
                    "fur": "potato",
                    "pattern": "hairy",
                    "eyes": "lasers",
                    "mouth": "rainbow",
                    "hat": "underwear",
                    "acc": "knife",
                },
            },
            ws_b,
            tok_b,
        )
        updated_view = room._view_for("Alice")
        bob_game = next(p for p in updated_view["players"] if p["name"] == "Bob")
        assert bob_game["avatar"] == {
            "fur": "potato",
            "pattern": "hairy",
            "eyes": "lasers",
            "mouth": "rainbow",
            "hat": "underwear",
            "acc": "knife",
        }

    asyncio.run(flow())
