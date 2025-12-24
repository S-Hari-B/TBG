"""Weapons repository."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import WeaponDef


class WeaponsRepository(RepositoryBase[WeaponDef]):
    """Loads and validates weapon definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("weapons.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, WeaponDef]:
        weapons: Dict[str, WeaponDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Weapon IDs must be strings.")
            weapon_data = self._require_mapping(payload, f"weapon '{raw_id}'")
            self._assert_exact_fields(
                weapon_data,
                {"name", "attack", "value"},
                f"weapon '{raw_id}'",
                optional_fields={"tags", "slot_cost", "default_basic_attack_id", "energy_bonus"},
            )

            name = self._require_str(weapon_data["name"], f"weapon '{raw_id}' name")
            attack = self._require_int(weapon_data["attack"], f"weapon '{raw_id}' attack")
            value = self._require_int(weapon_data["value"], f"weapon '{raw_id}' value")

            weapons[raw_id] = WeaponDef(id=raw_id, name=name, attack=attack, value=value)
        return weapons

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


