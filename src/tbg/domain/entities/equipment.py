"""Equipment runtime models."""
from __future__ import annotations

from dataclasses import dataclass

from tbg.domain.defs import ArmourDef, WeaponDef


@dataclass(slots=True)
class Equipment:
    """Represents the equipped weapon and armour for an entity."""

    weapon: WeaponDef
    armour: ArmourDef




