"""Stat models for runtime entities."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Stats:
    """Stores basic combat stats."""

    max_hp: int
    hp: int
    max_mp: int
    mp: int
    attack: int
    defense: int


