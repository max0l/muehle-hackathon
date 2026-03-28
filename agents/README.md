# Agents context (Mühle / Nine Men’s Morris)

This folder is **onboarding and reference material for AI coding agents** working in this repository. Read it before large changes so assumptions match the hackathon setup.

## Files

| File | Purpose |
|------|---------|
| [PROJECT.md](./PROJECT.md) | What the repo is, architecture (client vs server), what belongs in this codebase |
| [GAME_RULES.md](./GAME_RULES.md) | Nine Men’s Morris rules relevant to logic and move generation |
| [SERVER_API.md](./SERVER_API.md) | HTTP contract summary (source of truth: `openapi.yaml` at repo root) |
| [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md) | Plan Option A: Eröffnungsbuch via Negamax/Alpha-Beta, TT, Heuristik, CLI, Tests, offene Regelfragen |

## Quick facts

- **Game:** Nine Men’s Morris (German: *Mühle*).
- **This repo:** **Client only** — talks to a remote game server; does not host match state or authoritative rules on the wire beyond what the server enforces.
- **Expected client capabilities:** Local **game logic** (validation, move listing, state representation), plus **heuristics / search / AI** to choose or analyze moves against the server API.

## Canonical spec

For request/response shapes and status codes, always prefer **`openapi.yaml`** in the repository root over this prose; `SERVER_API.md` is a shortened mirror for agents.
