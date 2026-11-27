"""Focused regressions for the confirmed transport, engine, and contract bugs."""

import asyncio
import random

import pytest
from fastapi.testclient import TestClient

from server.engine import Game, GameError
from server.engine.cards import Card
from server.main import app
from server.rooms import Room, RoomManager, SessionError

client = TestClient(app)


def make_game(n=3, seed=42):
    random.seed(seed)
    g = Game([f"P{i}" for i in range(n)])
    g.start()
    g.turn_index = 0
    return g


def cur(g):
    return g.players[g.order[g.turn_index]]


def give(g, name, ctype, variant=0):
    for i, c in enumerate(g.deck.cards):
        if c.type == ctype and c.variant == variant:
            card = g.deck.cards.pop(i)
            g.players[name].hand.append(card)
            return card
    card = Card(id=f"{ctype}.{variant}.test", type=ctype, variant=variant)
    g.players[name].hand.append(card)
    return card


def hand_ids(g, name):
    return [c.id for c in g.players[name].hand]


def force_turn(g, name):
    g.turn_index = g.order.index(name)


def all_pass(g):
    for p in g.alive():
        if p.name != g.nope["actor"] and p.name not in g.nope["responded"]:
            g.pass_nope(p.name)
    g.resolve_nope()


def put_top_bomb(g):
    for i in range(len(g.deck.cards)):
        if g.deck.cards[i].type == "explodingkitten":
            g.deck.cards.append(g.deck.cards.pop(i))
            return
    raise AssertionError("no exploding kitten in deck")


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


def test_duplicate_name_without_token_rejected():
    room = Room("TST1")
    ws1 = StubSocket()
    token = room.register("An", ws1)
    assert token
    with pytest.raises(SessionError):
        room.register("An", StubSocket())
    assert room.conns["An"] is ws1


def test_valid_session_replaces_stale_socket():
    room = Room("TST2")
    old = StubSocket()
    new = StubSocket()
    token = room.register("An", old)

    async def replace():
        out = room.register("An", new, token)
        await asyncio.sleep(0)
        return out

    assert asyncio.run(replace()) == token
    assert room.conns["An"] is new
    assert old.closed


def test_malformed_envelopes_do_not_mutate_game():
    room = Room("TST3")
    ws = StubSocket()
    token = room.register("An", ws)
    room.register("Binh", StubSocket())
    room.game = Game(["An", "Binh"])
    room.game.start()
    game = room.game
    with pytest.raises(GameError):
        asyncio.run(room.handle("An", {"action": "play"}, ws, token))
    with pytest.raises(GameError):
        asyncio.run(room.handle("An", [], ws, token))
    assert room.game is game
    assert game.pending is None


def test_duplicate_websocket_name_is_rejected():
    from server.rooms import MANAGER

    code = MANAGER.create()
    with client.websocket_connect(f"/ws/{code}?name=An") as a:
        assert a.receive_json()["type"] == "state"
        with client.websocket_connect(f"/ws/{code}?name=An") as b:
            assert b.receive_json()["type"] == "error"

def test_second_start_is_rejected():
    room = Room("TST4")
    room.register("An", StubSocket())
    room.register("Binh", StubSocket())
    room.votes = {"An": "original", "Binh": "original"}
    asyncio.run(room.start_game())
    game = room.game
    with pytest.raises(GameError):
        asyncio.run(room.start_game())
    assert room.game is game


def test_failed_broadcast_removes_socket():
    room = Room("TST5")
    good = StubSocket()
    bad = StubSocket(fail_send=True)
    room.register("An", good)
    room.register("Binh", bad)

    async def settle():
        await room.push_all()
        await asyncio.sleep(0)

    asyncio.run(settle())
    assert len(good.sent) == 2
    assert [p["name"] for p in good.sent[-1]["view"]["players"]] == ["An"]
    assert "Binh" not in room.conns
    assert bad.closed


def test_idle_room_pruned():
    manager = RoomManager()
    room = Room("TST6")
    room.last_active -= 4000
    manager.rooms["TST6"] = room
    manager.prune()
    assert "TST6" not in manager.rooms


def test_room_list_hides_player_names():
    code = client.post("/api/rooms").json()["code"]
    rooms = client.get("/api/rooms").json()
    entry = next(r for r in rooms if r["code"] == code)
    assert entry["player_count"] == 0
    assert "players" not in entry


def test_card_images_use_existing_jpg_assets():
    cards = client.get("/api/cards").json()
    assert cards["skip"]["image"].endswith(".jpg")
    image = client.get(cards["skip"]["image"])
    assert image.status_code == 200


def test_attack_bonuses_total_two_and_dead_scaling():
    g = make_game(3)
    first = cur(g).name
    nxt = g.order[(g.turn_index + 1) % 3]
    give(g, first, "attack2x")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    assert cur(g).name == nxt
    assert g.turns_left == 2


def test_targeted_attack_totals_two_turns():
    g = make_game(3)
    first = cur(g).name
    other = g.order[1]
    give(g, first, "targetattack2x")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    g.respond(first, {"player": other})
    assert cur(g).name == other
    assert g.turns_left == 2


def test_attack_of_dead_scales_with_dead_players():
    g = make_game(3)
    first = cur(g).name
    nxt = g.order[(g.turn_index + 1) % 3]
    dead = g.order[2]
    g.players[dead].alive = False
    give(g, first, "attackofthedead")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    assert cur(g).name == nxt
    assert g.turns_left == 3


def test_personal_attack_totals_three_turns():
    g = make_game(2)
    first = cur(g).name
    give(g, first, "personalattack3x")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    assert cur(g).name == first
    assert g.turns_left == 3


def test_favor_steals_from_crown_not_hand():
    g = make_game(2)
    thief, wearer = g.order[0], g.order[1]
    force_turn(g, wearer)
    give(g, wearer, "towerofpower")
    g.play_card(wearer, hand_ids(g, wearer)[-1])
    all_pass(g)
    stash_before = len(g.stash)
    wearer_hand_before = len(g.players[wearer].hand)
    thief_before = len(g.players[thief].hand)
    force_turn(g, thief)
    give(g, thief, "favor")
    g.play_card(thief, hand_ids(g, thief)[-1])
    all_pass(g)
    g.respond(thief, {"player": wearer})
    assert len(g.stash) == stash_before - 1
    assert len(g.players[wearer].hand) == wearer_hand_before
    assert len(g.players[thief].hand) == thief_before + 1


def test_barking_match_discards_both_cards():
    g = make_game(3)
    first, other = g.order[0], g.order[1]
    force_turn(g, first)
    first_card = give(g, first, "barkingkitten")
    give(g, other, "barkingkitten", 1)
    other_before = len(g.players[other].hand)
    g.play_card(first, first_card.id)
    assert g.players[other].alive
    assert not any(c.type == "barkingkitten" for c in g.players[first].hand)
    assert not any(c.type == "barkingkitten" for c in g.players[other].hand)
    assert len(g.players[other].hand) == other_before - 2  # barking + defuse
    assert sum(1 for c in g.grave if c.type == "barkingkitten") == 2


def test_barking_faceup_match_discards_both_cards():
    g = make_game(3)
    first, other = g.order[0], g.order[1]
    force_turn(g, first)
    lone = give(g, first, "barkingkitten")
    g.play_card(first, lone.id)
    assert any(c.type == "barkingkitten" for c in g.players[first].faceup)
    force_turn(g, other)
    give(g, other, "barkingkitten", 1)
    g.play_card(other, hand_ids(g, other)[-1])
    assert not any(c.type == "barkingkitten" for c in g.players[first].faceup)
    assert g.players[first].alive
    assert sum(1 for c in g.grave if c.type == "barkingkitten") == 2


def test_potluck_starts_with_actor():
    g = make_game(3)
    actor = cur(g).name
    give(g, actor, "potluck")
    give(g, actor, "skip")
    g.play_card(actor, next(c.id for c in g.players[actor].hand if c.type == "potluck"))
    all_pass(g)
    owners = []
    for _ in range(5):
        if g.pending is None:
            break
        owners.append(g.pending["owner"])
        g.respond(g.pending["owner"], {"card_id": hand_ids(g, g.pending["owner"])[-1]})
    assert owners
    assert owners[0] == actor


def test_garbage_collection_skips_empty_actor():
    g = make_game(2)
    actor, other = g.order[0], g.order[1]
    force_turn(g, actor)
    g.players[actor].hand = []
    give(g, actor, "garbagecollection")
    g.play_card(actor, hand_ids(g, actor)[-1])
    all_pass(g)
    assert g.pending is not None
    assert g.pending["owner"] == other


def test_feral_cat_cannot_pair_with_action_card():
    g = make_game(2)
    first = cur(g).name
    feral = give(g, first, "feralcat")
    skip = give(g, first, "skip")
    with pytest.raises(GameError):
        g.play_combo(first, "pair", [feral.id, skip.id])


def test_pending_details_visible_only_to_owner():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    force_turn(g, first)
    give(g, first, "alter3x")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    owner_pending = g.view(first)["pending"]
    other_pending = g.view(other)["pending"]
    assert owner_pending["owner"] == first
    assert owner_pending["data"]["cards"]
    assert other_pending["owner"] == first
    assert "cards" not in other_pending["data"]


def test_viewer_log_is_chronological():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g._say("private draw", private=first)
    g._say("public event")
    log = g.view(first)["log"]
    assert log.index("private draw") < log.index("public event")
    assert "private draw" not in g.view(other)["log"]


def test_malformed_respond_preserves_pending():
    g = make_game(2)
    first = cur(g).name
    put_top_bomb(g)
    g.draw(first)
    pending = g.pending
    with pytest.raises(GameError):
        g.respond(first, {"index": "not-an-int"})
    with pytest.raises(GameError):
        g.respond(first, [])
    assert g.pending == pending


def test_godcat_anytime_preserves_current_turn():
    g = make_game(3)
    first = cur(g).name
    other = g.order[1]
    force_turn(g, first)
    give(g, other, "godcat")
    g.play_now(other, hand_ids(g, other)[-1], as_type="shuffle")
    all_pass(g)
    assert cur(g).name == first
    assert any(e["card"]["type"] == "godcat" for e in g.playmat)


def test_dead_player_anytime_limits():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[other].alive = False
    give(g, other, "shufflenow")
    with pytest.raises(GameError):
        g.play_now(other, hand_ids(g, other)[-1])
    give(g, other, "clairvoyance")
    g.play_now(other, hand_ids(g, other)[-1])
    all_pass(g)
    assert other in g.bomb_watchers


def test_godcat_standby_defuse():
    g = make_game(2)
    first = cur(g).name
    give(g, first, "godcat")
    g.play_card(first, hand_ids(g, first)[-1], as_type="defuse")
    assert any(e["card"]["type"] == "godcat" for e in g.playmat)
    assert any("Defuse dự phòng" in m for m in g.log)
