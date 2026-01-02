"""Enemy runtime models."""
from __future__ import annotations

from dataclasses import dataclass

from .stats import Stats


@dataclass(slots=True)
class EnemyInstance:
    """Represents a spawned enemy ready for battle."""

    id: str
    enemy_id: str
    name: str
    stats: Stats
    xp_reward: int
    gold_reward: int
    tags: tuple[str, ...] = ()




