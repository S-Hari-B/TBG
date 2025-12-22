"""Effect definition primitives."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EffectDef:
    """Simple effect definition (e.g., heal HP)."""

    kind: str
    amount: int


