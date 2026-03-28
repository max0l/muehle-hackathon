"""Interactive REPL to drive a two-player Mühle session via the HTTP API."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import select
import sys
import threading
from typing import Any, Mapping, Optional
from uuid import UUID

import openapi_client
from openapi_client import DefaultApi
from openapi_client.rest import ApiException

from game.board_view import (
    board_diff_indices,
    colors_from_board_payload,
    format_board,
    print_board,
)
from game_client import DEFAULT_API_HOST, join_as_player

POLL_INTERVAL_SINGLE_SEC = 2.0

ALT_SCREEN_ON = "\033[?1049h"
ALT_SCREEN_OFF = "\033[?1049l"
CLEAR_AND_HOME = "\033[2J\033[H"


@dataclasses.dataclass
class Situation:
    game_state_label: str
    board: dict[int, int]
    current_color: Optional[str]
    board_error: Optional[str]


def _normalize_api_color(color: str | None) -> str | None:
    if color is None:
        return None
    return color.strip().lower()


def _normalize_board(colors: Mapping[int, int]) -> dict[int, int]:
    return {i: int(colors.get(i, 0)) for i in range(24)}


def _situation_display_key(sit: Situation) -> tuple[Any, ...]:
    """Stable key for everything the TUI shows from ``fetch_situation`` (not only the board)."""
    return (
        sit.game_state_label,
        sit.current_color,
        sit.board_error,
        tuple(sit.board[i] for i in range(24)),
    )


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
    """Returns (game_id, single_mode, player_name, our_color or None for dual).

    In single-seat mode, color is fixed: create → white, join → black.
    """
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

    # Single seat: creator plays white, joiner plays black (no manual choice).
    player_name = "white" if cj == 1 else "black"
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


def fetch_situation(
    api: DefaultApi,
    game_id: UUID,
    *,
    api_lock: Optional[threading.Lock] = None,
) -> Situation:
    lock_cm = api_lock if api_lock is not None else contextlib.nullcontext()
    with lock_cm:
        game_state = api.get_game_state(game_id)
        state_label = repr(game_state.state)
        current = api.get_current_player(game_id)
        cur = _normalize_api_color(current.color)
        board_err: Optional[str] = None
        board_norm = _normalize_board({})
        try:
            board_resp = api.get_board(game_id)
            board_obj = board_resp.board if isinstance(board_resp.board, dict) else None
            cols = colors_from_board_payload(board_obj)
            board_norm = _normalize_board(cols)
        except ApiException as exc:
            board_err = f"{exc.status} {exc.reason}"
            if exc.body:
                board_err = f"{board_err} — {exc.body}"
    return Situation(
        game_state_label=state_label,
        board=board_norm,
        current_color=cur,
        board_error=board_err,
    )


def print_situation_from(sit: Situation) -> None:
    print(f"Game state (API): {sit.game_state_label}")
    if sit.board_error:
        print(f"Board: could not load ({sit.board_error})", file=sys.stderr)
    else:
        print("Board (GET /board):")
        print_board(sit.board)
    print(f"Player to move (API): {sit.current_color!r}")


def print_situation_scroll(
    api: DefaultApi,
    game_id: UUID,
    *,
    api_lock: Optional[threading.Lock] = None,
) -> None:
    sit = fetch_situation(api, game_id, api_lock=api_lock)
    print_situation_from(sit)


def build_static_header(
    game_id: UUID,
    host: str,
    *,
    single_mode: bool,
    our_color: Optional[str],
) -> list[str]:
    lines = [
        "Mühle REPL",
        f"Game ID:   {game_id}",
        f"API host:  {host}",
    ]
    if single_mode:
        oc = our_color or "?"
        opp = "black" if oc == "white" else "white"
        lines.append(f"Mode:      Single seat — you: {oc}, opponent: {opp}")
    else:
        lines.append("Mode:      Local two-player — this client: white + black")
    return lines


def render_tui_frame(
    *,
    static_lines: list[str],
    sit: Situation,
    prev_board: Optional[Mapping[int, int]],
    help_text: str,
    notice: str = "",
) -> None:
    hi = board_diff_indices(prev_board, sit.board)
    rows: list[str] = [CLEAR_AND_HOME]
    rows.append("─" * 42)
    rows.extend(static_lines)
    rows.append("─" * 42)
    rows.append(f"Game state: {sit.game_state_label}")
    cc = sit.current_color or "?"
    rows.append(f"Turn:       {cc!r}")
    if notice:
        rows.append(notice)
    rows.append("")
    if sit.board_error:
        rows.append(f"Board: (error) {sit.board_error}")
    else:
        rows.append("Board:")
        rows.extend(format_board(sit.board, hi).split("\n"))
    rows.append("")
    rows.extend(help_text.split("\n"))
    rows.append(
        "Tip: red marks fields that changed since the previous view "
        "(e.g. the opponent's last move).",
    )
    rows.append("")
    rows.append("muehle> ")
    sys.stdout.write("\n".join(rows))
    sys.stdout.flush()


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
    """Background poll (non-TUI): when it becomes our turn, print board/state."""
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
                        sit_poll = fetch_situation(api, game_id, api_lock=None)
                    print_situation_from(sit_poll)
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
    host: str,
    secrets: Optional[dict[str, str]],
    single_secret: Optional[str],
    single_mode: bool,
    our_color: Optional[str] = None,
) -> None:
    api_lock: Optional[threading.Lock] = threading.Lock() if single_mode else None
    stop_poll = threading.Event()
    poll_thread: Optional[threading.Thread] = None
    help_text = repl_move_help(single_mode)

    use_tui = sys.stdout.isatty() and sys.stdin.isatty()
    poll_fetch = (
        use_tui
        and single_mode
        and bool(our_color)
        and sys.platform != "win32"
    )

    if single_mode and our_color and not poll_fetch:
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

    static_header = build_static_header(
        game_id,
        host,
        single_mode=single_mode,
        our_color=our_color,
    )

    def lock_ctx():
        return api_lock if api_lock is not None else contextlib.nullcontext()

    try:
        if use_tui:
            sys.stdout.write(ALT_SCREEN_ON)
            sys.stdout.flush()

        prev_board: Optional[dict[int, int]] = None
        last_rendered_sit: Optional[Situation] = None

        def paint(
            sit: Situation,
            before: Optional[dict[int, int]],
            notice: str = "",
            *,
            show_help: bool,
        ) -> None:
            nonlocal prev_board, last_rendered_sit
            if use_tui:
                render_tui_frame(
                    static_lines=static_header,
                    sit=sit,
                    prev_board=before,
                    help_text=help_text,
                    notice=notice,
                )
            else:
                print_situation_from(sit)
                if show_help:
                    print(help_text)
            prev_board = dict(sit.board)
            last_rendered_sit = sit

        with lock_ctx():
            sit0 = fetch_situation(api, game_id, api_lock=None)
        paint(sit0, None, "", show_help=True)

        while True:
            line = ""
            input_interrupted = False
            while True:
                try:
                    if use_tui and poll_fetch:
                        ready, _, _ = select.select(
                            [sys.stdin],
                            [],
                            [],
                            POLL_INTERVAL_SINGLE_SEC,
                        )
                        if not ready:
                            with lock_ctx():
                                sit_idle = fetch_situation(api, game_id, api_lock=None)
                            if (
                                last_rendered_sit is not None
                                and _situation_display_key(sit_idle)
                                == _situation_display_key(last_rendered_sit)
                            ):
                                continue
                            notice = ""
                            if (
                                our_color
                                and sit_idle.current_color == our_color
                                and prev_board is not None
                            ):
                                notice = "You are on the move."
                            paint(sit_idle, prev_board, notice, show_help=True)
                            continue
                    line = (
                        sys.stdin.readline()
                        if use_tui
                        else input("muehle> ")
                    )
                    if use_tui and line == "":
                        input_interrupted = True
                    break
                except (EOFError, KeyboardInterrupt):
                    print()
                    input_interrupted = True
                    break
            if input_interrupted:
                break

            raw = line.strip()
            if not raw:
                continue
            try:
                parsed = parse_command(raw, single_mode=single_mode)
            except ValueError as exc:
                print(f"Parse error: {exc}", file=sys.stderr)
                continue
            if parsed is None:
                continue
            if parsed[0] == "quit":
                break
            if parsed[0] == "help":
                if use_tui:
                    with lock_ctx():
                        sit = fetch_situation(api, game_id, api_lock=None)
                    paint(sit, prev_board, "", show_help=True)
                else:
                    print(help_text)
                continue
            if parsed[0] == "refresh":
                with lock_ctx():
                    sit = fetch_situation(api, game_id, api_lock=None)
                if use_tui:
                    paint(sit, prev_board, "", show_help=True)
                else:
                    print_situation_from(sit)
                    prev_board = dict(sit.board)
                    last_rendered_sit = sit
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
            with lock_ctx():
                sit = fetch_situation(api, game_id, api_lock=None)
            paint(sit, prev_board, "", show_help=use_tui)
    finally:
        stop_poll.set()
        if poll_thread is not None:
            poll_thread.join(timeout=POLL_INTERVAL_SINGLE_SEC + 1.0)
        if use_tui:
            sys.stdout.write(ALT_SCREEN_OFF)
            sys.stdout.flush()


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
                    host=host,
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
                    host=host,
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
