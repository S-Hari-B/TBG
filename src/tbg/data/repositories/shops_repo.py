"""Shops repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.data.repositories.items_repo import ItemsRepository
from tbg.data.repositories.weapons_repo import WeaponsRepository
from tbg.data.repositories.armour_repo import ArmourRepository
from tbg.domain.defs import ShopDef, ShopStockEntryDef, ShopType


class ShopsRepository(RepositoryBase[ShopDef]):
    """Loads and validates shop definitions."""

    def __init__(
        self,
        base_path=None,
        *,
        items_repo: ItemsRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
    ) -> None:
        super().__init__("shops.json", base_path)
        self._items_repo = items_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo

    def _build(self, raw: dict[str, object]) -> Dict[str, ShopDef]:
        container = self._require_mapping(raw, "shops.json")
        raw_shops = self._require_mapping(container.get("shops"), "shops.json.shops")
        definitions: Dict[str, ShopDef] = {}
        for shop_id, payload in raw_shops.items():
            if not isinstance(shop_id, str):
                raise DataValidationError("Shop IDs must be strings.")
            shop_map = self._require_mapping(payload, f"shop '{shop_id}'")
            shop_id_value = self._require_str(shop_map.get("id"), f"shop '{shop_id}' id")
            if shop_id_value != shop_id:
                raise DataValidationError(
                    f"shop '{shop_id}' id must match key (found '{shop_id_value}')."
                )
            name = self._require_str(shop_map.get("name"), f"shop '{shop_id}' name")
            shop_type = self._require_str(shop_map.get("shop_type"), f"shop '{shop_id}' shop_type")
            if shop_type not in ShopType.__args__:
                raise DataValidationError(f"shop '{shop_id}' shop_type '{shop_type}' is invalid.")
            tags = tuple(self._require_str_list(shop_map.get("tags", []), f"shop '{shop_id}' tags"))
            stock_pool = self._parse_stock_pool(shop_id, shop_type, shop_map.get("stock_pool"))
            stock_size = self._require_int(
                shop_map.get("stock_size", 10), f"shop '{shop_id}' stock_size"
            )
            if stock_size <= 0:
                raise DataValidationError(f"shop '{shop_id}' stock_size must be positive.")
            definitions[shop_id] = ShopDef(
                id=shop_id,
                name=name,
                shop_type=shop_type,
                tags=tags,
                stock_pool=stock_pool,
                stock_size=stock_size,
            )
        return definitions

    def _parse_stock_pool(
        self, shop_id: str, shop_type: str, raw_pool: object
    ) -> tuple[ShopStockEntryDef, ...]:
        if raw_pool is None:
            return tuple()
        pool_data = self._require_list(raw_pool, f"shop '{shop_id}' stock_pool")
        repo = self._resolve_repo(shop_type)
        entries: List[ShopStockEntryDef] = []
        seen: set[str] = set()
        for index, entry in enumerate(pool_data):
            entry_map = self._require_mapping(entry, f"shop '{shop_id}' stock_pool[{index}]")
            item_id = self._require_str(entry_map.get("id"), f"shop '{shop_id}' stock_pool[{index}].id")
            qty = self._require_int(entry_map.get("qty"), f"shop '{shop_id}' stock_pool[{index}].qty")
            if qty <= 0:
                raise DataValidationError(
                    f"shop '{shop_id}' stock_pool[{index}].qty must be positive."
                )
            if item_id in seen:
                raise DataValidationError(
                    f"shop '{shop_id}' stock_pool has duplicate id '{item_id}'."
                )
            seen.add(item_id)
            try:
                repo.get(item_id)
            except KeyError as exc:
                raise DataReferenceError(
                    f"shop '{shop_id}' stock_pool references missing id '{item_id}'."
                ) from exc
            entries.append(ShopStockEntryDef(id=item_id, qty=qty))
        return tuple(entries)

    def _resolve_repo(self, shop_type: str):
        if shop_type == "item":
            return self._items_repo
        if shop_type == "weapon":
            return self._weapons_repo
        if shop_type == "armour":
            return self._armour_repo
        raise DataValidationError(f"shop_type '{shop_type}' is invalid.")

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object/dict.")
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
