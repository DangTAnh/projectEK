# Exploding Kitty 🐱💥

Web-based **Exploding Kittens** cho nhiều người chơi (2–9). Backend FastAPI + WebSocket, frontend React (Vite), engine game viết thuần Python.

## Cấu trúc

```
server/            FastAPI: REST phòng/thẻ, WebSocket ván, phục vụ ảnh thẻ
  engine/          logic game (game.py, cards.py, deck.py, player.py)
  rooms.py         RoomManager: phòng, vote lobby, timer cửa sổ Nope
  main.py          entrypoint + routes
game_core/         bản engine desktop cũ (CLI, không dùng bởi web)
web/               React frontend (Vite)
  src/Room.jsx     màn chơi chính, WebSocket, animation/cutscene
  src/components/  CardView, PlayerList, PendingPanel, NopeBar
resources/         ảnh thẻ, ảnh nền, mô tả bộ bài
tests/             pytest: engine, server smoke, hồi quy transport/engine
```

## Chạy

### Backend (port 8000)

```bash
uvicorn server.main:app --reload
```

hoặc:

```bash
python -m server.main
```

### Frontend (port mặc định Vite)

```bash
cd web
npm install
npm run dev
```

Vite proxy `/api`, `/static`, `/ws` sang `localhost:8000` (xem [web/vite.config.js](web/vite.config.js)). Mở URL Vite in ra để chơi.

## Test

```bash
pytest
```

- `tests/test_engine.py` — logic ván (luật chơi, luồng, tính điểm).
- `tests/test_server.py` — smoke REST + WebSocket (lobby/start).
- `tests/test_bugfixes.py` — hồi quy transport/engine/contract đã sửa.
- `tests/test_bugfixes_engine.py` — biên engine (attack cộng dồn, Armageddon, clone, quyền riêng tư).
- `tests/test_bugfixes_transport.py` — `Room`/session token + biên WebSocket in-process.

`pytest.ini` đặt `faulthandler_timeout = 60` và thoát khi quá hạn: test treo sẽ dump stack và fail thay vì treo cả suite.

## API chính

| Method | Path | Mô tả |
|--------|------|-------|
| `POST` | `/api/rooms` | Tạo phòng, trả `code` 4 ký tự |
| `GET`  | `/api/rooms` | Danh sách phòng |
| `GET`  | `/api/desks` | Các bộ bài khả dụng |
| `GET`  | `/api/cards` | Metadata thẻ |
| `WS`   | `/ws/{code}?name=X` | Ván chơi: nhận `{type:"state"}` qua `push_all`, gửi action (play/combo/draw/respond/nope/…) |

## Ván chơi qua WebSocket

Client gửi action theo `{action: ...}`, server bắn lại state cho mọi người trong phòng. Các action ở [server/rooms.py](server/rooms.py#L185): `start`, `vote_desk`, `play`, `combo`, `draw`, `respond`, `nope`, `pass_nope`, `play_now`.

State chứa `view.log` — **chỉ 30 dòng cuối** (`self.log[-30:]`). Frontend dò sự kiện (ví dụ cutscene bom nổ) bằng cách track nội dung dòng log, không dò theo index — đừng sửa chỗ này theo độ dài.

## Lưu ý về animation trong log

Mọi animation dựa trên `view.log` (bom nổ, các hiệu ứng card) đều dùng chung cơ chế dò log ở [web/src/Room.jsx](web/src/Room.jsx#L52). Vì server gửi bộ đệm trượt `[-30:]`, dò theo **nội dung dòng cuối đã thấy** (đúng), không theo độ dài `log.length` (sẽ lệch index khi log > 30 dòng và làm animation bỏ lỡ ngẫu nhiên).