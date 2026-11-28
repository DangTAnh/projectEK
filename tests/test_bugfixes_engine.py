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
    g._card_seq += 1
    card = Card(id=f"{ctype}.{variant}.test.{g._card_seq}", type=ctype, variant=variant)
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
    for _ in range(3):
        give(g, first, "cat", 0)
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


# ---------- P0/P1 engine fixes & contract tests ----------


def test_graverobber_dead_player_auto_picks_random_non_godcat():
    g = make_game(3)
    first, dead = g.order[0], g.order[2]
    g.players[dead].alive = False
    god = Card(id="godcat.0.gr", type="godcat", variant=0)
    dead_card = Card(id="skip.0.gr", type="skip", variant=0)
    g.players[dead].hand = [god, dead_card]
    give(g, first, "graverobber")
    deck_before = g.deck.size()
    act(g, first, "graverobber")
    # Người chết tự động chọn ngẫu nhiên 1 thẻ hợp lệ (không phải Godcat), không mở pending treo bàn
    assert g.pending is None
    assert dead_card not in g.players[dead].hand
    assert god in g.players[dead].hand
    assert any(c.id == dead_card.id for c in g.deck.cards)
    assert g.deck.size() == deck_before + 1
    assert any(dead in line and "tự động chọn ngẫu nhiên" in line for line in g.log)


def test_digdeeper_decline_draws_second_card_and_leaves_first_on_top():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    first_top = Card(id="skip.0.dig1", type="skip", variant=0)
    second_top = Card(id="favor.0.dig2", type="favor", variant=0)
    g.deck.cards.append(second_top)
    g.deck.cards.append(first_top)  # đỉnh deck
    give(g, first, "digdeeper")
    act(g, first, "digdeeper")
    assert g.pending["kind"] == "yes_no"
    # card chỉ lộ cho owner, không lộ cho đối thủ
    assert g.view(first)["pending"]["data"]["card"]["id"] == first_top.id
    assert "card" not in g.view(other)["pending"]["data"]
    g.respond(first, {"value": False})
    assert second_top in g.players[first].hand
    assert first_top not in g.players[first].hand
    assert g.deck.peek(1)[0].id == first_top.id
    assert cur(g).name == other


def test_digdeeper_and_raisingheck_bomb_keep_waits_for_rescue_before_turn_ends():
    # Dig Deeper giữ EK: không đổi lượt trước khi chèn bom
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    bomb = Card(id="explodingkitten.0.digb", type="explodingkitten", variant=0)
    g.deck.cards.append(bomb)
    give(g, first, "digdeeper")
    give(g, first, "defuse")
    act(g, first, "digdeeper")
    g.respond(first, {"value": True})
    assert g.pending is not None and g.pending["kind"] == "pick_index"
    assert cur(g).name == first
    g.respond(first, {"index": 0})
    assert g.pending is None
    assert cur(g).name == other

    # Raising Heck giữ Imploding mặt úp: lật mặt lên, không tốn Defuse, đợi pick_index
    g2 = make_game(2)
    first2, other2 = g2.order[0], g2.order[1]
    imp = Card(id="implodingkitten.0.heck", type="implodingkitten", variant=0, faceup=False)
    g2.deck.cards[0] = imp
    defuses_before = sum(1 for c in g2.players[first2].hand if c.type == "defuse")
    give(g2, first2, "raisingheck")
    act(g2, first2, "raisingheck")
    assert g2.view(first2)["pending"]["data"]["card"]["id"] == imp.id
    g2.respond(first2, {"value": True})
    assert g2.pending is not None and g2.pending["data"]["reason"] == "imploding"
    assert imp.faceup is True
    assert cur(g2).name == first2
    assert sum(1 for c in g2.players[first2].hand if c.type == "defuse") == defuses_before
    g2.respond(first2, {"index": 0})
    assert cur(g2).name == other2


def test_illtakethat_bomb_intercept_waits_for_trapper_rescue():
    g = make_game(2)
    trapper, victim = g.order[0], g.order[1]
    g.players[victim].illtake_by = trapper
    force_turn(g, victim)
    give(g, trapper, "defuse")
    bomb = Card(id="explodingkitten.0.itt", type="explodingkitten", variant=0)
    g.deck.cards.append(bomb)
    g.draw(victim)
    assert g.pending is not None
    assert g.pending["owner"] == trapper
    assert g.pending["kind"] == "pick_index"
    assert cur(g).name == victim  # chưa chuyển lượt khi trapper chưa chèn bom xong
    g.respond(trapper, {"index": 0})
    assert g.pending is None
    assert cur(g).name == trapper


def test_play_combo_rejects_duplicate_card_ids_without_mutation():
    g = make_game(2)
    first = cur(g).name
    cat = give(g, first, "cat", 0)
    hand_before = list(g.players[first].hand)
    grave_before = list(g.grave)
    with pytest.raises(GameError):
        g.play_combo(first, "pair", [cat.id, cat.id])
    assert g.players[first].hand == hand_before
    assert g.grave == grave_before


def test_empty_mark_and_empty_reorder_do_not_softlock():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[other].hand = []
    give(g, first, "mark")
    act(g, first, "mark")
    assert g.pending is None

    g.deck.cards = []
    give(g, first, "alter3x")
    act(g, first, "alter3x")
    assert g.pending is None


def test_blind_play_empty_id_wastes_unplayable_and_random_own_hand_respond():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[first].blind = True
    for ctype in ("nope", "godcat", "armageddon", "graverobber", "cat"):
        g.players[first].hand = [Card(id=f"{ctype}.0.bl", type=ctype, variant=0)]
        g.play_card(first, "")
        assert g.players[first].hand == []
        assert g.grave[-1].type == ctype

    # blind + own_hand pending (favor + potluck excluding godcat)
    g2 = make_game(2)
    first2, other2 = g2.order[0], g2.order[1]
    g2.players[other2].blind = True
    g2.players[other2].hand = [
        Card(id="godcat.0.bl", type="godcat", variant=0),
        Card(id="skip.0.bl", type="skip", variant=0),
    ]
    assert g2.view(other2)["you"]["hand"] == [
        {"id": "blind.0", "type": "hidden", "variant": 0, "blind_index": 0},
        {"id": "blind.1", "type": "hidden", "variant": 0, "blind_index": 1},
    ]
    assert g2.view(other2)["you"]["hand_count"] == 2
    give(g2, first2, "potluck")
    give(g2, first2, "skip")
    act(g2, first2, "potluck")
    assert g2.pending["owner"] == first2
    # không bị mù thì không dùng random=True
    with pytest.raises(GameError):
        g2.respond(first2, {"random": True})
    g2.respond(first2, {"card_id": next(c.id for c in g2.players[first2].hand if c.type == "skip")})
    assert g2.pending["owner"] == other2
    g2.respond(other2, {"random": True})
    assert g2.pending is None
    # Godcat phải ở lại tay, skip lên đỉnh deck
    assert [c.type for c in g2.players[other2].hand] == ["godcat"]
    assert g2.deck.peek(1)[0].type == "skip"


def test_godcat_play_now_blocks_turn_ending_and_standby_defuse_works():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    god = give(g, other, "godcat")
    with pytest.raises(GameError):
        g.play_now(other, god.id, as_type="skip")
    with pytest.raises(GameError):
        g.play_now(other, god.id, as_type="attack2x")

    # Standby Defuse thực sự cứu khi rút bom
    g.players[first].hand = [c for c in g.players[first].hand if c.type != "defuse"]
    god_first = give(g, first, "godcat")
    g.play_card(first, god_first.id, as_type="defuse")
    assert g.players[first].standby_defuse is True
    bomb = Card(id="explodingkitten.0.sb", type="explodingkitten", variant=0)
    g.deck.cards.append(bomb)
    g.draw(first)
    assert g.players[first].alive is True
    assert g.players[first].standby_defuse is False
    assert g.pending is not None and g.pending["kind"] == "pick_index"


def test_godcat_offturn_clone_personalattack_gives_extra_turns_to_actor_not_current():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.grave.append(Card(id="personalattack3x.0.gc", type="personalattack3x", variant=0))
    god = give(g, other, "godcat")
    turns_before = g.turns_left
    g.play_now(other, god.id, as_type="clone")
    all_pass(g)
    assert cur(g).name == first
    assert g.turns_left == turns_before  # không cộng nhầm vào lượt của người đang đi
    assert g.players[other].extra_turns == 2


def test_clone_guards_zero_dead_and_non_action_cards():
    g = make_game(2)
    first = cur(g).name
    g.grave.append(Card(id="attackofthedead.0.cl", type="attackofthedead", variant=0))
    give(g, first, "clone")
    act(g, first, "clone")
    assert g.players[g.order[1]].extra_turns == 0
    assert cur(g).name == first

    g.grave.append(Card(id="explodingkitten.0.cl", type="explodingkitten", variant=0))
    give(g, first, "clone")
    act(g, first, "clone")
    assert any("Clone vô hiệu" in m for m in g.log)


def test_potluck_and_garbage_reject_godcat_into_deck():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    god = Card(id="godcat.0.nod", type="godcat", variant=0)
    skip = Card(id="skip.0.nod", type="skip", variant=0)
    g.players[first].hand = [god, skip]
    g.players[other].hand = [Card(id="godcat.0.nod2", type="godcat", variant=0)]
    give(g, first, "garbagecollection")
    act(g, first, "garbagecollection")
    assert g.pending["owner"] == first
    with pytest.raises(GameError):
        g.respond(first, {"card_id": god.id})
    g.respond(first, {"card_id": skip.id})
    # other chỉ có Godcat nên được bỏ qua, không soft-lock
    assert g.pending is None
    assert all(c.type != "godcat" for c in g.deck.cards)


def test_counter_nope_yup_resets_responded_and_deadline():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    give(g, first, "godcat")
    give(g, first, "nope")
    give(g, other, "nope")
    g.play_card(first, next(c.id for c in g.players[first].hand if c.type == "godcat"), as_type="skip")
    g.nope_deadline = 12345.0
    v_other = g.view(other)
    assert v_other["nope_window"]["as_type"] == "skip"
    assert v_other["nope_window"]["you_responded"] is False

    g.stack_nope(other)
    assert g.nope_deadline is None
    assert g.nope["responded"] == {other}
    assert g.nope_all_responded() is False  # 2 người: actor gốc được phép phản Nope (Yup)
    assert g.view(other)["nope_window"]["you_responded"] is True
    assert g.view(first)["nope_window"]["you_responded"] is False

    # Actor gốc phản Nope (Yup!) -> số Nope chẵn -> Skip chạy
    g.stack_nope(first)
    assert g.nope_deadline is None
    assert g.nope["responded"] == {first}
    g.pass_nope(other)
    assert g.nope_all_responded() is True
    g.resolve_nope()
    assert cur(g).name == other


def test_personalattack3x_stacked_math_and_accurate_log():
    g = make_game(2)
    first = cur(g).name
    g.turns_left = 2
    give(g, first, "personalattack3x")
    act(g, first, "personalattack3x")
    assert g.turns_left == 5
    assert any("5 lượt" in m for m in g.log)


def test_grave_reshuffle_excludes_exploded_and_faceup_imploding():
    g = make_game(2)
    first = cur(g).name
    g.deck.cards = []
    ek = Card(id="explodingkitten.0.gr", type="explodingkitten", variant=0)
    imp = Card(id="implodingkitten.0.gr", type="implodingkitten", variant=0, faceup=True)
    safe = Card(id="skip.0.gr", type="skip", variant=0)
    g.grave = [ek, imp, safe]
    g.draw(first)
    assert safe in g.players[first].hand
    assert ek in g.grave and imp in g.grave
    assert all(c.id not in (ek.id, imp.id) for c in g.deck.cards)


def test_view_contract_fields_and_log_cap():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[other].illtake_by = first
    for i in range(350):
        g._say(f"msg {i}")
    assert len(g.log) <= 300
    v = g.view(first)
    assert v["you"]["hand_count"] == len(g.players[first].hand)
    other_view = next(p for p in v["players"] if p["name"] == other)
    assert other_view["illtake_by"] == first
    entries = v["log_entries"]
    assert len(entries) == 30
    assert [e["text"] for e in entries] == v["log"]
    assert [e["seq"] for e in entries] == sorted(e["seq"] for e in entries)


def test_desk_assets_and_defuse_capacity():
    import json
    from pathlib import Path
    from server.engine.cards import CARD_META

    root = Path(__file__).resolve().parents[1]
    desks = sorted((root / "resources" / "desk").glob("*.json"))
    assert len(desks) >= 13
    for desk_path in desks:
        data = json.loads(desk_path.read_text(encoding="utf-8"))
        cards = data["cards"]
        if desk_path.stem in ("original", "web"):
            assert sum(cards.get("defuse", {}).values()) >= 9, f"{desk_path.name} needs >=9 defuses"
        for ctype, variants in cards.items():
            assert ctype in CARD_META, f"Unknown card type in {desk_path.name}: {ctype}"
            for var in variants:
                jpg = root / "resources" / "cards" / ctype / f"{var}.jpg"
                assert jpg.exists(), f"Missing asset for {desk_path.name}: {ctype}/{var}.jpg"
        # Chơi cả 2 người và 9 người trên mọi bộ bài đều phát đủ lá cứu nguy (defuse/zombiekitten)
        for n_players in (2, 9):
            g = Game([f"P{i}" for i in range(n_players)], desk=desk_path.stem)
            g.start()
            assert all(
                g.players[n].has_type("defuse") or g.players[n].has_type("zombiekitten")
                for n in g.order
            ), f"{desk_path.name} failed rescue deal for {n_players} players"
            if desk_path.stem in ("imploding-kittens", "recipes-for-disaster"):
                assert any(c.type == "implodingkitten" for c in g.deck.cards), (
                    f"{desk_path.name} missing implodingkitten in deck"
                )


# ---------- Debug Studio engine helpers ----------


def test_debug_put_deck_set_turn_toggle_blind_and_remove_card():
    g = make_game(3)
    p0, p1, p2 = g.order

    # debug_put_deck: top (0), custom index, clamping, faceup, invalid ctype
    top_card = g.debug_put_deck("explodingkitten", index=0, variant=2, faceup=False)
    assert g.deck.cards[-1].id == top_card.id
    assert top_card.type == "explodingkitten" and top_card.variant == 2 and top_card.faceup is False

    imp = g.debug_put_deck("imploding", index=2, variant=0, faceup=True)
    assert g.deck.peek(3)[2].id == imp.id
    assert imp.type == "implodingkitten" and imp.faceup is True

    bottom = g.debug_put_deck("skip", index=9999)
    assert g.deck.cards[0].id == bottom.id
    clamped_top = g.debug_put_deck("favor", index=-5)
    assert g.deck.cards[-1].id == clamped_top.id
    with pytest.raises(GameError):
        g.debug_put_deck("not_a_real_card_xyz")

    # debug_set_turn: chuyển lượt + clamp turns_left + xóa transient + chặn người chết / ván kết thúc
    g.revealed = [top_card]
    g.private_peeks[p0] = [top_card.to_dict()]
    g.debug_set_turn(p1, turns_left=3)
    assert cur(g).name == p1 and g.turns_left == 3
    assert g.revealed == [] and g.private_peeks == {}

    g.debug_set_turn(p2, turns_left=99)
    assert cur(g).name == p2 and g.turns_left == 10
    g.debug_set_turn(p0, turns_left=0)
    assert cur(g).name == p0 and g.turns_left == 1

    g.players[p2].alive = False
    with pytest.raises(GameError):
        g.debug_set_turn(p2, 1)

    # debug_toggle_blind
    assert g.debug_toggle_blind(p1) is True
    assert g.players[p1].blind is True
    assert g.debug_toggle_blind(p1) is False
    assert g.players[p1].blind is False

    # debug_remove_card
    target_card = g.players[p0].hand[0]
    g.players[p0].marked_id = target_card.id
    g.debug_remove_card(p0, target_card.id)
    assert target_card not in g.players[p0].hand
    assert g.grave[-1].id == target_card.id
    assert g.players[p0].marked_id is None
    with pytest.raises(GameError):
        g.debug_remove_card(p0, "missing.0.999")

    # phase ended rejects debug_set_turn
    g.phase = "ended"
    with pytest.raises(GameError):
        g.debug_set_turn(p0, 1)


def test_debug_snapshot_omniscient_fields_and_copy_safety():
    g = make_game(3)
    p0, p1, p2 = g.order
    g.players[p1].blind = True
    g.players[p1].extra_turns = 2
    g.players[p1].illtake_by = p0
    g.players[p1].standby_defuse = True
    g.players[p1].marked_id = g.players[p1].hand[0].id
    g.tower_wearer = p0
    g._say("secret msg", private=p1)
    top_imp = g.debug_put_deck("implodingkitten", index=0, faceup=True)
    g.pending = {"kind": "yes_no", "owner": p0, "data": {"question": "test?"}}
    nope_card = give(g, p0, "skip")
    g.nope = {
        "actor": p0,
        "card": nope_card,
        "as_type": None,
        "stack": [Card(id="nope.0.s", type="nope", variant=0)],
        "responded": {p2, p1},
        "effect": lambda: None,
    }
    g.nope_deadline = 1700000000.5

    snap = g.debug_snapshot()
    assert snap["phase"] == "playing"
    assert snap["desk_name"] == g.desk_name
    assert snap["winner"] is None
    assert snap["turn"] == {"current": p0, "turns_left": 1, "direction": 1}
    assert snap["deck_count"] == g.deck.size()
    assert len(snap["deck"]) <= 30
    assert snap["deck"][0] == {
        "id": top_imp.id,
        "type": "implodingkitten",
        "variant": 0,
        "faceup": True,
    }
    assert "faceup" in snap["deck"][1]
    assert snap["stash_count"] == len(g.stash)
    assert snap["tower_wearer"] == p0

    # pending là safe copy
    assert snap["pending"] == g.pending
    snap["pending"]["data"]["question"] = "mutated"
    assert g.pending["data"]["question"] == "test?"

    # nope snapshot
    assert snap["nope"]["actor"] == p0
    assert snap["nope"]["card"]["id"] == nope_card.id
    assert snap["nope"]["stacked"] == 1
    assert snap["nope"]["responded"] == sorted([p1, p2])
    assert snap["nope"]["ends_ms"] == 1700000000500

    # players toàn tri (thấy tay người bị mù)
    assert [p["name"] for p in snap["players"]] == g.order
    p1_snap = snap["players"][1]
    assert p1_snap["blind"] is True
    assert p1_snap["extra_turns"] == 2
    assert p1_snap["illtake_by"] == p0
    assert p1_snap["standby_defuse"] is True
    assert p1_snap["marked_id"] == g.players[p1].marked_id
    assert p1_snap["count"] == len(g.players[p1].hand)
    assert len(p1_snap["hand"]) == len(g.players[p1].hand)

    # log_entries gồm cả private
    assert any(e["text"] == "secret msg" and e["private"] == p1 for e in snap["log_entries"])


def test_last_boom_reports_exact_variant():
    # 1. Face-up Imploding Kitten -> variant == "imploding"
    g1 = make_game(2)
    cur = g1.current().name
    g1.players[cur].hand = [c for c in g1.players[cur].hand if c.type != "defuse"]
    g1.debug_put_deck("implodingkitten", index=0, faceup=True)
    g1.draw(cur)
    assert g1.last_boom == {"seq": 1, "who": cur, "variant": "imploding"}
    assert g1.view(cur)["last_boom"] == {"seq": 1, "who": cur, "variant": "imploding"}

    # 2. Exploding Kitten -> variant == "exploding"
    g2 = make_game(2)
    cur2 = g2.current().name
    g2.players[cur2].hand = [c for c in g2.players[cur2].hand if c.type not in ("defuse", "streakingkitten", "zombiekitten", "godcat")]
    g2.debug_put_deck("explodingkitten", index=0)
    g2.draw(cur2)
    assert g2.last_boom == {"seq": 1, "who": cur2, "variant": "exploding"}

    # 3. Armageddon Devilcat kill -> variant == "devilcat"
    g3 = make_game(2)
    cur3 = g3.current().name
    g3.players[cur3].hand = []
    g3._resolve_armageddon_fate(g3.players[cur3], Card(id="dc.0.99", type="devilcat", variant=0))
    assert g3.last_boom == {"seq": 1, "who": cur3, "variant": "devilcat"}


# ---------- Manual blind card picking & opaque blind slots ----------


def test_curse_shuffles_hand_and_exposes_opaque_blind_slots_with_zero_leak():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    # Give a known large hand so shuffle changes order deterministically with a seeded RNG
    cards = [
        Card(id=f"c.{i}", type=t, variant=i % 3)
        for i, t in enumerate(["defuse", "skip", "attack2x", "favor", "cat", "nope", "shuffle", "reverse"])
    ]
    g.players[other].hand = list(cards)
    g.players[other].marked_id = cards[0].id
    before_ids = [c.id for c in g.players[other].hand]

    random.seed(12345)
    give(g, first, "curseofthecatbutt")
    act(g, first, "curseofthecatbutt")
    assert g.pending == {"kind": "pick_player", "owner": first, "data": {"candidates": [other], "reason": "curse"}}
    g.respond(first, {"player": other})

    assert g.players[other].blind is True
    after_ids = [c.id for c in g.players[other].hand]
    assert sorted(after_ids) == sorted(before_ids)
    assert after_ids != before_ids  # hand was shuffled on curse

    v = g.view(other)
    expected_hand = [
        {"id": f"blind.{i}", "type": "hidden", "variant": 0, "blind_index": i}
        for i in range(len(cards))
    ]
    assert v["you"]["hand"] == expected_hand
    assert v["you"]["hand_count"] == len(cards)
    assert v["you"]["marked"] is None
    # Own entry in players list must also not leak marked card to blind player
    other_idx = g.order.index(other)
    assert v["players"][other_idx]["marked"] is None
    # Opponents still see the marked card
    assert g.view(first)["players"][other_idx]["marked"]["id"] == cards[0].id

    # Zero real card id or type leaked anywhere in you.hand
    real_ids = set(after_ids)
    real_types = {c.type for c in cards}
    for slot in v["you"]["hand"]:
        assert slot["id"] not in real_ids
        assert slot["type"] == "hidden"
        assert slot["type"] not in real_types
        assert slot["variant"] == 0


def test_blind_manual_play_card_exact_slot_waste_and_execute():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[first].blind = True
    defuse_card = Card(id="defuse.1.slot0", type="defuse", variant=1)
    skip_card = Card(id="skip.2.slot1", type="skip", variant=2)
    cat_card = Card(id="cat.0.slot2", type="cat", variant=0)
    g.players[first].hand = [defuse_card, skip_card, cat_card]

    # Rejects malformed, out-of-range, and guessed real card IDs while blind
    for bad_id in ("blind.-1", "blind.3", "blind.abc", "blind.00", skip_card.id):
        with pytest.raises(GameError):
            g.play_card(first, bad_id)
    assert [c.id for c in g.players[first].hand] == [defuse_card.id, skip_card.id, cat_card.id]

    # Picking blind.0 wastes the EXACT defuse at hand[0]
    g.play_card(first, "blind.0")
    assert g.grave[-1].id == defuse_card.id
    assert [c.id for c in g.players[first].hand] == [skip_card.id, cat_card.id]
    assert any("Defuse" in line and "graveyard" in line for line in g.log[-3:])
    # Still first's turn after wasting an unplayable card
    assert cur(g).name == first

    # Now skip_card is at index 0; picking blind.0 plays THAT exact skip!
    g.play_card(first, "blind.0")
    assert g.grave[-1].id == skip_card.id
    assert [c.id for c in g.players[first].hand] == [cat_card.id]
    assert g.nope is not None and g.nope["card"].id == skip_card.id
    all_pass(g)
    # Skip resolved and ended first's turn -> now other's turn
    assert cur(g).name == other


def test_blind_manual_respond_favor_and_potluck_godcat_guard():
    # 1. Favor: blind victim manually picks blind.1 -> transfers EXACT hand[1]
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    g.players[other].blind = True
    c0 = Card(id="defuse.0.f0", type="defuse", variant=0)
    c1 = Card(id="attack2x.0.f1", type="attack2x", variant=0)
    c2 = Card(id="skip.0.f2", type="skip", variant=0)
    g.players[other].hand = [c0, c1, c2]

    give(g, first, "favor")
    act(g, first, "favor")
    g.respond(first, {"player": other})
    assert g.pending["kind"] == "pick_card" and g.pending["owner"] == other

    # Rejects real card ID and out-of-range blind index
    with pytest.raises(GameError):
        g.respond(other, {"card_id": c1.id})
    with pytest.raises(GameError):
        g.respond(other, {"card_id": "blind.5"})
    assert g.pending is not None

    # Picking blind.1 transfers c1 (attack2x) to first
    g.respond(other, {"card_id": "blind.1"})
    assert g.pending is None
    assert [c.id for c in g.players[other].hand] == [c0.id, c2.id]
    assert any(c.id == c1.id for c in g.players[first].hand)

    # 2. Potluck: blind player picks godcat slot -> blocked without revealing godcat; non-godcat succeeds
    g2 = make_game(2)
    first2, other2 = g2.order[0], g2.order[1]
    g2.players[other2].blind = True
    gc = Card(id="godcat.0.p0", type="godcat", variant=0)
    sk = Card(id="skip.0.p1", type="skip", variant=0)
    g2.players[other2].hand = [gc, sk]

    give(g2, first2, "potluck")
    give(g2, first2, "shuffle")
    act(g2, first2, "potluck")
    g2.respond(first2, {"card_id": next(c.id for c in g2.players[first2].hand if c.type == "shuffle")})
    assert g2.pending["owner"] == other2

    with pytest.raises(GameError) as exc_info:
        g2.respond(other2, {"card_id": "blind.0"})
    assert "godcat" not in str(exc_info.value).lower()
    assert g2.pending is not None and g2.pending["owner"] == other2

    g2.respond(other2, {"card_id": "blind.1"})
    assert g2.pending is None
    assert [c.id for c in g2.players[other2].hand] == [gc.id]
    assert g2.deck.peek(1)[0].id == sk.id

    # 3. Garbage Collection (reason="into_deck"): same godcat protection for blind slots
    g3 = make_game(2)
    first3, other3 = g3.order[0], g3.order[1]
    g3.players[other3].blind = True
    gc3 = Card(id="godcat.0.g0", type="godcat", variant=0)
    rv3 = Card(id="reverse.0.g1", type="reverse", variant=0)
    g3.players[other3].hand = [gc3, rv3]

    give(g3, first3, "garbagecollection")
    give(g3, first3, "shuffle")
    act(g3, first3, "garbagecollection")
    g3.respond(first3, {"card_id": next(c.id for c in g3.players[first3].hand if c.type == "shuffle")})
    assert g3.pending["owner"] == other3

    with pytest.raises(GameError) as exc_info3:
        g3.respond(other3, {"card_id": "blind.0"})
    assert "godcat" not in str(exc_info3.value).lower()
    g3.respond(other3, {"card_id": "blind.1"})
    assert g3.pending is None
    assert [c.id for c in g3.players[other3].hand] == [gc3.id]
    assert any(c.id == rv3.id for c in g3.deck.cards)


def test_blind_play_exploding_kitten_from_hand_triggers_blind_defuse():
    g = make_game(3)
    first = cur(g).name
    p = g.players[first]
    p.blind = True
    ek = Card(id="explodingkitten.0.hand", type="explodingkitten", variant=0)
    sk = Card(id="streakingkitten.0.hand", type="streakingkitten", variant=0)
    df = Card(id="defuse.0.hand", type="defuse", variant=0)
    p.hand = [ek, sk, df]

    g.play_card(first, "blind.0")
    assert g.pending is not None
    assert g.pending["kind"] == "pick_card"
    assert g.pending["data"]["reason"] == "blind_defuse"
    assert p.blind is True

    # Chọn trúng defuse ở blind.1 -> cứu sống, gỡ mù và cho chèn lại bom
    g.respond(first, {"card_id": "blind.1"})
    assert p.alive is True and p.blind is False
    assert g.pending["kind"] == "pick_index"
    g.respond(first, {"index": 0})
    assert g.pending is None
    assert g.deck.peek(1)[0].id == ek.id


def test_fx_events_seq_monotone_and_view_cap():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    for _ in range(15):
        force_turn(g, first)
        g.turns_left = 1
        give(g, first, "skip")
        act(g, first, "skip")

    v = g.view(first)
    fx = v["fx_events"]
    assert len(fx) == 12
    seqs = [e["seq"] for e in fx]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)
    assert seqs[-1] == 15
    assert seqs[0] == 4
    # Internal buffer capped at 20
    assert len(g._fx_events) <= 20


def test_fx_events_nope_blocks_card_fx_and_emits_nope():
    g = make_game(2)
    first, other = g.order[0], g.order[1]
    give(g, first, "skip")
    give(g, other, "nope")
    play_type(g, first, "skip")
    assert g.view(first)["fx_events"] == []

    g.stack_nope(other)
    g.pass_nope(first)
    g.resolve_nope()

    fx = g.view(first)["fx_events"]
    assert len(fx) == 1
    assert fx[0]["kind"] == "nope"
    assert fx[0]["actor"] == other
    assert fx[0]["count"] == 1
    assert not any(e["kind"] == "card_fx" for e in fx)


def test_fx_events_draw_privacy_and_sources():
    g = make_game(2)
    first = cur(g).name
    secret_top = Card(id="seethefuture3x.0.s1", type="seethefuture3x", variant=0)
    secret_bot = Card(id="attack2x.0.s2", type="attack2x", variant=0)
    g.deck.cards.append(secret_top)
    g.deck.cards.insert(0, secret_bot)

    g.draw(first)
    force_turn(g, first)
    give(g, first, "drawfromthebottom")
    act(g, first, "drawfromthebottom")

    fx = g.view(first)["fx_events"]
    assert [(e["kind"], e["actor"], e.get("source")) for e in fx] == [
        ("draw", first, "top"),
        ("draw", first, "bottom"),
    ]
    for ev in fx:
        assert "card_type" not in ev
        assert "card_id" not in ev
        assert "seethefuture3x" not in str(ev)
        assert "attack2x" not in str(ev)


def test_fx_events_transfers_privacy_and_put_deck():
    g = make_game(2)
    first, other = g.order[0], g.order[1]

    # 1. Favor transfer: secret card_type must NEVER appear
    secret_favor = Card(id="defuse.0.fav", type="defuse", variant=0)
    g.players[other].hand.append(secret_favor)
    give(g, first, "favor")
    act(g, first, "favor")
    g.respond(first, {"player": other})
    g.respond(other, {"card_id": secret_favor.id})

    # 2. Pair steal transfer
    c1 = give(g, first, "cat", 1)
    c2 = give(g, first, "cat", 1)
    secret_steal = Card(id="zombiekitten.0.stl", type="zombiekitten", variant=0)
    g.players[other].hand = [secret_steal]
    g.play_combo(first, "pair", [c1.id, c2.id])
    all_pass(g)
    g.respond(first, {"player": other})
    g.respond(first, {"position": 0})

    # 3. Bury put_deck: secret buried card type must NEVER appear
    secret_bury = Card(id="clairvoyance.0.bry", type="clairvoyance", variant=0)
    g.deck.cards.append(secret_bury)
    give(g, first, "bury")
    act(g, first, "bury")
    g.respond(first, {"index": 0})

    fx = g.view(other)["fx_events"]
    assert len(fx) == 6
    assert fx[0] == {"seq": fx[0]["seq"], "kind": "card_fx", "actor": first, "card_type": "favor"}
    assert fx[1] == {"seq": fx[1]["seq"], "kind": "transfer", "actor": other, "target": first, "card_type": "favor"}
    assert fx[2] == {"seq": fx[2]["seq"], "kind": "card_fx", "actor": first, "card_type": "combo_pair", "source": "cat", "count": 2}
    assert fx[3] == {"seq": fx[3]["seq"], "kind": "transfer", "actor": other, "target": first, "card_type": "steal"}
    assert fx[4] == {"seq": fx[4]["seq"], "kind": "card_fx", "actor": first, "card_type": "bury"}
    assert fx[5] == {"seq": fx[5]["seq"], "kind": "put_deck", "actor": first, "card_type": "bury"}
    for ev in fx:
        s = str(ev)
        assert "defuse" not in s
        assert "zombiekitten" not in s
        assert "clairvoyance" not in s


def test_fx_events_defuse_and_bomb_put_deck():
    g = make_game(2)
    first = cur(g).name
    bomb = Card(id="explodingkitten.0.fx", type="explodingkitten", variant=0)
    g.deck.cards.append(bomb)
    g.players[first].hand = [Card(id="defuse.0.fx", type="defuse", variant=0)]

    g.draw(first)
    g.respond(first, {"index": 2})

    fx = g.view(first)["fx_events"]
    assert [(e["kind"], e["actor"], e.get("card_type"), e.get("source")) for e in fx] == [
        ("draw", first, None, "top"),
        ("defuse", first, "defuse", None),
        ("put_deck", first, "explodingkitten", None),
    ]


def test_fx_events_card_cutscenes_and_mark_curse_privacy():
    g = make_game(3)
    p0, p1, p2 = g.order[0], g.order[1], g.order[2]

    # attack2x
    give(g, p0, "attack2x")
    act(g, p0, "attack2x")
    assert g.view(p0)["fx_events"][-1] == {
        "seq": 1, "kind": "card_fx", "actor": p0, "target": p1, "card_type": "attack2x", "count": 2,
    }

    # reverse
    give(g, p1, "reverse")
    act(g, p1, "reverse")
    assert g.view(p1)["fx_events"][-1] == {
        "seq": 2, "kind": "card_fx", "actor": p1, "card_type": "reverse",
    }

    # shuffle
    give(g, p1, "shuffle")
    act(g, p1, "shuffle")
    assert g.view(p1)["fx_events"][-1] == {
        "seq": 3, "kind": "card_fx", "actor": p1, "card_type": "shuffle",
    }

    # mark (must NOT leak marked card type in fx_events)
    g.players[p0].hand = [Card(id="defuse.0.mk", type="defuse", variant=0)]
    give(g, p1, "mark")
    act(g, p1, "mark")
    g.respond(p1, {"player": p0})
    mark_ev = g.view(p1)["fx_events"][-1]
    assert mark_ev == {"seq": 4, "kind": "card_fx", "actor": p1, "target": p0, "card_type": "mark"}

    # curseofthecatbutt
    give(g, p1, "curseofthecatbutt")
    act(g, p1, "curseofthecatbutt")
    g.respond(p1, {"player": p0})
    curse_ev = g.view(p1)["fx_events"][-1]
    assert curse_ev == {
        "seq": 5, "kind": "card_fx", "actor": p1, "target": p0, "card_type": "curseofthecatbutt",
    }


def test_fx_events_epic_cards_devilcat_tower_catomic_attack_dead():
    g = make_game(3)
    p0, p1, p2 = g.order[0], g.order[1], g.order[2]

    # devilcat -> playmat + card_fx without "chưa cài đặt"
    give(g, p0, "devilcat")
    play_type(g, p0, "devilcat")
    assert g.view(p0)["fx_events"][-1] == {
        "seq": 1, "kind": "card_fx", "actor": p0, "card_type": "devilcat",
    }
    assert all("chưa cài đặt" not in line for line in g.log)

    # towerofpower -> card_fx
    give(g, p0, "towerofpower")
    act(g, p0, "towerofpower")
    assert g.view(p0)["fx_events"][-1] == {
        "seq": 2, "kind": "card_fx", "actor": p0, "card_type": "towerofpower",
    }

    # catomicbomb -> card_fx
    give(g, p0, "catomicbomb")
    act(g, p0, "catomicbomb")
    assert g.view(p0)["fx_events"][-1] == {
        "seq": 3, "kind": "card_fx", "actor": p0, "card_type": "catomicbomb",
    }

    # attackofthedead (1 dead player -> 3 turns on p2)
    g.players[p0].alive = False
    force_turn(g, p1)
    g.turns_left = 1
    give(g, p1, "attackofthedead")
    act(g, p1, "attackofthedead")
    assert g.view(p1)["fx_events"][-1] == {
        "seq": 4, "kind": "card_fx", "actor": p1, "target": p2, "card_type": "attackofthedead", "count": 3,
    }


def test_fx_events_godcat_and_armageddon():
    g = make_game(2)
    first, other = g.order[0], g.order[1]

    # 1. Nope-cancelled godcat must NOT emit godcat or eff_type card_fx
    give(g, first, "godcat")
    give(g, other, "nope")
    play_type(g, first, "godcat", as_type="skip")
    g.stack_nope(other)
    g.pass_nope(first)
    g.resolve_nope()
    fx_cancel = g.view(first)["fx_events"]
    assert len(fx_cancel) == 1
    assert fx_cancel[0]["kind"] == "nope"
    assert not any(e["kind"] == "card_fx" for e in fx_cancel)

    # 2. Executed godcat via play_card emits godcat (with source) + eff_type
    force_turn(g, first)
    give(g, first, "godcat")
    act(g, first, "godcat", as_type="skip")
    fx_play = g.view(first)["fx_events"]
    assert fx_play[-2] == {
        "seq": fx_play[-2]["seq"],
        "kind": "card_fx",
        "actor": first,
        "card_type": "godcat",
        "source": "skip",
    }
    assert fx_play[-1] == {
        "seq": fx_play[-1]["seq"],
        "kind": "card_fx",
        "actor": first,
        "card_type": "skip",
    }

    # 3. Executed godcat via play_now (off-turn) emits godcat + eff_type
    force_turn(g, first)
    god_now = give(g, other, "godcat")
    g.play_now(other, god_now.id, as_type="shufflenow")
    all_pass(g)
    fx_now = g.view(other)["fx_events"]
    assert fx_now[-2] == {
        "seq": fx_now[-2]["seq"],
        "kind": "card_fx",
        "actor": other,
        "card_type": "godcat",
        "source": "shufflenow",
    }
    assert fx_now[-1] == {
        "seq": fx_now[-1]["seq"],
        "kind": "card_fx",
        "actor": other,
        "card_type": "shufflenow",
    }

    # 4. Armageddon emits card_fx when triggered (devilcat + godcat on playmat)
    give(g, first, "devilcat")
    play_type(g, first, "devilcat")
    give(g, first, "defuse")
    give(g, other, "defuse")
    give(g, first, "armageddon")
    act(g, first, "armageddon")
    assert g.view(first)["fx_events"][-1] == {
        "seq": g.view(first)["fx_events"][-1]["seq"],
        "kind": "card_fx",
        "actor": first,
        "card_type": "armageddon",
    }
    g.respond(first, {"player": other})
    g.respond(other, {"value": True})
    assert any(e["kind"] == "receive" and e["card_type"] == "godcat" for e in g.view(first)["fx_events"])


def test_fx_events_barking_kitten_solo_and_paired():
    g = make_game(2)
    p0, p1 = g.order[0], g.order[1]

    # 1. Solo faceup placement
    give(g, p0, "barkingkitten", variant=0)
    play_type(g, p0, "barkingkitten")
    assert any(c.type == "barkingkitten" for c in g.players[p0].faceup)
    assert g.view(p0)["fx_events"][-1] == {
        "seq": 1, "kind": "card_fx", "actor": p0, "card_type": "barkingkitten",
    }

    # 2. Paired match against p0's faceup barkingkitten (p0 defuses)
    force_turn(g, p1)
    g.players[p0].hand = [Card(id="defuse.0.bk", type="defuse", variant=0)]
    give(g, p1, "barkingkitten", variant=1)
    play_type(g, p1, "barkingkitten")
    fx = g.view(p1)["fx_events"]
    assert fx[-2] == {"seq": 2, "kind": "card_fx", "actor": p1, "card_type": "barkingkitten"}
    assert fx[-1] == {"seq": 3, "kind": "defuse", "actor": p0, "card_type": "defuse"}


def test_fx_events_clone_combo_imploding_arm_and_favor_call():
    g = make_game(2)
    p0, p1 = g.order[0], g.order[1]

    # 1. Clone emits clone (source=beneath.type) followed by copied card_fx
    give(g, p0, "skip")
    act(g, p0, "skip")
    force_turn(g, p0)
    give(g, p0, "clone")
    act(g, p0, "clone")
    fx = g.view(p0)["fx_events"]
    assert fx[-2] == {"seq": fx[-2]["seq"], "kind": "card_fx", "actor": p0, "card_type": "clone", "source": "skip"}
    assert fx[-1] == {"seq": fx[-1]["seq"], "kind": "card_fx", "actor": p0, "card_type": "skip"}

    # 2. Combo pair & three (and cancelled combo emits neither)
    force_turn(g, p0)
    g.players[p1].hand = [Card(id="nope.0.cmb", type="nope", variant=0), Card(id="cat.0.trg", type="cat", variant=0)]
    c1 = give(g, p0, "cat", 0)
    c2 = give(g, p0, "cat", 0)
    g.play_combo(p0, "pair", [c1.id, c2.id])
    g.stack_nope(p1)
    g.pass_nope(p0)
    g.resolve_nope()
    assert not any(e.get("card_type") == "combo_pair" for e in g.view(p0)["fx_events"])

    force_turn(g, p0)
    f1 = give(g, p0, "feralcat", 0)
    f2 = give(g, p0, "cat", 5)
    g.play_combo(p0, "pair", [f1.id, f2.id])
    all_pass(g)
    assert g.view(p0)["fx_events"][-1] == {
        "seq": g.view(p0)["fx_events"][-1]["seq"],
        "kind": "card_fx",
        "actor": p0,
        "card_type": "combo_pair",
        "source": "cat",
        "count": 2,
    }
    g.respond(p0, {"player": p1})
    g.respond(p0, {"position": 0})

    force_turn(g, p0)
    g.players[p1].hand.append(Card(id="skip.0.three", type="skip", variant=0))
    t1 = Card(id="feralcat.0.three1", type="feralcat", variant=0)
    t2 = Card(id="feralcat.0.three2", type="feralcat", variant=0)
    t3 = Card(id="feralcat.0.three3", type="feralcat", variant=0)
    g.players[p0].hand.extend([t1, t2, t3])
    g.play_combo(p0, "three", [t1.id, t2.id, t3.id])
    all_pass(g)
    assert g.view(p0)["fx_events"][-1] == {
        "seq": g.view(p0)["fx_events"][-1]["seq"],
        "kind": "card_fx",
        "actor": p0,
        "card_type": "combo_three",
        "source": "feralcat",
        "count": 3,
    }
    g.respond(p0, {"player": p1})
    g.respond(p0, {"text": "skip"})

    # 3. Imploding Kitten first draw (faceup arming)
    force_turn(g, p0)
    imp = Card(id="implodingkitten.0.arm", type="implodingkitten", variant=0, faceup=False)
    g.deck.cards.append(imp)
    g.draw(p0)
    assert g.view(p0)["fx_events"][-1] == {
        "seq": g.view(p0)["fx_events"][-1]["seq"],
        "kind": "card_fx",
        "actor": p0,
        "card_type": "imploding_arm",
    }
    g.respond(p0, {"index": 0})

    # 4. Favor emits favor card_fx immediately before player chooses target
    force_turn(g, p1)
    give(g, p1, "favor")
    act(g, p1, "favor")
    assert g.view(p1)["fx_events"][-1] == {
        "seq": g.view(p1)["fx_events"][-1]["seq"],
        "kind": "card_fx",
        "actor": p1,
        "card_type": "favor",
    }


