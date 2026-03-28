from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from game.board import apply_move, initial_position, is_terminal, legal_moves
from game.encoding import canonicalize, decode_position, encode_position
from game.packed_store import PackedStateStore
from game.value_codec import ValueMode, get_value_codec


@dataclass
class GenerationResult:
    processed_frontier_states: int
    stored_states: int
    frontier_remaining: int
    stopped_because_of_limit: bool


@dataclass(frozen=True)
class GenerationProgress:
    processed_frontier_states: int
    stored_states: int
    frontier_remaining: int
    elapsed_seconds: float
    finished: bool = False


def _build_metadata(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "generator": "game.generate_db",
        "version": 1,
        "value_mode": args.value_mode,
        "max_depth": args.max_depth,
        "max_states": args.max_states,
        "batch_size": args.batch_size,
        "page_entries": args.page_entries,
    }


def _expand_frontier_batch(
    frontier_batch,
    *,
    codec,
    max_depth: int | None,
) -> tuple[int, list[tuple[bytes, object, int]]]:
    processed = 0
    generated: dict[bytes, tuple[object, int]] = {}
    for item in frontier_batch:
        processed += 1
        if max_depth is not None and item.depth >= max_depth:
            continue

        position = decode_position(item.position_key)
        if is_terminal(position):
            continue

        next_depth = item.depth + 1
        for move in legal_moves(position):
            next_position = canonicalize(apply_move(position, move))
            next_key = encode_position(next_position)
            if next_key in generated:
                continue
            generated[next_key] = (codec.evaluate(next_position, next_depth), next_depth)

    return processed, [(key, value, depth) for key, (value, depth) in generated.items()]


def _progress_snapshot(
    *,
    store: PackedStateStore,
    processed_frontier_states: int,
    started_at: float,
    finished: bool,
) -> GenerationProgress:
    return GenerationProgress(
        processed_frontier_states=processed_frontier_states,
        stored_states=store.entry_count(),
        frontier_remaining=store.frontier_size(),
        elapsed_seconds=time.perf_counter() - started_at,
        finished=finished,
    )


def _print_progress(progress: GenerationProgress) -> None:
    line = (
        "generation: "
        f"processed={progress.processed_frontier_states} "
        f"stored={progress.stored_states} "
        f"frontier={progress.frontier_remaining} "
        f"elapsed={progress.elapsed_seconds:.1f}s"
    )
    if progress.finished:
        print(f"\r{line}", file=sys.stderr)
        return
    print(f"\r{line}", end="", file=sys.stderr, flush=True)


def generate_database(
    output_path: str | Path,
    *,
    value_mode: ValueMode,
    max_depth: int | None,
    max_states: int | None,
    batch_size: int,
    page_entries: int,
    resume: bool,
    progress_callback: Callable[[GenerationProgress], None] | None = None,
) -> GenerationResult:
    output_path = Path(output_path)
    codec = get_value_codec(value_mode)
    store = PackedStateStore(output_path, codec, page_entries=page_entries)
    started_at = time.perf_counter()
    if store.entry_count() > 0 and not resume:
        raise RuntimeError(f"Database at {output_path} already contains states; use --resume to continue")

    metadata = _build_metadata(
        argparse.Namespace(
            value_mode=value_mode,
            max_depth=max_depth,
            max_states=max_states,
            batch_size=batch_size,
            page_entries=page_entries,
        )
    )
    store.initialize_build(metadata)

    if store.entry_count() == 0:
        start = canonicalize(initial_position())
        start_key = encode_position(start)
        inserted = store.add_states([(start_key, codec.evaluate(start, 0))], max_new_entries=1)
        if inserted and inserted[0]:
            store.enqueue_many([(start_key, 0)])

    processed = 0
    stop = False
    while True:
        if stop:
            break
        frontier_batch = store.pop_frontier_batch(batch_size)
        if not frontier_batch:
            break

        processed_batch, generated = _expand_frontier_batch(
            frontier_batch,
            codec=codec,
            max_depth=max_depth,
        )
        processed += processed_batch
        if not generated:
            continue

        remaining_slots = None
        if max_states is not None:
            remaining_slots = max(0, max_states - store.entry_count())
            if remaining_slots == 0:
                stop = True
                break

        entries_to_store = [(position_key, value) for position_key, value, _ in generated]
        inserted = store.add_states(entries_to_store, max_new_entries=remaining_slots)
        enqueued = [
            (position_key, depth)
            for (position_key, _value, depth), was_inserted in zip(generated, inserted)
            if was_inserted
        ]
        store.enqueue_many(enqueued)
        if progress_callback is not None:
            progress_callback(
                _progress_snapshot(
                    store=store,
                    processed_frontier_states=processed,
                    started_at=started_at,
                    finished=False,
                )
            )
        if max_states is not None and store.entry_count() >= max_states:
            stop = True

    result = GenerationResult(
        processed_frontier_states=processed,
        stored_states=store.entry_count(),
        frontier_remaining=store.frontier_size(),
        stopped_because_of_limit=stop,
    )
    if progress_callback is not None:
        progress_callback(
            _progress_snapshot(
                store=store,
                processed_frontier_states=processed,
                started_at=started_at,
                finished=True,
            )
        )
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate packed indexed ratings for Nine Men's Morris states")
    parser.add_argument("--output", default="state_db.packed", help="Target packed database directory")
    parser.add_argument(
        "--value-mode",
        choices=["heuristic", "wdl", "wdl-depth"],
        default="heuristic",
        help="Payload stored for each indexed state",
    )
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum BFS depth from the initial position")
    parser.add_argument("--max-states", type=int, default=None, help="Maximum number of unique states to store")
    parser.add_argument("--batch-size", type=int, default=256, help="How many frontier items to pop per transaction")
    parser.add_argument("--page-entries", type=int, default=4096, help="Entries per packed page file")
    parser.add_argument("--resume", action="store_true", help="Resume an existing packed build instead of starting fresh")
    parser.add_argument("--json", action="store_true", help="Print final stats as JSON")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    result = generate_database(
        args.output,
        value_mode=args.value_mode,
        max_depth=args.max_depth,
        max_states=args.max_states,
        batch_size=args.batch_size,
        page_entries=args.page_entries,
        resume=args.resume,
        progress_callback=None if args.json else _print_progress,
    )
    if args.json:
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return

    print(f"processed frontier states: {result.processed_frontier_states}")
    print(f"stored states: {result.stored_states}")
    print(f"frontier remaining: {result.frontier_remaining}")
    print(f"stopped because of limit: {result.stopped_because_of_limit}")


if __name__ == "__main__":
    main()
