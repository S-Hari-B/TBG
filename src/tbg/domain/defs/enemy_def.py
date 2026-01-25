"""Enemy definition structures."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EnemyDef:
    """Enemy definition including optional grouping info."""

    id: str
    name: str
    hp: int | None = None
    mp: int | None = None
    attack: int | None = None
    defense: int | None = None
    speed: int | None = None
    rewards_exp: int | None = None
    rewards_gold: int | None = None
    tags: tuple[str, ...] = ()
    enemy_ids: tuple[str, ...] | None = None
    weapon_ids: tuple[str, ...] = ()
    armour_id: str | None = None
    armour_slots: dict[str, str] = field(default_factory=dict)
    enemy_skill_ids: tuple[str, ...] = ()


