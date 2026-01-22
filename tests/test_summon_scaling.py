from tbg.domain.defs import BondScaling
from tbg.domain.entities import Stats
from tbg.domain.summon_scaling import scale_summon_stats


def test_scale_summon_stats_applies_bond_scaling() -> None:
    base = Stats(max_hp=10, hp=10, max_mp=4, mp=4, attack=3, defense=1, speed=2)
    scaling = BondScaling(hp_per_bond=1, atk_per_bond=2, def_per_bond=0, init_per_bond=1)

    scaled = scale_summon_stats(base, owner_bond=5, scaling=scaling)

    assert scaled.max_hp == 15
    assert scaled.hp == 15
    assert scaled.attack == 13
    assert scaled.defense == 1
    assert scaled.speed == 7
    assert scaled.max_mp == 4
    assert scaled.mp == 4


def test_scale_summon_stats_floors_fractional_scaling() -> None:
    base = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=2)
    scaling = BondScaling(hp_per_bond=0.5, atk_per_bond=1.5, def_per_bond=0.0, init_per_bond=0.5)

    scaled = scale_summon_stats(base, owner_bond=10, scaling=scaling)

    assert scaled.max_hp == 15
    assert scaled.attack == 18
    assert scaled.speed == 7


def test_scale_summon_stats_fractional_low_bond() -> None:
    base = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=2)
    scaling = BondScaling(hp_per_bond=0.8, atk_per_bond=0.5, def_per_bond=0.0, init_per_bond=0.0)

    scaled = scale_summon_stats(base, owner_bond=5, scaling=scaling)

    assert scaled.max_hp == 14
    assert scaled.attack == 5
