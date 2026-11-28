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
    assert cards["curseofthecatbutt"]["variant_names"]["0"] == "Curse of the Cat Butt"
    assert cards["curseofthecatbutt"]["variant_names"]["1"] == "Blind As A Bat"


def test_rest_desks_and_desk_details():
    desks = client.get("/api/desks").json()
    assert isinstance(desks, list)
    assert desks[:2] == ["original", "web"]
    for expected in ("good-vs-evil", "zombie-kittens", "recipes-for-disaster"):
        assert expected in desks

    details = client.get("/api/desks/details").json()
    assert isinstance(details, list)
    assert [d["id"] for d in details] == desks
    by_id = {d["id"]: d for d in details}
    for desk_id in ("original", "web", "good-vs-evil", "zombie-kittens", "recipes-for-disaster"):
        meta = by_id[desk_id]
        assert isinstance(meta["title"], str) and meta["title"]
        assert isinstance(meta["card_count"], int) and meta["card_count"] > 0
        assert isinstance(meta["deck_type"], str) and meta["deck_type"]


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


def test_ws_spectator_rematch_code_and_preload_smoke():
    from server.rooms import MANAGER

    with TestClient(app) as tc:
        code = MANAGER.create()
        with tc.websocket_connect(f"/ws/{code}?name=An") as a, \
                tc.websocket_connect(f"/ws/{code}?name=Binh") as b:
            _recv_state(a)
            _recv_state(b)
            _recv_state(a)

            a.send_json({"action": "start", "preload": True})
            va = _recv_state(a)
            while va.get("phase") != "loading":
                va = _recv_state(a)
            assert va["loading"]["desk"]
            assert "/backside.jpg" in va["loading"]["images"]

            a.send_json({"action": "assets_ready"})
            b.send_json({"action": "assets_ready"})

            va = _recv_state(a)
            while va.get("phase") != "playing":
                va = _recv_state(a)
            assert va["display_code"] == code
            assert va["real_code"] == code
            assert va["turn_timer"] is not None

            # Người thứ 3 vào phòng đang chơi -> chế độ khán giả
            with tc.websocket_connect(f"/ws/{code}?name=Spec") as s:
                vs = _recv_state(s)
                assert vs["you"]["spectator"] is True
                assert vs["you"]["hand"] == []
                assert vs["spectator_count"] == 1
                s.send_json({"action": "draw"})
                err = s.receive_json()
                assert err["type"] == "error"
                assert "khán giả" in err["message"]

                # Kết thúc ván -> rematch giữ display_code, đổi real_code, khán giả thành người chơi
                room = MANAGER.get(code)
                room.game.phase = "ended"
                room.game.winner = "An"
                a.send_json({"action": "rematch"})
                va2 = _recv_state(a)
                while va2.get("real_code") == code:
                    va2 = _recv_state(a)
                assert va2["display_code"] == code
                assert va2["real_code"] != code
                vs2 = _recv_state(s)
                while vs2.get("real_code") == code:
                    vs2 = _recv_state(s)
                assert vs2["you"]["spectator"] is False
                assert len(vs2["you"]["hand"]) >= 4

                info = tc.get(f"/api/rooms/{code}").json()
                assert info["code"] == code
                assert info["display_code"] == code
                assert info["real_code"] == va2["real_code"]
                assert tc.get(f"/api/rooms/{va2['real_code']}").status_code == 200

            # Đóng kết nối của s (giờ đã là người chơi trong ván mới), rồi kết nối lại không cần token cũ
            with tc.websocket_connect(f"/ws/{code}?name=Spec") as s_rejoin:
                vs3 = _recv_state(s_rejoin)
                assert vs3["you"]["spectator"] is False
                assert len(vs3["you"]["hand"]) >= 4
                # Trong khi đang online thì vẫn chặn trùng tên không có token
                with tc.websocket_connect(f"/ws/{code}?name=Spec") as dup:
                    err2 = dup.receive_json()
                    assert err2["type"] == "error"
                    assert err2["code"] == "NAME_TAKEN"
