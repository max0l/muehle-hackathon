from __future__ import annotations

import hashlib
from math import comb
import struct

from game.board import POINT_COORDS, GameState, Position

BOARD_SIZE = 7

COORD_TO_INDEX = {coord: index for index, coord in enumerate(POINT_COORDS)}

PHASE_TO_CODE: dict[GameState, int] = {
    "placing": 0,
    "moving": 1,
    "flying": 2,
    "remove": 3,
    "end": 4,
}
CODE_TO_PHASE = {value: key for key, value in PHASE_TO_CODE.items()}


def _identity(x: int, y: int) -> tuple[int, int]:
    return (x, y)


def _rotate90(x: int, y: int) -> tuple[int, int]:
    return (BOARD_SIZE - 1 - y, x)


def _rotate180(x: int, y: int) -> tuple[int, int]:
    return (BOARD_SIZE - 1 - x, BOARD_SIZE - 1 - y)


def _rotate270(x: int, y: int) -> tuple[int, int]:
    return (y, BOARD_SIZE - 1 - x)


def _reflect_vertical(x: int, y: int) -> tuple[int, int]:
    return (BOARD_SIZE - 1 - x, y)


def _reflect_horizontal(x: int, y: int) -> tuple[int, int]:
    return (x, BOARD_SIZE - 1 - y)


def _reflect_main_diagonal(x: int, y: int) -> tuple[int, int]:
    return (y, x)


def _reflect_anti_diagonal(x: int, y: int) -> tuple[int, int]:
    return (BOARD_SIZE - 1 - y, BOARD_SIZE - 1 - x)


TRANSFORM_FUNCTIONS = (
    _identity,
    _rotate90,
    _rotate180,
    _rotate270,
    _reflect_vertical,
    _reflect_horizontal,
    _reflect_main_diagonal,
    _reflect_anti_diagonal,
)


def _build_transform_map(transform) -> tuple[int, ...]:
    mapping = [0] * len(POINT_COORDS)
    for old_index, (x, y) in enumerate(POINT_COORDS):
        mapping[old_index] = COORD_TO_INDEX[transform(x, y)]
    return tuple(mapping)


TRANSFORMS = tuple(_build_transform_map(transform) for transform in TRANSFORM_FUNCTIONS)


def transform_position(position: Position, mapping: tuple[int, ...]) -> Position:
    transformed = [0] * len(position.board)
    for old_index, new_index in enumerate(mapping):
        transformed[new_index] = position.board[old_index]
    return Position(
        board=tuple(transformed),
        player_to_move=position.player_to_move,
        phase=position.phase,
        white_in_hand=position.white_in_hand,
        black_in_hand=position.black_in_hand,
    )


def encode_position(position: Position) -> bytes:
    metadata = struct.pack(
        ">BBBB",
        position.player_to_move,
        PHASE_TO_CODE[position.phase],
        position.white_in_hand,
        position.black_in_hand,
    )
    return bytes(position.board) + metadata


def decode_position(data: bytes) -> Position:
    if len(data) != 28:
        raise ValueError("Position encoding must be exactly 28 bytes")
    board = tuple(data[:24])
    player_to_move, phase_code, white_in_hand, black_in_hand = struct.unpack(">BBBB", data[24:])
    return Position(
        board=board,
        player_to_move=player_to_move,
        phase=CODE_TO_PHASE[phase_code],
        white_in_hand=white_in_hand,
        black_in_hand=black_in_hand,
    )


def canonicalize(position: Position) -> Position:
    best = position
    best_key = encode_position(position)
    for mapping in TRANSFORMS[1:]:
        transformed = transform_position(position, mapping)
        candidate_key = encode_position(transformed)
        if candidate_key < best_key:
            best = transformed
            best_key = candidate_key
    return best


def canonical_key(position: Position) -> bytes:
    return encode_position(canonicalize(position))


def subspace_signature(position: Position) -> tuple[str, int, int, int, int, int, int]:
    canonical = canonicalize(position)
    white_on_board = canonical.pieces_on_board(1)
    black_on_board = canonical.pieces_on_board(2)
    return (
        canonical.phase,
        canonical.player_to_move,
        canonical.white_in_hand,
        canonical.black_in_hand,
        white_on_board,
        black_on_board,
        len(canonical.board),
    )


def subspace_id(position: Position) -> str:
    phase, player, white_in_hand, black_in_hand, white_on_board, black_on_board, board_size = subspace_signature(position)
    return (
        f"phase-{phase}_stm-{player}_wh-{white_in_hand}_bh-{black_in_hand}"
        f"_wb-{white_on_board}_bb-{black_on_board}_n-{board_size}"
    )


def _rank_combination(combination: list[int], n: int) -> int:
    rank = 0
    k = len(combination)
    previous = -1
    for index, value in enumerate(combination):
        for candidate in range(previous + 1, value):
            rank += comb(n - 1 - candidate, k - 1 - index)
        previous = value
    return rank


def index_position(position: Position) -> tuple[str, int]:
    canonical = canonicalize(position)
    white_positions = [index for index, value in enumerate(canonical.board) if value == 1]
    black_positions = [index for index, value in enumerate(canonical.board) if value == 2]

    rank_white = _rank_combination(white_positions, len(canonical.board))
    remaining_positions = [index for index in range(len(canonical.board)) if index not in set(white_positions)]
    reduced_black = [remaining_positions.index(index) for index in black_positions]
    rank_black = _rank_combination(reduced_black, len(remaining_positions))
    black_multiplier = comb(len(remaining_positions), len(black_positions))
    return subspace_id(canonical), rank_white * black_multiplier + rank_black


def page_locator(position: Position, page_entries: int) -> tuple[str, int, int]:
    subspace, index = index_position(position)
    page_id, slot = divmod(index, page_entries)
    return subspace, page_id, slot


def page_locator_from_key(position_key: bytes, page_entries: int) -> tuple[str, int, int]:
    return page_locator(decode_position(position_key), page_entries)


def owner_shard_for_page(subspace: str, page_id: int, shard_count: int) -> int:
    if shard_count <= 1:
        return 0
    key = f"{subspace}:{page_id}".encode("utf-8")
    digest = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(digest, "big") % shard_count


def owner_shard_for_position(position: Position, page_entries: int, shard_count: int) -> int:
    subspace, page_id, _slot = page_locator(position, page_entries)
    return owner_shard_for_page(subspace, page_id, shard_count)


def owner_shard_for_key(position_key: bytes, page_entries: int, shard_count: int) -> int:
    subspace, page_id, _slot = page_locator_from_key(position_key, page_entries)
    return owner_shard_for_page(subspace, page_id, shard_count)


def subspace_capacity(position: Position) -> int:
    canonical = canonicalize(position)
    white_count = canonical.pieces_on_board(1)
    black_count = canonical.pieces_on_board(2)
    return comb(len(canonical.board), white_count) * comb(len(canonical.board) - white_count, black_count)
