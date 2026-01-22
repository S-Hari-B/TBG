"""Summons repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import BondScaling, SummonDef


class SummonsRepository(RepositoryBase[SummonDef]):
    """Loads and validates summon definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("summons.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, SummonDef]:
        summons: Dict[str, SummonDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Summon IDs must be strings.")
            summon_data = self._require_mapping(payload, f"summon '{raw_id}'")
            self._assert_exact_fields(
                summon_data,
                {
                    "name",
                    "max_hp",
                    "max_mp",
                    "attack",
                    "defense",
                    "speed",
                    "bond_cost",
                },
                f"summon '{raw_id}'",
                optional_fields={"tags", "bond_scaling"},
            )

            bond_scaling = self._parse_bond_scaling(
                summon_data.get("bond_scaling"),
                raw_id,
            )
            summons[raw_id] = SummonDef(
                id=raw_id,
                name=self._require_str(summon_data["name"], f"summon '{raw_id}' name"),
                max_hp=self._require_int(summon_data["max_hp"], f"summon '{raw_id}' max_hp"),
                max_mp=self._require_int(summon_data["max_mp"], f"summon '{raw_id}' max_mp"),
                attack=self._require_int(summon_data["attack"], f"summon '{raw_id}' attack"),
                defense=self._require_int(summon_data["defense"], f"summon '{raw_id}' defense"),
                speed=self._require_int(summon_data["speed"], f"summon '{raw_id}' speed"),
                bond_cost=self._require_int(summon_data["bond_cost"], f"summon '{raw_id}' bond_cost"),
                tags=tuple(self._require_str_list(summon_data.get("tags", []), f"summon '{raw_id}' tags")),
                bond_scaling=bond_scaling,
            )
        return summons

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
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result

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

    def _parse_bond_scaling(self, raw_value: object, summon_id: str) -> BondScaling:
        if raw_value is None:
            return BondScaling(hp_per_bond=0, atk_per_bond=0, def_per_bond=0, init_per_bond=0)
        mapping = self._require_mapping(raw_value, f"summon '{summon_id}' bond_scaling")
        expected = {"hp_per_bond", "atk_per_bond", "def_per_bond", "init_per_bond"}
        actual = set(mapping.keys())
        missing = expected - actual
        unknown = actual - expected
        if missing or unknown:
            msg_parts = []
            if missing:
                msg_parts.append(f"missing fields: {sorted(missing)}")
            if unknown:
                msg_parts.append(f"unknown fields: {sorted(unknown)}")
            raise DataValidationError(
                f"summon '{summon_id}' bond_scaling has schema issues ({'; '.join(msg_parts)})."
            )
        return BondScaling(
            hp_per_bond=self._require_non_negative_number(
                mapping["hp_per_bond"], f"summon '{summon_id}' bond_scaling.hp_per_bond"
            ),
            atk_per_bond=self._require_non_negative_number(
                mapping["atk_per_bond"], f"summon '{summon_id}' bond_scaling.atk_per_bond"
            ),
            def_per_bond=self._require_non_negative_number(
                mapping["def_per_bond"], f"summon '{summon_id}' bond_scaling.def_per_bond"
            ),
            init_per_bond=self._require_non_negative_number(
                mapping["init_per_bond"], f"summon '{summon_id}' bond_scaling.init_per_bond"
            ),
        )

    @staticmethod
    def _require_non_negative_number(value: object, context: str) -> float:
        if not isinstance(value, (int, float)):
            raise DataValidationError(f"{context} must be a number.")
        if value < 0:
            raise DataValidationError(f"{context} must be a non-negative number.")
        return float(value)
