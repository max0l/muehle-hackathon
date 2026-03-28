# Project overview

## Goal

Build a **client** for **Nine Men’s Morris** that participates in games via an **HTTP API**. The client should be able to:

1. **Represent game state** consistently with the server (board, phase, current player).
2. **Implement game logic** locally: legal moves, phase transitions (placement → movement → possible mill removals), and end conditions — so the agent can plan, test, and debug without round-tripping every hypothetical move.
3. **Apply heuristics and/or AI** (evaluation functions, minimax / MCTS, opening books, etc.) to **select strong moves** when playing against the server or another client.

## What this repository is *not*

- **Not** the authoritative game server. Session lifecycle, persistence, and final move acceptance are server-side.
- **Not** required to duplicate the server’s internal implementation — but the **client logic must agree with the rules** the server enforces, or moves will be rejected (4xx/5xx).

## Repository layout

| Path | Role |
|------|------|
| **`openapi.yaml`** | API contract (source of truth for HTTP). |
| **`openapi_client/`** | **Generated** Python client (OpenAPI Generator, Pydantic). Do not hand-edit; regenerate from the spec. |
| **`.openapi-generator/`**, **`.openapi-generator-ignore`** | Generator metadata and ignore rules. |
| **`main.py`** | Application entry (currently wires `Configuration` / `ApiClient` / `DefaultApi`); room to grow into a CLI or game loop. |
| **`agents/`** | Agent-oriented docs: project overview (this file), API summary, game rules, opening-book / DB plans, generated-client notes in **`README.md`**. |
| **`docs/`** | Generated Markdown API reference (mirrors `DefaultApi` and models). |
| **`test/`** | Generated tests for `openapi_client` (plus any future hand-written tests). |
| **`pyproject.toml`**, **`setup.py`**, **`requirements.txt`**, **`tox.ini`** | Packaging, dependencies, and test/lint automation. |
| **`.github/workflows/`** | CI (e.g. Python package / pytest). |

Game logic, search, and opening-book code are **not** present yet as top-level packages; the expected layout below is the target as those features land.

## Suggested module boundaries (implementation guidance)

- **`state` / `board`:** Board encoding (e.g. 24 intersections), piece counts, phase enum (place / move / remove), current player color. Map to/from server `board` JSON (see **`agents/README.md`** — schema is open in OpenAPI).
- **`rules` / `logic`:** Generate legal actions; apply moves; detect mills and forced removals; detect win/loss/draw if inferable from API state.
- **HTTP:** Use **`openapi_client`** for all Mühle REST calls. Add only a **thin wrapper** (retries, logging, env-based `host`) if needed — do not fork the generated client.
- **`ai` / `search`:** Planners using the rule engine (heuristic evaluation + search). Keep I/O separate so the same brain can run offline tests.

## Configuration

- **Base URL:** See `servers` in `openapi.yaml` (e.g. dev host/port). Prefer **`openapi_client.Configuration(host=...)`** from env or config; avoid hard-coding in multiple places as `main.py` evolves.

## Language / stack

- **Python** (see **`pyproject.toml`**: `requires-python >= 3.9`, **Pydantic** v2, **urllib3**).
- **Tests:** **pytest** / **tox** with coverage over **`openapi_client`**.
- **Regeneration:** After changing **`openapi.yaml`**, rerun OpenAPI Generator so **`openapi_client/`** and **`test/`** stay in sync.

For details on the generated client’s classes and methods, see **`agents/README.md`** (section *Generated OpenAPI Python client*).
