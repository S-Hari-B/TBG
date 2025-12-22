"""Armour definition structures."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ArmourDef:
    """Minimal armour definition."""

    id: str
    name: str
    defense: int
    value: int


