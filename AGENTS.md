# Repository Guidelines

## Project Overview

Exploding Kitty is a browser-based multiplayer Exploding Kittens game for 2–9 players. The live application is a Python/FastAPI backend with synchronous game logic, WebSockets for play, and a React/Vite frontend. Game state is process-local and in memory; there is no database or persistence layer.

## Architecture & Data Flow

1. `web/src/main.jsx` mounts `Home` when there is no `room` query parameter, otherwise `Room`.
2. `Home.jsx` uses relative REST calls to create/list rooms and stores the player name in `sessionStorage`. Room listings expose only `player_count`, not player names.
3. `Room.jsx` opens `/ws/{code}?name=...&token=...`, receives `{type: "state", view: ...}` snapshots, and sends `{action: ...}` messages. It stores the server-issued session token, retries only abnormal closes with a bounded backoff, and stops on terminal close codes.
4. `server/main.py` creates the FastAPI app, exposes room/card REST routes, mounts `resources/cards` at `/static/cards`, validates WebSocket joins, and forwards messages to `Room`.
5. The global `MANAGER` in `server/rooms.py` keeps rooms in memory with pruning and a creation cap. A `Room` owns connections and unguessable session tokens (keyed by name for reconnect), lobby desk votes, the current `Game`, and the five-second Nope timer.
6. `Room.handle()` validates envelopes and sender sessions, serializes mutations with a lock, dispatches actions to the synchronous `server.engine.Game`, and verifies stale sockets. `Game` uses lists/dicts, a continuation (`_ask`/`_cont`) for pending decisions, and `Game.view(name)` to hide private information. After each action, the room resolves or times out Nope and broadcasts a per-player view with timeouts and failure cleanup.
7. `server/engine/deck.py` stores cards as a list whose last element is the top; `resources/desk/*.json` supplies deck pools. The server returns only the last 30 chronological viewer-visible log lines; the frontend detects new animation events by the last seen log content, not by log length/index.

Actions currently handled by `server/rooms.py` include `start`, `vote_desk`, `play`, `combo`, `draw`, `respond`, `nope`, `pass_nope`, and `play_now`. `start` is rejected after a game exists. `debug_give` is disabled unless the server runs with `EK_DEBUG=1`, and there is no frontend debug control.

`game_core/` is the older standalone desktop/CLI engine. It is not imported by the current `server/` application; do not use it as the source of truth for web changes.

## Key Directories

| Path | Purpose |
|---|---|
| `server/` | Current FastAPI REST/WebSocket application. |
| `server/engine/` | Pure synchronous game state machine, cards, deck, and player models. |
| `tests/` | Pytest engine and in-process server/WebSocket tests. |
| `web/src/` | React entrypoint, lobby, room UI, API/WebSocket helpers, and components. |
| `web/src/components/` | Presentational card/player/pending/Nope UI pieces. |
| `web/public/` | Static frontend assets copied by Vite. |
| `resources/desk/` | JSON deck pools loaded by `Deck`. |
| `resources/cards/` | Card images served at `/static/cards`. |
| `resources/cards_desc/` | Human-readable card descriptions used as rules reference. |
| `game_core/` | Legacy desktop CLI implementation; keep separate from the web path. |
| `docs/` | Current audits and historical design material. |
| `tmp_shots/` | Manual visual/debug setup helpers and screenshots, not product code. |

## Development Commands

Run the backend from the project root:

```bash
uvicorn server.main:app --reload
# or
python -m server.main
```

The backend defaults to `0.0.0.0:8000`. Run the frontend separately:

```bash
cd web
npm install
npm run dev
```

Vite proxies `/api`, `/static`, and `/ws` to `localhost:8000`. For a production-style frontend build and local preview:

```bash
cd web
npm run build
npm run preview
```

`npm run build` writes the default `web/dist/`; the current FastAPI app does not mount or serve that directory. The frontend has no test or lint script.

Run the Python suite from the project root:

```bash
pytest
# focused suites
pytest tests/test_engine.py
pytest tests/test_server.py
pytest tests/test_bugfixes.py
pytest tests/test_bugfixes_engine.py
pytest tests/test_bugfixes_transport.py
```

`pytest.ini` sets `faulthandler_timeout = 60` with `faulthandler_exit_on_timeout`, so a hanging test dumps stacks and fails instead of blocking the suite forever.

## Code Conventions & Common Patterns

- Python uses 4-space indentation, `snake_case` functions/variables/modules, `PascalCase` classes, and type hints on public interfaces. Keep the game engine synchronous and independent of FastAPI.
- Validate game commands in `Game` and raise `GameError`; `Room`/the WebSocket boundary turns that into `{type: "error"}` without changing game state. Validate room membership, capacity, and lifecycle in `server/main.py`/`Room`, not in the frontend.
- Keep transport concerns in `server/main.py` and `server/rooms.py`: connection cleanup, reconnect-by-name, action dispatch, broadcasts, and timers. Keep card rules and state transitions in `server/engine/`.
- Use the deck convention consistently: top is the end of `Deck.cards`; `draw_top()` pops the end and insertion positions count from the top.
- Use `_ask()` for decisions and return continuations through `Game.respond()` rather than coupling the engine to WebSockets.
- Frontend components are function components with React hooks. Keep API URLs relative and use `web/src/api.js`; the Vite proxy and same-origin production routing depend on that. Use `sessionStorage` through the guarded `store` helper.
- Keep private state private in `Game.view(name)`. Public log animation is content-based because the server intentionally sends a sliding `log[-30:]` window.
- Error boundaries and guarded browser storage are intentional patterns: render failures should be visible, and unavailable session storage must not stop the client.
- Do not introduce a second state store or a new dependency for functionality already covered by the existing game state, browser APIs, or installed React/Vite tooling.

## Important Files

- `README.md`: current project layout, supported run/test commands, API summary, and log-animation invariant.
- `server/main.py`: FastAPI app and the REST/WebSocket boundary.
- `server/rooms.py`: in-memory `RoomManager`, session-token connections, action routing, desk voting, and Nope timer.
- `server/engine/game.py`: authoritative game state machine and card-effect rules.
- `server/engine/cards.py`: `Card`, `CARD_META`, Godcat restrictions, and rescue order.
- `server/engine/deck.py`: deck loading and top/bottom/insertion behavior.
- `server/engine/player.py`: player hand, liveness, and effect flags.
- `web/src/Room.jsx`: gameplay state consumer, WebSocket protocol client, actions, and animations.
- `web/src/Home.jsx` and `web/src/api.js`: lobby flow, persistence, REST helpers, session tokens, and WebSocket URL construction.
- `web/package.json`, `web/package-lock.json`, `web/vite.config.js`: frontend scripts, npm lockfile, and backend proxy.
- `resources/desk/*.json` and `resources/cards_desc/*.txt`: runtime deck data and rule reference.
- `tests/test_engine.py`, `tests/test_server.py`, `tests/test_bugfixes.py`, `tests/test_bugfixes_engine.py`, and `tests/test_bugfixes_transport.py`: regression suites.
- `pytest.ini`: hang watchdog for the suite (`faulthandler_timeout`, exit on timeout).
- `docs/superpowers/specs/`, `docs/card-effects-audit.md`, and `tmp_shots/`: historical, audit, or manual-debug material; not routine workflow commands.

## Runtime/Tooling Preferences

- Backend: the application imports FastAPI/Uvicorn and the tests import pytest, so those packages are expected in the active Python environment. No authoritative Python version or dependency manifest is checked in; `.pythonlibs/` is a local environment artifact, not a version contract.
- Frontend package manager: npm. `web/package-lock.json` is an npm lockfile v3; no Bun, pnpm, or Yarn configuration is present. Use `npm install` for the documented setup.
- The lockfile constrains Vite 5 to Node 18.x or >=20 and Rollup to Node >=18 with npm >=8. The repository does not declare an npm version or `packageManager` field.
- Vite is the only configured frontend build tool. The dev proxy is hard-coded to `localhost:8000` in `web/vite.config.js`.
- The current backend is an API/WebSocket server plus card-image mount, not a static host for `web/dist/`.
- Keep `resources/` and the current `server/` tree in sync when adding deck/card data; do not edit generated caches (`__pycache__`, `.pytest_cache`) as source.

## Testing & QA

- `tests/test_engine.py` is the main rule suite: direct synchronous `Game` tests cover dealing, turns, bombs/rescue, Nope, card effects, pending decisions, views, errors, and privacy. It seeds `random`, loads real desk JSON, and uses small helpers to force deterministic scenarios; it does not require a running server.
- `tests/test_server.py` uses `fastapi.testclient.TestClient` against `server.main:app`. It covers REST room/card responses, a two-client lobby/start WebSocket flow, and unknown-room errors without starting Uvicorn.
- `tests/test_bugfixes.py` covers session-token reconnects, malformed envelopes, restart/broadcast safeguards, corrected card rules, private pending data, chronological logs, and public image URLs. It mixes engine and transport cases because each test isolates its own `Room`/`Game`.
- `tests/test_bugfixes_engine.py` covers engine edge cases found by audit: stacked attack carry-over, Armageddon/clone/Garbage Collection interactions, swap-top privacy, and pending-decision invariants. Pure synchronous `Game` tests.
- `tests/test_bugfixes_transport.py` covers `Room`/`RoomManager` and the FastAPI WebSocket boundary with `TestClient` (session tokens, capacity, failed broadcasts, start failures, disconnect roster broadcasts). Runs in-process, no Uvicorn.
- A disconnect broadcast must survive the dying socket's own cancellation: `server/main.py` wraps the leave-notification in `asyncio.shield`, otherwise a cancelled scope (test client teardown, server shutdown) can drop the roster update and hang the remaining client.
- There is no coverage tool/configuration or enforced threshold. The historical design document's approximately 90% branch-coverage goal is aspirational, not a current CI requirement.
- There is no frontend test framework, browser test suite, or lint setup. For UI work, run the actual Vite app and exercise the changed flow in a browser; for backend work, run the focused pytest suite and then the full `pytest` suite when practical.
- When changing a public WebSocket/REST contract, update both `server/rooms.py` or `server/main.py` and the frontend consumer in `web/src/`, then cover the observable path with the server smoke test. When changing a game rule, add or update a focused engine test that exercises the rule through the public `Game` methods.
