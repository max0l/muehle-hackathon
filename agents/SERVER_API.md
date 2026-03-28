# Server HTTP API (summary)

**Source of truth:** `openapi.yaml` at the repository root (`Mühle HTTP API`, OpenAPI 3.0.3).

## Base URL

Configured under `servers` in the spec (example in spec: `http://172.28.40.187:40000`). Override per environment.

## Endpoints

### `GET /openapi.yaml`

Returns the OpenAPI document (YAML).

### `POST /games`

Creates a new game. **Response:** `201` JSON `{ message, id }` where `id` is a UUID (`gameId`).

### `POST /games/{gameId}/players`

**Body (form):** `playerName` (required).

**Response:** `200` JSON with `message` and `secret` — the **secret** is the `secretCode` for moves.

Errors: `404` game not found; `500` e.g. game full.

### `POST /games/{gameId}/moves`

**Body (form):**

| Field | Required | Notes |
|-------|----------|--------|
| `action` | yes | `place` \| `move` \| `remove` |
| `secretCode` | yes | From player registration |
| `fieldIndex` | depends | For `place` / `remove`, and **start** field for `move` |
| `toFieldIndex` | for `move` | Destination field |

**Response:** `200` on success; `400` invalid action or missing fields; `404` game not found; `500` rule violation, etc.

### `GET /games/{gameId}/state`

**Response:** `200` JSON with `state` (string) — game phase / status as defined by server.

### `GET /games/{gameId}/current-player`

**Response:** `200` JSON with `color` (e.g. `White`).

### `GET /games/{gameId}/board`

**Response:** `200` JSON with `board` (object) — field layout as defined by server.

## Error shape

Typical error JSON: `{ "error": "..." }` (see `components.schemas.Error` in the spec).
