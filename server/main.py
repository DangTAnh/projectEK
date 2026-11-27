"""FastAPI entrypoint: REST phòng/thẻ, WebSocket ván, static ảnh thẻ."""

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from functools import lru_cache
import logging
from pathlib import Path
import time

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import CARD_META, GameError
from .engine.cards import GODCAT_BANNED
from .engine.deck import available_desks, desk_catalog
from .rooms import (
    AUTH_CLOSE_CODE,
    MANAGER,
    MAX_PLAYERS,
    ROOM_UNAVAILABLE_CLOSE_CODE,
    UNKNOWN_ROOM_CLOSE_CODE,
    RoomUnavailableError,
    SessionError,
    _is_debug_enabled,
)

logger = logging.getLogger(__name__)

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
CARDS_DIR = RESOURCES_DIR / "cards"
CARDS_DESC_DIR = RESOURCES_DIR / "cards_desc"

CREATE_ROOM_RATE_LIMIT = 60
CREATE_ROOM_RATE_WINDOW = 60.0
_MAX_TRACKED_RATE_KEYS = 2048
_create_room_hits: dict[str, deque[float]] = {}

_CARD_CATEGORIES = {
    "explodingkitten": "bomb",
    "implodingkitten": "bomb",
    "devilcat": "bomb",
    "barkingkitten": "bomb",
    "defuse": "rescue",
    "streakingkitten": "rescue",
    "zombiekitten": "rescue",
    "godcat": "rescue",
    "seethefuture3x": "future",
    "seethefuture5x": "future",
    "revealthefuture3x": "future",
    "sharethefuture3x": "future",
    "alter3x": "future",
    "alter5x": "future",
    "alter3xnow": "future",
    "clairvoyance": "future",
    "cat": "combo",
    "feralcat": "combo",
    "favor": "steal",
    "potluck": "steal",
    "illtakethat": "steal",
    "mark": "steal",
    "curseofthecatbutt": "steal",
    "garbagecollection": "steal",
    "graverobber": "steal",
    "clone": "action",
    "swaptopandbottom": "future",
    "nope": "action",
    "feedthedead": "revive",
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _card_catalog()
    yield


app = FastAPI(title="Exploding Kitty", lifespan=_lifespan)


def _card_variants(ctype: str) -> list[int]:
    try:
        files = (CARDS_DIR / ctype).glob("*.jpg")
        return sorted(int(p.stem) for p in files if p.stem.isdigit())
    except OSError:
        return []


def _card_image(ctype: str, variants: list[int] | None = None) -> str:
    """Trả URL ảnh JPG thực sự tồn tại, thay vì mặc định sai extension."""
    if variants:
        return f"/static/cards/{ctype}/{variants[0]}.jpg"
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


def _card_description(ctype: str) -> str:
    """Đọc mô tả ngắn gọn từ resources/cards_desc/<ctype>.txt (fallback rỗng)."""
    path = CARDS_DESC_DIR / f"{ctype}.txt"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = [line.strip() for line in raw.splitlines()]
    out: list[str] = []
    in_desc = False
    for line in lines:
        low = line.lower()
        if low == "card description":
            in_desc = True
            continue
        if in_desc:
            if low in ("mechanics", "included in", "nope", "now", "notes") or low.startswith('"'):
                if out:
                    break
                continue
            if line:
                out.append(line)
    if out:
        return " ".join(out).strip()
    non_empty = [line for line in lines if line]
    return " ".join(non_empty)[:240].strip()


def _card_category(ctype: str) -> str:
    return _CARD_CATEGORIES.get(ctype, "action")


@lru_cache(maxsize=1)
def _card_catalog() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    for ctype, meta in CARD_META.items():
        variants = _card_variants(ctype)
        catalog[ctype] = {
            **meta,
            "type": ctype,
            "category": _card_category(ctype),
            "image": _card_image(ctype, variants),
            "description": _card_description(ctype),
            "godcat_banned": ctype in GODCAT_BANNED,
            "variants": variants,
        }
    return catalog


def _check_create_rate_limit(client_ip: str, now: float | None = None) -> bool:
    moment = now if now is not None else time.monotonic()
    cutoff = moment - CREATE_ROOM_RATE_WINDOW
    if len(_create_room_hits) >= _MAX_TRACKED_RATE_KEYS:
        stale = [ip for ip, hits in _create_room_hits.items() if not hits or hits[-1] < cutoff]
        for ip in stale:
            _create_room_hits.pop(ip, None)
    bucket = _create_room_hits.setdefault(client_ip, deque())
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= CREATE_ROOM_RATE_LIMIT:
        return False
    bucket.append(moment)
    return True


async def _send_error(ws: WebSocket, message: str, code: str = "GAME_ERROR") -> None:
    try:
        await ws.send_json({"type": "error", "code": code, "message": message})
    except (RuntimeError, WebSocketDisconnect):
        pass


async def _close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except (RuntimeError, WebSocketDisconnect):
        pass


def _debug_disabled_response() -> JSONResponse:
    return JSONResponse(
        {
            "code": "DEBUG_DISABLED",
            "message": "Debug đã tắt (chạy server với EK_DEBUG=1)",
        },
        status_code=403,
    )


# ---------- REST ----------

@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "rooms": len(MANAGER.rooms),
        "debug_enabled": _is_debug_enabled(),
    }


@app.post("/api/rooms")
async def create_room(request: Request) -> JSONResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not _check_create_rate_limit(client_ip):
        logger.warning("Rate-limited room creation from %s", client_ip)
        return JSONResponse(
            {"code": "RATE_LIMITED", "message": "Tạo phòng quá nhanh, hãy thử lại sau"},
            status_code=429,
        )
    try:
        return JSONResponse({"code": MANAGER.create()})
    except GameError as e:
        return JSONResponse({"code": "SERVER_FULL", "message": str(e)}, status_code=429)


@app.get("/api/desks")
async def list_desks() -> list[str]:
    return available_desks()


@app.get("/api/desks/details")
async def list_desk_details() -> list[dict]:
    return desk_catalog()


@app.get("/api/rooms")
async def list_rooms() -> list[dict]:
    return [
        {
            "code": r.code,
            "player_count": len(r.conns),
            "max_players": MAX_PLAYERS,
            "started": r.game is not None,
            "phase": r.game.phase if r.game else "lobby",
        }
        for r in MANAGER.active_rooms()
    ]


@app.get("/api/rooms/{code}")
async def get_room(code: str) -> JSONResponse:
    room = MANAGER.get(code)
    if room is None:
        return JSONResponse(
            {"code": "ROOM_NOT_FOUND", "message": "Phòng không tồn tại"},
            status_code=404,
        )
    return JSONResponse(
        {
            "code": room.code,
            "player_count": len(room.conns),
            "max_players": MAX_PLAYERS,
            "started": room.game is not None,
            "phase": room.game.phase if room.game else "lobby",
        }
    )


@app.get("/api/cards")
async def list_cards() -> dict:
    return _card_catalog()


# ---------- Debug REST (EK_DEBUG=1) ----------

@app.get("/api/debug/rooms")
async def debug_list_rooms() -> JSONResponse:
    if not _is_debug_enabled():
        return _debug_disabled_response()
    return JSONResponse(
        [
            {
                "code": r.code,
                "player_count": len(r.conns),
                "max_players": MAX_PLAYERS,
                "started": r.game is not None,
                "phase": r.game.phase if r.game else "lobby",
                "players": sorted(r.conns),
            }
            for r in MANAGER.active_rooms()
        ]
    )


@app.get("/api/debug/rooms/{code}")
async def debug_inspect_room(code: str) -> JSONResponse:
    if not _is_debug_enabled():
        return _debug_disabled_response()
    room = MANAGER.get(code)
    if room is None:
        return JSONResponse(
            {"code": "ROOM_NOT_FOUND", "message": "Phòng không tồn tại"},
            status_code=404,
        )
    try:
        return JSONResponse(await room.debug_inspect())
    except GameError as e:
        return JSONResponse({"code": "GAME_ERROR", "message": str(e)}, status_code=400)


@app.post("/api/debug/rooms/{code}/action")
async def debug_room_action(code: str, request: Request) -> JSONResponse:
    if not _is_debug_enabled():
        return _debug_disabled_response()
    room = MANAGER.get(code)
    if room is None:
        return JSONResponse(
            {"code": "ROOM_NOT_FOUND", "message": "Phòng không tồn tại"},
            status_code=404,
        )
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"code": "INVALID_JSON", "message": "Gói tin JSON không hợp lệ"},
            status_code=400,
        )
    if not isinstance(body, dict) or not isinstance(body.get("op"), str) or not body["op"]:
        return JSONResponse(
            {"code": "INVALID_ACTION", "message": "Thiếu op"},
            status_code=400,
        )
    try:
        snapshot = await room.debug_exec(body["op"], body)
    except GameError as e:
        return JSONResponse({"code": "GAME_ERROR", "message": str(e)}, status_code=400)
    return JSONResponse(snapshot)


app.mount("/static/cards", StaticFiles(directory=CARDS_DIR), name="cards")


# ---------- WebSocket ----------

@app.websocket("/ws/{code}")
async def ws_room(ws: WebSocket, code: str, name: str = "", token: str | None = None) -> None:
    room = MANAGER.get(code)
    await ws.accept()
    if room is None:
        await _send_error(ws, "Phòng không tồn tại", code="ROOM_NOT_FOUND")
        await _close(ws, UNKNOWN_ROOM_CLOSE_CODE)
        return
    clean = (name or "").strip()
    if not clean or len(clean) > 64:
        await _send_error(ws, "Tên không hợp lệ", code="INVALID_NAME")
        await _close(ws, AUTH_CLOSE_CODE)
        return

    try:
        session = await room.join(clean, ws, token)
    except RoomUnavailableError as e:
        await _send_error(ws, str(e), code=e.code)
        await _close(ws, ROOM_UNAVAILABLE_CLOSE_CODE)
        return
    except SessionError as e:
        await _send_error(ws, str(e), code=e.code)
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
                await _send_error(ws, "Gói tin JSON không hợp lệ", code="INVALID_JSON")
                continue
            except RuntimeError:
                break
            try:
                await room.handle(clean, msg, ws, session)
            except SessionError as e:
                await _send_error(ws, str(e), code=e.code)
                await _close(ws, AUTH_CLOSE_CODE)
                return
            except GameError as e:
                await _send_error(ws, str(e), code=getattr(e, "code", "GAME_ERROR"))
            except (WebSocketDisconnect, RuntimeError):
                break
            if room.conns.get(clean) is not ws:
                break
    finally:
        # rời phòng thì báo cho người còn lại biết roster lobby đã đổi.
        # shield: socket vừa rớt có thể bị huỷ scope ngay (TestClient/tắt server);
        # để cancel xuyên qua sẽ làm broadcast dở dang, người còn lại mất state.
        if room.leave(clean, ws):
            try:
                await asyncio.shield(room.push_all())
            except Exception:
                logger.exception("Failed to broadcast leave for %s in room %s", clean, code)


def run(host: str = "0.0.0.0", port: int = 8000) -> None:  # pragma: no cover
    import uvicorn
    uvicorn.run("server.main:app", host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    run()
