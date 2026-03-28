from game.generate_db import generate_database
from game.board import apply_move, initial_position, legal_moves
from game.encoding import canonical_key
from game.packed_store import PackedStateStore
from game.value_codec import get_value_codec


def test_packed_store_batch_add_and_enqueue_many(tmp_path) -> None:
    output = tmp_path / "state_db_batch"
    heuristic = get_value_codec("heuristic")
    store = PackedStateStore(output, heuristic, page_entries=64)
    store.initialize_build({"generator": "test"}, reset_queue=True)

    root = initial_position()
    moves = legal_moves(root)
    first_child = apply_move(root, moves[0])
    second_child = apply_move(root, moves[1])
    first_key = canonical_key(first_child)
    second_key = canonical_key(second_child)

    inserted = store.add_states(
        [
            (first_key, 5),
            (second_key, 9),
            (first_key, 5),
        ]
    )

    assert inserted == [True, True, False]
    assert store.entry_count() == 2

    start_tail = store.enqueue_many([(first_key, 1), (second_key, 1)])

    assert start_tail == 0
    assert store.frontier_size() == 2
    assert store.lookup(first_child) == 5
    assert store.lookup(second_child) == 9

    frontier = store.pop_frontier_batch(8)

    assert [(item.depth, item.position_key) for item in frontier] == [
        (1, first_key),
        (1, second_key),
    ]
    assert store.frontier_size() == 0


def test_generate_database_writes_scores(tmp_path) -> None:
    output = tmp_path / "state_db"

    result = generate_database(
        output,
        value_mode="heuristic",
        max_depth=1,
        max_states=50,
        batch_size=8,
        page_entries=64,
        resume=False,
    )

    assert result.stored_states > 1
    store = PackedStateStore(output, get_value_codec("heuristic"), page_entries=64)
    assert store.entry_count() == result.stored_states
    assert store.get_metadata()["generator"] == "game.generate_db"
    assert store.lookup(initial_position()) is not None


def test_generate_database_resume_continues_work(tmp_path) -> None:
    output = tmp_path / "state_db_resume"

    first = generate_database(
        output,
        value_mode="wdl-depth",
        max_depth=3,
        max_states=5,
        batch_size=4,
        page_entries=32,
        resume=False,
    )
    second = generate_database(
        output,
        value_mode="wdl-depth",
        max_depth=3,
        max_states=10,
        batch_size=4,
        page_entries=32,
        resume=True,
    )

    assert first.stopped_because_of_limit is True
    assert second.stored_states > first.stored_states


def test_generate_database_batch_size_preserves_small_run_results(tmp_path) -> None:
    output_a = tmp_path / "state_db_a"
    output_b = tmp_path / "state_db_b"

    result_a = generate_database(
        output_a,
        value_mode="heuristic",
        max_depth=2,
        max_states=500,
        batch_size=1,
        page_entries=64,
        resume=False,
    )
    result_b = generate_database(
        output_b,
        value_mode="heuristic",
        max_depth=2,
        max_states=500,
        batch_size=16,
        page_entries=64,
        resume=False,
    )

    store_a = PackedStateStore(output_a, get_value_codec("heuristic"), page_entries=64)
    store_b = PackedStateStore(output_b, get_value_codec("heuristic"), page_entries=64)
    root = initial_position()
    first_layer = [apply_move(root, move) for move in legal_moves(root)[:4]]

    assert result_a.stored_states == result_b.stored_states
    assert result_a.frontier_remaining == result_b.frontier_remaining
    assert store_a.lookup(root) == store_b.lookup(root)
    for position in first_layer:
        assert store_a.lookup(position) == store_b.lookup(position)


def test_generate_database_reports_progress(tmp_path) -> None:
    output = tmp_path / "state_db_progress"
    snapshots = []

    result = generate_database(
        output,
        value_mode="heuristic",
        max_depth=2,
        max_states=50,
        batch_size=8,
        page_entries=64,
        resume=False,
        progress_callback=snapshots.append,
    )

    assert snapshots
    assert snapshots[-1].finished is True
    assert snapshots[-1].processed_frontier_states == result.processed_frontier_states
    assert snapshots[-1].stored_states == result.stored_states
    assert snapshots[-1].frontier_remaining == result.frontier_remaining
