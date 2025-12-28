"""Weapon definition structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WeaponDef:
    """Weapon definition with optional combat metadata."""

    id: str
    name: str
    attack: int
    value: int
    tags: tuple[str, ...] = ()
    slot_cost: int = 1
    default_basic_attack_id: str | None = None
    energy_bonus: int = 0


