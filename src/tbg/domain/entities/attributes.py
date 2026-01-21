"""Attribute models for runtime entities."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Attributes:
    """Stores base attributes (no scaling applied yet)."""

    STR: int
    DEX: int
    INT: int
    VIT: int
    BOND: int

