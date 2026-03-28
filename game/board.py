import dataclasses
import random
from typing import Literal

GameState = Literal["placing", "moving", "end"]

# Board layout:
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

    def random_move(self) -> Move:
        return Move(
            type="place",
            fieldIndex=random.randint(0, 23),
            toFieldIndex=None,
            removedPiece=None,
        )

    def all_moves(self, player: int) -> list[Move]:
        moves = []
        if self.state == "placing":
            for field in range(24):
                if self.board[field] == 0:
                    moves.append(
                        Move(
                            type="place",
                            fieldIndex=field,
                            toFieldIndex=None,
                            removedPiece=None,
                        )
                    )
                # todo mills
        else:
            print("not yet implemented")
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
