"""Print Mühle board state from the HTTP API GET /board payload (ASCII, stdlib only)."""

from __future__ import annotations

from typing import Any, Mapping


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


def print_board(colors: Mapping[int, int]) -> None:
    """Same topology as ``Board.pretty_print``; each point shows field index and piece (``·`` / ``W`` / ``B``)."""

    def p(i: int) -> str:
        sym = {0: "·", 1: "W", 2: "B"}[colors.get(i, 0)]
        return f"{i:>2}{sym}"

    print(
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
        f"{p(21)}-----------{p(22)}-----------{p(23)}",
    )
