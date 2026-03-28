from game import PackedStateStore, canonical_key, get_value_codec, initial_position
from game.board import apply_move, legal_moves
from main import choose_move


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
    selected = choose_move(store, board_state, 1, "placing")

    assert selected is not None
    move, payload = selected
    assert move == moves[1]
    assert payload == 99
