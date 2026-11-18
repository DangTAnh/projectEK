"""FastAPI entrypoint: REST phòng/thẻ, WebSocket ván, static ảnh thẻ."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import CARD_META, GameError
from .engine.deck import available_desks
from .rooms import (
    AUTH_CLOSE_CODE,
    MANAGER,
    ROOM_UNAVAILABLE_CLOSE_CODE,
    UNKNOWN_ROOM_CLOSE_CODE,
    Room,
    RoomFullError,
    SessionError,
)

CARDS_DIR = Path(__file__).resolve().parents[1] / "resources" / "cards"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield


app = FastAPI(title="Exploding Kitty", lifespan=_lifespan)


def _card_image(ctype: str) -> str:
    """Trả URL ảnh JPG thực sự tồn tại, thay vì mặc định sai extension."""
    try:
        files = (CARDS_DIR / ctype).glob("*.jpg")
        ordered = sorted(
            files,
            key=lambda p: (0, int(p.stem)) if p.stem.isdigit() else (1, p.stem),
        )
        if ordered:
            return f"/static/cards/{ctype}/{ordered[0].name}"
    except OSError:
        pass
    return f"/static/cards/{ctype}/0.jpg"


async def _send_error(ws: WebSocket, message: str) -> None:
    try:
        await ws.send_json({"type": "error", "message": message})
    except (RuntimeError, WebSocketDisconnect):
        pass


async def _close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except (RuntimeError, WebSocketDisconnect):
        pass


# ---------- REST ----------

@app.post("/api/rooms")
async def create_room() -> JSONResponse:
    try:
        return JSONResponse({"code": MANAGER.create()})
    except GameError as e:
        return JSONResponse({"message": str(e)}, status_code=429)


@app.get("/api/desks")
async def list_desks() -> list[str]:
    return available_desks()


@app.get("/api/rooms")
async def list_rooms() -> list[dict]:
    return [
        {
            "code": r.code,
            "player_count": len(r.conns),
            "started": r.game is not None,
            "phase": r.game.phase if r.game else "lobby",
        }
        for r in MANAGER.active_rooms()
    ]


@app.get("/api/cards")
async def list_cards() -> dict:
    return {
        ctype: {**meta, "image": _card_image(ctype)}
        for ctype, meta in CARD_META.items()
    }


app.mount("/static/cards", StaticFiles(directory=CARDS_DIR), name="cards")


# ---------- WebSocket ----------

@app.websocket("/ws/{code}")
async def ws_room(ws: WebSocket, code: str, name: str, token: str | None = None) -> None:
    room = MANAGER.get(code)
    await ws.accept()
    if room is None:
        await _send_error(ws, "Phòng không tồn tại")
        await _close(ws, UNKNOWN_ROOM_CLOSE_CODE)
        return
    clean = (name or "").strip()
    if not clean or len(clean) > 64:
        await _send_error(ws, "Tên không hợp lệ")
        await _close(ws, AUTH_CLOSE_CODE)
        return
    if room.game is not None and clean not in room.game.names:
        await _send_error(ws, "Ván đã bắt đầu, không vào được nữa")
        await _close(ws, ROOM_UNAVAILABLE_CLOSE_CODE)
        return
    if len(set(room.conns) | {clean}) > 9:
        await _send_error(ws, "Phòng đã đầy (tối đa 9)")
        await _close(ws, ROOM_UNAVAILABLE_CLOSE_CODE)
        return

    try:
        session = room.register(clean, ws, token)
    except RoomFullError as e:
        await _send_error(ws, str(e))
        await _close(ws, ROOM_UNAVAILABLE_CLOSE_CODE)
        return
    except SessionError as e:
        await _send_error(ws, str(e))
        await _close(ws, AUTH_CLOSE_CODE)
        return
    try:
        await room.push_all()
        while True:
            try:
                msg = await ws.receive_json()
            except WebSocketDisconnect:
                break
            except ValueError:
                await _send_error(ws, "Gói tin JSON không hợp lệ")
                continue
            except RuntimeError:
                break
            try:
                await room.handle(clean, msg, ws, session)
            except SessionError as e:
                await _send_error(ws, str(e))
                await _close(ws, AUTH_CLOSE_CODE)
                return
            except GameError as e:
                await _send_error(ws, str(e))
            except (WebSocketDisconnect, RuntimeError):
                break
    finally:
        # rời phòng thì báo cho người còn lại biết roster lobby đã đổi.
        # shield: socket vừa rớt có thể bị huỷ scope ngay (TestClient/tắt server);
        # để cancel xuyên qua sẽ làm broadcast dở dang, người còn lại mất state.
        if room.leave(clean, ws):
            try:
                await asyncio.shield(room.push_all())
            except Exception:
                pass


def run(host: str = "0.0.0.0", port: int = 8000) -> None:  # pragma: no cover
    import uvicorn
    uvicorn.run("server.main:app", host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run()
