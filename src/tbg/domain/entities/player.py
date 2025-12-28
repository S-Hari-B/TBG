"""Player and party-member models."""
from __future__ import annotations

from dataclasses import dataclass

from .equipment import Equipment
from .stats import Stats


@dataclass(slots=True)
class Player:
    """Represents a player-created party member."""

    id: str
    name: str
    class_id: str
    stats: Stats
    equipment: Equipment
    extra_weapon_ids: tuple[str, ...] = ()


