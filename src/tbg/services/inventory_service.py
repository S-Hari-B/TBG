"""Inventory and equipment orchestration services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Sequence

from tbg.data.repositories import ArmourRepository, PartyMembersRepository, WeaponsRepository
from tbg.domain.defs import ClassDef, PartyMemberDef
from tbg.domain.inventory import ARMOUR_SLOTS, MemberEquipment
from tbg.domain.state import GameState


@dataclass(slots=True)
class PartyMemberView:
    member_id: str
    name: str
    is_player: bool


@dataclass(slots=True)
class WeaponSlotView:
    slot_index: int
    weapon_id: str | None
    weapon_name: str | None
    slot_cost: int | None


@dataclass(slots=True)
class ArmourSlotView:
    slot: str
    armour_id: str | None
    armour_name: str | None


@dataclass(slots=True)
class InventorySummary:
    weapons: List[tuple[str, str, int, int]]  # id, name, qty, slot_cost
    armour: List[tuple[str, str, int, str]]  # id, name, qty, slot
    items: List[tuple[str, int]]


@dataclass(slots=True)
class InventoryEvent:
    """Base class for inventory/equipment events."""


@dataclass(slots=True)
class ItemEquippedEvent(InventoryEvent):
    member_id: str
    member_name: str
    item_id: str
    item_name: str
    slot: str
    category: Literal["weapon", "armour"]


@dataclass(slots=True)
class ItemUnequippedEvent(InventoryEvent):
    member_id: str
    member_name: str
    item_id: str
    item_name: str
    slot: str
    category: Literal["weapon", "armour"]


@dataclass(slots=True)
class EquipFailedEvent(InventoryEvent):
    member_id: str
    member_name: str
    reason: str
    message: str


class InventoryService:
    """Service responsible for shared inventory and equipment operations."""

    def __init__(
        self,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
        party_members_repo: PartyMembersRepository,
    ) -> None:
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo
        self._party_members_repo = party_members_repo

    # ------------------------------------------------------------------ Views
    def list_party_members(self, state: GameState) -> List[PartyMemberView]:
        members: List[PartyMemberView] = []
        if state.player is not None:
            members.append(
                PartyMemberView(member_id=state.player.id, name=state.player.name, is_player=True)
            )
        for member_id in state.party_members:
            members.append(
                PartyMemberView(
                    member_id=member_id,
                    name=self._member_name(state, member_id),
                    is_player=False,
                )
            )
        return members

    def build_member_equipment_view(
        self,
        state: GameState,
        member_id: str,
    ) -> tuple[List[WeaponSlotView], List[ArmourSlotView]]:
        equipment = self._ensure_member_equipment(state, member_id)
        weapon_views: List[WeaponSlotView] = []
        for idx, weapon_id in enumerate(equipment.weapon_slots):
            if weapon_id:
                weapon_def = self._weapons_repo.get(weapon_id)
                weapon_views.append(
                    WeaponSlotView(
                        slot_index=idx,
                        weapon_id=weapon_id,
                        weapon_name=weapon_def.name,
                        slot_cost=weapon_def.slot_cost,
                    )
                )
            else:
                weapon_views.append(
                    WeaponSlotView(slot_index=idx, weapon_id=None, weapon_name=None, slot_cost=None)
                )

        armour_views: List[ArmourSlotView] = []
        for slot in ARMOUR_SLOTS:
            armour_id = equipment.armour_slots.get(slot)
            if armour_id:
                armour_def = self._armour_repo.get(armour_id)
                armour_views.append(
                    ArmourSlotView(slot=slot, armour_id=armour_id, armour_name=armour_def.name)
                )
            else:
                armour_views.append(ArmourSlotView(slot=slot, armour_id=None, armour_name=None))
        return weapon_views, armour_views

    def build_inventory_summary(self, state: GameState) -> InventorySummary:
        weapons_summary: List[tuple[str, str, int, int]] = []
        for weapon_id, qty in sorted(state.inventory.weapons.items()):
            weapon_def = self._weapons_repo.get(weapon_id)
            weapons_summary.append((weapon_id, weapon_def.name, qty, weapon_def.slot_cost))

        armour_summary: List[tuple[str, str, int, str]] = []
        for armour_id, qty in sorted(state.inventory.armour.items()):
            armour_def = self._armour_repo.get(armour_id)
            armour_summary.append((armour_id, armour_def.name, qty, armour_def.slot))

        items_summary = sorted(state.inventory.items.items())
        return InventorySummary(
            weapons=weapons_summary,
            armour=armour_summary,
            items=items_summary,
        )

    # ----------------------------------------------------------- Initialization
    def initialize_player_loadout(self, state: GameState, player_id: str, class_def: ClassDef) -> None:
        equipment = self._reset_member_equipment(state, player_id)
        for weapon_id in class_def.starting_weapons or (class_def.starting_weapon_id,):
            if not self._equip_weapon(
                state,
                player_id,
                weapon_id,
                slot_index=None,
                allow_replace=False,
                consume_from_inventory=False,
                record_events=False,
                auto_slot=True,
            ):
                state.inventory.add_weapon(weapon_id)

        armour_slots = class_def.starting_armour_slots or {"body": class_def.starting_armour_id}
        for slot, armour_id in armour_slots.items():
            self._equip_armour(
                state,
                player_id,
                armour_id,
                allow_replace=True,
                consume_from_inventory=False,
                record_events=False,
                target_slot=slot,
            )

        for item_id, qty in class_def.starting_items.items():
            state.inventory.add_item(item_id, qty)

    def initialize_party_member_loadout(
        self,
        state: GameState,
        member_id: str,
        member_def: PartyMemberDef,
    ) -> None:
        self._reset_member_equipment(state, member_id)
        for weapon_id in member_def.weapon_ids:
            if not self._equip_weapon(
                state,
                member_id,
                weapon_id,
                slot_index=None,
                allow_replace=False,
                consume_from_inventory=False,
                record_events=False,
                auto_slot=True,
            ):
                state.inventory.add_weapon(weapon_id)

        armour_slots = member_def.armour_slots or {}
        if member_def.armour_id and "body" not in armour_slots:
            armour_slots["body"] = member_def.armour_id
        for slot, armour_id in armour_slots.items():
            self._equip_armour(
                state,
                member_id,
                armour_id,
                allow_replace=True,
                consume_from_inventory=False,
                record_events=False,
                target_slot=slot,
            )

    # ----------------------------------------------------------- Weapon actions
    def equip_weapon(
        self,
        state: GameState,
        member_id: str,
        weapon_id: str,
        *,
        slot_index: int | None,
        allow_replace: bool = False,
    ) -> List[InventoryEvent]:
        success, events = self._equip_weapon(
            state,
            member_id,
            weapon_id,
            slot_index=slot_index,
            allow_replace=allow_replace,
            consume_from_inventory=True,
            record_events=True,
            auto_slot=False,
        )
        if not success and not events:
            member_name = self._member_name(state, member_id)
            events = [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="unknown",
                    message="Unable to equip weapon.",
                )
            ]
        return events

    def unequip_weapon_slot(self, state: GameState, member_id: str, slot_index: int) -> List[InventoryEvent]:
        events: List[InventoryEvent] = []
        equipment = self._ensure_member_equipment(state, member_id)
        if slot_index not in (0, 1):
            return [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=self._member_name(state, member_id),
                    reason="invalid_slot",
                    message="Invalid weapon slot selected.",
                )
            ]
        weapon_id = equipment.weapon_slots[slot_index]
        if not weapon_id:
            return [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=self._member_name(state, member_id),
                    reason="slot_empty",
                    message="Weapon slot is already empty.",
                )
            ]

        weapon_def = self._weapons_repo.get(weapon_id)
        slots_to_clear = {slot_index}
        if weapon_def.slot_cost == 2:
            slots_to_clear = {0, 1}
        for idx in slots_to_clear:
            equipment.weapon_slots[idx] = None
        state.inventory.add_weapon(weapon_id)
        events.append(
            ItemUnequippedEvent(
                member_id=member_id,
                member_name=self._member_name(state, member_id),
                item_id=weapon_id,
                item_name=weapon_def.name,
                slot=f"weapon_slot_{slot_index + 1}",
                category="weapon",
            )
        )
        return events

    # ----------------------------------------------------------- Armour actions
    def equip_armour(
        self,
        state: GameState,
        member_id: str,
        armour_id: str,
        *,
        allow_replace: bool = False,
    ) -> List[InventoryEvent]:
        success, events = self._equip_armour(
            state,
            member_id,
            armour_id,
            allow_replace=allow_replace,
            consume_from_inventory=True,
            record_events=True,
        )
        if not success and not events:
            events = [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=self._member_name(state, member_id),
                    reason="unknown",
                    message="Unable to equip armour.",
                )
            ]
        return events

    def unequip_armour_slot(self, state: GameState, member_id: str, slot: str) -> List[InventoryEvent]:
        events: List[InventoryEvent] = []
        equipment = self._ensure_member_equipment(state, member_id)
        slot = slot.lower()
        if slot not in ARMOUR_SLOTS:
            return [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=self._member_name(state, member_id),
                    reason="invalid_slot",
                    message="Invalid armour slot selected.",
                )
            ]
        armour_id = equipment.armour_slots.get(slot)
        if not armour_id:
            return [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=self._member_name(state, member_id),
                    reason="slot_empty",
                    message="Armour slot is already empty.",
                )
            ]
        armour_def = self._armour_repo.get(armour_id)
        equipment.armour_slots[slot] = None
        state.inventory.add_armour(armour_id)
        events.append(
            ItemUnequippedEvent(
                member_id=member_id,
                member_name=self._member_name(state, member_id),
                item_id=armour_id,
                item_name=armour_def.name,
                slot=f"armour_{slot}",
                category="armour",
            )
        )
        return events

    # ------------------------------------------------------------ Internal impl
    def _equip_weapon(
        self,
        state: GameState,
        member_id: str,
        weapon_id: str,
        *,
        slot_index: int | None,
        allow_replace: bool,
        consume_from_inventory: bool,
        record_events: bool,
        auto_slot: bool,
    ) -> tuple[bool, List[InventoryEvent]]:
        events: List[InventoryEvent] = []
        member_name = self._member_name(state, member_id)
        try:
            weapon_def = self._weapons_repo.get(weapon_id)
        except KeyError:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="unknown_weapon",
                    message="Weapon is not recognized by the data repository.",
                )
            ]

        equipment = self._ensure_member_equipment(state, member_id)
        target_slots = self._determine_required_slots(
            weapon_def, slot_index, auto_slot, equipment
        )
        if target_slots is None:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="invalid_slot",
                    message="Please choose a valid weapon slot.",
                )
            ]

        slots_to_clear = self._slots_to_clear(equipment, target_slots)
        blocking = [idx for idx in slots_to_clear if equipment.weapon_slots[idx]]
        if blocking and not allow_replace:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="slot_occupied",
                    message="Weapon slot is occupied. Choose a different slot or allow replacement.",
                )
            ]

        if consume_from_inventory and not state.inventory.remove_weapon(weapon_id):
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="not_in_inventory",
                    message="Weapon is not available in the shared inventory.",
                )
            ]

        removed_weapons: Dict[str, int] = {}
        for idx in slots_to_clear:
            occupant = equipment.weapon_slots[idx]
            if occupant and occupant not in removed_weapons:
                removed_weapons[occupant] = idx
        for idx in slots_to_clear:
            equipment.weapon_slots[idx] = None

        for removed_weapon_id, removed_slot in removed_weapons.items():
            state.inventory.add_weapon(removed_weapon_id)
            if record_events:
                removed_def = self._weapons_repo.get(removed_weapon_id)
                events.append(
                    ItemUnequippedEvent(
                        member_id=member_id,
                        member_name=member_name,
                        item_id=removed_weapon_id,
                        item_name=removed_def.name,
                        slot=f"weapon_slot_{removed_slot + 1}",
                        category="weapon",
                    )
                )

        for idx in target_slots:
            equipment.weapon_slots[idx] = weapon_id

        if record_events:
            events.append(
                ItemEquippedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    item_id=weapon_id,
                    item_name=weapon_def.name,
                    slot=f"weapon_slot_{target_slots[0] + 1}",
                    category="weapon",
                )
            )
        return True, events

    def _equip_armour(
        self,
        state: GameState,
        member_id: str,
        armour_id: str,
        *,
        allow_replace: bool,
        consume_from_inventory: bool,
        record_events: bool,
        target_slot: str | None = None,
    ) -> tuple[bool, List[InventoryEvent]]:
        events: List[InventoryEvent] = []
        member_name = self._member_name(state, member_id)
        try:
            armour_def = self._armour_repo.get(armour_id)
        except KeyError:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="unknown_armour",
                    message="Armour is not recognized by the data repository.",
                )
            ]

        slot = target_slot or armour_def.slot
        if slot not in ARMOUR_SLOTS:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="invalid_slot",
                    message="Armour slot is invalid.",
                )
            ]

        equipment = self._ensure_member_equipment(state, member_id)
        occupant = equipment.armour_slots.get(slot)
        if occupant and not allow_replace:
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="slot_occupied",
                    message="Armour slot already has equipment. Allow replacement to continue.",
                )
            ]
        if consume_from_inventory and not state.inventory.remove_armour(armour_id):
            return False, [
                EquipFailedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    reason="not_in_inventory",
                    message="Armour is not available in the shared inventory.",
                )
            ]
        if occupant:
            state.inventory.add_armour(occupant)
            if record_events:
                occupied_def = self._armour_repo.get(occupant)
                events.append(
                    ItemUnequippedEvent(
                        member_id=member_id,
                        member_name=member_name,
                        item_id=occupant,
                        item_name=occupied_def.name,
                        slot=f"armour_{slot}",
                        category="armour",
                    )
                )
        equipment.armour_slots[slot] = armour_id
        if record_events:
            events.append(
                ItemEquippedEvent(
                    member_id=member_id,
                    member_name=member_name,
                    item_id=armour_id,
                    item_name=armour_def.name,
                    slot=f"armour_{slot}",
                    category="armour",
                )
            )
        return True, events

    # ------------------------------------------------------------- Helper utils
    def _member_name(self, state: GameState, member_id: str) -> str:
        if state.player and member_id == state.player.id:
            return state.player.name
        try:
            member = self._party_members_repo.get(member_id)
            return member.name
        except KeyError:
            return member_id

    def _ensure_member_equipment(self, state: GameState, member_id: str) -> MemberEquipment:
        if member_id not in state.equipment:
            state.equipment[member_id] = MemberEquipment()
        return state.equipment[member_id]

    def _reset_member_equipment(self, state: GameState, member_id: str) -> MemberEquipment:
        state.equipment[member_id] = MemberEquipment()
        return state.equipment[member_id]

    def _determine_required_slots(
        self,
        weapon_def,
        slot_index: int | None,
        auto_slot: bool,
        equipment: MemberEquipment,
    ) -> List[int] | None:
        if weapon_def.slot_cost == 2:
            return [0, 1]
        if slot_index is None:
            if auto_slot:
                if equipment.weapon_slots[0] is None:
                    return [0]
                if equipment.weapon_slots[1] is None:
                    return [1]
                return [0]
            return None
        if slot_index not in (0, 1):
            return None
        return [slot_index]

    def _slots_to_clear(self, equipment: MemberEquipment, target_slots: Sequence[int]) -> set[int]:
        slots = set(target_slots)
        for idx in list(slots):
            occupant = equipment.weapon_slots[idx]
            if not occupant:
                continue
            try:
                occupant_def = self._weapons_repo.get(occupant)
            except KeyError:
                continue
            if occupant_def.slot_cost == 2:
                slots.update({0, 1})
        return slots

