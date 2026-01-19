"""Pure helpers for applying item effects to combat stats."""
from __future__ import annotations

from dataclasses import dataclass

from tbg.domain.defs import ItemDef
from tbg.domain.entities import Stats


@dataclass(slots=True)
class ResourcePool:
    """Generic mutable resource container (e.g., future energy gauge)."""

    current: int
    maximum: int


@dataclass(slots=True)
class ItemEffectResult:
    """Summary of stat deltas produced by a consumable."""

    hp_delta: int = 0
    mp_delta: int = 0
    energy_delta: int = 0

    @property
    def had_effect(self) -> bool:
        return any(delta != 0 for delta in (self.hp_delta, self.mp_delta, self.energy_delta))


def apply_item_effects(
    stats: Stats,
    item: ItemDef,
    *,
    energy_pool: ResourcePool | None = None,
) -> ItemEffectResult:
    """Apply healing/restoration effects to the provided stats."""

    result = ItemEffectResult()

    if item.heal_hp > 0:
        before = stats.hp
        stats.hp = min(stats.max_hp, stats.hp + max(0, item.heal_hp))
        result.hp_delta = stats.hp - before

    if item.heal_mp > 0:
        before = stats.mp
        stats.mp = min(stats.max_mp, stats.mp + max(0, item.heal_mp))
        result.mp_delta = stats.mp - before

    if energy_pool and item.restore_energy > 0:
        before = energy_pool.current
        energy_pool.current = min(energy_pool.maximum, energy_pool.current + max(0, item.restore_energy))
        result.energy_delta = energy_pool.current - before

    return result


