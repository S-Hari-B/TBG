"""Party member definition structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(slots=True)
class PartyMemberDef:
    """Defines recruitable party members."""

    id: str
    name: str
    base_hp: int
    base_mp: int
    speed: int
    starting_level: int
    weapon_ids: Tuple[str, ...]
    armour_id: str | None
    armour_slots: Dict[str, str] = field(default_factory=dict)
    tags: Tuple[str, ...] = ()

