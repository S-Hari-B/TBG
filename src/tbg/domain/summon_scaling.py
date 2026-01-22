"""Summon stat scaling helpers."""
from __future__ import annotations

from tbg.domain.defs import BondScaling
from tbg.domain.entities import Stats


def scale_summon_stats(base: Stats, owner_bond: int, scaling: BondScaling) -> Stats:
    bond = max(0, owner_bond)
    max_hp = int(base.max_hp + bond * scaling.hp_per_bond)
    attack = int(base.attack + bond * scaling.atk_per_bond)
    defense = int(base.defense + bond * scaling.def_per_bond)
    speed = int(base.speed + bond * scaling.init_per_bond)
    # Deterministic floor conversion: int(...) is applied once per stat.
    max_hp = max(1, max_hp)
    attack = max(0, attack)
    defense = max(0, defense)
    speed = max(0, speed)
    return Stats(
        max_hp=max_hp,
        hp=max_hp,
        max_mp=base.max_mp,
        mp=base.max_mp,
        attack=attack,
        defense=defense,
        speed=speed,
    )
