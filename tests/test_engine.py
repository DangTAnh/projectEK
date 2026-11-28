"""Test engine theo resources/cards_desc/*.txt — chạy pytest không cần server."""

import random

import pytest

from server.engine import Game, GameError
from server.engine.cards import CARD_META
from server.engine.deck import Deck

# ---------- helpers ----------


def make_game(n=3, seed=42):
    random.seed(seed)
    g = Game([f"P{i}" for i in range(n)])
    g.start()
    g.turn_index = 0  # deterministic: P0 luôn đi trước (deck xáo khác theo pool)
    return g


def cur(g):
    return g.players[g.order[g.turn_index]]


def give(g, name, ctype, variant=0):
    """Lấy 1 lá từ deck (khớp type/variant) đưa vào tay; không có thì chế lá giả."""
    for i, c in enumerate(g.deck.cards):
        if c.type == ctype and c.variant == variant:
            card = g.deck.cards.pop(i)
            g.players[name].hand.append(card)
            return card
    from server.engine.cards import Card
    card = Card(id=f"{ctype}.{variant}.test", type=ctype, variant=variant)
    g.players[name].hand.append(card)
    return card


def find_hand(g, name, ctype):
    return next((c for c in g.players[name].hand if c.type == ctype), None)


def hand_ids(g, name):
    return [c.id for c in g.players[name].hand]


def play_type(g, name, ctype, **kw):
    card = find_hand(g, name, ctype)
    assert card is not None, f"{name} không có {ctype}"
    g.play_card(name, card.id, **kw)


def act(g, name, ctype, **kw):
    """Chơi thẻ + đóng cửa sổ Nope nếu mở (mặc định thẻ nopeable mở window)."""
    play_type(g, name, ctype, **kw)
    if g.nope is not None:
        all_pass(g)


def all_pass(g):
    for p in g.alive():
        if p.name != g.nope["actor"] and p.name not in g.nope["responded"]:
            g.pass_nope(p.name)
    g.resolve_nope()


def force_turn(g, name):
    """Ép turn về người chơi name (giả định cùng alive)."""
    g.turn_index = g.order.index(name)


# ---------- chia bài ----------


class TestDeal:
    def test_formula(self):
        g = make_game(4)
        for name in g.order:
            p = g.players[name]
            assert len(p.hand) == 5  # 4 thường + 1 defuse
            assert p.has_type("defuse")
        ek_in_deck = sum(1 for c in g.deck.cards if c.type == "explodingkitten")
        assert ek_in_deck == 3  # N-1
        total = (sum(len(p.hand) for p in g.players.values())
                 + g.deck.size() + len(g.stash))
        pool = Deck()
        pool.load_pool("original")
        non_bomb = sum(1 for c in pool.cards if c.type != "explodingkitten")
        assert total == non_bomb + 3  # original.json có sẵn 20 bom bị engine lọc, thay bằng N-1 bom mới

    def test_stash_six(self):
        g = make_game(4)
        assert len(g.stash) == 6
        assert all(c.type not in ("explodingkitten", "implodingkitten") for c in g.stash)
        assert all(c.id for c in g.stash)

    def test_unique_ids(self):
        g = make_game(3)
        ids = [c.id for c in g.deck.cards] + [c.id for c in g.stash] + [
            c.id for p in g.players.values() for c in p.hand]
        assert len(ids) == len(set(ids))


# ---------- lượt & rút ----------


class TestTurn:
    def test_draw_ends_turn(self):
        g = make_game(2)
        first = cur(g).name
        other = g.order[1 - g.order.index(first)]
        put_top_safe(g, "skip")
        g.draw(first)
        assert cur(g).name == other

    def test_skip_consumes_turn(self):
        g = make_game(3)
        first = cur(g).name
        give(g, first, "skip")
        act(g, first, "skip")
        assert cur(g).name != first

    def test_superskip_clears_bonus(self):
        g = make_game(2)
        first = cur(g).name
        cur(g).extra_turns = 3
        give(g, first, "superskip")
        act(g, first, "superskip")
        assert cur(g).name != first

    def test_attack_gives_next_2(self):
        g = make_game(3)
        first = cur(g).name
        nxt_name = g.order[(g.turn_index + 1) % 3]
        give(g, first, "attack2x")
        act(g, first, "attack2x")
        assert cur(g).name == nxt_name
        assert g.turns_left == 2  # 1 lượt cơ bản + 1 lượt thưởng

    def test_reverse_flips(self):
        g = make_game(3)
        first = cur(g).name
        idx = g.turn_index
        give(g, first, "reverse")
        act(g, first, "reverse")
        assert g.direction == -1

    def test_personalattack_keeps_turn(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "personalattack3x")
        act(g, first, "personalattack3x")
        assert cur(g).name == first  # vẫn lượt mình
        assert g.turns_left == 3  # +2 lượt NGAY, không qua vòng

    def test_shuffle_is_noop_visible(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "shuffle")
        n = g.deck.size()  # đo sau give: give pop lá thật khỏi deck
        act(g, first, "shuffle")
        assert g.deck.size() == n


def put_top_safe(g, ctype):
    """Chuyển 1 lá ctype trong deck lên đỉnh."""
    for i in range(len(g.deck.cards)):
        if g.deck.cards[i].type == ctype:
            g.deck.cards.append(g.deck.cards.pop(i))
            return
    raise AssertionError(ctype)


# ---------- rút bom / rescue ----------


class TestDrawResolution:
    def test_defuse_then_pick_index(self):
        g = make_game(2)
        first = cur(g).name
        put_top_safe(g, "explodingkitten")
        g.draw(first)
        assert g.pending and g.pending["kind"] == "pick_index"
        size_before = g.deck.size()
        g.respond(first, {"index": 2})
        assert g.pending is None
        assert g.deck.size() == size_before + 1
        assert not find_hand(g, first, "defuse")

    def test_bomb_kill_keeps_hand(self):
        g = make_game(3)
        first = cur(g).name
        p = g.players[first]
        dfuse = find_hand(g, first, "defuse")
        p.hand.remove(dfuse)  # bỏ defuse để chết
        put_top_safe(g, "explodingkitten")
        g.draw(first)
        assert not p.alive
        assert len(p.hand) > 0  # chết GIỮ tay bài (phục vụ feedthedead/graverobber)
        assert any(c.type == "explodingkitten" for c in g.grave)

    def test_streaking_keep_decline_falls_through(self):
        g = make_game(2)
        first = cur(g).name
        p = g.players[first]
        for c in list(p.hand):
            if c.type == "defuse":
                p.hand.remove(c)
        give(g, first, "streakingkitten", 1)
        put_top_safe(g, "explodingkitten")
        g.draw(first)
        assert g.pending["kind"] == "yes_no"
        g.respond(first, {"value": True})
        streak = find_hand(g, first, "streakingkitten")
        assert streak is not None  # giữ bom MIỄN LÀ streaking còn trên tay
        assert any(c.type == "explodingkitten" for c in p.hand)  # giữ bom trên tay

    def test_imploding_first_lay_faceup_back(self):
        g = make_game(2)
        first = cur(g).name
        imp = give(g, first, "implodingkitten")  # mượn lá để đặt deck
        g.players[first].hand.remove(imp)
        imp.faceup = False
        g.deck.insert(imp, 0)
        size_before = g.deck.size()
        g.draw(first)
        assert g.pending["kind"] == "pick_index"
        assert g.revealed and g.revealed[0].type == "implodingkitten"
        g.respond(first, {"index": 0})
        assert imp.faceup is True
        assert g.deck.size() == size_before  # chèn lại, KHÔNG tốn defuse
        assert find_hand(g, first, "defuse") is not None

    def test_zombie_revives_dead(self):
        g = make_game(3)
        victim = g.order[2]
        g.players[victim].alive = False
        first = cur(g).name
        p = g.players[first]
        for c in list(p.hand):
            if c.type == "defuse":
                p.hand.remove(c)
        give(g, first, "zombiekitten")
        put_top_safe(g, "explodingkitten")
        g.draw(first)
        assert g.pending["kind"] == "yes_no"  # dùng zombie?
        g.respond(first, {"value": True})
        assert g.pending["kind"] == "pick_index"  # chèn bom lại
        g.respond(first, {"index": 5})
        assert g.pending["kind"] == "pick_player"  # hồi sinh ai?
        g.respond(first, {"player": victim})
        assert g.players[victim].alive
        assert find_hand(g, first, "zombiekitten") is None


# ---------- nope ----------


class TestNope:
    def test_nope_cancels_action(self):
        g = make_game(3)
        first = cur(g).name
        give(g, first, "skip")
        give(g, "P1", "nope")
        play_type(g, first, "skip")
        assert g.nope is not None
        g.stack_nope("P1")  # 1 Nope lẻ -> hủy
        all_pass(g)
        assert any("Nope" in m for m in g.log)
        # skip bị hủy -> vẫn lượt first
        assert cur(g).name == first

    def test_double_nope_reinstates(self):
        g = make_game(3)
        first = cur(g).name
        give(g, first, "shuffle")
        give(g, "P1", "nope")
        give(g, "P2", "nope")
        play_type(g, first, "shuffle")
        g.stack_nope("P1")
        g.stack_nope("P2")
        g.resolve_nope()
        assert g.phase == "playing"

    def test_cannot_nope_self(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "skip")
        give(g, first, "nope")
        play_type(g, first, "skip")
        with pytest.raises(GameError):
            g.stack_nope(first)

    def test_play_card_blocked_in_window(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "skip")
        give(g, first, "skip", 1)
        give(g, "P1", "nope")
        play_type(g, first, "skip")
        with pytest.raises(GameError):
            play_type(g, first, "skip")


# ---------- nhóm thẻ nhìn/xáo ----------


class TestFutureCards:
    def test_seethefuture_private_peek(self):
        g = make_game(2)
        first = cur(g).name
        expected = [c.to_dict() for c in g.deck.peek(3)]
        give(g, first, "seethefuture3x")
        act(g, first, "seethefuture3x")
        assert g.private_peeks[first] == expected

    def test_alter_future_reorder(self):
        g = make_game(2)
        first = cur(g).name
        top_before = [c.type for c in g.deck.peek(3)]
        give(g, first, "alter3x")
        act(g, first, "alter3x")
        assert g.pending["kind"] == "reorder"
        ids = [c["id"] for c in g.pending["data"]["cards"]]
        g.respond(first, {"order": list(reversed(ids))})
        assert [c.type for c in g.deck.peek(3)] == list(reversed(top_before))

    def test_revealfuture_public(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "revealthefuture3x")
        expected = [c.to_dict() for c in g.deck.peek(3)]
        act(g, first, "revealthefuture3x")
        assert [c.to_dict() for c in g.revealed] == expected

    def test_sharethefuture_shows_next_alive_and_persists_until_next_acts(self):
        g = make_game(3)
        first = cur(g).name
        nxt = g._next_alive(g.current()).name
        other = next(n for n in g.order if n not in (first, nxt))
        # Đảm bảo lá đỉnh sau reorder không phải bom để draw() an toàn
        g.debug_put_deck("skip", index=0)
        g.debug_put_deck("favor", index=0)
        g.debug_put_deck("shuffle", index=0)
        give(g, first, "sharethefuture3x")
        act(g, first, "sharethefuture3x")
        assert g.pending["kind"] == "reorder"
        ids = [c["id"] for c in g.pending["data"]["cards"]]
        reordered = list(reversed(ids))
        g.respond(first, {"order": reordered})

        expected = [c.to_dict() for c in g.deck.peek(3)]
        assert [c["id"] for c in expected] == reordered
        nxt_view = g.view(nxt)["you"]
        assert nxt_view.get("peek") == expected
        assert nxt_view.get("peek_meta", {}).get("source") == "share"
        assert nxt_view.get("peek_meta", {}).get("from") == first
        assert "peek" not in g.view(first)["you"]
        assert "peek" not in g.view(other)["you"]

        # Người đánh tiếp tục rút kết lượt -> người kế tiếp vẫn giữ peek đã được chia sẻ
        g.draw(first)
        assert cur(g).name == nxt
        assert g.view(nxt)["you"].get("peek") == expected

        # Khi chính người kế tiếp hành động -> peek được dọn
        give(g, nxt, "skip")
        act(g, nxt, "skip")
        assert "peek" not in g.view(nxt)["you"]

    def test_sharethefuture_respects_direction_and_skips_dead(self):
        g = make_game(4)
        first = cur(g).name
        idx = g.order.index(first)
        g.direction = -1
        dead_name = g.order[(idx - 1) % 4]
        expected_nxt = g.order[(idx - 2) % 4]
        g.players[dead_name].alive = False

        give(g, first, "sharethefuture3x")
        act(g, first, "sharethefuture3x")
        ids = [c["id"] for c in g.pending["data"]["cards"]]
        g.respond(first, {"order": ids})

        assert g.view(expected_nxt)["you"].get("peek") == [c.to_dict() for c in g.deck.peek(3)]
        assert "peek" not in g.view(dead_name)["you"]

    def test_clairvoyance_bomb_positions(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "clairvoyance")
        g.play_now(first, find_hand(g, first, "clairvoyance").id)
        if g.nope is not None:
            all_pass(g)
        v = g.view("P1")
        assert "bomb_positions" not in v["you"]
        v = g.view(first)
        pos = v["you"]["bomb_positions"]
        assert isinstance(pos, list)

    def test_digdeeper_keep(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "digdeeper")
        put_top_safe(g, "skip")
        dug_type = g.deck.peek(1)[0].type
        act(g, first, "digdeeper")
        assert g.pending["kind"] == "yes_no"
        g.respond(first, {"value": True})
        assert find_hand(g, first, dug_type) is not None

    def test_raisingheck_bottom_to_top(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "raisingheck")
        bottom_type = g.deck.cards[0].type
        act(g, first, "raisingheck")
        g.respond(first, {"value": False})  # không giữ -> lên đỉnh
        assert g.deck.peek(1)[0].type == bottom_type

    def test_catomicbomb_stacks_bombs_on_top(self):
        g = make_game(3)
        first = cur(g).name
        give(g, first, "catomicbomb")
        act(g, first, "catomicbomb")
        n_bombs = sum(1 for c in g.deck.cards if c.type in ("explodingkitten", "implodingkitten"))
        assert all(c.type in ("explodingkitten", "implodingkitten")
                   for c in g.deck.peek(n_bombs))


# ---------- combo & trộm bài ----------


class TestComboSteal:
    def test_pair_steal_from_hand(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "cat", 0)
        give(g, first, "cat", 0)
        g.stash = []  # cạn vương miện để trộm thẳng vào tay
        target_card = give(g, other, "favor")
        before = len(g.players[other].hand)
        g.play_combo(first, "pair", hand_ids(g, first)[-2:])
        all_pass(g)
        assert g.pending["kind"] == "pick_player"
        g.respond(first, {"player": other})
        assert g.pending["kind"] == "pick_card"  # kẻ trộm chọn úp trong tay victim
        pos = g.players[other].hand.index(target_card)
        g.respond(first, {"position": pos})
        assert target_card in g.players[first].hand
        assert len(g.players[other].hand) == before - 1

    def test_pair_with_feral_wildcard(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        stash_size = len(g.stash)
        give(g, first, "cat", 5)
        give(g, first, "feralcat", 0)
        give(g, other, "nope")
        g.play_combo(first, "pair", hand_ids(g, first)[-2:])
        all_pass(g)
        g.respond(first, {"player": other})
        # victim có tay: kẻ trộm chọn úp 1 lá — stash nguyên vẹn
        assert g.pending["kind"] == "pick_card"
        g.respond(first, {"position": 0})
        assert len(g.stash) == stash_size
        assert len(g.players[first].hand) > 0

    def test_pair_empty_nonwearer_no_steal(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "cat", 7)
        give(g, first, "feralcat", 1)
        g.players[other].hand = []  # victim hết tay và không đội crown: không trộm được
        stash_size = len(g.stash)
        g.play_combo(first, "pair", hand_ids(g, first)[-2:])
        all_pass(g)
        assert g.pending is None
        assert len(g.stash) == stash_size
        assert any("Không có ai để ăn trộm" in m for m in g.log)

    def test_three_calls_named_card(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "cat", 10)
        give(g, first, "cat", 10)
        give(g, first, "feralcat", 0)
        named = give(g, other, "cat", 14)
        g.play_combo(first, "three", hand_ids(g, first)[-3:])
        all_pass(g)
        g.respond(first, {"player": other})
        assert g.pending["kind"] == "input_card"
        assert g.pending["owner"] == first  # kẻ trộm tự nhập tên bài
        g.respond(first, {"text": "cat"})
        assert find_hand(g, first, "cat") is not None
        # victim đã mất lá cat đó
        assert named not in g.players[other].hand

    def test_combo_needs_same_type(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "cat", 0)
        give(g, first, "skip")
        with pytest.raises(GameError):  # mèo + action không thành combo
            g.play_combo(first, "pair", hand_ids(g, first)[-2:])

    def test_receive_bomb_kills_without_defuse(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        # victim không có defuse -> nhận bomb phải chết ngay
        g.players[other].hand = [c for c in g.players[other].hand if c.type != "defuse"]
        bomb = give(g, first, "explodingkitten", 0)
        g.players[first].hand.remove(bomb)
        g._receive_card(g.players[other], bomb)
        assert not g.players[other].alive

    def test_receive_bomb_defuse_saves(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        bomb = give(g, first, "explodingkitten", 0)
        g.players[first].hand.remove(bomb)
        give(g, other, "defuse", 0)
        g._receive_card(g.players[other], bomb)
        # còn sống, đang chờ chèn bom -> pending pick_index
        assert g.players[other].alive
        assert g.pending["kind"] == "pick_index"


# ---------- hiệu ứng lên người ----------


class TestPlayerEffects:
    def test_curse_blinds_target(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "curseofthecatbutt")
        play_type(g, first, "curseofthecatbutt")
        all_pass(g)
        assert g.pending["kind"] == "pick_player"
        g.respond(first, {"player": other})
        assert g.players[other].blind
        real_ids = {c.id for c in g.players[other].hand}
        real_types = {c.type for c in g.players[other].hand}
        blind_hand = g.view(other)["you"]["hand"]
        assert blind_hand == [
            {"id": f"blind.{i}", "type": "hidden", "variant": 0, "blind_index": i}
            for i in range(len(g.players[other].hand))
        ]
        assert all(c["id"] not in real_ids and c["type"] not in real_types for c in blind_hand)

    def test_blind_random_play_and_cure(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        g.players[other].blind = True
        force_turn(g, other)
        assert cur(g).blind
        g.draw(other)  # rút thành công -> khỏi mù
        assert not g.players[other].blind

    def test_mark_reveals_one_card(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "mark")
        play_type(g, first, "mark")
        all_pass(g)
        g.respond(first, {"player": other})
        marked_id = g.players[other].marked_id
        assert marked_id in hand_ids(g, other)
        v = g.view(other)
        assert v["players"][g.order.index(other)]["marked"]["id"] == marked_id

    def test_mark_clears_when_left_hand(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        stolen = g.players[other].hand[0]
        g.players[other].marked_id = stolen.id
        g.stash = []
        g._steal_pick(cur(g), other)  # kẻ trộm chọn úp lá bị lấy
        pos = g.players[other].hand.index(stolen)
        g.respond(cur(g).name, {"position": pos})
        assert g.players[other].marked_id is None

    def test_illtake_intercepts_next_draw(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "illtakethat")
        play_type(g, first, "illtakethat")  # không nope được nên hỏi mục tiêu ngay
        g.respond(first, {"player": other})
        assert g.players[other].illtake_by == first
        put_top_safe(g, "skip")
        g.draw(first)  # first rút lá an toàn để hết lượt
        assert cur(g).name == other
        put_top_safe(g, "seethefuture3x")
        g.draw(other)  # other rút — lá bị giật
        assert find_hand(g, first, "seethefuture3x") is not None
        assert cur(g).name == first  # other kết thúc lượt bình thường

    def test_favor_transfer(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        give(g, first, "favor")
        play_type(g, first, "favor")
        all_pass(g)
        g.respond(first, {"player": other})
        assert g.pending["owner"] == other
        cid = hand_ids(g, other)[0]
        before = len(g.players[other].hand)
        g.respond(other, {"card_id": cid})
        assert len(g.players[other].hand) == before - 1

    def test_potluck_to_top_of_deck(self):
        g = make_game(3)
        first = cur(g).name
        others = [n for n in g.order if n != first]
        for o in others:
            give(g, o, "skip")
        give(g, first, "potluck")
        play_type(g, first, "potluck")
        all_pass(g)
        # mỗi người khác (theo thứ tự chain) lần lượt pick_card
        for _ in range(len(others)):
            owner = g.pending["owner"]
            g.respond(owner, {"card_id": hand_ids(g, owner)[-1]})
        assert g.deck.peek(1)[0].type == "skip"  # lá cuối đặt lên đỉnh

    def test_reverse_two_players_like_skip(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "reverse")
        act(g, first, "reverse")
        assert cur(g).name != first


# ---------- anytime ----------


class TestAnytime:
    def test_shufflenow_out_of_turn(self):
        g = make_game(3)
        waiter = g.order[(g.turn_index + 1) % 3]
        give(g, waiter, "shufflenow")
        n = g.deck.size()
        g.play_now(waiter, find_hand(g, waiter, "shufflenow").id)
        if g.nope is not None:  # window mở với người khác alive
            all_pass(g)
        assert g.deck.size() == n
        assert cur(g).name != waiter  # không ăn lượt của ai

    def test_feedthedead_revival(self):
        g = make_game(3)
        dead = g.order[2]
        g.players[dead].alive = False
        giver = g.order[1]
        actor = cur(g).name
        give(g, giver, "favor")  # thẻ để dâng
        give(g, actor, "feedthedead")
        g.play_now(actor, find_hand(g, actor, "feedthedead").id)
        if g.nope is not None:
            all_pass(g)
        assert g.pending["kind"] == "pick_player"
        g.respond(actor, {"player": dead})
        # giver phải dâng thẻ
        assert g.pending["owner"] == giver
        g.respond(giver, {"card_id": hand_ids(g, giver)[-1]})
        assert g.players[dead].alive
        assert len(g.players[dead].hand) >= 1


# ---------- playmat: godcat/devilcat/armageddon ----------


class TestPlaymat:
    def test_devilcat_goes_to_playmat(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "devilcat")
        play_type(g, first, "devilcat")
        assert any(e["card"]["type"] == "devilcat" for e in g.playmat)

    def test_armageddon_requires_kitten_on_mat(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "armageddon")
        with pytest.raises(GameError):
            play_type(g, first, "armageddon")

    def test_godcat_as_any_card(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "godcat")
        act(g, first, "godcat", as_type="shuffle")
        assert any(e["card"]["type"] == "godcat" for e in g.playmat)

    def test_godcat_banned_targets(self):
        from server.engine.cards import GODCAT_BANNED
        for banned in ("nope", "explodingkitten", "godcat"):
            assert banned in GODCAT_BANNED

    def test_armageddon_runs_all_alive(self):
        g = make_game(3)
        first = cur(g).name
        other = g.order[1]
        give(g, first, "devilcat")
        play_type(g, first, "devilcat")  # không nope được
        give(g, first, "godcat")
        act(g, first, "godcat", as_type="skip")
        force_turn(g, first)
        give(g, first, "armageddon")
        play_type(g, first, "armageddon")
        all_pass(g)
        g.respond(first, {"player": other})
        g.respond(other, {"value": True})
        # cả hai lá rời playmat để chia úp, Devilcat quay lại, Godcat vào tay một người
        assert sum(1 for e in g.playmat if e["card"]["type"] == "devilcat") == 1
        assert any(find_hand(g, name, "godcat") is not None for name in (first, other))
        assert g.pending is None


# ---------- barking / clone / misc ----------


class TestMisc:
    def test_barking_faces_down_when_alone(self):
        g = make_game(3)
        first = cur(g).name
        give(g, first, "barkingkitten")
        play_type(g, first, "barkingkitten")
        assert any(c.type == "barkingkitten" for c in cur(g).faceup)
        assert g.phase == "playing"

    def test_barking_pair_forces_defuse_or_death(self):
        g = make_game(3)
        first, other = cur(g).name, g.order[1]
        give(g, first, "barkingkitten")
        give(g, other, "barkingkitten", 1)
        has_defuse = find_hand(g, other, "defuse") is not None
        play_type(g, first, "barkingkitten")
        if g.pending:  # cả đôi ở tay actor: chọn mục tiêu
            g.respond(first, {"player": other})
        if has_defuse:
            assert g.players[other].alive
        else:
            assert not g.players[other].alive

    def test_clone_mimics_beneath(self):
        from server.engine.cards import Card
        g = make_game(2)
        first = cur(g).name
        give(g, first, "clone")
        shuf = Card(id="shuffle.9.9", type="shuffle", variant=9)
        g.grave.append(shuf)  # beneath = shuffle
        act(g, first, "clone")
        assert any("Clone hóa thành Shuffle" in m for m in g.log)
        assert any("Deck được xáo." in m for m in g.log)

    def test_graverobber_needs_dead(self):
        g = make_game(2)
        first = cur(g).name
        give(g, first, "graverobber")
        with pytest.raises(GameError):
            play_type(g, first, "graverobber")

    def test_towerofpower_returns_to_deck(self):
        g = make_game(2)
        first = cur(g).name
        stash_before = len(g.stash)
        give(g, first, "towerofpower")
        act(g, first, "towerofpower")
        assert g.tower_wearer == first
        assert len(g.stash) == stash_before  # stash ở yên trong crown, không vào tay
        assert any(c.type == "towerofpower" for c in g.deck.cards)

    def test_view_shape(self):
        g = make_game(3)
        me = g.order[0]
        v = g.view(me)
        for key in ("phase", "you", "players", "deck_count", "stash_count", "grave_top",
                    "revealed", "playmat", "turn", "pending", "log"):
            assert key in v
        assert v["you"]["name"] == me
        assert len(v["players"]) == 3

    def test_error_preserves_pending(self):
        g = make_game(2)
        first = cur(g).name
        put_top_safe(g, "explodingkitten")
        g.draw(first)
        other = g.order[1]
        snap_owner = g.pending["owner"]
        with pytest.raises(GameError):  # sai owner -> lỗi, pending giữ nguyên
            g.respond(other, {"index": 0})
        assert g.pending["owner"] == snap_owner

    def test_meta_has_45_types(self):
        assert len(CARD_META) >= 45
        assert CARD_META["feralcat"]["wild_cat"] is True


class TestLogPrivacy:
    def test_draw_log_is_private(self):
        g = make_game(2)
        first, other = cur(g).name, g.order[1]
        g.players[first].log_checked = True
        g._say(f"Bạn rút Attack", private=first)
        g._say("Một sự kiện công khai")
        view_other = g.view(other)["log"]
        view_first = g.view(first)["log"]
        # người khác không thấy dòng rút riêng tư
        assert not any("Bạn rút Attack" in m for m in view_other)
        # người rút thấy nó
        assert any("Bạn rút Attack" in m for m in view_first)
        # cả hai cùng thấy dòng công khai
        assert any("công khai" in m for m in view_other)
        assert any("công khai" in m for m in view_first)
