"""Item definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ItemTargeting = Literal["self", "ally", "enemy", "any"]


@dataclass(slots=True)
class ItemDef:
    """Lightweight item definition used for loot/inventory description."""

    id: str
    name: str
    kind: str
    value: int
    heal_hp: int = 0
    heal_mp: int = 0
    restore_energy: int = 0
    targeting: ItemTargeting = "self"
    debuff_attack_flat: int = 0
    debuff_defense_flat: int = 0


