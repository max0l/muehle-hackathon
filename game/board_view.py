"""Render Mühle board state from the HTTP API GET /board payload."""

from __future__ import annotations

from typing import Any, Mapping

# Outer ring: room for "23 [B]"
_CELL_OUT = 9
# Inner arms
_CELL_IN = 7
_D_LONG = "--------"
_D_MID = "-----"
_D_SHORT = "---"


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


def _slot(colors: Mapping[int, int], index: int, width: int) -> str:
    return field_cell(index, colors.get(index, 0)).ljust(width)


def _top_line(colors: Mapping[int, int]) -> str:
    w = _CELL_OUT
    return (
        _slot(colors, 0, w)
        + _D_LONG
        + _slot(colors, 1, w)
        + _D_LONG
        + _slot(colors, 2, w)
    )


def _pipe_row(width: int, columns: list[int]) -> str:
    row = [" "] * width
    for c in columns:
        if 0 <= c < width:
            row[c] = "|"
    return "".join(row)


def _bracket_line(inner: str, width: int) -> str:
    """``|`` + ``inner`` centered in ``width - 2`` + ``|``."""
    inner_w = width - 2
    if len(inner) > inner_w:
        inner = inner[:inner_w]
    body = inner.center(inner_w)
    return "|" + body + "|"


def _inner_arm(colors: Mapping[int, int], a: int, b: int, c: int, dash: str) -> str:
    wi = _CELL_IN
    return _slot(colors, a, wi) + dash + _slot(colors, b, wi) + dash + _slot(colors, c, wi)


def _slot_centers_in_bracket(inner: str, width: int, wi: int, dash_len: int) -> tuple[int, int, int]:
    """Column indices of the centers of the three slots inside ``_bracket_line(inner)``."""
    inner_w = width - 2
    offset = 1 + (inner_w - len(inner)) // 2
    c0 = offset + wi // 2
    c1 = offset + wi + dash_len + wi // 2
    c2 = offset + 2 * (wi + dash_len) + wi // 2
    return (c0, c1, c2)


def _middle_cross_line(colors: Mapping[int, int], width: int) -> str:
    """9—10—11    12—13—14 on one row (tight slots so it fits the outer width)."""
    wt = 6
    sep = "-"
    left = _slot(colors, 9, wt) + sep + _slot(colors, 10, wt) + sep + _slot(colors, 11, wt)
    right = _slot(colors, 12, wt) + sep + _slot(colors, 13, wt) + sep + _slot(colors, 14, wt)
    gap = width - len(left) - len(right)
    gap = max(1, gap)
    core = left + (" " * gap) + right
    if len(core) < width:
        return core + (" " * (width - len(core)))
    if len(core) > width:
        return core[:width]
    return core


def format_board_diagram(colors: Mapping[int, int]) -> str:
    """Standard 24-point diagram; missing indices treated as empty (0)."""
    line0 = _top_line(colors)
    width = len(line0)
    w = _CELL_OUT
    d_long = len(_D_LONG)
    # Vertical rails: left rim, middle axis, right rim (align with bracket lines)
    rail_l = 0
    rail_m = w + d_long + w // 2
    rail_r = width - 1

    lines: list[str] = [
        line0,
        _pipe_row(width, [rail_l, rail_m, rail_r]),
    ]

    inner_345 = _inner_arm(colors, 3, 4, 5, _D_MID)
    line_345 = _bracket_line(inner_345, width)
    lines.append(line_345)
    i3, i4, i5 = _slot_centers_in_bracket(inner_345, width, _CELL_IN, len(_D_MID))

    inner_678 = _inner_arm(colors, 6, 7, 8, _D_SHORT)
    line_678 = _bracket_line(inner_678, width)
    lines.append(
        _pipe_row(width, [rail_l, i3, i4, i5, rail_r]),
    )
    lines.append(line_678)

    i6, i7, i8 = _slot_centers_in_bracket(inner_678, width, _CELL_IN, len(_D_SHORT))
    lines.append(_pipe_row(width, [rail_l, i3, i6, i7, i8, i5, rail_r]))

    lines.append(_middle_cross_line(colors, width))

    lines.append(_pipe_row(width, [rail_l, i3, i6, i7, i8, i5, rail_r]))

    inner_151617 = _inner_arm(colors, 15, 16, 17, _D_SHORT)
    lines.append(_bracket_line(inner_151617, width))

    lines.append(_pipe_row(width, [rail_l, i3, i4, i5, rail_r]))

    inner_181920 = _inner_arm(colors, 18, 19, 20, _D_MID)
    lines.append(_bracket_line(inner_181920, width))

    lines.append(_pipe_row(width, [rail_l, rail_m, rail_r]))

    lines.append(
        _slot(colors, 21, w)
        + _D_LONG
        + _slot(colors, 22, w)
        + _D_LONG
        + _slot(colors, 23, w)
    )

    return "\n".join(lines)
