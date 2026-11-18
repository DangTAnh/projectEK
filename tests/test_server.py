"""Smoke test server: REST + WebSocket lobby/start. Logic ván đã phủ ở test_engine."""

from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def _recv_state(ws, limit=50):
    """Đọc tới khi thấy 1 bản tin state (bỏ qua error)."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg.get("type") == "state":
            return msg["view"]
    raise AssertionError("không nhận được state")


def test_rest_rooms_and_cards():
    code = client.post("/api/rooms").json()["code"]
    assert len(code) == 4
    rooms = client.get("/api/rooms").json()
    assert any(r["code"] == code for r in rooms)
    cards = client.get("/api/cards").json()
    assert "feralcat" in cards and cards["skip"]["nopeable"] is True


def test_ws_lobby_and_start():
    from server.rooms import MANAGER

    code = MANAGER.create()
    with client.websocket_connect(f"/ws/{code}?name=An") as a, \
            client.websocket_connect(f"/ws/{code}?name=Binh") as b:
        va = _recv_state(a)
        assert va["phase"] == "lobby"
        a.send_json({"action": "start"})
        got_a = _recv_state(a)
        while got_a.get("phase") != "playing":
            got_a = _recv_state(a)
        got_b = _recv_state(b)
        while got_b.get("phase") != "playing":
            got_b = _recv_state(b)
        assert len(got_a["you"]["hand"]) >= 4
        assert len(got_b["you"]["hand"]) >= 4
        assert set(p["name"] for p in got_b["players"]) == {"An", "Binh"}


def test_ws_unknown_room():
    # server chấp nhận kết nối nhưng báo lỗi và đóng ngay
    with client.websocket_connect("/ws/ZZZZ?name=X") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"
