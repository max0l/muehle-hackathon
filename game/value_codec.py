from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Literal

from game.board import Position, terminal_winner
from game.heuristics import heuristic_score

ValueMode = Literal["heuristic", "wdl", "wdl-depth"]


def classify_wdl(position: Position) -> int:
    winner = terminal_winner(position)
    if winner is not None:
        return 1 if winner == position.player_to_move else -1
    score = heuristic_score(position)
    if score > 0:
        return 1
    if score < 0:
        return -1
    return 0


@dataclass(frozen=True)
class ValueCodec:
    mode: ValueMode
    payload_size: int

    def encode(self, value: object) -> bytes:
        raise NotImplementedError

    def decode(self, data: bytes) -> object:
        raise NotImplementedError

    def evaluate(self, position: Position, depth: int) -> object:
        raise NotImplementedError


@dataclass(frozen=True)
class HeuristicCodec(ValueCodec):
    mode: ValueMode = "heuristic"
    payload_size: int = 4

    def encode(self, value: object) -> bytes:
        return struct.pack(">i", int(value))

    def decode(self, data: bytes) -> int:
        return struct.unpack(">i", data)[0]

    def evaluate(self, position: Position, depth: int) -> int:
        return heuristic_score(position)


@dataclass(frozen=True)
class WdlCodec(ValueCodec):
    mode: ValueMode = "wdl"
    payload_size: int = 1

    def encode(self, value: object) -> bytes:
        return struct.pack(">b", int(value))

    def decode(self, data: bytes) -> int:
        return struct.unpack(">b", data)[0]

    def evaluate(self, position: Position, depth: int) -> int:
        return classify_wdl(position)


@dataclass(frozen=True)
class WdlDepthCodec(ValueCodec):
    mode: ValueMode = "wdl-depth"
    payload_size: int = 5

    def encode(self, value: object) -> bytes:
        wdl, ply_depth = value  # type: ignore[misc]
        return struct.pack(">bI", int(wdl), int(ply_depth))

    def decode(self, data: bytes) -> tuple[int, int]:
        return struct.unpack(">bI", data)

    def evaluate(self, position: Position, depth: int) -> tuple[int, int]:
        return (classify_wdl(position), depth)


def get_value_codec(mode: ValueMode) -> ValueCodec:
    if mode == "heuristic":
        return HeuristicCodec()
    if mode == "wdl":
        return WdlCodec()
    if mode == "wdl-depth":
        return WdlDepthCodec()
    raise ValueError(f"Unsupported value mode: {mode}")
