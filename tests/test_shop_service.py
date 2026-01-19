from __future__ import annotations

import json
from pathlib import Path

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ItemsRepository, ShopsRepository, WeaponsRepository
from tbg.domain.state import GameState
from tbg.services.shop_service import (
    ShopActionFailedEvent,
    ShopDebugGoldGrantedEvent,
    ShopPurchaseEvent,
    ShopSaleEvent,
    ShopService,
)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


def _build_service(definitions_dir: Path) -> ShopService:
    items_repo = ItemsRepository(base_path=definitions_dir)
    weapons_repo = WeaponsRepository(base_path=definitions_dir)
    armour_repo = ArmourRepository(base_path=definitions_dir)
    shops_repo = ShopsRepository(
        base_path=definitions_dir,
        items_repo=items_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )
    return ShopService(
        shops_repo=shops_repo,
        items_repo=items_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )


def _build_item_defs(count: int) -> dict:
    return {
        f"item_{idx}": {"name": f"Item {idx}", "kind": "consumable", "value": 5 + idx}
        for idx in range(1, count + 1)
    }


def test_shop_buy_reduces_gold_and_adds_inventory(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(3))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [
                        {"id": "item_1", "qty": 2},
                        {"id": "item_2", "qty": 2},
                        {"id": "item_3", "qty": 2},
                    ],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 10
    state.location_visits["town"] = 0

    events = shop_service.buy(state, "town", "item_shop", "item_1")

    assert isinstance(events[0], ShopPurchaseEvent)
    assert state.gold == 4  # item_1 value = 6
    assert state.inventory.items["item_1"] == 1


def test_shop_buy_fails_when_insufficient_gold(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(1))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "item_1", "qty": 2}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 1
    state.location_visits["town"] = 0

    events = shop_service.buy(state, "town", "item_shop", "item_1")

    assert isinstance(events[0], ShopActionFailedEvent)
    assert state.gold == 1
    assert not state.inventory.items


def test_shop_sell_increases_gold_and_reduces_inventory(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(1))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "item_1", "qty": 2}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 0
    state.inventory.add_item("item_1", 1)

    events = shop_service.sell(state, "item_shop", "item_1")

    assert isinstance(events[0], ShopSaleEvent)
    assert state.gold == 3  # item_1 value = 6, sell price = 3
    assert state.inventory.items.get("item_1") is None


def test_shop_sell_price_uses_floor(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "items.json",
        {"odd_item": {"name": "Odd", "kind": "consumable", "value": 5}},
    )
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "odd_item", "qty": 2}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 0
    state.inventory.add_item("odd_item", 1)

    events = shop_service.sell(state, "item_shop", "odd_item")

    assert isinstance(events[0], ShopSaleEvent)
    assert state.gold == 2


def test_shop_stock_rotation_changes_on_visit_count(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(12))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [
                        {"id": f"item_{idx}", "qty": 1} for idx in range(1, 13)
                    ],
                    "stock_size": 5,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")

    state.location_visits["town"] = 0
    first_page = shop_service.build_shop_view(state, "town", "item_shop")
    assert [entry.item_id for entry in first_page.entries] == [
        "item_1",
        "item_2",
        "item_3",
        "item_4",
        "item_5",
    ]

    state.location_visits["town"] = 1
    second_page = shop_service.build_shop_view(state, "town", "item_shop")
    assert [entry.item_id for entry in second_page.entries] == [
        "item_6",
        "item_7",
        "item_8",
        "item_9",
        "item_10",
    ]

    state.location_visits["town"] = 2
    third_page = shop_service.build_shop_view(state, "town", "item_shop")
    assert [entry.item_id for entry in third_page.entries] == ["item_11", "item_12"]


def test_shop_stock_depletes_and_blocks_purchase(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(1))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "item_1", "qty": 1}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 20
    state.location_visits["town"] = 0

    events = shop_service.buy(state, "town", "item_shop", "item_1")
    assert isinstance(events[0], ShopPurchaseEvent)

    events = shop_service.buy(state, "town", "item_shop", "item_1")
    assert isinstance(events[0], ShopActionFailedEvent)


def test_shop_restock_on_visit_change(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(1))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "item_1", "qty": 1}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 20
    state.location_visits["town"] = 0

    shop_service.buy(state, "town", "item_shop", "item_1")
    view = shop_service.build_shop_view(state, "town", "item_shop")
    assert not view.entries

    state.location_visits["town"] = 1
    view = shop_service.build_shop_view(state, "town", "item_shop")
    assert [entry.item_id for entry in view.entries] == ["item_1"]


def test_shop_debug_gold_grant_and_reject_negative(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(1))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [{"id": "item_1", "qty": 2}],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 5

    events = shop_service.grant_debug_gold(state, 7)

    assert isinstance(events[0], ShopDebugGoldGrantedEvent)
    assert state.gold == 12

    events = shop_service.grant_debug_gold(state, -1)
    assert isinstance(events[0], ShopActionFailedEvent)
    assert state.gold == 12


def test_shop_buy_many_best_effort(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(2))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [
                        {"id": "item_1", "qty": 1},
                        {"id": "item_2", "qty": 1},
                    ],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 8  # item_1 value = 6, item_2 value = 7
    state.location_visits["town"] = 0

    result = shop_service.buy_many(state, "town", "item_shop", ["item_1", "item_2"])

    assert result.success_count == 1
    assert result.failure_count == 1
    assert state.inventory.items.get("item_1") == 1
    assert state.inventory.items.get("item_2") is None


def test_shop_sell_many_best_effort(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "items.json", _build_item_defs(2))
    _write_json(definitions_dir / "weapons.json", {})
    _write_json(definitions_dir / "armour.json", {})
    _write_json(
        definitions_dir / "shops.json",
        {
            "shops": {
                "item_shop": {
                    "id": "item_shop",
                    "name": "Item Shop",
                    "shop_type": "item",
                    "tags": ["town"],
                    "stock_pool": [
                        {"id": "item_1", "qty": 2},
                        {"id": "item_2", "qty": 2},
                    ],
                    "stock_size": 10,
                }
            }
        },
    )
    shop_service = _build_service(definitions_dir)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.gold = 0
    state.inventory.add_item("item_1", 1)

    result = shop_service.sell_many(state, "item_shop", ["item_1", "item_2"])

    assert result.success_count == 1
    assert result.failure_count == 1
    assert state.inventory.items.get("item_1") is None
    assert state.inventory.items.get("item_2") is None
