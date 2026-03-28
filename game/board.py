import dataclasses
from typing import Literal

# TODO update with real values
GameState = Literal["placing", "moving"]
Player = Literal[1, 2]

# Board layout (same topology as ``Board.pretty_print`` and ``board_view.print_board``):
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


@dataclasses.dataclass
class Move:
    type: Literal["place", "move", "remove"]
    fieldIndex: int
    toFieldIndex: int | None
    removedPiece: int | None


class Board:
    def __init__(self, board: list[dict], states: GameState):
        self.board = [0] * 24
        for field in board:
            index = field["Index"]
            color = field["Color"]

            self.board[index] = color
        self.state = states

    def empty(self):
        self.board = [0] * 24
        self.state: GameState = "placing"

    def _all_fields_with_state(self, field_state: Player | None) -> list[int]:
        """Find all fields occupied by the player or empty depending on the argument."""
        if field_state is None:
            value = 0
        else:
            value = int(field_state)

        fields = list()
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

    def all_moves(self, player: Player) -> list[Move]:
        """Iterate all legal moves"""
        opponent: Player = 2 if player == 1 else 1
        moves = []

        if self.state == "placing":
            # Allow placing stones and removing enemy stones if a mill was completed
            for field in self._all_fields_with_state(None):
                base = Move(
                    type="place", fieldIndex=field, toFieldIndex=None, removedPiece=None
                )
                if self._forms_mill(field, player):
                    moves.extend(self._with_removal(base, opponent))
                else:
                    moves.append(base)

        elif self.state == "moving":
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
        b = self.board

        def p(i):
            return {0: "·", 1: "W", 2: "B"}[b[i]]

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
