from __future__ import annotations

from tbg.domain.attribute_scaling import apply_attribute_scaling
from tbg.domain.entities import Attributes, BaseStats, Stats


def test_attribute_scaling_applies_vit_and_int() -> None:
    base = BaseStats(max_hp=20, max_mp=5, attack=3, defense=1, speed=4)
    attributes = Attributes(STR=0, DEX=0, INT=3, VIT=2, BOND=0)
    scaled = apply_attribute_scaling(base, attributes, current_hp=20, current_mp=5)
    assert scaled.max_hp == 26  # 20 + (2 * 3)
    assert scaled.max_mp == 11  # 5 + (3 * 2)


def test_attribute_scaling_applies_str_and_dex() -> None:
    base = BaseStats(max_hp=10, max_mp=4, attack=2, defense=0, speed=5)
    attributes = Attributes(STR=4, DEX=3, INT=0, VIT=0, BOND=0)
    scaled = apply_attribute_scaling(base, attributes, current_hp=10, current_mp=4)
    assert scaled.attack == 6  # 2 + 4
    assert scaled.speed == 8  # 5 + 3


def test_attribute_scaling_clamps_hp_mp() -> None:
    base = BaseStats(max_hp=10, max_mp=5, attack=1, defense=0, speed=1)
    attributes = Attributes(STR=0, DEX=0, INT=1, VIT=1, BOND=0)
    scaled = apply_attribute_scaling(base, attributes, current_hp=99, current_mp=42)
    assert scaled.hp == scaled.max_hp
    assert scaled.mp == scaled.max_mp
