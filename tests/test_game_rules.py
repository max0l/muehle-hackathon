from game.board import (
    BLACK,
    WHITE,
    Move,
    Position,
    apply_move,
    legal_moves_for_player,
    removable_points,
)
from game.encoding import TRANSFORMS, canonical_key, index_position, transform_position
from game.value_codec import get_value_codec


def test_placing_mill_enters_remove_phase() -> None:
    position = Position(
        board=(
            WHITE,
            WHITE,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            BLACK,
            BLACK,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
        player_to_move=WHITE,
        phase="placing",
        white_in_hand=7,
        black_in_hand=7,
    )

    next_position = apply_move(position, Move(type="place", fieldIndex=2))

    assert next_position.phase == "remove"
    assert next_position.player_to_move == WHITE
    assert set(removable_points(next_position, WHITE)) == {9, 10}


def test_remove_switches_turn_and_phase() -> None:
    removing_position = Position(
        board=(
            WHITE,
            WHITE,
            WHITE,
            0,
            0,
            0,
            0,
            0,
            0,
            BLACK,
            BLACK,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
        player_to_move=WHITE,
        phase="remove",
        white_in_hand=6,
        black_in_hand=7,
    )

    next_position = apply_move(removing_position, Move(type="remove", fieldIndex=9, removedPiece=9))

    assert next_position.player_to_move == BLACK
    assert next_position.phase == "placing"
    assert next_position.board[9] == 0


def test_flying_moves_ignore_adjacency() -> None:
    position = Position(
        board=(
            WHITE,
            WHITE,
            WHITE,
            0,
            0,
            0,
            0,
            0,
            0,
            BLACK,
            BLACK,
            BLACK,
            BLACK,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
        player_to_move=WHITE,
        phase="moving",
        white_in_hand=0,
        black_in_hand=0,
    )

    moves = legal_moves_for_player(position, WHITE)

    assert any(move.fieldIndex == 0 and move.toFieldIndex == 23 for move in moves)
    assert len(moves) == 3 * 17


def test_canonical_key_matches_symmetry() -> None:
    position = Position(
        board=(
            WHITE,
            0,
            BLACK,
            0,
            WHITE,
            0,
            0,
            0,
            0,
            BLACK,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
        player_to_move=WHITE,
        phase="moving",
        white_in_hand=0,
        black_in_hand=0,
    )

    rotated = transform_position(position, TRANSFORMS[1])

    assert canonical_key(position) == canonical_key(rotated)


def test_index_position_matches_symmetry() -> None:
    position = Position(
        board=(
            WHITE,
            0,
            BLACK,
            0,
            WHITE,
            0,
            0,
            0,
            0,
            BLACK,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ),
        player_to_move=WHITE,
        phase="moving",
        white_in_hand=0,
        black_in_hand=0,
    )

    rotated = transform_position(position, TRANSFORMS[2])

    assert index_position(position) == index_position(rotated)


def test_value_codecs_round_trip() -> None:
    heuristic = get_value_codec("heuristic")
    wdl = get_value_codec("wdl")
    wdl_depth = get_value_codec("wdl-depth")

    assert heuristic.decode(heuristic.encode(1234)) == 1234
    assert wdl.decode(wdl.encode(-1)) == -1
    assert wdl_depth.decode(wdl_depth.encode((1, 9))) == (1, 9)
