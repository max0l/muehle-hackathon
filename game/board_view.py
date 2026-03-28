"""Render Mühle board state from the HTTP API GET /board payload.

Line topology and dash counts follow ``Board.pretty_print`` in ``game/board.py``;
see ``BOARD_PRINT_FIELD_INDICES`` there for the field-number-only wireframe.
"""

from __future__ import annotations

from typing import Any, Mapping

# Topology and dash lengths match ``game/board.py`` → ``Board.pretty_print``.
_D_MID = 7
_D_IN = 3
_MID_INNER_GAP = 7  # spaces between 11 and 12


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


def field_cell(index: int, color: int) -> str:
    """``Color`` 0 empty, 1 white, 2 black → ``N [ ]`` / ``N [W]`` / ``N [B]``."""
    if color == 1:
        tag = "[W]"
    elif color == 2:
        tag = "[B]"
    else:
        tag = "[ ]"
    return f"{index} {tag}"


def _pad_pipe_line(line: str, target_w: int) -> str:
    """If ``line`` is ``|`` … ``|``, pad the inner part on the right to ``target_w`` (left-aligned)."""
    if len(line) >= target_w:
        return line[:target_w]
    if not (line.startswith("|") and line.endswith("|")):
        return line.ljust(target_w)
    inner = line[1:-1]
    pad = target_w - 2 - len(inner)
    if pad <= 0:
        return line.ljust(target_w)
    return "|" + inner + (" " * pad) + "|"


def format_board_diagram(colors: Mapping[int, int]) -> str:
    """Standard 24-point diagram (same topology as ``Board.pretty_print`` in ``board.py``)."""
    W = max(len(field_cell(i, c)) for i in range(24) for c in (0, 1, 2))

    def cell(i: int) -> str:
        return field_cell(i, colors.get(i, 0))

    def h(i: int, *, last_on_row: bool) -> str:
        """Pad cells that have a dash run to the right; omit trailing pad on the row's last cell."""
        c = cell(i)
        if last_on_row:
            return c
        return c.ljust(W)

    d = "-" * _D_IN
    dm = "-" * _D_MID

    # Reference width: middle row (9–14). Rightmost field has no trailing pad so lines do not end in spaces.
    line_mid = (
        f"{h(9, last_on_row=False)}{d}{h(10, last_on_row=False)}{d}{h(11, last_on_row=False)}"
        f"{' ' * _MID_INNER_GAP}"
        f"{h(12, last_on_row=False)}{d}{h(13, last_on_row=False)}{d}{h(14, last_on_row=True)}"
    )
    w = len(line_mid)

    def outer_horizontal(a: int, b: int, c: int) -> str:
        """Top/bottom row: same total width as ``line_mid``; dash split may differ per row (e.g. ``2`` vs ``23``)."""
        rem_outer = w - len(h(a, last_on_row=False)) - len(h(b, last_on_row=False)) - len(h(c, last_on_row=True))
        d_lo = rem_outer // 2
        d_hi = rem_outer - d_lo
        return (
            f"{h(a, last_on_row=False)}{'-' * d_lo}{h(b, last_on_row=False)}"
            f"{'-' * d_hi}{h(c, last_on_row=True)}"
        )

    line0 = outer_horizontal(0, 1, 2)
    line_bot = outer_horizontal(21, 22, 23)

    gap = w - 3
    g = gap // 2
    g2 = gap - g
    line_v = "|" + (" " * g) + "|" + (" " * g2) + "|"

    line_345 = _pad_pipe_line(
        f"|   {h(3, last_on_row=False)}{dm}{h(4, last_on_row=False)}{dm}{h(5, last_on_row=True)}   |",
        w,
    )
    line_4 = _pad_pipe_line("|   |       |       |   |", w)
    line_678 = _pad_pipe_line(
        f"|   |   {h(6, last_on_row=False)}{d}{h(7, last_on_row=False)}{d}{h(8, last_on_row=True)}   |   |",
        w,
    )
    line_151617 = _pad_pipe_line(
        f"|   |   {h(15, last_on_row=False)}{d}{h(16, last_on_row=False)}{d}{h(17, last_on_row=True)}   |   |",
        w,
    )
    line_181920 = _pad_pipe_line(
        f"|   {h(18, last_on_row=False)}{dm}{h(19, last_on_row=False)}{dm}{h(20, last_on_row=True)}   |",
        w,
    )

    lines = [
        line0,
        line_v,
        line_345,
        line_4,
        line_678,
        line_4,
        line_mid,
        line_4,
        line_151617,
        line_4,
        line_181920,
        line_v,
        line_bot,
    ]

    for i, ln in enumerate(lines):
        if len(ln) != w:
            raise RuntimeError(f"board_view line {i} len {len(ln)} != {w}: {ln!r}")

    return "\n".join(lines)
