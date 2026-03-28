import argparse
import logging
import sys
import time
from typing import Any, Literal
from uuid import UUID

import openapi_client
from openapi_client import DefaultApi
from openapi_client.rest import ApiException

from game_client import DEFAULT_API_HOST, DEFAULT_PLAYER_NAME, join_as_player, resolve_game_id

PlayerColor = Literal["white", "black"]

_http_debug = logging.getLogger(__name__ + ".http")


def _setup_verbose_logging() -> None:
    _http_debug.setLevel(logging.DEBUG)
    _http_debug.propagate = False
    if _http_debug.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _http_debug.addHandler(handler)


class VerboseApiClient(openapi_client.ApiClient):
    """Logs one line per outbound HTTP request (method, URL, status or error)."""

    def call_api(
        self,
        method,
        url,
        header_params=None,
        body=None,
        post_params=None,
        _request_timeout=None,
    ):
        try:
            response_data = super().call_api(
                method,
                url,
                header_params=header_params,
                body=body,
                post_params=post_params,
                _request_timeout=_request_timeout,
            )
        except ApiException as exc:
            _http_debug.debug("%s %s -> error %s", method, url, exc.reason)
            raise
        else:
            _http_debug.debug("%s %s -> %s", method, url, response_data.status)
            return response_data

POLL_INTERVAL_SEC = 5


def _normalize_api_color(color: str | None) -> str | None:
    if color is None:
        return None
    return color.strip().lower()


def make_move(
    board_state: dict[str, Any] | None,
    player_number: int,
    game_state: str | None,
) -> None:
    """Compute and submit the next move. Stub until move logic is implemented."""
    pass


def game_loop(api: DefaultApi, game_id: UUID, our_color: PlayerColor) -> None:
    """Poll current player every ``POLL_INTERVAL_SEC``; on our turn, load board/state and call ``make_move``."""
    player_number = 1 if our_color == "white" else 2
    while True:
        current = api.get_current_player(game_id)
        api_color = _normalize_api_color(current.color)
        if api_color != our_color:
            time.sleep(POLL_INTERVAL_SEC)
            continue

        board_resp = api.get_board(game_id)
        board_state = board_resp.board if isinstance(board_resp.board, dict) else None
        game_state_resp = api.get_game_state(game_id)
        make_move(board_state, player_number, game_state_resp.state)
        time.sleep(POLL_INTERVAL_SEC)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Connect to a remote Mühle game: create or join by id, then register a player.",
    )
    parser.add_argument(
        "--game-id",
        type=UUID,
        metavar="UUID",
        default=None,
        help="Existing game id. If omitted, a new game is created.",
    )
    parser.add_argument(
        "--player",
        default=DEFAULT_PLAYER_NAME,
        help=f'Name sent to POST /games/{{id}}/players (default: "{DEFAULT_PLAYER_NAME}").',
    )
    parser.add_argument(
        "--color",
        choices=("white", "black"),
        required=True,
        metavar="COLOR",
        help="This client's color: white (1st player to join) or black (2nd).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log one line per HTTP request (method, URL, status) to stderr.",
    )
    args = parser.parse_args()

    if args.verbose:
        _setup_verbose_logging()

    configuration = openapi_client.Configuration(host=DEFAULT_API_HOST)
    client_cls = VerboseApiClient if args.verbose else openapi_client.ApiClient
    try:
        with client_cls(configuration) as api_client:
            api = openapi_client.DefaultApi(api_client)
            game_id = resolve_game_id(api, args.game_id)
            join_as_player(api, game_id, args.player)
            try:
                game_loop(api, game_id, args.color)
            except KeyboardInterrupt:
                print("\nStopped.", file=sys.stderr)
                raise SystemExit(0) from None
    except ApiException as exc:
        print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
        if exc.body:
            print(exc.body, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
