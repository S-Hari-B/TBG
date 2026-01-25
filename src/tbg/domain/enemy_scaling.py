"""Deterministic enemy stat scaling helpers."""
from __future__ import annotations

from tbg.domain.entities import Stats

# Area-level scaling is the primary difficulty ruler for the demo.
# Target range for current content is roughly levels 0-5.
# Coefficients stay linear and additive to keep tuning deterministic:
# - HP grows to handle broader player damage scaling.
# - DEF rises slowly to avoid breakpoint problems with subtractive defense.
# - ATK remains conservative to avoid bursty spikes.
# - SPEED now scales so enemy initiative remains competitive.
HP_PER_LEVEL = 12
ATTACK_PER_LEVEL = 2
DEFENSE_PER_LEVEL = 1
SPEED_PER_LEVEL = 1


def scale_enemy_stats(base: Stats, *, battle_level: int) -> Stats:
    level = max(0, battle_level)
    max_hp = base.max_hp + (HP_PER_LEVEL * level)
    attack = base.attack + (ATTACK_PER_LEVEL * level)
    defense = base.defense + (DEFENSE_PER_LEVEL * level)
    speed = base.speed + (SPEED_PER_LEVEL * level)
    hp = min(base.hp, max_hp)
    mp = min(base.mp, base.max_mp)
    return Stats(
        max_hp=max_hp,
        hp=hp,
        max_mp=base.max_mp,
        mp=mp,
        attack=attack,
        defense=defense,
        speed=speed,
    )
