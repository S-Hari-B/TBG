"""Battle domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Tuple

from tbg.domain.entities import Stats

Side = Literal["allies", "enemies"]


@dataclass(slots=True)
class Combatant:
    """Represents an individual participant in battle."""

    instance_id: str
    display_name: str
    side: Side
    stats: Stats
    tags: Tuple[str, ...] = ()
    weapon_tags: Tuple[str, ...] = ()
    guard_reduction: int = 0
    source_id: str | None = None  # original definition id

    @property
    def is_alive(self) -> bool:
        return self.stats.hp > 0


@dataclass(slots=True)
class BattleState:
    """Tracks the state of an ongoing battle."""

    battle_id: str
    allies: List[Combatant]
    enemies: List[Combatant]
    turn_queue: List[str] = field(default_factory=list)
    current_actor_id: str | None = None
    is_over: bool = False
    victor: Side | None = None
    player_id: str | None = None


@dataclass(slots=True)
class BattleCombatantView:
    """Presentation-friendly snapshot of a combatant."""

    instance_id: str
    name: str
    hp_display: str
    side: str
    is_alive: bool
    current_hp: int
    max_hp: int


