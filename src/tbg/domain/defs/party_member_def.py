"""Party member definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class PartyMemberDef:
    """Defines recruitable party members."""

    id: str
    name: str
    base_hp: int
    base_mp: int
    speed: int
    weapon_ids: Tuple[str, ...]
    armour_id: str | None
    tags: Tuple[str, ...] = ()

