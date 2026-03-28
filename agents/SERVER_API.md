# Server HTTP API (summary)

**Source of truth:** [`openapi.yaml`](../openapi.yaml) at the repository root — **Mühle HTTP API**, OpenAPI **3.0.3**, version **1.0.0**.

**Description (from spec):** REST-Schnittstelle für die Mühle-Spielsession: Spiel anlegen, Spieler registrieren, Züge ausführen, Brett und Zustand lesen. Pro Server-Prozess können beliebig viele Partien parallel laufen; jede Partie hat eine eigene `gameId` (UUID), alle Aktionen sind pro Partie isoliert.

## Base URL (`servers`)

| URL | `description` in spec |
|-----|------------------------|
| `http://172.28.40.187:40000` | Lokaler Dev-Server |

Override per environment via `openapi_client.Configuration(host=...)`.

## Endpoints (`paths`)

### `GET /openapi.yaml` — `getOpenAPISpec`

- **200:** OpenAPI 3.0 document (YAML), `application/yaml`, body typed as string in the spec.

### `POST /games` — `createGame`

- **201:** Spiel erzeugt — JSON object, required properties: `message` (string), `id` (string, uuid). Example `message`: *Game created*.
- **500:** Serverfehler — `Error`.

### `POST /games/{gameId}/players` — `addPlayer`

- **Request:** `application/x-www-form-urlencoded`, required: `playerName` (string).
- **200:** Spieler hinzugefügt — JSON with optional `message`, `secret` (string, *Geheimcode für Züge* → use as `secretCode` on moves).
- **404:** `GameNotFound` — unknown or invalid game (`{"error": "..."}`, example `game not found`).
- **500:** e.g. game full — `Error`.

### `POST /games/{gameId}/moves` — `submitMove`

- **Request:** `application/x-www-form-urlencoded`:
  - Required: `action` — enum **`place`**, **`move`**, **`remove`**; `secretCode` (string).
  - Optional: `fieldIndex` — bei place/remove Feld; bei move Startfeld.
  - Optional: `toFieldIndex` — nur bei `action=move`.
- **200:** Zug akzeptiert — JSON with optional `message` (example: *Stone moved*).
- **400:** Ungültige action oder fehlende Felder — `Error`.
- **404:** `GameNotFound`.
- **500:** Regelverletzung o. Ä. — `Error`.

### `GET /games/{gameId}/state` — `getGameState`

- **200:** JSON object with `state` (string).
- **404:** `GameNotFound`.

### `GET /games/{gameId}/current-player` — `getCurrentPlayer`

- **200:** JSON object with `color` (string), example `White`.
- **404:** `GameNotFound`.

### `GET /games/{gameId}/board` — `getBoard`

- **200:** JSON object with `board` (object) — field layout as defined by server (schema not further constrained in the spec).
- **404:** `GameNotFound`.

## Components

- **Parameter `gameId`:** path, required, string, format **uuid**.
- **Schema `Error`:** object with property `error` (string).
- **Response `GameNotFound`:** description *Unbekanntes oder ungültiges Spiel*, body `Error`, example `error: game not found`.
