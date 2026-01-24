"""File-system helpers for save slot storage."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from tbg.presentation.cli import config


@dataclass(slots=True)
class SlotMetadata:
    """Describes the contents of a save slot for menu display."""

    slot: int
    exists: bool
    metadata: Dict[str, Any] | None = None
    is_corrupt: bool = False


class SaveSlotStore:
    """Handles slot-based persistence on disk."""

    def __init__(self, base_dir: Path | str | None = None, slot_count: int = 3) -> None:
        self._base_dir = Path(base_dir) if base_dir is not None else config.get_save_dir()
        self._slot_count = slot_count

    def list_slots(self) -> List[SlotMetadata]:
        """Return metadata for each configured slot."""
        slots: List[SlotMetadata] = []
        for slot_index in range(1, self._slot_count + 1):
            path = self._slot_path(slot_index)
            if not path.exists():
                slots.append(SlotMetadata(slot=slot_index, exists=False))
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                raw_metadata = payload.get("metadata") if isinstance(payload, dict) else None
                metadata = raw_metadata if isinstance(raw_metadata, dict) else None
                slots.append(SlotMetadata(slot=slot_index, exists=True, metadata=metadata))
            except Exception:
                slots.append(SlotMetadata(slot=slot_index, exists=True, metadata=None, is_corrupt=True))
        return slots

    def slot_exists(self, slot: int) -> bool:
        """Return True if the slot has data on disk."""
        self._validate_slot(slot)
        return self._slot_path(slot).exists()

    def read_slot(self, slot: int) -> Dict[str, Any]:
        """Load and parse the payload stored in the requested slot."""
        self._validate_slot(slot)
        path = self._slot_path(slot)
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    def write_slot(self, slot: int, payload: Dict[str, Any]) -> None:
        """Persist the payload into the requested slot."""
        self._validate_slot(slot)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._slot_path(slot)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def delete_slot(self, slot: int) -> None:
        """Delete the requested slot payload if it exists."""
        self._validate_slot(slot)
        path = self._slot_path(slot)
        try:
            path.unlink()
        except FileNotFoundError:
            return

    def _slot_path(self, slot: int) -> Path:
        return self._base_dir / f"slot_{slot}.json"

    def _validate_slot(self, slot: int) -> None:
        if not 1 <= slot <= self._slot_count:
            raise ValueError(f"Slot index must be between 1 and {self._slot_count}.")
