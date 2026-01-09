"""Armour repository."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import ArmourDef


class ArmourRepository(RepositoryBase[ArmourDef]):
    """Loads and validates armour definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("armour.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, ArmourDef]:
        armour: Dict[str, ArmourDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Armour IDs must be strings.")
            armour_data = self._require_mapping(payload, f"armour '{raw_id}'")
            self._assert_exact_fields(
                armour_data,
                {"name", "slot", "defense", "value"},
                f"armour '{raw_id}'",
                optional_fields={"tags", "hp_bonus"},
            )

            name = self._require_str(armour_data["name"], f"armour '{raw_id}' name")
            slot = self._require_slot(armour_data["slot"], f"armour '{raw_id}' slot")
            defense = self._require_int(armour_data["defense"], f"armour '{raw_id}' defense")
            value = self._require_int(armour_data["value"], f"armour '{raw_id}' value")
            tags = tuple(self._require_str_list(armour_data.get("tags", []), f"armour '{raw_id}' tags"))
            hp_bonus = self._require_int(armour_data.get("hp_bonus", 0), f"armour '{raw_id}' hp_bonus")

            armour[raw_id] = ArmourDef(
                id=raw_id,
                name=name,
                slot=slot,
                defense=defense,
                value=value,
                tags=tags,
                hp_bonus=hp_bonus,
            )
        return armour

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
        if value is None:
            return []
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(item)
        return result

    @staticmethod
    def _require_slot(value: object, context: str) -> str:
        slot = ArmourRepository._require_str(value, context)
        if slot not in {"head", "body", "hands", "boots"}:
            raise DataValidationError(f"{context} must be one of head, body, hands, boots.")
        return slot


