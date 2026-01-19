"""Items repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import ItemDef


class ItemsRepository(RepositoryBase[ItemDef]):
    """Loads and validates item definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("items.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, ItemDef]:
        items: Dict[str, ItemDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Item IDs must be strings.")
            item_data = self._require_mapping(payload, f"item '{raw_id}'")
            self._assert_allowed_fields(
                item_data,
                required={"name", "kind", "value"},
                optional={
                    "heal_hp",
                    "heal_mp",
                    "restore_energy",
                    "targeting",
                    "debuff_attack_flat",
                    "debuff_defense_flat",
                },
                context=f"item '{raw_id}'",
            )

            name = self._require_str(item_data["name"], f"item '{raw_id}' name")
            kind = self._require_str(item_data["kind"], f"item '{raw_id}' kind")
            value = self._require_int(item_data["value"], f"item '{raw_id}' value")
            heal_hp = self._require_int(item_data.get("heal_hp", 0), f"item '{raw_id}' heal_hp")
            heal_mp = self._require_int(item_data.get("heal_mp", 0), f"item '{raw_id}' heal_mp")
            restore = self._require_int(item_data.get("restore_energy", 0), f"item '{raw_id}' restore_energy")
            targeting = self._normalize_targeting(item_data.get("targeting", "self"), raw_id)
            debuff_attack = self._require_int(
                item_data.get("debuff_attack_flat", 0), f"item '{raw_id}' debuff_attack_flat"
            )
            debuff_defense = self._require_int(
                item_data.get("debuff_defense_flat", 0), f"item '{raw_id}' debuff_defense_flat"
            )
            self._validate_debuff_fields(raw_id, debuff_attack, debuff_defense)

            items[raw_id] = ItemDef(
                id=raw_id,
                name=name,
                kind=kind,
                value=value,
                heal_hp=heal_hp,
                heal_mp=heal_mp,
                restore_energy=restore,
                targeting=targeting,
                debuff_attack_flat=debuff_attack,
                debuff_defense_flat=debuff_defense,
            )
        return items

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
    def _normalize_targeting(value: object, item_id: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"item '{item_id}' targeting must be a string.")
        normalized = value.strip().lower() or "self"
        if normalized not in {"self", "ally", "enemy", "any"}:
            raise DataValidationError(
                f"item '{item_id}' targeting must be one of ['self', 'ally', 'enemy', 'any']."
            )
        return normalized

    @staticmethod
    def _validate_debuff_fields(item_id: str, attack: int, defense: int) -> None:
        if attack < 0 or defense < 0:
            raise DataValidationError(f"item '{item_id}' debuff amounts must be non-negative.")
        if attack and defense:
            raise DataValidationError(
                f"item '{item_id}' cannot define both debuff_attack_flat and debuff_defense_flat."
            )

    @staticmethod
    def _assert_allowed_fields(
        mapping: dict[str, object],
        *,
        required: List[str],
        optional: List[str],
        context: str,
    ) -> None:
        required_set = set(required)
        optional_set = set(optional)
        actual = set(mapping.keys())
        missing = required_set - actual
        unknown = actual - required_set - optional_set
        if missing or unknown:
            msg = []
            if missing:
                msg.append(f"missing fields: {sorted(missing)}")
            if unknown:
                msg.append(f"unknown fields: {sorted(unknown)}")
            raise DataValidationError(f"{context} has schema issues ({'; '.join(msg)}).")


