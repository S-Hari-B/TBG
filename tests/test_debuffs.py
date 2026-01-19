from __future__ import annotations

from tbg.domain.debuffs import (
    ActiveDebuff,
    apply_debuff_no_stack,
    compute_effective_attack,
    compute_effective_defense,
)
from tbg.domain.entities import Stats


def test_apply_debuff_no_stack_prevents_duplicates() -> None:
    debuffs: list[ActiveDebuff] = []
    applied_first = apply_debuff_no_stack(
        debuffs, debuff_type="attack_down", amount=2, expires_at_round=3
    )
    applied_second = apply_debuff_no_stack(
        debuffs, debuff_type="attack_down", amount=3, expires_at_round=3
    )

    assert applied_first is True
    assert applied_second is False
    assert len(debuffs) == 1


def test_compute_effective_stats_respect_penalties() -> None:
    stats = Stats(max_hp=10, hp=10, max_mp=5, mp=5, attack=8, defense=4, speed=3)
    debuffs = [
        ActiveDebuff(debuff_type="attack_down", amount=3, expires_at_round=4),
        ActiveDebuff(debuff_type="defense_down", amount=2, expires_at_round=5),
    ]

    assert compute_effective_attack(stats, debuffs) == 5
    assert compute_effective_defense(stats, debuffs) == 2


def test_apply_allows_distinct_types() -> None:
    debuffs: list[ActiveDebuff] = []
    apply_debuff_no_stack(debuffs, debuff_type="attack_down", amount=1, expires_at_round=3)
    applied = apply_debuff_no_stack(debuffs, debuff_type="defense_down", amount=2, expires_at_round=4)

    assert applied is True
    assert len(debuffs) == 2
