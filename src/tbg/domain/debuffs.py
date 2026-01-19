"""Battle debuff helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Sequence

from tbg.domain.entities import Stats

DebuffType = Literal["attack_down", "defense_down"]
@dataclass(slots=True)
class ActiveDebuff:
    """Tracks a temporary battle debuff."""

    debuff_type: DebuffType
    amount: int
    expires_at_round: int


def apply_debuff_no_stack(
    debuffs: List[ActiveDebuff],
    *,
    debuff_type: DebuffType,
    amount: int,
    expires_at_round: int,
) -> bool:
    """
    Apply a debuff if the same type is not already active.

    Returns True if the debuff was applied, False when an existing
    debuff of the same type prevented stacking.
    """

    for existing in debuffs:
        if existing.debuff_type == debuff_type:
            return False
    debuffs.append(ActiveDebuff(debuff_type=debuff_type, amount=amount, expires_at_round=expires_at_round))
    return True


def compute_effective_attack(stats: Stats, debuffs: Sequence[ActiveDebuff]) -> int:
    penalty = sum(debuff.amount for debuff in debuffs if debuff.debuff_type == "attack_down")
    return max(1, stats.attack - penalty)


def compute_effective_defense(stats: Stats, debuffs: Sequence[ActiveDebuff]) -> int:
    penalty = sum(debuff.amount for debuff in debuffs if debuff.debuff_type == "defense_down")
    return max(0, stats.defense - penalty)


