"""Print Mühle board state from the HTTP API GET /board payload (ASCII, stdlib only)."""

from __future__ import annotations

from typing import Any, Mapping

ANSI_RESET = "\033[0m"
# White stone: dark glyph on white background; black stone: light glyph on black background.
ANSI_WHITE_STONE = "\033[30;47m"
ANSI_BLACK_STONE = "\033[97;40m"
# Diff highlight: red glyph, keep same field background as the piece (or default for empty).
ANSI_RED = "\033[31m"
ANSI_RED_ON_WHITE = "\033[31;47m"
ANSI_RED_ON_BLACK = "\033[31;40m"


def colors_from_board_payload(board: Mapping[str, Any] | None) -> dict[int, int]:
    """Parse ``board`` object with ``Fields`` / ``fields`` entries ``Index`` + ``Color``."""
    if not board:
        return {}
    raw = board.get("Fields") or board.get("fields") or []
    out: dict[int, int] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        idx = row.get("Index", row.get("index"))
        col = row.get("Color", row.get("color"))
        if idx is None or col is None:
            continue
        out[int(idx)] = int(col)
    return out


def format_board(
    colors: Mapping[int, int],
    highlight: set[int] | None = None,
) -> str:
    """Same topology as ``Board.pretty_print``.

    White stones use a white background (dark ``W``); black stones use a black background
    (bright ``B``). Indices in ``highlight`` are drawn with red glyphs and the same
    stone backgrounds where applicable.
    """
    hi = highlight or set()

    def p(i: int) -> str:
        c = colors.get(i, 0)
        sym = {0: "·", 1: "W", 2: "B"}[c]
        cell = f"{i:>2}{sym}"
        if i in hi:
            if c == 1:
                return f"{ANSI_RED_ON_WHITE}{cell}{ANSI_RESET}"
            if c == 2:
                return f"{ANSI_RED_ON_BLACK}{cell}{ANSI_RESET}"
            return f"{ANSI_RED}{cell}{ANSI_RESET}"
        if c == 1:
            return f"{ANSI_WHITE_STONE}{cell}{ANSI_RESET}"
        if c == 2:
            return f"{ANSI_BLACK_STONE}{cell}{ANSI_RESET}"
        return cell

    return (
        f"{p(0)}-----------{p(1)}-----------{p(2)}\n"
        f"|              |             |\n"
        f"|   {p(3)}-------{p(4)}-------{p(5)}  |\n"
        f"|   |          |         |   |\n"
        f"|   |   {p(6)}---{p(7)}---{p(8)}  |   |\n"
        f"|   |   |            |   |   |\n"
        f"{p(9)}-{p(10)}-{p(11)}          {p(12)}-{p(13)}-{p(14)}\n"
        f"|   |   |            |   |   |\n"
        f"|   |   {p(15)}---{p(16)}---{p(17)}  |   |\n"
        f"|   |         |          |   |\n"
        f"|   {p(18)}-------{p(19)}-------{p(20)}  |\n"
        f"|             |              |\n"
        f"{p(21)}-----------{p(22)}-----------{p(23)}"
    )


def board_diff_indices(
    prev: Mapping[int, int] | None, curr: Mapping[int, int]
) -> set[int]:
    """Field indices where occupancy changed (treat missing as empty)."""
    if prev is None:
        return set()
    return {i for i in range(24) if prev.get(i, 0) != curr.get(i, 0)}


def print_board(colors: Mapping[int, int]) -> None:
    """Print board without highlights (line-oriented / logs)."""
    print(format_board(colors, None))
