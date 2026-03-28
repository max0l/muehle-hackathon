from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from game.encoding import decode_position, index_position, owner_shard_for_position
from game.value_codec import ValueCodec

QUEUE_RECORD_SIZE = 32
META_FILE = "metadata.json"
QUEUE_FILE = "frontier.bin"
SUBSPACES_DIR = "subspaces"
SHARDS_DIR = "shards"
FORMAT_VERSION_V1 = 1
FORMAT_VERSION_V2 = 2


@dataclass
class FrontierItem:
    depth: int
    position_key: bytes


class PackedStateStore:
    def __init__(
        self,
        path: str | Path,
        codec: ValueCodec,
        *,
        page_entries: int = 4096,
        readonly: bool = False,
    ) -> None:
        self.path = Path(path)
        self.codec = codec
        self.page_entries = page_entries
        self.readonly = readonly
        self.shard_count = 1
        self.shard_id: int | None = None
        self.format_version = FORMAT_VERSION_V1
        self._is_sharded_root = False
        self._metadata_dirty = False
        self._page_write_handles: dict[tuple[Path, Path], tuple[BinaryIO, BinaryIO]] = {}
        self._queue_append_handle: BinaryIO | None = None
        self.path.mkdir(parents=True, exist_ok=True)
        self.subspaces_path = self.path / SUBSPACES_DIR
        self.subspaces_path.mkdir(parents=True, exist_ok=True)
        self.shards_path = self.path / SHARDS_DIR
        self.queue_path = self.path / QUEUE_FILE
        self.metadata_path = self.path / META_FILE
        self.metadata: dict[str, Any] = {}
        if self.metadata_path.exists():
            self.metadata = json.loads(self.metadata_path.read_text())
            metadata_format_version = self.metadata.get("format_version")
            if isinstance(metadata_format_version, int):
                self.format_version = metadata_format_version
            metadata_shard_count = self.metadata.get("shard_count")
            if isinstance(metadata_shard_count, int) and metadata_shard_count > 1:
                self.shard_count = metadata_shard_count
            metadata_shard_id = self.metadata.get("shard_id")
            if isinstance(metadata_shard_id, int):
                self.shard_id = metadata_shard_id
            self._is_sharded_root = self.shard_count > 1 and self.shard_id is None
            metadata_page_entries = self.metadata.get("page_entries")
            if isinstance(metadata_page_entries, int):
                self.page_entries = metadata_page_entries
            metadata_codec_mode = self.metadata.get("codec_mode")
            if metadata_codec_mode and metadata_codec_mode != self.codec.mode:
                raise ValueError(
                    f"Packed store was built with codec mode {metadata_codec_mode!r}, "
                    f"but {self.codec.mode!r} was requested"
                )

    def _flush_metadata(self) -> None:
        self.metadata_path.write_text(json.dumps(self.metadata, indent=2, sort_keys=True))
        self._metadata_dirty = False

    def _mark_metadata_dirty(self) -> None:
        self._metadata_dirty = True

    def _flush_open_handles(self) -> None:
        for values_handle, seen_handle in self._page_write_handles.values():
            values_handle.flush()
            seen_handle.flush()
        if self._queue_append_handle is not None:
            self._queue_append_handle.flush()

    def flush(self) -> None:
        self._flush_open_handles()
        if self._metadata_dirty:
            self._flush_metadata()

    def initialize_build(self, metadata: dict[str, Any], reset_queue: bool = False) -> None:
        if not self.metadata:
            self.metadata = {
                "build_info": metadata,
                "entry_count": 0,
                "frontier_head": 0,
                "frontier_tail": 0,
                "codec_mode": self.codec.mode,
                "payload_size": self.codec.payload_size,
                "page_entries": self.page_entries,
            }
        else:
            self.metadata.setdefault("build_info", metadata)
            self.metadata.setdefault("entry_count", 0)
            self.metadata.setdefault("frontier_head", 0)
            self.metadata.setdefault("frontier_tail", 0)
            self.metadata.setdefault("codec_mode", self.codec.mode)
            self.metadata.setdefault("payload_size", self.codec.payload_size)
            self.metadata.setdefault("page_entries", self.page_entries)
        if reset_queue:
            self.metadata["frontier_head"] = 0
            self.metadata["frontier_tail"] = 0
            self.queue_path.write_bytes(b"")
        self._flush_metadata()

    def get_metadata(self) -> dict[str, Any]:
        return dict(self.metadata.get("build_info", {}))

    def _shard_metadata_paths(self) -> list[Path]:
        if self.shard_count <= 1:
            return []
        return [self.shards_path / f"{shard_id:04d}" / META_FILE for shard_id in range(self.shard_count)]

    def _aggregate_shard_metric(self, key: str) -> int:
        total = 0
        for metadata_path in self._shard_metadata_paths():
            if not metadata_path.exists():
                continue
            metadata = json.loads(metadata_path.read_text())
            total += int(metadata.get(key, 0))
        return total

    def entry_count(self) -> int:
        if self._is_sharded_root and self.shard_count > 1:
            if "entry_count" in self.metadata:
                return int(self.metadata.get("entry_count", 0))
            return self._aggregate_shard_metric("entry_count")
        return int(self.metadata.get("entry_count", 0))

    def frontier_size(self) -> int:
        if self._is_sharded_root and self.shard_count > 1:
            if "frontier_size" in self.metadata:
                return int(self.metadata.get("frontier_size", 0))
            total = 0
            for metadata_path in self._shard_metadata_paths():
                if not metadata_path.exists():
                    continue
                metadata = json.loads(metadata_path.read_text())
                total += int(metadata.get("frontier_tail", 0)) - int(metadata.get("frontier_head", 0))
            return total
        return int(self.metadata.get("frontier_tail", 0)) - int(self.metadata.get("frontier_head", 0))

    def shard_path(self, shard_id: int) -> Path:
        return self.shards_path / f"{shard_id:04d}"

    def _page_paths(self, subspace: str, page_id: int) -> tuple[Path, Path]:
        subspace_path = self.subspaces_path / subspace
        subspace_path.mkdir(parents=True, exist_ok=True)
        return (
            subspace_path / f"values.{page_id:08x}.bin",
            subspace_path / f"seen.{page_id:08x}.bin",
        )

    def _read_seen(self, seen_path: Path, slot: int, handle: BinaryIO | None = None) -> bool:
        if handle is None and not seen_path.exists():
            return False
        if handle is None:
            with seen_path.open("rb") as handle:
                handle.seek(slot)
                raw = handle.read(1)
            return raw == b"\x01"

        handle.flush()
        handle.seek(slot)
        raw = handle.read(1)
        return raw == b"\x01"

    def _ensure_writable(self) -> None:
        if self.readonly:
            raise RuntimeError("PackedStateStore is readonly")

    def _get_page_write_handles(self, values_path: Path, seen_path: Path) -> tuple[BinaryIO, BinaryIO]:
        self._ensure_writable()
        key = (values_path, seen_path)
        handles = self._page_write_handles.get(key)
        if handles is None:
            self._ensure_page_files(values_path, seen_path)
            handles = (values_path.open("r+b"), seen_path.open("r+b"))
            self._page_write_handles[key] = handles
        return handles

    def _add_state_no_flush(self, position_key: bytes, value: object) -> bool:
        position = decode_position(position_key)
        subspace, index = index_position(position)
        page_id, slot = divmod(index, self.page_entries)
        values_path, seen_path = self._page_paths(subspace, page_id)
        values_handle, seen_handle = self._get_page_write_handles(values_path, seen_path)
        if self._read_seen(seen_path, slot, handle=seen_handle):
            return False

        values_handle.seek(slot * self.codec.payload_size)
        values_handle.write(self.codec.encode(value))
        seen_handle.seek(slot)
        seen_handle.write(b"\x01")

        self.metadata["entry_count"] = self.entry_count() + 1
        self._mark_metadata_dirty()
        return True

    def add_states(
        self,
        entries: list[tuple[bytes, object]],
        *,
        max_new_entries: int | None = None,
    ) -> list[bool]:
        inserted: list[bool] = []
        new_entries = 0
        for position_key, value in entries:
            if max_new_entries is not None and new_entries >= max_new_entries:
                inserted.append(False)
                continue
            was_added = self._add_state_no_flush(position_key, value)
            inserted.append(was_added)
            if was_added:
                new_entries += 1
        self.flush()
        return inserted

    def _get_queue_append_handle(self) -> BinaryIO:
        self._ensure_writable()
        if self._queue_append_handle is None:
            self._queue_append_handle = self.queue_path.open("ab")
        return self._queue_append_handle

    def enqueue_many(self, entries: list[tuple[bytes, int]]) -> int:
        tail = int(self.metadata.get("frontier_tail", 0))
        if not entries:
            return tail
        handle = self._get_queue_append_handle()
        for position_key, depth in entries:
            handle.write(struct.pack(">I", depth))
            handle.write(position_key)
        self.metadata["frontier_tail"] = tail + len(entries)
        self._mark_metadata_dirty()
        self.flush()
        return tail

    def close(self) -> None:
        self.flush()
        for values_handle, seen_handle in self._page_write_handles.values():
            values_handle.close()
            seen_handle.close()
        self._page_write_handles.clear()
        if self._queue_append_handle is not None:
            self._queue_append_handle.close()
            self._queue_append_handle = None

    def __enter__(self) -> "PackedStateStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def add_state(self, position_key: bytes, value: object) -> bool:
        was_added = self._add_state_no_flush(position_key, value)
        self.flush()
        return was_added

    def _ensure_page_files(self, values_path: Path, seen_path: Path) -> None:
        if not values_path.exists():
            with values_path.open("wb") as handle:
                handle.truncate(self.page_entries * self.codec.payload_size)
        if not seen_path.exists():
            with seen_path.open("wb") as handle:
                handle.truncate(self.page_entries)

    def lookup(self, position) -> object | None:
        if self._is_sharded_root and self.shard_count > 1:
            shard_id = owner_shard_for_position(position, self.page_entries, self.shard_count)
            shard_store = PackedStateStore(self.shard_path(shard_id), self.codec, page_entries=self.page_entries, readonly=True)
            return shard_store.lookup(position)
        subspace, index = index_position(position)
        page_id, slot = divmod(index, self.page_entries)
        values_path, seen_path = self._page_paths(subspace, page_id)
        if not self._read_seen(seen_path, slot):
            return None
        with values_path.open("rb") as values_handle:
            values_handle.seek(slot * self.codec.payload_size)
            raw = values_handle.read(self.codec.payload_size)
        return self.codec.decode(raw)

    def enqueue(self, position_key: bytes, depth: int) -> int:
        return self.enqueue_many([(position_key, depth)])

    def pop_frontier_batch(self, batch_size: int) -> list[FrontierItem]:
        head = int(self.metadata.get("frontier_head", 0))
        tail = int(self.metadata.get("frontier_tail", 0))
        if head >= tail or not self.queue_path.exists():
            return []

        items: list[FrontierItem] = []
        with self.queue_path.open("rb") as handle:
            handle.seek(head * QUEUE_RECORD_SIZE)
            for _ in range(min(batch_size, tail - head)):
                raw = handle.read(QUEUE_RECORD_SIZE)
                if len(raw) < QUEUE_RECORD_SIZE:
                    break
                depth = struct.unpack(">I", raw[:4])[0]
                items.append(FrontierItem(depth=depth, position_key=raw[4:]))

        self.metadata["frontier_head"] = head + len(items)
        self._mark_metadata_dirty()
        self.flush()
        return items
