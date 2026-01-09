"""Player class definition structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(slots=True)
class ClassDef:
    """Defines starting attributes and equipment ids for a class."""

    id: str
    name: str
    base_hp: int
    base_mp: int
    speed: int
    starting_weapon_id: str
    starting_armour_id: str
    starting_weapons: Tuple[str, ...] = ()
    starting_armour_slots: Dict[str, str] = field(default_factory=dict)
    starting_items: Dict[str, int] = field(default_factory=dict)
