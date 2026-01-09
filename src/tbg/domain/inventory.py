"""Shared party inventory and equipment structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


ARMOUR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "boots")


def _default_armour_slots() -> Dict[str, str | None]:
    return {slot: None for slot in ARMOUR_SLOTS}


@dataclass(slots=True)
class MemberEquipment:
    """Tracks equipped weapon and armour ids for a party member."""

    weapon_slots: List[str | None] = field(default_factory=lambda: [None, None])
    armour_slots: Dict[str, str | None] = field(default_factory=_default_armour_slots)


@dataclass(slots=True)
class PartyInventory:
    """Shared inventory buckets for the entire party."""

    weapons: Dict[str, int] = field(default_factory=dict)
    armour: Dict[str, int] = field(default_factory=dict)
    items: Dict[str, int] = field(default_factory=dict)

    def add_weapon(self, weapon_id: str, quantity: int = 1) -> None:
        self._add(self.weapons, weapon_id, quantity)

    def remove_weapon(self, weapon_id: str, quantity: int = 1) -> bool:
        return self._remove(self.weapons, weapon_id, quantity)

    def add_armour(self, armour_id: str, quantity: int = 1) -> None:
        self._add(self.armour, armour_id, quantity)

    def remove_armour(self, armour_id: str, quantity: int = 1) -> bool:
        return self._remove(self.armour, armour_id, quantity)

    def add_item(self, item_id: str, quantity: int = 1) -> None:
        self._add(self.items, item_id, quantity)

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        return self._remove(self.items, item_id, quantity)

    @staticmethod
    def _add(store: Dict[str, int], item_id: str, quantity: int) -> None:
        if quantity <= 0:
            return
        store[item_id] = store.get(item_id, 0) + quantity

    @staticmethod
    def _remove(store: Dict[str, int], item_id: str, quantity: int) -> bool:
        if quantity <= 0:
            return True
        current = store.get(item_id, 0)
        if current < quantity:
            return False
        new_value = current - quantity
        if new_value == 0:
            store.pop(item_id, None)
        else:
            store[item_id] = new_value
        return True


