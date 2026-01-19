from __future__ import annotations

from tbg.domain.defs import ItemDef
from tbg.domain.entities import Stats
from tbg.domain.item_effects import ResourcePool, apply_item_effects


def test_item_effects_restore_hp_and_mp_with_clamp() -> None:
    stats = Stats(max_hp=30, hp=10, max_mp=15, mp=5, attack=3, defense=2, speed=4)
    item = ItemDef(
        id="potion_combo",
        name="Combo Potion",
        kind="consumable",
        value=10,
        heal_hp=25,
        heal_mp=20,
    )

    result = apply_item_effects(stats, item)

    assert stats.hp == 30
    assert stats.mp == 15
    assert result.hp_delta == 20
    assert result.mp_delta == 10
    assert result.had_effect is True


def test_item_effects_report_no_effect_when_already_full() -> None:
    stats = Stats(max_hp=20, hp=20, max_mp=10, mp=10, attack=1, defense=1, speed=1)
    item = ItemDef(id="potion_hp_small", name="Potion", kind="consumable", value=5)

    result = apply_item_effects(stats, item)

    assert result.had_effect is False
    assert stats.hp == 20
    assert stats.mp == 10


def test_item_effects_restore_energy_pool_when_provided() -> None:
    stats = Stats(max_hp=10, hp=10, max_mp=5, mp=5, attack=1, defense=1, speed=1)
    pool = ResourcePool(current=2, maximum=6)
    item = ItemDef(
        id="energy_shard",
        name="Energy Shard",
        kind="consumable",
        value=4,
        restore_energy=5,
    )

    result = apply_item_effects(stats, item, energy_pool=pool)

    assert pool.current == 6
    assert result.energy_delta == 4
    assert result.had_effect is True


