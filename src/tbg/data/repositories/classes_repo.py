"""Classes repository with reference validation."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.armour_repo import ArmourRepository
from tbg.data.repositories.base import RepositoryBase
from tbg.data.repositories.weapons_repo import WeaponsRepository
from tbg.domain.defs import ClassDef


class ClassesRepository(RepositoryBase[ClassDef]):
    """Loads classes and ensures referenced equipment exists."""

    def __init__(
        self,
        weapons_repo: WeaponsRepository | None = None,
        armour_repo: ArmourRepository | None = None,
        base_path=None,
    ) -> None:
        super().__init__("classes.json", base_path)
        self._weapons_repo = weapons_repo or WeaponsRepository(base_path=base_path)
        self._armour_repo = armour_repo or ArmourRepository(base_path=base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, ClassDef]:
        weapon_ids = {weapon.id for weapon in self._weapons_repo.all()}
        armour_ids = {armour.id for armour in self._armour_repo.all()}

        classes: Dict[str, ClassDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Class IDs must be strings.")
            class_data = self._require_mapping(payload, f"class '{raw_id}'")
            self._assert_exact_fields(
                class_data,
                {"name", "base_hp", "base_mp", "speed", "starting_weapon", "starting_armour"},
                f"class '{raw_id}'",
                optional_fields={"starting_weapons", "starting_items", "starting_abilities"},
            )

            name = self._require_str(class_data["name"], f"class '{raw_id}' name")
            base_hp = self._require_int(class_data["base_hp"], f"class '{raw_id}' base_hp")
            base_mp = self._require_int(class_data["base_mp"], f"class '{raw_id}' base_mp")
            speed = self._require_int(class_data["speed"], f"class '{raw_id}' speed")
            starting_weapon = self._require_str(
                class_data["starting_weapon"], f"class '{raw_id}' starting_weapon"
            )
            if starting_weapon not in weapon_ids:
                raise DataReferenceError(
                    f"class '{raw_id}' references missing weapon '{starting_weapon}'."
                )

            starting_weapons: list[str] = []
            if "starting_weapons" in class_data:
                starting_weapons = self._require_str_list(
                    class_data["starting_weapons"], f"class '{raw_id}' starting_weapons"
                )
            if not starting_weapons:
                starting_weapons = [starting_weapon]
            elif starting_weapon not in starting_weapons:
                starting_weapons.insert(0, starting_weapon)
            for weapon_id in starting_weapons:
                if weapon_id not in weapon_ids:
                    raise DataReferenceError(
                        f"class '{raw_id}' references missing weapon '{weapon_id}' in starting_weapons."
                    )

            armour_slots = self._parse_starting_armour(
                class_data["starting_armour"], armour_ids, raw_id
            )
            starting_armour = armour_slots.get("body")
            if not starting_armour:
                raise DataValidationError(
                    f"class '{raw_id}' starting_armour must include a body slot."
                )

            starting_items: dict[str, int] = {}
            if "starting_items" in class_data:
                items = self._require_mapping(class_data["starting_items"], f"class '{raw_id}' starting_items")
                for item_id, qty in items.items():
                    starting_items[self._require_str(item_id, "item id")] = self._require_int(
                        qty, f"class '{raw_id}' starting_items[{item_id}]"
                    )
            else:
                starting_items = {}

            classes[raw_id] = ClassDef(
                id=raw_id,
                name=name,
                base_hp=base_hp,
                base_mp=base_mp,
                speed=speed,
                starting_weapon_id=starting_weapon,
                starting_armour_id=starting_armour,
                starting_weapons=tuple(starting_weapons),
                starting_armour_slots=armour_slots,
                starting_items=starting_items,
            )
        return classes

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
        return value

    @staticmethod
    def _assert_exact_fields(
        payload: dict[str, object],
        expected_keys: set[str],
        context: str,
        *,
        optional_fields: set[str] | None = None,
    ) -> None:
        actual_keys = set(payload.keys())
        optional = optional_fields or set()
        missing = expected_keys - actual_keys
        unknown = actual_keys - expected_keys - optional
        if missing or unknown:
            msg_parts = []
            if missing:
                msg_parts.append(f"missing fields: {sorted(missing)}")
            if unknown:
                msg_parts.append(f"unknown fields: {sorted(unknown)}")
            raise DataValidationError(f"{context} has schema issues ({'; '.join(msg_parts)}).")

    @staticmethod
    def _require_str_list(value: object, context: str) -> list[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _require_slot_name(slot: str, context: str) -> str:
        if slot not in {"head", "body", "hands", "boots"}:
            raise DataValidationError(f"{context} must be one of head, body, hands, boots.")
        return slot

    def _parse_starting_armour(
        self,
        raw_value: object,
        armour_ids: set[str],
        class_id: str,
    ) -> dict[str, str]:
        context = f"class '{class_id}' starting_armour"
        armour_slots: dict[str, str] = {}
        if isinstance(raw_value, str):
            armour_id = self._require_str(raw_value, context)
            if armour_id not in armour_ids:
                raise DataReferenceError(f"{context} references missing armour '{armour_id}'.")
            armour_slots["body"] = armour_id
            return armour_slots

        slot_mapping = self._require_mapping(raw_value, context)
        for slot_name, armour_id in slot_mapping.items():
            slot = self._require_slot_name(slot_name, f"{context}.{slot_name}")
            armour_id_str = self._require_str(armour_id, f"{context}.{slot_name}")
            if armour_id_str not in armour_ids:
                raise DataReferenceError(
                    f"{context} references missing armour '{armour_id_str}' in slot '{slot}'."
                )
            armour_slots[slot] = armour_id_str
        return armour_slots


