"""Player and party-member models."""
from __future__ import annotations

from dataclasses import dataclass, field

from .attributes import Attributes
from .base_stats import BaseStats
from .stats import Stats


@dataclass(slots=True)
class Player:
    """Represents a player-created party member."""

    id: str
    name: str
    class_id: str
    stats: Stats
    attributes: Attributes
    base_stats: BaseStats
    equipped_summons: list[str] = field(default_factory=list)




