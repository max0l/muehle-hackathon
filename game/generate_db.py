from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from game.board import apply_move, initial_position, is_terminal, legal_moves
from game.encoding import canonicalize, decode_position, encode_position, owner_shard_for_key, owner_shard_for_position
from game.packed_store import FORMAT_VERSION_V2, META_FILE, SHARDS_DIR, PackedStateStore
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


@dataclass(frozen=True)
class ShardBatchResult:
    shard_id: int
    processed_frontier_states: int
    inserted_states: int
    outbound_entries: dict[int, list[tuple[bytes, int]]]
    limit_reached: bool


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


def _root_metadata_path(output_path: Path) -> Path:
    return output_path / META_FILE


def _shard_store_path(output_path: Path, shard_id: int) -> Path:
    return output_path / SHARDS_DIR / f"{shard_id:04d}"


def _build_root_store_metadata(
    build_info: dict[str, Any],
    *,
    codec_mode: str,
    payload_size: int,
    page_entries: int,
    shard_count: int,
    entry_count: int = 0,
    frontier_size: int = 0,
) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION_V2,
        "build_info": build_info,
        "entry_count": entry_count,
        "frontier_size": frontier_size,
        "codec_mode": codec_mode,
        "payload_size": payload_size,
        "page_entries": page_entries,
        "shard_count": shard_count,
    }


def _write_root_store_metadata(output_path: Path, metadata: dict[str, Any]) -> None:
    _root_metadata_path(output_path).write_text(json.dumps(metadata, indent=2, sort_keys=True))


def _load_root_store_metadata(output_path: Path) -> dict[str, Any] | None:
    metadata_path = _root_metadata_path(output_path)
    if not metadata_path.exists():
        return None
    return json.loads(metadata_path.read_text())


def _initialize_sharded_stores(
    output_path: Path,
    *,
    build_info: dict[str, Any],
    value_mode: ValueMode,
    page_entries: int,
    shard_count: int,
    resume: bool,
) -> None:
    codec = get_value_codec(value_mode)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / SHARDS_DIR).mkdir(parents=True, exist_ok=True)
    root_metadata = _build_root_store_metadata(
        build_info,
        codec_mode=codec.mode,
        payload_size=codec.payload_size,
        page_entries=page_entries,
        shard_count=shard_count,
    )
    if not resume or _load_root_store_metadata(output_path) is None:
        _write_root_store_metadata(output_path, root_metadata)
    for shard_id in range(shard_count):
        shard_store = PackedStateStore(_shard_store_path(output_path, shard_id), codec, page_entries=page_entries)
        shard_store.initialize_build(
            {
                **build_info,
                "format_version": FORMAT_VERSION_V2,
                "shard_count": shard_count,
                "shard_id": shard_id,
            },
            reset_queue=not resume,
        )
        shard_store.metadata["format_version"] = FORMAT_VERSION_V2
        shard_store.metadata["shard_count"] = shard_count
        shard_store.metadata["shard_id"] = shard_id
        shard_store.flush()
        shard_store.close()


def _summarize_sharded_stores(
    output_path: Path,
    *,
    value_mode: ValueMode,
    page_entries: int,
    shard_count: int,
) -> tuple[int, int]:
    codec = get_value_codec(value_mode)
    total_entries = 0
    total_frontier = 0
    for shard_id in range(shard_count):
        shard_store = PackedStateStore(_shard_store_path(output_path, shard_id), codec, page_entries=page_entries, readonly=True)
        total_entries += shard_store.entry_count()
        total_frontier += shard_store.frontier_size()
    return total_entries, total_frontier


def _seed_sharded_root(
    output_path: Path,
    *,
    value_mode: ValueMode,
    page_entries: int,
    shard_count: int,
) -> None:
    codec = get_value_codec(value_mode)
    total_entries, total_frontier = _summarize_sharded_stores(
        output_path,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
    )
    if total_entries > 0 or total_frontier > 0:
        return
    start = canonicalize(initial_position())
    start_key = encode_position(start)
    owner_shard = owner_shard_for_position(start, page_entries, shard_count)
    shard_store = PackedStateStore(_shard_store_path(output_path, owner_shard), codec, page_entries=page_entries)
    shard_store.enqueue_many([(start_key, 0)])
    shard_store.close()


def _update_sharded_root_summary(
    output_path: Path,
    *,
    build_info: dict[str, Any],
    value_mode: ValueMode,
    page_entries: int,
    shard_count: int,
) -> tuple[int, int]:
    codec = get_value_codec(value_mode)
    total_entries, total_frontier = _summarize_sharded_stores(
        output_path,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
    )
    root_metadata = _build_root_store_metadata(
        build_info,
        codec_mode=codec.mode,
        payload_size=codec.payload_size,
        page_entries=page_entries,
        shard_count=shard_count,
        entry_count=total_entries,
        frontier_size=total_frontier,
    )
    _write_root_store_metadata(output_path, root_metadata)
    return total_entries, total_frontier


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


def _process_shard_batch(
    output_path_str: str,
    *,
    shard_id: int,
    value_mode: ValueMode,
    page_entries: int,
    batch_size: int,
    max_depth: int | None,
    shard_count: int,
    max_states: int | None,
    shared_entry_count,
    shared_entry_count_lock,
) -> ShardBatchResult:
    output_path = Path(output_path_str)
    codec = get_value_codec(value_mode)
    shard_store = PackedStateStore(_shard_store_path(output_path, shard_id), codec, page_entries=page_entries)
    frontier_batch = shard_store.pop_frontier_batch(batch_size)
    if not frontier_batch:
        shard_store.close()
        return ShardBatchResult(
            shard_id=shard_id,
            processed_frontier_states=0,
            inserted_states=0,
            outbound_entries={},
            limit_reached=False,
        )

    processed = 0
    inserted = 0
    limit_reached = False
    outbound_entries: dict[int, list[tuple[bytes, int]]] = defaultdict(list)
    local_enqueue: list[tuple[bytes, int]] = []

    for item in frontier_batch:
        processed += 1
        reserved_slot = False
        if max_states is not None:
            with shared_entry_count_lock:
                if shared_entry_count.value >= max_states:
                    limit_reached = True
                    break
                shared_entry_count.value += 1
                reserved_slot = True

        position = decode_position(item.position_key)
        if not shard_store.add_state(item.position_key, codec.evaluate(position, item.depth)):
            if reserved_slot:
                with shared_entry_count_lock:
                    shared_entry_count.value -= 1
            continue

        inserted += 1
        if max_depth is not None and item.depth >= max_depth:
            continue
        if is_terminal(position):
            continue

        next_depth = item.depth + 1
        for move in legal_moves(position):
            next_position = canonicalize(apply_move(position, move))
            next_key = encode_position(next_position)
            owner_shard = owner_shard_for_key(next_key, page_entries, shard_count)
            if owner_shard == shard_id:
                local_enqueue.append((next_key, next_depth))
            else:
                outbound_entries[owner_shard].append((next_key, next_depth))

    if local_enqueue:
        shard_store.enqueue_many(local_enqueue)
    shard_store.close()
    return ShardBatchResult(
        shard_id=shard_id,
        processed_frontier_states=processed,
        inserted_states=inserted,
        outbound_entries=dict(outbound_entries),
        limit_reached=limit_reached,
    )


def generate_database(
    output_path: str | Path,
    *,
    value_mode: ValueMode,
    max_depth: int | None,
    max_states: int | None,
    batch_size: int,
    page_entries: int,
    resume: bool,
    shard_count: int = 1,
    progress_callback: Callable[[GenerationProgress], None] | None = None,
) -> GenerationResult:
    output_path = Path(output_path)
    codec = get_value_codec(value_mode)
    started_at = time.perf_counter()
    build_info = _build_metadata(
        argparse.Namespace(
            value_mode=value_mode,
            max_depth=max_depth,
            max_states=max_states,
            batch_size=batch_size,
            page_entries=page_entries,
        )
    )
    if shard_count <= 1:
        store = PackedStateStore(output_path, codec, page_entries=page_entries)
        if store.entry_count() > 0 and not resume:
            raise RuntimeError(f"Database at {output_path} already contains states; use --resume to continue")

        store.initialize_build(build_info)

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
        store.close()
        return result

    existing_root_metadata = _load_root_store_metadata(output_path)
    if existing_root_metadata is not None and not resume:
        existing_entry_count = int(existing_root_metadata.get("entry_count", 0))
        if existing_entry_count > 0:
            raise RuntimeError(f"Database at {output_path} already contains states; use --resume to continue")
    if resume and existing_root_metadata is not None:
        existing_shard_count = existing_root_metadata.get("shard_count")
        if isinstance(existing_shard_count, int) and existing_shard_count > 1:
            shard_count = existing_shard_count

    _initialize_sharded_stores(
        output_path,
        build_info=build_info,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
        resume=resume,
    )
    _seed_sharded_root(
        output_path,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
    )
    total_entries, total_frontier = _update_sharded_root_summary(
        output_path,
        build_info=build_info,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
    )

    manager = multiprocessing.Manager()
    shared_entry_count = manager.Value("i", total_entries)
    shared_entry_count_lock = manager.Lock()
    processed = 0
    stop = False
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=shard_count, mp_context=context) as executor:
        while True:
            if stop:
                break
            active_shards: list[int] = []
            for shard_id in range(shard_count):
                shard_store = PackedStateStore(_shard_store_path(output_path, shard_id), codec, page_entries=page_entries, readonly=True)
                if shard_store.frontier_size() > 0:
                    active_shards.append(shard_id)
            if not active_shards:
                break

            futures = [
                executor.submit(
                    _process_shard_batch,
                    str(output_path),
                    shard_id=shard_id,
                    value_mode=value_mode,
                    page_entries=page_entries,
                    batch_size=batch_size,
                    max_depth=max_depth,
                    shard_count=shard_count,
                    max_states=max_states,
                    shared_entry_count=shared_entry_count,
                    shared_entry_count_lock=shared_entry_count_lock,
                )
                for shard_id in active_shards
            ]
            outbound_by_target: dict[int, list[tuple[bytes, int]]] = defaultdict(list)
            limit_reached = False
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                processed += result.processed_frontier_states
                limit_reached = limit_reached or result.limit_reached
                for target_shard, entries in result.outbound_entries.items():
                    outbound_by_target[target_shard].extend(entries)

            for target_shard, entries in outbound_by_target.items():
                shard_store = PackedStateStore(_shard_store_path(output_path, target_shard), codec, page_entries=page_entries)
                shard_store.enqueue_many(entries)
                shard_store.close()

            total_entries, total_frontier = _update_sharded_root_summary(
                output_path,
                build_info=build_info,
                value_mode=value_mode,
                page_entries=page_entries,
                shard_count=shard_count,
            )
            if progress_callback is not None:
                progress_callback(
                    GenerationProgress(
                        processed_frontier_states=processed,
                        stored_states=total_entries,
                        frontier_remaining=total_frontier,
                        elapsed_seconds=time.perf_counter() - started_at,
                        finished=False,
                    )
                )
            if limit_reached or (max_states is not None and shared_entry_count.value >= max_states):
                stop = True

    total_entries, total_frontier = _update_sharded_root_summary(
        output_path,
        build_info=build_info,
        value_mode=value_mode,
        page_entries=page_entries,
        shard_count=shard_count,
    )
    result = GenerationResult(
        processed_frontier_states=processed,
        stored_states=total_entries,
        frontier_remaining=total_frontier,
        stopped_because_of_limit=stop,
    )
    if progress_callback is not None:
        progress_callback(
            GenerationProgress(
                processed_frontier_states=processed,
                stored_states=total_entries,
                frontier_remaining=total_frontier,
                elapsed_seconds=time.perf_counter() - started_at,
                finished=True,
            )
        )
    manager.shutdown()
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
    parser.add_argument("--shards", type=int, default=1, help="Number of shard workers/stores for parallel generation")
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
        shard_count=args.shards,
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
