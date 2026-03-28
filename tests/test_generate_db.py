from game.generate_db import generate_database
from game.board import initial_position
from game.packed_store import PackedStateStore
from game.value_codec import get_value_codec


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
