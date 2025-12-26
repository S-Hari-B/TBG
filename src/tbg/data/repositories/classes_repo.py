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
            starting_armour = self._require_str(
                class_data["starting_armour"], f"class '{raw_id}' starting_armour"
            )

            if starting_weapon not in weapon_ids:
                raise DataReferenceError(
                    f"class '{raw_id}' references missing weapon '{starting_weapon}'."
                )
            if starting_armour not in armour_ids:
                raise DataReferenceError(
                    f"class '{raw_id}' references missing armour '{starting_armour}'."
                )

            classes[raw_id] = ClassDef(
                id=raw_id,
                name=name,
                base_hp=base_hp,
                base_mp=base_mp,
                speed=speed,
                starting_weapon_id=starting_weapon,
                starting_armour_id=starting_armour,
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


