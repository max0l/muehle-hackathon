# Agents context (Mühle / Nine Men’s Morris)

This folder is **onboarding and reference material for AI coding agents** working in this repository. Read it before large changes so assumptions match the hackathon setup.

## Files

| File | Purpose |
|------|---------|
| [PROJECT.md](./PROJECT.md) | What the repo is, architecture (client vs server), what belongs in this codebase |
| [GAME_RULES.md](./GAME_RULES.md) | Nine Men’s Morris rules relevant to logic and move generation |
| [SERVER_API.md](./SERVER_API.md) | HTTP contract summary (source of truth: `openapi.yaml` at repo root) |
| [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md) | Plan Option A: Eröffnungsbuch via Negamax/Alpha-Beta, TT, Heuristik, CLI, Tests, offene Regelfragen |
| [GASSER_OPENING_HEURISTICS.md](./GASSER_OPENING_HEURISTICS.md) | Gasser (1996): opening = search + DB leaves; rule variants; heuristic fallback when no DB |
| [MID_ENDGAME_DATABASE_PLAN.md](./MID_ENDGAME_DATABASE_PLAN.md) | Plan: retrograde mid/end tables — canonical encoding, perfect indexing, predecessors, build & lookup |

**Hand-written game code:** [`game/`](../game/) — see *Local game model* and *Heuristic DB generator* below.

## Quick facts

- **Game:** Nine Men’s Morris (German: *Mühle*).
- **This repo:** **Client only** — talks to a remote game server; does not host match state or authoritative rules on the wire beyond what the server enforces.
- **Expected client capabilities:** Local **game logic** (validation, move listing, state representation), plus **heuristics / search / AI** to choose or analyze moves against the server API.

## Mühle HTTP API (mirrors `openapi.yaml`)

Contract file: **[`openapi.yaml`](../openapi.yaml)** — OpenAPI **3.0.3**, **`info.version`:** **1.0.0**, **`info.title`:** **Mühle HTTP API**.

**`info.description` (spec, DE):** REST-Schnittstelle für die Mühle-Spielsession; Spiel anlegen, Spieler registrieren, Züge ausführen, Brett und Zustand lesen; beliebig viele Partien pro Server, isoliert per `gameId` (UUID).

**`servers[0]`:** `http://172.28.40.187:40000` — *Lokaler Dev-Server*.

| `operationId` | HTTP | Notes from spec |
|---------------|------|-----------------|
| `getOpenAPISpec` | GET `/openapi.yaml` | Returns YAML spec |
| `createGame` | POST `/games` | `201` → `message`, `id` (uuid); `500` |
| `addPlayer` | POST `/games/{gameId}/players` | form `playerName`; `200` → `secret` (+ optional `message`); `404` / `500` |
| `submitMove` | POST `/games/{gameId}/moves` | form: `action` ∈ {`place`,`move`,`remove`}, `secretCode`, optional `fieldIndex`, `toFieldIndex` for move; `200` / `400` / `404` / `500` |
| `getGameState` | GET `/games/{gameId}/state` | `200` → `state`; `404` |
| `getCurrentPlayer` | GET `/games/{gameId}/current-player` | `200` → `color` (e.g. `White`); `404` |
| `getBoard` | GET `/games/{gameId}/board` | `200` → `board` (object); `404` |

**Errors:** `components.schemas.Error` — `{ "error": string }`. **`GameNotFound`** — *Unbekanntes oder ungültiges Spiel*, example `game not found`.

Longer prose: **[SERVER_API.md](./SERVER_API.md)**. Human-oriented project layout: **[PROJECT.md](./PROJECT.md)**.

## Local game model (`game/`)

First-party logic for the **24-point** Morris board lives in **[`game/`](../game/)** (not generated).

### Point indexing `0 … 23`

The file documents the standard triple-square layout in ASCII; coordinates match **`ADJACENCY`** and **`MILLS`**.

- **Adjacency:** `ADJACENCY[i]` lists neighbors of point `i` (edges for sliding / distance-1 moves).
- **Mills:** `MILLS` is the fixed list of **16** triples `(a, b, c)` that form lines on this labeling (outer, middle, inner squares plus four “cross” lines through midpoints).

### Cell values (`Board.board`)

- **`0`** — empty  
- **`1`** — white  
- **`2`** — black  

### Server JSON → `Board`

`Board.__init__` expects a **list of field dicts** from the API shape: each item uses **`"Index"`** (int, `0…23`) and **`"Color"`** (int `0/1/2`). Names are **PascalCase** to match the current server payload style.

### Core files

- **[`game/board.py`](../game/board.py)** — immutable `Position`, `Move`, board geometry, mill detection, legal moves, `apply_move()`, terminal detection, and the compatibility `Board` wrapper.
- **[`game/encoding.py`](../game/encoding.py)** — symmetry transforms, canonicalization, and fixed-width state encoding / decoding.
- **[`game/heuristics.py`](../game/heuristics.py)** — phase-aware heuristic scorer for nonterminal states.
- **[`game/packed_store.py`](../game/packed_store.py)** — packed indexed file storage with file-backed frontier/progress bookkeeping.
- **[`game/value_codec.py`](../game/value_codec.py)** — configurable payload codecs: `heuristic`, `wdl`, `wdl-depth`.
- **[`game/generate_db.py`](../game/generate_db.py)** — CLI/resumable generator that traverses reachable states and writes key/value scores to disk.

### Phase type

`GameState = Literal["placing", "moving", "flying", "remove", "end"]`.

### Moves

- **`Move`:** `type` ∈ `place` | `move` | `remove` (same verbs as HTTP `action`), plus `fieldIndex` (int), optional `toFieldIndex`, optional `removedPiece`.
- **Move generation is implemented** for:
  - placement
  - sliding moves via `ADJACENCY`
  - flying moves when the side to move has three stones
  - removal states after a mill is closed
- **`apply_move()`** advances immutable positions through placement, removal, movement, and flying.
- **`terminal_winner()` / `is_terminal()`** model losses by fewer than three stones or no legal move.

### Display

**`pretty_print()`** returns an ASCII diagram using **`·` / `W` / `B`** for empty / white / black.

### Wiring to HTTP

- Map API **`fieldIndex` / `toFieldIndex` strings** to **ints** `0…23` before constructing `Move` or comparing to `Board.board`.
- Confirm server **color encoding** matches `1` = white, `2` = black (and empty `0`).
- `Board.__init__` still accepts server-style field dicts (`Index`, `Color`) for easy API integration, but the generator/search code should prefer immutable `Position`.

## Heuristic DB generator (`game/generate_db.py`)

The repo now contains a **full-game packed/indexed state generator** that stores values on disk without an in-memory KV database.

### What it writes

- **Index:** canonicalized `Position` ranked into a deterministic per-subspace index from **[`game/encoding.py`](../game/encoding.py)**.
- **Payload:** configurable via **[`game/value_codec.py`](../game/value_codec.py)**:
  - signed heuristic score
  - WDL
  - WDL + depth
- **Extra files:** metadata plus a file-backed frontier queue for resumable generation.

### CLI

Run via:

- `python3 -m game.generate_db --output state_db.packed --value-mode heuristic --max-depth 4 --max-states 10000 --json`

Supported flags:

- `--output`
- `--value-mode`
- `--max-depth`
- `--max-states`
- `--batch-size`
- `--page-entries`
- `--resume`
- `--json`

### Current scoring model

The heuristic currently combines:

- material / stones remaining
- stones on board
- closed mills
- open two-in-a-rows
- double threats
- mobility
- blocked opponent stones
- closing-move pressure
- phase-aware weights for `placing`, `moving`, `flying`, and `remove`

Terminal positions return large win/loss scores relative to the side to move.

### Notes on payload modes

- **`heuristic`** stores the signed evaluation directly.
- **`wdl`** stores `-1 / 0 / 1`, using exact terminal results when known and heuristic sign otherwise.
- **`wdl-depth`** stores the same WDL classification plus the generator ply depth at which the state was written. This is **not** yet retrograde depth-to-win/loss from the paper.

## Generated OpenAPI Python client (`openapi_client`)

The repo root package **`openapi_client/`** is **auto-generated** from **`openapi.yaml`** by [OpenAPI Generator](https://openapi-generator.tech) (`PythonClientCodegen`, Pydantic v2 models, `urllib3`). Treat it as **read-only**: fix the spec and **regenerate** instead of editing generated files. Metadata: **`.openapi-generator/`**, **`.openapi-generator-ignore`**, root **`README.md`** and **`docs/`** (per-operation examples).

### How to use it

1. **`openapi_client.Configuration(host=...)`** — set the server base URL (default in spec is only an example; `main.py` hard-codes a dev host).
2. **`openapi_client.ApiClient(configuration)`** as a context manager (or long-lived client).
3. **`openapi_client.DefaultApi(api_client)`** — all REST operations are methods on this class.

### `DefaultApi` ↔ HTTP

| Python method | HTTP | Success model / notes |
|---------------|------|------------------------|
| `create_game()` | `POST /games` | `CreateGame201Response` — `id` (`UUID`), `message` |
| `add_player(game_id, player_name)` | `POST /games/{gameId}/players` (form) | `AddPlayer200Response` — `secret` (move auth), optional `message` |
| `submit_move(game_id, action, secret_code, field_index=..., to_field_index=...)` | `POST /games/{gameId}/moves` (form) | `SubmitMove200Response`; `action` is `str` at type level — use `place` / `move` / `remove` per spec |
| `get_game_state(game_id)` | `GET /games/{gameId}/state` | `GetGameState200Response` — `state` |
| `get_current_player(game_id)` | `GET /games/{gameId}/current-player` | `GetCurrentPlayer200Response` — `color` |
| `get_board(game_id)` | `GET /games/{gameId}/board` | `GetBoard200Response` — `board` is **`Dict[str, Any]`** (schema is open in the spec; parse defensively in game logic) |
| `get_open_api_spec()` | `GET /openapi.yaml` | Raw spec payload (string) |

Each operation also has `*_with_http_info` (access status headers) and `*_without_preload_content` variants.

### Errors and typing

- Failures raise **`openapi_client.rest.ApiException`** (HTTP status and body available on the exception object).
- **`Error`** model: `{ "error": str }` for documented error responses.
- **`game_id`** parameters are **`uuid.UUID`**, not strings — convert when reading IDs from JSON/config.

### Tests and layout

- **`test/`** — generated tests against the package (e.g. `DefaultApi`, models); **`tox.ini`** / CI run **`pytest --cov=openapi_client`**.
- **`tests/`** — hand-written tests for local game logic and the generator (`test_game_rules.py`, `test_generate_db.py`).
- App code can live beside the package (e.g. **`main.py`**) and import `openapi_client` like any other dependency; **`pyproject.toml`** names the project `openapi_client` and pins runtime deps (`pydantic`, `urllib3`, etc.).

### Agents: where to implement what

- **Networking only** — use `openapi_client`; keep a thin wrapper if you need retries, logging, or env-based `host`.
- **Board geometry, rules, and state transitions** — **`game/board.py`**.
- **Canonical state keys / symmetry normalization** — **`game/encoding.py`**.
- **Heuristic evaluation** — **`game/heuristics.py`**.
- **On-disk packed DB generation** — **`game/generate_db.py`** + **`game/packed_store.py`** + **`game/value_codec.py`**.
- **OpenAPI** still does not constrain `board` JSON beyond `object` — validate **`Index` / `Color`** and string field indices against the live server.

## Canonical spec

Always prefer **[`openapi.yaml`](../openapi.yaml)** over this folder for exact request/response shapes and status codes. The **`openapi_client`** package is the generated Python projection of that spec (method names follow `operationId`, e.g. `create_game` ← `createGame`).
