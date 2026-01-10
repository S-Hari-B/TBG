"""Loot table definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(slots=True)
class LootDropDef:
    item_id: str
    chance: float
    min_qty: int = 1
    max_qty: int = 1


@dataclass(slots=True)
class LootTableDef:
    """Loot table keyed by enemy tags."""

    id: str
    required_tags: Tuple[str, ...]
    forbidden_tags: Tuple[str, ...]
    drops: List[LootDropDef]

