from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from game.board import apply_move, initial_position, is_terminal, legal_moves
from game.encoding import canonical_key, canonicalize, decode_position
from game.packed_store import PackedStateStore
from game.value_codec import ValueMode, get_value_codec


@dataclass
class GenerationResult:
    processed_frontier_states: int
    stored_states: int
    frontier_remaining: int
    stopped_because_of_limit: bool


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


def generate_database(
    output_path: str | Path,
    *,
    value_mode: ValueMode,
    max_depth: int | None,
    max_states: int | None,
    batch_size: int,
    page_entries: int,
    resume: bool,
) -> GenerationResult:
    output_path = Path(output_path)
    codec = get_value_codec(value_mode)
    store = PackedStateStore(output_path, codec, page_entries=page_entries)
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
        start_key = canonical_key(start)
        store.add_state(start_key, codec.evaluate(start, 0))
        store.enqueue(start_key, 0)

    processed = 0
    stop = False
    while True:
        if stop:
            break
        frontier_batch = store.pop_frontier_batch(batch_size)
        if not frontier_batch:
            break

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
                next_key = canonical_key(next_position)
                if not store.add_state(next_key, codec.evaluate(next_position, next_depth)):
                    continue

                store.enqueue(next_key, next_depth)
                if max_states is not None and store.entry_count() >= max_states:
                    stop = True
                    break

            if stop:
                break

    return GenerationResult(
        processed_frontier_states=processed,
        stored_states=store.entry_count(),
        frontier_remaining=store.frontier_size(),
        stopped_because_of_limit=stop,
    )


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
