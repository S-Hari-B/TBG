"""Attribute scaling helpers for derived combat stats."""
from __future__ import annotations

from dataclasses import dataclass

from tbg.domain.entities import Attributes, BaseStats, Stats

VIT_HP_PER_POINT = 3
INT_MP_PER_POINT = 2
STR_ATK_PER_POINT = 1
DEX_SPEED_PER_POINT = 1


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
