"""Weapon definition structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WeaponDef:
    """Minimal weapon definition."""

    id: str
    name: str
    attack: int
    value: int


