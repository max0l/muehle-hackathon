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
| **`game/board.py`** | Hand-written **24-point** board and rules core: immutable `Position`, `Move`, legal move generation, `apply_move()`, terminal detection, plus `Board` wrapper for API payloads. |
| **`game/encoding.py`** | Symmetry transforms, canonicalization, fixed-width position encoding/decoding, and deterministic per-subspace indexing. |
| **`game/heuristics.py`** | Phase-aware heuristic evaluation for generated states. |
| **`game/value_codec.py`** | Payload codecs for packed storage: heuristic, WDL, WDL+depth. |
| **`game/packed_store.py`** | Packed indexed score/meta/frontier storage on disk. |
| **`game/generate_db.py`** | CLI to traverse reachable states and persist packed indexed ratings on disk. |
| **`agents/`** | Agent-oriented docs: project overview (this file), API summary, game rules, opening-book / DB plans, generated-client notes in **`README.md`**. |
| **`docs/`** | Generated Markdown API reference (mirrors `DefaultApi` and models). |
| **`test/`** | Generated tests for `openapi_client` (plus any future hand-written tests). |
| **`tests/`** | Hand-written tests for local game logic, canonical encoding/indexing, and packed generation. |
| **`pyproject.toml`**, **`setup.py`**, **`requirements.txt`**, **`tox.ini`** | Packaging, dependencies, and test/lint automation. |
| **`.github/workflows/`** | CI (e.g. Python package / pytest). |

**Implemented now:** the repo contains a local full-game rules engine plus a bounded/resumable **packed indexed state generator**. Search and opening-book consumers can now build on these components.

## Suggested module boundaries (implementation guidance)

- **`game/board.py` (current):** full local rules core with immutable `Position`, `Move`, placement / movement / removal / flying, mill checks, and terminal detection. Keep server string indices and `state` strings in sync with measurements from the API.
- **`game/encoding.py` / `game/value_codec.py` / `game/packed_store.py` / `game/generate_db.py`:** offline state enumeration, symmetry normalization, packed indexed persistence, and configurable payload generation. This is the foundation for lookup-backed search.
- **HTTP:** Use **`openapi_client`** for all Mühle REST calls. Add only a **thin wrapper** (retries, logging, env-based `host`) if needed — do not fork the generated client.
- **`ai` / `search`:** Planners using the rule engine and optional packed lookup data. Keep I/O separate so the same brain can run offline tests.

## Configuration

- **Base URL:** See `servers` in `openapi.yaml` (e.g. dev host/port). Prefer **`openapi_client.Configuration(host=...)`** from env or config; avoid hard-coding in multiple places as `main.py` evolves.

## Language / stack

- **Python** (see **`pyproject.toml`**: `requires-python >= 3.9`, **Pydantic** v2, **urllib3**).
- **Tests:** **pytest** / **tox** with coverage over **`openapi_client`** and **`game`**.
- **Regeneration:** After changing **`openapi.yaml`**, rerun OpenAPI Generator so **`openapi_client/`** and **`test/`** stay in sync.

For details on the generated client’s classes and methods, see **`agents/README.md`** (section *Generated OpenAPI Python client*).
