from __future__ import annotations

import dataclasses
from typing import Literal

EMPTY = 0
WHITE = 1
BLACK = 2
PLAYER_VALUES = (WHITE, BLACK)
OTHER_PLAYER = {WHITE: BLACK, BLACK: WHITE}

GameState = Literal["placing", "moving", "flying", "remove", "end"]
Player = Literal[1, 2]

# Board layout (same topology as ``Board.pretty_print`` and ``board_view.format_board_diagram``):
#
# 0 ----------- 1 ----------- 2
# |             |             |
# |   3 ------- 4 ------- 5  |
# |   |         |         |  |
# |   |   6 --- 7 --- 8  |  |
# |   |   |           |  |  |
# 9 --10--11         12--13--14
# |   |   |           |  |  |
# |   |  15 ---16 ---17  |  |
# |   |         |         |  |
# |  18 -------19 ------20  |
# |             |             |
# 21 ----------22 ----------23

BOARD_PRINT_FIELD_INDICES = """\
0-----------1-----------2
|           |           |
|   3-------4-------5   |
|   |       |       |   |
|   |   6---7---8   |   |
|   |   |       |   |   |
9---10---11       12---13---14
|   |   |       |   |   |
|   |   15---16---17   |   |
|   |       |       |   |
|   18-------19-------20   |
|           |           |
21-----------22-----------23"""

ADJACENCY = [
    [1, 9],  # 0
    [0, 2, 4],  # 1
    [1, 14],  # 2
    [4, 10],  # 3
    [1, 3, 5, 7],  # 4
    [4, 13],  # 5
    [7, 11],  # 6
    [4, 6, 8],  # 7
    [7, 12],  # 8
    [0, 10, 21],  # 9
    [3, 9, 11, 18],  # 10
    [6, 10, 15],  # 11
    [8, 13, 17],  # 12
    [5, 12, 14, 20],  # 13
    [2, 13, 23],  # 14
    [11, 16],  # 15
    [15, 17, 19],  # 16
    [12, 16],  # 17
    [10, 19],  # 18
    [16, 18, 20, 22],  # 19
    [13, 19],  # 20
    [9, 22],  # 21
    [19, 21, 23],  # 22
    [14, 22],  # 23
]

MILLS = [
    # Outer square
    (0, 1, 2),
    (2, 14, 23),
    (21, 22, 23),
    (0, 9, 21),
    # Middle square
    (3, 4, 5),
    (5, 13, 20),
    (18, 19, 20),
    (3, 10, 18),
    # Inner square
    (6, 7, 8),
    (8, 12, 17),
    (15, 16, 17),
    (6, 11, 15),
    # Cross lines (connecting squares at midpoints)
    (1, 4, 7),
    (9, 10, 11),
    (12, 13, 14),
    (16, 19, 22),
]

POINT_COORDS = [
    (0, 0),
    (3, 0),
    (6, 0),
    (1, 1),
    (3, 1),
    (5, 1),
    (2, 2),
    (3, 2),
    (4, 2),
    (0, 3),
    (1, 3),
    (2, 3),
    (4, 3),
    (5, 3),
    (6, 3),
    (2, 4),
    (3, 4),
    (4, 4),
    (1, 5),
    (3, 5),
    (5, 5),
    (0, 6),
    (3, 6),
    (6, 6),
]


@dataclasses.dataclass(frozen=True)
class Move:
    type: Literal["place", "move", "remove"]
    fieldIndex: int
    toFieldIndex: int | None = None
    removedPiece: int | None = None


@dataclasses.dataclass(frozen=True)
class Position:
    board: tuple[int, ...]
    player_to_move: int = WHITE
    phase: GameState = "placing"
    white_in_hand: int = 9
    black_in_hand: int = 9

    def __post_init__(self) -> None:
        if len(self.board) != 24:
            raise ValueError("board must contain 24 points")
        if self.player_to_move not in PLAYER_VALUES:
            raise ValueError("player_to_move must be WHITE or BLACK")

    def pieces_on_board(self, player: int) -> int:
        return sum(1 for value in self.board if value == player)

    def stones_in_hand(self, player: int) -> int:
        return self.white_in_hand if player == WHITE else self.black_in_hand

    def stones_remaining(self, player: int) -> int:
        return self.pieces_on_board(player) + self.stones_in_hand(player)

    def empty_points(self) -> list[int]:
        return [index for index, value in enumerate(self.board) if value == EMPTY]


def initial_position() -> Position:
    return Position(board=(EMPTY,) * 24)


def _normalize_color(value: object) -> int:
    if isinstance(value, int) and value in {EMPTY, WHITE, BLACK}:
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"0", "empty"}:
            return EMPTY
        if lowered in {"1", "white", "w"}:
            return WHITE
        if lowered in {"2", "black", "b"}:
            return BLACK
    raise ValueError(f"Unsupported color value: {value!r}")


def _set_point(board: tuple[int, ...], index: int, value: int) -> tuple[int, ...]:
    mutable = list(board)
    mutable[index] = value
    return tuple(mutable)


def mill_lines_for_point(point: int) -> list[tuple[int, int, int]]:
    return [line for line in MILLS if point in line]


def point_in_mill(board: tuple[int, ...], player: int, point: int) -> bool:
    if board[point] != player:
        return False
    return any(all(board[index] == player for index in line) for line in mill_lines_for_point(point))


def count_mills(board: tuple[int, ...], player: int) -> int:
    return sum(1 for line in MILLS if all(board[index] == player for index in line))


def removable_points(position: Position, removing_player: int) -> list[int]:
    opponent = OTHER_PLAYER[removing_player]
    opponent_points = [index for index, value in enumerate(position.board) if value == opponent]
    outside_mills = [index for index in opponent_points if not point_in_mill(position.board, opponent, index)]
    return outside_mills or opponent_points


def inferred_phase(position: Position, player: int | None = None) -> GameState:
    player = position.player_to_move if player is None else player
    if position.phase in {"remove", "end"} and player == position.player_to_move:
        return position.phase
    if position.stones_in_hand(player) > 0:
        return "placing"
    if position.pieces_on_board(player) == 3:
        return "flying"
    return "moving"


def _raw_legal_moves_for_player(position: Position, player: int) -> list[Move]:
    if position.phase == "remove" and player == position.player_to_move:
        return [
            Move(type="remove", fieldIndex=point, removedPiece=point)
            for point in removable_points(position, player)
        ]

    phase = inferred_phase(position, player)
    empty_points = position.empty_points()
    if phase == "placing":
        return [Move(type="place", fieldIndex=point) for point in empty_points]

    own_points = [index for index, value in enumerate(position.board) if value == player]
    moves: list[Move] = []
    if phase == "moving":
        for source in own_points:
            for destination in ADJACENCY[source]:
                if position.board[destination] == EMPTY:
                    moves.append(Move(type="move", fieldIndex=source, toFieldIndex=destination))
        return moves

    for source in own_points:
        for destination in empty_points:
            moves.append(Move(type="move", fieldIndex=source, toFieldIndex=destination))
    return moves


def legal_moves_for_player(position: Position, player: int) -> list[Move]:
    if terminal_winner(position) is not None:
        return []
    return _raw_legal_moves_for_player(position, player)


def legal_moves(position: Position) -> list[Move]:
    return legal_moves_for_player(position, position.player_to_move)


def terminal_winner(position: Position) -> int | None:
    for player in PLAYER_VALUES:
        if position.stones_remaining(player) < 3:
            return OTHER_PLAYER[player]

    phase = inferred_phase(position)
    if phase in {"moving", "flying"} and not _raw_legal_moves_for_player(position, position.player_to_move):
        return OTHER_PLAYER[position.player_to_move]
    return None


def is_terminal(position: Position) -> bool:
    return terminal_winner(position) is not None or position.phase == "end"


def _next_phase_for_player(position: Position, player: int) -> GameState:
    if terminal_winner(position) is not None:
        return "end"
    if position.stones_in_hand(player) > 0:
        return "placing"
    if position.pieces_on_board(player) == 3:
        return "flying"
    return "moving"


def apply_move(position: Position, move: Move) -> Position:
    if is_terminal(position):
        raise ValueError("Cannot apply a move to a terminal position")

    player = position.player_to_move
    opponent = OTHER_PLAYER[player]
    board = list(position.board)
    white_in_hand = position.white_in_hand
    black_in_hand = position.black_in_hand
    phase = inferred_phase(position)

    if position.phase == "remove":
        target = move.removedPiece if move.removedPiece is not None else move.fieldIndex
        if move.type != "remove" or target not in removable_points(position, player):
            raise ValueError("Illegal remove move")
        board[target] = EMPTY
        next_position = Position(
            board=tuple(board),
            player_to_move=opponent,
            phase="moving",
            white_in_hand=white_in_hand,
            black_in_hand=black_in_hand,
        )
        next_phase = _next_phase_for_player(next_position, opponent)
        return Position(
            board=next_position.board,
            player_to_move=opponent,
            phase=next_phase,
            white_in_hand=white_in_hand,
            black_in_hand=black_in_hand,
        )

    if phase == "placing":
        if move.type != "place" or move.fieldIndex not in position.empty_points():
            raise ValueError("Illegal placement move")
        board[move.fieldIndex] = player
        if player == WHITE:
            white_in_hand -= 1
        else:
            black_in_hand -= 1
        formed_mill = point_in_mill(tuple(board), player, move.fieldIndex)
    else:
        if move.type != "move" or move.toFieldIndex is None:
            raise ValueError("Illegal movement move")
        if board[move.fieldIndex] != player or board[move.toFieldIndex] != EMPTY:
            raise ValueError("Illegal source or destination")
        if phase == "moving" and move.toFieldIndex not in ADJACENCY[move.fieldIndex]:
            raise ValueError("Sliding move must use adjacency")
        board[move.fieldIndex] = EMPTY
        board[move.toFieldIndex] = player
        formed_mill = point_in_mill(tuple(board), player, move.toFieldIndex)

    next_board = tuple(board)
    if formed_mill and any(value == opponent for value in next_board):
        return Position(
            board=next_board,
            player_to_move=player,
            phase="remove",
            white_in_hand=white_in_hand,
            black_in_hand=black_in_hand,
        )

    next_position = Position(
        board=next_board,
        player_to_move=opponent,
        phase="moving",
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
    )
    next_phase = _next_phase_for_player(next_position, opponent)
    return Position(
        board=next_board,
        player_to_move=opponent,
        phase=next_phase,
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
    )


class Board:
    def __init__(
        self,
        board: list[dict] | None = None,
        states: GameState = "placing",
        player_to_move: int = WHITE,
        white_in_hand: int | None = None,
        black_in_hand: int | None = None,
    ) -> None:
        points = [EMPTY] * 24
        board = [] if board is None else board
        for field in board:
            index = int(field["Index"])
            points[index] = _normalize_color(field["Color"])

        white_on_board = sum(1 for value in points if value == WHITE)
        black_on_board = sum(1 for value in points if value == BLACK)
        if white_in_hand is None:
            white_in_hand = max(0, 9 - white_on_board) if states == "placing" else 0
        if black_in_hand is None:
            black_in_hand = max(0, 9 - black_on_board) if states == "placing" else 0

        self.position = Position(
            board=tuple(points),
            player_to_move=player_to_move,
            phase=states,
            white_in_hand=white_in_hand,
            black_in_hand=black_in_hand,
        )

    @property
    def board(self) -> list[int]:
        return list(self.position.board)

    @property
    def state(self) -> GameState:
        return inferred_phase(self.position)

    def empty(self) -> None:
        self.position = initial_position()

    def _all_fields_with_state(self, field_state: Player | None) -> list[int]:
        """Find all fields occupied by the player or empty depending on the argument."""
        if field_state is None:
            value = EMPTY
        else:
            value = int(field_state)

        fields: list[int] = []
        for field in range(24):
            if self.board[field] == value:
                fields.append(field)

        return fields

    def _all_fields_outside_mill(self, player: Player) -> list[int]:
        """Find all fields occupied by the player or empty that are not part of a completed mill."""
        result = []
        for field in self._all_fields_with_state(player):
            in_mill = any(
                field in (f0, f1, f2)
                and self.board[f0] == player
                and self.board[f1] == player
                and self.board[f2] == player
                for f0, f1, f2 in MILLS
            )
            if not in_mill:
                result.append(field)
        return result

    def _forms_mill(
        self, field: int, player: Player, from_field: int | None = None
    ) -> bool:
        """Check if placing/moving player's piece to `field` completes a mill.
        `from_field` must be provided when moving so the vacated position is excluded."""
        for f0, f1, f2 in MILLS:
            if field in (f0, f1, f2):
                if all(
                    self.board[f] == player and f != from_field
                    for f in (f0, f1, f2)
                    if f != field
                ):
                    return True
        return False

    def _with_removal(self, base: Move, opponent: Player) -> list[Move]:
        """Expand a mill-forming move into one move per removable opponent piece."""
        removable = self._all_fields_outside_mill(opponent)
        if not removable:  # all opponent pieces are in mills — any may be taken
            removable = self._all_fields_with_state(opponent)
        return [dataclasses.replace(base, removedPiece=r) for r in removable]

    def all_moves(self, player: Player | None = None) -> list[Move]:
        """Iterate legal moves, expanding mill closures into concrete removals."""
        player = self.position.player_to_move if player is None else player
        opponent: Player = 2 if player == 1 else 1
        phase = inferred_phase(self.position, player)
        moves: list[Move] = []

        if phase == "remove":
            return legal_moves_for_player(self.position, player)

        if phase == "placing":
            # Allow placing stones and removing enemy stones if a mill was completed
            for field in self._all_fields_with_state(None):
                base = Move(
                    type="place", fieldIndex=field, toFieldIndex=None, removedPiece=None
                )
                if self._forms_mill(field, player):
                    moves.extend(self._with_removal(base, opponent))
                else:
                    moves.append(base)

        elif phase in {"moving", "flying"}:
            can_fly = len(self._all_fields_with_state(player)) <= 3
            empty_fields = self._all_fields_with_state(None)

            for from_field in self._all_fields_with_state(player):
                to_fields = (
                    empty_fields
                    if can_fly
                    else [f for f in ADJACENCY[from_field] if self.board[f] == 0]
                )
                for to_field in to_fields:
                    base = Move(
                        type="move",
                        fieldIndex=from_field,
                        toFieldIndex=to_field,
                        removedPiece=None,
                    )
                    if self._forms_mill(to_field, player, from_field=from_field):
                        moves.extend(self._with_removal(base, opponent))
                    else:
                        moves.append(base)

        return moves

    def pretty_print(self) -> str:
        b = self.position.board

        def p(i: int) -> str:
            return {EMPTY: "·", WHITE: "W", BLACK: "B"}[b[i]]

        return (
            f"{p(0)}-----------{p(1)}-----------{p(2)}\n"
            f"|           |           |\n"
            f"|   {p(3)}-------{p(4)}-------{p(5)}   |\n"
            f"|   |       |       |   |\n"
            f"|   |   {p(6)}---{p(7)}---{p(8)}   |   |\n"
            f"|   |   |       |   |   |\n"
            f"{p(9)}---{p(10)}---{p(11)}       {p(12)}---{p(13)}---{p(14)}\n"
            f"|   |   |       |   |   |\n"
            f"|   |   {p(15)}---{p(16)}---{p(17)}   |   |\n"
            f"|   |       |       |   |\n"
            f"|   {p(18)}-------{p(19)}-------{p(20)}   |\n"
            f"|           |           |\n"
            f"{p(21)}-----------{p(22)}-----------{p(23)}"
        )
