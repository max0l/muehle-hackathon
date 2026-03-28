"""Interactive REPL to drive a two-player Mühle session via the HTTP API."""

from __future__ import annotations

import argparse
import contextlib
import sys
import threading
from typing import Any, Optional
from uuid import UUID

import openapi_client
from openapi_client import DefaultApi
from openapi_client.rest import ApiException

from game.board_view import colors_from_board_payload, print_board
from game_client import DEFAULT_API_HOST, join_as_player

POLL_INTERVAL_SINGLE_SEC = 2.0


def _normalize_api_color(color: str | None) -> str | None:
    if color is None:
        return None
    return color.strip().lower()


def infer_our_color_from_player_name(player_name: str) -> Optional[str]:
    """Map join name to API color for single-mode polling (white/black)."""
    n = player_name.strip().lower()
    if n in ("white", "w", "1"):
        return "white"
    if n in ("black", "b", "2"):
        return "black"
    return None


def _prompt_nonempty(prompt: str) -> str:
    while True:
        line = input(prompt).strip()
        if line:
            return line
        print("Please enter a non-empty value.", file=sys.stderr)


def _prompt_int_choice(prompt: str, valid: set[int]) -> int:
    while True:
        raw = _prompt_nonempty(prompt)
        try:
            v = int(raw)
        except ValueError:
            print(f"Enter one of: {', '.join(str(x) for x in sorted(valid))}", file=sys.stderr)
            continue
        if v in valid:
            return v
        print(f"Enter one of: {', '.join(str(x) for x in sorted(valid))}", file=sys.stderr)


def run_interactive_wizard(host: str) -> tuple[UUID, bool, str, Optional[str]]:
    """Returns (game_id, single_mode, player_name_for_join, our_color or None for dual)."""
    print("Mühle REPL — interactive setup\n")
    mode = _prompt_int_choice(
        "Play mode — 1 = both players on this machine (local two-player), "
        "2 = single seat (play against another client): ",
        {1, 2},
    )
    single_mode = mode == 2

    cj = _prompt_int_choice(
        "Game — 1 = create a new game, 2 = join an existing game: ",
        {1, 2},
    )
    if cj == 1:
        configuration = openapi_client.Configuration(host=host)
        with openapi_client.ApiClient(configuration) as api_client:
            api = openapi_client.DefaultApi(api_client)
            created = api.create_game()
            game_id = created.id
        print(f"\nNew game — share this id:\n  {game_id}\n")
    else:
        raw_id = _prompt_nonempty("Enter game id (UUID): ")
        try:
            game_id = UUID(raw_id)
        except ValueError as exc:
            raise SystemExit(f"Invalid UUID: {raw_id}") from exc
        print(
            "\nJoining existing game — share this id so others can join:\n"
            f"  {game_id}\n",
        )

    if not single_mode:
        return game_id, False, "", None

    seat = _prompt_int_choice(
        "Your seat — 1 = White, 2 = Black: ",
        {1, 2},
    )
    player_name = "white" if seat == 1 else "black"
    return game_id, True, player_name, player_name


def repl_move_help(single_mode: bool) -> str:
    common = "Also:  refresh  |  help  |  quit"
    if single_mode:
        return (
            "Commands:  place <field>  |  move <from> <to>  |  remove <field>\n" + common
        )
    return (
        "Commands:  <white|black> place <field>  |  "
        "<white|black> move <from> <to>  |  "
        "<white|black> remove <field>\n"
        + common
    )


def print_situation(
    api: DefaultApi,
    game_id: UUID,
    *,
    api_lock: Optional[threading.Lock] = None,
) -> None:
    lock_cm = api_lock if api_lock is not None else contextlib.nullcontext()
    with lock_cm:
        game_state = api.get_game_state(game_id)
        print(f"Game state (API): {game_state.state!r}")
        try:
            board_resp = api.get_board(game_id)
            board_obj = board_resp.board if isinstance(board_resp.board, dict) else None
            colors = colors_from_board_payload(board_obj)
            print("Board (GET /board):")
            print_board(colors)
        except ApiException as exc:
            print(f"Board: could not load ({exc.status} {exc.reason})", file=sys.stderr)
            if exc.body:
                print(exc.body, file=sys.stderr)
        current = api.get_current_player(game_id)
        print(f"Player to move (API): {current.color!r}")


def parse_command(line: str, *, single_mode: bool) -> Optional[tuple[Any, ...]]:
    parts = line.strip().split()
    if not parts:
        return None
    head = parts[0].lower()
    if head in ("quit", "exit"):
        return ("quit",)
    if head == "help":
        return ("help",)
    if head == "refresh":
        return ("refresh",)

    if single_mode:
        if len(parts) < 2:
            raise ValueError("expected: <place|move|remove> …")
        action = parts[0].lower()
        if action not in ("place", "move", "remove"):
            raise ValueError("first token must be place, move, or remove")
        if action == "move":
            if len(parts) != 3:
                raise ValueError("move needs: move <from_field> <to_field>")
            return ("go", None, action, parts[1], parts[2])
        if len(parts) != 2:
            raise ValueError(f"{action} needs exactly one field index")
        return ("go", None, action, parts[1], "")

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
        return ("go", color, action, parts[2], parts[3])
    if len(parts) != 3:
        raise ValueError(f"{action} needs exactly one field index")
    return ("go", color, action, parts[2], "")


def run_submit_move(
    api: DefaultApi,
    game_id: UUID,
    parsed: tuple[Any, ...],
    *,
    secrets: Optional[dict[str, str]],
    single_secret: Optional[str],
    api_lock: Optional[threading.Lock] = None,
) -> None:
    _, color, action, a, b = parsed
    if color is None:
        if not single_secret:
            raise RuntimeError("single-player secret missing")
        secret = single_secret
    else:
        if not secrets or color not in secrets:
            raise RuntimeError("dual-player secrets missing")
        secret = secrets[color]
    lock_cm = api_lock if api_lock is not None else contextlib.nullcontext()
    with lock_cm:
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


def _poll_current_player_loop(
    api: DefaultApi,
    game_id: UUID,
    our_color: str,
    api_lock: threading.Lock,
    stop: threading.Event,
    *,
    initially_our_turn: bool,
) -> None:
    """Background poll: when it becomes our turn, print board/state and prompt."""
    notified = initially_our_turn
    while True:
        if stop.wait(timeout=POLL_INTERVAL_SINGLE_SEC):
            break
        try:
            with api_lock:
                cur = api.get_current_player(game_id)
            c = _normalize_api_color(cur.color)
            is_us = c == our_color
            if is_us:
                if not notified:
                    with api_lock:
                        print_situation(api, game_id, api_lock=None)
                    print("You are on the move:", flush=True)
                    notified = True
            else:
                notified = False
        except ApiException:
            continue


def run_repl_session(
    api: DefaultApi,
    game_id: UUID,
    *,
    secrets: Optional[dict[str, str]],
    single_secret: Optional[str],
    single_mode: bool,
    our_color: Optional[str] = None,
) -> None:
    api_lock: Optional[threading.Lock] = threading.Lock() if single_mode else None
    stop_poll = threading.Event()
    poll_thread: Optional[threading.Thread] = None

    if single_mode and our_color:
        assert api_lock is not None
        with api_lock:
            cur = api.get_current_player(game_id)
        initially_ours = _normalize_api_color(cur.color) == our_color
        poll_thread = threading.Thread(
            target=_poll_current_player_loop,
            args=(api, game_id, our_color, api_lock, stop_poll),
            kwargs={"initially_our_turn": initially_ours},
            daemon=True,
        )
        poll_thread.start()

    print_situation(api, game_id, api_lock=api_lock)
    help_text = repl_move_help(single_mode)
    print(help_text)
    try:
        while True:
            try:
                line = input("muehle> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            try:
                parsed = parse_command(line, single_mode=single_mode)
            except ValueError as exc:
                print(f"Parse error: {exc}", file=sys.stderr)
                continue
            if parsed is None:
                continue
            if parsed[0] == "quit":
                break
            if parsed[0] == "help":
                print(help_text)
                continue
            if parsed[0] == "refresh":
                print_situation(api, game_id, api_lock=api_lock)
                continue
            try:
                run_submit_move(
                    api,
                    game_id,
                    parsed,
                    secrets=secrets,
                    single_secret=single_secret,
                    api_lock=api_lock,
                )
            except ApiException as exc:
                print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
                if exc.body:
                    print(exc.body, file=sys.stderr)
                continue
            print_situation(api, game_id, api_lock=api_lock)
    finally:
        stop_poll.set()
        if poll_thread is not None:
            poll_thread.join(timeout=POLL_INTERVAL_SINGLE_SEC + 1.0)


def main() -> None:
    interactive = len(sys.argv) == 1

    parser = argparse.ArgumentParser(
        description=(
            "Mühle REPL: join a game locally (two seats) or alone (--single) for cross-client play. "
            "Run with no arguments for an interactive setup."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_API_HOST,
        help=f"API base URL (default: {DEFAULT_API_HOST!r})",
    )
    parser.add_argument(
        "--game-id",
        type=UUID,
        default=None,
        metavar="UUID",
        help="Use an existing game; do not create a new one. Id is printed so others can join.",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Register only this client as one player; use simplified commands (no white/black).",
    )
    parser.add_argument(
        "--player",
        default="white",
        metavar="NAME",
        help='Player name when using --single (default: "white"). Use white/black for turn notifications.',
    )
    if not interactive:
        args = parser.parse_args()
        host = args.host
        game_id_arg = args.game_id
        single_mode = args.single
        player_name_cli = args.player
        our_color_interactive: Optional[str] = None
    else:
        host = DEFAULT_API_HOST
        try:
            game_id_arg, single_mode, player_name_cli, our_color_interactive = (
                run_interactive_wizard(host)
            )
        except ApiException as exc:
            print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
            if exc.body:
                print(exc.body, file=sys.stderr)
            raise SystemExit(1) from exc

    configuration = openapi_client.Configuration(host=host)
    try:
        with openapi_client.ApiClient(configuration) as api_client:
            api = openapi_client.DefaultApi(api_client)
            if interactive:
                game_id = game_id_arg
            elif game_id_arg is not None:
                game_id = game_id_arg
                print(
                    "Joining an existing game — share this id so other players can join:\n"
                    f"  {game_id}\n",
                )
            else:
                created = api.create_game()
                game_id = created.id
                print(
                    "New game — share this id so other players can join:\n"
                    f"  {game_id}\n",
                )

            if single_mode:
                joined = join_as_player(api, game_id, player_name_cli)
                if not joined.secret:
                    print("Server did not return a player secret.", file=sys.stderr)
                    raise SystemExit(1)
                our_color = (
                    our_color_interactive
                    if interactive
                    else infer_our_color_from_player_name(player_name_cli)
                )
                run_repl_session(
                    api,
                    game_id,
                    secrets=None,
                    single_secret=joined.secret,
                    single_mode=True,
                    our_color=our_color,
                )
            else:
                white = join_as_player(api, game_id, "white")
                black = join_as_player(api, game_id, "black")
                if not white.secret or not black.secret:
                    print(
                        "Server did not return secrets for both players.",
                        file=sys.stderr,
                    )
                    raise SystemExit(1)
                run_repl_session(
                    api,
                    game_id,
                    secrets={"white": white.secret, "black": black.secret},
                    single_secret=None,
                    single_mode=False,
                    our_color=None,
                )
    except ApiException as exc:
        print(f"API error {exc.status}: {exc.reason}", file=sys.stderr)
        if exc.body:
            print(exc.body, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
