"""Enemy definition structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EnemyDef:
    """Minimal enemy definition."""

    id: str
    name: str
    max_hp: int
    attack: int
    defense: int
    xp: int
    gold: int


