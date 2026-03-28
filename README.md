# Mühle hackathon — HTTP API client

Python workspace for **Nine Men’s Morris** (*Mühle*) against the **Mühle HTTP API**.

The machine-readable contract is **[`openapi.yaml`](openapi.yaml)** (OpenAPI **3.0.3**, API version **1.0.0**). The **`openapi_client`** package is **generated** from that file with [OpenAPI Generator](https://openapi-generator.tech) (`PythonClientCodegen` **7.21.0**, Pydantic v2). Regenerate the client after spec changes; do not edit `openapi_client/` by hand.

## API (`info` / `paths` from the spec)

**Title:** Mühle HTTP API  

**Description (spec):** REST API for the Morris session: create games, register players, execute moves, read board and state. Any number of games may run per server process; each game has its own `gameId` (UUID) and isolated actions.

### Server (`servers` in `openapi.yaml`)

| URL | Description in spec |
|-----|---------------------|
| `http://172.28.40.187:40000` | Lokaler Dev-Server |

Point the client at your environment with `openapi_client.Configuration(host="https://your-host")`.

### Endpoints

All paths are relative to the configured host.

| Operation | Method | Path | Success | Other responses |
|-----------|--------|------|---------|-----------------|
| `getOpenAPISpec` | GET | `/openapi.yaml` | `200` — OpenAPI 3.0 document (`application/yaml`) | — |
| `createGame` | POST | `/games` | `201` — `{ "message", "id" }` (`id` is UUID) | `500` + `Error` |
| `addPlayer` | POST | `/games/{gameId}/players` | `200` — `{ "message"?, "secret" }` (`secret` → `secretCode` on moves) | `404` GameNotFound, `500` (e.g. game full) + `Error` |
| `submitMove` | POST | `/games/{gameId}/moves` | `200` — `{ "message" }` (e.g. *Stone moved*) | `400`, `404`, `500` + `Error` |
| `getGameState` | GET | `/games/{gameId}/state` | `200` — `{ "state" }` | `404` GameNotFound |
| `getCurrentPlayer` | GET | `/games/{gameId}/current-player` | `200` — `{ "color" }` (example: `White`) | `404` GameNotFound |
| `getBoard` | GET | `/games/{gameId}/board` | `200` — `{ "board" }` (object; structure defined by server) | `404` GameNotFound |

**`addPlayer`** request: `application/x-www-form-urlencoded`, required field **`playerName`**.

**`submitMove`** request: `application/x-www-form-urlencoded`:

- Required: **`action`** — one of `place`, `move`, `remove`; **`secretCode`**
- Optional: **`fieldIndex`** — for `place` / `remove` (field); for `move`, start field
- Optional: **`toFieldIndex`** — only for `action=move` (destination)

**`Error`** schema: `{ "error": string }`. **Game not found** example from spec: `game not found`.

### Python surface

See **[`agents/README.md`](agents/README.md)** for `DefaultApi` method names, models, and `ApiException` handling. Generated Markdown per operation: **[`docs/DefaultApi.md`](docs/DefaultApi.md)**.

---

## Requirements

Python **3.9+**

## Installation

From the repository root (editable install for development):

```sh
pip install -e .
```

Or use Setuptools:

```sh
python setup.py install --user
```

## Tests

```sh
pytest
```

(With coverage, as in CI / `tox.ini`: `pytest --cov=openapi_client`.)

## Getting started

```python
from pprint import pprint
from uuid import UUID

import openapi_client
from openapi_client.rest import ApiException

configuration = openapi_client.Configuration(
    host="http://172.28.40.187:40000"  # default in openapi.yaml; change for your server
)

with openapi_client.ApiClient(configuration) as api_client:
    api = openapi_client.DefaultApi(api_client)

    try:
        created = api.create_game()
        game_id = created.id
        print("game id:", game_id)

        joined = api.add_player(game_id, "player_1")
        secret = joined.secret
        pprint(joined)

        state = api.get_game_state(game_id)
        pprint(state)

        # api.submit_move(game_id, action="place", secret_code=secret, field_index="...")
    except ApiException as e:
        print(f"HTTP {e.status}: {e.reason}\n{e.body}")
```

`game_id` must be a **`uuid.UUID`** (not a string) when calling `DefaultApi`.

## Documentation (generated)

- [DefaultApi](docs/DefaultApi.md) — all operations  
- Models: [CreateGame201Response](docs/CreateGame201Response.md), [AddPlayer200Response](docs/AddPlayer200Response.md), [SubmitMove200Response](docs/SubmitMove200Response.md), [GetGameState200Response](docs/GetGameState200Response.md), [GetCurrentPlayer200Response](docs/GetCurrentPlayer200Response.md), [GetBoard200Response](docs/GetBoard200Response.md), [Error](docs/Error.md)

## Authorization

The OpenAPI spec defines **no** security schemes; endpoints do not require API keys or Bearer tokens in the contract.

## Agent / contributor context

Design notes and AI-oriented docs live under **[`agents/`](agents/README.md)**.
