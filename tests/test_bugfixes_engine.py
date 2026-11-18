"""Engine rule fixes vs resources/cards_desc/*.txt (slice: server/engine only)."""

import random

import pytest

from server.engine import Game, GameError
from server.engine.cards import Card


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
            return g.players[name].hand.append(g.deck.cards.pop(i)) or g.players[name].hand[-1]
    card = Card(id=f"{ctype}.{variant}.test", type=ctype, variant=variant)
    g.players[name].hand.append(card)
    return card


def hand_ids(g, name):
    return [c.id for c in g.players[name].hand]


def force_turn(g, name):
    g.turn_index = g.order.index(name)


def play_type(g, name, ctype, **kw):
    card = next(c for c in g.players[name].hand if c.type == ctype)
    g.play_card(name, card.id, **kw)


def act(g, name, ctype, **kw):
    play_type(g, name, ctype, **kw)
    if g.nope is not None:
        all_pass(g)


def all_pass(g):
    for p in g.alive():
        if p.name != g.nope["actor"] and p.name not in g.nope["responded"]:
            g.pass_nope(p.name)
    g.resolve_nope()


def test_stacked_attack_carries_remaining_turns():
    g = make_game(3)
    first, victim = g.order[0], g.order[1]
    give(g, first, "attack2x")
    act(g, first, "attack2x")
    assert cur(g).name == victim and g.turns_left == 2
    give(g, victim, "attack2x")
    g.play_card(victim, hand_ids(g, victim)[-1])
    all_pass(g)
    third = g.order[2]
    assert cur(g).name == third
    assert g.turns_left == 3  # 1 lượt dư + 2 mới


def test_stacked_targetattack_carries_remaining_turns():
    g = make_game(3)
    first, victim = g.order[0], g.order[1]
    give(g, first, "attack2x")
    act(g, first, "attack2x")
    give(g, victim, "targetattack2x")
    g.play_card(victim, hand_ids(g, victim)[-1])
    all_pass(g)
    g.respond(victim, {"player": g.order[2]})
    assert cur(g).name == g.order[2]
    assert g.turns_left == 3


def test_stacked_attack_of_dead_carries_remaining_turns():
    g = make_game(3)
    first, victim = g.order[0], g.order[1]
    g.players[g.order[2]].alive = False
    give(g, first, "attackofthedead")
    act(g, first, "attackofthedead")
    assert g.turns_left == 3
    give(g, victim, "attackofthedead")
    g.play_card(victim, hand_ids(g, victim)[-1])
    all_pass(g)
    assert g.turns_left == 5  # 2 lượt dư (3-1) + 3 mới (1 người chết)


def test_armageddon_ends_single_turn_under_attack():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    give(g, first, "devilcat")
    g.play_card(first, hand_ids(g, first)[-1])
    give(g, first, "godcat")
    act(g, first, "godcat", as_type="skip")
    force_turn(g, first)
    g.turns_left = 2  # đang gánh 2 lượt attack
    give(g, first, "defuse")
    give(g, other, "defuse")
    give(g, first, "armageddon")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    g.respond(first, {"player": other})
    g.respond(other, {"value": True})
    assert cur(g).name == first
    assert g.turns_left == 1  # armageddon.txt: chỉ hết 1 lượt


def test_devil_survived_by_zombie_kitten():
    g = make_game(2)
    holder = g.players[g.order[0]]
    holder.hand = [c for c in holder.hand if c.type != "defuse"]
    n_zombie = sum(1 for c in holder.hand if c.type == "zombiekitten")
    give(g, holder.name, "zombiekitten")
    devil = Card(id="devilcat.0.t", type="devilcat", variant=0)
    g._resolve_armageddon_fate(holder, devil)
    assert holder.alive
    assert sum(1 for c in holder.hand if c.type == "zombiekitten") == n_zombie
    assert any(c.type == "zombiekitten" for c in g.grave)


def test_clone_uses_own_card_for_tower():
    g = make_game(2)
    first = cur(g).name
    tower = Card(id="towerofpower.0.t", type="towerofpower", variant=0)
    g.grave.append(tower)
    clone = give(g, first, "clone")
    act(g, first, "clone")
    assert g.tower_wearer == first
    assert any(c.id == clone.id for c in g.deck.cards)  # lá Clone vào deck, không lôi lá grave
    assert any(c.id == tower.id for c in g.grave)


def test_clone_without_mat_kitten_is_void_not_crash():
    g = make_game(2)
    first = cur(g).name
    g.grave.append(Card(id="armageddon.0.t", type="armageddon", variant=0))
    give(g, first, "clone")
    act(g, first, "clone")  # không raise StopIteration
    assert any("vô hiệu" in m for m in g.log)


def test_godcat_armageddon_offturn_needs_mat():
    g = make_game(2)
    other = g.order[1]
    give(g, other, "godcat")
    with pytest.raises(GameError):
        g.play_now(other, hand_ids(g, other)[-1], as_type="armageddon")


def test_clone_pairs_with_cat():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    force_turn(g, first)
    cat = give(g, first, "cat", 1)
    clone = give(g, first, "clone")
    give(g, other, "skip")
    g.play_combo(first, "pair", [cat.id, clone.id])
    all_pass(g)
    assert g.pending is not None and g.pending["owner"] == first
    g.respond(first, {"player": other})
    pos = 0
    g.respond(first, {"position": pos})
    assert len(g.players[first].hand) > 0


def test_heck_keep_bomb_needs_rescue():
    g = make_game(2)
    first = cur(g).name
    bomb = Card(id="explodingkitten.0.t", type="explodingkitten", variant=0)
    g.deck.cards[0] = bomb  # đáy deck là bom
    give(g, first, "raisingheck")
    give(g, first, "defuse")
    act(g, first, "raisingheck")
    g.respond(first, {"value": True})  # giữ lá đáy = rút trúng bom
    assert g.pending is not None and g.pending["kind"] == "pick_index"
    assert g.players[first].alive


def test_three_call_does_not_yield_feral_for_action_query():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    force_turn(g, first)
    for v in (1, 2, 3):
        give(g, first, "cat", v)
    feral = give(g, other, "feralcat")
    n_before = len(g.players[first].hand)
    g.play_combo(first, "three", hand_ids(g, first)[-3:])
    all_pass(g)
    g.respond(first, {"player": other})
    g.respond(first, {"text": "skip"})
    assert feral in g.players[other].hand
    assert len(g.players[first].hand) == n_before - 3


def test_reorder_duplicate_ids_rejected():
    g = make_game(2)
    first = cur(g).name
    give(g, first, "alter3x")
    g.play_card(first, hand_ids(g, first)[-1])
    all_pass(g)
    ids = [c["id"] for c in g.pending["data"]["cards"]]
    snap = g.pending
    with pytest.raises(GameError):
        g.respond(first, {"order": [ids[0], ids[0], ids[1]]})
    assert g.pending == snap


def test_potluck_chain_survives_streaking_blast():
    g = make_game(2)
    actor, other = g.order[0], g.order[1]
    force_turn(g, actor)
    streak = give(g, actor, "streakingkitten")
    ek = Card(id="explodingkitten.0.t", type="explodingkitten", variant=0)
    g.players[actor].hand.append(ek)
    give(g, actor, "defuse")
    give(g, actor, "skip")
    give(g, other, "skip")
    give(g, actor, "potluck")
    g.play_card(actor, next(c.id for c in g.players[actor].hand if c.type == "potluck"))
    all_pass(g)
    assert g.pending["owner"] == actor
    g.respond(actor, {"card_id": streak.id})  # cho streaking đi -> EK nổ -> Defuse
    assert g.pending is not None and g.pending["kind"] == "pick_index"
    assert not any(c.type == "streakingkitten" for c in g.players[actor].hand)
    g.respond(actor, {"index": 0})
    # chuỗi Potluck tiếp tục tới người còn lại, không mất prompt bom
    assert g.pending is not None and g.pending["owner"] == other
    g.respond(other, {"card_id": hand_ids(g, other)[-1]})
    assert g.pending is None
    assert g.players[actor].alive


def test_swaptop_is_secret():
    g = make_game(2)
    first = cur(g).name
    give(g, first, "swaptopandbottom")
    act(g, first, "swaptopandbottom")
    assert g.revealed == []


def test_blind_hides_own_marked():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[first].blind = True
    g.players[first].marked_id = g.players[first].hand[0].id
    assert g.view(first)["you"]["marked"] is None
    idx = g.order.index(first)
    assert g.view(other)["players"][idx]["marked"] is not None
