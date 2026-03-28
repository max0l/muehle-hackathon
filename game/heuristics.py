from __future__ import annotations

from game.board import (
    ADJACENCY,
    BLACK,
    EMPTY,
    MILLS,
    WHITE,
    OTHER_PLAYER,
    Position,
    apply_move,
    count_mills,
    inferred_phase,
    legal_moves,
    legal_moves_for_player,
    point_in_mill,
    terminal_winner,
)

WIN_SCORE = 100_000
REMOVE_BONUS = 250

PHASE_WEIGHTS = {
    "placing": {
        "material": 500,
        "board_presence": 40,
        "mills": 140,
        "open_twos": 45,
        "double_threats": 90,
        "mobility": 4,
        "blocked": 8,
        "closing_moves": 50,
    },
    "moving": {
        "material": 700,
        "board_presence": 10,
        "mills": 170,
        "open_twos": 50,
        "double_threats": 110,
        "mobility": 14,
        "blocked": 16,
        "closing_moves": 65,
    },
    "flying": {
        "material": 800,
        "board_presence": 0,
        "mills": 180,
        "open_twos": 55,
        "double_threats": 120,
        "mobility": 10,
        "blocked": 8,
        "closing_moves": 70,
    },
    "remove": {
        "material": 700,
        "board_presence": 10,
        "mills": 170,
        "open_twos": 50,
        "double_threats": 110,
        "mobility": 10,
        "blocked": 16,
        "closing_moves": 65,
    },
}


def _line_counts(board: tuple[int, ...], player: int) -> tuple[int, int]:
    open_twos = 0
    double_threat_points: set[int] = set()
    for line in MILLS:
        player_count = sum(1 for index in line if board[index] == player)
        empty_points = [index for index in line if board[index] == EMPTY]
        if player_count == 2 and len(empty_points) == 1:
            open_twos += 1
            double_threat_points.add(empty_points[0])
    double_threats = sum(
        1
        for point in double_threat_points
        if sum(
            1
            for line in MILLS
            if point in line
            and sum(1 for index in line if board[index] == player) == 2
            and sum(1 for index in line if board[index] == EMPTY) == 1
        )
        >= 2
    )
    return open_twos, double_threats


def _blocked_stones(position: Position, player: int) -> int:
    if inferred_phase(position, player) not in {"moving", "flying"}:
        return 0
    if inferred_phase(position, player) == "flying":
        return 0
    blocked = 0
    for point, value in enumerate(position.board):
        if value == player and all(position.board[neighbor] != EMPTY for neighbor in ADJACENCY[point]):
            blocked += 1
    return blocked


def _count_closing_moves(position: Position, player: int) -> int:
    count = 0
    for move in legal_moves_for_player(position, player):
        if move.type == "remove":
            count += 1
            continue
        simulated = Position(
            board=position.board,
            player_to_move=player,
            phase=inferred_phase(position, player),
            white_in_hand=position.white_in_hand,
            black_in_hand=position.black_in_hand,
        )
        next_position = apply_move(simulated, move)
        if next_position.phase == "remove" and next_position.player_to_move == player:
            count += 1
    return count


def _player_feature_score(position: Position, player: int, weights: dict[str, int]) -> int:
    opponent = OTHER_PLAYER[player]
    open_twos, double_threats = _line_counts(position.board, player)
    mobility = len(legal_moves_for_player(position, player))
    blocked_opponent = _blocked_stones(position, opponent)
    return (
        position.stones_remaining(player) * weights["material"]
        + position.pieces_on_board(player) * weights["board_presence"]
        + count_mills(position.board, player) * weights["mills"]
        + open_twos * weights["open_twos"]
        + double_threats * weights["double_threats"]
        + mobility * weights["mobility"]
        + blocked_opponent * weights["blocked"]
        + _count_closing_moves(position, player) * weights["closing_moves"]
    )


def heuristic_score(position: Position) -> int:
    winner = terminal_winner(position)
    if winner is not None:
        return WIN_SCORE if winner == position.player_to_move else -WIN_SCORE

    phase = inferred_phase(position)
    weights = PHASE_WEIGHTS["moving" if phase == "end" else phase]

    white_score = _player_feature_score(position, WHITE, weights)
    black_score = _player_feature_score(position, BLACK, weights)

    score = white_score - black_score
    if position.phase == "remove":
        score += REMOVE_BONUS if position.player_to_move == WHITE else -REMOVE_BONUS
    return score if position.player_to_move == WHITE else -score
