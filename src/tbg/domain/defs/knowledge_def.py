"""Knowledge definition data structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class KnowledgeEntry:
    """Represents a block of knowledge a party member can share."""

    enemy_tags: Tuple[str, ...]
    max_level: int | None
    hp_range: Tuple[int, int] | None
    speed_hint: str | None
    behavior: str | None

