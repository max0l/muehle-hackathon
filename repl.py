"""Interactive REPL to drive a two-player Mühle session via the HTTP API."""

from __future__ import annotations

import argparse
import sys
from typing import Optional
from uuid import UUID

import openapi_client
from openapi_client import DefaultApi
from openapi_client.rest import ApiException

from game.board_view import colors_from_board_payload, format_board_diagram
from game_client import DEFAULT_API_HOST, join_as_player

MOVE_HELP = (
    "Commands:  <white|black> place <field>  |  "
    "<white|black> move <from> <to>  |  "
    "<white|black> remove <field>\n"
    "Also:  help  |  quit"
)


def print_situation(api: DefaultApi, game_id: UUID) -> None:
    game_state = api.get_game_state(game_id)
    print(f"Game state (API): {game_state.state!r}")
    try:
        board_resp = api.get_board(game_id)
        board_obj = board_resp.board if isinstance(board_resp.board, dict) else None
        colors = colors_from_board_payload(board_obj)
        print("Board (GET /board):")
        print(format_board_diagram(colors))
    except ApiException as exc:
        print(f"Board: could not load ({exc.status} {exc.reason})", file=sys.stderr)
        if exc.body:
            print(exc.body, file=sys.stderr)
    current = api.get_current_player(game_id)
    print(f"Player to move (API): {current.color!r}")


def parse_command(line: str) -> Optional[tuple[str, ...]]:
    parts = line.strip().split()
    if not parts:
        return None
    head = parts[0].lower()
    if head in ("quit", "exit"):
        return ("quit",)
    if head == "help":
        return ("help",)
    if len(parts) < 3:
        raise ValueError("expected: <white|black> <place|move|remove> …")
    color, action = parts[0].lower(), parts[1].lower()
    if color not in ("white", "black"):
        raise ValueError("first token must be white or black")
    if action not in ("place", "move", "remove"):
        raise ValueError("second token must be place, move, or remove")
    if action == "move":
        if len(parts) != 4:
            raise ValueError("move needs: <color> move <from_field> <to_field>")
        return (color, action, parts[2], parts[3])
    if len(parts) != 3:
        raise ValueError(f"{action} needs exactly one field index")
    return (color, action, parts[2], "")


def run_submit_move(
    api: DefaultApi,
    game_id: UUID,
    secrets: dict[str, str],
    parsed: tuple[str, ...],
) -> None:
    color, action, a, b = parsed  # b is "" for non-move
    secret = secrets[color]
    if action == "move":
        api.submit_move(
            game_id,
            action,
            secret,
            field_index=a,
            to_field_index=b,
        )
    else:
        api.submit_move(game_id, action, secret, field_index=a)


def run_repl_session(api: DefaultApi, game_id: UUID, secrets: dict[str, str]) -> None:
    print(f"Game id: {game_id}")
    print_situation(api, game_id)
    print(MOVE_HELP)
    while True:
        try:
            line = input("muehle> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            parsed = parse_command(line)
        except ValueError as exc:
            print(f"Parse error: {exc}", file=sys.stderr)
            continue
        if parsed is None:
            continue
        if parsed[0] == "quit":
            break
        if parsed[0] == "help":
            print(MOVE_HELP)
            continue
        try:
            run_submit_move(api, game_id, secrets, parsed)
        except ApiException as exc:
            print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
            if exc.body:
                print(exc.body, file=sys.stderr)
            continue
        print_situation(api, game_id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a game, join white and black, then enter moves in a REPL.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_API_HOST,
        help=f"API base URL (default: {DEFAULT_API_HOST!r})",
    )
    args = parser.parse_args()

    configuration = openapi_client.Configuration(host=args.host)
    try:
        with openapi_client.ApiClient(configuration) as api_client:
            api = openapi_client.DefaultApi(api_client)
            created = api.create_game()
            game_id = created.id
            white = join_as_player(api, game_id, "white")
            black = join_as_player(api, game_id, "black")
            if not white.secret or not black.secret:
                print("Server did not return secrets for both players.", file=sys.stderr)
                raise SystemExit(1)
            secrets = {"white": white.secret, "black": black.secret}
            run_repl_session(api, game_id, secrets)
    except ApiException as exc:
        print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
        if exc.body:
            print(exc.body, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
