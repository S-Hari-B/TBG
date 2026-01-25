"""Attribute scaling helpers for derived combat stats."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from tbg.domain.entities import Attributes, BaseStats, Stats

VIT_HP_PER_POINT = 3
INT_MP_PER_POINT = 2
STR_ATK_PER_POINT = 1
DEX_SPEED_PER_POINT = 1
ELEMENTAL_SKILL_TAGS = {"fire"}
PHYSICAL_SKILL_TAG = "physical"
DEX_ATK_MULTIPLIER = 0.75


@dataclass(frozen=True, slots=True)
class AttributeContributions:
    max_hp: int
    max_mp: int
    attack: int
    speed: int
    bond_reserved: int


@dataclass(frozen=True, slots=True)
class AttributeScalingBreakdown:
    base_stats: Stats
    attributes: Attributes
    contributions: AttributeContributions
    final_stats: Stats
    hp_clamped: bool
    mp_clamped: bool
    hp_before_clamp: int
    mp_before_clamp: int


def compute_attribute_contributions(attributes: Attributes) -> AttributeContributions:
    return AttributeContributions(
        max_hp=attributes.VIT * VIT_HP_PER_POINT,
        max_mp=attributes.INT * INT_MP_PER_POINT,
        attack=attributes.STR * STR_ATK_PER_POINT,
        speed=attributes.DEX * DEX_SPEED_PER_POINT,
        bond_reserved=attributes.BOND,
    )


def _resolve_action_attack_weights(skill_tags: Sequence[str]) -> tuple[float, float]:
    is_physical = PHYSICAL_SKILL_TAG in skill_tags
    is_magical = bool(ELEMENTAL_SKILL_TAGS.intersection(skill_tags))
    if is_physical and is_magical:
        return 0.5, 0.5
    if is_magical:
        return 0.0, 1.0
    return 1.0, 0.0


def compute_action_attack(
    base_attack: int,
    attributes: Attributes,
    skill_tags: Sequence[str],
    weapon_tags: Sequence[str],
) -> int:
    """Compute an action-specific attack value from skill tags."""
    str_weight, int_weight = _resolve_action_attack_weights(skill_tags)
    physical_multiplier = DEX_ATK_MULTIPLIER if "finesse" in weapon_tags else 1.0
    physical_attribute = attributes.DEX if "finesse" in weapon_tags else attributes.STR
    attribute_bonus = (
        physical_attribute * STR_ATK_PER_POINT * physical_multiplier * str_weight
        + attributes.INT * STR_ATK_PER_POINT * int_weight
    )
    return max(1, base_attack + int(attribute_bonus))


def apply_attribute_scaling(
    base_stats: BaseStats,
    attributes: Attributes,
    *,
    current_hp: int,
    current_mp: int,
) -> Stats:
    contributions = compute_attribute_contributions(attributes)
    max_hp = base_stats.max_hp + contributions.max_hp
    max_mp = base_stats.max_mp + contributions.max_mp
    hp = min(current_hp, max_hp)
    mp = min(current_mp, max_mp)
    return Stats(
        max_hp=max_hp,
        hp=hp,
        max_mp=max_mp,
        mp=mp,
        attack=base_stats.attack + contributions.attack,
        defense=base_stats.defense,
        speed=base_stats.speed + contributions.speed,
    )


def build_attribute_scaling_breakdown(
    base_stats: BaseStats,
    attributes: Attributes,
    *,
    current_hp: int,
    current_mp: int,
) -> AttributeScalingBreakdown:
    contributions = compute_attribute_contributions(attributes)
    final_stats = apply_attribute_scaling(
        base_stats,
        attributes,
        current_hp=current_hp,
        current_mp=current_mp,
    )
    return AttributeScalingBreakdown(
        base_stats=Stats(
            max_hp=base_stats.max_hp,
            hp=base_stats.max_hp,
            max_mp=base_stats.max_mp,
            mp=base_stats.max_mp,
            attack=base_stats.attack,
            defense=base_stats.defense,
            speed=base_stats.speed,
        ),
        attributes=attributes,
        contributions=contributions,
        final_stats=final_stats,
        hp_clamped=final_stats.hp < current_hp,
        mp_clamped=final_stats.mp < current_mp,
        hp_before_clamp=current_hp,
        mp_before_clamp=current_mp,
    )
