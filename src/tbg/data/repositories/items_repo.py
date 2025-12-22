"""Items repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import EffectDef, ItemDef


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
            self._assert_exact_fields(
                item_data,
                {"name", "description", "type", "effects", "value"},
                f"item '{raw_id}'",
            )

            name = self._require_str(item_data["name"], f"item '{raw_id}' name")
            description = self._require_str(item_data["description"], f"item '{raw_id}' description")
            item_type = self._require_str(item_data["type"], f"item '{raw_id}' type")
            value = self._require_int(item_data["value"], f"item '{raw_id}' value")
            effects = self._parse_effects(item_data["effects"], raw_id)

            items[raw_id] = ItemDef(
                id=raw_id,
                name=name,
                description=description,
                type=item_type,
                effects=effects,
                value=value,
            )
        return items

    def _parse_effects(self, raw_effects: object, item_id: str) -> List[EffectDef]:
        if not isinstance(raw_effects, list):
            raise DataValidationError(f"item '{item_id}' effects must be a list.")
        effects: List[EffectDef] = []
        for index, entry in enumerate(raw_effects):
            effect_context = f"item '{item_id}' effects[{index}]"
            effect_data = self._require_mapping(entry, effect_context)
            self._assert_exact_fields(effect_data, {"kind", "amount"}, effect_context)
            kind = self._require_str(effect_data["kind"], f"{effect_context} kind")
            amount = self._require_int(effect_data["amount"], f"{effect_context} amount")
            effects.append(EffectDef(kind=kind, amount=amount))
        return effects

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
    def _assert_exact_fields(payload: dict[str, object], expected_keys: set[str], context: str) -> None:
        actual_keys = set(payload.keys())
        if actual_keys != expected_keys:
            missing = expected_keys - actual_keys
            unknown = actual_keys - expected_keys
            pieces = []
            if missing:
                pieces.append(f"missing fields: {sorted(missing)}")
            if unknown:
                pieces.append(f"unknown fields: {sorted(unknown)}")
            raise DataValidationError(f"{context} has schema issues ({'; '.join(pieces)}).")


