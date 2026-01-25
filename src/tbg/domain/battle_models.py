"""Battle domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple

from tbg.domain.entities import Attributes, BaseStats, Stats
from tbg.domain.debuffs import ActiveDebuff

Side = Literal["allies", "enemies"]


@dataclass(slots=True)
class Combatant:
    """Represents an individual participant in battle."""

    instance_id: str
    display_name: str
    side: Side
    stats: Stats
    base_stats: BaseStats | Stats | None = None
    attributes: Attributes | None = None
    tags: Tuple[str, ...] = ()
    weapon_tags: Tuple[str, ...] = ()
    guard_reduction: int = 0
    source_id: str | None = None  # original definition id
    debuffs: List[ActiveDebuff] = field(default_factory=list)
    owner_id: str | None = None
    bond_cost: int | None = None

    @property
    def is_alive(self) -> bool:
        return self.stats.hp > 0


def is_summon(combatant: Combatant) -> bool:
    return combatant.owner_id is not None


def summon_owner_id(combatant: Combatant) -> str | None:
    return combatant.owner_id


@dataclass(slots=True)
class BattleState:
    """Tracks the state of an ongoing battle."""

    battle_id: str
    allies: List[Combatant]
    enemies: List[Combatant]
    enemy_aggro: Dict[str, Dict[str, int]] = field(default_factory=dict)
    party_threat: Dict[str, Dict[str, int]] = field(default_factory=dict)
    last_target: Dict[str, str | None] = field(default_factory=dict)
    turn_queue: List[str] = field(default_factory=list)
    current_actor_id: str | None = None
    is_over: bool = False
    victor: Side | None = None
    player_id: str | None = None
    round_index: int = 1
    round_last_actor_id: str | None = None
    enemy_skill_uses: Dict[str, Dict[str, int]] = field(default_factory=dict)


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
    defense: int


