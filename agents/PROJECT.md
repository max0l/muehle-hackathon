# Project overview

## Goal

Build a **client** for **Nine Men’s Morris** that participates in games via an **HTTP API**. The client should be able to:

1. **Represent game state** consistently with the server (board, phase, current player).
2. **Implement game logic** locally: legal moves, phase transitions (placement → movement → possible mill removals), and end conditions — so the agent can plan, test, and debug without round-tripping every hypothetical move.
3. **Apply heuristics and/or AI** (evaluation functions, minimax / MCTS, opening books, etc.) to **select strong moves** when playing against the server or another client.

## What this repository is *not*

- **Not** the authoritative game server. Session lifecycle, persistence, and final move acceptance are server-side.
- **Not** required to duplicate the server’s internal implementation — but the **client logic must agree with the rules** the server enforces, or moves will be rejected (4xx/5xx).

## Suggested module boundaries (implementation guidance)

- **`state` / `board`:** Board encoding (e.g. 24 intersections), piece counts, phase enum (place / move / remove), current player color.
- **`rules` / `logic`:** Generate legal actions; apply moves; detect mills and forced removals; detect win/loss/draw if inferable from API state.
- **`client` / `api`:** Thin HTTP layer matching `openapi.yaml` (create game, register player, poll state/board, submit moves).
- **`ai` / `search`:** Planners using the rule engine (heuristic evaluation + search). Keep I/O separate so the same brain can run offline tests.

## Configuration

- **Base URL:** See `servers` in `openapi.yaml` (e.g. dev host/port). The client should make the base URL configurable (env or config file) for different environments.

## Language / stack

The repository is currently minimal (e.g. `main.py`); agents should follow whatever stack the project adopts and keep the split above unless the team agrees otherwise.
