"""Shop definition structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Tuple


ShopType = Literal["item", "weapon", "armour"]


@dataclass(slots=True)
class ShopStockEntryDef:
    """Defines a stocked item and its quantity."""

    id: str
    qty: int


@dataclass(slots=True)
class ShopDef:
    """Definition for a deterministic shop."""

    id: str
    name: str
    shop_type: ShopType
    tags: Tuple[str, ...] = field(default_factory=tuple)
    stock_pool: Tuple[ShopStockEntryDef, ...] = field(default_factory=tuple)
    stock_size: int = 10
