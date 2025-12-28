"""Skill definition structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class SkillDef:
    """Describes a weapon-tag-gated combat skill."""

    id: str
    name: str
    description: str
    tags: Tuple[str, ...]
    required_weapon_tags: Tuple[str, ...]
    target_mode: str
    max_targets: int
    mp_cost: int
    base_power: int
    effect_type: str
    gold_value: int

