"""Summon definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class BondScaling:
    hp_per_bond: float
    atk_per_bond: float
    def_per_bond: float
    init_per_bond: float


@dataclass(slots=True)
class SummonDef:
    """Describes a summon definition."""

    id: str
    name: str
    max_hp: int
    max_mp: int
    attack: int
    defense: int
    speed: int
    bond_cost: int
    tags: Tuple[str, ...]
    bond_scaling: BondScaling
