# Exploding Kitty Web — Thiết kế

Ngày: 2026-08-25 · Trạng thái: chờ duyệt

## 1. Tổng quan

Web multiplayer cho game Exploding Kittens: backend FastAPI (engine event-driven viết lại trong `server/engine/`, tái sử dụng luật từ `game_core/` — bản console giữ nguyên), frontend React + Vite giao tiếp qua WebSocket. Hỗ trợ nhiều phòng song song, mỗi phòng 2–9 người, join bằng room code, reconnect bằng tên.

**Không làm:** chat, tài khoản/đăng nhập, lưu lịch sử ván, AI bot, mobile app.

## 2. Kiến trúc

```
┌─────────────┐  WebSocket /ws/{code}?name=   ┌──────────────────────┐
│  React/Vite │◄─────────────────────────────►│ FastAPI              │
│  web/dist   │  REST: /api/rooms, /api/cards │  ├─ rooms.py (Room×N)│
└─────────────┘                               │  └─ engine/          │
       ▲                                      │      game.py (state  │
       └── static ảnh: /static/cards/*        │      machine thuần)  │
                                              │      cards.py, deck.py, player.py
resources/cards/*/*.jpg ──mount──┐            └──────────────────────┘
```

- Engine **thuần Python đồng bộ, không biết gì về HTTP/WS** → test pytest chạy không cần server. `Room` bọc engine và dịch lệnh WS thành lời gọi engine.
- Mọi biến đổi state → Room đẩy snapshot **lọc theo từng người xem** (tay mình đầy đủ; tay người khác chỉ số lượng).
- Dev: Vite dev server (5173) proxy `/api`, `/ws`, `/static` → FastAPI (8000). Prod: `npm run build` → FastAPI mount `web/dist`.

## 3. Backend

### 3.1 Module (`server/`)

| File | Nội dung |
|---|---|
| `main.py` | App FastAPI: REST, WS endpoint, mount static |
| `rooms.py` | `Rooms`: dict code(4 chữ cái) → `Room`; tạo/join/reconnect; broadcast |
| `schemas.py` | Pydantic models cho message WS |
| `engine/game.py` | `Game`: state machine lượt chơi, xử lý lệnh |
| `engine/cards.py` | Registry 44 loại thẻ: class + hiệu ứng |
| `engine/deck.py` | Deck: draw top/bottom, insert, shuffle, grave |
| `engine/player.py` | Player: hand, alive |

### 3.2 Trạng thái phòng

```
phase: lobby | playing | ended
playing sub-state: awaiting_action | awaiting_nope | awaiting_response
turn: {current_index, direction (+1/-1), turns_left}
```

### 3.3 Luật ván chơi

- **Chia bài (đúng luật chính thức, xây deck động theo số người N):**
  1. Pool thẻ thường (không EK/Defuse) xáo → mỗi người rút 4.
  2. Mỗi người nhận 1 Defuse; Defuse thừa (nếu có) về đáy deck.
  3. Chèn N−1 quả EK vào deck, xáo lại.
- Thành phần pool theo `resources/desk/web.json` (file mới, chỉnh sửa được; `original.json` giữ nguyên vì con số 20 bom/6 defuse trong đó không chơi được).
- **Lượt:** `turns_left` mặc định 1; mỗi lần rút thẻ (bất kể từ đâu) trừ 1; về 0 → chuyển người theo `direction`. `reverse` đảo chiều (2 người còn lại → như Skip). Thẻ attack/skip/personalattack… đánh dấu `skip_draw` để kết thúc lượt không rút.
- **Rút phải xử lý theo thứ tự ưu tiên:** Defuse (chèn lại vị trí bất kỳ) → Streaking Kitten (hỏi giữ EK trên tay?) → Zombie Kitten / Godcat (sống sót, bỏ tay bài; Godcat giữ lại chính nó) → chết. Thẻ đặc biệt khi rút: `barkingkitten` (lật + chèn lại), `shufflenow` (xáo rồi rút lại, guard tối đa 10 vòng), `alter3xnow` (hiệu ứng chạy ngay rồi kết thúc lượt).
- **Chết:** toàn bộ tay bài xuống grave. Còn đúng 1 người sống → `ended`, công bố winner.
- **Timeout:** 90 giây không hành động khi tới lượt → tự rút (tránh kẹt ván). Pending response không timeout (quyết định chèn bom không nên bị bỏ).

### 3.4 Cửa sổ Nope (5 giây)

- Áp dụng cho **thẻ hành động chủ động**. Không nope được: EK, Defuse, Nope, các thẻ `*now` (kích hoạt khi rút).
- Timer 5s (asyncio task). Người chơi bấm **Nope** (đẩy 1 Nope lên chồng, đếm lệch) hoặc **Pass**. Khi tất cả người sống khác đã Pass/Nope → giải quyết sớm.
- Net-noped: thẻ hành động + toàn bộ Nope dùng → grave; hiệu ứng không chạy (lượt diễn ra bình thường, vẫn phải rút để hết lượt).

### 3.5 Điểm quyết định (`pending`)

Engine dừng tại điểm cần lựa chọn, đặt `pending = {kind, data}`:

| kind | Dùng cho | Client gửi `respond` |
|---|---|---|
| `pick_index` | Chèn bom vào vị trí 0..size | `{index}` |
| `pick_player` | Chọn mục tiêu (favor, steal…) | `{player}` |
| `pick_card` | Chọn thẻ từ nguồn chỉ định | `{source: "own_hand"\|"target_hand"\|"grave", card_id}` |
| `reorder` | alter3x/5x/now, sharethefuture | `{order: [card_id…]}` |
| `yes_no` | Streaking Kitten giữ bom? | `{value: bool}` |

Chuỗi quyết định nhiều bước (ví dụ Favor: chọn người → người đó chọn thẻ) = các `pending` nối tiếp nhau trong handler.

## 4. Giao thức WS

Kết nối: `GET /ws/{code}?name=X` — tên đã tồn tại trong phòng ⇒ reattach (reconnect). REST phụ trợ: `POST /api/rooms {name}` → `{code}`; `GET /api/cards` → catalog ảnh thẻ.

Client → Server:
```jsonc
{type:"start_game"}
{type:"play_card", card_id}
{type:"draw"}                    // rút để kết thúc lượt
{type:"respond", ...}            // giải pending, shape theo kind
{type:"nope"} / {type:"pass"}    // trong cửa sổ nope
```

Server → Client:
```jsonc
{type:"state", view:{
  phase, you:{name, alive, hand:[{id,type,variant}]},
  players:[{name, alive, count, is_turn}],
  deck_count, grave_top:[…10], revealed:[…],        // revealthefuture/swaptopandbottom
  turn:{direction, turns_left},
  pending:{kind,…}|null, nope_window:{ends_ms, stacked}|null,
  log:[…30 dòng cuối], winner|null}}
{type:"error", message}
```

Lỗi (sai lượt, thẻ không hợp lệ…) trả `{type:"error"}` và state không đổi.

## 5. Bảng 44 loại thẻ

### Nhóm A — luật chính thức, làm đúng luật

| Loại | Hiệu ứng |
|---|---|
| `explodingkitten` | Bom. Không cứu được → chết. |
| `defuse` | Khi rút bom: bỏ Defuse, chèn bom lại deck vị trí bất kỳ. |
| `skip` / `superskip` | Kết thúc lượt ngay, không rút. |
| `shuffle` | Xáo deck. |
| `attack2x` | Kết thúc lượt không rút; người kế tiếp +2 lượt. |
| `targetattack2x` | Chọn 1 người bất kỳ: họ +2 lượt; mình không rút. |
| `favor` | Chọn 1 người → họ đưa mình 1 thẻ tùy chọn. |
| `nope` | Hủy action vừa chơi (double-nope hủy lại). |
| `seethefuture3x` / `seethefuture5x` | Xem riêng 3 / 5 thẻ trên cùng. |
| `revealthefuture3x` | Lật 3 thẻ trên cùng cho cả bàn xem. |
| `sharethefuture3x` | Xem 3 thẻ trên cùng, lấy 1 về tay, còn lại giữ nguyên thứ tự. |
| `alter3x` / `alter5x` | Sắp xếp lại 3 / 5 thẻ trên cùng tùy ý. |
| `alter3xnow` | Khi rút phải: sắp xếp 3 thẻ trên cùng ngay, không vào tay; hết lượt. |
| `reverse` | Đảo chiều lượt; còn 2 người → như Skip. |
| `drawfromthebottom` | Rút từ đáy deck (vẫn tính lượt rút). |
| `streakingkitten` | Khi rút bom: có thể giữ bom trên tay, bỏ Streaking. |
| `zombiekitten` | Khi nổ đang giữ nó: sống, bỏ toàn bộ tay bài. |
| `implodingkitten` | Như EK nhưng khi Defuse thì đặt lên **đỉnh** deck. |
| `barkingkitten` | Khi rút phải: không nổ, lật cho cả bàn, chèn lại deck vị trí bất kỳ. |
| `cat` | 2 lá cùng variant → đánh cắp 1 thẻ ngẫu nhiên từ người tùy chọn. |
| `potluck` | Từng người khác đưa mình 1 thẻ tùy chọn. |
| `illtakethat` | Chọn 1 người, xem tay họ, lấy 1 thẻ tùy ý. |
| `garbagecollection` | Từng người khác bỏ 1 thẻ tùy chọn xuống grave (hết thẻ thì bỏ qua). |
| `personalattack3x` | Không rút; mỗi người khác rút ngay 1 thẻ. |
| `raisingheck` | Mỗi người khác rút ngay 1 thẻ; chơi chồng nhiều lá = ép rút nhiều vòng. *(đơn giản hóa)* |
| `swaptopandbottom` | Hoán đổi thẻ trên cùng ↔ dưới cùng, cả bàn thấy 2 thẻ đó. |
| `bury` | Chọn 1 thẻ từ grave đặt lên đỉnh deck (cả bàn thấy). |
| `graverobber` | Di chuyển 1 thẻ từ grave về tay. |
| `clone` | Tạo bản sao variant giống hệt 1 thẻ grave vào tay (gốc ở lại grave). |

### Nhóm B — tự định nghĩa (repo không có mô tả; ⚠️ = dễ đổi sau khi chơi thử)

| Loại | Hiệu ứng giả định |
|---|---|
| `digdeeper` ⚠️ | Rút từ đáy deck (trùng ý `drawfromthebottom`). |
| `shufflenow` ⚠️ | Khi rút phải: xáo deck rồi rút lại thẻ khác. |
| `clairvoyance` ⚠️ | Xem riêng 2 thẻ trên cùng. |
| `curseofthecatbutt` ⚠️ | Chọn 1 người: thẻ kế tiếp họ rút bị lật cho cả bàn trước khi vào tay. |
| `mark` ⚠️ | Chọn 1 người: lần rút kế tiếp họ phải rút 2 thẻ liên tiếp. |
| `devilcat` ⚠️ | Đánh cắp 1 thẻ ngẫu nhiên từ **từng** người khác. |
| `godcat` ⚠️ | Khi nổ đang giữ nó: sống, bỏ mọi thẻ khác, **giữ lại Godcat**. |
| `catomicbomb` ⚠️ | Gộp tay bài mọi người sống, xáo, chia đều lại. |
| `towerofpower` ⚠️ | Rút ngay 1 thẻ mà không kết thúc lượt. |
| `feedthedead` ⚠️ | Bỏ 1 thẻ tùy chọn → hồi sinh 1 người đã chết với 0 thẻ. |
| `attackofthedead` ⚠️ | Mọi người đã chết hồi sinh với 0 thẻ. |
| `armageddon` ⚠️ | Mọi người sống (kể cả mình) rút ngay 1 thẻ. |

## 6. Frontend (`web/`, React + Vite + JS thuần)

```
src/Home.jsx     # tên + tạo phòng / join code
src/Room.jsx     # bàn chơi, 1 nơi nhận state WS
src/components: Hand.jsx, Opponents.jsx, Piles.jsx (deck/grave/reveal),
                PendingModal.jsx (5 kind), NopeBar.jsx, Log.jsx, CardImage.jsx
src/api.js       # WS connect + auto-reconnect (backoff, rejoin theo tên)
index.css        # 1 file, theme tối kiểu bàn xanh
```

- Ảnh thẻ: `/static/cards/{type}/{variant}.jpg`, thiếu ảnh → placeholder emoji. Catalog từ `/api/cards`.
- Modal tương ứng 5 `pending.kind`; trong cửa sổ Nope hiện thanh đếm ngược + nút Nope/Pass cho người không phải actor.
- Winner banner khi `phase=ended`; nút "Ván mới" (reset phòng về lobby, giữ người).

## 7. Testing

pytest cho engine (không cần server): chia bài đúng công thức N người; mỗi loại thẻ nhóm A có ≥1 test luồng cơ bản; nhóm B test happy-path theo định nghĩa; nope (hủy + double-nope); reverse 2 người; chết → grave; thắng; `*now` khi rút. Rooms: tạo/join/reconnect. Target ~90% coverage các nhánh engine.

## 8. Chạy

```bash
# dev
uvicorn server.main:app --reload --port 8000   # terminal 1
cd web && npm install && npm run dev           # terminal 2 (proxy về 8000)

# prod
cd web && npm run build
uvicorn server.main:app --port 8000            # serve luôn web/dist
```

Không phải git repo → không commit được; nếu anh init git thì tôi commit spec + code theo từng bước.
