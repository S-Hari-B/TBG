"""Player class definition structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ClassDef:
    """Defines starting attributes and equipment ids for a class."""

    id: str
    name: str
    base_hp: int
    base_mp: int
    starting_weapon_id: str
    starting_armour_id: str


