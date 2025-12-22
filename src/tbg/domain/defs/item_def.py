"""Item definition structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .effect_def import EffectDef


@dataclass(slots=True)
class ItemDef:
    """Consumable or usable item definition."""

    id: str
    name: str
    description: str
    type: str
    effects: List[EffectDef] = field(default_factory=list)
    value: int = 0


