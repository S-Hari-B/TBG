"""Floor definition data structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FloorDef:
    """Describes a dungeon floor and its entry point."""

    id: str
    name: str
    level: int
    starting_location_id: str
    boss_location_id: str | None = None
    next_floor_id: str | None = None
    notes: str | None = None
