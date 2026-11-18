# Đối chiếu hiệu ứng bài: cards_desc vs. engine

Ngày: 2026-08-28 · Nguồn luật: `resources/cards_desc/*.txt` (40 lá) · Code: `server/engine/{cards,game,deck,player}.py`

## Tổng quan

| Kết quả | Số lá | Danh sách |
|---|---|---|
| ✅ KHỚP | 27 | alter3x, alter3xnow, alter5x, attack2x, attackofthedead, barkingkitten, bury, clone, curseofthecatbutt, defuse, drawfromthebottom, explodingkitten, favor, feralcat, garbagecollection, graverobber, implodingkitten, mark, potluck, raisingheck, revealthefuture3x, seethefuture3x, seethefuture5x, sharethefuture3x, shufflenow, shuffle, skip |
| ⚠️ SAI LỆCH nhỏ | 9 | cat, catomicbomb, clairvoyance, digdeeper, feedthedead, godcat, nope, personalattack3x, reverse |
| ❌ SAI LỆCH nặng | 4 | armageddon, devilcat, illtakethat, streakingkitten |

> Một số lá "KHỚP" có ghi chú lựa chọn thiết kế (xem mục C).

---

## A. Sai lệch nghiêm trọng (cần sửa)

### A1. armageddon — cơ chế hoàn toàn khác mô tả
- **Mô tả:** cần **CẢ Godcat VÀ Devilcat** trên playmat; người chơi lấy 2 lá đó, xáo, đặt úp 1 lá trước mình + 1 lá trước người khác; người đó chọn giữ/đổi; ai kết thúc với Devilcat thì Defuse hoặc nổ; Godcat vào tay người thắng; Devilcat về playmat; hết lượt không rút.
- **Code:** `_do_armageddon` ([game.py:994-1021](../server/engine/game.py#L994-L1021)) — mọi người lần lượt rút 1 lá từ deck, ai rút trúng devilcat thì nổ. Không hề có cơ chế "xáo 2 lá + úp + chọn giữ/đổi".
- **Thêm:** điều kiện kích hoạt sai — [game.py:367-369](../server/engine/game.py#L367-L369) chỉ yêu cầu `godcat` **HOẶC** `devilcat` trên playmat thay vì cả hai.

### A2. devilcat — lệch do phụ thuộc armageddon
- Bản thân lá (đánh ra playmat, không Nope) đúng, nhưng trong armageddon code, nhánh `card.type == "devilcat"` ([game.py:1005](../server/engine/game.py#L1005)) gần như **dead code** vì devilcat không nằm trong deck pool.

### A3. graverobber — chỉ lấy 1 lá thay vì toàn bộ tay người chết
- **Mô tả:** **ALL** bài trong tay người chết đặt vào draw pile rồi xáo.
- **Code:** [game.py:916-922](../server/engine/game.py#L916-L922) — mỗi người chết chỉ **chọn MỘT lá** cho vào deck.

### A4. illtakethat — bị Nope, trái mô tả
- **Mô tả:** "I'll Take That **CANNOT be blocked** by a Nope."
- **Code:** `nopeable: True` ở [cards.py:76-77](../server/engine/cards.py#L76-L77). Phần còn lại khớp: chặn lá rút tiếp theo của nạn nhân, bom chuyển cho người đặt, không chặn imploding ([game.py:608-623](../server/engine/game.py#L608-L623)).

### A5. streakingkitten — thiếu/sai 3 quy tắc
1. **Setup thiếu bomb:** [game.py:257](../server/engine/game.py#L257) luôn chia N-1 EK; mô tả yêu cầu **thêm 1 EK (tổng = số người chơi)** khi streaking có trong deck.
2. **Cứu bom sai:** code bắt **bỏ streaking vào grave** mới được giữ EK (`_streaking_keep`, [game.py:739-745](../server/engine/game.py#L739-L745)); mô tả cho **giữ EK miễn là streaking còn trên tay**, không hy sinh streaking.
3. **Thiếu rule "streaking rời tay → EK nổ":** không có xử lý khi streaking bị trộm/combo/favor/garbage — EK kẹt trong tay mãi an toàn.

---

## B. Sai lệch nhỏ

### B1. reverse — bị attack mà reverse thì mất CẢ 2 lượt
[game.py:825](../server/engine/game.py#L825) dùng `_end_turn(force=True)` → xóa toàn bộ lượt dồn. Mô tả (giống skip): "chỉ hết 1 trong 2 lượt". Skip dùng `_end_turn(drew=False)` không force — đúng; reverse phải làm giống vậy.

### B2. personalattack3x — chơi lặp thiếu 1 lượt
[game.py:813](../server/engine/game.py#L813): `turns_left += 2`. Lượt thường (turns_left=1) → 3 là đúng; nhưng mô tả là "phần còn lại **+3**", nên từ lần thứ hai trở đi thiếu 1 lượt. Cân nhắc `turns_left += 3`.

### B3. godcat — không dùng được ngoài lượt (trừ cứu bom)
Mô tả cho phép Godcat hóa thành bất kỳ lá nào **kể cả ngoài lượt** (ví dụ khi bị trộm EK). Code cấm godcat trong `play_now` ([game.py:497-498](../server/engine/game.py#L497-L498)) — chỉ tự kích hoạt khi cứu bom. Hóa thành lá nopeable trong lượt thì đúng (bị Nope theo lá hóa thân).

### B4. cat combo — trộm "ngẫu nhiên" thực ra là chọn theo vị trí
Mô tả: pair = trộm **ngẫu nhiên**. Code cho kẻ trộm biết số lá tay nạn nhân và **tự chọn vị trí** ([game.py:129-131](../server/engine/game.py#L129-L131)) — biết nhiều hơn luật cho phép. Cân nhắc random server-side hoặc chọn index mù không hiển thị số lá... (thực tế chỉ cần random chọn).

### B5. catomicbomb — lôi cả Imploding Kitten lên đỉnh
Mô tả: gom **Exploding** Kittens, "leave Imploding Kitten". Code dùng `BOMBS` gồm cả imploding ([game.py:925-932](../server/engine/game.py#L925-L932)).

### B6. clairvoyance — xem vị trí bom vĩnh viễn thay vì 1 lần
Mô tả: chơi khi ai defuse; được thấy vị trí chèn **một lần**. Code: `bomb_watchers` cho theo dõi vị trí bom **đến hết ván** ([game.py:797-799](../server/engine/game.py#L797-L799)); không gating "chỉ chơi sau khi ai defuse". (Phần người chết cũng chơi được là đúng luật.)

### B7. digdeeper — giữ bom không nổ; đỉnh/đáy deck cần kiểm tra lại
- Rút lá đỉnh, chọn **giữ**: nếu là bom thì phải nổ (Defuse/chết), nhưng code cho vào tay luôn ([game.py:1149-1154](../server/engine/game.py#L1149-L1154)).
- Chọn **bỏ**: code `append` vào cuối `deck.cards` ([game.py:1156](../server/engine/game.py#L1156)) — cần xác nhận quy ước đỉnh/đáy với `deck.py` (potluck dùng `insert(card, 0)`), nếu cuối list là đáy thì lá "trả về đỉnh" đang bị đưa xuống đáy.

### B8. feedthedead — tự hồi sinh người chết
Code đặt `target.alive = True` ([game.py:1109-1111](../server/engine/game.py#L1109-L1111)); mô tả chỉ nói "đưa bài cho người chết", không nói hồi sinh. Nếu đây là chủ ý đồ án thì bỏ qua.

### B9. nope — người chết không được Nope
`stack_nope` yêu cầu `p.alive` ([game.py:532](../server/engine/game.py#L532)); luật Zombie Kittens cho phép người chết Nope. Tùy quyết định luật nhà.

---

## C. Ghi chú thiết kế trên các lá KHỚP

- **nope**: không cho actor tự Nope lá mình ([game.py:529](../server/engine/game.py#L529)) — hợp lý.
- **barkingkitten**: file mô tả có phần Notes mâu thuẫn (luật mới "đổi một nửa bài"), code theo phần Mechanics chính — coi như khớp.
- **garbagecollection**: chèn vào vị trí ngẫu nhiên rồi còn xáo cả deck — hơi thừa so với mô tả nhưng kết quả tương đương.
- **explodingkitten**: code giữ lại tay người chết thay vì tước — phục vụ graverobber/attackofthedead theo luật Zombie, hợp lý.
- **clone**: hiệu ứng lá dưới chạy không qua cửa sổ Nope mới; Clone bản thân đã nopeable nên chấp nhận.
- **feralcat**: thiếu ngoại lệ "đánh đơn như Super Skip/Personal Attack khi deck có chúng" — deck hiện không có 2 lá đó nên không ảnh hưởng.
- **sharethefuture3x**: người kế xem sau khi reorder — về kết quả tương đương mô tả.
- **peek khi deck < n**: trả những gì có, không crash — chấp nhận.

---

## Đề xuất thứ tự sửa

1. **armageddon + devilcat** — viết lại `_do_armageddon` theo đúng cơ chế 2 lá úp + chọn giữ/đổi; sửa điều kiện kích hoạt thành cả hai lá.
2. **streakingkitten** — setup +1 EK; giữ bom cần streaking trên tay (không bỏ); thêm hook "streaking rời tay → EK nổ" vào `_leave_hand`/steal paths.
3. **graverobber** — đổi `_chain_into_deck(dead)` thành lấy **toàn bộ** tay người chết.
4. **illtakethat** — `nopeable: False`.
5. **reverse** — bỏ `force=True`.
6. **personalattack3x** — `+= 3`.
7. Các lệch nhỏ còn lại (godcat anytime, cat combo random, catomicbomb loại imploding, clairvoyance 1 lần, digdeeper bom nổ + đỉnh/đáy, feedthedead hồi sinh, nope cho người chết) — quyết theo luật nhà rồi sửa.
</content>
</invoke>