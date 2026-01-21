"""Base stat model (pre-attribute scaling)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BaseStats:
    """Represents base stats before attribute contributions."""

    max_hp: int
    max_mp: int
    attack: int
    defense: int
    speed: int
