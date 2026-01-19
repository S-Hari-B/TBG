"""Shop service for deterministic buy/sell flows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from tbg.data.repositories import ArmourRepository, ItemsRepository, ShopsRepository, WeaponsRepository
from tbg.domain.defs import ShopDef, ShopStockEntryDef, ShopType
from tbg.domain.state import GameState


@dataclass(slots=True)
class ShopEvent:
    """Base class for shop-related events."""


@dataclass(slots=True)
class ShopPurchaseEvent(ShopEvent):
    item_id: str
    item_name: str
    quantity: int
    total_cost: int
    total_gold: int


@dataclass(slots=True)
class ShopSaleEvent(ShopEvent):
    item_id: str
    item_name: str
    quantity: int
    total_gain: int
    total_gold: int


@dataclass(slots=True)
class ShopActionFailedEvent(ShopEvent):
    reason: str
    message: str


@dataclass(slots=True)
class ShopDebugGoldGrantedEvent(ShopEvent):
    amount: int
    total_gold: int


@dataclass(slots=True)
class ShopSummaryView:
    shop_id: str
    name: str
    shop_type: ShopType


@dataclass(slots=True)
class ShopEntryView:
    item_id: str
    name: str
    price: int
    owned: int
    stock: int


@dataclass(slots=True)
class ShopView:
    shop_id: str
    name: str
    shop_type: ShopType
    gold: int
    entries: List[ShopEntryView] = field(default_factory=list)


@dataclass(slots=True)
class ShopBatchResult:
    events: List[ShopEvent]
    success_count: int
    failure_count: int


class ShopService:
    """Deterministic shop stock and transaction logic."""

    def __init__(
        self,
        *,
        shops_repo: ShopsRepository,
        items_repo: ItemsRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
    ) -> None:
        self._shops_repo = shops_repo
        self._items_repo = items_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo

    def list_shops_for_location(self, location_tags: Sequence[str]) -> List[ShopSummaryView]:
        tags = set(location_tags)
        available = [
            shop for shop in self._shops_repo.all() if tags & set(shop.tags)
        ]
        return [
            ShopSummaryView(shop_id=shop.id, name=shop.name, shop_type=shop.shop_type)
            for shop in sorted(available, key=lambda entry: entry.id)
        ]

    def build_shop_view(self, state: GameState, location_id: str, shop_id: str) -> ShopView:
        shop = self._shops_repo.get(shop_id)
        stock_entries = self._resolve_stock_entries(shop, state, location_id)
        remaining = self._ensure_stock_for_shop(state, location_id, shop, stock_entries)
        entries: List[ShopEntryView] = []
        for entry in stock_entries:
            remaining_qty = remaining.get(entry.id, 0)
            if remaining_qty <= 0:
                continue
            item_id = entry.id
            name = self._resolve_name(shop.shop_type, item_id)
            price = self._buy_price(shop.shop_type, item_id)
            owned = self._owned_quantity(state, shop.shop_type, item_id)
            entries.append(
                ShopEntryView(
                    item_id=item_id,
                    name=name,
                    price=price,
                    owned=owned,
                    stock=remaining_qty,
                )
            )
        return ShopView(
            shop_id=shop.id,
            name=shop.name,
            shop_type=shop.shop_type,
            gold=state.gold,
            entries=entries,
        )

    def build_sell_view(self, state: GameState, shop_id: str) -> ShopView:
        shop = self._shops_repo.get(shop_id)
        entries: List[ShopEntryView] = []
        owned = self._owned_items(state, shop.shop_type)
        for item_id in sorted(owned.keys()):
            quantity = owned[item_id]
            if quantity <= 0:
                continue
            entries.append(
                ShopEntryView(
                    item_id=item_id,
                    name=self._resolve_name(shop.shop_type, item_id),
                    price=self._sell_price(shop.shop_type, item_id),
                    owned=quantity,
                    stock=0,
                )
            )
        return ShopView(
            shop_id=shop.id,
            name=shop.name,
            shop_type=shop.shop_type,
            gold=state.gold,
            entries=entries,
        )

    def buy(
        self, state: GameState, location_id: str, shop_id: str, item_id: str, quantity: int = 1
    ) -> List[ShopEvent]:
        if quantity <= 0:
            return [ShopActionFailedEvent(reason="invalid_quantity", message="Quantity must be positive.")]
        shop = self._shops_repo.get(shop_id)
        stock_entries = self._resolve_stock_entries(shop, state, location_id)
        remaining = self._ensure_stock_for_shop(state, location_id, shop, stock_entries)
        if item_id not in remaining:
            return [ShopActionFailedEvent(reason="not_in_stock", message="Item is not available here.")]
        if remaining[item_id] < quantity:
            return [ShopActionFailedEvent(reason="out_of_stock", message="Item is sold out.")]
        price = self._buy_price(shop.shop_type, item_id)
        total_cost = price * quantity
        if state.gold < total_cost:
            return [ShopActionFailedEvent(reason="insufficient_gold", message="Not enough gold.")]
        self._add_to_inventory(state, shop.shop_type, item_id, quantity)
        state.gold -= total_cost
        remaining[item_id] -= quantity
        return [
            ShopPurchaseEvent(
                item_id=item_id,
                item_name=self._resolve_name(shop.shop_type, item_id),
                quantity=quantity,
                total_cost=total_cost,
                total_gold=state.gold,
            )
        ]

    def buy_many(
        self, state: GameState, location_id: str, shop_id: str, item_ids: Sequence[str]
    ) -> ShopBatchResult:
        events: List[ShopEvent] = []
        success = 0
        failure = 0
        for item_id in item_ids:
            result = self.buy(state, location_id, shop_id, item_id, quantity=1)
            events.extend(result)
            if result and isinstance(result[0], ShopPurchaseEvent):
                success += 1
            else:
                failure += 1
        return ShopBatchResult(events=events, success_count=success, failure_count=failure)

    def sell(
        self, state: GameState, shop_id: str, item_id: str, quantity: int = 1
    ) -> List[ShopEvent]:
        if quantity <= 0:
            return [ShopActionFailedEvent(reason="invalid_quantity", message="Quantity must be positive.")]
        shop = self._shops_repo.get(shop_id)
        if not self._remove_from_inventory(state, shop.shop_type, item_id, quantity):
            return [ShopActionFailedEvent(reason="not_owned", message="Item not available to sell.")]
        price = self._sell_price(shop.shop_type, item_id)
        total_gain = price * quantity
        state.gold += total_gain
        return [
            ShopSaleEvent(
                item_id=item_id,
                item_name=self._resolve_name(shop.shop_type, item_id),
                quantity=quantity,
                total_gain=total_gain,
                total_gold=state.gold,
            )
        ]

    def sell_many(self, state: GameState, shop_id: str, item_ids: Sequence[str]) -> ShopBatchResult:
        events: List[ShopEvent] = []
        success = 0
        failure = 0
        for item_id in item_ids:
            result = self.sell(state, shop_id, item_id, quantity=1)
            events.extend(result)
            if result and isinstance(result[0], ShopSaleEvent):
                success += 1
            else:
                failure += 1
        return ShopBatchResult(events=events, success_count=success, failure_count=failure)

    def grant_debug_gold(self, state: GameState, amount: int) -> List[ShopEvent]:
        if amount < 0:
            return [
                ShopActionFailedEvent(
                    reason="invalid_amount",
                    message="Gold amount must be zero or higher.",
                )
            ]
        state.gold += amount
        return [ShopDebugGoldGrantedEvent(amount=amount, total_gold=state.gold)]

    def _resolve_stock_entries(
        self, shop: ShopDef, state: GameState, location_id: str
    ) -> List[ShopStockEntryDef]:
        pool = list(shop.stock_pool)
        if not pool:
            return []
        stock_size = shop.stock_size
        page_count = max(1, (len(pool) + stock_size - 1) // stock_size)
        visits = state.location_visits.get(location_id, 0)
        page_index = visits % page_count
        start = page_index * stock_size
        return pool[start : start + stock_size]

    def _ensure_stock_for_shop(
        self,
        state: GameState,
        location_id: str,
        shop: ShopDef,
        stock_entries: List[ShopStockEntryDef],
    ) -> dict[str, int]:
        visit_count = state.location_visits.get(location_id, 0)
        visit_index = state.shop_stock_visit_index.setdefault(location_id, {})
        remaining_map = state.shop_stock_remaining.setdefault(location_id, {})
        if visit_index.get(shop.id) != visit_count or shop.id not in remaining_map:
            remaining: Dict[str, int] = {entry.id: entry.qty for entry in stock_entries}
            remaining_map[shop.id] = remaining
            visit_index[shop.id] = visit_count
        return remaining_map.setdefault(shop.id, {})

    def _resolve_name(self, shop_type: ShopType, item_id: str) -> str:
        if shop_type == "item":
            return self._items_repo.get(item_id).name
        if shop_type == "weapon":
            return self._weapons_repo.get(item_id).name
        if shop_type == "armour":
            return self._armour_repo.get(item_id).name
        raise ValueError(f"Unsupported shop type '{shop_type}'.")

    def _buy_price(self, shop_type: ShopType, item_id: str) -> int:
        return self._resolve_value(shop_type, item_id)

    def _sell_price(self, shop_type: ShopType, item_id: str) -> int:
        return self._resolve_value(shop_type, item_id) // 2

    def _resolve_value(self, shop_type: ShopType, item_id: str) -> int:
        if shop_type == "item":
            return self._items_repo.get(item_id).value
        if shop_type == "weapon":
            return self._weapons_repo.get(item_id).value
        if shop_type == "armour":
            return self._armour_repo.get(item_id).value
        raise ValueError(f"Unsupported shop type '{shop_type}'.")

    @staticmethod
    def _owned_quantity(state: GameState, shop_type: ShopType, item_id: str) -> int:
        if shop_type == "item":
            return state.inventory.items.get(item_id, 0)
        if shop_type == "weapon":
            return state.inventory.weapons.get(item_id, 0)
        if shop_type == "armour":
            return state.inventory.armour.get(item_id, 0)
        return 0

    @staticmethod
    def _owned_items(state: GameState, shop_type: ShopType) -> dict[str, int]:
        if shop_type == "item":
            return dict(state.inventory.items)
        if shop_type == "weapon":
            return dict(state.inventory.weapons)
        if shop_type == "armour":
            return dict(state.inventory.armour)
        return {}

    @staticmethod
    def _add_to_inventory(state: GameState, shop_type: ShopType, item_id: str, quantity: int) -> None:
        if shop_type == "item":
            state.inventory.add_item(item_id, quantity)
        elif shop_type == "weapon":
            state.inventory.add_weapon(item_id, quantity)
        elif shop_type == "armour":
            state.inventory.add_armour(item_id, quantity)

    @staticmethod
    def _remove_from_inventory(state: GameState, shop_type: ShopType, item_id: str, quantity: int) -> bool:
        if shop_type == "item":
            return state.inventory.remove_item(item_id, quantity)
        if shop_type == "weapon":
            return state.inventory.remove_weapon(item_id, quantity)
        if shop_type == "armour":
            return state.inventory.remove_armour(item_id, quantity)
        return False
