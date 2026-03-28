import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main
from game import PackedStateStore, canonical_key, get_value_codec, initial_position
from game.board import Move, apply_move, legal_moves
from main import choose_move


class RecordingApi:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    def submit_move(
        self,
        game_id,
        action,
        secret_code,
        *,
        field_index=None,
        to_field_index=None,
    ) -> None:
        self.calls.append(
            {
                "game_id": str(game_id),
                "action": action,
                "secret_code": secret_code,
                "field_index": field_index,
                "to_field_index": to_field_index,
            }
        )


def test_packed_store_uses_metadata_page_entries(tmp_path) -> None:
    output = tmp_path / "state_db"
    heuristic = get_value_codec("heuristic")
    writer = PackedStateStore(output, heuristic, page_entries=64)
    writer.initialize_build({"generator": "test"}, reset_queue=True)
    start = initial_position()
    writer.add_state(canonical_key(start), 123)

    reader = PackedStateStore(output, heuristic, readonly=True)
    assert reader.page_entries == 64
    assert reader.lookup(start) == 123


def test_choose_move_prefers_highest_scored_successor(tmp_path) -> None:
    output = tmp_path / "state_db"
    heuristic = get_value_codec("heuristic")
    store = PackedStateStore(output, heuristic, page_entries=64)
    store.initialize_build({"generator": "test"}, reset_queue=True)

    root = initial_position()
    moves = legal_moves(root)
    first_child = apply_move(root, moves[0])
    second_child = apply_move(root, moves[1])
    store.add_state(canonical_key(first_child), 5)
    store.add_state(canonical_key(second_child), 99)

    board_state = {"Fields": []}
    selected = choose_move(store, board_state, 1, "PuttingStone")

    assert selected is not None
    move, payload = selected
    assert move == moves[1]
    assert payload == 99


def test_make_move_skips_waiting_for_players(monkeypatch) -> None:
    def unexpected_choose_move(*args, **kwargs):
        raise AssertionError("choose_move should not be called while waiting for players")

    monkeypatch.setattr(main, "choose_move", unexpected_choose_move)
    api = RecordingApi()

    selected = main.make_move(
        api,
        uuid4(),
        "secret",
        object(),  # type: ignore[arg-type]
        {"Fields": []},
        1,
        "WaitingForPlayers",
    )

    assert selected is None
    assert api.calls == []


def test_make_move_skips_finished_game(monkeypatch) -> None:
    def unexpected_choose_move(*args, **kwargs):
        raise AssertionError("choose_move should not be called after the game is over")

    monkeypatch.setattr(main, "choose_move", unexpected_choose_move)
    api = RecordingApi()

    selected = main.make_move(
        api,
        uuid4(),
        "secret",
        object(),  # type: ignore[arg-type]
        {"Fields": []},
        1,
        "WinWhite",
    )

    assert selected is None
    assert api.calls == []


def test_make_move_submits_place_for_placing_state(monkeypatch) -> None:
    selected_move = Move(type="place", fieldIndex=7)
    monkeypatch.setattr(main, "choose_move", lambda *args, **kwargs: (selected_move, 123))
    api = RecordingApi()
    game_id = uuid4()

    submitted = main.make_move(
        api,
        game_id,
        "secret",
        object(),  # type: ignore[arg-type]
        {"Fields": []},
        1,
        "PuttingStone",
    )

    assert submitted == selected_move
    assert api.calls == [
        {
            "game_id": str(game_id),
            "action": "place",
            "secret_code": "secret",
            "field_index": "7",
            "to_field_index": None,
        }
    ]


def test_make_move_submits_move_for_moving_state(monkeypatch) -> None:
    selected_move = Move(type="move", fieldIndex=3, toFieldIndex=4)
    monkeypatch.setattr(main, "choose_move", lambda *args, **kwargs: (selected_move, 456))
    api = RecordingApi()
    game_id = uuid4()

    submitted = main.make_move(
        api,
        game_id,
        "secret",
        object(),  # type: ignore[arg-type]
        {"Fields": [{"Index": 3, "Color": 1}]},
        1,
        "MovingStone",
    )

    assert submitted == selected_move
    assert api.calls == [
        {
            "game_id": str(game_id),
            "action": "move",
            "secret_code": "secret",
            "field_index": "3",
            "to_field_index": "4",
        }
    ]
