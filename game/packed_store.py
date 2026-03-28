from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from game.encoding import decode_position, index_position
from game.value_codec import ValueCodec

QUEUE_RECORD_SIZE = 32
META_FILE = "metadata.json"
QUEUE_FILE = "frontier.bin"
SUBSPACES_DIR = "subspaces"


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
        self.path.mkdir(parents=True, exist_ok=True)
        self.subspaces_path = self.path / SUBSPACES_DIR
        self.subspaces_path.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.path / QUEUE_FILE
        self.metadata_path = self.path / META_FILE
        self.metadata: dict[str, Any] = {}
        if self.metadata_path.exists():
            self.metadata = json.loads(self.metadata_path.read_text())
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

    def entry_count(self) -> int:
        return int(self.metadata.get("entry_count", 0))

    def frontier_size(self) -> int:
        return int(self.metadata.get("frontier_tail", 0)) - int(self.metadata.get("frontier_head", 0))

    def _page_paths(self, subspace: str, page_id: int) -> tuple[Path, Path]:
        subspace_path = self.subspaces_path / subspace
        subspace_path.mkdir(parents=True, exist_ok=True)
        return (
            subspace_path / f"values.{page_id:08x}.bin",
            subspace_path / f"seen.{page_id:08x}.bin",
        )

    def _read_seen(self, seen_path: Path, slot: int) -> bool:
        if not seen_path.exists():
            return False
        with seen_path.open("rb") as handle:
            handle.seek(slot)
            raw = handle.read(1)
        return raw == b"\x01"

    def _ensure_page_files(self, values_path: Path, seen_path: Path) -> None:
        if not values_path.exists():
            with values_path.open("wb") as handle:
                handle.truncate(self.page_entries * self.codec.payload_size)
        if not seen_path.exists():
            with seen_path.open("wb") as handle:
                handle.truncate(self.page_entries)

    def add_state(self, position_key: bytes, value: object) -> bool:
        position = decode_position(position_key)
        subspace, index = index_position(position)
        page_id, slot = divmod(index, self.page_entries)
        values_path, seen_path = self._page_paths(subspace, page_id)
        self._ensure_page_files(values_path, seen_path)
        if self._read_seen(seen_path, slot):
            return False

        with values_path.open("r+b") as values_handle:
            values_handle.seek(slot * self.codec.payload_size)
            values_handle.write(self.codec.encode(value))
        with seen_path.open("r+b") as seen_handle:
            seen_handle.seek(slot)
            seen_handle.write(b"\x01")

        self.metadata["entry_count"] = self.entry_count() + 1
        self._flush_metadata()
        return True

    def lookup(self, position) -> object | None:
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
        tail = int(self.metadata.get("frontier_tail", 0))
        with self.queue_path.open("ab") as handle:
            handle.write(struct.pack(">I", depth))
            handle.write(position_key)
        self.metadata["frontier_tail"] = tail + 1
        self._flush_metadata()
        return tail

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
        self._flush_metadata()
        return items
