"""Repository for loot tables keyed by enemy tags."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.json_loader import load_json
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import LootDropDef, LootTableDef


class LootTablesRepository(RepositoryBase[LootTableDef]):
    """Loads loot table definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("loot_tables.json", base_path)

    def _load_raw(self) -> list[object]:
        file_path = self._get_file_path()
        raw = load_json(file_path)
        if not isinstance(raw, list):
            raise DataValidationError("loot_tables.json must be a list.")
        return raw

    def _build(self, raw: list[object]) -> Dict[str, LootTableDef]:
        tables: Dict[str, LootTableDef] = {}
        for index, entry in enumerate(raw):
            context = f"loot_tables[{index}]"
            table_map = self._require_mapping(entry, context)
            table_id = self._require_str(table_map.get("id"), f"{context}.id")
            required_tags = tuple(self._require_str_list(table_map.get("required_enemy_tags", []), f"{context}.required_enemy_tags"))
            forbidden_tags = tuple(self._require_str_list(table_map.get("forbidden_enemy_tags", []), f"{context}.forbidden_enemy_tags"))
            drop_entries = self._require_list(table_map.get("drops"), f"{context}.drops")
            drops: List[LootDropDef] = []
            for drop_index, drop_entry in enumerate(drop_entries):
                drop_ctx = f"{context}.drops[{drop_index}]"
                drop_map = self._require_mapping(drop_entry, drop_ctx)
                item_id = self._require_str(drop_map.get("item_id"), f"{drop_ctx}.item_id")
                chance = self._require_float(drop_map.get("chance"), f"{drop_ctx}.chance")
                if not (0.0 <= chance <= 1.0):
                    raise DataValidationError(f"{drop_ctx}.chance must be between 0 and 1.")
                min_qty = self._require_int(drop_map.get("min_qty", 1), f"{drop_ctx}.min_qty")
                max_qty = self._require_int(drop_map.get("max_qty", min_qty), f"{drop_ctx}.max_qty")
                if min_qty <= 0 or max_qty < min_qty:
                    raise DataValidationError(f"{drop_ctx} quantity range invalid.")
                drops.append(
                    LootDropDef(
                        item_id=item_id,
                        chance=chance,
                        min_qty=min_qty,
                        max_qty=max_qty,
                    )
                )
            tables[table_id] = LootTableDef(
                id=table_id,
                required_tags=required_tags,
                forbidden_tags=forbidden_tags,
                drops=drops,
            )
        return tables

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _require_list(value: object, context: str) -> list[object]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        return value

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_str_list(value: object, context: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result

    @staticmethod
    def _require_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
        return value

    @staticmethod
    def _require_float(value: object, context: str) -> float:
        if not isinstance(value, (int, float)):
            raise DataValidationError(f"{context} must be a number.")
        return float(value)

