"""Armour definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class ArmourDef:
    """Armour definition including slot metadata."""

    id: str
    name: str
    slot: str
    defense: int
    value: int
    tags: Tuple[str, ...] = ()
    hp_bonus: int = 0
