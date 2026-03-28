from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time
from typing import Any, Literal, Mapping, Tuple, Union
from uuid import UUID

import openapi_client
from openapi_client import DefaultApi
from openapi_client.rest import ApiException

from game import Move, PackedStateStore, Position, apply_move, get_value_codec, legal_moves
from game.heuristics import heuristic_score
from game_client import DEFAULT_API_HOST, DEFAULT_PLAYER_NAME, join_as_player, resolve_game_id

PlayerColor = Literal["white", "black"]
PayloadValue = Union[int, Tuple[int, int]]

_http_debug = logging.getLogger(__name__ + ".http")
_search_debug = logging.getLogger(__name__ + ".search")


def _setup_verbose_logging() -> None:
    _http_debug.setLevel(logging.DEBUG)
    _http_debug.propagate = False
    if _http_debug.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _http_debug.addHandler(handler)


def _setup_search_debug_logging() -> None:
    _search_debug.setLevel(logging.DEBUG)
    _search_debug.propagate = False
    if _search_debug.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _search_debug.addHandler(handler)


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
_SERVER_WAITING_STATE = "waitingforplayers"
_SERVER_PLACING_STATES = {"placingstone", "puttingstone"}
_SERVER_MOVING_STATE = "movingstone"
_SERVER_REMOVING_STATE = "removingstone"
_SERVER_WIN_STATES = {"winblack", "winwhite"}


def _normalize_api_color(color: str | None) -> str | None:
    if color is None:
        return None
    return color.strip().lower()


def _normalize_game_state(game_state: str | None) -> str:
    if not game_state:
        return "moving"
    normalized = game_state.strip().lower()
    if normalized in _SERVER_PLACING_STATES:
        return "placing"
    if normalized == _SERVER_MOVING_STATE:
        return "moving"
    if normalized == _SERVER_REMOVING_STATE:
        return "remove"
    if normalized in _SERVER_WIN_STATES:
        return "end"
    if any(token in normalized for token in ("remove", "take", "schlag")):
        return "remove"
    if any(token in normalized for token in ("end", "over", "won", "lost", "draw", "finish")):
        return "end"
    if any(token in normalized for token in ("place", "placing", "setz")):
        return "placing"
    return "moving"


def _classify_server_state(game_state: str | None) -> Literal["waiting", "placing", "moving", "removing", "finished", "unknown"]:
    if not game_state:
        return "unknown"
    normalized = game_state.strip().lower()
    if normalized == _SERVER_WAITING_STATE:
        return "waiting"
    if normalized in _SERVER_PLACING_STATES:
        return "placing"
    if normalized == _SERVER_MOVING_STATE:
        return "moving"
    if normalized == _SERVER_REMOVING_STATE:
        return "removing"
    if normalized in _SERVER_WIN_STATES:
        return "finished"
    return "unknown"


def _submit_selected_move(
    api: DefaultApi,
    game_id: UUID,
    secret: str,
    move: Move,
) -> None:
    if move.type == "move":
        api.submit_move(
            game_id,
            move.type,
            secret,
            field_index=str(move.fieldIndex),
            to_field_index=str(move.toFieldIndex),
        )
        return

    if move.type == "remove":
        target = move.removedPiece if move.removedPiece is not None else move.fieldIndex
        api.submit_move(game_id, move.type, secret, field_index=str(target))
        return

    api.submit_move(game_id, move.type, secret, field_index=str(move.fieldIndex))


def _board_fields_from_payload(board_state: Mapping[str, Any] | None) -> list[dict[str, int]]:
    if not board_state:
        return []
    raw_fields = board_state.get("Fields") or board_state.get("fields") or []
    fields: list[dict[str, int]] = []
    for row in raw_fields:
        if not isinstance(row, dict):
            continue
        index = row.get("Index", row.get("index"))
        color = row.get("Color", row.get("color"))
        if index is None or color is None:
            continue
        fields.append({"Index": int(index), "Color": int(color)})
    return fields


def _board_piece_counts(board_state: Mapping[str, Any] | None) -> tuple[int, int]:
    white_on_board = 0
    black_on_board = 0
    for field in _board_fields_from_payload(board_state):
        if field["Color"] == 1:
            white_on_board += 1
        elif field["Color"] == 2:
            black_on_board += 1
    return white_on_board, black_on_board


def _position_from_api_board(
    board_state: Mapping[str, Any] | None,
    player_number: int,
    game_state: str | None,
    *,
    white_in_hand: int | None = None,
    black_in_hand: int | None = None,
) -> Position:
    from game.board import Board

    board = Board(
        _board_fields_from_payload(board_state),
        states=_normalize_game_state(game_state),  # type: ignore[arg-type]
        player_to_move=player_number,
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
    )
    return board.position


def _payload_to_score(payload: PayloadValue) -> int:
    if isinstance(payload, tuple):
        wdl, depth = payload
        if wdl > 0:
            return 1_000_000 - depth
        if wdl < 0:
            return -1_000_000 + depth
        return 0
    return payload


@dataclasses.dataclass(frozen=True)
class SearchCandidate:
    move: Move
    payload: PayloadValue
    score: int
    source: str


@dataclasses.dataclass
class HandStateTracker:
    white_in_hand: int | None = None
    black_in_hand: int | None = None
    last_white_on_board: int | None = None
    last_black_on_board: int | None = None

    def observe(
        self,
        board_state: Mapping[str, Any] | None,
        state_kind: Literal["waiting", "placing", "moving", "removing", "finished", "unknown"],
    ) -> tuple[int, int]:
        white_on_board, black_on_board = _board_piece_counts(board_state)
        if self.white_in_hand is None or self.black_in_hand is None:
            if state_kind == "placing":
                self.white_in_hand = max(0, 9 - white_on_board)
                self.black_in_hand = max(0, 9 - black_on_board)
            elif state_kind == "removing":
                # Best effort for mid-game joins: if not all 18 stones are on the board yet,
                # we are still in the placement stage even though a removal is pending.
                still_placing = white_on_board + black_on_board < 18
                self.white_in_hand = max(0, 9 - white_on_board) if still_placing else 0
                self.black_in_hand = max(0, 9 - black_on_board) if still_placing else 0
            else:
                self.white_in_hand = 0
                self.black_in_hand = 0
        else:
            white_gain = 0 if self.last_white_on_board is None else max(0, white_on_board - self.last_white_on_board)
            black_gain = 0 if self.last_black_on_board is None else max(0, black_on_board - self.last_black_on_board)
            if white_gain:
                self.white_in_hand = max(0, self.white_in_hand - white_gain)
            if black_gain:
                self.black_in_hand = max(0, self.black_in_hand - black_gain)
            if state_kind in {"moving", "finished"}:
                self.white_in_hand = 0
                self.black_in_hand = 0

        self.last_white_on_board = white_on_board
        self.last_black_on_board = black_on_board
        return self.white_in_hand, self.black_in_hand


def _format_move(move: Move) -> str:
    if move.type == "move":
        return f"move {move.fieldIndex}->{move.toFieldIndex}"
    if move.type == "remove":
        target = move.removedPiece if move.removedPiece is not None else move.fieldIndex
        return f"remove {target}"
    return f"place {move.fieldIndex}"


def _log_search_summary(
    position: Position,
    candidates: list[SearchCandidate],
    db_hits: int,
    db_misses: int,
) -> None:
    _search_debug.debug(
        "search: phase=%s to_move=%s legal_moves=%d db_hits=%d db_misses=%d",
        position.phase,
        position.player_to_move,
        len(candidates),
        db_hits,
        db_misses,
    )
    for rank, candidate in enumerate(candidates[:5], start=1):
        _search_debug.debug(
            "search: #%d %s score=%s payload=%s source=%s",
            rank,
            _format_move(candidate.move),
            candidate.score,
            candidate.payload,
            candidate.source,
        )


def choose_move(
    store: PackedStateStore,
    board_state: Mapping[str, Any] | None,
    player_number: int,
    game_state: str | None,
    *,
    white_in_hand: int | None = None,
    black_in_hand: int | None = None,
    debug: bool = False,
) -> tuple[Move, PayloadValue] | None:
    position = _position_from_api_board(
        board_state,
        player_number,
        game_state,
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
    )
    candidates = legal_moves(position)
    if not candidates:
        if debug:
            _search_debug.debug(
                "search: phase=%s to_move=%s legal_moves=0",
                position.phase,
                position.player_to_move,
            )
        return None

    best_move: Move | None = None
    best_value: PayloadValue | None = None
    best_score: int | None = None
    ranked_candidates: list[SearchCandidate] = []
    db_hits = 0
    db_misses = 0
    for move in candidates:
        next_position = apply_move(position, move)
        payload = store.lookup(next_position)
        source = "db"
        if payload is None:
            payload = heuristic_score(next_position)
            source = "heuristic"
            db_misses += 1
        else:
            db_hits += 1
        score = _payload_to_score(payload)
        ranked_candidates.append(
            SearchCandidate(move=move, payload=payload, score=score, source=source)
        )
        if best_score is None or score > best_score:
            best_move = move
            best_value = payload
            best_score = score

    ranked_candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    if debug:
        _log_search_summary(position, ranked_candidates, db_hits, db_misses)

    if best_move is None or best_value is None:
        return None
    return best_move, best_value


def make_move(
    api: DefaultApi,
    game_id: UUID,
    secret: str,
    store: PackedStateStore,
    board_state: dict[str, Any] | None,
    player_number: int,
    game_state: str | None,
    *,
    white_in_hand: int | None = None,
    black_in_hand: int | None = None,
    debug: bool = False,
) -> Move | None:
    """Compute and submit the next move using the packed state DB."""
    state_kind = _classify_server_state(game_state)
    if state_kind == "waiting":
        if debug:
            _search_debug.debug("search: server state=%s; waiting for the second player", game_state)
        return None
    if state_kind == "finished":
        if debug:
            _search_debug.debug("search: server state=%s; game already finished", game_state)
        return None
    if board_state is None:
        if debug:
            _search_debug.debug("search: missing board payload for state=%s", game_state)
        return None

    chosen = choose_move(
        store,
        board_state,
        player_number,
        game_state,
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
        debug=debug,
    )
    if chosen is None:
        return None

    move, payload = chosen
    expected_move_type = {"placing": "place", "moving": "move", "removing": "remove"}.get(state_kind)
    if expected_move_type is not None and move.type != expected_move_type:
        raise ValueError(
            f"Selected illegal action {move.type!r} for server state {game_state!r}; expected {expected_move_type!r}"
        )
    if debug:
        _search_debug.debug("search: selected %s payload=%s", _format_move(move), payload)
    else:
        print(f"Selected move: {move} -> {payload}", file=sys.stderr)
    _submit_selected_move(api, game_id, secret, move)
    return move


def game_loop(
    api: DefaultApi,
    game_id: UUID,
    our_color: PlayerColor,
    secret: str,
    store: PackedStateStore,
    *,
    debug: bool = False,
) -> None:
    """Poll current player every ``POLL_INTERVAL_SEC``; on our turn, load board/state and call ``make_move``."""
    player_number = 1 if our_color == "white" else 2
    last_wait_reason: tuple[str, str | None] | None = None
    hand_state = HandStateTracker()
    while True:
        game_state_resp = api.get_game_state(game_id)
        state_kind = _classify_server_state(game_state_resp.state)
        if state_kind == "finished":
            print(f"Game finished: {game_state_resp.state}", file=sys.stderr)
            return
        if state_kind == "waiting":
            wait_reason = ("waiting", game_state_resp.state)
            if wait_reason != last_wait_reason:
                if debug:
                    _search_debug.debug("search: server state=%s; waiting for players", game_state_resp.state)
                else:
                    print("Waiting for players.", file=sys.stderr)
                last_wait_reason = wait_reason
            time.sleep(POLL_INTERVAL_SEC)
            continue

        board_resp = api.get_board(game_id)
        board_state = board_resp.board if isinstance(board_resp.board, dict) else None
        white_in_hand, black_in_hand = hand_state.observe(board_state, state_kind)

        current = api.get_current_player(game_id)
        api_color = _normalize_api_color(current.color)
        if api_color != our_color:
            wait_reason = ("other-player", api_color)
            if wait_reason != last_wait_reason:
                if debug:
                    _search_debug.debug("search: waiting for turn; current player=%s our color=%s", api_color, our_color)
                else:
                    print(f"Waiting for turn: current player is {api_color}.", file=sys.stderr)
                last_wait_reason = wait_reason
            time.sleep(POLL_INTERVAL_SEC)
            continue

        last_wait_reason = None
        make_move(
            api,
            game_id,
            secret,
            store,
            board_state,
            player_number,
            game_state_resp.state,
            white_in_hand=white_in_hand,
            black_in_hand=black_in_hand,
            debug=debug,
        )
        time.sleep(POLL_INTERVAL_SEC)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect to a remote Mühle game: create or join by id, then register a player.",
    )
    start_group = parser.add_mutually_exclusive_group()
    start_group.add_argument(
        "--create-game",
        action="store_true",
        help="Create a new game explicitly.",
    )
    start_group.add_argument(
        "--join-game",
        "--game-id",
        dest="join_game_id",
        type=UUID,
        metavar="UUID",
        default=None,
        help="Join an existing game by id. `--game-id` is supported as an alias.",
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
    parser.add_argument(
        "--db-path",
        default="state_db.packed",
        help='Path to the packed state database directory (default: "state_db.packed").',
    )
    parser.add_argument(
        "--db-value-mode",
        choices=("heuristic", "wdl", "wdl-depth"),
        default="heuristic",
        help="Payload mode used when the packed DB was generated.",
    )
    parser.add_argument(
        "--search-debug",
        action="store_true",
        help="Log move search status, DB hits/misses, and top candidates to stderr.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        _setup_verbose_logging()
    if args.search_debug:
        _setup_search_debug_logging()

    configuration = openapi_client.Configuration(host=DEFAULT_API_HOST)
    client_cls = VerboseApiClient if args.verbose else openapi_client.ApiClient
    try:
        store = PackedStateStore(args.db_path, get_value_codec(args.db_value_mode), readonly=True)
        if args.search_debug:
            _search_debug.debug(
                "search: loaded store path=%s mode=%s page_entries=%s entries=%s",
                args.db_path,
                args.db_value_mode,
                store.page_entries,
                store.entry_count(),
            )
        with client_cls(configuration) as api_client:
            api = openapi_client.DefaultApi(api_client)
            if args.join_game_id is not None:
                print(f"Joining game with id: {args.join_game_id}")
            game_id = resolve_game_id(api, None if args.create_game else args.join_game_id)
            joined = join_as_player(api, game_id, args.player)
            if not joined.secret:
                print("Server did not return a player secret.", file=sys.stderr)
                raise SystemExit(1)
            try:
                game_loop(
                    api,
                    game_id,
                    args.color,
                    joined.secret,
                    store,
                    debug=args.search_debug,
                )
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
